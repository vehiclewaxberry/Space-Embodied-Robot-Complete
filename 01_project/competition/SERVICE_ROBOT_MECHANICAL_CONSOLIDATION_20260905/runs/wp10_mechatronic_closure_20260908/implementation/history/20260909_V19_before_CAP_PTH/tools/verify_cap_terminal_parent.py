"""Fresh read-only hash verification of the sealed 873 / 99 parent index."""
from pathlib import Path
import json,csv,hashlib
A=Path(__file__).resolve().parents[1];D=A.parent
rows=list(csv.DictReader((D/'results/OUTPUT_SHA256.csv').open(encoding='utf-8-sig')))
bad=[r['path'] for r in rows if not (D/r['path']).exists() or hashlib.sha256((D/r['path']).read_bytes()).hexdigest()!=r['sha256']]
assert not bad,bad
(A/'results/PARENT_INTEGRITY.json').write_text(json.dumps(dict(count=len(rows),mismatches=bad,all_parent_indexed_bytes_unchanged=True,current_verifier='tools/verify_cap_terminal_parent.py'),indent=2),encoding='utf-8')
print(json.dumps(dict(parent_files=len(rows),mismatches=bad)))
