"""Report the actual V19 working candidate, without inheriting historical review credit."""
from pathlib import Path
import ast,json,hashlib,datetime,csv
import psutil
from c203_surface_generation_contract_v19 import A,read,sha,validate_receipt,SPECS
from prepare_cap_harness_plan_v19 import validate_plan
def proof(path):
 v=read(path);assert v['passed'] is True,path
 assert all(sha(p)==h for p,h in v['inputs'].items()),'Stale evidence: '+path
 return v
def observation(path):
 if not (A/path).is_file():return dict(exists=False,current=False)
 v=read(path);bindings=v.get('inputs',v.get('reviewed_files',{}))
 if 'target' in v and 'target_sha256' in v:
  bindings={v['target']:v['target_sha256'],**v.get('records',{})}
  if 'published_image' in v:bindings[v['published_image']]=v['published_sha256']
 if 'images' in v:bindings=v['images']
 return dict(exists=True,sha256=sha(path),current=bool(bindings) and all((A/p).is_file() and sha(p)==h for p,h in bindings.items()))
def main():
 plan=read('mechanical/CAP_HARNESS_INSTANCE_PLAN_V19.json');validate_plan(plan,require_generated=plan['source_geometry_fresh'])
 path=proof('results/CAP_HARNESS_PATH_V19.json');surface=proof('results/C203_SURFACE_PROFILE_CHECK_V19.json')
 pad=proof('results/C203_WIRE_PTH_SOURCE_CHECK_V19.json');native=proof('results/C203_WIRE_PTH_NATIVE_CHECK_V19.json')
 heat=proof('power/CAP_HARNESS_ELECTROTHERMAL_V19.json');active=read('thermal/ACTIVE_HEAT_LOADS_V19.json')
 assert heat['state_count']==384 and heat['heat_rows']==4800 and sha(heat['output_csv'])==heat['output_sha256']
 assert active['calculation_sha256']==sha(active['calculation']) and active['source_assembly_sha256']==sha(active['source_assembly'])
 assert active['heat_dataset_sha256']==sha(active['heat_dataset']) and not active['add_to_parent']
 assert not heat['whole_design_complete'] and not active['whole_thermal_verified']
 fresh={k:validate_receipt(k)['output_sha256'] for k in SPECS} if plan['source_geometry_fresh'] else {}
 pending=['results/CAP_HARNESS_EXACT_V19.json','results/CAP_HARNESS_CAD_REVIEW_V19.json','results/CAP_HARNESS_SNAPSHOT_V19.json','results/CAP_HARNESS_VISUAL_REVIEW_V19.json']
 reviews=['results/CAP_HARNESS_READONLY_REVIEW_V19.json','results/CAP_HARNESS_HEAT_READONLY_REVIEW_V19.json','results/C203_WIRE_PTH_READONLY_REVIEW_V19.json','results/C203_SURFACE_READONLY_REVIEW_V19.json','results/C203_SURFACE_EXACT_READONLY_REVIEW_V19.json']
 sw=[p.info for p in psutil.process_iter(['pid','name','create_time']) if (p.info['name'] or '').casefold()=='sldworks.exe']
 original=A/'history/20260909_V18_before_cap_harness/SYSTEM_CLOSURE_MATRIX.csv'
 rows=list(csv.DictReader((A/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig')))
 oldrows=list(csv.DictReader(original.open(encoding='utf-8-sig')))
 assert len(rows)==37 and [(r['id'],r['status']) for r in rows]==[(r['id'],r['status']) for r in oldrows]
 paths=['mechanical/CAP_HARNESS_INSTANCE_PLAN_V19.json','results/CAP_HARNESS_PATH_V19.json','results/C203_SURFACE_PROFILE_CHECK_V19.json','results/C203_WIRE_PTH_SOURCE_CHECK_V19.json','results/C203_WIRE_PTH_NATIVE_CHECK_V19.json','power/CAP_HARNESS_ELECTROTHERMAL_V19.json','thermal/ACTIVE_HEAT_LOADS_V19.json','SYSTEM_CLOSURE_MATRIX.csv','tools/check_cap_harness_working_v19.py']
 out=dict(status='V19_WORKING_CANDIDATE__NATIVE_WIRE_PTH_REPAIR_VERIFIED__FULL_DESIGN_OPEN',timestamp=datetime.datetime.now().astimezone().isoformat(),
  previous_goal_turn_classification='progress',source_plan='mechanical/CAP_HARNESS_INSTANCE_PLAN_V19.json',source_plan_sha256=sha('mechanical/CAP_HARNESS_INSTANCE_PLAN_V19.json'),
  source_instances_by_state={s:len(v['rows']) for s,v in plan['states'].items()},unchanged_parent_instances=965,changed_parent_instances=5,added_wire_instances=2,
  fresh_STEP_outputs=fresh,surface_checks=len(surface['checks']),surface_faults_rejected=len(surface['faults']),analytic_checks=len(path['checks']),analytic_faults_rejected=len(path['faults']),
  heat_states=heat['state_count'],heat_faults_rejected=len(heat['faults']),C203_current_DRC_count=native['remaining_DRC_errors'],C203_current_DRC_types={'hole_clearance':4,'solder_mask_bridge':2},
  native_evidence={p:observation(p) for p in pending},read_only_reviews={p:observation(p) for p in reviews},
  solidworks_processes_observed=sw,available_mib=psutil.virtual_memory().available/2**20,active_published_revision=read('results/DELIVERY_DECISION.json')['revision'],
  V19_published=False,whole_design_complete=False,goal_complete=False,manufacturing_release=False,original_37_statuses_preserved=True,inputs={p:sha(p) for p in paths},
  open_items=['Two CAP NPTH groups: four hole_clearance and two solder_mask_bridge violations','Capacitor wire strain relief and assembly/solder tooling','Current geometry exact/contact checks and visual evidence must be current before publishing','Physical tolerance, sealing rubber, PTH barrels, solder and preload qualification','CHB local surface/contact profile remains to be evaluated','System thermal, battery/PMM and same-revision propulsion closure remain open'])
 (A/'results/CAP_HARNESS_WORKING_STATUS_V19.json').write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
 print(json.dumps({k:out[k] for k in ['status','source_instances_by_state','fresh_STEP_outputs','surface_checks','surface_faults_rejected','C203_current_DRC_count','available_mib','V19_published','whole_design_complete']}))
if __name__=='__main__':main()
