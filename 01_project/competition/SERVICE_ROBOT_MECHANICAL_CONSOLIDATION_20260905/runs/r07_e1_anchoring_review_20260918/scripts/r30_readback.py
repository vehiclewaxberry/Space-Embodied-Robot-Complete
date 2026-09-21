# -*- coding: utf-8 -*-
"""R07-E1 独立复验 r30：exports 全部 57 件 STEP 独立读回。
口径（自定期望，独立编码，不调用候选方 s05/spec 函数）：
  A) 每栓位三线同轴：纵梁贯穿孔轴(Ø3.4) vs 梁/桥端面盲孔轴(Ø3.4) vs 栓杆轴(Ø3 包络)，
     平行偏差与轴线距机器数值（验收 par<=1e-6, off<=1e-3，记录精确值）；
  B) 闭孔完整度：纵梁双壁中面环采样 72 点；端面盲孔柱面丰满度+孔口内 1mm 环采样；
  C) 孔数/孔位：每受影响件 r=1.7 且轴±Y 的柱面集合与参数块期望集合一一对应（多余孔必报）；
  D) 夹层测量：栓/垫圈/套 STEP 实测 bbox 与参数块名义叠层逐层核对；
  E) 登记表一致性：16/16/10/10 行、pair_id 集合、轴/贴合面/防转登记与参数块一致、
     material/grade/preload/locking/thread_engagement/load UNKNOWN 保留；
  F) exports 字节 sha256 对 EXPORT_MANIFEST 逐件钉固（文件对自身清单，非跨导出同一性）。
所有几何 S 系世界坐标，单位 mm。"""
import json, math, time
from pathlib import Path
from rev_common import (REV, RUN, ENG, sha256_file, write_json, bbox, cyl_faces,
                        axis_distance, ring_closure, inside, import_step,
                        load_params, expected_stations, PARAMS_SHA256_EXPECT)

R_HOLE = 1.7
TOL_FACE = 1e-3      # 孔面 (x,z) 匹配容差
TOL_PAR = 1e-6       # 平行偏差验收
TOL_OFF = 1e-3       # 轴线距验收

MEMBERS = ['RB_longeron_1_1', 'RB_longeron_-1_1', 'RB_longeron_1_-1', 'RB_longeron_-1_-1',
           'RB_upper_beam_20', 'RB_upper_beam_160', 'RB_lower_beam_20', 'RB_lower_beam_160',
           'WP01-RB-BRIDGE-R2']


def find_y_hole(shape, x, z):
    """在 shape 中找 r≈1.7、轴≈±Y、轴过 (x,z) 的柱面；返回 (face_rec, all_y_holes)。"""
    cands = []
    allh = []
    for r, loc, drc, face in cyl_faces(shape):
        if abs(r - R_HOLE) > 1e-4 or abs(abs(drc[1]) - 1) > 1e-6:
            continue
        allh.append((loc[0], loc[2]))
        if abs(loc[0] - x) < TOL_FACE and abs(loc[2] - z) < TOL_FACE:
            cands.append((r, loc, drc, face))
    return (cands[0] if cands else None), allh


def main():
    t0 = time.time()
    ev = REV / 'evidence'
    exp = RUN / 'exports'
    P, params_hash = load_params()
    stations = expected_stations(P)
    assert len(stations) == 16

    man = json.loads((exp / 'EXPORT_MANIFEST.json').read_text(encoding='utf-8'))
    man_parts = {p['name']: p for p in man['parts']}

    result = {
        'review': 'R07_E1_INDEPENDENT_REVERIFY', 'script': 'r30_readback.py',
        'reviewed_run': RUN.name, 'units': 'mm', 'frame': 'S',
        'params_sha256': params_hash,
        'params_sha256_pin_ok': params_hash == PARAMS_SHA256_EXPECT,
        'tolerances': {'face_match_mm': TOL_FACE, 'parallel': TOL_PAR, 'axis_offset_mm': TOL_OFF},
        'export_hash_pin': {'checked': 0, 'mismatches': []},
        'stations': [], 'member_face_audit': {}, 'registration_audit': {},
        'measured_volumes_mm3': {}, 'failures': [], 'verdict': None,
    }

    shapes, solids = {}, {}
    for name in MEMBERS:
        shapes[name] = import_step(str(exp / f'{name}.step'))
        solids[name] = shapes[name].solids()[0]
    for st in stations:
        for kind in ('bolt', 'washer', 'sleeve'):
            n = f"e1_anchor_{kind}_{st['group']}_{st['index']}"
            shapes[n] = import_step(str(exp / f'{n}.step'))

    # F) 字节哈希钉固
    for name, prec in man_parts.items():
        f = exp / prec['file']
        ok = sha256_file(f) == prec['sha256']
        result['export_hash_pin']['checked'] += 1
        if not ok:
            result['export_hash_pin']['mismatches'].append(name)
            result['failures'].append(f'export hash mismatch: {name}')
    if result['export_hash_pin']['checked'] != 57:
        result['failures'].append(f"manifest parts {result['export_hash_pin']['checked']} != 57")

    for n, s in shapes.items():
        result['measured_volumes_mm3'][n] = round(sum(so.volume for so in s.solids()), 6)

    # A/B/C) 逐栓位
    for st in stations:
        rec = {'pair_id': st['pair_id'], 'expected': {'x': st['x'], 'z': st['z'],
               'sy': st['sy'], 'sz': st['sz'], 'rail': st['rail'], 'beam': st['beam']}}
        # 纵梁贯穿孔
        fh, _ = find_y_hole(shapes[st['rail']], st['x'], st['z'])
        rec['rail_hole'] = {'face_found': fh is not None}
        if fh is None:
            result['failures'].append(f"{st['pair_id']} rail hole not found in {st['rail']}")
        else:
            r, loc, drc, face = fh
            ro1, ai1 = ring_closure(solids[st['rail']], st['x'], st['z'], st['sy']*112.15, r)
            ro2, ai2 = ring_closure(solids[st['rail']], st['x'], st['z'], st['sy']*102.15, r)
            rec['rail_hole'].update(axis_loc_mm=list(loc), axis_dir=list(drc),
                outer_wall_closed=(not ro1) and (not ai1),
                inner_wall_closed=(not ro2) and (not ai2))
            if not rec['rail_hole']['outer_wall_closed'] or not rec['rail_hole']['inner_wall_closed']:
                result['failures'].append(f"{st['pair_id']} rail wall not closed")
            rec['_rail_axis'] = (loc, drc)
        # 梁/桥端面盲孔
        fb, _ = find_y_hole(shapes[st['beam']], st['x'], st['z'])
        rec['beam_hole'] = {'face_found': fb is not None}
        if fb is None:
            result['failures'].append(f"{st['pair_id']} beam blind hole not found in {st['beam']}")
        else:
            r, loc, drc, face = fb
            fbb = face.bounding_box()
            span = max(fbb.size.Y, 1e-9)
            fullness = face.area / (2*math.pi*r*span)
            ro, ai = ring_closure(solids[st['beam']], st['x'], st['z'], st['sy']*100.15, r)
            rec['beam_hole'].update(axis_loc_mm=list(loc), axis_dir=list(drc),
                modeled_depth_mm=round(span, 6), cyl_fullness=fullness,
                mouth_closed=(not ro) and (not ai))
            if not (fullness > 1 - 1e-3 and not ro and not ai):
                result['failures'].append(f"{st['pair_id']} beam hole not closed")
            if abs(span - 12.0) > 1e-3:
                result['failures'].append(f"{st['pair_id']} beam hole depth {span} != 12")
            rec['_beam_axis'] = (loc, drc)
        # 栓包络轴
        bn = f"e1_anchor_bolt_{st['group']}_{st['index']}"
        bcf = [c for c in cyl_faces(shapes[bn]) if abs(c[0] - 1.5) < 1e-4]
        if not bcf:
            result['failures'].append(f"{st['pair_id']} bolt shank face not found")
            rec['bolt_axis_found'] = False
        else:
            rec['bolt_axis_found'] = True
            rec['_bolt_axis'] = (bcf[0][1], bcf[0][2])
        # 同轴
        coax = {}
        ok = True
        for label, pair in [('longeron_vs_beam', ('_rail_axis', '_beam_axis')),
                            ('longeron_vs_bolt', ('_rail_axis', '_bolt_axis')),
                            ('beam_vs_bolt', ('_beam_axis', '_bolt_axis'))]:
            a, b = rec.get(pair[0]), rec.get(pair[1])
            if a is None or b is None:
                coax[label] = 'MISSING_AXIS'; ok = False; continue
            par, off = axis_distance(a[0], a[1], b[0], b[1])
            coax[label] = {'parallel_deviation': par, 'axis_offset_mm': off}
            if par > TOL_PAR or off > TOL_OFF:
                ok = False
        rec['coaxial'] = coax
        rec['coaxial_ok'] = ok
        if not ok:
            result['failures'].append(f"{st['pair_id']} coaxiality fail")
        # D) 夹层实测
        layers = {}
        bb_bolt = bbox(shapes[bn])
        layers['bolt_bbox'] = list(bb_bolt)
        wn = f"e1_anchor_washer_{st['group']}_{st['index']}"
        sn = f"e1_anchor_sleeve_{st['group']}_{st['index']}"
        bb_w, bb_s = bbox(shapes[wn]), bbox(shapes[sn])
        sy = st['sy']
        exp_layer = {
            'washer_y': (min(sy*113.15, sy*113.65), max(sy*113.15, sy*113.65)),
            'sleeve_y': (min(sy*103.15, sy*111.15), max(sy*103.15, sy*111.15)),
            'head_y': (min(sy*113.65, sy*116.65), max(sy*113.65, sy*116.65)),
            'tip_y': sy*93.15,
        }
        def close(a, b, t=1e-6): return abs(a - b) <= t
        layer_ok = (
            close(bb_w[1], exp_layer['washer_y'][0]) and close(bb_w[4], exp_layer['washer_y'][1]) and
            close(bb_w[3]-bb_w[0], 6) and close(bb_w[5]-bb_w[2], 6) and
            close(bb_s[1], exp_layer['sleeve_y'][0]) and close(bb_s[4], exp_layer['sleeve_y'][1]) and
            close(bb_s[3]-bb_s[0], 4) and close(bb_s[5]-bb_s[2], 4) and
            close((bb_bolt[0]+bb_bolt[3])/2, st['x']) and close((bb_bolt[2]+bb_bolt[5])/2, st['z']) and
            close((bb_w[0]+bb_w[3])/2, st['x']) and close((bb_w[2]+bb_w[5])/2, st['z']) and
            close((bb_s[0]+bb_s[3])/2, st['x']) and close((bb_s[2]+bb_s[5])/2, st['z']))
        layers['washer_bbox'] = list(bb_w)
        layers['sleeve_bbox'] = list(bb_s)
        layers['nominal_stack_match'] = layer_ok
        # 栓头端 y（sy 外侧）与全长
        head_out = bb_bolt[4] if sy > 0 else bb_bolt[1]
        layers['head_outer_y'] = head_out
        layers['head_outer_ok'] = close(head_out, sy*116.65)
        layers['bolt_y_span_ok'] = close(bb_bolt[4]-bb_bolt[1], 23.5)
        rec['layers'] = layers
        if not (layer_ok and layers['head_outer_ok'] and layers['bolt_y_span_ok']):
            result['failures'].append(f"{st['pair_id']} stack layer mismatch")
        for k in ('_rail_axis', '_beam_axis', '_bolt_axis'):
            rec.pop(k, None)
        result['stations'].append(rec)

    # C) 每受影响件孔面集合审计（期望集合之外必报；梁/桥盲孔按端面区分，同 (x,z) 两端各计一面）
    for m in MEMBERS:
        is_rail = m.startswith('RB_longeron_')
        if is_rail:
            exp_set = sorted({(st['x'], st['z']) for st in stations if st['rail'] == m})
        else:
            exp_set = sorted({(st['x'], st['z'], st['sy']) for st in stations if st['beam'] == m})
        got = []
        for r, loc, drc, face in cyl_faces(shapes[m]):
            if abs(r - R_HOLE) <= 1e-4 and abs(abs(drc[1]) - 1) <= 1e-6:
                if is_rail:
                    got.append((round(loc[0], 6), round(loc[2], 6)))
                else:
                    fb = face.bounding_box()
                    end_sy = 1 if (fb.min.Y + fb.max.Y) / 2 > 0 else -1
                    got.append((round(loc[0], 6), round(loc[2], 6), end_sy))
        exp_r = sorted({tuple(round(v, 6) for v in e) for e in exp_set})
        got_s = sorted(set(got))
        missing = [e for e in exp_r if e not in got_s]
        extra = [g for g in got_s if g not in set(exp_r)]
        result['member_face_audit'][m] = {'expected': exp_r, 'found': got_s,
                                          'missing': missing, 'extra': extra}
        if missing or extra:
            result['failures'].append(f'{m} hole set mismatch missing={missing} extra={extra}')

    # E) 登记表一致性
    evd = RUN / 'evidence'
    dp = json.loads((evd / 'e1_dual_hole_pairs_16.json').read_text(encoding='utf-8'))
    st16 = json.loads((evd / 'e1_fastener_stacks_16.json').read_text(encoding='utf-8'))
    ms = json.loads((evd / 'e1_mounting_surfaces.json').read_text(encoding='utf-8'))
    tp = json.loads((evd / 'e1_tool_paths.json').read_text(encoding='utf-8'))
    exp_ids = {st['pair_id'] for st in stations}
    ra = {'dual_hole_pairs_rows': dp['row_count'], 'fastener_stacks_rows': st16['row_count'],
          'mounting_surfaces_rows': ms['row_count'], 'tool_paths_rows': tp['row_count'],
          'pair_id_set_match': {r['pair_id'] for r in dp['rows']} == exp_ids,
          'unknown_fields_preserved': True, 'axis_match': True, 'anti_rotation_match': True,
          'x160_registered_secondary': True, 'issues': []}
    stmap = {st['pair_id']: st for st in stations}
    for row in dp['rows']:
        stx = stmap.get(row['pair_id'])
        if stx is None:
            continue
        pt = row['hole_axis_S']['point_mm']; dr = row['hole_axis_S']['direction']
        if not (abs(pt[0]-stx['x']) < 1e-9 and abs(pt[2]-stx['z']) < 1e-9 and
                abs(pt[1]-stx['sy']*107.15) < 1e-9 and abs(dr[1]) == 1):
            ra['axis_match'] = False
            ra['issues'].append(f"{row['pair_id']} axis reg mismatch")
        for f in ('material', 'grade', 'preload', 'locking', 'thread_engagement', 'load'):
            if 'UNKNOWN' not in str(row.get(f, '')):
                ra['unknown_fields_preserved'] = False
                ra['issues'].append(f"{row['pair_id']} field {f} UNKNOWN lost")
        if not row.get('dof_registration'):
            ra['issues'].append(f"{row['pair_id']} dof_registration empty")
        ga = row.get('anti_rotation', '')
        if ga != stx['anti_rotation']:
            ra['anti_rotation_match'] = False
            ra['issues'].append(f"{row['pair_id']} anti_rotation mismatch")
        if stx['group'] in ('G03', 'G04', 'G07', 'G08') and 'REGISTERED_SECONDARY' not in ga:
            ra['x160_registered_secondary'] = False
            ra['issues'].append(f"{row['pair_id']} x160 secondary not registered")
    for tbl, rows_n, name in ((dp, 16, 'dual_hole_pairs'), (st16, 16, 'fastener_stacks'),
                              (ms, 10, 'mounting_surfaces'), (tp, 10, 'tool_paths')):
        if tbl['row_count'] != rows_n:
            ra['issues'].append(f'{name} rows {tbl["row_count"]} != {rows_n}')
    for row in tp['rows']:
        if not row.get('named_check_set'):
            ra['issues'].append(f"tool path {row.get('group')} named_check_set empty")
    if ra['issues']:
        result['failures'].extend(ra['issues'])
    result['registration_audit'] = ra

    offs = [c['axis_offset_mm'] for s in result['stations'] for c in s['coaxial'].values()
            if isinstance(c, dict)]
    result['max_axis_offset_mm'] = max(offs) if offs else None
    result['verdict'] = 'PASS' if not result['failures'] else 'FAIL'
    result['elapsed_s'] = round(time.time() - t0, 3)
    write_json(ev / 'review_readback.json', result)
    print('verdict', result['verdict'], 'max_off', result['max_axis_offset_mm'],
          'failures', result['failures'][:8], 'elapsed', result['elapsed_s'])


if __name__ == '__main__':
    main()
