"""Recover saved WP07 SERVICE without repeating its assembly construction.

Default --stage cold resolves ONE component, measures it, drops all body/document
wrappers, then returns that component to lightweight. Checkpoints contain all
completed observations every 25 components. The original interrupted receipt is
immutable. --stage export is a separate, resource-gated operation on a disposable
run-owned copy; it never saves the delivery SLDASM. Run under R7/run_guard.py.
"""
from pathlib import Path
import argparse
import gc
import json
import math
import os
import shutil
import sys
import traceback

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import integrate_native as base
from integrate_native import R, require, sha, normalized, val, t16

SERVICE = R/'native/WP07_ROBOT_SERVICE.SLDASM'
RECOVERY = R/'results/NATIVE_SERVICE_RECOVERY.json'
SAVED_SHA = '29e38402e66dfd706bcf555c35762d768ca2e9006d8c0e329a0ca1c7e8a9f785'
BASIS_MM = [[0., 0., 0.], [10., 0., 0.], [0., 10., 0.], [0., 0., 10.]]


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def persist(path, report):
    tmp = path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    os.replace(tmp, path)


def registered_inputs(manifest, manifest_sha, include_service_recovery=True):
    """Allow only pinned dependencies and independently completed run assemblies."""
    allowed = {}
    receipt_pins = {}
    for info in manifest['states'].values():
        for row in info['instances']:
            key = normalized(row['native_path'])
            require(key not in allowed or allowed[key] == row['native_sha256'], 'Conflicting native pins')
            allowed[key] = row['native_sha256']
    require(len(allowed) == 460, 'Expected union of 460 registered native dependencies')
    for state in ('service', 'parking', 'released'):
        assembly = R/'native'/('WP07_ROBOT_'+state.upper()+'.SLDASM')
        if not assembly.exists():
            continue
        standard = R/'results'/('NATIVE_'+state.upper()+'.json')
        receipt = RECOVERY if state == 'service' and include_service_recovery and RECOVERY.exists() else standard
        if state == 'service' and not include_service_recovery:
            allowed[normalized(assembly)] = SAVED_SHA
            continue
        require(receipt.exists(), 'Unregistered assembly has no receipt: '+str(assembly))
        evidence = read_json(receipt)
        require(evidence.get('status', '').startswith('PASS_'), 'Registered assembly has incomplete receipt: '+str(receipt))
        require(evidence.get('manifest_sha256') == manifest_sha, 'Assembly receipt belongs to another manifest')
        cold = evidence.get('cold_inspection', {})
        require(cold.get('component_count') == 597 and cold.get('solid_count') == 978,
                'Completed receipt has no full native component/body inspection')
        digest = evidence['final_native_sha256']
        require(evidence.get('cold_inspection_native_sha256') == digest, 'Cold inspection is not bound to final bytes')
        allowed[normalized(assembly)] = digest
        receipt_pins[str(receipt)] = sha(receipt)
    return allowed, receipt_pins


def controlled_recovery(manifest_sha):
    guard_path = R/'logs/native_service.run.json'
    previous_path = R/'results/NATIVE_SERVICE.json'
    guard, previous = read_json(guard_path), read_json(previous_path)
    require(guard.get('status') == 'AVAILABLE_MEMORY_GUARD', 'This recovery requires the recorded memory guard')
    require(normalized(guard['cwd']) == normalized(R), 'Guard belongs to another run')
    require('tools/integrate_native.py' in guard['command'] and guard['command'][-1] == 'service',
            'Guard does not identify the interrupted SERVICE worker')
    require(previous.get('state') == 'service' and previous.get('manifest_sha256') == manifest_sha,
            'Interrupted receipt provenance mismatch')
    saved = previous.get('native_save', {})
    require(saved.get('ok') is True and saved.get('errors') == 0 and saved.get('sha256') == SAVED_SHA,
            'Prior receipt does not prove successful native save')
    require(normalized(saved['path']) == normalized(SERVICE) and sha(SERVICE) == SAVED_SHA,
            'Saved SERVICE native bytes changed')
    warm = previous.get('warm_inspection', {})
    require(warm.get('component_count') == 597 and warm.get('solid_count') == 978 and
            len(warm.get('components', [])) == 597, 'Prior warm inspection is incomplete')
    return dict(guard_path=str(guard_path), guard_sha256=sha(guard_path), guard_status=guard['status'],
                guard_elapsed_s=guard.get('elapsed_s'), interrupted_receipt_path=str(previous_path),
                interrupted_receipt_sha256=sha(previous_path), saved_native_path=str(SERVICE),
                saved_native_sha256=SAVED_SHA, previous_warm_components=597, previous_warm_solids=978,
                previous_partial_cold_credit=0,
                scope='PRIOR_PROGRESS_TO_500_IS_NOT_PERSISTED_BODY_EVIDENCE; NEW_FULL_COLD_REQUIRED'), {
                    str(guard_path): sha(guard_path), str(previous_path): sha(previous_path)}


class ComponentwiseIntegrator(base.Integrator):
    """Reusable inspector; no bulk resolution is performed in this class."""
    def memory_snapshot(self):
        return dict(available_mib=self.psutil.virtual_memory().available/1024**2,
                    python_rss_mib=self.psutil.Process().memory_info().rss/1024**2,
                    solidworks_rss_mib=self.psutil.Process(int(val(self.sw, 'GetProcessID'))).memory_info().rss/1024**2)

    def _measure_resolved(self, component, row, digest):
        # All model/body/point wrappers are confined to this frame. Its finally
        # releases them BEFORE the caller requests lightweight state.
        transform = point = mapped = document = part = bodies = sheets = utility = None
        try:
            transform = self.wrap(component.Transform2, 'IMathTransform')
            values = list(transform.ArrayData)
            require(len(values) == 16 and all(math.isfinite(v) for v in values), 'Invalid actual transform')
            error = max(abs(a-b) for a, b in zip(values, t16(row['T_S_local'])))
            fixed = bool(component.IsFixed())
            require(error < 1e-8 and fixed, 'Actual fixed transform mismatch: '+row['id'])
            utility = self.wrap(self.sw.GetMathUtility(), 'IMathUtility')
            actual_points, basis_error = [], 0.
            for p in BASIS_MM:
                point = self.wrap(utility.CreatePoint(self.VARIANT(
                    self.pythoncom.VT_ARRAY | self.pythoncom.VT_R8, [x/1000 for x in p])), 'IMathPoint')
                mapped = self.wrap(point.MultiplyTransform(transform), 'IMathPoint')
                q = [x*1000 for x in list(mapped.ArrayData)]
                require(len(q) == 3 and all(math.isfinite(v) for v in q), 'Invalid actual COM point')
                T = row['T_S_local']
                wanted = [sum(T[i][j]*p[j] for j in range(3))+T[i][3] for i in range(3)]
                basis_error = max(basis_error, max(abs(q[i]-wanted[i]) for i in range(3)))
                actual_points.append(q)
                point = mapped = None
            require(basis_error <= 1e-5, 'Actual COM four-point mismatch: '+row['id'])
            document = self.wrap(component.GetModelDoc2(), 'IModelDoc2')
            require(document is not None, 'Resolved component has no actual part document')
            require(normalized(val(document, 'GetPathName')) == normalized(row['native_path']),
                    'Actual part document path mismatch')
            part = self.wrap(document, 'IPartDoc')
            bodies = part.GetBodies2(0, False) or []
            sheets = part.GetBodies2(1, False) or []
            require(len(bodies) == row['expected_solids'] and not sheets, 'Actual body count mismatch: '+row['id'])
            return dict(id=row['id'], path=str(Path(row['native_path']).resolve()), sha256=digest,
                        transform_sw16=values, transform_max_error=error, basis_points_local_mm=BASIS_MM,
                        world_basis_points_mm=actual_points, world_basis_error_mm=basis_error,
                        solid_count=len(bodies), sheet_count=len(sheets), fixed=fixed, visible=component.Visible)
        finally:
            bodies = sheets = part = document = mapped = point = transform = utility = None

    def inspect(self, model, rows, expected_path):
        require(normalized(val(model, 'GetPathName')) == normalized(expected_path), 'Cold document saved path mismatch')
        assembly = self.wrap(model, 'IAssemblyDoc')
        model.ClearSelection2(True)
        # Unload rather than resolve. Each subsequent SetSuppression2(2) is scoped
        # to ONE component; no ResolveAllLightweight is used here.
        unload_result = assembly.LightweightAllResolved()
        raw = assembly.GetComponents(True) or []
        lookup = {r['id']: r for r in rows}
        require(len(raw) == len(rows) == len(lookup) == 597, 'Cold instance count mismatch')
        result = dict(status='RUNNING_COMPONENTWISE_COLD', component_count=0, solid_count=0, components=[],
                      expected_component_count=597, expected_solid_count=978, assembly_path=str(expected_path),
                      initial_unload_api_return=unload_result, bulk_resolution_used=False,
                      component_resolution_mode='RESOLVE_ONE_MEASURE_RELEASE_WRAPPERS_LIGHTWEIGHT_ONE',
                      scope='ACTUAL_NATIVE_FIXED_POSE_IDS_PATHS_HASHES_BODY_COUNTS_COM_FOUR_POINTS; INHERITED_B601_HOLDS_RETAINED')
        self.report['cold_inspection'] = result
        self.checkpoint('componentwise_cold_started', memory=self.memory_snapshot())
        seen, hashes = set(), {}
        try:
            for item in raw:
                self.ram_floor()
                component = self.wrap(item, 'IComponent2')
                identity = component.ComponentReference
                require(identity in lookup and identity not in seen, 'Unexpected or duplicate actual component: '+str(identity))
                row = lookup[identity]
                path = normalized(val(component, 'GetPathName'))
                require(path == normalized(row['native_path']), 'Actual native dependency path mismatch: '+identity)
                if path not in hashes:
                    hashes[path] = sha(path)
                require(hashes[path] == row['native_sha256'], 'Actual native dependency hash mismatch: '+identity)
                self.report['active_component'] = identity
                observation = None
                try:
                    resolve_return = component.SetSuppression2(2)
                    require(component.GetSuppression2() == 2, 'Single-component resolution failed: '+identity)
                    observation = self._measure_resolved(component, row, hashes[path])
                    observation['resolve_api_return'] = resolve_return
                finally:
                    # _measure_resolved released all references to the part/body.
                    gc.collect()
                    light_return = component.SetSuppression2(1)
                    light_state = component.GetSuppression2()
                    self.report['last_lightweight_transition'] = dict(id=identity, api_return=light_return, actual_state=light_state)
                    require(light_state in (1, 4), 'Component did not return to lightweight: '+identity)
                    if observation is not None:
                        observation.update(lightweight_api_return=light_return, final_suppression_state=light_state)
                seen.add(identity)
                result['components'].append(observation)
                result['component_count'] = len(seen)
                result['solid_count'] += observation['solid_count']
                component = None
                if len(seen) % 25 == 0:
                    self.checkpoint('componentwise_cold_checkpoint', inspected=len(seen), total=597,
                                    memory=self.memory_snapshot())
            require(seen == set(lookup) and result['solid_count'] == 978, 'Cold coverage or body sum differs')
            deps = model.GetDependencies2(False, True, False) or []
            require(len(deps) % 2 == 0, 'Malformed native dependency return')
            paths = [deps[i+1] for i in range(0, len(deps), 2)]
            wanted = {normalized(r['native_path']) for r in rows}
            require({normalized(p) for p in paths} == wanted and len(wanted) == 445, 'Native dependency set mismatch')
            result.update(status='PASS_COMPONENTWISE_COLD', unique_dependencies=len(wanted),
                          dependency_paths=paths, completed_all_components=True)
            self.report.pop('active_component', None)
            self.checkpoint('componentwise_cold_completed', inspected=597, solids=978, memory=self.memory_snapshot())
            return result
        except Exception:
            result['status'] = 'FAILED_COMPONENTWISE_COLD_PARTIAL_ONLY'
            self.checkpoint('componentwise_cold_failed', completed=result['component_count'])
            raise


def open_readonly(builder, path):
    opened = builder.sw.OpenDoc6(str(path), 2, 195, '', 0, 0)
    require(isinstance(opened, tuple) and len(opened) == 3 and opened[0] is not None and opened[1] == 0,
            'Read-only lightweight native reopen failed')
    model = builder.wrap(opened[0], 'IModelDoc2')
    builder.activate(model, path)
    return model, dict(errors=opened[1], warnings=opened[2], options=195, readonly_requested=True,
                       after_last_native_save=True, native_sha256=sha(path))


def require_outer_guard(report):
    import psutil
    matches = []
    for process in psutil.Process().parents():
        try:
            command = process.cmdline()
        except psutil.Error:
            continue
        if any(Path(x).name.casefold() == 'run_guard.py' for x in command):
            matches.append(dict(pid=process.pid, command=command))
    require(matches, 'Run this worker under the existing R7/run_guard.py memory guard')
    report['outer_guard_processes'] = matches
    report['guard_scope'] = 'GUARD_MONITORS_AVAILABLE_RAM_AND_OWN_PYTHON_TREE; EXISTING_SOLIDWORKS_IS_NOT_IN_THE_CHILD_JOB'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=('cold', 'export'), default='cold')
    args = parser.parse_args()
    mfpath = R/'results/INTEGRATION_MANIFEST.json'
    mf, mfsha = read_json(mfpath), sha(mfpath)
    output = RECOVERY if args.stage == 'cold' else R/'results/NATIVE_SERVICE_STEP_RECOVERY.json'
    require(not output.exists(), 'Existing recovery receipt is protected: '+str(output))
    report = dict(status='RUNNING', state='service', stage=args.stage, manifest_sha256=mfsha,
                  progress=[], save_attempts=[], implementation=dict(path=str(Path(__file__).resolve()), sha256=sha(__file__)))
    builder = None
    try:
        proof, pins = controlled_recovery(mfsha)
        report['controlled_recovery'] = proof
        pins.update({str(mfpath): mfsha, str(Path(__file__).resolve()): sha(__file__), str(Path(base.__file__)): sha(base.__file__)})
        allowed, receipt_pins = registered_inputs(mf, mfsha, include_service_recovery=args.stage == 'export')
        pins.update(receipt_pins)
        for path, digest in {**allowed, **pins}.items():
            require(sha(path) == digest, 'Recovery input pin changed: '+path)
        report['input_pins'] = {**allowed, **pins}
        require_outer_guard(report)
        persist(output, report)
        if args.stage == 'export':
            # Full resolution is a separate resource decision, never a native
            # delivery prerequisite. 3072 MiB is this attempt's declared policy.
            import psutil
            free = psutil.virtual_memory().available/1024**2
            report['export_resource_preflight'] = dict(available_mib=free, required_available_mib=3072)
            if free < 3072:
                report.update(status='RESOURCE_BLOCKED_FULL_NATIVE_STEP_EXPORT', full_native_step_verified=False,
                              explanation='Whole native STEP was not attempted; component STEP files and native cold evidence remain distinct.')
                persist(output, report)
                return
        builder = ComponentwiseIntegrator(output, report)
        require(int(val(builder.sw, 'GetProcessID')) == 26208, 'Unexpected existing SolidWorks PID')
        builder.close_registered(allowed)
        gc.collect()
        builder.sw.Visible = True
        builder.sw.UserControl = True
        if args.stage == 'cold':
            model, report['cold_open'] = open_readonly(builder, SERVICE)
            report['cold_inspection'] = builder.inspect(model, mf['states']['service']['instances'], SERVICE)
            report['cold_inspection_native_sha256'] = SAVED_SHA
            report['final_native_sha256'] = SAVED_SHA
            report['full_step_export_status'] = 'NOT_ATTEMPTED_SEPARATE_RESOURCE_STAGE'
            report['full_native_step_verified'] = False
            report['source_full_step_is_not_native_roundtrip'] = True
            model.ShowNamedView2('', 7)
            model.ViewZoomtofit2()
            model.GraphicsRedraw2()
            image = R/'results/WP07_SERVICE_RECOVERY.bmp'
            report['screenshot'] = dict(path=str(image), saved=bool(model.SaveBMP(str(image), 1600, 1200)))
            report['left_open_dirty_flag'] = bool(val(model, 'GetSaveFlag'))
            report['no_native_save_performed'] = True
            report['status'] = 'PASS_NATIVE_SERVICE_COMPONENTWISE_COLD__FULL_STEP_NOT_VERIFIED'
        else:
            export_on_work_copy(builder, report, mf)
        report['inputs_unchanged'] = all(sha(path) == digest for path, digest in {**allowed, **pins}.items())
        require(report['inputs_unchanged'] and sha(SERVICE) == SAVED_SHA, 'Recovery altered pinned input bytes')
        builder.checkpoint('recovery_completed', stage_scope=args.stage)
    except Exception as exc:
        report.update(status='FAILED', error=str(exc), traceback=traceback.format_exc())
        persist(output, report)
        raise
    finally:
        if builder and builder.initialized:
            builder.pythoncom.CoUninitialize()


def export_on_work_copy(builder, report, manifest):
    work = R/'native/work/WP07_SERVICE_EXPORT_WORK.SLDASM'
    step = R/'native/WP07_ROBOT_SERVICE.step'
    require(not work.exists() and not step.exists(), 'Existing export output is protected')
    builder.ram_floor()
    shutil.copy2(SERVICE, work)
    report['export_work_copy'] = dict(path=str(work), source_sha256=SAVED_SHA)
    opened = builder.sw.OpenDoc6(str(work), 2, 193, '', 0, 0)
    require(isinstance(opened, tuple) and opened[0] is not None and opened[1] == 0, 'Export work copy open failed')
    model = builder.wrap(opened[0], 'IModelDoc2')
    builder.activate(model, work)
    assembly = builder.wrap(model, 'IAssemblyDoc')
    builder.ram_floor()
    report['full_resolution_stage_started'] = True
    builder.checkpoint('separate_native_step_full_resolution_started', memory=builder.memory_snapshot())
    result = assembly.ResolveAllLightweight()
    visibility = []
    try:
        raw = assembly.GetComponents(True) or []
        expected = {r['id'] for r in manifest['states']['service']['instances']}
        seen = set()
        for item in raw:
            component = builder.wrap(item, 'IComponent2')
            require(component.GetSuppression2() == 2, 'Full STEP export contains unresolved component')
            identity = component.ComponentReference
            require(identity in expected and identity not in seen, 'Full STEP identity mismatch')
            seen.add(identity)
            visibility.append((component, component.Visible))
            component.Visible = 1
        require(seen == expected and len(seen) == 597, 'Incomplete full native STEP export scope')
        model.ClearSelection2(True)
        builder.ram_floor()
        report['step_export'] = builder.save_new(model, step)
        report['step_export'].update(representation='ACTUAL_NATIVE_ROUNDTRIP', all_components_intended=True,
                                    component_count=597, functional_envelopes_intended=37,
                                    full_resolution_api_return=result, actual_readback='PENDING_INDEPENDENT_GEOMETRY_CHECK')
    finally:
        for component, previous in visibility:
            component.Visible = previous
    require(normalized(val(model, 'GetPathName')) == normalized(work), 'Export changed native work document path')
    if val(model, 'GetSaveFlag'):
        saved = model.Save3(1, 0, 0)
        require(isinstance(saved, tuple) and saved[0] and saved[1] == 0, 'Cannot persist restored work-copy display')
        report['work_copy_restored_save'] = dict(api_return=list(saved), sha256=sha(work))
    builder.close_own_saved(model, work, sha(work))
    visibility = raw = component = assembly = model = None
    gc.collect()
    model, report['delivery_final_reopen'] = open_readonly(builder, SERVICE)
    # Repeat the memory-bounded complete inspection on unchanged delivery bytes.
    report['cold_inspection'] = builder.inspect(model, manifest['states']['service']['instances'], SERVICE)
    report.update(final_native_sha256=SAVED_SHA, cold_inspection_native_sha256=SAVED_SHA,
                  status='NATIVE_STEP_EXPORTED_PENDING_INDEPENDENT_READBACK', full_native_step_verified=False,
                  no_delivery_native_save_performed=True)


if __name__ == '__main__':
    main()
