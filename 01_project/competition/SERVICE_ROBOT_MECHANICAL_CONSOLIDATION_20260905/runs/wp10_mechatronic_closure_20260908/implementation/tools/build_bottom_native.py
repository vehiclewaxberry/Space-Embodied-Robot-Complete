"""Local SW driver reusing frozen importer and explicit-transform metadata reader."""
from pathlib import Path
import sys,json,hashlib,importlib.util,argparse,gc,re,traceback
A=Path(__file__).resolve().parents[1];parent=A.parents[1]/'wp09_interfaces_20260907_1525/tools/integrate_native_v5.py'
spec=importlib.util.spec_from_file_location('bottom_native_frozen_helpers',parent);h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h);m=h.m
ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['import','assemble','cold']);ap.add_argument('--owner',required=True,type=Path);ap.add_argument('--dataset',choices=['BOTTOM','COLD'],default='BOTTOM');args=ap.parse_args()
inp=A/f'mechanical/NATIVE_{args.dataset}_INPUTS.json';p=json.loads(inp.read_text());assert p['source_plan_sha256']==m.sha(A/'mechanical/FIXED_HEAT_INSTANCE_PLAN.json')
count=len(p['rows']);nparts=len(p['parts'])
import_status='PASS_NINE_NATIVE_PARTS_SAVED_CLOSED_REOPENED' if args.dataset=='BOTTOM' else f'PASS_{nparts}_NATIVE_PARTS_SAVED_CLOSED_REOPENED'
assemble_status=f'PASS_NATIVE_{count}_INSTANCE_ASSEMBLY_SAVED__COLD_PENDING'
cold_status=f'PASS_COLD_NATIVE_{count}_INSTANCES_{count}_SOLIDS_TRANSFORMS_LOCAL_DEPENDENCIES'
out=A/'results'/f'NATIVE_{args.dataset}_{args.mode.upper()}.json';assert not out.exists(),out
clearance_inputs={}
for st in ['SERVICE','PARKING','RELEASED']:
    path=A/'results'/f'FIXED_HEAT_{st}_INTERFACES.json';q=json.loads(path.read_text());assert q['source_plan_sha256']==p['source_plan_sha256'] and q['zero_positive_volume_intersections'] and q['complete_coverage']
    clearance_inputs[path.relative_to(A).as_posix()]=m.sha(path)
r=dict(schema=f'WP10_NATIVE_{args.dataset}_LOCAL_V1',mode=args.mode,status='RUNNING',progress=[],parts=[],save_attempts=[],coordinate_frame=p['coordinate_frame'],
 input_sha256=m.sha(inp),source_plan_sha256=p['source_plan_sha256'],new_instance_ids=[q['id'] for q in p['rows']],manufacturing_release=False,mate_based_motion=False,whole_vehicle_native_assembly=False)
b=None;sw=None;prefs={};oldcommand=None;owner=json.loads(args.owner.read_text())
try:
    import psutil
    assert psutil.Process(owner['pid']).name().lower()=='sldworks.exe' and abs(psutil.Process(owner['pid']).create_time()-owner['create_time'])<.01
    b=h.Builder(out,r);sw=b.sw;assert int(m.val(sw,'GetProcessID'))==owner['pid'];assert not b.documents(),'Unexpected user documents: untouched'
    r['owned_sw']=owner;r['solidworks_revision']=str(m.val(sw,'RevisionNumber'));sw.UserControl=True;oldcommand=sw.CommandInProgress
    prefs=dict(toggles={k:sw.GetUserPreferenceToggle(k) for k in (111,291,691)},strings={k:sw.GetUserPreferenceStringValue(k) for k in (8,9,10)},integers={k:sw.GetUserPreferenceIntegerValue(k) for k in (577,578,579,580)})
    for k in prefs['toggles']:sw.SetUserPreferenceToggle(k,k==111)
    for k,name in ((8,'gb_part.prtdot'),(9,'gb_assembly.asmdot'),(10,'gb_a4.drwdot')):sw.SetUserPreferenceStringValue(k,str(m.TEMPLATES/name))
    for k,v in {577:0,578:1,579:2,580:0}.items():sw.SetUserPreferenceIntegerValue(k,v)
    sw.DocumentVisible(False,1);sw.DocumentVisible(False,2);sw.CommandInProgress=False
    if args.mode=='import':
        for q in p['parts']:
            b.import_part(q);receipt=r['parts'][-1];actual=receipt['part_cold_reopen']['facts']['volume_mm3'];err=abs(actual-q['expected_volume_mm3'])/q['expected_volume_mm3']
            receipt.update(source_volume_relative_error=err,source_volume_relative_threshold=1e-6,source_volume_relative_check_passed=err<1e-6)
            if not err<1e-6:
                assert args.dataset=='COLD' and q['id']=='C09' and q['representation_role']=='OEM_GEOMETRY' and Path(q['step_path']).name=='CHB500W_STANDARD_OEM.step',(q['id'],err)
                diagnostic=json.loads((A/'results/COLD_SOURCE_MATCH_DIAGNOSTIC.json').read_text())
                gk=diagnostic['integration']['local_GK_span'][-1]
                receipt['cross_kernel_volume_open']=dict(status='OPEN_NOT_PASSED',default_reference_mm3=q['expected_volume_mm3'],GK_reference_mm3=gk['volume_mm3'],GK_estimated_relative_error=gk['error'],
                 native_mm3=actual,relative_difference_from_GK=abs(actual-gk['volume_mm3'])/gk['volume_mm3'],
                 original_relative_threshold=1e-6,threshold_unchanged=True,
                 consequence='Part file may be saved and inspected; no full BRep/material/absolute volume equivalence credit. Native38 receipt must carry this open comparison.')
                r.setdefault('source_volume_comparison_open',[]).append(dict(id=q['id'],**receipt['cross_kernel_volume_open']))
                b.checkpoint('source_volume_comparison_open',id=q['id'],relative_error=err)
            else:b.checkpoint('source_volume_verified',id=q['id'],relative_error=err)
        r.update(status=import_status,unique_part_count=nparts)
        r['source_volume_comparison_all_passed']=not r.get('source_volume_comparison_open')
    else:
        imports=json.loads((A/f'results/NATIVE_{args.dataset}_IMPORT.json').read_text());assert imports['status']==import_status and imports['input_sha256']==m.sha(inp)
        r['source_volume_comparison_open']=imports.get('source_volume_comparison_open',[])
        r['source_volume_comparison_all_passed']=not r['source_volume_comparison_open']
        r.update(native_geometry_clearance_verified=False,full_BRep_shape_equivalence_verified=False)
        native={q['id']:q['native_save'] for q in imports['parts']};rows=p['rows']
        for q in rows:
            q['native_sha256']=native[q['native_part_id']]['sha256'];assert m.sha(q['native_path'])==q['native_sha256']
        target=Path(p['assembly_path']);assert sw.SetCurrentWorkingDirectory(str(target.parent))
        if args.mode=='assemble':
            assert not target.exists();model=b.wrap(sw.NewDocument(str(m.TEMPLATES/'gb_assembly.asmdot'),0,0.,0.),'IModelDoc2');assert model is not None
            asm=b.wrap(model,'IAssemblyDoc');fm=b.wrap(model.FeatureManager,'IFeatureManager');fm.EnableFeatureTree=False;fm.EnableFeatureTreeWindow=False
            for start in range(0,len(rows),8):
                chunk=rows[start:start+8];raw=asm.AddComponents3(b.VARIANT(b.pythoncom.VT_ARRAY|b.pythoncom.VT_BSTR,[q['native_path'] for q in chunk]),b.VARIANT(b.pythoncom.VT_ARRAY|b.pythoncom.VT_R8,[v for q in chunk for v in h.t16(q['T_S_local'])]),b.VARIANT(b.pythoncom.VT_ARRAY|b.pythoncom.VT_BSTR,['']*len(chunk))) or []
                assert len(raw)==len(chunk);model.ClearSelection2(True)
                for rc,q in zip(raw,chunk):
                    comp=b.wrap(rc,'IComponent2');comp.ComponentReference=q['id'];comp.Name2=re.sub(r'[ .()/\\\\]','_',q['id']);assert comp.Select4(True,None,False)
                asm.FixComponent();model.ClearSelection2(True);raw=rc=comp=None;gc.collect();asm.LightweightAllResolved();b.checkpoint('inserted',count=start+len(chunk))
            b.identity_inventory(asm,rows);props=b.wrap(b.wrap(model.Extension,'IModelDocExtension').CustomPropertyManager(''),'ICustomPropertyManager')
            for key,value in {'WP10_STATUS':'FIXED_LOCAL_ENGINEERING_CANDIDATE','WP10_COMPONENTS':count,'WP10_MOTION':'FIXED_SOURCE_DATUM_PLACEMENT_NO_MOVING_MATES','WP10_RELEASE':False}.items():props.Add3(key,30,str(value),2)
            model.EditRebuild3();r['native_save']=b.save_new(model,target);b.close_own_saved(model,target,r['native_save']['sha256']);model=asm=fm=props=None;gc.collect()
            r.update(status=assemble_status,component_count=count)
        else:
            saved=json.loads((A/f'results/NATIVE_{args.dataset}_ASSEMBLE.json').read_text());assert saved['status']==assemble_status and saved['input_sha256']==m.sha(inp)
            identity=lambda x:(x['pid'],x['create_time'])
            assert identity(owner)!=identity(imports['owned_sw']) and identity(owner)!=identity(saved['owned_sw']),'Cold read requires a different SolidWorks process from import and assembly'
            r['independent_cold_process_verified']=True
            digest=saved['native_save']['sha256'];assert m.sha(target)==digest
            opened=sw.OpenDoc6(str(target),2,195,'',0,0);assert opened[0] is not None and opened[1]==opened[2]==0
            model=b.wrap(opened[0],'IModelDoc2');units=list(m.val(model,'GetUnits'));assert units[0]==0
            _,observed=b.metadata(model,rows,True);assert len(observed)==count and sum(q['actual_solids'] for q in observed)==count and sum(q['actual_sheets'] for q in observed)==0
            deps=model.GetDependencies2(True,True,False) or [];paths=[deps[i+1] for i in range(0,len(deps),2)];assert len(paths)==nparts and {m.normalized(v) for v in paths}=={m.normalized(q['native_path']) for q in rows}
            assert all(Path(v).resolve().parent==target.parent.resolve() for v in paths)
            r.update(status=cold_status,component_count=count,solid_count=count,sheet_count=0,components=observed,dependencies=paths,native_sha256=digest,document_units=units,
              same_session_part_import=False,local_source_geometry_clearance_inputs=clearance_inputs,full_swept_motion_verified=False)
            b.close_own_saved(model,target,digest);model=None;gc.collect()
    assert not b.documents();b.checkpoint('completed')
except Exception as e:
    r.update(status='FAILED',error=repr(e),traceback=traceback.format_exc())
    if b:b.checkpoint('failed')
    else:out.write_text(json.dumps(r,indent=2),encoding='utf-8')
    raise
finally:
    if sw:
        try:
            for k,v in prefs.get('toggles',{}).items():sw.SetUserPreferenceToggle(k,v)
            for k,v in prefs.get('strings',{}).items():sw.SetUserPreferenceStringValue(k,v)
            for k,v in prefs.get('integers',{}).items():sw.SetUserPreferenceIntegerValue(k,v)
            if oldcommand is not None:sw.CommandInProgress=oldcommand
            sw.DocumentVisible(True,1);sw.DocumentVisible(True,2)
            if b and not b.documents():sw.ExitApp();r['owned_empty_sw_exit_requested']=True
        except Exception:r['cleanup_exception']=traceback.format_exc()
    if b:b.pythoncom.CoUninitialize()
    if out.exists():out.write_text(json.dumps(r,indent=2),encoding='utf-8')
