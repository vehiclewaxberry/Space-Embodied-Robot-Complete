# -*- coding: utf-8 -*-
# s07: 整装烟测——确认 R17 包未破坏 487 实例口径（结构态 = 483 + E4 夹套 4；全态回执 497 = 487+10 臂）
import hashlib, json, os, sys, time

RUN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENG = r'F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401
sys.path.insert(0, ENG)
import spacecraft_model as sm

def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()

def sidecar(p):
    h = sha(p)
    rel = os.path.relpath(p, RUN).replace('\\', '/')
    open(p + '.sha256', 'wb').write((h + '  ' + rel + '\n').encode('utf-8'))

t0 = time.time()
model, shapes, receipt = sm.build('service', include_arm=False)
ids = [r['id'] for r in receipt['instances']]
e4 = [i for i in ids if i.startswith('e4_clamp_sleeve_')]
structure_receipt = os.path.join(ENG, 'results', 'service_structure_instances.json')
full = json.loads(open(os.path.join(ENG, 'results', 'service_instances.json'), encoding='utf-8').read())
log = {'run': 'r17_export_chain_20260919', 'check': 'smoke_build_service_structure_after_r17',
       'expected_structure_instances': 487, 'actual_structure_instances': len(ids),
       'e4_clamp_sleeve_instances': len(e4), 'model_valid': bool(model.is_valid),
       'structure_receipt_hash_after_build': sha(structure_receipt),
       'full_service_receipt_instances': len(full['instances']),
       'full_receipt_note': '497 = 487 结构 + 10 B601 臂 link',
       'verdict': 'PASS' if len(ids) == 487 and len(e4) == 4 and model.is_valid and len(full['instances']) == 497 else 'FAIL',
       'elapsed_s': round(time.time() - t0, 3)}
p = os.path.join(RUN, 'logs', 's07_build_smoke_log.json')
open(p, 'wb').write((json.dumps(log, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
sidecar(p)
print(json.dumps({k: log[k] for k in ['actual_structure_instances', 'e4_clamp_sleeve_instances', 'model_valid', 'full_service_receipt_instances', 'structure_receipt_hash_after_build', 'verdict']}, ensure_ascii=False))
