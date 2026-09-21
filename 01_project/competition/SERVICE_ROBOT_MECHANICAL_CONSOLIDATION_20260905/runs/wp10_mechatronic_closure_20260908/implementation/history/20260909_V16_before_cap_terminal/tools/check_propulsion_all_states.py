from pathlib import Path
import subprocess,sys,json
A=Path(__file__).resolve().parents[1]
for state in ['service','parking','released']:
    q=subprocess.run([sys.executable,'-B','-X','utf8',str(A/'tools/check_propulsion_reroute.py'),'--state',state],cwd=A,capture_output=True,text=True,encoding='utf-8',errors='replace')
    for ext,s in [('stdout',q.stdout),('stderr',q.stderr)]:(A/'logs'/f'battery_prop_check_{state}.{ext}.log').write_text(s,encoding='utf-8')
    print(state,q.returncode,flush=True);assert q.returncode==0,q.stderr[-2500:]
    r=json.loads((A/f'results/BATTERY_PROPULSION_ROUTE_SCREEN_{state.upper()}.json').read_text());print(r['status'],r['test_count'],flush=True)
