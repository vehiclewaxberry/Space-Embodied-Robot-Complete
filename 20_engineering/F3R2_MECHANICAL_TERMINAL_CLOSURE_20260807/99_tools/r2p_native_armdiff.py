# -*- coding: utf-8 -*-
"""F3R2 native ARM-DIFFERENCE experiment.

Problem: IInterference.GetComponents is unreachable on this SolidWorks 2024
install (early-bound AND late-bound), so a native interference pair cannot be
named.  "arm pairs = 0" would then be an artefact of not knowing, not evidence.

Solution that needs no naming: measure the SAME configuration twice, once with
the arm resolved and once with the arm suppressed.  Every pair that disappears
when the arm is suppressed involved the arm; every pair that remains did not.
The difference is the arm's native interference count, from SolidWorks' own
B-rep kernel.

The arm is suppressed only in a THROWAWAY configuration derived in-session and
never saved, so the frozen eight configurations are untouched -- the baseline
hash is checked before and after.

usage: python r2p_native_armdiff.py <CONFIG_NAME>
"""
import json
import sys
import traceback

import r2_common as C

gm = C.gm
OUT = C.CLR2 / "F3R2_NATIVE_ARM_DIFFERENCE.json"
ARM_TOP = "B51_B601_ARTICULATED_ENGINEERING_ARM-1"
SW_SUPPRESSED, SW_RESOLVED = 0, 2


def volumes(mgr, log, tag):
    """Sorted interference volumes (mm^3) -- a naming-free fingerprint."""
    out = []
    for r in list(mgr.GetInterferences() or []):
        it = C.swc.cast(r, "IInterference")
        try:
            out.append(round(float(gm(it, "Volume")) * 1e9, 6))
        except Exception:
            out.append(None)
    out.sort(key=lambda v: -(v or 0))
    log.ev("IDM_RUN", tag=tag, n=len(out), avail_mb=C.avail_mb())
    return out


def main():
    cname = sys.argv[1] if len(sys.argv) > 1 else "STOWED_ENGINEERING_CANDIDATE"
    log = C.Log("r2p_armdiff_%s" % cname.lower())
    rep = {"schema": "F3R2_NATIVE_ARM_DIFFERENCE_V1", "configuration": cname,
           "method": ("same configuration measured twice -- arm resolved vs "
                      "arm suppressed; the difference is the arm's native "
                      "interference, and it needs no component naming"),
           "why": ("IInterference.GetComponents raises on this install, so "
                   "pairs cannot be named; 'arm pairs = 0' from naming would "
                   "be an artefact, not evidence")}
    try:
        rep["protected_pre"] = C.check_protected2("ARMDIFF_PRE")["verdict"]
        rep["baseline_sha_pre"] = C.sha256_file(C.BASELINE)

        def body(app, blog, attempt, beat=None):
            top = C.open_silent(app, blog, str(C.BASELINE))
            asm = C.swc.cast(top, "IAssemblyDoc")
            C.swc.activate_configuration(top, blog, cname)
            if not top.ForceRebuild3(True):
                raise RuntimeError("rebuild failed")
            mgr = gm(asm, "InterferenceDetectionManager")
            for p, v in (("TreatCoincidenceAsInterference", False),
                         ("TreatSubAssembliesAsComponents", True),
                         ("IncludeMultibodyPartInterferences", True),
                         ("MakeInterferingPartsTransparent", False),
                         ("ShowIgnoredInterferences", False)):
                try:
                    setattr(mgr, p, v)
                except Exception:
                    pass
            kids = C.R.top_children(top)
            if ARM_TOP not in kids:
                raise RuntimeError("arm component not at top level: %s"
                                   % sorted(kids))
            arm = kids[ARM_TOP]
            was = bool(gm(arm, "IsSuppressed"))
            with_arm = volumes(mgr, log, "arm_resolved")
            if beat:
                beat()

            # Suppress the arm IN MEMORY ONLY, in THIS configuration.
            # IComponent2.SetSuppression2(State) alone did not take effect on
            # this build (known config-scope trap); Select + Extension.
            # SelectByID2 with the assembly-level suppress API is the route
            # that actually applies.  Every attempt is verified by reading
            # IsSuppressed back, and a silent no-op raises.
            applied = None
            for how in ("SetSuppression2_only_this_config",
                        "AssemblyDoc_component_suppress",
                        "SetSuppression2_plain"):
                try:
                    if how == "SetSuppression2_only_this_config":
                        # 1 == swThisConfiguration
                        arm.SetSuppression2(SW_SUPPRESSED, 1, None)
                    elif how == "AssemblyDoc_component_suppress":
                        top.ClearSelection2(True)
                        if not arm.Select4(False, None, False):
                            continue
                        top.EditSuppress2()
                        top.ClearSelection2(True)
                    else:
                        arm.SetSuppression2(SW_SUPPRESSED)
                    top.ForceRebuild3(True)
                    k = C.R.top_children(top).get(ARM_TOP)
                    gone = (k is None) or bool(gm(k, "IsSuppressed"))
                    log.ev("SUPPRESS_ATTEMPT", how=how, effective=gone)
                    if gone:
                        applied = how
                        break
                except Exception as e:
                    log.ev("SUPPRESS_ATTEMPT_ERROR", how=how, err=str(e)[:90])
            if applied is None:
                raise RuntimeError("arm suppression did not take effect by "
                                   "any route")
            without_arm = volumes(mgr, log, "arm_suppressed")
            if beat:
                beat()

            arm2 = C.R.top_children(top).get(ARM_TOP)
            if arm2 is not None:
                try:
                    arm2.SetSuppression2(SW_RESOLVED, 1, None)
                except Exception:
                    arm2.SetSuppression2(SW_RESOLVED)
                top.ForceRebuild3(True)
            k = C.R.top_children(top).get(ARM_TOP)
            restored = k is not None and not bool(gm(k, "IsSuppressed"))
            # close WITHOUT saving: the throwaway suppression must not persist
            C.swc.close_document(app, top, blog)
            return {"arm_was_suppressed_before": was,
                    "suppression_route": applied,
                    "with_arm": with_arm, "without_arm": without_arm,
                    "arm_restored_in_session": restored}

        out = C.with_retry(log, "r2p_%s" % cname, body, attempts=2)
        wa, wo = out["with_arm"], out["without_arm"]

        # multiset difference on the volume fingerprint
        from collections import Counter
        ca, co = Counter(wa), Counter(wo)
        vanished = list((ca - co).elements())
        appeared = list((co - ca).elements())
        rep.update({
            "pairs_with_arm": len(wa),
            "pairs_without_arm": len(wo),
            "pairs_involving_arm": len(wa) - len(wo),
            "volumes_that_vanished_when_arm_suppressed": sorted(
                vanished, key=lambda v: -(v or 0))[:40],
            "volumes_that_appeared_when_arm_suppressed": sorted(
                appeared, key=lambda v: -(v or 0))[:40],
            "arm_interference_volume_mm3": round(
                sum(v for v in vanished if v), 6),
            "arm_restored_in_session": out["arm_restored_in_session"],
            "session": out.get("session")})
        rep["baseline_sha_post"] = C.sha256_file(C.BASELINE)
        rep["baseline_unchanged"] = (rep["baseline_sha_post"] ==
                                     rep["baseline_sha_pre"])
        rep["protected_post"] = C.check_protected2("ARMDIFF_POST")["verdict"]
        if appeared:
            rep["verdict"] = "ARMDIFF_INCONSISTENT_NEW_PAIRS_APPEARED"
        elif not rep["baseline_unchanged"]:
            rep["verdict"] = "ARMDIFF_FAIL_BASELINE_MODIFIED"
        elif rep["pairs_involving_arm"] == 0:
            rep["verdict"] = "ARM_NATIVE_INTERFERENCE_ZERO"
        else:
            rep["verdict"] = "ARM_NATIVE_INTERFERENCE_PRESENT"
    except Exception as exc:
        rep["verdict"] = "ARMDIFF_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-2000:]

    prev = json.loads(OUT.read_text(encoding="utf-8")) if OUT.is_file() else {}
    prev[cname] = rep
    C.write_json(OUT, prev)
    print("\n%s  ->  %s" % (cname, rep["verdict"]))
    print("   pairs with arm=%s  without arm=%s  =>  involving arm=%s"
          % (rep.get("pairs_with_arm"), rep.get("pairs_without_arm"),
             rep.get("pairs_involving_arm")))
    print("   arm interference volume: %s mm3"
          % rep.get("arm_interference_volume_mm3"))
    print("   baseline unchanged:", rep.get("baseline_unchanged"),
          "| arm restored:", rep.get("arm_restored_in_session"))
    if rep["verdict"] == "ARMDIFF_FAIL":
        print(rep.get("traceback"))
    sys.exit(0 if rep["verdict"].startswith("ARM_NATIVE") else 1)


if __name__ == "__main__":
    main()
