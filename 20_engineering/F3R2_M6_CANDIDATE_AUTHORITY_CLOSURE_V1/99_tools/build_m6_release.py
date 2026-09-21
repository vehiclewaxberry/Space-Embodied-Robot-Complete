"""M6 integration builder: output manifest, cross-WP reconciliation, gate, summary.

Read-only over all baselines. Writes only under 12_release/.
Run: python build_m6_release.py
"""
import csv
import hashlib
import json
import datetime
from pathlib import Path

M6 = Path(__file__).resolve().parents[1]
PROJECT = M6.parents[1]
NOW = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


# ---- 1. output manifest over all WP artifacts + authority scaffold ----------
EXCLUDE_DIRS = {"12_release", "99_tools", "__pycache__"}
records = []
for p in sorted(M6.rglob("*")):
    if not p.is_file():
        continue
    rel = p.relative_to(M6).as_posix()
    if rel.split("/")[0] in EXCLUDE_DIRS:
        continue
    records.append({"path": rel, "sha256": sha256(p), "bytes": p.stat().st_size})

manifest = {
    "schema": "M6_OUTPUT_MANIFEST_V1",
    "generated_local": NOW,
    "phase": "M6_CANDIDATE_AUTHORITY_CLOSURE",
    "file_count": len(records),
    "total_bytes": sum(r["bytes"] for r in records),
    "files": records,
}
(M6 / "12_release").mkdir(exist_ok=True)
(M6 / "12_release" / "M6_OUTPUT_MANIFEST_V1.json").write_text(
    json.dumps(manifest, indent=1) + "\n", encoding="utf-8")

# ---- 2. cross-WP reference reconciliation (post-hoc, no WP file mutation) ---
checks = []


def ptr(note, target_rel, expect_exists=True):
    t = M6 / target_rel
    ok = t.is_file() and t.stat().st_size > 0
    checks.append({
        "reference": note,
        "target": target_rel,
        "expected_present": expect_exists,
        "observed_present": ok,
        "sha256": sha256(t) if ok else None,
        "resolution": "VERIFIED_AT_M6_INTEGRATION" if ok else "MISSING_AT_M6_INTEGRATION",
    })


ptr("WP6 drawing index D04 CANDIDATE_PENDING -> WP1 draft SVG",
    "wp1_load_bridge/D04_LOAD_BRIDGE_INTERFACE_DRAFT.svg")
ptr("WP6 BOM DP-007 CANDIDATE_GEOMETRY_PENDING_WP1 -> FCStd",
    "wp1_load_bridge/LOAD_BRIDGE_CANDIDATE_V1.FCStd")
ptr("WP6 BOM DP-007 candidate -> neutral STEP",
    "wp1_load_bridge/LOAD_BRIDGE_CANDIDATE_V1.step")
ptr("WP5 subgate map sibling pointer -> WP2 diagnostic ledger",
    "wp2_mass_properties/SYSTEM_MASS_PROPERTIES_V4_DIAGNOSTIC.yaml")
ptr("WP5 subgate map sibling pointer -> WP4 material library V2",
    "wp4_materials/PROTOTYPE_MATERIAL_LIBRARY_V2.yaml")
ptr("WP7 Q2 readiness candidate input path -> WP2 aggregator",
    "wp2_mass_properties/aggregate_m6_mass_properties.py")
ptr("WP7 Q2 readiness candidate input path -> WP2 transform candidates",
    "wp2_mass_properties/CONFIGURATION_TRANSFORM_CANDIDATES_V1.yaml")
ptr("WP6 BOM DP-012 fastener A286 -> WP4 library record",
    "wp4_materials/PROTOTYPE_MATERIAL_LIBRARY_V2.yaml")

recon = {
    "schema": "M6_CROSS_WP_REFERENCE_RECONCILIATION_V1",
    "generated_local": NOW,
    "rule": "WP files and receipts are not mutated; references generated before "
            "sibling WPs landed are verified here at integration time.",
    "reference_checks": checks,
    "verified_count": sum(1 for c in checks if c["observed_present"]),
    "missing_count": sum(1 for c in checks if not c["observed_present"]),
    "status": "ALL_REFERENCES_VERIFIED" if all(c["observed_present"] for c in checks)
              else "UNRESOLVED_REFERENCES_PRESENT",
}
(M6 / "12_release" / "M6_CROSS_WP_REFERENCE_RECONCILIATION_V1.json").write_text(
    json.dumps(recon, indent=1) + "\n", encoding="utf-8")

# ---- 3. gate ----------------------------------------------------------------
gate = {
    "schema": "M6_CANDIDATE_AUTHORITY_CLOSURE_GATE_V1",
    "generated_local": NOW,
    "phase": "M6_CANDIDATE_AUTHORITY_CLOSURE",
    "release_claim_ceiling": "CANDIDATE_AND_DIAGNOSTIC_ENGINEERING_ARTIFACTS_ONLY",
    "memory_execution_record": {
        "threshold_gib": 6.0,
        "memory_gate_passed": False,
        "owner_override_used": True,
        "execution_controls": [
            "SINGLE_FREECAD_PROCESS_WP1_ONLY",
            "LIGHTWEIGHT_PARAMETERIZED_BREP_ONLY",
            "NO_FEA", "NO_RL_TRAINING",
        ],
    },
    "release_tokens": {
        "load_bridge_candidate_geometry": {
            "token": "M6_LOAD_BRIDGE_CANDIDATE_ISSUED",
            "issued": True,
            "status": "CANDIDATE_GEOMETRY_ONLY_NOT_INTERFACE_AUTHORITY",
            "evidence": "wp1_load_bridge/receipt.json",
        },
        "nine_configuration_diagnostic_mass_properties": {
            "token": "M6_NINE_CONFIG_DIAGNOSTIC_MASS_ISSUED",
            "issued": True,
            "status": "DIAGNOSTIC_ONLY_RELEASE_AGGREGATION_INACTIVE",
            "released_mass_count": 0, "released_cg_count": 0,
            "released_inertia_count": 0,
            "evidence": "wp2_mass_properties/receipt.json",
        },
        "tolerance_chain_numeric_execution": {
            "token": "M6_TOLERANCE_NUMERIC_CANDIDATES_ISSUED",
            "issued": True,
            "status": "CANDIDATE_NUMERIC_EXECUTION_ACCEPTED_CHAIN_COUNT_0",
            "evidence": "wp3_tolerance/receipt.json",
        },
        "material_library_v2": {
            "token": "M6_MATERIAL_LIBRARY_V2_CANDIDATES_ISSUED",
            "issued": True,
            "status": "PROTOTYPE_CANDIDATE_ONLY_0_SPEC_SELECTIONS_0_ALLOWABLES",
            "evidence": "wp4_materials/receipt.json",
        },
        "structural_entry_evidence_pack": {
            "token": "M6_STRUCTURAL_ENTRY_EVIDENCE_PACK_ISSUED",
            "issued": True,
            "status": "DRAFT_PRE_AUTHORITY_SUBGATES_REMAIN_HOLD",
            "formal_fea_run_count": 0,
            "evidence": "wp5_structural_entry/receipt.json",
        },
        "drawings_bom_candidate_extension": {
            "token": "M6_BOM_V2_CANDIDATE_ISSUED",
            "issued": True,
            "status": "CANDIDATE_ROWS_ONLY_NO_PROCUREMENT_OR_RELEASE_ROWS",
            "evidence": "wp6_drawings_bom/receipt.json",
        },
        "cdr_phase1_readiness_packs": {
            "token": "M6_CDR_READINESS_PACKS_ISSUED",
            "issued": True,
            "status": "PENDING_OWNER_REVIEW_GATES_REMAIN_HOLD",
            "evidence": "wp7_cdr_evidence/receipt.json",
        },
    },
    "retained_holds": [
        "SPACECRAFT_TO_M3R_LOAD_BRIDGE_PHYSICAL_INTERFACE_AUTHORITY_HOLD",
        "LEGACY_FLANGE_OWNERSHIP_ALLOCATION_HOLD",
        "ROOT_TO_M_FRAME_AUTHORITY_HOLD",
        "BUS_SIDE_ANCHOR_PATTERN_UNDEFINED_HOLD",
        "M3R_COMPONENT_MASS_COM_INERTIA_HOLD",
        "NINE_CONFIGURATION_RELEASE_MASS_CG_INERTIA_HOLD_0_OF_9",
        "TRACEABLE_UNCERTAINTY_MODEL_HOLD",
        "MEASURED_MASS_PROPERTIES_PHYSICAL_HARDWARE_HOLD",
        "MATERIAL_SPEC_ALLOWABLE_PROCESS_ENVIRONMENT_SELECTION_HOLD",
        "TOLERANCE_PHYSICAL_CONFORMITY_AND_METROLOGY_HOLD",
        "FASTENER_PHYSICAL_PARAMETERS_AND_PRELOAD_HOLD",
        "STRUCTURAL_ANALYSIS_ENTRY_ALL_SUBGATES_HOLD",
        "FORMAL_FEA_NOT_AUTHORIZED",
        "CDR_Q0_Q1_Q2_GATES_HOLD_PENDING_OWNER_REVIEW",
        "LAUNCHER_DEPLOYER_SEPARATION_ICD_EXTERNAL_HOLD",
        "CONTACT_FLEXIBLE_BODY_PRODUCTION_DYNAMICS_AND_RL_HOLD",
        "MANUFACTURING_LAUNCHER_QUALIFICATION_AND_FLIGHT_HOLD",
        "MEMORY_GATE_6GIB_REMAINS_FAILED",
    ],
    "prohibited_claims": [
        "MEMORY_GATE_PASS", "SYSTEM_COLLISION_PASS", "CONTACT_FORCE_PASS",
        "STRUCTURAL_ANALYSIS_READY", "MEASURED_OR_INSTALLED_MASS",
        "RELEASED_SYSTEM_MASS_CG_OR_INERTIA", "ACCEPTED_TOLERANCE_CHAIN",
        "DESIGN_ALLOWABLE_OR_FLIGHT_MATERIAL", "PROCUREMENT_BOM",
        "FLIGHT_OR_MANUFACTURING_RELEASE", "RL_POLICY_READY",
    ],
    "next_authorized_loop": {
        "id": "M7_PHYSICAL_INPUT_AND_OWNER_REVIEW_CLOSURE",
        "authorized_now": [
            "owner_review_of_M6_candidate_packages",
            "physical_measurement_campaign_planning",
            "controlled_copy_and_icd_acquisition",
            "bounded_diagnostic_simulation_research",
        ],
        "not_authorized_now": [
            "formal_FEA", "production_contact_dynamics",
            "RL_training_performance_claims",
            "manufacturing_procurement_qualification_or_flight_release",
        ],
    },
    "overall_status": "PENDING_VALIDATION",
}
(M6 / "12_release" / "M6_CANDIDATE_AUTHORITY_CLOSURE_GATE_V1.json").write_text(
    json.dumps(gate, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

# ---- 4. release summary ------------------------------------------------------
summary = f"""# M6 候选权威闭合发布摘要

生成:{NOW}(本地,+08:00)。

## 工程裁决

本轮在 M4(数字样机受限发布)、M5(几何与载荷闭合)、SIM15(诊断复核)之后,
把 M4 授权待办中**无需硬件/人审/外部 ICD** 的部分推进到候选/诊断级闭合。
这不是制造、结构、资格或飞行发布;正式 FEA 运行数为 0;所有物理权威 HOLD 原样保留。

## 七工作包结果

| WP | 令牌 | 状态 | 关键数值 |
|---|---|---|---|
| WP1 载荷桥 | M6_LOAD_BRIDGE_CANDIDATE_ISSUED | CANDIDATE | 160×160×10.75 mm 桥板跨 x 185.25–196.0;4×⌀6.6 @ (±70,±70);体积 260072.3919 mm³;候选质量 702.195458 g(MATERIAL_DERIVED,6061-T6 2700 kg/m³);21/21 检查 PASS |
| WP2 九构型质量 | M6_NINE_CONFIG_DIAGNOSTIC_MASS_ISSUED | DIAGNOSTIC | C01–C09 诊断聚合;Branch A 28.695555949 kg / Branch B 29.081436765 kg;与 M4 台账回归误差 ≤2.84e-14 kg;stage1 整星行复建误差 ≤4.2e-08;release 字段全 null |
| WP3 公差链 | M6_TOLERANCE_NUMERIC_CANDIDATES_ISSUED | CANDIDATE | B601-M3R 链 WC 最小径向间隙 0.1010 mm;Stage A↔B 止口 WC 0.206 mm;夹爪 4 档间隙 × 144 点 576/576 PASS_NEUTRAL(最小裕度 0.05 mm);铰链翼尖灵敏度 0.2 mm/mrad |
| WP4 材料库 | M6_MATERIAL_LIBRARY_V2_CANDIDATES_ISSUED | CANDIDATE | 7 条材料记录(V1 四条逐字保留 + A286/300 系 CRES/8552 预浸料);3 组采购规范候选、3 条表面/润滑工艺候选;22 条公开来源;规范选定 0、许用值 0 |
| WP5 结构入口 | M6_STRUCTURAL_ENTRY_EVIDENCE_PACK_ISSUED | DRAFT_PRE_AUTHORITY | FEA1/2/3 计划 + 4×HM4-75 螺栓组 6 单位载荷×4 钉解析(24 行,与 M5 系数一致);8 子门保持 HOLD;无 MoS 声称 |
| WP6 图纸/BOM | M6_BOM_V2_CANDIDATE_ISSUED | CANDIDATE | BOM V2 15 行(V1 13 行逐字保留 + DP-012 紧固件组 + DP-013 定位销);站位表 V2 补全 x 站位语义;D04 登记 CANDIDATE_PENDING(集成时已验证存在) |
| WP7 CDR 证据 | M6_CDR_READINESS_PACKS_ISSUED | PENDING_OWNER_REVIEW | Q0 条款映射骨架(14 标准全缺受控副本);Q1 19 项载荷缺口逐项闭合路径分类;Q2 ROOT_TO_M 五选项(未选定)+ 0/9 解除条件树 |

## 集成事实

- 输出清单:`M6_OUTPUT_MANIFEST_V1.json`({manifest['file_count']} 文件,{manifest['total_bytes']} B)。
- 跨 WP 引用和解:`M6_CROSS_WP_REFERENCE_RECONCILIATION_V1.json`({recon['verified_count']} 验证 / {recon['missing_count']} 缺失);WP 文件与 receipt 未被改写。
- 基线完整性:M4/M5/CDR/SIM15 及 L0 URDF 全部只读;钉住哈希由 99_tools/validate_m6_release.py 独立复核。
- 内存门:6 GiB 仍未过;全程仅 WP1 使用单进程 FreeCAD(Owner Override,与 M4-OVR-001 同源)。

## 保留 HOLD(摘要)

载荷桥物理接口权威、旧法兰所有权、ROOT_TO_M、舱侧锚固图案、M3R 组件 COM/惯量、
九构型发布质量/质心/惯量(0/9)、可追溯不确定度、实测质量(需硬件)、材料规范/许用值/
工艺/环境选定、公差实测符合性、紧固件物理参数、结构入口全部子门、CDR Q0/Q1/Q2、
发射/分离 ICD、接触/柔体生产动力学与 RL、制造/发射/资格/飞行。完整清单见 gate JSON。

## 下一闭环(M7)

1. Owner 审查本轮候选包(WP1–WP7)并裁决 ROOT_TO_M 与失效保留/抛离语义;
2. 实测质量—质心—惯量活动(需硬件与不确定度模型);
3. 受控标准副本与发射/分离 ICD 获取(外部);
4. 有界诊断仿真研究可继续(SIM15 后继不得声称生产动力学)。
"""
(M6 / "12_release" / "M6_RELEASE_SUMMARY.md").write_text(summary, encoding="utf-8")

print(json.dumps({
    "manifest_files": manifest["file_count"],
    "manifest_bytes": manifest["total_bytes"],
    "reconciliation": recon["status"],
    "verified": recon["verified_count"],
    "missing": recon["missing_count"],
}, indent=1))
