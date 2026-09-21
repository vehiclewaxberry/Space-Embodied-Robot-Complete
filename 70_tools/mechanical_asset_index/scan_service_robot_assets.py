"""Read-only screening of WP01-WP03; writes only a separate navigation packet.

Byte equality is not permission to delete a file. CAD caches and runtimes are
counted but not hashed, and no semantic geometry equivalence is inferred.
"""
from pathlib import Path
from collections import Counter, defaultdict
import csv
import hashlib
import json
import datetime
import os

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/loop0_20260905/screening'
PACKAGES = {
    'WP01': ROOT / '20_engineering/service_robot_wp01_20260905',
    'WP02': ROOT / '20_engineering/service_robot_wp02_20260905',
    'WP03': ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1',
}
MODELS = {'servicer_service', 'servicer_parking', 'servicer_released',
          'body_equipment_cutaway', 'body_exploded', 'wing_module',
          'retention_module', 'ground_ait'}
READ_FIRST = {'README.md', 'INTEGRATION_REPORT.md', 'ASSEMBLY_SEQUENCE.md',
              'BOM.csv', 'INTERFACES.csv', 'design_parameters.json',
              'DYNAMICS_AND_QUALIFICATION.md', 'SOURCE_AND_INTERFACE_NOTES.md',
              'results/DYNAMICS_HANDOFF.json', 'results/DYNAMICS_SUMMARY_ZH.md',
              'results/DELIVERY_RECEIPT.json', 'results/CONFIGURATION_DIMENSIONS.json'}
HISTORY = {'solar_kinematics_source.py', 'setup_candidate.py'}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def relative(path):
    return path.relative_to(ROOT).as_posix()


def write_csv(name, rows, fields):
    with (OUT / name).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    wp03 = PACKAGES['WP03']
    sources = json.loads((wp03 / 'results/SOURCE_PRESERVATION_CHECK.json').read_text(encoding='utf-8'))
    protected = {str(Path(r['path']).resolve()).casefold() for r in sources['records']}
    directed = {
        'WP01': {'kinematics.py', 'design_parameters.json', 'SOURCE_INPUTS.json'},
        'WP02': {'parts_model.py', 'design_parameters.json', 'motion_analysis.py',
                 'root_compliance.py', 'results/CONTACT_REGISTRATION.json',
                 'results/HARNESS_ANALYSIS.json'},
    }
    manifests = {}
    for name, folder in PACKAGES.items():
        with (folder / 'OUTPUT_SHA256.csv').open(encoding='utf-8-sig', newline='') as stream:
            manifests[name] = {r['path'].replace('\\', '/'): r for r in csv.DictReader(stream)}
    rows = []
    skipped_links = []
    duplicates_by_size = defaultdict(list)
    for package, folder in PACKAGES.items():
        bounded_files = []
        for current, dirs, filenames in os.walk(folder, followlinks=False):
            kept = []
            for name in dirs:
                child = Path(current) / name
                if child.is_symlink() or child.is_junction():
                    skipped_links.append(relative(child))
                else:
                    kept.append(name)
            dirs[:] = kept
            bounded_files.extend(Path(current) / name for name in filenames)
        for path in sorted(bounded_files):
            if path.is_symlink():
                skipped_links.append(relative(path))
                continue
            if not path.is_file():
                continue
            local = path.relative_to(folder).as_posix()
            size = path.stat().st_size
            pinned = str(path.resolve()).casefold() in protected
            if '__cadgen__' in path.parts:
                category, action = 'GENERATED_VIEWER_CACHE', 'Exclude from reading; retain for current viewer/replay'
            elif '__pycache__' in path.parts:
                category, action = 'GENERATED_BYTECODE', 'Exclude from reading; no deletion in this task'
            elif 'runtime' in path.parts or 'runtime_deps' in path.parts:
                category, action = 'RUNTIME_DEPENDENCY', 'Keep runtime until reproducibility environment is consolidated'
            elif pinned or local in directed.get(package, set()) or (package == 'WP01' and local.startswith('inputs/')):
                category, action = 'SOURCE_OR_REPRODUCTION_DEPENDENCY', 'Keep original path; used or pinned by current work'
            elif size == 0 and (local.endswith('.log') or '.stderr.' in local):
                category, action = 'EMPTY_EXECUTION_DIAGNOSTIC', 'Omit from reading; retain receipt/manifest association'
            elif path.suffix == '.log' or '.stderr.' in local:
                category, action = 'EXECUTION_DIAGNOSTIC', 'Read on failure or replay only'
            elif package != 'WP03':
                category, action = 'HISTORICAL_COMPONENT_WORK', 'Hide from current whole-spacecraft reading list; preserve lineage'
            elif any(t in local.lower() for t in ('path30', 'r1_findings', 'material_refinement')) or path.name in HISTORY:
                category, action = 'HISTORICAL_COUNTEREXAMPLE_OR_BOOTSTRAP', 'Keep original; consult only for design rationale/replay'
            elif local in READ_FIRST:
                category, action = 'CURRENT_WORKING_ENTRY', 'Read/use current candidate with declared limitations'
            elif path.name.removesuffix('.step.py').removesuffix('.step') in MODELS:
                category, action = 'CURRENT_MODEL_VARIANT', 'Keep distinct configuration or assembly viewpoint'
            elif local.startswith('parts/'):
                category, action = 'CURRENT_PART_CANDIDATE', 'Keep part identity; not manufacturing release'
            elif local.startswith('results/'):
                category, action = 'CURRENT_CHECK_OR_RECEIPT', 'Keep scope-specific evidence; not interchangeable'
            elif local.startswith(('snapshots/', 'drawings/')) or path.suffix == '.dxf':
                category, action = 'CURRENT_REVIEW_EXPORT', 'Use selected review entry; retain generated export'
            else:
                category, action = 'CURRENT_SOURCE_OR_REFERENCE', 'Keep; consult through working entry'
            row = {'path': relative(path), 'package': package, 'bytes': size,
                   'category': category, 'handling': action,
                   'listed_in_package_manifest': local in manifests[package],
                   'directed_source_pinned': pinned, 'exact_duplicate_group': ''}
            rows.append(row)
            if category not in {'GENERATED_VIEWER_CACHE', 'GENERATED_BYTECODE', 'RUNTIME_DEPENDENCY'} and size > 0:
                duplicates_by_size[size].append((path, row))
    duplicate_rows = []
    groups = 0
    repeated_bytes = 0
    for size, paths in sorted(duplicates_by_size.items()):
        if len(paths) < 2:
            continue
        by_hash = defaultdict(list)
        for path, row in paths:
            by_hash[digest(path)].append(row)
        for sha, members in by_hash.items():
            if len(members) < 2:
                continue
            groups += 1
            group = f'DUP-{groups:03d}'
            repeated_bytes += size * (len(members) - 1)
            for row in members:
                row['exact_duplicate_group'] = group
                duplicate_rows.append({'group': group, 'path': row['path'], 'bytes': size,
                                       'sha256': sha, 'category': row['category'],
                                       'disposition': 'KEEP_PATH_UNTIL_CONSUMER_AND_PROVENANCE_MIGRATION; BYTE_EQUAL_ONLY'})
    manifest_failures = []
    for local, entry in manifests['WP03'].items():
        path = wp03 / local
        if not path.is_file() or path.stat().st_size != int(entry['bytes']) or digest(path) != entry['sha256']:
            manifest_failures.append(local)
    pinned_failures = [r['path'] for r in sources['records']
                       if not Path(r['path']).is_file() or digest(Path(r['path'])) != r['expected_sha256']]
    count = Counter(r['category'] for r in rows)
    byte_counts = Counter()
    package_counts = Counter()
    for row in rows:
        byte_counts[row['category']] += row['bytes']
        package_counts[row['package']] += 1
    summary = {
        'schema': 'SERVICE_ROBOT_ASSET_SCREEN_V1',
        'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'scope': {key: relative(value) for key, value in PACKAGES.items()},
        'file_count': len(rows), 'package_file_counts': dict(package_counts),
        'category_counts': dict(count), 'category_bytes': dict(byte_counts),
        'exact_nonempty_duplicate_groups': groups,
        'exact_duplicate_member_count': len(duplicate_rows),
        'repeated_bytes_beyond_one_per_group': repeated_bytes,
        'repeated_bytes_are_not_estimated_safe_reclaimable_bytes': True,
        'duplicates_exclude_viewer_caches_bytecode_and_runtimes': True,
        'WP03_manifest_entry_count': len(manifests['WP03']),
        'WP03_manifest_mismatches': manifest_failures,
        'pinned_source_count': len(sources['records']), 'pinned_source_mismatches': pinned_failures,
        'referenced_conversation': {'id': '6a9add99-ba8c-83ee-994a-d86cc87f7d1d',
            'title': 'A3.2鲁棒收拢权衡', 'read_thread_used': False,
            'status': 'USER_SUPPLIED_WP03_ADVERSARIAL_LOOP_PACKAGE_AND_REVIEW_TEXT'},
        'skipped_links_or_junctions': skipped_links,
        'deletion_performed': False, 'move_performed': False,
        'CAD_geometry_changed_by_screening': False, 'global_gate_changed': False,
        'limitations': ['File screening is scoped to three WP packages, not a full project dependency closure.',
            'Historical different states, independent checks and semantic duplicates are not byte duplicates.',
            'No assertion about manufacturability, physical assembly, continuous clearance or flight qualification.'],
    }
    write_csv('ASSET_SCREEN.csv', rows, list(rows[0]))
    write_csv('EXACT_DUPLICATES.csv', duplicate_rows,
              ['group', 'path', 'bytes', 'sha256', 'category', 'disposition'])
    (OUT / 'SCREEN_RECEIPT.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if manifest_failures or pinned_failures else 0


if __name__ == '__main__':
    import sys
    if '--full-project' in sys.argv:
        from full_project_catalog import main as full_project_main
        raise SystemExit(full_project_main())
    raise SystemExit(main())
