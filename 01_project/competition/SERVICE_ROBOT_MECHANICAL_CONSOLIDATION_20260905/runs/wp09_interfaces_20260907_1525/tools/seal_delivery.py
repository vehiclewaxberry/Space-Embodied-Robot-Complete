"""Seal the bounded delivery after all jobs, visuals and document updates finish."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,csv,re
R=Path(__file__).resolve().parents[1]
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
status=json.loads((R/'results/DELIVERY_STATUS.json').read_text());assert status['status'].startswith('THREE_NATIVE_FIXED_POSES')
for state,row in status['native_states'].items():
    assert sha(row['native']['path'])==row['native']['sha256']
    assert sha(row['execution_receipt']['path'])==row['execution_receipt']['sha256']
for row in status['evidence_links']:assert sha(row['path'])==row['sha256']
frozen=json.loads((R/'inputs/INTEGRATION_HARNESS_CONTRACT_V6.json').read_text())['source_inputs']
for p,h in frozen.items():assert sha(p)==h
links=[]
for p in [R/'README.md',*sorted((R/'docs').glob('*.md'))]:
    for raw in re.findall(r'\]\((<[^>]+>|[^)]+)\)',p.read_text(encoding='utf-8')):
        v=raw.strip('<>')
        if v.startswith(('http:','https:','#','mailto:','app:','codex:')):continue
        v=v.split('#',1)[0]
        if not v:continue
        q=Path(v);q=q if q.is_absolute() else p.parent/q
        links.append(dict(document=str(p),target=str(q.resolve()),exists=q.exists()))
missing=[x for x in links if not x['exists']];assert not missing,missing
exclusions={'results/OUTPUT_SHA256.csv','results/FINAL_INTEGRITY.json'}
files=[]
for p in sorted(R.rglob('*')):
    if not p.is_file():continue
    rel=p.relative_to(R).as_posix()
    if rel in exclusions or any(k in p.parts for k in ['__pycache__','__cadgen__']) or rel.startswith('native/work/') or p.name.startswith('~$'):continue
    files.append(dict(path=rel,bytes=p.stat().st_size,sha256=sha(p)))
with (R/'results/OUTPUT_SHA256.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['path','bytes','sha256']);w.writeheader();w.writerows(files)
for row in files:assert sha(R/row['path'])==row['sha256']
report=dict(status='PASS_DELIVERY_FILES_BINDINGS_AND_FROZEN_INPUTS',utc=datetime.now(timezone.utc).isoformat(),output_file_count=len(files),output_manifest_sha256=sha(R/'results/OUTPUT_SHA256.csv'),frozen_inputs_checked=len(frozen),local_links_checked=len(links),missing_local_links=[],output_hashes_rechecked=True,excluded=['self-referential seal/manifest','native/work task scratch','SolidWorks lock files','reproducible CAD viewer caches and Python bytecode'],engineering_release_credit=False)
(R/'results/FINAL_INTEGRITY.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
