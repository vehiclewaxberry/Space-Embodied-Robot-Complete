from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import yaml


PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
TZ = timezone(timedelta(hours=8))


REL = {
    "owner_attachment": Path(r"C:\Users\stude\.codex\attachments\097124c4-bbc4-4459-85c4-748019414866\pasted-text.txt"),
    "owner_gpt_01_06": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/00_authority/M7_OWNER_DECISION_ODR_GPT_01_TO_06_TERMINAL_CLOSURE_V1.yaml"),
    "owner_20_26": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/00_authority/M7_OWNER_DECISION_ODR20_TO_ODR26_TERMINAL_R2_V1.yaml"),
    "owner_27_34": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/00_authority/M7_OWNER_DECISION_ODR27_TO_ODR34_TERMINAL_FREEZE_V1.yaml"),
    "owner_19": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/00_authority/M7_OWNER_DECISION_ODR19_SOLAR_ARRAY_R2_ECR_V1.yaml"),
    "integration_spec": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/round1/03_integration_spec/R2_FLEX_COUPLING_INTEGRATION_SPEC_V1.yaml"),
    "round3_npz": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/round3_hf_rom_v2/R2_HF_ROM_NUMERICAL_DATA_V2.npz"),
    "round3_rom5": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/round3_hf_rom_v2/R2_FIVE_MODE_ROM_V2.json"),
    "round3_gate": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/round3_hf_rom_v2/R2_FULL_FLEX_HF_ROM_GATE_V2.json"),
    "round3_validity_envelope": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/round3_hf_rom_v2/R2_FLEXIBILITY_VALIDITY_ENVELOPE_V2.json"),
    "e22_config": Path("30_simulation/e22_r2_full_flex_coupled_diagnostics/config/e22_config.yaml"),
    "e22_model": Path("30_simulation/e22_r2_full_flex_coupled_diagnostics/src/e22_model.py"),
    "e22_builder": Path("30_simulation/e22_r2_full_flex_coupled_diagnostics/src/build_e22.py"),
    "e22_hf_rom": Path("30_simulation/e22_r2_full_flex_coupled_diagnostics/results/R2_HF_TO_ROM_DYNAMIC_VALIDATION_V1.json"),
    "e22_gate": Path("30_simulation/e22_r2_full_flex_coupled_diagnostics/results/E22_R2_FULL_FLEX_COUPLED_GATE_V1.json"),
    "e22_authority_audit": Path("30_simulation/e22_r2_full_flex_coupled_diagnostics/results/E22_SOURCE_AND_AUTHORITY_AUDIT_V1.json"),
    "rom5_falsifier": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/checkpoint_a/red_team/ROM5_DIMENSION_FALSIFIER_V1.json"),
    "rom5_falsifier_script": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/checkpoint_a/red_team/recompute_rom5_dimension_falsifier.py"),
    "multicontact": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/checkpoint_a/decision_support/MULTICONTACT_ROM_DIMENSION_DECISION_SUPPORT_V1.json"),
    "multicontact_script": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/checkpoint_a/decision_support/recompute_multicontact_rom_dimension.py"),
    "checkpoint_a": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/checkpoint_a/R2_FULL_FLEX_GATE_V1.json"),
    "checkpoint_a_redteam": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/checkpoint_a/red_team/R2_FULL_FLEX_FINAL_RED_TEAM_AUDIT_V1.json"),
    "e15_gate": Path("30_simulation/e15_ancf_certification/results/gate_summary.json"),
    "checkpoint_b": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/checkpoint_b/ROUTE_C_CHECKPOINT_B_GATE_V1.json"),
    "mission_gate": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/04_mission/B601_HARNESS_MISSION_COVERAGE_GATE.json"),
    "route_c_registry": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/route_c_prep/ROUTE_C_C2_01_REGISTRY_SKELETON_V1.yaml"),
    "handoff_v2": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/07_release/MECHANICAL_TO_EMBODIED_HANDOFF_GATE_V2.json"),
    "sim13_audit": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/09_downstream_rebind/SIM13_CURRENT_MECHANICAL_BINDING_AUDIT_GATE_V1.json"),
    "m4_gate": Path("20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/12_release/MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_GATE_V1.json"),
    "m4_fcstd": Path("20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/02_parameterized_cad/SEI_DIGITAL_PROTOTYPE_V1.FCStd"),
    "m4_config_library": Path("20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/03_mass_properties/CONFIGURATION_LIBRARY_V1.yaml"),
    "m5_collision_audit": Path("20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/02_configurations/M5_BROADPHASE_COLLISION_AUDIT_V1.json"),
    "m7_assembly": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp1_structure_cad/DESIGN_FREEZE_ASSEMBLY_BUILD_REPORT_V1.json"),
    "m7_fcstd": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp1_structure_cad/DESIGN_FREEZE_ASSEMBLY_V1.FCStd"),
    "r2_mass": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml"),
    "material": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp6_material_selection/DESIGN_MATERIAL_SELECTION_V1.yaml"),
    "process_register": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp6_material_selection/PROCESS_AND_FINISH_REGISTER_V1.csv"),
    "tolerance": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp3_tolerance_alloc/TOLERANCE_CHAIN_REGISTER_V1.yaml"),
    "tolerance_results": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp3_tolerance_alloc/TOLERANCE_ALLOCATION_RESULTS_V1.yaml"),
    "bom": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp9_release_package/BOM_V3_DESIGN.csv"),
    "drawing_index": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp9_release_package/DRAWING_SET_INDEX_V1.csv"),
    "wp9_receipt": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp9_release_package/receipt.json"),
    "fea1": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp7_fea_operational/FEA1_EVIDENCE_V1.json"),
    "fea1b": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp7_fea_operational/FEA1B_ELEMENT_FORMULATION_EVIDENCE_V1.json"),
    "solar_r2_card": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/FLEXIBLE_APPENDAGE_R2.yaml"),
    "solar_r2_build": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_BUILD_REPORT_V2.json"),
    "solar_r2_fcstd": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_CANDIDATE_V1.FCStd"),
    "solar_r2_structural_screen": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_R2_STRUCTURAL_IMPACT_SCREEN_V1.yaml"),
    "r1_flex_card": Path("20_engineering/config/geometry/flexible_appendage_v1.yaml"),
    "r1_frame_tree": Path("20_engineering/config/geometry/frame_tree_v1.yaml"),
    "sim11_model_card": Path("20_engineering/config/coupled_scene/coupled_model_v0.yaml"),
    "sim11_ffr_panel": Path("30_simulation/sim_11_coupled_dynamics/src/ffr_panel.py"),
    "sim11_config_loader": Path("30_simulation/sim_11_coupled_dynamics/src/config_loader.py"),
    "mpi_bridge": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/02_bridge/B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml"),
    "mpi_bridge_gate": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/08_gate/MPI_BRIDGE_GATE_V1.json"),
    "bridged_mass": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/06_mass_propagation/SYSTEM_MASS_PROPERTIES_BRIDGED_V1.yaml"),
    "mission_pose_rebind": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/04_mission/B601_MISSION_POSE_AUTHORITY_REBIND_V1.yaml"),
    "pregrasp_mission_contract": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/04_mission/B601_MANDATORY_MISSION_TRAJECTORY_CONTRACT_V1.yaml"),
    "accepted_b601_urdf": Path("20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"),
    "accepted_fk_module": Path("30_simulation/sim_05_free_floating_arm/b601_model.py"),
    "target_ssot": Path("20_engineering/config/geometry/target_models_v1.yaml"),
    "target_satellite_full_tensor": Path("20_engineering/cad/spacecraft_layout/target_satellite_v0/target_satellite_v0.json"),
    "target_debris_full_tensor": Path("20_engineering/cad/spacecraft_layout/target_debris_v0/target_debris_v0.json"),
    "contact_scene": Path("20_engineering/config/coupled_scene/scene_A2_capture.yaml"),
    "contact_window_implementation": Path("30_simulation/sim_11_coupled_dynamics/src/contact_window.py"),
    "common_capture_axis_source": Path("30_simulation/common/capture_impulse.py"),
    "interface_v6": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/07_rebind/MECH_DYNAMICS_INTERFACE_V6_CANDIDATE.yaml"),
    "embodied_r3": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/07_rebind/EMBODIED_MECHANICAL_CONTRACT_R3_CANDIDATE.yaml"),
    "odr_gpt04_falsifier": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/16_odr_gpt04_frozen_route_b_branch_falsifier/ODR_GPT_04_FROZEN_ROUTE_B_BRANCH_FALSIFIER_V1.json"),
    "odr_gpt04_falsifier_controls": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/16_odr_gpt04_frozen_route_b_branch_falsifier/ODR_GPT_04_FROZEN_ROUTE_B_ADVERSARIAL_CONTROLS_V1.json"),
    "odr_gpt04_falsifier_gate": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/16_odr_gpt04_frozen_route_b_branch_falsifier/ODR_GPT_04_FROZEN_ROUTE_B_BRANCH_GATE_V1.json"),
    "odr_gpt04_falsifier_manifest": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/16_odr_gpt04_frozen_route_b_branch_falsifier/ODR_GPT_04_FROZEN_ROUTE_B_BRANCH_SHA256.csv"),
}


def locate(value: Path) -> Path:
    return value if value.is_absolute() else ROOT / value


def repo_label(value: Path) -> str:
    path = locate(value)
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def pin(name: str) -> dict[str, Any]:
    path = locate(REL[name])
    if not path.is_file():
        raise FileNotFoundError(f"missing required input: {path}")
    return {
        "id": name,
        "path": repo_label(REL[name]),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def read_json(name: str) -> dict[str, Any]:
    return json.loads(locate(REL[name]).read_text(encoding="utf-8"))


def read_yaml(name: str) -> dict[str, Any]:
    return yaml.safe_load(locate(REL[name]).read_text(encoding="utf-8"))


def assert_close(actual: float, expected: float, tol: float = 1e-14) -> None:
    if abs(float(actual) - float(expected)) > tol:
        raise AssertionError(f"numeric drift: actual={actual!r}, expected={expected!r}")


class NoAliasSafeDumper(yaml.SafeDumper):
    def ignore_aliases(self, data: Any) -> bool:
        return True


def dump_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        yaml.dump(payload, Dumper=NoAliasSafeDumper, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
        newline="\n",
    )


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    PACKAGE.mkdir(parents=True, exist_ok=True)
    generated_local = datetime.now(TZ).isoformat(timespec="seconds")
    source_pins = {name: pin(name) for name in REL}

    owner_text = locate(REL["owner_attachment"]).read_text(encoding="utf-8")
    if source_pins["owner_attachment"]["sha256"] != "67821E04869BE8202CF2473980B73AA4CE595B9689CC9D54F340820C0D38F773":
        raise AssertionError("direct Owner attachment hash drift")
    if "3–5 dominant modes / wing" not in owner_text:
        raise AssertionError("direct Owner P2 mode-count clause not found")

    spec_text = locate(REL["integration_spec"]).read_text(encoding="utf-8")
    for phrase in (
        "historical reproduction only",
        "NO new conclusion may cite it",
        "no R1 numeric value into R2_FLEX",
        "R2 truncation convergence <1% MUST be re-established",
    ):
        if phrase not in spec_text:
            raise AssertionError(f"integration contract phrase missing: {phrase}")

    multicontact = read_json("multicontact")
    fixed = multicontact["single_fixed_basis_across_all_windows"]
    tc20 = multicontact["per_window"]["TC_20MS"]
    if fixed["minimum_passing_dimension_within_first12"] != 11:
        raise AssertionError("full registered-window minimum dimension drift")
    if fixed["minimum_passing_dimension_preserving_three_bending"] != 11:
        raise AssertionError("three-bending full registered-window minimum dimension drift")
    fixed11 = fixed["minimum_passing_subset_preserving_three_bending"]
    assert_close(fixed11["global_max_relative_error_across_windows"], 0.007426037032524928)
    if tc20["minimum_passing_dimension_within_first12"] != 6:
        raise AssertionError("20 ms minimum dimension drift")
    if tc20["minimum_passing_dimension_preserving_three_bending"] != 7:
        raise AssertionError("20 ms three-bending minimum dimension drift")
    assert_close(tc20["minimum_passing_subset"]["global_max_relative_error"], 0.006575808515557166)
    assert_close(tc20["minimum_passing_subset_preserving_three_bending"]["global_max_relative_error"], 0.002714391128536163)

    e22 = read_json("e22_gate")
    if e22["summary"] != {"passed": 16, "total": 18, "failed": ["G11", "G17"]}:
        raise AssertionError("E22 gate state drift")
    checkpoint_a = read_json("checkpoint_a")
    if checkpoint_a["summary"]["passed"] != 6 or checkpoint_a["summary"]["total"] != 12:
        raise AssertionError("Checkpoint-A state drift")
    checkpoint_b = read_json("checkpoint_b")
    if checkpoint_b["checkpoint_outcome"] != "HOLD":
        raise AssertionError("Checkpoint-B HOLD not preserved")
    if checkpoint_b["physical_registry"]["value_non_null"] != 0 or checkpoint_b["physical_registry"]["status_HOLD"] != 13:
        raise AssertionError("Route-C registry state drift")
    if checkpoint_b["admission"]["ROUTE_C_CAD_AUTHORIZED"] is not False:
        raise AssertionError("Route-C CAD prohibition not preserved")
    odr04_falsifier = read_json("odr_gpt04_falsifier")
    odr04_falsifier_gate = read_json("odr_gpt04_falsifier_gate")
    odr04_controls = read_json("odr_gpt04_falsifier_controls")
    if odr04_falsifier_gate["outcome"] != "PASS_FALSIFIER__FROZEN_ROUTE_B_ODR_GPT_04_BRANCH_CLOSED_NEGATIVE":
        raise AssertionError("ODR-GPT-04 frozen Route-B falsifier state drift")
    if odr04_falsifier_gate["summary"] != {"passed": 18, "total": 18, "failed": []}:
        raise AssertionError("ODR-GPT-04 frozen Route-B falsifier criterion drift")
    if odr04_controls["summary"] != {"passed": 18, "total": 18, "failed": []}:
        raise AssertionError("ODR-GPT-04 falsifier negative-control drift")
    if odr04_falsifier_gate["technical_verdict"] != "ODR_GPT_04_DEFERMENT_NOT_EARNED_FOR_FROZEN_ROUTE_B__REGISTERED_MANDATORY_STATES_UNSAFE__ROUTE_B_REOPENING_PROHIBITED__ROUTE_C_REQUIRED_UNLESS_SEPARATELY_AUTHORIZED_NEW_VERSIONED_ROUTE":
        raise AssertionError("ODR-GPT-04 falsifier technical verdict drift")
    if odr04_falsifier_gate["branch_state"]["current_frozen_route_b_rated_envelope_path"] != "TERMINAL_NEGATIVE_CURRENT_REGISTERED_BRANCH":
        raise AssertionError("ODR-GPT-04 registered-branch closure drift")
    if odr04_falsifier_gate["branch_state"]["odr_gpt_04_deferment_earned"] is not False:
        raise AssertionError("ODR-GPT-04 deferment was silently earned")
    if odr04_falsifier_gate["branch_state"]["route_c_required_to_continue"] is not True:
        raise AssertionError("Route-C continuation requirement was lost")
    if odr04_falsifier_gate["branch_state"]["route_c_cad_authorized"] is not False:
        raise AssertionError("ODR-GPT-04 falsifier fabricated Route-C CAD authority")
    if odr04_falsifier_gate["proof_scope_guard"] != {"global_q_no_go_claim_made": False, "fillet_trim_global_invariance_proved": False, "closure_basis": "REGISTERED_0_OF_10_SAFE__0_OF_8_RELEASED__MISSION_FAIL__ROUTE_B_REOPENING_NONE_PERMITTED"}:
        raise AssertionError("ODR-GPT-04 falsifier proof-scope guard drift")
    if not any("does not prove that every external harness topology" in item for item in odr04_falsifier["scope_and_nonclaims"]):
        raise AssertionError("ODR-GPT-04 falsifier physical-scope guard missing")
    e15 = read_json("e15_gate")
    if e15["overall"] != "REPEAT_ANCF_CERTIFICATION":
        raise AssertionError("e15 state drift")
    handoff = read_json("handoff_v2")
    if handoff["checks_passed"] != 11 or handoff["checks_total"] != 12 or handoff["failing_checks"] != ["G12"]:
        raise AssertionError("handoff state drift")
    sim13 = read_json("sim13_audit")
    if sim13["verdict"] != "CURRENT_SIM13_PRODUCTION_MECHANICAL_BINDING_INVALIDATED_BY_NEWER_M7_EVIDENCE":
        raise AssertionError("Sim13 binding state drift")
    m4 = read_json("m4_gate")
    if m4["overall_status"] != "PASS_SCOPED_M4_DIGITAL_PROTOTYPE_AND_SIM14_DIAGNOSTIC_WITH_MANDATORY_PHYSICAL_HOLDS":
        raise AssertionError("M4 scoped release state drift")
    assembly = read_json("m7_assembly")
    if assembly["verdict"] != "PASS_DESIGN_FREEZE_ASSEMBLY_BUILD_WITH_EXPLICIT_HOLDS":
        raise AssertionError("M7 assembly state drift")
    mass = read_yaml("r2_mass")
    if len(mass["configurations"]) != 9:
        raise AssertionError("R2 nine-configuration ledger drift")
    assert_close(mass["mass_ledgers"]["m7_design_ledger_c01_kg"], 31.022864807342987)

    evidence = lambda *names: ";".join(source_pins[name]["path"] for name in names)
    matrix_rows = [
        {
            "m4_line": "L01",
            "item": "数字样机总装",
            "inheritance_decision": "INHERIT_M4_AND_M7__DO_NOT_REBUILD",
            "current_state": "COMPLETED_M4__M7_R1_ASSEMBLY_PASS__R2_REBASE_PARTIAL",
            "current_blocker": "NO_FOR_COUPLED_DIAGNOSTICS__YES_FOR_TERMINAL_CM",
            "evidence_paths": evidence("m4_fcstd", "m7_fcstd", "m7_assembly", "solar_r2_fcstd", "solar_r2_build"),
            "remaining_gap": "WP1 总装保留 R1 solar proxy；Solar R2 独立冻结但尚未回灌统一 R2 总装；HDRM/部分传感器仍为显式未建模槽位。",
            "minimum_terminal_action": "技术闭环后一次性重发版本化 R2 统一总装与 manifest；不重建 M3–M7 底层几何。",
        },
        {
            "m4_line": "L02",
            "item": "九构型数字样机",
            "inheritance_decision": "INHERIT_SCHEMA_AND_POSES__USE_R2_MASS_LEDGER",
            "current_state": "PARTIAL__R2_MASS_CG_INERTIA_9_OF_9__CURRENT_SYSTEM_COLLISION_NOT_RELEASED",
            "current_blocker": "CONDITIONAL_FOR_PRODUCTION_CONTACT__NOT_E22_PRIMARY_BLOCKER",
            "evidence_paths": evidence("m4_config_library", "r2_mass", "mission_pose_rebind", "m5_collision_audit", "checkpoint_b", "sim13_audit"),
            "remaining_gap": "C01–C09 设计质量/CG/完整惯量已闭合；历史几何/碰撞资产仍仅可作诊断，当前 trajectory/contact authority 未释放。",
            "minimum_terminal_action": "终局接口绑定 R2 账本、当前命名位姿以及闭合后的线束/碰撞状态；不重算已闭合质量账本。",
        },
        {
            "m4_line": "L03",
            "item": "质量惯量闭环",
            "inheritance_decision": "SUPERSEDE_M4_WITH_WP2_V3_R2_AND_MPI_BRIDGE",
            "current_state": "COMPLETED_DESIGN_LEVEL__MPI_CONSISTENCY_PASS__NOT_AS_BUILT_OR_PRODUCTION",
            "current_blocker": "NO_FOR_DIAGNOSTIC_DYNAMICS__TERMINAL_PROMOTION_PENDING",
            "evidence_paths": evidence("r2_mass", "bridged_mass", "mpi_bridge_gate"),
            "remaining_gap": "9/9 设计属性及不确定度存在；账本仍为设计候选，非实测 as-built。",
            "minimum_terminal_action": "在新版 terminal interface/handoff 中提升消费关系；保留 as-built correlation HOLD。",
        },
        {
            "m4_line": "L04",
            "item": "材料与工艺",
            "inheritance_decision": "SUPERSEDE_M4_PROTOTYPE_LIBRARY_WITH_M7_WP6",
            "current_state": "COMPLETED_DESIGN_LEVEL__R2_FLEX_PHYSICS_PROVISIONAL",
            "current_blocker": "NO_UNDER_DECLARED_PROVISIONAL_SCOPE__QUALIFICATION_HOLD_ONLY",
            "evidence_paths": evidence("material", "process_register", "solar_r2_card", "round3_gate"),
            "remaining_gap": "关键材料/工艺为设计级；Solar R2 EI/GJ/k_theta/zeta 仍含 PROVISIONAL_DERIVED，飞行许用值未闭合。",
            "minimum_terminal_action": "保持暂定参数、标准不确定度与线性域显式标记；硬件/资格阶段替换。",
        },
        {
            "m4_line": "L05",
            "item": "三类公差链",
            "inheritance_decision": "SUPERSEDE_M4_PLANS_WITH_M7_14_CHAIN_ALLOCATION",
            "current_state": "COMPLETED_ANALYTIC_DESIGN_LEVEL",
            "current_blocker": "NO__ROUTE_C_PHYSICAL_NULLS_ARE_A_NEW_HARNESS_DOMAIN",
            "evidence_paths": evidence("tolerance", "tolerance_results", "checkpoint_b"),
            "remaining_gap": "B601–M3R、夹爪和太阳翼核心链分析闭合；Route-C P01–P13 是新的物理产品/布线路径输入问题。",
            "minimum_terminal_action": "直接继承；不得把 Route-C 空字段误报为 M4 公差链未完成。",
        },
        {
            "m4_line": "L06",
            "item": "图纸与 BOM",
            "inheritance_decision": "SUPERSEDE_M4_DRAFTS_WITH_M7_WP9_DESIGN_PACKAGE",
            "current_state": "COMPLETED_M7_BASE__R2_SOLAR_HARNESS_REISSUE_PARTIAL",
            "current_blocker": "NO_FOR_SOLVER__YES_FOR_TERMINAL_RELEASE_PACKAGE",
            "evidence_paths": evidence("drawing_index", "bom", "wp9_receipt", "solar_r2_build", "checkpoint_b"),
            "remaining_gap": "M7 基础包非采购/非制造；Solar R2 与最终 Route-C 尚未统一回灌 BOM/图纸。",
            "minimum_terminal_action": "R2 柔性和线束闭合后做 WP9 版本化重发；不重画已闭合 M3R 主体。",
        },
        {
            "m4_line": "L07",
            "item": "结构分析入口与验证",
            "inheritance_decision": "SUPERSEDE_M4_STRUCTURAL_HOLD_WITH_M7_OPERATIONAL_FEA__KEEP_FULL_FLEX_SEPARATE",
            "current_state": "PARTIAL__OPERATIONAL_FEA_PASS__FULL_FLEX_CHECKPOINT_A_HOLD",
            "current_blocker": "YES__G11_G17_AND_E15",
            "evidence_paths": evidence("fea1", "fea1b", "solar_r2_structural_screen", "e22_gate", "checkpoint_a", "e15_gate", "multicontact"),
            "remaining_gap": "Operational FEA 已通过其设计级范围；E22 为 16/18，G11/G17 失败；e15 仍需重认证。",
            "minimum_terminal_action": "先由 Owner 选择 P2 维数/有效域及 G17 比较器语义，再发布隔离 Round4/E22-V2/e15 重跑链。",
        },
        {
            "m4_line": "L08",
            "item": "MECH-RL / Embodied 接口与 Gate",
            "inheritance_decision": "SUPERSEDE_M4_V2_AND_HISTORICAL_R2_HANDOFF_WITH_MPI_V6_R3_TERMINAL_REBIND",
            "current_state": "HOLD__CURRENT_SIM13_PRODUCTION_BINDING_INVALIDATED__HANDOFF_11_OF_12",
            "current_blocker": "YES__PRIMARY_DOWNSTREAM_ENTRY_BLOCKER",
            "evidence_paths": evidence("interface_v6", "embodied_r3", "checkpoint_b", "mission_gate", "handoff_v2", "sim13_audit"),
            "remaining_gap": "V6/R3 仍为候选；线束 0/10 SAFE、0/8 轨迹释放；Route-C 13/13 HOLD；handoff G12 失败；Sim13 仍硬绑 V1 且无运行时线束门。",
            "minimum_terminal_action": "上游闭合后重发接口/合同，更新 Sim13 loader，并加入 FAIL/UNKNOWN 线束负控及独立 production/contact Gate。",
        },
    ]
    matrix_path = PACKAGE / "M4_TO_M7_INHERITANCE_AND_GAP_MATRIX_V1.csv"
    write_csv(
        matrix_path,
        ["m4_line", "item", "inheritance_decision", "current_state", "current_blocker", "evidence_paths", "remaining_gap", "minimum_terminal_action"],
        matrix_rows,
    )

    fixed_errors = fixed11["per_window_max_relative_error"]
    fixed7_errors = fixed["best_by_dimension_1_to_12"]["7"]["per_window_max_relative_error"]
    p2_request = {
        "schema": "P2_ROM_DIMENSION_AND_VALIDITY_OWNER_DECISION_REQUEST_V1",
        "record_type": "APPROVAL_REQUEST_NOT_AUTHORIZATION_RECORD",
        "requested_decision_id": "ODR-GPT-07",
        "generated_local": generated_local,
        "generated_clock_source": "HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08",
        "status": "PENDING_OWNER_DECISION",
        "owner_accepted": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "mechanical_release_issued": False,
        "current_authority": {
            "mode_count_direct_owner_authority": {
                **source_pins["owner_attachment"],
                "clause": "3–5 dominant modes / wing",
            },
            "current_mode_ceiling_per_wing": 5,
            "truncation_contract": {
                "relative_limit": 0.01,
                "comparison_operator": "LEQ",
                "authority_class": "FROZEN_DERIVED_GATE_CONTRACT__NOT_A_DIRECT_OWNER_QUOTE",
                "provenance": [source_pins["integration_spec"], source_pins["e22_config"]],
            },
        },
        "problem_statement": {
            "current_round3_basis": ["B1", "B2", "B3", "T1", "T2"],
            "current_round3_basis_hf_indices_0based": [0, 3, 7, 1, 2],
            "current_20ms_error": 0.03505870603435051,
            "best_first12_eigenmode_5D_20ms_error": 0.010829637562359794,
            "current_gate": "G11_FAIL",
            "evidence_scope_limitations": [
                "first12_nominal_eigenmode_subsets_only",
                "nominal_HF_only",
                "one_E22_150kg_diagnostic_base_delta_twist",
                "five_discrete_contact_windows_not_a_continuous_5_to_100ms_proof",
                "no_LOW_HIGH_or_two_scenario_coupled_closure",
                "does_not_exclude_nonmodal_POD_Krylov_or_modes_13_to_183",
            ],
        },
        "engineering_recommendation": {
            "recommended_option": "A_11D_FIVE_REGISTERED_WINDOWS_CANDIDATE",
            "basis": "minimum fixed eigenmode subset within first 12 that preserves B1/B2/B3 and passes the current 1 percent six-metric score at all five registered discrete windows",
            "authorization_effect": "candidate generation and validation only; no pre-awarded PASS",
        },
        "requested_ruling": {
            "selected_option": None,
            "options": {
                "A_11D_FIVE_REGISTERED_WINDOWS_CANDIDATE": {
                    "recommended": True,
                    "mode_count_per_wing": 11,
                    "nominal_hf_index_set_0based": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                    "canonical_storage_order": ["B1", "B2", "B3", "T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8"],
                    "canonical_order_to_nominal_hf_indices_0based": [0, 3, 7, 1, 2, 4, 5, 6, 8, 9, 10],
                    "coupled_second_order_generalized_dimension_6plus2m": 28,
                    "claim_scope": "NOMINAL_DIAGNOSTIC_INPUT_AT_FIVE_REGISTERED_DISCRETE_WINDOWS__CANDIDATE_ONLY",
                    "claimed_discrete_contact_windows_ms": [5.0, 10.0, 20.0, 50.0, 100.0],
                    "per_window_max_relative_error": fixed_errors,
                    "worst_relative_error": fixed11["global_max_relative_error_across_windows"],
                    "governing_discrete_window_ms": 5.0,
                    "candidate_only_until_all_gates_pass": True,
                    "all_other_contact_windows": "UNKNOWN",
                    "outside_domain_policy": "HF_FALLBACK_OR_FAIL_CLOSED",
                    "interpolation_or_extrapolation": "PROHIBITED",
                    "continuous_interval_claim": False,
                    "authorized_actions_after_separate_owner_decision": [
                        "issue the P2 contract addendum for the 11D fixed basis and five listed discrete windows",
                        "build and validate an isolated 11D-per-wing Round4 component package",
                    ],
                    "actions_conditioned_on_other_branches": [
                        "coupled E22-V2/E23 requires ODR-GPT-08 G17-resolution branch PASS and all component gates",
                        "R2 e15 requires the coupled campaign and independent checks PASS",
                    ],
                    "prohibited_actions": ["continuous 5-to-100ms claim", "pre-awarded E22, e15, Checkpoint-A or release credit"],
                },
                "B_7D_NOMINAL_20MS_CANDIDATE": {
                    "recommended": False,
                    "mode_count_per_wing": 7,
                    "nominal_hf_index_set_0based": [0, 1, 2, 3, 4, 5, 7],
                    "canonical_storage_order": ["B1", "B2", "B3", "T1", "T2", "T3", "T4"],
                    "canonical_order_to_nominal_hf_indices_0based": [0, 3, 7, 1, 2, 4, 5],
                    "coupled_second_order_generalized_dimension_6plus2m": 20,
                    "claim_scope": "NOMINAL_DIAGNOSTIC_INPUT_AT_20MS_ONLY__CANDIDATE_ONLY",
                    "claimed_discrete_contact_windows_ms": [20.0],
                    "nominal_20ms_max_relative_error": 0.002714391128536163,
                    "known_failed_windows_ms": [5.0, 10.0],
                    "known_failed_window_relative_errors": {"TC_5MS": fixed7_errors["TC_5MS"], "TC_10MS": fixed7_errors["TC_10MS"]},
                    "unclaimed_diagnostic_pass_windows_ms": [50.0, 100.0],
                    "unclaimed_diagnostic_window_relative_errors": {"TC_50MS": fixed7_errors["TC_50MS"], "TC_100MS": fixed7_errors["TC_100MS"]},
                    "all_other_contact_windows": "UNKNOWN",
                    "outside_domain_policy": "HF_FALLBACK_OR_FAIL_CLOSED",
                    "interpolation_or_extrapolation": "PROHIBITED",
                    "continuous_interval_claim": False,
                    "authorized_actions_after_separate_owner_decision": [
                        "issue the P2 contract addendum for the 7D fixed basis at exactly 20 ms",
                        "build and validate an isolated 7D-per-wing Round4 component package for exactly 20 ms",
                    ],
                    "actions_conditioned_on_other_branches": [
                        "coupled E22-V2/E23 requires ODR-GPT-08 G17-resolution branch PASS and all component gates",
                        "R2 e15 requires the coupled campaign and independent checks PASS",
                    ],
                    "prohibited_actions": ["claim 5 ms or 10 ms validity", "pre-awarded E22, e15, Checkpoint-A or release credit"],
                },
                "C_6D_FIRST12_EIGENMODE_MINIMUM_AT_NOMINAL_20MS_NONPREFERRED": {
                    "recommended": False,
                    "mode_count_per_wing": 6,
                    "nominal_hf_index_set_0based": [0, 1, 2, 3, 4, 5],
                    "canonical_storage_order": ["B1", "B2", "T1", "T2", "T3", "T4"],
                    "canonical_order_to_nominal_hf_indices_0based": [0, 3, 1, 2, 4, 5],
                    "coupled_second_order_generalized_dimension_6plus2m": 18,
                    "claim_scope": "MINIMUM_WITHIN_FIRST12_EIGENMODE_SUBSETS_FOR_NOMINAL_20MS_DIAGNOSTIC_INPUT_ONLY",
                    "claimed_discrete_contact_windows_ms": [20.0],
                    "nominal_20ms_max_relative_error": 0.006575808515557166,
                    "nonpreferred_reason": "drops B3 and is not an additive extension of the frozen five-mode bending family",
                    "all_other_contact_windows": "UNKNOWN",
                    "outside_domain_policy": "HF_FALLBACK_OR_FAIL_CLOSED",
                    "interpolation_or_extrapolation": "PROHIBITED",
                    "continuous_interval_claim": False,
                    "authorized_actions_after_separate_owner_decision": [
                        "issue the P2 contract addendum for the 6D first-12 eigenmode basis at exactly 20 ms",
                        "build and validate an isolated 6D-per-wing Round4 component package for exactly 20 ms",
                    ],
                    "actions_conditioned_on_other_branches": [
                        "coupled E22-V2/E23 requires ODR-GPT-08 G17-resolution branch PASS and all component gates",
                        "R2 e15 requires the coupled campaign and independent checks PASS",
                    ],
                    "prohibited_actions": ["claim B3 retention", "pre-awarded E22, e15, Checkpoint-A or release credit"],
                },
                "D_RETAIN_3_TO_5_MODE_CONTRACT_KEEP_HOLD": {
                    "disposition": "KEEP_CHECKPOINT_A_HOLD",
                    "authorized_actions": ["preserve existing evidence and HOLD"],
                    "prohibited_actions": ["Round4 release-path model build", "E22/e15 rerun for P2 closure", "release credit"],
                },
                "E_AUTHORIZE_SEPARATE_RESEARCH_ONLY_NONMODAL_BASIS": {
                    "disposition": "NEW_ISOLATED_RESEARCH_CONTRACT_REQUIRED__NO_CURRENT_GATE_OR_RELEASE_CREDIT",
                    "authorized_actions": ["draft a separate research-only nonmodal-basis contract"],
                    "prohibited_actions": ["feed the research branch into M7 release", "modify Round3/E22-V1", "claim P2 closure"],
                },
                "F_REVISE_AND_RESUBMIT": {
                    "authorized_actions": ["revise this decision request only"],
                    "prohibited_actions": ["model execution", "Gate or release credit"],
                },
                "G_REJECT": {
                    "authorized_actions": ["archive the rejected request while retaining current HOLD"],
                    "prohibited_actions": ["model execution", "Gate or release credit"],
                },
            },
        },
        "acceptance_contract_after_separate_approval": {
            "applies_only_if_selected_option_in": [
                "A_11D_FIVE_REGISTERED_WINDOWS_CANDIDATE",
                "B_7D_NOMINAL_20MS_CANDIDATE",
                "C_6D_FIRST12_EIGENMODE_MINIMUM_AT_NOMINAL_20MS_NONPREFERRED",
            ],
            "nonmatching_option_effect": "THIS_ACCEPTANCE_CONTRACT_DOES_NOT_AUTHORIZE_EXECUTION",
            "hf_reference": "HASH_PINNED_183_DOF_ROUND3",
            "basis_policy": {
                "construction_corner": "NOMINAL",
                "phi": "ONE_HASH_PINNED_MASS_NORMALIZED_PHI_PER_WING",
                "fixed_across": ["LOW", "NOMINAL", "HIGH", "both_scenarios", "all_claimed_discrete_windows"],
                "corner_reselection": False,
                "column_reordering": False,
                "state_semantics_change": False,
                "consumer_basis_switching": "PROHIBITED",
            },
            "mode_identity_verification": {
                "role": "VALIDATION_ONLY__NEVER_SELECTS_OR_REORDERS_THE_CONSUMER_BASIS",
                "mass_weighting": "HASH_PINNED_ROUND4_PER_WING_183_BY_183_HF_MASS_MATRIX__NOT_REDUCED_MROM",
                "mass_matrix_corner_policy": "same physical mass matrix for LOW/NOMINAL/HIGH; any corner-dependent mass matrix is a contract change and FAIL_CLOSED",
                "corner_assignment": {
                    "method": "maximum-total-MAC one-to-one bipartite assignment from NOMINAL canonical identities to each corner HF eigenset",
                    "tie_policy": "if alternative assignment objective values differ by <=1e-12, identity is AMBIGUOUS and FAIL_CLOSED; no lexicographic silent tie break",
                    "consumer_effect": "assignment validates identity only and never changes stored basis columns",
                },
                "same_family_required": True,
                "family_classifier": {
                    "method": "ARGMAX_OF_HASH_PINNED_BENDING_VS_TORSION_GENERALIZED_STRAIN_ENERGY_PARTITION",
                    "normalization": "family energies divided by their nonnegative sum for each HF eigenvector",
                    "proposed_minimum_dominant_fraction": 0.90,
                    "below_threshold_or_tie": "MIXED_OR_AMBIGUOUS__FAIL_CLOSED",
                    "artifact_requirement": "algorithm, energy operators, labels and results emitted in a versioned hash-pinned Round4 mode-identity artifact before Gate execution",
                },
                "proposed_nonclustered_mass_weighted_MAC_min": 0.90,
                "proposed_near_degenerate_cluster_trigger_relative_frequency_gap_LEQ": 0.01,
                "relative_frequency_gap_formula": "abs(f_i-f_j)/max(abs(f_i),abs(f_j),1e-14_Hz)",
                "cluster_construction": "after one-to-one corner assignment, form the transitive union of canonical identity pairs whose relative gap is <=0.01 in any LOW/NOMINAL/HIGH corner",
                "proposed_cluster_subspace_min_principal_cosine_squared": 0.90,
                "ambiguous_or_family_mismatch": "FAIL_CLOSED",
                "threshold_authority": "PROPOSED_IN_THIS_REQUEST__EFFECTIVE_ONLY_IF_SEPARATELY_OWNER_APPROVED",
            },
            "wings": ["LEFT", "RIGHT"],
            "scenarios": ["22KG_0P5DPS", "150KG_3DPS"],
            "corners": ["LOW", "NOMINAL", "HIGH"],
            "damping_lane": "UNDAMPED_CONSERVATION_GATE",
            "metrics": ["tip_peak_m", "node_peak_m", "slope_peak_rad", "hinge_peak_rad", "torsion_peak_rad", "modal_energy_peak_J"],
            "score_formula": "max_over_scenario_corner_wing_claimed_window_metric(abs(peak_ROM-peak_HF)/max(abs(peak_HF),denominator_floor_for_metric))",
            "comparison_operator": "LEQ",
            "relative_limit": 0.01,
            "denominator_floor_by_metric": {
                "tip_peak_m": {"value": 1.0e-14, "unit": "m"},
                "node_peak_m": {"value": 1.0e-14, "unit": "m"},
                "slope_peak_rad": {"value": 1.0e-14, "unit": "rad"},
                "hinge_peak_rad": {"value": 1.0e-14, "unit": "rad"},
                "torsion_peak_rad": {"value": 1.0e-14, "unit": "rad"},
                "modal_energy_peak_J": {"value": 1.0e-14, "unit": "J"},
            },
            "contact_and_time_contract": {
                "shape": "half_sine_equal_impulse",
                "lockup": True,
                "component_post_window_s": 5.0,
                "component_contact_samples_including_endpoints": 401,
                "component_post_samples_including_endpoints": 5001,
                "component_peak_rule": "MAX_ABS_OVER_ENDPOINTS_CONTACT_BOUNDARY_AND_ALL_DENSE_OUTPUT_STATIONARY_POINTS",
                "peak_extractor": {
                    "candidate_bracketing_grids": {"contact_samples": 401, "post_samples": 5001},
                    "refined_bracketing_grids": {"contact_samples": 801, "post_samples": 10001},
                    "stationary_point_solver": "bracket derivative sign changes on each grid; refine every bracket on solver dense output with Brent root xtol_s=1e-12; include endpoints and contact lockup boundary",
                    "coincident_or_unbracketed_extremum_policy": "also test derivative-near-zero grid nodes and adjacent intervals; any unresolved candidate is FAIL_CLOSED",
                    "primary_vs_refined_peak_relative_formula": "abs(peak_primary-peak_refined)/max(abs(peak_refined),denominator_floor_for_metric)",
                    "proposed_primary_vs_refined_peak_relative_limit": 1.0e-4,
                    "comparison_operator": "LEQ",
                    "final_peak_source": "refined stationary-point set; sampled-grid maximum alone is insufficient",
                },
                "coupled_post_window_s": 40.0,
                "claimed_contact_windows": "SELECTED_OPTION_ONLY",
            },
            "solver_cross": {
                "primary": "Radau",
                "cross": "BDF",
                "rtol": 1.0e-10,
                "atol": 1.0e-12,
                "contact_max_step_divisions": 50,
                "relative_formula": "abs(a-b)/max(abs(a),abs(b),1e-14_with_matching_unit)",
                "comparison_operator": "LEQ",
                "relative_limit": 0.05,
            },
            "pass_logic": "ALL_REQUIRED_CASES_PASS",
            "supplements_not_replaces": {
                "E22_G01_TO_G18": True,
                "G12_linearity_limits": {"rotation_rad": 0.05, "translation_m": 0.03, "policy": "FAIL_CLOSED"},
                "conservation_negative_control_and_hash_gates": "ALL_RETAINED",
                "E22_threshold_source": source_pins["e22_config"],
                "G12_linearity_threshold_source": source_pins["round3_validity_envelope"],
            },
        },
        "authorization_matrix_after_separate_owner_decision": {
            "A_B_C": {
                "selected_option_must_be_one_of": [
                    "A_11D_FIVE_REGISTERED_WINDOWS_CANDIDATE",
                    "B_7D_NOMINAL_20MS_CANDIDATE",
                    "C_6D_FIRST12_EIGENMODE_MINIMUM_AT_NOMINAL_20MS_NONPREFERRED",
                ],
                "authorized_directly_by_ODR_GPT_07": ["publish the selected versioned P2 addendum", "build and close the isolated Round4 component package"],
                "conditioned_actions": {
                    "coupled_E22_V2_or_E23": "requires Round4 component PASS AND a valid ODR-GPT-08 G17-resolution branch PASS",
                    "R2_e15_recertification": "requires coupled E22-V2/E23 and its independent checks PASS",
                    "interface_handoff_and_release_chain": "requires technical subgate, Route-C physical/CAD/mission closure and all downstream joins PASS; the current frozen Route-B ODR-GPT-04 alternative is falsified and has no release edge",
                },
            },
            "D": {"effect": "retain current 3-to-5-mode contract and Checkpoint-A HOLD; no execution authority"},
            "E": {"effect": "research-only branch under a new isolated contract; no M7 Gate or release path"},
            "F_G": {"effect": "revise/reject path; no execution authority"},
        },
        "prohibited_even_if_approved": [
            "modify Round3 or E22-V1 in place",
            "modify Solar R2 CAD/STEP or accepted B601 URDF",
            "change physical mass, MPI bridge or e21 rigid result without a separate trigger",
            "relax the 1 percent score or remove torsion without a separate explicit ruling",
            "inherit e15 PASS",
            "claim release, qualification or Owner acceptance from this authorization alone",
        ],
        "conditional_release_chain": {
            "applies_only_if_selected_option_in": [
                "A_11D_FIVE_REGISTERED_WINDOWS_CANDIDATE",
                "B_7D_NOMINAL_20MS_CANDIDATE",
                "C_6D_FIRST12_EIGENMODE_MINIMUM_AT_NOMINAL_20MS_NONPREFERRED",
            ],
            "requires_ODR_GPT_08_resolution_before_coupled_campaign": True,
            "steps": [
            "contract_addendum_V2",
            "isolated_Round4_ROM_build",
            "Round4_component_independent_recompute_determinism_negative_controls_and_redteam",
            "join_ODR_GPT_08_G17_resolution_branch",
            "isolated_E22_V2_or_E23_full_campaign",
            "E22_independent_recompute",
            "E22_determinism_replay_and_package_manifest",
            "coupled_final_redteam_and_falsifier",
            "R2_e15_T1_to_T8_recertification",
            "A07_A09_technical_subgate_reissue_only",
            "join_Route_C_physical_and_mission_harness_resolution",
            "MECH_DYNAMICS_INTERFACE_rebind",
            "EMBODIED_MECHANICAL_CONTRACT_rebind",
            "Sim13_loader_update_and_runtime_harness_gate",
            "Handoff_rerun",
            "complete_Checkpoint_A_A01_A12_reissue",
            "final_unified_R2_assembly_collision_drawing_BOM_CM_reissue",
            "terminal_full_scope_redteam",
            "finding_level_falsifier",
            "TMG_1_to_TMG_7_aggregation",
            "release_manifest_and_hash_audit",
            "Checkpoint_C_only_after_all_independent_blockers_close",
            ],
        },
        "unchanged_independent_blockers": [
            "G17_SAME_SCOPE_TWO_SCENARIO_LEGACY_R1_EVIDENCE_INCOMPLETE_UNLESS_OWNER_EXPLICITLY_RESCOPES",
            "E15_REPEAT_ANCF_CERTIFICATION",
            "HARNESS_MISSION_COVERAGE_FAIL",
            "HARNESS_FROZEN_ROUTE_B_ODR_GPT_04_BRANCH_FALSIFIED__ROUTE_C_PHYSICAL_REGISTRY_13_OF_13_HOLD",
        ],
        "owner_decision_record": {
            "selected_option": None,
            "directive_verbatim": None,
            "source_path": None,
            "source_sha256": None,
            "effective_date": None,
        },
        "evidence_pins": [
            source_pins[name]
            for name in (
                "owner_attachment", "owner_gpt_01_06", "owner_20_26", "owner_27_34",
                "integration_spec", "round3_npz", "round3_rom5", "round3_gate", "round3_validity_envelope",
                "e22_config", "e22_hf_rom", "e22_gate", "rom5_falsifier",
                "rom5_falsifier_script", "multicontact", "multicontact_script",
                "checkpoint_a", "checkpoint_a_redteam", "e15_gate",
                "odr_gpt04_falsifier_gate", "odr_gpt04_falsifier_manifest",
            )
        ],
        "approval_record_rule": "This request is immutable and shall never be edited into PASS. A separately issued direct Owner decision must reference this request SHA-256.",
        "self_hash_policy": "SELF_REFERENCE_EXCLUDED; TERMINAL_DECISION_PACK_SHA256.csv pins this request after emission",
    }
    p2_path = PACKAGE / "P2_ROM_DIMENSION_AND_VALIDITY_DECISION_REQUEST_V1.yaml"
    dump_yaml(p2_path, p2_request)

    bridged = read_yaml("bridged_mass")
    bridged_c07 = next(item for item in bridged["configurations"] if item["configuration_id"] == "C07")
    r2_composition = bridged_c07["composition_candidate"]
    r2_solar_ids = {"solar_array_r2_left", "solar_array_r2_right"}
    retained_non_solar = [item for item in r2_composition if item["component_id"] not in r2_solar_ids]
    expected_non_solar_ids = {
        "bus_primary_structure",
        "b601_complete_arm_including_gripper_urdf_links",
        "m3r_stage_a_plus_stage_b_budget_envelope",
        "spacecraft_load_bridge_candidate",
    }
    if {item["component_id"] for item in retained_non_solar} != expected_non_solar_ids:
        raise AssertionError("bridged C07 non-solar composition whitelist drift")

    r1_card = read_yaml("r1_flex_card")
    r1_frames = read_yaml("r1_frame_tree")
    r1_wing_mass = float(r1_card["mass"]["m_panel_kg"])
    r1_span_m = float(r1_card["geometry"]["span_L_m"])
    r1_own_inertia = np.diag([
        float(r1_card["mass"]["I_own_com_kgm2"]["Ixx"]),
        float(r1_card["mass"]["I_own_com_kgm2"]["Iyy"]),
        float(r1_card["mass"]["I_own_com_kgm2"]["Izz"]),
    ])
    root_left = np.asarray(r1_frames["frames"]["F_L"]["origin_mm"], float) / 1000.0
    root_right = np.asarray(r1_frames["frames"]["F_R"]["origin_mm"], float) / 1000.0
    r1_left_cg = root_left + np.array([0.0, +0.5 * r1_span_m, 0.0])
    r1_right_cg = root_right + np.array([0.0, -0.5 * r1_span_m, 0.0])
    r1_components = [
        {"component_id": "legacy_r1_solar_left", "mass_kg": r1_wing_mass, "com_S_m": r1_left_cg.tolist(), "inertia_about_own_com_S_kg_m2": r1_own_inertia.tolist()},
        {"component_id": "legacy_r1_solar_right", "mass_kg": r1_wing_mass, "com_S_m": r1_right_cg.tolist(), "inertia_about_own_com_S_kg_m2": r1_own_inertia.tolist()},
    ]

    def aggregate_components(components: list[dict[str, Any]]) -> tuple[float, np.ndarray, np.ndarray]:
        total_mass = float(sum(float(item["mass_kg"]) for item in components))
        center = sum(float(item["mass_kg"]) * np.asarray(item["com_S_m"], float) for item in components) / total_mass
        inertia = np.zeros((3, 3), float)
        for item in components:
            component_mass = float(item["mass_kg"])
            offset = np.asarray(item["com_S_m"], float) - center
            inertia += np.asarray(item["inertia_about_own_com_S_kg_m2"], float)
            inertia += component_mass * ((offset @ offset) * np.eye(3) - np.outer(offset, offset))
        return total_mass, center, inertia

    current_non_solar, _, _ = aggregate_components(retained_non_solar)
    r1_pair_mass, r1_pair_cg, r1_pair_inertia = aggregate_components(r1_components)
    r1_comparator_pre_computed, r1_comparator_cg, r1_comparator_inertia = aggregate_components(retained_non_solar + r1_components)
    assert_close(current_non_solar, 29.46286480734299)
    assert_close(r1_pair_mass, 0.6967866)
    if np.max(np.abs(r1_pair_cg - np.array([-0.05675, 0.0, 0.0]))) > 1.0e-14:
        raise AssertionError("R1 pair CG reconstruction drift")
    if np.max(np.abs(r1_pair_inertia - np.diag([0.0339817637968385, 0.00299415, 0.036971733196838504]))) > 1.0e-14:
        raise AssertionError("R1 pair inertia reconstruction drift")
    assert_close(r1_comparator_pre_computed, 30.15965140734299)
    expected_r1_comparator_cg = np.array([0.09253568086034931, 4.5015873411029815e-05, -0.0013347633708374748])
    expected_r1_comparator_inertia = np.array([
        [0.26151636136753187, -0.0005770371145114792, 0.057243974283329536],
        [-0.0005770371145114792, 1.8042033853439725, -2.0585734207315368e-05],
        [0.057243974283329536, -2.0585734207315368e-05, 1.8138193934148086],
    ])
    if np.max(np.abs(r1_comparator_cg - expected_r1_comparator_cg)) > 1.0e-14:
        raise AssertionError("R1 comparator CG reconstruction drift")
    if np.max(np.abs(r1_comparator_inertia - expected_r1_comparator_inertia)) > 1.0e-14:
        raise AssertionError("R1 comparator inertia reconstruction drift")
    # Emit controlled decimal witnesses instead of binary float rendering noise.
    r2_pre_mass = 31.022864807342987
    r2_solar_mass = 1.56
    r1_comparator_pre = 30.15965140734299
    r1_comparator_plus_22 = 52.15965140734299
    r1_comparator_plus_150 = 180.159651407343
    legacy_request = {
        "schema": "LEGACY_R1_COMPARATOR_SEMANTICS_OWNER_DECISION_REQUEST_V1",
        "record_type": "APPROVAL_REQUEST_NOT_AUTHORIZATION_RECORD",
        "requested_decision_id": "ODR-GPT-08",
        "generated_local": generated_local,
        "generated_clock_source": "HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08",
        "status": "PENDING_OWNER_DECISION",
        "owner_accepted": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "problem_statement": {
            "current_E22_G17": "FAIL",
            "authority_conflict": "current integration spec makes Legacy R1 historical reproduction only and forbids new conclusions; a new protocol-matched comparator therefore requires a narrow explicit Owner amendment",
            "forbidden_misnomer": "HISTORICAL_FULL_SYSTEM_REPRODUCTION",
            "correct_model_class": "CONTROLLED_COUNTERFACTUAL_PROTOCOL_COMPARATOR",
        },
        "engineering_recommendation": {
            "recommended_option": "A_FOUR_LANE_PROTOCOL_MATCHED_COMPARATOR",
            "reason": "creates within-family rigid/flexible causal pairs while preserving complete R1-to-R2 numerical isolation",
            "credit_ceiling": "NEW_V2_G17_PROTOCOL_COMPLETENESS_ONLY__OLD_E22_G17_REMAINS_FAIL",
        },
        "requested_ruling": {
            "selected_option": None,
            "options": {
                "A_FOUR_LANE_PROTOCOL_MATCHED_COMPARATOR": {
                    "recommended": True,
                    "decision_effect_if_separately_approved": "NARROW_SEMANTICS_AMENDMENT_PLUS_BOUNDED_COMPARATOR_RUN_AUTHORIZATION_ONLY",
                    "owner_selection_alone_closes_G17": False,
                    "owner_selection_checkpoint_A_effect": "NONE",
                    "owner_selection_release_credit": False,
                    "simulation_authorized_now_by_this_request": False,
                    "narrow_amendment": {
                        "amends_only": "hash-pinned integration-spec LEGACY_R1_FLEX consumption/discipline and lane_isolation_invariants only as required to permit the isolated counterfactual",
                        "unchanged": "all other historical-only and no-R1-to-R2 prohibitions",
                        "integration_spec": source_pins["integration_spec"],
                    },
                    "canonical_lanes": [
                        "LEGACY_R1_SOLAR_SUBSYSTEM_RIGID_COUNTERFACTUAL_COMPARATOR",
                        "LEGACY_R1_SOLAR_SUBSYSTEM_FLEX_COUNTERFACTUAL_COMPARATOR",
                        "R2_RIGID_CURRENT",
                        "R2_SOLAR_FLEX_CURRENT",
                    ],
                    "within_family_causal_pairs": [
                        "LEGACY_R1_SOLAR_SUBSYSTEM_FLEX_COUNTERFACTUAL_COMPARATOR_MINUS_LEGACY_R1_SOLAR_SUBSYSTEM_RIGID_COUNTERFACTUAL_COMPARATOR",
                        "R2_SOLAR_FLEX_CURRENT_MINUS_R2_RIGID_CURRENT",
                    ],
                    "cross_family_semantics": "DESIGN_FAMILY_DELTA__NO_CAUSAL_FLEX_ATTRIBUTION",
                    "new_gate_name": "FOUR_LANE_TWO_SCENARIO_PROTOCOL_COMPLETENESS",
                    "old_E22_V1_disposition": "PRESERVE_UNCHANGED; issue V2 or addendum",
                    "R2_binding": {
                        "credit_eligible_binding": "ODR_GPT_07_APPROVED_ROUND4_FINAL_R2_ROM_AND_HASH",
                        "current_ROM5_use": "PRELIMINARY_NO_G17_CREDIT",
                        "stale_triggers": ["R2_ROM_hash", "R2_mode_dimension", "MPI_bridge_hash", "C07_mass_hash", "contact_contract_hash", "target_tensor_hash"],
                        "stale_disposition": "STALE_REQUIRES_FULL_FOUR_LANE_RERUN",
                    },
                },
                "B_REMOVE_LEGACY_NUMERICAL_G17_RETAIN_HISTORICAL_NARRATIVE": {
                    "recommended": False,
                    "effect": "Owner narrows the new-paper evidence scope; a new Gate records scope change and does not relabel old G17 FAIL as PASS",
                },
                "C_RETAIN_CURRENT_SAME_SCOPE_REQUIREMENT": {
                    "effect": "Checkpoint-A remains HOLD because current authority does not permit the required numerical comparator"
                },
                "D_REVISE_AND_RESUBMIT": {},
                "E_REJECT": {},
            },
        },
        "r1_protocol_comparator_mass_ledger": {
            "frame": "CURRENT_C07_SYSTEM_FRAME_S_WITH_CONFIRMED_MPI_BRIDGE",
            "source_configuration": "SYSTEM_MASS_PROPERTIES_BRIDGED_V1.yaml#configurations[C07].composition_candidate",
            "retained_component_whitelist": sorted(expected_non_solar_ids),
            "deleted_component_ids": sorted(r2_solar_ids),
            "added_component_ids": ["legacy_r1_solar_left", "legacy_r1_solar_right"],
            "post_capture_construction": "reaggregate this R1 counterfactual C07 plus the selected target full spatial tensor; direct C08/C09 consumption is prohibited",
            "current_R2_pre_capture_mass_kg": r2_pre_mass,
            "current_R2_two_wing_mass_kg": r2_solar_mass,
            "current_C07_non_solar_mass_kg": current_non_solar,
            "legacy_R1_mass_per_wing_kg": r1_wing_mass,
            "legacy_R1_pair_witness": {
                "mass_kg": r1_pair_mass,
                "cg_S_m": r1_pair_cg.tolist(),
                "inertia_about_pair_cg_S_kg_m2": r1_pair_inertia.tolist(),
                "root_left_S_m": root_left.tolist(),
                "root_right_S_m": root_right.tolist(),
                "panel_cg_left_S_m": r1_left_cg.tolist(),
                "panel_cg_right_S_m": r1_right_cg.tolist(),
                "panel_own_inertia_S_kg_m2": r1_own_inertia.tolist(),
            },
            "R1_rigid_body_mass_inertia_authority": {
                "binding_sources": [source_pins["r1_flex_card"], source_pins["r1_frame_tree"]],
                "binding_fields": ["mass.m_panel_kg", "mass.mu_kg_per_m", "mass.I_own_com_kgm2", "geometry", "r1_frame_tree.frames.F_L", "r1_frame_tree.frames.F_R"],
                "rule": "the decimal values in the card and the frame projections define each R1 wing rigid-body mass, CG and own inertia; both R1 rigid and R1 flex lanes consume the same reconstructed Mbb",
                "FFRPanel_gross_inertia_disposition": "FFRPanel quadrature J_rot/m_nodes may generate Phi/K/B and an audit witness but shall not redefine gross wing Mbb",
                "explicit_closure_correction": "replace the FFR-generated gross rigid block with the card-derived Mbb; record the pre-correction residual and require the post-correction residual <=1e-12 kg or kg*m^2 by field",
                "current_two_wing_pre_correction_inertia_residual_diag_kg_m2": [1.598000033381285e-10, 8.575000050720982e-11, 1.2595000677475547e-10],
                "silent_correction": False,
            },
            "R1_protocol_comparator_pre_capture_mass_kg": r1_comparator_pre,
            "R1_protocol_comparator_pre_capture_cg_S_m": r1_comparator_cg.tolist(),
            "R1_protocol_comparator_pre_capture_inertia_about_cg_S_kg_m2": r1_comparator_inertia.tolist(),
            "R1_protocol_comparator_plus_22kg_kg": r1_comparator_plus_22,
            "R1_protocol_comparator_plus_150kg_kg": r1_comparator_plus_150,
            "uncertainty": {
                "retained_non_solar_member_uncertainties": "CARRIED_VERBATIM_FROM_BRIDGED_C07_COMPOSITION",
                "legacy_R1_contribution": None,
                "legacy_R1_contribution_status": "UNKNOWN_NO_MEASUREMENT_OR_DECLARED_STANDARD_UNCERTAINTY__NO_ZERO_FILL",
                "aggregate_status": "PARTIALLY_KNOWN__DO_NOT_COLLAPSE_TO_A_SINGLE_STANDARD_UNCERTAINTY_BEFORE_R1_INPUT_EXISTS",
            },
            "reconstruction_tolerances": {
                "mass_abs_kg": 1.0e-12,
                "cg_component_abs_m": 1.0e-12,
                "inertia_component_abs_kg_m2": 1.0e-12,
                "root_and_panel_cg_component_abs_m": 1.0e-12,
            },
            "composition_rule": "CURRENT_C07_NON_SOLAR_STACK_PLUS_NATIVE_R1_LEFT_AND_RIGHT_WINGS",
            "not_equal_to_historical_sim11_stack": True,
            "not_current_R1_authority": True,
        },
        "protocol_fingerprint": {
            "canonical_case_count": 8,
            "cases": "4 lanes x 2 targets",
            "canonical_case_key_contract": {
                "key_fields": ["lane_id", "scenario_id"],
                "required_set": "EXACT_CARTESIAN_PRODUCT(canonical_lanes, scenarios)",
                "required_keys": [
                    "LEGACY_R1_SOLAR_SUBSYSTEM_RIGID_COUNTERFACTUAL_COMPARATOR__TARGET_22KG_0P5DPS",
                    "LEGACY_R1_SOLAR_SUBSYSTEM_RIGID_COUNTERFACTUAL_COMPARATOR__TARGET_150KG_3DPS",
                    "LEGACY_R1_SOLAR_SUBSYSTEM_FLEX_COUNTERFACTUAL_COMPARATOR__TARGET_22KG_0P5DPS",
                    "LEGACY_R1_SOLAR_SUBSYSTEM_FLEX_COUNTERFACTUAL_COMPARATOR__TARGET_150KG_3DPS",
                    "R2_RIGID_CURRENT__TARGET_22KG_0P5DPS",
                    "R2_RIGID_CURRENT__TARGET_150KG_3DPS",
                    "R2_SOLAR_FLEX_CURRENT__TARGET_22KG_0P5DPS",
                    "R2_SOLAR_FLEX_CURRENT__TARGET_150KG_3DPS",
                ],
                "uniqueness": "each key occurs exactly once; duplicate, missing or extra key is FAIL",
                "rigid_lane_corner": "NOT_APPLICABLE",
                "flex_lane_corner": "NOMINAL",
                "empty_comparison_set": "FAIL",
            },
            "scenarios": [
                {"id": "TARGET_22KG_0P5DPS", "mass_kg": 22.0, "tumble_rate_dps": 0.5},
                {"id": "TARGET_150KG_3DPS", "mass_kg": 150.0, "tumble_rate_dps": 3.0},
            ],
            "canonical_flex_corner": "NOMINAL_FOR_BOTH_FLEX_LANES",
            "LOW_HIGH_disposition": "SUPPORTING_SENSITIVITY_ONLY__NOT_PART_OF_EIGHT_CANONICAL_CASES",
            "R1_flex_definition": {
                "EI_N_m2": 0.0089042,
                "binding_parameter": "EI_N_m2",
                "first_mode_frequency_hz_computed": 1.000203676127154,
                "one_hz_status": "ROUNDED_DESIGN_LABEL_ONLY__NOT_AN_EXACT_NUMERICAL_CONSTRAINT",
                "computed_frequencies_hz_m1_to_m5": [1.000203676127154, 6.268169442271444, 17.55105593997081, 34.3930647769711, 56.854200413691096],
                "canonical_modes_per_wing": 5,
                "convergence_witness_modes_per_wing": [3, 4, 5],
                "damping_ratio": 0.0,
                "formulation": "Euler-Bernoulli analytic cantilever eigenmodes; mass-normalized by Gauss-Legendre quadrature; n_quad=24; chordwise/thickness rotary inertia closes only the card-authoritative rigid block",
                "flex_operator_outputs": ["Phi", "K", "B_t", "B_r", "response_extractors"],
            },
            "R2_flex_definition": "FINAL_ODR_GPT_07_APPROVED_ROUND4_ROM_HASH_REQUIRED_FOR_G17_CREDIT",
            "common_inputs": [
                "current confirmed MPI bridge",
                "current PREGRASP joint vector and accepted FK/T_E",
                "22 kg and 150 kg full target inertia tensors",
                "R_flip=diag(-1,-1,+1)",
                "common tumble axis",
                "v_app=0.01 m/s",
                "20 ms half-sine contact and lockup",
                "Radau and BDF with common tolerances",
                "40 s post-contact window",
                "common output definitions",
            ],
            "initial_modal_state": "ZERO_INDEPENDENT_FOR_EACH_LANE",
            "canonical_conservation_damping_ratio": 0.0,
            "common_output_fields": [
                "omega_plus_equiv_dps",
                "base_attitude_excursion_max_deg",
                "modal_energy_max_J",
                "wheel_momentum_required_Nms",
                "stabilization_proxy",
                "diagnostic_gate_classification",
            ],
            "rigid_modal_energy_semantics": "NOT_APPLICABLE_STRUCTURAL_ZERO_BY_MODEL_CONSTRUCTION__NOT_A_MEASURED_ZERO",
        },
        "acceptance_conditions_after_separate_approval": {
            "applies_only_if_selected_option": "A_FOUR_LANE_PROTOCOL_MATCHED_COMPARATOR",
            "nonmatching_option_effect": "NO_COMPARATOR_EXECUTION_AUTHORITY",
            "authority_and_CM": [
                "new direct Owner decision hash-pinned by new config",
                "narrow addendum does not rewrite the existing integration spec in place",
                "all source hashes match; old E22-V1, Checkpoint-A and sim11 artifacts remain unchanged",
            ],
            "per_lane_source_control": {
                "rule_scope": "all authority-bearing physical/numerical model inputs plus every executable, configuration and runtime-environment artifact actually consumed by the comparator",
                "common_whitelist_all_lanes": {
                    "confirmed_MPI_bridge": [source_pins["mpi_bridge"], source_pins["mpi_bridge_gate"]],
                    "PREGRASP_pose_and_kinematics": [source_pins["pregrasp_mission_contract"], source_pins["mission_pose_rebind"], source_pins["accepted_b601_urdf"], source_pins["accepted_fk_module"]],
                    "target_full_tensor_contract": [source_pins["target_ssot"], source_pins["target_satellite_full_tensor"], source_pins["target_debris_full_tensor"]],
                    "contact_and_capture_axis": [source_pins["contact_scene"], source_pins["contact_window_implementation"], source_pins["common_capture_axis_source"]],
                    "parent_protocol_and_reference_implementation": [source_pins["e22_config"], source_pins["e22_model"], source_pins["e22_builder"]],
                },
                "common_authority_field_map_all_lanes": [
                    {"source": source_pins["mpi_bridge"], "pointers": ["$.T_PHYSICAL_TO_DYNAMIC.homogeneous_4x4", "$.S_frame_conjugate_for_S_expressed_quantities.C_S_homogeneous_4x4"], "unit": "homogeneous transform with translation in m", "frame": "A0_physical_to_A0_dynamics and S-expressed conjugate"},
                    {"source": source_pins["pregrasp_mission_contract"], "pointers": ["$.joint_order", "$.states.PREGRASP.q_rad"], "unit": "ordered joint ids; rad", "frame": "accepted B601 URDF joint coordinates"},
                    {"source": source_pins["mission_pose_rebind"], "pointers": ["$.current_urdf.sha256", "$.states.PREGRASP.current_exact_fk_loadability", "$.states.PREGRASP.q_rad"], "unit": "hash; boolean; rad", "frame": "accepted B601 URDF joint coordinates"},
                    {"source": source_pins["accepted_b601_urdf"], "pointers": ["/robot/joint[*]/origin", "/robot/joint[*]/axis", "/robot/joint[*]/limit"], "unit": "URDF SI: m, rad, rad/s, N*m", "frame": "A0/base_link kinematic tree"},
                    {"source": source_pins["target_ssot"], "pointers": ["$.target_satellite_v0.mass_kg", "$.target_satellite_v0.inertia_diag_kgm2", "$.target_satellite_v0.grasp_primary", "$.target_debris_v0.mass_kg", "$.target_debris_v0.inertia_diag_kgm2", "$.target_debris_v0.grasp_primary"], "unit": "kg; kg*m^2; m after explicit mm conversion", "frame": "native target frame then R_flip into S"},
                    {"source": source_pins["target_satellite_full_tensor"], "pointers": ["$.mass_kg", "$.cg_m", "$.inertia_kg_m2_about_com", "$.features.grasp_points_mm"], "unit": "kg; m; kg*m^2; mm converted exactly to m", "frame": "target CAD frame then R_flip into S"},
                    {"source": source_pins["target_debris_full_tensor"], "pointers": ["$.mass_kg", "$.cg_m", "$.inertia_kg_m2_about_com", "$.features.grasp_points_mm"], "unit": "kg; m; kg*m^2; mm converted exactly to m", "frame": "target CAD frame then R_flip into S"},
                    {"source": source_pins["contact_scene"], "pointers": ["$.capture.v_app_m_s", "$.capture.constraint_mode", "$.capture.joints_locked_at_capture", "$.contact.model", "$.contact.T_c_ms_nominal", "$.contact.lockup_after_window"], "unit": "m/s; enum; boolean; ms", "frame": "frozen inertial wrench and accepted end-effector approach axis"},
                    {"source": source_pins["e22_config"], "pointers": ["$.scenarios.TARGET_22KG_0P5DPS.{target_key,mass_kg,tumble_dps}", "$.scenarios.TARGET_150KG_3DPS.{target_key,mass_kg,tumble_dps}", "$.physics.tumble_axis_target", "$.physics.target_to_S_rotation_diag", "$.physics.contact_window_ms_nominal", "$.physics.contact_window_shape", "$.physics.contact_lockup", "$.physics.solver", "$.diagnostic_thresholds"], "explicitly_excluded_pointers": ["$.scenarios.*.post_configuration", "$.scenarios.*.target_component"], "unit": "SI except explicitly dps/ms", "frame": "target/S/inertial semantics frozen by each field; post assembly is rebuilt from lane C07 plus the selected target full tensor"},
                ],
                "generated_before_execution_and_hash_pinned": [
                    "new four-lane comparator config",
                    "new comparator harness and output extractor implementation",
                    "independent recompute implementation",
                    "determinism replay implementation",
                    "Python/NumPy/SciPy/platform runtime lock and solver-option manifest",
                    "complete loaded-path/source manifest with no undeclared dynamic imports",
                ],
                "future_manifest_authority_rule": {
                    "may_add": ["comparator executable code", "independent checker code", "runtime/environment locks", "derived outputs and their hashes", "the single selected ODR-GPT-07 Round4 artifact slot after its direct approval"],
                    "authority_bearing_input_rule": "the manifest may reference only the exact frozen common/per-lane source pins and field pointers below; listing a new file never grants physical or numerical authority",
                    "forbidden": "new or broader physical/numerical input, whole-file fallback, wildcard pointer broadening, unit/frame reinterpretation, or a second ROM source without a new versioned Owner decision/addendum",
                    "manifest_relationship": "SUBSET_OF_FROZEN_AUTHORITY_WHITELIST_PLUS_EXECUTABLE_RUNTIME_AND_DERIVED_OUTPUTS__NEVER_AN_AUTHORITY_SUPERSET",
                },
                "LEGACY_R1_SOLAR_SUBSYSTEM_RIGID_COUNTERFACTUAL_COMPARATOR": {
                    "whitelist": ["bridged_C07_retained_non_solar_field_projection", "r1_flex_card_mass_geometry_inertia_projection", "r1_frame_tree.frames.F_L_projection", "r1_frame_tree.frames.F_R_projection"],
                    "blacklist": ["r1_frame_tree.frames.M", "legacy_T_SM", "legacy_24kg_whole_sat", "legacy_1p2kg_adapter", "R2_solar_components", "R2_ROM"],
                },
                "LEGACY_R1_SOLAR_SUBSYSTEM_FLEX_COUNTERFACTUAL_COMPARATOR": {
                    "whitelist": ["LEGACY_R1_SOLAR_SUBSYSTEM_RIGID_COUNTERFACTUAL_COMPARATOR_projection", "r1_flex_card_nominal_EI_projection", "sim11_ffr_panel_Phi_K_B_response_extractor_math_only"],
                    "blacklist": ["sim11_config_loader_full_stack", "sim11_A1_final_state", "legacy_T_SM", "R2_ROM", "R2_solar_components"],
                },
                "R2_RIGID_CURRENT": {
                    "whitelist": ["bridged_C07_current_field_projection"],
                    "blacklist": ["all_R1_mass_geometry_EI_Mqq_root_pose_and_state"],
                },
                "R2_SOLAR_FLEX_CURRENT": {
                    "whitelist": ["R2_RIGID_CURRENT_projection", "final_ODR_GPT_07_approved_Round4_ROM_and_validity_artifact_hashes"],
                    "blacklist": ["all_R1_mass_geometry_EI_Mqq_root_pose_and_state", "current_failed_ROM5_for_G17_credit"],
                },
                "per_lane_authority_field_map": {
                    "LEGACY_R1_SOLAR_SUBSYSTEM_RIGID_COUNTERFACTUAL_COMPARATOR": [
                        {"source": source_pins["bridged_mass"], "pointers": ["$.configurations[configuration_id=C07].composition_candidate[component_id in {bus_primary_structure,b601_complete_arm_including_gripper_urdf_links,m3r_stage_a_plus_stage_b_budget_envelope,spacecraft_load_bridge_candidate}].{mass_kg,com_S_m,inertia_about_own_com_S_kg_m2}"], "unit": "kg; m; kg*m^2", "frame": "S"},
                        {"source": source_pins["r1_flex_card"], "pointers": ["$.geometry.{span_L_m,chord_b_m,thickness_t_m}", "$.mass.{m_panel_kg,mu_kg_per_m,I_own_com_kgm2}"], "unit": "m; kg; kg/m; kg*m^2", "frame": "native R1 wing frame with explicit S placement"},
                        {"source": source_pins["r1_frame_tree"], "pointers": ["$.frames.F_L.{parent,origin_mm,axes}", "$.frames.F_R.{parent,origin_mm,axes}"], "unit": "mm converted exactly to m; axis enums", "frame": "S parent, F_L/F_R children"},
                    ],
                    "LEGACY_R1_SOLAR_SUBSYSTEM_FLEX_COUNTERFACTUAL_COMPARATOR": [
                        {"inherits_exact_map_from": "LEGACY_R1_SOLAR_SUBSYSTEM_RIGID_COUNTERFACTUAL_COMPARATOR"},
                        {"source": source_pins["r1_flex_card"], "pointers": ["$.stiffness.cases.nominal.EI_Nm2"], "unit": "N*m^2", "frame": "per-wing Euler-Bernoulli local deploy coordinate"},
                        {"source": source_pins["sim11_ffr_panel"], "pointers": ["FFRPanel.Phi", "FFRPanel.K", "FFRPanel.B_t", "FFRPanel.B_r", "FFRPanel.tip_deflection", "FFRPanel.strain_energy", "FFRPanel.modal_energy"], "unit": "mass-normalized modal SI", "frame": "F_L/F_R mapped to S; gross Mbb excluded"},
                    ],
                    "R2_RIGID_CURRENT": [
                        {"source": source_pins["bridged_mass"], "pointers": ["$.configurations[configuration_id=C07].composition_candidate[*].{component_id,mass_kg,com_S_m,inertia_about_own_com_S_kg_m2}"], "unit": "id; kg; m; kg*m^2", "frame": "S"},
                    ],
                    "R2_SOLAR_FLEX_CURRENT": [
                        {"inherits_exact_map_from": "R2_RIGID_CURRENT"},
                        {"future_source_slot": "ODR_GPT_07_APPROVED_ROUND4_FINAL_R2_ROM", "path_and_sha256": "NON_NULL_AND_HASH_PINNED_BEFORE_RUN", "pointers": ["$.per_wing.{Mbb,M_bq,Mqq,K,C,Phi,response_operators,basis_identity}", "$.validity.{corners,claimed_discrete_windows,thresholds}"], "unit": "SI with field-level units in the Round4 schema", "frame": "LEFT/RIGHT root frames and S coupling exactly as the approved Round4 contract"},
                    ],
                },
                "fingerprint_semantics": {
                    "production_file_integrity": "verify every source-file SHA before fixture construction and never mutate production files",
                    "negative_control_fixture": "apply mutations only to an in-memory deep copy made after production hashes pass",
                    "lane_input_fingerprint": "SHA-256 of canonical JSON containing only the exact authority-bearing fields consumed by that lane plus common/lane executable and runtime-manifest hashes",
                    "canonical_JSON": "UTF-8; sorted keys; no NaN/Inf; SI units; numeric type and array shape retained",
                    "whole_file_SHA_role": "separate immutable production-integrity evidence; not the negative-control lane projection fingerprint",
                    "intended_lane_guard": "every mutation must change every intended affected-lane projection fingerprint; an unchanged intended fingerprint is FAIL_INPUT_NOT_CONSUMED",
                },
                "hard_rule": "any consumed authority-bearing field outside common_authority_field_map_all_lanes plus that lane's per_lane_authority_field_map, any whole-file/wildcard fallback, any executable/runtime artifact outside the frozen executable list, or anything inside a blacklist is a machine FAIL; the generated manifest records these permissions but cannot expand them",
            },
            "mandatory_isolation_negative_controls": [
                {"id": "ISO-R1-TO-R2", "mutation": "on hash-verified in-memory fixtures, mutate R1 mass/EI/Mqq +1 percent and F_L/F_R root component +1 mm one at a time", "intended_projection_effect": "R1 mass/root changes both R1 lane fingerprints; EI/Mqq changes R1 flex only; each intended fingerprint must change", "required_non_target_effect": "both R2 lane projection fingerprints and deterministic physics outputs bitwise identical"},
                {"id": "ISO-R2-TO-R1", "mutation": "on hash-verified in-memory fixtures, mutate R2 solar mass, active ROM eigenvalue, or one bridged-C07 solar com_S_m component by +1 percent or +1 mm one at a time", "intended_projection_effect": "R2 solar mass/COM changes both R2 lane fingerprints or makes the pinned flex artifact stale; ROM eigenvalue changes R2 flex only; each intended fingerprint must change or hard-reject as registered", "required_non_target_effect": "both R1 lane projection fingerprints and deterministic physics outputs bitwise identical"},
                {"id": "ISO-FRAME", "mutation": "attempt read of frame_tree.frames.M or legacy T_SM", "required": "hard rejection before assembly"},
                {"id": "ISO-STATE", "mutation": "seed any lane from another lane final modal state", "required": "hard rejection; every canonical case constructs a new object with exact zero modal initial state"},
                {"id": "ISO-MANIFEST", "mutation": "remove a per-lane source hash or reuse a mutable model object", "required": "hard rejection"},
            ],
            "mutation_consumption_witness_contract": {
                "purpose": "prove that a mutated whitelisted field is consumed by assembly and by the solver, not merely copied into a fingerprint",
                "required_artifacts_per_mutation_and_lane": [
                    "for SOURCE_FIELD_MUTATION: instrumented field-read trace with source SHA, exact pointer, canonical value hash, reader function and lane/case id; for DERIVED_OPERATOR_INJECTION: assembly-injection trace with baseline operator hash, exact index/slice, injected value hash and no source-authority effect",
                    "before/after hashes, shapes, units and max-absolute deltas for every assembled Mbb/M_bq/Mqq/K/C/ROM/root-transform object named by the expected-effect matrix",
                    "solver-constructor input manifest whose operator hashes exactly equal the assembled-operator hashes",
                    "full deterministic state-history hash and registered output hash before/after",
                ],
                "changed_rule": "every object marked CHANGED must have a different hash and max_abs_delta > 0; every object marked BITWISE_STABLE must retain identical bytes/hash; NUMERICALLY_STABLE_IDENTITY_LEQ_1E_12 permits roundoff-only hash change but requires both matrices within 1e-12 of identity and before/after max_abs_delta <=1e-12",
                "solver_consumption_rule": "for each successfully executed intended lane, the full state-history hash must change; unchanged history is FAIL_SOLVER_DID_NOT_CONSUME_MUTATED_OPERATOR",
                "hard_rejection_rule": "a fail-closed stale/inconsistent-input rejection is allowed only where the expected-effect matrix says REBUILD_OR_HARD_REJECT; the rejection must cite the mutated pointer and dependency trace",
                "expected_effect_matrix": [
                    {"mutation": "R1_wing_mass_plus_1_percent", "mutation_class": "SOURCE_FIELD_MUTATION", "exact_source_pointers_and_operation": "multiply together by exactly 1.01: $.mass.m_panel_kg, $.mass.mu_kg_per_m and each $.mass.I_own_com_kgm2 component; hold geometry and EI fixed", "R1_rigid": {"Mbb": "CHANGED", "state_history": "CHANGED"}, "R1_flex": {"Mbb": "CHANGED", "M_bq": "CHANGED", "Phi": "CHANGED", "K": "CHANGED", "Mqq": "NUMERICALLY_STABLE_IDENTITY_LEQ_1E_12", "state_history": "CHANGED"}, "R2_rigid": "BITWISE_STABLE", "R2_flex": "BITWISE_STABLE"},
                    {"mutation": "R1_nominal_EI_plus_1_percent", "mutation_class": "SOURCE_FIELD_MUTATION", "exact_source_pointers_and_operation": "multiply $.stiffness.cases.nominal.EI_Nm2 by exactly 1.01 only", "R1_rigid": "BITWISE_STABLE", "R1_flex": {"K_and_frequency": "CHANGED", "Mbb_Mqq_Phi_B": "BITWISE_STABLE", "state_history": "CHANGED"}, "R2_rigid": "BITWISE_STABLE", "R2_flex": "BITWISE_STABLE"},
                    {"mutation": "R1_active_mode_Mqq_plus_1_percent", "mutation_class": "DERIVED_OPERATOR_INJECTION", "exact_injection": "after baseline R1-flex assembly and before solver construction, multiply one deterministically selected excited canonical-mode diagonal of Mqq by exactly 1.01; record the selected mode and preserve SPD", "source_authority_effect": "NONE_TEST_FIXTURE_ONLY", "R1_rigid": "BITWISE_STABLE", "R1_flex": {"Mqq": "CHANGED", "state_history": "CHANGED"}, "R2_rigid": "BITWISE_STABLE", "R2_flex": "BITWISE_STABLE"},
                    {"mutation": "R1_F_L_or_F_R_root_component_plus_1mm", "mutation_class": "SOURCE_FIELD_MUTATION", "exact_source_pointers_and_operation": "add exactly 1.0 mm to one registered component of $.frames.F_L.origin_mm or $.frames.F_R.origin_mm per subcase", "R1_rigid": {"Mbb": "CHANGED", "root_transform": "CHANGED", "state_history": "CHANGED"}, "R1_flex": {"Mbb": "CHANGED", "M_bq": "CHANGED", "root_transform": "CHANGED", "K_Mqq": "BITWISE_STABLE", "state_history": "CHANGED"}, "R2_rigid": "BITWISE_STABLE", "R2_flex": "BITWISE_STABLE"},
                    {"mutation": "R2_solar_mass_plus_1_percent", "mutation_class": "SOURCE_FIELD_MUTATION", "exact_source_pointers_and_operation": "multiply mass and own inertia fields together by exactly 1.01 for one selected R2 solar component in bridged C07; hold its CG fixed", "R1_rigid": "BITWISE_STABLE", "R1_flex": "BITWISE_STABLE", "R2_rigid": {"Mbb": "CHANGED", "state_history": "CHANGED"}, "R2_flex": "REBUILD_OR_HARD_REJECT_STALE_ROUND4"},
                    {"mutation": "R2_active_ROM_eigenvalue_plus_1_percent", "mutation_class": "DERIVED_OPERATOR_INJECTION", "exact_injection": "after baseline R2-flex assembly and before solver construction, multiply one deterministically selected excited Round4 eigenvalue by exactly 1.01 and rebuild its K entry; record mode identity and preserve SPD", "source_authority_effect": "NONE_TEST_FIXTURE_ONLY", "R1_rigid": "BITWISE_STABLE", "R1_flex": "BITWISE_STABLE", "R2_rigid": "BITWISE_STABLE", "R2_flex": {"K_or_ROM_operator": "CHANGED", "state_history": "CHANGED"}},
                    {"mutation": "R2_solar_C07_com_component_plus_1mm", "mutation_class": "SOURCE_FIELD_MUTATION", "exact_source_pointers_and_operation": "for one selected solar_array_r2_left/right row in $.configurations[configuration_id=C07].composition_candidate, add exactly 0.001 m to one $.com_S_m[k] component per subcase; mass and own inertia remain fixed", "R1_rigid": "BITWISE_STABLE", "R1_flex": "BITWISE_STABLE", "R2_rigid": {"Mbb": "CHANGED", "component_com_S_m": "CHANGED", "state_history": "CHANGED"}, "R2_flex": "REBUILD_OR_HARD_REJECT_STALE_ROUND4"},
                ],
                "pass_logic": "ALL_REQUIRED_ARTIFACTS_AND_ALL_EXPECTED_EFFECTS_PASS_FOR_EVERY_MUTATION__EMPTY_SET_FAIL",
            },
            "assembly_invariants": [
                "R1 rigid/flex Mbb elementwise identical",
                "R2 rigid/flex Mbb elementwise identical",
                "mass, CG and full inertia reconstructed with no null-to-zero",
                "SPD, Schur SPD, frame consistency and no solar double-counting",
            ],
            "R1_mode_convergence_contract": {
                "canonical_modes_per_wing": 5,
                "nested_witnesses_per_wing": [3, 4, 5],
                "pairwise_comparisons": ["m3_to_m4", "m4_to_m5"],
                "required_scenarios": ["TARGET_22KG_0P5DPS", "TARGET_150KG_3DPS"],
                "required_wings": ["LEFT", "RIGHT"],
                "per_wing_metrics": ["tip_max_abs_m", "root_moment_max_abs_N_m", "strain_energy_max_J"],
                "system_metrics": ["total_energy_max_J"],
                "indexing": "per-wing metrics are evaluated for each LEFT/RIGHT wing; system metrics are evaluated once per scenario and comparison, never duplicated by wing",
                "extractor_semantics": {
                    "tip_max_abs_m": "max(abs(tip transverse deflection))",
                    "root_moment_max_abs_N_m": "max(abs(EI times root curvature))",
                    "strain_energy_max_J": "max(nonnegative per-wing strain energy)",
                    "total_energy_max_J": "max(nonnegative whole coupled-system mechanical energy under the frozen ledger definition)",
                },
                "relative_formula": "abs(peak_hi-peak_lo)/max(abs(peak_hi),denominator_floor_for_metric)",
                "denominator_floor_by_metric": {
                    "tip_max_abs_m": {"value": 1.0e-14, "unit": "m"},
                    "root_moment_max_abs_N_m": {"value": 1.0e-14, "unit": "N*m"},
                    "strain_energy_max_J": {"value": 1.0e-14, "unit": "J"},
                    "total_energy_max_J": {"value": 1.0e-14, "unit": "J"},
                },
                "comparison_operator": "LEQ",
                "relative_limit": 0.01,
                "contact_samples_including_endpoints": 401,
                "post_window_s": 40.0,
                "post_samples_including_endpoints": 40001,
                "peak_extractor": {
                    "rule": "MAX_OVER_ENDPOINTS_CONTACT_BOUNDARY_AND_ALL_DENSE_OUTPUT_STATIONARY_POINTS",
                    "primary_bracketing": {"contact_samples": 401, "post_samples": 40001},
                    "refined_bracketing": {"contact_samples": 801, "post_samples": 80001},
                    "stationary_point_solver": "bracket derivative sign changes and derivative-near-zero nodes; refine on solver dense output with Brent root xtol_s=1e-12",
                    "primary_vs_refined_relative_formula": "abs(peak_primary-peak_refined)/max(abs(peak_refined),denominator_floor_for_metric)",
                    "proposed_primary_vs_refined_relative_limit": 1.0e-4,
                    "comparison_operator": "LEQ",
                    "unresolved_extremum": "FAIL_CLOSED",
                },
                "pass_logic": "ALL_PAIRWISE_X_SCENARIO_X_PER_WING_METRICS_AND_ALL_PAIRWISE_X_SCENARIO_X_SYSTEM_METRICS_PASS",
            },
            "frozen_numerical_thresholds": {
                "post_capture_rate_max_dps": 2.0,
                "wheel_small_N_m_s": 0.045,
                "wheel_large_N_m_s": 0.300,
                "solver_cross_relative_max": 0.05,
                "coupled_momentum_relative_max": 1.0e-8,
                "momentum_absolute_max_with_dimension_specific_units": 1.0e-12,
                "attach_momentum_relative_max": 1.0e-10,
                "energy_relative_max": 1.0e-8,
                "spd_min_eigenvalue": 1.0e-12,
                "geometry_alignment_m": 1.0e-9,
                "mass_reconstruction_kg": 1.0e-12,
                "inertia_reconstruction_kg_m2": 1.0e-12,
                "rom_truncation_relative_max": 0.01,
                "source": source_pins["e22_config"],
                "comparison_operators": {
                    "all_upper_bounds": "LEQ",
                    "minimum_SPD_eigenvalue": "STRICT_GT_1E_MINUS_12",
                },
            },
            "solver_and_contact_contract": {
                "contact_window_ms": 20.0,
                "shape": "half_sine_equal_impulse",
                "lockup": True,
                "post_window_s": 40.0,
                "primary_solver": "Radau",
                "cross_solver": "BDF",
                "rtol": 1.0e-10,
                "atol": 1.0e-12,
                "contact_max_step_divisions": 50,
            },
            "numerical_validation": [
                "R1 flex-to-rigid degeneration returns LEGACY_R1_SOLAR_SUBSYSTEM_RIGID_COUNTERFACTUAL_COMPARATOR",
                "R2 flex-to-rigid degeneration returns R2_RIGID_CURRENT",
                "R1 finite-bandwidth m3-to-m4-to-m5 contract passes every registered comparison",
                "R2 consumes the final ODR-GPT-07 approved Round4 ROM hash; ROM5 is preliminary only",
                "linear and angular momentum, energy and lockup ledgers close per case",
                "Radau/BDF cross, independent recompute and deterministic replay cover the new R1 assembly",
                "empty_comparison_set=0 and exactly eight canonical cases",
            ],
            "claim_labels": ["WITHIN_FAMILY_FLEX_EFFECT", "CROSS_FAMILY_DESIGN_DELTA", "NO_CAUSAL_FLEX_ATTRIBUTION"],
        },
        "prohibitions": [
            "no R1 mass, EI, Mqq, root pose, modal state or numeric value enters any R2 object",
            "no R2 two-wing 1.56 kg mass or R2 ROM enters an R1 comparator",
            "no legacy 24 kg whole-satellite ledger, 1.2 kg adapter or legacy T_SM enters the comparator",
            "no sim11 A1 final state or residual vibration becomes a new initial state",
            "no historical 150 kg summary substitutes for the new common-protocol run",
            "no area scaling, mass scaling, interpolation, averaging, null-to-zero or unknown-uncertainty-to-zero",
            "no R1/R2 frame averaging or silent old arm-placement selection",
            "no threshold, mode-order or contact-window tuning to force PASS",
            "no cross-family causal flexibility claim",
            "no in-place overwrite of old FAIL/HOLD or upstream accepted assets",
            "no Owner-accepted, next-stage, handoff, release, flight or qualification semantics",
            "no default consumption by MECH-RL, embodied production or current R2 consumers",
        ],
        "credit_not_inherited": [
            "sim10 gate/classification authority",
            "e15 certification",
            "R2 HF-to-ROM G11",
            "sim11 historical PASS as current-model credit",
            "harness mission coverage",
            "handoff 12-of-12",
            "terminal mechanical release",
            "flight, launcher, manufacturing, qualification or as-built",
            "Route-C, CAD, FEA or production-contact authority",
        ],
        "owner_decision_record": {
            "selected_option": None,
            "directive_verbatim": None,
            "source_path": None,
            "source_sha256": None,
            "effective_date": None,
        },
        "evidence_pins": [
            source_pins[name]
            for name in (
                "owner_attachment", "owner_19", "integration_spec", "e22_config", "e22_gate",
                "e22_authority_audit", "r1_flex_card", "r1_frame_tree", "sim11_model_card",
                "sim11_ffr_panel", "sim11_config_loader", "r2_mass", "bridged_mass",
                "mpi_bridge", "mpi_bridge_gate", "checkpoint_a", "e15_gate",
                "pregrasp_mission_contract", "mission_pose_rebind", "accepted_b601_urdf", "accepted_fk_module",
                "target_ssot", "target_satellite_full_tensor", "target_debris_full_tensor",
                "contact_scene", "contact_window_implementation", "common_capture_axis_source",
                "e22_model", "e22_builder",
            )
        ],
        "approval_record_rule": "This request is immutable and shall never be edited into PASS. A separately issued direct Owner decision must reference this request SHA-256.",
        "self_hash_policy": "SELF_REFERENCE_EXCLUDED; TERMINAL_DECISION_PACK_SHA256.csv pins this request after emission",
    }
    legacy_path = PACKAGE / "LEGACY_R1_COMPARATOR_SEMANTICS_DECISION_REQUEST_V1.yaml"
    dump_yaml(legacy_path, legacy_request)

    graph = {
        "schema": "TERMINAL_CLOSURE_DEPENDENCY_GRAPH_V1",
        "generated_local": generated_local,
        "status": "EXECUTABLE_GRAPH_FROZEN__OWNER_AND_EXTERNAL_INPUTS_PENDING",
        "active_mechanical_design": True,
        "heavy_solver_authorized_now": False,
        "terminal_release_candidate_generated": False,
        "owner_accepted": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "incoming_edge_semantics_default": "ALL_REQUIRED",
        "decision_edge_semantics": "an Owner signature is not sufficient by itself; the selected option and any separately required execution authority must exactly match the edge condition",
        "release_target_if_all_terminal_criteria_close_including_mission_evidence_and_route_c_when_required_by_ODR_GPT_04": "MECHANICAL_ENGINEERING_DESIGN_RELEASED_FOR_OPERATIONAL_DIGITAL_TWIN_AND_EMBODIED_CONTROL_WITH_FLIGHT_QUALIFICATION_HOLD",
        "release_root": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_V1/",
        "decision_branches": {
            "ODR-GPT-07": {
                "A_B_C": "may feed N03 only when the direct Owner record selects that exact option and explicitly authorizes its isolated Round4 component build",
                "D": "TERMINAL_HOLD; no model execution",
                "E": "isolated research-only branch N02E; no edge to the M7 release path",
                "F_G": "revise/reject; no execution edge",
            },
            "ODR-GPT-08": {
                "A": "may feed N05 only when the direct Owner record selects A and explicitly authorizes the bounded four-lane comparator run",
                "B": "feed N04B scope-change contract reissue only; old E22 G17 remains FAIL and no comparator credit is fabricated",
                "C": "TERMINAL_HOLD under the current same-scope requirement",
                "D_E": "revise/reject; no execution edge",
            },
        },
        "nodes": [
            {"id": "N01_M4_INHERITANCE", "status": "COMPLETE_SCOPED", "class": "FROZEN_BASELINE", "action": "inherit; do not rebuild"},
            {"id": "N02_P2_OWNER_DECISION", "status": "PENDING", "class": "OWNER_AUTHORITY", "request": p2_path.name},
            {"id": "N02E_P2_NONMODAL_RESEARCH", "status": "NOT_AUTHORIZED", "class": "ISOLATED_RESEARCH_ONLY", "release_path": False},
            {"id": "N03_ROUND4_P2_COMPONENT", "status": "NOT_AUTHORIZED", "class": "MODEL_BUILD", "join_policy": "ALL_REQUIRED"},
            {"id": "N04_G17_OWNER_DECISION", "status": "PENDING", "class": "OWNER_AUTHORITY", "request": legacy_path.name},
            {"id": "N04B_G17_SCOPE_CHANGE_CONTRACT_REISSUE", "status": "NOT_AUTHORIZED", "class": "CONTRACT_CHANGE", "old_G17_disposition": "PRESERVE_FAIL"},
            {"id": "N05_R1_COMPARATOR_PREP", "status": "NOT_AUTHORIZED", "class": "COUNTERFACTUAL_ASSEMBLY_AND_NEGATIVE_CONTROLS"},
            {"id": "N05B_FOUR_LANE_COMPARATOR", "status": "WAIT_ROUND4_AND_R1_PREP", "class": "COUPLED_DIAGNOSTIC", "join_policy": "ALL_REQUIRED"},
            {"id": "N05C_G17_RESOLUTION_GATE", "status": "WAIT_OWNER_BRANCH", "class": "GATE", "join_policy": "ONE_OF_MUTUALLY_EXCLUSIVE", "eligible_predecessors": ["N05B_FOUR_LANE_COMPARATOR", "N04B_G17_SCOPE_CHANGE_CONTRACT_REISSUE"]},
            {"id": "N06_E22_V2_OR_E23", "status": "NOT_AUTHORIZED", "class": "COUPLED_GATE", "join_policy": "ALL_REQUIRED"},
            {"id": "N07_E15_R2_RECERT", "status": "WAIT_UPSTREAM", "class": "CROSS_SOLVER_GATE"},
            {"id": "N08_A07_A09_TECHNICAL_SUBGATE_REISSUE", "status": "WAIT_UPSTREAM", "class": "DERIVED_TECHNICAL_SUBGATE", "scope": "A07-A09 only; does not alter or PASS the complete Checkpoint-A"},
            {"id": "N09_ROUTE_C_PHYSICAL_INPUTS", "status": "PENDING_EXTERNAL", "class": "TRACEABLE_PHYSICAL_DATA", "fields": "0/13 non-null"},
            {"id": "N10_CHECKPOINT_B_RERUN", "status": "HOLD", "class": "CHECKPOINT", "current": "2/8 admission PASS; CAD false"},
            {"id": "N11_ROUTE_C_CAD_AND_SWEEP", "status": "PROHIBITED", "class": "CAD_AND_HARNESS"},
            {"id": "N11B_RATED_MISSION_ENVELOPE_PROOF", "status": "FALSIFIED_TERMINAL_FROZEN", "class": "FROZEN_NEGATIVE_BRANCH_EVIDENCE", "current": "registered evidence is 0/10 mandatory states SAFE, 0/8 trajectories released and Mission Coverage FAIL; Route-B reopening is NONE_PERMITTED", "evidence": source_pins["odr_gpt04_falsifier_gate"], "release_path": False, "reopen_allowed": False, "global_q_no_go_claim": False, "reactivation_rule": "NONE for frozen Route-B; any new centerline/predicate requires separate direct Owner authorization, a new ECR and a new graph version"},
            {"id": "N10C_A11_ROUTE_C_OR_DEFERMENT_RESOLUTION", "status": "WAIT_ROUTE_C", "class": "CHECKPOINT_CRITERION_RESOLUTION", "legacy_id_note": "ID retained for history; current eligible path is Route-C only", "join_policy": "ALL_REQUIRED", "eligible_predecessors": ["N10_CHECKPOINT_B_RERUN"], "current_eligible_path": "ROUTE_C_ONLY"},
            {"id": "N12_MISSION_HARNESS_GATE", "status": "FAIL", "class": "MISSION_GATE", "current": "0/10 key states SAFE; 0/8 segments released", "join_policy": "ALL_REQUIRED", "eligible_predecessors": ["N11_ROUTE_C_CAD_AND_SWEEP"]},
            {"id": "N13_INTERFACE_CONTRACT_REBIND", "status": "WAIT_UPSTREAM", "class": "DIGITAL_THREAD", "join_policy": "ALL_REQUIRED"},
            {"id": "N14_SIM13_LOADER_RUNTIME_GATE", "status": "INVALIDATED", "class": "DOWNSTREAM_CONSUMER"},
            {"id": "N15_HANDOFF", "status": "HOLD_11_OF_12_G12", "class": "HANDOFF_GATE"},
            {"id": "N15B_CHECKPOINT_A_FULL_REISSUE", "status": "WAIT_ALL_A01_A12", "class": "CHECKPOINT", "join_policy": "ALL_REQUIRED", "required_outcome": "12/12 PASS"},
            {"id": "N16_FINAL_RELEASE_CANDIDATE_CM_STAGING", "status": "WAIT_TECHNICAL_CLOSURE", "class": "ASSEMBLY_DRAWING_BOM_RELEASE_STAGING", "join_policy": "ALL_REQUIRED", "scope": "stage release items 00-22; no release credit"},
            {"id": "N17_TERMINAL_RED_TEAM", "status": "NOT_REACHED", "class": "ADVERSARIAL_AUDIT", "required_output": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_V1/23_RED_TEAM/"},
            {"id": "N18_FINDING_FALSIFIER", "status": "NOT_REACHED", "class": "FALSIFIER", "required_output": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_V1/24_FALSIFIER/"},
            {"id": "N19_FINAL_SEVEN_GATE_AGGREGATION", "status": "NOT_REACHED", "class": "TERMINAL_GATE_AGGREGATION", "required_gates": ["TMG-1", "TMG-2", "TMG-3", "TMG-4", "TMG-5", "TMG-6", "TMG-7"]},
            {"id": "N20_RELEASE_MANIFEST_HASH_AUDIT", "status": "NOT_REACHED", "class": "CONFIGURATION_MANAGEMENT", "required_output": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_V1/25_RELEASE_SHA256.csv"},
            {"id": "N21_CHECKPOINT_C_TERMINAL", "status": "NOT_REACHED", "class": "TERMINAL_GATE"},
        ],
        "edges": [
            {"from": "N02_P2_OWNER_DECISION", "to": "N03_ROUND4_P2_COMPONENT", "condition": "direct Owner record selects exactly P2 Option A, B or C AND explicitly authorizes the selected isolated Round4 component build"},
            {"from": "N02_P2_OWNER_DECISION", "to": "N02E_P2_NONMODAL_RESEARCH", "condition": "direct Owner record selects exactly P2 Option E AND a new isolated research contract is issued; this node has no outgoing release edge"},
            {"from": "N04_G17_OWNER_DECISION", "to": "N05_R1_COMPARATOR_PREP", "condition": "direct Owner record selects exactly A_FOUR_LANE_PROTOCOL_MATCHED_COMPARATOR AND explicitly authorizes the bounded comparator run"},
            {"from": "N04_G17_OWNER_DECISION", "to": "N04B_G17_SCOPE_CHANGE_CONTRACT_REISSUE", "condition": "direct Owner record selects exactly B_REMOVE_LEGACY_NUMERICAL_G17_RETAIN_HISTORICAL_NARRATIVE AND a versioned scope-change contract is issued"},
            {"from": "N05_R1_COMPARATOR_PREP", "to": "N05B_FOUR_LANE_COMPARATOR", "condition": "R1 assembly, source isolation and negative controls PASS"},
            {"from": "N03_ROUND4_P2_COMPONENT", "to": "N05B_FOUR_LANE_COMPARATOR", "condition": "final ODR-GPT-07-approved Round4 R2 ROM hash and component Gate PASS available"},
            {"from": "N05B_FOUR_LANE_COMPARATOR", "to": "N05C_G17_RESOLUTION_GATE", "condition": "Option-A four-lane two-scenario protocol completeness Gate PASS"},
            {"from": "N04B_G17_SCOPE_CHANGE_CONTRACT_REISSUE", "to": "N05C_G17_RESOLUTION_GATE", "condition": "Option-B new scope Gate PASS; old E22-V1 G17 remains FAIL and is not relabelled"},
            {"from": "N03_ROUND4_P2_COMPONENT", "to": "N06_E22_V2_OR_E23", "condition": "Round4 component, independent recompute, determinism, negative controls and red-team PASS"},
            {"from": "N05C_G17_RESOLUTION_GATE", "to": "N06_E22_V2_OR_E23", "condition": "exactly one mutually exclusive G17-resolution branch PASS"},
            {"from": "N06_E22_V2_OR_E23", "to": "N07_E15_R2_RECERT", "condition": "G11 and G17 closed without weakened criteria"},
            {"from": "N07_E15_R2_RECERT", "to": "N08_A07_A09_TECHNICAL_SUBGATE_REISSUE", "condition": "A07, A08 and A09 each PASS with versioned evidence; complete Checkpoint-A remains unchanged"},
            {"from": "N09_ROUTE_C_PHYSICAL_INPUTS", "to": "N10_CHECKPOINT_B_RERUN", "condition": "P01-P13 traceable values, units, uncertainty and authority"},
            {"from": "N10_CHECKPOINT_B_RERUN", "to": "N11_ROUTE_C_CAD_AND_SWEEP", "condition": "8/8 admission PASS plus separately recorded CAD authorization"},
            {"from": "N11_ROUTE_C_CAD_AND_SWEEP", "to": "N12_MISSION_HARNESS_GATE", "condition": "full required trajectory sweep and rated-envelope proof"},
            {"from": "N10_CHECKPOINT_B_RERUN", "to": "N10C_A11_ROUTE_C_OR_DEFERMENT_RESOLUTION", "condition": "Route-C C2 registry and CAD admission PASS"},
            {"from": "N08_A07_A09_TECHNICAL_SUBGATE_REISSUE", "to": "N13_INTERFACE_CONTRACT_REBIND", "condition": "A07-A09 technical subgate PASS"},
            {"from": "N12_MISSION_HARNESS_GATE", "to": "N13_INTERFACE_CONTRACT_REBIND", "condition": "mission harness coverage PASS under PASS_FULL_RANGE or PASS_HARNESS_RATED_MISSION_ENVELOPE; no unsafe required trajectory"},
            {"from": "N13_INTERFACE_CONTRACT_REBIND", "to": "N14_SIM13_LOADER_RUNTIME_GATE", "condition": "versioned interface and fail-closed runtime harness field"},
            {"from": "N14_SIM13_LOADER_RUNTIME_GATE", "to": "N15_HANDOFF", "condition": "independent negative controls and production-binding audit PASS"},
            {"from": "N08_A07_A09_TECHNICAL_SUBGATE_REISSUE", "to": "N15B_CHECKPOINT_A_FULL_REISSUE", "condition": "A07-A09 technical results PASS"},
            {"from": "N10C_A11_ROUTE_C_OR_DEFERMENT_RESOLUTION", "to": "N15B_CHECKPOINT_A_FULL_REISSUE", "condition": "A11 is resolved by Route-C C2 registry and CAD admission PASS; the frozen Route-B ODR-GPT-04 branch is terminal-negative and cannot satisfy A11"},
            {"from": "N12_MISSION_HARNESS_GATE", "to": "N15B_CHECKPOINT_A_FULL_REISSUE", "condition": "A10 mission harness coverage PASS"},
            {"from": "N15_HANDOFF", "to": "N15B_CHECKPOINT_A_FULL_REISSUE", "condition": "A12 handoff 12/12 PASS"},
            {"from": "N15B_CHECKPOINT_A_FULL_REISSUE", "to": "N16_FINAL_RELEASE_CANDIDATE_CM_STAGING", "condition": "complete Checkpoint-A A01-A12 is independently refreshed and 12/12 PASS"},
            {"from": "N01_M4_INHERITANCE", "to": "N16_FINAL_RELEASE_CANDIDATE_CM_STAGING", "condition": "inherit accepted M4 geometry and schemas; reissue only controlled R2 deltas"},
            {"from": "N16_FINAL_RELEASE_CANDIDATE_CM_STAGING", "to": "N17_TERMINAL_RED_TEAM", "condition": "unified R2 candidate items 00-22, nine-config collision, drawings/BOM and hashes are staged with no release credit"},
            {"from": "N17_TERMINAL_RED_TEAM", "to": "N18_FINDING_FALSIFIER", "condition": "full-scope adversarial findings register emitted over Route-C, harness, flexibility, interfaces, Sim13 and final CM candidate"},
            {"from": "N18_FINDING_FALSIFIER", "to": "N19_FINAL_SEVEN_GATE_AGGREGATION", "condition": "every finding has an executable falsifier and HIGH=0; unresolved finding is HOLD"},
            {"from": "N19_FINAL_SEVEN_GATE_AGGREGATION", "to": "N20_RELEASE_MANIFEST_HASH_AUDIT", "condition": "TMG-1 through TMG-7 PASS; internal design HOLD=0; hash mismatch=0; unexplained interference=0; empty comparison set=0"},
            {"from": "N20_RELEASE_MANIFEST_HASH_AUDIT", "to": "N21_CHECKPOINT_C_TERMINAL", "condition": "complete items 00-25 exist; 25_RELEASE_SHA256.csv validates every release artifact and self-reference policy"},
        ],
        "parallelizable_after_authority": [
            ["N03_ROUND4_P2_COMPONENT", "N05_R1_COMPARATOR_PREP", "N09_ROUTE_C_PHYSICAL_INPUTS"],
            ["N16_FINAL_RELEASE_CANDIDATE_CM_STAGING"],
        ],
        "current_internal_owner_decisions_needed": ["ODR-GPT-07", "ODR-GPT-08"],
        "current_harness_resolution_needed": "close Route-C P01-P13, Checkpoint-B, separate CAD authority, new physical sweep and mandatory mission coverage; the current frozen Route-B ODR-GPT-04 path is machine-falsified",
        "current_route_c_physical_inputs_if_route_c_required": "Route-C P01-P13 controlled registry closure (required on the current graph)",
        "nonclaims": [
            "this graph does not authorize any currently blocked node",
            "flight qualification, manufacturing release and as-built correlation remain HOLD after the design-release target",
            "five discrete windows do not establish a continuous 5-to-100ms validity interval",
            "the frozen Route-B no-go does not prove every external harness topology physically impossible",
            "no new Route-B2 or alternate-centerline release edge exists without a separate Owner-authorized ECR and graph revision",
        ],
    }
    graph_path = PACKAGE / "TERMINAL_CLOSURE_DEPENDENCY_GRAPH_V1.yaml"
    dump_yaml(graph_path, graph)

    gate = {
        "schema": "TERMINAL_DECISION_PACK_GATE_V1",
        "generated_local": generated_local,
        "generator": "GPT mechanical chief and multi-agent Loop Engineering integrator",
        "scope": "decision-package integrity and terminal dependency control only",
        "outcome": "READY_FOR_OWNER_DECISIONS_WITH_FROZEN_ROUTE_B_BRANCH_FALSIFIED_AND_ROUTE_C_HOLD",
        "technical_verdict": "DECISION_PACK_COMPLETE__ODR_GPT_07_AND_08_PENDING__MISSION_HARNESS_FAIL__FROZEN_ROUTE_B_ODR_GPT_04_BRANCH_FALSIFIED__ROUTE_C_13_OF_13_HOLD__NO_EXECUTION_OR_RELEASE_AUTHORITY",
        "integrity_criteria": [
            {"id": "TDP-01", "name": "all source files exist and are hash-pinned", "pass": True},
            {"id": "TDP-02", "name": "M4 scoped release preserved and no M3-M6 rebuild requested", "pass": True},
            {"id": "TDP-03", "name": "M4-to-M7 L01-L08 inheritance/gap matrix emitted", "pass": True},
            {"id": "TDP-04", "name": "Checkpoint-A HOLD 6/12 preserved", "pass": True},
            {"id": "TDP-05", "name": "P2 11D/7D/6D evidence and fail-closed basis/window/solver contract emitted without pre-awarded PASS", "pass": True},
            {"id": "TDP-06", "name": "ODR-GPT-07 request remains unselected and unauthorized", "pass": True},
            {"id": "TDP-07", "name": "Legacy R1 authority conflict, executable mass ledger and bidirectional four-lane isolation guards preserved", "pass": True},
            {"id": "TDP-08", "name": "ODR-GPT-08 request remains unselected and unauthorized", "pass": True},
            {"id": "TDP-09", "name": "Checkpoint-B HOLD and Route-C CAD prohibition preserved", "pass": True},
            {"id": "TDP-10", "name": "e15 REPEAT, handoff G12 and Sim13 invalidation preserved", "pass": True},
            {"id": "TDP-11", "name": "terminal dependency graph is fail-closed", "pass": True},
            {"id": "TDP-12", "name": "Owner acceptance, next-stage authority and release credit remain false", "pass": True},
            {"id": "TDP-13", "name": "frozen Route-B ODR-GPT-04 branch is closed by a hash-pinned 18/18 falsifier with 18/18 negative controls and no release edge; no global-q claim is made", "pass": True},
        ],
        "integrity_summary": {"passed": 13, "total": 13, "failed": []},
        "decision_requests": [
            {"id": "ODR-GPT-07", "file": p2_path.name, "status": "PENDING_OWNER_DECISION", "recommended_option": "A_11D_FIVE_REGISTERED_WINDOWS_CANDIDATE"},
            {"id": "ODR-GPT-08", "file": legacy_path.name, "status": "PENDING_OWNER_DECISION", "recommended_option": "A_FOUR_LANE_PROTOCOL_MATCHED_COMPARATOR"},
        ],
        "checkpoint_state": {
            "A_R2_FULL_FLEX": {"outcome": "HOLD", "criteria": "6/12", "E22": "16/18; G11/G17 fail", "e15": "REPEAT_ANCF_CERTIFICATION"},
            "B_ROUTE_C_C2": {"outcome": "HOLD", "integrity": "8/8", "admission": "2/8", "registry": "0/13 non-null", "route_c_cad_authorized": False},
            "FROZEN_ROUTE_B_ODR04": {"outcome": "TERMINAL_NEGATIVE_CURRENT_REGISTERED_BRANCH", "deferment_earned": False, "release_edge": False, "global_q_no_go_claim": False},
            "C_TERMINAL_RELEASE": {"reached": False, "candidate_generated": False},
        },
        "current_internal_authority_blockers": ["ODR-GPT-07 P2 dimension/validity ruling", "ODR-GPT-08 Legacy R1 comparator semantics ruling"],
        "current_harness_evidence_blocker": "the frozen Route-B ODR-GPT-04 branch is machine-falsified; close Route-C P01-P13, Checkpoint-B, separate CAD authority, new physical sweep and mandatory Mission Coverage",
        "allowed_now": [
            "Owner review and separate issuance of ODR-GPT-07 and ODR-GPT-08",
            "receive and source-control Route-C RFI-E/F/G responses",
            "obtain the five Owner input classes, supplier samples and exact installed-construction measurements required by the Route-C registry",
            "upgrade P01-P13 only with value, unit, tolerance or uncertainty, traceable source and authority class; null remains HOLD",
            "rerun Checkpoint-B only after the new physical evidence is configuration-controlled",
            "preserve and independently validate the frozen Route-B ODR-GPT-04 terminal-negative evidence",
            "preserve completed M4-M7 and Checkpoint A/B evidence",
        ],
        "prohibited_now": [
            "Round4 ROM or four-lane numerical campaign before separate Owner authorization",
            "Route-C CAD before 8/8 admission PASS and separate CAD authorization",
            "trajectory search, posture rebinding, rate scaling, reopening or relabelling of the frozen Route-B as an ODR-GPT-04 closure path",
            "in-place modification of Round3, E22-V1, Checkpoint-A or historical sim11",
            "production contact/RL, terminal release, qualification or flight claim",
        ],
        "source_pins": list(source_pins.values()),
        "owner_accepted": False,
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
        "terminal_release_candidate_generated": False,
        "self_hash_policy": "SELF_REFERENCE_EXCLUDED; TERMINAL_DECISION_PACK_SHA256.csv pins this Gate after emission",
    }
    gate_path = PACKAGE / "TERMINAL_DECISION_PACK_GATE_V1.json"
    gate_path.write_text(json.dumps(gate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    receipt = f"""# 机械终局决策包 V1 收据

生成时间：{generated_local}

## 裁决

- 决策包完整性：13/13 PASS。
- Checkpoint A：HOLD（6/12；E22 16/18，G11/G17 失败；e15=REPEAT_ANCF_CERTIFICATION）。
- Checkpoint B：HOLD（完整性 8/8；C2 准入 2/8；P01–P13 为 0/13 非空；Route-C CAD 禁止）。
- Checkpoint C：未到达，未生成机械终局 Release 候选。

## 两项待 Owner 独立落字的内部决策

1. ODR-GPT-07：推荐 A_11D_FIVE_REGISTERED_WINDOWS_CANDIDATE。该 11D 基底只证明名义诊断输入在 5/10/20/50/100 ms 五个离散注册窗满足当前 1% 六指标分数，最坏 0.742604%@5 ms；不证明连续 5–100 ms 区间，也不预授 E22/e15 PASS。
2. ODR-GPT-08：推荐 A_FOUR_LANE_PROTOCOL_MATCHED_COMPARATOR。R1 与 R2 各自只在族内做刚/柔因果配对；跨族只能报告设计族差异。

## 外部物理输入

当前冻结 Route-B 的 ODR-GPT-04 额定任务包络分支已被机器证伪：当前注册证据为 10 个强制状态 0/10 SAFE、8 条轨迹 0/8 released、Mission Coverage FAIL，同时 Route-B 终局冻结明确 `reopening=NONE_PERMITTED`。该结论不泛化为所有外置线束拓扑物理不可能，也不声称所有 q 均 UNSAFE；圆角裁剪的全域不变量尚未建立。它终止的是当前冻结 Route-B 的合法发布分支。当前闭环必须补齐 Route-C P01–P13 的可追溯物理数据、单位、不确定度及 authority class，达到 Checkpoint-B 8/8 后另取 CAD 授权，再完成新物理路线与全程任务覆盖。任何 null、扫描轴或 LLM 估计均不得转为 CAD 权威。

## 不变声明

M4 的受限数字样机发布继续有效且不重做；当前工作只处理 R2 终局增量。Owner acceptance、next_stage_authorized、release_credit 均为 false。
"""
    receipt_path = PACKAGE / "TERMINAL_DECISION_PACK_RECEIPT_V1.md"
    receipt_path.write_text(receipt, encoding="utf-8", newline="\n")

    output_names = [
        matrix_path.name,
        p2_path.name,
        legacy_path.name,
        graph_path.name,
        gate_path.name,
        receipt_path.name,
        Path(__file__).name,
        "validate_terminal_decision_pack.py",
    ]
    manifest_rows = []
    for name, item in source_pins.items():
        manifest_rows.append({"class": "INPUT", "id": name, "path": item["path"], "bytes": item["bytes"], "sha256": item["sha256"]})
    for name in output_names:
        path = PACKAGE / name
        if not path.is_file():
            raise FileNotFoundError(f"output/script missing before manifest emission: {path}")
        manifest_rows.append({"class": "OUTPUT", "id": name, "path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)})
    manifest_rows.sort(key=lambda row: (row["class"], row["path"]))
    write_csv(PACKAGE / "TERMINAL_DECISION_PACK_SHA256.csv", ["class", "id", "path", "bytes", "sha256"], manifest_rows)


if __name__ == "__main__":
    main()
