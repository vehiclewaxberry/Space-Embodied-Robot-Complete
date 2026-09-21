"""Seal V18 after all native jobs and publication have finished.
Viewer HTTP logs live outside this package. No CAD/COM is loaded here.
"""
from pathlib import Path
import csv,hashlib,json,zipfile
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert json.loads((A/'results/DELIVERY_DECISION.json').read_text())['revision']=='V18_CHB_INPUT_TERMINAL_AND_MOUNT'
review=json.loads((A/'results/CHB_INPUT_READONLY_REVIEW_V18.json').read_text())
assert all(sha(A/p)==h for p,h in review['reviewed_files'].items())
integration=json.loads((A/'results/CHB_INPUT_REVISION_INTEGRATION_V18.json').read_text())
assert all(sha(A/p)==h for p,h in integration['evidence'].items())
assert not integration['whole_design_complete'] and not integration['goal_complete']
files=sorted(p for p in A.rglob('*') if p.is_file() and not {'history','__pycache__'}.intersection(p.relative_to(A).parts) and p.name not in ['OUTPUT_SHA256.csv','WP10_IMPLEMENTATION_DELTA.zip'])
rows=[dict(path=p.relative_to(A).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in files]
manifest=A/'results/OUTPUT_SHA256.csv'
with manifest.open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=['path','bytes','sha256']);w.writeheader();w.writerows(rows)
temporary=(A.parent/'logs/wp10_chb_input_final_package.tmp.zip').resolve()
assert temporary.is_relative_to(A.parent.resolve()) and temporary.parent.is_dir()
with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as z:
    for p in files+[manifest]:z.write(p,p.relative_to(A))
with zipfile.ZipFile(temporary) as z:
    assert z.testzip() is None
    for r in rows:
        assert sha(A/r['path'])==r['sha256'],r['path']
        assert hashlib.sha256(z.read(r['path'])).hexdigest()==r['sha256'],r['path']
temporary.replace(A/'WP10_IMPLEMENTATION_DELTA.zip')
print(json.dumps(dict(files=len(files),zip_entries=len(files)+1,bytes=(A/'WP10_IMPLEMENTATION_DELTA.zip').stat().st_size,closed_publisher_receipt_included=True)))
