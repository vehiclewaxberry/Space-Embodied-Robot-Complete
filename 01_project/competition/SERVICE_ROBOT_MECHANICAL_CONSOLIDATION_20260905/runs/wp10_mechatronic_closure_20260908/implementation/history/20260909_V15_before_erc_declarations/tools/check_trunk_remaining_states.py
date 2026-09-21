"""Run the remaining fixed states serially under the enclosing memory guard."""
from pathlib import Path
import subprocess,sys,json
A=Path(__file__).resolve().parents[1]
for s in ['parking','released']:
    q=subprocess.run([sys.executable,'-B','-X','utf8','tools/check_trunk_supports.py','--state',s],cwd=A,capture_output=True,text=True,encoding='utf-8')
    for ext,t in [('stdout',q.stdout),('stderr',q.stderr)]:(A/f'logs/trunk_{s}.{ext}.log').write_text(t,encoding='utf-8')
    assert q.returncode==0,q.stderr
    r=json.loads((A/f'results/TRUNK_SUPPORT_SCREEN_{s.upper()}.json').read_text());assert r['status']=='TRUNK_SUPPORT_STATIC_GEOMETRY_CLEAR__MATERIAL_PRELOAD_AND_RELEASE_BRANCHES_OPEN';print(s,r['test_count'],len(r['required_contacts']),flush=True)
