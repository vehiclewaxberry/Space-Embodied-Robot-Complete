"""User-authorized bounded cleanup; preserve apps with work and all Codex hosts."""
from pathlib import Path
import ctypes, datetime, json, time
from ctypes import wintypes
import psutil

A=Path(__file__).resolve().parents[1]
before=psutil.virtual_memory().available/2**20
identity=[]
for p in psutil.process_iter(['pid','name','exe','create_time','cpu_times']):
    try:
        exe=(p.info['exe'] or '').replace('\\','/').lower()
        role=None
        if '/microsoftwindows.client.webexperience_' in exe and exe.endswith('/dashboard/widgets.exe'):role='close_widgets'
        if exe=='f:/windows_profile/solidworks/solidworks/sldworks_fs.exe':role='close_preloader'
        if '/windowsapps/claude_' in exe and exe.endswith('/app/claude.exe'):role='trim_only_preserve_session'
        if role:
            cpu=p.cpu_times();identity.append((p,p.create_time(),exe,role,cpu.user+cpu.system))
    except (psutil.AccessDenied,psutil.NoSuchProcess):pass
time.sleep(2)
k=ctypes.WinDLL('kernel32',use_last_error=True);api=ctypes.WinDLL('psapi',use_last_error=True)
k.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];k.OpenProcess.restype=wintypes.HANDLE
k.CloseHandle.argtypes=[wintypes.HANDLE];api.EmptyWorkingSet.argtypes=[wintypes.HANDLE];api.EmptyWorkingSet.restype=wintypes.BOOL
rows=[]
for p,ct,exe,role,cpu0 in identity:
    try:
        assert p.create_time()==ct and p.exe().replace('\\','/').lower()==exe
        c=p.cpu_times();delta=c.user+c.system-cpu0
        row=dict(pid=p.pid,exe=exe,role=role,cpu_delta_s=delta,rss_before_MiB=p.memory_info().rss/2**20)
        if delta>.05:row['action']='preserved_active_sample'
        elif role=='close_preloader' and any(q.name().lower()=='sldworks.exe' for q in psutil.process_iter()):row['action']='preserved_active_solidworks'
        elif role.startswith('close_'):
            p.terminate()
            try:p.wait(timeout=3);row['action']='terminated';row['process_exit_confirmed']=True
            except psutil.TimeoutExpired:row['action']='termination_pending';row['process_exit_confirmed']=False
        else:
            h=k.OpenProcess(0x1000|0x0100,False,p.pid)
            try:row['trim_ok']=bool(h and api.EmptyWorkingSet(h))
            finally:
                if h:k.CloseHandle(h)
            row['action']='working_set_trim_only';row['rss_after_MiB']=p.memory_info().rss/2**20
        rows.append(row)
    except (psutil.AccessDenied,psutil.NoSuchProcess,AssertionError) as e:rows.append(dict(pid=p.pid,action='skipped',error=type(e).__name__))
samples=[]
for _ in range(3):samples.append(psutil.virtual_memory().available/2**20);time.sleep(1)
out=dict(schema='WP10_BACKGROUND_CLEANUP_V21',time_local=datetime.datetime.now().astimezone().isoformat(),before_available_MiB=before,after_samples_MiB=samples,start_threshold_MiB=2048,headroom_target_MiB=2304,threshold_met=min(samples)>=2048,rows=rows,retained=['Codex including its ChatGPT.exe hosts','Claude desktop sessions and Claude Code workers','native CAD and KiCad sessions','MCP services','network, sync, drivers and OS services'],scope='Only verified idle Widgets and SolidWorks preload processes terminated. Claude desktop resident pages trimmed only; pages can return on demand. No settings changed.')
p=A/'results/BACKGROUND_MEMORY_CLEANUP_V21.json';assert not p.exists(),'Do not overwrite cleanup receipt'
p.write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(dict(before_MiB=before,after_samples_MiB=samples,closed=[r['role'] for r in rows if r['action']=='terminated'],trimmed=sum(r.get('trim_ok',False) for r in rows),threshold_met=out['threshold_met'])))
