"""Deterministic offline checks, including an AST-isolated actual upstream SDK method.
All RX frames are constructed protocol fixtures, never captured motor telemetry.
"""
import ast
import hashlib
import json
import platform
import sys
import time
import types
import unittest
from pathlib import Path
sys.dont_write_bytecode=True
from dm_codec import *
from dm_offline_adapter import *

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'sources'/'motorbridge'

def synthetic_rx(status=1, aid=0x11, mid=1, p=0x7fff, v=0x7ff, t=0x7ff):
    data=bytes([(status<<4)|mid,p>>8,p&255,v>>4,((v&15)<<4)|(t>>8),t&255,55,44])
    return bytes([0xaa,0x11,8])+aid.to_bytes(4,'little')+data+bytes([0x55])

def fixture(**changes):
    args=dict(name='J1_SYNTHETIC',motor_id=1,feedback_id=0x11,model='4340P',
              firmware_revision='SYNTHETIC_NOT_DEVICE_READ',motor_rad_per_joint_rad=1.0,
              motor_zero_rad=0.0,q_min_rad=-.5,q_max_rad=.5,velocity_max_rad_s=.2,
              torque_max_nm=.5,kp_max_nm_rad=10,kd_max_nm_s_rad=1,timeout_ms=100,
              evidence_kind='SYNTHETIC_OFFLINE_FIXTURE')
    args.update(changes);return JointConfig(**args)

def ready(**cfg):
    bus=FakeTransport();a=OfflineAdapter(fixture(**cfg),bus)
    a.receive(synthetic_rx(),0);a.set_simulated_power_permission(True)
    return a,bus

class ProtocolTests(unittest.TestCase):
    def test_01_zero_golden(self):
        self.assertEqual(encode_mit(0,0,0,0,0,MODELS['4340P']).hex(),'7fff7ff0000007ff')
    def test_02_endpoints_and_clipping(self):
        l=MODELS['4310']
        self.assertEqual(encode_mit(-12.5,-30,-10,0,0,l),bytes(8))
        self.assertEqual(encode_mit(12.5,30,10,500,5,l),bytes([255])*8)
        self.assertEqual(encode_mit(999,999,999,999,999,l),bytes([255])*8)
    def test_03_nan_infinite_rejected(self):
        for x in (float('nan'),float('inf'),float('-inf')):
            with self.assertRaises(ValueError): encode_mit(x,0,0,0,0,MODELS['4310'])
    def test_04_serial_tx_golden(self):
        raw=encode_dm_serial(Frame(1,bytes.fromhex('7fff7ff0000007ff')))
        self.assertEqual(raw.hex(),'55aa1e03010000000a0000000001000000000800007fff7ff0000007ff00')
    def test_05_sensor_golden_and_quantization(self):
        raw=bytes.fromhex('aa110811000000117fff7ff7ff372c55')
        frame=RxParser().feed(raw)[0]; f=decode_feedback(frame.data,MODELS['4340P'])
        self.assertEqual((f['motor_id'],f['status'],f['mos_temperature_c'],f['rotor_temperature_c']),(1,1,55,44))
        self.assertLessEqual(abs(f['position_rad']),25/65535)
        self.assertLessEqual(abs(f['velocity_rad_s']),20/4095)
        self.assertLessEqual(abs(f['torque_nm']),56/4095)
    def test_06_fragmentation_noise_and_multiple(self):
        p=RxParser();raw=synthetic_rx()
        self.assertEqual(p.feed(b'noise'+raw[:4]),[])
        self.assertEqual(len(p.feed(raw[4:]+raw)),2)
    def test_07_invalid_dlc_rtr_extended_end_marker(self):
        for index,value in ((2,9),(2,0x88),(2,0x48),(15,0)):
            p=RxParser();raw=bytearray(synthetic_rx());raw[index]=value
            self.assertEqual(p.feed(bytes(raw)),[]);self.assertGreater(p.rejected,0)
    def test_08_buffer_bounded(self):
        with self.assertRaises(ValueError):RxParser().feed(bytes(1025))
    def test_09_model_catalog_matches_locked_source(self):
        import re
        text=(SRC/'motor_vendors/damiao/src/motor.rs').read_text(encoding='utf-8')
        for model,l in MODELS.items():
            pat=r'model:\s*"'+model+r'",\s*pmax:\s*([\d.]+),\s*vmax:\s*([\d.]+),\s*tmax:\s*([\d.]+)'
            m=re.search(pat,text);self.assertIsNotNone(m)
            self.assertEqual(tuple(map(float,m.groups())),(l.p,l.v,l.t))
    def test_10_all_reported_faults_and_unknown(self):
        for code in list(range(8,15))+[2,15]:
            a,b=ready();a.receive(synthetic_rx(status=code),1)
            self.assertIsNotNone(a.latch);self.assertFalse(a.power_permission)
            with self.assertRaises(RuntimeError):a.command_joint_mit(0,0,0,0,0,2,0)
            self.assertEqual(b.tx,[])
    def test_11_power_not_inferred_from_feedback(self):
        b=FakeTransport();a=OfflineAdapter(fixture(),b);a.receive(synthetic_rx(),0)
        with self.assertRaises(RuntimeError):a.command_joint_mit(0,0,0,0,0,1,0)
        self.assertEqual(b.tx,[])
    def test_12_power_permission_cannot_replace_feedback(self):
        b=FakeTransport();a=OfflineAdapter(fixture(),b);a.set_simulated_power_permission(True)
        with self.assertRaises(RuntimeError):a.command_joint_mit(0,0,0,0,0,1,0)
    def test_13_timeout_latched_fresh_frame_no_auto_resume(self):
        a,b=ready();a.tick(101);a.receive(synthetic_rx(),102)
        self.assertEqual(a.latch,'FEEDBACK_TIMEOUT')
        with self.assertRaises(RuntimeError):a.set_simulated_power_permission(True)
        with self.assertRaises(RuntimeError):a.command_joint_mit(0,0,0,0,0,103,0)
        self.assertEqual(b.tx,[])
    def test_14_reset_requires_fresh_disabled_and_revokes_power(self):
        a,b=ready();a.tick(101)
        with self.assertRaises(RuntimeError):a.reset_while_disabled(102)
        a.receive(synthetic_rx(status=0),103);a.reset_while_disabled(104)
        self.assertIsNone(a.latch);self.assertFalse(a.power_permission)
        with self.assertRaises(RuntimeError):a.command_joint_mit(0,0,0,0,0,105,0)
    def test_15_both_ids_match(self):
        for kwargs in ({'aid':0x12},{'mid':2}):
            a,b=ready()
            with self.assertRaises(ValueError):a.receive(synthetic_rx(**kwargs),1)
            self.assertEqual(a.latch,'WRONG_ID');self.assertEqual(b.tx,[])
    def test_16_joint_limits_reject_not_clip(self):
        for values in ((.51,0,0,0,0),(0,.21,0,0,0),(0,0,.51,0,0),(0,0,0,11,0),(0,0,0,0,1.1)):
            a,b=ready()
            with self.assertRaises(ValueError):a.command_joint_mit(*values,1,0)
            self.assertEqual(b.tx,[])
    def test_17_local_sequence_replay_rejected(self):
        a,b=ready();a.command_joint_mit(0,0,0,0,0,1,3)
        with self.assertRaises(ValueError):a.command_joint_mit(0,0,0,0,0,2,3)
        self.assertEqual(len(b.tx),1)
    def test_18_transform_and_gain_units(self):
        a,b=ready(motor_rad_per_joint_rad=-2.0,motor_zero_rad=.1)
        raw=a.command_joint_mit(.2,.1,.4,4,.4,1,0)
        expected=encode_mit(-.3,-.2,-.2,1,.1,MODELS['4340P'])
        self.assertEqual(raw[21:29],expected)
    def test_19_no_physical_transport_substitution(self):
        class RealLooking(FakeTransport):pass
        with self.assertRaises(TypeError):OfflineAdapter(fixture(),RealLooking())
    def test_20_no_enable_calibration_write_api(self):
        for name in ('enable','set_zero','write_register','flash','open','scan','clear_error'):
            self.assertFalse(hasattr(OfflineAdapter,name))
    def test_21_clock_rollback_latches(self):
        a,b=ready();a.tick(5)
        with self.assertRaises(ValueError):a.tick(4)
        self.assertEqual(a.latch,'CLOCK_ROLLBACK')
    def test_22_bad_framing_latches_even_if_good_frame_follows(self):
        a,b=ready();bad=bytearray(synthetic_rx());bad[-1]=0
        a.receive(bytes(bad)+synthetic_rx(),1)
        self.assertEqual(a.latch,'FRAMING_ERROR');self.assertFalse(a.power_permission)
    def test_23_register_reply_not_sensor(self):
        a,b=ready();raw=bytearray(synthetic_rx());raw[8]=1;raw[9]=0x33
        with self.assertRaises(ValueError):a.receive(bytes(raw),1)
        self.assertEqual(a.latch,'NON_SENSOR_FRAME')
    def test_24_actual_sdk_send_mit_ast_on_fake_abi(self):
        # Execute only the unmodified upstream pure forwarding/error methods.
        # Do NOT import core.py, package __init__, ABI loader, or constructors.
        source=SRC/'bindings/python/src/motorbridge/core.py'
        tree=ast.parse(source.read_text(encoding='utf-8'))
        funcs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('_ok','_err_text')]
        motor=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Motor')
        motor.body=[n for n in motor.body if isinstance(n,ast.FunctionDef) and n.name in ('send_mit','_require_open')]
        isolated=ast.Module(body=funcs+[motor],type_ignores=[])
        calls=[]
        class FakeLib:
            rc=0
            def motor_handle_send_mit(self,*args):calls.append(args);return self.rc
            def motor_last_error_message(self):return b'SYNTHETIC_ABI_ERROR'
        lib=FakeLib();abi=types.SimpleNamespace(lib=lib)
        env={'CallError':RuntimeError,'get_abi':lambda:abi}
        exec(compile(isolated,str(source),'exec'),env)
        obj=env['Motor'].__new__(env['Motor']);obj._ptr=17;obj._abi=abi
        obj.send_mit(.2,.1,3,.4,.5)
        self.assertEqual(calls[-1],(17,.2,.1,3,.4,.5))
        lib.rc=-1
        with self.assertRaisesRegex(RuntimeError,'SYNTHETIC_ABI_ERROR'):obj.send_mit(0,0,0,0,0)
        obj._ptr=None
        with self.assertRaisesRegex(RuntimeError,'closed'):obj.send_mit(0,0,0,0,0)
    def test_25_executable_modules_have_no_io_imports(self):
        for name in ('dm_codec.py','dm_offline_adapter.py'):
            tree=ast.parse((ROOT/'software'/name).read_text())
            imports=[]
            for n in ast.walk(tree):
                if isinstance(n,ast.Import):imports.extend(a.name for a in n.names)
                elif isinstance(n,ast.ImportFrom):imports.append(n.module)
            self.assertTrue(set(imports)<= {'dataclasses','math','struct','dm_codec'})
    def test_26_hardware_revision_cannot_be_implied(self):
        with self.assertRaises(ValueError):fixture(firmware_revision='')
        with self.assertRaises(ValueError):fixture(evidence_kind='PUBLIC_REFERENCE_NOT_AS_BUILT')
    def test_27_explicit_disable_prevents_command(self):
        a,b=ready();a.receive(synthetic_rx(status=0),1)
        with self.assertRaises(RuntimeError):a.command_joint_mit(0,0,0,0,0,2,0)
    def test_28_motor_range_checked_after_transform(self):
        a,b=ready(motor_zero_rad=12.5)
        with self.assertRaises(ValueError):a.command_joint_mit(.1,0,0,0,0,1,0)
    def test_29_disabled_then_enabled_does_not_restore_permission(self):
        a,b=ready();a.receive(synthetic_rx(status=0),1);a.receive(synthetic_rx(status=1),2)
        self.assertFalse(a.power_permission)
        with self.assertRaises(RuntimeError):a.command_joint_mit(0,0,0,0,0,3,0)
        self.assertEqual(b.tx,[])

class Recorded(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.records=[]
    def addSuccess(self,test):super().addSuccess(test);self.records.append({'test':test.id(),'status':'PASS'})
    def addFailure(self,test,err):super().addFailure(test,err);self.records.append({'test':test.id(),'status':'FAIL','error':self._exc_info_to_string(err,test)})
    def addError(self,test,err):super().addError(test,err);self.records.append({'test':test.id(),'status':'ERROR','error':self._exc_info_to_string(err,test)})

if __name__=='__main__':
    started=time.perf_counter()
    result=unittest.TextTestRunner(verbosity=2,resultclass=Recorded).run(unittest.defaultTestLoader.loadTestsFromTestCase(ProtocolTests))
    hashes=[]
    for p in list((ROOT/'software').glob('*'))+list(SRC.rglob('*')):
        if p.is_file():hashes.append({'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    import ctypes
    from ctypes import wintypes
    class MemoryCounters(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD),
                  ('PeakWorkingSetSize',ctypes.c_size_t),('WorkingSetSize',ctypes.c_size_t),
                  ('QuotaPeakPagedPoolUsage',ctypes.c_size_t),('QuotaPagedPoolUsage',ctypes.c_size_t),
                  ('QuotaPeakNonPagedPoolUsage',ctypes.c_size_t),('QuotaNonPagedPoolUsage',ctypes.c_size_t),
                  ('PagefileUsage',ctypes.c_size_t),('PeakPagefileUsage',ctypes.c_size_t)]
    mc=MemoryCounters();mc.cb=ctypes.sizeof(mc)
    ctypes.windll.kernel32.GetCurrentProcess.restype=wintypes.HANDLE
    ctypes.windll.psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(MemoryCounters),wintypes.DWORD]
    ctypes.windll.psapi.GetProcessMemoryInfo.restype=wintypes.BOOL
    ok=ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(),ctypes.byref(mc),mc.cb)
    receipt={'status':'PASS_OFFLINE_PROTOCOL_ADAPTER_ONLY' if result.wasSuccessful() else 'FAIL',
      'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
      'python':platform.python_version(),'executed_implementation':'Python codec port plus AST-isolated unmodified MotorBridge Python SDK send_mit/_require_open/_ok/_err_text on fake ABI',
      'elapsed_seconds':time.perf_counter()-started,'peak_working_set_mib':mc.PeakWorkingSetSize/1048576 if ok else None,
      'rust_library_execution':'NOT_EXECUTED; no Rust toolchain installed','transport':'memory only; exact FakeTransport type',
      'hardware_frames':'NONE; all synthetic protocol construction fixtures','physical_io_operations':0,
      'hardware_power_permission':False,'build_approved':False,'tests':result.records,'file_hashes':hashes}
    (ROOT/'results'/'DM_OFFLINE_TEST_RESULTS.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    sys.exit(0 if result.wasSuccessful() else 1)
