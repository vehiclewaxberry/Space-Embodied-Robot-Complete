"""Terminate only this task's independently evidenced timed-out SW instance."""
from pathlib import Path
import json,hashlib,datetime,time
import psutil
C=Path(__file__).resolve().parents[1]
guard=json.loads((C/'logs/portable_copy.run.json').read_text());copy=json.loads((C/'results/PORTABLE_COPY.json').read_text());inputs=json.loads((C/'results/PORTABLE_INPUTS.json').read_text())
assert guard['status']=='TIMEOUT_GUARD'
pid=copy['attachment_attempt']['returned_pid'];assert pid==30252 and copy['attachment_attempt']['existing_pids']==[pid]
assert any(x['stage']=='copy_started' and x['state']=='service' for x in copy['progress'])
p=psutil.Process(pid);assert p.name().casefold()=='sldworks.exe'
ct=datetime.datetime.fromtimestamp(p.create_time(),datetime.timezone.utc)
expected=datetime.datetime(2026,9,7,11,43,35,tzinfo=datetime.timezone.utc)
assert abs((ct-expected).total_seconds())<3,'PID was reused or ownership time changed'
P=Path(inputs['copy_root']);file_state=[]
for f in sorted(P.iterdir()):
 if f.is_file():file_state.append({'name':f.name,'bytes':f.stat().st_size,'mtime':f.stat().st_mtime})
r={'status':'OWNED_TIMED_OUT_SW_TERMINATION_PREPARED','pid':pid,'create_time_utc':ct.isoformat(),'exe':p.exe(),'command_line':p.cmdline(),
 'working_set_mib':p.memory_info().rss/1048576,'available_mib':psutil.virtual_memory().available/1048576,
 'ownership':'SolidWorks launched for this task; CopyDocument entered after actual empty-documents assertion in portable_copy.py; no second CAD writer',
 'current_documents':'COM call busy; current document enumeration unavailable. Only this task CopyDocument operation was submitted since empty-session check.',
 'authority':'Root explicitly authorized terminating PID30252 on 2026-09-07 after timeout and ownership proof; no unknown process termination',
 'guard_status':guard['status'],'files_before':file_state}
out=C/'results/PORTABLE_OWNED_STOP.json';out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
p.terminate();p.wait(timeout=20)
def sha(f):
 h=hashlib.sha256()
 with Path(f).open('rb') as stream:
  for b in iter(lambda:stream.read(1048576),b''):h.update(b)
 return h.hexdigest()
bad=[]
for f,d in inputs['input_sha256'].items():
 if sha(f)!=d:bad.append(f)
for row in inputs['parts']:
 if sha(row['source'])!=row['source_sha256']:bad.append(row['source'])
r.update(status='PASS_OWNED_TIMEOUT_INSTANCE_STOPPED_PARENTS_UNCHANGED' if not bad else 'SOURCE_CHANGED',
         source_hash_mismatches=bad,available_after_mib=psutil.virtual_memory().available/1048576,
         files_after=[{'path':str(f),'sha256':sha(f),'bytes':f.stat().st_size} for f in sorted(P.iterdir()) if f.is_file()])
out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');assert not bad
print(json.dumps({'status':r['status'],'available_after_mib':r['available_after_mib'],'file_count':len(r['files_after'])}))
