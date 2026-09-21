#!/usr/bin/env python3
"""Build the append-only R2 current-state reissue.

The output order is deliberately one-way:

    INPUT_MANIFEST -> GATE -> PACKAGE_MANIFEST

The package manifest excludes itself.  No parent artifact is modified.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any, Iterable


PACKAGE_REL = Path(
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/current_state_reissue_v2"
)
INPUT_NAME = "R2_CURRENT_STATE_INPUT_MANIFEST_V2.json"
GATE_NAME = "R2_CURRENT_STATE_GATE_V2.json"
PACKAGE_NAME = "R2_CURRENT_STATE_PACKAGE_MANIFEST_V2.json"


class CurrentStateError(RuntimeError):
    """Raised when an upstream truth no longer satisfies this reissue contract."""


SOURCE_SPECS: tuple[tuple[str, str, str, str], ...] = (
    (
        "terminal_release_gate",
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/00_RELEASE_GATE.json",
        "frozen terminal mechanical ruling",
        "SNAPSHOT_ONLY_NO_CURRENT_PASS_INHERITANCE",
    ),
    (
        "baseline_manifest_with_self_defect",
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/01_BASELINE_MANIFEST.json",
        "frozen baseline manifest and self-fingerprint defect source",
        "DEFECT_EVIDENCE_ONLY_NO_REPAIR_AUTHORITY",
    ),
    (
        "terminal_release_sha256",
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/22_RELEASE_SHA256.csv",
        "frozen release hash ledger",
        "FROZEN_LEDGER_NO_PARENT_MUTATION",
    ),
    (
        "odr60_option_a_execution_closure",
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/results/ODR60_OPTION_A_EXECUTION_CLOSURE_GATE_V1.json",
        "current Option-A mount/frame and M01 readiness truth",
        "STATIC_PREFLIGHT_CANDIDATE_ONLY",
    ),
    (
        "m01_system_collision_registry_gate",
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/system_registry/M01_SYSTEM_COLLISION_REGISTRY_GATE_V1.json",
        "current object/pair universe audit",
        "STATIC_REGISTRY_ONLY_NO_QUERY_AUTHORITY",
    ),
    (
        "m01_system_binding_readiness_gate",
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_SYSTEM_BINDING_CONTRACT_V1/SYSTEM_BINDING_READINESS_GATE_V1.json",
        "current M01 binding-contract readiness",
        "METADATA_BINDING_ONLY_NO_PAIR_EDGE_PATH_AUTHORITY",
    ),
    (
        "m01_query_infrastructure_gate",
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_QUERY_INFRASTRUCTURE_V1/QUERY_INFRASTRUCTURE_GATE_V1.json",
        "current query-infrastructure static fixture truth",
        "STATIC_FIXTURES_ONLY_NO_QUERY_OR_SEARCH_AUTHORITY",
    ),
    (
        "route_c_m01_negative_witness",
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/ROUTE_C_V9F_MANDATORY_M01_FALSIFIER_GATE.json",
        "current frozen M01 straight-q Route-C negative witness",
        "NEGATIVE_ONLY_NO_ARCHITECTURE_INFEASIBILITY_CLAIM",
    ),
    (
        "sim13_post_terminal_backend_addendum",
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/loop_b/sim13_post_terminal_handoff_addendum_v1/SIM13_POST_TERMINAL_HANDOFF_ADDENDUM_GATE_V1.json",
        "post-terminal Sim13 backend negative-control subscope",
        "BACKEND_SUBSCOPE_ONLY_NO_FULL_TMG6_REISSUE",
    ),
    (
        "sim13_static_system_binding_candidate",
        "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/system_binding_candidate_v1/results/SYSTEM_BINDING_V2_RESEARCH_CANDIDATE_GATE_V1.json",
        "current static topology/schema/receipt candidate",
        "RESEARCH_CANDIDATE_LOAD_ABORT_ONLY",
    ),
    (
        "parent_dynamics_engineering_gate",
        "30_simulation/r2_dynamics_engineering_closure/results/R2_DYNAMICS_ENGINEERING_GATE_V1.json",
        "unmodified parent dynamics Gate",
        "PARENT_HOLD",
    ),
    (
        "dg1_dg2_candidate_gate",
        "30_simulation/r2_dynamics_engineering_closure/dg1_dg2_candidate_v2/results/R2_DG1_DG2_CANDIDATE_GATE_V2.json",
        "additive DG1/DG2 bounded candidate",
        "ADDITIVE_CANDIDATE_NO_PARENT_CREDIT",
    ),
    (
        "dg3_candidate_gate",
        "30_simulation/r2_dynamics_engineering_closure/dg3_arm_flex_coupling_candidate_v1/results/R2_DG3_ARM_FLEX_COUPLING_CANDIDATE_GATE_V1.json",
        "additive frozen-C0 DG3 bounded candidate",
        "ADDITIVE_CANDIDATE_NO_PARENT_CREDIT",
    ),
    (
        "dg4_candidate_gate",
        "30_simulation/r2_dynamics_engineering_closure/dg4_contact_hybrid_candidate_v1/results/DG4_CONTACT_HYBRID_GATE_V1.json",
        "additive two-body post-impact DG4 diagnostic candidate",
        "DESIGN_DIAGNOSTIC_NO_PHYSICAL_ATTACHMENT_CREDIT",
    ),
    (
        "dg5_candidate_gate",
        "30_simulation/r2_dynamics_engineering_closure/dg5_uncertainty_candidate_v1/results/R2_DG5_DESIGN_UNCERTAINTY_CANDIDATE_GATE_V1.json",
        "additive deterministic-corner DG5 design candidate",
        "DESIGN_SCREEN_NO_PROBABILITY_OR_AS_BUILT_CREDIT",
    ),
    (
        "digital_prototype_dynamics_entry_gate_v3",
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/digital_prototype_dynamics_entry_v1/CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V3.json",
        "current additive DG1-DG5 convergence ruling",
        "BOUNDED_RESEARCH_ENTRY_ONLY",
    ),
    (
        "digital_prototype_dynamics_entry_manifest_v3",
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/digital_prototype_dynamics_entry_v1/CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_MANIFEST_V3.json",
        "V3 package integrity manifest",
        "INTEGRITY_EVIDENCE_ONLY",
    ),
    (
        "control_predevelopment_gate",
        "30_simulation/control_r2_integrated_candidate/results/CTRL_R2_PREDEVELOPMENT_GATE_V1.json",
        "offline control predevelopment candidate",
        "OFFLINE_PREDEVELOPMENT_ONLY",
    ),
    (
        "parent_control_engineering_gate",
        "30_simulation/r2_control_engineering_closure/results/R2_CONTROL_ENGINEERING_GATE_V1.json",
        "unmodified parent control engineering Gate",
        "PARENT_HOLD",
    ),
    (
        "joint_dynamics_control_gate",
        "30_simulation/r2_dynamics_control_system_closure/results/R2_DYNAMICS_CONTROL_SYSTEM_GATE_V1.json",
        "current fail-closed system join",
        "JOINT_HOLD_NO_RUNTIME_EXECUTION",
    ),
    (
        "historical_safe00_gate",
        "30_simulation/safety_00_runtime_gate/results/safety_00_gate_check.json",
        "historical SAFE-00 machine Gate with pending review",
        "HISTORICAL_PASS_NO_CURRENT_TREE_OR_NEXT_STAGE_CREDIT",
    ),
    (
        "l06_drawing_set_index",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp9_release_package/DRAWING_SET_INDEX_V1.csv",
        "L06 drawing authority and manufacturing-use ledger",
        "PROTOTYPE_DOCUMENTATION_MANUFACTURING_PROHIBITED",
    ),
    (
        "l06_d05_stage_a",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp9_release_package/D05_STAGE_A.svg",
        "M3R Stage-A drawing material and sibling-hash witness",
        "DRAWING_CANDIDATE_MANUFACTURING_PROHIBITED",
    ),
    (
        "l06_d06_stage_b",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp9_release_package/D06_STAGE_B.svg",
        "M3R Stage-B drawing material and sibling-hash witness",
        "DRAWING_CANDIDATE_MANUFACTURING_PROHIBITED",
    ),
    (
        "l06_d08_assembly_stackup",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp9_release_package/D08_ASSEMBLY_STACKUP.svg",
        "assembly-stack drawing sibling-hash witness",
        "DRAWING_CANDIDATE_MANUFACTURING_PROHIBITED",
    ),
    (
        "l06_design_bom",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp9_release_package/BOM_V3_DESIGN.csv",
        "design BOM material and sibling-hash witness",
        "NOT_A_PROCUREMENT_OR_MANUFACTURING_BOM",
    ),
    (
        "current_design_material_selection",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp6_material_selection/DESIGN_MATERIAL_SELECTION_V1.yaml",
        "current design-level M3R Stage-A/B material selection",
        "DESIGN_SELECTION_NO_FLIGHT_ALLOWABLE_OR_PROCUREMENT_CREDIT",
    ),
)


def workspace_root() -> Path:
    return Path(__file__).resolve().parents[4]


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def strict_json_bytes(data: bytes, label: str) -> Any:
    def no_duplicates(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in pairs:
            if key in out:
                raise CurrentStateError(f"duplicate JSON key in {label}: {key}")
            out[key] = value
        return out

    try:
        return json.loads(data.decode("utf-8-sig"), object_pairs_hook=no_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CurrentStateError(f"invalid JSON in {label}: {exc}") from exc


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CurrentStateError(message)


def get_path(obj: Any, *keys: str) -> Any:
    current = obj
    for key in keys:
        require(isinstance(current, dict) and key in current, f"missing field: {'.'.join(keys)}")
        current = current[key]
    return current


def _read_sources(root: Path) -> tuple[list[dict[str, Any]], dict[str, bytes]]:
    pins: list[dict[str, Any]] = []
    raw: dict[str, bytes] = {}
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for source_id, rel, role, ceiling in SOURCE_SPECS:
        require(source_id not in seen_ids, f"duplicate source id: {source_id}")
        require(rel not in seen_paths, f"duplicate source path: {rel}")
        require("\\" not in rel and not Path(rel).is_absolute() and ".." not in Path(rel).parts,
                f"non-canonical source path: {rel}")
        path = root / Path(rel)
        require(path.is_file(), f"missing source: {rel}")
        data = path.read_bytes()
        raw[source_id] = data
        pins.append(
            {
                "authority_ceiling": ceiling,
                "bytes": len(data),
                "id": source_id,
                "path": rel,
                "role": role,
                "sha256": sha256_bytes(data),
            }
        )
        seen_ids.add(source_id)
        seen_paths.add(rel)
    require(len(pins) == 27, f"source count is {len(pins)}, expected 27")
    return pins, raw


def _json_sources(raw: dict[str, bytes]) -> dict[str, Any]:
    json_ids = {
        source_id
        for source_id, rel, _role, _ceiling in SOURCE_SPECS
        if rel.lower().endswith(".json")
    }
    return {source_id: strict_json_bytes(raw[source_id], source_id) for source_id in json_ids}


def _extract_current_truth(raw: dict[str, bytes]) -> dict[str, Any]:
    j = _json_sources(raw)
    terminal = j["terminal_release_gate"]
    baseline = j["baseline_manifest_with_self_defect"]
    odr = j["odr60_option_a_execution_closure"]
    registry = j["m01_system_collision_registry_gate"]
    binding = j["m01_system_binding_readiness_gate"]
    query = j["m01_query_infrastructure_gate"]
    route = j["route_c_m01_negative_witness"]
    sim13_addendum = j["sim13_post_terminal_backend_addendum"]
    sim13_static = j["sim13_static_system_binding_candidate"]
    parent_dyn = j["parent_dynamics_engineering_gate"]
    dg12 = j["dg1_dg2_candidate_gate"]
    dg3 = j["dg3_candidate_gate"]
    dg4 = j["dg4_candidate_gate"]
    dg5 = j["dg5_candidate_gate"]
    v3 = j["digital_prototype_dynamics_entry_gate_v3"]
    v3_manifest = j["digital_prototype_dynamics_entry_manifest_v3"]
    prectrl = j["control_predevelopment_gate"]
    parent_ctrl = j["parent_control_engineering_gate"]
    joint = j["joint_dynamics_control_gate"]
    safe = j["historical_safe00_gate"]

    # Frozen terminal release remains a snapshot and remains closed.
    require(terminal["gate_a_pass"] is False, "terminal gate_a_pass unexpectedly true")
    require(terminal["next_stage_authorized"] is False, "terminal next stage unexpectedly true")
    require(terminal["release_credit"] is False, "terminal release credit unexpectedly true")
    tmg = {row["id"]: row for row in terminal["tmg"]}
    require(tmg["TMG-4"]["state"] == "HOLD", "TMG-4 no longer HOLD")
    require(tmg["TMG-6"]["state"] == "FAIL_15_OF_20", "frozen TMG-6 snapshot changed")

    # The baseline manifest defect is recorded, never repaired here.
    baseline_entry = next(
        (row for row in baseline["files"] if row.get("file") == "01_BASELINE_MANIFEST.json"),
        None,
    )
    require(baseline_entry is not None, "baseline self entry absent")
    baseline_actual = raw["baseline_manifest_with_self_defect"]
    baseline_actual_bytes = len(baseline_actual)
    baseline_actual_sha = sha256_bytes(baseline_actual)
    require(baseline_entry["bytes"] != baseline_actual_bytes, "baseline byte defect disappeared")
    require(baseline_entry["sha256"] != baseline_actual_sha, "baseline hash defect disappeared")
    require(
        baseline["self_reference_policy"]
        == "22_RELEASE_SHA256.csv excludes itself and this manifest to avoid self-reference",
        "baseline self-reference policy changed",
    )

    # Current M01 readiness: Option A and static frame rows are closed, execution is not.
    require(get_path(odr, "owner_authority", "option_a_selected") is True, "Option A not selected")
    require(get_path(odr, "owner_authority", "low_memory_override_authorized") is False,
            "low-memory override unexpectedly true")
    require(get_path(odr, "actual_closures", "execution_mount_full_precision_spelling_bound") is True,
            "execution mount spelling no longer bound")
    require(get_path(odr, "actual_closures", "accepted_urdf_subtree_collision_frame_rows") == 10,
            "accepted frame rows not 10")
    require(get_path(odr, "remaining_readiness", "three_stage_scene_instances_bound") == 0,
            "M01 stage instances no longer zero")
    require(get_path(odr, "remaining_readiness", "clearance_policy_rows_bound") == 0,
            "clearance rows no longer zero")
    require(get_path(odr, "remaining_readiness", "motion_certificates_bound") == 0,
            "motion certificates no longer zero")
    require(get_path(odr, "remaining_readiness", "pair_oracle_rows_executed") == 0,
            "pair oracle rows no longer zero")
    require(get_path(odr, "execution_record", "edges_certified") == 0, "edges no longer zero")
    require(odr["path_search_executed"] is False, "M01 path search unexpectedly executed")
    require(registry["pair_coverage"]["expected_pairs"] == 11175, "pair universe changed")
    require(registry["pair_coverage"]["status_counts"]["UNASSESSED_FAIL_CLOSED"] == 11166,
            "M01 unassessed-pair count changed")
    require(registry["pre_search_ready"] is False, "M01 registry unexpectedly pre-search ready")
    require(binding["authority"].startswith("METADATA_BINDING_READINESS_ONLY"),
            "M01 binding authority ceiling changed")
    require(query["path_search_executed"] is False and query["next_stage_authorized"] is False,
            "query infrastructure authority unexpectedly advanced")

    # Exact Route-C mandatory M01 negative witness.
    witness = route["witness"]
    collision = witness["collision"]
    require(witness["segment"] == "M01" and witness["fraction"] == 0.5,
            "Route-C negative witness identity changed")
    require(collision["raw_clearance_mm"] == -10.729480331980062,
            "Route-C raw penetration witness changed")
    require(collision["gated_clearance_mm"] == -17.313396996697108,
            "Route-C gated penetration witness changed")
    require(collision["raw_physical_penetration"] is True, "Route-C penetration no longer true")
    require(route["route_c_formal_pass"] is False and route["next_stage_authorized"] is False,
            "Route-C gate unexpectedly advanced")

    # Sim13 20/20 is append-only backend negative-control credit, not a full TMG-6 reissue.
    lineage = sim13_addendum["lineage"]
    backend = sim13_addendum["backend_subscope"]
    current_authority = sim13_addendum["current_authority"]
    require(lineage["historical_terminal_nc_score"] == "15/20", "Sim13 historical score changed")
    require(lineage["post_terminal_backend_nc_score"] == "20/20", "Sim13 backend score changed")
    require(lineage["historical_15_of_20_superseded"] is False, "Sim13 parent was superseded")
    require(lineage["full_tmg6_reissue_executed"] is False, "full TMG-6 unexpectedly reissued")
    require(backend["tmg6_backend_subscope"] == "PASS_20_OF_20", "backend subscope not 20/20")
    require("ABORT_ONLY" in backend["maximum_operational_state"], "Sim13 max state not ABORT_ONLY")
    require(current_authority["sim13_system_binding_gate_passed"] is False,
            "Sim13 system binding unexpectedly passed")
    require(current_authority["current_contact_grasp_authorized"] is False,
            "Sim13 contact/grasp unexpectedly authorized")
    require(sim13_static["candidate_static_gate_passed"] is True, "static Sim13 candidate lost")
    require(sim13_static["sim13_system_binding_gate_passed"] is False,
            "static candidate inflated to system binding pass")
    require(sim13_static["maximum_operational_state"] == "ABORT_ONLY",
            "static candidate max state changed")

    # Additive dynamics candidates are recorded without modifying the parent Gate.
    require(parent_dyn["summary"]["candidate_satisfied"] == 1, "parent dynamics numerator changed")
    require(parent_dyn["summary"]["total"] == 6, "parent dynamics denominator changed")
    require(parent_dyn["dynamics_engineering_complete"] is False, "parent dynamics unexpectedly complete")
    require(dg12["summary"] == {"failed": [], "passed": 15, "total": 15}, "DG1/DG2 score changed")
    require(dg12["next_stage_authorized"] is False and dg12["release_credit"] is False,
            "DG1/DG2 authority inflated")
    require(dg3["summary"] == {"failed": [], "passed": 30, "total": 30}, "DG3 score changed")
    require(dg3["parent_DG3_satisfied"] is False, "DG3 parent unexpectedly satisfied")
    require(dg4["criteria_passed"] == 15 and dg4["criteria_total"] == 15, "DG4 score changed")
    require(dg4["parent_DG4_satisfied"] is False and dg4["physical_contact_ready"] is False,
            "DG4 physical or parent authority inflated")
    require(dg5["summary"] == {"failed": [], "passed": 16, "total": 16}, "DG5 score changed")
    require(dg5["parent_DG5_satisfied"] is False, "DG5 parent unexpectedly satisfied")
    require(dg5["as_built_mass_properties"] is None, "DG5 as-built mass was zero-filled/invented")
    require(dg5["contact_uncertainty"] is None and dg5["actuator_uncertainty"] is None,
            "DG5 contact/actuator uncertainty was invented")
    require(v3["summary"] == {"failed": [], "passed": 19, "total": 19}, "V3 score changed")
    require(v3["dynamics_candidate_ledger"]["parent_dynamics_engineering_complete"] is False,
            "V3 parent dynamics unexpectedly complete")
    require(v3["next_stage_authorized"] is False and v3["release_credit"] is False,
            "V3 authority inflated")
    require(v3_manifest.get("schema") == "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_MANIFEST_V3",
            "V3 manifest schema changed")
    v3_manifest_text = raw["digital_prototype_dynamics_entry_manifest_v3"].decode("utf-8-sig")
    require("CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_MANIFEST_V3.json" not in v3_manifest_text,
            "V3 manifest unexpectedly self-references")
    require(v3_manifest.get("next_stage_authorized") is False
            and v3_manifest.get("release_credit") is False,
            "V3 manifest authority inflated")

    # Control and joint truth remains HOLD; historical SAFE PASS cannot be inherited.
    require(prectrl["summary"]["candidate_packaging_criteria_satisfied"] == 9,
            "control predevelopment numerator changed")
    require(prectrl["summary"]["total"] == 9, "control predevelopment denominator changed")
    require(prectrl["technical_predevelopment_complete"] is False,
            "control predevelopment unexpectedly technically complete")
    require(parent_ctrl["control_engineering_complete"] is False,
            "parent control unexpectedly complete")
    require(parent_ctrl["next_stage_authorized"] is False and parent_ctrl["release_credit"] is False,
            "parent control authority inflated")
    require(joint["required_condition_evaluation"]["pass_count"] == 4,
            "joint Gate numerator changed")
    require(joint["required_condition_evaluation"]["total"] == 13,
            "joint Gate denominator changed")
    require(joint["joint_system_ready"] is False and joint["next_stage_authorized"] is False,
            "joint Gate unexpectedly ready")
    require(safe["verdict"] == "PASS", "historical SAFE verdict changed")
    require(safe["review_status"] == "PENDING_REVIEW", "historical SAFE review status changed")
    require(safe["next_stage_authorized"] is False, "historical SAFE next stage unexpectedly true")

    # L06: eight drawings are prohibited for manufacturing; the two M3R drawings and
    # BOM retain 6061 labels while the current design selection is 7075-T651.
    drawing_text = raw["l06_drawing_set_index"].decode("utf-8-sig")
    drawing_rows = list(csv.DictReader(io.StringIO(drawing_text)))
    require(len(drawing_rows) == 8, f"drawing row count changed: {len(drawing_rows)}")
    require(all(row["manufacturing_use"] == "PROHIBITED" for row in drawing_rows),
            "one or more drawings no longer prohibit manufacturing")
    rows_by_id = {row["drawing_id"]: row for row in drawing_rows}
    require("AL6061-T6 CANDIDATE" in rows_by_id["D05_STAGE_A"]["material_specification"],
            "D05 6061 label missing")
    require("AL6061-T6 CANDIDATE" in rows_by_id["D06_STAGE_B"]["material_specification"],
            "D06 6061 label missing")
    require("PENDING_SIBLING_HASH" in rows_by_id["D05_STAGE_A"]["tolerance_specification"],
            "D05 sibling-hash witness missing")
    require("PENDING_SIBLING_HASH" in rows_by_id["D06_STAGE_B"]["tolerance_specification"],
            "D06 sibling-hash witness missing")
    require("PENDING_SIBLING_HASH" in rows_by_id["D08_ASSEMBLY_STACKUP"]["tolerance_specification"],
            "D08 sibling-hash witness missing")

    d05_text = raw["l06_d05_stage_a"].decode("utf-8-sig")
    d06_text = raw["l06_d06_stage_b"].decode("utf-8-sig")
    d08_text = raw["l06_d08_assembly_stackup"].decode("utf-8-sig")
    bom_text = raw["l06_design_bom"].decode("utf-8-sig")
    material_text = raw["current_design_material_selection"].decode("utf-8-sig")
    require("AL6061-T6 CANDIDATE" in d05_text and "AL6061-T6 CANDIDATE" in d06_text,
            "D05/D06 SVG 6061 witness missing")
    require(d05_text.count("PENDING_SIBLING_HASH") == 4, "D05 pending-hash count changed")
    require(d06_text.count("PENDING_SIBLING_HASH") == 4, "D06 pending-hash count changed")
    require(d08_text.count("PENDING_SIBLING_HASH") == 3, "D08 pending-hash count changed")
    require(bom_text.count("PENDING_SIBLING_HASH") == 32, "BOM pending-hash count changed")
    require("AL6061-T6 candidate per M3R_STAGE_A_PARAMETER_TABLE.yaml" in bom_text,
            "BOM Stage-A 6061 lineage missing")
    require("AL6061-T6 candidate per M3R_STAGE_B_PARAMETER_TABLE.yaml" in bom_text,
            "BOM Stage-B 6061 lineage missing")
    m3r_block_start = material_text.find("family_id: M3R_PRIMARY_STRUCTURE_STAGE_A_B")
    m3r_block_end = material_text.find("family_id: GENERAL_BRACKETS_CAMERA_BRACKET_LOAD_BRIDGE")
    require(0 <= m3r_block_start < m3r_block_end, "M3R material family block missing")
    m3r_block = material_text[m3r_block_start:m3r_block_end]
    require("material_id: PMAT-AL7075-T651-SHEET-PLATE" in m3r_block,
            "current M3R 7075-T651 selection missing")
    require("selection_status: DESIGN_APPROVED" in m3r_block,
            "current M3R design-selection status missing")

    return {
        "baseline_manifest_integrity_defect": {
            "actual_bytes": baseline_actual_bytes,
            "actual_sha256": baseline_actual_sha,
            "defect_confirmed": True,
            "internal_self_entry_bytes": baseline_entry["bytes"],
            "internal_self_entry_sha256": baseline_entry["sha256"],
            "policy_claim": baseline["self_reference_policy"],
            "repair_or_parent_mutation_performed": False,
        },
        "control_and_joint": {
            "control_engineering_complete": False,
            "control_predevelopment_candidate_packaging": "9_OF_9",
            "control_technical_predevelopment_complete": False,
            "historical_safe_gate": "PASS_PENDING_REVIEW_NEXT_STAGE_FALSE",
            "joint_gate": "4_OF_13",
            "joint_system_ready": False,
            "rl_or_vla_execution_authorized": False,
        },
        "dynamics": {
            "DG1_DG2": "15_OF_15_ADDITIVE_CANDIDATE",
            "DG3": "30_OF_30_ADDITIVE_CANDIDATE_PARENT_FALSE",
            "DG4": "15_OF_15_DESIGN_DIAGNOSTIC_PARENT_AND_PHYSICAL_FALSE",
            "DG5": "16_OF_16_DESIGN_SCREEN_PARENT_FALSE_AS_BUILT_CONTACT_ACTUATOR_NULL",
            "V3": "19_OF_19_ADDITIVE_CONVERGENCE",
            "parent_dynamics": "1_OF_6_HOLD_NOT_REISSUED",
        },
        "l06_drawing_bom_material_conflict": {
            "bom_pending_sibling_hash_occurrences": 32,
            "current_m3r_stage_a_b_design_material": "PMAT-AL7075-T651-SHEET-PLATE",
            "d05_d06_d08_pending_sibling_hash_occurrences": {"D05": 4, "D06": 4, "D08": 3},
            "d05_material_label": "AL6061-T6 CANDIDATE",
            "d06_material_label": "AL6061-T6 CANDIDATE",
            "drawing_count": 8,
            "manufacturing_use": "PROHIBITED_8_OF_8",
            "manufacturing_or_procurement_release": False,
            "owner_adjudication_required": True,
        },
        "mechanical_m01_route_c": {
            "M01_clearance_policy": "0_OF_11166",
            "M01_continuous_edge_certificates": 0,
            "M01_motion_certificates": "0_OF_150",
            "M01_pair_oracle": "0_OF_11166",
            "M01_path_search_executed": False,
            "M01_stage_instances": "0_OF_3",
            "accepted_arm_frame_ledger": "10_OF_10",
            "execution_mount_full_precision_bound": True,
            "low_memory_override_authorized": False,
            "option_a_selected": True,
            "route_c_m01_fraction": 0.5,
            "route_c_m01_gated_clearance_mm": -17.313396996697108,
            "route_c_m01_raw_clearance_mm": -10.729480331980062,
            "route_c_formal_pass": False,
            "terminal_gate_a_pass": False,
        },
        "sim13": {
            "backend_negative_control_subscope": "20_OF_20_PASS",
            "current_contact_grasp_authorized": False,
            "full_tmg6_reissued": False,
            "historical_terminal_snapshot": "15_OF_20",
            "maximum_operational_state": "ABORT_ONLY",
            "sim13_system_binding_gate_passed": False,
            "static_research_candidate_passed": True,
        },
    }


def _pin(rel: str, data: bytes) -> dict[str, Any]:
    return {"bytes": len(data), "path": rel, "sha256": sha256_bytes(data)}


def build_documents(root: Path | None = None, package_dir: Path | None = None) -> dict[str, bytes]:
    root = (root or workspace_root()).resolve()
    package_dir = (package_dir or (root / PACKAGE_REL)).resolve()
    require(package_dir.is_dir(), f"package directory missing: {package_dir}")
    source_pins, raw = _read_sources(root)
    current_truth = _extract_current_truth(raw)

    input_manifest = {
        "authority": "APPEND_ONLY_CURRENT_STATE_SOURCE_FREEZE__NO_PARENT_MUTATION",
        "decision_rule": "Authority > Evidence > Independent reproduction > Agent opinion",
        "generated_utc": "DETERMINISTIC_REISSUE_NO_WALLCLOCK",
        "layer": 1,
        "next_stage_authorized": False,
        "release_credit": False,
        "schema": "R2_CURRENT_STATE_INPUT_MANIFEST_V2",
        "source_count": len(source_pins),
        "source_pins": source_pins,
        "source_read_policy": "ONE_IMMUTABLE_BYTE_READ_PER_SOURCE__STRICT_JSON_DUPLICATE_KEYS_REJECTED",
    }
    input_bytes = canonical_json(input_manifest)

    checks = {
        "R2CS-01_exactly_27_current_sources_bound": len(source_pins) == 27,
        "R2CS-02_source_ids_and_paths_unique": len({p["id"] for p in source_pins}) == 27
        and len({p["path"] for p in source_pins}) == 27,
        "R2CS-03_terminal_release_gate_remains_false": current_truth["mechanical_m01_route_c"]["terminal_gate_a_pass"] is False,
        "R2CS-04_baseline_manifest_self_fingerprint_defect_exactly_recorded": current_truth["baseline_manifest_integrity_defect"]["defect_confirmed"],
        "R2CS-05_baseline_parent_not_repaired_or_mutated": current_truth["baseline_manifest_integrity_defect"]["repair_or_parent_mutation_performed"] is False,
        "R2CS-06_option_a_and_mount_frame_field_limited_closures_bound": current_truth["mechanical_m01_route_c"]["option_a_selected"] is True
        and current_truth["mechanical_m01_route_c"]["accepted_arm_frame_ledger"] == "10_OF_10",
        "R2CS-07_m01_clearance_motion_oracle_edge_and_search_remain_zero": current_truth["mechanical_m01_route_c"]["M01_clearance_policy"] == "0_OF_11166"
        and current_truth["mechanical_m01_route_c"]["M01_motion_certificates"] == "0_OF_150"
        and current_truth["mechanical_m01_route_c"]["M01_pair_oracle"] == "0_OF_11166"
        and current_truth["mechanical_m01_route_c"]["M01_continuous_edge_certificates"] == 0
        and current_truth["mechanical_m01_route_c"]["M01_path_search_executed"] is False,
        "R2CS-08_route_c_m01_negative_witness_preserved": current_truth["mechanical_m01_route_c"]["route_c_m01_raw_clearance_mm"] < 0.0
        and current_truth["mechanical_m01_route_c"]["route_c_m01_gated_clearance_mm"] < 0.0,
        "R2CS-09_route_c_formal_pass_remains_false": current_truth["mechanical_m01_route_c"]["route_c_formal_pass"] is False,
        "R2CS-10_sim13_backend_20_of_20_is_subscope_only": current_truth["sim13"]["backend_negative_control_subscope"] == "20_OF_20_PASS"
        and current_truth["sim13"]["full_tmg6_reissued"] is False,
        "R2CS-11_sim13_historical_15_of_20_not_superseded": current_truth["sim13"]["historical_terminal_snapshot"] == "15_OF_20",
        "R2CS-12_sim13_maximum_operational_state_abort_only": current_truth["sim13"]["maximum_operational_state"] == "ABORT_ONLY",
        "R2CS-13_sim13_system_and_contact_authority_false": current_truth["sim13"]["sim13_system_binding_gate_passed"] is False
        and current_truth["sim13"]["current_contact_grasp_authorized"] is False,
        "R2CS-14_parent_dynamics_remains_1_of_6_hold": current_truth["dynamics"]["parent_dynamics"] == "1_OF_6_HOLD_NOT_REISSUED",
        "R2CS-15_dg1_dg2_candidate_exact": current_truth["dynamics"]["DG1_DG2"] == "15_OF_15_ADDITIVE_CANDIDATE",
        "R2CS-16_dg3_candidate_exact_without_parent_credit": current_truth["dynamics"]["DG3"] == "30_OF_30_ADDITIVE_CANDIDATE_PARENT_FALSE",
        "R2CS-17_dg4_candidate_exact_without_physical_credit": current_truth["dynamics"]["DG4"] == "15_OF_15_DESIGN_DIAGNOSTIC_PARENT_AND_PHYSICAL_FALSE",
        "R2CS-18_dg5_candidate_exact_with_nulls": current_truth["dynamics"]["DG5"] == "16_OF_16_DESIGN_SCREEN_PARENT_FALSE_AS_BUILT_CONTACT_ACTUATOR_NULL",
        "R2CS-19_v3_additive_convergence_exact": current_truth["dynamics"]["V3"] == "19_OF_19_ADDITIVE_CONVERGENCE",
        "R2CS-20_control_predevelopment_only": current_truth["control_and_joint"]["control_predevelopment_candidate_packaging"] == "9_OF_9"
        and current_truth["control_and_joint"]["control_technical_predevelopment_complete"] is False,
        "R2CS-21_parent_control_remains_hold": current_truth["control_and_joint"]["control_engineering_complete"] is False,
        "R2CS-22_joint_gate_remains_4_of_13_hold": current_truth["control_and_joint"]["joint_gate"] == "4_OF_13"
        and current_truth["control_and_joint"]["joint_system_ready"] is False,
        "R2CS-23_historical_safe_pass_not_promoted": current_truth["control_and_joint"]["historical_safe_gate"] == "PASS_PENDING_REVIEW_NEXT_STAGE_FALSE",
        "R2CS-24_l06_all_eight_drawings_manufacturing_prohibited": current_truth["l06_drawing_bom_material_conflict"]["manufacturing_use"] == "PROHIBITED_8_OF_8",
        "R2CS-25_l06_6061_vs_7075_conflict_explicit": current_truth["l06_drawing_bom_material_conflict"]["d05_material_label"] == "AL6061-T6 CANDIDATE"
        and current_truth["l06_drawing_bom_material_conflict"]["current_m3r_stage_a_b_design_material"] == "PMAT-AL7075-T651-SHEET-PLATE",
        "R2CS-26_l06_sibling_hash_debt_exactly_counted": current_truth["l06_drawing_bom_material_conflict"]["d05_d06_d08_pending_sibling_hash_occurrences"] == {"D05": 4, "D06": 4, "D08": 3}
        and current_truth["l06_drawing_bom_material_conflict"]["bom_pending_sibling_hash_occurrences"] == 32,
        "R2CS-27_no_rl_vla_nonabort_or_release_authority": current_truth["control_and_joint"]["rl_or_vla_execution_authorized"] is False,
        "R2CS-28_all_generated_authority_flags_fail_closed": True,
    }
    require(all(checks.values()), "one or more current-state checks failed")

    gate = {
        "artifact_package_generated": True,
        "authority": "APPEND_ONLY_CURRENT_STATE_REISSUE_INTEGRITY_ONLY__NO_ENGINEERING_GATE_SUPERSESSION",
        "checks": checks,
        "current_truth": current_truth,
        "generated_utc": "DETERMINISTIC_REISSUE_NO_WALLCLOCK",
        "input_manifest": _pin(str(PACKAGE_REL / INPUT_NAME).replace("\\", "/"), input_bytes),
        "layer": 2,
        "maximum_claim": "HASH_BOUND_CURRENT_STATE_LEDGER_WITH_EXACT_NEGATIVE_AND_CANDIDATE_BOUNDARIES",
        "mechanical_release_ready": False,
        "next_stage_authorized": False,
        "parent_artifacts_modified": False,
        "reissue_integrity_pass": True,
        "release_credit": False,
        "review_status": "PENDING_OWNER_REVIEW",
        "schema": "R2_CURRENT_STATE_GATE_V2",
        "summary": {"failed": [], "passed": len(checks), "total": len(checks)},
        "technical_verdict": "PASS_APPEND_ONLY_CURRENT_STATE_REISSUE_INTEGRITY__MECHANICAL_DYNAMICS_CONTROL_SIM13_AND_RELEASE_HOLD",
    }
    gate_bytes = canonical_json(gate)

    local_names = (
        "README.md",
        "build_current_state_reissue.py",
        "validate_current_state_reissue.py",
        "tests/test_current_state_reissue.py",
    )
    local_pins: list[dict[str, Any]] = []
    for name in local_names:
        path = package_dir / Path(name)
        require(path.is_file(), f"missing local package source: {name}")
        local_pins.append(_pin(str(PACKAGE_REL / name).replace("\\", "/"), path.read_bytes()))
    local_pins.extend(
        [
            _pin(str(PACKAGE_REL / INPUT_NAME).replace("\\", "/"), input_bytes),
            _pin(str(PACKAGE_REL / GATE_NAME).replace("\\", "/"), gate_bytes),
        ]
    )
    package_manifest = {
        "authority": "PACKAGE_INTEGRITY_ONLY__NO_PARENT_OR_RELEASE_AUTHORITY",
        "entry_count": len(local_pins),
        "generated_utc": "DETERMINISTIC_REISSUE_NO_WALLCLOCK",
        "layer": 3,
        "layer_order": [INPUT_NAME, GATE_NAME, PACKAGE_NAME],
        "next_stage_authorized": False,
        "package_entries": local_pins,
        "release_credit": False,
        "schema": "R2_CURRENT_STATE_PACKAGE_MANIFEST_V2",
        "self_reference_policy": f"{PACKAGE_NAME} EXCLUDES_ITSELF",
    }
    package_bytes = canonical_json(package_manifest)
    return {INPUT_NAME: input_bytes, GATE_NAME: gate_bytes, PACKAGE_NAME: package_bytes}


def write_documents(documents: dict[str, bytes], package_dir: Path) -> None:
    for name in (INPUT_NAME, GATE_NAME, PACKAGE_NAME):
        (package_dir / name).write_bytes(documents[name])


def check_documents(documents: dict[str, bytes], package_dir: Path) -> None:
    for name, expected in documents.items():
        path = package_dir / name
        require(path.is_file(), f"missing generated artifact: {name}")
        actual = path.read_bytes()
        require(actual == expected, f"stale or tampered generated artifact: {name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="write the three deterministic layers")
    mode.add_argument("--check", action="store_true", help="check the three layers byte-for-byte")
    args = parser.parse_args()
    root = workspace_root()
    package_dir = root / PACKAGE_REL
    documents = build_documents(root, package_dir)
    if args.write:
        write_documents(documents, package_dir)
    else:
        check_documents(documents, package_dir)
    print(
        json.dumps(
            {
                "gate_sha256": sha256_bytes(documents[GATE_NAME]),
                "input_manifest_sha256": sha256_bytes(documents[INPUT_NAME]),
                "mode": "write" if args.write else "check",
                "package_manifest_sha256": sha256_bytes(documents[PACKAGE_NAME]),
                "source_count": 27,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
