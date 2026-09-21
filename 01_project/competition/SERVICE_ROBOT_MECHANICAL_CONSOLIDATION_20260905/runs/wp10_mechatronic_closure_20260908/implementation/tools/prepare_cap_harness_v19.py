"""Preserve the sealed V18 candidate before the next physical wiring delta."""
from pathlib import Path
import hashlib,json,shutil,datetime
A=Path(__file__).resolve().parents[1]
H=A/'history/20260909_V18_before_cap_harness'
assert not H.exists(), 'Existing archive must not be overwritten'
H.mkdir(parents=True)
rows=[]
for folder in ['ecad','power','results','tools','mechanical','docs/hardware']:
 for p in sorted((A/folder).rglob('*')):
  if not p.is_file() or '__pycache__' in p.parts:continue
  if folder=='mechanical' and len(p.relative_to(A/folder).parts)>1:continue
  rel=p.relative_to(A);q=H/rel;q.parent.mkdir(parents=True,exist_ok=True)
  shutil.copy2(p,q);rows.append(dict(path=rel.as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
for name in ['README.md','REVIEW.html','SYSTEM_CLOSURE_MATRIX.csv','WP10_IMPLEMENTATION_DELTA.zip']:
 p=A/name;q=H/name;shutil.copy2(p,q)
 digest=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(2**20),b''):digest.update(block)
 rows.append(dict(path=name,bytes=p.stat().st_size,sha256=digest.hexdigest()))
(H/'ARCHIVE_SHA256.json').write_text(json.dumps(dict(time=datetime.datetime.now().astimezone().isoformat(),files=rows),indent=2))
print(json.dumps(dict(archived=len(rows),bytes=sum(r['bytes'] for r in rows))))
