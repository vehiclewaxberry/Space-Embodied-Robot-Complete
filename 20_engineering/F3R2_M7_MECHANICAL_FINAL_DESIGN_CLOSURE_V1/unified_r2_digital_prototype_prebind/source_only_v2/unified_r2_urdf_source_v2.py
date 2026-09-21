#!/usr/bin/env python3
"""Dormant Unified-R2 V2 URDF source with explicit bus-structure bookkeeping.

Import is side-effect free. ``gen_urdf()`` is the only public generation entry
point and takes zero arguments.  It returns an in-memory XML root only after a
fresh, hash-bound, time-bounded and single-use execution record passes; it never
writes a ``.urdf`` file.  The private ``_build_robot`` is intentionally available
to the independent source-only validator for in-memory topology inspection.
"""

from __future__ import annotations

import copy
import ctypes
import hashlib
import json
import marshal
import math
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
INPUTS_PATH = HERE / "UNIFIED_R2_URDF_SOURCE_INPUTS_V2.yaml"
AUTHORITY_PATH = HERE / "UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2.json"
RUN_CONSUMPTION_DIR = HERE / ".unified_r2_v2_run_consumption"
OVERRIDE_CONSUMPTION_DIR = HERE / ".unified_r2_v2_override_consumption"
ACTIVE_RUN_LOCK_PATH = HERE / ".unified_r2_v2_active_run.lock"

ROBOT_NAME = "unified_r2_c01_no_route_c_sim_candidate_v2"
SELECTED_MODE = "EXPLICIT_STRUCTURE_PLUS_RESIDUAL"
MEMORY_GATE_GIB = 6.0
MAX_AUTHORITY_VALIDITY_SECONDS = 7200.0
REQUIRED_LOW_MEMORY_RISK_ACK = "ACCEPT_SINGLE_RUN_LOW_MEMORY_RISK"
EXPECTED_TOTAL_MASS_KG = 31.022864807342987
EXPECTED_BY_MODE = {
    "AGGREGATE_BUS": {
        "physical_links": 15,
        "frame_only_links": 3,
        "links": 18,
        "joints": 17,
        "fixed": 9,
        "revolute": 6,
        "prismatic": 2,
        "actuated_dof": 8,
    },
    "EXPLICIT_STRUCTURE_PLUS_RESIDUAL": {
        "physical_links": 16,
        "frame_only_links": 3,
        "links": 19,
        "joints": 18,
        "fixed": 10,
        "revolute": 6,
        "prismatic": 2,
        "actuated_dof": 8,
    },
}
FRAME_ONLY_LINKS = {
    "D_BUS_MATE_PHYSICAL",
    "M_DYNAMICS_NONPHYSICAL",
    "D_BUS_M6_PATTERN",
}


def _fmt(values) -> str:
    return " ".join(f"{float(value):.16g}" for value in values)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _load_inputs_snapshot() -> tuple[dict[str, Any], str]:
    """Parse and hash the exact same immutable input byte snapshot."""

    payload = INPUTS_PATH.read_bytes()
    return yaml.safe_load(payload.decode("utf-8-sig")), hashlib.sha256(payload).hexdigest().upper()


def _available_memory_gib() -> float | None:
    if os.name == "nt":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return status.ullAvailPhys / (1024.0**3)
        return None
    try:
        return int(os.sysconf("SC_PAGE_SIZE")) * int(os.sysconf("SC_AVPHYS_PAGES")) / (1024.0**3)
    except (AttributeError, OSError, TypeError, ValueError):
        return None


def _parse_utc(value: str, field: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise RuntimeError(f"GENERATION_NOT_AUTHORIZED_PREBIND: invalid {field}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0.0:
        raise RuntimeError(f"GENERATION_NOT_AUTHORIZED_PREBIND: {field} must carry explicit UTC")
    return parsed.astimezone(timezone.utc)


def _safe_id(value: str) -> bool:
    return 12 <= len(value) <= 128 and all(ch.isalnum() or ch in "-_:" for ch in value)


def _atomic_consume(directory: Path, identifier: str, payload: dict[str, Any], error_token: str) -> str:
    digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest().upper()
    directory.mkdir(parents=False, exist_ok=True)
    marker = directory / f"{digest}.json"
    try:
        with marker.open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True, ensure_ascii=False)
            stream.write("\n")
    except FileExistsError as exc:
        raise RuntimeError(error_token) from exc
    return marker.relative_to(HERE).as_posix()


def _acquire_active_lock(payload: dict[str, Any]) -> str:
    try:
        with ACTIVE_RUN_LOCK_PATH.open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True, ensure_ascii=False)
            stream.write("\n")
    except FileExistsError as exc:
        raise RuntimeError(
            "GENERATION_NOT_AUTHORIZED_PREBIND: ACTIVE_WRITER_LOCK_PRESENT; inspect and clear only after confirming no generator remains"
        ) from exc
    return ACTIVE_RUN_LOCK_PATH.relative_to(HERE).as_posix()


def _release_active_lock(run_id: str) -> None:
    try:
        payload = json.loads(ACTIVE_RUN_LOCK_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        raise RuntimeError("ACTIVE_WRITER_LOCK_UNREADABLE_OR_MISSING_FAIL_CLOSED") from exc
    if payload.get("run_id") != run_id:
        raise RuntimeError("ACTIVE_WRITER_LOCK_OWNER_MISMATCH_FAIL_CLOSED")
    ACTIVE_RUN_LOCK_PATH.unlink()


def _verify_source_pins(inputs: dict[str, Any]) -> dict[str, bytes]:
    """Hash exact byte snapshots and return those snapshots to the builder."""

    failures = []
    payloads: dict[str, bytes] = {}
    for pin_id, pin in inputs["source_pins"].items():
        path = ROOT / pin["path"]
        if not path.is_file():
            failures.append(pin_id)
            continue
        payload = path.read_bytes()
        payloads[pin_id] = payload
        if len(payload) != int(pin["bytes"]) or hashlib.sha256(payload).hexdigest().upper() != pin["sha256"]:
            failures.append(pin_id)
    if failures:
        raise RuntimeError("SOURCE_PIN_DRIFT_FAIL_CLOSED: " + ",".join(failures))
    return payloads


def _require_execution_authority(
    inputs: dict[str, Any],
    input_snapshot_sha256: str,
    runtime_code_sha256: str,
) -> dict[str, Any]:
    if not AUTHORITY_PATH.is_file():
        raise RuntimeError("GENERATION_NOT_AUTHORIZED_PREBIND: V2 execution authorization absent")
    record = json.loads(AUTHORITY_PATH.read_text(encoding="utf-8-sig"))
    if record.get("schema") != "UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2":
        raise RuntimeError("GENERATION_NOT_AUTHORIZED_PREBIND: authorization schema mismatch")
    flags = record.get("authority_flags", {})
    required_true = (
        "rebase_execution_authorized",
        "unified_r2_v2_generation_authorized",
        "system_urdf_generation_authorized",
        "route_c_exclusion_accepted_for_this_sim_candidate",
        "memory_admitted_for_this_execution",
    )
    if any(flags.get(name) is not True for name in required_true):
        raise RuntimeError("GENERATION_NOT_AUTHORIZED_PREBIND: exact-true prerequisite missing")
    if flags.get("route_c_cad_authorized") is not False:
        raise RuntimeError("GENERATION_NOT_AUTHORIZED_PREBIND: Route-C authorization is outside this candidate")
    if record.get("owner_accepted") is not True:
        raise RuntimeError("GENERATION_NOT_AUTHORIZED_PREBIND: Owner acceptance absent")
    if record.get("selected_bus_mass_mode") != inputs["selected_bus_mass_mode"]:
        raise RuntimeError("GENERATION_NOT_AUTHORIZED_PREBIND: bus mass mode mismatch")

    run_id = str(record.get("run_id", ""))
    if not _safe_id(run_id):
        raise RuntimeError("GENERATION_NOT_AUTHORIZED_PREBIND: fresh safe run_id required")
    issued = _parse_utc(str(record.get("issued_utc", "")), "issued_utc")
    expires = _parse_utc(str(record.get("expires_utc", "")), "expires_utc")
    now = datetime.now(timezone.utc)
    validity = (expires - issued).total_seconds()
    if not (issued <= now < expires) or not (0.0 < validity <= MAX_AUTHORITY_VALIDITY_SECONDS):
        raise RuntimeError("GENERATION_NOT_AUTHORIZED_PREBIND: authorization not current or exceeds two hours")

    source_hash = _sha256(Path(__file__))
    input_hash = _sha256(INPUTS_PATH)
    if (
        record.get("source_sha256") != source_hash
        or record.get("input_sha256") != input_snapshot_sha256
        or input_hash != input_snapshot_sha256
        or record.get("runtime_code_sha256") != runtime_code_sha256
    ):
        raise RuntimeError("GENERATION_NOT_AUTHORIZED_PREBIND: source/input hash binding mismatch")

    available_gib = _available_memory_gib()
    below_gate = available_gib is None or available_gib < MEMORY_GATE_GIB
    override = record.get("low_memory_owner_override")
    if below_gate:
        if not isinstance(override, dict) or not _safe_id(str(override.get("owner_override_id", ""))):
            raise RuntimeError("MEMORY_GATE_HOLD: fresh run-specific Owner Override required")
        if override.get("risk_ack") != REQUIRED_LOW_MEMORY_RISK_ACK:
            raise RuntimeError("MEMORY_GATE_HOLD: exact low-memory risk acknowledgement required")
        if override.get("issued_utc") != record.get("issued_utc") or override.get("expires_utc") != record.get("expires_utc"):
            raise RuntimeError("MEMORY_GATE_HOLD: override and execution validity windows must match")
        if override.get("run_id") != run_id:
            raise RuntimeError("MEMORY_GATE_HOLD: Owner Override must bind the exact execution run_id")

    run_digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest().upper()
    if (RUN_CONSUMPTION_DIR / f"{run_digest}.json").exists():
        raise RuntimeError("RUN_ID_ALREADY_CONSUMED")
    if below_gate:
        override_id = str(override["owner_override_id"])
        override_digest = hashlib.sha256(override_id.encode("utf-8")).hexdigest().upper()
        if (OVERRIDE_CONSUMPTION_DIR / f"{override_digest}.json").exists():
            raise RuntimeError("LOW_MEMORY_OVERRIDE_ALREADY_CONSUMED")

    lock_marker = _acquire_active_lock(
        {
            "schema": "UNIFIED_R2_V2_ACTIVE_WRITER_LOCK",
            "run_id": run_id,
            "acquired_utc": now.isoformat().replace("+00:00", "Z"),
            "source_sha256": source_hash,
            "input_sha256": input_snapshot_sha256,
            "runtime_code_sha256": runtime_code_sha256,
            "exception_policy": "RETAIN_FOR_OWNER_INSPECTION_AND_MANUAL_CLEARANCE",
        }
    )
    run_marker = _atomic_consume(
        RUN_CONSUMPTION_DIR,
        run_id,
        {
            "schema": "UNIFIED_R2_V2_RUN_CONSUMPTION",
            "run_id": run_id,
            "consumed_utc": now.isoformat().replace("+00:00", "Z"),
            "source_sha256": source_hash,
            "input_sha256": input_snapshot_sha256,
            "runtime_code_sha256": runtime_code_sha256,
            "selected_bus_mass_mode": inputs["selected_bus_mass_mode"],
        },
        "RUN_ID_ALREADY_CONSUMED",
    )
    override_marker = None
    if below_gate:
        override_marker = _atomic_consume(
            OVERRIDE_CONSUMPTION_DIR,
            str(override["owner_override_id"]),
            {
                **override,
                "schema": "UNIFIED_R2_V2_LOW_MEMORY_OVERRIDE_CONSUMPTION",
                "consumed_utc": now.isoformat().replace("+00:00", "Z"),
                "memory_gate_status": "OWNER_OVERRIDE_LOW_MEMORY",
                "memory_gate_passed": False,
                "execution_authorized": True,
            },
            "LOW_MEMORY_OVERRIDE_ALREADY_CONSUMED",
        )
    return {
        **record,
        "available_memory_gib": available_gib,
        "memory_gate_gib": MEMORY_GATE_GIB,
        "memory_gate_status": "OWNER_OVERRIDE_LOW_MEMORY" if below_gate else "MET_WITHOUT_OVERRIDE",
        "memory_gate_passed": not below_gate,
        "execution_authorized": True,
        "run_consumption_marker": run_marker,
        "override_consumption_marker": override_marker,
        "active_writer_lock": lock_marker,
    }


def _transpose(a):
    return [list(row) for row in zip(*a)]


def _matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(len(b))) for j in range(len(b[0]))] for i in range(len(a))]


def _matvec(a, v):
    return [sum(a[i][k] * v[k] for k in range(len(v))) for i in range(len(a))]


def _sub(a, b):
    return [x - y for x, y in zip(a, b)]


def _rotation(T):
    return [row[:3] for row in T[:3]]


def _translation(T):
    return [row[3] for row in T[:3]]


def _inverse_transform(T):
    R = _rotation(T)
    Rt = _transpose(R)
    t_inv = [-value for value in _matvec(Rt, _translation(T))]
    return [Rt[0] + [t_inv[0]], Rt[1] + [t_inv[1]], Rt[2] + [t_inv[2]], [0.0, 0.0, 0.0, 1.0]]


def _rpy_from_rotation(R):
    pitch = math.asin(max(-1.0, min(1.0, -R[2][0])))
    cp = math.cos(pitch)
    if abs(cp) > 1.0e-12:
        return [math.atan2(R[2][1], R[2][2]), pitch, math.atan2(R[1][0], R[0][0])]
    return [math.atan2(-R[1][2], R[1][1]), pitch, 0.0]


def _to_link_properties(component: dict[str, Any], T_S_link):
    R = _rotation(T_S_link)
    Rt = _transpose(R)
    com_link = _matvec(Rt, _sub(component["com_S_m"], _translation(T_S_link)))
    inertia_link = _matmul(_matmul(Rt, component["inertia_about_com_S_kg_m2"]), R)
    return com_link, inertia_link


def _add_inertial(link, component: dict[str, Any], T_S_link=None):
    if T_S_link is None:
        com = component["com_S_m"]
        inertia = component["inertia_about_com_S_kg_m2"]
    else:
        com, inertia = _to_link_properties(component, T_S_link)
    inertial = ET.SubElement(link, "inertial")
    ET.SubElement(inertial, "origin", {"xyz": _fmt(com), "rpy": "0 0 0"})
    ET.SubElement(inertial, "mass", {"value": f"{float(component['mass_kg']):.16g}"})
    ET.SubElement(
        inertial,
        "inertia",
        {
            "ixx": f"{float(inertia[0][0]):.16g}",
            "ixy": f"{float(inertia[0][1]):.16g}",
            "ixz": f"{float(inertia[0][2]):.16g}",
            "iyy": f"{float(inertia[1][1]):.16g}",
            "iyz": f"{float(inertia[1][2]):.16g}",
            "izz": f"{float(inertia[2][2]):.16g}",
        },
    )


def _add_box(link, size, origin=(0.0, 0.0, 0.0), rpy=(0.0, 0.0, 0.0), include_collision=True):
    for tag, enabled in (("visual", True), ("collision", include_collision)):
        if enabled:
            node = ET.SubElement(link, tag)
            ET.SubElement(node, "origin", {"xyz": _fmt(origin), "rpy": _fmt(rpy)})
            geometry = ET.SubElement(node, "geometry")
            ET.SubElement(geometry, "box", {"size": _fmt(size)})


def _add_fixed_joint(robot, name: str, parent: str, child: str, T_parent_child):
    joint = ET.SubElement(robot, "joint", {"name": name, "type": "fixed"})
    ET.SubElement(joint, "parent", {"link": parent})
    ET.SubElement(joint, "child", {"link": child})
    ET.SubElement(
        joint,
        "origin",
        {"xyz": _fmt(_translation(T_parent_child)), "rpy": _fmt(_rpy_from_rotation(_rotation(T_parent_child)))},
    )


def _box_from_bounds(bounds):
    lower, upper = bounds
    size = [upper[i] - lower[i] for i in range(3)]
    center = [(upper[i] + lower[i]) / 2.0 for i in range(3)]
    if any(value <= 0.0 for value in size):
        raise RuntimeError("non-positive broad-phase box")
    return center, size


def _append_b601_subtree(robot, inputs, source_payloads: dict[str, bytes] | None = None):
    if source_payloads is None:
        arm_payload = (ROOT / inputs["source_pins"]["accepted_b601_urdf"]["path"]).read_bytes()
        bounds_payload = (ROOT / inputs["source_pins"]["b601_linklocal_bounds"]["path"]).read_bytes()
    else:
        arm_payload = source_payloads["accepted_b601_urdf"]
        bounds_payload = source_payloads["b601_linklocal_bounds"]
    arm_root = ET.fromstring(arm_payload)
    bounds = json.loads(bounds_payload.decode("utf-8-sig"))
    for source_link in arm_root.findall("link"):
        link = copy.deepcopy(source_link)
        for child in list(link):
            if child.tag in {"visual", "collision"}:
                link.remove(child)
        name = link.attrib["name"]
        if name in bounds["components"] and name != "legacy_gripper_detail":
            center, size = _box_from_bounds(bounds["components"][name]["local_surface"]["bounds_link_m"])
            _add_box(link, size, center)
        elif name == "gripper_link":
            center, size = _box_from_bounds(
                bounds["active_gripper_r1"]["palm"]["local_surface"]["bounds_gripper_link_m"]
            )
            _add_box(link, size, center)
        robot.append(link)
    for joint in arm_root.findall("joint"):
        robot.append(copy.deepcopy(joint))


def _build_robot(
    inputs: dict[str, Any],
    source_payloads: dict[str, bytes] | None = None,
) -> ET.Element:
    mode = inputs["selected_bus_mass_mode"]
    if mode not in EXPECTED_BY_MODE:
        raise RuntimeError(f"UNKNOWN_BUS_MASS_MODE_FAIL_CLOSED: {mode}")
    components = inputs["components_c01"]
    frames = inputs["frames"]
    robot = ET.Element("robot", {"name": ROBOT_NAME})
    robot.append(
        ET.Comment(
            "Source-static C01 candidate; no Route-C; broad-phase only; no contact, Sim13, production or flight authority"
        )
    )

    bus = ET.SubElement(robot, "link", {"name": "spacecraft_bus"})
    if mode == "AGGREGATE_BUS":
        _add_inertial(bus, components["spacecraft_bus_aggregate"])
        _add_box(bus, components["spacecraft_bus_aggregate"]["broadphase_box_size_m"])
    else:
        _add_inertial(bus, components["bus_equipment_algebraic_residual"])
        structure = ET.SubElement(robot, "link", {"name": "bus_primary_structure_candidate_v1"})
        _add_inertial(structure, components["bus_primary_structure_candidate_v1"])
        _add_box(structure, components["bus_primary_structure_candidate_v1"]["broadphase_box_size_m"])

    for frame_name in ("D_BUS_MATE_PHYSICAL", "M_DYNAMICS_NONPHYSICAL", "D_BUS_M6_PATTERN"):
        ET.SubElement(robot, "link", {"name": frame_name})

    T_S_D = frames["T_S_D_BUS_MATE_PHYSICAL"]
    T_S_M = frames["T_S_M_DYNAMICS_NONPHYSICAL"]
    T_S_P = frames["T_S_D_BUS_M6_PATTERN"]
    T_D_P = frames["T_D_BUS_MATE_PHYSICAL_D_BUS_M6_PATTERN"]
    if T_S_D != T_S_M:
        raise RuntimeError("D_AND_M_NUMERIC_TRANSFORM_DRIFT")
    if max(abs(_matmul(T_S_D, T_D_P)[i][j] - T_S_P[i][j]) for i in range(4) for j in range(4)) > 1.0e-12:
        raise RuntimeError("D_TO_PATTERN_COMPOSITION_DRIFT")

    bridge = ET.SubElement(robot, "link", {"name": "load_bridge_candidate"})
    bridge_component = components["load_bridge_candidate"]
    bridge_com, _ = _to_link_properties(bridge_component, T_S_P)
    _add_inertial(bridge, bridge_component, T_S_P)
    _add_box(bridge, bridge_component["broadphase_box_size_pattern_m"], bridge_com)

    T_S_M3R = frames["T_S_M3R_LOCAL"]
    m3r = ET.SubElement(robot, "link", {"name": "m3r_lumped_link"})
    _add_inertial(m3r, components["m3r_lumped_link"], T_S_M3R)

    for frame_name, component_name in (
        ("T_S_R2_ROOT_L", "solar_r2_left_c01_snapshot"),
        ("T_S_R2_ROOT_R", "solar_r2_right_c01_snapshot"),
    ):
        link = ET.SubElement(robot, "link", {"name": component_name})
        _add_inertial(link, components[component_name], frames[frame_name])
        for leaf_index in range(3):
            center = (0.0, -(leaf_index + 0.5) * 0.200, -leaf_index * 0.003)
            _add_box(link, (0.300, 0.0025, 0.200), center, (math.pi / 2.0, 0.0, 0.0))

    _append_b601_subtree(robot, inputs, source_payloads)

    identity = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
    if mode == "EXPLICIT_STRUCTURE_PLUS_RESIDUAL":
        _add_fixed_joint(
            robot,
            "bus_to_bus_primary_structure_candidate_v1",
            "spacecraft_bus",
            "bus_primary_structure_candidate_v1",
            identity,
        )
    _add_fixed_joint(robot, "bus_to_D_BUS_MATE_PHYSICAL", "spacecraft_bus", "D_BUS_MATE_PHYSICAL", T_S_D)
    _add_fixed_joint(robot, "D_BUS_MATE_PHYSICAL_to_D_BUS_M6_PATTERN", "D_BUS_MATE_PHYSICAL", "D_BUS_M6_PATTERN", T_D_P)
    _add_fixed_joint(robot, "D_BUS_M6_PATTERN_to_load_bridge_candidate", "D_BUS_M6_PATTERN", "load_bridge_candidate", identity)
    _add_fixed_joint(
        robot,
        "load_bridge_candidate_to_m3r_lumped_link",
        "load_bridge_candidate",
        "m3r_lumped_link",
        _matmul(_inverse_transform(T_S_P), T_S_M3R),
    )
    _add_fixed_joint(
        robot,
        "m3r_lumped_link_to_base_link",
        "m3r_lumped_link",
        "base_link",
        _matmul(_inverse_transform(T_S_M3R), frames["T_S_B601_ARM_BASE_PHYSICAL"]),
    )
    _add_fixed_joint(robot, "bus_to_M_DYNAMICS_NONPHYSICAL", "spacecraft_bus", "M_DYNAMICS_NONPHYSICAL", T_S_M)
    _add_fixed_joint(
        robot,
        "bus_to_solar_r2_left_c01_snapshot",
        "spacecraft_bus",
        "solar_r2_left_c01_snapshot",
        frames["T_S_R2_ROOT_L"],
    )
    _add_fixed_joint(
        robot,
        "bus_to_solar_r2_right_c01_snapshot",
        "spacecraft_bus",
        "solar_r2_right_c01_snapshot",
        frames["T_S_R2_ROOT_R"],
    )

    links = robot.findall("link")
    joints = robot.findall("joint")
    expected = EXPECTED_BY_MODE[mode]
    joint_types: dict[str, int] = {}
    for joint in joints:
        joint_types[joint.attrib["type"]] = joint_types.get(joint.attrib["type"], 0) + 1
    physical_links = [link for link in links if link.find("inertial") is not None]
    frame_links = [link for link in links if link.attrib["name"] in FRAME_ONLY_LINKS]
    if len(links) != expected["links"] or len(joints) != expected["joints"]:
        raise RuntimeError(f"TOPOLOGY_DRIFT: links={len(links)} joints={len(joints)}")
    if len(physical_links) != expected["physical_links"] or len(frame_links) != expected["frame_only_links"]:
        raise RuntimeError("PHYSICAL_OR_FRAME_ONLY_LINK_COUNT_DRIFT")
    if any(list(link) for link in frame_links):
        raise RuntimeError("FRAME_ONLY_LINK_HAS_INERTIAL_VISUAL_OR_COLLISION")
    if joint_types != {"fixed": expected["fixed"], "revolute": 6, "prismatic": 2}:
        raise RuntimeError(f"JOINT_TYPE_DRIFT: {joint_types}")
    total_mass = sum(float(link.find("inertial/mass").attrib["value"]) for link in physical_links)
    if abs(total_mass - EXPECTED_TOTAL_MASS_KG) > 1.0e-12:
        raise RuntimeError(f"TOTAL_MASS_DRIFT: {total_mass}")
    return robot


def _runtime_code_sha256() -> str:
    """Fingerprint the loaded function code, not merely the mutable source file."""

    digest = hashlib.sha256()
    for name in sorted(globals()):
        value = globals()[name]
        code = getattr(value, "__code__", None)
        if code is not None and getattr(value, "__module__", None) == __name__:
            digest.update(name.encode("utf-8"))
            digest.update(marshal.dumps(code))
    return digest.hexdigest().upper()


def gen_urdf():
    """Return an in-memory URDF root after fresh V2 authority; never write a file."""

    inputs, input_snapshot_sha256 = _load_inputs_snapshot()
    runtime_code_sha256 = _runtime_code_sha256()
    authority = _require_execution_authority(inputs, input_snapshot_sha256, runtime_code_sha256)
    source_payloads = _verify_source_pins(inputs)
    robot = _build_robot(inputs, source_payloads)
    if (
        _sha256(Path(__file__)) != authority["source_sha256"]
        or _sha256(INPUTS_PATH) != authority["input_sha256"]
        or _runtime_code_sha256() != authority["runtime_code_sha256"]
    ):
        raise RuntimeError("SOURCE_OR_INPUT_CHANGED_DURING_IN_MEMORY_GENERATION_FAIL_CLOSED")
    _verify_source_pins(inputs)
    _release_active_lock(authority["run_id"])
    return robot


if __name__ == "__main__":
    raise SystemExit("Direct execution is forbidden; use gen_urdf() only after V2 authorization.")
