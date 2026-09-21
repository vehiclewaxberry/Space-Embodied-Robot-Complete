"""Serial primary STEP inspection; run each phase inside the existing RAM guard."""
from pathlib import Path
import sys,json,subprocess,hashlib,os,shutil
A=Path(__file__).resolve().parents[1];CAD=Path('F:/codex_skill/AgentSkills/codex-skills/cad/scripts')
os.environ['WP10_FONT_SANITY']='1'
os.environ['PYTHONPATH']=str(A/'tools/cad_runtime')
phase=sys.argv[1];rows=[]
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def run(tag,args):
    q=subprocess.run([sys.executable,'-B','-X','utf8',str(CAD/args[0]),*args[1:]],cwd=A,capture_output=True,text=True,encoding='utf-8')
    p='results/CAP_TERMINAL_'+tag+'_V17.json';(A/p).write_text(q.stdout,encoding='utf-8')
    (A/'logs'/('cap_terminal_'+tag+'_V17.stderr.log')).write_text(q.stderr,encoding='utf-8')
    assert q.returncode==0,(tag,q.stderr)
    v=json.loads(q.stdout);assert v.get('ok',True),v
    rows.append(dict(result=p,sha256=sha(p),returncode=q.returncode));print(tag+' completed',flush=True)
    return v
if phase in ['pcb','assembly']:
    stem='input_cap_pcb' if phase=='pcb' else 'input_cap_integration'
    target='mechanical/'+stem+'.step'
    run(phase.upper()+'_REFS',['inspect','refs',target,'--facts','--planes','--positioning'])
    run(phase.upper()+'_VALIDATE',['inspect','validate',target]+([] if phase=='pcb' else ['--skip-self-intersection']))
elif phase in ['pcb_shot','assembly_shot']:
    ispart=phase=='pcb_shot';target='mechanical/input_cap_'+('pcb' if ispart else 'integration')+'.step'
    output='review/C203_'+('PCB' if ispart else 'ASSEMBLY')+'_V17.png'
    hidden=[] if ispart else [1,32,33,34,35,36,37]
    shot=run(phase.upper(),['snapshot','--input',target,'--output',output,'--camera='+('right' if ispart else '135:-25'),'--width','1100','--height','825','--json']+[v for n in hidden for v in ['--hide','o1.'+str(n)]])
    assert shot['ok'] and len(shot['outputs'])==1
    actual=Path(shot['outputs'][0]['path']).resolve();assert actual.is_relative_to((A/'review').resolve())
    shutil.copyfile(actual,A/output)
    assert sha(output)==hashlib.sha256(actual.read_bytes()).hexdigest()
    rows.append(dict(image=output,original_image=actual.relative_to(A).as_posix(),sha256=sha(output)))
else:raise ValueError(phase)
v=dict(phase=phase,results=rows,source=target,source_sha256=sha(target),source_generator_sha256=sha(target+'.py'),whole_assembly_validation=False,full_background_self_intersection_checked=False,visual_review_by_root_completed=False)
(A/('results/CAP_TERMINAL_CAD_'+phase.upper()+'_V17.json')).write_text(json.dumps(v,indent=2),encoding='utf-8')
