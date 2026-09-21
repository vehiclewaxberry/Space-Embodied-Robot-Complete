# -*- coding: utf-8 -*-
"""F3R2 G3-A: locate arm<->bus interference across ALL EIGHT configurations of
the NEW baseline. Declared first priority.

The earlier "native interference = 0" result belonged to an older candidate and
older configuration logic; it is NOT used to dismiss anything here. Every
configuration of F3R2_..._OPERATIONAL_BASELINE is measured fresh, in a clean
SolidWorks session (D-F3R1-07).

Per interference pair we record configuration, both components, volume, the
component classes involved, and -- when it is excluded -- the explicit reason.
Excluded (but registered) classes: suppressed components, reference/envelope-only
bodies, duplicate donor representations, intentional coincident mate references,
and bodies belonging to a non-live configuration.
"""
import csv
import json
import sys
import traceback

from f3r1_env import JLog, check_protected, sha256_file
import b3_lib.sw_core as swc
import sw_session as ss
import r2_env as R

log = JLog("r2b_g3a")
gm = R.gm
OUTJ = R.CLR2 / "G3A_NATIVE_INTERFERENCE_RESULTS.json"
OUTC = R.CLR2 / "G3A_INTERFERENCE_PAIR_REGISTER.csv"

ARM_TOKENS = ("B51_REF_", "B51_REV_", "B51_B601")
BUS_GROUPS = {
    "primary_structure": ("01_Primary_Structure", "Deck_", "Removable_Panels",
                          "Longeron", "Frame", "Bay"),
    "adapter_plate": ("Adapter_Plate",),
    "central_boss": ("Central_Boss",),
    "spacecraft_flange": ("Spacecraft_Flange",),
    "load_path": ("Load_Bridge", "Load_Spreading_Frame", "Harness_Passage",
                  "Maintenance_Access_Cover"),
    "solar_root": ("05_Solar_Array_Root", "06_Solar_Array_Root", "Root_Base",
                   "Root_Node_Spine", "Hinge_", "Torsion_Spring", "Hard_Stop",
                   "HDRM_"),
    "solar_wing": ("WING_",),
    "saddles": ("Aft_Saddle", "Fwd_Saddle", "Mid_Saddle"),
    "arm_stow_support": ("04_ARM_STOW_SUPPORT", "Launch_Lock_Interface",
                         "Release_Clearance_Envelope"),
}


def classify(leaf):
    if any(t in leaf for t in ARM_TOKENS):
        return "arm"
    for g, toks in BUS_GROUPS.items():
        if any(t in leaf for t in toks):
            return g
    return "other"


def main():
    rep = {"schema": "F3R2_G3A_INTERFERENCE_V1",
           "baseline": str(R.BASELINE),
           "note": ("Fresh measurement on the NEW F3R2 baseline. Prior "
                    "'interference 0' results belonged to an older candidate "
                    "and older configuration logic and are NOT used to dismiss "
                    "these findings.")}
    rows = []
    try:
        rep["protected_pre"] = check_protected("R2B_PRE")["verdict"]
        rep["baseline_sha_pre"] = sha256_file(R.BASELINE)
        app, sess = R.fresh(log, "r2b_g3a")
        rep["session"] = sess
        blog = swc.BuildLog("r2b")
        wd = ss.MemoryDialogWatchdog(log)
        wd.start()
        percfg = {}
        try:
            top = swc.open_document(app, blog, str(R.BASELINE))
            asm = swc.cast(top, "IAssemblyDoc")
            present = list(gm(top, "GetConfigurationNames") or [])
            rep["configs_present"] = present
            for cname in R.CONFIGS:
                if cname not in present:
                    percfg[cname] = {"status": "CONFIG_ABSENT"}
                    continue
                swc.activate_configuration(top, blog, cname)
                if not top.ForceRebuild3(True):
                    raise RuntimeError("rebuild failed: %s" % cname)
                # suppressed set for exclusion reasoning
                supp = {full.split("/")[-1] for leaf, full, k
                        in R.walk_all(top) if bool(gm(k, "IsSuppressed"))}
                itf = R.interference_full(top, asm, log)
                real_pairs = []
                for it in itf.get("items", []):
                    leaves = it["leaves"]
                    classes = sorted({classify(l) for l in leaves})
                    excl = it.get("excluded_reason")
                    if excl is None and any(l in supp for l in leaves):
                        excl = "SUPPRESSED_COMPONENT"
                    if excl is None and len(leaves) >= 2 and \
                            leaves[0] == leaves[1]:
                        excl = "SAME_COMPONENT_SELF_PAIR"
                    involves_arm = "arm" in classes
                    rec = {"configuration": cname,
                           "component_a": leaves[0] if leaves else "",
                           "component_b": leaves[1] if len(leaves) > 1 else "",
                           "full_a": it["components"][0] if it["components"] else "",
                           "full_b": (it["components"][1]
                                      if len(it["components"]) > 1 else ""),
                           "volume_mm3": it["volume_mm3"],
                           "classes": ",".join(classes),
                           "involves_arm": involves_arm,
                           "excluded_reason": excl or "",
                           "counts_as_real": (excl is None)}
                    rows.append(rec)
                    if excl is None:
                        real_pairs.append(rec)
                arm_pairs = [p for p in real_pairs if p["involves_arm"]]
                percfg[cname] = {
                    "status": "MEASURED",
                    "count_raw": itf.get("count_raw"),
                    "count_real": len(real_pairs),
                    "count_real_arm": len(arm_pairs),
                    "real_volume_mm3": round(
                        sum(p["volume_mm3"] for p in real_pairs), 5),
                    "arm_volume_mm3": round(
                        sum(p["volume_mm3"] for p in arm_pairs), 5),
                    "top_arm_pairs": arm_pairs[:8]}
                log.ev("G3A_CONFIG", config=cname,
                       raw=itf.get("count_raw"), real=len(real_pairs),
                       arm=len(arm_pairs))
            swc.activate_configuration(top, blog, "DEPLOYED_NOMINAL")
            swc.close_document(app, top, blog)
        finally:
            wd.stop()
        R.kill_sw(log)
        rep["per_configuration"] = percfg
        rep["baseline_sha_post"] = sha256_file(R.BASELINE)
        rep["baseline_unchanged"] = (rep["baseline_sha_post"] ==
                                     rep["baseline_sha_pre"])
        rep["protected_post"] = check_protected("R2B_POST")["verdict"]
        tot_arm = sum(v.get("count_real_arm", 0) for v in percfg.values()
                      if isinstance(v, dict))
        rep["total_real_arm_pairs"] = tot_arm
        rep["deployed_nominal_arm_pairs"] = percfg.get(
            "DEPLOYED_NOMINAL", {}).get("count_real_arm")
        rep["verdict"] = "G3A_MEASURED"
    except Exception as exc:
        rep["verdict"] = "G3A_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-2000:]
        log.ev("G3A_FAIL", error=str(exc))
        try:
            R.kill_sw(log)
        except Exception:
            pass

    if rows:
        with open(OUTC, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            for r in rows:
                w.writerow(r)
    OUTJ.write_text(json.dumps(rep, indent=2, ensure_ascii=False),
                    encoding="utf-8")
    print("verdict:", rep["verdict"])
    for c, v in (rep.get("per_configuration") or {}).items():
        if v.get("status") != "MEASURED":
            print("  %-30s %s" % (c, v.get("status")))
            continue
        print("  %-30s raw=%-4s real=%-4s arm=%-3s arm_vol=%s mm3"
              % (c, v["count_raw"], v["count_real"], v["count_real_arm"],
                 v["arm_volume_mm3"]))
        for p in v.get("top_arm_pairs", [])[:4]:
            print("        %8.3f mm3  %s <-> %s  [%s]"
                  % (p["volume_mm3"], p["component_a"][:26],
                     p["component_b"][:26], p["classes"]))
    print("  total real arm pairs:", rep.get("total_real_arm_pairs"))
    print("  baseline unchanged:", rep.get("baseline_unchanged"))
    if rep["verdict"] == "G3A_FAIL":
        print(rep.get("traceback"))
    sys.exit(0 if rep["verdict"] == "G3A_MEASURED" else 1)


if __name__ == "__main__":
    main()
