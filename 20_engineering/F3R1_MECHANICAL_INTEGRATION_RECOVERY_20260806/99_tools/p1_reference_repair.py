# -*- coding: utf-8 -*-
"""P1: reference-ownership verification + repair for the isolated copies.

Trap #9 (B3 campaign): a whole-tree copy of a SolidWorks assembly can silently
resolve some components back to the SOURCE tree via baked absolute paths. Any
later "edit the copy" then writes into the frozen donor. This script:

  1. reads dependencies of both copied top assemblies WITHOUT opening them;
  2. opens each copy and reads the ACTUAL resolved component paths;
  3. repairs any leak with IAssemblyDoc.ReplaceComponents2 to the F3R1 path;
  4. saves (candidate only), cold-reopens, and re-verifies 100% ownership;
  5. records mate totals/errors and component counts as the G1 evidence.

Writes only under F3R1. Donor trees are never opened for write.
"""
import json
import sys
import traceback
from pathlib import Path

from f3r1_env import F3R1, JLog, check_protected
import b3_lib.sw_core as swc
import sw_session as ss

log = JLog("p1_reference_repair")
OUT = F3R1 / "01_asset_selection" / "F3R1_REFERENCE_OWNERSHIP.json"

TARGETS = [
    ("SPACECRAFT_COPY",
     F3R1 / "03_native_cad/SPACECRAFT_V2_2_NATIVE_COPY/Assembly/Space_Embodied_Service_Spacecraft_V2_2.SLDASM",
     F3R1 / "03_native_cad/SPACECRAFT_V2_2_NATIVE_COPY"),
    ("B601_ARM_COPY",
     F3R1 / "03_native_cad/B601_ARM_B51_COPY/assembly/B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM",
     F3R1 / "03_native_cad/B601_ARM_B51_COPY"),
]


def leak_fix_map(leaks, allowed_root):
    """Map leaked path -> same-named file under the F3R1 copy (must exist)."""
    fixes, unmatched = {}, []
    index = {}
    for p in Path(allowed_root).rglob("*"):
        if p.is_file():
            index.setdefault(p.name.lower(), []).append(p)
    for lk in leaks:
        cands = index.get(Path(lk["path"]).name.lower(), [])
        if len(cands) == 1:
            fixes[lk["path"]] = str(cands[0])
        else:
            unmatched.append({"leak": lk, "candidates": [str(c) for c in cands]})
    return fixes, unmatched


def process(app, tag, top, root, rep):
    entry = {"top": str(top), "allowed_root": str(root)}

    pairs = ss.doc_dependencies(app, top)
    inside, leaks = ss.classify_deps(pairs, root)
    entry["pre_open_dependencies"] = {"total": len(pairs), "inside": len(inside),
                                      "leaks": leaks}
    log.ev("DEPS_PRE", tag=tag, total=len(pairs), leaks=len(leaks))

    blog = swc.BuildLog("p1_" + tag)
    model = swc.open_document(app, blog, str(top))
    comps = ss.components_of(model)
    actual_leaks = [c for c in comps
                    if c["path"] and not c["path"].lower().replace("/", "\\")
                    .startswith(str(root).lower().replace("/", "\\"))]
    entry["opened"] = {"components_total": len(comps),
                       "actual_leaks": actual_leaks}
    log.ev("OPEN_SCAN", tag=tag, comps=len(comps), leaks=len(actual_leaks))

    repaired = []
    if actual_leaks:
        fixes, unmatched = leak_fix_map(
            [{"path": c["path"]} for c in actual_leaks], root)
        if unmatched:
            entry["unmatched_leaks"] = unmatched
            log.ev("LEAK_UNMATCHED_FAIL_CLOSED", tag=tag, n=len(unmatched))
            raise RuntimeError("unmatched leaks in %s" % tag)
        asm = swc.cast(model, "IAssemblyDoc")
        gm = swc.get_com_member
        for c in actual_leaks:
            newp = fixes[c["path"]]
            conf = gm(model, "ConfigurationManager").ActiveConfiguration
            rootc = conf.GetRootComponent3(True)
            kids = gm(swc.cast(rootc, "IComponent2"), "GetChildren")

            def find(clist):
                for k in clist or []:
                    k2 = swc.cast(k, "IComponent2")
                    if str(gm(k2, "Name2")) == c["name"]:
                        return k2
                    got = find(gm(k2, "GetChildren"))
                    if got is not None:
                        return got
                return None

            comp_obj = find(kids)
            if comp_obj is None:
                raise RuntimeError("component not found for repair: %s" % c["name"])
            model.ClearSelection2(True)
            sel_ok = comp_obj.Select4(False, None, False)
            ok = asm.ReplaceComponents2(newp, "", False, 2, True)
            repaired.append({"component": c["name"], "old": c["path"],
                             "new": newp, "selected": bool(sel_ok),
                             "api_ok": bool(ok)})
            log.ev("REPLACED", tag=tag, comp=c["name"], ok=bool(ok))
        swc.rebuild_or_fail(model, blog, "post-replace rebuild")
        swc.save(model, blog)

    total, errors = ss.mate_status(model)
    entry["mates"] = {"total": total, "errors": errors}
    swc.close_document(app, model, blog)

    # cold reopen verification
    model2 = swc.open_document(app, blog, str(top))
    comps2 = ss.components_of(model2)
    leaks2 = [c for c in comps2
              if c["path"] and not c["path"].lower().replace("/", "\\")
              .startswith(str(root).lower().replace("/", "\\"))]
    t2, e2 = ss.mate_status(model2)
    entry["cold_reopen"] = {"components_total": len(comps2), "leaks": leaks2,
                            "mates_total": t2, "mate_errors": e2}
    entry["repaired"] = repaired
    entry["ownership"] = "ISOLATED_100PCT" if not leaks2 else "LEAKS_REMAIN"
    swc.close_document(app, model2, blog)
    log.ev("COLD_REOPEN", tag=tag, comps=len(comps2), leaks=len(leaks2),
           mates=t2, mate_errors=e2)
    rep["targets"][tag] = entry
    if leaks2:
        raise RuntimeError("ownership not isolated for %s" % tag)


def main():
    check_protected("P1_PRE")
    rep = {"schema": "F3R1_REFERENCE_OWNERSHIP_V1", "targets": {}}
    wd = ss.MemoryDialogWatchdog(log)
    wd.start()
    try:
        app = ss.connect(log)
        for tag, top, root in TARGETS:
            process(app, tag, top, root, rep)
        rep["verdict"] = "P1_PASS_OWNERSHIP_ISOLATED"
    except Exception as exc:
        rep["verdict"] = "P1_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-1500:]
        log.ev("P1_FAIL", error=str(exc))
    finally:
        wd.stop()
        rep["watchdog"] = {"memory_dialogs_dismissed": wd.dismissed,
                           "other_dialogs_logged": wd.seen_other}
    check_protected("P1_POST")
    OUT.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    print("verdict:", rep["verdict"])
    sys.exit(0 if rep["verdict"].startswith("P1_PASS") else 1)


if __name__ == "__main__":
    main()
