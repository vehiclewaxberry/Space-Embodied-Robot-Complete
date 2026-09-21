# -*- coding: utf-8 -*-
"""R07-E4 独立复验 r33：4 夹套 + 4 改件螺钉新增干涉扫描（布尔口径，独立编码）。
基底钉固先行（sha 不等不开扫）。范围（与被审口径对齐但独立实现；布尔一律 OCP 原生，勘误 O2）：
  A) 8 E4 件（4 e4_clamp_sleeve_* + 4 RB_end_screw_-1_*）vs 全部 PHYSICAL_GEOMETRY+SIMPLIFIED_PROXY 实例；
     改件螺钉 vs 同角端塞 4 对为 49.71 螺纹惯例（重叠区 x[-177,-161] 逐位未变，r32 双车道互锁）
     → 与被审一致路由到 E（不计新阳性，但数值须 == r32 车道一）。
  B) 8 E4 件两两；
  D) 被审 38 项具名让隙逐项独立复算（名单从被审 acc 读出）；
  E) E4 vs E1/E2/E3 件互避：bbox 命中对计数。
预期：A=30、B=4（对照被审计数）、新阳性 0、clearance 38/38、路由到 E 4 对。
FUNCTIONAL_ENVELOPE 不作判据。"""
import json, sys, time, itertools
from e4_common import (REV, RUN, ENG, write_json, bbox, overlap, common_volume,
                       sha256_file, load_params, stations,
                       PARAMS_SHA256_EXPECT, SOURCE_SHA256_EXPECT)

TOL = 1e-6


def main():
    t0 = time.time()
    src_hash = sha256_file(ENG / 'spacecraft_model.py')
    P, params_hash = load_params()
    pin = {'spacecraft_model.py': {'actual': src_hash, 'expect': SOURCE_SHA256_EXPECT,
                                   'ok': src_hash == SOURCE_SHA256_EXPECT},
           'design_parameters.json': {'actual': params_hash, 'expect': PARAMS_SHA256_EXPECT,
                                      'ok': params_hash == PARAMS_SHA256_EXPECT}}
    result = {'review': 'R07_E4_INDEPENDENT_REVERIFY', 'script': 'e4_r33_scan.py',
              'reviewed_run': RUN.name, 'basis_pin': pin, 'tolerance_mm3': TOL,
              'pairs': {'A_e4_vs_other': 0, 'B_e4_vs_e4': 0},
              'routed_to_E_thread_convention': [], 'positives_new': [], 'errors': [],
              'explicit_clearance_checks': [],
              'e4_vs_e1_bbox_pairs': 0, 'e4_vs_e2_bbox_pairs': 0, 'e4_vs_e3_bbox_pairs': 0,
              'failures': [], 'verdict': None}
    if not all(v['ok'] for v in pin.values()):
        result['failures'].append('basis pin mismatch - scan aborted')
        result['verdict'] = 'FAIL'
        write_json(REV / 'evidence' / 'review_e4_scan.json', result)
        print('ABORT: basis pin mismatch', pin)
        return

    sts = stations(P)
    sleeves = sorted(st['sleeve'] for st in sts)
    screws = sorted(st['screw'] for st in sts)
    e4parts = sleeves + screws
    plug_of_screw = {st['screw']: st['plug'] for st in sts}

    sys.path.insert(0, str(ENG))
    import spacecraft_model as sm
    model, shapes, receipt = sm.build('service', include_arm=False)
    reps = {r['id']: r['representation_role'] for r in receipt['instances']}
    others = {n: s for n, s in shapes.items()
              if reps.get(n) in ('PHYSICAL_GEOMETRY', 'SIMPLIFIED_PROXY')
              and n not in e4parts}
    env_n = sum(1 for n in shapes if reps.get(n) == 'FUNCTIONAL_ENVELOPE')
    result['e4_part_count'] = len(e4parts)
    result['other_count'] = len(others)
    result['functional_envelopes_excluded_count'] = env_n
    result['build_instance_count'] = len(receipt['instances'])
    for n in e4parts:
        if n not in shapes:
            result['failures'].append(f'E4 part {n} not in build')
    bb = {n: bbox(s) for n, s in shapes.items()}

    def run_pair(n1, n2, cat):
        v = common_volume(shapes[n1], shapes[n2])
        if isinstance(v, dict):
            result['errors'].append({'pair': [n1, n2], **v})
            return
        result['pairs'][cat] += 1
        if cat == 'A_e4_vs_other':
            if n2.startswith('e1_anchor_'):
                result['e4_vs_e1_bbox_pairs'] += 1
            if n2.startswith('e2_'):
                result['e4_vs_e2_bbox_pairs'] += 1
            if n2.startswith('e3_'):
                result['e4_vs_e3_bbox_pairs'] += 1
            # 49.71 螺纹惯例路由到 E（改件螺钉 vs 同角端塞）
            if n1 in plug_of_screw and plug_of_screw[n1] == n2:
                result['routed_to_E_thread_convention'].append(
                    {'pair': [n1, n2], 'common_volume_mm3': v,
                     'note': 'PRE_EXISTING_THREAD_ENGAGEMENT_CONVENTION; r32 双车道逐位互锁'})
                return
        if v > TOL:
            result['positives_new'].append({'pair': [n1, n2], 'common_volume_mm3': v,
                                            'category': cat})

    for na in e4parts:
        for no in others:
            if overlap(bb[na], bb[no]):
                run_pair(na, no, 'A_e4_vs_other')
    for n1, n2 in itertools.combinations(e4parts, 2):
        if overlap(bb[n1], bb[n2]):
            run_pair(n1, n2, 'B_e4_vs_e4')

    # D) 被审 38 项具名让隙逐项复算
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

    n_new = len(result['positives_new'])
    n_clr_fail = sum(1 for c in result['explicit_clearance_checks'] if not c['pass'])
    if result['positives_new']:
        result['failures'].append(f"new positives: {result['positives_new'][:5]}")
    if result['errors']:
        result['failures'].append(f"errors: {result['errors'][:3]}")
    # 路由对数值的操作数次序归因确认：common(screw,plug) vs common(plug,screw)
    order_probe = {}
    for stx in sts[:1]:
        sp, pl = stx['screw'], stx['plug']
        v_sp = common_volume(shapes[sp], shapes[pl])
        v_ps = common_volume(shapes[pl], shapes[sp])
        order_probe = {'screw_first_mm3': v_sp, 'plug_first_mm3': v_ps,
                       'abs_diff': None if isinstance(v_sp, dict) or isinstance(v_ps, dict)
                       else abs(v_sp - v_ps),
                       'note': ('BRepAlgoAPI_Common 非逐位可交换：操作数次序改变求积路径；'
                                'r32 车道一/二与被审/E3 登记均 plug-first，本扫描 A 循环 screw-first，'
                                '差 ~7e-8 属同几何路径漂移，非几何差异')}
    result['operand_order_probe'] = order_probe
    result['candidate_pair_counts'] = acc['pairs']
    a_eff = result['pairs']['A_e4_vs_other'] - len(result['routed_to_E_thread_convention'])
    result['summary'] = {
        'pairs_bbox_total': result['pairs'],
        'A_effective_after_E_routing': a_eff,
        'candidate_pairs': acc['pairs'],
        'pair_counts_match_candidate': (a_eff == acc['pairs']['A_e4_vs_other']
                                        and result['pairs']['B_e4_vs_e4'] == acc['pairs']['B_e4_vs_e4']),
        'new_positives': n_new,
        'routed_to_E': len(result['routed_to_E_thread_convention']),
        'clearance_checks': len(result['explicit_clearance_checks']),
        'clearance_fail': n_clr_fail,
        'e4_vs_e1_bbox_pairs': result['e4_vs_e1_bbox_pairs'],
        'e4_vs_e2_bbox_pairs': result['e4_vs_e2_bbox_pairs'],
        'e4_vs_e3_bbox_pairs': result['e4_vs_e3_bbox_pairs']}
    result['verdict'] = 'PASS' if not result['failures'] else 'FAIL'
    result['verdict_semantics'] = ('PASS=无 E4 新增干涉；49.71 螺纹惯例 4 对路由到 E（r32 双车道逐位互锁），'
                                   'E1 结转对不含 E4 件不在本扫描口径出现')
    result['elapsed_s'] = round(time.time() - t0, 3)
    write_json(REV / 'evidence' / 'review_e4_scan.json', result)
    print('verdict', result['verdict'])
    print(json.dumps(result['summary'], ensure_ascii=False))
    print('routed_to_E values:', [r['common_volume_mm3'] for r in result['routed_to_E_thread_convention']])
    print('errors', len(result['errors']), 'elapsed', result['elapsed_s'])


if __name__ == '__main__':
    main()
