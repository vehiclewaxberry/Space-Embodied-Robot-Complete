"""Future R2 exact NPZ schema: B4G channels plus raw event/work evidence.

This is intentionally not byte/schema-compatible with legacy B4G raw. The
legacy archive lacks an independent stage work state, saved-sample reported
power, post work/command histories, and raw 0/1 event cardinality.
"""

from __future__ import annotations

from typing import Any

from .strict_json import canonical_sha256

DTYPE_F64 = "<f8"
DTYPE_I64 = "<i8"
DTYPE_BOOL = "|b1"


def _a(dtype: str, shape: list[Any], unit: str, meaning: str) -> dict[str, Any]:
    return {"dtype": dtype, "shape": shape, "unit": unit, "meaning": meaning}


# The 25 historical active names are retained. Stage arrays use the R2 vNext
# layout: mechanical stages only; legacy code-0 saved-state rows are forbidden.
ACTIVE_ARRAYS: dict[str, dict[str, Any]] = {
    "command_Q_14": _a(DTYPE_F64, ["N", 14], "SI_mixed_generalized_force", "saved generalized command"),
    "contact_force_N": _a(DTYPE_F64, ["N"], "N", "contact resultant force"),
    "contact_torque_N_m": _a(DTYPE_F64, ["N"], "N*m", "contact resultant torque"),
    "energy_minus_work_residual_J": _a(DTYPE_F64, ["N"], "J", "independent energy-minus-work residual"),
    "ideal_constraint_power_W": _a(DTYPE_F64, ["N"], "W", "ideal constraint power"),
    "left_gap_m": _a(DTYPE_F64, ["N"], "m", "left signed gap"),
    "left_gap_rate_m_s": _a(DTYPE_F64, ["N"], "m/s", "left gap rate"),
    "right_gap_m": _a(DTYPE_F64, ["N"], "m", "right signed gap"),
    "right_gap_rate_m_s": _a(DTYPE_F64, ["N"], "m/s", "right gap rate"),
    "service_state_29": _a(DTYPE_F64, ["N", 29], "SI_mixed_state", "service state [r,q,qj,v,w,dqj]"),
    "signed_W_act_J": _a(DTYPE_F64, ["N"], "J", "saved signed actuator work state"),
    "stage_P_coordinates_m": _a(DTYPE_F64, ["S", 2], "m", "mechanical-stage prismatic coordinates"),
    "stage_code": _a(DTYPE_I64, ["S"], "1", "RK4 1..4 or midpoint 1,5; code 0 forbidden"),
    "stage_command_Q_14": _a(DTYPE_F64, ["S", 14], "SI_mixed_generalized_force", "mechanical-stage generalized command"),
    "stage_domain_and_sign_pass": _a(DTYPE_BOOL, ["S"], "1", "mechanical-stage domain/sign predicate"),
    "stage_gap_jacobian_P": _a(DTYPE_F64, ["S", 2, 2], "1", "mechanical-stage P-gap Jacobian"),
    "stage_mass_cholesky_min_diagonal": _a(DTYPE_F64, ["S"], "SI_sqrt_mass", "stage mass Cholesky minimum diagonal"),
    "stage_power_W": _a(DTYPE_F64, ["S"], "W", "reported actuator power at mechanical stages"),
    "stage_service_state_29": _a(DTYPE_F64, ["S", 29], "SI_mixed_state", "service state at mechanical stages"),
    "stage_time_s": _a(DTYPE_F64, ["S"], "s", "mechanical-stage time"),
    "target_state_13": _a(DTYPE_F64, ["N", 13], "SI_mixed_state", "target state [r,q,v,w]"),
    "time_s": _a(DTYPE_F64, ["N"], "s", "saved time; only final finite-event interval may be fractional"),
    "total_angular_momentum_N_m_s": _a(DTYPE_F64, ["N", 3], "N*m*s", "native total angular momentum"),
    "total_kinetic_energy_J": _a(DTYPE_F64, ["N"], "J", "total kinetic energy"),
    "total_linear_momentum_N_s": _a(DTYPE_F64, ["N", 3], "N*s", "native total linear momentum"),
}


# The 19 historical post names remain present in every profile. P/PS are zero
# for no-event/common evidence and P>=2 for a finite removal.
POST_ARRAYS: dict[str, dict[str, Any]] = {
    "post_contact_force_N": _a(DTYPE_F64, ["P"], "N", "post-removal contact force"),
    "post_contact_torque_N_m": _a(DTYPE_F64, ["P"], "N*m", "post-removal contact torque"),
    "post_left_gap_m": _a(DTYPE_F64, ["P"], "m", "post-removal left gap"),
    "post_left_gap_rate_m_s": _a(DTYPE_F64, ["P"], "m/s", "post-removal left gap rate"),
    "post_right_gap_m": _a(DTYPE_F64, ["P"], "m", "post-removal right gap"),
    "post_right_gap_rate_m_s": _a(DTYPE_F64, ["P"], "m/s", "post-removal right gap rate"),
    "post_service_state_29": _a(DTYPE_F64, ["P", 29], "SI_mixed_state", "post-removal service state"),
    "post_stage_P_coordinates_m": _a(DTYPE_F64, ["PS", 2], "m", "post stage P coordinates"),
    "post_stage_code": _a(DTYPE_I64, ["PS"], "1", "post mechanical-stage code"),
    "post_stage_domain_and_sign_pass": _a(DTYPE_BOOL, ["PS"], "1", "post stage domain/sign predicate"),
    "post_stage_gap_jacobian_P": _a(DTYPE_F64, ["PS", 2, 2], "1", "post stage P-gap Jacobian"),
    "post_stage_service_state_29": _a(DTYPE_F64, ["PS", 29], "SI_mixed_state", "post stage service state"),
    "post_stage_target_state_13": _a(DTYPE_F64, ["PS", 13], "SI_mixed_state", "post stage target state"),
    "post_stage_time_s": _a(DTYPE_F64, ["PS"], "s", "post mechanical-stage time"),
    "post_target_state_13": _a(DTYPE_F64, ["P", 13], "SI_mixed_state", "post-removal target state"),
    "post_time_s": _a(DTYPE_F64, ["P"], "s", "post-removal saved time"),
    "post_total_angular_momentum_N_m_s": _a(DTYPE_F64, ["P", 3], "N*m*s", "post native angular momentum"),
    "post_total_kinetic_energy_J": _a(DTYPE_F64, ["P"], "J", "post total kinetic energy"),
    "post_total_linear_momentum_N_s": _a(DTYPE_F64, ["P", 3], "N*s", "post native linear momentum"),
}


R2_REQUIRED_ARRAYS: dict[str, dict[str, Any]] = {
    "sample_power_reported_W": _a(DTYPE_F64, ["N"], "W", "runner-reported saved-sample actuator power"),
    "stage_augmented_W_act_J": _a(DTYPE_F64, ["S"], "J", "independently propagated stage work state"),
    "post_signed_W_act_J": _a(DTYPE_F64, ["P"], "J", "carried post-removal work state"),
    "post_command_Q_14": _a(DTYPE_F64, ["P", 14], "SI_mixed_generalized_force", "post-removal generalized command"),
    "acquisition_event_count": _a(DTYPE_I64, [], "1", "zero for A0 bookend; one otherwise"),
    "acquisition_event_sample_index": _a(DTYPE_I64, ["A"], "1", "0/1-length acquisition saved-sample index"),
    "acquisition_event_time_s": _a(DTYPE_F64, ["A"], "s", "0/1-length raw acquisition event time"),
    "bilateral_removal_event_count": _a(DTYPE_I64, [], "1", "zero or one"),
    "bilateral_removal_active_sample_index": _a(DTYPE_I64, ["R"], "1", "0/1-length exact removal index"),
    "bilateral_removal_event_time_s": _a(DTYPE_F64, ["R"], "s", "0/1-length exact removal time"),
    "saved_window_end_index": _a(DTYPE_I64, [], "1", "exact last admitted saved sample"),
    "active_interval_ledger_certified": _a(
        DTYPE_BOOL, ["I"], "1",
        "independently available active interval ledger; I=N-1 and every consumed interval must be true",
    ),
}


EXACT_ARRAYS = {**ACTIVE_ARRAYS, **POST_ARRAYS, **R2_REQUIRED_ARRAYS}
PROFILE_DEFINITIONS: dict[str, dict[str, Any]] = {
    name: {
        "schema": "SIM13_V4B4G_R2_ARRAY_PROFILE_V1",
        "outcomes": [outcome],
        "arrays": EXACT_ARRAYS,
        "stage_layout": "NO_CODE0_MECHANICAL_STAGES_ONLY",
        "last_interval_policy": "ONLY_FINAL_INTERVAL_MAY_BE_FRACTIONAL_AND_ONLY_FOR_RAW_FINITE_REMOVAL",
    }
    for name, outcome in (
        ("FRESH_FINITE_REMOVAL_V1", "FINITE_BILATERAL_REMOVAL_OBSERVED"),
        ("FRESH_NO_REMOVAL_V1", "NO_REMOVAL_OBSERVED_WITHIN_SAVED_WINDOW"),
        ("COMMON_PROPAGATION_V1", "COMMON_PROPAGATION_WINDOW_COMPLETE"),
        ("A0_BOOKEND_V1", "A0_BOOKEND_WINDOW_COMPLETE_NO_CAPTURE_EVENT"),
    )
}

PROFILE_SHA256 = {name: canonical_sha256(value) for name, value in PROFILE_DEFINITIONS.items()}
OUTCOME_TO_PROFILE = {outcome: name for name, profile in PROFILE_DEFINITIONS.items() for outcome in profile["outcomes"]}


def contract_document() -> dict[str, Any]:
    profile_registry = {
        name: {
            "schema": profile["schema"],
            "outcomes": profile["outcomes"],
            "array_set": "EXACT_ARRAYS_56",
            "array_count": len(EXACT_ARRAYS),
            "stage_layout": profile["stage_layout"],
            "last_interval_policy": profile["last_interval_policy"],
        }
        for name, profile in PROFILE_DEFINITIONS.items()
    }
    return {
        "schema": "SIM13_V4B4G_R2_RAW_ARRAY_CONTRACT_V1",
        "compatibility": "FUTURE_R2_EXACT_SCHEMA_LEGACY_B4G_RAW_IS_INCOMPATIBLE",
        "legacy_b4g_missing_required_arrays": [
            "sample_power_reported_W", "stage_augmented_W_act_J", "post_signed_W_act_J",
            "post_command_Q_14", "acquisition_event_count", "acquisition_event_sample_index",
            "acquisition_event_time_s", "bilateral_removal_event_count",
            "bilateral_removal_active_sample_index", "bilateral_removal_event_time_s",
            "saved_window_end_index", "active_interval_ledger_certified",
        ],
        "coordinate_and_unit_policy": {
            "system": "SI",
            "quaternion_order": "WXYZ",
            "service_state_29_layout": ["r_I_m[3]", "q_BI_wxyz[4]", "joint_q_R_rad[6]", "joint_q_P_m[2]", "v_I_m_s[3]", "omega_B_rad_s[3]", "joint_dq_R_rad_s[6]", "joint_dq_P_m_s[2]"],
            "target_state_13_layout": ["r_I_m[3]", "q_TI_wxyz[4]", "v_I_m_s[3]", "omega_T_rad_s[3]"],
        },
        "event_policy": {
            "acquisition_count": "ZERO_FOR_A0_BOOKEND_OTHERWISE_ONE",
            "removal_count": "0_OR_1",
            "no_removal": "ZERO_LENGTH_REMOVAL_INDEX_AND_TIME_ARRAYS_NO_SENTINEL_NO_NULL",
            "index_order": "0<=acquisition_index<=removal_index<=saved_window_end_index<N_IF_REMOVAL",
            "active_start": "A1_AND_COMMON_ACQUISITION_INDEX_IS_EXACTLY_ZERO_AND_TIME_S_0_IS_ACQUISITION_TIME",
            "no_removal_horizon_s": 0.08,
        },
        "post_release_policy": {
            "duration_s": 0.005,
            "saved_interval_s": "EXACT_REGISTERED_LANE_STEP_S",
            "stage_P_redundancy": "EXACT_POST_STAGE_P_EQUALS_POST_STAGE_SERVICE_STATE_COLUMNS_13_15",
        },
        "exact_array_count": len(EXACT_ARRAYS),
        "exact_arrays": EXACT_ARRAYS,
        "profile_sha256": PROFILE_SHA256,
        "profiles": profile_registry,
    }


ARRAY_CONTRACT_DOCUMENT_SHA256 = canonical_sha256(contract_document())

__all__ = [
    "ACTIVE_ARRAYS", "ARRAY_CONTRACT_DOCUMENT_SHA256", "EXACT_ARRAYS",
    "OUTCOME_TO_PROFILE", "POST_ARRAYS", "PROFILE_DEFINITIONS", "PROFILE_SHA256",
    "R2_REQUIRED_ARRAYS", "contract_document",
]
