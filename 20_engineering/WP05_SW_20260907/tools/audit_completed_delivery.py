"""Apply the independent receipt checker to full and scoped actual assemblies."""
from pathlib import Path
import json
import check_native_delivery as checker
R = Path(__file__).resolve().parents[1]

def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def write(p, data):
    Path(p).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')

def main():
    mf_path = R / 'results/PARTS_SOURCE_MANIFEST_DEDUP.json'
    imports_path = R / 'results/NATIVE_IMPORTS.json'
    audit = checker.run_audit(mf_path, [imports_path],
        [R/'results'/('WP05_ROBOT_'+s+'_COLD.json') for s in ['SERVICE','PARKING','RELEASED']], R)
    write(R/'results/INDEPENDENT_NATIVE_DELIVERY_CHECK.json', audit)
    mf, imports = read(mf_path), read(imports_path)
    natives = {p['part_key']: p for p in imports['parts']}
    jobs_path = R / 'results/PLANNED_ASSEMBLY_JOBS.json'
    scoped = []
    for job in read(jobs_path)[3:]:
        receipt_path = R / 'results' / (job['name'] + '_COLD.json')
        rec = read(receipt_path)
        ids = set(job['ids'])
        expected = [r for r in mf['states'][job['state']]['instances'] if r['id'] in ids]
        a = checker.Audit()
        a.add('expected_scope_ids', {r['id'] for r in expected} == ids)
        checker.check_state_rows(expected, rec['components'], expected_count=len(ids), audit=a, state=job['name'])
        checker.check_file(a, 'native_assembly', rec['target'], rec['target_sha256'], R, '.sldasm')
        a.add('open_errors_and_warnings', rec['open_errors'] == 0 and rec['open_warnings'] == 0)
        actual = {r['id']: r for r in rec['components']}
        for row in expected:
            n, c = natives[row['part_key']], actual.get(row['id'], {})
            a.add('instance:'+row['id']+':native_body_count', c.get('resolved_solid_count') == n['facts']['solid_count'])
            a.add('instance:'+row['id']+':no_sheet_bodies', type(c.get('resolved_sheet_count')) is int and c['resolved_sheet_count'] == 0)
            a.add('instance:'+row['id']+':canonical_path', checker.norm(c.get('path','')) == checker.norm(n['target']))
        expected_paths = {checker.norm(natives[r['part_key']]['target']) for r in expected}
        actual_paths = {checker.norm(r['path']) for r in rec['dependencies']}
        a.add('dependency_set', actual_paths == expected_paths)
        for dep in rec['dependencies']:
            checker.check_file(a, 'actual_dependency', dep['path'], dep['sha256'], R, '.sldprt')
        scoped.append({'name': job['name'], 'expected_instances': len(expected),
            'inputs': [{'path': str(p), 'sha256': checker.sha256(p)} for p in [mf_path, imports_path, jobs_path, receipt_path]],
            **a.summary()})
    report = {'schema': 'WP05_SCOPED_NATIVE_RECEIPT_AUDIT_V1', 'results': scoped,
              'checker_sha256': checker.sha256(checker.__file__),
              'physical_assembly_completed': False, 'continuous_motion_verified': False,
              'manufacturing_release': False}
    write(R/'results/INDEPENDENT_SCOPED_ASSEMBLY_CHECK.json', report)
    print(json.dumps({'full': {'status': audit['status'], 'counts': audit['counts'],
        'diagnostic_counts': audit['diagnostic_counts'],
        'required_nonpasses': [r for r in audit['checks'] if r['required'] and r['status'] != 'PASS']},
        'scoped': [{'name': r['name'], 'status': r['status'], 'counts': r['counts']} for r in scoped]}, ensure_ascii=False))

if __name__ == '__main__':
    main()
