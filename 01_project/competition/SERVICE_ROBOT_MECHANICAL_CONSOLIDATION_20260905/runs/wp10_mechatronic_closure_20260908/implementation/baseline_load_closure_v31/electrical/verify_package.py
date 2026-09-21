"""Rebuild + meaningful model tests + artifact readback, no network or hardware."""
import contextlib
import hashlib
import io
import json
import unittest
from pathlib import Path
from build_load_package import build

HERE=Path(__file__).resolve().parent

def main():
 with contextlib.redirect_stdout(io.StringIO()): build()
 stream=io.StringIO()
 result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.discover(str(HERE),pattern='test_load_model.py'))
 p=json.loads((HERE/'ARM_ELECTRICAL_PARAMETERS.json').read_text(encoding='utf-8'))
 s=json.loads((HERE/'LOAD_SENSITIVITY_SCENARIOS.json').read_text(encoding='utf-8'))
 assertions={
  'seven_sdk_axes':len(p['axis_bindings'])==7,
  'model_mix_three_4340_four_4310':[x['motor_family'] for x in p['axis_bindings']].count('DM4340P')==3 and [x['motor_family'] for x in p['axis_bindings']].count('DM4310')==4,
  'as_built_not_fabricated':all(x['as_built_motor_revision'] is None and x['as_built_readback'] is None for x in p['axis_bindings']),
  'four_requested_scan_powers':[x['motion_bus_power_W'] for x in s['scenarios']]==[60,120,240,360],
  'non_motion_unknown_preserved':all(x['hold_bus_power_W'] is None and x['standby_bus_power_W'] is None and x['gripper_bus_power_W'] is None for x in s['scenarios']),
  'all_scenarios_explicit_label':all(x['label']=='DESIGN_SENSITIVITY_NOT_MOTOR_PREDICTION' and x['hardware_capacity_bound'] is False for x in s['scenarios']),
  'no_field_commands':p['hardware_io_executed'] is False,
 }
 receipt={'schema_version':'V31_ELECTRICAL_TEST_RECEIPT_1','model_tests_run':result.testsRun,
          'model_tests_passed':result.wasSuccessful(),'artifact_assertions':assertions,
          'source_hash_checks':'builder fail-closed for 5 inherited source files; checked during this execution',
          'verdict':'PASS_SOFTWARE_AND_SOURCE_BINDING_ONLY' if result.wasSuccessful() and all(assertions.values()) else 'FAIL',
          'actual_motor_performance_validated':False,'hardware_io_executed':False,'test_log':stream.getvalue()}
 (HERE/'ELECTRICAL_TEST_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 files=[]
 for path in sorted(HERE.rglob('*')):
  if path.is_file() and '__pycache__' not in path.parts and path.name!='ELECTRICAL_PACKAGE_SHA256.json':
   files.append({'path':path.relative_to(HERE).as_posix(),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
 (HERE/'ELECTRICAL_PACKAGE_SHA256.json').write_text(json.dumps({'files':files},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:receipt[k] for k in ['verdict','model_tests_run','model_tests_passed']}))
 if receipt['verdict']=='FAIL':raise SystemExit(1)

if __name__=='__main__': main()
