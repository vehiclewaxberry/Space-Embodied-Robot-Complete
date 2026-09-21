"""Trim four observed parentless worker residents; never terminate user computation."""
from pathlib import Path
import psutil,json,time,sys
import memory_reclaim_safe_v24 as m
A=Path(__file__).resolve().parents[1];out=dict(before_MiB=psutil.virtual_memory().available/2**20,rows=[],terminated=[])
expected={15660:1789104301.1061444,20804:1789104301.04133,48004:1789104301.066632,28576:1789104301.093228}
me=psutil.Process();user=me.username();session=m.session(me.pid)
for pid,created in expected.items():
 h=None;r=dict(pid=pid,action='skipped')
 try:
  p=psutil.Process(pid);exe=m.norm(p.exe());cmd=' '.join(p.cmdline())
  assert exe=='g:/windows_program_file/anaconda/python.exe' and abs(p.create_time()-created)<.001
  assert p.username()==user and m.session(pid)==session and 'spawn_main(parent_pid=46360,' in cmd
  assert p.parent() is None and not p.children() and m.norm(p.cwd())==m.norm(str(next(q for q in A.parents if (q/'PROJECT_MAP.md').exists())))
  h=m.K.OpenProcess(0x1000|0x0100,False,pid);assert h
  ct,im=m.identity(h);assert abs(ct-created)<.001 and im==exe
  r.update(action='trim_resident_only',before_MiB=p.memory_info().rss/2**20,trim_ok=bool(m.P.EmptyWorkingSet(h)))
 except (psutil.Error,AssertionError,OSError) as e:r['reason']=str(e)
 finally:
  if h:m.K.CloseHandle(h)
  out['rows'].append(r)
out['after_samples_MiB']=[]
for _ in range(3):out['after_samples_MiB'].append(psutil.virtual_memory().available/2**20);time.sleep(1)
out['threshold_met']=min(out['after_samples_MiB'])>=2048
p=A/'results'/('OBSERVED_WORKER_RECLAIM_V30_'+sys.argv[1]+'.json')
with p.open('x') as f:json.dump(out,f,indent=2)
print(json.dumps(out))
