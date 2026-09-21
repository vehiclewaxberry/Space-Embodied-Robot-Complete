"""Independent fail-closed validation for Mechanical Loop Continuation V3."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[4]
ECR_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ECR_ROOT / "13_loop_continuation_v3"
GATE_PATH = OUTPUT_ROOT / "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V3.json"
MANIFEST_PATH = (
    OUTPUT_ROOT / "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_OUTPUT_MANIFEST_V3.json"
)
VALIDATION_PATH = (
    OUTPUT_ROOT / "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_VALIDATION_V3.json"
)
EXPECTED_VERDICT = "MECHANICAL_LOOP_ENGINEERING_CONTINUES_WITH_HASH_BOUND_ISOLATED_NONRELEASE_NUMERIC_DIAGNOSTIC_EXECUTION_CLOSED__PRE_CAD_PHYSICAL_CONTACT_ATTACHED_RECOVERY_MISSION_PRODUCTION_AND_FLIGHT_RELEASE_HOLD"
URDF_SHA = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
SOLAR_SHA = "21FF77B882DBFAB87B3E77DD56817EFC7F321C68E30AFEDCDDBB4D79B9915795"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def all_false(mapping: Mapping[str, Any], names: list[str]) -> bool:
    return all(mapping.get(name) is False for name in names)


def gate_safe(bundle: Mapping[str, Any]) -> bool:
    try:
        gate = bundle["gate"]
        manifest = bundle["manifest"]
        if gate["schema"] != "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V3":
            return False
        if gate["verdict"] != EXPECTED_VERDICT or gate["gate"] != "HOLD":
            return False
        if gate["next_stage_authorized"] or gate["release_credit"]:
            return False
        if gate["testing_pass_grants_authority"]:
            return False
        if gate["facts_total"] != 10 or gate["facts_confirmed"] != 10:
            return False
        if len(gate["facts"]) != 10 or not all(
            fact["observed"] is True for fact in gate["facts"]
        ):
            return False
        if len(gate["input_bindings"]) != 15:
            return False
        if any(
            not binding.get("sha256") or binding.get("bytes", 0) <= 0
            for binding in gate["input_bindings"]
        ):
            return False
        by_name = {item["name"]: item for item in gate["input_bindings"]}
        manifest_sources = {item["name"]: item for item in manifest["sources"]}
        if any(
            name not in manifest_sources
            or manifest_sources[name]["path"] != binding["path"]
            or manifest_sources[name]["sha256"] != binding["sha256"]
            or manifest_sources[name]["bytes"] != binding["bytes"]
            for name, binding in by_name.items()
        ):
            return False
        if by_name["accepted_urdf"]["sha256"] != URDF_SHA:
            return False
        if by_name["solar_r2"]["sha256"] != SOLAR_SHA:
            return False
        facts = {fact["id"]: fact for fact in gate["facts"]}
        if facts["LC3-01"]["evidence"]["gate"] != "HOLD":
            return False
        if facts["LC3-02"]["evidence"]["criteria"] != "17/17":
            return False
        if facts["LC3-02"]["evidence"]["diagnostic_execution_verdict"] != "PASS":
            return False
        if facts["LC3-02"]["evidence"]["gate"] != "HOLD":
            return False
        if facts["LC3-02"]["evidence"]["released_segments"] != 0:
            return False
        if facts["LC3-03"]["evidence"]["checks"] != "31/31":
            return False
        if facts["LC3-03"]["evidence"]["negative_controls"] != "85/85":
            return False
        m01 = facts["LC3-04"]["evidence"]
        if abs(m01["peak_base_attitude_deviation_deg"] - 122.54308036902498) > 1e-12:
            return False
        if m01["max_momentum_residual_norm_S"] > 1e-12:
            return False
        if m01["acceptance_threshold_authority"] is not None or m01["engineering_prediction"]:
            return False
        m05 = facts["LC3-05"]["evidence"]
        if abs(m05["sim13_final_phase_deg"] - 25.0) > 1e-10:
            return False
        if m05["branch_merge_performed"] or m05["physical_target_state_released"]:
            return False
        m06 = facts["LC3-06"]["evidence"]
        if m06["case_count"] != 20 or m06["max_relative_impulse_error"] >= 1e-8:
            return False
        if m06["physical_contact_fields"] is not None or m06["hardware_force_credit"]:
            return False
        m07_arm = facts["LC3-07"]["evidence"]
        if abs(m07_arm["peak_base_attitude_deviation_deg"] - 37.200770990128426) > 1e-12:
            return False
        if m07_arm["attached_target_propagated"]:
            return False
        if m07_arm["acceptance_threshold_authority"] is not None:
            return False
        m07_sim15 = facts["LC3-08"]["evidence"]
        if m07_sim15["case_count"] != 4 or not m07_sim15["baseline_exact"]:
            return False
        if m07_sim15["C08_branch_selection_performed"]:
            return False
        if m07_sim15["locked_transform_gripper_to_target"] is not None:
            return False
        if m07_sim15["physical_contact_authority"]:
            return False
        isolation = facts["LC3-09"]["evidence"]
        if isolation["lane_execution_count"] != 6:
            return False
        if any(
            isolation[name]
            for name in (
                "cross_lane_chaining_performed",
                "branch_merging_performed",
                "mission_timeline_created",
            )
        ):
            return False
        if isolation["released_segments"] != 0:
            return False
        immutable = facts["LC3-10"]["evidence"]
        if immutable["accepted_urdf_sha256"] != URDF_SHA:
            return False
        if immutable["solar_r2_sha256"] != SOLAR_SHA:
            return False
        if immutable["new_geometry_count"] != 0:
            return False
        current = gate["current_release"]
        if current["isolated_nonrelease_numeric_diagnostic_execution_ready"] is not True:
            return False
        if current["isolated_nonrelease_numeric_diagnostic_execution_closed"] is not True:
            return False
        if not all(
            current[name] is True
            for name in (
                "m01_rigid_base_reaction_diagnostic_executed",
                "m05_two_branch_diagnostics_executed_separately",
                "m06_twenty_scalar_stimulus_cases_executed",
                "m07_arm_only_and_sim15_diagnostics_executed_separately",
            )
        ):
            return False
        if not all_false(
            current,
            [
                "end_to_end_diagnostic_dynamics_ready",
                "mission_sequence_executable",
                "mission_trajectory_release_ready",
                "cad_generation_authorized",
                "physical_contact_ready",
                "attached_target_recovery_ready",
                "production_dynamics_ready",
                "sim13_current_production_binding_valid",
                "hardware_motion_ready",
                "flight_qualification_ready",
            ],
        ):
            return False
        lane = gate["bounded_diagnostic_lane"]
        if lane["state"] != "HASH_BOUND_ISOLATED_NON_RELEASE_NUMERIC_DIAGNOSTIC_EXECUTION_AND_REPRODUCIBILITY_CLOSED":
            return False
        observations = gate["diagnostic_design_observations"]
        if observations["acceptance_threshold_authority"] is not None:
            return False
        if observations["model_scope"] != "ISOLATED_DIAGNOSTIC_ONLY":
            return False
        if observations["mechanical_design_release_credit"]:
            return False
        if manifest["schema"] != "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_OUTPUT_MANIFEST_V3":
            return False
        if manifest["output_count"] != 2 or manifest["source_count"] != 17:
            return False
        if not manifest["validation_report_excluded_to_avoid_self_hash"]:
            return False
        if manifest["gate"] != "HOLD" or manifest["next_stage_authorized"] or manifest["release_credit"]:
            return False
        return True
    except (KeyError, TypeError, ValueError, IndexError):
        return False


def validate() -> dict[str, Any]:
    gate = load(GATE_PATH)
    manifest = load(MANIFEST_PATH)
    bundle = {"gate": gate, "manifest": manifest}
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
    check("NO_VALIDATION_SELF_HASH", all("VALIDATION_V3" not in item["path"] for item in manifest["outputs"] + manifest["sources"]), True)
    check("NO_RELEASE_CREDIT", not gate["release_credit"] and not gate["next_stage_authorized"], False)

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
    add("INPUT_HASH_DRIFT", lambda b: b["gate"]["input_bindings"][0].__setitem__("sha256", "0" * 64))
    add("URDF_HASH_DRIFT", lambda b: b["gate"]["input_bindings"][-2].__setitem__("sha256", "0" * 64))
    add("SOLAR_HASH_DRIFT", lambda b: b["gate"]["input_bindings"][-1].__setitem__("sha256", "0" * 64))
    add("E19_CRITERIA_DRIFT", lambda b: b["gate"]["facts"][1]["evidence"].__setitem__("criteria", "16/17"))
    add("E19_GATE_PROMOTED", lambda b: b["gate"]["facts"][1]["evidence"].__setitem__("gate", "PASS"))
    add("E19_RELEASED_SEGMENT", lambda b: b["gate"]["facts"][1]["evidence"].__setitem__("released_segments", 1))
    add("VALIDATION_CHECK_LOSS", lambda b: b["gate"]["facts"][2]["evidence"].__setitem__("checks", "30/31"))
    add("VALIDATION_NEGATIVE_LOSS", lambda b: b["gate"]["facts"][2]["evidence"].__setitem__("negative_controls", "84/85"))
    add("M01_RESULT_DRIFT", lambda b: b["gate"]["facts"][3]["evidence"].__setitem__("peak_base_attitude_deviation_deg", 0.0))
    add("M01_THRESHOLD_FABRICATED", lambda b: b["gate"]["facts"][3]["evidence"].__setitem__("acceptance_threshold_authority", 5.0))
    add("M01_ENGINEERING_PREDICTION", lambda b: b["gate"]["facts"][3]["evidence"].__setitem__("engineering_prediction", True))
    add("M05_PHASE_UNIT_ERROR", lambda b: b["gate"]["facts"][4]["evidence"].__setitem__("sim13_final_phase_deg", 0.436332))
    add("M05_BRANCH_MERGED", lambda b: b["gate"]["facts"][4]["evidence"].__setitem__("branch_merge_performed", True))
    add("M05_STATE_RELEASED", lambda b: b["gate"]["facts"][4]["evidence"].__setitem__("physical_target_state_released", True))
    add("M06_CASE_LOSS", lambda b: b["gate"]["facts"][5]["evidence"].__setitem__("case_count", 19))
    add("M06_CONTACT_FORCE_FILLED", lambda b: b["gate"]["facts"][5]["evidence"].__setitem__("physical_contact_fields", 0.0))
    add("M06_HARDWARE_FORCE_CREDIT", lambda b: b["gate"]["facts"][5]["evidence"].__setitem__("hardware_force_credit", True))
    add("M07_ARM_RESULT_DRIFT", lambda b: b["gate"]["facts"][6]["evidence"].__setitem__("peak_base_attitude_deviation_deg", 0.0))
    add("M07_TARGET_ATTACHED", lambda b: b["gate"]["facts"][6]["evidence"].__setitem__("attached_target_propagated", True))
    add("M07_THRESHOLD_FABRICATED", lambda b: b["gate"]["facts"][6]["evidence"].__setitem__("acceptance_threshold_authority", 1.0))
    add("SIM15_CASE_LOSS", lambda b: b["gate"]["facts"][7]["evidence"].__setitem__("case_count", 3))
    add("SIM15_BASELINE_NOT_EXACT", lambda b: b["gate"]["facts"][7]["evidence"].__setitem__("baseline_exact", False))
    add("C08_BRANCH_SELECTED", lambda b: b["gate"]["facts"][7]["evidence"].__setitem__("C08_branch_selection_performed", True))
    add("LOCKED_TRANSFORM_FILLED", lambda b: b["gate"]["facts"][7]["evidence"].__setitem__("locked_transform_gripper_to_target", [[1, 0, 0, 0]]))
    add("PHYSICAL_CONTACT_AUTHORITY", lambda b: b["gate"]["facts"][7]["evidence"].__setitem__("physical_contact_authority", True))
    add("CROSS_LANE_CHAIN", lambda b: b["gate"]["facts"][8]["evidence"].__setitem__("cross_lane_chaining_performed", True))
    add("BRANCH_MERGE", lambda b: b["gate"]["facts"][8]["evidence"].__setitem__("branch_merging_performed", True))
    add("MISSION_TIMELINE", lambda b: b["gate"]["facts"][8]["evidence"].__setitem__("mission_timeline_created", True))
    add("GEOMETRY_CREATED", lambda b: b["gate"]["facts"][9]["evidence"].__setitem__("new_geometry_count", 1))
    add("ISOLATED_EXECUTION_FALSE", lambda b: b["gate"]["current_release"].__setitem__("isolated_nonrelease_numeric_diagnostic_execution_ready", False))
    add("ISOLATED_CLOSURE_FALSE", lambda b: b["gate"]["current_release"].__setitem__("isolated_nonrelease_numeric_diagnostic_execution_closed", False))
    add("END_TO_END_TRUE", lambda b: b["gate"]["current_release"].__setitem__("end_to_end_diagnostic_dynamics_ready", True))
    add("MISSION_EXECUTABLE_TRUE", lambda b: b["gate"]["current_release"].__setitem__("mission_sequence_executable", True))
    add("CAD_AUTHORIZED_TRUE", lambda b: b["gate"]["current_release"].__setitem__("cad_generation_authorized", True))
    add("PHYSICAL_CONTACT_TRUE", lambda b: b["gate"]["current_release"].__setitem__("physical_contact_ready", True))
    add("ATTACHED_RECOVERY_TRUE", lambda b: b["gate"]["current_release"].__setitem__("attached_target_recovery_ready", True))
    add("PRODUCTION_TRUE", lambda b: b["gate"]["current_release"].__setitem__("production_dynamics_ready", True))
    add("SIM13_PRODUCTION_TRUE", lambda b: b["gate"]["current_release"].__setitem__("sim13_current_production_binding_valid", True))
    add("HARDWARE_TRUE", lambda b: b["gate"]["current_release"].__setitem__("hardware_motion_ready", True))
    add("FLIGHT_TRUE", lambda b: b["gate"]["current_release"].__setitem__("flight_qualification_ready", True))
    add("LANE_STATE_PROMOTED", lambda b: b["gate"]["bounded_diagnostic_lane"].__setitem__("state", "MISSION_READY"))
    add("OBS_THRESHOLD_FILLED", lambda b: b["gate"]["diagnostic_design_observations"].__setitem__("acceptance_threshold_authority", 5.0))
    add("OBS_RELEASE_CREDIT", lambda b: b["gate"]["diagnostic_design_observations"].__setitem__("mechanical_design_release_credit", True))
    add("MANIFEST_GATE_PROMOTED", lambda b: b["manifest"].__setitem__("gate", "PASS"))
    add("MANIFEST_NEXT_TRUE", lambda b: b["manifest"].__setitem__("next_stage_authorized", True))
    add("MANIFEST_RELEASE_TRUE", lambda b: b["manifest"].__setitem__("release_credit", True))
    add("MANIFEST_OUTPUT_LOSS", lambda b: b["manifest"].__setitem__("output_count", 1))
    add("MANIFEST_SOURCE_LOSS", lambda b: b["manifest"].__setitem__("source_count", 16))

    negatives = []
    for identifier, mutation in mutations:
        candidate = copy.deepcopy(bundle)
        mutation(candidate)
        negatives.append(
            {
                "id": identifier,
                "pass": not gate_safe(candidate),
                "accepted_after_mutation": gate_safe(candidate),
            }
        )
    checks_passed = sum(item["pass"] for item in checks)
    negatives_passed = sum(item["pass"] for item in negatives)
    passed = (
        checks_passed == len(checks)
        and negatives_passed == len(negatives)
        and len(negatives) >= 40
    )
    return {
        "schema": "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_VALIDATION_V3",
        "generated_local": "2026-08-23T21:20:00+08:00",
        "scope": "independent V2-to-e19-to-V3 hash semantic isolation null-HOLD and adversarial validation",
        "checks": checks,
        "checks_passed": checks_passed,
        "checks_total": len(checks),
        "negative_controls": negatives,
        "negative_controls_passed": negatives_passed,
        "negative_controls_total": len(negatives),
        "unified_gate_safe_predicate": True,
        "gate": "HOLD",
        "next_stage_authorized": False,
        "release_credit": False,
        "verdict": (
            "PASS_LOOP_V3_ISOLATED_DIAGNOSTIC_REBIND__ALL_PHYSICAL_MISSION_CAD_PRODUCTION_AND_RELEASE_GATES_HOLD"
            if passed
            else "FAIL_LOOP_V3_VALIDATION"
        ),
    }


if __name__ == "__main__":
    result = validate()
    VALIDATION_PATH.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "verdict": result["verdict"],
                "checks": f"{result['checks_passed']}/{result['checks_total']}",
                "negative_controls": f"{result['negative_controls_passed']}/{result['negative_controls_total']}",
                "gate": result["gate"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    raise SystemExit(0 if result["verdict"].startswith("PASS_") else 1)
