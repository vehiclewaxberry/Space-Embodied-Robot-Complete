r"""Phase C1 round 2 - after all round-1 candidates failed.

WHY ROUND 1 WAS INSUFFICIENT (honest correction of my own probe design):

  makepy emits both inverse members with wFlags=1:
      IInverse -> InvokeTypes(10, LCID, 1, (9,0), (),)
      Inverse  -> InvokeTypes( 9, LCID, 1, (9,0), (),)
  and pythoncom.DISPATCH_METHOD == 1. So round-1 candidates C5/C6 ("explicit
  DISPATCH_METHOD instead of makepy wFlags=1") were byte-identical to C1/C2.
  Round 1 therefore tested 4 distinct paths, not 6, and never once tested
  DISPATCH_PROPERTYGET - even though the SolidWorks error is literally
  61836 "cannot read write-only property", which is property-flavoured.

  Round-1 result that still stands and is informative:
      C4 (late-bound "Inverse") failed with -2147352573 DISP_E_MEMBERNOTFOUND,
      a DIFFERENT error from every other candidate. So the late-bound name
      "Inverse" does not exist at all, while every path that genuinely reaches
      dispid 9 or 10 gets 61836 from inside SolidWorks. The defect is in the
      SolidWorks member, not in how Python binds to it.

ROUND 2 TESTS TWO GENUINELY NEW FAMILIES:

  D1-D5  invocation-FLAG variants (PROPERTYGET / METHOD|PROPERTYGET / raw
         Invoke). These are the real untested hypothesis.

  D6a/D6b  NUMERICAL inverse, bypassing the broken member entirely. In this very
         session CreateTransform round-tripped with drift 0.0, and IMultiply and
         ArrayData both work. For a rigid transform that is sufficient to build
         the inverse in Python and hand it back to SolidWorks. Crucially this is
         SELF-VALIDATING: the result is checked with inv(T) x T = I using
         SolidWorks' own working IMultiply, so a wrong storage-order assumption
         shows up as a large residual rather than as a silent bad answer.

Attach-only, read-only, opens no documents, mutates nothing.
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
    "LOOP1E_IINVERSE_PROBE_ROUND2_RECEIPT.json",
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


def value(member):
    return member() if callable(member) else member


def identity_residual(values: list[float]) -> float:
    rot = values[0:9]
    trans = values[9:12]
    ident = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
    return max(
        max(abs(a - b) for a, b in zip(rot, ident)),
        max(abs(t) for t in trans),
    )


def numerical_rigid_inverse(vals: list[float], translation_convention: str) -> list[float]:
    """Build the inverse of a rigid SolidWorks ArrayData transform in pure Python.

    Layout: vals[0:9] rotation, vals[9:12] translation, vals[12] scale, vals[13:16] unused.

    The 3x3 transpose is convention-agnostic: for flat index i*3+j, transposing
    means new[i*3+j] = old[j*3+i] whether the block is read row- or column-major.
    Only the translation term depends on the convention, so both are offered and
    the caller picks the one that IMultiply confirms.
    """
    rot = vals[0:9]
    trans = vals[9:12]
    scale = vals[12]
    if abs(scale - 1.0) > 1.0e-12:
        raise ValueError(f"non-unit scale {scale} - rigid inverse formula does not apply")

    rt = [rot[j * 3 + i] for i in range(3) for j in range(3)]  # transpose

    if translation_convention == "A":
        inv_t = [-sum(rt[i * 3 + j] * trans[j] for j in range(3)) for i in range(3)]
    elif translation_convention == "B":
        inv_t = [-sum(rt[j * 3 + i] * trans[j] for j in range(3)) for i in range(3)]
    else:
        raise ValueError(translation_convention)

    return rt + inv_t + [1.0, 0.0, 0.0, 0.0]


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

    report: dict = {
        "schema": "V5R_LOOP1E_IINVERSE_PROBE_ROUND2_RECEIPT_V1",
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "solidworks_revision": revision,
        "document_count_at_probe": doc_count,
        "attach_only": True,
        "documents_opened_by_probe": 0,
        "round1_design_defect_acknowledged": (
            "round-1 C5/C6 used pythoncom.DISPATCH_METHOD (==1), identical to makepy's "
            "own wFlags=1, so they duplicated C1/C2 and DISPATCH_PROPERTYGET went untested"
        ),
        "dispatch_flag_constants": {
            "DISPATCH_METHOD": int(pythoncom.DISPATCH_METHOD),
            "DISPATCH_PROPERTYGET": int(pythoncom.DISPATCH_PROPERTYGET),
        },
        "candidates": [],
    }

    math_util = wrap(value(sw.GetMathUtility), "IMathUtility")
    array_variant = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, ARRAY16)
    t_raw = math_util.CreateTransform(array_variant)
    if t_raw is None:
        report["fatal"] = "CreateTransform returned null"
        _write(report)
        return 1
    T = wrap(t_raw, "IMathTransform")

    source_vals = [float(v) for v in list(value(T.ArrayData))]
    creation_drift = max(abs(a - b) for a, b in zip(source_vals, ARRAY16))
    report["created_transform_max_drift"] = creation_drift
    if creation_drift > 1.0e-12:
        report["fatal"] = f"CreateTransform round-trip drift {creation_drift}"
        report["verdict"] = "PROBE_ABORTED_CREATE_TRANSFORM_CORRUPTED"
        _write(report)
        return 1
    print(f"test transform verified (drift {creation_drift:.3e}), SW {revision}, docs={doc_count}")
    print(f"DISPATCH_METHOD={int(pythoncom.DISPATCH_METHOD)} "
          f"DISPATCH_PROPERTYGET={int(pythoncom.DISPATCH_PROPERTYGET)}")
    print("probing round-2 inverse paths:")

    def record(name, family, note, fn):
        entry = {"candidate": name, "family": family, "note": note}
        try:
            inv_obj = fn()
            if inv_obj is None:
                entry.update(ok=False, error="returned null")
            else:
                inv = wrap(inv_obj, "IMathTransform")
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
        if entry.get("ok"):
            extra = f"residual={entry.get('identity_residual'):.3e} true_inverse={entry.get('is_true_inverse')}"
        else:
            extra = str(entry.get("error", ""))[:105]
        print(f"  [{flag}] {name:38s} {extra}")

    PROPGET = pythoncom.DISPATCH_PROPERTYGET
    METHOD = pythoncom.DISPATCH_METHOD

    record("D1_InvokeTypes_PROPERTYGET_dispid10", "flags",
           "the actual untested hypothesis: dispid 10 as a property get",
           lambda: T._oleobj_.InvokeTypes(10, 0, PROPGET, (9, 0), ()))

    record("D2_InvokeTypes_PROPERTYGET_dispid9", "flags",
           "dispid 9 as a property get",
           lambda: T._oleobj_.InvokeTypes(9, 0, PROPGET, (9, 0), ()))

    record("D3_InvokeTypes_METHOD_OR_PROPGET_dispid10", "flags",
           "let the server choose: METHOD|PROPERTYGET on dispid 10",
           lambda: T._oleobj_.InvokeTypes(10, 0, METHOD | PROPGET, (9, 0), ()))

    record("D4_InvokeTypes_METHOD_OR_PROPGET_dispid9", "flags",
           "METHOD|PROPERTYGET on dispid 9",
           lambda: T._oleobj_.InvokeTypes(9, 0, METHOD | PROPGET, (9, 0), ()))

    record("D5_raw_Invoke_PROPERTYGET_dispid9", "flags",
           "low-level Invoke rather than InvokeTypes, dispid 9 property get",
           lambda: T._oleobj_.Invoke(9, 0, PROPGET, True))

    # --- numerical family: bypasses the broken member completely -------------
    def make_numerical(convention):
        def build():
            inv_vals = numerical_rigid_inverse(source_vals, convention)
            variant = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, inv_vals)
            built = math_util.CreateTransform(variant)
            if built is None:
                raise RuntimeError("CreateTransform(inverse) returned null")
            return built
        return build

    record("D6a_numerical_inverse_conventionA", "numerical",
           "R^T with inv_t = -R^T t (row-vector convention); verified by SolidWorks IMultiply",
           make_numerical("A"))

    record("D6b_numerical_inverse_conventionB", "numerical",
           "R^T with inv_t = -R t (column-vector convention); verified by SolidWorks IMultiply",
           make_numerical("B"))

    working = [c for c in report["candidates"] if c.get("ok") and c.get("is_true_inverse")]
    report["working_candidate_count"] = len(working)
    flag_winners = [c for c in working if c["family"] == "flags"]
    numerical_winners = [c for c in working if c["family"] == "numerical"]
    report["working_flag_candidates"] = [c["candidate"] for c in flag_winners]
    report["working_numerical_candidates"] = [c["candidate"] for c in numerical_winners]
    # prefer a flag fix: it keeps the change to a single call, no new arithmetic
    # in the trusted path. Fall back to numerical only if no flag path works.
    report["recommended_candidate"] = (
        flag_winners[0]["candidate"] if flag_winners
        else (numerical_winners[0]["candidate"] if numerical_winners else None)
    )
    report["recommendation_basis"] = (
        "flag-family preferred: single-call change, no new arithmetic introduced into the "
        "transform path" if flag_winners else
        "no flag path works; numerical inverse is the remaining route and is validated "
        "against SolidWorks' own IMultiply" if numerical_winners else
        "nothing worked"
    )
    report["verdict"] = (
        "IINVERSE_REPLACEMENT_PATH_FOUND" if working else "NO_WORKING_INVERSE_PATH_FOUND_ESCALATE"
    )
    _write(report)
    print(f"\nverdict: {report['verdict']}")
    print(f"recommended: {report['recommended_candidate']}")
    print(f"basis: {report['recommendation_basis']}")
    return 0 if working else 1


def _write(report: dict) -> None:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, ensure_ascii=False)
    print(f"receipt: {OUT}")


if __name__ == "__main__":
    sys.exit(main())
