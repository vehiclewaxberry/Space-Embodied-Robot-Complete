r"""Suppress the interactive "New SOLIDWORKS Document" chooser before Attempt 2.

Attempt 1 blocked for 108 minutes inside sw.NewDocument (Loop1E line 2982)
because the freshly restarted session raised the interactive New Document
chooser (window class #32770, title "新建 SOLIDWORKS 文件") and the COM call
cannot return until it is dismissed. Window enumeration also showed the main
frame with en=False, the signature of a modal child holding the app.

Notably the G0 smoke tool calls the SAME NewDocument (its line 323) and it
SUCCEEDED twice today, so NewDocument is not inherently broken on this install -
the difference is per-session UI state.

swNoviceMode (swUserPreferenceToggle_e = 4) controls whether the novice New
Document chooser appears. Setting it False makes NewDocument resolve the passed
template directly instead of prompting.

Design notes:
  - does NOT touch the SHA-pinned BASE_HELPER; it reuses that module's pattern
    (snapshot then set) rather than editing it
  - records the PRIOR value so the change is reversible and auditable
  - changes exactly ONE toggle; no other preference is written
  - refuses to run if a document is open (would indicate a dirty session)

Attach-only: never starts or exits SolidWorks.
"""
from __future__ import annotations

import ctypes
import datetime as dt
import json
import os
import sys

SW_PROG_ID = "SldWorks.Application"
SW_NOVICE_MODE = 4  # swUserPreferenceToggle_e.swNoviceMode
OUT = os.path.join(
    r"F:\China Graduate Future Flight Vehicle Innovation Competition",
    r"20_engineering\F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820\04_validation",
    "LOOP1E_NEWDOC_DIALOG_SUPPRESSION_RECEIPT.json",
)


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def available_gib() -> float:
    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
    return stat.ullAvailPhys / (1024.0 ** 3)


def value(member):
    return member() if callable(member) else member


def main() -> int:
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    raw = win32com.client.GetActiveObject(SW_PROG_ID)

    revision = str(value(raw.RevisionNumber))
    doc_count = int(value(raw.GetDocumentCount))
    pid = int(value(raw.GetProcessID))
    print(f"attached: pid={pid} revision={revision} docs={doc_count} avail={available_gib():.3f} GiB")

    if doc_count != 0:
        print(f"REFUSING: {doc_count} document(s) open; Attempt 2 requires a clean empty session")
        return 1

    before = bool(raw.GetUserPreferenceToggle(SW_NOVICE_MODE))
    print(f"swNoviceMode before = {before}")

    raw.SetUserPreferenceToggle(SW_NOVICE_MODE, False)
    after = bool(raw.GetUserPreferenceToggle(SW_NOVICE_MODE))
    print(f"swNoviceMode after  = {after}")

    payload = {
        "schema": "V5R_LOOP1E_NEWDOC_DIALOG_SUPPRESSION_RECEIPT_V1",
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "owner_ruling": "AUTHORIZE_LOW_MEMORY_EXECUTION_WITH_BOUNDED_NATIVE_ATTEMPTS_20260820",
        "purpose": "prevent sw.NewDocument (Loop1E:2982) from blocking on the interactive "
                   "New Document chooser, which consumed Attempt 1",
        "solidworks_pid": pid,
        "solidworks_revision": revision,
        "document_count": doc_count,
        "available_gib": round(available_gib(), 4),
        "memory_gate_passed": False,
        "owner_override_used": True,
        "preference_changed": {
            "name": "swNoviceMode",
            "swUserPreferenceToggle_e": SW_NOVICE_MODE,
            "value_before": before,
            "value_after": after,
            "reversible": True,
            "restore_instruction": f"sw.SetUserPreferenceToggle({SW_NOVICE_MODE}, {before})",
        },
        "preferences_changed_count": 1,
        "base_helper_modified": False,
        "loop1e_script_modified": False,
        "documents_opened": 0,
        "cad_written": False,
        "attach_only": True,
        "verdict": "NEWDOC_CHOOSER_SUPPRESSED" if after is False else "SUPPRESSION_FAILED_VALUE_DID_NOT_TAKE",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, ensure_ascii=False)
    print(f"verdict: {payload['verdict']}")
    print(f"receipt: {OUT}")
    return 0 if after is False else 1


if __name__ == "__main__":
    sys.exit(main())
