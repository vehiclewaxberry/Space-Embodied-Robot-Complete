"""Independent fail-closed validation for the e19 B601 diagnostic package.

The validator deliberately does not import the e19 builder.  It recomputes
hash closure, trajectory/history summaries, branch-local kinematics, scalar
half-sine identities, and Sim15 diagnostic invariants from persisted files.
Every adversarial mutation is evaluated by the same ``gate_safe(bundle)``
predicate used for the unmodified package.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable, Mapping

import numpy as np
import yaml


PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[1]
PREFIX = "30_simulation/e19_b601_mission_branch_diagnostic_evaluation"
URDF_SHA256 = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"

FILES = {
    "authority": f"{PREFIX}/00_authority/E19_AUTHORITY_CONTRACT_V1.yaml",
    "config": f"{PREFIX}/config/E19_ISOLATED_DIAGNOSTIC_CAMPAIGN_V1.yaml",
    "input_manifest": f"{PREFIX}/results/E19_INPUT_MANIFEST_V1.json",
    "m01": f"{PREFIX}/results/E19_M01_BASE_REACTION_SUMMARY_V1.json",
    "m01_history": f"{PREFIX}/results/E19_M01_BASE_REACTION_HISTORY_V1.csv",
    "m05": f"{PREFIX}/results/E19_M05_BRANCH_EVALUATION_V1.json",
    "m05_history": f"{PREFIX}/results/E19_M05_SIM13_KINEMATIC_HISTORY_V1.csv",
    "m06": f"{PREFIX}/results/E19_M06_HALF_SINE_EXECUTION_REGISTER_V1.json",
    "m06_history": f"{PREFIX}/results/E19_M06_HALF_SINE_SAVED_HISTORY_V1.csv",
    "m07_arm": f"{PREFIX}/results/E19_M07_ARM_ONLY_BASE_REACTION_SUMMARY_V1.json",
    "m07_arm_history": f"{PREFIX}/results/E19_M07_ARM_ONLY_BASE_REACTION_HISTORY_V1.csv",
    "m07_rigid": f"{PREFIX}/results/E19_M07_SIM15_RIGID_CAPTURE_RECOMPUTE_V1.json",
    "register": f"{PREFIX}/results/E19_DIAGNOSTIC_EVALUATION_REGISTER_V1.json",
    "gate": f"{PREFIX}/results/E19_DIAGNOSTIC_EVALUATION_GATE_V1.json",
    "output_manifest": f"{PREFIX}/results/E19_OUTPUT_MANIFEST_V1.json",
}

M01_SOURCE = (
    "30_simulation/e18_b601_mission_input_branches/02_candidates/"
    "M01_HELD_STOW_TO_RELEASE_CLEAR_QUINTIC_V1.csv"
)
M05_SOURCE = (
    "30_simulation/e18_b601_mission_input_branches/02_candidates/"
    "M05_22_TARGET_STATE_BRANCHES_V1.json"
)
M07_SOURCE = (
    "30_simulation/e17_b601_mission_trajectory_candidates/results/candidates/"
    "M07_22_ARM_ONLY_QUINTIC_V1.csv"
)
SIM15_BASELINE = (
    "30_simulation/sim_15_m5_geometry_gated_grasping/evidence/"
    "SIM15_DIAGNOSTIC_BASELINE_V1.json"
)

EXPECTED_SOURCE_IDS = {
    "mechanical_loop_v2_gate",
    "e18_authority",
    "e18_gate",
    "e18_manifest",
    "e18_validation",
    "e18_m01_contract",
    "e18_m05_contract",
    "e18_m06_contract",
    "e18_m07_contract",
    "e18_m01_candidate",
    "e18_m05_branches",
    "e18_m06_matrix",
    "e18_m07_branches",
    "e17_m07_candidate",
    "accepted_urdf",
    "mass_budget_v1",
    "system_mass_properties_v3",
    "sim05_dynamics",
    "sim05_b601_model",
    "common_rigid_body",
    "sim13_backend",
    "sim13_randomization",
    "sim13_action",
    "sim13_config",
    "sim15_baseline",
    "sim15_gate",
    "sim15_binding_receipt",
    "sim15_generator",
    "sim15_authority",
    "sim15_contact_gate",
    "sim15_env",
    "sim15_joint_loads",
    "sim15_rigid_capture",
}

EXPECTED_RESULT_PATHS = {
    FILES["m01"],
    FILES["m01_history"],
    FILES["m05"],
    FILES["m05_history"],
    FILES["m06"],
    FILES["m06_history"],
    FILES["m07_arm"],
    FILES["m07_arm_history"],
    FILES["m07_rigid"],
}

EXPECTED_CONTROLLED_PATHS = {
    f"{PREFIX}/README.md",
    FILES["authority"],
    FILES["config"],
    f"{PREFIX}/docs/preregistration.md",
    f"{PREFIX}/docs/method_and_limitations.md",
    f"{PREFIX}/src/build_e19_diagnostics.py",
    f"{PREFIX}/tests/validate_e19_diagnostics.py",
    *EXPECTED_RESULT_PATHS,
    FILES["input_manifest"],
    FILES["register"],
    FILES["gate"],
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def canonical_sha(value: Any) -> str:
    data = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest().upper()


def read_json(relative: str) -> Any:
    return json.loads((ROOT / relative).read_text(encoding="utf-8-sig"))


def read_yaml(relative: str) -> Any:
    return yaml.safe_load((ROOT / relative).read_text(encoding="utf-8-sig"))


def read_csv(relative: str) -> list[dict[str, str]]:
    with (ROOT / relative).open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def all_none(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(all_none(item) for item in value.values())
    if isinstance(value, list):
        return all(all_none(item) for item in value)
    return value is None


def finite_tree(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(finite_tree(item) for item in value.values())
    if isinstance(value, list):
        return all(finite_tree(item) for item in value)
    if isinstance(value, float):
        return math.isfinite(value)
    return True


def close(a: float, b: float, *, atol: float = 1.0e-12, rtol: float = 1.0e-12) -> bool:
    return math.isclose(float(a), float(b), abs_tol=atol, rel_tol=rtol)


def csv_false(value: Any) -> bool:
    return str(value).strip().lower() == "false"


def manifest_item_matches(item: Mapping[str, Any]) -> bool:
    try:
        path = ROOT / str(item["path"])
        expected_hash = item.get("sha256", item.get("actual_sha256"))
        return (
            path.is_file()
            and sha256_file(path) == expected_hash
            and path.stat().st_size == int(item["bytes"])
        )
    except (KeyError, OSError, TypeError, ValueError):
        return False


def joint_limits() -> tuple[np.ndarray, np.ndarray]:
    urdf = ROOT / "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
    root = ET.parse(urdf).getroot()
    lower, upper = [], []
    for index in range(1, 7):
        node = root.find(f"./joint[@name='joint{index}']/limit")
        if node is None:
            raise ValueError(f"missing joint{index} limit")
        lower.append(float(node.attrib["lower"]))
        upper.append(float(node.attrib["upper"]))
    return np.asarray(lower), np.asarray(upper)


def source_trajectory_safe(
    rows: list[dict[str, str]], summary: Mapping[str, Any], duration: float, count: int
) -> bool:
    try:
        if len(rows) != count:
            return False
        times = np.asarray([float(row["t_s"]) for row in rows])
        if not close(times[0], 0.0) or not close(times[-1], duration):
            return False
        if np.max(np.abs(np.diff(times) - 0.01)) > 2.0e-12:
            return False
        q = np.asarray(
            [[float(row[f"joint{i}_q_rad"]) for i in range(1, 7)] for row in rows]
        )
        dq = np.asarray(
            [[float(row[f"joint{i}_dq_rad_s"]) for i in range(1, 7)] for row in rows]
        )
        ddq = np.asarray(
            [[float(row[f"joint{i}_ddq_rad_s2"]) for i in range(1, 7)] for row in rows]
        )
        q0, q1 = q[0], q[-1]
        q_ref, dq_ref, ddq_ref = [], [], []
        for time in times:
            x = float(time) / duration
            s = 10.0 * x**3 - 15.0 * x**4 + 6.0 * x**5
            sd = (30.0 * x**2 - 60.0 * x**3 + 30.0 * x**4) / duration
            sdd = (60.0 * x - 180.0 * x**2 + 120.0 * x**3) / duration**2
            delta = q1 - q0
            q_ref.append(q0 + delta * s)
            dq_ref.append(delta * sd)
            ddq_ref.append(delta * sdd)
        audit = summary["trajectory_audit"]
        lower, upper = joint_limits()
        calculated_margin = float(np.min(np.minimum(q - lower, upper - q)))
        return (
            np.max(np.abs(q - np.asarray(q_ref))) <= 3.0e-12
            and np.max(np.abs(dq - np.asarray(dq_ref))) <= 3.0e-12
            and np.max(np.abs(ddq - np.asarray(ddq_ref))) <= 3.0e-12
            and np.max(np.abs(dq[[0, -1]])) <= 1.0e-12
            and np.max(np.abs(ddq[[0, -1]])) <= 1.0e-12
            and calculated_margin > 0.0
            and np.allclose(q0, audit["q0_rad"], atol=1.0e-12, rtol=0.0)
            and np.allclose(q1, audit["q1_rad"], atol=1.0e-12, rtol=0.0)
            and close(calculated_margin, audit["minimum_joint_limit_margin_rad"])
            and audit["sample_count"] == count
            and close(audit["duration_s"], duration)
            and close(audit["sample_period_s"], 0.01)
            and max(
                audit["max_abs_q_reconstruction_error_rad"],
                audit["max_abs_dq_reconstruction_error_rad_s"],
                audit["max_abs_ddq_reconstruction_error_rad_s2"],
            )
            <= 3.0e-12
        )
    except (KeyError, TypeError, ValueError, ArithmeticError):
        return False


def arm_lane_safe(
    summary: Mapping[str, Any],
    history: list[dict[str, str]],
    source_rows: list[dict[str, str]],
    lane_id: str,
    duration: float,
    count: int,
) -> bool:
    try:
        if summary["schema"] != f"E19_{lane_id}_BASE_REACTION_SUMMARY_V1":
            return False
        if summary["lane_id"] != lane_id or summary["authority_class"] != "NON_RELEASE_DIAGNOSTIC_EXECUTION_ONLY":
            return False
        if not source_trajectory_safe(source_rows, summary, duration, count):
            return False
        if len(history) != count:
            return False
        times = np.asarray([float(row["t_s"]) for row in history])
        if not close(times[0], 0.0) or not close(times[-1], duration):
            return False
        if np.max(np.abs(np.diff(times) - 0.01)) > 2.0e-12:
            return False
        attitude = np.asarray([float(row["base_attitude_deviation_deg"]) for row in history])
        translation = np.asarray(
            [[float(row[f"base_{axis}_m"]) for axis in "xyz"] for row in history]
        )
        angular_rate = np.asarray(
            [[float(row[f"base_w{axis}_rad_s"]) for axis in "xyz"] for row in history]
        )
        quaternions = np.asarray(
            [
                [float(row[f"base_q_{component}"]) for component in ("w", "x", "y", "z")]
                for row in history
            ]
        )
        residuals = np.asarray([float(row["momentum_residual_norm_S"]) for row in history])
        reaction = summary["base_reaction"]
        solver = summary["solver"]
        return (
            np.all(np.isfinite(attitude))
            and np.all(np.isfinite(translation))
            and np.all(np.isfinite(angular_rate))
            and np.all(np.isfinite(quaternions))
            and np.all(np.isfinite(residuals))
            and close(np.max(attitude), reaction["peak_attitude_deviation_deg"], atol=1.0e-10)
            and close(attitude[-1], reaction["final_attitude_deviation_deg"], atol=1.0e-10)
            and close(np.max(np.linalg.norm(angular_rate, axis=1)), reaction["peak_base_rate_rad_s"], atol=1.0e-12)
            and close(np.max(np.linalg.norm(translation, axis=1)), reaction["peak_base_translation_m"], atol=1.0e-12)
            and np.allclose(translation[-1], reaction["final_base_translation_m"], atol=1.0e-12, rtol=0.0)
            and close(np.max(residuals), reaction["max_momentum_residual_norm_S"], atol=1.0e-15)
            and np.max(residuals) <= reaction["momentum_residual_limit"] == 1.0e-12
            and close(np.max(np.abs(np.linalg.norm(quaternions, axis=1) - 1.0)), reaction["quaternion_norm_max_error"], atol=1.0e-15)
            and reaction["acceptance_threshold_authority"] is None
            and reaction["engineering_prediction"] is False
            and solver["algorithm"] == "SIM05_RIGID_FREE_FLOATING_ZERO_MOMENTUM"
            and solver["legacy_default_path_currently_valid"] is False
            and solver["rigid_model_only"] is True
            and solver["flexible_panels_modeled"] is False
            and solver["actuator_dynamics_modeled"] is False
            and solver["mass_property_release_authority"] is False
            and summary["attached_target_propagated"] is False
            and summary["physical_stow_or_lock_confirmed"] is None
            and summary["collision_safe"] is None
            and summary["solar_keep_out_safe"] is None
            and summary["harness_safe"] is None
            and summary["hardware_motion_authorized"] is False
            and summary["released_for_mission_gate"] is False
            and all(row["authority_class"] == "NON_RELEASE_DIAGNOSTIC_EXECUTION_ONLY" for row in history)
            and all(csv_false(row["attached_target_propagated"]) for row in history)
            and all(csv_false(row["released_for_mission_gate"]) for row in history)
        )
    except (KeyError, TypeError, ValueError, ArithmeticError):
        return False


def m05_safe(summary: Mapping[str, Any], history: list[dict[str, str]]) -> bool:
    try:
        kinetic = summary["sim13_kinematic_branch"]
        static = summary["static_display_branch"]
        if len(history) != 1001:
            return False
        omega = math.radians(0.5)
        max_norm_error = 0.0
        max_analytic_error = 0.0
        for index, row in enumerate(history):
            ideal_time = index * 0.05
            observed_time = float(row["t_s"])
            if int(row["sample_index"]) != index or not close(observed_time, ideal_time, atol=2.0e-12):
                return False
            observed = np.asarray([float(row[f"target_q_{c}"]) for c in ("x", "y", "z", "w")])
            # The backend accumulates dt, so its stored time carries the expected
            # sub-picosecond floating-point drift.  Recompute the analytic
            # quaternion at that persisted time while separately checking the
            # ideal 0.05 s grid above.
            expected = np.asarray(
                [
                    0.0,
                    0.0,
                    math.sin(omega * observed_time / 2.0),
                    math.cos(omega * observed_time / 2.0),
                ]
            )
            norm_error = abs(float(np.linalg.norm(observed)) - 1.0)
            analytic_error = float(np.linalg.norm(observed - expected))
            max_norm_error = max(max_norm_error, norm_error)
            max_analytic_error = max(max_analytic_error, analytic_error)
            if not np.allclose(
                [float(row["target_x_m"]), float(row["target_y_m"]), float(row["target_z_m"])],
                [1.0, 0.0, 0.0],
                atol=1.0e-12,
                rtol=0.0,
            ):
                return False
            if not close(float(row["target_wz_rad_s"]), omega, atol=1.0e-15):
                return False
            if row["collision_safety_interpretation"] != "PROHIBITED" or row["action"] != "ABORT" or not csv_false(row["released_for_mission_gate"]):
                return False
        return (
            summary["schema"] == "E19_M05_BRANCH_EVALUATION_V1"
            and summary["authority_class"] == "NON_RELEASE_DIAGNOSTIC_EXECUTION_ONLY"
            and summary["branch_ids"] == ["SIM13_KINEMATIC_BOOTSTRAP", "SCENE_MANIFEST_STATIC_DISPLAY"]
            and summary["branch_merge_performed"] is False
            and kinetic["steps"] == 1000
            and kinetic["history_samples"] == 1001
            and close(kinetic["timestep_s"], 0.05)
            and close(kinetic["final_time_s"], 50.0)
            and close(kinetic["final_phase_deg"], 25.0, atol=1.0e-12)
            and close(kinetic["max_quaternion_norm_error"], max_norm_error, atol=1.0e-15)
            and close(kinetic["max_analytic_quaternion_error"], max_analytic_error, atol=1.0e-15)
            and max_norm_error <= 1.0e-12
            and max_analytic_error <= 1.0e-12
            and kinetic["randomization_enabled"] is False
            and kinetic["action"] == "ABORT"
            and kinetic["contact_computed"] is False
            and kinetic["collision_detected_false_is_safety_credit"] is False
            and kinetic["production_binding_valid"] is False
            and static["R_TS_orthogonality_residual"] <= 1.0e-12
            and close(static["R_TS_determinant"], 1.0, atol=1.0e-12)
            and static["capture_point_transform_residual_m"] <= 1.0e-12
            and static["target_com_transform_residual_m"] <= 1.0e-12
            and static["capture_time_s_semantics"] == "STATIC_DISPLAY_PARAMETER_NOT_MISSION_EPOCH"
            and static["time_propagation_performed"] is False
            and static["target_twist_introduced"] is False
            and all_none(summary["required_physical_inputs"])
            and summary["released_for_mission_gate"] is False
        )
    except (KeyError, TypeError, ValueError, ArithmeticError):
        return False


def m06_safe(summary: Mapping[str, Any], history: list[dict[str, str]]) -> bool:
    try:
        cases = summary["cases"]
        expected_grid = {
            (speed, window)
            for speed in (0.005, 0.01, 0.02, 0.03)
            for window in (5, 10, 20, 50, 100)
        }
        observed_grid = {
            (float(case["approach_speed_m_s"]), int(case["solver_contact_window_ms"]))
            for case in cases
        }
        if len(cases) != 20 or observed_grid != expected_grid or len(history) != 4020:
            return False
        by_id: dict[str, list[dict[str, str]]] = {}
        for row in history:
            by_id.setdefault(row["case_id"], []).append(row)
        max_error = 0.0
        for case in cases:
            impulse = float(case["source_impulse_N_s"])
            window_s = float(case["solver_contact_window_s"])
            window_ms = int(case["solver_contact_window_ms"])
            peak = float(case["solver_peak_force_N"])
            expected_peak = math.pi * impulse / (2.0 * window_s)
            if not close(window_s, window_ms / 1000.0, atol=1.0e-15):
                return False
            if not close(peak, expected_peak, atol=2.0e-13):
                return False
            if not close(case["expected_peak_force_N"], expected_peak, atol=2.0e-13):
                return False
            if case["peak_formula_abs_error_N"] > 2.0e-12:
                return False
            if case["relative_impulse_error"] >= 1.0e-8:
                return False
            if case["endpoint_max_abs_amplitude_N"] > 1.0e-11:
                return False
            if case["midpoint_peak_abs_error_N"] > 1.0e-11:
                return False
            if case["Fpeak_Tc_over_J_minus_pi_over_2"] > 1.0e-12:
                return False
            if case["standard_uncertainty_N_s"] is not None:
                return False
            if case["classification"] != "SOLVER_STIMULUS_PROXY_NOT_HARDWARE_CONTACT" or case["physical_contact_interpretation"] is not False:
                return False
            max_error = max(max_error, float(case["relative_impulse_error"]))
            rows = by_id.get(case["case_id"], [])
            if len(rows) != 201:
                return False
            for index, row in enumerate(rows):
                t = window_s * index / 200.0
                expected_force = peak * math.sin(math.pi * t / window_s)
                expected_cumulative = peak * window_s / math.pi * (1.0 - math.cos(math.pi * t / window_s))
                if int(row["sample_index"]) != index or not close(float(row["t_s"]), t, atol=2.0e-15):
                    return False
                if not close(float(row["solver_stimulus_amplitude_N"]), expected_force, atol=2.0e-12):
                    return False
                if not close(float(row["analytic_cumulative_impulse_N_s"]), expected_cumulative, atol=2.0e-14):
                    return False
                if row["stimulus_role"] != "SOLVER_STIMULUS_PROXY_NOT_HARDWARE_CONTACT" or not csv_false(row["released_for_mission_gate"]):
                    return False
        return (
            summary["schema"] == "E19_M06_HALF_SINE_EXECUTION_REGISTER_V1"
            and summary["authority_class"] == "NON_RELEASE_DIAGNOSTIC_EXECUTION_ONLY"
            and summary["case_count"] == 20
            and summary["grid_unique"] is True
            and summary["high_resolution_samples_per_case"] == 10001
            and summary["saved_samples_per_case"] == 201
            and close(summary["max_relative_impulse_error"], max_error, atol=1.0e-18)
            and all_none(summary["physical_contact_and_lock"])
            and summary["six_dimensional_impulse_synthesized"] is False
            and summary["hardware_force_credit"] is False
            and summary["released_for_mission_gate"] is False
        )
    except (KeyError, TypeError, ValueError, ArithmeticError, ZeroDivisionError):
        return False


def m07_rigid_safe(value: Mapping[str, Any], baseline: Mapping[str, Any]) -> bool:
    try:
        source_cases = {
            case["case_id"]: case
            for case in baseline["capture_envelope"]["cases"]
            if case["anchor_id"] == "ANCHOR_22KG_0P5DPS"
        }
        cases = value["cases"]
        if len(cases) != 4 or {case["approach_speed_m_s"] for case in cases} != {0.005, 0.01, 0.02, 0.03}:
            return False
        for case in cases:
            source = source_cases[case["case_id"]]
            if any(case[key] != source[key] for key in ("input_sha256", "solver_sha256", "output_sha256")):
                return False
            if not close(case["total_mass_kg"], 51.081436764691, atol=1.0e-12):
                return False
            if case["linear_momentum_residual_norm_kg_m_s"] >= 1.0e-11 or case["angular_momentum_residual_norm_kg_m2_s"] >= 1.0e-11:
                return False
            if case["kinetic_energy_after_J"] > case["kinetic_energy_before_J"] + 1.0e-15:
                return False
            if not close(case["plastic_energy_loss_J"], case["kinetic_energy_before_J"] - case["kinetic_energy_after_J"], atol=1.0e-15):
                return False
            if case["combined_inertia_symmetric"] is not True or case["combined_inertia_min_eigenvalue_kg_m2"] <= 0.0:
                return False
            if case["service_com_linear_impulse_magnitude_N_s"] <= 0.0 or case["m06_scalar_source_impulse_N_s_separate_model"] <= 0.0:
                return False
            if not close(
                case["m06_to_sim15_service_impulse_ratio_nonmergeable"],
                case["m06_scalar_source_impulse_N_s_separate_model"] / case["service_com_linear_impulse_magnitude_N_s"],
            ):
                return False
            if case["model_difference_is_measurement_uncertainty"] is not False:
                return False
            if case["physical_contact_computed"] is not False or case["engineering_prediction"] is not False:
                return False
            if any(case[key] is not None for key in ("contact_duration_s", "contact_force_N", "contact_pressure_Pa")):
                return False
        masses = value["C08_diagnostic_mass_branches"]
        return (
            value["schema"] == "E19_M07_SIM15_RIGID_CAPTURE_RECOMPUTE_V1"
            and value["authority_class"] == "NON_RELEASE_DIAGNOSTIC_EXECUTION_ONLY"
            and value["sim15_baseline_recomputed_from_current_hash_bound_code"] is True
            and value["bound_baseline_sha256"] == value["recomputed_baseline_sha256"] == URDF_SHA256.replace(URDF_SHA256, "4D6B08F5F8DD6A45CC1CDCFBF2A04CEACF758ABAB1350FF0BE6742DCD4E85C1F")
            and sha256_file(ROOT / SIM15_BASELINE) == value["bound_baseline_sha256"]
            and value["case_count"] == 4
            and all(value["e18_required_0p01_case"].values())
            and len(masses) == 2
            and all(item["standard_uncertainty_kg"] is None and item["released"] is False for item in masses)
            and value["C08_branch_selection_performed"] is False
            and value["C08_branch_averaging_performed"] is False
            and close(value["C08_branch_delta_kg_not_uncertainty"], abs(masses[1]["mass_kg"] - masses[0]["mass_kg"]))
            and value["selected_post_capture_model_branch"] is None
            and value["locked_transform_gripper_to_target"] is None
            and value["contact_normals"] is None
            and value["released_mass_kg"] is None
            and value["released_cg_m"] is None
            and value["released_inertia_kg_m2"] is None
            and value["attached_target_recovery_propagated"] is False
            and value["physical_contact_authority"] is False
            and value["released_for_mission_gate"] is False
        )
    except (KeyError, TypeError, ValueError, ArithmeticError, ZeroDivisionError):
        return False


def gate_safe(bundle: Mapping[str, Any]) -> bool:
    """Single fail-closed predicate for baseline and every deepcopy mutation."""

    try:
        authority = bundle["authority"]
        config = bundle["config"]
        input_manifest = bundle["input_manifest"]
        register = bundle["register"]
        gate = bundle["gate"]
        output_manifest = bundle["output_manifest"]

        if not finite_tree(bundle):
            return False
        if authority["schema"] != "E19_B601_ISOLATED_DIAGNOSTIC_AUTHORITY_CONTRACT_V1" or authority["authority_class"] != "NON_RELEASE_DIAGNOSTIC_EXECUTION_ONLY":
            return False
        if authority["immutable_asset"] != {
            "path": "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
            "sha256": URDF_SHA256,
            "modification": "FORBIDDEN",
        }:
            return False
        if set(authority["execution_lanes"]) != {"M01", "M05_SIM13", "M05_STATIC", "M06", "M07_ARM_ONLY", "M07_SIM15"}:
            return False
        if any(lane["cross_lane_state_input"] is not None for lane in authority["execution_lanes"].values()):
            return False
        if authority["execution_lanes"]["M07_ARM_ONLY"]["attached_target_propagated"] is not False:
            return False
        for key in (
            "cross_lane_chaining_allowed",
            "branch_merging_allowed",
            "mission_segment_execution",
            "hardware_command_emitted",
            "physical_contact_computed",
            "production_dynamics_claimed",
            "cad_or_mesh_generation_authorized",
            "unknown_zero_fill_allowed",
            "testing_pass_grants_authority",
            "next_stage_authorized",
            "release_credit",
        ):
            if authority[key] is not False:
                return False
        if authority["released_segments"] != 0:
            return False

        if config["schema"] != "E19_ISOLATED_DIAGNOSTIC_CAMPAIGN_V1" or config["units_policy"] != "STRICT_SI_AT_ALL_EXECUTION_BOUNDARIES":
            return False
        if config["quaternion_conventions"] != {"sim05_base_history": "wxyz", "sim13_target_history": "xyzw"}:
            return False
        if any(config["global_invariants"].values()):
            return False
        if config["M01"]["sample_count"] != 1151 or not close(config["M01"]["duration_s"], 11.5) or config["M01"]["physical_release_execution"] is not False:
            return False
        if (
            config["M05"]["maximum_steps"] != 1000
            or not close(config["M05"]["timestep_s"], 0.05)
            or not close(config["M05"]["diagnostic_horizon_s"], 50.0)
            or config["M05"]["randomization_enabled"] is not False
            or config["M05"]["action"] != "ABORT"
            or config["M05"]["branches_merge_allowed"] is not False
        ):
            return False
        if config["M06"]["expected_case_count"] != 20 or config["M06"]["physical_contact_interpretation"] is not False:
            return False
        if config["M07"]["arm_only_sample_count"] != 451 or config["M07"]["attached_target_propagated"] is not False:
            return False
        if any(config["M07"][key] is not None for key in ("selected_post_capture_model_branch", "locked_transform_gripper_to_target", "released_mass_cg_inertia")):
            return False

        records = input_manifest["records"]
        if input_manifest["schema"] != "E19_INPUT_MANIFEST_V1" or input_manifest["record_count"] != len(records) != 0:
            return False
        if len(records) != len(EXPECTED_SOURCE_IDS) or {item["source_id"] for item in records} != EXPECTED_SOURCE_IDS:
            return False
        if any(item["status"] != "EXACT_HASH_MATCH" or item["expected_sha256"] != item["actual_sha256"] or not manifest_item_matches(item) for item in records):
            return False
        if input_manifest["source_set_sha256"] != canonical_sha(records) or input_manifest["all_exact_hash_match"] is not True:
            return False
        if input_manifest["accepted_urdf_sha256"] != URDF_SHA256 or input_manifest["accepted_urdf_modified"] is not False:
            return False
        if input_manifest["cross_lane_state_input_count"] != 0 or input_manifest["release_credit"] is not False:
            return False
        if sha256_file(ROOT / authority["immutable_asset"]["path"]) != URDF_SHA256:
            return False

        if not arm_lane_safe(bundle["m01"], bundle["m01_history"], bundle["m01_source"], "M01", 11.5, 1151):
            return False
        if not arm_lane_safe(bundle["m07_arm"], bundle["m07_arm_history"], bundle["m07_source"], "M07_ARM_ONLY", 4.5, 451):
            return False
        if not m05_safe(bundle["m05"], bundle["m05_history"]):
            return False
        if not m06_safe(bundle["m06"], bundle["m06_history"]):
            return False
        if not m07_rigid_safe(bundle["m07_rigid"], bundle["sim15_baseline"]):
            return False

        if register["schema"] != "E19_DIAGNOSTIC_EVALUATION_REGISTER_V1" or register["authority_class"] != "NON_RELEASE_DIAGNOSTIC_EXECUTION_ONLY":
            return False
        if register["result_count"] != len(register["results"]) or {item["path"] for item in register["results"]} != EXPECTED_RESULT_PATHS:
            return False
        if any(not manifest_item_matches(item) for item in register["results"]):
            return False
        if register["input_manifest"]["path"] != FILES["input_manifest"] or register["input_manifest"]["sha256"] != sha256_file(ROOT / FILES["input_manifest"]):
            return False
        if set(register["lane_execution"]) != {"M01", "M05_SIM13", "M05_STATIC", "M06", "M07_ARM_ONLY", "M07_SIM15"} or register["lane_execution_count"] != 6:
            return False
        if any(register[key] is not False for key in ("cross_lane_chaining_performed", "branch_merging_performed", "mission_timeline_created", "attached_target_recovery_propagated", "end_to_end_diagnostic_dynamics_ready", "physical_contact_ready", "attached_target_recovery_ready", "mission_sequence_executable", "production_dynamics_ready", "cad_or_mesh_generated", "accepted_urdf_modified", "release_credit", "next_stage_authorized")):
            return False
        if register["isolated_numeric_diagnostic_execution_ready"] is not True or register["released_segments"] != 0:
            return False
        null_ledger = register["null_hold_ledger"]
        if null_ledger["schema"] != "E19_NULL_HOLD_LEDGER_V1" or null_ledger["unknown_zero_fill_performed"] is not False:
            return False
        if not all_none({key: value for key, value in null_ledger.items() if key not in {"schema", "unknown_zero_fill_performed"}}):
            return False
        observations = register["diagnostic_observations"]
        if not close(observations["M01_peak_base_attitude_deviation_deg"], bundle["m01"]["base_reaction"]["peak_attitude_deviation_deg"]):
            return False
        if not close(observations["M07_arm_only_peak_base_attitude_deviation_deg"], bundle["m07_arm"]["base_reaction"]["peak_attitude_deviation_deg"]):
            return False
        if observations["no_base_attitude_acceptance_threshold_authority"] is not True or observations["M06_vs_Sim15_impulses_are_separate_models"] is not True:
            return False

        if gate["schema"] != "E19_ISOLATED_NONRELEASE_DIAGNOSTIC_GATE_V1" or gate["gate"] != "HOLD":
            return False
        if gate["criteria_total"] != len(gate["criteria"]) or gate["criteria_total"] != 17 or gate["criteria_observed"] != 17:
            return False
        if any(item["observed"] is not True or item["state"] != "PASS_DIAGNOSTIC_ONLY" or item["release_credit"] is not False for item in gate["criteria"]):
            return False
        if [item["id"] for item in gate["criteria"]] != [f"E19-G{i:02d}" for i in range(1, 18)]:
            return False
        if gate["input_manifest"] != register["input_manifest"]:
            return False
        if gate["result_register"]["path"] != FILES["register"] or gate["result_register"]["sha256"] != sha256_file(ROOT / FILES["register"]):
            return False
        for key in (
            "cross_lane_chaining_performed",
            "end_to_end_diagnostic_dynamics_ready",
            "physical_contact_ready",
            "attached_target_recovery_ready",
            "mission_release_ready",
            "production_dynamics_ready",
            "hardware_motion_ready",
            "mechanical_design_released",
            "flight_qualification_ready",
            "testing_pass_grants_authority",
            "next_stage_authorized",
            "release_credit",
        ):
            if gate[key] is not False:
                return False
        if gate["diagnostic_execution_verdict"] != "PASS" or gate["isolated_numeric_diagnostic_execution_ready"] is not True:
            return False
        if gate["four_mission_segments_consumed_as_independent_lanes"] is not True or gate["six_isolated_lane_evaluations_executed"] is not True:
            return False
        if gate["released_segments"] != 0 or gate["verdict"] != "E19_ISOLATED_NUMERIC_REPRODUCIBILITY_CLOSED__END_TO_END_PHYSICAL_CONTACT_ATTACHED_RECOVERY_AND_MISSION_RELEASE_HOLD":
            return False

        artifacts = output_manifest["artifacts"]
        if output_manifest["schema"] != "E19_OUTPUT_MANIFEST_V1" or output_manifest["artifact_count"] != len(artifacts):
            return False
        if {item["path"] for item in artifacts} != EXPECTED_CONTROLLED_PATHS or any(not manifest_item_matches(item) for item in artifacts):
            return False
        if output_manifest["artifact_set_sha256"] != canonical_sha(artifacts):
            return False
        if output_manifest["input_source_set_sha256"] != input_manifest["source_set_sha256"] or output_manifest["accepted_urdf_sha256"] != URDF_SHA256:
            return False
        if output_manifest["validation_report_excluded"] is not True or any(item["path"].endswith("E19_VALIDATION_V1.json") for item in artifacts):
            return False
        if output_manifest["gate"] != "HOLD" or output_manifest["released_segments"] != 0 or output_manifest["next_stage_authorized"] is not False or output_manifest["release_credit"] is not False:
            return False
        forbidden = {".step", ".stp", ".stl", ".obj", ".glb", ".gltf", ".urdf"}
        if any(suffix in forbidden for suffix in bundle["package_suffixes"]):
            return False
        return True
    except (KeyError, IndexError, TypeError, ValueError, OSError, ArithmeticError, ET.ParseError):
        return False


def main() -> None:
    for relative in FILES.values():
        if not (ROOT / relative).is_file():
            raise FileNotFoundError(relative)

    bundle: dict[str, Any] = {
        "authority": read_yaml(FILES["authority"]),
        "config": read_yaml(FILES["config"]),
        "input_manifest": read_json(FILES["input_manifest"]),
        "m01": read_json(FILES["m01"]),
        "m01_history": read_csv(FILES["m01_history"]),
        "m01_source": read_csv(M01_SOURCE),
        "m05": read_json(FILES["m05"]),
        "m05_history": read_csv(FILES["m05_history"]),
        "m06": read_json(FILES["m06"]),
        "m06_history": read_csv(FILES["m06_history"]),
        "m07_arm": read_json(FILES["m07_arm"]),
        "m07_arm_history": read_csv(FILES["m07_arm_history"]),
        "m07_source": read_csv(M07_SOURCE),
        "m07_rigid": read_json(FILES["m07_rigid"]),
        "sim15_baseline": read_json(SIM15_BASELINE),
        "register": read_json(FILES["register"]),
        "gate": read_json(FILES["gate"]),
        "output_manifest": read_json(FILES["output_manifest"]),
        "package_suffixes": [path.suffix.lower() for path in PACKAGE.rglob("*") if path.is_file()],
    }

    checks: list[dict[str, Any]] = []

    def check(identifier: str, predicate: bool, evidence: Any) -> None:
        checks.append({"id": identifier, "pass": bool(predicate), "evidence": evidence})

    for name, relative in FILES.items():
        path = ROOT / relative
        check(f"FILE_{name.upper()}", path.is_file() and path.stat().st_size > 0, relative)
    check("ACCEPTED_URDF_HASH", sha256_file(ROOT / bundle["authority"]["immutable_asset"]["path"]) == URDF_SHA256, URDF_SHA256)
    check("AUTHORITY_FAIL_CLOSED", bundle["authority"]["authority_class"] == "NON_RELEASE_DIAGNOSTIC_EXECUTION_ONLY" and bundle["authority"]["released_segments"] == 0, bundle["authority"]["authority_class"])
    check("CONFIG_STRICT_SI", bundle["config"]["units_policy"] == "STRICT_SI_AT_ALL_EXECUTION_BOUNDARIES", bundle["config"]["units_policy"])
    check("INPUT_MANIFEST_33_SOURCES", len(bundle["input_manifest"]["records"]) == len(EXPECTED_SOURCE_IDS), len(bundle["input_manifest"]["records"]))
    check("INPUT_HASH_CLOSURE", all(manifest_item_matches(item) for item in bundle["input_manifest"]["records"]), bundle["input_manifest"]["source_set_sha256"])
    check("M01_SOURCE_AND_BASE_REACTION", arm_lane_safe(bundle["m01"], bundle["m01_history"], bundle["m01_source"], "M01", 11.5, 1151), bundle["m01"]["base_reaction"])
    check("M05_KINEMATIC_AND_STATIC_BRANCHES", m05_safe(bundle["m05"], bundle["m05_history"]), bundle["m05"]["status"])
    check("M06_20_EQUAL_IMPULSE_CASES", m06_safe(bundle["m06"], bundle["m06_history"]), {"cases": bundle["m06"]["case_count"], "max_relative_error": bundle["m06"]["max_relative_impulse_error"]})
    check("M07_ARM_ONLY_BASE_REACTION", arm_lane_safe(bundle["m07_arm"], bundle["m07_arm_history"], bundle["m07_source"], "M07_ARM_ONLY", 4.5, 451), bundle["m07_arm"]["base_reaction"])
    check("M07_SIM15_RECOMPUTE", m07_rigid_safe(bundle["m07_rigid"], bundle["sim15_baseline"]), bundle["m07_rigid"]["status"])
    check("RESULT_REGISTER_HASH_CLOSURE", all(manifest_item_matches(item) for item in bundle["register"]["results"]), bundle["register"]["result_count"])
    check("NULL_HOLD_LEDGER", all_none({key: value for key, value in bundle["register"]["null_hold_ledger"].items() if key not in {"schema", "unknown_zero_fill_performed"}}), "all physical UNKNOWN leaves remain null")
    check("GATE_17_OF_17_HOLD", bundle["gate"]["criteria_observed"] == bundle["gate"]["criteria_total"] == 17 and bundle["gate"]["gate"] == "HOLD", bundle["gate"]["verdict"])
    check("OUTPUT_MANIFEST_HASH_CLOSURE", all(manifest_item_matches(item) for item in bundle["output_manifest"]["artifacts"]), bundle["output_manifest"]["artifact_count"])
    check("VALIDATION_EXCLUDED_FROM_MANIFEST", bundle["output_manifest"]["validation_report_excluded"] is True and FILES.get("validation") is None, bundle["output_manifest"]["scope"])
    check("UNIFIED_GATE_SAFE_BASELINE", gate_safe(bundle), "all persisted artifacts and boundary semantics")

    mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("NC-01_AUTH_URDF_HASH", lambda b: b["authority"]["immutable_asset"].__setitem__("sha256", "0" * 64)),
        ("NC-02_AUTH_URDF_MODIFIABLE", lambda b: b["authority"]["immutable_asset"].__setitem__("modification", "ALLOWED")),
        ("NC-03_AUTH_CROSS_LANE", lambda b: b["authority"].__setitem__("cross_lane_chaining_allowed", True)),
        ("NC-04_AUTH_BRANCH_MERGE", lambda b: b["authority"].__setitem__("branch_merging_allowed", True)),
        ("NC-05_AUTH_MISSION_EXECUTION", lambda b: b["authority"].__setitem__("mission_segment_execution", True)),
        ("NC-06_AUTH_HARDWARE_COMMAND", lambda b: b["authority"].__setitem__("hardware_command_emitted", True)),
        ("NC-07_AUTH_PHYSICAL_CONTACT", lambda b: b["authority"].__setitem__("physical_contact_computed", True)),
        ("NC-08_AUTH_PRODUCTION", lambda b: b["authority"].__setitem__("production_dynamics_claimed", True)),
        ("NC-09_AUTH_CAD", lambda b: b["authority"].__setitem__("cad_or_mesh_generation_authorized", True)),
        ("NC-10_AUTH_ZERO_FILL", lambda b: b["authority"].__setitem__("unknown_zero_fill_allowed", True)),
        ("NC-11_AUTH_NEXT_STAGE", lambda b: b["authority"].__setitem__("next_stage_authorized", True)),
        ("NC-12_AUTH_RELEASE_CREDIT", lambda b: b["authority"].__setitem__("release_credit", True)),
        ("NC-13_AUTH_RELEASED_SEGMENT", lambda b: b["authority"].__setitem__("released_segments", 1)),
        ("NC-14_AUTH_STATE_TRANSFER", lambda b: b["authority"]["execution_lanes"]["M05_SIM13"].__setitem__("cross_lane_state_input", "M01.final")),
        ("NC-15_CONFIG_UNITS", lambda b: b["config"].__setitem__("units_policy", "MIXED")),
        ("NC-16_CONFIG_QUAT_ORDER", lambda b: b["config"]["quaternion_conventions"].__setitem__("sim13_target_history", "wxyz")),
        ("NC-17_CONFIG_CROSS_LANE", lambda b: b["config"]["global_invariants"].__setitem__("cross_lane_chaining_allowed", True)),
        ("NC-18_CONFIG_M01_SAMPLES", lambda b: b["config"]["M01"].__setitem__("sample_count", 1150)),
        ("NC-19_CONFIG_M01_DURATION", lambda b: b["config"]["M01"].__setitem__("duration_s", 1.15)),
        ("NC-20_CONFIG_RELEASE", lambda b: b["config"]["M01"].__setitem__("physical_release_execution", True)),
        ("NC-21_CONFIG_M05_DT", lambda b: b["config"]["M05"].__setitem__("timestep_s", 0.5)),
        ("NC-22_CONFIG_RANDOMIZE", lambda b: b["config"]["M05"].__setitem__("randomization_enabled", True)),
        ("NC-23_CONFIG_M05_MERGE", lambda b: b["config"]["M05"].__setitem__("branches_merge_allowed", True)),
        ("NC-24_CONFIG_M06_COUNT", lambda b: b["config"]["M06"].__setitem__("expected_case_count", 19)),
        ("NC-25_CONFIG_M06_PHYSICAL", lambda b: b["config"]["M06"].__setitem__("physical_contact_interpretation", True)),
        ("NC-26_CONFIG_M07_ATTACH", lambda b: b["config"]["M07"].__setitem__("attached_target_propagated", True)),
        ("NC-27_CONFIG_M07_SELECT", lambda b: b["config"]["M07"].__setitem__("selected_post_capture_model_branch", "C08-B")),
        ("NC-28_CONFIG_M07_TRANSFORM", lambda b: b["config"]["M07"].__setitem__("locked_transform_gripper_to_target", [0, 0, 0])),
        ("NC-29_INPUT_COUNT", lambda b: b["input_manifest"].__setitem__("record_count", 32)),
        ("NC-30_INPUT_EXPECTED_HASH", lambda b: b["input_manifest"]["records"][0].__setitem__("expected_sha256", "F" * 64)),
        ("NC-31_INPUT_ACTUAL_HASH", lambda b: b["input_manifest"]["records"][0].__setitem__("actual_sha256", "F" * 64)),
        ("NC-32_INPUT_MATCH_FLAG", lambda b: b["input_manifest"].__setitem__("all_exact_hash_match", False)),
        ("NC-33_INPUT_STATE_COUNT", lambda b: b["input_manifest"].__setitem__("cross_lane_state_input_count", 1)),
        ("NC-34_INPUT_RELEASE", lambda b: b["input_manifest"].__setitem__("release_credit", True)),
        ("NC-35_M01_SAMPLE_COUNT", lambda b: b["m01"]["trajectory_audit"].__setitem__("sample_count", 1150)),
        ("NC-36_M01_MOMENTUM", lambda b: b["m01"]["base_reaction"].__setitem__("max_momentum_residual_norm_S", 1.0e-6)),
        ("NC-37_M01_PHYSICAL_STOW", lambda b: b["m01"].__setitem__("physical_stow_or_lock_confirmed", True)),
        ("NC-38_M01_COLLISION_CREDIT", lambda b: b["m01"].__setitem__("collision_safe", True)),
        ("NC-39_M01_HISTORY_ATTACH", lambda b: b["m01_history"][0].__setitem__("attached_target_propagated", "true")),
        ("NC-40_M01_NAN", lambda b: b["m01"]["base_reaction"].__setitem__("peak_base_rate_rad_s", float("nan"))),
        ("NC-41_M05_MERGED", lambda b: b["m05"].__setitem__("branch_merge_performed", True)),
        ("NC-42_M05_QUAT_ERROR", lambda b: b["m05"]["sim13_kinematic_branch"].__setitem__("max_analytic_quaternion_error", 1.0e-4)),
        ("NC-43_M05_COLLISION_CREDIT", lambda b: b["m05"]["sim13_kinematic_branch"].__setitem__("collision_detected_false_is_safety_credit", True)),
        ("NC-44_M05_EPOCH_FILL", lambda b: b["m05"]["required_physical_inputs"].__setitem__("epoch", 0.0)),
        ("NC-45_M05_STATIC_PROPAGATED", lambda b: b["m05"]["static_display_branch"].__setitem__("time_propagation_performed", True)),
        ("NC-46_M05_HISTORY_QUAT", lambda b: b["m05_history"][10].__setitem__("target_q_w", "0.0")),
        ("NC-47_M06_DROP_CASE", lambda b: b["m06"]["cases"].pop()),
        ("NC-48_M06_PHYSICAL_FORCE", lambda b: b["m06"]["physical_contact_and_lock"].__setitem__("contact_force_N", 0.0)),
        ("NC-49_M06_ZERO_UNCERTAINTY", lambda b: b["m06"]["cases"][0].__setitem__("standard_uncertainty_N_s", 0.0)),
        ("NC-50_M06_PHYSICAL_INTERPRET", lambda b: b["m06"]["cases"][0].__setitem__("physical_contact_interpretation", True)),
        ("NC-51_M06_PEAK_FORMULA", lambda b: b["m06"]["cases"][0].__setitem__("solver_peak_force_N", 1.0)),
        ("NC-52_M06_HISTORY_ROLE", lambda b: b["m06_history"][0].__setitem__("stimulus_role", "PHYSICAL_FORCE")),
        ("NC-53_M07_ARM_ATTACH", lambda b: b["m07_arm"].__setitem__("attached_target_propagated", True)),
        ("NC-54_M07_ARM_MOMENTUM", lambda b: b["m07_arm"]["base_reaction"].__setitem__("max_momentum_residual_norm_S", 1.0)),
        ("NC-55_M07_ARM_HISTORY_RELEASE", lambda b: b["m07_arm_history"][0].__setitem__("released_for_mission_gate", "true")),
        ("NC-56_SIM15_BASELINE_HASH", lambda b: b["m07_rigid"].__setitem__("recomputed_baseline_sha256", "0" * 64)),
        ("NC-57_SIM15_MOMENTUM", lambda b: b["m07_rigid"]["cases"][0].__setitem__("linear_momentum_residual_norm_kg_m_s", 1.0)),
        ("NC-58_SIM15_ENERGY_GAIN", lambda b: b["m07_rigid"]["cases"][0].__setitem__("kinetic_energy_after_J", 1.0e9)),
        ("NC-59_SIM15_INERTIA", lambda b: b["m07_rigid"]["cases"][0].__setitem__("combined_inertia_min_eigenvalue_kg_m2", -1.0)),
        ("NC-60_SIM15_PHYSICAL_CONTACT", lambda b: b["m07_rigid"]["cases"][0].__setitem__("physical_contact_computed", True)),
        ("NC-61_SIM15_CONTACT_DURATION", lambda b: b["m07_rigid"]["cases"][0].__setitem__("contact_duration_s", 0.02)),
        ("NC-62_SIM15_C08_SELECT", lambda b: b["m07_rigid"].__setitem__("C08_branch_selection_performed", True)),
        ("NC-63_SIM15_C08_UNCERTAINTY", lambda b: b["m07_rigid"]["C08_diagnostic_mass_branches"][0].__setitem__("standard_uncertainty_kg", 0.0)),
        ("NC-64_SIM15_LOCKED_TRANSFORM", lambda b: b["m07_rigid"].__setitem__("locked_transform_gripper_to_target", [0, 0, 0])),
        ("NC-65_SIM15_RELEASED_MASS", lambda b: b["m07_rigid"].__setitem__("released_mass_kg", 51.081436764691)),
        ("NC-66_REGISTER_CHAINING", lambda b: b["register"].__setitem__("cross_lane_chaining_performed", True)),
        ("NC-67_REGISTER_MERGE", lambda b: b["register"].__setitem__("branch_merging_performed", True)),
        ("NC-68_REGISTER_TIMELINE", lambda b: b["register"].__setitem__("mission_timeline_created", True)),
        ("NC-69_REGISTER_NULL_FILL", lambda b: b["register"]["null_hold_ledger"]["M01_release_event"].__setitem__("release_confirmed", False)),
        ("NC-70_REGISTER_END_TO_END", lambda b: b["register"].__setitem__("end_to_end_diagnostic_dynamics_ready", True)),
        ("NC-71_REGISTER_PHYSICAL", lambda b: b["register"].__setitem__("physical_contact_ready", True)),
        ("NC-72_REGISTER_MISSION", lambda b: b["register"].__setitem__("mission_sequence_executable", True)),
        ("NC-73_REGISTER_PRODUCTION", lambda b: b["register"].__setitem__("production_dynamics_ready", True)),
        ("NC-74_REGISTER_CAD", lambda b: b["register"].__setitem__("cad_or_mesh_generated", True)),
        ("NC-75_REGISTER_URDF", lambda b: b["register"].__setitem__("accepted_urdf_modified", True)),
        ("NC-76_REGISTER_RELEASE", lambda b: b["register"].__setitem__("released_segments", 1)),
        ("NC-77_GATE_CRITERION", lambda b: b["gate"]["criteria"][0].__setitem__("observed", False)),
        ("NC-78_GATE_NEXT_STAGE", lambda b: b["gate"].__setitem__("next_stage_authorized", True)),
        ("NC-79_GATE_PHYSICAL", lambda b: b["gate"].__setitem__("physical_contact_ready", True)),
        ("NC-80_GATE_PROMOTED", lambda b: b["gate"].__setitem__("gate", "PASS")),
        ("NC-81_MANIFEST_COUNT", lambda b: b["output_manifest"].__setitem__("artifact_count", 18)),
        ("NC-82_MANIFEST_VALIDATION_INCLUDED", lambda b: b["output_manifest"].__setitem__("validation_report_excluded", False)),
        ("NC-83_MANIFEST_HASH", lambda b: b["output_manifest"]["artifacts"][0].__setitem__("sha256", "0" * 64)),
        ("NC-84_MANIFEST_RELEASE", lambda b: b["output_manifest"].__setitem__("release_credit", True)),
        ("NC-85_GEOMETRY_SUFFIX", lambda b: b["package_suffixes"].append(".step")),
    ]

    negative_controls: list[dict[str, Any]] = []
    for identifier, mutate in mutations:
        candidate = copy.deepcopy(bundle)
        mutate(candidate)
        negative_controls.append({"id": identifier, "pass": not gate_safe(candidate)})

    checks_passed = sum(item["pass"] for item in checks)
    negative_passed = sum(item["pass"] for item in negative_controls)
    passed = (
        checks_passed == len(checks)
        and negative_passed == len(negative_controls)
        and len(negative_controls) >= 48
    )
    report = {
        "schema": "E19_VALIDATION_V1",
        "generated_local": bundle["gate"]["generated_local"],
        "scope": "INDEPENDENT_HASH_NUMERIC_BRANCH_ISOLATION_NULL_HOLD_AND_FAIL_CLOSED_VALIDATION",
        "verdict": "PASS_E19_ISOLATED_DIAGNOSTIC_INTEGRITY__ALL_PHYSICAL_MISSION_PRODUCTION_AND_RELEASE_GATES_HOLD" if passed else "FAIL_E19_DIAGNOSTIC_INTEGRITY",
        "package_integrity_pass": passed,
        "checks": checks,
        "checks_passed": checks_passed,
        "checks_total": len(checks),
        "negative_controls": negative_controls,
        "negative_controls_passed": negative_passed,
        "negative_controls_total": len(negative_controls),
        "accepted_urdf_sha256": sha256_file(ROOT / bundle["authority"]["immutable_asset"]["path"]),
        "four_mission_segments_consumed_as_independent_lanes": True,
        "cross_lane_chaining_performed": False,
        "physical_contact_ready": False,
        "mission_release_ready": False,
        "production_dynamics_ready": False,
        "released_segments": 0,
        "testing_pass_grants_authority": False,
        "gate": "HOLD",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    output = PACKAGE / "results/E19_VALIDATION_V1.json"
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "verdict": report["verdict"],
                "checks": f"{checks_passed}/{len(checks)}",
                "negative_controls": f"{negative_passed}/{len(negative_controls)}",
                "validation_sha256": sha256_file(output),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    if not passed:
        for item in checks:
            if not item["pass"]:
                print(f"FAILED CHECK: {item['id']} -> {item['evidence']}", file=sys.stderr)
        for item in negative_controls:
            if not item["pass"]:
                print(f"FAILED NEGATIVE: {item['id']}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
