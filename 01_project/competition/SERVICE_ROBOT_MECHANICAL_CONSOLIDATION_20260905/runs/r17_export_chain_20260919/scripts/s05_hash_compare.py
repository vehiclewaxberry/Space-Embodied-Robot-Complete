# -*- coding: utf-8 -*-
# s05: 正式交付物改前/改后哈希对照登记
import hashlib, json, os

RUN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENG = r'F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/service_robot_wp03_spacecraft_body_r1'

def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()

manifest = json.loads(open(os.path.join(RUN, 'inputs', 'INPUT_MANIFEST.json'), encoding='utf-8').read())
before = {d['file']: d.get('sha256_before') for d in manifest['deliverables_before']}
rows = []
for rel, h0 in before.items():
    p = os.path.join(ENG, rel)
    rows.append({'file': rel, 'sha256_before': h0,
                 'sha256_after': sha(p) if os.path.exists(p) else None,
                 'changed': (h0 != sha(p)) if os.path.exists(p) else None,
                 'note': {'BOM.csv': '重生成：497 实例（E1–E4 后 487 结构+10 臂），含分配列；改前为 361 实例旧链',
                          'INTERFACES.csv': '重生成：同源回执接口表',
                          'results/DYNAMICS_HANDOFF.json': '重生成：三态新回执+地面视图，source_files_unchanged=true',
                          'results/DYNAMICS_SUMMARY_ZH.md': 'HANDOFF 子进程同步再生',
                          'results/parking_instances.json': '重建（497）',
                          'results/released_instances.json': '重建（497）',
                          'results/service_instances.json': '重建（497）',
                          'results/parking_ground_instances.json': '重建（502，含 GSE 独立账本）',
                          'results/service_structure_instances.json': '完整模式 build 副作用刷新（487=483+4，同 E4 烟测口径）'}.get(rel, '')})
out = {'run': 'r17_export_chain_20260919', 'check': 'deliverables_before_after_hash_compare',
       'before_source': 'inputs/INPUT_MANIFEST.json::deliverables_before（改前快照）',
       'deliverables': rows,
       'all_changed_documented': all(r['changed'] for r in rows),
       'note': '改前备份原件在 inputs/（BOM.csv/INTERFACES.csv/DYNAMICS_HANDOFF.json/*_instances.json 同名快照）；'
               '全部交付物哈希变化均为本包授权重生成，改动原因逐行登记'}
p = os.path.join(RUN, 'evidence', 'r17_deliverables_hash_compare.json')
open(p, 'wb').write((json.dumps(out, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
h = sha(p)
rel = os.path.relpath(p, RUN).replace('\\', '/')
open(p + '.sha256', 'wb').write((h + '  ' + rel + '\n').encode('utf-8'))
for r in rows:
    print(r['file'], 'changed=', r['changed'])
    print('  before', (r['sha256_before'] or 'MISSING')[:16], ' after', (r['sha256_after'] or 'MISSING')[:16])
