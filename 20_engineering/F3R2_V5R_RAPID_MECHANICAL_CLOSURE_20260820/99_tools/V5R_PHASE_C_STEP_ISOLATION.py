r"""Phase C1 round 3 - STEP ISOLATION. Find out which COM call actually raises 61836.

Round 2 produced a result that breaks the whole prior root-cause story:

  D6a/D6b (numerical inverse) ALSO failed with 61836 - yet they never call
  IInverse or Inverse at all. They only use CreateTransform, IMultiply and
  ArrayData. Therefore 61836 is NOT coming from the inverse member.

This also retires a premise I asserted earlier and never actually verified.
LOOP1E_IINVERSE_PATCH_DESIGN.json claims:

  "IMultiply ... WORKS - called successfully on the same object at line 2617"

That was inferred from reading the source, not observed. It cannot be true:
production raised at line 2613, so line 2617 was never reached in that run. The
claim should never have been recorded as a finding.

Rounds 1 and 2 both wrapped the whole chain in a single try/except, so neither
could attribute the error to a specific call. This round isolates every COM call
behind its own try/except and reports each independently. No fix is proposed
until the failing member is identified by observation.

Attach-only, read-only, opens no documents.
"""
from __future__ import annotations

import json
import os
import sys
import datetime as dt

SW_TLB = ("{83A33D31-27C5-11CE-BFD4-00400513BB57}", 0, 32, 0)
SW_PROG_ID = "SldWorks.Application"
OUT = os.path.join(
    r"F:\China Graduate Future Flight Vehicle Innovation Competition",
    r"20_engineering\F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820\04_validation",
    "LOOP1E_STEP_ISOLATION_RECEIPT.json",
)

COS30, SIN30 = 0.8660254037844387, 0.49999999999999994
ARRAY16 = [
    COS30, SIN30, 0.0,
    -SIN30, COS30, 0.0,
    0.0, 0.0, 1.0,
    0.1, -0.2, 0.3,
    1.0,
    0.0, 0.0, 0.0,
]
IDENTITY16 = [
    1.0, 0.0, 0.0,
    0.0, 1.0, 0.0,
    0.0, 0.0, 1.0,
    0.0, 0.0, 0.0,
    1.0,
    0.0, 0.0, 0.0,
]

steps: list[dict] = []


def value(member):
    return member() if callable(member) else member


def step(name, note, fn):
    """Run one isolated COM call. Returns (ok, result)."""
    entry = {"step": name, "note": note}
    try:
        result = fn()
        entry["ok"] = True
        entry["result_repr"] = type(result).__name__ if result is not None else "None"
        entry["is_none"] = result is None
        steps.append(entry)
        print(f"  [OK  ] {name:44s} -> {entry['result_repr']}")
        return True, result
    except Exception as exc:  # noqa: BLE001 - isolating failure modes is the point
        entry["ok"] = False
        entry["error_type"] = type(exc).__name__
        entry["error"] = str(exc)
        entry["is_61836"] = "61836" in str(exc)
        steps.append(entry)
        marker = " <== 61836" if entry["is_61836"] else ""
        print(f"  [FAIL] {name:44s} {type(exc).__name__}: {str(exc)[:80]}{marker}")
        return False, None


def main() -> int:
    import pythoncom
    import win32com.client
    from win32com.client import gencache, VARIANT

    pythoncom.CoInitialize()
    types = gencache.GetModuleForTypelib(*SW_TLB)
    raw = win32com.client.GetActiveObject(SW_PROG_ID)

    def wrap(obj, interface):
        klass = getattr(types, interface)
        source = getattr(obj, "_oleobj_", obj)
        ole = source.QueryInterface(klass.CLSID, pythoncom.IID_IDispatch)
        return klass(ole)

    sw = wrap(raw, "ISldWorks")
    revision = str(value(sw.RevisionNumber))
    doc_count = int(value(sw.GetDocumentCount))
    print(f"SolidWorks {revision}, docs={doc_count}")
    print("isolating each COM call:")

    math_util = wrap(value(sw.GetMathUtility), "IMathUtility")

    # --- S1: build the source transform ------------------------------------
    variant_a = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, ARRAY16)
    ok, t_raw = step("S1_CreateTransform_source", "known to work in round 1/2",
                     lambda: math_util.CreateTransform(variant_a))
    if not ok or t_raw is None:
        return _finish(report_head(revision, doc_count), "ABORT_CANNOT_CREATE_SOURCE_TRANSFORM")

    ok, T = step("S2_wrap_source_QueryInterface", "QueryInterface to IMathTransform",
                 lambda: wrap(t_raw, "IMathTransform"))
    if not ok:
        return _finish(report_head(revision, doc_count), "ABORT_CANNOT_WRAP_SOURCE")

    ok, src_vals = step("S3_read_source_ArrayData", "does ArrayData work on this object?",
                        lambda: [float(v) for v in list(value(T.ArrayData))])
    if not ok:
        return _finish(report_head(revision, doc_count), "ABORT_ARRAYDATA_BROKEN_ON_SOURCE")

    # --- S4/S5: a SECOND CreateTransform object (the numerical-path shape) ---
    variant_i = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, IDENTITY16)
    ok, i_raw = step("S4_CreateTransform_identity", "second CreateTransform call in same session",
                     lambda: math_util.CreateTransform(variant_i))
    I = None
    if ok and i_raw is not None:
        ok2, I = step("S5_wrap_identity_and_read_ArrayData",
                      "ArrayData on a SECOND created transform",
                      lambda: wrap(i_raw, "IMathTransform"))
        if ok2 and I is not None:
            step("S6_read_identity_ArrayData", "confirm second object is readable",
                 lambda: [float(v) for v in list(value(I.ArrayData))])

    # --- S7..S10: the multiply family, argument-marshalling variants ---------
    step("S7_IMultiply_wrapped_arg", "T.IMultiply(T) with a makepy-wrapped argument",
         lambda: T.IMultiply(T))
    step("S8_IMultiply_raw_arg", "T.IMultiply(t_raw) with the raw dispatch argument",
         lambda: T.IMultiply(t_raw))
    step("S9_Multiply_dispid1_wrapped", "non-I variant Multiply (dispid 1), wrapped arg",
         lambda: T.Multiply(T))
    if I is not None:
        step("S10_IMultiply_identity_arg", "T.IMultiply(identity) - different argument object",
             lambda: T.IMultiply(I))

    # --- S11/S12: the inverse family, for completeness in ONE receipt --------
    step("S11_IInverse_dispid10", "the originally blamed call",
         lambda: T.IInverse())
    step("S12_Inverse_dispid9", "sibling inverse member",
         lambda: T.Inverse())

    # --- S13: IGetData2, the documented alternative decomposition route -----
    # If Multiply/Inverse are unusable, IGetData2 can still extract axes and
    # translation, from which a relative transform can be composed in Python.
    def s13():
        import win32com.client as w
        x = w.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_DISPATCH, None)
        y = w.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_DISPATCH, None)
        z = w.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_DISPATCH, None)
        t = w.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_DISPATCH, None)
        s = w.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_R8, 0.0)
        T.IGetData2(x, y, z, t, s)
        return {"scale": s.value}
    step("S13_IGetData2_decomposition", "axis/translation decomposition as an alternative route", s13)

    head = report_head(revision, doc_count)
    failing = [s for s in steps if not s.get("ok")]
    err_61836 = [s["step"] for s in steps if s.get("is_61836")]
    head["steps_total"] = len(steps)
    head["steps_failed"] = len(failing)
    head["steps_raising_61836"] = err_61836
    head["steps_ok"] = [s["step"] for s in steps if s.get("ok")]
    head["retired_unverified_claim"] = (
        "LOOP1E_IINVERSE_PATCH_DESIGN.json asserted IMultiply 'WORKS - called successfully "
        "at line 2617'. That was inferred from source, never observed, and cannot be true "
        "because production raised at line 2613. This receipt supersedes that claim with "
        "direct per-call observation."
    )
    return _finish(head, "STEP_ISOLATION_COMPLETE")


def report_head(revision, doc_count) -> dict:
    return {
        "schema": "V5R_LOOP1E_STEP_ISOLATION_RECEIPT_V1",
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "purpose": "attribute COM error 61836 to a specific member by isolating every call",
        "solidworks_revision": revision,
        "document_count_at_probe": doc_count,
        "attach_only": True,
        "documents_opened_by_probe": 0,
    }


def _finish(head: dict, verdict: str) -> int:
    head["steps"] = steps
    head["verdict"] = verdict
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(head, fh, indent=1, ensure_ascii=False)
    print(f"\nverdict: {verdict}")
    print(f"receipt: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
