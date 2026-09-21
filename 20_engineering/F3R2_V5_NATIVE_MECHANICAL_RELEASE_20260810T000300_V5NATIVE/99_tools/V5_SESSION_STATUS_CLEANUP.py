#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Attach-only session status + cleanup: list open documents and close them all.

Uses the production close_all_owned(). Prints JSON on stdout. Never saves.
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

RUN_ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE")
sys.path.insert(0, str(RUN_ROOT / "99_tools"))

import F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY as base  # noqa: E402
import F3R2_V5_NATIVE_LOOP1C1_GRIPPER_ASSEMBLY_ATTACH_ONLY as m  # noqa: E402


def main() -> int:
    result = {"schema": "V5_SESSION_STATUS_CLEANUP_V1"}
    sw = types = pythoncom = None
    try:
        import pythoncom  # noqa: F401
        import win32com.client
        from win32com.client import gencache

        pythoncom.CoInitialize()
        types = gencache.GetModuleForTypelib(*base.SW_TLB)
        raw = win32com.client.GetActiveObject(base.SW_PROG_ID)
        sw = base.wrap(raw, "ISldWorks", types, pythoncom)
        result["pid"] = int(base.value(sw, "GetProcessID"))
        result["revision"] = str(base.value(sw, "RevisionNumber"))
        docs = base.as_list(base.value(sw, "GetDocuments"))
        result["open_documents_before"] = [str(base.value(doc, "GetTitle")) for doc in docs]
        if docs:
            result["cleanup"] = m.close_all_owned(sw)
        result["open_documents_after"] = int(base.value(sw, "GetDocumentCount"))
        result["verdict"] = "V5_SESSION_EMPTY" if result["open_documents_after"] == 0 else "V5_SESSION_NOT_EMPTY"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_SESSION_STATUS_FAIL"
    finally:
        if pythoncom is not None:
            try:
                pythoncom.CoUninitialize()
            except Exception:  # noqa: BLE001
                pass
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("verdict") == "V5_SESSION_EMPTY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
