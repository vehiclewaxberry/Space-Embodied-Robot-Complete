"""Publishable evidence receipt only after actual snapshot review."""
import argparse,json,csv
from pathlib import Path
from battery_variant_context import A,read,sha
p=argparse.ArgumentParser();p.add_argument('--snapshots-reviewed',action='store_true');a=p.parse_args();assert a.snapshots_reviewed
plan=read('mechanical/ROOT_BUSHING_INSTANCE_PLAN.json');preview=read('mechanical/ROOT_BUSHING_PREVIEW_INPUTS.json');cfg=read('mechanical/ROOT_BUSHING_DESIGN.json')
assert plan['component_count']==936 and preview['component_count']==136
assert all(sha(A/q)==h for q,h in plan['inputs'].items()) and plan['source_script_sha256']==sha(A/'tools/prepare_root_bushing.py')
assert all(sha(A/q)==h for q,h in preview['inputs'].items())
parent=read(cfg['parent_source_plan']);screens={}
for state,sp in plan['states'].items():
    s=read(f'results/ROOT_BUSHING_SCREEN_{state.upper()}.json');screens[state]=s
    assert s['status']=='ROOT_PASSAGE_STATIC_CAPTURE_CLEAR__THREAD_STRAIN_RELIEF_AND_RELEASE_OPEN' and s['source_plan_sha256']==sha(A/'mechanical/ROOT_BUSHING_INSTANCE_PLAN.json') and s['source_script_sha256']==sha(A/'tools/check_root_bushing.py')
    assert s['test_count']==18 and len(s['contacts'])==6 and all(q['passed'] for group in ['contacts','capture_stops','tool_allocation_tests'] for q in s[group])
    assert s['keeper_insertion']['passed'] and s['keeper_insertion']['travel_mm']==20
    assert not s['collisions'] and not s['unexpected_contacts'] and not s['failures']
    assert all(sha(A/q)==h for q,h in s['inputs'].items()) and all(sha(q)==h for q,h in s['source_hashes'].items())
    rows={r['id']:r for r in sp['rows']};old={r['id']:r for r in parent['states'][state]['rows']}
    assert len(rows)==936 and set(old)<=set(rows) and all(rows[k]==old[k] for k in old if k not in sp['changed_ids'])
    assert len(sp['retained_release_ids'])==4 and all(rows[k]==old[k] for k in sp['retained_release_ids'])
    assert all(sha(r['step_path'])==r['source_sha256'] for r in rows.values())
d=read('results/ROOT_DIMENSIONAL_SCENARIOS.json');assert d['geometric_scenarios_positive'] and not d['tolerance_qualified']
assert all(sha(A/q)==h for q,h in d['inputs'].items())
stems=['root_'+q.lower() for q in ['BUSH_LEFT','BUSH_RIGHT','KEEPER','SCREW_8','BRIDGE']]+['root_bushing_integration','root_bushing_detail'];shots={};checks=[]
for stem in stems:
    refs=read(f'logs/root_cad_{stem}_refs.stdout.log');v=read(f'logs/root_cad_{stem}_validate.stdout.log');token=refs['tokens'][0]
    assert refs['ok'] and v['ok'] and v['failureCount']==0 and token['stepHash']==sha(A/f'mechanical/{stem}.step')
    n=136 if stem=='root_bushing_integration' else 5 if stem=='root_bushing_detail' else 1;assert token['summary']['leafOccurrenceCount']==n
    checks.append(dict(stem=stem,step_sha256=token['stepHash'],leaf_count=n,geometry_valid=True,assembly_self_intersection_skipped=n>1))
    for line in (A/f'logs/root_cad_{stem}_snapshot.stdout.log').read_text().splitlines():
        if line.startswith('saved snapshot: '):
            path=Path(line.removeprefix('saved snapshot: '));shots[path.relative_to(A).as_posix()]=sha(path)
assert len(shots)==8
sp=plan['states']['service'];rows={q['id']:q for q in sp['rows']};bom=[]
for k in sp['changed_ids']+sp['added_ids']:
    r=rows[k];material=cfg['material_candidate']['bushing' if k.startswith('ROOT_BUSH') else 'keeper' if k=='ROOT_KEEPER' else 'screw'] if k.startswith('ROOT_') else 'Existing bridge material remains unqualified for this local hole change'
    bom.append(dict(instance_id=k,change='REPLACED_EXISTING' if k in sp['changed_ids'] else 'ADDED',quantity=1,source_step=r['step_path'],source_sha256=r['source_sha256'],T_S_step=json.dumps(r['T_S_step'],separators=(',',':')),material_candidate=material,torque_Nm='',actual_mass_kg='',manufacture_released=False))
with (A/'mechanical/ROOT_BUSHING_INSTANCE_BOM.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(bom[0]));w.writeheader();w.writerows(bom)
paths=['mechanical/ROOT_BUSHING_DESIGN.json','mechanical/ROOT_BUSHING_BRIEF.md','mechanical/ROOT_BUSHING_INSTANCE_PLAN.json','mechanical/ROOT_BUSHING_PREVIEW_INPUTS.json','mechanical/ROOT_BUSHING_INSTANCE_BOM.csv','mechanical/root_bushing_common.py','tools/prepare_root_bushing.py','tools/check_root_bushing.py','tools/prepare_root_preview.py','tools/check_root_dimensional_scenarios.py','results/ROOT_DIMENSIONAL_SCENARIOS.json',cfg['material_source']['file']]+[f'results/ROOT_BUSHING_SCREEN_{s.upper()}.json' for s in plan['states']]+[f'mechanical/{stem}.{ext}' for stem in stems for ext in ['step','step.py']]
receipts=[read(p.relative_to(A)) for p in (A/'logs').glob('native_delta_root*.run.json')];assert all(r['status']!='RUNNING' for r in receipts);samples=[s for r in receipts for s in r.get('samples',[])]
out=dict(schema='WP10_ROOT_PASSAGE_REVIEWED_V1',source_script_sha256=sha(__file__),status='ROOT_PASSAGE_CAPTURE_AND936_SOURCE_TABLES_DELIVERED__WHOLE_DESIGN_OPEN',inputs={q:sha(A/q) for q in paths},CAD_checks=checks,snapshots=shots,snapshots_actually_reviewed=True,source_instances_by_state={s:936 for s in screens},local_preview_instances=136,detail_instances=5,changed_existing_instances=1,added_instances=5,exact_pairs_by_state={s:r['test_count'] for s,r in screens.items()},required_contacts_by_state={s:len(r['contacts']) for s,r in screens.items()},nominal_capture_stop_areas_mm2=[r['down_0p1_stop_contact_area_mm2'] for r in screens['service']['capture_stops']],known_release_segments_retained=sp['retained_release_ids'],release_10deg_counterexample=screens['parking']['release_10deg_counterexample'],full_native_SolidWorks_assembly_generated=False,full_BRep_assembly_generated=False,full_harness_or_whole_fit_verified=False,material_thread_strength_qualified=False,mass_inertia_thermal_qualified=False,whole_design_complete=False,review_disposition=['Single read-only reviewer confirmed release hardware is unbound functional geometry and supplied10degree endpoint counterexample, then root independently confirmed in actual STEP.','Actual first right tool-shaft collision233.297879693mm3 withRB303 archived; changed to one side-entry keeper and two left-side screw axes.','Reviewer requested real0.1mm lower-stop contact; OCP areas54.286721054/29.498274543mm2 agree with independent analytical areas.','Contract parameters drive CAD and screw datum; original release rows are compared unchanged;0.06mm remaining tolerance scenario is explicitly not qualification.'],memory=dict(all_jobs_terminal=True,minimum_available_MiB=min(s['available_mib'] for s in samples),maximum_combined_RSS_MiB=max(s['combined_rss_mib'] for s in samples),receipt_statuses=[dict(name=r['name'],status=r['status']) for r in receipts]))
(A/'results/ROOT_BUSHING_REVIEW.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(dict(source_instances=936,local_instances=136,BOM_rows=len(bom),snapshots=len(shots),whole_design_complete=False)))
