"""Bind reviewed CAD and local counterexample corrections without whole-fit credit."""
from pathlib import Path
import json,hashlib,argparse
A=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--snapshots-reviewed',action='store_true');args=ap.parse_args();assert args.snapshots_reviewed
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
seed=read('results/BATTERY_RELAYOUT_SEED_SCREEN.json');route=read('results/BATTERY_INTERNAL_ROUTE_SCREEN.json');preview=read('mechanical/BATTERY_BAY_PREVIEW_INPUTS.json')
assert seed['status']=='BODY_AND_MOVED_GROUPS_SCREEN_CLEAR__MOUNT_AND_REROUTE_PENDING'
assert route['status']=='ROUTE_BODY_SCREEN_CLEAR__CLAMPS_AND_JUNCTIONS_PENDING' and not route['branch_fit_proved']
for record in [seed,route,preview]:assert all(sha(A/q)==h for q,h in record['input_sha256'].items())
assert all(sha(A/q)==h for q,h in seed['source_override_sha256'].items())
assert all(sha(r['step_path'])==r['source_sha256'] for r in preview['rows'])
stems=['upper_deck_battery_layout','wall_navigation_bosses','arm_adapter_battery_layout','battery_max_envelope','bridge_harness_passage','m3rb_harness_relief','battery_internal_route','battery_bay_layout'];checks=[]
for stem in stems:
    refs=read(f'logs/battery_cad_{stem}_refs.stdout.log');val=read(f'logs/battery_cad_{stem}_validate.stdout.log');t=refs['tokens'][0]
    assert refs['ok'] and val['ok'] and val['failureCount']==0
    assert t['stepHash']==sha(A/f'mechanical/{stem}.step')
    count=t['summary']['leafOccurrenceCount'];assert count==(55 if stem=='battery_bay_layout' else 1)
    checks.append(dict(stem=stem,leaf_occurrences=count,step_sha256=t['stepHash'],geometry_validate=True,bounds=t['summary']['bounds']))
shots={}
for stem in stems:
    log=A/f'logs/battery_cad_{stem}_snapshot.stdout.log'
    if not log.exists():continue
    for line in log.read_text(encoding='utf-8').splitlines():
        if line.startswith('saved snapshot: '):
            path=Path(line.removeprefix('saved snapshot: '));assert path.exists();shots[path.relative_to(A).as_posix()]=sha(path)
assert len(shots)==8,len(shots)
paths=['mechanical/BATTERY_BAY_LAYOUT.json','mechanical/BATTERY_BAY_PREVIEW_INPUTS.json','mechanical/BATTERY_INTERNAL_ROUTE.json','mechanical/BATTERY_HARNESS_PASSAGE.json','mechanical/BATTERY_BAY_BRIEF.md','results/BATTERY_RELAYOUT_SEED_SCREEN.json','results/BATTERY_INTERNAL_ROUTE_SCREEN.json','tools/prepare_battery_bay_preview.py','tools/check_battery_relayout_seed.py','tools/check_battery_internal_route.py','mechanical/battery_passage_common.py','mechanical/heat_layout_relocation.py']
paths += [f'mechanical/{stem}.{ext}' for stem in stems for ext in ['step','step.py']]
r=dict(schema='WP10_BATTERY_BAY_REVIEWED_INCREMENT_V1',status='REVIEWED_LOCAL_GEOMETRY_INCREMENT__A05_AND_HARNESS_OPEN',source_script_sha256=sha(__file__),inputs={q:sha(A/q) for q in paths},CAD_checks=checks,snapshots=shots,snapshots_actually_reviewed=True,local_instances=55,moved_parent_instances=38,parent_service_instances=894,whole_candidate_integrated=False,new_native_SolidWorks_assembly_generated=False,seed_tests=dict(battery=len(seed['battery_tests']),moved=len(seed['moved_group_tests']),host_before_after=len(seed['host_override_vs_untouched_tests'])),route_actual_pairs=route['test_count'],battery_clearance_mm=route['battery']['distance_mm'],whole_design_complete=False,thermal_credit_inherited_from_old_894_layout=False,mechanical_hold_down_verified=False,release_branch_fit_proved=False,
 remaining_geometry_responsibility_ids=preview['omitted_from_this_local_view_but_still_required'],
 review_disposition=[
  'Fixed initial8 moved-component/deck interferences with group shifts and4 new deck holes; preserve archived counterexamples.',
  'Corrected navigation4.65mm support gap with4 integral wall bosses and drive-carrier/root-fastener interference with edge relief.',
  'ActualSTEP verified bridge169.646003mm3 andM3RB68.565260mm3 riser intersections; D10 hole/R5 edge relief now remove only specified material.',
  'Read-only reviewer identified overbroad branch exemptions, missing material-removal locality, and stale preview hash credit. All3 corrected and rechecked.',
  'Independent read-only review confirms current55-instance preview and source hashes; existing release overlap105mm/1319.468915mm3 and each branch/M3RB456.336140mm3 remainOPEN.'
 ],limits=['RRC D maximum rectangular envelope is not manufacturer body/contact BRep.','No battery clamp, insertion or protected terminal/PMM integration credit.','27 pending routes/clamps plus2 release branches explicitly retained as design responsibilities.','No passage strength, sleeve/strain relief, device hold-down, full-state or thermal requalification.','55-instance STEP is a local review assembly; current native38 thermalcore and old894 thermal source remain distinct.'])
(A/'results/BATTERY_BAY_REVIEW.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
receipts=[];samples=[]
for p in (A/'logs').glob('native_delta_battery*.run.json'):
    d=json.loads(p.read_text());receipts.append({k:d.get(k) for k in ['name','started_local','status','returncode','available_start_mib','elapsed_s']});samples+=d.get('samples',[])
mem=dict(schema='WP10_BATTERY_SERIAL_MEMORY_AUDIT_V1',receipts=receipts,minimum_sampled_available_mib=min(s['available_mib'] for s in samples),maximum_sampled_combined_rss_mib=max(s['combined_rss_mib'] for s in samples),start_floor_mib=2048,runtime_floor_mib=512,owned_rss_and_job_commit_limit_mib=1400,cleanup='Owned job resources released at completion; no new app termination in this relayout increment',all_current_jobs_terminal=all(x['status']!='RUNNING' for x in receipts))
assert mem['all_current_jobs_terminal'];(A/'results/BATTERY_MEMORY_AUDIT.json').write_text(json.dumps(mem,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(local_instances=55,validated_CAD_entries=len(checks),snapshots_reviewed=len(shots),minimum_available_mib=mem['minimum_sampled_available_mib'],maximum_combined_rss_mib=mem['maximum_sampled_combined_rss_mib'],whole_design_complete=False)))
