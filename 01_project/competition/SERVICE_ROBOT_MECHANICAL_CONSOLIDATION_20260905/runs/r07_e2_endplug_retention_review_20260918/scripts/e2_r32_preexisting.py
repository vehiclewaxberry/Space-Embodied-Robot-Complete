# -*- coding: utf-8 -*-
"""R07-E2 独立复验 r32：既有干涉核查。
被审登记（acc_interference_boolean.json，值一律从被审文件读出，不硬编码）：
  A. registered_preexisting_carried_forward：E1 结转两对
     RB_upper_beam_160 vs shear_web_screw_±1_150_94 ≈ 0.461 mm³（WP02 横梁端角既有，
     E1 审阅观察项 O5 已独立确认，E2 未碰横梁/剪力栓）；
  B. registered_thread_engagement_convention：八对 RB_end_plug_* vs RB_end_screw_*
     ≈ 49.71 mm³（WP02 螺纹咬合惯例：Ø4 螺钉包络入塞 Ø3.3 导孔=螺纹啮合表示）。
独立核查链：
  A1) 改前快照重建无孔旧横梁（E1 rev_common.unmodified_upper_beam，改前快照钉固）
      vs 解析剪力栓包络 → 应逐位等于登记值；E1 exports 现行带孔横梁 vs 同包络 → 1e-12 容差；
  B1) exports 塞（import_step 读回）vs 解析 M4 螺钉包络 → 应复现登记值；
  B2) plug_rebuild 重建塞（按改前快照 L195 = 现行 L253 同一行模式）vs 同包络 → 双路互证；
  G1) git show 90cd8d1f^:spacecraft_model.py（LF 归一化）== inputs 快照；
  G2) git show 90cd8d1f^:root_structure.py（LF 归一化）== inputs 快照（WP02 源未动）；
  G3) 塞重建行文本：改前快照 vs 现行源码逐字一致（证明 E2 未触碰塞定义）。
布尔一律用 e2_common.common_volume（OCP.BRepAlgoAPI_Common 原生；工具勘误见该函数）。"""
import json, subprocess, time, sys, hashlib
from pathlib import Path
from e2_common import (REV, RUN, RUN_E1, ROOT, ENG, write_json, common_volume,
                       import_step, sha256_file, stations, load_params,
                       m4_screw_envelope, plug_rebuild)

E1_SCRIPTS = REV.parent / 'r07_e1_anchoring_review_20260918' / 'scripts'
sys.path.insert(0, str(E1_SCRIPTS))
from rev_common import unmodified_upper_beam, shear_web_screw_envelope  # noqa: E402

SNAP_MODEL_SHA = '15573df4fe7dafcdc986e3b7b623f18065acd875d1eb82b95c731f0226b3ca82'
SNAP_ROOTSTRUCT_SHA = 'eaf7d17bba7b2bbabe215059bdc21f11b55944dac14858e4729022a6f3ef5c48'
E2_COMMIT = '90cd8d1f'
PLUG_LINE = 's=box((20,7.8,7.8));s=bore(s,3.3,24,(0,0,0),(1,0,0));s=bore(s,4.5,12,(-np.sign(xyz[0])*3,0,0))'


def git_show_bytes(rev, relpath):
    cp = subprocess.run(['git', 'show', f'{rev}:{relpath}'], cwd=str(ROOT),
                        capture_output=True, timeout=60)
    if cp.returncode != 0:
        return None, cp.stderr.decode('utf-8', 'replace')[:300]
    return cp.stdout, None


def norm_lf(b):
    return b.replace(b'\r\n', b'\n')


def b123d_common(a, b):
    """被审方原始布尔路径 build123d Shape.intersect（仅用于 build123d 原生件；
    import_step 读回件存在静默 None 陷阱，见 e2_common.common_volume 工具勘误）。"""
    c = a.intersect(b)
    if c is None:
        return {'error': 'build123d intersect returned None (import-step trap)'}
    return float(sum(s.volume for s in c.solids()))


def main():
    t0 = time.time()
    acc = json.loads((RUN / 'evidence' / 'acc_interference_boolean.json').read_text(encoding='utf-8'))
    carried = {tuple(e['pair']): e for e in acc['registered_preexisting_carried_forward']}
    thread_conv = {tuple(e['pair']): e for e in acc['registered_thread_engagement_convention']}
    result = {'review': 'R07_E2_INDEPENDENT_REVERIFY', 'script': 'e2_r32_preexisting.py',
              'reviewed_run': RUN.name, 'failures': [], 'verdict': None}

    # 0) 快照钉固
    snap_rs = RUN / 'inputs' / 'root_structure.py'
    snap_sm = RUN / 'inputs' / 'spacecraft_model.py'
    pins = {'root_structure.py': (sha256_file(snap_rs), SNAP_ROOTSTRUCT_SHA),
            'spacecraft_model.py': (sha256_file(snap_sm), SNAP_MODEL_SHA)}
    result['snapshot_pins'] = {k: {'actual': a, 'expected': e, 'match': a == e}
                               for k, (a, e) in pins.items()}
    for k, v in result['snapshot_pins'].items():
        if not v['match']:
            result['failures'].append(f'snapshot pin mismatch: {k}')

    # A) E1 结转两对
    ctrl_beam = unmodified_upper_beam(160)
    e1_beam_path = RUN_E1 / 'exports' / 'RB_upper_beam_160.step'
    e1_beam = import_step(str(e1_beam_path)) if e1_beam_path.exists() else None
    result['A_e1_carried_forward'] = {}
    for side in (-1, 1):
        key = ('RB_upper_beam_160', f'shear_web_screw_{side}_150_94')
        reg = carried[key]['common_volume_mm3_now']
        env = shear_web_screw_envelope(side)
        v_ctrl = common_volume(ctrl_beam, env)
        v_ctrl_b = b123d_common(ctrl_beam, env)
        rec = {'registered_mm3': reg, 'control_unmodified_beam_mm3_occ': v_ctrl,
               'control_unmodified_beam_mm3_build123d': v_ctrl_b,
               'control_occ_vs_registered_abs_diff': abs(v_ctrl - reg),
               'control_build123d_bit_identical': v_ctrl_b == reg}
        # 判据：OCC 路径 1e-12 容差（两布尔路径间存在 1ulp 级漂移，探针已归因）；
        # build123d 路径（=被审方原路径）应逐位复现登记值
        ok = (abs(v_ctrl - reg) <= 1e-12) and (v_ctrl_b == reg)
        if e1_beam is not None:
            v_e1 = common_volume(e1_beam, env)
            rec['e1_build_beam_mm3_occ'] = v_e1
            rec['e1_build_vs_registered_abs_diff'] = abs(v_e1 - reg)
            rec['e1_build_within_1e-12'] = abs(v_e1 - reg) <= 1e-12
            ok = ok and rec['e1_build_within_1e-12']
        else:
            rec['e1_build_beam_mm3_occ'] = 'E1 exports beam step missing'
            ok = False
        rec['pass'] = ok
        result['A_e1_carried_forward'][key[1]] = rec
        if not ok:
            result['failures'].append(f'A: {key[1]} recomputation mismatch: {rec}')

    # B) 49.71 mm³ 八对：exports 塞 + 重建塞双路（OCC）+ build123d 路径（被审方原路径）三路
    P, _ = load_params()
    sts = stations(P)
    result['B_thread_engagement_convention'] = {}
    for s in sts:
        key = (s['plug'], s['screw'])
        reg = thread_conv[key]['common_volume_mm3']
        env = m4_screw_envelope(s['sx'], s['sy'], s['sz'])
        plug_step = import_step(str(RUN / 'exports' / f"{s['plug']}.step"))
        plug_rb = plug_rebuild(s['sx'], s['sy'], s['sz'])
        v_exp = common_volume(plug_step, env)
        v_rb = common_volume(plug_rb, env)
        v_b123d = b123d_common(plug_rb, env)  # 仅对 build123d 原生件（import 件有 None 陷阱）
        rec = {'registered_mm3': reg,
               'occ_exports_plug_mm3': v_exp, 'occ_rebuild_plug_mm3': v_rb,
               'build123d_rebuild_plug_mm3': v_b123d,
               'occ_dual_abs_diff': abs(v_exp - v_rb),
               'occ_vs_registered_abs_diff': max(abs(v_exp - reg), abs(v_rb - reg)),
               'build123d_vs_registered_abs_diff': abs(v_b123d - reg)}
        # 判据（探针归因后）：
        #  1) OCC 双路互证 ≤1e-9（独立几何一致性）；
        #  2) OCC 值 vs 登记值 ≤5e-3（≈1e-4 相对；布尔实现路径间系统差，探针实测 1.9e-3~2.6e-3）；
        #  3) build123d 路径（=被审方原路径）vs 登记值 ≤1e-4（H03 逐位，H01 6.7e-5）
        rec['pass'] = (rec['occ_dual_abs_diff'] <= 1e-9 and
                       rec['occ_vs_registered_abs_diff'] <= 5e-3 and
                       rec['build123d_vs_registered_abs_diff'] <= 1e-4)
        result['B_thread_engagement_convention'][s['id']] = rec
        if not rec['pass']:
            result['failures'].append(f"B: {s['id']} mismatch: {rec}")

    # G) 非 E2 引入证明：git 旧态 + 塞定义行逐字比对
    g = {}
    rel_sm = '20_engineering/service_robot_wp03_spacecraft_body_r1/spacecraft_model.py'
    rel_rs = '20_engineering/service_robot_wp03_spacecraft_body_r1/root_structure.py'
    for tag, rel, snap in (('spacecraft_model.py', rel_sm, snap_sm),
                           ('root_structure.py', rel_rs, snap_rs)):
        old, err = git_show_bytes(f'{E2_COMMIT}^', rel)
        if old is None:
            g[tag] = {'status': 'UNAVAILABLE', 'error': err}
            result['failures'].append(f'git old state unavailable for {tag}: {err}')
        else:
            same = hashlib.sha256(norm_lf(old)).hexdigest() == hashlib.sha256(
                norm_lf(snap.read_bytes())).hexdigest()
            g[tag] = {'rev': f'{E2_COMMIT}^', 'lf_normalized_content_identical_to_snapshot': same}
            if not same:
                result['failures'].append(f'git old {tag} content != snapshot')
    # G3) 塞重建行逐字比对（改前快照 vs 现行源码）
    cur_lines = (ENG / 'spacecraft_model.py').read_text(encoding='utf-8').splitlines()
    snap_lines = snap_sm.read_text(encoding='utf-8').splitlines()
    cur_hit = [(i + 1, ln.strip()) for i, ln in enumerate(cur_lines) if PLUG_LINE in ln]
    snap_hit = [(i + 1, ln.strip()) for i, ln in enumerate(snap_lines) if PLUG_LINE in ln]
    g['plug_rebuild_line'] = {
        'current_hits': cur_hit, 'snapshot_hits': snap_hit,
        'line_content_identical': (len(cur_hit) == 1 and len(snap_hit) == 1 and
                                   cur_hit[0][1] == snap_hit[0][1]),
        'note': '塞 WP03 重建几何定义行；E2 未触碰 → 49.71 mm³ 惯例非 E2 引入'}
    if not g['plug_rebuild_line']['line_content_identical']:
        result['failures'].append('plug rebuild line changed by E2!')
    result['G_not_introduced_by_e2'] = g

    result['boolean_path_attribution'] = {
        'probe': '_work/probe_boolean_path_attribution.py',
        'finding': '登记布尔值由被审方 build123d Shape.intersect 路径产生；审阅方独立路径 '
                   'OCP.BRepAlgoAPI_Common 对同一几何给出系统差 1.9e-3~2.6e-3 mm³ '
                   '（≈5e-5 相对，OCC 圆柱-圆柱相交曲线剖分的实现路径依赖）。'
                   'A 对为 1ulp(2.2e-16) 漂移；B 对 build123d 路径复现登记值（H03 逐位、H01 6.7e-5）。',
        'impact': '该惯例对是登记性数值（非 Gate 判据）；所有 Gate 判定为零/非零语义，'
                  '两条布尔路径在全部 Gate 相关对上一致（零干涉对在两条路径下均为 0），'
                  '故此路径差不影响任何 Gate 结论。'}

    nA = len(result['A_e1_carried_forward'])
    nB = len(result['B_thread_engagement_convention'])
    result['conclusion'] = ('PRE_EXISTING_CONFIRMED' if not result['failures'] else 'DISPUTED')
    result['summary'] = {'A_pairs': nA, 'B_pairs': nB,
                         'A_all_pass': all(r['pass'] for r in result['A_e1_carried_forward'].values()),
                         'B_all_pass': all(r['pass'] for r in result['B_thread_engagement_convention'].values())}
    result['verdict'] = 'PASS' if not result['failures'] else 'FAIL'
    result['elapsed_s'] = round(time.time() - t0, 3)
    write_json(REV / 'evidence' / 'review_e2_preexisting.json', result)
    print('verdict', result['verdict'], result['conclusion'], result['summary'])
    for k, v in result['A_e1_carried_forward'].items():
        print('A', k, v)
    for k, v in result['B_thread_engagement_convention'].items():
        print('B', k, v['registered_mm3'], v['occ_exports_plug_mm3'],
              v['occ_rebuild_plug_mm3'], v['build123d_rebuild_plug_mm3'], v['pass'])
    print('G plug line:', g['plug_rebuild_line']['line_content_identical'],
          cur_hit, snap_hit)
    print('failures', result['failures'])


if __name__ == '__main__':
    main()
