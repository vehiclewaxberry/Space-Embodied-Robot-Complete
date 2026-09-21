# -*- coding: utf-8 -*-
"""R01 验收1/2：STEP 读回机器验证。
验收1：两甲板共 16 个所需闭孔、原四处破边消除；每孔闭合性 + 到柱避口最小距离机器数值。
验收2：32 组连接的基准/孔轴/方向/单位/夹层一致性机器核对。
读回工具：build123d.import_step（任务书指定）。所有几何为 S 系世界坐标，单位 mm。"""
import sys, json, math, hashlib, time
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401
from build123d import import_step
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_IN

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r01_deck_fastening_20260917'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, str(ENG))
import spacecraft_model as sm

R01 = sm.P['deck_fastening_r01']
DPAT = R01['deck_hole_pattern']; WPAT = R01['angle_to_shear_web_hole_pattern']
DECKS = {'lower': -99.65, 'upper': -10}
SEGMENTS = [(-167, 11.5), (28.5, 151.5)]
TOL = 1e-6

def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))

def sidecar(p):
    h = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    wlf(str(p) + '.sha256', h + '  ' + Path(p).name + '\n')
    return h

def cyl_faces(shape, axis_tol=1e-6):
    """返回 [(radius, loc(x,y,z), dir(x,y,z), face)] 仅圆柱面。"""
    out = []
    for f in shape.faces():
        ad = BRepAdaptor_Surface(f.wrapped)
        if ad.GetType() == GeomAbs_Cylinder:
            c = ad.Cylinder(); a = c.Axis(); l = a.Location(); d = a.Direction()
            out.append((c.Radius(), (l.X(), l.Y(), l.Z()), (d.X(), d.Y(), d.Z()), f))
    return out

def plane_faces(shape):
    out = []
    for f in shape.faces():
        ad = BRepAdaptor_Surface(f.wrapped)
        if ad.GetType() == GeomAbs_Plane:
            pl = ad.Plane(); a = pl.Axis(); l = a.Location(); d = a.Direction()
            out.append(((l.X(), l.Y(), l.Z()), (d.X(), d.Y(), d.Z()), f))
    return out

def dist_shapes(a, b):
    ext = BRepExtrema_DistShapeShape(a.wrapped, b.wrapped)
    if not ext.IsDone():
        return None
    return ext.Value()

def inside(solid, x, y, z):
    cls = BRepClass3d_SolidClassifier(solid.wrapped, gp_Pnt(x, y, z), 1e-9)
    return cls.State() == TopAbs_IN

def axis_distance(l1, d1, l2, d2):
    """两直线：平行度 |d1×d2| 与 l2 到 line1 的距离。"""
    cross = (d1[1]*d2[2]-d1[2]*d2[1], d1[2]*d2[0]-d1[0]*d2[2], d1[0]*d2[1]-d1[1]*d2[0])
    par = math.sqrt(sum(c*c for c in cross))
    v = (l2[0]-l1[0], l2[1]-l1[1], l2[2]-l1[2])
    cx = (v[1]*d1[2]-v[2]*d1[1], v[2]*d1[0]-v[0]*d1[2], v[0]*d1[1]-v[1]*d1[0])
    return par, math.sqrt(sum(c*c for c in cx))

def hole_closure(solid, x, y, z, r, n=72, dr=0.05):
    """环采样：r+dr 处 n 点全部在实体内 -> 闭孔；轴心必须在孔外。"""
    ring_out = []
    for i in range(n):
        a = 2*math.pi*i/n
        px, py = x + (r+dr)*math.cos(a), y + (r+dr)*math.sin(a)
        if not inside(solid, px, py, z):
            ring_out.append(round(a, 4))
    axis_in = inside(solid, x, y, z)
    return ring_out, axis_in

def main():
    t0 = time.time()
    ev = RUN / 'evidence'
    shapes = {}
    for p in sm.deck_fastening_parts(sm.P):
        if p['kind'] in ('DECK', 'ANGLE', 'WEB'):
            shapes[p['name']] = import_step(str(RUN / 'exports' / (p['name'] + '.step')))
    result = {'run': 'r01_deck_fastening_20260917', 'check': 'ACC1_closed_holes_and_broken_edge_elimination',
              'readback_tool': 'build123d.import_step', 'units': 'mm', 'frame': 'S',
              'decks': {}, 'verdict': None, 'failures': []}
    # ---------- 验收 1：甲板闭孔 ----------
    for deck, z in DECKS.items():
        name = f'{deck}_equipment_deck'
        s = shapes[name]
        solids = s.solids()
        solid = solids[0]
        cf = cyl_faces(s)
        holes = [c for c in cf if abs(c[0] - DPAT['diameter_mm']/2) < 1e-6 and abs(abs(c[2][2]) - 1) < 1e-6]
        drec = {'file': name + '.step', 'solid_count': len(solids),
                'cyl_hole_faces_r1.7_axisZ': len(holes), 'holes': [], 'old_pattern_residuals': []}
        for x in DPAT['X_S_mm']:
            for y in DPAT['Y_S_mm']:
                cand = [c for c in holes if abs(c[1][0] - x) < 1e-6 and abs(c[1][1] - y) < 1e-6]
                hrec = {'x_S_mm': x, 'y_S_mm': y, 'face_found': len(cand) > 0}
                if cand:
                    r, loc, drc, face = cand[0]
                    # 闭合性 A：圆柱面完整度 = 面积 / (2πr·轴向跨度)
                    bb = face.bounding_box()
                    span = max(bb.size.Z, 1e-9)
                    fullness = face.area / (2*math.pi*r*span)
                    # 闭合性 B：72 点环采样全部在材料内
                    ring_out, axis_in = hole_closure(solid, x, y, z, r)
                    # 到柱避口最小距离：孔柱面 → 避口竖直平面
                    notch_walls = []
                    for ploc, pn, pf in plane_faces(s):
                        if abs(pn[2]) < 1e-6:  # 竖直面
                            if (abs(pn[0]) > 1-1e-6 and any(abs(abs(ploc[0])-v) < 1e-6 for v in (11.5, 28.5, 151.5, 168.5))) or \
                               (abs(pn[1]) > 1-1e-6 and any(abs(abs(ploc[1])-v) < 1e-6 for v in (85.65, 102.65))):
                                notch_walls.append(pf)
                    dnotch = min(dist_shapes(face, w) for w in notch_walls)
                    outer = [pf for ploc, pn, pf in plane_faces(s)
                             if (abs(pn[0]) > 1-1e-6 and abs(abs(ploc[0])-172) < 1e-6) or
                                (abs(pn[1]) > 1-1e-6 and abs(abs(ploc[1])-98.15) < 1e-6)]
                    dedge = min(dist_shapes(face, w) for w in outer)
                    hrec.update(cyl_fullness=fullness, ring_points_outside=ring_out,
                                axis_inside_material=axis_in,
                                closed=(fullness > 1-1e-3) and (not ring_out) and (not axis_in),
                                min_dist_to_column_notch_mm=dnotch, min_dist_to_deck_outer_edge_mm=dedge)
                    if not hrec['closed']:
                        result['failures'].append(f'{name} hole ({x},{y}) not closed')
                else:
                    result['failures'].append(f'{name} hole ({x},{y}) face not found')
                drec['holes'].append(hrec)
        # 旧反例残迹：旧孔位 (150,±89) 不得再有任何圆柱孔面
        for y in (-89, 89):
            res = [c for c in holes if abs(c[1][0] - 150) < 0.5 and abs(c[1][1] - y) < 3.5]
            drec['old_pattern_residuals'].append({'old_x': 150, 'old_y': y, 'residual_faces': len(res)})
            if res:
                result['failures'].append(f'{name} old hole (150,{y}) residual face present')
        drec['closed_hole_count'] = sum(1 for h in drec['holes'] if h.get('closed'))
        result['decks'][deck] = drec
    total_closed = sum(d['closed_hole_count'] for d in result['decks'].values())
    result['total_closed_holes'] = total_closed
    result['expected_closed_holes'] = 16
    result['verdict'] = 'PASS' if total_closed == 16 and not result['failures'] else 'FAIL'
    result['elapsed_s'] = round(time.time() - t0, 3)
    f1 = ev / 'acc1_deck_closed_holes.json'
    wlf(f1, json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    h1 = sidecar(f1)
    print('ACC1', result['verdict'], 'closed', total_closed, '/16', 'failures', result['failures'][:4])
    for deck, d in result['decks'].items():
        for h in d['holes']:
            print(' ', deck, h['x_S_mm'], h['y_S_mm'], 'closed=', h.get('closed'),
                  'notch=', None if 'min_dist_to_column_notch_mm' not in h else round(h['min_dist_to_column_notch_mm'], 4),
                  'edge=', None if 'min_dist_to_deck_outer_edge_mm' not in h else round(h['min_dist_to_deck_outer_edge_mm'], 4))

if __name__ == '__main__':
    main()
