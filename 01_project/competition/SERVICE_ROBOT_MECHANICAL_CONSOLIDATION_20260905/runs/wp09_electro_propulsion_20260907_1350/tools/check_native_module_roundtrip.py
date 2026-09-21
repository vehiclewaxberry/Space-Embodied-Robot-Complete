"""Independently match WP09 native assembly STEP material to exported source parts.

Only explicit main execution initializes OCCT. No producer or SolidWorks/COM
builder is imported. Existing receipts and existing output files are preserved.
"""
from __future__ import annotations

import argparse
from collections import Counter
import datetime as dt
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import traceback

sys.dont_write_bytecode = True
R = Path(__file__).resolve().parents[1]
EXPECTED_COUNTS = {'a3200': 22, 'mips': 6, 'battery_mount': 16}
I4 = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
SW_IDENTITY16 = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
WORLD_BASIS_MM = [[0, 0, 0], [10, 0, 0], [0, 10, 0], [0, 0, 10]]
NORMAL_PART_STATUS = 'NATIVE_PART_SAVED_CLOSED_REOPENED_VERIFIED_AND_CLOSED'
RECOVERED_PART_STATUS = 'CLEAN_SAVED_INTERRUPTED_PART_REUSED_COLD_ASSEMBLY_CHECK_REQUIRED'


def require(okay, message):
    if not okay:
        raise ValueError(message)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def key(path):
    return os.path.normcase(str(Path(path).resolve()))


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def pin(inputs, path, expected=None):
    path = str(Path(path).resolve())
    actual = digest(path)
    require(expected is None or actual == expected, 'SHA256 mismatch: ' + path)
    require(path not in inputs or inputs[path] == actual, 'Input changed: ' + path)
    inputs[path] = actual
    return path


def normalized_map(values):
    result = {}
    for path, value in values.items():
        ident = key(path)
        require(ident not in result or result[ident] == value, 'Conflicting dependency hash')
        result[ident] = value
    return result


class Audit:
    def __init__(self, output, module):
        self.output, self.module = output, module
        self.rows, self.inputs, self.context = [], {}, {}
        self.stage = 'INPUTS'
        self.started = dt.datetime.now(dt.timezone.utc).isoformat()

    def check(self, ident, okay, measurement=None, **detail):
        row = dict(id=ident, status='PASS' if okay is True else 'FAIL', detail=detail)
        if measurement is not None:
            row['measurement'] = measurement
        self.rows.append(row)

    def error(self, ident, exc):
        self.rows.append(dict(id=ident, status='FAIL', exception_type=type(exc).__name__,
                              exception_message=str(exc), traceback=traceback.format_exc()))

    def write(self, status='IN_PROGRESS', **extra):
        report = dict(schema='WP09_NATIVE_MODULE_STEP_MATERIAL_CHECK_V1', status=status,
                      module=self.module, started_utc=self.started,
                      checkpoint_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                      stage=self.stage, results=self.rows,
                      counts=dict(Counter(row['status'] for row in self.rows)),
                      input_sha256_before=self.inputs,
                      no_producer_or_native_builder_imported=True, no_com_used=True,
                      scope='Only material equivalence of the native assembly STEP export to each original emitted single-solid STEP, in unchanged declared millimetre coordinates.',
                      material_equivalence_verified=False, integrated_into_wp08=False,
                      actual_equipment_selected=False, physical_assembly_completed=False,
                      electrical_complete=False, pcb_function_verified=False,
                      thread_engagement_verified=False, strength_verified=False,
                      pressure_system_designed=False, plume_or_thrust_vector_verified=False,
                      manufacturing_release=False, mate_based_motion_model=False,
                      **self.context)
        report.update(extra)
        temporary = self.output.with_name(self.output.name + '.tmp')
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        os.replace(temporary, self.output)


def bbox_error(a, b):
    return max(abs(a[side][axis] - b[side][axis])
               for side in ('min_mm', 'max_mm') for axis in range(3))


def nested_error(actual, expected):
    require(len(actual) == len(expected) and all(len(a) == len(b) for a, b in zip(actual, expected)),
            'Malformed native measured coordinate array')
    require(all(math.isfinite(value) for row in actual for value in row), 'Nonfinite native coordinate')
    return max(abs(value - reference) for a, b in zip(actual, expected) for value, reference in zip(a, b))


def native_fact_error(facts, source, linear):
    require(facts['document_length_unit'] == 'mm' and facts['geometric_COM_length_unit'] == 'm',
            'Unrecognized native model units')
    require(facts['solid_count'] == 1 and facts['sheet_count'] == 0 and len(facts['bodies']) == 1,
            'Native part model must contain one solid and no sheets')
    require(math.isfinite(facts['volume_mm3']) and facts['volume_mm3'] > 0,
            'Native fact volume missing or nonpositive')
    reference = [source['bbox_mm']['min_mm'], source['bbox_mm']['max_mm']]
    error = max(nested_error(facts['bounds_mm'], reference),
                nested_error(facts['bodies'][0]['bounds_mm'], reference))
    require(error <= linear, 'Native fact bbox differs from original source')
    return error


def check_native_component_evidence(audit, row, component, source, linear, native_dependencies, schema):
    ident, saved = row['id'], row['native_save']
    require(key(component['path']) == key(saved['path']) and component['sha256'] == saved['sha256'],
            'Cold component path/hash differs from saved native part: ' + ident)
    pin(audit.inputs, component['path'], component['sha256'])
    require(component['fixed'] is True and component['suppression_state'] == 2
            and component['resolved_solid_count'] == 1 and component['resolved_sheet_count'] == 0,
            'Cold component is not fixed, resolved, single-solid: ' + ident)
    require(len(component['bodies_info']) == 1 and len(component['sheets_info']) == 0,
            'Cold resolved body information incomplete: ' + ident)
    require(component['transform_sw16'] == SW_IDENTITY16, 'Cold component transform is not identity: ' + ident)
    basis_error = nested_error(component['world_basis_points_mm'], WORLD_BASIS_MM)
    require(basis_error <= linear, 'Cold component basis/scale differs: ' + ident)
    bbox = native_fact_error(component['model_part_facts'], source, linear)
    audit.check('COLD_COMPONENT_CURRENT_HASH_BODY_UNITS_AND_IDENTITY:' + ident, True,
                dict(native_sha256=component['sha256'], recomputed_bbox_error_mm=bbox,
                     recomputed_basis_error_mm=basis_error, transform_sw16=component['transform_sw16'],
                     resolved_solid_count=component['resolved_solid_count'],
                     resolved_sheet_count=component['resolved_sheet_count']),
                evidence_scope='Recheck of hash-bound actual native cold-assembly observations; subsequent STEP BRep matching independently verifies material.')
    if row['status'] == NORMAL_PART_STATUS:
        require(saved['ok'] is True and saved['errors'] == 0, 'Normal part save acknowledgement not successful')
        cold = row['part_cold_reopen']
        require(cold['errors'] == 0, 'Normal native part cold reopen error')
        native_fact_error(cold['facts'], source, linear)
        require(row['external_reference_count'] == row['auxiliary_reference_count'] == 0,
                'Normal native part has external dependencies')
        return
    require(schema == 'WP09_NATIVE_BOUNDED_SESSION' and audit.module == 'a3200'
            and ident == 'A3200_BOTTOM_WASHER_2' and row['status'] == RECOVERED_PART_STATUS,
            'Unrecognized interrupted native part recovery')
    recovery_path = row['recovery_receipt']
    require(key(recovery_path) == key(R / 'results/A3200_INTERRUPTED_SESSION_EXIT.json'),
            'Unexpected recovery receipt for known interrupted part')
    require(key(recovery_path) in native_dependencies, 'Recovery receipt missing from frozen native input pins')
    recovery_path = pin(audit.inputs, recovery_path, native_dependencies[key(recovery_path)])
    recovery = read(recovery_path)
    require(recovery['status'] == 'TASK_OWNED_CLEAN_DOCUMENT_CLOSED_EMPTY_SESSION_EXIT_REQUESTED'
            and recovery['empty_document_session_verified'] is True
            and recovery['save_api_acknowledgement_recovered'] is False,
            'Recovery cleanliness/empty-session/unknown-ACK evidence incomplete')
    require(saved['ok'] is None and saved['errors'] is None and saved['warnings'] is None
            and saved['original_save_api_acknowledgement'] == 'UNKNOWN_GUARD_INTERRUPTED'
            and saved.get('api_return') is None, 'Original interrupted save acknowledgement must remain UNKNOWN')
    closed = [item for item in recovery['closed'] if key(item['path']) == key(saved['path'])]
    before = [item for item in recovery['documents_before'] if key(item['path']) == key(saved['path'])]
    require(len(closed) == len(before) == 1, 'Recovery does not uniquely identify interrupted document')
    evidence = closed[0]
    require(evidence['sha256'] == saved['sha256'] and evidence['source_sha256'] == source['sha256']
            and evidence['dirty'] is False and before[0]['dirty'] is False
            and before[0]['document_type'] == 1
            and evidence['previous_save_acknowledgement'] == 'UNKNOWN_GUARD_INTERRUPTED',
            'Recovered document/source/hash/cleanliness evidence mismatch')
    pin(audit.inputs, evidence['path'], evidence['sha256'])
    recovered_bbox = native_fact_error(evidence['facts'], source, linear)
    native_fact_error(row['facts'], source, linear)
    audit.context.setdefault('interrupted_save_acknowledgements', {})[ident] = 'UNKNOWN_GUARD_INTERRUPTED'
    audit.check('INTERRUPTED_PART_RECOVERY_BOUND_TO_CURRENT_COLD_COMPONENT:' + ident, True,
                dict(recovery_receipt=recovery_path, native_sha256=saved['sha256'],
                     recovered_bbox_error_mm=recovered_bbox, current_cold_bbox_error_mm=bbox,
                     original_save_api_acknowledgement='UNKNOWN_GUARD_INTERRUPTED',
                     original_save_api_acknowledgement_recovered=False),
                scope='Clean saved file, observed native facts and subsequent current cold component are bound; no credit for the unavailable original save API acknowledgement.')


def material_delta(g, actual, source):
    missing = g.volume(source - actual)
    extra = g.volume(actual - source)
    return dict(missing_material_mm3=missing, extra_material_mm3=extra,
                symmetric_difference_mm3=math.fsum((missing, extra)))


def free_topology(shape, solids):
    """Identify non-solid faces, wires, edges, or vertices in the imported file."""
    from OCP.TopExp import TopExp
    from OCP.TopAbs import TopAbs_FACE, TopAbs_WIRE, TopAbs_EDGE, TopAbs_VERTEX, TopAbs_SHELL
    from OCP.TopTools import TopTools_IndexedMapOfShape
    result = {}
    for name, kind in (('shell', TopAbs_SHELL), ('face', TopAbs_FACE), ('wire', TopAbs_WIRE),
                       ('edge', TopAbs_EDGE), ('vertex', TopAbs_VERTEX)):
        all_items, solid_items = TopTools_IndexedMapOfShape(), TopTools_IndexedMapOfShape()
        TopExp.MapShapes_s(shape.wrapped, kind, all_items)
        for solid in solids:
            TopExp.MapShapes_s(solid.wrapped, kind, solid_items)
        uncovered = [index for index in range(1, all_items.Extent() + 1)
                     if not solid_items.Contains(all_items.FindKey(index))]
        result[name] = dict(total=all_items.Extent(), within_solids=solid_items.Extent(),
                            uncovered_indices_one_based=uncovered)
    return result


def run(audit, emission_path, native_path, local_check_path):
    inputs, module = audit.inputs, audit.module
    count = EXPECTED_COUNTS[module]
    pin(inputs, __file__)
    ep, np, lp = [pin(inputs, path) for path in (emission_path, native_path, local_check_path)]
    emission, native, local_check = read(ep), read(np), read(lp)
    expected_schema = 'WP09_BATTERY_MOUNT_EMISSION' if module == 'battery_mount' else 'WP09_MODULE_LOCAL_EMISSION'
    require(emission['schema'] == expected_schema and emission.get('module', module) == module, 'Wrong source emission identity')
    require(native['schema'] in ('WP09_NATIVE_LOCAL', 'WP09_NATIVE_BOUNDED_SESSION')
            and native['module'] == module, 'Wrong native receipt identity')
    require(native['status'] == 'PASS_NATIVE_FIXED_LOCAL_ASSEMBLY_COLD_REOPEN_ONLY', 'Native cold-reopen receipt not PASS')
    require(native['input_files_unchanged'] is True, 'Native input preservation not verified')
    require(normalized_map(native['input_sha256_before']) == normalized_map(native['input_sha256_after']),
            'Native before/after dependency hashes differ')
    require(str(local_check.get('status', '')).startswith('PASS'), 'Independent local source check is not PASS')
    native_dependencies = normalized_map(native['input_sha256_before'])
    local_dependencies = normalized_map(local_check['input_sha256_before'])
    require(native_dependencies.get(key(ep)) == inputs[ep] and native_dependencies.get(key(lp)) == inputs[lp],
            'Native receipt is not bound to this emission and local check')
    require(local_dependencies.get(key(ep)) == inputs[ep], 'Local check is not bound to this emission')
    for receipt in (native, local_check):
        for path, value in receipt['input_sha256_before'].items():
            pin(inputs, path, value)
    cp = pin(inputs, emission['contract_path'], emission['contract_sha256'])
    contract = read(cp)
    for path, value in contract['source_inputs'].items():
        pin(inputs, path, value)
    pin(inputs, emission['producer_path'], emission['producer_sha256'])
    assembly_source = emission['assembly_step']
    pin(inputs, assembly_source['path'], assembly_source['sha256'])
    tolerance = contract['acceptance']
    require(all(math.isfinite(tolerance[x]) and tolerance[x] > 0
                for x in ('linear_mm', 'volume_mm3', 'integration_eps')), 'Invalid declared tolerance')
    require(emission['instances'] == emission['solids'] == native['component_count'] == count,
            'Declared component/solid count mismatch')
    require(len(emission['parts']) == len(native['parts']) == count, 'Source/native part membership count mismatch')
    native_parts = {row['id']: row for row in native['parts']}
    require(len(native_parts) == count and set(native_parts) == set(emission['parts']), 'Duplicate/missing native instance ID')
    frame = emission.get('frame', contract.get('frame', 'S_WORLD_MM'))
    require(native['coordinate_frame'] == frame + '_IDENTITY', 'Native coordinate frame not unchanged identity')
    cold = native['cold_assembly_inspection']
    require(native['cold_open']['errors'] == 0 and cold['component_count'] == cold['resolved_solid_total'] == count
            and cold['coordinate_frame'] == native['coordinate_frame']
            and cold['all_components_fixed_at_identity'] is True,
            'Incomplete native final cold-assembly evidence')
    cold_components = {row['id']: row for row in cold['components']}
    require(len(cold['components']) == len(cold_components) == count
            and set(cold_components) == set(emission['parts']), 'Cold component set is not exactly source membership')
    cold_dependencies = normalized_map({row['path']: row['sha256'] for row in cold['dependencies']})
    require(len(cold['dependencies']) == len(cold_dependencies) == count,
            'Duplicate/missing native cold assembly dependencies')
    parts = {}
    for ident, source in emission['parts'].items():
        row = native_parts[ident]
        require(row['status'] in (NORMAL_PART_STATUS, RECOVERED_PART_STATUS),
                'Incomplete or unrecognized native part cold reopen: ' + ident)
        require(row['expected_solids'] == 1 and key(row['source']) == key(source['path'])
                and row['source_sha256'] == source['sha256'], 'Native source identity mismatch: ' + ident)
        source_path = pin(inputs, source['path'], source['sha256'])
        saved = row['native_save']
        require(key(row['target']) == key(saved['path']), 'Native saved part is not declared target')
        pin(inputs, saved['path'], saved['sha256'])
        require(cold_dependencies.get(key(saved['path'])) == saved['sha256'],
                'Cold assembly dependency does not match native saved part')
        check_native_component_evidence(audit, row, cold_components[ident], source, tolerance['linear_mm'],
                                        native_dependencies, native['schema'])
        parts[ident] = dict(path=source_path, sha256=source['sha256'], T_S_local=I4)
    saved_assembly = native['assembly_save']
    pin(inputs, saved_assembly['path'], saved_assembly['sha256'])
    require(key(cold['assembly_path']) == key(saved_assembly['path'])
            and saved_assembly['ok'] is True and saved_assembly['errors'] == 0,
            'Final cold assembly does not identify a successfully saved native assembly')
    exported = native['roundtrip_export']
    require(exported['ok'] is True and exported['errors'] == 0, 'Roundtrip export API receipt not successful')
    require(exported['native_sha256'] == saved_assembly['sha256'], 'Roundtrip export bound to different native assembly')
    require(exported['active_document_confirmed'] is True and exported['all_selections_cleared'] is True,
            'Native full-assembly export provenance incomplete')
    roundtrip = pin(inputs, exported['path'], exported['sha256'])
    parts['__NATIVE_ROUNDTRIP__'] = dict(path=roundtrip, sha256=exported['sha256'], T_S_local=I4)
    reader_path = pin(inputs, contract['geometry_reader'])
    cadgen_root = Path('F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src/cadgen')
    require(cadgen_root.is_dir(), 'Missing installed geometry helper package')
    for helper in sorted(cadgen_root.rglob('*.py')):
        pin(inputs, helper)
    audit.context.update(emission_path=ep, native_receipt_path=np, local_check_path=lp,
                         coordinate_frame=frame, expected_solid_count=count,
                         tolerance=dict(tolerance), native_assembly_path=saved_assembly['path'],
                         roundtrip_step_path=roundtrip,
                         source_representation_roles={k: v['representation_role'] for k, v in emission['parts'].items()})
    audit.check('SOURCE_NATIVE_AND_HELPER_HASH_BINDINGS', True,
                dict(source_part_ids=sorted(emission['parts']), declared_count=count,
                     native_cold_receipt_status=native['status']))
    audit.write()
    spec = importlib.util.spec_from_file_location('wp09_native_independent_geometry', reader_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    g = helper.Geometry(dict(parts=parts, tolerances=tolerance), inputs)
    from build123d import import_step
    g.import_step = import_step
    audit.stage = 'ACTUAL_NATIVE_STEP_READBACK'
    actual = g.load('__NATIVE_ROUNDTRIP__')
    facts = g.facts(actual)
    solids = list(actual.solids())
    topology = free_topology(actual, solids)
    valid = facts['shape_valid'] and facts['solid_count'] == count and facts['volume_mm3'] > 0
    audit.check('NATIVE_STEP_VALID_EXACT_SOLID_COUNT', bool(valid), facts)
    audit.check('NATIVE_STEP_NO_EXTRA_NON_SOLID_GEOMETRY',
                all(not row['uncovered_indices_one_based'] for row in topology.values()), topology)
    require(valid, 'Invalid or wrong-count native STEP readback')
    native_facts = [g.facts(solid) for solid in solids]
    mapping = {}
    audit.stage = 'BBOX_FILTER_THEN_BIDIRECTIONAL_BREP_MATERIAL_MATCHING'
    for ident in sorted(emission['parts']):
        try:
            source = g.load(ident)
            sf = g.facts(source)
            source_topology = free_topology(source, list(source.solids()))
            source_valid = sf['shape_valid'] and sf['solid_count'] == 1 and sf['volume_mm3'] > 0
            bound_error = bbox_error(sf['bbox_mm'], emission['parts'][ident]['bbox_mm'])
            audit.check('SOURCE_STEP_SINGLE_SOLID_AND_DECLARED_BBOX:' + ident,
                        bool(source_valid and bound_error <= g.linear
                             and all(not row['uncovered_indices_one_based'] for row in source_topology.values())),
                        dict(facts=sf, declared_bbox_max_difference_mm=bound_error, topology=source_topology))
            require(source_valid, 'Invalid source single-solid STEP: ' + ident)
            candidates = [index for index, nf in enumerate(native_facts)
                          if bbox_error(sf['bbox_mm'], nf['bbox_mm']) <= g.linear]
            observations, matches = [], []
            for index in candidates:
                delta = material_delta(g, solids[index], source)
                observations.append(dict(native_solid_index_zero_based=index,
                                         bbox_max_difference_mm=bbox_error(sf['bbox_mm'], native_facts[index]['bbox_mm']),
                                         **delta))
                if native_facts[index]['shape_valid'] and delta['symmetric_difference_mm3'] <= g.volume_tol:
                    matches.append(index)
            audit.check('SOURCE_NATIVE_UNIQUE_MATERIAL_MATCH:' + ident, len(matches) == 1,
                        dict(aabb_candidates_zero_based=candidates, actual_brep_differences=observations,
                             exact_matches_zero_based=matches, bbox_rejected_count=count - len(candidates)),
                        matching_method='Every native solid is considered by absolute millimetre bbox; each candidate is tested by both directed BRep material differences, without volume-only acceptance.')
            if len(matches) == 1:
                mapping[ident] = matches[0]
        except Exception as exc:
            audit.error('SOURCE_MATCH_EXCEPTION:' + ident, exc)
        audit.write()
    used = set(mapping.values())
    audit.check('ONE_TO_ONE_BIJECTION_NO_EXTRA_OR_REUSED_NATIVE_BODY',
                len(mapping) == len(used) == count and used == set(range(count)),
                dict(source_to_native_solid_zero_based=mapping,
                     unmatched_native_indices_zero_based=sorted(set(range(count)) - used)))
    counts = Counter(row['id'].split(':')[0] for row in audit.rows)
    audit.check('ALL_SOURCE_COMPARISONS_EXECUTED',
                counts['SOURCE_STEP_SINGLE_SOLID_AND_DECLARED_BBOX'] == count
                and counts['SOURCE_NATIVE_UNIQUE_MATERIAL_MATCH'] == count
                and counts['COLD_COMPONENT_CURRENT_HASH_BODY_UNITS_AND_IDENTITY'] == count,
                dict(expected=count, actual=dict(counts)))
    audit.stage = 'COMPLETED_GEOMETRY_PENDING_FINAL_HASH_CHECK'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', nargs='?', choices=tuple(EXPECTED_COUNTS))
    parser.add_argument('--module', dest='module_kind', choices=tuple(EXPECTED_COUNTS))
    parser.add_argument('--emission', type=Path)
    parser.add_argument('--native-receipt', type=Path)
    parser.add_argument('--local-check', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    if args.kind and args.module_kind and args.kind != args.module_kind:
        parser.error('Positional module and --module disagree')
    module = args.module_kind or args.kind
    if module is None:
        parser.error('Supply module a3200, mips or battery_mount')
    ep = args.emission or R / 'results' / module / 'EMISSION.json'
    np = args.native_receipt or R / 'results' / (module + '_NATIVE.json')
    lp = args.local_check or R / 'results' / module / 'CHECK.json'
    output = (args.output or R / 'results' / (module + '_NATIVE_MATERIAL_CHECK.json')).resolve()
    require(not output.exists() and not output.with_name(output.name + '.tmp').exists(), 'Existing output protected')
    require(key(output) not in {key(ep), key(np), key(lp), key(__file__)}, 'Output would overwrite an input')
    output.parent.mkdir(parents=True, exist_ok=True)
    audit, completed = Audit(output, module), False
    audit.write()
    try:
        run(audit, ep, np, lp)
        completed = True
    except Exception as exc:
        audit.error('INCOMPLETE_EXECUTION_EXCEPTION', exc)
    after = {}
    for path in audit.inputs:
        try:
            after[path] = digest(path)
        except Exception:
            after[path] = None
    unchanged = audit.inputs == after
    audit.check('ALL_INPUTS_UNCHANGED', unchanged,
                dict(changed_paths=[p for p in audit.inputs if audit.inputs[p] != after[p]]))
    passed = completed and unchanged and bool(audit.rows) and all(row['status'] == 'PASS' for row in audit.rows)
    status = 'PASS_LOCAL_NATIVE_STEP_MATERIAL_EQUIVALENCE' if passed else 'FAIL_CLOSED_NATIVE_MODULE_MATERIAL_CHECK'
    audit.write(status, completed_all_planned_checks=completed,
                material_equivalence_verified=passed, input_sha256_after=after,
                inputs_unchanged=unchanged)
    print(json.dumps(dict(module=module, status=status, output=str(output),
                         counts=dict(Counter(row['status'] for row in audit.rows))), ensure_ascii=False), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
