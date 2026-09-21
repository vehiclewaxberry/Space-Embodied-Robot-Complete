from pathlib import Path
import hashlib,json,shutil
A=Path(__file__).resolve().parents[1];C=A/'coupled_closure';H=A/'history/20260910_V30_before_lugs'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
c=json.loads((C/'CANDIDATE_V29.json').read_text());assert all(sha(Path(p))==h for p,h in c['source_lock'].items())
if not H.exists():
 H.mkdir();rows=[]
 for name in ['CURRENT_WORKING_CANDIDATE.json','README.md','coupled_closure/CANDIDATE_V29.json','power/SELECTED_BOM.csv']:
  p=A/name;dst=H/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst);rows.append(dict(path=name,sha256=sha(p)))
 (H/'SOURCE_SNAPSHOT.json').write_text(json.dumps(rows,indent=2))
lock=dict(json.loads((C/'TERMINAL_GEOMETRY_INPUTS_V29.json').read_text())['source_lock'])
for p in [C/'main_input_terminals_v29.step.py',C/'TERMINAL_GEOMETRY_INPUTS_V29.json',C/'LUG_OEM_INSPECTION_V30.json',C/'LUG_HARDWARE_INSPECTION_V30.json',*list((A/'sources/lugs_v30').glob('*.stp')),*list((A/'sources/lugs_v30').glob('*.step')),*list((A/'sources/lugs_v30').glob('*.pdf'))]:lock[p.relative_to(A).as_posix()]=sha(p)
(C/'LUG_SOURCE_LOCK_V30.json').write_text(json.dumps(lock,indent=2));print('V29 59 locks valid; V30 local inputs locked',len(lock))
