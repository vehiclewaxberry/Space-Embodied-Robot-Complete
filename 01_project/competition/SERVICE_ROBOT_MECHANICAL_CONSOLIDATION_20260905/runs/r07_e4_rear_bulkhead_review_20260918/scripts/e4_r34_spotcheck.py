# -*- coding: utf-8 -*-
"""R07-E4 独立复验 r34：ACCEPTANCE_SUMMARY 抽验（S1-S10）+ 供应方侧未动实证。
只读被审证据与本人 r30-r33 证据；S9/S10 各需一次 build（当前/git 旧态），临时文件 finally unlink。
S7 说明：任务书表述"九项"，实际 not_run 8 条——按实际条数核对语义覆盖，计数差异如实登记。"""
import json, math, sys, time, subprocess, hashlib, importlib.util
from pathlib import Path
from e4_common import (REV, RUN, ENG, E4_COMMIT, write_json, sha256_file, bbox,
                       load_params)

TMP = ENG / '_review_pre_e4_tmp_s34.py'
REL_SM = '20_engineering/service_robot_wp03_spacecraft_body_r1/spacecraft_model.py'


def norm_lf(b):
    return b.replace(b'\r\n', b'\n')


def main():
    t0 = time.time()
    S = json.loads((RUN / 'ACCEPTANCE_SUMMARY.json').read_text(encoding='utf-8'))
    acc_b = json.loads((RUN / 'evidence' / 'acc_interference_boolean.json').read_text(encoding='utf-8'))
    acc_r = json.loads((RUN / 'evidence' / 'acc_readback_holes_coaxial.json').read_text(encoding='utf-8'))
    bom = json.loads((RUN / 'evidence' / 'e4_bom_mass_delta.json').read_text(encoding='utf-8'))
    s07 = json.loads((RUN / 'logs' / 's07_build_smoke_log.json').read_text(encoding='utf-8'))
    r30 = json.loads((REV / 'evidence' / 'review_e4_readback.json').read_text(encoding='utf-8'))
    r32 = json.loads((REV / 'evidence' / 'review_e4_preexisting.json').read_text(encoding='utf-8'))
    r32b = json.loads((REV / 'evidence' / 'review_e4_git_baseline.json').read_text(encoding='utf-8'))
    r33 = json.loads((REV / 'evidence' / 'review_e4_scan.json').read_text(encoding='utf-8'))
    result = {'review': 'R07_E4_INDEPENDENT_REVERIFY', 'script': 'e4_r34_spotcheck.py',
              'reviewed_run': RUN.name, 'checks': {}, 'failures': [], 'verdict': None}

    def rec(key, ok, detail):
        result['checks'][key] = {'pass': bool(ok), 'detail': detail}
        if not ok:
            result['failures'].append(f'{key}: {json.dumps(detail, ensure_ascii=False)[:300]}')

    # S1 烟测 487=483+4（s07 日志 + r33 独立 build 实例数互锁）
    ok = (s07['baseline_instances_e3_closed'] == 483 and s07['expected_instances'] == 487
          and s07['actual_instances'] == 487 and s07['e4_instances'] == 4
          and s07['e4_breakdown'] == {'clamp_sleeve': 4}
          and s07['modified_screw_instances_same_name_replaced'] == 4
          and r33['build_instance_count'] == 487)
    rec('S1_smoke_487_eq_483_plus_4', ok,
        {'s07': {k: s07[k] for k in ('baseline_instances_e3_closed', 'expected_instances',
                                     'actual_instances', 'e4_instances')},
         'review_r33_build_instance_count': r33['build_instance_count']})

    # S2 同轴 0.0（被审 v2 coaxial_pairs 逐项取最大 + 本人 r30 24 对互锁）
    acc_pairs = []
    for cp in acc_r.get('coaxial_pairs', []):
        for k, v in cp.items():
            if isinstance(v, dict) and 'axis_offset_mm' in v:
                acc_pairs.append(v)
    acc_max_off = max((p.get('axis_offset_mm', 0.0) for p in acc_pairs), default=None)
    acc_max_par = max((p.get('parallel_deviation', 0.0) for p in acc_pairs), default=None)
    ok = (acc_r.get('verdict') == 'PASS'
          and acc_pairs and acc_max_off == 0.0 and acc_max_par == 0.0
          and r30['summary']['coaxial_pairs'] == 24 and r30['summary']['coaxial_all_zero'])
    rec('S2_coaxial_zero', ok,
        {'acc_v2_pairs': len(acc_pairs), 'acc_v2_max_offset': acc_max_off,
         'acc_v2_max_par': acc_max_par,
         'review_r30': r30['summary']})

    # S3 登记表行数 4/4/4/4（独立数行）
    rows = {}
    for key, fn in (('dual_hole_pairs', 'e4_dual_hole_pairs_4.json'),
                    ('fastener_stacks', 'e4_fastener_stacks_4.json'),
                    ('mounting_surfaces', 'e4_mounting_surfaces.json'),
                    ('tool_paths', 'e4_tool_paths.json')):
        d = json.loads((RUN / 'evidence' / fn).read_text(encoding='utf-8'))
        n = None
        if isinstance(d, list):
            n = len(d)
        elif isinstance(d, dict):
            if isinstance(d.get('rows'), list):
                n = len(d['rows'])
            elif 'row_count' in d:
                n = d['row_count']
            else:
                for v in d.values():
                    if isinstance(v, list):
                        n = len(v)
                        break
        rows[key] = n
    ok = (rows == {'dual_hole_pairs': 4, 'fastener_stacks': 4,
                   'mounting_surfaces': 4, 'tool_paths': 4}
          and S['registration_tables']['dual_hole_pairs_rows'] == 4
          and S['registration_tables']['fastener_stacks_rows'] == 4
          and S['registration_tables']['mounting_surfaces_rows'] == 4
          and S['registration_tables']['tool_paths_rows'] == 4)
    rec('S3_registration_rows_4x4', ok, rows)

    # S4 布尔口径（OCP 方法字样 + A30/B4/38 + r33 互锁）
    ok = ('OCP BRepAlgoAPI_Common' in acc_b['authoritative_method']
          and acc_b['pairs'] == {'A_e4_vs_other': 30, 'B_e4_vs_e4': 4}
          and len(acc_b['explicit_clearance_checks']) == 38
          and acc_b['positives'] == [] and acc_b['max_common_volume_mm3'] == 0.0
          and r33['verdict'] == 'PASS' and r33['summary']['pair_counts_match_candidate']
          and r33['summary']['new_positives'] == 0 and r33['summary']['clearance_fail'] == 0)
    rec('S4_boolean_method_counts', ok,
        {'method': acc_b['authoritative_method'][:80], 'pairs': acc_b['pairs'],
         'review_r33': r33['summary']})

    # S5 质量复算（夹套质量/ΔV 解析互证 + 行口径）
    v_sleeve_sum = sum(p['volume_mm3'] for p in bom['added_parts'])
    m_expect = v_sleeve_sum * 2.7e-6
    dv_expect = math.pi * 2.0**2 * 8
    ok = (len(bom['added_parts']) == 4 and len(bom['modified_parts']) == 4
          and abs(v_sleeve_sum - bom['added_volume_mm3']) <= 1e-9
          and abs(bom['added_volume_mm3'] - 1572.241459415548) <= 1e-9
          and abs(bom['added_sleeve_al_candidate_mass_kg'] - m_expect) <= 1e-15
          and abs(bom['added_sleeve_al_candidate_mass_kg'] - 0.00424505194042198) <= 1e-15
          and all(p['mass_kg_allocated'] is not None and p['representation_role'] == 'PHYSICAL_GEOMETRY'
                  for p in bom['added_parts'])
          and all(p['mass_kg_allocated'] is None and p['representation_role'] == 'SIMPLIFIED_PROXY'
                  and p['mass_basis'] == 'THREADLESS_FASTENER_UNSELECTED'
                  for p in bom['modified_parts'])
          and all(abs(p['delta_volume_mm3'] - dv_expect) <= 1e-9 for p in bom['modified_parts'])
          and all(abs(p['volume_after_mm3'] - p['volume_before_mm3'] - p['delta_volume_mm3']) <= 1e-9
                  for p in bom['modified_parts'])
          and abs(bom['volume_before_mm3'] if False else bom['modified_parts'][0]['volume_before_mm3'] - 430.3981935418017) <= 1e-9
          and abs(bom['modified_parts'][0]['volume_after_mm3'] - 530.9291584566749) <= 1e-9
          and bom['removed_volume_mm3'] == 0.0
          and abs(bom['net_allocated_mass_delta_kg'] - bom['added_sleeve_al_candidate_mass_kg']) <= 1e-18)
    rec('S5_mass_delta', ok,
        {'sleeve_volume_sum_mm3': v_sleeve_sum, 'mass_recomputed_kg': m_expect,
         'registered_mass_kg': bom['added_sleeve_al_candidate_mass_kg'],
         'delta_v_per_piece_analytic': dv_expect,
         'delta_v_registered': bom['modified_parts'][0]['delta_volume_mm3'],
         'net_allocated': bom['net_allocated_mass_delta_kg']})

    # S6 UNKNOWN/UNSELECTED 保留（参数块 + 摘要字样）
    P, _ = load_params()
    e4p = P['rear_bulkhead_clamp_r07_e4']
    ok = ('UNKNOWN' in e4p['status'] and 'UNSELECTED' in e4p['rear_screw']['thread']
          and 'UNKNOWN' in e4p['rear_screw']['material_grade_preload_locking_engagement']
          and 'UNKNOWN' in e4p['clamp_sleeve']['material']
          and 'UNKNOWN' in bom['material_status']
          and 'NOT_ALLOCATED' in S['design']['modified_screw']['mass_status']
          and all(p['mass_basis'] == 'THREADLESS_FASTENER_UNSELECTED' for p in bom['modified_parts'])
          and 'UNKNOWN' in S['design']['clamp_sleeve']['mass_status'])
    rec('S6_unknown_preserved', ok,
        {'param_status': e4p['status'][:120], 'thread': e4p['rear_screw']['thread'],
         'sleeve_material': e4p['clamp_sleeve']['material'][:100]})

    # S7 NOT_RUN 实际 8 条 + 语义覆盖（任务书"九项"计数差异如实登记）
    nr = S['not_run']
    topics = {'独立复验': '独立第三方复验', '载荷夹紧': '载荷/强度校核', '选型材料': '紧固件选型',
              'ICD': '供应方侧 ICD', '制造性': '制造性审查', '工具回放': '工具路径实物回放',
              'OUT_OF_SCOPE': 'front_service_cover', '实物': '实物试配'}
    coverage = {k: any(t in e for e in nr) for k, t in topics.items()}
    ok = (len(nr) == 8 and all(coverage.values()))
    rec('S7_not_run_coverage', ok,
        {'actual_count': len(nr), 'brief_wording': '任务书表述"九项"',
         'count_discrepancy_note': ('实际 8 条：任务书九项表述与实际条数差 1；'
                                    '语义覆盖 8 主题全到位（"部署器对接实物验证；实物试配/装配"合并一条），'
                                    '计数差异如实登记（观察项候选）'),
         'coverage': coverage})

    # S8 v1 FAIL 归档链
    v1 = RUN / 'evidence' / 'acc_readback_holes_coaxial_v1_fail.json'
    v1j = json.loads(v1.read_text(encoding='utf-8')) if v1.exists() else {}
    v1_side = Path(str(v1) + '.sha256')
    side_ok = False
    if v1_side.exists():
        h, rel = v1_side.read_text(encoding='utf-8').strip().split('  ', 1)
        side_ok = (h == hashlib.sha256(v1.read_bytes()).hexdigest()
                   and rel == 'evidence/acc_readback_holes_coaxial_v1_fail.json')
    ih = S.get('iteration_history', {})
    ok = (v1.exists() and v1j.get('verdict') == 'FAIL'
          and len(v1j.get('failures', [])) == 8
          and side_ok and acc_r.get('verdict') == 'PASS'
          and 's05_readback_FAIL_v1' in ih and 's05_readback_v2_fix' in ih
          and 'bb.min.X' in ih['s05_readback_FAIL_v1'] and 'bb.max.X' in ih['s05_readback_v2_fix'])
    rec('S8_v1_fail_archive', ok,
        {'v1_exists': v1.exists(), 'v1_verdict': v1j.get('verdict'),
         'v1_failures': len(v1j.get('failures', [])), 'v1_sidecar_valid': side_ok,
         'v2_verdict': acc_r.get('verdict'), 'iteration_history_keys': list(ih.keys())})

    # S9 尖端 -161 逐位（r30 + r32b + git 旧态 build 基线螺钉 bbox max.X 直测）
    ok30 = all(v['pass'] for v in r30['screw_tip_engagement'].values())
    ok32b = r32b['summary']['core_prediction'].startswith('CONFIRMED')
    old_src = subprocess.run(['git', 'show', f'{E4_COMMIT}^:{REL_SM}'], cwd=str(REV.parents[4]),
                             capture_output=True, timeout=60)
    tip_git = None
    if old_src.returncode == 0:
        TMP.write_bytes(old_src.stdout)
        try:
            sys.path.insert(0, str(ENG))
            spec = importlib.util.spec_from_file_location('spacecraft_model_pre_e4_s34', str(TMP))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            model, shapes, receipt = mod.build('service', include_arm=False)
            tips = {n: (bbox(s)[0], bbox(s)[3]) for n, s in shapes.items()
                    if n.startswith('RB_end_screw_')}
            tip_git = tips
        finally:
            try:
                TMP.unlink()
            except FileNotFoundError:
                pass
    # 后场螺钉朝 +x：尖端在 bbox max.X=-161；前场螺钉朝 -x：尖端在 bbox min.X=+161（头在 max 侧 +187）
    rear_tips_ok = tip_git and all(tip_git[f'RB_end_screw_-1_{sy}_{sz}'][1] == -161.0
                                   for sy in (-1, 1) for sz in (-1, 1))
    front_tips_ok = tip_git and all(tip_git[f'RB_end_screw_1_{sy}_{sz}'][0] == 161.0
                                    for sy in (-1, 1) for sz in (-1, 1))
    ok = ok30 and ok32b and bool(rear_tips_ok) and bool(front_tips_ok)
    rec('S9_tip_minus_161_bit_exact', ok,
        {'r30_screw_pass': ok30, 'r32b_core': r32b['summary']['core_prediction'],
         'git_baseline_rear_tip_max_x': {k: v[1] for k, v in (tip_git or {}).items()
                                         if k.startswith('RB_end_screw_-1_')},
         'git_baseline_front_tip_min_x_unique': sorted({v[0] for k, v in (tip_git or {}).items()
                                                        if k.startswith('RB_end_screw_1_')}),
         'orientation_note': '前场螺钉朝 -x，尖端在 bbox min.X=+161（头侧 max.X=+187），非 ±161 对称 bug'})

    # S10 供应方侧未动 + constraints 7 条（root_structure 钉固 + 当前 build 占位件 bbox）
    rs_sha = sha256_file(ENG / 'root_structure.py')
    man = json.loads((RUN / 'inputs' / 'INPUT_MANIFEST.json').read_text(encoding='utf-8'))
    rs_expect = {f['snapshot'].split('/')[-1]: f['snapshot_sha256']
                 for f in man['files']}['root_structure.py']
    sys.path.insert(0, str(ENG))
    import spacecraft_model as sm
    model, shapes, receipt = sm.build('service', include_arm=False)
    supplier = {}
    for n in ('launch_interface_reserved_volume', 'rear_vertical_rib_86', 'rear_vertical_rib_-86'):
        if n in shapes:
            supplier[n] = [round(x, 3) for x in bbox(shapes[n])]
    ribs_ok = all(abs(supplier[n][0] - (-195.0)) < 1e-6 and abs(supplier[n][3] - (-189.0)) < 1e-6
                  for n in ('rear_vertical_rib_86', 'rear_vertical_rib_-86') if n in supplier)
    rsv = supplier.get('launch_interface_reserved_volume')
    rsv_ok = rsv and abs(rsv[0] - (-215.0)) < 1e-6 and abs(rsv[3] - (-195.0)) < 1e-6
    ch = S.get('constraints_honored', [])
    ok = (rs_sha == rs_expect and ribs_ok and bool(rsv_ok) and len(ch) == 7
          and 'OUT_OF_SCOPE' in S['geometric_truth_registration']['front_cover_out_of_scope'])
    rec('S10_supplier_side_untouched', ok,
        {'root_structure_sha_match_snapshot': rs_sha == rs_expect,
         'supplier_bboxes': supplier, 'constraints_count': len(ch),
         'constraints': ch})

    n_pass = sum(1 for c in result['checks'].values() if c['pass'])
    result['summary'] = {'checks': len(result['checks']), 'passed': n_pass,
                         'consistency': f'{n_pass}/{len(result["checks"])}'}
    result['verdict'] = 'PASS' if not result['failures'] else 'FAIL'
    result['elapsed_s'] = round(time.time() - t0, 3)
    write_json(REV / 'evidence' / 'review_e4_spotcheck.json', result)
    print('verdict', result['verdict'], result['summary'])
    for k, c in result['checks'].items():
        print(k, 'PASS' if c['pass'] else 'FAIL')
    print('failures', result['failures'])


if __name__ == '__main__':
    main()
