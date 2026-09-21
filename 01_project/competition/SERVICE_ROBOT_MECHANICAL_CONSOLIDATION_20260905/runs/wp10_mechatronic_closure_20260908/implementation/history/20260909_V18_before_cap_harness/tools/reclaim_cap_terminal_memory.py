"""Reuse idle-tool trimming and include newly loaded KiCad/Node MCP services.

Only reloadable resident pages are trimmed after a low-CPU sample. This cannot
prove absence of pending I/O or in-flight MCP work. Preserve processes and dirty state;
never target CAD/browser/editor/OS executables or the active code-mode host.
"""
from pathlib import Path
import sys
A=Path(__file__).resolve().parents[1]
p=A/'tools/reclaim_idle_tool_memory.py'
suffix=sys.argv[1] if len(sys.argv)>1 else 'initial'
assert suffix.replace('_','').isalnum()
s=p.read_text(encoding='utf-8').replace('COLD_PATH_MEMORY_RECOVERY.json','CAP_TERMINAL_MEMORY_RECOVERY_V17_'+suffix+'.json').replace('service_command=cmd,','')
s=s.replace("allow=['mcp_server.py'", "allow=['kicad-mcp-server', 'artifact-template-picker', 'unified-computer-use', 'mcp_server.py'")
s=s.replace("(p.info['name'] or '').casefold()!='python.exe'", "(p.info['name'] or '').casefold() not in ['python.exe','pythonw.exe','node.exe']")
s=s.replace("not in ['python.exe','conhost.exe']", "not in ['python.exe','pythonw.exe','conhost.exe','node.exe','node_repl.exe']")
s=s.replace('before=psutil.virtual_memory()', "excluded_pids={psutil.Process().pid}|{q.pid for q in psutil.Process().parents()}\nbefore=psutil.virtual_memory()")
s=s.replace("        cmd=' '.join", "        if p.pid in excluded_pids:continue\n        cmd=' '.join")
exec(compile(s,str(p),'exec'),{'__file__':str(p),'__name__':'__main__'})
