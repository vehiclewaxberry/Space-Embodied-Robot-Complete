"""Build the fail-closed Mechanical Loop Engineering Continuation V5.

V5 binds two bounded, non-release evidence packages to the immutable V4
continuation state:

* e21 detects the mixed B601 arm-placement contexts and closes only a current
  R2 deployed-locked rigid-wing, arm-only two-placement sensitivity plus a
  fixed-base leaf-only ROM reproduction.  It selects neither placement and
  does not close full R2 flexibility.
* Route-C C1.5 qualifies synthetic predicates and freezes a pre-CAD parameter
  space.  Physical capacity measurands remain null and the Route-C Gate stays
  UNKNOWN/HOLD.

No upstream geometry, URDF, CAD, mission, production, hardware or flight
authority is created by this builder.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[4]
ECR_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ECR_ROOT / "15_loop_continuation_v5"
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


SOURCES: tuple[tuple[str, str, str], ...] = (
    (
        "loop_v4_gate",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "ecr_b601_harness_rated_envelope/14_loop_continuation_v4/"
        "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V4.json",
        "B1D73BBCA80D231BAEEF9DAC8A0A2BD43248760FAB94E70375F9433513B2601D",
    ),
    (
        "loop_v4_brief",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "ecr_b601_harness_rated_envelope/14_loop_continuation_v4/"
        "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_BRIEF_V4.md",
        "B426041646CC1C154D1299E169A58C8D151E04C6DF45FE6D1158B32344A48A98",
    ),
    (
        "loop_v4_manifest",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "ecr_b601_harness_rated_envelope/14_loop_continuation_v4/"
        "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_OUTPUT_MANIFEST_V4.json",
        "15BE7086FF2D469695C942B9B729001F3ACAB504F58CFC828EDEC21E7F4269FD",
    ),
    (
        "loop_v4_validation",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "ecr_b601_harness_rated_envelope/14_loop_continuation_v4/"
        "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_VALIDATION_V4.json",
        "3E3F8375C1543AA59C98E5F7EF7F7DB029288856B3798769102EEDA7738354D7",
    ),
    (
        "e21_gate",
        "30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/"
        "results/E21_DIAGNOSTIC_GATE_V1.json",
        "B03B7C7AF571AA00FE3612756FFBBD99CB834B84377BA8DC2C213355C252616B",
    ),
    (
        "e21_validation",
        "30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/"
        "results/E21_VALIDATION_V1.json",
        "AF681C99C4A32E7A04EB83435FF8B4743D1BABC3A26E522A824B12142DC45825",
    ),
    (
        "e21_manifest",
        "30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/"
        "results/E21_OUTPUT_MANIFEST_V1.json",
        "8DA16F75AAE0AF359EEA597E1F279EEF8F6CEBBCA491DC4BF6D6F133810B580F",
    ),
    (
        "route_c_precad_gate",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "ecr_b601_harness_rated_envelope/08_route_c/"
        "02_pre_cad_parametric_guided_route_search/03_gate/"
        "ROUTE_C_PRECAD_PARAMETRIC_SEARCH_GATE_V1.json",
        "B43745081B4D0F2250993EBDB89074054B4A755C8A21555F9A42F0C392BCADCF",
    ),
    (
        "route_c_precad_validation",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "ecr_b601_harness_rated_envelope/08_route_c/"
        "02_pre_cad_parametric_guided_route_search/03_gate/"
        "ROUTE_C_PRECAD_PARAMETRIC_SEARCH_VALIDATION_V1.json",
        "84D89F631F7904DA955F7654AFE6DC06F8E5458A08AF410435808000A375FCAF",
    ),
    (
        "route_c_precad_manifest",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "ecr_b601_harness_rated_envelope/08_route_c/"
        "02_pre_cad_parametric_guided_route_search/03_gate/"
        "ROUTE_C_PRECAD_PARAMETRIC_SEARCH_OUTPUT_MANIFEST_V1.json",
        "7AE5015ED5E2DDE4B4F6F950B49147521DDB5960DDAB7142F8D0D57C9F4D3F0E",
    ),
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode("utf-8")


def load_json(relative: str) -> Any:
    return json.loads((PROJECT_ROOT / relative).read_text(encoding="utf-8"))


def source_path(name: str) -> str:
    for source_name, relative, _ in SOURCES:
        if source_name == name:
            return relative
    raise KeyError(name)


def binding_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for name, relative, expected in SOURCES:
        if (
            not expected
            or expected.startswith("PENDING_")
            or relative.startswith("PENDING_")
        ):
            raise RuntimeError(f"{name} is not frozen and hash-pinned")
        path = PROJECT_ROOT / relative
        if not path.is_file():
            raise RuntimeError(f"{name} source missing: {relative}")
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"{name} hash mismatch: {actual}")
        records.append(
            {
                "name": name,
                "path": relative,
                "sha256": actual,
                "bytes": path.stat().st_size,
            }
        )
    return records


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


def require_uniform(node: Any, key: str, expected: Any) -> Any:
    values = values_for_key(node, key)
    if not values:
        raise RuntimeError(f"required semantic missing: {key}")
    canonical = json.dumps(values[0], sort_keys=True, ensure_ascii=False)
    if any(
        json.dumps(value, sort_keys=True, ensure_ascii=False) != canonical
        for value in values[1:]
    ):
        raise RuntimeError(f"conflicting semantic values: {key}")
    if values[0] != expected:
        raise RuntimeError(f"semantic mismatch for {key}: {values[0]!r}")
    return copy.deepcopy(values[0])


def criterion_by_id(gate: Mapping[str, Any], criterion_id: str) -> Mapping[str, Any]:
    matches = [item for item in gate["criteria"] if item.get("id") == criterion_id]
    if len(matches) != 1:
        raise RuntimeError(f"criterion not unique: {criterion_id}")
    item = matches[0]
    if item.get("status") != "PASS" or item.get("passed") is not True:
        raise RuntimeError(f"criterion not PASS: {criterion_id}")
    return item


def require_v4(v4: Mapping[str, Any], validation: Mapping[str, Any]) -> None:
    if v4.get("schema") != "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V4":
        raise RuntimeError("V4 schema changed")
    if (
        v4.get("gate") != "HOLD"
        or v4.get("next_stage_authorized") is not False
        or v4.get("release_credit") is not False
        or v4.get("testing_pass_grants_authority") is not False
    ):
        raise RuntimeError("V4 authority boundary changed")
    if (
        validation.get("gate") != "HOLD"
        or validation.get("next_stage_authorized") is not False
        or validation.get("release_credit") is not False
        or not str(validation.get("verdict", "")).startswith("PASS_")
        or validation.get("checks_passed") != validation.get("checks_total")
        or validation.get("negative_controls_passed")
        != validation.get("negative_controls_total")
        or validation.get("deepcopy_per_mutation") is not True
        or validation.get("check_only_exact_reproduction") is not True
    ):
        raise RuntimeError("V4 validation boundary changed")


def require_e21(
    gate: Mapping[str, Any],
    validation: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    if gate.get("schema") != "E21_DIAGNOSTIC_GATE_V1":
        raise RuntimeError("e21 schema changed")
    if (
        gate.get("overall") != "HOLD"
        or gate.get("next_stage_authorized") is not False
        or gate.get("release_credit") is not False
        or gate.get("test_pass_grants_authority") is not False
        or gate.get("diagnostic_subcriteria_all_pass") is not True
    ):
        raise RuntimeError("e21 authority boundary changed")
    counts = gate.get("criterion_counts", {})
    if counts != {"total": 23, "pass": 23, "fail": 0}:
        raise RuntimeError("e21 Gate criterion count changed")

    mixed = criterion_by_id(gate, "E21-G04")["evidence"]
    if mixed != (
        "MIXED_LEDGER_ARM_PLACEMENT_CONTEXT_DETECTED__"
        "CONSUMPTION_SEMANTICS_UNRESOLVED_HOLD"
    ):
        raise RuntimeError("e21 mixed-context ruling changed")
    sensitivity = criterion_by_id(gate, "E21-G05")["evidence"]
    expected_sensitivity = {
        "branches_selected": False,
        "branches_averaged": False,
        "branch_delta_is_uncertainty": False,
        "single_placement_consumption_semantics_resolved": False,
    }
    for key, expected in expected_sensitivity.items():
        if sensitivity.get(key) is not expected:
            raise RuntimeError(f"e21 sensitivity boundary changed: {key}")
    scope = criterion_by_id(gate, "E21-G13")["evidence"]
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
        raise RuntimeError("e21 rigid arm-only scope changed")
    rom_conflict = criterion_by_id(gate, "E21-G21")["evidence"]
    if (
        rom_conflict.get("selected") is not False
        or rom_conflict.get("propagated_to_free_floating_dynamics") is not False
        or rom_conflict.get("dynamic_mass_allocation_frozen") is not False
    ):
        raise RuntimeError("e21 ROM conflict was promoted")
    rom_response = criterion_by_id(gate, "E21-G22")["evidence"]
    if any(rom_response.get(key) is not None for key in rom_response):
        raise RuntimeError("e21 ROM null response field was filled")

    holds = gate.get("mandatory_holds", {})
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
    if holds != required_holds:
        raise RuntimeError("e21 mandatory HOLD ledger changed")

    if (
        validation.get("status") != "PASS"
        or validation.get("criterion_counts")
        != {"total": 38, "pass": 38, "fail": 0}
        or validation.get("overall_authority") != "HOLD"
        or validation.get("next_stage_authorized") is not False
        or validation.get("test_pass_grants_authority") is not False
        or validation.get("gate_verdict_reproduced") != gate.get("verdict")
        or not validation.get("negative_controls")
        or any(
            item.get("deep_copy_used") is not True
            or item.get("mutation_detected") is not True
            or item.get("status") != "PASS"
            for item in validation["negative_controls"]
        )
    ):
        raise RuntimeError("e21 independent validation changed")
    if (
        manifest.get("authority") != "CURRENT_M7_R2_NON_RELEASE_DIAGNOSTIC_ONLY"
        or manifest.get("next_stage_authorized") is not False
        or manifest.get("release_credit") is not False
        or manifest.get("validation_included") is not True
        or manifest.get("manifest_self_reference_excluded") is not True
    ):
        raise RuntimeError("e21 manifest boundary changed")

    return {
        "mixed_context_state": mixed,
        "sensitivity": copy.deepcopy(sensitivity),
        "rom_conflict": copy.deepcopy(rom_conflict),
        "rom_response": copy.deepcopy(rom_response),
        "mandatory_holds": copy.deepcopy(holds),
        "criterion_counts": copy.deepcopy(counts),
        "validation_counts": copy.deepcopy(validation["criterion_counts"]),
        "negative_control_count": len(validation["negative_controls"]),
    }


def require_route_c(
    gate: Mapping[str, Any],
    validation: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Require frozen C1.5 evidence without assuming physical feasibility."""

    if gate.get("schema") != "ROUTE_C_PRECAD_PARAMETRIC_SEARCH_GATE_V1":
        raise RuntimeError("Route-C Gate schema changed")
    if gate.get("gate") != "UNKNOWN_FAIL_CLOSED":
        raise RuntimeError("Route-C Gate is not UNKNOWN_FAIL_CLOSED")
    if gate.get("verdict") != ROUTE_C_EXPECTED_VERDICT:
        raise RuntimeError("Route-C terminal verdict changed")
    if gate.get("authority_effect") != (
        "CLOSES_PREDICATE_QUALIFICATION_AND_PARAMETER_SEARCH_CONTRACT_ONLY"
    ):
        raise RuntimeError("Route-C authority effect changed")
    if (
        gate.get("next_stage_authorized") is not False
        or gate.get("cad_entry_authorized") is not False
        or gate.get("candidate_found") is not False
        or gate.get("route_b_disposition") != "REJECTED"
        or gate.get("source_hashes_all_match") is not True
    ):
        raise RuntimeError("Route-C authority or negative baseline changed")
    predicate = gate.get("predicate_qualification", {})
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
        raise RuntimeError("Route-C predicate qualification changed")
    parameter = gate.get("parameter_space", {})
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
        raise RuntimeError("Route-C parameter-space boundary changed")
    local_repro = gate.get("local_hash_bound_reproducibility", {})
    if (
        local_repro.get("all_match") is not True
        or local_repro.get("external_trust_anchor") is not False
        or local_repro.get("authority_pin_count") != 5
        or local_repro.get("binding_class")
        != "LOCAL_HASH_BOUND_REPRODUCIBILITY_AND_SELF_CONSISTENCY__NO_EXTERNAL_TRUST_ANCHOR"
    ):
        raise RuntimeError("Route-C local reproducibility boundary changed")

    capacity: dict[str, Any] = {}
    for key in NULL_CAPACITY_FIELDS:
        values = values_for_key(gate, key)
        if not values or any(value is not None for value in values):
            raise RuntimeError(f"Route-C physical capacity is not null: {key}")
        capacity[key] = None
    frontier = gate.get("physical_capacity_frontier", {})
    if (
        frontier.get("candidate_found") is not False
        or frontier.get("physical_candidates_evaluated") != 0
        or frontier.get("state") != "UNKNOWN_NOT_COMPUTABLE"
    ):
        raise RuntimeError("Route-C physical frontier was promoted")
    if gate.get("retained_holds") != ROUTE_C_RETAINED_HOLDS:
        raise RuntimeError("Route-C retained HOLD ledger changed")
    upstream = gate.get("upstream_gate_state", {})
    if upstream != {
        "CAD_entry_gate": "HOLD",
        "CAD_entry_verdict": "ROUTE_C_PARAMETRIC_CAD_ENTRY_NOT_AUTHORIZED",
        "MPI_controlled": 0,
        "MPI_gate": "HOLD",
        "MPI_total": 8,
        "ODR42": "PENDING",
    }:
        raise RuntimeError("Route-C upstream Gate state changed")

    deep = validation.get("deep_copy_negative_controls", {})
    if (
        validation.get("schema")
        != "ROUTE_C_PRECAD_PARAMETRIC_SEARCH_VALIDATION_V1"
        or validation.get("status")
        != "PASS_VALIDATION_OF_NON_RELEASE_C1_5_DIAGNOSTIC"
        or validation.get("checks_passed") != 26
        or validation.get("checks_total") != 26
        or validation.get("checks_failed") != []
        or validation.get("validated_gate") != "UNKNOWN_FAIL_CLOSED"
        or validation.get("validated_verdict") != ROUTE_C_EXPECTED_VERDICT
        or deep.get("all_passed") is not True
        or deep.get("controls_passed") != 48
        or deep.get("controls_total") != 48
        or deep.get("original_gate_unchanged_after_deep_copy_mutations")
        is not True
    ):
        raise RuntimeError("Route-C validation changed")
    parameter_null = validation.get("parameter_null_negative_controls", {})
    parameter_contract = validation.get(
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
        raise RuntimeError("Route-C parameter negative controls changed")
    if (
        manifest.get("schema")
        != "ROUTE_C_PRECAD_PARAMETRIC_SEARCH_OUTPUT_MANIFEST_V1"
        or manifest.get("status") != "FROZEN_NON_RELEASE_C1_5_DIAGNOSTIC_PACKAGE"
        or manifest.get("gate") != "UNKNOWN_FAIL_CLOSED"
        or manifest.get("verdict") != ROUTE_C_EXPECTED_VERDICT
        or manifest.get("next_stage_authorized") is not False
        or manifest.get("self_hash_policy")
        != "SELF_HASH_EXCLUDED_TO_AVOID_RECURSION"
    ):
        raise RuntimeError("Route-C manifest changed")

    return {
        "schema": gate.get("schema"),
        "verdict": gate.get("verdict"),
        "overall": gate.get("gate"),
        "physical_capacity_frontier": capacity,
        "released_segments": 0,
        "predicate_positive": "11/11",
        "predicate_negative": "36/36",
        "validation_checks": "26/26",
        "validation_deep_copy_controls": "48/48",
        "parameter_null_controls": "7/7",
        "parameter_contract_controls": "12/12",
        "external_trust_anchor": False,
    }


def build_gate() -> dict[str, Any]:
    bindings = binding_records()
    v4 = load_json(source_path("loop_v4_gate"))
    v4_validation = load_json(source_path("loop_v4_validation"))
    e21 = load_json(source_path("e21_gate"))
    e21_validation = load_json(source_path("e21_validation"))
    e21_manifest = load_json(source_path("e21_manifest"))
    route_gate = load_json(source_path("route_c_precad_gate"))
    route_validation = load_json(source_path("route_c_precad_validation"))
    route_manifest = load_json(source_path("route_c_precad_manifest"))

    require_v4(v4, v4_validation)
    e21_state = require_e21(e21, e21_validation, e21_manifest)
    route_state = require_route_c(route_gate, route_validation, route_manifest)

    current_release = copy.deepcopy(v4["current_release"])
    for key in (E21_EVALUATED_STATE, ROUTE_C_FROZEN_STATE):
        if key in current_release:
            raise RuntimeError(f"V4 already contains V5-only state: {key}")
        current_release[key] = True

    prior_false_keys = sorted(
        key for key, value in v4["current_release"].items() if value is False
    )
    facts = [
        {
            "id": "LC5-01",
            "name": "V4_GATE_BRIEF_MANIFEST_AND_VALIDATION_ARE_EXACTLY_HASH_BOUND",
            "observed": True,
            "evidence": {
                "schema": v4["schema"],
                "verdict": v4["verdict"],
                "gate": v4["gate"],
                "validation_checks": (
                    f"{v4_validation['checks_passed']}/"
                    f"{v4_validation['checks_total']}"
                ),
                "validation_negative_controls": (
                    f"{v4_validation['negative_controls_passed']}/"
                    f"{v4_validation['negative_controls_total']}"
                ),
            },
        },
        {
            "id": "LC5-02",
            "name": "E21_CURRENT_R2_NON_RELEASE_DIAGNOSTIC_IS_HASH_BOUND",
            "observed": True,
            "evidence": {
                "verdict": e21["verdict"],
                "overall": e21["overall"],
                "gate_criteria": e21_state["criterion_counts"],
                "validation_criteria": e21_state["validation_counts"],
                "validation_negative_controls": e21_state[
                    "negative_control_count"
                ],
            },
        },
        {
            "id": "LC5-03",
            "name": "BOTH_M7_LEDGER_GENERATIONS_MACHINE_DETECT_MIXED_ARM_PLACEMENT_CONTEXTS",
            "observed": True,
            "evidence": {
                "state": PLACEMENT_STATE,
                "e21_machine_state": e21_state["mixed_context_state"],
                "single_consumption_rule_resolved": False,
                "odr01_invalidated": False,
                "configuration_declared_mechanically_wrong": False,
            },
        },
        {
            "id": "LC5-04",
            "name": "CURRENT_R2_DEPLOYED_LOCKED_RIGID_WING_M07_TWO_PLACEMENT_SENSITIVITY_CLOSED",
            "observed": True,
            "evidence": {
                "branches_selected": e21_state["sensitivity"][
                    "branches_selected"
                ],
                "branches_averaged": e21_state["sensitivity"][
                    "branches_averaged"
                ],
                "branch_delta_is_uncertainty": e21_state["sensitivity"][
                    "branch_delta_is_uncertainty"
                ],
                "single_placement_consumption_semantics_resolved": e21_state[
                    "sensitivity"
                ]["single_placement_consumption_semantics_resolved"],
                "full_R2_flexible_coupling": False,
                "contact": False,
                "target_attached": False,
            },
        },
        {
            "id": "LC5-05",
            "name": "FIXED_BASE_LEAF_ONLY_ROM_REPRODUCTION_AND_NONSELCTED_MOVING_HINGE_CONFLICT_RECORDED",
            "observed": True,
            "evidence": {
                "fixed_base_leaf_only_rom_reproduction_closed": True,
                "moving_inter_hinge_mass_conflict_selected": e21_state[
                    "rom_conflict"
                ]["selected"],
                "moving_inter_hinge_mass_conflict_propagated": e21_state[
                    "rom_conflict"
                ]["propagated_to_free_floating_dynamics"],
                "dynamic_mass_allocation_frozen": e21_state["rom_conflict"]
                ["dynamic_mass_allocation_frozen"],
                "damping_matrix": e21_state["rom_response"]["damping_matrix"],
                "participation_factors": e21_state["rom_response"]
                ["participation_factors"],
                "forced_response": e21_state["rom_response"]["forced_response"],
            },
        },
        {
            "id": "LC5-06",
            "name": "R2_FULL_FLEX_AND_E15_CERTIFICATION_REMAIN_OPEN",
            "observed": True,
            "evidence": {
                "r2_full_flexible_coupling": e21_state["mandatory_holds"]
                ["r2_full_flexible_coupling"],
                "e15_ancf_certification": e21_state["mandatory_holds"]
                ["e15_ancf_certification"],
                "full_flex_ready": False,
            },
        },
        {
            "id": "LC5-07",
            "name": "R2_HARNESS_R2_HRN_04_REMAINS_FAIL_REDESIGN_REQUIRED",
            "observed": True,
            "evidence": {
                "R2_HRN_04": e21_state["mandatory_holds"]
                ["r2_harness_R2_HRN_04"],
                "harness_physical_capacity_released": False,
            },
        },
        {
            "id": "LC5-08",
            "name": "ROUTE_C_C15_PREDICATE_QUALIFICATION_AND_PARAMETER_SPACE_FROZEN",
            "observed": True,
            "evidence": {
                ROUTE_C_FROZEN_STATE: True,
                "route_c_schema": route_state["schema"],
                "route_c_verdict": route_state["verdict"],
                "route_c_overall": route_state["overall"],
                "predicate_positive_controls": route_state[
                    "predicate_positive"
                ],
                "predicate_negative_controls": route_state[
                    "predicate_negative"
                ],
                "validation_checks": route_state["validation_checks"],
                "validation_deep_copy_controls": route_state[
                    "validation_deep_copy_controls"
                ],
                "parameter_null_controls": route_state[
                    "parameter_null_controls"
                ],
                "parameter_contract_controls": route_state[
                    "parameter_contract_controls"
                ],
                "external_trust_anchor": route_state[
                    "external_trust_anchor"
                ],
                "physical_candidate_selected": False,
            },
        },
        {
            "id": "LC5-09",
            "name": "ROUTE_C_PHYSICAL_CAPACITY_FRONTIER_REMAINS_NULL_UNKNOWN_AND_HOLD",
            "observed": True,
            "evidence": {
                "physical_capacity_frontier": route_state[
                    "physical_capacity_frontier"
                ],
                "released_segments": route_state["released_segments"],
                "capacity_gate": "UNKNOWN_HOLD",
                "zero_fill_used": False,
            },
        },
        {
            "id": "LC5-10",
            "name": "ODR42_MPI_CAD_VENDOR_MISSION_PRODUCTION_HARDWARE_AND_FLIGHT_HOLDS_RETAINED",
            "observed": True,
            "evidence": {
                "odr42": "HOLD_PENDING",
                "mpi_controlled": 0,
                "mpi_total": 8,
                "cad": "HOLD",
                "vendor": "HOLD",
                "mission": "HOLD",
                "production": "HOLD",
                "hardware": "HOLD",
                "flight": "HOLD",
            },
        },
        {
            "id": "LC5-11",
            "name": "V4_STATE_IS_PRESERVED_WITH_EXACTLY_TWO_BOUNDED_NONRELEASE_TRUE_ADDITIONS",
            "observed": True,
            "evidence": {
                "existing_current_release_key_count": len(v4["current_release"]),
                "existing_fields_changed": [],
                "new_true_fields": [E21_EVALUATED_STATE, ROUTE_C_FROZEN_STATE],
                "prior_false_fields_preserved": prior_false_keys,
            },
        },
        {
            "id": "LC5-12",
            "name": "NO_GEOMETRY_OR_RELEASE_AUTHORITY_CREATED",
            "observed": True,
            "evidence": {
                "new_geometry_count": 0,
                "accepted_urdf_mutated": False,
                "solar_r2_mutated": False,
                "released_segments": 0,
                "mechanical_release_credit": False,
            },
        },
    ]

    return {
        "schema": "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V5",
        "generated_local": GENERATED_LOCAL,
        "authority_scope": (
            "HASH_BOUND_CURRENT_R2_DEPLOYED_LOCKED_RIGID_ARM_PLACEMENT_"
            "SENSITIVITY_FIXED_BASE_LEAF_ONLY_ROM_AND_ROUTE_C_C15_PRECAD_"
            "METHOD_CONTRACT__NONSELECTING_NONRELEASE_PRE_FULL_FLEX_PRE_"
            "CONTACT_PRE_ATTACHED_PRE_CAD_PRE_MISSION_PRE_PRODUCTION"
        ),
        "decision_rule": "Authority > later evidence > independent reproduction > opinion",
        "fail_closed_invariants": [
            "all V4 current-release fields remain byte-semantic exact",
            "mixed placement contexts are detected but no single dynamics consumption rule is selected",
            "the ODR-01 and WP11 placement branches are not selected averaged merged or treated as uncertainty",
            "the e21 free-floating execution uses current R2 deployed-locked rigid-wing residual properties and is arm-only",
            "fixed-base leaf-only ROM reproduction does not close moving-hinge mass allocation damping participation forced response or full R2 flexibility",
            "e15 remains REPEAT_ANCF_CERTIFICATION",
            "R2-HRN-04 remains FAIL_REDESIGN_REQUIRED",
            "Route-C C1.5 freezes only predicate qualification and a parameter-space contract",
            "all physical capacity-frontier measurands remain null and UNKNOWN/HOLD",
            "ODR-42 MPI product vendor CAD mission production hardware and flight authority remain HOLD",
            "test PASS grants no authority",
        ],
        "input_bindings": bindings,
        "facts": facts,
        "facts_total": len(facts),
        "facts_confirmed": sum(fact["observed"] for fact in facts),
        "state_transition": {
            "from_schema": v4["schema"],
            "prior_gate": v4["gate"],
            "existing_current_release_fields_preserved_exactly": True,
            "existing_current_release_fields_changed": [],
            "new_true_fields": [E21_EVALUATED_STATE, ROUTE_C_FROZEN_STATE],
            "new_true_field_count": 2,
            "additional_release_authority_created": False,
        },
        "current_release": current_release,
        "m7_r2_arm_placement_consumption": {
            "state": PLACEMENT_STATE,
            "mixed_context_detected": True,
            "both_ledger_generations_audited": True,
            "single_consumption_rule_resolved": False,
            "branch_selected": None,
            "branches_averaged": False,
            "branch_delta_is_uncertainty": False,
            "current_r2_deployed_locked_rigid_wing_m07_two_placement_sensitivity_closed": True,
            "r2_full_flexible_coupling": "NOT_EVALUATED",
            "acceptance_threshold_authority": None,
        },
        "fixed_base_r2_rom_boundary": {
            "leaf_only_published_rom_reproduction_closed": True,
            "moving_inter_hinge_mass_conflict_recorded": True,
            "moving_inter_hinge_mass_conflict_selected": False,
            "moving_inter_hinge_mass_conflict_propagated_to_free_floating_dynamics": False,
            "dynamic_mass_allocation_frozen": False,
            "damping_matrix": None,
            "participation_factors": None,
            "forced_response": None,
            "full_r2_flex_claimed": False,
        },
        "route_c_precad_method_contract": {
            "state": "PREDICATE_QUALIFICATION_AND_PARAMETER_SPACE_FROZEN",
            ROUTE_C_FROZEN_STATE: True,
            "physical_capacity_frontier": route_state[
                "physical_capacity_frontier"
            ],
            "physical_capacity_gate": "UNKNOWN_HOLD",
            "physical_route_c_candidate_selected": False,
            "topology_branches_averaged": False,
            "odr42_authorized": False,
            "mpi_controlled": 0,
            "mpi_total": 8,
            "cad_entry_authorized": False,
            "vendor_selected": False,
            "mission_coverage_released": False,
            "released_segments": 0,
        },
        "preserved_holds": {
            "single_arm_placement_consumption_rule": "UNRESOLVED",
            "r2_full_flexible_coupling": "NOT_EVALUATED",
            "e15_ancf_certification": "REPEAT_ANCF_CERTIFICATION",
            "r2_harness_R2_HRN_04": "FAIL_REDESIGN_REQUIRED",
            "physical_contact_ready": False,
            "attached_target_recovery_ready": False,
            "released_combined_mass_properties_ready": False,
            "cad_generation_authorized": False,
            "mission_trajectory_release_ready": False,
            "production_dynamics_ready": False,
            "hardware_motion_ready": False,
            "flight_qualification_ready": False,
        },
        "blocking_fronts": copy.deepcopy(v4["blocking_fronts"]),
        "shortest_engineering_sequence": [
            "Owner resolves one controlled B601 arm-placement consumption rule without averaging the two contexts",
            "freeze moving-hinge mass allocation and measured or bounded R2 stiffness damping participation inputs before a full-flex run",
            "repeat the required flexible certification chain and clear e15 independently",
            "redesign and re-evaluate R2-HRN-04 using physical geometry and controlled product data",
            "close ODR-42 and MPI-01 through MPI-08 before any Route-C CAD entry",
            "instantiate physical Route-C geometry and capacity evidence without replacing nulls by scan-axis values",
            "close contact target attachment mission production hardware and flight gates independently",
        ],
        "verdict": EXPECTED_VERDICT,
        "gate": "HOLD",
        "testing_pass_grants_authority": False,
        "unknown_uncertainties_zero_filled": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "released_segments": 0,
        "required_owner_statement": v4["required_owner_statement"],
        "prohibition": (
            "No single arm-placement rule, R2 full-flex, physical harness capacity, "
            "contact, attached-target recovery, Route-C CAD, mission, production, "
            "hardware, manufacturing, qualification, or flight claim from V5."
        ),
    }


def build_brief(gate: Mapping[str, Any]) -> str:
    return f"""# 机械 Loop Engineering 续接裁决 V5

## 本轮闭合的非释放证据

- V5 Gate 的顶层 schema、12 条事实、权限与人类裁决字段、HOLD 账本、阻断前沿及最短工程顺序均已纳入 exact canonical fail-closed 校验；新增平行 authority/release/CAD/capacity 字段会被拒绝。
- V5 manifest 的 Gate/Brief 输出及 builder/validator source 记录均按运行时 path/SHA-256/bytes 精确闭合；validation 按明确 self-hash policy 排除，避免递归自引用。
- e21 已机器检测 M7 V2 与 V3_R2 账本中的 B601 臂放置上下文混用，并完成 current-R2、双翼 deployed-locked rigid、M07 arm-only 的两放置分支敏感性诊断。该差值不是统计不确定度，两个分支没有选择、平均或合并。
- fixed-base leaf-only R2 ROM 已复现；moving inter-hinge mass 冲突被记录但未选择、未传播到自由漂浮动力学。阻尼矩阵、参与因子与受迫响应仍为 `null`。
- Route-C C1.5 仅完成合成谓词资格检查和参数空间合同冻结。全部物理容量前沿字段仍为 `null`，released segments 仍为 `0`，不能解释为找到或选择了物理 Route-C 候选。

机器裁决：`{gate['verdict']}`

## 关键工程裁决

- 臂放置消费状态：`{PLACEMENT_STATE}`。这表示“已经评估并检测到混用”，不表示 single placement 已协调或授权。
- e21 自由漂浮结果只覆盖 current R2 deployed-locked rigid-wing + M07 arm-only；不覆盖 R2 full-flex、接触、目标附着、锁定、恢复或任务序列。
- e15 仍为 `REPEAT_ANCF_CERTIFICATION`；`R2-HRN-04=FAIL_REDESIGN_REQUIRED`。
- Route-C physical capacity、ODR-42、MPI 0/8、产品/vendor、CAD、任务、生产、硬件与飞行均保持 UNKNOWN/HOLD。

## 下一最短闭环

先由 Owner 冻结唯一的 B601 arm-placement consumption rule；随后冻结 moving-hinge mass allocation 与受控 R2 柔性参数并重过 e15。线束侧先完成 R2-HRN-04 重设计，再关闭 ODR-42 和 MPI-01..MPI-08，之后才能进入独立版本 Route-C CAD 与物理容量验证。

测试 PASS 不授予 authority。总体 `gate=HOLD`、`next_stage_authorized=false`、`release_credit=false`、`released_segments=0`。
"""


def script_records() -> list[dict[str, Any]]:
    scripts = [
        Path(__file__).resolve(),
        Path(__file__).resolve().with_name(
            "validate_mechanical_loop_continuation_v5.py"
        ),
    ]
    records = []
    for path in scripts:
        if not path.is_file():
            raise RuntimeError(f"required V5 script missing: {path}")
        records.append(
            {
                "name": path.stem,
                "path": path.relative_to(PROJECT_ROOT).as_posix(),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )
    return records


def artifact_bytes() -> dict[Path, bytes]:
    gate = build_gate()
    gate_data = json_bytes(gate)
    brief_data = build_brief(gate).encode("utf-8")
    gate_path = OUTPUT_ROOT / "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V5.json"
    brief_path = OUTPUT_ROOT / "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_BRIEF_V5.md"
    manifest_path = (
        OUTPUT_ROOT
        / "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_OUTPUT_MANIFEST_V5.json"
    )
    output_records = []
    for path, data in ((gate_path, gate_data), (brief_path, brief_data)):
        output_records.append(
            {
                "path": path.relative_to(PROJECT_ROOT).as_posix(),
                "sha256": sha256_bytes(data),
                "bytes": len(data),
            }
        )
    sources = binding_records() + script_records()
    manifest = {
        "schema": "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_OUTPUT_MANIFEST_V5",
        "generated_local": GENERATED_LOCAL,
        "outputs": output_records,
        "sources": sources,
        "output_count": len(output_records),
        "source_count": len(sources),
        "validation_report_excluded_to_avoid_self_hash": True,
        "self_hash_policy": "VALIDATION_REPORT_EXCLUDED_TO_AVOID_SELF_REFERENCE",
        "verdict": EXPECTED_VERDICT,
        "gate": "HOLD",
        "next_stage_authorized": False,
        "release_credit": False,
        "released_segments": 0,
    }
    return {
        gate_path: gate_data,
        brief_path: brief_data,
        manifest_path: json_bytes(manifest),
    }


def write_outputs() -> None:
    artifacts = artifact_bytes()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    for path, data in artifacts.items():
        path.write_bytes(data)


def check_outputs() -> tuple[bool, list[str]]:
    mismatches: list[str] = []
    for path, expected in artifact_bytes().items():
        if not path.is_file():
            mismatches.append(f"missing:{path.relative_to(PROJECT_ROOT).as_posix()}")
        elif path.read_bytes() != expected:
            mismatches.append(f"drift:{path.relative_to(PROJECT_ROOT).as_posix()}")
    return not mismatches, mismatches


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    if args.check_only:
        passed, mismatches = check_outputs()
        print(
            json.dumps(
                {"exact_reproduction": passed, "mismatches": mismatches},
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0 if passed else 1
    write_outputs()
    gate = json.loads(
        (
            OUTPUT_ROOT / "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V5.json"
        ).read_text(encoding="utf-8")
    )
    print(
        json.dumps(
            {
                "verdict": gate["verdict"],
                "facts": f"{gate['facts_confirmed']}/{gate['facts_total']}",
                "gate": gate["gate"],
                "release_credit": gate["release_credit"],
                "released_segments": gate["released_segments"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
