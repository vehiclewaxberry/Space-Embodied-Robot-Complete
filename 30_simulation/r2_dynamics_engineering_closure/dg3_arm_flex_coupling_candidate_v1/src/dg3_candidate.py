"""Audited DG3 evaluator with conservation, frame, and mass-containment gates."""
from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import yaml

from dg3_arm_flex import (
    ROOT,
    _c07_spatial_inertia,
    _joint_limits,
    _pin_path,
    _relative_norm,
    _rhs,
    _vector,
    assemble_model,
    audit_rom_structure,
    audit_unified_urdf_and_frames,
    conservative_initial_state,
    contract_tamper_negative_controls,
    joint_motion,
    load_contract,
    load_json,
    response_envelope,
    solve_case,
    solve_modes_removed_rigid_case,
    validate_contract_semantics,
    validate_source_pins,
)
from r2_dynamics import load_backend


def _base_state_cross_metrics(
    primary_history: np.ndarray, cross_history: np.ndarray
) -> dict[str, float]:
    primary_history = np.asarray(primary_history, dtype=float)
    cross_history = np.asarray(cross_history, dtype=float)
    if primary_history.shape != cross_history.shape or primary_history.shape[1] < 12:
        raise ValueError("BASE_STATE_HISTORIES_MUST_MATCH_AND_HAVE_AT_LEAST_12_COLUMNS")
    return {
        "base_translation_max_abs_m": float(
            np.max(np.abs(primary_history[:, :3] - cross_history[:, :3]))
        ),
        "base_rotation_max_abs_rad": float(
            np.max(np.abs(primary_history[:, 3:6] - cross_history[:, 3:6]))
        ),
        "base_linear_rate_max_abs_m_s": float(
            np.max(np.abs(primary_history[:, 6:9] - cross_history[:, 6:9]))
        ),
        "base_angular_rate_max_abs_rad_s": float(
            np.max(np.abs(primary_history[:, 9:12] - cross_history[:, 9:12]))
        ),
    }


def _cross_metrics(
    primary: Mapping[str, Any], cross: Mapping[str, Any]
) -> dict[str, float]:
    primary_history = np.asarray(primary["history"])
    cross_history = np.asarray(cross["history"])
    return {
        **_base_state_cross_metrics(primary_history, cross_history),
        "eta_relative": _relative_norm(
            primary_history[:, 12:26], cross_history[:, 12:26]
        ),
        "eta_rate_relative": _relative_norm(
            primary_history[:, 26:40], cross_history[:, 26:40]
        ),
    }


def _dimension_gate_records(
    metrics: Mapping[str, float],
    threshold_keys: Mapping[str, str],
    metric_keys: Mapping[str, str],
    units: Mapping[str, str],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    records = {}
    for dimension in ("position", "attitude", "linear_rate", "angular_rate"):
        threshold_key = threshold_keys[dimension]
        unit = units[dimension]
        value = float(metrics[metric_keys[dimension]])
        threshold = float(contract["thresholds"][threshold_key])
        records[dimension] = {
            "value": value,
            "threshold": threshold,
            "unit": unit,
            "threshold_key": threshold_key,
            "threshold_unit_matches_contract": contract["threshold_units"][
                threshold_key
            ]
            == unit,
            "pass": value <= threshold
            and contract["threshold_units"][threshold_key] == unit,
        }
    return records


def _forced_lane(
    backend: Any,
    rom: Mapping[str, np.ndarray],
    envelope: Mapping[str, Any],
    contract: Mapping[str, Any],
    q0: np.ndarray,
    amplitude: np.ndarray,
    corner: str,
    damping_scale: float,
    lane_class: str,
    gate_credit: bool,
) -> dict[str, Any]:
    threshold = contract["thresholds"]
    model = assemble_model(
        backend,
        rom,
        q0,
        corner,
        coupling_scale=1.0,
        damping_scale=damping_scale,
    )
    primary = solve_case(
        model,
        q0,
        amplitude,
        contract["prescribed_excitation"],
        contract["solvers"],
        "Radau",
    )
    cross_solver = dict(contract["solvers"])
    if damping_scale == 0.0 and corner == "HIGH":
        cross_solver["max_step_s"] = contract["solvers"][
            "cross_C0_HIGH_max_step_s"
        ]
    cross = solve_case(
        model,
        q0,
        amplitude,
        contract["prescribed_excitation"],
        cross_solver,
        "BDF",
    )
    solver_cross = _cross_metrics(primary, cross)
    linearity = response_envelope(
        rom, envelope, np.asarray(primary["history"])[:, 12:26]
    )
    diagnostic_no_spectral_credit = {
        "classification": "DIAGNOSTIC_NO_SPECTRAL_CREDIT",
        "reason": "28X28_COORDINATES_MIX_M_RAD_AND_MASS_NORMALIZED_MODAL_UNITS",
        "numeric_spectral_values_emitted": False,
        "forbidden_numeric_fields": [
            "eigenvalue",
            "condition_number",
            "spectral_radius",
        ],
        "units": None,
        "gate_credit": False,
    }
    checks = {
        "mass_matrices_symmetric_structure": all(
            audit["symmetric_within_frozen_numeric_tolerance"]
            for audit in model["mass_matrix_structure"].values()
        ),
        "all_solve_mass_matrices_Cholesky_positive_definite": model[
            "all_mass_matrices_cholesky_positive_definite"
        ],
        "damping_zero_for_conservative_lane": damping_scale != 0.0
        or float(np.max(np.abs(model["damping"]))) == 0.0,
        "solver_base_translation_cross": solver_cross[
            "base_translation_max_abs_m"
        ]
        <= threshold["solver_base_translation_cross_max_m"],
        "solver_base_rotation_cross": solver_cross["base_rotation_max_abs_rad"]
        <= threshold["solver_base_rotation_cross_max_rad"],
        "solver_base_linear_rate_cross": solver_cross[
            "base_linear_rate_max_abs_m_s"
        ]
        <= threshold["solver_base_linear_rate_cross_max_m_s"],
        "solver_base_angular_rate_cross": solver_cross[
            "base_angular_rate_max_abs_rad_s"
        ]
        <= threshold["solver_base_angular_rate_cross_max_rad_s"],
        "solver_eta_cross": solver_cross["eta_relative"]
        <= threshold["solver_eta_relative_max"],
        "solver_eta_rate_cross": solver_cross["eta_rate_relative"]
        <= threshold["solver_eta_rate_relative_max"],
        "energy_work_dissipation_balance": primary["metrics"][
            "energy_work_dissipation_balance_relative_peak"
        ]
        <= threshold["energy_work_dissipation_balance_relative_max"],
        "canonical_base_linear_momentum": primary["metrics"][
            "canonical_base_linear_momentum_residual_max_kg_m_s"
        ]
        <= threshold["canonical_linear_momentum_residual_max_kg_m_s"],
        "canonical_base_angular_momentum": primary["metrics"][
            "canonical_base_angular_momentum_residual_max_kg_m2_s"
        ]
        <= threshold["canonical_angular_momentum_residual_max_kg_m2_s"],
        "arm_motion_excites_modal_energy": primary["metrics"][
            "modal_energy_peak_J"
        ]
        >= threshold["modal_energy_excitation_min_J"],
        "linearity_envelope": linearity["pass"],
        "base_tangent_rotation_envelope": primary["metrics"][
            "base_rotation_tangent_peak_rad"
        ]
        <= threshold["base_tangent_rotation_max_rad"],
    }
    return {
        "corner": corner,
        "lane_class": lane_class,
        "gate_credit": gate_credit,
        "damping_scale": damping_scale,
        "solver_controls": {
            "primary_max_step_s": contract["solvers"]["max_step_s"],
            "cross_max_step_s": cross_solver["max_step_s"],
            "cross_refinement_reason": (
                contract["solvers"]["cross_C0_HIGH_refinement_reason"]
                if damping_scale == 0.0 and corner == "HIGH"
                else None
            ),
        },
        "matrix": {
            "shape": list(model["mass"].shape),
            "joint_modal_block_exact_zero": bool(
                np.count_nonzero(model["joint_modal"]) == 0
            ),
            "positive_definite_structure": model["mass_matrix_structure"],
            "all_mass_matrices_cholesky_positive_definite": model[
                "all_mass_matrices_cholesky_positive_definite"
            ],
            "diagnostic_no_spectral_credit": diagnostic_no_spectral_credit,
        },
        "primary": primary["metrics"],
        "cross": cross["metrics"],
        "solver_cross": solver_cross,
        "linearity": linearity,
        "checks": checks,
        "checks_all_pass": all(checks.values()),
        "gate_pass": gate_credit and all(checks.values()),
    }


def evaluate() -> dict[str, Any]:
    contract = load_contract()
    contract_semantics_audit = validate_contract_semantics(contract)
    contract_negative_controls = contract_tamper_negative_controls(contract)
    binding = validate_source_pins(contract)
    if not binding["all_match"]:
        return {
            "schema": "DG3_ARM_FLEX_COUPLING_EVIDENCE_V1",
            "technical_verdict": "SOURCE_HASH_DRIFT__FAIL_CLOSED",
            "source_binding": binding,
            "contract_semantics_audit": contract_semantics_audit,
            "contract_tamper_negative_controls": contract_negative_controls,
            "candidate_pass": False,
            "parent_DG3_satisfied": False,
            "parent_DG3_complete": False,
            "dynamics_engineering_complete": False,
            "hardware_valid": False,
            "production_valid": False,
            "next_stage_authorized": False,
            "release_credit": False,
        }

    backend = load_backend(ROOT)
    q0 = _vector(contract["frozen_linearization"]["q0_mixed_rad_m"], 8, "Q0")
    amplitude = _vector(
        contract["prescribed_excitation"]["amplitude_mixed_rad_m"],
        8,
        "AMPLITUDE",
    )
    rom = np.load(_pin_path(contract, "round4_rom_npz"))
    rom_document = load_json(_pin_path(contract, "round4_rom_contract"))
    envelope = load_json(_pin_path(contract, "round4_validity_envelope"))
    mass_ledger = yaml.safe_load(
        _pin_path(contract, "r2_mass_ledger").read_text(encoding="utf-8")
    )
    frame_tree = yaml.safe_load(
        _pin_path(contract, "unified_r2_frame_tree").read_text(encoding="utf-8")
    )
    frame_bridge = yaml.safe_load(
        _pin_path(contract, "mpi_frame_bridge").read_text(encoding="utf-8")
    )
    e23_source_text = _pin_path(contract, "e23_model_source").read_text(
        encoding="utf-8"
    )
    threshold = contract["thresholds"]
    round4_gate = load_json(_pin_path(contract, "round4_gate"))
    e23_gate = load_json(_pin_path(contract, "e23_gate"))
    dg12_gate = load_json(_pin_path(contract, "dg1_dg2_gate"))
    mpi_gate = load_json(_pin_path(contract, "mpi_bridge_gate"))

    corner_bindings = contract["corner_semantics"]["bindings"]
    expected_corner_parameters = {
        corner: corner_bindings[corner]["parameters"]
        for corner in ("LOW", "NOMINAL", "HIGH")
    }
    corner_semantics_checks = {
        "contract_exact_validator_passed": contract_semantics_audit["checks"][
            "corner_semantics_exact"
        ]
        and contract_semantics_audit["checks"][
            "corner_order_exact_LOW_NOMINAL_HIGH"
        ],
        "external_validity_envelope_parameters_exact": envelope.get(
            "parameter_corners"
        )
        == expected_corner_parameters,
        "ROM_K_and_C_keys_bound_for_all_three_corners": all(
            corner_bindings[corner]["Krom_key"] in rom.files
            and corner_bindings[corner]["Crom_key"] in rom.files
            for corner in ("LOW", "NOMINAL", "HIGH")
        ),
        "all_parameter_corners_strictly_LOW_then_NOMINAL_then_HIGH": all(
            expected_corner_parameters["LOW"][parameter]
            < expected_corner_parameters["NOMINAL"][parameter]
            < expected_corner_parameters["HIGH"][parameter]
            for parameter in ("EI", "GJ", "k_root", "k_inter", "zeta")
        ),
        "bounded_deterministic_not_probabilistic_semantics_exact": contract[
            "corner_semantics"
        ]["uncertainty_method"]
        == "BOUNDED_DETERMINISTIC_ALL_PARAMETER_CORNERS__NOT_PROBABILISTIC_STANDARD_UNCERTAINTY"
        and contract["corner_semantics"]["correlation_assumption"]
        == "LOW_AND_HIGH_ARE_CONSERVATIVE_ALL_PARAMETER_CORNERS__NO_INDEPENDENCE_CLAIM",
    }
    corner_semantics_audit = {
        "schema": "DG3_LOW_NOMINAL_HIGH_CORNER_SEMANTICS_AUDIT_V1",
        "order": ["LOW", "NOMINAL", "HIGH"],
        "parameter_units": contract["corner_semantics"]["parameter_units"],
        "checks": corner_semantics_checks,
        "pass": all(corner_semantics_checks.values()),
    }

    rom_structure_audit = audit_rom_structure(contract, rom, rom_document)
    nominal_model = assemble_model(backend, rom, q0, "NOMINAL")
    urdf_frame_audit = audit_unified_urdf_and_frames(
        contract,
        backend,
        q0,
        nominal_model,
        mass_ledger,
        envelope,
        frame_tree,
        frame_bridge,
        e23_source_text,
    )

    limits = _joint_limits(backend)
    times = np.linspace(
        0.0,
        float(contract["prescribed_excitation"]["duration_s"]),
        int(contract["prescribed_excitation"]["samples"]),
    )
    q_history = np.asarray(
        [
            joint_motion(
                float(time_s),
                q0,
                amplitude,
                float(contract["prescribed_excitation"]["frequency_hz"]),
            )[0]
            for time_s in times
        ]
    )
    lower_margins = q_history - limits[:, 0]
    upper_margins = limits[:, 1] - q_history
    joint_margin_revolute_rad = float(
        min(np.min(lower_margins[:, :6]), np.min(upper_margins[:, :6]))
    )
    joint_margin_prismatic_m = float(
        min(np.min(lower_margins[:, 6:]), np.min(upper_margins[:, 6:]))
    )

    undamped_coupling_lanes = [
        _forced_lane(
            backend,
            rom,
            envelope,
            contract,
            q0,
            amplitude,
            corner,
            0.0,
            "C0_UNDAMPED_PRESCRIBED_ARM_COUPLING_GATE_LANE",
            True,
        )
        for corner in contract["corners"]
    ]
    damped_sensitivity_diagnostics = [
        _forced_lane(
            backend,
            rom,
            envelope,
            contract,
            q0,
            amplitude,
            corner,
            1.0,
            "DAMPED_LOW_NOMINAL_HIGH_SENSITIVITY_DESIGN_DIAGNOSTIC_ONLY",
            False,
        )
        for corner in contract["corners"]
    ]

    conservative_contract = contract["conservative_free_response"]
    conservative_model = assemble_model(
        backend,
        rom,
        q0,
        conservative_contract["corner"],
        damping_scale=float(conservative_contract["damping_scale"]),
    )
    conservative_amplitude = _vector(
        conservative_contract["joint_amplitude_mixed_rad_m"],
        8,
        "CONSERVATIVE_AMPLITUDE",
    )
    conservative_initial = conservative_initial_state(
        conservative_model,
        np.asarray(conservative_contract["initial_eta"], dtype=float),
        np.asarray(conservative_contract["initial_eta_rate_per_s"], dtype=float),
    )
    conservative_primary = solve_case(
        conservative_model,
        q0,
        conservative_amplitude,
        contract["prescribed_excitation"],
        contract["solvers"],
        "Radau",
        initial_state=conservative_initial,
    )
    conservative_cross = solve_case(
        conservative_model,
        q0,
        conservative_amplitude,
        contract["prescribed_excitation"],
        contract["solvers"],
        "BDF",
        initial_state=conservative_initial,
    )
    conservative_solver_cross = _cross_metrics(
        conservative_primary, conservative_cross
    )
    conservative_checks = {
        "all_solve_mass_matrices_Cholesky_positive_definite": conservative_model[
            "all_mass_matrices_cholesky_positive_definite"
        ],
        "C_matrix_exact_zero": float(
            np.max(np.abs(conservative_model["damping"]))
        )
        == 0.0,
        "joint_motion_and_external_work_exact_zero": float(
            np.max(np.abs(conservative_amplitude))
        )
        == 0.0
        and abs(conservative_primary["metrics"]["actuator_work_final_J"])
        <= 1.0e-20
        and abs(conservative_primary["metrics"]["damping_dissipation_final_J"])
        <= 1.0e-20,
        "total_energy_conserved": conservative_primary["metrics"][
            "total_energy_conservation_relative_peak"
        ]
        <= threshold["conservative_energy_relative_max"],
        "canonical_linear_momentum_conserved": conservative_primary["metrics"][
            "canonical_base_linear_momentum_residual_max_kg_m_s"
        ]
        <= threshold["canonical_linear_momentum_residual_max_kg_m_s"],
        "canonical_angular_momentum_conserved": conservative_primary["metrics"][
            "canonical_base_angular_momentum_residual_max_kg_m2_s"
        ]
        <= threshold["canonical_angular_momentum_residual_max_kg_m2_s"],
        "initial_canonical_base_momentum_zero": max(
            abs(float(value))
            for value in conservative_primary["metrics"][
                "canonical_base_momentum_initial"
            ]
        )
        <= max(
            threshold["canonical_linear_momentum_residual_max_kg_m_s"],
            threshold["canonical_angular_momentum_residual_max_kg_m2_s"],
        ),
        "Radau_BDF_base_position_cross": conservative_solver_cross[
            "base_translation_max_abs_m"
        ]
        <= threshold["solver_base_translation_cross_max_m"],
        "Radau_BDF_base_attitude_cross": conservative_solver_cross[
            "base_rotation_max_abs_rad"
        ]
        <= threshold["solver_base_rotation_cross_max_rad"],
        "Radau_BDF_base_linear_rate_cross": conservative_solver_cross[
            "base_linear_rate_max_abs_m_s"
        ]
        <= threshold["solver_base_linear_rate_cross_max_m_s"],
        "Radau_BDF_base_angular_rate_cross": conservative_solver_cross[
            "base_angular_rate_max_abs_rad_s"
        ]
        <= threshold["solver_base_angular_rate_cross_max_rad_s"],
        "Radau_BDF_eta_relative": conservative_solver_cross["eta_relative"]
        <= threshold["solver_eta_relative_max"],
        "Radau_BDF_eta_rate_relative": conservative_solver_cross[
            "eta_rate_relative"
        ]
        <= threshold["solver_eta_rate_relative_max"],
    }
    conservative_lane = {
        "lane_class": "C0_UNFORCED_CONSERVATIVE_FREE_RESPONSE_GATE_LANE",
        "corner": conservative_contract["corner"],
        "damping_scale": 0.0,
        "external_work_J": 0.0,
        "initial_state_rule": conservative_contract["initial_base_rate_rule"],
        "primary": conservative_primary["metrics"],
        "cross": conservative_cross["metrics"],
        "solver_cross_by_declared_dimension": conservative_solver_cross,
        "mass_matrix_positive_definite_structure": conservative_model[
            "mass_matrix_structure"
        ],
        "checks": conservative_checks,
        "pass": all(conservative_checks.values()),
    }

    rigid_mass = np.asarray(backend.tree.mass_matrix(q0), dtype=float)
    modes_removed_primary = solve_modes_removed_rigid_case(
        rigid_mass,
        q0,
        amplitude,
        contract["prescribed_excitation"],
        contract["solvers"],
        "Radau",
    )
    modes_removed_cross = solve_modes_removed_rigid_case(
        rigid_mass,
        q0,
        amplitude,
        contract["prescribed_excitation"],
        contract["solvers"],
        "BDF",
    )
    base_dimension_units = {
        "position": contract["units"]["base_position"],
        "attitude": contract["units"]["base_attitude"],
        "linear_rate": contract["units"]["base_linear_rate"],
        "angular_rate": contract["units"]["base_angular_rate"],
    }
    base_metric_keys = {
        "position": "base_translation_max_abs_m",
        "attitude": "base_rotation_max_abs_rad",
        "linear_rate": "base_linear_rate_max_abs_m_s",
        "angular_rate": "base_angular_rate_max_abs_rad_s",
    }
    modes_removed_solver_cross_metrics = _base_state_cross_metrics(
        np.asarray(modes_removed_primary["history"]),
        np.asarray(modes_removed_cross["history"]),
    )
    modes_removed_solver_cross = _dimension_gate_records(
        modes_removed_solver_cross_metrics,
        {
            "position": "modes_removed_solver_position_cross_max_m",
            "attitude": "modes_removed_solver_attitude_cross_max_rad",
            "linear_rate": "modes_removed_solver_linear_rate_cross_max_m_s",
            "angular_rate": "modes_removed_solver_angular_rate_cross_max_rad_s",
        },
        base_metric_keys,
        base_dimension_units,
        contract,
    )
    modes_removed_analytic = _dimension_gate_records(
        modes_removed_primary["metrics"],
        {
            "position": "modes_removed_analytic_position_max_m",
            "attitude": "modes_removed_analytic_attitude_max_rad",
            "linear_rate": "modes_removed_analytic_linear_rate_max_m_s",
            "angular_rate": "modes_removed_analytic_angular_rate_max_rad_s",
        },
        {
            "position": "analytic_base_position_max_abs_m",
            "attitude": "analytic_base_attitude_max_abs_rad",
            "linear_rate": "analytic_base_linear_rate_max_abs_m_s",
            "angular_rate": "analytic_base_angular_rate_max_abs_rad_s",
        },
        base_dimension_units,
        contract,
    )
    modes_removed_checks = {
        "modal_DOF_exactly_removed": modes_removed_primary["modal_dof"] == 0
        and modes_removed_primary["state_dimension"] == 12
        and modes_removed_primary["mass_matrix_shape"] == [14, 14],
        "all_solve_mass_matrices_Cholesky_positive_definite": modes_removed_primary[
            "all_mass_matrices_cholesky_positive_definite"
        ]
        and modes_removed_cross["all_mass_matrices_cholesky_positive_definite"],
        "analytic_position_m": modes_removed_analytic["position"]["pass"],
        "analytic_attitude_rad": modes_removed_analytic["attitude"]["pass"],
        "analytic_linear_rate_m_s": modes_removed_analytic["linear_rate"]["pass"],
        "analytic_angular_rate_rad_s": modes_removed_analytic["angular_rate"]["pass"],
        "canonical_linear_momentum_conserved": modes_removed_primary["metrics"][
            "canonical_base_linear_momentum_residual_max_kg_m_s"
        ]
        <= threshold["canonical_linear_momentum_residual_max_kg_m_s"],
        "canonical_angular_momentum_conserved": modes_removed_primary["metrics"][
            "canonical_base_angular_momentum_residual_max_kg_m2_s"
        ]
        <= threshold["canonical_angular_momentum_residual_max_kg_m2_s"],
        "Radau_BDF_position_m": modes_removed_solver_cross["position"]["pass"],
        "Radau_BDF_attitude_rad": modes_removed_solver_cross["attitude"]["pass"],
        "Radau_BDF_linear_rate_m_s": modes_removed_solver_cross["linear_rate"]["pass"],
        "Radau_BDF_angular_rate_rad_s": modes_removed_solver_cross[
            "angular_rate"
        ]["pass"],
    }
    modes_removed_lane = {
        "lane_class": "TRUE_MODES_REMOVED_CONSTRAINED_RIGID_GATE_LANE",
        "definition": modes_removed_primary["lane_definition"],
        "primary": modes_removed_primary["metrics"],
        "cross": modes_removed_cross["metrics"],
        "analytic_cross_by_declared_dimension": modes_removed_analytic,
        "Radau_BDF_cross_by_declared_dimension": modes_removed_solver_cross,
        "mass_matrix_positive_definite_structure": {
            "primary": modes_removed_primary["mass_matrix_structure"],
            "cross": modes_removed_cross["mass_matrix_structure"],
        },
        "checks": modes_removed_checks,
        "pass": all(modes_removed_checks.values()),
    }

    zero_coupling_model = assemble_model(
        backend,
        rom,
        q0,
        "NOMINAL",
        coupling_scale=0.0,
        damping_scale=0.0,
    )
    zero_coupling = solve_case(
        zero_coupling_model,
        q0,
        amplitude,
        contract["prescribed_excitation"],
        contract["solvers"],
        "Radau",
    )
    zero_coupling_history = np.asarray(zero_coupling["history"])
    zero_coupling_vs_modes_removed_metrics = _base_state_cross_metrics(
        zero_coupling_history[:, :12],
        np.asarray(modes_removed_primary["history"]),
    )
    zero_coupling_vs_modes_removed = _dimension_gate_records(
        zero_coupling_vs_modes_removed_metrics,
        {
            "position": "zero_coupling_vs_modes_removed_position_cross_max_m",
            "attitude": "zero_coupling_vs_modes_removed_attitude_cross_max_rad",
            "linear_rate": "zero_coupling_vs_modes_removed_linear_rate_cross_max_m_s",
            "angular_rate": "zero_coupling_vs_modes_removed_angular_rate_cross_max_rad_s",
        },
        base_metric_keys,
        base_dimension_units,
        contract,
    )
    zero_motion_model = assemble_model(
        backend, rom, q0, "NOMINAL", damping_scale=0.0
    )
    zero_motion_rhs = _rhs(
        zero_motion_model,
        q0,
        np.zeros(8),
        float(contract["prescribed_excitation"]["frequency_hz"]),
    )(0.0, np.zeros(42))
    falsifiers = {
        "zero_motion_rhs_all_components_exact_zero": bool(
            np.count_nonzero(zero_motion_rhs) == 0
        ),
        "zero_coupling_eta_max_abs": float(
            np.max(np.abs(zero_coupling_history[:, 12:26]))
        ),
        "zero_coupling_eta_rate_max_per_s": float(
            np.max(np.abs(zero_coupling_history[:, 26:40]))
        ),
        "zero_coupling_vs_true_modes_removed_by_declared_dimension": zero_coupling_vs_modes_removed,
        "joint_limit_revolute_minimum_margin_rad": joint_margin_revolute_rad,
        "joint_limit_prismatic_minimum_margin_m": joint_margin_prismatic_m,
    }
    falsifier_checks = {
        "zero_motion_stays_exactly_zero": falsifiers[
            "zero_motion_rhs_all_components_exact_zero"
        ],
        "zero_coupling_eta_response_eliminated": falsifiers[
            "zero_coupling_eta_max_abs"
        ]
        <= threshold["zero_coupling_eta_max_abs"],
        "zero_coupling_eta_rate_response_eliminated": falsifiers[
            "zero_coupling_eta_rate_max_per_s"
        ]
        <= threshold["zero_coupling_eta_rate_max_per_s"],
        "zero_coupling_matches_modes_removed_position_m": zero_coupling_vs_modes_removed[
            "position"
        ]["pass"],
        "zero_coupling_matches_modes_removed_attitude_rad": zero_coupling_vs_modes_removed[
            "attitude"
        ]["pass"],
        "zero_coupling_matches_modes_removed_linear_rate_m_s": zero_coupling_vs_modes_removed[
            "linear_rate"
        ]["pass"],
        "zero_coupling_matches_modes_removed_angular_rate_rad_s": zero_coupling_vs_modes_removed[
            "angular_rate"
        ]["pass"],
        "zero_coupling_and_zero_motion_mass_matrices_Cholesky_positive_definite": zero_coupling_model[
            "all_mass_matrices_cholesky_positive_definite"
        ]
        and zero_motion_model["all_mass_matrices_cholesky_positive_definite"],
        "revolute_joint_limits_respected": joint_margin_revolute_rad
        >= threshold["joint_limit_revolute_minimum_margin_rad"],
        "prismatic_joint_limits_respected": joint_margin_prismatic_m
        >= threshold["joint_limit_prismatic_minimum_margin_m"],
    }
    zero_coupling_falsifier = {
        "lane_class": "ZERO_BASE_MODAL_COUPLING_FALSIFIER__MODES_RETAINED",
        "modal_DOF_retained": 14,
        "coupling_scale": 0.0,
        "metrics": {
            "eta_max_abs": {
                "value": falsifiers["zero_coupling_eta_max_abs"],
                "threshold": threshold["zero_coupling_eta_max_abs"],
                "unit": contract["units"]["modal_coordinate"],
            },
            "eta_rate_max_per_s": {
                "value": falsifiers["zero_coupling_eta_rate_max_per_s"],
                "threshold": threshold["zero_coupling_eta_rate_max_per_s"],
                "unit": contract["units"]["modal_rate"],
            },
            "base_cross_vs_true_modes_removed_by_declared_dimension": zero_coupling_vs_modes_removed,
        },
        "mass_matrix_positive_definite_structure": zero_coupling_model[
            "mass_matrix_structure"
        ],
        "explicit_non_equivalence": "THIS_IS_NOT_THE_MODES_REMOVED_RIGID_LANE",
    }

    authority_checks = {
        "round4_ROM_gate_17_of_17_provisional": round4_gate.get(
            "technical_verdict"
        )
        == "PASS_WITH_DECLARED_PROVISIONAL_PHYSICS"
        and round4_gate.get("summary") == {"passed": 17, "total": 17},
        "E23_gate_18_of_18_provisional_but_not_numerically_inherited": e23_gate.get(
            "technical_verdict"
        )
        == "PASS_WITH_DECLARED_PROVISIONAL_PHYSICS"
        and e23_gate.get("summary", {}).get("passed") == 18
        and e23_gate.get("summary", {}).get("total") == 18
        and urdf_frame_audit["representation_compatibility_audit"][
            "E23_numerical_inheritance"
        ]
        is False,
        "DG1_DG2_candidate_available": dg12_gate.get(
            "candidate_package_complete"
        )
        is True,
        "MPI_bridge_9_of_9": mpi_gate.get("mpi_gate") == "PASS"
        and mpi_gate.get("criterion_counts", {}).get("pass") == 9,
        "all_upstream_release_flags_remain_false": all(
            gate.get("next_stage_authorized") is False
            and gate.get("release_credit") is False
            for gate in (round4_gate, e23_gate, dg12_gate, mpi_gate)
        ),
    }
    spectral_policy_checks = {
        "mixed_unit_policy_exact": contract["frozen_linearization"][
            "mixed_28x28_spectral_policy"
        ]
        == "DIAGNOSTIC_NO_SPECTRAL_CREDIT__COORDINATES_HAVE_MIXED_UNITS",
        "all_spectral_records_have_zero_gate_credit": all(
            row["matrix"]["diagnostic_no_spectral_credit"]["classification"]
            == "DIAGNOSTIC_NO_SPECTRAL_CREDIT"
            and row["matrix"]["diagnostic_no_spectral_credit"]["gate_credit"]
            is False
            and row["matrix"]["diagnostic_no_spectral_credit"]["units"] is None
            and row["matrix"]["diagnostic_no_spectral_credit"][
                "numeric_spectral_values_emitted"
            ]
            is False
            and not any(
                "eigen" in key.lower() or "condition" in key.lower()
                for key in row["matrix"]["diagnostic_no_spectral_credit"]
                if key != "forbidden_numeric_fields"
            )
            for row in undamped_coupling_lanes + damped_sensitivity_diagnostics
        ),
        "undamped_LOW_NOMINAL_HIGH_order_and_count_exact": [
            row["corner"] for row in undamped_coupling_lanes
        ]
        == ["LOW", "NOMINAL", "HIGH"]
        and len(undamped_coupling_lanes) == 3,
        "damped_LOW_NOMINAL_HIGH_are_diagnostic_only": [
            row["corner"] for row in damped_sensitivity_diagnostics
        ]
        == ["LOW", "NOMINAL", "HIGH"]
        and len(damped_sensitivity_diagnostics) == 3
        and all(
            row["gate_credit"] is False
            and row["lane_class"]
            == "DAMPED_LOW_NOMINAL_HIGH_SENSITIVITY_DESIGN_DIAGNOSTIC_ONLY"
            for row in damped_sensitivity_diagnostics
        ),
    }

    execution_guards_clear = all(
        value is False for value in contract["execution_guards"].values()
    )
    mass_structure_checks = {
        "nominal_model_all_declared_mass_matrices_positive": nominal_model[
            "all_mass_matrices_cholesky_positive_definite"
        ],
        "all_undamped_solve_lanes_positive": all(
            row["checks"][
                "all_solve_mass_matrices_Cholesky_positive_definite"
            ]
            for row in undamped_coupling_lanes
        ),
        "all_damped_diagnostic_solve_lanes_positive": all(
            row["checks"][
                "all_solve_mass_matrices_Cholesky_positive_definite"
            ]
            for row in damped_sensitivity_diagnostics
        ),
        "conservative_solve_lane_positive": conservative_checks[
            "all_solve_mass_matrices_Cholesky_positive_definite"
        ],
        "modes_removed_Radau_and_BDF_positive": modes_removed_checks[
            "all_solve_mass_matrices_Cholesky_positive_definite"
        ],
        "zero_coupling_and_zero_motion_positive": falsifier_checks[
            "zero_coupling_and_zero_motion_mass_matrices_Cholesky_positive_definite"
        ],
        "no_mass_matrix_spectral_numeric_credit": all(
            audit["eigenvalue_or_condition_number_emitted"] is False
            and audit["spectral_numeric_credit"] is False
            for row in undamped_coupling_lanes + damped_sensitivity_diagnostics
            for audit in row["matrix"]["positive_definite_structure"].values()
        ),
    }
    mass_matrix_positive_definite_audit = {
        "schema": "DG3_MASS_MATRIX_CHOLESKY_STRUCTURE_AUDIT_V1",
        "method": "CHOLESKY_BOOLEAN_STRUCTURE_ONLY__NO_EIGENVALUE_CONDITION_OR_PIVOT_OUTPUT",
        "checks": mass_structure_checks,
        "pass": all(mass_structure_checks.values()),
    }
    all_pass = (
        contract_semantics_audit["pass"]
        and contract_negative_controls["all_rejected"]
        and corner_semantics_audit["pass"]
        and all(authority_checks.values())
        and rom_structure_audit["pass"]
        and urdf_frame_audit["pass"]
        and all(row["gate_pass"] for row in undamped_coupling_lanes)
        and conservative_lane["pass"]
        and modes_removed_lane["pass"]
        and all(falsifier_checks.values())
        and all(spectral_policy_checks.values())
        and mass_matrix_positive_definite_audit["pass"]
        and execution_guards_clear
    )
    return {
        "schema": "DG3_ARM_FLEX_COUPLING_EVIDENCE_V1",
        "technical_verdict": (
            "DG3_BOUNDED_C0_CONSERVATION_AND_ARM_FLEX_COUPLING_CANDIDATE_PASS__PARENT_DG3_HOLD"
            if all_pass
            else "DG3_ARM_FLEX_COUPLING_CANDIDATE_HOLD__SEE_FAILED_CHECKS"
        ),
        "source_binding": binding,
        "contract_semantics_audit": contract_semantics_audit,
        "contract_tamper_negative_controls": contract_negative_controls,
        "corner_semantics_audit": corner_semantics_audit,
        "authority_checks": authority_checks,
        "model_semantics": {
            "coordinate_order": contract["frozen_linearization"][
                "mass_matrix_order"
            ],
            "coordinate_units": {
                "base": contract["frozen_linearization"][
                    "base_coordinate_units"
                ],
                "joint": contract["frozen_linearization"]["joint_units"],
                "modal": contract["frozen_linearization"][
                    "modal_coordinate_units"
                ],
            },
            "coupling_path": "PRESCRIBED_JOINT_ACCELERATION_TO_BASE_REACTION_TO_SOLAR_MODAL_RESPONSE",
            "direct_joint_modal_mass_block": "EXACT_ZERO",
            "mass_double_counting": "FORBIDDEN__UNIFIED_R2_ALREADY_CONTAINS_BOTH_0P78KG_RIGID_WINGS",
            "time_varying_mass_and_Coriolis": "NOT_IMPLEMENTED_IN_THIS_FROZEN_TANGENT_CANDIDATE",
        },
        "rom_structure_audit": rom_structure_audit,
        "unified_urdf_mass_and_frame_audit": urdf_frame_audit,
        "representation_compatibility_audit": urdf_frame_audit[
            "representation_compatibility_audit"
        ],
        "spectral_credit_policy": {
            "classification": "DIAGNOSTIC_NO_SPECTRAL_CREDIT",
            "reason": "MIXED_UNITS_IN_28X28_COORDINATE_VECTOR",
            "checks": spectral_policy_checks,
        },
        "mass_matrix_positive_definite_audit": mass_matrix_positive_definite_audit,
        "undamped_coupling_gate_lanes": undamped_coupling_lanes,
        "damped_sensitivity_diagnostics": damped_sensitivity_diagnostics,
        "conservative_free_response_lane": conservative_lane,
        "modes_removed_constrained_rigid_lane": modes_removed_lane,
        "zero_coupling_falsifier": zero_coupling_falsifier,
        "falsifiers": falsifiers,
        "falsifier_checks": falsifier_checks,
        "execution_guards": contract["execution_guards"],
        "candidate_pass": all_pass,
        "parent_DG3_satisfied": False,
        "parent_DG3_complete": False,
        "dynamics_engineering_complete": False,
        "hardware_valid": False,
        "production_valid": False,
        "next_stage_authorized": contract["next_stage_authorized"],
        "release_credit": contract["release_credit"],
        "review_status": contract["review_status"],
    }
