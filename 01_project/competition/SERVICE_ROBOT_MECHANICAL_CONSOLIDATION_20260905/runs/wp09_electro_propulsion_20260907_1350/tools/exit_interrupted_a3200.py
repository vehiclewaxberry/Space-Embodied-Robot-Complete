from pathlib import Path
import json,sys,importlib.util,traceback
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('wp09_native_clean',R/'tools/build_module_native.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
out=R/'results/A3200_INTERRUPTED_SESSION_EXIT.json';assert not out.exists()
report=dict(status='RUNNING',progress=[],parts=[],save_attempts=[],closed=[],save_api_acknowledgement_recovered=False)
b=None
try:
    b=m.ModuleBuilder(out,report);m.require(int(m.val(b.sw,'GetProcessID'))==22908,'Unexpected singleton')
    em=json.loads((R/'results/a3200/EMISSION.json').read_text());docs=b.documents();report['documents_before']=[d for _,d in docs]
    m.require(len(docs)==1,'Unexpected document count')
    for doc,d in docs:
        path=Path(d['path']).resolve();ident=path.stem
        m.require(path== (R/'native/a3200/parts'/(ident+'.SLDPRT')).resolve() and ident=='A3200_BOTTOM_WASHER_2','Unexpected doc left untouched')
        m.require(not d['dirty'] and d['document_type']==1,'Dirty or non-part left untouched')
        facts=b.part_facts(doc);err=m.bbox_max_error(facts['bounds_mm'],em['parts'][ident]['bbox_mm'])
        m.require(facts['solid_count']==1 and facts['sheet_count']==0 and err<=1e-5,'Actual native body or dimensions differ')
        digest=m.sha(path);b.close_own_saved(doc,path,digest)
        report['closed'].append(dict(path=str(path),sha256=digest,source_sha256=em['parts'][ident]['sha256'],facts=facts,bbox_error_mm=err,dirty=False,previous_save_acknowledgement='UNKNOWN_GUARD_INTERRUPTED'))
    m.require(not b.documents(),'Documents remain')
    report['empty_document_session_verified']=True;b.checkpoint('empty_session')
    b.sw.ExitApp();report['status']='TASK_OWNED_CLEAN_DOCUMENT_CLOSED_EMPTY_SESSION_EXIT_REQUESTED';b.checkpoint('exited')
finally:
    if b and b.initialized:b.pythoncom.CoUninitialize()

