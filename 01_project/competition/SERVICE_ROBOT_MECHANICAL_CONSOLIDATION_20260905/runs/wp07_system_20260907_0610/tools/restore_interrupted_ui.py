"""Restore only UI flags left paused by an ended, pinned WP07 SERVICE worker.

No activation, suppression change, close, save, rebuild, redraw, zoom, screenshot
or export. Requires the exact active saved SERVICE document and SW PID 26208.
Run under run_guard.py before the next COM task. All prior evidence is immutable.
"""
from pathlib import Path
import argparse
import sys
import traceback

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import resume_service as recovery
from integrate_native import Integrator, R, require, sha, normalized, val


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', type=Path, default=R/'results/NATIVE_SERVICE_RECOVERY_FAST.json')
    parser.add_argument('--guard', type=Path, default=R/'logs/recover_service_fast_full.run.json')
    parser.add_argument('--output', type=Path, default=R/'results/RESTORE_INTERRUPTED_UI.json')
    args = parser.parse_args()
    source, guard_path, output = args.receipt.resolve(), args.guard.resolve(), args.output.resolve()
    require(source.is_relative_to((R/'results').resolve()) and guard_path.is_relative_to((R/'logs').resolve()),
            'Restoration must use this run\'s existing receipts')
    require(output.is_relative_to((R/'results').resolve()) and output.suffix.lower() == '.json' and not output.exists(),
            'Restoration receipt must be a new run-local JSON')
    prior, guard = recovery.read_json(source), recovery.read_json(guard_path)
    require(guard.get('status') in ('AVAILABLE_MEMORY_GUARD', 'TIMEOUT_GUARD', 'JOB_WORKING_SET_GUARD',
                                  'COMMAND_FAILED', 'MONITOR_OR_LAUNCH_ERROR_FAIL_CLOSED'),
            'No ended interrupted-worker guard evidence')
    require(normalized(guard['cwd']) == normalized(R), 'Guard belongs to another run')
    import psutil
    require(guard.get('pid') and not psutil.pid_exists(guard['pid']), 'Interrupted worker PID is still alive')
    implementation = prior.get('implementation', {})
    script = Path(implementation.get('path', '')).resolve()
    require(script.is_relative_to(HERE) and script.is_file() and sha(script) == implementation.get('sha256'),
            'Interrupted worker source pin differs')
    require(any(Path(x).name.casefold() == script.name.casefold() for x in guard['command']),
            'Guard does not identify the interrupted worker')
    require(prior.get('state') == 'service' and
            prior.get('cold_open', {}).get('native_sha256') == recovery.SAVED_SHA,
            'Interrupted worker does not bind to the saved SERVICE file')
    before = prior.get('ui_control_before', {})
    names = {'CommandInProgress', 'EnableGraphicsUpdate', 'EnableFeatureTree', 'EnableFeatureTreeWindow'}
    require(set(before) == names and all(type(before[k]) is bool for k in names), 'Original UI flags are not completely recorded')
    require(sha(recovery.SERVICE) == recovery.SAVED_SHA, 'Saved SERVICE bytes changed')
    pins = {str(source): sha(source), str(guard_path): sha(guard_path), str(script): sha(script),
            str(Path(__file__).resolve()): sha(__file__), str(recovery.SERVICE): recovery.SAVED_SHA,
            str(R/'results/INTEGRATION_MANIFEST.json'): prior['manifest_sha256']}
    for path, digest in pins.items():
        require(sha(path) == digest, 'Restoration input pin differs: '+path)
    report = dict(schema='WP07_INTERRUPTED_UI_RESTORATION_V1', status='RUNNING', progress=[], state='service',
                  prior_receipt_path=str(source), prior_receipt_sha256=pins[str(source)],
                  ended_guard_status=guard['status'], guard_path=str(guard_path), guard_sha256=pins[str(guard_path)],
                  target_ui_flags=before, native_path=str(recovery.SERVICE), native_sha256=recovery.SAVED_SHA,
                  input_sha256_before=pins, scope='SESSION_UI_FLAGS_ONLY', no_native_save=True,
                  no_redraw_or_screenshot=True, no_model_activation_or_suppression_change=True,
                  restored_properties=[])
    builder = None
    try:
        recovery.require_outer_guard(report)
        recovery.persist(output, report)
        builder = Integrator(output, report)
        require(int(val(builder.sw, 'GetProcessID')) == 26208, 'Unexpected existing SolidWorks PID')
        model = builder.wrap(val(builder.sw, 'ActiveDoc'), 'IModelDoc2')
        require(model is not None and normalized(val(model, 'GetPathName')) == normalized(recovery.SERVICE),
                'Active document is not the owned, saved SERVICE assembly; no UI flag changed')
        report['active_document_dirty_before'] = bool(val(model, 'GetSaveFlag'))
        view = builder.wrap(model.ActiveView, 'IModelView')
        feature = builder.wrap(model.FeatureManager, 'IFeatureManager')
        require(view is not None and feature is not None, 'Actual UI interfaces unavailable')
        objects = {'CommandInProgress': builder.sw, 'EnableGraphicsUpdate': view,
                   'EnableFeatureTree': feature, 'EnableFeatureTreeWindow': feature}
        report['observed_ui_flags_before'] = {k: bool(getattr(objects[k], k)) for k in names}
        builder.checkpoint('pinned_interrupted_ui_restoration_preflight_complete')
        for name in ('EnableFeatureTreeWindow', 'EnableFeatureTree', 'EnableGraphicsUpdate', 'CommandInProgress'):
            observed = bool(getattr(objects[name], name))
            if observed != before[name]:
                setattr(objects[name], name, before[name])
            actual = bool(getattr(objects[name], name))
            report['restored_properties'].append(dict(name=name, observed_before=observed,
                target=before[name], actual_after=actual, changed=observed != before[name], restored=actual == before[name]))
            builder.checkpoint('actual_ui_flag_restored', property=name, target=before[name], actual=actual)
            require(actual == before[name], 'UI flag restoration did not persist: '+name)
        require(normalized(val(model, 'GetPathName')) == normalized(recovery.SERVICE), 'Active model path changed unexpectedly')
        after = {path: sha(path) for path in pins}
        require(after == pins, 'Pinned file bytes changed during UI restoration')
        report.update(status='PASS_SESSION_UI_FLAGS_RESTORED_NO_NATIVE_MUTATION', input_sha256_after=after,
                      inputs_unchanged=True, observed_ui_flags_after={k: bool(getattr(objects[k], k)) for k in names},
                      active_document_dirty_after=bool(val(model, 'GetSaveFlag')))
        builder.checkpoint('interrupted_ui_restoration_completed')
    except Exception as exc:
        report.update(status='FAILED', error=str(exc), traceback=traceback.format_exc())
        recovery.persist(output, report)
        raise
    finally:
        if builder and builder.initialized:
            builder.pythoncom.CoUninitialize()


if __name__ == '__main__':
    main()
