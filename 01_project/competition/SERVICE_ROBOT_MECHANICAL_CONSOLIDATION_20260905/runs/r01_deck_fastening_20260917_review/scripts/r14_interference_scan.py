# -*- coding: utf-8 -*-
"""WP03 R01 验收6 独立复验 - 任务5：新候选未处置干涉独立扫描。

具名检查集合定义复用构建者 acc5（验收 6 任务书允许），但全部计算独立重算：
  - 结构件（2 甲板/8 角材/2 腹板）与 32 紧固件包络一律从 run exports/ 重新 import_step 读回；
  - 邻件（柱/隔套/剪力卡/盖板/设备/适配板/保持器）由审阅者自写代码按 design_parameters.json 解析重建；
  - 穿透：紧固件杆面环点 + 头/垫/螺母特征点 vs 结构实体分类器；
  - 两两间隙：紧固件包络两两 BRepExtrema 最小距离（bbox 预过滤）；
  - 工具/插入/退出扫掠：Ø6 插入、Ø8x150 工具、Ø10x60 螺母侧扳手（甲板件），Ø6/Ø8（腹板件），
    对具名邻件集合求距；CO_PRESENT 且 d<0.5 -> VIOLATION；后装/头顶保持器 -> SEQUENCE_CONSTRAINT。
"""
import sys, json, math, hashlib, time
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401
from build123d import Box, Cylinder, Location
from cadgen.step_scene import import_step
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_IN

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
HIT_MM = 0.5

def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))

def sidecar(p):
    h = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    wlf(str(p) + '.sha256', h + '  ' + Path(p).name + '\n')
    return h

def box(size, c=(0, 0, 0)):
    return Box(*size).moved(Location(tuple(c)))

def cylz(d, h, c):
    return Cylinder(d / 2, h).moved(Location(tuple(c)))

def cyly(d, h, c):
    from build123d import Plane
    return Cylinder(d / 2, h).moved(Plane(origin=tuple(c), z_dir=(0, 1, 0)).location)

def dist(a, b):
    e = BRepExtrema_DistShapeShape(a.wrapped, b.wrapped)
    return e.Value() if e.IsDone() else None

def bbox(s):
    b = s.bounding_box()
    return (b.min.X, b.min.Y, b.min.Z), (b.max.X, b.max.Y, b.max.Z)

def bbox_gap(a, b):
    (a0, a1), (b0, b1) = bbox(a), bbox(b)
    d2 = 0.0
    for i in range(3):
        lo = max(a0[i], b0[i]); hi = min(a1[i], b1[i])
        if lo > hi:
            d2 += (lo - hi) ** 2
    return math.sqrt(d2)

class Inside:
    def __init__(self, solids):
        self.solids = solids
    def __call__(self, x, y, z):
        p = gp_Pnt(x, y, z)
        for s in self.solids:
            if BRepClass3d_SolidClassifier(s.wrapped, p, 1e-9).State() == TopAbs_IN:
                return True
        return False

def main():
    t0 = time.time()
    manifest = json.loads((EXP / 'EXPORT_MANIFEST.json').read_text(encoding='utf-8'))
    names = [m['name'] for m in manifest['parts']]
    shapes = {n: import_step(str(EXP / f'{n}.step')) for n in names}
    struct = {n: shapes[n] for n in names
              if n.endswith('equipment_deck') or '_deck_angle_' in n or n.startswith('shear_web')}
    fasteners = {n: shapes[n] for n in names if 'fastener' in n}

    # 具名邻件集合（定义与 acc5 具名集合一致，独立重建）
    neighbors = {}
    for x in (20, 160):
        for y in (-94.15, 94.15):
            neighbors[f'RB_pillar_{x}_{y}'] = (box((14, 14, 193.3), (x, y, -1.5)), 'CO_PRESENT')
            neighbors[f'RB_lower_spacer_{x}_{y}'] = (box((14, 14, 3), (x, y, -99.65)), 'CO_PRESENT')
    for side in (-1, 1):
        for x in [-150, -90, -30, 30, 90, 150]:
            for z in [-94, 94]:
                neighbors[f'shear_clip_{side}_{x}_{z}'] = (box((16, 6, 14.3), (x, side * 106.15, z)), 'CO_PRESENT')
        for x in [-150, 0, 150]:
            for z in [-75, 75]:
                neighbors[f'cover_mount_{side}_{x}_{z}'] = (box((12, 8.5, 12), (x, side * 107.4, z)), 'CO_PRESENT')
        neighbors[f'access_cover_{side}'] = (box((344, 1.5, 180), (0, side * 112.4, 0)), 'LATER_COVER')
    for eq in P['equipment']:
        size = eq['size_mm']; c = eq['center_mm']
        neighbors[f"equipment_{eq['name']}"] = (box(tuple(size), tuple(c)), 'LATER_EQUIPMENT')
        neighbors[f"adapter_{eq['name']}"] = (box((size[0] + 8, size[1] + 8, 2),
                                                  (c[0], c[1], c[2] - size[2] / 2 + 1)), 'LATER_EQUIPMENT')
    for k, hx in enumerate(P['retention']['station_x_mm']):
        neighbors[f'hold_crossbeam_{k}'] = (box((22, 202.3, 10), (hx, 0, 101.15)), 'OVERHEAD_RETENTION')
        for y in (-94.15, 94.15):
            neighbors[f'hold_roof_lug_{k}_{y}'] = (box((22, 14, 12), (hx, y, 112.15)), 'OVERHEAD_RETENTION')
    for deck in DECKS:
        neighbors[f'{deck}_equipment_deck'] = (struct[f'{deck}_equipment_deck'], 'CO_PRESENT')
        for side in (-1, 1):
            for k in (0, 1):
                neighbors[f'{deck}_deck_angle_{side}_{k}'] = (struct[f'{deck}_deck_angle_{side}_{k}'], 'CO_PRESENT')
            neighbors[f'shear_web_{side}'] = (struct[f'shear_web_{side}'], 'CO_PRESENT')

    rep = {'review': 'r01_deck_fastening_20260917_review',
           'check': 'ACC6_T5_new_candidate_interference_independent_scan',
           'identity': 'INDEPENDENT_REVERIFY（具名集合定义复用 acc5，全部几何重读回/距离重算）',
           'units': 'mm', 'frame': 'S', 'hit_threshold_mm': HIT_MM,
           'named_check_set': sorted(list(neighbors) + list(fasteners)),
           'fastener_penetration': [], 'fastener_pairwise': None,
           'tool_paths': [], 'violations': [], 'sequence_constraints': []}

    # 1) 穿透采样
    for fn, fs in sorted(fasteners.items()):
        deck = 'lower' if fn.startswith('lower') else 'upper'
        rel = Inside([s for n, s in struct.items() if n.startswith(deck) or n.startswith('shear_web')])
        z = DECKS[deck]; zt = z + 1.5
        hits = 0; npts = 0
        if '_deck_fastener_' in fn:
            x = float(fn.split('_')[-1]); side = int(fn.split('_')[-2]); y = side * 92.65
            for zi in [zt - 1.5, zt - 3, zt - 4.5, zt - 6, zt - 7.5, zt - 9.5, zt - 11.5]:
                for a in range(8):
                    ang = 2 * math.pi * a / 8
                    npts += 1
                    if rel(x + 1.5 * math.cos(ang), y + 1.5 * math.sin(ang), zi):
                        hits += 1
            for pt in [(x, y, zt + 2), (x, y, zt + 0.25), (x, y, zt - 6.25), (x, y, zt - 7.7)]:
                npts += 1
                if rel(*pt):
                    hits += 1
        else:
            side = int(fn.split('_')[4]); x = float(fn.split('_')[6])
            wz = WPAT['Z_S_mm_by_deck'][deck]
            for yi in [side * 97, side * 98.15, side * 99.65, side * 101.15, side * 102.5]:
                for a in range(8):
                    ang = 2 * math.pi * a / 8
                    npts += 1
                    if rel(x + 1.5 * math.cos(ang), yi, wz + 1.5 * math.sin(ang)):
                        hits += 1
            for pt in [(x, side * 104.65, wz), (x, side * 102.9, wz), (x, side * 97.9, wz), (x, side * 96.45, wz)]:
                npts += 1
                if rel(*pt):
                    hits += 1
        rep['fastener_penetration'].append({'fastener': fn, 'sample_points': npts,
                                            'points_inside_structure': hits})
        if hits:
            rep['violations'].append(f'{fn}: {hits}/{npts} 采样点穿入结构材料')

    # 2) 两两最小距离
    fl = sorted(fasteners)
    best = (None, None, 1e9)
    for i in range(len(fl)):
        for j in range(i + 1, len(fl)):
            if bbox_gap(fasteners[fl[i]], fasteners[fl[j]]) > 5:
                continue
            d = dist(fasteners[fl[i]], fasteners[fl[j]])
            if d is not None and d < best[2]:
                best = (fl[i], fl[j], d)
    rep['fastener_pairwise'] = {'pair': [best[0], best[1]], 'min_distance_mm': round(best[2], 6)}
    if best[2] < HIT_MM:
        rep['violations'].append(f'紧固件两两间隙 {best[0]}/{best[1]} = {best[2]:.4f} < {HIT_MM}')

    # 3) 工具/插入/退出扫掠
    def check_sweep(sweep, name, view):
        hits = []
        for nn, (ns, stage) in view.items():
            if bbox_gap(sweep, ns) > 1.0:
                continue
            d = dist(sweep, ns)
            if d is not None and d < HIT_MM:
                hits.append({'neighbor': nn, 'distance_mm': round(d, 4), 'stage': stage})
        rep['tool_paths'].append({'sweep': name, 'hits': hits})
        for h in hits:
            if h['stage'] == 'CO_PRESENT':
                rep['violations'].append(f"{name}: 与同时在场件 {h['neighbor']} 干涉 d={h['distance_mm']}")
            elif h['stage'] == 'OVERHEAD_RETENTION':
                rep['sequence_constraints'].append(
                    f"{name}: overhead path crosses retention {h['neighbor']} (d={h['distance_mm']})")
            else:
                rep['sequence_constraints'].append(
                    f"{name}: crosses later-installed {h['neighbor']} (d={h['distance_mm']})")

    for deck, z in DECKS.items():
        zt = z + 1.5
        later_deck = 'upper' if deck == 'lower' else None
        for x in DPAT['X_S_mm']:
            for side in (-1, 1):
                y = side * 92.65
                fid = f'{deck}_deck_fastener_{side}_{x}'
                ins = cylz(6, 40 + (zt + 3.5) - (zt - 8.9), (x, y, (zt - 8.9 + zt + 3.5 + 40) / 2))
                tool = cylz(8, 150, (x, y, zt + 3.5 + 75))
                nut_tool = cylz(10, 60, (x, y, zt - 8.9 - 30))
                kseg = 0 if x <= SEGMENTS[0][1] else 1
                skip = {fid, f'{deck}_equipment_deck', f'{deck}_deck_angle_{side}_{kseg}'}
                view = {n: v for n, v in neighbors.items() if n not in skip}
                if later_deck:
                    view[f'{later_deck}_equipment_deck'] = (struct[f'{later_deck}_equipment_deck'], 'LATER_DECK')
                    for os_ in (-1, 1):
                        for ok_ in (0, 1):
                            view[f'{later_deck}_deck_angle_{os_}_{ok_}'] = (
                                struct[f'{later_deck}_deck_angle_{os_}_{ok_}'], 'LATER_DECK')
                check_sweep(ins, f'insert/exit {fid}', view)
                check_sweep(tool, f'tool {fid}', view)
                check_sweep(nut_tool, f'nut-side wrench {fid}', view)
    for deck in DECKS:
        wz = WPAT['Z_S_mm_by_deck'][deck]
        for side in (-1, 1):
            for k, (a, b) in enumerate(SEGMENTS):
                for x in WPAT['X_S_mm_by_segment'][k]:
                    fid = f'{deck}_angle_web_fastener_{side}_{k}_{x}'
                    ins = cyly(6, 40 + (106.15 - 95.25), (x, side * (95.25 + (106.15 - 95.25 + 40) / 2), wz))
                    tool = cyly(8, 150, (x, side * (106.15 + 75), wz))
                    skip = {fid, f'shear_web_{side}', f'{deck}_deck_angle_{side}_{k}'}
                    view = {n: v for n, v in neighbors.items() if n not in skip}
                    check_sweep(ins, f'insert/exit {fid}', view)
                    check_sweep(tool, f'tool {fid}', view)

    rep['named_check_set_size'] = len(rep['named_check_set'])
    rep['penetration_sample_hits_total'] = sum(p['points_inside_structure'] for p in rep['fastener_penetration'])
    rep['verdict'] = ('INDEPENDENT_SCAN_NO_UNRESOLVED_INTERFERENCE' if not rep['violations']
                      else 'INDEPENDENT_SCAN_VIOLATIONS_FOUND')
    rep['note'] = ('SEQUENCE_CONSTRAINT 为装序约束记录（后装件/头顶保持器，装序未冻结），不构成未处置干涉；'
                   '判定口径与构建者 acc5 相同但独立重算。')
    rep['elapsed_s'] = round(time.time() - t0, 3)
    f = REVIEW / 'evidence' / 'review_t5_interference_scan.json'
    f.parent.mkdir(parents=True, exist_ok=True)
    wlf(f, json.dumps(rep, ensure_ascii=False, indent=2) + '\n'); sidecar(f)
    print('T5', rep['verdict'], 'named_set', rep['named_check_set_size'],
          'violations', len(rep['violations']), 'seq', len(rep['sequence_constraints']),
          'pen_hits', rep['penetration_sample_hits_total'],
          'pair_min', rep['fastener_pairwise'], 'elapsed', rep['elapsed_s'])
    for v in rep['violations'][:10]:
        print(' VIOL', v)

if __name__ == '__main__':
    main()
