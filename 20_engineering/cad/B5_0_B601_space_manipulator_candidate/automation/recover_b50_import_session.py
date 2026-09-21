"""Restore a timed-out B5.0 STEP-import session and exit its exact SW PID."""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

sys.dont_write_bytecode = True

import win32com.client

from sw_b50_core import (
    CANDIDATE_ROOT,
    Phase0Error,
    require_within,
    sldworks_process_ids,
    utc_now,
    write_json_once,
)


RUNS_ROOT = CANDIDATE_ROOT / "03_CAD" / "native_runs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--expected-pid", required=True, type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_root = require_within(
        RUNS_ROOT / args.run_id, RUNS_ROOT, "native_run_root"
    )
    before_path = (
        run_root / "evidence" / f"{args.tag}_import_preferences_before.json"
    )
    recovery_path = (
        run_root / "evidence" / f"{args.tag}_import_timeout_recovery.json"
    )
    report = {
        "schema": "SER_B50_IMPORT_TIMEOUT_RECOVERY_V1",
        "generated_utc": utc_now(),
        "run_id": args.run_id,
        "tag": args.tag,
        "expected_pid": args.expected_pid,
        "status": "B5_0_IMPORT_RECOVERY_HOLD",
        "forced_process_termination": False,
    }
    sw = None
    try:
        if recovery_path.exists():
            raise Phase0Error(f"recovery evidence exists: {recovery_path}")
        if not before_path.is_file():
            raise Phase0Error(f"preference snapshot missing: {before_path}")
        snapshot = json.loads(before_path.read_text(encoding="utf-8"))
        report["process_ids_before"] = sldworks_process_ids()
        if report["process_ids_before"] != [args.expected_pid]:
            raise Phase0Error(
                "recovery requires exactly the expected SolidWorks PID: "
                f"{report['process_ids_before']}"
            )
        sw = win32com.client.Dispatch("SldWorks.Application.32")
        connected_pid = int(sw.GetProcessID)
        report["connected_pid"] = connected_pid
        if connected_pid != args.expected_pid:
            try:
                sw.ExitApp()
            finally:
                sw = None
            raise Phase0Error(
                f"connected PID {connected_pid} != expected {args.expected_pid}"
            )
        before = snapshot["before"]
        for key, value in before["integer"].items():
            sw.SetUserPreferenceIntegerValue(int(key), int(value))
        for key, value in before["toggle"].items():
            sw.SetUserPreferenceToggle(int(key), bool(value))
        readback = {
            "integer": {
                str(key): int(sw.GetUserPreferenceIntegerValue(int(key)))
                for key in before["integer"]
            },
            "toggle": {
                str(key): bool(sw.GetUserPreferenceToggle(int(key)))
                for key in before["toggle"]
            },
        }
        report["restored"] = readback
        report["preference_restoration_pass"] = readback == before
        if readback != before:
            raise Phase0Error(
                f"preference recovery readback mismatch: {readback}"
            )
        sw.CloseAllDocuments(True)
        sw.ExitApp()
        sw = None
        deadline = time.monotonic() + 45.0
        remaining = sldworks_process_ids()
        while remaining and time.monotonic() < deadline:
            time.sleep(0.5)
            remaining = sldworks_process_ids()
        report["process_ids_after"] = remaining
        if remaining:
            raise Phase0Error(
                f"SolidWorks PID remains after exact COM ExitApp: {remaining}"
            )
        report["status"] = "B5_0_IMPORT_RECOVERY_PASS"
    except Exception as exc:
        report["exception"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        if sw is not None:
            try:
                sw.ExitApp()
            except Exception as exit_exc:
                report["exit_error"] = repr(exit_exc)
    finally:
        report["completed_utc"] = utc_now()
        write_json_once(recovery_path, report, run_root)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "B5_0_IMPORT_RECOVERY_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
