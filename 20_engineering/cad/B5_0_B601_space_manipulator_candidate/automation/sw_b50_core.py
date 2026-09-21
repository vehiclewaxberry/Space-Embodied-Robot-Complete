"""Fail-closed SolidWorks helpers for the B5.0 Phase0 smoke gate.

This module is intentionally independent from the frozen V2.x automation.
It may write only below a caller-supplied run root inside the B5.0 candidate
tree.  It never opens a pre-existing SolidWorks session and never terminates a
process forcibly.
"""
from __future__ import annotations

import gc
import hashlib
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CANDIDATE_ROOT = Path(__file__).resolve().parent.parent
PHASE0_RUNS_ROOT = CANDIDATE_ROOT / "phase0_runs"

SW_PROGID = "SldWorks.Application.32"
SW_TLB = ("{83A33D31-27C5-11CE-BFD4-00400513BB57}", 0, 32, 0)
EXPECTED_SW_MAJOR = 32

# swUserPreferenceStringValue_e, SolidWorks 2024 type library.
TEMPLATE_PREFERENCE = {"part": 8, "assembly": 9, "drawing": 10}
TEMPLATE_SUFFIX = {"part": ".prtdot", "assembly": ".asmdot", "drawing": ".drwdot"}
PINNED_TEMPLATE_PATH = {
    "part": Path(
        r"C:\ProgramData\SolidWorks\SOLIDWORKS 2024\templates\gb_part.prtdot"
    ),
    "assembly": Path(
        r"C:\ProgramData\SolidWorks\SOLIDWORKS 2024\templates\gb_assembly.asmdot"
    ),
    "drawing": Path(
        r"C:\ProgramData\SolidWorks\SOLIDWORKS 2024\templates\gb_a3.drwdot"
    ),
}
EXPECTED_TEMPLATE_SHA256 = {
    "part": "5DA21678EFE07EF465770630BEB4FFE540F23D47FCA07715F74D2AFDBEA87271",
    "assembly": "37DED9268BABC616A97BF9DA29BDCC2FFD60E8E4353670748F74A18A3BB450CC",
    "drawing": "B376D09B3937C02A57B6496D24F55FF0637243F7FAD215987F9E57610B10210E",
}

DOC_TYPE = {"part": 1, "assembly": 2, "drawing": 3}
OPEN_SILENT_READ_ONLY = 1 | 2
SAVE_CURRENT_VERSION = 0
SAVE_SILENT = 1

WRITER_MUTEX_NAME = r"Local\SER_B50_PHASE0_SOLIDWORKS_WRITER"
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


class Phase0Error(RuntimeError):
    """A fail-closed Phase0 precondition, COM, save, or validation error."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("PHASE0_%Y%m%dT%H%M%SZ")


def validate_run_id(run_id: str) -> str:
    if not RUN_ID_RE.fullmatch(run_id):
        raise Phase0Error(
            "run_id must match [A-Za-z0-9][A-Za-z0-9_.-]{0,63}"
        )
    return run_id


def _resolved(path: Path) -> Path:
    return path.resolve(strict=False)


def is_within(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath([str(_resolved(path)), str(_resolved(root))]) == str(
            _resolved(root)
        )
    except ValueError:
        return False


def require_within(path: Path, root: Path, label: str = "path") -> Path:
    candidate = _resolved(Path(path))
    if not is_within(candidate, root):
        raise Phase0Error(f"{label} escapes authorized root: {candidate}")
    return candidate


def phase0_run_root(run_id: str) -> Path:
    validate_run_id(run_id)
    return require_within(PHASE0_RUNS_ROOT / run_id, PHASE0_RUNS_ROOT, "run_root")


def require_new_run_root(run_id: str) -> Path:
    run_root = phase0_run_root(run_id)
    if run_root.exists():
        raise Phase0Error(f"run_root already exists; overwrite is forbidden: {run_root}")
    run_root.mkdir(parents=True, exist_ok=False)
    return run_root


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def artifact_record(path: Path, root: Path) -> dict[str, Any]:
    path = require_within(path, root, "artifact")
    if not path.is_file():
        raise Phase0Error(f"artifact is missing: {path}")
    size = path.stat().st_size
    if size <= 0:
        raise Phase0Error(f"artifact is empty: {path}")
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": size,
        "sha256": sha256_file(path),
    }


def write_json_once(path: Path, payload: dict[str, Any], root: Path) -> None:
    path = require_within(path, root, "json_output")
    if path.exists():
        raise Phase0Error(f"JSON evidence already exists; overwrite forbidden: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    if temporary.exists():
        raise Phase0Error(f"stale JSON temporary exists: {temporary}")
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _powershell_executable() -> str:
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    candidate = (
        system_root
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    return str(candidate) if candidate.is_file() else "powershell.exe"


def sldworks_process_ids() -> list[int]:
    command = (
        "$p=@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue | "
        "Select-Object -ExpandProperty Id); "
        "[pscustomobject]@{ids=@($p)} | ConvertTo-Json -Compress"
    )
    completed = subprocess.run(
        [
            _powershell_executable(),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            command,
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode != 0:
        raise Phase0Error(
            "cannot enumerate SLDWORKS processes: "
            + (completed.stderr.strip() or f"exit={completed.returncode}")
        )
    try:
        payload = json.loads(completed.stdout)
        return sorted({int(value) for value in payload.get("ids", [])})
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise Phase0Error(
            f"invalid process inventory output: {completed.stdout!r}"
        ) from exc


def wait_for_no_sldworks(timeout_seconds: float = 30.0) -> list[int]:
    deadline = time.monotonic() + timeout_seconds
    last: list[int] = []
    while time.monotonic() < deadline:
        last = sldworks_process_ids()
        if not last:
            return []
        time.sleep(0.5)
    return last


def get_com_member(obj: Any, name: str, *args: Any) -> Any:
    member = getattr(obj, name)
    return member(*args) if callable(member) else member


def _unpack_return(value: Any) -> tuple[Any, list[Any]]:
    if isinstance(value, tuple):
        return value[0], list(value[1:])
    return value, []


class SolidWorksSession:
    """One mutex-protected, newly launched, early-bound SolidWorks session."""

    def __init__(self, run_root: Path, visible: bool = False) -> None:
        self.run_root = require_within(run_root, CANDIDATE_ROOT, "session_run_root")
        self.visible = bool(visible)
        self.raw = None
        self.sw = None
        self.pythoncom = None
        self.win32api = None
        self.win32event = None
        self.mutex = None
        self.tlb_module = None
        self.com_initialized = False
        self.owner_pid: int | None = None
        self.pre_process_ids: list[int] = []
        self.post_process_ids: list[int] = []
        self.cleanup_errors: list[str] = []
        self.templates: dict[str, dict[str, Any]] = {}
        self.revision: str | None = None

    def __enter__(self) -> "SolidWorksSession":
        try:
            import pythoncom
            import win32api
            import win32event
            import winerror
            import win32com.client
            from win32com.client import gencache

            self.pythoncom = pythoncom
            self.win32api = win32api
            self.win32event = win32event

            self.mutex = win32event.CreateMutex(None, True, WRITER_MUTEX_NAME)
            if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
                win32api.CloseHandle(self.mutex)
                self.mutex = None
                raise Phase0Error("another B5.0 SolidWorks writer owns the mutex")

            self.pre_process_ids = sldworks_process_ids()
            if self.pre_process_ids:
                raise Phase0Error(
                    "exclusive launch requires zero pre-existing SLDWORKS processes; "
                    f"found {self.pre_process_ids}"
                )

            pythoncom.CoInitialize()
            self.com_initialized = True
            self.tlb_module = gencache.EnsureModule(*SW_TLB)
            if self.tlb_module is None:
                raise Phase0Error("SolidWorks 32.0 makepy module is unavailable")

            self.raw = win32com.client.DispatchEx(SW_PROGID)
            klass = getattr(self.tlb_module, "ISldWorks")
            ole = self.raw._oleobj_.QueryInterface(
                klass.CLSID, pythoncom.IID_IDispatch
            )
            self.sw = klass(ole)
            if type(self.sw).__name__ == "CDispatch":
                raise Phase0Error("SolidWorks object is not early-bound ISldWorks")

            deadline = time.monotonic() + 30.0
            last_error: Exception | None = None
            while time.monotonic() < deadline:
                try:
                    self.revision = str(get_com_member(self.sw, "RevisionNumber"))
                    break
                except Exception as exc:  # COM server still initializing.
                    last_error = exc
                    time.sleep(0.5)
            if self.revision is None:
                raise Phase0Error(
                    f"SolidWorks did not become ready: {last_error!r}"
                )
            try:
                major = int(self.revision.split(".", 1)[0])
            except ValueError as exc:
                raise Phase0Error(
                    f"unparseable SolidWorks revision: {self.revision}"
                ) from exc
            if major != EXPECTED_SW_MAJOR:
                raise Phase0Error(
                    f"SolidWorks major {major} != required {EXPECTED_SW_MAJOR}"
                )

            self.sw.Visible = self.visible
            try:
                self.sw.CommandInProgress = True
            except Exception as exc:
                raise Phase0Error(
                    f"cannot enable command-in-progress mode: {exc!r}"
                ) from exc

            self.owner_pid = int(get_com_member(self.sw, "GetProcessID"))
            deadline = time.monotonic() + 10.0
            observed: list[int] = []
            while time.monotonic() < deadline:
                observed = sldworks_process_ids()
                if self.owner_pid in observed:
                    break
                time.sleep(0.25)
            if self.owner_pid not in observed:
                raise Phase0Error(
                    f"owned SolidWorks PID {self.owner_pid} not observed in {observed}"
                )
            if get_com_member(self.sw, "ActiveDoc") is not None:
                raise Phase0Error("new SolidWorks instance unexpectedly has an active document")

            for kind, enum_value in TEMPLATE_PREFERENCE.items():
                preference_path_text = str(
                    get_com_member(
                        self.sw, "GetUserPreferenceStringValue", enum_value
                    )
                    or ""
                ).strip()
                preference_path = Path(preference_path_text)
                template = PINNED_TEMPLATE_PATH[kind]
                if not template.is_file():
                    raise Phase0Error(
                        f"pinned {kind} template is not a file: {template}"
                    )
                if template.suffix.lower() != TEMPLATE_SUFFIX[kind]:
                    raise Phase0Error(
                        f"{kind} template has wrong suffix: {template}"
                    )
                template_hash = sha256_file(template)
                if template_hash != EXPECTED_TEMPLATE_SHA256[kind]:
                    raise Phase0Error(
                        f"{kind} template hash drift: {template_hash} != "
                        f"{EXPECTED_TEMPLATE_SHA256[kind]}"
                    )
                self.templates[kind] = {
                    "preference_enum": enum_value,
                    "user_preference_path": preference_path_text,
                    "user_preference_is_file": preference_path.is_file(),
                    "user_preference_sha256": (
                        sha256_file(preference_path)
                        if preference_path.is_file()
                        else None
                    ),
                    "path": str(template.resolve()),
                    "bytes": template.stat().st_size,
                    "sha256": template_hash,
                    "selection_policy": "EXPLICIT_PINNED_TEMPLATE_NO_PREFERENCE_MUTATION",
                }
            return self
        except Exception:
            self._cleanup()
            raise

    def __exit__(self, exc_type, exc, traceback) -> bool:
        self._cleanup()
        if exc_type is None and self.cleanup_errors:
            raise Phase0Error("; ".join(self.cleanup_errors))
        return False

    def _cleanup(self) -> None:
        if self.sw is not None:
            try:
                self.sw.CloseAllDocuments(True)
            except Exception as exc:
                self.cleanup_errors.append(f"CloseAllDocuments:{exc!r}")
            try:
                self.sw.CommandInProgress = False
            except Exception as exc:
                self.cleanup_errors.append(f"CommandInProgressFalse:{exc!r}")
            try:
                self.sw.ExitApp()
            except Exception as exc:
                self.cleanup_errors.append(f"ExitApp:{exc!r}")
        elif self.raw is not None:
            try:
                self.raw.ExitApp()
            except Exception as exc:
                self.cleanup_errors.append(f"ExitAppRaw:{exc!r}")

        self.sw = None
        self.raw = None
        gc.collect()
        if self.pythoncom is not None and self.com_initialized:
            try:
                self.pythoncom.CoUninitialize()
            except Exception as exc:
                self.cleanup_errors.append(f"CoUninitialize:{exc!r}")
            self.com_initialized = False
        self.pythoncom = None

        try:
            self.post_process_ids = wait_for_no_sldworks(30.0)
            if self.post_process_ids:
                self.cleanup_errors.append(
                    f"SLDWORKS processes remain after ExitApp:{self.post_process_ids}"
                )
        except Exception as exc:
            self.cleanup_errors.append(f"post_process_check:{exc!r}")

        if self.mutex is not None and self.win32event is not None:
            try:
                self.win32event.ReleaseMutex(self.mutex)
            except Exception as exc:
                self.cleanup_errors.append(f"ReleaseMutex:{exc!r}")
            try:
                self.win32api.CloseHandle(self.mutex)
            except Exception as exc:
                self.cleanup_errors.append(f"CloseMutex:{exc!r}")
            self.mutex = None

    def info(self) -> dict[str, Any]:
        return {
            "revision": self.revision,
            "owner_pid": self.owner_pid,
            "pre_process_ids": self.pre_process_ids,
            "post_process_ids": self.post_process_ids,
            "early_bound_interface": (
                type(self.sw).__name__ if self.sw is not None else "released"
            ),
            "templates": self.templates,
            "cleanup_errors": list(self.cleanup_errors),
        }

    def cast(self, obj: Any, interface_name: str) -> Any:
        if obj is None:
            return None
        klass = getattr(self.tlb_module, interface_name)
        try:
            ole = obj._oleobj_.QueryInterface(
                klass.CLSID, self.pythoncom.IID_IDispatch
            )
            return klass(ole)
        except Exception as exc:
            raise Phase0Error(
                f"cannot cast COM object to {interface_name}: {exc!r}"
            ) from exc

    def new_document(self, kind: str) -> Any:
        if kind not in TEMPLATE_PREFERENCE:
            raise Phase0Error(f"unsupported document kind: {kind}")
        template = self.templates[kind]["path"]
        model = self.sw.NewDocument(template, 0, 0.0, 0.0)
        if model is None:
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                model = get_com_member(self.sw, "ActiveDoc")
                if model is not None:
                    break
                time.sleep(0.25)
        if model is None:
            raise Phase0Error(f"NewDocument returned no {kind} document")
        return self.cast(model, "IModelDoc2")

    def open_document(self, path: Path, kind: str) -> tuple[Any, dict[str, Any]]:
        path = require_within(path, self.run_root, "open_document")
        if not path.is_file():
            raise Phase0Error(f"document is missing: {path}")
        try:
            returned = self.sw.OpenDoc6(
                str(path),
                DOC_TYPE[kind],
                OPEN_SILENT_READ_ONLY,
                "",
                0,
                0,
            )
            model, outs = _unpack_return(returned)
            errors = int(outs[0]) if len(outs) > 0 else None
            warnings = int(outs[1]) if len(outs) > 1 else None
        except TypeError:
            from win32com.client import VARIANT

            errors_ref = VARIANT(self.pythoncom.VT_BYREF | self.pythoncom.VT_I4, 0)
            warnings_ref = VARIANT(
                self.pythoncom.VT_BYREF | self.pythoncom.VT_I4, 0
            )
            model = self.sw.OpenDoc6(
                str(path),
                DOC_TYPE[kind],
                OPEN_SILENT_READ_ONLY,
                "",
                errors_ref,
                warnings_ref,
            )
            errors, warnings = int(errors_ref.value), int(warnings_ref.value)
        if model is None:
            raise Phase0Error(
                f"OpenDoc6 returned no document: {path}; "
                f"errors={errors}, warnings={warnings}"
            )
        if errors not in (None, 0):
            raise Phase0Error(f"OpenDoc6 error {errors} for {path}")
        return self.cast(model, "IModelDoc2"), {
            "path": path.relative_to(self.run_root).as_posix(),
            "errors": errors,
            "warnings": warnings,
            "read_only": True,
        }

    def close_document(self, model: Any) -> None:
        title = str(get_com_member(model, "GetTitle"))
        self.sw.CloseDoc(title)

    def close_all_documents(self) -> None:
        self.sw.CloseAllDocuments(True)

    def save_as(
        self,
        model: Any,
        path: Path,
        *,
        require_zero_warnings: bool = True,
    ) -> dict[str, Any]:
        path = require_within(path, self.run_root, "save_target")
        if path.exists():
            raise Phase0Error(f"save target already exists: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        returned = model.Extension.SaveAs(
            str(path),
            SAVE_CURRENT_VERSION,
            SAVE_SILENT,
            None,
            0,
            0,
        )
        api_result, outs = _unpack_return(returned)
        if len(outs) < 2:
            raise Phase0Error(
                f"SaveAs did not return error/warning outputs for {path}: {returned!r}"
            )
        errors, warnings = int(outs[0]), int(outs[1])
        if not bool(api_result) or errors != 0:
            raise Phase0Error(
                "initial SaveAs failed: "
                f"path={path}, api_ok={bool(api_result)}, "
                f"errors={errors}, warnings={warnings}"
            )
        if require_zero_warnings and warnings != 0:
            raise Phase0Error(
                "initial SaveAs warning is not accepted in Phase0: "
                f"path={path}, warnings={warnings}"
            )

        native_finalize: dict[str, Any] | None = None
        if path.suffix.lower() in {".sldprt", ".sldasm", ".slddrw"}:
            if not model.ForceRebuild3(True):
                raise Phase0Error(
                    f"full rebuild failed before final native save: {path}"
                )
            returned_final = model.Save3(SAVE_SILENT, 0, 0)
            final_ok, final_outs = _unpack_return(returned_final)
            if len(final_outs) < 2:
                raise Phase0Error(
                    f"Save3 did not return error/warning outputs for {path}: "
                    f"{returned_final!r}"
                )
            final_errors = int(final_outs[0])
            final_warnings = int(final_outs[1])
            native_finalize = {
                "api_ok": bool(final_ok),
                "errors": final_errors,
                "warnings": final_warnings,
                "full_rebuild": True,
            }
            if not bool(final_ok) or final_errors != 0:
                raise Phase0Error(
                    f"final native Save3 failed: path={path}, "
                    f"result={native_finalize}"
                )
            if require_zero_warnings and final_warnings != 0:
                raise Phase0Error(
                    f"final native Save3 warning is not accepted: path={path}, "
                    f"result={native_finalize}"
                )

        deadline = time.monotonic() + 20.0
        last_size = -1
        stable_count = 0
        while time.monotonic() < deadline:
            if path.is_file():
                size = path.stat().st_size
                if size > 0 and size == last_size:
                    stable_count += 1
                else:
                    stable_count = 0
                last_size = size
                if stable_count >= 2:
                    break
            time.sleep(0.25)
        record = {
            "path": path.relative_to(self.run_root).as_posix(),
            "api_ok": bool(api_result),
            "errors": errors,
            "warnings": warnings,
            "native_finalize": native_finalize,
            "exists": path.is_file(),
            "bytes": path.stat().st_size if path.is_file() else 0,
            "sha256": sha256_file(path) if path.is_file() else None,
        }
        if not record["exists"] or record["bytes"] <= 0:
            raise Phase0Error(f"SaveAs produced no non-empty artifact: {record}")
        return record

    def set_text_properties(self, model: Any, properties: dict[str, Any]) -> None:
        manager = model.Extension.CustomPropertyManager("")
        for key, value in properties.items():
            result = manager.Add3(str(key), 30, str(value), 2)
            if int(result) < 0:
                raise Phase0Error(f"cannot set custom property {key}: result={result}")

    def read_text_property(self, model: Any, name: str) -> str | None:
        manager = model.Extension.CustomPropertyManager("")
        try:
            returned = manager.Get5(name, False, "", "")
            if isinstance(returned, tuple):
                values = list(returned[1:])
                if len(values) >= 2:
                    return str(values[1] or values[0] or "")
        except Exception:
            pass
        try:
            value = manager.Get(name)
            return None if value is None else str(value)
        except Exception:
            return None

    def activate_document(self, title: str) -> Any:
        returned = self.sw.ActivateDoc3(title, False, 0, 0)
        model, _ = _unpack_return(returned)
        if model is None:
            model = get_com_member(self.sw, "ActiveDoc")
        if model is None:
            raise Phase0Error(f"cannot activate document: {title}")
        return self.cast(model, "IModelDoc2")


IDENTITY_TRANSFORM_16 = [
    1.0,
    0.0,
    0.0,
    0.0,
    1.0,
    0.0,
    0.0,
    0.0,
    1.0,
    0.0,
    0.0,
    0.0,
    1.0,
    0.0,
    0.0,
    0.0,
]


def add_component_identity(
    session: SolidWorksSession, assembly_model: Any, part_path: Path
) -> dict[str, Any]:
    part_path = require_within(part_path, session.run_root, "component_part")
    part_model, open_record = session.open_document(part_path, "part")
    part_title = str(get_com_member(part_model, "GetTitle"))
    assembly_title = str(get_com_member(assembly_model, "GetTitle"))
    session.activate_document(assembly_title)
    assembly = session.cast(assembly_model, "IAssemblyDoc")
    component = assembly.AddComponent5(
        str(part_path), 0, "", False, "", 0.0, 0.0, 0.0
    )
    if component is None:
        raise Phase0Error(f"AddComponent5 failed: {part_path}")
    component = session.cast(component, "IComponent2")
    math_utility = session.cast(
        get_com_member(session.sw, "GetMathUtility"), "IMathUtility"
    )
    transform = math_utility.CreateTransform(IDENTITY_TRANSFORM_16)
    try:
        component.Transform2 = transform
    except Exception:
        if not component.SetTransformAndSolve2(transform):
            raise Phase0Error("cannot apply identity component transform")
    assembly_model.ClearSelection2(True)
    if not component.Select4(True, None, False):
        raise Phase0Error("cannot select smoke component for fixing")
    assembly.FixComponent()
    assembly_model.ClearSelection2(True)
    if not assembly_model.ForceRebuild3(False):
        raise Phase0Error("assembly rebuild failed after component insertion")
    component_path = Path(str(get_com_member(component, "GetPathName"))).resolve()
    if component_path != part_path.resolve():
        raise Phase0Error(
            f"component reference mismatch: {component_path} != {part_path}"
        )
    session.sw.CloseDoc(part_title)
    return {
        "source_open": open_record,
        "component_path": component_path.relative_to(session.run_root).as_posix(),
        "transform": "IDENTITY_4X4",
        "fixed": True,
    }
