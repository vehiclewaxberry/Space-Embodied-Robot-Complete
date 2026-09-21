"""After owned memory guard: full new/modified validation; background self-test excluded explicitly."""
from pathlib import Path
import subprocess,sys,json
A=Path(__file__).resolve().parents[1];CAD=Path('F:/codex_skill/AgentSkills/codex-skills/cad/scripts')
target='mechanical/input_cap_integration.step.py';outputs=[]
for stem,args in [('NEW30_FULL',['validate',target,'--refs',','.join('o1.'+str(i) for i in range(1,31))]),('CONTEXT_NO_SELF',['validate',target,'--skip-self-intersection'])]:
 q=subprocess.run([sys.executable,'-B','-X','utf8',str(CAD/'inspect'),*args],cwd=A,capture_output=True,text=True,encoding='utf-8');p='results/INPUT_CAP_'+stem+'_VALIDATE.json';(A/p).write_text(q.stdout,encoding='utf-8');assert q.returncode==0,q.stderr;d=json.loads(q.stdout);assert d['ok'],d;outputs.append(dict(output=p,self_intersection_included=stem=='NEW30_FULL'));print(stem+' passed',flush=True)
q=subprocess.run([sys.executable,'-B','-X','utf8',str(CAD/'snapshot'),'--input',target,'--output','review/input_cap_integration.png','--camera=135:-25','--hide','o1.1','--hide','o1.32','--hide','o1.37','--width','1200','--height','900','--json'],cwd=A,capture_output=True,text=True,encoding='utf-8');(A/'results/INPUT_CAP_INTEGRATION_SNAPSHOT.json').write_text(q.stdout,encoding='utf-8');assert q.returncode==0,q.stderr
print(q.stdout,flush=True)
(A/'results/INPUT_CAP_VIEW_VALIDATION.json').write_text(json.dumps(dict(detail_full_validation='results/INPUT_CAP_DETAIL_VALIDATE.json',context_validations=outputs,original_full_context_test='logs/native_delta_input_cap_validation.run.json',original_full_context_status='COMBINED_WORKING_SET_GUARD',full_background_self_intersection_complete=False,context_snapshot_hidden_refs={'o1.1':'upper deck','o1.32':'radiator','o1.37':'lower deck'},hidden_for_visibility_only=True),indent=2),encoding='utf-8')
