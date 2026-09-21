# -*- coding: utf-8 -*-
"""R07-E4 BOM/质量增量：
- 新增 4 件阶梯夹套 = 真实铝候选 CAD_ESTIMATE（E1 防压套先例：GOLD/PHYSICAL_GEOMETRY，
  build 内按 density 2.7e-6 记质量；材料牌号/压溃/承压 UNKNOWN，非零填）；
- 改件 4 件后场螺钉 M4×22→M4×30 仍为无螺纹名义包络 SIMPLIFIED_PROXY（NOT_ALLOCATED）：
  体积差实算 = 本 run build 回执体积 − 同源复建基线 rs.screw(4,22,7,4)（平移不变量，无需定位）；
- 无任何既有构件改孔（Ø8 窗口/端框 Ø4.5/端塞 Ø3.3 均既有未动）：removed_volume = 0；
- 净分配质量增量 = 4 夹套质量和（改件螺钉包络前后均 NOT_ALLOCATED，不计分配）。"""
import sys, json, csv, hashlib, time
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_e4_rear_bulkhead_20260918'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, str(ENG))
import spacecraft_model as sm
import root_structure as rs

RHO_AL = 2.7e-6

def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))

def sidecar(p):
    h = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    rel = Path(p).resolve().relative_to(RUN).as_posix()
    wlf(str(p) + '.sha256', h + '  ' + rel + '\n')
    return h

def main():
    t0 = time.time()
    model, shapes, receipt = sm.build('service', include_arm=False)
    recs = {r['id']: r for r in receipt['instances']}
    E4 = sm.P['rear_bulkhead_clamp_r07_e4']
    spec = sm.rear_bulkhead_clamp_spec(sm.P)

    # 新增夹套（真实铝候选 CAD_ESTIMATE，build 内已记质量）
    rows_add = []
    for r in spec:
        rid = f"e4_clamp_sleeve_{r['group']}"
        rec = recs[rid]
        rows_add.append({'instance': rid, 'kind': 'CLAMP_SLEEVE',
                         'volume_mm3': rec['volume_mm3'],
                         'mass_kg_allocated': rec['mass_kg'],
                         'mass_basis': rec['mass_basis'],
                         'representation_role': rec['representation_role'],
                         'al_density_check_kg': round(rec['volume_mm3'] * RHO_AL, 15)})
    added_v = sum(r['volume_mm3'] for r in rows_add)
    added_m = sum(r['mass_kg_allocated'] for r in rows_add)

    # 改件螺钉（包络 NOT_ALLOCATED）：体积差实算 vs 同源复建基线
    v_base_screw = rs.screw(4, 22, 7, 4).volume
    rows_mod = []
    for r in spec:
        rid = r['screw']
        rec = recs[rid]
        rows_mod.append({'instance': rid, 'kind': 'REAR_SCREW_ENVELOPE_M4X22_TO_M4X30',
                         'baseline_source': 'root_structure.screw(4,22,7,4) 同源复建（体积平移不变量）',
                         'volume_before_mm3': v_base_screw,
                         'volume_after_mm3': rec['volume_mm3'],
                         'delta_volume_mm3': rec['volume_mm3'] - v_base_screw,
                         'delta_al_equivalent_kg': round((rec['volume_mm3'] - v_base_screw) * RHO_AL, 12),
                         'mass_kg_allocated': rec['mass_kg'], 'mass_basis': rec['mass_basis'],
                         'representation_role': rec['representation_role'],
                         'pn_candidate': E4['rear_screw']['pn_candidate'],
                         'note': '延长仅在头侧（锚点 -183→-191）；与端塞啮合段 x[-177,-161] 逐位不变'})
    mod_dv = sum(r['delta_volume_mm3'] for r in rows_mod)

    result = {
        'run': 'r07_e4_rear_bulkhead_20260918',
        'density_al_candidate_kg_mm3': RHO_AL,
        'material_status': 'UNKNOWN; 铝 2.7e-6 仅候选估算（E1 防压套先例），材料牌号/压溃/承压 UNKNOWN，非零填',
        'added_part_count': len(rows_add),
        'modified_part_count': len(rows_mod),
        'added_volume_mm3': added_v,
        'added_sleeve_al_candidate_mass_kg': added_m,
        'modified_screw_delta_volume_mm3': mod_dv,
        'modified_screw_delta_al_equivalent_kg': round(mod_dv * RHO_AL, 12),
        'removed_volume_mm3': 0.0,
        'removed_volume_note': '本边不新增任何孔：Ø8 窗口/端框 Ø4.5 孔/端塞 Ø3.3 导孔均既有未改；无构件去除体积',
        'net_allocated_mass_delta_kg': added_m,
        'mass_allocation_status': '夹套 4 件真实铝候选 CAD_ESTIMATE（build 内 density 记质量，E1 先例）；改件螺钉 4 件包络 NOT_ALLOCATED（前后同口径，体积差仅供预算）；净分配增量=夹套质量和',
        'added_parts': rows_add,
        'modified_parts': rows_mod,
        'elapsed_s': round(time.time() - t0, 3),
    }
    f1 = RUN / 'evidence' / 'e4_bom_mass_delta.json'
    wlf(f1, json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    sidecar(f1)
    allrows = [dict(row_type='ADDED', **r) for r in rows_add] + [dict(row_type='MODIFIED', **r) for r in rows_mod]
    keys = sorted({k for r in allrows for k in r.keys()})
    with open(RUN / 'evidence' / 'e4_bom_delta.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(allrows)
    sidecar(RUN / 'evidence' / 'e4_bom_delta.csv')
    print('sleeves', len(rows_add), 'added_v', round(added_v, 6), 'sleeve_mass_kg', round(added_m, 12))
    print('screws', len(rows_mod), 'delta_v_per', round(rows_mod[0]['delta_volume_mm3'], 9),
          'delta_v_total', round(mod_dv, 6), 'net_allocated_delta_kg', round(added_m, 12))

if __name__ == '__main__':
    main()
