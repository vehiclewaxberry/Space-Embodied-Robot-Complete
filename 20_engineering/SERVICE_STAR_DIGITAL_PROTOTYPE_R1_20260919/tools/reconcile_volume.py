"""File-only, single-part measurement reconciliation; original failures remain.

This is deliberately not a general tolerance override. Only the pinned CHB500W
source can use a converged independent integral, with the unchanged comparator.
No native document, source plan or diagnostic is edited by this script.
"""
from pathlib import Path
import argparse
import copy
import datetime
import hashlib
import json
import math

OUT = Path(__file__).resolve().parents[1]
PART_ID = 'I_2883cdc18626958a'
SOURCE_SHA = '2883cdc18626958a2a4553b6a3a33dac8d3dbef24c44cffe61f1b74f95e6156b'
ORIGINAL_PLAN_SHA = 'f0d9ac5da8824dfd05455e1aeae92ec8f724d263a6b435ae167279b70b94432a'
ORIGINAL_NATIVE_SHA = '625584715647698e0a34349c1723c9e500b00e8cf1ecc4df20296b9dab3fccdc'
ORIGINAL_VOLUME = 44018.05271647816
RELATIVE_TOLERANCE = 1e-5
ABSOLUTE_FLOOR_MM3 = 1e-4
STATUS = 'PASS_SINGLE_PART_VOLUME_REFERENCE_RECONCILIATION_UNCHANGED_TOLERANCE'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def norm(path):
    return str(Path(path).resolve()).casefold()


def ref(path):
    return {'path': str(path), 'sha256': sha(path)}


def finite_positive(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def compare(value, reference):
    require(finite_positive(value) and finite_positive(reference), 'Invalid comparison volume')
    limit = max(ABSOLUTE_FLOOR_MM3, reference * RELATIVE_TOLERANCE)
    delta = abs(value - reference)
    return {'value_mm3': value, 'reference_mm3': reference, 'absolute_error_mm3': delta,
            'relative_error': delta / reference, 'unchanged_limit_mm3': limit, 'pass': delta <= limit}


def evidence(root=OUT, require_current_native=True):
    """Recompute all acceptance conditions from immutable file receipts."""
    root = Path(root)
    plan_path = root / 'inputs/ALL_IMPORT_PLAN.json'
    failed_path = root / 'results/IMPORT_16_231_hidden.json'
    diagnostic_path = root / 'results/NATIVE_VOLUME_DIAGNOSTIC_2883.json'
    independent_path = root / 'results/VOLUME_CROSSCHECK_2883.json'
    plan, failed, diagnostic, independent = [read(p) for p in (plan_path, failed_path, diagnostic_path, independent_path)]
    require(sha(plan_path) == ORIGINAL_PLAN_SHA, 'This single-part reconciliation is not authorized for a different source plan')
    jobs = [q for q in plan['parts'] if q['id'] == PART_ID]
    require(len(jobs) == 1, 'The fixed part ID must occur exactly once')
    job = jobs[0]
    require(job['source_sha256'] == SOURCE_SHA and sha(job['step_path']) == SOURCE_SHA, 'Pinned source mismatch')
    require(job['expected_volume_mm3'] == ORIGINAL_VOLUME, 'Original source-plan measurement changed')
    require(failed['status'] == 'FAILED', 'Original failed history must remain FAILED')
    failed_rows = [r for r in failed['parts'] if r['id'] == PART_ID]
    require(len(failed_rows) == 1, 'Missing or duplicate original failed row')
    row = failed_rows[0]
    require(row['volume_numeric_screen_pass'] is False, 'Original volume failure was rewritten')
    require(row['source_sha256'] == SOURCE_SHA and sha(row['source']) == SOURCE_SHA, 'Original import source pin mismatch')
    require(norm(row['target']) == norm(job['native_path']), 'Original native target mismatch')
    require(row['status'] == 'NATIVE_PART_SAVED_CLOSED_REOPENED_VERIFIED_AND_CLOSED', 'Original native cold-read missing')
    require(row['import_stage'] == 'COMPLETED', 'Original import incomplete')
    cold = row['part_cold_reopen']; facts = cold['facts']
    require(row['import_errors'] == cold['errors'] == row['external_reference_count'] == row['auxiliary_reference_count'] == 0,
            'Original import, cold-open or external-reference checks failed')
    require(facts['solid_count'] == job['expected_solids'] == 1 and facts['sheet_count'] == 0, 'Original native body counts mismatch')
    bbox_error = max(abs(facts['bounds_mm'][i][j] - job['expected_local_bbox_mm'][i][j]) for i in range(2) for j in range(3))
    require(bbox_error <= 1e-4, 'Original native bounds fail unchanged tolerance')
    require(not compare(facts['volume_mm3'], ORIGINAL_VOLUME)['pass'], 'Original discrepancy not reproduced')
    native_sha = row['native_save']['sha256']
    require(native_sha == ORIGINAL_NATIVE_SHA, 'This reconciliation is not for the originally diagnosed native file')
    require(diagnostic['source_sha256'] == SOURCE_SHA and diagnostic['native_sha256'] == native_sha,
            'Diagnostic source/native binding mismatch')
    require(norm(diagnostic['native_path']) == norm(job['native_path']), 'Diagnostic native target mismatch')
    if require_current_native:
        require(sha(job['native_path']) == native_sha, 'Native changed before reconciliation; material chain required later')
    require(sha(diagnostic['roundtrip_step']) == diagnostic['roundtrip_sha256'], 'Native roundtrip hash mismatch')
    require(diagnostic['export_api'][0] is True and diagnostic['export_api'][1] == 0, 'Native roundtrip export failed')
    require(diagnostic['native_facts']['solid_count'] == 1 and diagnostic['native_facts']['sheet_count'] == 0,
            'Diagnostic native body counts mismatch')
    require(independent['schema'] == 'OCP_VOLUME_CROSSCHECK_V1' and independent['part_id'] == PART_ID, 'Wrong independent audit')
    require(independent['source_sha256_before'] == independent['source_sha256_after'] == SOURCE_SHA,
            'Independent source hash mismatch')
    require(norm(independent['source_path']) == norm(job['step_path']), 'Independent source path mismatch')
    require(independent['all_import_plan_sha256'] == sha(plan_path), 'Independent source-plan hash mismatch')
    require(independent['baseline_reproduction']['plan_value_matches_exactly'] is True
            and independent['baseline_reproduction']['default_volume_mm3'] == ORIGINAL_VOLUME,
            'Independent review did not reproduce the original negative result')
    require(independent['unchanged_relative_volume_acceptance_tolerance'] == RELATIVE_TOLERANCE,
            'Independent audit changed the acceptance tolerance')
    binding = independent.get('native_diagnostic_binding', {})
    binding_path = Path(binding.get('path', 'MISSING'))
    if not binding_path.is_absolute():
        binding_path = root.parent.parent / binding_path
    require(norm(binding_path) == norm(diagnostic_path) and binding.get('sha256') == sha(diagnostic_path),
            'Independent audit is not bound to this native diagnostic')
    require(binding.get('native_sha256') == native_sha and norm(binding.get('native_path', '.')) == norm(job['native_path']),
            'Independent diagnostic native hash/path mismatch')
    require(binding.get('roundtrip_sha256') == diagnostic['roundtrip_sha256']
            and norm(binding.get('roundtrip_path', '.')) == norm(diagnostic['roundtrip_step']),
            'Independent audit roundtrip hash/path mismatch')
    require(binding.get('accuracy_results') == diagnostic['accuracy_results'], 'Independent native accuracy values changed')
    final = independent.get('final_assessment', {})
    require(final.get('volume_reference_correction_supported') is True, 'Independent final assessment still pending or negative')
    require(final.get('source_reference_converged') is True and final.get('native_roundtrip_converged') is True,
            'Independent convergence assessment incomplete')
    require(final.get('acceptance_relative_tolerance') == RELATIVE_TOLERANCE, 'Final tolerance mismatch')
    reference = final.get('source_reference_volume_mm3')
    require(finite_positive(reference), 'Final independent volume reference missing')
    series = independent['gauss_kronrod_series']
    fine = [r for r in series if r['eps'] <= 1e-7 and r['OnlyClosed'] is True]
    require(len(fine) >= 4 and {r['IsUseSpan'] for r in fine} == {True, False}, 'Both span modes and refinements are required')
    require(all(finite_positive(r['volume_mm3']) and 0 <= r['estimated_relative_error'] <= 1e-6 for r in fine),
            'Independent integral uncertainty consumes the original comparator margin')
    spread = max(r['volume_mm3'] for r in fine) - min(r['volume_mm3'] for r in fine)
    require(spread / reference <= 1e-6, 'Independent refined results do not converge within comparator margin')
    chosen = [r for r in fine if r['IsUseSpan'] is True and r['eps'] <= 1e-9 and r['volume_mm3'] == reference]
    require(chosen, 'Final reference not an actual refined source integral')
    require(independent['shape_valid'] is True and independent['solid_count'] == 1
            and not independent['invalid_face_indices'], 'Independent source geometry check failed')
    roundtrip = independent.get('roundtrip_checks', {})
    rt_facts = roundtrip.get('facts', {})
    require(rt_facts.get('valid') is True and rt_facts.get('solids') == 1 and rt_facts.get('all_shells_closed') is True
            and rt_facts.get('invalid_faces') == [], 'Independent native roundtrip body check failed')
    rt_box = rt_facts.get('optimal_bbox_mm', [])
    expected_box = [v for bound in job['expected_local_bbox_mm'] for v in bound]
    require(len(rt_box) == 6 and max(abs(a-b) for a, b in zip(rt_box, expected_box)) <= 1e-4,
            'Independent native roundtrip bounds fail unchanged tolerance')
    rt_fine = [r for r in roundtrip.get('gauss_kronrod_series', []) if r['eps'] <= 1e-7
               and r['OnlyClosed'] is True and r['IsUseSpan'] is True]
    require(len(rt_fine) >= 2 and all(finite_positive(r['volume_mm3']) and 0 <= r['estimated_relative_error'] <= 1e-6 for r in rt_fine),
            'Independent native roundtrip integral convergence missing')
    rt_reference = final.get('native_roundtrip_reference_volume_mm3')
    require(finite_positive(rt_reference) and any(r['eps'] <= 1e-9 and r['volume_mm3'] == rt_reference for r in rt_fine),
            'Native roundtrip reference is not a recorded refined integral')
    require((max(r['volume_mm3'] for r in rt_fine) - min(r['volume_mm3'] for r in rt_fine)) / rt_reference <= 1e-6,
            'Native roundtrip integral spread exceeds the comparator margin')
    maximum = [r for r in diagnostic['accuracy_results'] if r['accuracy'] == 2 and r['api_status'] == 0]
    require(len(maximum) == 1, 'Maximum-accuracy native diagnostic missing')
    comparisons = {'original_native_cold_read': compare(facts['volume_mm3'], reference),
                   'native_maximum_accuracy': compare(maximum[0]['volume_mm3'], reference),
                   'native_roundtrip': compare(final.get('native_roundtrip_reference_volume_mm3'), reference)}
    require(all(v['pass'] for v in comparisons.values()), 'One or more volumes fail the unchanged tolerance')
    return {'schema': 'NATIVE_VOLUME_REFERENCE_RECONCILIATION_V1', 'status': STATUS, 'part_id': PART_ID,
            'import_plan_sha256': sha(plan_path), 'interrupted_receipt': str(failed_path),
            'interrupted_receipt_sha256': sha(failed_path), 'source': ref(job['step_path']),
            'native_before_material': {'path': job['native_path'], 'sha256': native_sha},
            'native_diagnostic': ref(diagnostic_path), 'independent_volume_evidence': ref(independent_path),
            'native_roundtrip': ref(diagnostic['roundtrip_step']), 'parts': [copy.deepcopy(row)],
            'volume_reference_reconciliation': {'original_plan_expected_volume_mm3': ORIGINAL_VOLUME,
                'corrected_reference_volume_mm3': reference, 'reference_method': 'INDEPENDENT_SOURCE_GAUSS_KRONROD_WITH_CONVERGENCE_AND_NATIVE_ROUNDTRIP',
                'relative_tolerance': RELATIVE_TOLERANCE, 'absolute_floor_mm3': ABSOLUTE_FLOOR_MM3,
                'source_refinement_spread_mm3': spread, 'comparisons': comparisons,
                'native_bbox_error_mm': bbox_error, 'original_failure_preserved': True,
                'source_plan_unchanged': True, 'tolerance_relaxed': False, 'geometric_exact_equivalence_claimed': False},
            'scope': 'Source-volume measurement reconciliation for this exact part only. Reuses existing native cold-read evidence; no new COM read. Original failed row and plan remain unchanged.',
            'whole_design_complete': False, 'physical_material_assignment': False, 'software_default_mass_authoritative': False}


def validate_existing_receipt(path, root=OUT):
    """Recheck pinned evidence after materials; caller must validate native hash chain."""
    actual = read(path)
    expected = evidence(root, require_current_native=False)
    for key, value in expected.items():
        require(actual.get(key) == value, 'Reconciliation field differs from independently recomputed evidence: ' + key)
    return expected


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--check-only', action='store_true'); args = parser.parse_args()
    result = evidence()
    target = OUT / 'results/IMPORT_35_36_volume_reconciled.json'
    if not args.check_only:
        require(not target.exists(), 'Existing reconciliation receipt protected')
        result['generated_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({'status': result['status'], 'path': str(target), 'comparison': result['volume_reference_reconciliation']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
