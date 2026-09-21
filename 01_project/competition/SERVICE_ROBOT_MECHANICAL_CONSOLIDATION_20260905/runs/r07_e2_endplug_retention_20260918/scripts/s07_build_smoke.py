# -*- coding: utf-8 -*-
"""R07-E2 烟测：build('service', include_arm=False) 整装可建，实例数 = 431(E1 后基线) + 28(E2 保持件) = 459。
构建会刷新 results/service_structure_instances.json（E1 后 431 版已备份于 logs/*.pre_e2_smoke_bak）。"""
import sys, json, hashlib, time
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_e2_endplug_retention_20260918'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, str(ENG))
import spacecraft_model as sm

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
    ids = [r['id'] for r in receipt['instances']]
    e2 = [i for i in ids if i.startswith(('e2_stub_', 'e2_washer_', 'e2_pin_'))]
    envelopes = [r['id'] for r in receipt['instances'] if r['id'] in e2 and r['representation_role'] == 'SIMPLIFIED_PROXY']
    plug_pns = {r['id']: r['pn'] for r in receipt['instances'] if r['id'].startswith('RB_end_plug_')}
    log = {
        'run': 'r07_e2_endplug_retention_20260918', 'check': 'smoke_build_service_structure',
        'command': "spacecraft_model.build('service', include_arm=False)",
        'baseline_instances_e1_closed': 431, 'expected_instances': 459,
        'actual_instances': len(ids),
        'e2_instances': len(e2),
        'e2_breakdown': {'stub': sum(1 for a in e2 if '_stub_' in a),
                         'washer': sum(1 for a in e2 if '_washer_' in a),
                         'wing_pin': sum(1 for a in e2 if '_pin_' in a)},
        'threadless_envelope_instances_not_allocated': len(envelopes),
        'end_plug_pns_unchanged': plug_pns,
        'model_valid': bool(model.is_valid),
        'receipt_file': '20_engineering/service_robot_wp03_spacecraft_body_r1/results/service_structure_instances.json (已按当前源码刷新；E1 后 431 版备份 logs/service_structure_instances.json.pre_e2_smoke_bak)',
        'verdict': 'PASS' if len(ids) == 459 and len(e2) == 28 and model.is_valid else 'FAIL',
        'elapsed_s': round(time.time() - t0, 3),
    }
    f1 = RUN / 'logs' / 's07_build_smoke_log.json'
    wlf(f1, json.dumps(log, ensure_ascii=False, indent=2) + '\n')
    sidecar(f1)
    print(json.dumps({k: log[k] for k in ['actual_instances', 'e2_instances', 'e2_breakdown', 'model_valid', 'verdict']}, ensure_ascii=False))

if __name__ == '__main__':
    main()
