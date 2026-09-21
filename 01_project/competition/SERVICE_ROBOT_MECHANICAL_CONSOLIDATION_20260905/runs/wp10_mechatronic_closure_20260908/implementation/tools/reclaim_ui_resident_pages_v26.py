"""Reversible working-set trim of observed UI processes; no termination or cache deletion.

Unlike the idle utility closer, this may trim a busy renderer's resident pages.
The OS keeps committed application state and pages it back on demand. No guarantee
of durable savings; record three samples and keep the native launch gate unchanged.
"""
from pathlib import Path
import sys,json,datetime,time,ctypes,psutil
import memory_reclaim_safe_v24 as m
A=Path(__file__).resolve().parents[1];tag=sys.argv[1];assert tag.replace('_','').isalnum()
dest=A/'results'/('UI_RESIDENT_RECOVERY_'+tag+'.json')
me=psutil.Process();exclude={me.pid}|{p.pid for p in me.parents()};user=me.username();sess=m.session(me.pid)
out=dict(schema='WP10_V26_UI_RESIDENT_TRIM_NO_TERMINATION',time=datetime.datetime.now().isoformat(),
 before_MiB=psutil.virtual_memory().available/2**20,processes_terminated=[],rows=[],scope='Observed browser and Codex UI only; preserve committed state, documents, windows and sessions. Busy-process trimming may briefly page fault.')
with dest.open('x') as f:json.dump(out,f)
for p in psutil.process_iter():
 h=None;row={}
 try:
  if p.pid in exclude or p.username()!=user or m.session(p.pid)!=sess:continue
  exe=m.norm(p.exe())
  if not (exe in ['c:/program files/google/chrome/application/chrome.exe','c:/program files (x86)/microsoft/edge/application/msedge.exe'] or (exe.startswith('c:/program files/windowsapps/openai.codex_') and exe.endswith('/app/chatgpt.exe'))):continue
  rss=p.memory_info().rss
  if rss<128*2**20:continue
  created=p.create_time();row=dict(pid=p.pid,exe=exe,rss_before_MiB=rss/2**20)
  h=m.K.OpenProcess(0x1000|0x0100,False,p.pid)
  if not h:raise OSError('OpenProcess failed')
  ct,im=m.identity(h)
  if abs(ct-created)>.001 or im!=exe:raise OSError('HANDLE identity changed')
  row['trim_ok']=bool(m.P.EmptyWorkingSet(h))
 except (psutil.Error,OSError) as e:
  if row:row['error']=str(e)
 finally:
  if h:m.K.CloseHandle(h)
  if row:out['rows'].append(row)
samples=[]
for _ in range(3):samples.append(psutil.virtual_memory().available/2**20);time.sleep(2)
out.update(after_samples_MiB=samples,threshold_MiB=2048,threshold_met=min(samples)>=2048)
dest.write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(dict(trimmed=sum(r.get('trim_ok',False) for r in out['rows']),closed=0,after_samples_MiB=samples,threshold_met=out['threshold_met'])))
