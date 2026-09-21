"""Independent fail-closed validator for the integrated mechanical-loop gate."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[4]
BASE_REL = (
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "ecr_b601_harness_rated_envelope"
)
OUT_REL = f"{BASE_REL}/10_loop_integration"
GATE_REL = f"{OUT_REL}/MECHANICAL_LOOP_ENGINEERING_STAGE_GATE_V1.json"
MANIFEST_REL = f"{OUT_REL}/MECHANICAL_LOOP_ENGINEERING_OUTPUT_MANIFEST_V1.json"
REPORT_REL = f"{OUT_REL}/MECHANICAL_LOOP_ENGINEERING_VALIDATION_REPORT_V1.json"

EXPECTED_VERDICT = (
    "MECHANICAL_LOOP_ENGINEERING_PRE_CAD_HOLD_WITH_ACTIONABLE_ROUTE_C_"
    "PACKAGE_AND_SIM13_FAIL_CLOSED_SUPERSESSION"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def read_json(relative_path: str) -> dict[str, Any]:
    return json.loads((REPO / relative_path).read_text(encoding="utf-8"))


def write_json(relative_path: str, value: Any) -> None:
    path = REPO / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def add_check(checks: list[dict[str, Any]], check_id: str, passed: bool, evidence: Any) -> None:
    checks.append({"id": check_id, "pass": bool(passed), "evidence": evidence})


def release_is_fail_closed(gate: dict[str, Any]) -> bool:
    release = gate["current_release"]
    prohibited_false = (
        "route_c_parametric_cad_entry_ready",
        "mechanical_design_released",
        "production_dynamics_ready",
        "physical_contact_ready",
        "physics_gated_rl_ready",
        "hardware_motion_ready",
        "flight_qualification_ready",
    )
    return (
        all(release[name] is False for name in prohibited_false)
        and release["diagnostic_kinematic_research_only"] is True
        and release["abort_always_available"] is True
        and gate["next_stage_authorized"] is False
    )


def input_binding_results(gate: dict[str, Any]) -> list[bool]:
    results: list[bool] = []
    for binding in gate.get("input_bindings", []):
        path = REPO / binding["path"]
        actual = sha256_file(path) if path.is_file() else None
        results.append(actual == binding["sha256"])
    return results


def main() -> None:
    gate = read_json(GATE_REL)
    manifest = read_json(MANIFEST_REL)
    checks: list[dict[str, Any]] = []

    add_check(checks, "V01_GATE_SCHEMA", gate.get("schema") == "MECHANICAL_LOOP_ENGINEERING_STAGE_GATE_V1", gate.get("schema"))
    add_check(checks, "V02_INPUT_BINDING_COUNT", len(gate.get("input_bindings", [])) == 9, len(gate.get("input_bindings", [])))

    input_results = input_binding_results(gate)
    add_check(checks, "V03_ALL_INPUT_HASHES_MATCH", all(input_results), {"passed": sum(input_results), "total": len(input_results)})

    facts = gate.get("facts", [])
    add_check(checks, "V04_FACTS_7_OF_7", len(facts) == 7 and all(item.get("observed") is True for item in facts), {"confirmed": sum(item.get("observed") is True for item in facts), "total": len(facts)})
    add_check(checks, "V05_FACT_COUNTS_SELF_CONSISTENT", gate.get("facts_total") == 7 and gate.get("facts_confirmed") == 7, {"total": gate.get("facts_total"), "confirmed": gate.get("facts_confirmed")})
    add_check(checks, "V06_EXPECTED_HOLD_VERDICT", gate.get("verdict") == EXPECTED_VERDICT, gate.get("verdict"))
    add_check(checks, "V07_AUTHORIZATION_FRONT_ONLY", gate.get("authorization_front_package_complete") is True and gate.get("next_stage_authorized") is False, {"package": gate.get("authorization_front_package_complete"), "next": gate.get("next_stage_authorized")})
    add_check(checks, "V08_RELEASE_BITS_FAIL_CLOSED", release_is_fail_closed(gate), gate.get("current_release"))
    add_check(checks, "V09_NONINHERITANCE_COMPLETE", len(gate.get("explicit_noninheritance", [])) == 5, gate.get("explicit_noninheritance"))
    add_check(checks, "V10_ONE_PASS_SEQUENCE_PRESENT", len(gate.get("one_pass_sequence_after_required_authority_and_inputs", [])) == 7, gate.get("one_pass_sequence_after_required_authority_and_inputs"))
    add_check(checks, "V11_OWNER_ACTION_EXPLICIT", "ODR-42" in gate.get("required_owner_action", "") and "APPROVE_BOUNDED_DETAILED_DESIGN" in gate.get("required_owner_action", ""), gate.get("required_owner_action"))
    add_check(checks, "V12_PROHIBITION_EXPLICIT", all(term in gate.get("prohibition", "") for term in ("CAD/STEP", "production dynamics", "physical-contact RL", "hardware motion")), gate.get("prohibition"))

    outputs = manifest.get("outputs", [])
    sources = manifest.get("sources", [])
    output_matches = [sha256_file(REPO / item["path"]) == item["sha256"] for item in outputs]
    source_matches = [sha256_file(REPO / item["path"]) == item["sha256"] for item in sources]
    add_check(checks, "V13_MANIFEST_COUNTS", manifest.get("output_count") == 1 and manifest.get("source_count") == 2 and len(outputs) == 1 and len(sources) == 2, {"outputs": len(outputs), "sources": len(sources)})
    add_check(checks, "V14_OUTPUT_HASHES_MATCH", all(output_matches), {"passed": sum(output_matches), "total": len(output_matches)})
    add_check(checks, "V15_SOURCE_HASHES_MATCH", all(source_matches), {"passed": sum(source_matches), "total": len(source_matches)})

    negative_controls: list[dict[str, Any]] = []
    mutated = copy.deepcopy(gate)
    mutated["current_release"]["production_dynamics_ready"] = True
    negative_controls.append({"id": "NC01_PRODUCTION_TRUE_TRIPS", "pass": release_is_fail_closed(mutated) is False})
    mutated = copy.deepcopy(gate)
    mutated["current_release"]["route_c_parametric_cad_entry_ready"] = True
    negative_controls.append({"id": "NC02_CAD_TRUE_TRIPS", "pass": release_is_fail_closed(mutated) is False})
    mutated = copy.deepcopy(gate)
    mutated["current_release"]["diagnostic_kinematic_research_only"] = False
    negative_controls.append({"id": "NC03_DIAGNOSTIC_SCOPE_LOSS_TRIPS", "pass": release_is_fail_closed(mutated) is False})
    mutated = copy.deepcopy(gate)
    mutated["next_stage_authorized"] = True
    negative_controls.append({"id": "NC04_SILENT_AUTHORIZATION_TRIPS", "pass": release_is_fail_closed(mutated) is False})
    mutated = copy.deepcopy(gate)
    mutated["input_bindings"][0]["sha256"] = "0" * 64
    negative_controls.append(
        {
            "id": "NC05_INPUT_HASH_TAMPER_TRIPS",
            "pass": not all(input_binding_results(mutated)),
        }
    )
    add_check(checks, "V16_ALL_NEGATIVE_CONTROLS_PASS", all(item["pass"] for item in negative_controls), {"passed": sum(item["pass"] for item in negative_controls), "total": len(negative_controls)})

    failed = [item["id"] for item in checks if not item["pass"]]
    report = {
        "schema": "MECHANICAL_LOOP_ENGINEERING_VALIDATION_REPORT_V1",
        "generated_from_gate_timestamp": gate["generated_local"],
        "verdict": "PASS" if not failed else "FAIL",
        "scope": "package and authority-chain integrity; not a physical release",
        "checks": checks,
        "checks_total": len(checks),
        "checks_passed": len(checks) - len(failed),
        "checks_failed": len(failed),
        "failed_checks": failed,
        "negative_controls": negative_controls,
        "negative_controls_total": len(negative_controls),
        "negative_controls_passed": sum(item["pass"] for item in negative_controls),
        "next_stage_authorized": False,
    }
    write_json(REPORT_REL, report)
    print(
        json.dumps(
            {
                "verdict": report["verdict"],
                "checks": f'{report["checks_passed"]}/{report["checks_total"]}',
                "negative_controls": (
                    f'{report["negative_controls_passed"]}/'
                    f'{report["negative_controls_total"]}'
                ),
                "report_sha256": sha256_file(REPO / REPORT_REL),
            },
            ensure_ascii=False,
        )
    )
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
