"""T3 collision evidence using the frozen sim_09 coarse geometry contract.

CTRL-01-R (repeat preregistration R-2): T3 now starts from the method-specific
frozen T2 t=15 s state and the target continues the frozen sim09 const-omega
3 deg/s propagation (T3-local time t maps to absolute phase omega*(15 s + t)).
With the trigger and propagation frozen, the target and combined keep-out
margins are evaluated at every fixed integration node alongside the static
servicer geometry; the v0 fail-closed NOT_EVALUATED refusal is retired for
this contract and retained for any input that violates it.

The target keep-out box is inertially anchored at the t2 capture placement
(station-kept CoM, rotating about it) and is re-expressed in the current S
frame at each node using the recorded base pose.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from contracts import normalized_semantic_sha256, raw_sha256
from repo_imports import REPO_ROOT, load_object, q_to_R

import collision


TARGET_ID = "target_satellite_v0"
TARGET_SPEC_PATH = (
    REPO_ROOT
    / "20_engineering"
    / "cad"
    / "spacecraft_layout"
    / TARGET_ID
    / f"{TARGET_ID}.json"
)
GEOMETRY_PATH = (
    REPO_ROOT / "20_engineering" / "config" / "grasp_evaluator" / "collision_geometry_v1.yaml"
)
PRIMARY_GRASP_ID = "launch_adapter_ring"
PLAN_CONTRACT_MATCHED = (
    "MATCHED_T2_T15_TRIGGER_AND_CONST_OMEGA_CONTINUATION"
)
TARGET_MOTION_CONTRACT = (
    "SIM09_CONST_OMEGA_3_DEG_PER_S_FROM_FROZEN_T2_T15_STATE"
)


class CollisionEvidenceUnavailable(RuntimeError):
    """Frozen inputs cannot support the declared collision evaluation."""


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _primary_grasp_point_T() -> np.ndarray:
    if not TARGET_SPEC_PATH.exists():
        raise CollisionEvidenceUnavailable(
            f"missing frozen target specification: {_relative(TARGET_SPEC_PATH)}"
        )
    spec = json.loads(TARGET_SPEC_PATH.read_text(encoding="utf-8"))
    points = [
        row
        for row in spec.get("features", {}).get("grasp_points_mm", [])
        if row.get("name") == PRIMARY_GRASP_ID
    ]
    if len(points) != 1:
        raise CollisionEvidenceUnavailable(
            f"frozen target specification does not contain one {PRIMARY_GRASP_ID}"
        )
    if points[0].get("approach_axis") != "+X_T":
        raise CollisionEvidenceUnavailable(
            "primary frozen target grasp approach is not +X_T"
        )
    return np.asarray(points[0]["point_mm"], dtype=float) / 1000.0


def build_t2_target_scene(model, cfg: dict[str, Any]) -> dict[str, Any]:
    """Construct the t=0 target pose from the frozen T2 EE capture pose.

    The frozen sim_09 launch-ring grasp convention maps EE axes to target axes:
    x_E=+z_T, y_E=+y_T, z_E=-x_T. No target dimensions are recreated here.
    """
    if not GEOMETRY_PATH.exists():
        raise CollisionEvidenceUnavailable(
            f"missing frozen collision geometry: {_relative(GEOMETRY_PATH)}"
        )
    geo = collision.load_geometry(str(GEOMETRY_PATH))
    if TARGET_ID not in geo.get("targets", {}):
        raise CollisionEvidenceUnavailable(
            f"{TARGET_ID} absent from frozen collision geometry"
        )

    q0 = np.asarray(cfg["trajectories"]["T2"]["q_initial_rad"], dtype=float)
    capture_point_S = np.asarray(
        cfg["trajectories"]["T2"]["capture_point_S_m"], dtype=float
    )
    fk = model.arm.fk(q0)
    ee_position_S = np.asarray(fk["T_E"][:3, 3], dtype=float)
    R_SE = np.asarray(fk["T_E"][:3, :3], dtype=float)
    position_residual = float(np.linalg.norm(ee_position_S - capture_point_S))
    if position_residual > 1e-6:
        raise CollisionEvidenceUnavailable(
            f"T2 EE/capture-point residual {position_residual:.3e} m exceeds 1e-6"
        )

    R_ST = np.column_stack((-R_SE[:, 2], R_SE[:, 1], R_SE[:, 0]))
    orthogonality_error = float(np.max(np.abs(R_ST.T @ R_ST - np.eye(3))))
    determinant = float(np.linalg.det(R_ST))
    if orthogonality_error > 1e-10 or abs(determinant - 1.0) > 1e-10:
        raise CollisionEvidenceUnavailable("derived T2 target rotation is invalid")

    target = load_object(TARGET_ID)
    cg_T = np.asarray(target["cg"], dtype=float)
    grasp_point_T = _primary_grasp_point_T()
    grasp_relative_com_T = grasp_point_T - cg_T
    target_com_S = capture_point_S - R_ST @ grasp_relative_com_T
    reconstructed_capture = target_com_S + R_ST @ grasp_relative_com_T
    grasp_residual = float(np.linalg.norm(reconstructed_capture - capture_point_S))
    if grasp_residual > 1e-12:
        raise CollisionEvidenceUnavailable(
            f"target grasp placement residual {grasp_residual:.3e} m"
        )

    target_primitive = collision.target_primitive(
        TARGET_ID, R_ST, target_com_S, cg_T, geo=geo
    )
    return {
        "target_id": TARGET_ID,
        "primary_grasp_id": PRIMARY_GRASP_ID,
        "capture_point_I_m": capture_point_S,
        "grasp_point_T_m": grasp_point_T,
        "target_cg_T_m": cg_T,
        "target_com_I_m": target_com_S,
        "target_rotation_IT": R_ST,
        "target_primitive_t0": target_primitive,
        "t2_pose_position_residual_m": position_residual,
        "target_grasp_placement_residual_m": grasp_residual,
        "target_rotation_orthogonality_max_abs": orthogonality_error,
        "target_rotation_determinant": determinant,
        "geometry": geo,
        "sources": {
            "collision_geometry": {
                "path": _relative(GEOMETRY_PATH),
                "raw_sha256": raw_sha256(GEOMETRY_PATH),
                "normalized_semantic_sha256": normalized_semantic_sha256(
                    GEOMETRY_PATH
                ),
            },
            "target_specification": {
                "path": _relative(TARGET_SPEC_PATH),
                "raw_sha256": raw_sha256(TARGET_SPEC_PATH),
                "normalized_semantic_sha256": normalized_semantic_sha256(
                    TARGET_SPEC_PATH
                ),
            },
        },
    }


def _rotvec_matrix(axis: np.ndarray, angle: float) -> np.ndarray:
    a = axis / np.linalg.norm(axis)
    K = np.array(
        [
            [0.0, -a[2], a[1]],
            [a[2], 0.0, -a[0]],
            [-a[1], a[0], 0.0],
        ]
    )
    return (
        np.eye(3)
        + math.sin(angle) * K
        + (1.0 - math.cos(angle)) * (K @ K)
    )


def _target_only_margin(arm, q, target_prim, grasp_point_S, geo) -> float:
    """Minimum arm-capsule vs target keep-out margin, allowed zone exempt.

    Uses the frozen sim_09 capsule chain, sampling counts and signed-distance
    primitives; no geometry is redefined here.
    """
    radius = float(geo["arm_capsules"]["radius_m"])
    n_s = max(int(geo["arm_capsules"]["n_samples_per_capsule"]), 9)
    r_allow = float(geo["grasp_allowed_zone_radius_m"])
    chain = collision.capsule_chain(arm, q)
    grasp = np.asarray(grasp_point_S, dtype=float)
    margin = np.inf
    ts = np.linspace(0.0, 1.0, n_s)
    for k in range(len(chain) - 1):
        pts = chain[k][None, :] + ts[:, None] * (chain[k + 1] - chain[k])[None, :]
        for p in pts:
            if np.linalg.norm(p - grasp) < r_allow:
                continue
            margin = min(
                margin, collision.point_primitive_sd(p, target_prim) - radius
            )
    return float(margin)


def evaluate_t3_collision(
    model,
    cfg: dict[str, Any],
    t_grid: np.ndarray,
    theta_history: np.ndarray,
    base_position_I_history: np.ndarray,
    base_quaternion_history: np.ndarray,
    t_offset_s: float,
) -> dict[str, Any]:
    """Static, target and combined margins at every fixed integration node."""
    dt = float(cfg["controller"]["sample_period_s"])
    n = len(t_grid)
    if not (
        theta_history.shape == (n, 6)
        and base_position_I_history.shape == (n, 3)
        and base_quaternion_history.shape == (n, 4)
    ):
        raise ValueError("collision history shapes do not match the T3 time grid")
    if n < 2 or not np.allclose(np.diff(t_grid), dt, rtol=0.0, atol=1e-12):
        raise ValueError("T3 collision coverage must use every fixed integration node")

    trigger_cfg = cfg["trajectories"]["T3"]["trigger"]
    expected_offset = float(trigger_cfg["time_s"])
    if not np.isclose(float(t_offset_s), expected_offset, rtol=0.0, atol=1e-12):
        raise CollisionEvidenceUnavailable(
            f"T3 time offset {t_offset_s} s does not match the frozen "
            f"trigger contract {expected_offset} s"
        )

    scene = build_t2_target_scene(model, cfg)
    geo = scene["geometry"]
    t2 = cfg["trajectories"]["T2"]
    axis = np.asarray(t2["target_tumble_axis_inertial"], dtype=float)
    axis /= np.linalg.norm(axis)
    omega = math.radians(float(t2["target_tumble_rate_before_capture_deg_per_s"]))
    R_IT0 = np.asarray(scene["target_rotation_IT"], dtype=float)
    com_I = np.asarray(scene["target_com_I_m"], dtype=float)
    cg_T = np.asarray(scene["target_cg_T_m"], dtype=float)
    grasp_rel_com_T = (
        np.asarray(scene["grasp_point_T_m"], dtype=float) - cg_T
    )

    static_margin = np.empty(n)
    target_margin = np.empty(n)
    combined_margin = np.empty(n)
    for index in range(n):
        theta = theta_history[index]
        r_b = base_position_I_history[index]
        quat = base_quaternion_history[index]
        R_IB = q_to_R(np.asarray(quat, float) / np.linalg.norm(quat)).as_matrix()
        t_abs = float(t_offset_s) + float(t_grid[index])
        R_IT = _rotvec_matrix(axis, omega * t_abs) @ R_IT0
        R_ST = R_IB.T @ R_IT
        com_S = R_IB.T @ (com_I - r_b)
        grasp_I = com_I + R_IT @ grasp_rel_com_T
        grasp_S = R_IB.T @ (grasp_I - r_b)
        target_prim = collision.target_primitive(
            TARGET_ID, R_ST, com_S, cg_T, geo=geo
        )
        static_margin[index] = collision.configuration_margin(
            model.arm, theta, None, grasp_S, geo=geo
        )
        target_margin[index] = _target_only_margin(
            model.arm, theta, target_prim, grasp_S, geo
        )
        combined_margin[index] = min(static_margin[index], target_margin[index])

    def minimum(values: np.ndarray) -> tuple[float, float]:
        minimum_index = int(np.argmin(values))
        return float(values[minimum_index]), float(t_grid[minimum_index])

    static_min, static_time = minimum(static_margin)
    target_min, target_time = minimum(target_margin)
    combined_min, combined_time = minimum(combined_margin)
    return {
        "evaluation_status": "EVALUATED",
        "plan_contract_status": PLAN_CONTRACT_MATCHED,
        "static_evaluation_status": "EVALUATED",
        "target_evaluation_status": "EVALUATED",
        "combined_evaluation_status": "EVALUATED",
        "not_evaluated_reason": "",
        "static_margin_min_m": static_min,
        "static_margin_t_at_min_s": static_time,
        "target_margin_min_m": target_min,
        "target_margin_t_at_min_s": target_time,
        "combined_margin_min_m": combined_min,
        "combined_margin_t_at_min_s": combined_time,
        "time_samples": int(n),
        "time_step_s": dt,
        "t_offset_s": float(t_offset_s),
        "target_phase_at_t3_start_deg": math.degrees(omega * float(t_offset_s)),
        "static_time_coverage": "ALL_FIXED_INTEGRATION_NODES",
        "target_time_coverage": "ALL_FIXED_INTEGRATION_NODES",
        "between_node_coverage": "NOT_GUARANTEED",
        "capsules": int(len(collision.capsule_chain(model.arm, theta_history[0])) - 1),
        "axis_samples_per_capsule": max(
            int(geo["arm_capsules"]["n_samples_per_capsule"]), 9
        ),
        "target_motion_contract": TARGET_MOTION_CONTRACT,
        "target_id": TARGET_ID,
        "primary_grasp_id": PRIMARY_GRASP_ID,
        "scene": {
            "capture_point_I_m": scene["capture_point_I_m"].tolist(),
            "grasp_point_T_m": scene["grasp_point_T_m"].tolist(),
            "target_cg_T_m": scene["target_cg_T_m"].tolist(),
            "target_com_I_m": scene["target_com_I_m"].tolist(),
            "target_rotation_IT_t0": scene["target_rotation_IT"].tolist(),
            "target_primitive_t0_center_S": np.asarray(
                scene["target_primitive_t0"]["center_S"], dtype=float
            ).tolist(),
            "target_primitive_t0_half_extents_m": list(
                scene["target_primitive_t0"]["half_extents_m"]
            ),
            "t2_pose_position_residual_m": scene[
                "t2_pose_position_residual_m"
            ],
            "target_grasp_placement_residual_m": scene[
                "target_grasp_placement_residual_m"
            ],
            "target_rotation_orthogonality_max_abs": scene[
                "target_rotation_orthogonality_max_abs"
            ],
            "target_rotation_determinant": scene[
                "target_rotation_determinant"
            ],
            "sources": scene["sources"],
        },
        "t_s": np.asarray(t_grid, dtype=float),
        "static_margin_m": static_margin,
        "target_margin_m": target_margin,
        "combined_margin_m": combined_margin,
    }
