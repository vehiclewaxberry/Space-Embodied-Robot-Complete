"""Seal an explicit native whitelist only after its current cold receipts match.

Preparation has no side effects. Run --check to inspect gates without writing;
run --build to write the ZIP, SHA256.csv, and results/PACKAGE_DELIVERY.json.
No COM, CAD loading, source-reference editing, relocation, or Pack and Go.
"""
from pathlib import Path
import argparse
import csv
import datetime as dt
import hashlib
import importlib.util
import io
import json
import os
import struct
import sys
import uuid
import zipfile

OUT = Path(__file__).resolve().parents[1]
PLAN = OUT / 'inputs/INTEGRATED_ASSEMBLY_PLAN.json'
AUDITOR = OUT / 'tools/summarize_delivery.py'
RESULT = OUT / 'results/PACKAGE_DELIVERY.json'
ZIP = OUT / 'SERVICE_STAR_R1_REVIEW_PACKAGE.zip'
CSV = OUT / 'SHA256.csv'
DIAGNOSTIC_STEP = OUT / 'diagnostics/I_2883cdc18626958a_native_roundtrip.step'
STATES = ('service', 'parking', 'released')
TOP_PASS = 'PASS_FIXED_POSE_NATIVE_MEMBERSHIP_TRANSFORMS_AND_LOCAL_REFERENCES'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def key(path):
    return str(Path(path).resolve()).casefold()


def owned(path, domain=None):
    p = Path(path).resolve()
    boundary = (OUT / domain).resolve() if domain else OUT.resolve()
    require(p.is_relative_to(boundary), f'Outside intended package domain: {p}')
    require(p.is_file(), f'Missing file: {p}')
    return p


def relative(path):
    return Path(path).resolve().relative_to(OUT.resolve()).as_posix()


def check_png(path, expected_hash):
    p = owned(path, 'views')
    require(p.suffix.lower() == '.png' and sha(p) == expected_hash, f'PNG hash mismatch: {p}')
    with p.open('rb') as stream:
        head = stream.read(24)
    require(head[:8] == b'\x89PNG\r\n\x1a\n' and head[12:16] == b'IHDR', f'Not PNG: {p}')
    width, height = struct.unpack('>II', head[16:24])
    require(width >= 640 and height >= 480, f'Unexpected PNG dimensions: {p}')
    return p


def delivery_audit():
    """The single file-only authority for recovery, volume and material hash chains.

    derive() returns data only. Never call the summarizer's main(), because main
    writes BOM/status files. No local fallback may accept a rejected proof.
    """
    digest = sha(owned(AUDITOR, 'tools'))
    spec = importlib.util.spec_from_file_location('package_delivery_file_auditor', AUDITOR)
    module = importlib.util.module_from_spec(spec)
    previous_bytecode = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
        status, tables, report = module.derive(root=OUT)
    finally:
        sys.dont_write_bytecode = previous_bytecode
    require(sha(AUDITOR) == digest, 'Shared audit implementation changed during verification')
    require(status.get('artifact_build_status') == 'SOURCE_BOUND_FIXED_POSE_ARTIFACTS_VERIFIED_ENGINEERING_OPEN',
            'Shared delivery audit incomplete: ' + json.dumps({
                'artifact_build_status': status.get('artifact_build_status'),
                'increments': status.get('increment_native_parts'),
                'groups': status.get('fixed_groups'),
                'active_parts': status.get('active_native_part_files'),
                'input_errors': status.get('input_errors')}, ensure_ascii=False))
    for flag in ('native_fixed_pose_delivery_verified', 'neutral_fixed_pose_delivery_verified',
                 'all_active_material_decisions_cold_verified'):
        require(status.get(flag) is True, f'Shared audit gate not true: {flag}')
    require(not status.get('input_errors'), 'Shared audit reports invalid source pins')
    require(report.get('accepted_group_count') == 23, 'Shared audit does not accept all 23 groups')
    require(status.get('active_native_part_files', {}).get('planned_unique') == 692,
            'Shared audit active-part count differs from package contract')
    return status, tables, report, digest


def gates():
    audit_status, tables, audit_report, auditor_hash = delivery_audit()
    proof_pins = {}
    def pin(path, digest):
        target = key(path)
        require(digest and (target not in proof_pins or proof_pins[target]['sha256'] == digest),
                f'Conflicting/missing hash in accepted audit evidence: {path}')
        proof_pins[target] = {'path': str(Path(path).resolve()), 'sha256': digest}
    pin(AUDITOR, auditor_hash)
    for section in ('input_manifest_sha256', 'material_plan_sha256'):
        for path, digest in audit_status[section].items():
            pin(path, digest)
    for proof in audit_report['accepted_increment_geometry_proofs']:
        pin(proof['receipt']['path'], proof['receipt']['sha256'])
    plan = load(PLAN)
    plan_hash = sha(PLAN)
    require(set(plan['states']) == set(STATES), 'Plan must contain exactly three expected states')
    groups = {g['id']: g for g in plan['groups']}
    require(len(groups) == len(plan['groups']) == 23, 'Expected 23 unique planned groups')
    parts = {key(r['native_path']): owned(r['native_path'], 'native')
             for group in groups.values() for r in group['rows']}
    require(len(parts) == 692, f'Expected 692 unique native parts, found {len(parts)}')
    require(all(p.suffix.lower() == '.sldprt' for p in parts.values()), 'Part whitelist has non-SLDPRT')
    group_paths = {gid: owned(g['path'], 'native') for gid, g in groups.items()}
    require(all(p.name == gid + '.SLDASM' and gid.startswith('DPG_') for gid, p in group_paths.items()),
            'Only current DPG assemblies may enter group whitelist')
    tops = {state: owned(plan['states'][state]['path'], 'native') for state in STATES}
    require(all(p.name == f'SERVICE_STAR_{s.upper()}_R1.SLDASM' for s, p in tops.items()),
            'Unexpected top assembly; legacy 873 tops are prohibited')
    library = owned(OUT / 'native/GROUND_CANDIDATE_MATERIALS.sldmat', 'native')
    for filename, digest in plan.get('source_maps', {}).items():
        require(sha(owned(OUT / 'inputs' / filename, 'inputs')) == digest, f'Stale source map: {filename}')
    accepted_groups = audit_report.get('accepted_group_proofs', {})
    require(set(accepted_groups) == set(groups), 'Shared audit must expose all accepted_group_proofs for sealing')
    group_evidence = {}
    for gid, path in group_paths.items():
        proof = accepted_groups[gid]
        require(key(proof['path']) == key(path) and sha(path) == proof['sha256'],
                f'Native group changed after shared audit: {gid}')
        pin(proof['receipt']['path'], proof['receipt']['sha256'])
        group_evidence[gid] = {'path': relative(path), 'sha256': proof['sha256'],
            'receipt': proof['receipt'], 'proof_authority': 'summarize_delivery.derive'}
    top_evidence = {}
    allowed = set(parts) | {key(p) for p in group_paths.values()} | {key(library)}
    for state in STATES:
        definition = plan['states'][state]
        accepted = audit_status['states'][state]['native_assembly_receipt']
        pin(accepted['path'], accepted['sha256'])
        receipt = owned(accepted['path'], 'results')
        require(sha(receipt) == accepted['sha256'], f'Accepted TOP proof changed after shared audit: {state}')
        data = load(receipt)
        require(sha(tops[state]) == audit_status['states'][state]['native_assembly_current_sha256'],
                f'Native TOP changed after shared audit: {state}')
        expected = {r['id']: r for gid in definition['groups'] for r in groups[gid]['rows']}
        require(len(expected) == definition['leaf_count'] == audit_status['states'][state]['instances'] == 1110,
                f'Package instance contract mismatch: {state}')
        # This is a packaging boundary, not a second CAD acceptance rule: every
        # dependency of the already-accepted top must be present in the ZIP.
        dependencies = data.get('dependencies', [])
        require(dependencies and all(key(p) in allowed for p in dependencies),
                f'Unpackaged/legacy/external top geometry dependency: {state}')
        expected_dependencies = {key(group_paths[g]) for g in definition['groups']} | {
            key(r['native_path']) for r in expected.values()}
        require({key(p) for p in dependencies} - {key(library)} == expected_dependencies,
                f'Top dependency closure differs from planned whitelist: {state}')
        top_evidence[state] = {'path': relative(tops[state]), 'sha256': data['sha256'],
            'receipt': relative(receipt), 'receipt_sha256': sha(receipt),
            'leaves': len(expected), 'proof_authority': 'summarize_delivery.derive',
            'cold_warnings': data.get('cold_open', {}).get('warnings'),
            'needs_rebuild2': data.get('needs_rebuild2'), 'dependencies': len(expected_dependencies)}
    accepted_parts = {}
    for rows in tables.values():
        for row in rows:
            target = key(row['native_path'])
            require(row['native_material_decision_cold_recorded'] is True,
                    f'Shared audit has no current material decision: {row["native_path"]}')
            pin(row['native_material_receipt'], row['native_material_receipt_sha256'])
            proof = {k: row[k] for k in ('native_current_sha256', 'native_geometry_status',
                'native_geometry_hash_chain_verified', 'native_increment_geometry_cold_verified',
                'native_geometry_receipt', 'native_material_decision_cold_recorded',
                'native_material_receipt', 'native_material_receipt_sha256')}
            require(target not in accepted_parts or accepted_parts[target] == proof,
                    f'Inconsistent per-state shared part proof: {row["native_path"]}')
            accepted_parts[target] = proof
    require(set(accepted_parts) == set(parts), 'Shared audit and native part whitelist differ')
    part_evidence = []
    for target, path in parts.items():
        proof = accepted_parts[target]
        require(sha(path) == proof['native_current_sha256'], f'Part changed after shared audit: {path}')
        part_evidence.append({'path': relative(path), **proof})
    neutral = load(OUT / 'results/NEUTRAL_ASSEMBLY.json')
    pin(audit_status['neutral_receipt']['path'], audit_status['neutral_receipt']['sha256'])
    neutral_paths = []
    for state in STATES:
        p = owned(OUT / 'neutral' / f'SERVICE_STAR_{state.upper()}_R1.step', 'neutral')
        proof = audit_status['states'][state]['neutral_assembly']
        require(proof['current_file_named_leaf_counts_and_transforms_verified'] is True
                and key(proof['path']) == key(p) and sha(p) == proof['sha256'],
                f'Neutral changed after shared audit: {state}')
        neutral_paths.append(p)
    render = neutral['states']['service']['render']
    require(render.get('status') == 'ACTUAL_EXPORTED_STEP_VISUALLY_REVIEWED_WITH_DECLARED_LIMITATIONS'
            and bool(render.get('visual_review')), 'Main view not visually reviewed')
    views = [check_png(render['path'], render['sha256'])]
    current_native_view = OUT / 'results/NATIVE_SERVICE_VIEW.json'
    if current_native_view.exists():
        view = load(current_native_view)
        require(view.get('status') == 'PASS_ACTUAL_NATIVE_CAPTURE_VISUALLY_REVIEWED'
                and view.get('visual_review_accepted') is True, 'New native capture not visually accepted')
        require(view.get('native_sha256') == sha(tops['service']), 'New native capture has stale top hash')
        views.append(check_png(view['png_path'], view['png_sha256']))
    native_view = OUT / 'results/VIEW_service.json'
    if native_view.exists():
        view = load(native_view)
        if view.get('status') == TOP_PASS and view.get('actual_native_capture') is True:
            require(view.get('sha256') == sha(tops['service']), 'Native main view has stale top hash')
            views.append(check_png(view['png_path'], view['png_sha256']))
    native = list(parts.values()) + list(group_paths.values()) + list(tops.values()) + [library]
    require(len(native) == 719 and len({key(p) for p in native}) == 719, 'Native whitelist collision')
    for proof in proof_pins.values():
        require(sha(proof['path']) == proof['sha256'], f'Accepted audit input changed before packaging: {proof["path"]}')
    evidence = {'assembly_plan_sha256': plan_hash,
        'shared_auditor': {'path': relative(AUDITOR), 'sha256': auditor_hash,
                           'entry_point': 'derive(root=OUT)', 'writes_performed': False},
        'shared_audit_status': audit_status, 'shared_audit_report': audit_report,
        'accepted_audit_input_pins': list(proof_pins.values()),
        'native_whitelist_counts': {'parts': 692, 'groups': 23, 'tops': 3, 'material_libraries': 1},
        'groups': group_evidence, 'tops': top_evidence, 'parts': part_evidence,
        'material_library': {'path': relative(library), 'sha256': sha(library)},
        'neutral_receipt_sha256': sha(OUT / 'results/NEUTRAL_ASSEMBLY.json'),
        'views': [relative(p) for p in views]}
    return native, neutral_paths, views, evidence


def gather(native, neutral, views):
    # One specifically authorized review exhibit. Do not glob diagnostics or
    # treat this round-trip specimen as an assembly runtime dependency.
    paths = [owned(OUT / 'README.md'), owned(__file__), owned(AUDITOR),
             owned(DIAGNOSTIC_STEP, 'diagnostics')] + native + neutral + views
    reconciliation = OUT / 'tools/reconcile_volume.py'
    if reconciliation.is_file():
        paths.append(owned(reconciliation, 'tools'))
    for domain in ('docs', 'inputs', 'results'):
        for p in sorted((OUT / domain).rglob('*')):
            if not p.is_file() or p == RESULT:
                continue
            if domain == 'results' and p.suffix.lower() != '.json':
                continue
            paths.append(owned(p, domain))
    files = {relative(p): p for p in paths}
    require(len({name.casefold() for name in files}) == len(files), 'Case-insensitive ZIP entry collision')
    return files


def package(build=False, replace=False):
    native, neutral, views, evidence = gates()
    files = gather(native, neutral, views)
    hashes = {name: sha(p) for name, p in files.items()}
    report = {'schema': 'LOCAL_COLD_VERIFIED_REVIEW_PACKAGE_V1',
        'status': 'PASS_CURRENT_LOCAL_COLD_VERIFIED_PAYLOAD_WHITELIST',
        'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'package_path': str(ZIP), 'evidence': evidence,
        'scope': {'local_native_cold_open_verified': True,
                  'planned_CAD_dependency_files_included': True,
                  'all_historical_original_evidence_copied': False,
                  'standalone_reproduction_of_full_history_claimed': False,
                  'cross_computer_extract_and_relocation_tested': False,
                  'PackAndGo_executed': False, 'native_references_rewritten_by_packager': False,
                  'fully_parametric_model': False, 'continuous_motion_mates': False,
                  'whole_design_complete': False, 'ready_to_power': False, 'flight_ready': False,
                  'whole_mass_kg': None, 'all_engineering_materials_resolved': False},
        'archive_receipt_policy': 'Inside-ZIP receipt seals payload gates before archive hashing; external receipt additionally records final ZIP and CSV hashes. CSV excludes its own digest.',
        'excluded_native_policy': 'Only exact current plan whitelist; legacy WP09D tops/G_* groups, unused parts, staging STEP, and other native files are excluded.',
        'files_from_disk': len(files), 'native_files': len(native),
        'diagnostic_review_exhibits': [{'path': relative(DIAGNOSTIC_STEP),
            'sha256': hashes[relative(DIAGNOSTIC_STEP)],
            'purpose': 'Native round-trip STEP evidence for the item-35 volume discrepancy disposition',
            'assembly_runtime_dependency': False}],
        'hashes_current_at_gate': True}
    if not build:
        print(json.dumps({'status': 'CHECK_ONLY_GATES_PASSED_NO_OUTPUT_WRITTEN',
                          'files': len(files), 'native_files': len(native)}, indent=2))
        return
    require(replace or not ZIP.exists(), f'Existing package protected; use --replace only for this generated package: {ZIP}')
    scope = ("# Package scope\n\n"
        "Open native/SERVICE_STAR_SERVICE_R1.SLDASM (or PARKING/RELEASED) with all native files kept together.\n"
        "This is the current 1110-instance fixed-pose review candidate, not the old 873-instance host.\n"
        "The three native tops and 23 groups were cold-opened locally; receipt and current hashes are checked.\n"
        "Cross-computer extraction/relocation has not been tested. This ZIP is not a SolidWorks Pack and Go result.\n"
        "Imported/reference geometry is not a fully parametric feature model and has no continuous motion mates.\n"
        "STEP colors do not prove engineering material assignments. Read README.md, BOM, and unresolved scope.\n"
        "Historical JSON may retain original absolute provenance paths; those are evidence, not extra packaged geometry.\n"
        "The main workspace retains historical original sources; this ZIP does not copy that entire evidence chain or claim standalone reproduction of it.\n"
        "Including the planned CAD dependency files is distinct from copying every original evidence file; relocation remains untested.\n"
        "diagnostics/I_2883cdc18626958a_native_roundtrip.step is the single authorized volume-discrepancy review exhibit, not an assembly runtime dependency.\n"
        "SHA256.csv covers each payload entry except itself. The external packaging receipt adds the final ZIP hash.\n")
    synthetic = {'PACKAGE_SCOPE.md': scope.encode('utf-8'),
                 'results/PACKAGE_DELIVERY.json': json_bytes(report)}
    manifest = []
    for name in sorted(files):
        manifest.append((name, files[name].stat().st_size, hashes[name]))
    for name, content in sorted(synthetic.items()):
        manifest.append((name, len(content), hashlib.sha256(content).hexdigest()))
    csv_stream = io.StringIO(newline='')
    writer = csv.writer(csv_stream)
    writer.writerow(['relative_path', 'bytes', 'sha256'])
    writer.writerows(sorted(manifest))
    csv_bytes = csv_stream.getvalue().encode('utf-8-sig')
    synthetic['SHA256.csv'] = csv_bytes
    expected = {name: digest for name, size, digest in manifest}
    expected['SHA256.csv'] = hashlib.sha256(csv_bytes).hexdigest()
    temporary = OUT / ('.SERVICE_STAR_R1_REVIEW_PACKAGE.' + uuid.uuid4().hex + '.zip.tmp')
    try:
        with zipfile.ZipFile(temporary, 'x', compression=zipfile.ZIP_DEFLATED,
                             compresslevel=1, allowZip64=True) as archive:
            for name, path in sorted(files.items()):
                archive.write(path, arcname=name)
            for name, content in sorted(synthetic.items()):
                archive.writestr(name, content)
        with zipfile.ZipFile(temporary, 'r') as archive:
            require(set(archive.namelist()) == set(expected), 'ZIP entry whitelist mismatch')
            require(len(archive.namelist()) == len(expected), 'ZIP contains duplicate entries')
            for name, digest in expected.items():
                value = hashlib.sha256()
                with archive.open(name) as stream:
                    for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
                        value.update(block)
                require(value.hexdigest() == digest, f'ZIP payload mismatch: {name}')
        require(set(gather(native, neutral, views)) == set(files), 'Payload inventory changed during packaging')
        require(all(sha(path) == hashes[name] for name, path in files.items()),
                'Payload bytes changed during packaging; archive not published')
        os.replace(temporary, ZIP)
        CSV.write_bytes(csv_bytes)
        report.update(status='PASS_CURRENT_LOCAL_COLD_VERIFIED_WHITELIST_ZIP_SEALED',
                      zip_sha256=sha(ZIP), zip_bytes=ZIP.stat().st_size,
                      sha256_csv_path=str(CSV), sha256_csv_sha256=hashlib.sha256(csv_bytes).hexdigest(),
                      zip_entries=len(expected), zip_readback_each_payload_sha256_verified=True,
                      payload_source_files_unchanged_during_packaging=True,
                      archived_receipt_sha256=expected['results/PACKAGE_DELIVERY.json'])
        RESULT.write_bytes(json_bytes(report))
        print(json.dumps({k: report[k] for k in ['status', 'package_path', 'zip_bytes', 'zip_sha256', 'zip_entries']}, indent=2))
    finally:
        if temporary.exists():
            require(temporary.resolve().parent == OUT.resolve() and temporary.name.startswith('.SERVICE_STAR_R1_REVIEW_PACKAGE.'),
                    'Unsafe temporary cleanup path')
            temporary.unlink()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true', help='Read-only preflight; write nothing')
    mode.add_argument('--build', action='store_true', help='Gate, package, hash, read back, and publish')
    parser.add_argument('--replace', action='store_true', help='Replace only the previous generated ZIP after all checks pass')
    args = parser.parse_args()
    try:
        package(build=args.build, replace=args.replace)
    except Exception as error:
        failure = {'schema': 'LOCAL_COLD_VERIFIED_REVIEW_PACKAGE_V1', 'status': 'FAILED_CLOSED_PACKAGE_NOT_ACCEPTED',
                   'error': str(error), 'type': type(error).__name__,
                   'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                   'package_file_present_after_failure': ZIP.exists(), 'cross_computer_relocation_tested': False}
        if args.build:
            RESULT.write_bytes(json_bytes(failure))
        print(json.dumps(failure, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(2)
