"""Synthetic 6R arm with a fixed palm and two independent prismatic branches.

The branch signs and design-model inertials are read-only topology inputs from
the existing B601 URDF.  Contact pad positions remain explicit synthetic
assumptions because current left/right contact frames are null/HOLD.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import sys
from typing import Sequence

import numpy as np


HERE = Path(__file__).resolve().parent
PHASE_ROOT = HERE.parents[1]
if str(PHASE_ROOT) not in sys.path:
    sys.path.insert(0, str(PHASE_ROOT))

from sim13_v4a.full_floating import (  # noqa: E402
    BodyKinematics,
    ChainKinematics,
    DynamicsError,
    FullFloatingServiceModel,
    ServiceState,
    axis_rotation,
    quat_to_rotation,
    skew,
)


SCOPE = "SYNTHETIC_BRANCHED_6R_PLUS_PARALLEL_2P_TOPOLOGY_DIAGNOSTIC"
CURRENT_SYSTEM_BOUND = False
PHYSICAL_CONTACT_FRAMES_BOUND = False
URDF_MODIFIED_OR_GENERATED = False


@dataclass(frozen=True)
class BranchFrames:
    arm_joint_origins_inertial_m: tuple[np.ndarray, ...]
    arm_joint_axes_inertial: tuple[np.ndarray, ...]
    arm_link_origins_inertial_m: tuple[np.ndarray, ...]
    arm_link_rotations_body_to_inertial: tuple[np.ndarray, ...]
    palm_origin_inertial_m: np.ndarray
    palm_rotation_body_to_inertial: np.ndarray
    left_joint_origin_inertial_m: np.ndarray
    right_joint_origin_inertial_m: np.ndarray
    left_axis_inertial: np.ndarray
    right_axis_inertial: np.ndarray
    left_link_origin_inertial_m: np.ndarray
    right_link_origin_inertial_m: np.ndarray
    left_link_rotation_body_to_inertial: np.ndarray
    right_link_rotation_body_to_inertial: np.ndarray


class BranchedGripperServiceModel(FullFloatingServiceModel):
    """Full-floating service model whose final two P joints are siblings."""

    def __init__(self) -> None:
        super().__init__()
        self.arm_dof = 6
        self.palm_fixed_origin_parent_m = np.array((0.0, 0.0, 0.15971))
        self.palm_fixed_rotation_parent = axis_rotation((0.0, 1.0, 0.0), -0.5 * math.pi)
        self.palm_mass_kg = 0.181800159145243
        self.palm_com_body_m = np.array((-0.11400456131826, 7.30809328589541e-05, -8.098254686284e-08))
        self.palm_inertia_body_kg_m2 = np.array(
            (
                (0.000232385828322385, -2.77584025941111e-07, -6.04874349510246e-10),
                (-2.77584025941111e-07, 5.85085867377427e-05, -1.15493362444215e-08),
                (-6.04874349510246e-10, -1.15493362444215e-08, 0.000205213535851537),
            )
        )
        self.left_joint_origin_palm_m = np.array((-0.042091, 2.7531e-05, -1.3031e-05))
        self.right_joint_origin_palm_m = np.array((-0.042091, -2.7531e-05, 1.3031e-05))
        self.left_joint_rotation_palm = axis_rotation((0.0, 0.0, 1.0), -0.5 * math.pi)
        self.right_joint_rotation_palm = axis_rotation((0.0, 0.0, 1.0), 0.5 * math.pi)
        self.left_axis_palm = np.array((0.0, -1.0, 0.0))
        self.right_axis_palm = np.array((0.0, 1.0, 0.0))
        self.finger_masses_kg = (0.0423278952416158, 0.0423278949561274)
        self.finger_com_body_m = (
            np.array((0.00937154605945142, -0.0183514409006279, -0.00213050813223617)),
            np.array((0.00937154599936671, 0.0183514410059713, 0.00213050822993754)),
        )
        self.finger_inertias_body_kg_m2 = (
            np.array(
                (
                    (9.68819007445228e-06, -1.14547785891207e-06, 1.82410432419993e-08),
                    (-1.14547785891207e-06, 9.7195653452821e-06, 1.20737618180169e-07),
                    (1.82410432419993e-08, 1.20737618180169e-07, 1.13638462227589e-05),
                )
            ),
            np.array(
                (
                    (9.68819002375832e-06, 1.14547786360874e-06, -1.82410118281856e-08),
                    (1.14547786360874e-06, 9.7195652747221e-06, 1.20737613592695e-07),
                    (-1.82410118281856e-08, 1.20737613592695e-07, 1.13638461944347e-05),
                )
            ),
        )

    @property
    def total_mass_kg(self) -> float:
        return float(
            self.base_mass_kg
            + np.sum(self.link_masses_kg[:6])
            + self.palm_mass_kg
            + sum(self.finger_masses_kg)
        )

    def _branch_frames(self, state: ServiceState) -> BranchFrames:
        state = self.validate_service_state(state)
        parent_position = state.base_position_inertial_m
        parent_rotation = quat_to_rotation(state.base_quaternion_body_to_inertial_wxyz)
        joint_origins: list[np.ndarray] = []
        joint_axes: list[np.ndarray] = []
        link_origins: list[np.ndarray] = []
        link_rotations: list[np.ndarray] = []
        for index in range(self.arm_dof):
            joint_origin = parent_position + parent_rotation @ self.joint_origin_offsets_parent_m[index]
            axis_world = parent_rotation @ self.joint_axes_parent[index]
            child_rotation = parent_rotation @ axis_rotation(
                self.joint_axes_parent[index], float(state.joint_coordinates_mixed[index])
            )
            child_origin = joint_origin
            joint_origins.append(joint_origin); joint_axes.append(axis_world)
            link_origins.append(child_origin); link_rotations.append(child_rotation)
            parent_position = child_origin + child_rotation @ self.link_tip_offsets_body_m[index]
            parent_rotation = child_rotation
        palm_origin = parent_position + parent_rotation @ self.palm_fixed_origin_parent_m
        palm_rotation = parent_rotation @ self.palm_fixed_rotation_parent
        left_joint = palm_origin + palm_rotation @ self.left_joint_origin_palm_m
        right_joint = palm_origin + palm_rotation @ self.right_joint_origin_palm_m
        left_axis = palm_rotation @ self.left_axis_palm
        right_axis = palm_rotation @ self.right_axis_palm
        left_origin = left_joint + left_axis * float(state.joint_coordinates_mixed[6])
        right_origin = right_joint + right_axis * float(state.joint_coordinates_mixed[7])
        return BranchFrames(
            tuple(joint_origins), tuple(joint_axes), tuple(link_origins), tuple(link_rotations),
            palm_origin, palm_rotation, left_joint, right_joint, left_axis, right_axis,
            left_origin, right_origin,
            palm_rotation @ self.left_joint_rotation_palm,
            palm_rotation @ self.right_joint_rotation_palm,
        )

    def _arm_point_jacobians(
        self, state: ServiceState, point_inertial_m: np.ndarray, frames: BranchFrames
    ) -> tuple[np.ndarray, np.ndarray]:
        jv = np.zeros((3, self.full_velocity_dof)); jw = np.zeros_like(jv)
        jv[:, :3] = np.eye(3)
        jv[:, 3:6] = -skew(point_inertial_m - state.base_position_inertial_m)
        jw[:, 3:6] = np.eye(3)
        for index in range(self.arm_dof):
            axis = frames.arm_joint_axes_inertial[index]
            jv[:, 6 + index] = np.cross(axis, point_inertial_m - frames.arm_joint_origins_inertial_m[index])
            jw[:, 6 + index] = axis
        return jv, jw

    def palm_frame_and_jacobians(
        self, state: ServiceState
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        state = self.validate_service_state(state); frames = self._branch_frames(state)
        jv, jw = self._arm_point_jacobians(state, frames.palm_origin_inertial_m, frames)
        return frames.palm_origin_inertial_m, frames.palm_rotation_body_to_inertial, jv, jw

    def synthetic_pad_position_and_jacobian(
        self,
        state: ServiceState,
        side: str,
        *,
        closed_half_gap_m: float,
        pad_x_palm_m: float,
        pad_z_palm_m: float,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        state = self.validate_service_state(state); frames = self._branch_frames(state)
        if not all(math.isfinite(value) for value in (closed_half_gap_m, pad_x_palm_m, pad_z_palm_m)):
            raise DynamicsError("synthetic pad constants must be finite")
        if side == "left":
            coordinate = float(state.joint_coordinates_mixed[6])
            local = np.array((pad_x_palm_m, -(closed_half_gap_m + coordinate), pad_z_palm_m))
            p_column = 12; p_axis = frames.left_axis_inertial
        elif side == "right":
            coordinate = float(state.joint_coordinates_mixed[7])
            local = np.array((pad_x_palm_m, closed_half_gap_m + coordinate, pad_z_palm_m))
            p_column = 13; p_axis = frames.right_axis_inertial
        else:
            raise DynamicsError("side must be left or right")
        position = frames.palm_origin_inertial_m + frames.palm_rotation_body_to_inertial @ local
        jv, jw = self._arm_point_jacobians(state, position, frames)
        jv[:, p_column] = p_axis
        return position, jv, jw

    def point_position_and_jacobian(
        self, state: ServiceState, link_index: int, point_local_m: Sequence[float]
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        state = self.validate_service_state(state); frames = self._branch_frames(state)
        local = np.asarray(point_local_m, dtype=float)
        if local.shape != (3,) or not np.all(np.isfinite(local)):
            raise DynamicsError("link-local point must contain three finite values")
        if 0 <= link_index < 6:
            position = frames.arm_link_origins_inertial_m[link_index] + frames.arm_link_rotations_body_to_inertial[link_index] @ local
            jv = np.zeros((3, self.full_velocity_dof)); jw = np.zeros_like(jv)
            jv[:, :3] = np.eye(3); jv[:, 3:6] = -skew(position - state.base_position_inertial_m); jw[:, 3:6] = np.eye(3)
            for index in range(link_index + 1):
                axis = frames.arm_joint_axes_inertial[index]
                jv[:, 6 + index] = np.cross(axis, position - frames.arm_joint_origins_inertial_m[index]); jw[:, 6 + index] = axis
            return position, jv, jw
        if link_index == 6:
            position = frames.left_link_origin_inertial_m + frames.left_link_rotation_body_to_inertial @ local
            jv, jw = self._arm_point_jacobians(state, position, frames); jv[:, 12] = frames.left_axis_inertial
            return position, jv, jw
        if link_index == 7:
            position = frames.right_link_origin_inertial_m + frames.right_link_rotation_body_to_inertial @ local
            jv, jw = self._arm_point_jacobians(state, position, frames); jv[:, 13] = frames.right_axis_inertial
            return position, jv, jw
        raise DynamicsError("link_index must be in [0,7]")

    def kinematics(self, state: ServiceState) -> ChainKinematics:
        state = self.validate_service_state(state); frames = self._branch_frames(state)
        base_rotation = quat_to_rotation(state.base_quaternion_body_to_inertial_wxyz)
        base_jv = np.zeros((3, self.full_velocity_dof)); base_jw = np.zeros_like(base_jv)
        base_jv[:, :3] = np.eye(3); base_jw[:, 3:6] = np.eye(3)
        bodies: list[BodyKinematics] = [
            BodyKinematics(
                "service_base", self.base_mass_kg,
                base_rotation @ self.base_inertia_body_kg_m2 @ base_rotation.T,
                state.base_position_inertial_m.copy(), base_rotation, base_jv, base_jw,
            )
        ]
        for index in range(self.arm_dof):
            rotation = frames.arm_link_rotations_body_to_inertial[index]
            position = frames.arm_link_origins_inertial_m[index] + rotation @ self.link_com_offsets_body_m[index]
            jv = np.zeros((3, self.full_velocity_dof)); jw = np.zeros_like(jv)
            jv[:, :3] = np.eye(3); jv[:, 3:6] = -skew(position - state.base_position_inertial_m); jw[:, 3:6] = np.eye(3)
            for joint in range(index + 1):
                axis = frames.arm_joint_axes_inertial[joint]
                jv[:, 6 + joint] = np.cross(axis, position - frames.arm_joint_origins_inertial_m[joint]); jw[:, 6 + joint] = axis
            bodies.append(BodyKinematics(
                f"synthetic_arm_link_{index + 1}", float(self.link_masses_kg[index]),
                rotation @ self.link_inertias_body_kg_m2[index] @ rotation.T,
                position, rotation, jv, jw,
            ))
        palm_position = frames.palm_origin_inertial_m + frames.palm_rotation_body_to_inertial @ self.palm_com_body_m
        palm_jv, palm_jw = self._arm_point_jacobians(state, palm_position, frames)
        bodies.append(BodyKinematics(
            "design_model_palm", self.palm_mass_kg,
            frames.palm_rotation_body_to_inertial @ self.palm_inertia_body_kg_m2 @ frames.palm_rotation_body_to_inertial.T,
            palm_position, frames.palm_rotation_body_to_inertial, palm_jv, palm_jw,
        ))
        for side, origin, rotation, mass, com, inertia, column, axis in (
            ("left", frames.left_link_origin_inertial_m, frames.left_link_rotation_body_to_inertial, self.finger_masses_kg[0], self.finger_com_body_m[0], self.finger_inertias_body_kg_m2[0], 12, frames.left_axis_inertial),
            ("right", frames.right_link_origin_inertial_m, frames.right_link_rotation_body_to_inertial, self.finger_masses_kg[1], self.finger_com_body_m[1], self.finger_inertias_body_kg_m2[1], 13, frames.right_axis_inertial),
        ):
            position = origin + rotation @ com
            jv, jw = self._arm_point_jacobians(state, position, frames); jv[:, column] = axis
            bodies.append(BodyKinematics(
                f"design_model_{side}_finger", mass, rotation @ inertia @ rotation.T,
                position, rotation, jv, jw,
            ))
        return ChainKinematics(
            tuple(bodies),
            tuple((*frames.arm_joint_origins_inertial_m, frames.left_joint_origin_inertial_m, frames.right_joint_origin_inertial_m)),
            tuple((*frames.arm_joint_axes_inertial, frames.left_axis_inertial, frames.right_axis_inertial)),
            tuple((*frames.arm_link_origins_inertial_m, frames.left_link_origin_inertial_m, frames.right_link_origin_inertial_m)),
            tuple((*frames.arm_link_rotations_body_to_inertial, frames.left_link_rotation_body_to_inertial, frames.right_link_rotation_body_to_inertial)),
        )
