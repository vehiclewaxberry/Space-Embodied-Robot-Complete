"""Inventory stable run files; caches, locks and temporary work assemblies excluded."""
from pathlib import Path
import csv,hashlib,json,datetime
R=Path(__file__).resolve().parents[1]
out=R/'DELIVERY_FILES_SHA256.csv';receipt=R/'results/DELIVERY_HASH_MANIFEST.json'
assert not out.exists() and not receipt.exists()
assert (R/'README.md').is_file() and (R/'results/DELIVERY_STATUS.json').is_file()
rows=[]
for path in sorted(R.rglob('*')):
    if not path.is_file():continue
    relative=path.relative_to(R)
    if any(x in {'__pycache__','__cadgen__'} for x in relative.parts) or path.name.startswith('~$') or relative.as_posix().startswith('native/work/'):continue
    if path in (out,receipt):continue
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    rows.append(dict(relative_path=relative.as_posix(),bytes=path.stat().st_size,sha256=digest.hexdigest()))
with out.open('w',encoding='utf-8-sig',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=['relative_path','bytes','sha256']);writer.writeheader();writer.writerows(rows)
data=dict(schema='WP07_DELIVERY_FILE_HASHES',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
          file_count=len(rows),total_bytes=sum(x['bytes'] for x in rows),manifest_path=str(out),manifest_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),
          excluded=['__cadgen__ render caches','__pycache__','~$ application lock files','native/work temporary assemblies','this receipt and hash manifest'],
          linked_native_dependencies_outside_run='Bound separately by INTEGRATION_MANIFEST and native validation receipts; not copied into this directory',
          standalone_pack_and_go=False,engineering_release=False)
receipt.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(data,ensure_ascii=False))
