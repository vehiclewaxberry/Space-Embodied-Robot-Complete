from pathlib import Path
import json,subprocess,sys
A=Path(__file__).resolve().parents[1];cad='F:/codex_skill/AgentSkills/codex-skills/cad/scripts'
commands=[('label_rebuild',[cad+'/gen','mechanical/brake_tim.step.py','mechanical/brake_resistor_installation.step.py','--write','--json']),
          ('OEM_datums',[str(A/'tools/probe_brake_oem.py')]),
          ('contact_check',[str(A/'tools/check_brake_geometry.py')])]
for stem,views in [('brake_resistor_installation',['iso','top']),('brake_carrier',['top']),('brake_tim',['iso'])]:
    job=dict(input='mechanical/'+stem+'.step.py',mode='view',outputs=[dict(path=f'review/{stem}_{v}.png',camera=v) for v in views],render=dict(viewLabels=True,padding=.12,sizeProfile='diagnostic'))
    jp=A/'review'/f'{stem}_snapshot.json';jp.write_text(json.dumps(job),encoding='utf-8')
    commands.append((stem+'_snapshot',[cad+'/snapshot','--job',str(jp)]))
out=[]
for name,args in commands:
    r=subprocess.run([sys.executable,'-B','-X','utf8',*args],cwd=A,capture_output=True,text=True,encoding='utf-8',errors='replace')
    (A/'logs'/f'brake_final_{name}.stdout.log').write_text(r.stdout,encoding='utf-8')
    (A/'logs'/f'brake_final_{name}.stderr.log').write_text(r.stderr,encoding='utf-8')
    out.append(dict(name=name,returncode=r.returncode));print(name,r.returncode,flush=True)
    if r.returncode:break
(A/'results/BRAKE_FINAL_GEOMETRY_SEQUENCE.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
assert len(out)==len(commands) and all(r['returncode']==0 for r in out),out
