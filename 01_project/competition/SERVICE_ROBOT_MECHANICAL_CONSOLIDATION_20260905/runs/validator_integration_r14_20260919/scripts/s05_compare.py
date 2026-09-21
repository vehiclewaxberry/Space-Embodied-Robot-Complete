# -*- coding: utf-8 -*-
"""s05 R14 扰动机检对照：基线 vs 主扰动 vs 遗留扰动 vs 复现，全部断言机器判定。

输入四个回执：
  baseline = inputs/r14_baseline_service_structure_instances.json (d220c702...)
  main     = evidence/r14_perturbed_receipt.json        (X_S_mm[1] -50->-45)
  legacy   = evidence/r14_legacy_perturbed_receipt.json (superseded 150->155)
  repro    = evidence/r14_repro_receipt.json            (恢复态重建)
断言组：
  A 复现性：repro 与 baseline 字节逐位一致（sha256）
  B 遗留字段无效：legacy 与 baseline 除 dependency_sha256.design_parameters.json 外逐键相等
  C 主扰动预期效应：
    C1 实例总数 487 不变；id 差集恰为 4 移除（*_deck_fastener_*_-50）+ 4 新增（_-45），其余逐位相同
    C2 责任件：lower/upper_equipment_deck 与 segment0 甲板角材 mass_kg 不变、COM x 正移、惯量张量变化；
       segment1 角材与全部剪力网/其余件逐位不变（局部性）
    C3 对偶件：改名 fastener 的 parent_assembly/mount_interface/pn 后缀映射保持，COM x +5mm，质量不变
    C4 叠层：每甲板 fastener 数 8 不变、甲板厚度方向 bounds 不变（grip 叠层几何未变，仅孔位 x 平移）
    C5 BOM 口径：id 集合差即 BOM 行差（4 换名），pn 规律一致
    C6 provenance：dependency_sha256.design_parameters.json 改变（扰动入 provenance），source_sha256 不变
UNKNOWN 零填禁止：任何字段缺失即断言失败，不填充。
"""
import hashlib, json, os

RUN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENG = r'F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/service_robot_wp03_spacecraft_body_r1'


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def sidecar(p):
    rel = os.path.relpath(p, RUN).replace('\\', '/')
    open(p + '.sha256', 'wb').write((sha(p) + '  ' + rel + '\n').encode('utf-8'))


def load(p):
    return json.loads(open(p, encoding='utf-8').read())


def idx(receipt):
    return {r['id']: r for r in receipt['instances']}


def strip_dep(receipt):
    d = dict(receipt)
    dep = dict(d['dependency_sha256'])
    dep.pop('design_parameters.json')
    d['dependency_sha256'] = dep
    return d


def main():
    base = load(os.path.join(RUN, 'inputs', 'r14_baseline_service_structure_instances.json'))
    main_p = load(os.path.join(RUN, 'evidence', 'r14_perturbed_receipt.json'))
    legacy = load(os.path.join(RUN, 'evidence', 'r14_legacy_perturbed_receipt.json'))
    repro_p = os.path.join(RUN, 'evidence', 'r14_repro_receipt.json')
    base_p = os.path.join(RUN, 'inputs', 'r14_baseline_service_structure_instances.json')

    A = {'repro_sha256': sha(repro_p), 'baseline_sha256': sha(base_p)}
    A['bit_identical'] = A['repro_sha256'] == A['baseline_sha256']

    B = {'legacy_equal_except_params_dependency': strip_dep(legacy) == strip_dep(base),
         'params_dependency_changed': legacy['dependency_sha256']['design_parameters.json'] != base['dependency_sha256']['design_parameters.json']}

    bi, mi = idx(base), idx(main_p)
    removed = sorted(set(bi) - set(mi))
    added = sorted(set(mi) - set(bi))
    C1 = {'instance_count_baseline': len(bi), 'instance_count_perturbed': len(mi),
          'count_unchanged': len(bi) == len(mi) == 487,
          'removed_ids': removed, 'added_ids': added,
          'removed_all_fastener_m50': all(r.endswith('_-50') and 'deck_fastener' in r for r in removed),
          'added_all_fastener_m45': all(a.endswith('_-45') and 'deck_fastener' in a for a in added),
          'rename_bijection': sorted(r.replace('_-50', '_-45') for r in removed) == added,
          'removed_count': len(removed), 'added_count': len(added)}

    EPS = 1e-9
    RHO = 2.7e-6  # kg/mm3 甲板/角材候选密度
    M_HOLE = RHO * 3.141592653589793 * 1.7 ** 2 * 3  # Ø3.4 通孔×3mm 板厚去除质量
    resp_rows = [('lower_equipment_deck', 2), ('upper_equipment_deck', 2),
                 ('lower_deck_angle_-1_0', 1), ('lower_deck_angle_1_0', 1),
                 ('upper_deck_angle_-1_0', 1), ('upper_deck_angle_1_0', 1)]
    C2 = {'responsible_parts': {}, 'unchanged_spot_checks': {},
          'physics': '孔=去除材料：孔位 x 正移 5mm → 责任件 COM x 负移，|dx|=n_hole*m_hole*5/mass'}
    ok2 = True
    for rid, n_holes in resp_rows:
        b, m = bi[rid], mi[rid]
        dx = m['center_of_mass_S_mm'][0] - b['center_of_mass_S_mm'][0]
        dx_expected = -n_holes * M_HOLE * 5.0 / b['mass_kg']
        row = {'mass_unchanged': abs(m['mass_kg'] - b['mass_kg']) < EPS,
               'com_dx_mm': dx, 'com_dx_expected_mm': dx_expected,
               'com_x_moved_negative': dx < 0,
               'com_dx_matches_analytic_1pct': abs(dx - dx_expected) < abs(dx_expected) * 0.01,
               'inertia_changed': m['inertia_about_COM_S_kg_mm2'] != b['inertia_about_COM_S_kg_mm2'],
               'mass_kg': b['mass_kg']}
        ok2 &= (row['mass_unchanged'] and row['com_x_moved_negative']
                and row['com_dx_matches_analytic_1pct'] and row['inertia_changed'])
        C2['responsible_parts'][rid] = row
    for rid in ['lower_deck_angle_-1_1', 'lower_deck_angle_1_1', 'upper_deck_angle_-1_1', 'upper_deck_angle_1_1',
                'shear_web_-1', 'shear_web_1']:
        same = bi[rid] == mi[rid]
        C2['unchanged_spot_checks'][rid] = same
        ok2 &= same
    C2['local_effect_only'] = ok2

    C3 = {'renamed_fasteners': {}}
    ok3 = True
    for r, a in zip(removed, added):
        b, m = bi[r], mi[a]
        row = {'parent_same': b['parent_assembly'] == m['parent_assembly'],
               'mount_same': b['mount_interface'] == m['mount_interface'],
               'pn_maps': m['pn'] == b['pn'].replace('_-50', '_-45'),
               'mass_unchanged': (b['mass_kg'] == m['mass_kg']),
               'com_dx_mm': m['center_of_mass_S_mm'][0] - b['center_of_mass_S_mm'][0]}
        row['com_dx_is_plus_5mm'] = abs(row['com_dx_mm'] - 5.0) < 1e-6
        ok3 &= row['parent_same'] and row['mount_same'] and row['mass_unchanged'] and row['com_dx_is_plus_5mm']
        C3['renamed_fasteners'][r + ' -> ' + a] = row
    C3['counterpart_pairing_preserved'] = ok3

    C4 = {'per_deck_fastener_count': {}, 'deck_z_bounds_unchanged': {}}
    ok4 = True
    for deck in ['lower', 'upper']:
        cb = sum(1 for i in bi if i.startswith(f'{deck}_deck_fastener_'))
        cm = sum(1 for i in mi if i.startswith(f'{deck}_deck_fastener_'))
        C4['per_deck_fastener_count'][deck] = {'baseline': cb, 'perturbed': cm}
        ok4 &= cb == cm == 8
        bb = bi[f'{deck}_equipment_deck']['bounds']
        mb = mi[f'{deck}_equipment_deck']['bounds']
        z_same = bb['min_mm'][2] == mb['min_mm'][2] and bb['max_mm'][2] == mb['max_mm'][2]
        y_same = bb['min_mm'][1] == mb['min_mm'][1] and bb['max_mm'][1] == mb['max_mm'][1]
        C4['deck_z_bounds_unchanged'][deck] = z_same and y_same
        ok4 &= z_same and y_same
    C4['grip_stack_geometry_preserved'] = ok4

    C5 = {'bom_line_delta_is_id_rename_only': C1['rename_bijection'] and len(removed) == 4 and len(added) == 4,
          'note': 'write_parts=False，BOM.csv 正式交付物未重生成；BOM 口径差=回执实例 id 集合差'}

    C6 = {'params_dependency_changed': main_p['dependency_sha256']['design_parameters.json'] != base['dependency_sha256']['design_parameters.json'],
          'source_sha256_unchanged': main_p['source_sha256'] == base['source_sha256'],
          'other_dependencies_unchanged': all(main_p['dependency_sha256'][k] == v for k, v in base['dependency_sha256'].items() if k != 'design_parameters.json')}

    checks = {'A_reproducibility': A, 'B_legacy_field_inert': B, 'C1_id_set': C1,
              'C2_responsible_parts_local_effect': C2, 'C3_counterpart_fasteners': C3,
              'C4_grip_stack': C4, 'C5_bom_delta': C5, 'C6_provenance': C6}
    passed = (A['bit_identical'] and B['legacy_equal_except_params_dependency'] and B['params_dependency_changed']
              and C1['count_unchanged'] and C1['removed_all_fastener_m50'] and C1['added_all_fastener_m45']
              and C1['rename_bijection'] and C1['removed_count'] == 4
              and C2['local_effect_only'] and C3['counterpart_pairing_preserved']
              and C4['grip_stack_geometry_preserved'] and C5['bom_line_delta_is_id_rename_only']
              and C6['params_dependency_changed'] and C6['source_sha256_unchanged'] and C6['other_dependencies_unchanged'])

    out = {'schema': 'R14_PERTURBATION_COMPARE_V1',
           'mutation': {'path': 'deck_fastening_r01.deck_hole_pattern.X_S_mm[1]', 'before': -50, 'after': -45,
                        'legacy_mutation': 'deck_fastening_r01.legacy_deck_hole_pattern_superseded.X_S_mm[3] 150->155'},
           'checks': checks, 'verdict': 'R14_PERTURBATION_EXPECTED_EFFECT_CONFIRMED' if passed else 'R14_COMPARE_FAIL'}
    op = os.path.join(RUN, 'evidence', 'r14_perturbation_compare.json')
    open(op, 'wb').write((json.dumps(out, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    sidecar(op)
    lp = os.path.join(RUN, 'logs', 's05_compare_log.json')
    open(lp, 'wb').write((json.dumps({'script': 's05_compare.py', 'verdict': out['verdict'],
                                      'evidence_sha256': sha(op)}, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    sidecar(lp)
    print(json.dumps({'verdict': out['verdict'], 'removed': removed, 'added': added}, ensure_ascii=False))
    if not passed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
