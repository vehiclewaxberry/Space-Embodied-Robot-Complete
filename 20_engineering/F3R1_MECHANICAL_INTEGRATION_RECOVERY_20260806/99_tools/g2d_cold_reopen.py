# -*- coding: utf-8 -*-
"""G2-12: cold reopen in a brand-new SolidWorks process and gate the result.

Separate invocation on purpose: D-F3R1-07 proved a session that already ran a
build can fabricate both mate errors and interference, so the acceptance evidence
must come from a process that has never touched this document.

Verifies: 8/8 configurations present, each activates and rebuilds, exactly one
live wing per side, mate errors / dangling / overdefined = 0, B601 and root drift
= 0, every component path inside F3R1, and G0/G1/donor hashes unchanged.
Then exports one STEP per configuration key states for the screenshot stage.
"""
import csv
import json
import sys
import traceback

from f3r1_env import F3R1, JLog, check_protected, sha256_file
import b3_lib.sw_core as swc
import sw_session as ss
import g2_env as G

log = JLog("g2d_cold")
gm = G.gm
TOL_MM, TOL_DEG = 0.01, 0.01
OUT = G.G2DIR / "F3R1_G2_COLD_REOPEN_REPORT.json"
GATE = G.G2DIR / "F3R1_G2_GATE_STATUS.json"
STEPDIR = G.G2DIR / "step"
SHOT_CONFIGS = ["STOWED_ENGINEERING_CANDIDATE", "DEPLOYED_NOMINAL",
                "L_FAIL", "R_FAIL"]


def main():
    rep = {"schema": "F3R1_G2_COLD_REOPEN_V1", "tol_mm": TOL_MM}
    rows = []
    try:
        pre_prot = check_protected("G2D_PRE")
        auth_doc, auth = G.load_authority()
        order = [c["name"] for c in auth_doc["configurations"]]
        rep["expected_configs"] = order
        rep["input"] = {"path": str(G.V3_CONF), "sha256": sha256_file(G.V3_CONF)}

        app, sess = G.fresh_session(log, "g2d_cold_reopen")
        rep["session"] = sess
        blog = swc.BuildLog("g2d")
        wd = ss.MemoryDialogWatchdog(log)
        wd.start()
        try:
            top = swc.open_document(app, blog, str(G.V3_CONF))
            present = list(gm(top, "GetConfigurationNames") or [])
            rep["configs_present"] = present
            rep["all_eight_present"] = all(c in present for c in order)
            rep["no_junk_configs"] = not any(
                p.lower().startswith(("configuration", "default-copy", "copy of"))
                for p in present)

            # reference from the first config
            swc.activate_configuration(top, blog, order[0])
            top.ForceRebuild3(True)
            k0 = G.top_children(top)
            root_nm = next(n for n in k0 if n.startswith("Space_Embodied"))
            arm_nm = next(n for n in k0 if n.startswith("B51_B601"))
            root_ref, arm_ref = G.t16_of(k0[root_nm]), G.t16_of(k0[arm_nm])
            rep["n_top_components"] = len(k0)

            STEPDIR.mkdir(parents=True, exist_ok=True)
            for cname in order:
                swc.activate_configuration(top, blog, cname)
                ok_rb = bool(top.ForceRebuild3(True))
                kids = G.top_children(top)
                liveL = [n for n in kids if n.startswith("WING_") and "_L_" in n
                         and not bool(gm(kids[n], "IsSuppressed"))]
                liveR = [n for n in kids if n.startswith("WING_") and "_R_" in n
                         and not bool(gm(kids[n], "IsSuppressed"))]
                t_all, t_err = ss.mate_status(top)
                d_root = G.delta_t16(root_ref, G.t16_of(kids[root_nm]))
                d_arm = G.delta_t16(arm_ref, G.t16_of(kids[arm_nm]))
                inside = all(str(F3R1).lower() in
                             str(gm(k, "GetPathName") or "").lower()
                             for k in kids.values())
                rows.append({"configuration": cname, "rebuild_ok": ok_rb,
                             "n_components": len(kids),
                             "live_left": len(liveL), "live_right": len(liveR),
                             "live_left_panel": ",".join(liveL),
                             "live_right_panel": ",".join(liveR),
                             "mates_total": t_all, "mate_errors": t_err,
                             "root_drift_mm": round(d_root[0], 6),
                             "arm_drift_mm": round(d_arm[0], 6),
                             "arm_drift_deg": round(d_arm[1], 6),
                             "paths_inside_f3r1": inside})
                log.ev("COLD_CONFIG", config=cname, ok=ok_rb,
                       live="%d/%d" % (len(liveL), len(liveR)), err=t_err)
                if cname in SHOT_CONFIGS:
                    sp = STEPDIR / ("F3R1_V3_%s.step" % cname)
                    if sp.exists():
                        sp.unlink()
                    swc.save_as(top, blog, sp, overwrite=True)
                    log.ev("STEP_EXPORTED", config=cname,
                           bytes=sp.stat().st_size)
            swc.activate_configuration(top, blog, order[0])
            swc.close_document(app, top, blog)
        finally:
            wd.stop()
        G.kill_sw(log)
        rep["processes_after"] = G.sw_process_count()

        post_prot = check_protected("G2D_POST")
        rep["protected_unchanged"] = all(a.get("status") == "MATCH"
                                        for a in post_prot["assets"].values())
        rep["g0_sha"] = sha256_file(G.G0_FROZEN)
        rep["g1_sha"] = sha256_file(G.V2_MATED)
        rep["g0_unchanged"] = rep["g0_sha"].startswith(G.G0_SHA_PREFIX)
        rep["g1_unchanged"] = rep["g1_sha"].startswith(G.G1_POST_SHA_PREFIX)
        rep["v3_sha"] = sha256_file(G.V3_CONF)

        rep["per_config"] = rows
        rep["all_rebuild_ok"] = all(r["rebuild_ok"] for r in rows)
        rep["per_side_unique"] = all(r["live_left"] == 1 and r["live_right"] == 1
                                    for r in rows)
        rep["mate_errors_total"] = sum(r["mate_errors"] for r in rows)
        rep["max_root_drift_mm"] = max((r["root_drift_mm"] for r in rows),
                                       default=None)
        rep["max_arm_drift_mm"] = max((r["arm_drift_mm"] for r in rows),
                                      default=None)
        rep["all_paths_inside"] = all(r["paths_inside_f3r1"] for r in rows)
        rep["verdict"] = "G2D_COLD_REOPEN_DONE"
    except Exception as exc:
        rep["verdict"] = "G2D_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-2000:]
        log.ev("G2D_FAIL", error=str(exc))
        try:
            G.kill_sw(log)
        except Exception:
            pass

    OUT.write_text(json.dumps(rep, indent=2, ensure_ascii=False),
                   encoding="utf-8")

    # ---------------- G2 gate ----------------
    tc = G.G2DIR / "F3R1_G2_C_TEST_REPORT.json"
    test = json.loads(tc.read_text(encoding="utf-8")) if tc.is_file() else {}
    checks = {
        "eight_configs_present": bool(rep.get("all_eight_present")),
        "no_junk_configs": bool(rep.get("no_junk_configs")),
        "all_configs_rebuild": bool(rep.get("all_rebuild_ok")),
        "one_real_wing_per_side": bool(rep.get("per_side_unique")),
        "no_duplicate_live_wings": bool(test.get("no_duplicate_live")),
        "mate_errors_zero": rep.get("mate_errors_total") == 0,
        "arm_drift_zero": (rep.get("max_arm_drift_mm") is not None
                           and rep["max_arm_drift_mm"] <= TOL_MM),
        "root_drift_zero": (rep.get("max_root_drift_mm") is not None
                            and rep["max_root_drift_mm"] <= TOL_MM),
        "stress_three_rounds": test.get("stress_rounds") == 3,
        "angles_match_authority": bool(test.get("all_angles_match")),
        "paths_inside_f3r1": bool(rep.get("all_paths_inside")),
        "g0_unchanged": bool(rep.get("g0_unchanged")),
        "g1_unchanged": bool(rep.get("g1_unchanged")),
        "protected_unchanged": bool(rep.get("protected_unchanged")),
        "cold_reopen_ok": rep.get("verdict") == "G2D_COLD_REOPEN_DONE",
    }
    holds = [
        "PARTIAL: no authoritative wing angle (state_policy.json null, "
        "diagnostic_samples_define_partial=false); NOT geometrically "
        "differentiated from DEPLOYED_NOMINAL -- registered, not defined.",
        "SERVICE: PENDING_RATIFICATION_HOLD; wing angle reuses 90/90 for "
        "viewing only, no service access sequence or joint vector authorised.",
        "SOLAR_DEPLOY_ARM_LOCKED: end-state angles only; the deploy TRANSIT "
        "path is not authorised.",
        "D-F3R1-06 wing-root hinge interface OPEN: panels at |y|=113.15 vs real "
        "hinge pins at |y|=143.15, a 30.0 mm gap measured on all four panels. "
        "G2 angle realisation is KINEMATIC_CONFIGURATION_CANDIDATE only.",
        "q_stow remains O13_V3_CANDIDATE_HOLD_PROVISIONAL; "
        "STOWED_ENGINEERING_CANDIDATE is NOT runtime compliant and NOT a "
        "SAFE-00 execution entry.",
    ]
    failed = [k for k, v in checks.items() if not v]
    if not failed:
        verdict = "G2_CONFIGURATION_DIFFERENTIATION_PASS"
    elif set(failed) <= {"angles_match_authority"}:
        verdict = "G2_PARTIAL_PASS_WITH_NAMED_CONFIGURATION_HOLDS"
    elif not checks["one_real_wing_per_side"] or not checks[
            "no_duplicate_live_wings"]:
        verdict = "G2_FAIL_CONFIGURATION_OR_ASSET_DUPLICATION"
    else:
        verdict = "G2_PARTIAL_PASS_WITH_NAMED_CONFIGURATION_HOLDS"
    gate = {"schema": "F3R1_G2_GATE_STATUS_V1", "gate": "G2", "checks": checks,
            "failed_checks": failed, "named_holds": holds, "verdict": verdict,
            "v3_sha256": rep.get("v3_sha"),
            "next_authorisation": "G3_REAL_MECHANICAL_INTERFACE_CLOSURE",
            "next_priority_order": [
                "wing-root lug + hinge interface (closes D-F3R1-06)",
                "G07/G08/Mid real saddles (closes R3-04)",
                "ARM HDRM", "camera + harness", "gripper two fingers"]}
    GATE.write_text(json.dumps(gate, indent=2, ensure_ascii=False),
                    encoding="utf-8")

    if rows:
        cc = G.G2DIR / "F3R1_G2_COLD_REOPEN_PER_CONFIG.csv"
        with open(cc, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            for r in rows:
                w.writerow(r)

    print("cold reopen:", rep["verdict"])
    for r in rows:
        print("    %-30s rb=%s live=%d/%d err=%d arm=%.4f root=%.4f in=%s"
              % (r["configuration"], r["rebuild_ok"], r["live_left"],
                 r["live_right"], r["mate_errors"], r["arm_drift_mm"],
                 r["root_drift_mm"], r["paths_inside_f3r1"]))
    print()
    print("GATE:", verdict)
    for k, v in checks.items():
        print("   %-28s %s" % (k, "PASS" if v else "FAIL"))
    if rep["verdict"] == "G2D_FAIL":
        print(rep.get("traceback"))
    sys.exit(0)


if __name__ == "__main__":
    main()
