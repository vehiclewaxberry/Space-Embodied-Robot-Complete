# -*- coding: utf-8 -*-
"""WP03 R01 验收6 独立复验 - 负控一：旧破边可检出。

旧甲板重建来源（不改原文件，几何行逐义复刻到隔离目录）：
  run 内 inputs/ 快照 spacecraft_model.py（改前版本，sha256 11bd80a667505fc5fd0cf9bc79f7a892bcab5424ae16997de4fd0f163f53a2e9，
  见 inputs/INPUT_MANIFEST.json）第 124-131 行：
    for deck,z in [('lower',-99.65),('upper',-10)]:
        d=Box(344,196.3,3)
        for x in [20,160]:
            for y in [-94.15,94.15]:d=d-box((17,17,7),(x,y,0))
        for x in [-150,-50,50,150]:
            for y in [-89,89]:d=bore(d,3.4,7,(x,y,0))
旧孔系 X=[-150,-50,50,150]/Y=±89 与 inputs/design_parameters.json legacy 语义一致（issues.json R01：
X=150 孔与 x=160 处 17x17 柱避口解析连通 0.2mm，两甲板共四处破边）。

判定器与任务1读回完全同源：闭孔 = 轴心空 + 孔壁外 0.05mm 72 环点全在材料内 + 圆柱面完整度>0.999。
预期：每甲板 (150,-89)、(150,+89) 两孔破边（环点落入避口空腔），其余 6 孔闭合（防误报对照）。
"""
import sys, json, math, hashlib, time
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401
from build123d import Box, Location, export_step
from cadgen.step_scene import import_step
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder
from OCP.BRepTools import BRepTools
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_IN

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r01_deck_fastening_20260917'
REVIEW = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r01_deck_fastening_20260917_review'
WORK = REVIEW / '_work' / 'nc1_legacy_deck'
SRC = RUN / 'inputs' / 'spacecraft_model.py'

def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))

def sidecar(p):
    h = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    wlf(str(p) + '.sha256', h + '  ' + Path(p).name + '\n')
    return h

def box(size, c=(0, 0, 0)):
    return Box(*size).moved(Location(tuple(c)))

def cylinder_d(d, h, c=(0, 0, 0)):
    from build123d import Cylinder
    return Cylinder(d / 2, h).moved(Location(tuple(c)))

def cyl_face_fullness_at(shape, x, y, r=1.7, tol=0.05):
    best = None
    for f in shape.faces():
        ad = BRepAdaptor_Surface(f.wrapped)
        if ad.GetType() != GeomAbs_Cylinder:
            continue
        cyl = ad.Cylinder(); ax = cyl.Axis(); loc = ax.Location(); d = ax.Direction()
        if abs(cyl.Radius() - r) < 0.02 and abs(abs(d.Z()) - 1) < 1e-6 and \
           abs(loc.X() - x) < tol and abs(loc.Y() - y) < tol:
            umin, umax, vmin, vmax = BRepTools.UVBounds_s(f.wrapped)
            fu = (umax - umin) / (2 * math.pi)
            best = fu if best is None else max(best, fu)
    return best

def closed_hole(solid, x, y, zmid, hole_r=1.7, n=72):
    cls = BRepClass3d_SolidClassifier(solid.wrapped, gp_Pnt(x, y, zmid), 1e-9)
    axis_void = cls.State() != TopAbs_IN
    out_pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        px, py = x + (hole_r + 0.05) * math.cos(a), y + (hole_r + 0.05) * math.sin(a)
        c = BRepClass3d_SolidClassifier(solid.wrapped, gp_Pnt(px, py, zmid), 1e-9)
        if c.State() != TopAbs_IN:
            out_pts.append([round(px, 4), round(py, 4)])
    return axis_void and not out_pts, axis_void, out_pts

def build_legacy_deck():
    """逐义复刻 inputs/spacecraft_model.py L124-131 旧甲板（含旧孔系），局部坐标。"""
    d = Box(344, 196.3, 3)
    for x in [20, 160]:
        for y in [-94.15, 94.15]:
            d = d - box((17, 17, 7), (x, y, 0))
    for x in [-150, -50, 50, 150]:
        for y in [-89, 89]:
            d = d - cylinder_d(3.4, 7, (x, y, 0))
    return d

def main():
    t0 = time.time()
    WORK.mkdir(parents=True, exist_ok=True)
    rep = {'review': 'r01_deck_fastening_20260917_review', 'check': 'ACC6_NC1_legacy_broken_edge_detectable',
           'negative_control': '旧孔系 X=[-150,-50,50,150]/Y=±89 重建后，读回判定器必须检出原四处破边',
           'legacy_source': {
               'snapshot': str(SRC).replace('\\', '/'),
               'snapshot_sha256': hashlib.sha256(SRC.read_bytes()).hexdigest(),
               'expected_sha256_per_INPUT_MANIFEST': '11bd80a667505fc5fd0cf9bc79f7a892bcab5424ae16997de4fd0f163f53a2e9',
               'geometry_lines': 'L124-131 (deck box / 17x17 柱避口 @x=20,160,y=±94.15 / 旧孔系 bore)',
               'isolation': str(WORK).replace('\\', '/'),
               'note': '未修改 run inputs 或工程源；旧甲板在审阅 _work 隔离目录重建并导出 STEP 后重新 import_step 读回'},
           'expected_broken': [{'deck': dk, 'x': 150, 'y': oy} for dk in ('lower', 'upper') for oy in (-89, 89)],
           'decks': {}, 'failures': []}

    for deck, z in [('lower', -99.65), ('upper', -10)]:
        d = build_legacy_deck()
        f = WORK / f'legacy_{deck}_equipment_deck.step'
        export_step(d, str(f))
        s = import_step(str(f))  # 与正检同口径：导出后重新读回
        # 注意：旧甲板按局部坐标（z=0 中心）重建导出，判定在同一局部系进行，与 z 世界偏移无关
        holes = []
        broken = 0
        for x in [-150, -50, 50, 150]:
            for y in [-89, 89]:
                closed, axis_void, out_pts = closed_hole(s, x, y, 0.0)
                fullness = cyl_face_fullness_at(s, x, y)
                is_broken = (not closed) or (fullness is None) or (fullness < 0.999)
                holes.append({'x': x, 'y': y, 'closed': closed, 'axis_void': axis_void,
                              'cyl_fullness': fullness, 'ring_points_outside_count': len(out_pts),
                              'ring_points_outside_sample': out_pts[:6], 'broken_edge_detected': is_broken})
                broken += is_broken
        rep['decks'][deck] = {'step_file': f.name, 'step_sha256': hashlib.sha256(f.read_bytes()).hexdigest(),
                              'broken_edge_count': broken, 'holes': holes}
        if broken != 2:
            rep['failures'].append(f'{deck}: 检出破边 {broken} != 预期 2（负控失效）')
        for h in holes:
            expect_broken = (h['x'] == 150)
            if h['broken_edge_detected'] != expect_broken:
                rep['failures'].append(f"{deck} 孔({h['x']},{h['y']}): 检出={h['broken_edge_detected']} 预期={expect_broken}")
    total_broken = sum(d['broken_edge_count'] for d in rep['decks'].values())
    rep['total_broken_edges_detected'] = total_broken
    rep['expected_total'] = 4
    rep['detected'] = (total_broken == 4 and not rep['failures'])
    # 破边机理复核：孔 (150,±89) r1.7 右缘 151.7 > 避口内壁 151.5 → 连通 0.2mm
    rep['mechanism_check'] = {'hole_right_edge_mm': 150 + 1.7, 'notch_inner_wall_mm': 160 - 8.5,
                              'analytic_overlap_mm': round(150 + 1.7 - (160 - 8.5), 6)}
    rep['verdict'] = 'NC1_PASS_old_broken_edges_detected' if rep['detected'] else 'NC1_FAIL_detector_blind_to_legacy_defect'
    rep['elapsed_s'] = round(time.time() - t0, 3)
    out = REVIEW / 'evidence' / 'review_nc1_legacy_broken_edge.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    wlf(out, json.dumps(rep, ensure_ascii=False, indent=2) + '\n'); sidecar(out)
    print('NC1', rep['verdict'], 'broken detected:', total_broken, '/4', 'elapsed', rep['elapsed_s'])
    for x in rep['failures'][:10]:
        print(' FAIL', x)

if __name__ == '__main__':
    main()
