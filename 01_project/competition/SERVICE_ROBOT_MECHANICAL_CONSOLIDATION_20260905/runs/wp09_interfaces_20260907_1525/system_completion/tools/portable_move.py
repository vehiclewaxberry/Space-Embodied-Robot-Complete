"""Move only this task's native package between two verified in-scope roots."""
from pathlib import Path
import sys,json,argparse,hashlib,time
import psutil
C=Path(__file__).resolve().parents[1];base=(C/'mechanical/portable').resolve()
ap=argparse.ArgumentParser();ap.add_argument('direction',choices=['forward','return']);a=ap.parse_args()
src=base/('package' if a.direction=='forward' else 'moved')
dst=base/('relocation_trial/package' if a.direction=='forward' else 'package')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert src.resolve().is_relative_to(base) and dst.resolve().is_relative_to(base)
assert src.is_dir() and not dst.exists()
need=C/'results'/('PORTABLE_COLD_PRIMARY_V2.json' if a.direction=='forward' else 'PORTABLE_COLD_RELOCATED_V2.json')
j=json.loads(need.read_text());assert j['status']=='PASS_ALL_THREE_COLD_PORTABLE_STATES'
assert not any((p.info.get('name') or '').lower()=='sldworks.exe' for p in psutil.process_iter(['name'])),'SW must have exited before directory relocation'
before={p.relative_to(src).as_posix():sha(p) for p in src.rglob('*') if p.is_file()}
dst.parent.mkdir(parents=True,exist_ok=True)
src.rename(dst)
assert not src.exists()
after={p.relative_to(dst).as_posix():sha(p) for p in dst.rglob('*') if p.is_file()};assert before==after
out=C/'results'/('PORTABLE_MOVE_'+a.direction.upper()+'.json');assert not out.exists()
result={'status':'PASS_IN_SCOPE_NATIVE_DIRECTORY_MOVE','source':str(src),'destination':str(dst),
 'source_absent_after':not src.exists(),'file_count':len(after),'unchanged_file_hashes':after,'prerequisite':str(need),'prerequisite_sha256':sha(need),
 'operation':'Path.rename, same filesystem; resolved source and destination verified within current portable directory; no deletion'}
out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'status':result['status'],'files':len(after),'destination':str(dst)}))
