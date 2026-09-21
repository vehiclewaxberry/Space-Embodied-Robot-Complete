"""Bounded cleanup with live HANDLE identity; no document sessions terminated."""
from pathlib import Path
from ctypes import wintypes as W
import ctypes,datetime,json,sys,time,psutil
A=Path(__file__).resolve().parents[1]
K=ctypes.WinDLL('kernel32',use_last_error=True);P=ctypes.WinDLL('psapi',use_last_error=True);U=ctypes.WinDLL('user32',use_last_error=True)
K.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];K.OpenProcess.restype=W.HANDLE
K.CloseHandle.argtypes=[W.HANDLE]
K.GetProcessTimes.argtypes=[W.HANDLE,*([ctypes.POINTER(W.FILETIME)]*4)];K.GetProcessTimes.restype=W.BOOL
K.QueryFullProcessImageNameW.argtypes=[W.HANDLE,W.DWORD,W.LPWSTR,ctypes.POINTER(W.DWORD)];K.QueryFullProcessImageNameW.restype=W.BOOL
K.ProcessIdToSessionId.argtypes=[W.DWORD,ctypes.POINTER(W.DWORD)];K.ProcessIdToSessionId.restype=W.BOOL
K.TerminateProcess.argtypes=[W.HANDLE,W.UINT];K.TerminateProcess.restype=W.BOOL
K.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD];K.WaitForSingleObject.restype=W.DWORD
P.EmptyWorkingSet.argtypes=[W.HANDLE];P.EmptyWorkingSet.restype=W.BOOL
U.GetWindowThreadProcessId.argtypes=[W.HWND,ctypes.POINTER(W.DWORD)]
U.IsWindowVisible.argtypes=[W.HWND];U.IsWindowVisible.restype=W.BOOL
CALLBACK=ctypes.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
U.EnumWindows.argtypes=[CALLBACK,W.LPARAM];U.EnumWindows.restype=W.BOOL
def norm(s):return s.replace('\\','/').casefold()
def session(pid):
 s=W.DWORD()
 if not K.ProcessIdToSessionId(pid,ctypes.byref(s)):raise OSError('session unavailable')
 return s.value
def visible_pids():
 found=set()
 @CALLBACK
 def f(hwnd,_):
  if U.IsWindowVisible(hwnd):
   pid=W.DWORD();U.GetWindowThreadProcessId(hwnd,ctypes.byref(pid));found.add(pid.value)
  return True
 if not U.EnumWindows(f,0):raise OSError('window inventory unavailable')
 return found
def io(p):
 v=p.io_counters()
 return tuple(getattr(v,k,0) for k in ['read_count','write_count','other_count','read_bytes','write_bytes','other_bytes'])
def identity(h):
 ts=[W.FILETIME() for _ in range(4)]
 if not K.GetProcessTimes(h,*[ctypes.byref(t) for t in ts]):raise OSError('times unavailable')
 created=((ts[0].dwHighDateTime<<32)+ts[0].dwLowDateTime)/1e7-11644473600
 b=ctypes.create_unicode_buffer(32768);n=W.DWORD(len(b))
 if not K.QueryFullProcessImageNameW(h,0,b,ctypes.byref(n)):raise OSError('image unavailable')
 return created,norm(b.value)
ALLOW=['mcp_server.py','mcp_server_pyfluent_preload.py','solidworks_mcp.server','skills_bridge_server.py',
 'qwen_vision','aerospace_mcp_skills','comsol_link','workbench mcp','kicad-mcp-server',
 'artifact-template-picker','unified-computer-use']
def role(p,mode):
 exe=norm(p.exe())
 if mode=='background':
  if '/microsoftwindows.client.webexperience_' in exe and exe.endswith('/dashboard/widgets.exe'):return 'close_widgets'
  if exe=='f:/windows_profile/solidworks/solidworks/sldworks_fs.exe':return 'close_preloader'
  if '/windowsapps/claude_' in exe and exe.endswith('/app/claude.exe'):return 'trim_only_preserve_session'
  if exe=='c:/windows/explorer.exe':return 'trim_only_preserve_explorer_session'
 else:
  if p.name().casefold() not in ['python.exe','pythonw.exe','node.exe']:return
  if not any(v in ' '.join(p.cmdline()).casefold() for v in ALLOW):return
  if not any(q.name().casefold()=='codex.exe' for q in p.parents()):return
  if any(q.name().casefold() not in ['python.exe','pythonw.exe','node.exe','node_repl.exe','conhost.exe'] for q in p.children(recursive=True)):return
  return 'trim_only_preserve_tool'
def run(mode,tag):
 assert mode in ['background','tools'] and tag.replace('_','').isalnum()
 prefix='BACKGROUND_MEMORY_CLEANUP_' if mode=='background' else 'CAP_TERMINAL_MEMORY_RECOVERY_V17_'
 path=A/'results'/(prefix+tag+'.json')
 out=dict(schema='WP10_HANDLE_BOUND_MEMORY_RECLAIM_V24',mode=mode,status='STARTED',
  time_local=datetime.datetime.now().astimezone().isoformat(),before_available_MiB=psutil.virtual_memory().available/2**20,
  rows=[],processes_terminated=[],start_threshold_MiB=2048,headroom_target_MiB=2304,
  scope='Known background utilities close only after no visible windows/children, same user/session, stable CPU+IO and handle identity. Other matches trim resident pages only. No permanent memory guarantee.')
 with path.open('x',encoding='utf-8') as f:json.dump(out,f,indent=2)
 try:
  me=psutil.Process();exclude={me.pid}|{q.pid for q in me.parents()};user=me.username();sess=session(me.pid);items=[]
  for p in psutil.process_iter():
   try:
    if p.pid in exclude or p.username()!=user or session(p.pid)!=sess:continue
    r=role(p,mode)
    if r:
     c=p.cpu_times();items.append((p.pid,p.create_time(),norm(p.exe()),r,c.user+c.system,io(p)))
   except (psutil.Error,OSError):pass
  time.sleep(2)
  for pid,created,exe,r,cpu0,io0 in items:
   h=None;row=dict(pid=pid,role=r,action='preserved',trim_ok=False)
   try:
    p=psutil.Process(pid);c=p.cpu_times()
    if p.username()!=user or session(pid)!=sess or role(p,mode)!=r:continue
    row.update(cpu_delta_s=c.user+c.system-cpu0,rss_before_MiB=p.memory_info().rss/2**20)
    if abs(p.create_time()-created)>.001:row['action']='preserved_identity_changed';continue
    if row['cpu_delta_s']>.05 or io(p)!=io0:row['action']='preserved_busy_sample';continue
    closing=r.startswith('close_')
    if closing and (pid in visible_pids() or p.children(recursive=True)):
     row['action']='preserved_visible_or_child_process';continue
    if r=='close_preloader' and any(q.name().lower()=='sldworks.exe' for q in psutil.process_iter()):
     row['action']='preserved_solidworks_session';continue
    h=K.OpenProcess(0x1000|0x0100|(0x0001|0x100000 if closing else 0),False,pid)
    if not h:raise OSError('OpenProcess failed '+str(ctypes.get_last_error()))
    hct,hexe=identity(h)
    if abs(hct-created)>.001 or hexe!=exe:raise OSError('handle identity mismatch')
    if closing:
     ok=bool(K.TerminateProcess(h,0))
     row['process_exit_confirmed']=ok and K.WaitForSingleObject(h,3000)==0
     row['action']='terminated' if row['process_exit_confirmed'] else 'termination_not_confirmed'
     if row['process_exit_confirmed']:out['processes_terminated'].append(pid)
    else:
     row['trim_ok']=bool(P.EmptyWorkingSet(h));row['success']=row['trim_ok'];row['action']='working_set_trim_only'
   except (psutil.Error,OSError) as e:row.update(action='skipped',error=str(e))
   finally:
    if h:K.CloseHandle(h)
    out['rows'].append(row)
  samples=[]
  for _ in range(3):samples.append(psutil.virtual_memory().available/2**20);time.sleep(1)
  out.update(status='COMPLETED',after_samples_MiB=samples,after_available_MiB=samples[-1],
   threshold_met=min(samples)>=2048,engineering_launcher_must_recheck=True)
 finally:path.write_text(json.dumps(out,indent=2),encoding='utf-8')
 print(json.dumps(dict(status=out['status'],closed=len(out['processes_terminated']),trimmed=sum(r.get('trim_ok',False) for r in out['rows']),after_samples_MiB=out.get('after_samples_MiB'),threshold_met=out.get('threshold_met'))))

