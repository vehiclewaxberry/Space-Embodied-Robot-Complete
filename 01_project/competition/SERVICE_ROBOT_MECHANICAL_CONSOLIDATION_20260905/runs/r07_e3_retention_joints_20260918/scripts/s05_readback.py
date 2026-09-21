# -*- coding: utf-8 -*-
"""R07-E3 STEP 读回机器验证（build123d.import_step 自读回）：
A) 边1（Y 轴）：上纵梁 Ø3.4 双壁贯穿孔（壁中面 y=±112.15/±102.15 环采样闭合）
   vs 横梁端面盲孔（Ø3.4 深 7：孔内两平面闭合 + 孔底 0.5 外轴心回实体）
   vs 栓杆轴 三者同轴（|d1×d2| 与轴线距机器数值）；
B) 边2（Z 轴）：横梁/耳座 Ø4.5 竖孔（中面环采样）vs 足叉盲孔（啮合带闭合 + 打通至槽底：
   孔内轴心空、槽内轴心空）vs 栓杆轴 同轴；
C) 孔数核对：上纵梁 Y 向 Ø3.4 孔数 = E2 run 同名 STEP 基线 +4；横梁 Y 盲孔 4/Z 孔 4（含 2 既有备用）；
   耳座 Z 孔 3（含 1 既有备用）；足叉 Z 盲孔 2（枢轴 Ø8.4 X 向 1 既有不重复计）。
所有几何 S 系世界坐标，单位 mm。"""
import sys, json, math, hashlib, time
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401
from build123d import import_step
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_IN

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_e3_retention_joints_20260918'
E2RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_e2_endplug_retention_20260918'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, str(ENG))
import spacecraft_model as sm

E3 = sm.P['retention_joints_r07_e3']
E1P = E3['edge1_clamp']; E2P = E3['edge2_foot']
R1 = E1P['hole_diameter_mm'] / 2      # 1.7
R2 = E2P['hole_diameter_mm'] / 2      # 2.25
R_SHANK1 = E1P['fastener_candidate']['shank_diameter_mm'] / 2   # 1.5
R_SHANK2 = E2P['fastener_candidate']['shank_diameter_mm'] / 2   # 2.0

def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))

def sidecar(p):
    h = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    rel = Path(p).resolve().relative_to(RUN).as_posix()
    wlf(str(p) + '.sha256', h + '  ' + rel + '\n')
    return h

def cyl_faces(shape):
    out = []
    for f in shape.faces():
        ad = BRepAdaptor_Surface(f.wrapped)
        if ad.GetType() == GeomAbs_Cylinder:
            c = ad.Cylinder(); a = c.Axis(); l = a.Location(); d = a.Direction()
            out.append((c.Radius(), (l.X(), l.Y(), l.Z()), (d.X(), d.Y(), d.Z()), f))
    return out

def inside(solid, x, y, z):
    cls = BRepClass3d_SolidClassifier(solid.wrapped, gp_Pnt(x, y, z), 1e-9)
    return cls.State() == TopAbs_IN

def axis_distance(l1, d1, l2, d2):
    cross = (d1[1]*d2[2]-d1[2]*d2[1], d1[2]*d2[0]-d1[0]*d2[2], d1[0]*d2[1]-d1[1]*d2[0])
    par = math.sqrt(sum(c*c for c in cross))
    v = (l2[0]-l1[0], l2[1]-l1[1], l2[2]-l1[2])
    cx = (v[1]*d1[2]-v[2]*d1[1], v[2]*d1[0]-v[0]*d1[2], v[0]*d1[1]-v[1]*d1[0])
    return par, math.sqrt(sum(c*c for c in cx))

def ring_closure(solid, plane, c1, c2, fixed, r, n=72, dr=0.05):
    """plane='y': XZ 平面环（Y 轴孔），fixed=y；plane='z': XY 平面环（Z 轴孔），fixed=z。"""
    outs = []
    for i in range(n):
        a = 2*math.pi*i/n
        p1, p2 = c1 + (r+dr)*math.cos(a), c2 + (r+dr)*math.sin(a)
        x, y, z = (p1, fixed, p2) if plane == 'y' else (p1, p2, fixed)
        if not inside(solid, x, y, z):
            outs.append(round(a, 4))
    ax = (c1, fixed, c2) if plane == 'y' else (c1, c2, fixed)
    return outs, inside(solid, *ax)

def find_axis_hole(shape, r_target, axis_sel, tol=1e-6):
    """axis_sel: 对轴线上点的坐标断言 dict，如 {'x':..,'z':..}（Y 轴孔）或 {'x':..,'y':..}（Z 轴孔）。"""
    out = []
    for rr, loc, drc, f in cyl_faces(shape):
        if abs(rr - r_target) > tol:
            continue
        if 'yaxis' in axis_sel and abs(abs(drc[1]) - 1) > 1e-6:
            continue
        if 'zaxis' in axis_sel and abs(abs(drc[2]) - 1) > 1e-6:
            continue
        ok = True
        for k, v in axis_sel.items():
            if k in ('yaxis', 'zaxis'):
                continue
            idx = {'x': 0, 'y': 1, 'z': 2}[k]
            if abs(loc[idx] - v) > tol:
                ok = False; break
        if ok:
            out.append((rr, loc, drc, f))
    return out

def main():
    t0 = time.time()
    ev = RUN / 'evidence'; exp = RUN / 'exports'
    spec1 = sm.retention_clamp_spec(sm.P)
    spec2 = sm.retention_foot_spec(sm.P)
    result = {'run': 'r07_e3_retention_joints_20260918',
              'check': 'step_readback_paired_holes_and_coaxiality',
              'readback_tool': 'build123d.import_step', 'units': 'mm', 'frame': 'S',
              'members': {}, 'coaxial_pairs': [], 'hole_counts': {}, 'failures': [], 'verdict': None}
    rails = {n: import_step(str(exp / f'{n}.step')) for n in ['RB_longeron_1_1', 'RB_longeron_-1_1']}
    beams = {n: import_step(str(exp / f'hold_crossbeam_{k}.step')) for k, n in [(0, 'hold_crossbeam_0'), (1, 'hold_crossbeam_1')]}
    lugs = {n: import_step(str(exp / f'{n}.step')) for n in ['hold_roof_lug_0_-94.15', 'hold_roof_lug_1_-94.15']}
    feet = {n: import_step(str(exp / f'hold_pivot_clevis_{k}.step')) for k, n in [(0, 'hold_pivot_clevis_0'), (1, 'hold_pivot_clevis_1')]}

    # ---------- 边1：纵梁孔 + 横梁盲孔 ----------
    for r in spec1:
        pid = f"E3P-{r['group']}-{r['index']}"
        sy = r['sy']; x = r['x']; z = r['z']
        rail_name, beam_name = r['mate'], r['beam']
        rsolid = rails[rail_name].solids()[0]; bsolid = beams[beam_name].solids()[0]
        mrec = result['members'].setdefault(rail_name, {'holes': []})
        brec = result['members'].setdefault(beam_name, {'holes': []})
        # 纵梁贯穿孔：双壁中面环闭合
        cand = find_axis_hole(rails[rail_name], R1, {'yaxis': 1, 'x': x, 'z': z})
        hrec = {'kind': 'e3_longeron_yaxis_through_hole', 'pair_id': pid, 'expected_mm': [x, sy*101.15, z], 'face_found': len(cand) > 0}
        if not cand:
            result['failures'].append(f'{pid} {rail_name} y-hole x={x} not found'); r['_rail_axis'] = None
        else:
            rr, loc, drc, _ = cand[0]
            ro1, ai1 = ring_closure(rsolid, 'y', x, z, sy*112.15, rr)
            ro2, ai2 = ring_closure(rsolid, 'y', x, z, sy*102.15, rr)
            hrec.update(axis_loc_mm=list(loc), axis_dir=list(drc),
                        outer_wall_closed=(not ro1) and (not ai1), inner_wall_closed=(not ro2) and (not ai2))
            if not (hrec['outer_wall_closed'] and hrec['inner_wall_closed']):
                result['failures'].append(f'{pid} {rail_name} wall closure fail')
            r['_rail_axis'] = (loc, drc)
        mrec['holes'].append(hrec)
        # 横梁端面盲孔：孔内两平面闭合 + 孔底完整（轴心：孔内空、孔底外 0.5 回实体）
        cand = find_axis_hole(beams[beam_name], R1, {'yaxis': 1, 'x': x, 'z': z})
        hrec = {'kind': 'e3_crossbeam_end_blind_hole', 'pair_id': pid, 'expected_mm': [x, sy*101.15, z], 'face_found': len(cand) > 0}
        if not cand:
            result['failures'].append(f'{pid} {beam_name} blind hole x={x} not found'); r['_beam_axis'] = None
        else:
            rr, loc, drc, _ = cand[0]
            ro1, ai1 = ring_closure(bsolid, 'y', x, z, sy*100.65, rr)   # 孔口内 0.5
            ro2, ai2 = ring_closure(bsolid, 'y', x, z, sy*95.15, rr)    # 近孔底（孔底 94.15）
            axis_in_void = not inside(bsolid, x, sy*94.65, z)           # 孔底前 0.5 轴心仍为空
            bottom_intact = inside(bsolid, x, sy*93.65, z)              # 孔底外 0.5 轴心回实体
            hrec.update(axis_loc_mm=list(loc), axis_dir=list(drc),
                        closed_near_mouth=(not ro1) and (not ai1), closed_near_bottom=(not ro2) and (not ai2),
                        axis_void_before_bottom=axis_in_void, bottom_intact=bottom_intact,
                        blind_depth_mm=7, nominal_engagement_mm=5)
            if not (hrec['closed_near_mouth'] and hrec['closed_near_bottom'] and axis_in_void and bottom_intact):
                result['failures'].append(f'{pid} {beam_name} blind hole closure/bottom fail')
            r['_beam_axis'] = (loc, drc)
        brec['holes'].append(hrec)

    # ---------- 边2：横梁/耳座竖孔 + 足叉盲孔 ----------
    for r in spec2:
        pid = f"E3P-{r['group']}-{r['index']}"
        x = r['x']; y = r['y']
        beam_name, lug_name, foot_name = r['beam'], r['lug'], r['foot']
        bsolid = beams[beam_name].solids()[0]; lsolid = lugs[lug_name].solids()[0]; fsolid = feet[foot_name].solids()[0]
        # 横梁竖孔（中面 z=101.15 环闭合）
        for tag, shp, solid, zmid in [('crossbeam', beams[beam_name], bsolid, 101.15), ('roof_lug', lugs[lug_name], lsolid, 112.15)]:
            mrec = result['members'].setdefault(tag == 'crossbeam' and beam_name or lug_name, {'holes': []})
            cand = find_axis_hole(shp, R2, {'zaxis': 1, 'x': x, 'y': y})
            hrec = {'kind': f'e3_{tag}_zaxis_hole', 'pair_id': pid, 'expected_mm': [x, y, zmid], 'face_found': len(cand) > 0}
            if not cand:
                result['failures'].append(f'{pid} {tag} z-hole x={x} not found'); r[f'_{tag}_axis'] = None
            else:
                rr, loc, drc, _ = cand[0]
                ro, ai = ring_closure(solid, 'z', x, y, zmid, rr)
                hrec.update(axis_loc_mm=list(loc), axis_dir=list(drc), midplane_closed=(not ro) and (not ai))
                if not hrec['midplane_closed']:
                    result['failures'].append(f'{pid} {tag} closure fail')
                r[f'_{tag}_axis'] = (loc, drc)
            mrec['holes'].append(hrec)
        # 足叉盲孔：啮合带闭合（z=120.65）+ 打通至槽底（孔内轴心空 + 槽内轴心空）
        mrec = result['members'].setdefault(foot_name, {'holes': []})
        cand = find_axis_hole(feet[foot_name], R2, {'zaxis': 1, 'x': x, 'y': y})
        hrec = {'kind': 'e3_clevis_foot_blind_hole', 'pair_id': pid, 'expected_mm': [x, y, 118.15], 'face_found': len(cand) > 0}
        if not cand:
            result['failures'].append(f'{pid} {foot_name} foot hole x={x} not found'); r['_foot_axis'] = None
        else:
            rr, loc, drc, _ = cand[0]
            ro, ai = ring_closure(fsolid, 'z', x, y, 120.65, rr)   # 啮合带中面（脚座实体带 z[118.15,125.15]）
            void_in_hole = not inside(fsolid, x, y, 124.65)       # 孔内近槽底 0.5 轴心仍为空
            open_to_slot = not inside(fsolid, x, y, 125.65)       # 打通至槽：槽内轴心为空
            pivot_clear = inside(fsolid, x, y + 4.0, 121.65) is not None  # 占位（枢轴孔 Ø8.4@z=135.15 远离，无需避让带）
            hrec.update(axis_loc_mm=list(loc), axis_dir=list(drc),
                        engagement_midplane_closed=(not ro) and (not ai),
                        axis_void_near_slot_floor=void_in_hole, opened_to_slot=open_to_slot,
                        modeled_depth_mm=7, nominal_engagement_mm=5, tip_to_slot_floor_mm=2)
            if not (hrec['engagement_midplane_closed'] and void_in_hole and open_to_slot):
                result['failures'].append(f'{pid} {foot_name} foot hole closure/slot-opening fail')
            r['_foot_axis'] = (loc, drc)
        mrec['holes'].append(hrec)

    # ---------- 同轴数值 ----------
    for r in spec1:
        pid = f"E3P-{r['group']}-{r['index']}"
        bolt = import_step(str(exp / f"e3_clamp_bolt_{r['group']}_{r['index']}.step"))
        cf = [c for c in cyl_faces(bolt) if abs(c[0] - R_SHANK1) < 1e-6]
        baxis = (cf[0][1], cf[0][2]) if cf else None
        pair = {'pair_id': pid, 'edge': 'edge1_clamp'}; ok = True
        for label, a, b in [('longeron_vs_crossbeam', r.get('_rail_axis'), r.get('_beam_axis')),
                            ('longeron_vs_bolt', r.get('_rail_axis'), baxis),
                            ('crossbeam_vs_bolt', r.get('_beam_axis'), baxis)]:
            if a is None or b is None:
                pair[label] = 'MISSING_AXIS'; ok = False; continue
            par, off = axis_distance(a[0], a[1], b[0], b[1])
            pair[label] = {'parallel_deviation': par, 'axis_offset_mm': off}
            if par > 1e-6 or off > 1e-6:
                ok = False
        pair['coaxial'] = ok
        if not ok:
            result['failures'].append(f'{pid} coaxiality fail')
        result['coaxial_pairs'].append(pair)
    for r in spec2:
        pid = f"E3P-{r['group']}-{r['index']}"
        bolt = import_step(str(exp / f"e3_foot_bolt_{r['group']}_{r['index']}.step"))
        cf = [c for c in cyl_faces(bolt) if abs(c[0] - R_SHANK2) < 1e-6]
        baxis = (cf[0][1], cf[0][2]) if cf else None
        pair = {'pair_id': pid, 'edge': 'edge2_foot'}; ok = True
        ax = {'crossbeam': r.get('_crossbeam_axis'), 'roof_lug': r.get('_roof_lug_axis'), 'foot': r.get('_foot_axis'), 'bolt': baxis}
        for i, (la, a) in enumerate(ax.items()):
            for lb, b in list(ax.items())[i+1:]:
                label = f'{la}_vs_{lb}'
                if a is None or b is None:
                    pair[label] = 'MISSING_AXIS'; ok = False; continue
                par, off = axis_distance(a[0], a[1], b[0], b[1])
                pair[label] = {'parallel_deviation': par, 'axis_offset_mm': off}
                if par > 1e-6 or off > 1e-6:
                    ok = False
        pair['coaxial'] = ok
        if not ok:
            result['failures'].append(f'{pid} coaxiality fail')
        result['coaxial_pairs'].append(pair)

    # ---------- C: 孔数核对 ----------
    counts = {}
    for n in ['RB_longeron_1_1', 'RB_longeron_-1_1']:
        now = len([c for c in cyl_faces(rails[n]) if abs(c[0] - R1) < 1e-6 and abs(abs(c[2][1]) - 1) < 1e-6])
        base = len([c for c in cyl_faces(import_step(str(E2RUN / 'exports' / f'{n}.step'))) if abs(c[0] - R1) < 1e-6 and abs(abs(c[2][1]) - 1) < 1e-6])
        counts[n] = {'yaxis_d3p4_now': now, 'yaxis_d3p4_e2_baseline': base, 'delta': now - base, 'expected_delta': 4}
        if now - base != 4:
            result['failures'].append(f'{n} y-hole count delta {now-base} != 4')
    for k in [0, 1]:
        bn = f'hold_crossbeam_{k}'
        counts[bn] = {'yaxis_d3p4_blind': len([c for c in cyl_faces(beams[bn]) if abs(c[0] - R1) < 1e-6 and abs(abs(c[2][1]) - 1) < 1e-6]),
                      'zaxis_d4p5_total': len([c for c in cyl_faces(beams[bn]) if abs(c[0] - R2) < 1e-6 and abs(abs(c[2][2]) - 1) < 1e-6]),
                      'expected': 'Y 盲孔 4（本 run）+ Z 孔 4（2 新 + 2 既有备用）'}
        if counts[bn]['yaxis_d3p4_blind'] != 4 or counts[bn]['zaxis_d4p5_total'] != 4:
            result['failures'].append(f'{bn} hole counts fail: {counts[bn]}')
        ln = f'hold_roof_lug_{k}_-94.15'
        counts[ln] = {'zaxis_d4p5_total': len([c for c in cyl_faces(lugs[ln]) if abs(c[0] - R2) < 1e-6 and abs(abs(c[2][2]) - 1) < 1e-6]),
                      'expected': 'Z 孔 3（2 新 + 1 既有备用）'}
        if counts[ln]['zaxis_d4p5_total'] != 3:
            result['failures'].append(f'{ln} hole counts fail: {counts[ln]}')
        fn = f'hold_pivot_clevis_{k}'
        counts[fn] = {'zaxis_d4p5_blind': len([c for c in cyl_faces(feet[fn]) if abs(c[0] - R2) < 1e-6 and abs(abs(c[2][2]) - 1) < 1e-6]),
                      'expected': 'Z 盲孔 2（本 run；枢轴 Ø8.4 X 向既有不重复计）'}
        if counts[fn]['zaxis_d4p5_blind'] != 2:
            result['failures'].append(f'{fn} hole counts fail: {counts[fn]}')
    result['hole_counts'] = counts

    result['verdict'] = 'PASS' if not result['failures'] else 'FAIL'
    result['elapsed_s'] = round(time.time() - t0, 3)
    f1 = ev / 'acc_readback_holes_coaxial.json'
    wlf(f1, json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    sidecar(f1)
    offs, pars = [], []
    for p in result['coaxial_pairs']:
        for k, v in p.items():
            if isinstance(v, dict) and 'axis_offset_mm' in v:
                offs.append(v['axis_offset_mm']); pars.append(v['parallel_deviation'])
    print('verdict', result['verdict'], 'failures', result['failures'][:8])
    print('counts', json.dumps(counts, ensure_ascii=False))
    print('coaxial max offset', max(offs) if offs else None, 'max par', max(pars) if pars else None)

if __name__ == '__main__':
    main()
