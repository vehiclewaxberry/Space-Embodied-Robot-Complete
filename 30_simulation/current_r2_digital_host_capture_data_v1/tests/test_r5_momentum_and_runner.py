"""R5 unit safety, stability and immutable-runner negative controls."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from dh_v1.integrators import pack_state, rk4_run
from dh_v1.momentum_ledger_r5 import (
    LedgerContractError,
    MomentumScales,
    build_unit_safe_ledger,
    compensated_component_sum,
    compute_preintegration_scales,
    evaluate_momentum_gate_r5,
    evaluate_three_point_convergence,
    rigid_body_momentum_about_origin,
    rigid_body_momentum_from_scaled_interface,
    shift_angular_momentum_reference,
    split_spatial_momentum,
    validate_unit_scale_contract,
)
from dh_v1.plant import FloatingPlant, compose_models
from dh_v1.scen_dynamics_r5 import (
    PDControllerR5,
    _longest_true_duration,
    controller_from_config,
    rk4_step_r5,
    stability_analysis_r5,
)
from dh_v1.urdf_extract import extract_urdf

MODULE = Path(__file__).resolve().parents[1]
REPO = MODULE.parents[1]
RUNNER_PATH = MODULE / "scripts/run_r5_increment.py"
SPEC = importlib.util.spec_from_file_location("run_r5_increment", RUNNER_PATH)
RUNNER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(RUNNER)


@pytest.fixture(scope="session")
def composed_model(arm_model, servicer_urdf_path):
    servicer = extract_urdf(servicer_urdf_path)
    return compose_models(
        servicer,
        arm_model,
        "S_servicer_12U_v0",
        [0.18525, 0.0, 0.0],
        [0.0, np.pi / 2.0, 0.0],
        "mount_T_SM_ODR01_nominal_frozen_v1",
    )


@pytest.fixture(scope="session")
def composed_plant(composed_model):
    return FloatingPlant(composed_model)


@pytest.fixture(scope="session")
def controller_config():
    return yaml.safe_load(
        (MODULE / "configs/controllers/s03_pd_v1.yaml").read_text(encoding="utf-8")
    )


@pytest.fixture(scope="session")
def scenario_config():
    cfg = yaml.safe_load(
        (MODULE / "configs/scenarios/r5_s02_s03_v1.yaml").read_text(encoding="utf-8")
    )
    return {
        **cfg["s03"],
        "sample_period_target_s": cfg["sample_period_target_s"],
    }


def synthetic_samples():
    t = np.array([0.0, 0.5, 1.0])
    H = np.array([[1.0, 2.0, 3.0], [1.0 + 1e-12, 2.0, 3.0], [1.0, 2.0, 3.0]])
    P = np.array([[4.0, 5.0, 6.0], [4.0, 5.0 + 2e-12, 6.0], [4.0, 5.0, 6.0]])
    return {"t": t, "h_O": np.hstack([H, P])}


def single_body_model(mass=6.0, com=(0.0, 0.0, 0.0), inertia=(0.10, 0.18, 0.22)):
    return {
        "robot_name": "r5_analytic_single_body",
        "links": [
            {
                "name": "body",
                "inertial": {
                    "mass": mass,
                    "com": list(com),
                    "inertia_com": np.diag(inertia).tolist(),
                    "inertial_origin_rpy": [0.0, 0.0, 0.0],
                },
                "has_visual": False,
                "has_collision": False,
            }
        ],
        "joints": [],
        "provenance": {"purpose": "R5_L1_L4_ANALYTIC_FIXTURE"},
    }


def test_split_spatial_momentum_keeps_units_separate():
    H, P = split_spatial_momentum(synthetic_samples()["h_O"])
    assert H.shape == P.shape == (3, 3)
    assert np.array_equal(H[0], [1.0, 2.0, 3.0])
    assert np.array_equal(P[0], [4.0, 5.0, 6.0])


def test_unit_safe_ledger_has_two_residual_norms_and_no_six_vector_norm():
    scales = MomentumScales(10.0, 20.0, 1.0, 1.0, 1.0, 1.0, 1.0, {})
    ledger = build_unit_safe_ledger(
        synthetic_samples(),
        scales,
        np.zeros(3),
        np.zeros(3),
        [],
        external_wrench_status="FROZEN_ZERO_BY_MODEL_SCOPE",
        event_monitor_status="VERIFIED",
    )
    assert "norm_R_P_kg_m_s" in ledger and "norm_R_H_N_m_s" in ledger
    assert ledger["contract"]["no_mixed_dimension_norm"] is True
    assert ledger["metrics"]["epsilon_P_max"] == pytest.approx(2e-13, rel=1e-4)
    assert ledger["metrics"]["epsilon_H_max"] == pytest.approx(5e-14, rel=1e-4)


def test_empty_event_list_without_verified_monitor_is_rejected():
    scales = MomentumScales(10.0, 20.0, 1.0, 1.0, 1.0, 1.0, 1.0, {})
    with pytest.raises(LedgerContractError, match="VERIFIED"):
        build_unit_safe_ledger(
            synthetic_samples(),
            scales,
            np.zeros(3),
            np.zeros(3),
            [],
            external_wrench_status="FROZEN_ZERO_BY_MODEL_SCOPE",
            event_monitor_status="UNKNOWN",
        )


def test_external_force_and_torque_impulses_close_separate_ledgers():
    t = np.array([0.0, 0.5, 1.0])
    force = np.array([2.0, -1.0, 0.5])
    torque = np.array([0.2, 0.3, -0.4])
    P = t[:, None] * force
    H = t[:, None] * torque
    samples = {"t": t, "h_O": np.hstack([H, P])}
    scales = MomentumScales(1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, {})
    ledger = build_unit_safe_ledger(
        samples,
        scales,
        force,
        torque,
        [],
        external_wrench_status="EXPLICIT_HISTORY_VERIFIED",
        event_monitor_status="VERIFIED",
    )
    assert ledger["metrics"]["norm_R_P_max_kg_m_s"] < 1e-15
    assert ledger["metrics"]["norm_R_H_max_N_m_s"] < 1e-15


def test_registered_event_impulse_closes_and_unregistered_event_does_not():
    t = np.array([0.0, 0.5, 1.0])
    J = np.array([1.0, 2.0, 3.0])
    K = np.array([0.1, -0.2, 0.3])
    P = np.array([[0.0, 0.0, 0.0], J, J])
    H = np.array([[0.0, 0.0, 0.0], K, K])
    samples = {"t": t, "h_O": np.hstack([H, P])}
    scales = MomentumScales(1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, {})
    event = {
        "t_s": 0.5,
        "linear_impulse_I_kg_m_s": J,
        "angular_impulse_O_I_N_m_s": K,
    }
    closed = build_unit_safe_ledger(
        samples,
        scales,
        np.zeros(3),
        np.zeros(3),
        [event],
        external_wrench_status="FROZEN_ZERO_BY_MODEL_SCOPE",
        event_monitor_status="VERIFIED",
    )
    open_ledger = build_unit_safe_ledger(
        samples,
        scales,
        np.zeros(3),
        np.zeros(3),
        [],
        external_wrench_status="FROZEN_ZERO_BY_MODEL_SCOPE",
        event_monitor_status="VERIFIED",
    )
    assert closed["metrics"]["norm_R_P_max_kg_m_s"] == 0.0
    assert closed["metrics"]["norm_R_H_max_N_m_s"] == 0.0
    assert open_ledger["metrics"]["norm_R_P_max_kg_m_s"] > 0.0
    assert open_ledger["metrics"]["norm_R_H_max_N_m_s"] > 0.0


def test_reference_point_shift_and_interface_unit_equivalence():
    P = np.array([2.0, -3.0, 4.0])
    H_O = np.array([0.5, 1.5, -2.0])
    r_OOprime_m = np.array([0.2, -0.1, 0.4])
    H_Oprime = H_O - np.cross(r_OOprime_m, P)
    r_OOprime_mm = 1000.0 * r_OOprime_m
    P_g_mm_s = P  # 1 kg*m/s == 1e6 g*mm/s; convert explicitly below
    P_back = P_g_mm_s * 1.0e6 / 1.0e6
    H_back = H_Oprime * 1.0e9 / 1.0e9
    assert np.allclose(H_Oprime, H_O - np.cross(r_OOprime_mm / 1000.0, P_back))
    assert np.array_equal(H_back, H_Oprime)


def test_compensated_sum_is_componentwise_same_unit_only():
    values = np.array([[1.0e16, 1.0, 2.0], [1.0, 2.0, 3.0], [-1.0e16, 3.0, 4.0]])
    result = compensated_component_sum(values)
    assert np.array_equal(result, [1.0, 6.0, 9.0])
    with pytest.raises(LedgerContractError):
        compensated_component_sum(np.zeros((2, 6)))


def test_preintegration_scales_are_physical_and_positive(arm_plant):
    q = np.zeros(arm_plant.nj)
    qd = np.array([0.3, -0.2, 0.25, -0.15, 0.2, -0.1, 0.01, 0.01])
    x0 = pack_state(np.zeros(3), np.array([1.0, 0.0, 0.0, 0.0]), q, np.zeros(6), qd)
    scales = compute_preintegration_scales(arm_plant, x0, 5.0)
    assert scales.P_den_kg_m_s > 0.0
    assert scales.H_den_N_m_s > 0.0
    assert scales.source_terms["total_mass_times_L_ref_over_T_ref_kg_m_s"] > 0.0
    assert scales.as_dict()["posterior_residual_used"] is False


@pytest.mark.parametrize(
    "values,dts,mode",
    [
        ([1e-10], [1e-3], "FAIL_INSUFFICIENT_REFINEMENT_POINTS"),
        ([1e-10, 1e-11, 1e-12], [1e-3, 2e-3, 5e-4], "FAIL_INVALID_DT_ORDER"),
        ([1e-10, 1e-11, 1e-12], [4e-3, 2e-3, 0.9e-3], "FAIL_INVALID_DT_RATIO"),
    ],
)
def test_three_point_protocol_fails_closed(values, dts, mode):
    result = evaluate_three_point_convergence(values, dts, 1e-12, [3.0, 5.5])
    assert result["passed"] is False
    assert result["mode"] == mode


def test_pd_controller_is_pure_and_componentwise_units(composed_plant, controller_config):
    controller = controller_from_config(composed_plant, controller_config)
    q = controller.q_start.copy()
    qd = np.zeros(composed_plant.nj)
    first = controller.evaluate(1.0, q, qd)
    second = controller.evaluate(1.0, q, qd)
    for key in first:
        assert np.array_equal(first[key], second[key])
    assert np.allclose(
        first["effort_raw"], first["effort_P"] + first["effort_I"] + first["effort_D"]
    )
    assert np.all(first["effort_I"] == 0.0)
    assert [body.jtype for body in composed_plant.bodies[1:]] == ["revolute"] * 6 + [
        "prismatic"
    ] * 2
    assert controller_config["effort_units"] == ["N*m"] * 6 + ["N"] * 2


def test_rk4_step_matches_legacy_zero_control_one_step(arm_plant):
    q = np.zeros(arm_plant.nj)
    q[1:5] = [-1.0, -0.8, 0.3, 0.4]
    qd = np.array([0.3, -0.2, 0.25, -0.15, 0.2, -0.1, 0.01, 0.01])
    x0 = pack_state(
        np.zeros(3), np.array([1.0, 0.0, 0.0, 0.0]), q, np.zeros(6), qd
    )
    legacy = rk4_run(arm_plant, x0, 1e-3, 1e-3, sample_every=1)
    actual, stages, _ = rk4_step_r5(arm_plant, x0, 0.0, 1e-3, controller=None)
    assert len(stages) == 4
    assert np.array_equal(actual, legacy["x"][-1])


def test_saturation_duration_uses_accepted_nodes_not_four_stage_calls():
    longest, transitions = _longest_true_duration(
        np.array([False, True, True, False, True]), 0.1
    )
    assert longest == pytest.approx(0.2)
    assert transitions == 3


def test_local_stability_analysis_classifies_neutral_and_controlled_modes(
    composed_plant, controller_config, scenario_config
):
    controller = controller_from_config(composed_plant, controller_config)
    report = stability_analysis_r5(composed_plant, controller, scenario_config)
    assert report["continuous_reduced_model"]["M_eff_positive_definite"] is True
    assert report["continuous_reduced_model"]["all_modes_strictly_stable"] is True
    assert report["continuous_reduced_model"]["fastest_mode_dominant_joint_index"] == 6
    assert report["dt_analysis"][0]["actual_reduced_map_classification"] == "UNSTABLE"
    assert report["dt_analysis"][1]["actual_reduced_map_classification"] == "DECAY"
    assert report["dt_analysis"][2]["actual_reduced_map_classification"] == "DECAY"
    assert all(
        item["full_velocity_state_rk4_polynomial_classification"]["neutral"] >= 1
        for item in report["dt_analysis"]
    )
    assert report["ruling"] == "RK4_TIME_DISCRETIZATION_MECHANISM_CONFIRMED"


@pytest.mark.parametrize("bad", [".", "..", "../escape", "a/b", "C:\\escape", ""])
def test_runner_rejects_invalid_run_ids(bad):
    with pytest.raises(RUNNER.R5RunError):
        RUNNER.validate_run_id(bad)


def test_runner_rejects_output_root_escape(tmp_path):
    with pytest.raises(RUNNER.R5RunError, match="inside"):
        RUNNER.resolve_output_root(tmp_path)


def test_runner_source_manifest_is_explicit_not_git_head_only():
    manifest = RUNNER.source_manifest()
    paths = {row["path"] for row in manifest["files"]}
    assert manifest["git_target_tracked"] is False
    assert manifest["source_tree_sha256"]
    assert any(path.endswith("momentum_ledger_r5.py") for path in paths)
    assert any(path.endswith("r5_momentum_gate_v1.yaml") for path in paths)


def test_r5_source_has_no_legacy_mixed_gate_fields():
    source = (MODULE / "src/dh_v1/scen_dynamics_r5.py").read_text(encoding="utf-8")
    assert "tracking_error_settled_rad" not in source
    assert 'np.linalg.norm(samples["h_O"]' not in source
    assert "tracking_error_revolute_max_rad" in source
    assert "tracking_error_prismatic_max_m" in source


def test_frozen_dt_grids_and_scope_exclusions_are_exact():
    config = yaml.safe_load(
        (MODULE / "configs/scenarios/r5_s02_s03_v1.yaml").read_text(encoding="utf-8")
    )
    assert config["s02"]["dt_grid_s"] == [0.004, 0.002, 0.001]
    assert config["s03"]["dt_grid_s"] == [0.001, 0.0005, 0.00025]
    assert config["scope_exclusions"]["contact"] == "NOT_RUN_T_E_T_MISSING"
    assert config["scope_exclusions"]["reaction_wheels"].startswith("NOT_IN_PLANT")


def test_path_independent_plant_identity_excludes_source_path(composed_model):
    identity = RUNNER.physics_identity(composed_model)
    assert "provenance" not in identity
    text = str(identity)
    assert "F:\\" not in text and "F:/" not in text


def test_l1_stationary_system_has_zero_p_h_and_residuals():
    plant = FloatingPlant(single_body_model())
    x0 = pack_state(
        np.zeros(3),
        np.array([1.0, 0.0, 0.0, 0.0]),
        np.zeros(0),
        np.zeros(6),
        np.zeros(0),
    )
    samples = rk4_run(plant, x0, 0.01, 0.001, sample_every=1)
    ledger = build_unit_safe_ledger(
        samples,
        MomentumScales(1.0, 1.0, 1.0, 1.0, 6.0, 1.0, 0.01, {}),
        np.zeros(3),
        np.zeros(3),
        [],
        external_wrench_status="FROZEN_ZERO_BY_MODEL_SCOPE",
        event_monitor_status="VERIFIED",
    )
    for field in (
        "P_I_kg_m_s",
        "H_O_I_N_m_s",
        "R_P_I_kg_m_s",
        "R_H_O_I_N_m_s",
    ):
        assert np.array_equal(ledger[field], np.zeros_like(ledger[field]))


def test_l2_single_rigid_body_translation_matches_mass_times_velocity():
    mass = 4.2
    velocity = np.array([0.4, -0.2, 0.7])
    result = rigid_body_momentum_about_origin(
        mass, np.zeros(3), velocity, np.diag([0.2, 0.3, 0.4]), np.zeros(3)
    )
    assert np.array_equal(result["P_I_kg_m_s"], mass * velocity)
    assert np.array_equal(result["H_O_I_N_m_s"], np.zeros(3))


def test_l3_single_rigid_body_spin_matches_inertia_times_omega():
    inertia = np.diag([0.2, 0.3, 0.5])
    omega = np.array([0.4, -0.6, 0.2])
    result = rigid_body_momentum_about_origin(
        3.0, np.zeros(3), np.zeros(3), inertia, omega
    )
    assert np.array_equal(result["P_I_kg_m_s"], np.zeros(3))
    assert np.allclose(result["H_spin_I_N_m_s"], inertia @ omega)
    assert np.allclose(result["H_O_I_N_m_s"], inertia @ omega)


def test_l4_orbital_and_spin_angular_momentum_sum_about_o():
    mass = 2.5
    r = np.array([1.2, -0.4, 0.3])
    velocity = np.array([-0.2, 0.5, 0.1])
    inertia = np.diag([0.11, 0.17, 0.23])
    omega = np.array([0.3, 0.2, -0.1])
    result = rigid_body_momentum_about_origin(mass, r, velocity, inertia, omega)
    expected_orbital = np.cross(r, mass * velocity)
    expected_spin = inertia @ omega
    assert np.allclose(result["H_orbital_O_I_N_m_s"], expected_orbital)
    assert np.allclose(result["H_spin_I_N_m_s"], expected_spin)
    assert np.allclose(result["H_O_I_N_m_s"], expected_orbital + expected_spin)


def test_l5_internal_joint_motion_preserves_total_p_and_h(arm_plant):
    q = np.zeros(arm_plant.nj)
    q[1:5] = [-1.0, -0.8, 0.3, 0.4]
    qd = np.array([0.3, -0.2, 0.25, -0.15, 0.2, -0.1, 0.01, 0.01])
    x0 = pack_state(
        np.zeros(3), np.array([1.0, 0.0, 0.0, 0.0]), q, np.zeros(6), qd
    )
    samples = rk4_run(arm_plant, x0, 0.02, 0.001, sample_every=1)
    scales = compute_preintegration_scales(arm_plant, x0, 0.02)
    ledger = build_unit_safe_ledger(
        samples,
        scales,
        np.zeros(3),
        np.zeros(3),
        [],
        external_wrench_status="FROZEN_ZERO_BY_MODEL_SCOPE",
        event_monitor_status="VERIFIED",
    )
    assert not np.array_equal(samples["x"][0, 7 : 7 + arm_plant.nj], samples["x"][-1, 7 : 7 + arm_plant.nj])
    assert ledger["metrics"]["norm_R_P_max_kg_m_s"] < 1.0e-10
    assert ledger["metrics"]["norm_R_H_max_N_m_s"] < 1.0e-10


def test_l8_unregistered_event_fails_production_momentum_gate():
    t = np.array([0.0, 0.5, 1.0])
    P = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
    samples = {"t": t, "h_O": np.hstack([np.zeros((3, 3)), P])}
    ledger = build_unit_safe_ledger(
        samples,
        MomentumScales(1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, {}),
        np.zeros(3),
        np.zeros(3),
        [],
        external_wrench_status="FROZEN_ZERO_BY_MODEL_SCOPE",
        event_monitor_status="VERIFIED",
    )
    config = yaml.safe_load(
        (MODULE / "configs/gates/r5_momentum_gate_v1.yaml").read_text(encoding="utf-8")
    )["momentum"]
    ruling = evaluate_momentum_gate_r5(ledger, config)
    assert ruling["numeric_diagnostic_gates"]["G_P_BALANCE_DIAGNOSTIC"] is False
    assert ruling["threshold_authority_gate"] is False


def test_l9_reference_point_transform_multiple_states():
    H = np.array([[0.5, 1.5, -2.0], [-0.2, 0.3, 0.7], [4.0, -1.0, 2.0]])
    P = np.array([[2.0, -3.0, 4.0], [0.0, 2.0, -1.0], [-2.5, 0.5, 1.0]])
    r = np.array([0.2, -0.1, 0.4])
    shifted = shift_angular_momentum_reference(H, P, r)
    assert np.allclose(shifted, H - np.cross(np.broadcast_to(r, P.shape), P))


def test_l10_si_and_mm_g_deg_interfaces_produce_identical_p_h():
    mass = 2.0
    r = np.array([0.4, -0.3, 0.2])
    velocity = np.array([0.5, 0.1, -0.2])
    inertia = np.diag([0.02, 0.03, 0.05])
    omega = np.array([0.4, -0.2, 0.1])
    si = rigid_body_momentum_from_scaled_interface(
        mass_value=mass,
        com_position_value=r,
        com_velocity_value=velocity,
        inertia_com_value=inertia,
        omega_value=omega,
        length_to_m=1.0,
        mass_to_kg=1.0,
        time_to_s=1.0,
        angle_to_rad=1.0,
        inertia_to_kg_m2=1.0,
    )
    non_si = rigid_body_momentum_from_scaled_interface(
        mass_value=mass * 1.0e3,
        com_position_value=r * 1.0e3,
        com_velocity_value=velocity * 1.0e3,
        inertia_com_value=inertia * 1.0e9,
        omega_value=np.rad2deg(omega),
        length_to_m=1.0e-3,
        mass_to_kg=1.0e-3,
        time_to_s=1.0,
        angle_to_rad=np.pi / 180.0,
        inertia_to_kg_m2=1.0e-9,
    )
    for field in ("P_I_kg_m_s", "H_O_I_N_m_s"):
        assert np.allclose(non_si[field], si[field], rtol=0.0, atol=1.0e-15)


def test_l11_wrong_inertia_scaling_fails_closed():
    with pytest.raises(LedgerContractError, match="FAIL_UNIT_INCONSISTENCY"):
        validate_unit_scale_contract(
            length_to_m=1.0e-3,
            mass_to_kg=1.0e-3,
            time_to_s=1.0,
            angle_to_rad=np.pi / 180.0,
            inertia_to_kg_m2=1.0e-6,
        )


def test_l12_mixed_momentum_gate_field_is_rejected():
    ledger = build_unit_safe_ledger(
        synthetic_samples(),
        MomentumScales(10.0, 20.0, 1.0, 1.0, 1.0, 1.0, 1.0, {}),
        np.zeros(3),
        np.zeros(3),
        [],
        external_wrench_status="FROZEN_ZERO_BY_MODEL_SCOPE",
        event_monitor_status="VERIFIED",
    )
    with pytest.raises(LedgerContractError, match="mixed-dimension"):
        evaluate_momentum_gate_r5(
            ledger,
            {"epsilon_P_max": 1e-9, "epsilon_H_max": 1e-9, "epsilon_PH": 1e-9},
        )


def test_l13_existing_run_directory_fails_before_execution(tmp_path):
    existing = tmp_path / "already-there"
    existing.mkdir()
    with pytest.raises(RUNNER.R5RunError, match="FAIL_OUTPUT_DIRECTORY_ALREADY_EXISTS"):
        RUNNER.assert_new_output_directory(existing)


@pytest.mark.parametrize(
    "missing_hash",
    [
        "plant_physics_sha256",
        "controller_config_sha256",
        "safe_threshold_sha256",
        "all_production_source_sha256",
    ],
)
def test_l14_manifest_missing_authority_hash_fails_closed(missing_hash):
    manifest = {field: "VALUE" for field in RUNNER.R5_MANIFEST_REQUIRED_FIELDS}
    for field in RUNNER.R5_MANIFEST_REQUIRED_HASHES:
        manifest[field] = "a" * 64
    manifest.update(
        {
            "dt_s": 0.001,
            "duration_s": 1.0,
            "seed": 1,
            "terminal_status": "COMPLETE",
        }
    )
    manifest.pop(missing_hash)
    with pytest.raises(RUNNER.R5RunError, match="FAIL_MANIFEST_INCOMPLETE"):
        RUNNER.validate_r5_episode_manifest(manifest)


def test_l15_three_point_refinement_accepts_exact_grid_and_rejects_duplicate():
    passed = evaluate_three_point_convergence(
        [1.0e-6, 6.25e-8, 3.90625e-9], [0.004, 0.002, 0.001], 1.0e-12, [3.0, 5.5]
    )
    duplicate = evaluate_three_point_convergence(
        [1.0e-6, 6.25e-8, 3.90625e-9], [0.004, 0.002, 0.002], 1.0e-12, [3.0, 5.5]
    )
    assert passed["passed"] is True
    assert duplicate["passed"] is False
    assert duplicate["mode"] == "FAIL_INVALID_DT_ORDER"


@pytest.mark.parametrize("missing", ["effort_raw", "effort_limited", "was_clipped"])
def test_l16_missing_torque_field_cannot_be_complete(composed_model, composed_plant, missing):
    joint_contract = RUNNER.movable_joint_contract(composed_model, composed_plant)
    frame = RUNNER.zero_controller_dataframe(np.array([0.0, 0.001]), 0.001, joint_contract)
    frame = frame.drop(columns=[missing])
    with pytest.raises(RUNNER.R5RunError, match="FAIL_TORQUE_TIMESERIES_INCOMPLETE"):
        RUNNER.validate_torque_timeseries(frame, joint_contract)


def test_r5_atomic_success_package_has_exact_required_files_and_cannot_overwrite(
    tmp_path, monkeypatch
):
    canonical_base = tmp_path / "12_results" / "R5"
    monkeypatch.setattr(RUNNER, "CANONICAL_R5_BASE", canonical_base.resolve())
    joint_contract = [
        {
            "joint_index": 1,
            "joint_name": "joint1",
            "joint_type": "revolute",
            "coordinate_unit": "rad",
            "rate_unit": "rad/s",
            "effort_unit": "N*m",
        }
    ]
    manifest = {field: "VALUE" for field in RUNNER.R5_MANIFEST_REQUIRED_FIELDS}
    for field in RUNNER.R5_MANIFEST_REQUIRED_HASHES:
        manifest[field] = "a" * 64
    manifest.update(
        {
            "schema": "R5_EPISODE_MANIFEST_V2",
            "run_id": "TEST_BATCH",
            "episode_id": "TEST_EPISODE",
            "scenario_id": "S02_TEST",
            "case_id": "C01",
            "seed": 1,
            "dt_s": 0.001,
            "dt_schedule_id": "TEST_GRID",
            "duration_s": 0.001,
            "start_utc": "2026-08-27T00:00:00+00:00",
            "end_utc": "2026-08-27T00:00:01+00:00",
            "terminal_status": "COMPLETE",
            "resolved_episode_config_sha256": "b" * 64,
        }
    )
    torque = RUNNER.zero_controller_dataframe(np.array([0.0]), 0.001, joint_contract)
    lifecycle = RUNNER.preopen_episode_lifecycle(
        run_id="TEST_BATCH",
        episode_id="TEST_EPISODE",
        scenario_id="S02_TEST",
        case_id="C01",
        planned_config={"dt_s": 0.001, "test_only": True},
        all_production_source_sha256="a" * 64,
    )
    aggregate, canonical = RUNNER.write_episode(
        tmp_path / "batch" / "episodes",
        "TEST_EPISODE",
        manifest,
        {"authority": "TEST"},
        {"resolved": True},
        [],
        pd.DataFrame({"t_s": [0.0]}),
        {"numeric": "TEST"},
        {"formal": "HOLD_TEST_ONLY"},
        [{"path": "source.py", "bytes": 1, "sha256": "c" * 64}],
        {"python": "TEST"},
        {"controller": "C0"},
        {"safe": "NOT_EVALUATED"},
        {"schema": "TEST_LEDGER", "joint_contract": joint_contract},
        {"status": "TEST"},
        torque,
        lifecycle=lifecycle,
    )
    assert aggregate.is_dir() and canonical.is_dir()
    assert all((canonical / name).is_file() for name in RUNNER.R5_REQUIRED_PACKAGE_FILES)
    assert (canonical / "HASH_MANIFEST.csv").is_file()
    assert lifecycle["terminal_status"] == "COMPLETE"
    assert lifecycle["atomic_publish"] is True
    assert json.loads((canonical / "RUN_MANIFEST.json").read_text(encoding="utf-8"))[
        "lifecycle_contract"
    ]["preopened_before_integration"] is True
    assert not (canonical / "INCOMPLETE_RUN_MARKER.json").exists()
    assert not any(path.name.startswith(".") and ".tmp-" in path.name for path in canonical.parent.iterdir())
    with pytest.raises(RUNNER.R5RunError, match="FAIL_OUTPUT_DIRECTORY_ALREADY_EXISTS"):
        RUNNER.publish_episode_atomically(aggregate, manifest)


def test_r5_failure_lifecycle_is_preopened_and_failure_package_is_retained(
    tmp_path, monkeypatch
):
    canonical_base = tmp_path / "12_results" / "R5"
    monkeypatch.setattr(RUNNER, "CANONICAL_R5_BASE", canonical_base.resolve())
    lifecycle = RUNNER.preopen_episode_lifecycle(
        run_id="TEST_FAILURE_BATCH",
        episode_id="TEST_FAILURE_EPISODE",
        scenario_id="S03_TEST",
        case_id="C_FAILURE",
        planned_config={"dt_s": 0.002, "test_only": True},
        all_production_source_sha256="d" * 64,
    )
    marker_path = lifecycle["temp_path"] / "INCOMPLETE_RUN_MARKER.json"
    assert marker_path.is_file()
    marker_before = json.loads(marker_path.read_text(encoding="utf-8"))
    assert marker_before["preopened_before_integration"] is True
    assert [item["state"] for item in marker_before["state_history"]] == [
        "CREATED",
        "PREEXEC_PASS",
        "RUNNING",
    ]

    failure_path = RUNNER.fail_episode_lifecycle(
        lifecycle, RuntimeError("synthetic integration failure")
    )
    assert failure_path is not None and failure_path.is_dir()
    assert not lifecycle["temp_path"].exists()
    marker_after = json.loads(
        (failure_path / "INCOMPLETE_RUN_MARKER.json").read_text(encoding="utf-8")
    )
    failure_context = json.loads(
        (failure_path / "FAILURE_CONTEXT.json").read_text(encoding="utf-8")
    )
    failure_manifest = json.loads(
        (failure_path / "RUN_MANIFEST.json").read_text(encoding="utf-8")
    )
    assert marker_after["terminal_status"] == "FAILED"
    assert marker_after["success_credit"] is False
    assert marker_after["state_history"][-1]["state"] == "FAILED"
    assert failure_context["partial_artifacts_preserved"] is True
    assert failure_manifest["partial_package"] is True
    assert failure_manifest["terminal_status"] == "FAILED"


def test_r5_verdict_is_composed_from_current_lifecycle_and_authority_conditions():
    conditions = {
        "FAILURE_LIFECYCLE_PREOPEN_AND_ATOMIC_PUBLISH": True,
        "THRESHOLD_AUTHORITY_BOUND": False,
        "OTHER_REQUIRED_CONDITION": True,
    }
    verdict = RUNNER.r5_gate_verdict(conditions)
    assert "THRESHOLD_AUTHORITY_HOLD" in verdict
    assert "VERSIONED_RUNNER_FAILURE_LIFECYCLE_PASS" in verdict
    assert "VERSIONED_RUNNER_FAILURE_LIFECYCLE_HOLD" not in verdict

    conditions["FAILURE_LIFECYCLE_PREOPEN_AND_ATOMIC_PUBLISH"] = False
    verdict = RUNNER.r5_gate_verdict(conditions)
    assert "VERSIONED_RUNNER_FAILURE_LIFECYCLE_HOLD" in verdict
