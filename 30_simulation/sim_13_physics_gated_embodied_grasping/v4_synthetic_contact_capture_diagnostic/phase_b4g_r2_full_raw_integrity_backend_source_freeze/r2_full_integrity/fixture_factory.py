"""Temporary, nonphysical fixtures for backend discrimination tests only."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any, Callable

import numpy as np

from .context import (
    AUTHORIZATION_SENTINEL,
    CLAIM_BOUNDARY,
    CONTEXT_SCHEMA,
    EVIDENCE_CLASS,
    PARENT_CLAIM_BOUNDARY,
    PARENT_SOURCE_KIND,
    PROVENANCE_SCOPE,
    load_integrity_context,
)
from .integrity import _profile
from .source_api import load_geometry_module, load_raw_modules, project_root


ArrayMutator = Callable[[dict[str, np.ndarray]], None]
ObjectMutator = Callable[[dict[str, Any]], None]
CASE_ID = "FRESH__RK4_H_MS_0P25__A1__A_16__T_MS_5"


@dataclass(frozen=True)
class FixtureBundle:
    root: Path
    raw_sidecar_relative_path: str
    context_relative_path: str

    def load(self) -> tuple[Any, Any]:
        modules = load_raw_modules()
        case = modules["adapter"].load_bound_case(self.root, self.raw_sidecar_relative_path)
        context = load_integrity_context(self.root, self.context_relative_path, case)
        return case, context


def _canonical_sha256(value: Any) -> str:
    return load_raw_modules()["strict_json"].canonical_sha256(value)


def _populate_truth(arrays: dict[str, np.ndarray]) -> None:
    geometry = load_geometry_module()
    snapshot = {
        "translation_palm_to_target_m": [0.0, 0.0, 0.0],
        "rotation_palm_to_target": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
    }
    service = np.zeros(29, dtype="<f8")
    service[3] = 1.0
    service[13:15] = 0.03
    arrays["service_state_29"][:] = service
    arrays["stage_service_state_29"][:] = service
    arrays["stage_P_coordinates_m"][:] = service[13:15]
    arrays["post_service_state_29"][:] = service
    arrays["post_stage_service_state_29"][:] = service
    arrays["post_stage_P_coordinates_m"][:] = service[13:15]

    active_target = geometry.reconstruct_active_target_state_13(service, snapshot)
    active_observation = geometry.recompute_gap_rate(service, active_target)
    active_jacobian = geometry.centered_gap_jacobian(service, snapshot=snapshot)
    arrays["target_state_13"][:] = active_target
    arrays["left_gap_m"][:] = active_observation.gaps_m[0]
    arrays["right_gap_m"][:] = active_observation.gaps_m[1]
    arrays["left_gap_rate_m_s"][:] = active_observation.gap_rates_m_s[0]
    arrays["right_gap_rate_m_s"][:] = active_observation.gap_rates_m_s[1]
    arrays["stage_gap_jacobian_P"][:] = active_jacobian.raw_gap_jacobian_p

    arrays["post_target_state_13"][:] = active_target
    arrays["post_stage_target_state_13"][:] = active_target
    post_observation = geometry.recompute_gap_rate(service, active_target)
    post_jacobian = geometry.centered_gap_jacobian(service, independent_target_state_13=active_target)
    arrays["post_left_gap_m"][:] = post_observation.gaps_m[0]
    arrays["post_right_gap_m"][:] = post_observation.gaps_m[1]
    arrays["post_left_gap_rate_m_s"][:] = post_observation.gap_rates_m_s[0]
    arrays["post_right_gap_rate_m_s"][:] = post_observation.gap_rates_m_s[1]
    arrays["post_stage_gap_jacobian_P"][:] = post_jacobian.raw_gap_jacobian_p

    expected_saved = _profile(arrays["time_s"], 0.0, 16.0, 0.005)
    expected_stage = _profile(arrays["stage_time_s"], 0.0, 16.0, 0.005)
    arrays["command_Q_14"][:] = 0.0
    arrays["command_Q_14"][:, 12] = expected_saved
    arrays["command_Q_14"][:, 13] = expected_saved
    arrays["stage_command_Q_14"][:] = 0.0
    arrays["stage_command_Q_14"][:, 12] = expected_stage
    arrays["stage_command_Q_14"][:, 13] = expected_stage
    arrays["post_command_Q_14"][:] = 0.0
    arrays["sample_power_reported_W"][:] = 0.0
    arrays["stage_power_W"][:] = 0.0
    arrays["signed_W_act_J"][:] = 0.0
    arrays["stage_augmented_W_act_J"][:] = 0.0
    arrays["post_signed_W_act_J"][:] = 0.0
    arrays["total_kinetic_energy_J"][:] = 10.0
    arrays["post_total_kinetic_energy_J"][:] = 10.0
    arrays["energy_minus_work_residual_J"][:] = 0.0
    arrays["ideal_constraint_power_W"][:] = 0.0
    arrays["total_linear_momentum_N_s"][:] = 0.0
    arrays["total_angular_momentum_N_m_s"][:] = 0.0
    arrays["post_total_linear_momentum_N_s"][:] = 0.0
    arrays["post_total_angular_momentum_N_m_s"][:] = 0.0
    arrays["contact_force_N"][:] = 0.0
    arrays["contact_torque_N_m"][:] = 0.0
    arrays["post_contact_force_N"][:] = 0.0
    arrays["post_contact_torque_N_m"][:] = 0.0
    arrays["stage_mass_cholesky_min_diagonal"][:] = 1.0
    arrays["stage_domain_and_sign_pass"][:] = True
    arrays["post_stage_domain_and_sign_pass"][:] = True
    arrays["active_interval_ledger_certified"][:] = True


def _acquisition_payload(case: Any) -> dict[str, Any]:
    service = case.arrays["service_state_29"][0]
    target = case.arrays["target_state_13"][0]
    z_plus = np.concatenate((service[15:29], target[7:13]))
    snapshot = {
        "translation_palm_to_target_m": [0.0, 0.0, 0.0],
        "rotation_palm_to_target": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
    }
    return {
        "lane_id": case.sidecar["lane_id"],
        "case_id": case.sidecar["case_id"],
        "event": {
            "run_id": case.sidecar["case_id"],
            "method": case.sidecar["method"],
            "step_s": case.sidecar["step_s"],
            "index": 0,
            "time_s": float(case.arrays["time_s"][0]),
            "source": "INDEPENDENT_B3_RERUN_FIRST_QUALIFYING_SAMPLE",
            "b3_dissipation_J": 0.0,
            "service": {
                "base_position_inertial_m": service[0:3].tolist(),
                "base_quaternion_body_to_inertial_wxyz": service[3:7].tolist(),
                "joint_coordinates_mixed": service[7:15].tolist(),
            },
            "target": {
                "position_inertial_m": target[0:3].tolist(),
                "quaternion_body_to_inertial_wxyz": target[3:7].tolist(),
            },
        },
        "acquisition": {
            "run_id": case.sidecar["case_id"],
            "acquisition_time_s": float(case.arrays["time_s"][0]),
            "z_plus_reduced": z_plus.tolist(),
            "eta_plus": z_plus[:14].tolist(),
            "snapshot": snapshot,
            "energy_audit": {"D_B3_minus_J": 0.0},
        },
    }


def write_technical_fixture(
    root: Path,
    *,
    array_mutator: ArrayMutator | None = None,
    acquisition_mutator: ObjectMutator | None = None,
    parent_mutator: ObjectMutator | None = None,
    context_mutator: ObjectMutator | None = None,
) -> FixtureBundle:
    modules = load_raw_modules()

    def populate(arrays: dict[str, np.ndarray]) -> None:
        _populate_truth(arrays)
        if array_mutator is not None:
            array_mutator(arrays)

    raw_relative = modules["fixture_factory"].write_case(
        root,
        case_id=CASE_ID,
        method="rk4",
        step_s=0.00025,
        outcome=modules["adapter"].OUTCOME_FINITE,
        horizon_s=0.006,
        alpha=16.0,
        command_duration_s=0.005,
        array_mutator=populate,
    )
    case = modules["adapter"].load_bound_case(root, raw_relative)
    acquisition = _acquisition_payload(case)
    if acquisition_mutator is not None:
        acquisition_mutator(acquisition)
    acquisition_sha = _canonical_sha256(acquisition)
    removal_index = int(case.arrays["bilateral_removal_active_sample_index"][0])
    parent = {
        "schema": "SIM13_V4B4G_R2_B4E_PARENT_POST_TRACE_COMPACT_V1",
        "case_id": case.sidecar["case_id"],
        "lane_id": case.sidecar["lane_id"],
        "method": case.sidecar["method"],
        "step_s": case.sidecar["step_s"],
        "producer_id": PARENT_SOURCE_KIND,
        "parent_source_bindings": [
            dict(item) for item in load_geometry_module().validate_frozen_source_bindings(project_root())
        ],
        "input_projection": {
            "raw_npz_sha256": case.npz_sha256,
            "acquisition_certificate_sha256": acquisition_sha,
            "removal_index": removal_index,
            "removal_time_s": float(case.arrays["bilateral_removal_event_time_s"][0]),
            "active_service_state_29_sha256": _canonical_sha256(case.arrays["service_state_29"][removal_index].tolist()),
        },
        "mapping_z_before_20": np.concatenate((
            case.arrays["service_state_29"][removal_index, 15:29],
            case.arrays["target_state_13"][removal_index, 7:13],
        )).tolist(),
        "terminal_service_state_29": case.arrays["post_service_state_29"][-1].tolist(),
        "terminal_target_state_13": case.arrays["post_target_state_13"][-1].tolist(),
        "post_release_passed": True,
        "terminal_status": "SOURCE_ONLY_TECHNICAL_PARENT_TRACE_COMPLETE",
        "claim_boundary": PARENT_CLAIM_BOUNDARY,
    }
    if parent_mutator is not None:
        parent_mutator(parent)
    parent_relative = f"evidence/parent/{CASE_ID}.json"
    parent_path = root / parent_relative
    modules["strict_json"].atomic_write_json(parent_path, parent)
    parent_payload = parent_path.read_bytes()
    context = {
        "schema": CONTEXT_SCHEMA,
        "case_id": case.sidecar["case_id"],
        "lane_id": case.sidecar["lane_id"],
        "method": case.sidecar["method"],
        "step_s": case.sidecar["step_s"],
        "raw_binding": case.raw_binding(),
        "execution_evidence_class": EVIDENCE_CLASS,
        "authorization_terminal_binding": AUTHORIZATION_SENTINEL,
        "acquisition_certificate_payload": acquisition,
        "acquisition_certificate_sha256": acquisition_sha,
        "acquisition_provenance_scope": PROVENANCE_SCOPE,
        "parent_trace_binding": {
            "schema": "SIM13_V4B4G_R2_PARENT_POST_RELEASE_TRACE_FILE_BINDING_V1",
            "path": parent_relative,
            "bytes": len(parent_payload),
            "sha256": hashlib.sha256(parent_payload).hexdigest().upper(),
        },
        "claim_boundary": CLAIM_BOUNDARY,
    }
    if context_mutator is not None:
        context_mutator(context)
    context_relative = f"evidence/context/{CASE_ID}.json"
    modules["strict_json"].atomic_write_json(root / context_relative, context)
    return FixtureBundle(root, raw_relative, context_relative)


__all__ = ["CASE_ID", "FixtureBundle", "write_technical_fixture"]
