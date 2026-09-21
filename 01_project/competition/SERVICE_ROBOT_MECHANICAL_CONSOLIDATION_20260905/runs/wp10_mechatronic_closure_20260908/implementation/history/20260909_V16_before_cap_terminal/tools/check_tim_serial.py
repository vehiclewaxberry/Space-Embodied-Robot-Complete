from pathlib import Path
import subprocess,sys,json
A=Path(__file__).resolve().parents[1];cli='F:/codex_skill/AgentSkills/codex-skills/cad/scripts/inspect'
tasks=[('tim_facts',['refs','mechanical/converter_tim.step.py','--facts','--planes','--positioning']),('tim_validate',['validate','mechanical/converter_tim.step.py']),('tim_assembly_no_self',['validate','mechanical/converter_installation.step.py','--skip-self-intersection'])]
out=[]
for name,args in tasks:
 p=subprocess.run([sys.executable,'-B','-X','utf8',cli,*args],cwd=A,capture_output=True,text=True,encoding='utf-8',errors='replace')
 (A/'results'/f'{name}.json').write_text(p.stdout,encoding='utf-8');(A/'logs'/f'{name}.stderr.log').write_text(p.stderr,encoding='utf-8');out.append(dict(name=name,exit_code=p.returncode));print(name,p.returncode,flush=True)
 if p.returncode:break
(A/'results/TIM_CAD_CHECK_SEQUENCE.json').write_text(json.dumps(out,indent=2),encoding='utf-8');assert len(out)==len(tasks) and all(x['exit_code']==0 for x in out)
