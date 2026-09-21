"""Close only clean/hash-bound WP09 native documents; exit only verified empty SW."""
from pathlib import Path
import sys,json,importlib.util,argparse
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('wp09_close_native',R/'tools/build_module_native.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
p=argparse.ArgumentParser();p.add_argument('receipt',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
d=json.loads(a.receipt.read_text());m.require(d['status']=='PASS_NATIVE_FIXED_LOCAL_ASSEMBLY_COLD_REOPEN_ONLY','Native receipt not complete')
m.require(not a.output.exists(),'Protected output')
allowed={m.normalized(d['assembly_save']['path']):d['assembly_save']['sha256']}
for x in d['parts']:allowed[m.normalized(x['native_save']['path'])]=x['native_save']['sha256']
report=dict(status='RUNNING',progress=[],parts=[],save_attempts=[],source_receipt=str(a.receipt),source_sha256=m.sha(a.receipt))
b=None
try:
    b=m.ModuleBuilder(a.output,report);docs=b.documents();report['documents_before']=[x for _,x in docs]
    for obj,x in docs:
        k=m.normalized(x['path']) if x['path'] else ''
        m.require(k in allowed and not x['dirty'] and m.sha(x['path'])==allowed[k],'Unknown/dirty document remains untouched')
    for obj,x in docs:b.close_own_saved(obj,Path(x['path']),allowed[m.normalized(x['path'])])
    m.require(not b.documents(),'Documents remain')
    report['empty_session_verified']=True;b.sw.ExitApp()
    report['status']='CLEAN_OWNED_DOCUMENTS_CLOSED_EMPTY_SESSION_EXIT_REQUESTED';b.checkpoint('complete')
finally:
    if b and b.initialized:b.pythoncom.CoUninitialize()

