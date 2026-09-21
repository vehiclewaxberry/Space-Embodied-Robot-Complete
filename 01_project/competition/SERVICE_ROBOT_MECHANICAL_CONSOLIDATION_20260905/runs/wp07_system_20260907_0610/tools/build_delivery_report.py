"""Build a Chinese WP07 factual delivery snapshot from existing run artifacts.

No CAD/COM, geometry generation, engineering Gate or external mutation. Default
outputs: R7/README.md and R7/results/DELIVERY_STATUS.json. --preview prints a short
summary without writing either. --replace-owned may replace only this generator's
own earlier report pair; all source receipts remain immutable.
"""
from pathlib import Path
import argparse
import collections
import datetime as dt
import hashlib
import json
import os
from urllib.parse import quote, urlparse, parse_qs, unquote

R = Path(__file__).resolve().parents[1]
SCHEMA = 'WP07_DELIVERY_FACTS_V1'
MARKER = '<!-- generated-by: tools/build_delivery_report.py; WP07_DELIVERY_FACTS_V1 -->'
STATES = ('service', 'parking', 'released')


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def norm(path):
    return str(Path(path).resolve()).replace('\\', '/').casefold()


def relative(path):
    path = Path(path).resolve()
    try:
        return path.relative_to(R).as_posix()
    except ValueError:
        return path.as_posix()


def link(label, path):
    return '['+str(label).replace('[', '(').replace(']', ')')+'](<'+Path(path).resolve().as_posix()+'>)'


def viewer_url(path):
    path = Path(path).resolve()
    return 'http://127.0.0.1:3245/'+quote(path.parent.as_posix(), safe='/:')+'?file='+quote(path.name, safe='')


def viewer_url_matches(url, path):
    parsed = urlparse(url or '')
    path = Path(path).resolve()
    return (parsed.scheme == 'http' and parsed.netloc == '127.0.0.1:3245' and
            norm(unquote(parsed.path).lstrip('/')) == norm(path.parent) and
            parse_qs(parsed.query).get('file') == [path.name])


class Snapshot:
    def __init__(self):
        self.pins, self.cache, self.unreadable = {}, {}, []

    def file(self, path, expected=None):
        path = Path(path).resolve()
        result = dict(path=str(path), exists=path.is_file())
        if not result['exists']:
            result['expected_sha256'] = expected
            return result
        key = norm(path)
        if key not in self.cache:
            self.cache[key] = sha(path)
        digest = self.cache[key]
        self.pins[str(path)] = digest
        result.update(sha256=digest, bytes=path.stat().st_size)
        if expected is not None:
            result.update(expected_sha256=expected, expected_hash_matches=digest == expected)
        return result

    def json(self, path, required=False):
        path = Path(path).resolve()
        if not path.is_file():
            require(not required, 'Required receipt absent: '+str(path))
            return None, dict(path=str(path), exists=False, status='NOT_PRESENT')
        info = self.file(path)
        try:
            data = json.loads(path.read_text(encoding='utf-8-sig'))
            require(isinstance(data, dict), 'Expected top-level JSON object')
        except Exception as exc:
            info.update(status='UNREADABLE_RECEIPT', error=str(exc))
            self.unreadable.append(info)
            require(not required, 'Required receipt unreadable: '+str(path))
            return None, info
        info['status'] = data.get('status', 'STATUS_NOT_DECLARED')
        return data, info

    def check_unchanged(self):
        changed = [path for path, digest in self.pins.items() if not Path(path).is_file() or sha(path) != digest]
        require(not changed, 'Inputs changed during report snapshot; rerun after workers finish: '+repr(changed))


def brief(data):
    keys = ('schema', 'status', 'scope', 'scope_status', 'station_index', 'mode', 'state',
            'counts', 'component_count', 'instance_count', 'solid_count', 'part_count',
            'board_count', 'module_count', 'open_module_count', 'ready', 'contract_consistency_pass',
            'electrical_completion_pass', 'hardware_energization_allowed', 'fit_screen_pair_count',
            'fit_screen_orientation_count', 'fit_screen_independent_arithmetic_pass',
            'physical_assembly_completed', 'structural_strength_verified', 'actual_thread_verified',
            'manufacturing_release', 'source_files_unchanged', 'source_hashes_unchanged', 'inputs_unchanged',
            'failed_bounds_count', 'arm_count', 'mesh_bbox_tolerance_mm', 'exact_brep_equivalence_claimed',
            'unchanged_nonarm_count', 'arm_instance_count', 'arm_body_count', 'collision_verified',
            'candidate_instances', 'context_instances', 'engineering_status',
            'expected_board_count', 'actual_solid_count', 'board_check_count',
            'edge_cuts_record_count', 'modeled_drill_count', 'unmodeled_drill_count',
            'pair_count', 'separated_pair_count', 'needs_brep_count', 'minimum_distance_lower_bound_mm',
            'selected_station', 'station_presence', 'input_files_unchanged', 'session_preferences_restored',
            'complete_mass_budget', 'allocated_mass_known_instances', 'allocated_mass_unknown_instances',
            'allocated_mass_partial_sum_kg', 'purchasing_bom')
    result = {key: data[key] for key in keys if key in data}
    for key in ('errors', 'blockers', 'diagnostics', 'checks', 'negative_controls'):
        if isinstance(data.get(key), list):
            result[key+'_count'] = len(data[key])
    if isinstance(data.get('negative_controls'), list):
        result['negative_controls_rejected_count'] = sum(
            item.get('rejected') is True or item.get('status') == 'PASS_REJECTED'
            for item in data['negative_controls'] if isinstance(item, dict))
    if isinstance(data.get('unique_minimum_input_groups'), list):
        result['minimum_input_groups'] = [dict(id=x.get('id'), name=x.get('name'), status=x.get('status'))
                                           for x in data['unique_minimum_input_groups']]
    if data.get('schema') == 'WP07_RETENTION_BOTH_STATIONS_CROSS_V1':
        result['groups'] = {name: {key: group.get(key) for key in ('pair_count', 'separated_pair_count',
                            'needs_brep_count', 'minimum_distance_lower_bound_mm')}
                            for name, group in data.get('groups', {}).items()}
        result['station_input_bindings'] = {name: {key: station.get(key) for key in (
            'status', 'station', 'part_count', 'emission_path', 'emission_sha256', 'c03_local_path',
            'c03_local_sha256', 'c03_counts')} for name, station in data.get('stations', {}).items()}
    return result


def collect_native(snapshot, manifest, manifest_sha):
    result, dependencies = {}, {}
    for state in STATES:
        rows = manifest['states'][state]['instances']
        require(len(rows) == 597 and sum(row['expected_solids'] for row in rows) == 978,
                'This report only describes the frozen 597/978 WP06-integrated branch')
        changes = collections.Counter(row['change'] for row in rows)
        require(dict(changes) == dict(RETAIN_UNCHANGED=573, REPLACE_SINGLE_INSTANCE=8, ADD_HARDWARE=16),
                'Integration delta changed; revise report scope before publication')
        for row in rows:
            dependencies.setdefault(norm(row['native_path']), (row['native_path'], row['native_sha256']))
    dependency_files = [snapshot.file(path, digest) for path, digest in dependencies.values()]
    missing = [x['path'] for x in dependency_files if not x['exists']]
    changed = [x['path'] for x in dependency_files if x.get('expected_hash_matches') is False]
    for state in STATES:
        info = manifest['states'][state]
        file = snapshot.file(R/'native'/('WP07_ROBOT_'+state.upper()+'.SLDASM'))
        receipts = []
        for path in sorted((R/'results').glob('NATIVE_'+state.upper()+'*.json')):
            data, meta = snapshot.json(path)
            if not data:
                receipts.append(meta)
                continue
            cold = data.get('cold_inspection', {})
            observations = cold.get('components', [])
            saved_sha = data.get('final_native_sha256') or data.get('native_save', {}).get('sha256')
            cold_sha = data.get('cold_inspection_native_sha256')
            count = cold.get('component_count', len(observations))
            last = data.get('progress', [])[-1].get('stage') if data.get('progress') else None
            measured_ids = {x.get('id') for x in observations if isinstance(x, dict)}
            exact_ids = measured_ids == {x['id'] for x in info['instances']} and len(observations) == 597
            expected = {x['id']: x for x in info['instances']}
            valid_measured_parts = exact_ids and all(
                row.get('solid_count') == expected[row['id']]['expected_solids'] and row.get('sheet_count') == 0
                and row.get('sha256') == expected[row['id']]['native_sha256']
                and norm(row.get('path', '')) == norm(expected[row['id']]['native_path'])
                and row.get('fixed') is True for row in observations)
            complete = (str(data.get('status', '')).startswith('PASS_') and data.get('inputs_unchanged') is True
                        and data.get('manifest_sha256') == manifest_sha and last in ('completed', 'recovery_completed')
                        and count == 597 and cold.get('solid_count') == 978 and valid_measured_parts
                        and file['exists'] and isinstance(saved_sha, str) and len(saved_sha) == 64
                        and file.get('sha256') == saved_sha == cold_sha and not missing and not changed)
            receipts.append(dict(**meta, completed_cold_evidence_current=complete,
                measured_component_count=count, measured_solid_count=cold.get('solid_count'),
                actual_COM_vector_component_count=sum('world_basis_points_mm' in x for x in observations if isinstance(x, dict)),
                warm_component_count=data.get('warm_inspection', {}).get('component_count'),
                warm_solid_count=data.get('warm_inspection', {}).get('solid_count'),
                native_save_sha256=data.get('native_save', {}).get('sha256'), final_native_sha256=saved_sha,
                cold_native_sha256=cold_sha, final_checkpoint=last, inherited_measurement_count=cold.get('inherited_measurement_count', 0),
                newly_measured_count=cold.get('new_measurement_count'), scope=cold.get('scope'),
                full_step_export_status=data.get('full_step_export_status'),
                producer_inputs_unchanged=data.get('inputs_unchanged')))
        accepted = [x for x in receipts if x.get('completed_cold_evidence_current')]
        accepted.sort(key=lambda x: ('FAST' in Path(x['path']).name, 'RECOVERY' in Path(x['path']).name), reverse=True)
        best = accepted[0] if accepted else max(receipts, key=lambda x: x.get('measured_component_count', 0), default=None)
        result[state] = dict(native_file=file,
            status='SAVED_NATIVE_WITH_COMPLETE_BOUND_COLD_EVIDENCE' if accepted else
                   ('SAVED_NATIVE_CANDIDATE_COLD_INCOMPLETE' if file['exists'] else 'NATIVE_NOT_GENERATED'),
            completed_cold_evidence_current=bool(accepted), selected_receipt=best, all_receipts=receipts,
            planned_instance_count=597, planned_solid_count=978, planned_unique_dependencies=445,
            retained_count=573, replaced_count=8, removed_count=4, added_count=16,
            retention_detail_integrated=False)
    return dict(states=result, completed_state_count=sum(x['completed_cold_evidence_current'] for x in result.values()),
                dependency_mode='LINKED_WORKSPACE_DEPENDENCIES_NOT_PACK_AND_GO', standalone_pack_and_go=False,
                manifest_union_native_dependency_count=len(dependencies), dependencies_checked=len(dependency_files),
                dependencies_missing=missing, dependencies_changed=changed, dependencies=dependency_files,
                changed_geometry_scope='WP06_SIDE_JOINT_DELTA_ONLY', retention_detail_integrated=False,
                inherited_B601_native_part_holds_count=10, inherited_B601_holds_cleared=False)


def collect_records(snapshot, paths):
    output = []
    for path in sorted(set(Path(p).resolve() for p in paths)):
        data, meta = snapshot.json(path)
        if data:
            meta.update(facts=brief(data))
            if isinstance(data.get('checks'), list):
                actual_counts = collections.Counter(x.get('status', 'STATUS_NOT_DECLARED')
                    for x in data['checks'] if isinstance(x, dict))
                declared = data.get('counts')
                meta['actual_check_status_counts'] = dict(actual_counts)
                meta['actual_check_total'] = len(data['checks'])
                if isinstance(declared, dict):
                    meta['declared_check_counts_consistent'] = all(
                        declared.get(key, 0) == actual_counts.get(key, 0) for key in set(declared) | set(actual_counts))
            if data.get('checker_path') and data.get('checker_sha256'):
                meta['checker_source'] = snapshot.file(data['checker_path'], data['checker_sha256'])
            if data.get('receipt_path'):
                expected = data.get('input_sha256', {}).get(data['receipt_path'])
                meta['referenced_geometry_receipt'] = snapshot.file(data['receipt_path'], expected)
            if data.get('schema') == 'WP07_RETENTION_BOTH_STATIONS_CROSS_V1':
                comparisons = data.get('comparisons', [])
                actual = collections.Counter(row.get('status', 'STATUS_NOT_DECLARED') for row in comparisons)
                meta['actual_comparison_status_counts'] = dict(actual)
                meta['actual_comparison_total'] = len(comparisons)
                group_checks = {}
                for name, declared in data.get('groups', {}).items():
                    group_rows = [row for row in comparisons if row.get('group') == name]
                    group_checks[name] = (len(group_rows) == declared.get('pair_count') and
                        sum(row.get('status') == 'SEPARATED_BY_AABB' for row in group_rows) == declared.get('separated_pair_count') and
                        sum(row.get('status') != 'SEPARATED_BY_AABB' for row in group_rows) == declared.get('needs_brep_count'))
                meta['comparison_group_counts_consistent'] = group_checks
                meta['comparison_counts_consistent'] = (len(comparisons) == data.get('pair_count') and
                    actual.get('SEPARATED_BY_AABB', 0) == data.get('separated_pair_count') and all(group_checks.values()))
                before, after = data.get('source_sha256_before', {}), data.get('source_sha256_after', {})
                meta['cross_source_files'] = [snapshot.file(source, digest) for source, digest in after.items()]
                meta['cross_source_hashes_current'] = (bool(after) and before == after and
                    data.get('source_hashes_unchanged') is True and all(item.get('expected_hash_matches') is True
                        for item in meta['cross_source_files']))
            for key in ('output', 'input_snapshot'):
                item = data.get(key)
                if isinstance(item, dict) and item.get('path'):
                    candidate = Path(item['path'])
                    if not candidate.is_absolute():
                        candidate = R/candidate
                    meta[key] = snapshot.file(candidate, item.get('sha256'))
        output.append(meta)
    return output


def collect_visualization(snapshot):
    paths = list((R/'viewer').glob('*GLB*RESULT*.json')) + list((R/'results').glob('*GLB*CHECK*.json'))
    records = collect_records(snapshot, paths)
    preferred, v3 = None, None
    for record in records:
        is_v3 = Path(record['path']).name == 'REVIEW_GLB_V3_RESULT.json'
        record['role'] = 'BREP_SOURCE_MESH_PREVIEW_V3' if is_v3 else 'HISTORICAL_DISPLAY_RESULT_NOT_CURRENT_PREVIEW'
        data, _ = snapshot.json(record['path'])
        if not data:
            continue
        if is_v3:
            observations = data.get('world_bbox_checks', [])
            output = record.get('output', {})
            complete = (data.get('status') == 'PASS_DISPLAY_REVIEW_ONLY' and data.get('instance_count') == 597
                        and data.get('failed_bounds_count') == 0 and len(observations) == 597
                        and all(x.get('status') == 'PASS_DISPLAY_BOUNDS' for x in observations)
                        and data.get('source_hashes_unchanged') is True and output.get('exists') is True
                        and output.get('expected_hash_matches') is True)
            record['completed_bound_display_check'] = complete
            if complete:
                preferred = v3 = record
    for record in records:
        if Path(record['path']).name != 'REVIEW_GLB_V4_COMPACT_RESULT.json':
            continue
        record['role'] = 'EXACT_COMPACTED_V3_DISPLAY_PREVIEW_V4'
        data, _ = snapshot.json(record['path'])
        if not data:
            continue
        sources = data.get('source_sha256_before', {})
        source_files = [snapshot.file(path, digest) for path, digest in sources.items()]
        sources_current = bool(source_files) and all(x.get('expected_hash_matches') is True for x in source_files)
        source_by_path = {norm(path): digest for path, digest in sources.items()}
        v3_bound = bool(v3 and source_by_path.get(norm(v3['path'])) == v3.get('sha256') and
                        source_by_path.get(norm(v3['output']['path'])) == v3['output'].get('sha256'))
        observations = data.get('inherited_v3_world_bbox_checks', [])
        exact_flags = ('source_frames_and_hierarchy_preserved', 'all_referenced_view_bytes_identical',
                      'all_accessor_semantics_preserved', 'all_primitive_attributes_preserved',
                      'all_live_materials_preserved', 'live_triangles_and_index_order_preserved')
        output = record.get('output', {})
        complete = (data.get('schema') == 'WP07_LOSSLESS_GLB_COMPACT_V4' and
                    data.get('status') == 'PASS_EXACT_DISPLAY_COMPACTION' and
                    data.get('source_hashes_unchanged') is True and sources_current and v3_bound and
                    all(data.get(key) is True for key in exact_flags) and data.get('decimation') is False and
                    data.get('coordinate_quantization') is False and data.get('attributes_removed') == [] and
                    data.get('instance_count') == 597 and data.get('failed_bounds_count') == 0 and
                    len(observations) == 597 and all(x.get('status') == 'PASS_DISPLAY_BOUNDS' for x in observations) and
                    output.get('exists') is True and output.get('expected_hash_matches') is True)
        prior = data.get('prior_snapshot_attempt', {})
        record.update(completed_bound_display_check=complete, source_files=source_files,
                      source_hashes_current=sources_current, accepted_v3_source_bound=v3_bound,
                      inherited_display_bounds_count=len(observations), exactness_flags={key: data.get(key) for key in exact_flags},
                      producer_rendered=data.get('rendered'), producer_snapshot_reviewed=data.get('snapshot_reviewed'),
                      display_bounds_basis=data.get('display_bounds_basis'), after=data.get('after'),
                      render_completion_inferred_from_compaction=False,
                      prior_snapshot_attempt=snapshot.file(prior['path'], prior.get('sha256')) if prior.get('path') else None)
        if complete:
            preferred = record
    attempts = []
    for path in sorted((R/'logs').glob('snapshot_service*.run.json')):
        data, meta = snapshot.json(path)
        if data:
            meta.update(command=data.get('command'), returncode=data.get('returncode'), elapsed_s=data.get('elapsed_s'),
                        scope='DISPLAY_SNAPSHOT_ATTEMPT_NOT_GEOMETRY_VALIDATION')
            for suffix in ('stdout', 'stderr'):
                log = path.with_name(path.name.removesuffix('.run.json')+'.'+suffix+'.log')
                meta[suffix] = snapshot.file(log)
                if log.is_file() and data.get('status') != 'RUNNING':
                    text = log.read_text(encoding='utf-8-sig', errors='replace')
                    meta[suffix+'_tail'] = text[-3000:]
        attempts.append(meta)
    archives = collect_records(snapshot, (R/'viewer/history').rglob('ARCHIVE_RECEIPT.json'))
    links = []
    if preferred:
        links.append(dict(id='service', path=preferred['output']['path'], url=viewer_url(preferred['output']['path'])))
    for name in ('retention_station0.step.py', 'retention_station1.step.py', 'pcb_reference_panels.step.py'):
        file = snapshot.file(R/'candidate'/name)
        if file['exists']:
            links.append(dict(id=name, path=file['path'], url=viewer_url(file['path']),
                              interactive_display_verified_by_link_existence=False))
    return dict(scope='HASH_BOUND_SOURCE_BREP_CACHE_TRIANGLE_MESH_DISPLAY_ONLY; NOT_NATIVE_BREP_CERTIFICATION',
                records=records, preferred_preview=preferred, accepted_v3_source=v3, history_archives=archives,
                snapshot_attempts=attempts, visual_review=collect_visual_review(snapshot), viewer_links=links,
                viewer_handoff=collect_records(snapshot, [R/'results/VIEWER_HANDOFF.json']),
                v3_expected_receipt=snapshot.file(R/'viewer/REVIEW_GLB_V3_RESULT.json'),
                v3_expected_display_file=snapshot.file(R/'viewer/WP07_SERVICE_BREP_REVIEW_V3.glb'),
                v1_is_failed_history_not_current_pass=True)


def collect_visual_review(snapshot):
    data, meta = snapshot.json(R/'results/VISUAL_REVIEW.json')
    result = dict(receipt=meta, status='VISUAL_REVIEW_NOT_PRESENT', groups=[],
                  reviewed_image_count=0, whole_service_reviewed=False, whole_service_interactive_reviewed=False,
                  saved_whole_png=False,
                  scope='ACTUAL_IMAGE_REVIEW_RECORD_ONLY_NOT_GEOMETRY_OR_MECHANICAL_ACCEPTANCE')
    if not data:
        return result
    valid_schema = data.get('schema') == 'WP07_ROOT_VISUAL_REVIEW_V1'
    for group in data.get('groups', []):
        images = [snapshot.file(item['path'], item.get('sha256'))
                  for item in group.get('images', []) if isinstance(item, dict) and item.get('path')]
        bound = bool(images) and len(images) == len(group.get('images', [])) and all(
            image.get('expected_hash_matches') is True for image in images)
        reviewed = valid_schema and group.get('reviewed') is True and group.get('status') == 'REVIEWED_DISPLAY_ONLY' and bound
        source = group.get('source', {})
        source_file = snapshot.file(source['path'], source.get('sha256')) if source.get('path') else {}
        url_bound = bool(source.get('path') and viewer_url_matches(group.get('viewer_url'), source['path']))
        interactive_reviewed = (valid_schema and group.get('reviewed') is True and
            group.get('status') == 'REVIEWED_INTERACTIVE_DISPLAY_ONLY' and bool(group.get('method')) and
            source_file.get('expected_hash_matches') is True and url_bound)
        result['groups'].append(dict(id=group.get('id'), declared_status=group.get('status'),
            declared_reviewed=group.get('reviewed'), images=images, current_image_hashes_bound=bound,
            reviewed_current_images=reviewed, reviewed_current_interactive_display=interactive_reviewed,
            source=source_file, viewer_url=group.get('viewer_url'), viewer_url_bound=url_bound,
            method=group.get('method'), saved_whole_png=group.get('saved_whole_png'), observations=group.get('observations')))
    whole_groups = [x for x in result['groups'] if x['id'] in ('service', 'whole_service', 'service_v4', 'whole')]
    result.update(status=data.get('status'), declared_whole_service_reviewed=data.get('whole_service_reviewed'),
                  recorded_local=data.get('recorded_local'), receipt_scope=data.get('scope'),
                  reviewed_image_count=sum(len(x['images']) for x in result['groups'] if x['reviewed_current_images']),
                  whole_service_interactive_reviewed=bool(data.get('whole_service_reviewed') is True and whole_groups and
                      all(x['reviewed_current_interactive_display'] for x in whole_groups)),
                  saved_whole_png=bool(data.get('saved_whole_png') is True and whole_groups and
                      all(x['reviewed_current_images'] for x in whole_groups)),
                  whole_snapshot_note=data.get('whole_snapshot_note'),
                  whole_snapshot_failures=collect_records(snapshot, [x['path'] for x in data.get('whole_snapshot_failures', []) if x.get('path')]),
                  whole_service_reviewed=bool(data.get('whole_service_reviewed') is True and whole_groups and
                      all(x['reviewed_current_images'] or x['reviewed_current_interactive_display'] for x in whole_groups)))
    return result


def collect_final_reopen(snapshot, manifest, manifest_sha, native):
    data, meta = snapshot.json(R/'results/FINAL_REOPEN_SERVICE_V4.json')
    result = dict(receipt=meta, status='FINAL_SERVICE_REOPEN_PENDING', current_bound_evidence=False,
                  current_body_count_remeasured=False, current_COM_basis_points_remeasured=False)
    if not data:
        return result
    before, after = data.get('input_sha256_before', {}), data.get('input_sha256_after', {})
    source_files = [snapshot.file(path, digest) for path, digest in after.items()]
    pins_current = bool(after) and before == after and all(x.get('expected_hash_matches') is True for x in source_files)
    expected = {x['id']: x for x in manifest['states']['service']['instances']}
    rows = data.get('components', [])
    ids_exact = len(rows) == 597 and {x.get('id') for x in rows} == set(expected)
    rows_bound = ids_exact and all(norm(row.get('path', '')) == norm(expected[row['id']]['native_path']) and
        row.get('sha256') == expected[row['id']]['native_sha256'] and row.get('fixed') is True and
        row.get('prior_full_cold_solid_count') == expected[row['id']]['expected_solids'] and
        isinstance(row.get('expected_transform_max_error'), (int, float)) and row['expected_transform_max_error'] < 1e-8 and
        isinstance(row.get('prior_actual_COM_basis_error_mm'), (int, float)) and row['prior_actual_COM_basis_error_mm'] <= 1e-5
        for row in rows)
    dependencies = data.get('dependencies', [])
    expected_paths = {norm(x['native_path']): x['native_sha256'] for x in expected.values()}
    deps_bound = len(dependencies) == 445 and {norm(x.get('path', '')) for x in dependencies} == set(expected_paths) and all(
        row.get('sha256') == expected_paths[norm(row.get('path', ''))] for row in dependencies)
    references = {}
    for key in ('prior_receipt', 'independent_three_state_check'):
        source = data.get(key, {})
        references[key] = snapshot.file(source['path'], source.get('sha256')) if source.get('path') else {}
    file = native['states']['service']['native_file']
    final_sha = data.get('final_native_sha256')
    complete = (data.get('schema') == 'WP07_FINAL_NATIVE_REOPEN_V4' and
        data.get('status') == 'PASS_FINAL_NATIVE_SERVICE_DISPLAY_AFTER_THREE_STATE_ACCEPTANCE' and
        native['completed_state_count'] == 3 and data.get('manifest_sha256') == manifest_sha and
        norm(data.get('native_path', '')) == norm(file['path']) and file.get('sha256') == final_sha == data.get('prior_full_cold_native_sha256') and
        data.get('inputs_unchanged') is True and pins_current and rows_bound and deps_bound and
        all(ref.get('expected_hash_matches') is True for ref in references.values()) and
        data.get('component_count') == 597 and data.get('unique_dependencies') == 445 and data.get('prior_full_cold_body_count') == 978 and
        data.get('native_file_unchanged') is True and data.get('left_open_read_only') is True and data.get('no_native_save_performed') is True and
        data.get('current_body_count_remeasured') is False and data.get('current_COM_basis_points_remeasured') is False and
        bool(data.get('progress')) and data['progress'][-1].get('stage') == 'final_saved_service_display_ready_without_saving')
    result.update(status='FINAL_SERVICE_READONLY_REOPEN_CURRENT_BOUND' if complete else 'FINAL_SERVICE_REOPEN_EVIDENCE_INCOMPLETE',
                  observed_status=data.get('status'), current_bound_evidence=complete, native_file=file,
                  final_native_sha256=final_sha, references=references, input_files=source_files,
                  input_hashes_current=pins_current, component_rows_bound=rows_bound, dependencies_bound=deps_bound,
                  component_count=len(rows), prior_full_cold_body_count=data.get('prior_full_cold_body_count'),
                  explicit_graphics_and_screenshot_skipped=data.get('explicit_graphics_and_screenshot_skipped'),
                  left_open_read_only=data.get('left_open_read_only'), left_open_dirty_flag=data.get('left_open_dirty_flag'),
                  current_body_count_remeasured=data.get('current_body_count_remeasured'),
                  current_COM_basis_points_remeasured=data.get('current_COM_basis_points_remeasured'), scope=data.get('scope'))
    return result


def local_native_evidence(snapshot, record):
    data, _ = snapshot.json(record['path'])
    if not data or data.get('schema') != 'WP07_RETENTION_NATIVE_LOCAL_ASSEMBLY_V1':
        return None
    saved = data.get('assembly_save', {})
    assembly = snapshot.file(saved['path'], saved.get('sha256')) if saved.get('path') else None
    part_files = []
    for part in data.get('parts', []):
        save = part.get('native_save', {})
        if save.get('path'):
            part_files.append(dict(id=part.get('id'), **snapshot.file(save['path'], save.get('sha256')),
                cold_reopen_recorded=isinstance(part.get('part_cold_reopen'), dict)))
    cold = data.get('cold_assembly_inspection', {})
    components = cold.get('components', [])
    parts = {item['id']: item for item in part_files}
    exact_parts = len(part_files) == len(parts) == 18 and len(components) == 18 and len({x.get('id') for x in components}) == 18
    bound_components = exact_parts and all(row.get('id') in parts and
        norm(row.get('path', '')) == norm(parts[row['id']]['path']) and row.get('sha256') == parts[row['id']].get('sha256')
        and row.get('resolved_solid_count') == 1 and row.get('resolved_sheet_count') == 0
        and row.get('fixed') is True and len(row.get('world_basis_points_mm', [])) == 4 for row in components)
    complete = (data.get('status') == 'PASS_NATIVE_FIXED_LOCAL_ASSEMBLY_COLD_REOPEN_ONLY'
        and data.get('input_files_unchanged') is True and data.get('session_preferences_restored') is True
        and data.get('candidate_instances') == 17 and data.get('context_instances') == 1
        and cold.get('component_count') == 18 and cold.get('resolved_solid_total') == 18
        and cold.get('coordinate_frame') == 'LOCAL_MAST_MM_IDENTITY' and assembly is not None
        and assembly.get('exists') is True and assembly.get('expected_hash_matches') is True
        and saved.get('ok') is True and saved.get('errors') == 0 and bound_components
        and all(x.get('exists') is True and x.get('expected_hash_matches') is True and x['cold_reopen_recorded'] for x in part_files))
    neutral = data.get('roundtrip_export', {})
    return dict(receipt_path=record['path'], receipt_sha256=record.get('sha256'), observed_status=data.get('status'),
                station_index=data.get('station_index'), assembly_file=assembly, native_parts=part_files,
                actual_saved_part_file_count=sum(x.get('exists') and x.get('expected_hash_matches') is True for x in part_files),
                native_local_cold_evidence_current=bool(complete), candidate_instances_from_receipt=data.get('candidate_instances'),
                context_instances_from_receipt=data.get('context_instances'),
                actual_cold_component_count=cold.get('component_count'), actual_cold_solid_total=cold.get('resolved_solid_total'),
                coordinate_frame=cold.get('coordinate_frame', data.get('coordinate_frame')),
                local_roundtrip_STEP=(snapshot.file(neutral['path'], neutral.get('sha256')) if neutral.get('path') else None),
                geometry_roundtrip_material_equivalence_claimed=False, integrated_into_597_instance_system=False,
                engineering_scope='LOCAL_INDEPENDENT_CANDIDATE_NO_MECHANICAL_RELEASE_CREDIT')


def collect_pcb_reference(snapshot):
    contract_path = R/'inputs/pcb_reference_contract.json'
    contract, contract_meta = snapshot.json(contract_path)
    boards = [] if contract is None else contract.get('boards', [])
    source_scope = {} if contract is None else contract.get('drill_scope', {})
    step_path = R/'candidate/pcb_reference_panels.step'
    step = snapshot.file(step_path)
    records = collect_records(snapshot, (R/'results').glob('PCB_REFERENCE*.json'))
    readback_path = R/'results/PCB_REFERENCE_STEP_READBACK.json'
    readback, readback_meta = snapshot.json(readback_path)
    artifacts = []
    for path in (R/'candidate/pcb_reference_panels.step.py', R/'candidate/pcb_reference_panels.py',
                 R/'candidate/pcb_reference_brief.md'):
        artifacts.append(snapshot.file(path))
    image_paths = set()
    for folder in (R/'results', R/'viewer'):
        for extension in ('png', 'jpg', 'jpeg', 'webp'):
            image_paths.update(folder.glob('PCB_REFERENCE*.'+extension))
            image_paths.update(folder.glob('pcb_reference*.'+extension))
    cache = R/'candidate/__cadgen__'
    if cache.exists():
        for extension in ('png', 'jpg', 'jpeg', 'webp'):
            image_paths.update(path for path in cache.rglob('*.'+extension)
                               if 'pcb_reference_panels' in path.as_posix().lower())
    # Root may save snapshots outside the CAD cache. This scan is bounded to R7
    # and accepts only PCB-reference-named image paths, never unrelated images.
    image_paths.update(path for path in R.rglob('*') if path.is_file()
                       and path.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp')
                       and 'pcb_reference' in relative(path).casefold())
    snapshots = [snapshot.file(path) for path in sorted(image_paths)]
    # Source status remains a frozen design declaration. Only an independently
    # completed, current-STEP-bound readback may supply executed geometry credit.
    bound_readback = False
    readback_source_pins = []
    if readback is not None and step['exists']:
        digest_candidates = [readback.get('step_sha256'), readback.get('actual_step_sha256')]
        for name in ('step', 'actual_step', 'source_step'):
            value = readback.get(name)
            if isinstance(value, dict) and value.get('path') and norm(value['path']) == norm(step_path):
                digest_candidates.append(value.get('sha256'))
        for name in ('input_sha256', 'input_sha256_before', 'input_sha256_after', 'source_sha256',
                     'source_sha256_before', 'source_sha256_after'):
            values = readback.get(name)
            if isinstance(values, dict):
                digest_candidates.extend(value for path, value in values.items() if norm(path) == norm(step_path))
        source_after = readback.get('source_sha256_after', {})
        if isinstance(source_after, dict):
            readback_source_pins = [snapshot.file(path, expected) for path, expected in source_after.items()]
        current_sources = bool(readback_source_pins) and all(
            x.get('exists') is True and x.get('expected_hash_matches') is True for x in readback_source_pins)
        counts = readback.get('counts', {})
        bound_readback = (readback.get('schema') == 'WP07_PCB_REFERENCE_STEP_READBACK_V1'
                          and readback.get('status') == 'PASS' and step.get('sha256') in digest_candidates
                          and counts.get('boards_pass') == len(boards) == 4
                          and counts.get('boards_checked') == 4
                          and counts.get('mechanical_holes_pass') == source_scope.get('modeled_mounting_or_outline_drill_records') == 26
                          and counts.get('mechanical_holes_checked') == 26
                          and readback.get('source_files_unchanged') is True
                          and readback.get('independent_geometry_readback') is True and readback.get('generator_called') is False
                          and readback.get('source_sha256_before') == source_after and current_sources)
    return dict(classification='REFERENCE_UNSELECTED_BARE_PCB', contract=contract_meta, source_artifacts=artifacts,
        status=('REFERENCE_STEP_CURRENT_READBACK_PASS' if bound_readback else
                'REFERENCE_STEP_EXISTS_READBACK_NOT_COMPLETE' if step['exists'] else 'REFERENCE_SOURCE_ONLY_NOT_GENERATED'),
        source_board_count=len(boards), source_edge_cuts_records=sum(row.get('all_edge_cuts_records', 0) for row in boards),
        source_internal_loop_count=sum(max(0, row.get('expected_closed_loops', 0)-1) for row in boards),
        source_modeled_mechanical_drill_records=source_scope.get('modeled_mounting_or_outline_drill_records'),
        source_all_pad_drill_and_via_records=source_scope.get('all_pad_drill_and_via_records'),
        source_unmodeled_drill_records=source_scope.get('unmodeled_pad_drill_and_via_records'),
        all_drill_records_include_modeled_subset=source_scope.get('total_includes_modeled_26'),
        boards=[{key: row.get(key) for key in ('id', 'all_edge_cuts_records', 'expected_closed_loops',
                'modeled_mounting_or_outline_drills', 'source_thickness_mm', 'populated_height_mm', 'selected_hardware')}
                for row in boards],
        actual_STEP=step, readback_receipt=readback_meta, readback_bound_to_current_STEP=bound_readback,
        readback_source_files=readback_source_pins,
        expectation_provenance={} if readback is None else readback.get('expectation_provenance', {}),
        full_outline_pointwise_or_material_equivalence_claimed=False,
        result_records=records, snapshot_files=snapshots, snapshot_image_present=bool(snapshots),
        snapshot_review_completed_claimed=False, integrated_into_597_instance_system=False,
        spacecraft_installation_transform_assigned=False, selected_hardware=False,
        actual_populated_component_heights_verified=False, copper_layers_or_routing_complete=False,
        spacecraft_schematic_complete=False, electrical_completion_claimed=False, hardware_energization_allowed=False,
        manufacturing_release=False)


def stdout_json(snapshot, path, required_keys):
    metadata = snapshot.file(path)
    if not metadata['exists']:
        return None, metadata
    records = []
    for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
        try:
            data = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(data, dict) and all(key in data for key in required_keys):
            records.append(data)
    return (records[-1] if records else None), metadata


def collect_cad_validity(snapshot, retention_native):
    """Read actual CLI logs; do not execute a kernel or imply material comparison."""
    descriptors = [
        ('validate_native_retention0', 18, 'LOCAL_NATIVE_ROUNDTRIP_STEP', None),
        ('validate_native_retention1', 18, 'LOCAL_NATIVE_ROUNDTRIP_STEP', None),
        ('validate_retention_view0', 18, 'LOCAL_REVIEW_SOURCE_GEOMETRY', 'refs_retention_view0'),
        ('validate_retention_view1', 18, 'LOCAL_REVIEW_SOURCE_GEOMETRY', 'refs_retention_view1'),
        ('validate_pcb_reference', 4, 'PCB_REFERENCE_SOURCE_GEOMETRY', 'refs_pcb_reference')]
    output = []
    for name, expected, representation, refs_name in descriptors:
        guard, guard_meta = snapshot.json(R/'logs'/(name+'.run.json'))
        actual, log_meta = stdout_json(snapshot, R/'logs'/(name+'.stdout.log'), ('ok', 'entry', 'occurrenceCount', 'failureCount'))
        record = dict(name=name, representation=representation, expected_occurrences=expected,
                      guard=guard_meta, stdout=log_meta, actual_cli_result=actual,
                      bounded_CAD_validity_log_pass=False, boolean_material_equivalence_verified=False,
                      full_spacecraft_validity_claimed=False)
        if guard is None or actual is None:
            record['status'] = 'NOT_RUN_OR_NO_FINAL_STRUCTURED_RESULT'
            output.append(record)
            continue
        command = guard.get('command', [])
        if 'validate' not in command or command.index('validate')+1 >= len(command):
            record['status'] = 'GUARD_COMMAND_DOES_NOT_BIND_VALIDATE_TARGET'
            output.append(record)
            continue
        target = Path(command[command.index('validate')+1])
        target = target.resolve() if target.is_absolute() else (R/target).resolve()
        require(target.is_relative_to(R), 'Unexpected nonlocal validation target')
        is_builder = target.name.endswith('.step.py')
        step_path = target.with_suffix('') if is_builder else target
        entry_path = step_path.with_suffix('')
        actual_entry = Path(actual['entry'])
        actual_entry = actual_entry.resolve() if actual_entry.is_absolute() else (R/actual_entry).resolve()
        record.update(command_target=snapshot.file(target), STEP_file=snapshot.file(step_path),
                      command_validates_builder=is_builder, entry_matches_command=norm(actual_entry) == norm(entry_path))
        binding = False
        if representation == 'LOCAL_NATIVE_ROUNDTRIP_STEP':
            matches = [item for item in retention_native if item.get('local_roundtrip_STEP') and
                       norm(item['local_roundtrip_STEP']['path']) == norm(step_path)]
            if len(matches) == 1:
                file = matches[0]['local_roundtrip_STEP']
                binding = (not is_builder and file.get('exists') is True and file.get('expected_hash_matches') is True
                           and file.get('sha256') == record['STEP_file'].get('sha256'))
                record['native_export_binding'] = dict(receipt_path=matches[0]['receipt_path'],
                    receipt_sha256=matches[0]['receipt_sha256'], exported_STEP_sha256=file.get('sha256'))
        else:
            refs_guard, refs_guard_meta = snapshot.json(R/'logs'/(refs_name+'.run.json'))
            refs, refs_meta = stdout_json(snapshot, R/'logs'/(refs_name+'.stdout.log'), ('ok', 'tokens'))
            record['refs_guard'], record['refs_stdout'] = refs_guard_meta, refs_meta
            if refs is not None and refs_guard is not None:
                tokens = []
                for token in refs.get('tokens', []):
                    if not token.get('stepPath'):
                        continue
                    token_path = Path(token['stepPath'])
                    token_path = token_path.resolve() if token_path.is_absolute() else (R/token_path).resolve()
                    if norm(token_path) == norm(step_path):
                        tokens.append(token)
                if len(tokens) == 1:
                    token = tokens[0]
                    record['refs_STEP_binding'] = dict(step_path=str(step_path), step_sha256=token.get('stepHash'),
                                                       summary=token.get('summary', {}))
                    binding = (is_builder and refs.get('ok') is True and refs_guard.get('status') == 'COMPLETED'
                               and refs_guard.get('returncode') == 0 and record['STEP_file'].get('exists') is True
                               and token.get('stepHash') == record['STEP_file'].get('sha256')
                               and token.get('summary', {}).get('leafOccurrenceCount') == expected)
        passed = (guard.get('status') == 'COMPLETED' and guard.get('returncode') == 0
                  and actual.get('ok') is True and actual.get('occurrenceCount') == expected
                  and actual.get('failureCount') == 0 and not actual.get('errors')
                  and record['entry_matches_command'] and record['command_target']['exists'] and binding)
        record.update(status='PASS_SCOPED_CAD_VALIDITY_LOG' if passed else 'INCOMPLETE_OR_FAILED_CAD_VALIDITY_BINDING',
                      bounded_CAD_validity_log_pass=passed, current_STEP_hash_binding=binding,
                      scope=('ACTUAL_LOCAL_NATIVE_ROUNDTRIP_STEP_CLI_VALIDATE_ONLY' if not is_builder else
                             'BUILDER_GEOMETRY_CLI_VALIDATE_WITH_SEPARATE_REFS_HASH_BINDING_TO_EXPORTED_STEP'))
        output.append(record)
    return output


def collect_jobs(snapshot):
    jobs = []
    for path in sorted((R/'logs').glob('*.run.json')):
        data, meta = snapshot.json(path)
        if not data:
            jobs.append(meta)
            continue
        samples = data.get('samples', [])
        free = [x.get('available_mib') for x in samples if isinstance(x.get('available_mib'), (int, float))]
        rss = [x.get('child_tree_rss_mib') for x in samples if isinstance(x.get('child_tree_rss_mib'), (int, float))]
        meta.update(name=data.get('name', path.stem), command=data.get('command'), elapsed_s=data.get('elapsed_s'),
                    returncode=data.get('returncode'), client_pid=data.get('pid'),
                    minimum_available_mib=min(free) if free else None, maximum_client_tree_rss_mib=max(rss) if rss else None,
                    saved_native_truth='GUARD_STATUS_DOES_NOT_REPLACE_NATIVE_SAVE_OR_COLD_RECEIPTS')
        jobs.append(meta)
    interruptions = [x for x in jobs if x.get('status') not in ('COMPLETED', 'RUNNING')]
    return dict(all_jobs=jobs, interruptions=interruptions,
                running_guard_records=[x for x in jobs if x.get('status') == 'RUNNING'],
                controlled_stop_notes=collect_records(snapshot, (R/'results').glob('*STOP*.json')))


def collect():
    snapshot = Snapshot()
    snapshot.file(__file__)
    manifest, manifest_meta = snapshot.json(R/'results/INTEGRATION_MANIFEST.json', required=True)
    native = collect_native(snapshot, manifest, manifest_meta['sha256'])
    retention_roots = [path for path in (R/'results').glob('retention_detail*') if path.is_dir()]
    retention_paths = [path for root in retention_roots for path in root.rglob('*.json')]
    retention_paths += list((R/'results').glob('RETENTION*.json'))
    retention = collect_records(snapshot, retention_paths)
    for record in retention:
        record['evidence_group'] = ('C03_COMPARATOR_ON_EXISTING_C02_GEOMETRY'
            if 'retention_detail_c03' in Path(record['path']).parts else
            'LOCAL_NATIVE_ASSEMBLY' if Path(record['path']).name.startswith('RETENTION_NATIVE_') else
            'BOTH_STATIONS_AND_STATION1_WP06_AABB_SUBSETS' if Path(record['path']).name == 'RETENTION_BOTH_STATIONS_CROSS.json' else
            'CROSS_MODULE_SCREEN' if Path(record['path']).name.startswith('RETENTION_WP06_CROSS_') else
            'C02_GEOMETRY_EMISSION_OR_PRIOR_COMPARATOR')
        record['integrated_into_597_instance_system'] = False
    retention_native = [evidence for record in retention
        if record['evidence_group'] == 'LOCAL_NATIVE_ASSEMBLY'
        for evidence in [local_native_evidence(snapshot, record)] if evidence is not None]
    electrical = collect_records(snapshot, (R/'results').glob('ELECTRICAL*.json'))
    pcb_reference = collect_pcb_reference(snapshot)
    cad_validity = collect_cad_validity(snapshot, retention_native)
    visuals = collect_visualization(snapshot)
    final_reopen = collect_final_reopen(snapshot, manifest, manifest_meta['sha256'], native)
    validation_paths = list((R/'results').glob('NATIVE_DELIVERY_CHECK*.json')) + list((R/'results').glob('FINAL_REOPEN_SERVICE*.json'))
    validation = collect_records(snapshot, validation_paths)
    whole_steps = []
    for state in STATES:
        for kind, path in [('ACTUAL_NATIVE_ROUNDTRIP_CANDIDATE', R/'native'/('WP07_ROBOT_'+state.upper()+'.step')),
                           ('SOURCE_COMPOSITE_CANDIDATE', R/'candidate'/('servicer_'+state+'.step'))]:
            whole_steps.append(dict(state=state, representation=kind, **snapshot.file(path),
                                   accepted_as_complete_delivery=False))
    jobs = collect_jobs(snapshot)
    bom, bommeta = snapshot.json(R/'results/BOM_AUDIT.json')
    ecad_readme = snapshot.file(R/'ecad/README.md')
    part_steps = {norm(x['step_path']): x for state in manifest['states'].values() for x in state['instances']}
    report = dict(schema=SCHEMA, status='FACTUAL_SNAPSHOT_NOT_ENGINEERING_GATE_OR_RELEASE', is_gate=False,
        generated_utc=dt.datetime.now(dt.timezone.utc).isoformat(), run_path=str(R), manifest=manifest_meta,
        native=native, native_validation_records=validation, final_service_reopen=final_reopen,
        retention=dict(scope='LOCAL_CANDIDATE_ONLY_NOT_INTEGRATED_IN_597_INSTANCE_SYSTEM', integrated_into_system=False,
                       records=retention, local_STEP_file_count=sum(len(list(root.rglob('*.step'))) for root in retention_roots),
                       c03_is_comparator_revision_on_c02_geometry=True, native_local_assemblies=retention_native),
        electrical=dict(scope='REFERENCE_EXTRACTION_INTERFACE_DRAFT_AND_STATIC_CONSISTENCY_ONLY', records=electrical,
                        readme=ecad_readme, hardware_energization_allowed=False, electrical_completion_claimed=False),
        pcb_mechanical_reference=pcb_reference,
        bounded_CAD_validity_records=cad_validity,
        visualization=visuals,
        whole_STEP=dict(complete_delivery=False, candidates=whole_steps,
                        scope='WHOLE_597_INSTANCE_SPACECRAFT_ONLY; LOCAL_AND_PCB_STEP_DELIVERIES_ARE_SEPARATE',
                        source_composite_is_native_roundtrip=False,
                        text='本轮没有获得完整整机 STEP 交付证据；源组合 STEP 与原生回导 STEP 分别记录，不能互换。'),
        existing_part_STEP_references=dict(manifest_unique_reference_count=len(part_steps),
                                          scope='REFERENCED_PART_FILES_NOT_A_COMPLETE_ASSEMBLY_STEP_EXPORT'),
        jobs=jobs, BOM=None if bom is None else dict(**bommeta, facts=brief(bom)),
        engineering_scope=dict(full_system_global_material_equivalence=False, continuous_motion_verified=False,
            physical_assembly_completed=False, strength_verified=False, mass_budget_complete=False,
            manufacturing_release=False, flight_qualification=False, inherited_B601_holds_cleared=False),
        unreadable_receipts=snapshot.unreadable)
    snapshot.check_unchanged()
    report['source_snapshot_sha256'] = snapshot.pins
    report['source_snapshot_unchanged_during_collection'] = True
    return report


def render(report):
    n = report['native']
    lines = [MARKER, '# WP07 机械设计与装配交付记录', '',
             '生成时间（UTC）：'+report['generated_utc']+'。本文件按现存文件与机器记录汇总本轮事实，不是新的工程 Gate 或制造放行。', '',
             '当前 '+str(n['completed_state_count'])+'/3 个构型具备与现有原生文件、依赖哈希绑定的完整冷检查记录。'
             '597 实例整机分支只集成 WP06 侧向连接改动：保留 573、替换 8、删除 4 个旧裸杆件并新增 16 个紧固件，目标为 978 个实体。'
             '本轮保持机构的局部候选尚未并入这套整机。', '',
             '模块执行入口：'+link('当前机械模块执行状态表', R/'results/MECHANICAL_MODULE_EXECUTION_STATUS.csv')+
             ' 列出 16 个模块的本轮实际执行、剩余边界和证据。原 '+
             link('MECHANICAL_MODULE_MATRIX.csv', R/'results/MECHANICAL_MODULE_MATRIX.csv')+
             ' 是准备阶段清单，保留其当时状态；当前执行表不代表各模块工程设计全部完成。', '',
             '## 原生装配与查看', '', '| 构型 | 当前文件与检查事实 | 证据 |', '|---|---|---|']
    for state in STATES:
        item = n['states'][state]
        selected = item['selected_receipt']
        if item['completed_cold_evidence_current']:
            description = '原生已保存；597 实例 / 978 实体完整冷检记录绑定当前文件'
        elif item['native_file']['exists']:
            count = selected.get('measured_component_count', 0) if selected else 0
            description = '原生候选已保存；完整冷检未完成（已记录 '+str(count)+'/597 实例）'
        else:
            description = '原生尚未生成'
        file_text = link(state.upper(), item['native_file']['path']) if item['native_file']['exists'] else state.upper()
        evidence = link(selected['status'], selected['path']) if selected else '尚无执行记录'
        lines.append('| '+file_text+' | '+description+' | '+evidence+' |')
    lines += ['', '原生文件使用已固定哈希的 WP05/WP06 链接依赖；每态清单含 445 个不同原生零件文件，三态清单合计 '
              +str(n['manifest_union_native_dependency_count'])+' 个。当前不是独立 Pack and Go 包，移动装配文件时必须保留这些依赖路径。', '',
              '**整机 STEP：** '+report['whole_STEP']['text']+' 已生成的局部装配、PCB 参考和分件 STEP 单独交付，不等于完整整机 STEP。', '',
              'B601 的 10 个原生零件沿用既有几何 HOLD；实体计数、变换复核或 GLB 可视化不解除这些 HOLD，也不代表整机材料等价或全局无干涉。', '']
    final_reopen = report['final_service_reopen']
    if final_reopen['current_bound_evidence']:
        lines += ['SERVICE 最终只读重开已完成，'+link('最终重开记录', final_reopen['receipt']['path'])+
                  ' 绑定当前原生文件及 597 实例 / 445 个依赖的身份、哈希、矩阵与固定状态。'
                  '978 个实体及实际 COM 四基点来自同一原生文件哈希下的先前完整冷检；此次未重新逐体或重新采集 COM 四基点，也未保存原生文件。'
                  '这不单独证明整机图像已渲染或已目视审阅。', '']
    else:
        lines += ['SERVICE 最终只读重开状态：'+final_reopen['status']+
                  ('；'+link('实际记录', final_reopen['receipt']['path']) if final_reopen['receipt']['exists'] else '；尚无完成记录')+'。', '']
    lines += ['## 局部保持机构候选', '',
              '这些成果是独立的局部候选，未集成到上述 597 实例整机。以下照录实际检查状态；名义几何或有条件装配路径结果不代表真实螺纹、预紧、强度或连续动作完成。', '']
    if report['retention']['records']:
        lines += ['| 记录 | 模式 / 站点 / 姿态 | 实际状态 | 已记录检查数量 |', '|---|---|---|---|']
        for rec in report['retention']['records']:
            f = rec.get('facts', {})
            count = rec.get('actual_check_status_counts', f.get('counts', f.get('checks_count', '—')))
            if rec.get('declared_check_counts_consistent') is False:
                count = str(count)+'；与声明counts不一致'
            scope_label = ' / '.join(str(f.get(key, '—')) for key in ('mode', 'station_index', 'state'))
            lines.append('| '+link(relative(rec['path']), rec['path'])+' | '+scope_label+' | '+str(rec['status'])+' | '+str(count)+' |')
        c03 = [rec for rec in report['retention']['records']
               if rec.get('evidence_group') == 'C03_COMPARATOR_ON_EXISTING_C02_GEOMETRY' and rec.get('facts', {}).get('mode') == 'local']
        for rec in c03:
            counts = rec.get('actual_check_status_counts', {})
            if rec.get('actual_check_total', 0):
                lines += ['', 'C03 对照器 '+link(relative(rec['path']), rec['path'])+' 实际记录 '+str(counts.get('PASS', 0))+
                          '/'+str(rec['actual_check_total'])+' 项 PASS；其几何输入仍来自已生成的 C02 局部零件。'
                          '这不增加整机集成或强度、真实螺纹与制造放行的结论。']
        if any(rec.get('facts', {}).get('mode') == 'neighbours' for rec in report['retention']['records']):
            lines += ['', '各邻域对照记录分别对应表中指定站点、冻结姿态和邻件合同；其检查数量不相加作为全机或连续动作验证。']
    else:
        lines.append('尚无局部保持机构执行结果。')
    for rec in report['retention']['records']:
        if rec.get('evidence_group') == 'CROSS_MODULE_SCREEN':
            facts = rec.get('facts', {})
            lines += ['', '保持机构与 WP06 改件的交叉检查 '+link(relative(rec['path']), rec['path'])+
                      ' 记录 '+str(facts.get('separated_pair_count', '未记录'))+'/'+str(facts.get('pair_count', '未记录'))+
                      ' 对包围盒分离，'+str(facts.get('needs_brep_count', '未记录'))+' 对需要进一步 BRep 处理。'
                      '这仅覆盖所选保持机构与 24 个 WP06 改件，不是整机全部邻件或连续运动检查。']
        elif rec.get('evidence_group') == 'BOTH_STATIONS_AND_STATION1_WP06_AABB_SUBSETS':
            facts = rec.get('facts', {})
            lines += ['', '两站交叉结果 '+link(relative(rec['path']), rec['path'])+' 的实际状态为 '+str(rec['status'])+
                      '；记录 '+str(rec.get('actual_comparison_total', '未记录'))+' 对比较。下面两个子集分别列示：', '',
                      '| 指定子集（三个冻结姿态） | 分离 / 比较对数 | 最小距离下界 mm | NEEDS_BREP |',
                      '|---|---|---|---|']
            labels = {'STATION_0_VS_STATION_1': '站 0 的 17 件 × 站 1 的 17 件',
                      'STATION_1_VS_WP06_DELTA': '站 1 的 17 件 × WP06 的 24 个改件'}
            for name, group in facts.get('groups', {}).items():
                lines.append('| '+labels.get(name, name)+' | '+str(group.get('separated_pair_count'))+'/'+
                    str(group.get('pair_count'))+' | '+str(group.get('minimum_distance_lower_bound_mm'))+' | '+
                    str(group.get('needs_brep_count'))+' |')
            lines += ['', '该记录的分组数量一致性：'+str(rec.get('comparison_counts_consistent'))+
                      '；当前输入哈希绑定：'+str(rec.get('cross_source_hashes_current'))+'。'
                      '原站 0 对 WP06 的交叉记录独立保留，不把这些数量合并为全机碰撞、连续路径或制造验证。']
    local_native = report['retention'].get('native_local_assemblies', [])
    if local_native:
        lines += ['', '| 局部原生装配 | 实际交付事实 |', '|---|---|']
        for item in local_native:
            assembly = item.get('assembly_file')
            title = link('Station '+str(item['station_index'])+' 局部装配', assembly['path']) if assembly and assembly['exists'] else 'Station '+str(item['station_index'])
            facts = ('已保存并冷检 18 实例 / 18 实体（17 个候选零件 + 1 个已有上下文零件）'
                if item['native_local_cold_evidence_current'] else
                '局部原生完成证据不足；当前记录 '+str(item['actual_saved_part_file_count'])+' 个已保存零件文件，状态 '+str(item['observed_status']))
            lines.append('| '+title+' | '+facts+'；独立局部坐标，未整星回装 |')
            neutral = item.get('local_roundtrip_STEP')
            if neutral and neutral.get('exists'):
                lines.append('| '+link('Station '+str(item['station_index'])+' 局部原生回导 STEP', neutral['path'])+
                             ' | 实际导出文件；有限有效性检查见下表，未声明布尔材料等价 |')
    else:
        lines += ['', '尚无已执行的保持机构局部原生装配记录；不能仅根据生成脚本记为已生成 18 件原生装配。']
    lines += ['', '### 已执行的局部与参考几何有效性检查', '',
              '以下读取真实 CAD `validate` 的结构化 stdout，并核对已结束的 guard、目标路径和实际 STEP 哈希。'
              '目标为 `.step` 的两项是局部原生回导 STEP；目标为 `.step.py` 的项是生成源几何检查，并以单独 `refs` 结果绑定已导出的 STEP。'
              '这些有限检查不等于源/回导体的双向布尔材料等价或整机有效性。', '',
              '| 目标与范围 | 实际 occurrences / failures | 结果 |', '|---|---|---|']
    labels = {'LOCAL_NATIVE_ROUNDTRIP_STEP': '局部原生回导 STEP', 'LOCAL_REVIEW_SOURCE_GEOMETRY': '局部视图源几何',
              'PCB_REFERENCE_SOURCE_GEOMETRY': 'PCB 参考源几何'}
    for record in report['bounded_CAD_validity_records']:
        actual = record.get('actual_cli_result') or {}
        target = record.get('STEP_file')
        label = labels.get(record['representation'], record['representation'])+' / '+record['name']
        if target and target['exists']:
            label = link(label, target['path'])
        lines.append('| '+label+' | '+str(actual.get('occurrenceCount', '未执行'))+' / '+
                     str(actual.get('failureCount', '未执行'))+' | '+
                     link(record['status'], record['stdout']['path'])+' |')
    lines += ['', '## 可视化与电气', '',
              '显示文件按已执行记录和当前哈希选择：优先采用 V4 精确紧缩 GLB，保留 V3 的源 STEP / BRep 缓存来源。'
              'GLB 是显示用三角网格；精确紧缩只保持已引用的显示字节、层级和变换，不代表渲染完成、BRep 有效性、间隙或机械验收。', '']
    preferred = report['visualization'].get('preferred_preview')
    if preferred:
        facts = preferred.get('facts', {})
        is_v4 = preferred['role'] == 'EXACT_COMPACTED_V3_DISPLAY_PREVIEW_V4'
        title = '优先载入：V4 精确紧缩 GLB' if is_v4 else '可供载入：V3 BRep 来源显示网格'
        lines += [link(title, preferred['output']['path'])+'：实际状态 '+str(preferred['status'])+
                  '；文件 '+format(preferred['output']['bytes'], ',')+' 字节，'+str(facts.get('instance_count'))+
                  ' 个实例。实际显示与目视审阅另见下方记录。', '']
        if is_v4:
            v3 = report['visualization']['accepted_v3_source']
            lines += ['V4 来源为 '+link('V3 显示记录', v3['path'])+'；保留完整顶点属性（含 CAD 边缘）、索引、三角形顺序和实例变换。'
                      '597 项世界包围盒检查由字节与变换不变关系继承，未增加新的几何验证。', '']
    else:
        lines += ['尚无同时满足已执行显示检查及当前文件哈希绑定的预览记录。', '']
    for rec in report['visualization']['records']:
        out = rec.get('output')
        is_current = rec.get('role') in ('BREP_SOURCE_MESH_PREVIEW_V3', 'EXACT_COMPACTED_V3_DISPLAY_PREVIEW_V4')
        target = '；'+link('显示候选文件', out['path']) if is_current and out and out.get('exists') else ''
        lines.append('- '+link(relative(rec['path']), rec['path'])+'：'+str(rec['status'])+target+
                     ('；旧 V1 失败历史，不作为当前通过预览' if not is_current else '')+'。')
    if not report['visualization']['records']:
        lines.append('尚无可视化执行记录。')
    review = report['visualization']['visual_review']
    for item in report['visualization']['viewer_links']:
        lines += ['', '['+'打开 '+item['id']+' 交互查看器'+']('+item['url']+')。']
    for handoff in report['visualization']['viewer_handoff']:
        if handoff['exists']:
            lines += ['', link('交互查看器实际交接记录', handoff['path'])+'：'+str(handoff['status'])+'。']
    if review['receipt']['exists']:
        lines += ['', link('实际图像审阅记录', review['receipt']['path'])+'：'+str(review['status'])+
                  '；当前哈希仍匹配且已审阅的图像 '+str(review['reviewed_image_count'])+' 张。', '',
                  '| 图像组 | 当前文件绑定与审阅事实 | 图像 |', '|---|---|---|']
        for group in review['groups']:
            text = ('实际本地图像已审阅，仅显示范围' if group['reviewed_current_images'] else
                    '实际交互画面已审阅，绑定 GLB 哈希；无整机 PNG' if group['reviewed_current_interactive_display'] else
                    '未具备当前文件绑定的已审阅记录')
            targets = '、'.join(link(Path(x['path']).name, x['path']) for x in group['images'] if x['exists'])
            if group['reviewed_current_interactive_display']:
                targets = '[交互查看器]('+group['viewer_url']+')'
            lines.append('| '+str(group['id'])+' | '+text+' | '+targets+' |')
    else:
        lines += ['', '尚无实际图像审阅记录。']
    if review['whole_service_interactive_reviewed']:
        lines += ['', '整机 SERVICE 交互画面已在本轮实际加载并审阅，当前 GLB 源文件哈希仍匹配。'
                  '尚无已保存的完整整机 PNG；交互画面审阅不改写 scripts/snapshot 的失败记录。']
    elif review['saved_whole_png']:
        lines += ['', '整机 SERVICE 已保存 PNG 且具备当前图像哈希绑定的实际审阅记录，仅显示范围。']
    else:
        lines += ['', '整机 SERVICE 尚未具备与当前文件绑定的实际画面审阅记录；GLB 文件存在不替代该项。']
    if report['visualization']['snapshot_attempts']:
        lines += ['', '整机快照尝试分别记录如下；内存保护、浏览器页面关闭或不支持的显示模式属于显示流程结果，不判为几何失败。', '',
                  '| 快照尝试 | 实际运行状态 |', '|---|---|']
        for attempt in report['visualization']['snapshot_attempts']:
            lines.append('| '+link(Path(attempt['path']).name, attempt['path'])+' | '+str(attempt['status'])+' |')
    lines += ['', '电气工作仍按参考提取、接口草案与静态一致性记录；未形成可上电接线或完成电气设计的结论。', '']
    if report['electrical']['readme']['exists']:
        lines.append(link('电气包说明', report['electrical']['readme']['path'])+'。')
    for rec in report['electrical']['records']:
        f = rec.get('facts', {})
        details = []
        for key, label in [('module_count', '模块'), ('open_module_count', '未闭合模块'), ('board_count', '参考板卡'),
                           ('negative_controls_rejected_count', '被拒绝的负对照')]:
            if key in f:
                details.append(label+' '+str(f[key]))
        lines.append('- '+link(Path(rec['path']).name, rec['path'])+'：'+str(rec['status'])+
                     ('；'+'，'.join(details) if details else '')+'。')
    pcb = report['pcb_mechanical_reference']
    lines += ['', '### 未选型 PCB 机械参考', '',
              '参考合同包含 '+str(pcb['source_board_count'])+' 块裸板、'+str(pcb['source_edge_cuts_records'])+
              ' 条源板框/内部槽边、'+str(pcb['source_modeled_mechanical_drill_records'])+' 个机械相关钻孔记录及各自源文件厚度。'
              '源数据的 '+str(pcb['source_all_pad_drill_and_via_records'])+' 个总钻孔/过孔记录已经包含这 '+
              str(pcb['source_modeled_mechanical_drill_records'])+' 个；另有 '+str(pcb['source_unmodeled_drill_records'])+' 个未建模。', '']
    if pcb['actual_STEP']['exists']:
        lines.append(link('已生成 PCB 机械参考 STEP', pcb['actual_STEP']['path'])+'；当前状态：'+pcb['status']+'。')
    else:
        lines.append('PCB 机械参考 STEP 尚未生成；当前只记录冻结源和合同，不记为 CAD 已完成。')
    if pcb['readback_receipt']['exists']:
        lines.append(link('独立 STEP 读回结果', pcb['readback_receipt']['path'])+'：'+str(pcb['readback_receipt']['status'])+
                     '；与当前 STEP 哈希绑定的完成证据：'+('有' if pcb['readback_bound_to_current_STEP'] else '不足')+'。')
    else:
        lines.append('独立 STEP 读回尚无执行记录。')
    if pcb['snapshot_files']:
        lines.append('已生成快照文件：'+'、'.join(link(Path(x['path']).name, x['path']) for x in pcb['snapshot_files'])+'。快照存在不单独记为审阅通过。')
    else:
        lines.append('尚未发现本轮 PCB 参考快照文件。')
    lines += ['', '这 '+str(pcb['source_board_count'])+' 块板是未选型的机械参考，并非服务星已经选定的 PCB；未包含真实已装器件高度、铜层与完整布线，'
              '也不代表服务星原理图完成、已经分配机内安装位置或完成电气设计。它们没有加入 597 实例整机。']
    if pcb['readback_receipt']['exists']:
        lines += ['读回检查重新加载实际 STEP，期望参数仍复用生成源的纯参数提取；不声明全板框逐点或材料等价。']
    lines += ['', '## 中断、未完成与范围', '',
              '以下保留本轮全部未成功结束的受控任务；内存保护、主动停止、检查失败与超时分别照录，不改写为成功。', '',
              '| 任务 | 实际状态 | 运行秒数 | 最低可用内存 MiB |', '|---|---|---|']
    for job in report['jobs']['interruptions']:
        elapsed = job.get('elapsed_s')
        free = job.get('minimum_available_mib')
        lines.append('| '+link(job.get('name', Path(job['path']).name), job['path'])+' | '+str(job['status'])+' | '+
                     (f'{elapsed:.2f}' if isinstance(elapsed, (int, float)) else '—')+' | '+
                     (f'{free:.2f}' if isinstance(free, (int, float)) else '—')+' |')
    if not report['jobs']['interruptions']:
        lines.append('| 无已登记中断 | — | — | — |')
    if report['jobs']['running_guard_records']:
        lines += ['', '快照中仍有 RUNNING guard 记录，本报告不把它们记为已完成任务：'+
                  '、'.join(link(x.get('name', '运行记录'), x['path']) for x in report['jobs']['running_guard_records'])+'。']
    lines += ['', '后续仍需完成保持机构的整机邻件核验与受控回装、冻结实际硬件及接线、质量预算、强度与公差、连续动作与实物装配验证。'
              '本轮不声明整星机械设计完成、全局无干涉、硬件上电许可、制造放行或飞行适用。', '',
              '完整事实与文件哈希见 '+link('DELIVERY_STATUS.json', R/'results/DELIVERY_STATUS.json')+'。', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview', action='store_true')
    parser.add_argument('--replace-owned', action='store_true')
    args = parser.parse_args()
    readme, status = R/'README.md', R/'results/DELIVERY_STATUS.json'
    if not args.preview and (readme.exists() or status.exists()):
        require(args.replace_owned and readme.is_file() and status.is_file(), 'Existing report pair is protected')
        old = json.loads(status.read_text(encoding='utf-8-sig'))
        require(old.get('schema') == SCHEMA and readme.read_text(encoding='utf-8').startswith(MARKER),
                'Only this generator\'s own previous report pair may be replaced')
    report = collect()
    markdown = render(report)
    if args.preview:
        print(json.dumps(dict(status=report['status'], native_completed_states=report['native']['completed_state_count'],
            native_states={k: v['status'] for k, v in report['native']['states'].items()},
            retention_records=len(report['retention']['records']), electrical_records=len(report['electrical']['records']),
            visual_records=len(report['visualization']['records']), interruptions=len(report['jobs']['interruptions']),
            preferred_GLB=(report['visualization']['preferred_preview'] or {}).get('output'),
            actual_reviewed_image_count=report['visualization']['visual_review']['reviewed_image_count'],
            whole_service_image_reviewed=report['visualization']['visual_review']['whole_service_reviewed'],
            whole_service_interactive_reviewed=report['visualization']['visual_review']['whole_service_interactive_reviewed'],
            saved_whole_png=report['visualization']['visual_review']['saved_whole_png'],
            final_service_reopen=report['final_service_reopen']['status'],
            pcb_reference_status=report['pcb_mechanical_reference']['status'],
            pcb_reference_snapshot_count=len(report['pcb_mechanical_reference']['snapshot_files']),
            native_retention_complete_count=sum(x['native_local_cold_evidence_current'] for x in report['retention']['native_local_assemblies']),
            native_retention_roundtrip_STEP_files=sum(bool(x.get('local_roundtrip_STEP') and x['local_roundtrip_STEP'].get('exists'))
                for x in report['retention']['native_local_assemblies']),
            bounded_CAD_validity={x['name']:x['status'] for x in report['bounded_CAD_validity_records']},
            pcb_reference_STEP_exists=report['pcb_mechanical_reference']['actual_STEP']['exists'],
            whole_system_STEP_delivery=False, output_not_written=True), ensure_ascii=False, indent=2))
        return
    report['generated_readme_sha256'] = hashlib.sha256(markdown.encode('utf-8')).hexdigest()
    readme_tmp, status_tmp = readme.with_suffix('.md.tmp'), status.with_suffix('.json.tmp')
    readme_tmp.write_text(markdown, encoding='utf-8', newline='')
    status_tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8', newline='')
    os.replace(readme_tmp, readme)
    os.replace(status_tmp, status)
    print(json.dumps(dict(status=report['status'], readme=str(readme), status_file=str(status)), ensure_ascii=False))


if __name__ == '__main__':
    main()
