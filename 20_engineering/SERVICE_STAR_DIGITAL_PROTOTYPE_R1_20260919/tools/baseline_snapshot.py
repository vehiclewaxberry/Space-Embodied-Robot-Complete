"""Show the actually available 873-leaf material-updated native host, not the planned 1110 model."""
from native_integrate import *
configure_com()
rp=OUT/'results/BASELINE_NATIVE_VIEW.json'
assert not rp.exists()
r={'status':'RUNNING','progress':[],'scope':'ACTUAL_873_LEAF_HOST_COPY_WITH_PARTIAL_MATERIAL_ASSIGNMENTS',
   'planned_1110_integration_shown':False,'whole_design_complete':False}
b=PrototypeBuilder(rp,r);sw=b.sw
target=OUT/'native/WP09D_SERVICE.SLDASM';digest=m.sha(target)
try:
    sw.DocumentVisible(True,2)
    opened=sw.OpenDoc6(str(target),2,5,'',0,0);assert opened[0] is not None and opened[1]==0
    d=b.wrap(opened[0],'IModelDoc2');b.activate(d,target)
    d.ShowNamedView2('',7);d.ViewZoomtofit2();d.GraphicsRedraw2()
    bmp=OUT/'views/BASELINE_873_NATIVE.bmp';assert d.SaveBMP(str(bmp),1600,1200)
    from PIL import Image
    png=bmp.with_suffix('.png');Image.open(bmp).save(png)
    sw.CloseDoc(m.val(d,'GetTitle'));assert m.sha(target)==digest
    r.update(status='PASS_ACTUAL_NATIVE_BASELINE_VIEW_ONLY',native_path=str(target),native_sha256=digest,
             png_path=str(png),png_sha256=m.sha(png),open_errors=opened[1],open_warnings=opened[2])
    b.checkpoint('complete')
except Exception as e:
    r.update(status='FAILED',error=str(e),traceback=traceback.format_exc());b.checkpoint('failed');raise
finally:b.pythoncom.CoUninitialize()
