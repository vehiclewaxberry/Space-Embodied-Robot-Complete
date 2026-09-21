"""Independent fail-closed validation for Mechanical Loop Continuation V5."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Mapping


sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parents[4]
ECR_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ECR_ROOT / "15_loop_continuation_v5"
GATE_PATH = OUTPUT_ROOT / "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V5.json"
BRIEF_PATH = OUTPUT_ROOT / "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_BRIEF_V5.md"
MANIFEST_PATH = (
    OUTPUT_ROOT / "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_OUTPUT_MANIFEST_V5.json"
)
VALIDATION_PATH = (
    OUTPUT_ROOT / "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_VALIDATION_V5.json"
)
BUILDER_PATH = Path(__file__).resolve().with_name(
    "build_mechanical_loop_continuation_v5.py"
)
GENERATED_LOCAL = "2026-08-24T00:05:00+08:00"

E21_EVALUATED_STATE = "m7_r2_arm_placement_consumption_semantics_evaluated"
ROUTE_C_FROZEN_STATE = (
    "route_c_precad_predicate_qualification_and_parameter_space_frozen"
)
PLACEMENT_STATE = (
    "M7_R2_ARM_PLACEMENT_CONSUMPTION_SEMANTICS_EVALUATED__"
    "MIXED_CONTEXT_DETECTED__SINGLE_CONSUMPTION_RULE_UNRESOLVED"
)
EXPECTED_VERDICT = (
    "MECHANICAL_LOOP_ENGINEERING_CONTINUES_WITH_CURRENT_R2_RIGID_ARM_"
    "PLACEMENT_SENSITIVITY_FIXED_BASE_ROM_AND_ROUTE_C_PRECAD_METHOD_"
    "CONTRACT_CLOSED__SINGLE_PLACEMENT_R2_FULL_FLEX_E15_HARNESS_PHYSICAL_"
    "CAPACITY_CONTACT_ATTACHED_CAD_MISSION_PRODUCTION_AND_FLIGHT_HOLD"
)
NULL_CAPACITY_FIELDS = (
    "D_max_geometry_mm",
    "R_path_min_mm",
    "deltaL_mm",
    "carrier_travel_mm",
    "manufacturing_coordinates_mm",
)
ROUTE_C_EXPECTED_VERDICT = (
    "UNKNOWN_FAIL_CLOSED__PREDICATE_QUALIFICATION_AND_PARAMETER_SPACE_"
    "FROZEN__PHYSICAL_GUIDE_VOLUMES_CAD_BRANCH_ODR42_MPI_VENDOR_MISSION_"
    "AND_RELEASE_HOLD"
)
ROUTE_C_RETAINED_HOLDS = [
    "HOLD_ODR42_PENDING",
    "HOLD_MPI_0_OF_8_CONTROLLED",
    "HOLD_ROUTE_C_CAD_ENTRY",
    "HOLD_PHYSICAL_GUIDE_VOLUMES_ABSENT",
    "HOLD_HN_02_HN_03_ABSENT",
    "HOLD_PHYSICAL_CAD_BRANCH_ABSENT",
    "HOLD_FULL_RANGE",
    "HOLD_MISSION_TRAJECTORY_AUTHORITY_AND_COVERAGE",
    "HOLD_VENDOR_CABLE_CONNECTOR_BEND_AND_FLEX_LIFE",
    "HOLD_MASS_CG_INERTIA",
    "HOLD_RESTORING_TORQUE",
    "HOLD_PRODUCTION_DYNAMICS",
    "HOLD_PHYSICAL_CONTACT_RL",
    "HOLD_HARDWARE_MOTION_AND_TEST",
    "HOLD_FLIGHT_AND_QUALIFICATION_RELEASE",
]
EXPECTED_INPUT_NAMES = {
    "loop_v4_gate",
    "loop_v4_brief",
    "loop_v4_manifest",
    "loop_v4_validation",
    "e21_gate",
    "e21_validation",
    "e21_manifest",
    "route_c_precad_gate",
    "route_c_precad_validation",
    "route_c_precad_manifest",
}
EXPECTED_SCRIPT_NAMES = {
    "build_mechanical_loop_continuation_v5",
    "validate_mechanical_loop_continuation_v5",
}
EXPECTED_GATE_TOP_LEVEL_KEYS = {
    "schema",
    "generated_local",
    "authority_scope",
    "decision_rule",
    "fail_closed_invariants",
    "input_bindings",
    "facts",
    "facts_total",
    "facts_confirmed",
    "state_transition",
    "current_release",
    "m7_r2_arm_placement_consumption",
    "fixed_base_r2_rom_boundary",
    "route_c_precad_method_contract",
    "preserved_holds",
    "blocking_fronts",
    "shortest_engineering_sequence",
    "verdict",
    "gate",
    "testing_pass_grants_authority",
    "unknown_uncertainties_zero_filled",
    "next_stage_authorized",
    "release_credit",
    "released_segments",
    "required_owner_statement",
    "prohibition",
}
EXPECTED_MANIFEST_TOP_LEVEL_KEYS = {
    "schema",
    "generated_local",
    "outputs",
    "sources",
    "output_count",
    "source_count",
    "validation_report_excluded_to_avoid_self_hash",
    "self_hash_policy",
    "verdict",
    "gate",
    "next_stage_authorized",
    "release_credit",
    "released_segments",
}
EXPECTED_AUTHORITY_SCOPE = (
    "HASH_BOUND_CURRENT_R2_DEPLOYED_LOCKED_RIGID_ARM_PLACEMENT_"
    "SENSITIVITY_FIXED_BASE_LEAF_ONLY_ROM_AND_ROUTE_C_C15_PRECAD_METHOD_"
    "CONTRACT__NONSELECTING_NONRELEASE_PRE_FULL_FLEX_PRE_CONTACT_PRE_"
    "ATTACHED_PRE_CAD_PRE_MISSION_PRE_PRODUCTION"
)
EXPECTED_DECISION_RULE = (
    "Authority > later evidence > independent reproduction > opinion"
)
EXPECTED_REQUIRED_OWNER_STATEMENT = (
    "批准 ODR-42：APPROVE_BOUNDED_DETAILED_DESIGN；冻结 accepted URDF 与 Solar "
    "R2；完成 MPI-01..MPI-08 后方可生成独立版本 Route-C CAD。"
)
EXPECTED_PROHIBITION = (
    "No single arm-placement rule, R2 full-flex, physical harness capacity, "
    "contact, attached-target recovery, Route-C CAD, mission, production, "
    "hardware, manufacturing, qualification, or flight claim from V5."
)

# Canonical JSON hashes bind all nested keys, values, list order and evidence.
EXPECTED_CANONICAL_HASHES = {
    "v5_gate": "6270B4F96D63986F437A4F8AF25A0357B0B2132C7E6073665DB79B8A489E60DA",
    "fail_closed_invariants": "81A4311C6764194488609E6AC087E8A51A66F4EA45CBA08DB3ED80D63793A965",
    "facts": "448E5EEA39CD8508423D5E2B1A7CFA684DF28DAC931A8665FAEA9B05F4C48295",
    "preserved_holds": "33A43553FEC6F113BDDC38B2C571A190914B6094A92764AA2A431B4723F838C3",
    "blocking_fronts": "412EA8A2C3F31D9D85E82026740011058D5D7B9F9EA8C72C904EAA2E9EF0B170",
    "shortest_engineering_sequence": "30391F35E8A3229BB1AEAE0BDF764E1F4813D65EEF1918CF0B97741103C3BD2E",
    "m7_r2_arm_placement_consumption": "9605F039540E9DD7055C56DB4C7953054BED363A61DC7132CAAFF96804502C7B",
    "fixed_base_r2_rom_boundary": "7BE3E035DC541368B9930BAA2C83D34583B40AAC382860EC65F7D73871585369",
    "route_c_precad_method_contract": "7BFF5B32BB857D0151A66152E717740D9E7EB17171882F362EF5E8ADA7EA4ACC",
    "state_transition": "67461273CF3382E0780472223279129AA875AF5D342C7F2CC65C91F7E3439E83",
    "current_release": "8BC4423D0AD089AE3C6983A397838F59BD9FAD62CE892FC4E51B0273CF7C0CB3",
    "loop_v4_gate": "7DE10ECA81A2009B791E13E14D1FE49C569DFB151DC9665F34FDE638AD355274",
    "loop_v4_manifest": "E4D89DBEBD6771A814F8EDC0C0E7D2433B0FFC617EA51E99C13B4E350AE14C10",
    "loop_v4_validation": "D1E157DA14F25C1CAD799A56B338C0A258C57D164F90333C717ECF9B888B27A8",
    "e21_gate": "0D52D2D9AC9C6C5A8B23E625E52F3C75FFC240F44008EF9026F4B20C139A3EF8",
    "e21_validation": "7829C185F68B32CFDE4A579D996578FDF1721AD4622464C991D72B0E40C920AB",
    "e21_manifest": "2184C8D3CF3794F6A8B31660BEFCCE2591C9AD00CCC881B697C6264BCA723010",
    "route_c_precad_gate": "A25EEA9C3ABE21EEAF0A9AD09E291E872CA2F34F5F524630B4EBF41763A4DD31",
    "route_c_precad_validation": "CC114B10BC7B243ED119746FE15E5C8C851C930074D9F07EFC4F7B1CBE578603",
    "route_c_precad_manifest": "D580F778BA16B3731545950B3E271EFBD3D0AC248D6AFC689E8E109DE697F6D0",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode("utf-8")


def canonical_hash(value: Any) -> str:
    data = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest().upper()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_builder() -> ModuleType:
    spec = importlib.util.spec_from_file_location("loop_v5_builder", BUILDER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load V5 builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def values_for_key(node: Any, key: str) -> list[Any]:
    values: list[Any] = []
    if isinstance(node, Mapping):
        for candidate_key, value in node.items():
            if candidate_key == key:
                values.append(value)
            values.extend(values_for_key(value, key))
    elif isinstance(node, list):
        for value in node:
            values.extend(values_for_key(value, key))
    return values


def set_first_key(node: Any, key: str, value: Any) -> bool:
    if isinstance(node, dict):
        if key in node:
            node[key] = value
            return True
        return any(set_first_key(child, key, value) for child in node.values())
    if isinstance(node, list):
        return any(set_first_key(child, key, value) for child in node)
    return False


def criterion(gate: Mapping[str, Any], criterion_id: str) -> Mapping[str, Any]:
    matches = [item for item in gate["criteria"] if item.get("id") == criterion_id]
    if len(matches) != 1:
        raise KeyError(criterion_id)
    return matches[0]


def source_bundle(gate: Mapping[str, Any], manifest: Mapping[str, Any]) -> dict[str, Any]:
    by_name = {item["name"]: item for item in gate["input_bindings"]}

    def source(name: str) -> Any:
        return load(PROJECT_ROOT / by_name[name]["path"])

    return {
        "gate": gate,
        "manifest": manifest,
        "v4": source("loop_v4_gate"),
        "v4_manifest": source("loop_v4_manifest"),
        "v4_validation": source("loop_v4_validation"),
        "e21": source("e21_gate"),
        "e21_validation": source("e21_validation"),
        "e21_manifest": source("e21_manifest"),
        "route": source("route_c_precad_gate"),
        "route_validation": source("route_c_precad_validation"),
        "route_manifest": source("route_c_precad_manifest"),
    }


def gate_safe(bundle: Mapping[str, Any]) -> bool:
    """One unified fail-closed predicate used by every mutation control."""

    try:
        gate = bundle["gate"]
        manifest = bundle["manifest"]
        v4 = bundle["v4"]
        v4_manifest = bundle["v4_manifest"]
        v4_validation = bundle["v4_validation"]
        e21 = bundle["e21"]
        e21_validation = bundle["e21_validation"]
        e21_manifest = bundle["e21_manifest"]
        route = bundle["route"]
        route_validation = bundle["route_validation"]
        route_manifest = bundle["route_manifest"]

        if set(gate) != EXPECTED_GATE_TOP_LEVEL_KEYS:
            return False
        if canonical_hash(gate) != EXPECTED_CANONICAL_HASHES["v5_gate"]:
            return False
        if gate.get("generated_local") != GENERATED_LOCAL:
            return False
        if gate.get("authority_scope") != EXPECTED_AUTHORITY_SCOPE:
            return False
        if gate.get("decision_rule") != EXPECTED_DECISION_RULE:
            return False
        if gate.get("required_owner_statement") != EXPECTED_REQUIRED_OWNER_STATEMENT:
            return False
        if gate.get("prohibition") != EXPECTED_PROHIBITION:
            return False
        for section in (
            "fail_closed_invariants",
            "facts",
            "preserved_holds",
            "blocking_fronts",
            "shortest_engineering_sequence",
            "m7_r2_arm_placement_consumption",
            "fixed_base_r2_rom_boundary",
            "route_c_precad_method_contract",
            "state_transition",
            "current_release",
        ):
            if canonical_hash(gate.get(section)) != EXPECTED_CANONICAL_HASHES[section]:
                return False
        if any(
            set(fact) != {"id", "name", "observed", "evidence"}
            for fact in gate.get("facts", [])
        ):
            return False
        if (
            canonical_hash(v4) != EXPECTED_CANONICAL_HASHES["loop_v4_gate"]
            or canonical_hash(v4_manifest)
            != EXPECTED_CANONICAL_HASHES["loop_v4_manifest"]
            or canonical_hash(v4_validation)
            != EXPECTED_CANONICAL_HASHES["loop_v4_validation"]
            or canonical_hash(e21) != EXPECTED_CANONICAL_HASHES["e21_gate"]
            or canonical_hash(e21_validation)
            != EXPECTED_CANONICAL_HASHES["e21_validation"]
            or canonical_hash(e21_manifest)
            != EXPECTED_CANONICAL_HASHES["e21_manifest"]
            or canonical_hash(route)
            != EXPECTED_CANONICAL_HASHES["route_c_precad_gate"]
            or canonical_hash(route_validation)
            != EXPECTED_CANONICAL_HASHES["route_c_precad_validation"]
            or canonical_hash(route_manifest)
            != EXPECTED_CANONICAL_HASHES["route_c_precad_manifest"]
        ):
            return False

        if gate.get("schema") != "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V5":
            return False
        if gate.get("verdict") != EXPECTED_VERDICT or gate.get("gate") != "HOLD":
            return False
        if gate.get("next_stage_authorized") is not False:
            return False
        if gate.get("release_credit") is not False:
            return False
        if gate.get("testing_pass_grants_authority") is not False:
            return False
        if gate.get("unknown_uncertainties_zero_filled") is not False:
            return False
        if gate.get("released_segments") != 0:
            return False
        if gate.get("facts_total") != 12 or gate.get("facts_confirmed") != 12:
            return False
        if len(gate.get("facts", [])) != 12:
            return False
        if any(fact.get("observed") is not True for fact in gate["facts"]):
            return False
        if [fact.get("id") for fact in gate["facts"]] != [
            f"LC5-{index:02d}" for index in range(1, 13)
        ]:
            return False

        bindings = gate.get("input_bindings", [])
        if len(bindings) != len(EXPECTED_INPUT_NAMES):
            return False
        by_name = {item.get("name"): item for item in bindings}
        if set(by_name) != EXPECTED_INPUT_NAMES:
            return False
        if any(
            set(item) != {"name", "path", "sha256", "bytes"}
            for item in bindings
        ):
            return False
        if any(
            not item.get("path")
            or not item.get("sha256")
            or len(item["sha256"]) != 64
            or item.get("bytes", 0) <= 0
            for item in bindings
        ):
            return False

        if set(manifest) != EXPECTED_MANIFEST_TOP_LEVEL_KEYS:
            return False
        if manifest.get("schema") != (
            "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_OUTPUT_MANIFEST_V5"
        ):
            return False
        if (
            manifest.get("generated_local") != GENERATED_LOCAL
            or manifest.get("verdict") != EXPECTED_VERDICT
            or manifest.get("gate") != "HOLD"
            or manifest.get("next_stage_authorized") is not False
            or manifest.get("release_credit") is not False
            or manifest.get("released_segments") != 0
            or manifest.get("validation_report_excluded_to_avoid_self_hash")
            is not True
            or manifest.get("self_hash_policy")
            != "VALIDATION_REPORT_EXCLUDED_TO_AVOID_SELF_REFERENCE"
            or manifest.get("output_count") != 2
            or len(manifest.get("outputs", [])) != 2
        ):
            return False
        if any(
            set(item) != {"name", "path", "sha256", "bytes"}
            for item in manifest["sources"]
        ):
            return False
        if any(
            set(item) != {"path", "sha256", "bytes"}
            for item in manifest["outputs"]
        ):
            return False
        expected_outputs = [
            {
                "path": path.relative_to(PROJECT_ROOT).as_posix(),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in (GATE_PATH, BRIEF_PATH)
        ]
        if manifest["outputs"] != expected_outputs:
            return False
        expected_script_sources = [
            {
                "name": path.stem,
                "path": path.relative_to(PROJECT_ROOT).as_posix(),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in (BUILDER_PATH, Path(__file__).resolve())
        ]
        expected_sources = copy.deepcopy(bindings) + expected_script_sources
        if manifest["sources"] != expected_sources:
            return False
        manifest_sources = {item.get("name"): item for item in manifest["sources"]}
        if set(manifest_sources) != EXPECTED_INPUT_NAMES | EXPECTED_SCRIPT_NAMES:
            return False
        if manifest.get("source_count") != len(expected_sources):
            return False

        if v4.get("schema") != "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V4":
            return False
        if (
            v4.get("gate") != "HOLD"
            or v4.get("next_stage_authorized") is not False
            or v4.get("release_credit") is not False
            or v4.get("testing_pass_grants_authority") is not False
        ):
            return False
        if (
            v4_manifest.get("gate") != "HOLD"
            or v4_manifest.get("next_stage_authorized") is not False
            or v4_manifest.get("release_credit") is not False
        ):
            return False
        if (
            v4_validation.get("gate") != "HOLD"
            or v4_validation.get("next_stage_authorized") is not False
            or v4_validation.get("release_credit") is not False
            or not str(v4_validation.get("verdict", "")).startswith("PASS_")
            or v4_validation.get("checks_passed")
            != v4_validation.get("checks_total")
            or v4_validation.get("negative_controls_passed")
            != v4_validation.get("negative_controls_total")
            or v4_validation.get("deepcopy_per_mutation") is not True
            or v4_validation.get("check_only_exact_reproduction") is not True
        ):
            return False

        expected_release = copy.deepcopy(v4["current_release"])
        if E21_EVALUATED_STATE in expected_release or ROUTE_C_FROZEN_STATE in expected_release:
            return False
        expected_release[E21_EVALUATED_STATE] = True
        expected_release[ROUTE_C_FROZEN_STATE] = True
        if gate.get("current_release") != expected_release:
            return False
        transition = gate.get("state_transition", {})
        if (
            transition.get("from_schema") != v4["schema"]
            or transition.get("prior_gate") != "HOLD"
            or transition.get("existing_current_release_fields_preserved_exactly")
            is not True
            or transition.get("existing_current_release_fields_changed") != []
            or transition.get("new_true_fields")
            != [E21_EVALUATED_STATE, ROUTE_C_FROZEN_STATE]
            or transition.get("new_true_field_count") != 2
            or transition.get("additional_release_authority_created") is not False
        ):
            return False

        if (
            e21.get("schema") != "E21_DIAGNOSTIC_GATE_V1"
            or e21.get("overall") != "HOLD"
            or e21.get("next_stage_authorized") is not False
            or e21.get("release_credit") is not False
            or e21.get("test_pass_grants_authority") is not False
            or e21.get("diagnostic_subcriteria_all_pass") is not True
            or e21.get("criterion_counts")
            != {"total": 23, "pass": 23, "fail": 0}
        ):
            return False
        if criterion(e21, "E21-G04").get("evidence") != (
            "MIXED_LEDGER_ARM_PLACEMENT_CONTEXT_DETECTED__"
            "CONSUMPTION_SEMANTICS_UNRESOLVED_HOLD"
        ):
            return False
        sensitivity = criterion(e21, "E21-G05").get("evidence", {})
        if (
            sensitivity.get("branches_selected") is not False
            or sensitivity.get("branches_averaged") is not False
            or sensitivity.get("branch_delta_is_uncertainty") is not False
            or sensitivity.get("single_placement_consumption_semantics_resolved")
            is not False
        ):
            return False
        scope = criterion(e21, "E21-G13").get("evidence", [])
        if not scope or any(
            lane.get("r2_wings")
            != "DEPLOYED_LOCKED_RIGID_MASS_PROPERTIES_IN_FIXED_RESIDUAL"
            or lane.get("legacy_r1_panel_inputs_consumed") is not False
            or lane.get("target_attached") is not False
            or lane.get("contact") is not False
            or lane.get("collision") is not False
            or lane.get("full_R2_flexible_coupling") is not False
            for lane in scope
        ):
            return False
        rom = criterion(e21, "E21-G21").get("evidence", {})
        if (
            rom.get("selected") is not False
            or rom.get("propagated_to_free_floating_dynamics") is not False
            or rom.get("dynamic_mass_allocation_frozen") is not False
        ):
            return False
        rom_response = criterion(e21, "E21-G22").get("evidence", {})
        if set(rom_response) != {"damping_matrix", "participation_factors", "forced_response"}:
            return False
        if any(value is not None for value in rom_response.values()):
            return False
        required_holds = {
            "single_arm_placement_consumption_semantics": "UNRESOLVED",
            "r2_full_flexible_coupling": "NOT_EVALUATED",
            "e15_ancf_certification": "REPEAT_ANCF_CERTIFICATION",
            "r2_harness_R2_HRN_04": "FAIL_REDESIGN_REQUIRED",
            "owner_review": "PENDING_OWNER_REVIEW",
            "collision": "HOLD_NOT_EVALUATED",
            "contact": "HOLD_NOT_EVALUATED",
            "target_attachment": "HOLD_NOT_EVALUATED",
            "mission_capture": "HOLD_NOT_EVALUATED",
            "production": "HOLD",
            "flight": "HOLD",
        }
        if e21.get("mandatory_holds") != required_holds:
            return False
        if (
            e21_validation.get("status") != "PASS"
            or e21_validation.get("criterion_counts")
            != {"total": 38, "pass": 38, "fail": 0}
            or e21_validation.get("overall_authority") != "HOLD"
            or e21_validation.get("next_stage_authorized") is not False
            or e21_validation.get("test_pass_grants_authority") is not False
            or not e21_validation.get("negative_controls")
            or any(
                item.get("deep_copy_used") is not True
                or item.get("mutation_detected") is not True
                or item.get("status") != "PASS"
                for item in e21_validation["negative_controls"]
            )
        ):
            return False
        if (
            e21_manifest.get("authority")
            != "CURRENT_M7_R2_NON_RELEASE_DIAGNOSTIC_ONLY"
            or e21_manifest.get("next_stage_authorized") is not False
            or e21_manifest.get("release_credit") is not False
        ):
            return False

        if (
            route.get("schema") != "ROUTE_C_PRECAD_PARAMETRIC_SEARCH_GATE_V1"
            or route.get("gate") != "UNKNOWN_FAIL_CLOSED"
            or route.get("verdict") != ROUTE_C_EXPECTED_VERDICT
            or route.get("authority_effect")
            != "CLOSES_PREDICATE_QUALIFICATION_AND_PARAMETER_SEARCH_CONTRACT_ONLY"
            or route.get("next_stage_authorized") is not False
            or route.get("cad_entry_authorized") is not False
            or route.get("candidate_found") is not False
            or route.get("route_b_disposition") != "REJECTED"
            or route.get("source_hashes_all_match") is not True
        ):
            return False
        predicate = route.get("predicate_qualification", {})
        if predicate != {
            "comparison_sets_nonempty": True,
            "grants_design_authority": False,
            "negative_controls_passed": 36,
            "negative_controls_total": 36,
            "positive_controls_passed": 11,
            "positive_controls_total": 11,
            "state": "PASS_SYNTHETIC_SEMANTICS_ONLY",
            "tests_passed": 47,
            "tests_total": 47,
        }:
            return False
        parameter = route.get("parameter_space", {})
        if (
            parameter.get("state") != "FROZEN_NON_RELEASE"
            or parameter.get("topologies_mutually_exclusive") is not True
            or parameter.get("J4_side_bypass_and_guided_loop_merged") is not False
            or parameter.get("accepted_urdf_joint_ranges_reduced") is not False
            or parameter.get("bundle_OD_is_scan_axis_not_known_value") is not True
            or parameter.get("vendor_bend_is_scan_axis_not_known_value") is not True
            or parameter.get("canonical_contract", {}).get(
                "canonical_contract_match"
            )
            is not True
            or parameter.get("canonical_contract", {}).get("top_level_keys_exact")
            is not True
            or parameter.get("physical_null_contract", {}).get(
                "all_required_physical_values_null"
            )
            is not True
        ):
            return False
        local_repro = route.get("local_hash_bound_reproducibility", {})
        if (
            local_repro.get("all_match") is not True
            or local_repro.get("external_trust_anchor") is not False
            or local_repro.get("authority_pin_count") != 5
            or local_repro.get("binding_class")
            != "LOCAL_HASH_BOUND_REPRODUCIBILITY_AND_SELF_CONSISTENCY__NO_EXTERNAL_TRUST_ANCHOR"
        ):
            return False
        for key in NULL_CAPACITY_FIELDS:
            values = values_for_key(route, key)
            if not values or any(value is not None for value in values):
                return False
        frontier = route.get("physical_capacity_frontier", {})
        if (
            frontier.get("candidate_found") is not False
            or frontier.get("physical_candidates_evaluated") != 0
            or frontier.get("state") != "UNKNOWN_NOT_COMPUTABLE"
            or route.get("retained_holds") != ROUTE_C_RETAINED_HOLDS
            or route.get("upstream_gate_state")
            != {
                "CAD_entry_gate": "HOLD",
                "CAD_entry_verdict": "ROUTE_C_PARAMETRIC_CAD_ENTRY_NOT_AUTHORIZED",
                "MPI_controlled": 0,
                "MPI_gate": "HOLD",
                "MPI_total": 8,
                "ODR42": "PENDING",
            }
        ):
            return False
        deep = route_validation.get("deep_copy_negative_controls", {})
        if (
            route_validation.get("schema")
            != "ROUTE_C_PRECAD_PARAMETRIC_SEARCH_VALIDATION_V1"
            or route_validation.get("status")
            != "PASS_VALIDATION_OF_NON_RELEASE_C1_5_DIAGNOSTIC"
            or route_validation.get("checks_passed") != 26
            or route_validation.get("checks_total") != 26
            or route_validation.get("checks_failed") != []
            or route_validation.get("validated_gate") != "UNKNOWN_FAIL_CLOSED"
            or route_validation.get("validated_verdict") != ROUTE_C_EXPECTED_VERDICT
            or deep.get("all_passed") is not True
            or deep.get("controls_passed") != 48
            or deep.get("controls_total") != 48
            or deep.get("original_gate_unchanged_after_deep_copy_mutations")
            is not True
        ):
            return False
        parameter_null = route_validation.get(
            "parameter_null_negative_controls", {}
        )
        parameter_contract = route_validation.get(
            "parameter_contract_negative_controls", {}
        )
        if (
            parameter_null.get("all_passed") is not True
            or parameter_null.get("controls_passed") != 7
            or parameter_null.get("controls_total") != 7
            or parameter_contract.get("all_passed") is not True
            or parameter_contract.get("controls_passed") != 12
            or parameter_contract.get("controls_total") != 12
        ):
            return False
        if (
            route_manifest.get("schema")
            != "ROUTE_C_PRECAD_PARAMETRIC_SEARCH_OUTPUT_MANIFEST_V1"
            or route_manifest.get("status")
            != "FROZEN_NON_RELEASE_C1_5_DIAGNOSTIC_PACKAGE"
            or route_manifest.get("gate") != "UNKNOWN_FAIL_CLOSED"
            or route_manifest.get("verdict") != ROUTE_C_EXPECTED_VERDICT
            or route_manifest.get("next_stage_authorized") is not False
            or route_manifest.get("self_hash_policy")
            != "SELF_HASH_EXCLUDED_TO_AVOID_RECURSION"
        ):
            return False

        placement = gate.get("m7_r2_arm_placement_consumption", {})
        if (
            placement.get("state") != PLACEMENT_STATE
            or placement.get("mixed_context_detected") is not True
            or placement.get("both_ledger_generations_audited") is not True
            or placement.get("single_consumption_rule_resolved") is not False
            or placement.get("branch_selected") is not None
            or placement.get("branches_averaged") is not False
            or placement.get("branch_delta_is_uncertainty") is not False
            or placement.get(
                "current_r2_deployed_locked_rigid_wing_m07_two_placement_sensitivity_closed"
            )
            is not True
            or placement.get("r2_full_flexible_coupling") != "NOT_EVALUATED"
            or placement.get("acceptance_threshold_authority") is not None
        ):
            return False
        fixed_rom = gate.get("fixed_base_r2_rom_boundary", {})
        if (
            fixed_rom.get("leaf_only_published_rom_reproduction_closed") is not True
            or fixed_rom.get("moving_inter_hinge_mass_conflict_recorded") is not True
            or fixed_rom.get("moving_inter_hinge_mass_conflict_selected") is not False
            or fixed_rom.get(
                "moving_inter_hinge_mass_conflict_propagated_to_free_floating_dynamics"
            )
            is not False
            or fixed_rom.get("dynamic_mass_allocation_frozen") is not False
            or fixed_rom.get("damping_matrix") is not None
            or fixed_rom.get("participation_factors") is not None
            or fixed_rom.get("forced_response") is not None
            or fixed_rom.get("full_r2_flex_claimed") is not False
        ):
            return False
        route_contract = gate.get("route_c_precad_method_contract", {})
        if (
            route_contract.get("state")
            != "PREDICATE_QUALIFICATION_AND_PARAMETER_SPACE_FROZEN"
            or route_contract.get(ROUTE_C_FROZEN_STATE) is not True
            or route_contract.get("physical_capacity_gate") != "UNKNOWN_HOLD"
            or route_contract.get("physical_route_c_candidate_selected") is not False
            or route_contract.get("topology_branches_averaged") is not False
            or route_contract.get("odr42_authorized") is not False
            or route_contract.get("mpi_controlled") != 0
            or route_contract.get("mpi_total") != 8
            or route_contract.get("cad_entry_authorized") is not False
            or route_contract.get("vendor_selected") is not False
            or route_contract.get("mission_coverage_released") is not False
            or route_contract.get("released_segments") != 0
        ):
            return False
        capacity = route_contract.get("physical_capacity_frontier", {})
        if set(capacity) != set(NULL_CAPACITY_FIELDS):
            return False
        if any(value is not None for value in capacity.values()):
            return False
        holds = gate.get("preserved_holds", {})
        if (
            holds.get("single_arm_placement_consumption_rule") != "UNRESOLVED"
            or holds.get("r2_full_flexible_coupling") != "NOT_EVALUATED"
            or holds.get("e15_ancf_certification") != "REPEAT_ANCF_CERTIFICATION"
            or holds.get("r2_harness_R2_HRN_04") != "FAIL_REDESIGN_REQUIRED"
            or any(
                holds.get(key) is not False
                for key in (
                    "physical_contact_ready",
                    "attached_target_recovery_ready",
                    "released_combined_mass_properties_ready",
                    "cad_generation_authorized",
                    "mission_trajectory_release_ready",
                    "production_dynamics_ready",
                    "hardware_motion_ready",
                    "flight_qualification_ready",
                )
            )
        ):
            return False
        return True
    except (KeyError, TypeError, ValueError, IndexError):
        return False


Mutation = tuple[str, Callable[[dict[str, Any]], None]]


def assign(path: tuple[Any, ...], value: Any) -> Callable[[dict[str, Any]], None]:
    def mutate(bundle: dict[str, Any]) -> None:
        node: Any = bundle
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value

    return mutate


def pop_key(path: tuple[Any, ...]) -> Callable[[dict[str, Any]], None]:
    def mutate(bundle: dict[str, Any]) -> None:
        node: Any = bundle
        for key in path[:-1]:
            node = node[key]
        node.pop(path[-1])

    return mutate


def set_e21_criterion(
    criterion_id: str, key: str, value: Any
) -> Callable[[dict[str, Any]], None]:
    def mutate(bundle: dict[str, Any]) -> None:
        evidence = criterion(bundle["e21"], criterion_id)["evidence"]
        evidence[key] = value

    return mutate


def set_route_null(key: str, value: Any) -> Callable[[dict[str, Any]], None]:
    def mutate(bundle: dict[str, Any]) -> None:
        if not set_first_key(bundle["route"], key, value):
            raise KeyError(key)

    return mutate


def set_manifest_source_field(
    name: str, key: str, value: Any
) -> Callable[[dict[str, Any]], None]:
    def mutate(bundle: dict[str, Any]) -> None:
        matches = [
            item
            for item in bundle["manifest"]["sources"]
            if item.get("name") == name
        ]
        if len(matches) != 1:
            raise KeyError(name)
        matches[0][key] = value

    return mutate


def negative_mutations() -> list[Mutation]:
    mutations: list[Mutation] = [
        ("GATE_SCHEMA_DRIFT", assign(("gate", "schema"), "DRIFT")),
        ("VERDICT_DRIFT", assign(("gate", "verdict"), "PASS")),
        ("GATE_PROMOTED", assign(("gate", "gate"), "PASS")),
        ("NEXT_STAGE_TRUE", assign(("gate", "next_stage_authorized"), True)),
        ("RELEASE_CREDIT_TRUE", assign(("gate", "release_credit"), True)),
        ("TEST_AUTHORITY_TRUE", assign(("gate", "testing_pass_grants_authority"), True)),
        ("UNKNOWN_UNCERTAINTIES_ZERO_FILLED", assign(("gate", "unknown_uncertainties_zero_filled"), True)),
        ("RELEASED_SEGMENTS_ONE", assign(("gate", "released_segments"), 1)),
        ("P1_EXTRA_RELEASE_AUTHORIZED", lambda b: b["gate"].__setitem__("release_authorized", True)),
        ("P1_EXTRA_CAD_ENTRY_AUTHORIZED", lambda b: b["gate"].__setitem__("cad_entry_authorized", True)),
        ("P1_PARALLEL_PHYSICAL_CAPACITY_FRONTIER", lambda b: b["gate"].__setitem__("physical_capacity_frontier", {"D_max_geometry_mm": 99.0, "state": "PASS"})),
        ("P1_AUTHORITY_SCOPE_FLIGHT_UPLIFT", assign(("gate", "authority_scope"), "FLIGHT_RELEASE_AUTHORITY")),
        ("P1_REQUIRED_OWNER_STATEMENT_FALSE_APPROVAL", assign(("gate", "required_owner_statement"), "ODR42 APPROVED")),
        ("P1_PROHIBITION_CLEARED", assign(("gate", "prohibition"), "")),
        ("P1_LC5_12_RELEASE_CREDIT_TRUE", assign(("gate", "facts", 11, "evidence", "mechanical_release_credit"), True)),
        ("EXTRA_TOP_LEVEL_UNKNOWN", lambda b: b["gate"].__setitem__("unknown_authority_field", False)),
        ("FAIL_CLOSED_INVARIANT_REMOVED", lambda b: b["gate"]["fail_closed_invariants"].pop()),
        ("BLOCKING_FRONT_PROMOTED", assign(("gate", "blocking_fronts", 0, "state"), "PASS")),
        ("SHORTEST_SEQUENCE_REMOVED", lambda b: b["gate"]["shortest_engineering_sequence"].pop()),
        ("FACT_TOTAL_DRIFT", assign(("gate", "facts_total"), 11)),
        ("FACT_CONFIRMED_DRIFT", assign(("gate", "facts_confirmed"), 11)),
        ("FACT_FALSE", assign(("gate", "facts", 0, "observed"), False)),
        ("FACT_ID_DRIFT", assign(("gate", "facts", 0, "id"), "LC5-X")),
        ("FACT_REMOVED", lambda b: b["gate"]["facts"].pop()),
        ("INPUT_REMOVED", lambda b: b["gate"]["input_bindings"].pop()),
        ("INPUT_NAME_DRIFT", assign(("gate", "input_bindings", 0, "name"), "DRIFT")),
        ("INPUT_PATH_BLANK", assign(("gate", "input_bindings", 0, "path"), "")),
        ("INPUT_HASH_DRIFT", assign(("gate", "input_bindings", 0, "sha256"), "0" * 64)),
        ("INPUT_BYTES_ZERO", assign(("gate", "input_bindings", 0, "bytes"), 0)),
        ("MANIFEST_SCHEMA_DRIFT", assign(("manifest", "schema"), "DRIFT")),
        ("MANIFEST_GATE_PASS", assign(("manifest", "gate"), "PASS")),
        ("MANIFEST_NEXT_TRUE", assign(("manifest", "next_stage_authorized"), True)),
        ("MANIFEST_RELEASE_TRUE", assign(("manifest", "release_credit"), True)),
        ("MANIFEST_SEGMENT_ONE", assign(("manifest", "released_segments"), 1)),
        ("MANIFEST_SELF_HASH_TRUE", assign(("manifest", "validation_report_excluded_to_avoid_self_hash"), False)),
        ("MANIFEST_OUTPUT_COUNT_DRIFT", assign(("manifest", "output_count"), 3)),
        ("MANIFEST_OUTPUT_REMOVED", lambda b: b["manifest"]["outputs"].pop()),
        ("MANIFEST_SOURCE_COUNT_DRIFT", assign(("manifest", "source_count"), 1)),
        ("MANIFEST_SOURCE_REMOVED", lambda b: b["manifest"]["sources"].pop()),
        ("MANIFEST_SOURCE_HASH_DRIFT", assign(("manifest", "sources", 0, "sha256"), "F" * 64)),
        ("MANIFEST_EXTRA_AUTHORITY_FIELD", lambda b: b["manifest"].__setitem__("release_authorized", True)),
        ("P1_MANIFEST_GENERATED_LOCAL_DRIFT", assign(("manifest", "generated_local"), "2099-01-01T00:00:00+08:00")),
        ("P1_MANIFEST_GATE_OUTPUT_SHA_DRIFT", assign(("manifest", "outputs", 0, "sha256"), "0" * 64)),
        ("P1_MANIFEST_GATE_OUTPUT_PATH_DRIFT", assign(("manifest", "outputs", 0, "path"), "wrong/gate.json")),
        ("P1_MANIFEST_GATE_OUTPUT_BYTES_DRIFT", assign(("manifest", "outputs", 0, "bytes"), 1)),
        ("P1_MANIFEST_BUILDER_SHA_DRIFT", set_manifest_source_field("build_mechanical_loop_continuation_v5", "sha256", "0" * 64)),
        ("P1_MANIFEST_BUILDER_PATH_DRIFT", set_manifest_source_field("build_mechanical_loop_continuation_v5", "path", "wrong/builder.py")),
        ("P1_MANIFEST_BUILDER_BYTES_DRIFT", set_manifest_source_field("build_mechanical_loop_continuation_v5", "bytes", 1)),
        ("P1_MANIFEST_VALIDATOR_SHA_DRIFT", set_manifest_source_field("validate_mechanical_loop_continuation_v5", "sha256", "0" * 64)),
        ("MANIFEST_VERDICT_DRIFT", assign(("manifest", "verdict"), "PASS")),
        ("MANIFEST_SELF_HASH_POLICY_DRIFT", assign(("manifest", "self_hash_policy"), "INCLUDES_VALIDATION")),
        ("V4_GATE_PROMOTED", assign(("v4", "gate"), "PASS")),
        ("V4_NEXT_TRUE", assign(("v4", "next_stage_authorized"), True)),
        ("V4_RELEASE_TRUE", assign(("v4", "release_credit"), True)),
        ("V4_TEST_AUTHORITY_TRUE", assign(("v4", "testing_pass_grants_authority"), True)),
        ("V4_MANIFEST_GATE_PASS", assign(("v4_manifest", "gate"), "PASS")),
        ("V4_MANIFEST_NEXT_TRUE", assign(("v4_manifest", "next_stage_authorized"), True)),
        ("V4_VALIDATION_GATE_PASS", assign(("v4_validation", "gate"), "PASS")),
        ("V4_VALIDATION_CHECK_LOSS", assign(("v4_validation", "checks_passed"), 37)),
        ("V4_VALIDATION_NEGATIVE_LOSS", assign(("v4_validation", "negative_controls_passed"), 115)),
        ("V4_VALIDATION_DEEPCOPY_FALSE", assign(("v4_validation", "deepcopy_per_mutation"), False)),
        ("V4_VALIDATION_EXACT_FALSE", assign(("v4_validation", "check_only_exact_reproduction"), False)),
        ("OLD_FALSE_PROMOTED", assign(("gate", "current_release", "physical_contact_ready"), True)),
        ("OLD_TRUE_DEMOTED", assign(("gate", "current_release", "isolated_nonrelease_numeric_input_branches_ready"), False)),
        ("E21_STATE_FALSE", assign(("gate", "current_release", E21_EVALUATED_STATE), False)),
        ("ROUTE_STATE_FALSE", assign(("gate", "current_release", ROUTE_C_FROZEN_STATE), False)),
        ("EXTRA_RELEASE_FIELD", lambda b: b["gate"]["current_release"].__setitem__("extra", True)),
        ("TRANSITION_SCHEMA_DRIFT", assign(("gate", "state_transition", "from_schema"), "DRIFT")),
        ("TRANSITION_PRIOR_PASS", assign(("gate", "state_transition", "prior_gate"), "PASS")),
        ("TRANSITION_PRESERVATION_FALSE", assign(("gate", "state_transition", "existing_current_release_fields_preserved_exactly"), False)),
        ("TRANSITION_CHANGED_FIELD", lambda b: b["gate"]["state_transition"]["existing_current_release_fields_changed"].append("x")),
        ("TRANSITION_NEW_FIELD_LOSS", lambda b: b["gate"]["state_transition"]["new_true_fields"].pop()),
        ("TRANSITION_COUNT_DRIFT", assign(("gate", "state_transition", "new_true_field_count"), 3)),
        ("TRANSITION_AUTHORITY_TRUE", assign(("gate", "state_transition", "additional_release_authority_created"), True)),
        ("E21_OVERALL_PASS", assign(("e21", "overall"), "PASS")),
        ("E21_NEXT_TRUE", assign(("e21", "next_stage_authorized"), True)),
        ("E21_RELEASE_TRUE", assign(("e21", "release_credit"), True)),
        ("E21_TEST_AUTHORITY_TRUE", assign(("e21", "test_pass_grants_authority"), True)),
        ("E21_SUBCRITERIA_FALSE", assign(("e21", "diagnostic_subcriteria_all_pass"), False)),
        ("E21_CRITERIA_COUNT_DRIFT", assign(("e21", "criterion_counts", "pass"), 22)),
        ("E21_MIXED_STATE_DRIFT", assign(("e21", "criteria", 3, "evidence"), "RECONCILED")),
        ("E21_BRANCH_SELECTED", set_e21_criterion("E21-G05", "branches_selected", True)),
        ("E21_BRANCH_AVERAGED", set_e21_criterion("E21-G05", "branches_averaged", True)),
        ("E21_DELTA_UNCERTAINTY", set_e21_criterion("E21-G05", "branch_delta_is_uncertainty", True)),
        ("E21_SINGLE_RULE_RESOLVED", set_e21_criterion("E21-G05", "single_placement_consumption_semantics_resolved", True)),
        ("E21_ROM_SELECTED", set_e21_criterion("E21-G21", "selected", True)),
        ("E21_ROM_PROPAGATED", set_e21_criterion("E21-G21", "propagated_to_free_floating_dynamics", True)),
        ("E21_MASS_ALLOCATION_FROZEN", set_e21_criterion("E21-G21", "dynamic_mass_allocation_frozen", True)),
        ("E21_DAMPING_FILLED", set_e21_criterion("E21-G22", "damping_matrix", [[0.0]])),
        ("E21_PARTICIPATION_FILLED", set_e21_criterion("E21-G22", "participation_factors", [0.0])),
        ("E21_FORCED_RESPONSE_FILLED", set_e21_criterion("E21-G22", "forced_response", {})),
        ("E21_HOLD_SINGLE_RESOLVED", assign(("e21", "mandatory_holds", "single_arm_placement_consumption_semantics"), "RESOLVED")),
        ("E21_HOLD_FULL_FLEX_PASS", assign(("e21", "mandatory_holds", "r2_full_flexible_coupling"), "PASS")),
        ("E21_HOLD_E15_PASS", assign(("e21", "mandatory_holds", "e15_ancf_certification"), "PASS")),
        ("E21_HOLD_HARNESS_PASS", assign(("e21", "mandatory_holds", "r2_harness_R2_HRN_04"), "PASS")),
        ("E21_HOLD_CONTACT_PASS", assign(("e21", "mandatory_holds", "contact"), "PASS")),
        ("E21_HOLD_MISSION_PASS", assign(("e21", "mandatory_holds", "mission_capture"), "PASS")),
        ("E21_VALIDATION_FAIL", assign(("e21_validation", "status"), "FAIL")),
        ("E21_VALIDATION_COUNT_LOSS", assign(("e21_validation", "criterion_counts", "pass"), 37)),
        ("E21_VALIDATION_AUTHORITY_PASS", assign(("e21_validation", "overall_authority"), "PASS")),
        ("E21_VALIDATION_NEXT_TRUE", assign(("e21_validation", "next_stage_authorized"), True)),
        ("E21_NEGATIVE_UNDETECTED", assign(("e21_validation", "negative_controls", 0, "mutation_detected"), False)),
        ("E21_MANIFEST_AUTHORITY_DRIFT", assign(("e21_manifest", "authority"), "RELEASE")),
        ("E21_MANIFEST_NEXT_TRUE", assign(("e21_manifest", "next_stage_authorized"), True)),
        ("E21_MANIFEST_RELEASE_TRUE", assign(("e21_manifest", "release_credit"), True)),
        ("E21_EXTRA_NESTED_SCHEMA_FIELD", lambda b: b["e21"].__setitem__("release_authorized", True)),
        ("E21_VALIDATION_EXTRA_FIELD", lambda b: b["e21_validation"].__setitem__("cad_authorized", True)),
        ("ROUTE_GATE_PASS", assign(("route", "gate"), "PASS")),
        ("ROUTE_VERDICT_DRIFT", assign(("route", "verdict"), "PASS")),
        ("ROUTE_AUTHORITY_EFFECT_DRIFT", assign(("route", "authority_effect"), "CAD_AUTHORIZED")),
        ("ROUTE_PREDICATE_STATE_DRIFT", assign(("route", "predicate_qualification", "state"), "PASS_PHYSICAL")),
        ("ROUTE_PREDICATE_POSITIVE_LOSS", assign(("route", "predicate_qualification", "positive_controls_passed"), 7)),
        ("ROUTE_PREDICATE_NEGATIVE_LOSS", assign(("route", "predicate_qualification", "negative_controls_passed"), 17)),
        ("ROUTE_PARAMETER_STATE_DRIFT", assign(("route", "parameter_space", "state"), "RELEASED")),
        ("ROUTE_TOPOLOGIES_MERGED", assign(("route", "parameter_space", "topologies_mutually_exclusive"), False)),
        ("ROUTE_CANONICAL_MATCH_FALSE", assign(("route", "parameter_space", "canonical_contract", "canonical_contract_match"), False)),
        ("ROUTE_PARAMETER_NULL_FALSE", assign(("route", "parameter_space", "physical_null_contract", "all_required_physical_values_null"), False)),
        ("ROUTE_LOCAL_REPRO_FALSE", assign(("route", "local_hash_bound_reproducibility", "all_match"), False)),
        ("ROUTE_EXTERNAL_TRUST_ANCHOR_TRUE", assign(("route", "local_hash_bound_reproducibility", "external_trust_anchor"), True)),
        ("ROUTE_NEXT_TRUE", assign(("route", "next_stage_authorized"), True)),
        ("ROUTE_SOURCE_CAD_TRUE", assign(("route", "cad_entry_authorized"), True)),
        ("ROUTE_CANDIDATE_TRUE", assign(("route", "candidate_found"), True)),
        ("ROUTE_ROUTE_B_REOPENED", assign(("route", "route_b_disposition"), "OPEN")),
        ("ROUTE_SOURCE_HASH_FALSE", assign(("route", "source_hashes_all_match"), False)),
        ("ROUTE_HOLD_REMOVED", lambda b: b["route"]["retained_holds"].pop()),
        ("ROUTE_VALIDATION_FAIL", assign(("route_validation", "status"), "FAIL")),
        ("ROUTE_VALIDATION_CHECK_LOSS", assign(("route_validation", "checks_passed"), 19)),
        ("ROUTE_VALIDATION_DEEP_LOSS", assign(("route_validation", "deep_copy_negative_controls", "controls_passed"), 13)),
        ("ROUTE_VALIDATION_PN_LOSS", assign(("route_validation", "parameter_null_negative_controls", "controls_passed"), 6)),
        ("ROUTE_VALIDATION_PC_LOSS", assign(("route_validation", "parameter_contract_negative_controls", "controls_passed"), 11)),
        ("ROUTE_VALIDATION_VERDICT_DRIFT", assign(("route_validation", "validated_verdict"), "PASS")),
        ("ROUTE_MANIFEST_NEXT_TRUE", assign(("route_manifest", "next_stage_authorized"), True)),
        ("ROUTE_MANIFEST_GATE_PASS", assign(("route_manifest", "gate"), "PASS")),
        ("ROUTE_MANIFEST_VERDICT_DRIFT", assign(("route_manifest", "verdict"), "PASS")),
        ("ROUTE_EXTRA_NESTED_SCHEMA_FIELD", lambda b: b["route"].__setitem__("release_authorized", True)),
        ("ROUTE_VALIDATION_EXTRA_FIELD", lambda b: b["route_validation"].__setitem__("cad_authorized", True)),
        ("PLACEMENT_STATE_DRIFT", assign(("gate", "m7_r2_arm_placement_consumption", "state"), "RESOLVED")),
        ("PLACEMENT_MIXED_FALSE", assign(("gate", "m7_r2_arm_placement_consumption", "mixed_context_detected"), False)),
        ("PLACEMENT_RULE_RESOLVED", assign(("gate", "m7_r2_arm_placement_consumption", "single_consumption_rule_resolved"), True)),
        ("PLACEMENT_BRANCH_SELECTED", assign(("gate", "m7_r2_arm_placement_consumption", "branch_selected"), "ODR01")),
        ("PLACEMENT_BRANCH_AVERAGED", assign(("gate", "m7_r2_arm_placement_consumption", "branches_averaged"), True)),
        ("PLACEMENT_DELTA_UNCERTAINTY", assign(("gate", "m7_r2_arm_placement_consumption", "branch_delta_is_uncertainty"), True)),
        ("PLACEMENT_FULL_FLEX_PASS", assign(("gate", "m7_r2_arm_placement_consumption", "r2_full_flexible_coupling"), "PASS")),
        ("PLACEMENT_THRESHOLD_FILLED", assign(("gate", "m7_r2_arm_placement_consumption", "acceptance_threshold_authority"), 1.0)),
        ("ROM_REPRO_FALSE", assign(("gate", "fixed_base_r2_rom_boundary", "leaf_only_published_rom_reproduction_closed"), False)),
        ("ROM_CONFLICT_SELECTED", assign(("gate", "fixed_base_r2_rom_boundary", "moving_inter_hinge_mass_conflict_selected"), True)),
        ("ROM_CONFLICT_PROPAGATED", assign(("gate", "fixed_base_r2_rom_boundary", "moving_inter_hinge_mass_conflict_propagated_to_free_floating_dynamics"), True)),
        ("ROM_MASS_FROZEN", assign(("gate", "fixed_base_r2_rom_boundary", "dynamic_mass_allocation_frozen"), True)),
        ("ROM_DAMPING_FILLED", assign(("gate", "fixed_base_r2_rom_boundary", "damping_matrix"), [[0.0]])),
        ("ROM_PARTICIPATION_FILLED", assign(("gate", "fixed_base_r2_rom_boundary", "participation_factors"), [0.0])),
        ("ROM_FORCED_FILLED", assign(("gate", "fixed_base_r2_rom_boundary", "forced_response"), {})),
        ("ROM_FULL_FLEX_TRUE", assign(("gate", "fixed_base_r2_rom_boundary", "full_r2_flex_claimed"), True)),
        ("ROUTE_CONTRACT_STATE_DRIFT", assign(("gate", "route_c_precad_method_contract", "state"), "PHYSICAL_PASS")),
        ("ROUTE_CONTRACT_FROZEN_FALSE", assign(("gate", "route_c_precad_method_contract", ROUTE_C_FROZEN_STATE), False)),
        ("ROUTE_CAPACITY_PASS", assign(("gate", "route_c_precad_method_contract", "physical_capacity_gate"), "PASS")),
        ("ROUTE_CANDIDATE_SELECTED", assign(("gate", "route_c_precad_method_contract", "physical_route_c_candidate_selected"), True)),
        ("ROUTE_TOPOLOGY_AVERAGED", assign(("gate", "route_c_precad_method_contract", "topology_branches_averaged"), True)),
        ("ROUTE_ODR42_TRUE", assign(("gate", "route_c_precad_method_contract", "odr42_authorized"), True)),
        ("ROUTE_MPI_ONE", assign(("gate", "route_c_precad_method_contract", "mpi_controlled"), 1)),
        ("ROUTE_CAD_TRUE", assign(("gate", "route_c_precad_method_contract", "cad_entry_authorized"), True)),
        ("ROUTE_VENDOR_TRUE", assign(("gate", "route_c_precad_method_contract", "vendor_selected"), True)),
        ("ROUTE_MISSION_TRUE", assign(("gate", "route_c_precad_method_contract", "mission_coverage_released"), True)),
        ("ROUTE_CONTRACT_SEGMENT_ONE", assign(("gate", "route_c_precad_method_contract", "released_segments"), 1)),
        ("HOLD_SINGLE_RESOLVED", assign(("gate", "preserved_holds", "single_arm_placement_consumption_rule"), "RESOLVED")),
        ("HOLD_FULL_FLEX_PASS", assign(("gate", "preserved_holds", "r2_full_flexible_coupling"), "PASS")),
        ("HOLD_E15_PASS", assign(("gate", "preserved_holds", "e15_ancf_certification"), "PASS")),
        ("HOLD_HARNESS_PASS", assign(("gate", "preserved_holds", "r2_harness_R2_HRN_04"), "PASS")),
        ("HOLD_CONTACT_TRUE", assign(("gate", "preserved_holds", "physical_contact_ready"), True)),
        ("HOLD_ATTACHED_TRUE", assign(("gate", "preserved_holds", "attached_target_recovery_ready"), True)),
        ("HOLD_MASS_TRUE", assign(("gate", "preserved_holds", "released_combined_mass_properties_ready"), True)),
        ("HOLD_CAD_TRUE", assign(("gate", "preserved_holds", "cad_generation_authorized"), True)),
        ("HOLD_MISSION_TRUE", assign(("gate", "preserved_holds", "mission_trajectory_release_ready"), True)),
        ("HOLD_PRODUCTION_TRUE", assign(("gate", "preserved_holds", "production_dynamics_ready"), True)),
        ("HOLD_HARDWARE_TRUE", assign(("gate", "preserved_holds", "hardware_motion_ready"), True)),
        ("HOLD_FLIGHT_TRUE", assign(("gate", "preserved_holds", "flight_qualification_ready"), True)),
    ]
    for key in NULL_CAPACITY_FIELDS:
        mutations.append((f"ROUTE_SOURCE_NULL_FILLED_{key}", set_route_null(key, 0.0)))
        mutations.append(
            (
                f"V5_CAPACITY_NULL_FILLED_{key}",
                assign(
                    (
                        "gate",
                        "route_c_precad_method_contract",
                        "physical_capacity_frontier",
                        key,
                    ),
                    0.0,
                ),
            )
        )
    return mutations


def artifact_exact_checks(builder: ModuleType) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(check_id: str, passed: bool, detail: Any) -> None:
        checks.append({"id": check_id, "pass": bool(passed), "detail": detail})

    gate = load(GATE_PATH)
    manifest = load(MANIFEST_PATH)
    by_name = {item["name"]: item for item in gate["input_bindings"]}
    for name in sorted(EXPECTED_INPUT_NAMES):
        item = by_name[name]
        path = PROJECT_ROOT / item["path"]
        add(
            f"INPUT_HASH_{name}",
            path.is_file()
            and sha256(path) == item["sha256"]
            and path.stat().st_size == item["bytes"],
            item["path"],
        )
    for item in manifest["outputs"]:
        path = PROJECT_ROOT / item["path"]
        add(
            f"OUTPUT_HASH_{path.stem}",
            path.is_file()
            and sha256(path) == item["sha256"]
            and path.stat().st_size == item["bytes"],
            item["path"],
        )
    for item in manifest["sources"]:
        path = PROJECT_ROOT / item["path"]
        add(
            f"MANIFEST_SOURCE_HASH_{item['name']}",
            path.is_file()
            and sha256(path) == item["sha256"]
            and path.stat().st_size == item["bytes"],
            item["path"],
        )
    expected_artifacts = builder.artifact_bytes()
    for path, expected in expected_artifacts.items():
        add(
            f"CHECK_ONLY_EXACT_{path.stem}",
            path.is_file() and path.read_bytes() == expected,
            path.relative_to(PROJECT_ROOT).as_posix(),
        )
    exact, mismatches = builder.check_outputs()
    add("BUILDER_CHECK_ONLY_EXACT_REPRODUCTION", exact, mismatches)
    add(
        "NO_VALIDATION_SELF_HASH",
        all(item["path"] != VALIDATION_PATH.relative_to(PROJECT_ROOT).as_posix() for item in manifest["outputs"]),
        VALIDATION_PATH.relative_to(PROJECT_ROOT).as_posix(),
    )
    pycache = sorted(
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in ECR_ROOT.rglob("__pycache__")
    )
    add("NO_PYCACHE", not pycache, pycache)
    baseline = source_bundle(gate, manifest)
    add("UNIFIED_GATE_SAFE_BASELINE", gate_safe(baseline), [])
    add(
        "GATE_EXACT_TOP_LEVEL_KEY_SET",
        set(gate) == EXPECTED_GATE_TOP_LEVEL_KEYS,
        sorted(gate),
    )
    add(
        "GATE_EXACT_CANONICAL_HASH",
        canonical_hash(gate) == EXPECTED_CANONICAL_HASHES["v5_gate"],
        canonical_hash(gate),
    )
    add(
        "AUTHORITY_AND_HUMAN_RULING_FIELDS_EXACT",
        gate["authority_scope"] == EXPECTED_AUTHORITY_SCOPE
        and gate["decision_rule"] == EXPECTED_DECISION_RULE
        and gate["required_owner_statement"] == EXPECTED_REQUIRED_OWNER_STATEMENT
        and gate["prohibition"] == EXPECTED_PROHIBITION,
        [],
    )
    add(
        "FACTS_12_EXACT_CANONICAL_EVIDENCE",
        canonical_hash(gate["facts"]) == EXPECTED_CANONICAL_HASHES["facts"]
        and len(gate["facts"]) == 12,
        EXPECTED_CANONICAL_HASHES["facts"],
    )
    add(
        "HOLDS_FRONTS_AND_SEQUENCE_EXACT",
        canonical_hash(gate["preserved_holds"])
        == EXPECTED_CANONICAL_HASHES["preserved_holds"]
        and canonical_hash(gate["blocking_fronts"])
        == EXPECTED_CANONICAL_HASHES["blocking_fronts"]
        and canonical_hash(gate["shortest_engineering_sequence"])
        == EXPECTED_CANONICAL_HASHES["shortest_engineering_sequence"],
        [],
    )
    add(
        "E21_ALL_NESTED_SCHEMA_AND_EVIDENCE_EXACT",
        canonical_hash(baseline["e21"])
        == EXPECTED_CANONICAL_HASHES["e21_gate"]
        and canonical_hash(baseline["e21_validation"])
        == EXPECTED_CANONICAL_HASHES["e21_validation"]
        and canonical_hash(baseline["e21_manifest"])
        == EXPECTED_CANONICAL_HASHES["e21_manifest"],
        [],
    )
    add(
        "ROUTE_C_ALL_NESTED_SCHEMA_AND_EVIDENCE_EXACT",
        canonical_hash(baseline["route"])
        == EXPECTED_CANONICAL_HASHES["route_c_precad_gate"]
        and canonical_hash(baseline["route_validation"])
        == EXPECTED_CANONICAL_HASHES["route_c_precad_validation"]
        and canonical_hash(baseline["route_manifest"])
        == EXPECTED_CANONICAL_HASHES["route_c_precad_manifest"],
        [],
    )
    expected_manifest_outputs = [
        {
            "path": path.relative_to(PROJECT_ROOT).as_posix(),
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in (GATE_PATH, BRIEF_PATH)
    ]
    expected_manifest_sources = copy.deepcopy(gate["input_bindings"]) + [
        {
            "name": path.stem,
            "path": path.relative_to(PROJECT_ROOT).as_posix(),
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in (BUILDER_PATH, Path(__file__).resolve())
    ]
    add(
        "MANIFEST_OUTPUT_AND_V5_TOOL_RECORDS_RUNTIME_EXACT",
        manifest["generated_local"] == GENERATED_LOCAL
        and manifest["verdict"] == EXPECTED_VERDICT
        and manifest["outputs"] == expected_manifest_outputs
        and manifest["sources"] == expected_manifest_sources
        and manifest["self_hash_policy"]
        == "VALIDATION_REPORT_EXCLUDED_TO_AVOID_SELF_REFERENCE",
        [],
    )
    add(
        "V4_GATE_BRIEF_MANIFEST_VALIDATION_BOUND",
        {item["name"] for item in gate["input_bindings"]}
        >= {"loop_v4_gate", "loop_v4_brief", "loop_v4_manifest", "loop_v4_validation"},
        [],
    )
    add(
        "E21_THREE_PIECE_EVIDENCE_BOUND",
        {item["name"] for item in gate["input_bindings"]}
        >= {"e21_gate", "e21_validation", "e21_manifest"},
        [],
    )
    add(
        "ROUTE_C_THREE_PIECE_EVIDENCE_BOUND",
        {item["name"] for item in gate["input_bindings"]}
        >= {"route_c_precad_gate", "route_c_precad_validation", "route_c_precad_manifest"},
        [],
    )
    add(
        "ALL_FACTS_CONFIRMED",
        gate["facts_confirmed"] == gate["facts_total"] == 12,
        "12/12",
    )
    add(
        "EXACT_TWO_NONRELEASE_STATE_ADDITIONS",
        gate["state_transition"]["new_true_fields"]
        == [E21_EVALUATED_STATE, ROUTE_C_FROZEN_STATE],
        gate["state_transition"]["new_true_fields"],
    )
    add(
        "RELEASE_BOUNDARY_HOLD_FALSE_FALSE_ZERO",
        gate["gate"] == "HOLD"
        and gate["next_stage_authorized"] is False
        and gate["release_credit"] is False
        and gate["released_segments"] == 0,
        [],
    )
    return checks


def build_validation() -> dict[str, Any]:
    builder = load_builder()
    checks = artifact_exact_checks(builder)
    gate = load(GATE_PATH)
    manifest = load(MANIFEST_PATH)
    baseline = source_bundle(gate, manifest)
    if not gate_safe(baseline):
        raise RuntimeError("baseline unified Gate predicate failed")

    negative_controls: list[dict[str, Any]] = []
    for control_id, mutate in negative_mutations():
        candidate = copy.deepcopy(baseline)
        mutate(candidate)
        accepted = gate_safe(candidate)
        negative_controls.append(
            {
                "id": control_id,
                "pass": not accepted,
                "accepted_after_mutation": accepted,
                "deep_copy_used": True,
            }
        )

    checks_passed = sum(item["pass"] for item in checks)
    negatives_passed = sum(item["pass"] for item in negative_controls)
    all_safe = (
        checks_passed == len(checks)
        and negatives_passed == len(negative_controls)
        and gate_safe(baseline)
    )
    if not all_safe:
        failed_checks = [item["id"] for item in checks if not item["pass"]]
        failed_controls = [
            item["id"] for item in negative_controls if not item["pass"]
        ]
        raise RuntimeError(
            f"V5 validation failed: checks={failed_checks}, controls={failed_controls}"
        )

    return {
        "schema": "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_VALIDATION_V5",
        "generated_local": GENERATED_LOCAL,
        "checks": checks,
        "checks_passed": checks_passed,
        "checks_total": len(checks),
        "negative_controls": negative_controls,
        "negative_controls_passed": negatives_passed,
        "negative_controls_total": len(negative_controls),
        "deepcopy_per_mutation": True,
        "minimum_negative_control_count": 100,
        "check_only_exact_reproduction": True,
        "unified_gate_safe_predicate": True,
        "unknown_uncertainties_zero_filled": False,
        "gate": "HOLD",
        "next_stage_authorized": False,
        "release_credit": False,
        "released_segments": 0,
        "verdict": (
            "PASS_LOOP_V5_CURRENT_R2_RIGID_ARM_PLACEMENT_FIXED_BASE_ROM_"
            "AND_ROUTE_C_PRECAD_METHOD_REBIND__SINGLE_PLACEMENT_FULL_FLEX_"
            "E15_HARNESS_PHYSICAL_CAPACITY_CONTACT_ATTACHED_CAD_MISSION_"
            "PRODUCTION_AND_FLIGHT_GATES_HOLD"
        ),
    }


def expected_validation_bytes() -> bytes:
    return json_bytes(build_validation())


def write_validation() -> None:
    VALIDATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    VALIDATION_PATH.write_bytes(expected_validation_bytes())


def check_validation() -> tuple[bool, list[str]]:
    mismatches: list[str] = []
    builder = load_builder()
    exact, builder_mismatches = builder.check_outputs()
    if not exact:
        mismatches.extend(f"builder:{item}" for item in builder_mismatches)
    expected = expected_validation_bytes()
    if not VALIDATION_PATH.is_file():
        mismatches.append("missing:validation")
    elif VALIDATION_PATH.read_bytes() != expected:
        mismatches.append("drift:validation")
    return not mismatches, mismatches


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    if args.check_only:
        passed, mismatches = check_validation()
        print(
            json.dumps(
                {"exact_reproduction": passed, "mismatches": mismatches},
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0 if passed else 1
    write_validation()
    validation = load(VALIDATION_PATH)
    print(
        json.dumps(
            {
                "verdict": validation["verdict"],
                "checks": (
                    f"{validation['checks_passed']}/{validation['checks_total']}"
                ),
                "negative_controls": (
                    f"{validation['negative_controls_passed']}/"
                    f"{validation['negative_controls_total']}"
                ),
                "gate": validation["gate"],
                "released_segments": validation["released_segments"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
