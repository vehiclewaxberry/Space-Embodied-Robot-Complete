# -*- coding: utf-8 -*-
"""WP03 R01 验收6 独立复验 - 任务1：独立读回（审阅者自写，不复用构建者脚本结论）。

对 run exports/ 下全部 STEP（2 甲板、8 角材、2 剪力腹板、32 紧固件包络）独立 import_step 读回：
  A) 完整性：文件名/哈希 vs EXPORT_MANIFEST.json；
  B) 甲板：16 闭孔存在（X=[-150,-50,50,140]/Y=±92.65/Ø3.4），圆柱面完整度、72 点环采样、
     轴心判空；旧孔系 (150,±89) 残余面数=0；孔到柱避口/甲板外边距解析+面距复核；
  C) 同轴：甲板孔 <-> 角材水平腿孔（Z 轴）；角材竖直腿孔 <-> 剪力腹板孔（Y 轴）；
  D) 紧固件包络：杆 R1.5 / 头 R2.75 / 垫+螺母 OD3.0 面数；垫圈 OD <= 6mm 限值。
期望位置真值取自工程源 design_parameters.json deck_fastening_r01（独立读取，不经过构建者脚本）。
"""
import sys, json, math, hashlib, time
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401  必须先于 build123d（系统坏字体守卫）
from cadgen.step_scene import import_step
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
from OCP.BRepTools import BRepTools
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_IN
from OCP.BRepExtrema import BRepExtrema_DistShapeShape

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r01_deck_fastening_20260917'
REVIEW = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r01_deck_fastening_20260917_review'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
EXP = RUN / 'exports'

P = json.loads((ENG / 'design_parameters.json').read_text(encoding='utf-8'))
R01 = P['deck_fastening_r01']
DPAT = R01['deck_hole_pattern']; WPAT = R01['angle_to_shear_web_hole_pattern']
DECKS = {'lower': -99.65, 'upper': -10}
SEGMENTS = [(-167, 11.5), (28.5, 151.5)]
TOL_AXIS = 0.05      # 轴心匹配容差 mm
TOL_COAX = 1e-3      # 同轴判定容差 mm（名义几何应 ~0）
WASHER_OD_LIMIT = R01['deck_angle_fastener_candidate']['washer_outer_diameter_max_mm']

def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))

def sidecar(p):
    h = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    wlf(str(p) + '.sha256', h + '  ' + Path(p).name + '\n')
    return h

def sha256_of(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def cyl_faces(shape, r_tol=0.02):
    """提取全部圆柱面: (radius, axis_point, axis_dir, face, u_fullness)"""
    out = []
    for f in shape.faces():
        ad = BRepAdaptor_Surface(f.wrapped)
        if ad.GetType() != GeomAbs_Cylinder:
            continue
        cyl = ad.Cylinder(); ax = cyl.Axis()
        umin, umax, vmin, vmax = BRepTools.UVBounds_s(f.wrapped)
        loc = ax.Location(); d = ax.Direction()
        out.append({'r': cyl.Radius(), 'p': (loc.X(), loc.Y(), loc.Z()),
                    'd': (d.X(), d.Y(), d.Z()), 'fullness': (umax - umin) / (2 * math.pi),
                    'face': f})
    return out

def plane_faces(shape):
    out = []
    for f in shape.faces():
        ad = BRepAdaptor_Surface(f.wrapped)
        if ad.GetType() == GeomAbs_Plane:
            pl = ad.Plane(); n = pl.Axis().Direction(); l = pl.Location()
            out.append({'n': (n.X(), n.Y(), n.Z()), 'p': (l.X(), l.Y(), l.Z()), 'face': f})
    return out

class SolidProbe:
    def __init__(self, shape):
        self.shape = shape
    def inside(self, x, y, z):
        c = BRepClass3d_SolidClassifier(self.shape.wrapped, gp_Pnt(x, y, z), 1e-9)
        return c.State() == TopAbs_IN

def axis_deviation_2d(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])

def check_closed_hole(solid, x, y, axis, zmid, hole_r, n_ring=72):
    """闭孔判定：轴心为空空腔、孔壁外 0.05mm 环点全在材料内。返回 (closed, ring_out_count)"""
    probe = SolidProbe(solid)
    axis_void = not probe.inside(x, y, zmid)
    out_pts = []
    for i in range(n_ring):
        a = 2 * math.pi * i / n_ring
        if axis == 'Z':
            px, py, pz = x + (hole_r + 0.05) * math.cos(a), y + (hole_r + 0.05) * math.sin(a), zmid
        else:  # Y 轴孔
            px, py, pz = x + (hole_r + 0.05) * math.cos(a), y, zmid + (hole_r + 0.05) * math.sin(a)
        if not probe.inside(px, py, pz):
            out_pts.append([round(px, 4), round(py, 4), round(pz, 4)])
    return axis_void and not out_pts, out_pts

def main():
    t0 = time.time()
    rep = {'review': 'r01_deck_fastening_20260917_review', 'check': 'ACC6_T1_independent_readback',
           'reviewer': 'WP03 R01 独立审阅者（只读最终导出，未修改候选）',
           'readback_tool': 'cadgen.step_scene.import_step (OCP), 自写脚本 scripts/r10_independent_readback.py',
           'units': 'mm', 'frame': 'S',
           'expected_source': '20_engineering/service_robot_wp03_spacecraft_body_r1/design_parameters.json deck_fastening_r01',
           'expected_source_sha256': sha256_of(ENG / 'design_parameters.json'),
           'tolerances': {'axis_match_mm': TOL_AXIS, 'coaxial_mm': TOL_COAX, 'ring_samples': 72,
                          'washer_od_limit_mm': WASHER_OD_LIMIT},
           'failures': []}

    # ---------- A) 清单与哈希完整性 ----------
    manifest = json.loads((EXP / 'EXPORT_MANIFEST.json').read_text(encoding='utf-8'))
    mfiles = {m['file']: m for m in manifest['parts']}
    hash_bad = []
    for fn, m in mfiles.items():
        if sha256_of(EXP / fn) != m['sha256']:
            hash_bad.append(fn)
    rep['export_manifest'] = {'files': len(mfiles), 'sha256_all_match': not hash_bad, 'mismatch': hash_bad,
                              'manifest_sha256': sha256_of(EXP / 'EXPORT_MANIFEST.json')}
    if hash_bad:
        rep['failures'].append(f'EXPORT_MANIFEST 哈希不一致: {hash_bad}')
    kinds = {}
    for m in manifest['parts']:
        kinds[m['kind']] = kinds.get(m['kind'], 0) + 1
    rep['export_manifest']['counts_by_kind'] = kinds

    shapes = {}
    for fn in sorted(mfiles):
        shapes[fn[:-5]] = import_step(str(EXP / fn))

    # ---------- B) 甲板闭孔 ----------
    rep['decks'] = {}
    hole_r = DPAT['diameter_mm'] / 2
    total_closed = 0
    for deck, z in DECKS.items():
        s = shapes[f'{deck}_equipment_deck']
        cf = [c for c in cyl_faces(s) if abs(c['r'] - hole_r) < 0.02 and abs(abs(c['d'][2]) - 1) < 1e-6]
        dinfo = {'solid_count': len(s.solids()), 'cyl_hole_faces_r1.7_axisZ': len(cf), 'holes': [],
                 'old_pattern_residuals': [], 'closed_hole_count': 0}
        if len(cf) != 8:
            rep['failures'].append(f'{deck}: Z 轴 Ø3.4 圆柱孔面数 {len(cf)} != 8')
        for x in DPAT['X_S_mm']:
            for y in DPAT['Y_S_mm']:
                cand = [c for c in cf if abs(c['p'][0] - x) < TOL_AXIS and abs(c['p'][1] - y) < TOL_AXIS]
                found = bool(cand)
                fullness = max((c['fullness'] for c in cand), default=None)
                closed, ring_out = check_closed_hole(s, x, y, 'Z', z, hole_r)
                # 解析边距：孔到柱避口（x=160 避口内壁 x=151.5；y 范围 85.65..102.65 覆盖孔心 y）
                notch_gap = 151.5 - (x + hole_r) if x > 20 else 20 - 8.5 - (x + hole_r)
                edge_gap = 98.15 - abs(y) - hole_r
                dinfo['holes'].append({'x_S_mm': x, 'y_S_mm': y, 'face_found': found,
                                       'cyl_fullness': fullness, 'ring_points_outside': ring_out,
                                       'closed': closed,
                                       'analytic_hole_to_column_notch_mm': round(notch_gap, 6),
                                       'analytic_hole_to_deck_outer_edge_mm': round(edge_gap, 6)})
                if not (found and closed and fullness is not None and fullness > 0.999):
                    rep['failures'].append(f'{deck} 孔({x},{y}): found={found} closed={closed} fullness={fullness}')
                else:
                    total_closed += 1
                    dinfo['closed_hole_count'] += 1
        # 旧孔系残余
        for oy in (-89, 89):
            res = [c for c in cf if abs(c['p'][0] - 150) < TOL_AXIS and abs(c['p'][1] - oy) < TOL_AXIS]
            dinfo['old_pattern_residuals'].append({'old_x': 150, 'old_y': oy, 'residual_faces': len(res)})
            if res:
                rep['failures'].append(f'{deck}: 旧孔(150,{oy}) 残余面 {len(res)}')
        # 孔到避口壁面 BRep 距离（x=140 孔 vs x=151.5 避口内壁面）
        notch_walls = [p for p in plane_faces(s) if abs(abs(p['n'][0]) - 1) < 1e-6 and abs(p['p'][0] - 151.5) < 0.01]
        h140 = [c for c in cf if abs(c['p'][0] - 140) < TOL_AXIS]
        if notch_walls and h140:
            best = min(
                BRepExtrema_DistShapeShape(c['face'].wrapped, w['face'].wrapped).Value()
                for c in h140 for w in notch_walls)
            dinfo['brep_min_dist_hole140_to_notch_wall_mm'] = round(best, 6)
        # 避口壁面清点（4 避口 x 3 壁 = 12）
        walls = [p for p in plane_faces(s)
                 if (abs(abs(p['n'][0]) - 1) < 1e-6 and any(abs(p['p'][0] - v) < 0.01 for v in (11.5, 28.5, 151.5, 168.5))) or
                    (abs(abs(p['n'][1]) - 1) < 1e-6 and abs(abs(p['p'][1]) - 85.65) < 0.01)]
        dinfo['column_notch_wall_faces'] = len(walls)
        rep['decks'][deck] = dinfo
    rep['total_closed_holes'] = total_closed
    rep['expected_closed_holes'] = 16

    # ---------- C) 同轴 ----------
    rep['coaxial'] = {'deck_angle_pairs': [], 'angle_web_pairs': []}
    for deck, z in DECKS.items():
        ds = shapes[f'{deck}_equipment_deck']
        deck_axes = [(c['p'][0], c['p'][1]) for c in cyl_faces(ds)
                     if abs(c['r'] - hole_r) < 0.02 and abs(abs(c['d'][2]) - 1) < 1e-6]
        for side in (-1, 1):
            for k, (a, b) in enumerate(SEGMENTS):
                aname = f'{deck}_deck_angle_{side}_{k}'
                ang = shapes[aname]
                acf = cyl_faces(ang)
                a_hz = [(c['p'][0], c['p'][1]) for c in acf
                        if abs(c['r'] - hole_r) < 0.02 and abs(abs(c['d'][2]) - 1) < 1e-6]
                a_vy = [(c['p'][0], c['p'][2]) for c in acf
                        if abs(c['r'] - hole_r) < 0.02 and abs(abs(c['d'][1]) - 1) < 1e-6]
                # 甲板-角材：期望该段内全部甲板孔
                exp_x = [x for x in DPAT['X_S_mm'] if a - 1e-9 <= x <= b + 1e-9]
                for x in exp_x:
                    ey = side * 92.65
                    da = min(deck_axes, key=lambda ax: axis_deviation_2d(ax, (x, ey)))
                    aa = min(a_hz, key=lambda ax: axis_deviation_2d(ax, (x, ey))) if a_hz else None
                    dev = axis_deviation_2d(da, aa) if aa else None
                    ok = aa is not None and axis_deviation_2d(da, (x, ey)) < TOL_AXIS and dev < TOL_COAX
                    rep['coaxial']['deck_angle_pairs'].append(
                        {'pair': f'{deck}/{aname}/x{x}', 'expected_xy': [x, ey],
                         'deck_axis': [round(v, 6) for v in da],
                         'angle_axis': [round(v, 6) for v in aa] if aa else None,
                         'coaxial_deviation_mm': None if dev is None else round(dev, 9), 'ok': ok})
                    if not ok:
                        rep['failures'].append(f'同轴失败 deck-angle {deck} {aname} x={x}: dev={dev}')
                # 角材-腹板
                web = shapes[f'shear_web_{side}']
                web_axes = [(c['p'][0], c['p'][2]) for c in cyl_faces(web)
                            if abs(c['r'] - hole_r) < 0.02 and abs(abs(c['d'][1]) - 1) < 1e-6]
                wz = WPAT['Z_S_mm_by_deck'][deck]
                for x in WPAT['X_S_mm_by_segment'][k]:
                    wa = min(web_axes, key=lambda ax: axis_deviation_2d(ax, (x, wz)))
                    aa = min(a_vy, key=lambda ax: axis_deviation_2d(ax, (x, wz))) if a_vy else None
                    dev = axis_deviation_2d(wa, aa) if aa else None
                    ok = aa is not None and axis_deviation_2d(wa, (x, wz)) < TOL_AXIS and dev < TOL_COAX
                    rep['coaxial']['angle_web_pairs'].append(
                        {'pair': f'{deck}/{aname}/shear_web_{side}/x{x}', 'expected_xz': [x, wz],
                         'web_axis_xz': [round(v, 6) for v in wa],
                         'angle_axis_xz': [round(v, 6) for v in aa] if aa else None,
                         'coaxial_deviation_mm': None if dev is None else round(dev, 9), 'ok': ok})
                    if not ok:
                        rep['failures'].append(f'同轴失败 angle-web {deck} {aname} x={x}: dev={dev}')
    rep['coaxial']['deck_angle_ok'] = sum(p['ok'] for p in rep['coaxial']['deck_angle_pairs'])
    rep['coaxial']['angle_web_ok'] = sum(p['ok'] for p in rep['coaxial']['angle_web_pairs'])

    # ---------- D) 紧固件包络 ----------
    rep['fasteners'] = []
    for name in sorted(n for n in shapes if 'fastener' in n):
        s = shapes[name]
        cf = cyl_faces(s)
        r15 = [c for c in cf if abs(c['r'] - 1.5) < 0.02]
        r275 = [c for c in cf if abs(c['r'] - 2.75) < 0.02]
        r30 = [c for c in cf if abs(c['r'] - 3.0) < 0.02]
        rmax = max(c['r'] for c in cf)
        od_ok = 2 * rmax <= WASHER_OD_LIMIT + 1e-6
        complete = bool(r15) and bool(r275) and len(r30) >= 2 and od_ok
        rep['fasteners'].append({'fastener': name, 'shank_R1.5_faces': len(r15),
                                 'head_R2.75_faces': len(r275), 'OD6_class_faces': len(r30),
                                 'max_cyl_OD_mm': round(2 * rmax, 6), 'washer_od_within_limit': od_ok,
                                 'complete': complete})
        if not complete:
            rep['failures'].append(f'包络不完整 {name}: shank={len(r15)} head={len(r275)} OD6={len(r30)} maxOD={2*rmax}')
    rep['fastener_envelopes_complete'] = sum(f['complete'] for f in rep['fasteners'])
    rep['fastener_envelopes_total'] = len(rep['fasteners'])

    rep['verdict'] = 'PASS' if not rep['failures'] else 'FAIL'
    rep['elapsed_s'] = round(time.time() - t0, 3)
    f = REVIEW / 'evidence' / 'review_t1_readback.json'
    f.parent.mkdir(parents=True, exist_ok=True)
    wlf(f, json.dumps(rep, ensure_ascii=False, indent=2) + '\n'); sidecar(f)
    print('T1', rep['verdict'], 'closed', total_closed, '/16',
          'coax DA', rep['coaxial']['deck_angle_ok'], 'AW', rep['coaxial']['angle_web_ok'],
          'fasteners', rep['fastener_envelopes_complete'], '/', rep['fastener_envelopes_total'],
          'failures', len(rep['failures']), 'elapsed', rep['elapsed_s'])
    for x in rep['failures'][:12]:
        print(' FAIL', x)

if __name__ == '__main__':
    main()
