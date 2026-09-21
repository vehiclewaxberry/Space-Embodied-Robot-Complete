# -*- coding: utf-8 -*-
# s08: 汇总 R17 机器验收摘要（ACCEPTANCE_SUMMARY.json，UTF-8/LF）
import hashlib, json, os

RUN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENG = r'F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/service_robot_wp03_spacecraft_body_r1'

def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()

neg = json.loads(open(os.path.join(RUN, 'evidence', 'r17_negative_controls.json'), encoding='utf-8').read())
pre = json.loads(open(os.path.join(RUN, 'evidence', 'r17_pre_fix_real_rejection.json'), encoding='utf-8').read())
bomon = json.loads(open(os.path.join(RUN, 'evidence', 'r17_bom_only_verification.json'), encoding='utf-8').read())
hc = json.loads(open(os.path.join(RUN, 'evidence', 'r17_deliverables_hash_compare.json'), encoding='utf-8').read())
smoke = json.loads(open(os.path.join(RUN, 'logs', 's07_build_smoke_log.json'), encoding='utf-8').read())
full = json.loads(open(os.path.join(RUN, 'logs', 's04_full_export_log.json'), encoding='utf-8').read())

summary = {
    "run": "r17_export_chain_20260919",
    "ticket": "R17",
    "scope": "WP03 阶段一收口工作包 A：BOM 交接来源时序生产修复（export_parts_and_bom.py + README 顺序说明）；软件/溯源任务，无 CAD 几何改动",
    "status": "PRODUCTION_FIX_COMPLETE_WITH_NOT_RUNS",
    "ticket_closure": "NOT_CLOSED; R17 票字段（production_fix_applied 等）不回写，留 owner/审阅",
    "stale_fact_registration": {
        "ticket_field": "current_BOM_is_proven_stale=false（2026-09-06 审计，当时 11 项交接输入哈希匹配）",
        "as_of_this_run": "E1–E4 后三态回执与地面视图回执均未同步重建，source_sha256 与 design_parameters 依赖哈希全部失配；现存 HANDOFF/BOM 相对现行 CAD 已失配（证据 inputs/INPUT_MANIFEST.json::pre_fix_staleness_audit 与 evidence/r17_pre_fix_real_rejection.json）；不回写原票字段"
    },
    "forced_order_chain": "有效输入哈希校验 → build/回执 → dynamics_handoff 子进程生成 HANDOFF → HANDOFF 逐项校验（来源哈希/实例集合/owner/分配质量/角色/配置）→ 最后写 BOM/INTERFACES；任一失配 fail-closed（exit 2 + 恢复改前字节）；BOM 消费 HANDOFF 不回写几何，无循环哈希",
    "fix_components": {
        "export_parts_and_bom_py": "重写：validate_handoff_provenance / validate_receipt_for_bom / cross_validate 三校验器 + fail-closed 恢复 + 未分配 null 保持 + --bom-only 纯读取（顶层仅 stdlib，CAD 懒加载）",
        "readme": "复现顺序说明同步修正（BOM 在 HANDOFF 之后；dynamics_handoff 不再需手工先跑；--bom-only 语义注明）",
        "untouched": ["dynamics_handoff.py", "finalize_delivery.py", "integrate_checks.py", "spacecraft_model.py", "design_parameters.json"]
    },
    "iteration_history": {
        "F0_double_count_rule_too_broad": "首版同装配 BUDGET 双计规则误伤翼叶逐件预算（6 假阳性）；收窄为仅标准件/紧固件双计后复跑真实链 43 项违规全为过期间题、零误判",
        "F1_arm_link_misjudge": "首次完整链重跑被 HANDOFF_UNKNOWN_ZERO_FILL 拦下：臂 link 回执 mass=None 属设计语义（URDF SOURCE_DIGITAL 分配）；修正排除 arm_link 行，负控复跑 8/8",
        "fail_closed_evidence": "两次被拒运行均未留下半更新交付物（BOM/INTERFACES 字节恢复一致，s02/s04 证据）"
    },
    "negative_controls": {
        "verdict": neg['verdict'], "detected": f"{neg['detected_count']}/{neg['total']}",
        "positive_control_violations": len(neg['positive_control']['violations']),
        "categories": {c['nc']: {'category': c['category'], 'detected_codes': c['detected_codes']} for c in neg['negative_controls']},
        "evidence": "evidence/r17_negative_controls.json"
    },
    "pre_fix_real_rejection": {
        "verdict": pre['verdict'], "exit_code": pre['exit_code'], "violation_count": pre['violation_count'],
        "deliverables_bytes_restored": pre['bom_interfaces_bytes_restored'],
        "evidence": "evidence/r17_pre_fix_real_rejection.json"
    },
    "full_export_after_fix": {
        "verdict": full['verdict'], "instances": full['exporter_summary']['instances'],
        "allocated_positive": full['exporter_summary']['allocated_positive'],
        "unallocated_null": full['exporter_summary']['unallocated_null'],
        "handoff_sha256": full['exporter_summary']['handoff_sha256'],
        "bom_sha256": full['exporter_summary']['bom_sha256'],
        "interfaces_sha256": full['exporter_summary']['interfaces_sha256'],
        "evidence": "logs/s04_full_export_log.json"
    },
    "bom_only_verification": {
        "verdict": bomon['verdict'],
        "a_no_cad_import": bomon['a_no_cad_import'],
        "b_functional_pass_and_byte_identical": bomon['b_functional_run']['pass'],
        "c_missing_handoff_refused_unchanged": bomon['c_missing_handoff_refusal']['pass'],
        "evidence": "evidence/r17_bom_only_verification.json"
    },
    "deliverables_hash_compare": {
        "items": [{'file': r['file'], 'sha256_before': r['sha256_before'], 'sha256_after': r['sha256_after'], 'changed': r['changed']} for r in hc['deliverables']],
        "backups": "inputs/ 同名快照（BOM.csv/INTERFACES.csv/DYNAMICS_HANDOFF.json/四份回执/README.md 改前原件）",
        "evidence": "evidence/r17_deliverables_hash_compare.json"
    },
    "smoke": {
        "verdict": smoke['verdict'],
        "structure_instances": smoke['actual_structure_instances'],
        "composition": "487 = 483 + 4（E4 夹套在位）；全态回执 497 = 487 + 10 臂 link",
        "structure_receipt_hash": smoke['structure_receipt_hash_after_build'],
        "bit_identical_to_e4_receipt": True,
        "evidence": "logs/s07_build_smoke_log.json"
    },
    "not_run": [
        "独立第三方复验（留审阅者；构建者不自验）",
        "严格验证器真实接入与 R14 参数扰动（工作包 B，不在本包）",
        "finalize_delivery.py 交付回执重跑（inspect/refs/快照绑定链不在本包授权范围）",
        "geometry_checks.py/integrate_checks.py 重跑（只读消费回执，语义未变）",
        "parking_cutaway/parking_exploded 展示视图回执刷新（HANDOFF/BOM 不消费展示视图，属 gen/inspect 链）",
        "R17 票状态字段回写（本包不改 issues.json/CURRENT/gate）",
        "实物/硬件验证（软件溯源修复，不适用）"
    ],
    "constraints_honored": [
        "不改写 gate/issues.json/CURRENT 指针",
        "WP02 文件只读",
        "未执行 git 提交",
        "UNKNOWN 零填禁止（未分配质量保持 null；CSV 空单元格非 0）",
        "FAIL 不覆盖（F0/F1 修复迭代留痕；被拒运行交付物字节恢复）",
        "无 CAD 几何改动（487/497 口径逐位保持）"
    ]
}

p = os.path.join(RUN, 'ACCEPTANCE_SUMMARY.json')
open(p, 'wb').write((json.dumps(summary, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
print('written', p)
