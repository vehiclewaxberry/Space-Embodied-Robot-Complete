# -*- coding: utf-8 -*-
"""R07-E3 独立复验 r31：三负控（证明审阅布尔链有检出能力）。
NC-a 探针 FAIL v1 参数态回放：v1（边2 栓链 y=-94.15 + 边1 贯入 8/杆端|y|=93.15）下
  边1 栓杆 vs 边2 栓杆 4 对相贯，登记值 16.370042/16.370132 mm3 量级（logs/s01b_probe_FAIL_v1.log）；
  本审阅用解析 v1 包络独立复算须报同量级阳性；v2 真实包络（exports）同 4 对须为 0。
NC-b 缺对偶/错轴变异：
  b1 缺对偶——解析填孔柱（Ø4.5 堵横梁新 Z 孔）fuse 进 exports 横梁后 vs 真实 foot bolt 杆 → 阳性；
  b2 错轴——exports foot bolt 平移 +x 1.0 后 vs exports 足叉（盲孔错轴）→ 阳性；真实位对照 0。
NC-c 栓链与既有件冲突变异（各含真实件对照 0；既有件取自独立 build）：
  c1 E1 锚固件——clamp 包络放到 E1 梁栓位 (154.85,+1,105.3) vs e1 套/栓 → 阳性；
  c2 柱贯通杆——foot 包络平移到 RB_pillar_tierod 轴位 vs 该包络 → 阳性；
  c3 R01 件——foot 包络平移到 shear_web_-1 实体区 vs 剪力板 → 阳性。
布尔一律 OCP 原生（勘误 O2）。"""
import json, math, sys, time
from pathlib import Path
from e3_common import (REV, RUN, ENG, write_json, import_step, common_volume,
                       clamp_bolt_envelope, foot_bolt_envelope, foot_bolt_v1,
                       cylinder_at, inside, bbox, load_params, stations,
                       sha256_file, PARAMS_SHA256_EXPECT, SOURCE_SHA256_EXPECT,
                       Z_CLAMP, Y_FOOT)

REGISTERED_V1 = {('E3P-J02-0', 'E3P-C01-0'): 16.370042182855656,
                 ('E3P-J02-1', 'E3P-C01-1'): 16.370132204695462,
                 ('E3P-J04-0', 'E3P-C02-0'): 16.370042181704193,
                 ('E3P-J04-1', 'E3P-C02-1'): 16.370132203247618}


def main():
    t0 = time.time()
    result = {'review': 'R07_E3_INDEPENDENT_REVERIFY', 'script': 'e3_r31_negative_controls.py',
              'reviewed_run': RUN.name, 'failures': [], 'verdict': None}
    pin = {'source': sha256_file(ENG / 'spacecraft_model.py') == SOURCE_SHA256_EXPECT,
           'params': load_params()[1] == PARAMS_SHA256_EXPECT}
    result['basis_pin_ok'] = all(pin.values())
    if not result['basis_pin_ok']:
        result['failures'].append(f'basis pin fail: {pin}')

    P, _ = load_params()
    sts = stations(P)
    by_id = {s['pair_id']: s for s in sts}

    # ---------------- NC-a：v1 回放 ----------------
    nca = {'expectation': 'v1 参数态 4 对边1杆 vs 边2杆相贯 ≈16.37 mm3；v2 真实件 4 对全 0',
           'registered_v1_mm3': {f'{k[0]}|{k[1]}': v for k, v in REGISTERED_V1.items()},
           'pairs': [], 'v2_controls': [], 'detect_ok': None}
    for (jid, cid), reg in REGISTERED_V1.items():
        j, c = by_id[jid], by_id[cid]
        v1_clamp = clamp_bolt_envelope(j['x'], j['sy'], shank_tip_y_abs=93.15)  # v1 贯入 8
        v1_foot = foot_bolt_v1(c['x'])                                          # v1 y=-94.15
        v = common_volume(v1_clamp, v1_foot)
        ok = (not isinstance(v, dict)) and abs(v - reg) < 1e-2
        nca['pairs'].append({'pair': [jid, cid], 'replay_mm3': v, 'registered_mm3': reg,
                             'abs_diff': None if isinstance(v, dict) else abs(v - reg),
                             'detect_ok': ok})
        # v2 对照（exports 真实件）
        v2c = common_volume(import_step(str(RUN / 'exports' / f"{j['bolt']}.step")),
                            import_step(str(RUN / 'exports' / f"{c['bolt']}.step")))
        nca['v2_controls'].append({'pair': [j['bolt'], c['bolt']], 'common_mm3': v2c,
                                   'zero_ok': (not isinstance(v2c, dict)) and v2c <= 1e-6})
    nca['detect_ok'] = (all(p['detect_ok'] for p in nca['pairs']) and
                        all(c['zero_ok'] for c in nca['v2_controls']))
    result['nc_a'] = nca
    if not nca['detect_ok']:
        result['failures'].append(f"NC-a fail: {nca['pairs']} / {nca['v2_controls']}")

    # ---------------- NC-b：缺对偶/错轴 ----------------
    ncb = {'b1_missing_dual_hole': {}, 'b2_axis_shift': {}, 'detect_ok': None}
    s = by_id['E3P-C01-0']  # x=-120.5, beam=hold_crossbeam_0, foot=hold_pivot_clevis_0
    beam_exp = import_step(str(RUN / 'exports' / 'hold_crossbeam_0.step'))
    foot_exp = import_step(str(RUN / 'exports' / 'hold_pivot_clevis_0.step'))
    bolt_exp = import_step(str(RUN / 'exports' / 'e3_foot_bolt_C01_0.step'))
    # b1 缺对偶：填孔柱堵横梁 Z 新孔 → 栓杆 vs 填孔柱阳性（量级 π*4*10≈125.7）
    plug = cylinder_at(4.5, 12.0, (s['x'], Y_FOOT, 101.15))
    v_b1 = common_volume(bolt_exp, plug)
    v_b1_real = common_volume(bolt_exp, beam_exp)
    ncb['b1_missing_dual_hole'] = {
        'mutation': 'hold_crossbeam_0 新 Z 孔 (x=-120.5,y=-90.65) 被 Ø4.5 填孔柱封堵',
        'bolt_vs_fillplug_mm3': v_b1,
        'bolt_vs_real_drilled_beam_mm3': v_b1_real,
        'detect_ok': (not isinstance(v_b1, dict)) and v_b1 > 100 and
                     (not isinstance(v_b1_real, dict)) and v_b1_real <= 1e-6}
    # b2 错轴：foot bolt 平移 +x 1.0 vs 足叉（盲孔错 1.0 < 孔径差 0.5/边 → 杆撞孔壁）
    from build123d import Location
    bolt_shifted = bolt_exp.moved(Location((1.0, 0, 0)))
    v_b2 = common_volume(bolt_shifted, foot_exp)
    v_b2_real = common_volume(bolt_exp, foot_exp)
    ncb['b2_axis_shift'] = {
        'mutation': 'e3_foot_bolt_C01_0 平移 +x 1.0（盲孔 Ø4.5 vs 杆 Ø4 隙 0.25/边 → 撞孔壁）',
        'shifted_vs_foot_mm3': v_b2, 'real_vs_foot_mm3': v_b2_real,
        'detect_ok': (not isinstance(v_b2, dict)) and v_b2 > 1 and
                     (not isinstance(v_b2_real, dict)) and v_b2_real <= 1e-6}
    ncb['detect_ok'] = ncb['b1_missing_dual_hole']['detect_ok'] and ncb['b2_axis_shift']['detect_ok']
    result['nc_b'] = ncb
    if not ncb['detect_ok']:
        result['failures'].append(f"NC-b fail: {ncb}")

    # ---------------- NC-c：与既有件冲突变异（独立 build 取既有件） ----------------
    sys.path.insert(0, str(ENG))
    import spacecraft_model as sm
    model, shapes, receipt = sm.build('service', include_arm=False)
    ncc = {'build_instances': len(receipt['instances']), 'cases': {}, 'detect_ok': None}

    def case(name, env, target_name, real_env, note):
        tgt = shapes[target_name]
        v_mut = common_volume(env, tgt)
        v_real = common_volume(real_env, tgt) if real_env is not None else 0.0
        ok = (not isinstance(v_mut, dict)) and v_mut > 1e-3 and \
             (not isinstance(v_real, dict)) and v_real <= 1e-6
        ncc['cases'][name] = {'mutation_target': target_name, 'note': note,
                              'mutated_mm3': v_mut, 'real_mm3': v_real, 'detect_ok': ok}
        return ok

    # c1 E1 锚固件：clamp 包络放到 E1 G03_0 梁栓位 (154.85,+1,105.3)
    from e3_common import Z_CLAMP as _zc
    e1_env = clamp_bolt_envelope(154.85, 1).moved(Location((0, 0, 105.3 - Z_CLAMP)))
    t1 = 'e1_anchor_bolt_G03_0' if 'e1_anchor_bolt_G03_0' in shapes else \
         [n for n in shapes if n.startswith('e1_anchor_bolt_G03')][0]
    case('c1_e1_anchor', e1_env, t1,
         clamp_bolt_envelope(-119.5, 1), 'clamp 包络置于 E1 梁栓位 (154.85,+1,105.3) vs E1 栓（同轴 Ø3 杆-杆相贯）；对照真实 J01_0 vs 同栓=0')

    # c2 柱贯通杆：foot 包络平移到 tierod 轴位
    tierods = sorted(n for n in shapes if 'tierod' in n)
    t2 = tierods[0]
    bb = bbox(shapes[t2])
    tx, ty = (bb[0]+bb[3])/2, (bb[1]+bb[4])/2
    mut2 = foot_bolt_envelope(tx, y=ty)
    case('c2_pillar_tierod', mut2, t2,
         foot_bolt_envelope(-120.5), f'foot 包络平移到 {t2} 轴位 ({tx:.2f},{ty:.2f})；对照真实 C01_0 vs 同杆=0')

    # c3 R01 剪力板：foot 包络平移到 shear_web_-1 实体区
    t3 = 'shear_web_-1'
    bb = bbox(shapes[t3])
    sx, sz = (bb[0]+bb[3])/2, (bb[2]+bb[5])/2
    sy_c = (bb[1]+bb[4])/2
    # 找实体点：剪力板厚度方向取 bbox 中面，x/z 中心应实体（验证 inside）
    assert inside(shapes[t3], sx, sy_c, sz), 'shear_web center not solid - adjust probe'
    mut3 = foot_bolt_envelope(sx, y=sy_c)
    case('c3_r01_shear_web', mut3, t3,
         foot_bolt_envelope(-120.5), f'foot 包络平移到 {t3} 实体区 ({sx:.1f},{sy_c:.2f},{sz:.1f})；对照真实 C01_0 vs 同板=0')

    ncc['detect_ok'] = all(c['detect_ok'] for c in ncc['cases'].values())
    result['nc_c'] = ncc
    if not ncc['detect_ok']:
        result['failures'].append(f"NC-c fail: {ncc['cases']}")

    result['verdict'] = 'PASS' if not result['failures'] else 'FAIL'
    result['elapsed_s'] = round(time.time() - t0, 3)
    write_json(REV / 'evidence' / 'review_e3_negative_controls.json', result)
    print('verdict', result['verdict'])
    print('NC-a:', nca['detect_ok'], [(p['pair'], round(p['replay_mm3'], 4)) for p in nca['pairs']])
    print('NC-b:', ncb['detect_ok'], ncb['b1_missing_dual_hole']['bolt_vs_fillplug_mm3'],
          ncb['b2_axis_shift']['shifted_vs_foot_mm3'])
    print('NC-c:', ncc['detect_ok'], {k: round(v['mutated_mm3'], 3) for k, v in ncc['cases'].items()})
    print('failures', result['failures'], 'elapsed', result['elapsed_s'])


if __name__ == '__main__':
    main()
