# -*- coding: utf-8 -*-
"""阶段一收口复验 B3/B4：R14 扰动对照独立复算 + 恢复态/污染/清洁度核查。
B3a 改名双射：基线回执（inputs 快照）vs 扰动回执（被审证据）实例 id 集合差集恰 4+4、
    *_-50 → *_-45 一一映射；实例总数 487 不变。
B3b 责任件局部效应：共同 id 逐行比对，差异行恰为责任件（甲板+segment0 角材），
    mass_kg 不变、COM x 负移且与解析 |dx|=n_hole·m_hole·5/mass 在 1% 内一致；
    segment1 角材与剪力网逐位不变；4 改名 fastener parent/mount/pn 映射/COM +5.000。
B3c 遗留字段无效：legacy 扰动回执与基线逐键相等（除 dependency_sha256.design_parameters.json）。
B3d 恢复 bit-identical：复现回执 sha == 基线 d220c702… == 现行 live 文件；git diff HEAD 为空。
B3e 正式 BOM.csv 未被扰动污染：live BOM.csv == R17 后哈希 a6ce5bff…（扰动试验不回写 BOM）。
B4  清洁度：git status 全仓；ENG 目录无残留临时/备份文件；全态回执与 R17 后哈希一致。"""
import json, subprocess, time
from pathlib import Path
from sc_common import (REV, RUN_B, ROOT, ENG, write_json, sha256_file, R17_AFTER,
                       PARAMS_SHA, BASELINE_STRUCTURE_RECEIPT_SHA)

RESULTS = ENG / 'results'


def rows_by_id(receipt):
    return {r['id']: r for r in receipt['instances']}


def main():
    t0 = time.time()
    result = {'review': 'STAGE1_CLOSURE_INDEPENDENT_REVERIFY/B_VALIDATOR_R14',
              'script': 'r_b3b4_r14_clean.py', 'reviewed_run': 'validator_integration_r14_20260919',
              'failures': [], 'verdict': None}
    base = json.loads((RUN_B / 'inputs' / 'r14_baseline_service_structure_instances.json').read_text(encoding='utf-8'))
    pert = json.loads((RUN_B / 'evidence' / 'r14_perturbed_receipt.json').read_text(encoding='utf-8'))
    cmp_e = json.loads((RUN_B / 'evidence' / 'r14_perturbation_compare.json').read_text(encoding='utf-8'))
    b_rows, p_rows = rows_by_id(base), rows_by_id(pert)

    # ---- B3a 改名双射 ----
    removed = sorted(set(b_rows) - set(p_rows))
    added = sorted(set(p_rows) - set(b_rows))
    bij = all(r.replace('-50', '-45') in added for r in removed) and \
          all(a.replace('-45', '-50') in removed for a in added)
    b3a = {'count_baseline': len(b_rows), 'count_perturbed': len(p_rows),
           'removed': removed, 'added': added,
           'removed_all_suffix_-50': all(r.endswith('_-50') and 'deck_fastener' in r for r in removed),
           'added_all_suffix_-45': all(a.endswith('_-45') and 'deck_fastener' in a for a in added),
           'rename_bijection': bij}
    b3a['pass'] = (b3a['count_baseline'] == 487 and b3a['count_perturbed'] == 487
                   and len(removed) == 4 and len(added) == 4 and bij
                   and b3a['removed_all_suffix_-50'] and b3a['added_all_suffix_-45'])
    result['B3a_rename_bijection'] = b3a
    if not b3a['pass']:
        result['failures'].append(f'B3a: {removed} {added}')

    # ---- B3b 责任件局部效应（逐行独立比对）----
    responsible = cmp_e['checks']['C2_responsible_parts_local_effect']['responsible_parts']
    diff_rows = {}
    for rid in sorted(set(b_rows) & set(p_rows)):
        if b_rows[rid] != p_rows[rid]:
            br, pr = b_rows[rid], p_rows[rid]
            changed_keys = sorted(k for k in set(br) | set(pr) if br.get(k) != pr.get(k))
            bm, pm = br.get('mass_kg'), pr.get('mass_kg')
            mass_rel = (abs(bm - pm) / abs(bm)) if (isinstance(bm, (int, float)) and isinstance(pm, (int, float)) and bm) else (0.0 if bm == pm else None)
            diff_rows[rid] = {'changed_keys': changed_keys,
                              'mass_rel_diff': mass_rel,
                              'mass_unchanged': bm == pm or (mass_rel is not None and mass_rel <= 1e-12),
                              'com_dx_mm': (pr['center_of_mass_S_mm'][0] - br['center_of_mass_S_mm'][0])
                              if br.get('center_of_mass_S_mm') and pr.get('center_of_mass_S_mm') else None}
    claimed_resp = set(responsible)
    com_checks = {}
    for rid, claim in responsible.items():
        meas = diff_rows.get(rid, {}).get('com_dx_mm')
        exp = claim['com_dx_expected_mm']
        com_checks[rid] = {
            'measured_dx': meas, 'claimed_dx': claim['com_dx_mm'],
            'analytic_expected_dx': exp,
            'measured_eq_claimed': meas == claim['com_dx_mm'],
            'within_1pct_of_analytic': (meas is not None and exp
                                        and abs(abs(meas) - abs(exp)) / abs(exp) <= 0.01),
            'moved_negative': meas is not None and meas < 0}
    # 改名 fastener 对偶件核查
    counterpart = {}
    for r in removed:
        a = r.replace('-50', '-45')
        br, pr = b_rows[r], p_rows[a]
        counterpart[a] = {
            'parent_same': br.get('parent_assembly') == pr.get('parent_assembly'),
            'mount_same': br.get('mount_interface') == pr.get('mount_interface'),
            'pn_maps': str(pr.get('pn', '')).endswith('-45') and str(br.get('pn', '')).endswith('-50')
                       and str(pr.get('pn', ''))[:-3] == str(br.get('pn', ''))[:-3],
            'mass_unchanged': br.get('mass_kg') == pr.get('mass_kg'),
            'com_dx_mm': pr['center_of_mass_S_mm'][0] - br['center_of_mass_S_mm'][0]}
    spot = cmp_e['checks']['C2_responsible_parts_local_effect']['unchanged_spot_checks']
    spot_ok = all(rid not in diff_rows for rid in spot)
    b3b = {'diff_row_ids': sorted(diff_rows),
           'diff_eq_responsible_set': set(diff_rows) == claimed_resp,
           'responsible_claimed': sorted(claimed_resp),
           'com_checks': com_checks,
           'mass_unchanged_all_diff_rows': all(v['mass_unchanged'] for v in diff_rows.values()),
           'mass_max_rel_diff': max((v['mass_rel_diff'] or 0.0) for v in diff_rows.values()),
           'mass_tolerance_note': 'mass_kg/volume_mm3 个别行为 1 ULP 浮点和序噪声（≤2.06e-16 相对），物理质量不变；判据取相对容差 1e-12',
           'counterpart_fasteners': counterpart,
           'segment1_shearweb_bit_identical': spot_ok,
           'changed_keys_union': sorted({k for v in diff_rows.values() for k in v['changed_keys']})}
    b3b['pass'] = (b3b['diff_eq_responsible_set'] and b3b['mass_unchanged_all_diff_rows']
                   and all(c['measured_eq_claimed'] and c['within_1pct_of_analytic'] and c['moved_negative']
                           for c in com_checks.values())
                   and all(v['parent_same'] and v['mount_same'] and v['pn_maps'] and v['mass_unchanged']
                           and abs(v['com_dx_mm'] - 5.0) < 1e-9 for v in counterpart.values())
                   and spot_ok)
    result['B3b_local_effect'] = b3b
    if not b3b['pass']:
        result['failures'].append(f'B3b: diff_rows={sorted(diff_rows)} com={com_checks}')

    # ---- B3c 遗留字段无效 ----
    legacy = json.loads((RUN_B / 'evidence' / 'r14_legacy_perturbed_receipt.json').read_text(encoding='utf-8'))
    keys_b, keys_l = set(base), set(legacy)
    diff_top = sorted(k for k in keys_b | keys_l if base.get(k) != legacy.get(k))
    b3c = {'top_level_diff_keys': diff_top,
           'only_params_dependency': diff_top == ['dependency_sha256'],
           'dep_diff_keys': sorted(k for k in set(base.get('dependency_sha256', {})) | set(legacy.get('dependency_sha256', {}))
                                   if base.get('dependency_sha256', {}).get(k) != legacy.get('dependency_sha256', {}).get(k))}
    b3c['pass'] = (b3c['only_params_dependency']
                   and b3c['dep_diff_keys'] == ['design_parameters.json'])
    result['B3c_legacy_field_inert'] = b3c
    if not b3c['pass']:
        result['failures'].append(f'B3c: {b3c}')

    # ---- B3d 恢复 bit-identical + git 对照 ----
    repro = json.loads((RUN_B / 'evidence' / 'r14_repro_receipt.json').read_text(encoding='utf-8'))
    repro_file_sha = sha256_file(RUN_B / 'evidence' / 'r14_repro_receipt.json')
    live_struct_sha = sha256_file(RESULTS / 'service_structure_instances.json')
    live_params_sha = sha256_file(ENG / 'design_parameters.json')
    gd = subprocess.run(['git', 'diff', 'HEAD', '--stat', '--',
                         '20_engineering/service_robot_wp03_spacecraft_body_r1'],
                        cwd=str(ROOT), capture_output=True, timeout=60)
    b3d = {'repro_receipt_file_sha': repro_file_sha,
           'baseline_sha': BASELINE_STRUCTURE_RECEIPT_SHA,
           'repro_eq_baseline': repro_file_sha == BASELINE_STRUCTURE_RECEIPT_SHA,
           'live_struct_sha': live_struct_sha,
           'live_eq_baseline': live_struct_sha == BASELINE_STRUCTURE_RECEIPT_SHA,
           'live_params_sha': live_params_sha,
           'live_params_eq_e4_pin': live_params_sha == PARAMS_SHA,
           'git_diff_head_eng': gd.stdout.decode('utf-8', 'replace').strip() or 'EMPTY',
           'note': '恢复态回执==基线的声明用 git 对照：live 文件 sha == d220c702… 且 git diff HEAD 为空'
                   '（d29b06d6 提交态即恢复态）'}
    b3d['pass'] = (b3d['repro_eq_baseline'] and b3d['live_eq_baseline']
                   and b3d['live_params_eq_e4_pin'] and b3d['git_diff_head_eng'] == 'EMPTY')
    result['B3d_restore_bit_identical'] = b3d
    if not b3d['pass']:
        result['failures'].append(f'B3d: {b3d}')

    # ---- B3e BOM 未污染 ----
    bom_sha = sha256_file(ENG / 'BOM.csv')
    b3e = {'live_bom_sha': bom_sha, 'r17_after_sha': R17_AFTER['BOM.csv'],
           'unpolluted': bom_sha == R17_AFTER['BOM.csv'],
           'note': 'R14 扰动 write_parts=False 不回写 BOM；现行 BOM 逐位 == R17 修复后交付态'}
    b3e['pass'] = b3e['unpolluted']
    result['B3e_bom_unpolluted'] = b3e
    if not b3e['pass']:
        result['failures'].append(f'B3e: {b3e}')

    # ---- B4 清洁度 ----
    gs = subprocess.run(['git', 'status', '--porcelain'], cwd=str(ROOT),
                        capture_output=True, timeout=60)
    status_lines = [ln for ln in gs.stdout.decode('utf-8', 'replace').splitlines() if ln.strip()]
    # ENG 目录非跟踪且未忽略文件盘点（__cadgen__/ 缓存由 .gitignore:19 覆盖，不计入清洁度）
    gl = subprocess.run(['git', 'ls-files', '--others', '--exclude-standard', '--',
                         '20_engineering/service_robot_wp03_spacecraft_body_r1'],
                        cwd=str(ROOT), capture_output=True, timeout=60)
    untracked_eng = sorted(ln.strip().replace('/', '\\')
                           for ln in gl.stdout.decode('utf-8', 'replace').splitlines() if ln.strip())
    receipts_now = {name: sha256_file(RESULTS / name)
                    for name in ('parking_instances.json', 'released_instances.json',
                                 'service_instances.json', 'parking_ground_instances.json',
                                 'DYNAMICS_HANDOFF.json', 'service_structure_instances.json')
                    if (RESULTS / name).is_file()}
    receipts_consistent = all(
        receipts_now.get(k) == v for k, v in {
            'parking_instances.json': R17_AFTER['parking_instances.json'],
            'released_instances.json': R17_AFTER['released_instances.json'],
            'service_instances.json': R17_AFTER['service_instances.json'],
            'parking_ground_instances.json': R17_AFTER['parking_ground_instances.json'],
            'DYNAMICS_HANDOFF.json': R17_AFTER['DYNAMICS_HANDOFF.json'],
            'service_structure_instances.json': BASELINE_STRUCTURE_RECEIPT_SHA}.items())
    b4 = {'git_status_porcelain': status_lines,
          'untracked_eng_files': untracked_eng,
          'expected_new_untracked': sorted([
              '20_engineering\\service_robot_wp03_spacecraft_body_r1\\strict_surface_integration.py',
              '20_engineering\\service_robot_wp03_spacecraft_body_r1\\results\\STRICT_SURFACE_INTEGRATION.json']),
          'receipts_now_sha': receipts_now,
          'receipts_consistent_with_r17_after': receipts_consistent}
    b4['pass'] = (sorted(untracked_eng) == b4['expected_new_untracked']
                  and receipts_consistent
                  and all(ln.startswith('?? ') for ln in status_lines))
    result['B4_workspace_cleanliness'] = b4
    if not b4['pass']:
        result['failures'].append(f'B4: untracked={untracked_eng} status={status_lines[:6]}')

    keys = ['B3a_rename_bijection', 'B3b_local_effect', 'B3c_legacy_field_inert',
            'B3d_restore_bit_identical', 'B3e_bom_unpolluted', 'B4_workspace_cleanliness']
    result['summary'] = {k.split('_')[0]: result[k]['pass'] for k in keys}
    result['verdict'] = 'PASS' if not result['failures'] else 'FAIL'
    result['elapsed_s'] = round(time.time() - t0, 3)
    write_json(REV / 'evidence' / 'review_b3b4_r14_clean.json', result)
    print('verdict', result['verdict'], json.dumps(result['summary'], ensure_ascii=False))
    print('failures', result['failures'])


if __name__ == '__main__':
    main()
