"""Six canonical parts per serial SW session; cold reopen plus STEP readback."""
from pathlib import Path
import sys,json,importlib.util,argparse,traceback
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1];PARENT=R.parent/'wp09_electro_propulsion_20260907_1350/tools/build_module_native.py'
spec=importlib.util.spec_from_file_location('wp09_native_proven',PARENT);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('batch',type=int);ap.add_argument('--start',type=int);ap.add_argument('--count',type=int,default=2);a=ap.parse_args()
    cp=R/'results/CANONICAL_NATIVE_INPUTS.json';c=json.loads(cp.read_text());assert c['status']=='PASS_TRANSLATION_ONLY_MATERIAL_SHARING'
    records=c['unique_parts'];rows=[]
    start=a.start if a.start is not None else (a.batch-1)*a.count
    for p in records[start:start+a.count]:rows.append(dict(id=p['id'],step_path=p['path'],source_sha256=p['sha256'],native_path=str(R/'native/p'/(p['id']+'.SLDPRT')),expected_solids=1,expected_local_bbox_mm=p['facts']['bbox_mm'],representation_role=p['representation_role']))
    assert rows
    rp=R/'results'/f'NATIVE_PARTS_B{a.batch}.json';assert not rp.exists()
    report=dict(status='RUNNING',batch=a.batch,coordinate_frame='CANONICAL_LOCAL_MM_WITH_EXPLICIT_INSTANCE_TRANSLATIONS',parts=[],progress=[],save_attempts=[],canonical_manifest_sha256=m.sha(cp),roundtrip=[],manufacturing_release=False)
    b=None;prefs=None;cmd=None
    try:
        b=m.ModuleBuilder(rp,report);assert not b.documents(),'Existing docs left untouched';sw=b.sw;sw.Visible=True;sw.UserControl=True
        cmd=sw.CommandInProgress
        prefs=dict(toggles={k:sw.GetUserPreferenceToggle(k) for k in (111,161,290,291,691,690,769)},strings={k:sw.GetUserPreferenceStringValue(k) for k in (8,9,10)},integers={k:sw.GetUserPreferenceIntegerValue(k) for k in (12,140,207,577,578,579,580)})
        report['preferences_before']=prefs;b.checkpoint('preferences_persisted_before_any_change')
        for k in prefs['toggles']:sw.SetUserPreferenceToggle(k,k in (111,161,290))
        for k,v in {12:0,140:0,207:0,577:0,578:1,579:2,580:0}.items():sw.SetUserPreferenceIntegerValue(k,v)
        for k,n in ((8,'gb_part.prtdot'),(9,'gb_assembly.asmdot'),(10,'gb_a4.drwdot')):sw.SetUserPreferenceStringValue(k,str(m.TEMPLATES/n))
        sw.CommandInProgress=False
        for row in rows:
            if Path(row['native_path']).exists():
                old=json.loads((R/'results/NATIVE_PARTS_B1.json').read_text());oldrow=next(x for x in old['parts'] if x['id']==row['id'])
                assert oldrow['source_sha256']==row['source_sha256']
                saved=next(x for x in old['save_attempts'] if m.normalized(x['path'])==m.normalized(row['native_path']))
                assert saved['ok'] and saved['errors']==0
                report['parts'].append(dict(id=row['id'],source_sha256=row['source_sha256'],status='REUSED_SAVED_INTERRUPTED_PART_PENDING_COLD_READBACK',native_save=dict(path=row['native_path'],sha256=m.sha(row['native_path'])),prior_receipt=str(R/'results/NATIVE_PARTS_B1.json')))
            else:b.import_part(row)
            opened=sw.OpenDoc6(row['native_path'],1,1,'',0,0);assert opened[0] is not None and opened[1]==0
            doc=b.wrap(opened[0],'IModelDoc2');b.activate(doc,Path(row['native_path']));doc.ClearSelection2(True)
            facts=b.part_facts(doc);assert facts['solid_count']==1 and facts['sheet_count']==0
            assert m.bbox_max_error(facts['bounds_mm'],row['expected_local_bbox_mm'])<=m.job_linear_tolerance_mm()
            report['parts'][-1]['cold_recheck']=facts
            rt=R/'native/rt'/(row['id']+'.step');saved=b.save_new(doc,rt);report['roundtrip'].append(dict(id=row['id'],source_sha256=row['source_sha256'],**saved))
            b.close_own_saved(doc,Path(row['native_path']),m.sha(row['native_path']));b.checkpoint('roundtrip_saved',id=row['id'])
        assert not b.documents()
        report['status']='PASS_NATIVE_PART_COLD_REOPEN_BOUNDS__MATERIAL_READBACK_PENDING'
    except Exception as ex:
        report.update(status='FAILED',error=repr(ex),traceback=traceback.format_exc());raise
    finally:
        if b:
            if prefs:
                for group,method in [('toggles','SetUserPreferenceToggle'),('strings','SetUserPreferenceStringValue'),('integers','SetUserPreferenceIntegerValue')]:
                    for k,v in prefs[group].items():getattr(b.sw,method)(k,v)
                b.sw.CommandInProgress=cmd
                report['preferences_restored']=all(b.sw.GetUserPreferenceToggle(k)==v for k,v in prefs['toggles'].items()) and all(b.sw.GetUserPreferenceIntegerValue(k)==v for k,v in prefs['integers'].items()) and all(b.sw.GetUserPreferenceStringValue(k)==v for k,v in prefs['strings'].items())
            report['documents_after']=[d for _,d in b.documents()]
            if not report['documents_after'] and report['status'].startswith('PASS'):b.sw.ExitApp();report['clean_empty_session_exit_requested']=True
            b.checkpoint('session_end');b.pythoncom.CoUninitialize()
        else:rp.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
