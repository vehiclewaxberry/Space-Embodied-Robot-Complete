from pathlib import Path
import subprocess,sys,json
A=Path(__file__).resolve().parents[1];cli='F:/codex_skill/AgentSkills/codex-skills/cad/scripts/inspect'
tasks=[('brake_assembly_facts',['refs','mechanical/brake_resistor_installation.step.py','--facts','--planes','--positioning']),
       ('brake_carrier_validate',['validate','mechanical/brake_carrier.step.py']),
       ('brake_tim_validate',['validate','mechanical/brake_tim.step.py']),
       ('brake_assembly_validate',['validate','mechanical/brake_resistor_installation.step.py'])]
out=[]
for name,args in tasks:
    p=subprocess.run([sys.executable,'-B','-X','utf8',cli,*args],cwd=A,capture_output=True,text=True,encoding='utf-8',errors='replace')
    (A/'results'/f'{name}.json').write_text(p.stdout,encoding='utf-8')
    (A/'logs'/f'{name}.stderr.log').write_text(p.stderr,encoding='utf-8')
    out.append(dict(name=name,exit_code=p.returncode));print(name,p.returncode,flush=True)
    if p.returncode:break
(A/'results/BRAKE_CAD_CHECK_SEQUENCE.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
assert len(out)==len(tasks) and all(x['exit_code']==0 for x in out)
