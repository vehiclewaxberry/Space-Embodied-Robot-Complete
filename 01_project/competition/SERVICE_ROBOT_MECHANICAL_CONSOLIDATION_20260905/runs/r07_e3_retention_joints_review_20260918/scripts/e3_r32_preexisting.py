# -*- coding: utf-8 -*-
"""R07-E3 独立复验 r32：既有干涉核查。
A) E1 结转两对 RB_upper_beam_160 vs shear_web_screw_±1_150_94：
   被审登记 now=0.4610888343501606（两侧），+1 侧 bit_identical=false（vs E1 登记 ...6085，
   差 2.5e-16），声称属 OCP 求积路径差异如实登记。
   独立验证：OCC 原生复算（改前快照重建旧横梁 vs 解析剪力栓包络）须 == 被审 now 值；
   build123d 路径（E1 原口径）复算须 == E1 登记两尾数 → 归因闭环（E2 审阅 r32/O3 同型）。
B) 8 对端塞 vs M4 螺钉 49.71mm3 螺纹咬合惯例非 E3 引入：
   git f130d873^ 旧态 == inputs 快照（LF 归一化）；塞重建行逐字未变；
   build 口径 OCC 复算 8 对（容差 5e-3，布尔路径差 E2 r32 已归因）。
布尔一律 OCP 原生（勘误 O2）；build123d 路径仅作归因对照（原生件）。"""
import json, subprocess, time, sys, hashlib
from pathlib import Path
from e3_common import (REV, RUN, RUN_E2, ROOT, ENG, write_json, common_volume,
                       b123d_common, sha256_file, import_step)

E1_SCRIPTS = REV.parent / 'r07_e1_anchoring_review_20260918' / 'scripts'
sys.path.insert(0, str(E1_SCRIPTS))
from rev_common import unmodified_upper_beam, shear_web_screw_envelope  # noqa: E402

E3_COMMIT = 'f130d873'
PLUG_LINE = 's=box((20,7.8,7.8));s=bore(s,3.3,24,(0,0,0),(1,0,0));s=bore(s,4.5,12,(-np.sign(xyz[0])*3,0,0))'


def git_show_bytes(rev, relpath):
    cp = subprocess.run(['git', 'show', f'{rev}:{relpath}'], cwd=str(ROOT),
                        capture_output=True, timeout=60)
    if cp.returncode != 0:
        return None, cp.stderr.decode('utf-8', 'replace')[:300]
    return cp.stdout, None


def norm_lf(b):
    return b.replace(b'\r\n', b'\n')


def main():
    t0 = time.time()
    acc = json.loads((RUN / 'evidence' / 'acc_interference_boolean.json').read_text(encoding='utf-8'))
    carried = {tuple(e['pair']): e for e in acc['registered_preexisting_carried_forward']}
    thread_conv = acc['registered_thread_engagement_convention']
    result = {'review': 'R07_E3_INDEPENDENT_REVERIFY', 'script': 'e3_r32_preexisting.py',
              'reviewed_run': RUN.name, 'failures': [], 'verdict': None}

    # 快照钉固
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
        # 归因闭环：OCC 路径复现被审 now 值；build123d 路径复现 E1 登记值 → 2.5e-16 差=路径漂移
        rec['attribution_closed'] = (rec['review_occ_eq_candidate_now'] and
                                     rec['review_build123d_eq_e1_registered'])
        rec['pass'] = rec['attribution_closed']
        result['A_e1_carried_forward'][key[1]] = rec
        if not rec['pass']:
            result['failures'].append(f'A: {key[1]} attribution fail: {rec}')

    # B) 49.71 惯例八对：git 旧态 + 塞行逐字 + build 口径 OCC 复算
    g = {}
    rel_sm = '20_engineering/service_robot_wp03_spacecraft_body_r1/spacecraft_model.py'
    rel_rs = '20_engineering/service_robot_wp03_spacecraft_body_r1/root_structure.py'
    for tag, rel, snap in (('spacecraft_model.py', rel_sm, snap_sm),
                           ('root_structure.py', rel_rs, snap_rs)):
        old, err = git_show_bytes(f'{E3_COMMIT}^', rel)
        if old is None:
            g[tag] = {'status': 'UNAVAILABLE', 'error': err}
            result['failures'].append(f'git old state unavailable: {tag}')
        else:
            same = hashlib.sha256(norm_lf(old)).hexdigest() == hashlib.sha256(
                norm_lf(snap.read_bytes())).hexdigest()
            g[tag] = {'rev': f'{E3_COMMIT}^', 'lf_normalized_content_identical_to_snapshot': same}
            if not same:
                result['failures'].append(f'git old {tag} != snapshot')
    cur_lines = (ENG / 'spacecraft_model.py').read_text(encoding='utf-8').splitlines()
    snap_lines = snap_sm.read_text(encoding='utf-8').splitlines()
    cur_hit = [(i + 1, ln.strip()) for i, ln in enumerate(cur_lines) if PLUG_LINE in ln]
    snap_hit = [(i + 1, ln.strip()) for i, ln in enumerate(snap_lines) if PLUG_LINE in ln]
    g['plug_rebuild_line'] = {'current_hits': cur_hit, 'snapshot_hits': snap_hit,
                              'line_content_identical': (len(cur_hit) == 1 and len(snap_hit) == 1
                                                         and cur_hit[0][1] == snap_hit[0][1])}
    if not g['plug_rebuild_line']['line_content_identical']:
        result['failures'].append('plug rebuild line changed by E3!')
    result['B_git_not_introduced_by_e3'] = g

    # build 口径复算 8 对（E2 review 登记值取自 E2 run 被审证据，容差 5e-3 路径差）
    e2_acc = json.loads((RUN_E2 / 'evidence' / 'acc_interference_boolean.json').read_text(encoding='utf-8'))
    reg8 = {tuple(e['pair']): e['common_volume_mm3'] for e in e2_acc['registered_thread_engagement_convention']}
    sys.path.insert(0, str(ENG))
    import spacecraft_model as sm
    model, shapes, receipt = sm.build('service', include_arm=False)
    result['B_thread_convention_recompute'] = {}
    for (plug, screw), reg in sorted(reg8.items()):
        v = common_volume(shapes[plug], shapes[screw])
        ok = (not isinstance(v, dict)) and abs(v - reg) <= 5e-3
        result['B_thread_convention_recompute'][plug] = {
            'e2_registered_mm3': reg, 'review_build_occ_mm3': v,
            'abs_diff': None if isinstance(v, dict) else abs(v - reg),
            'tolerance_mm3': 5e-3, 'pass': ok}
        if not ok:
            result['failures'].append(f'B: {plug} {v!r} vs {reg!r}')

    result['conclusion'] = 'PRE_EXISTING_CONFIRMED' if not result['failures'] else 'DISPUTED'
    result['summary'] = {
        'A_pairs': len(result['A_e1_carried_forward']),
        'A_attribution_all_closed': all(r['pass'] for r in result['A_e1_carried_forward'].values()),
        'B_pairs': len(result['B_thread_convention_recompute']),
        'B_all_pass': all(r['pass'] for r in result['B_thread_convention_recompute'].values()),
        'plug_line_unchanged': g['plug_rebuild_line']['line_content_identical']}
    result['verdict'] = 'PASS' if not result['failures'] else 'FAIL'
    result['elapsed_s'] = round(time.time() - t0, 3)
    write_json(REV / 'evidence' / 'review_e3_preexisting.json', result)
    print('verdict', result['verdict'], result['conclusion'], result['summary'])
    for k, v in result['A_e1_carried_forward'].items():
        print('A', k, {kk: vv for kk, vv in v.items() if 'mm3' in kk or 'eq' in kk or kk == 'pass'})
    print('failures', result['failures'])


if __name__ == '__main__':
    main()
