# -*- coding: utf-8 -*-
"""R07-E1 烟测：build('service', include_arm=False) 整装可建，实例数 = 383(R01 后基线) + 48(新增锚固件) = 431。
构建会刷新 results/service_structure_instances.json（改件前旧版已备份于 logs/*.pre_e1_smoke_bak）。"""
import sys, json, hashlib, time
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_root_longeron_anchoring_20260917'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, str(ENG))
import spacecraft_model as sm

def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))

def sidecar(p):
    h = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    wlf(str(p) + '.sha256', h + '  ' + Path(p).name + '\n')
    return h

def main():
    t0 = time.time()
    model, shapes, receipt = sm.build('service', include_arm=False)
    ids = [r['id'] for r in receipt['instances']]
    anchors = [i for i in ids if i.startswith('e1_anchor_')]
    sleeves = {r['id']: r['mass_kg'] for r in receipt['instances'] if r['id'].startswith('e1_anchor_sleeve')}
    envelopes = [r['id'] for r in receipt['instances'] if r['id'].startswith('e1_anchor_') and r['representation_role'] == 'SIMPLIFIED_PROXY']
    pns = {r['id']: r['pn'] for r in receipt['instances'] if r['id'] in
           ['RB_upper_beam_20', 'RB_upper_beam_160', 'RB_lower_beam_20', 'RB_lower_beam_160', 'WP01-RB-BRIDGE-R2']}
    log = {
        'run': 'r07_root_longeron_anchoring_20260917', 'check': 'smoke_build_service_structure',
        'command': "spacecraft_model.build('service', include_arm=False)",
        'baseline_instances_r01_closed': 383, 'expected_instances': 431,
        'actual_instances': len(ids),
        'anchor_instances': len(anchors),
        'anchor_breakdown': {'bolt': sum(1 for a in anchors if '_bolt_' in a),
                             'washer': sum(1 for a in anchors if '_washer_' in a),
                             'sleeve': sum(1 for a in anchors if '_sleeve_' in a)},
        'sleeve_mass_kg_minmax': [min(sleeves.values()), max(sleeves.values())] if sleeves else None,
        'threadless_envelope_instances_not_allocated': len(envelopes),
        'modified_member_pns': pns,
        'model_valid': bool(model.is_valid),
        'receipt_file': '20_engineering/service_robot_wp03_spacecraft_body_r1/results/service_structure_instances.json (已按当前源码刷新；旧版备份 logs/service_structure_instances.json.pre_e1_smoke_bak)',
        'verdict': 'PASS' if len(ids) == 431 and len(anchors) == 48 and model.is_valid else 'FAIL',
        'elapsed_s': round(time.time() - t0, 3),
    }
    f1 = RUN / 'logs' / 's07_build_smoke_log.json'
    wlf(f1, json.dumps(log, ensure_ascii=False, indent=2) + '\n')
    sidecar(f1)
    print(json.dumps({k: log[k] for k in ['actual_instances', 'anchor_instances', 'anchor_breakdown', 'model_valid', 'verdict']}, ensure_ascii=False))

if __name__ == '__main__':
    main()
