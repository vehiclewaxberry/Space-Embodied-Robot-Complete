# -*- coding: utf-8 -*-
"""R01 验收2 + 交付物4：
- 两层连接（甲板—角材 16 组；角材—剪力板 16 组）基准/孔轴/方向/单位/夹层一致性机器核对；
- 输出 32 组对偶孔表（JSON+CSV）与 32 行紧固叠层表（JSON+CSV），全部带 .sha256 边车。
读回工具：build123d.import_step；坐标：S 系世界坐标，单位 mm。"""
import sys, json, math, hashlib, time, io, csv
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
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r01_deck_fastening_20260917'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, str(ENG))
import spacecraft_model as sm

R01 = sm.P['deck_fastening_r01']
DPAT = R01['deck_hole_pattern']; WPAT = R01['angle_to_shear_web_hole_pattern']
DFA = R01['deck_angle_fastener_candidate']; WFA = R01['angle_web_fastener_candidate']
DECKS = {'lower': -99.65, 'upper': -10}
SEGMENTS = [(-167, 11.5), (28.5, 151.5)]
R_HOLE = DPAT['diameter_mm'] / 2

def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))

def sidecar(p):
    h = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    wlf(str(p) + '.sha256', h + '  ' + Path(p).name + '\n')
    return h

def cyl_axes(shape):
    out = []
    for f in shape.faces():
        ad = BRepAdaptor_Surface(f.wrapped)
        if ad.GetType() == GeomAbs_Cylinder and abs(ad.Cylinder().Radius() - R_HOLE) < 1e-6:
            a = ad.Cylinder().Axis(); l = a.Location(); d = a.Direction()
            out.append(((l.X(), l.Y(), l.Z()), (d.X(), d.Y(), d.Z())))
    return out

def find_axis(axes, point, direction, tol=1e-6):
    """在孔轴列表中查找过 point 附近、沿 direction 的轴。direction 为单位向量。"""
    for l, d in axes:
        if abs(abs(d[0]*direction[0]+d[1]*direction[1]+d[2]*direction[2]) - 1) > 1e-6:
            continue
        # point 到直线距离
        v = (point[0]-l[0], point[1]-l[1], point[2]-l[2])
        cx = (v[1]*d[2]-v[2]*d[1], v[2]*d[0]-v[0]*d[2], v[0]*d[1]-v[1]*d[0])
        if math.sqrt(sum(c*c for c in cx)) < tol:
            return (l, d)
    return None

def axis_deviation(a, b):
    (l1, d1), (l2, d2) = a, b
    cross = (d1[1]*d2[2]-d1[2]*d2[1], d1[2]*d2[0]-d1[0]*d2[2], d1[0]*d2[1]-d1[1]*d2[0])
    par = math.sqrt(sum(c*c for c in cross))
    v = (l2[0]-l1[0], l2[1]-l1[1], l2[2]-l1[2])
    cx = (v[1]*d1[2]-v[2]*d1[1], v[2]*d1[0]-v[0]*d1[2], v[0]*d1[1]-v[1]*d1[0])
    return par, math.sqrt(sum(c*c for c in cx))

def inside(solid, x, y, z):
    cls = BRepClass3d_SolidClassifier(solid.wrapped, gp_Pnt(x, y, z), 1e-9)
    return cls.State() == TopAbs_IN

def stackup(solids_by_part, origin, direction, t_min, t_max, offset=(0, 0, 0), step=0.005):
    """沿轴采样（origin 加 offset 径向偏置，避开孔腔），输出 [{part, t_from, t_to, thickness_mm}]。"""
    intervals = []
    for name, solid in solids_by_part.items():
        t = t_min; start = None
        while t <= t_max + 1e-12:
            p = (origin[0]+offset[0]+direction[0]*t, origin[1]+offset[1]+direction[1]*t, origin[2]+offset[2]+direction[2]*t)
            ins = inside(solid, *p)
            if ins and start is None:
                start = t
            if not ins and start is not None:
                intervals.append({'part': name, 't_from_mm': round(start, 4), 't_to_mm': round(t, 4),
                                  'thickness_mm': round(t-start, 4)})
                start = None
            t += step
        if start is not None:
            intervals.append({'part': name, 't_from_mm': round(start, 4), 't_to_mm': round(t_max, 4),
                              'thickness_mm': round(t_max-start, 4)})
    intervals.sort(key=lambda r: r['t_from_mm'])
    return intervals

def main():
    t0 = time.time()
    ev = RUN / 'evidence'
    parts = {p['name']: p for p in sm.deck_fastening_parts(sm.P)}
    shapes, solids, axes = {}, {}, {}
    for name, p in parts.items():
        if p['kind'] in ('DECK', 'ANGLE', 'WEB'):
            shapes[name] = import_step(str(RUN / 'exports' / (name + '.step')))
            solids[name] = shapes[name].solids()[0]
            axes[name] = cyl_axes(shapes[name])

    groups = []
    failures = []
    # ---- 层 1：甲板—角材 16 组 ----
    for deck, z in DECKS.items():
        dname = f'{deck}_equipment_deck'
        for side in (-1, 1):
            y = side * 92.65
            for x in DPAT['X_S_mm']:
                k = 0 if x <= SEGMENTS[0][1] else 1
                aname = f'{deck}_deck_angle_{side}_{k}'
                a_deck = find_axis(axes[dname], (x, y, z), (0, 0, 1))
                a_ang = find_axis(axes[aname], (x, y, z), (0, 0, 1))
                gid = f'DA_{deck}_s{side:+d}_x{x}'
                if not a_deck or not a_ang:
                    failures.append(f'{gid}: missing dual hole face (deck={bool(a_deck)}, angle={bool(a_ang)})')
                    continue
                par, dist = axis_deviation(a_deck, a_ang)
                st = stackup({dname: solids[dname], aname: solids[aname]}, (x, y, 0), (0, 0, 1), z-6, z+3, offset=(2.0, 0.0, 0.0))
                thick = [i['thickness_mm'] for i in st]
                seq = [i['part'] for i in st]
                ok = (par < 1e-6 and dist < 1e-6 and seq == [aname, dname]
                      and abs(thick[0]-3.0) < 0.02 and abs(thick[1]-3.0) < 0.02)
                if not ok:
                    failures.append(f'{gid}: axis/stackup mismatch par={par} dist={dist} seq={seq} thick={thick}')
                groups.append({
                    'pair_id': gid, 'layer': 'deck_to_angle', 'A_part': dname, 'B_part': aname,
                    'hole_axis_S': [0, 0, 1], 'axis_point_S_mm': [x, y, 'through'],
                    'datum': 'S (bus_geometric_center)', 'units': 'mm',
                    'direction': DFA['direction'],
                    'diameter_mm': DPAT['diameter_mm'],
                    'stackup_sequence': st, 'nominal_grip_mm': DFA['nominal_grip_mm'],
                    'measured_grip_mm': round(sum(thick), 4),
                    'parallelism_deviation': par, 'coaxial_deviation_mm': dist,
                    'fastener_instance': f'{deck}_deck_fastener_{side}_{x}',
                    'fastener_candidate': 'M3x12_THREADLESS_ENVELOPE_NOT_SELECTED',
                    'consistency_ok': ok,
                })
    # ---- 层 2：角材—剪力板 16 组 ----
    for deck, z in DECKS.items():
        wz = WPAT['Z_S_mm_by_deck'][deck]
        for side in (-1, 1):
            wname = f'shear_web_{side}'
            for k, (a, b) in enumerate(SEGMENTS):
                aname = f'{deck}_deck_angle_{side}_{k}'
                for x in WPAT['X_S_mm_by_segment'][k]:
                    a_ang = find_axis(axes[aname], (x, side*99.65, wz), (0, 1, 0))
                    a_web = find_axis(axes[wname], (x, side*102.15, wz), (0, 1, 0))
                    gid = f'AW_{deck}_s{side:+d}_seg{k}_x{x}'
                    if not a_ang or not a_web:
                        failures.append(f'{gid}: missing dual hole face (angle={bool(a_ang)}, web={bool(a_web)})')
                        continue
                    par, dist = axis_deviation(a_ang, a_web)
                    st = stackup({aname: solids[aname], wname: solids[wname]},
                                 (x, 0, wz), (0, side, 0), 95, 105, offset=(0.0, 0.0, 2.0))
                    thick = [i['thickness_mm'] for i in st]
                    seq = [i['part'] for i in st]
                    ok = (par < 1e-6 and dist < 1e-6 and seq == [aname, wname]
                          and abs(thick[0]-3.0) < 0.02 and abs(thick[1]-2.0) < 0.02)
                    if not ok:
                        failures.append(f'{gid}: axis/stackup mismatch par={par} dist={dist} seq={seq} thick={thick}')
                    groups.append({
                        'pair_id': gid, 'layer': 'angle_to_shear_web', 'A_part': aname, 'B_part': wname,
                        'hole_axis_S': [0, 1, 0], 'axis_point_S_mm': [x, 'through', wz],
                        'datum': 'S (bus_geometric_center)', 'units': 'mm',
                        'direction': WFA['direction'],
                        'diameter_mm': WPAT['diameter_mm'],
                        'stackup_sequence': st, 'nominal_grip_mm': WFA['nominal_grip_mm'],
                        'measured_grip_mm': round(sum(thick), 4),
                        'parallelism_deviation': par, 'coaxial_deviation_mm': dist,
                        'fastener_instance': f'{deck}_angle_web_fastener_{side}_{k}_{x}',
                        'fastener_candidate': 'M3x10_THREADLESS_ENVELOPE_NOT_SELECTED',
                        'consistency_ok': ok,
                    })
    # ---- 紧固叠层表（32 行）----
    stacks = []
    for g in groups:
        fa = DFA if g['layer'] == 'deck_to_angle' else WFA
        stacks.append({
            'fastener_instance': g['fastener_instance'], 'pair_id': g['pair_id'],
            'layer': g['layer'],
            'stack_from_head': ['head_D5.5x3', 'washer_D6x0.5_maxOD6',
                                f"grip_{fa['nominal_grip_mm']}mm(" + '+'.join(
                                    f"{i['part']}:{i['thickness_mm']}" for i in g['stackup_sequence']) + ')',
                                'washer_D6x0.5_maxOD6', 'nut_envelope_D6x2.4'],
            'thread_candidate': fa['thread'], 'underhead_length_mm': fa['underhead_length_mm'],
            'nominal_grip_mm': fa['nominal_grip_mm'],
            'head_diameter_mm': fa['head_diameter_mm'],
            'washer_outer_diameter_max_mm': fa['washer_outer_diameter_max_mm'],
            'direction': fa['direction'],
            'material_grade': 'UNKNOWN', 'effective_thread_engagement': 'UNKNOWN',
            'preload': 'UNKNOWN', 'locking': 'UNKNOWN',
            'identity': 'CANDIDATE_NOMINAL_GEOMETRY_NOT_SELECTED_HARDWARE',
        })
    ok_count = sum(1 for g in groups if g['consistency_ok'])
    acc2 = {'run': 'r01_deck_fastening_20260917', 'check': 'ACC2_dual_axis_datum_direction_units_stackup_consistency',
            'readback_tool': 'build123d.import_step', 'frame': 'S', 'units': 'mm',
            'groups_total': len(groups), 'groups_ok': ok_count,
            'tolerance': {'coaxial_mm': 1e-6, 'parallelism': 1e-6, 'thickness_mm': 0.02},
            'failures': failures,
            'verdict': 'PASS' if len(groups) == 32 and ok_count == 32 and not failures else 'FAIL',
            'elapsed_s': round(time.time()-t0, 3)}
    f2 = ev / 'acc2_connection_consistency.json'
    wlf(f2, json.dumps(acc2, ensure_ascii=False, indent=2) + '\n'); sidecar(f2)
    # 对偶孔表
    table = {'run': 'r01_deck_fastening_20260917', 'table': 'R01_dual_hole_pairs_32',
             'identity': 'CANDIDATE_NOMINAL_GEOMETRY; material/grade/preload/locking UNKNOWN',
             'row_count': len(groups), 'rows': groups}
    f3 = ev / 'r01_dual_hole_pairs_32.json'
    wlf(f3, json.dumps(table, ensure_ascii=False, indent=2) + '\n'); sidecar(f3)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow(['pair_id', 'layer', 'A_part', 'B_part', 'hole_axis_S', 'axis_point_S_mm',
                'datum', 'units', 'diameter_mm', 'stackup_sequence_mm', 'nominal_grip_mm',
                'measured_grip_mm', 'coaxial_deviation_mm', 'parallelism_deviation',
                'fastener_instance', 'fastener_candidate', 'direction', 'consistency_ok'])
    for g in groups:
        w.writerow([g['pair_id'], g['layer'], g['A_part'], g['B_part'],
                    '/'.join(map(str, g['hole_axis_S'])), json.dumps(g['axis_point_S_mm']),
                    g['datum'], g['units'], g['diameter_mm'],
                    ' + '.join(f"{i['part']}:{i['thickness_mm']}" for i in g['stackup_sequence']),
                    g['nominal_grip_mm'], g['measured_grip_mm'],
                    g['coaxial_deviation_mm'], g['parallelism_deviation'],
                    g['fastener_instance'], g['fastener_candidate'], g['direction'], g['consistency_ok']])
    f4 = ev / 'r01_dual_hole_pairs_32.csv'
    wlf(f4, buf.getvalue()); sidecar(f4)
    f5 = ev / 'r01_fastener_stacks_32.json'
    wlf(f5, json.dumps({'run': 'r01_deck_fastening_20260917', 'table': 'R01_fastener_stacks_32',
                        'identity': 'CANDIDATE_NOMINAL_GEOMETRY_NOT_SELECTED_HARDWARE; UNKNOWN 项禁止零填',
                        'row_count': len(stacks), 'rows': stacks}, ensure_ascii=False, indent=2) + '\n'); sidecar(f5)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow(['fastener_instance', 'pair_id', 'layer', 'thread_candidate', 'underhead_length_mm',
                'nominal_grip_mm', 'head_diameter_mm', 'washer_outer_diameter_max_mm',
                'stack_from_head', 'direction', 'material_grade', 'effective_thread_engagement',
                'preload', 'locking', 'identity'])
    for s in stacks:
        w.writerow([s['fastener_instance'], s['pair_id'], s['layer'], s['thread_candidate'],
                    s['underhead_length_mm'], s['nominal_grip_mm'], s['head_diameter_mm'],
                    s['washer_outer_diameter_max_mm'], ' > '.join(s['stack_from_head']), s['direction'],
                    s['material_grade'], s['effective_thread_engagement'], s['preload'], s['locking'], s['identity']])
    f6 = ev / 'r01_fastener_stacks_32.csv'
    wlf(f6, buf.getvalue()); sidecar(f6)
    print('ACC2', acc2['verdict'], 'groups', ok_count, '/', len(groups))
    for f in failures[:8]:
        print(' FAIL', f)
    print('layers:', {l: sum(1 for g in groups if g['layer'] == l) for l in ('deck_to_angle', 'angle_to_shear_web')})

if __name__ == '__main__':
    main()
