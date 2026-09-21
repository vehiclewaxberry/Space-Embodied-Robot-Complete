"""Unified C0-C3 resolved-rate controller implementation."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.spatial.transform import Rotation

from contracts import (
    dls_pseudoinverse,
    exact_svd_projector,
    joint_limits,
    method_contract,
    reaction_map_about_base_origin,
)
from repo_imports import skew


@dataclass
class ControllerOutput:
    theta_dot_command: np.ndarray
    position_error_m: float
    orientation_error_rad: float
    task_sigma_min: float
    task_condition: float
    task_rank: int
    task_nullity: int
    nullspace_active: bool
    nullspace_fade: float
    nullspace_leakage: float
    reaction_primary_norm: float
    reaction_command_norm: float
    predicted_base_twist: np.ndarray
    feedforward_norm: float


class ResolvedRateController:
    """Same skeleton for C0-C3; only J, feedforward, and N*zeta vary."""

    def __init__(self, model, cfg: dict, method: str, task_mode: str):
        self.model = model
        self.cfg = cfg
        self.contract = method_contract(method, task_mode, cfg)
        self.arm = model.arm
        self.lo, self.hi = joint_limits(self.arm)
        self._plane_n1 = None

    def _continuous_plane_basis(self, a_des: np.ndarray) -> np.ndarray:
        a_des = np.asarray(a_des, dtype=float)
        a_des /= np.linalg.norm(a_des)
        if self._plane_n1 is None:
            seeds = np.eye(3)
            seed = seeds[int(np.argmin(np.abs(seeds @ a_des)))]
            n1 = np.cross(a_des, seed)
        else:
            n1 = self._plane_n1 - a_des * float(a_des @ self._plane_n1)
            if np.linalg.norm(n1) < 1e-10:
                seeds = np.eye(3)
                seed = seeds[int(np.argmin(np.abs(seeds @ a_des)))]
                n1 = np.cross(a_des, seed)
        n1 /= np.linalg.norm(n1)
        n2 = np.cross(a_des, n1)
        self._plane_n1 = n1
        return np.vstack([n1, n2])

    def _pose_error(
        self,
        R_IB: np.ndarray,
        position_I: np.ndarray,
        rotation_IE: np.ndarray,
        reference: dict,
    ) -> tuple[np.ndarray, float, float]:
        position_error_S = R_IB.T @ (reference["position_I"] - position_I)
        rotation_error_I = Rotation.from_matrix(
            reference["rotation_IE"] @ rotation_IE.T
        ).as_rotvec()
        rotation_error_S = R_IB.T @ rotation_error_I
        return (
            np.concatenate([position_error_S, rotation_error_S]),
            float(np.linalg.norm(position_error_S)),
            float(np.linalg.norm(rotation_error_I)),
        )
    def command(
        self,
        theta: np.ndarray,
        eta: np.ndarray,
        eta_dot: np.ndarray,
        R_IB: np.ndarray,
        position_I: np.ndarray,
        rotation_IE: np.ndarray,
        reference: dict,
    ) -> ControllerOutput:
        cc = self.cfg["controller"]
        contract = self.contract
        pose_error, position_error, orientation_error = self._pose_error(
            R_IB, position_I, rotation_IE, reference
        )
        twist_reference_S = np.concatenate(
            [
                R_IB.T @ reference["twist_I"][:3],
                R_IB.T @ reference["twist_I"][3:],
            ]
        )
        fk = self.arm.fk(theta)
        Jm = self.arm.jacobian(theta, fk_out=fk)
        Jstar_full = self.model.generalized_jacobian(theta, eta)
        J6 = Jstar_full[:, :6] if contract.uses_generalized_jacobian else Jm

        if contract.task_mode == "pose_6d":
            Jtask = J6
            error_task = pose_error
            feedforward_task = twist_reference_S
        else:
            a_current_S = fk["T_E"][:3, 2]
            a_desired_S = R_IB.T @ reference["rotation_IE"][:, 2]
            basis = self._continuous_plane_basis(a_desired_S)
            rows_attitude = (
                basis
                @ skew(a_desired_S)
                @ skew(a_current_S)
                @ J6[3:, :]
            )
            Jtask = np.vstack([J6[:3, :], rows_attitude])
            alignment_residual = -(
                basis @ np.cross(a_current_S, a_desired_S)
            )
            error_task = np.concatenate([pose_error[:3], alignment_residual])
            feedforward_attitude = (
                basis
                @ skew(a_desired_S)
                @ skew(a_current_S)
                @ twist_reference_S[3:]
            )
            feedforward_task = np.concatenate(
                [twist_reference_S[:3], feedforward_attitude]
            )
            orientation_error = float(
                np.arccos(
                    np.clip(float(a_current_S @ a_desired_S), -1.0, 1.0)
                )
            )

        gains = np.concatenate(
            [
                np.full(3, float(cc["position_gain_per_s"])),
                np.full(
                    Jtask.shape[0] - 3,
                    float(cc["orientation_gain_per_s"]),
                ),
            ]
        )
        rhs = gains * error_task
        if contract.uses_reference_feedforward:
            rhs = rhs + feedforward_task
        pinv = dls_pseudoinverse(Jtask, float(cc["dls_lambda"]))
        primary = pinv @ rhs
        theta_dot = primary.copy()

        singular = np.linalg.svd(Jtask, compute_uv=False)
        rank_threshold = float(cc["svd_rank_rtol"]) * singular[0]
        rank = int(np.sum(singular > rank_threshold))
        nullity = int(6 - rank)
        nullspace_active = False
        nullspace_fade = 0.0
        nullspace_leakage = 0.0
        reaction = reaction_map_about_base_origin(self.model, theta, eta)
        reaction_primary = float(np.linalg.norm(reaction @ primary))

        if contract.uses_reaction_nullspace:
            projector, exact_rank = exact_svd_projector(
                Jtask, float(cc["svd_rank_rtol"])
            )
            rank = exact_rank
            nullity = 6 - exact_rank
            nullspace_leakage = float(np.linalg.norm(Jtask @ projector, ord=2))
            margin = float(np.min(np.minimum(theta - self.lo, self.hi - theta)))
            fade_margin = float(cc["nullspace_limit_fade_margin_rad"])
            nullspace_fade = float(np.clip(margin / fade_margin, 0.0, 1.0))
            if nullity == 1 and nullspace_fade > 0.0:
                zeta = (
                    -2.0
                    * float(cc["reaction_nullspace_gain"])
                    * reaction.T
                    @ reaction
                    @ primary
                )
                theta_dot = primary + nullspace_fade * (projector @ zeta)
                nullspace_active = True

        momentum_map = self.model.momentum_matrix(theta, eta)
        rate_m = np.concatenate([theta_dot, eta_dot])
        predicted_base = -np.linalg.solve(
            momentum_map[:, :6], momentum_map[:, 6:] @ rate_m
        )
        reaction_command = float(np.linalg.norm(reaction @ theta_dot))
        sigma_min = float(singular[-1])
        condition = (
            float(singular[0] / singular[-1])
            if singular[-1] > 0.0
            else float("inf")
        )
        return ControllerOutput(
            theta_dot_command=theta_dot,
            position_error_m=position_error,
            orientation_error_rad=orientation_error,
            task_sigma_min=sigma_min,
            task_condition=condition,
            task_rank=rank,
            task_nullity=nullity,
            nullspace_active=nullspace_active,
            nullspace_fade=nullspace_fade,
            nullspace_leakage=nullspace_leakage,
            reaction_primary_norm=reaction_primary,
            reaction_command_norm=reaction_command,
            predicted_base_twist=predicted_base,
            feedforward_norm=(
                float(np.linalg.norm(feedforward_task))
                if contract.uses_reference_feedforward
                else 0.0
            ),
        )
