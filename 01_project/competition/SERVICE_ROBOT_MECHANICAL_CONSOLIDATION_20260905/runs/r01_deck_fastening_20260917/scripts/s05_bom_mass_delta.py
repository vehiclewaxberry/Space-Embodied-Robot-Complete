# -*- coding: utf-8 -*-
"""R01 交付物5：BOM/质量增量与旧反例对照。
质量 = 体积 × 2.7e-6 kg/mm3 铝候选密度（CANDIDATE 身份，非实测）。
旧几何按 design_parameters.json deck_fastening_r01.legacy_deck_hole_pattern_superseded 重建（仅改孔系，其余同数学）。"""
import sys, json, math, hashlib, time
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401
from build123d import Box, Location
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
    return h

def volume(s):
    g = GProp_GProps(); BRepGProp.VolumeProperties_s(s.wrapped, g)
    return g.Mass()

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
    return box((b-a, 11, 3), (0, 0, 0)) + box((b-a, 3, 14), (0, 7, legz)) if False else \
           box((b-a, 11, 3), (0, -3.5, 0)) + box((b-a, 3, 14), (0, 3.5, legz))

def old_web():
    w = Box(344, 2, 202.3)
    for x in [-150, -90, -30, 30, 90, 150]:
        for z in [-94, 94]:
            w = bore(w, 3.4, 6, (x+4, 0, z), (0, 1, 0))
    return w

def main():
    t0 = time.time()
    parts = {p['name']: p for p in sm.deck_fastening_parts(sm.P)}
    rows = []
    # 甲板：旧（legacy 孔系） vs 新
    for deck in DECKS:
        v_old = volume(old_deck())
        v_new = volume(parts[f'{deck}_equipment_deck']['shape'])
        rows.append({'part': f'{deck}_equipment_deck', 'volume_old_mm3': v_old, 'volume_new_mm3': v_new,
                     'delta_volume_mm3': v_new - v_old,
                     'change': '孔系 X=[-150,-50,50,150],Y=±89 -> X=[-150,-50,50,140],Y=±92.65（8孔数不变，位置改变）；柱避口保留'})
    # 角材：旧（无孔） vs 新（水平腿4孔+竖直腿2孔/段）
    for deck in DECKS:
        for side in (-1, 1):
            for k, (a, b) in enumerate(SEGMENTS):
                v_old = volume(old_angle(a, b, deck))
                v_new = volume(parts[f'{deck}_deck_angle_{side}_{k}']['shape'])
                rows.append({'part': f'{deck}_deck_angle_{side}_{k}', 'volume_old_mm3': v_old, 'volume_new_mm3': v_new,
                             'delta_volume_mm3': v_new - v_old,
                             'change': '新增配合孔：水平腿 2 孔（与甲板同轴）+ 竖直腿 2 孔（与剪力板同轴）' if k == 0 else '同段1（水平腿2孔+竖直腿2孔）'})
    # 剪力板：旧（仅纵梁孔） vs 新（+8 角材配合孔）
    for side in (-1, 1):
        v_old = volume(old_web())
        v_new = volume(parts[f'shear_web_{side}']['shape'])
        rows.append({'part': f'shear_web_{side}', 'volume_old_mm3': v_old, 'volume_new_mm3': v_new,
                     'delta_volume_mm3': v_new - v_old,
                     'change': '新增 8 个角材—剪力板配合孔（z=-94.15/-18.5 各 4），纵梁孔系不变'})
    for r in rows:
        r['mass_old_kg_AL_CANDIDATE'] = r['volume_old_mm3'] * RHO
        r['mass_new_kg_AL_CANDIDATE'] = r['volume_new_mm3'] * RHO
        r['delta_mass_kg_AL_CANDIDATE'] = r['delta_volume_mm3'] * RHO
    dv = sum(r['delta_volume_mm3'] for r in rows)
    # 紧固件：候选包络体积（参考），质量 UNKNOWN（未选标准件）
    fast_vol = {p['name']: volume(p['shape']) for p in parts.values() if p['kind'].startswith('FASTENER')}
    out = {
        'run': 'r01_deck_fastening_20260917',
        'check': 'BOM_mass_delta_vs_old_counterexample',
        'density_kg_mm3': RHO, 'density_identity': 'AL_CANDIDATE（候选密度，非实测材料）',
        'per_part': rows,
        'total_delta_volume_mm3': dv,
        'total_delta_mass_kg_AL_CANDIDATE': dv * RHO,
        'fasteners': {
            'count': len(fast_vol),
            'deck_angle_sets_M3x12_candidate': 16, 'angle_web_sets_M3x10_candidate': 16,
            'envelope_volume_each_mm3': fast_vol,
            'mass_kg': 'UNKNOWN（THREADLESS_ENVELOPE_NOT_SELECTED；材料/等级/预紧/防松 UNKNOWN，禁止零填）',
        },
        'old_counterexample_resolution': {
            'old_defect': LEGACY['defect'],
            'old_broken_edge_holes_total': 4,
            'old_hole_notch_overlap_mm': 0.2,
            'new_min_hole_to_column_notch_mm_measured': 9.8,
            'new_broken_edge_holes': 0,
            'evidence': 'evidence/acc1_deck_closed_holes.json',
        },
        'bom_identity': 'CANDIDATE_NOMINAL_GEOMETRY；整星 BOM.csv 未重生成（整装重建 NOT_RUN 时保持原样）',
        'elapsed_s': round(time.time()-t0, 3),
    }
    f = RUN / 'evidence' / 'r01_bom_mass_delta.json'
    wlf(f, json.dumps(out, ensure_ascii=False, indent=2) + '\n'); sidecar(f)
    print('total delta volume mm3:', round(dv, 3), 'delta mass kg (AL cand):', round(dv*RHO, 6))
    for r in rows[:3]:
        print(' ', r['part'], round(r['delta_volume_mm3'], 2))

if __name__ == '__main__':
    main()
