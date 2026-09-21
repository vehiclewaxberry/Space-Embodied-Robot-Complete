"""Byte-copy parts; replace only closed assembly file references through the SW API."""
from pathlib import Path
import sys,json,importlib.util,shutil,traceback
sys.dont_write_bytecode=True
C=Path(__file__).resolve().parents[1];R=C.parent;B=(C/'mechanical/portable').resolve();P=B/'package'
sp=importlib.util.spec_from_file_location('redirect_frozen_helper',R/'tools/integrate_native_v5.py');h=importlib.util.module_from_spec(sp);sp.loader.exec_module(h);m=h.m
j=json.loads((C/'results/PORTABLE_INPUTS.json').read_text());out=C/'results/PORTABLE_COPY_V2.json';assert not out.exists()
r={'status':'RUNNING','method':'byte-identical shutil.copy2 + ISldWorks.ReplaceReferencedDocument on closed owned copies',
   'progress':[],'states':{},'parts':[],'prior_failure':'PORTABLE_COPY.json + logs/portable_copy.run.json TIMEOUT_GUARD',
   'manufacturing_release':False,'regenerated_solids':False}
b=None
try:
 b=h.Builder(out,r);sw=b.sw;assert not b.documents(),'Unexpected documents left untouched';r['empty_session_before']=True
 archived=B/'copydocument_timeout_partial'
 if P.exists():
  assert P.resolve().is_relative_to(B) and archived.resolve().is_relative_to(B) and not archived.exists()
  assert json.loads((C/'results/PORTABLE_OWNED_STOP.json').read_text())['status']=='PASS_OWNED_TIMEOUT_INSTANCE_STOPPED_PARENTS_UNCHANGED'
  P.rename(archived);r['failed_copy_archive']=str(archived)
 P.mkdir();r['solidworks_revision']=str(m.val(sw,'RevisionNumber'))
 for q in j['parts']:
  assert m.sha(q['source'])==q['source_sha256'];target=P/q['copy_name'];assert not target.exists()
  shutil.copy2(q['source'],target);assert m.sha(target)==q['source_sha256']
  r['parts'].append({'path':str(target),'sha256':q['source_sha256'],'source':q['source'],'bytes':q['bytes']})
 b.checkpoint('all_source_part_bytes_copied',count=len(r['parts']))
 for state,s in j['states'].items():
  assert not b.documents();target=P/s['target_name'];assert not target.exists();shutil.copy2(s['source_assembly'],target)
  unique={m.normalized(q['source']):q for q in s['rows']};r['states'][state]={'target':str(target),'source':s['source_assembly'],'replacements':[]}
  b.checkpoint('closed_reference_replacement_started',state=state,unique_parts=len(unique))
  for i,q in enumerate(unique.values()):
   b.ram_floor();dest=str(P/q['copy_name']);ok=sw.ReplaceReferencedDocument(str(target),q['source'],dest)
   r['states'][state]['replacements'].append({'source':q['source'],'target':dest,'api_return':bool(ok)})
   assert ok,'ReplaceReferencedDocument failed'
   if i%25==24:b.checkpoint('closed_references_replaced',state=state,count=i+1)
  deps=sw.GetDocumentDependencies2(str(target),True,False,False) or [];paths=[deps[i+1] for i in range(0,len(deps),2)]
  expected={m.normalized(P/q['copy_name']) for q in unique.values()}
  assert {m.normalized(p) for p in paths}==expected,'Stored dependency set mismatch'
  assert all(Path(p).resolve().is_relative_to(P) for p in paths)
  r['states'][state].update(sha256=m.sha(target),bytes=target.stat().st_size,dependencies=paths,outside_dependency_count=0,child_documents=len(unique))
  b.checkpoint('closed_reference_replacement_verified',state=state)
 assert not b.documents()
 assert all(m.sha(p)==v for p,v in j['input_sha256'].items())
 for q in j['parts']:assert m.sha(P/q['copy_name'])==q['source_sha256'] and m.sha(q['source'])==q['source_sha256']
 r.update(status='PASS_NATIVE_COPY_AND_STORED_LOCAL_DEPENDENCIES_COLD_OPEN_PENDING',source_inputs_unchanged=True,part_count=len(r['parts']),open_documents_after=[])
 sw.ExitApp();b.checkpoint('empty_session_exit')
except Exception as exc:
 r.update(status='FAILED',error=repr(exc),traceback=traceback.format_exc())
 if b:b.checkpoint('failed')
 else:out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
 raise
finally:
 if b:b.pythoncom.CoUninitialize()
