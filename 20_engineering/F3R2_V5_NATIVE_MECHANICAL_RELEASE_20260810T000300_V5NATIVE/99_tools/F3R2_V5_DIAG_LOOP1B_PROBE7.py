#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Loop1B probe 7: why does GetRemainingDOFs fail in DEPLOYING/BOTH_FAIL cold?

Probe 6: the saved L assembly (lightweight components) answers the DOF query
correctly in STOWED/DEPLOYED/L_FAIL/R_FAIL/default, but returns api_return=2
with zeroed slots in DEPLOYING and BOTH_FAIL, in read-only and editable modes
alike.  This probe dumps mate health per configuration and tests whether an
in-memory rebuild (EditRebuild3 / ForceRebuild3) restores the DOF query.
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
        return {"returned_type": type(raw).__name__}
    return {"api_return": int(raw[0]), "slot_statuses": [int(raw[i]) for i in (1, 3, 5, 7, 9, 11)]}


def mate_dump(model, types, pythoncom):
    rows = []
    try:
        ledger = L1B.mate_ledger(model, types, pythoncom)
        for r in ledger:
            rows.append({"name": r["feature_name"], "type": r["mate_type"], "align": r["alignment"], "supp": r["suppressed"], "err": r["feature_error_code"], "warn": r["feature_is_warning"]})
    except Exception as exc:
        rows.append({"ledger_error": repr(exc)[:300]})
    return rows


def config_report(model, name, types, pythoncom):
    row = {"configuration": name, "activate_ok": bool(model.ShowConfiguration2(name))}
    panel = L1B.component_by_path(model, Path(L1B.SIDES["L"]["panel"]), types, pythoncom)
    lug = L1B.component_by_path(model, Path(L1B.SIDES["L"]["lug"]), types, pythoncom)
    row["mates"] = mate_dump(model, types, pythoncom)
    row["dof_before"] = {"PANEL": dof_raw(panel), "LUG": dof_raw(lug)}
    row["edit_rebuild_ok"] = bool(model.EditRebuild3())
    row["dof_after_edit_rebuild"] = {"PANEL": dof_raw(panel), "LUG": dof_raw(lug)}
    row["force_rebuild_ok"] = bool(model.ForceRebuild3(True))
    row["dof_after_force_rebuild"] = {"PANEL": dof_raw(panel), "LUG": dof_raw(lug)}
    return row


def main() -> int:
    out = {"probe": "LOOP1B_PROBE7_CONFIG_DOF_REBUILD_V1", "reports": []}
    sw = types = pythoncom = None
    model = None
    try:
        expected_pid = L1B.registered_baseline()["session_b_pid"]
        sw, types, pythoncom, session = L1B.attach_empty_session(expected_pid)
        out["session"] = session
        model, opened = L1B.open_doc(sw, TARGET, L1B.SW_ASSEMBLY, True, types, pythoncom)
        for name in ("STOWED", "DEPLOYING", "BOTH_FAIL"):
            print("CFG", name, flush=True, file=sys.stderr)
            out["reports"].append(config_report(model, name, types, pythoncom))
        out["verdict"] = "PROBE7_COMPLETE"
    except Exception as exc:
        out["verdict"] = "PROBE7_EXCEPTION"
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
    return 0 if out.get("verdict") == "PROBE7_COMPLETE" else 3


if __name__ == "__main__":
    raise SystemExit(main())
