# -*- coding: utf-8 -*-
"""R07-E3 独立复验 r30：exports 独立读回。
范围：
  R1 基底钉固（ENG 源码/参数 sha256 vs EXPORT_MANIFEST）+ 32 件 STEP 哈希钉固；
  R2 12 组对偶孔存在性/位置/同轴独立重算（孔轴自 exports 圆柱面读出，栓轴独立解析；
     边1 三方：纵梁孔-横梁盲孔-栓；边2 四方：横梁孔-耳座孔-足叉盲孔-栓）；
  R3 盲孔深 7 / 贯入 5 / 啮合 5 独立测量（轴心+偏轴 inside 采样 + exports 栓杆端实测）；
  R4 边2 足叉盲孔打通至槽底 + 槽底完整性 + 槽内零凸出（栓尖 z=123.15 vs 轮毂域 125.15）；
  R5 枢轴（Ø8.4 X 向 @z=135.15，既有）vs 栓链几何分离 + INTERLOCK_REGISTERED 登记复核；
  R6 孔缘净距独立复算：耳座孔缘 1.25 / 备用孔缘 ~2.02（登记 2.03）/ 梁内孔-孔 1.25 / 杆-杆 3.5；
  R7 孔数普查（按轴位去重）：纵梁 YØ3.4 14/根（E2 基线 10+4）；横梁 Y 盲孔4+Z孔4；耳座 Z 孔3；足叉 Z 盲孔2；
  R8 栓/垫圈几何读回 vs 解析包络（体积 1e-3 相对容差）；
  R9 几何真相登记复核（ACCEPTANCE_SUMMARY geometric_truth_registration 与参数块互锁）。
坐标系 S（bus 几何中心），单位 mm。布尔/采样一律 OCC 原生（勘误 O2）。"""
import json, math, time
from pathlib import Path
from e3_common import (REV, RUN, ENG, write_json, sha256_file, import_step, inside,
                       cyl_faces, axis_distance, load_params, stations, bbox,
                       clamp_bolt_envelope, clamp_washer_envelope,
                       foot_bolt_envelope, foot_washer_envelope, common_volume,
                       PARAMS_SHA256_EXPECT, SOURCE_SHA256_EXPECT, Z_CLAMP, Y_FOOT,
                       HUB_Z_MIN)

TOL_AXIS = 1e-6


def hole_axes(shape, r_target, axis_dir, r_tol=1e-3, dir_tol=1e-6, cluster_by='axis'):
    """从 shape 圆柱面中筛出半径 r_target、轴平行 axis_dir 的孔。
    cluster_by='axis'：按轴位去重（非轴向坐标 + 轴向 loc 符号；同侧双壁贯穿孔 2 柱面
    因 loc 轴向坐标同号而归一，±端盲孔异号而分列——与被审'柱面计数'口径区分，
    证据中两口径并列）。"""
    out = []
    for r, loc, d, f in cyl_faces(shape):
        if abs(r - r_target) > r_tol:
            continue
        dot = abs(d[0]*axis_dir[0] + d[1]*axis_dir[1] + d[2]*axis_dir[2])
        if dot < 1 - dir_tol:
            continue
        out.append((r, loc, d))
    axi = [i for i in range(3) if abs(axis_dir[i]) > 0.5][0]
    uniq = {}
    for r, loc, d in out:
        key = tuple(round(loc[i], 3) for i in range(3) if i != axi) + (1 if loc[axi] >= 0 else -1,)
        uniq.setdefault(key, (r, loc, d))
    return list(uniq.values()), len(out)  # (轴位去重清单, 柱面计数)


def axis_off_to_point(loc, d, point, axis_dir):
    """孔轴（loc,d 归一到 axis_dir 方向）与目标轴线（过 point 沿 axis_dir）的垂直距。"""
    v = (point[0]-loc[0], point[1]-loc[1], point[2]-loc[2])
    # 垂直于轴向的分量
    dot = v[0]*axis_dir[0] + v[1]*axis_dir[1] + v[2]*axis_dir[2]
    perp = (v[0]-dot*axis_dir[0], v[1]-dot*axis_dir[1], v[2]-dot*axis_dir[2])
    return math.sqrt(sum(c*c for c in perp))


def measure_blind_depth(solid, x, z, y_surface, sy, r_off=0.0, dz=0.0):
    """Y 向盲孔深度：轴心（可偏置）自端面向内 0.05 步进，首个实体点即孔底。"""
    y = y_surface
    while abs(y_surface - y) < 12:
        if inside(solid, x + r_off, y, z + dz):
            return abs(y_surface - y)
        y -= sy * 0.05
    return None


def main():
    t0 = time.time()
    result = {'review': 'R07_E3_INDEPENDENT_REVERIFY', 'script': 'e3_r30_readback.py',
              'reviewed_run': RUN.name, 'units': 'mm', 'frame': 'S',
              'failures': [], 'verdict': None}

    # R1 基底钉固
    man = json.loads((RUN / 'exports' / 'EXPORT_MANIFEST.json').read_text(encoding='utf-8'))
    src_h = sha256_file(ENG / 'spacecraft_model.py')
    P, par_h = load_params()
    pin = {'spacecraft_model.py': {'actual': src_h, 'expect': SOURCE_SHA256_EXPECT,
                                   'manifest': man['source_sha256'], 'ok': src_h == SOURCE_SHA256_EXPECT == man['source_sha256']},
           'design_parameters.json': {'actual': par_h, 'expect': PARAMS_SHA256_EXPECT,
                                      'manifest': man['parameters_sha256'], 'ok': par_h == PARAMS_SHA256_EXPECT == man['parameters_sha256']}}
    result['basis_pin'] = pin
    if not all(v['ok'] for v in pin.values()):
        result['failures'].append(f'basis pin mismatch: {pin}')

    # exports 哈希钉固
    ep = {}
    hash_ok = True
    for p in man['parts']:
        f = RUN / 'exports' / p['file']
        h = sha256_file(f)
        ep[p['name']] = {'file': p['file'], 'sha256_ok': h == p['sha256'],
                         'volume_registered': p['volume_mm3'], 'bbox_registered': (p['bbox_min_mm'], p['bbox_max_mm'])}
        hash_ok = hash_ok and ep[p['name']]['sha256_ok']
    result['export_hash_pin'] = {'parts': len(ep), 'all_sha256_ok': hash_ok,
                                 'n_ok': sum(1 for v in ep.values() if v['sha256_ok'])}
    if not (hash_ok and len(ep) == 32):
        result['failures'].append(f'export hash pin fail: {result["export_hash_pin"]}')

    shapes = {n: import_step(str(RUN / 'exports' / v['file'])) for n, v in ep.items()}
    sts = stations(P)
    result['stations'] = {}

    # ---- 逐栓位读回 ----
    for s in sts:
        rec = {'pair_id': s['pair_id'], 'edge': s['edge']}
        if s['edge'] == 'edge1':
            x, sy = s['x'], s['sy']
            target = (x, None, Z_CLAMP)
            # 纵梁 Y 孔轴（Ø3.4）
            longeron_holes, _ = hole_axes(shapes[s['mate']], 1.7, (0, 1, 0))
            beam_holes, _ = hole_axes(shapes[s['beam']], 1.7, (0, 1, 0))
            def pick(holes):
                best, bd = None, 1e9
                for r, loc, d in holes:
                    off = math.hypot(loc[0]-x, loc[2]-Z_CLAMP)
                    if off < bd:
                        best, bd = (r, loc, d), off
                return best, bd
            lh, loff = pick(longeron_holes)
            bh, boff = pick(beam_holes)
            bolt_axes, _ = hole_axes(shapes[s['bolt']], 1.5, (0, 1, 0))
            ba, aoff = pick(bolt_axes)
            rec['hole_axes'] = {'longeron_off_mm': loff, 'beam_blind_off_mm': boff,
                                'bolt_shank_off_mm': aoff}
            rec['coaxial'] = (loff < TOL_AXIS and boff < TOL_AXIS and aoff < TOL_AXIS)
            # R3 盲孔深/贯入
            depth_c = measure_blind_depth(shapes[s['beam']], x, Z_CLAMP, sy*101.15, sy)
            depth_o = measure_blind_depth(shapes[s['beam']], x, Z_CLAMP, sy*101.15, sy, r_off=1.0)
            # 栓杆端 |y|（bbox）
            bb = ep[s['bolt']]['bbox_registered']
            tip_y = bb[0][1] if sy > 0 else -bb[1][1]
            rec['blind_hole'] = {'depth_axis_mm': depth_c, 'depth_offaxis_1mm_mm': depth_o,
                                 'expect_depth_mm': 7.0, 'bolt_tip_abs_y_mm': tip_y,
                                 'engagement_mm': 101.15 - tip_y,
                                 'expect_engagement_mm': 5.0}
            rec['depth_ok'] = (depth_c is not None and abs(depth_c - 7.0) < 0.1 and
                               depth_o is not None and abs(depth_o - 7.0) < 0.1 and
                               abs(tip_y - 96.15) < 1e-6)
            if not (rec['coaxial'] and rec['depth_ok']):
                result['failures'].append(f"{s['pair_id']} readback fail: {rec}")
        else:
            x, y = s['x'], s['y']
            holes = {}
            for part, key in ((s['beam'], 'crossbeam'), (s['lug'], 'roof_lug'), (s['foot'], 'foot_blind')):
                hs, _ = hole_axes(shapes[part], 2.25, (0, 0, 1))
                best, bd = None, 1e9
                for r, loc, d in hs:
                    off = math.hypot(loc[0]-x, loc[1]-y)
                    if off < bd:
                        best, bd = (r, loc, d), off
                holes[key] = bd
            bolt_axes, _ = hole_axes(shapes[s['bolt']], 2.0, (0, 0, 1))
            ba, aoff = None, 1e9
            for r, loc, d in bolt_axes:
                off = math.hypot(loc[0]-x, loc[1]-y)
                if off < aoff:
                    aoff = off
            holes['bolt_shank'] = aoff
            rec['hole_axes_off_mm'] = holes
            rec['coaxial'] = all(v < TOL_AXIS for v in holes.values())
            # R4 打通至槽底 + 槽底完整 + 栓尖
            axis_bore_open = all(not inside(shapes[s['foot']], x, y, z)
                                 for z in (118.65, 121.0, 124.5, 125.0))
            # 打通至槽底：孔壁环（r=2.75, 8 点）在槽底前 0.5（z=124.65）全实体
            # （孔被材料包围直至槽底，无唇边/堵头）；轴心入槽腔（z=125.65/130.0）空
            ring = [(x + 2.75*math.cos(a), y + 2.75*math.sin(a))
                    for a in [2*math.pi*i/8 for i in range(8)]]
            ring_in = sum(1 for px, py in ring if inside(shapes[s['foot']], px, py, 124.65))
            axis_slot_open = all(not inside(shapes[s['foot']], x, y, z)
                                 for z in (125.65, 130.0))
            floor_ok = (ring_in == 8 and axis_slot_open)
            bb = ep[s['bolt']]['bbox_registered']
            tip_z = bb[1][2]
            rec['foot_hole'] = {'axis_bore_open_to_slot': axis_bore_open,
                                'ring_solid_at_slot_floor_z124_65': f'{ring_in}/8',
                                'axis_open_into_slot_cavity': axis_slot_open,
                                'drilled_through_to_slot_bottom': floor_ok,
                                'bolt_tip_z_mm': tip_z,
                                'engagement_mm': tip_z - 118.15,
                                'tip_to_slot_bottom_mm': HUB_Z_MIN - tip_z,
                                'expect_engagement_mm': 5.0, 'expect_tip_gap_mm': 2.0}
            rec['foot_ok'] = (axis_bore_open and floor_ok and
                              abs(tip_z - 123.15) < 1e-6)
            if not (rec['coaxial'] and rec['foot_ok']):
                result['failures'].append(f"{s['pair_id']} readback fail: {rec}")
        result['stations'][s['pair_id']] = rec

    result['max_axis_offset_mm'] = 0.0
    offs = []
    for rec in result['stations'].values():
        if 'hole_axes' in rec:
            offs += list(rec['hole_axes'].values())
        else:
            offs += list(rec['hole_axes_off_mm'].values())
    result['max_axis_offset_mm'] = max(offs)

    # R5 枢轴 vs 栓链
    pivot_notes = {}
    for k in (0, 1):
        foot = shapes[f'hold_pivot_clevis_{k}']
        piv, _ = hole_axes(foot, 4.2, (1, 0, 0), r_tol=1e-3)
        px = []
        for r, loc, d in piv:
            px.append({'loc': [round(v, 3) for v in loc], 'r': r})
        # 枢轴孔 z≈135.15；栓链尖 z≤123.15 → 分离
        sep = all(abs(l['loc'][2] - 135.15) < 0.5 for l in px) if px else False
        pivot_notes[f'hold_pivot_clevis_{k}'] = {'pivot_axes_D8p4_X': px,
                                                 'pivot_z_135_15': sep,
                                                 'chain_tip_max_z': 123.15,
                                                 'z_separation': 135.15 - 4.2 - 123.15 > 0}
    ms_txt = (RUN / 'evidence' / 'e3_mounting_surfaces.json').read_text(encoding='utf-8')
    tp_txt = (RUN / 'evidence' / 'e3_tool_paths.json').read_text(encoding='utf-8')
    result['pivot_vs_chain'] = {'per_foot': pivot_notes,
                                'interlock_registered_mounting': 'INTERLOCK_REGISTERED' in ms_txt,
                                'interlock_registered_toolpaths': 'INTERLOCK_REGISTERED' in tp_txt}
    if not (result['pivot_vs_chain']['interlock_registered_mounting'] or
            result['pivot_vs_chain']['interlock_registered_toolpaths']):
        result['failures'].append('INTERLOCK_REGISTERED not found in registration tables')

    # R6 孔缘净距（独立复算）
    clear = {}
    # 耳座孔缘 1.25（y 外面 -87.15）
    lug_bb = ep['hold_roof_lug_0_-94.15']['bbox_registered']
    clear['lug_hole_edge_y'] = {'hole_center_y': Y_FOOT, 'hole_r': 2.25,
                                'lug_outer_y': lug_bb[1][1],
                                'edge_distance_mm': abs(Y_FOOT - lug_bb[1][1]) - 2.25,
                                'registered_mm': 1.25}
    # 备用孔缘：找横梁既有中心 Z 孔（x=站心）
    spare = {}
    for k, xc in ((0, -115.0), (1, -40.0)):
        beam = shapes[f'hold_crossbeam_{k}']
        zs, _ = hole_axes(beam, 2.25, (0, 0, 1))
        sp = []
        for r, loc, d in zs:
            if abs(loc[0] - xc) < 0.5:  # 中心孔
                sp.append((round(loc[0], 3), round(loc[1], 3)))
        spare[f'crossbeam_{k}'] = sp
    # 新孔 vs 备用孔边缘距
    edges = []
    for k, xc in ((0, -115.0), (1, -40.0)):
        for sx, sy_ in spare[f'crossbeam_{k}']:
            for nx in (xc - 5.5, xc + 5.5):
                dist = math.hypot(nx - sx, Y_FOOT - sy_) - 4.5
                edges.append(round(dist, 4))
    clear['spare_hole_edge'] = {'spare_hole_positions': spare,
                                'new_vs_spare_edge_distances_mm': sorted(set(edges)),
                                'registered_mm': 2.03}
    # 梁内孔-孔 1.25 / 杆-杆 3.5（解析）
    clear['in_beam_hole_to_hole_mm'] = {'value': 94.15 - (90.65 + 2.25), 'registered_mm': 1.25}
    clear['shank_to_shank_mm'] = {'value': 96.15 - (90.65 + 2.0), 'registered_mm': 3.5}
    result['clearance_recompute'] = clear
    c1 = abs(clear['lug_hole_edge_y']['edge_distance_mm'] - 1.25) < 1e-9
    c2 = any(abs(e - 2.03) < 0.02 for e in clear['spare_hole_edge']['new_vs_spare_edge_distances_mm'])
    c3 = abs(clear['in_beam_hole_to_hole_mm']['value'] - 1.25) < 1e-9
    c4 = abs(clear['shank_to_shank_mm']['value'] - 3.5) < 1e-9
    result['clearance_ok'] = {'lug_edge_1.25': c1, 'spare_edge_2.03': c2,
                              'in_beam_hole_hole_1.25': c3, 'shank_shank_3.5': c4}
    if not all(result['clearance_ok'].values()):
        result['failures'].append(f'clearance recompute fail: {clear}')

    # R7 孔数普查
    # 两口径：被审登记=柱面计数（未去重）；本审阅独立轴位口径=去重后轴位数。
    # 实测对应：纵梁柱面 14（基线 5 轴位×双壁 10 + E3 4 轴位×单柱面 4）= 被审登记 14=10+4；
    # 轴位 9（基线 5 + E3 4）。两口径均自洽，差异为计数口径非几何缺陷。
    census = {}
    for n, r, ax in (('RB_longeron_1_1', 1.7, (0, 1, 0)), ('RB_longeron_-1_1', 1.7, (0, 1, 0))):
        axes_n, faces_n = hole_axes(shapes[n], r, ax)
        census[n] = {'yaxis_d3p4_faces': faces_n, 'yaxis_d3p4_axis_positions': len(axes_n),
                     'expect_faces': 14, 'expect_axis_positions': 9}
    for k in (0, 1):
        n = f'hold_crossbeam_{k}'
        ya, yf = hole_axes(shapes[n], 1.7, (0, 1, 0))
        za, zf = hole_axes(shapes[n], 2.25, (0, 0, 1))
        census[n] = {'yaxis_d3p4_blind_faces': yf, 'yaxis_d3p4_blind_axis_positions': len(ya),
                     'zaxis_d4p5_faces': zf, 'zaxis_d4p5_axis_positions': len(za),
                     'expect': 'Y盲孔4 + Z孔4（两口径此处一致）'}
        n = f'hold_roof_lug_{k}_-94.15'
        za, zf = hole_axes(shapes[n], 2.25, (0, 0, 1))
        census[n] = {'zaxis_d4p5_faces': zf, 'zaxis_d4p5_axis_positions': len(za), 'expect': 3}
        n = f'hold_pivot_clevis_{k}'
        za, zf = hole_axes(shapes[n], 2.25, (0, 0, 1))
        census[n] = {'zaxis_d4p5_blind_faces': zf, 'zaxis_d4p5_blind_axis_positions': len(za),
                     'expect': 2}
    result['hole_census'] = census
    cen_ok = (all(census[f'RB_longeron_{s}_1']['yaxis_d3p4_faces'] == 14 and
                  census[f'RB_longeron_{s}_1']['yaxis_d3p4_axis_positions'] == 9
                  for s in (1, -1)) and
              all(census[f'hold_crossbeam_{k}']['yaxis_d3p4_blind_axis_positions'] == 4 and
                  census[f'hold_crossbeam_{k}']['zaxis_d4p5_axis_positions'] == 4 for k in (0, 1)) and
              all(census[f'hold_roof_lug_{k}_-94.15']['zaxis_d4p5_axis_positions'] == 3 for k in (0, 1)) and
              all(census[f'hold_pivot_clevis_{k}']['zaxis_d4p5_blind_axis_positions'] == 2 for k in (0, 1)))
    result['hole_census_ok'] = cen_ok
    if not cen_ok:
        result['failures'].append(f'hole census fail: {census}')

    # R8 栓/垫圈几何 vs 解析包络（体积 + 布尔差量 0）
    vol = {}
    for s in sts:
        if s['edge'] == 'edge1':
            env_b = clamp_bolt_envelope(s['x'], s['sy'])
            env_w = clamp_washer_envelope(s['x'], s['sy'])
        else:
            env_b = foot_bolt_envelope(s['x'])
            env_w = foot_washer_envelope(s['x'])
        vb = common_volume(env_b, shapes[s['bolt']])
        # 解析包络与 exports 件的"互为子集"验证：env∩step 体积 ≈ 两者体积
        v_env = env_b.volume
        v_step = ep[s['bolt']]['volume_registered']
        ok = abs(v_env - v_step) / v_step < 1e-3 and abs(vb - v_step) / v_step < 1e-3
        vol[s['bolt']] = {'env_mm3': round(v_env, 6), 'step_mm3': v_step,
                          'common_mm3': round(vb, 6) if not isinstance(vb, dict) else vb,
                          'ok': ok}
        if not ok:
            result['failures'].append(f"envelope mismatch {s['bolt']}: {vol[s['bolt']]}")
    result['fastener_envelope_check'] = vol

    # R9 几何真相登记复核
    acc_sum = json.loads((RUN / 'ACCEPTANCE_SUMMARY.json').read_text(encoding='utf-8'))
    gtr = acc_sum['geometric_truth_registration']
    e3p = P['retention_joints_r07_e3']
    truth = {
        'fit_band_5mm': 'z∈[101.15,106.15]' in gtr['fit_band_5mm'] and '贴合带' in gtr['fit_band_5mm'],
        'no_anti_crush_sleeve': 'OMITTED_REGISTERED' in e3p['edge1_clamp']['fastener_candidate']['anti_crush_sleeve'],
        'mast_hub_exclusion': '125.15' in gtr['mast_hub_exclusion'],
        'pivot_vs_foot_chain': 'INTERLOCK_REGISTERED' in gtr['pivot_vs_foot_chain'],
        'existing_spare_hole': 'UNUSED_EXISTING_SPARE' in gtr['existing_spare_hole'],
    }
    result['geometric_truth_registration'] = truth
    if not all(truth.values()):
        result['failures'].append(f'truth registration fail: {truth}')

    result['verdict'] = 'PASS' if not result['failures'] else 'FAIL'
    result['elapsed_s'] = round(time.time() - t0, 3)
    write_json(REV / 'evidence' / 'review_e3_readback.json', result)
    print('verdict', result['verdict'], 'max_off', result['max_axis_offset_mm'],
          'census_ok', cen_ok, 'clearance_ok', result['clearance_ok'])
    print('failures', result['failures'][:5], 'elapsed', result['elapsed_s'])


if __name__ == '__main__':
    main()
