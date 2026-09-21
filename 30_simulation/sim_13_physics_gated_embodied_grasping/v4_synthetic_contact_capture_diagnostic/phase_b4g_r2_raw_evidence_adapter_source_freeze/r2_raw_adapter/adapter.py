"""Strict sidecar/NPZ adapter and raw-derived source-only evaluations.

Every NPZ is read once into bytes, SHA-bound, and opened from ``BytesIO`` with
``allow_pickle=False``.  Sidecar numeric claims never substitute for arrays.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from io import BytesIO
import math
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Mapping, NamedTuple
import zipfile

import numpy as np

from .array_contract import (
    ARRAY_CONTRACT_DOCUMENT_SHA256,
    OUTCOME_TO_PROFILE,
    PROFILE_DEFINITIONS,
    PROFILE_SHA256,
)
from .path_binding import PathBindingError, single_read_project_file
from .production_api import ProductionAPIError, load_production_modules, project_root
from .schedule_binding import SOURCE_HASHES, expected_binding, schedule_records
from .strict_json import StrictJSONError, canonical_sha256, loads_bytes


SIDECAR_BASE_KEYS = {
    "schema", "case_id", "lane_id", "method", "step_s", "execution_family",
    "outcome", "array_profile", "npz_relative_path", "npz_bytes",
    "npz_sha256", "array_contract_sha256", "array_contract_document_sha256",
    "acquisition_time_s", "command_duration_s", "alpha", "schedule_index",
    "matrix_row_sha256", "source_hashes",
    "registered_roles",
}
FRESH_SIDECAR_KEYS = SIDECAR_BASE_KEYS
FINITE_FRESH_SIDECAR_KEYS = FRESH_SIDECAR_KEYS | {"removal_time_s"}
A0_SIDECAR_KEYS = SIDECAR_BASE_KEYS | {"bookend_sentinel"}
OUTCOME_FINITE = "FINITE_BILATERAL_REMOVAL_OBSERVED"
OUTCOME_NO_REMOVAL = "NO_REMOVAL_OBSERVED_WITHIN_SAVED_WINDOW"
OUTCOME_COMMON = "COMMON_PROPAGATION_WINDOW_COMPLETE"
OUTCOME_A0 = "A0_BOOKEND_WINDOW_COMPLETE_NO_CAPTURE_EVENT"
FRESH_ACQ_ROLE = "FRESH_ACQ_OBSERVATION"
FRESH_ALPHA16_ROLE = "FRESH_ALPHA16_PROPAGATION"
G12_ROLE = "G12_FRESH_REFERENCE"
COMMON_ROLE = "COMMON_PROPAGATION_DIAGNOSTIC"
A0_ROLE = "A0_BOOKEND"
FROZEN_LANE_STEPS_S = (0.00025, 0.000125, 0.0000625)
NO_REMOVAL_SAVED_HORIZON_S = 0.08
POST_RELEASE_WINDOW_S = 0.005
COMMON_COARSE_GRID_STEP_S = 0.00025
MAX_NPZ_TOTAL_UNCOMPRESSED_BYTES = 256 * 1024 * 1024
DONOR_PAYLOAD_SHA256 = "DA3E10D7D30DFD9BABFB71BF055D62A1BD06CF8DE3023E463A649FF92A952D15"
COMMON_GROUP_SHA256 = "396A903DA584765FDA03B867F2F3F27B910CED9383D34BC5064A01B33D4F6444"
COMMON_DONOR_RELATIVE_PATH = (
    "30_simulation/sim_13_physics_gated_embodied_grasping/"
    "v4_synthetic_contact_capture_diagnostic/"
    "phase_b4g_post_freeze_synthetic_jaw_retraction_execution/"
    "evidence/raw_cases/052__RK4_REFERENCE__A1__ALPHA_16__TCMD_MS_10.json"
)
COMMON_DONOR_HASHES = MappingProxyType({
    "payload_canonical_bytes": 31092,
    "payload_sha256": DONOR_PAYLOAD_SHA256,
    "group_canonical_bytes": 1317,
    "group_sha256": COMMON_GROUP_SHA256,
})
COMMON_DONOR_PROJECTION_SHA256 = "1A1593F5E79EC5F59A435599C0A5088F24F83A17E5D38F4F25F65BEDD0C74337"
COMMON_SIDECAR_KEYS = SIDECAR_BASE_KEYS | {
    "common_donor_certificate_sha256", "common_state_group_sha256",
    "common_donor_hashes_before", "common_donor_hashes_after",
}


class AdapterError(ValueError):
    pass


class CommonDonorProjection(NamedTuple):
    acquisition_time_s: float
    service_state_29: tuple[float, ...]
    target_state_13: tuple[float, ...]
    projection_sha256: str


@dataclass(frozen=True)
class BoundRawCase:
    sidecar_relative_path: str
    sidecar_bytes: int
    sidecar_sha256: str
    sidecar: Mapping[str, Any]
    arrays: Mapping[str, np.ndarray]
    npz_relative_path: str
    npz_bytes: int
    npz_sha256: str
    array_profile: str
    array_contract_sha256: str

    def raw_binding(self) -> dict[str, Any]:
        return {
            "schema": "SIM13_V4B4G_R2_RAW_IMMUTABLE_BINDING_V1",
            "case_id": self.sidecar["case_id"],
            "sidecar_relative_path": self.sidecar_relative_path,
            "sidecar_bytes": self.sidecar_bytes,
            "sidecar_sha256": self.sidecar_sha256,
            "npz_relative_path": self.npz_relative_path,
            "npz_bytes": self.npz_bytes,
            "npz_sha256": self.npz_sha256,
            "array_profile": self.array_profile,
            "array_contract_sha256": self.array_contract_sha256,
            "array_contract_document_sha256": ARRAY_CONTRACT_DOCUMENT_SHA256,
        }


def _hex64(value: Any) -> bool:
    return type(value) is str and len(value) == 64 and all(char in "0123456789ABCDEF" for char in value)


def _finite_float(value: Any) -> bool:
    return type(value) is float and math.isfinite(value)


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _deep_freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_deep_freeze(item) for item in value)
    return value


def common_donor_projection() -> CommonDonorProjection:
    """Rehydrate and re-hash the donor on every call, without a solver.

    A process-global success cache is intentionally forbidden.  COMMON case
    loading calls this once before and once after reading its NPZ, so every
    case observes the current hash-locked external source.
    """

    try:
        modules = load_production_modules()
        rehydrator = modules["rehydrator"]
        fixture = rehydrator.load_donor_fixture(project_root() / COMMON_DONOR_RELATIVE_PATH)
        hashes = rehydrator.fixture_hashes(fixture)
        group = rehydrator.derive_common_group(fixture)
    except AdapterError:
        raise
    except Exception as exc:
        raise AdapterError("COMMON_DONOR_REHYDRATION_FAILED") from exc
    if (
        hashes != COMMON_DONOR_HASHES
        or fixture.declared_certificate_sha256 != DONOR_PAYLOAD_SHA256
        or canonical_sha256(group) != COMMON_GROUP_SHA256
    ):
        raise AdapterError("COMMON_DONOR_REHYDRATION_OR_HASH_BINDING_INVALID")
    service = [
        *group["service"]["base_position_inertial_m"],
        *group["service"]["base_quaternion_body_to_inertial_wxyz"],
        *group["service"]["joint_coordinates_mixed"],
        *group["service"]["post_acquisition_eta_mixed"],
    ]
    target = [
        *group["target"]["position_inertial_m"],
        *group["target"]["quaternion_body_to_inertial_wxyz"],
        *group["target"]["post_acquisition_twist_inertial_mixed"],
    ]
    if len(service) != 29 or len(target) != 13:
        raise AdapterError("COMMON_DONOR_STATE_WIDTH_INVALID")
    projection = {
        "acquisition_time_s": float(group["acquisition_time_s"]),
        "service_state_29": [float(value) for value in service],
        "target_state_13": [float(value) for value in target],
    }
    projection_sha256 = canonical_sha256(projection)
    if projection_sha256 != COMMON_DONOR_PROJECTION_SHA256:
        raise AdapterError("COMMON_DONOR_CANONICAL_PROJECTION_DIGEST_DRIFT")
    return CommonDonorProjection(
        projection["acquisition_time_s"],
        tuple(projection["service_state_29"]),
        tuple(projection["target_state_13"]),
        projection_sha256,
    )


def _validate_sidecar(sidecar: Any, sidecar_relative_path: str) -> None:
    if not isinstance(sidecar, dict):
        raise AdapterError("SIDECAR_OBJECT_REQUIRED")
    outcome = sidecar.get("outcome")
    expected_keys = (
        FINITE_FRESH_SIDECAR_KEYS if outcome == OUTCOME_FINITE
        else FRESH_SIDECAR_KEYS if outcome == OUTCOME_NO_REMOVAL
        else COMMON_SIDECAR_KEYS if outcome == OUTCOME_COMMON
        else A0_SIDECAR_KEYS if outcome == OUTCOME_A0
        else set()
    )
    if not expected_keys or set(sidecar) != expected_keys:
        raise AdapterError("SIDECAR_EXACT_SCHEMA_OR_OUTCOME_REQUIRED")
    profile = OUTCOME_TO_PROFILE[outcome]
    case_id = sidecar["case_id"]
    sidecar_path = PurePosixPath(sidecar_relative_path)
    expected_npz = sidecar_path.with_suffix(".npz").as_posix()
    try:
        registered = expected_binding(case_id)
    except (ValueError, ProductionAPIError) as exc:
        raise AdapterError("SIDECAR_CASE_NOT_IN_FROZEN_78_ROW_MATRIX") from exc
    row = registered["row"]
    if (
        sidecar["schema"] != "SIM13_V4B4G_R2_RAW_CASE_SIDECAR_V1"
        or type(case_id) is not str or not case_id or sidecar_path.stem != case_id
        or type(sidecar["lane_id"]) is not str or not sidecar["lane_id"]
        or sidecar["method"] not in {"rk4", "midpoint"}
        or not _finite_float(sidecar["step_s"]) or sidecar["step_s"] <= 0.0
        or sidecar["array_profile"] != profile
        or sidecar["array_contract_sha256"] != PROFILE_SHA256[profile]
        or sidecar["array_contract_document_sha256"] != ARRAY_CONTRACT_DOCUMENT_SHA256
        or sidecar["npz_relative_path"] != expected_npz
        or type(sidecar["npz_bytes"]) is not int or sidecar["npz_bytes"] <= 0
        or not _hex64(sidecar["npz_sha256"])
        or type(sidecar["schedule_index"]) is not int
        or sidecar["schedule_index"] != registered["schedule_index"]
        or sidecar["matrix_row_sha256"] != registered["matrix_row_sha256"]
        or sidecar["source_hashes"] != SOURCE_HASHES
        or sidecar["registered_roles"] != row["roles"]
        or sidecar["lane_id"] != row["lane_id"] or sidecar["method"] != row["method"]
        or sidecar["step_s"] != row["step_s"] or sidecar["execution_family"] != row["execution_family"]
        or sidecar["alpha"] != row["alpha"] or sidecar["command_duration_s"] != row["command_duration_s"]
    ):
        raise AdapterError("SIDECAR_IDENTITY_PATH_HASH_OR_CONTRACT_INVALID")
    if outcome in {OUTCOME_FINITE, OUTCOME_NO_REMOVAL}:
        if (
            sidecar["execution_family"] != "FRESH"
            or row["arm"] != "A1"
            or not _finite_float(sidecar["alpha"]) or sidecar["alpha"] <= 0.0
            or not _finite_float(sidecar["acquisition_time_s"]) or sidecar["acquisition_time_s"] < 0.0
        ):
            raise AdapterError("FRESH_SIDECAR_ROLE_OR_ALPHA_INVALID")
    else:
        if outcome == OUTCOME_COMMON:
            # Measured pre-NPZ binding.  A second uncached measurement is made
            # after NPZ decoding in _validate_shapes_and_relations.
            donor_before = common_donor_projection()
            if (
                sidecar["execution_family"] != "COMMON_PROP" or sidecar["registered_roles"] != [COMMON_ROLE]
                or not _finite_float(sidecar["alpha"]) or sidecar["alpha"] != 16.0
                or not _finite_float(sidecar["command_duration_s"]) or sidecar["command_duration_s"] <= 0.0
                or not _finite_float(sidecar["acquisition_time_s"]) or sidecar["acquisition_time_s"] < 0.0
                or sidecar["common_donor_certificate_sha256"] != DONOR_PAYLOAD_SHA256
                or sidecar["common_state_group_sha256"] != COMMON_GROUP_SHA256
                or sidecar["common_donor_hashes_before"] != COMMON_DONOR_HASHES
                or sidecar["common_donor_hashes_after"] != COMMON_DONOR_HASHES
                or donor_before.projection_sha256 != COMMON_DONOR_PROJECTION_SHA256
            ):
                raise AdapterError("COMMON_SIDECAR_ROLE_OR_LEVEL_INVALID")
        elif not (
            sidecar["execution_family"] == "FRESH"
            and sidecar["registered_roles"] == [A0_ROLE]
            and sidecar["alpha"] == "NOT_APPLICABLE_A0"
            and sidecar["command_duration_s"] == "NOT_APPLICABLE_A0"
            and sidecar["acquisition_time_s"] == "NOT_APPLICABLE_A0"
            and sidecar["bookend_sentinel"] == row["sentinel"]
        ):
            raise AdapterError("A0_BOOKEND_SIDECAR_ENUM_OR_SENTINEL_INVALID")
    if outcome == OUTCOME_FINITE and (
        not _finite_float(sidecar["removal_time_s"])
        or sidecar["removal_time_s"] < sidecar["acquisition_time_s"]
    ):
        raise AdapterError("FINITE_REMOVAL_TIME_INVALID")


def _load_npz_arrays(payload: bytes, profile_name: str) -> dict[str, np.ndarray]:
    expected = PROFILE_DEFINITIONS[profile_name]["arrays"]
    try:
        with zipfile.ZipFile(BytesIO(payload), "r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            expected_members = {f"{name}.npy" for name in expected}
            if len(names) != len(set(names)) or set(names) != expected_members:
                raise AdapterError("NPZ_EXACT_MEMBER_SET_OR_DUPLICATE_MEMBER_INVALID")
            if sum(info.file_size for info in infos) > MAX_NPZ_TOTAL_UNCOMPRESSED_BYTES:
                raise AdapterError("NPZ_TOTAL_UNCOMPRESSED_SIZE_LIMIT_EXCEEDED")
            for info in infos:
                member = PurePosixPath(info.filename)
                if (
                    info.is_dir() or info.flag_bits & 0x1 or member.is_absolute()
                    or len(member.parts) != 1 or any(part in {"", ".", ".."} for part in member.parts)
                    or info.file_size <= 0 or info.file_size > 256 * 1024 * 1024
                    or info.compress_size <= 0 or info.file_size / info.compress_size > 200.0
                ):
                    raise AdapterError("NPZ_ARCHIVE_MEMBER_UNSAFE")
        with np.load(BytesIO(payload), allow_pickle=False) as archive:
            if set(archive.files) != set(expected) or len(archive.files) != len(expected):
                raise AdapterError("NPZ_EXACT_ARRAY_SET_REQUIRED")
            arrays: dict[str, np.ndarray] = {}
            for name in expected:
                value = np.asarray(archive[name])
                if value.dtype.str != expected[name]["dtype"]:
                    raise AdapterError(f"NPZ_DTYPE_OR_ENDIAN_INVALID:{name}:{value.dtype.str}")
                if value.dtype.hasobject or value.dtype.kind in {"O", "S", "U", "V"}:
                    raise AdapterError(f"NPZ_PICKLE_OBJECT_STRING_OR_STRUCTURED_FORBIDDEN:{name}")
                if value.dtype.kind == "f" and not np.all(np.isfinite(value)):
                    raise AdapterError(f"NPZ_NONFINITE_ARRAY_FORBIDDEN:{name}")
                # A normal owning ndarray can later have WRITEABLE re-enabled.
                # Rebuild over an immutable ``bytes`` buffer so post-hash
                # mutation cannot detach evaluation from the bound NPZ.
                immutable = np.frombuffer(value.tobytes(order="C"), dtype=value.dtype).reshape(value.shape)
                immutable.setflags(write=False)
                arrays[name] = immutable
            return arrays
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        if isinstance(exc, AdapterError):
            raise
        if "Object arrays cannot be loaded" in str(exc):
            raise AdapterError("NPZ_PICKLE_OBJECT_ARRAY_FORBIDDEN_ALLOW_PICKLE_FALSE") from exc
        raise AdapterError("NPZ_PARSE_FAILED_ALLOW_PICKLE_FALSE") from exc


def _validate_shapes_and_relations(sidecar: dict[str, Any], arrays: dict[str, np.ndarray]) -> None:
    profile = sidecar["array_profile"]
    specs = PROFILE_DEFINITIONS[profile]["arrays"]
    n = int(arrays["time_s"].size)
    s = int(arrays["stage_time_s"].size)
    acquisition_count = int(arrays["acquisition_event_count"].item())
    removal_count = int(arrays["bilateral_removal_event_count"].item())
    symbols = {
        "N": n,
        "S": s,
        "P": int(arrays["post_time_s"].size),
        "PS": int(arrays["post_stage_time_s"].size),
        "A": acquisition_count,
        "R": removal_count,
        "I": n - 1,
    }
    if n < 2 or s < 1:
        raise AdapterError("NONEMPTY_SAVED_AND_STAGE_HISTORY_REQUIRED")
    for name, spec in specs.items():
        expected_shape = tuple(symbols[item] if isinstance(item, str) else item for item in spec["shape"])
        if arrays[name].shape != expected_shape:
            raise AdapterError(f"NPZ_SHAPE_INVALID:{name}:{arrays[name].shape}:{expected_shape}")
    time_s = arrays["time_s"]
    if time_s.size == 0 or np.any(np.diff(time_s) <= 0.0):
        raise AdapterError("SAVED_TIME_EMPTY_OR_NOT_STRICTLY_INCREASING")
    if not np.all(arrays["active_interval_ledger_certified"]):
        raise AdapterError("ACTIVE_INTERVAL_LEDGER_MUST_CERTIFY_EVERY_SAVED_INTERVAL")
    step_s = sidecar["step_s"]
    intervals = np.diff(time_s)
    if np.any(intervals <= 0.0):
        raise AdapterError("SAVED_INTERVAL_NONPOSITIVE")
    if intervals.size > 1 and np.any(np.abs(intervals[:-1] - step_s) > 1e-15):
        raise AdapterError("ONLY_FINAL_INTERVAL_MAY_BE_FRACTIONAL")
    if float(intervals[-1]) > step_s + 1e-15:
        raise AdapterError("FINAL_INTERVAL_EXCEEDS_NOMINAL_MAX_STEP")
    final_fractional = abs(float(intervals[-1]) - step_s) > 1e-15
    if final_fractional and sidecar["outcome"] != OUTCOME_FINITE:
        raise AdapterError("FRACTIONAL_FINAL_INTERVAL_REQUIRES_RAW_FINITE_REMOVAL")
    method = sidecar["method"]
    if method == "rk4":
        block_codes = [1, 2, 3, 4]
        offsets = [0.0, 0.5, 0.5, 1.0]
    else:
        block_codes = [1, 5]
        offsets = [0.0, 0.5]
    expected_codes: list[int] = []
    expected_stage_times: list[float] = []
    for left, right in zip(time_s, time_s[1:]):
        h = float(right - left)
        expected_codes.extend(block_codes)
        expected_stage_times.extend(float(left + offset * h) for offset in offsets)
    if arrays["stage_code"].tolist() != expected_codes:
        raise AdapterError("METHOD_SPECIFIC_STAGE_CODE_SEQUENCE_INVALID")
    if not np.array_equal(arrays["stage_time_s"], np.asarray(expected_stage_times, dtype="<f8")):
        raise AdapterError("METHOD_SPECIFIC_STAGE_TIME_SEQUENCE_INVALID")
    if np.any(arrays["stage_mass_cholesky_min_diagonal"] <= 0.0):
        raise AdapterError("NONPOSITIVE_STAGE_MASS_CHOLESKY_DIAGONAL")
    if not np.array_equal(arrays["stage_P_coordinates_m"], arrays["stage_service_state_29"][:, 13:15]):
        raise AdapterError("ACTIVE_STAGE_P_COORDINATE_REDUNDANCY_MISMATCH")
    if acquisition_count not in {0, 1}:
        raise AdapterError("ACQUISITION_EVENT_COUNT_MUST_BE_ZERO_OR_ONE")
    if removal_count not in {0, 1}:
        raise AdapterError("REMOVAL_EVENT_COUNT_MUST_BE_ZERO_OR_ONE")
    saved_end = int(arrays["saved_window_end_index"].item())
    if saved_end != n - 1:
        raise AdapterError("SAVED_WINDOW_END_MUST_BIND_FINAL_SAVED_SAMPLE")
    if sidecar["outcome"] == OUTCOME_A0:
        if acquisition_count != 0 or removal_count != 0 or symbols["P"] != 0 or symbols["PS"] != 0:
            raise AdapterError("A0_BOOKEND_REQUIRES_ZERO_CAPTURE_EVENTS_AND_ZERO_POST_ARRAYS")
        return
    if acquisition_count != 1:
        raise AdapterError("A1_OR_COMMON_ACQUISITION_EVENT_COUNT_MUST_EQUAL_ONE")
    acquisition = int(arrays["acquisition_event_sample_index"][0])
    if acquisition != 0 or saved_end != n - 1:
        raise AdapterError("ACQUISITION_MUST_BE_FIRST_SAVED_SAMPLE_AND_WINDOW_END_LAST")
    if float(arrays["acquisition_event_time_s"][0]) != float(time_s[acquisition]) or float(arrays["acquisition_event_time_s"][0]) != sidecar["acquisition_time_s"]:
        raise AdapterError("ACQUISITION_INDEX_TIME_MISMATCH")
    if sidecar["outcome"] == OUTCOME_COMMON:
        # Uncached post-NPZ donor measurement; source drift between or across
        # case loads cannot inherit an earlier successful result.
        donor = common_donor_projection()
        if (
            float(time_s[0]) != donor.acquisition_time_s
            or tuple(arrays["service_state_29"][0].tolist()) != donor.service_state_29
            or tuple(arrays["target_state_13"][0].tolist()) != donor.target_state_13
        ):
            raise AdapterError("COMMON_RAW_INITIAL_STATE_NOT_EXACT_FROZEN_DONOR_PROJECTION")
    if sidecar["outcome"] == OUTCOME_FINITE:
        if removal_count != 1 or symbols["P"] < 2:
            raise AdapterError("FINITE_OUTCOME_REQUIRES_ONE_RAW_EVENT_AND_AT_LEAST_TWO_POST_SAMPLES")
        removal = int(arrays["bilateral_removal_active_sample_index"][0])
        if not (0 <= acquisition <= removal <= saved_end < n):
            raise AdapterError("ACQUISITION_REMOVAL_WINDOW_INDEX_ORDER_INVALID")
        raw_removal_time = float(arrays["bilateral_removal_event_time_s"][0])
        if raw_removal_time != float(time_s[removal]) or raw_removal_time != sidecar["removal_time_s"]:
            raise AdapterError("REMOVAL_INDEX_TIME_MISMATCH")
        if removal != saved_end:
            raise AdapterError("FINITE_REMOVAL_MUST_TERMINATE_ACTIVE_SAVED_WINDOW")
        post_time = arrays["post_time_s"]
        if post_time.size == 0 or np.any(np.diff(post_time) <= 0.0) or float(post_time[0]) != sidecar["removal_time_s"]:
            raise AdapterError("POST_TIME_EMPTY_NONMONOTONIC_OR_NOT_BOUND_TO_REMOVAL")
        if float(post_time[-1]) != float(post_time[0] + POST_RELEASE_WINDOW_S):
            raise AdapterError("POST_RELEASE_WINDOW_MUST_EQUAL_EXACT_5MS")
        expected_post_time = post_time[0] + np.arange(post_time.size, dtype="<f8") * step_s
        if not np.array_equal(post_time, expected_post_time):
            raise AdapterError("POST_SAVED_INTERVAL_MUST_EQUAL_REGISTERED_LANE_STEP")
        post_stages_per_step = 4 if method == "rk4" else 2
        if symbols["PS"] != post_stages_per_step * (symbols["P"] - 1):
            raise AdapterError("POST_MECHANICAL_STAGE_COUNT_INVALID")
        post_codes_expected: list[int] = []
        post_times_expected: list[float] = []
        for left, right in zip(post_time, post_time[1:]):
            h = float(right - left)
            post_codes_expected.extend(block_codes)
            post_times_expected.extend(float(left + offset * h) for offset in offsets)
        if arrays["post_stage_code"].tolist() != post_codes_expected:
            raise AdapterError("POST_MECHANICAL_STAGE_CODE_SEQUENCE_INVALID")
        if not np.array_equal(arrays["post_stage_time_s"], np.asarray(post_times_expected, dtype="<f8")):
            raise AdapterError("POST_MECHANICAL_STAGE_TIME_SEQUENCE_INVALID")
        if not np.array_equal(arrays["post_stage_P_coordinates_m"], arrays["post_stage_service_state_29"][:, 13:15]):
            raise AdapterError("POST_STAGE_P_COORDINATE_REDUNDANCY_MISMATCH")
    else:
        if removal_count != 0 or symbols["P"] != 0 or symbols["PS"] != 0:
            raise AdapterError("NO_REMOVAL_OUTCOME_REQUIRES_ZERO_EVENT_AND_ZERO_LENGTH_POST_ARRAYS")
        if sidecar["outcome"] == OUTCOME_NO_REMOVAL and float(time_s[-1]) != float(time_s[acquisition] + NO_REMOVAL_SAVED_HORIZON_S):
            raise AdapterError("NO_REMOVAL_SAVED_WINDOW_MUST_EQUAL_EXACT_80MS")


def load_bound_case(project_root: Path, sidecar_relative_path: str) -> BoundRawCase:
    try:
        sidecar_file = single_read_project_file(project_root, sidecar_relative_path, suffix=".json")
        sidecar = loads_bytes(sidecar_file.payload)
        _validate_sidecar(sidecar, sidecar_file.relative_path)
        npz_file = single_read_project_file(project_root, sidecar["npz_relative_path"], suffix=".npz")
    except (PathBindingError, StrictJSONError) as exc:
        raise AdapterError(str(exc)) from exc
    digest = hashlib.sha256(npz_file.payload).hexdigest().upper()
    if npz_file.byte_count != sidecar["npz_bytes"] or digest != sidecar["npz_sha256"]:
        raise AdapterError("NPZ_BYTES_OR_SHA256_BINDING_MISMATCH")
    arrays = _load_npz_arrays(npz_file.payload, sidecar["array_profile"])
    _validate_shapes_and_relations(sidecar, arrays)
    sidecar_digest = hashlib.sha256(sidecar_file.payload).hexdigest().upper()
    return BoundRawCase(
        sidecar_file.relative_path,
        sidecar_file.byte_count,
        sidecar_digest,
        _deep_freeze(sidecar),
        MappingProxyType(arrays),
        npz_file.relative_path,
        npz_file.byte_count,
        digest,
        sidecar["array_profile"],
        sidecar["array_contract_sha256"],
    )


def _service_channels(state: np.ndarray) -> dict[str, Any]:
    return {
        "service_position_m": state[..., 0:3].tolist(),
        "service_quaternion": state[..., 3:7].tolist(),
        "R_joint_coordinates_rad": state[..., 7:13].tolist(),
        "P_joint_coordinates_m": state[..., 13:15].tolist(),
        "service_base_linear_velocity_m_s": state[..., 15:18].tolist(),
        "service_base_angular_velocity_rad_s": state[..., 18:21].tolist(),
        "R_joint_velocity_rad_s": state[..., 21:27].tolist(),
        "P_joint_velocity_m_s": state[..., 27:29].tolist(),
    }


def _target_channels(state: np.ndarray) -> dict[str, Any]:
    return {
        "target_position_m": state[..., 0:3].tolist(),
        "target_quaternion": state[..., 3:7].tolist(),
        "target_linear_velocity_m_s": state[..., 7:10].tolist(),
        "target_angular_velocity_rad_s": state[..., 10:13].tolist(),
    }


def _numeric_payload_sha256(arrays: Mapping[str, np.ndarray]) -> str:
    """Digest every numeric array including name, dtype, shape and C bytes."""

    digest = hashlib.sha256(b"SIM13_V4B4G_R2_NUMERIC_PAYLOAD_V1\0")
    for name in sorted(arrays):
        value = arrays[name]
        metadata = f"{name}\0{value.dtype.str}\0{','.join(str(item) for item in value.shape)}\0{value.nbytes}\0".encode("ascii")
        digest.update(len(metadata).to_bytes(8, "little"))
        digest.update(metadata)
        digest.update(value.tobytes(order="C"))
    return digest.hexdigest().upper()


def derive_fresh_acquisition_observation(case: BoundRawCase) -> dict[str, Any]:
    if (
        case.sidecar["execution_family"] != "FRESH"
        or FRESH_ACQ_ROLE not in case.sidecar["registered_roles"]
        or case.sidecar["alpha"] != 16.0
        or case.sidecar["command_duration_s"] != 0.01
    ):
        raise AdapterError("FRESH_RAW_CASE_REQUIRED")
    index = int(case.arrays["acquisition_event_sample_index"][0])
    service = case.arrays["service_state_29"][index]
    target = case.arrays["target_state_13"][index]
    kinetic = case.arrays["total_kinetic_energy_J"]
    work = case.arrays["signed_W_act_J"]
    channels = {
        **_service_channels(service),
        **_target_channels(target),
        "linear_momentum_native": case.arrays["total_linear_momentum_N_s"][index].tolist(),
        "angular_momentum_native": case.arrays["total_angular_momentum_N_m_s"][index].tolist(),
        "D_B3_minus_J": float(case.arrays["energy_minus_work_residual_J"][index]),
        "switch_energy_identity_J": float((kinetic[index] - kinetic[0]) - (work[index] - work[0])),
    }
    return {
        "schema": "SIM13_V4B4G_R2_RAW_DERIVED_FRESH_ACQUISITION_OBSERVATION_V1",
        "case_id": case.sidecar["case_id"],
        "lane_id": case.sidecar["lane_id"],
        "method": case.sidecar["method"],
        "step_s": case.sidecar["step_s"],
        "alpha": case.sidecar["alpha"],
        "command_duration_s": case.sidecar["command_duration_s"],
        "acquisition_index": index,
        "acquisition_time_s": float(case.arrays["time_s"][index]),
        "raw_binding": case.raw_binding(),
        "derivation_rule_id": "R2_RAW_EXACT_ARRAYS_AT_ACQUISITION_INDEX_V1",
        "channels": channels,
    }


def derive_common_propagation_observation(case: BoundRawCase) -> dict[str, Any]:
    if case.sidecar["execution_family"] != "COMMON_PROP" or COMMON_ROLE not in case.sidecar["registered_roles"]:
        raise AdapterError("COMMON_PROP_RAW_CASE_REQUIRED_NO_FRESH_CREDIT_REUSE")
    start = int(case.arrays["acquisition_event_sample_index"][0])
    end = int(case.arrays["saved_window_end_index"].item())
    # The frozen metric consumes every sample on the closed coarse common grid,
    # not merely the two endpoints.  The three lanes project with exact strides
    # 1/2/4 onto 0.25 ms acquisition-relative samples.
    stride_by_step = {0.00025: 1, 0.000125: 2, 0.0000625: 4}
    try:
        stride = stride_by_step[case.sidecar["step_s"]]
    except KeyError as exc:
        raise AdapterError("COMMON_PROP_UNREGISTERED_COMMON_GRID_STRIDE") from exc
    indices = np.arange(start, end + 1, stride, dtype=np.int64)
    service = case.arrays["service_state_29"][indices]
    target = case.arrays["target_state_13"][indices]
    time = case.arrays["time_s"][indices]
    if float(time[-1]) != float(time[0] + case.sidecar["command_duration_s"]):
        raise AdapterError("COMMON_PROP_RAW_HORIZON_NOT_EXACT_COMMAND_DURATION")
    common_count = int(round(case.sidecar["command_duration_s"] / COMMON_COARSE_GRID_STEP_S)) + 1
    expected_relative = np.arange(common_count, dtype="<f8") * COMMON_COARSE_GRID_STEP_S
    expected_relative[-1] = case.sidecar["command_duration_s"]
    if indices[-1] != end or not np.array_equal(time, time[0] + expected_relative):
        raise AdapterError("COMMON_PROP_EXACT_CLOSED_COMMON_SAMPLE_GRID_REQUIRED")
    channels = {
        **{key.replace("service_quaternion", "service_quaternion_body_to_inertial_wxyz"): value for key, value in _service_channels(service).items()},
        **{key.replace("target_quaternion", "target_quaternion_body_to_inertial_wxyz"): value for key, value in _target_channels(target).items()},
        "total_linear_momentum_kg_m_s": case.arrays["total_linear_momentum_N_s"][indices].tolist(),
        "total_angular_momentum_kg_m2_s": case.arrays["total_angular_momentum_N_m_s"][indices].tolist(),
        "total_kinetic_energy_J": case.arrays["total_kinetic_energy_J"][indices].tolist(),
        "energy_minus_work_residual_J": case.arrays["energy_minus_work_residual_J"][indices].tolist(),
    }
    return {
        "schema": "SIM13_V4B4G_R2_RAW_DERIVED_COMMON_PROPAGATION_OBSERVATION_V1",
        "case_id": case.sidecar["case_id"],
        "method": case.sidecar["method"],
        "step_s": case.sidecar["step_s"],
        "command_duration_s": case.sidecar["command_duration_s"],
        "time_grid_s": expected_relative.tolist(),
        "raw_binding": case.raw_binding(),
        "common_donor_binding": {
            "donor_certificate_sha256": case.sidecar["common_donor_certificate_sha256"],
            "state_group_sha256": case.sidecar["common_state_group_sha256"],
            "hashes_before": dict(case.sidecar["common_donor_hashes_before"]),
            "hashes_after": dict(case.sidecar["common_donor_hashes_after"]),
            "raw_initial_projection_sha256": canonical_sha256({
                "acquisition_time_s": float(time[0]),
                "service_state_29": service[0].tolist(),
                "target_state_13": target[0].tolist(),
            }),
        },
        "derivation_rule_id": "R2_RAW_EXACT_ARRAYS_ACQUISITION_TO_SAVED_WINDOW_END_V1",
        "channels": channels,
    }


def _filtered_stage(case: BoundRawCase) -> tuple[list[float], list[list[float]], list[list[float]], list[float], list[str]]:
    codes = case.arrays["stage_code"]
    if case.sidecar["method"] == "rk4":
        names = {1: "RK4_K1", 2: "RK4_K2", 3: "RK4_K3", 4: "RK4_K4"}
    else:
        names = {1: "MIDPOINT_K1", 5: "MIDPOINT_K2"}
    try:
        code_names = [names[int(value)] for value in codes]
    except KeyError as exc:
        raise AdapterError("UNREGISTERED_MECHANICAL_STAGE_CODE") from exc
    return (
        case.arrays["stage_time_s"].tolist(),
        case.arrays["stage_command_Q_14"].tolist(),
        case.arrays["stage_service_state_29"].tolist(),
        case.arrays["stage_augmented_W_act_J"].tolist(),
        code_names,
    )


def _evaluate_g06_actual_dt(case: BoundRawCase) -> tuple[dict[str, Any], dict[str, Any]]:
    """Recompute the R2 work state with actual final exact-event ``dt``.

    The prior frozen evaluator required every interval to equal nominal
    ``step_s``.  That is intentionally not called here because a valid finite
    removal may shorten only the final interval.
    """

    saved_time = case.arrays["time_s"]
    saved_work = case.arrays["signed_W_act_J"]
    kinetic = case.arrays["total_kinetic_energy_J"]
    stage_time = case.arrays["stage_time_s"]
    stage_q = case.arrays["stage_command_Q_14"]
    stage_state = case.arrays["stage_service_state_29"]
    stage_work = case.arrays["stage_augmented_W_act_J"]
    stage_reported_power = case.arrays["stage_power_W"]
    stage_power = stage_q[:, 12] * stage_state[:, 27] + stage_q[:, 13] * stage_state[:, 28]
    power_error = float(np.max(np.abs(stage_power - stage_reported_power)))
    stages_per_step = 4 if case.sidecar["method"] == "rk4" else 2
    expected_codes = [1, 2, 3, 4] if stages_per_step == 4 else [1, 5]
    recurrence_errors: list[float] = []
    for interval, (left, right) in enumerate(zip(saved_time, saved_time[1:])):
        h = float(right - left)
        offset = stages_per_step * interval
        powers = stage_power[offset:offset + stages_per_step]
        values = stage_work[offset:offset + stages_per_step]
        times = stage_time[offset:offset + stages_per_step]
        codes = case.arrays["stage_code"][offset:offset + stages_per_step].tolist()
        if codes != expected_codes:
            raise AdapterError("G06_METHOD_SPECIFIC_STAGE_CODE_INVALID")
        if stages_per_step == 4:
            expected_times = [float(left), float(left + 0.5 * h), float(left + 0.5 * h), float(right)]
            expected_values = [
                float(saved_work[interval]),
                float(saved_work[interval] + 0.5 * h * powers[0]),
                float(saved_work[interval] + 0.5 * h * powers[1]),
                float(saved_work[interval] + h * powers[2]),
            ]
            expected_next = float(saved_work[interval] + h * (powers[0] + 2.0 * powers[1] + 2.0 * powers[2] + powers[3]) / 6.0)
        else:
            expected_times = [float(left), float(left + 0.5 * h)]
            expected_values = [float(saved_work[interval]), float(saved_work[interval] + 0.5 * h * powers[0])]
            expected_next = float(saved_work[interval] + h * powers[1])
        recurrence_errors.extend(abs(float(a) - b) for a, b in zip(times, expected_times))
        recurrence_errors.extend(abs(float(a) - b) for a, b in zip(values, expected_values))
        recurrence_errors.append(abs(float(saved_work[interval + 1]) - expected_next))
    recurrence_max = max(recurrence_errors, default=math.inf)
    residual = (kinetic - kinetic[0]) - (saved_work - saved_work[0])
    residual_max = float(np.max(np.abs(residual)))
    residual_reported_error = float(np.max(np.abs(np.abs(residual) - case.arrays["energy_minus_work_residual_J"])))
    evidence = {
        "schema": "SIM13_V4B4G_R2_G06_ACTUAL_DT_RAW_STAGE_EVIDENCE_V1",
        "case_id": case.sidecar["case_id"],
        "method": case.sidecar["method"],
        "nominal_max_step_s": case.sidecar["step_s"],
        "actual_interval_s": np.diff(saved_time).tolist(),
        "stage_codes": case.arrays["stage_code"].tolist(),
        "stage_times_s": stage_time.tolist(),
        "stage_power_reported_W": stage_reported_power.tolist(),
        "stage_power_recomputed_W": stage_power.tolist(),
        "stage_augmented_W_act_J": stage_work.tolist(),
        "raw_binding": case.raw_binding(),
    }
    report = {
        "rule_id": "B4G_R2_G06_ENERGY_MINUS_WORK_ACTUAL_FINAL_DT_V1",
        "stage_evidence_sha256": canonical_sha256(evidence),
        "residual_J": residual.tolist(),
        "active_max_abs_residual_J": residual_max,
        "active_max_abs_limit_J": 1e-7,
        "stage_power_max_abs_error_W": power_error,
        "stage_power_limit_W": 1e-14,
        "stage_work_recurrence_max_abs_error_J": recurrence_max,
        "stage_work_recurrence_limit_J": 1e-14,
        "raw_energy_minus_work_residual_max_abs_crosscheck_error_J": residual_reported_error,
        "raw_energy_minus_work_residual_crosscheck_limit_J": 1e-12,
        "last_interval_s": float(saved_time[-1] - saved_time[-2]),
        "nominal_max_step_s": case.sidecar["step_s"],
        "only_final_interval_may_be_fractional": True,
        "all_terms_finite": bool(np.all(np.isfinite(residual)) and np.all(np.isfinite(stage_power))),
        "independent_work_state_provenance_pass": bool(recurrence_max <= 1e-14),
        "scientific_predicate": bool(
            residual_max <= 1e-7 and power_error <= 1e-14 and recurrence_max <= 1e-14
            and residual_reported_error <= 1e-12
        ),
    }
    return report, evidence


def evaluate_fresh_alpha16_raw(case: BoundRawCase) -> dict[str, Any]:
    if (
        case.sidecar["execution_family"] != "FRESH"
        or FRESH_ALPHA16_ROLE not in case.sidecar["registered_roles"]
        or case.sidecar["alpha"] != 16.0
    ):
        return {"passed": False, "status": "HOLD_FRESH_ALPHA16_EXACT_RAW_ROLE_REQUIRED"}
    if case.sidecar["outcome"] not in {OUTCOME_FINITE, OUTCOME_NO_REMOVAL}:
        return {
            "passed": False,
            "status": "HOLD_FRESH_ALPHA16_FINITE_OR_NO_REMOVAL_RAW_REQUIRED",
            "raw_binding": case.raw_binding(),
        }
    try:
        modules = load_production_modules()
        work_energy = modules["work_energy"]
        finite_removal = case.sidecar["outcome"] == OUTCOME_FINITE
        g04_inputs = {
            "time_s": case.arrays["time_s"].tolist(),
            "command_Q_14": case.arrays["command_Q_14"].tolist(),
            "service_state_29": case.arrays["service_state_29"].tolist(),
            "sample_power_reported_W": case.arrays["sample_power_reported_W"].tolist(),
            "stage_command_Q_14": case.arrays["stage_command_Q_14"].tolist(),
            "stage_service_state_29": case.arrays["stage_service_state_29"].tolist(),
            "stage_power_reported_W": case.arrays["stage_power_W"].tolist(),
            "W_act_J": case.arrays["signed_W_act_J"].tolist(),
            "finite_removal_present": finite_removal,
            "post_W_act_J": case.arrays["post_signed_W_act_J"].tolist(),
            "post_actuator_work_reset_on_removal": False,
            "post_generalized_force_Q_14": case.arrays["post_command_Q_14"].tolist(),
        }
        g04 = work_energy.evaluate_g04(**g04_inputs)
        g06, stage_evidence = _evaluate_g06_actual_dt(case)
    except (AdapterError, ProductionAPIError, KeyError, TypeError, ValueError) as exc:
        return {"passed": False, "status": f"HOLD_FRESH_ALPHA16_RAW_RECOMPUTATION_REJECTED:{type(exc).__name__}"}
    g04_g06_subpredicates = bool(g04["scientific_predicate"] and g06["scientific_predicate"])
    return {
        "passed": False,
        "status": "HOLD_FRESH_ALPHA16_FULL_RAW_INTEGRITY_BACKEND_NOT_IMPLEMENTED_SOURCE_FREEZE",
        "source_only_candidate_predicate_pass": False,
        "g04_g06_raw_subpredicates_pass": g04_g06_subpredicates,
        "full_raw_integrity_recomputed": False,
        "full_raw_integrity_hold_reason": "G03_G05_G07_G08_G09_G10_G11_G16_EXACT_BACKEND_NOT_IMPLEMENTED",
        "r2_runtime_trajectory_evaluated": False,
        "raw_recomputation_completed": True,
        "finite_removal_present": finite_removal,
        "raw_binding": case.raw_binding(),
        "g04_inputs_sha256": canonical_sha256(g04_inputs),
        "g06_stage_evidence_sha256": canonical_sha256(stage_evidence),
        "g04": g04,
        "g06": g06,
    }


def evaluate_fresh_acquisition_raw_triplet(cases: list[BoundRawCase]) -> dict[str, Any]:
    if type(cases) is not list or len(cases) != 3:
        return {"passed": False, "status": "HOLD_EXACT_THREE_FRESH_RAW_CASES_REQUIRED"}
    try:
        observations = [derive_fresh_acquisition_observation(case) for case in cases]
        ordered = sorted(zip(cases, observations), key=lambda pair: pair[0].sidecar["step_s"], reverse=True)
        methods = {case.sidecar["method"] for case, _ in ordered}
        alphas = {case.sidecar["alpha"] for case, _ in ordered}
        durations = {case.sidecar["command_duration_s"] for case, _ in ordered}
        if (
            [case.sidecar["step_s"] for case, _ in ordered] != list(FROZEN_LANE_STEPS_S)
            or len(methods) != 1 or alphas != {16.0} or durations != {0.01}
            or any(FRESH_ACQ_ROLE not in case.sidecar["registered_roles"] for case, _ in ordered)
            or len({case.sidecar["case_id"] for case, _ in ordered}) != 3
            or len({case.sidecar["schedule_index"] for case, _ in ordered}) != 3
            or len({case.npz_relative_path for case, _ in ordered}) != 3
            or len({case.npz_sha256 for case, _ in ordered}) != 3
        ):
            raise AdapterError("FRESH_RAW_TRIPLET_LEVEL_BINDING_INVALID")
        evaluator = load_production_modules()["evaluator"]
        result = evaluator.evaluate_fresh_acquisition_triplet(
            tuple(obs["acquisition_time_s"] for _, obs in ordered),
            {name: tuple(obs["channels"][name] for _, obs in ordered) for name in observations[0]["channels"]},
        )
    except (AdapterError, ProductionAPIError, KeyError, TypeError, ValueError):
        return {"passed": False, "status": "HOLD_FRESH_ACQUISITION_RAW_TRIPLET_REJECTED"}
    candidate = bool(result.get("passed"))
    result["source_only_candidate_predicate_pass"] = candidate
    result["passed"] = False
    result["status"] = "HOLD_FRESH_ACQUISITION_SOURCE_FREEZE_NO_R2_NUMERICAL_EXECUTION_CREDIT"
    result["r2_runtime_trajectory_evaluated"] = False
    result["raw_triplet_binding_evaluable"] = True
    result["raw_bindings"] = [case.raw_binding() for case, _ in ordered]
    return result


def evaluate_common_propagation_raw_triplet(cases: list[BoundRawCase]) -> dict[str, Any]:
    if type(cases) is not list or len(cases) != 3:
        return {"passed": False, "status": "HOLD_EXACT_THREE_COMMON_RAW_CASES_REQUIRED"}
    try:
        observations = [derive_common_propagation_observation(case) for case in cases]
        ordered = sorted(zip(cases, observations), key=lambda pair: pair[0].sidecar["step_s"], reverse=True)
        methods = {case.sidecar["method"] for case, _ in ordered}
        durations = {case.sidecar["command_duration_s"] for case, _ in ordered}
        if (
            [case.sidecar["step_s"] for case, _ in ordered] != list(FROZEN_LANE_STEPS_S)
            or len(methods) != 1 or len(durations) != 1
            or any(case.sidecar["alpha"] != 16.0 or COMMON_ROLE not in case.sidecar["registered_roles"] for case, _ in ordered)
            or len({case.sidecar["case_id"] for case, _ in ordered}) != 3
            or len({case.sidecar["schedule_index"] for case, _ in ordered}) != 3
            or len({case.npz_relative_path for case, _ in ordered}) != 3
            or len({case.npz_sha256 for case, _ in ordered}) != 3
        ):
            raise AdapterError("COMMON_RAW_TRIPLET_LEVEL_BINDING_INVALID")
        evaluator = load_production_modules()["evaluator"]
        result = evaluator.evaluate_common_propagation_triplet(
            next(iter(methods)),
            {name: tuple(obs["channels"][name] for _, obs in ordered) for name in observations[0]["channels"]},
            time_grids_s=tuple(obs["time_grid_s"] for _, obs in ordered),
            command_duration_s=next(iter(durations)),
        )
    except (AdapterError, ProductionAPIError, KeyError, TypeError, ValueError):
        return {"passed": False, "status": "HOLD_COMMON_PROPAGATION_RAW_TRIPLET_REJECTED"}
    candidate = bool(result.get("passed"))
    result["source_only_candidate_predicate_pass"] = candidate
    result["passed"] = False
    result["status"] = "HOLD_COMMON_PROPAGATION_SOURCE_FREEZE_NO_R2_NUMERICAL_EXECUTION_CREDIT"
    result["r2_runtime_trajectory_evaluated"] = False
    result["raw_triplet_binding_evaluable"] = True
    result["raw_bindings"] = [case.raw_binding() for case, _ in ordered]
    return result


def evaluate_a0_bookend_raw(case: BoundRawCase) -> dict[str, Any]:
    if case.sidecar["outcome"] != OUTCOME_A0 or A0_ROLE not in case.sidecar["registered_roles"]:
        return {"passed": False, "status": "HOLD_A0_EXACT_BOOKEND_RAW_ROLE_REQUIRED"}
    arrays = case.arrays
    predicate = bool(
        np.all(arrays["command_Q_14"] == 0.0)
        and np.all(arrays["sample_power_reported_W"] == 0.0)
        and np.all(arrays["signed_W_act_J"] == 0.0)
        and np.all(arrays["stage_command_Q_14"] == 0.0)
        and np.all(arrays["stage_power_W"] == 0.0)
        and np.all(arrays["stage_augmented_W_act_J"] == 0.0)
        and np.all(arrays["contact_force_N"] == 0.0)
        and np.all(arrays["contact_torque_N_m"] == 0.0)
        and int(arrays["acquisition_event_count"].item()) == 0
        and int(arrays["bilateral_removal_event_count"].item()) == 0
    )
    projection_sha256 = _numeric_payload_sha256(arrays)
    return {
        "passed": False,
        "status": "HOLD_A0_BOOKEND_SOURCE_FREEZE_NO_R2_NUMERICAL_EXECUTION_CREDIT",
        "source_only_candidate_predicate_pass": predicate,
        "sentinel": case.sidecar["bookend_sentinel"],
        "projection_sha256": projection_sha256,
        "projection_rule": "ALL_EXACT_NPZ_ARRAYS_NAME_DTYPE_SHAPE_AND_C_BYTES_V1",
        "raw_binding": case.raw_binding(),
        "r2_runtime_trajectory_evaluated": False,
    }


def evaluate_a0_bookend_pair(pre: BoundRawCase, post: BoundRawCase) -> dict[str, Any]:
    left = evaluate_a0_bookend_raw(pre)
    right = evaluate_a0_bookend_raw(post)
    binding = bool(
        pre.sidecar["bookend_sentinel"] == "PRE"
        and post.sidecar["bookend_sentinel"] == "POST"
        and pre.sidecar["lane_id"] == post.sidecar["lane_id"]
        and pre.sidecar["method"] == post.sidecar["method"]
        and pre.sidecar["step_s"] == post.sidecar["step_s"]
        and pre.npz_relative_path != post.npz_relative_path
    )
    candidate = bool(
        binding
        and left.get("source_only_candidate_predicate_pass") is True
        and right.get("source_only_candidate_predicate_pass") is True
        and left.get("projection_sha256") == right.get("projection_sha256")
    )
    return {
        "passed": False,
        "status": "HOLD_A0_BOOKEND_PAIR_SOURCE_FREEZE_NO_R2_NUMERICAL_EXECUTION_CREDIT",
        "raw_pair_binding_evaluable": binding,
        "source_only_candidate_predicate_pass": candidate,
        "lane_id": pre.sidecar["lane_id"],
        "pre": left,
        "post": right,
        "r2_runtime_trajectory_evaluated": False,
    }


def _raw_clearance_record(case: BoundRawCase) -> dict[str, Any]:
    acquisition = int(case.arrays["acquisition_event_sample_index"][0])
    record: dict[str, Any] = {
        "case_id": case.sidecar["case_id"],
        "outcome": case.sidecar["outcome"],
        "acquisition_index": acquisition,
        "acquisition_time_s": float(case.arrays["time_s"][acquisition]),
        "raw_binding": case.raw_binding(),
        "full_raw_integrity_recomputed": False,
        "full_raw_integrity_hold_reason": "G03_G05_G07_G08_G09_G10_G11_G16_EXACT_BACKEND_NOT_IMPLEMENTED",
    }
    if case.sidecar["outcome"] == OUTCOME_FINITE:
        removal = int(case.arrays["bilateral_removal_active_sample_index"][0])
        terminal_work = float(case.arrays["signed_W_act_J"][removal])
        post_time = case.arrays["post_time_s"]
        post_service = case.arrays["post_service_state_29"]
        post_target = case.arrays["post_target_state_13"]
        post_linear = case.arrays["post_total_linear_momentum_N_s"]
        post_angular = case.arrays["post_total_angular_momentum_N_m_s"]
        post_energy = case.arrays["post_total_kinetic_energy_J"]
        duration = float(post_time[-1] - post_time[0])
        linear_drift = float(np.max(np.linalg.norm(post_linear - post_linear[0], axis=1)))
        angular_drift = float(np.max(np.linalg.norm(post_angular - post_angular[0], axis=1)))
        energy_drift = float(np.max(np.abs(post_energy - post_energy[0])))
        def hermite_minimum(values: np.ndarray, rates: np.ndarray, times: np.ndarray) -> float:
            minimum = math.inf
            for y0, y1, m0, m1, t0, t1 in zip(values, values[1:], rates, rates[1:], times, times[1:]):
                h = float(t1 - t0)
                # p(x)=a*x^3+b*x^2+c*x+d, x in [0,1]
                a = 2.0 * float(y0) - 2.0 * float(y1) + h * (float(m0) + float(m1))
                b = -3.0 * float(y0) + 3.0 * float(y1) - h * (2.0 * float(m0) + float(m1))
                c = h * float(m0)
                candidates = [0.0, 1.0]
                discriminant = 4.0 * b * b - 12.0 * a * c
                if abs(a) <= 1e-30:
                    if abs(b) > 1e-30:
                        candidates.append(-c / (2.0 * b))
                elif discriminant >= 0.0:
                    root = math.sqrt(discriminant)
                    candidates.extend(((-2.0 * b + root) / (6.0 * a), (-2.0 * b - root) / (6.0 * a)))
                for x in candidates:
                    if 0.0 <= x <= 1.0:
                        minimum = min(minimum, ((a * x + b) * x + c) * x + float(y0))
            return minimum

        active_service = case.arrays["service_state_29"][removal]
        active_target = case.arrays["target_state_13"][removal]
        active_linear = case.arrays["total_linear_momentum_N_s"][removal]
        active_angular = case.arrays["total_angular_momentum_N_m_s"][removal]
        active_energy = case.arrays["total_kinetic_energy_J"][removal]
        zero_jump = bool(
            np.array_equal(post_service[0], active_service)
            and np.array_equal(post_target[0], active_target)
            and np.array_equal(post_linear[0], active_linear)
            and np.array_equal(post_angular[0], active_angular)
            and float(post_energy[0]) == float(active_energy)
            and float(case.arrays["post_left_gap_m"][0]) == float(case.arrays["left_gap_m"][removal])
            and float(case.arrays["post_right_gap_m"][0]) == float(case.arrays["right_gap_m"][removal])
            and float(case.arrays["post_left_gap_rate_m_s"][0]) == float(case.arrays["left_gap_rate_m_s"][removal])
            and float(case.arrays["post_right_gap_rate_m_s"][0]) == float(case.arrays["right_gap_rate_m_s"][removal])
        )
        left_min = hermite_minimum(case.arrays["post_left_gap_m"], case.arrays["post_left_gap_rate_m_s"], post_time)
        right_min = hermite_minimum(case.arrays["post_right_gap_m"], case.arrays["post_right_gap_rate_m_s"], post_time)
        centered_step_m = 1.0e-7
        post_stage_stored_geometry_subset = bool(
            case.arrays["post_stage_time_s"].size > 0
            and np.all(case.arrays["post_stage_domain_and_sign_pass"])
            and np.all(case.arrays["post_stage_P_coordinates_m"] - centered_step_m >= 0.0)
            and np.all(case.arrays["post_stage_P_coordinates_m"] + centered_step_m <= 0.0715)
            and np.all(case.arrays["post_stage_gap_jacobian_P"][:, 0, 0] > 0.0)
            and np.all(case.arrays["post_stage_gap_jacobian_P"][:, 1, 1] > 0.0)
            and np.array_equal(
                case.arrays["post_stage_P_coordinates_m"],
                case.arrays["post_stage_service_state_29"][:, 13:15],
            )
        )
        def unit_quaternion_rows(values: np.ndarray) -> bool:
            return bool(
                values.ndim == 2 and values.shape[1] == 4
                and np.all(np.abs(np.linalg.norm(values, axis=1) - 1.0) <= 1.0e-12)
            )

        subset_predicates = {
            "exact_5ms_registered_saved_grid": bool(
                post_time.size >= 2
                and float(post_time[-1]) == float(post_time[0] + POST_RELEASE_WINDOW_S)
                and np.array_equal(
                post_time,
                post_time[0] + np.arange(post_time.size, dtype="<f8") * case.sidecar["step_s"],
                )
                and np.all(np.diff(post_time) > 0.0)
            ),
            "contact_force_torque_within_1e_12": bool(
                np.all(np.abs(case.arrays["post_contact_force_N"]) <= 1.0e-12)
                and np.all(np.abs(case.arrays["post_contact_torque_N_m"]) <= 1.0e-12)
            ),
            "post_command_exact_zero": bool(np.all(case.arrays["post_command_Q_14"] == 0.0)),
            "signed_work_exact_terminal_carry": bool(np.all(case.arrays["post_signed_W_act_J"] == terminal_work)),
            "finite_state_and_unit_quaternions": bool(
                np.all(np.isfinite(post_service)) and np.all(np.isfinite(post_target))
                and unit_quaternion_rows(post_service[:, 3:7])
                and unit_quaternion_rows(post_target[:, 3:7])
                and unit_quaternion_rows(case.arrays["post_stage_service_state_29"][:, 3:7])
                and unit_quaternion_rows(case.arrays["post_stage_target_state_13"][:, 3:7])
            ),
            "saved_P_closed_domain": bool(
                np.all(post_service[:, 13:15] >= 0.0)
                and np.all(post_service[:, 13:15] <= 0.0715)
            ),
            "stored_stage_domain_P_and_opening_sign_subset": post_stage_stored_geometry_subset,
            "native_momentum_drift_within_1e_9": bool(linear_drift <= 1.0e-9 and angular_drift <= 1.0e-9),
            "native_energy_drift_within_1e_7": bool(energy_drift <= 1.0e-7),
            "exact_zero_jump_array_mapping": zero_jump,
            "continuous_gap_at_least_1e_6": bool(left_min >= 1.0e-6 and right_min >= 1.0e-6),
            "saved_gap_rate_at_least_minus_1e_6": bool(
                np.all(case.arrays["post_left_gap_rate_m_s"] >= -1.0e-6)
                and np.all(case.arrays["post_right_gap_rate_m_s"] >= -1.0e-6)
            ),
        }
        post_raw_subset_pass = all(subset_predicates.values())
        record.update({
            "removal_index": removal,
            "removal_time_s": float(case.arrays["time_s"][removal]),
            "signed_work_terminal_J": terminal_work,
            "post_raw_subset_pass": post_raw_subset_pass,
            "partial_post_checks_pass": post_raw_subset_pass,
            "full_post_release_predicate_recomputed": False,
            "post_raw_subset_predicates": subset_predicates,
            "post_release_duration_s": duration,
            "post_linear_momentum_max_drift_N_s": linear_drift,
            "post_angular_momentum_max_drift_N_m_s": angular_drift,
            "post_energy_max_drift_J": energy_drift,
            "exact_zero_jump_mapping": zero_jump,
            "post_stage_stored_geometry_subset_pass": post_stage_stored_geometry_subset,
            "centered_sign_step_m": centered_step_m,
            "post_left_gap_hermite_minimum_m": left_min,
            "post_right_gap_hermite_minimum_m": right_min,
        })
    else:
        horizon = float(case.arrays["time_s"][-1] - case.arrays["time_s"][acquisition])
        record.update({
            "saved_no_removal_horizon_s": horizon,
            "saved_no_removal_complete_80ms": float(case.arrays["time_s"][-1]) == float(case.arrays["time_s"][acquisition] + NO_REMOVAL_SAVED_HORIZON_S),
            "post_raw_subset_pass": False,
            "partial_post_checks_pass": False,
            "full_post_release_predicate_recomputed": False,
        })
    record["raw_derived_certificate_sha256"] = canonical_sha256(record)
    return record


def evaluate_g12_raw_pair(rk4: BoundRawCase | None, midpoint: BoundRawCase | None) -> dict[str, Any]:
    base = {
        "passed": False,
        "scientific_predicate": False,
        "eligible": False,
        "r2_runtime_trajectory_evaluated": False,
    }
    if rk4 is None or midpoint is None:
        return {**base, "evaluation_status": "HOLD_G12_MISSING_RAW_CASE"}
    if (
        G12_ROLE not in rk4.sidecar["registered_roles"]
        or G12_ROLE not in midpoint.sidecar["registered_roles"]
        or rk4.sidecar["method"] != "rk4" or midpoint.sidecar["method"] != "midpoint"
        or rk4.sidecar["lane_id"] != "RK4_H_MS_0P0625"
        or midpoint.sidecar["lane_id"] != "MIDPOINT_H_MS_0P0625"
        or rk4.sidecar["step_s"] != 0.0000625 or midpoint.sidecar["step_s"] != 0.0000625
        or rk4.sidecar["alpha"] != midpoint.sidecar["alpha"]
        or rk4.sidecar["command_duration_s"] != midpoint.sidecar["command_duration_s"]
        or rk4.sidecar["case_id"] == midpoint.sidecar["case_id"]
        or rk4.npz_relative_path == midpoint.npz_relative_path
        or rk4.npz_sha256 == midpoint.npz_sha256
    ):
        return {**base, "evaluation_status": "HOLD_G12_REGISTERED_RAW_PAIR_BINDING_INVALID"}
    left = _raw_clearance_record(rk4)
    right = _raw_clearance_record(midpoint)
    if left["outcome"] == OUTCOME_NO_REMOVAL and right["outcome"] == OUTCOME_NO_REMOVAL:
        if (
            left.get("saved_no_removal_complete_80ms") is not True
            or right.get("saved_no_removal_complete_80ms") is not True
        ):
            return {
                **base,
                "evaluation_status": "FAIL_G12_BOTH_NO_EVENT_INCOMPLETE_80MS_HORIZON",
                "applicability": "FAIL",
                "raw_pair_binding_evaluable": True,
                "rk4": left,
                "midpoint": right,
            }
        return {
            **base,
            "evaluation_status": "NOT_APPLICABLE_G12_BOTH_RAW_VERIFIED_NO_EVENT_SAME_HORIZON",
            "applicability": "NOT_APPLICABLE",
            "both_raw_verified_same_horizon": True,
            "raw_pair_binding_evaluable": True,
            "full_raw_integrity_recomputed": False,
            "rk4": left,
            "midpoint": right,
        }
    if left["outcome"] != OUTCOME_FINITE or right["outcome"] != OUTCOME_FINITE:
        return {
            **base,
            "evaluation_status": "FAIL_G12_ONE_SIDE_FINITE_ONE_SIDE_NO_EVENT",
            "applicability": "FAIL",
            "raw_pair_binding_evaluable": True,
            "full_raw_integrity_recomputed": False,
            "rk4": left,
            "midpoint": right,
        }
    acq_difference = abs(left["acquisition_time_s"] - right["acquisition_time_s"])
    removal_difference = abs(left["removal_time_s"] - right["removal_time_s"])
    work_difference = abs(left["signed_work_terminal_J"] - right["signed_work_terminal_J"])
    work_tolerance = max(1e-10, 0.001 * max(abs(left["signed_work_terminal_J"]), abs(right["signed_work_terminal_J"])))
    raw_pair_subpredicates = {
        "rk4_partial_post_checks_pass": left["post_raw_subset_pass"] is True,
        "midpoint_partial_post_checks_pass": right["post_raw_subset_pass"] is True,
        "acquisition_time_difference_within_0p25ms": acq_difference <= 0.00025,
        "removal_time_difference_within_0p25ms": removal_difference <= 0.00025,
        "signed_work_difference_within_registered_tolerance": work_difference <= work_tolerance,
    }
    partial_post_checks_pass = all(raw_pair_subpredicates.values())
    return {
        **base,
        "evaluation_status": "HOLD_G12_FULL_RAW_INTEGRITY_BACKEND_NOT_IMPLEMENTED_SOURCE_FREEZE",
        "applicability": "RAW_DERIVED_SUBPREDICATES_ONLY",
        "source_only_candidate_predicate_pass": False,
        "partial_post_checks_pass": partial_post_checks_pass,
        "raw_pair_subpredicates": raw_pair_subpredicates,
        "raw_pair_binding_evaluable": True,
        "full_raw_integrity_recomputed": False,
        "acquisition_time_difference_s": acq_difference,
        "removal_time_difference_s": removal_difference,
        "signed_work_difference_J": work_difference,
        "signed_work_tolerance_J": work_tolerance,
        "rk4": left,
        "midpoint": right,
    }


def aggregate_g12_raw(cases: list[BoundRawCase]) -> dict[str, Any]:
    """Internally form the frozen 18 reference pairs from 36 unique raw cases."""

    base = {
        "passed": False,
        "aggregate_pass": False,
        "eligible_count": 0,
        "recommend_A2_including_campaign_review": False,
        "full_campaign_authorized": False,
        "r2_runtime_trajectory_evaluated": False,
    }
    if type(cases) is not list or len(cases) != 36:
        return {**base, "status": "HOLD_G12_EXACT_THIRTY_SIX_RAW_CASES_REQUIRED"}
    alphas = (0.5, 1.0, 2.0, 4.0, 8.0, 16.0)
    durations = (0.005, 0.01, 0.02)
    expected = {(method, alpha, duration) for method in ("rk4", "midpoint") for alpha in alphas for duration in durations}
    keys = [(case.sidecar["method"], case.sidecar["alpha"], case.sidecar["command_duration_s"]) for case in cases]
    raw_certificates = [canonical_sha256(_raw_clearance_record(case)) for case in cases]
    numeric_payload_sha256 = [_numeric_payload_sha256(case.arrays) for case in cases]
    if (
        set(keys) != expected or len(keys) != len(set(keys))
        or any(G12_ROLE not in case.sidecar["registered_roles"] for case in cases)
        or any(case.sidecar["step_s"] != 0.0000625 for case in cases)
        or len({case.sidecar["case_id"] for case in cases}) != 36
        or len({case.npz_relative_path for case in cases}) != 36
        or len({case.npz_sha256 for case in cases}) != 36
        or len(set(raw_certificates)) != 36
        or len(set(numeric_payload_sha256)) != 36
    ):
        return {**base, "status": "HOLD_G12_FROZEN_LEVEL_ROLE_OR_UNIQUE_RAW_BINDING_INVALID"}
    lookup = {key: case for key, case in zip(keys, cases)}
    pairs = [
        evaluate_g12_raw_pair(lookup[("rk4", alpha, duration)], lookup[("midpoint", alpha, duration)])
        for alpha in alphas for duration in durations
    ]
    raw_registry_structurally_valid = all(pair.get("raw_pair_binding_evaluable") is True for pair in pairs)
    raw_pair_outcomes_valid = all(
        pair.get("evaluation_status") in {
            "HOLD_G12_FULL_RAW_INTEGRITY_BACKEND_NOT_IMPLEMENTED_SOURCE_FREEZE",
            "NOT_APPLICABLE_G12_BOTH_RAW_VERIFIED_NO_EVENT_SAME_HORIZON",
        }
        for pair in pairs
    )
    source_registry_valid = bool(raw_registry_structurally_valid and raw_pair_outcomes_valid)
    return {
        **base,
        "status": (
            "HOLD_G12_RAW_REGISTRY_SOURCE_ONLY_VALID_NO_EXECUTION_CREDIT"
            if source_registry_valid else "FAIL_G12_RAW_PAIR_EVALUATION"
        ),
        "source_only_registry_valid": source_registry_valid,
        "raw_registry_structurally_valid": raw_registry_structurally_valid,
        "raw_pair_outcomes_valid": raw_pair_outcomes_valid,
        "full_raw_integrity_recomputed": False,
        "source_only_candidate_predicate_pass": False,
        "pair_count": len(pairs),
        "numeric_payload_unique_count": len(set(numeric_payload_sha256)),
        "pairs": pairs,
    }


def validate_raw_registry_structure(cases: list[BoundRawCase]) -> dict[str, Any]:
    """Fail closed over the full frozen 78-case raw registry."""

    if type(cases) is not list or len(cases) != 78:
        return {"passed": False, "status": "HOLD_EXACT_78_BOUND_RAW_CASES_REQUIRED", "case_count": len(cases) if isinstance(cases, list) else 0}
    rows, order = schedule_records()
    expected_ids = {row["case_id"] for row in rows}
    observed_ids = [case.sidecar["case_id"] for case in cases]
    if (
        set(observed_ids) != expected_ids or len(set(observed_ids)) != 78
        or observed_ids != order
        or any(case.sidecar["schedule_index"] != position for position, case in enumerate(cases))
        or len({case.npz_relative_path for case in cases}) != 78
    ):
        return {"passed": False, "status": "HOLD_78_CASE_SET_ORDER_OR_PATH_UNIQUENESS_INVALID", "case_count": 78}
    a0 = [case for case in cases if A0_ROLE in case.sidecar["registered_roles"]]
    common = [case for case in cases if COMMON_ROLE in case.sidecar["registered_roles"]]
    g12 = [case for case in cases if G12_ROLE in case.sidecar["registered_roles"]]
    alpha16 = [case for case in cases if FRESH_ALPHA16_ROLE in case.sidecar["registered_roles"]]
    fresh_acq = [case for case in cases if FRESH_ACQ_ROLE in case.sidecar["registered_roles"]]
    if len(a0) != 12 or len(common) != 18 or len(g12) != 36 or len(alpha16) != 18 or len(fresh_acq) != 6:
        return {"passed": False, "status": "HOLD_78_CASE_ROLE_CARDINALITY_INVALID", "case_count": 78}
    a0_pairs = []
    for lane in sorted({case.sidecar["lane_id"] for case in a0}):
        lane_cases = {case.sidecar["bookend_sentinel"]: case for case in a0 if case.sidecar["lane_id"] == lane}
        if set(lane_cases) != {"PRE", "POST"}:
            return {"passed": False, "status": "HOLD_A0_BOOKEND_PAIR_MISSING", "case_count": 78}
        a0_pairs.append(evaluate_a0_bookend_pair(lane_cases["PRE"], lane_cases["POST"]))
    fresh_triplets = {
        method: evaluate_fresh_acquisition_raw_triplet(
            [case for case in fresh_acq if case.sidecar["method"] == method]
        )
        for method in ("rk4", "midpoint")
    }
    common_triplets = {
        f"{method}__{int(round(duration * 1000.0))}ms": evaluate_common_propagation_raw_triplet(
            [
                case for case in common
                if case.sidecar["method"] == method and case.sidecar["command_duration_s"] == duration
            ]
        )
        for method in ("rk4", "midpoint")
        for duration in (0.005, 0.01, 0.02)
    }
    common_initial_projection_hashes = {
        derive_common_propagation_observation(case)["common_donor_binding"]["raw_initial_projection_sha256"]
        for case in common
    }
    common_donor_binding_pass = bool(
        len(common_initial_projection_hashes) == 1
        and all(case.sidecar["common_donor_certificate_sha256"] == DONOR_PAYLOAD_SHA256 for case in common)
        and all(case.sidecar["common_state_group_sha256"] == COMMON_GROUP_SHA256 for case in common)
        and all(
            dict(case.sidecar["common_donor_hashes_before"]) == COMMON_DONOR_HASHES
            and dict(case.sidecar["common_donor_hashes_after"]) == COMMON_DONOR_HASHES
            for case in common
        )
    )
    alpha16_results = [evaluate_fresh_alpha16_raw(case) for case in alpha16]
    g12_result = aggregate_g12_raw(g12)
    structure = bool(
        all(
            pair.get("raw_pair_binding_evaluable") is True
            and pair.get("source_only_candidate_predicate_pass") is True
            for pair in a0_pairs
        )
        and all(result.get("raw_triplet_binding_evaluable") is True for result in fresh_triplets.values())
        and all(result.get("raw_triplet_binding_evaluable") is True for result in common_triplets.values())
        and common_donor_binding_pass
        and all(result.get("raw_recomputation_completed") is True for result in alpha16_results)
        and g12_result.get("source_only_registry_valid") is True
    )
    return {
        "passed": False,
        "status": "HOLD_78_RAW_REGISTRY_SOURCE_ONLY_VALID_NO_EXECUTION_CREDIT" if structure else "FAIL_78_RAW_REGISTRY_STRUCTURE",
        "source_only_registry_valid": structure,
        "case_count": 78,
        "a0_pair_count": len(a0_pairs),
        "fresh_acquisition_triplet_count": len(fresh_triplets),
        "common_count": len(common),
        "common_triplet_count": len(common_triplets),
        "common_donor_binding_pass": common_donor_binding_pass,
        "common_donor_certificate_sha256": DONOR_PAYLOAD_SHA256,
        "common_state_group_sha256": COMMON_GROUP_SHA256,
        "fresh_alpha16_raw_interface_count": len(alpha16_results),
        "g12_reference_count": len(g12),
        "g12_pair_count": g12_result.get("pair_count", 0),
        "a0_pairs": a0_pairs,
        "fresh_acquisition_triplets": fresh_triplets,
        "common_triplets": common_triplets,
        "fresh_alpha16_raw_results": alpha16_results,
        "g12": g12_result,
        "trajectory_count": 0,
        "r2_numerical_preflight_executed": False,
    }


__all__ = [
    "AdapterError", "BoundRawCase", "derive_common_propagation_observation",
    "derive_fresh_acquisition_observation", "evaluate_common_propagation_raw_triplet",
    "evaluate_a0_bookend_pair", "evaluate_a0_bookend_raw",
    "evaluate_fresh_acquisition_raw_triplet", "evaluate_fresh_alpha16_raw",
    "evaluate_g12_raw_pair", "aggregate_g12_raw", "load_bound_case", "validate_raw_registry_structure",
]
