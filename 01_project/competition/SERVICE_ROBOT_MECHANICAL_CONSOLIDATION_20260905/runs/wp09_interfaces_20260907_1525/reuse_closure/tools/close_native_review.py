from pathlib import Path
import sys,json,importlib.util
sys.dont_write_bytecode=True
N=Path(__file__).resolve().parents[1];R=N.parent
sp=importlib.util.spec_from_file_location('frozen_view_helper',R/'tools/integrate_native_v5.py');h=importlib.util.module_from_spec(sp);sp.loader.exec_module(h)
target=N/'mechanical/native/WP09R_SERVICE.SLDASM';r=dict(status='RUNNING',progress=[],path=str(target));out=N/'results/NATIVE_VIEW_CLEANUP.json';b=h.Builder(out,r)
try:
 docs=b.documents();r['documents']=[x[1] for x in docs]
 assert len(docs)==1 and h.m.normalized(docs[0][1]['path'])==h.m.normalized(str(target))
 assert not docs[0][1]['dirty'],'Leave any modified document open'
 b.close_own_saved(docs[0][0],target,h.m.sha(target));assert not b.documents();b.sw.ExitApp()
 r.update(status='OWN_CLEAN_READONLY_REVIEW_CLOSED',image=str(N/'mechanical/WP09R_SERVICE.bmp'));b.checkpoint('completed')
finally:b.pythoncom.CoUninitialize()
