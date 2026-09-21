"""Capture the actual new native service assembly without saving CAD changes."""
from native_integrate import *
from PIL import Image,ImageStat
rp=OUT/'results/NATIVE_SERVICE_VIEW.json';assert not rp.exists()
target=OUT/'native/SERVICE_STAR_SERVICE_R1.SLDASM';before=m.sha(target)
r={'status':'RUNNING','progress':[],'native_path':str(target),'native_sha256':before,'visual_review_accepted':False}
configure_com();b=PrototypeBuilder(rp,r);sw=b.sw
try:
    sw.DocumentVisible(True,1);sw.DocumentVisible(True,2)
    opened=sw.OpenDoc6(str(target),2,1,'',0,0);assert opened[0] is not None and opened[1]==0
    d=b.wrap(opened[0],'IModelDoc2');r['open_errors']=opened[1];r['open_warnings']=opened[2]
    sw.ActivateDoc3(m.val(d,'GetTitle'),False,0,0)
    d.ShowNamedView2('',7);d.ViewZoomtofit2();d.GraphicsRedraw2()
    bmp=OUT/'views/INTEGRATED_NATIVE_SERVICE.bmp';assert d.SaveBMP(str(bmp),1800,1200)
    png=bmp.with_suffix('.png');im=Image.open(bmp).convert('RGB');im.save(png)
    r.update(png_path=str(png),png_sha256=m.sha(png),pixel_standard_deviation=ImageStat.Stat(im).stddev,
             status='CAPTURED_ACTUAL_NATIVE_AWAITING_VISUAL_REVIEW')
    sw.CloseDoc(m.val(d,'GetTitle'));assert m.sha(target)==before
    b.checkpoint('captured_without_CAD_save')
except Exception as ex:
    r.update(status='FAILED',error=str(ex),traceback=traceback.format_exc());b.checkpoint('failed');raise
finally:b.pythoncom.CoUninitialize()
