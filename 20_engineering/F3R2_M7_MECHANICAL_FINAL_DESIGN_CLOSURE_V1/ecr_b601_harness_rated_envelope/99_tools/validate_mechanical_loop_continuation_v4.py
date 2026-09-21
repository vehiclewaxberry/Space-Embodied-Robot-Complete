"""Independent fail-closed validation for Mechanical Loop Continuation V4."""

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
OUTPUT_ROOT = ECR_ROOT / "14_loop_continuation_v4"
GATE_PATH = OUTPUT_ROOT / "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V4.json"
BRIEF_PATH = OUTPUT_ROOT / "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_BRIEF_V4.md"
MANIFEST_PATH = (
    OUTPUT_ROOT / "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_OUTPUT_MANIFEST_V4.json"
)
VALIDATION_PATH = (
    OUTPUT_ROOT / "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_VALIDATION_V4.json"
)
BUILDER_PATH = Path(__file__).resolve().with_name(
    "build_mechanical_loop_continuation_v4.py"
)
GENERATED_LOCAL = "2026-08-23T23:45:00+08:00"
NEW_CLOSED_STATE = (
    "independent_surrogate_mass_branch_sim11_coupled_arm_only_"
    "diagnostic_execution_closed"
)
EXPECTED_VERDICT = (
    "MECHANICAL_LOOP_ENGINEERING_CONTINUES_WITH_INDEPENDENT_SURROGATE_MASS_"
    "BRANCH_SIM11_COUPLED_ARM_ONLY_DIAGNOSTIC_EXECUTION_CLOSED__M4_SYSTEM_"
    "MASS_INERTIA_E15_PHYSICAL_MOUNT_CONTACT_ATTACHED_CAD_MISSION_PRODUCTION_"
    "AND_FLIGHT_HOLD"
)
URDF_SHA = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
SOLAR_SHA = "21FF77B882DBFAB87B3E77DD56817EFC7F321C68E30AFEDCDDBB4D79B9915795"
EXPECTED_INPUT_NAMES = {
    "loop_v3_gate",
    "loop_v3_validation",
    "loop_v3_manifest",
    "e20_gate",
    "e20_validation",
    "e20_manifest",
    "e15_ancf_gate",
    "sim11_historical_gate",
    "m7_owner_decision_register",
    "m7_wp2_system_mass_properties_v2",
    "m4_named_pose_revalidation",
    "accepted_urdf",
    "solar_r2",
}
EXPECTED_SCRIPT_NAMES = {
    "build_mechanical_loop_continuation_v4",
    "validate_mechanical_loop_continuation_v4",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode("utf-8")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_builder() -> ModuleType:
    spec = importlib.util.spec_from_file_location("loop_v4_builder", BUILDER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load V4 builder")
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


def uniform_semantic(node: Any, key: str) -> Any:
    values = values_for_key(node, key)
    if not values:
        raise KeyError(key)
    canonical = json.dumps(values[0], sort_keys=True, ensure_ascii=False)
    if any(
        json.dumps(value, sort_keys=True, ensure_ascii=False) != canonical
        for value in values[1:]
    ):
        raise ValueError(f"conflicting values for {key}")
    return values[0]


def set_first_key(node: Any, key: str, value: Any) -> bool:
    if isinstance(node, dict):
        if key in node:
            node[key] = value
            return True
        return any(set_first_key(child, key, value) for child in node.values())
    if isinstance(node, list):
        return any(set_first_key(child, key, value) for child in node)
    return False


def source_bundle(gate: Mapping[str, Any], manifest: Mapping[str, Any]) -> dict[str, Any]:
    by_name = {item["name"]: item for item in gate["input_bindings"]}

    def source(name: str) -> Any:
        return load(PROJECT_ROOT / by_name[name]["path"])

    return {
        "gate": gate,
        "manifest": manifest,
        "v3": source("loop_v3_gate"),
        "v3_validation": source("loop_v3_validation"),
        "v3_manifest": source("loop_v3_manifest"),
        "e20": source("e20_gate"),
        "e20_validation": source("e20_validation"),
        "e20_manifest": source("e20_manifest"),
        "e15": source("e15_ancf_gate"),
        "sim11": source("sim11_historical_gate"),
    }


def gate_safe(bundle: Mapping[str, Any]) -> bool:
    try:
        gate = bundle["gate"]
        manifest = bundle["manifest"]
        v3 = bundle["v3"]
        v3_validation = bundle["v3_validation"]
        e20 = bundle["e20"]
        e20_validation = bundle["e20_validation"]
        e20_manifest = bundle["e20_manifest"]
        e15 = bundle["e15"]
        sim11 = bundle["sim11"]

        if gate["schema"] != "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V4":
            return False
        if gate["verdict"] != EXPECTED_VERDICT or gate["gate"] != "HOLD":
            return False
        if gate["next_stage_authorized"] is not False:
            return False
        if gate["release_credit"] is not False:
            return False
        if gate["testing_pass_grants_authority"] is not False:
            return False
        if gate["facts_total"] != 10 or gate["facts_confirmed"] != 10:
            return False
        if len(gate["facts"]) != 10:
            return False
        if any(fact["observed"] is not True for fact in gate["facts"]):
            return False

        bindings = gate["input_bindings"]
        if len(bindings) != len(EXPECTED_INPUT_NAMES):
            return False
        by_name = {item["name"]: item for item in bindings}
        if set(by_name) != EXPECTED_INPUT_NAMES:
            return False
        if any(
            not item.get("sha256")
            or len(item["sha256"]) != 64
            or item.get("bytes", 0) <= 0
            or not item.get("path")
            for item in bindings
        ):
            return False

        manifest_sources = {item["name"]: item for item in manifest["sources"]}
        if set(manifest_sources) != EXPECTED_INPUT_NAMES | EXPECTED_SCRIPT_NAMES:
            return False
        if any(
            manifest_sources[name]["path"] != record["path"]
            or manifest_sources[name]["sha256"] != record["sha256"]
            or manifest_sources[name]["bytes"] != record["bytes"]
            for name, record in by_name.items()
        ):
            return False
        if by_name["accepted_urdf"]["sha256"] != URDF_SHA:
            return False
        if by_name["solar_r2"]["sha256"] != SOLAR_SHA:
            return False

        if v3["schema"] != "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V3":
            return False
        if v3["gate"] != "HOLD":
            return False
        if v3["next_stage_authorized"] is not False:
            return False
        if v3["release_credit"] is not False:
            return False
        if not v3_validation["verdict"].startswith("PASS_"):
            return False
        if v3_validation["checks_passed"] != v3_validation["checks_total"]:
            return False
        if (
            v3_validation["negative_controls_passed"]
            != v3_validation["negative_controls_total"]
        ):
            return False
        v3_facts = {fact["id"]: fact for fact in v3["facts"]}
        if v3_facts["LC3-04"]["evidence"]["acceptance_threshold_authority"] is not None:
            return False
        if v3_facts["LC3-06"]["evidence"]["physical_contact_fields"] is not None:
            return False
        if v3_facts["LC3-07"]["evidence"]["acceptance_threshold_authority"] is not None:
            return False
        if v3_facts["LC3-08"]["evidence"]["locked_transform_gripper_to_target"] is not None:
            return False
        if v3["diagnostic_design_observations"]["acceptance_threshold_authority"] is not None:
            return False

        current = gate["current_release"]
        prior = v3["current_release"]
        if set(current) != set(prior) | {NEW_CLOSED_STATE}:
            return False
        if any(current[key] != value for key, value in prior.items()):
            return False
        if current[NEW_CLOSED_STATE] is not True:
            return False
        transition = gate["state_transition"]
        if transition["from_schema"] != v3["schema"]:
            return False
        if transition["prior_gate"] != "HOLD":
            return False
        if transition["existing_current_release_fields_preserved_exactly"] is not True:
            return False
        if transition["existing_current_release_fields_changed"] != []:
            return False
        if transition["only_new_closed_state"] != NEW_CLOSED_STATE:
            return False
        if transition["only_new_closed_state_value"] is not True:
            return False
        if transition["additional_authority_created"] is not False:
            return False

        e20_expected = {
            NEW_CLOSED_STATE: True,
            "mass_completion_rule": "UNIFORM_BUS_DENSITY_SCALAR_CLOSURE_SURROGATE",
            "bus_only_mass_and_inertia_scaled": True,
            "mount_frame_model": "M_DYNAMICS_LEGACY_NUMERICAL",
            "physical_mount_frame_applied": False,
            "physical_mount_transform": None,
            "m4_digital_prototype_installation_dynamics_claimed": False,
            "current_M7_unique_dynamics_M_consumed": False,
            "current_M7_design_dynamics_closure_claimed": False,
            "scene_A2_invoked": False,
            "contact_window_invoked": False,
            "attached_target_propagated": False,
            "selected_mass_branch": None,
            "physical_contact_ready": False,
            "mission_release_ready": False,
            "mechanical_design_released": False,
            "production_dynamics_ready": False,
            "hardware_motion_ready": False,
            "flight_qualification_ready": False,
        }
        if any(uniform_semantic(e20, key) != value for key, value in e20_expected.items()):
            return False
        if e20["gate"] != "HOLD":
            return False
        if e20["next_stage_authorized"] is not False:
            return False
        if e20["release_credit"] is not False:
            return False
        if e20["testing_pass_grants_authority"] is not False:
            return False
        if e20_validation["positive_passed"] != e20_validation["positive_total"]:
            return False
        if (
            e20_validation["negative_rejected"]
            != e20_validation["negative_total"]
        ):
            return False
        if not e20_validation["verdict"].startswith("PASS_"):
            return False
        if e20_manifest["gate"] != "HOLD":
            return False
        if e20_manifest["next_stage_authorized"] is not False:
            return False
        if e20_manifest["release_credit"] is not False:
            return False

        if e15["overall"] != "REPEAT_ANCF_CERTIFICATION":
            return False
        if e15["cross_solver_diagnostic"]["all_lt_5pct"] is not False:
            return False
        if e15["cross_solver_diagnostic"]["max_relative_difference"] <= 0.05:
            return False
        if e15["final_candidate_cross_solver"]["available"] is not False:
            return False
        if e15["final_candidate_cross_solver"]["max_relative_difference"] is not None:
            return False
        if sim11["verdict"] != "SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS":
            return False
        if sim11["PROVISIONAL_PARAMS"] is not True:
            return False

        facts = {fact["id"]: fact for fact in gate["facts"]}
        if set(facts) != {f"LC4-{index:02d}" for index in range(1, 11)}:
            return False
        if facts["LC4-01"]["evidence"]["gate"] != "HOLD":
            return False
        if facts["LC4-01"]["evidence"]["next_stage_authorized"] is not False:
            return False
        if facts["LC4-02"]["evidence"][NEW_CLOSED_STATE] is not True:
            return False
        if facts["LC4-02"]["evidence"]["gate"] != "HOLD":
            return False
        expected_checks = f"{e20_validation['positive_passed']}/{e20_validation['positive_total']}"
        expected_negatives = (
            f"{e20_validation['negative_rejected']}/"
            f"{e20_validation['negative_total']}"
        )
        if facts["LC4-03"]["evidence"]["checks"] != expected_checks:
            return False
        if facts["LC4-03"]["evidence"]["negative_controls"] != expected_negatives:
            return False
        if facts["LC4-04"]["evidence"]["released_system_mass_cg_inertia_authority"] is not False:
            return False
        if facts["LC4-04"]["evidence"]["branch_selection_or_averaging_credit"] is not False:
            return False
        if facts["LC4-05"]["evidence"]["physical_mount_transform"] is not None:
            return False
        if facts["LC4-05"]["evidence"]["m4_digital_prototype_installation_dynamics_claimed"] is not False:
            return False
        if facts["LC4-05"]["evidence"]["m7_odr01_dynamics_T_SM_translation_mm"] != [185.25, 0.0, 0.0]:
            return False
        if facts["LC4-05"]["evidence"]["m7_odr01_dynamics_T_SM_rotation"] != "Ry(+90deg)":
            return False
        if facts["LC4-05"]["evidence"]["numerically_matches_odr01_dynamics_convention"] is not True:
            return False
        if facts["LC4-05"]["evidence"]["current_M7_unique_dynamics_M_consumed"] is not False:
            return False
        if facts["LC4-05"]["evidence"]["current_M7_design_dynamics_closure_claimed"] is not False:
            return False
        if facts["LC4-05"]["evidence"]["cad_geometry_mount_context_x_mm"] != 208.0:
            return False
        if facts["LC4-05"]["evidence"]["cad_geometry_mount_context_clock_deg"] != 25.000014:
            return False
        if facts["LC4-05"]["evidence"]["dynamics_and_cad_geometry_contexts_separate"] is not True:
            return False
        if facts["LC4-05"]["evidence"]["m7_frame_to_mass_reconciliation_state"] != "M7_FRAME_TO_MASS_RECONCILIATION_NOT_EVALUATED_IN_E20":
            return False
        if any(facts["LC4-06"]["evidence"].values()):
            return False
        if facts["LC4-07"]["evidence"]["overall"] != "REPEAT_ANCF_CERTIFICATION":
            return False
        if (
            facts["LC4-07"]["evidence"]["max_relative_difference"]
            != e15["cross_solver_diagnostic"]["max_relative_difference"]
        ):
            return False
        if (
            facts["LC4-07"]["evidence"]["gate_limit"]
            != e15["final_candidate_cross_solver"]["gate_limit"]
        ):
            return False
        if facts["LC4-07"]["evidence"]["final_candidate_available"] is not False:
            return False
        if facts["LC4-08"]["evidence"]["PROVISIONAL_PARAMS"] is not True:
            return False
        prior_false_keys = sorted(key for key, value in prior.items() if value is False)
        state_fact = facts["LC4-09"]["evidence"]
        if state_fact["existing_current_release_key_count"] != len(prior):
            return False
        if state_fact["existing_fields_changed"] != []:
            return False
        if state_fact["new_true_fields"] != [NEW_CLOSED_STATE]:
            return False
        if state_fact["prior_false_fields_preserved"] != prior_false_keys:
            return False
        immutable = facts["LC4-10"]["evidence"]
        if immutable["accepted_urdf_sha256"] != URDF_SHA:
            return False
        if immutable["solar_r2_sha256"] != SOLAR_SHA:
            return False
        if immutable["new_geometry_count"] != 0:
            return False

        boundary = gate["surrogate_model_boundary"]
        if boundary["mass_completion_rule"] != "UNIFORM_BUS_DENSITY_SCALAR_CLOSURE_SURROGATE":
            return False
        if boundary["bus_only_mass_and_inertia_scaled"] is not True:
            return False
        if boundary["mass_completion_is_artificial_scalar_surrogate"] is not True:
            return False
        if boundary["released_system_mass_cg_inertia_authority"] is not False:
            return False
        if boundary["mount_frame_model"] != "M_DYNAMICS_LEGACY_NUMERICAL":
            return False
        if boundary["physical_mount_frame_applied"] is not False:
            return False
        if boundary["physical_mount_transform"] is not None:
            return False
        if boundary["m4_digital_prototype_installation_dynamics_claimed"] is not False:
            return False
        if boundary["m7_current_design_mass_dynamics_claimed"] is not False:
            return False
        if boundary["e20_current_M7_unique_dynamics_M_consumed"] is not False:
            return False
        if boundary["e20_current_M7_design_dynamics_closure_claimed"] is not False:
            return False
        if boundary["acceptance_threshold_authority"] is not None:
            return False
        if boundary["mechanical_design_release_credit"] is not False:
            return False

        consistency = gate["upstream_consistency_hold"]
        if consistency["state"] != "M7_FRAME_TO_MASS_RECONCILIATION_NOT_EVALUATED_IN_E20":
            return False
        if consistency["m7_odr01_dynamics_T_SM_translation_mm"] != [185.25, 0.0, 0.0]:
            return False
        if consistency["m7_odr01_dynamics_T_SM_rotation"] != "Ry(+90deg)":
            return False
        if consistency["m_dynamics_physical_entity"] is not False:
            return False
        if consistency["cad_geometry_mount_context_x_mm"] != 208.0:
            return False
        if consistency["cad_geometry_mount_context_clock_deg"] != 25.000014:
            return False
        if consistency["contexts_are_separate"] is not True:
            return False
        if consistency["independent_configuration_recomputation_completed_in_e20"] is not False:
            return False
        if consistency["reconciliation_closed"] is not False:
            return False
        if consistency["m7_current_design_mass_dynamics_upgrade"] is not False:
            return False
        if consistency["required_next_evidence"] != "E21_FRAME_TO_MASS_RECONCILIATION":
            return False
        if consistency["source_binding_names"] != [
            "m7_owner_decision_register",
            "m7_wp2_system_mass_properties_v2",
            "m4_named_pose_revalidation",
        ]:
            return False

        holds = gate["preserved_holds"]
        if holds["e15_ancf_certification"] != "REPEAT_ANCF_CERTIFICATION":
            return False
        if holds["sim11_panel_and_contact_parameters_provisional"] is not True:
            return False
        if holds["m7_frame_to_mass_reconciliation"] != "M7_FRAME_TO_MASS_RECONCILIATION_NOT_EVALUATED_IN_E20":
            return False
        false_holds = [
            "physical_contact_ready",
            "attached_target_recovery_ready",
            "released_combined_mass_properties_ready",
            "cad_generation_authorized",
            "mission_trajectory_release_ready",
            "production_dynamics_ready",
            "hardware_motion_ready",
            "flight_qualification_ready",
        ]
        if any(holds[name] is not False for name in false_holds):
            return False
        if gate["blocking_fronts"] != v3["blocking_fronts"]:
            return False
        if gate["required_owner_statement"] != v3["required_owner_statement"]:
            return False

        if manifest["schema"] != "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_OUTPUT_MANIFEST_V4":
            return False
        if manifest["output_count"] != 2:
            return False
        if manifest["source_count"] != len(EXPECTED_INPUT_NAMES | EXPECTED_SCRIPT_NAMES):
            return False
        if len(manifest["outputs"]) != 2 or len(manifest["sources"]) != manifest["source_count"]:
            return False
        output_paths = {item["path"] for item in manifest["outputs"]}
        expected_outputs = {
            GATE_PATH.relative_to(PROJECT_ROOT).as_posix(),
            BRIEF_PATH.relative_to(PROJECT_ROOT).as_posix(),
        }
        if output_paths != expected_outputs:
            return False
        if any(item.get("bytes", 0) <= 0 or len(item.get("sha256", "")) != 64 for item in manifest["outputs"]):
            return False
        if manifest["validation_report_excluded_to_avoid_self_hash"] is not True:
            return False
        if manifest["gate"] != "HOLD":
            return False
        if manifest["next_stage_authorized"] is not False:
            return False
        if manifest["release_credit"] is not False:
            return False
        validation_rel = VALIDATION_PATH.relative_to(PROJECT_ROOT).as_posix()
        if any(item["path"] == validation_rel for item in manifest["outputs"] + manifest["sources"]):
            return False
        return True
    except (KeyError, TypeError, ValueError, IndexError, AttributeError):
        return False


def validate() -> dict[str, Any]:
    gate = load(GATE_PATH)
    manifest = load(MANIFEST_PATH)
    bundle = source_bundle(gate, manifest)
    checks: list[dict[str, Any]] = []

    def check(identifier: str, observed: bool, detail: Any) -> None:
        checks.append({"id": identifier, "pass": bool(observed), "detail": detail})

    check("GATE_SAFE_BASELINE", gate_safe(copy.deepcopy(bundle)), gate["verdict"])
    for record in gate["input_bindings"]:
        path = PROJECT_ROOT / record["path"]
        check(
            f"INPUT_HASH_{record['name']}",
            path.is_file()
            and sha256(path) == record["sha256"]
            and path.stat().st_size == record["bytes"],
            record["path"],
        )
    for record in manifest["outputs"]:
        path = PROJECT_ROOT / record["path"]
        check(
            f"OUTPUT_HASH_{Path(record['path']).stem}",
            path.is_file()
            and sha256(path) == record["sha256"]
            and path.stat().st_size == record["bytes"],
            record["path"],
        )
    for record in manifest["sources"]:
        path = PROJECT_ROOT / record["path"]
        check(
            f"MANIFEST_SOURCE_HASH_{record['name']}",
            path.is_file()
            and sha256(path) == record["sha256"]
            and path.stat().st_size == record["bytes"],
            record["path"],
        )

    builder = load_builder()
    expected_artifacts = builder.artifact_bytes()
    for path, expected in expected_artifacts.items():
        check(
            f"CHECK_ONLY_EXACT_{path.stem}",
            path.is_file() and path.read_bytes() == expected,
            path.relative_to(PROJECT_ROOT).as_posix(),
        )
    builder_exact, builder_mismatches = builder.check_outputs()
    check("BUILDER_CHECK_ONLY_EXACT_REPRODUCTION", builder_exact, builder_mismatches)
    validation_rel = VALIDATION_PATH.relative_to(PROJECT_ROOT).as_posix()
    check(
        "NO_VALIDATION_SELF_HASH",
        all(
            item["path"] != validation_rel
            for item in manifest["outputs"] + manifest["sources"]
        ),
        validation_rel,
    )
    pycache_paths = sorted(
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in ECR_ROOT.rglob("__pycache__")
    )
    check("NO_PYCACHE", not pycache_paths, pycache_paths)
    check(
        "ONLY_ONE_NEW_CURRENT_RELEASE_STATE",
        set(gate["current_release"])
        == set(bundle["v3"]["current_release"]) | {NEW_CLOSED_STATE}
        and all(
            gate["current_release"][key] == value
            for key, value in bundle["v3"]["current_release"].items()
        )
        and gate["current_release"][NEW_CLOSED_STATE] is True,
        NEW_CLOSED_STATE,
    )

    mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = []

    def add(identifier: str, mutation: Callable[[dict[str, Any]], None]) -> None:
        mutations.append((identifier, mutation))

    add("VERDICT_DRIFT", lambda b: b["gate"].__setitem__("verdict", "PASS"))
    add("GATE_PROMOTED", lambda b: b["gate"].__setitem__("gate", "PASS"))
    add("NEXT_STAGE_TRUE", lambda b: b["gate"].__setitem__("next_stage_authorized", True))
    add("RELEASE_CREDIT_TRUE", lambda b: b["gate"].__setitem__("release_credit", True))
    add("TEST_PASS_AUTHORITY_TRUE", lambda b: b["gate"].__setitem__("testing_pass_grants_authority", True))
    add("FACT_REMOVED", lambda b: b["gate"]["facts"].pop())
    add("FACT_FALSE", lambda b: b["gate"]["facts"][0].__setitem__("observed", False))
    add("FACT_COUNT_DRIFT", lambda b: b["gate"].__setitem__("facts_total", 9))
    add("INPUT_REMOVED", lambda b: b["gate"]["input_bindings"].pop())
    add("INPUT_HASH_DRIFT", lambda b: b["gate"]["input_bindings"][0].__setitem__("sha256", "0" * 64))
    add("INPUT_BYTES_ZERO", lambda b: b["gate"]["input_bindings"][0].__setitem__("bytes", 0))
    add("INPUT_PATH_BLANK", lambda b: b["gate"]["input_bindings"][0].__setitem__("path", ""))
    add("MANIFEST_GATE_PROMOTED", lambda b: b["manifest"].__setitem__("gate", "PASS"))
    add("MANIFEST_NEXT_TRUE", lambda b: b["manifest"].__setitem__("next_stage_authorized", True))
    add("MANIFEST_RELEASE_TRUE", lambda b: b["manifest"].__setitem__("release_credit", True))
    add("MANIFEST_OUTPUT_COUNT", lambda b: b["manifest"].__setitem__("output_count", 1))
    add("MANIFEST_SOURCE_COUNT", lambda b: b["manifest"].__setitem__("source_count", 11))
    add("MANIFEST_VALIDATION_INCLUDED", lambda b: b["manifest"].__setitem__("validation_report_excluded_to_avoid_self_hash", False))
    add("MANIFEST_OUTPUT_REMOVED", lambda b: b["manifest"]["outputs"].pop())
    add("MANIFEST_SOURCE_REMOVED", lambda b: b["manifest"]["sources"].pop())
    add("MANIFEST_SOURCE_HASH_DRIFT", lambda b: b["manifest"]["sources"][0].__setitem__("sha256", "0" * 64))
    add("V3_GATE_PROMOTED", lambda b: b["v3"].__setitem__("gate", "PASS"))
    add("V3_NEXT_TRUE", lambda b: b["v3"].__setitem__("next_stage_authorized", True))
    add("V3_RELEASE_TRUE", lambda b: b["v3"].__setitem__("release_credit", True))
    add("V3_FALSE_STATE_TRUE", lambda b: b["v3"]["current_release"].__setitem__("physical_contact_ready", True))
    add("V3_NULL_THRESHOLD_FILLED", lambda b: b["v3"]["diagnostic_design_observations"].__setitem__("acceptance_threshold_authority", 1.0))
    add("V3_NULL_CONTACT_FILLED", lambda b: b["v3"]["facts"][5]["evidence"].__setitem__("physical_contact_fields", 0.0))
    add("V3_VALIDATION_FAIL", lambda b: b["v3_validation"].__setitem__("verdict", "FAIL"))
    add("V3_VALIDATION_CHECK_LOSS", lambda b: b["v3_validation"].__setitem__("checks_passed", b["v3_validation"]["checks_total"] - 1))
    add("E20_NEW_STATE_FALSE", lambda b: set_first_key(b["e20"], NEW_CLOSED_STATE, False))
    add("E20_MASS_RULE_DRIFT", lambda b: set_first_key(b["e20"], "mass_completion_rule", "AVERAGE"))
    add("E20_BUS_SCALE_FALSE", lambda b: set_first_key(b["e20"], "bus_only_mass_and_inertia_scaled", False))
    add("E20_MOUNT_PROMOTED", lambda b: set_first_key(b["e20"], "mount_frame_model", "B601_ARM_BASE_PHYSICAL"))
    add("E20_PHYSICAL_MOUNT_APPLIED", lambda b: set_first_key(b["e20"], "physical_mount_frame_applied", True))
    add("E20_PHYSICAL_TRANSFORM_FILLED", lambda b: set_first_key(b["e20"], "physical_mount_transform", [[1, 0, 0, 0]]))
    add("E20_M4_CLAIM_TRUE", lambda b: set_first_key(b["e20"], "m4_digital_prototype_installation_dynamics_claimed", True))
    add("E20_CURRENT_M7_M_CONSUMED", lambda b: set_first_key(b["e20"], "current_M7_unique_dynamics_M_consumed", True))
    add("E20_CURRENT_M7_CLOSURE", lambda b: set_first_key(b["e20"], "current_M7_design_dynamics_closure_claimed", True))
    add("E20_SCENE_A2_TRUE", lambda b: set_first_key(b["e20"], "scene_A2_invoked", True))
    add("E20_CONTACT_WINDOW_TRUE", lambda b: set_first_key(b["e20"], "contact_window_invoked", True))
    add("E20_CONTACT_TRUE", lambda b: set_first_key(b["e20"], "physical_contact_ready", True))
    add("E20_ATTACHED_TRUE", lambda b: set_first_key(b["e20"], "attached_target_propagated", True))
    add("E20_BRANCH_SELECTED", lambda b: set_first_key(b["e20"], "selected_mass_branch", "M3R_B"))
    add("E20_MISSION_TRUE", lambda b: set_first_key(b["e20"], "mission_release_ready", True))
    add("E20_DESIGN_RELEASED", lambda b: set_first_key(b["e20"], "mechanical_design_released", True))
    add("E20_PRODUCTION_TRUE", lambda b: set_first_key(b["e20"], "production_dynamics_ready", True))
    add("E20_HARDWARE_TRUE", lambda b: set_first_key(b["e20"], "hardware_motion_ready", True))
    add("E20_FLIGHT_TRUE", lambda b: set_first_key(b["e20"], "flight_qualification_ready", True))
    add("E20_GATE_PROMOTED", lambda b: b["e20"].__setitem__("gate", "PASS"))
    add("E20_NEXT_TRUE", lambda b: b["e20"].__setitem__("next_stage_authorized", True))
    add("E20_RELEASE_TRUE", lambda b: b["e20"].__setitem__("release_credit", True))
    add("E20_TEST_AUTHORITY", lambda b: b["e20"].__setitem__("testing_pass_grants_authority", True))
    add("E20_VALIDATION_CHECK_LOSS", lambda b: b["e20_validation"].__setitem__("positive_passed", b["e20_validation"]["positive_total"] - 1))
    add("E20_VALIDATION_NEGATIVE_LOSS", lambda b: b["e20_validation"].__setitem__("negative_rejected", b["e20_validation"]["negative_total"] - 1))
    add("E20_VALIDATION_FAIL", lambda b: b["e20_validation"].__setitem__("verdict", "FAIL"))
    add("E20_MANIFEST_GATE", lambda b: b["e20_manifest"].__setitem__("gate", "PASS"))
    add("E20_MANIFEST_NEXT", lambda b: b["e20_manifest"].__setitem__("next_stage_authorized", True))
    add("E20_MANIFEST_RELEASE", lambda b: b["e20_manifest"].__setitem__("release_credit", True))
    add("E15_OVERALL_PROMOTED", lambda b: b["e15"].__setitem__("overall", "PASS"))
    add("E15_CROSS_SOLVER_CLEARED", lambda b: b["e15"]["cross_solver_diagnostic"].__setitem__("all_lt_5pct", True))
    add("E15_FINAL_CANDIDATE_CREATED", lambda b: b["e15"]["final_candidate_cross_solver"].__setitem__("available", True))
    add("E15_FINAL_DIFF_FILLED", lambda b: b["e15"]["final_candidate_cross_solver"].__setitem__("max_relative_difference", 0.01))
    add("SIM11_VERDICT_PROMOTED", lambda b: b["sim11"].__setitem__("verdict", "SIM11_GATES_PASS"))
    add("SIM11_PROVISIONAL_FALSE", lambda b: b["sim11"].__setitem__("PROVISIONAL_PARAMS", False))
    add("V4_NEW_STATE_FALSE", lambda b: b["gate"]["current_release"].__setitem__(NEW_CLOSED_STATE, False))
    add("V4_OLD_FALSE_TRUE", lambda b: b["gate"]["current_release"].__setitem__("physical_contact_ready", True))
    add("V4_OLD_TRUE_FALSE", lambda b: b["gate"]["current_release"].__setitem__("isolated_nonrelease_numeric_diagnostic_execution_closed", False))
    add("V4_EXTRA_STATE", lambda b: b["gate"]["current_release"].__setitem__("mission_ready", True))
    add("TRANSITION_SCHEMA_DRIFT", lambda b: b["gate"]["state_transition"].__setitem__("from_schema", "V2"))
    add("TRANSITION_PRESERVATION_FALSE", lambda b: b["gate"]["state_transition"].__setitem__("existing_current_release_fields_preserved_exactly", False))
    add("TRANSITION_CHANGED_FIELD", lambda b: b["gate"]["state_transition"]["existing_current_release_fields_changed"].append("physical_contact_ready"))
    add("TRANSITION_NEW_FIELD_DRIFT", lambda b: b["gate"]["state_transition"].__setitem__("only_new_closed_state", "other"))
    add("TRANSITION_NEW_VALUE_FALSE", lambda b: b["gate"]["state_transition"].__setitem__("only_new_closed_state_value", False))
    add("TRANSITION_AUTHORITY_TRUE", lambda b: b["gate"]["state_transition"].__setitem__("additional_authority_created", True))
    add("BOUNDARY_MASS_RULE", lambda b: b["gate"]["surrogate_model_boundary"].__setitem__("mass_completion_rule", "AVERAGE"))
    add("BOUNDARY_BUS_SCALE_FALSE", lambda b: b["gate"]["surrogate_model_boundary"].__setitem__("bus_only_mass_and_inertia_scaled", False))
    add("BOUNDARY_ARTIFICIAL_FALSE", lambda b: b["gate"]["surrogate_model_boundary"].__setitem__("mass_completion_is_artificial_scalar_surrogate", False))
    add("BOUNDARY_RELEASED_TRUE", lambda b: b["gate"]["surrogate_model_boundary"].__setitem__("released_system_mass_cg_inertia_authority", True))
    add("BOUNDARY_MOUNT_PROMOTED", lambda b: b["gate"]["surrogate_model_boundary"].__setitem__("mount_frame_model", "B601_ARM_BASE_PHYSICAL"))
    add("BOUNDARY_PHYSICAL_APPLIED", lambda b: b["gate"]["surrogate_model_boundary"].__setitem__("physical_mount_frame_applied", True))
    add("BOUNDARY_TRANSFORM_FILLED", lambda b: b["gate"]["surrogate_model_boundary"].__setitem__("physical_mount_transform", [[1, 0, 0, 0]]))
    add("BOUNDARY_M4_CLAIM", lambda b: b["gate"]["surrogate_model_boundary"].__setitem__("m4_digital_prototype_installation_dynamics_claimed", True))
    add("BOUNDARY_M7_CURRENT_DESIGN_CLAIM", lambda b: b["gate"]["surrogate_model_boundary"].__setitem__("m7_current_design_mass_dynamics_claimed", True))
    add("BOUNDARY_M7_M_CONSUMED", lambda b: b["gate"]["surrogate_model_boundary"].__setitem__("e20_current_M7_unique_dynamics_M_consumed", True))
    add("BOUNDARY_M7_CLOSURE", lambda b: b["gate"]["surrogate_model_boundary"].__setitem__("e20_current_M7_design_dynamics_closure_claimed", True))
    add("BOUNDARY_THRESHOLD_FILLED", lambda b: b["gate"]["surrogate_model_boundary"].__setitem__("acceptance_threshold_authority", 1.0))
    add("BOUNDARY_RELEASE_CREDIT", lambda b: b["gate"]["surrogate_model_boundary"].__setitem__("mechanical_design_release_credit", True))
    add("HOLD_E15_PROMOTED", lambda b: b["gate"]["preserved_holds"].__setitem__("e15_ancf_certification", "PASS"))
    add("HOLD_PANEL_PROVISIONAL_FALSE", lambda b: b["gate"]["preserved_holds"].__setitem__("sim11_panel_and_contact_parameters_provisional", False))
    add("HOLD_FRAME_RECONCILIATION_PROMOTED", lambda b: b["gate"]["preserved_holds"].__setitem__("m7_frame_to_mass_reconciliation", "PASS"))
    for field in (
        "physical_contact_ready",
        "attached_target_recovery_ready",
        "released_combined_mass_properties_ready",
        "cad_generation_authorized",
        "mission_trajectory_release_ready",
        "production_dynamics_ready",
        "hardware_motion_ready",
        "flight_qualification_ready",
    ):
        add(
            f"HOLD_{field.upper()}_TRUE",
            lambda b, name=field: b["gate"]["preserved_holds"].__setitem__(name, True),
        )
    add("BLOCKING_FRONT_PROMOTED", lambda b: b["gate"]["blocking_fronts"][0].__setitem__("state", "PASS"))
    add("CONSISTENCY_STATE_PROMOTED", lambda b: b["gate"]["upstream_consistency_hold"].__setitem__("state", "PASS"))
    add("CONSISTENCY_ODR_TRANSLATION_DRIFT", lambda b: b["gate"]["upstream_consistency_hold"].__setitem__("m7_odr01_dynamics_T_SM_translation_mm", [208.0, 0.0, 0.0]))
    add("CONSISTENCY_ODR_ROTATION_DRIFT", lambda b: b["gate"]["upstream_consistency_hold"].__setitem__("m7_odr01_dynamics_T_SM_rotation", "CLOCK25"))
    add("CONSISTENCY_M_PHYSICAL_TRUE", lambda b: b["gate"]["upstream_consistency_hold"].__setitem__("m_dynamics_physical_entity", True))
    add("CONSISTENCY_CONTEXT_MERGED", lambda b: b["gate"]["upstream_consistency_hold"].__setitem__("contexts_are_separate", False))
    add("CONSISTENCY_RECOMPUTED_TRUE", lambda b: b["gate"]["upstream_consistency_hold"].__setitem__("independent_configuration_recomputation_completed_in_e20", True))
    add("CONSISTENCY_CLOSED_TRUE", lambda b: b["gate"]["upstream_consistency_hold"].__setitem__("reconciliation_closed", True))
    add("CONSISTENCY_M7_UPGRADE_TRUE", lambda b: b["gate"]["upstream_consistency_hold"].__setitem__("m7_current_design_mass_dynamics_upgrade", True))
    add("CONSISTENCY_E21_REMOVED", lambda b: b["gate"]["upstream_consistency_hold"].__setitem__("required_next_evidence", None))
    add("CONSISTENCY_SOURCE_LOSS", lambda b: b["gate"]["upstream_consistency_hold"]["source_binding_names"].pop())
    add("OWNER_STATEMENT_DRIFT", lambda b: b["gate"].__setitem__("required_owner_statement", "APPROVED"))
    add("LC4_VALIDATION_COUNT_DRIFT", lambda b: b["gate"]["facts"][2]["evidence"].__setitem__("checks", "0/0"))
    add("LC4_E15_DIFF_DRIFT", lambda b: b["gate"]["facts"][6]["evidence"].__setitem__("max_relative_difference", 0.01))
    add("LC4_PRIOR_FALSE_LIST_LOSS", lambda b: b["gate"]["facts"][8]["evidence"]["prior_false_fields_preserved"].pop())
    add("LC4_URDF_DRIFT", lambda b: b["gate"]["facts"][9]["evidence"].__setitem__("accepted_urdf_sha256", "0" * 64))
    add("LC4_SOLAR_DRIFT", lambda b: b["gate"]["facts"][9]["evidence"].__setitem__("solar_r2_sha256", "0" * 64))
    add("LC4_GEOMETRY_CREATED", lambda b: b["gate"]["facts"][9]["evidence"].__setitem__("new_geometry_count", 1))

    negatives = []
    for identifier, mutation in mutations:
        candidate = copy.deepcopy(bundle)
        mutation(candidate)
        accepted = gate_safe(candidate)
        negatives.append(
            {
                "id": identifier,
                "pass": not accepted,
                "accepted_after_mutation": accepted,
            }
        )

    checks_passed = sum(item["pass"] for item in checks)
    negatives_passed = sum(item["pass"] for item in negatives)
    passed = (
        checks_passed == len(checks)
        and negatives_passed == len(negatives)
        and len(negatives) >= 80
    )
    return {
        "schema": "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_VALIDATION_V4",
        "generated_local": GENERATED_LOCAL,
        "scope": (
            "independent V3-to-e20-to-V4 hash semantic exact-state-preservation "
            "surrogate-boundary null-HOLD and deep-copy adversarial validation"
        ),
        "checks": checks,
        "checks_passed": checks_passed,
        "checks_total": len(checks),
        "negative_controls": negatives,
        "negative_controls_passed": negatives_passed,
        "negative_controls_total": len(negatives),
        "deepcopy_per_mutation": True,
        "minimum_negative_control_count": 80,
        "check_only_exact_reproduction": True,
        "unified_gate_safe_predicate": True,
        "gate": "HOLD",
        "next_stage_authorized": False,
        "release_credit": False,
        "verdict": (
            "PASS_LOOP_V4_INDEPENDENT_SURROGATE_BRANCH_DIAGNOSTIC_REBIND__"
            "M4_E15_PHYSICAL_CONTACT_ATTACHED_CAD_MISSION_PRODUCTION_AND_"
            "FLIGHT_GATES_HOLD"
            if passed
            else "FAIL_LOOP_V4_VALIDATION"
        ),
    }


def check_validation_file(expected: Mapping[str, Any]) -> tuple[bool, str]:
    if not VALIDATION_PATH.is_file():
        return False, "validation file missing"
    if VALIDATION_PATH.read_bytes() != json_bytes(expected):
        return False, "validation file differs from exact in-memory reproduction"
    return True, "exact"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    result = validate()
    if args.check_only:
        exact, detail = check_validation_file(result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "checks": f"{result['checks_passed']}/{result['checks_total']}",
                    "negative_controls": (
                        f"{result['negative_controls_passed']}/"
                        f"{result['negative_controls_total']}"
                    ),
                    "exact_reproduction": exact,
                    "detail": detail,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0 if result["verdict"].startswith("PASS_") and exact else 1
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    VALIDATION_PATH.write_bytes(json_bytes(result))
    print(
        json.dumps(
            {
                "verdict": result["verdict"],
                "checks": f"{result['checks_passed']}/{result['checks_total']}",
                "negative_controls": (
                    f"{result['negative_controls_passed']}/"
                    f"{result['negative_controls_total']}"
                ),
                "gate": result["gate"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if result["verdict"].startswith("PASS_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
