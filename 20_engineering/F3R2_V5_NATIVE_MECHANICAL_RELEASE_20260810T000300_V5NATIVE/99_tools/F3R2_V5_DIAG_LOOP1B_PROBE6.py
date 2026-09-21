#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Loop1B probe 6: cold read-only vs editable GetRemainingDOFs behavior.

The 214933Z run saved LEFT_WING_ROOT_TRUE_HINGE.SLDASM (motion proof + 6
configs + save passed), but cold read-only verify failed at
prove_component_true_1r: GetRemainingDOFs returned api_return=2 with all 12
out-parameter statuses 0.  This probe opens the saved assembly both ways
(read-only like the script's cold path, and editable without saving) and dumps
raw DOF returns per configuration for PANEL and LUG, plus suppression states.
Never saves; closes everything; stdout JSON only.
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

RUN_ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE")
sys.path.insert(0, str(RUN_ROOT / "99_tools"))

import F3R2_V5_NATIVE_LOOP1B_WING_ROOTS_ATTACH_ONLY as L1B  # noqa: E402

TARGET = RUN_ROOT / "02_native_subassemblies/LEFT_WING_ROOT_TRUE_HINGE.SLDASM"


def dof_raw(component):
    raw = component.GetRemainingDOFs()
    if not isinstance(raw, tuple):
        return {"returned_type": type(raw).__name__, "repr": repr(raw)}
    return {
        "api_return": int(raw[0]),
        "slot_statuses": [int(raw[i]) for i in (1, 3, 5, 7, 9, 11)],
    }


def dump_config(model, name, types, pythoncom):
    row = {"configuration": name}
    if not bool(model.ShowConfiguration2(name)):
        row["activate"] = "FAIL"
        return row
    row["active"] = str(L1B.value(L1B.value(model, "ConfigurationManager"), "ActiveConfiguration").Name)
    for label, path in (("PANEL", L1B.SIDES["L"]["panel"]), ("LUG", L1B.SIDES["L"]["lug"])):
        comp = L1B.component_by_path(model, Path(path), types, pythoncom)
        t = L1B.transform_array(comp)
        row[label] = {
            "suppression": int(L1B.value(comp, "GetSuppression")),
            "constrained_status": int(L1B.value(comp, "GetConstrainedStatus")),
            "dof": dof_raw(comp),
            "translation_mm": [round(t[9] * 1000.0, 4), round(t[10] * 1000.0, 4), round(t[11] * 1000.0, 4)],
        }
    return row


def main() -> int:
    out = {"probe": "LOOP1B_PROBE6_COLD_DOF_V1", "read_only_pass": [], "editable_pass": []}
    sw = types = pythoncom = None
    model = None
    try:
        expected_pid = L1B.registered_baseline()["session_b_pid"]
        sw, types, pythoncom, session = L1B.attach_empty_session(expected_pid)
        out["session"] = session
        model, opened = L1B.open_doc(sw, TARGET, L1B.SW_ASSEMBLY, True, types, pythoncom)
        names = [str(n) for n in L1B.as_list(L1B.value(model, "GetConfigurationNames"))]
        out["configurations"] = names
        for name in names:
            print("RO CFG", name, flush=True, file=sys.stderr)
            out["read_only_pass"].append(dump_config(model, name, types, pythoncom))
        L1B.close_doc(sw, model)
        model = None
        raw, errors, warnings = L1B.unpack_document(sw.OpenDoc6(str(TARGET), L1B.SW_ASSEMBLY, L1B.SW_OPEN_SILENT, "", 0, 0), "OPEN_EDIT")
        out["editable_open"] = {"errors": errors, "warnings": warnings}
        model = L1B.wrap(raw, "IModelDoc2", types, pythoncom)
        for name in ("STOWED", "DEPLOYING", "DEPLOYED"):
            print("RW CFG", name, flush=True, file=sys.stderr)
            out["editable_pass"].append(dump_config(model, name, types, pythoncom))
        out["verdict"] = "PROBE6_COMPLETE"
    except Exception as exc:
        out["verdict"] = "PROBE6_EXCEPTION"
        out["error"] = repr(exc)
        out["traceback"] = traceback.format_exc()
    finally:
        try:
            L1B.close_doc(sw, model)
        except Exception:
            pass
        try:
            L1B.close_owned_documents(sw)
            out["final_document_count"] = int(L1B.value(sw, "GetDocumentCount")) if sw is not None else None
        except Exception:
            out["final_document_count"] = "UNKNOWN"
        if pythoncom is not None:
            pythoncom.CoUninitialize()
    print(json.dumps(out, ensure_ascii=False))
    return 0 if out.get("verdict") == "PROBE6_COMPLETE" else 3


if __name__ == "__main__":
    raise SystemExit(main())
