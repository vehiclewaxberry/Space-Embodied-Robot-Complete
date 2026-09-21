"""Read-only cold proof of relocated native identities, transforms and references."""
from pathlib import Path
import sys,json,importlib.util,traceback,argparse,gc
sys.dont_write_bytecode=True
C=Path(__file__).resolve().parents[1];R=C.parent
sp=importlib.util.spec_from_file_location('portable_frozen_helper',R/'tools/integrate_native_v5.py');h=importlib.util.module_from_spec(sp);sp.loader.exec_module(h);m=h.m
ap=argparse.ArgumentParser();ap.add_argument('location',choices=['primary','relocated']);a=ap.parse_args()
j=json.loads((C/'results/PORTABLE_INPUTS.json').read_text());copy_receipt=json.loads((C/'results/PORTABLE_COPY_V2.json').read_text())
assert copy_receipt['status']=='PASS_NATIVE_COPY_AND_STORED_LOCAL_DEPENDENCIES_COLD_OPEN_PENDING'
base=C/'mechanical/portable';P=base/('package' if a.location=='primary' else 'relocation_trial/package')
if a.location=='relocated':assert not (base/'package').exists(),'Old package must be absent during the moved-root test'
out=C/'results'/('PORTABLE_COLD_'+a.location.upper()+'.json');assert not out.exists()
r={'status':'RUNNING','location':a.location,'root':str(P),'progress':[],'states':{},'all_parts_byte_identical_to_parent':False,
   'solid_measurements_this_task':0,'body_count_credit':'Inherited from sealed 705-component native receipts via identical SLDPRT SHA256; 1081 prior bodies and 5 port bodies',
   'manufacturing_release':False,'continuous_motion_verified':False,'all_external_dependencies_zero':False}
b=None
try:
 b=h.Builder(out,r);sw=b.sw;assert not b.documents(),'Existing documents left untouched'
 r['session_start_empty']=True;r['solidworks_revision']=str(m.val(sw,'RevisionNumber'))
 for state,s in j['states'].items():
  b.ram_floor();assert not b.documents()
  target=P/s['target_name'];saved_sha=copy_receipt['states'][state]['sha256'];assert m.sha(target)==saved_sha
  rows=[dict(q,native_path=str(P/q['copy_name']),native_sha256=q['source_sha256'],T_S_local=q['native_T_local_to_S']) for q in s['rows']]
  before={str(P/q['copy_name']):q['source_sha256'] for q in rows}
  assert all(m.sha(p)==v for p,v in before.items());b.checkpoint('cold_open_started',state=state)
  opened=sw.OpenDoc6(str(target),2,195,'',0,0)
  r['states'][state]={'path':str(target),'sha256':saved_sha,'open_errors':opened[1],'open_warnings':opened[2]}
  assert opened[0] is not None and opened[1]==0,'Actual cold open failed'
  model=b.wrap(opened[0],'IModelDoc2');b.activate(model,target)
  av=b.wrap(model.ActiveView,'IModelView');af=b.wrap(model.FeatureManager,'IFeatureManager')
  settings=[(sw,'CommandInProgress'),(av,'EnableGraphicsUpdate'),(af,'EnableFeatureTree'),(af,'EnableFeatureTreeWindow')]
  saved=[(o,k,bool(getattr(o,k))) for o,k in settings]
  try:
   for o,k in settings:setattr(o,k,k=='CommandInProgress')
   lookup,observed=b.metadata(model,rows,False)
  finally:
   for o,k,v in reversed(saved):setattr(o,k,v)
  original={q['id']:q for q in s['rows']}
  error=max(abs(v-w) for q in observed for v,w in zip(q['transform_sw16'],original[q['id']]['transform_sw16']))
  assert error<=1e-8 and len(observed)==705
  deps=model.GetDependencies2(True,True,False) or [];paths=[deps[i+1] for i in range(0,len(deps),2)]
  assert {m.normalized(p) for p in paths}=={m.normalized(p) for p in before}
  external=[p for p in paths if not Path(p).resolve().is_relative_to(P.resolve())];assert not external
  assert all(m.sha(p)==v for p,v in before.items()) and m.sha(target)==saved_sha
  r['states'][state].update(status='PASS_COLD_IDENTITY_TRANSFORM_LOCAL_DEPENDENCIES',components=observed,component_count=705,
     expected_solid_count_hash_bound=sum(q['expected_solids'] for q in rows),unique_part_files=len(before),
     max_transform_sw16_error=error,external_dependency_count=0,dependencies=paths,read_only=True,
     dirty_after_inspection=bool(m.val(model,'GetSaveFlag')),source_native_part_hashes_unchanged=True)
  assert not m.val(model,'GetSaveFlag'),'Unexpected dirty read-only document left open'
  lookup=None;settings=saved=[];av=af=None;gc.collect()
  b.close_own_saved(model,target,saved_sha);model=av=af=observed=None;gc.collect()
  assert not b.documents();b.checkpoint('cold_state_verified_closed',state=state,components=705)
 assert all(m.sha(p)==d for p,d in j['input_sha256'].items())
 for q in j['parts']:assert m.sha(P/q['copy_name'])==q['source_sha256'] and m.sha(q['source'])==q['source_sha256']
 r.update(status='PASS_ALL_THREE_COLD_PORTABLE_STATES',all_parts_byte_identical_to_parent=True,all_external_dependencies_zero=True,
          source_inputs_unchanged=True,open_documents_after=[],physical_path_relocation_test=(a.location=='relocated'))
 sw.ExitApp();b.checkpoint('verified_empty_exit')
except Exception as exc:
 r.update(status='FAILED',error=repr(exc),traceback=traceback.format_exc())
 if b:b.checkpoint('failed')
 else:out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
 raise
finally:
 if b:b.pythoncom.CoUninitialize()
