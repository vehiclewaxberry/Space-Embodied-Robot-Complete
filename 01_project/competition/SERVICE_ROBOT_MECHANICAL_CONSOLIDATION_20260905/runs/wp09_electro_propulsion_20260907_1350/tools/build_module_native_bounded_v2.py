"""Bounded six-new-parts SW sessions with immutable receipts and explicit reuse."""
from pathlib import Path
import sys,json,importlib.util,argparse,copy,traceback
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('wp09_native_parent',R/'tools/build_module_native.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('module');ap.add_argument('--batch',type=int,required=True);ap.add_argument('--local-check',type=Path);a=ap.parse_args();kind=a.module
    ep=R/'results'/kind/'EMISSION.json';cp=a.local_check or R/'results'/kind/'CHECK.json'
    em=json.loads(ep.read_text());ch=json.loads(cp.read_text());m.require(str(ch['status']).startswith('PASS'),'Local check incomplete')
    ci={m.normalized(k):v for k,v in ch.get('input_sha256_before',{}).items()}
    m.require(ci.get(m.normalized(ep))==m.sha(ep),'Local check not bound to emission')
    out=R/'results'/f'{kind}_NATIVE_BOUNDED_B{a.batch}.json';m.require(not out.exists(),'Receipt protected')
    folder=R/'native'/kind;target=folder/('WP09_'+kind.upper()+'.SLDASM');neutral=folder/'native_roundtrip.step'
    rows=[dict(id=k,step_path=v['path'],source_sha256=v['sha256'],native_path=str(folder/'parts'/(k+'.SLDPRT')),expected_solids=1,
      expected_local_bbox_mm=v['bbox_mm'],representation_role=v['representation_role'],context_only=k.startswith('CONTEXT_') or v['representation_role']=='FUNCTIONAL_ENVELOPE')
      for k,v in em['parts'].items()]
    c=json.loads(Path(em['contract_path']).read_text())
    pins={str(p):m.sha(p) for p in [Path(__file__),Path(m.__file__),m.FROZEN,m.ADAPTER,ep,cp,R/'results/SW_STARTUP.json']}
    pins.update(c['source_inputs']);pins[em['contract_path']]=em['contract_sha256'];pins[em['producer_path']]=em['producer_sha256']
    prior={};allowed={}
    for rp in sorted((R/'results').glob('*_NATIVE*.json')):
        d=json.loads(rp.read_text())
        if not isinstance(d.get('parts'),list):continue
        pins[str(rp)]=m.sha(rp)
        for old in d['parts']:
            ns=old.get('native_save')
            if ns and 'sha256' in ns:
                allowed[m.normalized(ns['path'])]=ns['sha256']
                if d.get('module')==kind:prior[old['id']]=copy.deepcopy(old)
        if d.get('status')=='PASS_NATIVE_FIXED_LOCAL_ASSEMBLY_COLD_REOPEN_ONLY':
            ns=d['assembly_save'];allowed[m.normalized(ns['path'])]=ns['sha256']
    recovery=R/'results/A3200_INTERRUPTED_SESSION_EXIT.json'
    if recovery.exists():
        d=json.loads(recovery.read_text());pins[str(recovery)]=m.sha(recovery)
        for q in d['closed']:
            allowed[m.normalized(q['path'])]=q['sha256']
            if kind=='a3200':
                ident=Path(q['path']).stem
                prior[ident]=dict(id=ident,source=em['parts'][ident]['path'],source_sha256=q['source_sha256'],target=q['path'],
                  expected_solids=1,status='CLEAN_SAVED_INTERRUPTED_PART_REUSED_COLD_ASSEMBLY_CHECK_REQUIRED',
                  facts=q['facts'],native_save=dict(path=q['path'],sha256=q['sha256'],bytes=Path(q['path']).stat().st_size,
                  ok=None,errors=None,warnings=None,original_save_api_acknowledgement='UNKNOWN_GUARD_INTERRUPTED'),
                  recovery_receipt=str(recovery))
    missing=[];reused=[]
    for row in rows:
        path=Path(row['native_path'])
        if path.exists():
            m.require(row['id'] in prior,'Unreceipted existing native part')
            old=prior[row['id']]
            m.require(m.normalized(old['native_save']['path'])==m.normalized(path) and m.sha(path)==old['native_save']['sha256'],'Existing native part hash changed')
            m.require(old['source_sha256']==row['source_sha256'],'Existing native source mismatch')
            pins[str(path)]=m.sha(path);reused.append(old)
        else:missing.append(row)
    m.require(not target.exists() and not neutral.exists(),'Existing assembly protected')
    pins.update({x['step_path']:x['source_sha256'] for x in rows})
    m.require(all(m.sha(p)==v for p,v in pins.items()),'Input changed before work')
    report=dict(schema='WP09_NATIVE_BOUNDED_SESSION',module=kind,batch=a.batch,status='BUILDING',coordinate_frame=em.get('frame','S_WORLD_MM')+'_IDENTITY',
      progress=[],parts=reused,save_attempts=[],reused_ids=[x['id'] for x in reused],input_sha256_before=pins,
      integrated_into_wp08=False,physical_assembly_completed=False,manufacturing_release=False,mate_based_motion_model=False,
      electrical_complete=False,pressure_system_designed=False,geometry_roundtrip_equivalence_verified=False,max_new_parts_per_session=6)
    b=None;prefs=None;command=None;partial=False
    try:
        import psutil
        ancestors=[dict(pid=p.pid,command=p.cmdline()) for p in psutil.Process().parents() if any(Path(x).name.lower()=='run_guard.py' for x in p.cmdline())]
        m.require(ancestors,'Outer guard required');report['outer_guard_processes']=ancestors
        b=m.ModuleBuilder(out,report);docs=b.documents();report['documents_before']=[d for _,d in docs]
        for doc,d in docs:
            key=m.normalized(d['path']) if d['path'] else ''
            m.require(key in allowed and not d['dirty'] and m.sha(d['path'])==allowed[key],'Unknown/dirty document left untouched')
        for doc,d in docs:b.close_own_saved(doc,Path(d['path']),allowed[m.normalized(d['path'])])
        m.require(not b.documents(),'Docs remain')
        sw=b.sw;sw.Visible=True;sw.UserControl=True;command=sw.CommandInProgress
        prefs=dict(toggles={k:sw.GetUserPreferenceToggle(k) for k in (111,291,691)},
          strings={k:sw.GetUserPreferenceStringValue(k) for k in (8,9,10)},integers={k:sw.GetUserPreferenceIntegerValue(k) for k in (577,578,579,580)})
        for k in prefs['toggles']:sw.SetUserPreferenceToggle(k,k==111)
        for k,n in ((8,'gb_part.prtdot'),(9,'gb_assembly.asmdot'),(10,'gb_a4.drwdot')):sw.SetUserPreferenceStringValue(k,str(m.TEMPLATES/n))
        for k,v in {577:0,578:1,579:2,580:0}.items():sw.SetUserPreferenceIntegerValue(k,v)
        sw.CommandInProgress=False
        for row in missing[:6]:b.import_part(row)
        partial=len(missing)>6
        if partial:
            m.require(not b.documents(),'Cannot exit nonempty partial session')
            report.update(status='PARTS_BATCH_COMPLETE_AWAITING_NEXT_SESSION',remaining_ids=[x['id'] for x in missing[6:]])
        else:
            b.assemble(rows,target,neutral)
            report.update(status='PASS_NATIVE_FIXED_LOCAL_ASSEMBLY_COLD_REOPEN_ONLY',component_count=len(rows))
        m.require(all(m.sha(p)==v for p,v in pins.items()),'Input changed during session')
        report.update(input_sha256_after=pins,input_files_unchanged=True)
        b.checkpoint('batch_completed')
    except Exception as exc:
        report.update(status='FAILED',error=str(exc),traceback=traceback.format_exc())
        if b:b.checkpoint('failed')
        else:out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        raise
    finally:
        if b:
            try:
                if prefs:
                    for k,v in prefs['toggles'].items():b.sw.SetUserPreferenceToggle(k,v)
                    for k,v in prefs['strings'].items():b.sw.SetUserPreferenceStringValue(k,v)
                    for k,v in prefs['integers'].items():b.sw.SetUserPreferenceIntegerValue(k,v)
                if command is not None:b.sw.CommandInProgress=command
                report['session_preferences_restored']=True
                if partial and report['status']=='PARTS_BATCH_COMPLETE_AWAITING_NEXT_SESSION':
                    m.require(not b.documents(),'Nonempty session cannot exit');b.sw.ExitApp();report['empty_session_exit_requested']=True
            except Exception as exc:report.update(status='FAILED',restore_or_exit_error=repr(exc))
            b.checkpoint('bounded_session_detached')
            if b.initialized:b.pythoncom.CoUninitialize()
if __name__=='__main__':main()

