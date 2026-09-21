"""Resume only the missing R6H top assembly; preserve all completed files."""
from pathlib import Path
import json,sys,hashlib,shutil,traceback,gc
D=Path(__file__).resolve().parents[1];R4=D.parent/'SERVICE_STAR_INTERNAL_LAYOUT_R4_20260920'
sys.path.insert(0,str(D.parent/'SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919/tools'))
import native_integrate as ni
ni.OUT=D
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
plan=read(D/'inputs/NATIVE_ASSEMBLY_PLAN.json');prior=read(D/'results/NATIVE_ASSEMBLY_DELIVERY.json')
assert prior['status']=='FAILED_CLOSED' and prior['error']=='Available memory is below the 512 MiB floor'
assert len(prior['parts'])==27 and len(prior['groups'])==4
for r in prior['parts']:assert sha(r['target'])==r['native_save']['sha256']
for r in prior['groups']:assert sha(r['saved']['path'])==r['saved']['sha256']
assert all(sha(r['path'])==r['sha256'] for r in plan['source_native_files'])
rp=D/'results/NATIVE_TOP_RESUME.json';assert not rp.exists()
report=dict(status='RUNNING',progress=[],save_attempts=[],prior_failed_build_sha256=sha(D/'results/NATIVE_ASSEMBLY_DELIVERY.json'),
  source_plan_sha256=sha(D/'inputs/NATIVE_ASSEMBLY_PLAN.json'),strategy='copy immutable R4 top; redirect three changed subassemblies; append one checked group',
  whole_design_complete=False,ready_to_power=False,flight_ready=False)
ni.configure_com();b=ni.PrototypeBuilder(rp,report);sw=b.sw
target=D/'native/SERVICE_STAR_SERVICE_R6H.SLDASM';doc=None
try:
    assert not target.exists()
    oldplan=read(R4/'inputs/NATIVE_ASSEMBLY_PLAN.json');oldtop={r['id']:r for r in oldplan['top_rows']}
    source=Path(read(R4/'results/NATIVE_ASSEMBLY_DELIVERY.json')['service']['saved']['path'])
    shutil.copy2(source,target);report['copied_source']=dict(path=str(source),sha256=sha(source));b.checkpoint('copied_top_only')
    report['closed_dependency_redirects']=[]
    for r in plan['top_rows']:
        if r['id'] in oldtop and r['native_path']!=oldtop[r['id']]['native_path']:
            ok=bool(sw.ReplaceReferencedDocument(str(target),oldtop[r['id']]['native_path'],r['native_path']))
            assert ok,r['id'];report['closed_dependency_redirects'].append(dict(id=r['id'],old=oldtop[r['id']]['native_path'],new=r['native_path']))
    assert len(report['closed_dependency_redirects'])==3
    sw.DocumentVisible(False,2)
    opened=sw.OpenDoc6(str(target),2,193,'',0,0);assert opened[0] is not None and opened[1]==0,opened[1:]
    doc=b.wrap(opened[0],'IModelDoc2');asm=b.wrap(doc,'IAssemblyDoc');asm.LightweightAllResolved();b.ram_floor()
    inherited=[r for r in plan['top_rows'] if r['id'] in oldtop]
    b.identity_inventory(asm,inherited)
    r=next(r for r in plan['top_rows'] if r['id']=='R6H_CORE_INSTALLATION')
    raw=asm.AddComponents3(b.VARIANT(b.pythoncom.VT_ARRAY|b.pythoncom.VT_BSTR,[r['native_path']]),
       b.VARIANT(b.pythoncom.VT_ARRAY|b.pythoncom.VT_R8,ni.h.t16(r['T_S_local'])),b.VARIANT(b.pythoncom.VT_ARRAY|b.pythoncom.VT_BSTR,['']))
    assert len(raw)==1;c=b.wrap(raw[0],'IComponent2');c.ComponentReference=r['id'];c.Name2=r['id']
    doc.ClearSelection2(True);assert c.Select4(False,None,False);asm.FixComponent();doc.ClearSelection2(True)
    raw=c=None;gc.collect();asm.LightweightAllResolved()
    lookup=b.identity_inventory(asm,plan['top_rows']);observed=[]
    for r in plan['top_rows']:
        c=lookup[r['id']];assert ni.m.normalized(c.GetPathName())==ni.m.normalized(r['native_path']) and c.IsFixed()
        err=max(abs(x-y) for x,y in zip(list(b.wrap(c.Transform2,'IMathTransform').ArrayData),ni.h.t16(r['T_S_local'])));assert err<1e-8
        observed.append(dict(id=r['id'],native_path=c.GetPathName(),fixed=True,transform_error=err))
    ext=b.wrap(doc.Extension,'IModelDocExtension');props=b.wrap(ext.CustomPropertyManager(''),'ICustomPropertyManager')
    for k,v in dict(DP_STATUS='HORIZONTAL_FIXED_POSE_GROUND_CANDIDATE',DP_CHILD_COUNT=len(plan['top_rows']),DP_SCOPE='R6H_MINIMUM_LOCAL_CHANGES',DP_WHOLE_MASS='UNKNOWN',DP_ENGINEERING_COMPLETE='FALSE').items():props.Add3(k,30,str(v),2)
    rebuild=bool(doc.EditRebuild3());saved=doc.Save3(1,0,0);assert saved[0] and saved[1]==0,saved
    report['service']=dict(id='service',saved=dict(path=str(target),sha256=sha(target),save=saved),direct_children=len(observed),children=observed,needs_rebuild2=int(ext.NeedsRebuild2),rebuild_api_return=rebuild)
    b.close_own_saved(doc,target,sha(target));doc=None;b.checkpoint('top_saved_closed')
    opened=sw.OpenDoc6(str(target),2,195,'',0,0);assert opened[0] is not None and opened[1]==0
    doc=b.wrap(opened[0],'IModelDoc2');asm=b.wrap(doc,'IAssemblyDoc');lookup=b.identity_inventory(asm,plan['top_rows'])
    for r in plan['top_rows']:
        c=lookup[r['id']];assert ni.m.normalized(c.GetPathName())==ni.m.normalized(r['native_path']) and c.IsFixed()
    report['service'].update(cold_errors=opened[1],cold_warnings=opened[2],cold_top_identity_count=len(lookup))
    b.close_own_saved(doc,target,sha(target));doc=None
    assert all(sha(r['path'])==r['sha256'] for r in plan['source_native_files'])
    assert all(sha(r['target'])==r['native_save']['sha256'] for r in prior['parts'])
    assert all(sha(r['saved']['path'])==r['saved']['sha256'] for r in prior['groups'])
    report.update(status='PASS_R6H_TOP_RESUME_COLD_REOPEN',source_native_files_unchanged=True);b.checkpoint('complete')
    final=dict(prior);final.pop('error');final.pop('traceback')
    final.update(status='PASS_R6H_HORIZONTAL_FIXED_POSE_NATIVE_BUILD',service=report['service'],resume_receipt_sha256=sha(rp),source_native_files_unchanged=True,horizontal_MAIN=True)
    ni.write(D/'results/NATIVE_ASSEMBLY_DELIVERY_FINAL.json',final)
except Exception as e:
    report.update(status='FAILED_CLOSED',error=str(e),traceback=traceback.format_exc());b.checkpoint('failed');raise
finally:
    # Close only our known copied output; it cannot contain user work.
    if doc is not None:
        try:sw.CloseDoc(ni.m.val(doc,'GetTitle'))
        except Exception:pass
    try:
        sw.DocumentVisible(True,1);sw.DocumentVisible(True,2)
        if report.get('session',{}).get('new_process') and not b.documents():sw.ExitApp()
    except Exception:pass
    b.pythoncom.CoUninitialize()
