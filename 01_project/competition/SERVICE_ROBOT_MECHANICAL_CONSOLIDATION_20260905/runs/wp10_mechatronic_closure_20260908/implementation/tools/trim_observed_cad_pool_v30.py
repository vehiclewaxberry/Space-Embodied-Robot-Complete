"""Reclaim resident pages of an observed read-only CAD check; preserve computation."""
from pathlib import Path
import psutil,json,time,sys
import memory_reclaim_safe_v24 as m
A=Path(__file__).resolve().parents[1];me=psutil.Process();user=me.username();sess=m.session(me.pid);out=dict(before_MiB=psutil.virtual_memory().available/2**20,terminated=[],rows=[])
try:
 parent=psutil.Process(30360);assert abs(parent.create_time()-1789104611.366511)<.001
 cmd=parent.cmdline();assert 'inspect' in cmd and 'validate' in cmd and any(x.endswith('F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION_STOWED.step') for x in cmd)
 candidates=[(p.pid,p.create_time()) for p in parent.children() if p.name().lower()=='python.exe']
except (psutil.Error,AssertionError):candidates=[]
for pid,created in candidates:
 h=None;r=dict(pid=pid)
 try:
  p=psutil.Process(pid);exe=m.norm(p.exe());assert p.ppid()==30360 and p.username()==user and m.session(pid)==sess
  assert '--multiprocessing-fork' in p.cmdline() and 'spawn_main(parent_pid=30360,' in ' '.join(p.cmdline())
  h=m.K.OpenProcess(0x1000|0x0100,False,pid);assert h
  ct,im=m.identity(h);assert abs(ct-created)<.001 and im==exe
  r.update(before_MiB=p.memory_info().rss/2**20,trim_ok=bool(m.P.EmptyWorkingSet(h)))
 except (psutil.Error,AssertionError,OSError) as e:r['skip']=str(e)
 finally:
  if h:m.K.CloseHandle(h)
  out['rows'].append(r)
out['after_MiB']=psutil.virtual_memory().available/2**20
with (A/'results'/('CAD_POOL_RESIDENT_TRIM_V30_'+sys.argv[1]+'.json')).open('x') as f:json.dump(out,f,indent=2)
print(json.dumps(out))
