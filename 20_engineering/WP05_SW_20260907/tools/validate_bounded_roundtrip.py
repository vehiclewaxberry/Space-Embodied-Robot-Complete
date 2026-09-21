"""Run the unchanged roundtrip validator in one bounded subprocess per part.

The parent is standard-library-only. Each child imports validate_native_roundtrip
and calls its validate_one, preserving its validity rules, integrations and
tolerances. Every result is persisted before proceeding. Timeout/crash/missing
exports remain INCOMPLETE with null geometry results. Only completed, hash-exact
PASS or geometry FAIL evidence can be reused; stdout from older runs is not data.

Default attaches evidence to NATIVE_IMPORTS after saving a byte-exact backup.
Use --no-apply for derived receipts only. Run this wrapper under the root-owned
1400 MiB/512 MiB-floor guard; child processes inherit that guard on Windows.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / 'tools/validate_native_roundtrip.py'
ITEMS = ROOT / 'results/roundtrip_items'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest_object(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    os.replace(temp, path)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def progress(stage, **fields):
    print(json.dumps(dict(stage=stage, **fields), ensure_ascii=False, allow_nan=False), flush=True)


def normalized(path):
    return str(Path(path).resolve()).replace('\\', '/').casefold()


def safe_key(key):
    if re.fullmatch(r'[A-Za-z0-9_-]{1,150}', key):
        return key
    return re.sub(r'[^A-Za-z0-9_-]', '_', key)[:110]+'_'+hashlib.sha256(key.encode()).hexdigest()[:12]


def without_evidence(row):
    result = copy.deepcopy(row)
    if isinstance(result.get('source_comparison'), dict):
        result['source_comparison'].pop('roundtrip_validation', None)
    return result


def verify_inputs(row, part, manifest_hash, validator_hash, wrapper_hash):
    """Hash source/native/returned STEP each time, including on a cache hit."""
    snapshots, issues = {}, []
    def bind(path, expected, extension, name):
        if not path or not isinstance(expected, str):
            issues.append(name+': missing recorded file/hash')
            return None, None
        p = Path(path).resolve()
        if not p.is_relative_to(ROOT.resolve()) or p.suffix.lower() != extension:
            issues.append(name+': path/extension is outside the package contract')
            return str(p), None
        if not p.is_file():
            issues.append(name+': recorded file is absent')
            return str(p), None
        actual = sha(p)
        snapshots[str(p)] = actual
        if actual.lower() != expected.lower():
            issues.append(name+': actual SHA differs from recorded SHA')
        return str(p), actual
    if part is None:
        issues.append('Part is absent from the bound source manifest')
        part = {}
    source_path, source_hash = bind(part.get('path'), part.get('sha256'), '.step', 'source')
    if source_path and row.get('source') and normalized(row['source']) != normalized(source_path):
        issues.append('Native import refers to another source path')
    if row.get('source_sha256') != part.get('sha256'):
        issues.append('Native import source SHA differs from source manifest')
    saved_native = row.get('native_save') or {}
    native_path, native_hash = bind(row.get('target'), saved_native.get('sha256'), '.sldprt', 'native')
    if saved_native.get('ok') is not True or saved_native.get('errors') != 0:
        issues.append('No successful native save receipt')
    rt = row.get('roundtrip') or {}
    saved_rt = rt.get('save') or {}
    rt_path, rt_hash = bind(rt.get('path'), saved_rt.get('sha256'), '.step', 'roundtrip')
    if saved_rt.get('ok') is not True or saved_rt.get('errors') != 0:
        issues.append('No successful SolidWorks roundtrip STEP export receipt')
    if rt.get('native_sha256') is not None and rt['native_sha256'] != native_hash:
        issues.append('Roundtrip export was bound to another native file SHA')
    if source_path and rt_path and normalized(source_path) == normalized(rt_path):
        issues.append('Roundtrip export path is the original source path')
    bindings = dict(source_path=source_path, source_sha256=source_hash,
        native_path=native_path, native_sha256=native_hash,
        roundtrip_path=rt_path, roundtrip_sha256=rt_hash,
        source_manifest_sha256=manifest_hash,
        native_row_payload_sha256=digest_object(without_evidence(row)),
        source_part_record_sha256=digest_object(part),
        validation_script_path=str(VALIDATOR.resolve()), validation_script_sha256=validator_hash,
        wrapper_script_path=str(Path(__file__).resolve()), wrapper_script_sha256=wrapper_hash)
    return bindings, snapshots, issues


def incomplete_evidence(key, bindings, reason, timeout_s, **context):
    return dict(status='INCOMPLETE', part_key=key, generated_utc=utc(),
        source_path=bindings.get('source_path'), source_sha256=bindings.get('source_sha256'),
        native_path=bindings.get('native_path'), native_sha256=bindings.get('native_sha256'),
        roundtrip_path=bindings.get('roundtrip_path'), roundtrip_sha256=bindings.get('roundtrip_sha256'),
        validation_script_path=bindings['validation_script_path'],
        validation_script_sha256=bindings['validation_script_sha256'],
        symmetric_difference_mm3=None, bbox_max_difference_mm=None, volume_difference_mm3=None,
        reason=reason, geometry_results_not_inferred=True,
        cross_kernel_scalar_failure_preserved=True, com_export_executed_by_this_validator=False,
        bounded_execution=dict(wrapper_script_path=bindings['wrapper_script_path'],
            wrapper_script_sha256=bindings['wrapper_script_sha256'], timeout_seconds=timeout_s,
            completed_validate_one=False, **context))


def persist_item(path, record):
    if path.exists():
        previous = path.read_bytes()
        old_hash = hashlib.sha256(previous).hexdigest()
        history = ITEMS/'history'/(path.stem+'_'+old_hash+'.json')
        history.parent.mkdir(parents=True, exist_ok=True)
        if not history.exists():
            history.write_bytes(previous)
        else:
            require(sha(history) == old_hash, 'Per-item history file is corrupted')
    write(path, record)


def worker(payload_path):
    """Executed only by the child. Importing the original module retains __file__."""
    payload = read(payload_path)
    bindings = payload['bindings']
    require(sha(VALIDATOR) == bindings['validation_script_sha256'], 'Original validator SHA changed before child start')
    require(sha(__file__) == bindings['wrapper_script_sha256'], 'Wrapper SHA changed before child start')
    for path, expected in payload['snapshots'].items():
        require(sha(path) == expected, 'Bound child input changed before execution: '+path)
    started = time.monotonic()
    snapshots = dict(payload['snapshots'])
    spec = importlib.util.spec_from_file_location('wp05_actual_native_roundtrip_validator', VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    evidence = module.validate_one(payload['row'], payload['part'], snapshots, [], bindings['validation_script_sha256'])
    after = {path:sha(path) for path in snapshots}
    unchanged = snapshots == after
    if not unchanged:
        evidence.update(status='FAIL', reason='Bound files changed during actual per-part validation')
    evidence['bounded_execution'] = dict(wrapper_script_path=bindings['wrapper_script_path'],
        wrapper_script_sha256=bindings['wrapper_script_sha256'], timeout_seconds=payload['timeout_seconds'],
        child_pid=os.getpid(), completed_validate_one=True, timed_out=False,
        elapsed_seconds=time.monotonic()-started, input_files_unchanged=unchanged)
    record = dict(schema='WP05_BOUNDED_ROUNDTRIP_ITEM_V1', part_key=payload['row']['part_key'],
        generated_utc=utc(), bindings=bindings, input_sha256_before=snapshots,
        input_sha256_after=after, input_files_unchanged=unchanged,
        completed_validate_one=True, timed_out=False, child_exit_code=0,
        roundtrip_validation=evidence,
        reusable=unchanged and evidence.get('status') in ('PASS', 'FAIL')
                 and 'volume_integration_method' in evidence)
    write(payload['result_path'], record)
    return 0


def reusable_cache(path, bindings):
    if not path.exists():
        return None
    try:
        item = read(path)
    except (ValueError, OSError):
        return None
    evidence = item.get('roundtrip_validation', {})
    return item if (item.get('bindings') == bindings and item.get('reusable') is True
        and item.get('completed_validate_one') is True and item.get('timed_out') is False
        and item.get('child_exit_code') == 0 and item.get('input_files_unchanged') is True
        and item.get('input_sha256_before') == item.get('input_sha256_after')
        and evidence.get('status') in ('PASS', 'FAIL')
        and evidence.get('validation_script_sha256') == bindings['validation_script_sha256']
        and evidence.get('bounded_execution', {}).get('wrapper_script_sha256') == bindings['wrapper_script_sha256']
        and evidence.get('source_sha256') == bindings['source_sha256']
        and evidence.get('native_sha256') == bindings['native_sha256']
        and evidence.get('roundtrip_sha256') == bindings['roundtrip_sha256']) else None


def run_item(row, part, bindings, snapshots, timeout_s):
    name = safe_key(row['part_key'])
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    attempt = ITEMS/'attempts'/(name+'_'+stamp)
    attempt.parent.mkdir(parents=True, exist_ok=True)
    payload_path = attempt.with_suffix('.job.json')
    result_path = attempt.with_suffix('.result.json')
    stdout_path, stderr_path = attempt.with_suffix('.stdout.log'), attempt.with_suffix('.stderr.log')
    snapshots = dict(snapshots)
    snapshots[str(VALIDATOR.resolve())] = bindings['validation_script_sha256']
    snapshots[str(Path(__file__).resolve())] = bindings['wrapper_script_sha256']
    write(payload_path, dict(row=row, part=part, bindings=bindings, snapshots=snapshots,
        timeout_seconds=timeout_s, result_path=str(result_path)))
    started = time.monotonic()
    child = None
    reason, event, code = None, None, None
    with stdout_path.open('wb') as stdout_file, stderr_path.open('wb') as stderr_file:
        try:
            child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--worker', str(payload_path)],
                stdin=subprocess.DEVNULL, stdout=stdout_file, stderr=stderr_file,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), cwd=str(ROOT))
            try:
                code = child.wait(timeout=timeout_s)
            except subprocess.TimeoutExpired:
                # Only this Popen-owned process is killed. The validator spawns no child tools.
                child.kill()
                code = child.wait(timeout=10)
                event, reason = 'TIMEOUT', 'Per-part actual validator exceeded its fixed execution limit'
            if event is None and code != 0:
                event, reason = 'CHILD_CRASH_OR_ERROR', 'Actual validator child exited without a completed successful execution receipt'
        except Exception as exc:
            if child is not None and child.poll() is None:
                child.kill()
                child.wait(timeout=10)
            event, reason = 'CHILD_NOT_STARTED_OR_FAILED', str(exc)
    elapsed = time.monotonic()-started
    context = dict(child_pid=None if child is None else child.pid, child_exit_code=code,
                   elapsed_seconds=elapsed, timed_out=event == 'TIMEOUT', termination_event=event,
                   stdout_path=str(stdout_path), stderr_path=str(stderr_path))
    if event is None and result_path.is_file():
        try:
            record = read(result_path)
            require(record.get('bindings') == bindings and record.get('completed_validate_one') is True,
                    'Child result binding or completion flag mismatch')
            require(record['roundtrip_validation']['validation_script_sha256'] == bindings['validation_script_sha256'],
                    'Child result points to another original validator')
            record['child_exit_code'] = code
            record['execution_logs'] = context
            return record
        except Exception as exc:
            event, reason = 'INVALID_CHILD_RECEIPT', str(exc)
            context['termination_event'] = event
    elif event is None:
        event, reason = 'NO_CHILD_RECEIPT', 'Child ended without a complete per-part evidence file'
        context['termination_event'] = event
    after = {p:sha(p) if Path(p).is_file() else None for p in snapshots}
    evidence = incomplete_evidence(row['part_key'], bindings, reason, timeout_s, **context)
    return dict(schema='WP05_BOUNDED_ROUNDTRIP_ITEM_V1', part_key=row['part_key'], generated_utc=utc(),
        bindings=bindings, completed_validate_one=False, timed_out=event == 'TIMEOUT',
        child_exit_code=code, reusable=False, input_sha256_before=snapshots,
        input_sha256_after=after, input_files_unchanged=after == snapshots,
        execution_logs=context, roundtrip_validation=evidence)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--imports', type=Path, default=ROOT/'results/NATIVE_IMPORTS.json')
    ap.add_argument('--manifest', type=Path, default=ROOT/'results/PARTS_SOURCE_MANIFEST_DEDUP.json')
    ap.add_argument('--limit', type=int)
    ap.add_argument('--timeout-seconds', type=float, default=60.0)
    ap.add_argument('--no-apply', action='store_true')
    ap.add_argument('--worker', type=Path, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.worker is not None:
        return worker(args.worker)
    require(0 < args.timeout_seconds <= 60, 'Per-part timeout must be positive and no greater than 60 seconds')
    require(args.limit is None or args.limit > 0, '--limit must be positive')
    imports_path, manifest_path = args.imports.resolve(), args.manifest.resolve()
    require(imports_path.is_relative_to(ROOT.resolve()) and manifest_path.is_relative_to(ROOT.resolve()),
            'Inputs must remain inside this delivery package')
    original_bytes = imports_path.read_bytes()
    original_hash = hashlib.sha256(original_bytes).hexdigest()
    original = json.loads(original_bytes.decode('utf-8-sig'))
    manifest = read(manifest_path)
    manifest_hash, validator_hash, wrapper_hash = sha(manifest_path), sha(VALIDATOR), sha(__file__)
    require(original.get('manifest_sha256') == manifest_hash, 'Native imports are bound to a different source manifest')
    by_key = {p['part_key']:p for p in manifest['parts']}
    require(len(by_key) == len(manifest['parts']), 'Duplicate source manifest part keys')
    require(len({r['part_key'] for r in original['parts']}) == len(original['parts']), 'Duplicate native import part keys')
    derived = copy.deepcopy(original)
    indices = [i for i,r in enumerate(derived['parts'])
               if isinstance(r.get('roundtrip'), dict) or r.get('source_comparison', {}).get('pass') is not True]
    selected = set(indices if args.limit is None else indices[:args.limit])
    before = {str(imports_path):original_hash, str(manifest_path):manifest_hash,
              str(VALIDATOR.resolve()):validator_hash, str(Path(__file__).resolve()):wrapper_hash}
    reports, reused_count = [], 0
    ITEMS.mkdir(parents=True, exist_ok=True)
    for i in indices:
        row = derived['parts'][i]
        part = by_key.get(row['part_key'])
        bindings, snapshots, issues = verify_inputs(row, part, manifest_hash, validator_hash, wrapper_hash)
        before.update(snapshots)
        item_path = ITEMS/(safe_key(row['part_key'])+'.json')
        evidence, item = None, None
        if i not in selected:
            evidence = incomplete_evidence(row['part_key'], bindings, 'NOT_SELECTED_IN_THIS_BOUNDED_RUN',
                                           args.timeout_seconds, termination_event='NOT_SELECTED', timed_out=False)
        elif issues:
            evidence = incomplete_evidence(row['part_key'], bindings, '; '.join(issues),
                                           args.timeout_seconds, termination_event='INPUT_BINDING_OR_EXPORT_INCOMPLETE', timed_out=False)
            item = dict(schema='WP05_BOUNDED_ROUNDTRIP_ITEM_V1', part_key=row['part_key'], generated_utc=utc(),
                bindings=bindings, reusable=False, completed_validate_one=False, timed_out=False,
                child_exit_code=None, input_sha256_before=snapshots, input_sha256_after=dict(snapshots),
                input_files_unchanged=True, roundtrip_validation=evidence)
            persist_item(item_path, item)
        else:
            item = reusable_cache(item_path, bindings)
            if item is not None:
                reused_count += 1
                evidence = copy.deepcopy(item['roundtrip_validation'])
                evidence['cache_reuse'] = dict(item_path=str(item_path), item_sha256=sha(item_path),
                                               source_native_roundtrip_rehashed=True, wrapper_and_validator_sha_match=True)
                progress('roundtrip_cache_reused', part_key=row['part_key'], status=evidence['status'])
            else:
                progress('roundtrip_child_start', part_key=row['part_key'], timeout_seconds=args.timeout_seconds)
                item = run_item(row, part, bindings, snapshots, args.timeout_seconds)
                # Rehash before persisting/cache admission, independent of what the child reported.
                current = {p:sha(p) if Path(p).is_file() else None for p in item['input_sha256_before']}
                if current != item['input_sha256_before']:
                    item['reusable'] = False
                    item['input_files_unchanged'] = False
                    item['input_sha256_after'] = current
                    item['roundtrip_validation'].update(status='FAIL', reason='Actual files changed before per-part persistence')
                persist_item(item_path, item)
                evidence = copy.deepcopy(item['roundtrip_validation'])
        old_comparison = copy.deepcopy(row.get('source_comparison', {}))
        row.setdefault('source_comparison', {})['roundtrip_validation'] = evidence
        require(without_evidence(row) == without_evidence(original['parts'][i]), 'Original scalar/native witness was changed')
        reports.append(dict(part_key=row['part_key'], original_source_comparison=old_comparison,
                            roundtrip_validation=evidence,
                            persistent_item=None if i not in selected else dict(path=str(item_path), sha256=sha(item_path))))
        progress('roundtrip_item_finished', part_key=row['part_key'], status=evidence['status'],
                 examined=len(reports), candidate_count=len(indices))
        # All completed items already exist independently if this wrapper is later stopped.
    after = {p:sha(p) if Path(p).is_file() else None for p in before}
    unchanged = before == after
    if not unchanged:
        for report in reports:
            report['roundtrip_validation'].update(status='FAIL', reason='Bound files changed during the bounded validation run')
    counts = dict(Counter(r['roundtrip_validation']['status'] for r in reports))
    status = ('FAIL' if counts.get('FAIL') or not unchanged else 'INCOMPLETE' if counts.get('INCOMPLETE') else
              'PASS_RECORDED_ROUNDTRIP_GEOMETRY_ONLY' if reports else 'INCOMPLETE')
    summary = dict(schema='WP05_NATIVE_ROUNDTRIP_VALIDATION_V1', status=status, generated_utc=utc(), counts=counts,
        available_native_receipt_count=len(original['parts']), source_manifest_part_count=len(by_key),
        candidate_roundtrip_count=len(indices), examined_count=len(selected),
        deferred_part_keys=[derived['parts'][i]['part_key'] for i in indices if i not in selected],
        limited_scope=len(selected) < len(indices), input_sha256_before=before, input_sha256_after=after,
        input_files_unchanged=unchanged, results=reports, original_scalar_witnesses_unchanged=True,
        timeout_seconds_per_part=args.timeout_seconds, reused_item_count=reused_count,
        wrapper_script_path=str(Path(__file__).resolve()), wrapper_script_sha256=wrapper_hash,
        validation_script_path=str(VALIDATOR.resolve()), validation_script_sha256=validator_hash,
        parent_loads_cad=False, child_processes_serial=True, com_export_executed=False,
        full_native_delivery_complete=False, physical_assembly_completed=False, manufacturing_release=False)
    derived_path = ROOT/'results/NATIVE_IMPORTS_ROUNDTRIP_VALIDATED.json'
    write(derived_path, derived)
    summary['derived_imports'] = dict(path=str(derived_path), sha256=sha(derived_path))
    if not args.no_apply and unchanged:
        backup = ROOT/'results/native_import_history'/('NATIVE_IMPORTS_'+original_hash+'.json')
        backup.parent.mkdir(parents=True, exist_ok=True)
        if backup.exists():
            require(sha(backup) == original_hash, 'Original native imports history SHA mismatch')
        else:
            backup.write_bytes(original_bytes)
        require(sha(imports_path) == original_hash, 'Native imports changed immediately before evidence attachment')
        write(imports_path, derived)
        summary['applied_imports'] = dict(path=str(imports_path), sha256=sha(imports_path))
        summary['original_imports_preserved'] = dict(path=str(backup), sha256=sha(backup))
    result_path = ROOT/'results/NATIVE_ROUNDTRIP_VALIDATION.json'
    if result_path.exists():
        data = result_path.read_bytes()
        old_report = ROOT/'results/native_import_history'/('NATIVE_ROUNDTRIP_VALIDATION_'+hashlib.sha256(data).hexdigest()+'.json')
        old_report.parent.mkdir(parents=True, exist_ok=True)
        if not old_report.exists():
            old_report.write_bytes(data)
    write(result_path, summary)
    progress('bounded_roundtrip_finished', status=status, counts=counts, reused=reused_count, report=str(result_path))
    return 1 if status == 'FAIL' else 2 if status == 'INCOMPLETE' else 0


if __name__ == '__main__':
    raise SystemExit(main())
