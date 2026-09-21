"""Resume document-side review with locally pinned cadgen 0.5.1; keep STEP bytes."""
from pathlib import Path
import subprocess,sys,json,os,hashlib
A=Path(__file__).resolve().parents[1];C=A/'coupled_closure';target='coupled_closure/main_input_lugs_v30.step';phase=sys.argv[1]
env=os.environ.copy();env['PYTHONPATH']=str(A/'tools/cadgen_v30')+os.pathsep+str(A/'tools/cad_runtime');env['CADGEN_COMPONENT_WORKERS']='1';env['CADGEN_VALIDATE_WORKERS']='1'
env['CADGEN_DAEMON']='0'  # Keep all native children inside this job's memory guard.
prefix=[sys.executable,'-B','-X','utf8','-m','cadgen.cli','step']
job=dict(input=target,mode='view',outputs=[dict(path=str(C/'LUG_ISO_V30.png'),camera='iso'),dict(path=str(C/'LUG_OPPOSITE_V30.png'),camera=dict(direction=[-1,1,-.8])),dict(path=str(C/'LUG_TOP_V30.png'),camera='top'),dict(path=str(C/'LUG_FRONT_V30.png'),camera='front')],render=dict(viewLabels=True,padding=.12,sizeProfile='diagnostic'))
if phase.startswith('snapshot'):
 if phase!='snapshot':
  key=phase.split('_',1)[1].upper();job['outputs']=[r for r in job['outputs'] if ('LUG_'+key+'_V30.png') in r['path']];assert len(job['outputs'])==1
 job.update(width=960,height=720)
 (C/('LUG_SNAPSHOT_JOB_V30_'+phase+'.json')).write_text(json.dumps(job))
jobs={'validate':[('LUG_TOPOLOGY_VALIDATION_V30.json',prefix+['inspect','validate',target,'--skip-self-intersection'])], 'self':[('LUG_PROJECT_SELF_INTERSECTION_V30.json',prefix+['inspect','validate',target,'--refs','o1.17,o1.18,o1.19,o1.20'])], 'snapshot':[('LUG_SNAPSHOT_RESULT_V30.json',prefix+['snapshot','--job',str(C/'LUG_SNAPSHOT_JOB_V30.json'),'--json'])], 'refs':[('LUG_DOCUMENT_REFS_V30.json',prefix+['inspect','refs',target,'--facts','--planes','--positioning'])]}
records=[];sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();before=sha(A/target)
jobs['compile']=[('LUG_DOCUMENT_COMPILE_V30.json',prefix+['compile',target,'--json'])]
if phase.startswith('snapshot'):jobs[phase]=[('LUG_SNAPSHOT_RESULT_V30_'+phase+'.json',prefix+['snapshot','--job',str(C/('LUG_SNAPSHOT_JOB_V30_'+phase+'.json')),'--json'])]
for name,cmd in jobs[phase]:
 q=subprocess.run(cmd,cwd=A,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace');records.append(dict(command=cmd,returncode=q.returncode,stdout=q.stdout,stderr=q.stderr,STEP_before=before,STEP_after=sha(A/target)));(C/f'LUG_RESUMED_{phase}_COMMANDS_V30.json').write_text(json.dumps(records,indent=2));assert q.returncode==0,q.stderr;assert before==sha(A/target);(C/name).write_text(q.stdout)
print(phase,'complete; existing STEP unchanged')
