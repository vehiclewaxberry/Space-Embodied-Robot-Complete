# -*- coding: utf-8 -*-
"""WP03 R01 验收6 独立复验 - 负控三：垫圈外径超限 / 工具包络与邻近件干涉可检出。

NC3a 垫圈超限：重建 lower_deck_fastener_-1_-150 包络（几何逐义复刻工程源 deck_fastening_parts
紧固件段），将螺母侧垫圈由 Ø6 改为 Ø8（超过 design_parameters.json deck_angle_fastener_candidate
.washer_outer_diameter_max_mm=6 限值）。用与任务1同源的包络检查（最大圆柱面 OD <= 限值）判定：
预期 max_OD=8 > 6 -> 违规被检出。

NC3b 工具冲突：对真实读回的 upper_deck_fastener_-1_-50 构造工具扫掠（Ø8 x 150mm，沿 +Z，
与构建者 acc5 具名集合定义一致的解析圆柱），放置一个 CO_PRESENT 变异邻件（盒体横穿工具路径），
用审阅者自写的扫掠-邻件距离判定（BRepExtrema < 0.5mm 且 CO_PRESENT -> VIOLATION）：
预期 VIOLATION 被检出。另复核真实场景中 hold_crossbeam_1 与该工具路径 d=0.0 的命中可被复现
（该真实命中属 OVERHEAD_RETENTION 装序约束，非本负控违规）。
"""
import sys, json, math, hashlib, time
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401
from build123d import Box, Cylinder, Location, export_step
from cadgen.step_scene import import_step
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder
from OCP.BRepExtrema import BRepExtrema_DistShapeShape

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r01_deck_fastening_20260917'
REVIEW = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r01_deck_fastening_20260917_review'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
WORK = REVIEW / '_work' / 'nc3_washer_tool'
EXP = RUN / 'exports'

P = json.loads((ENG / 'design_parameters.json').read_text(encoding='utf-8'))
R01 = P['deck_fastening_r01']
WASHER_OD_LIMIT = R01['deck_angle_fastener_candidate']['washer_outer_diameter_max_mm']

def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))

def sidecar(p):
    h = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    wlf(str(p) + '.sha256', h + '  ' + Path(p).name + '\n')
    return h

def cyl(d, h, c=(0, 0, 0)):
    return Cylinder(d / 2, h).moved(Location(tuple(c)))

def box(size, c=(0, 0, 0)):
    return Box(*size).moved(Location(tuple(c)))

def dist(a, b):
    e = BRepExtrema_DistShapeShape(a.wrapped, b.wrapped)
    return e.Value() if e.IsDone() else None

def envelope_report(shape):
    radii = []
    for f in shape.faces():
        ad = BRepAdaptor_Surface(f.wrapped)
        if ad.GetType() == GeomAbs_Cylinder:
            radii.append(ad.Cylinder().Radius())
    max_od = 2 * max(radii)
    return {'max_cyl_OD_mm': round(max_od, 6),
            'washer_od_limit_mm': WASHER_OD_LIMIT,
            'within_limit': max_od <= WASHER_OD_LIMIT + 1e-6,
            'shank_R1.5_present': any(abs(r - 1.5) < 0.02 for r in radii),
            'head_R2.75_present': any(abs(r - 2.75) < 0.02 for r in radii)}

def deck_fastener_envelope(x, y, zt, nut_washer_od=6):
    """逐义复刻 deck_fastening_parts 甲板紧固件包络；nut_washer_od 为变异注入点。"""
    return (cyl(3, 12, (x, y, zt - 6)) + cyl(6, 0.5, (x, y, zt + 0.25)) +
            cyl(5.5, 3, (x, y, zt + 2)) + cyl(nut_washer_od, 0.5, (x, y, zt - 6.25)) +
            cyl(6, 2.4, (x, y, zt - 7.7)))

def main():
    t0 = time.time()
    WORK.mkdir(parents=True, exist_ok=True)
    failures = []

    # ---------- NC3a 垫圈 Ø8 超限 ----------
    z = -99.65; zt = z + 1.5
    mut = deck_fastener_envelope(-150, -92.65, zt, nut_washer_od=8)
    fa = WORK / 'mutant_fastener_washer_OD8.step'
    export_step(mut, str(fa))
    s_mut = import_step(str(fa))
    rep_mut = envelope_report(s_mut)
    nc3a_detected = (rep_mut['max_cyl_OD_mm'] == 8.0) and (not rep_mut['within_limit'])
    # 对照：真实读回的同名紧固件应通过同一限值检查（防误报）
    s_real = import_step(str(EXP / 'lower_deck_fastener_-1_-150.step'))
    rep_real = envelope_report(s_real)
    if not rep_real['within_limit']:
        failures.append(f"真实紧固件误报超限: {rep_real}")

    # ---------- NC3b 工具包络 vs 邻近件干涉 ----------
    # 真实工具扫掠：upper_deck_fastener_-1_-50，z=-10, zt=-8.5
    x, y = -50, -92.65
    ztu = -10 + 1.5
    tool = cyl(8, 150, (x, y, ztu + 3.5 + 75))  # 与 acc5 具名集合定义一致的解析工具圆柱
    # 变异邻件：CO_PRESENT 盒体横穿工具路径
    mutant_neighbor = box((10, 30, 30), (x, y, 60))
    d_mut = dist(tool, mutant_neighbor)
    violation_emitted = d_mut is not None and d_mut < 0.5
    # 复核真实 OVERHEAD_RETENTION 命中可复现（hold_crossbeam_1，装序约束非违规）
    station_x = P['retention']['station_x_mm']
    crossbeam = box((22, 202.3, 10), (station_x[1], 0, 101.15))
    roof_lug = box((22, 14, 12), (station_x[1], -94.15, 112.15))
    d_beam = dist(tool, crossbeam)
    d_lug = dist(tool, roof_lug)
    real_hit_reproduced = d_beam is not None and d_beam < 0.5
    nc3b_detected = violation_emitted
    if not nc3b_detected:
        failures.append(f'变异工具冲突未检出: d={d_mut}')

    rep = {
        'review': 'r01_deck_fastening_20260917_review',
        'check': 'ACC6_NC3_washer_oversize_or_tool_conflict_detectable',
        'nc3a_washer_oversize': {
            'mutation': 'lower_deck_fastener_-1_-150 螺母侧垫圈 Ø6 -> Ø8（隔离重建，未改原文件）',
            'step_file': fa.name, 'step_sha256': hashlib.sha256(fa.read_bytes()).hexdigest(),
            'limit_source': 'design_parameters.json deck_angle_fastener_candidate.washer_outer_diameter_max_mm',
            'mutant_measurement': rep_mut, 'real_fastener_control': rep_real,
            'violation_detected': nc3a_detected},
        'nc3b_tool_conflict': {
            'tool_sweep': {'fastener': 'upper_deck_fastener_-1_-50', 'diameter_mm': 8, 'length_mm': 150,
                           'axis_S': [0, 0, 1], 'z_span_mm': [ztu + 3.5, ztu + 3.5 + 150]},
            'mutant_neighbor': {'box_mm': [10, 30, 30], 'center_S_mm': [x, y, 60], 'stage': 'CO_PRESENT'},
            'distance_to_mutant_mm': None if d_mut is None else round(d_mut, 6),
            'violation_rule': 'BRepExtrema 距离 < 0.5mm 且 CO_PRESENT -> VIOLATION',
            'violation_detected': nc3b_detected,
            'real_overhead_hit_recheck': {
                'hold_crossbeam_1_distance_mm': None if d_beam is None else round(d_beam, 6),
                'hold_roof_lug_1_-94.15_distance_mm': None if d_lug is None else round(d_lug, 6),
                'stage': 'OVERHEAD_RETENTION（真实场景为装序约束记录，非 VIOLATION）',
                'hit_reproduced': real_hit_reproduced}},
        'failures': failures}
    ok = nc3a_detected and nc3b_detected and not failures
    rep['detected'] = ok
    rep['verdict'] = 'NC3_PASS_washer_oversize_and_tool_conflict_detected' if ok else 'NC3_FAIL_detector_blind'
    rep['elapsed_s'] = round(time.time() - t0, 3)
    out = REVIEW / 'evidence' / 'review_nc3_washer_tool_conflict.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    wlf(out, json.dumps(rep, ensure_ascii=False, indent=2) + '\n'); sidecar(out)
    print('NC3', rep['verdict'], 'washer_OD8 detected:', nc3a_detected,
          '| tool conflict detected:', nc3b_detected, f'(d={d_mut:.4f})',
          '| real crossbeam d=', round(d_beam, 4), 'lug d=', round(d_lug, 4))
    for e in failures:
        print(' FAIL', e)

if __name__ == '__main__':
    main()
