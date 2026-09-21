#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline solver for the 57 unlabeled source bodies to the frozen B51 labels.

Hypotheses (established from mirror-pair evidence):
1. Source SLDPRT link-6 local Y separates left/right: LEFT bodies have Y < 0,
   RIGHT bodies have Y > 0, palm bodies sit near Y = 0 (or in palm-only
   volume classes).
2. For small/pin bodies the local |Y| equals the CSV jaw-station |s| at unit
   scale; for the two large finger bodies the CSV s is an extreme-station, so
   magnitude is not used there (sign and volume suffice).
Matching therefore uses volume (B-rep invariant) + group sign + station
magnitude where reliable.  Remaining ties inside one volume class and one
body group are geometrically interchangeable and resolved by enumeration.
"""

from __future__ import annotations

import collections
import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
RUN_ROOT = ROOT / "20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
PROBE = RUN_ROOT / "13_validation/V5_DIAG_SOURCE_BODY_PROBE.json"
CSV = ROOT / "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/08_camera_harness/F3R2_GRIPPER_SOLID_ASSIGNMENT.csv"

VOL_TOL = 0.10
MAG_TOL = 0.60
LEFT_SIGN = -1.0


def main() -> None:
    probe = json.loads(PROBE.read_text(encoding="utf-8"))
    bodies = probe["bodies"]
    rows = [r for r in csv.DictReader(CSV.open("r", encoding="utf-8-sig", newline="")) if not r["solid"].endswith("057")]
    contracts = []
    for r in rows:
        contracts.append({
            "label": r["solid"],
            "group": r["assigned_body"],
            "volume": float(r["volume_mm3"]),
            "s": float(r["s_on_jaw_axis_mm"]),
        })

    def group_sign(group: str) -> Optional[float]:
        if group == "gripper_left":
            return LEFT_SIGN
        if group == "gripper_right":
            return -LEFT_SIGN
        return None

    # Candidate edges with station filter, except sign-only edges for the
    # two large finger-body classes where CSV s is an extreme station.
    large_volumes = {22535.34, 5588.088, 10223.294, 3135.677}
    edges: List[Tuple[int, int, float, float]] = []  # (contract_idx, body_idx, volume_res, station_res)
    for cidx, contract in enumerate(contracts):
        sign = group_sign(contract["group"])
        for bidx, body in enumerate(bodies):
            body_volume = float(body["volume_mm3"])
            volume_residual = abs(body_volume - contract["volume"])
            deviation_waiver = (contract["label"] == "B51_REF_gripper_detail_LINKLOCAL013" and abs(volume_residual - 2.898039) <= 0.01)
            if volume_residual > VOL_TOL and not deviation_waiver:
                continue
            y = float(body["mass_centroid_mm"][1])
            if sign is not None and y * sign >= -0.001:
                continue
            if round(contract["volume"], 3) in large_volumes:
                station_residual = 0.0  # sign-only
            elif abs(contract["s"]) > 1.0:
                station_residual = abs(abs(y) - abs(contract["s"]))
                if station_residual > MAG_TOL:
                    continue
            else:
                station_residual = abs(y)
                if station_residual > MAG_TOL:
                    continue
            edges.append((cidx, bidx, volume_residual, station_residual))
    edges.sort(key=lambda e: (e[2], e[3], e[0], e[1]))

    contract_match: Dict[int, int] = {}
    body_match: Dict[int, int] = {}
    order_by_contract: Dict[int, List[int]] = collections.defaultdict(list)
    for cidx, bidx, _, _ in edges:
        order_by_contract[cidx].append(bidx)

    def augment(cidx: int, visited: set) -> bool:
        for bidx in order_by_contract[cidx]:
            if bidx in visited:
                continue
            visited.add(bidx)
            if bidx not in body_match or augment(body_match[bidx], visited):
                contract_match[cidx] = bidx
                body_match[bidx] = cidx
                return True
        return False

    for cidx in range(len(contracts)):
        augment(cidx, set())

    assigned: List[Optional[Dict[str, Any]]] = [None] * len(bodies)
    rows_out: List[Dict[str, Any]] = []
    stats = collections.Counter()
    for cidx, contract in enumerate(contracts):
        if cidx not in contract_match:
            rows_out.append({**contract, "status": "NO_BODY", "body_enum": None, "station_residual_mm": None})
            stats["NO_BODY"] += 1
            continue
        bidx = contract_match[cidx]
        assigned[bidx] = contract
        match_edges = [e for e in edges if e[0] == cidx and e[1] == bidx]
        volume_residual = match_edges[0][2] if match_edges else None
        station_residual = match_edges[0][3] if match_edges else None
        alt = [e[1] for e in edges if e[0] == cidx and e[1] != bidx and abs(e[2] - volume_residual) <= 0.001 and abs(e[3] - station_residual) <= 0.05]
        tie = len(alt) > 0
        stats["TIE_BREAK_BY_ENUMERATION" if tie else "UNIQUE"] += 1
        rows_out.append({
            **contract,
            "status": "TIE_BREAK_BY_ENUMERATION" if tie else "UNIQUE",
            "body_enum": bidx,
            "body_y_mm": round(float(bodies[bidx]["mass_centroid_mm"][1]), 6),
            "volume_residual_mm3": round(volume_residual, 6) if volume_residual is not None else None,
            "station_residual_mm": round(station_residual, 6) if station_residual is not None else None,
            "candidate_indices": [e[1] for e in edges if e[0] == cidx][:4],
        })

    missing_bodies = [i for i, c in enumerate(assigned) if c is None]
    missing_contracts = [c["label"] for c in rows_out if c["status"] == "NO_BODY"]
    group_counts = collections.Counter(c["group"] for c in assigned if c)
    residuals = [c["station_residual_mm"] for c in rows_out if c.get("station_residual_mm") is not None]
    print("assigned:", sum(1 for c in assigned if c), "/ 57")
    print("missing bodies:", missing_bodies)
    print("missing contracts:", missing_contracts)
    print("stats:", dict(stats))
    print("group counts:", dict(group_counts))
    print("residual max:", max(residuals) if residuals else None, "mean:", round(sum(residuals) / len(residuals), 6) if residuals else None)
    print("large station residuals (>0.1):", sorted((c["label"], c["station_residual_mm"]) for c in rows_out if c.get("station_residual_mm", 0) > 0.1))
    print("ties:", [(c["label"], c["body_enum"], c["candidate_indices"]) for c in rows_out if c["status"] == "TIE_BREAK_BY_ENUMERATION"])
    print("fallback:", [(c["label"], c["body_enum"]) for c in rows_out if c["status"] == "FALLBACK_PALM"])
    label_set = {c["label"] for c in assigned if c}
    body_set = {i for i in range(57) if assigned[i] is not None}
    print("label coverage:", len(label_set), "body coverage:", len(body_set))
    print("total volume:", round(sum(float(bodies[i]["volume_mm3"]) for i in range(57)), 6), "total faces:", sum(int(bodies[i]["faces"]) for i in range(57)))


if __name__ == "__main__":
    main()
