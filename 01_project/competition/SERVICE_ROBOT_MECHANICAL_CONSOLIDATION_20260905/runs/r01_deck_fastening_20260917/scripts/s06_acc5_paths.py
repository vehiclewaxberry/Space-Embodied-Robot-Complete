# -*- coding: utf-8 -*-
"""R01 验收5（builder_self_check，非独立复验）：插入/工具/退出路径与具名检查集合。
性能策略：包围盒预过滤后再做 BRepExtrema 精确距离；穿透用内点采样分类（设计为面接触）。
1) 32 个紧固包络 vs 甲板/角材/剪力板：杆/头/垫/螺母内点采样不得落入结构材料（孔腔 0.2mm 径向间隙）；
2) 32 个紧固包络两两最小距离（bbox 预过滤）；
3) 插入/工具/退出扫掠（解析圆柱）对具名邻居集合的间隙：
   CO_PRESENT 冲突 -> VIOLATION；后装件（上甲板/设备/侧盖）-> SEQUENCE_CONSTRAINT。
标注：builder_self_check；独立复验（验收6）NOT_RUN 本轮。"""
import sys, json, math, hashlib, time
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401
from build123d import Box
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_IN

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r01_deck_fastening_20260917'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, str(ENG))
import spacecraft_model as sm
from spacecraft_model import box, cylinder

R01 = sm.P['deck_fastening_r01']
DPAT = R01['deck_hole_pattern']; WPAT = R01['angle_to_shear_web_hole_pattern']
DECKS = {'lower': -99.65, 'upper': -10}
SEGMENTS = [(-167, 11.5), (28.5, 151.5)]

def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))

def sidecar(p):
    h = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    wlf(str(p) + '.sha256', h + '  ' + Path(p).name + '\n')
    return h

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
            d2 += lo - hi
    return math.sqrt(d2) if d2 else 0.0

class Inside:
    def __init__(self, solids):
        self.solids = solids
    def __call__(self, x, y, z):
        p = gp_Pnt(x, y, z)
        for s in self.solids:
            cls = BRepClass3d_SolidClassifier(s.wrapped, p, 1e-9)
            if cls.State() == TopAbs_IN:
                return True
        return False

def main():
    t0 = time.time()
    parts = {p['name']: p for p in sm.deck_fastening_parts(sm.P)}
    struct = {n: p['shape'] for n, p in parts.items() if p['kind'] in ('DECK', 'ANGLE', 'WEB')}
    fasteners = {n: p['shape'] for n, p in parts.items() if p['kind'].startswith('FASTENER')}

    neighbors = {}
    for x in (20, 160):
        for y in (-94.15, 94.15):
            neighbors[f'RB_pillar_{x}_{y}'] = (box((14, 14, 193.3), (x, y, -1.5)), 'CO_PRESENT')
            neighbors[f'RB_lower_spacer_{x}_{y}'] = (box((14, 14, 3), (x, y, -99.65)), 'CO_PRESENT')
    for side in (-1, 1):
        for x in [-150, -90, -30, 30, 90, 150]:
            for z in [-94, 94]:
                neighbors[f'shear_clip_{side}_{x}_{z}'] = (box((16, 6, 14.3), (x, side*106.15, z)), 'CO_PRESENT')
        for x in [-150, 0, 150]:
            for z in [-75, 75]:
                neighbors[f'cover_mount_{side}_{x}_{z}'] = (box((12, 8.5, 12), (x, side*107.4, z)), 'CO_PRESENT')
        neighbors[f'access_cover_{side}'] = (box((344, 1.5, 180), (0, side*112.4, 0)), 'LATER_COVER')
    for eq in sm.P['equipment']:
        size = eq['size_mm']; c = eq['center_mm']
        neighbors[f"equipment_{eq['name']}"] = (box(tuple(size), tuple(c)), 'LATER_EQUIPMENT')
        base = c[2]-size[2]/2
        # 适配板随设备装入（票据方向：设备装入前完成甲板紧固）
        neighbors[f"adapter_{eq['name']}"] = (box((size[0]+8, size[1]+8, 2), (c[0], c[1], base+1)), 'LATER_EQUIPMENT')
    # 屋顶保持器横梁/耳座：与设备舱装序未冻结，按 OVERHEAD_RETENTION 记录装序约束
    for k, hx in enumerate(sm.P['retention']['station_x_mm']):
        neighbors[f'hold_crossbeam_{k}'] = (box((22, 202.3, 10), (hx, 0, 101.15)), 'OVERHEAD_RETENTION')
        for y in (-94.15, 94.15):
            neighbors[f'hold_roof_lug_{k}_{y}'] = (box((22, 14, 12), (hx, y, 112.15)), 'OVERHEAD_RETENTION')
    for deck, z in DECKS.items():
        neighbors[f'{deck}_equipment_deck'] = (struct[f'{deck}_equipment_deck'], 'CO_PRESENT')
        for side in (-1, 1):
            for k in (0, 1):
                neighbors[f'{deck}_deck_angle_{side}_{k}'] = (struct[f'{deck}_deck_angle_{side}_{k}'], 'CO_PRESENT')
            neighbors[f'shear_web_{side}'] = (struct[f'shear_web_{side}'], 'CO_PRESENT')

    report = {'run': 'r01_deck_fastening_20260917', 'check': 'ACC5_insertion_tool_exit_paths_named_set',
              'candidate_version': 'V2',
              'supersedes': 'evidence/acc5_builder_self_check.json (V1: 仅采样口径，对垫圈环形承压区有盲区 -> 审阅 FAIL；V2 起固化布尔交集口径 1b)',
              'identity': 'builder_self_check（解析包围体/轴线扫掠 + 布尔交集；独立复验 ACC6 不在本轮）',
              'units': 'mm', 'frame': 'S',
              'named_check_set': sorted(list(neighbors) + list(fasteners)),
              'fastener_penetration': [], 'fastener_pairwise': None,
              'tool_paths': [], 'violations': [], 'sequence_constraints': []}

    # 1) 穿透采样：每个紧固件沿轴在杆/螺母区采样表面点（r=1.5 杆面）与头/垫/螺母内点，不得落入结构材料
    for fn, fs in fasteners.items():
        deck = 'lower' if fn.startswith('lower') else 'upper'
        rel = Inside([struct[n] for n in struct if n.startswith(deck) or n.startswith('shear_web')])
        z = DECKS[deck]
        hits = 0; npts = 0
        if '_deck_fastener_' in fn:
            toks = fn.split('_')
            x = float(toks[-1]); side = int(toks[-2]); y = side*92.65
            zt = z+1.5
            for zi in [zt-1.5, zt-3, zt-4.5, zt-6, zt-7.5, zt-9.5, zt-11.5]:  # 杆区
                for a in range(8):
                    ang = 2*math.pi*a/8
                    npts += 1
                    if rel(x+1.5*math.cos(ang), y+1.5*math.sin(ang), zi):
                        hits += 1
            for pt in [(x, y, zt+2), (x, y, zt+0.25), (x, y, zt-6.25), (x, y, zt-7.7)]:  # 头/垫/螺母轴心（材料外区）
                npts += 1
                if rel(*pt):
                    hits += 1
        else:
            # 名称: {deck}_angle_web_fastener_{side}_{k}_{x}
            side = int(fn.split('_')[4]); k = int(fn.split('_')[5]); x = float(fn.split('_')[6])
            wz = WPAT['Z_S_mm_by_deck'][deck]
            for yi in [side*97, side*98.15, side*99.65, side*101.15, side*102.5]:
                for a in range(8):
                    ang = 2*math.pi*a/8
                    npts += 1
                    if rel(x+1.5*math.cos(ang), yi, wz+1.5*math.sin(ang)):
                        hits += 1
            for pt in [(x, side*105.15, wz), (x, side*103.4, wz), (x, side*97.9, wz), (x, side*96.45, wz)]:
                npts += 1
                if rel(*pt):
                        hits += 1
        report['fastener_penetration'].append({'fastener': fn, 'sample_points': npts, 'points_inside_structure': hits})
        if hits:
            report['violations'].append(f'{fn}: {hits}/{npts} sample points inside structure (penetration)')

    # 1b) V2 固化口径（审阅 FAIL r01_deck_fastening_20260917_review 指出 V1 采样口径对垫圈环形承压区有盲区）：
    # 每个紧固包络与所有结构件 + 所有具名邻居做布尔交集，common 体积必须 = 0（容差 1e-6 mm3）。
    # 面接触（相切）在布尔意义下体积为 0；任何正体积即穿透 -> VIOLATION。
    report['fastener_boolean_common'] = []
    def common_volume(a, b):
        inter = a.intersect(b)
        if inter is None:
            return 0.0
        try:
            items = list(inter)
        except TypeError:
            items = [inter]
        v = 0.0
        from OCP.GProp import GProp_GProps
        from OCP.BRepGProp import BRepGProp
        for s in items:
            g = GProp_GProps(); BRepGProp.VolumeProperties_s(s.wrapped, g); v += g.Mass()
        return v
    for fn, fs in fasteners.items():
        total = 0.0; worst = (None, 0.0)
        for nn, (ns, stage) in neighbors.items():
            if stage != 'CO_PRESENT':
                continue
            if bbox_gap(fs, ns) > 0.0:
                continue
            v = common_volume(fs, ns)
            total += v
            if v > worst[1]:
                worst = (nn, v)
        report['fastener_boolean_common'].append(
            {'fastener': fn, 'common_volume_mm3': total, 'worst_neighbor': worst[0], 'worst_volume_mm3': worst[1]})
        if total > 1e-6:
            report['violations'].append(f'{fn}: boolean common volume {total:.6f} mm3 with {worst[0]} (penetration)')

    # 2) 两两最小距离（bbox 预过滤）
    fl = sorted(fasteners)
    best = (None, None, 1e9)
    for i in range(len(fl)):
        for j in range(i+1, len(fl)):
            if bbox_gap(fasteners[fl[i]], fasteners[fl[j]]) > 5:
                continue
            d = dist(fasteners[fl[i]], fasteners[fl[j]])
            if d is not None and d < best[2]:
                best = (fl[i], fl[j], d)
    report['fastener_pairwise'] = {'pair': [best[0], best[1]], 'min_distance_mm': round(best[2], 6)}
    if best[2] < 0.5:
        report['violations'].append(f'fastener pair {best[0]}/{best[1]} clearance {best[2]:.4f} mm')

    # 3) 工具/插入/退出扫掠
    def check_sweep(sweep, name, view):
        hits = []
        for nn, (ns, stage) in view.items():
            if bbox_gap(sweep, ns) > 1.0:
                continue
            d = dist(sweep, ns)
            if d is not None and d < 0.5:
                hits.append({'neighbor': nn, 'distance_mm': round(d, 4), 'stage': stage})
        report['tool_paths'].append({'sweep': name, 'hits': hits})
        for h in hits:
            if h['stage'] == 'CO_PRESENT':
                report['violations'].append(f"{name}: conflicts co-present {h['neighbor']} d={h['distance_mm']}")
            elif h['stage'] == 'OVERHEAD_RETENTION':
                report['sequence_constraints'].append(
                    f"{name}: overhead path crosses retention {h['neighbor']} (d={h['distance_mm']}) -> "
                    f"须在保持器横梁/耳座安装前紧固，或改用斜向/加长杆工具（装序未冻结，移交装配程序任务）")
            else:
                report['sequence_constraints'].append(
                    f"{name}: crosses later-installed {h['neighbor']} (d={h['distance_mm']}) -> 须先装该紧固件")

    # 装序假设（builder 假设，非冻结）：下舱 -> 上舱 -> 适配板/设备 -> 侧盖；保持器头顶件装序未冻结。
    for deck, z in DECKS.items():
        zt = z + 1.5
        later_deck = 'upper' if deck == 'lower' else None  # 仅下层作业时上层为后装；上层作业时下层已装(CO_PRESENT)
        for x in DPAT['X_S_mm']:
            for side in (-1, 1):
                y = side*92.65
                fid = f'{deck}_deck_fastener_{side}_{x}'
                ins = cylinder(6, 40+(zt+3.5)-(zt-8.9), (x, y, (zt-8.9+zt+3.5+40)/2))
                tool = cylinder(8, 150, (x, y, zt+3.5+75))
                nut_tool = cylinder(10, 60, (x, y, zt-8.9-30))
                kseg = 0 if x <= SEGMENTS[0][1] else 1
                skip_names = {fid, f'{deck}_equipment_deck', f'{deck}_deck_angle_{side}_{kseg}'}
                view = {n: v for n, v in neighbors.items() if n not in skip_names}
                if later_deck:
                    view[f'{later_deck}_equipment_deck'] = (struct[f'{later_deck}_equipment_deck'], 'LATER_DECK')
                    for os_ in (-1, 1):
                        for ok_ in (0, 1):
                            on = f'{later_deck}_deck_angle_{os_}_{ok_}'
                            view[on] = (struct[on], 'LATER_DECK')
                check_sweep(ins, f'insert/exit {fid}', view)
                check_sweep(tool, f'tool {fid}', view)
                check_sweep(nut_tool, f'nut-side wrench {fid}', view)
    for deck in DECKS:
        wz = WPAT['Z_S_mm_by_deck'][deck]
        for side in (-1, 1):
            for k, (a, b) in enumerate(SEGMENTS):
                for x in WPAT['X_S_mm_by_segment'][k]:
                    fid = f'{deck}_angle_web_fastener_{side}_{k}_{x}'
                    # V2：头外移至 side*105.15（头外面 side*106.65），扫掠起点同步外移
                    ins = cylinder(6, 40+(106.65-95.25), (x, side*(95.25+(106.65-95.25+40)/2), wz), (0, 1, 0))
                    tool = cylinder(8, 150, (x, side*(106.65+75), wz), (0, 1, 0))
                    skip_names = {fid, f'shear_web_{side}', f'{deck}_deck_angle_{side}_{k}'}
                    view = {n: v for n, v in neighbors.items() if n not in skip_names}
                    check_sweep(ins, f'insert/exit {fid}', view)
                    check_sweep(tool, f'tool {fid}', view)

    report['verdict'] = 'PASS_BUILDER_SELF_CHECK' if not report['violations'] else 'FAIL'
    report['assembly_order_assumption'] = ('BUILDER_ASSUMPTION_NOT_FROZEN：下舱->上舱->适配板/设备->侧盖；'
                                           '保持器头顶件装序未冻结单列；适配板随设备（票据方向"设备装入前装配"）。')
    report['note'] = ('SEQUENCE_CONSTRAINT 为装序约束记录（与票据方向一致：设备装入前、侧盖安装前），不构成 VIOLATION；'
                      '插入/退出共用同一扫掠体（互为逆路径）；距离 <0.5mm 的扫掠—邻居接近全部显式记录；'
                      '独立复验（验收6：旧破边检出、缺对偶/错轴线负控、垫圈或工具冲突负控）NOT_RUN 本轮，留待审阅者。')
    report['elapsed_s'] = round(time.time()-t0, 3)
    f = RUN / 'evidence' / 'acc5_builder_self_check_v2.json'
    wlf(f, json.dumps(report, ensure_ascii=False, indent=2) + '\n'); sidecar(f)
    print('ACC5', report['verdict'], 'violations:', len(report['violations']),
          'sequence_constraints:', len(report['sequence_constraints']),
          'named_set:', len(report['named_check_set']))
    print('fastener pairwise min mm:', round(best[2], 4), best[0], '/', best[1])
    print('penetration sample hits total:', sum(p['points_inside_structure'] for p in report['fastener_penetration']))
    for v in report['violations'][:10]:
        print(' VIOL', v)
    import collections
    c = collections.Counter(s.split(':')[1].split(' crosses ')[1].split(' (')[0] for s in report['sequence_constraints'])
    for k, v in c.items():
        print(' SEQ', k, 'x', v)

if __name__ == '__main__':
    main()
