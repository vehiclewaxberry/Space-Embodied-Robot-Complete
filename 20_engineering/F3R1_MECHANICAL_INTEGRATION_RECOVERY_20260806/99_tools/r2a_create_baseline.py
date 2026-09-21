# -*- coding: utf-8 -*-
"""F3R2 step 1: create the operational-baseline candidate from V3_CONFIGURED.

GetPackAndGo is unusable on this machine (D-F3R1-01: InvokeTypes(207) binding
error), so the equivalent verifiable method is used: per-file copy of the whole
dependency closure + paired SHA-256 proof + in-SolidWorks reference ownership
check (trap #9: absolute paths leaking back to the source tree).

The V3 candidate and every upstream asset stay read-only; only the new F3R2 tree
is written.
"""
import csv
import json
import shutil
import sys
import traceback

from f3r1_env import F3R1, JLog, check_protected, sha256_file
import b3_lib.sw_core as swc
import sw_session as ss
import r2_env as R

log = JLog("r2a_baseline")
gm = R.gm
REP = R.NC2 / "F3R2_PACK_AND_GO_PROOF.json"
INV = R.NC2 / "F3R2_DEPENDENCY_INVENTORY.csv"


def main():
    rep = {"schema": "F3R2_BASELINE_CREATE_V1",
           "method": ("PER_FILE_COPY_PLUS_PAIRED_SHA256 "
                      "(GetPackAndGo unusable, D-F3R1-01)")}
    rows = []
    try:
        rep["protected_pre"] = check_protected("R2A_PRE")["verdict"]
        rep["v3_source"] = {"path": str(R.V3_SRC),
                            "sha256": sha256_file(R.V3_SRC)}
        if not rep["v3_source"]["sha256"].startswith(R.V3_SHA_PREFIX):
            raise RuntimeError("V3 source hash does not match authorised input")

        # ---- discover the dependency closure from the V3 assembly ----
        app, sess = R.fresh(log, "r2a_discover")
        rep["session_discover"] = sess
        blog = swc.BuildLog("r2a")
        wd = ss.MemoryDialogWatchdog(log)
        wd.start()
        try:
            src = swc.open_document(app, blog, str(R.V3_SRC), read_only=True)
            rep["v3_configs"] = list(gm(src, "GetConfigurationNames") or [])
            # Walk EVERY configuration: components suppressed in the active
            # config are not traversed, so a single-config walk misses files and
            # SolidWorks then resolves them back to the SOURCE tree (trap #9).
            # First pass missed Removable_Panels + both DEPLOYED wing panels.
            deps = {}
            for cname in R.CONFIGS:
                if cname not in rep["v3_configs"]:
                    continue
                swc.activate_configuration(src, blog, cname)
                src.ForceRebuild3(True)
                for leaf, full, k in R.walk_all(src):
                    p = str(gm(k, "GetPathName") or "")
                    if p:
                        deps[p] = deps.get(p, 0) + 1
            deps[str(R.V3_SRC)] = 1
            rep["closure_from_all_configs"] = True
            rep["n_dependency_files"] = len(deps)
            swc.close_document(app, src, blog)
        finally:
            wd.stop()
        R.kill_sw(log)

        # ---- copy the closure into the F3R2 tree, preserving structure ----
        f3r1_root = str(F3R1).lower()
        outside = []
        for p in sorted(deps):
            lp = p.lower()
            if not lp.startswith(f3r1_root):
                outside.append(p)
        rep["dependencies_outside_f3r1"] = outside
        if outside:
            raise RuntimeError("dependency outside F3R1: %d" % len(outside))

        from pathlib import Path
        for p in sorted(deps):
            srcp = Path(p)
            rel = srcp.relative_to(F3R1)
            # the top assembly is renamed; everything else keeps its relative path
            if str(srcp).lower() == str(R.V3_SRC).lower():
                dstp = R.BASELINE
            else:
                dstp = R.F3R2 / rel
            dstp.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(srcp, dstp)
            sa, sb = sha256_file(srcp), sha256_file(dstp)
            rows.append({"source": str(srcp), "destination": str(dstp),
                         "source_sha256": sa, "dest_sha256": sb,
                         "identical": sa == sb,
                         "instances_in_v3": deps[p]})
        rep["n_copied"] = len(rows)
        rep["all_identical"] = all(r["identical"] for r in rows)
        if not rep["all_identical"]:
            raise RuntimeError("copy SHA mismatch")
        log.ev("CLOSURE_COPIED", files=len(rows), identical=rep["all_identical"])

        # ---- reopen the F3R2 baseline and verify reference ownership ----
        app, sess2 = R.fresh(log, "r2a_verify")
        rep["session_verify"] = sess2
        blog = swc.BuildLog("r2a_v")
        wd = ss.MemoryDialogWatchdog(log)
        wd.start()
        try:
            top = swc.open_document(app, blog, str(R.BASELINE))
            rep["baseline_configs"] = list(gm(top, "GetConfigurationNames") or [])
            rep["all_eight_configs"] = all(c in rep["baseline_configs"]
                                           for c in R.CONFIGS)
            # ---- reference repair across ALL configs (trap #9) ----
            # Copying files does not rewrite references already stored in the
            # assembly; ReplaceComponents2 (proven in P1) repoints them.
            asm2 = swc.cast(top, "IAssemblyDoc")
            repaired, bad = [], []
            # ReplaceComponents2 acts on the shared document reference, so a
            # given file only needs repairing ONCE; without this guard the
            # per-config loop re-repaired Removable_Panels eight times.
            done_paths = set()
            for cname in R.CONFIGS:
                if cname not in rep["baseline_configs"]:
                    continue
                swc.activate_configuration(top, blog, cname)
                top.ForceRebuild3(True)
                for leaf, full, k in R.walk_all(top):
                    p = str(gm(k, "GetPathName") or "")
                    if not p or p.lower().startswith(str(R.F3R2).lower()):
                        continue
                    if p.lower() in done_paths:
                        continue
                    done_paths.add(p.lower())
                    from pathlib import Path
                    srcp = Path(p)
                    try:
                        newp = R.F3R2 / srcp.relative_to(F3R1)
                    except Exception:
                        bad.append({"component": full, "path": p,
                                    "repair": "NOT_UNDER_F3R1"})
                        continue
                    if not newp.is_file():
                        newp.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(srcp, newp)
                    top.ClearSelection2(True)
                    if not k.Select4(False, None, False):
                        bad.append({"component": full, "path": p,
                                    "repair": "SELECT_FAILED"})
                        continue
                    ok = asm2.ReplaceComponents2(str(newp), "", True, 2, True)
                    top.ClearSelection2(True)
                    repaired.append({"configuration": cname, "component": full,
                                     "old": p, "new": str(newp),
                                     "ok": bool(ok)})
                    log.ev("REF_REPAIRED", comp=full, ok=bool(ok))
            if repaired:
                swc.rebuild_or_fail(top, blog, "after reference repair")
                swc.save(top, blog)
            rep["references_repaired"] = repaired
            rep["n_references_repaired"] = len(repaired)

            # ---- re-verify across all configs ----
            for cname in R.CONFIGS:
                if cname not in rep["baseline_configs"]:
                    continue
                swc.activate_configuration(top, blog, cname)
                top.ForceRebuild3(True)
                for leaf, full, k in R.walk_all(top):
                    p = str(gm(k, "GetPathName") or "")
                    if p and not p.lower().startswith(str(R.F3R2).lower()):
                        bad.append({"component": full, "path": p,
                                    "configuration": cname})
            rep["references_leaking_outside_f3r2"] = bad[:40]
            rep["n_references_leaking"] = len(bad)
            t_all, t_err = ss.mate_status(top)
            rep["mates"] = {"total": t_all, "errors": t_err}
            kids = R.top_children(top)
            rep["top_components"] = sorted(kids.keys())
            rep["n_top_components"] = len(kids)
            swc.close_document(app, top, blog)
        finally:
            wd.stop()
        R.kill_sw(log)

        rep["baseline"] = {"path": str(R.BASELINE),
                           "sha256": sha256_file(R.BASELINE)}
        rep["protected_post"] = check_protected("R2A_POST")["verdict"]
        rep["v3_unchanged"] = (sha256_file(R.V3_SRC) ==
                               rep["v3_source"]["sha256"])
        ok = (rep["all_identical"] and rep["all_eight_configs"]
              and rep["n_references_leaking"] == 0
              and rep["mates"]["errors"] == 0 and rep["v3_unchanged"])
        rep["verdict"] = "R2A_BASELINE_CREATED" if ok else "R2A_CHECK"
    except Exception as exc:
        rep["verdict"] = "R2A_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-2000:]
        log.ev("R2A_FAIL", error=str(exc))
        try:
            R.kill_sw(log)
        except Exception:
            pass

    if rows:
        with open(INV, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            for r in rows:
                w.writerow(r)
    REP.write_text(json.dumps(rep, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print("verdict:", rep["verdict"])
    print("  deps:", rep.get("n_dependency_files"), "copied:",
          rep.get("n_copied"), "identical:", rep.get("all_identical"))
    print("  baseline sha:", (rep.get("baseline") or {}).get("sha256", "")[:20])
    print("  8 configs:", rep.get("all_eight_configs"),
          "| refs leaking:", rep.get("n_references_leaking"),
          "| mates:", rep.get("mates"))
    print("  V3 unchanged:", rep.get("v3_unchanged"),
          "| protected:", rep.get("protected_post"))
    if rep["verdict"] == "R2A_FAIL":
        print(rep.get("traceback"))
    sys.exit(0 if rep["verdict"] == "R2A_BASELINE_CREATED" else 1)


if __name__ == "__main__":
    main()
