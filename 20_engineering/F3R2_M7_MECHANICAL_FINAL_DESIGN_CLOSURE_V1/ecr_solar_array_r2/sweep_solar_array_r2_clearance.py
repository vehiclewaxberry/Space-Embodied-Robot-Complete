# -*- coding: utf-8 -*-
"""SOLAR_ARRAY_R2 continuous deployment clearance sweep (ODR-19 item 10).

Sweeps the full deployment sequence
    th1: 0 -> 90 deg (root leaf), then ph2: 0 -> 180 deg, then ph3: 0 -> 180 deg
and evaluates, at EVERY state, with NON-EMPTY comparison sets:
    leaf_k vs bus proxy            (both wings, k=1..3)
    leaf_k vs leaf_{k+1}           (adjacent leaves, both wings)
    leaf_k vs B601 q0 arm witness  (both wings, k=1..3)

Arm is held at q0/stowed witness because the ODR-19 interlock forbids
ARM_RELEASE unless both wings are SOLAR_DEPLOYED_LATCHED; the relevant
solar-deployment hazard is against the stowed arm.

D-R2-05 (recorded in report): HDRM tie-down rods retract INBOARD into
bus-resident sleeves before LEAF1_DEPLOY; the deployment corridor
therefore contains no HDRM hardware and HDRM pairs are not swept.  The
stowed engaged interface is covered in SOLAR_ARRAY_R2_BUILD_REPORT_V1.json
as INTENTIONAL_HDRM_STACK_INTERFACE.

Output: SOLAR_ARRAY_R2_CONTINUOUS_CLEARANCE_V1.json
  - per-state per-pair distance series (non-empty evidence)
  - per-pair sweep minimum + argmin state
  - any positive common volume = automatic FAIL

Run: G:/Windows_program_file/FreeCAD/bin/FreeCADCmd.exe sweep_solar_array_r2_clearance.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import FreeCAD as App
import Part

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import solar_array_r2_kinematics as K

PROJECT_ROOT = HERE.parents[2]
ARM_WITNESS_STEP = (PROJECT_ROOT / "20_engineering" / "cad" /
                    "freecad_authoritative" / "B601_KINEMATIC_ASSEMBLY_Q0_WITNESS.step")
OUTPUT_JSON = HERE / "SOLAR_ARRAY_R2_CONTINUOUS_CLEARANCE_V1.json"

TH1_STEP = 5.0
PH_STEP = 10.0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def local_now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def make_leaf_solid(side: int, leaf: dict) -> Part.Shape:
    origin, e2, e3 = K.leaf_solid_frame(side, leaf)
    m = App.Matrix(
        1.0, 0.0, 0.0, origin[0],
        0.0, e2[1], e3[1], origin[1],
        0.0, e2[2], e3[2], origin[2],
        0.0, 0.0, 0.0, 1.0,
    )
    box = Part.makeBox(K.LEAF_CHORD, K.LEAF_SPAN, K.LEAF_T)
    box.transformShape(m)
    return box


def frange(a, b, step):
    vals = []
    v = a
    while v < b - 1e-9:
        vals.append(round(v, 6))
        v += step
    vals.append(b)
    return vals


def sweep_states():
    """Deployment sequence: th1, then ph2, then ph3 (per ODR-19)."""
    states = []
    for th1 in frange(0.0, 90.0, TH1_STEP):
        states.append((th1, 0.0, 0.0))
    for ph2 in frange(PH_STEP, 180.0, PH_STEP):
        states.append((90.0, ph2, 0.0))
    for ph3 in frange(PH_STEP, 180.0, PH_STEP):
        states.append((90.0, 180.0, ph3))
    # de-duplicate the junction states
    seen = set()
    uniq = []
    for s in states:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq


def dist_common(a: Part.Shape, b: Part.Shape):
    d = float(a.distToShape(b)[0])
    cv = float(a.common(b).Volume) if d <= 1e-7 else 0.0
    return d, cv


def main() -> None:
    bus = Part.makeBox(2 * K.BODY_X_HALF, 2 * K.BODY_CROSS_HALF,
                       2 * K.BODY_CROSS_HALF,
                       App.Vector(-K.BODY_X_HALF, -K.BODY_CROSS_HALF,
                                  -K.BODY_CROSS_HALF))
    arm = Part.read(str(ARM_WITNESS_STEP))

    states = sweep_states()
    series = []
    pair_min = {}

    def record(pair_name, state, d, cv):
        series.append({
            "state_th1_ph2_ph3_deg": list(state),
            "pair": pair_name,
            "minimum_distance_mm": round(d, 9),
            "common_volume_mm3": round(cv, 9),
        })
        cur = pair_min.get(pair_name)
        if cur is None or d < cur["minimum_distance_mm"]:
            pair_min[pair_name] = {
                "minimum_distance_mm": round(d, 9),
                "at_state_th1_ph2_ph3_deg": list(state),
                "common_volume_at_min_mm3": round(cv, 9),
            }
        if cv > 1e-9:
            pair_min[pair_name]["worst_common_volume_mm3"] = max(
                cv, pair_min[pair_name].get("worst_common_volume_mm3", 0.0))

    for state in states:
        for side, wing in ((+1, "LEFT"), (-1, "RIGHT")):
            segs = K.leaf_segments(side, *state)
            solids = [make_leaf_solid(side, leaf) for leaf in segs]
            for k, solid in enumerate(solids, start=1):
                d, cv = dist_common(solid, bus)
                record("R2_%s_LEAF%d_vs_BUS" % (wing, k), state, d, cv)
                d, cv = dist_common(solid, arm)
                record("R2_%s_LEAF%d_vs_B601_Q0" % (wing, k), state, d, cv)
            for k in (0, 1):
                d, cv = dist_common(solids[k], solids[k + 1])
                record("R2_%s_LEAF%d_vs_LEAF%d" % (wing, k + 1, k + 2),
                       state, d, cv)

    violations = [s for s in series if s["common_volume_mm3"] > 1e-9]
    report = {
        "schema": "SOLAR_ARRAY_R2_CONTINUOUS_CLEARANCE_V1",
        "generated_local": local_now(),
        "authority": "ODR-19 item 10 - continuous non-empty clearance evidence",
        "class": "ENGINEERING_CANDIDATE",
        "sweep": {
            "sequence": "th1 0->90 (step 5), ph2 0->180 (step 10), "
                        "ph3 0->180 (step 10), per deployment order",
            "states_evaluated": len(states),
            "arm_state": "B601 q0 witness (ARM_RELEASE forbidden until "
                         "both wings SOLAR_DEPLOYED_LATCHED)",
            "hdrm_semantics": "D-R2-05: tie-down rods retract inboard into "
                              "bus sleeves before LEAF1_DEPLOY; deployment "
                              "corridor contains no HDRM hardware",
        },
        "evidence_integrity": {
            "samples_total": len(series),
            "empty_comparison_sets": 0,
            "note": "every state x pair produced a numeric distance; "
                    "empty-set passes are impossible in this report",
        },
        "pair_sweep_minima": pair_min,
        "violations": violations,
        "verdict": {
            "positive_volume_interferences": len(violations),
            "status": "PASS" if not violations else "FAIL",
        },
        "inputs": {
            "arm_witness_step": ARM_WITNESS_STEP.name,
            "arm_witness_sha256": sha256(ARM_WITNESS_STEP),
        },
        "series": series,
    }
    OUTPUT_JSON.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("R2_SWEEP_DONE states=%d samples=%d violations=%d" %
          (len(states), len(series), len(violations)))
    for name in sorted(pair_min):
        m = pair_min[name]
        print("MIN %-32s d=%s mm at %s" % (
            name, m["minimum_distance_mm"], m["at_state_th1_ph2_ph3_deg"]))

if __name__ == "__main__" or (len(sys.argv) > 1 and
        Path(sys.argv[1]).stem == __name__):
    main()
