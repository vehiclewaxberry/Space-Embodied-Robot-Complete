from pathlib import Path
import json, hashlib
from datetime import datetime, timezone
R=Path(__file__).resolve().parent
OUT=R/'results';OUT.mkdir(exist_ok=True)
def read(p): return json.loads((R/p).read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def put(name,d): (OUT/name).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
groups=[]
for name in ['INPUT_MANIFEST.json','PREVIOUS_ROUND_LOCK.json']:
 d=read('inputs/'+name); rows=[]
 for x in d['source_snapshot']:
  p=Path(x['path']);actual=sha(p) if p.exists() else None
  rows.append({'path':str(p),'expected_sha256':x['sha256'],'actual_sha256':actual,'unchanged':actual==x['sha256']})
 groups.append({'manifest':name,'file_count':len(rows),'all_unchanged':all(x['unchanged'] for x in rows),'files':rows})
d=read('inputs/ARM_REUSE_INPUT_EXTENSION.json')
rows=[{'path':p,'expected_sha256':h,'actual_sha256':sha(p),'unchanged':sha(p)==h} for p,h in d['source_sha256'].items()]
groups.append({'manifest':'ARM_REUSE_INPUT_EXTENSION.json','file_count':len(rows),'all_unchanged':all(x['unchanged'] for x in rows),'files':rows})
source={'schema':'WP04_ORIGINAL_SOURCE_PROTECTION_V1','checked_at':datetime.now(timezone.utc).isoformat(),'status':'PASS' if all(g['all_unchanged'] for g in groups) else 'FAIL','total_manifest_entries':sum(g['file_count'] for g in groups),'groups':groups,'scope':'Only the explicit input manifests and frozen previous-round files; not a whole-workspace backup.'}
put('SOURCE_PROTECTION.json',source)
assert source['status']=='PASS','Original source changed'
rev=read('review/R07_REVIEW_FINAL.json');three=read('review/R07_THREE_STATE.json')
control=read('review/DIGITAL_BODY_CONTROLS.json');ledger=read('review/ROBOT_ACTUAL_LEDGER_RECHECK.json')
binding=read('contracts/CONTRACT_BINDING_MANIFEST.json');param=read('candidate/results/R07_PARAMETER_PROPAGATION.json')
sections=['contract_checks','validity','local_final_equivalence','holes','bearing_faces','paths','sleeves','shared_pillar_stack','rear_and_axial','reliefs_and_counterbores','candidate5_explicit_reliefs','r01_deck_inventory_regression','r01_angle_inventory_regression']
for s in sections: assert all(x['status']=='PASS' for x in rev[s]),s
assert control['all_passed'] and control['case_count']==63 and binding['final_candidate_bound']
assert ledger['all_passed'] and len(ledger['checks'])==52
assert not rev['affected_static_pairs']['findings']
assert len(rev['affected_static_pairs']['thread_geometry_unknown'])==8
assert len(param['checks'])==8 and all(c['pass_'] for c in param['checks'])
# Verify exact files actually read by final independent geometry and ledger reviewers.
recheck=[]
for f in ['review/R07_REVIEW_FINAL.json','review/R07_THREE_STATE.json','review/ROBOT_ACTUAL_LEDGER_RECHECK.json']:
 d=read(f)
 assert d['input_sha256_before']==d['input_sha256_after'],f
 for p,h in d['input_sha256_after'].items():
  actual=sha(p)
  recheck.append({'audit':f,'path':p,'sha256':h,'current_matches':actual==h})
assert all(x['current_matches'] for x in recheck)
put('FINAL_EVIDENCE_FRESHNESS.json',{'schema':'WP04_FINAL_EVIDENCE_FRESHNESS_V1','status':'PASS','checks':recheck,'entry_count':len(recheck)})
evidence=['review/R07_REVIEW_FINAL.json','review/R07_THREE_STATE.json','review/DIGITAL_BODY_CONTROLS.json','review/ROBOT_ACTUAL_LEDGER_RECHECK.json','contracts/CONTRACT_BINDING_MANIFEST.json','candidate/results/R07_PARAMETER_PROPAGATION.json','candidate/results/POSE_SCREEN.json','candidate/results/R07_DRAWING_PROVENANCE.json','candidate/results/DYNAMICS_HANDOFF.json','candidate/BOM.csv','candidate/INTERFACES.csv','results/SOURCE_PROTECTION.json','results/FINAL_EVIDENCE_FRESHNESS.json']
result={
 'schema':'WP04_ENGINEERING_PROTOTYPE_DELIVERY_V1','run_id':R.name,
 'status':'FULL_DIGITAL_ASSEMBLY_CANDIDATE_DELIVERED__R07_SCOPED_NOMINAL_GEOMETRY_WITH_UNKNOWN',
 'user_target':'可装配工程样机设计：关键连接、机构接口和数字试装',
 'all_mechanical_design_complete':False,'physical_assembly_completed':False,'manufacturing_release':False,
 'flight_qualified':False,'continuous_motion_verified':False,'full_robot_collision_pass':None,
 'hardware_command_authorized':False,'embodied_control_or_learning_executed':False,
 'candidate_scope':{'states':['parking','released','service'],'state_meaning':['OPEN_PARKING_NOT_LAUNCH_STOW','RELEASED_DISCRETE_STATE','SERVICE_DISCRETE_STATE'],'instances_per_state':585,'new_nonarm_STEP_instances':575,'hash_locked_reused_arm_instances':10,'new_R07_instances':96,'geometry_changed_or_added_instances':158,'R07_local_instances':245,'connections':20,'interface_records':585,'drawings_reference_views':6,'manufacturing_dimensions_complete':False},
 'R07_geometry':{'status':rev['status'],'parent_issue_closed':False,'passed_counts':{s:len(rev[s]) for s in sections},'negative_controls':len(rev['negative_controls']['cases']),'static_scope':rev['scope'],'expected_static_pairs':rev['affected_static_pairs']['expected_pair_count'],'narrow_phase_pairs':rev['affected_static_pairs']['narrow_pair_count'],'unresolved_nonthread_intersections_in_scope':0,'bounded_thread_geometry_unknowns':8,'three_state_status':three['status']},
 'parameterization':{'passed_cases':8,'scope':param['scope'],'changed_field':param['parameter'],'full_system_parameterization_verified':False},
 'digital_body':{'final_candidate_bound':True,'software_contract_controls_passed':63,'actual_ledger_checks_passed':52,'hardware_or_scientific_gate_pass':False,'units_or_actuator_fields_without_physical_evidence':None},
 'mass_ledger':{'allocated_subset_mass_kg':20.733608541407722,'allocated_instances':198,'unknown_instances':387,'as_built_total_mass_kg':None,'unknown_mass_bounds_established':False,'arm_digital_mass_counted_once_kg':4.695555949342986,'states':ledger['states']},
 'review_artifact':'../START_HERE_ZH.md','interactive_viewer':'http://127.0.0.1:8767/index.html',
 'viewer_scope':'Display meshes and source references. Final UI checks and display hash bindings are separate in viewer/VIEWER_UI_REVIEW_FINAL.json and the final artifact manifest.',
 'remaining_engineering':[
  'R07 actual thread/engagement, grade, materials, preload, loads and tolerances unresolved; 8 bounded threadless proxy intersections remain UNKNOWN',
  'Retention foot counterbore leaves 2.5 mm floor; fork hole/relief net ligament nominally 1.1327625302982194 mm; structural acceptance not evaluated',
  'Four shortened legacy side screw proxies have zero nominal positive clearance; real fastener selection and tolerance margin not established',
  'R03 guide end retention, stops, return locking, actuator/transmission/sensing hardware and ground support remain open',
  'Rear reinforcement-rib attachment and sleeve temporary positioning/retention remain open',
  'Whole-robot arm/bus/finger containment, adjacent-link topology and continuous release/arm/wing/cable trajectory clearance not certified',
  'Full assembly dependency order and equipment/deck/panel insertion paths not demonstrated by the 128 local path checks',
  '387 unknown mass records; materials, actual hardware limits, harness physical data and mission loads required for verification',
  'Complete GD&T drawings, supplier part selection, strength/FEA, physical fit and manufacturing release remain open'
 ],
 'historical_machine_gates_changed':False,'source_protection_status':source['status'],
 'evidence_sha256':{p:sha(R/p) for p in evidence}
}
put('WP04_RESULT.json',result)
print(json.dumps({'status':result['status'],'source_groups':[{k:g[k] for k in ['manifest','file_count','all_unchanged']} for g in groups],'freshness_checks':len(recheck)},ensure_ascii=False))

