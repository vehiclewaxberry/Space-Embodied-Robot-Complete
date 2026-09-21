"""Only close hash-recorded, clean documents inside this run after guarded interruption."""
from pathlib import Path
import sys,json,importlib.util
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1];fp=R.parent/'wp09_electro_propulsion_20260907_1350/tools/build_module_native.py'
spec=importlib.util.spec_from_file_location('recovery_native',fp);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
out=R/'results/NATIVE_B1_RECOVERY.json';assert not out.exists()
report=dict(status='INSPECTING_OWN_INTERRUPTED_SESSION',progress=[],save_attempts=[],parts=[],closed=[],original_B1_preferences_restoration='UNVERIFIABLE_ORIGINAL_SNAPSHOT_NOT_PERSISTED_BEFORE_GUARD_INTERRUPTION')
b=m.ModuleBuilder(out,report)
try:
    docs=b.documents();report['before']=[d for _,d in docs]
    for doc,d in docs:
        p=Path(d['path']);assert p.is_relative_to(R/'native/p') and p.exists() and not d['dirty']
        f=b.part_facts(doc);assert f['solid_count']==1 and f['sheet_count']==0
        record=dict(path=str(p),sha256=m.sha(p),facts=f,clean=True)
        report['closed'].append(record);b.checkpoint('clean_saved_part_observed',path=str(p))
        b.close_own_saved(doc,p,record['sha256'])
    assert not b.documents();report['current_preferences']={str(k):b.sw.GetUserPreferenceToggle(k) for k in (111,161,290,291,691,690,769)}
    b.sw.ExitApp();report['status']='EXACT_CLEAN_SAVED_DOCS_CLOSED_EMPTY_SESSION_EXITED';b.checkpoint('empty_exit')
finally:b.pythoncom.CoUninitialize()
