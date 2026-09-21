"""Trim resident pages only; never stop applications, services, or CAD jobs."""
from pathlib import Path
import ctypes,json,datetime,psutil,argparse,os
R=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args()
out=(R/'results'/args.output).resolve()
assert out.is_relative_to((R/'results').resolve()) and out.suffix=='.json' and not out.exists()
k=ctypes.WinDLL('kernel32',use_last_error=True);a=ctypes.WinDLL('psapi',use_last_error=True)
k.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong];k.OpenProcess.restype=ctypes.c_void_p
k.CloseHandle.argtypes=[ctypes.c_void_p];a.EmptyWorkingSet.argtypes=[ctypes.c_void_p];a.EmptyWorkingSet.restype=ctypes.c_int
names={'sldworks.exe','chrome.exe','claude.exe','weixin.exe','chatgpt.exe'}
report=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),operation='EmptyWorkingSet',available_before_mib=psutil.virtual_memory().available/2**20,processes=[],processes_terminated=False,documents_closed=False,system_settings_changed=False)
for proc in psutil.process_iter(['pid','name','cmdline']):
    name=(proc.info['name'] or '').lower();cmd=' '.join(proc.info['cmdline'] or []).lower().replace('\\','/')
    bridge=(name=='python.exe' and any(s in cmd for s in ['/mcp/','mcp_server','solidworks_mcp.server','skills_bridge_server.py','/aerospace_mcp_skills/']))
    if proc.pid==os.getpid() or not(name in names or bridge):continue
    row=dict(pid=proc.pid,name=name,selection='named_application' if name in names else 'identified_tool_bridge_resident_pages_only');h=None
    try:
        row['rss_before_mib']=proc.memory_info().rss/2**20;h=k.OpenProcess(0x100|0x400,False,proc.pid)
        row['ok']=bool(h and a.EmptyWorkingSet(h));row['rss_after_mib']=proc.memory_info().rss/2**20
        if not row['ok']:row['error_code']=ctypes.get_last_error()
    except (psutil.NoSuchProcess,psutil.AccessDenied) as exc:row['error']=type(exc).__name__
    finally:
        if h:k.CloseHandle(h)
    report['processes'].append(row)
report['available_after_mib']=psutil.virtual_memory().available/2**20
out.write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='processes'}|{'process_count':len(report['processes']),'successful':sum(bool(x.get('ok')) for x in report['processes'])}))
