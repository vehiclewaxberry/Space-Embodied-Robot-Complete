# -*- coding: utf-8 -*-
"""F3R2 G3-A (chunked): native interference for ONE configuration per process.

Why chunked: whole-assembly interference detection on all eight configurations
in a single SolidWorks session exhausts this machine (~1.0 GB free), SolidWorks
raises a fatal low-memory dialog and dies mid-COM-call (D-F3R2-01).  Measuring
one configuration per process, with SolidWorks killed in between, keeps peak
memory to a single configuration.

Two-stage detection, same physics, far less memory:
  stage 1  TreatSubAssembliesAsComponents = True  -> the six top-level bodies
           (arm, spacecraft, four wing panels).  Cheap, and it answers the
           actual question "does the arm touch the spacecraft / a wing".
  stage 2  only for the pairs stage 1 flags, re-run with sub-assemblies
           expanded and UseSelectedComponents restricted to that pair, to name
           the offending leaf parts.

Stage 2 is skipped when stage 1 is clean -- and that skip is recorded, so a
clean result can never be confused with an unmeasured one.

usage:  python r2b3_g3a_chunked.py <CONFIG_NAME>
"""
import json
import sys
import traceback

import pythoncom

import r2_common as C

gm = C.gm
JOURNAL = C.CLR2 / "G3A_JOURNAL.json"

ARM_TOKENS = ("B51_REF_", "B51_REV_", "B51_B601")
REFERENCE_TOKENS = ("Launch_Lock_Interface_Reference",
                    "Release_Clearance_Envelope", "Master_Skeleton",
                    "_REFERENCE", "_ENVELOPE")


def is_arm(leaf):
    return any(t in leaf for t in ARM_TOKENS)


def is_reference_only(leaf):
    return any(t in leaf for t in REFERENCE_TOKENS)


def _set(mgr, log, **props):
    for p, v in props.items():
        try:
            setattr(mgr, p, v)
        except Exception as e:
            log.ev("IDM_PROP_SKIP", prop=p, err=str(e)[:70])


def _late(obj):
    """Late-bound IDispatch view of a COM object.

    The early-bound (makepy) IInterference wrapper on this install exposes only
    Volume and GetComponentCount -- GetComponents, Component1/2, GetBox and the
    rest raise AttributeError.  Going through plain IDispatch recovers them.
    """
    import win32com.client as wc
    try:
        return wc.dynamic.Dispatch(obj._oleobj_.QueryInterface(
            pythoncom.IID_IDispatch))
    except Exception:
        try:
            return wc.dynamic.Dispatch(obj)
        except Exception:
            return None


def _names_of(it, log):
    """Component names of one interference, early-bound first then late."""
    for get in (lambda o: gm(o, "GetComponents"),):
        try:
            raw = get(it)
            if raw:
                return [str(gm(C.swc.cast(c, "IComponent2"), "Name2"))
                        for c in list(raw)]
        except Exception:
            pass
    d = _late(it)
    if d is None:
        return []
    for attr in ("GetComponents",):
        try:
            raw = getattr(d, attr)
            raw = raw() if callable(raw) else raw
            if raw:
                out = []
                for c in list(raw):
                    try:
                        out.append(str(C.swc.cast(c, "IComponent2").Name2))
                    except Exception:
                        out.append(str(getattr(c, "Name2", "")))
                if any(out):
                    return out
        except Exception as e:
            log.ev("LATE_GETCOMPONENTS_FAILED", err=str(e)[:90])
    try:
        n = int(d.GetComponentCount)
        out = []
        for i in range(n):
            c = d.GetComponent(i)
            out.append(str(C.swc.cast(c, "IComponent2").Name2))
        if any(out):
            return out
    except Exception as e:
        log.ev("LATE_GETCOMPONENT_INDEX_FAILED", err=str(e)[:90])
    return []


def _collect(mgr, log, stage):
    out = []
    probed = False
    for r in list(mgr.GetInterferences() or []):
        it = C.swc.cast(r, "IInterference")
        if not probed:
            probed = True
            avail = {}
            d = _late(it)
            for name in ("Volume", "GetComponents", "GetComponentCount",
                         "GetComponent", "GetBox", "Name"):
                try:
                    v = getattr(it, name)
                    avail["early." + name] = ("callable" if callable(v)
                                              else type(v).__name__)
                except Exception:
                    avail["early." + name] = "ABSENT"
                if d is not None:
                    try:
                        v = getattr(d, name)
                        avail["late." + name] = ("callable" if callable(v)
                                                 else repr(v)[:40])
                    except Exception as e:
                        avail["late." + name] = "ABSENT:%s" % str(e)[:30]
            log.ev("IINTERFERENCE_API_PROBE", stage=stage, members=avail)
        try:
            vol = round(float(gm(it, "Volume")) * 1e9, 6)
        except Exception:
            vol = None
        comps = _names_of(it, log)
        if not comps:
            comps = ["UNNAMED_BY_API", "UNNAMED_BY_API"]
        leaves = [c.split("/")[-1] for c in comps]
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
        out.append({"stage": stage, "volume_mm3": vol, "components": comps,
                    "leaves": leaves, "centroid_mm": centroid})
    out.sort(key=lambda d: -(d["volume_mm3"] or 0))
    log.ev("IDM_STAGE", stage=stage, n=len(out), avail_mb=C.avail_mb())
    return out


def measure(cname):
    log = C.Log("r2b3_%s" % cname.lower())

    def body(app, blog, attempt):
        top = C.open_silent(app, blog, str(C.BASELINE))
        asm = C.swc.cast(top, "IAssemblyDoc")
        present = list(gm(top, "GetConfigurationNames") or [])
        if cname not in present:
            C.swc.close_document(app, top, blog)
            return {"status": "CONFIG_ABSENT"}
        C.swc.activate_configuration(top, blog, cname)
        if not top.ForceRebuild3(True):
            raise RuntimeError("rebuild failed: %s" % cname)

        kids = C.R.top_children(top)
        supp_top = {n for n, k in kids.items() if bool(gm(k, "IsSuppressed"))}
        live_top = [n for n in kids if n not in supp_top]

        mgr = gm(asm, "InterferenceDetectionManager")
        if mgr is None:
            raise RuntimeError("no InterferenceDetectionManager")
        _set(mgr, log, TreatCoincidenceAsInterference=False,
             TreatSubAssembliesAsComponents=True,
             IncludeMultibodyPartInterferences=True,
             MakeInterferingPartsTransparent=False,
             ShowIgnoredInterferences=False, UseSelectedComponents=False)
        coarse = _collect(mgr, log, "TOP_LEVEL")

        # stage 2: expand the flagged arm pairs to leaf parts.
        # NOTE: IInterferenceDetectionMgr on this build refuses
        # UseSelectedComponents (IDM_PROP_SKIP), so the expansion cannot be
        # restricted to one pair -- it is a whole-assembly leaf run, recorded
        # as such.  It is only performed when stage 1 flags the arm, because a
        # whole-assembly leaf run is what exhausted memory before.
        detail, expanded = [], []
        arm_flagged = [c for c in coarse if any(is_arm(l) for l in c["leaves"])]
        if arm_flagged:
            _set(mgr, log, TreatSubAssembliesAsComponents=False)
            detail = _collect(mgr, log, "LEAF_WHOLE_ASSEMBLY")
            expanded.append({"trigger_pairs": [c["leaves"] for c in
                                               arm_flagged],
                             "status": "EXPANDED_WHOLE_ASSEMBLY",
                             "restricted_to_pair": False,
                             "why": ("UseSelectedComponents is not settable on "
                                     "this SolidWorks build"),
                             "leaf_pairs": len(detail)})
            _set(mgr, log, TreatSubAssembliesAsComponents=True)

        C.swc.close_document(app, top, blog)
        return {"status": "MEASURED", "live_top": live_top,
                "suppressed_top": sorted(supp_top),
                "coarse": coarse, "detail": detail, "expanded": expanded}

    return C.with_retry(log, "r2b3_%s" % cname, body, attempts=2), log


def main():
    cname = sys.argv[1]
    rec = {"configuration": cname, "schema": "F3R2_G3A_CHUNK_V2"}
    try:
        out, log = measure(cname)
        rec.update(out)
        rows = []
        for src in ("coarse", "detail"):
            for c in rec.get(src, []) or []:
                leaves = c["leaves"]
                named = [l for l in leaves if l != "UNNAMED_BY_API"]
                excl = None
                if not named:
                    # The API refused to name the components.  An unnamed pair
                    # must NOT be excluded as a self-pair -- "we don't know
                    # what these are" is not "these are the same part".
                    excl = None
                    kind = "UNIDENTIFIED_BY_API"
                elif any(is_reference_only(l) for l in named):
                    excl = "REFERENCE_OR_ENVELOPE_BODY"
                    kind = "REFERENCE_ONLY"
                elif len(leaves) >= 2 and leaves[0] == leaves[1]:
                    excl = "SAME_COMPONENT_SELF_PAIR"
                    kind = "PHYSICAL"
                elif any(l in rec.get("suppressed_top", []) for l in named):
                    excl = "SUPPRESSED_COMPONENT"
                    kind = "PHYSICAL"
                else:
                    kind = "PHYSICAL"
                rows.append({
                    "configuration": cname, "stage": c["stage"],
                    "component_a": leaves[0] if leaves else "",
                    "component_b": leaves[1] if len(leaves) > 1 else "",
                    "volume_mm3": c["volume_mm3"],
                    "centroid_mm": c["centroid_mm"],
                    "faces": "NOT_PROVIDED_BY_API",
                    "involves_arm": any(is_arm(l) for l in named),
                    "identification": kind,
                    "component_kind_a": ("REFERENCE_ONLY"
                                         if leaves and
                                         is_reference_only(leaves[0])
                                         else kind),
                    "component_kind_b": ("REFERENCE_ONLY"
                                         if len(leaves) > 1
                                         and is_reference_only(leaves[1])
                                         else kind),
                    "in_mass_collision_bom": excl is None,
                    "excluded_reason": excl or "",
                    "counts_as_real": excl is None,
                    "full_a": c["components"][0] if c["components"] else "",
                    "full_b": (c["components"][1]
                               if len(c["components"]) > 1 else "")})
        rec["rows"] = rows
        real = [r for r in rows if r["counts_as_real"]]
        arm = [r for r in real if r["involves_arm"]]
        unid = [r for r in rows if r["identification"] == "UNIDENTIFIED_BY_API"]
        stage1 = [c for c in rec.get("coarse", []) or []]
        arm_named = any(is_arm(l) for c in stage1 for l in c["leaves"]
                        if l != "UNNAMED_BY_API")
        # If the API refused to name components, "arm pairs = 0" is NOT
        # evidence that the arm is clear -- it only means we could not tell.
        if unid:
            arm_verdict = "CANNOT_DETERMINE_COMPONENTS_UNNAMED_BY_API"
        elif arm_named:
            arm_verdict = "ARM_PAIRS_PRESENT"
        else:
            arm_verdict = "ARM_PAIRS_ZERO"
        rec["summary"] = {
            "status": "MEASURED",
            "count_top_level_raw": len(stage1),
            "count_leaf_raw": len(rec.get("detail", []) or []),
            "count_real": len(real),
            "count_pairs_naming_arm": len(arm),
            "count_unidentified_by_api": len(unid),
            "arm_involvement_verdict": arm_verdict,
            "arm_volume_mm3": round(sum(r["volume_mm3"] or 0 for r in arm), 6),
            "total_volume_mm3": round(sum(r["volume_mm3"] or 0
                                          for r in real), 6),
            "stage2_expanded": rec.get("expanded", []),
            "component_naming": (
                "UNAVAILABLE -- IInterference.GetComponents raises on this "
                "SolidWorks 2024 install, both early-bound (makepy) and "
                "late-bound (IDispatch); only Volume and GetComponentCount "
                "are reachable" if unid else "OK"),
            "live_top": rec.get("live_top"),
            "suppressed_top": rec.get("suppressed_top")}
    except Exception as exc:
        rec["summary"] = {"status": "CANNOT_EVALUATE",
                          "reason": str(exc)[:200]}
        rec["traceback"] = traceback.format_exc()[-1500:]
        rec["rows"] = []

    jr = json.loads(JOURNAL.read_text(encoding="utf-8")) \
        if JOURNAL.is_file() else {}
    jr[cname] = {"summary": rec["summary"], "rows": rec["rows"]}
    C.write_json(JOURNAL, jr)
    s = rec["summary"]
    print("\n%-32s %s" % (cname, s.get("status")))
    if s.get("status") == "MEASURED":
        print("   top-level pairs=%s  leaf pairs=%s  real=%s  vol=%s mm3"
              % (s["count_top_level_raw"], s["count_leaf_raw"],
                 s["count_real"], s["total_volume_mm3"]))
        print("   arm involvement: %s   (unidentified pairs: %s)"
              % (s["arm_involvement_verdict"],
                 s["count_unidentified_by_api"]))
        for r in rec["rows"][:12]:
            print("      %-10s %12s mm3  %-30s <-> %-30s real=%s %s"
                  % (r["stage"][:10], r["volume_mm3"], r["component_a"][:30],
                     r["component_b"][:30], r["counts_as_real"],
                     r["excluded_reason"]))
    else:
        print("   reason:", s.get("reason"))
    sys.exit(0 if s.get("status") in ("MEASURED", "CONFIG_ABSENT") else 1)


if __name__ == "__main__":
    main()
