#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Close every document in the attached Session B (attach-only cleanup)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True

RUN_ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE")
sys.path.insert(0, str(RUN_ROOT / "99_tools"))

import F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY as base  # noqa: E402


def main() -> int:
    import pythoncom
    import win32com.client
    from win32com.client import gencache

    pythoncom.CoInitialize()
    types = gencache.GetModuleForTypelib(*base.SW_TLB)
    raw = win32com.client.GetActiveObject(base.SW_PROG_ID)
    sw = base.wrap(raw, "ISldWorks", types, pythoncom)
    rows = []
    for _pass in range(6):
        documents = base.as_list(base.value(sw, "GetDocuments"))
        if not documents:
            break
        titles = []
        for raw in documents:
            try:
                titles.append(str(base.value(raw, "GetTitle")))
            except Exception:
                continue
        for title in reversed(list(dict.fromkeys(titles))):
            try:
                sw.CloseDoc(title)
                rows.append({"title": title, "closed": True})
            except Exception as exc:
                rows.append({"title": title, "closed": False, "exception": repr(exc)})
    print({"document_count": int(base.value(sw, "GetDocumentCount")), "closed": rows})
    pythoncom.CoUninitialize()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
