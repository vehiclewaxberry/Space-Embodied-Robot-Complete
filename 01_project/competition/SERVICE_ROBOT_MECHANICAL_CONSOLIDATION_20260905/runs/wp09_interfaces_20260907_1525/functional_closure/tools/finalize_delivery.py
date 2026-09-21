"""Delivery snapshot and integrity seal. Does not rerun CAD or touch hardware."""
from pathlib import Path
import json,csv,hashlib,re,collections,datetime
F=Path(__file__).resolve().parents[1];R=F.parent
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def bind(p):p=Path(p);return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
parent=read(F/'inputs/PARENT_BINDING.json');parentcheck=[]
for p,h in parent['sources'].items():parentcheck.append(dict(path=p,ok=Path(p).exists() and sha(p)==h))
with (R/'results/OUTPUT_SHA256.csv').open(encoding='utf-8-sig',newline='') as f:
 for row in csv.DictReader(f):
  p=R/row['path'];parentcheck.append(dict(path=str(p),ok=p.exists() and sha(p)==row['sha256']))
assert all(x['ok'] for x in parentcheck),'Parent changed: '+str([x for x in parentcheck if not x['ok']])
parts=read(F/'results/NATIVE_PORTS_MATERIAL.json');local=read(F/'results/NATIVE_LOCAL_PORTS.json');elec=read(F/'results/ELECTRICAL_CALCULATIONS.json');proto=read(F/'results/OFFLINE_PROTOCOL_CHECK.json');prop=read(F/'results/PROPULSION_SCREEN_RESULTS.json');geo=read(F/'results/PORTS_CHECK.json')
assert parts['status']=='PASS_NATIVE_PORTS_MATERIAL' and len(parts['records'])==5
for q in parts['records']:assert sha(q['native_path'])==q['native_sha256'] and q['ok']
assert local['status']=='PASS_LOCAL_NATIVE_ASSEMBLY_5_COMPONENTS_5_ACTUAL_SOLIDS' and sha(local['native_save']['path'])==local['native_save']['sha256']
assert elec['negative_controls_passed'] and len(elec['negative_controls'])==15
assert proto['test_count']==19 and all(t['passed'] for t in proto['tests'])
assert prop['self_check_count']==16 and prop['source_inputs_unchanged_after']
assert geo['status']=='PASS_SCOPED_GSE_PORT_GEOMETRY'
model=read(F/'ecad/CIRCUIT_MODEL.json');assert len(model['wires'])==23 and all(x['physical_status']=='NOT_EXECUTED' and x['build_approved'] is False and x['cut_length_mm'] is None for x in model['wires'])
checklists=[]
for name in ['PROP_DATA_PREFAB_CHECKLIST.csv','PROP_PWR_PREFAB_CHECKLIST.csv']:
 with (F/'ecad'/name).open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
 assert len(rows)==12 and all('NOT_EXECUTED' in list(x.values()) for x in rows)
 checklists.append(dict(path=name,count=12,physical_executed=0))
archive=F/'candidate/rejected_camera_overlap';ae=read(archive/'EMISSION.json');am=[]
for k,q in ae['parts'].items():
 p=archive/'parts'/(k+'.step');assert sha(p)==q['sha256'];am.append(dict(id=k,original_active_path=q['path'],archived=bind(p)))
write(archive/'ARCHIVE_NOTE.json',dict(status='REJECTED_CAMERA_OVERLAP_NOT_CURRENT',old_PWR_yz_mm=[-70,55],current_PWR_yz_mm=[70,55],all_archived_part_hashes_verified=True,part_mapping=am,source=bind(archive/'functional_ports.py'),note='Original receipt active paths are historical only; use hash-verified archived paths above'))
full=dict(status='UNVERIFIED_FULL_ASSEMBLY_DELTA_AFTER_INTERRUPTION_AND_MEMORY_GUARD',service_saved_file=bind(F/'native/WP09F_SERVICE.SLDASM'),service_cold_read_verified=False,parking_delta_generated=False,released_delta_generated=False,expected_components_per_state=705,expected_solids_per_state=1086,counts_are_prediction_not_verified_delivery=True,initial_receipt=bind(F/'results/NATIVE_SERVICE.json'),memory_guard=bind(F/'logs/native_service_recovery.run.json'),memory_floor_prestart_rejection=bind(F/'logs/native_service_recovery_resume.run.json'),own_clean_session_cleanup=bind(F/'results/OWN_SESSION_CLEANUP.json'),verified_parent_states=read(R/'results/DELIVERY_STATUS.json')['native_states'])
write(F/'results/NATIVE_FULL_INTEGRATION_STATUS.json',full)
status=dict(schema='WP09F_DELIVERY_SNAPSHOT',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='CANDIDATE_ELECTRICAL_PROPULSION_PACKAGE_AND_LOCAL_NATIVE_PORTS_DELIVERED__FULL_FUNCTIONAL_AND_GLOBAL_NATIVE_DELTA_OPEN',user_baseline='B601_DM_PUBLIC_REBOT_PARTS; SHIPMENT_NOT_BOUND',native_local=dict(assembly=bind(local['native_save']['path']),parts=5,component_count=5,actual_solid_count=5,cold_reopen_verified=True,parts_material_roundtrip_verified=True,fixed_assembly_only=True,editable_native_feature_history=False,self_contained_pack_and_go=False),global_native_delta=bind(F/'results/NATIVE_FULL_INTEGRATION_STATUS.json'),geometry=dict(status=geo['status'],scope=geo['scope'],pair_count=len(geo['pairs']),current_ports_yz_mm=[[70,55],[-70,-55]],continuous_motion_verified=False,retention_strength_verified=False),electrical=dict(conductors=23,negative_controls=15,independent_review=bind(F/'results/ELECTRICAL_INDEPENDENT_REVIEW_V2.json'),native_eda_erc=False,fully_released_circuits=0,physical_tests=0,physical_tests_planned=24,protocol_offline_tests=19),propulsion=dict(status=prop['status'],self_checks=16,actual_vendor_task_capability='UNKNOWN',pressure_hardware_executed=False),mechanical_release=False,electrical_release=False,flight_release=False,scientific_gate_credit=False,parent_frozen_assets_unchanged=True,open_blockers=['K1 part, coil/control/feedback and DC fault break requirements','DM V4 received connectors/termination/isolation and harness endpoint identities','Regenerative energy, input-loss absorption and resistor pulse thermal ratings','PDU regulated output transient precision and actual connector crimp combination','Dock/BPX/solar charge interfaces and final power/mass budget','Actual propulsion numbered nozzle ICD and task vector/resource binding','Gland nut stack, torque, strain relief, cover strength and service motion','Full three-state native delta validation blocked after interruption/resource guard'])
write(F/'results/DELIVERY_STATUS.json',status)
linkchecks=[]
for p in [F/'README.md',*sorted((F/'docs').glob('*.md'))]:
 for u in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
  if '://' in u or u.startswith('#'):continue
  q=(p.parent/u.split('#')[0].strip('<>')).resolve();linkchecks.append(dict(document=str(p),link=u,exists=q.exists() or q==F/'results/FINAL_INTEGRITY.json'))
assert all(x['exists'] for x in linkchecks),str([x for x in linkchecks if not x['exists']])
integrity=dict(status='PASS_DECLARED_DELIVERY_INTEGRITY_AND_PARENT_PRESERVATION',parent_checks=len(parentcheck),parent_checks_all_pass=True,parent_results=parentcheck,local_link_checks=len(linkchecks),links_all_present=True,local_links=linkchecks,checks_involve_no_physical_hardware=True,checklists=checklists,visual_review=dict(saved_primary_snapshot=bind(F/'viewer/PORTS_20260907T093757Z.png'),schematic_pngs_inspected=4,dimension_drawing_png_inspected=True,viewer_open_and_loaded=True),seal_excludes=['results/OUTPUT_SHA256.csv itself','__cadgen__ caches','__pycache__ caches','logs/viewer_start* active server logs'],scope='File integrity plus declared checks; not electrical ERC, manufacturing or science release')
write(F/'results/FINAL_INTEGRITY.json',integrity)
paths=[p for p in F.rglob('*') if p.is_file() and '__cadgen__' not in p.parts and '__pycache__' not in p.parts and not p.name.startswith('viewer_start') and p!=F/'results/OUTPUT_SHA256.csv']
with (F/'results/OUTPUT_SHA256.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['path','bytes','sha256']);w.writeheader()
 for p in sorted(paths):w.writerow(dict(path=p.relative_to(F).as_posix(),bytes=p.stat().st_size,sha256=sha(p)))
print(json.dumps(dict(parent_checks=len(parentcheck),parent_pass=True,link_checks=len(linkchecks),sealed_outputs=len(paths),local_native_components=5,physical_tests=0)))
if __name__=='__main__':pass
