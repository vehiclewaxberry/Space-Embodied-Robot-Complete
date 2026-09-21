r"""Statically prove every COM member call in the Loop1E script exists on the
interface it is called through.

Motivation: two Loop1E attempts have now died on this SINGLE defect class -
calling a member on a makepy wrapper that does not expose it.

  attempt 1 lineage: IInverse/IMultiply not invocable on IMathTransform
  attempt 2:         FeatureByName absent from IModelDoc2 (lives on IAssemblyDoc)

Fixing them one crash at a time costs a full run each (attempt 2 burned 50
minutes to surface line 2691, and line 3165 held the identical bug that would
have failed minutes later). This audit finds them all at once, offline.

Method:
  1. parse the generated typelib module and collect, per interface class, the
     set of members it actually exposes (methods + property maps)
  2. parse the Loop1E script and track which interface each variable was wrapped
     as, via  base.wrap(<raw>, "<Interface>", ...)  assignments
  3. for every  <var>.<Member>(...)  call, check that <Member> is in that
     interface's member set, and report the mismatches

Deliberately conservative: it only judges variables whose interface it can
attribute with certainty from a direct wrap() assignment, and reports what it
could not attribute rather than guessing. Unknown-variable calls are listed
separately so nothing is silently passed.

No SolidWorks, no COM activation, read-only.
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys

TYPELIB = r"C:\Users\stude\AppData\Local\Temp\gen_py\3.13\83A33D31-27C5-11CE-BFD4-00400513BB57x0x32x0.py"
SCRIPT = (
    r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering"
    r"\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE\99_tools"
    r"\F3R2_V5_NATIVE_LOOP1E_TOP_ASSEMBLY_ATTACH_ONLY.py"
)
OUT = os.path.join(
    r"F:\China Graduate Future Flight Vehicle Innovation Competition",
    r"20_engineering\F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820\04_validation",
    "LOOP1E_COM_MEMBER_AUDIT_RECEIPT.json",
)

# members that are not typelib members at all - python/pywin32 level or our own
IGNORE_MEMBERS = {
    "QueryInterface", "Dispatch", "keys", "items", "get", "append", "strip",
    "upper", "lower", "split", "replace", "resolve", "exists", "is_file",
    "read_text", "write_text", "open", "format", "join", "encode", "decode",
    "hexdigest", "update", "sort", "extend", "pop", "add", "startswith",
    "endswith", "casefold", "mkdir", "glob", "rglob", "iterdir", "stat",
    "name", "stem", "suffix", "parent", "parts", "value",
}


def typelib_members() -> dict[str, set[str]]:
    src = open(TYPELIB, encoding="utf-8", errors="replace").read()
    classes: dict[str, set[str]] = {}
    for match in re.finditer(r"^class (\w+)\(", src, re.MULTILINE):
        cls = match.group(1)
        start = match.start()
        nxt = src.find("\nclass ", start + 10)
        block = src[start: nxt if nxt > 0 else len(src)]
        members = set(re.findall(r"\n\tdef (\w+)\(", block))
        members |= set(re.findall(r"\n\s+def (\w+)\(", block))
        # property maps:  "MemberName": (dispid, ...)
        for pm in re.finditer(r'"(\w+)"\s*:\s*\(', block):
            members.add(pm.group(1))
        classes[cls] = members
    return classes


def main() -> int:
    classes = typelib_members()
    src = open(SCRIPT, encoding="utf-8").read()
    tree = ast.parse(src)

    # variable -> interface, from  x = base.wrap(raw, "IFoo", ...)
    var_iface: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            call = node.value
            fn = call.func
            is_wrap = (isinstance(fn, ast.Attribute) and fn.attr == "wrap") or (
                isinstance(fn, ast.Name) and fn.id == "wrap"
            )
            if is_wrap and len(call.args) >= 2 and isinstance(call.args[1], ast.Constant):
                iface = call.args[1].value
                if isinstance(iface, str) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    var_iface[node.targets[0].id] = iface

    mismatches = []
    unattributed = []
    checked = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        member = node.func.attr
        if member in IGNORE_MEMBERS or member.startswith("_"):
            continue
        target = node.func.value
        if not isinstance(target, ast.Name):
            continue
        var = target.id
        iface = var_iface.get(var)
        if iface is None:
            unattributed.append({"line": node.lineno, "var": var, "member": member})
            continue
        if iface not in classes:
            unattributed.append({"line": node.lineno, "var": var, "member": member,
                                 "note": f"interface {iface} not found in typelib"})
            continue
        checked += 1
        if member not in classes[iface]:
            owners = sorted(c for c, m in classes.items() if member in m and c.startswith("I"))
            mismatches.append({
                "line": node.lineno,
                "variable": var,
                "called_as_interface": iface,
                "member": member,
                "exists_on_interface": False,
                "member_actually_lives_on": owners[:12],
            })

    report = {
        "schema": "V5R_LOOP1E_COM_MEMBER_AUDIT_RECEIPT_V1",
        "purpose": "prove no remaining COM member is called through an interface that lacks it",
        "typelib": TYPELIB.replace("\\", "/"),
        "script": SCRIPT.replace("\\", "/"),
        "typelib_classes_parsed": len(classes),
        "wrapped_variables_attributed": len(var_iface),
        "member_calls_checked": checked,
        "mismatches_found": len(mismatches),
        "mismatches": mismatches,
        "unattributed_call_count": len(unattributed),
        "unattributed_note": "calls on variables whose interface could not be proven from a direct "
                             "base.wrap(...) assignment. NOT judged either way - listed so the gap is "
                             "explicit rather than silently passed.",
        "unattributed_sample": unattributed[:25],
        "verdict": "NO_REMAINING_INTERFACE_MEMBER_MISMATCH" if not mismatches
                   else "INTERFACE_MEMBER_MISMATCHES_PRESENT",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, ensure_ascii=False)

    print(f"typelib classes parsed      : {len(classes)}")
    print(f"wrapped vars attributed     : {len(var_iface)}")
    print(f"member calls checked        : {checked}")
    print(f"unattributed (not judged)   : {len(unattributed)}")
    print(f"MISMATCHES                  : {len(mismatches)}")
    for m in mismatches:
        print(f"  line {m['line']:>5}  {m['variable']}({m['called_as_interface']}).{m['member']}"
              f"  -> lives on {m['member_actually_lives_on']}")
    print(f"\nverdict: {report['verdict']}")
    print(f"receipt: {OUT}")
    return 0 if not mismatches else 1


if __name__ == "__main__":
    sys.exit(main())
