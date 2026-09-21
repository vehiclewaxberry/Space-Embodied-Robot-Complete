# -*- coding: utf-8 -*-
"""G2-4/6/7/8: build the eight named configurations in the V3 candidate.

Per configuration:
  * activate/create the configuration (donor flags False,False -- NEVER
    LinkToParent=True, which made a new config share the default's component
    positions and corrupted it in P4)
  * component suppression so AT MOST ONE panel per side is live
  * the live panel's transform: 0 deg uses the STOWED body as-built, 90 deg the
    DEPLOYED body as-built, intermediate angles rotate the DEPLOYED body about
    the REAL hinge axis (Hinge_Pin_L/R: X-parallel, y=+/-143.15, z=0)
  * the arm component's ReferencedConfiguration (STOWED_O13V3 or default)
  * configuration-specific custom properties recording runtime-compliance FALSE,
    the q_stow authority, and the angle authority/status

Angles come ONLY from F3R1_G2_CONFIG_ANGLE_AUTHORITY.json, which traces each
value to state_policy.json or marks it PROVISIONAL_HOLD. Nothing is guessed.

Fail-closed: the spacecraft root and the B601 arm must not drift at all
(<= 0.01 mm / 0.01 deg) across the whole build.
"""
import csv
import json
import sys
import traceback

import numpy as np

from f3r1_env import F3R1, JLog, check_protected, sha256_file
import b3_lib.sw_core as swc
import sw_session as ss
import g2_env as G

log = JLog("g2b_configs")
gm = G.gm
TOL_MM, TOL_DEG = 0.01, 0.01
REP = G.G2DIR / "F3R1_G2_B_BUILD_REPORT.json"
SUPP_CSV = G.G2DIR / "F3R1_G2_COMPONENT_SUPPRESSION_MATRIX.csv"


def live_panel_for(side, angle_deg, realised_deg=None):
    """Which donor body represents this side at this angle, and the extra
    rotation to apply to it.

    angle_deg None means NO AUTHORITATIVE ANGLE EXISTS (PARTIAL / SERVICE in
    state_policy.json). We must still keep exactly one live panel per side, so
    the configuration falls back to the REALISED angle recorded in the authority
    file -- and the authority file states plainly that such a configuration is
    not geometrically differentiated. We never invent an angle here.
    """
    if angle_deg is None:
        angle_deg = realised_deg
    if angle_deg is None:
        return None, 0.0
    if abs(angle_deg) < 1e-9:
        return G.PANELS[(side, 0.0)], 0.0
    if abs(angle_deg - 90.0) < 1e-9:
        return G.PANELS[(side, 90.0)], 0.0
    # intermediate: rotate the DEPLOYED body back from 90 deg to the target
    return G.PANELS[(side, 90.0)], (angle_deg - 90.0)


def set_props(model, cfgname, props, log):
    """Write configuration-specific custom properties (config scope)."""
    mgr = model.Extension.CustomPropertyManager(cfgname)
    n = 0
    for k, v in props.items():
        try:
            mgr.Add3(k, 30, str(v), 2)   # 30=text, 2=overwrite existing
            n += 1
        except Exception as e:
            log.ev("PROP_FAIL", config=cfgname, key=k, err=str(e)[:100])
    return n


def main():
    rep = {"schema": "F3R1_G2B_BUILD_V1", "tol_mm": TOL_MM, "tol_deg": TOL_DEG}
    supp_rows = []
    try:
        check_protected("G2B_PRE")
        auth_doc, auth = G.load_authority()
        rep["authority_policy_id"] = auth_doc["primary_authority"]["policy_id"]
        order = [c["name"] for c in auth_doc["configurations"]]
        rep["configuration_order"] = order

        app, sess = G.fresh_session(log, "g2b_build")
        rep["session"] = sess
        blog = swc.BuildLog("g2b")
        wd = ss.MemoryDialogWatchdog(log)
        wd.start()
        try:
            top = swc.open_document(app, blog, str(G.V3_CONF))
            kids = G.top_children(top)
            rep["existing_configs"] = list(gm(top, "GetConfigurationNames") or [])
            root_nm = next(n for n in kids if n.startswith("Space_Embodied"))
            arm_nm = next(n for n in kids if n.startswith("B51_B601"))
            rep["root_component"] = root_nm
            rep["arm_component"] = arm_nm

            # baseline transforms of root + arm + as-built panel poses
            base = {nm: G.t16_of(k) for nm, k in kids.items()}
            rep["baseline_captured"] = sorted(base.keys())

            cm = gm(top, "ConfigurationManager")
            built = []
            for cname in order:
                spec = auth[cname]
                existing = list(gm(top, "GetConfigurationNames") or [])
                if cname not in existing:
                    ok = cm.AddConfiguration2(
                        cname, spec.get("claim_limit", "")[:200], "", 0, "",
                        False, False)      # NO LinkToParent -- see P4 defect
                    log.ev("CONFIG_ADDED", name=cname, ok=(ok is not None))
                swc.activate_configuration(top, blog, cname)
                # component handles are per-configuration: re-fetch after every
                # switch or Transform2/SetSuppression2 act on stale objects
                kids = G.top_children(top)

                # ---- suppression: at most one live panel per side ----
                lp = {}
                for side, key, rkey in (("L", "solar_left_deg",
                                         "realised_left_deg"),
                                        ("R", "solar_right_deg",
                                         "realised_right_deg")):
                    ang = spec.get(key)
                    panel, extra = live_panel_for(side, ang, spec.get(rkey))
                    lp[side] = {"panel": panel, "angle_deg": ang,
                                "extra_rot_deg": extra}
                live = {v["panel"] for v in lp.values() if v["panel"]}
                for pnm in G.ALL_PANELS:
                    k = kids.get(pnm)
                    if k is None:
                        continue
                    want_live = pnm in live
                    k.SetSuppression2(G.SW_RESOLVED if want_live
                                      else G.SW_SUPPRESSED)
                swc.rebuild_or_fail(top, blog, "suppression %s" % cname)

                # ---- pose the live panels (rotate about the REAL hinge axis) --
                kids = G.top_children(top)     # post-rebuild handles
                posed = {}
                for side, v in lp.items():
                    pnm, extra = v["panel"], v["extra_rot_deg"]
                    if pnm is None:
                        continue
                    k = kids.get(pnm)
                    if k is None:
                        continue
                    want16 = base[pnm]
                    if abs(extra) > 1e-9:
                        Tb = G.t16_to_mat(base[pnm])
                        Rh = G.rot_about_x_through(
                            (G.HINGE[side]["y_mm"], G.HINGE[side]["z_mm"]),
                            extra)
                        want16 = G.mat_to_t16(Rh @ Tb)
                        k.SetTransformAndSolve3(G.make_transform(app, want16),
                                                True)
                    posed[pnm] = {"side": side, "angle_deg": v["angle_deg"],
                                  "extra_rot_deg": extra}
                swc.rebuild_or_fail(top, blog, "pose %s" % cname)

                # ---- arm referenced configuration ----
                kids = G.top_children(top)
                armk = kids[arm_nm]
                try:
                    armk.ReferencedConfiguration = spec["arm_config"]
                except Exception as e:
                    log.ev("ARM_CFG_FAIL", config=cname, err=str(e)[:110])
                swc.rebuild_or_fail(top, blog, "armcfg %s" % cname)

                # ---- configuration properties ----
                props = {
                    "GeometricDifferentiation": spec.get(
                        "geometric_differentiation", "DIFFERENTIATED"),
                    "RealisedLeftDeg": spec.get("realised_left_deg",
                                                spec.get("solar_left_deg")),
                    "RealisedRightDeg": spec.get("realised_right_deg",
                                                 spec.get("solar_right_deg")),
                    "ConfigurationName": cname,
                    "SSOT_Alias": spec.get("ssot_alias") or "NONE",
                    "SSOT_Status": spec.get("ssot_status", ""),
                    "SolarLeftDeg": spec.get("solar_left_deg"),
                    "SolarRightDeg": spec.get("solar_right_deg"),
                    "AngleSource": spec.get("angle_source", "")[:250],
                    "AngleStatus": spec.get("angle_status", ""),
                    "ArmConfiguration": spec.get("arm_config", ""),
                    "ArmStatus": spec.get("arm_status", ""),
                    "HDRMState": spec.get("hdrm_state", ""),
                    "RuntimeCompliance": str(bool(
                        spec.get("runtime_compliance", False))).upper(),
                    "Safe00ExecutionEntry": str(bool(
                        spec.get("safe00_execution_entry", False))).upper(),
                    "EngineeringEvaluationOnly": str(bool(
                        spec.get("engineering_evaluation_only", True))).upper(),
                    "QStowAuthority": "O13_V3_CANDIDATE_HOLD_PROVISIONAL",
                    "WingRootInterface": ("D_F3R1_06_OPEN_30MM_GAP_"
                                          "KINEMATIC_CONFIGURATION_CANDIDATE"),
                    "ClaimLimit": spec.get("claim_limit", "")[:250],
                }
                nprops = set_props(top, cname, props, log)

                # ---- drift guard on root + arm ----
                # Re-fetch component handles: the ones captured before the
                # configuration switch go stale and their Transform2 reads None,
                # which surfaced as a bogus inf drift.
                cur = G.top_children(top)
                d_root = G.delta_t16(base[root_nm], G.t16_of(cur[root_nm]))
                d_arm = G.delta_t16(base[arm_nm], G.t16_of(cur[arm_nm]))
                rec = {"config": cname, "live_panels": sorted(live),
                       "posed": posed, "n_props": nprops,
                       "root_drift_mm": round(d_root[0], 6),
                       "root_drift_deg": round(d_root[1], 6),
                       "arm_drift_mm": round(d_arm[0], 6),
                       "arm_drift_deg": round(d_arm[1], 6)}
                built.append(rec)
                log.ev("CONFIG_BUILT", **{k: rec[k] for k in
                                          ("config", "live_panels",
                                           "arm_drift_mm")})
                for pnm in G.ALL_PANELS:
                    k = kids.get(pnm)
                    supp_rows.append({
                        "configuration": cname, "component": pnm,
                        "suppressed": bool(gm(k, "IsSuppressed")) if k else "",
                        "live": pnm in live,
                        "side": "L" if "_L_" in pnm else "R",
                        "angle_deg": (lp["L"]["angle_deg"] if "_L_" in pnm
                                      else lp["R"]["angle_deg"]),
                    })
                if (d_root[0] > TOL_MM or d_root[1] > TOL_DEG
                        or d_arm[0] > TOL_MM or d_arm[1] > TOL_DEG):
                    raise RuntimeError(
                        "drift in %s: root %.4f/%.4f arm %.4f/%.4f"
                        % (cname, d_root[0], d_root[1], d_arm[0], d_arm[1]))

            rep["built"] = built
            rep["n_built"] = len(built)
            rep["configs_after"] = list(gm(top, "GetConfigurationNames") or [])
            # leave the engineering candidate active
            swc.activate_configuration(top, blog,
                                       "STOWED_ENGINEERING_CANDIDATE")
            swc.save(top, blog)
            swc.close_document(app, top, blog)
        finally:
            wd.stop()
        G.kill_sw(log)
        rep["v3_sha_after"] = sha256_file(G.V3_CONF)
        rep["verdict"] = "G2B_CONFIGS_BUILT"
    except Exception as exc:
        rep["verdict"] = "G2B_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-2000:]
        log.ev("G2B_FAIL", error=str(exc))
        try:
            G.kill_sw(log)
        except Exception:
            pass

    check_protected("G2B_POST")
    if supp_rows:
        with open(SUPP_CSV, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=list(supp_rows[0].keys()))
            w.writeheader()
            for r in supp_rows:
                w.writerow(r)
    REP.write_text(json.dumps(rep, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print("verdict:", rep["verdict"])
    print("  configs after:", rep.get("configs_after"))
    for b in rep.get("built") or []:
        print("    %-32s live=%s arm_drift=%.4f mm root_drift=%.4f mm props=%d"
              % (b["config"], ",".join(p.replace("WING_", "").replace("-1", "")
                                       for p in b["live_panels"]),
                 b["arm_drift_mm"], b["root_drift_mm"], b["n_props"]))
    if rep["verdict"] == "G2B_FAIL":
        print(rep.get("traceback"))
    sys.exit(0 if rep["verdict"] == "G2B_CONFIGS_BUILT" else 1)


if __name__ == "__main__":
    main()
