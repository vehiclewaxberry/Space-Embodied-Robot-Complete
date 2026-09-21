# -*- coding: utf-8 -*-
"""R07-E3 独立复验 r34：ACCEPTANCE_SUMMARY 抽验。
  S1 冒烟 483=459+24（s07 日志；与 r33 独立 build 实例数互锁）
  S2 同轴 0.0/0.0、12 对（acc 读回证据 vs 审阅 r30）
  S3 登记表行数 12/12/6/6
  S4 布尔 PASS/positives 空/max 0.0/A64 B12/clearance 80 全过（acc vs 审阅 r33）
  S5 质量：24 件/added 3850.619/removed 2827.194/allocated 0/铝当量独立重算/行级 allocated 全 null
  S5b removed 独立复算：git f130d873^ 旧源码 build 基线 8 改件体积 − E3 exports 体积；
      纵梁单孔去除 59.232 复现（基线=E2 exports 同名件）
  S6 UNKNOWN 保留（24 行 mass_basis 全 UNKNOWN/CANDIDATE）
  S7 NOT_RUN 恰八项且语义覆盖
  S8 FAIL v1 归档完整（log 存在/4 HIT 16.370/边车有效/v2 log hits 0/未被覆盖）
  S9 上纵梁哈希变化属预期说明 + 柱面口径 14=10+4（r30 独立复现互锁）
  S10 constraints_honored 六条在册
"""
import json, subprocess, sys, time, importlib.util
from pathlib import Path
from e3_common import (REV, RUN, ROOT, ENG, write_json, sha256_file, import_step)

EV = RUN / 'evidence'
LG = RUN / 'logs'
REV_EV = REV / 'evidence'
E3_COMMIT = 'f130d873'
AFFECTED = ['RB_longeron_1_1', 'RB_longeron_-1_1',
            'hold_crossbeam_0', 'hold_crossbeam_1',
            'hold_roof_lug_0_-94.15', 'hold_roof_lug_1_-94.15',
            'hold_pivot_clevis_0', 'hold_pivot_clevis_1']


def sidecar_ok(p):
    sc = Path(str(p) + '.sha256')
    if not sc.exists():
        return False
    return sc.read_text(encoding='utf-8').strip().split(' ')[0] == sha256_file(p)


def main():
    t0 = time.time()
    acc_sum = json.loads((RUN / 'ACCEPTANCE_SUMMARY.json').read_text(encoding='utf-8'))
    checks = {}
    failures = []

    # S1 冒烟
    smoke = json.loads((LG / 's07_build_smoke_log.json').read_text(encoding='utf-8'))
    r33 = json.loads((REV_EV / 'review_e3_scan.json').read_text(encoding='utf-8'))
    ok = (smoke['baseline_instances_e2_closed'] == 459 and smoke['expected_instances'] == 483 and
          smoke['actual_instances'] == 483 and smoke['e3_instances'] == 24 and
          smoke['verdict'] == 'PASS' and
          r33['build_instance_count'] == 483 and r33['e3_part_count'] == 24)
    checks['S1_smoke_483_eq_459_plus_24'] = {'smoke_actual': smoke['actual_instances'],
                                             'review_r33_build_count': r33['build_instance_count'],
                                             'pass': ok}
    if not ok:
        failures.append('S1 smoke mismatch')

    # S2 同轴
    rb = json.loads((EV / 'acc_readback_holes_coaxial.json').read_text(encoding='utf-8'))
    r30 = json.loads((REV_EV / 'review_e3_readback.json').read_text(encoding='utf-8'))
    sub = [v2 for pr in rb['coaxial_pairs'] for k2, v2 in pr.items()
           if isinstance(v2, dict) and 'axis_offset_mm' in v2]
    offs = [v2['axis_offset_mm'] for v2 in sub]
    pars = [v2['parallel_deviation'] for v2 in sub]
    ok = (rb['verdict'] == 'PASS' and len(rb['coaxial_pairs']) == 12 and
          all(pr['coaxial'] for pr in rb['coaxial_pairs']) and
          max(offs) == 0.0 and max(pars) == 0.0 and
          r30['verdict'] == 'PASS' and r30['max_axis_offset_mm'] == 0.0)
    checks['S2_readback_coaxial'] = {'acc_pairs': len(rb['coaxial_pairs']),
                                     'acc_max_off': max(offs),
                                     'review_r30_verdict': r30['verdict'], 'pass': ok}
    if not ok:
        failures.append('S2 readback mismatch')

    # S3 表行数
    counts = {}
    for f, k in (('e3_dual_hole_pairs_12.json', 'dual_hole_pairs'),
                 ('e3_fastener_stacks_12.json', 'fastener_stacks'),
                 ('e3_mounting_surfaces.json', 'mounting_surfaces'),
                 ('e3_tool_paths.json', 'tool_paths')):
        d = json.loads((EV / f).read_text(encoding='utf-8'))
        counts[k] = d.get('row_count', len(d['rows']))
    ok = counts == {'dual_hole_pairs': 12, 'fastener_stacks': 12,
                    'mounting_surfaces': 6, 'tool_paths': 6}
    checks['S3_registration_table_rows'] = {'counts': counts, 'pass': ok}
    if not ok:
        failures.append(f'S3 table rows {counts}')

    # S4 布尔
    bi = json.loads((EV / 'acc_interference_boolean.json').read_text(encoding='utf-8'))
    ok = (bi['verdict'] == 'PASS' and bi['positives'] == [] and
          bi['max_common_volume_mm3'] == 0.0 and
          bi['pairs'] == {'A_e3_vs_other': 64, 'B_e3_vs_e3': 12} and
          len(bi['explicit_clearance_checks']) == 80 and
          all(c['pass'] for c in bi['explicit_clearance_checks']) and
          'BRepAlgoAPI_Common' in bi['authoritative_method'] and
          r33['verdict'] == 'PASS' and r33['summary']['new_positives'] == 0 and
          r33['summary']['pairs']['A_e3_vs_other'] == 64 and
          r33['summary']['pairs']['B_e3_vs_e3'] == 12 and
          r33['summary']['clearance_checks'] == 80 and r33['summary']['clearance_fail'] == 0)
    checks['S4_boolean'] = {'acc_pairs': bi['pairs'],
                            'method': bi['authoritative_method'][:60],
                            'review_pairs': r33['summary']['pairs'], 'pass': ok}
    if not ok:
        failures.append('S4 boolean mismatch')

    # S5 质量（bom json 为全精度；ACCEPTANCE 摘要为圆整值，容差 1e-3 交叉核对）
    md = json.loads((EV / 'e3_bom_mass_delta.json').read_text(encoding='utf-8'))
    al_recompute = (md['added_volume_mm3'] - md['removed_volume_mm3']) * 2.7e-6
    ok = (md['added_part_count'] == 24 and md['modified_member_count'] == 8 and
          abs(md['added_volume_mm3'] - 3850.619) < 1e-3 and
          abs(md['removed_volume_mm3'] - 2827.194) < 1e-3 and
          md['net_allocated_mass_delta_kg'] == 0.0 and
          abs(md['net_al_candidate_mass_delta_kg'] - al_recompute) < 1e-9 and
          len(md['rows']) == 24 and
          all(r['mass_kg_allocated'] is None for r in md['rows']))
    checks['S5_mass'] = {'added_volume_mm3': md['added_volume_mm3'],
                         'removed_volume_mm3': md['removed_volume_mm3'],
                         'al_recompute_kg': al_recompute,
                         'registered_al_kg': md['net_al_candidate_mass_delta_kg'], 'pass': ok}
    if not ok:
        failures.append('S5 mass mismatch')

    # S5b removed 独立复算（git 旧源码 build 基线 vs E3 exports 体积）
    s5b = {'per_member': {}, 'pass': None}
    cp = subprocess.run(['git', 'show',
                         f'{E3_COMMIT}^:20_engineering/service_robot_wp03_spacecraft_body_r1/spacecraft_model.py'],
                        cwd=str(ROOT), capture_output=True, timeout=60)
    if cp.returncode != 0:
        s5b['pass'] = False
        s5b['error'] = cp.stderr.decode('utf-8', 'replace')[:200]
        failures.append('S5b git old source unavailable')
    else:
        # 旧源码内的工程文件相对路径以 ENG 目录为基准 → 临时置于 ENG 下 import，
        # finally 保证删除（审阅只读原则：不触碰任何既有文件，临时文件用后即删）
        tmp = ENG / '_review_pre_e3_tmp.py'
        tmp.write_bytes(cp.stdout)
        try:
            sys.path.insert(0, str(ENG))
            spec = importlib.util.spec_from_file_location('spacecraft_model_pre_e3', str(tmp))
            sm_pre = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(sm_pre)
            _, shapes_pre, _ = sm_pre.build('service', include_arm=False)
            tot = 0.0
            man = json.loads((RUN / 'exports' / 'EXPORT_MANIFEST.json').read_text(encoding='utf-8'))
            vol_now = {p['name']: p['volume_mm3'] for p in man['parts']}
            for n in AFFECTED:
                v_base = shapes_pre[n].volume
                v_cur = vol_now[n]
                removed = v_base - v_cur
                tot += removed
                s5b['per_member'][n] = {'baseline_mm3': round(v_base, 6),
                                        'current_mm3': v_cur,
                                        'removed_mm3': round(removed, 6)}
            s5b['removed_total_mm3'] = round(tot, 6)
            s5b['registered_removed_mm3'] = md['removed_volume_mm3']
            s5b['abs_diff'] = abs(tot - md['removed_volume_mm3'])
            # 纵梁单孔去除 59.232 复现
            per_hole = (s5b['per_member']['RB_longeron_1_1']['removed_mm3']) / 4
            s5b['longeron_per_hole_mm3'] = per_hole
            s5b['registered_per_hole_mm3'] = 59.232
            s5b['pass'] = (s5b['abs_diff'] < 1.0 and abs(per_hole - 59.232) < 1e-3)
        except Exception as e:  # noqa: BLE001
            s5b['pass'] = False
            s5b['error'] = str(e)[:300]
        finally:
            tmp.unlink(missing_ok=True)
            if str(ENG) in sys.path:
                sys.path.remove(str(ENG))
    checks['S5b_removed_recompute'] = s5b
    if not s5b['pass']:
        failures.append(f"S5b removed recompute fail: {s5b.get('abs_diff', s5b.get('error'))}")

    # S6 UNKNOWN 保留
    n_unknown = sum(1 for r in md['rows']
                    if ('UNKNOWN' in r['mass_basis'] or 'CANDIDATE' in r['mass_basis']))
    ok = (n_unknown == 24 and
          all(r['representation_role'] == 'SIMPLIFIED_PROXY' for r in md['rows']))
    checks['S6_unknown_preserved'] = {'rows_with_unknown_or_candidate': n_unknown, 'pass': ok}
    if not ok:
        failures.append('S6 UNKNOWN not fully preserved')

    # S7 NOT_RUN 八项语义
    nr = acc_sum['not_run']
    semantics = ['独立第三方复验', 'SHORT_ENGAGEMENT_REGISTERED', '防压套', 'UNSELECTED',
                 '公差堆叠', '工具路径实物回放', 'INTERLOCK_REGISTERED', '实物试配']
    missing = [s for s in semantics if not any(s in item for item in nr)]
    ok = (len(nr) == 8 and not missing)
    checks['S7_not_run'] = {'count': len(nr), 'missing_semantics': missing, 'pass': ok}
    if not ok:
        failures.append(f'S7 not_run count={len(nr)} missing={missing}')

    # S8 FAIL v1 归档完整
    v1log = LG / 's01b_probe_FAIL_v1.log'
    v2log = LG / 's01b_probe_v2.log'
    if not v1log.exists():
        checks['S8_fail_v1_archive'] = {'pass': False, 'reason': 'log missing'}
        failures.append('S8 v1 log missing')
    else:
        txt = v1log.read_text(encoding='utf-8')
        v2txt = v2log.read_text(encoding='utf-8') if v2log.exists() else ''
        n_hits = txt.count('HIT ')
        has_1637 = '16.370' in txt
        sc_ok = sidecar_ok(v1log)
        ih = acc_sum['iteration_history']
        ok = (n_hits == 4 and has_1637 and sc_ok and v2log.exists() and
              'hits 0' in v2txt and
              'probe_FAIL_v1' in ih and '16.37' in ih['probe_FAIL_v1'] and
              'hits 0' in ih['probe_v2'])
        checks['S8_fail_v1_archive'] = {'hit_lines': n_hits, 'has_16_37': has_1637,
                                        'sidecar_ok': sc_ok, 'v2_log_hits0': 'hits 0' in v2txt,
                                        'pass': ok}
        if not ok:
            failures.append('S8 FAIL v1 archive incomplete')

    # S9 上纵梁哈希变化属预期 + 柱面口径互锁
    xnote = acc_sum['cross_run_consistency']['longeron_step_vs_e2']
    cen = r30['hole_census']
    ok = ('哈希不一致属预期' in xnote and '实改上纵梁' in xnote and
          cen['RB_longeron_1_1']['yaxis_d3p4_faces'] == 14 and
          cen['RB_longeron_1_1']['yaxis_d3p4_axis_positions'] == 9 and
          r30['hole_census_ok'])
    checks['S9_longeron_hash_change_expected'] = {
        'note': xnote[:80], 'review_census_longeron': cen['RB_longeron_1_1'], 'pass': ok}
    if not ok:
        failures.append('S9 cross-run note/census mismatch')

    # S10 constraints_honored
    ch = acc_sum['constraints_honored']
    ok = (len(ch) == 6 and 'FAIL 不覆盖（探针 FAIL v1 归档 logs/s01b_probe_FAIL_v1.log）' in ch and
          '未执行 git 提交' in ch)
    checks['S10_constraints_honored'] = {'n_constraints': len(ch), 'pass': ok}
    if not ok:
        failures.append('S10 constraints check failed')

    n_pass = sum(1 for c in checks.values() if c['pass'])
    result = {'review': 'R07_E3_INDEPENDENT_REVERIFY', 'script': 'e3_r34_spotcheck.py',
              'reviewed_run': RUN.name, 'checks': checks,
              'spotcheck_pass_ratio': f'{n_pass}/{len(checks)}',
              'failures': failures, 'verdict': 'PASS' if not failures else 'FAIL',
              'elapsed_s': round(time.time() - t0, 3)}
    write_json(REV_EV / 'review_e3_spotcheck.json', result)
    print('verdict', result['verdict'], result['spotcheck_pass_ratio'])
    for k, v in checks.items():
        print(k, v['pass'])
    print('failures', failures)


if __name__ == '__main__':
    main()
