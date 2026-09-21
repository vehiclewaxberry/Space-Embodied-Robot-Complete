"""Cold recheck the exact saved assembly after a guard time limit; no reconstruction."""
from pathlib import Path
import sys,json,importlib.util,traceback
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('bounded_native_v2',R/'tools/integrate_native_v2.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
oldp=R/'results/NATIVE_SERVICE.json';old=json.loads(oldp.read_text());target=Path(old['native_save']['path']);assert m.m.sha(target)==old['native_save']['sha256']
rp=R/'results/NATIVE_SERVICE_RECOVERY.json';assert not rp.exists()
report=dict(status='COLD_RECOVERY_RUNNING',prior_receipt_sha256=m.m.sha(oldp),target=str(target),native_sha256=m.m.sha(target),coordinate_frame=old['coordinate_frame'],progress=[],save_attempts=[],parts=[],new_instance_ids=[r['id'] for r in old['rows'][619:]],basis_probe_scope='NEW_82_INSTANCES; FULL_MATRIX_READBACK_ALL_701',native_rebuilt=False)
b=m.Builder(rp,report)
try:
    docs=b.documents();report['documents_before']=[d for _,d in docs]
    for doc,d in docs:
        assert m.m.normalized(d['path'])==m.m.normalized(target) and not d['dirty'],'Unexpected/dirty doc left untouched'
        b.close_own_saved(doc,target,report['native_sha256'])
    assert not b.documents();b.sw.CommandInProgress=old['ui_before']['CommandInProgress'];b.checkpoint('interrupted_saved_doc_closed_global_command_restored')
    opened=b.sw.OpenDoc6(str(target),2,195,'',0,0);assert opened[0] is not None and opened[1]==0
    model=b.wrap(opened[0],'IModelDoc2');b.activate(model,target);av=b.wrap(model.ActiveView,'IModelView');af=b.wrap(model.FeatureManager,'IFeatureManager')
    settings=[(b.sw,'CommandInProgress'),(av,'EnableGraphicsUpdate'),(af,'EnableFeatureTree'),(af,'EnableFeatureTreeWindow')];prior=[(o,k,bool(getattr(o,k))) for o,k in settings];report['ui_before']={k:v for _,k,v in prior};b.checkpoint('cold_settings_persisted')
    try:
        for o,k in settings:setattr(o,k,k=='CommandInProgress')
        _,rows=b.metadata(model,old['rows'],True);report['cold_components']=rows
    finally:
        for o,k,v in reversed(prior):setattr(o,k,v)
    assert m.m.sha(target)==report['native_sha256']
    deps=model.GetDependencies2(False,True,False) or [];assert {m.m.normalized(deps[i+1]) for i in range(0,len(deps),2)}=={m.m.normalized(r['native_path']) for r in old['rows']}
    report.update(status='PASS_FIXED_POSE_NATIVE_DELTA_COLD_BODY_AND_TRANSFORM_CHECK',component_count=len(rows),solid_count=sum(r['actual_solids'] for r in rows),parent_sha256=old['parent_sha256'],full_dependency_set_verified=True,actual_body_counts=True,continuous_motion_verified=False)
    b.close_own_saved(model,target,report['native_sha256']);assert not b.documents();b.sw.ExitApp();b.checkpoint('recovery_verified_empty_exit')
except Exception as ex:
    report.update(status='FAILED',error=repr(ex),traceback=traceback.format_exc());b.checkpoint('failed');raise
finally:b.pythoncom.CoUninitialize()
