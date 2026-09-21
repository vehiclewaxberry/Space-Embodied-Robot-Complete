"""Close only the exact unchanged task-owned displayed assembly."""
from pathlib import Path
import sys,json,importlib.util
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('native_display_close',R/'tools/integrate_native_v5.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
rec=json.loads((R/'results/NATIVE_VIEW_PREPARE.json').read_text());p=Path(rec['target']);report=dict(status='CLOSING',progress=[],parts=[],save_attempts=[])
b=m.Builder(R/'results/NATIVE_VIEW_CLOSE.json',report)
try:
    docs=b.documents();assert len(docs)==1
    doc,d=docs[0];assert m.m.normalized(d['path'])==m.m.normalized(p) and not d['dirty']
    b.close_own_saved(doc,p,rec['native_sha256']);assert not b.documents();b.sw.ExitApp();report['status']='EXACT_UNCHANGED_VIEW_CLOSED_EMPTY_SESSION_EXITED';b.checkpoint('closed')
finally:b.pythoncom.CoUninitialize()
