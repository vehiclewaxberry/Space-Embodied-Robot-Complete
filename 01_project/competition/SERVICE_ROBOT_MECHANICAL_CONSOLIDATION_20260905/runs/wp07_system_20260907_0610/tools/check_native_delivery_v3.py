"""Independent WP07 native-delivery evidence check; no CAD/COM/OCP is loaded.

This checks persisted ACTUAL native cold measurements against the manifest and
current file bytes. It does not read a nonexistent whole STEP, infer global BRep
validity, or claim that source composites are SolidWorks roundtrip exports.
"""
from pathlib import Path
import argparse
import copy
import datetime as dt
import json
import math
import sys
import traceback

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_integration_readback as core

R = HERE.parent
STATES = ('service', 'parking', 'released')
PASS = 'PASS_SCOPED_NATIVE_THREE_STATE_EVIDENCE_WITH_INHERITED_GEOMETRY_HOLDS'


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def preferred_receipt(state):
    if state != 'service':
        return R/'results'/('NATIVE_'+state.upper()+'.json')
    candidates = [R/'results'/name for name in (
        'NATIVE_SERVICE_RECOVERY_FAST_V2.json', 'NATIVE_SERVICE_RECOVERY_FAST.json',
        'NATIVE_SERVICE_RECOVERY.json', 'NATIVE_SERVICE.json')]
    existing = [path for path in candidates if path.is_file()]
    # A completed newer receipt outranks every old partial receipt. Prefer a
    # completed receipt over a newer partial attempt when the saved bytes agree.
    for path in existing:
        try:
            data = core.read(path)
            cold = data.get('cold_inspection', {})
            digest = data.get('final_native_sha256')
            if (data.get('status', '').startswith('PASS_') and data.get('inputs_unchanged') is True
                    and cold.get('component_count') == 597 and cold.get('solid_count') == 978
                    and digest and data.get('cold_inspection_native_sha256') == digest
                    and core.sha(R/'native/WP07_ROBOT_SERVICE.SLDASM') == digest):
                return path
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return existing[0] if existing else candidates[-1]


def strict_native_rows_check(observed, expected):
    """The same validator handles the real observations and all memory-only faults."""
    result = core.native_rows_check(observed, expected)
    explicit_vectors = len(observed) == 597 and all(
        isinstance(row.get('world_basis_points_mm'), (list, tuple)) and
        len(row['world_basis_points_mm']) == 4 and all(
            isinstance(p, (list, tuple)) and len(p) == 3 and all(
                isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in p)
            for p in row['world_basis_points_mm']) for row in observed)
    result['all_actual_COM_four_point_vectors_persisted'] = explicit_vectors
    result['status'] = 'PASS' if result['status'] == 'PASS' and explicit_vectors else 'FAIL'
    result['independent_scope'] = (
        'PERSISTED_ACTUAL_NATIVE_BODY_COUNTS_PATHS_HASHES_FIXED_POSES; '
        'INDEPENDENT_RECOMPUTATION_OF_ACTUAL_16_MATRIX_AND_ALL_FOUR_STORED_COM_VECTORS_AGAINST_SOURCE_TRANSFORMS')
    return result


def fault_summary(name, fault, expected, identity, mutation):
    checked = strict_native_rows_check(fault, expected)
    failures = [dict(id=row['id'], failed_checks=[k for k, ok in row['checks'].items() if not ok])
                for row in checked['results'] if row['status'] != 'PASS']
    return dict(name=name, status='PASS_REJECTED' if checked['status'] == 'FAIL' else 'FAIL_FAULT_ACCEPTED',
                mutated_id=identity, mutation=mutation, validator_status=checked['status'],
                coverage_pass=checked['coverage_pass'], failures=failures,
                all_actual_COM_four_point_vectors_persisted=checked['all_actual_COM_four_point_vectors_persisted'],
                scope='MEMORY_ONLY_OBSERVATION_FAULT; NO_NATIVE_FILE_OR_ASSEMBLY_EDITED')


def negative_controls(observed, expected, manifest):
    replaced = next(r for r in expected if r['change'] == 'REPLACE_SINGLE_INSTANCE' and 'clip' in r['id'])
    old = replaced['previous_native']
    require(Path(old['path']).is_file() and core.sha(old['path']) == old['sha256'],
            'Wrong-old-part control must use an actual pinned original native part')
    wrong_old = copy.deepcopy(observed)
    row = next(r for r in wrong_old if r['id'] == replaced['id'])
    row.update(path=old['path'], sha256=old['sha256'])
    controls = [fault_summary('wrong_original_clip_native', wrong_old, expected, replaced['id'],
                             dict(path=old['path'], sha256=old['sha256']))]
    wrong_pose = copy.deepcopy(observed)
    row = next(r for r in wrong_pose if r['id'] == replaced['id'])
    row['transform_sw16'][9] += 0.001  # actual SW translation uses metres
    controls.append(fault_summary('actual_matrix_translation_plus_1_mm', wrong_pose, expected,
                                  replaced['id'], dict(sw_tx_delta_m=0.001)))
    missing_id = manifest['added_ids'][0]
    require(any(r['id'] == missing_id for r in observed), 'Missing-component fault target is absent')
    controls.append(fault_summary('one_added_hardware_missing',
                                  [copy.deepcopy(r) for r in observed if r['id'] != missing_id], expected,
                                  missing_id, dict(removed_observation=True)))
    wrong_vector = copy.deepcopy(observed)
    row = next(r for r in wrong_vector if r['id'] == replaced['id'])
    row['world_basis_points_mm'][0][0] += 1.
    controls.append(fault_summary('actual_COM_basis_origin_plus_1_mm', wrong_vector, expected,
                                  replaced['id'], dict(actual_world_x_delta_mm=1.)))
    missing_vectors = copy.deepcopy(observed)
    next(r for r in missing_vectors if r['id'] == replaced['id']).pop('world_basis_points_mm')
    controls.append(fault_summary('actual_COM_vectors_missing', missing_vectors, expected,
                                  replaced['id'], dict(removed_actual_COM_vectors=True)))
    return controls, {str(Path(old['path']).resolve()): old['sha256']}


def pin_file(path, expected, pins, cache):
    resolved = str(Path(path).resolve())
    key = core.norm(path)
    require(Path(resolved).is_file(), 'Required real file is absent: '+resolved)
    if key not in cache:
        cache[key] = core.sha(resolved)
    require(cache[key] == expected, 'Pinned file SHA mismatch: '+resolved)
    require(resolved not in pins or pins[resolved] == expected, 'Conflicting file pin: '+resolved)
    pins[resolved] = expected


def check_state(state, manifest, manifest_sha, pins, cache):
    receipt_path = preferred_receipt(state)
    require(receipt_path.is_file(), 'Native cold receipt missing: '+str(receipt_path))
    receipt = core.read(receipt_path)
    pin_file(receipt_path, core.sha(receipt_path), pins, cache)
    require(receipt.get('status', '').startswith('PASS_'), 'Native producer did not complete: '+str(receipt_path))
    require(receipt.get('state') == state and receipt.get('manifest_sha256') == manifest_sha,
            'Native receipt state or manifest binding differs')
    require(receipt.get('inputs_unchanged') is True, 'Producer final source/dependency hash audit did not complete')
    expected_last = 'recovery_completed' if state == 'service' and receipt_path.name in ('NATIVE_SERVICE_RECOVERY.json', 'NATIVE_SERVICE_RECOVERY_FAST.json', 'NATIVE_SERVICE_RECOVERY_FAST_V2.json') else 'completed'
    require(receipt.get('progress') and receipt['progress'][-1]['stage'] == expected_last,
            'Producer has no final completion checkpoint')
    info = manifest['states'][state]
    expected = info['instances']
    require(len(expected) == 597 and sum(r['expected_solids'] for r in expected) == 978, 'Manifest totals changed')
    assembly = R/'native'/('WP07_ROBOT_'+state.upper()+'.SLDASM')
    digest = receipt['final_native_sha256']
    pin_file(assembly, digest, pins, cache)
    require(receipt.get('cold_inspection_native_sha256') == digest, 'Cold body evidence is not bound to final native bytes')
    cold = receipt.get('cold_inspection', {})
    require(cold.get('component_count') == 597 and cold.get('solid_count') == 978,
            'Native cold observation totals incomplete')
    require(core.norm(cold.get('assembly_path', '')) == core.norm(assembly), 'Cold observation saved path mismatch')
    actual = cold.get('components', [])
    checked = strict_native_rows_check(actual, expected)
    require(checked['status'] == 'PASS', 'Independent native metadata/four-point/body evidence check failed: '+state)
    source_files, native_files = set(), set()
    for row in expected:
        pin_file(row['native_path'], row['native_sha256'], pins, cache)
        pin_file(row['step_path'], row['source_sha256'], pins, cache)
        source_files.add(core.norm(row['step_path']))
        native_files.add(core.norm(row['native_path']))
    require(len(native_files) == 445, 'Expected 445 actual native dependencies')
    if 'dependency_paths' in cold:
        require({core.norm(p) for p in cold['dependency_paths']} == native_files,
                'Persisted native GetDependencies2 paths differ')
    counts = {kind: sum(r['change'] == kind for r in expected)
              for kind in ('RETAIN_UNCHANGED', 'REPLACE_SINGLE_INSTANCE', 'ADD_HARDWARE')}
    require(counts == dict(RETAIN_UNCHANGED=573, REPLACE_SINGLE_INSTANCE=8, ADD_HARDWARE=16),
            'Native integration delta differs')
    expected_ids = {r['id'] for r in expected}
    require(not (set(manifest['removed_ids']) & expected_ids), 'Removed bare screws reappeared')
    require(set(manifest['added_ids']) <= expected_ids and set(manifest['replaced_ids']) <= expected_ids,
            'Changed-part coverage differs')
    require(len(info['context_ids_retained_once']) == info['context_count'] and
            len(set(info['context_ids_retained_once'])) == info['context_count'] and
            set(info['context_ids_retained_once']) <= expected_ids, 'Context instance coverage differs')
    arms = set(info['arm_ids_unchanged'])
    require(len(arms) == 10 and all(r['change'] == 'RETAIN_UNCHANGED' for r in expected if r['id'] in arms),
            'Inherited B601 identities changed')
    controls, extra_pins = negative_controls(actual, expected, manifest)
    for path, oldsha in extra_pins.items():
        pin_file(path, oldsha, pins, cache)
    require(all(c['status'] == 'PASS_REJECTED' for c in controls), 'Native metadata negative control was accepted')
    whole = R/'native'/('WP07_ROBOT_'+state.upper()+'.step')
    return dict(status='PASS_SCOPED_NATIVE_EVIDENCE', state=state, native_path=str(assembly),
                final_native_sha256=digest, receipt_path=str(receipt_path), receipt_sha256=pins[str(receipt_path.resolve())],
                component_count=597, measured_solid_count_from_bound_actual_cold=978, unique_native_dependencies=445,
                source_STEP_files_checked=len(source_files), delta_counts=counts,
                native_measurement_check=checked, negative_controls=controls,
                native_whole_STEP=dict(path=str(whole), exists=whole.is_file(), verified=False,
                    status='NOT_EVALUATED_BY_THIS_NATIVE_RECEIPT_CHECKER'),
                inherited_B601_arm_instance_count=10, inherited_B601_geometry_holds_unchanged=True,
                context_retained_once_count=info['context_count'], global_material_equivalence_verified=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', choices=('all',)+STATES, default='all')
    args = parser.parse_args()
    output = R/'results'/('NATIVE_DELIVERY_CHECK_'+args.state.upper()+'.json')
    require(not output.exists(), 'Existing independent receipt is protected: '+str(output))
    manifest_path = R/'results/INTEGRATION_MANIFEST.json'
    manifest, manifest_sha = core.read(manifest_path), core.sha(manifest_path)
    pins, cache = {}, {}
    report = dict(schema='WP07_NATIVE_DELIVERY_INDEPENDENT_V1', status='RUNNING',
                  generated_utc=dt.datetime.now(dt.timezone.utc).isoformat(), manifest_sha256=manifest_sha,
                  requested_states=list(STATES) if args.state == 'all' else [args.state], states={},
                  scope='INDEPENDENT_REPLAY_OF_ACTUAL_NATIVE_COLD_MEASUREMENTS_AND_CURRENT_FILE_HASHES',
                  full_native_STEP_verified=False, full_source_STEP_verified=False,
                  global_material_equivalence_verified=False, continuous_motion_verified=False,
                  physical_assembly_completed=False, strength_verified=False, manufacturing_release=False,
                  inherited_arm_status=manifest['retained_arm_status'])
    try:
        for source in (Path(__file__).resolve(), Path(core.__file__).resolve(), manifest_path):
            pin_file(source, core.sha(source), pins, cache)
        core.write(output, report)
        for state in report['requested_states']:
            report['states'][state] = check_state(state, manifest, manifest_sha, pins, cache)
            report['input_sha256_before'] = pins
            core.write(output, report)
        after = {p: core.sha(p) for p in pins}
        require(after == pins, 'Input bytes changed during independent native check')
        report.update(input_sha256_before=pins, input_sha256_after=after, inputs_unchanged=True,
                      status=PASS if args.state == 'all' else 'PASS_SCOPED_SINGLE_NATIVE_STATE_WITH_INHERITED_GEOMETRY_HOLDS')
        core.write(output, report)
        print(json.dumps(dict(status=report['status'], output=str(output), states=report['requested_states']), ensure_ascii=False))
    except Exception as exc:
        report.update(status='FAILED', error=str(exc), traceback=traceback.format_exc())
        core.write(output, report)
        raise


if __name__ == '__main__':
    main()
