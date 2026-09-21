"""Use SolidWorks CopyDocument once per closed assembly with explicit child mapping."""
from pathlib import Path
import sys,json,importlib.util,traceback
sys.dont_write_bytecode=True
C=Path(__file__).resolve().parents[1];R=C.parent
sp=importlib.util.spec_from_file_location('frozen_native_helper',R/'tools/integrate_native_v5.py');h=importlib.util.module_from_spec(sp);sp.loader.exec_module(h);m=h.m
j=json.loads((C/'results/PORTABLE_INPUTS.json').read_text(encoding='utf-8'))
P=Path(j['copy_root']).resolve();P.mkdir(exist_ok=True)
out=C/'results/PORTABLE_COPY.json';assert not out.exists()
r={'status':'RUNNING','method':'ISldWorks.CopyDocument','progress':[],'states':{},'parts':[],'manufacturing_release':False,'regenerated_solids':False}
b=None
try:
 b=h.Builder(out,r);sw=b.sw;assert not b.documents(),'Unexpected documents left untouched'
 r['solidworks_revision']=str(m.val(sw,'RevisionNumber'))
 for state,s in j['states'].items():
  b.ram_floor();target=P/s['target_name'];assert not target.exists()
  unique={m.normalized(q['source']):q for q in s['rows']}
  before=[q['source'] for q in unique.values()];after=[str(P/q['copy_name']) for q in unique.values()]
  assert all(Path(p).resolve().is_relative_to(P) for p in after)
  for q in unique.values():
   assert m.sha(q['source'])==q['source_sha256']
   dest=P/q['copy_name']
   if dest.exists():assert m.sha(dest)==q['source_sha256'],'Only identical owned copies can be overwritten'
  assert not b.documents();b.checkpoint('copy_started',state=state,unique_parts=len(unique))
  rc=sw.CopyDocument(s['source_assembly'],str(target),b.VARIANT(b.pythoncom.VT_ARRAY|b.pythoncom.VT_BSTR,before),b.VARIANT(b.pythoncom.VT_ARRAY|b.pythoncom.VT_BSTR,after),1)
  r['states'][state]={'copy_api_return':rc,'target':str(target),'source':s['source_assembly'],'child_documents':len(unique)}
  b.checkpoint('copy_api_returned',state=state,rc=rc)
  assert rc==0 and target.is_file(),'CopyDocument did not succeed'
  for q in unique.values():assert m.sha(P/q['copy_name'])==q['source_sha256'],'Native part bytes changed during copy'
  deps=sw.GetDocumentDependencies2(str(target),True,False,False) or []
  paths=[deps[k+1] for k in range(0,len(deps),2)]
  assert {m.normalized(p) for p in paths}=={m.normalized(p) for p in after},'Saved dependency paths differ'
  assert all(Path(p).resolve().is_relative_to(P) for p in paths)
  r['states'][state].update(sha256=m.sha(target),bytes=target.stat().st_size,dependencies=paths,outside_dependency_count=0,part_bytes_unchanged=True)
  assert m.sha(s['source_assembly'])==s['source_assembly_sha256'];b.checkpoint('copy_verified',state=state)
 assert not b.documents()
 for q in j['parts']:
  assert m.sha(P/q['copy_name'])==q['source_sha256'] and m.sha(q['source'])==q['source_sha256']
  r['parts'].append({'path':str(P/q['copy_name']),'sha256':q['source_sha256'],'source':q['source'],'bytes':q['bytes']})
 assert all(m.sha(p)==d for p,d in j['input_sha256'].items())
 r.update(status='PASS_NATIVE_COPY_AND_STORED_LOCAL_DEPENDENCIES_COLD_OPEN_PENDING',source_inputs_unchanged=True,part_count=len(r['parts']),open_documents_after=[])
 sw.ExitApp();b.checkpoint('empty_session_exit')
except Exception as exc:
 r.update(status='FAILED',error=repr(exc),traceback=traceback.format_exc())
 if b:b.checkpoint('failed')
 else:out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
 raise
finally:
 if b:b.pythoncom.CoUninitialize()
