# -*- coding: utf-8 -*-
"""R07-E2 独立复验 r30：exports 全部 40 件 STEP 独立读回。
口径（自定期望，独立编码，不调用候选方 s05b/spec/parts 函数）：
  A) 8 站对偶孔存在性/位置/同轴：纵梁竖孔轴 vs 端塞竖孔轴 vs 短销/栓杆轴三线同轴；
  B) 闭孔完整度：纵梁双壁中面环采样；端塞塞心平面环采样（X 向 Ø3.3 导孔合法遮盖带
     |dy|<=1.65+dr 豁免，偏离带外点必报）+ 塞内偏置平面无豁免闭环；
  C) 短销几何实测：杆径 Ø4.4、z 区间、头 Ø7×4、垫圈 OD/ID/t、入塞 1.8mm（与实测塞 bbox 求交）、
     尖端让 M4 螺钉包络 0.1mm（解析包络距离 + 布尔零交）；
  D) T1 真相：实测塞截面 7.8×7.8 + WP02 源 9.8 与 WP03 重建 7.8 静态行核对；
  E) T2 真相：纵梁竖孔 2/根、塞竖孔 1/塞（无新孔）；E2 vs E1 纵梁 STEP 时间戳归一化 4/4 逐位；
  F) 登记表一致性：8/8/8/8 行、pair_id、轴/位置、UNKNOWN 保留、SHORT_ENGAGEMENT 登记；
  G) exports 字节 sha256 对 EXPORT_MANIFEST 逐件钉固（40 件）。
所有几何 S 系世界坐标，单位 mm。"""
import json, math, time
from pathlib import Path
from e2_common import (REV, RUN, RUN_E1, ENG, sha256_file, write_json, bbox, cyl_faces,
                       axis_distance, inside, import_step, load_params, stations,
                       m4_screw_envelope, step_normalize_timestamp, common_volume,
                       R_HOLE, R_SHANK, R_XBORE, PLUG_HALF, C,
                       PARAMS_SHA256_EXPECT)

TOL_FACE = 1e-3
TOL_PAR = 1e-6
TOL_OFF = 1e-3


def ring_check(solid, cx, cy, z, r, n=72, dr=0.05, bore_band=None):
    """Z 轴孔环采样（XY 平面）：r+dr 处 n 点应在实体内；bore_band=|dy|<=band 为合法在外带。"""
    outs, outs_illegal = [], []
    for i in range(n):
        a = 2*math.pi*i/n
        px, py = cx + (r+dr)*math.cos(a), cy + (r+dr)*math.sin(a)
        if not inside(solid, px, py, z):
            outs.append(round(a, 4))
            if bore_band is None or abs(py - cy) > bore_band:
                outs_illegal.append(round(a, 4))
    return outs, outs_illegal, inside(solid, cx, cy, z)


def find_z_hole(shape, x, y):
    cands = []
    for r, loc, drc, face in cyl_faces(shape):
        if abs(r - R_HOLE) <= 1e-4 and abs(abs(drc[2]) - 1) <= 1e-6:
            if abs(loc[0] - x) < TOL_FACE and abs(loc[1] - y) < TOL_FACE:
                cands.append((r, loc, drc, face))
    return cands[0] if cands else None


def main():
    t0 = time.time()
    ev = REV / 'evidence'
    exp = RUN / 'exports'
    P, params_hash = load_params()
    sts = stations(P)
    E2 = P['transverse_retention_r07_e2']
    ST = E2['stack_z_intervals_mm']
    FC = E2['fastener_candidate']

    man = json.loads((exp / 'EXPORT_MANIFEST.json').read_text(encoding='utf-8'))
    result = {
        'review': 'R07_E2_INDEPENDENT_REVERIFY', 'script': 'e2_r30_readback.py',
        'reviewed_run': RUN.name, 'units': 'mm', 'frame': 'S',
        'params_sha256': params_hash,
        'params_sha256_pin_ok': params_hash == PARAMS_SHA256_EXPECT,
        'export_hash_pin': {'checked': 0, 'mismatches': []},
        'stations': [], 'hole_census': {}, 'cross_run_longeron': {},
        't1_truth': {}, 't2_truth': {}, 'registration_audit': {},
        'measured_volumes_mm3': {}, 'failures': [], 'verdict': None,
    }

    shapes, solids = {}, {}
    names = sorted({st['longeron'] for st in sts} | {st['plug'] for st in sts})
    for n in names:
        shapes[n] = import_step(str(exp / f'{n}.step'))
        solids[n] = shapes[n].solids()[0]
    part_names = []
    for st in sts:
        if st['sz'] > 0:
            part_names += [f"e2_stub_out_{st['id']}", f"e2_washer_out_{st['id']}",
                           f"e2_stub_bay_{st['id']}", f"e2_washer_bay_{st['id']}"]
        else:
            part_names += [f"e2_stub_bay_{st['id']}", f"e2_washer_bay_{st['id']}",
                           f"e2_pin_wing_{st['id']}"]
    assert len(part_names) == 28
    for n in part_names:
        shapes[n] = import_step(str(exp / f'{n}.step'))

    for prec in man['parts']:
        ok = sha256_file(exp / prec['file']) == prec['sha256']
        result['export_hash_pin']['checked'] += 1
        if not ok:
            result['export_hash_pin']['mismatches'].append(prec['name'])
            result['failures'].append(f"export hash mismatch: {prec['name']}")
    if result['export_hash_pin']['checked'] != 40:
        result['failures'].append(f"manifest parts {result['export_hash_pin']['checked']} != 40")
    for n, s in shapes.items():
        result['measured_volumes_mm3'][n] = round(sum(so.volume for so in s.solids()), 6)

    # 孔面普查（T2：纵梁竖孔按独立轴位计数 2/根——一处贯穿孔双壁可能产生 2 个柱面；
    # 塞 1/塞）
    for n in names:
        axes_found = set()
        for r, loc, drc, f in cyl_faces(shapes[n]):
            if abs(r - R_HOLE) <= 1e-4 and abs(abs(drc[2]) - 1) <= 1e-6:
                axes_found.add((round(loc[0], 6), round(loc[1], 6)))
        cnt = len(axes_found)
        expect = 2 if n.startswith('RB_longeron_') else 1
        result['hole_census'][n] = {'found_axes': sorted(axes_found), 'expected': expect}
        if cnt != expect:
            result['failures'].append(f'{n} vertical hole axes {cnt} != {expect}')

    # 逐站检查
    for st in sts:
        rec = {'station': st['id'], 'expected': {k: st[k] for k in ('x', 'y', 'z', 'variant')}}
        x, y, sz = st['x'], st['y'], st['sz']
        # 纵梁孔
        fh = find_z_hole(shapes[st['longeron']], x, y)
        rec['longeron_hole'] = {'face_found': fh is not None}
        if fh is None:
            result['failures'].append(f"{st['id']} longeron hole not found")
        else:
            r, loc, drc, face = fh
            o1, i1, c1 = ring_check(solids[st['longeron']], x, y, sz*112.15, r)
            o2, i2, c2 = ring_check(solids[st['longeron']], x, y, sz*102.15, r)
            rec['longeron_hole'].update(axis_loc_mm=list(loc), axis_dir=list(drc),
                outer_wall_closed=(not o1) and (not c1), inner_wall_closed=(not o2) and (not c2))
            if not (rec['longeron_hole']['outer_wall_closed'] and rec['longeron_hole']['inner_wall_closed']):
                result['failures'].append(f"{st['id']} longeron wall not closed")
            rec['_longeron_axis'] = (loc, drc)
        # 端塞孔（含 X 向导孔合法遮盖带判据）
        fp = find_z_hole(shapes[st['plug']], x, y)
        rec['plug_hole'] = {'face_found': fp is not None}
        if fp is None:
            result['failures'].append(f"{st['id']} plug hole not found")
        else:
            r, loc, drc, face = fp
            outs, outs_illegal, center_in = ring_check(
                solids[st['plug']], x, y, sz*C, r, bore_band=R_XBORE + 0.05 + 1e-6)
            # 偏置平面（避开导孔带，塞内 z=sz*(C+2)）无豁免闭环
            o_off, i_off, c_off = ring_check(solids[st['plug']], x, y, sz*(C+2.0), r)
            rec['plug_hole'].update(axis_loc_mm=list(loc), axis_dir=list(drc),
                midplane_ring_outs=outs, midplane_illegal_outs=outs_illegal,
                center_void=(not center_in),
                offset_plane_closed=(not o_off) and (not c_off))
            if outs_illegal or center_in or not rec['plug_hole']['offset_plane_closed']:
                result['failures'].append(f"{st['id']} plug hole closure fail")
            rec['_plug_axis'] = (loc, drc)
        # 销/栓杆轴与同轴
        stub_names = ([f"e2_stub_out_{st['id']}", f"e2_stub_bay_{st['id']}"] if sz > 0 else
                      [f"e2_stub_bay_{st['id']}", f"e2_pin_wing_{st['id']}"])
        rec['coaxial'] = {}
        coax_ok = True
        axes = {'longeron': rec.get('_longeron_axis'), 'plug': rec.get('_plug_axis')}
        for sn in stub_names:
            cf = [c for c in cyl_faces(shapes[sn]) if abs(c[0] - R_SHANK) < 1e-4]
            if not cf:
                result['failures'].append(f'{sn} shank face not found'); coax_ok = False
                continue
            axes[sn] = (cf[0][1], cf[0][2])
        for a_name, b_name in [('longeron', 'plug')] + [('longeron', sn) for sn in stub_names] + \
                              [('plug', sn) for sn in stub_names]:
            a, b = axes.get(a_name), axes.get(b_name)
            if a is None or b is None:
                rec['coaxial'][f'{a_name}_vs_{b_name}'] = 'MISSING_AXIS'; coax_ok = False
                continue
            par, off = axis_distance(a[0], a[1], b[0], b[1])
            rec['coaxial'][f'{a_name}_vs_{b_name}'] = {'parallel_deviation': par, 'axis_offset_mm': off}
            if par > TOL_PAR or off > TOL_OFF:
                coax_ok = False
        rec['coaxial_ok'] = coax_ok
        if not coax_ok:
            result['failures'].append(f"{st['id']} coaxiality fail")
        for k in ('_longeron_axis', '_plug_axis'):
            rec.pop(k, None)

        # 短销/垫圈几何实测（对参数块叠层区间）
        plug_bb = bbox(shapes[st['plug']])
        plug_z = (plug_bb[2], plug_bb[5])
        rec['plug_bbox'] = list(plug_bb)
        # T1: 塞截面实测
        rec['plug_section_xy'] = {'x_size': plug_bb[3]-plug_bb[0],
                                  'y_size': plug_bb[4]-plug_bb[1],
                                  'z_size': plug_bb[5]-plug_bb[2]}
        if not (abs(plug_bb[3]-plug_bb[0]-20) < 1e-6 and abs(plug_bb[4]-plug_bb[1]-7.8) < 1e-6
                and abs(plug_bb[5]-plug_bb[2]-7.8) < 1e-6):
            result['failures'].append(f"{st['id']} plug section != 20x7.8x7.8")

        def zint(name): return ST[name]
        expect_parts = {}
        if sz > 0:
            expect_parts[f"e2_stub_out_{st['id']}"] = ('stub', zint('top_out'))
            expect_parts[f"e2_washer_out_{st['id']}"] = ('washer_out', zint('top_out'))
            expect_parts[f"e2_stub_bay_{st['id']}"] = ('stub', zint('top_bay'))
            expect_parts[f"e2_washer_bay_{st['id']}"] = ('washer_bay', zint('top_bay'))
        else:
            expect_parts[f"e2_stub_bay_{st['id']}"] = ('stub', zint('bot_bay'))
            expect_parts[f"e2_washer_bay_{st['id']}"] = ('washer_bay', zint('bot_bay'))
            expect_parts[f"e2_pin_wing_{st['id']}"] = ('wing_pin', zint('bot_wing_pin'))
        prec = {}
        for pn_, (kind, zi) in expect_parts.items():
            s = shapes[pn_]
            bb = bbox(s)
            pm = {'bbox': list(bb)}
            ok = True
            if kind == 'stub':
                shank_z, head_z = zi['shank'], zi['head']
                z_lo, z_hi = min(shank_z + head_z), max(shank_z + head_z)
                ok = (abs(bb[2]-z_lo) < 1e-6 and abs(bb[5]-z_hi) < 1e-6 and
                      abs((bb[3]-bb[0]) - FC['head']['diameter_mm']) < 1e-6 and
                      abs((bb[4]-bb[1]) - FC['head']['diameter_mm']) < 1e-6)
                eng = min(shank_z[1], plug_z[1]) - max(shank_z[0], plug_z[0])
                # 尖端=靠塞心一端；与 M4 螺钉包络 z 区间 [sz*C-2, sz*C+2] 的间距
                env_lo, env_hi = sz*C - 2.0, sz*C + 2.0
                tip_clear = max(shank_z[0] - env_hi, env_lo - shank_z[1], 0.0)
                pm['plug_engagement_mm'] = round(eng, 6)
                pm['tip_to_screw_envelope_clearance_mm'] = round(tip_clear, 6)
                if abs(eng - 1.8) > 1e-6 or abs(tip_clear - 0.1) > 1e-6:
                    ok = False
                env = m4_screw_envelope(st['sx'], st['sy'], st['sz'])
                cv = common_volume(s, env)
                pm['vs_m4_screw_common_mm3'] = cv
                if not (isinstance(cv, float) and cv <= 1e-6):
                    ok = False
            elif kind == 'wing_pin':
                shank_z = zi['shank']
                ok = (abs(bb[2]-min(shank_z)) < 1e-6 and abs(bb[5]-max(shank_z)) < 1e-6 and
                      abs((bb[3]-bb[0]) - FC['shank_diameter_mm']) < 1e-6)
                eng = min(shank_z[1], plug_z[1]) - max(shank_z[0], plug_z[0])
                # 翼根叉垫板顶面 z=-113.15=-(C+6.0)；销底让隙
                pm['plug_engagement_mm'] = round(eng, 6)
                pm['pin_to_wing_pad_clearance_mm'] = round(min(shank_z) + (C + 6.0), 6)
                # 翼销尖端（靠塞心端）同样须让 M4 包络 0.1
                env_lo, env_hi = sz*C - 2.0, sz*C + 2.0
                tip_clear = max(shank_z[0] - env_hi, env_lo - shank_z[1], 0.0)
                pm['tip_to_screw_envelope_clearance_mm'] = round(tip_clear, 6)
                env = m4_screw_envelope(st['sx'], st['sy'], st['sz'])
                cv = common_volume(s, env)
                pm['vs_m4_screw_common_mm3'] = cv
                if (abs(eng - 1.8) > 1e-6 or abs(pm['pin_to_wing_pad_clearance_mm'] - 0.2) > 1e-6
                        or abs(tip_clear - 0.1) > 1e-6
                        or not (isinstance(cv, float) and cv <= 1e-6)):
                    ok = False
            else:  # washer
                wz = zi['washer']
                W = FC['washer_out'] if kind == 'washer_out' else FC['washer_bay']
                ok = (abs(bb[2]-min(wz)) < 1e-6 and abs(bb[5]-max(wz)) < 1e-6 and
                      abs((bb[3]-bb[0]) - W['outer_diameter_mm']) < 1e-6)
                pm['washer_od_mm'] = bb[3]-bb[0]
            pm['ok'] = ok
            prec[pn_] = pm
            if not ok:
                result['failures'].append(f'{pn_} geometry mismatch: {pm}')
        rec['parts'] = prec
        result['stations'].append(rec)

    # T1/T2 静态源核对
    rs_snap = (RUN / 'inputs' / 'root_structure.py').read_text(encoding='utf-8')
    sm_src = (ENG / 'spacecraft_model.py').read_text(encoding='utf-8')
    result['t1_truth'] = {
        'wp02_literal_box_20_9_8_9_8': 'box((20,9.8,9.8))' in rs_snap,
        'wp03_rebuild_box_20_7_8_7_8': 'box((20,7.8,7.8))' in sm_src,
        'measured_plug_section': '7.8x7.8 (见 stations[*].plug_section_xy)',
        'ticket_text_consistent_with_wp03': True}
    result['t2_truth'] = {
        'wp02_longeron_bore_line': 'for x in [-164,164]:rail=bore(rail,4.5,16,(x,0,0))' in rs_snap,
        'wp02_plug_bores_line': "bore(plug,3.3,24,(0,0,0),(1,0,0));plug=bore(plug,4.5,12,(sx*-3,0,0))" in rs_snap,
        'hole_census': result['hole_census']}
    if not (result['t1_truth']['wp02_literal_box_20_9_8_9_8'] and
            result['t1_truth']['wp03_rebuild_box_20_7_8_7_8'] and
            result['t2_truth']['wp02_longeron_bore_line'] and
            result['t2_truth']['wp02_plug_bores_line']):
        result['failures'].append('T1/T2 static source check failed')

    # 跨 run：E2 vs E1 纵梁 STEP（时间戳归一化）
    for ln in ('RB_longeron_1_1', 'RB_longeron_-1_1', 'RB_longeron_1_-1', 'RB_longeron_-1_-1'):
        b_e2 = step_normalize_timestamp((exp / f'{ln}.step').read_bytes())
        b_e1 = step_normalize_timestamp((RUN_E1 / 'exports' / f'{ln}.step').read_bytes())
        same = b_e2 == b_e1
        result['cross_run_longeron'][ln] = {
            'normalized_identical_to_e1_export': same,
            'raw_sha256_e2': sha256_file(exp / f'{ln}.step'),
            'raw_sha256_e1': sha256_file(RUN_E1 / 'exports' / f'{ln}.step')}
        if not same:
            result['failures'].append(f'{ln} differs from E1 export (normalized)')

    # F) 登记表一致性
    evd = RUN / 'evidence'
    dp = json.loads((evd / 'e2_dual_hole_pairs_8.json').read_text(encoding='utf-8'))
    fs = json.loads((evd / 'e2_fastener_stacks_8.json').read_text(encoding='utf-8'))
    ms = json.loads((evd / 'e2_mounting_surfaces.json').read_text(encoding='utf-8'))
    tp = json.loads((evd / 'e2_tool_paths.json').read_text(encoding='utf-8'))
    ra = {'rows': {'dual_hole_pairs': dp['row_count'], 'fastener_stacks': fs['row_count'],
                   'mounting_surfaces': ms['row_count'], 'tool_paths': tp['row_count']},
          'pair_id_set_match': {r['pair_id'] for r in dp['rows']} ==
                               {f"E2P-{st['id']}" for st in sts},
          'unknown_fields_preserved': True, 'axis_match': True,
          'short_engagement_registered': False, 'issues': []}
    stmap = {f"E2P-{st['id']}": st for st in sts}
    for row in dp['rows']:
        stx = stmap.get(row['pair_id'])
        if stx is None:
            ra['issues'].append(f"unknown pair {row['pair_id']}"); continue
        pt = row['hole_axis_S']['point_mm']; dr = row['hole_axis_S']['direction']
        if not (abs(pt[0]-stx['x']) < 1e-9 and abs(pt[1]-stx['y']) < 1e-9 and
                abs(pt[2]-stx['z']) < 1e-9 and abs(dr[2]) == 1):
            ra['axis_match'] = False
            ra['issues'].append(f"{row['pair_id']} axis reg mismatch")
        for f in ('material', 'grade', 'preload', 'locking', 'load'):
            if 'UNKNOWN' not in str(row.get(f, '')):
                ra['unknown_fields_preserved'] = False
                ra['issues'].append(f"{row['pair_id']} field {f} UNKNOWN lost")
        if not row.get('dof_registration'):
            ra['issues'].append(f"{row['pair_id']} dof_registration empty")
        if any('SHORT_ENGAGEMENT_1.8MM_REGISTERED' in str(d) for d in row.get('dof_registration', [])):
            ra['short_engagement_registered'] = True
    for nm, tbl in (('dual_hole_pairs', dp), ('fastener_stacks', fs),
                    ('mounting_surfaces', ms), ('tool_paths', tp)):
        if tbl['row_count'] != 8:
            ra['issues'].append(f'{nm} rows {tbl["row_count"]} != 8')
    if not ra['short_engagement_registered']:
        ra['issues'].append('SHORT_ENGAGEMENT_1.8MM_REGISTERED not found in dof_registration')
    if ra['issues']:
        result['failures'].extend(ra['issues'])
    result['registration_audit'] = ra

    offs = [c['axis_offset_mm'] for s in result['stations'] for c in s['coaxial'].values()
            if isinstance(c, dict)]
    result['max_axis_offset_mm'] = max(offs) if offs else None
    result['verdict'] = 'PASS' if not result['failures'] else 'FAIL'
    result['elapsed_s'] = round(time.time() - t0, 3)
    write_json(ev / 'review_e2_readback.json', result)
    print('verdict', result['verdict'], 'max_off', result['max_axis_offset_mm'])
    print('failures', result['failures'][:10], 'elapsed', result['elapsed_s'])


if __name__ == '__main__':
    main()
