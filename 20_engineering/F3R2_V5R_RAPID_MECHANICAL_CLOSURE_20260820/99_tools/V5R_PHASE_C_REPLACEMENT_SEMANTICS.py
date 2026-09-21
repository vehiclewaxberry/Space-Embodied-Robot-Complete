r"""Phase C2 pre-patch verification - prove the replacement chain is not just
callable but MATHEMATICALLY IDENTICAL to what the broken chain intended.

Step isolation (LOOP1E_STEP_ISOLATION_RECEIPT.json) established:

    dispid 10  IInverse   FAIL 61836     dispid 9  Inverse   OK
    dispid  2  IMultiply  FAIL 61836     dispid 1  Multiply  OK

so the I-prefixed members are not invocable through IDispatch on this build
while their non-prefixed siblings are. The patch will swap both.

BUT Multiply (dispid 1) is a DIFFERENT MEMBER from IMultiply (dispid 2), not an
alias, and relative_transform() feeds expected_link6_to_gripper_transform_16 -
a motion-contract value. If Multiply composed in the opposite order, the script
would keep running and silently emit wrong relative transforms, which is far
worse than the current crash. So before patching, verify:

  V1  inv(A).Multiply(A) == I                      (round trip, owner smoke test S1)
  V2  inv(A).Multiply(B) == A^-1 B  numerically    (composition ORDER is unchanged)
  V3  which ArrayData storage layout is real       (settles the open question that
                                                    round-2 D6a/D6b could not answer)

V2 is the load-bearing one: it compares SolidWorks' own answer against an
independently computed 4x4 product, so a reversed convention shows up as a
large residual instead of a plausible wrong number.

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
    "LOOP1E_REPLACEMENT_SEMANTICS_RECEIPT.json",
)

C30, S30 = 0.8660254037844387, 0.49999999999999994
C45, S45 = 0.7071067811865476, 0.7071067811865475

# A: 30 deg about Z, translation (0.1, -0.2, 0.3)
A16 = [C30, S30, 0.0, -S30, C30, 0.0, 0.0, 0.0, 1.0, 0.1, -0.2, 0.3, 1.0, 0.0, 0.0, 0.0]
# B: 45 deg about X, translation (-0.05, 0.4, 0.15) - deliberately unrelated to A
B16 = [1.0, 0.0, 0.0, 0.0, C45, S45, 0.0, -S45, C45, -0.05, 0.4, 0.15, 1.0, 0.0, 0.0, 0.0]


def value(member):
    return member() if callable(member) else member


def to_mat4(vals: list[float], layout: str) -> list[list[float]]:
    """16-value SolidWorks ArrayData -> homogeneous 4x4, under a stated layout."""
    r = vals[0:9]
    t = vals[9:12]
    if layout == "row":
        rot = [[r[0], r[1], r[2]], [r[3], r[4], r[5]], [r[6], r[7], r[8]]]
    elif layout == "col":
        rot = [[r[0], r[3], r[6]], [r[1], r[4], r[7]], [r[2], r[5], r[8]]]
    else:
        raise ValueError(layout)
    return [
        [rot[0][0], rot[0][1], rot[0][2], t[0]],
        [rot[1][0], rot[1][1], rot[1][2], t[1]],
        [rot[2][0], rot[2][1], rot[2][2], t[2]],
        [0.0, 0.0, 0.0, 1.0],
    ]


def from_mat4(m: list[list[float]], layout: str) -> list[float]:
    rot = [[m[i][j] for j in range(3)] for i in range(3)]
    t = [m[0][3], m[1][3], m[2][3]]
    if layout == "row":
        flat = [rot[0][0], rot[0][1], rot[0][2], rot[1][0], rot[1][1], rot[1][2], rot[2][0], rot[2][1], rot[2][2]]
    else:
        flat = [rot[0][0], rot[1][0], rot[2][0], rot[0][1], rot[1][1], rot[2][1], rot[0][2], rot[1][2], rot[2][2]]
    return flat + t + [1.0, 0.0, 0.0, 0.0]


def matmul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def inv4(m: list[list[float]]) -> list[list[float]]:
    """General 4x4 inverse by Gauss-Jordan - no rigidity assumption."""
    n = 4
    aug = [list(m[i]) + [1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1e-14:
            raise ValueError("singular matrix")
        aug[col], aug[pivot] = aug[pivot], aug[col]
        pv = aug[col][col]
        aug[col] = [v / pv for v in aug[col]]
        for row in range(n):
            if row != col and aug[row][col] != 0.0:
                f = aug[row][col]
                aug[row] = [rv - f * cv for rv, cv in zip(aug[row], aug[col])]
    return [row[n:] for row in aug]


def max_abs_diff(x: list[float], y: list[float]) -> float:
    return max(abs(a - b) for a, b in zip(x, y))


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
        return klass(source.QueryInterface(klass.CLSID, pythoncom.IID_IDispatch))

    sw = wrap(raw, "ISldWorks")
    revision = str(value(sw.RevisionNumber))
    doc_count = int(value(sw.GetDocumentCount))
    math_util = wrap(value(sw.GetMathUtility), "IMathUtility")

    def make(vals):
        v = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, vals)
        obj = math_util.CreateTransform(v)
        if obj is None:
            raise RuntimeError("CreateTransform returned null")
        return wrap(obj, "IMathTransform")

    def read(t):
        return [float(x) for x in list(value(t.ArrayData))]

    report: dict = {
        "schema": "V5R_LOOP1E_REPLACEMENT_SEMANTICS_RECEIPT_V1",
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "purpose": "prove Inverse(dispid 9)+Multiply(dispid 1) reproduce the intended "
                   "IInverse+IMultiply semantics before any patch is applied",
        "solidworks_revision": revision,
        "document_count_at_probe": doc_count,
        "attach_only": True,
        "documents_opened_by_probe": 0,
        "source_A16": A16,
        "source_B16": B16,
    }
    print(f"SolidWorks {revision}, docs={doc_count}")

    A = make(A16)
    B = make(B16)
    a_read, b_read = read(A), read(B)
    report["A_creation_drift"] = max_abs_diff(a_read, A16)
    report["B_creation_drift"] = max_abs_diff(b_read, B16)
    if max(report["A_creation_drift"], report["B_creation_drift"]) > 1e-12:
        report["verdict"] = "ABORT_CREATE_TRANSFORM_DRIFT"
        return _write(report, 1)
    print(f"inputs verified (drift {report['A_creation_drift']:.1e}, {report['B_creation_drift']:.1e})")

    # ---- the replacement chain, exactly as the patch will call it -----------
    inv_raw = A.Inverse()
    if inv_raw is None:
        report["verdict"] = "ABORT_INVERSE_RETURNED_NULL"
        return _write(report, 1)
    invA = wrap(inv_raw, "IMathTransform")
    inv_vals = read(invA)
    report["inverse_of_A_array16"] = inv_vals

    # V1 - round trip inv(A) * A == I  (owner smoke test S1)
    rt_raw = invA.Multiply(A)
    if rt_raw is None:
        report["verdict"] = "ABORT_MULTIPLY_RETURNED_NULL"
        return _write(report, 1)
    rt = read(wrap(rt_raw, "IMathTransform"))
    ident16 = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
    v1 = max_abs_diff(rt, ident16)
    report["V1_round_trip"] = {
        "product_array16": rt,
        "max_deviation_from_identity": v1,
        "tolerance": 1e-12,
        "pass": v1 < 1e-12,
    }
    print(f"V1 round trip  inv(A)*A vs I : {v1:.3e}  {'PASS' if v1 < 1e-12 else 'FAIL'}")

    # V2 - composition ORDER: inv(A).Multiply(B) vs an independent A^-1 B
    comp_raw = invA.Multiply(B)
    if comp_raw is None:
        report["verdict"] = "ABORT_COMPOSITION_RETURNED_NULL"
        return _write(report, 1)
    comp = read(wrap(comp_raw, "IMathTransform"))
    report["V2_solidworks_composition_array16"] = comp

    hypotheses = {}
    for layout in ("row", "col"):
        MA, MB = to_mat4(a_read, layout), to_mat4(b_read, layout)
        MAi = inv4(MA)
        for order, prod in (("invA_times_B", matmul(MAi, MB)), ("B_times_invA", matmul(MB, MAi))):
            hypotheses[f"{layout}|{order}"] = max_abs_diff(from_mat4(prod, layout), comp)
    report["V2_hypothesis_residuals"] = hypotheses
    best = min(hypotheses, key=hypotheses.get)
    report["V2_best_match"] = {"hypothesis": best, "residual": hypotheses[best]}
    v2_pass = hypotheses[best] < 1e-12 and best.endswith("invA_times_B")
    report["V2_composition_order_preserved"] = v2_pass
    for k, v in sorted(hypotheses.items(), key=lambda kv: kv[1]):
        print(f"V2 {k:26s} residual {v:.3e}")
    print(f"V2 best = {best}  -> order preserved: {v2_pass}")

    # V3 - which storage layout is real (settles the round-2 open question)
    report["V3_storage_layout"] = best.split("|")[0] if hypotheses[best] < 1e-12 else "UNRESOLVED"

    all_pass = report["V1_round_trip"]["pass"] and v2_pass
    report["verdict"] = (
        "REPLACEMENT_SEMANTICS_VERIFIED_SAFE_TO_PATCH" if all_pass
        else "REPLACEMENT_SEMANTICS_NOT_EQUIVALENT_DO_NOT_PATCH"
    )
    report["interpretation"] = (
        "Inverse(dispid 9) and Multiply(dispid 1) reproduce the intended IInverse/IMultiply "
        "semantics exactly, including composition order. Swapping both call sites changes no "
        "engineering value." if all_pass else
        "the non-prefixed members do NOT reproduce the intended semantics; patching them in "
        "would silently corrupt relative transforms. Escalate instead of patching."
    )
    print(f"\nverdict: {report['verdict']}")
    return _write(report, 0 if all_pass else 1)


def _write(report: dict, code: int) -> int:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, ensure_ascii=False)
    print(f"receipt: {OUT}")
    return code


if __name__ == "__main__":
    sys.exit(main())
