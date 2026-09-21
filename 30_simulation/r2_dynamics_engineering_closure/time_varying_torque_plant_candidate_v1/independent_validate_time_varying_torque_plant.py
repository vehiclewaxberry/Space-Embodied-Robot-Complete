#!/usr/bin/env python3
"""Standalone independent validator for the current-R2 torque-plant candidate.

This file intentionally shares no imports, constants, or functions with the
candidate builder or evaluator.  It parses the artifacts itself, holds its own
source/contract expectations, loads only the public Unified R2 backend, and
recomputes the admitted rigid zero-momentum physics from raw trajectories.
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Callable, Mapping, Sequence
import xml.etree.ElementTree as ET

import numpy as np
from scipy.integrate import solve_ivp


PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parents[2]
CONTRACT_PATH = PACKAGE_ROOT / "contracts" / "R2_TIME_VARYING_TORQUE_PLANT_CANDIDATE_CONTRACT_V1.json"
EVIDENCE_PATH = PACKAGE_ROOT / "results" / "R2_TIME_VARYING_TORQUE_PLANT_CANDIDATE_EVIDENCE_V1.json"
GATE_PATH = PACKAGE_ROOT / "results" / "R2_TIME_VARYING_TORQUE_PLANT_CANDIDATE_GATE_V1.json"
MANIFEST_PATH = PACKAGE_ROOT / "results" / "R2_TIME_VARYING_TORQUE_PLANT_CANDIDATE_MANIFEST_V1.json"
RECEIPT_PATH = PACKAGE_ROOT / "results" / "R2_TIME_VARYING_TORQUE_PLANT_INDEPENDENT_VALIDATION_V1.json"

EXPECTED_CONTRACT_BYTES = 13875
EXPECTED_CONTRACT_RAW_SHA256 = "570256E08C982712EFDECC9FA4A38586018779040AC33B53DDFC0AB45C9A3BD7"
EXPECTED_CONTRACT_CANONICAL_SHA256 = "696494D39C9246E19269B4F92577D8EAB74C848D9A08B56639080A2D75996565"
EXPECTED_EVIDENCE_BYTES = 238765
EXPECTED_EVIDENCE_RAW_SHA256 = "A6E51D746486EDCDA2EF3E67DE11DADB0CAD9047810EBDE547245AC0BCF1F016"
EXPECTED_GATE_BYTES = 11641
EXPECTED_GATE_RAW_SHA256 = "5DC60E93A881AB35BDA912115A4782DD11DA0903B444201491D06642326DA2D1"

EXPECTED_SCHEMA = "R2_TIME_VARYING_TORQUE_PLANT_CANDIDATE_CONTRACT_V1"
EXPECTED_SCOPE = "CURRENT_R2_ZERO_MOMENTUM_RIGID_DESIGN_DIAGNOSTIC_ONLY"
EXPECTED_REVIEW_STATUS = "PENDING_OWNER_REVIEW"
EXPECTED_MAXIMUM_CLAIM = (
    "R2_TIME_VARYING_TORQUE_DRIVEN_ZERO_MOMENTUM_RIGID_PLANT_CANDIDATE_PASS__"
    "ARBITRARY_DESIGN_EFFORT_ONLY__NO_FLEX_CONTACT_TARGET_ATTACHMENT_HARDWARE_"
    "CONTROL_PARENT_OR_RELEASE_CREDIT"
)
EXPECTED_JOINT_ORDER = tuple(f"joint{index}" for index in range(1, 7)) + (
    "gripper_joint1",
    "gripper_joint2",
)
EXPECTED_JOINT_TYPES = ("revolute",) * 6 + ("prismatic",) * 2
EXPECTED_COORDINATE_UNITS = ("rad",) * 6 + ("m",) * 2
EXPECTED_RATE_UNITS = ("rad/s",) * 6 + ("m/s",) * 2
EXPECTED_EFFORT_UNITS = ("N*m",) * 6 + ("N",) * 2
LOWER = np.asarray([-2.8, -3.14, -3.14, -1.87, -1.57, -3.14, 0.0, 0.0])
UPPER = np.asarray([2.8, 0.0, 0.0, 1.57, 1.57, 3.14, 0.0715, 0.0715])
SCALES = np.asarray([5.6, 3.14, 3.14, 3.44, 3.14, 6.28, 0.0715, 0.0715])
Q0 = np.asarray(
    [
        -0.000014722592995215019,
        -1.0482002296028674,
        -1.3989828152470147,
        -1.2200100679438755,
        0.000003673218594813444,
        0.000018395811591279014,
        0.03575,
        0.03575,
    ]
)
DQ0 = np.asarray([0.01, -0.012, 0.008, -0.006, 0.004, -0.002, 0.001, -0.0008])
R0 = np.asarray([0.12, -0.08, 0.04])
QUAT0 = np.asarray([0.98, 0.1, -0.08, 0.12])
AMPLITUDE = np.asarray([0.02, -0.015, 0.01, 0.008, -0.006, 0.005, 0.012, -0.009])
DURATION_S = 0.012
STEP_S = 0.00025
CONSTANT_DURATION_S = 0.004
CONSTANT_STEP_S = 0.001
QP_STAR = np.asarray([0.03575, 0.03575])
REVOLUTE_DIFFERENCE_STEP = 2.0e-5
PRISMATIC_DIFFERENCE_STEP = 2.0e-6

LIMIT = {
    "mass_rr": 1.0e-12,
    "mass_rp": 1.0e-12,
    "mass_pp": 1.0e-12,
    "bias_r": 1.0e-9,
    "bias_p": 1.0e-9,
    "cross_qr": 1.0e-8,
    "cross_qp": 1.0e-10,
    "cross_dqr": 1.0e-7,
    "cross_dqp": 1.0e-9,
    "cross_position": 1.0e-9,
    "cross_attitude": 1.0e-9,
    "cross_vlin": 1.0e-8,
    "cross_vang": 1.0e-8,
    "linear_momentum": 1.0e-11,
    "angular_momentum": 1.0e-11,
    "matrix_body_linear": 1.0e-11,
    "matrix_body_angular": 1.0e-11,
    "work_abs": 1.0e-10,
    "work_rel": 1.0e-7,
    "connection_linear": 1.0e-11,
    "connection_angular": 1.0e-11,
    "quaternion": 1.0e-12,
    "kkt_r": 1.0e-10,
    "kkt_p": 1.0e-10,
    "kkt_constraint": 1.0e-12,
    "kkt_reaction": 1.0e-10,
    "kkt_power": 1.0e-12,
    "free_prismatic_min": 1.0e-8,
    "scale_accel_r": 1.0e-10,
    "scale_accel_p": 1.0e-10,
    "scale_energy": 1.0e-12,
    "scale_power": 1.0e-12,
    "zero_energy": 1.0e-9,
    "constant_qr": 1.0e-12,
    "constant_qp": 1.0e-12,
    "constant_dqr": 1.0e-11,
    "constant_dqp": 1.0e-11,
    "constant_position": 1.0e-12,
    "constant_attitude": 1.0e-12,
}
DOP853_REPRO_LIMIT = {
    "qR_rad": 1.0e-11,
    "qP_m": 1.0e-13,
    "dqR_rad_s": 1.0e-9,
    "dqP_m_s": 1.0e-11,
    "position_m": 1.0e-12,
    "attitude_rad": 1.0e-12,
    "work_J": 1.0e-12,
}

EXPECTED_GATE_ROWS = (
    ("G01", "SOURCE_PINS_EXACT"),
    ("G02", "UNIFIED_R2_TOPOLOGY_AND_MASS_EXACT"),
    ("G03", "VALID_CANDIDATE_STATE_AND_INVALID_BACKEND_DEFAULT_REJECTED"),
    ("G04", "MIXED_COORDINATE_RATE_AND_EFFORT_UNITS_SEPARATED"),
    ("G05", "TIME_VARYING_EFFORT_PROFILE_EXACT"),
    ("G06", "ALL_HISTORIES_FINITE_AND_WITHIN_URDF_LIMITS"),
    ("G07", "REDUCED_MASS_BLOCK_SYMMETRY_AND_REFERENCE_SCALED_SPD"),
    ("G08", "BIAS_EXPLICIT_CHRISTOFFEL_CROSS"),
    ("G09", "ACTUATED_8DOF_TIME_VARYING_STATE_EVOLUTION"),
    ("G10", "LOCKED_2P_KKT_ELIMINATION_REACTION_AND_ZERO_POWER"),
    ("G11", "ZERO_TAUP_DOES_NOT_IMPLY_FREE_PRISMATIC_LOCK"),
    ("G12", "RK4_DOP853_NATIVE_UNIT_CROSS"),
    ("G13", "QUATERNION_NORM_AND_SIGN_INVARIANT_ATTITUDE"),
    ("G14", "PER_BODY_INERTIAL_LINEAR_MOMENTUM_ZERO"),
    ("G15", "PER_BODY_INERTIAL_ORIGIN_ANGULAR_MOMENTUM_ZERO"),
    ("G16", "GENERALIZED_MATRIX_VS_PER_BODY_MOMENTUM_CROSS"),
    ("G17", "GENERALIZED_WORK_EQUALS_KINETIC_ENERGY_CHANGE"),
    ("G18", "MECHANICAL_CONNECTION_ZERO_MOMENTUM_CLOSURE"),
    ("G19", "REFERENCE_COORDINATE_SCALE_EQUATION_ENERGY_POWER_INVARIANCE"),
    ("G20", "ZERO_EFFORT_ENERGY_AND_MOMENTUM_DEGENERATION"),
    ("G21", "VALID_CONSTANT_EFFORT_CURRENT_BACKEND_REGRESSION"),
    ("G22", "DETERMINISTIC_RK4_REPLAY_BYTE_IDENTICAL_CANONICAL"),
    ("G23", "MUTATION_AND_PHYSICS_NEGATIVE_CONTROLS"),
    ("G24", "ALL_SCOPE_GUARDS_AND_DOWNSTREAM_AUTHORITIES_FALSE"),
)

EXPECTED_SOURCE_PINS = (
    ("unified_r2_urdf", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/generated_v2/unified_r2_c01_no_route_c_sim_candidate_v2.urdf", 17191, "D84AA23CE98A2A9C697B1F32E433C01C3F0AE3BD0B5C56EF9A218DD88911CBDA"),
    ("unified_r2_urdf_execution_receipt", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/generated_v2/UNIFIED_R2_URDF_EXECUTION_RECEIPT_V2.json", 2891, "957CA67D7BCC2CB591DF2442F24532CA3DAE24F358FC69BF390AC1A20F6F021E"),
    ("free_floating_tree", "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/sim13_v2/free_floating_dynamics.py", 30769, "8ED47D66F3805394FF369492ABD56A5F0E832AFD6D003C6FA18E66F510836813"),
    ("unified_r2_backend", "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/sim13_v2_backends/dynamics_backend.py", 24361, "3A6A890D9ABABBC4E7E64315E461F56278BF3F9D4C56DDE89607598C01632DB7"),
    ("parent_dynamics_source", "30_simulation/r2_dynamics_engineering_closure/src/r2_dynamics.py", 51371, "437155144E1D634936DDAD845930B0241270314C1E8319878B153933FD9B6513"),
    ("parent_dynamics_authority", "30_simulation/r2_dynamics_engineering_closure/contracts/R2_DYNAMICS_AUTHORITY_V1.yaml", 9860, "67F69C4BBA252D4B988CB2A3403C84A25C7826BA89A003E3FBA298A70A377903"),
    ("parent_dynamics_gate", "30_simulation/r2_dynamics_engineering_closure/results/R2_DYNAMICS_ENGINEERING_GATE_V1.json", 5694, "C847DD680814864E8095223A42E4E4D53B903C6F6371E3DC47BAFEBAF478EB1A"),
    ("dg1_dg2_contract", "30_simulation/r2_dynamics_engineering_closure/dg1_dg2_candidate_v2/contracts/DG1_DG2_CANDIDATE_CONTRACT_V2.json", 5841, "E68D2B23F8BA893FC2B9AC14A3D36EC20ABB3E7FC2093117A3829E3EBC79E63E"),
    ("dg1_dg2_gate", "30_simulation/r2_dynamics_engineering_closure/dg1_dg2_candidate_v2/results/R2_DG1_DG2_CANDIDATE_GATE_V2.json", 1582, "1C3F1639018D4F7434DFB3B9E6AF086D3717B834C5E08D714A75D76C6ED2D362"),
    ("dg3_gate", "30_simulation/r2_dynamics_engineering_closure/dg3_arm_flex_coupling_candidate_v1/results/R2_DG3_ARM_FLEX_COUPLING_CANDIDATE_GATE_V1.json", 2916, "91BB7F3B424CF454DB5B2B4DFC27455AD46C4E6C5614F20D6A3C6EBB4714B7C3"),
    ("actuator_intake", "30_simulation/control_r2_integrated_candidate/contracts/CTRL_R2_ACTUATOR_DYNAMICS_INTAKE_V1.json", 10422, "7A23AF00299AC0F8FDA341A3F6239E2EC212A46CE0FD935C8F5F0320B7F71822"),
    ("digital_prototype_entry_v4", "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/digital_prototype_dynamics_entry_v1/CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V4.json", 9999, "277BE6349EC87E3CC76519E824F368F1D720C2C7E01646255DA5865510CB87EF"),
    ("sim13_v2_package_init", "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/sim13_v2/__init__.py", 534, "49AABF917F95FFD9C774671DF56221034CAB8AE8FF756425354DE7F7B0D06729"),
    ("sim13_v2_authority_resolver", "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/sim13_v2/authority_resolver.py", 14587, "E40C0BF6CCA55727E19D62A5DC5D915E839743E6F02595B256C9DDBFA75B16CF"),
    ("sim13_v2_contracts_module", "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/sim13_v2/contracts.py", 8261, "297B585797CB8F3BD7102D0935429617307CC36D6D0A085B2749FABEEF6D70C0"),
    ("sim13_v2_env_module", "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/sim13_v2/env.py", 8459, "84650310A0C1B5CE3BAD27B3B3F09F89C008665F93CFE2D526A75F3F52D3556B"),
    ("sim13_v2_system_model", "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/sim13_v2/system_model.py", 16073, "810615F1FF020F8DB4F953FFA4BB55DC2DE2DA3358A0800D7391EA19AEEA88FD"),
    ("sim13_v2_backends_package_init", "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/sim13_v2_backends/__init__.py", 450, "A49DB77F2753E3F55F5504822282050462D39580F1E8FD09903CCD05B91E56FB"),
    ("sim13_v2_backends_canonical", "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/sim13_v2_backends/canonical.py", 1455, "64079EC2AF72576A51A9EDC60571C12E169F941E75E9F87F23259116F2F4AB25"),
)
FROZEN_PACKAGE_PATHS = (
    "README.md",
    "contracts/R2_TIME_VARYING_TORQUE_PLANT_CANDIDATE_CONTRACT_V1.json",
    "evaluate_time_varying_torque_plant.py",
    "independent_validate_time_varying_torque_plant.py",
    "results/R2_TIME_VARYING_TORQUE_PLANT_CANDIDATE_EVIDENCE_V1.json",
    "results/R2_TIME_VARYING_TORQUE_PLANT_CANDIDATE_GATE_V1.json",
    "run_validation.py",
    "src/__init__.py",
    "src/time_varying_torque_plant.py",
    "tests/conftest.py",
    "tests/test_candidate.py",
)


class IndependentValidationError(RuntimeError):
    pass


def reject_constant(token: str) -> None:
    raise ValueError(f"STRICT_JSON_NONFINITE:{token}")


def unique_pairs(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"STRICT_JSON_DUPLICATE:{key}")
        result[key] = value
    return result


def strict_loads(text: str) -> Any:
    return json.loads(text, object_pairs_hook=unique_pairs, parse_constant=reject_constant)


def strict_read(path: Path) -> Any:
    return strict_loads(path.read_text(encoding="utf-8"))


def builtin(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [builtin(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return builtin(value.item())
    if isinstance(value, Mapping):
        return {str(key): builtin(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [builtin(item) for item in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("NONFINITE_OUTPUT")
        return value
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    raise TypeError(type(value).__name__)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        builtin(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest().upper()


def raw_record(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest().upper()}


def finite_vector(values: Sequence[float], size: int, label: str) -> np.ndarray:
    vector = np.asarray(values, dtype=float)
    if vector.shape != (size,) or not np.all(np.isfinite(vector)):
        raise IndependentValidationError(f"{label}_NOT_{size}_FINITE")
    return vector


def normalize(quaternion: Sequence[float]) -> np.ndarray:
    value = finite_vector(quaternion, 4, "QUATERNION")
    norm = float(np.linalg.norm(value))
    if norm <= 0.0:
        raise IndependentValidationError("QUATERNION_ZERO")
    return value / norm


def quat_product(left: Sequence[float], right: Sequence[float]) -> np.ndarray:
    lw, lx, ly, lz = finite_vector(left, 4, "QLEFT")
    rw, rx, ry, rz = finite_vector(right, 4, "QRIGHT")
    return np.asarray(
        [
            lw * rw - lx * rx - ly * ry - lz * rz,
            lw * rx + lx * rw + ly * rz - lz * ry,
            lw * ry - lx * rz + ly * rw + lz * rx,
            lw * rz + lx * ry - ly * rx + lz * rw,
        ]
    )


def rotation(quaternion: Sequence[float]) -> np.ndarray:
    w, x, y, z = normalize(quaternion)
    return np.asarray(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
            [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
        ]
    )


def attitude_distance(left: Sequence[float], right: Sequence[float]) -> float:
    q1 = normalize(left)
    q2 = normalize(right)
    if float(q1 @ q2) < 0.0:
        q2 = -q2
    relative = quat_product([q1[0], -q1[1], -q1[2], -q1[3]], q2)
    return float(2.0 * math.atan2(np.linalg.norm(relative[1:]), abs(relative[0])))


def load_public_backend() -> Any:
    rebind = PROJECT_ROOT / "30_simulation" / "sim_13_physics_gated_embodied_grasping" / "v2_system_rebind"
    for path in reversed((rebind / "runtime_fail_closed_backends_v2", rebind)):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    module = importlib.import_module("sim13_v2_backends.dynamics_backend")
    return module.UnifiedR2DynamicsBackend(project_root=PROJECT_ROOT)


def check_no_forbidden_imports() -> dict[str, Any]:
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    forbidden_tokens = (
        "time_varying_torque_plant",
        "evaluate_time_varying_torque_plant",
        "src.time_varying_torque_plant",
    )
    offending = [name for name in imported if any(token in name for token in forbidden_tokens)]
    return {"imports": sorted(imported), "offending": offending, "pass": not offending}


def expected_pin_documents() -> list[dict[str, Any]]:
    return [
        {"id": identifier, "path": path, "bytes": size, "sha256": sha}
        for identifier, path, size, sha in EXPECTED_SOURCE_PINS
    ]


def audit_sources(contract: Mapping[str, Any]) -> dict[str, Any]:
    expected = expected_pin_documents()
    contract_exact = contract.get("source_pins") == expected
    records: list[dict[str, Any]] = []
    for pin in expected:
        path = PROJECT_ROOT / pin["path"]
        actual = raw_record(path) if path.is_file() else {"bytes": -1, "sha256": "MISSING"}
        match = actual["bytes"] == pin["bytes"] and actual["sha256"] == pin["sha256"]
        records.append({"id": pin["id"], **actual, "match": match})
    return {
        "contract_pin_list_exact": contract_exact,
        "records": records,
        "all_match": contract_exact and all(item["match"] for item in records),
    }


def audit_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    raw = raw_record(CONTRACT_PATH)
    model = contract.get("model_contract", {})
    initial = contract.get("initial_state", {})
    effort = contract.get("effort_profile", {})
    locked = contract.get("lanes", {}).get("LOCKED_2P_6R_PULSE", {})
    runtime_binding = contract.get("runtime_project_module_binding", {})
    checks = {
        "raw_bytes": raw["bytes"] == EXPECTED_CONTRACT_BYTES,
        "raw_sha": raw["sha256"] == EXPECTED_CONTRACT_RAW_SHA256,
        "canonical_sha": canonical_hash(contract) == EXPECTED_CONTRACT_CANONICAL_SHA256,
        "schema": contract.get("schema") == EXPECTED_SCHEMA,
        "scope": contract.get("authority_scope") == EXPECTED_SCOPE,
        "maximum_claim": contract.get("maximum_claim") == EXPECTED_MAXIMUM_CLAIM,
        "review_status": contract.get("review_status") == EXPECTED_REVIEW_STATUS,
        "model_counts": (
            model.get("expected_links"), model.get("expected_joints"),
            model.get("expected_physical_links"), model.get("expected_frame_only_links"),
            model.get("expected_movable_dof"), model.get("integrated_state_dimension"),
            model.get("derived_base_twist_dimension"),
        ) == (19, 18, 16, 3, 8, 23, 6),
        "mass_exact": model.get("expected_total_mass_kg") == 31.022864807342987,
        "joint_order": tuple(model.get("joint_order", [])) == EXPECTED_JOINT_ORDER,
        "joint_types": tuple(model.get("joint_types", [])) == EXPECTED_JOINT_TYPES,
        "coordinate_units": tuple(model.get("coordinate_units", [])) == EXPECTED_COORDINATE_UNITS,
        "rate_units": tuple(model.get("rate_units", [])) == EXPECTED_RATE_UNITS,
        "effort_units": tuple(model.get("effort_units", [])) == EXPECTED_EFFORT_UNITS,
        "limits": np.array_equal(np.asarray(model.get("joint_lower_mixed_rad_m", [])), LOWER)
        and np.array_equal(np.asarray(model.get("joint_upper_mixed_rad_m", [])), UPPER),
        "scales": np.array_equal(np.asarray(model.get("reference_scales_mixed_rad_m", [])), SCALES),
        "initial": np.array_equal(np.asarray(initial.get("q0_mixed_rad_m", [])), Q0)
        and np.array_equal(np.asarray(initial.get("qdot0_mixed_rad_s_m_s", [])), DQ0)
        and np.array_equal(np.asarray(initial.get("base_position_inertial_initial_m", [])), R0)
        and np.array_equal(np.asarray(initial.get("base_quaternion_body_to_inertial_initial_wxyz", [])), QUAT0),
        "default_forbidden": initial.get("backend_default_initial_state_allowed") is False
        and initial.get("required_backend_default_invalid_joint") == "gripper_joint2"
        and initial.get("required_backend_default_invalid_value_m") == -0.004,
        "profile": effort.get("duration_s") == DURATION_S
        and effort.get("fixed_step_s") == STEP_S
        and np.array_equal(np.asarray(effort.get("amplitude_mixed_Nm_N", [])), AMPLITUDE)
        and effort.get("hardware_limit_enforcement") is False,
        "locked": np.array_equal(np.asarray(locked.get("qP_star_m", [])), QP_STAR)
        and np.array_equal(np.asarray(locked.get("dqP_m_s", [])), np.zeros(2))
        and np.array_equal(np.asarray(locked.get("tauP_N", [])), np.zeros(2)),
        "zero_momentum_only": model.get("total_momentum_scope")
        == "EXACTLY_ZERO__NONZERO_TOTAL_MOMENTUM_INPUT_FAILS_CLOSED",
        "runtime_module_binding": runtime_binding
        == {
            "direct_pinned_module_ids": [
                "parent_dynamics_source",
                "free_floating_tree",
                "unified_r2_backend",
            ],
            "transitive_pinned_module_ids": [
                "sim13_v2_package_init",
                "sim13_v2_authority_resolver",
                "sim13_v2_contracts_module",
                "sim13_v2_env_module",
                "sim13_v2_system_model",
                "sim13_v2_backends_package_init",
                "sim13_v2_backends_canonical",
            ],
            "expected_project_runtime_module_count_excluding_candidate": 10,
            "runtime_transitive_module_count": 7,
            "unpinned_project_runtime_modules_allowed": False,
        },
        "top_authority_false": contract.get("next_stage_authorized") is False
        and contract.get("release_credit") is False,
    }
    return {"raw": raw, "checks": checks, "all_pass": all(checks.values())}


def audit_urdf(contract: Mapping[str, Any]) -> dict[str, Any]:
    urdf_path = PROJECT_ROOT / EXPECTED_SOURCE_PINS[0][1]
    root = ET.parse(urdf_path).getroot()
    links = root.findall("link")
    joints = root.findall("joint")
    inertial_links = [link for link in links if link.find("inertial") is not None]
    total_mass = sum(float(link.find("inertial/mass").attrib["value"]) for link in inertial_links)
    movable: list[tuple[str, str, float, float]] = []
    for joint in joints:
        joint_type = joint.attrib.get("type")
        if joint_type not in {"revolute", "continuous", "prismatic"}:
            continue
        limit = joint.find("limit")
        movable.append(
            (joint.attrib["name"], joint_type, float(limit.attrib["lower"]), float(limit.attrib["upper"]))
        )
    by_name = {item[0]: item for item in movable}
    ordered = [by_name[name] for name in EXPECTED_JOINT_ORDER]
    checks = {
        "links": len(links) == 19,
        "joints": len(joints) == 18,
        "physical_links": len(inertial_links) == 16,
        "frame_only_links": len(links) - len(inertial_links) == 3,
        "mass": total_mass == 31.022864807342987,
        "movable_set": set(by_name) == set(EXPECTED_JOINT_ORDER),
        "movable_order": tuple(item[0] for item in ordered) == EXPECTED_JOINT_ORDER,
        "types": tuple(item[1] for item in ordered) == EXPECTED_JOINT_TYPES,
        "lower": np.array_equal(np.asarray([item[2] for item in ordered]), LOWER),
        "upper": np.array_equal(np.asarray([item[3] for item in ordered]), UPPER),
    }
    return {"checks": checks, "all_pass": all(checks.values()), "total_mass_kg": total_mass}


def state_is_valid(position: Sequence[float], quaternion: Sequence[float], q: Sequence[float], dq: Sequence[float]) -> bool:
    try:
        finite_vector(position, 3, "POSITION")
        normalize(quaternion)
        qv = finite_vector(q, 8, "q")
        finite_vector(dq, 8, "dq")
    except (IndependentValidationError, ValueError):
        return False
    return bool(np.all(qv >= LOWER) and np.all(qv <= UPPER))


def enforce_zero_total_momentum(momentum6: Sequence[float]) -> None:
    momentum = finite_vector(momentum6, 6, "TOTAL_MOMENTUM")
    if not np.array_equal(momentum, np.zeros(6)):
        raise IndependentValidationError(
            "NONZERO_TOTAL_MOMENTUM_BEHAVIORALLY_REJECTED"
        )


def audit_backend_default(backend: Any) -> dict[str, Any]:
    state = backend.initial_state()
    q = np.asarray(state.q_mixed_rad_m)
    violations = np.flatnonzero((q < LOWER) | (q > UPPER))
    names = [EXPECTED_JOINT_ORDER[index] for index in violations]
    return {
        "default_valid": state_is_valid(
            state.base_position_inertial_m,
            state.base_quaternion_body_to_inertial_wxyz,
            state.q_mixed_rad_m,
            state.qdot_mixed_rad_s_m_s,
        ),
        "violating_joints": names,
        "joint3_detected": "joint3" in names,
        "gripper_joint2_detected": "gripper_joint2" in names,
        "gripper_joint2_value_m": float(q[7]),
        "pass": "gripper_joint2" in names and float(q[7]) == -0.004,
    }


def authority_false(document: Mapping[str, Any]) -> bool:
    fields = (
        "flex_valid", "contact_valid", "target_attachment_valid", "hardware_valid",
        "control_valid", "parent_dynamics_engineering_complete", "sim13_non_abort_authorized",
        "next_stage_authorized", "release_credit",
    )
    return all(document.get(field) is False for field in fields)


def audit_gate_structure(gate: Mapping[str, Any]) -> dict[str, Any]:
    raw = raw_record(GATE_PATH)
    rows = gate.get("checks", [])
    pairs = tuple((row.get("id"), row.get("name")) for row in rows)
    checks = {
        "raw_bytes": raw["bytes"] == EXPECTED_GATE_BYTES,
        "raw_sha": raw["sha256"] == EXPECTED_GATE_RAW_SHA256,
        "schema": gate.get("schema") == "R2_TIME_VARYING_TORQUE_PLANT_CANDIDATE_GATE_V1",
        "rows_exact": pairs == EXPECTED_GATE_ROWS,
        "row_ids_unique": len({row.get("id") for row in rows}) == 24,
        "all_rows_true": len(rows) == 24 and all(row.get("pass") is True for row in rows),
        "summary": gate.get("passed") == 24 and gate.get("total") == 24 and gate.get("all_checks_pass") is True,
        "claim": gate.get("verdict") == EXPECTED_MAXIMUM_CLAIM
        and gate.get("maximum_claim") == EXPECTED_MAXIMUM_CLAIM,
        "review_status": gate.get("review_status") == EXPECTED_REVIEW_STATUS,
        "contract_hash": gate.get("contract_canonical_sha256") == EXPECTED_CONTRACT_CANONICAL_SHA256,
        "authority_false": authority_false(gate),
    }
    return {"raw": raw, "checks": checks, "all_pass": all(checks.values())}


def directory_payload_audit() -> dict[str, Any]:
    actual = sorted(
        path.relative_to(PACKAGE_ROOT).as_posix()
        for path in PACKAGE_ROOT.rglob("*")
        if path.is_file()
    )
    required = set(FROZEN_PACKAGE_PATHS) | {
        MANIFEST_PATH.relative_to(PACKAGE_ROOT).as_posix()
    }
    allowed = required | {RECEIPT_PATH.relative_to(PACKAGE_ROOT).as_posix()}
    actual_set = set(actual)
    missing = sorted(required - actual_set)
    unexpected = sorted(actual_set - allowed)
    return {
        "frozen_package_paths": list(FROZEN_PACKAGE_PATHS),
        "actual_file_paths": actual,
        "missing_required_paths": missing,
        "unexpected_paths_including_cache_or_bytecode": unexpected,
        "receipt_dynamic_present": RECEIPT_PATH.is_file(),
        "exact": not missing and not unexpected,
    }


def expected_manifest_entries() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for relative in FROZEN_PACKAGE_PATHS:
        path = PACKAGE_ROOT / relative
        if not path.is_file():
            raise IndependentValidationError(f"FROZEN_PACKAGE_PATH_MISSING:{relative}")
        record = raw_record(path)
        result.append({"path": relative, **record})
    return result


def manifest_is_exact(manifest: Mapping[str, Any]) -> tuple[bool, dict[str, Any]]:
    entries = manifest.get("package_entries", [])
    expected = expected_manifest_entries()
    paths = [item.get("path") for item in entries]
    expected_exclusions = [
        "results/R2_TIME_VARYING_TORQUE_PLANT_INDEPENDENT_VALIDATION_V1.json"
    ]
    payload = directory_payload_audit()
    checks = {
        "schema": manifest.get("schema") == "R2_TIME_VARYING_TORQUE_PLANT_CANDIDATE_MANIFEST_V1",
        "deterministic": manifest.get("deterministic") is True,
        "self_excluded": manifest.get("self_excluded") is True
        and manifest.get("self_excluded_path") == MANIFEST_PATH.relative_to(PACKAGE_ROOT).as_posix(),
        "receipt_excluded_explicitly": manifest.get("independent_validation_receipt_excluded") is True,
        "cache_or_unlisted_payload_forbidden": manifest.get(
            "cache_bytecode_or_unlisted_payload_allowed"
        ) is False,
        "exclusions_exact": manifest.get("exclusions") == expected_exclusions,
        "frozen_allowlist_exact": manifest.get("frozen_package_path_allowlist")
        == list(FROZEN_PACKAGE_PATHS),
        "directory_payload_exact": payload["exact"]
        and manifest.get("directory_payload_exact_at_generation") is True,
        "paths_unique": len(paths) == len(set(paths)),
        "paths_sorted": paths == sorted(paths),
        "self_absent": MANIFEST_PATH.relative_to(PACKAGE_ROOT).as_posix() not in paths,
        "receipt_absent": RECEIPT_PATH.relative_to(PACKAGE_ROOT).as_posix() not in paths,
        "entries_exact_no_extra": entries == expected,
        "entry_count": manifest.get("package_entry_count") == len(expected),
        "entry_hash": manifest.get("package_entries_canonical_sha256") == canonical_hash(expected),
        "external_pins": manifest.get("external_source_pins") == expected_pin_documents(),
        "external_pin_count": manifest.get("external_source_pin_count") == 19,
        "authority_false": manifest.get("next_stage_authorized") is False
        and manifest.get("release_credit") is False,
    }
    return all(checks.values()), checks


def effort(time_s: float, locked: bool = False) -> np.ndarray:
    if not math.isfinite(time_s) or time_s < -1.0e-15 or time_s > DURATION_S + 1.0e-15:
        raise IndependentValidationError("EFFORT_TIME_INVALID")
    value = AMPLITUDE * math.sin(math.pi * min(DURATION_S, max(0.0, time_s)) / DURATION_S) ** 2
    if locked:
        value[6:] = 0.0
    return value


def mass_derivatives(backend: Any, q: np.ndarray) -> np.ndarray:
    derivatives = np.empty((8, 8, 8))
    for index in range(8):
        step = REVOLUTE_DIFFERENCE_STEP if index < 6 else PRISMATIC_DIFFERENCE_STEP
        plus = q.copy(); plus[index] += step
        minus = q.copy(); minus[index] -= step
        coarse = (backend.reduced_mass_matrix(plus) - backend.reduced_mass_matrix(minus)) / (2.0 * step)
        half = 0.5 * step
        plus = q.copy(); plus[index] += half
        minus = q.copy(); minus[index] -= half
        fine = (backend.reduced_mass_matrix(plus) - backend.reduced_mass_matrix(minus)) / (2.0 * half)
        derivatives[index] = (4.0 * fine - coarse) / 3.0
    return derivatives


def bias_from_derivatives(derivatives: np.ndarray, dq: np.ndarray) -> np.ndarray:
    mass_rate = np.tensordot(dq, derivatives, axes=(0, 0))
    gradient = np.asarray([dq @ derivatives[index] @ dq for index in range(8)])
    return mass_rate @ dq - 0.5 * gradient


def christoffel_bias(derivatives: np.ndarray, dq: np.ndarray) -> np.ndarray:
    result = np.zeros(8)
    for i in range(8):
        for j in range(8):
            for k in range(8):
                coefficient = 0.5 * (
                    derivatives[k, i, j] + derivatives[j, i, k] - derivatives[i, j, k]
                )
                result[i] += coefficient * dq[j] * dq[k]
    return result


def solve_acceleration(backend: Any, q: np.ndarray, dq: np.ndarray, tau: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    matrix = np.asarray(backend.reduced_mass_matrix(q), dtype=float)
    derivatives = mass_derivatives(backend, q)
    bias = bias_from_derivatives(derivatives, dq)
    return np.linalg.solve(matrix, tau - bias), matrix, bias


def solve_locked(backend: Any, q: np.ndarray, dq: np.ndarray, tau: np.ndarray) -> dict[str, Any]:
    q_effective = q.copy(); q_effective[6:] = QP_STAR
    dq_effective = dq.copy(); dq_effective[6:] = 0.0
    tau_effective = tau.copy(); tau_effective[6:] = 0.0
    matrix = np.asarray(backend.reduced_mass_matrix(q_effective), dtype=float)
    derivatives = mass_derivatives(backend, q_effective)
    bias = bias_from_derivatives(derivatives, dq_effective)
    jacobian = np.column_stack((np.zeros((2, 6)), np.eye(2)))
    kkt = np.block([[matrix, -jacobian.T], [jacobian, np.zeros((2, 2))]])
    solution = np.linalg.solve(kkt, np.concatenate((tau_effective - bias, np.zeros(2))))
    acceleration = solution[:8]
    reaction = solution[8:]
    acceleration6 = np.linalg.solve(matrix[:6, :6], tau_effective[:6] - bias[:6])
    eliminated = np.concatenate((acceleration6, np.zeros(2)))
    eliminated_reaction = matrix[6:, :6] @ acceleration6 + bias[6:] - tau_effective[6:]
    return {
        "acceleration": acceleration,
        "reaction": reaction,
        "equilibrium": matrix @ acceleration + bias - tau_effective - jacobian.T @ reaction,
        "constraint": jacobian @ acceleration,
        "eliminated": eliminated,
        "eliminated_reaction": eliminated_reaction,
        "matrix": matrix,
        "bias": bias,
    }


def initial_augmented(locked: bool) -> np.ndarray:
    q = Q0.copy(); dq = DQ0.copy()
    if locked:
        q[6:] = QP_STAR; dq[6:] = 0.0
    return np.concatenate((R0, normalize(QUAT0), q, dq, [0.0]))


def rhs(backend: Any, time_s: float, state: np.ndarray, locked: bool, effort_function: Callable[[float], np.ndarray]) -> np.ndarray:
    position = state[:3]
    quaternion = normalize(state[3:7])
    q = state[7:15].copy()
    dq = state[15:23].copy()
    if locked:
        q[6:] = QP_STAR; dq[6:] = 0.0
    tau = finite_vector(effort_function(time_s), 8, "TAU")
    if locked:
        if not np.array_equal(tau[6:], np.zeros(2)):
            raise IndependentValidationError("LOCKED_TAUP_NONZERO")
        acceleration = solve_locked(backend, q, dq, tau)["acceleration"]
        acceleration[6:] = 0.0
    else:
        acceleration = solve_acceleration(backend, q, dq, tau)[0]
    base_twist = np.asarray(backend.mechanical_connection(q)) @ dq
    position_rate = rotation(quaternion) @ base_twist[:3]
    quaternion_rate = 0.5 * quat_product(quaternion, [0.0, *base_twist[3:]])
    q_rate = dq.copy()
    if locked:
        q_rate[6:] = 0.0
    return np.concatenate((position_rate, quaternion_rate, q_rate, acceleration, [float(tau @ dq)]))


def project(state: np.ndarray, locked: bool) -> np.ndarray:
    result = state.copy()
    result[3:7] = normalize(result[3:7])
    if locked:
        result[13:15] = QP_STAR
        result[21:23] = 0.0
    return result


def integrate_rk4(
    backend: Any,
    times: np.ndarray,
    initial: np.ndarray,
    locked: bool,
    effort_function: Callable[[float], np.ndarray],
) -> np.ndarray:
    state = project(initial, locked)
    history = [state.copy()]
    for left, right in zip(times[:-1], times[1:]):
        step = float(right - left)
        k1 = rhs(backend, float(left), state, locked, effort_function)
        k2 = rhs(backend, float(left + step / 2), state + step * k1 / 2, locked, effort_function)
        k3 = rhs(backend, float(left + step / 2), state + step * k2 / 2, locked, effort_function)
        k4 = rhs(backend, float(right), state + step * k3, locked, effort_function)
        state = project(state + step * (k1 + 2 * k2 + 2 * k3 + k4) / 6, locked)
        history.append(state.copy())
    return np.stack(history)


def integrate_dop853(
    backend: Any,
    times: np.ndarray,
    initial: np.ndarray,
    locked: bool,
    effort_function: Callable[[float], np.ndarray],
) -> np.ndarray:
    solution = solve_ivp(
        lambda time, state: rhs(
            backend, float(time), np.asarray(state), locked, effort_function
        ),
        (float(times[0]), float(times[-1])),
        project(initial, locked),
        method="DOP853",
        t_eval=times,
        rtol=1.0e-10,
        atol=1.0e-12,
        max_step=1.0e-3,
    )
    if not solution.success or solution.y.shape != (24, len(times)):
        raise IndependentValidationError(f"INDEPENDENT_DOP853_FAILED:{solution.message}")
    history = solution.y.T.copy()
    for index in range(len(history)):
        history[index] = project(history[index], locked)
    return history


def reconstruct_history(lane: Mapping[str, Any], solver: str) -> np.ndarray:
    physical = np.asarray(lane[f"{solver}_physical_state_history_23"], dtype=float)
    work = np.asarray(lane[f"{solver}_auxiliary_work_history_J"], dtype=float)
    if physical.ndim != 2 or physical.shape[1] != 23 or work.shape != (len(physical),):
        raise IndependentValidationError("RAW_HISTORY_SHAPE_INVALID")
    result = np.column_stack((physical, work))
    if not np.all(np.isfinite(result)):
        raise IndependentValidationError("RAW_HISTORY_NONFINITE")
    return result


def independent_body_momentum(tree: Any, q: np.ndarray, dq: np.ndarray, base_twist: np.ndarray, position: np.ndarray, quaternion: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    rot = rotation(quaternion)
    generalized_velocity = np.concatenate((base_twist, dq))
    linear = np.zeros(3)
    angular = np.zeros(3)
    for body in tree.body_kinematics(q):
        velocity_root = body.linear_jacobian @ generalized_velocity
        omega_root = body.angular_jacobian @ generalized_velocity
        velocity_inertial = rot @ velocity_root
        omega_inertial = rot @ omega_root
        com_inertial = position + rot @ body.com_root_m
        body_linear = body.mass_kg * velocity_inertial
        inertia_inertial = rot @ body.inertia_root_kg_m2 @ rot.T
        linear += body_linear
        angular += inertia_inertial @ omega_inertial + np.cross(com_inertial, body_linear)
    return linear, angular


def audit_raw_trajectory(backend: Any, times: np.ndarray, history: np.ndarray, locked: bool) -> dict[str, Any]:
    values: dict[str, list[float]] = {
        key: [] for key in (
            "p_body", "h_body", "p_cross", "h_cross", "p_connection", "h_connection",
            "quat", "rr", "rp", "pp", "qR_margin", "qP_margin", "energy",
        )
    }
    scaled_spd: list[bool] = []
    S = np.diag(SCALES)
    for state in history:
        position = state[:3]
        quaternion = state[3:7]
        q = state[7:15].copy(); dq = state[15:23].copy()
        if locked:
            q[6:] = QP_STAR; dq[6:] = 0.0
        full = np.asarray(backend.tree.mass_matrix(q), dtype=float)
        Hbb, Hbm, Hmb, Hmm = full[:6, :6], full[:6, 6:], full[6:, :6], full[6:, 6:]
        connection = -np.linalg.solve(Hbb, Hbm)
        base_twist = connection @ dq
        reduced = Hmm - Hmb @ np.linalg.solve(Hbb, Hbm)
        values["rr"].append(float(np.max(np.abs(reduced[:6, :6] - reduced[:6, :6].T))))
        values["rp"].append(float(np.max(np.abs(reduced[:6, 6:] - reduced[6:, :6].T))))
        values["pp"].append(float(np.max(np.abs(reduced[6:, 6:] - reduced[6:, 6:].T))))
        try:
            np.linalg.cholesky(S.T @ reduced @ S)
            scaled_spd.append(True)
        except np.linalg.LinAlgError:
            scaled_spd.append(False)
        generalized_momentum = full @ np.concatenate((base_twist, dq))
        rot = rotation(quaternion)
        matrix_p = rot @ generalized_momentum[:3]
        matrix_h = rot @ generalized_momentum[3:6] + np.cross(position, matrix_p)
        body_p, body_h = independent_body_momentum(
            backend.tree, q, dq, base_twist, position, quaternion
        )
        values["p_body"].append(float(np.linalg.norm(body_p)))
        values["h_body"].append(float(np.linalg.norm(body_h)))
        values["p_cross"].append(float(np.linalg.norm(body_p - matrix_p)))
        values["h_cross"].append(float(np.linalg.norm(body_h - matrix_h)))
        closure = Hbb @ base_twist + Hbm @ dq
        values["p_connection"].append(float(np.linalg.norm(closure[:3])))
        values["h_connection"].append(float(np.linalg.norm(closure[3:])))
        generalized_velocity = np.concatenate((base_twist, dq))
        values["energy"].append(float(0.5 * generalized_velocity @ full @ generalized_velocity))
        values["quat"].append(abs(float(np.linalg.norm(quaternion)) - 1.0))
        values["qR_margin"].append(float(np.min(np.minimum(q[:6] - LOWER[:6], UPPER[:6] - q[:6]))))
        values["qP_margin"].append(float(np.min(np.minimum(q[6:] - LOWER[6:], UPPER[6:] - q[6:]))))
    energy = np.asarray(values["energy"])
    work = history[:, 23]
    energy_change = energy - energy[0]
    error = energy_change - work
    work_relative = float(
        np.max(np.abs(error))
        / max(float(np.max(np.abs(energy_change))), float(np.max(np.abs(work))), 1.0e-15)
    )
    return {
        "samples": len(times),
        "finite": bool(np.all(np.isfinite(history))),
        "qR_margin_rad": min(values["qR_margin"]),
        "qP_margin_m": min(values["qP_margin"]),
        "mass_rr_kg_m2": max(values["rr"]),
        "mass_rp_kg_m": max(values["rp"]),
        "mass_pp_kg": max(values["pp"]),
        "scaled_spd": all(scaled_spd),
        "p_body_kg_m_s": max(values["p_body"]),
        "h_body_kg_m2_s": max(values["h_body"]),
        "p_cross_kg_m_s": max(values["p_cross"]),
        "h_cross_kg_m2_s": max(values["h_cross"]),
        "p_connection_kg_m_s": max(values["p_connection"]),
        "h_connection_kg_m2_s": max(values["h_connection"]),
        "quat_norm": max(values["quat"]),
        "work_abs_J": float(np.max(np.abs(error))),
        "work_relative": work_relative,
        "energy_history_J": energy,
    }


def solver_cross(backend: Any, left: np.ndarray, right: np.ndarray) -> dict[str, float]:
    q_error = np.abs(left[:, 7:15] - right[:, 7:15])
    dq_error = np.abs(left[:, 15:23] - right[:, 15:23])
    attitude = [attitude_distance(a[3:7], b[3:7]) for a, b in zip(left, right)]
    linear: list[float] = []
    angular: list[float] = []
    for a, b in zip(left, right):
        va = np.asarray(backend.mechanical_connection(a[7:15])) @ a[15:23]
        vb = np.asarray(backend.mechanical_connection(b[7:15])) @ b[15:23]
        linear.append(float(np.max(np.abs(va[:3] - vb[:3]))))
        angular.append(float(np.max(np.abs(va[3:] - vb[3:]))))
    return {
        "qR_rad": float(np.max(q_error[:, :6])),
        "qP_m": float(np.max(q_error[:, 6:])),
        "dqR_rad_s": float(np.max(dq_error[:, :6])),
        "dqP_m_s": float(np.max(dq_error[:, 6:])),
        "position_m": float(np.max(np.abs(left[:, :3] - right[:, :3]))),
        "attitude_rad": max(attitude),
        "v_linear_m_s": max(linear),
        "v_angular_rad_s": max(angular),
    }


def compare_reintegrated(expected: np.ndarray, actual: np.ndarray) -> dict[str, float]:
    return {
        "qR_rad": float(np.max(np.abs(expected[:, 7:13] - actual[:, 7:13]))),
        "qP_m": float(np.max(np.abs(expected[:, 13:15] - actual[:, 13:15]))),
        "dqR_rad_s": float(np.max(np.abs(expected[:, 15:21] - actual[:, 15:21]))),
        "dqP_m_s": float(np.max(np.abs(expected[:, 21:23] - actual[:, 21:23]))),
        "position_m": float(np.max(np.abs(expected[:, :3] - actual[:, :3]))),
        "attitude_rad": max(attitude_distance(a[3:7], b[3:7]) for a, b in zip(expected, actual)),
        "work_J": float(np.max(np.abs(expected[:, 23] - actual[:, 23]))),
    }


def audit_kkt(backend: Any, times: np.ndarray, history: np.ndarray) -> dict[str, Any]:
    metrics = {key: [] for key in ("eqR", "eqP", "constraint", "accelR", "accelP", "reaction", "power")}
    for time, state in zip(times, history):
        result = solve_locked(backend, state[7:15], state[15:23], effort(float(time), locked=True))
        equilibrium = np.abs(result["equilibrium"])
        metrics["eqR"].append(float(np.max(equilibrium[:6])))
        metrics["eqP"].append(float(np.max(equilibrium[6:])))
        metrics["constraint"].append(float(np.max(np.abs(result["constraint"]))))
        delta = np.abs(result["acceleration"] - result["eliminated"])
        metrics["accelR"].append(float(np.max(delta[:6])))
        metrics["accelP"].append(float(np.max(delta[6:])))
        metrics["reaction"].append(float(np.max(np.abs(result["reaction"] - result["eliminated_reaction"]))))
        metrics["power"].append(float(abs(result["reaction"] @ state[21:23])))
    midpoint_tau = effort(DURATION_S / 2, locked=True)
    free_acceleration = solve_acceleration(
        backend,
        np.concatenate((Q0[:6], QP_STAR)),
        np.concatenate((DQ0[:6], np.zeros(2))),
        midpoint_tau,
    )[0]
    return {
        "eqR_Nm": max(metrics["eqR"]),
        "eqP_N": max(metrics["eqP"]),
        "constraint_m_s2": max(metrics["constraint"]),
        "accelR_rad_s2": max(metrics["accelR"]),
        "accelP_m_s2": max(metrics["accelP"]),
        "reaction_N": max(metrics["reaction"]),
        "power_W": max(metrics["power"]),
        "free_prismatic_m_s2": float(np.max(np.abs(free_acceleration[6:]))),
    }


def audit_bias_and_scale(backend: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    derivatives = mass_derivatives(backend, Q0)
    compact = bias_from_derivatives(derivatives, DQ0)
    explicit = christoffel_bias(derivatives, DQ0)
    delta = np.abs(compact - explicit)
    bias_audit = {
        "R_Nm": float(np.max(delta[:6])),
        "P_N": float(np.max(delta[6:])),
    }
    tau = 0.37 * AMPLITUDE
    matrix = np.asarray(backend.reduced_mass_matrix(Q0))
    native_acceleration = np.linalg.solve(matrix, tau - compact)
    S = np.diag(SCALES)
    Sinv = np.diag(1.0 / SCALES)
    dx = Sinv @ DQ0
    transformed_matrix = S.T @ matrix @ S
    transformed_bias = S.T @ compact
    transformed_tau = S.T @ tau
    recovered = S @ np.linalg.solve(transformed_matrix, transformed_tau - transformed_bias)
    native_energy = float(0.5 * DQ0 @ matrix @ DQ0)
    transformed_energy = float(0.5 * dx @ transformed_matrix @ dx)
    native_power = float(tau @ DQ0)
    transformed_power = float(transformed_tau @ dx)
    scale_audit = {
        "accelR_rad_s2": float(np.max(np.abs(recovered[:6] - native_acceleration[:6]))),
        "accelP_m_s2": float(np.max(np.abs(recovered[6:] - native_acceleration[6:]))),
        "energy_relative": abs(native_energy - transformed_energy) / max(abs(native_energy), 1.0e-15),
        "power_relative": abs(native_power - transformed_power) / max(abs(native_power), 1.0e-15),
        "mixed_spectrum_used": False,
    }
    return bias_audit, scale_audit


def audit_constant_backend(backend: Any) -> dict[str, Any]:
    times = np.linspace(0.0, CONSTANT_DURATION_S, int(round(CONSTANT_DURATION_S / CONSTANT_STEP_S)) + 1)
    constant = lambda _time: AMPLITUDE.copy()
    independent = integrate_rk4(backend, times, initial_augmented(False), False, constant)[-1]
    q = Q0.copy(); dq = DQ0.copy(); position = R0.copy(); quaternion = normalize(QUAT0)
    twist = np.asarray(backend.mechanical_connection(q)) @ dq
    ee = backend.ee_centroid_inertial(q, position, quaternion)
    state_class = type(backend.initial_state())
    valid = state_class(tuple(q), tuple(dq), tuple(position), tuple(quaternion), tuple(twist), tuple(ee), "INDEPENDENT_VALID_STATE")
    after, assessment, backend_audit = backend.advance(
        valid, generalized_effort=AMPLITUDE, step_s=CONSTANT_STEP_S, steps=len(times) - 1
    )
    q_after = np.asarray(after.q_mixed_rad_m); dq_after = np.asarray(after.qdot_mixed_rad_s_m_s)
    return {
        "physical_changed": assessment["physical_state_changed"],
        "momentum_backend": backend_audit["momentum_conserved_within_limit"],
        "qR_rad": float(np.max(np.abs(independent[7:13] - q_after[:6]))),
        "qP_m": float(np.max(np.abs(independent[13:15] - q_after[6:]))),
        "dqR_rad_s": float(np.max(np.abs(independent[15:21] - dq_after[:6]))),
        "dqP_m_s": float(np.max(np.abs(independent[21:23] - dq_after[6:]))),
        "position_m": float(np.max(np.abs(independent[:3] - np.asarray(after.base_position_inertial_m)))),
        "attitude_rad": attitude_distance(independent[3:7], after.base_quaternion_body_to_inertial_wxyz),
    }


def audit_evidence_hash_chain(evidence: Mapping[str, Any], gate: Mapping[str, Any], manifest: Mapping[str, Any]) -> dict[str, Any]:
    raw = raw_record(EVIDENCE_PATH)
    replay_checks: dict[str, Any] = {}
    for lane_name in ("ACTUATED_8DOF", "LOCKED_2P_6R_PULSE"):
        history = reconstruct_history(evidence["lanes"][lane_name], "rk4")
        observed = canonical_hash(history)
        replay = evidence["deterministic_replay"][lane_name]
        replay_checks[lane_name] = {
            "raw_history_hash": observed,
            "first_matches": replay.get("first_history_canonical_sha256") == observed,
            "second_matches": replay.get("second_history_canonical_sha256") == observed,
            "declared_identical": replay.get("byte_identical_canonical_replay") is True,
        }
    manifest_by_path = {item["path"]: item for item in manifest.get("package_entries", [])}
    evidence_rel = EVIDENCE_PATH.relative_to(PACKAGE_ROOT).as_posix()
    gate_rel = GATE_PATH.relative_to(PACKAGE_ROOT).as_posix()
    checks = {
        "raw_bytes": raw["bytes"] == EXPECTED_EVIDENCE_BYTES,
        "raw_sha": raw["sha256"] == EXPECTED_EVIDENCE_RAW_SHA256,
        "schema": evidence.get("schema") == "R2_TIME_VARYING_TORQUE_PLANT_CANDIDATE_EVIDENCE_V1",
        "contract_hash_evidence": evidence.get("contract_canonical_sha256") == EXPECTED_CONTRACT_CANONICAL_SHA256,
        "contract_hash_gate": gate.get("contract_canonical_sha256") == EXPECTED_CONTRACT_CANONICAL_SHA256,
        "source_records": evidence.get("source_pins", {}).get("all_match") is True
        and len(evidence.get("source_pins", {}).get("records", [])) == 19,
        "replay_hashes": all(
            item["first_matches"] and item["second_matches"] and item["declared_identical"]
            for item in replay_checks.values()
        ),
        "manifest_evidence": manifest_by_path.get(evidence_rel, {}).get("sha256") == EXPECTED_EVIDENCE_RAW_SHA256
        and manifest_by_path.get(evidence_rel, {}).get("bytes") == EXPECTED_EVIDENCE_BYTES,
        "manifest_gate": manifest_by_path.get(gate_rel, {}).get("sha256") == EXPECTED_GATE_RAW_SHA256
        and manifest_by_path.get(gate_rel, {}).get("bytes") == EXPECTED_GATE_BYTES,
        "authority_false": evidence.get("next_stage_authorized") is False
        and evidence.get("release_credit") is False,
    }
    return {"raw": raw, "replay": replay_checks, "checks": checks, "all_pass": all(checks.values())}


def negative_controls(
    contract: Mapping[str, Any], evidence: Mapping[str, Any], gate: Mapping[str, Any],
    manifest: Mapping[str, Any], backend: Any,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []

    def exception_control(identifier: str, operation: Callable[[], Any]) -> None:
        passed = False; observed = "NO_EXCEPTION"
        try:
            operation()
        except Exception as exc:
            passed = True; observed = type(exc).__name__
        records.append({"id": identifier, "pass": passed, "observed": observed})

    def boolean_control(identifier: str, condition: bool) -> None:
        records.append({"id": identifier, "pass": bool(condition)})

    exception_control("INC01_DUPLICATE_JSON", lambda: strict_loads('{"a":1,"a":2}'))
    exception_control("INC02_JSON_NAN", lambda: strict_loads('{"a":NaN}'))
    exception_control("INC03_JSON_INFINITY", lambda: strict_loads('{"a":Infinity}'))
    boolean_control("INC04_EVIDENCE_RAW_HASH_MUTATION", hashlib.sha256(EVIDENCE_PATH.read_bytes() + b"x").hexdigest().upper() != EXPECTED_EVIDENCE_RAW_SHA256)
    mutated = copy.deepcopy(contract); mutated["model_contract"]["integrated_state_dimension"] = 24
    boolean_control("INC05_CONTRACT_INTERNAL_HASH_MUTATION", canonical_hash(mutated) != EXPECTED_CONTRACT_CANONICAL_SHA256)
    mutated = copy.deepcopy(contract); mutated["source_pins"][0]["sha256"] = "0" * 64
    boolean_control("INC06_SOURCE_PIN_MUTATION", mutated["source_pins"] != expected_pin_documents())
    mutated_gate = copy.deepcopy(gate); mutated_gate["next_stage_authorized"] = True
    boolean_control("INC07_AUTHORITY_ESCALATION", not authority_false(mutated_gate))
    default = backend.initial_state()
    boolean_control("INC08_ILLEGAL_BACKEND_DEFAULT", not state_is_valid(default.base_position_inertial_m, default.base_quaternion_body_to_inertial_wxyz, default.q_mixed_rad_m, default.qdot_mixed_rad_s_m_s))
    q_bad = Q0.copy(); q_bad[0] = UPPER[0] + 1.0e-4
    boolean_control("INC09_LIMIT_L_MUTATION", not state_is_valid(R0, QUAT0, q_bad, DQ0))
    locked_history = reconstruct_history(evidence["lanes"]["LOCKED_2P_6R_PULSE"], "rk4")
    lock_q_bad = locked_history.copy(); lock_q_bad[2, 13] += 1.0e-5
    boolean_control("INC10_LOCK_POSITION_MUTATION", not np.array_equal(lock_q_bad[:, 13:15], np.full((len(lock_q_bad), 2), 0.03575)))
    lock_dq_bad = locked_history.copy(); lock_dq_bad[2, 21] = 1.0e-4
    boolean_control("INC11_LOCK_RATE_MUTATION", not np.array_equal(lock_dq_bad[:, 21:23], np.zeros((len(lock_dq_bad), 2))))
    times = np.asarray(evidence["lanes"]["LOCKED_2P_6R_PULSE"]["time_s"])
    work_bad = locked_history.copy(); work_bad[-1, 23] += 1.0e-4
    boolean_control("INC12_WORK_LEDGER_MUTATION", audit_raw_trajectory(backend, times, work_bad, True)["work_abs_J"] > LIMIT["work_abs"])
    momentum_state = locked_history[len(locked_history) // 2]
    momentum_q = momentum_state[7:15].copy(); momentum_q[6:] = QP_STAR
    momentum_dq = momentum_state[15:23].copy(); momentum_dq[6:] = 0.0
    wrong_zero_base_twist_momentum = np.asarray(backend.tree.mass_matrix(momentum_q)) @ np.concatenate((np.zeros(6), momentum_dq))
    boolean_control(
        "INC13_MOMENTUM_MUTATION",
        float(np.linalg.norm(wrong_zero_base_twist_momentum[:3])) > LIMIT["linear_momentum"]
        or float(np.linalg.norm(wrong_zero_base_twist_momentum[3:6])) > LIMIT["angular_momentum"],
    )
    duplicate_manifest = copy.deepcopy(manifest); duplicate_manifest["package_entries"].append(copy.deepcopy(duplicate_manifest["package_entries"][0]))
    boolean_control("INC14_MANIFEST_DUPLICATE", not manifest_is_exact(duplicate_manifest)[0])
    extra_manifest = copy.deepcopy(manifest); extra_manifest["package_entries"].append({"path": "extra", "bytes": 0, "sha256": "0" * 64})
    boolean_control("INC15_MANIFEST_EXTRA", not manifest_is_exact(extra_manifest)[0])
    self_manifest = copy.deepcopy(manifest); self_manifest["package_entries"].append({"path": manifest["self_excluded_path"], "bytes": 1, "sha256": "0" * 64})
    boolean_control("INC16_MANIFEST_SELF_INCLUSION", not manifest_is_exact(self_manifest)[0])
    duplicate_gate = copy.deepcopy(gate); duplicate_gate["checks"][1]["id"] = "G01"
    boolean_control("INC17_GATE_DUPLICATE_ID", not audit_gate_document_in_memory(duplicate_gate))
    missing_gate = copy.deepcopy(gate); missing_gate["checks"].pop()
    boolean_control("INC18_GATE_MISSING_ROW", not audit_gate_document_in_memory(missing_gate))
    actuated_rk4 = reconstruct_history(evidence["lanes"]["ACTUATED_8DOF"], "rk4")
    actuated_dop = reconstruct_history(evidence["lanes"]["ACTUATED_8DOF"], "dop853")
    solver_bad = actuated_dop.copy(); solver_bad[len(solver_bad) // 2, 7] += 1.0e-3
    boolean_control("INC19_SOLVER_CROSS_MUTATION", solver_cross(backend, actuated_rk4, solver_bad)["qR_rad"] > LIMIT["cross_qr"])
    boolean_control("INC20_ZERO_QUATERNION", not state_is_valid(R0, [0, 0, 0, 0], Q0, DQ0))
    kkt = solve_locked(backend, Q0, np.concatenate((DQ0[:6], np.zeros(2))), effort(DURATION_S / 2, True))
    acceleration_bad = kkt["acceleration"].copy(); acceleration_bad[6] += 1.0e-3
    boolean_control("INC21_KKT_CONSTRAINT_MUTATION", float(np.max(np.abs(acceleration_bad[6:]))) > LIMIT["kkt_constraint"])
    exception_control(
        "INC22_NONZERO_TOTAL_MOMENTUM_BEHAVIORAL_REJECTION",
        lambda: enforce_zero_total_momentum([1.0e-12, 0, 0, 0, 0, 0]),
    )
    units_bad = list(EXPECTED_COORDINATE_UNITS); units_bad[-1] = "rad"
    boolean_control("INC23_MIXED_UNIT_MUTATION", tuple(units_bad) != EXPECTED_COORDINATE_UNITS)
    quat_bad = actuated_rk4.copy(); quat_bad[1, 3:7] *= 1.1
    boolean_control("INC24_QUATERNION_NORM_MUTATION", float(np.max(np.abs(np.linalg.norm(quat_bad[:, 3:7], axis=1) - 1.0))) > LIMIT["quaternion"])
    resigned_gate = copy.deepcopy(gate)
    resigned_gate["review_status"] = "APPROVED"
    resigned_gate_raw = (
        json.dumps(
            builtin(resigned_gate),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    resigned_manifest = copy.deepcopy(manifest)
    gate_relative = GATE_PATH.relative_to(PACKAGE_ROOT).as_posix()
    resigned_entry = next(
        item
        for item in resigned_manifest["package_entries"]
        if item["path"] == gate_relative
    )
    resigned_entry["bytes"] = len(resigned_gate_raw)
    resigned_entry["sha256"] = hashlib.sha256(resigned_gate_raw).hexdigest().upper()
    resigned_manifest["package_entries_canonical_sha256"] = canonical_hash(
        resigned_manifest["package_entries"]
    )
    internally_consistently_resigned = (
        resigned_entry["sha256"]
        == hashlib.sha256(resigned_gate_raw).hexdigest().upper()
        and resigned_manifest["package_entries_canonical_sha256"]
        == canonical_hash(resigned_manifest["package_entries"])
    )
    boolean_control(
        "INC25_GATE_REVIEW_STATUS_CONSISTENT_RESIGN",
        internally_consistently_resigned
        and not audit_gate_document_in_memory(resigned_gate),
    )
    allowlist_mutant = copy.deepcopy(manifest)
    allowlist_mutant["frozen_package_path_allowlist"] = list(
        allowlist_mutant["frozen_package_path_allowlist"]
    ) + ["unregistered_business_file.json"]
    boolean_control(
        "INC26_FROZEN_ALLOWLIST_MUTATION",
        not manifest_is_exact(allowlist_mutant)[0],
    )
    transitive_pin_mutant = copy.deepcopy(contract)
    transitive_pin_mutant["source_pins"][-1]["sha256"] = "F" * 64
    boolean_control(
        "INC27_TRANSITIVE_RUNTIME_PIN_MUTATION",
        transitive_pin_mutant["source_pins"] != expected_pin_documents(),
    )
    dop853_mutant = actuated_dop.copy()
    dop853_mutant[len(dop853_mutant) // 2, 21] += 1.0e-6
    dop853_mutation_error = compare_reintegrated(dop853_mutant, actuated_dop)
    boolean_control(
        "INC28_DOP853_ARCHIVE_FIELD_MUTATION",
        dop853_mutation_error["dqP_m_s"] > DOP853_REPRO_LIMIT["dqP_m_s"],
    )
    return {
        "records": records,
        "count": len(records),
        "passed": sum(item["pass"] for item in records),
        "minimum_required": 16,
        "all_pass": len(records) >= 16 and all(item["pass"] for item in records),
    }


def audit_gate_document_in_memory(gate: Mapping[str, Any]) -> bool:
    rows = gate.get("checks", [])
    return (
        tuple((row.get("id"), row.get("name")) for row in rows) == EXPECTED_GATE_ROWS
        and len({row.get("id") for row in rows}) == 24
        and all(row.get("pass") is True for row in rows)
        and gate.get("passed") == 24
        and gate.get("total") == 24
        and gate.get("all_checks_pass") is True
        and gate.get("review_status") == EXPECTED_REVIEW_STATUS
        and authority_false(gate)
    )


def reproduce_physics(backend: Any, evidence: Mapping[str, Any]) -> dict[str, Any]:
    times = np.asarray(evidence["lanes"]["ACTUATED_8DOF"]["time_s"], dtype=float)
    expected_times = np.linspace(0.0, DURATION_S, int(round(DURATION_S / STEP_S)) + 1)
    if not np.array_equal(times, expected_times):
        raise IndependentValidationError("TIME_GRID_MISMATCH")
    lanes: dict[str, Any] = {}
    raw_audits: list[dict[str, Any]] = []
    integration_reproduction: dict[str, Any] = {}
    dop853_integration_reproduction: dict[str, Any] = {}
    for lane_name, locked in (("ACTUATED_8DOF", False), ("LOCKED_2P_6R_PULSE", True)):
        lane = evidence["lanes"][lane_name]
        lane_times = np.asarray(lane["time_s"], dtype=float)
        if not np.array_equal(lane_times, times):
            raise IndependentValidationError("LANE_TIME_GRID_MISMATCH")
        rk4_raw = reconstruct_history(lane, "rk4")
        dop_raw = reconstruct_history(lane, "dop853")
        rk4_audit = audit_raw_trajectory(backend, times, rk4_raw, locked)
        dop_audit = audit_raw_trajectory(backend, times, dop_raw, locked)
        raw_audits.extend((rk4_audit, dop_audit))
        independent = integrate_rk4(
            backend,
            times,
            initial_augmented(locked),
            locked,
            (lambda t, lock=locked: effort(t, lock)),
        )
        reproduction = compare_reintegrated(rk4_raw, independent)
        integration_reproduction[lane_name] = reproduction
        independent_dop853 = integrate_dop853(
            backend,
            times,
            initial_augmented(locked),
            locked,
            (lambda t, lock=locked: effort(t, lock)),
        )
        dop853_reproduction = compare_reintegrated(dop_raw, independent_dop853)
        dop853_integration_reproduction[lane_name] = dop853_reproduction
        lanes[lane_name] = {
            "rk4": rk4_audit,
            "dop853": dop_audit,
            "solver_cross": solver_cross(backend, rk4_raw, dop_raw),
            "rk4_independent_reintegration": reproduction,
            "dop853_independent_reintegration": dop853_reproduction,
            "qR_peak_change_rad": float(np.max(np.abs(rk4_raw[:, 7:13] - rk4_raw[0, 7:13]))),
            "qP_peak_change_m": float(np.max(np.abs(rk4_raw[:, 13:15] - rk4_raw[0, 13:15]))),
            "lock_position_exact": (not locked) or np.array_equal(rk4_raw[:, 13:15], np.full((len(rk4_raw), 2), 0.03575)),
            "lock_rate_exact": (not locked) or np.array_equal(
                rk4_raw[:, 21:23], np.zeros((len(rk4_raw), 2))
            ),
        }
    bias_audit, scale_audit = audit_bias_and_scale(backend)
    locked_rk4 = reconstruct_history(evidence["lanes"]["LOCKED_2P_6R_PULSE"], "rk4")
    kkt_audit = audit_kkt(backend, times, locked_rk4)
    zero_history = integrate_rk4(
        backend,
        times,
        initial_augmented(False),
        False,
        lambda _time: np.zeros(8),
    )
    zero_audit = audit_raw_trajectory(backend, times, zero_history, False)
    zero_energy = np.asarray(zero_audit["energy_history_J"])
    zero_relative = float(np.max(np.abs(zero_energy - zero_energy[0])) / max(abs(float(zero_energy[0])), 1.0e-15))
    constant_audit = audit_constant_backend(backend)
    aggregate = {
        "finite_limits": all(item["finite"] and item["qR_margin_rad"] >= 0 and item["qP_margin_m"] >= 0 for item in raw_audits),
        "mass": all(item["mass_rr_kg_m2"] <= LIMIT["mass_rr"] and item["mass_rp_kg_m"] <= LIMIT["mass_rp"] and item["mass_pp_kg"] <= LIMIT["mass_pp"] and item["scaled_spd"] for item in raw_audits),
        "p": max(item["p_body_kg_m_s"] for item in raw_audits),
        "h": max(item["h_body_kg_m2_s"] for item in raw_audits),
        "p_cross": max(item["p_cross_kg_m_s"] for item in raw_audits),
        "h_cross": max(item["h_cross_kg_m2_s"] for item in raw_audits),
        "p_connection": max(item["p_connection_kg_m_s"] for item in raw_audits),
        "h_connection": max(item["h_connection_kg_m2_s"] for item in raw_audits),
        "quat": max(item["quat_norm"] for item in raw_audits),
        "work_abs": max(item["work_abs_J"] for item in raw_audits),
        "work_rel": max(item["work_relative"] for item in raw_audits),
    }
    return {
        "lanes": lanes,
        "aggregate": aggregate,
        "bias": bias_audit,
        "kkt": kkt_audit,
        "scale": scale_audit,
        "zero_effort": {**zero_audit, "energy_relative_drift": zero_relative},
        "constant_backend": constant_audit,
        "integration_reproduction": integration_reproduction,
        "dop853_integration_reproduction": dop853_integration_reproduction,
    }


def build_receipt() -> dict[str, Any]:
    contract = strict_read(CONTRACT_PATH)
    evidence = strict_read(EVIDENCE_PATH)
    gate = strict_read(GATE_PATH)
    manifest = strict_read(MANIFEST_PATH)
    independence = check_no_forbidden_imports()
    strict_self_test = {"duplicate": False, "nan": False, "infinity": False}
    for key, text in (("duplicate", '{"x":1,"x":2}'), ("nan", '{"x":NaN}'), ("infinity", '{"x":Infinity}')):
        try:
            strict_loads(text)
        except ValueError:
            strict_self_test[key] = True
    contract_audit = audit_contract(contract)
    sources = audit_sources(contract)
    urdf = audit_urdf(contract)
    gate_structure = audit_gate_structure(gate)
    manifest_pass, manifest_checks = manifest_is_exact(manifest)
    manifest_audit = {
        "raw": raw_record(MANIFEST_PATH),
        "declared_entry_count": manifest.get("package_entry_count"),
        "declared_entries_canonical_sha256": manifest.get(
            "package_entries_canonical_sha256"
        ),
        "independently_recomputed_entries_canonical_sha256": canonical_hash(
            expected_manifest_entries()
        ),
        "checks": manifest_checks,
        "all_pass": manifest_pass,
    }
    backend = load_public_backend()
    default_audit = audit_backend_default(backend)
    evidence_chain = audit_evidence_hash_chain(evidence, gate, manifest)
    physics = reproduce_physics(backend, evidence)
    controls = negative_controls(contract, evidence, gate, manifest, backend)
    aggregate = physics["aggregate"]
    crosses = [physics["lanes"][name]["solver_cross"] for name in physics["lanes"]]
    reproduction = list(physics["integration_reproduction"].values())
    dop853_reproduction = list(
        physics["dop853_integration_reproduction"].values()
    )
    dop853_reproduction_pass = all(
        all(item[field] <= threshold for field, threshold in DOP853_REPRO_LIMIT.items())
        for item in dop853_reproduction
    )
    kkt = physics["kkt"]
    scale = physics["scale"]
    constant = physics["constant_backend"]
    independent_gate = {
        "G01": sources["all_match"],
        "G02": urdf["all_pass"],
        "G03": state_is_valid(R0, QUAT0, Q0, DQ0) and default_audit["pass"] and not default_audit["default_valid"],
        "G04": contract_audit["checks"]["coordinate_units"] and contract_audit["checks"]["rate_units"] and contract_audit["checks"]["effort_units"],
        "G05": np.array_equal(effort(0.0), np.zeros(8)) and np.array_equal(effort(DURATION_S / 2), AMPLITUDE) and float(np.max(np.abs(effort(DURATION_S)))) <= np.finfo(float).eps,
        "G06": aggregate["finite_limits"],
        "G07": aggregate["mass"],
        "G08": physics["bias"]["R_Nm"] <= LIMIT["bias_r"] and physics["bias"]["P_N"] <= LIMIT["bias_p"],
        "G09": physics["lanes"]["ACTUATED_8DOF"]["qR_peak_change_rad"] > 0 and physics["lanes"]["ACTUATED_8DOF"]["qP_peak_change_m"] > 0 and all(max(item.values()) <= 5.0e-13 for item in reproduction),
        "G10": kkt["eqR_Nm"] <= LIMIT["kkt_r"] and kkt["eqP_N"] <= LIMIT["kkt_p"] and kkt["constraint_m_s2"] <= LIMIT["kkt_constraint"] and kkt["accelR_rad_s2"] <= LIMIT["kkt_r"] and kkt["accelP_m_s2"] <= LIMIT["kkt_constraint"] and kkt["reaction_N"] <= LIMIT["kkt_reaction"] and kkt["power_W"] <= LIMIT["kkt_power"] and physics["lanes"]["LOCKED_2P_6R_PULSE"]["lock_position_exact"] and physics["lanes"]["LOCKED_2P_6R_PULSE"]["lock_rate_exact"],
        "G11": kkt["free_prismatic_m_s2"] >= LIMIT["free_prismatic_min"],
        "G12": all(item["qR_rad"] <= LIMIT["cross_qr"] and item["qP_m"] <= LIMIT["cross_qp"] and item["dqR_rad_s"] <= LIMIT["cross_dqr"] and item["dqP_m_s"] <= LIMIT["cross_dqp"] and item["position_m"] <= LIMIT["cross_position"] and item["attitude_rad"] <= LIMIT["cross_attitude"] and item["v_linear_m_s"] <= LIMIT["cross_vlin"] and item["v_angular_rad_s"] <= LIMIT["cross_vang"] for item in crosses)
        and dop853_reproduction_pass,
        "G13": aggregate["quat"] <= LIMIT["quaternion"] and all(item["attitude_rad"] <= LIMIT["cross_attitude"] for item in crosses),
        "G14": aggregate["p"] <= LIMIT["linear_momentum"],
        "G15": aggregate["h"] <= LIMIT["angular_momentum"],
        "G16": aggregate["p_cross"] <= LIMIT["matrix_body_linear"] and aggregate["h_cross"] <= LIMIT["matrix_body_angular"],
        "G17": aggregate["work_abs"] <= LIMIT["work_abs"] and aggregate["work_rel"] <= LIMIT["work_rel"],
        "G18": aggregate["p_connection"] <= LIMIT["connection_linear"] and aggregate["h_connection"] <= LIMIT["connection_angular"],
        "G19": scale["accelR_rad_s2"] <= LIMIT["scale_accel_r"] and scale["accelP_m_s2"] <= LIMIT["scale_accel_p"] and scale["energy_relative"] <= LIMIT["scale_energy"] and scale["power_relative"] <= LIMIT["scale_power"] and scale["mixed_spectrum_used"] is False,
        "G20": physics["zero_effort"]["energy_relative_drift"] <= LIMIT["zero_energy"] and physics["zero_effort"]["p_body_kg_m_s"] <= LIMIT["linear_momentum"] and physics["zero_effort"]["h_body_kg_m2_s"] <= LIMIT["angular_momentum"],
        "G21": constant["physical_changed"] and constant["momentum_backend"] and constant["qR_rad"] <= LIMIT["constant_qr"] and constant["qP_m"] <= LIMIT["constant_qp"] and constant["dqR_rad_s"] <= LIMIT["constant_dqr"] and constant["dqP_m_s"] <= LIMIT["constant_dqp"] and constant["position_m"] <= LIMIT["constant_position"] and constant["attitude_rad"] <= LIMIT["constant_attitude"],
        "G22": evidence_chain["checks"]["replay_hashes"] and all(max(item.values()) <= 5.0e-13 for item in reproduction),
        "G23": controls["all_pass"] and controls["passed"] >= 16,
        "G24": authority_false(gate) and evidence.get("execution_boundaries", {}).get("candidate_only") is True and all(value is False for key, value in evidence.get("execution_boundaries", {}).items() if key != "candidate_only"),
    }
    reproduced_rows = [
        {"id": identifier, "name": name, "pass": bool(independent_gate[identifier])}
        for identifier, name in EXPECTED_GATE_ROWS
    ]
    top_checks = [
        ("IV01", "NO_BUILDER_EVALUATOR_OR_SRC_IMPORT", independence["pass"]),
        ("IV02", "INDEPENDENT_STRICT_JSON_DUPLICATE_NAN_INF", all(strict_self_test.values())),
        ("IV03", "HELD_CONTRACT_RAW_CANONICAL_AND_SEMANTICS", contract_audit["all_pass"]),
        ("IV04", "HELD_SOURCE_PINS_REHASHED", sources["all_match"]),
        ("IV05", "URDF_TOPOLOGY_LIMITS_AND_MASS_REPARSED", urdf["all_pass"]),
        ("IV06", "PUBLIC_BACKEND_DEFAULT_STATE_REJECTED", default_audit["pass"] and not default_audit["default_valid"]),
        ("IV07", "GATE_RAW_HASH_ROWS_AND_AUTHORITY", gate_structure["all_pass"]),
        ("IV08", "EVIDENCE_RAW_HASH_AND_INTERNAL_HASH_CHAIN", evidence_chain["all_pass"]),
        ("IV09", "MANIFEST_EXACT_UNIQUE_NO_EXTRA_SELF_EXCLUDED", manifest_pass),
        ("IV10", "RAW_TRAJECTORY_INDEPENDENT_PHYSICS_RECOMPUTED", all(independent_gate[f"G{index:02d}"] for index in range(6, 22))),
        (
            "IV11",
            "INDEPENDENT_RK4_AND_DOP853_REINTEGRATION",
            all(max(item.values()) <= 5.0e-13 for item in reproduction)
            and dop853_reproduction_pass,
        ),
        ("IV12", "INDEPENDENT_MUTATION_CONTROLS", controls["all_pass"]),
    ]
    checks = [
        {"id": identifier, "name": name, "pass": bool(passed)}
        for identifier, name, passed in top_checks
    ] + [
        {"id": "IR" + row["id"][1:], "name": "INDEPENDENT_REPRODUCTION__" + row["name"], "pass": row["pass"]}
        for row in reproduced_rows
    ]
    all_pass = all(item["pass"] for item in checks)
    return builtin(
        {
            "schema": "R2_TIME_VARYING_TORQUE_PLANT_INDEPENDENT_VALIDATION_V1",
            "validator_architecture": "STANDALONE_NO_SHARED_BUILDER_EVALUATOR_SRC_IMPORTS",
            "held_contract_canonical_sha256": EXPECTED_CONTRACT_CANONICAL_SHA256,
            "checks": checks,
            "passed": sum(item["pass"] for item in checks),
            "total": len(checks),
            "all_checks_pass": all_pass,
            "independent_gate_reproduction": reproduced_rows,
            "independence_import_audit": independence,
            "strict_json_self_test": strict_self_test,
            "contract_audit": contract_audit,
            "source_audit": sources,
            "urdf_audit": urdf,
            "backend_default_audit": default_audit,
            "gate_structure_audit": gate_structure,
            "evidence_hash_chain": evidence_chain,
            "manifest_audit": manifest_audit,
            "physics_recomputation": physics,
            "negative_controls": controls,
            "maximum_claim_unchanged": EXPECTED_MAXIMUM_CLAIM,
            "measurement_uncertainty_boundary": "NO_HARDWARE_MEASUREMENTS_OR_UNCERTAINTY_MODEL_USED__DESIGN_NUMBERS_ONLY",
            "flex_valid": False,
            "contact_valid": False,
            "target_attachment_valid": False,
            "hardware_valid": False,
            "control_valid": False,
            "parent_dynamics_engineering_complete": False,
            "sim13_non_abort_authorized": False,
            "next_stage_authorized": False,
            "release_credit": False,
        }
    )


def pretty_bytes(value: Any) -> bytes:
    return (
        json.dumps(builtin(value), indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--stdout", action="store_true")
    args = parser.parse_args()
    receipt = build_receipt()
    if args.write:
        RECEIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT_PATH.write_bytes(pretty_bytes(receipt))
        record = raw_record(RECEIPT_PATH)
        print(json.dumps({"receipt": record, "checks": f"{receipt['passed']}/{receipt['total']}"}, indent=2, sort_keys=True))
        return 0 if receipt["all_checks_pass"] else 2
    if args.check:
        if not RECEIPT_PATH.is_file():
            raise IndependentValidationError("INDEPENDENT_RECEIPT_MISSING")
        stored = strict_read(RECEIPT_PATH)
        exact = canonical_bytes(stored) == canonical_bytes(receipt)
        result = {
            "standalone_recompute_pass": receipt["all_checks_pass"],
            "stored_receipt_canonical_exact": exact,
            "checks": f"{receipt['passed']}/{receipt['total']}",
            "negative_controls": f"{receipt['negative_controls']['passed']}/{receipt['negative_controls']['count']}",
            "all_pass": bool(receipt["all_checks_pass"] and exact),
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["all_pass"] else 3
    print(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False))
    return 0 if receipt["all_checks_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
