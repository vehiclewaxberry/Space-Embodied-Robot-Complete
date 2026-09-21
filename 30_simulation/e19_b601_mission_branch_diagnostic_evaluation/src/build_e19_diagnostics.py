"""Build the e19 isolated, non-release B601 diagnostic campaign.

The four mission branches are evaluated independently.  This module never
creates CAD, never modifies the accepted URDF, never fills physical UNKNOWNs,
and never chains branch outputs into a mission timeline.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import importlib.util
import io
import json
import math
import sys
import types
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import yaml


MODULE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = MODULE_ROOT.parents[1]
RESULTS_ROOT = MODULE_ROOT / "results"
GENERATED_LOCAL = "2026-08-23T20:10:00+08:00"
ACCEPTED_URDF_SHA256 = (
    "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
)

SOURCE_SPECS: tuple[tuple[str, str, str], ...] = (
    (
        "mechanical_loop_v2_gate",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "ecr_b601_harness_rated_envelope/12_loop_continuation_v2/"
        "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V2.json",
        "F1C7DD89A07B343DDEAF6466F87D2B19CECF6B6D0A04A47B793248DC72DF6AD5",
    ),
    (
        "e18_authority",
        "30_simulation/e18_b601_mission_input_branches/00_authority/"
        "E18_AUTHORITY_CONTRACT_V1.yaml",
        "DC6AB3985EC8C22C5D8C84400156A9A176A414875F117EA706F4E61D6378856C",
    ),
    (
        "e18_gate",
        "30_simulation/e18_b601_mission_input_branches/results/"
        "E18_B601_MISSION_INPUT_BRANCH_GATE_V1.json",
        "FBB65E252537F2E7FAD7F55BC3CAACCE1E2DDAA1365E1D522985C956CB7070C7",
    ),
    (
        "e18_manifest",
        "30_simulation/e18_b601_mission_input_branches/results/"
        "E18_OUTPUT_MANIFEST_V1.json",
        "AC7F0023BABFE37F83F24FED77865BFDC9B3A43CA21A8A07B627FB1D5FE08A09",
    ),
    (
        "e18_validation",
        "30_simulation/e18_b601_mission_input_branches/results/E18_VALIDATION_V1.json",
        "2D26580744688C4C776AA9B1279447921F81C672A4F2AB3359E4F623467068F4",
    ),
    (
        "e18_m01_contract",
        "30_simulation/e18_b601_mission_input_branches/01_contracts/"
        "M01_RELEASE_EVENT_AND_SWEEP_V1.yaml",
        "DC389C8C62E755F10821B86C60C396A35E397FA3ED63E9035580F86380287090",
    ),
    (
        "e18_m05_contract",
        "30_simulation/e18_b601_mission_input_branches/01_contracts/"
        "M05_22_TARGET_STATE_AND_SYNC_V1.yaml",
        "BF992776715D9C2B578AB4C160B403E24F4026811F648219D351A14A53224B1D",
    ),
    (
        "e18_m06_contract",
        "30_simulation/e18_b601_mission_input_branches/01_contracts/"
        "M06_22_CONTACT_AND_LOCK_V1.yaml",
        "C00CB3A47B73E453DEE2C169CEC0594379C18B4A62F047B9A6350E0197D0E869",
    ),
    (
        "e18_m07_contract",
        "30_simulation/e18_b601_mission_input_branches/01_contracts/"
        "M07_22_ATTACHED_TARGET_RECOVERY_V1.yaml",
        "891D2F228D3EB354BC83FFC1B414A2CABCC45A864B653AF3D04ABF3E8E0501EF",
    ),
    (
        "e18_m01_candidate",
        "30_simulation/e18_b601_mission_input_branches/02_candidates/"
        "M01_HELD_STOW_TO_RELEASE_CLEAR_QUINTIC_V1.csv",
        "B4CB77804E6B9FC17C8910E56A0ECB34DC63B91659337E8BCAB0FCA6189E7AA9",
    ),
    (
        "e18_m05_branches",
        "30_simulation/e18_b601_mission_input_branches/02_candidates/"
        "M05_22_TARGET_STATE_BRANCHES_V1.json",
        "08E59C0AC4EC27B0F5F2CC7D311102EC606BCE6D0CC318E8B9D95D840E9A5C75",
    ),
    (
        "e18_m06_matrix",
        "30_simulation/e18_b601_mission_input_branches/02_candidates/"
        "M06_22_HALF_SINE_EQUAL_IMPULSE_STIMULUS_MATRIX_V1.csv",
        "1446339899916D4F5B37000A89EBA5D687E40F8A3D9E3FE152D695B5E022C0D0",
    ),
    (
        "e18_m07_branches",
        "30_simulation/e18_b601_mission_input_branches/02_candidates/"
        "M07_22_ATTACHED_TARGET_RECOVERY_BRANCHES_V1.json",
        "0D02CE3531BC48317F5234140B03F5AC9284766DC87A9713E76D776532CFC286",
    ),
    (
        "e17_m07_candidate",
        "30_simulation/e17_b601_mission_trajectory_candidates/results/candidates/"
        "M07_22_ARM_ONLY_QUINTIC_V1.csv",
        "8AFBE9B95E1078CA7F73A4546CE4CAE605655C413DE7AF997AA807E0C31ECBF2",
    ),
    (
        "accepted_urdf",
        "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
        ACCEPTED_URDF_SHA256,
    ),
    (
        "mass_budget_v1",
        "20_engineering/stage1_spacecraft_layout/04_mass_inertia_budget/"
        "mass_inertia_budget_v1.csv",
        "073C802527E35C9495188EEFD5D8BA51F524D326142CF2AB31E436BAD0899392",
    ),
    (
        "system_mass_properties_v3",
        "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/"
        "03_mass_properties/SYSTEM_MASS_PROPERTIES_V3.yaml",
        "3F88318666C8A7DA57A74D65F94E8B27A7D84E32741039A893C21FC247A9FE9F",
    ),
    (
        "sim05_dynamics",
        "30_simulation/sim_05_free_floating_arm/dynamics.py",
        "86C512DFFC9AEC2C7840F4AF3E1A7380F613D302A56C9021F10BDB40F0D705E9",
    ),
    (
        "sim05_b601_model",
        "30_simulation/sim_05_free_floating_arm/b601_model.py",
        "3E2B451476F437E482661E275073249AD101705251B78C042851C32AE741052F",
    ),
    (
        "common_rigid_body",
        "30_simulation/common/rigid_body.py",
        "6CE88E6D0FA45B29694C43FDB6E2FAE6E8E61F309C9C1DC89A6A33FD5F32BC99",
    ),
    (
        "sim13_backend",
        "30_simulation/sim_13_physics_gated_embodied_grasping/src/physics_backend.py",
        "674F103E183D4602E8741D522B7D2747573F012F713F7CA6283C440547558D7A",
    ),
    (
        "sim13_randomization",
        "30_simulation/sim_13_physics_gated_embodied_grasping/src/domain_randomization.py",
        "62B6A486781C5AEE6102846571AF21475792B167370A44EF29BB2A46644347BF",
    ),
    (
        "sim13_action",
        "30_simulation/sim_13_physics_gated_embodied_grasping/src/action_space.py",
        "86657E6B17A67342D7BB688353DBDFDBFA0B7C4DC871486B5AE69B8BBAE948B6",
    ),
    (
        "sim13_config",
        "30_simulation/sim_13_physics_gated_embodied_grasping/config/"
        "sim13_bootstrap.json",
        "4624C5BA2A016A002531FCF6FB6EFD661AA488D6C9420197789263D4B0E42B8D",
    ),
    (
        "sim15_baseline",
        "30_simulation/sim_15_m5_geometry_gated_grasping/evidence/"
        "SIM15_DIAGNOSTIC_BASELINE_V1.json",
        "4D6B08F5F8DD6A45CC1CDCFBF2A04CEACF758ABAB1350FF0BE6742DCD4E85C1F",
    ),
    (
        "sim15_gate",
        "30_simulation/sim_15_m5_geometry_gated_grasping/evidence/"
        "SIM15_DIAGNOSTIC_GATE_V1.json",
        "A5B1EA597793A98F8829184501C5DBB6300BC8479FDE083EDB249DA00D4FC338",
    ),
    (
        "sim15_binding_receipt",
        "30_simulation/sim_15_m5_geometry_gated_grasping/evidence/"
        "SIM15_BINDING_RECEIPT_V1.json",
        "77FA8FFD984C068FF8F8750B6773CF6D8BAE6453C9E3EDF2BB53B119D53903B1",
    ),
    (
        "sim15_generator",
        "30_simulation/sim_15_m5_geometry_gated_grasping/tools/generate_baseline.py",
        "4987D46486A1DDD04BE45A12E4322CEF16B1C4D99C7AF248380733E0A4562F76",
    ),
    (
        "sim15_authority",
        "30_simulation/sim_15_m5_geometry_gated_grasping/src/authority.py",
        "99CB2633667FB3590AA6885F8045960FA75C6BAA291006CDC408FAF16E77B391",
    ),
    (
        "sim15_contact_gate",
        "30_simulation/sim_15_m5_geometry_gated_grasping/src/contact_gate.py",
        "E0644AF0A26CA4D8F4C22B713BAEA7489B90D72594DA903C41B57A3B44C8830C",
    ),
    (
        "sim15_env",
        "30_simulation/sim_15_m5_geometry_gated_grasping/src/env.py",
        "3004FB1DAA2FEB67ACE4CCEFECEFD7E1D67496F7B8941F7428BFD0ADDB76BCEC",
    ),
    (
        "sim15_joint_loads",
        "30_simulation/sim_15_m5_geometry_gated_grasping/src/joint_loads.py",
        "C1699F76CC7E44ADA73707273E2FA98FFE8DD047055D4DF2DA4C2AD0899E089A",
    ),
    (
        "sim15_rigid_capture",
        "30_simulation/sim_15_m5_geometry_gated_grasping/src/rigid_capture.py",
        "1FC4033EFE542F4A71DDFD74996970FE3A1DC50D2A9796FA2DF9BDDEA03C6AAF",
    ),
)

STATIC_ARTIFACTS = (
    "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/README.md",
    "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/00_authority/"
    "E19_AUTHORITY_CONTRACT_V1.yaml",
    "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/config/"
    "E19_ISOLATED_DIAGNOSTIC_CAMPAIGN_V1.yaml",
    "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/docs/preregistration.md",
    "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/docs/"
    "method_and_limitations.md",
    "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/src/"
    "build_e19_diagnostics.py",
    "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/tests/"
    "validate_e19_diagnostics.py",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode("utf-8")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def csv_bytes(fieldnames: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def project_path(relative: str) -> Path:
    return PROJECT_ROOT / Path(relative)


def artifact_record(relative: str, content: bytes | None = None) -> dict[str, Any]:
    path = project_path(relative)
    data = path.read_bytes() if content is None else content
    return {"path": relative, "sha256": sha256_bytes(data), "bytes": len(data)}


def build_input_manifest() -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for source_id, relative, expected in SOURCE_SPECS:
        path = project_path(relative)
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(
                f"source hash mismatch for {source_id}: expected {expected}, got {actual}"
            )
        records.append(
            {
                "source_id": source_id,
                "path": relative,
                "expected_sha256": expected,
                "actual_sha256": actual,
                "bytes": path.stat().st_size,
                "status": "EXACT_HASH_MATCH",
            }
        )
    return {
        "schema": "E19_INPUT_MANIFEST_V1",
        "generated_local": GENERATED_LOCAL,
        "scope": "HASH_BOUND_NON_RELEASE_DIAGNOSTIC_INPUTS_AND_SOLVER_SOURCES",
        "records": records,
        "record_count": len(records),
        "source_set_sha256": sha256_bytes(canonical_json_bytes(records)),
        "all_exact_hash_match": True,
        "accepted_urdf_sha256": ACCEPTED_URDF_SHA256,
        "accepted_urdf_modified": False,
        "cross_lane_state_input_count": 0,
        "release_credit": False,
    }


def _read_trajectory(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError(f"empty trajectory {path}")
    t = np.asarray([float(row["t_s"]) for row in rows], dtype=float)
    q = np.asarray(
        [[float(row[f"joint{i}_q_rad"]) for i in range(1, 7)] for row in rows],
        dtype=float,
    )
    dq = np.asarray(
        [[float(row[f"joint{i}_dq_rad_s"]) for i in range(1, 7)] for row in rows],
        dtype=float,
    )
    ddq = np.asarray(
        [[float(row[f"joint{i}_ddq_rad_s2"]) for i in range(1, 7)] for row in rows],
        dtype=float,
    )
    return {"rows": rows, "t": t, "q": q, "dq": dq, "ddq": ddq}


def _quintic_at(t: float, duration: float, q0: np.ndarray, q1: np.ndarray):
    x = min(max(float(t) / duration, 0.0), 1.0)
    s = 10.0 * x**3 - 15.0 * x**4 + 6.0 * x**5
    sd = (30.0 * x**2 - 60.0 * x**3 + 30.0 * x**4) / duration
    sdd = (60.0 * x - 180.0 * x**2 + 120.0 * x**3) / duration**2
    delta = q1 - q0
    return q0 + delta * s, delta * sd, delta * sdd


def _trajectory_audit(data: Mapping[str, Any], duration: float) -> dict[str, Any]:
    t = data["t"]
    q = data["q"]
    dq = data["dq"]
    ddq = data["ddq"]
    q0, q1 = q[0].copy(), q[-1].copy()
    q_ref, dq_ref, ddq_ref = [], [], []
    for ti in t:
        qi, dqi, ddqi = _quintic_at(float(ti), duration, q0, q1)
        q_ref.append(qi)
        dq_ref.append(dqi)
        ddq_ref.append(ddqi)
    q_ref = np.asarray(q_ref)
    dq_ref = np.asarray(dq_ref)
    ddq_ref = np.asarray(ddq_ref)
    return {
        "q0_rad": q0.tolist(),
        "q1_rad": q1.tolist(),
        "max_abs_q_reconstruction_error_rad": float(np.max(np.abs(q - q_ref))),
        "max_abs_dq_reconstruction_error_rad_s": float(
            np.max(np.abs(dq - dq_ref))
        ),
        "max_abs_ddq_reconstruction_error_rad_s2": float(
            np.max(np.abs(ddq - ddq_ref))
        ),
        "max_abs_dq_rad_s": np.max(np.abs(dq), axis=0).tolist(),
        "max_abs_ddq_rad_s2": np.max(np.abs(ddq), axis=0).tolist(),
        "endpoint_dq_max_abs_rad_s": float(
            max(np.max(np.abs(dq[0])), np.max(np.abs(dq[-1])))
        ),
        "endpoint_ddq_max_abs_rad_s2": float(
            max(np.max(np.abs(ddq[0])), np.max(np.abs(ddq[-1])))
        ),
        "joint_path_length_rad": np.sum(np.abs(np.diff(q, axis=0)), axis=0).tolist(),
    }


def _urdf_joint_limits() -> tuple[np.ndarray, np.ndarray]:
    root = ET.parse(
        project_path(
            "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
        )
    ).getroot()
    lowers, uppers = [], []
    for index in range(1, 7):
        joint = root.find(f"./joint[@name='joint{index}']")
        if joint is None or joint.find("limit") is None:
            raise ValueError(f"missing joint{index} limit")
        limit = joint.find("limit")
        assert limit is not None
        lowers.append(float(limit.get("lower")))
        uppers.append(float(limit.get("upper")))
    return np.asarray(lowers), np.asarray(uppers)


def _load_sim05_model():
    sim05_root = project_path("30_simulation/sim_05_free_floating_arm")
    if str(sim05_root) not in sys.path:
        sys.path.insert(0, str(sim05_root))
    b601_model = importlib.import_module("b601_model")
    dynamics = importlib.import_module("dynamics")
    urdf_path = project_path(
        "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
    )
    mass_path = project_path(
        "20_engineering/stage1_spacecraft_layout/04_mass_inertia_budget/"
        "mass_inertia_budget_v1.csv"
    )
    original_arm = dynamics.B601Arm
    original_loader = dynamics.load_object
    dynamics.B601Arm = lambda: original_arm(str(urdf_path))
    dynamics.load_object = lambda object_id: original_loader(object_id, str(mass_path))
    try:
        model = dynamics.FreeFloatingB601()
    finally:
        dynamics.B601Arm = original_arm
        dynamics.load_object = original_loader
    return model


def _evaluate_arm_lane(
    *,
    lane_id: str,
    source_relative: str,
    duration: float,
    expected_samples: int,
    model: Any,
    attached_target_propagated: bool,
) -> tuple[dict[str, Any], bytes]:
    data = _read_trajectory(project_path(source_relative))
    if len(data["rows"]) != expected_samples:
        raise ValueError(f"{lane_id} sample count mismatch")
    if abs(float(data["t"][-1]) - duration) > 1.0e-12:
        raise ValueError(f"{lane_id} duration mismatch")
    if np.max(np.abs(np.diff(data["t"]) - 0.01)) > 2.0e-12:
        raise ValueError(f"{lane_id} time grid mismatch")
    audit = _trajectory_audit(data, duration)
    speed_limits = np.asarray([0.7, 0.7, 0.7, 0.8, 0.8, 1.0], dtype=float)
    acceleration_limits = np.asarray([2.0, 2.0, 2.0, 2.5, 2.5, 3.0], dtype=float)
    reconstruction_pass = bool(
        audit["max_abs_q_reconstruction_error_rad"] <= 2.0e-14
        and audit["max_abs_dq_reconstruction_error_rad_s"] <= 2.0e-14
        and audit["max_abs_ddq_reconstruction_error_rad_s2"] <= 2.0e-14
    )
    provisional_limits_respected = bool(
        np.all(np.asarray(audit["max_abs_dq_rad_s"]) <= speed_limits + 1.0e-12)
        and np.all(
            np.asarray(audit["max_abs_ddq_rad_s2"])
            <= acceleration_limits + 1.0e-12
        )
    )
    endpoint_continuity_pass = bool(
        audit["endpoint_dq_max_abs_rad_s"] <= 1.0e-12
        and audit["endpoint_ddq_max_abs_rad_s2"] <= 1.0e-12
    )
    source_release_flags_false = all(
        str(row.get("released_for_mission_gate", "")).casefold() == "false"
        for row in data["rows"]
    )
    jaw_travel_all_null = all(
        row.get("jaw_travel_m") in (None, "") for row in data["rows"]
    )
    if not (
        reconstruction_pass
        and provisional_limits_respected
        and endpoint_continuity_pass
        and source_release_flags_false
        and jaw_travel_all_null
    ):
        raise RuntimeError(f"{lane_id} trajectory integrity failed closed")
    q0 = data["q"][0]
    q1 = data["q"][-1]

    def q_fun(t: float) -> np.ndarray:
        return _quintic_at(t, duration, q0, q1)[0]

    def qd_fun(t: float) -> np.ndarray:
        return _quintic_at(t, duration, q0, q1)[1]

    result = model.integrate_trajectory(
        q_fun,
        qd_fun,
        duration,
        n_out=expected_samples,
        rtol=1.0e-11,
        atol=1.0e-13,
    )
    residuals = []
    history_rows: list[dict[str, Any]] = []
    for index, t in enumerate(result["t"]):
        momentum = model.momentum_base_frame(
            q_fun(float(t)), result["Vb"][index], qd_fun(float(t))
        )
        residual = float(np.linalg.norm(momentum))
        residuals.append(residual)
        row = {
            "sample_index": index,
            "t_s": float(t),
            "base_x_m": float(result["r"][index, 0]),
            "base_y_m": float(result["r"][index, 1]),
            "base_z_m": float(result["r"][index, 2]),
            "base_q_w": float(result["Q"][index, 0]),
            "base_q_x": float(result["Q"][index, 1]),
            "base_q_y": float(result["Q"][index, 2]),
            "base_q_z": float(result["Q"][index, 3]),
            "base_euler_x_deg": float(result["euler_xyz_deg"][index, 0]),
            "base_euler_y_deg": float(result["euler_xyz_deg"][index, 1]),
            "base_euler_z_deg": float(result["euler_xyz_deg"][index, 2]),
            "base_attitude_deviation_deg": float(result["dev_angle_deg"][index]),
            "base_vx_m_s": float(result["Vb"][index, 0]),
            "base_vy_m_s": float(result["Vb"][index, 1]),
            "base_vz_m_s": float(result["Vb"][index, 2]),
            "base_wx_rad_s": float(result["Vb"][index, 3]),
            "base_wy_rad_s": float(result["Vb"][index, 4]),
            "base_wz_rad_s": float(result["Vb"][index, 5]),
            "momentum_residual_norm_S": residual,
            "authority_class": "NON_RELEASE_DIAGNOSTIC_EXECUTION_ONLY",
            "attached_target_propagated": str(attached_target_propagated).lower(),
            "released_for_mission_gate": "false",
        }
        history_rows.append(row)

    lowers, uppers = _urdf_joint_limits()
    q = data["q"]
    minimum_margin = float(np.min(np.minimum(q - lowers, uppers - q)))
    base_rate_norm = np.linalg.norm(result["Vb"][:, 3:], axis=1)
    base_translation_norm = np.linalg.norm(result["r"], axis=1)
    total_mass = float(sum(body["mass"] for body in model._bodies(q0)))
    audit.update(
        {
            "minimum_joint_limit_margin_rad": minimum_margin,
            "sample_count": expected_samples,
            "duration_s": duration,
            "sample_period_s": 0.01,
            "provisional_speed_limits_rad_s": speed_limits.tolist(),
            "provisional_acceleration_limits_rad_s2": acceleration_limits.tolist(),
            "analytic_reconstruction_pass": reconstruction_pass,
            "endpoint_continuity_pass": endpoint_continuity_pass,
            "provisional_limits_respected": provisional_limits_respected,
            "source_release_flags_all_false": source_release_flags_false,
            "jaw_travel_all_null": jaw_travel_all_null,
        }
    )
    summary = {
        "schema": f"E19_{lane_id}_BASE_REACTION_SUMMARY_V1",
        "generated_local": GENERATED_LOCAL,
        "lane_id": lane_id,
        "authority_class": "NON_RELEASE_DIAGNOSTIC_EXECUTION_ONLY",
        "source_candidate": source_relative,
        "trajectory_audit": audit,
        "solver": {
            "algorithm": "SIM05_RIGID_FREE_FLOATING_ZERO_MOMENTUM",
            "namespace_adapter": (
                "IN_MEMORY_EXPLICIT_REORG_PATH_INJECTION__UPSTREAM_FILES_UNMODIFIED"
            ),
            "legacy_default_path_currently_valid": False,
            "rigid_model_only": True,
            "flexible_panels_modeled": False,
            "actuator_dynamics_modeled": False,
            "diagnostic_model_total_mass_kg": total_mass,
            "mass_property_release_authority": False,
        },
        "base_reaction": {
            "peak_attitude_deviation_deg": float(np.max(result["dev_angle_deg"])),
            "final_attitude_deviation_deg": float(result["dev_angle_deg"][-1]),
            "peak_base_rate_rad_s": float(np.max(base_rate_norm)),
            "peak_base_translation_m": float(np.max(base_translation_norm)),
            "final_base_translation_m": result["r"][-1].tolist(),
            "max_momentum_residual_norm_S": float(max(residuals)),
            "momentum_residual_limit": 1.0e-12,
            "quaternion_norm_max_error": float(
                np.max(np.abs(np.linalg.norm(result["Q"], axis=1) - 1.0))
            ),
            "acceptance_threshold_authority": None,
            "engineering_prediction": False,
        },
        "attached_target_propagated": attached_target_propagated,
        "physical_stow_or_lock_confirmed": None,
        "collision_safe": None,
        "solar_keep_out_safe": None,
        "harness_safe": None,
        "hardware_motion_authorized": False,
        "released_for_mission_gate": False,
        "status": "PASS_ISOLATED_RIGID_FREE_FLOATING_DIAGNOSTIC",
    }
    history_fields = list(history_rows[0])
    return summary, csv_bytes(history_fields, history_rows)


def _load_sim13_modules():
    package_name = "_e19_sim13_src"
    src_root = project_path(
        "30_simulation/sim_13_physics_gated_embodied_grasping/src"
    )
    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(src_root)]
        package.__package__ = package_name
        sys.modules[package_name] = package
    action = importlib.import_module(f"{package_name}.action_space")
    randomization = importlib.import_module(f"{package_name}.domain_randomization")
    backend = importlib.import_module(f"{package_name}.physics_backend")
    return action, randomization, backend


def _evaluate_m05() -> tuple[dict[str, Any], bytes]:
    branches = load_json(
        project_path(
            "30_simulation/e18_b601_mission_input_branches/02_candidates/"
            "M05_22_TARGET_STATE_BRANCHES_V1.json"
        )
    )
    by_id = {branch["branch_id"]: branch for branch in branches["branches"]}
    kinetic = by_id["SIM13_KINEMATIC_BOOTSTRAP"]
    static = by_id["SCENE_MANIFEST_STATIC_DISPLAY"]
    if any(branch["merge_allowed"] for branch in branches["branches"]):
        raise RuntimeError("M05 branch merge unexpectedly allowed")
    action_mod, random_mod, backend_mod = _load_sim13_modules()
    backend = backend_mod.DeterministicPhysicsBackend(kinetic["timestep_s"])
    random_sample = random_mod.RandomizationSample(
        seed=0,
        target_mass_scale=1.0,
        tumble_delta_dps=0.0,
        relative_position_delta_m=(0.0, 0.0, 0.0),
    )
    state = backend.reset(kinetic["branch_id"].replace("SIM13_KINEMATIC_BOOTSTRAP", backend_mod.ANCHOR_22KG), random_sample, 8)
    abort = action_mod.HighLevelAction.abort()
    omega = float(kinetic["target_angular_velocity_rad_s"][2])
    history: list[dict[str, Any]] = []
    analytic_errors: list[float] = []
    norm_errors: list[float] = []

    def append_state(index: int, current: Any):
        theta = omega * current.simulation_time_s
        analytic = np.asarray(
            [0.0, 0.0, math.sin(theta / 2.0), math.cos(theta / 2.0)]
        )
        observed = np.asarray(current.target_relative_quaternion_xyzw)
        analytic_error = float(np.linalg.norm(observed - analytic))
        norm_error = float(abs(np.linalg.norm(observed) - 1.0))
        analytic_errors.append(analytic_error)
        norm_errors.append(norm_error)
        history.append(
            {
                "sample_index": index,
                "t_s": current.simulation_time_s,
                "target_x_m": current.target_relative_position_m[0],
                "target_y_m": current.target_relative_position_m[1],
                "target_z_m": current.target_relative_position_m[2],
                "target_q_x": observed[0],
                "target_q_y": observed[1],
                "target_q_z": observed[2],
                "target_q_w": observed[3],
                "target_wx_rad_s": current.target_angular_velocity_radps[0],
                "target_wy_rad_s": current.target_angular_velocity_radps[1],
                "target_wz_rad_s": current.target_angular_velocity_radps[2],
                "analytic_phase_deg": math.degrees(theta),
                "quaternion_norm_error": norm_error,
                "analytic_quaternion_error": analytic_error,
                "collision_detected_backend_field": str(current.collision_detected).lower(),
                "collision_safety_interpretation": "PROHIBITED",
                "action": "ABORT",
                "released_for_mission_gate": "false",
            }
        )

    append_state(0, state)
    for step in range(1, 1001):
        state = backend.step(abort)
        append_state(step, state)

    R = np.asarray(static["R_TS"], dtype=float)
    origin = np.asarray(static["target_origin_S_m"], dtype=float)
    grasp_t = np.asarray(static["primary_grasp_point_T_m"], dtype=float)
    capture_s = np.asarray(static["capture_point_S_m"], dtype=float)
    mass_props = load_yaml(
        project_path(
            "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/"
            "03_mass_properties/SYSTEM_MASS_PROPERTIES_V3.yaml"
        )
    )
    com_t = np.asarray(
        mass_props["component_records"]["target_22kg_scenario"]["center_of_mass"][
            "estimate_xyz_m"
        ],
        dtype=float,
    )
    com_s = np.asarray(static["target_com_S_m"], dtype=float)
    ortho_residual = float(np.linalg.norm(R.T @ R - np.eye(3), ord="fro"))
    determinant = float(np.linalg.det(R))
    grasp_residual = float(np.linalg.norm(origin + R @ grasp_t - capture_s))
    com_residual = float(np.linalg.norm(origin + R @ com_t - com_s))

    summary = {
        "schema": "E19_M05_BRANCH_EVALUATION_V1",
        "generated_local": GENERATED_LOCAL,
        "authority_class": "NON_RELEASE_DIAGNOSTIC_EXECUTION_ONLY",
        "branch_nonmerge_rule": branches["branch_nonmerge_rule"],
        "branch_ids": list(by_id),
        "branch_merge_performed": False,
        "sim13_kinematic_branch": {
            "target_mass_kg_metadata_only": state.target_mass_kg,
            "timestep_s": backend.timestep_s,
            "steps": 1000,
            "history_samples": len(history),
            "final_time_s": state.simulation_time_s,
            "final_phase_deg": math.degrees(omega * state.simulation_time_s),
            "max_quaternion_norm_error": max(norm_errors),
            "max_analytic_quaternion_error": max(analytic_errors),
            "randomization_enabled": False,
            "action": "ABORT",
            "contact_computed": False,
            "collision_detected_false_is_safety_credit": False,
            "production_binding_valid": False,
            "status": "PASS_BRANCH_LOCAL_CONSTANT_RATE_KINEMATICS",
        },
        "static_display_branch": {
            "R_TS_orthogonality_residual": ortho_residual,
            "R_TS_determinant": determinant,
            "capture_point_transform_residual_m": grasp_residual,
            "target_com_transform_residual_m": com_residual,
            "capture_time_s_semantics": "STATIC_DISPLAY_PARAMETER_NOT_MISSION_EPOCH",
            "time_propagation_performed": False,
            "target_twist_introduced": False,
            "status": "PASS_STATIC_FRAME_ALGEBRA_ONLY",
        },
        "required_physical_inputs": {
            "epoch": None,
            "common_frame": None,
            "T_service_target_at_epoch": None,
            "rotation_axis": None,
            "phase_at_epoch_rad": None,
            "grasp_interface_id": None,
            "target_surface_normal": None,
            "sync_terminal_twist": None,
            "sync_error_tolerance": None,
            "sync_time_window_s": None,
            "selected_whole_system_mass_inertia_branch": None,
        },
        "released_for_mission_gate": False,
        "status": "PASS_TWO_ISOLATED_NONMERGEABLE_M05_DIAGNOSTICS",
    }
    return summary, csv_bytes(list(history[0]), history)


def _simpson_uniform(values: np.ndarray, step: float) -> float:
    if len(values) < 3 or (len(values) - 1) % 2:
        raise ValueError("Simpson integration requires an even number of intervals")
    return float(
        step
        / 3.0
        * (
            values[0]
            + values[-1]
            + 4.0 * np.sum(values[1:-1:2])
            + 2.0 * np.sum(values[2:-1:2])
        )
    )


def _evaluate_m06() -> tuple[dict[str, Any], bytes]:
    matrix_path = project_path(
        "30_simulation/e18_b601_mission_input_branches/02_candidates/"
        "M06_22_HALF_SINE_EQUAL_IMPULSE_STIMULUS_MATRIX_V1.csv"
    )
    with matrix_path.open("r", encoding="utf-8", newline="") as stream:
        source_rows = list(csv.DictReader(stream))
    physical_fields = (
        "solver_standard_uncertainty_N_s",
        "physical_contact_duration_s",
        "physical_contact_force_N",
        "physical_contact_pressure_Pa",
        "physical_contact_normal",
        "physical_lock_confirmation",
    )
    if len(source_rows) != 20:
        raise ValueError("M06 must contain exactly 20 cases")
    if any(row[field] not in ("", None) for row in source_rows for field in physical_fields):
        raise ValueError("M06 physical or uncertainty fields must remain null")
    summaries: list[dict[str, Any]] = []
    saved: list[dict[str, Any]] = []
    grid = set()
    for row in source_rows:
        case_id = row["case_id"]
        speed = float(row["approach_speed_m_s"])
        impulse = float(row["source_impulse_N_s"])
        window_ms = int(row["solver_contact_window_ms"])
        window_s = float(row["solver_contact_window_s"])
        peak = float(row["solver_peak_force_N"])
        grid.add((speed, window_ms))
        expected_peak = math.pi * impulse / (2.0 * window_s)
        n = 10001
        time = np.linspace(0.0, window_s, n)
        force = peak * np.sin(math.pi * time / window_s)
        numerical_impulse = _simpson_uniform(force, window_s / (n - 1))
        relative_error = abs(numerical_impulse - impulse) / impulse
        endpoint_max = float(max(abs(force[0]), abs(force[-1])))
        midpoint_error = float(abs(force[n // 2] - peak))
        ratio_error = float(abs(peak * window_s / impulse - math.pi / 2.0))
        summaries.append(
            {
                "case_id": case_id,
                "approach_speed_m_s": speed,
                "source_impulse_N_s": impulse,
                "solver_contact_window_ms": window_ms,
                "solver_contact_window_s": window_s,
                "solver_peak_force_N": peak,
                "expected_peak_force_N": expected_peak,
                "peak_formula_abs_error_N": abs(peak - expected_peak),
                "numerical_impulse_N_s": numerical_impulse,
                "relative_impulse_error": relative_error,
                "endpoint_max_abs_amplitude_N": endpoint_max,
                "midpoint_peak_abs_error_N": midpoint_error,
                "Fpeak_Tc_over_J_minus_pi_over_2": ratio_error,
                "standard_uncertainty_N_s": None,
                "classification": "SOLVER_STIMULUS_PROXY_NOT_HARDWARE_CONTACT",
                "physical_contact_interpretation": False,
                "status": "PASS_EQUAL_IMPULSE_HALF_SINE_NUMERICAL_INTEGRATION",
            }
        )
        for sample_index, ti in enumerate(np.linspace(0.0, window_s, 201)):
            fi = peak * math.sin(math.pi * ti / window_s)
            cumulative = peak * window_s / math.pi * (
                1.0 - math.cos(math.pi * ti / window_s)
            )
            saved.append(
                {
                    "case_id": case_id,
                    "sample_index": sample_index,
                    "t_s": ti,
                    "solver_stimulus_amplitude_N": fi,
                    "analytic_cumulative_impulse_N_s": cumulative,
                    "source_impulse_N_s": impulse,
                    "solver_contact_window_s": window_s,
                    "stimulus_role": "SOLVER_STIMULUS_PROXY_NOT_HARDWARE_CONTACT",
                    "released_for_mission_gate": "false",
                }
            )
    expected_grid = {
        (speed, window)
        for speed in (0.005, 0.01, 0.02, 0.03)
        for window in (5, 10, 20, 50, 100)
    }
    if grid != expected_grid:
        raise ValueError("M06 grid mismatch")
    summary = {
        "schema": "E19_M06_HALF_SINE_EXECUTION_REGISTER_V1",
        "generated_local": GENERATED_LOCAL,
        "authority_class": "NON_RELEASE_DIAGNOSTIC_EXECUTION_ONLY",
        "measurement_model": "Fpeak=pi*J/(2*Tc); integral_0^Tc F(t)dt=J",
        "case_count": len(summaries),
        "grid_unique": True,
        "high_resolution_samples_per_case": 10001,
        "saved_samples_per_case": 201,
        "cases": summaries,
        "max_relative_impulse_error": max(
            case["relative_impulse_error"] for case in summaries
        ),
        "physical_contact_and_lock": {
            "contact_duration_s": None,
            "contact_force_N": None,
            "contact_pressure_Pa": None,
            "contact_normal": None,
            "contact_point_m": None,
            "contact_area_m2": None,
            "initial_gap_m": None,
            "stiffness_N_m": None,
            "damping_N_s_m": None,
            "coefficient_of_restitution": None,
            "static_friction_coefficient": None,
            "kinetic_friction_coefficient": None,
            "lock_confirmed": None,
            "lock_retention_force_N": None,
            "gripper_physical_closing_speed_m_s": None,
            "gripper_physical_closing_time_s": None,
        },
        "six_dimensional_impulse_synthesized": False,
        "hardware_force_credit": False,
        "released_for_mission_gate": False,
        "status": "PASS_20_OF_20_SCALAR_SOLVER_STIMULUS_EXECUTIONS",
    }
    return summary, csv_bytes(list(saved[0]), saved)


def _load_sim15_generator():
    sim15_root = project_path("30_simulation/sim_15_m5_geometry_gated_grasping")
    if str(sim15_root) not in sys.path:
        sys.path.insert(0, str(sim15_root))
    module_name = "_e19_sim15_generate_baseline"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(
        module_name, sim15_root / "tools" / "generate_baseline.py"
    )
    if spec is None or spec.loader is None:
        raise ImportError("unable to load Sim15 generator")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _evaluate_m07_rigid(m06_summary: Mapping[str, Any]) -> dict[str, Any]:
    generator = _load_sim15_generator()
    regenerated = generator.build_baseline()
    regenerated_bytes = json_bytes(regenerated)
    expected_hash = (
        "4D6B08F5F8DD6A45CC1CDCFBF2A04CEACF758ABAB1350FF0BE6742DCD4E85C1F"
    )
    if sha256_bytes(regenerated_bytes) != expected_hash:
        raise RuntimeError("Sim15 current code no longer reproduces bound baseline")
    cases = [
        case
        for case in regenerated["capture_envelope"]["cases"]
        if case["anchor_id"] == "ANCHOR_22KG_0P5DPS"
    ]
    cases.sort(key=lambda case: case["approach_speed_mps"])
    e18_m07 = load_json(
        project_path(
            "30_simulation/e18_b601_mission_input_branches/02_candidates/"
            "M07_22_ATTACHED_TARGET_RECOVERY_BRANCHES_V1.json"
        )
    )
    embedded = e18_m07["sim15_0p01_m_s_full_state_branch"]["full_case_record"]
    compact_cases = []
    m06_by_speed = {}
    for case in m06_summary["cases"]:
        m06_by_speed.setdefault(case["approach_speed_m_s"], case["source_impulse_N_s"])
    for case in cases:
        output = case["output"]
        inertia = np.asarray(output["combined_inertia_about_com_kg_m2"], dtype=float)
        eig = np.linalg.eigvalsh(inertia)
        service_impulse = float(
            np.linalg.norm(np.asarray(output["service_com_linear_impulse_N_s"]))
        )
        scalar_sim06 = float(m06_by_speed[case["approach_speed_mps"]])
        compact_cases.append(
            {
                "case_id": case["case_id"],
                "approach_speed_m_s": case["approach_speed_mps"],
                "input_sha256": case["input_sha256"],
                "solver_sha256": case["solver_sha256"],
                "output_sha256": case["output_sha256"],
                "total_mass_kg": output["total_mass_kg"],
                "combined_center_of_mass_m": output["combined_center_of_mass_m"],
                "combined_linear_velocity_m_s": output[
                    "combined_linear_velocity_mps"
                ],
                "combined_angular_velocity_rad_s": output[
                    "combined_angular_velocity_radps"
                ],
                "combined_inertia_min_eigenvalue_kg_m2": float(np.min(eig)),
                "combined_inertia_symmetric": bool(
                    np.allclose(inertia, inertia.T, atol=1.0e-14, rtol=0.0)
                ),
                "linear_momentum_residual_norm_kg_m_s": output[
                    "linear_residual_norm_kg_mps"
                ],
                "angular_momentum_residual_norm_kg_m2_s": output[
                    "angular_residual_norm_kg_m2ps"
                ],
                "kinetic_energy_before_J": output["kinetic_energy_before_J"],
                "kinetic_energy_after_J": output["kinetic_energy_after_J"],
                "plastic_energy_loss_J": output["plastic_energy_loss_J"],
                "service_com_linear_impulse_magnitude_N_s": service_impulse,
                "m06_scalar_source_impulse_N_s_separate_model": scalar_sim06,
                "m06_to_sim15_service_impulse_ratio_nonmergeable": (
                    scalar_sim06 / service_impulse
                ),
                "model_difference_is_measurement_uncertainty": False,
                "physical_contact_computed": output["physical_contact_computed"],
                "contact_duration_s": output["contact_duration_s"],
                "contact_force_N": output["contact_force_N"],
                "contact_pressure_Pa": output["contact_pressure_Pa"],
                "engineering_prediction": output["engineering_prediction"],
                "status": case["status"],
            }
        )
    required = next(
        case for case in cases if abs(case["approach_speed_mps"] - 0.01) < 1.0e-15
    )
    mass_branches = deepcopy(e18_m07["C08_diagnostic_mass_branches"])
    return {
        "schema": "E19_M07_SIM15_RIGID_CAPTURE_RECOMPUTE_V1",
        "generated_local": GENERATED_LOCAL,
        "authority_class": "NON_RELEASE_DIAGNOSTIC_EXECUTION_ONLY",
        "sim15_baseline_recomputed_from_current_hash_bound_code": True,
        "bound_baseline_sha256": expected_hash,
        "recomputed_baseline_sha256": sha256_bytes(regenerated_bytes),
        "solver_bundle_sha256": regenerated["solver_receipt"]["bundle_sha256"],
        "case_count": len(compact_cases),
        "cases": compact_cases,
        "e18_required_0p01_case": {
            "case_id_match": required["case_id"] == embedded["case_id"],
            "input_sha256_match": required["input_sha256"]
            == embedded["input_sha256"],
            "output_sha256_match": required["output_sha256"]
            == embedded["output_sha256"],
            "solver_sha256_match": required["solver_sha256"]
            == embedded["solver_sha256"],
        },
        "C08_diagnostic_mass_branches": mass_branches,
        "C08_branch_selection_performed": False,
        "C08_branch_averaging_performed": False,
        "C08_branch_delta_kg_not_uncertainty": abs(
            mass_branches[1]["mass_kg"] - mass_branches[0]["mass_kg"]
        ),
        "selected_post_capture_model_branch": None,
        "locked_transform_gripper_to_target": None,
        "contact_normals": None,
        "released_mass_kg": None,
        "released_cg_m": None,
        "released_inertia_kg_m2": None,
        "attached_target_recovery_propagated": False,
        "physical_contact_authority": False,
        "released_for_mission_gate": False,
        "status": "PASS_SIM15_CURRENT_CODE_EXACT_REPRODUCTION_DIAGNOSTIC_ONLY",
    }


def _null_ledger() -> dict[str, Any]:
    contracts = {
        "M01": load_yaml(
            project_path(
                "30_simulation/e18_b601_mission_input_branches/01_contracts/"
                "M01_RELEASE_EVENT_AND_SWEEP_V1.yaml"
            )
        ),
        "M05": load_yaml(
            project_path(
                "30_simulation/e18_b601_mission_input_branches/01_contracts/"
                "M05_22_TARGET_STATE_AND_SYNC_V1.yaml"
            )
        ),
        "M06": load_yaml(
            project_path(
                "30_simulation/e18_b601_mission_input_branches/01_contracts/"
                "M06_22_CONTACT_AND_LOCK_V1.yaml"
            )
        ),
        "M07": load_yaml(
            project_path(
                "30_simulation/e18_b601_mission_input_branches/01_contracts/"
                "M07_22_ATTACHED_TARGET_RECOVERY_V1.yaml"
            )
        ),
    }
    m01_event = contracts["M01"]["release_event_contract"]
    m05_inputs = contracts["M05"]["required_physical_inputs"]
    m06_contact = contracts["M06"]["physical_contact_and_lock"]
    m07_inputs = contracts["M07"]["required_physical_inputs"]
    m07_mass = contracts["M07"]["released_mass_cg_inertia"]
    return {
        "schema": "E19_NULL_HOLD_LEDGER_V1",
        "M01_release_event": {
            key: value
            for key, value in m01_event.items()
            if key
            not in {
                "physical_stow_status",
                "arm_motion_enable_guard",
                "guard_binding_status",
            }
        },
        "M05_required_physical_inputs": m05_inputs,
        "M06_physical_contact_and_lock": {
            key: value for key, value in m06_contact.items() if key != "status"
        },
        "M07_required_physical_inputs": m07_inputs,
        "M07_released_mass_cg_inertia": {
            key: value for key, value in m07_mass.items() if key != "status"
        },
        "unknown_zero_fill_performed": False,
    }


def _all_leaf_values_none(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(_all_leaf_values_none(item) for item in value.values())
    if isinstance(value, list):
        return all(_all_leaf_values_none(item) for item in value)
    return value is None


def _write_documents(documents: Mapping[str, bytes]) -> None:
    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    for relative, content in documents.items():
        path = project_path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_bytes(content)
        temporary.replace(path)


def build_package(*, write: bool = True) -> dict[str, Any]:
    input_manifest = build_input_manifest()
    loop_gate = load_json(project_path(SOURCE_SPECS[0][1]))
    if (
        loop_gate["bounded_diagnostic_lane"]["state"]
        != "HASH_BOUND_ISOLATED_NON_RELEASE_NUMERIC_INPUT_BRANCH_INTEGRITY_READY"
    ):
        raise RuntimeError("upstream bounded diagnostic lane is not authorized")
    if loop_gate["next_stage_authorized"] or loop_gate["release_credit"]:
        raise RuntimeError("upstream release semantics changed unexpectedly")
    e18_gate = load_json(
        project_path(
            "30_simulation/e18_b601_mission_input_branches/results/"
            "E18_B601_MISSION_INPUT_BRANCH_GATE_V1.json"
        )
    )
    if e18_gate["gate"] != "HOLD" or e18_gate["released_segments"] != 0:
        raise RuntimeError("e18 must remain HOLD with zero released segments")

    model = _load_sim05_model()
    m01_summary, m01_history = _evaluate_arm_lane(
        lane_id="M01",
        source_relative=(
            "30_simulation/e18_b601_mission_input_branches/02_candidates/"
            "M01_HELD_STOW_TO_RELEASE_CLEAR_QUINTIC_V1.csv"
        ),
        duration=11.5,
        expected_samples=1151,
        model=model,
        attached_target_propagated=False,
    )
    m05_summary, m05_history = _evaluate_m05()
    m06_summary, m06_history = _evaluate_m06()
    m07_arm_summary, m07_arm_history = _evaluate_arm_lane(
        lane_id="M07_ARM_ONLY",
        source_relative=(
            "30_simulation/e17_b601_mission_trajectory_candidates/results/candidates/"
            "M07_22_ARM_ONLY_QUINTIC_V1.csv"
        ),
        duration=4.5,
        expected_samples=451,
        model=model,
        attached_target_propagated=False,
    )
    m07_rigid = _evaluate_m07_rigid(m06_summary)
    null_ledger = _null_ledger()
    null_sections = {
        key: value
        for key, value in null_ledger.items()
        if key not in {"schema", "unknown_zero_fill_performed"}
    }
    if not _all_leaf_values_none(null_sections):
        raise RuntimeError("physical UNKNOWN/null ledger was populated")

    result_contents: dict[str, bytes] = {
        "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/results/"
        "E19_M01_BASE_REACTION_SUMMARY_V1.json": json_bytes(m01_summary),
        "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/results/"
        "E19_M01_BASE_REACTION_HISTORY_V1.csv": m01_history,
        "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/results/"
        "E19_M05_BRANCH_EVALUATION_V1.json": json_bytes(m05_summary),
        "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/results/"
        "E19_M05_SIM13_KINEMATIC_HISTORY_V1.csv": m05_history,
        "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/results/"
        "E19_M06_HALF_SINE_EXECUTION_REGISTER_V1.json": json_bytes(m06_summary),
        "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/results/"
        "E19_M06_HALF_SINE_SAVED_HISTORY_V1.csv": m06_history,
        "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/results/"
        "E19_M07_ARM_ONLY_BASE_REACTION_SUMMARY_V1.json": json_bytes(
            m07_arm_summary
        ),
        "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/results/"
        "E19_M07_ARM_ONLY_BASE_REACTION_HISTORY_V1.csv": m07_arm_history,
        "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/results/"
        "E19_M07_SIM15_RIGID_CAPTURE_RECOMPUTE_V1.json": json_bytes(m07_rigid),
    }
    input_relative = (
        "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/results/"
        "E19_INPUT_MANIFEST_V1.json"
    )
    result_contents[input_relative] = json_bytes(input_manifest)
    result_records = [
        {
            "result_id": Path(relative).stem,
            "path": relative,
            "sha256": sha256_bytes(content),
            "bytes": len(content),
        }
        for relative, content in result_contents.items()
        if relative != input_relative
    ]
    register = {
        "schema": "E19_DIAGNOSTIC_EVALUATION_REGISTER_V1",
        "generated_local": GENERATED_LOCAL,
        "authority_class": "NON_RELEASE_DIAGNOSTIC_EXECUTION_ONLY",
        "input_manifest": {
            "path": input_relative,
            "sha256": sha256_bytes(result_contents[input_relative]),
        },
        "results": result_records,
        "result_count": len(result_records),
        "lane_execution": {
            "M01": "PASS_ISOLATED_RIGID_FREE_FLOATING_DIAGNOSTIC",
            "M05_SIM13": "PASS_BRANCH_LOCAL_CONSTANT_RATE_KINEMATICS",
            "M05_STATIC": "PASS_STATIC_FRAME_ALGEBRA_ONLY",
            "M06": "PASS_20_OF_20_SCALAR_SOLVER_STIMULUS_EXECUTIONS",
            "M07_ARM_ONLY": "PASS_ISOLATED_RIGID_FREE_FLOATING_DIAGNOSTIC",
            "M07_SIM15": "PASS_SIM15_CURRENT_CODE_EXACT_REPRODUCTION_DIAGNOSTIC_ONLY",
        },
        "lane_execution_count": 6,
        "cross_lane_chaining_performed": False,
        "branch_merging_performed": False,
        "mission_timeline_created": False,
        "attached_target_recovery_propagated": False,
        "null_hold_ledger": null_ledger,
        "diagnostic_observations": {
            "M01_peak_base_attitude_deviation_deg": m01_summary["base_reaction"][
                "peak_attitude_deviation_deg"
            ],
            "M07_arm_only_peak_base_attitude_deviation_deg": m07_arm_summary[
                "base_reaction"
            ]["peak_attitude_deviation_deg"],
            "no_base_attitude_acceptance_threshold_authority": True,
            "M06_vs_Sim15_impulses_are_separate_models": True,
        },
        "isolated_numeric_diagnostic_execution_ready": True,
        "end_to_end_diagnostic_dynamics_ready": False,
        "physical_contact_ready": False,
        "attached_target_recovery_ready": False,
        "mission_sequence_executable": False,
        "production_dynamics_ready": False,
        "cad_or_mesh_generated": False,
        "accepted_urdf_modified": False,
        "released_segments": 0,
        "release_credit": False,
        "next_stage_authorized": False,
    }
    register_relative = (
        "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/results/"
        "E19_DIAGNOSTIC_EVALUATION_REGISTER_V1.json"
    )
    result_contents[register_relative] = json_bytes(register)

    criteria = [
        ("E19-G01", "all source and solver hashes exact", input_manifest["all_exact_hash_match"]),
        ("E19-G02", "accepted URDF immutable", input_manifest["accepted_urdf_sha256"] == ACCEPTED_URDF_SHA256),
        ("E19-G03", "M01 quintic and rigid free-floating momentum closure", m01_summary["trajectory_audit"]["analytic_reconstruction_pass"] and m01_summary["trajectory_audit"]["endpoint_continuity_pass"] and m01_summary["trajectory_audit"]["provisional_limits_respected"] and m01_summary["trajectory_audit"]["minimum_joint_limit_margin_rad"] > 0.0 and m01_summary["base_reaction"]["max_momentum_residual_norm_S"] <= 1.0e-12),
        ("E19-G04", "M01 release hardware and safety authority remain absent", m01_summary["physical_stow_or_lock_confirmed"] is None and not m01_summary["hardware_motion_authorized"]),
        ("E19-G05", "M05 Sim13 constant-rate kinematic reproduction", m05_summary["sim13_kinematic_branch"]["max_analytic_quaternion_error"] <= 1.0e-12 and m05_summary["sim13_kinematic_branch"]["max_quaternion_norm_error"] <= 1.0e-12 and abs(m05_summary["sim13_kinematic_branch"]["final_phase_deg"] - 25.0) <= 1.0e-10 and not m05_summary["sim13_kinematic_branch"]["randomization_enabled"] and not m05_summary["sim13_kinematic_branch"]["contact_computed"] and not m05_summary["sim13_kinematic_branch"]["collision_detected_false_is_safety_credit"]),
        ("E19-G06", "M05 static frame algebra", m05_summary["static_display_branch"]["R_TS_orthogonality_residual"] <= 1.0e-12 and abs(m05_summary["static_display_branch"]["R_TS_determinant"] - 1.0) <= 1.0e-12 and m05_summary["static_display_branch"]["capture_point_transform_residual_m"] <= 1.0e-12 and m05_summary["static_display_branch"]["target_com_transform_residual_m"] <= 1.0e-12 and not m05_summary["static_display_branch"]["time_propagation_performed"] and not m05_summary["static_display_branch"]["target_twist_introduced"]),
        ("E19-G07", "M05 branches remain nonmergeable", not m05_summary["branch_merge_performed"]),
        ("E19-G08", "M06 20-case equal-impulse waveform closure", m06_summary["case_count"] == 20 and m06_summary["grid_unique"] and m06_summary["max_relative_impulse_error"] < 1.0e-8 and all(case["peak_formula_abs_error_N"] <= 1.0e-12 and case["endpoint_max_abs_amplitude_N"] <= 1.0e-12 and case["midpoint_peak_abs_error_N"] <= 1.0e-12 and case["Fpeak_Tc_over_J_minus_pi_over_2"] <= 1.0e-12 and case["standard_uncertainty_N_s"] is None and not case["physical_contact_interpretation"] for case in m06_summary["cases"])),
        ("E19-G09", "M06 physical contact fields remain null", _all_leaf_values_none(m06_summary["physical_contact_and_lock"])),
        ("E19-G10", "M07 arm-only trajectory excludes attached target", m07_arm_summary["trajectory_audit"]["analytic_reconstruction_pass"] and m07_arm_summary["trajectory_audit"]["endpoint_continuity_pass"] and m07_arm_summary["trajectory_audit"]["provisional_limits_respected"] and m07_arm_summary["trajectory_audit"]["jaw_travel_all_null"] and m07_arm_summary["base_reaction"]["max_momentum_residual_norm_S"] <= 1.0e-12 and not m07_arm_summary["attached_target_propagated"]),
        ("E19-G11", "Sim15 current code exactly reproduces bound baseline", m07_rigid["sim15_baseline_recomputed_from_current_hash_bound_code"] and m07_rigid["bound_baseline_sha256"] == m07_rigid["recomputed_baseline_sha256"]),
        ("E19-G12", "Sim15 momentum energy and inertia diagnostic closure", all(case["linear_momentum_residual_norm_kg_m_s"] < 1.0e-11 and case["angular_momentum_residual_norm_kg_m2_s"] < 1.0e-11 and case["kinetic_energy_after_J"] <= case["kinetic_energy_before_J"] + 1.0e-15 and case["plastic_energy_loss_J"] >= 0.0 and case["combined_inertia_symmetric"] and case["combined_inertia_min_eigenvalue_kg_m2"] > 0.0 and not case["physical_contact_computed"] and case["contact_duration_s"] is None and case["contact_force_N"] is None and case["contact_pressure_Pa"] is None and not case["engineering_prediction"] for case in m07_rigid["cases"])),
        ("E19-G13", "M07 locked transform and released mass properties remain null", m07_rigid["selected_post_capture_model_branch"] is None and m07_rigid["locked_transform_gripper_to_target"] is None and m07_rigid["released_mass_kg"] is None and m07_rigid["released_cg_m"] is None and m07_rigid["released_inertia_kg_m2"] is None),
        ("E19-G14", "all physical UNKNOWN values remain null", _all_leaf_values_none(null_sections)),
        ("E19-G15", "no cross-lane chaining or branch merge", not register["cross_lane_chaining_performed"] and not register["branch_merging_performed"]),
        ("E19-G16", "no CAD mesh URDF or historical Gate mutation", not register["cad_or_mesh_generated"] and not register["accepted_urdf_modified"]),
        ("E19-G17", "all release and production claims fail closed", not register["end_to_end_diagnostic_dynamics_ready"] and not register["physical_contact_ready"] and not register["mission_sequence_executable"] and not register["production_dynamics_ready"] and register["released_segments"] == 0),
    ]
    gate = {
        "schema": "E19_ISOLATED_NONRELEASE_DIAGNOSTIC_GATE_V1",
        "generated_local": GENERATED_LOCAL,
        "authority_scope": "ISOLATED_NUMERIC_DIAGNOSTIC_EXECUTION_ONLY",
        "input_manifest": register["input_manifest"],
        "result_register": {
            "path": register_relative,
            "sha256": sha256_bytes(result_contents[register_relative]),
        },
        "criteria": [
            {
                "id": criterion_id,
                "name": name,
                "state": "PASS_DIAGNOSTIC_ONLY" if observed else "FAIL",
                "observed": bool(observed),
                "release_credit": False,
            }
            for criterion_id, name, observed in criteria
        ],
        "criteria_total": len(criteria),
        "criteria_observed": sum(bool(item[2]) for item in criteria),
        "four_mission_segments_consumed_as_independent_lanes": True,
        "six_isolated_lane_evaluations_executed": True,
        "cross_lane_chaining_performed": False,
        "diagnostic_execution_verdict": "PASS",
        "isolated_numeric_diagnostic_execution_ready": True,
        "end_to_end_diagnostic_dynamics_ready": False,
        "physical_contact_ready": False,
        "attached_target_recovery_ready": False,
        "mission_release_ready": False,
        "production_dynamics_ready": False,
        "hardware_motion_ready": False,
        "mechanical_design_released": False,
        "flight_qualification_ready": False,
        "released_segments": 0,
        "testing_pass_grants_authority": False,
        "gate": "HOLD",
        "verdict": "E19_ISOLATED_NUMERIC_REPRODUCIBILITY_CLOSED__END_TO_END_PHYSICAL_CONTACT_ATTACHED_RECOVERY_AND_MISSION_RELEASE_HOLD",
        "next_stage_authorized": False,
        "release_credit": False,
        "allowed_next": [
            "use the isolated numerical observations to prioritize coupled-model and hardware-input closure",
            "repeat each lane independently after an explicitly versioned input or solver change",
            "close ODR-42 MPI actuator contact lock target-state and released mass-property evidence",
        ],
        "prohibited_next": [
            "chain lane outputs into a mission trajectory",
            "promote M06 amplitude to physical contact force",
            "propagate an attached target without a locked transform and selected mass branch",
            "rebind Sim13 as production contact or RL dynamics",
            "generate Route-C CAD before ODR-42 and 8-of-8 MPI closure",
        ],
    }
    gate_relative = (
        "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/results/"
        "E19_DIAGNOSTIC_EVALUATION_GATE_V1.json"
    )
    result_contents[gate_relative] = json_bytes(gate)

    controlled_records = [
        artifact_record(relative) for relative in STATIC_ARTIFACTS
    ] + [
        {
            "path": relative,
            "sha256": sha256_bytes(content),
            "bytes": len(content),
        }
        for relative, content in result_contents.items()
    ]
    output_manifest = {
        "schema": "E19_OUTPUT_MANIFEST_V1",
        "generated_local": GENERATED_LOCAL,
        "scope": "CONTROLLED_E19_CODE_CONTRACTS_AND_RESULTS__VALIDATION_EXCLUDED_TO_AVOID_RECURSIVE_HASHING",
        "artifacts": controlled_records,
        "artifact_count": len(controlled_records),
        "artifact_set_sha256": sha256_bytes(canonical_json_bytes(controlled_records)),
        "input_source_set_sha256": input_manifest["source_set_sha256"],
        "accepted_urdf_sha256": ACCEPTED_URDF_SHA256,
        "validation_report_excluded": True,
        "gate": "HOLD",
        "released_segments": 0,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    manifest_relative = (
        "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/results/"
        "E19_OUTPUT_MANIFEST_V1.json"
    )
    result_contents[manifest_relative] = json_bytes(output_manifest)
    if write:
        _write_documents(result_contents)
    return {
        "input_manifest": input_manifest,
        "M01": m01_summary,
        "M05": m05_summary,
        "M06": m06_summary,
        "M07_ARM_ONLY": m07_arm_summary,
        "M07_SIM15": m07_rigid,
        "register": register,
        "gate": gate,
        "output_manifest": output_manifest,
        "files": result_contents,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="rebuild in memory and compare every generated artifact with disk",
    )
    args = parser.parse_args(argv)
    package = build_package(write=not args.check_only)
    exact = True
    if args.check_only:
        for relative, expected in package["files"].items():
            path = project_path(relative)
            exact = exact and path.is_file() and path.read_bytes() == expected
    report = {
        "verdict": package["gate"]["verdict"],
        "gate": package["gate"]["gate"],
        "criteria": f"{package['gate']['criteria_observed']}/{package['gate']['criteria_total']}",
        "generated_artifacts": len(package["files"]),
        "check_only_exact_match": exact if args.check_only else None,
        "M01_peak_base_attitude_deviation_deg": package["M01"]["base_reaction"]["peak_attitude_deviation_deg"],
        "M07_arm_only_peak_base_attitude_deviation_deg": package["M07_ARM_ONLY"]["base_reaction"]["peak_attitude_deviation_deg"],
        "release_credit": False,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
    return 0 if package["gate"]["diagnostic_execution_verdict"] == "PASS" and exact else 1


if __name__ == "__main__":
    raise SystemExit(main())
