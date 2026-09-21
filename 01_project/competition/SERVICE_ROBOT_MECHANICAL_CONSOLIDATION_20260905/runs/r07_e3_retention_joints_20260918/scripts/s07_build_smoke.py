# -*- coding: utf-8 -*-
"""R07-E3 烟测：build('service', include_arm=False) 整装可建，实例数 = 459(E2 后基线) + 24(E3 保持件) = 483。
构建会刷新 results/service_structure_instances.json（E2 后 459 版已备份于 logs/*.pre_e3_smoke_bak）。"""
import sys, json, hashlib, time
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_e3_retention_joints_20260918'
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
    e3 = [i for i in ids if i.startswith(('e3_clamp_', 'e3_foot_'))]
    envelopes = [r['id'] for r in receipt['instances'] if r['id'] in e3 and r['representation_role'] == 'SIMPLIFIED_PROXY']
    log = {
        'run': 'r07_e3_retention_joints_20260918', 'check': 'smoke_build_service_structure',
        'command': "spacecraft_model.build('service', include_arm=False)",
        'baseline_instances_e2_closed': 459, 'expected_instances': 483,
        'actual_instances': len(ids),
        'e3_instances': len(e3),
        'e3_breakdown': {'clamp_bolt': sum(1 for a in e3 if '_clamp_bolt_' in a),
                         'clamp_washer': sum(1 for a in e3 if '_clamp_washer_' in a),
                         'foot_bolt': sum(1 for a in e3 if '_foot_bolt_' in a),
                         'foot_washer': sum(1 for a in e3 if '_foot_washer_' in a)},
        'threadless_envelope_instances_not_allocated': len(envelopes),
        'model_valid': bool(model.is_valid),
        'receipt_file': '20_engineering/service_robot_wp03_spacecraft_body_r1/results/service_structure_instances.json (已按当前源码刷新；E2 后 459 版备份 logs/service_structure_instances.json.pre_e3_smoke_bak)',
        'verdict': 'PASS' if len(ids) == 483 and len(e3) == 24 and model.is_valid else 'FAIL',
        'elapsed_s': round(time.time() - t0, 3),
    }
    f1 = RUN / 'logs' / 's07_build_smoke_log.json'
    wlf(f1, json.dumps(log, ensure_ascii=False, indent=2) + '\n')
    sidecar(f1)
    print(json.dumps({k: log[k] for k in ['actual_instances', 'e3_instances', 'e3_breakdown', 'model_valid', 'verdict']}, ensure_ascii=False))

if __name__ == '__main__':
    main()
