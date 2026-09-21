# -*- coding: utf-8 -*-
"""R07-E2 BOM/质量增量：E2 新增 28 件均为无螺纹名义包络（NOT_ALLOCATED；AL_EQUIVALENT 仅供预算），
无既有构件修改（removed=0）；净分配质量增量 = 0 kg（包络未分配，非零填：质量状态 NOT_ALLOCATED 如实登记）。"""
import sys, json, csv, hashlib, time
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_e2_endplug_retention_20260918'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, str(ENG))
import spacecraft_model as sm

RHO_AL = 2.7e-6
E2PREFIX = ('e2_stub_', 'e2_washer_', 'e2_pin_')

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
    recs = {r['id']: r for r in receipt['instances'] if r['id'].startswith(E2PREFIX)}
    rows = []
    for name in sorted(recs):
        r = recs[name]
        v = r['volume_mm3']
        rows.append({
            'instance': name, 'kind': ('STUB' if '_stub_' in name else 'WING_PIN' if '_pin_' in name else 'WASHER'),
            'volume_mm3': round(v, 6), 'al_equivalent_mass_kg': round(v * RHO_AL, 9),
            'mass_kg_allocated': r['mass_kg'], 'mass_basis': r['mass_basis'],
            'representation_role': r['representation_role']})
    added_v = sum(r['volume_mm3'] for r in rows)
    result = {
        'run': 'r07_e2_endplug_retention_20260918',
        'density_al_candidate_kg_mm3': RHO_AL,
        'material_status': 'UNKNOWN; 铝 2.7e-6 仅候选估算，钢 7.85e-6 仅参考行',
        'added_part_count': len(rows),
        'modified_member_count': 0,
        'modified_member_note': 'E2 不修改任何既有构件（对偶孔两侧均已存在）→ removed_volume=0（非估算，恒等）',
        'added_volume_mm3': round(added_v, 6),
        'removed_volume_mm3': 0.0,
        'net_volume_mm3': round(added_v, 6),
        'added_al_candidate_mass_kg': round(added_v * RHO_AL, 9),
        'removed_al_mass_kg': 0.0,
        'net_al_candidate_mass_delta_kg': round(added_v * RHO_AL, 9),
        'net_allocated_mass_delta_kg': 0.0,
        'mass_allocation_status': 'ALL_E2_PARTS_THREADLESS_ENVELOPE_NOT_ALLOCATED; AL_EQUIVALENT listed for budget only; 非零填（质量状态如实登记为 NOT_ALLOCATED）',
        'rows': rows,
        'elapsed_s': round(time.time() - t0, 3),
    }
    f1 = RUN / 'evidence' / 'e2_bom_mass_delta.json'
    wlf(f1, json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    sidecar(f1)
    with open(RUN / 'evidence' / 'e2_bom_delta.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    sidecar(RUN / 'evidence' / 'e2_bom_delta.csv')
    print('parts', len(rows), 'added_v', round(added_v, 3), 'al_eq_kg', round(added_v * RHO_AL, 9), 'elapsed_s', result['elapsed_s'])

if __name__ == '__main__':
    main()
