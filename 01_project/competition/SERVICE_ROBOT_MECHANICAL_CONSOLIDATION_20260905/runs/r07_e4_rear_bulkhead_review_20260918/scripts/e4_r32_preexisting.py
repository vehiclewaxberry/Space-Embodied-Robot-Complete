# -*- coding: utf-8 -*-
"""R07-E4 独立复验 r32：既有干涉核查 + 方案核心预言（bit-identical）当前 build 车道。
A) E1 结转两对 RB_upper_beam_160 vs shear_web_screw_±1_150_94（三路径归因闭环，同 E3 r32 法）：
   OCC 原生复算须 == 被审 now 值（…606 两侧）；build123d 路径须 == E1 登记两尾数（…606/…6085）。
B) 8 对端塞 vs M4 螺钉 49.71mm3 螺纹惯例——E4 方案核心预言：
   "螺钉延长仅在头侧（x<-183），端塞∩螺钉重叠区 x[-177,-161] 不变 → 复算逐位一致"。
   车道一（本脚本）：当前（E4 后）ENG build OCC 复算 8 对
     vs E3 审阅 r32 build OCC 值（e4_common.E3_REVIEW_BUILD_OCC）逐位比对；
     同时 vs 被审 acc rtc 登记值与其 bit_identical_to_e3_registration 声明逐条核验。
   车道二（e4_r32b）：git d1a3b70a^ 旧源码 build 基线 8 对 vs 当前 build 逐位比对。
布尔一律 OCP 原生（勘误 O2）；build123d 路径仅作归因对照（原生件）。"""
import json, time, sys
from pathlib import Path
from e4_common import (REV, RUN, ROOT, ENG, E3_REVIEW_BUILD_OCC, write_json,
                       common_volume, b123d_common, sha256_file, import_step)

E1_SCRIPTS = REV.parent / 'r07_e1_anchoring_review_20260918' / 'scripts'
sys.path.insert(0, str(E1_SCRIPTS))
from rev_common import unmodified_upper_beam, shear_web_screw_envelope  # noqa: E402


def main():
    t0 = time.time()
    acc = json.loads((RUN / 'evidence' / 'acc_interference_boolean.json').read_text(encoding='utf-8'))
    carried = {tuple(e['pair']): e for e in acc['registered_preexisting_carried_forward']}
    rtc = acc['registered_thread_engagement_convention']
    result = {'review': 'R07_E4_INDEPENDENT_REVERIFY', 'script': 'e4_r32_preexisting.py',
              'reviewed_run': RUN.name, 'failures': [], 'verdict': None}

    # 快照钉固（E4 run inputs）
    snap_sm = RUN / 'inputs' / 'spacecraft_model.py'
    snap_rs = RUN / 'inputs' / 'root_structure.py'
    man = json.loads((RUN / 'inputs' / 'INPUT_MANIFEST.json').read_text(encoding='utf-8'))
    expect = {f['snapshot'].split('/')[-1]: f['snapshot_sha256'] for f in man['files']}
    pins = {}
    for f in (snap_sm, snap_rs):
        a = sha256_file(f)
        pins[f.name] = {'actual': a, 'expect': expect.get(f.name), 'ok': a == expect.get(f.name)}
    result['snapshot_pins'] = pins
    if not all(v['ok'] for v in pins.values()):
        result['failures'].append(f'snapshot pin fail: {pins}')

    # A) E1 结转两对（三路径）
    ctrl_beam = unmodified_upper_beam(160)
    result['A_e1_carried_forward'] = {}
    for side in (-1, 1):
        key = ('RB_upper_beam_160', f'shear_web_screw_{side}_150_94')
        e = carried[key]
        env = shear_web_screw_envelope(side)
        v_occ = common_volume(ctrl_beam, env)
        v_b123d = b123d_common(ctrl_beam, env)
        rec = {'e1_registered_mm3': e['e1_registered_mm3'],
               'candidate_now_mm3': e['common_volume_mm3_now'],
               'candidate_bit_identical_declared': e['bit_identical_to_e1_registration'],
               'review_occ_mm3': v_occ,
               'review_occ_eq_candidate_now': v_occ == e['common_volume_mm3_now'],
               'review_build123d_mm3': v_b123d,
               'review_build123d_eq_e1_registered': v_b123d == e['e1_registered_mm3']}
        rec['attribution_closed'] = (rec['review_occ_eq_candidate_now'] and
                                     rec['review_build123d_eq_e1_registered'])
        rec['pass'] = rec['attribution_closed']
        result['A_e1_carried_forward'][key[1]] = rec
        if not rec['pass']:
            result['failures'].append(f'A: {key[1]} attribution fail: {rec}')

    # B 车道一：当前 build OCC 复算 8 对，vs E3 审阅 build OCC 值 + 被审 acc rtc 登记
    sys.path.insert(0, str(ENG))
    import spacecraft_model as sm
    model, shapes, receipt = sm.build('service', include_arm=False)
    acc_rtc = {tuple(e['pair']): e for e in rtc}
    result['B_thread_convention_lane1_current_build'] = {}
    for (plug, screw), e in sorted(acc_rtc.items()):
        v = common_volume(shapes[plug], shapes[screw])
        ref_e3 = E3_REVIEW_BUILD_OCC[plug]
        rec = {'pair': [plug, screw],
               'screw_modified_by_e4': e['screw_modified_by_e4'],
               'review_current_build_occ_mm3': v,
               'e3_review_build_occ_mm3': ref_e3,
               'bit_identical_to_e3_review_build': v == ref_e3,
               'candidate_registered_mm3': e['common_volume_mm3'],
               'bit_identical_to_candidate_registration': v == e['common_volume_mm3'],
               'candidate_declared_bit_identical_to_e3': e['bit_identical_to_e3_registration']}
        ok = (not isinstance(v, dict)) and rec['bit_identical_to_e3_review_build'] \
            and rec['bit_identical_to_candidate_registration']
        rec['pass'] = ok
        result['B_thread_convention_lane1_current_build'][plug] = rec
        if not ok:
            result['failures'].append(f'B lane1: {plug} {v!r} vs e3_review {ref_e3!r} '
                                      f'vs acc {e["common_volume_mm3"]!r}')

    result['conclusion'] = 'PRE_EXISTING_CONFIRMED' if not result['failures'] else 'DISPUTED'
    A = result['A_e1_carried_forward']
    B = result['B_thread_convention_lane1_current_build']
    result['summary'] = {
        'A_pairs': len(A), 'A_attribution_all_closed': all(r['pass'] for r in A.values()),
        'B_pairs': len(B),
        'B_bit_identical_to_e3_review_all': all(r['bit_identical_to_e3_review_build'] for r in B.values()),
        'B_bit_identical_to_candidate_all': all(r['bit_identical_to_candidate_registration'] for r in B.values()),
        'B_modified_screw_pairs': sum(1 for r in B.values() if r['screw_modified_by_e4']),
        'lane2_git_baseline': 'see review_e4_git_baseline.json (e4_r32b)'}
    result['verdict'] = 'PASS' if not result['failures'] else 'FAIL'
    result['elapsed_s'] = round(time.time() - t0, 3)
    write_json(REV / 'evidence' / 'review_e4_preexisting.json', result)
    print('verdict', result['verdict'], result['conclusion'])
    print(json.dumps(result['summary'], ensure_ascii=False))
    for k, v in B.items():
        print('B', k, v['review_current_build_occ_mm3'],
              'bit_e3=', v['bit_identical_to_e3_review_build'],
              'bit_acc=', v['bit_identical_to_candidate_registration'],
              'modified=', v['screw_modified_by_e4'])
    print('failures', result['failures'])


if __name__ == '__main__':
    main()
