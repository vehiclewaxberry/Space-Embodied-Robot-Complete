"""Seal the bounded R2 delta and verify the immutable R1 native payload."""
from pathlib import Path
import csv,hashlib,json,zipfile,datetime
D=Path(__file__).resolve().parents[1];R1=D.parent/'SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919'
def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
native=read(D/'results/NATIVE_ROUTE_DELIVERY_V2.json')
assert native['status']=='PASS_LOCAL_NATIVE_DELTA_COLD_READ_FIXED_POSE'
assert native['service']['full_leaf_count']==1110 and native['R1_sources_unchanged']
for mode in ['group','detail','service']:
    r=native[mode];assert r['cold_errors']==r['cold_warnings']==r['needs_rebuild2']==0
    p=Path(r['saved']['path']);assert sha(p)==r['saved']['sha256']
route=read(D/'results/RELEASE_ROUTE_STATIC_CHECK.json');assert not route['unclassified_collisions']
visual=read(D/'results/ROUTE_VISUAL.json')
assert visual['input_check_sha256']==sha(D/'results/RELEASE_ROUTE_STATIC_CHECK.json')
assert visual['status']=='ACTUAL_STEP_RENDER_VISUALLY_REVIEWED'
for r in route['rows']:assert sha(Path(r['output']['path']))==r['output']['sha256']
electric=read(D/'results/INDEPENDENT_ELECTRICAL_REVIEW.json')
for r in electric['reviewed_files']:assert sha(D/r['path'])==r['sha256'],r['path']
act=read(D/'results/INDEPENDENT_ACTUATION_REVIEW.json')
for p,digest in act['artifact_sha256'].items():assert sha(D/p)==digest,p
review=read(D/'results/INDEPENDENT_ROUTE_REVIEW.json')
assert review['status'].startswith('PASS_WITH_OBSERVATIONS')
basezip=R1/'SERVICE_STAR_R1_REVIEW_PACKAGE.zip'
assert sha(basezip)=='89320dbb87156e8337b9bef6ab1091d9868a67bd1617cb4fd9eb292756f90b72'
records=[]
with zipfile.ZipFile(basezip) as z:
    for item in z.infolist():
        if not item.filename.startswith('native/') or item.is_dir():continue
        p=R1/item.filename
        with z.open(item) as f:expected=hashlib.file_digest(f,'sha256').hexdigest()
        assert sha(p)==expected,item.filename
        records.append({'path':str(p),'sha256':expected})
assert len(records)==719
write(D/'results/R1_PRESERVATION.json',{'status':'SEALED_ZIP_AND_719_NATIVE_PAYLOADS_UNCHANGED',
    'zip_path':str(basezip),'zip_sha256':sha(basezip),'native_file_count':len(records),'native_files':records})
status={'schema':'R2_DELIVERY_STATUS_V1','closed_on':'2026-09-20',
    'status':'SOURCE_BOUND_LOCAL_DIGITAL_INCREMENT_VERIFIED_ENGINEERING_INPUTS_OPEN',
    'full_service_native_leaf_count':1110,'local_detail_native_leaf_count':20,
    'native_cold_open_errors':0,'native_cold_open_warnings':0,'R1_native_payloads_preserved':719,
    'native_portable_package':False,'R1_native_directory_required':True,
    'static_route_scope':'TWO_FUNCTIONAL_BRANCHES; THREE_FIXED_STATES; NO_FULL_MOTION_RELEASE',
    'electrical_active_records':84,'electrical_physical_manufacturing_releases':0,
    'current_thruster_geometry_known':False,'orbit_modes':9,'physical_orbit_mode_permissions':False,
    'whole_design_complete':False,'ready_to_power':False,'flight_ready':False,
    'trusted_whole_mass_kg':None,'trusted_COM_mm':None,'trusted_inertia_kg_m2':None,
    'sources_and_reviews':{n:sha(D/'results'/n) for n in [
        'INDEPENDENT_ELECTRICAL_REVIEW.json','INDEPENDENT_ACTUATION_REVIEW.json','INDEPENDENT_ROUTE_REVIEW.json',
        'NATIVE_ROUTE_DELIVERY_V2.json','RELEASE_ROUTE_STATIC_CHECK.json','ROUTE_VISUAL.json','R1_PRESERVATION.json']}}
write(D/'results/R2_DELIVERY_STATUS.json',status)
active_native=[Path(x['target']) for x in native['parts']]+[Path(native[k]['saved']['path']) for k in ['group','detail','service']]
payload=[D/'README.md']
for folder in ['inputs','docs','cad','views','results','tools']:
    for p in sorted((D/folder).rglob('*')):
        if not p.is_file() or '_generated_com' in p.parts or '__pycache__' in p.parts:continue
        if p.suffix.lower() in ['.pyc','.log','.tmp','.zip']:continue
        if p.name in ['DELIVERY_MANIFEST.csv','PACKAGE_DELIVERY.json']:continue
        payload.append(p)
payload+=active_native;payload=sorted(set(payload))
manifest=D/'results/DELIVERY_MANIFEST.csv'
with manifest.open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f);w.writerow(['relative_path','bytes','sha256'])
    for p in payload:w.writerow([p.relative_to(D).as_posix(),p.stat().st_size,sha(p)])
payload.append(manifest)
target=D/'SERVICE_STAR_R2_LOCAL_INCREMENT.zip';assert not target.exists()
with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in payload:z.write(p,p.relative_to(D).as_posix())
with zipfile.ZipFile(target) as z:
    assert len(z.infolist())==len(payload)
    for p in payload:
        with z.open(p.relative_to(D).as_posix()) as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
        assert actual==sha(p),p
write(D/'results/PACKAGE_DELIVERY.json',{'status':'SEALED_AND_PAYLOAD_READBACK_VERIFIED_LOCAL_DELTA',
    'path':str(target),'sha256':sha(target),'bytes':target.stat().st_size,'entries':len(payload),
    'portable_native_PackAndGo':False,'R1_native_directory_required':True,
    'standalone_local_STEP':'cad/INTERNAL_HARNESS_DETAIL_R2.step',
    'scope':'Local fixed-pose design increment; no engineering/manufacturing/power/flight release'})
print('SEALED',len(payload),target.stat().st_size,sha(target))
