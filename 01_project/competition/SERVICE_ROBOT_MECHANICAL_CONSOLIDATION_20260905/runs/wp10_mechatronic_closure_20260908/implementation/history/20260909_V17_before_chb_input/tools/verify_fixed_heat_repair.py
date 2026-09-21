from pathlib import Path
import json,subprocess,sys
A=Path(__file__).resolve().parents[1];cad='F:/codex_skill/AgentSkills/codex-skills/cad/scripts'
commands=[]
for stem in ['upper_deck_relocated','propulsion_data_route','fixed_heat_bay']:
    commands.append((stem+'_refs',[cad+'/inspect','refs','mechanical/'+stem+'.step','--facts','--planes','--positioning']))
    args=[cad+'/inspect','validate','mechanical/'+stem+'.step']
    if stem=='fixed_heat_bay':args+=['--skip-self-intersection']
    commands.append((stem+'_bounded_validate',args))
    commands.append((stem+'_snapshot',[cad+'/snapshot','--job',str(A/'review'/f'{stem}_snapshot.json')]))
for state in ['parking','released']:commands.append((state+'_interfaces',['tools/check_fixed_heat_interfaces.py',state]))
out=[]
for name,args in commands:
    r=subprocess.run([sys.executable,'-B','-X','utf8',*args],cwd=A,capture_output=True,text=True,encoding='utf-8',errors='replace')
    (A/'logs'/f'fixed_heat_repair_{name}.stdout.log').write_text(r.stdout,encoding='utf-8')
    (A/'logs'/f'fixed_heat_repair_{name}.stderr.log').write_text(r.stderr,encoding='utf-8')
    out.append(dict(name=name,returncode=r.returncode,args=args))
    (A/'results/FIXED_HEAT_REPAIR_SEQUENCE.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(name,r.returncode,flush=True)
    if r.returncode:break
assert len(out)==len(commands) and all(r['returncode']==0 for r in out),out
