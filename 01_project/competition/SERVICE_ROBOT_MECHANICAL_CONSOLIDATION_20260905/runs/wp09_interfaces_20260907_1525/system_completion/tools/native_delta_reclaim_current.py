"""Current explicitly observed Codex desktop backend; reversible page reclamation."""
from pathlib import Path
import psutil
C=Path(__file__).resolve().parents[1]
assert not [p for p in psutil.process_iter(['name']) if p.info['name'].lower()=='sldworks.exe']
p=psutil.Process(8876);assert p.name().lower()=='codex.exe' and 'app-server' in p.cmdline() and any('OpenAI\\Codex\\bin\\' in x for x in p.cmdline())
source=C/'tools/reclaim_idle_tool_working_sets.py';code=source.read_text(encoding='utf-8');assert 'psutil.Process(30448)' in code
exec(compile(code.replace('psutil.Process(30448)','psutil.Process(8876)'),str(source),'exec'),{'__file__':str(source),'__name__':'__main__'})
