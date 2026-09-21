# -*- coding: utf-8 -*-
"""F3R2 G3-A: locate arm<->spacecraft interference on the NEW baseline, in all
eight configurations.  Declared first priority.

The older "native interference = 0" belonged to a different candidate and to the
pre-G2 configuration logic.  It is NOT used to dismiss anything here: every
configuration of F3R2_..._OPERATIONAL_BASELINE is measured fresh, in a clean
SolidWorks session.

Fail-closed rules honoured:
  * a pair is only excluded with an explicit, recorded reason;
  * anything the SolidWorks API does not provide is written as
    NOT_PROVIDED_BY_API -- never invented, never silently dropped;
  * a configuration that could not be measured stays CANNOT_EVALUATE and does
    not read as "clean".

Per-configuration results are journalled as soon as they are produced, so a
low-memory RPC death (D-F3R2-01) costs one configuration, not the whole run;
re-running resumes from the journal.
"""
import json
import sys
import traceback

import r2_common as C

log = C.Log("r2b2_g3a")
gm = C.gm
OUTJ = C.CLR2 / "G3A_NATIVE_INTERFERENCE_RESULTS.json"
OUTC = C.CLR2 / "G3A_INTERFERENCE_PAIR_REGISTER.csv"
JOURNAL = C.CLR2 / "G3A_JOURNAL.json"

ARM_TOKENS = ("B51_REF_", "B51_REV_", "B51_B601")
BUS_GROUPS = {
    "primary_structure": ("01_Primary_Structure", "Deck_", "Removable_Panels",
                          "Longeron", "Frame", "Bay", "Panel"),
    "adapter_plate": ("Adapter_Plate",),
    "central_boss": ("Central_Boss",),
    "spacecraft_flange": ("Spacecraft_Flange",),
    "load_path": ("Load_Bridge", "Load_Spreading", "Harness_Passage",
                  "Maintenance_Access"),
    "solar_root": ("05_Solar_Array_Root", "06_Solar_Array_Root", "Root_Base",
                   "Root_Node", "Hinge", "Torsion_Spring", "Hard_Stop",
                   "HDRM"),
    "solar_wing": ("WING_",),
    "saddles": ("Aft_Saddle", "Fwd_Saddle", "Mid_Saddle", "Saddle"),
    "arm_stow_support": ("04_ARM_STOW_SUPPORT", "Launch_Lock_Interface",
                         "Release_Clearance_Envelope"),
}
# Reference / envelope-only bodies: registered, never counted as a real
# engineering interference, but the reason is always written down.
REFERENCE_TOKENS = ("Launch_Lock_Interface_Reference",
                    "Release_Clearance_Envelope", "Master_Skeleton",
                    "_REFERENCE", "_ENVELOPE")


def classify(leaf):
    if any(t in leaf for t in ARM_TOKENS):
        return "arm"
    for g, toks in BUS_GROUPS.items():
        if any(t in leaf for t in toks):
            return g
    return "other"


def is_reference_only(leaf):
    return any(t in leaf for t in REFERENCE_TOKENS)


def probe_interference_api(it):
    """Record exactly which IInterference members this build exposes, so the
    register can say NOT_PROVIDED_BY_API honestly instead of guessing."""
    got = {}
    for name in ("Volume", "Name", "GetComponents", "GetBox", "IsCoincident",
                 "GetFaces", "Component1", "Component2"):
        try:
            v = getattr(it, name)
            got[name] = "callable" if callable(v) else str(type(v).__name__)
        except Exception:
            got[name] = "ABSENT"
    return got


def measure_config(top, asm, cname, blog):
    """Native interference for one configuration, with per-pair detail."""
    C.swc.activate_configuration(top, blog, cname)
    if not top.ForceRebuild3(True):
        raise RuntimeError("rebuild failed: %s" % cname)
    supp, live = set(), set()
    for leaf, full, k in C.R.walk_all(top):
        (supp if bool(gm(k, "IsSuppressed")) else live).add(leaf)

    mgr = gm(asm, "InterferenceDetectionManager")
    if mgr is None:
        return {"status": "CANNOT_EVALUATE", "reason": "NO_IDM"}, []
    for p, v in (("TreatCoincidenceAsInterference", False),
                 ("TreatSubAssembliesAsComponents", True),
                 ("IncludeMultibodyPartInterferences", True),
                 ("MakeInterferingPartsTransparent", False),
                 ("ShowIgnoredInterferences", False),
                 ("UseSelectedComponents", False)):
        try:
            setattr(mgr, p, v)
        except Exception as e:
            log.ev("IDM_PROP_SKIP", prop=p, err=str(e)[:70])

    raw = mgr.GetInterferences()
    items = list(raw or [])
    api_probe = None
    rows = []
    for r in items:
        it = C.swc.cast(r, "IInterference")
        if api_probe is None:
            api_probe = probe_interference_api(it)
        try:
            vol = float(gm(it, "Volume")) * 1e9  # m^3 -> mm^3
        except Exception:
            vol = None
        comps = []
        try:
            for c in list(gm(it, "GetComponents") or []):
                comps.append(str(gm(C.swc.cast(c, "IComponent2"), "Name2")))
        except Exception:
            pass
        leaves = [c.split("/")[-1] for c in comps]
        # centroid: only if the build exposes a box; never fabricated
        centroid = "NOT_PROVIDED_BY_API"
        try:
            box = gm(it, "GetBox")
            if box:
                b = [float(x) * 1000.0 for x in box]
                centroid = [round((b[0] + b[3]) / 2, 3),
                            round((b[1] + b[4]) / 2, 3),
                            round((b[2] + b[5]) / 2, 3)]
        except Exception:
            pass
        classes = sorted({classify(l) for l in leaves})
        excl = None
        if any(is_reference_only(l) for l in leaves):
            excl = "REFERENCE_OR_ENVELOPE_BODY"
        elif any(l in supp for l in leaves):
            excl = "SUPPRESSED_COMPONENT"
        elif len(leaves) >= 2 and leaves[0] == leaves[1]:
            excl = "SAME_COMPONENT_SELF_PAIR"
        rows.append({
            "configuration": cname,
            "component_a": leaves[0] if leaves else "",
            "component_b": leaves[1] if len(leaves) > 1 else "",
            "full_a": comps[0] if comps else "",
            "full_b": comps[1] if len(comps) > 1 else "",
            "volume_mm3": vol,
            "centroid_mm": centroid,
            "faces": "NOT_PROVIDED_BY_API",
            "classes": ",".join(classes),
            "involves_arm": "arm" in classes,
            "component_kind_a": ("REFERENCE_ONLY"
                                 if leaves and is_reference_only(leaves[0])
                                 else "PHYSICAL"),
            "component_kind_b": ("REFERENCE_ONLY"
                                 if len(leaves) > 1 and is_reference_only(leaves[1])
                                 else "PHYSICAL"),
            "in_mass_collision_bom": (excl is None),
            "excluded_reason": excl or "",
            "counts_as_real": excl is None,
        })
    rows.sort(key=lambda d: -(d["volume_mm3"] or 0))
    real = [r for r in rows if r["counts_as_real"]]
    arm = [r for r in real if r["involves_arm"]]
    return ({"status": "MEASURED", "count_raw": len(rows),
             "count_real": len(real), "count_real_arm": len(arm),
             "real_volume_mm3": round(sum(r["volume_mm3"] or 0
                                          for r in real), 5),
             "arm_volume_mm3": round(sum(r["volume_mm3"] or 0
                                         for r in arm), 5),
             "live_components": len(live), "suppressed_components": len(supp),
             "api_probe": api_probe,
             "top_real_pairs": real[:10]}, rows)


def run(todo):
    def body(app, blog, attempt):
        top = C.open_silent(app, blog, str(C.BASELINE))
        asm = C.swc.cast(top, "IAssemblyDoc")
        present = list(gm(top, "GetConfigurationNames") or [])
        done = {}
        for cname in todo:
            if cname not in present:
                done[cname] = ({"status": "CONFIG_ABSENT"}, [])
                continue
            summ, rows = measure_config(top, asm, cname, blog)
            done[cname] = (summ, rows)
            log.ev("G3A_CONFIG", config=cname, status=summ.get("status"),
                   raw=summ.get("count_raw"), real=summ.get("count_real"),
                   arm=summ.get("count_real_arm"),
                   arm_vol=summ.get("arm_volume_mm3"), avail_mb=C.avail_mb())
            # journal immediately: a crash must cost one configuration only
            jr = json.loads(JOURNAL.read_text(encoding="utf-8")) \
                if JOURNAL.is_file() else {}
            jr[cname] = {"summary": summ, "rows": rows}
            C.write_json(JOURNAL, jr)
        C.swc.activate_configuration(top, blog, "DEPLOYED_NOMINAL")
        C.swc.close_document(app, top, blog)
        return {"configs_present": present, "measured": list(done.keys())}
    return C.with_retry(log, "r2b2", body, attempts=3)


def main():
    rep = {"schema": "F3R2_G3A_INTERFERENCE_V1", "baseline": str(C.BASELINE),
           "note": ("Fresh measurement on the F3R2 baseline. Prior "
                    "'interference 0' results belonged to an older candidate "
                    "and older configuration logic and are NOT used to dismiss "
                    "these findings (user directive, 2026-08-07).")}
    try:
        rep["protected_pre"] = C.check_protected2("R2B2_PRE")["verdict"]
        rep["baseline_sha_pre"] = C.sha256_file(C.BASELINE)
        jr = json.loads(JOURNAL.read_text(encoding="utf-8")) \
            if JOURNAL.is_file() else {}
        todo = [c for c in C.CONFIGS
                if jr.get(c, {}).get("summary", {}).get("status") != "MEASURED"]
        rep["resumed_from_journal"] = [c for c in C.CONFIGS if c not in todo]
        if todo:
            out = run(todo)
            rep.update({k: v for k, v in out.items() if k != "measured"})
            jr = json.loads(JOURNAL.read_text(encoding="utf-8"))
        percfg = {c: jr.get(c, {}).get("summary", {"status": "CANNOT_EVALUATE",
                                                   "reason": "NOT_RUN"})
                  for c in C.CONFIGS}
        rows = [r for c in C.CONFIGS for r in jr.get(c, {}).get("rows", [])]

        # nearest valid non-interfering configuration, per real pair
        clean = {}
        for r in rows:
            key = tuple(sorted([r["component_a"], r["component_b"]]))
            clean.setdefault(key, set())
            if r["counts_as_real"]:
                clean[key].add(r["configuration"])
        for r in rows:
            key = tuple(sorted([r["component_a"], r["component_b"]]))
            bad = clean.get(key, set())
            ok = [c for c in C.CONFIGS
                  if percfg.get(c, {}).get("status") == "MEASURED"
                  and c not in bad]
            r["nearest_non_interfering_config"] = (
                ok[0] if ok else "NONE_MEASURED_CLEAN")

        rep["per_configuration"] = percfg
        meas = [v for v in percfg.values() if v.get("status") == "MEASURED"]
        rep["configs_measured"] = len(meas)
        rep["all_eight_measured"] = len(meas) == len(C.CONFIGS)
        rep["total_real_pairs"] = sum(v["count_real"] for v in meas)
        rep["total_real_arm_pairs"] = sum(v["count_real_arm"] for v in meas)
        dn = percfg.get("DEPLOYED_NOMINAL", {})
        rep["deployed_nominal"] = {
            "status": dn.get("status"),
            "real_pairs": dn.get("count_real"),
            "real_arm_pairs": dn.get("count_real_arm"),
            "real_volume_mm3": dn.get("real_volume_mm3")}
        rep["baseline_sha_post"] = C.sha256_file(C.BASELINE)
        rep["baseline_unchanged"] = (rep["baseline_sha_post"] ==
                                     rep["baseline_sha_pre"])
        rep["protected_post"] = C.check_protected2("R2B2_POST")["verdict"]
        rep["verdict"] = ("G3A_MEASURED" if rep["all_eight_measured"]
                          else "G3A_INCOMPLETE")
        C.write_csv(OUTC, rows, fields=[
            "configuration", "component_a", "component_b", "classes",
            "volume_mm3", "centroid_mm", "faces", "involves_arm",
            "component_kind_a", "component_kind_b", "in_mass_collision_bom",
            "counts_as_real", "excluded_reason",
            "nearest_non_interfering_config", "full_a", "full_b"])
    except Exception as exc:
        rep["verdict"] = "G3A_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-2500:]
        log.ev("G3A_FAIL", error=str(exc)[:200])

    C.write_json(OUTJ, rep)
    print("\nverdict:", rep["verdict"])
    for c, v in (rep.get("per_configuration") or {}).items():
        if v.get("status") != "MEASURED":
            print("  %-30s %s" % (c, v.get("status")))
            continue
        print("  %-30s raw=%-3s real=%-3s arm=%-3s arm_vol=%s mm3"
              % (c, v["count_raw"], v["count_real"], v["count_real_arm"],
                 v["arm_volume_mm3"]))
        for p in v.get("top_real_pairs", [])[:5]:
            print("        %10s mm3  %-26s <-> %-26s [%s]"
                  % (p["volume_mm3"], p["component_a"][:26],
                     p["component_b"][:26], p["classes"]))
    print("  total real pairs:", rep.get("total_real_pairs"),
          "| arm pairs:", rep.get("total_real_arm_pairs"))
    print("  baseline unchanged:", rep.get("baseline_unchanged"))
    if rep["verdict"] == "G3A_FAIL":
        print(rep.get("traceback"))
    sys.exit(0 if rep["verdict"] == "G3A_MEASURED" else 1)


if __name__ == "__main__":
    main()
