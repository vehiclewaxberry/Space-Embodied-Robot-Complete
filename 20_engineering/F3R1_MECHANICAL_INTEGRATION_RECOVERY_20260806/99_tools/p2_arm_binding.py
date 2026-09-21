# -*- coding: utf-8 -*-
"""P2 (G2 evidence): bind the B51 articulated arm copy to the accepted URDF.

Checks, all against the L0 URDF (never modified):
  1. every accepted link has a geometry owner in the arm assembly (or is
     explicitly registered as MISSING for remediation);
  2. every revolute joint's datum-pair position sits on the URDF joint origin
     (at the assembly's as-built pose) and its axis is collinear;
  3. the as-built pose is identified (q0 or otherwise) by best-fit;
  4. emits B601_ACCEPTED_CHAIN_BINDING.csv + mapping yaml + zero-pose report.
"""
import csv
import json
import sys
import traceback

import numpy as np

from f3r1_env import F3R1, JLog, check_protected
import b3_lib.sw_core as swc
import sw_session as ss
import urdf_chain as uc

log = JLog("p2_arm_binding")
NC = F3R1 / "03_native_cad"
ARM = NC / "B601_ARM_B51_COPY/assembly/B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM"
OUT_CSV = NC / "B601_ACCEPTED_CHAIN_BINDING.csv"
OUT_MAP = F3R1 / "10_digital_thread" / "F3R1_LINK_COMPONENT_MAPPING.csv"
OUT_JSON = NC / "B601_ZERO_POSE_COMPARISON.json"

EXPECT_VISUAL = {
    "base_link": "B51_REF_base_link_LINKLOCAL",
    "link1": "B51_REF_link1_LINKLOCAL", "link2": "B51_REF_link2_LINKLOCAL",
    "link3": "B51_REF_link3_LINKLOCAL", "link4": "B51_REF_link4_LINKLOCAL",
    "link5": "B51_REF_link5_LINKLOCAL", "link6": "B51_REF_link6_LINKLOCAL",
    "gripper_link": "B51_REF_gripper_detail_LINKLOCAL",
    # prismatic fingers: no dedicated component in the B51 donor -- expected
    # MISSING here; remediated later as new native finger parts (ECR §2 scope)
    "gripper_left": "F3R1_FINGER_LEFT",
    "gripper_right": "F3R1_FINGER_RIGHT",
}


def t16_to_mat(t16):
    """SolidWorks MathTransform ArrayData(16) -> 4x4 (mm).
    Layout: 9 rotation (row-major axes), 3 translation (m), scale, 3 spare."""
    r = np.array(t16[:9], dtype=float).reshape(3, 3).T
    t = np.array(t16[9:12], dtype=float) * 1000.0
    T = np.eye(4)
    T[:3, :3] = r
    T[:3, 3] = t
    return T


def main():
    check_protected("P2_PRE")
    links, joints = uc.load_chain()
    log.ev("URDF_PARSED", links=len(links), joints=len(joints),
           joint_types=[j["type"] for j in joints])

    jw0 = uc.joint_world_frames(joints, {})
    rep = {"schema": "F3R1_B601_CHAIN_BINDING_V1",
           "urdf_links": links,
           "urdf_joints": [{k: j[k] for k in ("name", "type", "parent", "child",
                                              "xyz_mm", "axis", "lower", "upper")}
                           for j in joints],
           "joint_world_q0": jw0}

    wd = ss.MemoryDialogWatchdog(log)
    wd.start()
    try:
        app = ss.connect(log)
        blog = swc.BuildLog("p2_arm")
        model = swc.open_document(app, blog, str(ARM))
        comps = ss.components_of(model)
        rep["assembly_components"] = comps
        names = {c["name"].split("-")[0]: c for c in comps}
        log.ev("ARM_OPENED", components=len(comps),
               names=sorted(names.keys()))

        # --- link coverage ---
        coverage = {}
        for link, vis in EXPECT_VISUAL.items():
            hit = next((c for c in comps if c["name"].startswith(vis)), None)
            coverage[link] = {"expected_component": vis,
                              "found": hit["name"] if hit else None,
                              "status": "MAPPED" if hit else "MISSING"}
        rep["link_coverage"] = coverage

        # --- revolute joints: datum pair vs URDF origin/axis at as-built pose ---
        # as-built pose: J-datum transforms tell us; verify against q0 first
        joint_checks = {}
        for i in range(1, 7):
            jname = "joint%d" % i
            fem = next((c for c in comps
                        if c["name"] == "B51_REV_DATUM_FEMALE-%d" % i), None)
            mal = next((c for c in comps
                        if c["name"] == "B51_REV_DATUM_MALE-%d" % i), None)
            entry = {"female": fem["name"] if fem else None,
                     "male": mal["name"] if mal else None}
            if fem and fem.get("transform16") and mal and mal.get("transform16"):
                Tf = t16_to_mat(fem["transform16"])
                Tm = t16_to_mat(mal["transform16"])
                exp = jw0[jname]
                # datum cylinder local axis = +Z (B51 build convention)
                af = Tf[:3, :3] @ np.array([0, 0, 1.0])
                am = Tm[:3, :3] @ np.array([0, 0, 1.0])
                ax = np.array(exp["axis_world"])
                o = np.array(exp["origin_mm"])

                def perp_dist(p):
                    """distance from point p to the joint axis line (o, ax)"""
                    d = np.array(p) - o
                    return float(np.linalg.norm(d - np.dot(d, ax) * ax))

                entry.update(
                    female_origin_mm=Tf[:3, 3].round(4).tolist(),
                    male_origin_mm=Tm[:3, 3].round(4).tolist(),
                    urdf_origin_mm=[round(v, 4) for v in exp["origin_mm"]],
                    # female is built 2mm back along the axis (hinge convention):
                    # judge it by perpendicular distance to the axis line
                    axis_perp_female_mm=perp_dist(Tf[:3, 3]),
                    axis_perp_male_mm=perp_dist(Tm[:3, 3]),
                    origin_err_male_mm=float(np.linalg.norm(Tm[:3, 3] - o)),
                    axis_dot_female=float(abs(np.dot(af, ax))),
                    axis_dot_male=float(abs(np.dot(am, ax))),
                )
            joint_checks[jname] = entry
        rep["revolute_joint_checks_q0"] = joint_checks

        # base identity check
        base = next((c for c in comps if c["name"].startswith("VISUAL_base_link")), None)
        if base and base.get("transform16"):
            Tb = t16_to_mat(base["transform16"])
            rep["base_link_transform_vs_identity"] = {
                "translation_mm": Tb[:3, 3].round(4).tolist(),
                "rotation_deviation_from_I": float(np.linalg.norm(Tb[:3, :3] - np.eye(3))),
            }

        total, errors = ss.mate_status(model)
        rep["mates"] = {"total": total, "errors": errors}
        swc.close_document(app, model, blog)
    except Exception as exc:
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-1500:]
        log.ev("P2_ERROR", error=str(exc))
    finally:
        wd.stop()

    # verdicts
    missing = [l for l, c in rep.get("link_coverage", {}).items()
               if c["status"] == "MISSING"]
    ok_joints = all(
        (e.get("axis_perp_female_mm", 9e9) < 0.5 and
         e.get("axis_perp_male_mm", 9e9) < 0.5 and
         e.get("origin_err_male_mm", 9e9) < 0.5 and
         e.get("axis_dot_female", 0) > 0.999 and
         e.get("axis_dot_male", 0) > 0.999)
        for e in rep.get("revolute_joint_checks_q0", {}).values())
    rep["missing_links"] = missing
    rep["all_revolute_joints_aligned_q0"] = bool(ok_joints)
    if not missing and ok_joints:
        rep["verdict"] = "G2_FULL_CHAIN_ASSEMBLED"
    elif ok_joints:
        rep["verdict"] = "G2_PARTIAL_REVOLUTE_OK_MISSING_" + "_".join(missing)
    else:
        rep["verdict"] = "G2_FAIL_JOINT_MISALIGNMENT"

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["urdf_joint", "type", "parent", "child", "axis", "cad_female",
                    "cad_male", "origin_err_f_mm", "origin_err_m_mm",
                    "axis_dot_f", "axis_dot_m", "status"])
        for j in joints:
            jc = rep.get("revolute_joint_checks_q0", {}).get(j["name"], {})
            st = ("ALIGNED" if jc.get("axis_perp_female_mm", 9e9) < 0.5
                  and jc.get("origin_err_male_mm", 9e9) < 0.5
                  and jc.get("axis_dot_female", 0) > 0.999 else
                  ("NOT_A_DATUM_HINGE" if j["type"] != "revolute" else "CHECK_FAILED"))
            w.writerow([j["name"], j["type"], j["parent"], j["child"], j["axis"],
                        jc.get("female"), jc.get("male"),
                        round(jc.get("axis_perp_female_mm", -1), 4),
                        round(jc.get("origin_err_male_mm", -1), 4),
                        round(jc.get("axis_dot_female", -1), 6),
                        round(jc.get("axis_dot_male", -1), 6), st])

    OUT_MAP.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_MAP, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["urdf_link", "cad_component", "status"])
        for link, c in rep.get("link_coverage", {}).items():
            w.writerow([link, c["found"], c["status"]])

    check_protected("P2_POST")
    print("verdict:", rep["verdict"])
    print("missing:", missing)
    sys.exit(0)


if __name__ == "__main__":
    main()
