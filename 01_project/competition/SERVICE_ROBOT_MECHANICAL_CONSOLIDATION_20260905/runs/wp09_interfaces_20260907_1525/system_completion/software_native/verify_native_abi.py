"""Execute the real pinned DLL only on metadata, NULL and unbound handles.

No add-motor, serial/device constructors, CAN open, enable of a bound object,
runtime downloader, scan, register write, motion or hardware-I/O operation.
"""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import ctypes,hashlib,json,os,re,shutil
from datetime import datetime,timezone
D=Path(__file__).resolve().parent; C=D.parent; N=C.parent/'reuse_closure'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
wheel=json.loads((C/'results/DM_NATIVE_INTAKE.json').read_text(encoding='utf-8'))
assert sha(Path(wheel['path']))==wheel['artifact']['sha256']
pkg=D/'upstream/motorbridge'; src=D/'sources/pinned'
for f in ['abi.py','dm_device_runtime.py','errors.py','models.py']:
    assert sha(pkg/f)==sha(src/'bindings/python/src/motorbridge'/f),f
assert sha(pkg/'core.py')==sha(N/'sources/motorbridge/bindings/python/src/motorbridge/core.py')
dll=pkg/'lib/motor_abi.dll'
os.environ['MOTORBRIDGE_LIB']=str(dll)
sys.path.insert(0,str(D/'upstream'))
import motorbridge
from motorbridge.abi import get_abi,CState
from motorbridge.errors import CallError
abi=get_abi(); lib=abi.lib; rows=[]
def check(name,condition,actual):
    rows.append({'name':name,'pass':bool(condition),'actual':actual})
    assert condition,(name,actual)
check('loaded_dll_exact_path',Path(lib._name).resolve()==dll.resolve(),lib._name)
check('native_version',motorbridge.abi_version()=='0.5.3',motorbridge.abi_version())
caps=motorbridge.abi_capabilities()
check('capabilities_schema_and_dm_serial',caps['schema']==1 and 'dm-serial' in caps['transports'] and 'damiao' in caps['vendors'],caps)
source=(src/'motor_abi/src/lib.rs').read_text(encoding='utf-8')
expected_caps=json.loads(re.search(r'const ABI_CAPABILITIES: &str = r#"(.*?)"#;',source,re.S).group(1).replace('__MOTORBRIDGE_VERSION__','0.5.3'))
check('native_capabilities_equal_pinned_source',caps==expected_caps,True)
layout={name:getattr(CState,name).offset for name,_ in CState._fields_}
expected_layout={'has_value':0,'can_id':4,'arbitration_id':8,'status_code':12,'pos':16,'vel':20,'torq':24,'t_mos':28,'t_rotor':32}
check('Python_ctypes_layout_matches_pinned_repr_C_declaration',layout==expected_layout and ctypes.sizeof(CState)==36,{'offsets':layout,'sizeof':ctypes.sizeof(CState),'native_struct_layout_probe_executed':False})
# All these early NULL paths are reviewed before dereference / bus access.
for name,args in [('motor_controller_poll_feedback_once',(None,)),('motor_controller_shutdown',(None,)),('motor_handle_send_mit',(None,0.,0.,0.,0.,0.)),('motor_handle_send_vel',(None,0.))]:
    rc=getattr(lib,name)(*args);err=lib.motor_last_error_message().decode()
    check(name+'_NULL_rejected',rc==-1 and 'null' in err,{'rc':rc,'error':err})
out=CState();out.has_value=987
rc=lib.motor_handle_get_state(None,ctypes.byref(out));err=lib.motor_last_error_message().decode()
check('null_state_does_not_fabricate_feedback',rc==-1 and out.has_value==987,{'rc':rc,'sentinel_after':out.has_value,'error':err})
# The reviewed constructor only stores a channel string, without opening it.
# Never add a motor: that operation is where upstream opens the hardware bus.
controller=motorbridge.Controller('WP09_OFFLINE_UNBOUND_NO_BUS')
try:
    check('real_native_unbound_constructor',bool(controller._ptr),{'non_null_handle':bool(controller._ptr)})
    for name in ['poll_feedback_once','enable_all','disable_all','shutdown','close_bus']:
        try:getattr(controller,name)()
        except CallError as exc:
            message=str(exc)
            check('real_Python_to_DLL_'+name+'_unbound',('no motor' in message),message)
        else:check(name+'_must_reject_unbound',False,'unexpected success')
finally:controller.close()
check('native_controller_free_and_python_clear',controller._ptr is None,controller._ptr)
try:controller.poll_feedback_once()
except CallError as exc:check('use_after_close_rejected_by_binding','closed' in str(exc),str(exc))
else:check('closed_rejection',False,'unexpected success')
shutil.copy2(N/'sources/motorbridge/LICENSE',D/'LICENSE_MOTORBRIDGE')
receipt={'schema':'DM_REAL_NATIVE_ABI_BOUNDARY_V1','utc':datetime.now(timezone.utc).isoformat(),'status':'PASS_REAL_DLL_LOAD_METADATA_AND_UNBOUND_LIFECYCLE',
 'tests_passed':sum(r['pass'] for r in rows),'tests_total':len(rows),'rows':rows,
 'wheel':{'path':wheel['path'],'sha256':wheel['artifact']['sha256']},'dll':{'path':str(dll),'sha256':sha(dll)},
 'pinned_reference_commit':'c48ebc4b2f250aa1f411a580d9d7b626e187040f','Python_binding_matches_pinned_source':True,'native_binary_rebuilt_here':False,
 'binary_commit_attestation_available':False,'binary_identity_scope':'Official PyPI 0.5.3 distribution digest; matching ABI metadata and Python bindings. Not a locally reproduced binary.',
 'native_Rust_ABI_executed':True,'native_MIT_codec_executed':False,'native_serial_backend_executed':False,'fake_ABI_used':False,
 'hardware_io':0,'hardware_io_evidence':'Audited invocation set and pinned implementation early-return/lazy-unbound paths; no OS device-access trace was run',
 'native_struct_layout_probe_executed':False,'controller_state_exercised':'Unbound only; no motor ever added; physical constructors not called',
 'system_electrical_closed':False,'runtime_environment_modified_systemwide':False}
(C/'results/DM_NATIVE_VERIFICATION.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in receipt.items() if k!='rows'},ensure_ascii=False))
