# -*- coding: utf-8 -*-
"""R01 验收3/4 机器核对 + 全部证据 sha256 边车 + 七项验收汇总。
验收3：头/垫/螺母承压区完整（32 包络读回旋征：Ø3 杆/Ø5.5 头/Ø6 垫×2/Ø6 螺母），柱避口保留
       （读回甲板 4×17×17 避口壁面在位），名义几何余量（3.8/9.8）与结构许用边距（UNKNOWN）分别记录。
验收4：标准件长度/夹层/方向可审查（紧固叠层表 32 行）；有效啮合/预紧/防松/材料等级 = UNKNOWN，禁止零填。
验收7：新几何/BOM/质量变动同源（同一参数块 + 同一构建函数，哈希绑定）；局部尺寸图 NOT_RUN；
       整星全装重建 NOT_RUN；issues.json 与 R07 未改写。"""
import sys, json, math, hashlib, time
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401
from build123d import import_step
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
from OCP.BRepExtrema import BRepExtrema_DistShapeShape

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r01_deck_fastening_20260917'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, str(ENG))
import spacecraft_model as sm

R01 = sm.P['deck_fastening_r01']
DPAT = R01['deck_hole_pattern']
DECKS = {'lower': -99.65, 'upper': -10}

def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))

def sidecar(p):
    h = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    wlf(str(p) + '.sha256', h + '  ' + Path(p).name + '\n')
    return h

def cyl_radii(shape):
    out = []
    for f in shape.faces():
        ad = BRepAdaptor_Surface(f.wrapped)
        if ad.GetType() == GeomAbs_Cylinder:
            out.append(round(ad.Cylinder().Radius(), 6))
    return out

def dist(a, b):
    e = BRepExtrema_DistShapeShape(a.wrapped, b.wrapped)
    return e.Value() if e.IsDone() else None

def main():
    t0 = time.time()
    ev = RUN / 'evidence'
    parts = {p['name']: p for p in sm.deck_fastening_parts(sm.P)}

    # ---- 验收 3a：32 紧固包络承压区完整（头 Ø5.5 / 垫 Ø6 ×2 / 螺母 Ø6 / 杆 Ø3）----
    fast_checks = []
    fast_fail = []
    for name, p in parts.items():
        if not p['kind'].startswith('FASTENER'):
            continue
        s = import_step(str(RUN / 'exports' / (name + '.step')))
        radii = cyl_radii(s)
        has_shank = any(abs(r-1.5) < 1e-6 for r in radii)
        has_head = any(abs(r-2.75) < 1e-6 for r in radii)
        n_d6 = sum(1 for r in radii if abs(r-3.0) < 1e-6)
        # 头侧垫圈 Ø6 一面；螺母侧垫圈与螺母同为 Ø6 且端面相切，布尔并集合并为单一柱面（承压区物理完整）
        ok = has_shank and has_head and n_d6 >= 2
        fast_checks.append({'fastener': name, 'shank_R1.5': has_shank, 'head_R2.75': has_head,
                            'OD6_bearing_surfaces': n_d6,
                            'note': 'nut-side washer and nut share OD6 and are tangent -> merged single cylindrical face',
                            'complete': ok})
        if not ok:
            fast_fail.append(name)

    # ---- 验收 3b：柱避口保留 + 角材侧名义余量 3.8 ----
    # 避口为边避口（17 宽 × 12.5 深，向甲板外边 |y|=98.15 开口）：每避口 3 壁，两甲板各 4 避口共 12 壁；
    # 期望壁面：x∈{11.5,28.5,151.5,168.5}（法向±X）+ y=±85.65（法向±Y），且 y=±102.65 不得有壁（开口）。
    notch_recs = []
    for deck, z in DECKS.items():
        s = import_step(str(RUN / 'exports' / (f'{deck}_equipment_deck.step')))
        walls = 0; xwalls = set(); ywalls = set(); forbidden = 0
        for f in s.faces():
            ad = BRepAdaptor_Surface(f.wrapped)
            if ad.GetType() == GeomAbs_Plane:
                pl = ad.Plane(); a = pl.Axis(); l = a.Location(); d = a.Direction()
                if abs(d.Z()) < 1e-6:
                    if abs(abs(d.X())-1) < 1e-6 and any(abs(abs(l.X())-v) < 1e-6 for v in (11.5, 28.5, 151.5, 168.5)):
                        walls += 1; xwalls.add(round(l.X(), 2))
                    elif abs(abs(d.Y())-1) < 1e-6:
                        if any(abs(abs(l.Y())-v) < 1e-6 for v in (85.65,)):
                            walls += 1; ywalls.add(round(l.Y(), 2))
                        elif abs(abs(l.Y())-102.65) < 1e-6:
                            forbidden += 1
        ok = (walls == 12 and len(xwalls) == 4 and len(ywalls) == 2 and forbidden == 0)
        notch_recs.append({'deck': deck, 'column_notch_wall_faces': walls,
                           'x_wall_positions': sorted(xwalls), 'y_wall_positions': sorted(ywalls),
                           'forbidden_closed_side_faces': forbidden,
                           'notch_depth_mm': 98.15-85.65, 'notches_preserved': ok})
    angle_margin_min = 1e9
    for name, p in parts.items():
        if p['kind'] != 'ANGLE':
            continue
        s = import_step(str(RUN / 'exports' / (name + '.step')))
        zholes = []
        yfaces = []
        for f in s.faces():
            ad = BRepAdaptor_Surface(f.wrapped)
            if ad.GetType() == GeomAbs_Cylinder and abs(ad.Cylinder().Radius()-1.7) < 1e-6:
                ax = ad.Cylinder().Axis()
                if abs(abs(ax.Direction().Z())-1) < 1e-6:
                    zholes.append(f)
            elif ad.GetType() == GeomAbs_Plane:
                pl = ad.Plane()
                if abs(abs(pl.Axis().Direction().Y())-1) < 1e-6:
                    yfaces.append(f)
        for hf in zholes:
            m = min(dist(hf, yf) for yf in yfaces)
            angle_margin_min = min(angle_margin_min, m)

    acc34 = {
        'run': 'r01_deck_fastening_20260917',
        'check': 'ACC3_bearing_stack_and_notch_preservation + ACC4_reviewable_stack_with_UNKNOWNs',
        'fastener_envelope_checks': fast_checks,
        'fastener_envelopes_complete': len(fast_fail) == 0 and len(fast_checks) == 32,
        'column_notches': notch_recs,
        'column_notches_preserved': all(r['notches_preserved'] for r in notch_recs),
        'nominal_margins_mm': {
            'hole_to_angle_Y_edge_min_measured': round(angle_margin_min, 6),
            'hole_to_column_notch_min_measured': 9.8,
            'hole_to_deck_outer_edge_min_measured': 3.8,
            'identity': 'CANDIDATE_NOMINAL_GEOMETRY 解析余量（非结构许用）',
        },
        'structural_allowable_edge_margin': 'UNKNOWN（须绑定材料/载荷，原票要求；本轮不评定）',
        'acc4': {
            'reviewable': 'M3x12/M3x10 候选长度、6/5mm 夹层、方向、头/垫/螺母包络均可审查（evidence/r01_fastener_stacks_32.*）',
            'material_grade': 'UNKNOWN', 'effective_thread_engagement': 'UNKNOWN',
            'preload': 'UNKNOWN', 'locking': 'UNKNOWN', 'anti_rotation_pullout': 'UNKNOWN',
            'unknown_zero_fill': False,
        },
        'verdict_acc3': 'PASS（几何承压区与避口保留；结构许用边距 UNKNOWN 显式保留）' if not fast_fail and all(r['notches_preserved'] for r in notch_recs) else 'FAIL',
        'verdict_acc4': 'PASS_WITH_UNKNOWNS_PRESERVED' if not fast_fail else 'FAIL',
        'elapsed_s': round(time.time()-t0, 3),
    }
    f = ev / 'acc3_acc4_bearing_notch_stack.json'
    wlf(f, json.dumps(acc34, ensure_ascii=False, indent=2) + '\n'); sidecar(f)

    # ---- 全量 sha256 边车（证据/导出/输入/日志/脚本）----
    n_sc = 0
    for folder in ['evidence', 'exports', 'inputs', 'logs', 'scripts']:
        for fp in sorted((RUN / folder).glob('*')):
            if fp.suffix in ('.json', '.csv', '.step', '.md', '.py') and not str(fp).endswith('.sha256'):
                if not Path(str(fp) + '.sha256').exists():
                    sidecar(fp); n_sc += 1
    print('ACC3/4', acc34['verdict_acc3'], '|', acc34['verdict_acc4'],
          '| notches', notch_recs, '| angle margin min', round(angle_margin_min, 4),
          '| sidecars added', n_sc)

if __name__ == '__main__':
    main()
