# -*- coding: utf-8 -*-
"""WP03 R01 验收6 独立复验 - 汇总裁决 + 全部产物 sha256 边车（含脚本，二进制 LF）。"""
import sys, json, hashlib, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r01_deck_fastening_20260917'
REVIEW = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r01_deck_fastening_20260917_review'
EV = REVIEW / 'evidence'

def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))

def sidecar(p):
    h = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    wlf(str(p) + '.sha256', h + '  ' + Path(p).name + '\n')
    return h

def main():
    t1 = json.loads((EV / 'review_t1_readback.json').read_text(encoding='utf-8'))
    nc1 = json.loads((EV / 'review_nc1_legacy_broken_edge.json').read_text(encoding='utf-8'))
    nc2 = json.loads((EV / 'review_nc2_missing_dual_axis.json').read_text(encoding='utf-8'))
    nc3 = json.loads((EV / 'review_nc3_washer_tool_conflict.json').read_text(encoding='utf-8'))
    t5 = json.loads((EV / 'review_t5_interference_scan.json').read_text(encoding='utf-8'))
    t5b = json.loads((EV / 'review_t5b_envelope_interference.json').read_text(encoding='utf-8'))
    t6 = json.loads((EV / 'review_t6_spotcheck.json').read_text(encoding='utf-8'))

    verdict = {
        'review': 'r01_deck_fastening_20260917_review',
        'ticket': 'R01_DECK_ANGLE_FASTENER_MINIMUM_PROPOSAL_R1 / WP03 计划 §3.2 验收6 独立复验',
        'reviewer': 'WP03 R01 独立审阅者（只读最终导出，未修改候选，未执行 git 提交）',
        'reviewed_run': str(RUN).replace('\\', '/'),
        'reviewed_builder_commit': 'bd126961',
        'builder_summary_sha256': hashlib.sha256((RUN / 'ACCEPTANCE_SUMMARY.json').read_bytes()).hexdigest(),
        'date': '2026-09-17',
        'verdict': 'R01_ACC6_INDEPENDENT_REVERIFY_FAIL__WEB_FASTENER_HEAD_WASHER_EMBEDDED_0p5MM_IN_SHEAR_WEB_16X',
        'verdict_reason': (
            '验收6 第四分句不满足：新候选存在新增相关未处置干涉——全部 16 件角材—腹板紧固件'
            '（{lower,upper}_angle_web_fastener_*）头侧垫圈（Ø6x0.5）承压面位于剪力腹板外表面内侧 0.5mm，'
            '垫圈环形承压区（r1.7..3.0）整体嵌入腹板材料，布尔交集体积每件 9.597566 mm3'
            '（理论 π(3^2-1.7^2)*0.5=9.60 吻合）。16 件甲板紧固件对照干净（交集体积 0）。'),
        'sub_results': {
            't1_independent_readback': {
                'verdict': t1['verdict'],
                'closed_holes': f"{t1['total_closed_holes']}/{t1['expected_closed_holes']}",
                'deck_angle_coaxial_ok': t1['coaxial']['deck_angle_ok'],
                'angle_web_coaxial_ok': t1['coaxial']['angle_web_ok'],
                'fastener_envelopes_complete': f"{t1['fastener_envelopes_complete']}/{t1['fastener_envelopes_total']}",
                'export_sha256_all_match': t1['export_manifest']['sha256_all_match'],
                'evidence': 'evidence/review_t1_readback.json'},
            'nc1_legacy_broken_edge': {
                'verdict': nc1['verdict'],
                'broken_edges_detected': f"{nc1['total_broken_edges_detected']}/{nc1['expected_total']}",
                'false_positives_on_12_intact_holes': 0,
                'legacy_source_sha256': nc1['legacy_source']['snapshot_sha256'],
                'evidence': 'evidence/review_nc1_legacy_broken_edge.json'},
            'nc2_missing_dual_axis': {
                'verdict': nc2['verdict'],
                'missing_dual_detected': nc2['detection']['missing_dual_detected_at_x-150'],
                'measured_deviation_mm': nc2['detection']['measured_axis_deviation_mm'],
                'false_positives': nc2['detection']['false_positives_on_unmutated_pairs'],
                'evidence': 'evidence/review_nc2_missing_dual_axis.json'},
            'nc3_washer_tool_conflict': {
                'verdict': nc3['verdict'],
                'washer_OD8_detected': nc3['nc3a_washer_oversize']['violation_detected'],
                'tool_conflict_detected': nc3['nc3b_tool_conflict']['violation_detected'],
                'real_overhead_hit_reproduced': nc3['nc3b_tool_conflict']['real_overhead_hit_recheck']['hit_reproduced'],
                'evidence': 'evidence/review_nc3_washer_tool_conflict.json'},
            't5_interference_scan_sampling': {
                'verdict': t5['verdict'],
                'named_set': t5['named_check_set_size'],
                'violations_sampling_scheme': len(t5['violations']),
                'sequence_constraints': len(t5['sequence_constraints']),
                'pairwise_min_mm': t5['fastener_pairwise']['min_distance_mm'],
                'known_blind_spot': t5b['known_blind_spot_of_t5'],
                'evidence': 'evidence/review_t5_interference_scan.json'},
            't5b_interference_scan_boolean': {
                'verdict': t5b['verdict'],
                'violation_count': t5b['violation_count'],
                'common_volume_each_mm3': 9.597566,
                'affected': '全部 16 件角材—腹板紧固件',
                'evidence': 'evidence/review_t5b_envelope_interference.json'},
            't6_spotcheck_acc1_to_5': {
                'verdict': t6['verdict'],
                'agreement': f"{t6['spot_values_consistent']}/{t6['spot_values_total']}",
                'agreement_rate': t6['agreement_rate'],
                'discrepancies': [
                    '验收3：腹板紧固件头垫圈承压区被腹板吞没（交集体积 9.597566 mm3），构建者"承压区完整"不成立',
                    '验收4：腹板件承压面到杆尖读回测量 9.5mm != 名义 M3x10（同一根因）',
                    '验收5：构建者 acc5 violations=0 为采样盲区假阴性，布尔口径 16 处未处置干涉'],
                'evidence': 'evidence/review_t6_spotcheck.json'}},
        'builder_claims_not_confirmed': [
            'ACCEPTANCE_SUMMARY 验收3 "头、垫、螺母/螺纹承压区完整"（对 16 件腹板紧固件不成立）',
            'ACCEPTANCE_SUMMARY 验收5 "violations: 0 / penetration_sample_hits: 0"（采样盲区假阴性）',
            'r01_fastener_stacks_32 腹板件 underhead_length_mm=10（读回承压面到杆尖 9.5mm）'],
        'builder_claims_confirmed': [
            '验收1：16/16 闭孔、旧破边消除、最小孔到避口 9.8mm、到外边 3.8mm（独立读回一致）',
            '验收2：32/32 组同轴偏差 0.0、夹层 6.0/5.0mm（独立重算一致）',
            '验收5：具名集合 108、两两最小间隙 4.5458mm、装序约束 46 条、穿透采样 0（同口径一致）'],
        'root_cause_hypothesis_not_a_fix': (
            '工程源 spacecraft_model.py deck_fastening_parts 腹板紧固件行头垫圈中心 side*102.9'
            '（y 102.65..103.15），相对贴面正确值 side*103.4 内移 0.5mm；审阅者不修改候选。'),
        'scope_limits': {
            'whole_design_complete': False,
            'manufacturing_release': False,
            'material_grade_preload_locking_engagement': 'UNKNOWN（保持构建者原样，未评定）',
            'structural_allowable_edge_margin': 'UNKNOWN（须绑定材料/载荷）',
            'full_assembly_rebuild': 'NOT_RUN（属构建者验收7 范围）',
            'review_scope': '仅 run exports/ 数字几何名义装配；未评审图纸/BOM/质量链'},
        'fail_policy': 'FAIL 不被 PASS 覆盖；本 FAIL 不否定三负控与读回 PASS 分结论',
        'recommended_builder_action': (
            '腹板紧固件头垫圈/头整体外移 0.5mm 使承压面与腹板外表面重合（side*103.15），'
            '重导出后重跑验收1-6；构建者 acc5 穿透采样建议增补垫圈环形承压区采样或直接采用布尔交集口径。'),
        'elapsed_note': '各子项耗时见各自 evidence JSON',
    }
    f = REVIEW / 'REVIEW_VERDICT.json'
    wlf(f, json.dumps(verdict, ensure_ascii=False, indent=2) + '\n')
    sidecar(f)
    # 全部脚本边车
    for sp in sorted((REVIEW / 'scripts').glob('*.py')):
        sidecar(sp)
    print('VERDICT', verdict['verdict'])
    print('sidecars written for verdict +', len(list((REVIEW / 'scripts').glob('*.py'))), 'scripts')

if __name__ == '__main__':
    main()
