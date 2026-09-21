"""Check all pinned historical native and neutral inputs without loading CAD."""
from pathlib import Path
import json,hashlib
OUT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):
    with open(p,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
sources={}
def add(p,h):
    k=str(Path(p).resolve());assert k not in sources or sources[k]==h
    sources[k]=h
c=read(OUT/'inputs/NATIVE_COPY_PLAN.json')
for q in c['parts']+c['assemblies']:add(q['source'],q['source_sha256'])
for q in read(OUT/'inputs/ALL_IMPORT_PLAN.json')['parts']:add(q['step_path'],q['source_sha256'])
n=read(OUT/'inputs/NEUTRAL_SOURCE_MAP.json')
groups=n['groups'];groups=groups.values() if isinstance(groups,dict) else groups
for g in groups:
    for q in g['rows']:add(q['step_path'],q['source_sha256'])
rows=[{'path':p,'expected_sha256':h,'actual_sha256':sha(p)} for p,h in sorted(sources.items())]
assert all(q['expected_sha256']==q['actual_sha256'] for q in rows)
r={'status':'PASS_ALL_PINNED_SOURCE_FILES_UNCHANGED','source_count':len(rows),'files':rows,
   'scope':'Pinned original native assets and geometry sources only; source bodies are not re-evaluated by this hash audit.'}
(OUT/'results/SOURCE_PRESERVATION.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
print(r['status'],len(rows))
