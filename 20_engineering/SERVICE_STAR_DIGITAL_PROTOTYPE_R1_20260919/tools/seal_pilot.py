"""Cold-check the first STEP imported by the desktop MCP, removing source links."""
from native_integrate import *
configure_com();q=read(OUT/'inputs/ALL_IMPORT_PLAN.json')['parts'][0]
rp=OUT/'results/FIRST_MCP_NATIVE_COLD_SEAL.json';assert not rp.exists()
r={'status':'RUNNING','progress':[],'source_sha256':q['source_sha256'],'parts':[]}
b=PrototypeBuilder(rp,r);sw=b.sw;p=Path(q['native_path'])
try:
    assert m.sha(q['step_path'])==q['source_sha256']
    opened=sw.OpenDoc6(str(p),1,1,'',0,0);assert opened[0] is not None and opened[1]==0
    d=b.wrap(opened[0],'IModelDoc2');e=b.wrap(d.Extension,'IModelDocExtension');e.BreakAllExternalFileReferences2(True)
    assert d.ListExternalFileReferencesCount2()==0 and d.ListAuxiliaryExternalFileReferencesCount()==0
    props=b.wrap(e.CustomPropertyManager(''),'ICustomPropertyManager')
    props.Add3('DP_SOURCE_SHA256',30,q['source_sha256'],2);props.Add3('DP_STATUS',30,'GROUND_GEOMETRY_CANDIDATE',2)
    saved=d.Save3(1,0,0);assert saved[0] and saved[1]==0;sw.CloseDoc(m.val(d,'GetTitle'))
    opened=sw.OpenDoc6(str(p),1,3,'',0,0);assert opened[0] is not None and opened[1]==0
    d=b.wrap(opened[0],'IModelDoc2');facts=b.part_facts(d)
    assert facts['solid_count']==q['expected_solids'] and facts['sheet_count']==0
    box=q['expected_local_bbox_mm'];err=m.bbox_max_error(facts['bounds_mm'],{'min_mm':box[0],'max_mm':box[1]})
    assert err<=m.job_linear_tolerance_mm()
    volerr=abs(facts['volume_mm3']-q['expected_volume_mm3']);assert volerr<=max(1e-4,q['expected_volume_mm3']*1e-5)
    sw.CloseDoc(m.val(d,'GetTitle'))
    r.update(status='PASS_FIRST_MCP_NATIVE_COLD_BODY_BOUNDS_VOLUME_AND_NO_EXTERNAL_LINKS',native_path=str(p),
             native_sha256=m.sha(p),facts=facts,bbox_error_mm=err,volume_error_mm3=volerr)
    b.checkpoint('complete')
except Exception as e:
    r.update(status='FAILED',error=str(e),traceback=traceback.format_exc());b.checkpoint('failed');raise
finally:b.pythoncom.CoUninitialize()
