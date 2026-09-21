"""Close only this run's exact hash-bound clean documents, keep the SW app."""
from pathlib import Path
import sys,json,gc
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'tools'))
import integrate_native_delta as owner
def main():
    p=R/'results/UNLOAD_VERIFIED_NATIVE.json'
    owner.require(not p.exists(),'Existing receipt protected')
    report=dict(status='RUNNING',progress=[],save_attempts=[])
    owner.reuse.require_outer_guard(report)
    b=owner.Builder(p,report)
    try:
        owner.require(int(owner.val(b.sw,'GetProcessID'))==26208,'Existing session changed')
        m=json.loads((R/'results/INTEGRATION_MANIFEST.json').read_text())
        n=json.loads((R/'results/REAR_RIB_NATIVE.json').read_text())
        allowed={owner.oldbase.normalized(r['native_path']):r['native_sha256'] for s in m['states'].values() for r in s['instances']}
        for f in (R/'results').glob('NATIVE_*.json'):
            d=json.loads(f.read_text())
            if d.get('status')=='PASS_NATIVE_FIXED_POSE_DELTA_COLD_REOPEN':allowed[owner.oldbase.normalized(d['native_save']['path'])]=d['native_save']['sha256']
        for row in [n['assembly_save'],*[x['native_save'] for x in n['parts']]]:
            allowed[owner.oldbase.normalized(row['path'])]=row['sha256']
        report['memory_before']=b.memory_snapshot()
        report['documents_before']=[d for _,d in b.documents()]
        b.close_registered(allowed)
        gc.collect()
        report['memory_after']=b.memory_snapshot()
        report['status']='CLOSED_ONLY_REGISTERED_CLEAN_DOCUMENTS_NO_PROCESS_EXIT'
        b.checkpoint('completed')
    finally:
        if b.initialized:b.pythoncom.CoUninitialize()
if __name__=='__main__':main()
