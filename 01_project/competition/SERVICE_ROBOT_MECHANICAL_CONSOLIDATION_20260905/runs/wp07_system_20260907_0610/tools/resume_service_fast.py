"""Bounded SERVICE recovery with paused UI updates and batched unloading.

Example pilot, only after the previous guard has finished:
  resume_service_fast.py --prior-receipt results/NATIVE_SERVICE_RECOVERY.json
    --prior-guard logs/resume_service.run.json --limit-new 25

Default output is NATIVE_SERVICE_RECOVERY_FAST.json; a limited run writes
NATIVE_SERVICE_FAST_PILOT.json. Existing outputs are protected. Repeat with the
pilot as --prior-receipt to retain its measured prefix. No native save, full
resolution, named view, zoom, explicit redraw, screenshot or STEP export occurs.
"""
from pathlib import Path
import argparse
import copy
import gc
import json
import math
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import resume_service as slow
import check_native_delivery as check
from integrate_native import R, require, sha, normalized, val, t16


def validate_prefix(prior_path, guard_path, manifest, manifest_sha):
    import psutil
    prior_path, guard_path = prior_path.resolve(), guard_path.resolve()
    require(prior_path.is_relative_to((R/'results').resolve()) and
            guard_path.is_relative_to((R/'logs').resolve()), 'Prefix receipts must be run-local')
    prior, guard = slow.read_json(prior_path), slow.read_json(guard_path)
    require(guard.get('status') in ('COMPLETED', 'COMMAND_FAILED', 'TIMEOUT_GUARD', 'AVAILABLE_MEMORY_GUARD',
                                  'JOB_WORKING_SET_GUARD', 'MONITOR_OR_LAUNCH_ERROR_FAIL_CLOSED'),
            'Previous guard is still running or has no ended-worker evidence')
    require(guard.get('pid') and not psutil.pid_exists(guard['pid']), 'Previous worker PID is still alive; no concurrent COM allowed')
    require(normalized(guard['cwd']) == normalized(R), 'Previous guard belongs to another run')
    implementation = prior.get('implementation', {})
    source = Path(implementation.get('path', '')).resolve()
    require(source.is_relative_to(HERE) and source.is_file() and sha(source) == implementation.get('sha256'),
            'Previous measurement source pin is unavailable or changed')
    require(any(Path(arg).name.casefold() == source.name.casefold() for arg in guard['command']),
            'Guard command does not identify the previous measurement source')
    require(prior.get('state') == 'service' and prior.get('manifest_sha256') == manifest_sha,
            'Previous measurement state/manifest differs')
    saved = prior.get('cold_inspection_native_sha256') or prior.get('controlled_recovery', {}).get('saved_native_sha256')
    require(saved == slow.SAVED_SHA and sha(slow.SERVICE) == saved, 'Prefix is not bound to unchanged saved SERVICE bytes')
    cold = prior.get('cold_inspection', {})
    observed = cold.get('components', [])
    require(core_path(cold.get('assembly_path', '')) == core_path(slow.SERVICE), 'Prefix assembly path differs')
    require(0 < len(observed) <= 597 and len({r['id'] for r in observed}) == len(observed), 'Empty or duplicate prefix')
    require(cold.get('component_count') == len(observed) and
            cold.get('solid_count') == sum(r['solid_count'] for r in observed), 'Prefix checkpoint totals differ')
    expected = manifest['states']['service']['instances']
    by_id = {r['id']: r for r in expected}
    require(all(r['id'] in by_id for r in observed), 'Prefix contains an unknown instance')
    validated = check.core.native_rows_check(observed, expected)
    require(len(validated['results']) == len(observed) and all(r['status'] == 'PASS' for r in validated['results']),
            'Prefix measurement does not match source paths/hashes/body counts/matrices/points')
    require(all(r['direct_com_basis_status'] == 'ACTUAL_VECTORS_CHECKED' for r in validated['results']),
            'Prefix lacks actual COM four-point vectors')
    for row in observed:
        require(sha(row['path']) == by_id[row['id']]['native_sha256'], 'Measured prefix native part changed')
    pins = {str(prior_path): sha(prior_path), str(guard_path): sha(guard_path), str(source): sha(source)}
    return copy.deepcopy(observed), dict(receipt_path=str(prior_path), receipt_sha256=pins[str(prior_path)],
        guard_path=str(guard_path), guard_sha256=pins[str(guard_path)], previous_guard_status=guard['status'],
        source_path=str(source), source_sha256=pins[str(source)], reused_measured_count=len(observed),
        saved_native_sha256=saved,
        scope='PREVIOUS_ACTUAL_BODY_AND_COM_POINT_MEASUREMENTS_ON_IDENTICAL_SAVED_NATIVE_AND_DEPENDENCY_BYTES; '
              'CURRENT_REOPEN_WILL_RECHECK_IDS_PATHS_HASHES_TRANSFORMS_FOR_ALL_INSTANCES'), pins


def core_path(path):
    return normalized(path)


class FastIntegrator(slow.ComponentwiseIntegrator):
    batch_size = 25
    limit_new = 0
    prefix = ()

    def inspect(self, model, rows, expected_path):
        require(normalized(val(model, 'GetPathName')) == normalized(expected_path), 'Saved path mismatch')
        assembly = self.wrap(model, 'IAssemblyDoc')
        view = self.wrap(model.ActiveView, 'IModelView')
        feature = self.wrap(model.FeatureManager, 'IFeatureManager')
        require(view is not None and feature is not None, 'Actual UI control interfaces unavailable')
        controls = [(self.sw, 'CommandInProgress', True), (view, 'EnableGraphicsUpdate', False),
                    (feature, 'EnableFeatureTree', False), (feature, 'EnableFeatureTreeWindow', False)]
        before = [(obj, name, bool(getattr(obj, name))) for obj, name, _ in controls]
        report = self.report
        report['ui_control_before'] = {name: old for _, name, old in before}
        result = dict(status='RUNNING_BATCHED_COLD', component_count=len(self.prefix),
                      solid_count=sum(r['solid_count'] for r in self.prefix), components=list(self.prefix),
                      assembly_path=str(expected_path), expected_component_count=597, expected_solid_count=978,
                      inherited_measurement_count=len(self.prefix), new_measurement_count=0,
                      full_resolution_used=False, batch_unload_size=self.batch_size,
                      scope='ACTUAL_BODY_AND_COM_FOUR_POINT_MEASUREMENTS_ON_IDENTICAL_PINNED_NATIVE_BYTES; '
                            'DECLARED_PRIOR_PREFIX_PLUS_NEW_SUFFIX; ALL_CURRENT_COMPONENT_METADATA_RECHECKED')
        report['cold_inspection'] = result
        report['batch_timings'] = []
        installed = []
        all_started = time.monotonic()
        try:
            for obj, name, wanted in controls:
                installed.append(name)
                setattr(obj, name, wanted)
                require(bool(getattr(obj, name)) == wanted, 'UI control did not accept requested value: '+name)
            report['ui_controls_applied'] = {name: bool(getattr(obj, name)) for obj, name, _ in controls}
            model.ClearSelection2(True)
            result['initial_unload_api_return'] = assembly.LightweightAllResolved()
            raw = assembly.GetComponents(True) or []
            expected = {r['id']: r for r in rows}
            require(len(raw) == len(expected) == 597, 'Actual instance count differs')
            lookup, hashes, current = {}, {}, []
            for item in raw:
                component = self.wrap(item, 'IComponent2')
                identity = component.ComponentReference
                require(identity in expected and identity not in lookup, 'Unknown/duplicate current identity')
                row = expected[identity]
                path = normalized(val(component, 'GetPathName'))
                require(path == normalized(row['native_path']), 'Current dependency path differs')
                if path not in hashes:
                    hashes[path] = sha(path)
                require(hashes[path] == row['native_sha256'], 'Current native part SHA differs')
                transform = self.wrap(component.Transform2, 'IMathTransform')
                matrix = list(transform.ArrayData)
                transform = None
                require(len(matrix) == 16 and all(math.isfinite(v) for v in matrix), 'Invalid current transform')
                error = max(abs(a-b) for a, b in zip(matrix, t16(row['T_S_local'])))
                require(error < 1e-8 and component.IsFixed(), 'Current fixed transform differs')
                require(component.GetSuppression2() in (1, 2, 4), 'Current component suppressed or invalid')
                lookup[identity] = component
                current.append(dict(id=identity, path=path, sha256=hashes[path], transform_sw16=matrix, fixed=True))
            report['current_reopen_metadata'] = dict(component_count=597, components=current,
                scope='ALL_ACTUAL_CURRENT_IDS_PATHS_HASHES_FIXED_TRANSFORMS; NO_BODY_REUSE_CREDIT_FROM_METADATA_ALONE')
            reused = {r['id'] for r in self.prefix}
            todo = [r for r in rows if r['id'] not in reused]
            if self.limit_new:
                todo = todo[:self.limit_new]
            self.checkpoint('fast_current_metadata_and_prefix_checked', reused=len(reused), new_planned=len(todo),
                            memory=self.memory_snapshot())
            for start in range(0, len(todo), self.batch_size):
                group = todo[start:start+self.batch_size]
                timing = dict(batch_index=len(report['batch_timings']), count=len(group), resolve_s=0., measure_s=0., unload_s=0.)
                begin = time.monotonic()
                completed = []
                try:
                    for row in group:
                        if self.psutil.virtual_memory().available < 768*1024**2:
                            gc.collect()
                            emergency = assembly.LightweightAllResolved()
                            timing.setdefault('early_memory_unloads', []).append(dict(
                                api_return=emergency, before_component=row['id'], memory=self.memory_snapshot()))
                        self.ram_floor()
                        component = lookup[row['id']]
                        report['active_component'] = row['id']
                        tick = time.monotonic()
                        resolve_return = None
                        if component.GetSuppression2() != 2:
                            resolve_return = component.SetSuppression2(2)
                        require(component.GetSuppression2() == 2, 'Single-component resolution failed: '+row['id'])
                        timing['resolve_s'] += time.monotonic()-tick
                        tick = time.monotonic()
                        observation = self._measure_resolved(component, row, hashes[normalized(row['native_path'])])
                        timing['measure_s'] += time.monotonic()-tick
                        observation['resolve_api_return'] = resolve_return
                        observation['measurement_session'] = str(self.report_path)
                        result['components'].append(observation)
                        result['component_count'] += 1
                        result['solid_count'] += observation['solid_count']
                        result['new_measurement_count'] += 1
                        completed.append(observation)
                        component = None
                        # Part/body wrappers were released by _measure_resolved.
                        # No per-component SetSuppression2(1) or per-item gc sweep.
                finally:
                    tick = time.monotonic()
                    gc.collect()
                    timing['unload_api_return'] = assembly.LightweightAllResolved()
                    for observation in completed:
                        state = lookup[observation['id']].GetSuppression2()
                        require(state in (1, 4), 'Batch did not unload measured component: '+observation['id'])
                        observation['final_suppression_state'] = state
                        observation['unload_method'] = 'BATCH_LIGHTWEIGHT_ALL_RESOLVED'
                    timing['unload_s'] = time.monotonic()-tick
                    timing['elapsed_s'] = time.monotonic()-begin
                    timing['memory_after'] = self.memory_snapshot()
                    report['batch_timings'].append(timing)
                    self.checkpoint('fast_batch_measurements_persisted', completed=result['component_count'],
                                    new_completed=result['new_measurement_count'], elapsed_s=timing['elapsed_s'])
            require(len({r['id'] for r in result['components']}) == result['component_count'], 'Duplicate combined evidence IDs')
            deps = model.GetDependencies2(False, True, False) or []
            require(len(deps) % 2 == 0, 'Malformed native dependency result')
            paths = [deps[i+1] for i in range(0, len(deps), 2)]
            require({normalized(p) for p in paths} == {normalized(r['native_path']) for r in rows}, 'Current dependency set differs')
            result.update(unique_dependencies=445, dependency_paths=paths)
            complete = result['component_count'] == 597
            if complete:
                require(result['solid_count'] == 978 and check.strict_native_rows_check(result['components'], rows)['status'] == 'PASS',
                        'Complete cold evidence failed independent strict replay')
            result['status'] = 'PASS_BATCHED_COLD' if complete else 'PILOT_PARTIAL_MEASUREMENTS_ONLY'
            result['completed_all_components'] = complete
            report['performance'] = dict(new_measurements=result['new_measurement_count'],
                total_inside_controls_s=time.monotonic()-all_started,
                batch_total_s=sum(b['elapsed_s'] for b in report['batch_timings']),
                baseline_declared_25_components_s=110., baseline_is_prior_observation_not_same_component_trial=True,
                optimization_speedup_verified=False)
            n = report['performance']['new_measurements']
            if n:
                report['performance']['measured_batch_seconds_per_component'] = report['performance']['batch_total_s']/n
                report['performance']['nominal_597_batch_seconds_at_measured_rate'] = report['performance']['batch_total_s']*597/n
            report.pop('active_component', None)
            # Persist every measured body/actual point BEFORE re-enabling graphics.
            self.checkpoint('all_available_cold_evidence_persisted_before_ui_restore', measured=result['component_count'],
                            all597_complete=complete)
            return result
        except Exception:
            result['status'] = 'FAILED_BATCHED_COLD_PARTIAL_ONLY'
            self.checkpoint('fast_cold_exception_preserved', measured=result['component_count'])
            raise
        finally:
            restore = []
            # State changes are restored, but no draw/zoom/view/screenshot is requested.
            for obj, name, old in reversed(before):
                if name not in installed:
                    continue
                try:
                    setattr(obj, name, old)
                    actual = bool(getattr(obj, name))
                    restore.append(dict(property=name, expected=old, actual=actual, restored=actual == old))
                except Exception as exc:
                    restore.append(dict(property=name, restored=False, error=repr(exc)))
            report['ui_control_restore'] = restore
            self.checkpoint('ui_controls_restored_without_explicit_redraw')
            require(all(r['restored'] for r in restore), 'UI control restoration failed; manual session recovery needed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prior-receipt', type=Path)
    parser.add_argument('--prior-guard', type=Path)
    parser.add_argument('--limit-new', type=int, default=0)
    parser.add_argument('--batch-size', type=int, choices=(10, 25, 50), default=25)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    require(bool(args.prior_receipt) == bool(args.prior_guard), 'Prefix receipt and guard must both be provided')
    require(0 <= args.limit_new <= 597, 'Invalid pilot measurement limit')
    output = args.output or R/'results'/('NATIVE_SERVICE_FAST_PILOT.json' if args.limit_new else 'NATIVE_SERVICE_RECOVERY_FAST.json')
    output = output.resolve()
    require(output.is_relative_to((R/'results').resolve()) and output.suffix.lower() == '.json' and not output.exists(),
            'Output must be new run-local results JSON')
    mfpath = R/'results/INTEGRATION_MANIFEST.json'
    manifest, mfsha = slow.read_json(mfpath), sha(mfpath)
    report = dict(status='RUNNING', state='service', manifest_sha256=mfsha, progress=[], save_attempts=[],
                  implementation=dict(path=str(Path(__file__).resolve()), sha256=sha(__file__)),
                  full_native_step_verified=False, full_step_export_status='NOT_ATTEMPTED_NATIVE_ONLY_RECOVERY',
                  no_native_save_performed=True, no_explicit_graphics_or_screenshot_calls=True)
    builder = None
    try:
        slow.require_outer_guard(report)
        proof, pins = slow.controlled_recovery(mfsha)
        report['controlled_recovery'] = proof
        prefix = []
        if args.prior_receipt:
            prefix, report['prefix_recovery'], prefix_pins = validate_prefix(args.prior_receipt, args.prior_guard, manifest, mfsha)
            pins.update(prefix_pins)
        allowed, receipt_pins = slow.registered_inputs(manifest, mfsha, include_service_recovery=False)
        pins.update(receipt_pins)
        for source in (mfpath, Path(__file__).resolve(), Path(slow.__file__).resolve(), Path(check.__file__).resolve(),
                       Path(check.core.__file__).resolve()):
            pins[str(source)] = sha(source)
        pins.update(allowed)
        for path, digest in pins.items():
            require(sha(path) == digest, 'Pinned recovery input changed: '+path)
        report['input_pins'] = pins
        slow.persist(output, report)
        builder = FastIntegrator(output, report)
        require(int(val(builder.sw, 'GetProcessID')) == 26208, 'Unexpected existing SolidWorks PID')
        builder.batch_size, builder.limit_new, builder.prefix = args.batch_size, args.limit_new, prefix
        builder.close_registered(allowed)
        gc.collect()
        model, report['cold_open'] = slow.open_readonly(builder, slow.SERVICE)
        report['cold_inspection'] = builder.inspect(model, manifest['states']['service']['instances'], slow.SERVICE)
        report.update(cold_inspection_native_sha256=slow.SAVED_SHA, final_native_sha256=slow.SAVED_SHA,
                      left_open_dirty_flag=bool(val(model, 'GetSaveFlag')))
        report['inputs_unchanged'] = all(sha(path) == digest for path, digest in pins.items())
        require(report['inputs_unchanged'], 'Pinned input bytes changed during fast recovery')
        report['status'] = ('PASS_NATIVE_SERVICE_COMPONENTWISE_COLD__FULL_STEP_NOT_VERIFIED'
                            if report['cold_inspection']['completed_all_components'] else 'PILOT_COMPLETE_PARTIAL_NATIVE_MEASUREMENTS_ONLY')
        builder.checkpoint('recovery_completed', measured=report['cold_inspection']['component_count'],
                           native_complete=report['cold_inspection']['completed_all_components'])
    except Exception as exc:
        report.update(status='FAILED', error=str(exc), traceback=traceback.format_exc())
        slow.persist(output, report)
        raise
    finally:
        if builder and builder.initialized:
            builder.pythoncom.CoUninitialize()


if __name__ == '__main__':
    main()
