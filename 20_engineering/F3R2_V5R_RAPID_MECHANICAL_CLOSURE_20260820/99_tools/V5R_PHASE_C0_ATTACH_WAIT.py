r"""Phase C0 - wait for a clean, already-started SolidWorks process to become
attachable, then confirm it is empty. Does NOT start SolidWorks (this project's
attach-only scripts never call subprocess/Dispatch/DispatchEx - see the banned
import guards in F3R2_V5_LOOP1E0_LOCAL_ARM_CHECKPOINT_V2_MIGRATE.py and
F3R2_V5_NATIVE_LOOP3_RELEASE_BUILD_ATTACH_ONLY.py). The process itself is
started once, out of band, by a plain OS `start` command issued by the
operator/orchestrator - this script only polls GetActiveObject.

Exit 0 + PASS receipt  => safe to run the Phase C probe.
Exit 1 + TIMEOUT/FAIL receipt => report honestly, do not fabricate an attach.
"""
from __future__ import annotations

import json
import os
import sys
import time
import datetime as dt

SW_PROG_ID = "SldWorks.Application"
EXPECTED_REVISION_PREFIX = "32.5."
MAX_WAIT_SECONDS = 420  # under the owner's 10-minute per-stage watchdog, leaves margin
POLL_INTERVAL_SECONDS = 5
OUT = os.path.join(
    r"F:\China Graduate Future Flight Vehicle Innovation Competition",
    r"20_engineering\F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820\04_validation",
    "LOOP1E_PHASE_C0_ATTACH_WAIT_RECEIPT.json",
)


def value(member):
    """Normalise late-bound members that arrive as methods (cf. base.value())."""
    return member() if callable(member) else member


def available_gib() -> float:
    import ctypes

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
            ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
    return stat.ullAvailPhys / (1024.0 ** 3)


def main() -> int:
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    start = time.time()
    attempts = []
    while time.time() - start < MAX_WAIT_SECONDS:
        elapsed = round(time.time() - start, 1)
        sample = {"elapsed_s": elapsed, "available_gib": round(available_gib(), 4)}
        try:
            raw = win32com.client.GetActiveObject(SW_PROG_ID)
            # read-only calls straight on the raw dispatch object, no static binding
            # needed - but late binding surfaces some typelib properties as methods,
            # so normalise via value() exactly as base.value() does.
            revision = str(value(raw.RevisionNumber))
            doc_count = int(value(raw.GetDocumentCount))
            sample.update(attached=True, revision=revision, doc_count=doc_count)
            attempts.append(sample)
            if revision.startswith(EXPECTED_REVISION_PREFIX) and doc_count == 0:
                _write({
                    "schema": "V5R_LOOP1E_PHASE_C0_ATTACH_WAIT_RECEIPT_V1",
                    "verdict": "ATTACH_CONFIRMED_EMPTY_SESSION",
                    "elapsed_seconds": elapsed,
                    "revision": revision,
                    "doc_count": doc_count,
                    "available_gib_at_attach": sample["available_gib"],
                    "attempts": attempts,
                    "timestamp_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                })
                print(f"ATTACH_CONFIRMED_EMPTY_SESSION revision={revision} doc_count={doc_count} elapsed={elapsed}s")
                return 0
            print(f"  [{elapsed:6.1f}s] attached but not ready yet: revision={revision} doc_count={doc_count}")
        except Exception as exc:  # noqa: BLE001 - polling loop, record and retry
            sample.update(attached=False, error=f"{type(exc).__name__}: {exc}")
            attempts.append(sample)
            print(f"  [{elapsed:6.1f}s] not yet attachable: {sample['error'][:100]}")
        time.sleep(POLL_INTERVAL_SECONDS)

    _write({
        "schema": "V5R_LOOP1E_PHASE_C0_ATTACH_WAIT_RECEIPT_V1",
        "verdict": "TIMEOUT_NOT_ATTACHABLE_WITHIN_WINDOW",
        "max_wait_seconds": MAX_WAIT_SECONDS,
        "attempts": attempts,
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    print(f"TIMEOUT after {MAX_WAIT_SECONDS}s - not attachable")
    return 1


def _write(payload: dict) -> None:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    sys.exit(main())
