"""Create a preserved-parent working revision for STOP output engineering."""
from pathlib import Path
import shutil,json,hashlib
A=Path(__file__).resolve().parents[1];P=A/'ecad/revisions/v35';D=P.parent/'v36';R=A/'results/stop_v36'
assert not D.exists(), 'Do not overwrite an existing working revision'
parent=json.loads((A/'coupled_closure/CANDIDATE_V35.json').read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert all(sha(p)==h for p,h in parent['source_lock'].items())
shutil.copytree(P,D);R.mkdir(parents=True,exist_ok=True);(R/'sources').mkdir(exist_ok=True)
lock={str(p):sha(p) for p in P.rglob('*') if p.is_file()}
(R/'PARENT_SOURCE_LOCK.json').write_text(json.dumps(lock,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(working_source=str(D),parent_files=len(lock),active_revision_unchanged='V35')))
