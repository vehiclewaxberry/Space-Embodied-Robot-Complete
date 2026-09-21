"""Exact Unified-R2 XML-byte contract validator for synthetic fixtures only.

This module intentionally has no file-writing API and no import of the dormant
Unified-R2 generator.  The fixture builder emits in-memory XML bytes solely to
exercise the parser and negative controls; those bytes are not a released or
current system URDF.
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from pathlib import PurePosixPath
from typing import Any


ROBOT_NAME = "unified_r2_c01_no_route_c_sim_candidate_v2"
TOTAL_MASS_KG = 31.022864807342987
NUMERIC_TOLERANCE = 0.0
FRAME_ONLY_LINKS = (
    "D_BUS_MATE_PHYSICAL",
    "D_BUS_M6_PATTERN",
    "M_DYNAMICS_NONPHYSICAL",
)

# mass, COM xyz in link frame, symmetric inertia terms ixx/ixy/ixz/iyy/iyz/izz
PHYSICAL_INERTIALS: dict[str, tuple[float, tuple[float, ...], tuple[float, ...]]] = {
    "spacecraft_bus": (
        17.26823279235072,
        (-0.011984071178916797, -0.0000006659522079788254, 0.0007839544760700856),
        (0.12235271003976697, 0.00000219102407579873, -0.0008852398604710216, 0.23221057676128243, -0.000000010008527669029352, 0.2307345506459197),
    ),
    "bus_primary_structure_candidate_v1": (
        6.034980607649281,
        (0.03121899421170191, 0.0000019055268779790955, 0.000023442970841877576),
        (0.07122970338863957, -0.0000016941966973078647, 0.000015503826840431267, 0.10797810844743179, 0.0000000012627839575954173, 0.10799032107524492),
    ),
    "load_bridge_candidate": (
        0.702195458,
        (-1.272569222692219e-10, -1.072691633523576e-10, 0.005375000000000074),
        (0.001567906972732913, 3.577867169202165e-18, 9.433353601271602e-22, 0.001567906972732919, 2.022987917607558e-21, 0.003122289368361704),
    ),
    "m3r_lumped_link": (
        0.7619,
        (-1.272569288182205e-10, -1.072691664294674e-10, -0.00461205511262569),
        (0.001808962466764922, 0.0, 0.0, 0.001808962466764922, 0.0, 0.003594002755196379),
    ),
    "base_link": (0.8366, (-0.000007849, -0.0000011531, 0.029841), (0.00133040, 0.00000001, 0.0, 0.00213119, 0.0, 0.00275877)),
    "link1": (0.1613, (0.000113614552951627, -0.000616319527051323, 0.0236476372671394), (0.00025207, 0.0, -0.00002832, 0.00015464, 0.0, 0.00023416)),
    "link2": (1.3266, (-0.13225622308888, -0.0030617036386309, -0.0308306967030205), (0.00073374, -0.00000043, 0.00000851, 0.01255987, 0.00000128, 0.01281387)),
    "link3": (0.8353, (0.121040035791843, -0.0536211076627949, -0.0310137854608077), (0.00046807, -0.00003456, -0.00004260, 0.00632695, 0.00000006, 0.00648221)),
    "link4": (0.52, (0.0608200956293136, -0.0511711906613122, -0.030299458623927), (0.00045986, 0.00024219, -0.00000672, 0.00075258, -0.00000535, 0.00066742)),
    "link5": (0.383, (-0.00502802058982517, 0.00000173866206692364, 0.0386233236326755), (0.00019772, -0.00000062, -0.00002426, 0.00021737, 0.00000002, 0.00017191)),
    "link6": (0.3663, (0.00000376418727127126, -0.000100908819946677, 0.0253308606425965), (0.00015554, 0.0, 0.0, 0.00015554, 0.0, 0.00013966)),
    "gripper_link": (0.181800159145243, (-0.11400456131826, 0.0000730809328589541, -0.00000008098254686284), (0.000232385828322385, -0.000000277584025941111, -0.000000000604874349510246, 0.0000585085867377427, -0.0000000115493362444215, 0.000205213535851537)),
    "gripper_left": (0.0423278952416158, (0.00937154605945142, -0.0183514409006279, -0.00213050813223617), (0.00000968819007445228, -0.00000114547785891207, 0.0000000182410432419993, 0.0000097195653452821, 0.000000120737618180169, 0.0000113638462227589)),
    "gripper_right": (0.0423278949561274, (0.00937154599936671, 0.0183514410059713, 0.00213050822993754), (0.00000968819002375832, 0.00000114547786360874, -0.0000000182410118281856, 0.0000097195652747221, 0.000000120737613592695, 0.0000113638461944347)),
    "solar_r2_left_c01_snapshot": (0.78, (0.0, -0.231153846, 0.009015385), (0.030004785546499838, 0.0, 0.0, 0.004930698924865386, -0.002295028962016152, 0.03317408662163446)),
    "solar_r2_right_c01_snapshot": (0.78, (0.0, -0.231153846, 0.009015385), (0.030004785546499838, 0.0, 0.0, 0.004930698924865386, -0.002295028962016152, 0.03317408662163446)),
}

# Exact source-static primitive broadphase ledger.  Each item is
# (origin_xyz_in_link, origin_rpy_in_link, box_size_m).  It is copied from the
# pinned V2 source inputs and B601 link-local bounds; it is not narrowphase,
# physical-contact, CAD, manufacturing, or flight geometry authority.
SOURCE_STATIC_BROADPHASE_BOXES: dict[
    str, tuple[tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]], ...]
] = {
    "spacecraft_bus": (),
    "bus_primary_structure_candidate_v1": (
        ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.3405, 0.2263, 0.2263)),
    ),
    "load_bridge_candidate": (
        ((-1.272569222692219e-10, -1.072691633523576e-10, 0.005375000000000074), (0.0, 0.0, 0.0), (0.160, 0.160, 0.01075)),
    ),
    "m3r_lumped_link": (),
    "base_link": (
        ((8.499917997718473e-05, -2.1998530026736546e-05, 0.042479995727539056), (0.0, 0.0, 0.0), (0.09200000322496146, 0.09200000138696146, 0.08014999389648438)),
    ),
    "link1": (
        ((0.005269996107382928, -0.00014899511224148246, 0.038674981689453145), (0.0, 0.0, 0.0), (0.08690398244527683, 0.07725002229885372, 0.09854998779296875)),
    ),
    "link2": (
        ((-0.13174698905284665, -3.600180598871752e-05, -0.03135502280805903), (0.0, 0.0, 0.0), (0.3209999871775209, 0.05700004150792364, 0.0680000663026154)),
    ),
    "link3": (
        ((0.12220718575653167, -0.028827980387596312, -0.031039077406094594), (0.0, 0.0, 0.0), (0.29782561327610557, 0.10500002255553624, 0.08025002813858524)),
    ),
    "link4": (
        ((0.043413748174133196, -0.028354303942868253, -0.029989992086658663), (0.0, 0.0, 0.0), (0.14588395207493776, 0.11595737184106639, 0.06676003282946874)),
    ),
    "link5": (
        ((-0.0016750223766869264, -8.702040021112134e-05, 0.03673899048289639), (0.0, 0.0, 0.0), (0.07000000259065592, 0.07699999777302086, 0.08503997558596882)),
    ),
    "link6": (
        ((-3.6472411839922475e-05, 7.391637363161202e-06, 0.026795693445186338), (0.0, 0.0, 0.0), (0.07700004738170349, 0.06350450150569048, 0.06150011133261792)),
    ),
    "gripper_link": (
        ((-0.09061401748657226, 7.431030273438721e-06, 3.702545166015675e-05), (0.0, 0.0, 0.0), (0.033099998474121095, 0.18406967163085938, 0.06846666717529297)),
    ),
    "gripper_left": (),
    "gripper_right": (),
    "solar_r2_left_c01_snapshot": (
        ((0.0, -0.1, 0.0), (math.pi / 2.0, 0.0, 0.0), (0.300, 0.0025, 0.200)),
        ((0.0, -0.30000000000000004, -0.003), (math.pi / 2.0, 0.0, 0.0), (0.300, 0.0025, 0.200)),
        ((0.0, -0.5, -0.006), (math.pi / 2.0, 0.0, 0.0), (0.300, 0.0025, 0.200)),
    ),
    "solar_r2_right_c01_snapshot": (
        ((0.0, -0.1, 0.0), (math.pi / 2.0, 0.0, 0.0), (0.300, 0.0025, 0.200)),
        ((0.0, -0.30000000000000004, -0.003), (math.pi / 2.0, 0.0, 0.0), (0.300, 0.0025, 0.200)),
        ((0.0, -0.5, -0.006), (math.pi / 2.0, 0.0, 0.0), (0.300, 0.0025, 0.200)),
    ),
}
GEOMETRY_BOX_COUNTS = {
    name: len(boxes) for name, boxes in SOURCE_STATIC_BROADPHASE_BOXES.items()
}

# name, type, parent, child, xyz, rpy, axis-or-None, lower/upper/effort/velocity-or-None
JOINTS: tuple[tuple[Any, ...], ...] = (
    ("bus_to_bus_primary_structure_candidate_v1", "fixed", "spacecraft_bus", "bus_primary_structure_candidate_v1", (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), None, None),
    ("bus_to_D_BUS_MATE_PHYSICAL", "fixed", "spacecraft_bus", "D_BUS_MATE_PHYSICAL", (0.18525, 0.0, 0.0), (0.0, 1.5707963267948966, 0.0), None, None),
    ("D_BUS_MATE_PHYSICAL_to_D_BUS_M6_PATTERN", "fixed", "D_BUS_MATE_PHYSICAL", "D_BUS_M6_PATTERN", (0.000086366070, 0.000015994151, 0.0), (0.0, 0.0, 0.4363325573440537), None, None),
    ("D_BUS_M6_PATTERN_to_load_bridge_candidate", "fixed", "D_BUS_M6_PATTERN", "load_bridge_candidate", (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), None, None),
    ("load_bridge_candidate_to_m3r_lumped_link", "fixed", "load_bridge_candidate", "m3r_lumped_link", (0.0, 0.0, 0.02275), (0.0, 0.0, 0.0), None, None),
    ("m3r_lumped_link_to_base_link", "fixed", "m3r_lumped_link", "base_link", (-0.00008503365669377021, 0.00002200427555603084, 0.0), (0.0, 0.0, 0.0), None, None),
    ("joint1", "revolute", "base_link", "link1", (-0.00008416, 0.0, 0.08465), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (-2.8, 2.8, 27.0, 50.0)),
    ("joint2", "revolute", "link1", "link2", (0.020084, 0.031625, 0.05555), (-1.5708, 0.0, 0.0), (0.0, 0.0, -1.0), (-3.14, 0.0, 27.0, 50.0)),
    ("joint3", "revolute", "link2", "link3", (-0.264, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (-3.14, 0.0, 27.0, 50.0)),
    ("joint4", "revolute", "link3", "link4", (0.2426, -0.054, -0.001625), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (-1.87, 1.57, 7.0, 200.0)),
    ("joint5", "revolute", "link4", "link5", (0.078308, -0.0375, -0.03), (-1.5708, 0.0, 0.0), (0.0, 0.0, 1.0), (-1.57, 1.57, 7.0, 200.0)),
    ("joint6", "revolute", "link5", "link6", (0.023692, 0.0, 0.04), (0.0, 1.5708, 0.0), (0.0, 0.0, 1.0), (-3.14, 3.14, 7.0, 200.0)),
    ("gripper_joint", "fixed", "link6", "gripper_link", (0.0, 0.0, 0.15971), (0.0, -1.5708, 0.0), None, None),
    ("gripper_joint1", "prismatic", "gripper_link", "gripper_left", (-0.042091, 0.000027531, -0.000013031), (0.0, 0.0, -1.5708), (1.0, 0.0, 0.0), (0.0, 0.0715, 100.0, 15.0)),
    ("gripper_joint2", "prismatic", "gripper_link", "gripper_right", (-0.042091, -0.000027531, 0.000013031), (0.0, 0.0, 1.5708), (1.0, 0.0, 0.0), (0.0, 0.0715, 100.0, 15.0)),
    ("bus_to_M_DYNAMICS_NONPHYSICAL", "fixed", "spacecraft_bus", "M_DYNAMICS_NONPHYSICAL", (0.18525, 0.0, 0.0), (0.0, 1.5707963267948966, 0.0), None, None),
    ("bus_to_solar_r2_left_c01_snapshot", "fixed", "spacecraft_bus", "solar_r2_left_c01_snapshot", (0.0, 0.1154, -0.10815), (0.0, 0.0, math.pi), None, None),
    ("bus_to_solar_r2_right_c01_snapshot", "fixed", "spacecraft_bus", "solar_r2_right_c01_snapshot", (0.0, -0.1154, -0.10815), (0.0, 0.0, 0.0), None, None),
)


class URDFContractError(ValueError):
    pass


def _fmt(values: tuple[float, ...]) -> str:
    return " ".join(f"{value:.17g}" for value in values)


def _vector(text: str | None, *, path: str) -> tuple[float, float, float]:
    if text is None:
        raise URDFContractError(f"MISSING_VECTOR:{path}")
    try:
        values = tuple(float(part) for part in text.split())
    except ValueError as exc:
        raise URDFContractError(f"INVALID_VECTOR:{path}") from exc
    if len(values) != 3 or any(not math.isfinite(value) for value in values):
        raise URDFContractError(f"INVALID_VECTOR:{path}")
    return values  # type: ignore[return-value]


def _scalar(text: str | None, *, path: str) -> float:
    try:
        value = float(text)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise URDFContractError(f"INVALID_SCALAR:{path}") from exc
    if not math.isfinite(value):
        raise URDFContractError(f"INVALID_SCALAR:{path}")
    return value


def _same(actual: tuple[float, ...], expected: tuple[float, ...], path: str) -> None:
    # Exact parsed-float contract: even a 1e-30 drift from an expected zero is
    # rejected.  This is a source-static identity test, not a physical tolerance.
    if actual != expected:
        raise URDFContractError(f"EXACT_NUMERIC_MISMATCH:{path}")


def _validate_mesh_uri(uri: str) -> None:
    if not uri or "\x00" in uri or "\\" in uri or ":" in uri or uri.startswith("/"):
        raise URDFContractError("UNSAFE_MESH_REFERENCE")
    raw_parts = uri.split("/")
    path = PurePosixPath(uri)
    if "//" in uri or any(part in ("", ".", "..") for part in raw_parts) or path.parts[0] != "meshes":
        raise URDFContractError("UNSAFE_MESH_REFERENCE")


def _require_child_tags(element: ET.Element, tags: tuple[str, ...], path: str) -> None:
    actual = tuple(child.tag for child in list(element))
    if actual != tags:
        raise URDFContractError(f"EXACT_CHILD_SEQUENCE_MISMATCH:{path}:{actual}")


def _require_leaf(element: ET.Element, path: str) -> None:
    if list(element):
        raise URDFContractError(f"LEAF_ELEMENT_HAS_CHILDREN:{path}")


def _add_fixture_box(
    link: ET.Element,
    spec: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]],
) -> None:
    origin, rpy, size = spec
    for tag in ("visual", "collision"):
        node = ET.SubElement(link, tag)
        ET.SubElement(node, "origin", {"xyz": _fmt(origin), "rpy": _fmt(rpy)})
        geometry = ET.SubElement(node, "geometry")
        ET.SubElement(geometry, "box", {"size": _fmt(size)})


def build_synthetic_parser_fixture_bytes() -> bytes:
    """Build a deterministic in-memory parser fixture; never write it to disk."""

    root = ET.Element("robot", {"name": ROBOT_NAME})
    root.append(ET.Comment("SYNTHETIC_PARSER_FIXTURE_ONLY__NO_SYSTEM_BINDING_CREDIT"))
    for name, (mass, com, inertia) in PHYSICAL_INERTIALS.items():
        link = ET.SubElement(root, "link", {"name": name})
        inertial = ET.SubElement(link, "inertial")
        ET.SubElement(inertial, "origin", {"xyz": _fmt(com), "rpy": "0 0 0"})
        ET.SubElement(inertial, "mass", {"value": f"{mass:.17g}"})
        ET.SubElement(
            inertial,
            "inertia",
            dict(zip(("ixx", "ixy", "ixz", "iyy", "iyz", "izz"), _fmt(inertia).split())),
        )
        for box_spec in SOURCE_STATIC_BROADPHASE_BOXES[name]:
            _add_fixture_box(link, box_spec)
    for name in FRAME_ONLY_LINKS:
        ET.SubElement(root, "link", {"name": name})
    for name, kind, parent, child, xyz, rpy, axis, limits in JOINTS:
        joint = ET.SubElement(root, "joint", {"name": name, "type": kind})
        ET.SubElement(joint, "parent", {"link": parent})
        ET.SubElement(joint, "child", {"link": child})
        ET.SubElement(joint, "origin", {"xyz": _fmt(xyz), "rpy": _fmt(rpy)})
        if axis is not None:
            ET.SubElement(joint, "axis", {"xyz": _fmt(axis)})
        if limits is not None:
            ET.SubElement(
                joint,
                "limit",
                dict(zip(("lower", "upper", "effort", "velocity"), _fmt(limits).split())),
            )
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def validate_system_urdf_bytes(payload: bytes) -> dict[str, Any]:
    """Validate exact topology, fields, inertials and safe geometry references."""

    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")
    upper = payload.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise URDFContractError("DTD_OR_ENTITY_FORBIDDEN")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise URDFContractError("INVALID_XML") from exc
    if root.tag != "robot" or root.attrib != {"name": ROBOT_NAME}:
        raise URDFContractError("ROBOT_IDENTITY_MISMATCH")
    mesh_nodes = root.findall(".//mesh")
    for mesh in mesh_nodes:
        if set(mesh.attrib) != {"filename"}:
            raise URDFContractError("MESH_ATTRIBUTE_SET_MISMATCH")
        _validate_mesh_uri(mesh.get("filename", ""))
        _require_leaf(mesh, "mesh")
    if mesh_nodes:
        raise URDFContractError("MESH_GEOMETRY_FORBIDDEN_BY_V2_PRIMITIVE_CONTRACT")
    unknown_root_children = [
        child.tag
        for child in list(root)
        if child.tag is not ET.Comment and child.tag not in ("link", "joint")
    ]
    if unknown_root_children:
        raise URDFContractError(f"UNKNOWN_ROOT_CHILD:{unknown_root_children}")
    links = root.findall("link")
    joints = root.findall("joint")
    if (len(links), len(joints)) != (19, 18):
        raise URDFContractError("TOPOLOGY_COUNT_MISMATCH")
    link_map = {link.get("name"): link for link in links}
    joint_map = {joint.get("name"): joint for joint in joints}
    if None in link_map or len(link_map) != 19 or set(link_map) != set(PHYSICAL_INERTIALS) | set(FRAME_ONLY_LINKS):
        raise URDFContractError("LINK_SET_MISMATCH")
    if None in joint_map or len(joint_map) != 18 or set(joint_map) != {item[0] for item in JOINTS}:
        raise URDFContractError("JOINT_SET_MISMATCH")

    total_mass = 0.0
    for name, (expected_mass, expected_com, expected_inertia) in PHYSICAL_INERTIALS.items():
        link = link_map[name]
        if link.attrib != {"name": name}:
            raise URDFContractError(f"LINK_ATTRIBUTE_SET_MISMATCH:{name}")
        inertials = link.findall("inertial")
        if len(inertials) != 1:
            raise URDFContractError(f"INERTIAL_COUNT_MISMATCH:{name}")
        inertial = inertials[0]
        if inertial.attrib:
            raise URDFContractError(f"INERTIAL_ATTRIBUTE_SET_MISMATCH:{name}")
        _require_child_tags(inertial, ("origin", "mass", "inertia"), f"{name}/inertial")
        origin = inertial.find("origin")
        mass = inertial.find("mass")
        tensor = inertial.find("inertia")
        if origin is None or mass is None or tensor is None:
            raise URDFContractError(f"INERTIAL_FIELD_MISSING:{name}")
        if set(origin.attrib) != {"xyz", "rpy"}:
            raise URDFContractError(f"INERTIAL_ORIGIN_ATTRIBUTE_SET_MISMATCH:{name}")
        if set(mass.attrib) != {"value"}:
            raise URDFContractError(f"MASS_ATTRIBUTE_SET_MISMATCH:{name}")
        _require_leaf(origin, f"{name}/inertial/origin")
        _require_leaf(mass, f"{name}/inertial/mass")
        _require_leaf(tensor, f"{name}/inertial/inertia")
        _same(_vector(origin.get("xyz"), path=f"{name}/inertial/origin/xyz"), expected_com, f"{name}/COM")
        _same(_vector(origin.get("rpy"), path=f"{name}/inertial/origin/rpy"), (0.0, 0.0, 0.0), f"{name}/inertial_rpy")
        actual_mass = _scalar(mass.get("value"), path=f"{name}/mass")
        _same((actual_mass,), (expected_mass,), f"{name}/mass")
        if set(tensor.attrib) != {"ixx", "ixy", "ixz", "iyy", "iyz", "izz"}:
            raise URDFContractError(f"INERTIA_TENSOR_FIELD_SET_MISMATCH:{name}")
        actual_tensor = tuple(_scalar(tensor.get(field), path=f"{name}/{field}") for field in ("ixx", "ixy", "ixz", "iyy", "iyz", "izz"))
        _same(actual_tensor, expected_inertia, f"{name}/inertia")
        total_mass += actual_mass
        visuals = link.findall("visual")
        collisions = link.findall("collision")
        expected_specs = SOURCE_STATIC_BROADPHASE_BOXES[name]
        expected_boxes = len(expected_specs)
        if len(visuals) != expected_boxes or len(collisions) != expected_boxes:
            raise URDFContractError(f"GEOMETRY_CLASS_OR_COUNT_MISMATCH:{name}")
        expected_link_children = ("inertial",) + tuple(
            tag for _ in expected_specs for tag in ("visual", "collision")
        )
        _require_child_tags(link, expected_link_children, name)
        for geometry_class, nodes in (("visual", visuals), ("collision", collisions)):
            for index, (node, expected_spec) in enumerate(zip(nodes, expected_specs)):
                expected_xyz, expected_rpy, expected_size = expected_spec
                if node.attrib:
                    raise URDFContractError(f"GEOMETRY_NODE_ATTRIBUTE_SET_MISMATCH:{name}:{geometry_class}:{index}")
                _require_child_tags(node, ("origin", "geometry"), f"{name}/{geometry_class}/{index}")
                geometry_origin = node.find("origin")
                geometry = node.find("geometry")
                if geometry_origin is None or geometry is None:
                    raise URDFContractError(f"GEOMETRY_FIELD_MISSING:{name}:{geometry_class}:{index}")
                if set(geometry_origin.attrib) != {"xyz", "rpy"} or geometry.attrib:
                    raise URDFContractError(f"GEOMETRY_ATTRIBUTE_SET_MISMATCH:{name}:{geometry_class}:{index}")
                _same(
                    _vector(geometry_origin.get("xyz"), path=f"{name}/{geometry_class}/{index}/origin_xyz"),
                    expected_xyz,
                    f"{name}/{geometry_class}/{index}/origin_xyz",
                )
                _same(
                    _vector(geometry_origin.get("rpy"), path=f"{name}/{geometry_class}/{index}/origin_rpy"),
                    expected_rpy,
                    f"{name}/{geometry_class}/{index}/origin_rpy",
                )
                _require_child_tags(geometry, ("box",), f"{name}/{geometry_class}/{index}/geometry")
                box = geometry.find("box")
                if box is None or set(box.attrib) != {"size"}:
                    raise URDFContractError(f"BOX_ATTRIBUTE_SET_MISMATCH:{name}:{geometry_class}:{index}")
                _require_leaf(geometry_origin, f"{name}/{geometry_class}/{index}/origin")
                _require_leaf(box, f"{name}/{geometry_class}/{index}/box")
                size = _vector(box.get("size"), path=f"{name}/{geometry_class}/{index}/size")
                if any(value <= 0.0 for value in size):
                    raise URDFContractError(f"NONPOSITIVE_BOX_SIZE:{name}:{geometry_class}:{index}")
                _same(size, expected_size, f"{name}/{geometry_class}/{index}/size")
    _same((math.fsum(
        _scalar(link_map[name].find("inertial/mass").get("value"), path=f"{name}/mass")
        for name in PHYSICAL_INERTIALS
    ),), (TOTAL_MASS_KG,), "total_mass")

    for name in FRAME_ONLY_LINKS:
        if link_map[name].attrib != {"name": name}:
            raise URDFContractError(f"LINK_ATTRIBUTE_SET_MISMATCH:{name}")
        if list(link_map[name]):
            raise URDFContractError(f"FRAME_ONLY_LINK_CONTAMINATED:{name}")
    children: dict[str, str] = {}
    type_counts = {"fixed": 0, "revolute": 0, "prismatic": 0}
    for expected in JOINTS:
        name, kind, parent, child, xyz, rpy, axis, limits = expected
        joint = joint_map[name]
        if joint.attrib != {"name": name, "type": kind}:
            raise URDFContractError(f"JOINT_IDENTITY_MISMATCH:{name}")
        parent_element = joint.find("parent")
        child_element = joint.find("child")
        origin = joint.find("origin")
        if parent_element is None or child_element is None or origin is None:
            raise URDFContractError(f"JOINT_FIELD_MISSING:{name}")
        expected_children = ("parent", "child", "origin") if axis is None else ("parent", "child", "origin", "axis", "limit")
        _require_child_tags(joint, expected_children, name)
        if set(parent_element.attrib) != {"link"} or set(child_element.attrib) != {"link"}:
            raise URDFContractError(f"PARENT_CHILD_ATTRIBUTE_SET_MISMATCH:{name}")
        if set(origin.attrib) != {"xyz", "rpy"}:
            raise URDFContractError(f"JOINT_ORIGIN_ATTRIBUTE_SET_MISMATCH:{name}")
        _require_leaf(parent_element, f"{name}/parent")
        _require_leaf(child_element, f"{name}/child")
        _require_leaf(origin, f"{name}/origin")
        if parent_element.attrib != {"link": parent} or child_element.attrib != {"link": child}:
            raise URDFContractError(f"PARENT_CHILD_MISMATCH:{name}")
        _same(_vector(origin.get("xyz"), path=f"{name}/origin/xyz"), xyz, f"{name}/origin_xyz")
        _same(_vector(origin.get("rpy"), path=f"{name}/origin/rpy"), rpy, f"{name}/origin_rpy")
        axis_element = joint.find("axis")
        limit_element = joint.find("limit")
        if axis is None:
            if axis_element is not None or limit_element is not None:
                raise URDFContractError(f"FIXED_JOINT_HAS_MOTION_FIELDS:{name}")
        else:
            if axis_element is None or limit_element is None:
                raise URDFContractError(f"MOVABLE_JOINT_FIELD_MISSING:{name}")
            if set(axis_element.attrib) != {"xyz"}:
                raise URDFContractError(f"AXIS_ATTRIBUTE_SET_MISMATCH:{name}")
            _require_leaf(axis_element, f"{name}/axis")
            _require_leaf(limit_element, f"{name}/limit")
            _same(_vector(axis_element.get("xyz"), path=f"{name}/axis"), axis, f"{name}/axis_and_sign")
            if set(limit_element.attrib) != {"lower", "upper", "effort", "velocity"}:
                raise URDFContractError(f"JOINT_LIMIT_FIELD_SET_MISMATCH:{name}")
            actual_limits = tuple(_scalar(limit_element.get(field), path=f"{name}/{field}") for field in ("lower", "upper", "effort", "velocity"))
            _same(actual_limits, limits, f"{name}/limits")
        if child in children:
            raise URDFContractError(f"MULTIPLE_PARENT:{child}")
        children[child] = parent
        type_counts[kind] += 1

    if type_counts != {"fixed": 10, "revolute": 6, "prismatic": 2}:
        raise URDFContractError("JOINT_TYPE_COUNT_MISMATCH")
    roots = set(link_map) - set(children)
    if roots != {"spacecraft_bus"}:
        raise URDFContractError("ROOT_LINK_MISMATCH")
    for link_name in link_map:
        seen: set[str] = set()
        cursor = link_name
        while cursor in children:
            if cursor in seen:
                raise URDFContractError("KINEMATIC_CYCLE")
            seen.add(cursor)
            cursor = children[cursor]
        if cursor != "spacecraft_bus":
            raise URDFContractError("DISCONNECTED_KINEMATIC_TREE")
    physical_path = (
        "spacecraft_bus",
        "D_BUS_MATE_PHYSICAL",
        "D_BUS_M6_PATTERN",
        "load_bridge_candidate",
        "m3r_lumped_link",
        "base_link",
    )
    for parent, child in zip(physical_path, physical_path[1:]):
        if children.get(child) != parent:
            raise URDFContractError("PHYSICAL_LOAD_PATH_MISMATCH")
    if "M_DYNAMICS_NONPHYSICAL" in physical_path:
        raise URDFContractError("PHYSICAL_PATH_TRAVERSES_NONPHYSICAL_M")
    return {
        "robot_name": ROBOT_NAME,
        "links": 19,
        "physical_links": 16,
        "frame_only_links": 3,
        "joints": 18,
        "fixed": 10,
        "revolute": 6,
        "prismatic": 2,
        "actuated_dof": 8,
        "total_mass_kg": math.fsum(item[0] for item in PHYSICAL_INERTIALS.values()),
        "mesh_references": len(root.findall(".//mesh")),
        "visual_box_count": sum(GEOMETRY_BOX_COUNTS.values()),
        "collision_box_count": sum(GEOMETRY_BOX_COUNTS.values()),
        "geometry_contract": "EXACT_SOURCE_STATIC_PRIMITIVE_BROADPHASE_ONLY__NO_NARROWPHASE_OR_PHYSICAL_CONTACT_CREDIT",
        "numeric_comparison": "EXACT_PARSED_FLOAT_NO_TOLERANCE",
        "fixture_only": True,
    }


__all__ = [
    "FRAME_ONLY_LINKS",
    "GEOMETRY_BOX_COUNTS",
    "JOINTS",
    "NUMERIC_TOLERANCE",
    "PHYSICAL_INERTIALS",
    "ROBOT_NAME",
    "SOURCE_STATIC_BROADPHASE_BOXES",
    "TOTAL_MASS_KG",
    "URDFContractError",
    "build_synthetic_parser_fixture_bytes",
    "validate_system_urdf_bytes",
]
