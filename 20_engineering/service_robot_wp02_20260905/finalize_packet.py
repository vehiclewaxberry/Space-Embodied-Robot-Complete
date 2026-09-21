"""Assemble a scoped delivery receipt from completed results; never runs CAD/hardware."""
from pathlib import Path
import csv, datetime, hashlib, json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def read(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'))

def verified(path, expected):
    p = Path(path)
    actual = sha(p) if p.is_file() else None
    return dict(path=str(p), expected_sha256=expected, actual_sha256=actual,
                unchanged=actual == expected)

def main():
    key = read('results/KEY_GEOMETRY_CHECK.json')
    fixed = read('results/FIXED_GSE_ARM_PATH.json')
    logic = read('results/RELEASE_STATE_MACHINE.json')
    cli = read('results/CLI_VALIDATION_RECEIPT.json')
    held = read('results/held_build_receipt.json')
    context = read('results/held_context_build_receipt.json')
    root = read('results/ROOT_COMPLIANCE.json')
    drawings = read('results/DRAWING_PROJECTIONS.json')
    with (HERE / 'BOM.csv').open(encoding='utf-8-sig', newline='') as f:
        bom = list(csv.DictReader(f))
    with (HERE / 'MEASUREMENT_REGISTER.csv').open(encoding='utf-8-sig', newline='') as f:
        measurements = list(csv.DictReader(f))
    pinned = [verified(r['path'], r['sha256']) for r in read('INPUT_PROVENANCE.json')['rows']]
    breps = [verified(ROOT / r['source'], r['sha256']) for r in
             json.loads((HERE.parent / 'service_robot_wp01_20260905/SOURCE_INPUTS.json').read_text(encoding='utf-8'))]
    meshes = [verified(r['path'], r['sha256']) for r in fixed['mesh_sources']]
    scoped_hashes = [verified(p, h) for p, h in key['source_hashes_after_latest_stage'].items()]
    scoped_hashes += [verified(p, h) for p, h in fixed['source_hashes'].items()]
    scoped_hashes += [verified(HERE / 'key_geometry_check.py', key['script_sha256']),
                      verified(HERE / 'release_state_machine.py', logic['source_code_sha256']),
                      verified(HERE / 'design_parameters.json', logic['parameters_sha256'])]
    checked_preservation = pinned + breps + meshes + scoped_hashes
    assert all(r['unchanged'] for r in checked_preservation), 'Source changed; recompute affected checks.'
    assert not key['source_changed_during_run']
    assert cli['all_commands_succeeded'] and len(cli['runs']) == 8
    assert not key['held_solid_validation']['failing_occurrences']
    assert not key['released_solid_validation']['failing_occurrences']
    pairs = key['sampled_cross_fixed_moving']
    narrow = [r for p in pairs for r in p['narrow_phase_pairs']]
    assert all(r['status'] == 'NO_POSITIVE_COMMON_VOLUME' for r in narrow)
    custom_files = sorted((HERE / 'parts').glob('*.step'))
    assert len(custom_files) == 56 and len(bom) == 79
    assert held['occurrence_count'] == 224 and context['occurrence_count'] == 228
    assert logic['passed_count'] == logic['scenario_count'] == 25
    primary = [n + '.step' for n in ['key_assembly_held', 'key_assembly_released', 'root_connection', 'key_assembly_context']]
    selected = [
        'snapshots/FINAL_key_assembly_context_0_20260905T113651Z.png',
        'snapshots/FINAL_key_assembly_held_0_20260905T113657Z.png',
        'snapshots/FINAL_key_assembly_released_1_20260905T113702Z.png',
        'snapshots/FINAL_root_connection_1_20260905T113707Z.png']
    required = primary + selected + ['README.md', 'DESIGN_REVIEW.md', 'REPRODUCE.md',
        'BOM.csv', 'MEASUREMENT_REGISTER.csv', 'INPUT_AND_MEASUREMENT.md', 'ROOT_LOAD_PATH.md',
        'LOAD_CASES.json', 'HARNESS_DESIGN.md', 'ASSEMBLY_AND_ACCEPTANCE.md',
        'RELEASE_SEQUENCE.md', 'MOTION_AND_CLEARANCE.md', 'collision_coverage.csv',
        'key_interfaces.dxf', 'drawings/WP02_INTERFACE_DRAWINGS.pdf', 'drawings/INTERFACE_DRAWINGS.html']
    assert all((HERE / p).is_file() and (HERE / p).stat().st_size > 0 for p in required)
    receipt = {
        'schema': 'WP02_KEY_ASSEMBLY_DELIVERY_V1',
        'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'status': 'DIGITAL_DETAILED_DESIGN_CANDIDATE_DELIVERED__PHYSICAL_INPUTS_PENDING',
        'physical_state': 'OPEN_PARKING_GROUND_DEVELOPMENT',
        'as_built_assembly_completed': False,
        'manufacturing_release': False,
        'flight_qualification': False,
        'historical_project_gates_modified': False,
        'source_sha256': {n: sha(HERE / n) for n in ['parts_model.py', 'design_parameters.json']},
        'counts': {'BOM_unique_part_numbers': len(bom), 'custom_part_STEP_files': len(custom_files),
            'noncontext_occurrences_each_state': held['occurrence_count'],
            'noncontext_solids_each_state': held['solid_count'],
            'context_solids': context['solid_count'], 'primary_STEP_files': len(primary),
            'interface_drawing_pages': len(drawings), 'physical_measurement_rows': len(measurements)},
        'mass_classification_from_held_build': held['classification_totals'],
        'mass_complete': held['mass_complete'],
        'mass_scope': 'Assumed aluminum density geometry estimates; hardware incomplete; no measured or total spacecraft mass claim.',
        'primary_STEP': [{'path': p, 'bytes': (HERE / p).stat().st_size, 'sha256': sha(HERE / p)} for p in primary],
        'CAD_CLI': {'commands': len(cli['runs']), 'all_succeeded': cli['all_commands_succeeded'],
            'self_intersection_checked': False, 'source': 'results/CLI_VALIDATION_RECEIPT.json'},
        'solid_validity': {'held_failed': key['held_solid_validation']['failing_occurrences'],
            'released_failed': key['released_solid_validation']['failing_occurrences'],
            'scope': 'Per-solid valid topology, closed shells and positive volume; not assembly physical validation.'},
        'moving_fixed_sampled_check': {'Y_positions_mm': [r['Y_mm'] for r in pairs],
            'broad_phase_pair_count': sum(r['total_fixed_moving_pairs'] for r in pairs),
            'Boolean_narrow_phase_pair_count': len(narrow), 'positive_common_volume_pairs': 0,
            'source': 'results/KEY_GEOMETRY_CHECK.json', 'continuous_clearance_proved': False},
        'accepted_arm_fixed_GSE_sampled_check': {k: fixed[k] for k in [
            'sample_count', 'arm_link_count', 'fixed_fixture_count', 'total_sample_link_fixture_pairs',
            'strict_aabb_separation_count', 'triangle_clip_pair_count', 'surface_hit_count',
            'contains_status', 'continuous_rotating_path_status', 'actual_material_intersection_volume_status']},
        'offline_release_logic': {k: logic[k] for k in ['candidate_strokes_mm', 'scenario_count', 'passed_count',
            'hardware_IO_present', 'hardware_actuation_executed', 'sensors_selected_or_validated', 'input_class']},
        'root_compliance': {'scope': root['scope'], 'positive_definite': root['baseline']['positive_definite'],
            'normalized_symmetry_relative': root['baseline']['normalized_symmetry_relative'],
            'max_force_balance_error_N': root['baseline']['max_force_balance_error_N'],
            'max_moment_balance_error_Nm': root['baseline']['max_moment_balance_error_Nm'],
            'saddle_reactions': root['saddle_reactions'], 'strength_margin': None},
        'harness_status': 'HARNESS_PROXY_ONLY; actual OD, dynamic bend, twist, outlet tangent and physical free length pending',
        'vendor_source': {'repository': 'https://github.com/Seeed-Projects/reBot-DevArm',
            'commit': '8def0ebd8ea0785dcbfc58c00ab176ee42acba5d',
            'receipt': 'inputs/vendor_reference/VENDOR_SOURCE_RECEIPT.json',
            'physical_DM_variant_confirmed': False},
        'remaining_physical_inputs': ['DM version, installation frame/clocking and real fastener insertion/thread engagement',
            'Manufacturer permitted link2 lower and link3 upper contact regions, shell supports and pad pressure',
            'Cable OD, backshell, outlet direction, dynamic bend/twist and free length',
            'Measured arm mass/CG, GSE and independent unloading load capability',
            'Materials, joint/preload/locking design, fits and hardware sensor trigger distance (nominal gap 23 mm)'],
        'known_restrictions': ['Current four GSE columns overlap 90-degree wing deployed envelopes; reconfigure before wing motion',
            'Original complete arm BRep topology findings retained; display convex hulls do not repair or verify it',
            'Continuous motion, complete closed-body containment, full self-collision, cable pinching and loaded deflection remain unverified'],
        'source_preservation': {'pinned_WP01_attachment_M3R': pinned, 'original_BRep_sources': breps,
            'accepted_STL_sources': meshes, 'all_checked_sources_unchanged': True,
            'meaning': 'Only listed hashes verified; no claim that every workspace file was audited.'},
        'current_check_dependencies': scoped_hashes,
        'visual_review': {'primary_models_reviewed': 4, 'selected_images': selected,
            'released_ISO_cropped_not_selected': 'snapshots/FINAL_key_assembly_released_0_20260905T113702Z.png',
            'DXF_3D_snapshot': 'FAILED_MISSING_PREVIEW_GLB_FOR_2D_PACKAGE',
            'DXF_fallback': 'Five-page vector PDF and PNG render complete; root and B-saddle pages visually reviewed'},
        'required_deliverables_present': required,
        'evidence_files': ['results/' + n + '.json' for n in ['KEY_GEOMETRY_CHECK', 'FIXED_GSE_ARM_PATH',
            'CONTACT_REGISTRATION', 'ROOT_COMPLIANCE', 'HARNESS_ANALYSIS', 'RELEASE_STATE_MACHINE',
            'VENDOR_GEOMETRY_PROBE', 'MOTION_ANALYSIS', 'DRAWING_PROJECTIONS', 'CLI_VALIDATION_RECEIPT', 'SNAPSHOT_RECEIPT']],
        'manifest': {'path': 'OUTPUT_SHA256.csv', 'excludes': ['itself', 'caches', 'runtime_deps', 'runtime', 'temporary/log files', 'unselected snapshots']}
    }
    (HERE / 'results/DELIVERY_RECEIPT.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    files = [p for p in HERE.iterdir() if p.is_file() and p.suffix in ['.md', '.py', '.json', '.csv', '.step', '.dxf'] and p.name != 'OUTPUT_SHA256.csv']
    for folder in ['parts', 'inputs', 'drawings', 'results']:
        files += [p for p in (HERE / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts
                  and p.suffix.lower() in ['.json', '.csv', '.md', '.py', '.step', '.stp', '.urdf', '.txt', '.pdf', '.png', '.html', '.yaml', '.yml']]
    files += [HERE / p for p in selected]
    files = sorted(set(files))
    with (HERE / 'OUTPUT_SHA256.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f); w.writerow(['path', 'bytes', 'sha256'])
        for p in files: w.writerow([p.relative_to(HERE).as_posix(), p.stat().st_size, sha(p)])
    print(json.dumps({'status': receipt['status'], 'counts': receipt['counts'],
        'manifest_rows': len(files), 'all_checked_sources_unchanged': True}, ensure_ascii=False))

if __name__ == '__main__':
    main()
