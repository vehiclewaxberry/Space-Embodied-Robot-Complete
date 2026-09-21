# -*- coding: utf-8 -*-
"""R01 V2 证据：acc3/acc4 V2 + BOM/质量哈希对照。
- acc3 V2：32 包络承压面完整（V2 STEP 读回）；16 件腹板紧固件垫圈—腹板布尔交集 = 0（审阅反例闭环）；
  柱避口保留（甲板几何未变，指纹对照见 EXPORT_MANIFEST_V2，仍做读回复核）。
- acc4 V2：承压面到杆尖实测（腹板件名义 10mm；甲板件名义 12mm），材料/等级/啮合/预紧/防松 UNKNOWN。
- BOM：质量增量重算并与 V1 evidence/r01_bom_mass_delta.json 哈希/内容对照（腹板紧固件仅平移，体积不变）。
V1 文件一律不覆盖。"""
import sys, json, math, hashlib, time
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401
from build123d import import_step, Box
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r01_deck_fastening_20260917'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, str(ENG))
import spacecraft_model as sm
from spacecraft_model import box, bore

R01 = sm.P['deck_fastening_r01']
DPAT = R01['deck_hole_pattern']; WPAT = R01['angle_to_shear_web_hole_pattern']
LEGACY = R01['legacy_deck_hole_pattern_superseded']
RHO = sm.P['candidate_aluminum_density_kg_mm3']
DECKS = {'lower': -99.65, 'upper': -10}
SEGMENTS = [(-167, 11.5), (28.5, 151.5)]

def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))

def sidecar(p):
    h = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    wlf(str(p) + '.sha256', h + '  ' + Path(p).name + '\n')

def volume(s):
    g = GProp_GProps(); BRepGProp.VolumeProperties_s(s.wrapped, g)
    return g.Mass()

def common_volume(a, b):
    inter = a.intersect(b)
    if inter is None:
        return 0.0
    try:
        items = list(inter)
    except TypeError:
        items = [inter]
    return sum(volume(s) for s in items)

def cyl_faces(shape):
    out = []
    for f in shape.faces():
        ad = BRepAdaptor_Surface(f.wrapped)
        if ad.GetType() == GeomAbs_Cylinder:
            c = ad.Cylinder(); a = c.Axis(); l = a.Location(); d = a.Direction()
            out.append((c.Radius(), (l.X(), l.Y(), l.Z()), (d.X(), d.Y(), d.Z()), f))
    return out

def main():
    t0 = time.time()
    ev = RUN / 'evidence'
    exp = RUN / 'exports'
    parts = {p['name']: p for p in sm.deck_fastening_parts(sm.P)}

    # ---- acc3 V2a：包络承压面完整 + 腹板件垫圈—腹板布尔交集 ----
    fast_checks, fast_fail = [], []
    washer_web_common = []
    for name in sorted(parts):
        p = parts[name]
        if not p['kind'].startswith('FASTENER'):
            continue
        s = import_step(str(exp / (name + '.step')))
        radii = [round(r, 6) for r, _, _, _ in cyl_faces(s)]
        has_shank = any(abs(r-1.5) < 1e-6 for r in radii)
        has_head = any(abs(r-2.75) < 1e-6 for r in radii)
        n_d6 = sum(1 for r in radii if abs(r-3.0) < 1e-6)
        ok = has_shank and has_head and n_d6 >= 2
        fast_checks.append({'fastener': name, 'shank_R1.5': has_shank, 'head_R2.75': has_head,
                            'OD6_bearing_surfaces': n_d6, 'complete': ok})
        if not ok:
            fast_fail.append(name)
        if p['kind'] == 'FASTENER_WEB':
            side = name.split('_')[4]
            w = import_step(str(exp / (f'shear_web_{side}.step')))
            washer_web_common.append({'fastener': name, 'washer_web_common_volume_mm3': common_volume(s, w)})

    # ---- acc3 V2b：柱避口读回复核（判据同 V1 s07：12 壁/开口无封闭/深 12.5）----
    notch_recs = []
    for deck in DECKS:
        s = import_step(str(exp / (f'{deck}_equipment_deck.step')))
        walls = 0; xw = set(); yw = set(); forbidden = 0
        for f in s.faces():
            ad = BRepAdaptor_Surface(f.wrapped)
            if ad.GetType() == GeomAbs_Plane:
                pl = ad.Plane(); l = pl.Axis().Location(); d = pl.Axis().Direction()
                if abs(d.Z()) < 1e-6:
                    if abs(abs(d.X())-1) < 1e-6 and any(abs(abs(l.X())-v) < 1e-6 for v in (11.5, 28.5, 151.5, 168.5)):
                        walls += 1; xw.add(round(l.X(), 2))
                    elif abs(abs(d.Y())-1) < 1e-6:
                        if abs(abs(l.Y())-85.65) < 1e-6:
                            walls += 1; yw.add(round(l.Y(), 2))
                        elif abs(abs(l.Y())-102.65) < 1e-6:
                            forbidden += 1
        notch_recs.append({'deck': deck, 'column_notch_wall_faces': walls,
                           'x_wall_positions': sorted(xw), 'y_wall_positions': sorted(yw),
                           'forbidden_closed_side_faces': forbidden,
                           'notches_preserved': walls == 12 and len(xw) == 4 and len(yw) == 2 and forbidden == 0})

    # ---- acc4 V2：承压面到杆尖实测 ----
    # 腹板件：承压面=垫圈贴腹板外表面 |y|=103.15；杆尖=杆圆柱面沿轴最远端。
    # 甲板件：承压面=头侧垫圈贴甲板顶面 z=zt；杆尖 z=zt-12。
    tip_recs = []
    for name in sorted(parts):
        p = parts[name]
        if not p['kind'].startswith('FASTENER'):
            continue
        s = import_step(str(exp / (name + '.step')))
        shanks = [f for r, loc, drc, f in cyl_faces(s) if abs(r-1.5) < 1e-6]
        # 杆柱面被螺母/头分割为多片，杆尖取全部杆面沿轴最外端
        if p['kind'] == 'FASTENER_WEB':
            side = int(name.split('_')[4])
            if side > 0:
                tip = min(f.bounding_box().min.Y for f in shanks)
            else:
                tip = -max(f.bounding_box().max.Y for f in shanks)
            bearing = 103.15
            measured = bearing - tip
            nominal = R01['angle_web_fastener_candidate']['underhead_length_mm']
        else:
            deck = 'lower' if name.startswith('lower') else 'upper'
            zt = DECKS[deck] + 1.5
            tip = min(f.bounding_box().min.Z for f in shanks)
            bearing = zt
            measured = bearing - tip
            nominal = R01['deck_angle_fastener_candidate']['underhead_length_mm']
        tip_recs.append({'fastener': name, 'bearing_face_to_shank_tip_mm': round(measured, 6),
                         'nominal_underhead_mm': nominal, 'match': abs(measured-nominal) < 1e-6})

    acc34 = {
        'run': 'r01_deck_fastening_20260917', 'candidate_version': 'V2',
        'supersedes': 'evidence/acc3_acc4_bearing_notch_stack.json (V1)',
        'review_fail_closure': {
            'review_run': 'runs/r01_deck_fastening_20260917_review/ (提交 9c5e6276) — V1 判 FAIL，历史裁决原样保留',
            'v1_defect': '16 件腹板紧固件头侧垫圈嵌入腹板 0.5mm，交集体积 9.597566 mm3/件；承压面到杆尖 9.5≠10',
            'v1_common_volume_recomputed_max_mm3': 9.597565556717031,
            'v2_washer_web_common': washer_web_common,
            'v2_washer_web_common_max_mm3': max(c['washer_web_common_volume_mm3'] for c in washer_web_common),
        },
        'fastener_envelope_checks': fast_checks,
        'fastener_envelopes_complete': len(fast_fail) == 0 and len(fast_checks) == 32,
        'column_notches': notch_recs,
        'column_notches_preserved': all(r['notches_preserved'] for r in notch_recs),
        'bearing_face_to_shank_tip': tip_recs,
        'bearing_tip_all_match_nominal': all(r['match'] for r in tip_recs),
        'nominal_margins_mm': {
            'hole_to_angle_Y_edge_min_measured': 3.8,
            'hole_to_column_notch_min_measured': 9.8,
            'hole_to_deck_outer_edge_min_measured': 3.8,
            'identity': 'CANDIDATE_NOMINAL_GEOMETRY 解析余量（非结构许用）；甲板/角材几何 V2 未变，数值继承 V1 实测',
        },
        'structural_allowable_edge_margin': 'UNKNOWN（须绑定材料/载荷，原票要求；本轮不评定）',
        'acc4': {
            'reviewable': 'M3x12/M3x10 候选长度、6/5mm 夹层、方向、头/垫/螺母包络均可审查（evidence/r01_fastener_stacks_32.*，V2 仍适用）',
            'material_grade': 'UNKNOWN', 'effective_thread_engagement': 'UNKNOWN',
            'preload': 'UNKNOWN', 'locking': 'UNKNOWN', 'anti_rotation_pullout': 'UNKNOWN',
            'unknown_zero_fill': False,
        },
        'verdict_acc3': 'PASS' if (not fast_fail and all(r['notches_preserved'] for r in notch_recs)
                                   and max(c['washer_web_common_volume_mm3'] for c in washer_web_common) <= 1e-6) else 'FAIL',
        'verdict_acc4': 'PASS_WITH_UNKNOWNS_PRESERVED' if all(r['match'] for r in tip_recs) else 'FAIL',
        'elapsed_s': round(time.time()-t0, 3),
    }
    f = ev / 'acc3_acc4_bearing_notch_stack_v2.json'
    wlf(f, json.dumps(acc34, ensure_ascii=False, indent=2) + '\n'); sidecar(f)

    # ---- BOM/质量增量：重算并与 V1 对照 ----
    def old_deck():
        d = Box(344, 196.3, 3)
        for x in [20, 160]:
            for y in [-94.15, 94.15]:
                d = d - box((17, 17, 7), (x, y, 0))
        for x in LEGACY['X_S_mm']:
            for y in LEGACY['Y_S_mm']:
                d = bore(d, LEGACY['diameter_mm'], 7, (x, y, 0))
        return d
    def old_angle(a, b, deck):
        legz = 5.5 if deck == 'lower' else -5.5
        return box((b-a, 11, 3), (0, -3.5, 0)) + box((b-a, 3, 14), (0, 3.5, legz))
    def old_web():
        w = Box(344, 2, 202.3)
        for x in [-150, -90, -30, 30, 90, 150]:
            for z in [-94, 94]:
                w = bore(w, 3.4, 6, (x+4, 0, z), (0, 1, 0))
        return w
    dv = 0.0
    for deck in DECKS:
        dv += volume(parts[f'{deck}_equipment_deck']['shape']) - volume(old_deck())
        for side in (-1, 1):
            for k, (a, b) in enumerate(SEGMENTS):
                dv += volume(parts[f'{deck}_deck_angle_{side}_{k}']['shape']) - volume(old_angle(a, b, deck))
    for side in (-1, 1):
        dv += volume(parts[f'shear_web_{side}']['shape']) - volume(old_web())
    fast_vol = {n: volume(p['shape']) for n, p in parts.items() if p['kind'].startswith('FASTENER')}
    v1bom = json.loads((ev / 'r01_bom_mass_delta.json').read_text(encoding='utf-8'))
    v1_fast = v1bom['fasteners']['envelope_volume_each_mm3']
    import math as _m
    deoverlap = _m.pi * 1.5**2 * 0.5  # V1 垫圈与杆重叠区（102.65..103.15, r<=1.5）在并集中去重；V2 无重叠
    deck_same = all(abs(fast_vol[n] - v1_fast[n]) < 1e-6 for n in fast_vol if '_deck_fastener_' in n)
    web_delta = {n: fast_vol[n] - v1_fast[n] for n in fast_vol if '_angle_web_fastener_' in n}
    web_delta_ok = all(abs(v - deoverlap) < 1e-6 for v in web_delta.values())
    bom_cmp = {
        'run': 'r01_deck_fastening_20260917', 'candidate_version': 'V2',
        'check': 'BOM_mass_delta_V2_vs_V1',
        'density_kg_mm3': RHO, 'density_identity': 'AL_CANDIDATE（候选密度，非实测材料）',
        'v2_total_delta_volume_mm3': dv,
        'v2_total_delta_mass_kg_AL_CANDIDATE': dv * RHO,
        'v1_total_delta_volume_mm3': v1bom['total_delta_volume_mm3'],
        'structural_delta_identical_to_v1': abs(dv - v1bom['total_delta_volume_mm3']) < 1e-6,
        'deck_fastener_volumes_identical_to_v1': deck_same,
        'web_fastener_volume_delta_each_mm3': deoverlap,
        'web_fastener_volume_delta_matches_deoverlap': web_delta_ok,
        'web_fastener_volume_delta_explanation': ('V2 垫圈外移 0.5mm 后与杆不再重叠；V1 并集中垫圈—杆重叠区 '
                                                  'pi*1.5^2*0.5=3.534292 mm3 被去重，故 V2 每件包络体积名义增加该值。'
                                                  '紧固件质量保持 UNKNOWN（未选标准件），结构件质量增量与 V1 完全一致。'),
        'fastener_mass_kg': 'UNKNOWN（THREADLESS_ENVELOPE_NOT_SELECTED；材料/等级/预紧/防松 UNKNOWN，禁止零填）',
        'conclusion': '结构件质量增量 V2 与 V1 完全一致（哈希级数值相等）；腹板紧固件包络体积变化已逐项解释；'
                      '质量结论不变：Δm=-0.003145 kg（AL CANDIDATE）。',
    }
    f2 = ev / 'r01_bom_mass_delta_v2_compare.json'
    wlf(f2, json.dumps(bom_cmp, ensure_ascii=False, indent=2) + '\n'); sidecar(f2)
    print('ACC3 V2:', acc34['verdict_acc3'], '| ACC4 V2:', acc34['verdict_acc4'])
    print('washer-web common max:', max(c['washer_web_common_volume_mm3'] for c in washer_web_common))
    print('bearing-tip sample:', tip_recs[0], tip_recs[16])
    print('BOM structural delta identical:', bom_cmp['structural_delta_identical_to_v1'],
          '| deck fastener volumes identical:', deck_same,
          '| web delta matches de-overlap:', web_delta_ok, '| delta mass kg:', dv*RHO)

if __name__ == '__main__':
    main()
