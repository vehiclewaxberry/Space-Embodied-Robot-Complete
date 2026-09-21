r"""Phase C probe - find a working inverse path for IMathTransform on this install.

Root cause (established from the makepy module, no SolidWorks needed):

  IInverse  -> self._oleobj_.InvokeTypes(10, LCID, 1, (9,0), (),)   <-- DISPID 10, FAILS 61836
  Inverse   -> self._oleobj_.InvokeTypes( 9, LCID, 1, (9,0), (),)   <-- DISPID 9,  UNTESTED
  IMultiply -> self._oleobj_.InvokeTypes( 2, ...)                    <-- DISPID 2,  WORKS today

So the COM layer is fine; a single DISPID is being rejected as a write-only
property on this SW2024 SP5 install. Four candidate paths are ranked cheapest
-first. The probe reports which ones return a usable transform and whether the
result is numerically a true inverse; it does NOT patch anything.

Requires an already-running, document-empty SolidWorks session (attach-only,
same discipline as the Loop1 helpers). Opens one throwaway assembly? No - it
needs no document at all: MathUtility can build transforms from raw data.

Usage:
  python V5R_PHASE_C_IINVERSE_PROBE.py
"""

from __future__ import annotations

import json
import os
import sys
import datetime as dt

# braces are REQUIRED: gencache.GetGeneratedFileName does clsid[1:-1] assuming
# "{...}", so a brace-less GUID silently loses its first and last characters and
# GetModuleForTypelib fails on a mangled module name. Matches SW_TLB in
# F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY.py:59 exactly.
SW_TLB = ("{83A33D31-27C5-11CE-BFD4-00400513BB57}", 0, 32, 0)
SW_PROG_ID = "SldWorks.Application"
OUT = os.path.join(
    r"F:\China Graduate Future Flight Vehicle Innovation Competition",
    r"20_engineering\F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820\04_validation",
    "LOOP1E_IINVERSE_PROBE_RECEIPT.json",
)

# a deliberately non-trivial rigid transform: 30 deg about Z, translation (0.1, -0.2, 0.3)
COS30, SIN30 = 0.8660254037844387, 0.49999999999999994
ARRAY16 = [
    COS30, SIN30, 0.0,
    -SIN30, COS30, 0.0,
    0.0, 0.0, 1.0,
    0.1, -0.2, 0.3,
    1.0,
    0.0, 0.0, 0.0,
]


def value(member):
    """Normalise typelib members that arrive as bound methods (cf. base.value())."""
    return member() if callable(member) else member


def identity_residual(values: list[float]) -> float:
    """max |M - I| over the 3x3 rotation block and the translation triple."""
    rot = values[0:9]
    trans = values[9:12]
    ident = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
    return max(
        max(abs(a - b) for a, b in zip(rot, ident)),
        max(abs(t) for t in trans),
    )


def main() -> int:
    import pythoncom
    import win32com.client
    from win32com.client import gencache, dynamic, VARIANT

    pythoncom.CoInitialize()
    types = gencache.GetModuleForTypelib(*SW_TLB)
    raw = win32com.client.GetActiveObject(SW_PROG_ID)

    def wrap(obj, interface):
        klass = getattr(types, interface)
        # candidates C5/C6 return a bare PyIDispatch from InvokeTypes, which has no
        # _oleobj_ attribute - it IS the oleobj. Without this branch those two would
        # raise AttributeError and be recorded as false failures.
        source = getattr(obj, "_oleobj_", obj)
        ole = source.QueryInterface(klass.CLSID, pythoncom.IID_IDispatch)
        return klass(ole)

    sw = wrap(raw, "ISldWorks")
    revision = str(value(sw.RevisionNumber))
    doc_count = int(value(sw.GetDocumentCount))

    report: dict = {
        "schema": "V5R_LOOP1E_IINVERSE_PROBE_RECEIPT_V1",
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "solidworks_revision": revision,
        "document_count_at_probe": doc_count,
        "attach_only": True,
        "documents_opened_by_probe": 0,
        "source_array16": ARRAY16,
        "candidates": [],
    }

    math_util = wrap(value(sw.GetMathUtility), "IMathUtility")

    # KNOWN TRAP (project memory f3r1-stow-pose-com-traps-2026-08): handing
    # CreateTransform a bare Python list SILENTLY CORRUPTS non-identity
    # transforms. Our test transform is deliberately non-identity, so the array
    # must be marshalled as an explicit VT_ARRAY|VT_R8 VARIANT.
    array_variant = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, ARRAY16)
    t_raw = math_util.CreateTransform(array_variant)
    if t_raw is None:
        report["fatal"] = "CreateTransform returned null"
        _write(report)
        return 1
    T = wrap(t_raw, "IMathTransform")

    # Guard the trap rather than trusting the fix: read the transform back and
    # confirm it is what we asked for. A corrupted T would make every downstream
    # residual meaningless, so this aborts instead of reporting a bogus winner.
    readback = [float(v) for v in list(value(T.ArrayData))]
    creation_drift = max(abs(a - b) for a, b in zip(readback, ARRAY16))
    report["created_transform_readback"] = readback
    report["created_transform_max_drift"] = creation_drift
    if creation_drift > 1.0e-12:
        report["fatal"] = (
            f"CreateTransform round-trip drift {creation_drift} exceeds 1e-12 - the "
            "known bare-list corruption trap is still active despite VARIANT marshalling; "
            "no candidate result would be trustworthy"
        )
        report["verdict"] = "PROBE_ABORTED_CREATE_TRANSFORM_CORRUPTED"
        _write(report)
        print(f"FATAL: {report['fatal']}")
        return 1
    print(f"test transform verified, creation drift {creation_drift:.3e}")

    def record(name, dispid, note, fn):
        entry = {"candidate": name, "dispid": dispid, "note": note}
        try:
            inv_raw = fn()
            if inv_raw is None:
                entry.update(ok=False, error="returned null")
            else:
                inv = wrap(inv_raw, "IMathTransform")
                prod_raw = inv.IMultiply(T)
                if prod_raw is None:
                    entry.update(ok=False, error="IMultiply(inverse, T) returned null")
                else:
                    prod = wrap(prod_raw, "IMathTransform")
                    vals = [float(v) for v in list(value(prod.ArrayData))]
                    res = identity_residual(vals)
                    entry.update(
                        ok=True,
                        product_array16=vals,
                        identity_residual=res,
                        is_true_inverse=res < 1.0e-12,
                    )
        except Exception as exc:  # noqa: BLE001 - probe records every failure mode
            entry.update(ok=False, error=f"{type(exc).__name__}: {exc}")
        report["candidates"].append(entry)
        flag = "OK " if entry.get("ok") else "FAIL"
        extra = f"residual={entry.get('identity_residual')}" if entry.get("ok") else entry.get("error", "")[:110]
        print(f"  [{flag}] {name:34s} {extra}")

    print(f"SolidWorks {revision}, docs={doc_count}")
    print("probing inverse paths:")

    # C1 - the current, failing call. Recorded to prove the defect reproduces.
    record("C1_static_IInverse", 10, "current code path, expected to fail 61836",
           lambda: T.IInverse())

    # C2 - sibling member at a different DISPID, same makepy binding style.
    record("C2_static_Inverse", 9, "different DISPID, same static binding",
           lambda: T.Inverse())

    # C3 - late-bound dynamic dispatch: the precedent that fixed IMateEntity2.Reference.
    def c3():
        dyn = dynamic.Dispatch(T._oleobj_.QueryInterface(pythoncom.IID_IDispatch))
        return dyn.IInverse()
    record("C3_late_bound_IInverse", 10, "dynamic dispatch, project precedent (accessor A2)", c3)

    def c4():
        dyn = dynamic.Dispatch(T._oleobj_.QueryInterface(pythoncom.IID_IDispatch))
        return dyn.Inverse()
    record("C4_late_bound_Inverse", 9, "dynamic dispatch on the DISPID 9 sibling", c4)

    # C5 - raw InvokeTypes with METHOD-only flags, bypassing makepy's wFlags=1.
    def c5():
        return T._oleobj_.InvokeTypes(10, 0, pythoncom.DISPATCH_METHOD, (9, 0), ())
    record("C5_raw_InvokeTypes_METHOD_dispid10", 10, "explicit DISPATCH_METHOD instead of makepy wFlags=1", c5)

    def c6():
        return T._oleobj_.InvokeTypes(9, 0, pythoncom.DISPATCH_METHOD, (9, 0), ())
    record("C6_raw_InvokeTypes_METHOD_dispid9", 9, "explicit DISPATCH_METHOD on DISPID 9", c6)

    working = [c for c in report["candidates"] if c.get("ok") and c.get("is_true_inverse")]
    report["working_candidate_count"] = len(working)
    report["recommended_candidate"] = working[0]["candidate"] if working else None
    report["defect_reproduced"] = any(
        c["candidate"] == "C1_static_IInverse" and not c.get("ok") for c in report["candidates"]
    )
    report["verdict"] = (
        "IINVERSE_REPLACEMENT_PATH_FOUND" if working else "NO_WORKING_INVERSE_PATH_FOUND_ESCALATE"
    )
    _write(report)
    print(f"\nverdict: {report['verdict']}")
    print(f"recommended: {report['recommended_candidate']}")
    return 0 if working else 1


def _write(report: dict) -> None:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, ensure_ascii=False)
    print(f"receipt: {OUT}")


if __name__ == "__main__":
    sys.exit(main())
