"""Independent reconstruction of admissible M7 mechanical evidence claims."""

from __future__ import annotations

import math
from pathlib import PurePosixPath
from typing import Any, Mapping
import xml.etree.ElementTree as ET

from .strict_io import AdmissionError, EvidenceSnapshot, load_default_snapshot, thaw


STATUS_ENUM = (
    "BOUND_DIGITAL",
    "DESIGN_CANDIDATE",
    "DIAGNOSTIC_ONLY",
    "OWNER_REQUIRED",
    "TEST_REQUIRED",
    "ABSENT",
)
GATE_CEILING = "PASS_M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_SOURCE_FREEZE_ONLY"
MANDATORY_FALSE = (
    "system_urdf_available",
    "current_system_bound",
    "physical_contact_ready",
    "dynamics_capture_entry_authorized",
    "next_stage_authorized",
)
B601_LINKS = (
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
)
B601_JOINTS = (
    "joint1",
    "joint2",
    "joint3",
    "joint4",
    "joint5",
    "joint6",
    "gripper_joint",
    "gripper_joint1",
    "gripper_joint2",
)
ACTUATED_JOINTS = (
    "joint1",
    "joint2",
    "joint3",
    "joint4",
    "joint5",
    "joint6",
    "gripper_joint1",
    "gripper_joint2",
)
PHYSICAL_PATH = (
    "spacecraft_bus",
    "D_BUS_MATE_PHYSICAL",
    "D_BUS_M6_PATTERN",
    "load_bridge_candidate",
    "m3r_lumped_link",
    "base_link",
)


def _doc(snapshot: EvidenceSnapshot, artifact_id: str) -> Mapping[str, Any]:
    parsed = snapshot.artifacts[artifact_id].parsed
    if not isinstance(parsed, Mapping):
        raise AdmissionError(f"{artifact_id} has no structured document")
    return parsed


def _close(a: Any, b: float, tolerance: float = 1e-12) -> bool:
    return (
        not isinstance(a, bool)
        and isinstance(a, (int, float))
        and math.isfinite(float(a))
        and abs(float(a) - b) <= tolerance
    )


def _quantity(
    value: int | float,
    unit: str,
    coordinate_frame: str,
    reference_point: str,
    authority: str,
    status: str,
    source_artifact: str,
    source_field: str,
) -> dict[str, Any]:
    if status not in STATUS_ENUM:
        raise AdmissionError(f"invalid evidence status: {status}")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise AdmissionError("quantity value must be a finite number, not bool")
    for label in (unit, coordinate_frame, reference_point, authority, source_artifact, source_field):
        if not isinstance(label, str) or not label:
            raise AdmissionError("quantity metadata must be non-empty strings")
    return {
        "value": value,
        "unit": unit,
        "coordinate_frame": coordinate_frame,
        "reference_point": reference_point,
        "authority": authority,
        "status": status,
        "source_artifact": source_artifact,
        "source_field": source_field,
    }


def _record(checks: dict[str, bool], name: str, observation: Any) -> None:
    checks[name] = observation is True


def _parse_urdf(payload: bytes) -> dict[str, Any]:
    root = ET.fromstring(payload)
    links = [element.attrib.get("name") for element in root.findall("link")]
    joints: list[dict[str, Any]] = []
    for element in root.findall("joint"):
        axis = element.find("axis")
        limit = element.find("limit")
        origin = element.find("origin")
        parent = element.find("parent")
        child = element.find("child")
        joints.append(
            {
                "name": element.attrib.get("name"),
                "type": element.attrib.get("type"),
                "parent": None if parent is None else parent.attrib.get("link"),
                "child": None if child is None else child.attrib.get("link"),
                "axis": None if axis is None else tuple(float(x) for x in axis.attrib["xyz"].split()),
                "origin_xyz": tuple(float(x) for x in ("0 0 0" if origin is None else origin.attrib.get("xyz", "0 0 0")).split()),
                "origin_rpy": tuple(float(x) for x in ("0 0 0" if origin is None else origin.attrib.get("rpy", "0 0 0")).split()),
                "lower": None if limit is None or "lower" not in limit.attrib else float(limit.attrib["lower"]),
                "upper": None if limit is None or "upper" not in limit.attrib else float(limit.attrib["upper"]),
                "velocity": None if limit is None or "velocity" not in limit.attrib else float(limit.attrib["velocity"]),
            }
        )
    masses: list[float] = []
    mesh_names: list[str] = []
    for link in root.findall("link"):
        mass = link.find("./inertial/mass")
        if mass is None or "value" not in mass.attrib:
            raise AdmissionError(f"URDF link lacks inertial mass: {link.attrib.get('name')}")
        masses.append(float(mass.attrib["value"]))
        for mesh in link.findall("./visual/geometry/mesh") + link.findall("./collision/geometry/mesh"):
            mesh_names.append(mesh.attrib.get("filename", ""))
    return {"links": links, "joints": joints, "masses": masses, "mesh_names": mesh_names}


def _evaluate_topology(snapshot: EvidenceSnapshot, checks: dict[str, bool], quantities: dict[str, Any]) -> dict[str, Any]:
    frame = _doc(snapshot, "frame_tree")
    boundary = _doc(snapshot, "rebind_boundary")
    selected = frame.get("mode_topology", {}).get("EXPLICIT_STRUCTURE_PLUS_RESIDUAL", {})
    expected = {
        "total_links": 19,
        "physical_links": 16,
        "frame_only_links": 3,
        "joints": 18,
        "actuated_dof": 8,
    }
    for field, value in expected.items():
        _record(checks, f"topology_{field}_exact", selected.get(field) == value)
        quantities[field] = _quantity(
            value,
            "count",
            "NOT_APPLICABLE",
            "NOT_APPLICABLE",
            "UNIFIED_R2_SYSTEM_FRAME_TREE_V2",
            "BOUND_DIGITAL",
            "frame_tree",
            f"mode_topology.EXPLICIT_STRUCTURE_PLUS_RESIDUAL.{field}",
        )
    type_counts = selected.get("joint_type_counts", {})
    _record(checks, "topology_fixed_10", type_counts.get("fixed") == 10)
    _record(checks, "topology_revolute_6", type_counts.get("revolute") == 6)
    _record(checks, "topology_prismatic_2", type_counts.get("prismatic") == 2)
    links = frame.get("link_tree_selected_mode", ())
    joints = frame.get("joint_tree_selected_mode", ())
    _record(checks, "selected_link_tree_length_19", len(links) == 19)
    _record(checks, "selected_joint_tree_length_18", len(joints) == 18)
    b601_link_names = tuple(item.get("link") for item in links if "B601" in str(item.get("role")))
    b601_joint_names = tuple(item.get("name") for item in joints if item.get("name") in B601_JOINTS)
    _record(checks, "b601_link_subtree_exact_10", b601_link_names == B601_LINKS)
    _record(checks, "b601_joint_subtree_exact_9_ordered", b601_joint_names == B601_JOINTS)
    common = frame.get("mode_topology", {}).get("common_b601_subtree", {})
    _record(
        checks,
        "b601_common_counts_10_9_1_6_2_8",
        tuple(common.get(k) for k in ("links", "joints", "fixed", "revolute", "prismatic", "actuated_dof"))
        == (10, 9, 1, 6, 2, 8),
    )
    frame_only = frame.get("frame_only_contract", {})
    _record(
        checks,
        "frame_only_identities_exact",
        tuple(frame_only.get("links", ()))
        == ("D_BUS_MATE_PHYSICAL", "M_DYNAMICS_NONPHYSICAL", "D_BUS_M6_PATTERN"),
    )
    absolute = frame.get("canonical_absolute_frames_in_spacecraft_bus_S", {})
    d_frame = absolute.get("D_BUS_MATE_PHYSICAL", {})
    m_frame = absolute.get("M_DYNAMICS_NONPHYSICAL", {})
    _record(checks, "D_M_numeric_transforms_equal", d_frame.get("T_S_frame") == m_frame.get("T_S_frame"))
    _record(
        checks,
        "D_M_semantic_identities_distinct",
        d_frame.get("role") == "physical mating datum"
        and m_frame.get("role") == "nonphysical dynamics reference only"
        and m_frame.get("semantic_alias_permitted") is False
        and frame_only.get("D_and_M_semantic_relation") == "DISTINCT_IMMUTABLE_IDENTITIES__NEVER_ALIASES",
    )
    boundary_path = tuple(boundary.get("frame_and_load_path_contract", {}).get("physical_path", ()))
    _record(checks, "physical_load_path_exact_and_excludes_M", boundary_path == PHYSICAL_PATH and "M_DYNAMICS_NONPHYSICAL" not in boundary_path)
    return {"frame": frame, "boundary": boundary, "tree_joints": joints}


def _evaluate_urdf(
    snapshot: EvidenceSnapshot,
    frame: Mapping[str, Any],
    tree_joints: Any,
    checks: dict[str, bool],
    quantities: dict[str, Any],
) -> dict[str, Any]:
    urdf = _parse_urdf(snapshot.artifacts["b601_urdf"].payload)
    _record(checks, "accepted_urdf_links_exact_10", tuple(urdf["links"]) == B601_LINKS)
    _record(checks, "accepted_urdf_joints_exact_9_ordered", tuple(j["name"] for j in urdf["joints"]) == B601_JOINTS)
    counts = {kind: sum(j["type"] == kind for j in urdf["joints"]) for kind in ("fixed", "revolute", "prismatic")}
    _record(checks, "accepted_urdf_joint_types_1_6_2", counts == {"fixed": 1, "revolute": 6, "prismatic": 2})
    movable = tuple(j["name"] for j in urdf["joints"] if j["type"] != "fixed")
    _record(checks, "accepted_urdf_actuated_order_exact_8", movable == ACTUATED_JOINTS)
    frame_joint_map = {item.get("name"): item for item in tree_joints if item.get("name") in B601_JOINTS}
    fields_match = True
    for joint in urdf["joints"]:
        ledger = frame_joint_map.get(joint["name"], {})
        fields_match &= joint["type"] == ledger.get("type")
        fields_match &= joint["parent"] == ledger.get("parent") and joint["child"] == ledger.get("child")
        fields_match &= all(_close(a, float(b), 1e-12) for a, b in zip(joint["origin_xyz"], ledger.get("origin_xyz_m", ())))
        fields_match &= all(_close(a, float(b), 1e-12) for a, b in zip(joint["origin_rpy"], ledger.get("origin_rpy_rad", ())))
        if joint["type"] != "fixed":
            fields_match &= all(_close(a, float(b), 1e-12) for a, b in zip(joint["axis"], ledger.get("axis_joint_frame", ())))
            limits = ledger.get("limits", {})
            lower_key, upper_key = ("lower_rad", "upper_rad") if joint["type"] == "revolute" else ("lower_m", "upper_m")
            fields_match &= _close(joint["lower"], float(limits.get(lower_key)), 1e-12)
            fields_match &= _close(joint["upper"], float(limits.get(upper_key)), 1e-12)
    _record(checks, "accepted_urdf_exact_fields_match_frame_tree", bool(fields_match))
    _record(checks, "joint_units_SI_rad_m_s", frame.get("units") == {"length": "m", "angle": "rad", "mass": "kg", "inertia": "kg*m^2"})
    mass = sum(urdf["masses"])
    _record(checks, "accepted_b601_mass_exact", _close(mass, 4.695555949342986))
    quantities["accepted_b601_subtree_mass"] = _quantity(
        mass,
        "kg",
        "B601_LINK_LOCAL_FRAMES",
        "PER_LINK_CENTERS_OF_MASS",
        "ACCEPTED_B601_URDF_DIGITAL_INERTIAL_MODEL",
        "BOUND_DIGITAL",
        "b601_urdf",
        "robot.link[*].inertial.mass.value",
    )
    unique_meshes = tuple(sorted(set(urdf["mesh_names"])))
    expected_meshes = tuple(sorted(f"meshes_b601_gripper/{name}.STL" for name in B601_LINKS))
    _record(checks, "accepted_urdf_unique_mesh_references_exact_10", unique_meshes == expected_meshes)
    mesh_artifacts = [artifact for key, artifact in snapshot.artifacts.items() if key.startswith("mesh_")]
    declared_paths = {
        f"meshes_b601_gripper/{PurePosixPath(artifact.relative_path).name}" for artifact in mesh_artifacts
    }
    _record(
        checks,
        "urdf_mesh_bytes_hash_bound_and_nonempty",
        len(mesh_artifacts) == 10
        and declared_paths == set(expected_meshes)
        and all(artifact.byte_count >= 84 and artifact.read_count == 1 for artifact in mesh_artifacts),
    )
    return urdf


def _evaluate_mass(
    boundary: Mapping[str, Any],
    mass_model: Mapping[str, Any],
    checks: dict[str, bool],
    quantities: dict[str, Any],
) -> None:
    selected = boundary.get("selected_system_contract", {})
    separation = selected.get("mass_authority_separation", {})
    residual = separation.get("residual_bus_mass_kg")
    explicit = separation.get("explicit_structure_mass_kg")
    recomposed = separation.get("recomposed_bus_mass_kg")
    prohibited = separation.get("prohibited_double_count_total_kg")
    total = selected.get("total_mass_kg")
    configs = mass_model.get("configurations", ())
    c01 = next((item for item in configs if item.get("configuration_id") == "C01"), None)
    _record(checks, "mass_model_has_9_configurations", len(configs) == 9)
    _record(checks, "C01_mass_matches_boundary", c01 is not None and _close(c01.get("mass", {}).get("value_kg"), 31.022864807342987) and _close(total, 31.022864807342987))
    _record(checks, "bus_mass_recomposes_without_double_count", _close(float(residual) + float(explicit), float(recomposed)) and _close(recomposed, 23.3032134))
    _record(checks, "prohibited_double_count_is_not_selected_total", _close(prohibited, 37.05784541499227) and not _close(total, float(prohibited)))
    quantities["whole_system_design_mass"] = _quantity(
        float(total),
        "kg",
        "S",
        "SYSTEM_COMPOSITION",
        "SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2__DESIGN_MODEL_NOT_AS_BUILT",
        "DESIGN_CANDIDATE",
        "mass_model",
        "configurations[C01].mass.value_kg",
    )
    quantities["residual_bus_mass"] = _quantity(float(residual), "kg", "S", "SPACECRAFT_BUS_RESIDUAL", "SIM13_VERSIONED_REBIND_BOUNDARY_V2", "DESIGN_CANDIDATE", "rebind_boundary", "selected_system_contract.mass_authority_separation.residual_bus_mass_kg")
    quantities["explicit_structure_mass"] = _quantity(float(explicit), "kg", "S", "BUS_PRIMARY_STRUCTURE", "SIM13_VERSIONED_REBIND_BOUNDARY_V2", "DESIGN_CANDIDATE", "rebind_boundary", "selected_system_contract.mass_authority_separation.explicit_structure_mass_kg")


def _all_null_physical_contact(contact: Mapping[str, Any]) -> bool:
    normal = contact.get("normal_contact", {})
    tangential = contact.get("tangential_contact", {})
    actuator = contact.get("gripper_actuator", {})
    estimates = [entry.get("estimate") for entry in normal.values() if isinstance(entry, Mapping)]
    estimates += [entry.get("estimate") for entry in tangential.values() if isinstance(entry, Mapping)]
    estimates += [
        actuator.get(key, {}).get("estimate")
        for key in (
            "first_contact_closing_velocity_mps",
            "continuous_force_N",
            "peak_force_N",
            "power_off_holding_force_N",
            "control_latency_s",
        )
    ]
    geometry = contact.get("contact_geometry", {})
    geometry_null = all(
        geometry.get(key) is None
        for key in ("left_contact_frame_T_gripper_link", "right_contact_frame_T_gripper_link", "target_surface_normal")
    )
    return all(value is None for value in estimates) and geometry_null


def evaluate_snapshot(snapshot: EvidenceSnapshot) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    quantities: dict[str, Any] = {}
    topology = _evaluate_topology(snapshot, checks, quantities)
    frame = topology["frame"]
    boundary = topology["boundary"]
    _evaluate_urdf(snapshot, frame, topology["tree_joints"], checks, quantities)
    _evaluate_mass(boundary, _doc(snapshot, "mass_model"), checks, quantities)

    geometry = _doc(snapshot, "geometry_decision")
    collision = _doc(snapshot, "collision_audit")
    mesh_loadable = checks.get("urdf_mesh_bytes_hash_bound_and_nonempty", False)
    collision_authority = collision.get("narrow_phase_available") is True or collision.get("system_collision_release") is True
    _record(checks, "mesh_loadable_does_not_imply_collision_authority", mesh_loadable and not collision_authority and collision.get("narrow_phase_available") is False and collision.get("system_collision_release") is False)
    _record(checks, "geometry_is_digital_only_with_contact_hold", geometry.get("status") == "PASS_SOURCE_BOUND_LINK_LOCALIZATION_FOR_DIGITAL_GEOMETRY" and geometry.get("active_gripper_r1", {}).get("motion_contract", {}).get("contact_and_strength_status") == "HOLD")

    gripper = _doc(snapshot, "gripper_interface")
    velocity_gate = _doc(snapshot, "gripper_velocity_gate")
    model_layer = gripper.get("model_layer", {})
    physical_layer = gripper.get("physical_actuator_layer", {})
    _record(checks, "urdf_velocity_literal_is_15_m_s_model_only", _close(model_layer.get("urdf_velocity_limit_literal_m_s"), 15.0) and model_layer.get("role") == "MODEL_LIMIT_ONLY")
    _record(checks, "urdf_velocity_not_physical_velocity", all(value is None for key, value in physical_layer.items() if key != "status") and velocity_gate.get("physical_actuator_speed_authority") == "HOLD" and velocity_gate.get("physical_gripper_timing_ready") is False)
    quantities["gripper_urdf_velocity_literal"] = _quantity(15.0, "m/s", "GRIPPER_JOINT_FRAME", "PRISMATIC_COORDINATE", "ACCEPTED_URDF_MODEL_LIMIT_ONLY__NOT_PHYSICAL_CAPABILITY", "DIAGNOSTIC_ONLY", "gripper_interface", "model_layer.urdf_velocity_limit_literal_m_s")
    quantities["gripper_stroke"] = _quantity(0.0715, "m", "GRIPPER_JOINT_FRAME", "PRISMATIC_COORDINATE", "DIGITAL_GEOMETRY_VALUE__UNCERTAINTY_HOLD", "BOUND_DIGITAL", "contact_contract", "gripper_actuator.stroke_m.estimate")

    contact = _doc(snapshot, "contact_contract")
    contact_plan = _doc(snapshot, "contact_test_plan")
    _record(checks, "physical_contact_parameters_remain_null", _all_null_physical_contact(contact))
    _record(checks, "contact_zero_fill_forbidden", contact.get("zero_fill_forbidden") is True)
    _record(checks, "physical_contact_kernel_not_authorized", contact.get("physical_contact_kernel_authorized") is False)
    _record(checks, "CT01_through_CT05_planned_not_executed", tuple(test.get("id") for test in contact_plan.get("tests", ())) == ("CT-01", "CT-02", "CT-03", "CT-04", "CT-05") and all(str(test.get("status", "")).startswith("HOLD") for test in contact_plan.get("tests", ())))

    trajectory = _doc(snapshot, "trajectory_contract")
    trajectory_gate = _doc(snapshot, "trajectory_gate")
    segments = trajectory.get("segments", ())
    candidate_count = sum("PROVISIONAL" in str(item.get("trajectory_authority")) for item in segments)
    released_count = sum(item.get("released_for_mission_gate") is True for item in segments)
    _record(checks, "trajectory_joint_order_exact_rad_s", tuple(trajectory.get("joint_order", ())) == ACTUATED_JOINTS[:6] and trajectory.get("units") == {"q": "rad", "time": "s"})
    _record(checks, "eight_trajectory_segments_all_unknown", len(segments) == 8 and all(item.get("status") == "UNKNOWN" for item in segments))
    _record(checks, "candidate_trajectory_is_not_released", candidate_count > 0 and released_count == 0 and trajectory_gate.get("trajectory_segments_with_released_authority") == 0 and trajectory_gate.get("trajectory_segments_unknown") == 8)
    quantities["mandatory_trajectory_segment_count"] = _quantity(8, "count", "B601_CONFIGURATION_SPACE", "MISSION_SEQUENCE", "B601_MANDATORY_MISSION_TRAJECTORY_CONTRACT_V1", "DIAGNOSTIC_ONLY", "trajectory_contract", "segments")
    quantities["released_trajectory_segment_count"] = _quantity(0, "count", "B601_CONFIGURATION_SPACE", "MISSION_SEQUENCE", "B601_HARNESS_MISSION_COVERAGE_GATE_V1", "ABSENT", "trajectory_gate", "trajectory_segments_with_released_authority")

    source_gate = _doc(snapshot, "source_gate")
    current_audit = _doc(snapshot, "current_binding_audit")
    current = boundary.get("current_state", {})
    _record(checks, "source_only_gate_explicitly_emits_no_urdf", source_gate.get("urdf_emitted") is False and frame.get("source_only_boundary", {}).get("urdf_emitted") is False)
    _record(checks, "required_system_artifacts_absent", len(snapshot.required_absent_paths) == 2)
    _record(checks, "current_binding_explicitly_invalidated", current_audit.get("current_authority", {}).get("mechanical_release") is False and current_audit.get("current_authority", {}).get("diagnostic_kinematic_bootstrap_only") is True)
    _record(checks, "owner_and_rebind_authority_absent", source_gate.get("owner_accepted") is False and source_gate.get("sim13_rebind_authorized") is False and current.get("unified_r2_generation_authorized") is False)

    outputs = {
        "system_urdf_available": False,
        "current_system_bound": False,
        "physical_contact_ready": False,
        "dynamics_capture_entry_authorized": False,
        "next_stage_authorized": False,
    }
    _record(checks, "mandatory_outputs_all_false", all(outputs[name] is False for name in MANDATORY_FALSE))
    domain_ledger = {
        "system_topology_and_frames": {"status": "BOUND_DIGITAL", "authority": "UNIFIED_R2_SYSTEM_FRAME_TREE_V2", "claim": "source-bound static tree only"},
        "accepted_b601_kinematics_and_inertials": {"status": "BOUND_DIGITAL", "authority": "accepted B601 URDF immutable bytes", "claim": "digital kinematics, limits and inertials"},
        "whole_system_mass_properties": {"status": "DESIGN_CANDIDATE", "authority": "SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2", "claim": "design model, not measured or as-built"},
        "collision_geometry": {"status": "DIAGNOSTIC_ONLY", "authority": "M5 broad-phase plus hash-bound URDF mesh files", "claim": "loadable meshes are not authoritative narrow phase"},
        "mission_trajectory": {"status": "DIAGNOSTIC_ONLY", "authority": "candidate/UNKNOWN mission contract", "claim": "zero released segments"},
        "system_instantiation": {"status": "OWNER_REQUIRED", "authority": "separate single-use Owner/rebase authorization absent", "claim": "system URDF and V2 interface absent"},
        "physical_gripper_and_contact": {"status": "TEST_REQUIRED", "authority": "CT-01 through CT-05", "claim": "physical parameters remain null"},
        "authoritative_target_contact_geometry": {"status": "ABSENT", "authority": "M5 contact contract", "claim": "frames, normal and patch absent"},
    }
    _record(checks, "status_enum_exact_and_complete", set(item["status"] for item in domain_ledger.values()) == set(STATUS_ENUM))
    source_receipts = {
        artifact_id: {
            "path": artifact.relative_path,
            "bytes": artifact.byte_count,
            "sha256": artifact.sha256,
            "read_count": artifact.read_count,
        }
        for artifact_id, artifact in snapshot.artifacts.items()
    }
    passed = bool(checks) and all(checks.values())
    return {
        "schema": "M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_EVALUATION_V1",
        "source_only_validation_pass": passed,
        "evaluation_status": GATE_CEILING if passed else "FAIL_M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION",
        "checks": checks,
        "checks_passed": sum(checks.values()),
        "checks_total": len(checks),
        "quantities": quantities,
        "domain_ledger": domain_ledger,
        "machine_policy_results": {
            "mesh_loadable_is_collision_authority": False,
            "urdf_velocity_is_physical_velocity_authority": False,
            "candidate_trajectory_is_released_trajectory": False,
            "physical_contact_zero_fill_permitted": False,
        },
        "binding_contract": {
            "path": snapshot.binding_relative_path,
            "bytes": snapshot.binding_bytes,
            "sha256": snapshot.binding_sha256,
        },
        "source_receipts": source_receipts,
        "required_absent_paths": list(snapshot.required_absent_paths),
        **outputs,
    }


def evaluate_default_snapshot() -> dict[str, Any]:
    return evaluate_snapshot(load_default_snapshot())


def validate_publication_candidate(document: Mapping[str, Any]) -> None:
    """Reject any attempt to publish beyond this source-freeze ceiling."""
    if document.get("evaluation_status") != GATE_CEILING:
        raise AdmissionError("publication status is not the frozen source-only ceiling")
    if document.get("source_only_validation_pass") is not True:
        raise AdmissionError("source-only validation must be exact true")
    for field in MANDATORY_FALSE:
        if document.get(field) is not False:
            raise AdmissionError(f"mandatory false output was promoted: {field}")


def mutable_documents_for_tests(snapshot: EvidenceSnapshot) -> dict[str, Any]:
    """Return copies only for negative controls; never part of production admission."""
    return {
        artifact_id: thaw(artifact.parsed)
        for artifact_id, artifact in snapshot.artifacts.items()
        if isinstance(artifact.parsed, Mapping)
    }
