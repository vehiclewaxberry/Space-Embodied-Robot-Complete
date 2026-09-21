# -*- coding: utf-8 -*-
"""WP03 R01 候选 V2 验收6 独立复验 - 任务3：ACCEPTANCE_SUMMARY_V2 抽验复核。

每项至少 1 个数值独立重算（数据来源：审阅者 review_v2_readback / review_v2_regression 证据）；
并核验 V1 FAIL 历史原样保留（V1 汇总哈希不变、v1_superseded 物证齐备）、UNKNOWN 未零填。
"""
import sys, json, hashlib, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r01_deck_fastening_20260917'
REVIEW = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r01_deck_fastening_20260917_review'
EV = REVIEW / 'evidence'
REV = RUN / 'evidence'

def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))

def sidecar(p):
    h = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    wlf(str(p) + '.sha256', h + '  ' + Path(p).name + '\n')
    return h

def cmp(name, builder_val, my_val, tol=0.01):
    if isinstance(builder_val, (int, float)) and isinstance(my_val, (int, float)):
        ok = abs(builder_val - my_val) <= tol
    else:
        ok = builder_val == my_val
    return {'quantity': name, 'builder_v2': builder_val, 'independent': my_val, 'consistent': bool(ok)}

def main():
    t0 = time.time()
    acc = json.loads((RUN / 'ACCEPTANCE_SUMMARY_V2.json').read_text(encoding='utf-8'))
    rb = json.loads((EV / 'review_v2_readback.json').read_text(encoding='utf-8'))
    rg = json.loads((EV / 'review_v2_regression_negative_control.json').read_text(encoding='utf-8'))
    v1_verdict = json.loads((REVIEW / 'REVIEW_VERDICT.json').read_text(encoding='utf-8'))
    acc5v2 = json.loads((REV / 'acc5_builder_self_check_v2.json').read_text(encoding='utf-8'))
    bom = json.loads((REV / 'r01_bom_mass_delta_v2_compare.json').read_text(encoding='utf-8'))
    stacks = json.loads((REV / 'r01_fastener_stacks_32.json').read_text(encoding='utf-8'))

    kn = {i['item']: i.get('key_numbers', {}) for i in acc['acceptance_items']}
    items = []

    # 验收1（V2 沿用 V1 证据 + 清单证明）：审阅者在 V2 导出上直接重验
    items.append({'item': 1, 'checks': [
        cmp('closed_holes', 16, rb['structural_reverify']['total_closed_holes'], 0),
        cmp('old_pattern_residual_faces', 0,
            sum(d['old_pattern_residual_faces'] for d in rb['structural_reverify']['decks'].values()), 0)]})
    # 验收2
    items.append({'item': 2, 'checks': [
        cmp('groups_ok', 32, rb['structural_reverify']['coaxial']['deck_angle_ok']
            + rb['structural_reverify']['coaxial']['angle_web_ok'], 0),
        cmp('coaxial_deviation_mm', 0.0, rb['structural_reverify']['coaxial']['deviation_max_mm'])]})
    # 验收3
    items.append({'item': 3, 'checks': [
        cmp('washer_web_common_volume_16件_max', 0.0, rb['web_fastener_common_max_mm3'], 0),
        cmp('v1_common_volume_recomputed_mm3', 9.597565556717031,
            max(e['reviewer_boolean_common_mm3'] for e in rg['v1_replay_negative_control']['entries']), 1e-6),
        cmp('column_notch_walls_lower', 12, rb['structural_reverify']['decks']['lower']['column_notch_wall_faces'], 0)]})
    # 验收4
    web_tips = [t for t in rb['bearing_face_to_shank_tip'] if 'angle_web' in t['fastener']]
    deck_tips = [t for t in rb['bearing_face_to_shank_tip'] if '_deck_fastener_' in t['fastener']]
    unknowns_ok = all(r.get('material_grade') == 'UNKNOWN' and r.get('preload') == 'UNKNOWN'
                      and r.get('locking') == 'UNKNOWN' and r.get('effective_thread_engagement') == 'UNKNOWN'
                      for r in stacks['rows'])
    items.append({'item': 4, 'checks': [
        cmp('web 承压面到杆尖', 10.0, max(t['bearing_face_to_shank_tip_mm'] for t in web_tips)),
        cmp('deck 承压面到杆尖', 12.0, max(t['bearing_face_to_shank_tip_mm'] for t in deck_tips)),
        cmp('tip_match', '32/32', rb['tip_match'], 0),
        cmp('UNKNOWN 未零填', True, unknowns_ok, 0)]})
    # 验收5
    items.append({'item': 5, 'checks': [
        cmp('named_check_set_size', 108, len(acc5v2['named_check_set']), 0),
        cmp('boolean_common_entries', 32, len(acc5v2['fastener_boolean_common']), 0),
        cmp('boolean_common_max_mm3', 0.0,
            max(e['common_volume_mm3'] for e in acc5v2['fastener_boolean_common']), 0),
        cmp('violations(审阅者布尔口径)', 0, len(rg['v2_scan']['violations']), 0),
        cmp('fastener_pairwise_min_distance_mm', 4.545797, acc5v2['fastener_pairwise']['min_distance_mm'], 1e-6),
        cmp('sequence_constraints', 46, len(acc5v2['sequence_constraints']), 0)]})
    # 验收7
    items.append({'item': 7, 'checks': [
        cmp('mass_delta_kg_AL_candidate', -0.0031447701211326394,
            bom['v2_total_delta_mass_kg_AL_CANDIDATE'], 1e-12),
        cmp('structural_delta_identical_to_v1', True, bom['structural_delta_identical_to_v1'], 0),
        cmp('web_fastener_envelope_delta_each_mm3', 3.534292,
            rb['v1_v2_envelope_volume_delta']['per_fastener'][0]['volume_delta_mm3'], 1e-4)]})

    # V1 FAIL 历史保留核验
    v1_sum_sha = hashlib.sha256((RUN / 'ACCEPTANCE_SUMMARY.json').read_bytes()).hexdigest()
    v1_files = sorted((RUN / 'exports' / 'v1_superseded').glob('*.step'))
    v1_sidecars_ok = all((RUN / 'exports' / 'v1_superseded' / (f.name + '.sha256')).exists() for f in v1_files)
    history = {
        'v1_acceptance_summary_sha256': v1_sum_sha,
        'v1_acceptance_summary_unchanged_since_review':
            v1_sum_sha == v1_verdict['builder_summary_sha256'],
        'v1_superseded_step_count': len(v1_files),
        'v1_superseded_sidecars_complete': v1_sidecars_ok,
        'v1_evidence_files_present': all((REV / n).exists() for n in [
            'acc5_builder_self_check.json', 'acc3_acc4_bearing_notch_stack.json', 'r01_bom_mass_delta.json']),
        'v2_summary_declares_v1_fail': acc['v1_fail_history_preserved']['review_verdict'].startswith('FAIL')}
    history['preserved'] = all([history['v1_acceptance_summary_unchanged_since_review'],
                                len(v1_files) == 16, v1_sidecars_ok,
                                history['v1_evidence_files_present'],
                                history['v2_summary_declares_v1_fail']])

    total = sum(len(i['checks']) for i in items)
    consistent = sum(1 for i in items for c in i['checks'] if c['consistent'])
    rep = {'review': 'r01_deck_fastening_20260917_review', 'candidate_version': 'V2',
           'check': 'ACC6_V2_T3_acceptance_summary_v2_spotcheck',
           'builder_summary_v2_sha256': hashlib.sha256((RUN / 'ACCEPTANCE_SUMMARY_V2.json').read_bytes()).hexdigest(),
           'items': items, 'v1_fail_history_preservation': history,
           'spot_values_total': total, 'spot_values_consistent': consistent,
           'agreement_rate': round(consistent / total, 6),
           'verdict': ('SPOTCHECK_ALL_CONSISTENT_AND_HISTORY_PRESERVED'
                       if consistent == total and history['preserved']
                       else 'SPOTCHECK_DISCREPANCY_OR_HISTORY_GAP'),
           'elapsed_s': round(time.time() - t0, 3)}
    f = EV / 'review_v2_spotcheck.json'
    wlf(f, json.dumps(rep, ensure_ascii=False, indent=2) + '\n'); sidecar(f)
    print('V2-T3', rep['verdict'], f'{consistent}/{total}', 'history_preserved:', history['preserved'])
    for i in items:
        for c in i['checks']:
            if not c['consistent']:
                print(' DISCREPANCY item', i['item'], c)

if __name__ == '__main__':
    main()
