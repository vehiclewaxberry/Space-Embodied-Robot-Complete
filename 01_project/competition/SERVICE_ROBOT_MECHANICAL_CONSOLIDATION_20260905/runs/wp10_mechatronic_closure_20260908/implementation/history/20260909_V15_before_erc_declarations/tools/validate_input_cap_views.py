from pathlib import Path
import subprocess,sys,json
A=Path(__file__).resolve().parents[1];CAD=Path('F:/codex_skill/AgentSkills/codex-skills/cad/scripts');results=[]
for name in ['detail','integration']:
 target='mechanical/input_cap_'+name+'.step.py'
 for operation,args in [('refs',['refs',target,'--facts','--planes','--positioning']),('validate',['validate',target])]:
  q=subprocess.run([sys.executable,'-B','-X','utf8',str(CAD/'inspect'),*args],cwd=A,capture_output=True,text=True,encoding='utf-8');p='results/INPUT_CAP_'+name.upper()+'_'+operation.upper()+'.json';(A/p).write_text(q.stdout,encoding='utf-8');assert q.returncode==0,q.stderr;results.append(dict(output=p,returncode=q.returncode))
 q=subprocess.run([sys.executable,'-B','-X','utf8',str(CAD/'snapshot'),'--input',target,'--output','review/input_cap_'+name+'.png','--camera=135:-25','--width','1200','--height','900','--json'],cwd=A,capture_output=True,text=True,encoding='utf-8');p='results/INPUT_CAP_'+name.upper()+'_SNAPSHOT.json';(A/p).write_text(q.stdout,encoding='utf-8');assert q.returncode==0,q.stderr;results.append(dict(output=p,returncode=q.returncode));print(q.stdout,flush=True)
(A/'results/INPUT_CAP_VIEW_VALIDATION.json').write_text(json.dumps(dict(commands=results,visual_inspection_completed=False),indent=2),encoding='utf-8')
