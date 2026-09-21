"""Fresh read-only native audit, resolving leaf batches to bound memory."""
from pathlib import Path
import json,sys,hashlib,traceback,gc
D=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(D.parent/'SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919/tools'))
import native_integrate as ni
ni.OUT=D
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
plan=read(D/'inputs/NATIVE_ASSEMBLY_PLAN.json');dl=read(D/'results/NATIVE_ASSEMBLY_DELIVERY.json');resume=read(D/'results/NATIVE_SERVICE_TOP_RESUME.json')
assert resume['status']=='PASS_R6H_SERVICE_TOP_RESUMED_AND_COLD_VERIFIED' and resume['plan_sha256']==sha(D/'inputs/NATIVE_ASSEMBLY_PLAN.json')
locks=plan['source_native_files']+[dict(path=x['target'],sha256=x['native_save']['sha256']) for x in dl['parts']]+[x['saved'] for x in dl['groups']]+[resume['service']['saved']]
locks=list({str(Path(r['path']).resolve()).lower():r for r in locks}.values());assert all(sha(r['path'])==r['sha256'] for r in locks)
rp=D/'results/NATIVE_ASSEMBLY_RECHECK.json';assert not rp.exists()
r=dict(status='RUNNING',progress=[],save_attempts=[],scope='Cold native identities, paths, global transforms, fixed pose and actual body counts; read only; batched resolution',
  source_plan_sha256=sha(D/'inputs/NATIVE_ASSEMBLY_PLAN.json'),source_resume_sha256=sha(D/'results/NATIVE_SERVICE_TOP_RESUME.json'),whole_design_complete=False,ready_to_power=False,flight_ready=False)
ni.configure_com();b=ni.PrototypeBuilder(rp,r);sw=b.sw;doc=None
try:
    target=Path(resume['service']['saved']['path']);x=sw.OpenDoc6(str(target),2,195,'',0,0);assert x[0] is not None and x[1]==0 and x[2]==0,x[1:]
    doc=b.wrap(x[0],'IModelDoc2');asm=b.wrap(doc,'IAssemblyDoc');r['cold_open']=dict(errors=x[1],warnings=x[2],options=195)
    top=b.identity_inventory(asm,plan['top_rows']);assert len(top)==15
    for row in plan['top_rows']:
        c=top[row['id']];assert ni.m.normalized(c.GetPathName())==ni.m.normalized(row['native_path']) and c.IsFixed()
        assert max(abs(a-z) for a,z in zip(list(b.wrap(c.Transform2,'IMathTransform').ArrayData),ni.h.t16(row['T_S_local'])))<1e-8
    expected={row['id']:row for row in plan['expected_leaves']};seen=set();cache={};maximum=0;total=0;leaves=[]
    allraw=list(asm.GetComponents(False) or []);b.checkpoint('recursive_tree_loaded',components=len(allraw))
    for raw in allraw:
        c=b.wrap(raw,'IComponent2');path=c.GetPathName()
        if Path(path).suffix.lower()!='.sldprt':continue
        ident=c.ComponentReference;assert ident in expected and ident not in seen,ident
        seen.add(ident);row=expected[ident];assert ni.m.normalized(path)==ni.m.normalized(row['native_path']) and c.IsFixed(),ident
        actual=list(b.wrap(c.GetTotalTransform(False),'IMathTransform').ArrayData);err=max(abs(a-z) for a,z in zip(actual,ni.h.t16(row['T_S_local'])));maximum=max(maximum,err);assert err<1e-8,(ident,err)
        k=ni.m.normalized(path)
        if k not in cache:
            if int(c.GetSuppression2()) not in (2,3):c.SetSuppression2(2)
            rawpart=c.GetModelDoc2()
            assert rawpart is not None,ident
            part=b.wrap(rawpart,'IPartDoc');cache[k]=dict(solid_count=len(part.GetBodies2(0,False) or []),sheet_count=len(part.GetBodies2(1,False) or []))
            part=rawpart=None
        facts=cache[k];assert facts['solid_count']==row['expected_solids'] and facts['sheet_count']==row.get('expected_sheets',0),(ident,facts)
        total+=facts['solid_count'];leaves.append(dict(id=ident,path=path,global_transform_error=err,fixed=True,actual_solids=facts['solid_count'],actual_sheets=facts['sheet_count']))
        if len(seen)%30==0:
            c=None;gc.collect();asm.LightweightAllResolved();b.ram_floor();b.checkpoint('leaf_batch_verified',leaves=len(seen),actual_solids=total)
    assert len(seen)==plan['expected_leaf_count']==1153 and set(expected)==seen
    assert total==plan['expected_solid_instances']==1602
    r.update(direct_group_count=15,leaf_count=len(seen),actual_solid_instances=total,all_leaf_ids_unique=True,all_paths_match=True,all_fixed=True,maximum_total_transform_error=maximum,unique_native_parts=len(cache),body_counts=cache,leaves=leaves)
    rebuild=bool(doc.EditRebuild3());needs=int(b.wrap(doc.Extension,'IModelDocExtension').NeedsRebuild2)
    r.update(rebuild_api_return=rebuild,needs_rebuild2=needs);assert rebuild and needs==0
    sw.CloseDoc(ni.m.val(doc,'GetTitle'));doc=None
    assert all(sha(z['path'])==z['sha256'] for z in locks)
    r.update(status='PASS_READ_ONLY_HORIZONTAL_NATIVE_RECHECK',locked_files_unchanged=len(locks),documents_saved=0);b.checkpoint('complete')
except Exception as e:
    r.update(status='FAILED_CLOSED',error=str(e),traceback=traceback.format_exc());b.checkpoint('failed');raise
finally:
    if doc is not None:
        try:sw.CloseDoc(ni.m.val(doc,'GetTitle'))
        except Exception:pass
    b.pythoncom.CoUninitialize()
