"""Show final SERVICE only after all three native states pass independent checks.

This read-only reopen checks actual current IDs/paths/transforms/fixed state and
dependencies. Complete body counts and actual COM four-point vectors come from
the SHA-bound preceding cold measurements; they are not falsely remeasured here.
No full STEP is required, read, or credited. Run under the existing run_guard.py.
"""
from pathlib import Path
import gc
import math
import sys
import traceback

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_native_delivery as independent
import resume_service as recovery
from integrate_native import Integrator, R, require, sha, normalized, val, t16


def main():
    output = R/'results/FINAL_REOPEN_SERVICE_V2.json'
    require(not output.exists(), 'Existing final-reopen receipt is protected')
    manifest_path = R/'results/INTEGRATION_MANIFEST.json'
    check_path = R/'results/NATIVE_DELIVERY_CHECK_ALL.json'
    manifest = recovery.read_json(manifest_path)
    manifest_sha = sha(manifest_path)
    checked = recovery.read_json(check_path)
    require(checked.get('status') == independent.PASS and checked.get('inputs_unchanged') is True,
            'All three native states must complete the independent check before final display')
    require(checked.get('manifest_sha256') == manifest_sha and set(checked.get('states', {})) == set(independent.STATES),
            'Independent check manifest or three-state coverage differs')
    require(checked.get('input_sha256_before') == checked.get('input_sha256_after'),
            'Independent check has incomplete source hash evidence')
    pins = dict(checked['input_sha256_after'])
    for source in (Path(__file__).resolve(), Path(independent.__file__).resolve(), Path(recovery.__file__).resolve(), check_path):
        pins[str(source)] = sha(source)
    allowed, receipts = recovery.registered_inputs(manifest, manifest_sha, include_service_recovery=True)
    require(len(allowed) == 463, 'Expected three saved native states plus 460 unique dependencies')
    pins.update(receipts)
    for state in independent.STATES:
        prior_path = independent.preferred_receipt(state)
        require(str(prior_path) == checked['states'][state]['receipt_path'] and
                sha(prior_path) == checked['states'][state]['receipt_sha256'],
                'Final display receipt changed since independent check: '+state)
        require(checked['states'][state]['status'] == 'PASS_SCOPED_NATIVE_EVIDENCE',
                'A native state lacks independent scoped acceptance')
    source = independent.preferred_receipt('service')
    previous = recovery.read_json(source)
    path = R/'native/WP07_ROBOT_SERVICE.SLDASM'
    digest = previous['final_native_sha256']
    require(previous.get('cold_inspection_native_sha256') == digest and sha(path) == digest,
            'Final SERVICE bytes are not the fully cold-inspected bytes')
    prior_cold = previous['cold_inspection']
    old_rows = {row['id']: row for row in prior_cold['components']}
    expected = {row['id']: row for row in manifest['states']['service']['instances']}
    require(len(old_rows) == len(expected) == 597 and set(old_rows) == set(expected), 'Prior cold coverage differs')
    for native, native_sha in allowed.items():
        pins[native] = native_sha
    for file, digest_pin in pins.items():
        require(sha(file) == digest_pin, 'Pinned evidence or native input changed before final reopen: '+file)
    report = dict(schema='WP07_FINAL_NATIVE_REOPEN_V2', state='service', status='RUNNING', progress=[],
                  manifest_sha256=manifest_sha, native_path=str(path), final_native_sha256=digest,
                  prior_receipt=dict(path=str(source), sha256=sha(source)),
                  independent_three_state_check=dict(path=str(check_path), sha256=sha(check_path)),
                  prior_full_cold_native_sha256=previous['cold_inspection_native_sha256'],
                  prior_full_cold_body_count=978, current_body_count_remeasured=False,
                  current_COM_basis_points_remeasured=False, prior_actual_COM_vectors_independently_verified=True,
                  input_sha256_before=pins, registered_three_state_dependency_count=460,
                  scope='CURRENT_READONLY_NATIVE_ID_PATH_SHA_MATRIX_FIXED_DISPLAY_DEPENDENCIES; '
                        'BODY_AND_COM_POINT_EVIDENCE_FROM_PRECEDING_COMPLETE_COLD_ON_THE_SAME_NATIVE_BYTES',
                  full_native_STEP_verified=False, global_material_equivalence_verified=False,
                  physical_assembly_completed=False, manufacturing_release=False)
    builder = None
    try:
        recovery.require_outer_guard(report)
        recovery.persist(output, report)
        builder = Integrator(output, report)
        require(int(val(builder.sw, 'GetProcessID')) == 26208, 'Unexpected existing SolidWorks PID')
        builder.close_registered(allowed)
        gc.collect()
        model, report['cold_open'] = recovery.open_readonly(builder, path)
        assembly = builder.wrap(model, 'IAssemblyDoc')
        report['initial_unload_api_return'] = assembly.LightweightAllResolved()
        raw = assembly.GetComponents(True) or []
        require(len(raw) == 597, 'Final file instance count differs')
        observed, seen, cache = [], set(), {}
        report['components'] = observed
        for item in raw:
            builder.ram_floor()
            component = builder.wrap(item, 'IComponent2')
            identity = component.ComponentReference
            require(identity in expected and identity not in seen, 'Unknown or duplicate final instance')
            row, prior = expected[identity], old_rows[identity]
            native = Path(val(component, 'GetPathName')).resolve()
            key = normalized(native)
            require(key == normalized(row['native_path']) == normalized(prior['path']), 'Final native dependency path differs')
            if key not in cache:
                cache[key] = sha(native)
            require(cache[key] == row['native_sha256'] == prior['sha256'], 'Final native dependency hash differs')
            transform = builder.wrap(component.Transform2, 'IMathTransform')
            matrix = list(transform.ArrayData)
            transform = None
            require(len(matrix) == 16 and all(math.isfinite(v) for v in matrix), 'Invalid final transform')
            expected_error = max(abs(a-b) for a, b in zip(matrix, t16(row['T_S_local'])))
            prior_error = max(abs(a-b) for a, b in zip(matrix, prior['transform_sw16']))
            require(expected_error < 1e-8 and prior_error < 1e-8 and component.IsFixed(), 'Final fixed pose differs')
            suppression = component.GetSuppression2()
            require(suppression in (1, 2, 4), 'Final component is suppressed/unresolved')
            visible = component.Visible
            require(visible == prior['visible'], 'Final saved display state differs')
            require(prior['solid_count'] == row['expected_solids'] and prior['sheet_count'] == 0,
                    'Prior measured bodies do not bind to current native dependency')
            # Current transform is independently reconstructed at all four points;
            # actual COM vectors are retained from the complete prior cold pass.
            basis = [[sum(matrix[3*j+i]*p[j]*matrix[12] for j in range(3))+matrix[9+i]*1000
                      for i in range(3)] for p in independent.core.BASIS]
            basis_error = max(abs(basis[k][i]-prior['world_basis_points_mm'][k][i])
                              for k in range(4) for i in range(3))
            require(basis_error <= 1e-5, 'Current matrix disagrees with prior actual COM four-point evidence')
            observed.append(dict(id=identity, path=str(native), sha256=cache[key], transform_sw16=matrix,
                expected_transform_max_error=expected_error, prior_transform_max_error=prior_error, fixed=True,
                suppression_state=suppression, visible=visible, prior_full_cold_solid_count=prior['solid_count'],
                current_matrix_derived_basis_mm=basis, prior_actual_COM_basis_error_mm=basis_error,
                body_count_evidence='PRIOR_COMPLETE_COLD_SAME_NATIVE_PATH_AND_SHA_NOT_REMEASURED'))
            seen.add(identity)
            component = None
            if len(seen) % 100 == 0:
                builder.checkpoint('final_display_metadata_checkpoint', inspected=len(seen))
        require(seen == set(expected), 'Final instance coverage differs')
        deps = model.GetDependencies2(False, True, False) or []
        require(len(deps) % 2 == 0, 'Malformed final dependency array')
        paths = [Path(deps[i+1]).resolve() for i in range(0, len(deps), 2)]
        require({normalized(p) for p in paths} == {normalized(r['native_path']) for r in expected.values()},
                'Final dependency set differs')
        require(len({normalized(p) for p in paths}) == 445, 'Final unique dependency count differs')
        model.ShowNamedView2('', 7)
        model.ViewZoomtofit2()
        model.GraphicsRedraw2()
        bmp = R/'results/WP07_SERVICE_FINAL.bmp'
        report['screenshot'] = dict(path=str(bmp), saved=bool(model.SaveBMP(str(bmp), 1600, 1200)))
        require(sha(path) == digest, 'Read-only final display changed native bytes')
        after = {p: sha(p) for p in pins}
        require(after == pins, 'Pinned native/evidence bytes changed during final reopen')
        report.update(status='PASS_FINAL_NATIVE_SERVICE_DISPLAY_AFTER_THREE_STATE_ACCEPTANCE', component_count=597,
                      unique_dependencies=445, dependencies=[dict(path=str(p), sha256=cache[normalized(p)]) for p in paths],
                      input_sha256_after=after, inputs_unchanged=True, native_file_unchanged=True,
                      left_open_read_only=True, left_open_dirty_flag=bool(val(model, 'GetSaveFlag')),
                      no_native_save_performed=True)
        builder.checkpoint('final_saved_service_display_ready_without_saving', component_count=597,
                           final_native_sha256=digest)
    except Exception as exc:
        report.update(status='FAILED', error=str(exc), traceback=traceback.format_exc())
        recovery.persist(output, report)
        raise
    finally:
        if builder and builder.initialized:
            builder.pythoncom.CoUninitialize()


if __name__ == '__main__':
    main()
