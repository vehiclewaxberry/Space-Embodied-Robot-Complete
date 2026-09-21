from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import yaml


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_REL = Path("contracts/SYSTEM_BINDING_V2_RESEARCH_CANDIDATE_CONTRACT_V1.json")
RECEIPT_REL = Path("evidence/SYSTEM_BINDING_V2_RESEARCH_CANDIDATE_RECEIPT_V1.json")
GATE_REL = Path("results/SYSTEM_BINDING_V2_RESEARCH_CANDIDATE_GATE_V1.json")
MANIFEST_REL = Path("manifest/SYSTEM_BINDING_V2_RESEARCH_CANDIDATE_SHA256_V1.json")


def find_repo_root(start: Path = PACKAGE_ROOT) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "PROJECT_MAP.md").is_file() and (candidate / "30_simulation").is_dir():
            return candidate
    raise RuntimeError("repository root not found")


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicates)
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected YAML mapping: {path}")
    return data


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def file_record(repo_root: Path, pin: dict[str, Any]) -> dict[str, Any]:
    path = repo_root / pin["path"]
    if not path.is_file():
        return {
            "path": pin["path"],
            "expected_sha256": pin["sha256"],
            "expected_bytes": pin["bytes"],
            "exists": False,
            "match": False,
            "role": pin["role"],
        }
    raw = path.read_bytes()
    actual_sha = sha256_bytes(raw)
    actual_bytes = len(raw)
    return {
        "path": pin["path"],
        "expected_sha256": pin["sha256"],
        "actual_sha256": actual_sha,
        "expected_bytes": pin["bytes"],
        "actual_bytes": actual_bytes,
        "exists": True,
        "match": actual_sha == pin["sha256"] and actual_bytes == pin["bytes"],
        "role": pin["role"],
    }


def _decimal(text: str) -> Decimal:
    try:
        value = Decimal(text)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"invalid finite number: {text!r}") from exc
    if not value.is_finite():
        raise ValueError(f"non-finite number: {text!r}")
    return value


def _number_token(text: str) -> str:
    value = _decimal(text)
    if value == 0:
        return "0"
    return str(value.normalize())


def _vector(value: str | None, default: str = "0 0 0") -> list[str]:
    values = (value if value is not None else default).split()
    if len(values) != 3:
        raise ValueError(f"expected 3-vector, got {value!r}")
    return [_number_token(item) for item in values]


def _origin(parent: ET.Element) -> dict[str, list[str]]:
    origin = parent.find("origin")
    return {
        "xyz": _vector(origin.get("xyz") if origin is not None else None),
        "rpy": _vector(origin.get("rpy") if origin is not None else None),
    }


def _link_semantics(link: ET.Element) -> dict[str, Any]:
    inertial = link.find("inertial")
    inertial_record: dict[str, Any] | None = None
    if inertial is not None:
        mass = inertial.find("mass")
        inertia = inertial.find("inertia")
        if mass is None or inertia is None:
            raise ValueError(f"incomplete inertial on link {link.get('name')}")
        inertial_record = {
            "origin": _origin(inertial),
            "mass": _number_token(mass.get("value", "")),
            "inertia": {
                key: _number_token(inertia.get(key, ""))
                for key in ("ixx", "ixy", "ixz", "iyy", "iyz", "izz")
            },
        }
    return {"name": link.get("name"), "inertial": inertial_record}


def _joint_semantics(joint: ET.Element) -> dict[str, Any]:
    parent = joint.find("parent")
    child = joint.find("child")
    if parent is None or child is None:
        raise ValueError(f"joint {joint.get('name')} lacks parent or child")
    axis = joint.find("axis")
    limit = joint.find("limit")
    return {
        "name": joint.get("name"),
        "type": joint.get("type"),
        "parent": parent.get("link"),
        "child": child.get("link"),
        "origin": _origin(joint),
        "axis": None if axis is None else _vector(axis.get("xyz")),
        "limit": None if limit is None else {
            key: (_number_token(limit.get(key)) if limit.get(key) is not None else None)
            for key in ("lower", "upper", "effort", "velocity")
        },
    }


def urdf_semantics(root: ET.Element) -> dict[str, Any]:
    return {
        "links": {link.get("name"): _link_semantics(link) for link in root.findall("link")},
        "joints": {joint.get("name"): _joint_semantics(joint) for joint in root.findall("joint")},
    }


def _geometry_valid(link: ET.Element) -> bool:
    for item in [*link.findall("visual"), *link.findall("collision")]:
        _origin(item)
        geometry = item.find("geometry")
        if geometry is None or len(list(geometry)) != 1:
            return False
        shape = list(geometry)[0]
        if shape.tag == "box":
            if any(_decimal(x) <= 0 for x in shape.get("size", "").split()) or len(shape.get("size", "").split()) != 3:
                return False
        elif shape.tag == "cylinder":
            if _decimal(shape.get("radius", "")) <= 0 or _decimal(shape.get("length", "")) <= 0:
                return False
        elif shape.tag == "sphere":
            if _decimal(shape.get("radius", "")) <= 0:
                return False
        elif shape.tag == "mesh":
            if not shape.get("filename"):
                return False
            if shape.get("scale") is not None and any(_decimal(x) <= 0 for x in shape.get("scale", "").split()):
                return False
        else:
            return False
    return True


def audit_urdf(system_path: Path, accepted_path: Path, contract: dict[str, Any]) -> dict[str, Any]:
    system_root = ET.fromstring(system_path.read_bytes())
    accepted_root = ET.fromstring(accepted_path.read_bytes())
    errors: list[str] = []
    if system_root.tag != "robot" or not system_root.get("name"):
        errors.append("SYSTEM_ROOT_OR_NAME_INVALID")
    links = system_root.findall("link")
    joints = system_root.findall("joint")
    link_names = [x.get("name") for x in links]
    joint_names = [x.get("name") for x in joints]
    if None in link_names or len(set(link_names)) != len(link_names):
        errors.append("SYSTEM_LINK_NAMES_INVALID_OR_DUPLICATE")
    if None in joint_names or len(set(joint_names)) != len(joint_names):
        errors.append("SYSTEM_JOINT_NAMES_INVALID_OR_DUPLICATE")

    parent_by_child: dict[str, str] = {}
    child_map: dict[str, list[str]] = {str(name): [] for name in link_names}
    joint_types: Counter[str] = Counter()
    axes_valid = True
    limits_valid = True
    origins_valid = True
    for joint in joints:
        try:
            record = _joint_semantics(joint)
        except ValueError:
            origins_valid = False
            continue
        parent, child = record["parent"], record["child"]
        if parent not in child_map or child not in child_map or child in parent_by_child:
            errors.append("SYSTEM_PARENT_CHILD_GRAPH_INVALID")
            continue
        parent_by_child[child] = parent
        child_map[parent].append(child)
        joint_types[str(record["type"])] += 1
        if record["type"] != "fixed":
            if record["axis"] is None:
                axes_valid = False
            else:
                values = [float(v) for v in record["axis"]]
                axes_valid &= all(math.isfinite(v) for v in values) and abs(sum(v * v for v in values) - 1.0) <= 1e-12
        if record["type"] in {"revolute", "prismatic"}:
            limit = record["limit"]
            if limit is None or limit["lower"] is None or limit["upper"] is None:
                limits_valid = False
            else:
                limits_valid &= _decimal(limit["lower"]) <= _decimal(limit["upper"])

    roots = sorted(set(str(x) for x in link_names) - set(parent_by_child))
    visited: set[str] = set()
    stack = roots[:]
    while stack:
        node = stack.pop()
        if node in visited:
            errors.append("SYSTEM_GRAPH_CYCLE")
            break
        visited.add(node)
        stack.extend(child_map.get(node, []))
    connected_acyclic = len(roots) == 1 and len(visited) == len(links) and len(joints) == len(links) - 1

    physical = [link for link in links if link.find("inertial") is not None]
    frame_only = [link for link in links if link.find("inertial") is None and not link.findall("visual") and not link.findall("collision")]
    mass_total_decimal = sum(
        (_decimal(link.find("inertial/mass").get("value", "")) for link in physical),
        Decimal("0"),
    )
    mass_total_float64 = sum(float(link.find("inertial/mass").get("value", "")) for link in physical)
    geometry_valid = True
    inertials_valid = True
    for link in links:
        try:
            geometry_valid &= _geometry_valid(link)
            rec = _link_semantics(link)
            if rec["inertial"] is not None:
                inertials_valid &= _decimal(rec["inertial"]["mass"]) > 0
                inertials_valid &= all(
                    _decimal(rec["inertial"]["inertia"][key]) > 0
                    for key in ("ixx", "iyy", "izz")
                )
        except ValueError:
            geometry_valid = False
            inertials_valid = False

    expected = contract["expected_topology"]
    accepted_expected = contract["accepted_b601_subtree"]
    accepted_sem = urdf_semantics(accepted_root)
    system_sem = urdf_semantics(system_root)
    accepted_link_names = set(accepted_sem["links"])
    accepted_joint_names = set(accepted_sem["joints"])
    system_subtree = {
        "links": {name: system_sem["links"].get(name) for name in sorted(accepted_link_names)},
        "joints": {name: system_sem["joints"].get(name) for name in sorted(accepted_joint_names)},
    }
    accepted_sorted = {
        "links": {name: accepted_sem["links"][name] for name in sorted(accepted_link_names)},
        "joints": {name: accepted_sem["joints"][name] for name in sorted(accepted_joint_names)},
    }
    subtree_equal = system_subtree == accepted_sorted
    accepted_mass_decimal = sum(
        (_decimal(rec["inertial"]["mass"]) for rec in accepted_sem["links"].values() if rec["inertial"] is not None),
        Decimal("0"),
    )
    accepted_mass_float64 = sum(
        float(rec["inertial"]["mass"])
        for rec in accepted_sem["links"].values()
        if rec["inertial"] is not None
    )

    checks = {
        "xml_parse_and_robot_name_valid": system_root.tag == "robot" and bool(system_root.get("name")),
        "unique_links_19": len(links) == expected["links"] and len(set(link_names)) == len(link_names),
        "unique_joints_18": len(joints) == expected["joints"] and len(set(joint_names)) == len(joint_names),
        "single_root_connected_acyclic": connected_acyclic and roots == [contract["frame_contract"]["root_link"]],
        "joint_types_fixed10_revolute6_prismatic2": joint_types == Counter({"fixed": expected["fixed"], "revolute": expected["revolute"], "prismatic": expected["prismatic"]}),
        "movable_axes_unit_and_joint_frame_ledger_bound": axes_valid,
        "revolute_and_prismatic_limits_ordered": limits_valid,
        "origins_finite_three_vectors": origins_valid,
        "geometry_schema_and_positive_dimensions": geometry_valid,
        "physical_links_16_with_positive_inertials": len(physical) == expected["physical_links"] and inertials_valid,
        "frame_only_links_exact_3": sorted(x.get("name") for x in frame_only) == sorted(expected["frame_only_link_names"]),
        "total_mass_matches_interface_float64_contract": mass_total_float64 == float(expected["total_mass_kg"]),
        "accepted_b601_link_joint_counts": len(accepted_link_names) == accepted_expected["links"] and len(accepted_joint_names) == accepted_expected["joints"],
        "accepted_b601_mass_matches_interface_float64_contract": accepted_mass_float64 == float(accepted_expected["mass_kg"]),
        "accepted_b601_semantic_subtree_exact": subtree_equal,
    }
    return {
        "checks": checks,
        "all_checks_pass": all(checks.values()) and not errors,
        "errors": sorted(set(errors)),
        "facts": {
            "robot_name": system_root.get("name"),
            "root_link": roots[0] if len(roots) == 1 else None,
            "links": len(links),
            "joints": len(joints),
            "physical_links": len(physical),
            "frame_only_links": len(frame_only),
            "joint_types": dict(sorted(joint_types.items())),
            "actuated_dof": joint_types["revolute"] + joint_types["prismatic"],
            "total_mass_kg": repr(mass_total_float64),
            "total_mass_decimal_literal_sum_kg": str(mass_total_decimal),
            "accepted_b601_mass_kg": repr(accepted_mass_float64),
            "accepted_b601_mass_decimal_literal_sum_kg": str(accepted_mass_decimal),
            "accepted_b601_semantic_digest": sha256_bytes(canonical_bytes(accepted_sorted)),
            "system_b601_semantic_digest": sha256_bytes(canonical_bytes(system_subtree)),
        },
    }


def dotted_get(mapping: dict[str, Any], path: str) -> Any:
    value: Any = mapping
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def audit_authority(
    interface: dict[str, Any],
    g12: dict[str, Any],
    m01_registry: dict[str, Any],
    m01_execution: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    false_values = {path: dotted_get(interface, path) for path in contract["required_interface_false_fields"]}
    true_values = {path: dotted_get(interface, path) for path in contract["required_interface_true_backend_evidence_fields"]}
    g12_fail_closed = (
        g12.get("verdict") == "MECHANICAL_TO_EMBODIED_HANDOFF_FAIL"
        and g12.get("next_stage_authorized") is False
        and g12.get("release_credit") is False
        and g12.get("current_handoff_gate_v2", {}).get("checks") == "11/12"
        and g12.get("current_handoff_gate_v2", {}).get("failed") == "G12 HARNESS_RATED_OPERATIONAL_ENVELOPE"
    )
    pair_coverage = m01_registry.get("pair_coverage", {})
    m01_registry_hold = (
        m01_registry.get("complete_system_collision_pass") is False
        and m01_registry.get("path_search_executed") is False
        and m01_registry.get("next_stage_authorized") is False
        and pair_coverage.get("status_counts", {}).get("UNASSESSED_FAIL_CLOSED") == 11166
    )
    authority = m01_execution.get("authority", {})
    execution = m01_execution.get("execution_record", {})
    readiness = m01_execution.get("remaining_readiness", {})
    m01_execution_hold = (
        m01_execution.get("static_preflight_pass") is False
        and authority.get("next_stage_authorized") is False
        and authority.get("runtime_memory_admission_pass") is False
        and execution.get("geometry_query_executed") is False
        and execution.get("path_search_executed") is False
        and readiness.get("three_stage_scene_instances_bound") == 0
        and readiness.get("clearance_policy_rows_bound") == 0
        and readiness.get("motion_certificates_bound") == 0
        and readiness.get("pair_oracle_rows_executed") == 0
    )
    checks = {
        "interface_required_false_fields_are_exact_false": all(value is False for value in false_values.values()),
        "interface_backend_evidence_fields_are_exact_true": all(value is True for value in true_values.values()),
        "g12_harness_remains_fail_closed_11_of_12": g12_fail_closed,
        "m01_registry_remains_11166_unassessed_fail_closed": m01_registry_hold,
        "m01_execution_remains_presearch_hold": m01_execution_hold,
    }
    blockers = [
        "OWNER_ACCEPTANCE_FALSE",
        "ROUTE_C_EXCLUSION_ACCEPTANCE_FALSE",
        "ROUTE_C_SCOPE_DISPOSITION_FALSE",
        "SIM13_SYSTEM_BINDING_GATE_FALSE",
        "G12_HARNESS_HANDOFF_FAIL_11_OF_12",
        "M01_11166_PAIRS_UNASSESSED_FAIL_CLOSED",
        "M01_SCENE_CLEARANCE_MOTION_ORACLE_AND_EDGE_AUTHORITY_ABSENT",
        "CONSUMER_LOAD_AUTHORIZATION_FALSE",
        "CONTACT_GRASP_AUTHORIZATION_FALSE",
    ]
    return {
        "checks": checks,
        "all_checks_pass": all(checks.values()),
        "interface_false_values": false_values,
        "interface_true_backend_evidence_values": true_values,
        "blockers": blockers,
        "sim13_system_binding_gate_passed": False,
        "consumer_load_authorized": False,
        "contact_grasp_authorized": False,
        "maximum_operational_state": "ABORT_ONLY",
        "next_stage_authorized": False,
        "release_credit": False,
    }


def _audit_backend_documents(repo_root: Path, pins: dict[str, Any]) -> dict[str, Any]:
    generation = load_json(repo_root / pins["urdf_generation_receipt"]["path"])
    loader = load_json(repo_root / pins["loader_validation_receipt"]["path"])
    runtime_receipt = load_json(repo_root / pins["runtime_evaluator_receipt"]["path"])
    runtime_gate = load_json(repo_root / pins["runtime_gate"]["path"])
    dynamics_receipt = load_json(repo_root / pins["dynamics_backend_receipt"]["path"])
    dynamics_gate = load_json(repo_root / pins["dynamics_backend_gate"]["path"])
    contact_receipt = load_json(repo_root / pins["contact_backend_receipt"]["path"])
    contact_gate = load_json(repo_root / pins["contact_backend_gate"]["path"])
    nc_gate = load_json(repo_root / pins["negative_control_20_of_20_gate"]["path"])
    checks = {
        "source_only_urdf_emission_disclosed_and_static_checks_pass": generation.get("all_checks_pass") is True and generation.get("next_stage_authorized") is False and generation.get("release_credit") is False and generation.get("emission_class") == "SOURCE_ONLY_BUILDER_EMISSION__NOT_GEN_URDF_AUTHORITY_EXECUTION",
        "loader_static_receipt_pass_but_rebind_false": loader.get("verdict") == "PASS_SOURCE_STATIC_ONLY__NO_URDF_NO_SIM13_REBIND_NO_EXECUTION_OR_RELEASE_AUTHORITY" and loader.get("owner_accepted") is False and loader.get("sim13_rebind_authorized") is False,
        "runtime_receipt_and_gate_pass_but_no_authority": runtime_receipt.get("all_checks_pass") is True and runtime_receipt.get("next_stage_authorized") is False and runtime_gate.get("gate_passed") is True and runtime_gate.get("next_stage_authorized") is False,
        "dynamics_receipt_and_gate_pass_but_no_authority": dynamics_receipt.get("all_checks_pass") is True and dynamics_receipt.get("next_stage_authorized") is False and dynamics_gate.get("gate_passed") is True and dynamics_gate.get("next_stage_authorized") is False,
        "contact_receipt_and_gate_pass_bounded_only": contact_receipt.get("all_checks_pass") is True and contact_receipt.get("next_stage_authorized") is False and "BOUNDED_PROVISIONAL" in str(contact_receipt.get("backend_scope")) and contact_gate.get("gate_passed") is True and contact_gate.get("next_stage_authorized") is False,
        "negative_controls_20_of_20_abort_only": nc_gate.get("gate_passed") is True and nc_gate.get("nc_score") == "20/20" and "ABORT_ONLY" in str(nc_gate.get("maximum_operational_state")) and nc_gate.get("next_stage_authorized") is False,
    }
    return {"checks": checks, "all_checks_pass": all(checks.values())}


def _interface_pin_crosscheck(interface: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    pins = contract["input_pins"]
    artifacts = interface.get("artifacts", {})
    pairs = {
        "accepted_b601_urdf": artifacts.get("accepted_b601_urdf", {}),
        "system_urdf": artifacts.get("system_urdf", {}),
        "urdf_generation_receipt": artifacts.get("urdf_generation_receipt", {}),
        "loader_source": artifacts.get("gate_stages", {}).get("SIM13_SYSTEM_BINDING_GATE_V2", {}).get("v2_loader_source", {}),
        "loader_validation_receipt": artifacts.get("gate_stages", {}).get("SIM13_SYSTEM_BINDING_GATE_V2", {}).get("v2_loader_validation_receipt", {}),
        "runtime_evaluator_source": artifacts.get("gate_stages", {}).get("SIM13_RUNTIME_FAIL_CLOSED_GATE_V2", {}).get("runtime_evaluator_source", {}),
        "runtime_gate_adapter_source": artifacts.get("gate_stages", {}).get("SIM13_RUNTIME_FAIL_CLOSED_GATE_V2", {}).get("runtime_gate_adapter_source", {}),
        "runtime_evaluator_receipt": artifacts.get("gate_stages", {}).get("SIM13_RUNTIME_FAIL_CLOSED_GATE_V2", {}).get("runtime_evaluator_receipt", {}),
        "dynamics_backend_source": artifacts.get("gate_stages", {}).get("SIM13_DYNAMICS_BACKEND_GATE_V2", {}).get("dynamics_backend_source", {}),
        "dynamics_backend_receipt": artifacts.get("gate_stages", {}).get("SIM13_DYNAMICS_BACKEND_GATE_V2", {}).get("dynamics_backend_validation_receipt", {}),
        "contact_backend_source": artifacts.get("gate_stages", {}).get("SIM13_CONTACT_GRASP_GATE_V2", {}).get("contact_backend_source", {}),
        "contact_backend_receipt": artifacts.get("gate_stages", {}).get("SIM13_CONTACT_GRASP_GATE_V2", {}).get("contact_backend_validation_receipt", {}),
        "sim_candidate_contract": artifacts.get("sim_candidate_contract", {}),
        "system_frame_tree": artifacts.get("system_frame_tree", {}),
    }
    results = {
        key: value.get("path") == pins[key]["path"] and value.get("sha256") == pins[key]["sha256"] and value.get("bytes") == pins[key]["bytes"]
        for key, value in pairs.items()
    }
    return {"checks": results, "all_checks_pass": all(results.values())}


def evaluate(repo_root: Path | None = None, contract_path: Path | None = None) -> dict[str, Any]:
    repo_root = (repo_root or find_repo_root()).resolve()
    contract_path = contract_path or (PACKAGE_ROOT / CONTRACT_REL)
    contract = load_json(contract_path)
    pins = contract["input_pins"]
    pin_records = {key: file_record(repo_root, pin) for key, pin in pins.items()}
    pins_match = all(record["match"] for record in pin_records.values())

    interface = load_yaml(repo_root / pins["mech_rl_system_interface_v2"]["path"])
    g12 = load_json(repo_root / pins["g12_mech_to_embodied_handoff_gate"]["path"])
    m01_registry = load_json(repo_root / pins["m01_collision_registry_gate"]["path"])
    m01_execution = load_json(repo_root / pins["m01_execution_closure_gate"]["path"])
    urdf_audit = audit_urdf(
        repo_root / pins["system_urdf"]["path"],
        repo_root / pins["accepted_b601_urdf"]["path"],
        contract,
    )
    interface_crosscheck = _interface_pin_crosscheck(interface, contract)
    backend_audit = _audit_backend_documents(repo_root, pins)
    authority_audit = audit_authority(interface, g12, m01_registry, m01_execution, contract)
    static_candidate_pass = pins_match and urdf_audit["all_checks_pass"] and interface_crosscheck["all_checks_pass"] and backend_audit["all_checks_pass"] and authority_audit["all_checks_pass"]
    return {
        "schema": "SYSTEM_BINDING_V2_RESEARCH_CANDIDATE_RECEIPT_V1",
        "generated_utc": "DETERMINISTIC_RECEIPT_NO_WALLCLOCK",
        "artifact_class": contract["artifact_class"],
        "configuration_id": contract["configuration_id"],
        "contract": {
            "path": CONTRACT_REL.as_posix(),
            "sha256": sha256_bytes(contract_path.read_bytes()),
            "bytes": len(contract_path.read_bytes()),
        },
        "source_pin_audit": {
            "count": len(pin_records),
            "all_match": pins_match,
            "records": pin_records,
        },
        "urdf_static_audit": urdf_audit,
        "interface_pin_crosscheck": interface_crosscheck,
        "backend_receipt_audit": backend_audit,
        "authority_hold_audit": authority_audit,
        "static_candidate_gate_passed": static_candidate_pass,
        "current_sim13_system_binding_gate_passed": False,
        "maximum_claim": "RESEARCH_CANDIDATE_LOAD__ABORT_ONLY" if static_candidate_pass else "ABORT_ONLY__CANDIDATE_LOAD_REJECTED",
        "non_abort_authorized": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "verdict": "STATIC_TOPOLOGY_HASH_SCHEMA_AND_RECEIPTS_PASS__OWNER_ROUTE_C_G12_M01_CONSUMER_AND_CONTACT_AUTHORITY_HOLD__ABORT_ONLY" if static_candidate_pass else "SYSTEM_BINDING_RESEARCH_CANDIDATE_REJECTED__ABORT_ONLY",
    }


def build_outputs(repo_root: Path | None = None, contract_path: Path | None = None) -> tuple[bytes, bytes, bytes]:
    receipt = evaluate(repo_root, contract_path)
    receipt_bytes = canonical_bytes(receipt)
    gate = {
        "schema": "SYSTEM_BINDING_V2_RESEARCH_CANDIDATE_GATE_V1",
        "generated_utc": "DETERMINISTIC_GATE_NO_WALLCLOCK",
        "receipt": {
            "path": RECEIPT_REL.as_posix(),
            "sha256": sha256_bytes(receipt_bytes),
            "bytes": len(receipt_bytes),
        },
        "checks": {
            "all_23_input_hash_pins_match": receipt["source_pin_audit"]["all_match"] and receipt["source_pin_audit"]["count"] == 23,
            "urdf_static_topology_and_b601_semantics_pass": receipt["urdf_static_audit"]["all_checks_pass"],
            "interface_artifact_pins_crosscheck": receipt["interface_pin_crosscheck"]["all_checks_pass"],
            "loader_runtime_dynamics_contact_receipts_bounded_pass": receipt["backend_receipt_audit"]["all_checks_pass"],
            "authority_holds_detected_fail_closed": receipt["authority_hold_audit"]["all_checks_pass"],
        },
        "candidate_static_gate_passed": receipt["static_candidate_gate_passed"],
        "sim13_system_binding_gate_passed": False,
        "maximum_claim": receipt["maximum_claim"],
        "maximum_operational_state": "ABORT_ONLY",
        "non_abort_authorized": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "blockers": receipt["authority_hold_audit"]["blockers"],
        "verdict": receipt["verdict"],
    }
    gate_bytes = canonical_bytes(gate)
    local_source_roles = {
        CONTRACT_REL: "binding contract and frozen external input pins",
        Path("evaluate_system_binding_candidate_v1.py"): "deterministic CLI writer/checker",
        Path("system_binding_candidate/__init__.py"): "package export",
        Path("system_binding_candidate/evaluator.py"): "read-only evaluator",
        Path("tests/conftest.py"): "test import bootstrap",
        Path("tests/test_system_binding_candidate.py"): "positive and fail-closed negative controls",
        Path("pytest.ini"): "test configuration",
        Path("README.md"): "scope, boundary and reproduction instructions",
    }
    local_sources = {}
    for rel, role in local_source_roles.items():
        raw = (PACKAGE_ROOT / rel).read_bytes()
        local_sources[rel.as_posix()] = {
            "path": rel.as_posix(),
            "sha256": sha256_bytes(raw),
            "bytes": len(raw),
            "role": role,
        }
    manifest = {
        "schema": "SYSTEM_BINDING_V2_RESEARCH_CANDIDATE_SHA256_V1",
        "generated_utc": "DETERMINISTIC_MANIFEST_NO_WALLCLOCK",
        "contract": receipt["contract"],
        "local_sources": local_sources,
        "inputs": receipt["source_pin_audit"]["records"],
        "generated_outputs": {
            "receipt": {"path": RECEIPT_REL.as_posix(), "sha256": sha256_bytes(receipt_bytes), "bytes": len(receipt_bytes)},
            "gate": {"path": GATE_REL.as_posix(), "sha256": sha256_bytes(gate_bytes), "bytes": len(gate_bytes)},
        },
    }
    return receipt_bytes, gate_bytes, canonical_bytes(manifest)


def authority_negative_control(interface: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    """Pure helper used by tests: caller-supplied promotion claims cannot create authority."""
    candidate = deepcopy(interface)
    candidate.setdefault("authority", {}).setdefault("current_values", {})["owner_accepted"] = True
    return candidate
