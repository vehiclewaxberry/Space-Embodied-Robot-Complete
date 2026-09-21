"""Write the bounded reuse contract and hash the actual local source bundle."""
import csv, hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'sources'/'motorbridge'
COMMIT='c48ebc4b2f250aa1f411a580d9d7b626e187040f'
PARENT=ROOT.parent/'functional_closure'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(name,data):
    (ROOT/'results'/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
files=[]
for p in sorted(SRC.rglob('*')):
    if p.is_file():
        name=p.relative_to(SRC).as_posix()
        files.append({'upstream_path':name,'local_path':str(p),'bytes':p.stat().st_size,'sha256':sha(p),
                      'url':f'https://raw.githubusercontent.com/motorbridge/motorbridge/{COMMIT}/{name}'})
dump('DM_SOURCE_MANIFEST.json',{'repository':'https://github.com/motorbridge/motorbridge','commit':COMMIT,
    'license':'MIT','copyright':'Copyright (c) 2026 motorbridge','license_file':str(SRC/'LICENSE'),
    'source_status':'ACTUAL_MINIMAL_SOURCE_FILES_DOWNLOADED','files':files,
    'attempt_notes':'Initial Python requests/urllib and later PowerShell downloads hit TLS EOF. Eighteen complete source files retained; optional ABI loader/runtime and demo downloads were not completed. No network bypass or TLS verification bypass used.',
    'omitted_upstream_runtime_files':['bindings/python/src/motorbridge/abi.py','bindings/python/src/motorbridge/dm_device_runtime.py','bindings/python/src/motorbridge/errors.py','bindings/python/src/motorbridge/models.py','bindings/python/examples/damiao_dm_serial_demo.py'],
    'upstream_dependencies_declared_not_installed':['Rust motor_core path dependency','serialport 4.6','libloading 0.8','cc 1'],
    'executed_adapter_dependencies':'Python standard library only; no actual ABI, DLL or serialport imported'})
lines=list(csv.DictReader((PARENT/'ecad/FUNCTIONAL_FROM_TO.csv').open(encoding='utf-8-sig',newline='')))
config={'identity':'PUBLIC_REFERENCE_NOT_AS_BUILT','transport_candidate':'dm-serial','serial_baud_candidate':921600,
        'can_bus_bitrate':None,'adapter_sku_candidate':'100011896','splitter_sku_candidate':'100045091',
        'controller_firmware_revision':None,'adapter_firmware_revision':None,'physical_device_path':None,
        'enable_physical_io':False,'joints':[]}
for i in range(1,8):
    config['joints'].append({'name':f'J{i}' if i<7 else 'GRIPPER','motor_can_id_reference':i,
        'feedback_can_id_reference':16+i,'model_reference':'4340P' if i==1 else None,
        'model_assignment_status':'J1 public corrected model; other joint distribution requires actual assembly mapping',
        'firmware_revision':None,'motor_rad_per_joint_rad':None,'motor_zero_rad':None,
        'mechanical_position_bounds_rad':None,'operating_velocity_limit_rad_s':None,'operating_torque_limit_nm':None})
(ROOT/'software'/'DM_REFERENCE_CONFIG.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
dump('DM_INTEGRATION_CONTRACT.json',{
    'status':'OFFLINE_DM_PROTOCOL_REUSE_COMPLETE_WITH_DECLARED_HARDWARE_INPUTS',
    'parent_from_to':{'path':str(PARENT/'ecad/FUNCTIONAL_FROM_TO.csv'),'sha256':sha(PARENT/'ecad/FUNCTIONAL_FROM_TO.csv'),'total_conductors':len(lines)},
    'electrical_rows_bound':[x for x in lines if x['wire_id'] in ('C01','C02','C03','C04')],
    'selection_evidence':[
      {'url':'https://wiki.seeedstudio.com/rebot_b601_dm_getting_started/','finding':'Preparation adapter product link resolves to SKU 100011896; Windows gateway example explicitly dm-serial, 921600; reference IDs motor 1..7 and feedback 0x11..0x17.'},
      {'url':'https://www.seeedstudio.com/DM-CAN-USB-Driver-Borad-p-6706.html','finding':'Official linked product identifies SKU 100011896.'},
      {'path':str(PARENT/'inputs/vendor_sources/DM_PUBLIC_BOM.md'),'sha256':sha(PARENT/'inputs/vendor_sources/DM_PUBLIC_BOM.md'),'finding':'DM V4 reference uses three 4340P and four 4310; J1 correction recorded. Counts alone do not assign each remaining joint.'}],
    'mapping':[
      {'source':'motor_vendors/damiao/src/protocol.rs::encode_mit_cmd/decode_sensor_feedback/float_to_uint/uint_to_float','project':'software/dm_codec.py','implementation':'Python port with float32 rounding; MIT header and local full MIT license'},
      {'source':'motor_core/src/dm_serial.rs::encode_tx/try_parse_rx','project':'software/dm_codec.py::encode_dm_serial/RxParser','implementation':'Offline byte codec; receive validates DLC8, standard ID, no RTR and bounded buffer more strictly than upstream'},
      {'source':'motor_vendors/damiao/src/motor.rs::DAMIAO_MODELS','project':'software/dm_codec.py::MODELS','implementation':'4310/4340P constants extracted by review and regex checked against source during tests'},
      {'source':'bindings/python/src/motorbridge/core.py::Motor.send_mit/_require_open + _ok/_err_text','project':'software/test_dm_offline.py::test_24','implementation':'Unmodified AST method bodies executed with fake ABI; constructors, imports and native code excluded'}],
    'units':{'position':'rad at configured joint / motor output shaft','velocity':'rad/s','torque':'N m','kp':'N m/rad','kd':'N m s/rad','temperature':'degC',
             'transform':'motor_q = r * joint_q + motor_zero; motor_v = r * joint_v; motor_tau = joint_tau / r; motor_kp,kd = joint_kp,kd / r^2; ideal static mapping, r/zero/efficiency not identified on actual device'},
    'source_protocol_scaling_not_hardware_safe_limits':{'4310':{'pmax_rad':12.5,'vmax_rad_s':30,'tmax_nm':10},'4340P':{'pmax_rad':12.5,'vmax_rad_s':10,'tmax_nm':28}},
    'side_effect_review':{'protocol_rs':'pure byte/arithmetic routines; no opening',
       'dm_serial_rs':'DmSerialBus::open calls serialport.open; send writes port; therefore not executed',
       'motor_rs':'new constructs state; enable/disable/maintenance methods call bus.send; none executed',
       'python_core':'Controller constructors call ABI bus-open routines; from_dm_device calls runtime installation helper; not imported or instantiated',
       'ast_isolation':'Only reviewed forwarding/error methods extracted, no __init__ or imports; fake lib contains no I/O'},
    'resolved_this_package':['public adapter transport selection','reviewable actual protocol source','offline MIT/serial encoding and feedback','explicit model/ID/configuration contract','local error/timeout inhibition and communication-vs-power separation'],
    'remaining_exact_inputs':['Actual DM V4 adapter/motor firmware revisions and installed CAN/master IDs','J2..J7 motor model assignment, calibrated joint sign/zero/ratio, travel/speed/torque limits','Actual CAN bitrate, termination count, connector cavity views and signal return/isolation/backfeed','Real sample frames and a matching Rust/ABI build for end-to-end byte/ABI validation','Hardware power interlock K1 and bus-energy behavior; mechanical support and measured stop time'],
    'protocol_limitations':['Upstream TX CRC field fixed zero; RX envelope has no validated checksum here. Cannot certify corruption detection.','DM payload has no authenticated timestamp/sequence; local API sequence blocks repeated local calls only, not valid wire replay or forged telemetry.','MOS/rotor byte temperatures and status fault flags are parsed; no unverified thermal threshold is invented.','Ambiguous register-like sensor bytes are rejected conservatively. Receiver does not implement maintenance replies.'],
    'hardware_execution':False,'build_approved':False,'scientific_gate_credit':False})
print(json.dumps({'actual_source_files':len(files),'source_bytes':sum(x['bytes'] for x in files),'from_to_bound_rows':4,'physical_io':0}))
