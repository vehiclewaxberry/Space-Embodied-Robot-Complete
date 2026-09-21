r"""Phase C0 one-shot - answer a single question and exit immediately:
is there an attachable, empty SolidWorks session visible to THIS process's
Windows user and privilege level?

This is the decisive check, more so than a process count: a SLDWORKS.EXE
started under a different user or elevation level exists in the task list but
is invisible to GetActiveObject, which is the only thing the Loop1E chain can
actually use.

Starts nothing, opens nothing, mutates nothing. Exits at once either way -
no polling - so it can be run cheaply before committing to the wait loop.

Exit 0 = attachable empty session, safe to proceed to the Phase C probe.
Exit 2 = attached but not empty / wrong revision (needs operator cleanup).
Exit 1 = nothing attachable.
"""
from __future__ import annotations

import ctypes
import sys

SW_PROG_ID = "SldWorks.Application"
EXPECTED_REVISION_PREFIX = "32.5."


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def value(member):
    """Late-bound dispatch exposes some typelib properties as methods.

    Mirrors base.value() in F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY.py: under the
    makepy static binding GetDocumentCount is a property, but on the raw dispatch
    object it arrives as a bound method. Normalise both.
    """
    return member() if callable(member) else member


def memory_snapshot() -> tuple[float, float, int]:
    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
    gib = 1024.0 ** 3
    return (stat.ullAvailPhys / gib, stat.ullTotalPhys / gib, int(stat.dwMemoryLoad))


def main() -> int:
    avail, total, load = memory_snapshot()
    print(f"AVAIL_GIB={avail:.4f} TOTAL_GIB={total:.4f} MEM_LOAD_PCT={load}")

    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    try:
        raw = win32com.client.GetActiveObject(SW_PROG_ID)
    except Exception as exc:  # noqa: BLE001 - the whole point is to classify the failure
        print(f"ATTACH=NO  reason={type(exc).__name__}: {exc}")
        print("VERDICT=NO_ATTACHABLE_SESSION")
        return 1

    revision = str(value(raw.RevisionNumber))
    doc_count = int(value(raw.GetDocumentCount))
    print(f"ATTACH=YES revision={revision} doc_count={doc_count}")

    if not revision.startswith(EXPECTED_REVISION_PREFIX):
        print(f"VERDICT=REVISION_MISMATCH expected_prefix={EXPECTED_REVISION_PREFIX}")
        return 2
    if doc_count != 0:
        print("VERDICT=SESSION_NOT_EMPTY_OPERATOR_MUST_CLOSE_DOCUMENTS")
        return 2

    print("VERDICT=ATTACH_CONFIRMED_EMPTY_SESSION")
    return 0


if __name__ == "__main__":
    sys.exit(main())
