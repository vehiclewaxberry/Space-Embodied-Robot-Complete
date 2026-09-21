#!/usr/bin/env python3
"""Validate exact reproduction and fail-closed controls for Route-C C1.5."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, MutableMapping, Sequence, Tuple

sys.dont_write_bytecode = True

PACKAGE = Path(__file__).resolve().parents[1]
BUILDER_PATH = PACKAGE / "99_tools/build_route_c_precad_parametric_search.py"
INDEPENDENT_EXPECTED_PARAMETER_CANONICAL_SHA256 = "271318F10115ED212A19A038BFFCA7D0ADDF77C74D4D54DD08D057F9FE991F3B"
INDEPENDENT_EXPECTED_PARAMETER_SECTION_SHA256 = {
    "top_level_metadata": "D7CF14632BB89686094A8AA690C935767DF95A5234576CD71EAD40767F1D4E74",
    "topologies": "7F424885605A3C17114AB7730280B52ADA0321D18625C6A681036D94682D2270",
    "global_scan_axes": "23FF00E4A1323016D99F0A6B71CC27E1C59F8F3FB546F274B3DCD564B04B6411",
    "joint_variable_schema": "A47825E22CEC54ACF21CE6C072A4CCEAFC055DD8C94427E79126B0CE361AB79E",
    "unknown_physical_inputs": "687A838AE36E939CC9C57209D228E9C50E5CF232F8D2B983B80A195DFFDE4EE2",
    "search_output_rules": "0F320DEE441A1CDC4C3F29D03D319ABAB59CB4A5A8D753BF0C574C4BBF483E79",
}


def load_builder() -> Any:
    spec = importlib.util.spec_from_file_location("route_c_precad_builder", BUILDER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Route-C C1.5 builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def independent_canonical_sha256(payload: Any) -> str:
    data = (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    return hashlib.sha256(data).hexdigest().upper()


def independent_parameter_canonical_audit(parameter: Mapping[str, Any]) -> Dict[str, Any]:
    section_names = (
        "topologies",
        "global_scan_axes",
        "joint_variable_schema",
        "unknown_physical_inputs",
        "search_output_rules",
    )
    sections: Dict[str, Any] = {
        "top_level_metadata": {key: value for key, value in parameter.items() if key not in section_names}
    }
    for name in section_names:
        sections[name] = parameter.get(name, "MISSING_SECTION")
    section_matches = {
        name: independent_canonical_sha256(sections[name]) == expected
        for name, expected in INDEPENDENT_EXPECTED_PARAMETER_SECTION_SHA256.items()
    }
    actual = independent_canonical_sha256(parameter)
    return {
        "expected_canonical_sha256": INDEPENDENT_EXPECTED_PARAMETER_CANONICAL_SHA256,
        "actual_canonical_sha256": actual,
        "canonical_contract_match": actual == INDEPENDENT_EXPECTED_PARAMETER_CANONICAL_SHA256 and all(section_matches.values()),
        "section_matches": section_matches,
    }


def independent_parameter_null_audit(parameter: Mapping[str, Any]) -> Dict[str, Any]:
    """Independent recursive check; deliberately does not call the builder audit."""
    violations: List[str] = []
    axes = parameter.get("global_scan_axes")
    if not isinstance(axes, list):
        violations.append("global_scan_axes:MISSING")
    else:
        for index, axis in enumerate(axes):
            if not isinstance(axis, Mapping):
                violations.append(f"global_scan_axes[{index}]:INVALID")
                continue
            for field in ("selected_value", "uncertainty"):
                if axis.get(field) is not None:
                    violations.append(f"global_scan_axes[{index}].{field}")

    def walk(value: Any, path: str) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                child_path = f"{path}.{key}"
                if key == "physical_value" and child is not None:
                    violations.append(child_path)
                else:
                    walk(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")

    walk(parameter.get("joint_variable_schema"), "joint_variable_schema")
    unknowns = parameter.get("unknown_physical_inputs")
    if not isinstance(unknowns, Mapping):
        violations.append("unknown_physical_inputs:MISSING")
    else:
        for key, value in unknowns.items():
            if value is not None:
                violations.append(f"unknown_physical_inputs.{key}")
    rules = parameter.get("search_output_rules")
    if not isinstance(rules, Mapping):
        violations.append("search_output_rules:MISSING")
    else:
        for key in ("D_max_geometry_mm", "R_path_min_mm", "deltaL_mm", "carrier_travel_mm"):
            if rules.get(key) is not None:
                violations.append(f"search_output_rules.{key}")
        if rules.get("candidate_found_allowed_without_physical_guide_volumes") is not False:
            violations.append("search_output_rules.candidate_found_allowed_without_physical_guide_volumes")
    violations.sort()
    return {"all_required_physical_values_null": not violations, "violations": violations}


def independent_parameter_null_negative_controls(parameter: Mapping[str, Any]) -> Dict[str, Any]:
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
    for control_id, mutate in controls:
        probe = deepcopy(parameter)
        mutate(probe)
        audit = independent_parameter_null_audit(probe)
        results.append({"id": control_id, "passed": audit["all_required_physical_values_null"] is False, "violations": audit["violations"]})
    return {
        "controls_total": len(results),
        "controls_passed": sum(item["passed"] for item in results),
        "all_passed": all(item["passed"] for item in results),
        "controls": results,
    }


def independent_parameter_contract_negative_controls(parameter: Mapping[str, Any]) -> Dict[str, Any]:
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
    for control_id, mutate in controls:
        probe = deepcopy(parameter)
        mutate(probe)
        audit = independent_parameter_canonical_audit(probe)
        results.append({"id": control_id, "passed": audit["canonical_contract_match"] is False, "audit": audit})
    return {
        "controls_total": len(results),
        "controls_passed": sum(item["passed"] for item in results),
        "all_passed": all(item["passed"] for item in results),
        "controls": results,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true", required=True, help="perform non-mutating validation")
    parser.add_argument("--compact", action="store_true", help="print compact JSON")
    args = parser.parse_args(argv)
    builder = load_builder()
    expected_outputs, expected_manifest = builder.build_all()
    checks: List[Dict[str, Any]] = []

    def add(check_id: str, passed: bool, evidence: Any) -> None:
        checks.append({"id": check_id, "passed": bool(passed), "evidence": evidence})

    byte_mismatches: List[str] = []
    for path, expected in expected_outputs.items():
        actual = path.read_bytes() if path.is_file() else None
        if actual != expected:
            byte_mismatches.append(builder.rel(path))
    add("EXACT_BYTE_REBUILD", not byte_mismatches, byte_mismatches)

    gate = builder.load_json(builder.GATE_PATH)
    authority = builder.load_json(builder.AUTHORITY_PATH)
    state, reason = builder.classify_gate_candidate(gate, authority)
    add("CROSS_ENTRYPOINT_GATE_CLASSIFICATION", state == "VALID_FAIL_CLOSED_GATE", {"state": state, "reason": reason})
    add("EXACT_GATE_AND_VERDICT", gate["gate"] == "UNKNOWN_FAIL_CLOSED" and gate["verdict"] == builder.EXPECTED_VERDICT, {"gate": gate["gate"], "verdict": gate["verdict"]})
    add("SOURCE_HASH_PINS", all(item["hash_match"] for item in gate["source_bindings"]), {item["name"]: item["hash_match"] for item in gate["source_bindings"]})

    deep_controls = builder.run_deep_copy_negative_controls(gate, authority)
    add(
        "DEEP_COPY_NEGATIVE_CONTROLS",
        deep_controls["all_passed"] and deep_controls["original_gate_unchanged_after_deep_copy_mutations"],
        {"passed": deep_controls["controls_passed"], "total": deep_controls["controls_total"]},
    )

    qualification = builder.load_json(builder.QUALIFICATION_PATH)
    summary = qualification["summary"]
    add("PREDICATE_POSITIVE_CONTROLS", summary["positive_controls_passed"] == summary["positive_controls_total"] == 11, summary)
    add("PREDICATE_NEGATIVE_CONTROLS", summary["negative_controls_passed"] == summary["negative_controls_total"] == 36, summary)

    parameter = builder.load_json(builder.PARAMETER_PATH)
    parameter_null_audit = independent_parameter_null_audit(parameter)
    add("INDEPENDENT_PARAMETER_PHYSICAL_NULL_AUDIT", parameter_null_audit["all_required_physical_values_null"], parameter_null_audit)
    independent_parameter_controls = independent_parameter_null_negative_controls(parameter)
    add(
        "INDEPENDENT_PARAMETER_NULL_NEGATIVE_CONTROLS",
        independent_parameter_controls["all_passed"],
        {"passed": independent_parameter_controls["controls_passed"], "total": independent_parameter_controls["controls_total"]},
    )
    parameter_canonical_audit = independent_parameter_canonical_audit(parameter)
    add("INDEPENDENT_PARAMETER_CANONICAL_HASH_AUDIT", parameter_canonical_audit["canonical_contract_match"], parameter_canonical_audit)
    independent_parameter_contract_controls = independent_parameter_contract_negative_controls(parameter)
    add(
        "INDEPENDENT_PARAMETER_CANONICAL_NEGATIVE_CONTROLS",
        independent_parameter_contract_controls["all_passed"],
        {"passed": independent_parameter_contract_controls["controls_passed"], "total": independent_parameter_contract_controls["controls_total"]},
    )

    semantics = builder.load_json(builder.SEMANTICS_PATH)
    add(
        "SEMANTICS_SCOPE_KIND_AND_SAMPLE_COVERAGE_SCHEMA",
        semantics["finite_contact_volume_schema"]["required_fields"]
        == ["object_id", "object_class", "scope_kind", "owner_segment", "bounds_min_mm", "bounds_max_mm"]
        and any("Cartesian product" in item for item in semantics["finite_contact_volume_schema"]["requirements"]),
        semantics["finite_contact_volume_schema"]["required_fields"],
    )

    frontier = builder.load_json(builder.FRONTIER_PATH)
    physical = frontier["physical_capacity_frontier"]
    null_values = {
        "D_max_geometry_mm": physical["D_max_geometry_mm"]["value"],
        "R_path_min_mm": physical["R_path_min_mm"]["value"],
        "deltaL_mm": physical["deltaL_mm"]["value"],
        "carrier_travel_mm": physical["carrier_travel_mm"]["value"],
        "manufacturing_coordinates_mm": physical["manufacturing_coordinates_mm"],
    }
    add("PHYSICAL_CAPACITY_MEASURANDS_NULL", all(value is None for value in null_values.values()), null_values)
    add(
        "FRONTIER_PARAMETER_NULL_AUDIT_BOUND",
        frontier.get("parameter_physical_null_audit", {}).get("all_required_physical_values_null") is True
        and frontier.get("parameter_physical_null_audit", {}).get("violations") == [],
        frontier.get("parameter_physical_null_audit"),
    )
    add(
        "FRONTIER_PARAMETER_CANONICAL_AUDIT_BOUND",
        frontier.get("parameter_canonical_contract_audit", {}).get("canonical_contract_match") is True
        and frontier.get("parameter_canonical_contract_audit", {}).get("actual_canonical_sha256")
        == INDEPENDENT_EXPECTED_PARAMETER_CANONICAL_SHA256,
        frontier.get("parameter_canonical_contract_audit"),
    )
    add("NO_CANDIDATE_FOUND", frontier["candidate_found"] is False and frontier["physical_route_c_candidates_evaluated"] == 0, {"candidate_found": frontier["candidate_found"], "evaluated": frontier["physical_route_c_candidates_evaluated"]})
    add("ROUTE_B_V2_HARD_NEGATIVES", gate["route_b_v2_hard_negative_results_verbatim"]["clearance_worst_mm"] == -11.9938 and gate["route_b_v2_hard_negative_results_verbatim"]["min_bend_radius_mm"] == 0.1 and gate["route_b_v2_hard_negative_results_verbatim"]["pinch_worst_mm"] == -11.9902, gate["route_b_v2_hard_negative_results_verbatim"])
    add("ROUTE_B_REJECTED", gate["route_b_disposition"] == "REJECTED", gate["route_b_disposition"])
    add("ALL_HOLDS_RETAINED", set(authority["retained_holds"]) <= set(gate["retained_holds"]), gate["retained_holds"])
    local_mismatches: List[str] = []
    local_pins = authority.get("local_hash_bound_sources", [])
    for pin in local_pins:
        path = builder.ROOT / pin["path"]
        if not path.is_file() or builder.sha256_file(path) != pin["sha256"]:
            local_mismatches.append(pin["name"])
    local_boundary = authority.get("local_hash_binding_boundary", {})
    add(
        "LOCAL_HASH_BOUND_SELF_CONSISTENCY_NO_EXTERNAL_TRUST_ANCHOR",
        len(local_pins) == 5
        and not local_mismatches
        and local_boundary.get("binding_class") == builder.LOCAL_BINDING_CLASS
        and local_boundary.get("external_trust_anchor") is False,
        {"pin_count": len(local_pins), "mismatches": local_mismatches, "external_trust_anchor": local_boundary.get("external_trust_anchor")},
    )
    add("NO_AUTHORITY_UPGRADE", gate["next_stage_authorized"] is False and gate["cad_entry_authorized"] is False and gate["candidate_found"] is False, {"next_stage_authorized": gate["next_stage_authorized"], "cad_entry_authorized": gate["cad_entry_authorized"], "candidate_found": gate["candidate_found"]})

    manifest = builder.load_json(builder.MANIFEST_PATH)
    manifest_mismatches: List[str] = []
    for entry in manifest["package_sources"] + manifest["generated_outputs"]:
        path = builder.ROOT / entry["path"]
        if not path.is_file() or builder.sha256_file(path) != entry["sha256"] or path.stat().st_size != entry["bytes"]:
            manifest_mismatches.append(entry["name"])
    add("MANIFEST_HASH_AND_SIZE_BINDINGS", not manifest_mismatches, manifest_mismatches)
    add("MANIFEST_SELF_HASH_EXCLUDED", manifest["output_manifest_self_hash"] is None and manifest["self_hash_policy"] == "SELF_HASH_EXCLUDED_TO_AVOID_RECURSION", manifest["self_hash_policy"])

    cache_paths = sorted(builder.rel(path) for path in PACKAGE.rglob("__pycache__"))
    pyc_paths = sorted(builder.rel(path) for path in PACKAGE.rglob("*.pyc"))
    add("NO_PYTHON_CACHE", not cache_paths and not pyc_paths, {"cache_dirs": cache_paths, "pyc_files": pyc_paths})
    forbidden_outputs = sorted(
        builder.rel(path)
        for path in PACKAGE.rglob("*")
        if path.is_file() and path.suffix.lower() in {".fcstd", ".step", ".stp", ".stl", ".glb", ".urdf"}
    )
    add("NO_CAD_MESH_OR_URDF_OUTPUT", not forbidden_outputs, forbidden_outputs)

    report = {
        "schema": "ROUTE_C_PRECAD_PARAMETRIC_SEARCH_RUNTIME_VALIDATION_V1",
        "mode": "CHECK_ONLY",
        "status": "PASS" if all(item["passed"] for item in checks) else "FAIL",
        "checks_total": len(checks),
        "checks_passed": sum(item["passed"] for item in checks),
        "checks_failed": [item["id"] for item in checks if not item["passed"]],
        "checks": checks,
        "deep_copy_negative_controls": deep_controls,
        "independent_parameter_null_negative_controls": independent_parameter_controls,
        "independent_parameter_contract_negative_controls": independent_parameter_contract_controls,
        "gate": gate["gate"],
        "verdict": gate["verdict"],
        "manifest_gate": expected_manifest["gate"],
        "authority_effect": "NONE__RUNTIME_VALIDATION_PASS_DOES_NOT_AUTHORIZE_CAD_OR_PHYSICAL_FEASIBILITY",
    }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=None if args.compact else 2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
