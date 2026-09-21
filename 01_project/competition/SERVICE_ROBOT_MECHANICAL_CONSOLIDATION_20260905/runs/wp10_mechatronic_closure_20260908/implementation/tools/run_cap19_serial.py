"""One active native launch per WP10 workspace, plus live legacy-guard exclusion."""
from pathlib import Path
import sys,subprocess,msvcrt,json,datetime
import psutil
A=Path(__file__).resolve().parents[1]
def main():
 tag=sys.argv[1];assert tag.replace('_','').isalnum()
 lock=(A/'logs/CAP19_NATIVE_SERIAL.lock').open('a+b')
 try:
  lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
 except OSError:raise SystemExit('Another serial native launch holds the workspace lock')
 try:
  active=[]
  for p in psutil.process_iter(['pid','name']):
   if (p.info['name'] or '').lower() not in ['python.exe','pythonw.exe']:continue
   try:
    cmd=p.cmdline()
    if any(Path(x).name=='native_delta_guard.py' for x in cmd) and Path(p.cwd()).resolve()==A:active.append(dict(pid=p.pid,command=cmd))
   except (psutil.NoSuchProcess,psutil.AccessDenied):continue
  assert not active,'Existing native guard must finish before next launch: '+str(active)
  path=A/f'logs/CAP19_SERIAL_{tag}.json';assert not path.exists(),'Do not overwrite serial launch receipt'
  record=dict(started_local=datetime.datetime.now().astimezone().isoformat(),workspace_mutex_held=True,legacy_native_guards_at_start=active,command=[sys.executable,'-B','-X','utf8','tools/run_cap19.py',*sys.argv[1:]])
  path.write_text(json.dumps(record,indent=2),encoding='utf-8')
  q=subprocess.run(record['command'],cwd=A)
  record.update(finished_local=datetime.datetime.now().astimezone().isoformat(),returncode=q.returncode)
  path.write_text(json.dumps(record,indent=2),encoding='utf-8')
  raise SystemExit(q.returncode)
 finally:
  lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
if __name__=='__main__':main()
