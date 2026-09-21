# -*- coding: utf-8 -*-
"""P0a: SolidWorks COM smoke test via the proven b3_lib route (win32com+makepy).

B51R1's S01 died on PowerShell COM activation (0x8002802B). The B3 campaign's
win32com route worked for 282 native parts, so F3R1 revalidates THAT route
before any build is attempted. Read-only: no document is created or saved.
"""
import json
import sys
import traceback

from f3r1_env import F3R1, JLog, check_protected

log = JLog("p0a_com_smoke")
OUT = F3R1 / "00_authority" / "F3R1_COM_SMOKE_RESULT.json"
rep = {"schema": "F3R1_COM_SMOKE_V1", "steps": []}


def step(name, ok, **kw):
    rep["steps"].append({"step": name, "ok": bool(ok), **kw})
    log.ev(name, ok=bool(ok), **kw)


if __name__ == "__main__":
    try:
        check_protected("P0A_PRE")
        step("PROTECTED_PRE", True)
    except Exception as exc:
        step("PROTECTED_PRE", False, error=str(exc))
        rep["verdict"] = "FAIL_PROTECTED"
        OUT.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
        sys.exit(1)

    # free memory check (ctypes; no external deps)
    try:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        ms = MEMORYSTATUSEX()
        ms.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
        rep["memory"] = {"total_gb": round(ms.ullTotalPhys / 2**30, 2),
                         "avail_gb": round(ms.ullAvailPhys / 2**30, 2),
                         "load_pct": ms.dwMemoryLoad}
        step("MEMORY", ms.ullAvailPhys > 2 * 2**30, **rep["memory"])
    except Exception as exc:
        step("MEMORY", False, error=str(exc))

    # makepy availability
    try:
        import b3_lib.sw_core as sw

        mod = sw._sw_module()
        step("MAKEPY_MODULE", mod is not None, module=str(getattr(mod, "__name__", None)))
    except Exception as exc:
        step("MAKEPY_MODULE", False, error=str(exc), tb=traceback.format_exc()[-800:])
        rep["verdict"] = "FAIL_MAKEPY"
        OUT.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
        sys.exit(1)

    # connect (Dispatch starts SW if not running)
    try:
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        try:
            app = win32com.client.GetActiveObject("SldWorks.Application")
            how = "GetActiveObject(existing session)"
        except Exception:
            app = win32com.client.Dispatch("SldWorks.Application")
            how = "Dispatch(new session)"
        app.Visible = True
        ver = app.RevisionNumber
        docs_open = app.GetDocumentCount
        if callable(docs_open):
            docs_open = docs_open()
        step("SW_CONNECT", True, how=how, revision=str(ver), open_docs=int(docs_open))
        rep["sw_revision"] = str(ver)
        rep["connect_route"] = how
        rep["verdict"] = "COM_OK"
    except Exception as exc:
        step("SW_CONNECT", False, error=str(exc), tb=traceback.format_exc()[-800:])
        rep["verdict"] = "FAIL_CONNECT"

    OUT.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    print("verdict:", rep["verdict"])
    sys.exit(0 if rep["verdict"] == "COM_OK" else 1)
