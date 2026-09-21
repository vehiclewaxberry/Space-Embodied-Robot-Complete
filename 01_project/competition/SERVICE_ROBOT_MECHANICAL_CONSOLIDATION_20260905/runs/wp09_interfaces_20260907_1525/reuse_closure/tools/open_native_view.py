from pathlib import Path
import sys,json,importlib.util
sys.dont_write_bytecode=True
N=Path(__file__).resolve().parents[1];R=N.parent
sp=importlib.util.spec_from_file_location('frozen_view_helper',R/'tools/integrate_native_v5.py');h=importlib.util.module_from_spec(sp);sp.loader.exec_module(h)
target=N/'mechanical/native/WP09R_SERVICE.SLDASM';r=dict(status='RUNNING',progress=[],path=str(target));out=N/'results/NATIVE_VIEW_OPEN.json';b=h.Builder(out,r)
try:
 assert not b.documents(),'User documents left untouched'
 raw=b.sw.OpenDoc6(str(target),2,195,'',0,0);assert raw[0] is not None and raw[1]==0
 model=b.wrap(raw[0],'IModelDoc2');b.activate(model,target)
 model.ShowNamedView2('*Isometric',7);model.ViewZoomtofit2();model.GraphicsRedraw2()
 r.update(status='OPEN_READ_ONLY_LIGHTWEIGHT',save_flag=bool(h.m.val(model,'GetSaveFlag')));b.checkpoint('view_ready')
finally:b.pythoncom.CoUninitialize()
