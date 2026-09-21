"""Read-only cold recovery of artifact left after interruption; no repeated edits."""
from pathlib import Path
import sys,json,importlib.util,traceback
sys.dont_write_bytecode=True
F=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('delta',F/'tools/integrate_ports_native.py');d=importlib.util.module_from_spec(s);s.loader.exec_module(d)
h=d.h;m=d.m
out=F/'results/NATIVE_SERVICE_RECOVERY.json';assert not out.exists()
prior=F/'results/NATIVE_SERVICE.json';r=json.loads(prior.read_text());rows=r['rows'];target=F/'native/WP09F_SERVICE.SLDASM';th=m.sha(target)
r.update(status='RECOVERING_COLD_FILE_AFTER_INTERRUPTION',prior_receipt_sha256=m.sha(prior),prior_status=r['status'],progress=[],native_save=dict(path=str(target),sha256=th,bytes=target.stat().st_size,api_return=None,api_return_status='INTERRUPTED_BEFORE_RECEIPT; COLD_FILE_VALIDATION_ONLY'))
b=None
try:
 b=h.Builder(out,r);sw=b.sw;docs=b.documents()
 if docs:
  assert len(docs)==1 and m.normalized(docs[0][1]['path'])==m.normalized(str(target)) and not docs[0][1]['dirty']
  cold=docs[0][0];r['recovered_session']='RESUMED_PREVIOUS_COLD_REOPEN_AFTER_GUARD_INTERRUPTION'
 else:
  opened=sw.OpenDoc6(str(target),2,195,'',0,0);assert opened[0] is not None and opened[1]==0;cold=b.wrap(opened[0],'IModelDoc2')
 b.activate(cold,target);b.wrap(cold,'IAssemblyDoc').LightweightAllResolved();b.checkpoint('cold_session_attached')
 av=b.wrap(cold.ActiveView,'IModelView');af=b.wrap(cold.FeatureManager,'IFeatureManager');settings=[(sw,'CommandInProgress'),(av,'EnableGraphicsUpdate'),(af,'EnableFeatureTree'),(af,'EnableFeatureTreeWindow')];saved=[(o,k,bool(getattr(o,k))) for o,k in settings]
 try:
  for o,k in settings:setattr(o,k,k=='CommandInProgress')
  _,obs=b.metadata(cold,rows,True);r['cold_components']=obs
 finally:
  for o,k,v in reversed(saved):setattr(o,k,v)
 deps=cold.GetDependencies2(False,True,False) or [];assert {m.normalized(deps[i+1]) for i in range(0,len(deps),2)}=={m.normalized(x['native_path']) for x in rows}
 assert m.sha(target)==th and m.sha(r['parent'])==r['parent_sha256']
 r.update(status='PASS_FIXED_NATIVE_DELTA_WITH_HASH_BOUND_PARENT',component_count=len(obs),expected_solid_count=sum(x.get('expected_solids',1) for x in rows),new_body_count_actual=sum(x.get('actual_solids',0) for x in obs),retained_solid_count_hash_bound=sum(x.get('expected_solids',1) for x in rows[:700]),all_metadata_verified=True,parent_unchanged=True,continuous_motion_verified=False)
 assert r['component_count']==705 and r['expected_solid_count']==1086 and r['new_body_count_actual']==5
 if not m.val(cold,'GetSaveFlag'):b.close_own_saved(cold,target,th)
 assert not b.documents();sw.ExitApp();b.checkpoint('verified_empty_exit')
except Exception as ex:
 r.update(status='FAILED',error=repr(ex),traceback=traceback.format_exc())
 if b:b.checkpoint('failed')
 else:out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
 raise
finally:
 if b:b.pythoncom.CoUninitialize()
