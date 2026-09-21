"""Seal this child deliverable after review; keep failure history and immutable parents."""
import csv, hashlib, json, re
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import unquote,urlsplit
C=Path(__file__).resolve().parents[1]
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
assert read(C/'results/DELIVERY_STATUS.json')['whole_mechatronic_detailed_design_complete'] is False
parent=read(C/'results/PARENT_PRESERVATION.json')
assert parent['status']=='PASS'
links=[]
for p in [C/'README.md',C/'REVIEW.html',C/'mechanical/ASSEMBLY_DELTA_ZH.md']:
    content=p.read_text(encoding='utf-8')
    candidates=re.findall(r'\]\(([^)]+)\)',content) if p.suffix=='.md' else re.findall(r'(?:href|src)="([^"]+)"',content)
    for raw in candidates:
        if raw.startswith(('http:','https:','mailto:','#','data:')):continue
        target=(p.parent/unquote(urlsplit(raw).path.strip('<>'))).resolve()
        if target.name in ['FINAL_INTEGRITY.json','OUTPUT_SHA256.csv']:exists=True
        else:exists=target.is_file()
        links.append({'source':str(p.relative_to(C)),'target':str(target),'exists':exists})
assert all(r['exists'] for r in links),[r for r in links if not r['exists']]
excludes={'__pycache__','__cadgen__','runtime_config'}
special={'results/FINAL_INTEGRITY.json','results/OUTPUT_SHA256.csv','logs/review_server.stdout.log','logs/review_server.stderr.log'}
files=[]
for p in sorted(C.rglob('*')):
    if not p.is_file() or excludes.intersection(p.parts):continue
    rel=p.relative_to(C).as_posix()
    if rel in special or p.name.startswith('~$') or p.suffix=='.pyc':continue
    files.append({'path':rel,'bytes':p.stat().st_size,'sha256':sha(p)})
manifest=C/'results/OUTPUT_SHA256.csv'
with manifest.open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['path','bytes','sha256']);w.writeheader();w.writerows(files)
report={'status':'PASS_HASH_MANIFEST_LINKS_AND_IMMUTABLE_PARENT','utc':datetime.now(timezone.utc).isoformat(),'files_sealed':len(files),'manifest_sha256':sha(manifest),'parent_files_checked':parent['checked_files'],'entry_links_checked':len(links),'links':links,'exclusions':sorted(special|excludes),'engineering_completion_credit':False,'physical_execution_credit':False}
(C/'results/FINAL_INTEGRITY.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='links'},ensure_ascii=False))
