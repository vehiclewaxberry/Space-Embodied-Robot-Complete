"""Generate validator evidence and a non-final pre-audit Phase-A Gate."""

from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

import numpy as np

from sim13_v4a.full_floating import (
    CONTACT_IMPLEMENTED,
    CURRENT_SYSTEM_BOUND,
    FORMAL_NC19_CREDIT,
    JOINT_COORDINATE_UNITS,
    JOINT_EFFORT_UNITS,
    JOINT_RATE_UNITS,
    PRODUCTION_BACKEND,
    ServiceState,
    TargetState,
    deterministic_scenario,
    deterministic_el_audit_states,
    deterministic_stress_points,
    propagate_no_contact,
    quat_from_rotvec,
    quat_product,
    quat_to_rotation,
    quaternion_geodesic,
    relative_scalar_drift,
    relative_vector_drift,
    run_negative_controls,
)


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
EVIDENCE = HERE / "evidence"
RESULTS = HERE / "results"
SOURCE_MANIFEST = EVIDENCE / "SIM13_V4A_PHASE_A_SOURCE_MANIFEST_V3.json"
LEDGER = EVIDENCE / "SIM13_V4A_PHASE_A_DYNAMICS_LEDGER_V3.json"
VALIDATION = EVIDENCE / "SIM13_V4A_PHASE_A_VALIDATION_V3.json"
EVIDENCE_MANIFEST = EVIDENCE / "SIM13_V4A_PHASE_A_EVIDENCE_MANIFEST_V3.json"
PRE_AUDIT_GATE = RESULTS / "SIM13_V4A_PHASE_A_PRE_AUDIT_GATE_V3.json"
AUDIT_RECEIPT = EVIDENCE / "SIM13_V4A_PHASE_A_INDEPENDENT_AUDIT_RECEIPT_V3.json"
FINAL_GATE = RESULTS / "SIM13_V4A_PHASE_A_AUDITED_GATE_V3.json"
TERMINAL_MANIFEST = RESULTS / "SIM13_V4A_PHASE_A_TERMINAL_SELF_EXCLUDED_MANIFEST_V3.json"
V2_GATE = HERE.parent / "v2_system_rebind/results/SIM13_V2_PREBIND_SOURCE_GATE_V1.json"

EXPECTED_NODEIDS = (
    "tests/test_dynamics.py::test_zero_velocity_zero_external_has_zero_acceleration",
    "tests/test_dynamics.py::test_service_free_motion_preserves_p_h_and_energy_separately",
    "tests/test_dynamics.py::test_target_full_6dof_preserves_p_h_and_energy_separately",
    "tests/test_dynamics.py::test_no_contact_decouples_plants_and_uses_one_time_axis",
    "tests/test_dynamics.py::test_rk4_step_halving_converges_componentwise",
    "tests/test_dynamics.py::test_el_audit_registry_has_six_explicit_diverse_nonzero_velocity_states",
    "tests/test_governance.py::test_phase_a_authority_and_contact_boundaries_remain_false",
    "tests/test_governance.py::test_no_urdf_interface_or_authorization_artifact_exists",
    "tests/test_kinematics.py::test_topology_and_mixed_unit_contract_are_explicit",
    "tests/test_kinematics.py::test_mass_matrix_is_spd_and_has_free_base_joint_coupling",
    "tests/test_kinematics.py::test_mass_matrix_energy_matches_direct_body_sum",
    "tests/test_kinematics.py::test_link_local_point_jacobian_matches_finite_difference",
    "tests/test_kinematics.py::test_point_jacobian_is_covariant_under_global_rigid_transform",
    "tests/test_kinematics.py::test_fixed_multiconfiguration_registry_covers_all_links_and_point_jacobians",
    "tests/test_negative_controls.py::test_registered_mutation_is_detected[NC-A01_BASE_LOCK]",
    "tests/test_negative_controls.py::test_registered_mutation_is_detected[NC-A02_MISSING_COUPLING_BLOCK]",
    "tests/test_negative_controls.py::test_registered_mutation_is_detected[NC-A03_RP_UNIT_SCALE]",
    "tests/test_negative_controls.py::test_registered_mutation_is_detected[NC-A04_INVALID_QUATERNION]",
    "tests/test_negative_controls.py::test_registered_mutation_is_detected[NC-A05_JACOBIAN_SIGN]",
    "tests/test_negative_controls.py::test_registered_mutation_is_detected[NC-A06_POINT_OFFSET]",
)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _record(path: Path, role: str) -> dict[str, Any]:
    return {
        "role": role,
        "path": _relative(path),
        "bytes": path.stat().st_size,
        "sha256": _sha(path),
    }


def _source_paths() -> list[Path]:
    paths = [
        HERE / "README.md",
        HERE / "pytest.ini",
        HERE / "validate_phase_a.py",
        HERE / "independent_audit_phase_a.py",
        HERE / "contracts/SYNTHETIC_FULL_FLOATING_MODEL_CONTRACT_V1.json",
        HERE / "contracts/GOVERNANCE_BOUNDARY_V1.json",
    ]
    paths.extend(sorted((HERE / "sim13_v4a").glob("*.py")))
    paths.extend(sorted((HERE / "tests").glob("*.py")))
    return sorted(set(paths), key=lambda path: _relative(path))


def _run_tests() -> dict[str, Any]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    collect = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=HERE,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    collected = tuple(
        line.strip() for line in collect.stdout.splitlines() if "::" in line
    )
    execution = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=HERE,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    match = re.search(r"(\d+) passed", execution.stdout)
    passed = int(match.group(1)) if match else 0
    return {
        "collection_return_code": collect.returncode,
        "execution_return_code": execution.returncode,
        "collected_nodeids": list(collected),
        "expected_nodeids": list(EXPECTED_NODEIDS),
        "exact_collection_match": collected == EXPECTED_NODEIDS,
        "passed": passed,
        "expected": len(EXPECTED_NODEIDS),
        "stdout_tail": execution.stdout.strip().splitlines()[-3:],
        "stderr": execution.stderr.strip(),
    }


def _configuration_covariance(model, service) -> dict[str, float]:
    global_quaternion = quat_from_rotvec((0.23, -0.17, 0.11))
    global_rotation = quat_to_rotation(global_quaternion)
    translation = np.array((-0.7, 0.4, 0.2))
    transformed = ServiceState(
        translation + global_rotation @ service.base_position_inertial_m,
        quat_product(global_quaternion, service.base_quaternion_body_to_inertial_wxyz),
        service.joint_coordinates_mixed.copy(),
        service.nu_s_mixed.copy(),
    )
    point_local = (0.053, 0.019, -0.027)
    point, jacobian, _ = model.point_position_and_jacobian(service, 6, point_local)
    transformed_point, transformed_jacobian, _ = model.point_position_and_jacobian(
        transformed, 6, point_local
    )
    velocity_transform = np.eye(14)
    velocity_transform[:3, :3] = global_rotation
    velocity_transform[3:6, 3:6] = global_rotation
    return {
        "point_position_covariance_error_m": float(
            np.linalg.norm(transformed_point - (translation + global_rotation @ point))
        ),
        "point_jacobian_covariance_max_error_mixed_units": float(
            np.max(
                np.abs(
                    transformed_jacobian @ velocity_transform
                    - global_rotation @ jacobian
                )
            )
        ),
    }


def _componentwise_final_difference(left, right) -> dict[str, float]:
    return {
        "service_base_position_m": float(
            np.linalg.norm(
                left.service_base_position_inertial_m[-1]
                - right.service_base_position_inertial_m[-1]
            )
        ),
        "service_base_quaternion_geodesic_rad": quaternion_geodesic(
            left.service_base_quaternion_body_to_inertial_wxyz[-1],
            right.service_base_quaternion_body_to_inertial_wxyz[-1],
        ),
        "service_q_R_rad": float(
            np.max(
                np.abs(
                    left.service_joint_coordinates_mixed[-1, :6]
                    - right.service_joint_coordinates_mixed[-1, :6]
                )
            )
        ),
        "service_q_P_m": float(
            np.max(
                np.abs(
                    left.service_joint_coordinates_mixed[-1, 6:]
                    - right.service_joint_coordinates_mixed[-1, 6:]
                )
            )
        ),
        "service_v_base_m_s": float(
            np.max(np.abs(left.service_nu_s_mixed[-1, :3] - right.service_nu_s_mixed[-1, :3]))
        ),
        "service_omega_base_rad_s": float(
            np.max(np.abs(left.service_nu_s_mixed[-1, 3:6] - right.service_nu_s_mixed[-1, 3:6]))
        ),
        "service_qdot_R_rad_s": float(
            np.max(np.abs(left.service_nu_s_mixed[-1, 6:12] - right.service_nu_s_mixed[-1, 6:12]))
        ),
        "service_qdot_P_m_s": float(
            np.max(np.abs(left.service_nu_s_mixed[-1, 12:] - right.service_nu_s_mixed[-1, 12:]))
        ),
        "target_position_m": float(
            np.linalg.norm(left.target_position_inertial_m[-1] - right.target_position_inertial_m[-1])
        ),
        "target_quaternion_geodesic_rad": quaternion_geodesic(
            left.target_quaternion_body_to_inertial_wxyz[-1],
            right.target_quaternion_body_to_inertial_wxyz[-1],
        ),
        "target_velocity_m_s": float(
            np.max(np.abs(left.target_twist_inertial_mixed[-1, :3] - right.target_twist_inertial_mixed[-1, :3]))
        ),
        "target_omega_rad_s": float(
            np.max(np.abs(left.target_twist_inertial_mixed[-1, 3:] - right.target_twist_inertial_mixed[-1, 3:]))
        ),
    }


def _conservation_metrics(history) -> dict[str, Any]:
    return {
        "service": {
            "linear_momentum_relative_drift": relative_vector_drift(history.service_linear_momentum_n_s),
            "linear_momentum_max_absolute_drift_n_s": float(np.max(np.linalg.norm(history.service_linear_momentum_n_s - history.service_linear_momentum_n_s[0], axis=1))),
            "angular_momentum_about_common_inertial_origin_relative_drift": relative_vector_drift(history.service_angular_momentum_about_inertial_origin_n_m_s),
            "angular_momentum_max_absolute_drift_n_m_s": float(np.max(np.linalg.norm(history.service_angular_momentum_about_inertial_origin_n_m_s - history.service_angular_momentum_about_inertial_origin_n_m_s[0], axis=1))),
            "kinetic_energy_relative_drift": relative_scalar_drift(history.service_kinetic_energy_j),
            "kinetic_energy_max_absolute_drift_j": float(np.max(np.abs(history.service_kinetic_energy_j - history.service_kinetic_energy_j[0]))),
        },
        "target": {
            "linear_momentum_relative_drift": relative_vector_drift(history.target_linear_momentum_n_s),
            "linear_momentum_max_absolute_drift_n_s": float(np.max(np.linalg.norm(history.target_linear_momentum_n_s - history.target_linear_momentum_n_s[0], axis=1))),
            "angular_momentum_about_common_inertial_origin_relative_drift": relative_vector_drift(history.target_angular_momentum_about_inertial_origin_n_m_s),
            "angular_momentum_max_absolute_drift_n_m_s": float(np.max(np.linalg.norm(history.target_angular_momentum_about_inertial_origin_n_m_s - history.target_angular_momentum_about_inertial_origin_n_m_s[0], axis=1))),
            "kinetic_energy_relative_drift": relative_scalar_drift(history.target_kinetic_energy_j),
            "kinetic_energy_max_absolute_drift_j": float(np.max(np.abs(history.target_kinetic_energy_j - history.target_kinetic_energy_j[0]))),
        },
        "combined": {
            "linear_momentum_relative_drift": relative_vector_drift(history.total_linear_momentum_n_s),
            "linear_momentum_max_absolute_drift_n_s": float(np.max(np.linalg.norm(history.total_linear_momentum_n_s - history.total_linear_momentum_n_s[0], axis=1))),
            "angular_momentum_about_common_inertial_origin_relative_drift": relative_vector_drift(history.total_angular_momentum_about_inertial_origin_n_m_s),
            "angular_momentum_max_absolute_drift_n_m_s": float(np.max(np.linalg.norm(history.total_angular_momentum_about_inertial_origin_n_m_s - history.total_angular_momentum_about_inertial_origin_n_m_s[0], axis=1))),
            "kinetic_energy_relative_drift": relative_scalar_drift(history.total_kinetic_energy_j),
            "kinetic_energy_max_absolute_drift_j": float(np.max(np.abs(history.total_kinetic_energy_j - history.total_kinetic_energy_j[0]))),
        },
        "linear_and_angular_momentum_combined_in_one_norm": False,
        "common_angular_momentum_reference": "INERTIAL_ORIGIN",
    }


def _forbidden_source_calls() -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    forbidden_names = {"_build_" + "robot", "gen_" + "urdf"}
    for path in sorted(HERE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = getattr(node, "module", "") or ""
                names = [alias.name for alias in node.names]
                if "unified_r2" in module.lower() or any("unified_r2" in name.lower() for name in names):
                    violations.append({"path": _relative(path), "line": node.lineno, "kind": "FORBIDDEN_IMPORT"})
            if isinstance(node, ast.Call):
                called = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
                if called in forbidden_names:
                    violations.append({"path": _relative(path), "line": node.lineno, "kind": "FORBIDDEN_CALL", "name": called})
    return violations


def _check(checks: list[dict[str, Any]], identifier: str, name: str, passed: bool, evidence: Any) -> None:
    checks.append({"id": identifier, "name": name, "pass": bool(passed), "evidence": evidence})


def build_evidence(test_receipt: dict[str, Any], source_reference: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    model, service, target = deterministic_scenario()
    matrix = model.mass_matrix(service)
    matrix_metrics = {
        "shape": list(matrix.shape),
        "symmetry_max_abs": float(np.max(np.abs(matrix - matrix.T))),
        "minimum_eigenvalue_under_declared_SI_channel_scaling": float(np.min(np.linalg.eigvalsh(matrix))),
        "condition_number_under_declared_SI_channel_scaling": float(np.linalg.cond(matrix)),
        "base_joint_coupling_frobenius_under_declared_SI_channel_scaling": float(np.linalg.norm(matrix[:6, 6:])),
    }
    direct_energy = model.momentum_energy(service).kinetic_energy_j
    matrix_energy = model.kinetic_energy_from_mass_matrix(service)
    point_local = (0.071, -0.023, 0.038)
    _, point_jacobian, _ = model.point_position_and_jacobian(service, 7, point_local)
    fd_jacobian = model.finite_difference_point_jacobian(service, 7, point_local)
    point_error = float(np.max(np.abs(point_jacobian - fd_jacobian)))
    covariance = _configuration_covariance(model, service)
    stress_records = []
    for case in deterministic_stress_points():
        _, analytic_stress, _ = model.point_position_and_jacobian(
            case.service_state, case.link_index, case.point_local_m
        )
        finite_difference_stress = model.finite_difference_point_jacobian(
            case.service_state, case.link_index, case.point_local_m
        )
        stress_records.append(
            {
                "case_id": case.case_id,
                "link_index": case.link_index,
                "base_position_inertial_m": case.service_state.base_position_inertial_m.tolist(),
                "base_quaternion_body_to_inertial_wxyz": case.service_state.base_quaternion_body_to_inertial_wxyz.tolist(),
                "joint_coordinates_R_rad": case.service_state.joint_coordinates_mixed[:6].tolist(),
                "joint_coordinates_P_m": case.service_state.joint_coordinates_mixed[6:].tolist(),
                "point_local_m": case.point_local_m.tolist(),
                "maximum_point_jacobian_error_mixed_units": float(
                    np.max(np.abs(analytic_stress - finite_difference_stress))
                ),
            }
        )
    stress_summary = {
        "registry": "FIXED_EXPLICIT_ARRAYS_NO_RNG_V1",
        "case_count": len(stress_records),
        "covered_link_indices": sorted({item["link_index"] for item in stress_records}),
        "maximum_point_jacobian_error_mixed_units": max(
            item["maximum_point_jacobian_error_mixed_units"] for item in stress_records
        ),
        "cases": stress_records,
    }
    el_state_records = []
    for case in deterministic_el_audit_states():
        acceleration = model.acceleration_zero_external(case.service_state)
        el_state_records.append(
            {
                "case_id": case.case_id,
                "base_position_inertial_m": case.service_state.base_position_inertial_m.tolist(),
                "base_quaternion_body_to_inertial_wxyz": case.service_state.base_quaternion_body_to_inertial_wxyz.tolist(),
                "joint_coordinates_R_rad": case.service_state.joint_coordinates_mixed[:6].tolist(),
                "joint_coordinates_P_m": case.service_state.joint_coordinates_mixed[6:].tolist(),
                "base_linear_velocity_m_s": case.service_state.nu_s_mixed[:3].tolist(),
                "base_angular_velocity_rad_s": case.service_state.nu_s_mixed[3:6].tolist(),
                "joint_R_velocity_rad_s": case.service_state.nu_s_mixed[6:12].tolist(),
                "joint_P_velocity_m_s": case.service_state.nu_s_mixed[12:].tolist(),
                "primary_acceleration": {
                    "base_linear_m_s2": acceleration[:3].tolist(),
                    "base_angular_rad_s2": acceleration[3:6].tolist(),
                    "joint_R_rad_s2": acceleration[6:12].tolist(),
                    "joint_P_m_s2": acceleration[12:].tolist(),
                },
            }
        )
    el_state_registry = {
        "registry": "SIX_EXPLICIT_NONZERO_VELOCITY_STATES_NO_RNG_V1",
        "case_count": len(el_state_records),
        "case_ids": [item["case_id"] for item in el_state_records],
        "contains_nominal": el_state_records[0]["case_id"] == "EL00_NOMINAL",
        "main_bias_effort_exported": False,
        "cases": el_state_records,
    }

    fine = propagate_no_contact(model, service, target, step_s=0.002, steps=40, method="rk4")
    coarse = propagate_no_contact(model, service, target, step_s=0.004, steps=20, method="rk4")
    midpoint = propagate_no_contact(model, service, target, step_s=0.001, steps=80, method="midpoint")
    step_halving = _componentwise_final_difference(coarse, fine)
    integrator_crosscheck = _componentwise_final_difference(fine, midpoint)
    component_limits = {
        "service_base_position_m": 2.0e-7,
        "service_base_quaternion_geodesic_rad": 2.0e-7,
        "service_q_R_rad": 2.0e-7,
        "service_q_P_m": 2.0e-7,
        "service_v_base_m_s": 2.0e-7,
        "service_omega_base_rad_s": 2.0e-7,
        "service_qdot_R_rad_s": 2.0e-7,
        "service_qdot_P_m_s": 2.0e-7,
        "target_position_m": 2.0e-8,
        "target_quaternion_geodesic_rad": 2.0e-7,
        "target_velocity_m_s": 2.0e-10,
        "target_omega_rad_s": 2.0e-7,
    }
    conservation = _conservation_metrics(fine)
    quaternion_errors = {
        "service_max_unit_norm_error": float(np.max(np.abs(np.linalg.norm(fine.service_base_quaternion_body_to_inertial_wxyz, axis=1) - 1.0))),
        "target_max_unit_norm_error": float(np.max(np.abs(np.linalg.norm(fine.target_quaternion_body_to_inertial_wxyz, axis=1) - 1.0))),
    }
    changed_target = TargetState(
        target.position_inertial_m + np.array((0.4, -0.1, 0.2)),
        target.quaternion_body_to_inertial_wxyz,
        target.twist_inertial_mixed * np.array((1.2, 0.8, 1.1, 0.9, 1.1, 1.3)),
    )
    baseline_short = propagate_no_contact(model, service, target, step_s=0.002, steps=8)
    variant_short = propagate_no_contact(model, service, changed_target, step_s=0.002, steps=8)
    no_contact_decoupling = {
        "service_state_max_difference_when_only_target_changes": float(
            max(
                np.max(np.abs(baseline_short.service_base_position_inertial_m - variant_short.service_base_position_inertial_m)),
                np.max(np.abs(baseline_short.service_base_quaternion_body_to_inertial_wxyz - variant_short.service_base_quaternion_body_to_inertial_wxyz)),
                np.max(np.abs(baseline_short.service_joint_coordinates_mixed - variant_short.service_joint_coordinates_mixed)),
                np.max(np.abs(baseline_short.service_nu_s_mixed - variant_short.service_nu_s_mixed)),
            )
        ),
        "shared_time_axis_exact": bool(np.array_equal(baseline_short.time_s, variant_short.time_s)),
        "contact_force_evaluations": 0,
    }
    mutations = run_negative_controls(model, service)
    base_mutation = mutations["NC-A01_BASE_LOCK"]
    base_limits = base_mutation["guard_thresholds"]
    missing_coupling = mutations["NC-A02_MISSING_COUPLING_BLOCK"]
    rp_scale = mutations["NC-A03_RP_UNIT_SCALE"]
    quaternion_mutation = mutations["NC-A04_INVALID_QUATERNION"]
    sign_mutation = mutations["NC-A05_JACOBIAN_SIGN"]
    offset_mutation = mutations["NC-A06_POINT_OFFSET"]
    mutation_raw_thresholds_pass = (
        all(item["detected"] is True for item in mutations.values())
        and base_mutation["free_linear_momentum_defect_n_s"] < base_limits["free_linear_max_n_s"]
        and base_mutation["free_angular_momentum_defect_n_m_s"] < base_limits["free_angular_max_n_m_s"]
        and base_mutation["locked_linear_momentum_defect_n_s"] > base_limits["locked_linear_min_n_s"]
        and base_mutation["locked_angular_momentum_defect_n_m_s"] > base_limits["locked_angular_min_n_m_s"]
        and missing_coupling["direct_vs_mutated_energy_error_j"] > missing_coupling["guard_threshold_min_j"]
        and rp_scale["maximum_point_jacobian_error_mixed_units"] > rp_scale["guard_threshold_min_mixed_units"]
        and quaternion_mutation["injected_nonunit_norm_error"] > quaternion_mutation["guard_threshold_max_unit_norm_error"]
        and quaternion_mutation["nan_rejected"] is True
        and quaternion_mutation["nonunit_rejected"] is True
        and sign_mutation["maximum_point_jacobian_error_mixed_units"] > sign_mutation["guard_threshold_min_mixed_units"]
        and offset_mutation["maximum_point_jacobian_error_mixed_units"] > offset_mutation["guard_threshold_min_mixed_units"]
    )

    v2_gate_payload = json.loads(V2_GATE.read_text(encoding="utf-8"))
    v2_formal_hold_intact = (
        v2_gate_payload.get("formal_negative_controls_declared") == 20
        and v2_gate_payload.get("formal_negative_controls_passed") == 15
        and v2_gate_payload.get("formal_negative_controls_dependency_hold") == 5
        and v2_gate_payload.get("formal_negative_controls_hold_ids") == ["NC15", "NC16", "NC18", "NC19", "NC20"]
        and v2_gate_payload.get("formal_negative_controls_all_passed") is False
    )
    forbidden_calls = _forbidden_source_calls()
    forbidden_artifacts = [
        _relative(path)
        for path in HERE.rglob("*")
        if path.is_file()
        and (
            path.suffix.lower() == ".urdf"
            or path.name in {
                "MECH_RL_SYSTEM_INTERFACE_V2.yaml",
                "UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2.json",
            }
        )
    ]
    caches = [
        _relative(path)
        for path in HERE.rglob("*")
        if path.name in {"__pycache__", ".pytest_cache", ".pytest-cache-disabled"}
        or path.suffix.lower() in {".pyc", ".pyo"}
    ]

    checks: list[dict[str, Any]] = []
    _check(checks, "A01", "synthetic topology is exactly free base plus 6R+2P and independent target 6DOF", model.joint_types == ("R",) * 6 + ("P",) * 2 and model.full_velocity_dof == 14, {"joint_types": list(model.joint_types), "service_velocity_dof": model.full_velocity_dof, "target_dof": 6, "actual_b601_claimed": False})
    _check(checks, "A02", "R and P coordinate/rate/effort units are declared separately", JOINT_COORDINATE_UNITS == ("rad",) * 6 + ("m",) * 2 and JOINT_RATE_UNITS == ("rad/s",) * 6 + ("m/s",) * 2 and JOINT_EFFORT_UNITS == ("N*m",) * 6 + ("N",) * 2, {"coordinate_units": list(JOINT_COORDINATE_UNITS), "rate_units": list(JOINT_RATE_UNITS), "effort_units": list(JOINT_EFFORT_UNITS), "full_mass_matrix_single_unit": None})
    _check(checks, "A03", "full floating 14x14 mass matrix is symmetric positive definite with nonzero base-joint coupling", matrix_metrics["shape"] == [14, 14] and matrix_metrics["symmetry_max_abs"] < 1.0e-12 and matrix_metrics["minimum_eigenvalue_under_declared_SI_channel_scaling"] > 1.0e-5 and matrix_metrics["base_joint_coupling_frobenius_under_declared_SI_channel_scaling"] > 0.05, matrix_metrics)
    _check(checks, "A04", "direct rigid-body kinetic energy cross-checks the mass matrix", abs(direct_energy - matrix_energy) < 2.0e-13, {"direct_body_sum_j": direct_energy, "quadratic_mass_matrix_j": matrix_energy, "absolute_error_j": abs(direct_energy - matrix_energy)})
    _check(checks, "A05", "link-local inertial point translational Jacobian matches tangent finite difference", point_error < 3.0e-8, {"maximum_absolute_error_mixed_units": point_error, "link_index": 7, "point_local_m": list(point_local)})
    _check(checks, "A06", "point position and Jacobian are covariant under a global rigid transform", covariance["point_position_covariance_error_m"] < 1.0e-11 and covariance["point_jacobian_covariance_max_error_mixed_units"] < 1.0e-10, covariance)
    _check(checks, "A07", "service no-contact P H E close separately", conservation["service"]["linear_momentum_relative_drift"] < 2.0e-8 and conservation["service"]["angular_momentum_about_common_inertial_origin_relative_drift"] < 2.0e-8 and conservation["service"]["kinetic_energy_relative_drift"] < 2.0e-8, conservation["service"])
    _check(checks, "A08", "target no-contact P H E close separately", conservation["target"]["linear_momentum_relative_drift"] < 1.0e-12 and conservation["target"]["angular_momentum_about_common_inertial_origin_relative_drift"] < 1.0e-10 and conservation["target"]["kinetic_energy_relative_drift"] < 1.0e-10, conservation["target"])
    _check(checks, "A09", "combined no-contact P H E close about the common inertial origin without heterogeneous norm", conservation["combined"]["linear_momentum_relative_drift"] < 2.0e-8 and conservation["combined"]["angular_momentum_about_common_inertial_origin_relative_drift"] < 2.0e-8 and conservation["combined"]["kinetic_energy_relative_drift"] < 2.0e-8 and conservation["linear_and_angular_momentum_combined_in_one_norm"] is False, conservation["combined"] | {"linear_and_angular_momentum_combined_in_one_norm": False, "reference": "COMMON_INERTIAL_ORIGIN"})
    _check(checks, "A10", "RK4 step halving is componentwise within frozen mixed-unit limits", all(step_halving[name] <= limit for name, limit in component_limits.items()), {"coarse": {"step_s": 0.004, "steps": 20}, "fine": {"step_s": 0.002, "steps": 40}, "observed": step_halving, "limits": component_limits, "heterogeneous_sum_used": False})
    _check(checks, "A11", "independent explicit-midpoint integration cross-check is componentwise within limits", all(integrator_crosscheck[name] <= limit for name, limit in component_limits.items()), {"reference": {"method": "RK4", "step_s": 0.002, "steps": 40}, "crosscheck": {"method": "EXPLICIT_MIDPOINT", "step_s": 0.001, "steps": 80}, "observed": integrator_crosscheck, "limits": component_limits, "heterogeneous_sum_used": False})
    _check(checks, "A12", "service and target share one time axis while remaining exactly decoupled", no_contact_decoupling["shared_time_axis_exact"] and no_contact_decoupling["service_state_max_difference_when_only_target_changes"] == 0.0 and no_contact_decoupling["contact_force_evaluations"] == 0, no_contact_decoupling)
    _check(checks, "A13", "service and target quaternion norms remain closed", quaternion_errors["service_max_unit_norm_error"] < 3.0e-15 and quaternion_errors["target_max_unit_norm_error"] < 3.0e-15, quaternion_errors)
    _check(checks, "A14", "all six raw injected defects cross their registered thresholds and are caught", mutation_raw_thresholds_pass and len(mutations) == 6, mutations)
    _check(checks, "A15", "frozen pytest collection and execution pass exactly", test_receipt["collection_return_code"] == 0 and test_receipt["execution_return_code"] == 0 and test_receipt["exact_collection_match"] is True and test_receipt["passed"] == len(EXPECTED_NODEIDS), test_receipt)
    _check(checks, "A16", "no Unified private call/import or forbidden generated artifact exists", forbidden_calls == [] and forbidden_artifacts == [], {"forbidden_source_calls_or_imports": forbidden_calls, "forbidden_artifacts": forbidden_artifacts, "unified_private_builder_called": False, "unified_generator_called": False})
    _check(checks, "A17", "formal Sim13 V2 remains 15 of 20 with NC19 and four peers on HOLD", v2_formal_hold_intact and FORMAL_NC19_CREDIT is False, {"v2_gate": _record(V2_GATE, "READ_ONLY_FORMAL_V2_GATE"), "declared": v2_gate_payload.get("formal_negative_controls_declared"), "passed": v2_gate_payload.get("formal_negative_controls_passed"), "dependency_hold": v2_gate_payload.get("formal_negative_controls_dependency_hold"), "hold_ids": v2_gate_payload.get("formal_negative_controls_hold_ids"), "this_package_formal_credit": 0})
    _check(checks, "A18", "production current-system contact owner release and next-stage flags remain false", not CONTACT_IMPLEMENTED and not CURRENT_SYSTEM_BOUND and not PRODUCTION_BACKEND, {"contact_implemented": CONTACT_IMPLEMENTED, "current_system_bound": CURRENT_SYSTEM_BOUND, "production_backend": PRODUCTION_BACKEND, "owner_authorized": False, "capture_passed": False, "released": False, "next_stage_authorized": False})
    _check(checks, "A19", "diagnostic directory is free of Python and pytest cache residue", caches == [], {"cache_residue": caches})
    _check(checks, "A20", "ten frozen explicit stress configurations cover all eight link point Jacobians", stress_summary["case_count"] == 10 and stress_summary["covered_link_indices"] == list(range(8)) and stress_summary["maximum_point_jacobian_error_mixed_units"] < 3.0e-8, stress_summary)
    _check(checks, "A21", "six frozen no-RNG EL states include nominal and diverse nonzero R/P motion", el_state_registry["case_count"] == 6 and el_state_registry["contains_nominal"] is True and all(all(abs(value) > 0.0 for value in item["joint_R_velocity_rad_s"] + item["joint_P_velocity_m_s"]) for item in el_state_records), el_state_registry)

    ledger = {
        "schema": "SIM13_V4A_PHASE_A_DYNAMICS_LEDGER_V3",
        "artifact_class": "SYNTHETIC_FULL_FLOATING_NO_CONTACT_ALGORITHM_DIAGNOSTIC",
        "hash_chain": {"upstream_source_manifest": source_reference},
        "scope": {
            "phase": "A",
            "contact": "NOT_IMPLEMENTED",
            "service": "SYNTHETIC_ANALOGUE_6R2P_FULL_FLOATING",
            "target": "INDEPENDENT_SYNTHETIC_RIGID_6DOF",
            "actual_b601_bound": False,
            "unified_r2_bound": False,
        },
        "units": {
            "service_velocity_contract": "nu_s=[v_b_inertial_m_s(3),omega_b_inertial_rad_s(3),qdot_R_rad_s(6),qdot_P_m_s(2)]",
            "joint_coordinate_units": list(JOINT_COORDINATE_UNITS),
            "joint_rate_units": list(JOINT_RATE_UNITS),
            "joint_effort_units": list(JOINT_EFFORT_UNITS),
            "full_mass_matrix_single_unit": None,
        },
        "matrix": matrix_metrics,
        "point_kinematics": {"finite_difference_max_error_mixed_units": point_error, "rigid_transform_covariance": covariance, "fixed_multiconfiguration_stress": stress_summary},
        "primary_zero_external_accelerations_for_independent_el_audit": el_state_registry,
        "integration": {"primary": "RK4", "step_halving": step_halving, "independent_integrator_crosscheck": integrator_crosscheck, "component_limits": component_limits},
        "conservation": conservation,
        "negative_controls": mutations,
        "formal_boundary": {"sim13_v2": "15/20_PASS_5/20_DEPENDENCY_HOLD", "formal_nc19_closed": False, "current_system_contact_capture_owner_release_next_stage": False},
    }
    validation = {
        "schema": "SIM13_V4A_PHASE_A_VALIDATION_V3",
        "hash_chain": {"upstream_source_manifest": source_reference},
        "checks": checks,
        "summary": {"pass": sum(item["pass"] for item in checks), "fail": sum(not item["pass"] for item in checks), "total": len(checks)},
    }
    return ledger, validation


def build_gate(validation: dict[str, Any], source_reference: dict[str, Any], evidence_reference: dict[str, Any]) -> dict[str, Any]:
    diagnostic_pass = validation["summary"]["fail"] == 0
    return {
        "schema": "SIM13_V4A_PHASE_A_PRE_AUDIT_GATE_V3",
        "overall_status": "PASS_VALIDATOR_PENDING_INDEPENDENT_AUDIT" if diagnostic_pass else "FAIL_PHASE_A_VALIDATOR",
        "final_gate": False,
        "hash_chain": {"upstream_source_manifest": source_reference, "upstream_evidence_manifest": evidence_reference},
        "diagnostic_checks": validation["summary"],
        "gates": [
            {"id": "V4A-G01", "name": "synthetic full-floating no-contact Phase-A validator", "status": "PASS_PENDING_INDEPENDENT_AUDIT" if diagnostic_pass else "FAIL", "pass": diagnostic_pass},
            {"id": "V4A-G01A", "name": "independent Euler-Lagrange and evidence-DAG audit", "status": "PENDING_NOT_RUN_BY_VALIDATOR", "pass": False},
            {"id": "V4A-G02", "name": "continuous contact backend and capture", "status": "HOLD_PHASE_B_NOT_IMPLEMENTED", "pass": False},
            {"id": "V4A-G03", "name": "current Unified-R2 system binding", "status": "HOLD_NO_AUTHORIZED_CURRENT_SYSTEM_INSTANCE", "pass": False},
            {"id": "V4A-G04", "name": "formal Sim13 NC19 closure", "status": "HOLD_FORMAL_V2_REMAINS_15_OF_20", "pass": False},
            {"id": "V4A-G05", "name": "Owner production release and next stage", "status": "HOLD_NOT_AUTHORIZED", "pass": False},
        ],
        "authorizations": {
            "synthetic_phase_a_validator_ready": diagnostic_pass,
            "synthetic_phase_a_audited_ready": False,
            "contact_ready": False,
            "capture_ready": False,
            "current_system_bound": False,
            "formal_nc19_closed": False,
            "owner_authorized": False,
            "production_ready": False,
            "released": False,
            "next_stage_authorized": False,
        },
        "formal_sim13_v2_state": {"passed": 15, "declared": 20, "dependency_hold": 5, "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"], "changed_by_this_package": False},
        "prohibitions": [
            "DO_NOT_CALL_UNIFIED_PRIVATE_BUILDER_OR_GENERATOR",
            "DO_NOT_CREATE_URDF_FORMAL_INTERFACE_OR_AUTHORIZATION",
            "DO_NOT_CALL_SYNTHETIC_ANALOGUE_ACTUAL_B601_OR_UNIFIED_R2",
            "DO_NOT_CLAIM_CONTACT_CAPTURE_OR_FORMAL_NC19_PASS",
            "DO_NOT_COMBINE_LINEAR_AND_ANGULAR_MOMENTUM_IN_ONE_NORM",
            "DO_NOT_INHERIT_OWNER_PRODUCTION_RELEASE_OR_NEXT_STAGE_AUTHORITY",
        ],
    }


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    # Explicit downstream invalidation prevents a stale audited result from
    # surviving a new validator/source hash.  Targets are fixed inside V4A.
    for stale_downstream in (AUDIT_RECEIPT, FINAL_GATE, TERMINAL_MANIFEST):
        stale_downstream.unlink(missing_ok=True)
    source_manifest = {
        "schema": "SIM13_V4A_PHASE_A_SOURCE_MANIFEST_V3",
        "self_excluded_path": _relative(SOURCE_MANIFEST),
        "records": [_record(path, "FROZEN_SOURCE_INPUT") for path in _source_paths()],
        "acyclic_rule": "THIS_MANIFEST_EXCLUDES_ITSELF_AND_ALL_GENERATED_EVIDENCE_RESULTS",
    }
    _write_json(SOURCE_MANIFEST, source_manifest)
    source_reference = _record(SOURCE_MANIFEST, "UPSTREAM_SOURCE_MANIFEST")
    tests = _run_tests()
    ledger, validation = build_evidence(tests, source_reference)
    _write_json(LEDGER, ledger)
    _write_json(VALIDATION, validation)
    evidence_manifest = {
        "schema": "SIM13_V4A_PHASE_A_EVIDENCE_MANIFEST_V3",
        "upstream_source_manifest": source_reference,
        "self_excluded_path": _relative(EVIDENCE_MANIFEST),
        "records": [_record(LEDGER, "DYNAMICS_LEDGER"), _record(VALIDATION, "VALIDATION_EVIDENCE")],
        "acyclic_rule": "SOURCE_MANIFEST_TO_EVIDENCE_TO_PRE_AUDIT_GATE; NO_DOWNSTREAM_BACK_EDGE",
    }
    _write_json(EVIDENCE_MANIFEST, evidence_manifest)
    evidence_reference = _record(EVIDENCE_MANIFEST, "UPSTREAM_EVIDENCE_MANIFEST")
    gate = build_gate(validation, source_reference, evidence_reference)
    _write_json(PRE_AUDIT_GATE, gate)
    print(json.dumps({"gate": gate["overall_status"], "checks": validation["summary"], "tests": {"passed": tests["passed"], "expected": tests["expected"], "exact_collection_match": tests["exact_collection_match"]}, "pre_audit_gate_path": _relative(PRE_AUDIT_GATE), "final_gate_exists": FINAL_GATE.is_file(), "next": "RUN_INDEPENDENT_AUDIT"}, indent=2, ensure_ascii=False))
    return 0 if validation["summary"]["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
