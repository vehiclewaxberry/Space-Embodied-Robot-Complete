from pathlib import Path
import sys,json,importlib.util
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('failed_native_cleanup',R/'tools/build_module_native.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
rp=R/'results/battery_mount_NATIVE_BOUNDED_B1.json';d=json.loads(rp.read_text());m.require(d['status']=='FAILED','Not the failed import')
out=R/'results/BATTERY_IMPORT_FAILURE_SESSION_EXIT.json';m.require(not out.exists(),'Protected output')
allowed={m.normalized(x['native_save']['path']):x['native_save']['sha256'] for x in d['parts'] if x.get('native_save')}
report=dict(status='RUNNING',progress=[],parts=[],save_attempts=[],failure_receipt=str(rp),failure_sha256=m.sha(rp),geometry_failure_preserved=True)
b=m.ModuleBuilder(out,report)
try:
    docs=b.documents();report['documents_before']=[x for _,x in docs]
    for doc,x in docs:
        key=m.normalized(x['path']) if x['path'] else ''
        m.require(key in allowed and not x['dirty'] and m.sha(x['path'])==allowed[key],'Unknown/dirty document left untouched')
    for doc,x in docs:b.close_own_saved(doc,Path(x['path']),allowed[m.normalized(x['path'])])
    m.require(not b.documents(),'Docs remain');b.sw.ExitApp()
    report['status']='CLEAN_SAVED_FAILED_IMPORT_CLOSED_EMPTY_SESSION_EXIT_REQUESTED';b.checkpoint('completed')
finally:b.pythoncom.CoUninitialize()

