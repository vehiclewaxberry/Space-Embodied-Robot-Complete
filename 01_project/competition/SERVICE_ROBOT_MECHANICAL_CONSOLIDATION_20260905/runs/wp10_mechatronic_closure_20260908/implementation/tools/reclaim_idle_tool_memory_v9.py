"""Reclaim reloadable resident pages of idle Codex tool services, never kill apps.

Authorized memory cleanup. Restrict to known Python tool-service command lines
under a running codex.exe ancestor and unchanged process identity. Do not stop
servers, solvers, CAD sessions, browsers, editors or OS services.
"""
from pathlib import Path
import psutil,ctypes,json,time,datetime
from ctypes import wintypes
A=Path(__file__).resolve().parents[1]
allow=['mcp_server.py','mcp_server_pyfluent_preload.py','solidworks_mcp.server','skills_bridge_server.py','qwen_vision','aerospace_mcp_skills','comsol_link','workbench mcp']
before=psutil.virtual_memory().available/2**20;selected=[]
for p in psutil.process_iter(['pid','name','cmdline','create_time','memory_info','cpu_times']):
    try:
        cmd=' '.join(p.info['cmdline'] or []).casefold()
        if (p.info['name'] or '').casefold()!='python.exe' or not any(a in cmd for a in allow):continue
        if not any(q.name().casefold()=='codex.exe' for q in p.parents()):continue
        if any(q.name().casefold() not in ['python.exe','conhost.exe'] for q in p.children(recursive=True)):continue
        cpu=p.info['cpu_times'];selected.append((p,p.info['create_time'],cpu.user+cpu.system,cmd,p.info['memory_info'].rss/2**20))
    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
time.sleep(.8)
kernel=ctypes.WinDLL('kernel32',use_last_error=True);psapi=ctypes.WinDLL('psapi',use_last_error=True)
kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle.restype=wintypes.BOOL
psapi.EmptyWorkingSet.argtypes=[wintypes.HANDLE];psapi.EmptyWorkingSet.restype=wintypes.BOOL
rows=[]
for p,created,cpu,cmd,rss in selected:
    try:
        now=p.cpu_times()
        if abs(p.create_time()-created)>.01 or now.user+now.system-cpu>.05:continue
        handle=kernel.OpenProcess(0x1000|0x0100,False,p.pid)
        if not handle:rows.append(dict(pid=p.pid,success=False,error=ctypes.get_last_error()));continue
        ok=bool(psapi.EmptyWorkingSet(handle));err=ctypes.get_last_error() if not ok else None;kernel.CloseHandle(handle)
        rows.append(dict(pid=p.pid,create_time=created,service_command=cmd,rss_before_MiB=rss,rss_after_MiB=p.memory_info().rss/2**20,success=ok,error=err))
    except (psutil.NoSuchProcess,psutil.AccessDenied) as e:rows.append(dict(pid=p.pid,success=False,error=str(e)))
after=psutil.virtual_memory().available/2**20
out=dict(schema='WP10_IDLE_CODEX_TOOL_WORKING_SET_RECLAIM_V9',time_local=datetime.datetime.now().astimezone().isoformat(),before_available_MiB=before,after_available_MiB=after,rows=rows,processes_terminated=[],method='Microsoft psapi EmptyWorkingSet; pages may be faulted back on demand; not process termination or permanent memory guarantee',api_source='https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-emptyworkingset',permission_basis='User requested background memory cleanup; only identified idle Codex tool services have reloadable resident pages trimmed')
(A/'results/PROP_ROUTING_MEMORY_RECOVERY.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(dict(before_MiB=before,after_MiB=after,trimmed=sum(r['success'] for r in rows),terminated=0)))

