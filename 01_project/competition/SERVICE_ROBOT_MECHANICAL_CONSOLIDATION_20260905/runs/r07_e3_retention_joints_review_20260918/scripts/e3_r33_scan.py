# -*- coding: utf-8 -*-
"""R07-E3 独立复验 r33：24 新件 + 8 改件新增干涉扫描（布尔口径，独立编码）。
基底钉固：ENG 源码/参数 sha256 须逐位等于 EXPORT_MANIFEST 登记构建源，否则不开扫。
范围（与被审登记口径对齐但独立实现；布尔一律 OCP 原生，勘误 O2）：
  A) 24 E3 件 vs 全部 PHYSICAL_GEOMETRY+SIMPLIFIED_PROXY 实例（bbox 预筛 + common 体积）；
  B) 24 E3 件两两；
  C) 8 改件（2 上纵梁 + 2 横梁 + 2 耳座_-94.15 + 2 足叉）vs 全部物理/代理实例；
  D) 被审登记 80 项具名让隙检查逐项独立复算（名单从被审 acc 文件读出）；
  E) E3 vs E1/E2 件互避：bbox 命中对计数 + 具名解析（clamp x/z vs E1 梁栓/桥栓无交叠）。
预期：新阳性 0；E1 结转对/49.71 惯例对不含 E3 或改件双方，不会在本扫描出现（r32 具名互锁）。
FUNCTIONAL_ENVELOPE 不作判据。"""
import json, sys, time, itertools
from pathlib import Path
from e3_common import (REV, RUN, ENG, write_json, bbox, overlap, common_volume,
                       sha256_file, load_params, stations,
                       PARAMS_SHA256_EXPECT, SOURCE_SHA256_EXPECT)

TOL = 1e-6
E3PREFIX = 'e3_'
AFFECTED = ['RB_longeron_1_1', 'RB_longeron_-1_1',
            'hold_crossbeam_0', 'hold_crossbeam_1',
            'hold_roof_lug_0_-94.15', 'hold_roof_lug_1_-94.15',
            'hold_pivot_clevis_0', 'hold_pivot_clevis_1']


def main():
    t0 = time.time()
    src_hash = sha256_file(ENG / 'spacecraft_model.py')
    P, params_hash = load_params()
    pin = {'spacecraft_model.py': {'actual': src_hash, 'expect': SOURCE_SHA256_EXPECT,
                                   'ok': src_hash == SOURCE_SHA256_EXPECT},
           'design_parameters.json': {'actual': params_hash, 'expect': PARAMS_SHA256_EXPECT,
                                      'ok': params_hash == PARAMS_SHA256_EXPECT}}
    result = {'review': 'R07_E3_INDEPENDENT_REVERIFY', 'script': 'e3_r33_scan.py',
              'reviewed_run': RUN.name, 'basis_pin': pin, 'tolerance_mm3': TOL,
              'pairs': {'A_e3_vs_other': 0, 'B_e3_vs_e3': 0, 'C_affected_vs_other': 0},
              'positives_new': [], 'errors': [], 'explicit_clearance_checks': [],
              'e3_vs_e1_bbox_pairs': 0, 'e3_vs_e2_bbox_pairs': 0,
              'e1_avoidance_analytic': {}, 'failures': [], 'verdict': None}
    if not all(v['ok'] for v in pin.values()):
        result['failures'].append('basis pin mismatch - scan aborted')
        result['verdict'] = 'FAIL'
        write_json(REV / 'evidence' / 'review_e3_scan.json', result)
        print('ABORT: basis pin mismatch', pin)
        return

    sys.path.insert(0, str(ENG))
    import spacecraft_model as sm
    model, shapes, receipt = sm.build('service', include_arm=False)
    reps = {r['id']: r['representation_role'] for r in receipt['instances']}
    e3parts = sorted(n for n in shapes if n.startswith(E3PREFIX))
    others = {n: s for n, s in shapes.items()
              if reps.get(n) in ('PHYSICAL_GEOMETRY', 'SIMPLIFIED_PROXY')
              and not n.startswith(E3PREFIX)}
    env_n = sum(1 for n in shapes if reps.get(n) == 'FUNCTIONAL_ENVELOPE')
    result['e3_part_count'] = len(e3parts)
    result['other_count'] = len(others)
    result['functional_envelopes_excluded_count'] = env_n
    result['build_instance_count'] = len(receipt['instances'])
    if len(e3parts) != 24:
        result['failures'].append(f'e3 part count {len(e3parts)} != 24')
    bb = {n: bbox(s) for n, s in shapes.items()}

    def run_pair(n1, s1, n2, s2, cat):
        v = common_volume(s1, s2)
        if isinstance(v, dict):
            result['errors'].append({'pair': [n1, n2], **v})
            return
        result['pairs'][cat] += 1
        if cat == 'A_e3_vs_other':
            if n2.startswith('e1_anchor_'):
                result['e3_vs_e1_bbox_pairs'] += 1
            if n2.startswith('e2_'):
                result['e3_vs_e2_bbox_pairs'] += 1
        if v > TOL:
            result['positives_new'].append({'pair': [n1, n2], 'common_volume_mm3': v,
                                            'category': cat})

    for na in e3parts:
        for no, so in others.items():
            if overlap(bb[na], bb[no]):
                run_pair(na, shapes[na], no, so, 'A_e3_vs_other')
    for n1, n2 in itertools.combinations(e3parts, 2):
        if overlap(bb[n1], bb[n2]):
            run_pair(n1, shapes[n1], n2, shapes[n2], 'B_e3_vs_e3')
    for nm in AFFECTED:
        if nm not in shapes:
            result['failures'].append(f'affected member {nm} not in build')
            continue
        for no, so in others.items():
            if no == nm:
                continue
            if overlap(bb[nm], bb[no]):
                run_pair(nm, shapes[nm], no, so, 'C_affected_vs_other')

    # D) 被审 80 项具名让隙逐项复算
    acc = json.loads((RUN / 'evidence' / 'acc_interference_boolean.json').read_text(encoding='utf-8'))
    for chk in acc['explicit_clearance_checks']:
        a, b = chk['a'], chk['b']
        if a not in shapes or b not in shapes:
            result['failures'].append(f'clearance pair missing in build: {a} vs {b}')
            continue
        v = common_volume(shapes[a], shapes[b])
        ok = (not isinstance(v, dict)) and v <= TOL
        result['explicit_clearance_checks'].append(
            {'pair_id': chk['pair_id'], 'a': a, 'b': b, 'intent': chk['intent'],
             'registered_mm3': chk['common_volume_mm3'],
             'review_mm3': None if isinstance(v, dict) else v, 'pass': ok})
        if isinstance(v, dict):
            result['errors'].append({'pair': [a, b], **v})
        elif not ok:
            result['positives_new'].append({'pair': [a, b], 'common_volume_mm3': v,
                                            'category': 'D_named_clearance',
                                            'intent': chk['intent']})

    # E) E3 边1 vs E1 栓位解析互避（参数块登记的 x/z 集合无交叠）
    e3p = P['retention_joints_r07_e3']
    e1_xz = {(15.5, 105.3), (24.5, 105.3), (154.85, 105.3), (146.0, 110.15), (154.85, 110.15)}
    e3_xz = {(float(b['x_S_mm']), 103.65)
             for g in e3p['edge1_clamp']['groups'] for b in g['bolts']}
    inter = e3_xz & e1_xz
    min_x_gap = min(abs(x3 - x1) for x3, _ in e3_xz for x1, _ in e1_xz)
    result['e1_avoidance_analytic'] = {
        'e3_clamp_xz': sorted(e3_xz), 'e1_bolt_xz': sorted(e1_xz),
        'xz_intersection': sorted(inter), 'min_x_gap_mm': min_x_gap,
        'registered_note': e3p['registered_constraints']['e1_bolt_avoidance'],
        'pass': not inter and min_x_gap > 10}
    if not result['e1_avoidance_analytic']['pass']:
        result['failures'].append('E1 avoidance analytic fail')

    n_new = len(result['positives_new'])
    n_clr_fail = sum(1 for c in result['explicit_clearance_checks'] if not c['pass'])
    if result['positives_new']:
        result['failures'].append(f"new positives: {result['positives_new'][:5]}")
    if result['errors']:
        result['failures'].append(f"errors: {result['errors'][:3]}")
    result['summary'] = {'pairs': result['pairs'], 'new_positives': n_new,
                         'clearance_checks': len(result['explicit_clearance_checks']),
                         'clearance_fail': n_clr_fail,
                         'e3_vs_e1_bbox_pairs': result['e3_vs_e1_bbox_pairs'],
                         'e3_vs_e2_bbox_pairs': result['e3_vs_e2_bbox_pairs']}
    result['verdict'] = 'PASS' if not result['failures'] else 'FAIL'
    result['verdict_semantics'] = ('PASS=无 E3 新增干涉；E1 结转对与 49.71 惯例对由 r32 具名互锁，'
                                   '不在本扫描口径出现')
    result['elapsed_s'] = round(time.time() - t0, 3)
    write_json(REV / 'evidence' / 'review_e3_scan.json', result)
    print('verdict', result['verdict'], result['summary'], 'errors', len(result['errors']),
          'elapsed', result['elapsed_s'])
    for p in result['positives_new'][:8]:
        print('NEW_POSITIVE', p)


if __name__ == '__main__':
    main()
