"""Record reviewed source integration, BOM deltas and remaining exact failures."""
from pathlib import Path
import json,csv,argparse
from battery_variant_context import A,read,sha
ap=argparse.ArgumentParser();ap.add_argument('--snapshots-reviewed',action='store_true');args=ap.parse_args();assert args.snapshots_reviewed
plan=read('mechanical/BATTERY_ROUTE_INSTANCE_PLAN.json');preview=read('mechanical/BATTERY_ROUTE_PREVIEW_INPUTS.json');assert preview['component_count']==85
assert plan['source_script_sha256']==sha(A/'tools/prepare_battery_route_variant.py') and all(sha(A/q)==h for q,h in plan['inputs'].items())
assert all(sha(A/q)==h for q,h in preview['input_sha256'].items())
screens={s:read(f'results/BATTERY_PROPULSION_ROUTE_SCREEN_{s.upper()}.json') for s in plan['states']}
for state,info in plan['states'].items():
    assert len(info['rows'])==893 and len(info['pending_harness_instances_present'])==12
    assert all(sha(q['step_path'])==q['source_sha256'] for q in info['rows'])
    r=screens[state];assert r['source_script_sha256']==sha(A/'tools/check_propulsion_reroute.py') and r['status']=='PROP_ROUTES_AND_DUAL_SUPPORT_GEOMETRY_CLEAR__ELECTRICAL_AND_OTHER_HARNESS_OPEN'
stems=['battery_prop_power','battery_prop_data','battery_dual_base','battery_dual_lid','battery_dual_post','battery_dual_rod','battery_route_deck','battery_route_integration'];checks=[];shots={}
for stem in stems:
    refs=read(f'logs/prop_cad_{stem}_refs.stdout.log');v=read(f'logs/prop_cad_{stem}_validate.stdout.log');r=refs['tokens'][0]
    assert refs['ok'] and v['ok'] and v['failureCount']==0 and r['stepHash']==sha(A/f'mechanical/{stem}.step')
    assert r['summary']['leafOccurrenceCount']==(85 if stem=='battery_route_integration' else 1)
    checks.append(dict(stem=stem,step_sha256=r['stepHash'],leaf_count=r['summary']['leafOccurrenceCount'],geometry_valid=True,bounds=r['summary']['bounds']))
    for line in (A/f'logs/prop_cad_{stem}_snapshot.stdout.log').read_text().splitlines():
        if line.startswith('saved snapshot: '):
            p=Path(line.removeprefix('saved snapshot: '));shots[p.relative_to(A).as_posix()]=sha(p)
assert len(shots)==9
rows={r['id']:r for r in plan['states']['service']['rows']};changed=plan['states']['service']['changed_this_round'];bom=[]
for k in changed:
    r=rows[k];role='FUNCTIONAL_BUNDLE_ENVELOPE_NO_PIN_CUT_LENGTH' if k.startswith('PROP_') else 'REUSED_CATALOGUE_GEOMETRY_RELOCATED' if k.startswith('CLAMP_DUAL_') and k.split('_')[-1] in ['BN','BW','TN','TW'] else 'PROJECT_CUSTOM_GEOMETRY_MATERIAL_PRELOAD_AND_TOLERANCE_OPEN'
    bom.append(dict(instance_id=k,quantity=1,role=role,source_step=r['step_path'],source_sha256=r['source_sha256'],T_S_step=json.dumps(r['T_S_step'],separators=(',',':')),material_or_hardware_release='NOT_RELEASED_BY_THIS_GEOMETRY_INCREMENT',mass_kg='',cut_length_mm='',build_approved=False))
with (A/'mechanical/BATTERY_PROPULSION_INSTANCE_BOM.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(bom[0]));w.writeheader();w.writerows(bom)
paths=['mechanical/BATTERY_PROPULSION_ROUTING.json','mechanical/BATTERY_PROPULSION_ROUTE_BRIEF.md','mechanical/BATTERY_ROUTE_INSTANCE_PLAN.json','mechanical/BATTERY_ROUTE_PREVIEW_INPUTS.json','mechanical/BATTERY_PROPULSION_INSTANCE_BOM.csv','mechanical/battery_propulsion_common.py','tools/battery_variant_context.py','tools/prepare_battery_route_variant.py','tools/check_propulsion_reroute.py','tools/check_release_port_counterexample.py','results/RELEASE_PORT_CLEARANCE_COUNTEREXAMPLE.json']
paths += [f'results/BATTERY_PROPULSION_ROUTE_SCREEN_{s.upper()}.json' for s in plan['states']]
paths += [f'mechanical/{stem}.{ext}' for stem in stems for ext in ['step','step.py']]
r=dict(schema='WP10_PROPULSION_ROUTE_REVIEWED_REVISION_V1',status='THREE_STATE_PROP_GEOMETRY_AND893_SOURCE_VARIANT_DELIVERED__MECHATRONIC_CLOSURE_OPEN',source_script_sha256=sha(__file__),inputs={q:sha(A/q) for q in paths},CAD_checks=checks,snapshots=shots,snapshots_actually_reviewed=True,local_preview_instances=85,complete_source_instance_count_by_state={s:len(v['rows']) for s,v in plan['states'].items()},geometry_pair_checks_by_state={s:r['test_count'] for s,r in screens.items()},changed_instances=17,remaining_pending_harness_ids=plan['states']['service']['pending_harness_instances_present'],critical_clearances=screens['service']['critical_clearances'],full_BRep_assembly_generated=False,full_native_SolidWorks_assembly_generated=False,whole_fit_verified=False,whole_design_complete=False,new_layout_mass_inertia_and_thermal_verified=False,review_disposition=['Single read-only reviewer independently reproduced66 service pairs and checked sources/transforms, positive-volume rules, and localized deck cuts.','All3 fixed states now independently execute66 changed-neighborhood pairs; this does not prove motion or full assembly.','Root OCP confirmed release port1mm parking gap and specificR14 side-approach points inside mast; original functional endpoints retained and no back-face substitute used.','893-instance source tables retain8 old trunk supports and4 old release segments with explicit OPEN responsibility;85-instance preview omits them with caption.'],limits=['D8 clamp support around OD6 bundle has1mm radial room, not gripping-force or liner qualification.','PropulsionDATA start(45,34,59) is an unbound functional handoff replacing a battery-occupied allocation, not an OEM pin.','All source hardware retained through normalized predecessor links; new row count is not a whole-fit release.','Current38 native thermalcore remains separate; no current source/native equivalence for full893 is claimed.'])
r['review_disposition'].append('Single read-only reviewer independently checked590 distinct source-file hashes and all transforms;85 preview rows match the full service source plan and all85 names exist in the exported STEP assembly references. Text/hash review supplies no additional CAD or mass/thermal credit.')
for q in ['tools/reclaim_idle_tool_memory_v9.py','results/PROP_ROUTING_MEMORY_RECOVERY.json']:
    r['inputs'][q]=sha(A/q)
(A/'results/PROP_ROUTING_REVIEW.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
receipts=[];samples=[]
for path in [*(A/'logs').glob('native_delta_prop_corridor*.run.json'),*(A/'logs').glob('native_delta_release_port_counterexample.run.json')]:
    d=json.loads(path.read_text());receipts.append({k:d.get(k) for k in ['name','status','available_start_mib','returncode','elapsed_s']});samples+=d.get('samples',[])
assert all(d['status']!='RUNNING' for d in receipts)
mem=dict(receipts=receipts,minimum_available_mib=min(s['available_mib'] for s in samples),maximum_combined_rss_mib=max(s['combined_rss_mib'] for s in samples),start_floor_mib=2048,runtime_floor_mib=512,owned_rss_and_job_limit_mib=1400,all_jobs_terminal=True)
(A/'results/PROP_ROUTING_MEMORY_AUDIT.json').write_text(json.dumps(mem,indent=2),encoding='utf-8')
print(json.dumps(dict(local_instances=85,source_instances_each_state=893,checks_each_state=66,CAD_entries=8,snapshots=9,changed_BOM_rows=len(bom),memory= {k:mem[k] for k in ['minimum_available_mib','maximum_combined_rss_mib']},whole_design_complete=False)))
