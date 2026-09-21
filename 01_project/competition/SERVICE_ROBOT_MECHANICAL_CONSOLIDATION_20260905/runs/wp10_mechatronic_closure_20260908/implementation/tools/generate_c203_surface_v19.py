"""One STEP generation, exclusively inside the existing native guard."""
from pathlib import Path
import sys,os,time,json,subprocess,datetime
import psutil
from c203_surface_generation_contract_v19 import A,SPECS,sources,sha,read,receipt_path,GUARD_ID_FIELDS
CAD=Path('F:/codex_skill/AgentSkills/codex-skills/cad/scripts')
def main(kind):
 assert kind in SPECS
 guarded=[]
 for process in psutil.Process().parents():
  cmd=process.cmdline()
  if any(Path(x).name=='native_delta_guard.py' for x in cmd):
   names=[x for x in cmd if x.startswith('native_delta_') and not x.endswith('.py')];assert len(names)==1
   guarded.append('logs/'+names[0]+'.run.json')
 assert len(guarded)==1,'Use tools/run_cap19.py; no unguarded CAD launch'
 guard_path=guarded[0]
 for i in range(20):
  if (A/guard_path).is_file():break
  time.sleep(.1)
 guard=read(guard_path);assert guard['status']=='RUNNING' and guard['pid']==os.getpid()
 assert not guard['SW_processes_at_start'] and guard['minimum_start_available_mib']>=2048
 recpath=receipt_path(kind);assert not (A/recpath).exists(),'Archive a previous receipt explicitly before regeneration'
 before=sources(kind);source=f"mechanical/{SPECS[kind]['stem']}.step.py";target=source[:-3]
 command=[sys.executable,'-B','-X','utf8',str(CAD/'gen'),source,'--write']
 started=datetime.datetime.now().astimezone().isoformat()
 q=subprocess.Popen(command,cwd=A,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
 stdout,stderr=q.communicate();finished=datetime.datetime.now().astimezone().isoformat()
 logbase='logs/'+Path(guard_path).name.removesuffix('.run.json')+'_generator'
 (A/(logbase+'.stdout.log')).write_text(stdout,encoding='utf-8');(A/(logbase+'.stderr.log')).write_text(stderr,encoding='utf-8')
 assert q.returncode==0,(q.returncode,stderr)
 assert before==sources(kind),'Source changed during generation'
 assert (A/target).is_file() and (A/target).stat().st_size>0
 rec=dict(schema='WP10_C203_SURFACE_GENERATION_V19',kind=kind,native_generation_executed=True,started_local=started,finished_local=finished,wrapper_pid=os.getpid(),generator_pid=q.pid,owner_guard_identity={k:guard[k] for k in GUARD_ID_FIELDS},
  inputs=before,command=command,generator_returncode=q.returncode,guard_receipt=guard_path,output=target,output_sha256=sha(target),output_bytes=(A/target).stat().st_size,
  stdout=logbase+'.stdout.log',stderr=logbase+'.stderr.log',whole_fit_verified=False,native_geometry_qualified=False,
  scope='Source-to-STEP export only. Plan builder requires guard completion; exact contacts and visual inspection are separate.')
 (A/recpath).write_text(json.dumps(rec,indent=2),encoding='utf-8');print(json.dumps(rec))
if __name__=='__main__':main(sys.argv[1])
