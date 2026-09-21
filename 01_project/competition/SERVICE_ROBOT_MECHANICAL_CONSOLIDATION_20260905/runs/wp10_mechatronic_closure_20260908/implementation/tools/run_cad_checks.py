from pathlib import Path
import subprocess,sys,json
A=Path(__file__).resolve().parents[1];cli='F:/codex_skill/AgentSkills/codex-skills/cad/scripts/inspect'
tasks=[('plate_refs',['refs','mechanical/converter_carrier.step.py','--facts','--planes','--positioning']),('plate_validate',['validate','mechanical/converter_carrier.step.py']),('assembly_validate_no_self',['validate','mechanical/converter_installation.step.py','--skip-self-intersection']),('thermal_gap',['measure','mechanical/converter_installation.step.py','--from','#o1.1.f3','--to','#o1.2.f98','--axis','z'])]
out=[]
for name,args in tasks:
 p=subprocess.run([sys.executable,'-B','-X','utf8',cli,*args],cwd=A,capture_output=True,text=True,encoding='utf-8',errors='replace')
 (A/'results'/f'{name}.json').write_text(p.stdout,encoding='utf-8');(A/'logs'/f'{name}.stderr.log').write_text(p.stderr,encoding='utf-8');out.append(dict(name=name,exit_code=p.returncode))
 if p.returncode:break
(A/'results/CAD_CHECK_SEQUENCE.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out));assert all(x['exit_code']==0 for x in out) and len(out)==len(tasks)
