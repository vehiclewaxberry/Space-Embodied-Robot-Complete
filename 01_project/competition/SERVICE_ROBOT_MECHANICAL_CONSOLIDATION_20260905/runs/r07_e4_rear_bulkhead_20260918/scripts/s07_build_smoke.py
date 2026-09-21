# -*- coding: utf-8 -*-
"""R07-E4 烟测：build('service', include_arm=False) 整装可建，实例数 = 483(E3 后基线) + 4(E4 夹套) = 487。
改件 4 螺钉为同名替换（RB_end_screw_-1_*，不增数）。构建会刷新 results/service_structure_instances.json
（E3 后 483 版已备份于 logs/service_structure_instances.json.pre_e4_smoke_bak）。"""
import sys, json, hashlib, time
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_e4_rear_bulkhead_20260918'
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
    e4 = [i for i in ids if i.startswith('e4_clamp_sleeve_')]
    mods = [i for i in ids if i.startswith('RB_end_screw_-1_')]
    mod_len = {r['id']: r for r in receipt['instances'] if r['id'] in mods}
    log = {
        'run': 'r07_e4_rear_bulkhead_20260918', 'check': 'smoke_build_service_structure',
        'command': "spacecraft_model.build('service', include_arm=False)",
        'baseline_instances_e3_closed': 483, 'expected_instances': 487,
        'actual_instances': len(ids),
        'e4_instances': len(e4),
        'e4_breakdown': {'clamp_sleeve': len(e4)},
        'modified_screw_instances_same_name_replaced': len(mods),
        'modified_screw_mass_basis': {k: v['mass_basis'] for k, v in sorted(mod_len.items())},
        'model_valid': bool(model.is_valid),
        'receipt_file': '20_engineering/service_robot_wp03_spacecraft_body_r1/results/service_structure_instances.json (已按当前源码刷新；E3 后 483 版备份 logs/service_structure_instances.json.pre_e4_smoke_bak)',
        'verdict': 'PASS' if len(ids) == 487 and len(e4) == 4 and len(mods) == 4 and model.is_valid else 'FAIL',
        'elapsed_s': round(time.time() - t0, 3),
    }
    f1 = RUN / 'logs' / 's07_build_smoke_log.json'
    wlf(f1, json.dumps(log, ensure_ascii=False, indent=2) + '\n')
    sidecar(f1)
    print(json.dumps({k: log[k] for k in ['actual_instances', 'e4_instances', 'e4_breakdown', 'modified_screw_instances_same_name_replaced', 'model_valid', 'verdict']}, ensure_ascii=False))

if __name__ == '__main__':
    main()
