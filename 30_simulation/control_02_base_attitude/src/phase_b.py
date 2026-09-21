"""Stage B: independent post-capture momentum-control replay."""
from __future__ import annotations

import csv
import sys

import numpy as np
import yaml

from config_loader import REPO
from ledger import classify_attribution, propellant_from_angular_impulse


COMMON = REPO / "30_simulation" / "common"
sys.path.insert(0, str(COMMON))

from capture_impulse import GRASP, TUMBLE_AXIS, chaser_stack, rigidize  # noqa: E402
from rigid_body import load_object  # noqa: E402


APPROACH_AXIS = np.array([1.0, 0.0, 0.0])
R_FLIP = np.diag([-1.0, -1.0, 1.0])
CLASS_TARGET = {
    "G1_slender": ("target_debris_v0", 150.0),
    "G2_cubesat": ("target_satellite_v0", 22.0),
}


def _load_cases(cfg: dict) -> dict:
    source = REPO / cfg["stage_b"]["cases_source"]
    with source.open(encoding="utf-8") as f:
        source_cfg = yaml.safe_load(f)
    return source_cfg["cases"]


def _build_case(case: dict):
    """Independent of sim_10 exact_point and sim_12 strategy_eval."""
    target_id, calibration_mass = CLASS_TARGET[case["cls"]]
    target = load_object(target_id)
    mass = float(case["m_t_kg"])
    scale = mass / calibration_mass
    inertia = np.asarray(target["I"], dtype=float) * scale ** (5.0 / 3.0)
    grasp = np.asarray(GRASP[target_id], dtype=float) * scale ** (1.0 / 3.0)
    m_c, com_c, i_c, ee_x = chaser_stack()
    bodies = [
        {
            "m": m_c,
            "I": R_FLIP @ i_c @ R_FLIP.T,
            "r": grasp + APPROACH_AXIS * (ee_x - com_c[0]),
            "v": -0.01 * APPROACH_AXIS,
            "w": np.zeros(3),
        },
        {
            "m": mass,
            "I": inertia,
            "r": np.zeros(3),
            "v": np.zeros(3),
            "w": np.deg2rad(float(case["omega_dps"])) * TUMBLE_AXIS,
        },
    ]
    return rigidize(bodies)


def _sim12_s1_reference() -> dict:
    path = REPO / "30_simulation" / "sim_12_strategy_feasibility" / "results" / "strategy_results.csv"
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return {
        row["case"]: {
            "H_required_Nms": float(row["H_required_Nms"]),
            "post_capture_rate_dps": float(row["post_capture_rate_dps"]),
        }
        for row in rows
        if row["strategy"] == "S1_passive"
    }


def frozen_legacy_region(
    h_norm: float, rate_dps: float, cfg: dict
) -> tuple[str, dict]:
    """Replay the frozen scalar region for cross-checking only.

    The historical 0.3 Nms value is the sum of three axis capacities.  It is
    not a physical wheel-feasibility criterion and must never drive the formal
    CTRL-02 domain label.
    """
    gates = cfg["gates"]
    stage = cfg["stage_b"]
    wheel_scalar = float(np.sum(stage["wheel_capacity_per_axis_Nms"]))
    j_req = h_norm / float(stage["lever_arm_m"])
    time_req = h_norm / (
        float(stage["thruster_force_N"]) * float(stage["lever_arm_m"])
    )
    checks = {
        "rate": rate_dps <= float(gates["post_capture_rate_max_dps"]),
        "wheel_scalar_legacy": h_norm <= wheel_scalar,
        "thruster_impulse": j_req <= float(gates["thruster_impulse_max_Ns"]),
        "detumble_time": time_req <= float(gates["detumble_time_max_s"]),
    }
    if not checks["rate"]:
        region = "INFEASIBLE_RATE"
    elif checks["wheel_scalar_legacy"]:
        region = "WHEELS_ONLY_FEASIBLE"
    elif checks["thruster_impulse"] and checks["detumble_time"]:
        region = "THRUSTER_REQUIRED_FEASIBLE"
    else:
        region = "INFEASIBLE_RESOURCE"
    return region, checks


def physical_box_feasibility(h_vector: np.ndarray, cfg: dict) -> dict:
    """Evaluate wheel storage against the complete per-axis momentum box."""
    h_vector = np.asarray(h_vector, dtype=float)
    if h_vector.shape != (3,):
        raise ValueError("physical wheel feasibility requires a 3-vector")
    box = np.asarray(cfg["stage_b"]["wheel_capacity_per_axis_Nms"], dtype=float)
    feasible_axes = np.abs(h_vector) <= box
    return {
        "criterion": "abs(H_i_Nms) <= wheel_capacity_i_Nms for every axis",
        "H_vector_Nms": h_vector.tolist(),
        "wheel_capacity_per_axis_Nms": box.tolist(),
        "axis_margin_Nms": (box - np.abs(h_vector)).tolist(),
        "axis_feasible": feasible_axes.tolist(),
        "feasible": bool(np.all(feasible_axes)),
    }


def _physical_control_region(
    h_vector: np.ndarray, rate_dps: float, cfg: dict
) -> tuple[str, dict]:
    """Formal momentum-level terminal-feasibility region.

    Wheel-only feasibility is decided exclusively by the per-axis box.  The
    frozen rate and external-resource checks remain unchanged for cases that
    require external angular-momentum removal.
    """
    gates = cfg["gates"]
    stage = cfg["stage_b"]
    h_norm = float(np.linalg.norm(h_vector))
    box = physical_box_feasibility(h_vector, cfg)
    j_req = h_norm / float(stage["lever_arm_m"])
    time_req = h_norm / (
        float(stage["thruster_force_N"]) * float(stage["lever_arm_m"])
    )
    checks = {
        "rate": rate_dps <= float(gates["post_capture_rate_max_dps"]),
        "physical_box": box,
        "thruster_impulse": j_req <= float(gates["thruster_impulse_max_Ns"]),
        "detumble_time": time_req <= float(gates["detumble_time_max_s"]),
    }
    if not checks["rate"]:
        region = "INFEASIBLE_RATE"
    elif box["feasible"]:
        region = "WHEELS_ONLY_FEASIBLE"
    elif checks["thruster_impulse"] and checks["detumble_time"]:
        region = "THRUSTER_REQUIRED_FEASIBLE"
    else:
        region = "INFEASIBLE_RESOURCE"
    return region, checks


def _controller_state(
    controller: str,
    h_initial: np.ndarray,
    inertia: np.ndarray,
    cfg: dict,
) -> dict:
    stage = cfg["stage_b"]
    gates = cfg["gates"]
    tol = float(gates["attribution_abs"])
    box = np.asarray(stage["wheel_capacity_per_axis_Nms"], dtype=float)
    external_capacity = float(gates["external_removal_capacity_Nms"])
    wheel = np.zeros(3)
    d_h_external = np.zeros(3)
    action = "NONE"

    if controller == "B0_no_control":
        outcome = "NO_CONTROL"
    elif controller == "B1_wheel_storage":
        action = "WHEEL_STORAGE"
        wheel = np.clip(h_initial, -box, box)
        outcome = "PENDING"
    elif controller == "B2_thruster_removal":
        action = "THRUSTER_REMOVAL"
        demand = -h_initial
        scale = min(1.0, external_capacity / max(np.linalg.norm(demand), 1e-300))
        d_h_external = scale * demand
        outcome = "PENDING"
    elif controller == "B3_wheel_thruster":
        action = "WHEEL_AND_THRUSTER"
        wheel = np.clip(h_initial, -box, box)
        demand = -(h_initial - wheel)
        scale = min(1.0, external_capacity / max(np.linalg.norm(demand), 1e-300))
        d_h_external = scale * demand
        outcome = "PENDING"
    else:
        raise ValueError(controller)

    h_total_final = h_initial + d_h_external
    h_body_final = h_total_final - wheel
    w_final = np.linalg.solve(inertia, h_body_final)
    rate_final = float(np.rad2deg(np.linalg.norm(w_final)))
    wheel_saturated = bool(np.any(np.abs(wheel) >= box - 1e-12))
    removal = float(np.linalg.norm(d_h_external))
    impulse, propellant = propellant_from_angular_impulse(
        removal,
        float(stage["lever_arm_m"]),
        float(stage["isp_s"]),
        float(stage["g0_mps2"]),
    )
    time_s = removal / (
        float(stage["thruster_force_N"]) * float(stage["lever_arm_m"])
    )
    closure = h_total_final - h_initial - d_h_external

    if controller == "B1_wheel_storage":
        outcome = (
            "BODY_RATE_ZERO_WITH_MOMENTUM_STORED"
            if np.linalg.norm(h_body_final) <= tol
            else "WHEEL_BOX_SATURATED"
        )
    elif controller == "B2_thruster_removal":
        outcome = (
            "ANGULAR_MOMENTUM_TARGET_REACHED"
            if np.linalg.norm(h_body_final) <= tol
            else "EXTERNAL_BUDGET_EXHAUSTED"
        )
    elif controller == "B3_wheel_thruster":
        if np.linalg.norm(h_body_final) > tol:
            outcome = "EXTERNAL_BUDGET_EXHAUSTED"
        elif removal > tol:
            outcome = "BODY_RATE_ZERO_WITH_MIXED_LEDGER"
        else:
            outcome = "BODY_RATE_ZERO_WITH_MOMENTUM_STORED"

    attribution = classify_attribution(
        d_h_external, wheel, internal_motion=False, tolerance=tol
    )
    return {
        "control_action": action,
        "controller_outcome": outcome,
        "attribution": attribution,
        "wheel_h_final_Nms": wheel.tolist(),
        "wheel_box_utilization_max": float(np.max(np.abs(wheel) / box)),
        "wheel_saturated": wheel_saturated,
        "external_angular_impulse_vector_Nms": d_h_external.tolist(),
        "external_angular_impulse_Nms": removal,
        "thruster_total_impulse_Ns": impulse,
        "propellant_g": propellant,
        "detumble_actuation_time_s": time_s,
        "H_total_final_Nms": float(np.linalg.norm(h_total_final)),
        "H_body_final_Nms": float(np.linalg.norm(h_body_final)),
        "body_rate_final_dps": rate_final,
        "external_ledger_closure_max_abs": float(np.max(np.abs(closure))),
    }


def run_phase_b(cfg: dict) -> tuple[list[dict], dict]:
    cases = _load_cases(cfg)
    refs = _sim12_s1_reference()
    rows = []
    crosschecks = {}
    for case_id in cfg["stage_b"]["cases"]:
        case = cases[case_id]
        capture = _build_case(case)
        h_initial = np.asarray(capture["H_com"], dtype=float)
        h_norm = float(np.linalg.norm(h_initial))
        rate_dps = float(np.rad2deg(np.linalg.norm(capture["w_plus"])))
        legacy_region, legacy_checks = frozen_legacy_region(h_norm, rate_dps, cfg)
        physical_region, physical_checks = _physical_control_region(
            h_initial, rate_dps, cfg
        )
        ref = refs[case_id]
        crosschecks[case_id] = {
            "H_diff_Nms": abs(h_norm - ref["H_required_Nms"]),
            "rate_diff_dps": abs(rate_dps - ref["post_capture_rate_dps"]),
            "independent_H_Nms": h_norm,
            "independent_rate_dps": rate_dps,
            "sim12_H_Nms": ref["H_required_Nms"],
            "sim12_rate_dps": ref["post_capture_rate_dps"],
        }
        domain = (
            "IN_FEASIBLE_REGION"
            if physical_region
            in ("WHEELS_ONLY_FEASIBLE", "THRUSTER_REQUIRED_FEASIBLE")
            else "OUT_OF_FEASIBLE_REGION"
        )

        for controller in cfg["stage_b"]["controllers"]:
            state = _controller_state(
                controller, h_initial, np.asarray(capture["I_comb"]), cfg
            )
            row = {
                "phase": "B",
                "case": case_id,
                "case_definition": {
                    "cls": case["cls"],
                    "m_t_kg": float(case["m_t_kg"]),
                    "omega_dps": float(case["omega_dps"]),
                },
                "controller": controller,
                "evaluation_status": "EVALUATED",
                "analysis_scope": "MOMENTUM_LEVEL_TERMINAL_FEASIBILITY",
                "stability_status": "NOT_EVALUATED_NO_ACTUATOR_DYNAMICS",
                "frozen_legacy_region": legacy_region,
                "frozen_legacy_region_checks": legacy_checks,
                "physical_control_region": physical_region,
                "physical_box_feasibility": physical_checks["physical_box"],
                "physical_region_checks": physical_checks,
                "domain_status": domain,
                "counterfactual_only": domain == "OUT_OF_FEASIBLE_REGION",
                "H_initial_Nms": h_norm,
                "post_capture_rate_initial_dps": rate_dps,
                "capture_eps_H": float(capture["eps_H_origin"]),
                "capture_eps_P": float(capture["eps_P"]),
                "flex_status": cfg["stage_b"]["flex_status"],
                **state,
            }
            rows.append(row)
    return rows, crosschecks
