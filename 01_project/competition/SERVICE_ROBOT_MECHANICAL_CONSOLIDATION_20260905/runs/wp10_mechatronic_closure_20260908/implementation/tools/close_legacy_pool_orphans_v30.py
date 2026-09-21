"""Close only previously observed workers after the legacy reader itself has exited."""
from pathlib import Path
import psutil,json,sys,datetime
import memory_reclaim_safe_v24 as m
A=Path(__file__).resolve().parents[1];root=next(q for q in A.parents if (q/'PROJECT_MAP.md').exists());me=psutil.Process();out=dict(time=datetime.datetime.now().astimezone().isoformat(),before_MiB=psutil.virtual_memory().available/2**20,rows=[])
for pid in [53828,20728,38948,32432,9700,21344,12504,30284]:
 h=None;r=dict(pid=pid,terminated=False)
 try:
  p=psutil.Process(pid);created=p.create_time();exe=m.norm(p.exe());cmd=p.cmdline()
  assert not psutil.pid_exists(30360) and p.parent() is None and p.ppid()==30360
  assert exe=='g:/windows_program_file/anaconda/python.exe' and created>1789104611.366511
  assert p.username()==me.username() and m.session(pid)==m.session(me.pid) and m.norm(p.cwd())==m.norm(str(root))
  assert '--multiprocessing-fork' in cmd and 'spawn_main(parent_pid=30360,' in ' '.join(cmd) and not p.children() and pid not in m.visible_pids()
  assert all(m.norm(q.path).startswith('c:/windows/') and q.path.lower().endswith('.mui') for q in p.open_files())
  h=m.K.OpenProcess(0x1000|0x0001|0x100000,False,pid);assert h
  ct,im=m.identity(h);assert abs(ct-created)<.001 and im==exe and not psutil.pid_exists(30360)
  r.update(created=created,rss_before_MiB=p.memory_info().rss/2**20,terminated=bool(m.K.TerminateProcess(h,0)) and m.K.WaitForSingleObject(h,3000)==0)
 except (psutil.Error,AssertionError,OSError) as e:r['skip_reason']=str(e)
 finally:
  if h:m.K.CloseHandle(h)
  out['rows'].append(r)
out['after_MiB']=psutil.virtual_memory().available/2**20
with (A/'results'/('LEGACY_POOL_ORPHANS_CLOSED_V30_'+sys.argv[1]+'.json')).open('x') as f:json.dump(out,f,indent=2)
print(json.dumps(out))
