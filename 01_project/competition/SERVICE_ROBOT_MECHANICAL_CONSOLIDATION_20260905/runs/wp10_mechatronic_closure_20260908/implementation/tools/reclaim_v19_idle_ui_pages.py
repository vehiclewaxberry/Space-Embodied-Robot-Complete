"""Release reloadable resident pages of identified idle desktop UI processes.

User repeatedly authorized background memory cleanup. EmptyWorkingSet changes
residency only; no process termination, document action, memory write or save.
Known Codex desktop processes and Explorer only; exclude busy processes. Parentage does
not imply termination here: only the OS working-set-residency API is used.
"""
import psutil,time,ctypes,json
from pathlib import Path
A=Path(__file__).resolve().parents[1]
me=psutil.Process();exclude={me.pid}
before=psutil.virtual_memory().available/2**20;sample=[]
for p in psutil.process_iter(['pid','name','create_time']):
 try:
  if p.pid in exclude or (p.info['name'] or '').lower() not in ['chatgpt.exe','codex.exe','explorer.exe']:continue
  t=p.cpu_times();sample.append((p,p.info['create_time'],t.user+t.system))
 except psutil.Error:pass
time.sleep(1)
k=ctypes.WinDLL('kernel32',use_last_error=True);api=ctypes.WinDLL('psapi',use_last_error=True)
k.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong];k.OpenProcess.restype=ctypes.c_void_p
k.CloseHandle.argtypes=[ctypes.c_void_p];api.EmptyWorkingSet.argtypes=[ctypes.c_void_p];api.EmptyWorkingSet.restype=ctypes.c_int
rows=[]
for p,created,cpu in sample:
 try:
  t=p.cpu_times();delta=t.user+t.system-cpu
  if abs(p.create_time()-created)>.01 or delta>.10:continue
  rss=p.memory_info().rss/2**20
  if rss<40:continue
  h=k.OpenProcess(0x0100|0x0400,False,p.pid)
  if not h:continue
  try:ok=bool(api.EmptyWorkingSet(h))
  finally:k.CloseHandle(h)
  rows.append(dict(pid=p.pid,name=p.name(),created=created,sample_cpu_s=delta,rss_before_mib=rss,rss_after_mib=p.memory_info().rss/2**20,trimmed=ok))
 except psutil.Error:pass
out=dict(before_mib=before,after_mib=psutil.virtual_memory().available/2**20,processes=rows,terminated=0,documents_saved_or_closed=False,method='Windows EmptyWorkingSet; preserve dirty/private pages and application state')
(A/'results/CAP_HARNESS_UI_MEMORY_RECOVERY_V19.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
