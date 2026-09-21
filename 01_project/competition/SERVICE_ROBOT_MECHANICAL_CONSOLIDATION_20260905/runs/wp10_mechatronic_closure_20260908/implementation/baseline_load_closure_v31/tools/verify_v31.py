"""Verify current source bytes and V31 implementation checks; no legacy execution."""
from pathlib import Path
import hashlib
import io
import json
import sys
import unittest
from power_phase_model import P,read,source_check

ROOT=next(p for p in P.parents if (p/'AGENTS.md').exists())

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def main():
    expected={}
    def add(path,h):
        key=str(Path(path).resolve())
        if key in expected and expected[key]!=h:raise ValueError('CONFLICTING_SOURCE_IDENTITIES')
        expected[key]=h
    for row in read(P/'mechanical/SOURCE_LOCK.json')['files']:add(row['path'],row['sha256'])
    for row in read(P/'inputs/ROOT_SOURCE_LOCK.json')['files']:add(row['path'],row['sha256'])
    for row in read(P/'actuators/SOURCE_BINDINGS.json').values():
        add(ROOT/row['path_relative_to_workspace'],row['sha256_raw'])
    for row in read(P/'electrical/SOURCE_MANIFEST.json')['sources']:
        if 'upstream_local_path' in row:
            add(row['upstream_local_path'],row['sha256'])
            add(P/'electrical'/row['package_path'],row['sha256'])
    for row in read(P/'results/SHARED_CONSUMER_RECEIPT.json')['consumed_files']:add(row['path'],row['sha256'])
    mismatches=[path for path,h in expected.items() if not Path(path).exists() or sha(path)!=h]
    if mismatches:raise ValueError('SOURCE_DRIFT: '+repr(mismatches))
    stream=io.StringIO()
    suite=unittest.defaultTestLoader.discover(str(P/'tests'),pattern='test_*.py')
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    mech=read(P/'mechanical/VALIDATION.json');elec=read(P/'electrical/ELECTRICAL_TEST_RECEIPT.json');act=read(P/'actuators/TEST_RESULTS.json')
    shared=read(P/'results/SHARED_CONSUMER_RECEIPT.json')
    assertions=dict(mechanical_scoped_checks=mech['result']=='PASS',
        electrical_model_tests=elec['model_tests_passed'],electrical_artifact_checks=all(elec['artifact_assertions'].values()),
        actuator_model_tests=act['passed'],shared_unknowns_preserved=all(shared['unknowns_preserved'].values()),
        old_solver_replay_exact=max(abs(v) for v in shared['numerical_source_replay_deltas'].values())==0,
        source_bytes_unchanged=not mismatches)
    out=dict(schema='V31_FINAL_VALIDATION',passed=result.wasSuccessful() and all(assertions.values()),
        root_tests_run=result.testsRun,root_failures=len(result.failures),root_errors=len(result.errors),
        module_test_counts=dict(mechanical=mech['total'],electrical=elec['model_tests_run'],actuators=act['tests_run'],root=result.testsRun),
        electrical_artifact_assertions=len(elec['artifact_assertions']),assertions=assertions,
        unique_source_files_checked=len(expected),
        source_scope='Current input hashes, including builders and local vendor snapshots; not a claim that historical raw-hash drifts were repaired.',
        new_hardware_tests=0,new_CAD_rebuilds=0,new_legacy_simulation_runs=0,
        root_test_log=stream.getvalue(),full_design_complete=False)
    (P/'results/VALIDATION.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (P/'results/VERIFIED_SOURCE_MANIFEST.json').write_text(json.dumps(dict(files=[dict(path=p,sha256=h) for p,h in sorted(expected.items())]),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in out.items() if k not in ['root_test_log','source_scope']},ensure_ascii=False))
    if not out['passed']:raise SystemExit(1)

if __name__=='__main__':main()
