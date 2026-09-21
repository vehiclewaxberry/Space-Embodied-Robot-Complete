"""Read-only recheck of the sealed immediate parent; does not award design credit."""
import csv, hashlib, json
from datetime import datetime, timezone
from pathlib import Path

C = Path(__file__).resolve().parents[1]
N = C.parent / 'reuse_closure'
manifest = N / 'results' / 'OUTPUT_SHA256.csv'
def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()
rows = list(csv.DictReader(manifest.open(encoding='utf-8-sig', newline='')))
checks = []
for row in rows:
    p = N / row['path']
    actual = sha(p) if p.is_file() else None
    checks.append({'path': row['path'], 'expected': row['sha256'], 'actual': actual,
                   'pass': actual == row['sha256']})
ancestor_checks = []
for ancestor in [C.parent, C.parent/'functional_closure']:
    ancestor_manifest=ancestor/'results/OUTPUT_SHA256.csv'
    for row in csv.DictReader(ancestor_manifest.open(encoding='utf-8-sig',newline='')):
        path=ancestor/row['path']
        actual=sha(path) if path.is_file() else None
        ancestor_checks.append({'path':str(path),'expected':row['sha256'],'actual':actual,'pass':actual==row['sha256']})
result = {'status': 'PASS' if all(r['pass'] for r in checks+ancestor_checks) else 'FAIL',
          'utc': datetime.now(timezone.utc).isoformat(), 'parent': str(N),
          'manifest_sha256': sha(manifest), 'checked_files': len(checks),
          'ancestor_published_files_checked':len(ancestor_checks),
          'parent_mutations_by_this_tool': 0, 'checks': checks,'ancestor_checks':ancestor_checks}
(C/'results'/'PARENT_PRESERVATION.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['checks','ancestor_checks']}))
raise SystemExit(0 if result['status'] == 'PASS' else 1)
