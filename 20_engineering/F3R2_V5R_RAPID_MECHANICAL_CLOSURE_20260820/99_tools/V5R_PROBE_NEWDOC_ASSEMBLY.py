r"""Isolate WHY Loop1E's NewDocument blocked while G0's did not.

Established facts:
  - swNoviceMode was ALREADY False, so the novice chooser toggle was not the
    cause and the suppression "fix" was a no-op. Do not spend the last attempt
    on an unverified remedy.
  - G0 creates a PART (its line 323) and succeeded twice today.
  - Loop1E creates an ASSEMBLY (line 2982) and blocked for 113 minutes.

Structural difference: new assemblies raise the "Begin Assembly" property
manager (Insert Component), which is a DIFFERENT prompt from the novice chooser
and can block a COM NewDocument until dismissed.

Relevant user preferences:
  swAutoShowPMOnNewAssembly  = 405  (show Begin Assembly PM on new assembly)
  swStartCommandWhenCreatingNewAsm (build-dependent alias of the same behaviour)

This probe:
  1. reports the current value of the candidate toggles
  2. creates a THROWAWAY assembly from the pinned template in a WATCHDOG THREAD
  3. if it returns quickly -> assembly creation is fine, and the toggle state
     that made it work is recorded
  4. if it blocks -> enumerates windows to name the exact blocking dialog, then
     reports without hanging this process forever

Writes NO CAD to any project path: the throwaway document is never saved and is
closed immediately. Touches no project asset.
"""
from __future__ import annotations

import ctypes
import datetime as dt
import json
import os
import sys
import threading
import time

SW_PROG_ID = "SldWorks.Application"
SW_DOC_ASSEMBLY = 2
ASSEMBLY_TEMPLATE = r"C:\ProgramData\SolidWorks\SOLIDWORKS 2024\templates\gb_assembly.asmdot"
NEWDOC_TIMEOUT_SECONDS = 45

CANDIDATE_TOGGLES = {
    "swAutoShowPMOnNewAssembly_405": 405,
    "swNoviceMode_4": 4,
}

OUT = os.path.join(
    r"F:\China Graduate Future Flight Vehicle Innovation Competition",
    r"20_engineering\F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820\04_validation",
    "LOOP1E_NEWDOC_ASSEMBLY_PROBE_RECEIPT.json",
)


def value(member):
    return member() if callable(member) else member


def visible_windows(pid: int) -> list[str]:
    user32 = ctypes.windll.user32
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    found: list[str] = []

    def cb(hwnd, _lparam):
        out = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(out))
        if out.value == pid and user32.IsWindowVisible(hwnd):
            title = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, title, 512)
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls, 256)
            found.append(
                f"en={bool(user32.IsWindowEnabled(hwnd))} cls={cls.value} title=[{title.value}]"
            )
        return True

    user32.EnumWindows(EnumWindowsProc(cb), None)
    return found


def main() -> int:
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    raw = win32com.client.GetActiveObject(SW_PROG_ID)
    pid = int(value(raw.GetProcessID))
    doc_count = int(value(raw.GetDocumentCount))
    print(f"attached pid={pid} docs={doc_count}")

    report: dict = {
        "schema": "V5R_LOOP1E_NEWDOC_ASSEMBLY_PROBE_RECEIPT_V1",
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "purpose": "determine whether ASSEMBLY creation (not the novice chooser) is what "
                   "blocked Loop1E's NewDocument, and find the toggle that prevents it",
        "solidworks_pid": pid,
        "document_count_at_start": doc_count,
        "memory_gate_passed": False,
        "owner_override_used": True,
        "project_cad_written": False,
        "throwaway_document_saved": False,
    }

    if doc_count != 0:
        report["verdict"] = "ABORT_SESSION_NOT_EMPTY"
        _write(report)
        return 1

    # --- read candidate toggles BEFORE ---
    before = {}
    for name, key in CANDIDATE_TOGGLES.items():
        try:
            before[name] = bool(raw.GetUserPreferenceToggle(key))
        except Exception as exc:  # noqa: BLE001
            before[name] = f"ERROR {type(exc).__name__}: {exc}"
    report["toggles_before"] = before
    print(f"toggles before: {json.dumps(before, ensure_ascii=False)}")

    # --- force the Begin Assembly property manager OFF ---
    applied = {}
    for name, key in (("swAutoShowPMOnNewAssembly_405", 405),):
        try:
            raw.SetUserPreferenceToggle(key, False)
            applied[name] = bool(raw.GetUserPreferenceToggle(key))
        except Exception as exc:  # noqa: BLE001
            applied[name] = f"ERROR {type(exc).__name__}: {exc}"
    report["toggles_applied"] = applied
    print(f"toggles applied: {json.dumps(applied, ensure_ascii=False)}")

    # --- watchdog-guarded NewDocument on a THROWAWAY assembly ---
    result: dict = {}

    def worker():
        try:
            pythoncom.CoInitialize()
            local = win32com.client.GetActiveObject(SW_PROG_ID)
            t0 = time.time()
            doc = local.NewDocument(ASSEMBLY_TEMPLATE, 0, 0.0, 0.0)
            result["elapsed"] = round(time.time() - t0, 2)
            result["returned_none"] = doc is None
            if doc is not None:
                try:
                    result["title"] = str(value(doc.GetTitle))
                    result["doc_type"] = int(value(doc.GetType))
                except Exception as exc:  # noqa: BLE001
                    result["readback_error"] = f"{type(exc).__name__}: {exc}"
            result["ok"] = True
        except Exception as exc:  # noqa: BLE001
            result["ok"] = False
            result["error"] = f"{type(exc).__name__}: {exc}"

    thread = threading.Thread(target=worker, daemon=True)
    print(f"calling NewDocument(assembly) with a {NEWDOC_TIMEOUT_SECONDS}s watchdog...")
    thread.start()
    thread.join(NEWDOC_TIMEOUT_SECONDS)

    if thread.is_alive():
        wins = visible_windows(pid)
        report["newdocument_result"] = "BLOCKED_TIMED_OUT"
        report["blocking_windows"] = wins
        report["verdict"] = "ASSEMBLY_NEWDOCUMENT_STILL_BLOCKS_TOGGLE_405_INSUFFICIENT"
        print(f"BLOCKED after {NEWDOC_TIMEOUT_SECONDS}s. Visible windows:")
        for w in wins:
            print(f"   {w}")
        _write(report)
        return 2

    report["newdocument_result"] = result
    print(f"NewDocument returned: {json.dumps(result, ensure_ascii=False)}")

    # --- close the throwaway WITHOUT saving ---
    closed = None
    try:
        title = result.get("title")
        if title:
            raw.CloseDoc(title)
            closed = True
    except Exception as exc:  # noqa: BLE001
        closed = f"ERROR {type(exc).__name__}: {exc}"
    report["throwaway_closed_without_saving"] = closed
    report["document_count_after"] = int(value(raw.GetDocumentCount))

    report["verdict"] = (
        "ASSEMBLY_NEWDOCUMENT_WORKS_WITH_PM_SUPPRESSED"
        if result.get("ok") and not result.get("returned_none")
        else "ASSEMBLY_NEWDOCUMENT_FAILED_SEE_RESULT"
    )
    report["conclusion_for_attempt_2"] = (
        "toggle 405 (Begin Assembly property manager) suppressed; NewDocument(assembly) now "
        "returns in %.2fs instead of blocking. Attempt 2 may proceed." % result.get("elapsed", -1)
        if report["verdict"].endswith("PM_SUPPRESSED")
        else "do NOT spend attempt 2 yet - assembly creation still not proven non-blocking"
    )
    _write(report)
    print(f"verdict: {report['verdict']}")
    return 0 if report["verdict"].endswith("PM_SUPPRESSED") else 3


def _write(report: dict) -> None:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, ensure_ascii=False)
    print(f"receipt: {OUT}")


if __name__ == "__main__":
    sys.exit(main())
