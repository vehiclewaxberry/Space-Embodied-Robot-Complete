from geometry import *
import sys
sys.path.insert(0,str(D.parent/'SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919/tools'))
import native_integrate as ni
ni.OUT=D;ni.configure_com()
rp=D/'results/NATIVE_VOLUME_DIAGNOSTIC.json';r=dict(status='RUNNING',progress=[])
b=ni.PrototypeBuilder(rp,r);sw=b.sw
p=D/'native/R6_MAIN_PCBA_INSTALLED.SLDPRT';oldhash=sha(p)
doc=None
try:
    x=sw.OpenDoc6(str(p),1,3,'',0,0);assert x[0] is not None and x[1]==0
    doc=b.wrap(x[0],'IModelDoc2');ext=b.wrap(doc.Extension,'IModelDocExtension')
    mass=b.wrap(ext.CreateMassProperty2(),'IMassProperty2');mass.AccuracyLevel=2
    r['mass_property2_high_accuracy_volume_mm3']=mass.Volume*1e9
    r['material_databases']=list(sw.GetMaterialDatabases() or [])
    target=D/'cad/DIAGNOSTIC_NATIVE_MAIN_ROUNDTRIP.step'
    r['export_return']=ext.SaveAs(str(target),0,3,None,0,0)
    assert target.is_file();r['roundtrip_sha256']=sha(target)
    sw.CloseDoc(ni.m.val(doc,'GetTitle'));doc=None
    assert sha(p)==oldhash
    r['status']='READ_ONLY_DIAGNOSTIC_COMPLETE';b.checkpoint('complete')
finally:
    if doc is not None:sw.CloseDoc(ni.m.val(doc,'GetTitle'))
    b.pythoncom.CoUninitialize()
