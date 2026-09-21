#!/usr/bin/env python3
"""Build deterministic source-only evidence for the Sim13 V2 prebind package."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import inspect
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

import numpy as np
import yaml


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
SIM13_V2_DIR = HERE / "sim13_v2"
TESTS_DIR = HERE / "tests"
CONFIG_PATH = HERE / "config" / "authority_bindings_v2.json"
EVIDENCE_DIR = HERE / "evidence"
RESULTS_DIR = HERE / "results"
MANIFEST_PATH = EVIDENCE_DIR / "SIM13_V2_PREBIND_SOURCE_SHA256_V1.csv"
VALIDATION_PATH = EVIDENCE_DIR / "SIM13_V2_PREBIND_VALIDATION_V1.json"
RECEIPT_PATH = EVIDENCE_DIR / "SIM13_V2_PREBIND_RECEIPT_V1.md"
GATE_PATH = RESULTS_DIR / "SIM13_V2_PREBIND_SOURCE_GATE_V1.json"
SOURCE_GENERATOR = PROJECT_ROOT / (
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "unified_r2_digital_prototype_prebind/source_only_v2/"
    "unified_r2_urdf_source_v2.py"
)
FUTURE_URDF = PROJECT_ROOT / (
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "unified_r2_digital_prototype_prebind/generated_v2/"
    "unified_r2_c01_no_route_c_sim_candidate_v2.urdf"
)
FUTURE_INTERFACE = HERE / "interfaces" / "MECH_RL_SYSTEM_INTERFACE_V2.yaml"

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from sim13_v2 import authority_resolver as authority_module
from sim13_v2.authority_resolver import AuthorityResolver
from sim13_v2.contact_preflight import (
    ContactAuthority,
    ContactState,
    half_sine_equal_impulse_fixture,
    validate_contact_normal,
    validate_contact_window,
)
from sim13_v2.contracts import GateSnapshot
from sim13_v2.env import Sim13V2Environment
from sim13_v2.free_floating_dynamics import (
    BACKEND_SCOPE,
    PRODUCTION_DYNAMICS_GATE_PASSED,
    URDFTreeDynamics,
    propagate_free_rigid_body,
)
from sim13_v2.negative_controls import REGISTRY, evaluate_negative_controls
from sim13_v2.regression_oracles import (
    CURRENT_OBSERVED_THRESHOLD_REGISTRY_SHA256,
    CURRENT_REEXECUTION_HOLD,
    EXPLICIT_FIXTURE_NO_AUTHORITY,
    HARD_LOCK_SCOPE,
    SIM10_EXPECTED_THRESHOLD_REGISTRY_SHA256,
    ExplicitTargetFixture,
    audit_current_reexecution_inputs,
    combine_unified_r2_service_body,
    ideal_two_body_hard_lock,
    load_historical_regression_anchors,
    single_link_capture_sensitivity,
    validate_historical_artifacts,
)
from sim13_v2.system_model import EXPECTED_TOTAL_MASS_KG, SystemModel
from run_negative_controls_prebind_v1 import build_evidence as build_negative_control_evidence


NEGATIVE_CONTROL_EVIDENCE_PATH = (
    EVIDENCE_DIR / "SIM13_V2_NEGATIVE_CONTROLS_PREBIND_V1.json"
)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def _file_record(path: Path) -> dict[str, object]:
    payload = path.read_bytes()
    return {
        "path": path.relative_to(PROJECT_ROOT).as_posix(),
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
    }


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _write_json(path: Path, document: object) -> None:
    _write_bytes(path, _canonical_json_bytes(document))


def _canonical_json_bytes(document: object) -> bytes:
    return (
        json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _build_current_source_model() -> tuple[bytes, SystemModel, URDFTreeDynamics]:
    source = _load_module(SOURCE_GENERATOR, "unified_r2_source_for_sim13_v2_validation")
    inputs, _ = source._load_inputs_snapshot()
    payloads = source._verify_source_pins(inputs)
    robot = source._build_robot(inputs, payloads)
    xml_bytes = ET.tostring(robot, encoding="utf-8")
    system = SystemModel.from_xml_bytes(xml_bytes, artifact_root=SOURCE_GENERATOR.parent)
    dynamics = URDFTreeDynamics(xml_bytes)
    return xml_bytes, system, dynamics


def _run_tests() -> dict[str, object]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPATH"] = str(HERE)
    command = [
        sys.executable,
        "-B",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        str(TESTS_DIR),
    ]
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    combined = (completed.stdout + "\n" + completed.stderr).strip()
    match = re.search(r"(\d+) passed", combined)
    passed = int(match.group(1)) if match else 0
    return {
        "command": "python -B -m pytest -q -p no:cacheprovider tests",
        "return_code": completed.returncode,
        "passed": passed,
        "summary": f"{passed} passed" if match else "NO_PASS_SUMMARY",
    }


def _check(checks: list[dict[str, object]], check_id: str, name: str, condition: bool, evidence: object) -> None:
    checks.append(
        {
            "id": check_id,
            "name": name,
            "pass": bool(condition),
            "evidence": evidence,
        }
    )


def main() -> int:
    resolution = AuthorityResolver().resolve()
    env = Sim13V2Environment()
    _, reset_info = env.reset()
    _, _, terminated, _, step_info = env.step(
        {
            "grasp_candidate_id": "GC_PREBIND_PROBE",
            "capture_timing_id": "T_PREBIND_PROBE",
            "strategy_id": "S1",
        }
    )
    xml_bytes, system, dynamics = _build_current_source_model()
    q = np.zeros(dynamics.movable_dof)
    qdot = np.linspace(0.001, 0.008, dynamics.movable_dof)
    base_twist = dynamics.base_twist_for_zero_momentum(q, qdot)
    momentum_residual = float(
        np.linalg.norm(dynamics.momentum(q, base_twist, qdot).vector6)
    )
    mass_matrix = dynamics.mass_matrix(q)
    symmetry_residual = float(np.max(np.abs(mass_matrix - mass_matrix.T)))
    minimum_eigenvalue = float(np.min(np.linalg.eigvalsh(mass_matrix)))
    sensitivity = dynamics.single_link_sensitivity(
        q, "link3", mass_scale=1.01, inertia_scale=1.01
    )
    rigid_history = propagate_free_rigid_body(
        np.diag((2.0, 3.0, 4.0)),
        (0.2, 0.3, 0.4),
        step_s=1.0e-3,
        steps=1000,
    )
    h0 = rigid_history.angular_momentum_inertial_kg_m2_s[0]
    e0 = rigid_history.kinetic_energy_j[0]
    angular_momentum_relative_drift = float(
        np.max(
            np.linalg.norm(
                rigid_history.angular_momentum_inertial_kg_m2_s - h0,
                axis=1,
            )
        )
        / np.linalg.norm(h0)
    )
    energy_relative_drift = float(
        np.max(np.abs(rigid_history.kinetic_energy_j - e0)) / abs(e0)
    )
    provisional = ContactAuthority("PROVISIONAL", "A" * 64)
    normal_decision = validate_contact_normal((1.0, 0.0, 0.0), provisional)
    window_decision = validate_contact_window(0.020, provisional)
    half_sine = half_sine_equal_impulse_fixture(1.0, 0.020)
    negative_registry_summary = evaluate_negative_controls(())
    fresh_negative_control_evidence = build_negative_control_evidence()
    expected_negative_control_payload = _canonical_json_bytes(
        fresh_negative_control_evidence
    )
    negative_control_payload = (
        NEGATIVE_CONTROL_EVIDENCE_PATH.read_bytes()
        if NEGATIVE_CONTROL_EVIDENCE_PATH.is_file()
        else b""
    )
    negative_control_evidence_exact = (
        negative_control_payload == expected_negative_control_payload
    )
    negative_control_record = (
        _file_record(NEGATIVE_CONTROL_EVIDENCE_PATH)
        if NEGATIVE_CONTROL_EVIDENCE_PATH.is_file()
        else {
            "path": NEGATIVE_CONTROL_EVIDENCE_PATH.relative_to(PROJECT_ROOT).as_posix(),
            "bytes": 0,
            "sha256": None,
        }
    )
    negative_control_summary = fresh_negative_control_evidence["summary"]
    negative_control_holds = sorted(
        item["control_id"]
        for item in fresh_negative_control_evidence["controls"]
        if not item["executed"]
    )

    historical_validation = validate_historical_artifacts(PROJECT_ROOT)
    historical_anchors = load_historical_regression_anchors(PROJECT_ROOT)
    current_reexecution = audit_current_reexecution_inputs(PROJECT_ROOT)
    target_axis = np.asarray((1.0, 0.15, 0.4), dtype=float)
    target_fixture = ExplicitTargetFixture(
        fixture_id="VALIDATION_TARGET_22KG_NO_AUTHORITY",
        mass_kg=22.0,
        com_root_m=np.asarray((0.85, 0.12, -0.04), dtype=float),
        inertia_about_com_root_kg_m2=np.asarray(
            ((0.42, 0.015, 0.0), (0.015, 0.51, -0.01), (0.0, -0.01, 0.60)),
            dtype=float,
        ),
        linear_velocity_root_m_s=np.zeros(3),
        angular_velocity_root_rad_s=(
            np.deg2rad(3.0) * target_axis / np.linalg.norm(target_axis)
        ),
    )
    service_aggregate = combine_unified_r2_service_body(
        dynamics, np.zeros(dynamics.movable_dof)
    )
    hard_lock = ideal_two_body_hard_lock(
        service_aggregate,
        target_fixture,
        service_linear_velocity_root_m_s=(-0.01, 0.002, 0.0),
        service_angular_velocity_root_rad_s=(0.0, 0.0, 0.0),
    )
    capture_sensitivity = single_link_capture_sensitivity(
        dynamics,
        np.zeros(dynamics.movable_dof),
        target_fixture,
        "link3",
        mass_scale=1.02,
        inertia_scale=1.03,
        com_delta_link_m=(0.001, 0.0, 0.0),
        service_linear_velocity_root_m_s=(-0.01, 0.0, 0.0),
    )
    tests = _run_tests()
    gates = resolution.snapshot.as_dict()
    gate_counts = {
        state: sum(value == state for value in gates.values())
        for state in ("PASS", "FAIL", "UNKNOWN")
    }

    source_files = sorted(
        [
            HERE / "README.md",
            HERE / "pytest.ini",
            HERE / "run_negative_controls_prebind_v1.py",
            HERE / "validate_prebind_v2.py",
            CONFIG_PATH,
            *SIM13_V2_DIR.glob("*.py"),
            *TESTS_DIR.glob("*.py"),
        ],
        key=lambda path: path.as_posix(),
    )
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=("artifact_id", "path", "bytes", "sha256"),
        lineterminator="\n",
    )
    writer.writeheader()
    for index, path in enumerate(source_files, start=1):
        record = _file_record(path)
        writer.writerow({"artifact_id": f"SRC{index:02d}", **record})
    _write_bytes(MANIFEST_PATH, buffer.getvalue().encode("utf-8"))
    manifest_record = _file_record(MANIFEST_PATH)

    checks: list[dict[str, object]] = []
    _check(checks, "P01", "AUTHORITY_CONFIG_HASH_PINNED", resolution.config_sha256 == authority_module._EXPECTED_BINDINGS_SHA256, resolution.config_sha256)
    _check(checks, "P02", "AUTHORITY_CONFIG_VALID", resolution.config_valid, resolution.errors)
    verified = sorted(name for name, item in resolution.artifacts.items() if item.verified)
    _check(checks, "P03", "FIVE_CURRENT_ARTIFACTS_HASH_AND_METADATA_VERIFIED", len(verified) == 5, verified)
    absent = sorted(name for name, item in resolution.artifacts.items() if item.reason_code == "ARTIFACT_NOT_YET_INSTANTIATED")
    _check(checks, "P04", "SYSTEM_INTERFACE_AND_URDF_EXPLICITLY_ABSENT", absent == ["system_interface", "system_urdf"], absent)
    _check(checks, "P05", "TWELVE_GATE_COUNT_AND_CURRENT_ZERO_PASS", len(gates) == 12 and gate_counts == {"PASS": 0, "FAIL": 3, "UNKNOWN": 9}, {"states": gates, "counts": gate_counts})
    _check(checks, "P06", "PREBIND_SCOPE_LOCK_ACTIVE", resolution.snapshot.evidence("mechanical_system_binding").reason_code == "MECHANICAL_SYSTEM_BINDING_PREBIND_SCOPE_LOCK", resolution.snapshot.evidence("mechanical_system_binding").reason_code)
    _check(checks, "P07", "NON_ABORT_PROBE_EXECUTES_CANONICAL_ABORT", terminated and step_info["executed_action"] == {"grasp_candidate_id": "__ABORT__", "capture_timing_id": "__ABORT__", "strategy_id": "ABORT"}, step_info["executed_action"])
    _check(checks, "P08", "PUBLIC_API_HAS_NO_GATE_INJECTION", all("gates" not in inspect.signature(method).parameters for method in (Sim13V2Environment.reset, Sim13V2Environment.action_mask, Sim13V2Environment.step)) and not hasattr(GateSnapshot, "all_pass"), "reset/action_mask/step have no gates; GateSnapshot has no all_pass")
    _check(checks, "P09", "SYSTEM_TOPOLOGY_19_18_16_3_8", (len(system.link_names), len(system.joint_names), len(system.physical_link_names), len(system.frame_only_link_names), len(system.movable_joint_names)) == (19, 18, 16, 3, 8), {"links": len(system.link_names), "joints": len(system.joint_names), "physical": len(system.physical_link_names), "frame_only": len(system.frame_only_link_names), "movable": len(system.movable_joint_names)})
    _check(checks, "P10", "SYSTEM_MASS_EXACT", abs(system.total_mass_kg - EXPECTED_TOTAL_MASS_KG) <= 1.0e-12, system.total_mass_kg)
    expected_movable = ("joint1", "joint2", "joint3", "joint4", "joint5", "joint6", "gripper_joint1", "gripper_joint2")
    _check(checks, "P11", "FIXED_GRIPPER_EXCLUDED_FROM_EIGHT_DOF_STATE", system.movable_joint_names == expected_movable and "gripper_joint" in system.fixed_joint_names, {"movable": system.movable_joint_names, "fixed_contains_gripper_joint": "gripper_joint" in system.fixed_joint_names})
    _check(checks, "P12", "MASS_MATRIX_SYMMETRIC_POSITIVE_DEFINITE", symmetry_residual <= 1.0e-12 and minimum_eigenvalue > 0.0, {"symmetry_residual": symmetry_residual, "minimum_eigenvalue": minimum_eigenvalue})
    _check(checks, "P13", "ZERO_MOMENTUM_BASE_REACTION_CLOSES", momentum_residual <= 1.0e-12, momentum_residual)
    _check(checks, "P14", "SINGLE_LINK_MASS_INERTIA_PERTURBATION_IS_SENSITIVE", float(sensitivity["mass_matrix_frobenius_delta"]) > 0.0 and float(sensitivity["Hbm_frobenius_delta"]) > 0.0 and sensitivity["original_snapshot_unchanged"] is True, sensitivity)
    _check(checks, "P15", "FREE_TARGET_EULER_RK4_CONSERVES_H_AND_ENERGY", angular_momentum_relative_drift <= 1.0e-10 and energy_relative_drift <= 1.0e-10, {"angular_momentum_relative_drift": angular_momentum_relative_drift, "energy_relative_drift": energy_relative_drift})
    _check(checks, "P16", "DYNAMICS_SCOPE_STAYS_PREBIND_NOT_TORQUE_OR_CONTACT", BACKEND_SCOPE.endswith("NOT_TORQUE_DRIVEN_NOT_CONTACT") and PRODUCTION_DYNAMICS_GATE_PASSED is False, {"scope": BACKEND_SCOPE, "production_gate_passed": PRODUCTION_DYNAMICS_GATE_PASSED})
    _check(checks, "P17", "PROVISIONAL_NORMAL_AND_20MS_WINDOW_NEVER_PASS", normal_decision.state is ContactState.UNKNOWN and window_decision.state is ContactState.UNKNOWN, {"normal": normal_decision.state.value, "window": window_decision.state.value})
    _check(checks, "P18", "HALF_SINE_FIXTURE_EQUAL_IMPULSE_ONLY", abs(half_sine.normalization_error_Ns) <= 1.0e-15 and "NOT_CONTINUOUS_CONTACT_BACKEND" in half_sine.model_scope, {"normalization_error_Ns": half_sine.normalization_error_Ns, "scope": half_sine.model_scope})
    _check(
        checks,
        "P19",
        "FORMAL_NEGATIVE_CONTROL_SUBSET_15_PASS_5_DEPENDENCY_HOLD",
        len(REGISTRY) == 20
        and negative_registry_summary.executed == 0
        and negative_control_evidence_exact
        and negative_control_summary
        == {
            "total": 20,
            "executed": 15,
            "passed": 15,
            "failed": 0,
            "pass": 15,
            "fail": 0,
            "hold": 5,
            "not_run_dependency_hold": 5,
        }
        and negative_control_holds == ["NC15", "NC16", "NC18", "NC19", "NC20"]
        and fresh_negative_control_evidence["formal_runner_verdict"]
        == "PASS_EXECUTED_SUBSET_WITH_DEPENDENCY_HOLDS"
        and fresh_negative_control_evidence["release"] is False
        and fresh_negative_control_evidence["next"] is False
        and fresh_negative_control_evidence["next_stage_authorized"] is False,
        {
            "artifact": negative_control_record,
            "artifact_matches_fresh_deterministic_execution": negative_control_evidence_exact,
            "summary": negative_control_summary,
            "dependency_holds": negative_control_holds,
            "release": fresh_negative_control_evidence["release"],
            "next": fresh_negative_control_evidence["next"],
        },
    )
    sim06_anchors = historical_anchors["sim06"]
    sim10_anchors = historical_anchors["sim10"]
    _check(
        checks,
        "P20",
        "HASH_PINNED_SIM05_SIM06_SIM10_E19_HISTORICAL_REGRESSION_ANCHORS",
        historical_validation["all_required_exact"] is True
        and historical_validation["all_present_artifacts_exact"] is True
        and historical_validation["unified_r2_pass_inherited"] is False
        and historical_anchors["sim05"]["peak_base_deviation_text_deg"] == "19.199852"
        and sim06_anchors["debris_3dps"]["stored_post_rate_text_dps"] == "3.06333"
        and sim06_anchors["satellite_3dps"]["stored_post_rate_text_dps"] == "1.38721"
        and sim06_anchors["satellite_0p5dps"]["stored_post_rate_text_dps"] == "0.231202"
        and sim10_anchors["debris_sim06"]["exact_post_rate_dps"]
        == 3.0633304945807067
        and sim10_anchors["debris_sim06"]["region"] == "INFEASIBLE_RATE"
        and sim10_anchors["satellite_sim06"]["exact_post_rate_dps"]
        == 1.3872061825379134
        and sim10_anchors["satellite_sim06"]["region"]
        == "WHEELS_ONLY_FEASIBLE"
        and sim10_anchors["debris_sim06"]["csv_crosscheck"].within_tolerance
        is True
        and sim10_anchors["satellite_sim06"]["csv_crosscheck"].within_tolerance
        is True
        and historical_anchors["e19_optional"]["gate"] == "HOLD"
        and historical_anchors["e19_optional"]["release_credit"] is False
        and historical_anchors["unified_r2_pass_inherited"] is False,
        {
            "scope": historical_anchors["scope"],
            "sim05_peak_base_deviation_deg": historical_anchors["sim05"][
                "peak_base_deviation_deg"
            ],
            "sim06_stored_post_rates_dps": {
                key: value["stored_post_rate_dps"]
                for key, value in sim06_anchors.items()
            },
            "sim10": {
                key: {
                    "exact_post_rate_dps": value["exact_post_rate_dps"],
                    "region": value["region"],
                    "half_last_digit_crosscheck": value[
                        "csv_crosscheck"
                    ].within_tolerance,
                }
                for key, value in sim10_anchors.items()
            },
            "e19_gate": historical_anchors["e19_optional"]["gate"],
            "unified_r2_pass_inherited": False,
        },
    )
    _check(
        checks,
        "P21",
        "CURRENT_SIM05_SIM06_SIM10_REEXECUTION_FAILS_CLOSED_ON_PATH_AND_HASH_DRIFT",
        current_reexecution["current_reexecution_status"] == CURRENT_REEXECUTION_HOLD
        and current_reexecution["legacy_default_path_missing"] is True
        and current_reexecution["threshold_registry"]["expected_sha256"]
        == SIM10_EXPECTED_THRESHOLD_REGISTRY_SHA256
        and current_reexecution["threshold_registry"]["actual_sha256"]
        == CURRENT_OBSERVED_THRESHOLD_REGISTRY_SHA256
        and current_reexecution["threshold_registry"][
            "matches_sim10_frozen_expected"
        ]
        is False
        and current_reexecution["threshold_registry"][
            "matches_observed_current_pin"
        ]
        is True
        and current_reexecution["historical_gate_is_current_reexecution"] is False
        and current_reexecution["unified_r2_pass_inherited"] is False,
        current_reexecution,
    )
    _check(
        checks,
        "P22",
        "IDEAL_TWO_RIGID_BODY_HARD_LOCK_MOMENTUM_LIMIT_ONLY",
        hard_lock.scope == HARD_LOCK_SCOPE
        and hard_lock.target_authority_class == EXPLICIT_FIXTURE_NO_AUTHORITY
        and hard_lock.linear_momentum_relative_residual <= 1.0e-14
        and hard_lock.angular_momentum_relative_residual <= 1.0e-14
        and hard_lock.plastic_energy_nonincrease is True
        and hard_lock.contact_force_available is False
        and hard_lock.contact_time_history_available is False,
        {
            "scope": hard_lock.scope,
            "target_authority_class": hard_lock.target_authority_class,
            "post_rate_dps": hard_lock.post_rate_dps,
            "linear_momentum_relative_residual": hard_lock.linear_momentum_relative_residual,
            "angular_momentum_relative_residual": hard_lock.angular_momentum_relative_residual,
            "plastic_energy_loss_j": hard_lock.plastic_energy_loss_j,
            "contact_force_available": hard_lock.contact_force_available,
            "contact_time_history_available": hard_lock.contact_time_history_available,
        },
    )
    _check(
        checks,
        "P23",
        "SINGLE_LINK_PERTURBATION_CHANGES_CURRENT_IDEAL_CAPTURE_LIMIT",
        capture_sensitivity["capture_output_changed"] is True
        and capture_sensitivity["omega_vector_delta_norm_rad_s"] > 0.0
        and abs(capture_sensitivity["post_rate_delta_dps"]) > 0.0,
        {
            "scope": capture_sensitivity["scope"],
            "authority_class": capture_sensitivity["authority_class"],
            "link_name": capture_sensitivity["link_name"],
            "post_rate_delta_dps": capture_sensitivity["post_rate_delta_dps"],
            "omega_vector_delta_norm_rad_s": capture_sensitivity[
                "omega_vector_delta_norm_rad_s"
            ],
        },
    )
    _check(checks, "P24", "ALL_PACKAGE_TESTS_PASS", tests["return_code"] == 0 and tests["passed"] >= 62, tests)
    emitted_urdfs = sorted(path.relative_to(PROJECT_ROOT).as_posix() for path in HERE.rglob("*.urdf"))
    _check(checks, "P25", "NO_URDF_OR_INTERFACE_INSTANCE_EMITTED", not FUTURE_URDF.exists() and not FUTURE_INTERFACE.exists() and not emitted_urdfs, {"future_urdf_exists": FUTURE_URDF.exists(), "future_interface_exists": FUTURE_INTERFACE.exists(), "package_urdfs": emitted_urdfs})

    failed = [item["id"] for item in checks if not item["pass"]]
    validation = {
        "schema": "SIM13_V2_PREBIND_VALIDATION_V1",
        "generated_date_local": "2026-08-24",
        "artifact_class": "SOURCE_ONLY_PREBIND_NOT_BOUND_NOT_LOADED",
        "source_manifest": manifest_record,
        "checks": checks,
        "score": {"pass": len(checks) - len(failed), "total": len(checks), "failed": failed},
        "runtime_gate_status": {"states": gates, "counts": gate_counts},
        "negative_controls": {
            "declared": 20,
            "formally_executed": negative_control_summary["executed"],
            "formal_pass_credit": negative_control_summary["passed"],
            "formal_fail": negative_control_summary["failed"],
            "dependency_hold": negative_control_summary["hold"],
            "dependency_hold_ids": negative_control_holds,
            "evidence": negative_control_record,
            "status": fresh_negative_control_evidence["formal_runner_verdict"],
            "all_passed": False,
            "release_credit": False,
        },
        "regression_oracles": {
            "historical_scope": historical_anchors["scope"],
            "historical_artifacts_exact": bool(
                historical_validation["all_present_artifacts_exact"]
            ),
            "historical_gate_preserved": True,
            "historical_gate_is_current_reexecution": False,
            "unified_r2_pass_inherited": False,
            "current_reexecution_status": current_reexecution[
                "current_reexecution_status"
            ],
            "ideal_hard_lock_scope": hard_lock.scope,
            "ideal_hard_lock_contact_force_available": False,
            "ideal_hard_lock_contact_time_history_available": False,
        },
        "current_limits": {
            "system_interface_instantiated": False,
            "system_urdf_available": False,
            "owner_scope_accepted": False,
            "current_regression_reexecution_ready": False,
            "production_runtime_gate_passed": False,
            "torque_driven_dynamics_gate_passed": False,
            "contact_grasp_gate_passed": False,
            "next_stage_authorized": False,
        },
        "in_memory_source_snapshot": {"bytes": len(xml_bytes), "sha256": _sha256_bytes(xml_bytes), "written_as_urdf": False},
    }
    _write_json(VALIDATION_PATH, validation)
    validation_record = _file_record(VALIDATION_PATH)

    gate_pass = not failed
    gate = {
        "schema": "SIM13_V2_PREBIND_SOURCE_GATE_V1",
        "generated_date_local": "2026-08-24",
        "package_validation": "PASS" if gate_pass else "FAIL",
        "score": validation["score"],
        "source_manifest": manifest_record,
        "validation": validation_record,
        "prebind_source_implementation_passed": gate_pass,
        "system_interface_instantiated": False,
        "system_urdf_available": False,
        "negative_control_evidence": negative_control_record,
        "formal_negative_controls_declared": 20,
        "formal_negative_controls_executed": negative_control_summary["executed"],
        "formal_negative_controls_passed": negative_control_summary["passed"],
        "formal_negative_controls_failed": negative_control_summary["failed"],
        "formal_negative_controls_dependency_hold": negative_control_summary["hold"],
        "formal_negative_controls_hold_ids": negative_control_holds,
        "formal_negative_controls_all_passed": False,
        "historical_regression_oracles_verified": bool(
            historical_validation["all_present_artifacts_exact"]
        ),
        "historical_regression_pass_inherited_to_unified_r2": False,
        "current_regression_reexecution_status": current_reexecution[
            "current_reexecution_status"
        ],
        "ideal_hard_lock_limit_verified": True,
        "ideal_hard_lock_is_contact_backend": False,
        "runtime_fail_closed_gate_passed": False,
        "production_dynamics_gate_passed": False,
        "contact_grasp_gate_passed": False,
        "owner_accepted": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "maximum_current_operational_state": "ABORT_ONLY_WITH_SOURCE_ONLY_ANALYTIC_PREBIND_DIAGNOSTICS",
        "technical_verdict": (
            "SIM13_V2_SOURCE_ONLY_PREBIND_IMPLEMENTATION_PASS__"
            "HISTORICAL_REGRESSION_PINNED__15_OF_20_NC_PASS__"
            "URDF_INTERFACE_OWNER_ACTION_BOUND_RUNTIME_TORQUE_DYNAMICS_CONTACT_"
            "AND_FIVE_NC_DEPENDENCY_HOLD"
            if gate_pass
            else "SIM13_V2_SOURCE_ONLY_PREBIND_IMPLEMENTATION_FAIL"
        ),
    }
    _write_json(GATE_PATH, gate)
    gate_record = _file_record(GATE_PATH)

    receipt = f"""# Sim13 V2 prebind receipt V1

- Date: 2026-08-24
- Validation: `{validation_record['path']}` / `{validation_record['sha256']}`
- Gate: `{gate_record['path']}` / `{gate_record['sha256']}`
- Source manifest: `{manifest_record['path']}` / `{manifest_record['sha256']}`
- Negative-control evidence: `{negative_control_record['path']}` / `{negative_control_record['sha256']}`
- Unit tests: {tests['passed']} passed
- Current runtime gates: PASS={gate_counts['PASS']}, FAIL={gate_counts['FAIL']}, UNKNOWN={gate_counts['UNKNOWN']}
- Formal NC01--NC20 execution credit: {negative_control_summary['passed']}/20 PASS, {negative_control_summary['hold']}/20 dependency HOLD, {negative_control_summary['failed']}/20 FAIL
- Dependency HOLD IDs: {', '.join(negative_control_holds)}
- Historical sim05/sim06/sim10 anchors: hash-pinned and verified; not inherited as Unified R2 PASS
- Current sim05/sim06/sim10 re-execution: {current_reexecution['current_reexecution_status']}
- Current ideal hard-lock calculation: momentum-limit diagnostic only; no contact force/time history
- Operational state: ABORT only; source-only analytic diagnostics
- URDF/interface emitted: no/no
- `next_stage_authorized`: false

This receipt records implementation readiness only. It is not Owner acceptance,
mechanical binding, contact authority, production dynamics release, training
authority, hardware-motion authority, or flight qualification.
"""
    _write_bytes(RECEIPT_PATH, receipt.encode("utf-8"))

    print(json.dumps({"gate": gate_record, "score": validation["score"], "tests": tests, "runtime_gate_counts": gate_counts}, indent=2))
    return 0 if gate_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
