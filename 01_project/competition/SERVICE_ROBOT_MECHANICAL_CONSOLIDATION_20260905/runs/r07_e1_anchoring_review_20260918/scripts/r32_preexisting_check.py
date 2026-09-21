# -*- coding: utf-8 -*-
"""R07-E1 独立复验 r32：既有干涉 0.461 mm³ 改前既有核查。
被审登记（acc_interference_boolean.json registered_preexisting）：
  RB_upper_beam_160 vs shear_web_screw_±1_150_94 公共体积 0.4610888343501606/85，
  声称改前既有（WP02 横梁端角 vs 既有剪力板栓包络 z≈95.15..97 掠入），E1 孔不涉及该角。
独立核查链：
  1) 用改件前快照（inputs/root_structure.py，INPUT_MANIFEST 哈希钉固）重建无 E1 孔旧横梁，
     与解析剪力栓包络 rod((154,±100.15,94),(154,±110.15,94),3) 复算公共体积 → 应逐位等于登记值；
  2) exports 现行带孔横梁 vs 同一包络 → 应逐位等于同一值（E1 孔在 z≈105.3，远离 z≤97 角区）；
  3) git 旧态对照：6579aee8^ 的 root_structure.py 字节 sha256 应等于 INPUT_MANIFEST 登记值
     （证明快照确为改前旧态）；E1 孔位与该角区间的几何隔离解析验证。"""
import json, math, subprocess, time
from pathlib import Path
from rev_common import (REV, RUN, ROOT, write_json, common_volume, import_step,
                        shear_web_screw_envelope, unmodified_upper_beam, sha256_file)

REGISTERED = {'shear_web_screw_-1_150_94': 0.4610888343501606,
              'shear_web_screw_1_150_94': 0.46108883435016085}
ROOT_STRUCTURE_SNAPSHOT_SHA = 'eaf7d17bba7b2bbabe215059bdc21f11b55944dac14858e4729022a6f3ef5c48'


def git_show_bytes(rev, relpath):
    cp = subprocess.run(['git', 'show', f'{rev}:{relpath}'], cwd=str(ROOT),
                        capture_output=True, timeout=60)
    if cp.returncode != 0:
        return None, cp.stderr.decode('utf-8', 'replace')[:300]
    return cp.stdout, None


def main():
    t0 = time.time()
    result = {'review': 'R07_E1_INDEPENDENT_REVERIFY', 'script': 'r32_preexisting_check.py',
              'reviewed_run': RUN.name, 'registered_values_mm3': REGISTERED,
              'recomputed': {}, 'git_old_state': {}, 'geometric_isolation': {},
              'failures': [], 'verdict': None}

    # 0) 快照钉固
    snap = RUN / 'inputs' / 'root_structure.py'
    snap_hash = sha256_file(snap)
    result['snapshot_pin'] = {'file': 'inputs/root_structure.py', 'sha256': snap_hash,
                              'matches_INPUT_MANIFEST': snap_hash == ROOT_STRUCTURE_SNAPSHOT_SHA}
    if not result['snapshot_pin']['matches_INPUT_MANIFEST']:
        result['failures'].append('snapshot root_structure.py hash mismatch')

    # 1) 无孔旧横梁（改件前重建） vs 解析剪力栓包络
    ctrl_beam = unmodified_upper_beam(160)
    # 2) exports 现行带孔横梁
    e1_beam = import_step(str(RUN / 'exports' / 'RB_upper_beam_160.step'))
    for side in (-1, 1):
        name = f'shear_web_screw_{side}_150_94'
        env = shear_web_screw_envelope(side)
        v_ctrl = common_volume(ctrl_beam, env)
        v_e1 = common_volume(e1_beam, env)
        reg = REGISTERED[name]
        ulp_ok = abs(v_e1 - v_ctrl) <= 1e-12
        result['recomputed'][name] = {
            'control_unmodified_beam_mm3': v_ctrl,
            'e1_build_beam_mm3': v_e1,
            'registered_mm3': reg,
            'control_bit_identical': v_ctrl == reg,
            'e1_build_bit_identical': v_e1 == reg,
            'e1_vs_control_abs_diff': abs(v_e1 - v_ctrl),
            'e1_vs_control_within_1ulp_tolerance': ulp_ok,
            'tolerance_note': '布尔结果受 B-rep 面剖分影响存在 1 ulp 级 OCC 数值噪声；'
                              'control（无孔旧件）须逐位等于登记值，e1 带孔件容差 1e-12'}
        if not (v_ctrl == reg and ulp_ok):
            result['failures'].append(
                f'{name}: control={v_ctrl!r} e1={v_e1!r} registered={reg!r}')

    # 3) git 旧态对照：6579aee8^ 的 root_structure.py 内容应与快照一致。
    # 注意：git 仓库存 LF，工作区/快照为 CRLF（INPUT_MANIFEST 按原字节登记）→ 归一化后比对。
    rel_rs = '20_engineering/service_robot_wp03_spacecraft_body_r1/root_structure.py'
    old_bytes, err = git_show_bytes('6579aee8^', rel_rs)
    if old_bytes is None:
        result['git_old_state'] = {'status': 'UNAVAILABLE', 'error': err}
        result['failures'].append('git old state unavailable: ' + str(err))
    else:
        import hashlib
        def norm(b): return b.replace(b'\r\n', b'\n')
        old_hash_norm = hashlib.sha256(norm(old_bytes)).hexdigest()
        snap_hash_norm = hashlib.sha256(norm(snap.read_bytes())).hexdigest()
        result['git_old_state'] = {
            'rev': '6579aee8^', 'path': rel_rs,
            'eol_note': 'git 仓库存 LF；快照/工作区为 CRLF；按 LF 归一化后比对内容',
            'sha256_lf_normalized_old': old_hash_norm,
            'sha256_lf_normalized_snapshot': snap_hash_norm,
            'content_identical': old_hash_norm == snap_hash_norm}
        if not result['git_old_state']['content_identical']:
            result['failures'].append('git old root_structure.py content != snapshot')

    # 4) 几何隔离解析验证：E1 盲孔（x=154.85, z=105.3, r=1.7, y 自 ±101.15 向内 12）
    #    vs 干涉角区（x∈[153,157], |y|∈[100.15,101.15], z∈[95.15,97]）
    hole_z = (105.3 - 1.7, 105.3 + 1.7)
    corner_z = (95.15, 97.0)
    result['geometric_isolation'] = {
        'e1_blind_hole': {'x': 154.85, 'z_interval_mm': list(hole_z),
                          'y_interval_mm': 'sy*[89.15,101.15] 自端面向内 12'},
        'interference_corner': {'x_interval_mm': [153.0, 157.0],
                                'abs_y_interval_mm': [100.15, 101.15],
                                'z_interval_mm': list(corner_z)},
        'z_disjoint': hole_z[0] > corner_z[1],
        'note': 'E1 孔 z 下限 103.6 > 角区 z 上限 97：区间不相交；且孔为去除材料，不可能新增材料干涉'}
    if not result['geometric_isolation']['z_disjoint']:
        result['failures'].append('geometric isolation check failed')

    result['conclusion'] = ('PRE_EXISTING_CONFIRMED' if not result['failures'] else 'DISPUTED')
    result['verdict'] = 'PASS' if not result['failures'] else 'FAIL'
    result['elapsed_s'] = round(time.time() - t0, 3)
    write_json(REV / 'evidence' / 'review_preexisting_interference.json', result)
    print('verdict', result['verdict'], 'conclusion', result['conclusion'])
    for k, v in result['recomputed'].items():
        print(k, v)
    print('git', result['git_old_state'])
    print('failures', result['failures'])


if __name__ == '__main__':
    main()
