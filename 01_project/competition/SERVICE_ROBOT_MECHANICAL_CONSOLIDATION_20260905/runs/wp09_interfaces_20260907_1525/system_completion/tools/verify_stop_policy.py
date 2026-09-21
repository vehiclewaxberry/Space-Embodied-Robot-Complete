from pathlib import Path
import sys,json,hashlib,unittest,io
sys.dont_write_bytecode=True
C=Path(__file__).resolve().parents[1];sys.path.insert(0,str(C/'control'))
import test_stop_supervisor
stream=io.StringIO();suite=unittest.defaultTestLoader.loadTestsFromModule(test_stop_supervisor)
r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
(C/'results/STOP_POLICY_TEST_LOG.txt').write_text(stream.getvalue(),encoding='utf8')
out=dict(status='PASS_OFFLINE_COMMAND_POLICY_ONLY' if r.wasSuccessful() else 'FAIL',tests_run=r.testsRun,failures=len(r.failures),errors=len(r.errors),source_sha256=hashlib.sha256((C/'control/stop_supervisor.py').read_bytes()).hexdigest(),physical_io=0,MCU_build_executed=False,hardware_time_bounds_verified=False,safety_rated_stop=False,claim='Commands and invariants tested. Interface adapter, physical stop, braking, support and energization have not been executed.')
(C/'results/STOP_POLICY_TESTS.json').write_text(json.dumps(out,indent=2),encoding='utf8')
print(json.dumps(out));assert r.wasSuccessful()
