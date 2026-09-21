"""Trim reloadable pages in identified idle Codex tool services, never terminate.

Runtime housekeeping only; does not modify the sealed implementation package.
"""
from pathlib import Path
from ctypes import wintypes
import ctypes
import datetime
import json
import time
import psutil

BASE = Path(__file__).resolve().parents[1]
STAMP = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
ancestor_ids = {p.pid for p in psutil.Process().parents() if p.name().lower() == 'codex.exe'}
assert ancestor_ids, 'No owning Codex ancestor; no processes will be changed'
known_python = ('mcp_server.py', 'mcp_server_pyfluent_preload.py', 'solidworks_mcp.server',
                'skills_bridge_server.py', 'qwen_vision', 'aerospace_mcp_skills',
                'comsol_link', 'workbench mcp')
known_node = ('artifact-template-picker', 'unified-computer-use')
before = psutil.virtual_memory().available / 2**20
selected = []
for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time', 'memory_info', 'cpu_times']):
    try:
        info = proc.info
        command = ' '.join(info['cmdline'] or []).casefold()
        name = (info['name'] or '').lower()
        allow = ((name == 'python.exe' and any(s in command for s in known_python)) or
                 (name == 'node.exe' and any(s in command for s in known_node)))
        if not allow or info['memory_info'].rss < 4 * 2**20:
            continue
        if not ancestor_ids.intersection(p.pid for p in proc.parents()):
            continue
        if any(p.name().lower() not in ('python.exe', 'node.exe', 'conhost.exe') for p in proc.children(recursive=True)):
            continue
        cpu = info['cpu_times'].user + info['cpu_times'].system
        selected.append((proc, info['create_time'], cpu, info['cmdline'], info['memory_info'].rss))
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        continue
time.sleep(1)
kernel = ctypes.WinDLL('kernel32', use_last_error=True)
psapi = ctypes.WinDLL('psapi', use_last_error=True)
kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel.OpenProcess.restype = wintypes.HANDLE
kernel.CloseHandle.argtypes = [wintypes.HANDLE]
kernel.CloseHandle.restype = wintypes.BOOL
psapi.EmptyWorkingSet.argtypes = [wintypes.HANDLE]
psapi.EmptyWorkingSet.restype = wintypes.BOOL
actions = []
for proc, created, cpu, command, rss in selected:
    try:
        now = proc.cpu_times()
        if proc.create_time() != created or proc.cmdline() != command or now.user + now.system - cpu > .02:
            continue
        handle = kernel.OpenProcess(0x1000 | 0x0100, False, proc.pid)
        if not handle:
            actions.append(dict(pid=proc.pid, success=False, error=ctypes.get_last_error()))
            continue
        try:
            success = bool(psapi.EmptyWorkingSet(handle))
            error = None if success else ctypes.get_last_error()
        finally:
            kernel.CloseHandle(handle)
        actions.append(dict(pid=proc.pid, name=proc.name(), creation_time=created,
                            command=command, success=success, error=error,
                            before_rss_MiB=rss / 2**20, after_rss_MiB=proc.memory_info().rss / 2**20))
    except (psutil.NoSuchProcess, psutil.AccessDenied) as error:
        actions.append(dict(pid=proc.pid, success=False, error=str(error)))
after = psutil.virtual_memory().available / 2**20
out = dict(schema='WP10_RUNTIME_IDLE_TOOL_PAGE_RECLAIM', time_local=datetime.datetime.now().astimezone().isoformat(),
           before_available_MiB=before, after_available_MiB=after, actions=actions,
           processes_terminated=[], unsaved_documents_closed=False,
           method='EmptyWorkingSet: reloadable resident pages only, not permanent committed-memory reclamation',
           source='https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-emptyworkingset',
           start_requirement_MiB=2048, start_requirement_met=after >= 2048)
path = BASE / 'logs' / f'idle_tool_memory_{STAMP}.json'
path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps(dict(before_available_MiB=before, after_available_MiB=after,
                      trimmed=sum(a['success'] for a in actions), terminated=0,
                      start_requirement_met=after >= 2048, receipt=str(path))))
