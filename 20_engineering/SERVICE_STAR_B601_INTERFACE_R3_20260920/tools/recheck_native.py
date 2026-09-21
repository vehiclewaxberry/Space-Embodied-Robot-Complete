"""User-requested fresh, read-only cold audit of the final R3 assembly."""
from pathlib import Path
import json, hashlib, sys, traceback

D = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(D.parent/'SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919/tools'))
import native_integrate as ni
ni.OUT = D

def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

plan = read(D/'inputs/NATIVE_ASSEMBLY_PLAN.json')
delivery = read(D/'results/NATIVE_ASSEMBLY_DELIVERY.json')
rp = D/'results/NATIVE_ASSEMBLY_RECHECK_V4.json'
assert not rp.exists(), 'Preserve prior audit receipts'
report = {'status':'RUNNING', 'progress':[], 'save_attempts':[],
          'request':'装配再次检查', 'scope':'cold native fixed-pose assembly, identities, total transforms, suppression, body counts, rebuild and preservation',
          'source_plan_sha256':sha(D/'inputs/NATIVE_ASSEMBLY_PLAN.json'),
          'source_delivery_sha256':sha(D/'results/NATIVE_ASSEMBLY_DELIVERY.json'),
          'whole_design_complete':False, 'ready_to_power':False, 'flight_ready':False}
locked = plan['source_native_files'] + [
    {'path':x['target'], 'sha256':x['native_save']['sha256']} for x in delivery['parts']
] + [delivery[k]['saved'] for k in ['group','service']]
assert all(sha(x['path'])==x['sha256'] for x in locked)
ni.configure_com()
b = ni.PrototypeBuilder(rp, report)
sw = b.sw
target = Path(delivery['service']['saved']['path'])
doc = None
try:
    # 1 silent + 2 read-only + 64 override lightweight default; do NOT set 128.
    opened = sw.OpenDoc6(str(target), 2, 67, '', 0, 0)
    assert opened[0] is not None and opened[1]==0 and opened[2]==0, str(opened[1:])
    doc = b.wrap(opened[0], 'IModelDoc2')
    asm = b.wrap(doc, 'IAssemblyDoc')
    report['cold_open'] = {'errors':opened[1], 'warnings':opened[2], 'options':67, 'fully_resolved_requested':True}
    report['resolve_all_return']=int(asm.ResolveAllLightWeightComponents(False))
    b.checkpoint('explicit_resolution_finished')
    assert report['resolve_all_return']==0
    expected = {r['id']:r for r in plan['expected_leaves']}
    direct = b.identity_inventory(asm, plan['top_rows'])
    assert len(direct)==14
    for row in plan['top_rows']:
        c = direct[row['id']]
        assert ni.m.normalized(c.GetPathName())==ni.m.normalized(row['native_path'])
        assert c.IsFixed()
        values = list(b.wrap(c.Transform2,'IMathTransform').ArrayData)
        assert max(abs(a-z) for a,z in zip(values,ni.h.t16(row['T_S_local']))) < 1e-8
    leaves=[]; cache={}; total=0; maximum=0.; suppressions={}
    for raw in asm.GetComponents(False) or []:
        c=b.wrap(raw,'IComponent2'); path=c.GetPathName()
        if Path(path).suffix.lower()!='.sldprt': continue
        ident=c.ComponentReference
        assert ident in expected and ident not in leaves, ident
        row=expected[ident]; leaves.append(ident)
        assert Path(path).is_file() and ni.m.normalized(path)==ni.m.normalized(row['native_path']), ident
        suppression=int(c.GetSuppression2()); suppressions[str(suppression)]=suppressions.get(str(suppression),0)+1
        assert suppression in (2,3) and c.IsFixed(), (ident,suppression)
        expected_T=ni.h.t16(row['T_S_local'])
        actual_T=list(b.wrap(c.GetTotalTransform(False),'IMathTransform').ArrayData)
        err=max(abs(a-z) for a,z in zip(actual_T,expected_T)); maximum=max(maximum,err)
        assert err<1e-8, (ident,err)
        key=ni.m.normalized(path)
        if key not in cache:
            raw_doc=c.GetModelDoc2(); assert raw_doc is not None, ident
            part=b.wrap(raw_doc,'IPartDoc')
            cache[key]={'solid_count':len(part.GetBodies2(0,False) or []),
                        'sheet_count':len(part.GetBodies2(1,False) or [])}
        facts=cache[key]
        assert facts['solid_count']==row['expected_solids'], (ident,facts,row['expected_solids'])
        assert facts['sheet_count']==row.get('expected_sheets',0), ident
        total+=facts['solid_count']
        if len(leaves)%100==0: b.checkpoint('native_leaf_audit', count=len(leaves))
    assert len(leaves)==1110 and set(leaves)==set(expected)
    assert total==plan['expected_solids_after_one_to_eight_replacement']==1520
    rebuild=bool(doc.ForceRebuild3(False))
    needs=int(b.wrap(doc.Extension,'IModelDocExtension').NeedsRebuild2)
    assert rebuild and needs==0
    report.update(direct_group_count=14,leaf_count=len(leaves),unique_native_part_files=len(cache),
                  actual_solid_instances=total,all_leaf_identities_unique=True,
                  all_native_paths_match=True,all_components_fixed=True,
                  maximum_total_transform_element_error=maximum,suppression_counts=suppressions,
                  per_unique_part_body_counts=cache,rebuild_api_return=rebuild,needs_rebuild2=needs)
    # A best-effort preview is separate from the native-geometry verdict.
    try:
        from PIL import Image
        sw.DocumentVisible(True,1);sw.DocumentVisible(True,2);doc.Visible=True
        sw.ActivateDoc3(ni.m.val(doc,'GetTitle'),False,0,0)
        view=b.wrap(doc.ActiveView,'IModelView');view.EnableGraphicsUpdate=True
        doc.ShowNamedView2('',7);doc.ViewZoomtofit2();doc.GraphicsRedraw2()
        b.pythoncom.PumpWaitingMessages()
        bmp=D/'views/SERVICE_STAR_SERVICE_R3_RESOLVED.bmp'
        ok=bool(doc.SaveBMP(str(bmp),1600,1200));assert ok
        im=Image.open(bmp);png=bmp.with_suffix('.png');im.save(png)
        report['preview']={'png_path':str(png),'sha256':sha(png),
                           'nonblank':any(z-a>10 for a,z in im.convert('RGB').getextrema()),
                           'visual_review':'PENDING'}
    except Exception as e:
        report['preview']={'status':'UNAVAILABLE','error':str(e)}
    sw.CloseDoc(ni.m.val(doc,'GetTitle')); doc=None
    assert not b.documents()
    assert all(sha(x['path'])==x['sha256'] for x in locked)
    report.update(status='PASS_READ_ONLY_NATIVE_ASSEMBLY_RECHECK',
                  native_files_hash_verified_before_and_after=len(locked),
                  all_native_files_unchanged=True,documents_saved=0)
    b.checkpoint('complete')
except Exception as e:
    report.update(status='FAILED_CLOSED',error=str(e),traceback=traceback.format_exc())
    b.checkpoint('failed')
    raise
finally:
    if doc is not None:
        # Only this script's known read-only assembly; never save a rebuilt document.
        sw.CloseDoc(ni.m.val(doc,'GetTitle'))
    b.pythoncom.CoUninitialize()
