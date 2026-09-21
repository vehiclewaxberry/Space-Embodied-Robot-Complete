"""Build isolated source-bound fixed-pose ground integration candidates."""
from native_integrate import *
import copy, gc, re
I=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]

def import_parts(start,end,tag):
    jobs=read(OUT/'inputs/ALL_IMPORT_PLAN.json')['parts'][start:end]
    rp=OUT/'results'/f'IMPORT_{start}_{end}_{tag}.json';assert not rp.exists()
    report={'status':'RUNNING','progress':[],'parts':[],'save_attempts':[],
            'coordinate_frame':'STEP_LOCAL_MM_TO_NATIVE_METRES', 'whole_design_complete':False,
            'import_plan_sha256':m.sha(OUT/'inputs/ALL_IMPORT_PLAN.json')}
    configure_com();b=PrototypeBuilder(rp,report);sw=b.sw
    prefs=dict(toggles={k:sw.GetUserPreferenceToggle(k) for k in (111,291,691)},strings={k:sw.GetUserPreferenceStringValue(k) for k in (8,9,10)},integers={k:sw.GetUserPreferenceIntegerValue(k) for k in (577,578,579,580)})
    try:
        for k in prefs['toggles']:sw.SetUserPreferenceToggle(k,k==111)
        for k,n in ((8,'gb_part.prtdot'),(9,'gb_assembly.asmdot'),(10,'gb_a4.drwdot')):sw.SetUserPreferenceStringValue(k,str(m.TEMPLATES/n))
        for k,v in {577:0,578:1,579:2,580:0}.items():sw.SetUserPreferenceIntegerValue(k,v)
        sw.DocumentVisible(False,1)
        for source_row in jobs:
            row=copy.deepcopy(source_row)
            short=OUT/'native'/(row['id']+'.step')
            if not short.exists():shutil.copy2(row['step_path'],short)
            assert m.sha(short)==row['source_sha256']
            row['step_path']=str(short)
            box=row['expected_local_bbox_mm'];row['expected_local_bbox_mm']={'min_mm':box[0],'max_mm':box[1]}
            assert not Path(row['native_path']).exists(),'Existing import protected'
            b.import_part(row)
            actual=report['parts'][-1]['part_cold_reopen']['facts']['volume_mm3']
            error=abs(actual-row['expected_volume_mm3'])
            report['parts'][-1]['volume_error_mm3']=error
            report['parts'][-1]['volume_numeric_screen_pass']=error<=max(1e-4,row['expected_volume_mm3']*1e-5)
            assert report['parts'][-1]['volume_numeric_screen_pass'], f"Volume mismatch: {row['id']}"
        report['status']='PASS_SOURCE_INCREMENT_IMPORTED_AND_COLD_READ'
        b.checkpoint('complete',count=len(report['parts']))
    except Exception as e:
        report.update(status='FAILED',error=str(e),traceback=traceback.format_exc());b.checkpoint('failed');raise
    finally:
        for k,v in prefs['toggles'].items():sw.SetUserPreferenceToggle(k,v)
        for k,v in prefs['strings'].items():sw.SetUserPreferenceStringValue(k,v)
        for k,v in prefs['integers'].items():sw.SetUserPreferenceIntegerValue(k,v)
        sw.DocumentVisible(True,1);b.pythoncom.CoUninitialize()

def make(b,rows,path,label):
    sw=b.sw;assert not path.exists()
    doc=b.wrap(sw.NewDocument(str(m.TEMPLATES/'gb_assembly.asmdot'),0,0.,0.),'IModelDoc2')
    asm=b.wrap(doc,'IAssemblyDoc');feature=b.wrap(doc.FeatureManager,'IFeatureManager')
    feature.EnableFeatureTree=False;feature.EnableFeatureTreeWindow=False
    for start in range(0,len(rows),8):
        chunk=rows[start:start+8];b.ram_floor()
        raw=asm.AddComponents3(b.VARIANT(b.pythoncom.VT_ARRAY|b.pythoncom.VT_BSTR,[q['native_path'] for q in chunk]),
            b.VARIANT(b.pythoncom.VT_ARRAY|b.pythoncom.VT_R8,[v for q in chunk for v in h.t16(q['T_S_local'])]),
            b.VARIANT(b.pythoncom.VT_ARRAY|b.pythoncom.VT_BSTR,['']*len(chunk))) or []
        assert len(raw)==len(chunk);doc.ClearSelection2(True)
        for rc,q in zip(raw,chunk):
            comp=b.wrap(rc,'IComponent2');comp.ComponentReference=q['id'];comp.Name2=re.sub(r'[ .()/\\]','_',q['id'])
            assert comp.Select4(True,None,False)
        asm.FixComponent();doc.ClearSelection2(True)
        raw=rc=comp=None;gc.collect();asm.LightweightAllResolved()
    b.identity_inventory(asm,rows)
    ext=b.wrap(doc.Extension,'IModelDocExtension');props=b.wrap(ext.CustomPropertyManager(''),'ICustomPropertyManager')
    for k,v in {'DP_STATUS':'GROUND_INTEGRATION_CANDIDATE_NOT_POWER_OR_FLIGHT_RELEASE',
                'DP_SCOPE':'SOURCE_BOUND_FIXED_POSE','DP_GROUP':label,'DP_CHILD_COUNT':len(rows),
                'DP_MOTION_MATES':'NONE','DP_WHOLE_MASS':'UNKNOWN','DP_ENGINEERING_COMPLETE':'FALSE'}.items():props.Add3(k,30,str(v),2)
    feature.EnableFeatureTree=True;feature.EnableFeatureTreeWindow=True
    rebuild=bool(doc.EditRebuild3())
    doc.ShowNamedView2('',7);doc.ViewZoomtofit2()
    result=ext.SaveAs(str(path),0,9,None,0,0);assert result[0] and result[1]==0,(path,result)
    post={'rebuild_api_return':rebuild,'needs_rebuild2':int(ext.NeedsRebuild2),'dirty':bool(m.val(doc,'GetSaveFlag'))}
    digest=m.sha(path);b.close_own_saved(doc,path,digest)
    return {'path':str(path),'sha256':digest,'save':result,'post_save':post}

def build_groups(start,end):
    plan=read(OUT/'inputs/INTEGRATED_ASSEMBLY_PLAN.json')
    rp=OUT/'results'/f'GROUPS_{start}_{end}.json';assert not rp.exists()
    report={'status':'RUNNING','progress':[],'groups':[],'save_attempts':[],
            'assembly_plan_sha256':m.sha(OUT/'inputs/INTEGRATED_ASSEMBLY_PLAN.json')}
    configure_com();b=PrototypeBuilder(rp,report);sw=b.sw
    try:
        sw.DocumentVisible(False,1);sw.DocumentVisible(False,2);sw.CommandInProgress=True
        for g in plan['groups'][start:end]:
            saved=make(b,g['rows'],Path(g['path']),g['id'])
            opened=sw.OpenDoc6(g['path'],2,195,'',0,0);assert opened[0] is not None and opened[1]==0
            doc=b.wrap(opened[0],'IModelDoc2');asm=b.wrap(doc,'IAssemblyDoc');lookup=b.identity_inventory(asm,g['rows'])
            for row in g['rows']:
                comp=lookup[row['id']]
                assert m.normalized(m.val(comp,'GetPathName'))==m.normalized(row['native_path'])
                actual=list(b.wrap(comp.Transform2,'IMathTransform').ArrayData)
                assert max(abs(a-c) for a,c in zip(actual,h.t16(row['T_S_local'])))<1e-8 and comp.IsFixed()
            b.close_own_saved(doc,Path(g['path']),saved['sha256'])
            report['groups'].append({'id':g['id'],'save':saved,'leaves':len(g['rows']),'cold_errors':opened[1],'cold_warnings':opened[2]})
            lookup=doc=asm=None;gc.collect();b.checkpoint('group_saved_cold_verified',id=g['id'],count=len(report['groups']))
        report['status']='PASS_FIXED_GROUP_BUILD_AND_COLD_READ';b.checkpoint('complete')
    except Exception as e:
        report.update(status='FAILED',error=str(e),traceback=traceback.format_exc());b.checkpoint('failed');raise
    finally:
        sw.CommandInProgress=False;sw.DocumentVisible(True,1);sw.DocumentVisible(True,2);b.pythoncom.CoUninitialize()

def top(state,view=False):
    plan=read(OUT/'inputs/INTEGRATED_ASSEMBLY_PLAN.json');s=plan['states'][state];groups={g['id']:g for g in plan['groups']}
    rp=OUT/'results'/f'{"VIEW" if view else "TOP"}_{state}.json';assert not rp.exists()
    report={'status':'RUNNING','progress':[],'save_attempts':[],'state':state,'whole_design_complete':False,
            'assembly_plan_sha256':m.sha(OUT/'inputs/INTEGRATED_ASSEMBLY_PLAN.json')}
    configure_com();b=PrototypeBuilder(rp,report);sw=b.sw
    try:
        target=Path(s['path'])
        if not view:
            sw.DocumentVisible(False,1);sw.DocumentVisible(False,2);sw.CommandInProgress=True
            rows=[{'id':ident,'native_path':groups[ident]['path'],'T_S_local':I} for ident in s['groups']]
            report['saved']=make(b,rows,target,'TOP_'+state)
            sw.CommandInProgress=False
        opened=sw.OpenDoc6(str(target),2,5 if view else 195,'',0,0)
        report['cold_open']={'errors':opened[1],'warnings':opened[2]};assert opened[0] is not None and opened[1]==0
        doc=b.wrap(opened[0],'IModelDoc2');asm=b.wrap(doc,'IAssemblyDoc')
        expected={r['id']:r for k in s['groups'] for r in groups[k]['rows']};seen=set();observed=[]
        for raw in asm.GetComponents(False) or []:
            comp=b.wrap(raw,'IComponent2');path=m.val(comp,'GetPathName')
            if Path(path).suffix.lower()=='.sldasm':continue
            ident=comp.ComponentReference;assert ident in expected and ident not in seen,ident;seen.add(ident)
            q=expected[ident];assert m.normalized(path)==m.normalized(q['native_path'])
            tv=list(b.wrap(comp.Transform2,'IMathTransform').ArrayData)
            assert max(abs(a-c) for a,c in zip(tv,h.t16(q['T_S_local'])))<1e-8 and comp.IsFixed()
            observed.append({'id':ident,'native_path':path,'transform_sw16':tv})
        assert seen==set(expected),(len(seen),len(expected))
        deps=doc.GetDependencies2(True,True,False) or [];paths=[deps[i+1] for i in range(0,len(deps),2)]
        assert all(Path(p).resolve().is_relative_to(OUT/'native') for p in paths)
        report.update(leaf_count=len(seen),components=observed,dependencies=paths,external_geometry_dependencies=0)
        if view:
            sw.DocumentVisible(True,1);sw.DocumentVisible(True,2)
            sw.ActivateDoc3(m.val(doc,'GetTitle'),False,0,0)
            doc.ShowNamedView2('',7);doc.ViewZoomtofit2();doc.GraphicsRedraw2()
            bmp=OUT/'views'/f'{state}_native.bmp';assert doc.SaveBMP(str(bmp),1600,1200)
            from PIL import Image
            png=bmp.with_suffix('.png');Image.open(bmp).save(png)
            report.update(png_path=str(png),png_sha256=m.sha(png),actual_native_capture=True)
        report['status']='PASS_FIXED_POSE_NATIVE_MEMBERSHIP_TRANSFORMS_AND_LOCAL_REFERENCES'
        report['path']=str(target);report['sha256']=m.sha(target);report['needs_rebuild2']=int(b.wrap(doc.Extension,'IModelDocExtension').NeedsRebuild2)
        # View changes on this owned inspection document may be discarded.
        sw.CloseDoc(m.val(doc,'GetTitle'));b.checkpoint('complete',leaves=len(seen))
    except Exception as e:
        report.update(status='FAILED',error=str(e),traceback=traceback.format_exc());b.checkpoint('failed');raise
    finally:
        sw.CommandInProgress=False;sw.DocumentVisible(True,1);sw.DocumentVisible(True,2);b.pythoncom.CoUninitialize()

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['import','groups','top','view']);ap.add_argument('--start',type=int,default=0);ap.add_argument('--end',type=int,default=None);ap.add_argument('--state',default='service');ap.add_argument('--tag',default='r2');a=ap.parse_args()
    if a.mode=='import':import_parts(a.start,a.end,a.tag)
    elif a.mode=='groups':build_groups(a.start,a.end)
    else:top(a.state,a.mode=='view')
