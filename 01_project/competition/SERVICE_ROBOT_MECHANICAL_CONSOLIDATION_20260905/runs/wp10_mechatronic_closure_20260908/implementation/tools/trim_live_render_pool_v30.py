"""Trim observed render-worker resident pages only; never stop live jobs."""
from pathlib import Path
import psutil,json,sys
import memory_reclaim_safe_v24 as m
A=Path(__file__).resolve().parents[1];me=psutil.Process();out=dict(terminated=[],rows=[],before_MiB=psutil.virtual_memory().available/2**20)
try:
 parent=psutil.Process(10204);assert '-m' in parent.cmdline() and 'cadgen.daemon.worker' in parent.cmdline();assert parent.ppid()==31492
 candidates=[(p.pid,p.create_time()) for p in parent.children() if p.pid in [52724,33208,34944,30168,32228,38768,12560]]
except (psutil.Error,AssertionError):candidates=[]
for pid,created in candidates:
 h=None;r=dict(pid=pid)
 try:
  p=psutil.Process(pid);exe=m.norm(p.exe());assert p.ppid()==10204 and p.username()==me.username() and m.session(pid)==m.session(me.pid)
  assert '--multiprocessing-fork' in p.cmdline() and 'spawn_main(parent_pid=10204,' in ' '.join(p.cmdline())
  h=m.K.OpenProcess(0x1000|0x0100,False,pid);assert h;ct,im=m.identity(h);assert abs(ct-created)<.001 and im==exe
  r.update(before_MiB=p.memory_info().rss/2**20,trim_ok=bool(m.P.EmptyWorkingSet(h)))
 except (psutil.Error,AssertionError,OSError) as e:r['skip']=str(e)
 finally:
  if h:m.K.CloseHandle(h)
  out['rows'].append(r)
out['after_MiB']=psutil.virtual_memory().available/2**20
with (A/'results'/('LIVE_RENDER_POOL_TRIM_V30_'+sys.argv[1]+'.json')).open('x') as f:json.dump(out,f,indent=2)
print(json.dumps(out))
