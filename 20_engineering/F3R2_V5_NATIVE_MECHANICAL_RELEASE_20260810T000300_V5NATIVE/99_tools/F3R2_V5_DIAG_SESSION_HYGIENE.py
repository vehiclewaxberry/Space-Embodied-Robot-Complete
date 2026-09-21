#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Session hygiene check: attach, list open documents, close all without saving."""

from __future__ import annotations

import json
import sys
from pathlib import Path

RUN_ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE")
sys.path.insert(0, str(RUN_ROOT / "99_tools"))

import F3R2_V5_NATIVE_LOOP1B_WING_ROOTS_ATTACH_ONLY as L1B  # noqa: E402


def main() -> int:
    out = {"probe": "SESSION_HYGIENE_V1"}
    sw = types = pythoncom = None
    try:
        expected_pid = L1B.registered_baseline()["session_b_pid"]
        # manual attach (attach_empty_session enforces empty; here we expect maybe non-empty)
        import pythoncom as pc
        import win32com.client
        from win32com.client import gencache
        pc.CoInitialize()
        pythoncom = pc
        types = gencache.GetModuleForTypelib(*L1B.SW_TLB)
        raw = win32com.client.GetActiveObject(L1B.SW_PROG_ID)
        sw = L1B.wrap(raw, "ISldWorks", types, pythoncom)
        pid = int(L1B.value(sw, "GetProcessID"))
        out["pid"] = pid
        out["pid_matches"] = (pid == expected_pid)
        docs = L1B.as_list(L1B.value(sw, "GetDocuments"))
        out["open_documents"] = [str(L1B.value(d, "GetTitle")) for d in docs]
        for d in docs:
            try:
                sw.CloseDoc(str(L1B.value(d, "GetTitle")))
            except Exception as exc:
                out.setdefault("close_errors", []).append(repr(exc))
        out["final_document_count"] = int(L1B.value(sw, "GetDocumentCount"))
        out["verdict"] = "SESSION_CLEAN" if out["final_document_count"] == 0 else "SESSION_STILL_OCCUPIED"
    except Exception as exc:
        import traceback
        out["verdict"] = "HYGIENE_EXCEPTION"
        out["error"] = repr(exc)
        out["traceback"] = traceback.format_exc()
    finally:
        if pythoncom is not None:
            pythoncom.CoUninitialize()
    print(json.dumps(out, ensure_ascii=False))
    return 0 if out.get("verdict") == "SESSION_CLEAN" else 3


if __name__ == "__main__":
    raise SystemExit(main())
