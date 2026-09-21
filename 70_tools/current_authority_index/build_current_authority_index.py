"""Generate a navigation-only, hash-bound current authority index."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


SOURCES = [
    ("project_map", "PROJECT_MAP.md", "NAVIGATION", "CURRENT", "project"),
    ("competition_gate", "10_research/competition_convergence/competition_gate_check.json", "MACHINE_GATE", "CURRENT", "competition"),
    ("mechanical_release_gate", "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/00_RELEASE_GATE.json", "MACHINE_GATE", "CURRENT_SNAPSHOT", "mechanical"),
    ("mechanical_baseline_manifest", "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/01_BASELINE_MANIFEST.json", "BASELINE_MANIFEST", "CURRENT", "mechanical"),
    ("mechanical_release_sha", "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/22_RELEASE_SHA256.csv", "HASH_MANIFEST", "CURRENT", "mechanical"),
    ("product_structure", "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/02_PRODUCT_STRUCTURE.yaml", "ENGINEERING_INTERFACE", "CURRENT", "mechanical"),
    ("accepted_b601_ref", "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/05_ACCEPTED_B601_URDF_REF.yaml", "ENGINEERING_INTERFACE", "CURRENT", "mechanical"),
    ("physical_dynamics_bridge", "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/06_PHYSICAL_DYNAMICS_BRIDGE.yaml", "ENGINEERING_INTERFACE", "CURRENT", "mechanical"),
    ("system_mass_properties", "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/07_SYSTEM_MASS_PROPERTIES.yaml", "ENGINEERING_INTERFACE", "CURRENT", "mechanical"),
    ("unified_r2_interface", "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/15_UNIFIED_R2_SYSTEM_INTERFACE.yaml", "ENGINEERING_INTERFACE", "CURRENT", "system"),
    ("mech_embodied_handoff", "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/17_MECH_TO_EMBODIED_HANDOFF_GATE.json", "MACHINE_GATE", "CURRENT_SNAPSHOT", "mechanical"),
    ("sim13_preexecution", "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/18_SIM13_PREEXECUTION_GATE.json", "MACHINE_GATE", "CURRENT_SNAPSHOT", "embodied"),
    ("qualification_holds", "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/19_OPEN_QUALIFICATION_HOLDS.csv", "HOLD_REGISTER", "CURRENT", "mechanical"),
    ("route_c_frontier", "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/ROUTE_C_TERMINAL_CURRENT_FRONTIER_V3.json", "FRONTIER_SNAPSHOT", "CURRENT", "mechanical"),
    ("odr60_request", "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR-60_DECISION_REQUEST.json", "OWNER_DECISION_REQUEST", "CURRENT_PENDING_DECISION", "authority"),
    ("odr60_manifest", "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR-60_SHA256.csv", "HASH_MANIFEST", "CURRENT", "authority"),
    ("odr60_system_binding", "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_SYSTEM_BINDING_CONTRACT_V1/SYSTEM_BINDING_READINESS_GATE_V1.json", "MACHINE_GATE", "CURRENT_CANDIDATE", "mechanical"),
    ("odr60_binding_intake", "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_BINDING_INTAKE_V1/BINDING_INTAKE_GATE_V1.json", "MACHINE_GATE", "CURRENT_CANDIDATE", "mechanical"),
    ("odr60_collision_authority", "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/ODR60_OPTION_A_COLLISION_AUTHORITY_GATE_V1.json", "MACHINE_GATE", "CURRENT_CANDIDATE", "mechanical"),
    ("odr60_preflight", "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_PREFLIGHT_V1/ODR60_OPTION_A_PREFLIGHT_GATE_V1.json", "MACHINE_GATE", "CURRENT_CANDIDATE_STRICT_JSON_HOLD", "mechanical"),
    ("odr60_option_a_execution_closure", "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/results/ODR60_OPTION_A_EXECUTION_CLOSURE_GATE_V1.json", "MACHINE_GATE", "CURRENT_CANDIDATE_HOLD", "mechanical"),
    ("sim10_gate", "30_simulation/sim_10_mission_feasibility/results/sim_10_gate_check.json", "MACHINE_GATE", "CURRENT", "dynamics"),
    ("sim11_gate", "30_simulation/sim_11_coupled_dynamics/results/sim_11_gate_check.json", "MACHINE_GATE", "CURRENT", "dynamics"),
    ("sim12_gate", "30_simulation/sim_12_strategy_feasibility/results/sim_12_gate_check.json", "MACHINE_GATE", "CURRENT", "strategy"),
    ("e15_gate", "30_simulation/e15_ancf_certification/results/gate_summary.json", "MACHINE_GATE", "KEEP_HISTORICAL_NEGATIVE", "dynamics"),
    ("e22_gate", "30_simulation/e22_r2_full_flex_coupled_diagnostics/results/E22_R2_FULL_FLEX_COUPLED_GATE_V1.json", "MACHINE_GATE", "KEEP_HISTORICAL_NEGATIVE", "dynamics"),
    ("e23_gate", "30_simulation/e23_r2_full_flex_coupled_recert/results/E23_R2_FULL_FLEX_COUPLED_GATE_V1.json", "MACHINE_GATE", "CURRENT_PROVISIONAL", "dynamics"),
    ("r2_dynamics_engineering", "30_simulation/r2_dynamics_engineering_closure/results/R2_DYNAMICS_ENGINEERING_GATE_V1.json", "MACHINE_GATE", "CURRENT_CANDIDATE_HOLD", "dynamics"),
    ("r2_8dof_constrained_dynamics", "30_simulation/r2_dynamics_engineering_closure/results/R2_8DOF_CONSTRAINED_DYNAMICS_GATE_V1.json", "MACHINE_GATE", "CURRENT_DIAGNOSTIC_HOLD", "dynamics"),
    ("pb_g0", "30_simulation/dynamics_control_prebind_r1/10_verification/PB_G0_GATE.json", "MACHINE_GATE", "CURRENT_DIAGNOSTIC", "control"),
    ("pb_g1", "30_simulation/dynamics_control_prebind_r1/10_verification/PB_G1_GATE.json", "MACHINE_GATE", "CURRENT_DIAGNOSTIC", "control"),
    ("ctrl01_gate", "30_simulation/control_01_end_effector_tracking/results/control_01_gate_check.json", "MACHINE_GATE", "KEEP_CURRENT_NEGATIVE", "control"),
    ("ctrl02_gate", "30_simulation/control_02_base_attitude/results/control_02_gate_check.json", "MACHINE_GATE", "CURRENT_PROVISIONAL", "control"),
    ("safe00_gate", "30_simulation/safety_00_runtime_gate/results/safety_00_gate_check.json", "MACHINE_GATE", "CURRENT_PENDING_REVIEW", "safety"),
    ("sim13_20_of_20", "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/results/SIM13_20_OF_20_GATE_V1.json", "MACHINE_GATE", "CURRENT_FAIL_CLOSED_ADDENDUM", "embodied"),
    ("sim13_post_terminal_addendum", "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/loop_b/sim13_post_terminal_handoff_addendum_v1/SIM13_POST_TERMINAL_HANDOFF_ADDENDUM_GATE_V1.json", "MACHINE_GATE", "CURRENT_APPEND_ONLY", "embodied"),
    ("ctrl_r2_predevelopment", "30_simulation/control_r2_integrated_candidate/results/CTRL_R2_PREDEVELOPMENT_GATE_V1.json", "MACHINE_GATE", "CURRENT_CANDIDATE", "control"),
    ("r2_control_engineering", "30_simulation/r2_control_engineering_closure/results/R2_CONTROL_ENGINEERING_GATE_V1.json", "MACHINE_GATE", "CURRENT_CANDIDATE_HOLD", "control"),
    ("r2_dynamics_control_system", "30_simulation/r2_dynamics_control_system_closure/results/R2_DYNAMICS_CONTROL_SYSTEM_GATE_V1.json", "MACHINE_GATE", "CURRENT_CANDIDATE_HOLD", "system"),
    ("current_frontier_odr60_ctrl", "30_simulation/control_r2_integrated_candidate/results/CURRENT_FRONTIER_ODR60_CTRL_V1.json", "FRONTIER_SNAPSHOT", "CURRENT_CANDIDATE", "system"),
    ("literature_manifest", "50_literature/references/manifest.yaml", "LITERATURE_MANIFEST", "CURRENT", "literature"),
]

ACTIVE_WORK = [
    ("AW-01", "ODR-60 system binding and M01 admission", "mechanical", "OPTION_A_RECORDED_STATIC_PREFLIGHT_HOLD_NO_SEARCH", "odr60_option_a_execution_closure"),
    ("AW-02", "CTRL R2 engineering closure", "control", "TASK_SPACE_UNIT_METRIC_UNBOUND_CONTROL_HOLD", "r2_control_engineering"),
    ("AW-04", "R2 constrained dynamics engineering closure", "dynamics", "DG1_UNIT_METRIC_DG2_INDEPENDENT_CONSERVATION_HOLD", "r2_dynamics_engineering"),
    ("AW-05", "R2 dynamics-control system join", "system", "JOINT_SYSTEM_HOLD_NO_PATH_NO_RELEASE", "r2_dynamics_control_system"),
    ("AW-03", "Current authority index and retention audit", "governance", "NAVIGATION_ONLY_NO_DELETE", "project_map"),
]

HOLDS = [
    ("H-01", "MECHANICAL_RELEASE_FALSE", "mechanical_release_gate", "blocks mechanical freeze"),
    ("H-02", "ODR60_OPTION_A_RECORDED_BUT_STATIC_PREFLIGHT_AND_RUNTIME_ADMISSION_FALSE", "odr60_option_a_execution_closure", "blocks geometry/pair/edge/path execution"),
    ("H-03", "M01_SCENE_CLEARANCE_MOTION_CERTIFICATE_PAIR_ORACLE_INCOMPLETE", "odr60_binding_intake", "blocks path admission"),
    ("H-04", "ODR60_PREFLIGHT_DUPLICATE_JSON_KEY_LEGACY_V1_RETAINED", "odr60_preflight", "legacy negative retained; strict V2 is consumed by current execution closure"),
    ("H-05", "CTRL01_REPEAT", "ctrl01_gate", "negative control result retained"),
    ("H-06", "CTRL01_REORG04_CONFIG_HASH_DRIFT", "ctrl_r2_predevelopment", "blocks exact legacy replay claim"),
    ("H-07", "CTRL02_HARDWARE_ACTUATOR_DYNAMICS_NOT_EVALUATED", "ctrl02_gate", "provisional scope only"),
    ("H-08", "SAFE00_PENDING_REVIEW_NEXT_STAGE_FALSE", "safe00_gate", "interface only"),
    ("H-09", "E15_REPEAT_ANCF_CERTIFICATION", "e15_gate", "legacy negative retained"),
    ("H-10", "E22_HOLD_16_OF_18", "e22_gate", "historical negative retained"),
    ("H-11", "E23_DECLARED_PROVISIONAL_PHYSICS", "e23_gate", "no mission release inheritance"),
    ("H-12", "SIM13_20_OF_20_IS_NEGATIVE_CONTROL_BACKEND_CREDIT_ONLY", "sim13_20_of_20", "not non-ABORT capture credit"),
    ("H-13", "R2_DYNAMICS_DG1_UNIT_METRIC_DG2_INDEPENDENT_CONSERVATION_HOLD", "r2_dynamics_engineering", "blocks dynamics engineering pass"),
    ("H-14", "R2_CONTROL_TASK_SPACE_UNIT_METRIC_UNBOUND", "r2_control_engineering", "blocks tracking and control engineering credit"),
    ("H-15", "R2_DYNAMICS_CONTROL_SYSTEM_NOT_READY", "r2_dynamics_control_system", "blocks physics-gated embodied-intelligence progression"),
]

SUPERSEDED = [
    ("S-01", "30_simulation/e22_r2_full_flex_coupled_diagnostics/results/E22_R2_FULL_FLEX_COUPLED_GATE_V1.json", "30_simulation/e23_r2_full_flex_coupled_recert/results/E23_R2_FULL_FLEX_COUPLED_GATE_V1.json", "KEEP_HISTORICAL_NEGATIVE"),
    ("S-02", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/round3_rom_v2/R2_FIVE_MODE_ROM_V2.json", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/round4_hf_rom_v3/R2_SEVEN_MODE_ROM_V3.json", "KEEP_HISTORICAL_LINEAGE"),
    ("S-03", "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/00_RELEASE_GATE.json#sim13_15_of_20_snapshot", "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/loop_b/sim13_post_terminal_handoff_addendum_v1/SIM13_POST_TERMINAL_HANDOFF_ADDENDUM_GATE_V1.json", "KEEP_APPEND_ONLY_BOTH"),
]

RETIREMENT = [
    ("R-01", "01_project/competition/archive/ROOT_HISTORY_20260729_20260810.md", "PRESERVED_HISTORICAL_NAVIGATION", "PROJECT_CURRENT_STATUS.md consolidated here under 2026-09-06 root cleanup; historical scope only"),
    ("R-02", "01_project/current/archive/PROJECT_MODEL_TRUTH_HIERARCHY_20260808.yaml", "ARCHIVED_HISTORICAL_TRUTH_MAP", "Original truth-map bytes relocated under 2026-09-06 root cleanup; not current authority"),
    ("R-03", "01_project/competition/archive/ROOT_HISTORY_20260729_20260810.md", "PRESERVED_HISTORICAL_NAVIGATION", "MECHANICAL_START_HERE.md consolidated here under 2026-09-06 root cleanup; historical scope only"),
    ("R-04", "__pycache__/", "CACHE_CANDIDATE_NOT_APPROVED", "directory-level review required"),
    ("R-05", ".pytest_cache/", "CACHE_CANDIDATE_NOT_APPROVED", "directory-level review required"),
    ("R-06", ".ruff_cache/", "CACHE_CANDIDATE_NOT_APPROVED", "directory-level review required"),
    ("R-07", "$out/", "UNKNOWN_NEEDS_OWNER", "contents and references not audited"),
]

# A row may be added here only after all five evidence columns are independently
# demonstrated.  The current audit has no such row; a header-only register is an
# intentional fail-closed result, not an omitted search result.
DELETE_CANDIDATES: list[tuple[str, str, str, bool, bool, bool, bool, bool, bool, str]] = []
DELETE_FIELDS = [
    "id",
    "path",
    "sha256",
    "byte_identical_duplicate",
    "no_current_reference",
    "current_authority_copy_exists",
    "cold_backup_restore_verified",
    "not_protected_evidence",
    "eligible_for_owner_review",
    "action",
]


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"DUPLICATE_JSON_KEY:{key}")
        out[key] = value
    return out


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def strict_json(path: Path) -> tuple[str, dict[str, Any] | None, str | None]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicates)
        return "PASS", value, None
    except Exception as exc:  # evidence audit must record, not hide, parser failures
        return "HOLD", None, str(exc)


def extract_gate(value: dict[str, Any] | None) -> tuple[str, str, Any, Any]:
    if value is None:
        return "", "", None, None
    for key in ("verdict", "technical_verdict", "authority_disposition", "state"):
        if key in value:
            return key, str(value[key]), value.get("next_stage_authorized"), value.get("release_credit")
    return "", "NO_TOP_LEVEL_VERDICT_FIELD", value.get("next_stage_authorized"), value.get("release_credit")


def render_strict_bool(value: Any) -> tuple[str, str]:
    if value is None:
        return "", "NOT_PRESENT"
    if type(value) is bool:
        return str(value).lower(), "PASS"
    return "", f"HOLD_NON_BOOLEAN:{type(value).__name__}"


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def build(repo: Path) -> dict[str, Any]:
    out = repo / "01_project" / "current"
    out.mkdir(parents=True, exist_ok=True)
    records = []
    gates = []
    for source_id, rel, kind, lifecycle, domain in SOURCES:
        path = repo / rel
        if not path.is_file():
            raise FileNotFoundError(rel)
        record = {
            "id": source_id,
            "path": rel,
            "bytes": path.stat().st_size,
            "sha256": sha(path),
            "authority_kind": kind,
            "lifecycle": lifecycle,
            "domain": domain,
            "consumer": "CURRENT_AUTHORITY_INDEX_NAVIGATION_ONLY",
            "configuration_management_state": "NOT_EVALUATED_CURRENT_WORKTREE",
        }
        records.append(record)
        if path.suffix.lower() == ".json" and kind in {"MACHINE_GATE", "OWNER_DECISION_REQUEST", "FRONTIER_SNAPSHOT"}:
            parse_status, value, error = strict_json(path)
            verdict_field, verdict, next_stage, release = extract_gate(value)
            next_stage_text, next_stage_type = render_strict_bool(next_stage)
            release_text, release_type = render_strict_bool(release)
            gates.append({
                "id": source_id,
                "path": rel,
                "sha256": record["sha256"],
                "strict_json": parse_status,
                "parse_error": error or "",
                "verdict_field": verdict_field,
                "source_verdict": verdict,
                "next_stage_authorized": next_stage_text,
                "next_stage_type_check": next_stage_type,
                "release_credit": release_text,
                "release_credit_type_check": release_type,
                "navigation_does_not_override_source": "true",
            })

    header = (
        "status: NAVIGATION_ONLY\n"
        "authority: NONE\n"
        "gate_authority: false\n"
        "canonical_values_copied: false\n"
        "rule: conflicts resolve at linked machine Gate/config/authorization source\n"
    )
    (out / "README_CURRENT.md").write_text(
        "# 当前权威来源导航\n\n"
        + "```text\n" + header + "```\n\n"
        + "本目录只合并入口、哈希和来源关系；不复制 CAD、URDF、配置、结果或 Gate。\n"
        + "总路径导航见 `../../PROJECT_MAP.md`。任何冲突以被链接的机器 Gate、冻结配置、接口或 Owner 记录为准。\n\n"
        + "当前机械执行边界：ODR-60 Option A 已由明确执行块首行记录；静态预检、运行内存、pair/edge/path/release 仍 false。\n"
        + "当前动力学边界：R2 8DOF KKT 组件诊断已建立，DG1 单位度量与 DG2 独立全状态守恒仍 HOLD。\n"
        + "当前控制边界：任务空间特征长度/权重矩阵未冻结，tracking、collision-aware、non-ABORT 与 release 均未授权。\n"
        + "当前系统边界：联合 Gate 为 HOLD，未执行 M01 路径搜索，未进入 Physics-Gated Embodied Intelligence。\n"
        + "本轮未删除、移动或归档任何文件；DELETE_CANDIDATES_V1.csv 当前为 0 个合格项。\n",
        encoding="utf-8", newline="\n"
    )

    authority_lines = [
        "schema: PROJECT_CURRENT_AUTHORITY_V1",
        "status: NAVIGATION_ONLY",
        "authority: NONE",
        "gate_authority: false",
        "canonical_values_copied: false",
        "sources:",
    ]
    for item in records:
        authority_lines.extend([
            f"  - id: {item['id']}",
            f"    path: {item['path']}",
            f"    bytes: {item['bytes']}",
            f"    sha256: {item['sha256']}",
            f"    authority_kind: {item['authority_kind']}",
            f"    lifecycle: {item['lifecycle']}",
            f"    domain: {item['domain']}",
            "    configuration_management_state: NOT_EVALUATED_CURRENT_WORKTREE",
        ])
    (out / "PROJECT_CURRENT_AUTHORITY_V1.yaml").write_text("\n".join(authority_lines) + "\n", encoding="utf-8", newline="\n")

    write_csv(out / "CURRENT_GATE_MATRIX_V1.csv", list(gates[0]), gates)
    active_rows = [dict(zip(["id", "work", "domain", "status", "source_id"], row)) for row in ACTIVE_WORK]
    write_csv(out / "ACTIVE_WORK_REGISTER_V1.csv", list(active_rows[0]), active_rows)
    hold_rows = [dict(zip(["id", "hold_or_negative", "source_id", "effect"], row)) for row in HOLDS]
    write_csv(out / "HOLD_AND_NEGATIVE_RESULTS_V1.csv", list(hold_rows[0]), hold_rows)

    pointers = [
        "schema: CURRENT_RELEASE_POINTERS_V1",
        "status: NAVIGATION_ONLY",
        "mechanical: 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/00_RELEASE_GATE.json",
        "mechanical_owner_decision: 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR-60_DECISION_REQUEST.json",
        "mechanical_odr60_execution_closure: 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/results/ODR60_OPTION_A_EXECUTION_CLOSURE_GATE_V1.json",
        "dynamics: 30_simulation/e23_r2_full_flex_coupled_recert/results/E23_R2_FULL_FLEX_COUPLED_GATE_V1.json",
        "dynamics_r2_engineering: 30_simulation/r2_dynamics_engineering_closure/results/R2_DYNAMICS_ENGINEERING_GATE_V1.json",
        "dynamics_r2_constrained: 30_simulation/r2_dynamics_engineering_closure/results/R2_8DOF_CONSTRAINED_DYNAMICS_GATE_V1.json",
        "control: 30_simulation/control_r2_integrated_candidate/results/CTRL_R2_PREDEVELOPMENT_GATE_V1.json",
        "control_r2_engineering: 30_simulation/r2_control_engineering_closure/results/R2_CONTROL_ENGINEERING_GATE_V1.json",
        "system_r2_dynamics_control_closure: 30_simulation/r2_dynamics_control_system_closure/results/R2_DYNAMICS_CONTROL_SYSTEM_GATE_V1.json",
        "safety: 30_simulation/safety_00_runtime_gate/results/safety_00_gate_check.json",
        "embodied_fail_closed: 30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/results/SIM13_20_OF_20_GATE_V1.json",
        "competition: 10_research/competition_convergence/competition_gate_check.json",
        "literature: 50_literature/references/manifest.yaml",
        "release_credit: false",
    ]
    (out / "CURRENT_RELEASE_POINTERS_V1.yaml").write_text("\n".join(pointers) + "\n", encoding="utf-8", newline="\n")

    superseded_rows = [dict(zip(["id", "historical_path", "current_path", "retention"], row)) for row in SUPERSEDED]
    write_csv(out / "SUPERSEDED_ASSET_REGISTER_V1.csv", list(superseded_rows[0]), superseded_rows)
    retirement_rows = [dict(zip(["id", "path", "classification", "basis"], row)) for row in RETIREMENT]
    write_csv(out / "RETIREMENT_CANDIDATES_V1.csv", list(retirement_rows[0]), retirement_rows)
    delete_rows = [dict(zip(DELETE_FIELDS, row)) for row in DELETE_CANDIDATES]
    write_csv(out / "DELETE_CANDIDATES_V1.csv", DELETE_FIELDS, delete_rows)

    nodes = [{"id": item["id"], "path": item["path"], "sha256": item["sha256"], "authority_kind": item["authority_kind"]} for item in records]
    edges = [
        {"from": "odr60_request", "to": "mechanical_release_gate", "relation": "MUST_CLOSE_BEFORE_REISSUE"},
        {"from": "odr60_system_binding", "to": "odr60_request", "relation": "CANDIDATE_REQUIRES_OWNER_SELECTION"},
        {"from": "odr60_option_a_execution_closure", "to": "odr60_request", "relation": "RECORDS_OPTION_A_BUT_RETAINS_ALL_ADMISSION_GATES"},
        {"from": "r2_dynamics_engineering", "to": "r2_8dof_constrained_dynamics", "relation": "AGGREGATES_DIAGNOSTIC_WITHOUT_UPGRADING_HOLD"},
        {"from": "r2_dynamics_control_system", "to": "odr60_option_a_execution_closure", "relation": "REQUIRES_MECHANICAL_ADMISSION"},
        {"from": "r2_dynamics_control_system", "to": "r2_dynamics_engineering", "relation": "REQUIRES_DYNAMICS_ENGINEERING_PASS"},
        {"from": "r2_dynamics_control_system", "to": "r2_control_engineering", "relation": "REQUIRES_CONTROL_ENGINEERING_PASS"},
        {"from": "r2_dynamics_control_system", "to": "safe00_gate", "relation": "REQUIRES_INDEPENDENT_SAFE_REVIEW_AND_AUTHORIZATION"},
        {"from": "r2_dynamics_control_system", "to": "sim13_20_of_20", "relation": "NEGATIVE_CONTROLS_DO_NOT_GRANT_NON_ABORT_AUTHORITY"},
        {"from": "ctrl_r2_predevelopment", "to": "ctrl01_gate", "relation": "RETAINS_NEGATIVE_RESULT"},
        {"from": "ctrl_r2_predevelopment", "to": "ctrl02_gate", "relation": "BINDS_PROVISIONAL_SCOPE"},
        {"from": "ctrl_r2_predevelopment", "to": "e23_gate", "relation": "BINDS_PROVISIONAL_FLEX_EVIDENCE"},
        {"from": "ctrl_r2_predevelopment", "to": "safe00_gate", "relation": "INTERFACE_ONLY_NO_ALLOW"},
        {"from": "e23_gate", "to": "e22_gate", "relation": "SUPERSEDES_CURRENT_COUPLED_RECERT_BUT_RETAINS_HISTORY"},
        {"from": "sim13_post_terminal_addendum", "to": "mechanical_release_gate", "relation": "APPEND_ONLY_LATER_EVIDENCE_DOES_NOT_REWRITE_SNAPSHOT"},
    ]
    graph = {
        "schema": "REFERENCE_GRAPH_V1",
        "status": "NAVIGATION_ONLY",
        "authority": "NONE",
        "nodes": nodes,
        "edges": edges,
        "delete_executed": False,
        "move_or_archive_executed": False,
    }
    (out / "REFERENCE_GRAPH_V1.json").write_text(json.dumps(graph, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")

    generated = sorted(path for path in out.iterdir() if path.is_file())
    return {
        "source_count": len(records),
        "gate_row_count": len(gates),
        "strict_json_hold_count": sum(row["strict_json"] != "PASS" for row in gates),
        "active_work_count": len(active_rows),
        "hold_negative_count": len(hold_rows),
        "superseded_count": len(superseded_rows),
        "retirement_candidate_count": len(retirement_rows),
        "eligible_delete_candidate_count": len(delete_rows),
        "delete_executed": False,
        "move_or_archive_executed": False,
        "generated_files": [path.relative_to(repo).as_posix() for path in generated],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    summary = build(args.repo_root.resolve())
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
