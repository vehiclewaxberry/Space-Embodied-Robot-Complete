"""Use the unchanged native guard immediately after recorded cleanup; same workspace mutex."""
from pathlib import Path
import subprocess,sys,os,msvcrt,json,datetime,psutil
A=Path(__file__).resolve().parents[1];tag=sys.argv[1];assert tag.replace('_','').isalnum();lock=(A/'logs/CAP19_NATIVE_SERIAL.lock').open('a+b')
lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
try:
 active=[]
 for p in psutil.process_iter(['name']):
  if (p.info['name'] or '').lower() not in ['python.exe','pythonw.exe']:continue
  try:
   if any(Path(s).name=='native_delta_guard.py' for s in p.cmdline()) and Path(p.cwd()).resolve()==A:active.append(p.pid)
  except psutil.Error:pass
 assert not active
 env=os.environ.copy();env.update(WP10_FONT_SANITY='1',PYTHONPATH=str(A/'tools/cad_runtime'),CADGEN_DAEMON='0',CADGEN_COMPONENT_WORKERS='1')
 cmd=[sys.executable,'-B','-X','utf8','tools/native_delta_guard.py','--timeout','240','native_delta_'+tag,'--',sys.executable,'-B','-X','utf8','tools/split_lug_snapshot_v30.py','render']
 r=dict(workspace_mutex_held=True,precleaned=True,cleanup='TEMPORARY_MEMORY_WINDOW_V30_a.json and UI trim lug30_split_window_b',unchanged_guard=True,command=cmd)
 q=subprocess.run(cmd,cwd=A,env=env);r['returncode']=q.returncode
 (A/'logs'/('CAP19_SERIAL_'+tag+'.json')).write_text(json.dumps(r,indent=2));raise SystemExit(q.returncode)
finally:
 lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
