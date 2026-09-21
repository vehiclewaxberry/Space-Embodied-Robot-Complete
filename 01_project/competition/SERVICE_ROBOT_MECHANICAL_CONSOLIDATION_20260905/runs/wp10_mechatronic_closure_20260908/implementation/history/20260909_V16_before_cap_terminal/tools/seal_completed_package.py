"""Seal after the publishing guard has closed its log handles.

Run directly after all V16 generation and publishing finishes. Do not wrap
this I/O-only finalizer in a guard whose live output is inside the package.
All source generation/checking is already complete; no CAD/COM is loaded.
"""
from pathlib import Path
import csv
import hashlib
import json
import zipfile

A=Path(__file__).resolve().parents[1]
guard=json.loads((A/'logs/native_delta_cap_binding_v16.run.json').read_text())
assert guard['status']=='COMPLETED' and guard['returncode']==0
review=json.loads((A/'results/INPUT_PASSIVE_READONLY_REVIEW.json').read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert all(sha(A/p)==v for p,v in review['reviewed_files'].items())
mechanical_review=json.loads((A/'results/INPUT_CAP_MOUNT_READONLY_REVIEW.json').read_text())
assert all(sha(A/p)==v for p,v in mechanical_review['reviewed_files'].items())
assert json.loads((A/'results/DELIVERY_DECISION.json').read_text())['revision']=='V16_MCP_CONDITIONAL_ERC_DECLARATIONS'
integration=json.loads((A/'results/ERC_REVISION_INTEGRATION.json').read_text())
assert all(sha(A/p)==h for p,h in integration['evidence'].items())
for memory_name in ['INPUT_PASSIVE_MEMORY_RECOVERY.json','INPUT_MOUNT_MEMORY_RECOVERY.json','INPUT_CAP_VALIDATION_MEMORY_RECOVERY.json']:
    memory_file=A/'results'/memory_name
    memory=json.loads(memory_file.read_text())
    for row in memory['rows']:row.pop('service_command',None)
    memory['command_lines_omitted_from_delivery']=True
    memory_file.write_text(json.dumps(memory,indent=2),encoding='utf-8')
files=sorted(p for p in A.rglob('*') if p.is_file() and not {'history','__pycache__'}.intersection(p.relative_to(A).parts) and p.name not in ['OUTPUT_SHA256.csv','WP10_IMPLEMENTATION_DELTA.zip'])
rows=[dict(path=p.relative_to(A).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in files]
manifest=A/'results/OUTPUT_SHA256.csv'
with manifest.open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=['path','bytes','sha256']);w.writeheader();w.writerows(rows)
temporary=(A.parent/'logs/wp10_input_cap_final_package.tmp.zip').resolve()
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
