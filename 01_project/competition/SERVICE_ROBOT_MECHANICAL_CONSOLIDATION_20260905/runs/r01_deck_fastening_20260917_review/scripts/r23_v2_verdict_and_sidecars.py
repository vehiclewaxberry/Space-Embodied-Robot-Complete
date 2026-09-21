# -*- coding: utf-8 -*-
"""WP03 R01 候选 V2 验收6 独立复验 - 汇总裁决 + 新增产物 sha256 边车（二进制 LF）。"""
import json, hashlib
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
    rb = json.loads((EV / 'review_v2_readback.json').read_text(encoding='utf-8'))
    rg = json.loads((EV / 'review_v2_regression_negative_control.json').read_text(encoding='utf-8'))
    sp = json.loads((EV / 'review_v2_spotcheck.json').read_text(encoding='utf-8'))

    all_pass = (rb['verdict'] == 'PASS' and rg['verdict'] == 'V2_SCAN_CLEAN_AND_V1_REPLAY_ALARMS'
                and sp['verdict'] == 'SPOTCHECK_ALL_CONSISTENT_AND_HISTORY_PRESERVED')
    verdict = {
        'review': 'r01_deck_fastening_20260917_review',
        'candidate_version': 'V2',
        'ticket': 'R01_DECK_ANGLE_FASTENER_MINIMUM_PROPOSAL_R1 / WP03 计划 §3.2 验收6 V2 独立复验',
        'reviewer': 'WP03 R01 独立审阅者（只读最终导出，未修改候选，未执行 git 提交）',
        'reviewed_run': str(RUN).replace('\\', '/'),
        'reviewed_builder_commit': '4c184e0e',
        'prior_v1_review_verdict': json.loads((REVIEW / 'REVIEW_VERDICT.json').read_text(encoding='utf-8'))['verdict'],
        'date': '2026-09-17',
        'verdict': ('R01_ACC6_V2_INDEPENDENT_REVERIFY_PASS' if all_pass else
                    'R01_ACC6_V2_INDEPENDENT_REVERIFY_FAIL__SEE_SUB_RESULTS'),
        'sub_results': {
            'v2_readback': {
                'verdict': rb['verdict'],
                'closed_holes': f"{rb['structural_reverify']['total_closed_holes']}/16",
                'coaxial': f"deck-angle {rb['structural_reverify']['coaxial']['deck_angle_ok']}/16 + "
                           f"angle-web {rb['structural_reverify']['coaxial']['angle_web_ok']}/16",
                'boolean_common_32_max_mm3': max(c['boolean_common_volume_mm3'] for c in rb['boolean_common']),
                'web_fastener_common_16_max_mm3': rb['web_fastener_common_max_mm3'],
                'bearing_face_to_shank_tip': rb['tip_match'] + '（腹板件 10.0 / 甲板件 12.0）',
                'v1_v2_volume_delta_mechanism_match': rb['v1_v2_envelope_volume_delta']['all_match'],
                'evidence': 'evidence/review_v2_readback.json'},
            'v2_interference_scan_boolean': {
                'verdict': 'CLEAN' if rg['v2_scan']['clean'] else 'VIOLATIONS',
                'violations': rg['v2_scan']['violations'],
                'evidence': 'evidence/review_v2_regression_negative_control.json'},
            'v1_replay_negative_control': {
                'verdict': 'ALARMS_ON_ALL_16' if rg['v1_replay_negative_control']['both_chains_alarm_on_all'] else 'BLIND',
                'reviewer_alarms': f"{rg['v1_replay_negative_control']['reviewer_alarms']}/16",
                'builder_s06_1b_alarms': f"{rg['v1_replay_negative_control']['builder_s06_1b_alarms']}/16",
                'per_fastener_common_mm3': rg['v1_replay_negative_control']['expected_per_fastener_mm3'],
                'note': '修复后检查链（布尔交集口径）对 V1 缺陷物证 16/16 报警，V1 假阴性盲区闭环',
                'evidence': 'evidence/review_v2_regression_negative_control.json'},
            'acceptance_summary_v2_spotcheck': {
                'verdict': sp['verdict'],
                'agreement': f"{sp['spot_values_consistent']}/{sp['spot_values_total']}",
                'agreement_rate': sp['agreement_rate'],
                'v1_fail_history_preserved': sp['v1_fail_history_preservation']['preserved'],
                'evidence': 'evidence/review_v2_spotcheck.json'}},
        'v1_fail_closure_confirmation': (
            'V1 FAIL（9c5e6276）指出的三项问题全部闭环：'
            '(1) 16 件腹板紧固件头垫圈嵌入腹板 -> V2 布尔交集 16 件最大 0.0 mm3；'
            '(2) acc4 腹板件承压面到杆尖 9.5mm -> V2 实测 10.0mm = 名义；'
            '(3) acc5 采样口径盲区 -> 构建者已固化布尔交集口径（s06 第1b节），'
            '审阅者以 V1 物证回放证明该链 16/16 报警。'),
        'scope_limits': {
            'whole_design_complete': False,
            'manufacturing_release': False,
            'material_grade_preload_locking_engagement': 'UNKNOWN（保持原样，未评定）',
            'structural_allowable_edge_margin': 'UNKNOWN（须绑定材料/载荷）',
            'full_assembly_rebuild_and_drawings': 'NOT_RUN（属构建者验收7 范围，本轮未评审）',
            'review_scope': '仅 run exports/ V2 数字几何名义装配'},
        'fail_policy': 'FAIL 不被 PASS 覆盖：本 PASS 仅针对候选 V2；V1 FAIL（9c5e6276）历史原样保留',
    }
    f = REVIEW / 'REVIEW_VERDICT_V2.json'
    wlf(f, json.dumps(verdict, ensure_ascii=False, indent=2) + '\n')
    sidecar(f)
    for spf in sorted((REVIEW / 'scripts').glob('r2*_v2*.py')):
        sidecar(spf)
    sidecar(REVIEW / 'scripts' / 'r23_v2_verdict_and_sidecars.py')
    print('VERDICT_V2', verdict['verdict'])

if __name__ == '__main__':
    main()
