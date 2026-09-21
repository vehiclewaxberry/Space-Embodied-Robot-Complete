# -*- coding: utf-8 -*-
"""R07-E2 独立复验 r33：28 件新增保持件干涉扫描（布尔口径，独立编码）。
基底钉固：当前 20_engineering 源码 sha256 须逐位等于 EXPORT_MANIFEST 登记构建源
（e2_common.SOURCE/PARAMS_SHA256_EXPECT），否则不开扫。
范围（与被审登记口径对齐但独立实现；布尔一律 OCP.BRepAlgoAPI_Common，见工具勘误）：
  A) 28 E2 件 vs 全部 PHYSICAL_GEOMETRY+SIMPLIFIED_PROXY 实例（bbox 预筛 + common 体积）；
  B) 28 E2 件两两；
  C) 12 受影响构件（4 纵梁 + 8 端塞，E2 新增对偶孔/竖孔）vs 全部物理/代理实例；
  D) 被审登记 64 项具名让隙检查逐项独立复算（对名单从被审 acc 文件读出）；
  E) build 口径具名复算：E1 结转两对 + 49.71 螺纹咬合惯例八对（与 r32 互锁）；
  F) E2 件 vs E1 锚固件（e1_anchor_*）bbox 命中对单独计数（属 A 子集）。
预期：新阳性 0；既有阳性仅 E1 结转两对 + 49.71 惯例八对（登记口径，不剔除）。
FUNCTIONAL_ENVELOPE 不作判据。"""
import json, sys, time, itertools
from pathlib import Path
from e2_common import (REV, RUN, ENG, write_json, bbox, overlap, common_volume,
                       sha256_file, load_params, stations,
                       PARAMS_SHA256_EXPECT, SOURCE_SHA256_EXPECT)

TOL = 1e-6
E2PREFIX = 'e2_'
AFFECTED = ['RB_longeron_1_1', 'RB_longeron_-1_1', 'RB_longeron_1_-1', 'RB_longeron_-1_-1'] + \
           [f'RB_end_plug_{sx}_{sy}_{sz}' for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
REGISTERED_PREEXISTING = {('RB_upper_beam_160', 'shear_web_screw_1_150_94'),
                          ('RB_upper_beam_160', 'shear_web_screw_-1_150_94')}


def main():
    t0 = time.time()
    # ---- 基底钉固 ----
    src_hash = sha256_file(ENG / 'spacecraft_model.py')
    P, params_hash = load_params()
    pin = {'spacecraft_model.py': {'actual': src_hash, 'expect': SOURCE_SHA256_EXPECT,
                                   'ok': src_hash == SOURCE_SHA256_EXPECT},
           'design_parameters.json': {'actual': params_hash, 'expect': PARAMS_SHA256_EXPECT,
                                      'ok': params_hash == PARAMS_SHA256_EXPECT}}
    result = {'review': 'R07_E2_INDEPENDENT_REVERIFY', 'script': 'e2_r33_scan.py',
              'reviewed_run': RUN.name, 'basis_pin': pin, 'tolerance_mm3': TOL,
              'pairs': {'A_e2_vs_other': 0, 'B_e2_vs_e2': 0, 'C_affected_vs_other': 0},
              'positives_new': [], 'positives_registered_preexisting': [],
              'positives_thread_convention': [], 'errors': [],
              'explicit_clearance_checks': [], 'named_recompute': {},
              'e2_vs_e1_anchor_bbox_pairs': 0, 'failures': [], 'verdict': None}
    if not all(v['ok'] for v in pin.values()):
        result['failures'].append('basis pin mismatch - scan aborted')
        result['verdict'] = 'FAIL'
        write_json(REV / 'evidence' / 'review_e2_scan.json', result)
        print('ABORT: basis pin mismatch', pin)
        return

    sys.path.insert(0, str(ENG))
    import spacecraft_model as sm
    model, shapes, receipt = sm.build('service', include_arm=False)
    reps = {r['id']: r['representation_role'] for r in receipt['instances']}
    e2parts = sorted(n for n in shapes if n.startswith(E2PREFIX))
    others = {n: s for n, s in shapes.items()
              if reps.get(n) in ('PHYSICAL_GEOMETRY', 'SIMPLIFIED_PROXY')
              and not n.startswith(E2PREFIX)}
    env_n = sum(1 for n in shapes if reps.get(n) == 'FUNCTIONAL_ENVELOPE')
    result['e2_part_count'] = len(e2parts)
    result['other_count'] = len(others)
    result['functional_envelopes_excluded_count'] = env_n
    result['build_instance_count'] = len(receipt['instances'])
    if len(e2parts) != 28:
        result['failures'].append(f'e2 part count {len(e2parts)} != 28')
    bb = {n: bbox(s) for n, s in shapes.items()}
    thread_pairs = set()

    def run_pair(n1, s1, n2, s2, cat):
        v = common_volume(s1, s2)
        if isinstance(v, dict):
            result['errors'].append({'pair': [n1, n2], **v})
            return
        result['pairs'][cat] += 1
        if cat == 'A_e2_vs_other' and (n1.startswith('e1_anchor_') or n2.startswith('e1_anchor_')):
            result['e2_vs_e1_anchor_bbox_pairs'] += 1
        if v > TOL:
            rec = {'pair': [n1, n2], 'common_volume_mm3': v, 'category': cat}
            if (n1, n2) in REGISTERED_PREEXISTING or (n2, n1) in REGISTERED_PREEXISTING:
                result['positives_registered_preexisting'].append(rec)
            elif (n1, n2) in thread_pairs or (n2, n1) in thread_pairs:
                result['positives_thread_convention'].append(rec)
            else:
                result['positives_new'].append(rec)

    # 49.71 惯例对名单（从被审登记读出）
    acc = json.loads((RUN / 'evidence' / 'acc_interference_boolean.json').read_text(encoding='utf-8'))
    for e in acc['registered_thread_engagement_convention']:
        thread_pairs.add(tuple(e['pair']))

    for na in e2parts:
        for no, so in others.items():
            if overlap(bb[na], bb[no]):
                run_pair(na, shapes[na], no, so, 'A_e2_vs_other')
    for n1, n2 in itertools.combinations(e2parts, 2):
        if overlap(bb[n1], bb[n2]):
            run_pair(n1, shapes[n1], n2, shapes[n2], 'B_e2_vs_e2')
    for nm in AFFECTED:
        if nm not in shapes:
            result['failures'].append(f'affected member {nm} not in build')
            continue
        for no, so in others.items():
            if no == nm:
                continue
            if overlap(bb[nm], bb[no]):
                run_pair(nm, shapes[nm], no, so, 'C_affected_vs_other')

    # D) 被审登记 64 项具名让隙检查逐项独立复算
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

    # E) build 口径具名复算：E1 结转两对 + 49.71 惯例八对
    for side in (-1, 1):
        nm = f'shear_web_screw_{side}_150_94'
        v = common_volume(shapes['RB_upper_beam_160'], shapes[nm])
        reg = 0.4610888343501606 if side == -1 else 0.46108883435016085
        ok = (not isinstance(v, dict)) and abs(v - reg) <= 1e-9
        result['named_recompute'][nm] = {'registered_mm3': reg, 'review_build_mm3': v,
                                         'abs_diff': None if isinstance(v, dict) else abs(v - reg),
                                         'pass': ok}
        if not ok:
            result['failures'].append(f'named recompute {nm}: {v!r} vs {reg!r}')
    for s in stations(P):
        v = common_volume(shapes[s['plug']], shapes[s['screw']])
        reg = thread_pairs and [e['common_volume_mm3']
                                for e in acc['registered_thread_engagement_convention']
                                if e['pair'] == [s['plug'], s['screw']]][0]
        ok = (not isinstance(v, dict)) and abs(v - reg) <= 5e-3  # 布尔路径差容差（r32 归因）
        result['named_recompute'][f"{s['plug']}__vs__{s['screw']}"] = {
            'registered_mm3': reg, 'review_build_mm3_occ_path': v,
            'abs_diff': None if isinstance(v, dict) else abs(v - reg),
            'tolerance_mm3': 5e-3, 'tolerance_basis': 'boolean path attribution (r32)', 'pass': ok}
        if not ok:
            result['failures'].append(f"named recompute {s['id']}: {v!r} vs {reg!r}")

    n_reg = len(result['positives_registered_preexisting'])
    n_thr = len(result['positives_thread_convention'])
    n_clr_fail = sum(1 for c in result['explicit_clearance_checks'] if not c['pass'])
    if result['positives_new']:
        result['failures'].append(f"new positives: {result['positives_new'][:5]}")
    if result['errors']:
        result['failures'].append(f"errors: {result['errors'][:3]}")
    result['summary'] = {'pairs': result['pairs'], 'new_positives': len(result['positives_new']),
                         'registered_preexisting_positives': n_reg,
                         'thread_convention_positives': n_thr,
                         'clearance_checks': len(result['explicit_clearance_checks']),
                         'clearance_fail': n_clr_fail,
                         'e2_vs_e1_anchor_bbox_pairs': result['e2_vs_e1_anchor_bbox_pairs']}
    result['verdict'] = 'PASS' if not result['failures'] else 'FAIL'
    result['verdict_semantics'] = ('PASS=无 E2 新增干涉；E1 结转对与 49.71 惯例对仅登记不剔除'
                                   '（与 r32 核查互锁）')
    result['elapsed_s'] = round(time.time() - t0, 3)
    write_json(REV / 'evidence' / 'review_e2_scan.json', result)
    print('verdict', result['verdict'], result['summary'], 'errors', len(result['errors']),
          'elapsed', result['elapsed_s'])
    for p in result['positives_new'][:6]:
        print('NEW_POSITIVE', p)
    for p in result['positives_thread_convention'][:10]:
        print('THREAD_CONV', p['pair'], p['common_volume_mm3'])


if __name__ == '__main__':
    main()
