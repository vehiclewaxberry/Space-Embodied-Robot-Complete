from pathlib import Path
import sys,json,subprocess
A=Path(__file__).resolve().parents[1]
for state in ['service','parking','released']:
    q=subprocess.run([sys.executable,'-B','-X','utf8',str(A/'tools/check_fixed_heat_interfaces.py'),state],capture_output=True,text=True,encoding='utf-8',errors='replace')
    for tag,s in [('stdout',q.stdout),('stderr',q.stderr)]:(A/'logs'/f'cold_path_{state}_interfaces.{tag}.log').write_text(s,encoding='utf-8')
    assert q.returncode==0,(state,q.stderr[-3000:])
    r=json.loads((A/f'results/FIXED_HEAT_{state.upper()}_INTERFACES.json').read_text())
    print(json.dumps(dict(state=state,pairs=len(r['exact_pairs']),positive=r['positive_volume_intersections'],unknown=r['unknown'])),flush=True)
    assert r['zero_positive_volume_intersections'] and r['complete_coverage']
