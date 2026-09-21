# -*- coding: utf-8 -*-
"""F3R2 G3-A: arm <-> spacecraft interference / clearance on the NEW baseline,
measured offline on the CAD geometry of the hash-bound G2 STEPs.

Why offline: SolidWorks on this machine both dies (fatal low-memory dialog ->
RPC failure) and hangs (Responding=False, CPU flat) during whole-assembly
interference detection -- reproduced four times, journalled.  The instrument
used here was proven first (G3A_INSTRUMENT_SELFCHECK.json: identity at the
as-built pose 5.7e-14, arm split lossless to 0.0009 mm, every environment part
classified).  It is a tessellation, so it is reported as AABB / MESH tiers and
never called a native B-rep verdict.

The prior "native interference = 0" belonged to an older candidate and older
configuration logic and is NOT used to dismiss anything here.

Each configuration is the same bus with a different live wing pair, which is
exactly how the eight G2 configurations differ, so the composition is honest.
"""
import json
import sys
import traceback

import numpy as np

import r2_common as C
import r2_pose as P

OUTJ = C.CLR2 / "G3A_NATIVE_INTERFERENCE_RESULTS.json"
OUTC = C.CLR2 / "G3A_INTERFERENCE_PAIR_REGISTER.csv"

# which wing panel is live in each configuration (G2 suppression matrix)
WINGS = {
    "STOWED_ENGINEERING_CANDIDATE": ("WING_L_STOWED", "WING_R_STOWED"),
    "SOLAR_DEPLOY_ARM_LOCKED": ("WING_L_DEPLOYED", "WING_R_DEPLOYED"),
    "DEPLOYED_NOMINAL": ("WING_L_DEPLOYED", "WING_R_DEPLOYED"),
    "L_FAIL": ("WING_L_STOWED", "WING_R_DEPLOYED"),
    "R_FAIL": ("WING_L_DEPLOYED", "WING_R_STOWED"),
    "DEPLOY_FAILED_BOTH": ("WING_L_STOWED", "WING_R_STOWED"),
    "PARTIAL": ("WING_L_DEPLOYED", "WING_R_DEPLOYED"),
    "SERVICE": ("WING_L_DEPLOYED", "WING_R_DEPLOYED"),
}
# Arm pose per configuration, from the G2 matrix column `arm_referenced_config`
# -- not guessed.  Six configurations reference the arm's STOWED_O13V3
# configuration; DEPLOYED_NOMINAL and SERVICE reference its default.
#
# Crucially, the two exported STEPs ALREADY carry those two arm poses:
# in F3R1_V3_STOWED_ENGINEERING_CANDIDATE.step the arm stands at q_stow
# (link3 has moved from x=324 to x=129, link6 to z=331).  So a configuration is
# measured on the STEP whose baked arm pose matches it, at zero relative motion,
# instead of re-posing meshes and stacking avoidable error.
Q_STOW = [145.572, -168.0, -57.0, -41.143, -20.954, -3.0]
ARM_REF = {
    "STOWED_ENGINEERING_CANDIDATE": "STOWED_O13V3",
    "SOLAR_DEPLOY_ARM_LOCKED": "STOWED_O13V3",
    "DEPLOYED_NOMINAL": "DEFAULT",
    "L_FAIL": "STOWED_O13V3",
    "R_FAIL": "STOWED_O13V3",
    "DEPLOY_FAILED_BOTH": "STOWED_O13V3",
    "PARTIAL": "STOWED_O13V3",
    "SERVICE": "DEFAULT",
}
# mesh set whose baked arm pose matches the configuration
ARM_TAG = {c: ("STOWED" if r == "STOWED_O13V3" else "DEPLOYED")
           for c, r in ARM_REF.items()}
POSE = {c: P.Q_AS_BUILT_DEG for c in ARM_REF}   # zero relative motion
Q_REPORTED = {c: (Q_STOW if r == "STOWED_O13V3" else [0.0] * 6)
              for c, r in ARM_REF.items()}
POSE_SOURCE = {
    c: ("arm baked at q_stow in F3R1_V3_STOWED_ENGINEERING_CANDIDATE.step; "
        "q from F3R1_STOW_POSE_REPORT.json (O13_V3_CANDIDATE_HOLD_PROVISIONAL);"
        " bound by G2 matrix arm_referenced_config=STOWED_O13V3"
        if r == "STOWED_O13V3"
        else "arm baked at its default configuration in "
             "F3R1_V3_DEPLOYED_NOMINAL.step (G2 matrix arm_referenced_config)")
    for c, r in ARM_REF.items()}


def main():
    rep = {"schema": "F3R2_G3A_INTERFERENCE_V2",
           "method": "OFFLINE_CAD_MESH_AABB_PLUS_SURFACE_DISTANCE",
           "authority_note": (
               "SolidWorks native B-rep interference is the authority and is "
               "NOT claimed here; see G3A_NATIVE_ATTEMPTS for the four "
               "reproduced SolidWorks failures on this machine."),
           "instrument_selfcheck": str(C.CLR2 /
                                       "G3A_INSTRUMENT_SELFCHECK.json"),
           "prior_result_note": (
               "the earlier 'native interference = 0' belonged to an older "
               "candidate and older configuration logic; it is not used to "
               "dismiss any finding here (user directive 2026-08-07)"),
           "arm_geometry": "B51 CAD links from the hash-bound G2 STEPs",
           "kinematics": "accepted B601 URDF (read-only, hash-guarded)"}
    rows = []
    try:
        rep["protected_pre"] = C.check_protected2("G3A_OFFLINE_PRE")["verdict"]
        man = P.load_manifest("DEPLOYED")
        rep["mesh_deflection_mm"] = man["linear_deflection_mm"]
        rep["arm_pose_binding"] = {c: {"arm_referenced_config": ARM_REF[c],
                                       "mesh_set": ARM_TAG[c],
                                       "q_deg": Q_REPORTED[c]}
                                   for c in C.CONFIGS}
        rep["tessellation_tolerance_note"] = (
            "a MESH gap within +/- the deflection of zero cannot distinguish "
            "touching from a thin interference; such pairs are reported "
            "TOO_CLOSE_TO_CALL rather than clean")
        percfg = {}
        for cname in C.CONFIGS:
            tag = ARM_TAG[cname]
            arms = P.arm_parts(tag)
            envs = P.env_parts(tag, wings=WINGS[cname])
            q = POSE[cname]
            got, _ = P.screen_pose(q, arms, envs)
            for r in got:
                r["configuration"] = cname
                r["q_deg"] = [round(v, 4) for v in Q_REPORTED[cname]]
                r["mesh_set"] = tag
                g = P.effective_gap(r)
                dfl = rep["mesh_deflection_mm"]
                if r["env_role"] == "REFERENCE_ONLY":
                    r["classification"] = "EXCLUDED_REFERENCE_ONLY_BODY"
                    r["counts_as_real"] = False
                elif r["env_role"] == "ARM_MOUNT_INTERFACE" and \
                        r["link"] == "base_link":
                    r["classification"] = "EXCLUDED_BOLTED_MOUNT_INTERFACE"
                    r["counts_as_real"] = False
                elif g < -dfl:
                    r["classification"] = "INTERFERENCE"
                    r["counts_as_real"] = True
                elif g <= dfl:
                    r["classification"] = "TOO_CLOSE_TO_CALL"
                    r["counts_as_real"] = True
                elif g < 5.0:
                    r["classification"] = "TIGHT_CLEARANCE"
                    r["counts_as_real"] = False
                else:
                    r["classification"] = "CLEAR"
                    r["counts_as_real"] = False
                r["effective_gap_mm"] = round(g, 4)
            rows.extend(got)
            real = [r for r in got if r["counts_as_real"]]
            tight = [r for r in got if r["classification"] == "TIGHT_CLEARANCE"]
            meshed = [r for r in got if r["tier"] == "MESH"]
            ranked = sorted(got, key=lambda r: r["effective_gap_mm"])
            percfg[cname] = {
                "status": "MEASURED_OFFLINE",
                "arm_referenced_config": ARM_REF[cname],
                "mesh_set": tag,
                "q_deg": [round(v, 4) for v in Q_REPORTED[cname]],
                "q_source": POSE_SOURCE[cname],
                "live_wings": list(WINGS[cname]),
                "pairs_screened": len(got),
                "pairs_mesh_evaluated": len(meshed),
                "interference_or_too_close": len(real),
                "tight_clearance_lt_5mm": len(tight),
                "min_gap_mm": ranked[0]["effective_gap_mm"] if ranked else None,
                "min_gap_pair": ("%s <-> %s" % (ranked[0]["arm_part"],
                                                ranked[0]["env_part"])
                                 if ranked else None),
                "worst_10": [{"arm": r["arm_part"], "env": r["env_part"],
                              "role": r["env_role"], "tier": r["tier"],
                              "gap_mm": r["effective_gap_mm"],
                              "class": r["classification"]}
                             for r in ranked[:10]]}
            C.Log("r2d_g3a").ev(
                "CONFIG_DONE", config=cname, pairs=len(got),
                meshed=len(meshed), real=len(real),
                min_gap=percfg[cname]["min_gap_mm"])
        rep["per_configuration"] = percfg
        rep["configs_measured"] = len(percfg)
        rep["all_eight_measured"] = len(percfg) == len(C.CONFIGS)
        rep["total_interference_or_too_close"] = sum(
            v["interference_or_too_close"] for v in percfg.values())
        rep["protected_post"] = C.check_protected2("G3A_OFFLINE_POST")["verdict"]
        rep["verdict"] = ("G3A_OFFLINE_MEASURED" if rep["all_eight_measured"]
                          else "G3A_OFFLINE_INCOMPLETE")
    except Exception as exc:
        rep["verdict"] = "G3A_OFFLINE_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-2500:]

    C.write_csv(OUTC, rows, fields=[
        "configuration", "mesh_set", "arm_part", "link", "env_part",
        "env_role", "tier", "aabb_gap_mm", "mesh_gap_mm", "effective_gap_mm",
        "classification", "counts_as_real", "q_deg"])
    C.write_json(OUTJ, rep)
    print("\nverdict:", rep["verdict"])
    for c, v in (rep.get("per_configuration") or {}).items():
        print("  %-30s pairs=%-4d mesh=%-3d real=%-3d tight=%-3d min=%s mm"
              % (c, v["pairs_screened"], v["pairs_mesh_evaluated"],
                 v["interference_or_too_close"], v["tight_clearance_lt_5mm"],
                 v["min_gap_mm"]))
        for w in v["worst_10"][:4]:
            print("        %9.3f  %-34s %-26s %-6s %s"
                  % (w["gap_mm"], w["arm"][:34], w["env"][:26], w["tier"],
                     w["class"]))
    print("  total interference/too-close:",
          rep.get("total_interference_or_too_close"))
    if rep["verdict"] == "G3A_OFFLINE_FAIL":
        print(rep.get("traceback"))
    sys.exit(0 if rep["verdict"] == "G3A_OFFLINE_MEASURED" else 1)


if __name__ == "__main__":
    main()
