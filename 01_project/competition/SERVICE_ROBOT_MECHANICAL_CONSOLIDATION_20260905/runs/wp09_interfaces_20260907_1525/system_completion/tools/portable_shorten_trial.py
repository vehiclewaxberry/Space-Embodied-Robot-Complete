"""Preserve all bytes while moving the owned trial package below MAX_PATH."""
from pathlib import Path
import psutil,json,hashlib
C=Path(__file__).resolve().parents[1];base=(C/'mechanical/portable').resolve()
src=(base/'relocation_trial/package').resolve();dst=(base/'moved').resolve()
assert src.is_relative_to(base) and dst.is_relative_to(base) and src.is_dir() and not dst.exists()
assert not (base/'package').exists()
assert not any((p.info.get('name') or '').lower()=='sldworks.exe' for p in psutil.process_iter(['name']))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
before={p.name:sha(p) for p in src.iterdir() if p.is_file()}
old_max=max(len(str(p)) for p in src.iterdir() if p.is_file())
src.rename(dst)
after={p.name:sha(p) for p in dst.iterdir() if p.is_file()};assert before==after
new_max=max(len(str(p)) for p in dst.iterdir() if p.is_file());assert new_max<250
r={'status':'PASS_OWNED_TRIAL_MOVE_BYTES_UNCHANGED','reason':'Relocation trial native part paths reached 261 characters and OpenDoc6 reported missing references; shorten physical root within owned scope',
   'source':str(src),'destination':str(dst),'old_max_path_characters':old_max,'new_max_path_characters':new_max,
   'original_package_absent':not (base/'package').exists(),'previous_trial_absent':not src.exists(),'file_hashes':after}
out=C/'results/PORTABLE_MOVE_SHORT_PATH.json';assert not out.exists();out.write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in r.items() if k!='file_hashes'}))
