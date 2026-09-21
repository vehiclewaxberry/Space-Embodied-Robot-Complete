#!/usr/bin/env python3
"""Build the deterministic Route-C C1.5 pre-CAD diagnostic evidence package."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, MutableMapping, Sequence, Tuple

sys.dont_write_bytecode = True

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = next(parent for parent in PACKAGE.parents if (parent / "PROJECT_MAP.md").is_file())
AUTHORITY_PATH = PACKAGE / "00_authority/ROUTE_C_PRECAD_DIAGNOSTIC_CONTRACT_V1.yaml"
SEMANTICS_PATH = PACKAGE / "01_predicate/ROUTE_C_CONTACT_AND_GUIDE_SEMANTICS_V1.yaml"
KERNEL_PATH = PACKAGE / "01_predicate/route_c_predicate_kernel.py"
PARAMETER_PATH = PACKAGE / "02_search/ROUTE_C_PARAMETER_SPACE_V1.yaml"

QUALIFICATION_PATH = PACKAGE / "01_predicate/ROUTE_C_PREDICATE_QUALIFICATION_V1.json"
FRONTIER_PATH = PACKAGE / "02_search/ROUTE_C_GEOMETRIC_CAPACITY_FRONTIER_V1.json"
GATE_PATH = PACKAGE / "03_gate/ROUTE_C_PRECAD_PARAMETRIC_SEARCH_GATE_V1.json"
VALIDATION_PATH = PACKAGE / "03_gate/ROUTE_C_PRECAD_PARAMETRIC_SEARCH_VALIDATION_V1.json"
MANIFEST_PATH = PACKAGE / "03_gate/ROUTE_C_PRECAD_PARAMETRIC_SEARCH_OUTPUT_MANIFEST_V1.json"

EXPECTED_VERDICT = (
    "UNKNOWN_FAIL_CLOSED__PREDICATE_QUALIFICATION_AND_PARAMETER_SPACE_FROZEN__"
    "PHYSICAL_GUIDE_VOLUMES_CAD_BRANCH_ODR42_MPI_VENDOR_MISSION_AND_RELEASE_HOLD"
)
GENERATED_LOCAL = "2026-08-23T23:15:00+08:00"
GATE_AUTHORITY_CLASS = "NON_RELEASE_C1_5_DIAGNOSTIC_GATE"
GATE_AUTHORITY_EFFECT = "CLOSES_PREDICATE_QUALIFICATION_AND_PARAMETER_SEARCH_CONTRACT_ONLY"
LOCAL_BINDING_CLASS = "LOCAL_HASH_BOUND_REPRODUCIBILITY_AND_SELF_CONSISTENCY__NO_EXTERNAL_TRUST_ANCHOR"
EXPECTED_PARAMETER_CANONICAL_SHA256 = "271318F10115ED212A19A038BFFCA7D0ADDF77C74D4D54DD08D057F9FE991F3B"
EXPECTED_PARAMETER_TOP_LEVEL_KEYS = [
    "authority_class",
    "global_scan_axes",
    "joint_domain_rule",
    "joint_variable_schema",
    "mutual_exclusion_rule",
    "next_stage_authorized",
    "schema",
    "search_output_rules",
    "selection_status",
    "status",
    "topologies",
    "unknown_physical_inputs",
    "version",
]
EXPECTED_PARAMETER_SECTION_SHA256 = {
    "top_level_metadata": "D7CF14632BB89686094A8AA690C935767DF95A5234576CD71EAD40767F1D4E74",
    "topologies": "7F424885605A3C17114AB7730280B52ADA0321D18625C6A681036D94682D2270",
    "global_scan_axes": "23FF00E4A1323016D99F0A6B71CC27E1C59F8F3FB546F274B3DCD564B04B6411",
    "joint_variable_schema": "A47825E22CEC54ACF21CE6C072A4CCEAFC055DD8C94427E79126B0CE361AB79E",
    "unknown_physical_inputs": "687A838AE36E939CC9C57209D228E9C50E5CF232F8D2B983B80A195DFFDE4EE2",
    "search_output_rules": "0F320DEE441A1CDC4C3F29D03D319ABAB59CB4A5A8D753BF0C574C4BBF483E79",
}
EXPECTED_PARAMETER_CANONICAL_AUDIT = {
    "binding_class": LOCAL_BINDING_CLASS,
    "code_binding": "EXPECTED_PARAMETER_CANONICAL_SHA256_AND_SECTION_SHA256_CONSTANTS",
    "expected_canonical_sha256": EXPECTED_PARAMETER_CANONICAL_SHA256,
    "actual_canonical_sha256": EXPECTED_PARAMETER_CANONICAL_SHA256,
    "canonical_contract_match": True,
    "expected_top_level_keys": EXPECTED_PARAMETER_TOP_LEVEL_KEYS,
    "actual_top_level_keys": EXPECTED_PARAMETER_TOP_LEVEL_KEYS,
    "top_level_keys_exact": True,
    "section_bindings": {
        name: {
            "expected_sha256": digest,
            "actual_sha256": digest,
            "match": True,
        }
        for name, digest in EXPECTED_PARAMETER_SECTION_SHA256.items()
    },
    "violations": [],
}
EXPECTED_PREDICATE_QUALIFICATION = {
    "state": "PASS_SYNTHETIC_SEMANTICS_ONLY",
    "positive_controls_passed": 11,
    "positive_controls_total": 11,
    "negative_controls_passed": 36,
    "negative_controls_total": 36,
    "tests_passed": 47,
    "tests_total": 47,
    "comparison_sets_nonempty": True,
    "grants_design_authority": False,
}
EXPECTED_PARAMETER_GATE_STATE = {
    "state": "FROZEN_NON_RELEASE",
    "topology_ids": ["RC-A", "RC-B", "RC-C", "RC-D"],
    "topologies_mutually_exclusive": True,
    "RC_D_primary_status": "REJECTED_AS_PRIMARY_CONCEPT",
    "J4_side_bypass_and_guided_loop_merged": False,
    "bundle_OD_is_scan_axis_not_known_value": True,
    "vendor_bend_is_scan_axis_not_known_value": True,
    "accepted_urdf_joint_ranges_reduced": False,
    "branch_result_averaging_forbidden": True,
    "scan_axis_as_measured_value_forbidden": True,
    "test_pass_as_authority_forbidden": True,
    "candidate_found_without_physical_guides_forbidden": True,
    "physical_null_contract": {
        "all_required_physical_values_null": True,
        "global_selected_values_and_uncertainties_null": True,
        "joint_physical_values_null": True,
        "unknown_physical_inputs_null": True,
        "search_output_physical_values_null": True,
        "violations": [],
    },
    "canonical_contract": EXPECTED_PARAMETER_CANONICAL_AUDIT,
}
EXPECTED_PHYSICAL_CAPACITY_STATE = {
    "state": "UNKNOWN_NOT_COMPUTABLE",
    "candidate_found": False,
    "physical_candidates_evaluated": 0,
    "D_max_geometry_mm": None,
    "R_path_min_mm": None,
    "deltaL_mm": None,
    "carrier_travel_mm": None,
    "manufacturing_coordinates_mm": None,
}
EXPECTED_PHYSICAL_INPUT_STATE = {
    "HN_02": "ABSENT",
    "HN_03": "ABSENT",
    "named_finite_guide_volumes": "ABSENT",
    "physical_route_c_cad_branch": "ABSENT",
    "manufacturing_coordinates_mm": None,
}
EXPECTED_UPSTREAM_GATE_STATE = {
    "ODR42": "PENDING",
    "MPI_controlled": 0,
    "MPI_total": 8,
    "MPI_gate": "HOLD",
    "CAD_entry_gate": "HOLD",
    "CAD_entry_verdict": "ROUTE_C_PARAMETRIC_CAD_ENTRY_NOT_AUTHORIZED",
}
EXPECTED_CRITERIA = [
    {"id": "RC15-01", "state": "PASS", "claim": "ALL_PREREGISTERED_SOURCE_HASHES_MATCH"},
    {"id": "RC15-02", "state": "PASS_SYNTHETIC_ONLY", "claim": "PREDICATE_SEMANTICS_QUALIFIED"},
    {"id": "RC15-03", "state": "PASS_NON_RELEASE", "claim": "MUTUALLY_EXCLUSIVE_PARAMETER_SPACE_FROZEN"},
    {"id": "RC15-04", "state": "UNKNOWN", "claim": "PHYSICAL_GUIDE_VOLUMES_ABSENT"},
    {"id": "RC15-05", "state": "UNKNOWN", "claim": "PHYSICAL_GEOMETRIC_CAPACITY_FRONTIER_NOT_COMPUTABLE"},
    {"id": "RC15-06", "state": "HOLD", "claim": "ODR42_PENDING"},
    {"id": "RC15-07", "state": "HOLD", "claim": "MPI_0_OF_8_CONTROLLED"},
    {"id": "RC15-08", "state": "HOLD", "claim": "C2_CAD_ENTRY_NOT_AUTHORIZED"},
    {"id": "RC15-09", "state": "HOLD", "claim": "VENDOR_MISSION_MASS_TORQUE_PRODUCTION_CONTACT_HARDWARE_AND_FLIGHT_NOT_RELEASED"},
]
EXPECTED_CLAIMS_NOT_MADE = [
    "ROUTE_C_CANDIDATE_FOUND",
    "PHYSICAL_GEOMETRIC_FEASIBILITY",
    "FULL_RANGE_PASS",
    "MISSION_PASS",
    "C2_CAD_AUTHORIZED",
    "PRODUCTION_OR_FLIGHT_RELEASE",
]


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def render_json(payload: Any) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def canonical_sha256(payload: Any) -> str:
    return sha256_bytes(render_json(payload))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_kernel() -> Any:
    spec = importlib.util.spec_from_file_location("route_c_predicate_kernel", KERNEL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load predicate kernel")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_bindings(authority: Mapping[str, Any]) -> List[Dict[str, Any]]:
    bindings: List[Dict[str, Any]] = []
    for pin in authority["source_hash_pins"]:
        source_path = ROOT / pin["path"]
        actual = sha256_file(source_path) if source_path.is_file() else None
        bindings.append(
            {
                "name": pin["name"],
                "path": pin["path"],
                "expected_sha256": pin["sha256"],
                "actual_sha256": actual,
                "hash_match": actual == pin["sha256"],
                "role": pin["role"],
            }
        )
    return bindings


def local_hash_bound_bindings(authority: Mapping[str, Any]) -> List[Dict[str, Any]]:
    bindings: List[Dict[str, Any]] = []
    pins = authority.get("local_hash_bound_sources")
    if not isinstance(pins, list):
        return bindings
    for pin in pins:
        if not isinstance(pin, Mapping):
            continue
        path_value = pin.get("path")
        source_path = ROOT / path_value if isinstance(path_value, str) else Path("__MISSING__")
        actual = sha256_file(source_path) if source_path.is_file() else None
        bindings.append(
            {
                "name": pin.get("name"),
                "path": path_value,
                "expected_sha256": pin.get("sha256"),
                "actual_sha256": actual,
                "hash_match": actual == pin.get("sha256"),
                "role": pin.get("role"),
            }
        )
    return bindings


def binding_by_name(bindings: Iterable[Mapping[str, Any]], name: str) -> Mapping[str, Any]:
    return next(binding for binding in bindings if binding["name"] == name)


def measure(value: Any, unit: str, status: str, reason: str) -> Dict[str, Any]:
    return {
        "value": value,
        "unit": unit,
        "standard_uncertainty": None,
        "uncertainty_distribution": None,
        "degrees_of_freedom": None,
        "status": status,
        "reason": reason,
    }


def audit_parameter_canonical_contract(parameter: Mapping[str, Any]) -> Dict[str, Any]:
    section_names = (
        "topologies",
        "global_scan_axes",
        "joint_variable_schema",
        "unknown_physical_inputs",
        "search_output_rules",
    )
    actual_top_level_keys = sorted(str(key) for key in parameter.keys()) if isinstance(parameter, Mapping) else []
    top_level_keys_exact = actual_top_level_keys == EXPECTED_PARAMETER_TOP_LEVEL_KEYS
    actual_canonical_sha256 = canonical_sha256(parameter)
    section_payloads: Dict[str, Any] = {
        "top_level_metadata": {
            key: value for key, value in parameter.items() if key not in section_names
        } if isinstance(parameter, Mapping) else None,
    }
    for name in section_names:
        section_payloads[name] = parameter.get(name, "MISSING_SECTION") if isinstance(parameter, Mapping) else "MISSING_SECTION"
    section_bindings: Dict[str, Dict[str, Any]] = {}
    violations: List[str] = []
    if not top_level_keys_exact:
        violations.append("TOP_LEVEL_KEY_SET_DRIFT")
    if actual_canonical_sha256 != EXPECTED_PARAMETER_CANONICAL_SHA256:
        violations.append("FULL_CANONICAL_CONTRACT_HASH_DRIFT")
    for name, expected_digest in EXPECTED_PARAMETER_SECTION_SHA256.items():
        actual_digest = canonical_sha256(section_payloads[name])
        match = actual_digest == expected_digest
        section_bindings[name] = {
            "expected_sha256": expected_digest,
            "actual_sha256": actual_digest,
            "match": match,
        }
        if not match:
            violations.append(f"{name}:CANONICAL_HASH_DRIFT")
    return {
        "binding_class": LOCAL_BINDING_CLASS,
        "code_binding": "EXPECTED_PARAMETER_CANONICAL_SHA256_AND_SECTION_SHA256_CONSTANTS",
        "expected_canonical_sha256": EXPECTED_PARAMETER_CANONICAL_SHA256,
        "actual_canonical_sha256": actual_canonical_sha256,
        "canonical_contract_match": not violations,
        "expected_top_level_keys": deepcopy(EXPECTED_PARAMETER_TOP_LEVEL_KEYS),
        "actual_top_level_keys": actual_top_level_keys,
        "top_level_keys_exact": top_level_keys_exact,
        "section_bindings": section_bindings,
        "violations": violations,
    }


def audit_parameter_physical_nulls(parameter: Mapping[str, Any]) -> Dict[str, Any]:
    violations: List[str] = []
    axes = parameter.get("global_scan_axes")
    if not isinstance(axes, list):
        violations.append("global_scan_axes:MISSING")
        axes = []
    for index, axis in enumerate(axes):
        if not isinstance(axis, Mapping):
            violations.append(f"global_scan_axes[{index}]:INVALID")
            continue
        if axis.get("selected_value") is not None:
            violations.append(f"global_scan_axes[{index}].selected_value")
        if axis.get("uncertainty") is not None:
            violations.append(f"global_scan_axes[{index}].uncertainty")

    def walk_joint_variables(value: Any, path: str) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                child_path = f"{path}.{key}"
                if key == "physical_value" and child is not None:
                    violations.append(child_path)
                else:
                    walk_joint_variables(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk_joint_variables(child, f"{path}[{index}]")

    walk_joint_variables(parameter.get("joint_variable_schema"), "joint_variable_schema")
    unknowns = parameter.get("unknown_physical_inputs")
    if not isinstance(unknowns, Mapping):
        violations.append("unknown_physical_inputs:MISSING")
    else:
        for key, value in unknowns.items():
            if value is not None:
                violations.append(f"unknown_physical_inputs.{key}")
    search_rules = parameter.get("search_output_rules")
    required_search_nulls = ("D_max_geometry_mm", "R_path_min_mm", "deltaL_mm", "carrier_travel_mm")
    if not isinstance(search_rules, Mapping):
        violations.append("search_output_rules:MISSING")
    else:
        for key in required_search_nulls:
            if search_rules.get(key) is not None:
                violations.append(f"search_output_rules.{key}")
        if search_rules.get("candidate_found_allowed_without_physical_guide_volumes") is not False:
            violations.append("search_output_rules.candidate_found_allowed_without_physical_guide_volumes")
    return {
        "all_required_physical_values_null": not violations,
        "violations": sorted(violations),
        "global_selected_values_and_uncertainties_null": not any(item.startswith("global_scan_axes") for item in violations),
        "joint_physical_values_null": not any(item.startswith("joint_variable_schema") for item in violations),
        "unknown_physical_inputs_null": not any(item.startswith("unknown_physical_inputs") for item in violations),
        "search_output_physical_values_null": not any(item.startswith("search_output_rules") for item in violations),
    }


def build_parameter_gate_state(parameter: Mapping[str, Any]) -> Dict[str, Any]:
    audit = audit_parameter_physical_nulls(parameter)
    canonical_audit = audit_parameter_canonical_contract(parameter)
    topologies = parameter.get("topologies")
    topology_ids = [item.get("id") for item in topologies if isinstance(item, Mapping)] if isinstance(topologies, list) else []
    topology_ids_exact = topology_ids == ["RC-A", "RC-B", "RC-C", "RC-D"] and len(set(topology_ids)) == 4
    mutual_rule = parameter.get("mutual_exclusion_rule")
    mutually_exclusive = topology_ids_exact and isinstance(mutual_rule, str) and mutual_rule.startswith("Exactly one of RC-A, RC-B, RC-C or RC-D")
    rc_d = next((item for item in topologies if isinstance(item, Mapping) and item.get("id") == "RC-D"), {}) if isinstance(topologies, list) else {}
    joint_schema = parameter.get("joint_variable_schema")
    j4 = joint_schema.get("J4") if isinstance(joint_schema, Mapping) else None
    j4_rule = j4.get("branch_rule") if isinstance(j4, Mapping) else None
    j4_not_merged = isinstance(j4_rule, str) and "mutually exclusive" in j4_rule and "shall not be merged" in j4_rule
    axes = parameter.get("global_scan_axes")
    axes_by_id = {
        item.get("id"): item
        for item in axes
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    } if isinstance(axes, list) else {}

    def diagnostic_axis_unknown(axis_id: str, required_authority: str) -> bool:
        axis = axes_by_id.get(axis_id)
        return bool(
            isinstance(axis, Mapping)
            and axis.get("selected_value") is None
            and axis.get("uncertainty") is None
            and axis.get("authority") == required_authority
        )

    joint_domain_rule = parameter.get("joint_domain_rule")
    accepted_ranges_reduced = not (
        isinstance(joint_domain_rule, str)
        and joint_domain_rule.startswith("Accepted-URDF J1..J6 ranges remain unchanged")
        and parameter.get("accepted_urdf_joint_ranges_reduced") in (None, False)
    )
    search_rules = parameter.get("search_output_rules")
    search_rules = search_rules if isinstance(search_rules, Mapping) else {}
    state = {
        "state": "FROZEN_NON_RELEASE",
        "topology_ids": topology_ids,
        "topologies_mutually_exclusive": mutually_exclusive,
        "RC_D_primary_status": rc_d.get("status"),
        "J4_side_bypass_and_guided_loop_merged": not j4_not_merged,
        "bundle_OD_is_scan_axis_not_known_value": diagnostic_axis_unknown(
            "bundle_outer_diameter", "SCAN_AXIS_ONLY_VENDOR_AND_MPI_VALUE_UNKNOWN"
        ),
        "vendor_bend_is_scan_axis_not_known_value": diagnostic_axis_unknown(
            "vendor_minimum_bend_radius", "SCAN_AXIS_ONLY_VENDOR_VALUE_UNKNOWN"
        ),
        "accepted_urdf_joint_ranges_reduced": accepted_ranges_reduced,
        "branch_result_averaging_forbidden": search_rules.get("branch_result_averaging") == "FORBIDDEN",
        "scan_axis_as_measured_value_forbidden": search_rules.get("scan_axis_as_measured_value") == "FORBIDDEN",
        "test_pass_as_authority_forbidden": search_rules.get("test_pass_as_authority") == "FORBIDDEN",
        "candidate_found_without_physical_guides_forbidden": search_rules.get(
            "candidate_found_allowed_without_physical_guide_volumes"
        ) is False,
        "physical_null_contract": audit,
        "canonical_contract": canonical_audit,
    }
    if state != EXPECTED_PARAMETER_GATE_STATE:
        state["state"] = "INVALID_PARAMETER_CONTRACT__FAIL_CLOSED"
    return state


def run_parameter_null_negative_controls(
    parameter: Mapping[str, Any],
    authority: Mapping[str, Any] | None = None,
    qualification: Mapping[str, Any] | None = None,
    bindings: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    controls: List[Tuple[str, Callable[[MutableMapping[str, Any]], None]]] = [
        ("PN01_GLOBAL_SELECTED_OD", lambda value: value["global_scan_axes"][0].__setitem__("selected_value", 9.9)),
        ("PN02_GLOBAL_AXIS_UNCERTAINTY", lambda value: value["global_scan_axes"][0].__setitem__("uncertainty", 0.2)),
        ("PN03_J1_PHYSICAL_VALUE", lambda value: value["joint_variable_schema"]["J1"][0].__setitem__("physical_value", 42.0)),
        ("PN04_J4_NESTED_PHYSICAL_VALUE", lambda value: value["joint_variable_schema"]["J4"]["J4_GUIDED_LOOP"][0].__setitem__("physical_value", 42.0)),
        ("PN05_UNKNOWN_SELECTED_BUNDLE_OD", lambda value: value["unknown_physical_inputs"].__setitem__("selected_bundle_outer_diameter_mm", 9.9)),
        ("PN06_UNKNOWN_CARRIER_HARDSTOPS", lambda value: value["unknown_physical_inputs"].__setitem__("carrier_hard_stop_positions_mm", [0.0, 100.0])),
        ("PN07_SEARCH_OUTPUT_DMAX", lambda value: value["search_output_rules"].__setitem__("D_max_geometry_mm", 10.0)),
    ]
    results: List[Dict[str, Any]] = []
    for control_id, mutator in controls:
        probe = deepcopy(parameter)
        mutator(probe)
        audit = audit_parameter_physical_nulls(probe)
        detected = audit["all_required_physical_values_null"] is False
        pipeline_state = "NOT_EXECUTED"
        pipeline_reason = "AUDIT_ONLY"
        frontier_status = "NOT_EXECUTED"
        derived_measurands_still_null = True
        if authority is not None and qualification is not None and bindings is not None:
            probe_frontier = build_frontier(authority, probe, qualification, bindings)
            probe_gate = build_gate(authority, probe, qualification, probe_frontier, bindings)
            pipeline_state, pipeline_reason = classify_gate_candidate(probe_gate, authority)
            frontier_status = probe_frontier["status"]
            physical = probe_frontier["physical_capacity_frontier"]
            derived_measurands_still_null = all(
                physical[name]["value"] is None
                for name in ("D_max_geometry_mm", "R_path_min_mm", "deltaL_mm", "carrier_travel_mm")
            ) and physical["manufacturing_coordinates_mm"] is None
            detected = bool(
                detected
                and frontier_status == "PARAMETER_PHYSICAL_NULL_CONTRACT_VIOLATED__FAIL_CLOSED"
                and probe_gate["parameter_space"]["physical_null_contract"]["all_required_physical_values_null"] is False
                and pipeline_state != "VALID_FAIL_CLOSED_GATE"
                and probe_gate["candidate_found"] is False
                and probe_gate["physical_capacity_frontier"]["physical_candidates_evaluated"] == 0
                and derived_measurands_still_null
            )
        results.append(
            {
                "id": control_id,
                "passed": detected,
                "violations": audit["violations"],
                "frontier_status": frontier_status,
                "gate_classifier_state": pipeline_state,
                "gate_classifier_reason": pipeline_reason,
                "derived_measurands_still_null": derived_measurands_still_null,
            }
        )
    return {
        "controls_total": len(results),
        "controls_passed": sum(item["passed"] for item in results),
        "all_passed": all(item["passed"] for item in results),
        "controls": results,
    }


def run_parameter_contract_negative_controls(
    parameter: Mapping[str, Any],
    authority: Mapping[str, Any] | None = None,
    qualification: Mapping[str, Any] | None = None,
    bindings: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    controls: List[Tuple[str, Callable[[MutableMapping[str, Any]], None]]] = [
        ("PC01_GLOBAL_RANGE_DRIFT", lambda value: value["global_scan_axes"][0]["diagnostic_range"].__setitem__("max", 999.0)),
        ("PC02_GLOBAL_UNIT_DRIFT", lambda value: value["global_scan_axes"][0].__setitem__("unit", "inch")),
        ("PC03_JOINT_VARIABLE_ID_DRIFT", lambda value: value["joint_variable_schema"]["J1"][0].__setitem__("id", "renamed_axis")),
        ("PC04_JOINT_RANGE_DRIFT", lambda value: value["joint_variable_schema"]["J1"][0]["diagnostic_range"].__setitem__("max", 9999.0)),
        ("PC05_GLOBAL_AXIS_REMOVED", lambda value: value["global_scan_axes"].pop()),
        ("PC06_UNKNOWN_INPUT_KEY_REMOVED", lambda value: value["unknown_physical_inputs"].pop("selected_vendor_minimum_bend_radius_mm")),
        ("PC07_SEARCH_OUTPUT_KEY_REMOVED", lambda value: value["search_output_rules"].pop("D_max_geometry_mm")),
        ("PC08_TOPOLOGY_RECORD_DRIFT", lambda value: value["topologies"][0].__setitem__("architecture", "rewritten-architecture")),
        ("PC09_EXTRA_TOP_LEVEL_KEY", lambda value: value.__setitem__("unregistered_parameter", None)),
        ("PC10_J4_BRANCH_RULE_DRIFT", lambda value: value["joint_variable_schema"]["J4"].__setitem__("branch_rule", "merged")),
        ("PC11_JOINT_UNIT_DRIFT", lambda value: value["joint_variable_schema"]["J6"][0].__setitem__("unit", "inch")),
        ("PC12_TOPOLOGY_EXTRA_FIELD", lambda value: value["topologies"][2].__setitem__("selected", True)),
    ]
    results: List[Dict[str, Any]] = []
    for control_id, mutator in controls:
        probe = deepcopy(parameter)
        mutator(probe)
        audit = audit_parameter_canonical_contract(probe)
        detected = audit["canonical_contract_match"] is False
        pipeline_state = "NOT_EXECUTED"
        pipeline_reason = "AUDIT_ONLY"
        frontier_status = "NOT_EXECUTED"
        derived_measurands_still_null = True
        if authority is not None and qualification is not None and bindings is not None:
            probe_frontier = build_frontier(authority, probe, qualification, bindings)
            probe_gate = build_gate(authority, probe, qualification, probe_frontier, bindings)
            pipeline_state, pipeline_reason = classify_gate_candidate(probe_gate, authority)
            frontier_status = probe_frontier["status"]
            physical = probe_frontier["physical_capacity_frontier"]
            derived_measurands_still_null = all(
                physical[name]["value"] is None
                for name in ("D_max_geometry_mm", "R_path_min_mm", "deltaL_mm", "carrier_travel_mm")
            ) and physical["manufacturing_coordinates_mm"] is None
            detected = bool(
                detected
                and frontier_status == "PARAMETER_CANONICAL_CONTRACT_VIOLATED__FAIL_CLOSED"
                and probe_gate["parameter_space"]["canonical_contract"]["canonical_contract_match"] is False
                and pipeline_state != "VALID_FAIL_CLOSED_GATE"
                and probe_gate["candidate_found"] is False
                and probe_gate["physical_capacity_frontier"]["physical_candidates_evaluated"] == 0
                and derived_measurands_still_null
            )
        results.append(
            {
                "id": control_id,
                "passed": detected,
                "violations": audit["violations"],
                "frontier_status": frontier_status,
                "gate_classifier_state": pipeline_state,
                "gate_classifier_reason": pipeline_reason,
                "derived_measurands_still_null": derived_measurands_still_null,
            }
        )
    return {
        "controls_total": len(results),
        "controls_passed": sum(item["passed"] for item in results),
        "all_passed": all(item["passed"] for item in results),
        "controls": results,
    }


def route_c_trade_rows() -> List[Dict[str, str]]:
    trade_path = ROOT / binding_by_name(source_bindings(load_json(AUTHORITY_PATH)), "route_c_concept_trade")["path"]
    with trade_path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def build_frontier(
    authority: Mapping[str, Any], parameter: Mapping[str, Any], qualification: Mapping[str, Any], bindings: List[Dict[str, Any]]
) -> Dict[str, Any]:
    v1 = load_json(ROOT / binding_by_name(bindings, "route_b_full_fk_v1")["path"])
    v2 = load_json(ROOT / binding_by_name(bindings, "route_b_full_fk_v2")["path"])
    v1_results = v1["results"]
    v2_results = v2["results"]
    parameter_null_audit = audit_parameter_physical_nulls(parameter)
    parameter_canonical_audit = audit_parameter_canonical_contract(parameter)
    if not parameter_null_audit["all_required_physical_values_null"]:
        frontier_status = "PARAMETER_PHYSICAL_NULL_CONTRACT_VIOLATED__FAIL_CLOSED"
    elif not parameter_canonical_audit["canonical_contract_match"]:
        frontier_status = "PARAMETER_CANONICAL_CONTRACT_VIOLATED__FAIL_CLOSED"
    else:
        frontier_status = "PHYSICAL_ROUTE_C_FRONTIER_NOT_COMPUTABLE"
    required_null_reason = (
        "PHYSICAL_ROUTE_C_GUIDE_CLAMP_CONNECTOR_VOLUMES_HN_02_HN_03_AND_CAD_BRANCH_ARE_ABSENT; "
        "ODR42_AND_MPI_REMAIN_OPEN"
    )
    return {
        "schema": "ROUTE_C_GEOMETRIC_CAPACITY_FRONTIER_V1",
        "generated_local": GENERATED_LOCAL,
        "authority_class": "NON_RELEASE_PRE_CAD_CAPACITY_DIAGNOSTIC",
        "status": frontier_status,
        "candidate_found": False,
        "physical_route_c_candidates_evaluated": 0,
        "physical_guide_volumes_evaluated": 0,
        "scope": "Route-B negative baseline plus null physical Route-C capacity measurands; no new route is generated.",
        "source_hashes_all_match": all(item["hash_match"] for item in bindings),
        "parameter_physical_null_audit": parameter_null_audit,
        "parameter_canonical_contract_audit": parameter_canonical_audit,
        "route_b_baselines": {
            "V1": {
                "status": "DOCUMENTED_NEGATIVE_RESULT",
                "functional_gate": v1["verdict"]["B601_HARNESS_FUNCTIONAL_GATE"],
                "clearance_worst_mm": v1_results["clearance_worst_mm"],
                "min_bend_radius_mm": v1_results["min_bend_radius_mm"],
                "pinch_worst_mm": v1_results["pinch_worst_mm"],
                "source_sha256": binding_by_name(bindings, "route_b_full_fk_v1")["actual_sha256"],
            },
            "V2": {
                "status": "DOCUMENTED_HARD_NEGATIVE_RESULT__ROUTE_B_REJECTED",
                "functional_gate": v2["verdict"]["B601_HARNESS_FUNCTIONAL_GATE"],
                "clearance_worst_mm": v2_results["clearance_worst_mm"],
                "clearance_worst_state": v2_results["clearance_worst_state"],
                "clearance_worst_against": v2_results["clearance_worst_against"],
                "min_bend_radius_mm": v2_results["min_bend_radius_mm"],
                "min_bend_argmin": v2_results["min_bend_argmin"],
                "pinch_worst_mm": v2_results["pinch_worst_mm"],
                "pinch_worst_state": v2_results["pinch_worst_state"],
                "pinch_worst_joint": v2_results["pinch_worst_joint"],
                "source_sha256": binding_by_name(bindings, "route_b_full_fk_v2")["actual_sha256"],
            },
            "terminal_disposition": "ROUTE_B_REJECTED__NOT_REOPENED_BY_THIS_DIAGNOSTIC",
        },
        "topology_branches": [
            {
                "id": topology["id"],
                "architecture": topology["architecture"],
                "status": topology["status"],
                "physical_frontier_computed": False,
                "selected": False,
            }
            for topology in parameter["topologies"]
        ],
        "physical_capacity_frontier": {
            "computable": False,
            "frontier_points": [],
            "D_max_geometry_mm": measure(None, "mm", "UNKNOWN", required_null_reason),
            "R_path_min_mm": measure(None, "mm", "UNKNOWN", required_null_reason),
            "deltaL_mm": measure(None, "mm", "UNKNOWN", required_null_reason),
            "carrier_travel_mm": measure(None, "mm", "UNKNOWN", required_null_reason),
            "manufacturing_coordinates_mm": None,
            "manufacturing_coordinates_status": "NULL_UNTIL_HN_02_HN_03_NAMED_FINITE_GUIDE_VOLUMES_AND_PHYSICAL_CAD_BRANCH_EXIST",
        },
        "scan_axis_boundary": {
            "bundle_outer_diameter": "DIAGNOSTIC_AXIS_ONLY__SELECTED_VALUE_NULL",
            "vendor_minimum_bend_radius": "DIAGNOSTIC_AXIS_ONLY__SELECTED_VALUE_NULL",
            "keepout_inflation": "SENSITIVITY_AXIS_ONLY__NOT_A_TOLERANCE",
            "axis_values_are_physical_authority": False,
        },
        "predicate_capacity_properties": {
            "signed_distance_deep_penetration_qualified": True,
            "owner_scoped_finite_contact_volume_semantics_qualified": True,
            "C2_curve_and_failure_injection_semantics_qualified": True,
            "OD_bend_keepout_feasible_set_monotonicity_qualified_on_synthetic_candidates": True,
            "qualification_summary": qualification["summary"],
            "physical_feasibility_inference_allowed": False,
        },
        "required_missing_inputs": {
            "HN_02_datum_and_volume": None,
            "HN_03_datum_and_volume": None,
            "named_finite_guide_volumes": None,
            "named_finite_clamp_volumes": None,
            "named_finite_connector_volumes": None,
            "physical_route_c_cad_branch": None,
            "selected_bundle_outer_diameter_mm": None,
            "selected_vendor_minimum_bend_radius_mm": None,
        },
        "authority_effect": "NONE__PREDICATE_AND_PARAMETER_SPACE_CLOSED_ONLY",
    }


def build_predicate_gate_state(qualification: Mapping[str, Any]) -> Dict[str, Any]:
    summary = qualification.get("summary")
    summary = summary if isinstance(summary, Mapping) else {}
    negative_controls = qualification.get("negative_controls")
    empty_control = next(
        (
            item
            for item in negative_controls
            if isinstance(item, Mapping) and item.get("id") == "N08_EMPTY_COMPARISON_UNKNOWN"
        ),
        {},
    ) if isinstance(negative_controls, list) else {}
    authority_effect = qualification.get("authority_effect")
    return {
        "state": summary.get("qualification"),
        "positive_controls_passed": summary.get("positive_controls_passed"),
        "positive_controls_total": summary.get("positive_controls_total"),
        "negative_controls_passed": summary.get("negative_controls_passed"),
        "negative_controls_total": summary.get("negative_controls_total"),
        "tests_passed": summary.get("tests_passed"),
        "tests_total": summary.get("tests_total"),
        "comparison_sets_nonempty": empty_control.get("passed") is True,
        "grants_design_authority": not (
            isinstance(authority_effect, str) and authority_effect.startswith("NONE__")
        ),
    }


def _frontier_measure_value(physical: Mapping[str, Any], name: str) -> Any:
    item = physical.get(name)
    return item.get("value") if isinstance(item, Mapping) else "MISSING_OR_INVALID"


def build_physical_capacity_gate_state(frontier: Mapping[str, Any]) -> Dict[str, Any]:
    physical = frontier.get("physical_capacity_frontier")
    physical = physical if isinstance(physical, Mapping) else {}
    audit = frontier.get("parameter_physical_null_audit")
    audit_ok = isinstance(audit, Mapping) and audit.get("all_required_physical_values_null") is True
    canonical_audit = frontier.get("parameter_canonical_contract_audit")
    canonical_ok = isinstance(canonical_audit, Mapping) and canonical_audit.get("canonical_contract_match") is True
    expected_unavailable = frontier.get("status") == "PHYSICAL_ROUTE_C_FRONTIER_NOT_COMPUTABLE" and audit_ok and canonical_ok
    return {
        "state": "UNKNOWN_NOT_COMPUTABLE" if expected_unavailable else "INVALID_OR_DRIFTED_PHYSICAL_FRONTIER__FAIL_CLOSED",
        "candidate_found": frontier.get("candidate_found"),
        "physical_candidates_evaluated": frontier.get("physical_route_c_candidates_evaluated"),
        "D_max_geometry_mm": _frontier_measure_value(physical, "D_max_geometry_mm"),
        "R_path_min_mm": _frontier_measure_value(physical, "R_path_min_mm"),
        "deltaL_mm": _frontier_measure_value(physical, "deltaL_mm"),
        "carrier_travel_mm": _frontier_measure_value(physical, "carrier_travel_mm"),
        "manufacturing_coordinates_mm": physical.get("manufacturing_coordinates_mm", "MISSING_OR_INVALID"),
    }


def build_physical_input_gate_state(parameter: Mapping[str, Any]) -> Dict[str, Any]:
    unknowns = parameter.get("unknown_physical_inputs")
    unknowns = unknowns if isinstance(unknowns, Mapping) else {}

    def presence(key: str) -> str:
        if key not in unknowns:
            return "UNKNOWN_MISSING"
        return "ABSENT" if unknowns[key] is None else "PRESENT_UNQUALIFIED"

    return {
        "HN_02": presence("HN_02_datum_and_volume"),
        "HN_03": presence("HN_03_datum_and_volume"),
        "named_finite_guide_volumes": presence("named_finite_guide_volumes"),
        "physical_route_c_cad_branch": presence("physical_route_c_cad_branch"),
        "manufacturing_coordinates_mm": unknowns.get("manufacturing_coordinates_mm", "MISSING_OR_INVALID"),
    }


def build_gate(
    authority: Mapping[str, Any], parameter: Mapping[str, Any], qualification: Mapping[str, Any], frontier: Mapping[str, Any], bindings: List[Dict[str, Any]]
) -> Dict[str, Any]:
    mpi = load_json(ROOT / binding_by_name(bindings, "route_c_mpi_gate")["path"])
    cad_entry = load_json(ROOT / binding_by_name(bindings, "route_c_cad_entry_gate")["path"])
    odr42_text = (ROOT / binding_by_name(bindings, "odr42_request")["path"]).read_text(encoding="utf-8")
    predicate_state = build_predicate_gate_state(qualification)
    parameter_state = build_parameter_gate_state(parameter)
    physical_capacity_state = build_physical_capacity_gate_state(frontier)
    physical_input_state = build_physical_input_gate_state(parameter)
    local_bindings = local_hash_bound_bindings(authority)
    local_reproducibility = {
        "binding_class": LOCAL_BINDING_CLASS,
        "external_trust_anchor": False,
        "authority_pin_count": len(authority.get("local_hash_bound_sources", []))
        if isinstance(authority.get("local_hash_bound_sources"), list)
        else 0,
        "bindings": local_bindings,
        "all_match": len(local_bindings) == 5 and all(item["hash_match"] for item in local_bindings),
    }
    criteria = deepcopy(EXPECTED_CRITERIA)
    if not all(item["hash_match"] for item in bindings):
        next(item for item in criteria if item["id"] == "RC15-01")["state"] = "UNKNOWN"
    if predicate_state != EXPECTED_PREDICATE_QUALIFICATION:
        next(item for item in criteria if item["id"] == "RC15-02")["state"] = "UNKNOWN"
    if parameter_state != EXPECTED_PARAMETER_GATE_STATE:
        next(item for item in criteria if item["id"] == "RC15-03")["state"] = "UNKNOWN"
    return {
        "schema": "ROUTE_C_PRECAD_PARAMETRIC_SEARCH_GATE_V1",
        "generated_local": GENERATED_LOCAL,
        "gate": "UNKNOWN_FAIL_CLOSED",
        "verdict": EXPECTED_VERDICT,
        "authority_class": GATE_AUTHORITY_CLASS,
        "next_stage_authorized": False,
        "cad_entry_authorized": False,
        "candidate_found": False,
        "route_b_disposition": "REJECTED",
        "source_bindings": bindings,
        "source_hashes_all_match": all(item["hash_match"] for item in bindings),
        "local_hash_bound_reproducibility": local_reproducibility,
        "route_b_v2_hard_negative_results_verbatim": deepcopy(authority["route_b_v2_hard_negative_results_verbatim"]),
        "predicate_qualification": predicate_state,
        "parameter_space": parameter_state,
        "physical_capacity_frontier": physical_capacity_state,
        "physical_input_state": physical_input_state,
        "upstream_gate_state": {
            "ODR42": "PENDING" if "owner_decision: PENDING" in odr42_text else "UNKNOWN",
            "MPI_controlled": mpi["criteria_controlled"],
            "MPI_total": mpi["criteria_total"],
            "MPI_gate": mpi["gate"],
            "CAD_entry_gate": cad_entry["gate"],
            "CAD_entry_verdict": cad_entry["verdict"],
        },
        "criteria": criteria,
        "retained_holds": deepcopy(authority["retained_holds"]),
        "forbidden_shortcuts": deepcopy(authority["forbidden_shortcuts"]),
        "authority_effect": GATE_AUTHORITY_EFFECT,
        "claims_not_made": deepcopy(EXPECTED_CLAIMS_NOT_MADE),
    }


def classify_gate_candidate(candidate: Mapping[str, Any], authority: Mapping[str, Any]) -> Tuple[str, str]:
    expected_keys = {
        "schema", "generated_local", "gate", "verdict", "authority_class",
        "next_stage_authorized", "cad_entry_authorized", "candidate_found",
        "route_b_disposition", "source_bindings", "source_hashes_all_match",
        "local_hash_bound_reproducibility",
        "route_b_v2_hard_negative_results_verbatim", "predicate_qualification",
        "parameter_space", "physical_capacity_frontier", "physical_input_state",
        "upstream_gate_state", "criteria", "retained_holds", "forbidden_shortcuts",
        "authority_effect", "claims_not_made",
    }
    if not isinstance(candidate, Mapping) or set(candidate) != expected_keys:
        return "UNKNOWN", "TOP_LEVEL_GATE_SCHEMA_DRIFT"
    if candidate["schema"] != "ROUTE_C_PRECAD_PARAMETRIC_SEARCH_GATE_V1" or candidate["generated_local"] != GENERATED_LOCAL:
        return "UNKNOWN", "GATE_IDENTITY_OR_FREEZE_TIME_DRIFT"
    if candidate["gate"] != "UNKNOWN_FAIL_CLOSED" or candidate["verdict"] != EXPECTED_VERDICT:
        return "UNKNOWN", "TERMINAL_VERDICT_DRIFT"
    if candidate["authority_class"] != GATE_AUTHORITY_CLASS or candidate["authority_effect"] != GATE_AUTHORITY_EFFECT:
        return "INVALID", "AUTHORITY_CLASS_OR_EFFECT_UPLIFT"
    if candidate["next_stage_authorized"] is not False or candidate["cad_entry_authorized"] is not False:
        return "INVALID", "UNAUTHORIZED_STAGE_OR_CAD_ENTRY"
    if candidate["candidate_found"] is not False:
        return "INVALID", "UNSUPPORTED_CANDIDATE_FOUND"
    if candidate["route_b_disposition"] != "REJECTED":
        return "INVALID", "ROUTE_B_REJECTION_NOT_RETAINED"
    if candidate["source_hashes_all_match"] is not True:
        return "UNKNOWN", "SOURCE_HASH_SUMMARY_NOT_TRUE"

    pins = authority.get("source_hash_pins")
    if not isinstance(pins, list) or len(pins) != 13:
        return "UNKNOWN", "AUTHORITY_SOURCE_PIN_COUNT_DRIFT"
    pin_names = [item.get("name") for item in pins if isinstance(item, Mapping)]
    if len(pin_names) != 13 or len(set(pin_names)) != 13:
        return "UNKNOWN", "AUTHORITY_SOURCE_PIN_NAMES_NOT_UNIQUE"
    pins_by_name = {item["name"]: item for item in pins}
    bindings = candidate["source_bindings"]
    if not isinstance(bindings, list) or len(bindings) != 13:
        return "UNKNOWN", "SOURCE_BINDING_COUNT_DRIFT"
    binding_names = [item.get("name") for item in bindings if isinstance(item, Mapping)]
    if len(binding_names) != 13 or len(set(binding_names)) != 13 or set(binding_names) != set(pins_by_name):
        return "UNKNOWN", "SOURCE_BINDING_NAME_SET_OR_UNIQUENESS_DRIFT"
    for binding in bindings:
        if set(binding) != {"name", "path", "expected_sha256", "actual_sha256", "hash_match", "role"}:
            return "UNKNOWN", "SOURCE_BINDING_FIELD_SCHEMA_DRIFT"
        pin = pins_by_name[binding["name"]]
        expected_binding = {
            "name": pin["name"],
            "path": pin["path"],
            "expected_sha256": pin["sha256"],
            "actual_sha256": pin["sha256"],
            "hash_match": True,
            "role": pin["role"],
        }
        if binding != expected_binding:
            return "UNKNOWN", "SOURCE_BINDING_PATH_HASH_OR_ROLE_DRIFT"

    local_state = candidate["local_hash_bound_reproducibility"]
    if not isinstance(local_state, Mapping) or set(local_state) != {
        "binding_class", "external_trust_anchor", "authority_pin_count", "bindings", "all_match"
    }:
        return "UNKNOWN", "LOCAL_HASH_BOUND_REPRODUCIBILITY_SCHEMA_DRIFT"
    if local_state["binding_class"] != LOCAL_BINDING_CLASS or local_state["external_trust_anchor"] is not False:
        return "INVALID", "LOCAL_BINDING_TRUST_CLASS_MISREPRESENTED"
    local_pins = authority.get("local_hash_bound_sources")
    if not isinstance(local_pins, list) or len(local_pins) != 5 or local_state["authority_pin_count"] != 5:
        return "UNKNOWN", "LOCAL_HASH_BOUND_PIN_COUNT_DRIFT"
    local_pin_names = [item.get("name") for item in local_pins if isinstance(item, Mapping)]
    if len(local_pin_names) != 5 or len(set(local_pin_names)) != 5:
        return "UNKNOWN", "LOCAL_HASH_BOUND_PIN_NAMES_NOT_UNIQUE"
    for pin in local_pins:
        if set(pin) != {"name", "path", "sha256", "role"}:
            return "UNKNOWN", "LOCAL_HASH_BOUND_PIN_FIELD_SET_DRIFT"
        if not isinstance(pin["sha256"], str) or not re.fullmatch(r"[0-9A-F]{64}", pin["sha256"]):
            return "UNKNOWN", "LOCAL_HASH_BOUND_PIN_DIGEST_INVALID"
    local_by_name = {item["name"]: item for item in local_pins}
    local_bindings = local_state["bindings"]
    if not isinstance(local_bindings, list) or len(local_bindings) != 5 or local_state["all_match"] is not True:
        return "UNKNOWN", "LOCAL_HASH_BOUND_BINDING_COUNT_OR_SUMMARY_DRIFT"
    local_names = [item.get("name") for item in local_bindings if isinstance(item, Mapping)]
    if len(local_names) != 5 or len(set(local_names)) != 5 or set(local_names) != set(local_by_name):
        return "UNKNOWN", "LOCAL_HASH_BOUND_BINDING_NAME_SET_DRIFT"
    for binding in local_bindings:
        if set(binding) != {"name", "path", "expected_sha256", "actual_sha256", "hash_match", "role"}:
            return "UNKNOWN", "LOCAL_HASH_BOUND_BINDING_FIELD_SET_DRIFT"
        pin = local_by_name[binding["name"]]
        expected_binding = {
            "name": pin["name"],
            "path": pin["path"],
            "expected_sha256": pin["sha256"],
            "actual_sha256": pin["sha256"],
            "hash_match": True,
            "role": pin["role"],
        }
        if binding != expected_binding:
            return "UNKNOWN", "LOCAL_HASH_BOUND_PATH_HASH_OR_ROLE_DRIFT"

    if candidate["route_b_v2_hard_negative_results_verbatim"] != authority["route_b_v2_hard_negative_results_verbatim"]:
        return "INVALID", "ROUTE_B_HARD_NEGATIVE_RESULT_DRIFT"
    predicate = candidate["predicate_qualification"]
    if predicate != EXPECTED_PREDICATE_QUALIFICATION:
        if isinstance(predicate, Mapping) and predicate.get("grants_design_authority") is not False:
            return "INVALID", "PREDICATE_AUTHORITY_UPLIFT"
        return "UNKNOWN", "PREDICATE_QUALIFICATION_SCHEMA_OR_COUNT_DRIFT"
    parameter = candidate["parameter_space"]
    if parameter != EXPECTED_PARAMETER_GATE_STATE:
        if isinstance(parameter, Mapping) and (
            parameter.get("accepted_urdf_joint_ranges_reduced") is not False
            or parameter.get("J4_side_bypass_and_guided_loop_merged") is not False
            or parameter.get("topologies_mutually_exclusive") is not True
        ):
            return "INVALID", "PARAMETER_SHORTCUT_OR_URDF_RANGE_REDUCTION"
        return "UNKNOWN", "PARAMETER_SPACE_SCHEMA_DRIFT"
    physical = candidate["physical_capacity_frontier"]
    if physical != EXPECTED_PHYSICAL_CAPACITY_STATE:
        return "INVALID", "PHYSICAL_CAPACITY_STATE_COORDINATE_OR_VALUE_INJECTION"
    physical_inputs = candidate["physical_input_state"]
    if physical_inputs != EXPECTED_PHYSICAL_INPUT_STATE:
        return "INVALID", "PHYSICAL_INPUT_STATE_OR_COORDINATE_INJECTION"
    if candidate["upstream_gate_state"] != EXPECTED_UPSTREAM_GATE_STATE:
        return "UNKNOWN", "UPSTREAM_GATE_STATE_CHANGED_OR_MISSING"
    if candidate["criteria"] != EXPECTED_CRITERIA:
        return "INVALID", "CRITERIA_STATE_OR_CLAIM_UPLIFT"
    if candidate["retained_holds"] != authority["retained_holds"]:
        return "UNKNOWN", "RETAINED_HOLD_SET_OR_ORDER_DRIFT"
    if candidate["forbidden_shortcuts"] != authority["forbidden_shortcuts"]:
        return "UNKNOWN", "FORBIDDEN_SHORTCUT_SET_OR_ORDER_DRIFT"
    if candidate["claims_not_made"] != EXPECTED_CLAIMS_NOT_MADE:
        return "INVALID", "CLAIMS_NOT_MADE_SCHEMA_OR_RELEASE_BOUNDARY_DRIFT"
    return "VALID_FAIL_CLOSED_GATE", "PREDICATE_AND_PARAMETER_CONTRACT_ONLY"


def run_deep_copy_negative_controls(gate: Mapping[str, Any], authority: Mapping[str, Any]) -> Dict[str, Any]:
    original_bytes = render_json(gate)
    def duplicate_source_bindings(value: MutableMapping[str, Any]) -> None:
        first = deepcopy(value["source_bindings"][0])
        value["source_bindings"] = [deepcopy(first) for _ in range(13)]

    def remove_required_source(value: MutableMapping[str, Any]) -> None:
        value["source_bindings"].pop()

    def uplift_criterion(value: MutableMapping[str, Any], criterion_id: str) -> None:
        next(item for item in value["criteria"] if item["id"] == criterion_id)["state"] = "PASS"

    controls: List[Tuple[str, Callable[[MutableMapping[str, Any]], None], set[str]]] = [
        ("DC01_MISSING_GATE", lambda value: value.pop("gate"), {"UNKNOWN"}),
        ("DC02_EMPTY_VERDICT", lambda value: value.__setitem__("verdict", ""), {"UNKNOWN"}),
        ("DC03_SOURCE_HASH_DRIFT", lambda value: value["source_bindings"][0].__setitem__("actual_sha256", "0" * 64), {"UNKNOWN"}),
        ("DC04_CANDIDATE_FOUND_INJECTION", lambda value: value.__setitem__("candidate_found", True), {"INVALID"}),
        ("DC05_DMAX_FABRICATION", lambda value: value["physical_capacity_frontier"].__setitem__("D_max_geometry_mm", 12.0), {"INVALID"}),
        ("DC06_GUIDE_VOLUME_FALSE_CLOSURE", lambda value: value["physical_input_state"].__setitem__("named_finite_guide_volumes", "PRESENT"), {"INVALID"}),
        ("DC07_ODR42_SILENT_APPROVAL", lambda value: value["upstream_gate_state"].__setitem__("ODR42", "APPROVED"), {"UNKNOWN"}),
        ("DC08_MPI_SILENT_CLOSURE", lambda value: value["upstream_gate_state"].__setitem__("MPI_controlled", 8), {"UNKNOWN"}),
        ("DC09_CAD_ENTRY_SILENT_PASS", lambda value: value["upstream_gate_state"].__setitem__("CAD_entry_gate", "PASS"), {"UNKNOWN"}),
        ("DC10_NEXT_STAGE_BYPASS", lambda value: value.__setitem__("next_stage_authorized", True), {"INVALID"}),
        ("DC11_ROUTE_B_REOPENED", lambda value: value.__setitem__("route_b_disposition", "PASS"), {"INVALID"}),
        ("DC12_EMPTY_COMPARISON_INJECTION", lambda value: value["predicate_qualification"].__setitem__("comparison_sets_nonempty", False), {"UNKNOWN"}),
        ("DC13_PREDICATE_COUNT_DRIFT", lambda value: value["predicate_qualification"].__setitem__("tests_passed", 0), {"UNKNOWN"}),
        ("DC14_REQUIRED_HOLD_REMOVED", lambda value: value["retained_holds"].remove("HOLD_FULL_RANGE"), {"UNKNOWN"}),
        ("DC15_DUPLICATE_SOURCE_BINDINGS", duplicate_source_bindings, {"UNKNOWN"}),
        ("DC16_REQUIRED_SOURCE_BINDING_REMOVED", remove_required_source, {"UNKNOWN"}),
        ("DC17_SOURCE_PATH_DRIFT", lambda value: value["source_bindings"][0].__setitem__("path", "wrong/path"), {"UNKNOWN"}),
        ("DC18_SOURCE_EXPECTED_HASH_DRIFT", lambda value: value["source_bindings"][0].__setitem__("expected_sha256", "F" * 64), {"UNKNOWN"}),
        ("DC19_SOURCE_HASH_MATCH_FALSE", lambda value: value["source_bindings"][0].__setitem__("hash_match", False), {"UNKNOWN"}),
        ("DC20_SOURCE_HASH_SUMMARY_FALSE", lambda value: value.__setitem__("source_hashes_all_match", False), {"UNKNOWN"}),
        ("DC21_MPI_GATE_PASS_WITH_ZERO_CONTROLLED", lambda value: value["upstream_gate_state"].__setitem__("MPI_gate", "PASS"), {"UNKNOWN"}),
        ("DC22_CAD_ENTRY_VERDICT_UPLIFT", lambda value: value["upstream_gate_state"].__setitem__("CAD_entry_verdict", "PASS"), {"UNKNOWN"}),
        ("DC23_PREDICATE_GRANTS_AUTHORITY", lambda value: value["predicate_qualification"].__setitem__("grants_design_authority", True), {"INVALID"}),
        ("DC24_AUTHORITY_CLASS_UPLIFT", lambda value: value.__setitem__("authority_class", "RELEASE_AUTHORITY"), {"INVALID"}),
        ("DC25_AUTHORITY_EFFECT_UPLIFT", lambda value: value.__setitem__("authority_effect", "AUTHORIZES_C2_CAD"), {"INVALID"}),
        ("DC26_PHYSICAL_FRONTIER_STATE_PASS", lambda value: value["physical_capacity_frontier"].__setitem__("state", "PASS"), {"INVALID"}),
        ("DC27_PHYSICAL_CANDIDATE_COUNT_INJECTION", lambda value: value["physical_capacity_frontier"].__setitem__("physical_candidates_evaluated", 1), {"INVALID"}),
        ("DC28_PHYSICAL_COORDINATE_INJECTION", lambda value: value["physical_capacity_frontier"].__setitem__("manufacturing_coordinates_mm", [0.0, 0.0, 0.0]), {"INVALID"}),
        ("DC29_PHYSICAL_INPUT_COORDINATE_INJECTION", lambda value: value["physical_input_state"].__setitem__("manufacturing_coordinates_mm", [0.0, 0.0, 0.0]), {"INVALID"}),
        ("DC30_HN02_FALSE_CLOSURE", lambda value: value["physical_input_state"].__setitem__("HN_02", "PRESENT"), {"INVALID"}),
        ("DC31_ACCEPTED_URDF_RANGE_REDUCTION", lambda value: value["parameter_space"].__setitem__("accepted_urdf_joint_ranges_reduced", True), {"INVALID"}),
        ("DC32_J4_BRANCH_MERGE", lambda value: value["parameter_space"].__setitem__("J4_side_bypass_and_guided_loop_merged", True), {"INVALID"}),
        ("DC33_TOPOLOGY_NONEXCLUSION", lambda value: value["parameter_space"].__setitem__("topologies_mutually_exclusive", False), {"INVALID"}),
        ("DC34_BUNDLE_AXIS_PROMOTED_TO_KNOWN", lambda value: value["parameter_space"].__setitem__("bundle_OD_is_scan_axis_not_known_value", False), {"UNKNOWN"}),
        ("DC35_PHYSICAL_UNKNOWN_CRITERION_UPLIFT", lambda value: uplift_criterion(value, "RC15-04"), {"INVALID"}),
        ("DC36_CAD_AUTHORITY_CRITERION_UPLIFT", lambda value: uplift_criterion(value, "RC15-08"), {"INVALID"}),
        ("DC37_RELEASE_BOUNDARY_CLAIM_REMOVED", lambda value: value["claims_not_made"].remove("C2_CAD_AUTHORIZED"), {"INVALID"}),
        ("DC38_FORBIDDEN_SHORTCUT_REMOVED", lambda value: value["forbidden_shortcuts"].pop(0), {"UNKNOWN"}),
        ("DC39_EXTRA_TOP_LEVEL_AUTHORITY_FIELD", lambda value: value.__setitem__("owner_approved", True), {"UNKNOWN"}),
        ("DC40_ROUTE_B_HARD_NEGATIVE_REWRITE", lambda value: value["route_b_v2_hard_negative_results_verbatim"].__setitem__("clearance_worst_mm", 1.0), {"INVALID"}),
        ("DC41_CAD_ENTRY_BOOLEAN_BYPASS", lambda value: value.__setitem__("cad_entry_authorized", True), {"INVALID"}),
        ("DC42_PHYSICAL_INPUT_EXTRA_STATE", lambda value: value["physical_input_state"].__setitem__("physical_coordinates", "PRESENT"), {"INVALID"}),
        ("DC43_PHYSICAL_FRONTIER_EXTRA_VALUE", lambda value: value["physical_capacity_frontier"].__setitem__("D_selected_mm", 10.0), {"INVALID"}),
        ("DC44_LOCAL_BINDING_HASH_DRIFT", lambda value: value["local_hash_bound_reproducibility"]["bindings"][0].__setitem__("actual_sha256", "0" * 64), {"UNKNOWN"}),
        ("DC45_LOCAL_BINDING_FALSE_EXTERNAL_TRUST_ANCHOR", lambda value: value["local_hash_bound_reproducibility"].__setitem__("external_trust_anchor", True), {"INVALID"}),
        ("DC46_LOCAL_BINDING_REMOVED", lambda value: value["local_hash_bound_reproducibility"]["bindings"].pop(), {"UNKNOWN"}),
        ("DC47_PARAMETER_CANONICAL_MATCH_FALSE", lambda value: value["parameter_space"]["canonical_contract"].__setitem__("canonical_contract_match", False), {"UNKNOWN"}),
        ("DC48_PARAMETER_SECTION_HASH_DRIFT", lambda value: value["parameter_space"]["canonical_contract"]["section_bindings"]["global_scan_axes"].__setitem__("actual_sha256", "0" * 64), {"UNKNOWN"}),
    ]
    results: List[Dict[str, Any]] = []
    for control_id, mutator, allowed_states in controls:
        probe = deepcopy(gate)
        mutator(probe)
        state, reason = classify_gate_candidate(probe, authority)
        results.append(
            {
                "id": control_id,
                "passed": state in allowed_states,
                "observed_state": state,
                "observed_reason": reason,
                "accepted_fail_closed_states": sorted(allowed_states),
            }
        )
    original_unchanged = render_json(gate) == original_bytes
    return {
        "controls_total": len(results),
        "controls_passed": sum(item["passed"] for item in results),
        "all_passed": all(item["passed"] for item in results),
        "original_gate_unchanged_after_deep_copy_mutations": original_unchanged,
        "controls": results,
    }


def check_entry(checks: List[Dict[str, Any]], check_id: str, passed: bool, evidence: Any) -> None:
    checks.append({"id": check_id, "passed": bool(passed), "evidence": evidence})


def build_validation(
    authority: Mapping[str, Any], semantics: Mapping[str, Any], parameter: Mapping[str, Any], qualification: Mapping[str, Any], frontier: Mapping[str, Any], gate: Mapping[str, Any]
) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    check_entry(checks, "SOURCE_HASHES_13_OF_13_MATCH", gate["source_hashes_all_match"] and len(gate["source_bindings"]) == 13, len(gate["source_bindings"]))
    hard = gate["route_b_v2_hard_negative_results_verbatim"]
    check_entry(
        checks,
        "ROUTE_B_V2_THREE_HARD_NEGATIVES_EXACT",
        hard["clearance_worst_mm"] == -11.9938 and hard["min_bend_radius_mm"] == 0.1 and hard["pinch_worst_mm"] == -11.9902,
        {key: hard[key] for key in ("clearance_worst_mm", "min_bend_radius_mm", "pinch_worst_mm")},
    )
    check_entry(checks, "ROUTE_B_REMAINS_REJECTED", gate["route_b_disposition"] == "REJECTED", gate["route_b_disposition"])
    qsum = qualification["summary"]
    check_entry(checks, "PREDICATE_POSITIVE_CONTROLS", qsum["positive_controls_passed"] == qsum["positive_controls_total"] == 11, qsum)
    check_entry(checks, "PREDICATE_NEGATIVE_CONTROLS", qsum["negative_controls_passed"] == qsum["negative_controls_total"] == 36, qsum)
    check_entry(
        checks,
        "FAILURE_SERIALIZATION_SCHEMA",
        semantics["failure_serialization"]["required_for_collision_or_pinch"] == ["state", "q", "segment", "point", "object_pair", "margin"],
        semantics["failure_serialization"]["required_for_collision_or_pinch"],
    )
    check_entry(checks, "NO_WHOLE_LINK_OR_INFINITE_EXEMPTION", "WHOLE_LINK" in semantics["finite_contact_volume_schema"]["forbidden_exemptions"] and "INFINITE_VOLUME" in semantics["finite_contact_volume_schema"]["forbidden_exemptions"], semantics["finite_contact_volume_schema"]["forbidden_exemptions"])
    check_entry(
        checks,
        "SEMANTICS_SCOPE_KIND_AND_SAMPLE_COVERAGE_SCHEMA",
        semantics["finite_contact_volume_schema"]["required_fields"]
        == ["object_id", "object_class", "scope_kind", "owner_segment", "bounds_min_mm", "bounds_max_mm"]
        and "Cartesian product" in semantics["finite_contact_volume_schema"]["requirements"][3],
        {
            "required_fields": semantics["finite_contact_volume_schema"]["required_fields"],
            "coverage_rule": semantics["finite_contact_volume_schema"]["requirements"][3],
        },
    )
    topology_ids = [item["id"] for item in parameter["topologies"]]
    check_entry(checks, "FOUR_MUTUALLY_EXCLUSIVE_TOPOLOGIES", topology_ids == ["RC-A", "RC-B", "RC-C", "RC-D"] and "Exactly one" in parameter["mutual_exclusion_rule"], topology_ids)
    check_entry(checks, "RC_D_REJECTED_PRIMARY", next(item["status"] for item in parameter["topologies"] if item["id"] == "RC-D") == "REJECTED_AS_PRIMARY_CONCEPT", "REJECTED_AS_PRIMARY_CONCEPT")
    check_entry(checks, "J4_BRANCHES_NOT_MERGED", "mutually exclusive" in parameter["joint_variable_schema"]["J4"]["branch_rule"], parameter["joint_variable_schema"]["J4"]["branch_rule"])
    check_entry(checks, "SCAN_AXES_NOT_KNOWN_VALUES", all(axis["selected_value"] is None for axis in parameter["global_scan_axes"]), parameter["global_scan_axes"])
    parameter_null_audit = audit_parameter_physical_nulls(parameter)
    check_entry(
        checks,
        "PARAMETER_PHYSICAL_NULL_CONTRACT",
        parameter_null_audit["all_required_physical_values_null"]
        and frontier.get("parameter_physical_null_audit") == parameter_null_audit
        and gate.get("parameter_space", {}).get("physical_null_contract") == parameter_null_audit,
        parameter_null_audit,
    )
    parameter_canonical_audit = audit_parameter_canonical_contract(parameter)
    check_entry(
        checks,
        "PARAMETER_FULL_CANONICAL_CONTRACT_HASH_BOUND",
        parameter_canonical_audit == EXPECTED_PARAMETER_CANONICAL_AUDIT
        and frontier.get("parameter_canonical_contract_audit") == parameter_canonical_audit
        and gate.get("parameter_space", {}).get("canonical_contract") == parameter_canonical_audit,
        parameter_canonical_audit,
    )
    frontier_nulls = frontier["physical_capacity_frontier"]
    check_entry(
        checks,
        "PHYSICAL_FRONTIER_ALL_REQUIRED_NULL",
        all(frontier_nulls[name]["value"] is None for name in ("D_max_geometry_mm", "R_path_min_mm", "deltaL_mm", "carrier_travel_mm")) and frontier_nulls["manufacturing_coordinates_mm"] is None,
        {name: (frontier_nulls[name]["value"] if isinstance(frontier_nulls[name], dict) else frontier_nulls[name]) for name in ("D_max_geometry_mm", "R_path_min_mm", "deltaL_mm", "carrier_travel_mm", "manufacturing_coordinates_mm")},
    )
    check_entry(checks, "NO_PHYSICAL_CANDIDATE_FOUND", frontier["candidate_found"] is False and frontier["physical_route_c_candidates_evaluated"] == 0, {"candidate_found": frontier["candidate_found"], "evaluated": frontier["physical_route_c_candidates_evaluated"]})
    check_entry(checks, "ODR42_MPI_CAD_HOLD", gate["upstream_gate_state"] == {"ODR42": "PENDING", "MPI_controlled": 0, "MPI_total": 8, "MPI_gate": "HOLD", "CAD_entry_gate": "HOLD", "CAD_entry_verdict": "ROUTE_C_PARAMETRIC_CAD_ENTRY_NOT_AUTHORIZED"}, gate["upstream_gate_state"])
    local_binding = gate["local_hash_bound_reproducibility"]
    check_entry(
        checks,
        "LOCAL_HASH_BOUND_REPRODUCIBILITY_SELF_CONSISTENCY",
        local_binding["binding_class"] == LOCAL_BINDING_CLASS
        and local_binding["external_trust_anchor"] is False
        and local_binding["authority_pin_count"] == 5
        and local_binding["all_match"] is True,
        {"binding_class": local_binding["binding_class"], "external_trust_anchor": local_binding["external_trust_anchor"], "all_match": local_binding["all_match"]},
    )
    check_entry(checks, "ALL_REQUIRED_HOLDS_RETAINED", set(authority["retained_holds"]) <= set(gate["retained_holds"]), gate["retained_holds"])
    state, reason = classify_gate_candidate(gate, authority)
    check_entry(checks, "GATE_CLASSIFIER_VALID_FAIL_CLOSED", state == "VALID_FAIL_CLOSED_GATE", {"state": state, "reason": reason})
    check_entry(checks, "EXACT_TERMINAL_VERDICT", gate["verdict"] == EXPECTED_VERDICT, gate["verdict"])
    check_entry(checks, "NO_AUTHORITY_UPGRADE", gate["next_stage_authorized"] is False and gate["cad_entry_authorized"] is False and qualification["authority_effect"].startswith("NONE"), {"next_stage_authorized": gate["next_stage_authorized"], "cad_entry_authorized": gate["cad_entry_authorized"]})
    check_entry(checks, "NO_CAD_MESH_OR_URDF_OUTPUTS", not any(path.suffix.lower() in {".fcstd", ".step", ".stp", ".stl", ".glb", ".urdf"} for path in PACKAGE.rglob("*")), "owned package has no CAD/mesh/URDF outputs")
    deep_controls = run_deep_copy_negative_controls(gate, authority)
    check_entry(checks, "DEEP_COPY_NEGATIVE_CONTROLS", deep_controls["all_passed"] and deep_controls["original_gate_unchanged_after_deep_copy_mutations"], {"passed": deep_controls["controls_passed"], "total": deep_controls["controls_total"]})
    parameter_null_controls = run_parameter_null_negative_controls(
        parameter,
        authority=authority,
        qualification=qualification,
        bindings=gate["source_bindings"],
    )
    check_entry(
        checks,
        "PARAMETER_NULL_NEGATIVE_CONTROLS",
        parameter_null_controls["all_passed"],
        {"passed": parameter_null_controls["controls_passed"], "total": parameter_null_controls["controls_total"]},
    )
    parameter_contract_controls = run_parameter_contract_negative_controls(
        parameter,
        authority=authority,
        qualification=qualification,
        bindings=gate["source_bindings"],
    )
    check_entry(
        checks,
        "PARAMETER_CANONICAL_CONTRACT_NEGATIVE_CONTROLS",
        parameter_contract_controls["all_passed"],
        {"passed": parameter_contract_controls["controls_passed"], "total": parameter_contract_controls["controls_total"]},
    )
    return {
        "schema": "ROUTE_C_PRECAD_PARAMETRIC_SEARCH_VALIDATION_V1",
        "generated_local": GENERATED_LOCAL,
        "validation_class": "DETERMINISTIC_CROSS_ENTRYPOINT_REBUILD_AND_SELF_CONSISTENCY_FAIL_CLOSED_AUDIT",
        "status": "PASS_VALIDATION_OF_NON_RELEASE_C1_5_DIAGNOSTIC" if all(item["passed"] for item in checks) else "FAIL",
        "checks_total": len(checks),
        "checks_passed": sum(item["passed"] for item in checks),
        "checks_failed": [item["id"] for item in checks if not item["passed"]],
        "checks": checks,
        "deep_copy_negative_controls": deep_controls,
        "parameter_null_negative_controls": parameter_null_controls,
        "parameter_contract_negative_controls": parameter_contract_controls,
        "byte_reproduction_contract": {
            "builder_option": "--check-only",
            "validator_option": "--check-only",
            "comparison": "EXACT_UTF8_BYTES",
            "timestamps": "FROZEN",
            "manifest_self_hash": "INTENTIONALLY_EXCLUDED_TO_AVOID_SELF_REFERENCE",
        },
        "validated_gate": gate["gate"],
        "validated_verdict": gate["verdict"],
        "authority_effect": "NONE__VALIDATION_PASS_DOES_NOT_AUTHORIZE_CAD_OR_PROVE_PHYSICAL_FEASIBILITY",
    }


def manifest_entry(name: str, path: Path, role: str, data: bytes | None = None) -> Dict[str, Any]:
    content = data if data is not None else path.read_bytes()
    return {"name": name, "path": rel(path), "sha256": sha256_bytes(content), "bytes": len(content), "role": role}


def build_all() -> Tuple[Dict[Path, bytes], Dict[str, Any]]:
    authority = load_json(AUTHORITY_PATH)
    semantics = load_json(SEMANTICS_PATH)
    parameter = load_json(PARAMETER_PATH)
    bindings = source_bindings(authority)
    kernel = load_kernel()
    qualification = kernel.run_qualification()
    qualification.update(
        {
            "generated_local": GENERATED_LOCAL,
            "semantics_path": rel(SEMANTICS_PATH),
            "semantics_sha256": sha256_file(SEMANTICS_PATH),
            "kernel_path": rel(KERNEL_PATH),
            "kernel_sha256": sha256_file(KERNEL_PATH),
            "source_hashes_all_match": all(item["hash_match"] for item in bindings),
        }
    )
    frontier = build_frontier(authority, parameter, qualification, bindings)
    gate = build_gate(authority, parameter, qualification, frontier, bindings)
    validation = build_validation(authority, semantics, parameter, qualification, frontier, gate)
    generated_payloads = {
        QUALIFICATION_PATH: render_json(qualification),
        FRONTIER_PATH: render_json(frontier),
        GATE_PATH: render_json(gate),
        VALIDATION_PATH: render_json(validation),
    }
    source_entries = [
        manifest_entry("authority_contract", AUTHORITY_PATH, "PREREGISTERED_SOURCE"),
        manifest_entry("contact_and_guide_semantics", SEMANTICS_PATH, "PREREGISTERED_SOURCE"),
        manifest_entry("predicate_kernel", KERNEL_PATH, "EXECUTABLE_SOURCE"),
        manifest_entry("parameter_space", PARAMETER_PATH, "PREREGISTERED_SOURCE"),
        manifest_entry("builder", Path(__file__).resolve(), "EXECUTABLE_SOURCE"),
        manifest_entry("validator", PACKAGE / "99_tools/validate_route_c_precad_parametric_search.py", "EXECUTABLE_SOURCE"),
        manifest_entry("readme", PACKAGE / "README.md", "HUMAN_NAVIGATION"),
    ]
    output_entries = [
        manifest_entry("predicate_qualification", QUALIFICATION_PATH, "GENERATED_EVIDENCE", generated_payloads[QUALIFICATION_PATH]),
        manifest_entry("geometric_capacity_frontier", FRONTIER_PATH, "GENERATED_EVIDENCE", generated_payloads[FRONTIER_PATH]),
        manifest_entry("gate", GATE_PATH, "MACHINE_GATE", generated_payloads[GATE_PATH]),
        manifest_entry("validation", VALIDATION_PATH, "MACHINE_VALIDATION", generated_payloads[VALIDATION_PATH]),
    ]
    manifest = {
        "schema": "ROUTE_C_PRECAD_PARAMETRIC_SEARCH_OUTPUT_MANIFEST_V1",
        "generated_local": GENERATED_LOCAL,
        "status": "FROZEN_NON_RELEASE_C1_5_DIAGNOSTIC_PACKAGE",
        "source_hash_bindings": bindings,
        "package_sources": source_entries,
        "generated_outputs": output_entries,
        "output_manifest_self_hash": None,
        "self_hash_policy": "SELF_HASH_EXCLUDED_TO_AVOID_RECURSION",
        "gate": gate["gate"],
        "verdict": gate["verdict"],
        "next_stage_authorized": False,
    }
    generated_payloads[MANIFEST_PATH] = render_json(manifest)
    return generated_payloads, manifest


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="write deterministic generated outputs")
    mode.add_argument("--check-only", action="store_true", help="compare current outputs with an in-memory rebuild")
    parser.add_argument("--summary", action="store_true", help="print a compact JSON summary")
    args = parser.parse_args(argv)
    outputs, _ = build_all()
    mismatches: List[str] = []
    if args.write:
        for path, data in outputs.items():
            atomic_write(path, data)
    else:
        for path, expected in outputs.items():
            actual = path.read_bytes() if path.is_file() else None
            if actual != expected:
                mismatches.append(rel(path))
    summary = {
        "mode": "WRITE" if args.write else "CHECK_ONLY",
        "outputs_total": len(outputs),
        "byte_mismatches": mismatches,
        "source_hashes_all_match": all(
            binding["hash_match"] for binding in load_json(GATE_PATH)["source_bindings"]
        ) if GATE_PATH.is_file() else False,
        "gate": load_json(GATE_PATH)["gate"] if GATE_PATH.is_file() else None,
        "verdict": load_json(GATE_PATH)["verdict"] if GATE_PATH.is_file() else None,
    }
    if args.summary or mismatches:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if not mismatches and summary["source_hashes_all_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
