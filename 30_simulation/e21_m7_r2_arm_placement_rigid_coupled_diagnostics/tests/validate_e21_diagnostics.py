"""Independent semantic validator and manifest builder for e21."""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable

import yaml

sys.dont_write_bytecode = True


MODULE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = MODULE_ROOT.parents[1]
RESULTS_ROOT = MODULE_ROOT / "results"
PREFIX = "30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics"
GENERATED_LOCAL = "2026-08-23T15:00:00+08:00"
VERDICT = (
    "E21_M7_R2_MIXED_ARM_PLACEMENT_DETECTED__CURRENT_R2_RIGID_WING_"
    "FREE_FLOATING_ARM_ONLY_TWO_PLACEMENT_SENSITIVITY_AND_FIXED_BASE_ROM_"
    "REPRODUCTION_CLOSED__SINGLE_PLACEMENT_R2_FULL_FLEX_COUPLING_E15_"
    "HARNESS_CONTACT_MISSION_PRODUCTION_AND_FLIGHT_HOLD"
)

STATIC_ARTIFACTS = (
    f"{PREFIX}/README.md",
    f"{PREFIX}/00_authority/E21_AUTHORITY_CONTRACT_V1.yaml",
    f"{PREFIX}/config/E21_CURRENT_R2_RIGID_DIAGNOSTIC_CAMPAIGN_V1.yaml",
    f"{PREFIX}/docs/preregistration.md",
    f"{PREFIX}/docs/method_and_limitations.md",
    f"{PREFIX}/src/build_e21_diagnostics.py",
    f"{PREFIX}/tests/validate_e21_diagnostics.py",
)

CORE_RESULTS = (
    "E21_INPUT_MANIFEST_V1.json",
    "E21_NINE_CONFIGURATION_ARM_PLACEMENT_AUDIT_V1.json",
    "E21_M07_TRAJECTORY_RECONSTRUCTION_CHECK_V1.json",
    "E21_C07_R2_DEPLOYED_LOCKED_FIXED_RESIDUAL_V1.json",
    "E21_ODR01_DYNAMICS_T_SM__M07_ARM_ONLY_RADAU_SUMMARY_V1.json",
    "E21_ODR01_DYNAMICS_T_SM__M07_ARM_ONLY_RADAU_HISTORY_V1.csv",
    "E21_WP11_PHYSICAL_GEOMETRY_CONTEXT__M07_ARM_ONLY_RADAU_SUMMARY_V1.json",
    "E21_WP11_PHYSICAL_GEOMETRY_CONTEXT__M07_ARM_ONLY_RADAU_HISTORY_V1.csv",
    "E21_TWO_PLACEMENT_RIGID_DYNAMICS_SENSITIVITY_V1.json",
    "E21_FIXED_BASE_R2_ROM_REPRODUCTION_AND_MASS_CONFLICT_V1.json",
    "E21_DIAGNOSTIC_GATE_V1.json",
)


def project_path(relative: str) -> Path:
    return PROJECT_ROOT / Path(relative)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def load_json(name: str) -> Any:
    return json.loads((RESULTS_ROOT / name).read_text(encoding="utf-8"))


def record(relative: str, data: bytes | None = None) -> dict[str, Any]:
    blob = project_path(relative).read_bytes() if data is None else data
    return {"path": relative.replace("\\", "/"), "sha256": sha256_bytes(blob), "bytes": len(blob)}


def semantic_detectors(campaign: dict[str, Any]) -> dict[str, Callable[[dict[str, Any]], bool]]:
    limits = campaign["thresholds"]
    return {
        "source_hashes": lambda ctx: bool(ctx["input"]["all_exact_hash_match"] and all(x["exact_hash_match"] for x in ctx["input"]["records"])),
        "placement_nonselection": lambda ctx: bool(
            ctx["audit"]["mixed_placement_context_detected"]
            and not ctx["audit"]["branch_selected"]
            and not ctx["audit"]["branches_averaged"]
            and not ctx["audit"]["branch_delta_is_uncertainty"]
            and not ctx["audit"]["ODR01_invalidated"]
        ),
        "odr_initial_closure": lambda ctx: bool(
            ctx["odr"]["initial_mass_properties_vs_V3_R2_C07"]["mass_error_kg"] <= limits["odr01_c07_mass_closure_kg"]
            and ctx["odr"]["initial_mass_properties_vs_V3_R2_C07"]["cg_error_norm_m"] <= limits["odr01_c07_cg_closure_m"]
            and ctx["odr"]["initial_mass_properties_vs_V3_R2_C07"]["inertia_max_abs_error_kg_m2"] <= limits["odr01_c07_inertia_closure_kg_m2"]
        ),
        "lane_scope": lambda ctx: all(
            not row["model_scope"]["target_attached"]
            and not row["model_scope"]["contact"]
            and not row["model_scope"]["collision"]
            and not row["model_scope"]["full_R2_flexible_coupling"]
            and not row["model_scope"]["legacy_r1_panel_inputs_consumed"]
            for row in (ctx["odr"], ctx["physical"])
        ),
        "lane_numerics": lambda ctx: all(
            max(row["metrics"]["momentum_max_norm_dP"], row["metrics"]["momentum_max_norm_dL"]) <= limits["momentum_norm"]
            and row["metrics"]["energy_audit_relative"] <= limits["energy_audit_relative"]
            and row["metrics"]["quaternion_norm_max_error_after_normalization"] <= limits["quaternion_norm_error"]
            and row["metrics"]["mass_matrix_min_eigenvalue"] > limits["mass_matrix_min_eigenvalue"]
            for row in (ctx["odr"], ctx["physical"])
        ),
        "rom_conflict_nonpropagation": lambda ctx: bool(
            not ctx["rom"]["nonselecting_conflict_diagnostic"]["selected"]
            and not ctx["rom"]["nonselecting_conflict_diagnostic"]["propagated_to_free_floating_dynamics"]
            and ctx["rom"]["damping_matrix"] is None
            and ctx["rom"]["participation_factors"] is None
            and ctx["rom"]["forced_response"] is None
        ),
        "holds": lambda ctx: bool(
            ctx["gate"]["overall"] == "HOLD"
            and ctx["gate"]["mandatory_holds"]["r2_full_flexible_coupling"] == "NOT_EVALUATED"
            and ctx["gate"]["mandatory_holds"]["e15_ancf_certification"] == "REPEAT_ANCF_CERTIFICATION"
            and ctx["gate"]["mandatory_holds"]["r2_harness_R2_HRN_04"] == "FAIL_REDESIGN_REQUIRED"
            and ctx["gate"]["mandatory_holds"]["owner_review"] == "PENDING_OWNER_REVIEW"
            and ctx["gate"]["mandatory_holds"]["production"] == "HOLD"
            and ctx["gate"]["mandatory_holds"]["flight"] == "HOLD"
        ),
        "authority": lambda ctx: bool(
            ctx["gate"]["review_status"] == "PENDING_OWNER_REVIEW"
            and not ctx["gate"]["next_stage_authorized"]
            and not ctx["gate"]["release_credit"]
            and not ctx["gate"]["test_pass_grants_authority"]
        ),
    }


def negative_controls(context: dict[str, Any], detectors: dict[str, Callable[[dict[str, Any]], bool]]) -> list[dict[str, Any]]:
    controls: list[tuple[str, str, Callable[[dict[str, Any]], None]]] = []

    def add(identifier: str, detector: str, mutation: Callable[[dict[str, Any]], None]) -> None:
        controls.append((identifier, detector, mutation))

    add("NC01_SOURCE_HASH_FALSE", "source_hashes", lambda ctx: ctx["input"].__setitem__("all_exact_hash_match", False))
    add("NC02_SELECT_PLACEMENT", "placement_nonselection", lambda ctx: ctx["audit"].__setitem__("branch_selected", True))
    add("NC03_BREAK_ODR_CLOSURE", "odr_initial_closure", lambda ctx: ctx["odr"]["initial_mass_properties_vs_V3_R2_C07"].__setitem__("mass_error_kg", 1.0))
    add("NC04_ATTACH_TARGET", "lane_scope", lambda ctx: ctx["physical"]["model_scope"].__setitem__("target_attached", True))
    add("NC05_BREAK_MOMENTUM", "lane_numerics", lambda ctx: ctx["odr"]["metrics"].__setitem__("momentum_max_norm_dL", 1.0))
    add("NC06_PROPAGATE_ROM_CONFLICT", "rom_conflict_nonpropagation", lambda ctx: ctx["rom"]["nonselecting_conflict_diagnostic"].__setitem__("propagated_to_free_floating_dynamics", True))
    add("NC07_CLEAR_E15", "holds", lambda ctx: ctx["gate"]["mandatory_holds"].__setitem__("e15_ancf_certification", "PASS"))
    add("NC08_AUTHORIZE_NEXT_STAGE", "authority", lambda ctx: ctx["gate"].__setitem__("next_stage_authorized", True))

    rows = []
    for identifier, detector_name, mutation in controls:
        candidate = copy.deepcopy(context)
        baseline_detected = detectors[detector_name](candidate)
        mutation(candidate)
        mutation_detected = not detectors[detector_name](candidate)
        rows.append({
            "id": identifier, "deep_copy_used": True, "detector": detector_name,
            "baseline_passed": bool(baseline_detected),
            "mutation_detected": bool(mutation_detected),
            "status": "PASS" if baseline_detected and mutation_detected else "FAIL",
        })
    return rows


def validate_history(name: str, expected_lane: str) -> dict[str, Any]:
    rows = list(csv.DictReader((RESULTS_ROOT / name).read_text(encoding="utf-8").splitlines()))
    indices = [int(row["sample_index"]) for row in rows]
    times = [float(row["t_s"]) for row in rows]
    first_state = [float(rows[0][key]) for key in ("base_x_m", "base_y_m", "base_z_m", "quat_w", "quat_x", "quat_y", "quat_z", "joint_work_J")]
    return {
        "file": name, "row_count": len(rows),
        "lane_id_exact": all(row["lane_id"] == expected_lane for row in rows),
        "indices_exact": indices == list(range(451)),
        "time_start_s": times[0], "time_end_s": times[-1],
        "time_monotonic": all(b > a for a, b in zip(times, times[1:])),
        "zero_independent_initial_state": first_state == [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0],
    }


def build_validation() -> tuple[dict[str, Any], bytes, dict[str, Any], bytes]:
    campaign = yaml.safe_load(project_path(f"{PREFIX}/config/E21_CURRENT_R2_RIGID_DIAGNOSTIC_CAMPAIGN_V1.yaml").read_text(encoding="utf-8"))
    context = {
        "input": load_json("E21_INPUT_MANIFEST_V1.json"),
        "audit": load_json("E21_NINE_CONFIGURATION_ARM_PLACEMENT_AUDIT_V1.json"),
        "trajectory": load_json("E21_M07_TRAJECTORY_RECONSTRUCTION_CHECK_V1.json"),
        "residual": load_json("E21_C07_R2_DEPLOYED_LOCKED_FIXED_RESIDUAL_V1.json"),
        "odr": load_json("E21_ODR01_DYNAMICS_T_SM__M07_ARM_ONLY_RADAU_SUMMARY_V1.json"),
        "physical": load_json("E21_WP11_PHYSICAL_GEOMETRY_CONTEXT__M07_ARM_ONLY_RADAU_SUMMARY_V1.json"),
        "cross": load_json("E21_TWO_PLACEMENT_RIGID_DYNAMICS_SENSITIVITY_V1.json"),
        "rom": load_json("E21_FIXED_BASE_R2_ROM_REPRODUCTION_AND_MASS_CONFLICT_V1.json"),
        "gate": load_json("E21_DIAGNOSTIC_GATE_V1.json"),
    }
    detectors = semantic_detectors(campaign)
    negative = negative_controls(context, detectors)
    history = [
        validate_history("E21_ODR01_DYNAMICS_T_SM__M07_ARM_ONLY_RADAU_HISTORY_V1.csv", "ODR01_DYNAMICS_T_SM"),
        validate_history("E21_WP11_PHYSICAL_GEOMETRY_CONTEXT__M07_ARM_ONLY_RADAU_HISTORY_V1.csv", "WP11_PHYSICAL_GEOMETRY_CONTEXT"),
    ]
    classifications = {
        ledger["ledger"]: [row["context_match_classification"] for row in ledger["rows"]]
        for ledger in context["audit"]["ledgers"]
    }
    expected_pattern = ["WP11_PHYSICAL_GEOMETRY_CONTEXT"]*6 + ["ODR01_DYNAMICS_T_SM"]*3
    source_hashes_independent = all(
        sha256_bytes(project_path(row["path"]).read_bytes()) == row["sha256"] == row["expected_sha256"]
        for row in context["input"]["records"]
    )
    core_hashes = [record(f"{PREFIX}/results/{name}") for name in CORE_RESULTS]
    checks = [
        ("V01", "all declared source hashes independently recheck", source_hashes_independent),
        ("V02", "input manifest has required runtime exclusions", not context["input"]["runtime_boundary"]["legacy_r1_panel_card_read"] and not context["input"]["runtime_boundary"]["legacy_r1_ffr_constructed"] and not context["input"]["runtime_boundary"]["scene_A2_read"] and not context["input"]["runtime_boundary"]["target_attached"]),
        ("V03", "gate verdict exact", context["gate"]["verdict"] == VERDICT),
        ("V04", "gate has 23 of 23 diagnostic subcriteria", context["gate"]["criterion_counts"] == {"total": 23, "pass": 23, "fail": 0} and context["gate"]["diagnostic_subcriteria_all_pass"]),
        ("V05", "gate remains HOLD", context["gate"]["overall"] == "HOLD"),
        ("V06", "no next-stage or release authority", not context["gate"]["next_stage_authorized"] and not context["gate"]["release_credit"] and not context["gate"]["test_pass_grants_authority"]),
        ("V07", "two ledgers and 36 placement evaluations", context["audit"]["ledger_count"] == 2 and context["audit"]["configuration_count_per_ledger"] == 9 and context["audit"]["placement_evaluation_count"] == 36),
        ("V08", "V2 placement classification pattern exact", classifications["V2"] == expected_pattern),
        ("V09", "V3_R2 placement classification pattern exact", classifications["V3_R2"] == expected_pattern),
        ("V10", "mixed placement is nonselecting", detectors["placement_nonselection"](context)),
        ("V11", "no configuration declared wrong", not context["audit"]["any_configuration_declared_wrong"]),
        ("V12", "V2 arm rows carried verbatim to V3_R2", context["audit"]["all_arm_rows_carried_verbatim"]),
        ("V13", "all M07 rows reproduce", context["trajectory"]["row_count"] == 451 and context["trajectory"]["all_numeric_rows_reproduced"]),
        ("V14", "M07 remains non-release and no target metadata consumed", context["trajectory"]["all_rows_non_release"] and not context["trajectory"]["target_metadata_consumed"]),
        ("V15", "fixed residual mass positive", context["residual"]["fixed_residual"]["mass_kg"] > 0.0),
        ("V16", "fixed residual inertia SPD", context["residual"]["fixed_residual"]["inertia_min_eigenvalue_kg_m2"] > 0.0),
        ("V17", "residual reclosure is machine precision", context["residual"]["reclosure"]["mass_error_kg"] <= 1.0e-12 and context["residual"]["reclosure"]["cg_error_norm_m"] <= 1.0e-12 and context["residual"]["reclosure"]["inertia_max_abs_error_kg_m2"] <= 1.0e-12),
        ("V18", "current R2 deployed locked wing mass closes", context["residual"]["r2_wing_check"]["ledger_solar_component_mass_kg"] == context["residual"]["r2_wing_check"]["solar_r2_mass_package_C07_both_wings_kg"] == 1.56),
        ("V19", "no legacy panel in residual", not context["residual"]["r2_wing_check"]["legacy_r1_panel_card_or_mass_or_ffr_consumed"]),
        ("V20", "ODR lane closes V3_R2 C07", detectors["odr_initial_closure"](context)),
        ("V21", "physical lane reports nonzero V3_R2 difference", context["physical"]["initial_mass_properties_vs_V3_R2_C07"]["cg_error_norm_m"] > 0.0 and context["physical"]["initial_mass_properties_vs_V3_R2_C07"]["inertia_max_abs_error_kg_m2"] > 0.0),
        ("V22", "lane scope remains rigid arm-only", detectors["lane_scope"](context)),
        ("V23", "lane numerical invariants close", detectors["lane_numerics"](context)),
        ("V24", "lane models and zero states independent", context["cross"]["independent_model_objects"] and context["cross"]["independent_zero_initial_states"] and not context["cross"]["state_transfer_between_lanes"]),
        ("V25", "lane deltas are not uncertainty", not context["cross"]["branches_selected"] and not context["cross"]["branches_averaged"] and not context["cross"]["branch_delta_is_uncertainty"] and context["cross"]["standard_uncertainty"] is None),
        ("V26", "ODR history has 451 exact rows", history[0]["row_count"] == 451 and history[0]["indices_exact"] and history[0]["lane_id_exact"]),
        ("V27", "physical history has 451 exact rows", history[1]["row_count"] == 451 and history[1]["indices_exact"] and history[1]["lane_id_exact"]),
        ("V28", "both histories start independently from zero", all(row["zero_independent_initial_state"] for row in history)),
        ("V29", "both histories span 0 to 4.5 s monotonically", all(row["time_start_s"] == 0.0 and row["time_end_s"] == 4.5 and row["time_monotonic"] for row in history)),
        ("V30", "leaf-only ROM matrix reproduces", context["rom"]["leaf_only"]["published_mass_matrix_max_abs_error_kg_m2"] <= campaign["thresholds"]["rom_mass_matrix_kg_m2"]),
        ("V31", "all five ROM frequency cases reproduce", len(context["rom"]["leaf_only"]["cases"]) == 5 and max(row["published_max_abs_error_hz"] for row in context["rom"]["leaf_only"]["cases"]) <= campaign["thresholds"]["rom_published_frequency_hz"]),
        ("V32", "ROM conflict remains nonpropagated", detectors["rom_conflict_nonpropagation"](context)),
        ("V33", "ROM dynamic mass allocation stays unfrozen", not context["rom"]["nonselecting_conflict_diagnostic"]["dynamic_mass_allocation_frozen"]),
        ("V34", "all mandatory holds remain", detectors["holds"](context)),
        ("V35", "authority detector remains fail-closed", detectors["authority"](context)),
        ("V36", "all eight deep-copy negative controls detected", len(negative) == 8 and all(row["status"] == "PASS" for row in negative)),
        ("V37", "all core result artifacts are present and hashed", len(core_hashes) == len(CORE_RESULTS) and all(row["bytes"] > 0 for row in core_hashes)),
        ("V38", "unknown uncertainties are not zero-filled", not context["gate"]["unknown_uncertainties_zero_filled"] and context["rom"]["standard_uncertainty"] is None and context["odr"]["standard_uncertainty"] is None and context["physical"]["standard_uncertainty"] is None),
    ]
    criteria = [{"id": i, "name": name, "status": "PASS" if passed else "FAIL", "passed": bool(passed)} for i, name, passed in checks]
    validation = {
        "schema": "E21_VALIDATION_V1", "generated_local": GENERATED_LOCAL,
        "status": "PASS" if all(row["passed"] for row in criteria) else "FAIL",
        "criteria": criteria,
        "criterion_counts": {"total": len(criteria), "pass": sum(row["passed"] for row in criteria), "fail": sum(not row["passed"] for row in criteria)},
        "history_checks": history, "negative_controls": negative,
        "core_artifact_hashes": core_hashes,
        "gate_verdict_reproduced": context["gate"]["verdict"],
        "overall_authority": "HOLD", "next_stage_authorized": False,
        "test_pass_grants_authority": False,
    }
    validation_blob = json_bytes(validation)

    manifest_records = [record(relative) for relative in STATIC_ARTIFACTS]
    manifest_records.extend(core_hashes)
    manifest_records.append(record(f"{PREFIX}/results/E21_VALIDATION_V1.json", validation_blob))
    manifest = {
        "schema": "E21_OUTPUT_MANIFEST_V1", "generated_local": GENERATED_LOCAL,
        "authority": "CURRENT_M7_R2_NON_RELEASE_DIAGNOSTIC_ONLY",
        "record_count": len(manifest_records), "records": manifest_records,
        "content_set_sha256": sha256_bytes(canonical_json_bytes(manifest_records)),
        "static_artifact_count": len(STATIC_ARTIFACTS),
        "core_result_count": len(CORE_RESULTS),
        "validation_included": True,
        "manifest_self_reference_excluded": True,
        "manifest_self_sha256": None,
        "expected_result_file_count_including_manifest": len(CORE_RESULTS) + 2,
        "next_stage_authorized": False, "release_credit": False,
    }
    manifest_blob = json_bytes(manifest)
    return validation, validation_blob, manifest, manifest_blob


def write_or_check(validation_blob: bytes, manifest_blob: bytes, check_only: bool) -> None:
    expected = {
        "E21_VALIDATION_V1.json": validation_blob,
        "E21_OUTPUT_MANIFEST_V1.json": manifest_blob,
    }
    failures = []
    for name, blob in expected.items():
        path = RESULTS_ROOT / name
        if check_only:
            if not path.is_file() or path.read_bytes() != blob:
                failures.append(name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(blob)
    actual_names = {p.name for p in RESULTS_ROOT.iterdir() if p.is_file()}
    expected_names = set(CORE_RESULTS) | set(expected)
    if actual_names != expected_names:
        failures.append(f"result_set:{sorted(actual_names ^ expected_names)}")
    if list(MODULE_ROOT.rglob("__pycache__")) or list(MODULE_ROOT.rglob("*.pyc")):
        failures.append("python_cache_present")
    if failures:
        raise SystemExit("E21_VALIDATION_CHECK_FAILED: " + ", ".join(failures))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    validation, validation_blob, manifest, manifest_blob = build_validation()
    if validation["status"] != "PASS":
        failed = [row["id"] for row in validation["criteria"] if not row["passed"]]
        raise SystemExit("E21_VALIDATION_FAIL: " + ", ".join(failed))
    write_or_check(validation_blob, manifest_blob, args.check_only)
    print(
        f"E21_VALIDATION_OK criteria={validation['criterion_counts']['pass']}/"
        f"{validation['criterion_counts']['total']} negative_controls={len(validation['negative_controls'])}/8 "
        f"manifest_records={manifest['record_count']} overall=HOLD"
    )


if __name__ == "__main__":
    main()
