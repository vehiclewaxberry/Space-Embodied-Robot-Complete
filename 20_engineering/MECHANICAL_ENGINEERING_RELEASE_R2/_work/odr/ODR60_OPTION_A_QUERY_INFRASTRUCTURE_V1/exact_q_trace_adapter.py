"""Read-only adapter for the frozen Route-C V9F main-local harness kernel.

The accepted evaluator intentionally remains byte-unchanged.  This adapter
loads that exact source, stops immediately before its mission sweep, calls the
main-local ``eval_clearance`` closure once, and aborts before the evaluator's
three declared output writes.  This is a legacy pointwise harness-clearance
query, not a 150-object system-collision query and not a continuous-q proof.
Actual V9F execution remains separately authority- and memory-gated; static
audit and synthetic tests do not execute current geometry.
"""

from __future__ import annotations

import ast
from contextlib import redirect_stderr, redirect_stdout
import copy
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import re
import sys
import uuid
from typing import Any, Callable, Mapping, Sequence


V9F_SOURCE_REL = Path(
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/"
    "ROUTE_C_EXACT_SWEEP_V9F.py"
)
V9F_SOURCE_SHA256 = (
    "9F26AC9A8DE5E2EEB57103F07B769EB43AC30A8FBAFD90FE8DF5D501FA8C8A7F"
)
V9F_MESH_MANIFEST_SHA256 = (
    "A90123580F73A7FF2DCE3F7A5BDB31DC31A1741D69A3CBFE837CB4DB53A00F25"
)
V9F_LEGACY_RAW_BASE_LINK_SOURCE_SHA256 = (
    "22641C079014FE968702393F61E7F7F1A8F80C6C1DF45A61E31545F6EAFF3B65"
)
CAPTURE_MARKER = "m_nom = run_mission(MAX_DQ_STEP)"
NOMINAL_AVAILABLE_PHYSICAL_MEMORY_MIN_GIB = 6.0
OWNER_AUTHORITY_SCHEMA = "ODR60_OPTION_A_SINGLE_RUN_AUTHORITY_V1"
LOW_MEMORY_OVERRIDE_SCHEMA = "ODR60_OPTION_A_LOW_MEMORY_OVERRIDE_V1"
OWNER_OPTION_A_DECISION_TOKEN = "AUTHORIZE_OPTION_A_FIXED_ENDPOINT_M01_TRAJECTORY_SEARCH"
LOW_MEMORY_OVERRIDE_TOKEN = "ACCEPT_SINGLE_RUN_LOW_MEMORY_RISK"

# Fail-closed trust anchors.  They intentionally remain absent until an Owner
# selection is recorded as a project artifact and this package is rebuilt.
ACCEPTED_OWNER_AUTHORITY_RECEIPT_REL: Path | None = None
ACCEPTED_OWNER_AUTHORITY_RECEIPT_SHA256: str | None = None
ACCEPTED_LOW_MEMORY_OVERRIDE_RECEIPT_REL: Path | None = None
ACCEPTED_LOW_MEMORY_OVERRIDE_RECEIPT_SHA256: str | None = None


class ExactQAdapterError(RuntimeError):
    """Base class for fail-closed adapter errors."""


class ExactQAuthorityError(ExactQAdapterError):
    """Raised before importing V9F when run-specific authority is absent."""


class ExactQCaptureError(ExactQAdapterError):
    """Raised when source structure, query output, or no-write proof drifts."""


class _QueryCaptured(BaseException):
    pass


def workspace_root(start: Path | None = None) -> Path:
    here = (start or Path(__file__)).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise ExactQAdapterError("workspace root not found")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _canonical_sha256(payload: Mapping[str, Any], excluded_keys: set[str]) -> str:
    material = {
        key: value for key, value in payload.items() if key not in excluded_keys
    }
    canonical = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest().upper()


def _capture_line(source_text: str, marker: str = CAPTURE_MARKER) -> int:
    matches = [
        index
        for index, line in enumerate(source_text.splitlines(), start=1)
        if line.strip() == marker
    ]
    if len(matches) != 1:
        raise ExactQCaptureError(
            f"capture marker count must be exactly one, observed {len(matches)}"
        )
    return matches[0]


def static_audit_frozen_v9f(
    source_path: Path | None = None,
    *,
    expected_sha256: str = V9F_SOURCE_SHA256,
) -> dict[str, Any]:
    """Audit the frozen source without importing it or loading geometry."""

    root = workspace_root()
    path = (source_path or (root / V9F_SOURCE_REL)).resolve()
    source = path.read_text(encoding="utf-8")
    observed_sha = sha256_file(path)
    capture_line = _capture_line(source)
    tree = ast.parse(source, filename=str(path))
    main_defs = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "main"
    ]
    evaluator_lines = [
        index
        for index, line in enumerate(source.splitlines(), start=1)
        if line.strip().startswith("def eval_clearance(")
    ]
    output_write_lines = [
        index
        for index, line in enumerate(source.splitlines(), start=1)
        if "with open(OUT_" in line
    ]
    checks = {
        "source_hash_matches_frozen_pin": observed_sha == expected_sha256,
        "exactly_one_main_definition": len(main_defs) == 1,
        "exactly_one_main_local_eval_clearance": len(evaluator_lines) == 1,
        "eval_clearance_precedes_capture": bool(
            evaluator_lines and evaluator_lines[0] < capture_line
        ),
        "exactly_three_declared_output_writes": len(output_write_lines) == 3,
        "all_declared_output_writes_follow_capture": bool(
            output_write_lines
            and all(line > capture_line for line in output_write_lines)
        ),
        "capture_marker_is_unique": True,
    }
    return {
        "schema": "ODR60_FROZEN_V9F_STATIC_ADAPTER_AUDIT_V1",
        "scope": "ROUTE_C_HARNESS_POINTWISE_MESH_CLEARANCE_ONLY",
        "source": {
            "path": str(path.relative_to(root)).replace("\\", "/"),
            "sha256": observed_sha,
            "expected_sha256": expected_sha256,
            "bytes": path.stat().st_size,
        },
        "capture_line": capture_line,
        "eval_clearance_line": evaluator_lines[0] if evaluator_lines else None,
        "declared_output_write_lines": output_write_lines,
        "checks": checks,
        "pass": all(checks.values()),
        "current_geometry_loaded": False,
        "exact_q_query_executed": False,
        "accepted_run_authority_pin_present": bool(
            ACCEPTED_OWNER_AUTHORITY_RECEIPT_REL
            and ACCEPTED_OWNER_AUTHORITY_RECEIPT_SHA256
        ),
        "current_exact_q_execution_admitted": False,
        "complete_system_collision": False,
        "continuous_edge_evaluated": False,
        "v2_base_link_operational_proxy_bound": False,
        "path_search_executed": False,
    }


def _normalize_q(q: Sequence[float]) -> tuple[float, ...]:
    if isinstance(q, (str, bytes)) or len(q) != 6:
        raise ExactQCaptureError("q must contain exactly six revolute coordinates")
    values = tuple(float(value) for value in q)
    if not all(math.isfinite(value) for value in values):
        raise ExactQCaptureError("q contains a non-finite coordinate")
    return values


def _artifact_state(paths: Sequence[Path]) -> dict[str, tuple[bool, int | None, str | None]]:
    state: dict[str, tuple[bool, int | None, str | None]] = {}
    for path in paths:
        if path.is_file():
            state[str(path)] = (True, path.stat().st_size, sha256_file(path))
        else:
            state[str(path)] = (False, None, None)
    return state


def _json_safe(value: Any, nonfinite_paths: list[str], path: str = "$") -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _json_safe(item, nonfinite_paths, f"{path}.{key}")
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [
            _json_safe(item, nonfinite_paths, f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    if hasattr(value, "item"):
        try:
            return _json_safe(value.item(), nonfinite_paths, path)
        except (TypeError, ValueError):
            pass
    if isinstance(value, float) and not math.isfinite(value):
        nonfinite_paths.append(path)
        return None
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise ExactQCaptureError(f"query result contains unsupported value at {path}")


def _normalize_v9f_frame_result(
    frame_locals: Mapping[str, Any], q: tuple[float, ...]
) -> dict[str, Any]:
    required = {
        "arm",
        "eval_clearance",
        "own_best_global",
        "own_detail_global",
        "own_pinch",
        "own_clearance_comparison_count",
    }
    missing = sorted(required.difference(frame_locals))
    if missing:
        raise ExactQCaptureError(f"missing V9F main-local symbols: {missing}")

    arm = frame_locals["arm"]
    limits = []
    for joint in arm.rev:
        lower = float(joint["lo"])
        upper = float(joint["hi"])
        limits.append({"joint": joint["name"], "lower": lower, "upper": upper})
    outside = [
        item["joint"]
        for item, value in zip(limits, q)
        if value < item["lower"] or value > item["upper"]
    ]
    if outside:
        raise ExactQCaptureError(f"q violates frozen joint limits: {outside}")

    raw = copy.deepcopy(frame_locals["eval_clearance"](q))
    if not isinstance(raw, dict):
        raise ExactQCaptureError("eval_clearance did not return a mapping")
    own_best = float(frame_locals["own_best_global"])
    if own_best < float(raw.get("clearance", math.inf)):
        raw["clearance"] = own_best
        raw["clearance_raw"] = None
        raw["detail"] = copy.deepcopy(frame_locals["own_detail_global"])
        raw["limiting_class"] = "POSE_INVARIANT_OWN_HOST"
    else:
        raw["limiting_class"] = "POSE_DEPENDENT_EXACT_Q"

    raw_pinch = raw.get("pinch", {})
    raw["pinch"] = {
        name: min(float(raw_pinch.get(name, math.inf)), float(value))
        for name, value in frame_locals["own_pinch"].items()
    }
    counts = dict(raw.get("comparison_counts", {}))
    counts["pose_invariant_own_host"] = int(
        frame_locals["own_clearance_comparison_count"]
    )
    counts["total_including_pose_invariant_own_host"] = int(
        counts.get("total", 0) + counts["pose_invariant_own_host"]
    )
    raw["comparison_counts"] = counts

    nonfinite_paths: list[str] = []
    safe_result = _json_safe(raw, nonfinite_paths)
    clearance = safe_result.get("clearance")
    comparison_total = safe_result.get("comparison_counts", {}).get(
        "total_including_pose_invariant_own_host", 0
    )
    query_valid = (
        clearance is not None
        and isinstance(clearance, (int, float))
        and math.isfinite(float(clearance))
        and int(comparison_total) > 0
        and safe_result.get("detail") is not None
    )
    payload = {
        "schema": "ODR60_FROZEN_V9F_EXACT_Q_QUERY_RESULT_V1",
        "scope": "ROUTE_C_HARNESS_POINTWISE_MESH_CLEARANCE_ONLY",
        "authority": "READ_ONLY_SINGLE_POSE_LEGACY_V9F_LOCAL_HARNESS_QUERY",
        "q_rad": list(q),
        "q_binary64_hex": [value.hex() for value in q],
        "joint_limits": limits,
        "result": safe_result,
        "nonfinite_result_paths_replaced_with_null": nonfinite_paths,
        "query_valid": query_valid,
        "classification": (
            "LEGACY_V9F_LOCAL_QUERY_COMPLETE__NOT_SYSTEM_COLLISION_AUTHORITY"
            if query_valid
            else "UNKNOWN_ABORT"
        ),
        "geometry_authority_limits": {
            "mesh_manifest_sha256": V9F_MESH_MANIFEST_SHA256,
            "legacy_raw_base_link_source_sha256": (
                V9F_LEGACY_RAW_BASE_LINK_SOURCE_SHA256
            ),
            "v2_base_link_operational_proxy_bound": False,
            "centerline_sample_spacing_mm": 1.5,
            "centerline_spatial_discretization_allowance_bound": None,
            "system_pair_ids_returned": False,
        },
        "complete_system_collision": False,
        "continuous_edge_evaluated": False,
        "system_pair_evaluation_authorized": False,
        "path_search_authorized": False,
        "path_search_executed": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    payload["core_result_sha256"] = _canonical_sha256(
        payload, {"core_result_sha256"}
    )
    return payload


def _capture_main_local_query(
    source_path: Path,
    expected_sha256: str,
    q: Sequence[float],
    *,
    normalizer: Callable[[Mapping[str, Any], tuple[float, ...]], dict[str, Any]] = (
        _normalize_v9f_frame_result
    ),
    marker: str = CAPTURE_MARKER,
) -> dict[str, Any]:
    """Internal capture primitive; exposed to synthetic tests, not authorization."""

    path = source_path.resolve()
    observed_sha = sha256_file(path)
    if observed_sha != expected_sha256:
        raise ExactQCaptureError(
            f"source hash mismatch: expected {expected_sha256}, observed {observed_sha}"
        )
    q_value = _normalize_q(q)
    source_text = path.read_text(encoding="utf-8")
    capture_line = _capture_line(source_text, marker)
    module_name = f"_odr60_exact_q_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ExactQCaptureError("cannot construct source module spec")
    module = importlib.util.module_from_spec(spec)
    holder: dict[str, Any] = {}
    previous_fast = os.environ.get("RC_FAST")
    previous_tag = os.environ.get("RC_FAST_OUTPUT_TAG")
    previous_trace = sys.gettrace()
    os.environ["RC_FAST"] = "0"
    os.environ["RC_FAST_OUTPUT_TAG"] = ""
    stdout = io.StringIO()
    stderr = io.StringIO()
    output_paths: list[Path] = []
    before_state: dict[str, tuple[bool, int | None, str | None]] = {}

    def trace(frame: Any, event: str, _arg: Any) -> Any:
        if (
            event == "line"
            and Path(frame.f_code.co_filename).resolve() == path
            and frame.f_lineno == capture_line
        ):
            sys.settrace(None)
            holder["payload"] = normalizer(frame.f_locals, q_value)
            raise _QueryCaptured()
        return trace

    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            for name in ("OUT_SWEEP", "OUT_LEDGER", "OUT_GATE"):
                value = getattr(module, name, None)
                if value is not None:
                    output_paths.append(Path(value).resolve())
            before_state = _artifact_state(output_paths)
            sys.settrace(trace)
            try:
                module.main()
            except _QueryCaptured:
                pass
            finally:
                sys.settrace(previous_trace)
    finally:
        sys.settrace(previous_trace)
        sys.modules.pop(module_name, None)
        if previous_fast is None:
            os.environ.pop("RC_FAST", None)
        else:
            os.environ["RC_FAST"] = previous_fast
        if previous_tag is None:
            os.environ.pop("RC_FAST_OUTPUT_TAG", None)
        else:
            os.environ["RC_FAST_OUTPUT_TAG"] = previous_tag

    if "payload" not in holder:
        raise ExactQCaptureError("capture marker was not reached")
    after_state = _artifact_state(output_paths)
    if after_state != before_state:
        raise ExactQCaptureError("evaluator output artifact state changed during query")
    holder["payload"]["adapter_execution"] = {
        "source_sha256": observed_sha,
        "capture_line": capture_line,
        "declared_output_artifact_count": len(output_paths),
        "declared_output_artifacts_unchanged_during_main_before_capture": True,
        "side_effect_claim_scope": (
            "THREE_DECLARED_V9F_OUTPUT_ARTIFACTS_ONLY__"
            "NOT_A_PROOF_OF_ZERO_UNDECLARED_OR_IMPORT_TIME_SIDE_EFFECTS"
        ),
        "captured_log_line_count": len(stdout.getvalue().splitlines()),
        "captured_stderr_empty": not bool(stderr.getvalue()),
        "prior_python_trace_restored": sys.gettrace() is previous_trace,
    }
    holder["payload"]["adapter_query_receipt_sha256"] = _canonical_sha256(
        holder["payload"], {"adapter_query_receipt_sha256"}
    )
    return holder["payload"]


def _load_json_receipt(path: Path, expected_sha256: str) -> dict[str, Any]:
    root = workspace_root()
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ExactQAuthorityError("authority receipt is outside the project") from exc
    if not resolved.is_file():
        raise ExactQAuthorityError("authority receipt is absent")
    if not isinstance(expected_sha256, str) or not re.fullmatch(
        r"[0-9A-Fa-f]{64}", expected_sha256
    ):
        raise ExactQAuthorityError("authority receipt hash pin is invalid")
    observed = sha256_file(resolved)
    if observed != expected_sha256.upper():
        raise ExactQAuthorityError("authority receipt hash mismatch")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExactQAuthorityError("authority receipt is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ExactQAuthorityError("authority receipt root is not a mapping")
    return payload


def _validate_current_run_admission(
    run_id: str, available_physical_memory_gib: float
) -> dict[str, Any]:
    if not isinstance(run_id, str) or re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", run_id
    ) is None:
        raise ExactQAuthorityError("run_id is absent or unsafe")
    try:
        available = float(available_physical_memory_gib)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ExactQAuthorityError("available physical memory is not numeric") from exc
    if not math.isfinite(available) or available < 0.0:
        raise ExactQAuthorityError("available physical memory is invalid")
    if not (
        ACCEPTED_OWNER_AUTHORITY_RECEIPT_REL
        and ACCEPTED_OWNER_AUTHORITY_RECEIPT_SHA256
    ):
        raise ExactQAuthorityError(
            "no hash-bound run-specific Owner authority is accepted by this build"
        )
    root = workspace_root()
    authority = _load_json_receipt(
        root / ACCEPTED_OWNER_AUTHORITY_RECEIPT_REL,
        ACCEPTED_OWNER_AUTHORITY_RECEIPT_SHA256,
    )
    required_authority = {
        "schema": OWNER_AUTHORITY_SCHEMA,
        "decision_id": "ODR-60",
        "decision_token": OWNER_OPTION_A_DECISION_TOKEN,
        "owner_approved": True,
        "run_id": run_id,
        "execution_scope": "READ_ONLY_SINGLE_POSE_LEGACY_V9F_LOCAL_HARNESS_QUERY",
        "single_run_only": True,
    }
    mismatches = [
        key
        for key, expected in required_authority.items()
        if authority.get(key) != expected
    ]
    nonce = authority.get("single_use_nonce")
    if not isinstance(nonce, str) or re.fullmatch(r"[A-Fa-f0-9]{32,128}", nonce) is None:
        mismatches.append("single_use_nonce")
    if mismatches:
        raise ExactQAuthorityError(
            f"run-specific Owner authority fields mismatch: {sorted(set(mismatches))}"
        )

    memory_gate_passed = available >= NOMINAL_AVAILABLE_PHYSICAL_MEMORY_MIN_GIB
    override_sha256 = None
    if not memory_gate_passed:
        if not (
            ACCEPTED_LOW_MEMORY_OVERRIDE_RECEIPT_REL
            and ACCEPTED_LOW_MEMORY_OVERRIDE_RECEIPT_SHA256
        ):
            raise ExactQAuthorityError(
                "memory gate did not pass and no hash-bound run-specific Owner override is accepted"
            )
        override = _load_json_receipt(
            root / ACCEPTED_LOW_MEMORY_OVERRIDE_RECEIPT_REL,
            ACCEPTED_LOW_MEMORY_OVERRIDE_RECEIPT_SHA256,
        )
        required_override = {
            "schema": LOW_MEMORY_OVERRIDE_SCHEMA,
            "run_id": run_id,
            "owner_approved": True,
            "override_token": LOW_MEMORY_OVERRIDE_TOKEN,
            "risk_acknowledged": True,
            "memory_gate_passed": False,
            "owner_override_used": True,
            "single_use_nonce": nonce,
        }
        override_mismatches = [
            key
            for key, expected in required_override.items()
            if override.get(key) != expected
        ]
        if override_mismatches:
            raise ExactQAuthorityError(
                "low-memory Owner override fields mismatch: "
                f"{sorted(override_mismatches)}"
            )
        override_sha256 = ACCEPTED_LOW_MEMORY_OVERRIDE_RECEIPT_SHA256

    return {
        "run_id": run_id,
        "authority_receipt_path": str(ACCEPTED_OWNER_AUTHORITY_RECEIPT_REL).replace(
            "\\", "/"
        ),
        "authority_receipt_sha256": ACCEPTED_OWNER_AUTHORITY_RECEIPT_SHA256,
        "single_use_nonce": nonce,
        "available_physical_memory_gib": available,
        "nominal_available_physical_memory_min_gib": (
            NOMINAL_AVAILABLE_PHYSICAL_MEMORY_MIN_GIB
        ),
        "memory_gate_passed": memory_gate_passed,
        "owner_override_used": not memory_gate_passed,
        "low_memory_override_receipt_sha256": override_sha256,
        "memory_status": (
            "PASS_NOMINAL_AVAILABLE_MEMORY"
            if memory_gate_passed
            else "OWNER_OVERRIDE_LOW_MEMORY__MEMORY_GATE_PASSED_REMAINS_FALSE"
        ),
    }


def measure_available_physical_memory_gib() -> float:
    """Measure available physical memory; never accept a caller-provided boolean."""

    if os.name == "nt":
        import ctypes

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

        status = MemoryStatusEx()
        status.dwLength = ctypes.sizeof(MemoryStatusEx)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise ExactQAuthorityError("GlobalMemoryStatusEx failed")
        return float(status.ullAvailPhys) / float(1024**3)
    if hasattr(os, "sysconf"):
        try:
            return float(os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")) / float(
                1024**3
            )
        except (ValueError, OSError, TypeError):
            pass
    raise ExactQAuthorityError("available physical memory cannot be measured")


def _claim_single_run(admission: Mapping[str, Any]) -> Path:
    receipt_dir = Path(__file__).resolve().parent / "run_receipts"
    receipt_dir.mkdir(parents=False, exist_ok=True)
    receipt_path = receipt_dir / f"{admission['run_id']}.json"
    claim = {
        "schema": "ODR60_OPTION_A_EXACT_Q_SINGLE_RUN_CONSUMPTION_V1",
        "status": "ADMISSION_CONSUMED__QUERY_NOT_COMPLETE",
        "run_admission": dict(admission),
        "query_receipt_sha256": None,
        "error": None,
    }
    try:
        with receipt_path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(claim, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
    except FileExistsError as exc:
        raise ExactQAuthorityError("run_id authority was already consumed") from exc
    return receipt_path


def _finalize_single_run_claim(
    receipt_path: Path,
    admission: Mapping[str, Any],
    *,
    status: str,
    query_receipt_sha256: str | None,
    error: str | None,
) -> None:
    payload = {
        "schema": "ODR60_OPTION_A_EXACT_Q_SINGLE_RUN_CONSUMPTION_V1",
        "status": status,
        "run_admission": dict(admission),
        "query_receipt_sha256": query_receipt_sha256,
        "error": error,
    }
    temporary = receipt_path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, receipt_path)


def evaluate_frozen_v9f_exact_q(
    q: Sequence[float],
    *,
    run_id: str,
    source_path: Path | None = None,
) -> dict[str, Any]:
    """Execute one current V9F harness query under hash-bound single-use admission."""

    available = measure_available_physical_memory_gib()
    admission = _validate_current_run_admission(run_id, available)
    root = workspace_root()
    path = (source_path or (root / V9F_SOURCE_REL)).resolve()
    audit = static_audit_frozen_v9f(path)
    if not audit["pass"]:
        raise ExactQCaptureError("frozen V9F source static audit failed")
    claim_path = _claim_single_run(admission)
    try:
        payload = _capture_main_local_query(path, V9F_SOURCE_SHA256, q)
        payload["run_admission"] = admission
        payload["run_consumption_receipt"] = {
            "path": str(claim_path.relative_to(root)).replace("\\", "/"),
            "declared_execution_side_effect": True,
        }
        payload["full_execution_receipt_sha256"] = _canonical_sha256(
            payload, {"full_execution_receipt_sha256"}
        )
    except BaseException as exc:
        _finalize_single_run_claim(
            claim_path,
            admission,
            status="ADMISSION_CONSUMED__QUERY_ABORTED",
            query_receipt_sha256=None,
            error=f"{type(exc).__name__}: {exc}",
        )
        raise
    _finalize_single_run_claim(
        claim_path,
        admission,
        status="ADMISSION_CONSUMED__QUERY_COMPLETE",
        query_receipt_sha256=payload["full_execution_receipt_sha256"],
        error=None,
    )
    return payload
