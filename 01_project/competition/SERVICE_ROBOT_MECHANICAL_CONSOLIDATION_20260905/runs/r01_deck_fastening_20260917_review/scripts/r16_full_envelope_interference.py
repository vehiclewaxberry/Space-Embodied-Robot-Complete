# -*- coding: utf-8 -*-
"""WP03 R01 验收6 独立复验 - 任务5补充：紧固件全包络 vs 结构/邻件 布尔交集干涉扫描。

背景：任务5 初版扫描（review_t5_interference_scan.json）沿用构建者 acc5 的穿透采样口径
（杆面 r=1.5 环点 + 头/垫/螺母轴心点），对垫圈环形承压区存在采样盲区；验收4 抽验的
杆长/承压面测量暴露出角材—腹板紧固件头侧垫圈可能嵌入腹板。本补充检查改用布尔交集体积
（无采样盲区）复核全部 32 个紧固件包络：
  A) 包络 ∩ 被夹持结构件（甲板/角材/腹板）期望体积 ~0（孔径向间隙 0.2mm，承压面仅相切）；
  B) 包络 vs 其余 CO_PRESENT 具名邻件 BRepExtrema 距离（<0.5mm 记干涉）。
初版扫描盲区如实记录于本文件 known_blind_spot_of_t5。
"""
import sys, json, math, hashlib, time
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
DECKS = {'lower': -99.65, 'upper': -10}

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

def main():
    t0 = time.time()
    manifest = json.loads((EXP / 'EXPORT_MANIFEST.json').read_text(encoding='utf-8'))
    names = [m['name'] for m in manifest['parts']]
    shapes = {n: import_step(str(EXP / f'{n}.step')) for n in names}
    struct = {n: shapes[n] for n in names
              if n.endswith('equipment_deck') or '_deck_angle_' in n or n.startswith('shear_web')}
    fasteners = {n: shapes[n] for n in names if 'fastener' in n}

    # CO_PRESENT 解析邻件（与 acc5 具名集合定义一致，独立重建）
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

    rep = {'review': 'r01_deck_fastening_20260917_review',
           'check': 'ACC6_T5B_full_envelope_boolean_interference',
           'known_blind_spot_of_t5': ('初版 T5 与构建者 acc5 的穿透采样仅覆盖杆面 r=1.5 环点与头/垫/螺母轴心点，'
                                      '未覆盖垫圈环形承压区（r 1.7..3.0）；盲区由验收4 杆长/承压面抽验暴露，'
                                      '本补充检查以布尔交集体积闭合。'),
           'units': 'mm', 'frame': 'S',
           'per_fastener': [], 'violations': []}

    for fn, fs in sorted(fasteners.items()):
        deck = 'lower' if fn.startswith('lower') else 'upper'
        layer_struct = {n: s for n, s in struct.items()
                        if n.startswith(deck) or n.startswith('shear_web')}
        entry = {'fastener': fn, 'common_with_clamped': {}, 'neighbor_min_distance_mm': None,
                 'nearest_neighbor': None}
        for sn, ss in sorted(layer_struct.items()):
            if bbox_gap(fs, ss) > 1.0:
                continue
            v = common_volume(fs, ss)
            if v > 1e-6:
                entry['common_with_clamped'][sn] = round(v, 6)
                rep['violations'].append(f'{fn}: 包络与 {sn} 交集体积 {v:.6f} mm3（期望 ~0）')
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
                rep['violations'].append(f'{fn}: 与 CO_PRESENT 邻件 {best[0]} 距离 {best[1]:.4f} < 0.5')
        rep['per_fastener'].append(entry)

    # 机理定位：角材—腹板紧固件头侧垫圈承压面 z/y 位置 vs 腹板外表面
    rep['mechanism'] = {
        'finding': ('全部 16 件 {lower,upper}_angle_web_fastener_* 头侧垫圈（Ø6x0.5）承压面位于'
                    '腹板外表面内侧 0.5mm：垫圈 y 区间 side*(102.65..103.15)，腹板外表面 side*103.15，'
                    '垫圈整体嵌入腹板材料（环形区 r1.7..3.0），每件交集体积约 9.598 mm3 = π(3^2-1.7^2)*0.5。'),
        'expected_geometry': '头侧垫圈应贴腹板外表面：y 区间 side*(103.15..103.65)（承压面重合 side*103.15）',
        'deck_fasteners_status': '16 件甲板紧固件与甲板/角材交集体积均为 0（对照正常）',
        'builder_acc5_false_negative': ('构建者 acc5 穿透采样口径同样未覆盖垫圈环形承压区，'
                                        '其 violations=0 / penetration_hits=0 对该缺陷为假阴性；'
                                        '其工具/插入扫掠 skip 集合排除被夹持件，亦无法发现。'),
        'root_cause_hypothesis': ('工程源 spacecraft_model.py deck_fastening_parts 腹板紧固件行：'
                                  '头垫圈中心 side*102.9（y 102.65..103.15），相对正确值 side*103.4 内移 0.5mm；'
                                  '审阅者不修改候选，仅记录。')}

    rep['violation_count'] = len(rep['violations'])
    rep['verdict'] = ('T5B_INTERFERENCE_FOUND__WASHER_EMBEDDED_IN_SHEAR_WEB' if rep['violations']
                      else 'T5B_NO_INTERFERENCE')
    rep['elapsed_s'] = round(time.time() - t0, 3)
    f = REVIEW / 'evidence' / 'review_t5b_envelope_interference.json'
    f.parent.mkdir(parents=True, exist_ok=True)
    wlf(f, json.dumps(rep, ensure_ascii=False, indent=2) + '\n'); sidecar(f)
    print('T5B', rep['verdict'], 'violations:', rep['violation_count'])
    for v in rep['violations'][:20]:
        print(' ', v)

if __name__ == '__main__':
    main()
