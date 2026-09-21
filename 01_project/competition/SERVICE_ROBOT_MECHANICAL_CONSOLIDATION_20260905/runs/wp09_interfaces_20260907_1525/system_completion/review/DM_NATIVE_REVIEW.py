"""Independent read-only evidence audit; never imports or executes motorbridge."""
from pathlib import Path
import ast,base64,csv,hashlib,io,json,math,zipfile
from datetime import datetime,timezone
import yaml

C=Path(__file__).resolve().parents[1]; D=C/'software_native'; N=C.parent/'reuse_closure'; checks=[]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def bind(p): return {'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size}
def check(name,truth,value=None):
 checks.append({'name':name,'pass':bool(truth),'actual':value});assert truth,(name,value)
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
native=read(C/'results/DM_NATIVE_VERIFICATION.json'); delta=read(C/'results/DM_PUBLIC_REFERENCE_DELTA.json'); intake=read(C/'results/DM_NATIVE_INTAKE.json')
wheel=Path(intake['path']);meta=D/'sources/pypi_motorbridge_0.5.3.json';metadata=read(meta)
check('wheel_hash_equals_intake',sha(wheel)==intake['artifact']['sha256'])
check('pypi_metadata_hash',sha(meta)==intake['pypi_metadata_sha256'])
artifact=next(x for x in metadata['urls'] if x['filename']==wheel.name)
check('wheel_hash_equals_PyPI_release_record',sha(wheel)==artifact['digests']['sha256'])
check('wheel_download_url_equals_PyPI_release_record',intake['artifact']['url']==artifact['url'])
check('PyPI_metadata_project_identity',metadata['info']['name']=='motorbridge' and metadata['info']['version']=='0.5.3',metadata['info'].get('project_urls'))
with zipfile.ZipFile(wheel) as z:
 check('wheel_CRC',z.testzip() is None)
 dll_bytes=z.read('motorbridge/lib/motor_abi.dll')
 check('loaded_DLL_bytes_are_wheel_member',hashlib.sha256(dll_bytes).hexdigest()==sha(Path(native['dll']['path']))==native['dll']['sha256'])
 for name in z.namelist():
  if name.startswith('motorbridge/') and name.endswith('.py'):
   extracted=D/'upstream'/name
   check('extracted_'+name,extracted.is_file() and hashlib.sha256(z.read(name)).hexdigest()==sha(extracted))
 record=next(x for x in z.namelist() if x.endswith('.dist-info/RECORD'))
 for name,digest,size in csv.reader(io.StringIO(z.read(record).decode())):
  if digest:
   alg,value=digest.split('=',1)
   check('wheel_RECORD_'+name,alg=='sha256' and base64.urlsafe_b64encode(hashlib.sha256(z.read(name)).digest()).decode().rstrip('=')==value and len(z.read(name))==int(size))
manifest=read(D/'sources/ABI_SOURCE_MANIFEST.json')
for row in manifest['rows']:
 check('pinned_source_hash_'+row['path'],sha(D/'sources/pinned'/row['path'])==row['sha256'])
check('source_commit_matches_receipt',manifest['commit']==native['pinned_reference_commit'])
for f in ['abi.py','dm_device_runtime.py','errors.py','models.py']:
 check('binding_source_'+f,sha(D/'upstream/motorbridge'/f)==sha(D/'sources/pinned/bindings/python/src/motorbridge'/f))
check('core_binding_source',sha(D/'upstream/motorbridge/core.py')==sha(N/'sources/motorbridge/bindings/python/src/motorbridge/core.py'))
check('no_binary_commit_attestation_claim',native['binary_commit_attestation_available'] is False and native['native_binary_rebuilt_here'] is False)
check('native_boundary_executed_scope',native['native_Rust_ABI_executed'] and not native['fake_ABI_used'] and not native['native_MIT_codec_executed'] and not native['native_serial_backend_executed'])
check('native_receipt_counts',native['tests_total']==len(native['rows'])==native['tests_passed'] and all(x['pass'] for x in native['rows']))
runner=D/'verify_native_abi.py'; tree=ast.parse(runner.read_text(encoding='utf-8'))
for node in ast.walk(tree):
 if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
  check('no_direct_hardware_method_'+str(node.lineno),node.func.attr not in {'from_dm_serial','from_dm_device','from_mcu_serial','from_socketcanfd','add_damiao_motor','add_motor','ensure_dm_device_runtime'})
life=(D/'sources/pinned/motor_abi/src/controller_lifecycle_ffi.rs').read_text()
check('unbound_controller_source_path', 'inner: Mutex::new(ControllerInner::Unbound(channel))' in life)
check('unbound_dispatch_rejects', 'ControllerInner::Unbound(_) => Err(' in life and 'controller has no motor' in life)
state=(D/'sources/pinned/motor_abi/src/state_ffi.rs').read_text()
check('null_state_returns_before_output_write',state.index('if motor.is_null() || out_state.is_null()') < state.index('let out = unsafe'))
pm=D/'sources/seeed_dm_config/manifest.json';m=read(pm)
for row in m['rows']:check('Seeed_hash_'+row['path'],sha(D/'sources/seeed_dm_config'/row['path'])==row['sha256'])
cfg=read(Path(delta['child']['path']));parent=read(Path(delta['parent']['path']));pub=yaml.safe_load((D/'sources/seeed_dm_config/config/rebotarm_dm.yaml').read_text(encoding='utf-8'))
check('DM_child_hash',sha(Path(delta['child']['path']))==delta['child']['sha256'])
check('DM_parent_hash',sha(Path(delta['parent']['path']))==delta['parent']['sha256'])
check('DM_seven_drives_not_seven_arm_joints',len(pub['joints'])==7 and pub['groups']['arm']['joints']==[f'joint{i}' for i in range(1,7)] and pub['groups']['gripper']['joints']==['gripper'])
for i,(p,c) in enumerate(zip(pub['joints'],cfg['joints']),1):
 check('DM_model_'+str(i),p['model']==c['model_reference']==('4340P' if i<=3 else '4310'))
 check('DM_id_'+str(i),p['motor_id']==c['motor_can_id_reference']==i)
 check('DM_feedback_'+str(i),p['feedback_id']==c['feedback_can_id_reference']==i+16)
 check('not_asbuilt_'+str(i),c['motor_rad_per_joint_rad'] is None and c['mechanical_position_bounds_rad'] is None)
check('public_mapping_is_not_asbuilt',not cfg['enable_physical_io'] and not delta['as_built_bound'])
budget=delta['serial_budget'];baud=budget['baud']
check('serial_source_hash',sha(Path(budget['source_path']))==budget['source_sha256'])
text=Path(budget['source_path']).read_text()
check('explicit_8N1',all(x in text for x in ['DataBits::Eight','StopBits::One','Parity::None']))
check('actual_encoder_packet_length', 'TX_FRAME_LEN: usize = 30' in text and 'RX_FRAME_LEN: usize = 16' in text and '.write_all(&raw)' in text)
check('ideal_capacity',budget['maximum_ideal_commands_per_second']==baud/300==3072)
for i,row in enumerate(budget['rows']):
 count=6*row['arm_rate_hz']+row['gripper_rate_hz'];tx=count*30*10/baud;rx=count*16*10/baud
 check('rate_row_'+str(i),count==row['commands_per_second'] and count*30==row['TX_bytes_per_second'] and math.isclose(tx,row['TX_serial_utilization_8N1']) and math.isclose(rx,row['RX_utilization_if_one_reply_per_command_8N1']) and (tx<=1)==row['TX_fits_ideal_no_overhead'])
check('full_duplex_not_summed',budget['full_duplex_separate_TX_RX'])
issues=[]
old_name=any(x['name']=='C_state_native_windows_ABI_layout' for x in native['rows'])
if old_name:
 issues.append({'id':'DMR01','severity':'CLAIM_SCOPE_CORRECTION','location':'verify_native_abi.py C_state_native_windows_ABI_layout','finding':'ctypes offsets and size are checked only in Python against expected repr(C) layout; NULL native get_state returns before writing the structure. No native DLL structure-layout probe was executed.','requested':'Rename as Python_ctypes_layout_matches_pinned_repr_C_declaration and record native_struct_layout_probe_executed=false.'})
if native.get('native_struct_layout_probe_executed') is False:
 layout_scope='PYTHON_LAYOUT_ONLY_EXPLICITLY_RECORDED'
else:layout_scope='PYTHON_LAYOUT_ONLY_REVIEWER_LIMITATION'
evidence=[runner,D/'build_dm_reference_delta.py',C/'results/DM_NATIVE_VERIFICATION.json',C/'results/DM_NATIVE_INTAKE.json',C/'results/DM_PUBLIC_REFERENCE_DELTA.json',pm,Path(delta['child']['path']),D/'sources/ABI_SOURCE_MANIFEST.json']
out={'schema':'DM_NATIVE_INDEPENDENT_REVIEW_V1','utc':datetime.now(timezone.utc).isoformat(),
 'status':'PASS_WITH_LAYOUT_CLAIM_CLARIFICATION_REQUIRED' if issues else 'PASS_WITH_DECLARED_BOUNDARY_SCOPE',
 'checks_passed':sum(r['pass'] for r in checks),'checks_total':len(checks),'checks':checks,'issues':issues,
 'scope':'Read-only file/source/ZIP/hash review and independent arithmetic; no MotorBridge import or DLL/constructor execution by reviewer.',
 'wheel_identity':'PyPI motorbridge 0.5.3 distribution bytes and RECORD verified; not native binary commit attestation.',
 'hardware_io_zero_basis':'Reviewed explicit call set, unbound/NULL code paths, no real channel or motor binding; not OS-level device-I/O tracing.',
 'layout_scope':layout_scope,
 'native_codec_or_serial_execution_credit':False,'actual_hardware_motion_credit':False,
 'mapping_scope':'Six arm joints plus one gripper; public Seeed model/ID reference only.',
 'throughput_scope':'8N1 line-rate arithmetic at configured baud, conditional one reply per command; does not establish actual USB CDC pacing/CAN/scheduler or control frequency.',
 'input_evidence':[bind(x) for x in evidence]}
dest=C/'review/DM_NATIVE_REVIEW.json';dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:out[k] for k in ['status','checks_passed','checks_total','issues']},ensure_ascii=False))
