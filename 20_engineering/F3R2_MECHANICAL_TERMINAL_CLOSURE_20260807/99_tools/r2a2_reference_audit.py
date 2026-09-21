# -*- coding: utf-8 -*-
"""F3R2 R2A-resume: audit where the copied baseline actually resolves its
references, per configuration, and inventory every component.

The previous attempt crashed (RPC death after a fatal low-memory dialog) before
it could record anything, so nothing about the copied baseline is yet known.
This script MEASURES first and repairs nothing: SolidWorks resolves references
by relative path as well as by stored absolute path, so the copied tree may
already be self-contained.  Assuming a repair is needed would rewrite and
re-save 73 documents for no reason -- and every extra write is a chance to
corrupt the candidate.

Outputs (F3R2 only):
  03_native_cad/F3R2_REFERENCE_AUDIT.json
  03_native_cad/F3R2_COMPONENT_INVENTORY.csv     (component x configuration)
"""
import sys
import traceback

import r2_common as C

log = C.Log("r2a2_reference_audit")
gm = C.gm
OUTJ = C.NC2 / "F3R2_REFERENCE_AUDIT.json"
OUTC = C.NC2 / "F3R2_COMPONENT_INVENTORY.csv"


def audit(app, blog, attempt):
    top = C.open_silent(app, blog, str(C.BASELINE))
    out = {"attempt": attempt}
    out["configs_present"] = list(gm(top, "GetConfigurationNames") or [])
    rows = []
    percfg = {}
    f3r2_root = str(C.F3R2).lower()
    f3r1_root = str(C.F3R1).lower()
    for cname in C.CONFIGS:
        if cname not in out["configs_present"]:
            percfg[cname] = {"status": "CONFIG_ABSENT"}
            continue
        C.swc.activate_configuration(top, blog, cname)
        if not top.ForceRebuild3(True):
            raise RuntimeError("rebuild failed: %s" % cname)
        inside = outside = 0
        n_supp = 0
        for leaf, full, k in C.R.walk_all(top):
            p = str(gm(k, "GetPathName") or "")
            lp = p.lower()
            where = ("F3R2" if lp.startswith(f3r2_root)
                     else "F3R1" if lp.startswith(f3r1_root)
                     else "ELSEWHERE" if p else "NO_PATH")
            supp = bool(gm(k, "IsSuppressed"))
            if where == "F3R2":
                inside += 1
            else:
                outside += 1
            if supp:
                n_supp += 1
            rows.append({"configuration": cname, "leaf": leaf,
                         "full_name": full, "path": p, "resolves_in": where,
                         "suppressed": supp,
                         "referenced_config": str(
                             gm(k, "ReferencedConfiguration") or ""),
                         "depth": full.count("/")})
        t_all, t_err = C.ss.mate_status(top)
        percfg[cname] = {"status": "MEASURED", "components": inside + outside,
                         "resolved_inside_f3r2": inside,
                         "resolved_outside_f3r2": outside,
                         "suppressed": n_supp,
                         "mates_total": t_all, "mates_error": t_err}
        log.ev("CFG_AUDITED", config=cname, inside=inside, outside=outside,
               supp=n_supp, mates=t_all, mate_err=t_err,
               avail_mb=C.avail_mb())
    out["per_configuration"] = percfg
    kids = C.R.top_children(top)
    out["top_components"] = sorted(kids.keys())
    out["n_top_components"] = len(kids)
    out["mate_rows"] = C.R.mate_rows(top)
    C.swc.activate_configuration(top, blog, "DEPLOYED_NOMINAL")
    C.swc.close_document(app, top, blog)
    out["rows"] = rows
    return out


def main():
    rep = {"schema": "F3R2_REFERENCE_AUDIT_V1", "baseline": str(C.BASELINE),
           "purpose": ("measure reference ownership of the copied baseline "
                       "before deciding whether any repair write is justified")}
    rows = []
    try:
        rep["protected_pre"] = C.check_protected2("R2A2_PRE")["verdict"]
        rep["baseline_sha_pre"] = C.sha256_file(C.BASELINE)
        rep["avail_mb_pre"] = C.avail_mb()
        out = C.with_retry(log, "r2a2", audit, attempts=3)
        rows = out.pop("rows", [])
        rep.update(out)
        rep["baseline_sha_post"] = C.sha256_file(C.BASELINE)
        rep["baseline_unchanged"] = (rep["baseline_sha_post"] ==
                                     rep["baseline_sha_pre"])
        rep["protected_post"] = C.check_protected2("R2A2_POST")["verdict"]
        percfg = rep["per_configuration"]
        meas = [v for v in percfg.values() if v.get("status") == "MEASURED"]
        rep["all_eight_configs"] = (len(meas) == len(C.CONFIGS))
        rep["total_resolved_outside_f3r2"] = sum(
            v["resolved_outside_f3r2"] for v in meas)
        rep["mate_errors_max"] = max([v["mates_error"] for v in meas] or [-1])
        rep["repair_required"] = rep["total_resolved_outside_f3r2"] > 0
        rep["verdict"] = ("R2A2_SELF_CONTAINED"
                          if not rep["repair_required"] else
                          "R2A2_REPAIR_REQUIRED")
    except Exception as exc:
        rep["verdict"] = "R2A2_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-2500:]
        log.ev("R2A2_FAIL", error=str(exc)[:200])

    C.write_csv(OUTC, rows)
    C.write_json(OUTJ, rep)
    print("\nverdict:", rep["verdict"])
    for c, v in (rep.get("per_configuration") or {}).items():
        print("  %-30s %s" % (c, v))
    print("  top components:", rep.get("n_top_components"))
    print("  outside F3R2:", rep.get("total_resolved_outside_f3r2"),
          "| mate err max:", rep.get("mate_errors_max"),
          "| baseline unchanged:", rep.get("baseline_unchanged"))
    if rep["verdict"] == "R2A2_FAIL":
        print(rep.get("traceback"))
    sys.exit(0 if rep["verdict"] in ("R2A2_SELF_CONTAINED",
                                     "R2A2_REPAIR_REQUIRED") else 1)


if __name__ == "__main__":
    main()
