"""Small fail-closed primitives used by the independent B4G validator.

This module intentionally does not import the campaign runner, solver, mutation
harness, or their tests.  It only reads byte-bound JSON/NPZ evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np


class DuplicateKeyError(ValueError):
    """Raised when a JSON object contains a duplicate key."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(key)
        result[key] = value
    return result


def _reject_nonfinite_json_numbers(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("NONFINITE_JSON_NUMBER")
    if isinstance(value, dict):
        for item in value.values():
            _reject_nonfinite_json_numbers(item)
    elif isinstance(value, list):
        for item in value:
            _reject_nonfinite_json_numbers(item)


def read_json_strict(path: Path) -> dict[str, Any]:
    payload = Path(path).read_bytes()
    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
        )
        _reject_nonfinite_json_numbers(value)
    except (UnicodeDecodeError, json.JSONDecodeError, DuplicateKeyError, ValueError) as error:
        raise ValueError(f"JSON_STRICT_READ_FAILED:{Path(path).name}:{error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"JSON_ROOT_NOT_OBJECT:{Path(path).name}")
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest().upper()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def is_sha256(value: Any) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 64
        and value == value.upper()
        and all(character in "0123456789ABCDEF" for character in value)
    )


def finite_number(value: Any) -> bool:
    return bool(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value))


def resolve_declared(project_root: Path, phase_root: Path, declared: Any) -> Path:
    path = Path(str(declared))
    if path.is_absolute():
        return path.resolve()
    project_candidate = (project_root / path).resolve()
    if project_candidate.exists():
        return project_candidate
    return (phase_root / path).resolve()


@dataclass
class ValidationReport:
    """Machine-readable result; any failed check makes the report fail closed."""

    mode: str
    checks: int = 0
    failures: list[dict[str, Any]] = field(default_factory=list)
    observations: dict[str, Any] = field(default_factory=dict)

    def require(self, condition: Any, code: str, detail: Any = None) -> bool:
        self.checks += 1
        passed = bool(condition)
        if not passed:
            self.failures.append({"code": code, "detail": detail})
        return passed

    def guard(self, code: str, operation: Any) -> Any:
        self.checks += 1
        try:
            return operation()
        except Exception as error:  # validation must convert all malformed inputs to evidence
            self.failures.append({
                "code": code,
                "detail": {"error_type": type(error).__name__, "error": str(error)},
            })
            return None

    @property
    def passed(self) -> bool:
        return not self.failures

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": "SIM13_V4B4G_READ_ONLY_VALIDATION_REPORT_V1",
            "mode": self.mode,
            "status": "PASS" if self.passed else "DIAGNOSTIC_FAIL_CLOSED",
            "passed": self.passed,
            "final": False,
            "audited": False,
            "validator_pass_claimed": False,
            "campaign_or_scientific_credit": False,
            "check_count": self.checks,
            "failure_count": len(self.failures),
            "failures": self.failures,
            "observations": self.observations,
            "writes_performed": False,
            "solver_runner_mutation_modules_imported": False,
        }


def verify_file_record(
    report: ValidationReport,
    *,
    path: Path,
    expected_bytes: Any,
    expected_sha256: Any,
    code: str,
) -> bool:
    exists = report.require(path.is_file(), f"{code}_MISSING", path.as_posix())
    if not exists:
        return False
    size = path.stat().st_size
    digest = sha256_file(path)
    size_ok = report.require(size == expected_bytes, f"{code}_BYTES", {"expected": expected_bytes, "actual": size})
    sha_ok = report.require(digest == expected_sha256, f"{code}_SHA256", {"expected": expected_sha256, "actual": digest})
    return size_ok and sha_ok


def exact_keys(report: ValidationReport, value: Mapping[str, Any], required: Iterable[str], code: str) -> bool:
    missing = sorted(set(required) - set(value))
    return report.require(not missing, code, {"missing": missing})


def exact_key_set(report: ValidationReport, value: Mapping[str, Any], expected: Iterable[str], code: str) -> bool:
    expected_set = set(expected)
    actual_set = set(value)
    return report.require(
        actual_set == expected_set,
        code,
        {
            "missing": sorted(expected_set - actual_set),
            "extra": sorted(actual_set - expected_set),
        },
    )


def load_npz_strict(report: ValidationReport, path: Path, *, code: str) -> dict[str, np.ndarray] | None:
    if not report.require(path.is_file(), f"{code}_MISSING", path.as_posix()):
        return None
    try:
        with np.load(path, allow_pickle=False) as archive:
            names = list(archive.files)
            if len(names) != len(set(names)):
                report.require(False, f"{code}_DUPLICATE_ARRAY_NAME", names)
                return None
            arrays = {name: np.asarray(archive[name]) for name in names}
    except Exception as error:
        report.require(False, f"{code}_ALLOW_PICKLE_FALSE_READ", str(error))
        return None
    for name, array in arrays.items():
        report.require(array.dtype.kind not in "OUSV", f"{code}_NON_NUMERIC_ARRAY", name)
        report.require(array.dtype.kind != "c", f"{code}_COMPLEX_ARRAY", name)
        if array.dtype.kind == "f":
            report.require(bool(np.all(np.isfinite(array))), f"{code}_NONFINITE_ARRAY", name)
    return arrays


def normalized_numeric_array(value: Any) -> np.ndarray:
    array = np.asarray(value)
    if array.dtype.kind == "b":
        result = np.asarray(array, dtype=np.bool_)
    elif array.dtype.kind in "iu":
        result = np.asarray(array, dtype="<i8")
    elif array.dtype.kind == "f":
        result = np.asarray(array, dtype="<f8")
    else:
        raise ValueError(f"UNSUPPORTED_NUMERIC_ARRAY:{array.dtype}")
    return np.ascontiguousarray(result)


def array_payload_sha256(arrays: Mapping[str, Any]) -> str:
    digest = hashlib.sha256()
    for name in sorted(arrays):
        array = normalized_numeric_array(arrays[name])
        header = canonical_bytes({"name": name, "dtype": array.dtype.str, "shape": list(array.shape)})
        digest.update(len(header).to_bytes(8, "big"))
        digest.update(header)
        digest.update(array.tobytes(order="C"))
    return digest.hexdigest().upper()
