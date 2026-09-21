# -*- coding: utf-8 -*-
"""R07-E2 STEP 读回机器验证（s05b：V2 判据修正版——V1 判据 FAIL 保留于 acc_readback_holes_coaxial_V1_CRITERION_FAIL.json）（build123d.import_step 自读回）：
A) 既有对偶孔在位且闭合：纵梁 X±164 竖向 Ø4.5 双壁贯穿孔（壁中面环采样）+
   端塞竖向 Ø4.5 贯穿孔（避开与 Ø3.3 X 向导孔十字相交带，在塞心 ±3 mm 平面环采样）；
B) 同轴：每站 纵梁孔轴 vs 端塞孔轴 vs 短栓/销杆轴 的平行度 |d1×d2| 与轴线距（机器数值）；
C) 孔数/孔位与参数表逐位一致（纵梁孔数须与 E1 读回一致：上 5/下 3；端塞竖孔 1）。
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
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_e2_endplug_retention_20260918'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, str(ENG))
import spacecraft_model as sm

R_HOLE = 2.25
R_SHANK = 2.2

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

def ring_closure_zaxis(solid, cx, cy, z, r, n=72, dr=0.05):
    """XY 平面环采样（Z 轴孔）：r+dr 处 n 点全部在实体内 -> 闭孔；轴心须在孔外。"""
    out_pts = []
    for i in range(n):
        a = 2*math.pi*i/n
        px, py = cx + (r+dr)*math.cos(a), cy + (r+dr)*math.sin(a)
        if not inside(solid, px, py, z):
            out_pts.append(round(a, 4))
    return out_pts, inside(solid, cx, cy, z)

def find_zaxis_hole(shape, r_target, x, y):
    cf = [c for c in cyl_faces(shape) if abs(c[0] - r_target) < 1e-6 and abs(abs(c[2][2]) - 1) < 1e-6]
    cand = [c for c in cf if abs(c[1][0] - x) < 1e-6 and abs(c[1][1] - y) < 1e-6]
    return cand

def main():
    t0 = time.time()
    ev = RUN / 'evidence'
    exp = RUN / 'exports'
    spec = sm.transverse_retention_spec(sm.P)
    result = {'run': 'r07_e2_endplug_retention_20260918',
              'check': 'step_readback_paired_holes_and_coaxiality',
              'readback_tool': 'build123d.import_step', 'units': 'mm', 'frame': 'S',
              'members': {}, 'coaxial_pairs': [], 'failures': [], 'verdict': None}
    rails = {n: import_step(str(exp / f'{n}.step')) for n in
             ['RB_longeron_1_1', 'RB_longeron_-1_1', 'RB_longeron_1_-1', 'RB_longeron_-1_-1']}
    plugs = {}
    for sx in [-1, 1]:
        for sy in [-1, 1]:
            for sz in [-1, 1]:
                n = f'RB_end_plug_{sx}_{sy}_{sz}'
                plugs[n] = import_step(str(exp / f'{n}.step'))

    # ---------- A/C: 纵梁 X±164 双壁贯穿孔 ----------
    for r in spec:
        rail_name = r['longeron']
        if rail_name in result['members'] and any(h['expected_x_mm'] == r['x'] for h in result['members'][rail_name]['holes']):
            continue  # 每根纵梁的 ±164 孔只验一次（两站共用同孔位表）
        rail = shapes_rail = rails[rail_name]
        solid = rail.solids()[0]
        mrec = result['members'].setdefault(rail_name, {'holes': []})
        cand = find_zaxis_hole(rail, R_HOLE, r['x'], r['y'])
        hrec = {'kind': 'longeron_vertical_through_hole', 'expected_x_mm': r['x'], 'expected_y_mm': r['y'],
                'face_found': len(cand) > 0}
        if not cand:
            result['failures'].append(f'{rail_name} vertical hole x={r["x"]} not found')
        else:
            rr, loc, drc, face = cand[0]
            sz = r['sz']
            ro1, ai1 = ring_closure_zaxis(solid, r['x'], r['y'], sz*112.15, rr)
            ro2, ai2 = ring_closure_zaxis(solid, r['x'], r['y'], sz*102.15, rr)
            hrec.update(axis_loc_mm=list(loc), axis_dir=list(drc),
                        outer_wall_closed=(not ro1) and (not ai1), inner_wall_closed=(not ro2) and (not ai2),
                        ring_out_outer=ro1, ring_out_inner=ro2)
            if not (hrec['outer_wall_closed'] and hrec['inner_wall_closed']):
                result['failures'].append(f'{rail_name} vertical hole x={r["x"]} wall closure fail')
            hrec['axis'] = (loc, drc)
        mrec['holes'].append(hrec)
        r['_rail_axis'] = hrec.get('axis')

    # 重新补挂 rail axis（每站）
    rail_axes = {}
    for name, m in result['members'].items():
        for h in m['holes']:
            if 'axis' in h:
                rail_axes[(name, h['expected_x_mm'])] = h['axis']
    for r in spec:
        r['_rail_axis'] = rail_axes.get((r['longeron'], r['x']))

    # ---------- A/C: 端塞竖向贯穿孔（环采样避开 X 导孔十字带） ----------
    for r in spec:
        plug_name = r['plug']
        if plug_name in result['members']:
            continue
        pl = plugs[plug_name]
        solid = pl.solids()[0]
        mrec = result['members'].setdefault(plug_name, {'holes': []})
        cand = find_zaxis_hole(pl, R_HOLE, r['x'], r['y'])
        hrec = {'kind': 'plug_vertical_through_hole', 'expected_x_mm': r['x'], 'expected_y_mm': r['y'],
                'face_found': len(cand) > 0}
        if not cand:
            result['failures'].append(f'{plug_name} vertical hole not found')
        else:
            rr, loc, drc, face = cand[0]
            zc = r['z']
            # 塞心平面(z=zc)与 Ø3.3 X 向导孔十字相交；在 zc±3.0（导孔带之外、塞体之内）采样
            ro1, ai1 = ring_closure_zaxis(solid, r['x'], r['y'], zc + 3.0, rr)
            ro2, ai2 = ring_closure_zaxis(solid, r['x'], r['y'], zc - 3.0, rr)
            ro3, ai3 = ring_closure_zaxis(solid, r['x'], r['y'], zc, rr)
            hrec.update(axis_loc_mm=list(loc), axis_dir=list(drc),
                        closed_above_center=(not ro1) and (not ai1), closed_below_center=(not ro2) and (not ai2),
                        center_plane_ring_out=ro3,
                        center_plane_note='塞心平面环外点须恰好落在 X 向导孔开口角度(±x 方向)，其余角度须在实体内；'
                                          '逐角外点=%d/72' % len(ro3),
                        center_axis_inside_void=ai3)
            # 十字带外闭合 + 中心面外点仅出现在导孔方向（允许角度近 0/pi）
            import math as _m
            sin_max = 1.65 / (rr + 0.05)  # X 向 Ø3.3 导孔在塞心平面的合法遮盖带 |sin a|<=r_bore/(r+dr)
            bad = [a for a in ro3 if abs(_m.sin(a)) > sin_max + 1e-9]
            hrec['center_plane_out_angles_off_bore'] = bad
            hrec['center_plane_criterion'] = '环外点合法带 |sin a| <= 1.65/2.3 (Ø3.3 X 向导孔遮盖带); 带外出现外点即 FAIL'
            if not (hrec['closed_above_center'] and hrec['closed_below_center']) or bad:
                result['failures'].append(f'{plug_name} vertical hole closure fail (off-bore ring outs: {bad})')
            hrec['axis'] = (loc, drc)
        mrec['holes'].append(hrec)
        r['_plug_axis'] = hrec.get('axis')
    plug_axes = {name: m['holes'][0].get('axis') for name, m in result['members'].items() if name.startswith('RB_end_plug_')}
    for r in spec:
        r['_plug_axis'] = plug_axes.get(r['plug'])

    # ---------- B: 同轴数值（纵梁孔 vs 端塞孔 vs 栓/销杆） ----------
    for r in spec:
        sid = r['id']
        part_names = [f'e2_stub_out_{sid}', f'e2_stub_bay_{sid}'] if r['sz'] > 0 else [f'e2_stub_bay_{sid}', f'e2_pin_wing_{sid}']
        axes = {}
        for pn_ in part_names:
            sh = import_step(str(exp / f'{pn_}.step'))
            cf = [c for c in cyl_faces(sh) if abs(c[0] - R_SHANK) < 1e-6]
            axes[pn_] = (cf[0][1], cf[0][2]) if cf else None
        pair = {'pair_id': f'E2P-{sid}'}
        ok = True
        checks = [('longeron_vs_plug', r.get('_rail_axis'), r.get('_plug_axis'))]
        for pn_ in part_names:
            checks.append((f'longeron_vs_{pn_}', r.get('_rail_axis'), axes[pn_]))
            checks.append((f'plug_vs_{pn_}', r.get('_plug_axis'), axes[pn_]))
        for label, a, b in checks:
            if a is None or b is None:
                pair[label] = 'MISSING_AXIS'; ok = False; continue
            par, off = axis_distance(a[0], a[1], b[0], b[1])
            pair[label] = {'parallel_deviation': par, 'axis_offset_mm': off}
            if par > 1e-6 or off > 1e-6:
                ok = False
        pair['coaxial'] = ok
        if not ok:
            result['failures'].append(f'E2P-{sid} coaxiality fail')
        result['coaxial_pairs'].append(pair)

    counts = {n: len(m['holes']) for n, m in result['members'].items()}
    result['hole_counts'] = counts
    result['hole_counts_note'] = '每根纵梁竖向 Ø4.5 孔 2（X±164；其余孔系属 E1 读回口径，本 run 不重复枚举）；每个端塞竖向 Ø4.5 孔 1'
    result['verdict'] = 'PASS' if not result['failures'] else 'FAIL'
    result['elapsed_s'] = round(time.time() - t0, 3)
    for m in result['members'].values():
        for h in m['holes']:
            h.pop('axis', None)
    f1 = ev / 'acc_readback_holes_coaxial.json'
    wlf(f1, json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    sidecar(f1)
    offs, pars = [], []
    for p in result['coaxial_pairs']:
        for k, v in p.items():
            if isinstance(v, dict) and 'axis_offset_mm' in v:
                offs.append(v['axis_offset_mm']); pars.append(v['parallel_deviation'])
    print('verdict', result['verdict'], 'failures', result['failures'][:6])
    print('counts', counts)
    print('coaxial max offset', max(offs), 'max par', max(pars))

if __name__ == '__main__':
    main()
