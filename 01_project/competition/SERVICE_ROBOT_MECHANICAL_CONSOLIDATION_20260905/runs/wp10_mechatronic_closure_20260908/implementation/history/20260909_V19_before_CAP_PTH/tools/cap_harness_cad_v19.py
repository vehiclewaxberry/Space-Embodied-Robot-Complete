"""Explicit serial generation/inspection of current physical harness objects."""
from pathlib import Path
import subprocess,sys,json,hashlib,shutil
A=Path(__file__).resolve().parents[1];CAD=Path('F:/codex_skill/AgentSkills/codex-skills/cad/scripts');phase=sys.argv[1]
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def run(tag,args):
 q=subprocess.run([sys.executable,'-B','-X','utf8',str(CAD/args[0]),*args[1:]],cwd=A,capture_output=True,text=True,encoding='utf-8')
 (A/f'logs/cap19_{tag}.stdout.log').write_text(q.stdout,encoding='utf-8');(A/f'logs/cap19_{tag}.stderr.log').write_text(q.stderr,encoding='utf-8')
 assert q.returncode==0,(tag,q.stderr);return q.stdout
if phase in ['plus','minus','assembly']:
 print(run('gen_'+phase,['gen','mechanical/cap_harness_'+phase+'.step.py','--write']))
elif phase=='review':
 target='mechanical/cap_harness_assembly.step';records=[]
 for verb,args in [('refs',['refs',target,'--facts','--planes','--positioning']),('validate',['validate',target,'--skip-self-intersection'])]:
  v=json.loads(run(verb,['inspect',*args]));assert v.get('ok',True)
  name='results/CAP_HARNESS_'+verb.upper()+'_V19.json';(A/name).write_text(json.dumps(v,indent=2));records.append(name)
 (A/'results/CAP_HARNESS_CAD_REVIEW_V19.json').write_text(json.dumps(dict(target=target,target_sha256=sha(target),records={p:sha(p) for p in records},self_intersection_skipped=True)))
 print('Actual harness assembly inspected')
elif phase=='shot':
 target='mechanical/cap_harness_assembly.step';out='review/CAP_HARNESS_ASSEMBLY_V19.png'
 v=json.loads(run('shot',['snapshot','--input',target,'--output',out,'--camera=130:22','--width','1200','--height','900','--json']))
 assert v['ok'] and len(v['outputs'])==1
 actual=Path(v['outputs'][0]['path']).resolve();assert actual.is_relative_to((A/'review').resolve());shutil.copyfile(actual,A/out)
 v.update(target=target,target_sha256=sha(target),published_image=out,published_sha256=sha(out))
 (A/'results/CAP_HARNESS_SNAPSHOT_V19.json').write_text(json.dumps(v,indent=2));print(out)
else:raise ValueError(phase)
