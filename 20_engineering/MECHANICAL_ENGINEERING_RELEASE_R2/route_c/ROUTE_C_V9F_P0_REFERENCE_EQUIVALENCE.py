#!/usr/bin/env python3
"""Fail-closed dynamic equivalence check for the V9F FAST reference and P0.

The tagged P0 run is allowed to add one root-level ``execution_metadata``
object solely to isolate output paths.  Every other JSON value and every CSV
byte must match the archived-reference implementation's untagged FAST run.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
REFERENCE_SOURCE = (
    HERE
    / "_work"
    / "v9f_evaluator_pre_redteam_fix"
    / "ROUTE_C_EXACT_SWEEP_V9F_PRE_PERFORMANCE_REFERENCE.py"
)
P0_SOURCE = HERE / "ROUTE_C_EXACT_SWEEP_V9F.py"
REFERENCE_SOURCE_SHA256 = (
    "46732BB71605E6EE52488C6324FB47E5E7C009490A3E94F49DE95EC2B0DF6244"
)
P0_SOURCE_SHA256 = (
    "9F26AC9A8DE5E2EEB57103F07B769EB43AC30A8FBAFD90FE8DF5D501FA8C8A7F"
)
PROVENANCE_RUNNER = HERE / "ROUTE_C_V9F_PROVENANCE_RUNNER.py"
PROVENANCE_RUNNER_SHA256 = (
    "01773C4E4149449E5834D1E2974E11DFA1C5D2291ED7E1DD67276BA859BC9E9B"
)

REFERENCE_FILES = {
    "sweep": HERE / "ROUTE_C_EXACT_SWEEP_V9F.json",
    "ledger": HERE / "ROUTE_C_ROBUST_MARGIN_LEDGER_V9F.csv",
    "gate": HERE / "ROUTE_C_MISSION_COVERAGE_GATE_V9F.json",
}
P0_FILES = {
    "sweep": HERE / "ROUTE_C_EXACT_SWEEP_V9F_P0_BENCH.json",
    "ledger": HERE / "ROUTE_C_ROBUST_MARGIN_LEDGER_V9F_P0_BENCH.csv",
    "gate": HERE / "ROUTE_C_MISSION_COVERAGE_GATE_V9F_P0_BENCH.json",
}
OUT = HERE / "ROUTE_C_V9F_P0_REFERENCE_EQUIVALENCE.json"
REFERENCE_RECEIPT = HERE / "ROUTE_C_V9F_FAST_REFERENCE_RUN_RECEIPT.json"
P0_RECEIPT = HERE / "ROUTE_C_V9F_FAST_P0_BENCH_RUN_RECEIPT.json"

EXPECTED_TAG_METADATA = {
    "fast_output_tag": "P0_BENCH",
    "scope": "OUTPUT_PATH_ISOLATION_ONLY__NOT_A_SCIENTIFIC_INPUT",
    "output_basenames": [
        "ROUTE_C_EXACT_SWEEP_V9F_P0_BENCH.json",
        "ROUTE_C_ROBUST_MARGIN_LEDGER_V9F_P0_BENCH.csv",
        "ROUTE_C_MISSION_COVERAGE_GATE_V9F_P0_BENCH.json",
    ],
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_once(path: Path) -> tuple[bytes, str]:
    """Return the exact bytes used by both parsing/comparison and hashing."""
    data = path.read_bytes()
    return data, sha256_bytes(data)


def resolved_child_for_comparison(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def finite_tree(value: Any) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(finite_tree(v) for v in value.values())
    if isinstance(value, list):
        return all(finite_tree(v) for v in value)
    return True


def first_differences(a: Any, b: Any, path: str = "$", limit: int = 32) -> list[dict]:
    out: list[dict] = []

    def walk(left: Any, right: Any, where: str) -> None:
        if len(out) >= limit:
            return
        if type(left) is not type(right):
            out.append(
                {
                    "path": where,
                    "kind": "TYPE_MISMATCH",
                    "reference_type": type(left).__name__,
                    "p0_type": type(right).__name__,
                    "reference": repr(left),
                    "p0": repr(right),
                }
            )
            return
        if isinstance(left, dict):
            left_keys = set(left)
            right_keys = set(right)
            for key in sorted(left_keys - right_keys):
                out.append({"path": f"{where}.{key}", "kind": "MISSING_IN_P0"})
                if len(out) >= limit:
                    return
            for key in sorted(right_keys - left_keys):
                out.append({"path": f"{where}.{key}", "kind": "EXTRA_IN_P0"})
                if len(out) >= limit:
                    return
            for key in sorted(left_keys & right_keys):
                walk(left[key], right[key], f"{where}.{key}")
                if len(out) >= limit:
                    return
            return
        if isinstance(left, list):
            if len(left) != len(right):
                out.append(
                    {
                        "path": where,
                        "kind": "LENGTH_MISMATCH",
                        "reference": len(left),
                        "p0": len(right),
                    }
                )
                return
            for index, (lv, rv) in enumerate(zip(left, right)):
                walk(lv, rv, f"{where}[{index}]")
                if len(out) >= limit:
                    return
            return
        if left != right:
            out.append(
                {
                    "path": where,
                    "kind": "VALUE_MISMATCH",
                    "reference": repr(left),
                    "p0": repr(right),
                }
            )

    walk(a, b, path)
    return out


def reject_constant(token: str) -> None:
    raise ValueError(f"non-finite JSON constant rejected: {token}")


def unique_object(pairs: list[tuple[str, Any]]) -> dict:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key rejected: {key}")
        value[key] = item
    return value


def load_json_bytes(data: bytes, label: str) -> dict:
    text = data.decode("utf-8")
    value = json.loads(
        text,
        parse_constant=reject_constant,
        object_pairs_hook=unique_object,
    )
    if not isinstance(value, dict):
        raise ValueError(f"root is not an object: {label}")
    return value


def csv_structure_and_finiteness(data: bytes, label: str) -> tuple[bool, str | None]:
    try:
        text = data.decode("utf-8")
        rows = list(csv.reader(io.StringIO(text, newline="")))
    except Exception as exc:  # pragma: no cover - fail-closed diagnostic
        return False, f"{label}: CSV parse/decode failed: {exc}"
    expected_header = ["margin_id", "unit", "value", "acceptance", "status", "basis"]
    if not rows or rows[0] != expected_header:
        return False, f"{label}: header mismatch"
    if len(rows) < 2:
        return False, f"{label}: no data rows"
    allowed_value_sentinels = {
        "UNKNOWN",
        "NOT_EVALUATED_IN_KEY_STATE_FAST_CHECK",
        "SKIPPED_IN_FAST_MODE",
    }
    for row_index, row in enumerate(rows[1:], start=2):
        if len(row) != len(expected_header):
            return False, f"{label}: row {row_index} has {len(row)} columns"
        value_cell = row[2]
        if value_cell in allowed_value_sentinels:
            continue
        try:
            number = float(value_cell)
        except ValueError:
            return False, f"{label}: unapproved nonnumeric value at row {row_index}: {value_cell!r}"
        if not math.isfinite(number):
            return False, f"{label}: non-finite numeric value at row {row_index}: {value_cell!r}"
    return True, None


def validate_receipt(
    receipt: dict,
    *,
    role: str,
    source_sha: str,
    expected_tag: str,
    output_hashes: dict[str, str],
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    role_name = "reference" if role == "REFERENCE_FAST" else "p0"
    source_path = (
        "_work/v9f_evaluator_pre_redteam_fix/ROUTE_C_EXACT_SWEEP_V9F_PRE_PERFORMANCE_REFERENCE.py"
        if role_name == "reference"
        else "ROUTE_C_EXACT_SWEEP_V9F.py"
    )

    def exact(key: str, wanted: Any) -> None:
        actual = receipt.get(key)
        if type(actual) is not type(wanted) or actual != wanted:
            errors.append(
                f"{key}: expected exact {type(wanted).__name__} {wanted!r}, "
                f"got {type(actual).__name__} {actual!r}"
            )

    expected = {
        "schema": "ROUTE_C_V9F_PROVENANCE_RUN_RECEIPT_V1",
        "role": role,
        "source_sha256": source_sha,
        "fast_mode": True,
        "fast_output_tag": expected_tag,
        "child_exit_code": 0,
        "completed": True,
        "runner_sha256": PROVENANCE_RUNNER_SHA256,
        "runner_sha256_after": PROVENANCE_RUNNER_SHA256,
        "runner_unchanged_across_run": True,
        "source_sha256_after": source_sha,
        "source_unchanged_across_run": True,
        "source_path": source_path,
        "runner_path": PROVENANCE_RUNNER.name,
        "fake_evaluator_file_for_here_semantics": str(P0_SOURCE),
        "execution_mode": "PINNED_SOURCE_BYTES_COMPILE_EXEC_WITH_BUILTIN_OPEN_OUTPUT_REDIRECT",
        "output_publish_from_isolated_staging": True,
        "staged_output_set_complete": True,
        "publish_performed": True,
        "staging_publish_hash_match": True,
        "output_set_complete": True,
        "preexisting_outputs_moved_to_archive": True,
        "authority": "EXECUTION_PROVENANCE_ONLY__NO_GEOMETRY_OR_RELEASE_CREDIT",
        "next_stage_authorized": False,
        "release_credit": False,
        "recoverability_scope": "LAUNCH_PREEXISTING_AND_PREPUBLISH_SNAPSHOTS__UNCOOPERATIVE_WRITER_RACE_NOT_CLAIMED",
    }
    for key, wanted in expected.items():
        exact(key, wanted)
    actual_output_hashes = receipt.get("output_sha256")
    if type(actual_output_hashes) is not dict or actual_output_hashes != output_hashes:
        errors.append("output_sha256 does not bind the exact compared bytes")
    staged_output_hashes = receipt.get("staged_output_sha256")
    if type(staged_output_hashes) is not dict or staged_output_hashes != output_hashes:
        errors.append("staged_output_sha256 does not match compared output bytes")
    published_output_hashes = receipt.get("published_output_sha256")
    if type(published_output_hashes) is not dict or published_output_hashes != output_hashes:
        errors.append("published_output_sha256 does not match compared output bytes")

    run_id = receipt.get("run_id")
    if type(run_id) is not str or re.fullmatch(r"[A-Z0-9_-]{1,64}", run_id) is None:
        errors.append("run_id is missing or outside the runner whitelist")
        run_id = "INVALID"
    expected_run_root = Path("_work") / "v9f_provenance_runs" / run_id
    expected_staging = str(expected_run_root / "staging").replace("\\", "/")
    expected_log = str(expected_run_root / "child_stdout_stderr.log").replace("\\", "/")
    expected_archive = str(expected_run_root / "preexisting").replace("\\", "/")
    exact("isolated_staging_directory", expected_staging)
    exact("child_log", expected_log)
    exact("preexisting_archive", expected_archive)
    if type(receipt.get("preexisting_moved")) is not list:
        errors.append("preexisting_moved must be a list")
    if type(receipt.get("concurrent_pre_publish_moved")) is not list:
        errors.append("concurrent_pre_publish_moved must be a list")

    command = receipt.get("command")
    if type(command) is not list or len(command) != 5:
        errors.append("command must be the five-token runner child command")
    else:
        expected_suffix = ["-B", str(PROVENANCE_RUNNER), "--child", role_name]
        if any(type(token) is not str for token in command):
            errors.append("command tokens must all be strings")
        elif command[1:] != expected_suffix:
            errors.append(f"command suffix mismatch: {command[1:]!r}")
        if receipt.get("python_executable") != command[0]:
            errors.append("python_executable does not match command[0]")
    exact("cwd", str(HERE))

    child_log = HERE / expected_log
    if not resolved_child_for_comparison(child_log, HERE) or not child_log.is_file():
        errors.append("child log is missing or outside Route-C")
    else:
        log_bytes, log_sha = read_once(child_log)
        del log_bytes
        if receipt.get("child_log_sha256") != log_sha:
            errors.append("child_log_sha256 mismatch")
    return not errors, errors


def main() -> int:
    required = [
        REFERENCE_SOURCE,
        P0_SOURCE,
        PROVENANCE_RUNNER,
        REFERENCE_RECEIPT,
        P0_RECEIPT,
        *REFERENCE_FILES.values(),
        *P0_FILES.values(),
    ]
    missing = [str(path) for path in required if not path.is_file()]
    result: dict[str, Any] = {
        "schema": "ROUTE_C_V9F_P0_REFERENCE_EQUIVALENCE_V1",
        "generated_utc": "DETERMINISTIC_REPLAY_NO_WALLCLOCK",
        "authority": "FAST_IMPLEMENTATION_EQUIVALENCE_ONLY__NO_GEOMETRY_OR_RELEASE_CREDIT",
        "comparison_contract": {
            "json_rule": "EXACT_TYPED_VALUE_EQUALITY_AFTER_REMOVING_ONLY_WHITELISTED_ROOT_EXECUTION_METADATA_FROM_TAGGED_P0",
            "csv_rule": "BYTE_FOR_BYTE_EQUALITY",
            "float_rule": "EXACT_PYTHON_VALUE_EQUALITY__NO_TOLERANCE",
            "missing_or_nonfinite": "FAIL_CLOSED",
            "provenance_rule": "BOTH_OUTPUT_SETS_MUST_BE_BOUND_TO_COMPLETED_HASH_PINNED_RUN_RECEIPTS",
            "read_rule": "EACH_FILE_READ_ONCE__SAME_BYTES_USED_FOR_HASH_PARSE_AND_COMPARISON",
            "trust_boundary": "LOCAL_WORKSPACE_AND_HASH_PINNED_RUNNER_ARE_TRUSTED__NO_EXTERNAL_SIGNATURE_OR_IMMUTABLE_LEDGER_CLAIM",
        },
        "missing_files": missing,
        "source_pins": {},
        "file_pins": {},
        "checks": {},
        "differences": {},
        "verdict": "FAIL_CLOSED_NOT_EVALUATED",
        "p0_accepted_as_reference_equivalent": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }

    if missing:
        OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return 2

    ref_source_bytes, ref_source_sha = read_once(REFERENCE_SOURCE)
    p0_source_bytes, p0_source_sha = read_once(P0_SOURCE)
    runner_bytes, runner_sha = read_once(PROVENANCE_RUNNER)
    result["source_pins"] = {
        "reference": {
            "path": str(REFERENCE_SOURCE.relative_to(HERE)).replace("\\", "/"),
            "sha256": ref_source_sha,
            "expected": REFERENCE_SOURCE_SHA256,
            "match": ref_source_sha == REFERENCE_SOURCE_SHA256,
        },
        "p0": {
            "path": P0_SOURCE.name,
            "sha256": p0_source_sha,
            "expected": P0_SOURCE_SHA256,
            "match": p0_source_sha == P0_SOURCE_SHA256,
        },
        "provenance_runner": {
            "path": PROVENANCE_RUNNER.name,
            "sha256": runner_sha,
            "expected": PROVENANCE_RUNNER_SHA256,
            "match": runner_sha == PROVENANCE_RUNNER_SHA256,
        },
    }

    del ref_source_bytes, p0_source_bytes, runner_bytes

    all_output_bytes: dict[str, dict[str, bytes]] = {"reference": {}, "p0": {}}
    all_output_hashes: dict[str, dict[str, str]] = {"reference": {}, "p0": {}}
    for role, paths in (("reference", REFERENCE_FILES), ("p0", P0_FILES)):
        for kind, path in paths.items():
            data, digest = read_once(path)
            all_output_bytes[role][kind] = data
            all_output_hashes[role][path.name] = digest
            result["file_pins"][f"{role}_{kind}"] = {
                "path": path.name,
                "sha256": digest,
            }

    parse_errors: list[str] = []
    json_equal: dict[str, bool] = {}
    metadata_checks: dict[str, bool] = {}
    finite_checks: dict[str, bool] = {}
    for kind in ("sweep", "gate"):
        try:
            ref_value = load_json_bytes(
                all_output_bytes["reference"][kind],
                REFERENCE_FILES[kind].name,
            )
            p0_value = load_json_bytes(
                all_output_bytes["p0"][kind],
                P0_FILES[kind].name,
            )
        except Exception as exc:
            parse_errors.append(f"{kind}: {exc}")
            json_equal[kind] = False
            metadata_checks[kind] = False
            finite_checks[f"reference_{kind}"] = False
            finite_checks[f"p0_{kind}"] = False
            result["differences"][kind] = [
                {"kind": "FAIL_CLOSED_PARSE_ERROR", "detail": str(exc)}
            ]
            continue
        metadata = p0_value.pop("execution_metadata", None)
        metadata_checks[kind] = metadata == EXPECTED_TAG_METADATA
        metadata_checks[f"{kind}_absent_from_reference"] = (
            "execution_metadata" not in ref_value
        )
        finite_checks[f"reference_{kind}"] = finite_tree(ref_value)
        finite_checks[f"p0_{kind}"] = finite_tree(p0_value)
        differences = first_differences(ref_value, p0_value)
        result["differences"][kind] = differences
        json_equal[kind] = not differences

    ref_ledger = all_output_bytes["reference"]["ledger"]
    p0_ledger = all_output_bytes["p0"]["ledger"]
    ledger_equal = ref_ledger == p0_ledger
    ref_ledger_finite, ref_ledger_error = csv_structure_and_finiteness(
        ref_ledger, REFERENCE_FILES["ledger"].name
    )
    p0_ledger_finite, p0_ledger_error = csv_structure_and_finiteness(
        p0_ledger, P0_FILES["ledger"].name
    )
    result["differences"]["ledger"] = [] if ledger_equal else [
        {
            "kind": "BYTE_MISMATCH",
            "reference_length": len(ref_ledger),
            "p0_length": len(p0_ledger),
        }
    ]

    receipt_parse_errors: list[str] = []
    receipt_values: dict[str, dict] = {}
    receipt_pins: dict[str, dict] = {}
    for role, path in (("reference", REFERENCE_RECEIPT), ("p0", P0_RECEIPT)):
        try:
            data, digest = read_once(path)
            receipt_values[role] = load_json_bytes(data, path.name)
            receipt_pins[role] = {"path": path.name, "sha256": digest}
        except Exception as exc:
            receipt_parse_errors.append(f"{role}: {exc}")
            receipt_values[role] = {}
            receipt_pins[role] = {"path": path.name, "sha256": None}
    result["run_receipt_pins"] = receipt_pins

    ref_receipt_ok, ref_receipt_errors = validate_receipt(
        receipt_values["reference"],
        role="REFERENCE_FAST",
        source_sha=REFERENCE_SOURCE_SHA256,
        expected_tag="",
        output_hashes=all_output_hashes["reference"],
    )
    p0_receipt_ok, p0_receipt_errors = validate_receipt(
        receipt_values["p0"],
        role="P0_FAST",
        source_sha=P0_SOURCE_SHA256,
        expected_tag="P0_BENCH",
        output_hashes=all_output_hashes["p0"],
    )
    result["run_receipt_validation"] = {
        "reference": {"pass": ref_receipt_ok, "errors": ref_receipt_errors},
        "p0": {"pass": p0_receipt_ok, "errors": p0_receipt_errors},
        "parse_errors": receipt_parse_errors,
    }

    checks = {
        "reference_source_hash_match": ref_source_sha == REFERENCE_SOURCE_SHA256,
        "p0_source_hash_match": p0_source_sha == P0_SOURCE_SHA256,
        "provenance_runner_hash_match": runner_sha == PROVENANCE_RUNNER_SHA256,
        "reference_run_receipt_bound": ref_receipt_ok,
        "p0_run_receipt_bound": p0_receipt_ok,
        "no_parse_errors": not parse_errors and not receipt_parse_errors,
        "p0_tag_metadata_exact": all(metadata_checks.values()),
        "all_json_finite": all(finite_checks.values()),
        "reference_ledger_structured_and_finite": ref_ledger_finite,
        "p0_ledger_structured_and_finite": p0_ledger_finite,
        "sweep_science_fields_exact": json_equal.get("sweep", False),
        "gate_science_fields_exact": json_equal.get("gate", False),
        "ledger_bytes_exact": ledger_equal,
    }
    result["checks"] = checks
    result["metadata_checks"] = metadata_checks
    result["finite_checks"] = finite_checks
    result["ledger_validation"] = {
        "reference_error": ref_ledger_error,
        "p0_error": p0_ledger_error,
    }
    passed = all(checks.values())
    result["verdict"] = (
        "PASS_EXACT_DYNAMIC_EQUIVALENCE__P0_ACCEPTED_FOR_FULL_DOUBLE_REPLAY"
        if passed
        else "FAIL_DYNAMIC_EQUIVALENCE__P0_REJECTED"
    )
    result["p0_accepted_as_reference_equivalent"] = passed
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
