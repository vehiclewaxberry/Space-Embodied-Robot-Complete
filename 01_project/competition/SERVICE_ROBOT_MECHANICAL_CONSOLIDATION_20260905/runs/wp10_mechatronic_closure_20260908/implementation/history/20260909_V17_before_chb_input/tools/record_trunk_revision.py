"""Bind reviewed CAD to the same full source candidate, retaining all open responsibilities."""
import json,csv,argparse
from pathlib import Path
from battery_variant_context import A,read,sha
p=argparse.ArgumentParser();p.add_argument('--snapshots-reviewed',action='store_true');args=p.parse_args();assert args.snapshots_reviewed
plan=read('mechanical/TRUNK_SUPPORT_INSTANCE_PLAN.json');preview=read('mechanical/TRUNK_SUPPORT_PREVIEW_INPUTS.json');assert plan['component_count']==931 and preview['component_count']==131
assert plan['source_script_sha256']==sha(A/'tools/prepare_trunk_variant.py') and all(sha(A/q)==h for q,h in plan['inputs'].items())
screens={s:read(f'results/TRUNK_SUPPORT_SCREEN_{s.upper()}.json') for s in plan['states']}
for state,s in screens.items():
    assert s['state']==state and s['source_plan_sha256']==sha(A/'mechanical/TRUNK_SUPPORT_INSTANCE_PLAN.json') and s['source_script_sha256']==sha(A/'tools/check_trunk_supports.py')
    assert s['status']=='TRUNK_SUPPORT_STATIC_GEOMETRY_CLEAR__MATERIAL_PRELOAD_AND_RELEASE_BRANCHES_OPEN' and s['test_count']==129 and len(s['required_contacts'])==54 and all(r['passed'] for r in s['required_contacts'])
    assert all(sha(A/q)==h for q,h in s['inputs'].items()) and all(sha(q)==h for q,h in s['source_hashes'].items())
    assert len(plan['states'][state]['rows'])==931 and all(sha(r['step_path'])==r['source_sha256'] for r in plan['states'][state]['rows'])
stack=read('results/TRUNK_NOMINAL_STACK.json');assert stack['passed'] and all(sha(A/q)==h for q,h in stack['inputs'].items())
stems=['trunk_'+q.lower() for q in ['LOW_BASE','HIGH_BASE','CAP','LINER_LOW','LINER_HIGH','SCREW_12','SCREW_14','SCREW_20','DECK','DRIVE_ADAPTER','COMPUTE_ADAPTER']]+['trunk_support_integration'];checks=[];shots={}
for stem in stems:
    refs=read(f'logs/trunk_cad_{stem}_refs.stdout.log');v=read(f'logs/trunk_cad_{stem}_validate.stdout.log');r=refs['tokens'][0];assert refs['ok'] and v['ok'] and v['failureCount']==0 and r['stepHash']==sha(A/f'mechanical/{stem}.step')
    assert r['summary']['leafOccurrenceCount']==(131 if stem=='trunk_support_integration' else 1)
    checks.append(dict(stem=stem,source_sha256=sha(A/f'mechanical/{stem}.step.py'),step_sha256=r['stepHash'],leaf_count=r['summary']['leafOccurrenceCount'],geometry_valid=True))
    for line in (A/f'logs/trunk_cad_{stem}_snapshot.stdout.log').read_text().splitlines():
        if line.startswith('saved snapshot: '):
            q=Path(line.removeprefix('saved snapshot: '));shots[q.relative_to(A).as_posix()]=sha(q)
assert len(shots)==13
sr=plan['states']['service'];rows={r['id']:r for r in sr['rows']};bom=[]
for k in sr['changed_ids']+sr['added_ids']:
    r=rows[k];bom.append(dict(instance_id=k,change='REPLACED_EXISTING' if k in sr['changed_ids'] else 'ADDED',quantity=1,representation=r['representation_role'],source_step=r['step_path'],source_sha256=r['source_sha256'],T_S_step=json.dumps(r['T_S_step'],separators=(',',':')),material_grade_or_liner='',fastener_torque_Nm='',mass_kg='',fabrication_released=False))
with (A/'mechanical/TRUNK_SUPPORT_INSTANCE_BOM.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(bom[0]));w.writeheader();w.writerows(bom)
paths=['mechanical/TRUNK_SUPPORT_DESIGN.json','mechanical/TRUNK_SUPPORT_BRIEF.md','mechanical/TRUNK_SUPPORT_INSTANCE_PLAN.json','mechanical/TRUNK_SUPPORT_PREVIEW_INPUTS.json','mechanical/TRUNK_SUPPORT_INSTANCE_BOM.csv','mechanical/trunk_support_common.py','tools/prepare_trunk_variant.py','tools/check_trunk_supports.py','tools/verify_trunk_nominal_stack.py','results/TRUNK_NOMINAL_STACK.json','results/RELEASE_PORT_CLEARANCE_COUNTEREXAMPLE.json']+[f'results/TRUNK_SUPPORT_SCREEN_{s.upper()}.json' for s in plan['states']]+[f'mechanical/{stem}.{ext}' for stem in stems for ext in ['step','step.py']]
receipts=[read(q.relative_to(A)) for q in (A/'logs').glob('native_delta_trunk*.run.json')];assert all(q['status']!='RUNNING' for q in receipts);samples=[s for q in receipts for s in q.get('samples',[])]
out=dict(schema='WP10_TRUNK_SUPPORT_REVIEWED_V1',source_script_sha256=sha(__file__),status='FOUR_TRUNK_SUPPORTS_AND931_SOURCE_TABLES_DELIVERED__WHOLE_DESIGN_OPEN',inputs={q:sha(A/q) for q in paths},CAD_checks=checks,snapshots=shots,snapshots_actually_reviewed=True,source_instances_by_state={s:931 for s in plan['states']},local_preview_instances=131,changed_existing_instances=11,added_instances=38,exact_pairs_by_state={s:r['test_count'] for s,r in screens.items()},required_contacts_by_state={s:len(r['required_contacts']) for s,r in screens.items()},nominal_fastener_stacks=10,known_release_segments_retained=sr['known_pending_release_ids'],full_native_SolidWorks_assembly_generated=False,full_BRep_assembly_generated=False,full_harness_or_whole_fit_verified=False,materials_preload_strength_qualified=False,mass_inertia_thermal_qualified=False,whole_design_complete=False,review_disposition=['Single read-only reviewer identified adapter plates under the high foot, then checked original holes remain outside the revised edge window.','Actual STEP counterexamples460mm3 connector interference and5.15638mm3 screw-hole infill archived; high station moved15mm and support bore recut after union.','Reviewer requested predecessorSHA binding and mandatory bearing contact; root added both and all3 states passed129 pairs and54 required positive-area contacts.','All8 old support IDs are replaced, not deleted; all4 release segments remain present and OPEN; new materials and fastening qualification are not inferred from static geometry.'],memory=dict(all_jobs_terminal=True,minimum_available_MiB=min(s['available_mib'] for s in samples),maximum_combined_RSS_MiB=max(s['combined_rss_mib'] for s in samples),receipt_statuses=[dict(name=q['name'],status=q['status']) for q in receipts]))
(A/'results/TRUNK_SUPPORT_REVIEW.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(dict(local_instances=131,source_instances=931,BOM_rows=len(bom),snapshots=len(shots),whole_design_complete=False)))
