from pathlib import Path
import sys,json,importlib.util
sys.dont_write_bytecode=True
R=Path(r'''F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_electro_propulsion_20260907_1350''')
s=importlib.util.spec_from_file_location('save_failed_iges_parent',R/'tools/build_module_native.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
rp=R/'results/battery_mount_NATIVE_BOUNDED_B5.json';d=json.loads(rp.read_text());assert d['status']=='FAILED' and d['documents_before']==[]
out=R/'results/BATTERY_IGES_FAILED_SHEETS_PRESERVED.json';assert not out.exists()
report=dict(status='RUNNING',progress=[],parts=[],save_attempts=[],failure_receipt=str(rp),failure_sha256=m.sha(rp),geometry_pass_credit=False)
b=m.ModuleBuilder(out,report)
try:
    assert report['attachment_attempt']['returned_pid']==d['attachment_attempt']['returned_pid']
    docs=b.documents();assert len(docs)==1;model,f=docs[0];report['documents_before']=[f]
    assert not f['path'] and f['title']=='WP09_BAT_-152_-78_screw.SLDPRT'
    facts=b.part_facts(model);assert facts['solid_count']==0 and facts['sheet_count']==7;report['facts']=facts
    saved=b.save_new(model,R/'native/failed_iges_sheets/WP09_BAT_FIRST_SCREW_7SHEETS_DIAGNOSTIC.SLDPRT');report['preserved_file']=saved
    b.close_own_saved(model,Path(saved['path']),saved['sha256']);assert not b.documents();b.sw.ExitApp()
    report['status']='FAILED_IMPORT_SHEETS_SAVED_AND_EMPTY_SESSION_EXIT_REQUESTED';b.checkpoint('preserved_and_closed')
finally:b.pythoncom.CoUninitialize()
