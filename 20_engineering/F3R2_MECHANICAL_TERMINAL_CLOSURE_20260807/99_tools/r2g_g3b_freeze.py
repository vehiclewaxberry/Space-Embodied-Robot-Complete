# -*- coding: utf-8 -*-
"""F3R2 G3-B freeze: emit the authoritative pose register, YAML and transition
matrix from the evaluated + searched poses.

Consumers (dynamics, control, embodied policy) read F3R2_ARM_INITIAL_POSE.yaml.
Everything in it is traceable: q from the accepted URDF's limits and the
recorded stow pose, clearance from the CAD meshes, and anything the geometry
cannot answer is written as NOT_EVALUATED with its reason -- never as a pass.
"""
import json
import math
import sys
import traceback

import numpy as np

import r2_common as C
import r2_kin as K
import r2_pose as P
from r2e_g3b_poses import evaluate, home_gate, CLEAR_MIN_MM, MARGIN_MIN_DEG

log = C.Log("r2g_g3b_freeze")
EVAL = C.CFG2 / "F3R2_POSE_EVALUATION.json"
SEARCH = C.CFG2 / "F3R2_POSE_SEARCH.json"
OUTY = C.CFG2 / "F3R2_ARM_INITIAL_POSE.yaml"
OUTC = C.CFG2 / "F3R2_ARM_POSE_REGISTER.csv"
OUTM = C.CFG2 / "F3R2_POSE_TRANSITION_MATRIX.csv"
OUTD = C.CFG2 / "F3R2_INITIAL_POSE_DECISION.md"

Q_STOW = [145.572, -168.0, -57.0, -41.143, -20.954, -3.0]
# joint travel budget for a transition to be called continuous in one move
MAX_SINGLE_MOVE_DEG = 180.0


def yaml_dump(obj, ind=0):
    """Minimal YAML writer (no PyYAML dependency in this environment)."""
    sp = "  " * ind
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)) and v:
                out.append("%s%s:" % (sp, k))
                out.append(yaml_dump(v, ind + 1))
            elif isinstance(v, (dict, list)):
                out.append("%s%s: %s" % (sp, k, "{}" if isinstance(v, dict)
                                         else "[]"))
            else:
                out.append("%s%s: %s" % (sp, k, scalar(v)))
    elif isinstance(obj, list):
        for v in obj:
            if isinstance(v, (dict, list)):
                out.append("%s-" % sp)
                out.append(yaml_dump(v, ind + 1))
            else:
                out.append("%s- %s" % (sp, scalar(v)))
    return "\n".join(out)


def scalar(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return repr(round(v, 6))
    if isinstance(v, str):
        return v if (v and all(c.isalnum() or c in "._-/+" for c in v)) \
            else json.dumps(v, ensure_ascii=False)
    return str(v)


def main():
    rep = {"schema": "F3R2_POSE_FREEZE_V1"}
    try:
        C.check_protected2("G3B_FREEZE_PRE")
        ev = json.loads(EVAL.read_text(encoding="utf-8"))
        se = json.loads(SEARCH.read_text(encoding="utf-8"))
        arms = P.arm_parts("DEPLOYED")
        envs = P.env_parts("DEPLOYED",
                           wings=("WING_L_DEPLOYED", "WING_R_DEPLOYED"))

        poses = {}
        poses["Q_AS_BUILT_REFERENCE"] = ev["poses"]["Q_AS_BUILT_REFERENCE"]
        poses["Q_STOW_ENGINEERING_CANDIDATE"] = \
            ev["poses"]["Q_STOW_ENGINEERING_CANDIDATE"]
        for name in ("Q_DEPLOYED_HOME", "Q_RELEASE_CLEAR", "Q_SERVICE_READY"):
            r = se["results"][name]
            if r["status"] != "FROZEN":
                raise RuntimeError("%s not frozen: %s" % (name, r["status"]))
            e = dict(r["chosen"]["evaluation"])
            e["gate"] = r["chosen"]["gate"]
            e["feasible_grid_points"] = r["feasible_candidates"]
            poses[name] = e

        # --- provenance and intent, written per pose, never inferred later ---
        meta = {
            "Q_AS_BUILT_REFERENCE": {
                "source": ("URDF zero pose == the pose the CAD arm stands in "
                           "inside F3R1_V3_DEPLOYED_NOMINAL.step"),
                "cad_configuration": "DEPLOYED_NOMINAL / SERVICE (arm default)",
                "intended_control_use": ("geometric datum only; every other "
                                         "pose is measured from it"),
                "runtime": False,
                "hold": ("NOT A CONTROL START STATE: joint2 and joint3 sit "
                         "exactly on their upper mechanical stop (both limits "
                         "0.000 deg), limit margin 0.0 deg")},
            "Q_DEPLOYED_HOME": {
                "source": ("deterministic grid search inside accepted joint "
                           "limits, mesh-verified against the CAD assembly"),
                "cad_configuration": "DEPLOYED_NOMINAL",
                "intended_control_use": ("control and dynamics initialisation "
                                         "truth; the pose every controller "
                                         "starts from"),
                "runtime": True, "hold": None},
            "Q_RELEASE_CLEAR": {
                "source": "deterministic grid search, saddle-clearance first",
                "cad_configuration": "DEPLOYED_NOMINAL",
                "intended_control_use": ("first safe pose after the stow "
                                         "restraint releases"),
                "runtime": True,
                "hold": ("the RELEASE SEQUENCE itself is not authorised; this "
                         "is the geometric end state only, and ARM HDRM "
                         "hardware does not exist yet (G4)")},
            "Q_SERVICE_READY": {
                "source": ("deterministic grid search, +x service-axis reach "
                           "objective"),
                "cad_configuration": "SERVICE",
                "intended_control_use": "pre-service staging pose",
                "runtime": True,
                "hold": ("SERVICE configuration itself remains "
                         "PENDING_RATIFICATION_HOLD from G2")},
            "Q_STOW_ENGINEERING_CANDIDATE": {
                "source": ("F3R1_STOW_POSE_REPORT.json q_stow_deg, baked into "
                           "F3R1_V3_STOWED_ENGINEERING_CANDIDATE.step"),
                "cad_configuration": "STOWED_ENGINEERING_CANDIDATE",
                "intended_control_use": ("launch / transport restraint "
                                         "candidate; NOT a control start state"),
                "runtime": False,
                "hold": ("O13_V3_CANDIDATE_HOLD_PROVISIONAL; contacts the "
                         "G07/G08/Mid placeholder blocks (0.001-0.319 mm) and "
                         "those blocks are not real supports")},
        }
        for k, m in meta.items():
            poses[k].update(m)

        # --- transition matrix ---
        order = ["Q_STOW_ENGINEERING_CANDIDATE", "Q_RELEASE_CLEAR",
                 "Q_DEPLOYED_HOME", "Q_SERVICE_READY",
                 "Q_AS_BUILT_REFERENCE"]
        trans = []
        for a in order:
            for b in order:
                if a == b:
                    continue
                qa = np.array(poses[a]["q_deg"], dtype=float)
                qb = np.array(poses[b]["q_deg"], dtype=float)
                d = np.abs(qb - qa)
                trans.append({
                    "from": a, "to": b,
                    "delta_deg_per_joint": [round(float(x), 3) for x in d],
                    "max_joint_travel_deg": round(float(d.max()), 3),
                    "total_joint_travel_deg": round(float(d.sum()), 3),
                    "single_move_feasible":
                        bool(d.max() <= MAX_SINGLE_MOVE_DEG),
                    "path_clearance_verified": "NOT_YET -- G5 sweeps the path",
                    "endpoints_both_runtime": bool(
                        poses[a].get("runtime") and poses[b].get("runtime"))})

        # --- register CSV ---
        rows = []
        for name, p in poses.items():
            rows.append({
                "pose": name,
                "q_deg": json.dumps(p["q_deg"]),
                "q_rad": json.dumps(p["q_rad"]),
                "joint_limits_valid": p["joint_limits_valid"],
                "nearest_joint_limit_margin_deg":
                    p["nearest_joint_limit_margin_deg"],
                "ee_position_mm": json.dumps(
                    p["end_effector_pose_mm"]["position"]),
                "min_arm_to_bus_mm": p["min_arm_to_bus_mm"],
                "min_arm_to_wing_mm": p["min_arm_to_wing_mm"],
                "min_arm_to_saddle_mm": p["min_arm_to_saddle_mm"],
                "min_gripper_to_bus_mm": p["min_gripper_to_bus_mm"],
                "camera_visibility": p["camera_visibility"],
                "urdf_sha256": C.R.URDF_SHA,
                "cad_configuration": p["cad_configuration"],
                "runtime": p["runtime"],
                "intended_control_use": p["intended_control_use"],
                "hold": p["hold"] or "",
                "source": p["source"]})
        C.write_csv(OUTC, rows)
        C.write_csv(OUTM, trans, fields=[
            "from", "to", "max_joint_travel_deg", "total_joint_travel_deg",
            "single_move_feasible", "endpoints_both_runtime",
            "path_clearance_verified", "delta_deg_per_joint"])

        # --- YAML for consumers ---
        y = {
            "schema": "F3R2_ARM_INITIAL_POSE_V1",
            "frozen_utc": "2026-08-07",
            "kinematics_authority": {
                "urdf": str(C.R.URDF), "sha256": C.R.URDF_SHA,
                "note": ("topology, axes, joint limits and FK only; the URDF "
                         "collision STLs are NOT the mechanical geometry of "
                         "this assembly")},
            "geometry_authority": {
                "source": ("B51 CAD links, tessellated from the hash-bound G2 "
                           "per-configuration STEPs"),
                "mesh_deflection_mm": 0.5,
                "note": ("clearance numbers below are mesh-tier; SolidWorks "
                         "native B-rep interference was NOT obtainable on this "
                         "machine -- see 05_clearance/G3A_NATIVE_ATTEMPTS.json")},
            "mount": {"transform_mm_rows": P.K.T_MOUNT.tolist(),
                      "clock_deg": P.K.CLOCK_DEG,
                      "station": P.K.MOUNT_STATION},
            "joint_order": K.ARM_JOINTS,
            "joint_limits_deg": {j: list(K.LIMITS_DEG[j])
                                 for j in K.ARM_JOINTS},
            "acceptance_thresholds": {
                "min_clearance_mm": CLEAR_MIN_MM,
                "min_joint_limit_margin_deg": MARGIN_MIN_DEG},
            "poses": {},
        }
        for name, p in poses.items():
            y["poses"][name] = {
                "q_deg": p["q_deg"], "q_rad": p["q_rad"],
                "runtime": p["runtime"],
                "cad_configuration": p["cad_configuration"],
                "intended_control_use": p["intended_control_use"],
                "source": p["source"],
                "hold": p["hold"],
                "joint_limits_valid": p["joint_limits_valid"],
                "nearest_joint_limit_margin_deg":
                    p["nearest_joint_limit_margin_deg"],
                "end_effector_position_mm":
                    p["end_effector_pose_mm"]["position"],
                "base_to_ee_transform_mm": p["base_to_ee_transform_mm"],
                "clearance_mm": {
                    "arm_to_bus": p["min_arm_to_bus_mm"],
                    "arm_to_wing": p["min_arm_to_wing_mm"],
                    "arm_to_saddle_placeholder": p["min_arm_to_saddle_mm"],
                    "gripper_to_bus": p["min_gripper_to_bus_mm"]},
                "comparison_sets": {"bus_pairs": p["n_bus_pairs"],
                                    "wing_pairs": p["n_wing_pairs"],
                                    "saddle_pairs": p["n_saddle_pairs"]},
                "camera_visibility": p["camera_visibility"],
                "home_gate": p.get("gate"),
            }
        y["runtime_pose_enum"] = [k for k, p in poses.items() if p["runtime"]]
        y["non_runtime_poses"] = [k for k, p in poses.items()
                                  if not p["runtime"]]
        OUTY.write_text("# F3R2 frozen arm poses -- machine-readable SSOT\n"
                        + yaml_dump(y) + "\n", encoding="utf-8")

        rep["poses_frozen"] = list(poses)
        rep["runtime_poses"] = y["runtime_pose_enum"]
        rep["transition_rows"] = len(trans)
        rep["outputs"] = [str(OUTY), str(OUTC), str(OUTM)]
        rep["protected_post"] = C.check_protected2("G3B_FREEZE_POST")["verdict"]
        rep["verdict"] = "G3B_POSES_FROZEN"
        C.write_json(C.CFG2 / "F3R2_POSE_FREEZE.json", rep)
        print("verdict:", rep["verdict"])
        for name, p in poses.items():
            print("  %-30s q=%s runtime=%s margin=%.2f bus=%s wing=%s"
                  % (name, p["q_deg"], p["runtime"],
                     p["nearest_joint_limit_margin_deg"],
                     p["min_arm_to_bus_mm"], p["min_arm_to_wing_mm"]))
        print("  runtime enum:", y["runtime_pose_enum"])
        print("  transitions:", len(trans))
    except Exception as exc:
        rep["verdict"] = "G3B_FREEZE_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-2000:]
        C.write_json(C.CFG2 / "F3R2_POSE_FREEZE.json", rep)
        print("FAIL:", exc)
        print(rep["traceback"])
    sys.exit(0 if rep["verdict"] == "G3B_POSES_FROZEN" else 1)


if __name__ == "__main__":
    main()
