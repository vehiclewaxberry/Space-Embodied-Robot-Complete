#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fresh-process, read-only verifier for one V5 solar-array R2 attempt.

The verifier never starts SOLIDWORKS and never writes a CAD document.  It
attaches to an explicitly named, already-running empty SOLIDWORKS 2024 SP5
process, proves that this process is different from the build process recorded
in an explicit build-stage receipt, opens every staged native document
read-only, and reads configuration transforms, mates, references, and hashes.

The build-stage receipt consumed by this script is deliberately strict.  It is
the hand-off contract between the future transactional R2 builder and this
independent verifier.  All PASS/FAIL evidence is append-only and remains below
the supplied attempt root; no global release receipt is published here.

Commands
--------

``audit`` performs only filesystem/source checks and never imports COM.
``verify`` is attach-only and requires ``--expected-pid``.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


sys.dont_write_bytecode = True

RUN_ROOT = Path(
    r"F:\China Graduate Future Flight Vehicle Innovation Competition"
    r"\20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
)
ATTEMPTS_ROOT = RUN_ROOT / "13_validation" / "solar_r2_attempts"
SOLIDWORKS_EXE = Path(r"F:\Windows_profile\solidworks\SOLIDWORKS\SLDWORKS.exe")

EXPECTED_BUILD_SCHEMA = "F3R2_V5_SOLAR_R2_BUILD_STAGE_RECEIPT_V1"
EXPECTED_BUILD_VERDICT = "V5_SOLAR_R2_BUILD_STAGE_SAME_PID_PASS"
EXPECTED_SW_REVISION_PREFIX = "32.5."
EXPECTED_ARTIFACT_COUNTS = {"SLDPRT": 34, "SLDASM": 2}
EXPECTED_CONFIGS: Tuple[str, ...] = (
    "SOLAR_STOWED",
    "SOLAR_DEPLOY_STAGE1",
    "SOLAR_DEPLOY_STAGE2",
    "SOLAR_DEPLOYED_NOMINAL",
    "SOLAR_LEFT_FAIL",
    "SOLAR_RIGHT_FAIL",
    "SOLAR_BOTH_FAIL",
)
STATE_ANGLES: Dict[str, Dict[str, Tuple[float, float, float]]] = {
    "SOLAR_STOWED": {"L": (0.0, 0.0, 0.0), "R": (0.0, 0.0, 0.0)},
    "SOLAR_DEPLOY_STAGE1": {"L": (90.0, 0.0, 0.0), "R": (90.0, 0.0, 0.0)},
    "SOLAR_DEPLOY_STAGE2": {"L": (90.0, 90.0, 0.0), "R": (90.0, 90.0, 0.0)},
    "SOLAR_DEPLOYED_NOMINAL": {"L": (90.0, 90.0, 90.0), "R": (90.0, 90.0, 90.0)},
    "SOLAR_LEFT_FAIL": {"L": (0.0, 0.0, 0.0), "R": (90.0, 90.0, 90.0)},
    "SOLAR_RIGHT_FAIL": {"L": (90.0, 90.0, 90.0), "R": (0.0, 0.0, 0.0)},
    "SOLAR_BOTH_FAIL": {"L": (0.0, 0.0, 0.0), "R": (0.0, 0.0, 0.0)},
}

SW_PROG_ID = "SldWorks.Application"
SW_TLB = ("{83A33D31-27C5-11CE-BFD4-00400513BB57}", 0, 32, 0)
SW_DOC_PART = 1
SW_DOC_ASSEMBLY = 2
SW_OPEN_SILENT = 1
SW_OPEN_READ_ONLY = 2
TRANS_TOL_MM = 0.05
ROT_TOL_DEG = 0.1

PASS_RELATIVE = Path("evidence/F3R2_V5_SOLAR_R2_FRESH_VERIFY_PASS.json")
FAIL_GLOB = "F3R2_V5_SOLAR_R2_FRESH_VERIFY_FAIL_*.json"

# Direct calls to these CAD/application mutation families are forbidden in this
# source.  The AST audit also checks indirect calls made through ``value``.
FORBIDDEN_CALL_PREFIXES: Tuple[str, ...] = (
    "settransform",
    "save",
    "add3",
    "addmate",
    "replacecomponents",
    "newdocument",
    "exitapp",
    "delete",
    "editdelete",
    "fixcomponent",
    "unfixcomponent",
    "dispatch",
)


class VerifyError(RuntimeError):
    def __init__(self, code: str, message: str, detail: Optional[Mapping[str, Any]] = None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.detail = dict(detail or {})


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def norm(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def file_fact(path: Path) -> Dict[str, Any]:
    resolved = path.resolve()
    return {"path": norm(resolved), "bytes": resolved.stat().st_size, "sha256": sha256(resolved)}


def write_json_once(path: Path, payload: Mapping[str, Any], attempt_root: Path) -> None:
    resolved_parent = path.parent.resolve()
    if attempt_root.resolve() not in resolved_parent.parents and resolved_parent != attempt_root.resolve():
        raise VerifyError("EVIDENCE_SCOPE_FAIL", "evidence target escapes attempt root", {"path": norm(path)})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def load_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise VerifyError("JSON_ROOT_FAIL", "JSON root must be an object", {"path": norm(path)})
    return payload


def is_under(path: Path, root: Path) -> bool:
    candidate = path.resolve()
    parent = root.resolve()
    return candidate == parent or parent in candidate.parents


def assert_attempt_root(path: Path) -> Path:
    raw = path.absolute()
    resolved = raw.resolve()
    if not resolved.is_dir():
        raise VerifyError("ATTEMPT_ROOT_MISSING", "attempt root is not an existing directory", {"path": str(raw)})
    if resolved == ATTEMPTS_ROOT.resolve() or not is_under(resolved, ATTEMPTS_ROOT):
        raise VerifyError(
            "ATTEMPT_ROOT_SCOPE_FAIL",
            "attempt root must be a child of the controlled solar R2 attempts directory",
            {"path": norm(resolved), "required_parent": norm(ATTEMPTS_ROOT)},
        )
    if raw.is_symlink():
        raise VerifyError("ATTEMPT_ROOT_SYMLINK_FAIL", "attempt root may not be a symlink", {"path": str(raw)})
    cursor = raw
    while cursor != ATTEMPTS_ROOT.absolute() and cursor != cursor.parent:
        if cursor.is_symlink():
            raise VerifyError("ATTEMPT_PATH_SYMLINK_FAIL", "attempt path contains a symlink", {"path": str(cursor)})
        cursor = cursor.parent
    return resolved


def assert_build_receipt(attempt_root: Path, path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_file() or not is_under(resolved, attempt_root):
        raise VerifyError(
            "BUILD_RECEIPT_SCOPE_FAIL",
            "build receipt must be an existing file inside the attempt root",
            {"path": norm(resolved), "attempt_root": norm(attempt_root)},
        )
    if path.absolute().is_symlink():
        raise VerifyError("BUILD_RECEIPT_SYMLINK_FAIL", "build receipt may not be a symlink", {"path": str(path)})
    return resolved


def value(obj: Any, name: str, *args: Any) -> Any:
    member = getattr(obj, name)
    return member(*args) if callable(member) else member


def unpack(result: Any) -> Tuple[Any, List[Any]]:
    if isinstance(result, tuple):
        return result[0], list(result[1:])
    return result, []


def as_list(value_in: Any) -> List[Any]:
    if value_in is None:
        return []
    return list(value_in) if isinstance(value_in, (tuple, list)) else [value_in]


def wrap(obj: Any, interface: str, types: Any, pythoncom: Any) -> Any:
    klass = getattr(types, interface)
    ole = obj._oleobj_.QueryInterface(klass.CLSID, pythoncom.IID_IDispatch)
    return klass(ole)


def direct_call_name(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def is_forbidden_api(name: str) -> bool:
    lowered = name.casefold()
    return any(lowered.startswith(prefix) for prefix in FORBIDDEN_CALL_PREFIXES)


def source_policy_audit() -> Dict[str, Any]:
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(Path(__file__)))
    violations: List[Dict[str, Any]] = []
    local_imports: List[Dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            called = direct_call_name(node.func)
            if called and is_forbidden_api(called):
                violations.append({"line": node.lineno, "kind": "direct_call", "api": called})
            if called in {"value", "getattr"} and len(node.args) >= 2:
                member = node.args[1]
                if isinstance(member, ast.Constant) and isinstance(member.value, str) and is_forbidden_api(member.value):
                    violations.append({"line": node.lineno, "kind": "indirect_call", "api": member.value})
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("F3R2_"):
                    local_imports.append({"line": node.lineno, "module": alias.name})
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("F3R2_"):
                local_imports.append({"line": node.lineno, "module": node.module})
    checks = {
        "forbidden_mutating_com_calls_absent": not violations,
        "mutation_capable_local_helpers_not_imported": not local_imports,
        "attach_only_prog_id_present": SW_PROG_ID in source,
        "read_only_open_flag_present": "SW_OPEN_READ_ONLY" in source,
        "attempt_local_evidence_policy_present": "EVIDENCE_SCOPE_FAIL" in source,
    }
    return {
        "script": file_fact(Path(__file__)),
        "checks": checks,
        "violations": violations,
        "local_helper_imports": local_imports,
        "solidworks_touched": False,
        "verdict": "V5_SOLAR_R2_FRESH_VERIFY_SOURCE_POLICY_PASS" if all(checks.values()) else "V5_SOLAR_R2_FRESH_VERIFY_SOURCE_POLICY_FAIL",
    }


def resolve_relative_artifact(attempt_root: Path, relative: Any) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise VerifyError("ARTIFACT_RELATIVE_PATH_FAIL", "artifact relative_path must be a non-empty relative string", {"value": relative})
    resolved = (attempt_root / relative).resolve()
    if not is_under(resolved, attempt_root) or not resolved.is_file():
        raise VerifyError("ARTIFACT_SCOPE_FAIL", "artifact is missing or outside attempt root", {"relative_path": relative, "resolved": norm(resolved)})
    return resolved


def check_expected_fact(path: Path, row: Mapping[str, Any], label: str) -> Dict[str, Any]:
    actual = file_fact(path)
    expected_bytes = int(row.get("bytes", -1))
    expected_sha = str(row.get("sha256", "")).upper()
    if actual["bytes"] != expected_bytes or actual["sha256"] != expected_sha:
        raise VerifyError(
            "BUILD_FACT_MISMATCH",
            "current file differs from build-stage receipt",
            {"label": label, "expected": {"bytes": expected_bytes, "sha256": expected_sha}, "actual": actual},
        )
    return actual


def resolve_external_fact(row: Mapping[str, Any]) -> Tuple[Path, Dict[str, Any]]:
    raw = row.get("path")
    if not isinstance(raw, str) or not Path(raw).is_absolute():
        raise VerifyError("EXTERNAL_REFERENCE_PATH_FAIL", "external reference fact requires an absolute path", {"path": raw})
    path = Path(raw).resolve()
    if not path.is_file() or is_under(path, ATTEMPTS_ROOT):
        raise VerifyError("EXTERNAL_REFERENCE_SCOPE_FAIL", "external reference is missing or points into attempts", {"path": norm(path)})
    if not is_under(path, RUN_ROOT):
        raise VerifyError("EXTERNAL_REFERENCE_OUTSIDE_V5", "external reference must remain inside the V5 run root", {"path": norm(path)})
    return path, check_expected_fact(path, row, "allowed_external_reference")


def resolve_component_entry(
    attempt_root: Path,
    row: Mapping[str, Any],
    artifact_paths: Set[Path],
    external_paths: Set[Path],
) -> Dict[str, Any]:
    if "relative_path" in row:
        path = resolve_relative_artifact(attempt_root, row["relative_path"])
    elif isinstance(row.get("path"), str) and Path(str(row["path"])).is_absolute():
        path = Path(str(row["path"])).resolve()
    else:
        raise VerifyError("EXPECTED_COMPONENT_PATH_FAIL", "expected component needs relative_path or absolute path", {"row": dict(row)})
    if path not in artifact_paths and path not in external_paths:
        raise VerifyError("EXPECTED_COMPONENT_NOT_AUTHORIZED", "expected component is not an artifact or allowed external reference", {"path": norm(path)})
    transform = row.get("transform16")
    if not isinstance(transform, list) or len(transform) != 16 or not all(isinstance(item, (int, float)) and math.isfinite(float(item)) for item in transform):
        raise VerifyError("EXPECTED_TRANSFORM_SHAPE_FAIL", "expected transform must contain 16 finite numbers", {"path": norm(path)})
    return {
        "path": path,
        "transform16": [float(item) for item in transform],
        "fixed": row.get("fixed"),
        "suppression": row.get("suppression"),
        "name2": row.get("name2"),
    }


def validate_build_receipt(attempt_root: Path, receipt_path: Path) -> Dict[str, Any]:
    payload = load_json(receipt_path)
    if payload.get("schema") != EXPECTED_BUILD_SCHEMA or payload.get("verdict") != EXPECTED_BUILD_VERDICT:
        raise VerifyError(
            "BUILD_RECEIPT_GATE_FAIL",
            "build receipt schema/verdict does not authorize fresh verification",
            {"schema": payload.get("schema"), "verdict": payload.get("verdict")},
        )
    if Path(str(payload.get("attempt_root", ""))).resolve() != attempt_root.resolve():
        raise VerifyError("BUILD_RECEIPT_ATTEMPT_FAIL", "build receipt binds a different attempt root", {"receipt_value": payload.get("attempt_root"), "actual": norm(attempt_root)})

    session = payload.get("session")
    if not isinstance(session, dict):
        raise VerifyError("BUILD_SESSION_MISSING", "build receipt lacks session object")
    build_pid = int(session.get("pid", -1))
    build_start = float(session.get("process_create_time", -1.0))
    if build_pid <= 0 or build_start <= 0.0 or not str(session.get("revision", "")).startswith(EXPECTED_SW_REVISION_PREFIX):
        raise VerifyError("BUILD_SESSION_IDENTITY_FAIL", "build PID/start-time/revision is incomplete", {"session": session})

    artifact_rows = payload.get("artifacts")
    if not isinstance(artifact_rows, list):
        raise VerifyError("BUILD_ARTIFACT_LIST_MISSING", "build receipt lacks artifacts list")
    artifacts: Dict[Path, Dict[str, Any]] = {}
    counts = {"SLDPRT": 0, "SLDASM": 0}
    for index, row in enumerate(artifact_rows):
        if not isinstance(row, dict):
            raise VerifyError("BUILD_ARTIFACT_ROW_FAIL", "artifact row must be an object", {"index": index})
        path = resolve_relative_artifact(attempt_root, row.get("relative_path"))
        if path in artifacts:
            raise VerifyError("BUILD_ARTIFACT_DUPLICATE", "artifact path appears more than once", {"path": norm(path)})
        suffix = path.suffix.upper().lstrip(".")
        if suffix not in counts or str(row.get("document_type", "")).upper() != suffix:
            raise VerifyError("BUILD_ARTIFACT_TYPE_FAIL", "artifact document_type/suffix mismatch", {"path": norm(path), "document_type": row.get("document_type")})
        counts[suffix] += 1
        artifacts[path] = {"row": row, "fact": check_expected_fact(path, row, f"artifact[{index}]"), "document_type": suffix, "role": row.get("role")}
    if counts != EXPECTED_ARTIFACT_COUNTS:
        raise VerifyError("BUILD_ARTIFACT_COUNT_FAIL", "R2 artifact count differs from 34 SLDPRT + 2 SLDASM", {"expected": EXPECTED_ARTIFACT_COUNTS, "actual": counts})

    external: Dict[Path, Dict[str, Any]] = {}
    external_rows = payload.get("allowed_external_references")
    if not isinstance(external_rows, list) or len(external_rows) < 4:
        raise VerifyError("EXTERNAL_REFERENCE_LIST_FAIL", "build receipt must bind at least the four root clevis/pin inputs")
    for row in external_rows:
        if not isinstance(row, dict):
            raise VerifyError("EXTERNAL_REFERENCE_ROW_FAIL", "external reference row must be an object")
        path, fact = resolve_external_fact(row)
        if path in external:
            raise VerifyError("EXTERNAL_REFERENCE_DUPLICATE", "external reference path is duplicated", {"path": norm(path)})
        external[path] = fact

    assemblies_payload = payload.get("assemblies")
    if not isinstance(assemblies_payload, dict) or set(assemblies_payload) != {"L", "R"}:
        raise VerifyError("BUILD_ASSEMBLY_CONTRACT_FAIL", "build receipt assemblies must contain exactly L and R")
    assemblies: Dict[str, Dict[str, Any]] = {}
    for side in ("L", "R"):
        side_row = assemblies_payload[side]
        if not isinstance(side_row, dict):
            raise VerifyError("BUILD_SIDE_ROW_FAIL", "side assembly contract must be an object", {"side": side})
        assembly_path = resolve_relative_artifact(attempt_root, side_row.get("relative_path"))
        if assembly_path not in artifacts or artifacts[assembly_path]["document_type"] != "SLDASM":
            raise VerifyError("BUILD_SIDE_ASSEMBLY_PATH_FAIL", "side contract does not identify one staged SLDASM", {"side": side, "path": norm(assembly_path)})
        states = side_row.get("states")
        if not isinstance(states, dict) or set(states) != set(EXPECTED_CONFIGS):
            raise VerifyError("BUILD_STATE_SET_FAIL", "side state contract must contain exactly seven configurations", {"side": side, "actual": sorted(states) if isinstance(states, dict) else None})
        normalized_states: Dict[str, Dict[str, Any]] = {}
        common_component_paths: Optional[Set[Path]] = None
        for state in EXPECTED_CONFIGS:
            state_row = states[state]
            if not isinstance(state_row, dict):
                raise VerifyError("BUILD_STATE_ROW_FAIL", "state contract row must be an object", {"side": side, "state": state})
            angles = state_row.get("angles_deg")
            expected_angles = STATE_ANGLES[state][side]
            if not isinstance(angles, list) or tuple(float(item) for item in angles) != expected_angles:
                raise VerifyError("BUILD_STATE_ANGLES_FAIL", "state logical angles differ from frozen table", {"side": side, "state": state, "expected": expected_angles, "actual": angles})
            component_rows = state_row.get("components")
            if not isinstance(component_rows, list):
                raise VerifyError("BUILD_STATE_COMPONENTS_FAIL", "state contract lacks component transform rows", {"side": side, "state": state})
            normalized_components = [resolve_component_entry(attempt_root, row, set(artifacts), set(external)) for row in component_rows if isinstance(row, dict)]
            if len(normalized_components) != len(component_rows):
                raise VerifyError("BUILD_STATE_COMPONENT_ROW_TYPE_FAIL", "all state components must be objects", {"side": side, "state": state})
            paths = {row["path"] for row in normalized_components}
            if len(paths) != len(normalized_components) or len(paths) < 19:
                raise VerifyError("BUILD_STATE_COMPONENT_CARDINALITY_FAIL", "state component paths must be unique and include the complete side assembly", {"side": side, "state": state, "count": len(paths)})
            if common_component_paths is None:
                common_component_paths = paths
            elif paths != common_component_paths:
                raise VerifyError("BUILD_STATE_COMPONENT_SET_DRIFT", "physical component path set differs across configurations", {"side": side, "state": state})
            normalized_states[state] = {"angles_deg": list(expected_angles), "components": normalized_components}
        mate_count = int(side_row.get("expected_mate_count", -1))
        if mate_count < 20:
            raise VerifyError("BUILD_MATE_COUNT_CONTRACT_FAIL", "expected mate count is below the 3R minimum", {"side": side, "expected_mate_count": mate_count})
        assemblies[side] = {"path": assembly_path, "states": normalized_states, "expected_mate_count": mate_count}

    protected: Dict[Path, Dict[str, Any]] = {}
    builder_row = payload.get("builder")
    protected_rows = payload.get("protected_inputs")
    if not isinstance(builder_row, dict) or not isinstance(protected_rows, list) or not protected_rows:
        raise VerifyError("BUILD_PROTECTED_INPUTS_FAIL", "build receipt must bind builder and protected_inputs")
    for label, row in [("builder", builder_row), *[(f"protected_input[{index}]", item) for index, item in enumerate(protected_rows)]]:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str) or not Path(str(row["path"])).is_absolute():
            raise VerifyError("BUILD_PROTECTED_FACT_PATH_FAIL", "protected fact requires an absolute path", {"label": label, "row": row})
        path = Path(str(row["path"])).resolve()
        if not path.is_file():
            raise VerifyError("BUILD_PROTECTED_FACT_MISSING", "protected fact file is absent", {"label": label, "path": norm(path)})
        protected[path] = check_expected_fact(path, row, label)

    return {
        "payload": payload,
        "receipt": file_fact(receipt_path),
        "session": session,
        "artifacts": artifacts,
        "external": external,
        "assemblies": assemblies,
        "protected": protected,
        "counts": counts,
    }


def snapshot(contract: Mapping[str, Any], receipt_path: Path) -> Dict[str, Dict[str, Any]]:
    paths = set(contract["artifacts"]) | set(contract["external"]) | set(contract["protected"]) | {receipt_path.resolve()}
    return {norm(path): file_fact(path) for path in sorted(paths, key=norm)}


def terminal_evidence(attempt_root: Path) -> List[str]:
    evidence_dir = attempt_root / "evidence"
    rows: List[Path] = []
    pass_path = attempt_root / PASS_RELATIVE
    if pass_path.exists():
        rows.append(pass_path)
    if evidence_dir.is_dir():
        rows.extend(evidence_dir.glob(FAIL_GLOB))
    return [norm(path) for path in sorted(set(rows), key=norm)]


def transaction_static_audit(attempt_root: Path, receipt_path: Path) -> Dict[str, Any]:
    contract = validate_build_receipt(attempt_root, receipt_path)
    terminal = terminal_evidence(attempt_root)
    return {
        "attempt_root": norm(attempt_root),
        "build_receipt": contract["receipt"],
        "artifact_counts": contract["counts"],
        "side_assemblies": {side: norm(row["path"]) for side, row in contract["assemblies"].items()},
        "protected_file_count": len(contract["protected"]),
        "allowed_external_reference_count": len(contract["external"]),
        "existing_terminal_evidence": terminal,
        "execution_authorized": not terminal,
        "solidworks_touched": False,
        "verdict": "V5_SOLAR_R2_FRESH_VERIFY_TRANSACTION_READY" if not terminal else "V5_SOLAR_R2_FRESH_VERIFY_TRANSACTION_HOLD",
    }


def attach_fresh_session(expected_pid: int, build_session: Mapping[str, Any]) -> Tuple[Any, Any, Any, Dict[str, Any]]:
    import psutil
    import pythoncom
    import win32com.client
    from win32com.client import gencache

    pythoncom.CoInitialize()
    types = gencache.GetModuleForTypelib(*SW_TLB)
    raw = win32com.client.GetActiveObject(SW_PROG_ID)
    sw = wrap(raw, "ISldWorks", types, pythoncom)
    actual_pid = int(value(sw, "GetProcessID"))
    revision = str(value(sw, "RevisionNumber"))
    document_count = int(value(sw, "GetDocumentCount"))
    if actual_pid != int(expected_pid):
        raise VerifyError("FRESH_SESSION_PID_FAIL", "active SOLIDWORKS PID differs from explicit expected PID", {"expected": expected_pid, "actual": actual_pid})
    if not revision.startswith(EXPECTED_SW_REVISION_PREFIX):
        raise VerifyError("FRESH_SESSION_REVISION_FAIL", "SOLIDWORKS must be 2024 SP5", {"revision": revision})
    if document_count != 0 or value(sw, "ActiveDoc") is not None:
        raise VerifyError("FRESH_SESSION_NOT_EMPTY", "fresh verifier requires zero open documents", {"document_count": document_count})

    process = psutil.Process(actual_pid)
    executable = Path(process.exe()).resolve()
    create_time = float(process.create_time())
    if os.path.normcase(str(executable)) != os.path.normcase(str(SOLIDWORKS_EXE.resolve())):
        raise VerifyError("FRESH_SESSION_EXECUTABLE_FAIL", "active process is not the pinned SOLIDWORKS executable", {"expected": norm(SOLIDWORKS_EXE), "actual": norm(executable)})

    build_pid = int(build_session["pid"])
    build_create_time = float(build_session["process_create_time"])
    if actual_pid == build_pid or create_time <= build_create_time:
        raise VerifyError(
            "FRESH_PROCESS_IDENTITY_FAIL",
            "verification process is not newer and distinct from the build process",
            {"build_pid": build_pid, "build_create_time": build_create_time, "verify_pid": actual_pid, "verify_create_time": create_time},
        )
    try:
        old = psutil.Process(build_pid)
        if abs(float(old.create_time()) - build_create_time) < 0.001:
            raise VerifyError("BUILD_PROCESS_STILL_ALIVE", "the exact build SOLIDWORKS process is still alive", {"build_pid": build_pid, "build_create_time": build_create_time})
    except psutil.NoSuchProcess:
        pass

    return sw, types, pythoncom, {
        "attach_only": True,
        "pid": actual_pid,
        "process_create_time": create_time,
        "revision": revision,
        "executable": norm(executable),
        "document_count_before": document_count,
        "active_doc_is_null_before": True,
        "different_pid_from_build": actual_pid != build_pid,
        "newer_process_than_build": create_time > build_create_time,
    }


def unpack_open(result: Any, path: Path) -> Tuple[Any, int, int]:
    if not isinstance(result, tuple) or len(result) < 3:
        raise VerifyError("READ_ONLY_OPEN_RETURN_FAIL", "typed OpenDoc6 did not return model/errors/warnings", {"path": norm(path), "returned": repr(result)})
    raw, outs = unpack(result)
    return raw, int(outs[0]), int(outs[1])


def open_read_only(sw: Any, path: Path, document_type: int, types: Any, pythoncom: Any) -> Tuple[Any, Dict[str, Any]]:
    raw, errors, warnings = unpack_open(
        sw.OpenDoc6(str(path), document_type, SW_OPEN_SILENT | SW_OPEN_READ_ONLY, "", 0, 0),
        path,
    )
    if raw is None or errors != 0 or warnings != 0:
        raise VerifyError("READ_ONLY_OPEN_FAIL", "native document did not open cleanly read-only", {"path": norm(path), "errors": errors, "warnings": warnings})
    model = wrap(raw, "IModelDoc2", types, pythoncom)
    if not bool(value(model, "IsOpenedReadOnly")):
        raise VerifyError("READ_ONLY_MODE_FAIL", "SOLIDWORKS reports document writable", {"path": norm(path)})
    if Path(str(value(model, "GetPathName"))).resolve() != path.resolve():
        raise VerifyError("OPEN_PATH_READBACK_FAIL", "opened path differs from expected artifact", {"expected": norm(path), "actual": str(value(model, "GetPathName"))})
    if int(value(model, "GetType")) != document_type:
        raise VerifyError("OPEN_DOCUMENT_TYPE_FAIL", "opened document type differs", {"path": norm(path), "expected": document_type, "actual": int(value(model, "GetType"))})
    return model, {"errors": errors, "warnings": warnings, "read_only": True, "path": norm(path)}


def transform_array(component: Any) -> List[float]:
    transform = value(component, "Transform2")
    if transform is None:
        raise VerifyError("COMPONENT_TRANSFORM_NULL", "component has no Transform2", {"name2": str(value(component, "Name2"))})
    data = [float(item) for item in as_list(value(transform, "ArrayData"))]
    if len(data) != 16 or not all(math.isfinite(item) for item in data):
        raise VerifyError("COMPONENT_TRANSFORM_SHAPE_FAIL", "component transform is not 16 finite numbers", {"name2": str(value(component, "Name2")), "transform": data})
    return data


def transform_error(actual: Sequence[float], expected: Sequence[float]) -> Dict[str, float]:
    translation_mm = math.sqrt(sum((float(actual[index]) - float(expected[index])) ** 2 for index in (9, 10, 11))) * 1000.0
    actual_rotation = [[float(actual[column * 3 + row]) for column in range(3)] for row in range(3)]
    expected_rotation = [[float(expected[column * 3 + row]) for column in range(3)] for row in range(3)]
    trace = sum(sum(expected_rotation[k][row] * actual_rotation[k][row] for k in range(3)) for row in range(3))
    cosine = max(-1.0, min(1.0, (trace - 1.0) / 2.0))
    return {"translation_mm": translation_mm, "rotation_deg": math.degrees(math.acos(cosine))}


def get_components(model: Any, types: Any, pythoncom: Any) -> List[Any]:
    assembly = wrap(model, "IAssemblyDoc", types, pythoncom)
    return [wrap(raw, "IComponent2", types, pythoncom) for raw in as_list(assembly.GetComponents(False))]


def component_ledger(model: Any, types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    rows = []
    for component in get_components(model, types, pythoncom):
        raw_path = str(value(component, "GetPathName"))
        if not raw_path:
            raise VerifyError("VIRTUAL_COMPONENT_PROHIBITED", "solar R2 side assembly contains a virtual/unsaved component", {"name2": str(value(component, "Name2"))})
        path = Path(raw_path).resolve()
        if not path.is_file():
            raise VerifyError("COMPONENT_REFERENCE_MISSING", "component reference path is absent", {"name2": str(value(component, "Name2")), "path": norm(path)})
        rows.append({
            "name2": str(value(component, "Name2")),
            "path": path,
            "path_text": norm(path),
            "fixed": bool(value(component, "IsFixed")),
            "suppression": int(value(component, "GetSuppression")),
            "transform16": transform_array(component),
            "file": file_fact(path),
        })
    paths = [row["path"] for row in rows]
    if len(paths) != len(set(paths)):
        raise VerifyError("COMPONENT_PATH_DUPLICATE", "side assembly contains duplicate physical component paths", {"paths": [norm(path) for path in paths]})
    return sorted(rows, key=lambda row: row["path_text"])


def feature_error_state(feature: Any) -> Dict[str, Any]:
    legacy = int(value(feature, "GetErrorCode"))
    returned = value(feature, "GetErrorCode2", False)
    code2, outs = unpack(returned)
    if len(outs) != 1 or int(code2) != legacy:
        raise VerifyError("MATE_ERROR_READBACK_SHAPE_FAIL", "mate feature error APIs disagree", {"legacy": legacy, "returned": repr(returned)})
    return {"feature_error_code": legacy, "feature_error_code2": int(code2), "feature_is_warning": bool(outs[0]), "suppressed": bool(value(feature, "IsSuppressed"))}


def mate_object_fact(mate: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    count = int(value(mate, "GetMateEntityCount"))
    paths: List[str] = []
    reference_types: List[int] = []
    for index in range(count):
        raw_entity = mate.MateEntity(index)
        if raw_entity is None:
            raise VerifyError("MATE_ENTITY_NULL", "mate endpoint is null", {"index": index, "count": count})
        entity = wrap(raw_entity, "IMateEntity2", types, pythoncom)
        raw_component = value(entity, "ReferenceComponent")
        if raw_component is None:
            raise VerifyError("MATE_COMPONENT_NULL", "mate endpoint lacks a component", {"index": index})
        component = wrap(raw_component, "IComponent2", types, pythoncom)
        path = Path(str(value(component, "GetPathName"))).resolve()
        if not path.is_file():
            raise VerifyError("MATE_COMPONENT_PATH_FAIL", "mate endpoint path is missing", {"path": norm(path)})
        paths.append(norm(path))
        reference_types.append(int(value(entity, "ReferenceType2")))
    return {
        "mate_type": int(value(mate, "Type")),
        "alignment": int(value(mate, "Alignment")),
        "entity_count": count,
        "component_paths": sorted(paths),
        "reference_types": sorted(reference_types),
    }


def mate_ledger(model: Any, types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    feature = value(model, "FirstFeature")
    for _ in range(10000):
        if feature is None:
            names = [row["feature_name"] for row in rows]
            if len(names) != len(set(names)):
                raise VerifyError("MATE_NAME_DUPLICATE", "mate feature names are not unique", {"names": names})
            return rows
        typed = wrap(feature, "IFeature", types, pythoncom)
        if str(value(typed, "GetTypeName2")) == "MateGroup":
            sub = value(typed, "GetFirstSubFeature")
            for _sub in range(10000):
                if sub is None:
                    break
                sub_feature = wrap(sub, "IFeature", types, pythoncom)
                raw_mate = value(sub_feature, "GetSpecificFeature2")
                if raw_mate is None:
                    raise VerifyError("MATE_SPECIFIC_FEATURE_NULL", "mate subfeature has no IMate2", {"feature": str(value(sub_feature, "Name"))})
                mate = wrap(raw_mate, "IMate2", types, pythoncom)
                row = {"feature_name": str(value(sub_feature, "Name")), **feature_error_state(sub_feature), **mate_object_fact(mate, types, pythoncom)}
                if row["feature_error_code"] != 0 or row["feature_error_code2"] != 0 or row["feature_is_warning"] or row["suppressed"] or row["entity_count"] != 2:
                    raise VerifyError("MATE_HEALTH_FAIL", "mate is errored, warned, suppressed, or not two-ended", row)
                rows.append(row)
                sub = value(sub_feature, "GetNextSubFeature")
            else:
                raise VerifyError("MATE_SUBFEATURE_LIMIT", "mate subfeature traversal exceeded guard")
        feature = value(typed, "GetNextFeature")
    raise VerifyError("MATE_FEATURE_LIMIT", "feature traversal exceeded guard")


def compare_components(actual: Sequence[Mapping[str, Any]], expected: Sequence[Mapping[str, Any]], side: str, state: str) -> List[Dict[str, Any]]:
    actual_map = {Path(row["path"]).resolve(): row for row in actual}
    expected_map = {Path(row["path"]).resolve(): row for row in expected}
    if set(actual_map) != set(expected_map):
        raise VerifyError(
            "CONFIG_COMPONENT_SET_FAIL",
            "read-only configuration component set differs from build hand-off",
            {"side": side, "state": state, "expected": sorted(norm(path) for path in expected_map), "actual": sorted(norm(path) for path in actual_map)},
        )
    rows = []
    for path in sorted(expected_map, key=norm):
        observed = actual_map[path]
        wanted = expected_map[path]
        error = transform_error(observed["transform16"], wanted["transform16"])
        if error["translation_mm"] > TRANS_TOL_MM or error["rotation_deg"] > ROT_TOL_DEG:
            raise VerifyError("CONFIG_TRANSFORM_FAIL", "read-only component transform differs from saved build contract", {"side": side, "state": state, "path": norm(path), "error": error})
        if wanted.get("fixed") is not None and bool(observed["fixed"]) != bool(wanted["fixed"]):
            raise VerifyError("CONFIG_FIXED_STATE_FAIL", "component fixed state differs", {"side": side, "state": state, "path": norm(path), "expected": wanted["fixed"], "actual": observed["fixed"]})
        if wanted.get("suppression") is not None and int(observed["suppression"]) != int(wanted["suppression"]):
            raise VerifyError("CONFIG_SUPPRESSION_FAIL", "component suppression state differs", {"side": side, "state": state, "path": norm(path), "expected": wanted["suppression"], "actual": observed["suppression"]})
        rows.append({"path": norm(path), "name2": observed["name2"], "fixed": observed["fixed"], "suppression": observed["suppression"], "transform16": observed["transform16"], "error": error})
    return rows


def verify_assembly(
    sw: Any,
    types: Any,
    pythoncom: Any,
    side: str,
    contract: Mapping[str, Any],
    authorized_paths: Set[Path],
) -> Dict[str, Any]:
    path = Path(contract["path"])
    model, opened = open_read_only(sw, path, SW_DOC_ASSEMBLY, types, pythoncom)
    title = str(value(model, "GetTitle"))
    try:
        names = [str(name) for name in as_list(value(model, "GetConfigurationNames"))]
        if set(names) != set(EXPECTED_CONFIGS) or len(names) != len(EXPECTED_CONFIGS):
            raise VerifyError("FRESH_CONFIG_SET_FAIL", "native side assembly configuration set is not exactly seven", {"side": side, "actual": names})
        state_rows = []
        for state in EXPECTED_CONFIGS:
            if not bool(model.ShowConfiguration2(state)):
                raise VerifyError("FRESH_CONFIG_ACTIVATE_FAIL", "read-only configuration activation failed", {"side": side, "state": state})
            if not bool(model.ForceRebuild3(True)):
                raise VerifyError("FRESH_CONFIG_REBUILD_FAIL", "read-only configuration rebuild failed", {"side": side, "state": state})
            components = component_ledger(model, types, pythoncom)
            if any(Path(row["path"]).resolve() not in authorized_paths for row in components):
                raise VerifyError("FRESH_REFERENCE_NOT_AUTHORIZED", "assembly resolved a component outside the attempt/external allowlist", {"side": side, "state": state, "paths": [row["path_text"] for row in components]})
            compared = compare_components(components, contract["states"][state]["components"], side, state)
            mates = mate_ledger(model, types, pythoncom)
            if len(mates) != int(contract["expected_mate_count"]):
                raise VerifyError("FRESH_MATE_COUNT_FAIL", "mate ledger count differs from build contract", {"side": side, "state": state, "expected": contract["expected_mate_count"], "actual": len(mates)})
            for mate in mates:
                if any(Path(path_text).resolve() not in authorized_paths for path_text in mate["component_paths"]):
                    raise VerifyError("FRESH_MATE_REFERENCE_FAIL", "mate endpoint escapes authorized reference set", {"side": side, "state": state, "mate": mate})
            state_rows.append({
                "state": state,
                "angles_deg": list(STATE_ANGLES[state][side]),
                "components": compared,
                "mate_ledger": mates,
                "reference_count": len(components),
                "verdict": "V5_SOLAR_R2_FRESH_CONFIG_READ_ONLY_PASS",
            })
        return {"side": side, "target": file_fact(path), "open": opened, "configuration_names": names, "states": state_rows, "verdict": "V5_SOLAR_R2_FRESH_SIDE_READ_ONLY_PASS"}
    finally:
        sw.CloseDoc(title)


def verify_part(sw: Any, types: Any, pythoncom: Any, path: Path) -> Dict[str, Any]:
    model, opened = open_read_only(sw, path, SW_DOC_PART, types, pythoncom)
    title = str(value(model, "GetTitle"))
    try:
        if not bool(model.ForceRebuild3(True)):
            raise VerifyError("FRESH_PART_REBUILD_FAIL", "read-only part rebuild failed", {"path": norm(path)})
        part = wrap(model, "IPartDoc", types, pythoncom)
        bodies = as_list(part.GetBodies2(0, False))
        if not bodies:
            raise VerifyError("FRESH_PART_BODY_FAIL", "read-only native part contains no solid body", {"path": norm(path)})
        return {"target": file_fact(path), "open": opened, "solid_body_count": len(bodies), "verdict": "V5_SOLAR_R2_FRESH_PART_READ_ONLY_PASS"}
    finally:
        sw.CloseDoc(title)


def close_only_authorized_documents(sw: Any, authorized_paths: Set[Path]) -> Dict[str, Any]:
    closed: List[str] = []
    unknown: List[Dict[str, str]] = []
    for _ in range(100):
        documents = as_list(value(sw, "GetDocuments"))
        if not documents:
            break
        progress = False
        unknown = []
        for raw in documents:
            title = str(value(raw, "GetTitle"))
            raw_path = str(value(raw, "GetPathName"))
            path = Path(raw_path).resolve() if raw_path else None
            if path is not None and path in authorized_paths:
                sw.CloseDoc(title)
                closed.append(norm(path))
                progress = True
            else:
                unknown.append({"title": title, "path": norm(path) if path is not None else ""})
        if unknown or not progress:
            break
    remaining = int(value(sw, "GetDocumentCount"))
    if unknown or remaining != 0 or value(sw, "ActiveDoc") is not None:
        raise VerifyError("FRESH_CLEANUP_FAIL", "verifier did not close to an empty session without touching unknown documents", {"remaining": remaining, "unknown": unknown, "closed": closed})
    return {"closed_authorized_documents": sorted(set(closed)), "document_count_after": remaining, "active_doc_is_null_after": True}


def verify_attempt(attempt_root: Path, receipt_path: Path, expected_pid: int) -> Dict[str, Any]:
    source_audit = source_policy_audit()
    if not source_audit["verdict"].endswith("_PASS"):
        raise VerifyError("SOURCE_POLICY_HOLD", "verifier source policy audit failed", source_audit)
    transaction_audit = transaction_static_audit(attempt_root, receipt_path)
    if not transaction_audit["execution_authorized"]:
        raise VerifyError("TRANSACTION_TERMINAL_HOLD", "attempt already contains terminal fresh-verification evidence", transaction_audit)
    contract = validate_build_receipt(attempt_root, receipt_path)
    before = snapshot(contract, receipt_path)
    authorized_paths = set(contract["artifacts"]) | set(contract["external"])
    result: Dict[str, Any] = {
        "schema": "F3R2_V5_SOLAR_R2_FRESH_VERIFY_RECEIPT_V1",
        "timestamp_start_utc": utc_now(),
        "attempt_root": norm(attempt_root),
        "verifier": file_fact(Path(__file__)),
        "source_policy_audit": source_audit,
        "transaction_static_audit": transaction_audit,
        "build_receipt": file_fact(receipt_path),
        "protected_pre": before,
        "parts": [],
        "assemblies": [],
        "cad_write_calls": 0,
        "read_only": True,
    }
    sw = types = pythoncom = None
    cleanup: Optional[Dict[str, Any]] = None
    try:
        sw, types, pythoncom, session = attach_fresh_session(expected_pid, contract["session"])
        result["solidworks"] = session
        for path, row in sorted(contract["artifacts"].items(), key=lambda item: norm(item[0])):
            if row["document_type"] == "SLDPRT":
                result["parts"].append(verify_part(sw, types, pythoncom, path))
                cleanup = close_only_authorized_documents(sw, authorized_paths)
        for side in ("L", "R"):
            result["assemblies"].append(verify_assembly(sw, types, pythoncom, side, contract["assemblies"][side], authorized_paths))
            cleanup = close_only_authorized_documents(sw, authorized_paths)
        cleanup = close_only_authorized_documents(sw, authorized_paths)
        after = snapshot(contract, receipt_path)
        if before != after:
            raise VerifyError("PROTECTED_HASH_POST_FAIL", "CAD, build receipt, or protected input bytes changed during read-only verification", {"pre": before, "post": after})
        result.update({
            "timestamp_end_utc": utc_now(),
            "cleanup": cleanup,
            "protected_post": after,
            "hash_pre_equals_post": True,
            "fresh_process": True,
            "build_pid_differs_from_verify_pid": True,
            "configuration_transform_readback_mode": "READ_ONLY_NO_DRIVER_CALLS",
            "mate_reference_readback_mode": "READ_ONLY_NATIVE_BREP",
            "verdict": "V5_SOLAR_R2_NEW_PID_READ_ONLY_COLD_VERIFY_PASS",
        })
        pass_path = attempt_root / PASS_RELATIVE
        write_json_once(pass_path, result, attempt_root)
        return {"receipt": file_fact(pass_path), "payload": result}
    finally:
        if sw is not None:
            try:
                close_only_authorized_documents(sw, authorized_paths)
            except Exception:
                pass
        if pythoncom is not None:
            pythoncom.CoUninitialize()


def failure_path(attempt_root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    return attempt_root / "evidence" / f"F3R2_V5_SOLAR_R2_FRESH_VERIFY_FAIL_{stamp}.json"


def run_verify(args: argparse.Namespace) -> int:
    attempt_root: Optional[Path] = None
    receipt_path: Optional[Path] = None
    try:
        attempt_root = assert_attempt_root(Path(args.attempt_root))
        receipt_path = assert_build_receipt(attempt_root, Path(args.build_receipt))
        result = verify_attempt(attempt_root, receipt_path, int(args.expected_pid))
        print(json.dumps({"verdict": result["payload"]["verdict"], "receipt": result["receipt"]}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        failure = {
            "schema": "F3R2_V5_SOLAR_R2_FRESH_VERIFY_FAILURE_V1",
            "timestamp_utc": utc_now(),
            "attempt_root": norm(attempt_root) if attempt_root is not None else str(args.attempt_root),
            "build_receipt": file_fact(receipt_path) if receipt_path is not None and receipt_path.is_file() else str(args.build_receipt),
            "expected_pid": int(args.expected_pid),
            "verifier": file_fact(Path(__file__)),
            "error_code": getattr(exc, "code", "FRESH_VERIFY_UNEXPECTED_FAIL"),
            "error": str(exc),
            "detail": getattr(exc, "detail", {}),
            "traceback": traceback.format_exc(),
            "cad_write_calls": 0,
            "verdict": "V5_SOLAR_R2_NEW_PID_READ_ONLY_COLD_VERIFY_FAIL",
        }
        if attempt_root is not None:
            try:
                target = failure_path(attempt_root)
                write_json_once(target, failure, attempt_root)
                failure["failure_receipt"] = file_fact(target)
            except Exception as write_exc:
                failure["failure_receipt_write_error"] = repr(write_exc)
        print(json.dumps(failure, ensure_ascii=False, indent=2), file=sys.stderr)
        return 3


def run_audit(args: argparse.Namespace) -> int:
    result: Dict[str, Any] = {
        "schema": "F3R2_V5_SOLAR_R2_FRESH_VERIFY_STATIC_AUDIT_V1",
        "timestamp_utc": utc_now(),
        "source_policy": source_policy_audit(),
        "attempts_root": norm(ATTEMPTS_ROOT),
        "solidworks_touched": False,
    }
    ok = result["source_policy"]["verdict"].endswith("_PASS")
    if bool(args.attempt_root) != bool(args.build_receipt):
        result["transaction_error"] = "--attempt-root and --build-receipt must be supplied together"
        ok = False
    elif args.attempt_root and args.build_receipt:
        try:
            attempt_root = assert_attempt_root(Path(args.attempt_root))
            receipt_path = assert_build_receipt(attempt_root, Path(args.build_receipt))
            result["transaction"] = transaction_static_audit(attempt_root, receipt_path)
            ok = ok and bool(result["transaction"]["execution_authorized"])
        except Exception as exc:
            result["transaction_error"] = {"code": getattr(exc, "code", "STATIC_AUDIT_FAIL"), "error": str(exc), "detail": getattr(exc, "detail", {})}
            ok = False
    result["execution_authorized"] = ok
    result["verdict"] = "V5_SOLAR_R2_FRESH_VERIFY_STATIC_AUDIT_PASS" if ok else "V5_SOLAR_R2_FRESH_VERIFY_STATIC_AUDIT_HOLD"
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if ok else 2


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    audit = commands.add_parser("audit", help="source/filesystem-only audit; never touches SOLIDWORKS")
    audit.add_argument("--attempt-root")
    audit.add_argument("--build-receipt")
    verify = commands.add_parser("verify", help="attach to an explicit fresh PID and verify read-only")
    verify.add_argument("--attempt-root", required=True)
    verify.add_argument("--build-receipt", required=True)
    verify.add_argument("--expected-pid", required=True, type=int)
    return root


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "audit":
        return run_audit(args)
    return run_verify(args)


if __name__ == "__main__":
    raise SystemExit(main())
