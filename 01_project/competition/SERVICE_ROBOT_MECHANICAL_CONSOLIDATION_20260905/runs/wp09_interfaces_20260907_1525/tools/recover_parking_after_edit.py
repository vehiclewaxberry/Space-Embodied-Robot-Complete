"""Finish exact task-owned edited parking document after guard interruption."""
from pathlib import Path
import sys,json,importlib.util,gc,traceback
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location('native_resume_base',R/'tools/integrate_native_v5.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
oldp=R/'results/NATIVE_PARKING.json';old=json.loads(oldp.read_text());rows=old['rows']
assert old['progress'] and any(p.get('stage')=='inserted' and p.get('count')==82 for p in old['progress'])
target=R/'native/WP09_PARKING.SLDASM';work=R/'native/work/W_parking.SLDASM'
out=R/'results/NATIVE_PARKING_RECOVERY.json';assert not out.exists()
report=dict(status='RECOVERY_RUNNING',state='parking',rows=rows,new_instance_ids=old['new_instance_ids'],progress=[],parts=[],save_attempts=[],prior_receipt_sha256=m.m.sha(oldp),parent=old['parent'],parent_sha256=old['parent_sha256'],parent_receipt_path=old['parent_receipt_path'],parent_receipt_sha256=old['parent_receipt_sha256'],parent_independent_check_sha256=old['parent_independent_check_sha256'],coordinate_frame=old['coordinate_frame'],basis_probe_scope=old['basis_probe_scope'],retained_body_evidence=old['retained_body_evidence'],manufacturing_release=False,mate_based_motion=False)
b=m.Builder(out,report)
try:
    assert m.m.sha(old['parent'])==old['parent_sha256']
    assert m.m.sha(old['parent_receipt_path'])==old['parent_receipt_sha256']
    docs=b.documents();report['documents_before']=[d for _,d in docs];assert len(docs)<=1
    b.checkpoint('recovery_input_recorded')
    if target.exists():
        if 'native_save' in old:
            assert m.m.sha(target)==old['native_save']['sha256'];report['native_save']=old['native_save']
        else:
            acknowledged=[x for x in old['save_attempts'] if m.m.normalized(x.get('path',''))==m.m.normalized(target) and x.get('ok') is True]
            assert acknowledged
            report['native_save']=dict(path=str(target),sha256=m.m.sha(target),bytes=target.stat().st_size,ok=True,errors=acknowledged[-1].get('errors'),warnings=acknowledged[-1].get('warnings'),hash_source='OBSERVED_AFTER_INTERRUPT_OF_ACKNOWLEDGED_SAVE; VALIDATED_BY_FULL_METADATA_AND_NEW_BODY_COLD_READ')
        for doc,d in docs:
            assert m.m.normalized(d['path'])==m.m.normalized(target) and not d['dirty'];b.close_own_saved(doc,target,m.m.sha(target))
    else:
        assert len(docs)==1 and m.m.normalized(docs[0][1]['path'])==m.m.normalized(work)
        assert m.m.sha(work)==old['parent_sha256']
        model=docs[0][0];b.activate(model,work);asm=b.wrap(model,'IAssemblyDoc')
        b.identity_inventory(asm,rows);report['live_exact_701_identities_verified']=True
        report['native_save']=b.save_new(model,target)
        b.close_own_saved(model,target,report['native_save']['sha256']);model=asm=None;gc.collect()
    b.sw.CommandInProgress=old['ui_before']['CommandInProgress'];assert not b.documents()
    b.checkpoint('saved_exact_edited_document_no_rebuild')
    opened=b.sw.OpenDoc6(str(target),2,195,'',0,0);assert opened[0] is not None and opened[1]==0
    cold=b.wrap(opened[0],'IModelDoc2');b.activate(cold,target);av=b.wrap(cold.ActiveView,'IModelView');af=b.wrap(cold.FeatureManager,'IFeatureManager')
    settings=[(b.sw,'CommandInProgress'),(av,'EnableGraphicsUpdate'),(af,'EnableFeatureTree'),(af,'EnableFeatureTreeWindow')]
    prior=[(o,k,old['ui_before'][k]) for o,k in settings];report['restored_ui_source']='ORIGINAL_PERSISTED_PREEDIT_SNAPSHOT';b.checkpoint('ui_restore_source_recorded')
    try:
        for o,k in settings:setattr(o,k,k=='CommandInProgress')
        _,obs=b.metadata(cold,rows,True);report['cold_components']=obs
    finally:
        for o,k,v in reversed(prior):setattr(o,k,v)
    assert m.m.sha(target)==report['native_save']['sha256']
    deps=cold.GetDependencies2(False,True,False) or []
    assert {m.m.normalized(deps[i+1]) for i in range(0,len(deps),2)}=={m.m.normalized(r['native_path']) for r in rows}
    c=json.loads((R/'inputs/INTEGRATION_HARNESS_CONTRACT_V6.json').read_text());assert all(m.m.sha(p)==h for p,h in c['source_inputs'].items())
    report.update(status='PASS_FIXED_POSE_NATIVE_NEW_BODY_AND_ALL_METADATA_WITH_HASH_BOUND_PARENT',component_count=len(obs),solid_count=sum(r.get('expected_solids',1) for r in rows),new_body_count_actual=sum(x.get('actual_solids',0) for x in obs),retained_solid_count_hash_bound=sum(r.get('expected_solids',1) for r in rows[:619]),body_counts_are_actual=False,continuous_motion_verified=False,full_dependency_set_verified=True,frozen_inputs_unchanged=True)
    b.close_own_saved(cold,target,report['native_save']['sha256']);assert not b.documents();b.sw.ExitApp();b.checkpoint('recovery_verified_empty_exit')
except Exception as ex:
    report.update(status='FAILED',error=repr(ex),traceback=traceback.format_exc());b.checkpoint('failed');raise
finally:b.pythoncom.CoUninitialize()
