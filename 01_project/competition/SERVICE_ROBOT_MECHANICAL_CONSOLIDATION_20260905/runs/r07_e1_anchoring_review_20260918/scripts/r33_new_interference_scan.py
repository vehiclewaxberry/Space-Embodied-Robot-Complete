# -*- coding: utf-8 -*-
"""R07-E1 独立复验 r33：48 件新锚固包络新增干涉扫描（布尔口径，独立编码）。
基底钉固：当前 20_engineering 源码 sha256 须逐位等于 EXPORT_MANIFEST 登记构建源
（spacecraft_model.py 15573df4…、design_parameters.json c875b6b2…），否则不开扫。
范围（与登记口径对齐但独立实现）：
  A) 48 锚固件 vs 全部 PHYSICAL_GEOMETRY+SIMPLIFIED_PROXY 实例（bbox 预筛 + common 体积）；
  B) 48 锚固件两两；
  C) 9 受影响构件 vs 全部物理/代理实例；
  D) 96 项具名零间隙检查（16 站 × 栓-纵梁孔/栓-端面孔/栓-套/套-管内腔/套-端塞/垫圈-外腹面）。
预期：唯一阳性 = 已登记既有对 RB_upper_beam_160 vs shear_web_screw_±1_150_94（C 类），
其余全部 ≤1e-6 mm³；FUNCTIONAL_ENVELOPE 不作判据。"""
import json, math, sys, time, itertools
from pathlib import Path
from rev_common import (REV, RUN, ROOT, ENG, write_json, bbox, overlap, common_volume,
                        sha256_file, load_params, expected_stations,
                        PARAMS_SHA256_EXPECT, SOURCE_SHA256_EXPECT)

TOL = 1e-6
MEMBERS = ['RB_longeron_1_1', 'RB_longeron_-1_1', 'RB_longeron_1_-1', 'RB_longeron_-1_-1',
           'RB_upper_beam_20', 'RB_upper_beam_160', 'RB_lower_beam_20', 'RB_lower_beam_160',
           'WP01-RB-BRIDGE-R2']
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
    result = {'review': 'R07_E1_INDEPENDENT_REVERIFY', 'script': 'r33_new_interference_scan.py',
              'reviewed_run': RUN.name, 'basis_pin': pin, 'tolerance_mm3': TOL,
              'pairs': {'A_anchor_vs_other': 0, 'B_anchor_vs_anchor': 0, 'C_member_vs_other': 0},
              'positives_new': [], 'positives_registered_preexisting': [], 'errors': [],
              'explicit_clearance_checks': [], 'failures': [], 'verdict': None}
    if not all(v['ok'] for v in pin.values()):
        result['failures'].append('basis pin mismatch - scan aborted')
        result['verdict'] = 'FAIL'
        write_json(REV / 'evidence' / 'review_new_interference_scan.json', result)
        print('ABORT: basis pin mismatch', pin)
        return

    sys.path.insert(0, str(ENG))
    import spacecraft_model as sm
    model, shapes, receipt = sm.build('service', include_arm=False)
    reps = {r['id']: r['representation_role'] for r in receipt['instances']}
    anchors = sorted(n for n in shapes if n.startswith('e1_anchor_'))
    others = {n: s for n, s in shapes.items()
              if reps.get(n) in ('PHYSICAL_GEOMETRY', 'SIMPLIFIED_PROXY')
              and not n.startswith('e1_anchor_')}
    env_n = sum(1 for n in shapes if reps.get(n) == 'FUNCTIONAL_ENVELOPE')
    result['anchor_count'] = len(anchors)
    result['other_count'] = len(others)
    result['functional_envelopes_excluded_count'] = env_n
    result['build_instance_count'] = len(receipt['instances'])
    if len(anchors) != 48:
        result['failures'].append(f'anchor count {len(anchors)} != 48')
    bb = {n: bbox(s) for n, s in shapes.items()}

    def run_pair(n1, s1, n2, s2, cat):
        v = common_volume(s1, s2)
        if isinstance(v, dict):
            result['errors'].append({'pair': [n1, n2], **v})
            return
        result['pairs'][cat] += 1
        if v > TOL:
            rec = {'pair': [n1, n2], 'common_volume_mm3': v, 'category': cat}
            if (n1, n2) in REGISTERED_PREEXISTING or (n2, n1) in REGISTERED_PREEXISTING:
                result['positives_registered_preexisting'].append(rec)
            else:
                result['positives_new'].append(rec)

    for na in anchors:
        for no, so in others.items():
            if overlap(bb[na], bb[no]):
                run_pair(na, shapes[na], no, so, 'A_anchor_vs_other')
    for n1, n2 in itertools.combinations(anchors, 2):
        if overlap(bb[n1], bb[n2]):
            run_pair(n1, shapes[n1], n2, shapes[n2], 'B_anchor_vs_anchor')
    for nm in MEMBERS:
        for no, so in others.items():
            if no == nm:
                continue
            if overlap(bb[nm], bb[no]):
                run_pair(nm, shapes[nm], no, so, 'C_member_vs_other')

    # D) 具名零间隙检查（参数块独立展开 16 站）
    for st in expected_stations(P):
        gid, j = st['group'], st['index']
        bn = f'e1_anchor_bolt_{gid}_{j}'
        wn = f'e1_anchor_washer_{gid}_{j}'
        sn = f'e1_anchor_sleeve_{gid}_{j}'
        plug = f"RB_end_plug_1_{st['sy']}_{st['sz']}"
        for a, b, intent in [(bn, st['rail'], '栓杆 vs 纵梁 Ø3.4 孔：零干涉'),
                             (bn, st['beam'], '栓杆 vs 端面盲孔：零干涉(threadless 包络)'),
                             (bn, sn, '栓杆 Ø3 vs 套 ID3.4：零干涉'),
                             (sn, st['rail'], '防压套 vs 纵梁管内腔：零干涉'),
                             (sn, plug, '防压套 vs 端塞(x>=157)：零干涉(154.85 站关键)'),
                             (wn, st['rail'], '垫圈 vs 纵梁外腹面：贴面零体积')]:
            v = common_volume(shapes[a], shapes[b])
            ok = (not isinstance(v, dict)) and v <= TOL
            result['explicit_clearance_checks'].append(
                {'pair_id': f'E1P-{gid}-{j}', 'a': a, 'b': b, 'intent': intent,
                 'common_volume_mm3': None if isinstance(v, dict) else v, 'pass': ok})
            if isinstance(v, dict):
                result['errors'].append({'pair': [a, b], **v})
            elif not ok:
                result['positives_new'].append({'pair': [a, b], 'common_volume_mm3': v,
                                                'category': 'D_named_clearance', 'intent': intent})

    n_reg = len(result['positives_registered_preexisting'])
    if result['positives_new']:
        result['failures'].append(f"new positives: {result['positives_new'][:5]}")
    if result['errors']:
        result['failures'].append(f"errors: {result['errors'][:3]}")
    if n_reg != 2:
        result['failures'].append(f'registered preexisting positives {n_reg} != 2')
    else:
        for rec in result['positives_registered_preexisting']:
            if abs(rec['common_volume_mm3'] - 0.4610888343501608) > 1e-9:
                result['failures'].append(f"preexisting volume drift: {rec}")
    result['verdict'] = 'PASS' if not result['failures'] else 'FAIL'
    result['verdict_semantics'] = 'PASS=无 E1 新增干涉；既有对仅登记不剔除（与 r32 核查互锁）'
    result['elapsed_s'] = round(time.time() - t0, 3)
    write_json(REV / 'evidence' / 'review_new_interference_scan.json', result)
    print('verdict', result['verdict'], 'pairs', result['pairs'],
          'new', len(result['positives_new']), 'reg', n_reg,
          'clearance_fail', sum(1 for c in result['explicit_clearance_checks'] if not c['pass']),
          'errors', len(result['errors']), 'elapsed', result['elapsed_s'])
    for p in result['positives_new'][:6]:
        print('NEW_POSITIVE', p)


if __name__ == '__main__':
    main()
