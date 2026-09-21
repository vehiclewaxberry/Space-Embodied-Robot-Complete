#!/usr/bin/env python3
"""Generate deterministic V3 Phase-A evidence with an acyclic hash chain."""

from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import numpy as np


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
TESTS_DIR = HERE / "tests"
EVIDENCE_DIR = HERE / "evidence"
RESULTS_DIR = HERE / "results"
SOURCE_MANIFEST_PATH = EVIDENCE_DIR / "SIM13_V3_PHASE_A_SOURCE_MANIFEST_V2.csv"
LEDGER_PATH = EVIDENCE_DIR / "SIM13_V3_PHASE_A_DYNAMICS_LEDGER_V2.json"
VALIDATION_PATH = EVIDENCE_DIR / "SIM13_V3_PHASE_A_VALIDATION_V2.json"
EVIDENCE_MANIFEST_PATH = EVIDENCE_DIR / "SIM13_V3_PHASE_A_EVIDENCE_MANIFEST_V2.json"
GATE_PATH = RESULTS_DIR / "SIM13_V3_PHASE_A_DYNAMICS_GATE_V2.json"

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from sim13_v3.reduced_dynamics import (
    BACKEND_SCOPE,
    CHRISTOFFEL_BACKEND,
    CURRENT_SYSTEM_BINDING_PASSED,
    MASS_MATRIX_BLOCK_UNIT_CONTRACT,
    PRODUCTION_DYNAMICS_GATE_PASSED,
    ZeroMomentumReducedDynamics,
)
from sim13_v3.source_model import (
    FIXTURE_AUTHORITY_CLASS,
    FIXTURE_ID,
    PROJECT_ROOT as MODEL_PROJECT_ROOT,
    V2_ROOT,
    build_synthetic_8dof_model,
    file_record,
    read_only_current_system_records,
    sha256_bytes,
    synthetic_8dof_xml_bytes,
)
from sim13_v3.target_6dof import (
    TARGET_BACKEND_SCOPE,
    URDFDynamicsError,
    propagate_target_6dof,
)


EXPECTED_TEST_NODEIDS = (
    "tests/test_authority_boundary.py::test_current_system_records_are_read_only_hashes_not_solver_inputs",
    "tests/test_authority_boundary.py::test_no_unified_builder_or_generation_call_in_v3_runtime_modules",
    "tests/test_reduced_dynamics.py::test_fixture_is_exactly_synthetic_8dof_and_never_written_as_urdf",
    "tests/test_reduced_dynamics.py::test_scope_is_explicitly_nonproduction_and_fd_christoffel",
    "tests/test_reduced_dynamics.py::test_mixed_generalized_coordinate_and_mass_block_unit_contract",
    "tests/test_reduced_dynamics.py::test_full_14_by_14_mass_matrix_is_symmetric_positive_definite",
    "tests/test_reduced_dynamics.py::test_all_eight_generalized_coordinate_effort_channels_are_independent",
    "tests/test_reduced_dynamics.py::test_forward_inverse_roundtrip",
    "tests/test_reduced_dynamics.py::test_zero_state_zero_generalized_effort_zero_acceleration",
    "tests/test_reduced_dynamics.py::test_single_generalized_effort_generates_base_reaction_and_separate_zero_momenta",
    "tests/test_reduced_dynamics.py::test_per_coordinate_two_step_richardson_derivatives_are_consistent",
    "tests/test_reduced_dynamics.py::test_free_motion_conserves_reduced_energy_and_zero_momentum",
    "tests/test_reduced_dynamics.py::test_powered_motion_closes_work_energy",
    "tests/test_reduced_dynamics.py::test_robot_step_size_convergence",
    "tests/test_target_6dof.py::test_target_full_translation_nonprincipal_rotation_and_invariants",
    "tests/test_target_6dof.py::test_target_step_size_convergence",
    "tests/test_target_6dof.py::test_target_inertia_asymmetry_fails_closed",
)

SOURCE_WHITELIST = (
    "pytest.ini",
    "README.md",
    "validate_phase_a.py",
    "independent_audit_phase_a.py",
    "sim13_v3/__init__.py",
    "sim13_v3/reduced_dynamics.py",
    "sim13_v3/source_model.py",
    "sim13_v3/target_6dof.py",
    "tests/conftest.py",
    "tests/test_authority_boundary.py",
    "tests/test_reduced_dynamics.py",
    "tests/test_target_6dof.py",
)

GENERALIZED_EFFORT_UNITS = ("N*m",) * 6 + ("N",) * 2
GENERALIZED_COORDINATE_UNITS = ("rad",) * 6 + ("m",) * 2
GENERALIZED_RATE_UNITS = ("rad/s",) * 6 + ("m/s",) * 2

SERVICE_CONVERGENCE_LIMITS = {
    "revolute_coordinate_max_abs_rad": 2.0e-8,
    "prismatic_coordinate_max_abs_m": 2.0e-9,
    "revolute_rate_max_abs_rad_s": 2.0e-8,
    "prismatic_rate_max_abs_m_s": 2.0e-9,
    "base_position_norm_m": 2.0e-9,
    "base_linear_velocity_norm_m_s": 2.0e-9,
    "base_angular_velocity_norm_rad_s": 2.0e-8,
    "base_quaternion_geodesic_rad": 2.0e-8,
}
TARGET_CONVERGENCE_LIMITS = {
    "position_norm_m": 1.0e-13,
    "velocity_norm_m_s": 1.0e-13,
    "omega_norm_rad_s": 2.0e-13,
    "quaternion_geodesic_rad": 3.0e-7,
}


def _canonical_json_bytes(document: object) -> bytes:
    return (
        json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _write_json(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical_json_bytes(document))


def _record(path: Path, role: str) -> dict[str, object]:
    return {"role": role, **file_record(path)}


def _write_csv_manifest(
    path: Path, schema: str, records: list[dict[str, object]]
) -> None:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=("schema", "role", "path", "bytes", "sha256"),
        lineterminator="\n",
    )
    writer.writeheader()
    for record in records:
        writer.writerow({"schema": schema, **record})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(stream.getvalue().encode("utf-8"))


def _source_manifest_records() -> list[dict[str, object]]:
    records = [_record(HERE / relative, "V3_CONTROLLED_SOURCE") for relative in SOURCE_WHITELIST]
    records.append(
        _record(
            V2_ROOT / "sim13_v2" / "free_floating_dynamics.py",
            "REUSED_V2_MASS_MATRIX_BACKEND_SOURCE",
        )
    )
    records.extend(
        {"role": "UNIFIED_R2_READ_ONLY_HASH_NOT_SOLVER_INPUT", **record}
        for record in read_only_current_system_records()
    )
    return records


def _normalize_nodeid(line: str) -> str:
    return line.strip().replace("\\", "/")


def _run_tests() -> dict[str, object]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPATH"] = str(HERE)
    collect_command = [
        sys.executable,
        "-B",
        "-m",
        "pytest",
        "--collect-only",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests",
    ]
    collected_process = subprocess.run(
        collect_command,
        cwd=HERE,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    nodeids = tuple(
        _normalize_nodeid(line)
        for line in collected_process.stdout.splitlines()
        if "::" in line
    )
    test_command = [
        sys.executable,
        "-B",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests",
    ]
    completed = subprocess.run(
        test_command,
        cwd=HERE,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    output = (completed.stdout + "\n" + completed.stderr).strip()
    match = re.search(r"(\d+) passed", output)
    passed = int(match.group(1)) if match else 0
    return {
        "collect_command": "python -B -m pytest --collect-only -q -p no:cacheprovider tests",
        "collect_return_code": collected_process.returncode,
        "expected_count": len(EXPECTED_TEST_NODEIDS),
        "collected_count": len(nodeids),
        "expected_nodeids": list(EXPECTED_TEST_NODEIDS),
        "collected_nodeids": list(nodeids),
        "exact_collection_match": nodeids == EXPECTED_TEST_NODEIDS,
        "test_command": "python -B -m pytest -q -p no:cacheprovider tests",
        "test_return_code": completed.returncode,
        "passed": passed,
        "summary": f"{passed} passed" if match else "NO_PASS_SUMMARY",
    }


def _relative_scalar_drift(history: np.ndarray) -> float:
    scale = max(abs(float(history[0])), np.finfo(float).tiny)
    return float(np.max(np.abs(history - history[0])) / scale)


def _relative_vector_drift(history: np.ndarray) -> float:
    scale = max(float(np.linalg.norm(history[0])), np.finfo(float).tiny)
    return float(np.max(np.linalg.norm(history - history[0], axis=1)) / scale)


def _quaternion_geodesic(left: np.ndarray, right: np.ndarray) -> float:
    alignment = abs(float(left @ right))
    return float(2.0 * np.arccos(np.clip(alignment, -1.0, 1.0)))


def _bias_from_derivatives(derivatives: np.ndarray, rates: np.ndarray) -> np.ndarray:
    mass_rate = np.tensordot(rates, derivatives, axes=(0, 0))
    energy_gradient = np.array(
        [rates @ derivatives[index] @ rates for index in range(rates.size)]
    )
    return mass_rate @ rates - 0.5 * energy_gradient


def _check(
    checks: list[dict[str, object]],
    check_id: str,
    name: str,
    passed: bool,
    evidence: object,
) -> None:
    checks.append(
        {
            "id": check_id,
            "name": name,
            "status": "PASS" if passed else "FAIL",
            "pass": bool(passed),
            "evidence": evidence,
        }
    )


def _recompute_case_inputs() -> tuple[dict[str, object], ...]:
    return (
        {
            "case_id": "RC01_MIXED_NOMINAL",
            "q": (0.11, -0.16, 0.08, 0.13, -0.09, 0.06, 0.012, -0.009),
            "rates": (0.055, -0.041, 0.032, 0.024, -0.019, 0.015, 0.004, -0.003),
            "effort": (-0.13, -0.08714285714285715, -0.04428571428571429, -0.0014285714285714457, 0.041428571428571426, 0.08428571428571427, 0.1271428571428571, 0.17),
        },
        {
            "case_id": "RC02_OPPOSING_RP",
            "q": (-0.19, 0.07, -0.12, 0.04, 0.15, -0.05, -0.016, 0.014),
            "rates": (-0.031, 0.046, -0.028, 0.037, 0.021, -0.018, -0.005, 0.006),
            "effort": (0.09, -0.07, 0.05, -0.04, 0.03, -0.02, 0.018, -0.016),
        },
        {
            "case_id": "RC03_ASYMMETRIC_SHAPE",
            "q": (0.23, 0.09, -0.06, -0.17, 0.04, 0.12, 0.019, -0.011),
            "rates": (0.022, 0.017, -0.039, 0.028, -0.033, 0.026, 0.007, 0.002),
            "effort": (-0.04, 0.06, -0.08, 0.10, -0.05, 0.03, -0.012, 0.014),
        },
    )


def build_evidence(
    source_manifest_reference: dict[str, object], tests: dict[str, object]
) -> tuple[dict[str, object], dict[str, object]]:
    if PROJECT_ROOT != MODEL_PROJECT_ROOT:
        raise RuntimeError("project-root resolution drift")
    fixture_bytes = synthetic_8dof_xml_bytes()
    model = build_synthetic_8dof_model()
    solver = ZeroMomentumReducedDynamics(model)
    primary = _recompute_case_inputs()[0]
    q = np.asarray(primary["q"], dtype=float)
    rates = np.asarray(primary["rates"], dtype=float)
    full_mass = model.mass_matrix(q)
    reduced_mass = solver.reduced_mass_matrix(q)
    connection = solver.mechanical_connection(q)

    response = np.linalg.solve(reduced_mass, np.eye(8))
    base_reaction_columns = connection @ response
    response_rank = int(np.linalg.matrix_rank(response, tol=1.0e-10))
    roundtrip_effort = np.asarray(primary["effort"], dtype=float)
    roundtrip_forward = solver.forward_dynamics(q, rates, roundtrip_effort)
    reconstructed_effort = solver.inverse_dynamics(
        q,
        rates,
        roundtrip_forward.generalized_acceleration_mixed_units,
    )
    roundtrip_error_by_channel = np.abs(reconstructed_effort - roundtrip_effort)
    zero_result = solver.forward_dynamics(np.zeros(8), np.zeros(8), np.zeros(8))

    recompute_cases: list[dict[str, object]] = []
    derivative_consistency_max = 0.0
    for case in _recompute_case_inputs():
        case_q = np.asarray(case["q"], dtype=float)
        case_rates = np.asarray(case["rates"], dtype=float)
        case_effort = np.asarray(case["effort"], dtype=float)
        derivative_diagnostic = solver.reduced_mass_derivative_diagnostic(case_q)
        derivative_consistency_max = max(
            derivative_consistency_max,
            float(
                np.max(
                    derivative_diagnostic.per_coordinate_relative_consistency
                )
            ),
        )
        case_reduced = solver.reduced_mass_matrix(case_q)
        case_bias = _bias_from_derivatives(
            derivative_diagnostic.derivatives_mixed_units, case_rates
        )
        case_acceleration = np.linalg.solve(
            case_reduced, case_effort - case_bias
        )
        case_blocks = model.mass_matrix_blocks(case_q)
        case_base_twist = -np.linalg.solve(
            case_blocks.Hbb, case_blocks.Hbm @ case_rates
        )
        case_momentum = model.momentum(case_q, case_base_twist, case_rates)
        recompute_cases.append(
            {
                "case_id": case["case_id"],
                "generalized_coordinates": {
                    "values": case_q.tolist(),
                    "units_by_coordinate": list(GENERALIZED_COORDINATE_UNITS),
                },
                "generalized_rates": {
                    "values": case_rates.tolist(),
                    "units_by_coordinate": list(GENERALIZED_RATE_UNITS),
                },
                "generalized_effort": {
                    "values": case_effort.tolist(),
                    "units_by_coordinate": list(GENERALIZED_EFFORT_UNITS),
                },
                "main_backend_results": {
                    "generalized_bias_effort_values": case_bias.tolist(),
                    "generalized_bias_effort_units": list(GENERALIZED_EFFORT_UNITS),
                    "generalized_acceleration_values": case_acceleration.tolist(),
                    "generalized_acceleration_units": ["rad/s^2"] * 6
                    + ["m/s^2"] * 2,
                    "base_twist_body_values": case_base_twist.tolist(),
                    "base_twist_body_units": ["m/s"] * 3 + ["rad/s"] * 3,
                    "linear_momentum_residual_ns": float(
                        np.linalg.norm(case_momentum.linear_root_kg_m_s)
                    ),
                    "angular_momentum_about_root_residual_nms": float(
                        np.linalg.norm(
                            case_momentum.angular_about_root_kg_m2_s
                        )
                    ),
                    "numeric_reduced_mass_sha256": sha256_bytes(
                        np.asarray(case_reduced, dtype="<f8").tobytes(order="C")
                    ),
                },
                "finite_difference": {
                    "method": CHRISTOFFEL_BACKEND,
                    "coarse_steps": derivative_diagnostic.per_coordinate_coarse_step.tolist(),
                    "fine_steps": derivative_diagnostic.per_coordinate_fine_step.tolist(),
                    "step_units": list(
                        derivative_diagnostic.per_coordinate_step_units
                    ),
                    "relative_consistency_by_coordinate": derivative_diagnostic.per_coordinate_relative_consistency.tolist(),
                },
            }
        )

    free_history = solver.propagate(q, rates, step_s=0.002, steps=12)
    free_energy_drift = _relative_scalar_drift(free_history.kinetic_energy_j)
    free_linear_residual = float(
        np.max(free_history.linear_momentum_residual_ns)
    )
    free_angular_residual = float(
        np.max(free_history.angular_momentum_about_root_residual_nms)
    )
    free_quaternion_error = float(
        np.max(
            np.abs(
                np.linalg.norm(
                    free_history.base_quaternion_body_to_inertial_wxyz, axis=1
                )
                - 1.0
            )
        )
    )

    powered_effort = np.array(
        (0.02, -0.015, 0.01, 0.008, -0.006, 0.005, 0.001, -0.0008)
    )
    powered = solver.propagate(
        q,
        rates,
        step_s=0.001,
        steps=12,
        generalized_effort=powered_effort,
    )
    work_energy_error = float(
        np.max(
            np.abs(
                powered.kinetic_energy_j
                - powered.kinetic_energy_j[0]
                - powered.generalized_work_j
            )
        )
    )

    convergence_effort = np.array(
        (0.01, -0.008, 0.006, 0.004, -0.003, 0.002, 0.0005, -0.0004)
    )
    robot_coarse = solver.propagate(
        q,
        rates,
        step_s=0.002,
        steps=6,
        generalized_effort=convergence_effort,
    )
    robot_fine = solver.propagate(
        q,
        rates,
        step_s=0.001,
        steps=12,
        generalized_effort=convergence_effort,
    )
    service_convergence = {
        "revolute_coordinate_max_abs_rad": float(
            np.max(np.abs(robot_coarse.q[-1, :6] - robot_fine.q[-1, :6]))
        ),
        "prismatic_coordinate_max_abs_m": float(
            np.max(np.abs(robot_coarse.q[-1, 6:] - robot_fine.q[-1, 6:]))
        ),
        "revolute_rate_max_abs_rad_s": float(
            np.max(
                np.abs(robot_coarse.qdot[-1, :6] - robot_fine.qdot[-1, :6])
            )
        ),
        "prismatic_rate_max_abs_m_s": float(
            np.max(
                np.abs(robot_coarse.qdot[-1, 6:] - robot_fine.qdot[-1, 6:])
            )
        ),
        "base_position_norm_m": float(
            np.linalg.norm(
                robot_coarse.base_position_inertial_m[-1]
                - robot_fine.base_position_inertial_m[-1]
            )
        ),
        "base_linear_velocity_norm_m_s": float(
            np.linalg.norm(
                robot_coarse.base_twist_body_mixed_units[-1, :3]
                - robot_fine.base_twist_body_mixed_units[-1, :3]
            )
        ),
        "base_angular_velocity_norm_rad_s": float(
            np.linalg.norm(
                robot_coarse.base_twist_body_mixed_units[-1, 3:]
                - robot_fine.base_twist_body_mixed_units[-1, 3:]
            )
        ),
        "base_quaternion_geodesic_rad": _quaternion_geodesic(
            robot_coarse.base_quaternion_body_to_inertial_wxyz[-1],
            robot_fine.base_quaternion_body_to_inertial_wxyz[-1],
        ),
    }

    target_kwargs = {
        "mass_kg": 22.0,
        "inertia_body_kg_m2": np.array(
            ((2.1, 0.08, -0.03), (0.08, 3.2, 0.05), (-0.03, 0.05, 4.8))
        ),
        "position_inertial_initial_m": (1.2, -0.4, 0.7),
        "velocity_inertial_initial_m_s": (0.06, -0.025, 0.018),
        "omega_body_initial_rad_s": (0.31, 0.47, -0.26),
        "quaternion_body_to_inertial_initial_wxyz": (
            0.91,
            0.12,
            -0.18,
            0.34,
        ),
    }
    target = propagate_target_6dof(**target_kwargs, step_s=0.001, steps=500)
    target_linear_drift = _relative_vector_drift(
        target.linear_momentum_inertial_kg_m_s
    )
    target_spin_drift = _relative_vector_drift(
        target.spin_angular_momentum_about_com_inertial
    )
    target_total_angular_drift = _relative_vector_drift(
        target.total_angular_momentum_about_inertial_origin
    )
    target_energy_drift = _relative_scalar_drift(target.kinetic_energy_j)
    target_quaternion_error = float(
        np.max(
            np.abs(
                np.linalg.norm(target.quaternion_body_to_inertial_wxyz, axis=1)
                - 1.0
            )
        )
    )
    target_translation = float(
        np.linalg.norm(
            target.position_inertial_m[-1] - target.position_inertial_m[0]
        )
    )
    target_nonprincipal_evolution = float(
        np.linalg.norm(target.omega_body_rad_s[-1] - target.omega_body_rad_s[0])
    )
    target_coarse = propagate_target_6dof(
        **target_kwargs, step_s=0.002, steps=100
    )
    target_fine = propagate_target_6dof(
        **target_kwargs, step_s=0.001, steps=200
    )
    target_convergence = {
        "position_norm_m": float(
            np.linalg.norm(
                target_coarse.position_inertial_m[-1]
                - target_fine.position_inertial_m[-1]
            )
        ),
        "velocity_norm_m_s": float(
            np.linalg.norm(
                target_coarse.velocity_inertial_m_s[-1]
                - target_fine.velocity_inertial_m_s[-1]
            )
        ),
        "omega_norm_rad_s": float(
            np.linalg.norm(
                target_coarse.omega_body_rad_s[-1]
                - target_fine.omega_body_rad_s[-1]
            )
        ),
        "quaternion_geodesic_rad": _quaternion_geodesic(
            target_coarse.quaternion_body_to_inertial_wxyz[-1],
            target_fine.quaternion_body_to_inertial_wxyz[-1],
        ),
    }
    asymmetric_inertia_rejected = False
    try:
        propagate_target_6dof(
            22.0,
            ((2.0, 2.0e-10, 0.0), (0.0, 3.0, 0.0), (0.0, 0.0, 4.0)),
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
            (0.1, 0.2, 0.3),
            step_s=0.001,
            steps=1,
        )
    except URDFDynamicsError:
        asymmetric_inertia_rejected = True

    current_records = read_only_current_system_records()
    no_urdf_outputs = list(HERE.rglob("*.urdf")) == []
    checks: list[dict[str, object]] = []
    summary = model.model_summary()
    _check(
        checks,
        "A01",
        "synthetic fixture topology is 6R+2P and eight generalized coordinates",
        summary["revolute_joints"] == 6
        and summary["prismatic_joints"] == 2
        and summary["movable_dof"] == 8,
        summary,
    )
    _check(
        checks,
        "A02",
        "mixed generalized-coordinate and block-unit contract is complete",
        [item["generalized_effort_unit"] for item in solver.coordinate_contract[6:]]
        == list(GENERALIZED_EFFORT_UNITS)
        and MASS_MATRIX_BLOCK_UNIT_CONTRACT["global_single_unit"] is None,
        {
            "coordinate_contract": solver.coordinate_contract,
            "mass_matrix_block_unit_contract": MASS_MATRIX_BLOCK_UNIT_CONTRACT,
        },
    )
    _check(
        checks,
        "A03",
        "full 14x14 mixed-unit mass matrix is numerically SPD under declared SI scaling",
        full_mass.shape == (14, 14)
        and np.min(np.linalg.eigvalsh(full_mass)) > 1.0e-6,
        {
            "shape": list(full_mass.shape),
            "symmetry_max_abs": float(np.max(np.abs(full_mass - full_mass.T))),
            "numeric_minimum_eigenvalue_under_declared_SI_scaling": float(
                np.min(np.linalg.eigvalsh(full_mass))
            ),
        },
    )
    _check(
        checks,
        "A04",
        "reduced 8x8 mixed-unit matrix is numerically SPD under declared SI scaling",
        np.min(np.linalg.eigvalsh(reduced_mass)) > 1.0e-7,
        {
            "numeric_minimum_eigenvalue_under_declared_SI_scaling": float(
                np.min(np.linalg.eigvalsh(reduced_mass))
            ),
            "numeric_condition_number_under_declared_SI_scaling": float(
                np.linalg.cond(reduced_mass)
            ),
        },
    )
    _check(
        checks,
        "A05",
        "eight generalized-coordinate/generalized-effort channels are numerically independent",
        response_rank == 8,
        {
            "hardware_actuator_claimed": False,
            "declared_effort_units": list(GENERALIZED_EFFORT_UNITS),
            "numeric_response_rank_under_declared_SI_scaling": response_rank,
            "numeric_column_norms_under_declared_SI_scaling": np.linalg.norm(
                response, axis=0
            ).tolist(),
        },
    )
    _check(
        checks,
        "A06",
        "forward-inverse generalized-effort roundtrip is supplementary evidence",
        float(np.max(roundtrip_error_by_channel)) < 2.0e-11,
        {
            "maximum_absolute_error_by_channel": roundtrip_error_by_channel.tolist(),
            "units_by_channel": list(GENERALIZED_EFFORT_UNITS),
            "not_sole_dynamics_evidence": True,
        },
    )
    _check(
        checks,
        "A07",
        "zero state and zero generalized effort imply zero acceleration",
        np.linalg.norm(
            zero_result.full_acceleration_components_mixed_units
        )
        < 1.0e-14,
        {
            "numeric_full_acceleration_component_norm_under_declared_SI_scaling": float(
                np.linalg.norm(
                    zero_result.full_acceleration_components_mixed_units
                )
            )
        },
    )
    _check(
        checks,
        "A08",
        "each generalized-effort channel produces a base reaction column",
        float(np.min(np.linalg.norm(base_reaction_columns, axis=0))) > 1.0e-6,
        {
            "base_reaction_column_norms_under_declared_SI_scaling": np.linalg.norm(
                base_reaction_columns, axis=0
            ).tolist(),
            "hardware_actuator_claimed": False,
        },
    )
    _check(
        checks,
        "A09",
        "per-coordinate two-step Richardson derivative consistency",
        derivative_consistency_max < 5.0e-7,
        {
            "maximum_relative_consistency_across_three_states": derivative_consistency_max,
            "recompute_cases": len(recompute_cases),
        },
    )
    _check(
        checks,
        "A10",
        "free motion energy and separate linear/angular momentum closure",
        free_energy_drift < 2.0e-8
        and free_linear_residual < 2.0e-13
        and free_angular_residual < 2.0e-13,
        {
            "relative_energy_drift": free_energy_drift,
            "maximum_linear_momentum_residual_ns": free_linear_residual,
            "maximum_angular_momentum_about_root_residual_nms": free_angular_residual,
            "maximum_quaternion_norm_error": free_quaternion_error,
            "heterogeneous_six_vector_norm_used": False,
        },
    )
    _check(
        checks,
        "A11",
        "generalized work-energy closure",
        work_energy_error < 2.0e-9,
        {"maximum_absolute_work_energy_error_j": work_energy_error},
    )
    _check(
        checks,
        "A12",
        "service-body step-size convergence is passed componentwise by unit class",
        all(
            service_convergence[name] <= limit
            for name, limit in SERVICE_CONVERGENCE_LIMITS.items()
        ),
        {
            "observed": service_convergence,
            "predeclared_limits": SERVICE_CONVERGENCE_LIMITS,
            "heterogeneous_error_sum_used": False,
        },
    )
    _check(
        checks,
        "A13",
        "target has full translation and nonprincipal rotation",
        target_translation > 0.01 and target_nonprincipal_evolution > 1.0e-3,
        {
            "translation_m": target_translation,
            "omega_body_change_rad_s": target_nonprincipal_evolution,
        },
    )
    _check(
        checks,
        "A14",
        "target P, spin-H about CoM, total-H about inertial origin, E and quaternion close",
        target_linear_drift < 1.0e-14
        and target_spin_drift < 2.0e-12
        and target_total_angular_drift < 2.0e-12
        and target_energy_drift < 2.0e-13
        and target_quaternion_error < 2.0e-14,
        {
            "linear_momentum_relative_drift": target_linear_drift,
            "spin_angular_momentum_about_com_inertial_relative_drift": target_spin_drift,
            "total_angular_momentum_about_inertial_origin_relative_drift": target_total_angular_drift,
            "energy_relative_drift": target_energy_drift,
            "maximum_quaternion_norm_error": target_quaternion_error,
        },
    )
    _check(
        checks,
        "A15",
        "target step-size convergence is passed componentwise",
        all(
            target_convergence[name] <= limit
            for name, limit in TARGET_CONVERGENCE_LIMITS.items()
        ),
        {
            "observed": target_convergence,
            "predeclared_limits": TARGET_CONVERGENCE_LIMITS,
            "heterogeneous_error_sum_used": False,
        },
    )
    _check(
        checks,
        "A16",
        "target inertia asymmetry above tolerance fails closed",
        asymmetric_inertia_rejected,
        {
            "asymmetric_fixture_rejected": asymmetric_inertia_rejected,
            "silent_symmetrization_allowed": False,
        },
    )
    _check(
        checks,
        "A17",
        "no URDF artifact emitted",
        no_urdf_outputs,
        {
            "urdf_files_under_v3": []
            if no_urdf_outputs
            else [str(path) for path in HERE.rglob("*.urdf")]
        },
    )
    _check(
        checks,
        "A18",
        "exact frozen local test collection passes",
        tests["collect_return_code"] == 0
        and tests["test_return_code"] == 0
        and tests["exact_collection_match"] is True
        and tests["passed"] == len(EXPECTED_TEST_NODEIDS),
        tests,
    )

    ledger = {
        "schema": "SIM13_V3_PHASE_A_DYNAMICS_LEDGER_V2",
        "artifact_class": "SYNTHETIC_ONLY_GENERIC_NUMERICAL_DIAGNOSTIC",
        "hash_chain": {"upstream_source_manifest": source_manifest_reference},
        "fixture": {
            "fixture_id": FIXTURE_ID,
            "authority_class": FIXTURE_AUTHORITY_CLASS,
            "in_memory_xml_bytes": len(fixture_bytes),
            "in_memory_xml_sha256": sha256_bytes(fixture_bytes),
            "written_to_urdf_file": False,
            "solver_input": True,
        },
        "units": {
            "generalized_coordinates": list(GENERALIZED_COORDINATE_UNITS),
            "generalized_rates": list(GENERALIZED_RATE_UNITS),
            "generalized_effort": list(GENERALIZED_EFFORT_UNITS),
            "coordinate_contract": solver.coordinate_contract,
            "mass_matrix_block_unit_contract": MASS_MATRIX_BLOCK_UNIT_CONTRACT,
        },
        "backend": {
            "scope": BACKEND_SCOPE,
            "christoffel_backend": CHRISTOFFEL_BACKEND,
            "external_wrench": "ZERO",
            "total_momentum_constraint": "ZERO_WITH_LINEAR_AND_ANGULAR_RESIDUALS_REPORTED_SEPARATELY",
            "integration": "fixed_step_RK4_with_SE3_quaternion_reconstruction",
            "production_dynamics_gate_passed": PRODUCTION_DYNAMICS_GATE_PASSED,
        },
        "target_backend": {
            "scope": TARGET_BACKEND_SCOPE,
            "state": "position3+velocity3+omega_body3+quaternion4",
            "angular_momentum_outputs": [
                {
                    "name": "spin_angular_momentum_about_com_inertial",
                    "unit": "N*m*s",
                    "reference_point": "target_center_of_mass",
                },
                {
                    "name": "total_angular_momentum_about_inertial_origin",
                    "unit": "N*m*s",
                    "definition": "r_cross_m_v_plus_spin",
                    "reference_point": "inertial_origin",
                },
            ],
        },
        "independent_recompute_contract": {
            "required_method": "EXPLICIT_SCHUR_PLUS_FIVE_POINT_TRIPLE_CHRISTOFFEL_WITHOUT_IMPORTING_REDUCED_DYNAMICS",
            "cases": recompute_cases,
        },
        "metrics": {item["id"]: item["evidence"] for item in checks},
        "current_system_boundary": {
            "unified_r2_source_imported": False,
            "unified_r2_private_builder_called": False,
            "unified_r2_generator_called": False,
            "unified_r2_solver_input": False,
            "current_system_binding_passed": CURRENT_SYSTEM_BINDING_PASSED,
            "status": "HOLD_FRESH_OWNER_RUN_HASH_MEMORY_AUTHORIZATION_ABSENT",
            "read_only_hash_records": current_records,
        },
    }
    validation = {
        "schema": "SIM13_V3_PHASE_A_VALIDATION_V2",
        "hash_chain": {"upstream_source_manifest": source_manifest_reference},
        "checks": checks,
        "summary": {
            "pass": sum(item["pass"] for item in checks),
            "fail": sum(not item["pass"] for item in checks),
            "total": len(checks),
        },
    }
    return ledger, validation


def build_gate(
    validation: dict[str, object],
    source_manifest_reference: dict[str, object],
    evidence_manifest_reference: dict[str, object],
) -> dict[str, object]:
    all_passed = validation["summary"]["fail"] == 0
    return {
        "schema": "SIM13_V3_PHASE_A_DYNAMICS_GATE_V2",
        "overall_status": "PASS_DIAGNOSTIC_WITH_UNIFIED_R2_EXECUTION_BINDING_HOLD"
        if all_passed
        else "FAIL_DIAGNOSTIC",
        "hash_chain": {
            "upstream_source_manifest": source_manifest_reference,
            "upstream_evidence_manifest": evidence_manifest_reference,
        },
        "diagnostic_checks": validation["summary"],
        "gates": [
            {
                "id": "DYN-A01",
                "name": "generic synthetic eight-coordinate reduced dynamics numerical diagnostic",
                "status": "PASS_DIAGNOSTIC" if all_passed else "FAIL",
                "pass": all_passed,
            },
            {
                "id": "DYN-G01",
                "name": "current Unified-R2 execution and solver binding",
                "status": "HOLD_FRESH_OWNER_RUN_HASH_MEMORY_AUTHORIZATION_ABSENT",
                "pass": False,
            },
            {
                "id": "DYN-G02",
                "name": "production generalized-effort-driven dynamics",
                "status": "HOLD_NOT_IMPLEMENTED_OR_AUTHORIZED",
                "pass": False,
            },
            {
                "id": "DYN-G03",
                "name": "continuous contact and capture",
                "status": "HOLD_NOT_IN_SCOPE",
                "pass": False,
            },
            {
                "id": "DYN-G04",
                "name": "mechanical or simulation release",
                "status": "HOLD_NO_RELEASE_INHERITANCE",
                "pass": False,
            },
        ],
        "authorizations": {
            "generic_algorithm_diagnostic_ready": all_passed,
            "unified_r2_dynamic_analysis_ready": False,
            "production_dynamics_ready": False,
            "contact_capture_ready": False,
            "next_stage_authorized": False,
        },
        "prohibitions": [
            "DO_NOT_TREAT_SYNTHETIC_FIXTURE_AS_UNIFIED_R2",
            "DO_NOT_CALL_PRIVATE_UNIFIED_R2_BUILDER_WITHOUT_FRESH_AUTHORITY",
            "DO_NOT_CALL_UNIFIED_R2_GENERATOR_WITHOUT_FRESH_AUTHORITY",
            "DO_NOT_CLAIM_HARDWARE_ACTUATOR_INDEPENDENCE",
            "DO_NOT_COMBINE_LINEAR_AND_ANGULAR_MOMENTUM_IN_ONE_NORM",
            "DO_NOT_COMBINE_HETEROGENEOUS_STEP_ERRORS_WITHOUT_FROZEN_SCALING",
            "DO_NOT_CLAIM_PRODUCTION_DYNAMICS_CONTACT_CAPTURE_OR_RELEASE",
            "RICHARDSON_CHRISTOFFEL_IS_DIAGNOSTIC_ONLY",
        ],
    }


def main() -> int:
    source_records = _source_manifest_records()
    _write_csv_manifest(
        SOURCE_MANIFEST_PATH,
        "SIM13_V3_PHASE_A_SOURCE_MANIFEST_V2",
        source_records,
    )
    source_reference = _record(SOURCE_MANIFEST_PATH, "UPSTREAM_SOURCE_MANIFEST")
    tests = _run_tests()
    ledger, validation = build_evidence(source_reference, tests)
    _write_json(LEDGER_PATH, ledger)
    _write_json(VALIDATION_PATH, validation)
    evidence_manifest = {
        "schema": "SIM13_V3_PHASE_A_EVIDENCE_MANIFEST_V2",
        "upstream_source_manifest": source_reference,
        "self_excluded_path": EVIDENCE_MANIFEST_PATH.relative_to(
            PROJECT_ROOT
        ).as_posix(),
        "records": [
            _record(LEDGER_PATH, "DIAGNOSTIC_LEDGER"),
            _record(VALIDATION_PATH, "VALIDATION_EVIDENCE"),
        ],
    }
    _write_json(EVIDENCE_MANIFEST_PATH, evidence_manifest)
    evidence_reference = _record(
        EVIDENCE_MANIFEST_PATH, "UPSTREAM_EVIDENCE_MANIFEST"
    )
    gate = build_gate(validation, source_reference, evidence_reference)
    _write_json(GATE_PATH, gate)
    print(
        json.dumps(
            {
                "gate": gate["overall_status"],
                "checks": validation["summary"],
                "tests": {
                    "passed": tests["passed"],
                    "expected": tests["expected_count"],
                    "exact_collection_match": tests["exact_collection_match"],
                },
                "gate_path": GATE_PATH.relative_to(PROJECT_ROOT).as_posix(),
                "downstream_required": "run independent_audit_phase_a.py",
            },
            indent=2,
        )
    )
    return 0 if validation["summary"]["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
