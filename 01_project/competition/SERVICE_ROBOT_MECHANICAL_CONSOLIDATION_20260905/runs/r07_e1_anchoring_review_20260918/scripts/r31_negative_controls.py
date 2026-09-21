# -*- coding: utf-8 -*-
"""R07-E1 独立复验 r31：三个负控制实验——先证明检查链"能报"，再信任"未报"。
NC-a V1 回放：按 s03b 记录的 V1 参数（套 Ø5/Ø3.4×8；x=154.85 站减径 Ø4；栓位 z=±104.15/110.15）
  重建 16 件 V1 防压套包络，对 exports 纵梁（V3 孔在 y 壁、套侵入在 z 壁，区域不相交，基底忠实）
  做布尔交集。期望：max ≈ 28.85 mm³（V1 FAIL 登记 max_intrusion 28.854630126389758），阳性 ≥16。
  对照组：V3 位（z=±105.3/109.0，Ø4）同法应为 0。
NC-b 缺对偶/错轴变异：_work 重建 RB_upper_beam_20 无孔件，钻 4 盲孔但 G01-0 偏移 1mm(x=16.5)，
  导出 STEP 重读回，用 r30 的孔面审计函数判定。期望：报 missing=(15.5,105.3) extra=(16.5,105.3)。
NC-c 既有件冲突变异：变异栓置于既有剪力板栓包络站位 (154,+1,94)，
  与 shear_web_screw 包络布尔交集应报大阳性（量级 ≈π·1.5²·10≈70.7）；同法验真实 G03_0 栓应为 0。
所有变异件只在 _work/ 隔离目录重建并重读回后判定。"""
import json, math, time
from pathlib import Path
from rev_common import (REV, RUN, write_json, bbox, cyl_faces, common_volume, import_step,
                        export_step, load_params, expected_stations, sleeve_envelope,
                        bolt_envelope, washer_envelope, shear_web_screw_envelope,
                        unmodified_upper_beam, cylinder_at)

# V1 状态（s03b/s03c 参数 diff 记录）：栓位 z=±104.15(梁)/110.15(桥)；桥栓 x=146/154.85；套 Ø5，x=154.85 站 Ø4
V1_Z_BEAM, V1_Z_BRIDGE = 104.15, 110.15
V1_MAX_EXPECT = 28.854630126389758


def v1_stations(P):
    """按 V1 参数展开 16 套位。"""
    out = []
    for st in expected_stations(P):
        g, x, sy, sz = st['group'], st['x'], st['sy'], st['sz']
        if st['member'] == 'bridge':
            x = 146.0 if st['index'] == 0 else 154.85   # V1 桥第二栓在 154.85（s03c 才移至 40）
            z = V1_Z_BRIDGE
        else:
            z = sz * V1_Z_BEAM
        od = 4.0 if abs(x - 154.85) < 1e-9 else 5.0     # V1 reduced OD 仅 x=154.85 站
        out.append({'pair_id': st['pair_id'], 'x': x, 'z': z, 'sy': sy, 'sz': sz,
                    'rail': st['rail'], 'sleeve_od': od})
    return out


def main():
    t0 = time.time()
    ev = REV / 'evidence'
    work = REV / '_work'
    work.mkdir(exist_ok=True)
    P, ph = load_params()
    result = {'review': 'R07_E1_INDEPENDENT_REVERIFY', 'script': 'r31_negative_controls.py',
              'reviewed_run': RUN.name, 'nc_a': {}, 'nc_b': {}, 'nc_c': {},
              'verdict': None, 'failures': []}

    rails = {n: import_step(str(RUN / 'exports' / f'{n}.step'))
             for n in ('RB_longeron_1_1', 'RB_longeron_-1_1', 'RB_longeron_1_-1', 'RB_longeron_-1_-1')}

    # ---------------- NC-a：V1 回放 ----------------
    nca = {'expectation': 'max≈28.85 mm³（V1 FAIL 登记值），阳性≥16；V3 对照=0',
           'positives': [], 'max_common_volume_mm3': 0.0, 'v3_control_positives': []}
    for st in v1_stations(P):
        sleeve_v1 = sleeve_envelope(st['x'], st['sy'], st['z'], od=st['sleeve_od'])
        v = common_volume(sleeve_v1, rails[st['rail']])
        if isinstance(v, dict):
            result['failures'].append(f"NC-a error {st['pair_id']}: {v}")
            continue
        if v > 1e-6:
            nca['positives'].append({'pair_id': st['pair_id'], 'sleeve_od': st['sleeve_od'],
                                     'common_volume_mm3': v})
        nca['max_common_volume_mm3'] = max(nca['max_common_volume_mm3'], v)
    # V3 对照组（Ø4，z=±105.3/109.0）
    for st in expected_stations(P):
        sleeve_v3 = sleeve_envelope(st['x'], st['sy'], st['z'])
        v = common_volume(sleeve_v3, rails[st['rail']])
        if isinstance(v, dict):
            result['failures'].append(f"NC-a v3 control error {st['pair_id']}: {v}")
            continue
        if v > 1e-6:
            nca['v3_control_positives'].append({'pair_id': st['pair_id'], 'common_volume_mm3': v})
    nca['positive_count'] = len(nca['positives'])
    nca['replay_vs_registered_max'] = {
        'registered_v1_max_mm3': V1_MAX_EXPECT,
        'replay_max_mm3': nca['max_common_volume_mm3'],
        'rel_diff': abs(nca['max_common_volume_mm3'] - V1_MAX_EXPECT) / V1_MAX_EXPECT}
    nca['detect_ok'] = (nca['positive_count'] >= 16 and
                        abs(nca['replay_vs_registered_max']['rel_diff']) < 0.02 and
                        not nca['v3_control_positives'])
    if not nca['detect_ok']:
        result['failures'].append('NC-a V1 replay detection failed')
    result['nc_a'] = nca

    # ---------------- NC-a2：V2 回放（同站位双栓互侵） ----------------
    # V2 状态（s03c 记录）：桥第二栓在 (154.85,±1,109.0)，与同 x 的 G03/G04 梁栓 (154.85,±1,105.3)
    # z 间距 3.7 < 垫圈 Ø6 → 头/垫圈/套互侵；登记 V2 max_intrusion 15.208025245922368（12 对）。
    nca2 = {'expectation': 'max≈15.21 mm³（V2 FAIL 登记 max_intrusion 15.208025245922368），阳性≥2（G03/G04 两侧）',
            'pairs': [], 'max_common_volume_mm3': 0.0}
    for gid, sy in (('G03', 1), ('G04', -1)):
        v2_b = bolt_envelope(154.85, sy, 109.0)
        v2_w = washer_envelope(154.85, sy, 109.0)
        v2_s = sleeve_envelope(154.85, sy, 109.0)
        for kind, v2p in (('bolt', v2_b), ('washer', v2_w), ('sleeve', v2_s)):
            for mkind in ('bolt', 'washer', 'sleeve'):
                real = import_step(str(RUN / 'exports' / f'e1_anchor_{mkind}_{gid}_0.step'))
                v = common_volume(v2p, real)
                if isinstance(v, dict):
                    result['failures'].append(f'NC-a2 error {gid} {kind}/{mkind}: {v}')
                    continue
                if v > 1e-6:
                    nca2['pairs'].append({'v2_part': f'v2_bridge_{kind}@{gid}',
                                          'real_part': f'e1_anchor_{mkind}_{gid}_0',
                                          'common_volume_mm3': v})
                nca2['max_common_volume_mm3'] = max(nca2['max_common_volume_mm3'], v)
    nca2['positive_count'] = len(nca2['pairs'])
    nca2['replay_vs_registered_max'] = {
        'registered_v2_max_mm3': 15.208025245922368,
        'replay_max_mm3': nca2['max_common_volume_mm3'],
        'rel_diff': abs(nca2['max_common_volume_mm3'] - 15.208025245922368) / 15.208025245922368}
    nca2['detect_ok'] = (nca2['positive_count'] >= 2 and
                         abs(nca2['replay_vs_registered_max']['rel_diff']) < 0.02)
    if not nca2['detect_ok']:
        result['failures'].append('NC-a2 V2 replay detection failed')
    result['nc_a2'] = nca2

    # ---------------- NC-b：缺对偶/错轴变异 ----------------
    mut = unmodified_upper_beam(20)
    # 钻 4 盲孔 Ø3.4 深 12（轴 Y，自端面 y=±101.15 向内）；G01-0 变异偏移 1mm → x=16.5
    drilled = [(16.5, 1), (24.5, 1), (15.5, -1), (24.5, -1)]
    for x, sy in drilled:
        mut = mut - cylinder_at(3.4, 12, (x, sy*95.15, 105.3))  # 自端面 y=±101.15 向内 12mm，孔心 y=±95.15
    fstep = work / 'mut_beam_g01_offset.step'
    export_step(mut, str(fstep))
    mut_rb = import_step(str(fstep))
    got = []  # (x, z, end_sy) 端面感知：盲孔柱面 bbox 的 y 中心符号区分 ±端
    for r, loc, drc, face in cyl_faces(mut_rb):
        if abs(r - 1.7) <= 1e-4 and abs(abs(drc[1]) - 1) <= 1e-6:
            fb = face.bounding_box()
            end_sy = 1 if (fb.min.Y + fb.max.Y) / 2 > 0 else -1
            got.append((round(loc[0], 6), round(loc[2], 6), end_sy))
    expected_set = {(15.5, 105.3, 1), (24.5, 105.3, 1), (15.5, 105.3, -1), (24.5, 105.3, -1)}
    extra = sorted(g for g in got if g not in expected_set)
    # 逐栓位配对（r30 口径，容差 1e-3，端面感知）：G01-0 应报缺孔，其余三位应找到
    station_hits = {}
    for pid, x, sy in (('G01-0', 15.5, 1), ('G01-1', 24.5, 1), ('G02-0', 15.5, -1), ('G02-1', 24.5, -1)):
        station_hits[pid] = any(abs(g[0] - x) < 1e-3 and abs(g[1] - 105.3) < 1e-3 and g[2] == sy
                                for g in got)
    ncb = {'mutation': 'G01-0 盲孔 x=15.5→16.5（偏移 1mm）；变异件 _work/mut_beam_g01_offset.step 重建并重读回',
           'expected_holes': sorted(expected_set), 'found_holes': sorted(got),
           'station_face_found': station_hits, 'detected_extra': extra,
           'detect_ok': (station_hits == {'G01-0': False, 'G01-1': True, 'G02-0': True, 'G02-1': True}
                         and extra == [(16.5, 105.3, 1)])}
    if not ncb['detect_ok']:
        result['failures'].append('NC-b mutation detection failed')
    result['nc_b'] = ncb

    # ---------------- NC-c：既有件冲突变异 ----------------
    screw_p = shear_web_screw_envelope(1)     # 既有 shear_web_screw_1_150_94 包络
    mut_bolt = bolt_envelope(154.0, 1, 94.0)  # 变异：把栓放到既有栓站位
    v_mut = common_volume(mut_bolt, screw_p)
    real_bolt = import_step(str(RUN / 'exports' / 'e1_anchor_bolt_G03_0.step'))
    v_real = common_volume(real_bolt, screw_p)
    ncc = {'mutation': '变异栓包络置于既有 shear_web_screw_1_150_94 站位 (154,+1,94)，轴 Y',
           'mutated_bolt_vs_screw_common_mm3': v_mut,
           'real_G03_0_bolt_vs_same_screw_common_mm3': v_real,
           'analytic_expect_mm3': round(math.pi * 1.5**2 * 10.0, 4),
           'detect_ok': (not isinstance(v_mut, dict)) and v_mut > 50 and
                        (not isinstance(v_real, dict)) and v_real <= 1e-6}
    if not ncc['detect_ok']:
        result['failures'].append('NC-c conflict mutation detection failed')
    result['nc_c'] = ncc

    result['verdict'] = 'PASS' if not result['failures'] else 'FAIL'
    result['elapsed_s'] = round(time.time() - t0, 3)
    write_json(ev / 'review_negative_controls.json', result)
    print('verdict', result['verdict'])
    print('NC-a: positives', nca['positive_count'], 'max', nca['max_common_volume_mm3'],
          'rel_diff', round(nca['replay_vs_registered_max']['rel_diff'], 6),
          'v3_control', len(nca['v3_control_positives']))
    print('NC-a2: positives', nca2['positive_count'], 'max', nca2['max_common_volume_mm3'],
          'rel_diff', round(nca2['replay_vs_registered_max']['rel_diff'], 6))
    print('NC-b:', ncb['detect_ok'], 'station_hits', ncb['station_face_found'], 'extra', ncb['detected_extra'])
    print('NC-c:', ncc['detect_ok'], 'mut', v_mut, 'real', v_real)
    print('failures', result['failures'], 'elapsed', result['elapsed_s'])


if __name__ == '__main__':
    main()
