"""Reclaim pageable working sets of identified unused tool servers; never terminate them.

User authorized memory cleanup before retry. No document/process termination,
service stop, priority change, page-file setting change or persistent OS mutation.
"""
import ctypes,json,time
from ctypes import wintypes as W
from pathlib import Path
from datetime import datetime,timezone
import psutil
C=Path(__file__).resolve().parents[1]
known_unused_markers=(
 'CAE-Agent-Hub\\MCP\\Abaqus\\',
 'CAE-Agent-Hub\\MCP\\Ansys\\Fluent MCP\\',
 'CAE-Agent-Hub\\MCP\\Ansys\\Workbench MCP\\',
 'CAE-Agent-Hub\\MCP\\Ansys\\AEDT MCP\\',
 'academic\\comsol_link\\',
 'Aerospace_MCP_Skills\\skills\\vibration_control.py',
 'Aerospace_MCP_Skills\\skills\\ancf_kinematics.py',
)
# Require the exact observed current Codex backend identity and command-line subtree.
backend=psutil.Process(30448)
assert backend.name().lower()=='codex.exe'
before=psutil.virtual_memory().available/2**20
kernel=ctypes.WinDLL('kernel32',use_last_error=True)
kernel.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];kernel.OpenProcess.restype=W.HANDLE
kernel.K32EmptyWorkingSet.argtypes=[W.HANDLE];kernel.K32EmptyWorkingSet.restype=W.BOOL
kernel.CloseHandle.argtypes=[W.HANDLE];kernel.CloseHandle.restype=W.BOOL
targets=[]
for p in backend.children(recursive=True):
    try:
        if p.name().lower() not in ('python.exe','pythonw.exe'):continue
        command=' '.join(p.cmdline())
        if not any(x.casefold() in command.casefold() for x in known_unused_markers):continue
        if 'solidworks' in command.casefold() or 'system_completion' in command.casefold():continue
        targets.append((p,p.create_time(),command,p.cpu_times(),p.memory_info().rss))
    except (psutil.NoSuchProcess,psutil.AccessDenied):continue
# Verify the observed servers are quiescent; skip any consuming work during observation.
time.sleep(1.5)
rows=[]
for p,created,command,cpu,rss in targets:
    row={'pid':p.pid,'create_time':created,'command':command,'rss_before_MiB':rss/2**20}
    try:
        assert p.create_time()==created
        now=p.cpu_times();busy=(now.user+now.system)-(cpu.user+cpu.system)
        row['cpu_seconds_during_observation']=busy
        if busy>.05:
            row['status']='SKIPPED_ACTIVE';rows.append(row);continue
        # Query information + set-quota permissions, sufficient for EmptyWorkingSet.
        handle=kernel.OpenProcess(0x0400|0x0100,False,p.pid)
        if not handle:
            row.update(status='OPEN_DENIED',winerror=ctypes.get_last_error())
        else:
            try:
                ok=bool(kernel.K32EmptyWorkingSet(handle))
                row.update(status='WORKING_SET_RECLAIMED' if ok else 'RECLAIM_DENIED',winerror=0 if ok else ctypes.get_last_error())
            finally:kernel.CloseHandle(handle)
        row['rss_after_MiB']=p.memory_info().rss/2**20
        row['same_process_alive']=p.is_running() and p.create_time()==created
    except psutil.NoSuchProcess:row['status']='EXITED_INDEPENDENTLY'
    rows.append(row)
time.sleep(.5)
after=psutil.virtual_memory().available/2**20
report={'utc':datetime.now(timezone.utc).isoformat(),'status':'READ_IDENTIFIED_IDLE_TOOL_SERVERS_AND_RECLAIM_PAGEABLE_WORKING_SETS',
 'available_before_MiB':before,'available_after_MiB':after,'observed_available_change_MiB':after-before,
 'processes_terminated':0,'services_stopped':0,'files_modified_outside_task':0,
 'scope':'Observed current Codex backend descendants matching exact unused simulation tool server paths; no SolidWorks/CAD job, browser, user document or OS service.',
 'reclaim_success_count':sum(r['status']=='WORKING_SET_RECLAIMED' for r in rows),'rows':rows,
 'note':'Available RAM is a concurrent-system observation; pages can fault back if a server is used. This does not guarantee future memory availability.'}
stamp=datetime.now(timezone.utc).strftime('%H%M%S')
out=C/'results'/('MEMORY_RECLAIM_'+stamp+'.json')
out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({**{k:v for k,v in report.items() if k!='rows'},'receipt':str(out)},ensure_ascii=False))
