"""Fail-closed rigid-body momentum backend for the Sim13 V2 prebind path.

This module consumes URDF XML *bytes* in memory.  It does not generate, write,
authorize, bind, or load a production URDF.  Its deliberately narrow scope is
prescribed joint motion at the momentum level; it is neither a torque-driven
multibody solver nor a contact model.

Generalized velocity ordering is::

    nu = [v_base(3), omega_base(3), qdot_movable(n)]

All vectors are expressed in the root/base frame.  The base angular momentum
is about the root-frame origin.  URDF joint axes are interpreted in the joint
frame, and inertial origins are interpreted in their owning link frame.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence
import math
import xml.etree.ElementTree as ET

import numpy as np


BACKEND_SCOPE = "PRESCRIBED_JOINT_MOTION_MOMENTUM_PREBIND_NOT_TORQUE_DRIVEN_NOT_CONTACT"
PRODUCTION_DYNAMICS_GATE_PASSED = False


class URDFDynamicsError(ValueError):
    """Raised when the in-memory URDF cannot support audited dynamics."""


@dataclass(frozen=True)
class LinkInertial:
    """A physical link's mass properties in URDF inertial-frame semantics."""

    name: str
    mass_kg: float
    com_link_m: np.ndarray
    rotation_link_inertial: np.ndarray
    inertia_inertial_kg_m2: np.ndarray


@dataclass(frozen=True)
class JointDefinition:
    """A supported URDF tree joint."""

    name: str
    joint_type: str
    parent: str
    child: str
    origin_parent_joint_m: np.ndarray
    rotation_parent_joint: np.ndarray
    axis_joint: np.ndarray


@dataclass(frozen=True)
class JointWorldState:
    """Joint axis and origin expressed in the root frame at one configuration."""

    origin_root_m: np.ndarray
    axis_root: np.ndarray


@dataclass(frozen=True)
class BodyKinematics:
    """CoM geometry and Jacobians for one physical link."""

    link_name: str
    mass_kg: float
    com_root_m: np.ndarray
    inertia_root_kg_m2: np.ndarray
    linear_jacobian: np.ndarray
    angular_jacobian: np.ndarray


@dataclass(frozen=True)
class MassMatrixBlocks:
    """Symmetric generalized mass matrix and its base/joint partitions."""

    full: np.ndarray
    Hbb: np.ndarray
    Hbm: np.ndarray
    Hmb: np.ndarray
    Hmm: np.ndarray


@dataclass(frozen=True)
class MomentumState:
    """Physical system momentum derived from the first six generalized momenta."""

    linear_root_kg_m_s: np.ndarray
    angular_about_root_kg_m2_s: np.ndarray

    @property
    def vector6(self) -> np.ndarray:
        return np.concatenate((self.linear_root_kg_m_s, self.angular_about_root_kg_m2_s))


@dataclass(frozen=True)
class FreeRigidBodyHistory:
    """Deterministic fixed-step RK4 history for a torque-free rigid target."""

    time_s: np.ndarray
    omega_body_rad_s: np.ndarray
    quaternion_body_to_inertial_wxyz: np.ndarray
    angular_momentum_inertial_kg_m2_s: np.ndarray
    kinetic_energy_j: np.ndarray


def _finite_vector(values: Sequence[float], size: int, field: str) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if result.shape != (size,) or not np.all(np.isfinite(result)):
        raise URDFDynamicsError(f"{field} must contain {size} finite values")
    return result


def _parse_triplet(text: str | None, default: Sequence[float], field: str) -> np.ndarray:
    if text is None:
        return _finite_vector(default, 3, field)
    try:
        values = [float(token) for token in text.split()]
    except ValueError as exc:
        raise URDFDynamicsError(f"{field} contains a non-numeric value") from exc
    return _finite_vector(values, 3, field)


def _rotation_from_rpy(rpy: Sequence[float]) -> np.ndarray:
    """URDF fixed-axis RPY rotation: Rz(yaw) @ Ry(pitch) @ Rx(roll)."""

    roll, pitch, yaw = _finite_vector(rpy, 3, "rpy")
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    rx = np.array(((1.0, 0.0, 0.0), (0.0, cr, -sr), (0.0, sr, cr)))
    ry = np.array(((cp, 0.0, sp), (0.0, 1.0, 0.0), (-sp, 0.0, cp)))
    rz = np.array(((cy, -sy, 0.0), (sy, cy, 0.0), (0.0, 0.0, 1.0)))
    return rz @ ry @ rx


def _axis_angle(axis: np.ndarray, angle: float) -> np.ndarray:
    x, y, z = axis
    c = math.cos(float(angle))
    s = math.sin(float(angle))
    one_c = 1.0 - c
    return np.array(
        (
            (c + x * x * one_c, x * y * one_c - z * s, x * z * one_c + y * s),
            (y * x * one_c + z * s, c + y * y * one_c, y * z * one_c - x * s),
            (z * x * one_c - y * s, z * y * one_c + x * s, c + z * z * one_c),
        ),
        dtype=float,
    )


def _transform(rotation: np.ndarray, translation: np.ndarray) -> np.ndarray:
    result = np.eye(4)
    result[:3, :3] = rotation
    result[:3, 3] = translation
    return result


def _skew(vector: np.ndarray) -> np.ndarray:
    x, y, z = vector
    return np.array(((0.0, -z, y), (z, 0.0, -x), (-y, x, 0.0)))


def _origin(node: ET.Element | None, field: str) -> tuple[np.ndarray, np.ndarray]:
    if node is None:
        return np.zeros(3), np.eye(3)
    xyz = _parse_triplet(node.get("xyz"), (0.0, 0.0, 0.0), f"{field}.xyz")
    rpy = _parse_triplet(node.get("rpy"), (0.0, 0.0, 0.0), f"{field}.rpy")
    return xyz, _rotation_from_rpy(rpy)


class URDFTreeDynamics:
    """Auditable tree-model dynamics assembled from an in-memory URDF snapshot."""

    SUPPORTED_JOINT_TYPES = frozenset(("fixed", "revolute", "prismatic"))

    def __init__(self, xml_bytes: bytes):
        if not isinstance(xml_bytes, (bytes, bytearray)) or not xml_bytes:
            raise URDFDynamicsError("a non-empty URDF XML byte snapshot is required")
        self._xml_bytes = bytes(xml_bytes)
        try:
            root = ET.fromstring(self._xml_bytes)
        except ET.ParseError as exc:
            raise URDFDynamicsError("invalid URDF XML byte snapshot") from exc
        if root.tag != "robot":
            raise URDFDynamicsError("URDF root element must be <robot>")
        self.robot_name = root.get("name", "")
        self._parse_links(root)
        self._parse_joints(root)
        self._validate_tree()

    @classmethod
    def from_element(cls, robot: ET.Element) -> "URDFTreeDynamics":
        """Serialize an existing source-built element only to an in-memory snapshot."""

        return cls(ET.tostring(robot, encoding="utf-8"))

    def _parse_links(self, root: ET.Element) -> None:
        link_nodes = root.findall("link")
        names = [node.get("name", "") for node in link_nodes]
        if not names or any(not name for name in names) or len(set(names)) != len(names):
            raise URDFDynamicsError("URDF links must have unique non-empty names")
        self.link_names = tuple(names)
        self._link_nodes = {node.get("name", ""): node for node in link_nodes}
        inertials: dict[str, LinkInertial] = {}
        for name, link in self._link_nodes.items():
            inertial = link.find("inertial")
            if inertial is None:
                continue
            mass_node = inertial.find("mass")
            tensor_node = inertial.find("inertia")
            if mass_node is None or tensor_node is None:
                raise URDFDynamicsError(f"physical link {name} has an incomplete inertial block")
            try:
                mass = float(mass_node.attrib["value"])
                ixx = float(tensor_node.attrib["ixx"])
                ixy = float(tensor_node.attrib["ixy"])
                ixz = float(tensor_node.attrib["ixz"])
                iyy = float(tensor_node.attrib["iyy"])
                iyz = float(tensor_node.attrib["iyz"])
                izz = float(tensor_node.attrib["izz"])
            except (KeyError, ValueError) as exc:
                raise URDFDynamicsError(f"physical link {name} has invalid inertia scalars") from exc
            tensor = np.array(((ixx, ixy, ixz), (ixy, iyy, iyz), (ixz, iyz, izz)), dtype=float)
            if not math.isfinite(mass) or mass <= 0.0 or not np.all(np.isfinite(tensor)):
                raise URDFDynamicsError(f"physical link {name} mass/inertia must be positive and finite")
            tensor = 0.5 * (tensor + tensor.T)
            if np.min(np.linalg.eigvalsh(tensor)) <= 0.0:
                raise URDFDynamicsError(f"physical link {name} inertia tensor is not positive definite")
            com, rotation = _origin(inertial.find("origin"), f"link[{name}].inertial.origin")
            inertials[name] = LinkInertial(name, mass, com, rotation, tensor)
        if not inertials:
            raise URDFDynamicsError("at least one physical link with inertia is required")
        self.inertials = inertials
        self.physical_link_names = tuple(name for name in self.link_names if name in inertials)
        self.frame_only_link_names = tuple(name for name in self.link_names if name not in inertials)

    def _parse_joints(self, root: ET.Element) -> None:
        joints: list[JointDefinition] = []
        seen: set[str] = set()
        for node in root.findall("joint"):
            name = node.get("name", "")
            joint_type = node.get("type", "")
            if not name or name in seen:
                raise URDFDynamicsError("URDF joints must have unique non-empty names")
            if joint_type not in self.SUPPORTED_JOINT_TYPES:
                raise URDFDynamicsError(f"joint {name} has unsupported type {joint_type!r}")
            parent_node, child_node = node.find("parent"), node.find("child")
            if parent_node is None or child_node is None:
                raise URDFDynamicsError(f"joint {name} is missing parent or child")
            parent, child = parent_node.get("link", ""), child_node.get("link", "")
            if parent not in self._link_nodes or child not in self._link_nodes or parent == child:
                raise URDFDynamicsError(f"joint {name} has an invalid parent/child pair")
            xyz, rotation = _origin(node.find("origin"), f"joint[{name}].origin")
            if joint_type == "fixed":
                axis = np.zeros(3)
            else:
                axis_node = node.find("axis")
                axis = _parse_triplet(
                    None if axis_node is None else axis_node.get("xyz"),
                    (1.0, 0.0, 0.0),
                    f"joint[{name}].axis",
                )
                norm = float(np.linalg.norm(axis))
                if norm <= 0.0:
                    raise URDFDynamicsError(f"joint {name} axis must be nonzero")
                axis = axis / norm
            joints.append(JointDefinition(name, joint_type, parent, child, xyz, rotation, axis))
            seen.add(name)
        self.joints = tuple(joints)
        self.joint_names = tuple(joint.name for joint in joints)
        self.movable_joints = tuple(joint for joint in joints if joint.joint_type != "fixed")
        self.movable_joint_names = tuple(joint.name for joint in self.movable_joints)
        self._movable_index = {joint.name: index for index, joint in enumerate(self.movable_joints)}
        self._joint_by_child = {joint.child: joint for joint in joints}
        self._children: dict[str, list[JointDefinition]] = {name: [] for name in self.link_names}
        for joint in joints:
            self._children[joint.parent].append(joint)

    def _validate_tree(self) -> None:
        if len(self._joint_by_child) != len(self.joints):
            raise URDFDynamicsError("a link may not have more than one parent joint")
        child_links = set(self._joint_by_child)
        roots = [name for name in self.link_names if name not in child_links]
        if len(roots) != 1:
            raise URDFDynamicsError(f"URDF must be one tree with one root; found {len(roots)}")
        if len(self.joints) != len(self.link_names) - 1:
            raise URDFDynamicsError("URDF must be a connected acyclic tree")
        self.root_link = roots[0]
        visited: set[str] = set()
        stack = [self.root_link]
        while stack:
            link = stack.pop()
            if link in visited:
                raise URDFDynamicsError("cycle detected in URDF tree")
            visited.add(link)
            stack.extend(joint.child for joint in self._children[link])
        if visited != set(self.link_names):
            raise URDFDynamicsError("URDF contains disconnected links")
        for link in self.physical_link_names:
            current = link
            seen: set[str] = set()
            while current != self.root_link:
                if current in seen or current not in self._joint_by_child:
                    raise URDFDynamicsError(f"cannot resolve ancestor chain for {link}")
                seen.add(current)
                current = self._joint_by_child[current].parent

    @property
    def link_count(self) -> int:
        return len(self.link_names)

    @property
    def joint_count(self) -> int:
        return len(self.joints)

    @property
    def physical_link_count(self) -> int:
        return len(self.physical_link_names)

    @property
    def frame_only_link_count(self) -> int:
        return len(self.frame_only_link_names)

    @property
    def movable_dof(self) -> int:
        return len(self.movable_joints)

    @property
    def total_mass_kg(self) -> float:
        return float(sum(item.mass_kg for item in self.inertials.values()))

    @property
    def backend_scope(self) -> str:
        return BACKEND_SCOPE

    def model_summary(self) -> dict[str, object]:
        return {
            "robot_name": self.robot_name,
            "backend_scope": BACKEND_SCOPE,
            "production_dynamics_gate_passed": PRODUCTION_DYNAMICS_GATE_PASSED,
            "links": self.link_count,
            "joints": self.joint_count,
            "physical_links": self.physical_link_count,
            "frame_only_links": self.frame_only_link_count,
            "fixed_joints": sum(joint.joint_type == "fixed" for joint in self.joints),
            "revolute_joints": sum(joint.joint_type == "revolute" for joint in self.joints),
            "prismatic_joints": sum(joint.joint_type == "prismatic" for joint in self.joints),
            "movable_dof": self.movable_dof,
            "movable_joint_names": list(self.movable_joint_names),
            "total_mass_kg": self.total_mass_kg,
        }

    def _q_vector(self, q: Sequence[float] | Mapping[str, float] | None) -> np.ndarray:
        if q is None:
            return np.zeros(self.movable_dof)
        if isinstance(q, Mapping):
            missing = set(self.movable_joint_names) - set(q)
            extra = set(q) - set(self.movable_joint_names)
            if missing or extra:
                raise URDFDynamicsError(
                    f"joint map must exactly match movable joints; missing={sorted(missing)} extra={sorted(extra)}"
                )
            values = [q[name] for name in self.movable_joint_names]
        else:
            values = q
        return _finite_vector(values, self.movable_dof, "q")

    def _qdot_vector(self, qdot: Sequence[float] | Mapping[str, float]) -> np.ndarray:
        if isinstance(qdot, Mapping):
            missing = set(self.movable_joint_names) - set(qdot)
            extra = set(qdot) - set(self.movable_joint_names)
            if missing or extra:
                raise URDFDynamicsError(
                    f"joint-rate map must exactly match movable joints; missing={sorted(missing)} extra={sorted(extra)}"
                )
            values = [qdot[name] for name in self.movable_joint_names]
        else:
            values = qdot
        return _finite_vector(values, self.movable_dof, "qdot")

    def forward_kinematics(
        self, q: Sequence[float] | Mapping[str, float] | None = None
    ) -> tuple[dict[str, np.ndarray], dict[str, JointWorldState]]:
        """Return root-to-link transforms and root-expressed joint geometry."""

        q_vector = self._q_vector(q)
        transforms: dict[str, np.ndarray] = {self.root_link: np.eye(4)}
        joint_states: dict[str, JointWorldState] = {}
        stack = [self.root_link]
        while stack:
            parent = stack.pop()
            parent_transform = transforms[parent]
            for joint in self._children[parent]:
                joint_transform = parent_transform @ _transform(
                    joint.rotation_parent_joint, joint.origin_parent_joint_m
                )
                axis_root = joint_transform[:3, :3] @ joint.axis_joint
                joint_states[joint.name] = JointWorldState(joint_transform[:3, 3].copy(), axis_root.copy())
                motion = np.eye(4)
                if joint.joint_type == "revolute":
                    motion[:3, :3] = _axis_angle(
                        joint.axis_joint, q_vector[self._movable_index[joint.name]]
                    )
                elif joint.joint_type == "prismatic":
                    motion[:3, 3] = joint.axis_joint * q_vector[self._movable_index[joint.name]]
                transforms[joint.child] = joint_transform @ motion
                stack.append(joint.child)
        return transforms, joint_states

    def _ancestor_joints(self, link_name: str) -> tuple[JointDefinition, ...]:
        ancestors: list[JointDefinition] = []
        current = link_name
        while current != self.root_link:
            joint = self._joint_by_child[current]
            ancestors.append(joint)
            current = joint.parent
        ancestors.reverse()
        return tuple(ancestors)

    def body_kinematics(
        self, q: Sequence[float] | Mapping[str, float] | None = None
    ) -> tuple[BodyKinematics, ...]:
        """Construct each physical body's CoM geometry and full Jacobians."""

        transforms, joint_states = self.forward_kinematics(q)
        width = 6 + self.movable_dof
        bodies: list[BodyKinematics] = []
        for link_name in self.physical_link_names:
            inertial = self.inertials[link_name]
            link_transform = transforms[link_name]
            rotation_root_inertial = link_transform[:3, :3] @ inertial.rotation_link_inertial
            com_root = link_transform[:3, :3] @ inertial.com_link_m + link_transform[:3, 3]
            inertia_root = (
                rotation_root_inertial
                @ inertial.inertia_inertial_kg_m2
                @ rotation_root_inertial.T
            )
            linear = np.zeros((3, width))
            angular = np.zeros((3, width))
            linear[:, :3] = np.eye(3)
            linear[:, 3:6] = -_skew(com_root)
            angular[:, 3:6] = np.eye(3)
            for joint in self._ancestor_joints(link_name):
                if joint.joint_type == "fixed":
                    continue
                column = 6 + self._movable_index[joint.name]
                state = joint_states[joint.name]
                if joint.joint_type == "revolute":
                    linear[:, column] = np.cross(state.axis_root, com_root - state.origin_root_m)
                    angular[:, column] = state.axis_root
                else:
                    linear[:, column] = state.axis_root
            bodies.append(
                BodyKinematics(
                    link_name,
                    inertial.mass_kg,
                    com_root,
                    0.5 * (inertia_root + inertia_root.T),
                    linear,
                    angular,
                )
            )
        return tuple(bodies)

    def mass_matrix(self, q: Sequence[float] | Mapping[str, float] | None = None) -> np.ndarray:
        """Assemble the symmetric base-6 plus movable-joint mass matrix."""

        width = 6 + self.movable_dof
        matrix = np.zeros((width, width))
        for body in self.body_kinematics(q):
            matrix += body.mass_kg * body.linear_jacobian.T @ body.linear_jacobian
            matrix += body.angular_jacobian.T @ body.inertia_root_kg_m2 @ body.angular_jacobian
        matrix = 0.5 * (matrix + matrix.T)
        if not np.all(np.isfinite(matrix)):
            raise URDFDynamicsError("assembled mass matrix contains non-finite values")
        return matrix

    def mass_matrix_blocks(
        self, q: Sequence[float] | Mapping[str, float] | None = None
    ) -> MassMatrixBlocks:
        matrix = self.mass_matrix(q)
        return MassMatrixBlocks(
            matrix,
            matrix[:6, :6],
            matrix[:6, 6:],
            matrix[6:, :6],
            matrix[6:, 6:],
        )

    def base_twist_for_zero_momentum(
        self,
        q: Sequence[float] | Mapping[str, float] | None,
        qdot: Sequence[float] | Mapping[str, float],
    ) -> np.ndarray:
        """Solve ``Vb = -Hbb^-1 Hbm qdot`` for zero initial momentum."""

        qdot_vector = self._qdot_vector(qdot)
        blocks = self.mass_matrix_blocks(q)
        try:
            return np.linalg.solve(blocks.Hbb, -(blocks.Hbm @ qdot_vector))
        except np.linalg.LinAlgError as exc:
            raise URDFDynamicsError("Hbb is singular; zero-momentum base twist is undefined") from exc

    def momentum(
        self,
        q: Sequence[float] | Mapping[str, float] | None,
        base_twist: Sequence[float],
        qdot: Sequence[float] | Mapping[str, float],
    ) -> MomentumState:
        base = _finite_vector(base_twist, 6, "base_twist")
        rates = self._qdot_vector(qdot)
        generalized_momentum = self.mass_matrix(q) @ np.concatenate((base, rates))
        return MomentumState(generalized_momentum[:3], generalized_momentum[3:6])

    def kinetic_energy_j(
        self,
        q: Sequence[float] | Mapping[str, float] | None,
        base_twist: Sequence[float],
        qdot: Sequence[float] | Mapping[str, float],
    ) -> float:
        base = _finite_vector(base_twist, 6, "base_twist")
        rates = self._qdot_vector(qdot)
        velocity = np.concatenate((base, rates))
        return float(0.5 * velocity @ self.mass_matrix(q) @ velocity)

    def perturbed_link_model(
        self,
        link_name: str,
        *,
        mass_scale: float = 1.0,
        inertia_scale: float = 1.0,
        com_delta_link_m: Sequence[float] = (0.0, 0.0, 0.0),
    ) -> "URDFTreeDynamics":
        """Return an in-memory one-link perturbation for source-model sensitivity.

        The original byte snapshot is never mutated and no artifact is written.
        Frame-only links are rejected because they intentionally have no mass.
        """

        if link_name not in self.inertials:
            raise URDFDynamicsError(f"{link_name!r} is not a physical link")
        if not math.isfinite(mass_scale) or mass_scale <= 0.0:
            raise URDFDynamicsError("mass_scale must be positive and finite")
        if not math.isfinite(inertia_scale) or inertia_scale <= 0.0:
            raise URDFDynamicsError("inertia_scale must be positive and finite")
        com_delta = _finite_vector(com_delta_link_m, 3, "com_delta_link_m")
        root = ET.fromstring(self._xml_bytes)
        target = next(link for link in root.findall("link") if link.get("name") == link_name)
        inertial = target.find("inertial")
        if inertial is None:  # pragma: no cover - guarded by parsed inertials
            raise URDFDynamicsError(f"{link_name!r} has no inertial block")
        mass_node = inertial.find("mass")
        tensor_node = inertial.find("inertia")
        assert mass_node is not None and tensor_node is not None
        mass_node.set("value", f"{float(mass_node.attrib['value']) * mass_scale:.17g}")
        for key in ("ixx", "ixy", "ixz", "iyy", "iyz", "izz"):
            tensor_node.set(key, f"{float(tensor_node.attrib[key]) * inertia_scale:.17g}")
        origin_node = inertial.find("origin")
        if origin_node is None:
            origin_node = ET.SubElement(inertial, "origin", {"xyz": "0 0 0", "rpy": "0 0 0"})
        old_com = _parse_triplet(origin_node.get("xyz"), (0.0, 0.0, 0.0), "inertial.origin.xyz")
        origin_node.set("xyz", " ".join(f"{value:.17g}" for value in old_com + com_delta))
        return URDFTreeDynamics(ET.tostring(root, encoding="utf-8"))

    def single_link_sensitivity(
        self,
        q: Sequence[float] | Mapping[str, float] | None,
        link_name: str,
        *,
        mass_scale: float = 1.01,
        inertia_scale: float = 1.01,
        com_delta_link_m: Sequence[float] = (0.0, 0.0, 0.0),
    ) -> dict[str, object]:
        """Quantify a single physical link's effect without changing authority state."""

        source_snapshot_before = self._xml_bytes
        baseline = self.mass_matrix(q)
        perturbed = self.perturbed_link_model(
            link_name,
            mass_scale=mass_scale,
            inertia_scale=inertia_scale,
            com_delta_link_m=com_delta_link_m,
        )
        changed = perturbed.mass_matrix(q)
        delta = changed - baseline
        return {
            "backend_scope": BACKEND_SCOPE,
            "authority_class": "SOURCE_ONLY_CURRENT_MODEL_SENSITIVITY_NOT_BINDING_EVIDENCE",
            "link_name": link_name,
            "baseline_total_mass_kg": self.total_mass_kg,
            "perturbed_total_mass_kg": perturbed.total_mass_kg,
            "mass_matrix_frobenius_delta": float(np.linalg.norm(delta, ord="fro")),
            "Hbb_frobenius_delta": float(np.linalg.norm(delta[:6, :6], ord="fro")),
            "Hbm_frobenius_delta": float(np.linalg.norm(delta[:6, 6:], ord="fro")),
            "original_snapshot_unchanged": self._xml_bytes == source_snapshot_before,
        }


def _validate_inertia(inertia_body_kg_m2: Sequence[Sequence[float]]) -> np.ndarray:
    inertia = np.asarray(inertia_body_kg_m2, dtype=float)
    if inertia.shape != (3, 3) or not np.all(np.isfinite(inertia)):
        raise URDFDynamicsError("target inertia must be a finite 3x3 matrix")
    if not np.allclose(inertia, inertia.T, atol=1.0e-13, rtol=0.0):
        raise URDFDynamicsError("target inertia must be symmetric")
    inertia = 0.5 * (inertia + inertia.T)
    if np.min(np.linalg.eigvalsh(inertia)) <= 0.0:
        raise URDFDynamicsError("target inertia must be positive definite")
    return inertia


def _quaternion_product(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    lw, lx, ly, lz = left
    rw, rx, ry, rz = right
    return np.array(
        (
            lw * rw - lx * rx - ly * ry - lz * rz,
            lw * rx + lx * rw + ly * rz - lz * ry,
            lw * ry - lx * rz + ly * rw + lz * rx,
            lw * rz + lx * ry - ly * rx + lz * rw,
        )
    )


def quaternion_to_rotation_body_to_inertial(quaternion_wxyz: Sequence[float]) -> np.ndarray:
    quaternion = _finite_vector(quaternion_wxyz, 4, "quaternion_wxyz")
    norm = float(np.linalg.norm(quaternion))
    if norm <= 0.0:
        raise URDFDynamicsError("quaternion norm must be nonzero")
    w, x, y, z = quaternion / norm
    return np.array(
        (
            (1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)),
            (2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)),
            (2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)),
        )
    )


def _free_rigid_body_derivative(state: np.ndarray, inertia: np.ndarray) -> np.ndarray:
    omega = state[:3]
    quaternion = state[3:]
    angular_momentum_body = inertia @ omega
    omega_dot = np.linalg.solve(inertia, -np.cross(omega, angular_momentum_body))
    quaternion_dot = 0.5 * _quaternion_product(quaternion, np.array((0.0, *omega)))
    return np.concatenate((omega_dot, quaternion_dot))


def rk4_free_rigid_body_step(
    inertia_body_kg_m2: Sequence[Sequence[float]],
    omega_body_rad_s: Sequence[float],
    quaternion_body_to_inertial_wxyz: Sequence[float],
    step_s: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Advance the torque-free Euler equations by one deterministic RK4 step."""

    inertia = _validate_inertia(inertia_body_kg_m2)
    omega = _finite_vector(omega_body_rad_s, 3, "omega_body_rad_s")
    quaternion = _finite_vector(quaternion_body_to_inertial_wxyz, 4, "quaternion")
    quaternion_norm = float(np.linalg.norm(quaternion))
    if quaternion_norm <= 0.0:
        raise URDFDynamicsError("quaternion norm must be nonzero")
    quaternion = quaternion / quaternion_norm
    if not math.isfinite(step_s) or step_s <= 0.0:
        raise URDFDynamicsError("step_s must be positive and finite")
    state = np.concatenate((omega, quaternion))
    k1 = _free_rigid_body_derivative(state, inertia)
    k2 = _free_rigid_body_derivative(state + 0.5 * step_s * k1, inertia)
    k3 = _free_rigid_body_derivative(state + 0.5 * step_s * k2, inertia)
    k4 = _free_rigid_body_derivative(state + step_s * k3, inertia)
    next_state = state + (step_s / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    next_state[3:] /= np.linalg.norm(next_state[3:])
    return next_state[:3], next_state[3:]


def propagate_free_rigid_body(
    inertia_body_kg_m2: Sequence[Sequence[float]],
    omega_body_initial_rad_s: Sequence[float],
    *,
    step_s: float,
    steps: int,
    quaternion_body_to_inertial_initial_wxyz: Sequence[float] = (1.0, 0.0, 0.0, 0.0),
) -> FreeRigidBodyHistory:
    """Propagate a torque-free target without assuming constant non-principal spin."""

    inertia = _validate_inertia(inertia_body_kg_m2)
    if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
        raise URDFDynamicsError("steps must be a positive integer")
    if not math.isfinite(step_s) or step_s <= 0.0:
        raise URDFDynamicsError("step_s must be positive and finite")
    omega = _finite_vector(omega_body_initial_rad_s, 3, "omega_body_initial_rad_s")
    quaternion = _finite_vector(
        quaternion_body_to_inertial_initial_wxyz, 4, "initial_quaternion"
    )
    norm = float(np.linalg.norm(quaternion))
    if norm <= 0.0:
        raise URDFDynamicsError("initial quaternion norm must be nonzero")
    quaternion = quaternion / norm

    time = np.arange(steps + 1, dtype=float) * step_s
    omega_history = np.empty((steps + 1, 3))
    quaternion_history = np.empty((steps + 1, 4))
    momentum_history = np.empty((steps + 1, 3))
    energy_history = np.empty(steps + 1)

    for index in range(steps + 1):
        omega_history[index] = omega
        quaternion_history[index] = quaternion
        rotation = quaternion_to_rotation_body_to_inertial(quaternion)
        momentum_history[index] = rotation @ (inertia @ omega)
        energy_history[index] = 0.5 * omega @ inertia @ omega
        if index < steps:
            omega, quaternion = rk4_free_rigid_body_step(
                inertia, omega, quaternion, step_s
            )

    return FreeRigidBodyHistory(
        time,
        omega_history,
        quaternion_history,
        momentum_history,
        energy_history,
    )
