r"""Phase C2 final pre-patch check - confirm the CORRECTED argument order.

V2 in LOOP1E_REPLACEMENT_SEMANTICS_RECEIPT.json established that dispid-1
Multiply is "apply left, then right":

    X.Multiply(Y)  ==  M_Y x M_X        (residual 1.11e-16, column layout)

while the code intends A^-1 B (relative transform of B expressed in A's frame).
So the naive swap invA.Multiply(B) is WRONG - it computes B A^-1, off by 0.354
on the test pair. The correct call under these semantics is:

    second_transform.Multiply(inverse)   ==  M_invA x M_B   ... no

careful: with X.Multiply(Y) == M_Y M_X, choosing X=second, Y=inverse gives
M_inverse x M_second = A^-1 B. THAT is the intended product. Verify exactly that,
against an independent 4x4 computation, before touching the production script.

Also verifies the shape guard at line 2621 will accept the result: 16 finite
values, values[12] == 1, values[13:16] == 0.

Attach-only, read-only, opens no documents.
"""
from __future__ import annotations

import json
import math
import os
import sys
import datetime as dt

SW_TLB = ("{83A33D31-27C5-11CE-BFD4-00400513BB57}", 0, 32, 0)
SW_PROG_ID = "SldWorks.Application"
OUT = os.path.join(
    r"F:\China Graduate Future Flight Vehicle Innovation Competition",
    r"20_engineering\F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820\04_validation",
    "LOOP1E_CORRECTED_ORDER_RECEIPT.json",
)

C30, S30 = 0.8660254037844387, 0.49999999999999994
C45, S45 = 0.7071067811865476, 0.7071067811865475
A16 = [C30, S30, 0.0, -S30, C30, 0.0, 0.0, 0.0, 1.0, 0.1, -0.2, 0.3, 1.0, 0.0, 0.0, 0.0]
B16 = [1.0, 0.0, 0.0, 0.0, C45, S45, 0.0, -S45, C45, -0.05, 0.4, 0.15, 1.0, 0.0, 0.0, 0.0]
# a third, asymmetric transform so the check is not accidentally satisfied by symmetry
C16 = [0.0, 1.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.7, 0.02, -0.33, 1.0, 0.0, 0.0, 0.0]


def value(m):
    return m() if callable(m) else m


def to_mat4_col(vals):
    r, t = vals[0:9], vals[9:12]
    return [
        [r[0], r[3], r[6], t[0]],
        [r[1], r[4], r[7], t[1]],
        [r[2], r[5], r[8], t[2]],
        [0.0, 0.0, 0.0, 1.0],
    ]


def from_mat4_col(m):
    return [
        m[0][0], m[1][0], m[2][0],
        m[0][1], m[1][1], m[2][1],
        m[0][2], m[1][2], m[2][2],
        m[0][3], m[1][3], m[2][3],
        1.0, 0.0, 0.0, 0.0,
    ]


def matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def inv4(m):
    n = 4
    aug = [list(m[i]) + [1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[piv][col]) < 1e-14:
            raise ValueError("singular")
        aug[col], aug[piv] = aug[piv], aug[col]
        pv = aug[col][col]
        aug[col] = [v / pv for v in aug[col]]
        for row in range(n):
            if row != col and aug[row][col] != 0.0:
                f = aug[row][col]
                aug[row] = [rv - f * cv for rv, cv in zip(aug[row], aug[col])]
    return [row[n:] for row in aug]


def mad(x, y):
    return max(abs(a - b) for a, b in zip(x, y))


def main() -> int:
    import pythoncom
    import win32com.client
    from win32com.client import gencache, VARIANT

    pythoncom.CoInitialize()
    types = gencache.GetModuleForTypelib(*SW_TLB)
    raw = win32com.client.GetActiveObject(SW_PROG_ID)

    def wrap(o, i):
        k = getattr(types, i)
        return k(getattr(o, "_oleobj_", o).QueryInterface(k.CLSID, pythoncom.IID_IDispatch))

    sw = wrap(raw, "ISldWorks")
    mu = wrap(value(sw.GetMathUtility), "IMathUtility")

    def make(v):
        o = mu.CreateTransform(VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, v))
        return wrap(o, "IMathTransform")

    def read(t):
        return [float(x) for x in list(value(t.ArrayData))]

    report = {
        "schema": "V5R_LOOP1E_CORRECTED_ORDER_RECEIPT_V1",
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "solidworks_revision": str(value(sw.RevisionNumber)),
        "document_count_at_probe": int(value(sw.GetDocumentCount)),
        "attach_only": True,
        "documents_opened_by_probe": 0,
        "established_semantics": "X.Multiply(Y) == M_Y x M_X (verified residual 1.11e-16)",
        "intended_quantity": "A^-1 B  (pose of B expressed in A's frame)",
        "candidate_call": "second_transform.Multiply(inverse_of_first)",
        "pairs": [],
    }
    print(f"SolidWorks {report['solidworks_revision']}, docs={report['document_count_at_probe']}")
    print("verifying corrected order on 3 independent pairs:")

    all_pass = True
    for name, first16, second16 in (("A_B", A16, B16), ("B_C", B16, C16), ("C_A", C16, A16)):
        First, Second = make(first16), make(second16)
        f_read, s_read = read(First), read(Second)

        inv_raw = First.Inverse()
        if inv_raw is None:
            report["pairs"].append({"pair": name, "ok": False, "error": "Inverse returned null"})
            all_pass = False
            continue
        invF = wrap(inv_raw, "IMathTransform")

        prod_raw = Second.Multiply(invF)
        if prod_raw is None:
            report["pairs"].append({"pair": name, "ok": False, "error": "Multiply returned null"})
            all_pass = False
            continue
        got = read(wrap(prod_raw, "IMathTransform"))

        MF, MS = to_mat4_col(f_read), to_mat4_col(s_read)
        want = from_mat4_col(matmul(inv4(MF), MS))
        residual = mad(got, want)

        shape_ok = (
            len(got) == 16
            and all(math.isfinite(v) for v in got)
            and abs(got[12] - 1.0) <= 1.0e-8
            and all(abs(got[i]) <= 1.0e-8 for i in (13, 14, 15))
        )
        ok = residual < 1e-12 and shape_ok
        all_pass = all_pass and ok
        report["pairs"].append({
            "pair": name,
            "ok": ok,
            "solidworks_result_array16": got,
            "independent_A_inv_B_array16": want,
            "residual_vs_A_inv_B": residual,
            "passes_line_2621_shape_guard": shape_ok,
        })
        print(f"  {name}: residual vs A^-1 B = {residual:.3e}  shape_guard={shape_ok}  {'PASS' if ok else 'FAIL'}")

    report["all_pairs_pass"] = all_pass
    report["verdict"] = (
        "CORRECTED_ORDER_VERIFIED_SAFE_TO_PATCH" if all_pass
        else "CORRECTED_ORDER_STILL_WRONG_DO_NOT_PATCH"
    )
    report["patch_semantics"] = {
        "old_line_2613": "inverse_raw = first_transform.IInverse()",
        "new_line_2613": "inverse_raw = first_transform.Inverse()",
        "old_line_2617": "relative_raw = inverse.IMultiply(second_transform)",
        "new_line_2617": "relative_raw = second_transform.Multiply(inverse)",
        "why_operands_swap": "dispid-1 Multiply composes as M_right x M_left, the opposite of "
                            "dispid-2 IMultiply, so preserving A^-1 B requires swapping the "
                            "receiver and the argument. A name-only swap would compute B A^-1.",
        "silent_corruption_averted": "relative_transform is called at line 2807 (record expected) "
                                     "and line 3185 (re-measure after cold reopen) and the two are "
                                     "compared at 1e-7. A consistently-wrong order cancels out in "
                                     "that comparison and would PASS the gate while writing a "
                                     "meaningless link6->gripper transform into the motion contract.",
    }
    print(f"\nverdict: {report['verdict']}")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, ensure_ascii=False)
    print(f"receipt: {OUT}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
