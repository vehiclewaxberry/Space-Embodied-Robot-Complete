#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Strict Session-B cold-reopen verifier for the F3R2 V5 G0 smoke part.

This program can only attach to an existing, manually started SOLIDWORKS
session.  It rejects the Session-A process, requires an empty SOLIDWORKS 2024
SP05 session, opens the frozen smoke part read-only, rebuilds and verifies the
native solid, closes it, records evidence, and deletes only that temporary CAD
asset.  It never creates a V5 release tree and never starts or exits SOLIDWORKS.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
ENGINEERING = ROOT / "20_engineering"
RUN_DIR = ENGINEERING / "_MFINAL_G0_SMOKE_20260809T172928_P4E8"
PART = RUN_DIR / "G0_SMOKE_20X20X10.SLDPRT"
SESSION_A_RECEIPT = RUN_DIR / "G0_SMOKE_SESSION_A_RECEIPT.json"
SESSION_A_ADDENDUM = RUN_DIR / "G0_SMOKE_SESSION_A_PROCESS_ADDENDUM.json"
SESSION_A_PID = 10332
SESSION_A_START_LOCAL = "2026-08-09T16:40:33.5328771+08:00"
SESSION_A_RECEIPT_SHA256 = "AA070605E7576A79239E0877DA855FCC3F7693E9FCD906E8EFF93F9CC2880F87"
PART_BYTES = 59102
PART_SHA256 = "797A28B0FD24239A14037690ADCE4A4D0DC4504AC2946B7D59C020D83E709656"
EXPECTED_FEATURE_COUNT = 19
EXPECTED_MAJOR = 32
MIN_AVAILABLE_GIB = 6.0
SOLIDWORKS_PROG_ID = "SldWorks.Application"
SOLIDWORKS_EXE = Path(r"F:\Windows_profile\solidworks\SOLIDWORKS\SLDWORKS.exe")

PREDELETE_RECEIPT = RUN_DIR / "G0_SMOKE_SESSION_B_PREDELETE_RECEIPT.json"
FINAL_RECEIPT = RUN_DIR / "G0_SOLIDWORKS_NATIVE_EXECUTION_READY.json"

PROTECTED = (
    {
        "name": "accepted_b601_urdf",
        "path": ENGINEERING / "cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
        "raw_sha256": "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164",
        "lf_sha256": "408147DDC9CC0BBA0FACBF864C559A54D1712262703BA41251514A4303B5A3A4",
    },
    {
        "name": "mass_inertia_budget",
        "path": ENGINEERING / "stage1_spacecraft_layout/04_mass_inertia_budget/mass_inertia_budget_v1.csv",
        "raw_sha256": "073C802527E35C9495188EEFD5D8BA51F524D326142CF2AB31E436BAD0899392",
    },
    {
        "name": "v2_2_native_donor_top",
        "path": ENGINEERING / "cad/Space_Embodied_Robot_CAD_V2_2_NATIVE/Assembly/Space_Embodied_Service_Spacecraft_V2_2.SLDASM",
        "raw_sha256": "30C09B50A0D2967EC1F48050CAAC34D12A43565C44978D54E3785595202DEF7A",
    },
    {
        "name": "b51_articulated_arm_donor",
        "path": ENGINEERING / "cad/B5_1_B601_interface_closure_candidate/03_CAD/native_articulated/B51_ARTICULATED_20260728T008/assembly/B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM",
        "raw_sha256": "603B87BBD4398FDDB3F732FFBFA7E1C080ED91ED6E0A026D56CBDCBA08DE2E22",
    },
    {
        "name": "f3r1_frozen_top",
        "path": ENGINEERING / "F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806/03_native_cad/F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION_V3_CONFIGURED.SLDASM",
        "raw_sha256": "19D85E9C703BEC107396AE84DAB7B12DE5722434FC7D5474B3A5A144A1B590D0",
    },
    {
        "name": "f3r2_frozen_top",
        "path": ENGINEERING / "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.SLDASM",
        "raw_sha256": "19D85E9C703BEC107396AE84DAB7B12DE5722434FC7D5474B3A5A144A1B590D0",
    },
)


class GateError(RuntimeError):
    def __init__(self, code: str, message: str, detail: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.code = code
        self.detail = detail or {}


class MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path, *, normalize_lf: bool = False) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        if normalize_lf:
            digest.update(stream.read().replace(b"\r\n", b"\n"))
        else:
            for block in iter(lambda: stream.read(1 << 20), b""):
                digest.update(block)
    return digest.hexdigest().upper()


def com_value(obj: Any, name: str, *args: Any) -> Any:
    member = getattr(obj, name)
    return member(*args) if callable(member) else member


def wrap_interface(obj: Any, interface_name: str, sw_types: Any, pythoncom: Any) -> Any:
    klass = getattr(sw_types, interface_name)
    ole = obj._oleobj_.QueryInterface(klass.CLSID, pythoncom.IID_IDispatch)
    return klass(ole)


def as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, (tuple, list)):
        return list(value)
    return [value]


def available_memory_gib() -> float:
    status = MemoryStatusEx()
    status.dwLength = ctypes.sizeof(MemoryStatusEx)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise GateError("MEMORY_QUERY_FAILED", "GlobalMemoryStatusEx returned false")
    return status.ullAvailPhys / (1024.0 ** 3)


def memory_gate() -> List[float]:
    samples: List[float] = []
    for index in range(10):
        samples.append(round(available_memory_gib(), 6))
        if index < 9:
            time.sleep(0.25)
    if not all(value >= MIN_AVAILABLE_GIB for value in samples):
        raise GateError(
            "RESOURCE_GATE_HOLD",
            "all Session-B samples must be at least 6 GiB",
            {"samples_gib": samples, "minimum_gib": MIN_AVAILABLE_GIB},
        )
    return samples


def validate_protected() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in PROTECTED:
        path: Path = item["path"]
        exists = path.is_file()
        raw = sha256(path) if exists else None
        lf = sha256(path, normalize_lf=True) if exists and item.get("lf_sha256") else None
        passed = exists and raw == item["raw_sha256"] and (
            item.get("lf_sha256") is None or lf == item["lf_sha256"]
        )
        rows.append(
            {
                "name": item["name"],
                "path": str(path).replace("\\", "/"),
                "bytes": path.stat().st_size if exists else None,
                "raw_sha256": raw,
                "lf_sha256": lf,
                "pass": passed,
            }
        )
    if not all(row["pass"] for row in rows):
        raise GateError(
            "PROTECTED_HASH_DRIFT",
            "protected PRE/POST identity changed",
            {"failures": [row for row in rows if not row["pass"]]},
        )
    return rows


def validate_session_a_evidence() -> Dict[str, Any]:
    if RUN_DIR.resolve().parent != ENGINEERING.resolve():
        raise GateError("UNSAFE_RUN_DIR", "smoke run is not directly under 20_engineering")
    if not SESSION_A_RECEIPT.is_file() or sha256(SESSION_A_RECEIPT) != SESSION_A_RECEIPT_SHA256:
        raise GateError("SESSION_A_RECEIPT_IDENTITY_FAIL", "Session-A receipt changed")
    receipt = json.loads(SESSION_A_RECEIPT.read_text(encoding="utf-8"))
    if receipt.get("verdict") != "G0_SMOKE_SESSION_A_PASS_AWAITING_SESSION_B":
        raise GateError("SESSION_A_VERDICT_FAIL", "Session-A receipt is not a PASS")
    if not SESSION_A_ADDENDUM.is_file():
        raise GateError("SESSION_A_ADDENDUM_MISSING", "Session-A process addendum is missing")
    if not PART.is_file() or PART.stat().st_size != PART_BYTES or sha256(PART) != PART_SHA256:
        raise GateError("SMOKE_PART_IDENTITY_FAIL", "smoke part bytes/hash changed")
    if PREDELETE_RECEIPT.exists() or FINAL_RECEIPT.exists():
        raise GateError("SESSION_B_RECEIPT_ALREADY_EXISTS", "Session-B is not re-entrant")
    if list(ENGINEERING.glob("F3R2_V5*")):
        raise GateError("V5_ALREADY_EXISTS_FAIL", "V5 must not exist before G0 closes")
    return {
        "session_a_receipt_sha256": SESSION_A_RECEIPT_SHA256,
        "session_a_pid": SESSION_A_PID,
        "session_a_start_local": SESSION_A_START_LOCAL,
        "smoke_part_bytes": PART_BYTES,
        "smoke_part_sha256": PART_SHA256,
    }


def write_json_exclusive(path: Path, payload: Dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def main() -> int:
    result: Dict[str, Any] = {
        "schema": "F3R2_V5_G0_SMOKE_SESSION_B_V1",
        "timestamp_utc": utc_now(),
        "run_dir": str(RUN_DIR).replace("\\", "/"),
        "safety": {
            "attach_only": True,
            "script_start_solidworks": False,
            "script_exit_solidworks": False,
            "changes_visible_or_user_control": False,
            "open_read_only": True,
            "v5_release_created": False,
        },
    }
    pythoncom = None
    sw = None
    model = None
    own_title: Optional[str] = None
    try:
        result["session_a_evidence"] = validate_session_a_evidence()
        result["protected_pre"] = validate_protected()
        result["memory_samples_gib"] = memory_gate()

        import psutil  # type: ignore
        import pythoncom as _pythoncom  # type: ignore
        import win32com.client  # type: ignore
        from win32com.client import gencache  # type: ignore

        pythoncom = _pythoncom
        pythoncom.CoInitialize()
        try:
            raw_sw = win32com.client.GetActiveObject(SOLIDWORKS_PROG_ID)
        except Exception as exc:
            raise GateError("ATTACH_REQUIRED", "no manually started Session-B SOLIDWORKS", {"exception": repr(exc)}) from exc
        sw_types = gencache.GetModuleForTypelib(
            "{83A33D31-27C5-11CE-BFD4-00400513BB57}", 0, 32, 0
        )
        sw = wrap_interface(raw_sw, "ISldWorks", sw_types, pythoncom)
        revision = str(com_value(sw, "RevisionNumber"))
        major = int(revision.split(".", 1)[0])
        current_pid = int(com_value(sw, "GetProcessID"))
        process = psutil.Process(current_pid)
        current_exe = Path(process.exe())
        current_start_utc = datetime.fromtimestamp(
            process.create_time(), tz=timezone.utc
        ).isoformat()
        doc_count = int(com_value(sw, "GetDocumentCount"))
        active_is_null = sw.ActiveDoc is None
        result["session_b_process"] = {
            "pid": current_pid,
            "process_start_utc": current_start_utc,
            "executable": str(current_exe).replace("\\", "/"),
            "revision": revision,
            "major": major,
            "doc_count_pre": doc_count,
            "active_doc_is_null_pre": active_is_null,
            "different_pid_from_session_a": current_pid != SESSION_A_PID,
        }
        if current_pid == SESSION_A_PID:
            raise GateError(
                "SESSION_B_NOT_NEW_PROCESS",
                "current SOLIDWORKS PID is still the Session-A PID",
                {"current_pid": current_pid, "session_a_pid": SESSION_A_PID},
            )
        if major != EXPECTED_MAJOR:
            raise GateError("SOLIDWORKS_VERSION_FAIL", "Session B must be SOLIDWORKS major 32")
        if os.path.normcase(str(current_exe)) != os.path.normcase(str(SOLIDWORKS_EXE)):
            raise GateError("SOLIDWORKS_EXE_FAIL", "unexpected SOLIDWORKS executable")
        if doc_count != 0 or not active_is_null:
            raise GateError("SESSION_B_NOT_CLEAN", "Session B must start with no open document")
        if available_memory_gib() < MIN_AVAILABLE_GIB:
            raise GateError("RESOURCE_GATE_HOLD", "memory fell below 6 GiB immediately before cold reopen")

        opened = sw.OpenDoc6(str(PART), 1, 3, "", 0, 0)
        if not isinstance(opened, tuple) or len(opened) < 3:
            raise GateError("OPEN_RESULT_SHAPE_FAIL", "typed OpenDoc6 did not return model/errors/warnings")
        model = opened[0]
        open_errors = int(opened[1])
        open_warnings = int(opened[2])
        if model is None or open_errors != 0 or open_warnings != 0:
            raise GateError(
                "COLD_REOPEN_FAIL",
                "OpenDoc6 did not return a clean read-only open",
                {"model_is_null": model is None, "errors": open_errors, "warnings": open_warnings},
            )
        model = wrap_interface(model, "IModelDoc2", sw_types, pythoncom)
        own_title = str(com_value(model, "GetTitle"))
        opened_path = Path(str(com_value(model, "GetPathName"))).resolve()
        if os.path.normcase(str(opened_path)) != os.path.normcase(str(PART.resolve())):
            raise GateError("OPENED_WRONG_DOCUMENT", "cold reopen path is not the smoke part")
        if int(com_value(model, "GetType")) != 1:
            raise GateError("OPENED_WRONG_TYPE", "cold reopened document is not a part")
        rebuild_ok = bool(com_value(model, "EditRebuild3"))
        if not rebuild_ok:
            raise GateError("COLD_REBUILD_FAIL", "EditRebuild3 returned false")
        feature_count = int(com_value(model, "GetFeatureCount"))
        if feature_count != EXPECTED_FEATURE_COUNT:
            raise GateError(
                "FEATURE_COUNT_DRIFT",
                "cold reopened feature count changed",
                {"actual": feature_count, "expected": EXPECTED_FEATURE_COUNT},
            )
        part = wrap_interface(model, "IPartDoc", sw_types, pythoncom)
        bodies = as_list(part.GetBodies2(0, False))
        if len(bodies) != 1:
            raise GateError("COLD_BODY_COUNT_FAIL", "expected one cold-reopened solid body", {"count": len(bodies)})
        body = bodies[0]
        if hasattr(body, "IsSolidBody") and not bool(com_value(body, "IsSolidBody")):
            raise GateError("COLD_BODY_NOT_SOLID", "cold-reopened body is not solid")
        box = [float(value) for value in as_list(com_value(body, "GetBodyBox"))]
        if len(box) != 6:
            raise GateError("COLD_BODY_BOX_FAIL", "GetBodyBox did not return six values")
        dimensions = sorted(
            [abs(box[3] - box[0]), abs(box[4] - box[1]), abs(box[5] - box[2])]
        )
        expected_dimensions = [0.010, 0.020, 0.020]
        if any(
            abs(actual - expected) > 0.00005
            for actual, expected in zip(dimensions, expected_dimensions)
        ):
            raise GateError(
                "COLD_DIMENSION_FAIL",
                "cold-reopened body is not 20 x 20 x 10 mm",
                {"dimensions_m_sorted": dimensions},
            )
        save_flag_after_rebuild = bool(com_value(model, "GetSaveFlag"))
        result["cold_reopen"] = {
            "open_options": ["SILENT", "READ_ONLY"],
            "open_errors": open_errors,
            "open_warnings": open_warnings,
            "title": own_title,
            "path": str(opened_path).replace("\\", "/"),
            "rebuild_ok": rebuild_ok,
            "feature_count": feature_count,
            "solid_body_count": len(bodies),
            "dimensions_m_sorted": dimensions,
            "save_flag_after_read_only_rebuild": save_flag_after_rebuild,
        }

        body = None
        bodies = []
        part = None
        sw.CloseDoc(own_title)
        model = None
        time.sleep(0.5)
        if int(com_value(sw, "GetDocumentCount")) != 0 or sw.ActiveDoc is not None:
            raise GateError("SESSION_B_CLOSE_FAIL", "cold-reopened document did not close")
        if not PART.is_file() or PART.stat().st_size != PART_BYTES or sha256(PART) != PART_SHA256:
            raise GateError("POST_OPEN_PART_IDENTITY_FAIL", "read-only cold reopen changed the smoke part")
        result["protected_post"] = validate_protected()
        result["solidworks_post"] = {
            "doc_count": int(com_value(sw, "GetDocumentCount")),
            "active_doc_is_null": sw.ActiveDoc is None,
        }
        result["verdict"] = "G0_SMOKE_SESSION_B_COLD_REOPEN_PASS_PENDING_TEMP_DELETE"
        result["temporary_asset"] = {
            "path": str(PART).replace("\\", "/"),
            "bytes": PART_BYTES,
            "sha256": PART_SHA256,
            "delete_pending": True,
        }
        write_json_exclusive(PREDELETE_RECEIPT, result)
        predelete_sha = sha256(PREDELETE_RECEIPT)

        resolved_part = PART.resolve(strict=True)
        if resolved_part.parent != RUN_DIR.resolve() or resolved_part.name != "G0_SMOKE_20X20X10.SLDPRT":
            raise GateError("TEMP_DELETE_SCOPE_FAIL", "refusing to delete outside exact smoke target")
        resolved_part.unlink()
        if PART.exists():
            raise GateError("TEMP_DELETE_FAIL", "temporary smoke part still exists after delete")

        result["timestamp_final_utc"] = utc_now()
        result["verdict"] = "G0_SOLIDWORKS_NATIVE_EXECUTION_READY"
        result["temporary_asset"].update(
            {"delete_pending": False, "deleted": True, "exists_after_delete": False}
        )
        result["predelete_receipt"] = {
            "path": str(PREDELETE_RECEIPT).replace("\\", "/"),
            "sha256": predelete_sha,
        }
        result["next_authorized_action"] = "CREATE_NEW_EXCLUSIVE_V5_RELEASE_ROOT"
        write_json_exclusive(FINAL_RECEIPT, result)
        print(
            json.dumps(
                {
                    **result,
                    "final_receipt": str(FINAL_RECEIPT).replace("\\", "/"),
                    "final_receipt_sha256": sha256(FINAL_RECEIPT),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except GateError as exc:
        result.update({"verdict": exc.code, "reason": str(exc), "detail": exc.detail})
        failure = RUN_DIR / f"G0_SMOKE_SESSION_B_FAIL_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')}.json"
        try:
            write_json_exclusive(failure, result)
            result["failure_receipt"] = str(failure).replace("\\", "/")
        except Exception as receipt_exc:
            result["failure_receipt_error"] = repr(receipt_exc)
        print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
        return 3
    except Exception as exc:
        result.update(
            {
                "verdict": "UNEXPECTED_SESSION_B_EXCEPTION",
                "exception_type": type(exc).__name__,
                "reason": repr(exc),
                "traceback": traceback.format_exc(),
            }
        )
        failure = RUN_DIR / f"G0_SMOKE_SESSION_B_FAIL_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')}.json"
        try:
            write_json_exclusive(failure, result)
            result["failure_receipt"] = str(failure).replace("\\", "/")
        except Exception as receipt_exc:
            result["failure_receipt_error"] = repr(receipt_exc)
        print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    finally:
        if model is not None and sw is not None and own_title:
            try:
                sw.CloseDoc(str(com_value(model, "GetTitle") or own_title))
            except Exception:
                pass
        model = None
        sw = None
        if pythoncom is not None:
            pythoncom.CoUninitialize()


if __name__ == "__main__":
    raise SystemExit(main())
