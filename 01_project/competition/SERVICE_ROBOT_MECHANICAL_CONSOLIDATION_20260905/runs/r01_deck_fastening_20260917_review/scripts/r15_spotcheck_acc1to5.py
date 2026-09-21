# -*- coding: utf-8 -*-
"""WP03 R01 验收6 独立复验 - 任务6：构建者 ACCEPTANCE_SUMMARY 验收 1-5 抽验复核。

每项至少抽 2 个数值，与审阅者独立重算（review_t1/t5/nc3 证据 + 本脚本补充的厚度/杆长测量）比对。
厚度测量方法（自写）：在孔轴旁 3mm 偏置点沿夹层法向以 0.005mm 步进做实体分类，取材料区间长度。
杆长测量：读回 STEP 杆面（R1.5 圆柱面）UV V 向跨度。
比对容差：计数精确相等；几何量 |diff| <= 0.01mm（构建者值含 BRep 容差量 2.995 等）。
"""
import sys, json, math, hashlib, time
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401
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
EXP = RUN / 'exports'
EV = RUN / 'evidence'
MEV = REVIEW / 'evidence'
GTOL = 0.01

def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))

def sidecar(p):
    h = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    wlf(str(p) + '.sha256', h + '  ' + Path(p).name + '\n')
    return h

def inside(shape, x, y, z):
    return BRepClass3d_SolidClassifier(shape.wrapped, gp_Pnt(x, y, z), 1e-9).State() == TopAbs_IN

def material_thickness(shape, p0, axis, span=10.0, step=0.005):
    """沿 axis 从 p0-span 走到 p0+span，返回材料区间总长（多段求和）。"""
    n = int(2 * span / step)
    total = 0.0
    for i in range(n):
        t = -span + (i + 0.5) * step
        if inside(shape, p0[0] + axis[0] * t, p0[1] + axis[1] * t, p0[2] + axis[2] * t):
            total += step
    return total

def head_bearing_to_tip(step_file, axis_idx, side_sign=1):
    """头侧承压面到杆尖距离（读回测量）：承压面 = R2.75 头面沿轴最远端 - 头高3 - 垫圈0.5；
    杆尖 = 实体 bbox 沿轴最近端。axis_idx: 2=Z 轴, 1=Y 轴；side_sign 用于 Y 轴镜像件。"""
    s = import_step(str(step_file))
    head = None
    for f in s.faces():
        ad = BRepAdaptor_Surface(f.wrapped)
        if ad.GetType() == GeomAbs_Cylinder and abs(ad.Cylinder().Radius() - 2.75) < 0.02:
            head = f
            break
    if head is None:
        return None
    hb = head.bounding_box(); sb = s.bounding_box()
    if axis_idx == 2:
        head_far, tip = hb.max.Z, sb.min.Z
    else:
        head_far = hb.max.Y if side_sign > 0 else -hb.min.Y
        tip = sb.min.Y if side_sign > 0 else -sb.max.Y
    return (head_far - 3.0 - 0.5) - tip

def cmp(name, builder_val, my_val, tol=GTOL):
    if isinstance(builder_val, (int, float)) and isinstance(my_val, (int, float)):
        ok = abs(builder_val - my_val) <= tol
    else:
        ok = builder_val == my_val
    return {'quantity': name, 'builder': builder_val, 'independent': my_val, 'consistent': bool(ok)}

def main():
    t0 = time.time()
    t1 = json.loads((MEV / 'review_t1_readback.json').read_text(encoding='utf-8'))
    t5 = json.loads((MEV / 'review_t5_interference_scan.json').read_text(encoding='utf-8'))
    nc3 = json.loads((MEV / 'review_nc3_washer_tool_conflict.json').read_text(encoding='utf-8'))
    t5b = json.loads((MEV / 'review_t5b_envelope_interference.json').read_text(encoding='utf-8'))
    acc = json.loads((RUN / 'ACCEPTANCE_SUMMARY.json').read_text(encoding='utf-8'))
    acc5 = json.loads((EV / 'acc5_builder_self_check.json').read_text(encoding='utf-8'))
    stacks = json.loads((EV / 'r01_fastener_stacks_32.json').read_text(encoding='utf-8'))
    pairs = json.loads((EV / 'r01_dual_hole_pairs_32.json').read_text(encoding='utf-8'))

    items = []

    # ---------- 验收1 ----------
    my_min_notch = min(h['analytic_hole_to_column_notch_mm'] for d in t1['decks'].values() for h in d['holes'])
    my_min_edge = min(h['analytic_hole_to_deck_outer_edge_mm'] for d in t1['decks'].values() for h in d['holes'])
    my_brep_notch = min(d['brep_min_dist_hole140_to_notch_wall_mm'] for d in t1['decks'].values())
    items.append({'item': 1, 'checks': [
        cmp('closed_holes', 16, t1['total_closed_holes'], 0),
        cmp('old_pattern_residual_faces', 0,
            sum(r['residual_faces'] for d in t1['decks'].values() for r in d['old_pattern_residuals']), 0),
        cmp('min_hole_to_column_notch_mm', 9.8, my_min_notch),
        cmp('min_hole_to_column_notch_mm(BRep 面距)', 9.8, my_brep_notch),
        cmp('min_hole_to_deck_outer_edge_mm', 3.8, my_min_edge)]})

    # ---------- 验收2 ----------
    my_da = t1['coaxial']['deck_angle_ok']; my_aw = t1['coaxial']['angle_web_ok']
    my_dev_max = max(max(p['coaxial_deviation_mm'] for p in t1['coaxial']['deck_angle_pairs']),
                     max(p['coaxial_deviation_mm'] for p in t1['coaxial']['angle_web_pairs']))
    # 独立夹层厚度：甲板-角材对（x=-150 旁 3mm 偏置）
    deck_l = import_step(str(EXP / 'lower_equipment_deck.step'))
    ang_l = import_step(str(EXP / 'lower_deck_angle_-1_0.step'))
    web_l = import_step(str(EXP / 'shear_web_-1.step'))
    t_deck = material_thickness(deck_l, (-147, -92.65, -99.65), (0, 0, 1))
    t_angle_h = material_thickness(ang_l, (-147, -92.65, -102.65), (0, 0, 1))
    t_angle_v = material_thickness(ang_l, (-130, -99.65, -91.15), (0, 1, 0))
    t_web = material_thickness(web_l, (-130, -102.15, -91.15), (0, 1, 0))
    items.append({'item': 2, 'checks': [
        cmp('groups_ok', 32, my_da + my_aw, 0),
        cmp('coaxial_deviation_mm(max)', 0.0, my_dev_max),
        cmp('deck_angle_stackup_mm', 6.0, t_deck + t_angle_h),
        cmp('angle_web_stackup_mm', 5.0, t_angle_v + t_web)],
        'thickness_method': '孔轴旁 3mm 偏置点 0.005mm 步进分类器测量',
        'thickness_detail': {'deck': round(t_deck, 4), 'angle_h_leg': round(t_angle_h, 4),
                             'angle_v_leg': round(t_angle_v, 4), 'web': round(t_web, 4)}})

    # ---------- 验收3 ----------
    my_f = {f['fastener']: f for f in t1['fasteners']}
    f1 = my_f['lower_deck_fastener_-1_-150']; f2 = my_f['upper_angle_web_fastener_1_1_130']
    my_notch_walls = [t1['decks'][d]['column_notch_wall_faces'] for d in ('lower', 'upper')]
    # 构建者口径为存在性布尔（shank_R1.5/head_R2.75: true）+ OD6 承压面数 2；R1.5 面在 STEP 接缝处
    # 分两片属导出惯例，按存在性比对
    t5b_map = {e['fastener']: e for e in t5b['per_fastener']}
    items.append({'item': 3, 'checks': [
        cmp('fastener_envelopes_complete', 32, t1['fastener_envelopes_complete'], 0),
        cmp('lower_deck_fastener_-1_-150 shank/head存在+OD6数', (True, True, 2),
            (f1['shank_R1.5_faces'] >= 1, f1['head_R2.75_faces'] >= 1, f1['OD6_class_faces']), 0),
        cmp('upper_angle_web_fastener_1_1_130 shank/head存在+OD6数', (True, True, 2),
            (f2['shank_R1.5_faces'] >= 1, f2['head_R2.75_faces'] >= 1, f2['OD6_class_faces']), 0),
        cmp('column_notch_walls_per_deck', [12, 12], my_notch_walls, 0),
        cmp('notch_depth_mm', 12.5, 98.15 - 85.65),
        cmp('nominal_margin_to_notch_mm', 9.8, my_min_notch),
        cmp('nominal_margin_angle_Y_edge_mm', 3.8, my_min_edge),
        cmp('web_fastener 头垫圈承压区未被结构吞没(交集体积)', 0.0,
            t5b_map['upper_angle_web_fastener_1_1_130']['common_with_clamped'].get('shear_web_1', 0.0))],
        'note': '头垫圈承压面位于腹板外表面内侧 0.5mm（见 review_t5b），"承压区完整"对 16 件腹板件不成立'})

    # ---------- 验收4 ----------
    rows = stacks['rows'] if 'rows' in stacks else stacks.get('stacks', [])
    n12 = sum(1 for r in rows if r.get('layer') == 'deck_to_angle' and r.get('underhead_length_mm') == 12)
    n10 = sum(1 for r in rows if r.get('layer') == 'angle_to_shear_web' and r.get('underhead_length_mm') == 10)
    # 独立读回测量：头承压面到杆尖距离
    L_deck = head_bearing_to_tip(EXP / 'lower_deck_fastener_1_50.step', 2)
    L_web = head_bearing_to_tip(EXP / 'upper_angle_web_fastener_-1_0_-70.step', 1, -1)
    unknowns_ok = all(r.get('material_grade') == 'UNKNOWN' and r.get('preload') == 'UNKNOWN'
                      and r.get('locking') == 'UNKNOWN' for r in rows)
    items.append({'item': 4, 'checks': [
        cmp('stack_rows', 32, len(rows), 0),
        cmp('M3x12_deck_angle_sets', 16, n12, 0),
        cmp('M3x10_angle_web_sets', 16, n10, 0),
        cmp('M3x12 承压面到杆尖(读回测量)', 12.0, L_deck),
        cmp('M3x10 承压面到杆尖(读回测量)', 10.0, L_web),
        cmp('UNKNOWN 字段保留(material/preload/locking)', True, unknowns_ok, 0)],
        'note': ('腹板件读回测量承压面到杆尖 9.5mm != 名义 M3x10：头垫圈中心内移 0.5mm'
                 '（与验收3/5B 垫圈嵌入腹板同源）；甲板件 12.0 一致。')})

    # ---------- 验收5 ----------
    my_pair = t5['fastener_pairwise']
    real_hit = nc3['nc3b_tool_conflict']['real_overhead_hit_recheck']
    items.append({'item': 5, 'checks': [
        cmp('named_check_set_size', 108, t5['named_check_set_size'], 0),
        cmp('penetration_sample_hits(同口径采样)', 0, t5['penetration_sample_hits_total'], 0),
        cmp('fastener_pairwise_min_distance_mm', 4.5458, my_pair['min_distance_mm'], 0.001),
        cmp('sequence_constraints', 46, len(t5['sequence_constraints']), 0),
        cmp('tool upper_deck_fastener_-1_-50 vs hold_crossbeam_1 d', 0.0,
            real_hit['hold_crossbeam_1_distance_mm']),
        cmp('pairwise 最近对', ['upper_angle_web_fastener_-1_1_130', 'upper_deck_fastener_-1_140'],
            my_pair['pair']),
        cmp('未处置干涉(布尔交集口径) violations', 0, t5b['violation_count'], 0)],
        'note': ('构建者 acc5 violations=0 在其采样口径下可复现，但该口径对垫圈环形承压区有盲区；'
                 '布尔交集口径下 16 件腹板紧固件头垫圈嵌入腹板（每件 9.597566 mm3），'
                 '构建者 "violations: 0" 结论不被独立复验确认。')})

    total = sum(len(i['checks']) for i in items)
    consistent = sum(1 for i in items for c in i['checks'] if c['consistent'])
    rep = {'review': 'r01_deck_fastening_20260917_review',
           'check': 'ACC6_T6_builder_acceptance_1_to_5_spotcheck',
           'method': '每项至少抽 2 个数值独立重算并比对；容差 0.01mm（计数精确）',
           'builder_summary_sha256': hashlib.sha256((RUN / 'ACCEPTANCE_SUMMARY.json').read_bytes()).hexdigest(),
           'items': items,
           'spot_values_total': total, 'spot_values_consistent': consistent,
           'agreement_rate': round(consistent / total, 6),
           'verdict': 'SPOTCHECK_ALL_CONSISTENT' if consistent == total else 'SPOTCHECK_DISCREPANCY_FOUND',
           'elapsed_s': round(time.time() - t0, 3)}
    f = MEV / 'review_t6_spotcheck.json'
    wlf(f, json.dumps(rep, ensure_ascii=False, indent=2) + '\n'); sidecar(f)
    print('T6', rep['verdict'], f'{consistent}/{total}', 'elapsed', rep['elapsed_s'])
    for i in items:
        for c in i['checks']:
            if not c['consistent']:
                print(' DISCREPANCY item', i['item'], c)

if __name__ == '__main__':
    main()
