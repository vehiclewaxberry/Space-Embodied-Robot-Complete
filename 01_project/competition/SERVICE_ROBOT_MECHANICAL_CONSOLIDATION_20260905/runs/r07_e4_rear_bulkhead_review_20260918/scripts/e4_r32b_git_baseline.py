# -*- coding: utf-8 -*-
"""R07-E4 独立复验 r32b：方案核心预言车道二——git d1a3b70a^ 旧源码 build 基线。
旧源码（E4 前，M4×22 锚点 -183）临时写入 ENG/_review_pre_e4_tmp.py，importlib 加载执行 build，
OCC 复算 8 对端塞∩螺钉，与车道一（当前 E4 后 build，review_e4_preexisting.json）逐位比对：
两趟一致即证"延长仅在头侧"（重叠区 x[-177,-161] 不变）。临时文件 finally unlink 并跑后确认无残留。
另核：git 旧态 spacecraft_model.py/root_structure.py LF 归一化 == E4 inputs 快照（E4 未悄悄改塞/其它行）。"""
import json, time, sys, subprocess, hashlib, importlib.util
from pathlib import Path
from e4_common import (REV, RUN, ROOT, ENG, E4_COMMIT, write_json, common_volume,
                       sha256_file)

TMP = ENG / '_review_pre_e4_tmp.py'
REL_SM = '20_engineering/service_robot_wp03_spacecraft_body_r1/spacecraft_model.py'
REL_RS = '20_engineering/service_robot_wp03_spacecraft_body_r1/root_structure.py'


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
    result = {'review': 'R07_E4_INDEPENDENT_REVERIFY', 'script': 'e4_r32b_git_baseline.py',
              'reviewed_run': RUN.name, 'failures': [], 'verdict': None}

    # git 旧态 vs E4 inputs 快照（LF 归一化）
    g = {}
    for tag, rel in (('spacecraft_model.py', REL_SM), ('root_structure.py', REL_RS)):
        old, err = git_show_bytes(f'{E4_COMMIT}^', rel)
        snap = RUN / 'inputs' / tag
        if old is None:
            g[tag] = {'status': 'UNAVAILABLE', 'error': err}
            result['failures'].append(f'git old state unavailable: {tag}')
        else:
            same = hashlib.sha256(norm_lf(old)).hexdigest() == hashlib.sha256(
                norm_lf(snap.read_bytes())).hexdigest()
            g[tag] = {'rev': f'{E4_COMMIT}^', 'lf_normalized_content_identical_to_snapshot': same}
            if not same:
                result['failures'].append(f'git old {tag} != E4 inputs snapshot')
    result['git_old_vs_snapshot'] = g

    # 车道二：旧源码 build 基线 8 对
    lane1 = json.loads((REV / 'evidence' / 'review_e4_preexisting.json').read_text(encoding='utf-8'))
    cur = lane1['B_thread_convention_lane1_current_build']
    old_src, err = git_show_bytes(f'{E4_COMMIT}^', REL_SM)
    if old_src is None:
        result['failures'].append(f'git old source unavailable: {err}')
    else:
        TMP.write_bytes(old_src)
        try:
            sys.path.insert(0, str(ENG))
            spec = importlib.util.spec_from_file_location('spacecraft_model_pre_e4', str(TMP))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            model, shapes, receipt = mod.build('service', include_arm=False)
            result['B_thread_convention_lane2_git_baseline'] = {}
            for plug in sorted(cur):
                screw = cur[plug]['pair'][1]
                v_old = common_volume(shapes[plug], shapes[screw])
                v_cur = cur[plug]['review_current_build_occ_mm3']
                rec = {'pair': [plug, screw],
                       'screw_modified_by_e4': cur[plug]['screw_modified_by_e4'],
                       'lane2_git_baseline_occ_mm3': v_old,
                       'lane1_current_build_occ_mm3': v_cur,
                       'bit_identical_lanes': (not isinstance(v_old, dict)) and v_old == v_cur,
                       'abs_diff': None if isinstance(v_old, dict) else abs(v_old - v_cur)}
                rec['pass'] = rec['bit_identical_lanes']
                result['B_thread_convention_lane2_git_baseline'][plug] = rec
                if not rec['pass']:
                    result['failures'].append(f'B lane2: {plug} {v_old!r} vs current {v_cur!r}')
        finally:
            try:
                TMP.unlink()
            except FileNotFoundError:
                pass
        result['tmp_file_residual'] = TMP.exists()
        if result['tmp_file_residual']:
            result['failures'].append('temp file residual in ENG!')

    B2 = result.get('B_thread_convention_lane2_git_baseline', {})
    result['summary'] = {
        'git_old_identical_to_snapshot': all(
            v.get('lf_normalized_content_identical_to_snapshot') for v in g.values()),
        'B2_pairs': len(B2),
        'B2_bit_identical_all': all(r['bit_identical_lanes'] for r in B2.values()) if B2 else False,
        'B2_modified_pairs_bit_identical': all(
            r['bit_identical_lanes'] for r in B2.values() if r['screw_modified_by_e4']),
        'core_prediction': ('CONFIRMED: 延长仅在头侧，8 对两车道逐位一致'
                            if B2 and all(r['bit_identical_lanes'] for r in B2.values())
                            else 'NOT_CONFIRMED')}
    result['verdict'] = 'PASS' if not result['failures'] else 'FAIL'
    result['elapsed_s'] = round(time.time() - t0, 3)
    write_json(REV / 'evidence' / 'review_e4_git_baseline.json', result)
    print('verdict', result['verdict'])
    print(json.dumps(result['summary'], ensure_ascii=False))
    for k, v in B2.items():
        print('B2', k, v['lane2_git_baseline_occ_mm3'], 'bit=', v['bit_identical_lanes'],
              'modified=', v['screw_modified_by_e4'])
    print('failures', result['failures'])


if __name__ == '__main__':
    main()
