"""Bounded pause of an identified read-only F3R2 worker pool, always resume in finally."""
from pathlib import Path
import psutil,time,json,sys,datetime
import memory_reclaim_safe_v24 as m
A=Path(__file__).resolve().parents[1];me=psutil.Process();saved=[];out=dict(start=datetime.datetime.now().astimezone().isoformat(),maximum_pause_s=90,source='readonly reviewer: daemon job-2 inspect validate F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.step',paused=[],resumed=[])
receipt=A/'results'/('TEMPORARY_MEMORY_WINDOW_V30_'+sys.argv[1]+'.json');assert not receipt.exists()
def write():receipt.write_text(json.dumps(out,indent=2))
try:
 parent=psutil.Process(10204);assert parent.ppid()==31492 and 'cadgen.daemon.worker' in parent.cmdline() and parent.username()==me.username()
 for p in parent.children():
  h=None
  try:
   pid=p.pid;created=p.create_time();exe=m.norm(p.exe());cmd=p.cmdline()
   assert pid in [52724,33208,34944,30168,32228,38768,12560,18800] and p.ppid()==10204 and p.username()==me.username() and m.session(pid)==m.session(me.pid)
   assert '--multiprocessing-fork' in cmd and 'spawn_main(parent_pid=10204,' in ' '.join(cmd) and pid not in m.visible_pids() and not p.children()
   assert p.status()!=psutil.STATUS_STOPPED
   h=m.K.OpenProcess(0x1000|0x0100,False,pid);assert h;ct,im=m.identity(h);assert abs(ct-created)<.001 and im==exe
   p.suspend();saved.append((p,created));out['paused'].append(dict(pid=pid,created=created,trimmed=bool(m.P.EmptyWorkingSet(h))));write()
  except (psutil.Error,AssertionError,OSError):pass
  finally:
   if h:m.K.CloseHandle(h)
 out['available_after_MiB']=psutil.virtual_memory().available/2**20;write();print(json.dumps(out),flush=True)
 deadline=time.monotonic()+90
 while time.monotonic()<deadline:
  if (A/'results/TEMPORARY_MEMORY_WINDOW_V30_RELEASE').exists():break
  time.sleep(.5)
finally:
 for p,created in saved:
  try:
   if abs(p.create_time()-created)<.001:p.resume();out['resumed'].append(p.pid)
  except psutil.Error:pass
 out['end']=datetime.datetime.now().astimezone().isoformat();write();print(json.dumps(out),flush=True)
