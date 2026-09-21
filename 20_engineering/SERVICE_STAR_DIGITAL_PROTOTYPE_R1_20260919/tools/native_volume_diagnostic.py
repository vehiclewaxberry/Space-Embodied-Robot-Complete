"""Read-only native volume accuracy check and isolated neutral export."""
from native_integrate import *
q=read(OUT/'inputs/ALL_IMPORT_PLAN.json')['parts'][35]
rp=OUT/'results/NATIVE_VOLUME_DIAGNOSTIC_2883.json';assert not rp.exists()
target=OUT/'diagnostics/I_2883cdc18626958a_native_roundtrip.step';target.parent.mkdir(exist_ok=True);assert not target.exists()
r={'status':'RUNNING','progress':[],'source_sha256':q['source_sha256'],'native_path':q['native_path'],
   'api_source':'https://help.solidworks.com/2026/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.imodeldocextension~getmassproperties2.html'}
configure_com();b=PrototypeBuilder(rp,r);sw=b.sw
try:
    before=m.sha(q['native_path']);opened=sw.OpenDoc6(q['native_path'],1,3,'',0,0);assert opened[0] is not None and opened[1]==0
    d=b.wrap(opened[0],'IModelDoc2');e=b.wrap(d.Extension,'IModelDocExtension')
    r['native_facts']=b.part_facts(d);r['accuracy_results']=[]
    for accuracy in (0,1,2):
        v=e.GetMassProperties2(accuracy,0,False)
        r['accuracy_results'].append({'accuracy':accuracy,'api_status':v[1],'volume_mm3':v[0][3]*1e9})
    saved=e.SaveAs(str(target),0,1,None,0,0);assert saved[0] and saved[1]==0,saved
    sw.CloseDoc(m.val(d,'GetTitle'));assert m.sha(q['native_path'])==before
    r.update(status='DIAGNOSTIC_EXPORTED_NO_PASS_CREDIT',native_sha256=before,
       roundtrip_step=str(target),roundtrip_sha256=m.sha(target),export_api=saved)
    b.checkpoint('complete')
except Exception as ex:
    r.update(status='FAILED',error=str(ex),traceback=traceback.format_exc());b.checkpoint('failed');raise
finally:b.pythoncom.CoUninitialize()
