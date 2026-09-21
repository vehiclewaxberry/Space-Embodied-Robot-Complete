"""Strict, solver-independent rehydration of the frozen B4E donor payload.

The dataclasses mirror the B4E public EventInput/AcquisitionResult boundary, but
this module deliberately does not import the historical implementation.  That
keeps source-freeze tests from accidentally executing physics code.
"""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path
from typing import Any, Iterator

import numpy as np

from .strict_json import canonical_bytes, canonical_sha256, file_sha256, iter_json_pointers, load_path


DONOR_RAW_BYTES = 69249
DONOR_RAW_SHA256 = "5DF0C19A71180E1BD91816235AAD50108613C2BC0F99F950018D786119CF9D4F"
DONOR_PAYLOAD_BYTES = 31092
DONOR_PAYLOAD_SHA256 = "DA3E10D7D30DFD9BABFB71BF055D62A1BD06CF8DE3023E463A649FF92A952D15"
COMMON_GROUP_BYTES = 1317
COMMON_GROUP_SHA256 = "396A903DA584765FDA03B867F2F3F27B910CED9383D34BC5064A01B33D4F6444"

EVENT_KEYS = {
    "run_id", "method", "step_s", "index", "time_s", "source", "state_label", "criteria",
    "service", "target", "left_common_contact_point_m", "right_common_contact_point_m",
    "left_contact_potential_J", "right_contact_potential_J", "b3_dissipation_J",
}
ACQUISITION_KEYS = {
    "run_id", "acquisition_time_s", "snapshot", "reference_length_m", "z_minus",
    "z_plus_reduced", "z_plus_kkt", "z_plus_schur_audit", "eta_plus",
    "linear_impulse_N_s", "angular_impulse_N_m_s", "lambda_bar", "ranks", "metrics",
    "wrench_audit", "energy_audit", "momentum_audit", "backend_provenance", "matrices",
}
MATRIX_SHAPES = {
    "A": (6, 14), "D": (6, 6), "G_bar": (6, 6), "J_bar": (6, 20),
    "J_c": (6, 20), "J_hat": (6, 20), "L": (20, 14), "L_hat": (20, 14),
    "M_attached": (14, 14), "M_minus": (20, 20), "S_eta": (14, 14),
    "S_z": (20, 20), "W_bar": (6, 6),
}

CRITERIA_KEYS = {
    "action_reaction_error_n", "all_ledgers_closed", "angular_momentum_drift_n_m_s",
    "common_point_shift_error_n_m", "dissipation_monotonic_violation_j",
    "dual_contact_dwell_s", "energy_plus_dissipation_drift_j",
    "friction_positive_power_w", "index", "jaw_aperture_rate_m_s", "left_contact",
    "left_finger_rate_m_s", "left_normal_force_n", "left_relative_normal_speed_m_s",
    "left_relative_tangential_speed_m_s", "linear_momentum_drift_n_s", "normals_dot",
    "right_contact", "right_finger_rate_m_s", "right_normal_force_n",
    "right_relative_normal_speed_m_s", "right_relative_tangential_speed_m_s",
    "service_angular_impulse_identity_error_n_m_s",
    "service_linear_impulse_identity_error_n_s", "soft_capture_transient_qualifies",
    "target_angular_impulse_identity_error_n_m_s", "target_inside_corridor",
    "target_linear_impulse_identity_error_n_s", "target_relative_center_speed_m_s",
    "target_relative_omega_rad_s", "target_torque_identity_error_n_m", "time_s",
    "virtual_power_identity_error_w",
}
CRITERIA_BOOL_KEYS = {
    "all_ledgers_closed", "left_contact", "right_contact",
    "soft_capture_transient_qualifies", "target_inside_corridor",
}
METRICS_KEYS = {
    "Jhat_Lhat_operator_inf_dimensionless", "W_bar_scaled_condition_number",
    "W_bar_scaled_min_eigenvalue", "attached_mass_fixed_child_inf",
    "combined_impulse_equation_P_joint_N_s", "combined_impulse_equation_R_joint_N_m_s",
    "combined_impulse_equation_service_base_angular_N_m_s",
    "combined_impulse_equation_service_base_linear_N_s",
    "combined_impulse_equation_target_angular_N_m_s",
    "combined_impulse_equation_target_linear_N_s", "contact_potential_sum_identity_J",
    "kkt_original_contract_residual_inf", "post_constraint_angular_twist_rad_s",
    "post_constraint_linear_twist_m_s", "projection_energy_identity_J",
    "quaternion_unit_norm_error_abs", "reduced_kkt_P_joint_component_m_s",
    "reduced_kkt_R_joint_component_rad_s",
    "reduced_kkt_service_base_angular_component_rad_s",
    "reduced_kkt_service_base_linear_component_m_s",
    "reduced_kkt_target_angular_component_rad_s",
    "reduced_kkt_target_linear_component_m_s", "rotation_determinant_error_abs",
    "rotation_orthogonality_inf", "scaled_post_constraint_inf",
    "schur_kkt_velocity_inf_audit_only", "snapshot_rotation_geodesic_rad",
    "snapshot_translation_identity_m", "switch_energy_identity_J",
    "total_angular_momentum_jump_about_fixed_inertial_origin_N_m_s",
    "total_linear_momentum_jump_N_s",
}
WRENCH_KEYS = {
    "contact_chord_unit_vector", "normalized_rank5_unreachable_projection_N_s",
    "normalized_rank5_unreachable_projection_norm_N_s",
    "ordinary_axis_projected_angular_impulse_N_m_s", "rank5_contact_capability_attributed",
    "rank5_unreachable_chi_missing_N_m_s", "synthetic_sixth_constraint_attributed",
    "transverse_angular_impulse_N_m_s",
}
ENERGY_KEYS = {
    "D_B3_minus_J", "D_projection_J", "D_projection_schur_J", "D_switch_J",
    "T_minus_J", "T_plus_J", "U_contact_minus_J", "U_left_minus_J", "U_right_minus_J",
}
MOMENTUM_KEYS = {
    "expected_target_angular_jump_N_m_s", "expected_target_linear_jump_N_s",
    "service_angular_momentum_jump_N_m_s", "service_equivalent_wrench_about_palm_origin",
    "service_linear_momentum_jump_N_s", "target_angular_momentum_jump_N_m_s",
    "target_linear_momentum_jump_N_s",
}
BACKEND_KEYS = {
    "acquisition_pinv_or_lstsq", "direct_kkt", "pinv_whitelist", "reduced_spd",
    "schur_audit_only",
}


class RehydrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ServiceState:
    base_position_inertial_m: np.ndarray
    base_quaternion_body_to_inertial_wxyz: np.ndarray
    joint_coordinates_mixed: np.ndarray
    nu_s_mixed: np.ndarray


@dataclass(frozen=True)
class TargetState:
    position_inertial_m: np.ndarray
    quaternion_body_to_inertial_wxyz: np.ndarray
    twist_inertial_mixed: np.ndarray


@dataclass(frozen=True)
class SnapshotTransform:
    translation_palm_to_target_m: np.ndarray
    rotation_palm_to_target: np.ndarray
    acquisition_time_s: float


@dataclass(frozen=True)
class EventInput:
    run_id: str
    method: str
    step_s: float
    index: int
    time_s: float
    service: ServiceState
    target: TargetState
    left_common_contact_point_m: np.ndarray
    right_common_contact_point_m: np.ndarray
    left_contact_potential_j: float
    right_contact_potential_j: float
    b3_dissipation_j: float
    state_label: str
    criteria: dict[str, Any]
    source: str


@dataclass(frozen=True)
class AcquisitionResult:
    run_id: str
    acquisition_time_s: float
    snapshot: SnapshotTransform
    reference_length_m: float
    z_minus: np.ndarray
    z_plus_reduced: np.ndarray
    z_plus_kkt: np.ndarray
    z_plus_schur_audit: np.ndarray
    eta_plus: np.ndarray
    linear_impulse_n_s: np.ndarray
    angular_impulse_n_m_s: np.ndarray
    lambda_bar: np.ndarray
    matrices: dict[str, np.ndarray]
    ranks: dict[str, int]
    metrics: dict[str, float]
    wrench_audit: dict[str, Any]
    energy_audit: dict[str, float]
    momentum_audit: dict[str, Any]
    backend_provenance: dict[str, str]


@dataclass(frozen=True)
class RehydratedFixture:
    case_id: str
    lane_id: str
    event: EventInput
    acquisition: AcquisitionResult
    declared_certificate_sha256: str
    source_pointer_count: int

    @property
    def service_initial_state(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Configuration from event; post-acquisition velocity only from z_plus."""

        return (
            self.event.service.base_position_inertial_m.copy(),
            self.event.service.base_quaternion_body_to_inertial_wxyz.copy(),
            self.event.service.joint_coordinates_mixed.copy(),
            self.acquisition.z_plus_reduced[:14].copy(),
        )

    @property
    def target_initial_state(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        return (
            self.event.target.position_inertial_m.copy(),
            self.event.target.quaternion_body_to_inertial_wxyz.copy(),
            self.acquisition.z_plus_reduced[14:20].copy(),
        )


def _exact_keys(value: Any, expected: set[str], pointer: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise RehydrationError(f"EXACT_KEYS_REQUIRED:{pointer}:{actual}")
    return value


def _string(value: Any, pointer: str) -> str:
    if type(value) is not str:
        raise RehydrationError(f"STRING_REQUIRED:{pointer}")
    return value


def _float(value: Any, pointer: str) -> float:
    if type(value) is not float or not np.isfinite(value):
        raise RehydrationError(f"FINITE_JSON_FLOAT_REQUIRED:{pointer}")
    return value


def _int(value: Any, pointer: str) -> int:
    if type(value) is not int:
        raise RehydrationError(f"JSON_INT_REQUIRED:{pointer}")
    return value


def _all_float_leaves(value: Any) -> bool:
    if isinstance(value, list):
        return all(_all_float_leaves(item) for item in value)
    return type(value) is float and np.isfinite(value)


def _array(value: Any, shape: tuple[int, ...], pointer: str) -> np.ndarray:
    if not isinstance(value, list) or not _all_float_leaves(value):
        raise RehydrationError(f"JSON_FLOAT_ARRAY_REQUIRED:{pointer}")
    try:
        array = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise RehydrationError(f"ARRAY_SHAPE_OR_FINITE_MISMATCH:{pointer}:RAGGED:{shape}") from exc
    if array.shape != shape or not np.all(np.isfinite(array)):
        raise RehydrationError(f"ARRAY_SHAPE_OR_FINITE_MISMATCH:{pointer}:{array.shape}:{shape}")
    return array.copy()


def _json_object(value: Any, pointer: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RehydrationError(f"OBJECT_REQUIRED:{pointer}")
    return deepcopy(value)


def _exact_float_object(value: Any, expected: set[str], pointer: str) -> dict[str, float]:
    obj = _exact_keys(value, expected, pointer)
    return {key: _float(obj[key], f"{pointer}/{key}") for key in sorted(expected)}


def _criteria_from_json(value: Any) -> dict[str, Any]:
    pointer = "/event/criteria"
    obj = _exact_keys(value, CRITERIA_KEYS, pointer)
    result: dict[str, Any] = {}
    for key in sorted(CRITERIA_KEYS):
        item = obj[key]
        if key == "index":
            result[key] = _int(item, f"{pointer}/{key}")
        elif key in CRITERIA_BOOL_KEYS:
            if type(item) is not bool:
                raise RehydrationError(f"JSON_BOOL_REQUIRED:{pointer}/{key}")
            result[key] = item
        else:
            result[key] = _float(item, f"{pointer}/{key}")
    return result


def _wrench_from_json(value: Any) -> dict[str, Any]:
    pointer = "/acquisition/wrench_audit"
    obj = _exact_keys(value, WRENCH_KEYS, pointer)
    result: dict[str, Any] = {
        "contact_chord_unit_vector": _array(
            obj["contact_chord_unit_vector"], (3,), f"{pointer}/contact_chord_unit_vector"
        ).tolist(),
        "normalized_rank5_unreachable_projection_N_s": _array(
            obj["normalized_rank5_unreachable_projection_N_s"],
            (6,),
            f"{pointer}/normalized_rank5_unreachable_projection_N_s",
        ).tolist(),
        "transverse_angular_impulse_N_m_s": _array(
            obj["transverse_angular_impulse_N_m_s"],
            (3,),
            f"{pointer}/transverse_angular_impulse_N_m_s",
        ).tolist(),
    }
    for key in (
        "normalized_rank5_unreachable_projection_norm_N_s",
        "ordinary_axis_projected_angular_impulse_N_m_s",
        "rank5_unreachable_chi_missing_N_m_s",
    ):
        result[key] = _float(obj[key], f"{pointer}/{key}")
    for key in ("rank5_contact_capability_attributed", "synthetic_sixth_constraint_attributed"):
        if type(obj[key]) is not bool:
            raise RehydrationError(f"JSON_BOOL_REQUIRED:{pointer}/{key}")
        result[key] = obj[key]
    return result


def _momentum_from_json(value: Any) -> dict[str, Any]:
    pointer = "/acquisition/momentum_audit"
    obj = _exact_keys(value, MOMENTUM_KEYS, pointer)
    result: dict[str, Any] = {}
    for key in sorted(MOMENTUM_KEYS - {"service_equivalent_wrench_about_palm_origin"}):
        result[key] = _array(obj[key], (3,), f"{pointer}/{key}").tolist()
    nested_pointer = f"{pointer}/service_equivalent_wrench_about_palm_origin"
    nested = _exact_keys(
        obj["service_equivalent_wrench_about_palm_origin"],
        {"angular_impulse_N_m_s", "linear_impulse_N_s", "r_cross_p_count"},
        nested_pointer,
    )
    result["service_equivalent_wrench_about_palm_origin"] = {
        "angular_impulse_N_m_s": _array(
            nested["angular_impulse_N_m_s"], (3,), f"{nested_pointer}/angular_impulse_N_m_s"
        ).tolist(),
        "linear_impulse_N_s": _array(
            nested["linear_impulse_N_s"], (3,), f"{nested_pointer}/linear_impulse_N_s"
        ).tolist(),
        "r_cross_p_count": _int(nested["r_cross_p_count"], f"{nested_pointer}/r_cross_p_count"),
    }
    return result


def _backend_from_json(value: Any) -> dict[str, str]:
    pointer = "/acquisition/backend_provenance"
    obj = _exact_keys(value, BACKEND_KEYS, pointer)
    return {key: _string(obj[key], f"{pointer}/{key}") for key in sorted(BACKEND_KEYS)}


def _service_from_json(value: Any) -> ServiceState:
    obj = _exact_keys(value, {"base_position_inertial_m", "base_quaternion_body_to_inertial_wxyz", "joint_coordinates_mixed", "nu_s_mixed"}, "/event/service")
    return ServiceState(
        _array(obj["base_position_inertial_m"], (3,), "/event/service/base_position_inertial_m"),
        _array(obj["base_quaternion_body_to_inertial_wxyz"], (4,), "/event/service/base_quaternion_body_to_inertial_wxyz"),
        _array(obj["joint_coordinates_mixed"], (8,), "/event/service/joint_coordinates_mixed"),
        _array(obj["nu_s_mixed"], (14,), "/event/service/nu_s_mixed"),
    )


def _target_from_json(value: Any) -> TargetState:
    obj = _exact_keys(value, {"position_inertial_m", "quaternion_body_to_inertial_wxyz", "twist_inertial_mixed"}, "/event/target")
    return TargetState(
        _array(obj["position_inertial_m"], (3,), "/event/target/position_inertial_m"),
        _array(obj["quaternion_body_to_inertial_wxyz"], (4,), "/event/target/quaternion_body_to_inertial_wxyz"),
        _array(obj["twist_inertial_mixed"], (6,), "/event/target/twist_inertial_mixed"),
    )


def _event_from_json(value: Any) -> EventInput:
    obj = _exact_keys(value, EVENT_KEYS, "/event")
    return EventInput(
        run_id=_string(obj["run_id"], "/event/run_id"),
        method=_string(obj["method"], "/event/method"),
        step_s=_float(obj["step_s"], "/event/step_s"),
        index=_int(obj["index"], "/event/index"),
        time_s=_float(obj["time_s"], "/event/time_s"),
        service=_service_from_json(obj["service"]),
        target=_target_from_json(obj["target"]),
        left_common_contact_point_m=_array(obj["left_common_contact_point_m"], (3,), "/event/left_common_contact_point_m"),
        right_common_contact_point_m=_array(obj["right_common_contact_point_m"], (3,), "/event/right_common_contact_point_m"),
        left_contact_potential_j=_float(obj["left_contact_potential_J"], "/event/left_contact_potential_J"),
        right_contact_potential_j=_float(obj["right_contact_potential_J"], "/event/right_contact_potential_J"),
        b3_dissipation_j=_float(obj["b3_dissipation_J"], "/event/b3_dissipation_J"),
        state_label=_string(obj["state_label"], "/event/state_label"),
        criteria=_criteria_from_json(obj["criteria"]),
        source=_string(obj["source"], "/event/source"),
    )


def _acquisition_from_json(value: Any) -> AcquisitionResult:
    obj = _exact_keys(value, ACQUISITION_KEYS, "/acquisition")
    acquisition_time = _float(obj["acquisition_time_s"], "/acquisition/acquisition_time_s")
    snapshot = _exact_keys(obj["snapshot"], {"name", "physical_lock_transform", "rotation_palm_to_target", "translation_palm_to_target_m"}, "/acquisition/snapshot")
    if snapshot["name"] != "T_PALM_TARGET_SNAPSHOT_SYNTHETIC" or snapshot["physical_lock_transform"] is not False:
        raise RehydrationError("SNAPSHOT_SEMANTICS_DRIFT")
    matrices_obj = _exact_keys(obj["matrices"], set(MATRIX_SHAPES), "/acquisition/matrices")
    matrices = {name: _array(matrices_obj[name], shape, f"/acquisition/matrices/{name}") for name, shape in MATRIX_SHAPES.items()}
    ranks = _exact_keys(obj["ranks"], {"G_bar", "J_hat", "L_hat"}, "/acquisition/ranks")
    if any(type(value) is not int for value in ranks.values()):
        raise RehydrationError("RANK_JSON_INT_REQUIRED")
    result = AcquisitionResult(
        run_id=_string(obj["run_id"], "/acquisition/run_id"),
        acquisition_time_s=acquisition_time,
        snapshot=SnapshotTransform(
            _array(snapshot["translation_palm_to_target_m"], (3,), "/acquisition/snapshot/translation_palm_to_target_m"),
            _array(snapshot["rotation_palm_to_target"], (3, 3), "/acquisition/snapshot/rotation_palm_to_target"),
            acquisition_time,
        ),
        reference_length_m=_float(obj["reference_length_m"], "/acquisition/reference_length_m"),
        z_minus=_array(obj["z_minus"], (20,), "/acquisition/z_minus"),
        z_plus_reduced=_array(obj["z_plus_reduced"], (20,), "/acquisition/z_plus_reduced"),
        z_plus_kkt=_array(obj["z_plus_kkt"], (20,), "/acquisition/z_plus_kkt"),
        z_plus_schur_audit=_array(obj["z_plus_schur_audit"], (20,), "/acquisition/z_plus_schur_audit"),
        eta_plus=_array(obj["eta_plus"], (14,), "/acquisition/eta_plus"),
        linear_impulse_n_s=_array(obj["linear_impulse_N_s"], (3,), "/acquisition/linear_impulse_N_s"),
        angular_impulse_n_m_s=_array(obj["angular_impulse_N_m_s"], (3,), "/acquisition/angular_impulse_N_m_s"),
        lambda_bar=_array(obj["lambda_bar"], (6,), "/acquisition/lambda_bar"),
        matrices=matrices,
        ranks=deepcopy(ranks),
        metrics=_exact_float_object(obj["metrics"], METRICS_KEYS, "/acquisition/metrics"),
        wrench_audit=_wrench_from_json(obj["wrench_audit"]),
        energy_audit=_exact_float_object(obj["energy_audit"], ENERGY_KEYS, "/acquisition/energy_audit"),
        momentum_audit=_momentum_from_json(obj["momentum_audit"]),
        backend_provenance=_backend_from_json(obj["backend_provenance"]),
    )
    if not np.array_equal(result.eta_plus, result.z_plus_reduced[:14]):
        raise RehydrationError("ETA_PLUS_NOT_EXACT_Z_PLUS_REDUCED_PREFIX")
    return result


def event_to_json(event: EventInput) -> dict[str, Any]:
    return {
        "run_id": event.run_id, "method": event.method, "step_s": event.step_s,
        "index": event.index, "time_s": event.time_s, "source": event.source,
        "state_label": event.state_label, "criteria": deepcopy(event.criteria),
        "service": {
            "base_position_inertial_m": event.service.base_position_inertial_m.tolist(),
            "base_quaternion_body_to_inertial_wxyz": event.service.base_quaternion_body_to_inertial_wxyz.tolist(),
            "joint_coordinates_mixed": event.service.joint_coordinates_mixed.tolist(),
            "nu_s_mixed": event.service.nu_s_mixed.tolist(),
        },
        "target": {
            "position_inertial_m": event.target.position_inertial_m.tolist(),
            "quaternion_body_to_inertial_wxyz": event.target.quaternion_body_to_inertial_wxyz.tolist(),
            "twist_inertial_mixed": event.target.twist_inertial_mixed.tolist(),
        },
        "left_common_contact_point_m": event.left_common_contact_point_m.tolist(),
        "right_common_contact_point_m": event.right_common_contact_point_m.tolist(),
        "left_contact_potential_J": event.left_contact_potential_j,
        "right_contact_potential_J": event.right_contact_potential_j,
        "b3_dissipation_J": event.b3_dissipation_j,
    }


def acquisition_to_json(value: AcquisitionResult, *, include_matrices: bool = True) -> dict[str, Any]:
    result = {
        "run_id": value.run_id, "acquisition_time_s": value.acquisition_time_s,
        "snapshot": {
            "name": "T_PALM_TARGET_SNAPSHOT_SYNTHETIC",
            "translation_palm_to_target_m": value.snapshot.translation_palm_to_target_m.tolist(),
            "rotation_palm_to_target": value.snapshot.rotation_palm_to_target.tolist(),
            "physical_lock_transform": False,
        },
        "reference_length_m": value.reference_length_m,
        "z_minus": value.z_minus.tolist(), "z_plus_reduced": value.z_plus_reduced.tolist(),
        "z_plus_kkt": value.z_plus_kkt.tolist(), "z_plus_schur_audit": value.z_plus_schur_audit.tolist(),
        "eta_plus": value.eta_plus.tolist(), "linear_impulse_N_s": value.linear_impulse_n_s.tolist(),
        "angular_impulse_N_m_s": value.angular_impulse_n_m_s.tolist(), "lambda_bar": value.lambda_bar.tolist(),
        "ranks": deepcopy(value.ranks), "metrics": deepcopy(value.metrics),
        "wrench_audit": deepcopy(value.wrench_audit), "energy_audit": deepcopy(value.energy_audit),
        "momentum_audit": deepcopy(value.momentum_audit), "backend_provenance": deepcopy(value.backend_provenance),
    }
    if include_matrices:
        result["matrices"] = {name: value.matrices[name].tolist() for name in MATRIX_SHAPES}
    return result


def to_payload(fixture: RehydratedFixture, *, include_matrices: bool = True) -> dict[str, Any]:
    validate_float64_arrays(fixture)
    return {
        "acquisition": acquisition_to_json(fixture.acquisition, include_matrices=include_matrices),
        "case_id": fixture.case_id,
        "event": event_to_json(fixture.event),
        "lane_id": fixture.lane_id,
    }


def rehydrate_payload(payload: Any, declared_certificate_sha256: str) -> RehydratedFixture:
    obj = _exact_keys(payload, {"acquisition", "case_id", "event", "lane_id"}, "/")
    pointer_count = sum(1 for _ in iter_json_pointers(obj))
    fixture = RehydratedFixture(
        case_id=_string(obj["case_id"], "/case_id"), lane_id=_string(obj["lane_id"], "/lane_id"),
        event=_event_from_json(obj["event"]), acquisition=_acquisition_from_json(obj["acquisition"]),
        declared_certificate_sha256=_string(declared_certificate_sha256, "/declared_certificate_sha256"),
        source_pointer_count=pointer_count,
    )
    if fixture.case_id != fixture.event.run_id or fixture.case_id != fixture.acquisition.run_id:
        raise RehydrationError("CASE_BOUND_RUN_ID_MISMATCH")
    if fixture.event.time_s != fixture.acquisition.acquisition_time_s or fixture.acquisition.snapshot.acquisition_time_s != fixture.acquisition.acquisition_time_s:
        raise RehydrationError("EVENT_ACQUISITION_AND_HIDDEN_SNAPSHOT_TIME_MISMATCH")
    rebuilt = to_payload(fixture, include_matrices=True)
    if sum(1 for _ in iter_json_pointers(rebuilt)) != pointer_count:
        raise RehydrationError("PAYLOAD_POINTER_SET_NOT_FULLY_CONSUMED")
    if canonical_bytes(rebuilt) != canonical_bytes(obj):
        raise RehydrationError("INCLUDE_MATRICES_ROUNDTRIP_NOT_BYTE_EXACT")
    if canonical_sha256(rebuilt) != declared_certificate_sha256:
        raise RehydrationError("ROUNDTRIP_CERTIFICATE_HASH_MISMATCH")
    return fixture


def derive_common_group(fixture: RehydratedFixture) -> dict[str, Any]:
    reduced = fixture.acquisition.z_plus_reduced
    return {
        "schema": "B4G_R2_COMMON_INITIAL_STATE_GROUP_V1",
        "donor_acquisition_certificate_sha256": fixture.declared_certificate_sha256,
        "acquisition_time_s": fixture.acquisition.acquisition_time_s,
        "service": {
            "base_position_inertial_m": fixture.event.service.base_position_inertial_m.tolist(),
            "base_quaternion_body_to_inertial_wxyz": fixture.event.service.base_quaternion_body_to_inertial_wxyz.tolist(),
            "joint_coordinates_mixed": fixture.event.service.joint_coordinates_mixed.tolist(),
            "post_acquisition_eta_mixed": reduced[:14].tolist(),
        },
        "target": {
            "position_inertial_m": fixture.event.target.position_inertial_m.tolist(),
            "quaternion_body_to_inertial_wxyz": fixture.event.target.quaternion_body_to_inertial_wxyz.tolist(),
            "post_acquisition_twist_inertial_mixed": reduced[14:20].tolist(),
        },
    }


def fixture_hashes(fixture: RehydratedFixture) -> dict[str, Any]:
    payload = to_payload(fixture, include_matrices=True)
    group = derive_common_group(fixture)
    return {
        "payload_canonical_bytes": len(canonical_bytes(payload)), "payload_sha256": canonical_sha256(payload),
        "group_canonical_bytes": len(canonical_bytes(group)), "group_sha256": canonical_sha256(group),
    }


def load_donor_fixture(path: Path) -> RehydratedFixture:
    if path.stat().st_size != DONOR_RAW_BYTES or file_sha256(path) != DONOR_RAW_SHA256:
        raise RehydrationError("DONOR_RAW_BYTES_OR_HASH_DRIFT")
    # Historical case metadata contains registered null fields outside the bound
    # certificate payload.  They are allowed only for this outer read; the
    # extracted payload is canonicalized with the package-wide no-null rule.
    raw = load_path(path, allow_null=True)
    if not isinstance(raw, dict) or not isinstance(raw.get("event_provenance"), dict):
        raise RehydrationError("DONOR_EVENT_PROVENANCE_MISSING")
    provenance = raw["event_provenance"]
    declared = provenance.get("acquisition_certificate_sha256")
    payload = provenance.get("acquisition_certificate_payload")
    if declared != DONOR_PAYLOAD_SHA256 or len(canonical_bytes(payload)) != DONOR_PAYLOAD_BYTES or canonical_sha256(payload) != DONOR_PAYLOAD_SHA256:
        raise RehydrationError("DONOR_PAYLOAD_BYTES_OR_HASH_DRIFT")
    fixture = rehydrate_payload(payload, declared)
    hashes = fixture_hashes(fixture)
    if hashes != {
        "payload_canonical_bytes": DONOR_PAYLOAD_BYTES, "payload_sha256": DONOR_PAYLOAD_SHA256,
        "group_canonical_bytes": COMMON_GROUP_BYTES, "group_sha256": COMMON_GROUP_SHA256,
    }:
        raise RehydrationError("DONOR_TYPED_ROUNDTRIP_OR_GROUP_DRIFT")
    return fixture


def collect_mutable_ids(value: Any) -> set[int]:
    seen: set[int] = set()
    def visit(item: Any) -> None:
        if isinstance(item, np.ndarray):
            seen.add(id(item))
        elif isinstance(item, dict):
            seen.add(id(item))
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            seen.add(id(item))
            for child in item:
                visit(child)
        elif is_dataclass(item):
            for field in fields(item):
                visit(getattr(item, field.name))
    visit(value)
    return seen


def validate_float64_arrays(value: Any) -> None:
    """Freeze typed numeric storage even when another dtype serializes similarly."""

    def visit(item: Any) -> None:
        if isinstance(item, np.ndarray):
            if item.dtype != np.dtype("float64") or not np.all(np.isfinite(item)):
                raise RehydrationError(f"FLOAT64_FINITE_ARRAY_REQUIRED:{item.dtype}")
        elif isinstance(item, dict):
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)
        elif is_dataclass(item):
            for field in fields(item):
                visit(getattr(item, field.name))
    visit(value)


def isolated_common_fixture(donor: RehydratedFixture) -> RehydratedFixture:
    """Return a complete, independently mutable case fixture after roundtrip."""

    before = fixture_hashes(donor)
    clone = deepcopy(donor)
    if collect_mutable_ids(donor) & collect_mutable_ids(clone):
        raise RehydrationError("COMMON_CASE_MUTABLE_OBJECT_IDENTITY_REUSED")
    if fixture_hashes(clone) != before:
        raise RehydrationError("COMMON_CASE_DEEPCOPY_HASH_DRIFT")
    return clone


@contextmanager
def donor_immutability_guard(donor: RehydratedFixture) -> Iterator[None]:
    before = fixture_hashes(donor)
    try:
        yield
    finally:
        after = fixture_hashes(donor)
        if after != before:
            raise RehydrationError("DONOR_MUTATED_DURING_CASE")


def to_bound_b4e_types(fixture: RehydratedFixture, b4e_module: Any) -> tuple[Any, Any]:
    """Build the hash-bound B4E classes after an execution guard imports them.

    The caller must pass the lazily imported ``constraint_solver`` module; this
    function never imports it.  A complete original serializer roundtrip is
    required before the objects can leave the adapter.
    """

    event = b4e_module.EventInput(
        fixture.event.run_id, fixture.event.method, fixture.event.step_s,
        fixture.event.index, fixture.event.time_s,
        b4e_module.ServiceState(
            fixture.event.service.base_position_inertial_m.copy(),
            fixture.event.service.base_quaternion_body_to_inertial_wxyz.copy(),
            fixture.event.service.joint_coordinates_mixed.copy(),
            fixture.event.service.nu_s_mixed.copy(),
        ),
        b4e_module.TargetState(
            fixture.event.target.position_inertial_m.copy(),
            fixture.event.target.quaternion_body_to_inertial_wxyz.copy(),
            fixture.event.target.twist_inertial_mixed.copy(),
        ),
        fixture.event.left_common_contact_point_m.copy(), fixture.event.right_common_contact_point_m.copy(),
        fixture.event.left_contact_potential_j, fixture.event.right_contact_potential_j,
        fixture.event.b3_dissipation_j, fixture.event.state_label,
        deepcopy(fixture.event.criteria), fixture.event.source,
    )
    acquisition = b4e_module.AcquisitionResult(
        fixture.acquisition.run_id, fixture.acquisition.acquisition_time_s,
        b4e_module.SnapshotTransform(
            fixture.acquisition.snapshot.translation_palm_to_target_m.copy(),
            fixture.acquisition.snapshot.rotation_palm_to_target.copy(),
            fixture.acquisition.snapshot.acquisition_time_s,
        ),
        fixture.acquisition.reference_length_m, fixture.acquisition.z_minus.copy(),
        fixture.acquisition.z_plus_reduced.copy(), fixture.acquisition.z_plus_kkt.copy(),
        fixture.acquisition.z_plus_schur_audit.copy(), fixture.acquisition.eta_plus.copy(),
        fixture.acquisition.linear_impulse_n_s.copy(), fixture.acquisition.angular_impulse_n_m_s.copy(),
        fixture.acquisition.lambda_bar.copy(),
        {name: matrix.copy() for name, matrix in fixture.acquisition.matrices.items()},
        deepcopy(fixture.acquisition.ranks), deepcopy(fixture.acquisition.metrics),
        deepcopy(fixture.acquisition.wrench_audit), deepcopy(fixture.acquisition.energy_audit),
        deepcopy(fixture.acquisition.momentum_audit), deepcopy(fixture.acquisition.backend_provenance),
    )
    rebuilt = {
        "acquisition": b4e_module.acquisition_to_json(acquisition, include_matrices=True),
        "case_id": fixture.case_id,
        "event": b4e_module.event_to_json(event),
        "lane_id": fixture.lane_id,
    }
    if canonical_bytes(rebuilt) != canonical_bytes(to_payload(fixture, include_matrices=True)):
        raise RehydrationError("BOUND_B4E_CLASS_SERIALIZER_ROUNDTRIP_MISMATCH")
    return event, acquisition
