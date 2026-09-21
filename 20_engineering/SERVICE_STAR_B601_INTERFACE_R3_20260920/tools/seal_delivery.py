"""Seal the local R3 delta and evidence without modifying any reviewed design."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,zipfile

D=Path(__file__).resolve().parents[1];ROOT=D.parents[1]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):
    assert not p.exists(),str(p)
    p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

reviews=[read(D/'results'/name) for name in ['INDEPENDENT_INTERFACE_REVIEW.json','INDEPENDENT_ASSEMBLY_RECHECK_REVIEW.json']]
for review in reviews:
    assert review['summary']['checks']==review['summary']['passed'] and not review['summary']['failed']
    assert all(sha(x['path'])==x['sha256'] for x in review['reviewed_file_snapshots'])
native=read(D/'results/NATIVE_ASSEMBLY_RECHECK_V4.json');geom=read(D/'results/GEOMETRY_ASSEMBLY_RECHECK_V2.json')
assert native['status']=='PASS_READ_ONLY_NATIVE_ASSEMBLY_RECHECK' and native['leaf_count']==1110 and native['actual_solid_instances']==1520
assert geom['status']=='PASS_R3_REGION_STATIC_RECHECK' and not geom['collisions']
plan=read(D/'inputs/NATIVE_ASSEMBLY_PLAN.json');assert all(sha(x['path'])==x['sha256'] for x in plan['source_native_files'])
visual=read(D/'results/INTERFERENCE_VISUALIZATION.json')
assert all(sha(x['path'])==x['sha256'] for x in visual['outputs'])
assert native['preview']['nonblank'] and sha(native['preview']['png_path'])==native['preview']['sha256']
write(D/'results/VISUAL_DELIVERY_REVIEW.json',{
    'status':'VISUALLY_REVIEWED','reviewer':'/root','actual_native_screenshot':native['preview'],
    'actual_STEP_interference_views':visual['outputs'],
    'static_image_visual_review':'Labels, current-versus-historical scope, 0.50/0.75mm gaps and CF1 red common region inspected',
    'interactive_browser_review':'Opened in Codex IAB; responsive single-column narrow layout and rendered 3D geometry visually inspected',
    'browser_url':'http://127.0.0.1:8765/ASSEMBLY_INTERFERENCE_VIEWER.html',
    'offline_html_self_contained':True,
    'earlier_blank_native_screenshots':'Failed captures retained locally and omitted from ZIP presentation',
    'cad_skill_cli_snapshot':'Unavailable: missing bundled Playwright browser',
    'cad_skill_viewer':'Unavailable in that runtime; delivered a separate actual-STEP Plotly viewer and native SolidWorks files'})
write(D/'DELIVERY_STATUS.json',{
    'status':'R3_LOCAL_FIXED_POSE_DIGITAL_ASSEMBLY_AND_VISUAL_REVIEW_DELIVERED',
    'utc':datetime.now(timezone.utc).isoformat(),'native_leaf_instances':1110,'actual_solid_instances':1520,
    'unique_part_files_service_state':677,'native_open_errors':0,'native_open_warnings':0,
    'R3_region_static_intersection_checks':36,'R3_region_penetrations':0,
    'independent_initial_interface_checks':99,'independent_assembly_recheck_checks':47,
    'native_references_require_R1_R2':True,'portable_pack_and_go':False,
    'current_R3_min_nominal_noncontact_gap_mm':0.5,'R2_M3RB_nominal_gap_mm':0.75,
    'CF1_old_candidate_installed':False,'CF1_relayout_complete':False,
    'whole_assembly_interference_free':None,'motion_swept_clearance_verified':False,
    'whole_material_assignment_complete':False,'trusted_whole_mass_kg':None,
    'trusted_COM_mm':None,'trusted_inertia_kg_m2':None,
    'ready_to_wire':False,'ready_to_power':False,'flight_ready':False,
    'current_evidence':{f:sha(D/f) for f in [
        'results/NATIVE_ASSEMBLY_RECHECK_V4.json','results/GEOMETRY_ASSEMBLY_RECHECK_V2.json',
        'results/INDEPENDENT_ASSEMBLY_RECHECK_REVIEW.json','results/INTERFERENCE_VISUALIZATION.json',
        'results/VISUAL_DELIVERY_REVIEW.json']},
    'superseded_geometry_check':'results/GEOMETRY_ASSEMBLY_RECHECK.json is coordinate-pairing diagnostic only; see V2 disposition'})
exclude_dirs={'__cadgen__','__pycache__','_generated_com','.git'}
blank_names={'SERVICE_STAR_SERVICE_R3.png','SERVICE_STAR_SERVICE_R3_V2.png'}
files=[p for p in D.rglob('*') if p.is_file() and not (set(p.relative_to(D).parts)&exclude_dirs)
       and p.suffix.lower() not in ('.bmp','.zip','.pyc') and p.name not in blank_names]
files.sort(key=lambda p:p.relative_to(D).as_posix())
manifest={'schema':'R3_LOCAL_DELTA_SHA256_V1','scope':'listed payload; manifest and ZIP receipt excluded from self-hash',
          'files':[{'path':p.relative_to(D).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in files]}
mp=D/'DELIVERY_SHA256.json';write(mp,manifest);files.append(mp)
zp=D/'SERVICE_STAR_R3_LOCAL_ASSEMBLY.zip';assert not zp.exists()
with zipfile.ZipFile(zp,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in files:z.write(p,p.relative_to(D).as_posix())
with zipfile.ZipFile(zp) as z:
    assert z.testzip() is None
    for row in manifest['files']:assert hashlib.sha256(z.read(row['path'])).hexdigest()==row['sha256']
    assert hashlib.sha256(z.read(mp.name)).hexdigest()==sha(mp)
receipt={'status':'LOCAL_DELTA_ZIP_HASH_AND_READBACK_PASS','path':str(zp),'sha256':sha(zp),'bytes':zp.stat().st_size,
         'entries':len(files),'manifest_sha256':sha(mp),'R1_R2_directories_required':True}
write(D/'results/PACKAGE_DELIVERY.json',receipt)
print(json.dumps(receipt,ensure_ascii=False,indent=2))
