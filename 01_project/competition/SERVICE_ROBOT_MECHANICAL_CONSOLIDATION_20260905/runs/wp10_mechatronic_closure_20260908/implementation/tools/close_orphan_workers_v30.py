"""Close only four identity-bound orphan workers with no result-owning parent."""
from pathlib import Path
import psutil,json,sys,datetime
import memory_reclaim_safe_v24 as m
A=Path(__file__).resolve().parents[1];root=next(q for q in A.parents if (q/'PROJECT_MAP.md').exists());me=psutil.Process();user=me.username();sess=m.session(me.pid)
expected={15660:1789104301.1061444,20804:1789104301.04133,48004:1789104301.066632,28576:1789104301.093228}
out=dict(time=datetime.datetime.now().astimezone().isoformat(),authorization='User repeated request to close unnecessary background processes; exact observed parentless computation workers only',before_MiB=psutil.virtual_memory().available/2**20,rows=[])
for pid,created in expected.items():
 h=None;r=dict(pid=pid,terminated=False)
 try:
  p=psutil.Process(pid);exe=m.norm(p.exe());cmd=p.cmdline()
  assert not psutil.pid_exists(46360) and p.parent() is None and p.ppid()==46360
  assert exe=='g:/windows_program_file/anaconda/python.exe' and abs(p.create_time()-created)<.001
  assert p.username()==user and m.session(pid)==sess and m.norm(p.cwd())==m.norm(str(root))
  assert len(cmd)==4 and cmd[1]=='-c' and cmd[3]=='--multiprocessing-fork' and cmd[2].startswith('from multiprocessing.spawn import spawn_main; spawn_main(parent_pid=46360, pipe_handle=')
  assert not p.children() and pid not in m.visible_pids()
  assert all(m.norm(q.path).startswith('c:/windows/') and q.path.lower().endswith('.mui') for q in p.open_files())
  h=m.K.OpenProcess(0x1000|0x0001|0x100000,False,pid);assert h
  ct,im=m.identity(h);assert abs(ct-created)<.001 and im==exe and not psutil.pid_exists(46360)
  r['rss_before_MiB']=p.memory_info().rss/2**20;r['terminated']=bool(m.K.TerminateProcess(h,0)) and m.K.WaitForSingleObject(h,3000)==0
 except (AssertionError,psutil.Error,OSError) as e:r['skip_reason']=str(e)
 finally:
  if h:m.K.CloseHandle(h)
  out['rows'].append(r)
out['after_MiB']=psutil.virtual_memory().available/2**20
p=A/'results'/('ORPHAN_WORKERS_CLOSED_V30_'+sys.argv[1]+'.json')
with p.open('x') as f:json.dump(out,f,indent=2)
print(json.dumps(out))
