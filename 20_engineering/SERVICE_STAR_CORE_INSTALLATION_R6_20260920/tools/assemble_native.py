"""R6 delta assembly: fixed source poses, new files only, cold readback."""
from geometry import *
import argparse, sys, traceback
R1=D.parent/'SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919'
PN=D/'inputs/NATIVE_ASSEMBLY_PLAN.json'

def exact_roundtrip(b,row):
    """Mass integrators can disagree on imported spline faces; compare actual bodies."""
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.BRepCheck import BRepCheck_Analyzer
    sw=b.sw;target=D/'cad'/(row['id']+'_NATIVE_ROUNDTRIP.step')
    sw.DocumentVisible(True,1)
    opened=sw.OpenDoc6(row['native_path'],1,3,'',0,0);assert opened[0] is not None and opened[1]==0
    doc=b.wrap(opened[0],'IModelDoc2');ext=b.wrap(doc.Extension,'IModelDocExtension')
    doc.Visible=True;title=doc.GetTitle;title=title() if callable(title) else title
    sw.ActivateDoc3(title,False,0,0);doc.ForceRebuild3(False)
    ret=ext.SaveAs(str(target),0,3,None,0,0);assert ret[0] and ret[1]==0
    title=doc.GetTitle;sw.CloseDoc(title() if callable(title) else title)
    def bodies(s):
        ex=TopExp_Explorer(s,TopAbs_SOLID);out=[]
        while ex.More():out.append(ex.Current());ex.Next()
        return out
    src=bodies(source(row));dst=bodies(load(target));assert len(src)==len(dst)==row['expected_solids']
    results=[]
    for i,a in enumerate(src):
        ba=np.array(g.precise_bounds(a));j=min(range(len(dst)),key=lambda j:np.max(np.abs(ba-np.array(g.precise_bounds(dst[j])))))
        z=dst.pop(j);be=float(np.max(np.abs(ba-np.array(g.precise_bounds(z)))))
        assert be<1e-4 and BRepCheck_Analyzer(a).IsValid() and BRepCheck_Analyzer(z).IsValid()
        va=g.volume(cut(a,z));vb=g.volume(cut(z,a));assert va<1e-5 and vb<1e-5,(i,va,vb)
        results.append(dict(body=i,bbox_error_mm=be,source_minus_native_mm3=va,native_minus_source_mm3=vb))
        if i%5==4:b.checkpoint('roundtrip_body_checked',id=row['id'],bodies=i+1)
    return dict(status='PASS_EXACT_BODY_ROUNDTRIP',source_sha256=row['source_sha256'],native_sha256=sha(row['native_path']),roundtrip_path=str(target),roundtrip_sha256=sha(target),bodies=results,source_mass_integral_equivalence=False)

def candidate_material(b,row):
    if row['id'] not in ('R6_MAIN_ANGLED_CARRIER','R6_IF_THERMAL_BRIDGE'):return None
    sw=b.sw;db=next(p for p in sw.GetMaterialDatabases() if p.lower().endswith('solidworks materials.sldmat'))
    x=sw.OpenDoc6(row['native_path'],1,1,'',0,0);assert x[0] is not None and x[1]==0
    doc=b.wrap(x[0],'IModelDoc2');part=b.wrap(doc,'IPartDoc');part.SetMaterialPropertyName2('',db,'6061 Alloy')
    actual=part.GetMaterialPropertyName2('');assert actual[0]=='6061 Alloy',actual
    ext=b.wrap(doc.Extension,'IModelDocExtension');props=b.wrap(ext.CustomPropertyManager(''),'ICustomPropertyManager')
    props.Add3('R6_MATERIAL_SCOPE',30,'GENERIC_6061_DESIGN_CANDIDATE_TEMPER_AND_QUALIFICATION_NOT_FROZEN',2)
    doc.EditRebuild3();saved=doc.Save3(1,0,0);assert saved[0] and saved[1]==0,saved
    digest=sha(row['native_path']);b.close_own_saved(doc,Path(row['native_path']),digest)
    x=sw.OpenDoc6(row['native_path'],1,3,'',0,0);doc=b.wrap(x[0],'IModelDoc2');actual2=b.wrap(doc,'IPartDoc').GetMaterialPropertyName2('');assert actual2[0]=='6061 Alloy'
    title=doc.GetTitle;sw.CloseDoc(title() if callable(title) else title)
    return dict(name='6061 Alloy',database=db,database_sha256=sha(db),native_sha256=digest,readback=actual2,heat_treatment_and_flight_qualification_frozen=False)

def prepare():
    check=read(D/'results/INCREMENT_STATIC_CHECK.json');assert check['valid']
    lay=read(D/'inputs/INSTALLATION_LAYOUT.json');old=read(R4/'inputs/NATIVE_ASSEMBLY_PLAN.json')
    rep={r['id']:r for r in lay['replacements']};gid='R6_CORE_INSTALLATION'
    expected=[dict(rep.get(r['id'],r),group=r['group']) for r in old['expected_leaves']]
    expected += [dict(r,group=gid) for r in lay['parts']]
    changed_gids={r['group'] for r in expected if r['id'] in rep}|{gid}
    groups=[dict(id=k,path=str(D/'native'/f'{k}_R6.SLDASM'),rows=[r for r in expected if r['group']==k]) for k in sorted(changed_gids)]
    byid={r['id']:r for r in groups}
    top=[dict(r,native_path=byid[r['id']]['path']) if r['id'] in byid else r for r in old['top_rows']]
    top.append(dict(id=gid,native_path=byid[gid]['path'],T_S_local=I))
    dl=read(R4/'results/NATIVE_ASSEMBLY_DELIVERY.json')
    locks=old['source_native_files']+[{'path':x['target'],'sha256':x['native_save']['sha256']} for x in dl['parts']]+[x['saved'] for x in dl['groups']]+[dl['service']['saved']]
    locks=list({str(Path(x['path']).resolve()).lower():x for x in locks}.values())
    assert all(sha(x['path'])==x['sha256'] for x in locks)
    assert len({r['id'] for r in expected})==len(expected)
    plan=dict(schema='R6_NATIVE_PLAN_V1',parts=lay['parts']+lay['replacements'],groups=groups,top_rows=top,expected_leaves=expected,
      expected_leaf_count=len(expected),expected_solid_instances=sum(r['expected_solids'] for r in expected),source_native_files=locks,
      source_R4_plan_sha256=sha(R4/'inputs/NATIVE_ASSEMBLY_PLAN.json'),source_layout_sha256=sha(D/'inputs/INSTALLATION_LAYOUT.json'),
      increment_static_check_sha256=sha(D/'results/INCREMENT_STATIC_CHECK.json'),fixed_pose_only=True,portable_package=False,
      CF1_mixed_geometry_installed=True,STOP_installed=False,AUX_installed=False,whole_design_complete=False,ready_to_power=False,flight_ready=False)
    write(PN,plan);print('PLAN',len(plan['parts']),len(groups),len(expected),plan['expected_solid_instances'],flush=True)

def run():
    sys.path.insert(0,str(R1/'tools'));import native_integrate as ni;ni.OUT=D
    import build_integrated as bi;bi.OUT=D
    plan=read(PN);rp=D/'results/NATIVE_ASSEMBLY_DELIVERY.json';assert not rp.exists()
    report=dict(status='RUNNING',progress=[],parts=[],groups=[],save_attempts=[],coordinate_frame='STEP_WORLD_S_MM_IDENTITY_ONCE',
      plan_sha256=sha(PN),whole_design_complete=False,ready_to_power=False,flight_ready=False,new_material_assignment=False)
    ni.configure_com();b=ni.PrototypeBuilder(rp,report);sw=b.sw
    prefs={k:sw.GetUserPreferenceToggle(k) for k in (111,291,691)}
    try:
        assert all(sha(x['path'])==x['sha256'] for x in plan['source_native_files'])
        for k in prefs:sw.SetUserPreferenceToggle(k,k==111)
        for p in plan['parts']:
            assert not Path(p['native_path']).exists()
            sw.DocumentVisible(False,1);b.import_part(p)
            facts=report['parts'][-1]['part_cold_reopen']['facts']
            error=abs(facts['volume_mm3']-p['expected_volume_mm3']);receipt=report['parts'][-1]
            receipt['volume_error_mm3']=error;receipt['direct_volume_comparison_pass']=error<max(1e-4,p['expected_volume_mm3']*1e-5)
            if not receipt['direct_volume_comparison_pass']:
                receipt['geometric_roundtrip']=exact_roundtrip(b,p)
            mat=candidate_material(b,p)
            if mat:
                receipt['material_assignment']=mat;receipt['import_native_save']=dict(receipt['native_save']);receipt['native_save']['sha256']=sha(p['native_path']);receipt['native_save']['bytes']=Path(p['native_path']).stat().st_size
                report['new_material_assignment']=True
            b.checkpoint('part_verified',id=p['id'])
        todo=[(g['id'],g['rows'],Path(g['path'])) for g in plan['groups']]+[('service',plan['top_rows'],D/'native'/globals().get('TOP_NATIVE_FILENAME','SERVICE_STAR_SERVICE_R6.SLDASM'))]
        for tag,rows,target in todo:
            sw.DocumentVisible(False,2);sw.CommandInProgress=True;saved=bi.make(b,rows,target,tag);sw.CommandInProgress=False
            opened=sw.OpenDoc6(str(target),2,195,'',0,0);assert opened[0] is not None and opened[1]==0
            doc=b.wrap(opened[0],'IModelDoc2');asm=b.wrap(doc,'IAssemblyDoc');lookup=b.identity_inventory(asm,rows)
            for r in rows:
                c=lookup[r['id']];assert ni.m.normalized(c.GetPathName())==ni.m.normalized(r['native_path'])
                assert max(abs(x-y) for x,y in zip(list(b.wrap(c.Transform2,'IMathTransform').ArrayData),ni.h.t16(r['T_S_local'])))<1e-8 and c.IsFixed()
            item=dict(id=tag,saved=saved,cold_errors=opened[1],cold_warnings=opened[2],direct_children=len(rows),needs_rebuild2=int(b.wrap(doc.Extension,'IModelDocExtension').NeedsRebuild2))
            if tag=='service':report['service']=item
            else:report['groups'].append(item)
            b.close_own_saved(doc,target,saved['sha256']);b.checkpoint('group_checked',tag=tag)
        report.update(status='PASS_R6_FIXED_POSE_NATIVE_BUILD',source_native_files_unchanged=all(sha(x['path'])==x['sha256'] for x in plan['source_native_files']))
        assert report['source_native_files_unchanged'];b.checkpoint('complete')
    except Exception as e:
        report.update(status='FAILED_CLOSED',error=str(e),traceback=traceback.format_exc());b.checkpoint('failed');raise
    finally:
        try:
            for k,v in prefs.items():sw.SetUserPreferenceToggle(k,v)
            sw.CommandInProgress=False;sw.DocumentVisible(True,1);sw.DocumentVisible(True,2)
        except Exception as cleanup_error:
            report['cleanup_error']=str(cleanup_error);b.checkpoint('cleanup_failed_preserved_original_result')
        b.pythoncom.CoUninitialize()

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['prepare','run']);a=ap.parse_args();{'prepare':prepare,'run':run}[a.mode]()
