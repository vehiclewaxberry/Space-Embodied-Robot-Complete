"""Explicit guarded native build/inspection; never generates whole directories."""
from pathlib import Path
import json,hashlib,subprocess,sys,datetime
A=Path(__file__).resolve().parents[1];CAD=Path('F:/codex_skill/AgentSkills/codex-skills/cad/scripts')
phase=sys.argv[1]
STEMS=dict(lower='cap_harness_lower_retained_v21',plus='cap_harness_lace_plus_v21',minus='cap_harness_lace_minus_v21',assembly='cap_harness_retained_assembly_v21')
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def run(args):
 q=subprocess.run([sys.executable,'-B','-X','utf8',str(CAD/args[0]),*args[1:]],cwd=A,capture_output=True,text=True,encoding='utf-8')
 stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
 for key,value in [('stdout',q.stdout),('stderr',q.stderr)]:(A/f'logs/cap21_{phase}_{stamp}.{key}.log').write_text(value,encoding='utf-8')
 assert q.returncode==0,q.stderr
 return q.stdout
if phase in STEMS:
 source='mechanical/'+STEMS[phase]+'.step.py';output=source[:-3]
 files=[source,'mechanical/cap_harness_retention_common_v21.py','power/CAP_HARNESS_RETENTION_V21.json','tools/cap_retention_native_v21.py']
 if phase=='assembly':files+=['mechanical/CAP_HARNESS_RETAINED_PLAN_V21.json']
 inputs={p:sha(p) for p in files}
 print(run(['gen',source,'--write']),flush=True)
 assert all(sha(p)==h for p,h in inputs.items())
 receipt=dict(schema='WP10_CAP_RETENTION_GENERATION_V21',phase=phase,time_local=datetime.datetime.now().astimezone().isoformat(),inputs=inputs,output=output,output_sha256=sha(output),native_exit=0)
 (A/f'results/CAP_RETENTION_GENERATION_{phase.upper()}_V21.json').write_text(json.dumps(receipt,indent=2))
elif phase=='review':
 target='mechanical/cap_harness_retained_assembly_v21.step'
 out=dict(target=target,target_sha256=sha(target),self_intersection_skipped=True)
 for verb,args in [('refs',['refs',target,'--facts','--planes','--positioning']),('validate',['validate',target,'--skip-self-intersection'])]:
  v=json.loads(run(['inspect',*args]));assert v.get('ok',True);out[verb]=v
 (A/'results/CAP_RETENTION_CAD_REVIEW_V21.json').write_text(json.dumps(out,indent=2))
elif phase=='shot':
 target='mechanical/cap_harness_retained_assembly_v21.step';output='review/CAP_RETENTION_ASSEMBLY_V21.png'
 v=json.loads(run(['snapshot','--input',target,'--output',output,'--camera=135:-18','--width','1200','--height','900','--json']))
 assert v['ok'];actual=Path(v['outputs'][0]['path']).resolve()
 import shutil
 if actual!=(A/output).resolve():shutil.copyfile(actual,A/output)
 v.update(target=target,target_sha256=sha(target),published_image=output,published_sha256=sha(output))
 (A/'results/CAP_RETENTION_SNAPSHOT_V21.json').write_text(json.dumps(v,indent=2));print(output)
else:raise ValueError(phase)

