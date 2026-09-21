"""Repair publication-metadata typo, preserving the first archive and source locks."""
from pathlib import Path
import json,csv,hashlib,zipfile
A=Path(__file__).resolve().parents[1];C=A/'coupled_closure'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
mf=C/'SHA256_V29.csv'
with mf.open(encoding='utf-8') as f:rows=list(csv.DictReader(f))
changed=[]
for r in rows:
 p=A/r['file']
 if sha(p)!=r['sha256']:
  assert r['file']=='tools/publish_terminals_v29.py',r['file'];changed.append(r['file']);r['sha256']=sha(p);r['bytes']=p.stat().st_size
assert changed==['tools/publish_terminals_v29.py']
p=Path(__file__);rows.append(dict(file=p.relative_to(A).as_posix(),sha256=sha(p),bytes=p.stat().st_size))
with mf.open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=['file','sha256','bytes']);w.writeheader();w.writerows(sorted(rows,key=lambda r:r['file']))
dest=C/'WP10_V29_TERMINAL_DELTA.zip';first=C/'WP10_V29_TERMINAL_DELTA_pre_finalize.zip';assert dest.resolve().is_relative_to(C.resolve()) and first.resolve().is_relative_to(C.resolve()) and not first.exists();dest.rename(first)
with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for r in rows:z.write(A/r['file'],r['file'])
 z.write(mf,mf.relative_to(A).as_posix())
with zipfile.ZipFile(dest) as z:
 assert z.testzip() is None
 for r in rows:assert hashlib.sha256(z.read(r['file'])).hexdigest()==r['sha256']
out=dict(file_count=len(rows)+1,archive_bytes=dest.stat().st_size,archive_sha256=sha(dest),CRC_pass=True,all_manifest_hashes_pass=True,requires_existing_WP10_baseline=True,publication_metadata_typo_fixed=True,first_archive_sha256=sha(first),changed_design_sources=[])
(C/'DELIVERY_PACKAGE_CHECK_V29.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
