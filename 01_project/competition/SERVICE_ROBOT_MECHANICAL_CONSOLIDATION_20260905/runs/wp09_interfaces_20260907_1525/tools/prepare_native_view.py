"""Read-only display of the verified service assembly; no save or body rebuild."""
from pathlib import Path
import sys,json,importlib.util
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('native_display_base',R/'tools/integrate_native_v5.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
rec=json.loads((R/'results/NATIVE_SERVICE_RECOVERY.json').read_text());p=Path(rec['target']);assert m.m.sha(p)==rec['native_sha256']
out=R/'results/NATIVE_VIEW_PREPARE.json';assert not out.exists();report=dict(status='PREPARING',target=str(p),native_sha256=rec['native_sha256'],parts=[],progress=[],save_attempts=[])
b=m.Builder(out,report)
try:
    assert not b.documents(),'Existing documents left untouched'
    opened=b.sw.OpenDoc6(str(p),2,195,'',0,0);assert opened[0] is not None and opened[1]==0
    doc=b.wrap(opened[0],'IModelDoc2');b.activate(doc,p)
    av=b.wrap(doc.ActiveView,'IModelView');av.EnableGraphicsUpdate=True
    doc.ShowNamedView2('',7);doc.ViewZoomtofit2();doc.GraphicsRedraw2()
    assert m.m.sha(p)==rec['native_sha256'] and not m.m.val(doc,'GetSaveFlag')
    report.update(status='READ_ONLY_SERVICE_VIEW_PREPARED',projection='ISOMETRIC',actual_image_captured=False);b.checkpoint('view_prepared')
finally:b.pythoncom.CoUninitialize()
