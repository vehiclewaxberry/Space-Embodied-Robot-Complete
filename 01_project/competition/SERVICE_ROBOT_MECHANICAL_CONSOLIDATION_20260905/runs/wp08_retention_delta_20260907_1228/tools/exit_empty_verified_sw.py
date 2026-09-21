"""User-authorized memory cleanup: graceful exit only after exact empty-session proof."""
from pathlib import Path
import sys,json,time
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'tools'))
import integrate_native_delta as owner
def main():
    out=R/'results/EXIT_EMPTY_SW.json'
    owner.require(not out.exists(),'Existing receipt protected')
    prior=json.loads((R/'results/UNLOAD_VERIFIED_NATIVE.json').read_text())
    owner.require(prior['status']=='CLOSED_ONLY_REGISTERED_CLEAN_DOCUMENTS_NO_PROCESS_EXIT','Prior scope close incomplete')
    report=dict(status='RUNNING',progress=[],save_attempts=[],reason='Release the empty task CAD session cache for bounded validation and viewing after prior explicit user memory-cleanup authorization')
    owner.reuse.require_outer_guard(report)
    b=owner.Builder(out,report)
    try:
        owner.require(int(owner.val(b.sw,'GetProcessID'))==26208,'Session changed')
        report['documents_before_exit']=[d for _,d in b.documents()]
        owner.require(not report['documents_before_exit'],'Open documents preserved; no exit allowed')
        report['memory_before']=b.memory_snapshot()
        b.checkpoint('empty_session_verified_graceful_exit_only')
        b.sw.ExitApp()
        for _ in range(40):
            if not b.psutil.pid_exists(26208):break
            time.sleep(.25)
        report['pid_exited']=not b.psutil.pid_exists(26208)
        report['available_mib_after']=b.psutil.virtual_memory().available/2**20
        report['status']='EMPTY_SESSION_EXITED_GRACEFULLY' if report['pid_exited'] else 'EXIT_REQUESTED_NO_FORCE_KILL'
        b.checkpoint('completed')
    finally:
        if b.initialized:b.pythoncom.CoUninitialize()
if __name__=='__main__':main()
