# -*- coding: utf-8 -*-
"""R07-E1 STEP 读回机器验证（build123d.import_step 自读回）：
A) 受影响 9 件闭孔：纵梁 Y 向贯穿孔（壁内闭合）、横梁/桥端面盲孔（孔柱面完整、不破边）；
B) 对偶同轴：每对 纵梁孔轴 vs 端面孔轴 vs 栓包络轴 的平行度 |d1×d2| 与轴线距（机器数值）；
C) 孔数/孔位与参数表逐位一致。所有几何 S 系世界坐标，单位 mm。"""
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
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_root_longeron_anchoring_20260917'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, str(ENG))
import spacecraft_model as sm

E1 = sm.P['root_anchoring_r07_e1']
R_HOLE = E1['hole_diameter_mm'] / 2

def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))

def sidecar(p):
    h = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    wlf(str(p) + '.sha256', h + '  ' + Path(p).name + '\n')
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

def ring_closure(solid, cx, cz, y, r, n=72, dr=0.05):
    """XZ 平面环采样（Y 轴孔）：r+dr 处 n 点全部在实体内 -> 闭孔；轴心须在孔外。"""
    out_pts = []
    for i in range(n):
        a = 2*math.pi*i/n
        px, pz = cx + (r+dr)*math.cos(a), cz + (r+dr)*math.sin(a)
        if not inside(solid, px, y, pz):
            out_pts.append(round(a, 4))
    return out_pts, inside(solid, cx, y, cz)

def main():
    t0 = time.time()
    ev = RUN / 'evidence'
    exp = RUN / 'exports'
    spec = sm.root_anchoring_spec(sm.P)
    result = {'run': 'r07_root_longeron_anchoring_20260917',
              'check': 'step_readback_closed_holes_and_coaxiality',
              'readback_tool': 'build123d.import_step', 'units': 'mm', 'frame': 'S',
              'members': {}, 'coaxial_pairs': [], 'failures': [], 'verdict': None}
    shapes = {}
    for name in ['RB_longeron_1_1', 'RB_longeron_-1_1', 'RB_longeron_1_-1', 'RB_longeron_-1_-1',
                 'RB_upper_beam_20', 'RB_upper_beam_160', 'RB_lower_beam_20', 'RB_lower_beam_160',
                 'WP01-RB-BRIDGE-R2']:
        shapes[name] = import_step(str(exp / f'{name}.step'))

    groups = {g['id']: g for g in E1['groups']}
    # ---------- A/C: 纵梁贯穿孔 + 横梁/桥盲孔 ----------
    for r in spec:
        sy, sz = r['sy'], r['sz']
        rail_name = f"RB_longeron_{sy}_{sz}"
        rail = shapes[rail_name]
        rail_solid = rail.solids()[0]
        mrec = result['members'].setdefault(rail_name, {'holes': []})
        cf = [c for c in cyl_faces(rail) if abs(c[0] - R_HOLE) < 1e-6 and abs(abs(c[2][1]) - 1) < 1e-6]
        cand = [c for c in cf if abs(c[1][0] - r['x']) < 1e-6 and abs(c[1][2] - r['z']) < 1e-6]
        hrec = {'pair_id': f"E1P-{r['group']}-{r['index']}", 'kind': 'longeron_through_hole',
                'expected_xz_mm': [r['x'], r['z']], 'face_found': len(cand) > 0}
        if not cand:
            result['failures'].append(f'{rail_name} hole ({r["x"]},{r["z"]}) not found')
        else:
            rr, loc, drc, face = cand[0]
            # 双壁中面闭孔环采样：外壁中面 y=sy*112.15、内壁中面 y=sy*102.15
            ro1, ai1 = ring_closure(rail_solid, r['x'], r['z'], sy*112.15, rr)
            ro2, ai2 = ring_closure(rail_solid, r['x'], r['z'], sy*102.15, rr)
            hrec.update(axis_loc_mm=list(loc), axis_dir=list(drc),
                        outer_wall_closed=(not ro1) and (not ai1), inner_wall_closed=(not ro2) and (not ai2),
                        ring_out_outer=ro1, ring_out_inner=ro2)
            if not (hrec['outer_wall_closed'] and hrec['inner_wall_closed']):
                result['failures'].append(f'{rail_name} hole ({r["x"]},{r["z"]}) wall closure fail')
            hrec['axis'] = (loc, drc)
        mrec['holes'].append(hrec)
        r['_rail_axis'] = hrec.get('axis')

        # B 件端面盲孔
        b_name = 'WP01-RB-BRIDGE-R2' if r['member'] == 'bridge' else f"RB_{r['member']}_{r['beam_x']}"
        bs = shapes[b_name]
        bsolid = bs.solids()[0]
        mrec = result['members'].setdefault(b_name, {'holes': []})
        cfb = [c for c in cyl_faces(bs) if abs(c[0] - R_HOLE) < 1e-6 and abs(abs(c[2][1]) - 1) < 1e-6]
        candb = [c for c in cfb if abs(c[1][0] - r['x']) < 1e-6 and abs(c[1][2] - r['z']) < 1e-6]
        brec = {'pair_id': f"E1P-{r['group']}-{r['index']}", 'kind': 'beam_end_blind_hole',
                'expected_xz_mm': [r['x'], r['z']], 'face_found': len(candb) > 0}
        if not candb:
            result['failures'].append(f'{b_name} blind hole ({r["x"]},{r["z"]}) not found')
        else:
            rr, loc, drc, face = candb[0]
            bb = face.bounding_box()
            span = max(bb.size.Y, 1e-9)
            fullness = face.area / (2*math.pi*rr*span)
            # 端面盲孔闭合：在孔口内侧 1 mm 平面环采样（避免边界面分类歧义）+ 孔深
            ro, ai = ring_closure(bsolid, r['x'], r['z'], sy*100.15, rr)
            depth = bb.size.Y
            brec.update(axis_loc_mm=list(loc), axis_dir=list(drc), modeled_depth_mm=round(depth, 6),
                        cyl_fullness=fullness, mouth_closed=(not ro) and (not ai), ring_out=ro,
                        closed=(fullness > 1-1e-3) and (not ro) and (not ai))
            if not brec['closed']:
                result['failures'].append(f'{b_name} blind hole ({r["x"]},{r["z"]}) not closed')
            brec['axis'] = (loc, drc)
        mrec['holes'].append(brec)
        r['_beam_axis'] = brec.get('axis')

    # ---------- B: 同轴数值（纵梁孔 vs 端面孔 vs 栓包络） ----------
    bolt_shapes = {}
    for r in spec:
        bn = f"e1_anchor_bolt_{r['group']}_{r['index']}"
        bolt_shapes[bn] = import_step(str(exp / f'{bn}.step'))
        cfb = [c for c in cyl_faces(bolt_shapes[bn]) if abs(c[0] - 1.5) < 1e-6]
        bolt_axis = cfb[0][1], cfb[0][2]
        pair = {'pair_id': f'E1P-{r["group"]}-{r["index"]}'}
        ok = True
        for label, ax in [('longeron_vs_beam', (r.get('_rail_axis'), r.get('_beam_axis'))),
                          ('longeron_vs_bolt', (r.get('_rail_axis'), bolt_axis)),
                          ('beam_vs_bolt', (r.get('_beam_axis'), bolt_axis))]:
            a, b = ax
            if a is None or b is None:
                pair[label] = 'MISSING_AXIS'; ok = False; continue
            par, off = axis_distance(a[0], a[1], b[0], b[1])
            pair[label] = {'parallel_deviation': par, 'axis_offset_mm': off}
            if par > 1e-6 or off > 1e-6:
                ok = False
        pair['coaxial'] = ok
        if not ok:
            result['failures'].append(f'{pair["pair_id"]} coaxiality fail')
        result['coaxial_pairs'].append(pair)

    # 孔数核对
    counts = {n: len(m['holes']) for n, m in result['members'].items()}
    result['hole_counts'] = counts
    result['hole_counts_note'] = '纵梁上 5/下 3（每根，含两侧端）；上横梁 4(x20)/2(x160)；下横梁 4/2；桥 4'
    result['verdict'] = 'PASS' if not result['failures'] else 'FAIL'
    result['elapsed_s'] = round(time.time() - t0, 3)
    # 去掉不可序列化键
    for m in result['members'].values():
        for h in m['holes']:
            h.pop('axis', None)
    f1 = ev / 'acc_readback_holes_coaxial.json'
    wlf(f1, json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    sidecar(f1)
    print('verdict', result['verdict'], 'failures', result['failures'][:6])
    print('counts', counts)
    off = [p['longeron_vs_beam']['axis_offset_mm'] for p in result['coaxial_pairs'] if isinstance(p.get('longeron_vs_beam'), dict)]
    par = [p['longeron_vs_beam']['parallel_deviation'] for p in result['coaxial_pairs'] if isinstance(p.get('longeron_vs_beam'), dict)]
    print('coaxial max offset', max(off), 'max par', max(par))

if __name__ == '__main__':
    main()
