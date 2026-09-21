# -*- coding: utf-8 -*-
"""G2-1 + G2-5: create the V3 candidate (never overwriting G1) and audit the
solar-wing instances.

Wing reality (measured, D-F3R1-06): the donor supplies FOUR separate panel
solids -- a STOWED and a DEPLOYED body per side -- each with SIX planar faces and
ZERO cylinders, i.e. no hinge bore. The panels sit at |y|=113.15 while the real
hinge pins (Hinge_Pin_L/R, r=4.000, axis +/-X) are at |y|=143.15: a ~30 mm gap.
So one rotatable panel per side cannot be built from existing geometry without
authoring a new part, which THIS stage does not authorise.

Chosen realisation (user-ratified): keep the four donor solids as the geometry
source, but guarantee that in EVERY configuration at most ONE panel per side is
live; all others are suppressed so they leave mass, collision and BOM. 0 deg uses
the STOWED body, 90 deg the DEPLOYED body, and intermediate angles rotate the
DEPLOYED body about the REAL hinge axis.

This script only: PRE-freeze, copy V2->V3, audit instances. It writes no mates.
"""
import csv
import json
import shutil
import sys
import traceback

from f3r1_env import F3R1, JLog, check_protected, sha256_file
import b3_lib.sw_core as swc
import sw_session as ss
import g2_env as G

log = JLog("g2a_v3_wing")
gm = G.gm
OUT = G.G2DIR / "F3R1_G2_WING_INSTANCE_AUDIT.csv"
REP = G.G2DIR / "F3R1_G2_A_V3_AND_WING_AUDIT.json"
NONMOD = G.G2DIR / "F3R1_G2_SOURCE_NON_MODIFICATION_REPORT.json"


def pre_freeze():
    """Snapshot every asset that must not change, before touching anything."""
    snap = {"g0_frozen": {"path": str(G.G0_FROZEN),
                          "sha256": sha256_file(G.G0_FROZEN)},
            "g1_v2_mated": {"path": str(G.V2_MATED),
                            "sha256": sha256_file(G.V2_MATED)}}
    snap["g0_prefix_ok"] = snap["g0_frozen"]["sha256"].startswith(G.G0_SHA_PREFIX)
    snap["g1_prefix_ok"] = snap["g1_v2_mated"]["sha256"].startswith(
        G.G1_POST_SHA_PREFIX)
    # donor / accepted assets come from the protected register
    snap["protected"] = check_protected("G2A_PRE")["assets"]
    return snap


def main():
    rep = {"schema": "F3R1_G2A_V3_AND_WING_AUDIT_V1"}
    rows = []
    try:
        rep["pre_freeze"] = pre_freeze()
        if not rep["pre_freeze"]["g0_prefix_ok"]:
            raise RuntimeError("G0 frozen assembly hash drifted")
        if not rep["pre_freeze"]["g1_prefix_ok"]:
            raise RuntimeError("G1 input assembly hash does not match report")

        # ---- create V3 without overwriting G1 ----
        if G.V3_CONF.exists():
            G.V3_CONF.unlink()
        shutil.copy2(G.V2_MATED, G.V3_CONF)
        rep["v3"] = {"path": str(G.V3_CONF), "sha256": sha256_file(G.V3_CONF)}
        rep["v3"]["identical_to_v2_at_creation"] = (
            rep["v3"]["sha256"] == rep["pre_freeze"]["g1_v2_mated"]["sha256"])
        log.ev("V3_CREATED", path=str(G.V3_CONF),
               identical=rep["v3"]["identical_to_v2_at_creation"])

        # ---- audit wing instances in the V3 candidate ----
        app, sess = G.fresh_session(log, "g2a_wing_audit")
        rep["session"] = sess
        blog = swc.BuildLog("g2a")
        wd = ss.MemoryDialogWatchdog(log)
        wd.start()
        try:
            top = swc.open_document(app, blog, str(G.V3_CONF))
            rep["configs_before"] = list(gm(top, "GetConfigurationNames") or [])
            kids = G.top_children(top)
            rep["top_children"] = sorted(kids.keys())

            for nm, k in sorted(kids.items()):
                if not nm.startswith("WING_"):
                    continue
                side = "L" if "_L_" in nm else ("R" if "_R_" in nm else "?")
                state = ("STOWED" if "STOWED" in nm else
                         "DEPLOYED" if "DEPLOYED" in nm else "?")
                box = gm(k, "GetBox", False, False)
                bb = [round(v * 1000.0, 3) for v in list(box)] if box else []
                mates_on = [m["name"] for m in G.mate_rows(top)]
                rows.append({
                    "component_name": nm,
                    "side": side,
                    "panel_state": state,
                    "source_file": str(gm(k, "GetPathName") or ""),
                    "sha256": sha256_file(str(gm(k, "GetPathName"))),
                    "is_fixed": bool(gm(k, "IsFixed")),
                    "is_suppressed": bool(gm(k, "IsSuppressed")),
                    "referenced_config": str(gm(k, "ReferencedConfiguration") or ""),
                    "bbox_mm": json.dumps(bb),
                    "transform16": json.dumps(G.t16_of(k)),
                    "n_cylindrical_faces": 0,
                    "hinge_bore_present": False,
                    "hinge_axis_y_mm": G.HINGE.get(side, {}).get("y_mm"),
                    # The panel edge NEAREST the hinge: for the left side that is
                    # bbox y-min, for the mirrored right side it is y-max. Using
                    # y-min for both gave a bogus -170 mm on the right.
                    "panel_inner_y_mm": (
                        (bb[1] if side == "L" else bb[4]) if bb else None),
                    "interface_gap_to_hinge_mm": (
                        round(abs(G.HINGE[side]["y_mm"])
                              - abs(bb[1] if side == "L" else bb[4]), 3)
                        if bb and side in G.HINGE else None),
                    "role": ("GEOMETRY_SOURCE_FOR_0DEG" if state == "STOWED"
                             else "GEOMETRY_SOURCE_FOR_90DEG_AND_ROTATION_BASE"),
                })
            rep["n_wing_instances"] = len(rows)
            rep["distinct_source_files"] = len(set(r["source_file"]
                                                   for r in rows))
            rep["identity_unique"] = (rep["distinct_source_files"] == len(rows))
            # per side count
            rep["per_side_instances"] = {
                "L": sum(1 for r in rows if r["side"] == "L"),
                "R": sum(1 for r in rows if r["side"] == "R")}
            swc.close_document(app, top, blog)
        finally:
            wd.stop()
        G.kill_sw(log)
        rep["session"]["processes_after_close"] = G.sw_process_count()

        rep["chosen_live_panels"] = {
            "note": ("Per configuration at most ONE panel per side stays live; "
                     "0 deg -> *_STOWED body, 90 deg -> *_DEPLOYED body, "
                     "intermediate -> *_DEPLOYED body rotated about the real "
                     "hinge axis. Non-live panels are component-suppressed so "
                     "they leave mass / collision / BOM."),
            "L": ["WING_L_STOWED-1", "WING_L_DEPLOYED-1"],
            "R": ["WING_R_STOWED-1", "WING_R_DEPLOYED-1"]}
        rep["verdict"] = "G2A_V3_CREATED_AND_WINGS_AUDITED"
    except Exception as exc:
        rep["verdict"] = "G2A_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-1800:]
        log.ev("G2A_FAIL", error=str(exc))

    # non-modification proof
    post = {"g0_frozen": sha256_file(G.G0_FROZEN) if G.G0_FROZEN.is_file() else None,
            "g1_v2_mated": sha256_file(G.V2_MATED) if G.V2_MATED.is_file() else None}
    pre = rep.get("pre_freeze", {})
    nm_rep = {"schema": "F3R1_G2_SOURCE_NON_MODIFICATION_V1",
              "g0_frozen": {"pre": pre.get("g0_frozen", {}).get("sha256"),
                            "post": post["g0_frozen"]},
              "g1_v2_mated": {"pre": pre.get("g1_v2_mated", {}).get("sha256"),
                              "post": post["g1_v2_mated"]},
              "protected_post": check_protected("G2A_POST")["assets"]}
    nm_rep["g0_unchanged"] = (nm_rep["g0_frozen"]["pre"] ==
                              nm_rep["g0_frozen"]["post"])
    nm_rep["g1_unchanged"] = (nm_rep["g1_v2_mated"]["pre"] ==
                              nm_rep["g1_v2_mated"]["post"])
    nm_rep["all_protected_unchanged"] = all(
        a.get("status") == "MATCH" for a in nm_rep["protected_post"].values())
    NONMOD.write_text(json.dumps(nm_rep, indent=2, ensure_ascii=False),
                      encoding="utf-8")

    if rows:
        with open(OUT, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            for r in rows:
                w.writerow(r)
    REP.write_text(json.dumps(rep, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print("verdict:", rep["verdict"])
    print("  V3:", rep.get("v3", {}).get("sha256", "")[:16],
          "identical_at_creation:", rep.get("v3", {}).get(
              "identical_to_v2_at_creation"))
    print("  wing instances:", rep.get("n_wing_instances"),
          "per side:", rep.get("per_side_instances"),
          "identity_unique:", rep.get("identity_unique"))
    for r in rows:
        print("    %-22s side=%s %-8s gap_to_hinge=%s mm  fixed=%s supp=%s"
              % (r["component_name"], r["side"], r["panel_state"],
                 r["interface_gap_to_hinge_mm"], r["is_fixed"],
                 r["is_suppressed"]))
    print("  G0 unchanged:", nm_rep["g0_unchanged"],
          "| G1 unchanged:", nm_rep["g1_unchanged"],
          "| protected:", nm_rep["all_protected_unchanged"])
    if rep["verdict"] == "G2A_FAIL":
        print(rep.get("traceback"))
    sys.exit(0 if rep["verdict"].startswith("G2A_V3") else 1)


if __name__ == "__main__":
    main()
