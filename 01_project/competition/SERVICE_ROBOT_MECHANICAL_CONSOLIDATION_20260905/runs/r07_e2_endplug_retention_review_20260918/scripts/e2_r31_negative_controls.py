# -*- coding: utf-8 -*-
"""R07-E2 独立复验 r31：三个负控制实验——先证明检查链"能报"，再信任"未报"。
NC-a 全长竖销变异（T3 十字相交反事实）：每站构造全长 Ø4.4 竖销（贯通双壁+全塞高），
  与解析 M4 螺钉包络(Ø4, x∈[161,183])布尔交集 → 8/8 必须报阳性（全长销不可行的几何证明）；
  对照：全部 16 件真实分段销/栓 vs 同包络 → 0（r30 已逐件核，此处汇总复核）。
  另记录十字开孔销剩余韧带解析值（(4.4-4.0)/2=0.2mm/边）与候选方登记 0.1mm 的差异。
NC-b 缺对偶/错轴变异：_work 重建 RB_end_plug_1_-1_1，竖孔偏移 +1mm(164→165)，
  导出 STEP 重读回，用 r30 的孔审计判定 → 报 missing=(164,−107.15) extra=(165,−107.15)。
NC-c 既有件冲突变异（双通道）：
  c1 翼销加长至 z=−113.6（侵入翼根叉垫板区）vs 真实 build 的 wing_root_fork 实例 → 阳性；
     真实导出销 vs 同叉 → 0。
  c2 stub_out 平移 +x 6mm（对错位无孔塞体）vs exports 端塞 → 阳性。
所有变异件只在 _work/ 隔离目录重建并重读回后判定。"""
import json, math, sys, time
from pathlib import Path
from e2_common import (REV, RUN, ENG, write_json, common_volume, import_step, export_step,
                       load_params, stations, m4_screw_envelope, full_length_pin,
                       plug_rebuild, cylinder_at, bbox, cyl_faces, R_HOLE, C,
                       SOURCE_SHA256_EXPECT, PARAMS_SHA256_EXPECT, sha256_file)

TOL = 1e-6


def main():
    t0 = time.time()
    ev = REV / 'evidence'
    work = REV / '_work'
    work.mkdir(exist_ok=True)
    P, params_hash = load_params()
    sts = stations(P)
    result = {'review': 'R07_E2_INDEPENDENT_REVERIFY', 'script': 'e2_r31_negative_controls.py',
              'reviewed_run': RUN.name, 'nc_a': {}, 'nc_b': {}, 'nc_c': {},
              'failures': [], 'verdict': None}

    # ---------------- NC-a：全长竖销 vs M4 螺钉包络（T3 反事实） ----------------
    nca = {'expectation': '全长竖销与 M4 螺钉包络 8/8 站相交（阳性）；真实分段销/栓 16/16 零交',
           'full_pin_vs_screw': [], 'real_stubs_vs_screw': [], 'positives': 0}
    for st in sts:
        pin = full_length_pin(st['x'], st['y'], st['sz'])
        env = m4_screw_envelope(st['sx'], st['sy'], st['sz'])
        v = common_volume(pin, env)
        nca['full_pin_vs_screw'].append({'station': st['id'], 'common_volume_mm3': v})
        if isinstance(v, dict) or v <= TOL:
            result['failures'].append(f"NC-a full pin {st['id']} not detected: {v}")
        else:
            nca['positives'] += 1
    for st in sts:
        snames = ([f"e2_stub_out_{st['id']}", f"e2_stub_bay_{st['id']}"] if st['sz'] > 0 else
                  [f"e2_stub_bay_{st['id']}", f"e2_pin_wing_{st['id']}"])
        for sn in snames:
            s = import_step(str(RUN / 'exports' / f'{sn}.step'))
            v = common_volume(s, m4_screw_envelope(st['sx'], st['sy'], st['sz']))
            nca['real_stubs_vs_screw'].append({'part': sn, 'common_volume_mm3': v})
            if not isinstance(v, float) or v > TOL:
                result['failures'].append(f'NC-a control {sn} vs screw: {v}')
    nca['ligament_analytic_mm_per_side'] = (4.4 - 4.0) / 2
    nca['candidate_registered_ligament_mm'] = 0.1
    nca['ligament_note'] = ('候选方登记"十字开孔销剩余韧带 0.1mm"；本审阅解析 (Ø4.4-Ø4.0)/2=0.2mm/边。'
                            '两者同量级且均结构无效，不影响 T3 结论（全长销几何不可共存已证）→ 观察项')
    nca['detect_ok'] = (nca['positives'] == 8 and
                        all(isinstance(r['common_volume_mm3'], float) and r['common_volume_mm3'] <= TOL
                            for r in nca['real_stubs_vs_screw']))
    if not nca['detect_ok']:
        result['failures'].append('NC-a detection incomplete')
    result['nc_a'] = nca

    # ---------------- NC-b：端塞竖孔错轴变异 ----------------
    mut = plug_rebuild(1, -1, 1, hole_dx=1.0)   # H03 塞：竖孔 164→165
    fstep = work / 'mut_plug_hole_offset.step'
    export_step(mut, str(fstep))
    mut_rb = import_step(str(fstep))
    got = set()
    for r, loc, drc, face in cyl_faces(mut_rb):
        if abs(r - R_HOLE) <= 1e-4 and abs(abs(drc[2]) - 1) <= 1e-6:
            got.add((round(loc[0], 6), round(loc[1], 6)))
    expected = {(164.0, -C)}
    missing = [e for e in sorted(expected) if e not in got]
    extra = [g for g in sorted(got) if g not in expected]
    ncb = {'mutation': 'RB_end_plug_1_-1_1 竖孔 x=164→165（+1mm）；_work 重建重读回',
           'expected': sorted(expected), 'found': sorted(got),
           'detected_missing': missing, 'detected_extra': extra,
           'detect_ok': missing == [(164.0, -C)] and extra == [(165.0, -C)]}
    if not ncb['detect_ok']:
        result['failures'].append('NC-b mutation detection failed')
    result['nc_b'] = ncb

    # ---------------- NC-c：既有件冲突变异 ----------------
    # c2（免 build 通道）：stub_out 平移 +x 6mm vs exports 端塞
    plug_h03 = import_step(str(RUN / 'exports' / 'RB_end_plug_1_-1_1.step'))
    stub_h03 = import_step(str(RUN / 'exports' / 'e2_stub_out_H03.step'))
    from build123d import Location
    stub_shifted = stub_h03.moved(Location((6.0, 0, 0)))
    v_c2 = common_volume(stub_shifted, plug_h03)
    v_c2_ctrl = common_volume(stub_h03, plug_h03)
    ncc2 = {'mutation': 'e2_stub_out_H03 平移 +x 6mm（对错位无孔塞体）',
            'mutated_vs_plug_common_mm3': v_c2, 'real_vs_plug_common_mm3': v_c2_ctrl,
            'detect_ok': (not isinstance(v_c2, dict)) and v_c2 > 1.0 and
                         isinstance(v_c2_ctrl, float) and v_c2_ctrl <= TOL}
    if not ncc2['detect_ok']:
        result['failures'].append(f'NC-c2 detection failed: {ncc2}')
    # c1（build 通道）：翼销加长侵入翼根叉垫板区 vs 真实 fork 实例
    src_hash = sha256_file(ENG / 'spacecraft_model.py')
    pin_ok = (src_hash == SOURCE_SHA256_EXPECT and params_hash == PARAMS_SHA256_EXPECT)
    ncc1 = {'basis_pin_ok': pin_ok}
    if not pin_ok:
        result['failures'].append('NC-c1 basis pin mismatch - skipped')
        ncc1['detect_ok'] = False
    else:
        sys.path.insert(0, str(ENG))
        import spacecraft_model as sm
        model, shapes, receipt = sm.build('service', include_arm=False)
        fork_names = [n for n in shapes if 'wing_root_fork' in n]
        ncc1['fork_instances'] = fork_names
        # H08: sx=1, sy=1, sz=-1 → 销位 (164, 107.15)
        mut_pin = cylinder_at(4.4, 4.35, (164.0, C, (-113.6 - 109.25) / 2))
        real_pin = import_step(str(RUN / 'exports' / 'e2_pin_wing_H08.step'))
        v_mut = sum(v for v in (common_volume(mut_pin, shapes[fn]) for fn in fork_names)
                    if isinstance(v, float))
        v_real = sum(v for v in (common_volume(real_pin, shapes[fn]) for fn in fork_names)
                     if isinstance(v, float))
        ncc1.update({'mutation': 'e2_pin_wing_H08 加长至 z=-113.6（侵入垫板区 0.45mm）',
                     'mutated_vs_forks_common_mm3': v_mut,
                     'real_vs_forks_common_mm3': v_real,
                     'detect_ok': v_mut > 0.1 and v_real <= TOL})
        if not ncc1['detect_ok']:
            result['failures'].append(f'NC-c1 detection failed: {ncc1}')
    result['nc_c'] = {'c1_wing_pad': ncc1, 'c2_shifted_stub': ncc2}

    result['verdict'] = 'PASS' if not result['failures'] else 'FAIL'
    result['elapsed_s'] = round(time.time() - t0, 3)
    write_json(ev / 'review_e2_negative_controls.json', result)
    print('verdict', result['verdict'])
    print('NC-a: positives', nca['positives'], '/8; full-pin common sample',
          nca['full_pin_vs_screw'][0], '; real stubs all zero:', nca['detect_ok'])
    print('NC-b:', ncb['detect_ok'], missing, extra)
    print('NC-c1:', ncc1.get('detect_ok'), ncc1.get('mutated_vs_forks_common_mm3'),
          ncc1.get('real_vs_forks_common_mm3'))
    print('NC-c2:', ncc2['detect_ok'], v_c2, v_c2_ctrl)
    print('failures', result['failures'], 'elapsed', result['elapsed_s'])


if __name__ == '__main__':
    main()
