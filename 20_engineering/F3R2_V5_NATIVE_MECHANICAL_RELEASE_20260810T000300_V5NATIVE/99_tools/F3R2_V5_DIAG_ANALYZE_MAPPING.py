#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline analysis of the source-body probe against the frozen assignment CSV.
Determines candidate label mapping structure and the local lateral axis."""

from __future__ import annotations

import collections
import csv
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple


ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
RUN_ROOT = ROOT / "20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
PROBE = RUN_ROOT / "13_validation/V5_DIAG_SOURCE_BODY_PROBE.json"
CSV = ROOT / "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/08_camera_harness/F3R2_GRIPPER_SOLID_ASSIGNMENT.csv"


def body_key(row: Dict[str, Any]) -> Tuple[float, int]:
    return (round(float(row["volume_mm3"]), 3), int(row["faces"]))


def main() -> None:
    probe = json.loads(PROBE.read_text(encoding="utf-8"))
    bodies = probe["bodies"]
    rows = [r for r in csv.DictReader(CSV.open("r", encoding="utf-8-sig", newline="")) if not r["solid"].endswith("057")]
    labels = {r["solid"]: r for r in rows}

    print("== name suffix distribution ==")
    suffixes: Dict[str, int] = {}
    for b in bodies:
        m = re.search(r"1\.1\.(\d+)\[1\]", b["name"])
        suffix = m.group(1) if m else "??"
        suffixes[suffix] = suffixes.get(suffix, 0) + 1
        b["suffix"] = suffix
    print("unique suffixes:", len(suffixes), "counts:", collections.Counter(suffixes.values()))

    print("\n== sequential order check (sorted by suffix vs CSV order) ==")
    sorted_by_suffix = sorted(bodies, key=lambda b: int(b["suffix"]) if b["suffix"] != "??" else 10 ** 9)
    order_matches = 0
    mismatches = []
    for index, (body, label_row) in enumerate(zip(sorted_by_suffix, rows)):
        ok = body["faces"] == int(label_row["faces"]) and abs(float(body["volume_mm3"]) - float(label_row["volume_mm3"])) <= 0.11
        if ok:
            order_matches += 1
        else:
            mismatches.append((index, body["suffix"], body["faces"], body["volume_mm3"], label_row["solid"], label_row["faces"], label_row["volume_mm3"]))
    print("sequential matches:", order_matches, "/", len(rows))
    for m in mismatches[:12]:
        print("  MISMATCH", m)

    print("\n== collision groups by (volume,faces) ==")
    by_key: Dict[Tuple[float, int], List[Dict[str, Any]]] = collections.defaultdict(list)
    for b in bodies:
        by_key[body_key(b)].append(b)
    colliding = {k: v for k, v in by_key.items() if len(v) > 1}
    print("collision groups:", len(colliding))

    print("\n== unique-contract palm bodies: lateral-axis hypothesis ==")
    unique = [v[0] for v in by_key.values() if len(v) == 1]
    print("unique bodies:", len(unique))
    for b in unique:
        print("  ", b["suffix"], b["faces"], round(float(b["volume_mm3"]), 3), "c=", [round(v, 3) for v in b["mass_centroid_mm"]])

    print("\n== mirror-pair structure in local frame (same volume+faces, centroid mirror) ==")
    # For each collision group, pair bodies whose centroids are symmetric about
    # one coordinate axis: centroid_a + centroid_b == (2*tx, 2*ty, 2*tz) with
    # two coordinates equal and the third negated in relative terms.
    for key, group in sorted(colliding.items(), key=lambda kv: -len(kv[1])):
        group = list(group)
        used = set()
        pairs: List[Tuple[int, int, str, float]] = []
        for i in range(len(group)):
            if i in used:
                continue
            best = None
            for j in range(i + 1, len(group)):
                if j in used:
                    continue
                a = group[i]["mass_centroid_mm"]
                c = group[j]["mass_centroid_mm"]
                for axis in (0, 1, 2):
                    others_equal = all(abs(a[k] - c[k]) <= 0.05 for k in range(3) if k != axis)
                    center = (a[axis] + c[axis]) / 2.0
                    if others_equal and abs(center) <= 0.15:
                        score = abs(a[axis] - c[axis])
                        if best is None or score > best[3]:
                            best = (i, j, "xyz"[axis], score)
            if best is not None:
                pairs.append(best)
                used.add(best[0])
                used.add(best[1])
        print("group", key, "n=", len(group), "pairs=", len(pairs), "unpaired=", sorted(set(range(len(group))) - used),
              "axis_scores=", [(p[0], p[1], p[2], round(p[3], 4)) for p in pairs[:8]])

    print("\n== per-group CSV order (labels sorted) ==")
    by_group: Dict[str, List[Tuple[str, str]]] = collections.defaultdict(list)
    for r in rows:
        by_group[r["assigned_body"]].append((r["solid"], str(round(float(r["s_on_jaw_axis_mm"]), 3))))
    for g in ("gripper_link", "gripper_left", "gripper_right"):
        print(g, len(by_group[g]), by_group[g])


if __name__ == "__main__":
    main()
