"""Strict in-memory parser for the selected Unified-R2 system URDF bytes."""
from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET


EXPECTED_FRAME_ONLY_LINKS = frozenset(
    {"D_BUS_MATE_PHYSICAL", "D_BUS_M6_PATTERN", "M_DYNAMICS_NONPHYSICAL"}
)
EXPECTED_COUNTS = {
    "links": 19,
    "joints": 18,
    "physical_links": 16,
    "frame_only_links": 3,
    "fixed": 10,
    "revolute": 6,
    "prismatic": 2,
    "movable": 8,
}
EXPECTED_TOTAL_MASS_KG = 31.022864807342987
EXPECTED_PHYSICAL_LINKS = frozenset(
    {
        "spacecraft_bus",
        "bus_primary_structure_candidate_v1",
        "load_bridge_candidate",
        "m3r_lumped_link",
        "solar_r2_left_c01_snapshot",
        "solar_r2_right_c01_snapshot",
        "base_link",
        "link1",
        "link2",
        "link3",
        "link4",
        "link5",
        "link6",
        "gripper_link",
        "gripper_left",
        "gripper_right",
    }
)
EXPECTED_JOINT_TREE = {
    "joint1": ("revolute", "base_link", "link1"),
    "joint2": ("revolute", "link1", "link2"),
    "joint3": ("revolute", "link2", "link3"),
    "joint4": ("revolute", "link3", "link4"),
    "joint5": ("revolute", "link4", "link5"),
    "joint6": ("revolute", "link5", "link6"),
    "gripper_joint": ("fixed", "link6", "gripper_link"),
    "gripper_joint1": ("prismatic", "gripper_link", "gripper_left"),
    "gripper_joint2": ("prismatic", "gripper_link", "gripper_right"),
    "bus_to_bus_primary_structure_candidate_v1": (
        "fixed",
        "spacecraft_bus",
        "bus_primary_structure_candidate_v1",
    ),
    "bus_to_D_BUS_MATE_PHYSICAL": (
        "fixed",
        "spacecraft_bus",
        "D_BUS_MATE_PHYSICAL",
    ),
    "D_BUS_MATE_PHYSICAL_to_D_BUS_M6_PATTERN": (
        "fixed",
        "D_BUS_MATE_PHYSICAL",
        "D_BUS_M6_PATTERN",
    ),
    "D_BUS_M6_PATTERN_to_load_bridge_candidate": (
        "fixed",
        "D_BUS_M6_PATTERN",
        "load_bridge_candidate",
    ),
    "load_bridge_candidate_to_m3r_lumped_link": (
        "fixed",
        "load_bridge_candidate",
        "m3r_lumped_link",
    ),
    "m3r_lumped_link_to_base_link": (
        "fixed",
        "m3r_lumped_link",
        "base_link",
    ),
    "bus_to_M_DYNAMICS_NONPHYSICAL": (
        "fixed",
        "spacecraft_bus",
        "M_DYNAMICS_NONPHYSICAL",
    ),
    "bus_to_solar_r2_left_c01_snapshot": (
        "fixed",
        "spacecraft_bus",
        "solar_r2_left_c01_snapshot",
    ),
    "bus_to_solar_r2_right_c01_snapshot": (
        "fixed",
        "spacecraft_bus",
        "solar_r2_right_c01_snapshot",
    ),
}
_UNSAFE_XML_RE = re.compile(br"<!DOCTYPE|<!ENTITY", re.IGNORECASE)


@dataclass(frozen=True)
class SystemState:
    joint_names: tuple[str, ...]
    q: tuple[float, ...]
    dq: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.joint_names) != 8 or len(self.q) != 8 or len(self.dq) != 8:
            raise ValueError("system state must contain exactly eight movable coordinates")
        if any(not math.isfinite(value) for value in (*self.q, *self.dq)):
            raise ValueError("system state values must be finite")


@dataclass(frozen=True)
class SystemModel:
    robot_name: str
    root_link: str
    link_names: tuple[str, ...]
    joint_names: tuple[str, ...]
    physical_link_names: tuple[str, ...]
    frame_only_link_names: tuple[str, ...]
    fixed_joint_names: tuple[str, ...]
    revolute_joint_names: tuple[str, ...]
    prismatic_joint_names: tuple[str, ...]
    movable_joint_names: tuple[str, ...]
    total_mass_kg: float

    @classmethod
    def from_xml_bytes(
        cls,
        payload: bytes,
        *,
        artifact_root: str | Path,
    ) -> "SystemModel":
        if not isinstance(payload, bytes) or not payload.strip():
            raise ValueError("URDF payload must be non-empty bytes")
        if _UNSAFE_XML_RE.search(payload):
            raise ValueError("DOCTYPE and ENTITY declarations are forbidden")
        try:
            root = ET.fromstring(payload)
        except ET.ParseError as exc:
            raise ValueError("URDF XML is not well formed") from exc
        if root.tag != "robot" or set(root.attrib) != {"name"} or not root.attrib["name"]:
            raise ValueError("root must be an exactly named robot element")
        if any("}" in element.tag for element in root.iter()):
            raise ValueError("XML namespaces are not accepted by this frozen parser")

        links = root.findall("link")
        joints = root.findall("joint")
        if len(links) != EXPECTED_COUNTS["links"] or len(joints) != EXPECTED_COUNTS["joints"]:
            raise ValueError("Unified-R2 topology must be exactly 19 links / 18 joints")
        link_names = tuple(_required_name(item, "link") for item in links)
        joint_names = tuple(_required_name(item, "joint") for item in joints)
        if len(set(link_names)) != len(link_names) or len(set(joint_names)) != len(joint_names):
            raise ValueError("link and joint names must be unique")

        physical: list[str] = []
        frames: list[str] = []
        total_mass = 0.0
        asset_root = Path(artifact_root).resolve(strict=False)
        for link in links:
            name = link.attrib["name"]
            inertials = link.findall("inertial")
            has_geometry = bool(link.findall("visual") or link.findall("collision"))
            if inertials:
                if len(inertials) != 1:
                    raise ValueError(f"{name}: physical link must have one inertial")
                physical.append(name)
                mass_nodes = inertials[0].findall("mass")
                if len(mass_nodes) != 1 or set(mass_nodes[0].attrib) != {"value"}:
                    raise ValueError(f"{name}: mass declaration invalid")
                mass = _finite_float(mass_nodes[0].attrib["value"], f"{name}.mass")
                if mass <= 0.0:
                    raise ValueError(f"{name}: physical mass must be positive")
                total_mass += mass
            else:
                if has_geometry or list(link):
                    raise ValueError(f"{name}: frame-only link has inertial/visual/collision or other children")
                frames.append(name)
            _validate_mesh_paths(link, asset_root)

        if len(physical) != EXPECTED_COUNTS["physical_links"]:
            raise ValueError("Unified-R2 must contain exactly 16 physical links")
        if set(physical) != EXPECTED_PHYSICAL_LINKS:
            raise ValueError("Unified-R2 physical-link identity set has drifted")
        if set(frames) != EXPECTED_FRAME_ONLY_LINKS:
            raise ValueError("the exact D/D-pattern/M frame-only set is required")
        if abs(total_mass - EXPECTED_TOTAL_MASS_KG) > 1.0e-12:
            raise ValueError(
                "Unified-R2 total mass must equal the selected 31.022864807342987 kg contract"
            )

        parents: dict[str, str] = {}
        children: dict[str, str] = {}
        joint_tree: dict[str, tuple[str, str, str]] = {}
        joint_origins: dict[str, tuple[float, ...]] = {}
        fixed: list[str] = []
        revolute: list[str] = []
        prismatic: list[str] = []
        link_set = set(link_names)
        for joint in joints:
            name = joint.attrib["name"]
            if set(joint.attrib) != {"name", "type"}:
                raise ValueError(f"{name}: joint attributes must be exactly name/type")
            joint_type = joint.attrib["type"]
            if joint_type not in {"fixed", "revolute", "prismatic"}:
                raise ValueError(f"{name}: unsupported joint type {joint_type}")
            parent_nodes = joint.findall("parent")
            child_nodes = joint.findall("child")
            if len(parent_nodes) != 1 or len(child_nodes) != 1:
                raise ValueError(f"{name}: exactly one parent and child are required")
            if set(parent_nodes[0].attrib) != {"link"} or set(child_nodes[0].attrib) != {"link"}:
                raise ValueError(f"{name}: parent/child attributes invalid")
            parent = parent_nodes[0].attrib["link"]
            child = child_nodes[0].attrib["link"]
            if parent not in link_set or child not in link_set or parent == child:
                raise ValueError(f"{name}: parent/child link reference invalid")
            if child in parents:
                raise ValueError(f"{child}: multiple parent joints are forbidden")
            parents[child] = parent
            children[name] = child
            joint_tree[name] = (joint_type, parent, child)
            joint_origins[name] = _joint_origin_six(joint, name)
            if joint_type == "fixed":
                fixed.append(name)
            elif joint_type == "revolute":
                revolute.append(name)
                _validate_movable_joint(joint, name)
            else:
                prismatic.append(name)
                _validate_movable_joint(joint, name)

        if (len(fixed), len(revolute), len(prismatic)) != (10, 6, 2):
            raise ValueError("joint type counts must be exactly fixed10/revolute6/prismatic2")
        if joint_tree != EXPECTED_JOINT_TREE:
            raise ValueError("Unified-R2 joint identity/type/parent-child tree has drifted")
        roots = [name for name in link_names if name not in parents]
        if roots != ["spacecraft_bus"]:
            raise ValueError("spacecraft_bus must be the unique tree root")
        for name in link_names:
            _path_to_root(name, parents, "spacecraft_bus", len(link_names))

        if "gripper_joint" not in fixed:
            raise ValueError("gripper_joint must remain fixed")
        if "gripper_joint" in revolute or "gripper_joint" in prismatic:
            raise ValueError("gripper_joint cannot enter the movable state")
        movable = tuple(revolute + prismatic)
        if len(movable) != EXPECTED_COUNTS["movable"]:
            raise ValueError("state dimension must be exactly 8 movable joints")

        base_path = _path_to_root("base_link", parents, "spacecraft_bus", len(link_names))
        expected_load_path = (
            "spacecraft_bus",
            "D_BUS_MATE_PHYSICAL",
            "D_BUS_M6_PATTERN",
            "load_bridge_candidate",
            "m3r_lumped_link",
            "base_link",
        )
        if tuple(base_path) != expected_load_path:
            raise ValueError("B601 physical load path does not follow S-D-pattern-bridge-M3R-base")
        if "M_DYNAMICS_NONPHYSICAL" in base_path:
            raise ValueError("physical load path may not traverse M_DYNAMICS_NONPHYSICAL")
        m_path = _path_to_root(
            "M_DYNAMICS_NONPHYSICAL", parents, "spacecraft_bus", len(link_names)
        )
        if tuple(m_path) != ("spacecraft_bus", "M_DYNAMICS_NONPHYSICAL"):
            raise ValueError("M_DYNAMICS_NONPHYSICAL must be an independent bus child")
        descendants_of_m = [
            name
            for name in link_names
            if name != "M_DYNAMICS_NONPHYSICAL"
            and "M_DYNAMICS_NONPHYSICAL"
            in _path_to_root(name, parents, "spacecraft_bus", len(link_names))
        ]
        if descendants_of_m:
            raise ValueError("no physical or frame link may be attached below M_DYNAMICS_NONPHYSICAL")
        d_transform = joint_origins["bus_to_D_BUS_MATE_PHYSICAL"]
        m_transform = joint_origins["bus_to_M_DYNAMICS_NONPHYSICAL"]
        if any(abs(left - right) > 1.0e-12 for left, right in zip(d_transform, m_transform)):
            raise ValueError("D and M must retain equal numeric transforms but distinct identities")

        return cls(
            robot_name=root.attrib["name"],
            root_link="spacecraft_bus",
            link_names=link_names,
            joint_names=joint_names,
            physical_link_names=tuple(physical),
            frame_only_link_names=tuple(frames),
            fixed_joint_names=tuple(fixed),
            revolute_joint_names=tuple(revolute),
            prismatic_joint_names=tuple(prismatic),
            movable_joint_names=movable,
            total_mass_kg=total_mass,
        )

    def zero_state(self) -> SystemState:
        zeros = (0.0,) * len(self.movable_joint_names)
        return SystemState(self.movable_joint_names, zeros, zeros)


def _required_name(element: ET.Element, label: str) -> str:
    expected_attributes = {"name", "type"} if label == "joint" else {"name"}
    if set(element.attrib) != expected_attributes or not element.attrib["name"]:
        raise ValueError(f"{label} must have exactly one non-empty name attribute")
    return element.attrib["name"]


def _finite_float(value: str, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label}: not numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"{label}: non-finite")
    return result


def _validate_movable_joint(joint: ET.Element, name: str) -> None:
    axes = joint.findall("axis")
    limits = joint.findall("limit")
    if len(axes) != 1 or set(axes[0].attrib) != {"xyz"}:
        raise ValueError(f"{name}: movable joint needs one xyz axis")
    axis = tuple(_finite_float(item, f"{name}.axis") for item in axes[0].attrib["xyz"].split())
    if len(axis) != 3 or math.sqrt(sum(value * value for value in axis)) <= 0.0:
        raise ValueError(f"{name}: joint axis must be a non-zero 3-vector")
    if len(limits) != 1:
        raise ValueError(f"{name}: movable joint needs one limit element")
    required = {"lower", "upper", "effort", "velocity"}
    if set(limits[0].attrib) != required:
        raise ValueError(f"{name}: limit fields must be exactly {sorted(required)}")
    values = {key: _finite_float(limits[0].attrib[key], f"{name}.{key}") for key in required}
    if values["lower"] > values["upper"] or values["effort"] <= 0.0 or values["velocity"] <= 0.0:
        raise ValueError(f"{name}: invalid joint limit ordering/capacity")


def _joint_origin_six(joint: ET.Element, name: str) -> tuple[float, ...]:
    origins = joint.findall("origin")
    if len(origins) != 1 or set(origins[0].attrib) != {"xyz", "rpy"}:
        raise ValueError(f"{name}: exactly one xyz/rpy origin is required")
    xyz = tuple(_finite_float(value, f"{name}.origin.xyz") for value in origins[0].attrib["xyz"].split())
    rpy = tuple(_finite_float(value, f"{name}.origin.rpy") for value in origins[0].attrib["rpy"].split())
    if len(xyz) != 3 or len(rpy) != 3:
        raise ValueError(f"{name}: origin xyz/rpy must each contain three values")
    return xyz + rpy


def _validate_mesh_paths(link: ET.Element, artifact_root: Path) -> None:
    for mesh in link.findall("./visual/geometry/mesh") + link.findall("./collision/geometry/mesh"):
        filename = mesh.attrib.get("filename")
        if not filename or "://" in filename or Path(filename).is_absolute():
            raise ValueError("mesh filename must be a non-empty local relative path")
        path = (artifact_root / filename).resolve(strict=False)
        try:
            path.relative_to(artifact_root)
        except ValueError as exc:
            raise ValueError("mesh path escapes the URDF artifact directory") from exc
        if not path.is_file():
            raise ValueError(f"mesh file is missing: {filename}")


def _path_to_root(
    node: str,
    parents: dict[str, str],
    root: str,
    maximum_nodes: int,
) -> list[str]:
    path = [node]
    seen = {node}
    while path[-1] != root:
        parent = parents.get(path[-1])
        if parent is None or parent in seen or len(path) > maximum_nodes:
            raise ValueError("URDF graph is disconnected or cyclic")
        path.append(parent)
        seen.add(parent)
    path.reverse()
    return path


__all__ = [
    "EXPECTED_COUNTS",
    "EXPECTED_FRAME_ONLY_LINKS",
    "EXPECTED_JOINT_TREE",
    "EXPECTED_PHYSICAL_LINKS",
    "EXPECTED_TOTAL_MASS_KG",
    "SystemModel",
    "SystemState",
]
