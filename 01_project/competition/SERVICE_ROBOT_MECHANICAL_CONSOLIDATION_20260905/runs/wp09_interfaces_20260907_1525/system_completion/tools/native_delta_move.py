"""Physical short-root relocation of the owned CAD directory with exact hashes."""
from pathlib import Path
import argparse,json,hashlib,os,datetime
import psutil
C=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('direction',choices=['forward','return']);a=ap.parse_args()
original=(C/'cad').resolve();moved=(C/'d').resolve()
assert original.parent==moved.parent==C.resolve() and original!=moved
assert not [p.info for p in psutil.process_iter(['name']) if (p.info['name'] or '').casefold()=='sldworks.exe'],'Do not move open CAD files'
src,dst=(original,moved) if a.direction=='forward' else (moved,original)
assert src.is_dir() and not dst.exists()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
files={str(p.relative_to(src)):sha(p) for p in src.rglob('*') if p.is_file()}
receipt=C/'results/NATIVE_DELTA_RELOCATION.json'
if a.direction=='forward':
 assert not receipt.exists()
 for state in ('service','parking','released'):
  q=json.loads((C/f'results/NATIVE_DELTA_COLD_{state}.json').read_text());assert q['status']=='PASS_COLD_NATIVE_DELTA_IDENTITIES_TRANSFORMS_LOCAL_DEPENDENCIES'
 r=dict(original_root=str(original),moved_root=str(moved),file_sha256_before=files,events=[])
else:
 r=json.loads(receipt.read_text());assert files==r['file_sha256_before']
 for state in ('service','parking','released'):
  q=json.loads((C/f'results/NATIVE_DELTA_COLD_relocated_{state}.json').read_text());assert q['status']=='PASS_COLD_NATIVE_DELTA_IDENTITIES_TRANSFORMS_LOCAL_DEPENDENCIES' and q['original_root_absent_during_cold_open']
os.rename(src,dst)
assert not src.exists() and {str(p.relative_to(dst)):sha(p) for p in dst.rglob('*') if p.is_file()}==files
r['events'].append(dict(direction=a.direction,utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source=str(src),destination=str(dst),source_absent=True,all_files_byte_unchanged=True,file_count=len(files)))
r['status']='MOVED_FOR_COLD_TEST' if a.direction=='forward' else 'PASS_PHYSICAL_MOVE_COLD_READ_RETURN_ALL_BYTES_UNCHANGED'
receipt.write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in r.items() if k!='file_sha256_before'}))
