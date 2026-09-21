"""Tests for the Sim13 V2 source-only free-floating momentum backend."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import numpy as np
import pytest
import yaml


HERE = Path(__file__).resolve()
V2_ROOT = HERE.parents[1]
PROJECT_ROOT = HERE.parents[4]
MODULE_PATH = V2_ROOT / "sim13_v2" / "free_floating_dynamics.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


dynamics = _load_module(MODULE_PATH, "sim13_v2_free_floating_dynamics_under_test")


def _inertial_xml(mass: float, com: tuple[float, float, float], inertia: tuple[float, float, float]) -> str:
    return f"""
      <inertial>
        <origin xyz="{com[0]} {com[1]} {com[2]}" rpy="0 0 0"/>
        <mass value="{mass}"/>
        <inertia ixx="{inertia[0]}" ixy="0" ixz="0"
                 iyy="{inertia[1]}" iyz="0" izz="{inertia[2]}"/>
      </inertial>
    """


def _synthetic_tree_bytes() -> bytes:
    xml = f"""
    <robot name="synthetic_free_flyer">
      <link name="base">{_inertial_xml(8.0, (0.05, -0.02, 0.01), (0.8, 0.9, 1.0))}</link>
      <link name="audit_frame"/>
      <link name="arm">{_inertial_xml(2.0, (0.35, 0.02, 0.0), (0.05, 0.06, 0.07))}</link>
      <link name="slider">{_inertial_xml(0.8, (0.08, 0.0, 0.01), (0.008, 0.009, 0.010))}</link>
      <joint name="base_to_audit" type="fixed">
        <parent link="base"/><child link="audit_frame"/>
        <origin xyz="0.1 0 0" rpy="0 0 0.2"/>
      </joint>
      <joint name="shoulder" type="revolute">
        <parent link="audit_frame"/><child link="arm"/>
        <origin xyz="0.2 0.0 0.1" rpy="0.1 -0.2 0.3"/>
        <axis xyz="0 0 2"/>
        <limit lower="-2" upper="2" effort="1" velocity="1"/>
      </joint>
      <joint name="finger" type="prismatic">
        <parent link="arm"/><child link="slider"/>
        <origin xyz="0.7 0 0" rpy="0 0.2 0"/>
        <axis xyz="1 0 0"/>
        <limit lower="0" upper="0.1" effort="1" velocity="1"/>
      </joint>
    </robot>
    """
    return xml.encode("utf-8")


@pytest.fixture(scope="module")
def synthetic_model():
    return dynamics.URDFTreeDynamics(_synthetic_tree_bytes())


def test_synthetic_tree_topology_and_fixed_joint_not_in_state(synthetic_model):
    assert synthetic_model.link_count == 4
    assert synthetic_model.joint_count == 3
    assert synthetic_model.physical_link_count == 3
    assert synthetic_model.frame_only_link_names == ("audit_frame",)
    assert synthetic_model.movable_joint_names == ("shoulder", "finger")
    assert synthetic_model.movable_dof == 2
    assert "base_to_audit" not in synthetic_model.movable_joint_names
    assert synthetic_model.backend_scope == (
        "PRESCRIBED_JOINT_MOTION_MOMENTUM_PREBIND_NOT_TORQUE_DRIVEN_NOT_CONTACT"
    )
    assert dynamics.PRODUCTION_DYNAMICS_GATE_PASSED is False


def test_mass_matrix_is_symmetric_positive_definite(synthetic_model):
    matrix = synthetic_model.mass_matrix((0.31, 0.025))
    assert matrix.shape == (8, 8)
    np.testing.assert_allclose(matrix, matrix.T, atol=1.0e-13, rtol=0.0)
    assert np.min(np.linalg.eigvalsh(matrix)) > 0.0
    blocks = synthetic_model.mass_matrix_blocks((0.31, 0.025))
    np.testing.assert_allclose(blocks.Hbm, blocks.Hmb.T, atol=1.0e-13, rtol=0.0)


def test_com_linear_jacobians_match_finite_difference_kinematics(synthetic_model):
    q = np.array((0.31, 0.025))
    bodies = {body.link_name: body for body in synthetic_model.body_kinematics(q)}
    epsilon = 1.0e-7
    for link_name in ("arm", "slider"):
        for joint_index in range(synthetic_model.movable_dof):
            q_plus = q.copy()
            q_minus = q.copy()
            q_plus[joint_index] += epsilon
            q_minus[joint_index] -= epsilon
            plus = {
                body.link_name: body for body in synthetic_model.body_kinematics(q_plus)
            }[link_name].com_root_m
            minus = {
                body.link_name: body for body in synthetic_model.body_kinematics(q_minus)
            }[link_name].com_root_m
            finite_difference = (plus - minus) / (2.0 * epsilon)
            np.testing.assert_allclose(
                bodies[link_name].linear_jacobian[:, 6 + joint_index],
                finite_difference,
                atol=3.0e-9,
                rtol=2.0e-8,
            )


def test_zero_qdot_implies_zero_base_twist(synthetic_model):
    base = synthetic_model.base_twist_for_zero_momentum((0.2, 0.01), (0.0, 0.0))
    np.testing.assert_allclose(base, np.zeros(6), atol=1.0e-15, rtol=0.0)


def test_prescribed_joint_motion_closes_total_momentum(synthetic_model):
    q = (0.42, 0.035)
    qdot = (0.33, -0.012)
    base = synthetic_model.base_twist_for_zero_momentum(q, qdot)
    momentum = synthetic_model.momentum(q, base, qdot)
    assert np.linalg.norm(momentum.vector6) < 2.0e-14
    assert synthetic_model.kinetic_energy_j(q, base, qdot) > 0.0


def test_mass_matrix_momentum_matches_direct_body_sum(synthetic_model):
    q = (0.27, 0.018)
    qdot = np.array((0.21, -0.015))
    base = np.array((0.02, -0.03, 0.01, 0.04, -0.015, 0.025))
    velocity = np.concatenate((base, qdot))
    linear = np.zeros(3)
    angular = np.zeros(3)
    for body in synthetic_model.body_kinematics(q):
        com_velocity = body.linear_jacobian @ velocity
        angular_velocity = body.angular_jacobian @ velocity
        linear += body.mass_kg * com_velocity
        angular += np.cross(body.com_root_m, body.mass_kg * com_velocity)
        angular += body.inertia_root_kg_m2 @ angular_velocity
    assembled = synthetic_model.momentum(q, base, qdot)
    np.testing.assert_allclose(assembled.linear_root_kg_m_s, linear, atol=2.0e-14, rtol=0.0)
    np.testing.assert_allclose(
        assembled.angular_about_root_kg_m2_s, angular, atol=2.0e-14, rtol=0.0
    )


def test_frame_only_link_cannot_enter_mass_or_sensitivity(synthetic_model):
    assert synthetic_model.total_mass_kg == pytest.approx(10.8)
    with pytest.raises(dynamics.URDFDynamicsError, match="not a physical link"):
        synthetic_model.perturbed_link_model("audit_frame", mass_scale=1.1)


def test_single_link_mass_and_inertia_perturbation_is_local_and_detectable(synthetic_model):
    original_arm = synthetic_model.inertials["arm"]
    original_base = synthetic_model.inertials["base"]
    perturbed = synthetic_model.perturbed_link_model(
        "arm", mass_scale=1.02, inertia_scale=1.03, com_delta_link_m=(0.001, 0.0, 0.0)
    )
    assert perturbed.inertials["arm"].mass_kg == pytest.approx(original_arm.mass_kg * 1.02)
    np.testing.assert_allclose(
        perturbed.inertials["arm"].inertia_inertial_kg_m2,
        original_arm.inertia_inertial_kg_m2 * 1.03,
    )
    assert perturbed.inertials["base"].mass_kg == pytest.approx(original_base.mass_kg)
    np.testing.assert_allclose(
        perturbed.inertials["base"].inertia_inertial_kg_m2,
        original_base.inertia_inertial_kg_m2,
    )
    assert synthetic_model.inertials["arm"].mass_kg == pytest.approx(original_arm.mass_kg)
    result = synthetic_model.single_link_sensitivity(
        (0.2, 0.02), "arm", mass_scale=1.02, inertia_scale=1.03
    )
    assert result["mass_matrix_frobenius_delta"] > 0.0
    assert result["Hbb_frobenius_delta"] > 0.0
    assert result["Hbm_frobenius_delta"] > 0.0
    assert result["authority_class"] == "SOURCE_ONLY_CURRENT_MODEL_SENSITIVITY_NOT_BINDING_EVIDENCE"


def test_torque_free_target_nonprincipal_spin_evolves_and_conserves_invariants():
    inertia = np.diag((2.0, 3.0, 5.0))
    initial_omega = np.array((0.7, 1.1, -0.4))
    history = dynamics.propagate_free_rigid_body(
        inertia,
        initial_omega,
        step_s=5.0e-4,
        steps=4000,
    )
    assert np.linalg.norm(history.omega_body_rad_s[-1] - initial_omega) > 1.0e-3
    energy_relative_drift = np.max(
        np.abs(history.kinetic_energy_j - history.kinetic_energy_j[0])
    ) / history.kinetic_energy_j[0]
    momentum_scale = np.linalg.norm(history.angular_momentum_inertial_kg_m2_s[0])
    momentum_relative_drift = np.max(
        np.linalg.norm(
            history.angular_momentum_inertial_kg_m2_s
            - history.angular_momentum_inertial_kg_m2_s[0],
            axis=1,
        )
    ) / momentum_scale
    assert energy_relative_drift < 2.0e-11
    assert momentum_relative_drift < 2.0e-10
    np.testing.assert_allclose(
        np.linalg.norm(history.quaternion_body_to_inertial_wxyz, axis=1),
        np.ones(history.time_s.size),
        atol=2.0e-14,
        rtol=0.0,
    )


def _load_unified_r2_source_only_model():
    source_dir = (
        PROJECT_ROOT
        / "20_engineering"
        / "F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"
        / "unified_r2_digital_prototype_prebind"
        / "source_only_v2"
    )
    source_module = _load_module(
        source_dir / "unified_r2_urdf_source_v2.py", "unified_r2_source_for_dynamics_test"
    )
    inputs = yaml.safe_load(
        (source_dir / "UNIFIED_R2_URDF_SOURCE_INPUTS_V2.yaml").read_text(encoding="utf-8-sig")
    )
    # Private source-only builder is explicitly exposed for in-memory validation.
    # This does not call gen_urdf(), consume an authority record, or write a URDF.
    robot = source_module._build_robot(inputs)
    return dynamics.URDFTreeDynamics(ET.tostring(robot, encoding="utf-8"))


def test_unified_r2_source_only_snapshot_topology_mass_matrix_and_momentum():
    model = _load_unified_r2_source_only_model()
    summary = model.model_summary()
    assert summary["links"] == 19
    assert summary["joints"] == 18
    assert summary["physical_links"] == 16
    assert summary["frame_only_links"] == 3
    assert summary["fixed_joints"] == 10
    assert summary["revolute_joints"] == 6
    assert summary["prismatic_joints"] == 2
    assert summary["movable_dof"] == 8
    assert summary["total_mass_kg"] == pytest.approx(31.022864807342987, abs=1.0e-12)
    assert set(model.frame_only_link_names) == {
        "D_BUS_MATE_PHYSICAL",
        "D_BUS_M6_PATTERN",
        "M_DYNAMICS_NONPHYSICAL",
    }
    q = np.linspace(-0.15, 0.12, model.movable_dof)
    qdot = np.linspace(0.04, -0.025, model.movable_dof)
    matrix = model.mass_matrix(q)
    np.testing.assert_allclose(matrix, matrix.T, atol=1.0e-12, rtol=0.0)
    assert np.min(np.linalg.eigvalsh(matrix)) > 0.0
    base = model.base_twist_for_zero_momentum(q, qdot)
    assert np.linalg.norm(model.momentum(q, base, qdot).vector6) < 5.0e-13


def test_unified_r2_single_link_sensitivity_changes_current_model_response():
    model = _load_unified_r2_source_only_model()
    q = np.zeros(model.movable_dof)
    result = model.single_link_sensitivity(
        q,
        "link3",
        mass_scale=1.005,
        inertia_scale=1.01,
        com_delta_link_m=(0.0005, 0.0, 0.0),
    )
    assert result["mass_matrix_frobenius_delta"] > 0.0
    assert result["Hbb_frobenius_delta"] > 0.0
    assert result["Hbm_frobenius_delta"] > 0.0
