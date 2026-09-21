r"""Write the Session-A process addendum for the CURRENT live SolidWorks session.

Session B (F3R2_V5_G0_SESSION_B_VERIFY_ATTACH_ONLY.py:303-307) hard-fails if it
attaches to the same PID that produced the Session-A part - it must verify the
part cold-opens in a genuinely fresh process. That check is load-bearing and is
not modified. This script only records WHICH pid is the disallowed Session-A
process, which is exactly what the addendum schema exists to state.

Attach-only, read-only against SolidWorks; writes one small JSON receipt.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

ENGINEERING = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering")
RUN_DIR = ENGINEERING / "_MFINAL_G0_SMOKE_20260820T090000_V5RA"
OUT = RUN_DIR / "G0_SMOKE_SESSION_A_PROCESS_ADDENDUM.json"
EXPECTED_EXE = "F:/Windows_profile/solidworks/SOLIDWORKS/SLDWORKS.exe"


def value(member):
    return member() if callable(member) else member


def main() -> int:
    if OUT.exists():
        print(f"REFUSING: addendum already exists (write-once): {OUT}")
        return 1
    if not (RUN_DIR / "G0_SMOKE_SESSION_A_RECEIPT.json").is_file():
        print(f"REFUSING: Session-A receipt not found in {RUN_DIR}")
        return 1

    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    raw = win32com.client.GetActiveObject("SldWorks.Application")
    pid = int(value(raw.GetProcessID))
    revision = str(value(raw.RevisionNumber))
    doc_count = int(value(raw.GetDocumentCount))
    print(f"live session: pid={pid} revision={revision} docs={doc_count}")

    # process start time, read without spawning anything
    start_local = None
    try:
        import ctypes
        from ctypes import wintypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        k32 = ctypes.windll.kernel32
        handle = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            creation = wintypes.FILETIME()
            exit_t = wintypes.FILETIME()
            kernel_t = wintypes.FILETIME()
            user_t = wintypes.FILETIME()
            if k32.GetProcessTimes(handle, ctypes.byref(creation), ctypes.byref(exit_t),
                                   ctypes.byref(kernel_t), ctypes.byref(user_t)):
                ticks = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
                epoch = dt.datetime(1601, 1, 1, tzinfo=dt.timezone.utc)
                started = epoch + dt.timedelta(microseconds=ticks / 10)
                start_local = started.astimezone().isoformat()
            k32.CloseHandle(handle)
    except Exception as exc:  # noqa: BLE001
        print(f"note: could not read process start time ({type(exc).__name__}: {exc})")

    if start_local is None:
        print("REFUSING: process start time unavailable; the addendum must carry it verbatim")
        return 1

    payload = {
        "schema": "F3R2_V5_G0_SMOKE_SESSION_A_PROCESS_ADDENDUM_V1",
        "recorded_local": dt.datetime.now().astimezone().isoformat(),
        "solidworks_process_id": pid,
        "solidworks_process_start_local": start_local,
        "solidworks_executable": EXPECTED_EXE,
        "solidworks_revision": revision,
        "session_a_receipt": "G0_SMOKE_SESSION_A_RECEIPT.json",
        "purpose": (
            f"Session B must attach to a different manually started SOLIDWORKS process; "
            f"PID {pid} is the disallowed Session A process."
        ),
        "non_claims": [
            "NOT_SESSION_B_COLD_REOPEN_PASS",
            "NOT_G0_SOLIDWORKS_NATIVE_EXECUTION_READY",
            "NOT_V5_RELEASE_CREATED",
        ],
        "authoring_context": {
            "owner_ruling": "AUTHORIZE_LOW_MEMORY_EXECUTION_WITH_BOUNDED_NATIVE_ATTEMPTS_20260820",
            "round": "20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820",
            "memory_gate_passed": False,
            "owner_override_used": True,
            "note": "Session-A samples were ~1.41-1.44 GiB, far below MIN_AVAILABLE_GIB=6.0. "
                    "Recorded honestly; this is NOT a memory gate pass.",
        },
    }
    with OUT.open("x", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"wrote {OUT}")
    print(f"SESSION_A_PID_TO_AVOID = {pid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
