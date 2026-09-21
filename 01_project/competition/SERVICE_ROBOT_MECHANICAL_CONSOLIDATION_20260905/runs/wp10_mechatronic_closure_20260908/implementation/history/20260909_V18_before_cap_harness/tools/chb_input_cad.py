"""Explicit, serial CAD targets. Execute inside native_delta_guard."""
from pathlib import Path
import sys,subprocess,os,json,hashlib,shutil
A=Path(__file__).resolve().parents[1];CAD=Path('F:/codex_skill/AgentSkills/codex-skills/cad/scripts')
os.environ['WP10_FONT_SANITY']='1';os.environ['PYTHONPATH']=str(A/'tools/cad_runtime')
phase=sys.argv[1]
def run(tag,args):
 q=subprocess.run([sys.executable,'-B','-X','utf8',str(CAD/args[0]),*args[1:]],cwd=A,capture_output=True,text=True,encoding='utf-8')
 (A/f'logs/chb18_{tag}.stdout.log').write_text(q.stdout,encoding='utf-8');(A/f'logs/chb18_{tag}.stderr.log').write_text(q.stderr,encoding='utf-8')
 assert q.returncode==0,(tag,q.stderr);print(tag,flush=True);return q.stdout
if phase in ['pcb','spacer','screw','assembly']:
 run('gen_'+phase,['gen','mechanical/chb_input_'+phase+'.step.py','--write'])
elif phase in ['review_pcb','review_assembly']:
 target='mechanical/chb_input_'+phase[7:]+'.step';records=[]
 for verb,args in [('refs',['refs',target,'--facts','--planes','--positioning']),('validate',['validate',target]+(['--skip-self-intersection'] if phase.endswith('assembly') else []))]:
  v=json.loads(run(phase+'_'+verb,['inspect',*args]));assert v.get('ok',True);name=f'results/CHB_INPUT_{phase}_{verb}_V18.json';(A/name).write_text(json.dumps(v,indent=2));records.append(name)
 (A/f'results/CHB_INPUT_{phase}_V18.json').write_text(json.dumps(dict(target=target,target_sha256=hashlib.sha256((A/target).read_bytes()).hexdigest(),records=records)))
elif phase in ['shot','shot_detail']:
 detail=phase=='shot_detail';suffix='_DETAIL' if detail else ''
 target='mechanical/chb_input_assembly.step';out='review/CHB_INPUT_ASSEMBLY'+suffix+'_V18.png'
 v=json.loads(run(phase,['snapshot','--input',target,'--output',out,'--camera=230:20' if detail else '--camera=130:22','--width','1200','--height','900','--json']+([a for i in range(7,12) for a in ['--hide','o1.'+str(i)]] if detail else [])))
 assert v['ok'] and len(v['outputs'])==1;actual=Path(v['outputs'][0]['path']).resolve();assert actual.is_relative_to((A/'review').resolve());shutil.copyfile(actual,A/out)
 v.update(target=target,target_sha256=hashlib.sha256((A/target).read_bytes()).hexdigest(),published_image=out,published_sha256=hashlib.sha256((A/out).read_bytes()).hexdigest(),root_visual_review_completed=False)
 v['hidden_occurrences']=['o1.'+str(i) for i in range(7,12)] if detail else []
 (A/('results/CHB_INPUT_SNAPSHOT'+suffix+'_V18.json')).write_text(json.dumps(v,indent=2))
else:raise ValueError(phase)
