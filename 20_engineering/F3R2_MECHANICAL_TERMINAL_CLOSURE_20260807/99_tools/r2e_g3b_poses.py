# -*- coding: utf-8 -*-
"""F3R2 G3-B: freeze the five named arm poses.

  Q_AS_BUILT_REFERENCE        the pose the CAD actually stands in (q = 0)
  Q_DEPLOYED_HOME             control/dynamics initialisation truth
  Q_RELEASE_CLEAR             first safe pose after the stow restraint releases
  Q_SERVICE_READY             pre-service staging pose
  Q_STOW_ENGINEERING_CANDIDATE the provisional stow pose (O13_V3 hold)

Nothing is guessed: q values come from the accepted URDF (limits, FK) and from
the recorded F3R1 stow pose; clearances come from the CAD meshes; every metric
the geometry cannot supply is written as NOT_EVALUATED with the reason.

Q_DEPLOYED_HOME must satisfy, all fail-closed:
  1 arm-to-bus interference   = 0
  2 arm-to-wing interference  = 0
  3 arm-to-bus comparison set  nonempty
  4 arm-to-wing comparison set nonempty
  5 every critical minimum distance is a finite number
  6 gripper clear of the bus
  7 joint limits valid with margin
  8 does not depend on G07/G08/Mid contact, nor on ARM HDRM lock
Camera visibility is NOT_EVALUATED until a camera exists (G4) -- it is not
silently passed.
"""
import json
import math
import sys
import traceback

import numpy as np

import r2_common as C
import r2_kin as K
import r2_pose as P

log = C.Log("r2e_g3b")
OUTY = C.CFG2 / "F3R2_ARM_INITIAL_POSE.yaml"
OUTC = C.CFG2 / "F3R2_ARM_POSE_REGISTER.csv"
OUTJ = C.CFG2 / "F3R2_POSE_EVALUATION.json"

Q_STOW = [145.572, -168.0, -57.0, -41.143, -20.954, -3.0]
MARGIN_MIN_DEG = 3.0          # keep away from mechanical stops
CLEAR_MIN_MM = 5.0            # bus/wing clearance target for HOME
SADDLES = set(P.SADDLES)


def evaluate(q_deg, arms, envs, label, stride=6, q_ref=None):
    """Full clearance evaluation of one pose against one environment set.

    q_ref is the pose the arm meshes are baked at (None == q = 0)."""
    rows, _ = P.screen_pose(q_deg, arms, envs, aabb_trigger=CLEAR_MIN_MM + 3.0,
                            stride=stride, q_ref=q_ref)
    for r in rows:
        g = P.effective_gap(r)
        r["effective_gap_mm"] = None if g is None else round(g, 4)
    bus = [r for r in rows if r["env_role"] in ("BUS_STRUCTURE",
                                                "ARM_MOUNT_INTERFACE")
           and not (r["env_role"] == "ARM_MOUNT_INTERFACE"
                    and r["link"] == "base_link")]
    # base_link is bolted to the bus and does not move with q, so a bus
    # clearance dominated by it is the SAME number for every pose -- a
    # fail-open metric.  The pose-sensitive quantity is the moving chain only.
    moving = [r for r in bus if r["link"] != "base_link"]
    wing = [r for r in rows if r["env_role"] == "SOLAR_WING"]
    sad = [r for r in rows if r["env_role"] == "SADDLE_PLACEHOLDER"]
    ref = [r for r in rows if r["env_role"] == "REFERENCE_ONLY"]
    grip = [r for r in rows if r["link"] == "gripper_link"
            and r["env_role"] in ("BUS_STRUCTURE", "ARM_MOUNT_INTERFACE")]

    def mn(rs):
        vals = [r["effective_gap_mm"] for r in rs
                if r["effective_gap_mm"] is not None]
        return min(vals) if vals else None

    def n_uneval(rs):
        return sum(1 for r in rs if r["tier"] == "CANNOT_EVALUATE")

    lim = K.within_limits(q_deg)
    worst_margin = min(v["margin_deg"] for v in lim.values())
    T = K.link_world(q_deg)
    ee = T["gripper_link"]
    out = {
        "label": label,
        "q_deg": [round(float(v), 4) for v in q_deg],
        "q_rad": [round(math.radians(float(v)), 6) for v in q_deg],
        "joint_limits": lim,
        "nearest_joint_limit_margin_deg": round(worst_margin, 4),
        "joint_limits_valid": all(v["inside"] for v in lim.values()),
        "end_effector_pose_mm": {
            "position": [round(float(x), 4) for x in ee[:3, 3]],
            "R_rows": [[round(float(x), 6) for x in r] for r in ee[:3, :3]]},
        "base_to_ee_transform_mm": [[round(float(x), 6) for x in r]
                                    for r in (np.linalg.inv(P.K.T_MOUNT) @ ee)],
        "min_arm_to_bus_mm": mn(bus),
        "min_moving_link_to_bus_mm": mn(moving),
        "min_arm_to_wing_mm": mn(wing),
        "min_arm_to_saddle_mm": mn(sad),
        "min_gripper_to_bus_mm": mn(grip),
        "min_arm_to_reference_body_mm": mn(ref),
        "n_bus_pairs": len(bus), "n_moving_bus_pairs": len(moving),
        "n_wing_pairs": len(wing),
        "n_saddle_pairs": len(sad),
        # An unevaluable pair counts as an interference: fail-closed.
        "bus_interference_count": sum(
            1 for r in bus if r["effective_gap_mm"] is None
            or r["effective_gap_mm"] <= 0.5),
        "moving_link_bus_interference_count": sum(
            1 for r in moving if r["effective_gap_mm"] is None
            or r["effective_gap_mm"] <= 0.5),
        "wing_interference_count": sum(
            1 for r in wing if r["effective_gap_mm"] is None
            or r["effective_gap_mm"] <= 0.5),
        "saddle_contact_count": sum(
            1 for r in sad if r["effective_gap_mm"] is None
            or r["effective_gap_mm"] <= 0.5),
        "unevaluable_pairs": {"bus": n_uneval(bus), "moving": n_uneval(moving),
                              "wing": n_uneval(wing), "saddle": n_uneval(sad),
                              "total": n_uneval(rows)},
        "camera_visibility": "NOT_EVALUATED_NO_CAMERA_IN_ASSEMBLY",
        "worst_pairs": sorted(
            [{"arm": r["arm_part"], "env": r["env_part"],
              "role": r["env_role"], "gap_mm": r["effective_gap_mm"],
              "tier": r["tier"]} for r in rows],
            key=lambda d: (d["gap_mm"] is not None, d["gap_mm"] or 0))[:8],
    }
    return out, rows


def home_gate(ev):
    """The eight hard requirements for Q_DEPLOYED_HOME, plus the pose-sensitive
    moving-chain check that the plain arm-to-bus number cannot provide."""
    g = {
        "1_arm_to_bus_interference_zero": ev["bus_interference_count"] == 0,
        "2_arm_to_wing_interference_zero": ev["wing_interference_count"] == 0,
        "3_bus_comparison_set_nonempty": ev["n_bus_pairs"] > 0,
        "4_wing_comparison_set_nonempty": ev["n_wing_pairs"] > 0,
        "5_all_critical_distances_finite": all(
            ev[k] is not None and math.isfinite(ev[k])
            for k in ("min_arm_to_bus_mm", "min_moving_link_to_bus_mm",
                      "min_arm_to_wing_mm", "min_gripper_to_bus_mm")),
        "6_gripper_clear_of_bus": (ev["min_gripper_to_bus_mm"] is not None
                                   and ev["min_gripper_to_bus_mm"]
                                   >= CLEAR_MIN_MM),
        "7_joint_limits_valid_with_margin": (
            ev["joint_limits_valid"]
            and ev["nearest_joint_limit_margin_deg"] >= MARGIN_MIN_DEG),
        "8_independent_of_saddles_and_hdrm": ev["saddle_contact_count"] == 0,
        "9_moving_chain_clear_of_bus": (
            ev["min_moving_link_to_bus_mm"] is not None
            and ev["n_moving_bus_pairs"] > 0
            and ev["min_moving_link_to_bus_mm"] >= CLEAR_MIN_MM),
    }
    g["camera_required_view_available"] = "NOT_EVALUATED_NO_CAMERA"
    return g


def main():
    rep = {"schema": "F3R2_ARM_POSE_FREEZE_V1",
           "kinematics_authority": "accepted B601 URDF (read-only)",
           "geometry_authority": ("B51 CAD links from the hash-bound G2 STEPs "
                                  "(NOT the URDF STLs -- they differ; see "
                                  "F3R2_ARM_GEOMETRY_RECONCILIATION)"),
           "urdf_sha256": C.R.URDF_SHA,
           "mount_transform_mm": P.K.T_MOUNT.tolist(),
           "clock_deg": P.K.CLOCK_DEG,
           "clearance_target_mm": CLEAR_MIN_MM,
           "joint_margin_target_deg": MARGIN_MIN_DEG}
    rows = []
    try:
        rep["protected_pre"] = C.check_protected2("G3B_PRE")["verdict"]
        arms_dep = P.arm_parts("DEPLOYED")
        envs_dep = P.env_parts("DEPLOYED",
                               wings=("WING_L_DEPLOYED", "WING_R_DEPLOYED"))
        arms_stw = P.arm_parts("STOWED")
        envs_stw = P.env_parts("STOWED",
                               wings=("WING_L_STOWED", "WING_R_STOWED"))

        poses = {}

        # ---- Q_AS_BUILT_REFERENCE ----
        ev, rr = evaluate([0.0] * 6, arms_dep, envs_dep, "Q_AS_BUILT_REFERENCE")
        ev["source"] = ("the pose the CAD arm actually stands in inside "
                        "F3R1_V3_DEPLOYED_NOMINAL.step; URDF zero pose")
        ev["intended_control_use"] = ("geometric reference only -- the frame "
                                      "every other pose is measured from")
        ev["cad_configuration"] = "DEPLOYED_NOMINAL (arm default)"
        poses["Q_AS_BUILT_REFERENCE"] = ev
        rows.extend(rr)
        log.ev("POSE_EVALUATED", pose="Q_AS_BUILT_REFERENCE",
               bus=ev["min_arm_to_bus_mm"], wing=ev["min_arm_to_wing_mm"])

        # ---- Q_STOW_ENGINEERING_CANDIDATE (measured on the STOWED mesh set) --
        ev, rr = evaluate([0.0] * 6, arms_stw, envs_stw,
                          "Q_STOW_ENGINEERING_CANDIDATE")
        ev["q_deg"] = [round(v, 4) for v in Q_STOW]
        ev["q_rad"] = [round(math.radians(v), 6) for v in Q_STOW]
        ev["joint_limits"] = K.within_limits(Q_STOW)
        ev["joint_limits_valid"] = all(v["inside"]
                                       for v in ev["joint_limits"].values())
        ev["nearest_joint_limit_margin_deg"] = round(
            min(v["margin_deg"] for v in ev["joint_limits"].values()), 4)
        ev["source"] = ("F3R1_STOW_POSE_REPORT.json q_stow_deg; the STOWED "
                        "STEP already carries this pose, so it is measured at "
                        "zero relative motion")
        ev["status"] = "O13_V3_CANDIDATE_HOLD_PROVISIONAL"
        ev["intended_control_use"] = ("launch / transport restraint candidate; "
                                      "NOT a control start state")
        ev["cad_configuration"] = "STOWED_ENGINEERING_CANDIDATE"
        poses["Q_STOW_ENGINEERING_CANDIDATE"] = ev
        rows.extend(rr)
        log.ev("POSE_EVALUATED", pose="Q_STOW_ENGINEERING_CANDIDATE",
               bus=ev["min_arm_to_bus_mm"], saddle=ev["min_arm_to_saddle_mm"])

        rep["poses"] = poses
        rep["stage"] = "BASELINE_POSES_EVALUATED"
        rep["home_gate_as_built"] = home_gate(poses["Q_AS_BUILT_REFERENCE"])
        rep["as_built_would_pass_home_gate"] = all(
            v is True for k, v in rep["home_gate_as_built"].items()
            if isinstance(v, bool))
        rep["protected_post"] = C.check_protected2("G3B_POST")["verdict"]
        rep["verdict"] = "G3B_BASELINE_EVALUATED"
    except Exception as exc:
        rep["verdict"] = "G3B_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-2500:]

    C.write_json(OUTJ, rep)
    print("verdict:", rep["verdict"])
    for name, ev in (rep.get("poses") or {}).items():
        print("\n%s  q=%s" % (name, ev["q_deg"]))
        print("   bus %-9s wing %-9s saddle %-9s gripper->bus %-9s ref %s"
              % (ev["min_arm_to_bus_mm"], ev["min_arm_to_wing_mm"],
                 ev["min_arm_to_saddle_mm"], ev["min_gripper_to_bus_mm"],
                 ev["min_arm_to_reference_body_mm"]))
        print("   limits valid=%s margin=%s deg | bus pairs=%d wing pairs=%d"
              % (ev["joint_limits_valid"],
                 ev["nearest_joint_limit_margin_deg"],
                 ev["n_bus_pairs"], ev["n_wing_pairs"]))
        for w in ev["worst_pairs"][:4]:
            print("      %9.3f %-32s %-24s %s" % (w["gap_mm"], w["arm"][:32],
                                                  w["env"][:24], w["role"]))
    print("\nas-built would pass HOME gate:",
          rep.get("as_built_would_pass_home_gate"))
    print("home gate detail:", json.dumps(rep.get("home_gate_as_built"),
                                          ensure_ascii=False))
    if rep["verdict"] == "G3B_FAIL":
        print(rep.get("traceback"))
    sys.exit(0 if rep["verdict"] == "G3B_BASELINE_EVALUATED" else 1)


if __name__ == "__main__":
    main()
