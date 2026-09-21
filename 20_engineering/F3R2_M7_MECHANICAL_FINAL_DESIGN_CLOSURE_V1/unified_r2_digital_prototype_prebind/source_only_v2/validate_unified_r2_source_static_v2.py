#!/usr/bin/env python3
"""Independent source-only validator for the Unified-R2 V2 URDF candidate.

The validator imports the dormant generator only after taking a before-snapshot,
calls the unauthorized public entry point as a negative control, and builds both
mass modes in memory through the private pure builder.  It never writes a URDF.
"""

from __future__ import annotations

import ast
import copy
import csv
import hashlib
import importlib.util
import json
import math
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PARENT = HERE.parent
INPUTS_PATH = HERE / "UNIFIED_R2_URDF_SOURCE_INPUTS_V2.yaml"
CONTRACT_PATH = HERE / "UNIFIED_R2_URDF_SIM_CANDIDATE_CONTRACT_V2.yaml"
FRAME_TREE_PATH = HERE / "UNIFIED_R2_SYSTEM_FRAME_TREE_V2.yaml"
LEDGER_PATH = PARENT / "UNIFIED_R2_URDF_DESIGN_LEDGER_V2.yaml"
SOURCE_PATH = HERE / "unified_r2_urdf_source_v2.py"
VALIDATION_PATH = HERE / "UNIFIED_R2_URDF_SOURCE_STATIC_VALIDATION_V2.json"
GATE_PATH = HERE / "UNIFIED_R2_URDF_SOURCE_GATE_V2.json"
HASH_PATH = HERE / "UNIFIED_R2_URDF_SOURCE_SHA256_V2.csv"
RECEIPT_PATH = HERE / "UNIFIED_R2_URDF_SOURCE_RECEIPT_V2.md"
AUTHORITY_PATH = HERE / "UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2.json"

EXPECTED_TOTAL_MASS_KG = 31.022864807342987
EXPECTED_B601_MASS_KG = 4.695555949342986
EXPECTED_ACTUATED = [
    "joint1",
    "joint2",
    "joint3",
    "joint4",
    "joint5",
    "joint6",
    "gripper_joint1",
    "gripper_joint2",
]
EXPECTED_FRAME_ONLY = {
    "D_BUS_MATE_PHYSICAL",
    "M_DYNAMICS_NONPHYSICAL",
    "D_BUS_M6_PATTERN",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def close(a: float, b: float, tolerance: float = 1.0e-12) -> bool:
    return abs(float(a) - float(b)) <= tolerance


def matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(len(b))) for j in range(len(b[0]))] for i in range(len(a))]


def transpose(a):
    return [list(row) for row in zip(*a)]


def matrix_residual(a, b) -> float:
    return max(abs(float(a[i][j]) - float(b[i][j])) for i in range(len(a)) for j in range(len(a[0])))


def det3(a) -> float:
    return (
        a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
        - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
        + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0])
    )


def parallel_axis(mass: float, displacement):
    d2 = sum(value * value for value in displacement)
    return [
        [mass * (d2 * (1.0 if i == j else 0.0) - displacement[i] * displacement[j]) for j in range(3)]
        for i in range(3)
    ]


def add_matrices(*matrices):
    return [[sum(matrix[i][j] for matrix in matrices) for j in range(3)] for i in range(3)]


def combine_components(components):
    total_mass = sum(float(component["mass_kg"]) for component in components)
    com = [
        sum(float(component["mass_kg"]) * float(component["com_S_m"][axis]) for component in components)
        / total_mass
        for axis in range(3)
    ]
    inertia_terms = []
    for component in components:
        displacement = [float(component["com_S_m"][axis]) - com[axis] for axis in range(3)]
        inertia_terms.append(
            add_matrices(
                component["inertia_about_com_S_kg_m2"],
                parallel_axis(float(component["mass_kg"]), displacement),
            )
        )
    return {"mass_kg": total_mass, "com_S_m": com, "inertia_about_com_S_kg_m2": add_matrices(*inertia_terms)}


def parse_vector(text: str) -> list[float]:
    return [float(value) for value in text.split()]


def numeric_residual(actual, declared) -> float:
    def flatten(value):
        if isinstance(value, (list, tuple)):
            result = []
            for child in value:
                result.extend(flatten(child))
            return result
        return [float(value)]

    actual_flat = flatten(actual)
    declared_flat = flatten(declared)
    if len(actual_flat) != len(declared_flat):
        return math.inf
    return max((abs(a - b) for a, b in zip(actual_flat, declared_flat)), default=0.0)


def cross_file_field_audit(robot, inputs, frame_tree, ledger, contract) -> dict[str, object]:
    """Compare generated in-memory XML against every declared system field.

    The audit is intentionally independent of source formatting.  Signed zero is
    normalized by numeric parsing, while discrepancies larger than the declared
    engineering tolerance fail UR2V2-23.
    """

    rows: list[dict[str, object]] = []

    def exact(entity_type, name, field, source_value, declared_value, declaration):
        passed = source_value == declared_value
        rows.append(
            {
                "entity_type": entity_type,
                "name": name,
                "field": field,
                "source_value": source_value,
                "declared_value": declared_value,
                "declaration": declaration,
                "comparison": "exact",
                "pass": passed,
            }
        )

    def numeric(entity_type, name, field, source_value, declared_value, tolerance, units, declaration):
        residual = numeric_residual(source_value, declared_value)
        rows.append(
            {
                "entity_type": entity_type,
                "name": name,
                "field": field,
                "source_value": source_value,
                "declared_value": declared_value,
                "declaration": declaration,
                "max_abs_residual": residual,
                "tolerance": tolerance,
                "units": units,
                "pass": residual <= tolerance,
            }
        )

    configuration = inputs["configuration"]
    expected_system_configuration = f"{configuration['configuration_id']}_{configuration['canonical_name']}"
    expected_urdf_configuration = f"{expected_system_configuration}_FIXED_SOLAR_SNAPSHOT"
    for declaration, value in (
        ("inputs.system_configuration_id", configuration["system_configuration_id"]),
        ("ledger.robot_metadata.configuration_id", ledger["robot_metadata"]["configuration_id"]),
        ("frame_tree.configuration_id", frame_tree["configuration_id"]),
    ):
        exact("configuration", "C01", "system_configuration_id", expected_system_configuration, value, declaration)
    exact(
        "configuration",
        "C01",
        "urdf_configuration_id",
        expected_urdf_configuration,
        configuration["urdf_configuration_id"],
        "inputs.urdf_configuration_id",
    )
    exact(
        "configuration",
        "C01",
        "urdf_configuration_id",
        expected_urdf_configuration,
        contract["model_contract"]["configuration"],
        "contract.model_contract.configuration",
    )
    for declaration, value in (
        ("ledger.robot_metadata.robot_name", ledger["robot_metadata"]["robot_name"]),
        ("frame_tree.robot_name", frame_tree["robot_name"]),
        ("contract.model_contract.robot_name", contract["model_contract"]["robot_name"]),
    ):
        exact("robot", robot.attrib["name"], "robot_name", robot.attrib["name"], value, declaration)

    actual_joints = {joint.attrib["name"]: joint for joint in robot.findall("joint")}
    limit_keys = {
        "revolute": ("lower_rad", "upper_rad", "effort_model_literal", "velocity_model_literal_rad_s"),
        "prismatic": ("lower_m", "upper_m", "effort_model_literal", "velocity_model_literal_m_s"),
    }
    for declaration, declared_joints in (
        ("frame_tree.joint_tree_selected_mode", frame_tree["joint_tree_selected_mode"]),
        ("ledger.joint_ledger", ledger["joint_ledger"]),
    ):
        exact("joint_set", declaration, "joint_names", sorted(actual_joints), sorted(row["name"] for row in declared_joints), declaration)
        for declared in declared_joints:
            name = declared["name"]
            joint = actual_joints.get(name)
            if joint is None:
                exact("joint", name, "exists", True, False, declaration)
                continue
            exact("joint", name, "type", joint.attrib["type"], declared["type"], declaration)
            exact("joint", name, "parent", joint.find("parent").attrib["link"], declared["parent"], declaration)
            exact("joint", name, "child", joint.find("child").attrib["link"], declared["child"], declaration)
            origin = joint.find("origin")
            numeric("joint", name, "origin_xyz_m", parse_vector(origin.attrib["xyz"]), declared["origin_xyz_m"], 1.0e-12, "m", declaration)
            numeric("joint", name, "origin_rpy_rad", parse_vector(origin.attrib["rpy"]), declared["origin_rpy_rad"], 1.0e-12, "rad", declaration)
            if "axis_joint_frame" in declared:
                axis = joint.find("axis")
                numeric("joint", name, "axis_joint_frame", parse_vector(axis.attrib["xyz"]), declared["axis_joint_frame"], 1.0e-12, "dimensionless", declaration)
            if "limits" in declared:
                limit = joint.find("limit")
                keys = limit_keys[joint.attrib["type"]]
                actual_limits = [float(limit.attrib[key]) for key in ("lower", "upper", "effort", "velocity")]
                declared_limits = [float(declared["limits"][key]) for key in keys]
                numeric("joint", name, "limits", actual_limits, declared_limits, 1.0e-12, "mixed_by_joint_type", declaration)

    actual_links = {link.attrib["name"]: link for link in robot.findall("link")}
    for declared in ledger["inertial_ledger"]:
        name = declared["link"]
        link = actual_links.get(name)
        inertial = None if link is None else link.find("inertial")
        if inertial is None:
            exact("inertial", name, "exists", True, False, "ledger.inertial_ledger")
            continue
        mass_key = "selected_mode_mass_kg" if name == "spacecraft_bus" else "mass_kg"
        com_key = "selected_mode_com_link_m" if name == "spacecraft_bus" else "com_link_m"
        inertia_key = "selected_mode_inertia_about_com_link_kg_m2" if name == "spacecraft_bus" else "inertia_about_com_link_kg_m2"
        inertia_node = inertial.find("inertia").attrib
        actual_inertia = [
            [float(inertia_node["ixx"]), float(inertia_node["ixy"]), float(inertia_node["ixz"])],
            [float(inertia_node["ixy"]), float(inertia_node["iyy"]), float(inertia_node["iyz"])],
            [float(inertia_node["ixz"]), float(inertia_node["iyz"]), float(inertia_node["izz"])],
        ]
        numeric("inertial", name, "mass_kg", float(inertial.find("mass").attrib["value"]), declared[mass_key], 1.0e-12, "kg", "ledger.inertial_ledger")
        numeric("inertial", name, "com_link_m", parse_vector(inertial.find("origin").attrib["xyz"]), declared[com_key], 1.0e-12, "m", "ledger.inertial_ledger")
        numeric("inertial", name, "inertia_about_com_link_kg_m2", actual_inertia, declared[inertia_key], 1.0e-15, "kg*m^2", "ledger.inertial_ledger")

    for declared in ledger["geometry_ledger"]["selected_mode_items"]:
        name = declared["link"]
        link = actual_links.get(name)
        if link is None:
            exact("geometry", name, "link_exists", True, False, "ledger.geometry_ledger")
            continue
        visuals = link.findall("visual")
        collisions = link.findall("collision")
        if declared["geometry_type"] == "none":
            exact("geometry", name, "visual_count", 0, len(visuals), "ledger.geometry_ledger")
            exact("geometry", name, "collision_count", 0, len(collisions), "ledger.geometry_ledger")
            continue
        leaves = declared.get("leaves", [declared])
        exact("geometry", name, "visual_count", len(leaves), len(visuals), "ledger.geometry_ledger")
        exact("geometry", name, "collision_count", len(leaves), len(collisions), "ledger.geometry_ledger")
        for tag, nodes in (("visual", visuals), ("collision", collisions)):
            for index, (leaf, node) in enumerate(zip(leaves, nodes)):
                origin = node.find("origin")
                box = node.find("geometry/box")
                numeric("geometry", name, f"{tag}[{index}].origin_xyz_m", parse_vector(origin.attrib["xyz"]), leaf["origin_xyz_m"], 1.0e-12, "m", "ledger.geometry_ledger")
                numeric("geometry", name, f"{tag}[{index}].origin_rpy_rad", parse_vector(origin.attrib["rpy"]), leaf["origin_rpy_rad"], 1.0e-12, "rad", "ledger.geometry_ledger")
                numeric("geometry", name, f"{tag}[{index}].size_m", parse_vector(box.attrib["size"]), leaf["size_m"], 1.0e-12, "m", "ledger.geometry_ledger")

    for name in sorted(EXPECTED_FRAME_ONLY):
        link = actual_links[name]
        exact("frame_only", name, "child_element_count", 0, len(list(link)), "source_and_frame_contract")

    failed_rows = [
        {key: row[key] for key in ("entity_type", "name", "field", "declaration")}
        for row in rows
        if not row["pass"]
    ]
    return {
        "row_count": len(rows),
        "passed_rows": len(rows) - len(failed_rows),
        "failed_rows": failed_rows,
        "all_passed": not failed_rows,
        "rows": rows,
    }


def directory_file_snapshot() -> dict[str, dict[str, object]]:
    return {
        path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in HERE.iterdir()
        if path.is_file()
    }


def load_source_module():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("unified_r2_urdf_source_static_v2", SOURCE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import V2 generator source")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def dynamic_authority_state_machine_audit(module) -> dict[str, object]:
    """Exercise authorization, override, replay and writer-lock paths in temp only."""

    with tempfile.TemporaryDirectory(prefix="unified_r2_v2_authority_test_") as temp_name:
        temp = Path(temp_name)
        module.HERE = temp
        module.INPUTS_PATH = temp / INPUTS_PATH.name
        module.AUTHORITY_PATH = temp / AUTHORITY_PATH.name
        module.RUN_CONSUMPTION_DIR = temp / ".run_consumption"
        module.OVERRIDE_CONSUMPTION_DIR = temp / ".override_consumption"
        module.ACTIVE_RUN_LOCK_PATH = temp / ".active_run.lock"
        module.INPUTS_PATH.write_bytes(INPUTS_PATH.read_bytes())

        issued = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
        expires = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat().replace("+00:00", "Z")

        def authority(run_id: str, low_memory: bool, override_run_id: str | None = None):
            record = {
                "schema": "UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2",
                "run_id": run_id,
                "issued_utc": issued,
                "expires_utc": expires,
                "selected_bus_mass_mode": "EXPLICIT_STRUCTURE_PLUS_RESIDUAL",
                "source_sha256": sha256(SOURCE_PATH),
                "runtime_code_sha256": module._runtime_code_sha256(),
                "input_sha256": sha256(module.INPUTS_PATH),
                "owner_accepted": True,
                "authority_flags": {
                    "rebase_execution_authorized": True,
                    "unified_r2_v2_generation_authorized": True,
                    "system_urdf_generation_authorized": True,
                    "route_c_exclusion_accepted_for_this_sim_candidate": True,
                    "route_c_cad_authorized": False,
                    "memory_admitted_for_this_execution": True,
                },
            }
            if low_memory:
                record["low_memory_owner_override"] = {
                    "owner_override_id": f"override:{run_id}",
                    "run_id": override_run_id if override_run_id is not None else run_id,
                    "issued_utc": issued,
                    "expires_utc": expires,
                    "risk_ack": "ACCEPT_SINGLE_RUN_LOW_MEMORY_RISK",
                }
            module.AUTHORITY_PATH.write_text(json.dumps(record), encoding="utf-8")

        module._available_memory_gib = lambda: 8.0
        high_run = "UR2V2:HIGH:0001"
        authority(high_run, False)
        high_robot = module.gen_urdf()
        high_success = (
            isinstance(high_robot, ET.Element)
            and not module.ACTIVE_RUN_LOCK_PATH.exists()
            and len(list(module.RUN_CONSUMPTION_DIR.glob("*.json"))) == 1
            and not list(temp.glob("*.urdf"))
        )
        replay_message = None
        try:
            module.gen_urdf()
        except RuntimeError as exc:
            replay_message = str(exc)
        replay_denied = replay_message is not None and "RUN_ID_ALREADY_CONSUMED" in replay_message

        module._available_memory_gib = lambda: 1.0
        low_run = "UR2V2:LOW:0002"
        authority(low_run, True)
        low_robot = module.gen_urdf()
        override_records = list(module.OVERRIDE_CONSUMPTION_DIR.glob("*.json"))
        override_payload = json.loads(override_records[0].read_text(encoding="utf-8")) if override_records else {}
        low_success = (
            isinstance(low_robot, ET.Element)
            and len(override_records) == 1
            and override_payload.get("run_id") == low_run
            and override_payload.get("memory_gate_status") == "OWNER_OVERRIDE_LOW_MEMORY"
            and override_payload.get("memory_gate_passed") is False
            and override_payload.get("execution_authorized") is True
            and not module.ACTIVE_RUN_LOCK_PATH.exists()
        )

        wrong_run = "UR2V2:LOW:0003"
        authority(wrong_run, True, override_run_id="UR2V2:OTHER:9999")
        wrong_override_message = None
        run_count_before_wrong = len(list(module.RUN_CONSUMPTION_DIR.glob("*.json")))
        try:
            module.gen_urdf()
        except RuntimeError as exc:
            wrong_override_message = str(exc)
        wrong_override_denied_before_consumption = (
            wrong_override_message is not None
            and "exact execution run_id" in wrong_override_message
            and len(list(module.RUN_CONSUMPTION_DIR.glob("*.json"))) == run_count_before_wrong
            and not module.ACTIVE_RUN_LOCK_PATH.exists()
        )

        module._available_memory_gib = lambda: 8.0
        lock_run = "UR2V2:LOCK:0004"
        authority(lock_run, False)
        module.ACTIVE_RUN_LOCK_PATH.write_text(
            json.dumps({"schema": "NEGATIVE_CONTROL_EXISTING_LOCK", "run_id": "other-run"}),
            encoding="utf-8",
        )
        lock_message = None
        run_count_before_lock = len(list(module.RUN_CONSUMPTION_DIR.glob("*.json")))
        try:
            module.gen_urdf()
        except RuntimeError as exc:
            lock_message = str(exc)
        lock_denied_before_consumption = (
            lock_message is not None
            and "ACTIVE_WRITER_LOCK_PRESENT" in lock_message
            and len(list(module.RUN_CONSUMPTION_DIR.glob("*.json"))) == run_count_before_lock
        )
        module.ACTIVE_RUN_LOCK_PATH.unlink()

        all_passed = all(
            (
                high_success,
                replay_denied,
                low_success,
                wrong_override_denied_before_consumption,
                lock_denied_before_consumption,
                not list(temp.glob("*.urdf")),
            )
        )
        return {
            "all_passed": all_passed,
            "high_memory_authorized_build": high_success,
            "same_run_replay_denied": replay_denied,
            "replay_message": replay_message,
            "low_memory_override_build": low_success,
            "override_record": {
                key: override_payload.get(key)
                for key in (
                    "schema",
                    "owner_override_id",
                    "run_id",
                    "risk_ack",
                    "memory_gate_status",
                    "memory_gate_passed",
                    "execution_authorized",
                )
            },
            "wrong_run_override_denied_before_consumption": wrong_override_denied_before_consumption,
            "wrong_run_override_message": wrong_override_message,
            "active_lock_denied_before_consumption": lock_denied_before_consumption,
            "active_lock_message": lock_message,
            "urdf_emitted": False,
            "mutable_test_scope": "TEMPORARY_DIRECTORY_ONLY",
        }


def robot_audit(robot: ET.Element) -> dict[str, object]:
    links = robot.findall("link")
    joints = robot.findall("joint")
    link_names = [link.attrib["name"] for link in links]
    joint_names = [joint.attrib["name"] for joint in joints]
    parent_by_child = {}
    children_by_parent = {name: [] for name in link_names}
    joint_types: dict[str, int] = {}
    for joint in joints:
        parent = joint.find("parent").attrib["link"]
        child = joint.find("child").attrib["link"]
        if child in parent_by_child:
            parent_by_child[child] = "DUPLICATE_PARENT"
        else:
            parent_by_child[child] = parent
        children_by_parent.setdefault(parent, []).append(child)
        joint_types[joint.attrib["type"]] = joint_types.get(joint.attrib["type"], 0) + 1
    roots = sorted(set(link_names) - set(parent_by_child))
    visited = set()
    active = set()
    cycle = False

    def visit(node):
        nonlocal cycle
        if node in active:
            cycle = True
            return
        if node in visited:
            return
        active.add(node)
        for child in children_by_parent.get(node, []):
            visit(child)
        active.remove(node)
        visited.add(node)

    for root in roots:
        visit(root)

    physical_links = [link for link in links if link.find("inertial") is not None]
    frame_only_links = [link for link in links if link.attrib["name"] in EXPECTED_FRAME_ONLY]
    total_mass = sum(float(link.find("inertial/mass").attrib["value"]) for link in physical_links)

    def path_from_root(child):
        path = [child]
        current = child
        while current in parent_by_child and parent_by_child[current] != "DUPLICATE_PARENT":
            current = parent_by_child[current]
            path.append(current)
        return list(reversed(path))

    return {
        "robot_name": robot.attrib.get("name"),
        "links": len(links),
        "joints": len(joints),
        "physical_links": len(physical_links),
        "frame_only_links": len(frame_only_links),
        "joint_types": joint_types,
        "actuated_dof": sum(joint.attrib["type"] in {"revolute", "continuous", "prismatic"} for joint in joints),
        "total_mass_kg": total_mass,
        "link_names": link_names,
        "joint_names": joint_names,
        "roots": roots,
        "connected": len(visited) == len(link_names),
        "acyclic": not cycle,
        "unique_parent_per_child": all(parent != "DUPLICATE_PARENT" for parent in parent_by_child.values()),
        "joints_equal_links_minus_one": len(joints) == len(links) - 1,
        "frame_only_pure": all(len(list(link)) == 0 for link in frame_only_links),
        "load_bridge_path": path_from_root("load_bridge_candidate"),
        "b601_path": path_from_root("base_link"),
    }


def b601_audit(accepted: ET.Element, robot: ET.Element) -> dict[str, object]:
    accepted_links = {link.attrib["name"]: link for link in accepted.findall("link")}
    robot_links = {link.attrib["name"]: link for link in robot.findall("link")}
    accepted_joints = {joint.attrib["name"]: joint for joint in accepted.findall("joint")}
    robot_joints = {joint.attrib["name"]: joint for joint in robot.findall("joint")}
    inertials_exact = all(
        name in robot_links
        and ET.tostring(source.find("inertial"), encoding="unicode")
        == ET.tostring(robot_links[name].find("inertial"), encoding="unicode")
        for name, source in accepted_links.items()
    )
    joints_exact = all(
        name in robot_joints
        and ET.tostring(source, encoding="unicode") == ET.tostring(robot_joints[name], encoding="unicode")
        for name, source in accepted_joints.items()
    )
    mass = sum(float(link.find("inertial/mass").attrib["value"]) for link in accepted_links.values())
    types: dict[str, int] = {}
    actuated = []
    for joint in accepted_joints.values():
        joint_type = joint.attrib["type"]
        types[joint_type] = types.get(joint_type, 0) + 1
        if joint_type in {"revolute", "continuous", "prismatic"}:
            actuated.append(joint.attrib["name"])
    gripper_velocities = {
        name: float(joint.find("limit").attrib["velocity"])
        for name, joint in accepted_joints.items()
        if name in {"gripper_joint1", "gripper_joint2"}
    }
    return {
        "links": len(accepted_links),
        "joints": len(accepted_joints),
        "mass_kg": mass,
        "joint_types": types,
        "actuated_joints": actuated,
        "inertials_exact": inertials_exact,
        "joints_exact": joints_exact,
        "gripper_model_velocity_literals_m_s": gripper_velocities,
    }


def source_ast_audit() -> dict[str, object]:
    source_text = SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source_text, filename=str(SOURCE_PATH))
    gen_defs = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "gen_urdf"]
    zero_arg = (
        len(gen_defs) == 1
        and not gen_defs[0].args.args
        and not gen_defs[0].args.kwonlyargs
        and gen_defs[0].args.vararg is None
        and gen_defs[0].args.kwarg is None
    )
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    forbidden = {"FreeCAD", "Part", "build123d", "cadquery", "subprocess", "pybullet", "abaqus"}
    required_tokens = (
        "GENERATION_NOT_AUTHORIZED_PREBIND",
        "SOURCE_PIN_DRIFT_FAIL_CLOSED",
        "UNKNOWN_BUS_MASS_MODE_FAIL_CLOSED",
        "route_c_exclusion_accepted_for_this_sim_candidate",
        "route_c_cad_authorized",
        "RUN_ID_ALREADY_CONSUMED",
        "LOW_MEMORY_OVERRIDE_ALREADY_CONSUMED",
        "OWNER_OVERRIDE_LOW_MEMORY",
        '"memory_gate_passed": False',
        "ACTIVE_WRITER_LOCK_PRESENT",
        "RETAIN_FOR_OWNER_INSPECTION_AND_MANUAL_CLEARANCE",
        "SOURCE_OR_INPUT_CHANGED_DURING_IN_MEMORY_GENERATION_FAIL_CLOSED",
        "runtime_code_sha256",
        "Owner Override must bind the exact execution run_id",
        "source_payloads[\"accepted_b601_urdf\"]",
        "def _build_robot",
    )
    return {
        "gen_urdf_zero_argument": zero_arg,
        "imports": sorted(imported),
        "forbidden_imports_absent": imported.isdisjoint(forbidden),
        "required_fail_closed_tokens_present": all(token in source_text for token in required_tokens),
        "no_urdf_output_path_or_xml_writer": (
            "OUTPUT_URDF_PATH" not in source_text
            and "ET.ElementTree" not in source_text
            and "ElementTree(robot).write" not in source_text
        ),
        "guarded_main_present": 'if __name__ == "__main__"' in source_text,
    }


def check(identifier: str, name: str, passed: bool, evidence) -> dict[str, object]:
    return {"id": identifier, "name": name, "pass": bool(passed), "evidence": evidence}


def main() -> None:
    inputs = yaml.safe_load(INPUTS_PATH.read_text(encoding="utf-8-sig"))
    contract = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8-sig"))
    frame_tree = yaml.safe_load(FRAME_TREE_PATH.read_text(encoding="utf-8-sig"))
    ledger = yaml.safe_load(LEDGER_PATH.read_text(encoding="utf-8-sig"))

    pin_rows = []
    for pin_id, pin in inputs["source_pins"].items():
        path = ROOT / pin["path"]
        actual_hash = sha256(path) if path.is_file() else None
        actual_bytes = path.stat().st_size if path.is_file() else None
        pin_rows.append(
            {
                "id": pin_id,
                "path": pin["path"],
                "expected_bytes": pin["bytes"],
                "actual_bytes": actual_bytes,
                "expected_sha256": pin["sha256"],
                "actual_sha256": actual_hash,
                "pass": actual_bytes == pin["bytes"] and actual_hash == pin["sha256"],
            }
        )

    ast_audit = source_ast_audit()
    before_snapshot = directory_file_snapshot()
    before_dirs = sorted(path.name for path in HERE.iterdir() if path.is_dir())
    module = load_source_module()
    after_import_snapshot = directory_file_snapshot()
    fail_closed_message = None
    try:
        module.gen_urdf()
    except RuntimeError as exc:
        fail_closed_message = str(exc)
    after_negative_snapshot = directory_file_snapshot()
    after_dirs = sorted(path.name for path in HERE.iterdir() if path.is_dir())
    negative_control_clean = (
        fail_closed_message is not None
        and "GENERATION_NOT_AUTHORIZED_PREBIND" in fail_closed_message
        and before_snapshot == after_import_snapshot == after_negative_snapshot
        and before_dirs == after_dirs
    )

    selected_inputs = copy.deepcopy(inputs)
    selected_inputs["selected_bus_mass_mode"] = "EXPLICIT_STRUCTURE_PLUS_RESIDUAL"
    aggregate_inputs = copy.deepcopy(inputs)
    aggregate_inputs["selected_bus_mass_mode"] = "AGGREGATE_BUS"
    selected_robot = module._build_robot(selected_inputs)
    aggregate_robot = module._build_robot(aggregate_inputs)
    selected_audit = robot_audit(selected_robot)
    aggregate_audit = robot_audit(aggregate_robot)
    dynamic_authority_audit = dynamic_authority_state_machine_audit(module)
    field_audit = cross_file_field_audit(selected_robot, inputs, frame_tree, ledger, contract)

    accepted = ET.parse(ROOT / inputs["source_pins"]["accepted_b601_urdf"]["path"]).getroot()
    arm_audit = b601_audit(accepted, selected_robot)

    mode = inputs["selected_bus_mass_mode"]
    selected_mode_count = sum(bool(data["selected"]) for name, data in inputs["mass_modes"].items() if name != "mutual_exclusion_rule" and name != "anti_double_count_rule")
    explicit = inputs["mass_modes"]["EXPLICIT_STRUCTURE_PLUS_RESIDUAL"]
    aggregate = inputs["mass_modes"]["AGGREGATE_BUS"]
    components = inputs["components_c01"]
    recomposed = combine_components(
        [components["bus_primary_structure_candidate_v1"], components["bus_equipment_algebraic_residual"]]
    )
    aggregate_component = components["spacecraft_bus_aggregate"]
    recomposition_errors = {
        "mass_kg": abs(recomposed["mass_kg"] - float(aggregate_component["mass_kg"])),
        "com_m": max(abs(recomposed["com_S_m"][i] - float(aggregate_component["com_S_m"][i])) for i in range(3)),
        "inertia_kg_m2": matrix_residual(
            recomposed["inertia_about_com_S_kg_m2"],
            aggregate_component["inertia_about_com_S_kg_m2"],
        ),
    }

    frame_rows = []
    for name, T in inputs["frames"].items():
        if not name.startswith("T_"):
            continue
        R = [row[:3] for row in T[:3]]
        orthogonality = matrix_residual(matmul(transpose(R), R), [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
        frame_rows.append(
            {
                "name": name,
                "orthogonality_residual": orthogonality,
                "determinant": det3(R),
                "pass": orthogonality <= 1.0e-12 and abs(det3(R) - 1.0) <= 1.0e-12,
            }
        )
    T_D = inputs["frames"]["T_S_D_BUS_MATE_PHYSICAL"]
    T_M = inputs["frames"]["T_S_M_DYNAMICS_NONPHYSICAL"]
    T_P = inputs["frames"]["T_S_D_BUS_M6_PATTERN"]
    T_D_P = inputs["frames"]["T_D_BUS_MATE_PHYSICAL_D_BUS_M6_PATTERN"]
    pattern_composition_residual = matrix_residual(matmul(T_D, T_D_P), T_P)

    structure_gate = json.loads((ROOT / inputs["source_pins"]["bus_structure_source_gate"]["path"]).read_text(encoding="utf-8"))
    structure_validation = json.loads((ROOT / inputs["source_pins"]["bus_structure_static_validation"]["path"]).read_text(encoding="utf-8"))
    frontier = json.loads((ROOT / inputs["source_pins"]["effective_frontier_v2"]["path"]).read_text(encoding="utf-8"))
    prb17 = next(row for row in frontier["effective_criteria"] if row["id"] == "PRB-17")
    sim13_loader_text = (ROOT / inputs["source_pins"]["sim13_mechanical_asset_loader_v1"]["path"]).read_text(encoding="utf-8")
    sim13_pin_rows = [row for row in pin_rows if row["id"].startswith("sim13_")]

    selected_expected = explicit["topology_counts"]
    aggregate_expected = aggregate["topology_counts"]
    common_static_absent = (
        not AUTHORITY_PATH.exists()
        and not list(HERE.glob("*.urdf"))
        and not (HERE / ".unified_r2_v2_run_consumption").exists()
        and not (HERE / ".unified_r2_v2_override_consumption").exists()
        and not (HERE / ".unified_r2_v2_active_run.lock").exists()
    )
    all_flags_false = all(value is False for value in inputs["authority_flags"].values()) and all(
        value is False for value in contract["authority_flags"].values()
    )

    checks = [
        check("UR2V2-01", "all five source-only design artifacts exist", all(path.is_file() for path in (INPUTS_PATH, CONTRACT_PATH, FRAME_TREE_PATH, LEDGER_PATH, SOURCE_PATH)), [str(path.relative_to(ROOT)).replace("\\", "/") for path in (INPUTS_PATH, CONTRACT_PATH, FRAME_TREE_PATH, LEDGER_PATH, SOURCE_PATH)]),
        check("UR2V2-02", "all 20 external source pins match path bytes and SHA-256", len(pin_rows) == 20 and all(row["pass"] for row in pin_rows), pin_rows),
        check("UR2V2-03", "bus structure source package is current 16/16 and 18/18 while PRB-17 remains HOLD", structure_gate["score"] == {"passed": 16, "total": 16} and structure_gate["all_checks_passed"] is True and structure_validation["score"] == {"passed": 18, "total": 18} and structure_validation["all_checks_passed"] is True and prb17["state"] == "HOLD" and prb17["pass"] is False and frontier["effective_summary"] == {"criteria_total": 20, "pass": 6, "hold": 14}, {"source_gate": structure_gate["score"], "static_validation": structure_validation["score"], "effective_summary": frontier["effective_summary"], "PRB17": {"state": prb17["state"], "pass": prb17["pass"]}}),
        check("UR2V2-04", "source has zero-argument generator and no CAD solver subprocess or URDF file writer", all(bool(value) for key, value in ast_audit.items() if key not in {"imports"}) and ast_audit["forbidden_imports_absent"], ast_audit),
        check("UR2V2-05", "import and unauthorized gen_urdf are side-effect free and fail closed", negative_control_clean, {"message": fail_closed_message, "before_files": len(before_snapshot), "after_files": len(after_negative_snapshot), "directories": after_dirs}),
        check("UR2V2-06", "no URDF authority run marker override marker or writer lock exists", common_static_absent, {"authority_present": AUTHORITY_PATH.exists(), "urdf_files": [path.name for path in HERE.glob("*.urdf")], "directories": after_dirs}),
        check("UR2V2-07", "selected bus mode is single-valued explicit structure plus residual", mode == "EXPLICIT_STRUCTURE_PLUS_RESIDUAL" and selected_mode_count == 1 and explicit["selected"] is True and aggregate["selected"] is False and set(explicit["bus_components"]) == {"bus_primary_structure_candidate_v1", "bus_equipment_algebraic_residual"} and explicit["prohibited_bus_components"] == ["spacecraft_bus_aggregate"], {"selected_bus_mass_mode": mode, "selected_mode_count": selected_mode_count}),
        check("UR2V2-08", "aggregate mode in-memory topology is exact", (aggregate_audit["links"], aggregate_audit["physical_links"], aggregate_audit["frame_only_links"], aggregate_audit["joints"], aggregate_audit["joint_types"], aggregate_audit["actuated_dof"]) == (aggregate_expected["total_links"], aggregate_expected["physical_links"], aggregate_expected["frame_only_links"], aggregate_expected["joints"], {"fixed": aggregate_expected["fixed_joints"], "revolute": 6, "prismatic": 2}, 8), aggregate_audit),
        check("UR2V2-09", "selected explicit mode in-memory topology is exact", (selected_audit["links"], selected_audit["physical_links"], selected_audit["frame_only_links"], selected_audit["joints"], selected_audit["joint_types"], selected_audit["actuated_dof"]) == (selected_expected["total_links"], selected_expected["physical_links"], selected_expected["frame_only_links"], selected_expected["joints"], {"fixed": selected_expected["fixed_joints"], "revolute": 6, "prismatic": 2}, 8), selected_audit),
        check("UR2V2-10", "both mode graphs are connected acyclic one-root trees", all(audit["roots"] == ["spacecraft_bus"] and audit["connected"] and audit["acyclic"] and audit["unique_parent_per_child"] and audit["joints_equal_links_minus_one"] for audit in (selected_audit, aggregate_audit)), {"selected": {key: selected_audit[key] for key in ("roots", "connected", "acyclic", "unique_parent_per_child", "joints_equal_links_minus_one")}, "aggregate": {key: aggregate_audit[key] for key in ("roots", "connected", "acyclic", "unique_parent_per_child", "joints_equal_links_minus_one")}}),
        check("UR2V2-11", "all three distinct frame-only links omit inertial visual and collision", selected_audit["frame_only_pure"] and aggregate_audit["frame_only_pure"] and EXPECTED_FRAME_ONLY.issubset(set(selected_audit["link_names"])), {"frame_only_links": sorted(EXPECTED_FRAME_ONLY), "selected_pure": selected_audit["frame_only_pure"], "aggregate_pure": aggregate_audit["frame_only_pure"]}),
        check("UR2V2-12", "D and M are numerically coincident but semantically distinct and Pattern composes through D", T_D == T_M and pattern_composition_residual <= 1.0e-12 and all(row["pass"] for row in frame_rows) and len({"D_BUS_MATE_PHYSICAL", "M_DYNAMICS_NONPHYSICAL", "D_BUS_M6_PATTERN"}) == 3 and "same numeric transform" in inputs["frames"]["semantic_non_alias_rule"] and "distinct identifiers" in inputs["frames"]["semantic_non_alias_rule"], {"D_equals_M": T_D == T_M, "pattern_composition_residual": pattern_composition_residual, "frames": frame_rows}),
        check("UR2V2-13", "physical bridge and B601 path traverses D then Pattern and never M", selected_audit["load_bridge_path"] == ["spacecraft_bus", "D_BUS_MATE_PHYSICAL", "D_BUS_M6_PATTERN", "load_bridge_candidate"] and selected_audit["b601_path"][:6] == ["spacecraft_bus", "D_BUS_MATE_PHYSICAL", "D_BUS_M6_PATTERN", "load_bridge_candidate", "m3r_lumped_link", "base_link"] and "M_DYNAMICS_NONPHYSICAL" not in selected_audit["b601_path"], {"bridge_path": selected_audit["load_bridge_path"], "B601_path": selected_audit["b601_path"]}),
        check("UR2V2-14", "explicit structure and residual recompose aggregate bus mass COM and full inertia", max(recomposition_errors.values()) <= 1.0e-12 and close(recomposed["mass_kg"], 23.3032134) and close(float(components["bus_primary_structure_candidate_v1"]["standard_uncertainty_kg"]), 0.9052470911473921) and close(float(components["bus_primary_structure_candidate_v1"]["local_sensitivity_diagnostic_standard_uncertainty_kg"]), 0.05647800480105046) and components["bus_equipment_algebraic_residual"]["standard_uncertainty_kg"] is None, {"recomposed": recomposed, "errors": recomposition_errors}),
        check("UR2V2-15", "both modes preserve exact target-free service-system mass", close(selected_audit["total_mass_kg"], EXPECTED_TOTAL_MASS_KG) and close(aggregate_audit["total_mass_kg"], EXPECTED_TOTAL_MASS_KG) and close(float(components["total_mass_kg"]), EXPECTED_TOTAL_MASS_KG), {"selected_kg": selected_audit["total_mass_kg"], "aggregate_kg": aggregate_audit["total_mass_kg"], "declared_kg": components["total_mass_kg"]}),
        check("UR2V2-16", "bus anti-double-count boundary excludes bridge target and legacy flange", close(float(components["load_bridge_candidate"]["mass_kg"]), 0.702195458) and "outside" in components["load_bridge_candidate"]["mass_budget_rule"] and close(float(components["excluded_mass_items"]["legacy_flange_mass_kg"]), 0.376019184652) and "never add" in components["excluded_mass_items"]["legacy_flange_rule"] and "not part" in components["excluded_mass_items"]["target_satellite_or_debris"], components["excluded_mass_items"]),
        check("UR2V2-17", "accepted B601 10-link 9-joint mass inertial and joint subtree is exact", arm_audit["links"] == 10 and arm_audit["joints"] == 9 and close(float(arm_audit["mass_kg"]), EXPECTED_B601_MASS_KG, 1.0e-15) and arm_audit["joint_types"] == {"revolute": 6, "fixed": 1, "prismatic": 2} and arm_audit["inertials_exact"] and arm_audit["joints_exact"], arm_audit),
        check("UR2V2-18", "B601 actuation set and model-only gripper velocity remain bounded", arm_audit["actuated_joints"] == EXPECTED_ACTUATED and arm_audit["gripper_model_velocity_literals_m_s"] == {"gripper_joint1": 15.0, "gripper_joint2": 15.0} and inputs["physical_capability_holds"]["physical_gripper_speed_m_s"] is None and inputs["physical_capability_holds"]["physical_gripper_timing_s"] is None and inputs["physical_capability_holds"]["physical_contact_capability"] is None, {"actuated": arm_audit["actuated_joints"], "velocity_literals": arm_audit["gripper_model_velocity_literals_m_s"], "physical_holds": inputs["physical_capability_holds"]}),
        check("UR2V2-19", "collision content is broad-phase only with residual M3R fingers target and Route-C excluded", inputs["collision_policy"]["class"] == "PRIMITIVE_BROADPHASE_ONLY" and inputs["collision_policy"]["contact_authority"] is False and inputs["components_c01"]["bus_equipment_algebraic_residual"]["collision"] is None and all(name in inputs["collision_policy"]["excluded"] for name in ("Route-C", "narrowphase_contact", "target_satellite", "target_debris")), inputs["collision_policy"]),
        check("UR2V2-20", "Solar R2 remains two fixed deployed snapshots without continuous-deployment claim", inputs["configuration"]["continuous_solar_deployment_claimed"] is False and inputs["physical_capability_holds"]["solar_continuous_deployment_model"] is None and close(float(components["solar_r2_left_c01_snapshot"]["mass_kg"]), 0.78) and close(float(components["solar_r2_right_c01_snapshot"]["mass_kg"]), 0.78), {"left_kg": components["solar_r2_left_c01_snapshot"]["mass_kg"], "right_kg": components["solar_r2_right_c01_snapshot"]["mass_kg"]}),
        check("UR2V2-21", "Sim13 V1 remains hash-pinned incompatible and unmodified", len(sim13_pin_rows) == 6 and all(row["pass"] for row in sim13_pin_rows) and "MECH_RL_INTERFACE_V1" in sim13_loader_text and inputs["sim13_boundary"]["v1_in_place_mutation_authorized"] is False and inputs["sim13_boundary"]["current_loader_compatible"] is False and contract["sim13_contract"]["sim13_rebind_authorized"] is False, {"pins": sim13_pin_rows, "boundary": inputs["sim13_boundary"], "contract": contract["sim13_contract"]}),
        check("UR2V2-22", "Route-C exclusion is unaccepted and every execution Owner contact rebind flight and release flag is false", all_flags_false and contract["maximum_current_verdict"] == "PASS_SOURCE_STATIC_ONLY" and contract["authorization_join"]["current_state"] == "DENY" and contract["authorization_join"]["route_c_policy"]["route_c_exclusion_accepted_for_this_sim_candidate"] is False and contract["authorization_join"]["route_c_policy"]["route_c_cad_authorization_required_for_this_excluding_candidate"] is False, {"input_flags": inputs["authority_flags"], "contract_flags": contract["authority_flags"], "maximum_current_verdict": contract["maximum_current_verdict"]}),
        check("UR2V2-23", "generated XML fields agree with inputs frame tree design ledger and contract", field_audit["all_passed"] and ledger["robot_metadata"]["selected_mass_mode"] == frame_tree["selected_mass_mode"] == inputs["selected_bus_mass_mode"] and frame_tree["mode_topology"]["EXPLICIT_STRUCTURE_PLUS_RESIDUAL"]["total_links"] == 19 and frame_tree["mode_topology"]["EXPLICIT_STRUCTURE_PLUS_RESIDUAL"]["joints"] == 18 and ledger["authority_boundary"]["urdf_emitted"] is False and frame_tree["source_only_boundary"]["urdf_emitted"] is False, field_audit),
        check("UR2V2-24", "authorized high-memory low-memory override replay and active-lock state machine passes in temp isolation", dynamic_authority_audit["all_passed"] is True, dynamic_authority_audit),
    ]

    failed = [row["id"] for row in checks if not row["pass"]]
    validation = {
        "schema": "UNIFIED_R2_URDF_SOURCE_STATIC_VALIDATION_V2",
        "generated_date_local": "2026-08-24",
        "mode": "source-only",
        "checks": checks,
        "summary": {"pass": len(checks) - len(failed), "total": len(checks), "failed": failed},
        "verdict": (
            "PASS_SOURCE_STATIC_ONLY__NO_URDF_NO_SIM13_REBIND_NO_EXECUTION_OR_RELEASE_AUTHORITY"
            if not failed
            else "HOLD_SOURCE_STATIC_VALIDATION_DEFECT"
        ),
        "source_pin_audit": pin_rows,
        "selected_mode_robot_audit": selected_audit,
        "aggregate_mode_robot_audit": aggregate_audit,
        "bus_recomposition_errors": recomposition_errors,
        "cross_file_field_audit": field_audit,
        "dynamic_authority_state_machine_audit": dynamic_authority_audit,
        "unauthorized_negative_control": {
            "message": fail_closed_message,
            "no_file_or_directory_delta": negative_control_clean,
            "urdf_emitted": False,
        },
        "review_status": "PENDING_OWNER_REVIEW",
        "owner_accepted": False,
        "sim13_rebind_authorized": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    VALIDATION_PATH.write_text(json.dumps(validation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    gate = {
        "schema": "UNIFIED_R2_URDF_SOURCE_GATE_V2",
        "generated_date_local": "2026-08-24",
        "package_validation": "PASS" if not failed else "HOLD",
        "technical_outcome": "PASS_SOURCE_STATIC_ONLY" if not failed else "HOLD_SOURCE_STATIC_VALIDATION_DEFECT",
        "static_validation": validation["summary"],
        "selected_bus_mass_mode": inputs["selected_bus_mass_mode"],
        "total_mass_kg": EXPECTED_TOTAL_MASS_KG,
        "urdf_emitted": False,
        "sim13_rebind_authorized": False,
        "route_c_exclusion_accepted_for_this_sim_candidate": False,
        "physical_contact_ready": False,
        "production_dynamics_ready": False,
        "flight_qualified": False,
        "review_status": "PENDING_OWNER_REVIEW",
        "owner_accepted": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "technical_verdict": "V2_SOURCE_TREE_MASS_AND_FRAME_CONTRACT_STATICALLY_CLOSED__URDF_EXECUTION_SIM13_CONTACT_AND_RELEASE_HOLD",
    }
    GATE_PATH.write_text(json.dumps(gate, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    RECEIPT_PATH.write_text(
        "# Unified R2 V2 URDF 源级数字样机回执\n\n"
        f"- 静态检查：`{validation['summary']['pass']}/{validation['summary']['total']}`；裁决仅为 `PASS_SOURCE_STATIC_ONLY`。\n"
        "- 选定模式：`EXPLICIT_STRUCTURE_PLUS_RESIDUAL`，19 links / 18 joints / 8 DOF；对照 aggregate 模式为 18 / 17 / 8。\n"
        "- 显式主结构与代数余量精确重组既有 bus lump；两模式整星质量均为 `31.022864807342987 kg`。\n"
        "- `D_BUS_MATE_PHYSICAL`、`M_DYNAMICS_NONPHYSICAL` 与 `D_BUS_M6_PATTERN` 是三个独立 frame-only links；物理路径经 D→Pattern，不经 M。\n"
        "- B601 接受版 10-link/9-joint 惯量与关节字段保持；`15 m/s` 仍只是 URDF 模型字面量。\n"
        "- 公共 `gen_urdf()` 未授权调用按预期 fail-closed；本目录没有 `.urdf`，没有修改 Sim13 V1。\n"
        "- 当前仍需 Owner 接受、Route-C 排除接受、版本化 Sim13 loader/runtime harness、接触后端及后续动力学 Gate。\n",
        encoding="utf-8",
    )

    hash_paths = [
        INPUTS_PATH,
        CONTRACT_PATH,
        FRAME_TREE_PATH,
        LEDGER_PATH,
        SOURCE_PATH,
        Path(__file__),
        VALIDATION_PATH,
        GATE_PATH,
        RECEIPT_PATH,
    ]
    with HASH_PATH.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["class", "path", "bytes", "sha256"])
        for path in hash_paths:
            writer.writerow(
                [
                    "UNIFIED_R2_V2_SOURCE_ONLY",
                    str(path.relative_to(ROOT)).replace("\\", "/"),
                    path.stat().st_size,
                    sha256(path),
                ]
            )

    print(
        json.dumps(
            {
                "verdict": validation["verdict"],
                "score": validation["summary"],
                "urdf_emitted": False,
                "sim13_rebind_authorized": False,
            },
            sort_keys=True,
        )
    )
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
