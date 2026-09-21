"""Registered B4G schedule helpers and one-slot deterministic execution API."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from . import forced_retraction as forced


HERE = Path(__file__).resolve().parent
PHASE_ROOT = HERE.parent
CONTRACT_ROOT = PHASE_ROOT / "contracts"
SCHEDULE_PATH = CONTRACT_ROOT / "PHASE_B4G_REGISTERED_SCHEDULE_V1.json"
REFERENCE_PATH = CONTRACT_ROOT / "PHASE_B4G_REFERENCE_FORCE_V1.json"


class CampaignContractError(RuntimeError):
    """A frozen schedule or slot does not match the B4G contract."""


@dataclass(frozen=True)
class ReferenceForceAudit:
    """Independent linear-solve recomputation of the one common force scale."""

    symmetric_effective_mass_kg: float
    reference_closing_speed_m_s: float
    reference_common_force_n: float
    individual_finger_reference_force_n: float
    opening_signs: tuple[int, int]
    source_event_time_s: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "symmetric_effective_mass_kg": self.symmetric_effective_mass_kg,
            "reference_closing_speed_m_s": self.reference_closing_speed_m_s,
            "reference_common_force_N": self.reference_common_force_n,
            "individual_finger_reference_force_N": self.individual_finger_reference_force_n,
            "opening_sign_left_right": list(self.opening_signs),
            "source_event_time_s": self.source_event_time_s,
            "linear_solve_used": True,
            "explicit_inverse_used": False,
        }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CampaignContractError(f"JSON_READ_FAILED:{path.name}") from error
    if not isinstance(value, dict):
        raise CampaignContractError(f"JSON_ROOT_NOT_OBJECT:{path.name}")
    return value


def _canonical_sha(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def load_registered_schedule(path: Path | None = None) -> dict[str, Any]:
    """Load and validate the immutable 144-slot registered schedule."""

    schedule = _read_json(SCHEDULE_PATH if path is None else Path(path))
    validate_registered_schedule(schedule)
    return schedule


def validate_registered_schedule(schedule: Mapping[str, Any]) -> None:
    """Fail closed on schedule hash, counts, ordering, or keyed-SHA drift."""

    if schedule.get("schema") != "SIM13_V4B4G_REGISTERED_SCHEDULE_V1":
        raise CampaignContractError("SCHEDULE_SCHEMA_MISMATCH")
    slots = schedule.get("slots")
    if not isinstance(slots, list) or len(slots) != 144:
        raise CampaignContractError("SCHEDULE_SLOT_COUNT_MISMATCH")
    if int(schedule.get("slot_count", -1)) != 144:
        raise CampaignContractError("SCHEDULE_DECLARED_SLOT_COUNT_MISMATCH")
    if _canonical_sha(slots) != str(schedule.get("slots_sha256", "")).upper():
        raise CampaignContractError("SCHEDULE_SLOT_HASH_MISMATCH")
    counts = {arm: sum(slot.get("arm") == arm for slot in slots) for arm in ("A0", "A1", "A2")}
    if counts != {"A0": 12, "A1": 108, "A2": 24}:
        raise CampaignContractError("SCHEDULE_ARM_COUNTS_MISMATCH")
    declared_counts = {
        "A0": int(schedule.get("a0_slot_count", -1)),
        "A1": int(schedule.get("a1_slot_count", -1)),
        "A2": int(schedule.get("a2_slot_count", -1)),
    }
    if declared_counts != counts:
        raise CampaignContractError("SCHEDULE_DECLARED_ARM_COUNTS_MISMATCH")
    for index, slot in enumerate(slots):
        if int(slot.get("slot_index", -1)) != index:
            raise CampaignContractError(f"SCHEDULE_INDEX_MISMATCH:{index}")
        arm = slot.get("arm")
        case_id = str(slot.get("case_id", ""))
        lane = str(slot.get("lane_id", ""))
        if not case_id.startswith(f"{lane}__{arm}__"):
            raise CampaignContractError(f"SCHEDULE_CASE_ID_MISMATCH:{index}")
        if arm in ("A1", "A2"):
            expected_key = hashlib.sha256(
                f"20260824|{lane}|{arm}|{case_id}".encode("utf-8"),
            ).hexdigest().upper()
            if str(slot.get("permutation_key_sha256", "")).upper() != expected_key:
                raise CampaignContractError(f"SCHEDULE_PERMUTATION_KEY_MISMATCH:{index}")
    lane_order = list(schedule.get("lane_order", []))
    expected_lanes = [
        "RK4_COARSE", "RK4_FINE", "RK4_REFERENCE",
        "MIDPOINT_COARSE", "MIDPOINT_FINE", "MIDPOINT_REFERENCE",
    ]
    if lane_order != expected_lanes:
        raise CampaignContractError("SCHEDULE_LANE_ORDER_MISMATCH")
    lane_definition = {
        "RK4_COARSE": ("rk4", 0.001),
        "RK4_FINE": ("rk4", 0.0005),
        "RK4_REFERENCE": ("rk4", 0.00025),
        "MIDPOINT_COARSE": ("midpoint", 0.0005),
        "MIDPOINT_FINE": ("midpoint", 0.00025),
        "MIDPOINT_REFERENCE": ("midpoint", 0.000125),
    }
    if [slot.get("lane_id") for slot in slots] != [
        lane for lane in expected_lanes for _ in range(24)
    ]:
        raise CampaignContractError("SCHEDULE_LANES_NOT_CONTIGUOUS_OR_ORDERED")
    full_factorial = {
        (alpha, duration)
        for alpha in (0.5, 1.0, 2.0, 4.0, 8.0, 16.0)
        for duration in (0.005, 0.01, 0.02)
    }
    expected_variants = {
        "RIGHT_HALF_DELAY", "LEFT_HALF_DELAY_MIRROR",
        "RIGHT_COMMAND_OFF", "LEFT_COMMAND_OFF_MIRROR",
    }
    for lane in lane_order:
        lane_slots = [slot for slot in slots if slot.get("lane_id") == lane]
        if len(lane_slots) != 24:
            raise CampaignContractError(f"SCHEDULE_LANE_SIZE_MISMATCH:{lane}")
        if lane_slots[0].get("arm") != "A0" or lane_slots[0].get("sentinel_position") != "PRE":
            raise CampaignContractError(f"SCHEDULE_A0_PRE_POSITION_MISMATCH:{lane}")
        if lane_slots[-1].get("arm") != "A0" or lane_slots[-1].get("sentinel_position") != "POST":
            raise CampaignContractError(f"SCHEDULE_A0_POST_POSITION_MISMATCH:{lane}")
        if [slot.get("arm") for slot in lane_slots[1:19]] != ["A1"] * 18:
            raise CampaignContractError(f"SCHEDULE_A1_BLOCK_MISMATCH:{lane}")
        if [slot.get("arm") for slot in lane_slots[19:23]] != ["A2"] * 4:
            raise CampaignContractError(f"SCHEDULE_A2_BLOCK_MISMATCH:{lane}")
        expected_method, expected_step = lane_definition[lane]
        if any(
            slot.get("method") != expected_method
            or float(slot.get("step_s", math.nan)) != expected_step
            for slot in lane_slots
        ):
            raise CampaignContractError(f"SCHEDULE_LANE_METHOD_STEP_MISMATCH:{lane}")
        a1_slots = lane_slots[1:19]
        observed_factorial = {
            (float(slot.get("alpha", math.nan)), float(slot.get("command_duration_s", math.nan)))
            for slot in a1_slots
        }
        if observed_factorial != full_factorial or len(observed_factorial) != len(a1_slots):
            raise CampaignContractError(f"SCHEDULE_A1_FULL_FACTORIAL_MISMATCH:{lane}")
        if [slot["permutation_key_sha256"] for slot in a1_slots] != sorted(
            slot["permutation_key_sha256"] for slot in a1_slots
        ):
            raise CampaignContractError(f"SCHEDULE_A1_KEY_ORDER_MISMATCH:{lane}")
        a2_slots = lane_slots[19:23]
        if {str(slot.get("variant_id", "")) for slot in a2_slots} != expected_variants:
            raise CampaignContractError(f"SCHEDULE_A2_VARIANTS_MISMATCH:{lane}")
        if [slot["permutation_key_sha256"] for slot in a2_slots] != sorted(
            slot["permutation_key_sha256"] for slot in a2_slots
        ):
            raise CampaignContractError(f"SCHEDULE_A2_KEY_ORDER_MISMATCH:{lane}")


def recompute_reference_force() -> ReferenceForceAudit:
    """Recompute Q_ref once from the hash-bound B4E reference acquisition."""

    contract = _read_json(REFERENCE_PATH)
    model = forced.b4e.BranchedGripperServiceModel()
    event = forced.b4e.extract_frozen_primary_event()
    acquisition = forced.b4e.acquisition_projection(model, event)
    service = forced.b4e.ServiceState(
        event.service.base_position_inertial_m.copy(),
        event.service.base_quaternion_body_to_inertial_wxyz.copy(),
        event.service.joint_coordinates_mixed.copy(),
        acquisition.eta_plus.copy(),
    )
    opening = forced.opening_signs(model, service, acquisition.snapshot)
    symmetric_basis = np.zeros(14)
    symmetric_basis[12:14] = np.asarray(opening.signs, dtype=float) / math.sqrt(2.0)
    mass, _, _, _, _, _ = forced.b4e._active_formula_terms(model, service, acquisition.snapshot)
    solved = forced.b4e._cholesky_solve(mass, symmetric_basis)
    denominator = float(symmetric_basis @ solved)
    if not math.isfinite(denominator) or denominator <= 0.0:
        raise CampaignContractError("REFERENCE_EFFECTIVE_MASS_DENOMINATOR_INVALID")
    effective_mass = 1.0 / denominator
    closing_speed = abs(float(symmetric_basis @ service.nu_s_mixed))
    common_force = effective_mass * closing_speed / 0.01
    finger_force = common_force / math.sqrt(2.0)
    result = ReferenceForceAudit(
        effective_mass, closing_speed, common_force, finger_force,
        opening.signs, float(event.time_s),
    )
    fields = (
        (effective_mass, float(contract["symmetric_effective_mass_kg"])),
        (closing_speed, float(contract["reference_closing_speed_m_s"])),
        (common_force, float(contract["reference_common_force_N"])),
        (finger_force, float(contract["individual_finger_reference_force_N"])),
    )
    if any(abs(actual - registered) > 1.0e-13 for actual, registered in fields):
        raise CampaignContractError("REFERENCE_FORCE_NATIVE_RECOMPUTATION_MISMATCH")
    return result


def command_for_slot(
    slot: Mapping[str, Any],
    *,
    selected_parent: Mapping[str, Any] | None = None,
) -> forced.ForcedCommand:
    """Map one frozen A0/A1/A2 slot to its exact command definition."""

    case_id = str(slot.get("case_id", ""))
    arm = slot.get("arm")
    if arm == "A0":
        return forced.ForcedCommand.zero(case_id)
    if arm == "A1":
        alpha = float(slot["alpha"])
        duration = float(slot["command_duration_s"])
        if alpha not in (0.5, 1.0, 2.0, 4.0, 8.0, 16.0):
            raise CampaignContractError("A1_ALPHA_OUTSIDE_REGISTERED_GRID")
        if duration not in (0.005, 0.01, 0.02):
            raise CampaignContractError("A1_DURATION_OUTSIDE_REGISTERED_GRID")
        command_arm = forced.CommandArm(alpha, 0.0, duration)
        return forced.ForcedCommand(command_arm, command_arm, case_id)
    if arm != "A2":
        raise CampaignContractError(f"UNKNOWN_SLOT_ARM:{arm}")
    if selected_parent is None:
        raise CampaignContractError("A2_PARENT_REQUIRED_FOR_EXECUTION")
    alpha = float(selected_parent["alpha"])
    duration = float(selected_parent["command_duration_s"])
    if alpha not in (0.5, 1.0, 2.0, 4.0, 8.0, 16.0) or duration not in (0.005, 0.01, 0.02):
        raise CampaignContractError("A2_PARENT_OUTSIDE_REGISTERED_A1_GRID")
    variant = str(slot.get("variant_id", ""))
    definitions = {
        "RIGHT_HALF_DELAY": ((1.0, 0.0), (0.5, 0.005)),
        "LEFT_HALF_DELAY_MIRROR": ((0.5, 0.005), (1.0, 0.0)),
        "RIGHT_COMMAND_OFF": ((1.0, 0.0), (0.0, 0.0)),
        "LEFT_COMMAND_OFF_MIRROR": ((0.0, 0.0), (1.0, 0.0)),
    }
    if variant not in definitions:
        raise CampaignContractError(f"UNKNOWN_A2_VARIANT:{variant}")
    left_definition, right_definition = definitions[variant]
    left = forced.CommandArm(alpha * left_definition[0], left_definition[1], duration)
    right = forced.CommandArm(alpha * right_definition[0], right_definition[1], duration)
    return forced.ForcedCommand(left, right, case_id)


def run_registered_slot(
    slot: Mapping[str, Any],
    *,
    selected_parent: Mapping[str, Any] | None = None,
    q_ref_n: float | None = None,
) -> forced.ForcedRunResult:
    """Execute one slot from a fresh B3 event; no event/state cache is used."""

    method = str(slot.get("method", ""))
    step_s = float(slot.get("step_s", math.nan))
    case_id = str(slot.get("case_id", ""))
    command = command_for_slot(slot, selected_parent=selected_parent)
    reference = recompute_reference_force().individual_finger_reference_force_n if q_ref_n is None else float(q_ref_n)
    event = forced.b4e.rerun_b3_to_event(case_id, method, step_s)
    model = forced.b4e.BranchedGripperServiceModel()
    acquisition = forced.b4e.acquisition_projection(model, event)
    return forced.propagate_forced_case(
        model, event, acquisition, command,
        case_id=case_id, method=method, step_s=step_s,
        q_ref_n=reference, end_time_s=float(event.time_s) + forced.ACTIVE_DURATION_S,
    )


def a0_replay_comparison(
    forced_result: forced.ForcedRunResult,
    b4e_active: Any,
    *,
    common_end_time_s: float = 0.08,
) -> dict[str, Any]:
    """Compare A0 to B4E on the registered common absolute-time interval."""

    if forced_result.command.left.alpha != 0.0 or forced_result.command.right.alpha != 0.0:
        raise CampaignContractError("A0_REPLAY_COMPARISON_REQUIRES_ZERO_COMMAND")
    forced_mask = forced_result.time_s <= float(common_end_time_s) + forced.b4e.TIME_INTERVAL_MERGE_TOLERANCE_S
    forced_time = forced_result.time_s[forced_mask]
    reference_time = np.asarray(b4e_active.time_s, dtype=float)
    if forced_time.shape != reference_time.shape or not np.array_equal(forced_time, reference_time):
        raise CampaignContractError("A0_COMMON_TIME_GRID_MISMATCH")
    forced_state = forced_result.state_30[forced_mask]
    comparisons = {
        "service_position_m": float(np.max(np.abs(forced_state[:, 0:3] - b4e_active.service_position_m))),
        "R_joint_coordinates_rad": float(np.max(np.abs(forced_state[:, 7:13] - b4e_active.service_joint_coordinates_mixed[:, 0:6]))),
        "P_joint_coordinates_m": float(np.max(np.abs(forced_state[:, 13:15] - b4e_active.service_joint_coordinates_mixed[:, 6:8]))),
        "base_linear_m_s": float(np.max(np.abs(forced_state[:, 15:18] - b4e_active.eta_mixed[:, 0:3]))),
        "base_angular_rad_s": float(np.max(np.abs(forced_state[:, 18:21] - b4e_active.eta_mixed[:, 3:6]))),
        "R_joint_rad_s": float(np.max(np.abs(forced_state[:, 21:27] - b4e_active.eta_mixed[:, 6:12]))),
        "P_joint_m_s": float(np.max(np.abs(forced_state[:, 27:29] - b4e_active.eta_mixed[:, 12:14]))),
        "left_gap_m": float(np.max(np.abs(forced_result.left_gap_m[forced_mask] - b4e_active.left_gap_m))),
        "right_gap_m": float(np.max(np.abs(forced_result.right_gap_m[forced_mask] - b4e_active.right_gap_m))),
        "left_gap_rate_m_s": float(np.max(np.abs(forced_result.left_gap_rate_m_s[forced_mask] - b4e_active.left_gap_rate_m_s))),
        "right_gap_rate_m_s": float(np.max(np.abs(forced_result.right_gap_rate_m_s[forced_mask] - b4e_active.right_gap_rate_m_s))),
        "signed_work_J": float(np.max(np.abs(forced_state[:, 29]))),
        "applied_force_N": float(np.max(np.abs(forced_result.applied_q_p_n[forced_mask]))),
    }
    quaternion_errors = [
        forced.b4e.quaternion_geodesic(left, right)
        for left, right in zip(forced_state[:, 3:7], b4e_active.service_quaternion_wxyz)
    ]
    comparisons["service_quaternion_geodesic_rad"] = float(max(quaternion_errors, default=0.0))
    tolerances = {
        "service_position_m": 1.0e-12,
        "service_quaternion_geodesic_rad": 1.0e-12,
        "R_joint_coordinates_rad": 1.0e-12,
        "P_joint_coordinates_m": 1.0e-12,
        "base_linear_m_s": 1.0e-12,
        "base_angular_rad_s": 1.0e-12,
        "R_joint_rad_s": 1.0e-12,
        "P_joint_m_s": 1.0e-12,
        "left_gap_m": 1.0e-12,
        "right_gap_m": 1.0e-12,
        "left_gap_rate_m_s": 1.0e-12,
        "right_gap_rate_m_s": 1.0e-12,
        "signed_work_J": 0.0,
        "applied_force_N": 0.0,
    }
    per_channel_pass = {
        name: value <= tolerances[name] for name, value in comparisons.items()
    }
    return {
        "common_end_time_s": float(common_end_time_s),
        "sample_count": int(len(forced_time)),
        "channel_maxima": comparisons,
        "native_absolute_tolerances": tolerances,
        "per_channel_pass": per_channel_pass,
        "Q_and_W_exact_zero": bool(
            np.all(forced_result.applied_q_p_n[forced_mask] == 0.0)
            and np.all(forced_state[:, 29] == 0.0)
        ),
        "passed": bool(all(per_channel_pass.values())),
    }


def work_quadrature_audit(result: forced.ForcedRunResult) -> dict[str, Any]:
    """Cross-check augmented signed work with native and every-second samples."""

    time = np.asarray(result.time_s, dtype=float)
    power = np.asarray(result.actuator_power_w, dtype=float)
    work = np.asarray(result.signed_work_j, dtype=float)
    if time.ndim != 1 or power.shape != time.shape or work.shape != time.shape or len(time) < 2:
        raise CampaignContractError("WORK_QUADRATURE_HISTORY_INVALID")
    fine = float(np.trapezoid(power, time))
    coarse_indices = list(range(0, len(time), 2))
    if coarse_indices[-1] != len(time) - 1:
        coarse_indices.append(len(time) - 1)
    coarse_index = np.asarray(coarse_indices, dtype=int)
    coarse = float(np.trapezoid(power[coarse_index], time[coarse_index]))
    augmented = float(work[-1] - work[0])
    fine_error = abs(fine - augmented)
    coarse_error = abs(coarse - augmented)
    passed = bool(
        fine_error <= 1.0e-7
        and (fine_error <= coarse_error + 1.0e-15 or coarse_error <= 1.0e-7)
    )
    return {
        "augmented_signed_work_J": augmented,
        "native_composite_trapezoid_J": fine,
        "every_second_sample_composite_trapezoid_J": coarse,
        "native_absolute_error_J": fine_error,
        "every_second_absolute_error_J": coarse_error,
        "native_absolute_error_limit_J": 1.0e-7,
        "refinement_slack_J": 1.0e-15,
        "passed": passed,
    }
