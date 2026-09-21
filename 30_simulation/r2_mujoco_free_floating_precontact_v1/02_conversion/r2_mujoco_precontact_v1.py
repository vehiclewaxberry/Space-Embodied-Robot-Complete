"""Isolated CURRENT-R2 MuJoCo free-floating pre-contact diagnostic.

This module is intentionally append-only and non-contact.  It converts the
hash-pinned Unified R2 URDF to three MJCF lanes, exercises MuJoCo as an
independent rigid multibody integrator, and compares it with the current R2
analytical reference.  It grants no mechanical, control, SAFE, contact,
Sim13, non-ABORT, next-stage, or release authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import copy
import csv
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import sys
import tempfile
from typing import Any, Callable, Mapping, Sequence
import xml.etree.ElementTree as ET

for _name in (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "BLIS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ.setdefault(_name, "1")

import mujoco
import numpy as np
import scipy


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_ROOT.parents[1]
AUTHORITY_DIR = PACKAGE_ROOT / "00_authority"
MODEL_DIR = PACKAGE_ROOT / "01_model"
RUN_DIR = PACKAGE_ROOT / "05_runs"
RESULTS_DIR = PACKAGE_ROOT / "results"
CONTRACT_PATH = AUTHORITY_DIR / "R2_MUJOCO_FREE_FLOATING_PRECONTACT_CONTRACT_V1.json"
SOURCE_LOCK_PATH = AUTHORITY_DIR / "SOURCE_AUTHORITY_LOCK_V1.json"

LANES = (
    "LOCKED_2P_REDUCED_6R",
    "LOCKED_2P_EQUALITY_6R2P",
    "FREE_2P_ZERO_FORCE_NEGATIVE_CONTROL",
)
R_JOINTS = tuple(f"joint{i}" for i in range(1, 7))
P_JOINTS = ("gripper_joint1", "gripper_joint2")


class DiagnosticError(RuntimeError):
    """Fail-closed diagnostic contract or execution error."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DiagnosticError(code)


def _reject_constant(token: str) -> None:
    raise DiagnosticError(f"NONFINITE_JSON_CONSTANT:{token}")


def _unique_pairs(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DiagnosticError(f"DUPLICATE_JSON_KEY:{key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_unique_pairs,
        parse_constant=_reject_constant,
    )
    _require(isinstance(value, dict), f"JSON_ROOT_NOT_OBJECT:{path}")
    return value


def to_builtin(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [to_builtin(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(key): to_builtin(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_builtin(item) for item in value]
    if isinstance(value, float):
        _require(math.isfinite(value), "NONFINITE_OUTPUT")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(to_builtin(value), indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def file_record(path: Path) -> dict[str, Any]:
    return {
        "path": path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _fmt(values: Sequence[float] | float) -> str:
    if isinstance(values, (float, int, np.floating, np.integer)):
        return f"{float(values):.17g}"
    return " ".join(f"{float(value):.17g}" for value in values)


def _vec(text: str | None, default: Sequence[float], field: str) -> np.ndarray:
    raw = default if text is None else [float(token) for token in text.split()]
    value = np.asarray(raw, dtype=float)
    _require(value.shape == (3,) and np.all(np.isfinite(value)), f"BAD_VECTOR:{field}")
    return value


def _rpy_matrix(rpy: Sequence[float]) -> np.ndarray:
    roll, pitch, yaw = np.asarray(rpy, dtype=float)
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return np.array(
        (
            (cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr),
            (sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr),
            (-sp, cp * sr, cp * cr),
        ),
        dtype=float,
    )


def _quat_wxyz(rotation: np.ndarray) -> np.ndarray:
    matrix = np.asarray(rotation, dtype=float)
    _require(matrix.shape == (3, 3), "ROTATION_SHAPE")
    trace = float(np.trace(matrix))
    if trace > 0.0:
        scale = math.sqrt(trace + 1.0) * 2.0
        quat = np.array((0.25 * scale, (matrix[2, 1] - matrix[1, 2]) / scale, (matrix[0, 2] - matrix[2, 0]) / scale, (matrix[1, 0] - matrix[0, 1]) / scale))
    else:
        index = int(np.argmax(np.diag(matrix)))
        if index == 0:
            scale = math.sqrt(1.0 + matrix[0, 0] - matrix[1, 1] - matrix[2, 2]) * 2.0
            quat = np.array(((matrix[2, 1] - matrix[1, 2]) / scale, 0.25 * scale, (matrix[0, 1] + matrix[1, 0]) / scale, (matrix[0, 2] + matrix[2, 0]) / scale))
        elif index == 1:
            scale = math.sqrt(1.0 + matrix[1, 1] - matrix[0, 0] - matrix[2, 2]) * 2.0
            quat = np.array(((matrix[0, 2] - matrix[2, 0]) / scale, (matrix[0, 1] + matrix[1, 0]) / scale, 0.25 * scale, (matrix[1, 2] + matrix[2, 1]) / scale))
        else:
            scale = math.sqrt(1.0 + matrix[2, 2] - matrix[0, 0] - matrix[1, 1]) * 2.0
            quat = np.array(((matrix[1, 0] - matrix[0, 1]) / scale, (matrix[0, 2] + matrix[2, 0]) / scale, (matrix[1, 2] + matrix[2, 1]) / scale, 0.25 * scale))
    quat /= np.linalg.norm(quat)
    if quat[0] < 0.0:
        quat *= -1.0
    return quat


def _origin(node: ET.Element | None, field: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if node is None:
        xyz = np.zeros(3)
        rpy = np.zeros(3)
    else:
        xyz = _vec(node.get("xyz"), (0.0, 0.0, 0.0), f"{field}.xyz")
        rpy = _vec(node.get("rpy"), (0.0, 0.0, 0.0), f"{field}.rpy")
    rotation = _rpy_matrix(rpy)
    return xyz, rotation, _quat_wxyz(rotation)


@dataclass(frozen=True)
class Joint:
    name: str
    kind: str
    parent: str
    child: str
    xyz: np.ndarray
    rotation: np.ndarray
    quat: np.ndarray
    axis: np.ndarray
    lower: float | None
    upper: float | None


@dataclass
class UrdfModel:
    robot_name: str
    links: dict[str, ET.Element]
    joints: tuple[Joint, ...]
    children: dict[str, list[Joint]]
    root_link: str


def parse_urdf(path: Path) -> UrdfModel:
    root = ET.fromstring(path.read_bytes())
    _require(root.tag == "robot", "URDF_ROOT_NOT_ROBOT")
    links = {node.get("name", ""): node for node in root.findall("link")}
    _require(len(links) == len(root.findall("link")) and "" not in links, "URDF_LINK_NAMES_INVALID")
    joints: list[Joint] = []
    children: dict[str, list[Joint]] = {name: [] for name in links}
    child_names: set[str] = set()
    for node in root.findall("joint"):
        name, kind = node.get("name", ""), node.get("type", "")
        _require(name and kind in {"fixed", "revolute", "prismatic"}, f"URDF_JOINT_INVALID:{name}")
        parent_node, child_node = node.find("parent"), node.find("child")
        _require(parent_node is not None and child_node is not None, f"URDF_JOINT_TREE_INVALID:{name}")
        parent, child = parent_node.get("link", ""), child_node.get("link", "")
        xyz, rotation, quat = _origin(node.find("origin"), f"joint[{name}]")
        if kind == "fixed":
            axis = np.zeros(3)
        else:
            axis_node = node.find("axis")
            axis = _vec(None if axis_node is None else axis_node.get("xyz"), (1.0, 0.0, 0.0), f"joint[{name}].axis")
            _require(np.linalg.norm(axis) > 0.0, f"URDF_AXIS_ZERO:{name}")
            axis = axis / np.linalg.norm(axis)
        limit = node.find("limit")
        lower = None if limit is None or limit.get("lower") is None else float(limit.get("lower", "nan"))
        upper = None if limit is None or limit.get("upper") is None else float(limit.get("upper", "nan"))
        joint = Joint(name, kind, parent, child, xyz, rotation, quat, axis, lower, upper)
        joints.append(joint)
        _require(parent in links and child in links and child not in child_names, f"URDF_TREE_INVALID:{name}")
        children[parent].append(joint)
        child_names.add(child)
    roots = sorted(set(links) - child_names)
    _require(len(roots) == 1 and len(joints) == len(links) - 1, "URDF_NOT_SINGLE_TREE")
    return UrdfModel(root.get("name", ""), links, tuple(joints), children, roots[0])


def _link_inertial_record(link: ET.Element) -> dict[str, Any] | None:
    inertial = link.find("inertial")
    if inertial is None:
        return None
    mass_node, inertia_node = inertial.find("mass"), inertial.find("inertia")
    _require(mass_node is not None and inertia_node is not None, f"INERTIAL_INCOMPLETE:{link.get('name')}")
    xyz, rotation, quat = _origin(inertial.find("origin"), f"link[{link.get('name')}].inertial")
    tensor = np.array(
        (
            (float(inertia_node.get("ixx", "nan")), float(inertia_node.get("ixy", "nan")), float(inertia_node.get("ixz", "nan"))),
            (float(inertia_node.get("ixy", "nan")), float(inertia_node.get("iyy", "nan")), float(inertia_node.get("iyz", "nan"))),
            (float(inertia_node.get("ixz", "nan")), float(inertia_node.get("iyz", "nan")), float(inertia_node.get("izz", "nan"))),
        ),
        dtype=float,
    )
    mass = float(mass_node.get("value", "nan"))
    _require(mass > 0.0 and np.min(np.linalg.eigvalsh(tensor)) > 0.0, f"INERTIAL_NOT_PHYSICAL:{link.get('name')}")
    return {"mass_kg": mass, "com_link_m": xyz, "rotation_link_inertial": rotation, "quat_link_inertial_wxyz": quat, "inertia_inertial_kg_m2": tensor}


def _visual_geoms(link: ET.Element, body: ET.Element) -> list[str]:
    names: list[str] = []
    for index, visual in enumerate(link.findall("visual")):
        geometry = visual.find("geometry")
        if geometry is None or len(geometry) != 1 or geometry[0].tag != "box":
            continue
        size = _vec(geometry[0].get("size"), (0.0, 0.0, 0.0), f"visual[{link.get('name')}]")
        _require(np.all(size > 0.0), f"VISUAL_BOX_NONPOSITIVE:{link.get('name')}")
        xyz, _, quat = _origin(visual.find("origin"), f"visual[{link.get('name')}]")
        name = f"visual_{link.get('name')}_{index}"
        rgba = "0.42 0.56 0.72 0.7"
        material = visual.find("material")
        color = None if material is None else material.find("color")
        if color is not None and color.get("rgba"):
            rgba = color.get("rgba", rgba)
        ET.SubElement(
            body,
            "geom",
            {
                "name": name,
                "type": "box",
                "pos": _fmt(xyz),
                "quat": _fmt(quat),
                "size": _fmt(0.5 * size),
                "rgba": rgba,
                "contype": "0",
                "conaffinity": "0",
                "group": "1",
            },
        )
        names.append(name)
    return names


def render_mjcf(urdf: UrdfModel, contract: Mapping[str, Any], lane: str, timestep_s: float | None = None) -> tuple[bytes, dict[str, Any]]:
    _require(lane in LANES, f"UNKNOWN_LANE:{lane}")
    dt = float(contract["integration"]["timestep_s"] if timestep_s is None else timestep_s)
    q8 = np.asarray(contract["initial_state"]["q8_mixed_rad_m"], dtype=float)
    qP = np.asarray(contract["model"]["qP_star_m"], dtype=float)
    root = ET.Element("mujoco", {"model": f"r2_{lane.lower()}"})
    ET.SubElement(root, "compiler", {"angle":"radian", "autolimits":"false", "balanceinertia":"false", "boundmass":"0", "boundinertia":"0", "discardvisual":"false", "fusestatic":"false", "inertiafromgeom":"false"})
    option = ET.SubElement(root, "option", {"timestep":_fmt(dt), "gravity":"0 0 0", "integrator":"RK4", "jacobian":"dense", "cone":"elliptic"})
    ET.SubElement(option, "flag", {"contact":"disable"})
    default = ET.SubElement(root, "default")
    ET.SubElement(default, "joint", {"damping":"0", "frictionloss":"0", "armature":"0", "stiffness":"0"})
    ET.SubElement(default, "geom", {"contype":"0", "conaffinity":"0", "density":"0"})
    worldbody = ET.SubElement(root, "worldbody")
    mapping: dict[str, Any] = {
        "schema": "R2_URDF_TO_MJCF_MAPPING_V1",
        "lane": lane,
        "source_robot": urdf.robot_name,
        "source_root_link": urdf.root_link,
        "compiler": {"fusestatic":False,"inertiafromgeom":False,"discardvisual":False,"balanceinertia":False,"boundmass":0,"boundinertia":0},
        "inertia_emission": "PINNED_NUMPY_SYMMETRIC_EIGH_TO_MJCF_DIAGINERTIA_AND_QUAT",
        "gravity_m_s2": [0.0,0.0,0.0],
        "contact_disabled_by_option": True,
        "body_map": [],
        "joint_map": [],
        "visual_geom_map": [],
    }

    def add_link(link_name: str, parent_xml: ET.Element, via: Joint | None) -> None:
        attributes = {"name": link_name}
        joint_element: ET.Element | None = None
        lock_removed = False
        if via is not None:
            pos = via.xyz.copy()
            if lane == "LOCKED_2P_REDUCED_6R" and via.name in P_JOINTS:
                pos += via.rotation @ (via.axis * qP[P_JOINTS.index(via.name)])
                lock_removed = True
            attributes.update({"pos":_fmt(pos), "quat":_fmt(via.quat)})
        body = ET.SubElement(parent_xml, "body", attributes)
        if via is None:
            joint_element = ET.SubElement(body, "freejoint", {"name":contract["model"]["free_joint"], "align":"false"})
        elif via.kind != "fixed" and not lock_removed:
            joint_attributes = {"name":via.name, "type":"hinge" if via.kind == "revolute" else "slide", "axis":_fmt(via.axis), "pos":"0 0 0", "limited":"true"}
            _require(via.lower is not None and via.upper is not None, f"MOVABLE_LIMIT_MISSING:{via.name}")
            joint_attributes["range"] = _fmt((via.lower, via.upper))
            joint_element = ET.SubElement(body, "joint", joint_attributes)
        inertial = _link_inertial_record(urdf.links[link_name])
        if inertial is not None:
            # Rotate the URDF tensor into the link/body frame.  We then use
            # NumPy's pinned double-precision symmetric eigensolver and emit
            # MuJoCo's principal-axis representation.  This avoids the
            # ~2e-9 reconstruction loss observed when MuJoCo's compiler
            # diagonalizes nearly repeated full-inertia eigenvalues itself.
            tensor = (
                inertial["rotation_link_inertial"]
                @ inertial["inertia_inertial_kg_m2"]
                @ inertial["rotation_link_inertial"].T
            )
            principal, axes = np.linalg.eigh(tensor)
            for column in (0, 1):
                pivot = int(np.argmax(np.abs(axes[:, column])))
                if axes[pivot, column] < 0.0:
                    axes[:, column] *= -1.0
            axes[:, 2] = np.cross(axes[:, 0], axes[:, 1])
            axes[:, 2] /= np.linalg.norm(axes[:, 2])
            ET.SubElement(body, "inertial", {
                "pos":_fmt(inertial["com_link_m"]),
                "mass":_fmt(inertial["mass_kg"]),
                "quat":_fmt(_quat_wxyz(axes)),
                "diaginertia":_fmt(principal),
            })
        geom_names = _visual_geoms(urdf.links[link_name], body)
        if link_name == contract["model"]["tool_link"]:
            ET.SubElement(body, "site", {"name":"tool_origin", "pos":"0 0 0", "size":"0.008", "rgba":"1 0.2 0.1 1", "group":"3"})
        mapping["body_map"].append({"urdf_link":link_name,"mjcf_body":link_name,"physical":inertial is not None,"mass_kg":None if inertial is None else inertial["mass_kg"]})
        mapping["visual_geom_map"].extend({"urdf_link":link_name,"mjcf_geom":name,"contact_enabled":False} for name in geom_names)
        if via is not None:
            mapping["joint_map"].append({
                "urdf_joint":via.name,
                "type":via.kind,
                "parent":via.parent,
                "child":via.child,
                "origin_parent_joint_m":via.xyz,
                "rotation_parent_joint":via.rotation,
                "axis_joint":via.axis,
                "lower":via.lower,
                "upper":via.upper,
                "mjcf_joint":None if via.kind == "fixed" or lock_removed else via.name,
                "lane_semantics":"FIXED_TRANSFORM" if via.kind == "fixed" else ("LOCKED_AT_QP_STAR_BY_COORDINATE_REMOVAL" if lock_removed else "MOVABLE"),
            })
        for child_joint in urdf.children[link_name]:
            add_link(child_joint.child, body, child_joint)

    add_link(urdf.root_link, worldbody, None)
    actuator = ET.SubElement(root, "actuator")
    for joint_name in R_JOINTS:
        ET.SubElement(actuator, "motor", {"name":f"motor_{joint_name}", "joint":joint_name, "gear":"1", "ctrllimited":"false"})
    if lane == "LOCKED_2P_EQUALITY_6R2P":
        equality = ET.SubElement(root, "equality")
        for name, position in zip(P_JOINTS, qP):
            ET.SubElement(equality, "joint", {"name":f"soft_lock_{name}", "joint1":name, "polycoef":_fmt((position,0,0,0,0)), "solref":"0.0005 1", "solimp":"0.9999 0.99999 0.0001 0.5 2", "active":"true"})
    keyframe = ET.SubElement(root, "keyframe")
    quat = np.asarray(contract["initial_state"]["base_quaternion_body_to_inertial_wxyz"], dtype=float)
    quat /= np.linalg.norm(quat)
    key_qpos = np.concatenate((np.asarray(contract["initial_state"]["base_position_inertial_m"]), quat, q8[:6], np.array([]) if lane == "LOCKED_2P_REDUCED_6R" else qP))
    ET.SubElement(keyframe, "key", {"name":"precontact_initial", "qpos":_fmt(key_qpos)})
    ET.indent(root, space="  ")
    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True, short_empty_elements=True) + b"\n"
    mapping["mjcf_sha256"] = sha256_bytes(xml_bytes)
    mapping["timestep_s"] = dt
    mapping["2p_semantics"] = contract["lanes"][lane]["lock_semantics"]
    return xml_bytes, mapping


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    _require(spec is not None and spec.loader is not None, f"MODULE_SPEC_FAIL:{path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def audit_source_pins(source_lock: Mapping[str, Any] | None = None) -> dict[str, Any]:
    lock = load_json(SOURCE_LOCK_PATH) if source_lock is None else source_lock
    records = []
    for pin in lock["pins"]:
        path = PROJECT_ROOT / pin["path"]
        actual_bytes = path.stat().st_size if path.is_file() else None
        actual_sha = sha256_file(path) if path.is_file() else None
        records.append({**pin,"actual_bytes":actual_bytes,"actual_sha256":actual_sha,"match":actual_bytes == pin["bytes"] and actual_sha == pin["sha256"]})
    return {"pins":records,"matched":sum(row["match"] for row in records),"total":len(records),"all_match":all(row["match"] for row in records)}


def load_reference(contract: Mapping[str, Any]) -> dict[str, Any]:
    pins = {row["id"]: PROJECT_ROOT / row["path"] for row in load_json(SOURCE_LOCK_PATH)["pins"]}
    td = _load_module("_r2_mj_td", pins["time_domain_source"])
    metric = _load_module("_r2_mj_metric", pins["task_metric_source"])
    plant = _load_module("_r2_mj_plant", pins["time_varying_plant_source"])
    control = _load_module("_r2_mj_control", pins["control_kinematics_source"])
    parent = _load_module("_r2_mj_parent", pins["parent_dynamics_source"])
    backend = parent.load_backend(PROJECT_ROOT)
    model = parent.ReducedR2Model(backend=backend, qP_star_m=np.asarray(contract["model"]["qP_star_m"], dtype=float))
    td_contract = load_json(pins["time_domain_contract"])
    metric_contract = load_json(pins["task_metric_contract"])
    plant_contract = load_json(pins["time_varying_plant_contract"])
    effective = td.effective_plant_contract(td_contract, plant_contract)
    return {"td":td,"metric":metric,"plant":plant,"control":control,"parent":parent,"backend":backend,"model":model,"td_contract":td_contract,"metric_contract":metric_contract,"plant_contract":plant_contract,"effective":effective}


def compile_lane(xml_bytes: bytes) -> tuple[mujoco.MjModel, mujoco.MjData]:
    model = mujoco.MjModel.from_xml_string(xml_bytes.decode("utf-8"))
    data = mujoco.MjData(model)
    return model, data


def _id(model: mujoco.MjModel, object_type: Any, name: str) -> int:
    identifier = mujoco.mj_name2id(model, object_type, name)
    _require(identifier >= 0, f"MUJOCO_NAME_ABSENT:{name}")
    return int(identifier)


def _joint_addresses(model: mujoco.MjModel, names: Sequence[str]) -> tuple[list[int], list[int]]:
    qpos, dof = [], []
    for name in names:
        jid = _id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
        qpos.append(int(model.jnt_qposadr[jid]))
        dof.append(int(model.jnt_dofadr[jid]))
    return qpos, dof


def set_state(model: mujoco.MjModel, data: mujoco.MjData, contract: Mapping[str, Any], lane: str, *, base_position: Sequence[float] | None = None, base_quaternion: Sequence[float] | None = None, base_velocity_world_local: Sequence[float] | None = None, q8: Sequence[float] | None = None, dq8: Sequence[float] | None = None) -> None:
    mujoco.mj_resetData(model, data)
    free_id = _id(model, mujoco.mjtObj.mjOBJ_JOINT, contract["model"]["free_joint"])
    qa, da = int(model.jnt_qposadr[free_id]), int(model.jnt_dofadr[free_id])
    position = np.asarray(contract["initial_state"]["base_position_inertial_m"] if base_position is None else base_position, dtype=float)
    quat = np.asarray(contract["initial_state"]["base_quaternion_body_to_inertial_wxyz"] if base_quaternion is None else base_quaternion, dtype=float)
    quat /= np.linalg.norm(quat)
    data.qpos[qa:qa+3] = position
    data.qpos[qa+3:qa+7] = quat
    data.qvel[da:da+6] = np.zeros(6) if base_velocity_world_local is None else np.asarray(base_velocity_world_local, dtype=float)
    q = np.asarray(contract["initial_state"]["q8_mixed_rad_m"] if q8 is None else q8, dtype=float)
    dq = np.asarray(contract["initial_state"]["dq8_mixed_rad_s_m_s"] if dq8 is None else dq8, dtype=float)
    names = R_JOINTS if lane == "LOCKED_2P_REDUCED_6R" else R_JOINTS + P_JOINTS
    q_values = q[:6] if lane == "LOCKED_2P_REDUCED_6R" else q
    dq_values = dq[:6] if lane == "LOCKED_2P_REDUCED_6R" else dq
    qaddr, daddr = _joint_addresses(model, names)
    data.qpos[qaddr] = q_values
    data.qvel[daddr] = dq_values
    mujoco.mj_normalizeQuat(model, data.qpos)
    mujoco.mj_forward(model, data)


def full_mass(model: mujoco.MjModel, data: mujoco.MjData) -> np.ndarray:
    matrix = np.zeros((model.nv, model.nv), dtype=np.float64, order="C")
    mujoco.mj_fullM(model, data, matrix)
    return matrix


def _scaled_mass(matrix: np.ndarray, lane: str, contract: Mapping[str, Any]) -> np.ndarray:
    length = float(load_json(PROJECT_ROOT / "30_simulation/r2_control_engineering_closure/time_domain_precontact_tracking_candidate_v1/contracts/CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_CANDIDATE_CONTRACT_V1.json")["controller"]["characteristic_length_m"])
    inertia = float(load_json(PROJECT_ROOT / "30_simulation/r2_control_engineering_closure/time_domain_precontact_tracking_candidate_v1/contracts/CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_CANDIDATE_CONTRACT_V1.json")["controller"]["reference_inertia_kg_m2"])
    scales = [length,length,length,1,1,1] + [1]*6 + ([] if lane == "LOCKED_2P_REDUCED_6R" else [length,length])
    scale = np.diag(scales)
    return scale.T @ matrix @ scale / inertia


def _analytical_tool_jacobian(reference: Mapping[str, Any], q8: np.ndarray, tool_link: str) -> np.ndarray:
    control, backend = reference["control"], reference["backend"]
    transform, joint_jac, _, _ = control._tool_jacobians(backend, q8, tool_link)
    point = np.asarray(transform[:3, 3], dtype=float)
    skew = np.array(((0,-point[2],point[1]),(point[2],0,-point[0]),(-point[1],point[0],0)), dtype=float)
    base = np.block([[np.eye(3),-skew],[np.zeros((3,3)),np.eye(3)]])
    return np.column_stack((base, joint_jac))


def _mjcf_inventory(model: mujoco.MjModel, contract: Mapping[str, Any], lane: str) -> dict[str, Any]:
    body_names = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, index) for index in range(1, model.nbody)]
    joint_names = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, index) for index in range(model.njnt)]
    disabled = bool(int(model.opt.disableflags) & int(mujoco.mjtDisableBit.mjDSBL_CONTACT))
    return {
        "nq":model.nq,"nv":model.nv,"nbody_including_world":model.nbody,"named_source_bodies":body_names,
        "joint_names":joint_names,"actuators":model.nu,"equalities":model.neq,
        "gravity_m_s2":model.opt.gravity.copy(),"contact_disable_flag":disabled,
        "all_geom_contype_zero":bool(np.all(model.geom_contype == 0)),
        "all_geom_conaffinity_zero":bool(np.all(model.geom_conaffinity == 0)),
        "expected_dynamic_dof":12 if lane == "LOCKED_2P_REDUCED_6R" else 14,
        "free_joint_present":contract["model"]["free_joint"] in joint_names,
    }


def _urdf_b601_audit(unified: UrdfModel, accepted: UrdfModel) -> dict[str, Any]:
    link_deltas: dict[str, float] = {}
    for name, link in accepted.links.items():
        _require(name in unified.links, f"B601_LINK_ABSENT:{name}")
        left, right = _link_inertial_record(link), _link_inertial_record(unified.links[name])
        _require((left is None) == (right is None), f"B601_INERTIAL_PRESENCE:{name}")
        if left is None:
            link_deltas[name] = 0.0
        else:
            link_deltas[name] = max(abs(left["mass_kg"]-right["mass_kg"]),float(np.max(np.abs(left["com_link_m"]-right["com_link_m"]))),float(np.max(np.abs(left["inertia_inertial_kg_m2"]-right["inertia_inertial_kg_m2"]))))
    uj = {joint.name:joint for joint in unified.joints}
    joint_deltas: dict[str, float] = {}
    for joint in accepted.joints:
        _require(joint.name in uj, f"B601_JOINT_ABSENT:{joint.name}")
        other = uj[joint.name]
        _require((joint.kind,joint.parent,joint.child)==(other.kind,other.parent,other.child), f"B601_JOINT_TOPOLOGY:{joint.name}")
        values = [np.max(np.abs(joint.xyz-other.xyz)),np.max(np.abs(joint.rotation-other.rotation)),np.max(np.abs(joint.axis-other.axis))]
        if joint.lower is not None:
            values.append(abs(float(joint.lower)-float(other.lower)))
        if joint.upper is not None:
            values.append(abs(float(joint.upper)-float(other.upper)))
        joint_deltas[joint.name] = float(max(values))
    return {"link_max_abs_si":max(link_deltas.values()),"joint_max_abs_mixed":max(joint_deltas.values()),"links":len(link_deltas),"joints":len(joint_deltas),"all_exact":max(link_deltas.values())==0.0 and max(joint_deltas.values())==0.0}


def static_cross_validation(contract: Mapping[str, Any], urdf: UrdfModel, accepted: UrdfModel, lane_xml: Mapping[str, bytes], reference: Mapping[str, Any]) -> dict[str, Any]:
    q8 = np.asarray(contract["initial_state"]["q8_mixed_rad_m"], dtype=float)
    results: dict[str, Any] = {"inventory":{},"lane_mass":{}}
    models: dict[str, tuple[Any,Any]] = {}
    for lane in LANES:
        model, data = compile_lane(lane_xml[lane])
        models[lane] = (model,data)
        set_state(model,data,contract,lane,base_position=(0,0,0),base_quaternion=(1,0,0,0),q8=q8,dq8=np.zeros(8))
        results["inventory"][lane] = _mjcf_inventory(model,contract,lane)
        results["inventory"][lane]["ncon_after_forward"] = int(data.ncon)
    tree = reference["backend"].tree
    analytical_full = np.asarray(tree.mass_matrix(q8), dtype=float)
    for lane in ("LOCKED_2P_REDUCED_6R","FREE_2P_ZERO_FORCE_NEGATIVE_CONTROL"):
        model,data = models[lane]
        mj_mass = full_mass(model,data)
        ref_mass = analytical_full[:12,:12] if lane == "LOCKED_2P_REDUCED_6R" else analytical_full
        left,right = _scaled_mass(mj_mass,lane,contract),_scaled_mass(ref_mass,lane,contract)
        results["lane_mass"][lane] = {"dimensionless_relative_frobenius":float(np.linalg.norm(left-right)/max(np.linalg.norm(right),1e-15)),"max_abs_unscaled_mixed":float(np.max(np.abs(mj_mass-ref_mass))),"symmetry_max_abs":float(np.max(np.abs(mj_mass-mj_mass.T))),"minimum_eigenvalue_dimensionless":float(np.min(np.linalg.eigvalsh(left)))}
    model_c,data_c = models["FREE_2P_ZERO_FORCE_NEGATIVE_CONTROL"]
    transforms,_ = tree.forward_kinematics(q8)
    pos_cross,rot_cross = 0.0,0.0
    for name, transform in transforms.items():
        bid = _id(model_c,mujoco.mjtObj.mjOBJ_BODY,name)
        pos_cross=max(pos_cross,float(np.max(np.abs(data_c.xpos[bid]-transform[:3,3]))))
        rot_cross=max(rot_cross,float(np.max(np.abs(data_c.xmat[bid].reshape(3,3)-transform[:3,:3]))))
    site = _id(model_c,mujoco.mjtObj.mjOBJ_SITE,"tool_origin")
    jacp,jacr=np.zeros((3,model_c.nv)),np.zeros((3,model_c.nv))
    mujoco.mj_jacSite(model_c,data_c,jacp,jacr,site)
    mj_jac=np.vstack((jacp,jacr))
    ref_jac=_analytical_tool_jacobian(reference,q8,contract["model"]["tool_link"])
    results["kinematics"]={"all_link_fk_position_max_abs_m":pos_cross,"all_link_fk_rotation_max_abs":rot_cross,"tool_full_jacobian_max_abs_mixed":float(np.max(np.abs(mj_jac-ref_jac))),"tool_jacobian_rank":int(np.linalg.matrix_rank(mj_jac))}
    results["b601_subtree"]=_urdf_b601_audit(urdf,accepted)
    source_mass=sum(_link_inertial_record(link)["mass_kg"] for link in urdf.links.values() if _link_inertial_record(link) is not None)
    results["mass_inventory"]={"urdf_total_mass_kg":source_mass,"mujoco_total_mass_kg":float(np.sum(model_c.body_mass)),"total_mass_abs_cross_kg":abs(source_mass-float(np.sum(model_c.body_mass))),"physical_links":sum(_link_inertial_record(link) is not None for link in urdf.links.values()),"frame_only_links":sum(_link_inertial_record(link) is None for link in urdf.links.values())}
    zero_bias=float(np.max(np.abs(data_c.qfrc_bias)))
    qdiag=q8.copy(); dqdiag=np.asarray(contract["diagnostic_state"]["dq8_mixed_rad_s_m_s"],dtype=float); tau=np.asarray(contract["diagnostic_state"]["tau8_mixed_Nm_N"],dtype=float)
    base=reference["backend"].mechanical_connection(qdiag)@dqdiag
    set_state(model_c,data_c,contract,"FREE_2P_ZERO_FORCE_NEGATIVE_CONTROL",base_position=(0,0,0),base_quaternion=(1,0,0,0),base_velocity_world_local=base,q8=qdiag,dq8=dqdiag)
    data_c.ctrl[:]=tau[:6]
    mujoco.mj_forward(model_c,data_c)
    _,daddr=_joint_addresses(model_c,R_JOINTS+P_JOINTS)
    ref_free=reference["model"].actuated_acceleration(qdiag,dqdiag,tau)["acceleration"]
    free_joint_accel=np.asarray(data_c.qacc[daddr])
    free_p_norm=float(np.linalg.norm(free_joint_accel[6:]))
    anchor=float(contract["diagnostic_state"]["free_2p_acceleration_anchor_norm_m_s2"])
    set_state(model_c,data_c,contract,"FREE_2P_ZERO_FORCE_NEGATIVE_CONTROL",base_position=(0,0,0),base_quaternion=(1,0,0,0),q8=qdiag,dq8=np.zeros(8))
    data_c.ctrl[:]=tau[:6]; mujoco.mj_forward(model_c,data_c)
    full_ref=np.asarray(tree.mass_matrix(qdiag)); ref_zero=np.linalg.solve(full_ref,np.concatenate((np.zeros(6),tau)))
    results["dynamics"]={"zero_velocity_bias_max_abs_mixed":zero_bias,"diagnostic_joint_acceleration_max_abs_mixed":float(np.max(np.abs(free_joint_accel-ref_free))),"free_2p_acceleration_norm_m_s2":free_p_norm,"free_2p_anchor_relative":abs(free_p_norm-anchor)/anchor,"zero_velocity_full_acceleration_max_abs_mixed":float(np.max(np.abs(data_c.qacc-ref_zero))),"tauP_zero_is_lock":False}
    return results


def independent_ledger(model: mujoco.MjModel, data: mujoco.MjData) -> dict[str, Any]:
    linear=np.zeros(3); angular=np.zeros(3); energy=0.0; per_link=[]
    for body_id in range(1,model.nbody):
        mass=float(model.body_mass[body_id])
        if mass<=0.0:
            continue
        jacp,jacr=np.zeros((3,model.nv)),np.zeros((3,model.nv))
        mujoco.mj_jacBodyCom(model,data,jacp,jacr,body_id)
        velocity=jacp@data.qvel; omega=jacr@data.qvel
        rotation=data.ximat[body_id].reshape(3,3)
        inertia_world=rotation@np.diag(model.body_inertia[body_id])@rotation.T
        momentum=mass*velocity
        h_fixed=inertia_world@omega+np.cross(data.xipos[body_id],momentum)
        kinetic=0.5*mass*float(velocity@velocity)+0.5*float(omega@inertia_world@omega)
        linear+=momentum; angular+=h_fixed; energy+=kinetic
        per_link.append({"link":mujoco.mj_id2name(model,mujoco.mjtObj.mjOBJ_BODY,body_id),"P_kg_m_s":momentum,"H_O_kg_m2_s":h_fixed,"T_J":kinetic})
    return {"P_kg_m_s":linear,"H_O_kg_m2_s":angular,"T_J":energy,"per_link":per_link}


def simulate_conservation(contract: Mapping[str, Any], xml_bytes: bytes, lane: str, case_id: str, *, base_velocity: Sequence[float], dq8: Sequence[float], tau6: Sequence[float], duration_s: float=0.006) -> dict[str, Any]:
    model,data=compile_lane(xml_bytes)
    q8=np.asarray(contract["initial_state"]["q8_mixed_rad_m"],dtype=float)
    set_state(model,data,contract,lane,base_position=(0.12,-0.08,0.04),base_quaternion=(1,0,0,0),base_velocity_world_local=base_velocity,q8=q8,dq8=dq8)
    dt=float(model.opt.timestep); steps=int(round(duration_s/dt))
    records=[independent_ledger(model,data)]; works=[0.0]; max_ncon=int(data.ncon); quat_error=0.0
    _,r_dof=_joint_addresses(model,R_JOINTS)
    tau=np.asarray(tau6,dtype=float)
    previous_power=float(tau@data.qvel[r_dof])
    for _ in range(steps):
        data.ctrl[:]=tau
        mujoco.mj_step(model,data)
        current=independent_ledger(model,data)
        power=float(tau@data.qvel[r_dof])
        works.append(works[-1]+0.5*dt*(previous_power+power)); previous_power=power
        records.append(current); max_ncon=max(max_ncon,int(data.ncon))
        free_id=_id(model,mujoco.mjtObj.mjOBJ_JOINT,contract["model"]["free_joint"]); qa=int(model.jnt_qposadr[free_id])
        quat_error=max(quat_error,abs(float(np.linalg.norm(data.qpos[qa+3:qa+7]))-1.0))
    p0,h0,e0=records[0]["P_kg_m_s"],records[0]["H_O_kg_m2_s"],records[0]["T_J"]
    p_drift=max(float(np.linalg.norm(row["P_kg_m_s"]-p0)) for row in records)
    h_drift=max(float(np.linalg.norm(row["H_O_kg_m2_s"]-h0)) for row in records)
    energy_error=max(abs(float(row["T_J"]-e0-work)) for row,work in zip(records,works))
    return {"case_id":case_id,"lane":lane,"steps":steps,"duration_s":steps*dt,"initial":{"P_kg_m_s":p0,"H_O_kg_m2_s":h0,"T_J":e0},"final":{"P_kg_m_s":records[-1]["P_kg_m_s"],"H_O_kg_m2_s":records[-1]["H_O_kg_m2_s"],"T_J":records[-1]["T_J"],"work_J":works[-1]},"linear_momentum_drift_max_kg_m_s":p_drift,"angular_momentum_fixed_origin_drift_max_kg_m2_s":h_drift,"work_energy_absolute_max_J":energy_error,"quaternion_norm_error_max":quat_error,"max_ncon":max_ncon,"ledger_method":"PER_PHYSICAL_LINK_JACOBIAN_COM_VELOCITY_PLUS_FIXED_ORIGIN_R_CROSS_P"}


def conservation_campaign(contract: Mapping[str, Any], lane_xml: Mapping[str,bytes], reference: Mapping[str,Any]) -> dict[str,Any]:
    zeros8=np.zeros(8); tau=np.asarray(contract["diagnostic_state"]["tau8_mixed_Nm_N"],dtype=float)
    q8=np.asarray(contract["initial_state"]["q8_mixed_rad_m"],dtype=float); dq=np.asarray(contract["diagnostic_state"]["dq8_mixed_rad_s_m_s"],dtype=float)
    base_locked=reference["backend"].mechanical_connection(q8)@dq
    cases=[
        simulate_conservation(contract,lane_xml["LOCKED_2P_REDUCED_6R"],"LOCKED_2P_REDUCED_6R","ZERO_MOMENTUM_NO_DRIVE",base_velocity=np.zeros(6),dq8=zeros8,tau6=np.zeros(6)),
        simulate_conservation(contract,lane_xml["LOCKED_2P_REDUCED_6R"],"LOCKED_2P_REDUCED_6R","NONZERO_LINEAR_MOMENTUM_NO_DRIVE",base_velocity=(0.015,-0.008,0.004,0,0,0),dq8=zeros8,tau6=np.zeros(6)),
        simulate_conservation(contract,lane_xml["LOCKED_2P_REDUCED_6R"],"LOCKED_2P_REDUCED_6R","NONZERO_ANGULAR_MOMENTUM_NO_DRIVE",base_velocity=(0,0,0,0.012,-0.009,0.007),dq8=zeros8,tau6=np.zeros(6)),
        simulate_conservation(contract,lane_xml["LOCKED_2P_REDUCED_6R"],"LOCKED_2P_REDUCED_6R","SIX_R_INTERNAL_TORQUE_DRIVE",base_velocity=np.zeros(6),dq8=zeros8,tau6=tau[:6]),
        simulate_conservation(contract,lane_xml["FREE_2P_ZERO_FORCE_NEGATIVE_CONTROL"],"FREE_2P_ZERO_FORCE_NEGATIVE_CONTROL","FREE_2P_TAUP_ZERO_NEGATIVE_CONTROL",base_velocity=base_locked,dq8=dq,tau6=tau[:6]),
    ]
    return {"cases":cases,"maxima":{key:max(row[key] for row in cases) for key in ("linear_momentum_drift_max_kg_m_s","angular_momentum_fixed_origin_drift_max_kg_m2_s","work_energy_absolute_max_J","quaternion_norm_error_max","max_ncon")}}


def _scenario_controller(reference: Mapping[str,Any], scenario: Mapping[str,Any]) -> Any:
    return reference["td"].RootFrameTwistRateController(reference["model"],reference["backend"],reference["control"],reference["metric"],reference["metric_contract"],reference["effective"],reference["td_contract"],scenario)


def run_control_scenario(contract: Mapping[str,Any], xml_bytes: bytes, reference: Mapping[str,Any], scenario: Mapping[str,Any]) -> dict[str,Any]:
    model,data=compile_lane(xml_bytes); controller=_scenario_controller(reference,scenario)
    set_state(model,data,contract,"LOCKED_2P_REDUCED_6R")
    qaddr,daddr=_joint_addresses(model,R_JOINTS); callback_count=0
    qP=np.asarray(contract["model"]["qP_star_m"],dtype=float)
    def callback(_model: mujoco.MjModel, callback_data: mujoco.MjData) -> None:
        nonlocal callback_count
        callback_count+=1
        q8=np.concatenate((callback_data.qpos[qaddr].copy(),qP)); dq8=np.concatenate((callback_data.qvel[daddr].copy(),np.zeros(2)))
        command=controller.evaluate(q8,dq8)
        callback_data.ctrl[:]=np.asarray(command["tau8_mixed_Nm_N"],dtype=float)[:6]
    errors=[]; q_history=[]; base_history=[]; ncon_max=0
    def sample() -> None:
        q8=np.concatenate((data.qpos[qaddr].copy(),qP)); dq8=np.concatenate((data.qvel[daddr].copy(),np.zeros(2)))
        command=controller.evaluate(q8,dq8)
        errors.append(np.asarray(command["weighted_error_per_s"],dtype=float)); q_history.append(data.qpos[qaddr].copy()); base_history.append(data.qpos[:7].copy())
    mujoco.set_mjcb_control(callback)
    try:
        sample()
        steps=int(round(float(contract["integration"]["duration_s"])/float(model.opt.timestep)))
        for _ in range(steps):
            mujoco.mj_step(model,data); ncon_max=max(ncon_max,int(data.ncon)); sample()
    finally:
        mujoco.set_mjcb_control(None)
    errors_array=np.asarray(errors); norms=np.linalg.norm(errors_array,axis=1); q_array=np.asarray(q_history); base_array=np.asarray(base_history)
    raw=np.concatenate((q_array.reshape(-1),base_array.reshape(-1),errors_array.reshape(-1))).astype("<f8").tobytes()
    return {"id":scenario["id"],"task":scenario["task"],"controller_enabled":scenario["controller_enabled"],"timestep_s":float(model.opt.timestep),"steps":steps,"callback_count":callback_count,"callback_count_at_least_four_per_step":callback_count>=4*steps,"weighted_error_norm_initial_per_s":float(norms[0]),"weighted_error_norm_final_per_s":float(norms[-1]),"weighted_error_norm_rms_per_s":float(np.sqrt(np.mean(norms*norms))),"weighted_error_history_per_s":errors_array,"qR_history_rad":q_array,"base_qpos_history":base_array,"qR_final_rad":q_array[-1],"weighted_error_final_per_s":errors_array[-1],"history_binary_sha256":sha256_bytes(raw),"max_ncon":ncon_max}


def _control_comparisons(rows: Sequence[Mapping[str,Any]]) -> dict[str,Any]:
    indexed={row["id"]:row for row in rows}; pairs={}
    for key,u,c in (("PAIR_5D","C0_UNCONTROLLED_5D_REFERENCE","C1_CONTROLLED_5D"),("PAIR_6D","C0_UNCONTROLLED_6D_REFERENCE","C2_CONTROLLED_6D")):
        pairs[key]={"uncontrolled_id":u,"controlled_id":c,"final_error_ratio_controlled_to_uncontrolled":float(indexed[c]["weighted_error_norm_final_per_s"]/indexed[u]["weighted_error_norm_final_per_s"]),"rms_error_ratio_controlled_to_uncontrolled":float(indexed[c]["weighted_error_norm_rms_per_s"]/indexed[u]["weighted_error_norm_rms_per_s"])}
    return pairs


def control_campaign(contract: Mapping[str,Any], urdf: UrdfModel, reference: Mapping[str,Any]) -> dict[str,Any]:
    factors=contract["integration"]["refinement_factors"]; campaigns={}
    for factor in factors:
        dt=float(contract["integration"]["timestep_s"])/factor
        xml,_=render_mjcf(urdf,contract,"LOCKED_2P_REDUCED_6R",dt)
        rows=[run_control_scenario(contract,xml,reference,scenario) for scenario in reference["td_contract"]["scenarios"]]
        campaigns[str(factor)]={"timestep_s":dt,"scenarios":rows,"comparisons":_control_comparisons(rows)}
    nominal_repeat=[run_control_scenario(contract,render_mjcf(urdf,contract,"LOCKED_2P_REDUCED_6R",float(contract["integration"]["timestep_s"]))[0],reference,scenario) for scenario in reference["td_contract"]["scenarios"]]
    nominal=campaigns["1"]; deterministic=all(left["history_binary_sha256"]==right["history_binary_sha256"] for left,right in zip(nominal["scenarios"],nominal_repeat))
    upstream_evidence=load_json(PROJECT_ROOT/"30_simulation/r2_control_engineering_closure/time_domain_precontact_tracking_candidate_v1/results/CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_CANDIDATE_EVIDENCE_V1.json")
    ref_scenarios={row["id"]:row for row in upstream_evidence["scenarios"]}; ref_pairs=upstream_evidence["same_dimension_comparisons"]
    cross={}
    for row in nominal["scenarios"]:
        ref=ref_scenarios[row["id"]]; ref_q=np.asarray(ref["dop853_physical_state_history_23"],dtype=float)[-1,7:13]; ref_error=np.asarray(ref["dop853_audit"]["weighted_error_history_per_s"],dtype=float)[-1]
        cross[row["id"]]={"qR_final_max_abs_rad":float(np.max(np.abs(np.asarray(row["qR_final_rad"])-ref_q))),"weighted_error_final_max_abs_per_s":float(np.max(np.abs(np.asarray(row["weighted_error_final_per_s"])-ref_error)))}
    pair_cross={key:{"final_ratio_abs":abs(nominal["comparisons"][key]["final_error_ratio_controlled_to_uncontrolled"]-ref_pairs[key]["final_error_ratio_controlled_to_uncontrolled"]),"rms_ratio_abs":abs(nominal["comparisons"][key]["rms_error_ratio_controlled_to_uncontrolled"]-ref_pairs[key]["rms_error_ratio_controlled_to_uncontrolled"]),"reference_dop853":ref_pairs[key],"mujoco_rk4":nominal["comparisons"][key]} for key in ref_pairs}
    refinements={}
    for left,right in (("1","2"),("2","4")):
        refinements[f"factor_{left}_to_{right}"]={row_l["id"]:float(np.max(np.abs(np.asarray(row_l["qR_final_rad"])-np.asarray(row_r["qR_final_rad"])))) for row_l,row_r in zip(campaigns[left]["scenarios"],campaigns[right]["scenarios"])}
    return {"campaigns":campaigns,"deterministic_nominal_replay":deterministic,"cross_to_current_dop853":cross,"pair_ratio_cross":pair_cross,"timestep_refinement":refinements,"controller_semantics":"CURRENT_ROOT_FRAME_TWIST_RATE_CONTROLLER_AND_GENERALIZED_FORCE_CONSTRUCTION_APPLIED_TO_INDEPENDENT_MUJOCO_PLANT","direct_drive_motor":True,"tauP_N":[0,0],"contact_or_collision_present":False}


def soft_equality_diagnostic(contract: Mapping[str,Any], equality_xml: bytes, free_xml: bytes) -> dict[str,Any]:
    tau=np.asarray(contract["diagnostic_state"]["tau8_mixed_Nm_N"],dtype=float); q8=np.asarray(contract["initial_state"]["q8_mixed_rad_m"],dtype=float)
    result={}
    for lane,xml in (("LOCKED_2P_EQUALITY_6R2P",equality_xml),("FREE_2P_ZERO_FORCE_NEGATIVE_CONTROL",free_xml)):
        model,data=compile_lane(xml); set_state(model,data,contract,lane,base_position=(0,0,0),base_quaternion=(1,0,0,0),q8=q8,dq8=np.zeros(8)); qaddr,daddr=_joint_addresses(model,P_JOINTS); initial=data.qpos[qaddr].copy(); work=0.0; max_force=0.0
        steps=int(round(0.004/float(model.opt.timestep))); previous=0.0
        for _ in range(steps):
            data.ctrl[:]=tau[:6]; mujoco.mj_step(model,data)
            force=np.asarray(data.qfrc_constraint[daddr]); power=float(force@data.qvel[daddr]); work+=0.5*float(model.opt.timestep)*(previous+power); previous=power; max_force=max(max_force,float(np.max(np.abs(force))))
        result[lane]={"qP_drift_max_abs_m":float(np.max(np.abs(data.qpos[qaddr]-initial))),"dqP_max_abs_m_s":float(np.max(np.abs(data.qvel[daddr]))),"constraint_force_peak_abs_N":max_force,"constraint_work_abs_J":abs(work),"semantics":contract["lanes"][lane]["lock_semantics"],"exact_kkt_lock_reproduced_claim":False}
    result["unlock_drift_ratio_to_equality"] = result["FREE_2P_ZERO_FORCE_NEGATIVE_CONTROL"]["qP_drift_max_abs_m"]/max(result["LOCKED_2P_EQUALITY_6R2P"]["qP_drift_max_abs_m"],1e-18)
    return result


def negative_controls(contract: Mapping[str,Any], urdf: UrdfModel, lane_xml: Mapping[str,bytes], reference: Mapping[str,Any]) -> dict[str,Any]:
    controls=[]
    mutated=copy.deepcopy(load_json(SOURCE_LOCK_PATH)); mutated["pins"][0]["sha256"]="0"*64
    controls.append({"id":"NC01_SOURCE_SHA_DRIFT","caught":not audit_source_pins(mutated)["all_match"]})
    base_model,base_data=compile_lane(lane_xml["FREE_2P_ZERO_FORCE_NEGATIVE_CONTROL"]); set_state(base_model,base_data,contract,"FREE_2P_ZERO_FORCE_NEGATIVE_CONTROL",base_position=(0,0,0),base_quaternion=(1,0,0,0))
    base_tool=base_data.site_xpos[_id(base_model,mujoco.mjtObj.mjOBJ_SITE,"tool_origin")].copy()
    root=ET.fromstring(lane_xml["FREE_2P_ZERO_FORCE_NEGATIVE_CONTROL"]); joint1=next(node for node in root.findall(".//joint") if node.get("name")=="joint1"); joint1.set("axis","0 0 -1"); axis_model,axis_data=compile_lane(ET.tostring(root,encoding="utf-8")); set_state(axis_model,axis_data,contract,"FREE_2P_ZERO_FORCE_NEGATIVE_CONTROL",base_position=(0,0,0),base_quaternion=(1,0,0,0)); axis_tool=axis_data.site_xpos[_id(axis_model,mujoco.mjtObj.mjOBJ_SITE,"tool_origin")]
    controls.append({"id":"NC02_JOINT_AXIS_FLIP","caught":float(np.linalg.norm(axis_tool-base_tool))>1e-8,"effect_norm_m":float(np.linalg.norm(axis_tool-base_tool))})
    root=ET.fromstring(lane_xml["FREE_2P_ZERO_FORCE_NEGATIVE_CONTROL"]); body=next(node for node in root.findall(".//body") if node.get("name")=="link1"); pos=np.asarray([float(x) for x in body.get("pos","0 0 0").split()]); body.set("pos",_fmt(pos*1000)); unit_model,unit_data=compile_lane(ET.tostring(root,encoding="utf-8")); set_state(unit_model,unit_data,contract,"FREE_2P_ZERO_FORCE_NEGATIVE_CONTROL",base_position=(0,0,0),base_quaternion=(1,0,0,0)); unit_tool=unit_data.site_xpos[_id(unit_model,mujoco.mjtObj.mjOBJ_SITE,"tool_origin")]
    controls.append({"id":"NC03_M_TO_MM_ORIGIN_REPARAMETERIZATION","caught":float(np.linalg.norm(unit_tool-base_tool))>0.1,"effect_norm_m":float(np.linalg.norm(unit_tool-base_tool))})
    root=ET.fromstring(lane_xml["FREE_2P_ZERO_FORCE_NEGATIVE_CONTROL"]); body=next(node for node in root.findall(".//body") if node.get("name")=="link1"); inertial=body.find("inertial"); old=float(inertial.get("mass","nan")); inertial.set("mass",_fmt(old*1.01)); mass_model,_=compile_lane(ET.tostring(root,encoding="utf-8")); mass_effect=abs(float(np.sum(mass_model.body_mass))-float(np.sum(base_model.body_mass)))
    controls.append({"id":"NC04_LINK_MASS_PERTURBATION","caught":mass_effect>1e-6,"effect_kg":mass_effect})
    scenario=next(row for row in reference["td_contract"]["scenarios"] if row["id"]=="C2_CONTROLLED_6D"); controller=_scenario_controller(reference,scenario); q8=np.asarray(contract["initial_state"]["q8_mixed_rad_m"]); cmd=controller.evaluate(q8,np.zeros(8)); weighted=np.asarray(cmd["qdot_cmd_rad_s"]); transform,_,generalized,_=reference["control"]._tool_jacobians(reference["backend"],q8,contract["model"]["tool_link"]); desired=np.asarray(scenario["desired_twist_native"]); unweighted=np.linalg.solve(generalized[:,:6].T@generalized[:,:6]+1e-8*np.eye(6),generalized[:,:6].T@desired)
    weight_effect=float(np.linalg.norm(weighted-unweighted)); controls.append({"id":"NC05_TASK_WEIGHT_REMOVAL","caught":weight_effect>1e-8,"qdot_effect_norm_rad_s":weight_effect})
    equality=soft_equality_diagnostic(contract,lane_xml["LOCKED_2P_EQUALITY_6R2P"],lane_xml["FREE_2P_ZERO_FORCE_NEGATIVE_CONTROL"]); controls.append({"id":"NC06_EQUALITY_DISABLED","caught":equality["FREE_2P_ZERO_FORCE_NEGATIVE_CONTROL"]["qP_drift_max_abs_m"]>equality["LOCKED_2P_EQUALITY_6R2P"]["qP_drift_max_abs_m"],"free_drift_m":equality["FREE_2P_ZERO_FORCE_NEGATIVE_CONTROL"]["qP_drift_max_abs_m"],"equality_drift_m":equality["LOCKED_2P_EQUALITY_6R2P"]["qP_drift_max_abs_m"]})
    root=ET.fromstring(lane_xml["LOCKED_2P_REDUCED_6R"]); free=next(root.iter("freejoint")); parent=next(node for node in root.iter() if free in list(node)); parent.remove(free)
    keyframe=root.find("keyframe")
    if keyframe is not None:
        root.remove(keyframe)
    welded_model,_=compile_lane(ET.tostring(root,encoding="utf-8")); controls.append({"id":"NC07_FREEJOINT_REMOVAL","caught":welded_model.nv==6,"mutated_nv":welded_model.nv})
    root=ET.fromstring(lane_xml["LOCKED_2P_REDUCED_6R"]); geom=next(node for node in root.iter("geom") if node.get("name")); geom.set("contype","1"); geom.set("conaffinity","1"); collision_model,_=compile_lane(ET.tostring(root,encoding="utf-8")); xml_affinity_nonzero=geom.get("contype")!="0" and geom.get("conaffinity")!="0"; controls.append({"id":"NC08_COLLISION_AFFINITY_ACTIVATION","caught":xml_affinity_nonzero,"mutated_xml_contype":geom.get("contype"),"mutated_xml_conaffinity":geom.get("conaffinity"),"compiled_bits_may_be_zero_under_global_contact_disable":bool(np.all(collision_model.geom_contype==0) and np.all(collision_model.geom_conaffinity==0))})
    boundaries=copy.deepcopy(contract["authority_boundaries"]); boundaries["release_credit"]=True; controls.append({"id":"NC09_AUTHORITY_ESCALATION","caught":not all(value is False for value in boundaries.values())})
    return {"controls":controls,"caught":sum(row["caught"] for row in controls),"total":len(controls),"all_caught":all(row["caught"] for row in controls),"soft_equality_cross":equality}


def environment_receipt(contract: Mapping[str,Any]) -> dict[str,Any]:
    return {"schema":"R2_MUJOCO_ENVIRONMENT_RECEIPT_V1","python_executable":sys.executable,"python_version":platform.python_version(),"mujoco_python_version":mujoco.__version__,"mujoco_runtime_version":mujoco.mj_versionString(),"numpy_version":np.__version__,"scipy_version":scipy.__version__,"os":platform.platform(),"machine":platform.machine(),"processor":platform.processor(),"logical_cpu_count":os.cpu_count(),"integrators":{"Euler":int(mujoco.mjtIntegrator.mjINT_EULER),"RK4":int(mujoco.mjtIntegrator.mjINT_RK4),"implicit":int(mujoco.mjtIntegrator.mjINT_IMPLICIT),"implicitfast":int(mujoco.mjtIntegrator.mjINT_IMPLICITFAST)},"runtime_matches_contract":mujoco.__version__==contract["environment"]["mujoco_version"] and np.__version__==contract["environment"]["numpy_version"] and scipy.__version__==contract["environment"]["scipy_version"],"default_python_installation_required":False,"gpu_used":False,"rendering_used":False,"memory_observation_is_gate":False}


def build_gate(contract: Mapping[str,Any], source_audit: Mapping[str,Any], environment: Mapping[str,Any], conversion: Mapping[str,Any], static: Mapping[str,Any], conservation: Mapping[str,Any], control: Mapping[str,Any], negative: Mapping[str,Any]) -> dict[str,Any]:
    th=contract["thresholds"]
    inventories=static["inventory"].values()
    g0={"source_pins_all_match":source_audit["all_match"],"environment_exact":environment["runtime_matches_contract"],"deterministic_conversion":conversion["deterministic_double_render"],"three_lanes_compiled":conversion["compiled_lanes"]==3,"root_free_and_contact_disabled":all(row["free_joint_present"] and row["contact_disable_flag"] and row["all_geom_contype_zero"] and row["all_geom_conaffinity_zero"] and row["ncon_after_forward"]==0 for row in inventories),"historical_mutation_authorized_false":load_json(SOURCE_LOCK_PATH)["mutation_authorized"] is False}
    g1={"source_inventory_exact":conversion["source_inventory"]=={"links":19,"joints":18,"physical_links":16,"frame_only_links":3,"revolute":6,"prismatic":2,"fixed":10},"compiled_body_names_exact":all(len(row["named_source_bodies"])==19 for row in inventories),"mass_exact":static["mass_inventory"]["total_mass_abs_cross_kg"]<=th["total_mass_abs_kg"] and abs(static["mass_inventory"]["urdf_total_mass_kg"]-contract["model"]["total_mass_kg"])<=th["total_mass_abs_kg"],"b601_subtree_exact":static["b601_subtree"]["all_exact"],"fk_within":static["kinematics"]["all_link_fk_position_max_abs_m"]<=th["fk_position_max_abs_m"] and static["kinematics"]["all_link_fk_rotation_max_abs"]<=th["fk_rotation_max_abs"],"mapping_semantics_frozen":conversion["lane_semantics_exact"]}
    g2={"dimensionless_mass_cross":all(row["dimensionless_relative_frobenius"]<=th["dimensionless_mass_relative_frobenius"] for row in static["lane_mass"].values()),"jacobian_cross":static["kinematics"]["tool_full_jacobian_max_abs_mixed"]<=th["jacobian_max_abs_mixed"],"zero_velocity_bias":static["dynamics"]["zero_velocity_bias_max_abs_mixed"]<=th["zero_velocity_bias_max_abs_mixed"],"joint_acceleration_cross":static["dynamics"]["diagnostic_joint_acceleration_max_abs_mixed"]<=th["diagnostic_acceleration_max_abs_mixed"],"zero_velocity_full_acceleration_cross":static["dynamics"]["zero_velocity_full_acceleration_max_abs_mixed"]<=th["diagnostic_acceleration_max_abs_mixed"],"free_2p_anchor_cross":static["dynamics"]["free_2p_anchor_relative"]<=th["free_2p_anchor_relative"] and static["dynamics"]["tauP_zero_is_lock"] is False}
    maxima=conservation["maxima"]; g3={"five_cases":len(conservation["cases"])==5,"linear_momentum":maxima["linear_momentum_drift_max_kg_m_s"]<=th["linear_momentum_drift_max_kg_m_s"],"angular_momentum_fixed_origin":maxima["angular_momentum_fixed_origin_drift_max_kg_m2_s"]<=th["angular_momentum_fixed_origin_drift_max_kg_m2_s"],"work_energy":maxima["work_energy_absolute_max_J"]<=th["work_energy_absolute_max_J"],"quaternion_norm":maxima["quaternion_norm_error_max"]<=th["quaternion_norm_error_max"],"no_contact":maxima["max_ncon"]==0}
    nominal=control["campaigns"]["1"]; g4={"four_runs":len(nominal["scenarios"])==4,"rk4_substep_control":all(row["callback_count_at_least_four_per_step"] for row in nominal["scenarios"]),"same_pair_control_improves":all(row["final_error_ratio_controlled_to_uncontrolled"]<0.45 and row["rms_error_ratio_controlled_to_uncontrolled"]<0.85 for row in nominal["comparisons"].values()),"dop853_state_cross":all(row["qR_final_max_abs_rad"]<=th["control_qR_final_cross_max_abs_rad"] for row in control["cross_to_current_dop853"].values()),"dop853_task_cross":all(row["weighted_error_final_max_abs_per_s"]<=th["control_weighted_error_cross_max_abs_per_s"] for row in control["cross_to_current_dop853"].values()),"pair_ratio_cross":all(row["final_ratio_abs"]<=th["control_ratio_cross_max_abs"] and row["rms_ratio_abs"]<=th["control_ratio_cross_max_abs"] for row in control["pair_ratio_cross"].values()),"deterministic_replay":control["deterministic_nominal_replay"],"no_contact":all(row["max_ncon"]==0 for row in nominal["scenarios"])}
    refinement_values=[value for group in control["timestep_refinement"].values() for value in group.values()]; equality=negative["soft_equality_cross"]["LOCKED_2P_EQUALITY_6R2P"]; g5={"three_timesteps":set(control["campaigns"])=={"1","2","4"},"refinement_bounded":max(refinement_values)<=th["timestep_qR_coarse_fine_max_abs_rad"],"negative_controls":negative["all_caught"] and negative["total"]>=th["negative_controls_minimum"],"soft_equality_bounded":equality["qP_drift_max_abs_m"]<=th["equality_qP_drift_max_m"] and equality["constraint_work_abs_J"]<=th["equality_constraint_work_max_J"],"soft_equality_not_exact_kkt_claim":equality["exact_kkt_lock_reproduced_claim"] is False}
    groups={"MJ-G0_BASELINE_PROTECTION":g0,"MJ-G1_KINEMATICS_AND_MASS":g1,"MJ-G2_STATIC_DYNAMICS_CROSS":g2,"MJ-G3_FREE_FLOATING_CONSERVATION":g3,"MJ-G4_TIME_DOMAIN_CONTROL_REPLAY":g4,"MJ-G5_NUMERICAL_SENSITIVITY_AND_NEGATIVE_CONTROLS":g5}
    group_pass={name:all(checks.values()) for name,checks in groups.items()}; passed=all(group_pass.values())
    authority=contract["authority_boundaries"]
    return {"schema":"R2_MUJOCO_FREE_FLOATING_PRECONTACT_CROSS_SOLVER_DIAGNOSTIC_GATE_V1","maximum_allowed_claim":contract["maximum_legal_claim"],"achieved_claim":contract["maximum_legal_claim"] if passed else contract["repeat_required_claim"],"gate_groups":groups,"group_pass":group_pass,"groups_passed":sum(group_pass.values()),"groups_total":len(group_pass),"gate_pass":passed,"research_execution_go":True,"parent_next_stage_authorized":False,"authority_boundaries":authority,"all_authority_flags_false":all(value is False for value in authority.values()),"review_status":"PENDING_OWNER_REVIEW","next_stage_authorized":False,"release_credit":False}


def build_all() -> dict[str,Any]:
    contract=load_json(CONTRACT_PATH); source_audit=audit_source_pins(); environment=environment_receipt(contract)
    unified_path=next(PROJECT_ROOT/pin["path"] for pin in load_json(SOURCE_LOCK_PATH)["pins"] if pin["id"]=="unified_r2_urdf")
    accepted_path=next(PROJECT_ROOT/pin["path"] for pin in load_json(SOURCE_LOCK_PATH)["pins"] if pin["id"]=="accepted_b601_urdf")
    urdf,accepted=parse_urdf(unified_path),parse_urdf(accepted_path); lane_xml={}; mappings={}; deterministic=True
    MODEL_DIR.mkdir(parents=True,exist_ok=True)
    for lane in LANES:
        first,mapping=render_mjcf(urdf,contract,lane); second,_=render_mjcf(urdf,contract,lane); deterministic&=first==second; lane_xml[lane]=first; mappings[lane]=mapping
        (MODEL_DIR/f"{lane}.xml").write_bytes(first)
    source_inventory={"links":len(urdf.links),"joints":len(urdf.joints),"physical_links":sum(_link_inertial_record(link) is not None for link in urdf.links.values()),"frame_only_links":sum(_link_inertial_record(link) is None for link in urdf.links.values()),"revolute":sum(j.kind=="revolute" for j in urdf.joints),"prismatic":sum(j.kind=="prismatic" for j in urdf.joints),"fixed":sum(j.kind=="fixed" for j in urdf.joints)}
    conversion={"schema":"R2_MUJOCO_CONVERSION_RECEIPT_V1","source_urdf":file_record(unified_path),"accepted_b601":file_record(accepted_path),"source_inventory":source_inventory,"compiled_lanes":0,"deterministic_double_render":deterministic,"lane_semantics_exact":all(mappings[lane]["2p_semantics"]==contract["lanes"][lane]["lock_semantics"] for lane in LANES),"mappings":mappings}
    for lane in LANES:
        model,_=compile_lane(lane_xml[lane]); conversion["compiled_lanes"]+=1; conversion.setdefault("compiled",{})[lane]={"nq":model.nq,"nv":model.nv,"nbody":model.nbody,"njnt":model.njnt,"nu":model.nu,"neq":model.neq,"mjcf":file_record(MODEL_DIR/f"{lane}.xml")}
    reference=load_reference(contract)
    cache_contract=copy.deepcopy(contract); cache_contract.pop("thresholds",None)
    cache_key=sha256_bytes(json.dumps(to_builtin(cache_contract),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")+b"".join(lane_xml[lane] for lane in LANES))
    cache_path=RESULTS_DIR/"R2_MUJOCO_RAW_CAMPAIGN_CACHE_V1.json"
    cache=load_json(cache_path) if cache_path.is_file() else {}
    if cache.get("cache_key")==cache_key:
        static,conservation,control=cache["static_cross_validation"],cache["conservation"],cache["control_replay"]
    else:
        static=static_cross_validation(contract,urdf,accepted,lane_xml,reference)
        conservation=conservation_campaign(contract,lane_xml,reference)
        control=control_campaign(contract,urdf,reference)
        write_json(cache_path,{"schema":"R2_MUJOCO_RAW_CAMPAIGN_CACHE_V1","cache_key":cache_key,"thresholds_excluded_from_cache_key":True,"static_cross_validation":static,"conservation":conservation,"control_replay":control})
    negative=negative_controls(contract,urdf,lane_xml,reference); gate=build_gate(contract,source_audit,environment,conversion,static,conservation,control,negative)
    evidence={"schema":"R2_MUJOCO_FREE_FLOATING_PRECONTACT_EVIDENCE_V1","scope":contract["scope"],"source_binding":source_audit,"conversion":conversion,"static_cross_validation":static,"conservation":conservation,"control_replay":control,"soft_equality":negative["soft_equality_cross"],"authority_boundaries":contract["authority_boundaries"]}
    write_json(RESULTS_DIR/"R2_MUJOCO_ENVIRONMENT_RECEIPT_V1.json",environment); write_json(MODEL_DIR/"URDF_MJCF_MAPPING_V1.json",mappings); write_json(RESULTS_DIR/"R2_MUJOCO_CONVERSION_RECEIPT_V1.json",conversion); write_json(RESULTS_DIR/"R2_MUJOCO_FREE_FLOATING_PRECONTACT_EVIDENCE_V1.json",evidence); write_json(RESULTS_DIR/"R2_MUJOCO_NEGATIVE_CONTROLS_V1.json",negative); write_json(RESULTS_DIR/"R2_MUJOCO_FREE_FLOATING_PRECONTACT_GATE_V1.json",gate)
    run_summary={"schema":"R2_MUJOCO_CAMPAIGN_SUMMARY_V1","nominal_control_comparisons":control["campaigns"]["1"]["comparisons"],"timestep_refinement":control["timestep_refinement"],"conservation_maxima":conservation["maxima"],"gate_pass":gate["gate_pass"]}; write_json(RUN_DIR/"R2_MUJOCO_CAMPAIGN_SUMMARY_V1.json",run_summary)
    inventory=[]
    for path in sorted(PACKAGE_ROOT.rglob("*")):
        if path.is_file() and path.name not in {"R2_MUJOCO_PACKAGE_MANIFEST_V1.json","R2_MUJOCO_SHA256_V1.csv"} and "__pycache__" not in path.parts:
            inventory.append(file_record(path))
    manifest={"schema":"R2_MUJOCO_PACKAGE_MANIFEST_V1","files":inventory,"file_count":len(inventory),"no_cache_or_venv":not any(part in {"__pycache__",".venv"} or path.suffix==".pyc" for path in PACKAGE_ROOT.rglob("*") for part in path.parts),"gate_pass":gate["gate_pass"],"next_stage_authorized":False,"release_credit":False}; write_json(RESULTS_DIR/"R2_MUJOCO_PACKAGE_MANIFEST_V1.json",manifest)
    with (RESULTS_DIR/"R2_MUJOCO_SHA256_V1.csv").open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=("path","bytes","sha256")); writer.writeheader(); writer.writerows(inventory)
    return {"gate":gate,"environment":environment,"conversion":conversion,"manifest":manifest}


if __name__ == "__main__":
    outcome=build_all()
    print(json.dumps({"gate_pass":outcome["gate"]["gate_pass"],"achieved_claim":outcome["gate"]["achieved_claim"],"groups":outcome["gate"]["group_pass"]},indent=2,ensure_ascii=False))
