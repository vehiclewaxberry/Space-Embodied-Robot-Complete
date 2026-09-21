"""Read-only hierarchical audit: top receipt + 15 separately resolved groups."""
from pathlib import Path
import json,sys,hashlib,traceback,gc,numpy as np
D=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(D.parent/'SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919/tools'))
import native_integrate as ni
ni.OUT=D
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def matrix(a):
    T=np.eye(4);T[:3,:3]=np.array(a[:9]).reshape(3,3,order='F');T[:3,3]=np.array(a[9:12])*1000
    assert abs(a[12]-1)<1e-10
    return T
plan=read(D/'inputs/NATIVE_ASSEMBLY_PLAN.json');dl=read(D/'results/NATIVE_ASSEMBLY_DELIVERY.json');resume=read(D/'results/NATIVE_SERVICE_TOP_RESUME.json');top=read(D/'results/EXISTING_TOP_INVENTORY.json')
assert resume['status']=='PASS_R6H_SERVICE_TOP_RESUMED_AND_COLD_VERIFIED' and top['status']=='READ_ONLY_INVENTORY_COMPLETE'
assert top['sha256']==resume['service']['saved']['sha256']==sha(resume['service']['saved']['path'])
assert resume['plan_sha256']==sha(D/'inputs/NATIVE_ASSEMBLY_PLAN.json')
actualtop={r['id']:r for r in top['top_rows']};assert set(actualtop)=={r['id'] for r in plan['top_rows']}
for row in plan['top_rows']:
    a=actualtop[row['id']];assert a['fixed'] and ni.m.normalized(a['path'])==ni.m.normalized(row['native_path'])
    assert np.max(np.abs(matrix(a['T'])-row['T_S_local']))<1e-8
locks=plan['source_native_files']+[dict(path=x['target'],sha256=x['native_save']['sha256']) for x in dl['parts']]+[x['saved'] for x in dl['groups']]+[resume['service']['saved']]
locks=list({str(Path(r['path']).resolve()).lower():r for r in locks}.values());assert all(sha(r['path'])==r['sha256'] for r in locks)
rp=D/'results/NATIVE_HIERARCHICAL_RECHECK_V2.json';assert not rp.exists()
r=dict(status='RUNNING',progress=[],save_attempts=[],sessions=[],groups=[],leaves=[],body_counts={},
    source_plan_sha256=sha(D/'inputs/NATIVE_ASSEMBLY_PLAN.json'),source_top_inventory_sha256=sha(D/'results/EXISTING_TOP_INVENTORY.json'),source_resume_sha256=sha(D/'results/NATIVE_SERVICE_TOP_RESUME.json'),
    scope='Cold top hierarchy combined with separately cold-opened fully resolved subassemblies; actual solid/sheet counts; no whole assembly simultaneous resolution claim',
    whole_design_complete=False,ready_to_power=False,flight_ready=False,
    resolution_api_basis='https://help.solidworks.com/2016/english/api/sldworksapi/SolidWorks.interop.sldworks~SolidWorks.interop.sldworks.IAssemblyDoc~ResolveAllLightWeightComponents.html',
    resolution_precondition='Each subassembly has its own visible, activated document window before resolution')
ni.configure_com();b=None;doc=None;seen=set();total=0;maxerr=0;cache={}
try:
    # Release cached model data only in the known empty task-owned SW session.
    b=ni.PrototypeBuilder(rp,r);r['sessions'].append(dict(r['session']))
    if r['session']['pid']==resume['session']['pid'] and not b.documents():
        b.sw.ExitApp();b.pythoncom.CoUninitialize();b=None;gc.collect()
    for index,row in enumerate(plan['top_rows']):
        if b is None:
            b=ni.PrototypeBuilder(rp,r);r['sessions'].append(dict(r['session']))
        b.ram_floor();sw=b.sw;sw.DocumentVisible(False,1);sw.DocumentVisible(True,2)
        x=sw.OpenDoc6(row['native_path'],2,67,'',0,0);assert x[0] is not None and x[1]==0 and x[2]==0,(row['id'],x[1:])
        doc=b.wrap(x[0],'IModelDoc2');doc.Visible=True
        activated=sw.ActivateDoc3(ni.m.val(doc,'GetTitle'),False,0,0)
        assert activated[0] is not None and activated[1]==0,(row['id'],'activation',activated[1])
        activated=None
        asm=b.wrap(doc,'IAssemblyDoc');resolution=int(asm.ResolveAllLightWeightComponents(False))
        b.checkpoint('group_resolution',group=row['id'],resolve_status=resolution)
        assert resolution==0,(row['id'],'resolve_status',resolution)
        expected={p['id']:p for p in plan['expected_leaves'] if p['group']==row['id']};members=b.identity_inventory(asm,list(expected.values()));assert len(members)==len(expected)
        parentT=matrix(actualtop[row['id']]['T']);group_total=0
        for ident,c in members.items():
            assert ident not in seen;seen.add(ident);p=expected[ident];path=c.GetPathName()
            assert ni.m.normalized(path)==ni.m.normalized(p['native_path']) and c.IsFixed() and int(c.GetSuppression2()) in (2,3),ident
            a=list(b.wrap(c.Transform2,'IMathTransform').ArrayData);T=parentT@matrix(a);err=float(np.max(np.abs(T-p['T_S_local'])));maxerr=max(maxerr,err);assert err<1e-8,(ident,err)
            raw=c.GetModelDoc2();assert raw is not None,ident
            part=b.wrap(raw,'IPartDoc');fact=dict(solid_count=len(part.GetBodies2(0,False) or []),sheet_count=len(part.GetBodies2(1,False) or []))
            assert fact['solid_count']==p['expected_solids'] and fact['sheet_count']==p.get('expected_sheets',0),(ident,fact)
            key=ni.m.normalized(path)
            if key in cache:assert cache[key]==fact
            cache[key]=fact;total+=fact['solid_count'];group_total+=fact['solid_count']
            r['leaves'].append(dict(id=ident,group=row['id'],path=path,global_transform_error=err,fixed=True,actual_solids=fact['solid_count'],actual_sheets=fact['sheet_count']))
            part=raw=c=None
        assert bool(doc.ForceRebuild3(False));needs=int(b.wrap(doc.Extension,'IModelDocExtension').NeedsRebuild2);assert needs==0
        r['groups'].append(dict(id=row['id'],path=row['native_path'],sha256=sha(row['native_path']),cold_errors=x[1],cold_warnings=x[2],resolve_status=resolution,resolved=True,leaves=len(expected),actual_solid_instances=group_total,needs_rebuild2=needs))
        sw.CloseDoc(ni.m.val(doc,'GetTitle'));doc=asm=members=x=None;gc.collect();assert not b.documents()
        b.checkpoint('cold_group_verified',group=row['id'],groups=index+1,leaf_count=len(seen),actual_solids=total)
        # A fresh empty session per group bounds SW's retained import/display cache.
        sw.ExitApp();b.pythoncom.CoUninitialize();b=sw=None;gc.collect()
    assert len(seen)==plan['expected_leaf_count']==1153 and total==plan['expected_solid_instances']==1602
    assert all(sha(z['path'])==z['sha256'] for z in locks)
    r.update(status='PASS_HIERARCHICAL_READ_ONLY_NATIVE_RECHECK',direct_group_count=15,leaf_count=len(seen),actual_solid_instances=total,body_counts=cache,unique_native_parts=len(cache),maximum_global_transform_error=maxerr,all_fixed=True,all_paths_match=True,all_leaf_ids_unique=True,locked_files_unchanged=len(locks),documents_saved=0,whole_assembly_simultaneously_resolved=False)
    ni.write(rp,r);print(r['status'],len(seen),total,flush=True)
except Exception as e:
    r.update(status='FAILED_CLOSED',error=str(e),traceback=traceback.format_exc());ni.write(rp,r);raise
finally:
    if b is not None:
        try:
            if doc is not None:b.sw.CloseDoc(ni.m.val(doc,'GetTitle'))
            if not b.documents():b.sw.ExitApp()
        except Exception:pass
        b.pythoncom.CoUninitialize()
