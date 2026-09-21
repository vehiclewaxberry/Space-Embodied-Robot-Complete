# -*- coding: utf-8 -*-
"""R07-E2 独立复验 r34：ACCEPTANCE_SUMMARY 抽验。
逐项对照被审验收摘要与底层证据/日志，并与审阅侧 r30-r33 独立证据互锁。
抽验项：
  S1 冒烟 459=431+28（s07 日志；实例数与 r33 独立 build 互锁）
  S2 读回 PASS/同轴 0.0/0.0/8 对/孔数 2 每纵梁 1 每塞（acc 证据 vs 审阅 r30）
  S3 登记表行数 8/8/8/8
  S4 布尔 PASS/positives 空/max 0.0/A68 B12/clearance 64 全过（acc vs 审阅 r33）
  S5 质量：28 件/added 3337.860504/removed 0/allocated 0/铝当量独立重算/行和复算/行级 allocated 全 null
  S6 UNKNOWN 保留：28 行 mass_basis 全含 UNKNOWN 或 CANDIDATE 且 allocated=null
  S7 NOT_RUN 恰七项且语义覆盖（独立复验/SHORT_ENGAGEMENT/选型 UNKNOWN/公差堆叠/工具回放/拆叉 NEEDS_SEQUENCE_REVIEW/实物试配）
  S8 关键登记落盘：SHORT_ENGAGEMENT_1.8MM_REGISTERED（mounting_surfaces）与 NEEDS_SEQUENCE_REVIEW（tool_paths）
  S9 V1 判据 FAIL 保留件：存在/verdict FAIL/8 塞 failures/iteration 注记/边车哈希有效
  S10 constraints_honored 六条在册；跨 run 纵梁一致性以审阅 r30 证据复核
"""
import json, time
from pathlib import Path
from e2_common import REV, RUN, write_json, sha256_file

EV = RUN / 'evidence'
LG = RUN / 'logs'
REV_EV = REV / 'evidence'


def sidecar_ok(p):
    sc = Path(str(p) + '.sha256')
    if not sc.exists():
        return False, 'sidecar missing'
    txt = sc.read_text(encoding='utf-8').strip()
    h = txt.split(' ')[0]
    return (h == sha256_file(p)), ('hash match' if h == sha256_file(p) else 'HASH MISMATCH')


def main():
    t0 = time.time()
    acc_sum = json.loads((RUN / 'ACCEPTANCE_SUMMARY.json').read_text(encoding='utf-8'))
    checks = {}
    failures = []

    # S1 冒烟
    smoke = json.loads((LG / 's07_build_smoke_log.json').read_text(encoding='utf-8'))
    r33 = json.loads((REV_EV / 'review_e2_scan.json').read_text(encoding='utf-8'))
    ok = (smoke['baseline_instances_e1_closed'] == 431 and smoke['expected_instances'] == 459 and
          smoke['actual_instances'] == 459 and smoke['e2_instances'] == 28 and
          smoke['e2_breakdown'] == {'stub': 12, 'washer': 12, 'wing_pin': 4} and
          smoke['verdict'] == 'PASS' and
          r33['build_instance_count'] == 459 and r33['e2_part_count'] == 28)
    checks['S1_smoke_459_eq_431_plus_28'] = {'smoke_actual': smoke['actual_instances'],
                                             'review_r33_build_count': r33['build_instance_count'],
                                             'pass': ok}
    if not ok:
        failures.append('S1 smoke/instance count mismatch')

    # S2 读回
    rb = json.loads((EV / 'acc_readback_holes_coaxial.json').read_text(encoding='utf-8'))
    r30 = json.loads((REV_EV / 'review_e2_readback.json').read_text(encoding='utf-8'))
    sub = [v2 for pr in rb['coaxial_pairs'] for v2 in pr.values()
           if isinstance(v2, dict) and 'axis_offset_mm' in v2]
    offs = [v2['axis_offset_mm'] for v2 in sub]
    pars = [v2['parallel_deviation'] for v2 in sub]
    ok = (rb['verdict'] == 'PASS' and len(rb['coaxial_pairs']) == 8 and
          all(pr['coaxial'] for pr in rb['coaxial_pairs']) and
          max(offs) == 0.0 and max(pars) == 0.0 and
          all(v == 2 for k, v in rb['hole_counts'].items() if k.startswith('RB_longeron')) and
          all(v == 1 for k, v in rb['hole_counts'].items() if k.startswith('RB_end_plug')) and
          r30['verdict'] == 'PASS' and r30['max_axis_offset_mm'] == 0.0)
    checks['S2_readback_coaxial'] = {'acc_pairs': len(rb['coaxial_pairs']),
                                     'acc_max_off': max(offs), 'acc_max_par': max(pars),
                                     'review_r30_verdict': r30['verdict'], 'pass': ok}
    if not ok:
        failures.append('S2 readback mismatch')

    # S3 登记表行数
    counts = {}
    for f, k in (('e2_dual_hole_pairs_8.json', 'dual_hole_pairs'),
                 ('e2_fastener_stacks_8.json', 'fastener_stacks'),
                 ('e2_mounting_surfaces.json', 'mounting_surfaces'),
                 ('e2_tool_paths.json', 'tool_paths')):
        d = json.loads((EV / f).read_text(encoding='utf-8'))
        counts[k] = d['row_count'] if 'row_count' in d else len(d['rows'])
    ok = counts == {'dual_hole_pairs': 8, 'fastener_stacks': 8,
                    'mounting_surfaces': 8, 'tool_paths': 8}
    checks['S3_registration_table_rows'] = {'counts': counts, 'pass': ok}
    if not ok:
        failures.append(f'S3 table rows {counts}')

    # S4 布尔
    bi = json.loads((EV / 'acc_interference_boolean.json').read_text(encoding='utf-8'))
    ok = (bi['verdict'] == 'PASS' and bi['positives'] == [] and
          bi['max_common_volume_mm3'] == 0.0 and
          bi['pairs'] == {'A_e2_vs_other': 68, 'B_e2_vs_e2': 12} and
          len(bi['explicit_clearance_checks']) == 64 and
          all(c['pass'] for c in bi['explicit_clearance_checks']) and
          r33['verdict'] == 'PASS' and r33['summary']['new_positives'] == 0 and
          r33['summary']['pairs']['A_e2_vs_other'] == 68 and
          r33['summary']['pairs']['B_e2_vs_e2'] == 12 and
          r33['summary']['clearance_checks'] == 64 and r33['summary']['clearance_fail'] == 0)
    checks['S4_boolean'] = {'acc_pairs': bi['pairs'], 'review_pairs': r33['summary']['pairs'],
                            'pass': ok}
    if not ok:
        failures.append('S4 boolean mismatch')

    # S5 质量
    md = json.loads((EV / 'e2_bom_mass_delta.json').read_text(encoding='utf-8'))
    vol_sum = sum(r['volume_mm3'] for r in md['rows'])
    al_recompute = md['added_volume_mm3'] * 2.7e-6
    ok = (md['added_part_count'] == 28 and md['modified_member_count'] == 0 and
          md['added_volume_mm3'] == 3337.860504 and md['removed_volume_mm3'] == 0.0 and
          md['net_allocated_mass_delta_kg'] == 0.0 and
          abs(md['net_al_candidate_mass_delta_kg'] - al_recompute) < 1e-9 and
          abs(vol_sum - md['added_volume_mm3']) < 1e-6 and
          all(r['mass_kg_allocated'] is None for r in md['rows']) and
          len(md['rows']) == 28)
    checks['S5_mass'] = {'row_volume_sum': vol_sum, 'al_recompute_kg': al_recompute,
                         'registered_al_kg': md['net_al_candidate_mass_delta_kg'], 'pass': ok}
    if not ok:
        failures.append('S5 mass mismatch')

    # S6 UNKNOWN 保留
    n_unknown = sum(1 for r in md['rows']
                    if ('UNKNOWN' in r['mass_basis'] or 'CANDIDATE' in r['mass_basis']))
    ok = (n_unknown == 28 and
          all(r['representation_role'] == 'SIMPLIFIED_PROXY' for r in md['rows']))
    checks['S6_unknown_preserved'] = {'rows_with_unknown_or_candidate': n_unknown, 'pass': ok}
    if not ok:
        failures.append('S6 UNKNOWN not fully preserved')

    # S7 NOT_RUN 七项语义
    nr = acc_sum['not_run']
    semantics = ['独立第三方复验', 'SHORT_ENGAGEMENT', 'UNSELECTED',
                 '公差堆叠', '工具路径实物回放', 'NEEDS_SEQUENCE_REVIEW', '实物试配']
    missing = [s for s in semantics if not any(s in item for item in nr)]
    ok = (len(nr) == 7 and not missing)
    checks['S7_not_run'] = {'count': len(nr), 'missing_semantics': missing, 'pass': ok}
    if not ok:
        failures.append(f'S7 not_run count={len(nr)} missing={missing}')

    # S8 关键登记落盘
    ms_txt = (EV / 'e2_mounting_surfaces.json').read_text(encoding='utf-8')
    tp_txt = (EV / 'e2_tool_paths.json').read_text(encoding='utf-8')
    md_txt = (EV / 'e2_bom_mass_delta.json').read_text(encoding='utf-8')
    ok = ('SHORT_ENGAGEMENT_1.8MM_REGISTERED' in ms_txt and
          'NEEDS_SEQUENCE_REVIEW' in tp_txt and 'PRESS_FIT_UNKNOWN' in md_txt)
    checks['S8_key_registrations'] = {
        'short_engagement_in_mounting_surfaces': 'SHORT_ENGAGEMENT_1.8MM_REGISTERED' in ms_txt,
        'sequence_review_in_tool_paths': 'NEEDS_SEQUENCE_REVIEW' in tp_txt,
        'press_fit_unknown_in_bom_mass_delta': 'PRESS_FIT_UNKNOWN' in md_txt, 'pass': ok}
    if not ok:
        failures.append('S8 key registration missing')

    # S9 V1 FAIL 保留件
    v1p = EV / 'acc_readback_holes_coaxial_V1_CRITERION_FAIL.json'
    if not v1p.exists():
        checks['S9_v1_fail_preserved'] = {'pass': False, 'reason': 'file missing'}
        failures.append('S9 V1 file missing')
    else:
        v1 = json.loads(v1p.read_text(encoding='utf-8'))
        sc_ok, sc_msg = sidecar_ok(v1p)
        plug_fails = [f for f in v1['failures'] if 'RB_end_plug_' in f]
        ok = (v1['verdict'] == 'FAIL' and len(v1['failures']) == 8 and
              len(plug_fails) == 8 and
              'V1_CRITERION_FAIL_PRESERVED' in str(v1.get('iteration', '')) and
              '判据缺陷' in str(v1.get('iteration', '')) and sc_ok)
        checks['S9_v1_fail_preserved'] = {'verdict': v1['verdict'], 'n_failures': len(v1['failures']),
                                          'plug_failures': len(plug_fails),
                                          'sidecar': sc_msg, 'pass': ok}
        if not ok:
            failures.append('S9 V1 preserved-artifact check failed')

    # S10 constraints_honored + 跨 run 一致性（审阅 r30 证据复核）
    ch = acc_sum['constraints_honored']
    xrl = r30.get('cross_run_longeron', {})
    xrun_ok = (len(xrl) == 4 and
               all(v.get('normalized_identical_to_e1_export') for v in xrl.values()))
    ok = (len(ch) == 6 and 'FAIL 不覆盖（s05 V1 判据 FAIL 保留）' in ch and
          '未执行 git 提交' in ch and (xrun_ok is True))
    checks['S10_constraints_and_cross_run'] = {'n_constraints': len(ch),
                                               'cross_run_longeron_4of4': xrun_ok, 'pass': ok}
    if not ok:
        failures.append('S10 constraints/cross-run check failed')

    n_pass = sum(1 for c in checks.values() if c['pass'])
    result = {'review': 'R07_E2_INDEPENDENT_REVERIFY', 'script': 'e2_r34_spotcheck.py',
              'reviewed_run': RUN.name, 'checks': checks,
              'spotcheck_pass_ratio': f'{n_pass}/{len(checks)}',
              'failures': failures, 'verdict': 'PASS' if not failures else 'FAIL',
              'elapsed_s': round(time.time() - t0, 3)}
    write_json(REV_EV / 'review_e2_spotcheck.json', result)
    print('verdict', result['verdict'], result['spotcheck_pass_ratio'])
    for k, v in checks.items():
        print(k, v['pass'])
    print('failures', failures)


if __name__ == '__main__':
    main()
