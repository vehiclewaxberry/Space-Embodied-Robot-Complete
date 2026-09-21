"""Run bounded stdlib tests and verify upstream readback, writing locally only."""
import hashlib
import io
import json
from pathlib import Path
import unittest
from build_actuator_contract import source_bindings

HERE = Path(__file__).resolve().parent


def main():
    pins = json.loads((HERE/'SOURCE_BINDINGS.json').read_text(encoding='utf-8'))
    source_before = source_bindings()
    if pins != source_before:
        raise RuntimeError('upstream source drift before test')
    suite = unittest.defaultTestLoader.discover(str(HERE), pattern='test_actuator_model.py')
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    after = source_bindings()
    hash_stable = pins == after
    report = {'schema': 'V31_ACTUATOR_TEST_RESULTS',
              'tests_run': result.testsRun, 'failures': len(result.failures),
              'errors': len(result.errors), 'passed': result.wasSuccessful() and hash_stable,
              'upstream_sources_match_before_and_after': hash_stable,
              'scope': 'STDLIB_RESEARCH_BOOKKEEPING_AND_SYNTHETIC_CONSTRAINTS',
              'hardware_tests_executed': False, 'whole_system_validated': False,
              'test_log': stream.getvalue()}
    (HERE/'TEST_RESULTS.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    inventory = {}
    for path in sorted(HERE.iterdir()):
        if path.is_file() and path.name != 'ARTIFACT_SHA256.json':
            raw = path.read_bytes()
            inventory[path.name] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    (HERE/'ARTIFACT_SHA256.json').write_text(json.dumps(inventory, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'test_log'}))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
