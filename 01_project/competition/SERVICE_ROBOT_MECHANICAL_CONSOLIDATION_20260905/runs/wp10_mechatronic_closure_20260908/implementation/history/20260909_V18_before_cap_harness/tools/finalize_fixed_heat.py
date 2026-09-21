from pathlib import Path
import json,subprocess,sys
A=Path(__file__).resolve().parents[1];cad='F:/codex_skill/AgentSkills/codex-skills/cad/scripts'
stems=['fixed_heat_wall_neg','fixed_heat_wall_pos','fixed_heat_installation','upper_deck_relocated','propulsion_power_route','propulsion_data_route','fixed_heat_bay']
commands=[('gen',[cad+'/gen',*['mechanical/'+s+'.step.py' for s in stems],'--write','--json']),
 ('contact',['tools/check_fixed_heat_geometry.py']),('source_instance_plan',['tools/prepare_fixed_heat_integration.py']),
 ('thermal',['tools/fixed_radiator_budget.py'])]
for stem in stems:
    commands.extend([(stem+'_refs',[cad+'/inspect','refs','mechanical/'+stem+'.step','--facts','--planes','--positioning']),
       (stem+'_validate',[cad+'/inspect','validate','mechanical/'+stem+'.step'])])
    job=dict(input='mechanical/'+stem+'.step.py',mode='view',outputs=[dict(path=f'review/{stem}_{v}.png',camera=v) for v in (['iso','top'] if stem=='fixed_heat_bay' else ['top'] if stem=='upper_deck_relocated' else ['iso'])],render=dict(viewLabels=True,padding=.12,sizeProfile='diagnostic'))
    jp=A/'review'/f'{stem}_snapshot.json';jp.write_text(json.dumps(job),encoding='utf-8')
    commands.append((stem+'_snapshot',[cad+'/snapshot','--job',str(jp)]))
out=[]
for name,args in commands:
    r=subprocess.run([sys.executable,'-B','-X','utf8',*args],cwd=A,capture_output=True,text=True,encoding='utf-8',errors='replace')
    (A/'logs'/f'fixed_heat_{name}.stdout.log').write_text(r.stdout,encoding='utf-8')
    (A/'logs'/f'fixed_heat_{name}.stderr.log').write_text(r.stderr,encoding='utf-8')
    out.append(dict(name=name,returncode=r.returncode));print(name,r.returncode,flush=True)
    if r.returncode:break
(A/'results/FIXED_HEAT_FINAL_SEQUENCE.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
assert len(out)==len(commands) and all(r['returncode']==0 for r in out),out
