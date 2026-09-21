"""Seal completed, independently reviewed R4 local delta. No upstream changes."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,zipfile
D=Path(__file__).resolve().parents[1];ROOT=D.parents[1];R3=D.parent/'SERVICE_STAR_B601_INTERFACE_R3_20260920'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):
    assert not p.exists(),str(p)
    p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
review=read(D/'results/INDEPENDENT_LAYOUT_REVIEW.json');assert review['summary']['check_count']==review['summary']['passed']==1037 and review['summary']['failed']==0
assert all(sha(x['path'])==x['sha256'] for x in review['source_locks'])
native=read(D/'results/NATIVE_ASSEMBLY_RECHECK.json');assert native['status']=='PASS_READ_ONLY_NATIVE_ASSEMBLY_RECHECK'
assert native['leaf_count']==1130 and native['actual_solid_instances']==1540 and native['needs_rebuild2']==0
geom=read(D/'results/INCREMENT_STATIC_CHECK.json');assert geom['valid'] and not geom['collisions'] and not geom['unknown']
assert len(geom['comparisons'])==363
plan=read(D/'inputs/NATIVE_ASSEMBLY_PLAN.json');delivery=read(D/'results/NATIVE_ASSEMBLY_DELIVERY.json')
locks=plan['source_native_files']+[{'path':x['target'],'sha256':x['native_save']['sha256']} for x in delivery['parts']]+[g['saved'] for g in delivery['groups']]+[delivery['service']['saved']]
assert len(locks)==758 and all(sha(x['path'])==x['sha256'] for x in locks)
r3=read(R3/'DELIVERY_SHA256.json');assert all(sha(R3/x['path'])==x['sha256'] for x in r3['files'])
cf=read(D/'results/CF1_FINAL_HOST_RECHECK.json');assert cf['status']=='CF1_REJECTED_IN_FINAL_R4__NOT_INSTALLED' and len(cf['best_candidate_states'])==3
assert len(cf['final_R4_delta_is_AABB_disjoint_from_all_18_poses'])==18
assert all(sha(x['path'])==x['sha256'] for x in cf['source_locks'])
visual=read(D/'results/LAYOUT_VISUALIZATION.json');assert visual['status']=='PASS_ACTUAL_CAD_VISUAL_REVIEW' and all(sha(x['path'])==x['sha256'] for x in visual['outputs'])
assert sha(native['preview']['png_path'])==native['preview']['sha256'] and read(D/'results/NATIVE_VISUAL_REVIEW.json')['status']=='PASS_VISUAL_INSPECTION'
guard=read(D/'results/DIMENSION_CONTRACT_NEGATIVE_CONTROL.json');assert guard['contract_bytes_restored'] and len(guard['field_controls'])==15
write(D/'results/FINAL_PRESERVATION.json',{'status':'PASS_SOURCE_PRESERVATION','native_files_checked':len(locks),'R3_payload_files_checked':len(r3['files']),
    'independent_source_locks_checked':len(review['source_locks']),'review_sha256':sha(D/'results/INDEPENDENT_LAYOUT_REVIEW.json'),
    'R3_manifest_sha256':sha(R3/'DELIVERY_SHA256.json')})
doc=ROOT/'01_project/competition/内部布局_R4_安装支撑与线束走廊_20260920.md'
write(D/'DELIVERY_STATUS.json',{'status':'R4_LOCAL_DIGITAL_LAYOUT_DELIVERED_WITH_OPEN_ENGINEERING_ITEMS','utc':datetime.now(timezone.utc).isoformat(),
    'native_leaf_instances':1130,'actual_solid_instances':1540,'unique_native_part_files':697,'top_groups':14,
    'new_mount_instances':20,'replacement_instances':6,'new_native_part_files':26,'rebuilt_groups':4,
    'three_fixed_state_exact_pairs':363,'increment_unapproved_penetrations':0,'nominal_interface_gap_mm':geom['interface_clip_gap_mm'],
    'nominal_route_to_M3RB_mm':geom['route_to_M3RB_mm'],'nominal_route_other_minimum_mm':geom['route_minimum_nominal_gap_mm'],
    'independent_review':review['status'],'independent_checks':1037,'CF1_rotated_poses_tested':18,'CF1_installed':False,
    'PCB_to_TIM_gap_mm':4.5,'native_R1_directory_required':True,'portable_pack_and_go':False,
    'all_motion_clearance_verified':False,'whole_assembly_interference_free':None,'whole_material_assignment_complete':False,
    'trusted_whole_mass_kg':None,'trusted_COM_mm':None,'trusted_inertia_kg_m2':None,'ready_to_wire':False,'ready_to_power':False,'flight_ready':False,
    'project_note':{'path':str(doc),'sha256':sha(doc)},'evidence':{f:sha(D/f) for f in [
        'results/INCREMENT_STATIC_CHECK.json','results/NATIVE_ASSEMBLY_RECHECK.json','results/INDEPENDENT_LAYOUT_REVIEW.json',
        'results/CF1_FINAL_HOST_RECHECK.json','results/DIMENSION_CONTRACT_NEGATIVE_CONTROL.json','inputs/NEXT_LAYOUT_WORK_ORDER.json']}})
exclude={'__pycache__','_generated_com','.git','__cadgen__'}
files=sorted([p for p in D.rglob('*') if p.is_file() and not set(p.relative_to(D).parts)&exclude and p.suffix.lower() not in ('.bmp','.zip','.pyc')],key=lambda p:p.relative_to(D).as_posix())
manifest={'schema':'R4_LOCAL_DELTA_SHA256_V1','scope':'listed payload, including rejected CF1 diagnostic; manifest and package receipt excluded from self-hash',
    'files':[{'path':p.relative_to(D).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in files]}
mp=D/'DELIVERY_SHA256.json';write(mp,manifest);files.append(mp)
zp=D/'SERVICE_STAR_R4_LOCAL_LAYOUT.zip';assert not zp.exists()
with zipfile.ZipFile(zp,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in files:z.write(p,p.relative_to(D).as_posix())
with zipfile.ZipFile(zp) as z:
    assert z.testzip() is None
    for r in manifest['files']:assert hashlib.sha256(z.read(r['path'])).hexdigest()==r['sha256']
    assert hashlib.sha256(z.read(mp.name)).hexdigest()==sha(mp)
receipt={'status':'LOCAL_DELTA_ZIP_HASH_AND_READBACK_PASS','path':str(zp),'sha256':sha(zp),'bytes':zp.stat().st_size,'entries':len(files),
    'manifest_sha256':sha(mp),'portable_pack_and_go':False,'native_R1_directory_required':True}
write(D/'results/PACKAGE_DELIVERY.json',receipt);print(json.dumps(receipt,ensure_ascii=False,indent=2))
