"""Stop exactly the observed legacy STEP validation pool, preserving its calling app."""
from pathlib import Path
import psutil,json,sys,datetime
import memory_reclaim_safe_v24 as m
A=Path(__file__).resolve().parents[1];me=psutil.Process();user=me.username();sess=m.session(me.pid)
out=dict(time=datetime.datetime.now().astimezone().isoformat(),authorization='Repeated user request to close unrelated background computation before current WP10 engineering',target='read-only validation of F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION_STOWED.step',before_MiB=psutil.virtual_memory().available/2**20,rows=[]);handles=[]
try:
 root=psutil.Process(30360);assert abs(root.create_time()-1789104611.366511)<.001
 cmd=root.cmdline();assert cmd[-3:-1]==['inspect','validate'] and cmd[-1].endswith('/F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION_STOWED.step'.replace('/','\\'))
 assert root.name().lower()=='python.exe' and root.username()==user and m.session(root.pid)==sess
 visible=m.visible_pids();children=root.children(recursive=True)
 for p in children+[root]:
  assert p.name().lower()=='python.exe' and p.username()==user and m.session(p.pid)==sess and p.pid not in visible
  if p.pid!=root.pid:assert '--multiprocessing-fork' in p.cmdline() or 'multiprocessing.resource_tracker' in ' '.join(p.cmdline())
  created=p.create_time();exe=m.norm(p.exe());h=m.K.OpenProcess(0x1000|0x0001|0x100000,False,p.pid);assert h
  ct,im=m.identity(h);assert abs(ct-created)<.001 and im==exe
  handles.append((p.pid,h,p.memory_info().rss/2**20))
 assert abs(psutil.Process(30360).create_time()-1789104611.366511)<.001
 for pid,h,rss in handles:
  ok=bool(m.K.TerminateProcess(h,0));out['rows'].append(dict(pid=pid,rss_before_MiB=rss,exit_confirmed=ok and m.K.WaitForSingleObject(h,3000)==0))
except (psutil.Error,AssertionError,OSError) as e:out['error']=str(e)
finally:
 for _,h,_ in handles:m.K.CloseHandle(h)
out['after_MiB']=psutil.virtual_memory().available/2**20
with (A/'results'/('LEGACY_READONLY_CHECK_STOP_V30_'+sys.argv[1]+'.json')).open('x') as f:json.dump(out,f,indent=2)
print(json.dumps(out))
