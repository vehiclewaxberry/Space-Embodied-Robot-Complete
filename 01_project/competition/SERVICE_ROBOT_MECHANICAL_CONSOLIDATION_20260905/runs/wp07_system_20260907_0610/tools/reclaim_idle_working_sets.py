"""Reclaim resident pages without terminating applications or discarding documents.

The user authorized unnecessary-background memory cleanup. This narrower action
uses Windows EmptyWorkingSet only on named CAD/browser/chat applications. It does
not change pagefile settings, security, priorities, services, or application files.
"""
from pathlib import Path
import ctypes,json,datetime,psutil
R=Path(__file__).resolve().parents[1]
out=R/'results/MEMORY_WORKING_SET_RECLAIM.json'
assert not out.exists()
names={'sldworks.exe','chrome.exe','claude.exe','weixin.exe'}
k=ctypes.WinDLL('kernel32',use_last_error=True)
a=ctypes.WinDLL('psapi',use_last_error=True)
k.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong];k.OpenProcess.restype=ctypes.c_void_p
k.CloseHandle.argtypes=[ctypes.c_void_p];k.CloseHandle.restype=ctypes.c_int
a.EmptyWorkingSet.argtypes=[ctypes.c_void_p];a.EmptyWorkingSet.restype=ctypes.c_int
report=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),operation='EmptyWorkingSet',
            available_before_mib=psutil.virtual_memory().available/2**20,processes=[],
            processes_terminated=False,documents_closed=False,system_settings_changed=False)
for p in psutil.process_iter(['pid','name']):
    name=(p.info['name'] or '').lower()
    if name not in names:continue
    row=dict(pid=p.pid,name=name)
    handle=None
    try:
        row['rss_before_mib']=p.memory_info().rss/2**20
        handle=k.OpenProcess(0x100|0x400,False,p.pid)
        row['ok']=bool(handle and a.EmptyWorkingSet(handle))
        if not row['ok']:row['error_code']=ctypes.get_last_error()
        row['rss_after_mib']=p.memory_info().rss/2**20
    except (psutil.NoSuchProcess,psutil.AccessDenied) as e:row['error']=type(e).__name__
    finally:
        if handle:k.CloseHandle(handle)
    report['processes'].append(row)
report['available_after_mib']=psutil.virtual_memory().available/2**20
out.write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='processes'}|{'process_count':len(report['processes']),'successful':sum(bool(p.get('ok')) for p in report['processes'])}))
