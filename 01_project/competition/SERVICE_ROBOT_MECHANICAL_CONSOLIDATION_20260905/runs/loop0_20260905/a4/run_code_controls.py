"""Read WP03 receipts/code; run isolated synthetic protocol controls only. No CAD."""
from pathlib import Path
import ast
import collections
import copy
import datetime
import hashlib
import itertools
import json
import sys
import xml.etree.ElementTree as ET
from strict_surface_aggregator import aggregate, digest, require_physical_view

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
WP03 = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
WP01 = ROOT / '20_engineering/service_robot_wp01_20260905'
WP02 = ROOT / '20_engineering/service_robot_wp02_20260905'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(name, value):
    with (HERE / name).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def pair_record_summary(rows, expected, deferred):
    ids = [tuple(sorted(r['links'])) for r in rows]
    false_ids = {tuple(sorted(r['links'])) for r in rows if r.get('surface_intersection') is False}
    return {'record_count': len(rows), 'unique_pair_count': len(set(ids)),
            'missing_pairs': [list(p) for p in sorted(expected - set(ids))],
            'unexpected_pairs': [list(p) for p in sorted(set(ids) - expected)],
            'duplicate_pairs': [list(p) for p, n in collections.Counter(ids).items() if n > 1],
            'false_result_count': sum(r.get('surface_intersection') is False for r in rows),
            'true_result_pairs': [r['links'] for r in rows if r.get('surface_intersection') is True],
            'unknown_pairs': [r['links'] for r in rows if r.get('surface_intersection') is None],
            'false_pair_set_exactly_declared_body_scope': false_ids == expected - deferred,
            'method_counts': dict(collections.Counter(r.get('method', r.get('broad_phase', 'NOT_RECORDED')) for r in rows))}


def main():
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    pose_path = WP03 / 'results/POSE_SCREEN.json'
    old_path = WP01 / 'LAYOUT_COMPARISON.json'
    source = WP03 / 'pose_screen.py'
    pose = read(pose_path)
    old = read(old_path)
    params = read(WP03 / 'design_parameters.json')
    urdf = ROOT / '20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf'
    tree = ET.parse(urdf).getroot()
    links = [link.get('name') for link in tree.findall('link')]
    adjacent = {tuple(sorted((j.find('parent').get('link'), j.find('child').get('link')))) for j in tree.findall('joint')}
    expected = {tuple(sorted(p)) for p in itertools.combinations(links, 2)} - adjacent
    deferred = {('gripper_left', 'gripper_right')}
    reads = {source, pose_path, old_path, urdf, WP03 / 'design_parameters.json',
             WP03 / 'body_exploded.step.py', WP03 / 'spacecraft_model.py',
             WP03 / 'dynamics_handoff.py', WP03 / 'export_parts_and_bom.py',
             WP03 / 'README.md', WP03 / 'BOM.csv', WP03 / 'INTERFACES.csv'}
    reads.update(Path(p) for p in pose['source_hashes'])
    reads.update(Path(row['path']) for row in pose['mesh_sources'])
    before = {str(p): sha(p) for p in sorted(reads)}
    bindings = [{'path': p, 'recorded_sha256': h, 'current_sha256': before[p],
                 'currently_matches': h == before[p]} for p, h in pose['source_hashes'].items()]
    old_mesh = {r['link']: r for r in old['mesh_sources']}
    meshes = [{'link': r['link'], 'path': r['path'], 'current_sha256': before[r['path']],
               'pose_recorded_sha256': r['sha256'], 'layout_recorded_sha256': old_mesh[r['link']]['sha256'],
               'three_way_current_match': before[r['path']] == r['sha256'] == old_mesh[r['link']]['sha256']}
              for r in pose['mesh_sources']]
    history = []
    candidates = []
    for p in pose['poses']:
        check = p['self_surface_check']
        if p['id'] in ('OPEN_PARKING_REFERENCE', 'SERVICE_WORK_REFERENCE'):
            key = 'stow' if p['id'] == 'OPEN_PARKING_REFERENCE' else 'work'
            state = 'parking' if key == 'stow' else 'service'
            receipt = old['self_intersection_by_pose'][key]
            history.append({'pose_id': p['id'], 'documented_status': check['status'],
                            'embedded_receipt_matches_current_layout': check['receipt'] == receipt,
                            'old_q_matches_pose': receipt['q_deg'] == p['q_deg'],
                            'old_finger_matches_pose': receipt['finger_joint_displacement_mm'] == p['finger_mm'],
                            'current_wp03_q_matches': p['q_deg'] == params['states'][state]['q_deg'],
                            'current_wp03_finger_matches': p['finger_mm'] == params['states'][state]['finger_mm'],
                            'layout_body_flag': receipt['body_involving_pairs_surface_disjoint'],
                            'layout_all_nonadjacent_flag': receipt['all_nonadjacent_pairs_surface_disjoint'],
                            'pair_audit': pair_record_summary(receipt['pairs'], expected, deferred),
                            'evidence_type': 'READ_ONLY_RECEIPT_CONSISTENCY_NOT_GEOMETRY_REPLAY',
                            'missing_historical_protocol': ['independent run_id', 'parent/worker frozen snapshot contract', 'worker input pre/post hashes']})
        else:
            candidates.append({'pose_id': p['id'], 'documented_status': check['status'],
                               'worker_completed_recorded': check.get('worker_completed'),
                               'pair_audit': pair_record_summary(check['records'], expected, deferred)})
    code = source.read_text(encoding='utf-8-sig')
    code_lines = code.splitlines()
    fragments = []
    for i, line in enumerate(code_lines, 1):
        if any(s in line for s in ('checked==35', "p['self_surface_check']={'status':'SOURCE_REFERENCE", 'OUTPUT.write_text', "HERE/'POSE_SCREEN.md'", 'subprocess.run', 'except subprocess.TimeoutExpired', 'script_sha256', "p['id'] in completed")):
            fragments.append({'line': i, 'text': line.strip()})
    dynamics_tree = ast.parse((WP03 / 'dynamics_handoff.py').read_text(encoding='utf-8-sig'))
    process_state = next(n for n in dynamics_tree.body if isinstance(n, ast.FunctionDef) and n.name == 'process_state')
    process_state_source = ast.get_source_segment((WP03 / 'dynamics_handoff.py').read_text(encoding='utf-8-sig'), process_state)
    audit = {'evidence_type': 'STATIC_SOURCE_AND_EXISTING_RECEIPT_AUDIT_NOT_GEOMETRY_REPLAY',
             'geometry_executed': False, 'production_modules_imported': False,
             'pose_source_sha256': before[str(source)], 'pose_result_script_hash_matches_current': pose['script_sha256'] == before[str(source)],
             'source_bindings': bindings, 'mesh_hash_bindings': meshes,
             'layout_urdf_hash_matches_current': old['source_urdf_sha256'] == before[str(urdf)],
             'layout_kinematics_hash_matches_current': old['kinematics_sha256'] == before[str(WP01 / 'kinematics.py')],
             'object_set': {'accepted_links': links, 'all_unordered_pairs': len(links)*(len(links)-1)//2,
                            'whole_adjacent_pairs_excluded_by_original_worker': [list(p) for p in sorted(adjacent)],
                            'expected_nonadjacent_pairs': [list(p) for p in sorted(expected)],
                            'explicit_unknown_pair': list(next(iter(deferred))), 'body_surface_scope_pair_count': len(expected-deferred),
                            'limitations': ['Adjacency excludes whole pairs, not only allowed interface contact regions.',
                                            'These 10 accepted STL links are not the 361 spacecraft instances or 742 nominal BRep leaf instances.']},
             'historical_reference_audit': history, 'candidate_record_audit': candidates,
             'self_worker_error_recorded': pose['self_worker_error'], 'source_fragments': fragments,
             'issue_dispositions': {
                 'R08': 'CONFIRMED_ACTIVE_WP01_WP02_DEPENDENCIES_AND_LIMITED_SCOPE; current two reference q/finger values checked, no whole-WP03 inference',
                 'R09': 'CONFIRMED_UNCONDITIONAL_LABEL_SETTING; current saved historical records agree for exact 35-pair body scope, so no evidence that historical geometry result is false',
                 'R10': 'REPRODUCED_BY_SIX_SYNTHETIC_STATUS_EXPRESSION_CASES; no geometry rerun',
                 'R11': 'CONFIRMED_FIXED_OUTPUT_OVERWRITE_AND_NO_PARENT_WORKER_SNAPSHOT_PROTOCOL_IN_SOURCE; current saved error is reported separately',
                 'R15': 'CONFIRMED_DISPLAY_ONLY_SOURCE_WARNING_AND_ARTIFICIAL_OFFSETS; no observed misuse; proposed guard tested separately'},
             'exploded_consumer_review': {'entry': str(WP03 / 'body_exploded.step.py'),
                                         'generated_receipt_view': 'exploded',
                                         'receipt_written_before_display_offsets': True,
                                         'process_state_references_view_field': "['view']" in process_state_source or "get('view'" in process_state_source,
                                         'default_handoff_input_files': ['parking_instances.json','released_instances.json','service_instances.json'],
                                         'interpretation': 'Default filenames select complete receipts; process_state has no explicit view contract. Not evidence that exploded data was used.'}}
    write('SOURCE_AND_RECORD_AUDIT.json', audit)
    # Protocol controls use actual pair identities and synthetic outcomes only.
    contract = {'run_id': 'loop0_a4_synthetic_control',
                'configuration': {'pose_id': 'SYNTHETIC_SAME_PAIR_SET', 'q_deg': [0,-30,-60,40,0,0],
                                  'finger_mm': 15, 'root_translation_mm': [90,0,125.15],
                                  'root_rotation': [[1,0,0],[0,1,0],[0,0,1]]},
                'input_sha256': {p: before[p] for p in [str(source), *pose['source_hashes'],
                                                       *(r['path'] for r in pose['mesh_sources'])]},
                'expected_nonadjacent_pairs': [list(p) for p in sorted(expected)],
                'explicit_unknown_pairs': [list(p) for p in deferred]}
    snapshot = digest(contract['input_sha256'])
    rows = [{'links': list(p), 'surface_intersection': None if p in deferred else False,
             'unknown_reason': 'ACCEPTED_STL_FINGER_PAIR_DEFERRED' if p in deferred else None,
             'run_id': contract['run_id'], 'pose_id': contract['configuration']['pose_id'],
             'snapshot_digest': snapshot} for p in sorted(expected)]
    normal = {'run_id': contract['run_id'], 'configuration': copy.deepcopy(contract['configuration']),
              'input_sha256_before': copy.deepcopy(contract['input_sha256']),
              'input_sha256_after': copy.deepcopy(contract['input_sha256']),
              'worker_returncode': 0, 'worker_error': None, 'timed_out': False,
              'completion': {'completed': True, 'run_id': contract['run_id'],
                             'pose_id': contract['configuration']['pose_id'], 'snapshot_digest': snapshot,
                             'expected_pair_count': len(expected)}, 'records': rows}
    cases = []
    def test(name, mutate=None, expected_status='INCOMPLETE_OR_INVALID_EVIDENCE'):
        value = copy.deepcopy(normal)
        if mutate: mutate(value)
        result = aggregate(contract, value)
        cases.append({'case': name, 'synthetic': True, 'geometry_executed': False,
                      'expected_status': expected_status, 'observed': result,
                      'matches_expected': result['status'] == expected_status, 'input': value})
    good = 'DECLARED_NONADJACENT_BODY_PAIR_SURFACES_DISJOINT_ONLY'
    test('normal_same_35_body_pairs_plus_explicit_unknown_fingers', expected_status=good)
    test('duplicate_replaces_required_pair', lambda x: x['records'].__setitem__(1, copy.deepcopy(x['records'][0])))
    test('reversed_pair_duplicate', lambda x: x['records'].append({**x['records'][0], 'links': list(reversed(x['records'][0]['links']))}))
    test('unexpected_pair_id', lambda x: x['records'][0].__setitem__('links', ['wrong_a','wrong_b']))
    test('missing_pair', lambda x: x['records'].pop(0))
    test('completion_missing', lambda x: x.__setitem__('completion', None))
    test('worker_returncode_error', lambda x: x.__setitem__('worker_returncode', 1))
    test('worker_error_with_35_false', lambda x: x.__setitem__('worker_error', 'synthetic exception after rows'))
    test('timeout_after_35_false', lambda x: x.__setitem__('timed_out', True))
    test('old_input_hash', lambda x: x['input_sha256_before'].__setitem__(str(source), '0'*64))
    test('input_changed_after', lambda x: x['input_sha256_after'].__setitem__(str(urdf), '0'*64))
    test('wrong_configuration', lambda x: x['configuration'].__setitem__('finger_mm', 0))
    test('wrong_run_id', lambda x: x.__setitem__('run_id', 'old_run'))
    test('old_row_snapshot', lambda x: x['records'][0].__setitem__('snapshot_digest', '0'*64))
    test('boolean_zero_is_not_false', lambda x: x['records'][0].__setitem__('surface_intersection', 0))
    test('known_hit_preserved', lambda x: x['records'][0].__setitem__('surface_intersection', True), 'SCOPED_SURFACE_INTERSECTION_RECORDED')
    view_controls = []
    for view in ['complete','exploded','cutaway','ground',None]:
        try:
            observed = require_physical_view({'view': view, 'state': 'parking'}); rejected = False
        except ValueError as exc:
            observed = str(exc); rejected = True
        view_controls.append({'view': view, 'synthetic': True, 'observed': observed,
                              'expected_rejected': view != 'complete', 'matches_expected': rejected == (view != 'complete')})
    write('STRICT_AGGREGATOR_CONTROLS.json', {'evidence_type': 'ISOLATED_CODE_NEGATIVE_CONTROLS_NOT_CAD',
          'prototype_deployed': False, 'contract': contract, 'cases': cases,
          'all_16_cases_matched': all(c['matches_expected'] for c in cases),
          'display_view_guard_controls': view_controls, 'all_5_view_controls_matched': all(c['matches_expected'] for c in view_controls),
          'limits': ['Synthetic false rows are not measured surface results.', 'Prototype only preserves the original declared 35-pair surface scope.',
                     'Original records lack this new run/snapshot protocol; no retroactive successful completion is invented.']})
    after = {str(p): sha(p) for p in sorted(reads)}
    write('READ_ONLY_RUN_RECEIPT.json', {'evidence_type': 'ISOLATED_CODE_CONTROLS_AND_READ_ONLY_AUDIT',
          'started_utc': started, 'finished_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'input_sha256_before': before, 'input_sha256_after': after, 'all_audited_inputs_unchanged': before == after,
          'geometry_executed': False, 'cad_imported': False, 'numpy_imported': 'numpy' in sys.modules,
          'vtk_imported': 'vtk' in sys.modules, 'original_pose_screen_imported': 'pose_screen' in sys.modules,
          'prototype_sha256': sha(HERE / 'strict_surface_aggregator.py'), 'runner_sha256': sha(Path(__file__)),
          'original_expression_probe_result': str(HERE / 'STATUS_BRANCH_PROBE_CURRENT.json')})
    print(json.dumps({'strict_cases': len(cases), 'strict_matched': sum(c['matches_expected'] for c in cases),
                      'view_cases': len(view_controls), 'view_matched': sum(c['matches_expected'] for c in view_controls),
                      'historical_records_audited': len(history), 'candidate_records_audited': len(candidates),
                      'inputs_unchanged': before == after, 'geometry_executed': False}))


if __name__ == '__main__':
    main()
