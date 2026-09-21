"""Build the fail-closed CHECKPOINT-A R2 Full-Flex aggregate.

The upstream artifacts are immutable inputs to this builder.  CHECKPOINT-A is
considered reached when the evaluation is complete; it is not equivalent to a
PASS, an Owner acceptance, a next-stage authorization, or release credit.
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[3]


PATHS = {
    "owner_directives": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/00_authority/M7_OWNER_DECISION_ODR_GPT_01_TO_06_TERMINAL_CLOSURE_V1.yaml",
    "handover_receipt": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/gpt_terminal_handover/GPT_TERMINAL_HANDOVER_RECEIPT_V1.json",
    "handover_frontier": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/gpt_terminal_handover/GPT_CURRENT_FRONTIER_MATRIX_V1.csv",
    "accepted_urdf": "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
    "mpi_bridge": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/02_bridge/B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml",
    "mpi_gate": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/08_gate/MPI_BRIDGE_GATE_V1.json",
    "round3_gate": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/round3_hf_rom_v2/R2_FULL_FLEX_HF_ROM_GATE_V2.json",
    "round3_rom": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/round3_hf_rom_v2/R2_FIVE_MODE_ROM_V2.json",
    "round3_npz": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/round3_hf_rom_v2/R2_HF_ROM_NUMERICAL_DATA_V2.npz",
    "e22_gate": "30_simulation/e22_r2_full_flex_coupled_diagnostics/results/E22_R2_FULL_FLEX_COUPLED_GATE_V1.json",
    "e22_cases": "30_simulation/e22_r2_full_flex_coupled_diagnostics/results/E22_R2_COUPLED_CASES_V1.json",
    "e22_independent": "30_simulation/e22_r2_full_flex_coupled_diagnostics/results/E22_INDEPENDENT_RECOMPUTE_V1.json",
    "e22_replay": "30_simulation/e22_r2_full_flex_coupled_diagnostics/results/E22_DETERMINISM_REPLAY_V1.json",
    "e22_manifest": "30_simulation/e22_r2_full_flex_coupled_diagnostics/results/E22_PACKAGE_MANIFEST_V1.json",
    "rom5_falsifier": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/checkpoint_a/red_team/ROM5_DIMENSION_FALSIFIER_V1.json",
    "rom5_falsifier_script": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/checkpoint_a/red_team/recompute_rom5_dimension_falsifier.py",
    "final_red_team": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/checkpoint_a/red_team/R2_FULL_FLEX_FINAL_RED_TEAM_AUDIT_V1.json",
    "e15_gate": "30_simulation/e15_ancf_certification/results/gate_summary.json",
    "harness_gate": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/04_mission/B601_HARNESS_MISSION_COVERAGE_GATE.json",
    "route_c_registry": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/route_c_prep/ROUTE_C_C2_01_REGISTRY_SKELETON_V1.yaml",
    "route_c_admission": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/route_c_prep/ROUTE_C_C2_ADMISSION_GATE_V1.yaml",
    "handoff_gate": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/07_release/MECHANICAL_TO_EMBODIED_HANDOFF_GATE_V2.json",
}


def full(relative: str) -> Path:
    return PROJECT_ROOT / relative


def sha256(relative: str | Path) -> str:
    path = full(relative) if isinstance(relative, str) else relative
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def read_json(key: str) -> dict[str, Any]:
    return json.loads(full(PATHS[key]).read_text(encoding="utf-8"))


def read_yaml(key: str) -> dict[str, Any]:
    return yaml.safe_load(full(PATHS[key]).read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(f"CHECKPOINT_A_FAIL_CLOSED: {message}")


def criterion(identifier: str, name: str, passed: bool, evidence: str) -> dict[str, Any]:
    return {"id": identifier, "name": name, "pass": bool(passed), "evidence": evidence}


def artifact(key: str, state: str, authority: str) -> dict[str, Any]:
    relative = PATHS[key]
    path = full(relative)
    return {
        "id": key,
        "path": relative,
        "bytes": path.stat().st_size,
        "sha256": sha256(relative),
        "state": state,
        "authority": authority,
    }


def frontier_row(
    item_id: str,
    domain: str,
    artifact_name: str,
    path: str,
    verification_status: str,
    frontier_status: str,
    machine_state: str,
    authority_basis: str,
    next_action: str,
) -> dict[str, Any]:
    disk_path = full(path)
    exists = disk_path.exists()
    return {
        "item_id": item_id,
        "domain": domain,
        "artifact": artifact_name,
        "path": path,
        "exists": str(exists).lower(),
        "bytes": disk_path.stat().st_size if exists and disk_path.is_file() else "",
        "sha256": sha256(path) if exists and disk_path.is_file() else "",
        "verification_status": verification_status,
        "frontier_status": frontier_status,
        "machine_state": machine_state,
        "authority_basis": authority_basis,
        "next_action": next_action,
    }


def main() -> None:
    for key, relative in PATHS.items():
        require(full(relative).is_file(), f"missing required artifact {key}: {relative}")

    owner = read_yaml("owner_directives")
    mpi = read_json("mpi_gate")
    component = read_json("round3_gate")
    e22 = read_json("e22_gate")
    cases = read_json("e22_cases")
    independent = read_json("e22_independent")
    replay = read_json("e22_replay")
    manifest = read_json("e22_manifest")
    falsifier = read_json("rom5_falsifier")
    final_red_team = read_json("final_red_team")
    e15 = read_json("e15_gate")
    harness = read_json("harness_gate")
    route_registry = read_yaml("route_c_registry")
    route_admission = read_yaml("route_c_admission")
    handoff = read_json("handoff_gate")

    require(owner["directives"][0]["recorded_effect"]["bridge_status"] == "CONFIRMED_MECHANICAL_DYNAMICS_BRIDGE", "ODR-GPT-01 bridge not confirmed")
    require(mpi["mpi_gate"] == "PASS", "MPI Gate is not PASS")
    require(mpi["criterion_counts"] == {"total": 9, "pass": 9, "fail": 0}, "MPI criterion count changed")
    require(all(float(mpi["bottom_line_metrics"][name]) == 0.0 for name in ("frame_ambiguity", "mass_inconsistency", "inertia_inconsistency", "consumer_ambiguity", "hash_mismatch")), "MPI bottom-line metric is nonzero")
    require(component["technical_verdict"] == "PASS_WITH_DECLARED_PROVISIONAL_PHYSICS", "Round3 component Gate changed")
    require(component["summary"] == {"passed": 17, "total": 17}, "Round3 component Gate is not 17/17")
    require(e22["technical_verdict"] == "HOLD_R2_HF_TO_ROM_DYNAMIC_VALIDATION_FAILED", "E22 verdict changed")
    require(e22["summary"] == {"passed": 16, "total": 18, "failed": ["G11", "G17"]}, "E22 Gate is not the frozen 16/18 G11/G17 HOLD")
    require(independent["pass"] is True and independent["summary"] == {"passed": 33, "total": 33, "failed": []}, "E22 independent recompute is not 33/33")
    require(replay["pass"] is True and replay["summary"]["passed"] == 5 and replay["summary"]["unique_independent_report_hashes"] == 1 and replay["summary"]["five_mode_max_relative_spread"] == 0.0, "E22 determinism replay changed")
    for relative, expected in manifest["package_assets"].items():
        require(sha256(relative) == expected, f"E22 package manifest mismatch: {relative}")
    require(falsifier["verdict"] == "ROM5_FULL_FIELD_TRUNCATION_FALSIFIED_AT_1PCT", "ROM5 falsifier verdict changed")
    require(final_red_team["primary_disposition"]["audit_conclusion"] == "NO_NEW_BLOCKER_BEYOND_DECLARED_G11_AND_G17", "final red-team found an additional blocker")
    require(final_red_team["primary_disposition"]["ten_point_audit_summary"] == {"pass": 8, "fail": 2, "failed_items": ["A07_MODE_RECONSTRUCTION_AND_HF_ROM_FALSIFIER", "A08_LEGACY_R1_SAME_SCOPE_COMPLETENESS"]}, "final red-team tally changed")
    require(e15["overall"] == "REPEAT_ANCF_CERTIFICATION", "e15 state changed")
    require(harness["harness_gate"] == "FAIL_AT_MANDATORY_KEY_STATES" and harness["mission_coverage"] == "FAIL", "harness mission state changed")
    require(sum(bool(x["pass"]) for x in harness["key_state_checks"]) == 0 and len(harness["key_state_checks"]) == 10, "harness key-state count changed")
    require(harness["trajectory_segments_with_released_authority"] == 0 and harness["trajectory_segments_unknown"] == 8, "harness trajectory count changed")
    require(route_registry["summary"]["entries_total"] == 13 and route_registry["summary"]["value_non_null"] == 0 and route_registry["summary"]["status_HOLD"] == 13, "Route-C registry null/HOLD count changed")
    require(route_admission["current_evaluation"]["tally"]["pass"] == 2 and route_admission["current_evaluation"]["tally"]["fail"] == 6 and route_admission["current_evaluation"]["ROUTE_C_CAD_AUTHORIZED"] is False, "Route-C admission state changed")
    require(handoff["checks_passed"] == 11 and handoff["checks_total"] == 12 and handoff["failing_checks"] == ["G12"] and handoff["verdict"] == "MECHANICAL_TO_EMBODIED_HANDOFF_FAIL", "handoff Gate state changed")

    nominal_cases: dict[str, dict[str, Any]] = {}
    for item in cases["solar_R2_flex_current_undamped_gate"]:
        if item["corner"] == "NOMINAL":
            post = item["post_capture"]
            nominal_cases[item["scenario"]] = {
                "case_id": item["case_id"],
                "omega_plus_equiv_dps": post["omega_plus_equiv_dps"],
                "base_rate_initial_dps": post["post_capture_rate_initial_dps"],
                "base_rate_peak_dps": post["post_capture_rate_max_dps"],
                "base_rate_final_dps": post["post_capture_rate_final_dps"],
                "base_attitude_excursion_max_deg": post["base_attitude_excursion_max_deg"],
                "modal_energy_max_J": post["modal_energy_max_J"],
                "wheel_momentum_required_Nms": post["wheel_momentum_required_Nms"],
                "classification": item["diagnostic_gate_classification"],
                "classification_scope": item["authority"]["classification_scope"],
            }
    require(set(nominal_cases) == {"TARGET_22KG_0P5DPS", "TARGET_150KG_3DPS"}, "nominal coupled scenarios incomplete")

    route_fields = [entry["quantity"] for entry in route_registry["registry_entries"]]
    metrics = e22["key_metrics"]
    criteria = [
        criterion("A01", "disk frontier and Owner directives verified", True, "handover snapshot retained; ODR-GPT-01..06 source-controlled"),
        criterion("A02", "MPI physical-to-dynamics bridge confirmed", True, "9/9; five bottom-line ambiguity/inconsistency/hash metrics are zero"),
        criterion("A03", "Round3 component HF/ROM construction Gate", True, "17/17 PASS_WITH_DECLARED_PROVISIONAL_PHYSICS"),
        criterion("A04", "R2 coupled campaign execution and numerical integrity", True, "LOW/NOMINAL/HIGH; two target scenarios; G01-G10 and G12-G16/G18 PASS"),
        criterion("A05", "independent reproduction and deterministic replay", True, "33/33 independent; five isolated runs, one report hash, zero metric spread"),
        criterion("A06", "independent final red-team completed", True, "10 items audited; no new blocker beyond G11/G17"),
        criterion("A07", "183-DOF HF to P2-bounded ROM5 full-field error <=1%", False, f"{100.0 * metrics['hf_to_rom_five_mode_max_relative']:.9f}% > 1%"),
        criterion("A08", "Rigid / Legacy R1 / Solar R2 two-scenario same-scope completeness", False, "Legacy R1 22 kg unavailable; 150 kg historical-only and causally incompatible"),
        criterion("A09", "e15 R2 certification inherited or rerun PASS", False, "REPEAT_ANCF_CERTIFICATION; NOT_INHERITED"),
        criterion("A10", "mandatory harness mission coverage", False, "0/10 key states SAFE; 0/8 segments released"),
        criterion("A11", "Route-C C2 physical registry and CAD admission", False, "13/13 physical fields null/HOLD; admission 2/8; CAD=false"),
        criterion("A12", "mechanical-to-embodied handoff V2", False, "11/12; G12 HARNESS_RATED_OPERATIONAL_ENVELOPE FAIL"),
    ]
    passed = sum(item["pass"] for item in criteria)

    confirmed = [
        artifact("owner_directives", "CURRENT_DIRECT_OWNER_DIRECTIVES", "Owner attachment registration; no acceptance claim"),
        artifact("accepted_urdf", "CURRENT_FROZEN", "KINEMATIC_AUTHORITY and MASS_INERTIA_AUTHORITY"),
        artifact("mpi_bridge", "CONFIRMED_MECHANICAL_DYNAMICS_BRIDGE", "ODR-GPT-01"),
        artifact("mpi_gate", "PASS_9_OF_9", "MPI scoped machine Gate"),
        artifact("round3_gate", "PASS_WITH_DECLARED_PROVISIONAL_PHYSICS_17_OF_17", "component HF/ROM Gate only"),
        artifact("round3_npz", "VERIFIED_NUMERICAL_PACKAGE", "Round3 component evidence"),
        artifact("e22_gate", "HOLD_16_OF_18_G11_G17", "coupled diagnostic machine Gate"),
        artifact("e22_independent", "PASS_33_OF_33", "independent raw-file/NPZ recompute"),
        artifact("e22_replay", "PASS_5_OF_5_DETERMINISTIC", "isolated-process replay"),
        artifact("e22_manifest", "VERIFIED_ACYCLIC_PACKAGE_MANIFEST", "post-Gate reverse pin"),
        artifact("rom5_falsifier", "VERIFIED_NEGATIVE_RESULT", "independent 792-subset falsifier"),
        artifact("final_red_team", "FINAL_AUDIT_8_PASS_2_DECLARED_FAIL", "independent final red-team"),
        artifact("e15_gate", "CONFIRMED_REPEAT", "scientific Gate SSOT"),
        artifact("harness_gate", "CONFIRMED_FAIL", "mission harness machine Gate"),
        artifact("route_c_registry", "CONFIRMED_13_NULL_HOLD", "ODR-GPT-03 current physical-input fact"),
        artifact("handoff_gate", "CONFIRMED_FAIL_11_OF_12", "current harness-aware handoff evidence"),
    ]

    unconfirmed = [
        {"item": "P2-compliant ROM satisfying the registered 1% full-field dynamic contract", "state": "NOT_AVAILABLE", "reason": "all 792 tested 5D HF subsets fail; best is 1.082963756%"},
        {"item": "Legacy R1 22 kg same-scope comparison", "state": "MISSING", "reason": "no artifact exists; no interpolation or substitution allowed"},
        {"item": "Legacy R1 150 kg same-scope comparison", "state": "NOT_AUTHORIZED_FOR_CAUSAL_COMPARISON", "reason": "historical mass/placement/arm/modal/initial-state scope differs"},
        {"item": "R2 e15 ANCF certification", "state": "NOT_INHERITED", "reason": "current Gate remains REPEAT_ANCF_CERTIFICATION"},
        {"item": "Harness-rated mandatory mission envelope", "state": "NOT_RELEASED", "reason": "all ten key states UNSAFE"},
        {"item": "Route-C physical capability authority", "state": "MISSING_EXTERNAL_PHYSICAL_DATA", "reason": "P01-P13 all null/HOLD"},
        {"item": "Route-C CAD", "state": "PROHIBITED", "reason": "ODR-GPT-03; C2 admission not satisfied"},
        {"item": "Terminal mechanical release package", "state": "NOT_GENERATED", "reason": "Checkpoint-A is HOLD; handoff and harness fail"},
    ]

    output = {
        "schema": "R2_FULL_FLEX_GATE_V1",
        "checkpoint": "CHECKPOINT-A__R2_FULL_FLEX_GATE",
        "generated_local": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "generator": "GPT mechanical chief and multi-agent Loop Engineering integrator",
        "checkpoint_reached": True,
        "checkpoint_outcome": "HOLD",
        "technical_verdict": "CHECKPOINT_A_REACHED__R2_FULL_FLEX_HOLD_ROM5_TRUNCATION_AND_LEGACY_R1_SCOPE__E15_NOT_INHERITED__NO_RELEASE_CREDIT",
        "scope": "R2 Full-Flex component model, coupled diagnostic campaign, independent reproduction, adversarial audit, and downstream authority guards; not flight qualification or mechanical release",
        "criteria": criteria,
        "summary": {"passed": passed, "total": len(criteria), "failed": [item["id"] for item in criteria if not item["pass"]]},
        "mpi_final_status": {
            "status": "CONFIRMED_MECHANICAL_DYNAMICS_BRIDGE",
            "machine_gate": "PASS",
            "criteria": "9/9",
            "bottom_line_metrics": {name: mpi["bottom_line_metrics"][name] for name in ("frame_ambiguity", "mass_inconsistency", "inertia_inconsistency", "consumer_ambiguity", "hash_mismatch")},
            "physical_installation_authority": "WP11",
            "dynamics_frame_authority": "ODR-01 T_SM",
            "unique_bridge": "T_PHYSICAL_TO_DYNAMICS",
            "numeric_bridge": "Trans(z,+0.02275 m) then Rot(z,+25.000014 deg)",
            "release_credit": False,
        },
        "full_flex": {
            "component_gate": {"technical_verdict": component["technical_verdict"], "summary": component["summary"], "key_metrics": component["key_metrics"]},
            "coupled_gate": {"technical_verdict": e22["technical_verdict"], "summary": e22["summary"], "key_metrics": metrics, "authority_dispositions": e22["authority_dispositions"]},
            "nominal_scenario_diagnostics": nominal_cases,
            "rom5_falsification": {
                "verdict": falsifier["verdict"],
                "current_rom5_max_relative": falsifier["current_round3_rom5"]["global_max_relative_error"],
                "best_any_5D_max_relative": falsifier["dimension_combination_falsifier"]["best_five_dimensional_subset"]["global_max_relative_error"],
                "minimum_passing_dimension": falsifier["dimension_combination_falsifier"]["minimum_passing_dimension_within_first12"],
                "minimum_passing_6D_max_relative": falsifier["dimension_combination_falsifier"]["best_six_dimensional_subset"]["global_max_relative_error"],
                "passing_7D_preserving_three_bending_max_relative": falsifier["dimension_combination_falsifier"]["best_seven_dimensional_subset_preserving_three_bending_modes"]["global_max_relative_error"],
                "P2_current_max_modes_per_wing": 5,
            },
            "legacy_comparison": cases["three_lane_two_scenario_comparison"],
            "e15": {"current": e15["overall"], "max_cross_solver_relative_difference": e15["cross_solver_diagnostic"]["max_relative_difference"], "inheritance": "NOT_INHERITED"},
            "independent_reproduction": {"summary": independent["summary"], "pass": independent["pass"], "determinism_replay": replay["summary"], "writer_response_match_relative_max": replay["runs"][0]["writer_response_match_relative_max"]},
            "remaining_work": [
                "Owner/P2 contract change plus upstream ROM regeneration: 6D B1+B2+T1-T4, or 7D B1-B3+T1-T4 if three-bending-family retention is mandatory; no silent extension is authorized.",
                "Provide a same-scope Legacy R1 two-scenario evidence lane or explicitly rescope the comparison requirement; keep G17 fail-closed until then.",
                "After a closed R2 model exists, rerun e15; the existing REPEAT_ANCF_CERTIFICATION state is not inherited.",
                "Keep long-horizon PROJECTED_EXPONENTIAL versus implicit validation as an explicit nonclaim until machine-bound; the 0.5 s read-only witness is nonblocking and not release evidence.",
            ],
        },
        "harness_mission": {
            "mission_coverage": harness["mission_coverage"],
            "harness_gate": harness["harness_gate"],
            "key_states_safe": 0,
            "key_states_total": 10,
            "trajectory_segments_released": harness["trajectory_segments_with_released_authority"],
            "trajectory_segments_total": 8,
            "trajectory_segments_unknown": harness["trajectory_segments_unknown"],
            "route_b": harness["route_b"],
            "route_c_escalation": harness["route_c_escalation"],
            "ODR_GPT_04_defer_condition_met": False,
        },
        "route_c": {
            "authority": "ODR-GPT-03",
            "physical_registry_fields": route_fields,
            "fields_total": route_registry["summary"]["entries_total"],
            "fields_non_null": route_registry["summary"]["value_non_null"],
            "fields_hold": route_registry["summary"]["status_HOLD"],
            "existing_admission_evaluation": route_admission["current_evaluation"]["tally"],
            "ROUTE_C_CAD_AUTHORIZED": False,
            "allowed_now": ["RFI-E", "RFI-F", "RFI-G", "traceable physical registry updates"],
            "forbidden_now": ["Route-C CAD", "null-to-zero", "LLM estimate as authority", "Route-B seed inheritance"],
            "authority_note": "The existing admission file supplies reproducible 2/8 and 13-null facts; current authority is ODR-GPT-03, not its embedded older Owner provenance.",
        },
        "mechanical_to_embodied_handoff": {"verdict": handoff["verdict"], "passed": handoff["checks_passed"], "total": handoff["checks_total"], "failed": handoff["failing_checks"], "next_stage_authorized": handoff["next_stage_authorized"]},
        "confirmed_artifacts": confirmed,
        "unconfirmed_or_blocked_artifacts": unconfirmed,
        "agent_assignments": [
            {"agent": "A0 / Mechanical Chief", "responsibility": "authority, dependency graph, Gate aggregation, Checkpoint-A issuance", "status": "COMPLETED_CHECKPOINT_A"},
            {"agent": "A2 / Full-Flex owner", "responsibility": "Round3 consumption, coupled LOW/NOMINAL/HIGH campaign, independent recompute, deterministic CM", "status": "COMPLETED_WITH_G11_G17_HOLD"},
            {"agent": "A5 / ROM5 Falsifier", "responsibility": "792 five-dimensional subsets, minimum passing dimension, contact-window falsification", "status": "COMPLETED_NEGATIVE_RESULT"},
            {"agent": "A5 / Final Red Team", "responsibility": "mass/frame/tensor/conservation/hash/determinism/fail-closed audit", "status": "COMPLETED_NO_NEW_BLOCKER"},
        ],
        "heavy_task_schedule": {
            "discipline": "one large solver at a time; no concurrent CAD writer or heavy solver",
            "completed_serially": ["Round3 183-DOF component HF/ROM", "E22 coupled campaign", "deterministic final rebuild", "five isolated independent replays"],
            "active_heavy_task": None,
            "next_heavy_task": "NONE_AUTHORIZED_AT_CHECKPOINT_A",
        },
        "next_automatic_action": [
            "Freeze the current Checkpoint-A evidence; do not relabel HOLD as PASS.",
            "Prepare the P2 mode-count/acceptance-contract decision package; do not generate a 6D/7D ROM without Owner authorization.",
            "Continue Route-C only through RFI-E/F/G and traceable P01-P13 physical registry closure; do not generate CAD.",
            "Do not rerun e15 or terminal handoff until the upstream ROM contract and harness physical authority are actually closed.",
        ],
        "terminal_release_candidate_generated": False,
        "review_status": "PENDING_OWNER_REVIEW",
        "owner_accepted": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "self_hash_policy": "SELF_REFERENCE_EXCLUDED; CHECKPOINT_A_SHA256.csv pins this Gate after emission",
        "evidence_hashes": {item["path"]: item["sha256"] for item in confirmed},
    }

    gate_path = HERE / "R2_FULL_FLEX_GATE_V1.json"
    gate_path.write_text(json.dumps(output, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")

    rows = [
        frontier_row("CPA-001", "HANDOVER", "Pre-Checkpoint-A disk frontier snapshot", PATHS["handover_receipt"], "VERIFIED", "HISTORICAL_SNAPSHOT_RETAINED", "Pre-Checkpoint-A receipt; not overwritten", "ODR-GPT handover", "Use this Checkpoint-A supplement for the current frontier"),
        frontier_row("CPA-002", "FRAMES", "MPI bridge Gate", PATHS["mpi_gate"], "VERIFIED", "CURRENT", "PASS 9/9; bridge CONFIRMED", "ODR-GPT-01", "Consume the unique bridge; no release credit"),
        frontier_row("CPA-003", "R2_COMPONENT", "Round3 HF/ROM component Gate", PATHS["round3_gate"], "VERIFIED", "CURRENT", "17/17 PASS_WITH_DECLARED_PROVISIONAL_PHYSICS", "Round3 component machine Gate", "Retain as component evidence only"),
        frontier_row("CPA-004", "R2_COUPLED", "E22 R2 Full-Flex coupled Gate", PATHS["e22_gate"], "VERIFIED", "CURRENT", "HOLD 16/18; G11/G17 FAIL", "E22 machine Gate", "Resolve ROM dimension contract and Legacy same-scope evidence"),
        frontier_row("CPA-005", "R2_INDEPENDENT", "E22 independent recompute", PATHS["e22_independent"], "VERIFIED", "CURRENT", "PASS 33/33", "Independent raw-file/NPZ recompute", "Retain with package manifest"),
        frontier_row("CPA-006", "R2_DETERMINISM", "E22 five-run replay", PATHS["e22_replay"], "VERIFIED", "CURRENT", "PASS 5/5; unique hash=1; spread=0", "Isolated-process replay", "Retain with package manifest"),
        frontier_row("CPA-007", "R2_ADVERSARIAL", "ROM5 dimension falsifier", PATHS["rom5_falsifier"], "VERIFIED", "CURRENT", "All 792 5D subsets fail 1%", "Independent red-team falsifier", "Owner/P2 contract decision required"),
        frontier_row("CPA-008", "R2_ADVERSARIAL", "Final R2 Full-Flex red-team audit", PATHS["final_red_team"], "VERIFIED", "CURRENT", "8 PASS / 2 declared FAIL; no new blocker", "Independent final audit", "Keep G11/G17 open"),
        frontier_row("CPA-009", "E15", "ANCF certification Gate", PATHS["e15_gate"], "VERIFIED", "HOLD", "REPEAT_ANCF_CERTIFICATION", "Scientific Gate SSOT", "Rerun only after closed R2 model"),
        frontier_row("CPA-010", "HARNESS", "Mandatory mission coverage Gate", PATHS["harness_gate"], "VERIFIED", "HOLD", "FAIL; 0/10 SAFE; 0/8 segments released", "ODR-GPT-04 condition evidence", "Continue Route-C physical closure"),
        frontier_row("CPA-011", "ROUTE_C", "C2 physical registry", PATHS["route_c_registry"], "VERIFIED", "HOLD", "13/13 null/HOLD; CAD=false", "ODR-GPT-03", "RFI-E/F/G only; no CAD"),
        frontier_row("CPA-012", "EMBODIED_HANDOFF", "Harness-aware handoff V2", PATHS["handoff_gate"], "VERIFIED", "HOLD", "FAIL 11/12; G12", "Current handoff evidence", "Rebuild only after upstream closure"),
        frontier_row("CPA-013", "TERMINAL_RELEASE", "MECHANICAL_ENGINEERING_RELEASE_V1", "20_engineering/MECHANICAL_ENGINEERING_RELEASE_V1", "MISSING", "HOLD", "Not generated", "Checkpoint-A machine verdict", "Do not generate while G11/G17/e15/harness/handoff remain open"),
    ]
    frontier_path = HERE / "CHECKPOINT_A_FRONTIER_SUPPLEMENT_V1.csv"
    with frontier_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    gate_hash = sha256(gate_path)
    receipt = f"""# R2 Full-Flex CHECKPOINT-A 收据

## 总裁决

`CHECKPOINT-A` 已到达，但结果是 **HOLD，不是 PASS**。

- 机器裁决：`{output['technical_verdict']}`
- R2 组件 HF/ROM：17/17，`PASS_WITH_DECLARED_PROVISIONAL_PHYSICS`
- R2 耦合诊断：16/18，仅 G11、G17 失败
- Owner 状态：`PENDING_OWNER_REVIEW`；`owner_accepted=false`
- `next_stage_authorized=false`；`release_credit=false`
- Checkpoint Gate SHA-256：`{gate_hash}`

## 当前磁盘前沿

当前前沿由 `CHECKPOINT_A_FRONTIER_SUPPLEMENT_V1.csv` 记录；原 `GPT_TERMINAL_HANDOVER_RECEIPT_V1.json` 和 `GPT_CURRENT_FRONTIER_MATRIX_V1.csv` 保留为检查点前快照，不覆盖。

已确认：MPI 唯一桥、Round3 组件 HF/ROM、E22 两场景三角点 coupled campaign、独立复算、五次确定性重放、ROM5 falsifier、终版红队、现行 e15/线束/Route-C/Handoff 负状态均已落盘并哈希化。

未闭合：P2 五模 1% 全场合同、Legacy R1 同口径两场景、R2 e15 再认证、任务线束覆盖、Route-C 物理能力、Handoff 12/12 和终局 Release 包。

## MPI final status

- `CONFIRMED_MECHANICAL_DYNAMICS_BRIDGE`
- 9/9 PASS；frame/mass/inertia/consumer/hash 五个底线量均为 0
- 物理安装权威：WP11；动力学帧权威：ODR-01 `T_SM`
- 唯一桥：`T_PHYSICAL_TO_DYNAMICS = Trans(z,+0.02275 m) · Rot(z,+25.000014°)`
- 该确认只覆盖安装语义桥，不产生机械 Release credit

## Full-Flex 状态与剩余工作

- 183-DOF HF→当前 ROM5 全场最大相对误差：{100.0 * metrics['hf_to_rom_five_mode_max_relative']:.9f}% > 1%
- 792 个五维 HF 组合全部失败；最佳五维：{100.0 * metrics['independent_best_any_5D_HF_subset_max_relative']:.9f}%
- 最小通过为 6D：0.657580852%；保留三弯曲族需 7D：0.271439113%
- P2 当前上限为每翼 5 模态，不能静默扩成 6D/7D；需要 Owner/P2 合同变更与上游 ROM 重生
- Legacy R1：22 kg 同口径证据不存在；150 kg 仅历史复现且因果口径不兼容，G17 保持 FAIL
- e15 保持 `REPEAT_ANCF_CERTIFICATION` / `NOT_INHERITED`

名义诊断：22 kg@0.5°/s 得 `omega_plus_equiv=0.160367°/s`、`Hc=0.0117823 N·m·s`；150 kg@3°/s 得 `3.042713°/s`、`3.646612 N·m·s`。两者均为 E22 provisional diagnostic，不继承 sim10 Gate。

## Harness mission coverage

- `FAIL_AT_MANDATORY_KEY_STATES`
- 10 个必需关键状态：0 SAFE / 10 UNSAFE
- 8 条任务轨迹：0 released / 8 UNKNOWN
- ODR-GPT-04 的 Route-C 延期条件不成立；Route-B 精确负结果继续冻结
- Handoff V2：11/12，G12 `HARNESS_RATED_OPERATIONAL_ENVELOPE` 失败

## Route-C physical null fields

13/13 均为 null/HOLD：`{'`, `'.join(route_fields)}`。

现有准入评估为 2/8 PASS、6/8 FAIL；`ROUTE_C_CAD_AUTHORIZED=false`。只允许继续 RFI-E/F/G 和可追溯物理注册，不允许猜值、null→0、继承 Route-B seed 或生成 Route-C CAD。

## Agent assignments

- A0：权威、依赖图、聚合 Gate 与 Checkpoint-A 签发——完成
- A2：Full-Flex coupled campaign、独立复算与确定性 CM——完成，G11/G17 HOLD
- A5-Falsifier：792 个五维组合与最小通过维数——完成负结果
- A5-Red Team：质量/帧/张量/守恒/哈希/确定性终审——完成，无新增阻断

## Heavy-task schedule

Round3 HF/ROM、E22 campaign、确定性终版重建和五次独立重放均已按单一大型任务串行完成。当前无正在运行的 heavy solver，也未授权新的 heavy task；Route-C CAD 未启动。

## 下一自动动作

1. 冻结本 Checkpoint-A 证据，不把 HOLD 改写为 PASS。
2. 准备 P2 模态数量/验收合同决策包；未经 Owner 授权不生成 6D/7D ROM。
3. Route-C 仅继续 RFI-E/F/G 与 P01-P13 物理注册闭合；不生成 CAD。
4. 在 ROM 合同与线束物理权威闭合前，不重跑 e15、不签发 Handoff 12/12、不创建终局 Release 包。
"""
    receipt_path = HERE / "R2_FULL_FLEX_CHECKPOINT_A_RECEIPT_V1.md"
    receipt_path.write_text(receipt, encoding="utf-8")

    hash_rows = []
    pinned = [Path(__file__).resolve(), gate_path, frontier_path, receipt_path]
    pinned.extend(full(relative) for relative in PATHS.values())
    seen: set[Path] = set()
    for path in pinned:
        path = path.resolve()
        if path in seen:
            continue
        seen.add(path)
        hash_rows.append({
            "path": path.relative_to(PROJECT_ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
            "role": "CHECKPOINT_OUTPUT" if HERE in path.parents or path == Path(__file__).resolve() else "PINNED_INPUT",
        })
    hashes_path = HERE / "CHECKPOINT_A_SHA256.csv"
    with hashes_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "bytes", "sha256", "role"])
        writer.writeheader()
        writer.writerows(hash_rows)

    print(json.dumps({
        "checkpoint_reached": True,
        "outcome": "HOLD",
        "gate_sha256": sha256(gate_path),
        "frontier_sha256": sha256(frontier_path),
        "receipt_sha256": sha256(receipt_path),
        "sha256_rows": len(hash_rows),
        "failed_criteria": output["summary"]["failed"],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
