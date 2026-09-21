"""Read-only delivery and active source verification, no EDA/CAD load."""
from pathlib import Path
import json,csv,hashlib
A=Path(__file__).resolve().parents[1];C=A/'coupled_closure'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
checks={};c=json.loads((C/'CANDIDATE_V29.json').read_text());checks['current_candidate_sources']=all(Path(p).exists() and sha(p)==h for p,h in c['source_lock'].items())
with (C/'SHA256_V29.csv').open(encoding='utf-8') as f:rows=list(csv.DictReader(f))
checks['all_delivered_files']=all((A/r['file']).exists() and sha(A/r['file'])==r['sha256'] for r in rows)
with (C/'SHA256.csv').open(encoding='utf-8-sig') as f:old=list(csv.DictReader(f))
checks['original_package_unchanged']=all(sha(C/r['file'])==r['sha256'] for r in old)
s=json.loads((C/'DELIVERY_STATUS_V29.json').read_text());checks['no_whole_release_credit']=not s['whole_design_complete'] and not s['manufacturing_release'] and not s['continuous_thermal_closed']
print(json.dumps(dict(passed=all(checks.values()),checks=checks,files=len(rows)),ensure_ascii=False));raise SystemExit(0 if all(checks.values()) else 1)
