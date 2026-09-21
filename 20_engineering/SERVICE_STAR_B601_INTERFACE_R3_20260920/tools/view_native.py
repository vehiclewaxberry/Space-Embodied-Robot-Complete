"""Read-only capture of the newly saved R3 assembly; no source document saved."""
from pathlib import Path
import sys,json,hashlib,time
D=Path(__file__).resolve().parents[1];sys.path.insert(0,str(D.parent/'SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919/tools'))
import native_integrate as ni
ni.OUT=D
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
r=json.loads((D/'results/NATIVE_ASSEMBLY_DELIVERY.json').read_text(encoding='utf-8'));assert r['status']=='PASS_R3_LOCAL_FIXED_POSE_NATIVE_ASSEMBLY'
report={'status':'RUNNING','progress':[],'parts':[],'save_attempts':[]};rp=D/'results/NATIVE_VIEW_V2.json';assert not rp.exists()
ni.configure_com();b=ni.PrototypeBuilder(rp,report);sw=b.sw
try:
    part=Path(r['parts'][0]['target']);expected=r['parts'][0]['native_save']['sha256'];assert sha(part)==expected
    opened=sw.OpenDoc6(str(part),1,3,'',0,0);assert opened[0] is not None and opened[1]==0;doc=b.wrap(opened[0],'IModelDoc2')
    partdoc=b.wrap(doc,'IPartDoc')
    material=partdoc.GetMaterialPropertyName2('')
    report['new_part_material_name']=material
    report['new_part_material_scope']='No new material assignment requested; placeholder assembly'
    sw.CloseDoc(ni.m.val(doc,'GetTitle'));assert sha(part)==expected
    target=Path(r['service']['saved']['path']);assert sha(target)==r['service']['saved']['sha256']
    opened=sw.OpenDoc6(str(target),2,5,'',0,0);assert opened[0] is not None and opened[1]==0;doc=b.wrap(opened[0],'IModelDoc2')
    sw.DocumentVisible(True,1);sw.DocumentVisible(True,2);doc.Visible=True;sw.ActivateDoc3(ni.m.val(doc,'GetTitle'),False,0,0)
    view=b.wrap(doc.ActiveView,'IModelView');view.EnableGraphicsUpdate=True
    doc.ShowNamedView2('',7);doc.ViewZoomtofit2();doc.GraphicsRedraw2()
    b.pythoncom.PumpWaitingMessages();time.sleep(2);doc.GraphicsRedraw2()
    bmp=D/'views/SERVICE_STAR_SERVICE_R3_V2.bmp';assert doc.SaveBMP(str(bmp),1600,1200)
    from PIL import Image
    png=bmp.with_suffix('.png');im=Image.open(bmp);im.save(png);nonblank=any(b-a>10 for a,b in im.convert('RGB').getextrema())
    report.update(status='CAPTURED_PENDING_VISUAL_REVIEW' if nonblank else 'FAILED_BLANK_CAPTURE',path=str(target),native_sha256=sha(target),png_path=str(png),png_sha256=sha(png),cold_errors=opened[1],cold_warnings=opened[2],actual_native_capture=True,nonblank=nonblank)
    sw.CloseDoc(ni.m.val(doc,'GetTitle'));assert sha(target)==r['service']['saved']['sha256'];b.checkpoint('complete')
except Exception as e:
    report.update(status='FAILED',error=str(e));b.checkpoint('failed');raise
finally:
    b.pythoncom.CoUninitialize()
