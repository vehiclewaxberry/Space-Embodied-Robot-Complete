#!/usr/bin/env python3
"""Read-only readiness assessment for a future Unified-R2 V2 issuer.

This module is deliberately not an issuer, signer, generator, or executor.  It
can only write four fixed-name reports below the project evidence directory.
It never writes the future authorization target or any adjacent run state.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import platform
import stat
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from safe_io import (
    EVIDENCE_ROOT,
    PROJECT_ROOT,
    SafeIOError,
    secure_read_bytes,
    sha256_bytes,
    write_fixed_json,
)


TOOL_DIR = Path(__file__).resolve().parent

SOURCE_DIR = (
    PROJECT_ROOT
    / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"
    / "unified_r2_digital_prototype_prebind/source_only_v2"
)
GENERATOR_SOURCE = SOURCE_DIR / "unified_r2_urdf_source_v2.py"
GENERATOR_INPUTS = SOURCE_DIR / "UNIFIED_R2_URDF_SOURCE_INPUTS_V2.yaml"
TARGET_AUTHORIZATION_FILE = SOURCE_DIR / "UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2.json"
PROTECTED_PATHS = {
    "future_authorization_target": TARGET_AUTHORIZATION_FILE,
    "run_consumption_tree": SOURCE_DIR / ".unified_r2_v2_run_consumption",
    "override_consumption_tree": SOURCE_DIR / ".unified_r2_v2_override_consumption",
    "active_run_lock": SOURCE_DIR / ".unified_r2_v2_active_run.lock",
    "future_interface_instance": (
        PROJECT_ROOT
        / "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind"
        / "interfaces/MECH_RL_SYSTEM_INTERFACE_V2.yaml"
    ),
}

REQUESTS = {
    "ODR-GPT-07": {
        "path": (
            PROJECT_ROOT
            / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/terminal_decision_pack"
            / "P2_ROM_DIMENSION_AND_VALIDITY_DECISION_REQUEST_V1.yaml"
        ),
        "bytes": 23043,
        "sha256": "679DC5D2BA2B814F584379C28E47A9F487D03277F0F1EAA45DFB85D150367D25",
        "allowed_options": {
            "A_11D_FIVE_REGISTERED_WINDOWS_CANDIDATE",
            "B_7D_NOMINAL_20MS_CANDIDATE",
            "C_6D_FIRST12_EIGENMODE_MINIMUM_AT_NOMINAL_20MS_NONPREFERRED",
            "D_RETAIN_3_TO_5_MODE_CONTRACT_KEEP_HOLD",
            "E_AUTHORIZE_SEPARATE_RESEARCH_ONLY_NONMODAL_BASIS",
            "F_REVISE_AND_RESUBMIT",
            "G_REJECT",
        },
    },
    "ODR-GPT-08": {
        "path": (
            PROJECT_ROOT
            / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/terminal_decision_pack"
            / "LEGACY_R1_COMPARATOR_SEMANTICS_DECISION_REQUEST_V1.yaml"
        ),
        "bytes": 46441,
        "sha256": "5ED037AE057F7119678DECF890C9C0E64740C1443E5E9B9682FC09B8610046F6",
        "allowed_options": {
            "A_FOUR_LANE_PROTOCOL_MATCHED_COMPARATOR",
            "B_REMOVE_LEGACY_NUMERICAL_G17_RETAIN_HISTORICAL_NARRATIVE",
            "C_RETAIN_CURRENT_SAME_SCOPE_REQUIREMENT",
            "D_REVISE_AND_RESUBMIT",
            "E_REJECT",
        },
    },
}

EXPECTED_GENERATOR_SOURCE = {
    "bytes": 24599,
    "sha256": "64AF651E928986F3492607CA74CE40F15B385357C53DD435C1A66AE6BB7A8E40",
}
EXPECTED_GENERATOR_INPUTS = {
    "bytes": 17945,
    "sha256": "8DC401FF86F6642DDD47585AD7ECE74F58831E7D3848F3B002BBF2B5952C56F3",
}

OUTPUT_NAMES = {
    "audit-current": "PREAUTHORIZATION_READINESS_CURRENT_V1.json",
    "assess-owner": "PREAUTHORIZATION_READINESS_OWNER_ASSESSMENT_V1.json",
    "verify-readiness": "PREAUTHORIZATION_READINESS_VERIFICATION_V1.json",
    "self-test": "PREAUTHORIZATION_READINESS_SELF_TEST_V1.json",
}
MAX_VALIDITY_SECONDS = 7200
MAX_OWNER_SOURCE_BYTES = 256 * 1024
MEMORY_GATE_GIB = 6.0
LOW_MEMORY_ACK = "ACCEPT_SINGLE_RUN_LOW_MEMORY_RISK"
OWNER_SCHEMA = "DIRECT_OWNER_INTENT_SOURCE_V1"

# This known attachment is the predecessor request/source, not a fresh direct
# Owner decision for ODR-GPT-07/08/C01.
KNOWN_STALE_EXTERNAL_SOURCE_HASHES = {
    "67821E04869BE8202CF2473980B73AA4CE595B9689CC9D54F340820C0D38F773",
}

ALLOWED_OWNER_SOURCE_ROOTS = [Path.home() / ".codex/attachments"]


class DuplicateKeyError(ValueError):
    """Raised when an Owner JSON object repeats a key."""


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _is_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    if stat.S_ISLNK(info.st_mode):
        return True
    return bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _snapshot_one(path: Path) -> dict[str, Any]:
    if not path.exists() and not path.is_symlink():
        return {"state": "ABSENT"}
    if _is_reparse(path):
        return {"state": "REPARSE_POINT_PRESENT_FAIL_CLOSED"}
    if path.is_file():
        return {
            "state": "FILE",
            "bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
        }
    if not path.is_dir():
        return {"state": "OTHER_FAIL_CLOSED"}
    entries: list[dict[str, Any]] = []
    for item in sorted(path.rglob("*"), key=lambda value: value.as_posix()):
        relative = item.relative_to(path).as_posix()
        if _is_reparse(item):
            entries.append({"path": relative, "state": "REPARSE_POINT_PRESENT_FAIL_CLOSED"})
        elif item.is_file():
            entries.append(
                {
                    "path": relative,
                    "state": "FILE",
                    "bytes": item.stat().st_size,
                    "sha256": _sha256_file(item),
                }
            )
        elif item.is_dir():
            entries.append({"path": relative, "state": "DIRECTORY"})
        else:
            entries.append({"path": relative, "state": "OTHER_FAIL_CLOSED"})
    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return {"state": "DIRECTORY", "entry_count": len(entries), "tree_sha256": _sha256_bytes(canonical)}


def protected_state_snapshot() -> dict[str, Any]:
    return {name: _snapshot_one(path) for name, path in PROTECTED_PATHS.items()}


def _pin_status(path: Path, expected: dict[str, Any]) -> dict[str, Any]:
    try:
        display_path = path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        display_path = str(path.absolute())
    try:
        allowed_root = PROJECT_ROOT if _is_relative_to(path.absolute(), PROJECT_ROOT.absolute()) else path.parent
        raw, _ = secure_read_bytes(path, allowed_roots=[allowed_root], max_bytes=2 * 1024 * 1024)
    except (OSError, SafeIOError):
        return {
            "path": display_path,
            "expected_bytes": expected["bytes"],
            "expected_sha256": expected["sha256"],
            "actual_bytes": None,
            "actual_sha256": None,
            "pass": False,
        }
    actual_bytes = len(raw)
    actual_sha = _sha256_bytes(raw)
    return {
        "path": display_path,
        "expected_bytes": expected["bytes"],
        "expected_sha256": expected["sha256"],
        "actual_bytes": actual_bytes,
        "actual_sha256": actual_sha,
        "pass": actual_bytes == expected["bytes"] and actual_sha == expected["sha256"],
    }


def _request_statuses() -> dict[str, Any]:
    return {decision_id: _pin_status(item["path"], item) for decision_id, item in REQUESTS.items()}


def _source_statuses() -> dict[str, Any]:
    return {
        "generator_source": _pin_status(GENERATOR_SOURCE, EXPECTED_GENERATOR_SOURCE),
        "generator_inputs": _pin_status(GENERATOR_INPUTS, EXPECTED_GENERATOR_INPUTS),
    }


def _available_memory_gib() -> tuple[float | None, str]:
    if os.name == "nt":
        class MEMORYSTATUSEX(ctypes.Structure):
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

        record = MEMORYSTATUSEX()
        record.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        try:
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(record)):
                return record.ullAvailPhys / (1024.0**3), "WINDOWS_GLOBAL_MEMORY_STATUS_EX"
        except (AttributeError, OSError):
            pass
        return None, "WINDOWS_MEASUREMENT_UNAVAILABLE"
    try:
        value = int(os.sysconf("SC_PAGE_SIZE")) * int(os.sysconf("SC_AVPHYS_PAGES")) / (1024.0**3)
        return value, "POSIX_SYSCONF"
    except (AttributeError, OSError, TypeError, ValueError):
        return None, "MEASUREMENT_UNAVAILABLE"


def _runtime_hash_preview() -> dict[str, Any]:
    """Return policy only; generator code is never imported, compiled, or executed."""

    return {
        "preview_only": True,
        "loaded_instance_scope": None,
        "runtime_code_sha256_preview": None,
        "status": "NOT_COMPUTED_BY_DESIGN_NONAUTHORITATIVE",
        "error": None,
        "generator_source_loaded": False,
        "generator_source_imported": False,
        "generator_source_compiled": False,
        "generator_source_executed": False,
        "reusable_by_future_issuer": False,
        "future_issuer_must_recompute_with_generator_in_same_loaded_instance_and_process": True,
        "explicit_warning": (
            "The future issuer must recompute the loaded-code hash in the exact same module instance and process "
            "that calls the generator; this readiness preview must never be copied into an authorization record."
        ),
    }


def _parse_utc(text: Any) -> datetime:
    if not isinstance(text, str):
        raise ValueError("OWNER_STATEMENT_UTC_MISSING")
    value = text.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError("OWNER_STATEMENT_UTC_NOT_EXPLICIT_UTC")
    return parsed.astimezone(timezone.utc)


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"DUPLICATE_KEY:{key}")
        result[key] = value
    return result


def _read_direct_owner_source(
    source: Path,
    expected_sha256: str,
    now: datetime,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    provenance: dict[str, Any] = {
        "present": True,
        "source_path": str(source.absolute()),
        "expected_source_sha256": expected_sha256.upper(),
        "actual_source_sha256": None,
        "bytes": None,
        "raw_bytes_parsed": False,
        "path_policy_pass": False,
        "reparse_or_symlink_detected": None,
        "source_freshness_pass": False,
        "source_schema_pass": False,
        "operator_supplied_decisions": False,
        "identity_authentication_status": "OUT_OF_SCOPE_REQUIRES_FUTURE_ISSUER",
        "status": "DENY_UNASSESSED",
    }
    if len(expected_sha256) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in expected_sha256):
        provenance["status"] = "DENY_INVALID_EXPECTED_SOURCE_SHA256"
        return None, provenance
    lexical = source.absolute()
    if _is_relative_to(lexical, PROJECT_ROOT.resolve()):
        provenance["status"] = "DENY_OWNER_SOURCE_PATH_OUTSIDE_DIRECT_ATTACHMENT_BOUNDARY"
        return None, provenance
    try:
        payload, handle_meta = secure_read_bytes(
            lexical,
            allowed_roots=ALLOWED_OWNER_SOURCE_ROOTS,
            max_bytes=MAX_OWNER_SOURCE_BYTES,
        )
    except SafeIOError as exc:
        token = str(exc)
        provenance["reparse_or_symlink_detected"] = "REPARSE" in token or "SYMLINK" in token
        provenance["failure_detail_class"] = token.split(":", 1)[0]
        provenance["status"] = (
            "DENY_REPARSE_OR_SYMLINK_OWNER_SOURCE"
            if provenance["reparse_or_symlink_detected"]
            else "DENY_SECURE_OWNER_SOURCE_HANDLE"
        )
        return None, provenance
    final_path = Path(handle_meta["final_handle_path"])
    if final_path.suffix.lower() not in {".json", ".txt"}:
        provenance["status"] = "DENY_OWNER_SOURCE_TYPE"
        return None, provenance
    provenance["reparse_or_symlink_detected"] = False
    provenance["path_policy_pass"] = True
    provenance["secure_handle_read"] = handle_meta
    stable = handle_meta["handle_identity_stable"]
    actual_sha = _sha256_bytes(payload)
    provenance["bytes"] = len(payload)
    provenance["actual_source_sha256"] = actual_sha
    provenance["read_snapshot_stable"] = stable
    if not stable:
        provenance["status"] = "DENY_OWNER_SOURCE_CHANGED_DURING_READ"
        return None, provenance
    if actual_sha != expected_sha256.upper():
        provenance["status"] = "DENY_OWNER_SOURCE_HASH_MISMATCH"
        return None, provenance
    if actual_sha in KNOWN_STALE_EXTERNAL_SOURCE_HASHES:
        provenance["status"] = "DENY_KNOWN_STALE_PREDECESSOR_SOURCE"
        return None, provenance
    try:
        decoded = payload.decode("utf-8-sig")
        if "\x00" in decoded:
            raise ValueError("NUL_BYTE")
        data = json.loads(decoded, object_pairs_hook=_reject_duplicate_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, DuplicateKeyError, ValueError, RecursionError) as exc:
        provenance["failure_detail_class"] = type(exc).__name__
        provenance["status"] = "DENY_OWNER_SOURCE_PARSE"
        return None, provenance
    provenance["raw_bytes_parsed"] = True
    if not isinstance(data, dict):
        provenance["status"] = "DENY_OWNER_SOURCE_ROOT_NOT_OBJECT"
        return None, provenance
    required_top = {
        "schema",
        "record_type",
        "origin",
        "owner_role_assertion",
        "owner_statement_utc",
        "decisions",
    }
    if set(data) != required_top:
        provenance["status"] = "DENY_OWNER_SOURCE_TOP_LEVEL_SCHEMA_OR_EXTRA_FIELDS"
        return None, provenance
    if (
        data.get("schema") != OWNER_SCHEMA
        or data.get("record_type") != "DIRECT_OWNER_SOURCE_NOT_MACHINE_AUTHORIZATION"
        or data.get("origin") != "USER_OR_OWNER_DIRECT_EXPORT"
        or data.get("owner_role_assertion") != "PROJECT_OWNER"
    ):
        provenance["status"] = "DENY_REQUEST_TEMPLATE_SELF_OR_NONOWNER_SOURCE"
        return None, provenance
    try:
        source_time = _parse_utc(data.get("owner_statement_utc"))
    except (TypeError, ValueError):
        provenance["status"] = "DENY_INVALID_OWNER_STATEMENT_TIME"
        return None, provenance
    age_seconds = (now - source_time).total_seconds()
    provenance["owner_statement_utc"] = _utc_text(source_time)
    provenance["owner_source_age_seconds"] = age_seconds
    if age_seconds < -300 or age_seconds >= MAX_VALIDITY_SECONDS:
        provenance["status"] = "DENY_STALE_OR_FUTURE_OWNER_SOURCE"
        return None, provenance
    provenance["source_freshness_pass"] = True
    if not isinstance(data.get("decisions"), dict):
        provenance["status"] = "DENY_OWNER_DECISIONS_NOT_OBJECT"
        return None, provenance
    expected_decision_keys = {
        "odr_gpt_07",
        "odr_gpt_08",
        "c01_unified_r2_research_candidate",
    }
    if set(data["decisions"]) != expected_decision_keys:
        provenance["decision_keys_observed"] = sorted(data["decisions"])
        provenance["decision_keys_expected"] = sorted(expected_decision_keys)
        provenance["status"] = "DENY_OWNER_DECISION_KEYSET_MUST_BE_EXACT"
        return None, provenance
    provenance["source_schema_pass"] = True
    provenance["status"] = "DIRECT_SOURCE_PARSED_FOR_READINESS_ONLY"
    return data, provenance


def _empty_decision(decision_id: str) -> dict[str, Any]:
    return {
        "decision_id": decision_id,
        "source_section_present": False,
        "request_binding_pass": False if decision_id.startswith("ODR") else None,
        "decision_schema_pass": False,
        "selected_option": None,
        "state": "NOT_READY_NO_DIRECT_OWNER_SOURCE",
        "authority_effect": "NONE",
    }


def _assess_odr(decision_id: str, section: Any, request_pin: dict[str, Any]) -> dict[str, Any]:
    result = _empty_decision(decision_id)
    result["source_section_present"] = section is not None
    if not isinstance(section, dict):
        result["state"] = "DENY_MISSING_OR_INVALID_DECISION_SECTION"
        return result
    required = {"decision_id", "decision", "selected_option", "request_sha256"}
    selected_raw = section.get("selected_option")
    decision_raw = section.get("decision")
    request_sha_raw = section.get("request_sha256")
    schema_pass = (
        set(section) == required
        and section.get("decision_id") == decision_id
        and isinstance(decision_raw, str)
        and isinstance(selected_raw, str)
        and isinstance(request_sha_raw, str)
        and len(request_sha_raw) == 64
        and all(character in "0123456789ABCDEF" for character in request_sha_raw)
    )
    result["decision_schema_pass"] = schema_pass
    result["selected_option"] = selected_raw if isinstance(selected_raw, str) else None
    result["decision"] = decision_raw if isinstance(decision_raw, str) else None
    result["request_sha256_from_owner_source"] = request_sha_raw if isinstance(request_sha_raw, str) else None
    result["request_sha256_expected"] = REQUESTS[decision_id]["sha256"]
    result["request_binding_pass"] = (
        schema_pass
        and request_pin["pass"]
        and request_sha_raw == REQUESTS[decision_id]["sha256"]
    )
    option_pass = isinstance(selected_raw, str) and selected_raw in REQUESTS[decision_id]["allowed_options"]
    result["selected_option_registered"] = option_pass
    selected_text = selected_raw if isinstance(selected_raw, str) else ""
    negative_or_hold_selection = any(
        token in selected_text
        for token in ("REJECT", "REVISE_AND_RESUBMIT", "KEEP_HOLD")
    )
    approve = decision_raw == "APPROVE"
    result["selected_option_is_negative_or_hold"] = negative_or_hold_selection
    result["affirmative_decision"] = approve and not negative_or_hold_selection
    if not schema_pass:
        result["state"] = "DENY_DECISION_SCHEMA_OR_EXTRA_FIELDS"
    elif not result["request_binding_pass"]:
        result["state"] = "DENY_REQUEST_HASH_DRIFT_OR_OWNER_BINDING_MISMATCH"
    elif not option_pass:
        result["state"] = "DENY_UNREGISTERED_OR_CONFLICTING_SELECTION"
    elif negative_or_hold_selection or not approve:
        result["state"] = "OWNER_DECISION_NEGATIVE_OR_NONAPPROVAL_RECORDED_NO_READINESS"
    else:
        result["state"] = "READY_FOR_SEPARATE_DECISION_RECORD_REVIEW"
    return result


def _assess_c01(section: Any, memory: dict[str, Any]) -> dict[str, Any]:
    result = _empty_decision("C01-UNIFIED-R2-RESEARCH-CANDIDATE")
    result.update(
        {
            "configuration": "C01_DEPLOYED_NOMINAL_FIXED_SOLAR_SNAPSHOT",
            "selected_bus_mass_mode": "EXPLICIT_STRUCTURE_PLUS_RESIDUAL",
            "total_design_mass_kg": 31.022864807342987,
            "route_c_is_in_model": False,
            "route_c_geometry_status": "HOLD_ABSENT",
            "candidate_scope_required": ["ANALYSIS_ONLY", "RESEARCH_CANDIDATE", "NON_PRODUCTION"],
            "prohibited_permissions": {
                "route_c_cad_authorized": False,
                "production_dynamics_authorized": False,
                "physical_contact_authorized": False,
                "sim13_rebind_authorized": False,
                "next_stage_authorized": False,
                "release_credit": False,
            },
        }
    )
    result["source_section_present"] = section is not None
    if not isinstance(section, dict):
        result["state"] = "DENY_MISSING_C01_INDEPENDENT_INTENT_SECTION"
        return result
    required = {
        "decision_id",
        "decision",
        "configuration",
        "selected_bus_mass_mode",
        "route_c_exclusion_accepted_for_this_sim_candidate",
        "route_c_cad_authorized",
        "scope",
        "production_dynamics_authorized",
        "physical_contact_authorized",
        "sim13_rebind_authorized",
        "next_stage_authorized",
        "release_credit",
        "low_memory_risk_ack",
    }
    schema_pass = set(section) == required and section.get("decision_id") == result["decision_id"]
    result["decision_schema_pass"] = schema_pass
    checks = {
        "affirmative_decision": section.get("decision") == "APPROVE",
        "configuration_exact": section.get("configuration") == result["configuration"],
        "mass_mode_exact": section.get("selected_bus_mass_mode") == result["selected_bus_mass_mode"],
        "route_c_exclusion_exact_true": section.get("route_c_exclusion_accepted_for_this_sim_candidate") is True,
        "route_c_cad_exact_false": section.get("route_c_cad_authorized") is False,
        "scope_exact": isinstance(section.get("scope"), list)
        and all(isinstance(item, str) for item in section.get("scope", []))
        and set(section.get("scope", [])) == set(result["candidate_scope_required"])
        and len(section.get("scope", [])) == 3,
        "production_dynamics_exact_false": section.get("production_dynamics_authorized") is False,
        "physical_contact_exact_false": section.get("physical_contact_authorized") is False,
        "sim13_rebind_exact_false": section.get("sim13_rebind_authorized") is False,
        "next_stage_exact_false": section.get("next_stage_authorized") is False,
        "release_credit_exact_false": section.get("release_credit") is False,
    }
    ack_required = memory["low_memory_ack_required_at_preview"]
    ack = section.get("low_memory_risk_ack")
    checks["low_memory_ack"] = (
        (ack == LOW_MEMORY_ACK) if ack_required else (ack is None or ack == LOW_MEMORY_ACK)
    )
    result["checks"] = checks
    result["low_memory_risk_ack_present_exact"] = ack == LOW_MEMORY_ACK
    result["low_memory_risk_ack_required_at_preview"] = ack_required
    if not schema_pass:
        result["state"] = "DENY_C01_SCHEMA_OR_EXTRA_FIELDS"
    elif not all(checks.values()):
        result["state"] = "DENY_C01_CONFLICT_NEGATION_OR_LOW_MEMORY_ACK_MISSING"
    else:
        result["state"] = "READY_FOR_SEPARATE_C01_ISSUER_REVIEW"
    return result


def _memory_preview() -> dict[str, Any]:
    available, source = _available_memory_gib()
    ack_required = available is None or available < MEMORY_GATE_GIB
    if available is None:
        status = "UNKNOWN_REQUIRES_EXACT_OWNER_RISK_ACK_FOR_FUTURE_SINGLE_RUN"
    elif available < MEMORY_GATE_GIB:
        status = "BELOW_6_GIB_REQUIRES_EXACT_OWNER_RISK_ACK_FOR_FUTURE_SINGLE_RUN"
    else:
        status = "AT_OR_ABOVE_6_GIB_PREVIEW_ONLY_FUTURE_EXECUTION_MUST_REMEASURE"
    return {
        "preview_only": True,
        "measurement_source": source,
        "available_memory_gib_preview": available,
        "memory_gate_gib": MEMORY_GATE_GIB,
        "status": status,
        "low_memory_ack_required_at_preview": ack_required,
        "required_ack_exact": LOW_MEMORY_ACK if ack_required else None,
        "memory_gate_passed": False,
        "owner_override_effect_created": False,
        "future_execution_must_remeasure": True,
    }


def _validity_status(valid_for_seconds: Any) -> tuple[bool, int | None, str]:
    if isinstance(valid_for_seconds, bool):
        return False, None, "DENY_INVALID_VALIDITY_WINDOW"
    try:
        if isinstance(valid_for_seconds, float) and not valid_for_seconds.is_integer():
            raise ValueError
        value = int(valid_for_seconds)
    except (TypeError, ValueError, OverflowError):
        return False, None, "DENY_INVALID_VALIDITY_WINDOW"
    if value <= 0 or value > MAX_VALIDITY_SECONDS:
        return False, value, "DENY_INVALID_VALIDITY_WINDOW"
    return True, value, "VALID_PREVIEW_WINDOW"


def build_readiness_report(
    *,
    owner_source: Path | None,
    expected_source_sha256: str | None,
    valid_for_seconds: Any,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = (now or _now_utc()).astimezone(timezone.utc)
    protected_before = protected_state_snapshot()
    request_pins = _request_statuses()
    source_pins = _source_statuses()
    memory = _memory_preview()
    runtime_preview = _runtime_hash_preview()
    validity_pass, validity_seconds, validity_state = _validity_status(valid_for_seconds)

    owner_data: dict[str, Any] | None = None
    if owner_source is None:
        owner_provenance = {
            "present": False,
            "source_path": None,
            "expected_source_sha256": None,
            "actual_source_sha256": None,
            "bytes": None,
            "raw_bytes_parsed": False,
            "path_policy_pass": False,
            "reparse_or_symlink_detected": None,
            "source_freshness_pass": False,
            "source_schema_pass": False,
            "operator_supplied_decisions": False,
            "identity_authentication_status": "NOT_APPLICABLE_NO_SOURCE",
            "status": "DENY_NO_DIRECT_OWNER_SOURCE",
        }
    elif expected_source_sha256 is None:
        owner_provenance = {
            "present": True,
            "source_path": str(owner_source),
            "status": "DENY_EXPECTED_SOURCE_SHA256_REQUIRED",
            "operator_supplied_decisions": False,
        }
    else:
        owner_data, owner_provenance = _read_direct_owner_source(
            owner_source, expected_source_sha256, now
        )

    decisions_source = owner_data.get("decisions", {}) if isinstance(owner_data, dict) else {}
    odr07 = _assess_odr("ODR-GPT-07", decisions_source.get("odr_gpt_07"), request_pins["ODR-GPT-07"])
    odr08 = _assess_odr("ODR-GPT-08", decisions_source.get("odr_gpt_08"), request_pins["ODR-GPT-08"])
    c01 = _assess_c01(decisions_source.get("c01_unified_r2_research_candidate"), memory)

    request_pass = all(item["pass"] for item in request_pins.values())
    source_pass = all(item["pass"] for item in source_pins.values())
    intent_pass = all(
        item["state"].startswith("READY_FOR_SEPARATE")
        for item in (odr07, odr08, c01)
    )
    protected_after = protected_state_snapshot()
    protected_unchanged = protected_before == protected_after

    if not request_pass:
        state = "DENY_REQUEST_HASH_DRIFT"
    elif not source_pass:
        state = "DENY_FROZEN_SOURCE_OR_INPUT_HASH_DRIFT"
    elif not protected_unchanged:
        state = "DENY_PROTECTED_TARGET_OR_RUNTIME_STATE_CHANGED"
    elif not validity_pass:
        state = validity_state
    elif owner_source is None:
        state = "DENY_NO_DIRECT_OWNER_SOURCE"
    elif owner_data is None:
        state = owner_provenance["status"]
    elif not intent_pass:
        state = "DENY_INCOMPLETE_NEGATIVE_OR_CONFLICTING_INDEPENDENT_OWNER_INTENTS"
    else:
        state = "STRUCTURALLY_READY_FOR_AUTHENTICATED_ISSUER_REVIEW__IDENTITY_UNVERIFIED__NO_AUTHORITY_CREATED"

    expires = now + timedelta(seconds=validity_seconds or 0)
    if owner_data is not None and owner_provenance.get("owner_statement_utc"):
        owner_statement_time = _parse_utc(owner_provenance["owner_statement_utc"])
        expires = min(expires, owner_statement_time + timedelta(seconds=MAX_VALIDITY_SECONDS))
    checks = {
        "request_hashes_match": request_pass,
        "frozen_generator_source_and_inputs_match": source_pass,
        "validity_window_is_positive_and_leq_7200_seconds": validity_pass,
        "direct_owner_source_parsed": owner_data is not None,
        "odr_gpt_07_independent_intent_ready": odr07["state"].startswith("READY_FOR_SEPARATE"),
        "odr_gpt_08_independent_intent_ready": odr08["state"].startswith("READY_FOR_SEPARATE"),
        "c01_independent_intent_ready": c01["state"].startswith("READY_FOR_SEPARATE"),
        "odr_07_and_08_do_not_imply_c01": True,
        "runtime_hash_deliberately_not_computed": runtime_preview["runtime_code_sha256_preview"] is None
        and runtime_preview["status"] == "NOT_COMPUTED_BY_DESIGN_NONAUTHORITATIVE",
        "generator_source_not_loaded_imported_compiled_or_executed": all(
            runtime_preview[key] is False
            for key in (
                "generator_source_loaded",
                "generator_source_imported",
                "generator_source_compiled",
                "generator_source_executed",
            )
        ),
        "protected_target_and_adjacent_state_observed_before_after_unchanged": protected_unchanged,
        "formal_authorization_target_written": False,
        "urdf_or_interface_written": False,
    }
    return {
        "schema": "PREAUTHORIZATION_READINESS_REPORT_V1",
        "artifact_class": "READ_ONLY_PREAUTHORIZATION_READINESS__NOT_AUTHORIZATION",
        "generated_utc": _utc_text(now),
        "summary": {
            "state": state,
            "authority_effect": "NONE",
            "execution_authorized": False,
            "target_authorization_written": False,
            "next_stage_authorized": False,
            "release_credit": False,
            "owner_accepted": False,
            "owner_identity_verified": False,
            "tooling_credit_only": True,
        },
        "owner_source_provenance": owner_provenance,
        "request_bindings": request_pins,
        "frozen_source_bindings": source_pins,
        "decision_readiness": {
            "odr_gpt_07": odr07,
            "odr_gpt_08": odr08,
            "c01_unified_r2_research_candidate": c01,
        },
        "c01_fixed_candidate_contract": {
            "configuration": "C01_DEPLOYED_NOMINAL_FIXED_SOLAR_SNAPSHOT",
            "selected_bus_mass_mode": "EXPLICIT_STRUCTURE_PLUS_RESIDUAL",
            "total_design_mass_kg": 31.022864807342987,
            "route_c_excluded": True,
            "route_c_cad_authorized": False,
            "scope": ["ANALYSIS_ONLY", "RESEARCH_CANDIDATE", "NON_PRODUCTION"],
            "execution_authorized": False,
            "urdf_write_authorized": False,
            "sim13_rebind_authorized": False,
            "production_dynamics_ready": False,
            "physical_contact_ready": False,
            "next_stage_authorized": False,
            "release_credit": False,
        },
        "ephemeral_preview": {
            "preview_only": True,
            "preview_id": f"READINESS-{uuid.uuid4().hex.upper()}",
            "issued_utc_preview": _utc_text(now),
            "expires_utc_preview": _utc_text(expires),
            "valid_for_seconds_requested": valid_for_seconds,
            "valid_for_seconds_normalized": validity_seconds,
            "validity_status": validity_state,
            "source_sha256_preview": source_pins["generator_source"]["actual_sha256"],
            "input_sha256_preview": source_pins["generator_inputs"]["actual_sha256"],
            "runtime_hash": runtime_preview,
            "may_be_reused_by_future_issuer": False,
        },
        "memory_preview": memory,
        "protected_state": {
            "before": protected_before,
            "after": protected_after,
            "observed_before_after_unchanged": protected_unchanged,
            "claim_limit": (
                "Endpoint equality is an observation, not proof that no transient write ever occurred; "
                "the no-generation claim additionally depends on absence of a generator execution path and static call audit."
            ),
        },
        "checks": checks,
        "formal_authorization_incompatibility": {
            "readiness_report_may_not_be_renamed_or_copied_as_authorization": True,
            "formal_schema_match": False,
            "rejection_reasons": [
                "artifact_class is readiness-only",
                "top-level execution grant fields are absent",
                "summary.owner_accepted is exact false",
                "summary.execution_authorized is exact false",
                "no run or override identifier exists",
                "runtime hash is deliberately not computed and no runtime value is reusable",
                "memory_gate_passed is exact false",
            ],
        },
        "prohibitions": [
            "NO_AUTHORIZATION_ISSUANCE",
            "NO_GENERATOR_OR_PRIVATE_BUILDER_INVOCATION",
            "NO_URDF_OR_INTERFACE_CREATION",
            "NO_RUN_CONSUMPTION_MARKER_OR_ACTIVE_LOCK",
            "NO_ROUTE_C_CAD_AUTHORITY",
            "NO_SIM13_REBIND_OR_PRODUCTION_CONTACT_AUTHORITY",
            "NO_NEXT_STAGE_OR_RELEASE_CREDIT",
        ],
    }


def _guarded_output_path(command: str) -> Path:
    if command not in OUTPUT_NAMES:
        raise RuntimeError("OUTPUT_NAME_NOT_ALLOWLISTED")
    root = EVIDENCE_ROOT.resolve()
    path = EVIDENCE_ROOT / OUTPUT_NAMES[command]
    if path.name != OUTPUT_NAMES[command] or path.parent.resolve() != root:
        raise RuntimeError("OUTPUT_PATH_BOUNDARY_VIOLATION")
    return path


def _pin_evidence_exact(pin: Any) -> bool:
    return bool(
        isinstance(pin, dict)
        and pin.get("pass") is True
        and isinstance(pin.get("expected_bytes"), int)
        and pin.get("expected_bytes") == pin.get("actual_bytes")
        and isinstance(pin.get("expected_sha256"), str)
        and len(pin.get("expected_sha256")) == 64
        and pin.get("expected_sha256") == pin.get("actual_sha256")
    )


def _owner_intent_evidence_checks(data: dict[str, Any] | None) -> dict[str, bool]:
    """Evaluate every readiness-only fact without authenticating the Owner."""

    if not isinstance(data, dict):
        return {"report_is_object": False}
    summary = data.get("summary", {})
    provenance = data.get("owner_source_provenance", {})
    report_checks = data.get("checks", {})
    decisions = data.get("decision_readiness", {})
    request_bindings = data.get("request_bindings", {})
    source_bindings = data.get("frozen_source_bindings", {})
    runtime = data.get("ephemeral_preview", {}).get("runtime_hash", {})
    protected = data.get("protected_state", {})
    odr07 = decisions.get("odr_gpt_07", {})
    odr08 = decisions.get("odr_gpt_08", {})
    c01 = decisions.get("c01_unified_r2_research_candidate", {})
    c01_checks = c01.get("checks", {})

    def odr_ready(decision: Any) -> bool:
        return bool(
            isinstance(decision, dict)
            and decision.get("source_section_present") is True
            and decision.get("decision_schema_pass") is True
            and decision.get("request_binding_pass") is True
            and decision.get("selected_option_registered") is True
            and decision.get("selected_option_is_negative_or_hold") is False
            and decision.get("affirmative_decision") is True
            and decision.get("decision") == "APPROVE"
            and decision.get("state") == "READY_FOR_SEPARATE_DECISION_RECORD_REVIEW"
            and isinstance(decision.get("request_sha256_from_owner_source"), str)
            and decision.get("request_sha256_from_owner_source")
            == decision.get("request_sha256_expected")
        )

    expected_c01_checks = {
        "affirmative_decision",
        "configuration_exact",
        "mass_mode_exact",
        "route_c_exclusion_exact_true",
        "route_c_cad_exact_false",
        "scope_exact",
        "production_dynamics_exact_false",
        "physical_contact_exact_false",
        "sim13_rebind_exact_false",
        "next_stage_exact_false",
        "release_credit_exact_false",
        "low_memory_ack",
    }
    expected_decision_keys = {
        "odr_gpt_07",
        "odr_gpt_08",
        "c01_unified_r2_research_candidate",
    }
    expected_report_ready_checks = {
        "direct_owner_source_parsed",
        "odr_gpt_07_independent_intent_ready",
        "odr_gpt_08_independent_intent_ready",
        "c01_independent_intent_ready",
        "request_hashes_match",
        "frozen_generator_source_and_inputs_match",
        "validity_window_is_positive_and_leq_7200_seconds",
        "runtime_hash_deliberately_not_computed",
        "generator_source_not_loaded_imported_compiled_or_executed",
        "protected_target_and_adjacent_state_observed_before_after_unchanged",
        "odr_07_and_08_do_not_imply_c01",
    }
    provenance_hashes_equal = bool(
        isinstance(provenance.get("expected_source_sha256"), str)
        and len(provenance.get("expected_source_sha256")) == 64
        and provenance.get("expected_source_sha256") == provenance.get("actual_source_sha256")
    )
    secure_meta = provenance.get("secure_handle_read", {})
    return {
        "ready_state_exact": summary.get("state")
        == "STRUCTURALLY_READY_FOR_AUTHENTICATED_ISSUER_REVIEW__IDENTITY_UNVERIFIED__NO_AUTHORITY_CREATED",
        "summary_authority_effect_none": summary.get("authority_effect") == "NONE",
        "summary_all_authority_and_release_flags_false": all(
            summary.get(key) is False
            for key in (
                "execution_authorized",
                "target_authorization_written",
                "owner_accepted",
                "next_stage_authorized",
                "release_credit",
            )
        ),
        "summary_owner_identity_unverified": summary.get("owner_identity_verified") is False,
        "summary_tooling_credit_only": summary.get("tooling_credit_only") is True,
        "provenance_direct_source_present": provenance.get("present") is True,
        "provenance_source_path_present": isinstance(provenance.get("source_path"), str)
        and bool(provenance.get("source_path")),
        "provenance_raw_bytes_parsed": provenance.get("raw_bytes_parsed") is True,
        "provenance_path_policy_pass": provenance.get("path_policy_pass") is True,
        "provenance_no_reparse": provenance.get("reparse_or_symlink_detected") is False,
        "provenance_fresh": provenance.get("source_freshness_pass") is True,
        "provenance_schema_pass": provenance.get("source_schema_pass") is True,
        "provenance_status_exact": provenance.get("status")
        == "DIRECT_SOURCE_PARSED_FOR_READINESS_ONLY",
        "provenance_operator_did_not_supply_decisions": provenance.get("operator_supplied_decisions")
        is False,
        "provenance_identity_unverified": provenance.get("identity_authentication_status")
        == "OUT_OF_SCOPE_REQUIRES_FUTURE_ISSUER",
        "provenance_hashes_equal": provenance_hashes_equal,
        "provenance_bytes_positive": isinstance(provenance.get("bytes"), int)
        and provenance.get("bytes") > 0,
        "provenance_read_snapshot_stable": provenance.get("read_snapshot_stable") is True,
        "provenance_secure_file_and_parent_handles_stable": secure_meta.get("handle_identity_stable")
        is True
        and secure_meta.get("parent_directory_handle_stable") is True,
        "decision_keyset_exact": set(decisions) == expected_decision_keys,
        "report_ready_checks_exact_true": all(
            report_checks.get(key) is True for key in expected_report_ready_checks
        ),
        "formal_target_and_urdf_write_checks_false": report_checks.get(
            "formal_authorization_target_written"
        )
        is False
        and report_checks.get("urdf_or_interface_written") is False,
        "request_pins_exact": set(request_bindings) == {"ODR-GPT-07", "ODR-GPT-08"}
        and all(_pin_evidence_exact(pin) for pin in request_bindings.values()),
        "frozen_source_pins_exact": set(source_bindings) == {"generator_source", "generator_inputs"}
        and all(_pin_evidence_exact(pin) for pin in source_bindings.values()),
        "odr_gpt_07_evidence_ready": odr_ready(odr07),
        "odr_gpt_08_evidence_ready": odr_ready(odr08),
        "c01_source_and_schema_ready": isinstance(c01, dict)
        and c01.get("source_section_present") is True
        and c01.get("decision_schema_pass") is True
        and c01.get("state") == "READY_FOR_SEPARATE_C01_ISSUER_REVIEW",
        "c01_all_exact_checks_true": isinstance(c01_checks, dict)
        and set(c01_checks) == expected_c01_checks
        and all(c01_checks.get(key) is True for key in expected_c01_checks),
        "runtime_hash_not_computed": runtime.get("runtime_code_sha256_preview") is None
        and runtime.get("status") == "NOT_COMPUTED_BY_DESIGN_NONAUTHORITATIVE"
        and runtime.get("reusable_by_future_issuer") is False,
        "runtime_generator_never_loaded_imported_compiled_or_executed": all(
            runtime.get(key) is False
            for key in (
                "generator_source_loaded",
                "generator_source_imported",
                "generator_source_compiled",
                "generator_source_executed",
            )
        ),
        "protected_endpoints_observed_unchanged": protected.get(
            "observed_before_after_unchanged"
        )
        is True
        and protected.get("before") == protected.get("after"),
    }


def _verify_readiness_raw_bytes(
    raw: bytes,
    *,
    report_path: Path,
    now: datetime | None = None,
    secure_read_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = (now or _now_utc()).astimezone(timezone.utc)
    checks: dict[str, bool] = {}
    errors: list[str] = []
    data: dict[str, Any] | None = None
    try:
        decoded = raw.decode("utf-8-sig")
        if "\x00" in decoded:
            raise ValueError("NUL_BYTE")
        parsed = json.loads(decoded, object_pairs_hook=_reject_duplicate_pairs)
        if not isinstance(parsed, dict):
            raise ValueError("REPORT_ROOT_NOT_OBJECT")
        data = parsed
    except Exception as exc:
        errors.append(f"RAW_PARSE:{type(exc).__name__}:{exc}")

    expected_top = {
        "schema",
        "artifact_class",
        "generated_utc",
        "summary",
        "owner_source_provenance",
        "request_bindings",
        "frozen_source_bindings",
        "decision_readiness",
        "c01_fixed_candidate_contract",
        "ephemeral_preview",
        "memory_preview",
        "protected_state",
        "checks",
        "formal_authorization_incompatibility",
        "prohibitions",
    }
    forbidden_formal_top = {
        "owner_accepted",
        "authority_flags",
        "run_id",
        "issued_utc",
        "expires_utc",
        "source_sha256",
        "input_sha256",
        "runtime_code_sha256",
    }
    if data is not None:
        checks["exact_top_level_whitelist"] = set(data) == expected_top
        checks["no_formal_authorization_top_level_fields"] = not forbidden_formal_top.intersection(data)
        try:
            import jsonschema

            schema = json.loads(
                (TOOL_DIR / "PREAUTHORIZATION_READINESS_SCHEMA_V1.json").read_text(encoding="utf-8")
            )
            jsonschema.Draft202012Validator(schema).validate(data)
            checks["complete_json_schema"] = True
        except Exception as exc:
            checks["complete_json_schema"] = False
            errors.append(f"SCHEMA:{type(exc).__name__}:{exc}")
        summary = data.get("summary", {})
        checks.update(
            {
                "artifact_class": data.get("artifact_class")
                == "READ_ONLY_PREAUTHORIZATION_READINESS__NOT_AUTHORIZATION",
                "authority_effect_none": summary.get("authority_effect") == "NONE",
                "execution_false": summary.get("execution_authorized") is False,
                "target_not_written": summary.get("target_authorization_written") is False,
                "owner_accepted_false": summary.get("owner_accepted") is False,
                "owner_identity_unverified": summary.get("owner_identity_verified") is False,
                "next_stage_false": summary.get("next_stage_authorized") is False,
                "release_credit_false": summary.get("release_credit") is False,
                "runtime_hash_null_by_design": data.get("ephemeral_preview", {})
                .get("runtime_hash", {})
                .get("runtime_code_sha256_preview")
                is None,
                "runtime_preview_nonreusable": data.get("ephemeral_preview", {})
                .get("runtime_hash", {})
                .get("reusable_by_future_issuer")
                is False,
                "memory_gate_not_claimed_pass": data.get("memory_preview", {}).get("memory_gate_passed")
                is False,
                "formal_schema_match_false": data.get("formal_authorization_incompatibility", {}).get(
                    "formal_schema_match"
                )
                is False,
                "protected_state_observed_unchanged": data.get("protected_state", {}).get(
                    "observed_before_after_unchanged"
                )
                is True,
            }
        )
        try:
            issued = _parse_utc(data["ephemeral_preview"]["issued_utc_preview"])
            expires = _parse_utc(data["ephemeral_preview"]["expires_utc_preview"])
            window = (expires - issued).total_seconds()
            checks["preview_issued_not_future"] = issued <= now
            checks["preview_live_now_before_expiry"] = now < expires
            checks["preview_window_positive_and_leq_7200"] = 0 < window <= MAX_VALIDITY_SECONDS
        except Exception as exc:
            checks["preview_issued_not_future"] = False
            checks["preview_live_now_before_expiry"] = False
            checks["preview_window_positive_and_leq_7200"] = False
            errors.append(f"TIME:{type(exc).__name__}:{exc}")

    structural_keys = {
        "exact_top_level_whitelist",
        "no_formal_authorization_top_level_fields",
        "complete_json_schema",
        "artifact_class",
        "authority_effect_none",
        "execution_false",
        "target_not_written",
        "owner_accepted_false",
        "owner_identity_unverified",
        "next_stage_false",
        "release_credit_false",
        "runtime_hash_null_by_design",
        "runtime_preview_nonreusable",
        "memory_gate_not_claimed_pass",
        "formal_schema_match_false",
        "protected_state_observed_unchanged",
    }
    structural_passed = data is not None and all(checks.get(key, False) for key in structural_keys)
    live_readiness_passed = structural_passed and all(
        checks.get(key, False)
        for key in (
            "preview_issued_not_future",
            "preview_live_now_before_expiry",
            "preview_window_positive_and_leq_7200",
        )
    )
    owner_intent_evidence_checks = _owner_intent_evidence_checks(data)
    owner_intents_ready = bool(
        structural_passed
        and owner_intent_evidence_checks
        and all(owner_intent_evidence_checks.values())
    )
    if not structural_passed:
        verification_state = "FAIL_READINESS_REPORT_STRUCTURE__NO_AUTHORITY_EFFECT"
    elif not live_readiness_passed:
        verification_state = "STRUCTURAL_REPORT_NOT_LIVE__OWNER_INTENTS_NOT_ACTIONABLE__NO_AUTHORITY_EFFECT"
    elif owner_intents_ready:
        verification_state = (
            "LIVE_STRUCTURAL_OWNER_INTENTS_EVIDENCE_READY__IDENTITY_UNVERIFIED__NO_AUTHORITY_EFFECT"
        )
    else:
        verification_state = "LIVE_STRUCTURAL_ARTIFACT__OWNER_INTENTS_NOT_READY__NO_AUTHORITY_EFFECT"
    return {
        "schema": "PREAUTHORIZATION_READINESS_VERIFICATION_V1",
        "artifact_class": "READ_ONLY_VERIFICATION__NO_AUTHORITY_EFFECT",
        "generated_utc": _utc_text(now),
        "report_path": str(report_path.absolute()),
        "report_bytes": len(raw),
        "report_sha256": sha256_bytes(raw),
        "secure_single_handle_read": secure_read_meta,
        "checks": checks,
        "structural_passed": structural_passed,
        "live_readiness_passed": live_readiness_passed,
        "live_readiness_scope": "ARTIFACT_TIME_WINDOW_ONLY__NOT_ISSUER_OR_EXECUTION_READINESS",
        "verification_state": verification_state,
        "owner_intent_evidence_checks": owner_intent_evidence_checks,
        "owner_intents_ready": owner_intents_ready,
        "owner_identity_verified": False,
        "signing_or_execution_ready": False,
        "errors": errors,
        "authority_effect": "NONE",
        "execution_authorized": False,
        "target_authorization_written": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }


def _verification_payload(report_path: Path, now: datetime | None = None) -> dict[str, Any]:
    try:
        raw, meta = secure_read_bytes(report_path, allowed_roots=[EVIDENCE_ROOT], max_bytes=MAX_OWNER_SOURCE_BYTES)
        return _verify_readiness_raw_bytes(raw, report_path=report_path, now=now, secure_read_meta=meta)
    except Exception as exc:
        current = (now or _now_utc()).astimezone(timezone.utc)
        return {
            "schema": "PREAUTHORIZATION_READINESS_VERIFICATION_V1",
            "artifact_class": "READ_ONLY_VERIFICATION__NO_AUTHORITY_EFFECT",
            "generated_utc": _utc_text(current),
            "report_path": str(report_path.absolute()),
            "report_bytes": None,
            "report_sha256": None,
            "secure_single_handle_read": None,
            "checks": {},
            "structural_passed": False,
            "live_readiness_passed": False,
            "live_readiness_scope": "ARTIFACT_TIME_WINDOW_ONLY__NOT_ISSUER_OR_EXECUTION_READINESS",
            "verification_state": "FAIL_SECURE_REPORT_READ__NO_AUTHORITY_EFFECT",
            "owner_intent_evidence_checks": {"report_is_object": False},
            "owner_intents_ready": False,
            "owner_identity_verified": False,
            "signing_or_execution_ready": False,
            "errors": [f"SECURE_READ:{type(exc).__name__}:{exc}"],
            "authority_effect": "NONE",
            "execution_authorized": False,
            "target_authorization_written": False,
            "next_stage_authorized": False,
            "release_credit": False,
        }


def _self_test_payload() -> dict[str, Any]:
    before = protected_state_snapshot()
    request_pins = _request_statuses()
    source_pins = _source_statuses()
    forbidden_tokens = ("gen_" + "urdf" + "(", "_" + "build_robot" + "(")
    source_text = Path(__file__).read_text(encoding="utf-8")
    parser = _make_parser()
    help_text = parser.format_help()
    checks = {
        "request_07_hash": request_pins["ODR-GPT-07"]["pass"],
        "request_08_hash": request_pins["ODR-GPT-08"]["pass"],
        "generator_source_hash": source_pins["generator_source"]["pass"],
        "generator_input_hash": source_pins["generator_inputs"]["pass"],
        "no_generator_call_token": forbidden_tokens[0] not in source_text,
        "no_private_builder_call_token": forbidden_tokens[1] not in source_text,
        "no_issuance_subcommand": all(
            token not in help_text
            for token in ("issue" + " ", "run" + " ", "write" + "-target")
        ),
        "no_force_option": "--" + "force" not in help_text,
        "no_output_path_option": "--" + "output" not in help_text,
        "target_not_present": before["future_authorization_target"]["state"] == "ABSENT",
        "runtime_state_not_present": all(
            before[name]["state"] == "ABSENT"
            for name in ("run_consumption_tree", "override_consumption_tree", "active_run_lock")
        ),
        "interface_not_present": before["future_interface_instance"]["state"] == "ABSENT",
    }
    no_owner = build_readiness_report(
        owner_source=None,
        expected_source_sha256=None,
        valid_for_seconds=MAX_VALIDITY_SECONDS,
    )
    checks.update(
        {
            "no_owner_denied": no_owner["summary"]["state"] == "DENY_NO_DIRECT_OWNER_SOURCE",
            "no_owner_authority_none": no_owner["summary"]["authority_effect"] == "NONE",
            "no_owner_execution_false": no_owner["summary"]["execution_authorized"] is False,
            "no_owner_target_false": no_owner["summary"]["target_authorization_written"] is False,
            "no_owner_next_stage_false": no_owner["summary"]["next_stage_authorized"] is False,
            "no_owner_release_false": no_owner["summary"]["release_credit"] is False,
            "no_owner_owner_accepted_false": no_owner["summary"]["owner_accepted"] is False,
            "no_owner_identity_unverified": no_owner["summary"]["owner_identity_verified"] is False,
            "readiness_formal_schema_false": no_owner["formal_authorization_incompatibility"]["formal_schema_match"]
            is False,
            "memory_gate_not_claimed_pass": no_owner["memory_preview"]["memory_gate_passed"] is False,
            "runtime_preview_nonreusable": no_owner["ephemeral_preview"]["runtime_hash"]["reusable_by_future_issuer"]
            is False,
            "runtime_hash_not_computed_by_design": no_owner["ephemeral_preview"]["runtime_hash"][
                "runtime_code_sha256_preview"
            ]
            is None,
            "generator_never_loaded_by_runtime_preview": all(
                no_owner["ephemeral_preview"]["runtime_hash"][key] is False
                for key in (
                    "generator_source_loaded",
                    "generator_source_imported",
                    "generator_source_compiled",
                    "generator_source_executed",
                )
            ),
            "invalid_zero_window_denied": _validity_status(0)[0] is False,
            "invalid_long_window_denied": _validity_status(MAX_VALIDITY_SECONDS + 1)[0] is False,
            "valid_max_window_accepted_for_preview": _validity_status(MAX_VALIDITY_SECONDS)[0] is True,
        }
    )
    after = protected_state_snapshot()
    checks["protected_target_and_adjacent_state_observed_unchanged"] = before == after
    return {
        "schema": "PREAUTHORIZATION_READINESS_SELF_TEST_V1",
        "artifact_class": "TOOL_SELF_TEST_ONLY__NO_AUTHORITY_EFFECT",
        "generated_utc": _utc_text(_now_utc()),
        "checks": checks,
        "summary": {
            "passed": all(checks.values()),
            "passed_count": sum(checks.values()),
            "total_count": len(checks),
        },
        "authority_effect": "NONE",
        "execution_authorized": False,
        "target_authorization_written": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }


def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only Unified-R2 V2 preauthorization readiness auditor; never an issuer or executor."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("audit-current", help="Write the fixed current denial/readiness report.")
    assess = subparsers.add_parser("assess-owner", help="Assess raw direct Owner source bytes for issuer readiness.")
    assess.add_argument("--owner-source", required=True, type=Path)
    assess.add_argument("--expected-source-sha256", required=True)
    assess.add_argument("--valid-for-seconds", required=True)
    verify = subparsers.add_parser("verify-readiness", help="Verify a readiness report; this never promotes it.")
    verify.add_argument("report", type=Path)
    subparsers.add_parser("self-test", help="Run bounded read-only safety checks.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _make_parser().parse_args(argv)
    before = protected_state_snapshot()
    if args.command == "audit-current":
        payload = build_readiness_report(
            owner_source=None,
            expected_source_sha256=None,
            valid_for_seconds=MAX_VALIDITY_SECONDS,
        )
    elif args.command == "assess-owner":
        payload = build_readiness_report(
            owner_source=args.owner_source,
            expected_source_sha256=args.expected_source_sha256,
            valid_for_seconds=args.valid_for_seconds,
        )
    elif args.command == "verify-readiness":
        payload = _verification_payload(args.report)
    elif args.command == "self-test":
        payload = _self_test_payload()
    else:  # argparse makes this unreachable
        raise RuntimeError("UNKNOWN_COMMAND_FAIL_CLOSED")
    after_assessment = protected_state_snapshot()
    if before != after_assessment:
        raise RuntimeError("PROTECTED_TARGET_OR_RUNTIME_STATE_CHANGED_DURING_ASSESSMENT")
    output_receipt = write_fixed_json(OUTPUT_NAMES[args.command], payload)
    output = Path(output_receipt["path"])
    after_write = protected_state_snapshot()
    if before != after_write:
        raise RuntimeError("PROTECTED_TARGET_OR_RUNTIME_STATE_CHANGED_DURING_REPORT_WRITE")
    print(
        json.dumps(
            {
                "command": args.command,
                "report": str(output),
                "state": payload.get("summary", {}).get(
                    "state", payload.get("verification_state")
                ),
                "authority_effect": "NONE",
            },
            sort_keys=True,
        )
    )
    if args.command == "verify-readiness" and not (
        payload.get("structural_passed") is True
        and payload.get("live_readiness_passed") is True
    ):
        return 2
    if args.command == "self-test" and not payload.get("summary", {}).get("passed", False):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
