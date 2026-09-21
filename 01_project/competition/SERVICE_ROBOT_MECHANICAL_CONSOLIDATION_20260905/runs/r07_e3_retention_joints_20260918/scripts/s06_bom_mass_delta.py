# -*- coding: utf-8 -*-
"""R07-E3 BOM/质量增量：
- E3 新增 24 件均为无螺纹名义包络（NOT_ALLOCATED；AL_EQUIVALENT 仅供预算，非零填）；
- 本 run 实改 8 既有构件（孔去除）：removed_volume 实算——上纵梁基线=E2 run 同名导出 STEP（E2 未改纵梁）；
  hold 构件基线=按 spacecraft_model 同源构造行复建的无 E3 delta 几何（横梁 plate(22,202.3,10)+2 备用孔 /
  耳座 plate(22,14,12)+1 备用孔 / 足叉 Box-slot-枢轴孔），现值=本 run 导出 STEP 读回；
- 净分配质量增量 = 0 kg（包络未分配）；铝当量净增量可正可负如实列。"""
import sys, json, csv, hashlib, time
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401
from build123d import import_step, Box, Location

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_e3_retention_joints_20260918'
E2RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_e2_endplug_retention_20260918'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, str(ENG))
import spacecraft_model as sm
from spacecraft_model import plate, box

RHO_AL = 2.7e-6
E3PREFIX = ('e3_clamp_', 'e3_foot_')

def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))

def sidecar(p):
    h = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    rel = Path(p).resolve().relative_to(RUN).as_posix()
    wlf(str(p) + '.sha256', h + '  ' + rel + '\n')
    return h

def baseline_hold(name):
    """与 spacecraft_model.build 保持器构件构造行同源的无 E3 delta 基线几何（世界系）。"""
    if name.startswith('hold_crossbeam'):
        k = int(name.rsplit('_', 1)[1])
        x = sm.P['retention']['station_x_mm'][k]
        s = plate((22, 202.3, 10), [(0, y, 4.5) for y in [-94.15, 94.15]])
        return s.moved(Location((x, 0, 101.15)))
    if name.startswith('hold_roof_lug'):
        k = int(name.split('_')[3])
        x = sm.P['retention']['station_x_mm'][k]
        s = plate((22, 14, 12), [(0, 0, 4.5)])
        return s.moved(Location((x, -94.15, 112.15)))
    if name.startswith('hold_pivot_clevis'):
        k = int(name.rsplit('_', 1)[1])
        x = sm.P['retention']['station_x_mm'][k]
        s = Box(30, 26, 30) - box((14, 28, 30), (0, 0, 7))
        from spacecraft_model import bore
        s = bore(s, 8.4, 36, (0, 0, 2), (1, 0, 0))
        return s.moved(Location((x, -99, 133.15)))
    raise ValueError(name)

def main():
    t0 = time.time()
    model, shapes, receipt = sm.build('service', include_arm=False)
    recs = {r['id']: r for r in receipt['instances'] if r['id'].startswith(E3PREFIX)}
    rows = []
    for name in sorted(recs):
        r = recs[name]
        v = r['volume_mm3']
        rows.append({
            'instance': name, 'kind': ('CLAMP_BOLT' if '_clamp_bolt_' in name else 'CLAMP_WASHER' if '_clamp_' in name else 'FOOT_BOLT' if '_foot_bolt_' in name else 'FOOT_WASHER'),
            'volume_mm3': round(v, 6), 'al_equivalent_mass_kg': round(v * RHO_AL, 9),
            'mass_kg_allocated': r['mass_kg'], 'mass_basis': r['mass_basis'],
            'representation_role': r['representation_role']})
    added_v = sum(r['volume_mm3'] for r in rows)

    # 实改构件 removed_volume 实算
    exp = RUN / 'exports'
    mods = []
    for n in ['RB_longeron_1_1', 'RB_longeron_-1_1']:
        v_now = import_step(str(exp / f'{n}.step')).volume
        v_base = import_step(str(E2RUN / 'exports' / f'{n}.step')).volume
        mods.append({'instance': n, 'baseline_source': 'r07_e2 exports 同名 STEP（E2 未改纵梁）',
                     'volume_before_mm3': round(v_base, 6), 'volume_after_mm3': round(v_now, 6),
                     'removed_volume_mm3': round(v_base - v_now, 6),
                     'delta_note': '+4 Y 向 Ø3.4 双壁贯穿孔（16mm 包络）'})
    for k in [0, 1]:
        for n in [f'hold_crossbeam_{k}', f'hold_roof_lug_{k}_-94.15', f'hold_pivot_clevis_{k}']:
            v_now = import_step(str(exp / f'{n}.step')).volume
            v_base = baseline_hold(n).volume
            mods.append({'instance': n, 'baseline_source': 'spacecraft_model 同源构造行复建（无 E3 delta）',
                         'volume_before_mm3': round(v_base, 6), 'volume_after_mm3': round(v_now, 6),
                         'removed_volume_mm3': round(v_base - v_now, 6),
                         'delta_note': {'hold_crossbeam': '+4 端面盲孔 Ø3.4深7 +2 竖孔 Ø4.5',
                                        'hold_roof_lug': '+2 竖孔 Ø4.5',
                                        'hold_pivot_clevis': '+2 脚座盲孔 Ø4.5深7 打通至槽底'}[n.rsplit('_', 2)[0] if 'lug' in n else n.rsplit('_', 1)[0]]})
    removed_v = sum(m['removed_volume_mm3'] for m in mods)
    result = {
        'run': 'r07_e3_retention_joints_20260918',
        'density_al_candidate_kg_mm3': RHO_AL,
        'material_status': 'UNKNOWN; 铝 2.7e-6 仅候选估算，钢 7.85e-6 仅参考行',
        'added_part_count': len(rows),
        'modified_member_count': len(mods),
        'modified_members': mods,
        'added_volume_mm3': round(added_v, 6),
        'removed_volume_mm3': round(removed_v, 6),
        'net_volume_mm3': round(added_v - removed_v, 6),
        'added_al_candidate_mass_kg': round(added_v * RHO_AL, 9),
        'removed_al_mass_kg': round(removed_v * RHO_AL, 9),
        'net_al_candidate_mass_delta_kg': round((added_v - removed_v) * RHO_AL, 9),
        'net_allocated_mass_delta_kg': 0.0,
        'mass_allocation_status': 'ALL_E3_PARTS_THREADLESS_ENVELOPE_NOT_ALLOCATED; AL_EQUIVALENT listed for budget only; 非零填（质量状态如实登记为 NOT_ALLOCATED）；改件去除体积为实算（基线 STEP/同源复建 − 本 run 导出 STEP 读回）',
        'rows': rows,
        'elapsed_s': round(time.time() - t0, 3),
    }
    f1 = RUN / 'evidence' / 'e3_bom_mass_delta.json'
    wlf(f1, json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    sidecar(f1)
    with open(RUN / 'evidence' / 'e3_bom_delta.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    sidecar(RUN / 'evidence' / 'e3_bom_delta.csv')
    print('parts', len(rows), 'added_v', round(added_v, 3), 'removed_v', round(removed_v, 3),
          'net_al_kg', round((added_v - removed_v) * RHO_AL, 9), 'elapsed_s', result['elapsed_s'])
    for m in mods:
        print('MOD', m['instance'], 'removed', m['removed_volume_mm3'])

if __name__ == '__main__':
    main()
