"""Preserve interrupted owned work, then reclaim only identified idle tool pages."""
from pathlib import Path
import json,hashlib,datetime,psutil,runpy
C=Path(__file__).resolve().parents[1]
assert not [p for p in psutil.process_iter(['name']) if p.info['name'].lower()=='sldworks.exe']
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S')
archive=C/'logs'/('native_delta_interrupted_v2_'+stamp);archive.mkdir()
rows=[]
for relative in ('results/NATIVE_DELTA_INTEGRATE_service.json','cad/W_service.SLDASM','cad/~$W_service.SLDASM'):
    old=(C/relative).resolve();assert old.is_relative_to(C.resolve())
    if not old.exists():continue
    new=(archive/old.name).resolve();assert new.is_relative_to(C.resolve()) and not new.exists()
    digest=hashlib.file_digest(old.open('rb'),'sha256').hexdigest()
    old.rename(new);assert hashlib.file_digest(new.open('rb'),'sha256').hexdigest()==digest
    rows.append({'old':str(old),'preserved':str(new),'sha256':digest})
r={'status':'OWNED_INTERRUPTED_V2_PRESERVED_NO_FINAL_NATIVE_CREDIT','rows':rows,'available_before_MiB':psutil.virtual_memory().available/2**20}
(C/'results'/('NATIVE_DELTA_RESUME_'+stamp+'.json')).write_text(json.dumps(r,indent=2),encoding='utf-8')
print(json.dumps(r))
# Scope checked from currently observed desktop Codex backend command; never kill.
backend=psutil.Process(8876)
assert backend.name().lower()=='codex.exe'
assert any('OpenAI\\Codex\\bin\\' in x for x in backend.cmdline()) and 'app-server' in backend.cmdline()
source=C/'tools/reclaim_idle_tool_working_sets.py'
code=source.read_text(encoding='utf-8');assert 'psutil.Process(30448)' in code
code=code.replace('psutil.Process(30448)','psutil.Process(8876)')
exec(compile(code,str(source),'exec'),{'__file__':str(source),'__name__':'__main__'})
