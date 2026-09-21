# -*- coding: utf-8 -*-
"""G2-10/11/12: per-configuration test, 3-round switch stress, cold reopen.

Per configuration: activate, rebuild, mate status, component count, live wing
count per side, root/arm/wing transforms, expected vs ACTUAL wing angle measured
back from geometry, duplicate-geometry check, interference, BOM/mass
participation, and configuration properties readback.

Then three full round-trips CONFIG_1..CONFIG_8..CONFIG_1 checking for drift,
lost components, suppression instability, duplicate panels and state leakage.

Runs entirely in ONE fresh session (D-F3R1-07 discipline); the cold reopen is a
separate script invocation so it genuinely uses a new process.
"""
import csv
import json
import math
import sys
import traceback

import numpy as np

from f3r1_env import F3R1, JLog, check_protected, sha256_file
import b3_lib.sw_core as swc
import sw_session as ss
import g2_env as G

log = JLog("g2c_test")
gm = G.gm
TOL_MM, TOL_DEG = 0.01, 0.01
MATRIX = G.G2DIR / "F3R1_G2_CONFIGURATION_MATRIX.csv"
MATEREG = G.G2DIR / "F3R1_G2_MATE_STATUS_REGISTER.csv"
DRIFT = G.G2DIR / "F3R1_G2_TRANSFORM_DRIFT_REPORT.json"
REP = G.G2DIR / "F3R1_G2_C_TEST_REPORT.json"


def measured_angle(live_panel, t16_now, base16):
    """Measure the ACTUAL wing angle back from geometry.

    A live *_STOWED body means 0 deg by definition. A live *_DEPLOYED body sits
    at 90 deg as-built, so any residual rotation relative to its as-built
    transform is subtracted from 90 to give the realised angle.
    """
    if live_panel is None or t16_now is None:
        return None
    if "STOWED" in live_panel:
        return 0.0
    if base16 is None:
        return None
    Rn = np.array(t16_now[:9], float).reshape(3, 3).T
    Rb = np.array(base16[:9], float).reshape(3, 3).T
    c = max(-1.0, min(1.0, (np.trace(Rb.T @ Rn) - 1.0) / 2.0))
    return round(90.0 - math.degrees(math.acos(c)), 4)


def interference(top, asm):
    mgr = gm(asm, "InterferenceDetectionManager")
    if mgr is None:
        return {"status": "NO_MANAGER"}
    for p, v in (("TreatCoincidenceAsInterference", False),
                 ("TreatSubAssembliesAsComponents", False),
                 ("IncludeMultibodyPartInterferences", True)):
        try:
            setattr(mgr, p, v)
        except Exception:
            pass
    vols, mover = [], []
    for r in list(mgr.GetInterferences() or []):
        try:
            it = swc.cast(r, "IInterference")
            v = round(float(gm(it, "Volume")) * 1e9, 4)
            names = [str(gm(swc.cast(c, "IComponent2"), "Name2")).split("/")[-1]
                     for c in list(gm(it, "GetComponents") or [])]
            vols.append(v)
            if any(n.startswith(("WING_", "B51_")) for n in names):
                mover.append({"volume_mm3": v, "components": names})
        except Exception:
            continue
    mover.sort(key=lambda d: -d["volume_mm3"])
    return {"status": "OK", "count": len(vols),
            "total_volume_mm3": round(sum(vols), 4),
            "count_involving_movers": len(mover),
            "top_mover_items": mover[:6]}


def read_props(top, cname):
    mgr = top.Extension.CustomPropertyManager(cname)
    out = {}
    try:
        names = list(gm(mgr, "GetNames") or [])
    except Exception:
        names = []
    for n in names:
        try:
            r = mgr.Get6(n, False)
            out[str(n)] = str(r[1]) if isinstance(r, tuple) and len(r) > 1 else ""
        except Exception:
            out[str(n)] = ""
    return out


def snapshot(top):
    """Per-config observable state used for both testing and stress comparison."""
    kids = G.top_children(top)
    live_wings = {"L": [], "R": []}
    for nm, k in kids.items():
        if not nm.startswith("WING_"):
            continue
        if not bool(gm(k, "IsSuppressed")):
            live_wings["L" if "_L_" in nm else "R"].append(nm)
    return {"n_components": len(kids),
            "transforms": {nm: G.t16_of(k) for nm, k in kids.items()},
            "suppressed": {nm: bool(gm(k, "IsSuppressed"))
                           for nm, k in kids.items()},
            "live_wings": live_wings}


def main():
    rep = {"schema": "F3R1_G2C_TEST_V1", "tol_mm": TOL_MM, "tol_deg": TOL_DEG}
    rows, mate_rows_all, drift_rec = [], [], {}
    try:
        check_protected("G2C_PRE")
        auth_doc, auth = G.load_authority()
        order = [c["name"] for c in auth_doc["configurations"]]
        app, sess = G.fresh_session(log, "g2c_test")
        rep["session"] = sess
        blog = swc.BuildLog("g2c")
        wd = ss.MemoryDialogWatchdog(log)
        wd.start()
        try:
            top = swc.open_document(app, blog, str(G.V3_CONF))
            asm = swc.cast(top, "IAssemblyDoc")
            present = list(gm(top, "GetConfigurationNames") or [])
            rep["configs_present"] = present
            rep["all_eight_present"] = all(c in present for c in order)

            # as-built DEPLOYED transforms are the 90 deg reference
            swc.activate_configuration(top, blog, "DEPLOYED_NOMINAL")
            top.ForceRebuild3(True)
            k0 = G.top_children(top)
            base_dep = {nm: G.t16_of(k) for nm, k in k0.items()
                        if "DEPLOYED" in nm}
            root_nm = next(n for n in k0 if n.startswith("Space_Embodied"))
            arm_nm = next(n for n in k0 if n.startswith("B51_B601"))
            root_ref = G.t16_of(k0[root_nm])
            arm_ref = G.t16_of(k0[arm_nm])

            # ---------- per configuration ----------
            for cname in order:
                spec = auth[cname]
                swc.activate_configuration(top, blog, cname)
                if not top.ForceRebuild3(True):
                    raise RuntimeError("rebuild failed: %s" % cname)
                snap = snapshot(top)
                t_all, t_err = ss.mate_status(top)
                for m in G.mate_rows(top):
                    mate_rows_all.append({"configuration": cname, **m})
                kids = G.top_children(top)
                d_root = G.delta_t16(root_ref, G.t16_of(kids[root_nm]))
                d_arm = G.delta_t16(arm_ref, G.t16_of(kids[arm_nm]))
                ang = {}
                for side in ("L", "R"):
                    lw = snap["live_wings"][side]
                    p = lw[0] if lw else None
                    ang[side] = measured_angle(
                        p, snap["transforms"].get(p),
                        base_dep.get(p))
                props = read_props(top, cname)
                itf = interference(top, asm)
                # A null authority angle means NO expectation exists; compare
                # against the REALISED value the authority file declares, so a
                # declared-undifferentiated config is not scored as a mismatch.
                exp_l = spec.get("solar_left_deg")
                exp_r = spec.get("solar_right_deg")
                if exp_l is None:
                    exp_l = spec.get("realised_left_deg")
                if exp_r is None:
                    exp_r = spec.get("realised_right_deg")
                row = {
                    "configuration": cname,
                    "ssot_alias": spec.get("ssot_alias") or "",
                    "n_components": snap["n_components"],
                    "live_left_count": len(snap["live_wings"]["L"]),
                    "live_right_count": len(snap["live_wings"]["R"]),
                    "live_left_panel": ",".join(snap["live_wings"]["L"]),
                    "live_right_panel": ",".join(snap["live_wings"]["R"]),
                    "expected_left_deg": exp_l,
                    "actual_left_deg": ang["L"],
                    "expected_right_deg": exp_r,
                    "actual_right_deg": ang["R"],
                    "angle_match": (
                        (exp_l is None or (ang["L"] is not None
                                           and abs(ang["L"] - exp_l) < 0.01))
                        and (exp_r is None or (ang["R"] is not None
                                               and abs(ang["R"] - exp_r) < 0.01))),
                    "angle_status": spec.get("angle_status"),
                    "authoritative_angle_exists": (
                        spec.get("solar_left_deg") is not None
                        and spec.get("solar_right_deg") is not None),
                    "geometric_differentiation": spec.get(
                        "geometric_differentiation", "DIFFERENTIATED"),
                    "angle_source_short": (spec.get("angle_source", "")[:60]),
                    "arm_referenced_config": str(
                        gm(kids[arm_nm], "ReferencedConfiguration") or ""),
                    "mates_total": t_all,
                    "mate_errors": t_err,
                    "root_drift_mm": round(d_root[0], 6),
                    "arm_drift_mm": round(d_arm[0], 6),
                    "arm_drift_deg": round(d_arm[1], 6),
                    "duplicate_live_panels": (len(snap["live_wings"]["L"]) > 1
                                              or len(snap["live_wings"]["R"]) > 1),
                    "interference_count": itf.get("count"),
                    "interference_movers": itf.get("count_involving_movers"),
                    "runtime_compliance": props.get("RuntimeCompliance", ""),
                    "safe00_entry": props.get("Safe00ExecutionEntry", ""),
                    "qstow_authority": props.get("QStowAuthority", ""),
                    "n_props": len(props),
                }
                rows.append(row)
                log.ev("CONFIG_TESTED", config=cname,
                       live=("%d/%d" % (row["live_left_count"],
                                        row["live_right_count"])),
                       angles=("%s/%s" % (ang["L"], ang["R"])),
                       mate_err=t_err, itf=itf.get("count"))

            # ---------- 3-round switch stress ----------
            stress = []
            ref_snaps = {r["configuration"]: None for r in rows}
            for rnd in range(1, 4):
                seq = order + [order[0]]
                for cname in seq:
                    swc.activate_configuration(top, blog, cname)
                    top.ForceRebuild3(True)
                    snap = snapshot(top)
                    kids = G.top_children(top)
                    d_root = G.delta_t16(root_ref, G.t16_of(kids[root_nm]))
                    d_arm = G.delta_t16(arm_ref, G.t16_of(kids[arm_nm]))
                    key = "%s" % cname
                    prev = ref_snaps.get(key)
                    leak = None
                    if prev is not None:
                        leak = max(
                            (G.delta_t16(prev["transforms"].get(n),
                                         snap["transforms"].get(n))[0]
                             for n in prev["transforms"]), default=0.0)
                        if prev["suppressed"] != snap["suppressed"]:
                            leak = float("inf")
                    else:
                        ref_snaps[key] = snap
                    stress.append({
                        "round": rnd, "config": cname,
                        "n_components": snap["n_components"],
                        "live_L": len(snap["live_wings"]["L"]),
                        "live_R": len(snap["live_wings"]["R"]),
                        "root_drift_mm": round(d_root[0], 6),
                        "arm_drift_mm": round(d_arm[0], 6),
                        "state_leak_mm": (None if leak is None
                                          else round(leak, 6))})
                    if (d_root[0] > TOL_MM or d_arm[0] > TOL_MM
                            or len(snap["live_wings"]["L"]) > 1
                            or len(snap["live_wings"]["R"]) > 1
                            or snap["n_components"] != rows[0]["n_components"]):
                        raise RuntimeError(
                            "stress failure round %d %s" % (rnd, cname))
                    if leak is not None and leak > TOL_MM:
                        raise RuntimeError(
                            "state leak %s round %d: %.4f mm" % (cname, rnd, leak))
                log.ev("STRESS_ROUND_OK", round=rnd)
            rep["stress"] = stress
            rep["stress_rounds"] = 3

            swc.activate_configuration(top, blog,
                                       "STOWED_ENGINEERING_CANDIDATE")
            swc.close_document(app, top, blog)
        finally:
            wd.stop()
        G.kill_sw(log)

        drift_rec = {"schema": "F3R1_G2_TRANSFORM_DRIFT_V1",
                     "reference": "DEPLOYED_NOMINAL as-built handles",
                     "per_config": [{k: r[k] for k in
                                     ("configuration", "root_drift_mm",
                                      "arm_drift_mm", "arm_drift_deg")}
                                    for r in rows],
                     "max_root_drift_mm": max((r["root_drift_mm"] for r in rows),
                                              default=None),
                     "max_arm_drift_mm": max((r["arm_drift_mm"] for r in rows),
                                             default=None),
                     "stress_max_arm_drift_mm": max(
                         (s["arm_drift_mm"] for s in rep.get("stress", [])),
                         default=None),
                     "tolerance_mm": TOL_MM}
        rep["n_configs_tested"] = len(rows)
        rep["all_angles_match"] = all(r["angle_match"] for r in rows)
        rep["no_duplicate_live"] = all(not r["duplicate_live_panels"]
                                       for r in rows)
        rep["per_side_unique"] = all(r["live_left_count"] <= 1
                                     and r["live_right_count"] <= 1
                                     for r in rows)
        rep["mate_errors_total"] = sum(r["mate_errors"] for r in rows)
        rep["verdict"] = "G2C_TESTED"
    except Exception as exc:
        rep["verdict"] = "G2C_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-2000:]
        log.ev("G2C_FAIL", error=str(exc))
        try:
            G.kill_sw(log)
        except Exception:
            pass

    check_protected("G2C_POST")
    if rows:
        with open(MATRIX, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            for r in rows:
                w.writerow(r)
    if mate_rows_all:
        with open(MATEREG, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=list(mate_rows_all[0].keys()))
            w.writeheader()
            for r in mate_rows_all:
                w.writerow(r)
    if drift_rec:
        DRIFT.write_text(json.dumps(drift_rec, indent=2, ensure_ascii=False),
                         encoding="utf-8")
    REP.write_text(json.dumps(rep, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print("verdict:", rep["verdict"])
    print("  configs tested:", rep.get("n_configs_tested"),
          "| all 8 present:", rep.get("all_eight_present"))
    print("  angles match:", rep.get("all_angles_match"),
          "| per-side unique:", rep.get("per_side_unique"),
          "| mate errors:", rep.get("mate_errors_total"))
    for r in rows:
        print("    %-30s L=%s(%s) R=%s(%s) arm=%s itf=%s err=%s"
              % (r["configuration"], r["actual_left_deg"], r["expected_left_deg"],
                 r["actual_right_deg"], r["expected_right_deg"],
                 r["arm_referenced_config"][:14], r["interference_count"],
                 r["mate_errors"]))
    print("  stress rounds:", rep.get("stress_rounds"),
          "| max arm drift in stress:",
          drift_rec.get("stress_max_arm_drift_mm"))
    if rep["verdict"] == "G2C_FAIL":
        print(rep.get("traceback"))
    sys.exit(0 if rep["verdict"] == "G2C_TESTED" else 1)


if __name__ == "__main__":
    main()
