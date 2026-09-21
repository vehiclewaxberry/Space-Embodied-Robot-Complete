# -*- coding: utf-8 -*-
"""WP03 R01 候选 V2 验收6 独立复验 - 任务2：V2 布尔口径干涉扫描 + V1 物证回放负控。

A) V2 无新干涉：对 V2 全部 32 包络做布尔口径干涉扫描（review_t5b 口径）——
   包络 ∩ 被夹持结构件（交集体积须 ~0）+ 包络 vs CO_PRESENT 具名邻件（BRepExtrema <0.5mm 记干涉）。
B) V1 物证回放负控（关键）：用 exports/v1_superseded/ 的 16 件 V1 缺陷 STEP，
   分别经 (i) 审阅者自写布尔检查 与 (ii) 构建者修复后检查链 scripts/s06_acc5_paths.py
   第 1b 节的 common_volume 实现（import 其模块直接调用其函数）对当前剪力腹板回放，
   两者必须都对每件报 9.597566 mm3 级违规——证明修复后的检查链能检出原缺陷。
"""
import sys, json, math, hashlib, time, importlib.util
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401
from build123d import Box, Location
from cadgen.step_scene import import_step
from OCP.BRepExtrema import BRepExtrema_DistShapeShape

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r01_deck_fastening_20260917'
REVIEW = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r01_deck_fastening_20260917_review'
EXP = RUN / 'exports'
V1 = EXP / 'v1_superseded'

def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))

def sidecar(p):
    h = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    wlf(str(p) + '.sha256', h + '  ' + Path(p).name + '\n')
    return h

def box(size, c=(0, 0, 0)):
    return Box(*size).moved(Location(tuple(c)))

def common_volume(a, b):
    c = a & b
    return 0.0 if c is None else c.volume

def dist(a, b):
    e = BRepExtrema_DistShapeShape(a.wrapped, b.wrapped)
    return e.Value() if e.IsDone() else None

def bbox(s):
    bb = s.bounding_box()
    return (bb.min.X, bb.min.Y, bb.min.Z), (bb.max.X, bb.max.Y, bb.max.Z)

def bbox_gap(a, b):
    (a0, a1), (b0, b1) = bbox(a), bbox(b)
    d2 = 0.0
    for i in range(3):
        lo = max(a0[i], b0[i]); hi = min(a1[i], b1[i])
        if lo > hi:
            d2 += (lo - hi) ** 2
    return math.sqrt(d2)

def builder_common_volume(a, b):
    """逐行复刻构建者 s06_acc5_paths.py 第 1b 节 common_volume（源 L157-170，main() 内嵌函数，
    无法 import 直接调用；此处按源码语义一字不差复制操作序列：intersect -> BRepGProp 体积求和）。"""
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

def main():
    t0 = time.time()
    m2 = json.loads((EXP / 'EXPORT_MANIFEST_V2.json').read_text(encoding='utf-8'))
    shapes = {p['name']: import_step(str(EXP / p['file'])) for p in m2['parts']}
    struct = {n: shapes[n] for n in shapes
              if n.endswith('equipment_deck') or '_deck_angle_' in n or n.startswith('shear_web')}
    fasteners = {n: shapes[n] for n in shapes if 'fastener' in n}

    neighbors = {}
    for x in (20, 160):
        for y in (-94.15, 94.15):
            neighbors[f'RB_pillar_{x}_{y}'] = box((14, 14, 193.3), (x, y, -1.5))
            neighbors[f'RB_lower_spacer_{x}_{y}'] = box((14, 14, 3), (x, y, -99.65))
    for side in (-1, 1):
        for x in [-150, -90, -30, 30, 90, 150]:
            for z in [-94, 94]:
                neighbors[f'shear_clip_{side}_{x}_{z}'] = box((16, 6, 14.3), (x, side * 106.15, z))
        for x in [-150, 0, 150]:
            for z in [-75, 75]:
                neighbors[f'cover_mount_{side}_{x}_{z}'] = box((12, 8.5, 12), (x, side * 107.4, z))

    rep = {'review': 'r01_deck_fastening_20260917_review', 'candidate_version': 'V2',
           'check': 'ACC6_V2_T2_boolean_interference_scan_and_v1_replay',
           'failures': []}

    # A) V2 布尔口径干涉扫描
    v2_viol = []
    per_fast = []
    for fn, fs in sorted(fasteners.items()):
        deck = 'lower' if fn.startswith('lower') else 'upper'
        entry = {'fastener': fn, 'common_with_clamped': {}, 'nearest_neighbor': None,
                 'neighbor_min_distance_mm': None}
        for sn, ss in struct.items():
            if not (sn.startswith(deck) or sn.startswith('shear_web')):
                continue
            v = common_volume(fs, ss)
            if v > 1e-6:
                entry['common_with_clamped'][sn] = round(v, 6)
                v2_viol.append(f'{fn}: 包络与 {sn} 交集体积 {v:.6f} mm3')
        best = (None, 1e9)
        for nn, ns in neighbors.items():
            if bbox_gap(fs, ns) > 2.0:
                continue
            d = dist(fs, ns)
            if d is not None and d < best[1]:
                best = (nn, d)
        if best[0]:
            entry['nearest_neighbor'] = best[0]
            entry['neighbor_min_distance_mm'] = round(best[1], 6)
            if best[1] < 0.5:
                v2_viol.append(f'{fn}: 与 CO_PRESENT 邻件 {best[0]} 距离 {best[1]:.4f}')
        per_fast.append(entry)
    rep['v2_scan'] = {'fasteners_checked': len(per_fast), 'violations': v2_viol,
                      'per_fastener': per_fast, 'clean': not v2_viol}
    if v2_viol:
        rep['failures'].append(f'V2 新增未处置干涉: {v2_viol[:4]}')

    # B) V1 物证回放负控
    builder_fn_source = ('runs/r01_deck_fastening_20260917/scripts/s06_acc5_paths.py 第1b节 '
                         'common_volume（L157-170，main() 内嵌无法 import；按源码逐行复刻回放）')
    replay = []
    alarm_mine = 0; alarm_builder = 0
    webs = {side: struct[f'shear_web_{side}'] for side in (-1, 1)}
    for v1f in sorted(V1.glob('*.step')):
        fn = v1f.stem
        side = int(fn.split('_')[4])
        v1s = import_step(str(v1f))
        v_mine = common_volume(v1s, webs[side])
        v_builder = builder_common_volume(v1s, webs[side])
        ok_mine = v_mine > 1e-6
        ok_builder = v_builder > 1e-6
        alarm_mine += ok_mine
        alarm_builder += ok_builder
        replay.append({'fastener': fn, 'v1_step_sha256': hashlib.sha256(v1f.read_bytes()).hexdigest(),
                       'reviewer_boolean_common_mm3': round(v_mine, 9),
                       'builder_s06_1b_common_mm3': round(v_builder, 9),
                       'reviewer_alarm': bool(ok_mine), 'builder_1b_alarm': bool(ok_builder)})
    rep['v1_replay_negative_control'] = {
        'v1_artifacts': len(replay),
        'reviewer_alarms': alarm_mine,
        'builder_s06_1b_alarms': alarm_builder,
        'expected_per_fastener_mm3': 9.597566,
        'builder_check_chain_source': builder_fn_source,
        'builder_1b_threshold_mm3': 1e-6,
        'entries': replay,
        'both_chains_alarm_on_all': alarm_mine == 16 == alarm_builder}
    if not (alarm_mine == 16 == alarm_builder):
        rep['failures'].append(f'V1 回放负控失效: reviewer={alarm_mine}/16 builder_1b={alarm_builder}/16')

    rep['verdict'] = ('V2_SCAN_CLEAN_AND_V1_REPLAY_ALARMS' if not rep['failures']
                      else 'FAIL')
    rep['elapsed_s'] = round(time.time() - t0, 3)
    f = REVIEW / 'evidence' / 'review_v2_regression_negative_control.json'
    f.parent.mkdir(parents=True, exist_ok=True)
    wlf(f, json.dumps(rep, ensure_ascii=False, indent=2) + '\n'); sidecar(f)
    print('V2-T2', rep['verdict'], '| v2 viol:', len(v2_viol),
          '| v1 replay alarms: reviewer', alarm_mine, '/16, builder_1b', alarm_builder, '/16')
    for x in rep['failures'][:6]:
        print(' FAIL', x)

if __name__ == '__main__':
    main()
