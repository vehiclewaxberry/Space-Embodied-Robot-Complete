# -*- coding: utf-8 -*-
# s00: 输入快照清单 + 正式交付物改前哈希登记（改前基线，供改后对照）
import hashlib, json, os, time

RUN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENG = r'F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/service_robot_wp03_spacecraft_body_r1'

def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()

inputs = []
for fn in sorted(os.listdir(os.path.join(RUN, 'inputs'))):
    p = os.path.join(RUN, 'inputs', fn)
    if os.path.isfile(p):
        inputs.append({'file': 'inputs/' + fn, 'bytes': os.path.getsize(p), 'sha256': sha(p)})

deliverables = ['BOM.csv', 'INTERFACES.csv',
                'results/DYNAMICS_HANDOFF.json', 'results/DYNAMICS_SUMMARY_ZH.md',
                'results/parking_instances.json', 'results/released_instances.json',
                'results/service_instances.json', 'results/parking_ground_instances.json',
                'results/service_structure_instances.json']
before = []
for rel in deliverables:
    p = os.path.join(ENG, rel)
    if os.path.exists(p):
        before.append({'file': rel, 'bytes': os.path.getsize(p), 'sha256_before': sha(p)})
    else:
        before.append({'file': rel, 'missing': True})

# 改前回执新鲜度审计（新校验器视角的既成事实记录）
cur_model = sha(os.path.join(ENG, 'spacecraft_model.py'))
stale_audit = {'current_spacecraft_model_sha256': cur_model, 'receipts': []}
for rel in ['results/parking_instances.json', 'results/released_instances.json',
            'results/service_instances.json', 'results/parking_ground_instances.json']:
    d = json.loads(open(os.path.join(ENG, rel), encoding='utf-8').read())
    stale_audit['receipts'].append({
        'file': rel, 'state': d.get('state'), 'view': d.get('view'),
        'instance_count': len(d['instances']),
        'recorded_model_sha256': d.get('source_sha256'),
        'matches_current_model': d.get('source_sha256') == cur_model,
        'dependency_matches': {n: sha(os.path.join(ENG, n)) == h for n, h in d.get('dependency_sha256', {}).items()}})

out = {'run': 'r17_export_chain_20260919', 'check': 's00_input_snapshot_and_before_hashes',
       'inputs': inputs, 'deliverables_before': before,
       'pre_fix_staleness_audit': stale_audit,
       'note': 'issues.json R17 字段 current_BOM_is_proven_stale=false 记录于 2026-09-06 审计（11 项交接输入哈希当时匹配）；'
               '此后 E1–E4 改件变更 spacecraft_model.py，三态回执未同步重建——本审计如实记录当前失配事实，不回写原票字段',
       'elapsed_s': 0}
t0 = time.time()
p1 = os.path.join(RUN, 'inputs', 'INPUT_MANIFEST.json')
open(p1, 'wb').write((json.dumps(out, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))

def sidecar(p):
    h = sha(p)
    rel = os.path.relpath(p, RUN).replace('\\', '/')
    open(p + '.sha256', 'wb').write((h + '  ' + rel + '\n').encode('utf-8'))

for it in inputs:
    sidecar(os.path.join(RUN, it['file']))
sidecar(p1)
print('inputs', len(inputs), 'deliverables_before', len(before))
for r in stale_audit['receipts']:
    print('STALE-AUDIT', r['file'], 'instances', r['instance_count'], 'model_match', r['matches_current_model'], 'deps', r['dependency_matches'])
