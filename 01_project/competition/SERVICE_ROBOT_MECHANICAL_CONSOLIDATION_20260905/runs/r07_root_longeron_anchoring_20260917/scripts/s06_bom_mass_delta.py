# -*- coding: utf-8 -*-
"""R07-E1 BOM 与质量增量（铝 2.7e-6 CANDIDATE；材料 UNKNOWN，钢候选仅作参考行）。
新增 48 件（16 栓包络+16 垫圈包络+16 防压套）质量 - 9 件受影响构件打孔去除材料质量。
去除量用"改件前重建件 vs 现行构建件"布尔体积差交叉核对，不用解析式代替实测体积。"""
import sys, json, csv, hashlib, time
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401
from build123d import Location

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_root_longeron_anchoring_20260917'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, str(ENG))
import spacecraft_model as sm
import root_structure as rs
import numpy as np

RHO_AL = 2.7e-6
RHO_ST = 7.85e-6

def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))

def sidecar(p):
    h = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    wlf(str(p) + '.sha256', h + '  ' + Path(p).name + '\n')
    return h

def pre_e1_members():
    """按 E1 前定义重建 9 件（含 WP03 既有剪力/端塞孔，无 E1 孔）。"""
    out = {}
    for sy in [-1, 1]:
        for sz in [-1, 1]:
            rail = rs.tube((354, 12, 12), 2, 'x')
            for x in [-164, 164]:
                rail = rs.bore(rail, 4.5, 16, (x, 0, 0))
            for hx in [-150, -90, -30, 30, 90, 150]:
                rail = rs.bore(rail, 3.4, 16, (hx, -sy, 0))
            if sz < 0:
                for hx in [-144, 144]:
                    rail = rs.bore(rail, 3.4, 16, (hx, 0, 0))
            out[f'RB_longeron_{sy}_{sz}'] = rail.moved(Location((0, sy*107.15, sz*107.15)))
    holes_b = [(x, y, 6.6) for x, y in rs.R['M6_local_xy_mm']] + [(x-90, y, 4.5) for x, y in rs.R['pillar_xy_mm']]
    for i in range(8):
        a = np.radians(22.5+45*i); holes_b.append((62.5*np.cos(a), 62.5*np.sin(a), 12))
    holes_b.append((0, 0, 44))
    out['WP01-RB-BRIDGE-R2'] = rs.plate(rs.R['bridge_mm'], holes_b).moved(Location(tuple(rs.R['bridge_center_mm'])))
    for x in rs.R['crossbeam_x_mm']:
        up = rs.plate(rs.R['upper_crossbeam_mm'], [(0, y, 6.6) for y in [-70, 70]] + [(0, y, 4.5) for y in [-94.15, 94.15]])
        out[f'RB_upper_beam_{x}'] = up.moved(Location((x, 0, 101.15)))
        low = rs.plate(rs.R['lower_crossbeam_mm'], [(0, y, 4.5) for y in [-94.15, 94.15]])
        out[f'RB_lower_beam_{x}'] = low.moved(Location((x, 0, -104.15)))
    return out

def main():
    t0 = time.time()
    ev = RUN / 'evidence'
    model, shapes, receipt = sm.build('service', include_arm=False)
    pre = pre_e1_members()
    members = ['RB_longeron_1_1', 'RB_longeron_-1_1', 'RB_longeron_1_-1', 'RB_longeron_-1_-1',
               'RB_upper_beam_20', 'RB_upper_beam_160', 'RB_lower_beam_20', 'RB_lower_beam_160',
               'WP01-RB-BRIDGE-R2']
    removed = []
    for n in members:
        v_pre = sum(s.volume for s in pre[n].solids())
        v_post = sum(s.volume for s in shapes[n].solids())
        removed.append({'member': n, 'volume_pre_mm3': round(v_pre, 6), 'volume_post_mm3': round(v_post, 6),
                        'removed_mm3': round(v_pre - v_post, 6), 'removed_al_mass_kg': round((v_pre - v_post) * RHO_AL, 9)})
    # 新增 48 件
    added = []
    for p in sm.root_anchoring_parts(sm.P):
        v = sum(s.volume for s in p['shape'].solids())
        added.append({'instance': p['name'], 'kind': p['kind'], 'mount': p['mount'],
                      'volume_mm3': round(v, 6),
                      'al_candidate_mass_kg': round(v * RHO_AL, 9),
                      'steel_reference_mass_kg': round(v * RHO_ST, 9),
                      'mass_status': 'SLEEVE_AL_CANDIDATE_PHYSICAL' if p['kind'] == 'E1_SLEEVE' else 'THREADLESS_ENVELOPE_MATERIAL_UNKNOWN_AL_EQUIVALENT_ONLY'})
    tot_add_v = sum(a['volume_mm3'] for a in added)
    tot_rem_v = sum(r['removed_mm3'] for r in removed)
    tot_add_al = sum(a['al_candidate_mass_kg'] for a in added)
    tot_rem_al = sum(r['removed_al_mass_kg'] for r in removed)
    sleeves_al = sum(a['al_candidate_mass_kg'] for a in added if a['kind'] == 'E1_SLEEVE')
    summary = {
        'run': 'r07_root_longeron_anchoring_20260917', 'density_al_candidate_kg_mm3': RHO_AL,
        'material_status': 'UNKNOWN; 铝 2.7e-6 仅候选估算，钢 7.85e-6 仅参考行',
        'added_part_count': len(added), 'modified_member_count': len(members),
        'added_volume_mm3': round(tot_add_v, 6),
        'removed_volume_mm3': round(tot_rem_v, 6),
        'net_volume_mm3': round(tot_add_v - tot_rem_v, 6),
        'added_al_candidate_mass_kg': round(tot_add_al, 9),
        'removed_al_mass_kg': round(tot_rem_al, 9),
        'net_al_candidate_mass_delta_kg': round(tot_add_al - tot_rem_al, 9),
        'sleeves_al_candidate_mass_kg(in_build_density)': round(sleeves_al, 9),
        'bolts_washers_mass_status': 'THREADLESS_ENVELOPE; mass NOT_ALLOCATED in build; AL_EQUIVALENT listed for budget only',
        'note': '去除体积=改件前重建件与现行 build 件体积差（含全部既有孔系），非解析式',
    }
    out = dict(summary)
    out['added_parts'] = added
    out['modified_members'] = removed
    f1 = ev / 'e1_bom_mass_delta.json'
    wlf(f1, json.dumps(out, ensure_ascii=False, indent=2) + '\n')
    sidecar(f1)
    with open(ev / 'e1_bom_delta.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['instance_or_member', 'role', 'volume_mm3', 'al_candidate_mass_kg', 'status'])
        for a in added:
            w.writerow([a['instance'], a['kind'], a['volume_mm3'], a['al_candidate_mass_kg'], a['mass_status']])
        for r in removed:
            w.writerow([r['member'], 'MODIFIED_MEMBER_REMOVED_MATERIAL', -r['removed_mm3'], -r['removed_al_mass_kg'], 'E1_HOLES_DRILLED'])
    sidecar(ev / 'e1_bom_delta.csv')
    print(json.dumps({k: v for k, v in summary.items() if 'mass' in k or 'volume' in k or 'count' in k}, ensure_ascii=False, indent=1))
    print('elapsed_s', round(time.time() - t0, 2))

if __name__ == '__main__':
    main()
