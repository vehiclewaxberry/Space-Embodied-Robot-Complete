"""Build the VIZ-Gate 0 coordinate-frame registry from read-only truth data.

The registry is the compact, machine-readable companion to the rendered
triads.  It deliberately follows the frozen SSOT naming migration:

* B = servicer free-flyer / mother-body base (not the robot mount);
* M = arm mounting face and B601 URDF base reference;
* E = end effector at the E1.5 display configuration;
* G1..G3 = the three debris grasp frames used by the E1/E1.5 candidate grid.

No CAD, URDF, simulation result, or SSOT file is modified.
"""
import _viz_bootstrap as vb

import csv
import json
import os

import numpy as np

import scene_assembly as sa
from e1_thin_slice import GRASP_POINTS


OUT_CSV = os.path.join(vb.VIZ_TABLES_DIR, "frame_registry_v1.csv")
COLUMNS = [
    "frame_name",
    "parent_frame",
    "translation_m",
    "quaternion_wxyz",
    "source_file",
    "confidence",
    "context_note",
    "scenario_hash",
]


def _quat_wxyz(R):
    """Deterministic unit quaternion for a proper 3x3 rotation matrix."""
    R = np.asarray(R, float)
    tr = float(np.trace(R))
    if tr > 0.0:
        s = np.sqrt(tr + 1.0) * 2.0
        w = 0.25 * s
        x = (R[2, 1] - R[1, 2]) / s
        y = (R[0, 2] - R[2, 0]) / s
        z = (R[1, 0] - R[0, 1]) / s
    else:
        i = int(np.argmax(np.diag(R)))
        if i == 0:
            s = np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2.0
            w = (R[2, 1] - R[1, 2]) / s
            x = 0.25 * s
            y = (R[0, 1] + R[1, 0]) / s
            z = (R[0, 2] + R[2, 0]) / s
        elif i == 1:
            s = np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2.0
            w = (R[0, 2] - R[2, 0]) / s
            x = (R[0, 1] + R[1, 0]) / s
            y = 0.25 * s
            z = (R[1, 2] + R[2, 1]) / s
        else:
            s = np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2.0
            w = (R[1, 0] - R[0, 1]) / s
            x = (R[0, 2] + R[2, 0]) / s
            y = (R[1, 2] + R[2, 1]) / s
            z = 0.25 * s
    q = np.asarray([w, x, y, z], float)
    q /= np.linalg.norm(q)
    if q[0] < 0.0:
        q *= -1.0
    return q


def _compact(values):
    vals = [0.0 if abs(float(v)) < 5e-13 else round(float(v), 12)
            for v in values]
    return json.dumps(vals, ensure_ascii=False, separators=(",", ":"))


def _row(name, parent, T, source, confidence, note, scenario_hash=""):
    T = np.asarray(T, float)
    return {
        "frame_name": name,
        "parent_frame": parent,
        "translation_m": _compact(T[:3, 3]),
        "quaternion_wxyz": _compact(_quat_wxyz(T[:3, :3])),
        "source_file": source,
        "confidence": confidence,
        "context_note": note,
        "scenario_hash": scenario_hash,
    }


def build_rows():
    I4 = np.eye(4)
    sel = sa.e15_selected_case()
    arm = sa.arm_frames(sel["q"])
    sat = sa.satellite_scene()
    deb = sa.debris_scene()

    # E is expressed relative to M, matching the SSOT transform T_ME(q).
    T_M_E = np.linalg.inv(arm["T_SM"]) @ arm["T_E"]

    rows = [
        _row(
            "I", "", I4,
            "20_engineering/stage1_spacecraft_layout/04_mass_inertia_budget/"
            "coordinate_frame_definition_v0.md",
            "reference definition",
            "Inertial/world root; the static registry snapshot uses t=0.",
        ),
        _row(
            "S", "I", I4,
            "20_engineering/config/geometry/frame_tree_v1.yaml; "
            "30_simulation/sim_05_free_floating_arm/results/sim_05_base_attitude.csv",
            "nominal frame; t=0 pose is display reference",
            "Static t=0 identity only; the Dynamics replay supplies I-to-S attitude.",
        ),
        _row(
            "B", "S", I4,
            "20_engineering/stage1_spacecraft_layout/04_mass_inertia_budget/"
            "coordinate_frame_definition_v0.md sec 2/3",
            "default/unverified",
            "SSOT B is the free-flyer mother-body base. Default T_SB is identity; "
            "a measured CoM offset is still required.",
        ),
        _row(
            "M", "S", arm["T_SM"],
            "20_engineering/config/geometry/frame_tree_v1.yaml; coordinate_frame_definition_v0.md sec 3.1",
            "nominal_frozen_v1",
            "Arm mounting face and B601 URDF base reference (the deprecated robot-base B).",
        ),
        _row(
            "E", "M", T_M_E,
            "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf; "
            "E1.5 e15_results_72cases.csv selected_q_json",
            "FK verified; geometry-selected, dynamics not admissible",
            f"Display configuration {sel['case_id']}; T_ME(q), not a flight trajectory.",
            sel["scenario_hash"],
        ),
        _row(
            "T", "S", sat["T_S_T"],
            "target_satellite_v0.json; 30_simulation/sim_09_grasp_evaluator/src/adapters.py::scene_placement",
            "display nominal; geometry only",
            "22 kg satellite main-assembly placement at t=0; E1/E1.5 did not evaluate this target.",
        ),
        _row(
            "D", "S", deb["T_S_T"],
            "target_debris_v0.json; 30_simulation/sim_09_grasp_evaluator/src/adapters.py::scene_placement",
            "E1 context placement; E1.5 evidence target",
            "Reference placement P1/tc0/v10mm/6D; E1 and E1.5 hashes differ because E1.5 includes roll.",
            deb["e1_candidate_hash"],
        ),
    ]

    for idx, pid in enumerate(("P1", "P2", "P3"), start=1):
        gp = GRASP_POINTS[pid]
        T_D_G = np.eye(4)
        T_D_G[:3, :3] = np.asarray(gp["R_C"], float)
        T_D_G[:3, 3] = np.asarray(gp["p_D"], float)
        rows.append(_row(
            f"G{idx}", "D", T_D_G,
            "30_simulation/sim_09_grasp_evaluator/src/e1_thin_slice.py::GRASP_POINTS; "
            "E1.5 e15_geometry_manifest.json",
            "geometry grid verified; dynamics status varies by case",
            f"{pid} local grasp frame; +z_G is the outward approach normal; "
            "roll is applied about +z_G.",
        ))
    return rows


def write_csv(path=OUT_CSV):
    rows = build_rows()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return rows


def main():
    rows = write_csv()
    print(f"frame registry written: {os.path.relpath(OUT_CSV, vb.REPO_ROOT)} "
          f"({len(rows)} frames)")
    return rows


if __name__ == "__main__":
    main()
