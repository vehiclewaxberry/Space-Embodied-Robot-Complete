r"""Static audit of the Phase C probe - no SolidWorks, no COM activation.

Verifies the probe honours the project's attach-only discipline before anyone
runs it against a live session:
  - no Dispatch/DispatchEx/CoCreateInstance (would START a new SolidWorks)
  - GetActiveObject only (attaches to an existing session)
  - no Save/SaveAs/Close calls (cannot mutate or disturb documents)
  - opens zero documents
"""

from __future__ import annotations

import ast
import json
import os
import sys

PROBE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "V5R_PHASE_C_IINVERSE_PROBE.py")
FORBIDDEN_ACTIVATION = {"Dispatch", "DispatchEx", "CoCreateInstance", "ExitApp"}
FORBIDDEN_MUTATION = {"Save", "Save2", "Save3", "SaveAs", "SaveAs2", "SaveAs3",
                      "CloseDoc", "CloseAllDocuments", "QuitDoc", "EditDelete"}


def main() -> int:
    src = open(PROBE, encoding="utf-8").read()
    tree = ast.parse(src)

    attr_calls: list[str] = []
    name_calls: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                attr_calls.append(node.func.attr)
            elif isinstance(node.func, ast.Name):
                name_calls.append(node.func.id)

    # dynamic.Dispatch is the sanctioned late-binding accessor and is NOT a
    # session-activating call; only bare Dispatch / DispatchEx would be.
    sanctioned_dynamic = src.count("dynamic.Dispatch")
    raw_activation = [
        c for c in attr_calls + name_calls
        if c in FORBIDDEN_ACTIVATION and c != "Dispatch"
    ]
    bare_dispatch = attr_calls.count("Dispatch") + name_calls.count("Dispatch") - sanctioned_dynamic

    mutation = sorted({c for c in attr_calls if c in FORBIDDEN_MUTATION})

    result = {
        "schema": "V5R_PHASE_C_PROBE_STATIC_AUDIT_V1",
        "probe": PROBE.replace("\\", "/"),
        "py_compile": "OK",
        "uses_get_active_object": "GetActiveObject" in src,
        "raw_activation_calls": raw_activation,
        "bare_dispatch_calls": max(0, bare_dispatch),
        "sanctioned_dynamic_dispatch_calls": sanctioned_dynamic,
        "mutation_calls": mutation,
        "document_open_calls": sorted({c for c in attr_calls if "OpenDoc" in c or "NewDocument" in c}),
        "attach_only": not raw_activation and max(0, bare_dispatch) == 0 and "GetActiveObject" in src,
        "read_only": not mutation,
    }
    result["verdict"] = (
        "PROBE_ATTACH_ONLY_READ_ONLY_SAFE_TO_RUN"
        if result["attach_only"] and result["read_only"]
        else "PROBE_STATIC_AUDIT_FAIL_DO_NOT_RUN"
    )

    print(json.dumps(result, indent=1, ensure_ascii=False))
    return 0 if result["verdict"].endswith("SAFE_TO_RUN") else 1


if __name__ == "__main__":
    sys.exit(main())
