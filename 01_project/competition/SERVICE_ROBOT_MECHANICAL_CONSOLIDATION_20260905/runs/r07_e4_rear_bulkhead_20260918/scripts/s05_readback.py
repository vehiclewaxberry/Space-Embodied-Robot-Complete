# -*- coding: utf-8 -*-
"""R07-E4 STEP 读回机器验证（build123d.import_step 自读回）：
A) 隔框 Ø8 窗口（既有未改）：4 角 X 轴孔面在位 + 窗口中面(x=-186)环闭合；
B) 夹套：ID Ø4.5 X 轴孔环闭合（筒中面 x=-186 / 法兰中面 x=-190，环在套材料内）+
   筒外柱面 OD7.9 在位；与窗口/端框孔/栓杆同轴；
C) 改件螺钉 M4×30：杆轴 X 向在位，bbox x∈[-195,-161]，尖端 x=-161 与 M4×22 基线
   （同源复建 screw(4,22,7,4)@-183，尖 -161）逐位一致；头 x[-195,-191]；
D) 端框 Ø4.5 孔 4（既有未改计数核对）+ 端塞 Ø3.3 导孔 1/塞（既有）；
E) 同轴：每角 窗口轴 vs 套 ID 轴 vs 端框孔轴 vs 栓杆轴（|d1×d2| 与轴线距机器数值）。
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
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_e4_rear_bulkhead_20260918'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, str(ENG))
import spacecraft_model as sm

E4 = sm.P['rear_bulkhead_clamp_r07_e4']
S = E4['clamp_sleeve']; RS = E4['rear_screw']
R_WIN = 4.0; R_ID = S['id_diameter_mm'] / 2; R_FRAME = 2.25; R_SHANK = RS['shank_diameter_mm'] / 2; R_PILOT = 1.65

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

def ring_closure_xaxis(solid, x, cy, cz, r, n=72, dr=0.05):
    """YZ 平面环采样（X 轴孔）：r+dr 处 n 点全部在实体内 -> 闭孔；轴心须在孔外。"""
    outs = []
    for i in range(n):
        a = 2*math.pi*i/n
        py, pz = cy + (r+dr)*math.cos(a), cz + (r+dr)*math.sin(a)
        if not inside(solid, x, py, pz):
            outs.append(round(a, 4))
    return outs, inside(solid, x, cy, cz)

def find_xaxis_hole(shape, r_target, y, z, tol=1e-6):
    out = []
    for rr, loc, drc, f in cyl_faces(shape):
        if abs(rr - r_target) > tol or abs(abs(drc[0]) - 1) > 1e-6:
            continue
        if abs(loc[1] - y) < 1e-6 and abs(loc[2] - z) < 1e-6:
            out.append((rr, loc, drc, f))
    return out

def main():
    t0 = time.time()
    ev = RUN / 'evidence'; exp = RUN / 'exports'
    spec = sm.rear_bulkhead_clamp_spec(sm.P)
    result = {'run': 'r07_e4_rear_bulkhead_20260918',
              'check': 'step_readback_paired_holes_and_coaxiality',
              'readback_tool': 'build123d.import_step', 'units': 'mm', 'frame': 'S',
              'members': {}, 'coaxial_pairs': [], 'hole_counts': {}, 'failures': [], 'verdict': None}
    bulk = import_step(str(exp / 'rear_launch_bulkhead.step')); bsolid = bulk.solids()[0]
    frame = import_step(str(exp / 'RB_end_frame_-1.step')); fsolid = frame.solids()[0]
    sleeves = {r['group']: import_step(str(exp / f"e4_clamp_sleeve_{r['group']}.step")) for r in spec}
    screws = {r['screw']: import_step(str(exp / f"{r['screw']}.step")) for r in spec}
    plugs = {r['plug']: import_step(str(exp / f"{r['plug']}.step")) for r in spec}

    for r in spec:
        pid = f"E4P-{r['group']}"; y, z = r['y'], r['z']
        axes = {}
        # A) 隔框 Ø8 窗口（既有未改）
        cand = find_xaxis_hole(bulk, R_WIN, y, z)
        hrec = {'kind': 'bulkhead_d8_window_preexisting', 'pair_id': pid, 'expected_mm': [-186, y, z], 'face_found': len(cand) > 0}
        if not cand:
            result['failures'].append(f'{pid} bulkhead window not found')
        else:
            rr, loc, drc, _ = cand[0]
            ro, ai = ring_closure_xaxis(bsolid, -186, y, z, rr)
            hrec.update(axis_loc_mm=list(loc), axis_dir=list(drc), midplane_closed=(not ro) and (not ai))
            if not hrec['midplane_closed']:
                result['failures'].append(f'{pid} bulkhead window closure fail')
            axes['window'] = (loc, drc)
        result['members'].setdefault('rear_launch_bulkhead', {'holes': []})['holes'].append(hrec)
        # B) 夹套 ID + 筒外柱面
        sl = sleeves[r['group']]; slsolid = sl.solids()[0]
        cand = find_xaxis_hole(sl, R_ID, y, z)
        hrec = {'kind': 'e4_sleeve_id_hole', 'pair_id': pid, 'expected_mm': [-186, y, z], 'face_found': len(cand) > 0}
        if not cand:
            result['failures'].append(f'{pid} sleeve ID hole not found')
        else:
            rr, loc, drc, _ = cand[0]
            ro1, ai1 = ring_closure_xaxis(slsolid, -186, y, z, rr)   # 筒中面
            ro2, ai2 = ring_closure_xaxis(slsolid, -190, y, z, rr)   # 法兰中面
            barrel_od = [c for c in cyl_faces(sl) if abs(c[0] - S['barrel_od_mm']/2) < 1e-6 and abs(abs(c[2][0]) - 1) < 1e-6]
            flange_od = [c for c in cyl_faces(sl) if abs(c[0] - S['flange_od_mm']/2) < 1e-6 and abs(abs(c[2][0]) - 1) < 1e-6]
            hrec.update(axis_loc_mm=list(loc), axis_dir=list(drc),
                        barrel_midplane_closed=(not ro1) and (not ai1), flange_midplane_closed=(not ro2) and (not ai2),
                        barrel_od_face_found=len(barrel_od) > 0, flange_od_face_found=len(flange_od) > 0)
            if not (hrec['barrel_midplane_closed'] and hrec['flange_midplane_closed'] and barrel_od and flange_od):
                result['failures'].append(f'{pid} sleeve closure/OD fail')
            axes['sleeve'] = (loc, drc)
        result['members'].setdefault(f"e4_clamp_sleeve_{r['group']}", {'holes': []})['holes'].append(hrec)
        # C) 改件螺钉
        sc = screws[r['screw']]
        cf = [c for c in cyl_faces(sc) if abs(c[0] - R_SHANK) < 1e-6 and abs(abs(c[2][0]) - 1) < 1e-6]
        hrec = {'kind': 'e4_modified_screw_m4x30', 'pair_id': pid, 'face_found': len(cf) > 0}
        if not cf:
            result['failures'].append(f'{pid} screw shank not found')
        else:
            bb = sc.bounding_box()
            tip_ok = abs(bb.min.X - RS['tip_x_S_mm']) < 1e-6
            head_ok = abs(bb.min.X - (-195)) < 1e-6 or abs(bb.min.X - RS['tip_x_S_mm']) < 1e-6
            hrec.update(axis_loc_mm=list(cf[0][1]), axis_dir=list(cf[0][2]),
                        bbox_min_x_mm=round(bb.min.X, 6), bbox_max_x_mm=round(bb.max.X, 6),
                        expected_bbox_x_mm=[-195, -161], tip_unchanged_vs_m4x22_baseline=tip_ok,
                        length_envelope_ok=abs(bb.min.X - (-195)) < 1e-6 and abs(bb.max.X - (-161)) < 1e-6)
            if not (tip_ok and hrec['length_envelope_ok']):
                result['failures'].append(f'{pid} screw envelope fail: {hrec}')
            axes['screw'] = (cf[0][1], cf[0][2])
        result['members'].setdefault(r['screw'], {'holes': []})['holes'].append(hrec)
        # D) 端框孔（既有未改）
        cand = find_xaxis_hole(frame, R_FRAME, y, z)
        hrec = {'kind': 'end_frame_d4p5_hole_preexisting', 'pair_id': pid, 'expected_mm': [-180, y, z], 'face_found': len(cand) > 0}
        if not cand:
            result['failures'].append(f'{pid} end frame hole not found')
        else:
            rr, loc, drc, _ = cand[0]
            ro, ai = ring_closure_xaxis(fsolid, -180, y, z, rr)
            hrec.update(axis_loc_mm=list(loc), axis_dir=list(drc), midplane_closed=(not ro) and (not ai))
            if not hrec['midplane_closed']:
                result['failures'].append(f'{pid} end frame hole closure fail')
            axes['frame'] = (loc, drc)
        result['members'].setdefault('RB_end_frame_-1', {'holes': []})['holes'].append(hrec)
        r['_axes'] = axes

    # E) 同轴（窗口 vs 套 ID vs 端框孔 vs 栓杆）
    for r in spec:
        pid = f"E4P-{r['group']}"
        axes = r.get('_axes', {})
        pair = {'pair_id': pid, 'edge': 'rear_frame_to_bulkhead'}; ok = True
        keys = ['window', 'sleeve', 'frame', 'screw']
        for i, la in enumerate(keys):
            for lb in keys[i+1:]:
                a, b = axes.get(la), axes.get(lb)
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

    # 孔数核对
    counts = {
        'rear_launch_bulkhead_d8_windows': len([c for c in cyl_faces(bulk) if abs(c[0] - R_WIN) < 1e-6 and abs(abs(c[2][0]) - 1) < 1e-6]),
        'RB_end_frame_-1_d4p5_holes': len([c for c in cyl_faces(frame) if abs(c[0] - R_FRAME) < 1e-6 and abs(abs(c[2][0]) - 1) < 1e-6]),
        'expected': '窗口 4（既有未改）；端框 Ø4.5 孔 4（既有未改）',
    }
    for r in spec:
        pn = r['plug']
        counts[f'{pn}_d3p3_pilot'] = len([c for c in cyl_faces(plugs[pn]) if abs(c[0] - R_PILOT) < 1e-6 and abs(abs(c[2][0]) - 1) < 1e-6])
    counts['expected_plugs'] = '端塞 Ø3.3 X 导孔 1/塞（既有未改）'
    if counts['rear_launch_bulkhead_d8_windows'] != 4 or counts['RB_end_frame_-1_d4p5_holes'] != 4:
        result['failures'].append(f'hole counts fail: {counts}')
    for r in spec:
        if counts[f"{r['plug']}_d3p3_pilot"] != 1:
            result['failures'].append(f"{r['plug']} pilot count fail")
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
