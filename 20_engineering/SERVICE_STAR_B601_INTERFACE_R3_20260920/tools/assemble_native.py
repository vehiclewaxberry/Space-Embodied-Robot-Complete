"""R3 local SolidWorks delta. Never modify the sealed R1/R2 native files."""
from pathlib import Path
import json,hashlib,sys,numpy as np,argparse,traceback,math,copy
D=Path(__file__).resolve().parents[1];ROOT=D.parents[1];R1=D.parent/'SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919';R2=D.parent/'SERVICE_STAR_INTERNAL_HARNESS_ORBIT_R2_20260919'
I=np.eye(4).tolist()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
PN=D/'inputs/NATIVE_ASSEMBLY_PLAN.json'
def prepare():
    check=read(D/'results/RESERVATION_STATIC_CHECK.json');assert check['geometry_valid_and_contained'] and check['external_static_intersections_clear']
    assert check['STEP_roundtrip']['volume_match'] and check['STEP_roundtrip']['solid_count']==8
    (D/'native').mkdir(exist_ok=True)
    a=np.array([x['bounds_mm'] for x in check['parts']]);part={'id':'equipment_arm_drive','step_path':str(D/'cad/B601_INTERFACE_RESERVATION.step'),'source_sha256':sha(D/'cad/B601_INTERFACE_RESERVATION.step'),'native_path':str(D/'native/B601_INTERFACE_RESERVATION_R3.SLDPRT'),'expected_solids':8,'expected_sheets':0,'expected_volume_mm3':check['STEP_roundtrip']['volume_mm3'],'expected_local_bbox_mm':{'min_mm':a[:,0,:].min(0).tolist(),'max_mm':a[:,1,:].max(0).tolist()},'T_S_local':I,'representation_role':'FUNCTIONAL_ENVELOPE','physical_material':None}
    src=read(R1/'inputs/INTEGRATED_ASSEMBLY_PLAN.json');g=next(g for g in src['groups'] if g['id'] in src['states']['service']['groups'] and any(r['id']==part['id'] for r in g['rows']))
    group={'id':g['id'],'path':str(D/'native/EQUIPMENT_GROUP_R3.SLDASM'),'rows':[part if r['id']==part['id'] else r for r in g['rows']]}
    r2=read(R2/'inputs/NATIVE_ROUTE_PLAN.json');top=[]
    for r in r2['top_rows']:top.append(dict(r,native_path=group['path']) if r['id']==g['id'] else r)
    assert sum(x['native_path']==group['path'] for x in top)==1
    expected={r['id']:r for gid in src['states']['service']['groups'] for g in src['groups'] if g['id']==gid for r in g['rows']}
    expected.update({x['id']:x for x in r2['parts']});expected[part['id']]=part
    assert len(expected)==1110
    sources=read(R2/'results/R1_PRESERVATION.json')['native_files']
    r2del=read(R2/'results/NATIVE_ROUTE_DELIVERY_V2.json')
    extra=[x['target'] for x in r2del['parts']]+[r2del[k]['saved']['path'] for k in ['group','detail','service']]
    sources += [{'path':p,'sha256':sha(p)} for p in extra]
    assert all(sha(x['path'])==x['sha256'] for x in sources)
    plan={'schema':'R3_NATIVE_ASSEMBLY_PLAN_V1','part':part,'group':group,'top_rows':top,'expected_leaves':list(expected.values()),'source_native_files':sources,'expected_full_leaf_count':1110,'expected_solids_after_one_to_eight_replacement':1520,'source_R2_plan_sha256':sha(R2/'inputs/NATIVE_ROUTE_PLAN.json'),'portable_package':False,'R1_R2_native_directories_required':True,'all_material_mass_and_flight_credit_for_new_part':False}
    write(PN,plan);print('Prepared R3:',len(group['rows']),'group rows;',len(top),'top groups;',len(sources),'source files locked')
def run():
    sys.path.insert(0,str(R1/'tools'));import native_integrate as ni;ni.OUT=D
    import build_integrated as bi;bi.OUT=D
    plan=read(PN);rp=D/'results/NATIVE_ASSEMBLY_DELIVERY.json';assert not rp.exists()
    report={'status':'RUNNING','progress':[],'parts':[],'save_attempts':[],'coordinate_frame':'STEP_AND_S_MM_IDENTITY_SINGLE_TRANSFORM','plan_sha256':sha(PN),'whole_design_complete':False,'ground_power_ready':False,'flight_ready':False}
    ni.configure_com();b=ni.PrototypeBuilder(rp,report);sw=b.sw
    prefs={k:sw.GetUserPreferenceToggle(k) for k in (111,291,691)}
    try:
        assert all(sha(x['path'])==x['sha256'] for x in plan['source_native_files'])
        for k in prefs:sw.SetUserPreferenceToggle(k,k==111)
        sw.DocumentVisible(False,1);b.import_part(plan['part'])
        facts=report['parts'][-1]['part_cold_reopen']['facts'];assert abs(facts['volume_mm3']-plan['part']['expected_volume_mm3'])<1e-3
        for tag,rows,target in [('group',plan['group']['rows'],Path(plan['group']['path'])),('service',plan['top_rows'],D/'native/SERVICE_STAR_SERVICE_R3.SLDASM')]:
            sw.DocumentVisible(False,2);sw.CommandInProgress=True;saved=bi.make(b,rows,target,tag);sw.CommandInProgress=False
            opened=sw.OpenDoc6(str(target),2,195,'',0,0);assert opened[0] is not None and opened[1]==0
            doc=b.wrap(opened[0],'IModelDoc2');asm=b.wrap(doc,'IAssemblyDoc');lookup=b.identity_inventory(asm,rows)
            for r in rows:
                c=lookup[r['id']];assert ni.m.normalized(ni.m.val(c,'GetPathName'))==ni.m.normalized(r['native_path'])
                assert max(abs(x-y) for x,y in zip(list(b.wrap(c.Transform2,'IMathTransform').ArrayData),ni.h.t16(r['T_S_local'])))<1e-8 and c.IsFixed()
            leaves=[]
            if tag=='service':
                expected={r['id']:r for r in plan['expected_leaves']}
                for raw in asm.GetComponents(False) or []:
                    c=b.wrap(raw,'IComponent2');p=ni.m.val(c,'GetPathName')
                    if Path(p).suffix.lower()!='.sldprt':continue
                    ident=c.ComponentReference;assert ident in expected and ident not in leaves;leaves.append(ident);r=expected[ident]
                    assert ni.m.normalized(p)==ni.m.normalized(r['native_path'])
                    assert max(abs(x-y) for x,y in zip(list(b.wrap(c.Transform2,'IMathTransform').ArrayData),ni.h.t16(r['T_S_local'])))<1e-8 and c.IsFixed()
                assert len(leaves)==1110
                report['all_1110_leaf_paths_and_transforms_verified']=True
            report[tag]={'saved':saved,'cold_errors':opened[1],'cold_warnings':opened[2],'direct_children':len(rows),'leaf_count':len(leaves) if tag=='service' else len(rows),'needs_rebuild2':int(b.wrap(doc.Extension,'IModelDocExtension').NeedsRebuild2)}
            b.close_own_saved(doc,target,saved['sha256']);b.checkpoint('cold_checked',tag=tag)
        report.update(status='PASS_R3_LOCAL_FIXED_POSE_NATIVE_ASSEMBLY',source_native_files_unchanged=all(sha(x['path'])==x['sha256'] for x in plan['source_native_files']),new_material_assignment=False,physical_board_selected=False)
        assert report['source_native_files_unchanged'];b.checkpoint('complete')
    except Exception as e:
        report.update(status='FAILED_CLOSED',error=str(e),traceback=traceback.format_exc());b.checkpoint('failed');raise
    finally:
        for k,v in prefs.items():sw.SetUserPreferenceToggle(k,v)
        sw.CommandInProgress=False;sw.DocumentVisible(True,1);sw.DocumentVisible(True,2)
        if report.get('status','').startswith('PASS_') and report['session']['new_process'] and not b.documents():sw.ExitApp()
        b.pythoncom.CoUninitialize()
def recover_own_import():
    sys.path.insert(0,str(R1/'tools'));import native_integrate as ni;ni.OUT=D
    import pythoncom,win32com.client
    from win32com.client import gencache
    rp=D/'results/NATIVE_ASSEMBLY_DELIVERY.json';r=read(rp)
    assert r['status']=='FAILED_CLOSED' and r['error']=="'coordinate_frame'" and not r['save_attempts']
    assert r['session']['new_process'] and r['session']['documents_before']==[]
    assert len(r['parts'])==1 and r['parts'][0]['import_stage']=='LOADFILE4_RETURNED'
    ni.configure_com();pythoncom.CoInitialize();b=object.__new__(ni.PrototypeBuilder);b.pythoncom=pythoncom
    b.types=gencache.GetModuleForTypelib('{83A33D31-27C5-11CE-BFD4-00400513BB57}',0,32,0)
    try:raw=win32com.client.GetActiveObject('SldWorks.Application')
    except Exception:raw=win32com.client.DispatchEx('SldWorks.Application')
    b.sw=b.wrap(raw,'ISldWorks');assert int(ni.m.val(b.sw,'GetProcessID'))==r['session']['pid']
    docs=b.documents();assert len(docs)==1
    doc,meta=docs[0];assert meta['title']=='B601_INTERFACE_RESERVATION.SLDPRT' and meta['path']=='' and meta['document_type']==1
    facts=json.loads(json.dumps(b.part_facts(doc)))
    expected=copy.deepcopy(r['parts'][0]['facts']);compared=copy.deepcopy(facts);drift=[]
    # Observed read-only repeats changed volume only by 1-2 floating point ULPs.
    # All topology, unit, per-body box and aggregate box fields must still match exactly.
    for old,new in [(expected,compared)]+list(zip(expected['bodies'],compared['bodies'])):
        a=old.pop('volume_mm3');z=new.pop('volume_mm3');drift.append(abs(a-z)/math.ulp(a));assert abs(a-z)<=4*math.ulp(a)
    assert compared==expected,'Unexpected non-volume geometry change must not be discarded'
    assert sha(r['parts'][0]['source'])==r['parts'][0]['source_sha256']
    b.sw.CloseDoc(meta['title']);assert not b.documents()
    archive=D/'results/NATIVE_ATTEMPT_01_METADATA_FAILURE.json';assert not archive.exists();rp.rename(archive)
    write(D/'results/NATIVE_IMPORT_RECOVERY.json',{'status':'OWN_UNSAVED_IMPORT_ONLY_CLOSED','pid':r['session']['pid'],'closed_document':meta,'all_nonvolume_geometry_facts_exactly_match':True,'volume_repeat_max_ULP':max(drift),'volume_repeat_acceptance_ULP':4,'source_hash_verified':True,'failure_receipt_sha256':sha(archive),'fix':'Supply required coordinate_frame receipt field; source geometry and native delivery tolerances unchanged'})
    pythoncom.CoUninitialize();print('Recovered only the exact task-owned unsaved import.')
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('mode',choices=['prepare','run','recover']);args=a.parse_args();{'prepare':prepare,'run':run,'recover':recover_own_import}[args.mode]()
