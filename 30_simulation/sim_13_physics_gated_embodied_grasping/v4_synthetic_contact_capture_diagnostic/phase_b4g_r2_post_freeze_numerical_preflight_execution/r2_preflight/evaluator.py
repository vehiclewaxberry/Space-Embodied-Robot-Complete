"""Fail-closed source-level evaluators for the frozen R2 preflight.

No function imports a historical solver or advances a physical state. Inputs
are complete, hash-bound evidence records; numerical routines only recompute
metrics over caller-supplied synthetic arrays.
"""

from __future__ import annotations

from copy import deepcopy
import math
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np

from .metrics import (
    ACQUISITION_CONTRACTION,
    COMMON_PROP_CHANNELS,
    FRESH_ACQ_CHANNELS,
    MIDPOINT_CONTRACTION,
    RK4_CONTRACTION,
    channel_distance,
    channel_sample_count,
    evaluate_channel_triplet,
    evaluate_direct_order_triplet,
    finest_cross_method_limit,
)
from .rehydrator import (
    COMMON_GROUP_BYTES,
    COMMON_GROUP_SHA256,
    DONOR_PAYLOAD_BYTES,
    DONOR_PAYLOAD_SHA256,
    RehydratedFixture,
    RehydrationError,
    collect_mutable_ids,
    fixture_hashes,
    rehydrate_payload,
)
from .schedule import LANES, expand_matrix, fresh_a1_id, generate_schedule
from .strict_json import StrictJSONError, canonical_bytes, canonical_sha256, file_sha256
from .work_energy import (
    G04_PASS_EXPRESSION,
    G04_REQUIRED_FIELDS,
    G04_RULE_ID,
    G06_REQUIRED_FIELDS,
    G06_RULE_ID,
    WorkEnergyError,
    evaluate_g04,
    evaluate_g06,
)


HEX = set("0123456789ABCDEF")
LANE_BY_METHOD_STEP = {(method, step_s): lane_id for lane_id, method, step_s in LANES}
MATRIX_BY_CASE = {row["case_id"]: row for row in expand_matrix()}
DONOR_HASHES = {
    "payload_canonical_bytes": DONOR_PAYLOAD_BYTES,
    "payload_sha256": DONOR_PAYLOAD_SHA256,
    "group_canonical_bytes": COMMON_GROUP_BYTES,
    "group_sha256": COMMON_GROUP_SHA256,
}
COMMAND_DURATIONS_S = {0.005, 0.01, 0.02}
REFERENCE_STEPS_S = [0.00025, 0.000125, 0.0000625]


def _hex64(value: Any) -> bool:
    return type(value) is str and len(value) == 64 and all(char in HEX for char in value)


def _finite_float(value: Any) -> bool:
    return type(value) is float and math.isfinite(value)


def _fail(status: str, **extra: Any) -> dict[str, Any]:
    return {"passed": False, "status": status, **extra}


def _registered_row(case_id: Any) -> dict[str, Any] | None:
    return MATRIX_BY_CASE.get(case_id) if type(case_id) is str else None


def _record_matches_row(record: dict[str, Any], row: dict[str, Any]) -> bool:
    return bool(
        record.get("case_id") == row["case_id"]
        and record.get("lane_id") == row["lane_id"]
        and record.get("method") == row["method"]
        and type(record.get("step_s")) is float
        and record.get("step_s") == row["step_s"]
    )


def _safe_hash(value: Any) -> str | None:
    try:
        return canonical_sha256(value)
    except (StrictJSONError, TypeError, ValueError):
        return None


def _safe_relative_evidence_path(value: Any) -> bool:
    if type(value) is not str or not value or "\\" in value or ":" in value:
        return False
    path = PurePosixPath(value)
    return bool(
        not path.is_absolute()
        and ".." not in path.parts
        and len(path.parts) == 3
        and path.parts[:2] == ("evidence", "cases")
        and path.suffix == ".json"
    )


def project_fresh_acquisition_identity(payload: dict[str, Any]) -> dict[str, Any]:
    """Project exactly the three registered case-identity leaves."""

    try:
        if set(payload) != {"acquisition", "case_id", "event", "lane_id"}:
            raise ValueError("outer keys")
        case_id = payload["case_id"]
        if (
            type(case_id) is not str
            or payload["event"]["run_id"] != case_id
            or payload["acquisition"]["run_id"] != case_id
        ):
            raise ValueError("case binding")
        projected = deepcopy(payload)
        projected["case_id"] = "CASE_IDENTITY_EXCLUDED_V1"
        projected["event"]["run_id"] = "CASE_IDENTITY_EXCLUDED_V1"
        projected["acquisition"]["run_id"] = "CASE_IDENTITY_EXCLUDED_V1"
        encoded = canonical_bytes(projected)
    except (KeyError, TypeError, ValueError, StrictJSONError):
        return {
            "status": "FAIL_IDENTITY_PROJECTION_SCHEMA",
            "canonical_bytes": "NOT_EVALUATED",
            "sha256": "NOT_EVALUATED",
        }
    return {
        "status": "PASS_IDENTITY_PROJECTION",
        "canonical_bytes": len(encoded),
        "sha256": canonical_sha256(projected),
    }


def evaluate_fresh_technical_repeats(
    payloads_by_duration_ms: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    if set(payloads_by_duration_ms) != {5, 10, 20}:
        return _fail("FAIL_FRESH_ACQ_TECHNICAL_REPEAT_MISSING_DURATION")
    try:
        lanes = {payload["lane_id"] for payload in payloads_by_duration_ms.values()}
        if len(lanes) != 1:
            raise ValueError("lane mismatch")
        lane = next(iter(lanes))
        for duration, payload in payloads_by_duration_ms.items():
            expected = fresh_a1_id(lane, 16, duration)
            row = _registered_row(expected)
            if (
                payload["case_id"] != expected
                or row is None
                or row["command_duration_s"] != duration / 1000.0
                or payload["event"]["method"] != row["method"]
                or payload["event"]["step_s"] != row["step_s"]
            ):
                raise ValueError("registered technical repeat binding")
            certificate = canonical_sha256(payload)
            rehydrate_payload(payload, certificate)
    except (KeyError, TypeError, ValueError, RehydrationError, StrictJSONError):
        return _fail("FAIL_FRESH_ACQ_TECHNICAL_REPEAT_REGISTERED_CASE_BINDING")
    projected = {duration: project_fresh_acquisition_identity(payload) for duration, payload in payloads_by_duration_ms.items()}
    passed = bool(
        all(result["status"] == "PASS_IDENTITY_PROJECTION" for result in projected.values())
        and len({result["canonical_bytes"] for result in projected.values()}) == 1
        and len({result["sha256"] for result in projected.values()}) == 1
    )
    return {
        "passed": passed,
        "status": (
            "PASS_FRESH_ACQ_TECHNICAL_REPEAT_IDENTITY"
            if passed
            else "FAIL_FRESH_ACQ_TECHNICAL_REPEAT_IDENTITY"
        ),
        "projected": projected,
        "independent_replicate_credit": False,
    }


def evaluate_fresh_acquisition_triplet(
    acquisition_times_s: tuple[float, float, float],
    channel_histories: dict[str, tuple[Any, Any, Any]],
) -> dict[str, Any]:
    """Low-level Cauchy evaluator; record-level callers bind provenance."""

    if set(channel_histories) != set(FRESH_ACQ_CHANNELS):
        return _fail("EXACT_SIXTEEN_CHANNEL_SET_REQUIRED")
    if (
        type(acquisition_times_s) is not tuple
        or len(acquisition_times_s) != 3
        or any(not _finite_float(value) for value in acquisition_times_s)
    ):
        return _fail("FINITE_ACQUISITION_TIME_TRIPLET_REQUIRED")
    d_cf = abs(acquisition_times_s[0] - acquisition_times_s[1])
    d_fr = abs(acquisition_times_s[1] - acquisition_times_s[2])
    time_pass = d_fr <= 6.25e-5 + 1e-15 and d_fr <= ACQUISITION_CONTRACTION * d_cf + 1e-15
    for name, values in channel_histories.items():
        if type(values) is not tuple or len(values) != 3:
            return _fail(f"FRESH_ACQ_CHANNEL_TRIPLET_REQUIRED:{name}")
        try:
            if any(
                channel_sample_count(name, value, channel_specs=FRESH_ACQ_CHANNELS) != 1
                for value in values
            ):
                return _fail(f"FRESH_ACQ_REQUIRES_ONE_EVENT_SNAPSHOT:{name}")
        except ValueError:
            return _fail(f"FRESH_ACQ_CHANNEL_SHAPE_INVALID:{name}")
    channel_results = {
        name: evaluate_channel_triplet(
            name,
            values[0],
            values[1],
            values[2],
            contraction=ACQUISITION_CONTRACTION,
            channel_specs=FRESH_ACQ_CHANNELS,
        )
        for name, values in channel_histories.items()
    }
    passed = bool(time_pass and all(result["passed"] for result in channel_results.values()))
    return {
        "passed": passed,
        "status": "PASS_FRESH_ACQUISITION_CONVERGENCE" if passed else "FAIL_FRESH_ACQUISITION_CONVERGENCE",
        "time": {"unit": "s", "D_CF": d_cf, "D_FR": d_fr, "passed": time_pass},
        "channels": channel_results,
    }


FRESH_ACQ_OBSERVATION_KEYS = {
    "schema", "case_id", "lane_id", "method", "step_s", "alpha",
    "command_duration_s", "acquisition_time_s", "native_momentum_raw_binding", "channels",
}
NATIVE_MOMENTUM_BINDING_KEYS = {
    "schema", "case_id", "sample_time_s", "total_linear_momentum_kg_m_s",
    "total_angular_momentum_kg_m2_s", "raw_relative_path", "raw_bytes",
    "raw_sha256", "raw_sample_index", "derivation_rule_id",
}
FRESH_ACQ_RECORD_KEYS = {
    "case_id", "lane_id", "method", "step_s",
    "acquisition_certificate_payload", "acquisition_certificate_sha256",
    "observation_payload", "observation_sha256",
}


def derive_fresh_acquisition_channels(
    fixture: RehydratedFixture,
    native_momentum_raw_binding: dict[str, Any],
) -> dict[str, Any]:
    """Derive all 16 channels from typed acquisition and a frozen raw binding.

    Fourteen channels are direct deterministic projections of the complete
    acquisition certificate. Native total P/H require future trajectory raw
    evidence; their exact source path/hash/formula is consumed here, while the
    current source-freeze never claims that the referenced file was executed.
    """

    if not isinstance(native_momentum_raw_binding, dict) or set(native_momentum_raw_binding) != NATIVE_MOMENTUM_BINDING_KEYS:
        raise ValueError("NATIVE_MOMENTUM_EXACT_RAW_BINDING_REQUIRED")
    linear = native_momentum_raw_binding["total_linear_momentum_kg_m_s"]
    angular = native_momentum_raw_binding["total_angular_momentum_kg_m2_s"]
    raw_path = native_momentum_raw_binding["raw_relative_path"]
    if (
        native_momentum_raw_binding["schema"] != "B4G_R2_FRESH_NATIVE_MOMENTUM_RAW_BINDING_V1"
        or native_momentum_raw_binding["case_id"] != fixture.case_id
        or native_momentum_raw_binding["sample_time_s"] != fixture.acquisition.acquisition_time_s
        or not isinstance(linear, list) or len(linear) != 3 or any(not _finite_float(value) for value in linear)
        or not isinstance(angular, list) or len(angular) != 3 or any(not _finite_float(value) for value in angular)
        or type(raw_path) is not str
        or raw_path != f"evidence/cases/{fixture.case_id}.npz"
        or type(native_momentum_raw_binding["raw_bytes"]) is not int
        or native_momentum_raw_binding["raw_bytes"] <= 0
        or not _hex64(native_momentum_raw_binding["raw_sha256"])
        or type(native_momentum_raw_binding["raw_sample_index"]) is not int
        or native_momentum_raw_binding["raw_sample_index"] < 0
        or native_momentum_raw_binding["derivation_rule_id"] != "B4G_R2_NATIVE_P_H_AT_ACQUISITION_EXACT_SAMPLE_V1"
    ):
        raise ValueError("NATIVE_MOMENTUM_RAW_BINDING_INVALID")
    service = fixture.event.service
    target = fixture.event.target
    z_plus = fixture.acquisition.z_plus_reduced
    energy = fixture.acquisition.energy_audit
    metrics = fixture.acquisition.metrics
    if type(energy.get("D_B3_minus_J")) is not float or type(metrics.get("switch_energy_identity_J")) is not float:
        raise ValueError("FRESH_ENERGY_CHANNEL_JSON_FLOAT_REQUIRED")
    return {
        "service_position_m": service.base_position_inertial_m.tolist(),
        "service_quaternion": service.base_quaternion_body_to_inertial_wxyz.tolist(),
        "R_joint_coordinates_rad": service.joint_coordinates_mixed[:6].tolist(),
        "P_joint_coordinates_m": service.joint_coordinates_mixed[6:8].tolist(),
        "service_base_linear_velocity_m_s": z_plus[0:3].tolist(),
        "service_base_angular_velocity_rad_s": z_plus[3:6].tolist(),
        "R_joint_velocity_rad_s": z_plus[6:12].tolist(),
        "P_joint_velocity_m_s": z_plus[12:14].tolist(),
        "target_position_m": target.position_inertial_m.tolist(),
        "target_quaternion": target.quaternion_body_to_inertial_wxyz.tolist(),
        "target_linear_velocity_m_s": z_plus[14:17].tolist(),
        "target_angular_velocity_rad_s": z_plus[17:20].tolist(),
        "linear_momentum_native": list(linear),
        "angular_momentum_native": list(angular),
        "D_B3_minus_J": energy["D_B3_minus_J"],
        "switch_energy_identity_J": metrics["switch_energy_identity_J"],
    }


def verify_fresh_native_momentum_raw(
    binding: dict[str, Any], raw_root: Path
) -> bool:
    """Verify the future raw file without importing or running physics code."""

    try:
        root = raw_root.resolve(strict=True)
        lexical = root / binding["raw_relative_path"]
        if lexical.is_symlink():
            return False
        candidate = lexical.resolve(strict=True)
        candidate.relative_to(root)
        if candidate.stat().st_size != binding["raw_bytes"]:
            return False
        if file_sha256(candidate) != binding["raw_sha256"]:
            return False
        index = binding["raw_sample_index"]
        with np.load(candidate, allow_pickle=False) as raw:
            required = {
                "time_s", "total_linear_momentum_N_s", "total_angular_momentum_N_m_s",
            }
            if not required.issubset(set(raw.files)):
                return False
            time = np.asarray(raw["time_s"])
            linear = np.asarray(raw["total_linear_momentum_N_s"])
            angular = np.asarray(raw["total_angular_momentum_N_m_s"])
            if (
                time.dtype != np.dtype("float64")
                or linear.dtype != np.dtype("float64")
                or angular.dtype != np.dtype("float64")
                or time.ndim != 1
                or time.size == 0
                or linear.shape != (time.size, 3)
                or angular.shape != (time.size, 3)
                or index >= time.size
                or not np.all(np.isfinite(time))
                or not np.all(np.isfinite(linear))
                or not np.all(np.isfinite(angular))
                or np.any(np.diff(time) <= 0.0)
            ):
                return False
            return bool(
                float(time[index]) == binding["sample_time_s"]
                and np.array_equal(linear[index], np.asarray(binding["total_linear_momentum_kg_m_s"], dtype=np.float64))
                and np.array_equal(angular[index], np.asarray(binding["total_angular_momentum_kg_m2_s"], dtype=np.float64))
            )
    except (KeyError, OSError, ValueError, TypeError):
        return False


def _validate_fresh_acquisition_record(record: dict[str, Any]) -> tuple[bool, str]:
    if set(record) != FRESH_ACQ_RECORD_KEYS:
        return False, "FRESH_ACQ_EXACT_RECORD_SCHEMA_REQUIRED"
    row = _registered_row(record["case_id"])
    if (
        row is None
        or not _record_matches_row(record, row)
        or row["execution_family"] != "FRESH"
        or row["alpha"] != 16.0
        or row["command_duration_s"] != 0.01
        or "FRESH_ACQ_OBSERVATION" not in row["roles"]
    ):
        return False, "FRESH_ACQ_REGISTERED_CASE_BINDING_INVALID"
    certificate = record["acquisition_certificate_sha256"]
    if not _hex64(certificate) or _safe_hash(record["acquisition_certificate_payload"]) != certificate:
        return False, "FRESH_ACQ_CERTIFICATE_HASH_INVALID"
    try:
        fixture = rehydrate_payload(record["acquisition_certificate_payload"], certificate)
    except (RehydrationError, StrictJSONError, TypeError, ValueError):
        return False, "FRESH_ACQ_CERTIFICATE_TYPED_ROUNDTRIP_INVALID"
    if (
        fixture.case_id != record["case_id"]
        or fixture.lane_id != record["lane_id"]
        or fixture.event.method != record["method"]
        or fixture.event.step_s != record["step_s"]
    ):
        return False, "FRESH_ACQ_CERTIFICATE_CASE_LANE_METHOD_STEP_INVALID"
    observation = record["observation_payload"]
    try:
        derived_channels = derive_fresh_acquisition_channels(
            fixture, observation.get("native_momentum_raw_binding") if isinstance(observation, dict) else {},
        )
    except (ValueError, KeyError, TypeError):
        return False, "FRESH_ACQ_CHANNEL_DERIVATION_OR_RAW_BINDING_INVALID"
    if (
        not isinstance(observation, dict)
        or set(observation) != FRESH_ACQ_OBSERVATION_KEYS
        or record["observation_sha256"] != _safe_hash(observation)
        or not _hex64(record["observation_sha256"])
        or observation["schema"] != "B4G_R2_FRESH_ACQUISITION_OBSERVATION_V1"
        or any(observation[key] != record[key] for key in ("case_id", "lane_id", "method", "step_s"))
        or observation["alpha"] != 16.0
        or observation["command_duration_s"] != 0.01
        or not _finite_float(observation["acquisition_time_s"])
        or observation["acquisition_time_s"] != fixture.acquisition.acquisition_time_s
        or not isinstance(observation["channels"], dict)
        or set(observation["channels"]) != set(FRESH_ACQ_CHANNELS)
        or observation["channels"] != derived_channels
    ):
        return False, "FRESH_ACQ_HASH_BOUND_OBSERVATION_INVALID"
    return True, "PASS"


def evaluate_fresh_acquisition_records(
    records: list[dict[str, Any]], *, raw_root: Path | None = None
) -> dict[str, Any]:
    if type(records) is not list or len(records) != 3:
        return _fail("FRESH_ACQ_EXACT_THREE_RECORDS_REQUIRED")
    for record in records:
        if not isinstance(record, dict):
            return _fail("FRESH_ACQ_RECORD_OBJECT_REQUIRED")
        valid, status = _validate_fresh_acquisition_record(record)
        if not valid:
            return _fail(status)
    ordered = sorted(records, key=lambda record: record["step_s"], reverse=True)
    method = ordered[0]["method"]
    expected_lanes = [LANE_BY_METHOD_STEP.get((method, step)) for step in REFERENCE_STEPS_S]
    expected_cases = [fresh_a1_id(lane, 16, 10) for lane in expected_lanes]
    if (
        method not in {"rk4", "midpoint"}
        or [record["step_s"] for record in ordered] != REFERENCE_STEPS_S
        or [record["lane_id"] for record in ordered] != expected_lanes
        or [record["case_id"] for record in ordered] != expected_cases
        or len({record["acquisition_certificate_sha256"] for record in ordered}) != 3
        or len({record["observation_sha256"] for record in ordered}) != 3
    ):
        return _fail("FRESH_ACQ_2_TO_1_LADDER_OR_PROVENANCE_INVALID")
    result = evaluate_fresh_acquisition_triplet(
        tuple(record["observation_payload"]["acquisition_time_s"] for record in ordered),
        {
            name: tuple(record["observation_payload"]["channels"][name] for record in ordered)
            for name in FRESH_ACQ_CHANNELS
        },
    )
    metric_pass = result["passed"]
    raw_verified = bool(
        raw_root is not None
        and all(
            verify_fresh_native_momentum_raw(
                record["observation_payload"]["native_momentum_raw_binding"], raw_root
            )
            for record in ordered
        )
    )
    result["source_only_metric_predicate_pass"] = metric_pass
    result["native_momentum_raw_verified"] = raw_verified
    result["record_binding_pass"] = bool(metric_pass and raw_verified)
    result["passed"] = bool(metric_pass and raw_verified)
    if metric_pass and not raw_verified:
        result["status"] = "HOLD_FRESH_ACQ_NATIVE_MOMENTUM_RAW_NOT_VERIFIED_NO_EXECUTION"
    result["method"] = method
    result["case_ids"] = [record["case_id"] for record in ordered]
    return result


def evaluate_common_propagation_triplet(
    method: str,
    channel_histories: dict[str, tuple[Any, Any, Any]],
    *,
    time_grids_s: tuple[list[float], list[float], list[float]],
    command_duration_s: float,
) -> dict[str, Any]:
    """Low-level common-state Cauchy evaluator over an exact shared grid."""

    if set(channel_histories) != set(COMMON_PROP_CHANNELS) or method not in {"midpoint", "rk4"}:
        return _fail("COMMON_PROP_SCHEMA_INVALID")
    if (
        type(time_grids_s) is not tuple
        or len(time_grids_s) != 3
        or any(
            type(grid) is not list or not grid or any(not _finite_float(value) for value in grid)
            for grid in time_grids_s
        )
        or not _finite_float(command_duration_s)
        or command_duration_s not in COMMAND_DURATIONS_S
        or not (time_grids_s[0] == time_grids_s[1] == time_grids_s[2])
        or time_grids_s[0][0] != 0.0
        or time_grids_s[0][-1] != command_duration_s
        or any(right <= left for left, right in zip(time_grids_s[0], time_grids_s[0][1:]))
    ):
        return _fail("COMMON_PROP_EXACT_ACQUISITION_RELATIVE_GRID_INVALID")
    for name, values in channel_histories.items():
        if type(values) is not tuple or len(values) != 3:
            return _fail(f"COMMON_PROP_CHANNEL_TRIPLET_REQUIRED:{name}")
        try:
            counts = [
                channel_sample_count(name, value, channel_specs=COMMON_PROP_CHANNELS)
                for value in values
            ]
        except ValueError:
            return _fail(f"COMMON_PROP_CHANNEL_SHAPE_INVALID:{name}")
        if counts != [len(grid) for grid in time_grids_s]:
            return _fail(f"COMMON_PROP_CHANNEL_GRID_LENGTH_MISMATCH:{name}")
    contraction = MIDPOINT_CONTRACTION if method == "midpoint" else RK4_CONTRACTION
    channel_results = {
        name: evaluate_channel_triplet(
            name, values[0], values[1], values[2], contraction=contraction,
            channel_specs=COMMON_PROP_CHANNELS,
        )
        for name, values in channel_histories.items()
    }
    passed = all(result["passed"] for result in channel_results.values())
    return {
        "passed": passed,
        "status": "PASS_COMMON_PROP_CONVERGENCE" if passed else "FAIL_COMMON_PROP_CONVERGENCE",
        "method": method,
        "command_duration_s": command_duration_s,
        "contraction": contraction,
        "channels": channel_results,
        "g12_credit": False,
        "selector_input": False,
    }


COMMON_OBSERVATION_KEYS = {
    "schema", "case_id", "lane_id", "method", "step_s",
    "command_duration_s", "time_grid_s", "raw_binding", "channels",
}
COMMON_RAW_BINDING_KEYS = {
    "schema", "case_id", "raw_relative_path", "raw_bytes", "raw_sha256",
    "derivation_rule_id",
}
COMMON_RECORD_KEYS = {
    "case_id", "lane_id", "method", "step_s", "command_duration_s",
    "donor_certificate_sha256", "donor_group_sha256", "donor_hashes_before",
    "donor_hashes_after", "fixture", "observation_payload", "observation_sha256",
    "evidence_path", "g12_credit", "selector_input", "fresh_acquisition_credit",
    "shared_removal_credit",
}


def _validate_common_record(record: dict[str, Any]) -> tuple[bool, str]:
    if set(record) != COMMON_RECORD_KEYS:
        return False, "COMMON_PROP_EXACT_RECORD_SCHEMA_REQUIRED"
    row = _registered_row(record["case_id"])
    if (
        row is None
        or not _record_matches_row(record, row)
        or row["execution_family"] != "COMMON_PROP"
        or row["command_duration_s"] != record["command_duration_s"]
        or record["command_duration_s"] not in COMMAND_DURATIONS_S
        or record["donor_certificate_sha256"] != DONOR_PAYLOAD_SHA256
        or record["donor_group_sha256"] != COMMON_GROUP_SHA256
        or record["g12_credit"] is not False
        or record["selector_input"] is not False
        or record["fresh_acquisition_credit"] is not False
        or record["shared_removal_credit"] is not False
        or not _safe_relative_evidence_path(record["evidence_path"])
        or PurePosixPath(record["evidence_path"]).stem != record["case_id"]
    ):
        return False, "COMMON_PROP_REGISTERED_CASE_OR_CREDIT_INVALID"
    fixture = record["fixture"]
    if not isinstance(fixture, RehydratedFixture):
        return False, "COMMON_PROP_TYPED_FIXTURE_REQUIRED"
    try:
        current_hashes = fixture_hashes(fixture)
    except (RehydrationError, StrictJSONError, TypeError, ValueError):
        return False, "COMMON_PROP_FIXTURE_HASH_RECOMPUTATION_FAILED"
    if (
        current_hashes != DONOR_HASHES
        or record["donor_hashes_before"] != DONOR_HASHES
        or record["donor_hashes_after"] != DONOR_HASHES
    ):
        return False, "COMMON_PROP_DONOR_BEFORE_AFTER_OR_CURRENT_HASH_DRIFT"
    observation = record["observation_payload"]
    raw_binding = observation.get("raw_binding") if isinstance(observation, dict) else None
    if (
        not isinstance(observation, dict)
        or set(observation) != COMMON_OBSERVATION_KEYS
        or not _hex64(record["observation_sha256"])
        or _safe_hash(observation) != record["observation_sha256"]
        or observation["schema"] != "B4G_R2_COMMON_PROPAGATION_OBSERVATION_V1"
        or any(
            observation[key] != record[key]
            for key in ("case_id", "lane_id", "method", "step_s", "command_duration_s")
        )
        or not isinstance(observation["channels"], dict)
        or set(observation["channels"]) != set(COMMON_PROP_CHANNELS)
        or not isinstance(raw_binding, dict)
        or set(raw_binding) != COMMON_RAW_BINDING_KEYS
        or raw_binding["schema"] != "B4G_R2_COMMON_PROPAGATION_RAW_BINDING_V1"
        or raw_binding["case_id"] != record["case_id"]
        or raw_binding["raw_relative_path"] != f"evidence/cases/{record['case_id']}.npz"
        or type(raw_binding["raw_bytes"]) is not int
        or raw_binding["raw_bytes"] <= 0
        or not _hex64(raw_binding["raw_sha256"])
        or raw_binding["derivation_rule_id"] != "B4G_R2_COMMON_16_CHANNEL_EXACT_RAW_ARRAY_MAP_V1"
    ):
        return False, "COMMON_PROP_HASH_BOUND_OBSERVATION_INVALID"
    return True, "PASS"


def verify_common_observation_raw(record: dict[str, Any], raw_root: Path) -> bool:
    """Recompute all common-grid channels from one hash-bound future raw file."""

    try:
        observation = record["observation_payload"]
        binding = observation["raw_binding"]
        root = raw_root.resolve(strict=True)
        lexical = root / binding["raw_relative_path"]
        if lexical.is_symlink():
            return False
        candidate = lexical.resolve(strict=True)
        candidate.relative_to(root)
        if candidate.stat().st_size != binding["raw_bytes"] or file_sha256(candidate) != binding["raw_sha256"]:
            return False
        with np.load(candidate, allow_pickle=False) as raw:
            required = {
                "time_s", "service_state_29", "target_state_13",
                "total_linear_momentum_N_s", "total_angular_momentum_N_m_s",
                "total_kinetic_energy_J", "energy_minus_work_residual_J",
            }
            if not required.issubset(set(raw.files)):
                return False
            arrays = {name: np.asarray(raw[name]) for name in required}
        time = arrays["time_s"]
        n = time.size
        if (
            any(array.dtype != np.dtype("float64") or not np.all(np.isfinite(array)) for array in arrays.values())
            or time.ndim != 1 or n == 0
            or arrays["service_state_29"].shape != (n, 29)
            or arrays["target_state_13"].shape != (n, 13)
            or arrays["total_linear_momentum_N_s"].shape != (n, 3)
            or arrays["total_angular_momentum_N_m_s"].shape != (n, 3)
            or arrays["total_kinetic_energy_J"].shape != (n,)
            or arrays["energy_minus_work_residual_J"].shape != (n,)
            or time.tolist() != observation["time_grid_s"]
        ):
            return False
        service = arrays["service_state_29"]
        target = arrays["target_state_13"]
        derived = {
            "service_position_m": service[:, 0:3].tolist(),
            "service_quaternion_body_to_inertial_wxyz": service[:, 3:7].tolist(),
            "R_joint_coordinates_rad": service[:, 7:13].tolist(),
            "P_joint_coordinates_m": service[:, 13:15].tolist(),
            "service_base_linear_velocity_m_s": service[:, 15:18].tolist(),
            "service_base_angular_velocity_rad_s": service[:, 18:21].tolist(),
            "R_joint_velocity_rad_s": service[:, 21:27].tolist(),
            "P_joint_velocity_m_s": service[:, 27:29].tolist(),
            "target_position_m": target[:, 0:3].tolist(),
            "target_quaternion_body_to_inertial_wxyz": target[:, 3:7].tolist(),
            "target_linear_velocity_m_s": target[:, 7:10].tolist(),
            "target_angular_velocity_rad_s": target[:, 10:13].tolist(),
            "total_linear_momentum_kg_m_s": arrays["total_linear_momentum_N_s"].tolist(),
            "total_angular_momentum_kg_m2_s": arrays["total_angular_momentum_N_m_s"].tolist(),
            "total_kinetic_energy_J": arrays["total_kinetic_energy_J"].tolist(),
            "energy_minus_work_residual_J": arrays["energy_minus_work_residual_J"].tolist(),
        }
        return derived == observation["channels"]
    except (KeyError, OSError, ValueError, TypeError):
        return False


def evaluate_common_propagation_records(
    records: list[dict[str, Any]], *, raw_root: Path | None = None
) -> dict[str, Any]:
    if type(records) is not list or len(records) != 3:
        return _fail("COMMON_PROP_EXACT_THREE_RECORDS_REQUIRED")
    fixture_id_sets: list[set[int]] = []
    for record in records:
        if not isinstance(record, dict):
            return _fail("COMMON_PROP_RECORD_OBJECT_REQUIRED")
        valid, status = _validate_common_record(record)
        if not valid:
            return _fail(status)
        fixture_id_sets.append(collect_mutable_ids(record["fixture"]))
    ordered = sorted(records, key=lambda record: record["step_s"], reverse=True)
    method = ordered[0]["method"]
    duration_s = ordered[0]["command_duration_s"]
    duration_ms = int(round(duration_s * 1000.0))
    expected_lanes = [LANE_BY_METHOD_STEP.get((method, step)) for step in REFERENCE_STEPS_S]
    expected_cases = [f"COMMON_PROP__{lane}__A_16__T_MS_{duration_ms}" for lane in expected_lanes]
    pairwise_disjoint = all(
        not (fixture_id_sets[i] & fixture_id_sets[j])
        for i in range(3) for j in range(i + 1, 3)
    )
    if (
        method not in {"rk4", "midpoint"}
        or [record["step_s"] for record in ordered] != REFERENCE_STEPS_S
        or [record["lane_id"] for record in ordered] != expected_lanes
        or [record["case_id"] for record in ordered] != expected_cases
        or any(record["method"] != method or record["command_duration_s"] != duration_s for record in ordered)
        or not pairwise_disjoint
        or len({record["evidence_path"] for record in ordered}) != 3
        or len({record["observation_sha256"] for record in ordered}) != 3
    ):
        return _fail("COMMON_PROP_LADDER_DONOR_OR_IDENTITY_INVALID")
    result = evaluate_common_propagation_triplet(
        method,
        {
            name: tuple(record["observation_payload"]["channels"][name] for record in ordered)
            for name in COMMON_PROP_CHANNELS
        },
        time_grids_s=tuple(record["observation_payload"]["time_grid_s"] for record in ordered),
        command_duration_s=duration_s,
    )
    metric_pass = result["passed"]
    raw_verified = bool(
        raw_root is not None
        and all(verify_common_observation_raw(record, raw_root) for record in ordered)
    )
    result["source_only_metric_predicate_pass"] = metric_pass
    result["raw_channel_payloads_verified"] = raw_verified
    result["record_binding_pass"] = bool(metric_pass and raw_verified)
    result["passed"] = bool(metric_pass and raw_verified)
    if metric_pass and not raw_verified:
        result["status"] = "HOLD_COMMON_PROP_RAW_CHANNELS_NOT_VERIFIED_NO_EXECUTION"
    result["case_ids"] = [record["case_id"] for record in ordered]
    return result


def validate_common_registry_structure(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate all 18 common records without granting numerical credit."""

    expected_order = [case_id for case_id in generate_schedule() if case_id.startswith("COMMON_PROP__")]
    if type(records) is not list or len(records) != 18:
        return _fail("COMMON_PROP_EXACT_EIGHTEEN_RECORDS_REQUIRED")
    if [record.get("case_id") for record in records if isinstance(record, dict)] != expected_order:
        return _fail("COMMON_PROP_BLOCKED_ORDER_MISMATCH")
    mutable_sets: list[set[int]] = []
    for record in records:
        if not isinstance(record, dict):
            return _fail("COMMON_PROP_RECORD_OBJECT_REQUIRED")
        valid, status = _validate_common_record(record)
        if not valid:
            return _fail(status)
        mutable_sets.append(collect_mutable_ids(record["fixture"]))
    if any(
        mutable_sets[i] & mutable_sets[j]
        for i in range(len(mutable_sets)) for j in range(i + 1, len(mutable_sets))
    ):
        return _fail("COMMON_PROP_MUTABLE_IDENTITY_REUSED_ACROSS_EIGHTEEN_CASES")
    if len({record["evidence_path"] for record in records}) != 18:
        return _fail("COMMON_PROP_EVIDENCE_PATH_REUSE")
    return {
        "passed": True,
        "status": "PASS_COMMON_PROP_EIGHTEEN_CASE_REGISTRY_STRUCTURE_ONLY",
        "record_count": 18,
        "all_mutable_id_sets_pairwise_disjoint": True,
        "g12_credit": False,
        "selector_input": False,
        "numerical_execution": False,
        "scientific_gate_pass": False,
    }


def validate_common_propagation_campaign(
    records: list[dict[str, Any]], *, raw_root: Path | None = None
) -> dict[str, Any]:
    """Validate all 18 common cases, including campaign-wide object isolation."""

    structural = validate_common_registry_structure(records)
    if structural["passed"] is not True:
        return structural
    triplets: dict[str, dict[str, Any]] = {}
    for method in ("rk4", "midpoint"):
        for duration_s in (0.005, 0.01, 0.02):
            group = [
                record for record in records
                if record["method"] == method and record["command_duration_s"] == duration_s
            ]
            key = f"{method}__{int(duration_s * 1000)}ms"
            triplets[key] = evaluate_common_propagation_records(group, raw_root=raw_root)
    passed = all(result["passed"] for result in triplets.values())
    all_hold = all(str(result.get("status", "")).startswith("HOLD_") for result in triplets.values())
    status = (
        "PASS_COMMON_PROP_EIGHTEEN_CASE_CAMPAIGN_STRUCTURE"
        if passed
        else "HOLD_COMMON_PROP_EIGHTEEN_CASE_CAMPAIGN_RAW_NOT_VERIFIED_NO_EXECUTION"
        if all_hold
        else "FAIL_COMMON_PROP_TRIPLET"
    )
    return {
        "passed": passed,
        "status": status,
        "source_only_registry_structure_pass": structural["passed"] is True,
        "record_count": 18,
        "all_mutable_id_sets_pairwise_disjoint": True,
        "registry_structure": structural,
        "triplets": triplets,
        "g12_credit": False,
        "selector_input": False,
    }


REQUIRED_ALPHA16_GATE_IDS = {
    "B4F-G03-P-ONLY-INTERNAL-GENERALIZED-FORCE",
    "B4F-G04-ACTUATOR-WORK-LEDGER",
    "B4F-G05-P-H-CONSERVATION",
    "B4F-G06-ENERGY-MINUS-WORK-IDENTITY",
    "B4F-G07-CONTACT-CONSTRAINT-MUTUAL-EXCLUSION",
    "B4F-G08-COMMAND-ZERO-BEFORE-REMOVAL",
    "B4F-G09-CONTINUOUS-BILATERAL-CLEARANCE",
    "B4F-G10-EXACT-ZERO-JUMP-REMOVAL",
    "B4F-G11-INDEPENDENT-POST-RELEASE-5MS",
    "B4F-G16-SYNTHETIC-GEOMETRY-DOMAIN",
}
CLEARANCE_CERTIFICATE_KEYS = {
    "schema", "case_id", "lane_id", "method", "step_s", "alpha",
    "command_duration_s", "fresh_b3_reconstruction_sha256", "outcome",
    "integrity_pass", "finite_bilateral_removal_event", "post_release_passed",
    "acquisition_time_s", "removal_time_s", "signed_work_terminal_J", "evidence_path",
}
FRESH_CERTIFICATE_RECORD_KEYS = {
    "case_id", "lane_id", "method", "step_s", "alpha", "command_duration_s",
    "acquisition_certificate_payload", "acquisition_certificate_sha256",
    "clearance_certificate_payload", "clearance_certificate_sha256", "evidence_path",
}


def _validate_fresh_certificate_record(
    record: dict[str, Any], *, require_reference: bool
) -> tuple[bool, str, dict[str, Any] | None]:
    if not FRESH_CERTIFICATE_RECORD_KEYS.issubset(record):
        return False, "FRESH_CERTIFICATE_RECORD_FIELDS_MISSING", None
    row = _registered_row(record["case_id"])
    if (
        row is None
        or not _record_matches_row(record, row)
        or row["execution_family"] != "FRESH"
        or row["arm"] != "A1"
        or record["alpha"] != row["alpha"]
        or record["command_duration_s"] != row["command_duration_s"]
        or record["command_duration_s"] not in COMMAND_DURATIONS_S
        or (require_reference and "G12_FRESH_REFERENCE" not in row["roles"])
        or (require_reference and record["step_s"] != 0.0000625)
        or not _safe_relative_evidence_path(record["evidence_path"])
        or PurePosixPath(record["evidence_path"]).stem != record["case_id"]
    ):
        return False, "FRESH_CERTIFICATE_REGISTERED_CASE_BINDING_INVALID", None
    acq_hash = record["acquisition_certificate_sha256"]
    if not _hex64(acq_hash) or _safe_hash(record["acquisition_certificate_payload"]) != acq_hash:
        return False, "FRESH_ACQUISITION_CERTIFICATE_HASH_INVALID", None
    try:
        fixture = rehydrate_payload(record["acquisition_certificate_payload"], acq_hash)
    except (RehydrationError, StrictJSONError, TypeError, ValueError):
        return False, "FRESH_ACQUISITION_CERTIFICATE_ROUNDTRIP_INVALID", None
    if (
        fixture.case_id != record["case_id"]
        or fixture.lane_id != record["lane_id"]
        or fixture.event.method != record["method"]
        or fixture.event.step_s != record["step_s"]
    ):
        return False, "FRESH_ACQUISITION_CERTIFICATE_METADATA_INVALID", None
    clearance = record["clearance_certificate_payload"]
    clearance_hash = record["clearance_certificate_sha256"]
    if (
        not isinstance(clearance, dict)
        or set(clearance) != CLEARANCE_CERTIFICATE_KEYS
        or not _hex64(clearance_hash)
        or _safe_hash(clearance) != clearance_hash
        or clearance["schema"] != "B4G_R2_FRESH_CLEARANCE_CERTIFICATE_V1"
        or any(
            clearance[key] != record[key]
            for key in ("case_id", "lane_id", "method", "step_s", "alpha", "command_duration_s", "evidence_path")
        )
        or clearance["fresh_b3_reconstruction_sha256"] != acq_hash
        or type(clearance["outcome"]) is not str
        or not clearance["outcome"]
        or type(clearance["integrity_pass"]) is not bool
        or type(clearance["finite_bilateral_removal_event"]) is not bool
        or type(clearance["post_release_passed"]) is not bool
        or not _finite_float(clearance["acquisition_time_s"])
        or clearance["acquisition_time_s"] != fixture.acquisition.acquisition_time_s
        or not _finite_float(clearance["removal_time_s"])
        or not _finite_float(clearance["signed_work_terminal_J"])
    ):
        return False, "FRESH_CLEARANCE_CERTIFICATE_INVALID", None
    return True, "PASS", clearance


FRESH_ALPHA16_RECORD_KEYS = FRESH_CERTIFICATE_RECORD_KEYS | {
    "gate_evidence_payload", "gate_evidence_sha256", "g04_inputs", "g06_inputs",
}
GATE_EVIDENCE_KEYS = {
    "schema", "case_id", "evidence_path", "gate_predicates",
    "g04_inputs_sha256", "g06_inputs_sha256", "clearance_certificate_sha256",
}
G04_INPUT_KEYS = {
    "time_s", "command_Q_14", "service_state_29", "sample_power_reported_W",
    "stage_command_Q_14", "stage_service_state_29", "stage_power_reported_W",
    "W_act_J", "finite_removal_present", "post_W_act_J",
    "post_actuator_work_reset_on_removal", "post_generalized_force_Q_14",
}
G06_INPUT_KEYS = {"total_kinetic_energy_J", "signed_W_act_J", "stage_evidence_payload"}


def _evaluate_bound_work_records(record: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(record["g04_inputs"], dict) or set(record["g04_inputs"]) != G04_INPUT_KEYS:
        raise WorkEnergyError("G04_EXACT_RAW_INPUT_SCHEMA_REQUIRED")
    if not isinstance(record["g06_inputs"], dict) or set(record["g06_inputs"]) != G06_INPUT_KEYS:
        raise WorkEnergyError("G06_EXACT_RAW_INPUT_SCHEMA_REQUIRED")
    g04 = evaluate_g04(**record["g04_inputs"])
    g06 = evaluate_g06(**record["g06_inputs"])
    stage = record["g06_inputs"]["stage_evidence_payload"]
    if (
        stage["method"] != record["method"]
        or stage["step_s"] != record["step_s"]
        or stage["saved_time_s"] != list(record["g04_inputs"]["time_s"])
        or stage["saved_W_act_J"] != list(record["g04_inputs"]["W_act_J"])
        or stage["stage_command_Q_14"] != list(record["g04_inputs"]["stage_command_Q_14"])
        or stage["stage_service_state_29"] != list(record["g04_inputs"]["stage_service_state_29"])
    ):
        raise WorkEnergyError("G04_G06_STAGE_EVIDENCE_NOT_IDENTICAL")
    if tuple(g04) != G04_REQUIRED_FIELDS or tuple(g06) != G06_REQUIRED_FIELDS:
        raise WorkEnergyError("G04_OR_G06_REPORT_SCHEMA_DRIFT")
    if g06["rule_id"] != G06_RULE_ID:
        raise WorkEnergyError("G06_RULE_ID_DRIFT")
    return g04, g06


def evaluate_fresh_alpha16_three_step(records: list[dict[str, Any]]) -> dict[str, Any]:
    if type(records) is not list or len(records) != 3:
        return _fail("FRESH_ALPHA16_EXACT_THREE_RECORDS_REQUIRED")
    evaluated: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    for record in records:
        if not isinstance(record, dict) or set(record) != FRESH_ALPHA16_RECORD_KEYS:
            return _fail("FRESH_ALPHA16_EXACT_THREE_RECORD_SCHEMA_REQUIRED")
        valid, status, clearance = _validate_fresh_certificate_record(record, require_reference=False)
        if not valid or clearance is None:
            return _fail(status)
        gate_evidence = record["gate_evidence_payload"]
        if (
            type(record["alpha"]) is not float
            or record["alpha"] != 16.0
            or not isinstance(gate_evidence, dict)
            or set(gate_evidence) != GATE_EVIDENCE_KEYS
            or not _hex64(record["gate_evidence_sha256"])
            or _safe_hash(gate_evidence) != record["gate_evidence_sha256"]
            or gate_evidence["schema"] != "B4G_R2_FRESH_ALPHA16_GATE_EVIDENCE_V1"
            or gate_evidence["case_id"] != record["case_id"]
            or gate_evidence["evidence_path"] != record["evidence_path"]
            or gate_evidence["clearance_certificate_sha256"] != record["clearance_certificate_sha256"]
            or gate_evidence["g04_inputs_sha256"] != _safe_hash(record["g04_inputs"])
            or gate_evidence["g06_inputs_sha256"] != _safe_hash(record["g06_inputs"])
            or not isinstance(gate_evidence["gate_predicates"], dict)
            or set(gate_evidence["gate_predicates"]) != REQUIRED_ALPHA16_GATE_IDS
            or any(value is not True for value in gate_evidence["gate_predicates"].values())
        ):
            return _fail("FRESH_ALPHA16_GATE_SET_OR_EXACT_BOOL_INVALID")
        try:
            g04, g06 = _evaluate_bound_work_records(record)
        except (WorkEnergyError, StrictJSONError, TypeError, ValueError, KeyError):
            return _fail("FRESH_ALPHA16_G04_G06_RAW_RECOMPUTATION_FAILED")
        evaluated.append((clearance, g04, g06))
    combined = sorted(zip(records, evaluated), key=lambda pair: pair[0]["step_s"], reverse=True)
    ordered = [pair[0] for pair in combined]
    results = [pair[1] for pair in combined]
    method = ordered[0]["method"]
    duration_s = ordered[0]["command_duration_s"]
    duration_ms = int(round(duration_s * 1000.0))
    expected_lanes = [LANE_BY_METHOD_STEP.get((method, step)) for step in REFERENCE_STEPS_S]
    expected_cases = [fresh_a1_id(lane, 16, duration_ms) for lane in expected_lanes]
    clearances = [result[0] for result in results]
    g04_reports = [result[1] for result in results]
    g06_reports = [result[2] for result in results]
    if (
        method not in {"rk4", "midpoint"}
        or [record["step_s"] for record in ordered] != REFERENCE_STEPS_S
        or [record["lane_id"] for record in ordered] != expected_lanes
        or [record["case_id"] for record in ordered] != expected_cases
        or any(record["method"] != method or record["command_duration_s"] != duration_s for record in ordered)
        or len({clearance["outcome"] for clearance in clearances}) != 1
        or any(clearance["integrity_pass"] is not True for clearance in clearances)
        or any(clearance["finite_bilateral_removal_event"] is not True for clearance in clearances)
        or any(clearance["post_release_passed"] is not True for clearance in clearances)
        or any(g04["scientific_predicate"] is not True or g04["cumulative_max_abs_error_J"] > 1e-7 for g04 in g04_reports)
        or any(g06["scientific_predicate"] is not True or g06["active_max_abs_residual_J"] > 1e-7 for g06 in g06_reports)
        or any(clearance["signed_work_terminal_J"] != g04["active_terminal_W_act_J"] for clearance, g04 in zip(clearances, g04_reports))
        or len({record["acquisition_certificate_sha256"] for record in ordered}) != 3
        or len({record["clearance_certificate_sha256"] for record in ordered}) != 3
        or len({record["evidence_path"] for record in ordered}) != 3
    ):
        return _fail("FRESH_ALPHA16_BINDING_PARITY_GATE_OR_FINITE_EVENT_INVALID")
    removal = [clearance["removal_time_s"] for clearance in clearances]
    work = [clearance["signed_work_terminal_J"] for clearance in clearances]
    removal_cf, removal_fr = abs(removal[0] - removal[1]), abs(removal[1] - removal[2])
    work_cf, work_fr = abs(work[0] - work[1]), abs(work[1] - work[2])
    work_tolerance = max(1e-10, 0.001 * max(abs(work[1]), abs(work[2])))
    removal_pass = removal_fr <= 0.00025 and removal_fr <= 0.60 * removal_cf + 1e-15
    work_pass = work_fr <= work_tolerance and work_fr <= 0.60 * work_cf + 1e-15
    g04_order = evaluate_direct_order_triplet(
        [report["cumulative_max_abs_error_J"] for report in g04_reports],
        floor_J=2e-12, p_min=1.8, floor_scope="FINE_AND_REFERENCE",
    )
    g06_order = evaluate_direct_order_triplet(
        [report["active_max_abs_residual_J"] for report in g06_reports],
        floor_J=1e-10,
        p_min=1.8 if method == "midpoint" else 3.0,
        floor_scope="FINE_AND_REFERENCE" if method == "midpoint" else "ALL_THREE",
    )
    candidate_pass = bool(removal_pass and work_pass and g04_order["passed"] and g06_order["passed"])
    return {
        "passed": False,
        "status": (
            "HOLD_FRESH_ALPHA16_FUTURE_TRAJECTORY_RAW_NOT_EXECUTED"
            if candidate_pass else "FAIL_FRESH_ALPHA16_CONVERGENCE_OR_ORDER"
        ),
        "source_only_candidate_predicate_pass": candidate_pass,
        "r2_runtime_trajectory_evaluated": False,
        "method": method,
        "command_duration_s": duration_s,
        "case_ids": [record["case_id"] for record in ordered],
        "removal_time": {"unit": "s", "D_CF": removal_cf, "D_FR": removal_fr, "passed": removal_pass},
        "signed_work": {"unit": "J", "D_CF": work_cf, "D_FR": work_fr, "absolute_tolerance_J": work_tolerance, "passed": work_pass},
        "g04_order": g04_order,
        "g06_order": g06_order,
        "g04_reports": g04_reports,
        "g06_reports": g06_reports,
    }


def evaluate_finest_cross_method(
    channel: str,
    midpoint_records: list[dict[str, Any]],
    rk4_records: list[dict[str, Any]],
    *,
    raw_root: Path | None = None,
) -> dict[str, Any]:
    """Cross-method check bound to two internally evaluated common triplets."""

    if channel not in COMMON_PROP_CHANNELS:
        return _fail("UNREGISTERED_CHANNEL")
    midpoint = evaluate_common_propagation_records(midpoint_records, raw_root=raw_root)
    rk4 = evaluate_common_propagation_records(rk4_records, raw_root=raw_root)
    if (
        midpoint.get("passed") is not True
        or rk4.get("passed") is not True
        or midpoint.get("method") != "midpoint"
        or rk4.get("method") != "rk4"
        or midpoint.get("command_duration_s") != rk4.get("command_duration_s")
    ):
        return _fail("VERIFIED_COMMON_TRIPLETS_REQUIRED")
    midpoint_ordered = sorted(midpoint_records, key=lambda record: record["step_s"], reverse=True)
    rk4_ordered = sorted(rk4_records, key=lambda record: record["step_s"], reverse=True)
    midpoint_fine = midpoint_ordered[-1]["observation_payload"]["channels"][channel]
    rk4_fine = rk4_ordered[-1]["observation_payload"]["channels"][channel]
    distance = channel_distance(channel, midpoint_fine, rk4_fine, channel_specs=COMMON_PROP_CHANNELS)
    d_fr_midpoint = midpoint["channels"][channel]["D_FR"]
    d_fr_rk4 = rk4["channels"][channel]["D_FR"]
    limit = finest_cross_method_limit(d_fr_midpoint, d_fr_rk4, COMMON_PROP_CHANNELS[channel]["floor"])
    return {
        "passed": distance <= limit,
        "status": "PASS_FINEST_CROSS_METHOD" if distance <= limit else "FAIL_FINEST_CROSS_METHOD",
        "channel": channel,
        "unit": COMMON_PROP_CHANNELS[channel]["unit"],
        "distance": distance,
        "limit": limit,
    }


G12_RECORD_KEYS = FRESH_CERTIFICATE_RECORD_KEYS


def evaluate_g12_pair(rk4: dict[str, Any], midpoint: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one registered finest-lane pair from fresh hash-bound evidence."""

    base = {
        "structurally_valid": False,
        "evaluation_status": "FAIL_G12_RECORD_SCHEMA",
        "scientific_predicate": False,
        "eligible": False,
    }
    if (
        not isinstance(rk4, dict) or not isinstance(midpoint, dict)
        or set(rk4) != G12_RECORD_KEYS or set(midpoint) != G12_RECORD_KEYS
    ):
        return base
    ok_rk4, status_rk4, clearance_rk4 = _validate_fresh_certificate_record(rk4, require_reference=True)
    ok_mid, status_mid, clearance_mid = _validate_fresh_certificate_record(midpoint, require_reference=True)
    if not ok_rk4 or clearance_rk4 is None:
        return {**base, "evaluation_status": status_rk4}
    if not ok_mid or clearance_mid is None:
        return {**base, "evaluation_status": status_mid}
    alpha = rk4["alpha"]
    duration = rk4["command_duration_s"]
    expected_rk4 = fresh_a1_id("RK4_H_MS_0P0625", alpha, int(round(duration * 1000.0)))
    expected_mid = fresh_a1_id("MIDPOINT_H_MS_0P0625", alpha, int(round(duration * 1000.0)))
    if (
        type(alpha) is not float or alpha not in {0.5, 1.0, 2.0, 4.0, 8.0, 16.0}
        or type(duration) is not float or duration not in COMMAND_DURATIONS_S
        or midpoint["alpha"] != alpha or midpoint["command_duration_s"] != duration
        or rk4["method"] != "rk4" or midpoint["method"] != "midpoint"
        or rk4["lane_id"] != "RK4_H_MS_0P0625"
        or midpoint["lane_id"] != "MIDPOINT_H_MS_0P0625"
        or rk4["case_id"] != expected_rk4 or midpoint["case_id"] != expected_mid
        or rk4["acquisition_certificate_sha256"] == midpoint["acquisition_certificate_sha256"]
        or rk4["clearance_certificate_sha256"] == midpoint["clearance_certificate_sha256"]
        or rk4["evidence_path"] == midpoint["evidence_path"]
        or clearance_rk4["integrity_pass"] is not True
        or clearance_mid["integrity_pass"] is not True
    ):
        return {
            **base,
            "evaluation_status": "FAIL_G12_REGISTERED_PAIR_OR_FRESH_PROVENANCE",
            "alpha": alpha,
            "command_duration_s": duration,
        }
    finite_rk4 = clearance_rk4["finite_bilateral_removal_event"]
    finite_mid = clearance_mid["finite_bilateral_removal_event"]
    record = {
        "structurally_valid": False,
        "source_only_schema_valid": True,
        "trajectory_raw_verified": False,
        "scientific_predicate": False,
        "eligible": False,
        "alpha": alpha,
        "command_duration_s": duration,
        "rk4_case_id": rk4["case_id"],
        "midpoint_case_id": midpoint["case_id"],
        "rk4_acquisition_certificate_sha256": rk4["acquisition_certificate_sha256"],
        "midpoint_acquisition_certificate_sha256": midpoint["acquisition_certificate_sha256"],
        "rk4_clearance_certificate_sha256": rk4["clearance_certificate_sha256"],
        "midpoint_clearance_certificate_sha256": midpoint["clearance_certificate_sha256"],
        "rk4_evidence_path": rk4["evidence_path"],
        "midpoint_evidence_path": midpoint["evidence_path"],
    }
    if not finite_rk4 and not finite_mid:
        return {
            **record,
            "evaluation_status": "HOLD_G12_NO_TRAJECTORY_RAW_TO_VERIFY_NOT_APPLICABLE_CLAIM",
            "source_only_candidate_status": "NOT_APPLICABLE_NO_PAIRED_FINITE_REFERENCE_EVENT",
        }
    if finite_rk4 and finite_mid:
        acq_difference = abs(clearance_rk4["acquisition_time_s"] - clearance_mid["acquisition_time_s"])
        removal_difference = abs(clearance_rk4["removal_time_s"] - clearance_mid["removal_time_s"])
        work_difference = abs(clearance_rk4["signed_work_terminal_J"] - clearance_mid["signed_work_terminal_J"])
        work_tolerance = max(
            1e-10,
            0.001 * max(abs(clearance_rk4["signed_work_terminal_J"]), abs(clearance_mid["signed_work_terminal_J"])),
        )
        predicate = bool(
            clearance_rk4["post_release_passed"] is True
            and clearance_mid["post_release_passed"] is True
            and acq_difference <= 0.00025
            and removal_difference <= 0.00025
            and work_difference <= work_tolerance
        )
        return {
            **record,
            "evaluation_status": "HOLD_G12_FUTURE_TRAJECTORY_RAW_NOT_EXECUTED",
            "source_only_candidate_status": "PASS_G12_PAIR_EVALUATED",
            "source_only_candidate_predicate": predicate,
            "acquisition_time_difference_s": acq_difference,
            "removal_time_difference_s": removal_difference,
            "signed_work_difference_J": work_difference,
            "signed_work_tolerance_J": work_tolerance,
        }
    return {
        **record,
        "evaluation_status": "HOLD_G12_NO_TRAJECTORY_RAW_TO_VERIFY_ONE_SIDE_NONFINITE_CLAIM",
        "source_only_candidate_status": "PASS_G12_PAIR_EVALUATED_ONE_SIDE_NONFINITE",
    }


def aggregate_g12(fresh_records: list[dict[str, Any]]) -> dict[str, Any]:
    """Build all 18 pairs internally from exactly 36 raw fresh records.

    Caller-produced pair summaries are intentionally not accepted.  In this
    source-only version the pair records remain HOLD because no R2 trajectory
    raw exists, so aggregate PASS and recommendation are necessarily false.
    """

    base = {
        "aggregate_pass": False,
        "record_count": len(fresh_records) if isinstance(fresh_records, list) else 0,
        "pair_count": 0,
        "eligible_count": 0,
        "recommend_A2_including_campaign_review": False,
        "full_campaign_authorized": False,
        "r2_runtime_trajectory_evaluated": False,
    }
    if (
        type(fresh_records) is not list
        or len(fresh_records) != 36
        or any(not isinstance(record, dict) or set(record) != G12_RECORD_KEYS for record in fresh_records)
    ):
        return {**base, "status": "FAIL_G12_EXACT_THIRTY_SIX_RAW_RECORDS_REQUIRED"}
    expected_ids = {
        fresh_a1_id(lane, alpha, duration_ms)
        for lane in ("RK4_H_MS_0P0625", "MIDPOINT_H_MS_0P0625")
        for alpha in (0.5, 1.0, 2.0, 4.0, 8.0, 16.0)
        for duration_ms in (5, 10, 20)
    }
    if {record["case_id"] for record in fresh_records} != expected_ids:
        return {**base, "status": "FAIL_G12_FROZEN_REFERENCE_CASE_SET_MISMATCH"}
    by_key = {(record["method"], record["alpha"], record["command_duration_s"]): record for record in fresh_records}
    if len(by_key) != 36:
        return {**base, "status": "FAIL_G12_DUPLICATE_METHOD_LEVEL"}
    pairs: list[dict[str, Any]] = []
    for alpha in (0.5, 1.0, 2.0, 4.0, 8.0, 16.0):
        for duration in (0.005, 0.01, 0.02):
            try:
                pair = evaluate_g12_pair(
                    by_key[("rk4", alpha, duration)],
                    by_key[("midpoint", alpha, duration)],
                )
            except KeyError:
                return {**base, "status": "FAIL_G12_LEVEL_PAIR_MISSING"}
            pairs.append(pair)
    case_ids = [record["case_id"] for record in fresh_records]
    acquisition_hashes = [record["acquisition_certificate_sha256"] for record in fresh_records]
    clearance_hashes = [record["clearance_certificate_sha256"] for record in fresh_records]
    evidence_paths = [record["evidence_path"] for record in fresh_records]
    uniqueness_pass = bool(
        len(case_ids) == len(set(case_ids)) == 36
        and len(acquisition_hashes) == len(set(acquisition_hashes)) == 36
        and all(_hex64(value) for value in acquisition_hashes)
        and len(clearance_hashes) == len(set(clearance_hashes)) == 36
        and all(_hex64(value) for value in clearance_hashes)
        and len(evidence_paths) == len(set(evidence_paths)) == 36
        and all(_safe_relative_evidence_path(value) for value in evidence_paths)
    )
    structural_pass = bool(
        uniqueness_pass
        and all(pair.get("structurally_valid") is True for pair in pairs)
        and all(pair.get("eligible") is pair.get("scientific_predicate") for pair in pairs)
    )
    eligible_count = sum(pair.get("eligible") is True for pair in pairs) if structural_pass else 0
    return {
        **base,
        "status": (
            "PASS_G12_AGGREGATE_STRUCTURE" if structural_pass
            else "HOLD_G12_AGGREGATE_NO_VERIFIED_R2_TRAJECTORY_RAW"
        ),
        "aggregate_pass": structural_pass,
        "pair_count": len(pairs),
        "eligible_count": eligible_count,
        "all_36_case_ids_certificates_and_evidence_paths_unique": uniqueness_pass,
        "recommend_A2_including_campaign_review": bool(structural_pass and eligible_count >= 1),
        "pairs": pairs,
    }


def validate_common_case_metadata(metadata: dict[str, Any]) -> bool:
    expected = {
        "execution_family": "COMMON_PROP",
        "donor_group_sha256": COMMON_GROUP_SHA256,
        "donor_certificate_sha256": DONOR_PAYLOAD_SHA256,
        "g12_credit": False,
        "selector_input": False,
        "fresh_acquisition_credit": False,
        "shared_removal_credit": False,
    }
    return isinstance(metadata, dict) and metadata == expected


def validator_g04_signature() -> dict[str, Any]:
    """Independent literal validator signature; do not delegate to runner."""

    required_fields = [
        "W_act_initial_J", "sample_power_recomputed_W", "sample_power_reported_W",
        "sample_power_max_abs_error_W", "stage_power_recomputed_W", "stage_power_reported_W",
        "stage_power_max_abs_error_W", "cumulative_trapezoid_work_J",
        "cumulative_max_abs_error_J", "terminal_native_abs_error_J",
        "terminal_every_second_abs_error_J", "finite_removal_present",
        "active_terminal_W_act_J", "post_W_act_J", "post_actuator_work_reset_on_removal",
        "post_generalized_force_Q_14", "all_terms_finite", "scientific_predicate",
    ]
    pass_expression = (
        "all_terms_finite AND W_act_initial_J==0.0 AND sample_power_max_abs_error_W<=1e-14_W_with_rtol_0 AND "
        "stage_power_max_abs_error_W<=1e-14_W_with_rtol_0 AND cumulative_max_abs_error_J<=1e-7_J AND "
        "terminal_native_abs_error_J<=1e-7_J AND (terminal_native_abs_error_J<=terminal_every_second_abs_error_J+1e-15_J OR "
        "terminal_every_second_abs_error_J<=1e-7_J) AND ((finite_removal_present==false) OR "
        "(all(post_W_act_J[j]==active_terminal_W_act_J for every saved post sample j) AND "
        "post_actuator_work_reset_on_removal==false AND all(post_generalized_force_Q_14[j,k]==0.0 for every saved post sample j and k=0..13)))"
    )
    return {
        "rule_id": "B4G_R2_G04_UNIFIED_STAGE_CUMULATIVE_TERMINAL_AND_POST_CARRY_V1",
        "required_fields": required_fields,
        "pass_expression": pass_expression,
    }


def validate_g04_signature_match(runner_signature: dict[str, Any]) -> bool:
    return bool(
        isinstance(runner_signature, dict)
        and runner_signature == validator_g04_signature()
        and runner_signature["rule_id"] == G04_RULE_ID
        and runner_signature["required_fields"] == list(G04_REQUIRED_FIELDS)
        and runner_signature["pass_expression"] == G04_PASS_EXPRESSION
    )


__all__ = [
    "CLEARANCE_CERTIFICATE_KEYS", "COMMON_RECORD_KEYS", "FRESH_ACQ_RECORD_KEYS",
    "FRESH_ALPHA16_RECORD_KEYS", "G12_RECORD_KEYS", "REQUIRED_ALPHA16_GATE_IDS",
    "aggregate_g12", "evaluate_common_propagation_records",
    "evaluate_common_propagation_triplet", "evaluate_finest_cross_method",
    "evaluate_fresh_acquisition_records", "evaluate_fresh_acquisition_triplet",
    "evaluate_fresh_alpha16_three_step", "evaluate_fresh_technical_repeats",
    "evaluate_g12_pair", "project_fresh_acquisition_identity", "validate_common_case_metadata",
    "validate_common_propagation_campaign", "validate_common_registry_structure",
    "validate_g04_signature_match",
    "validator_g04_signature",
]
