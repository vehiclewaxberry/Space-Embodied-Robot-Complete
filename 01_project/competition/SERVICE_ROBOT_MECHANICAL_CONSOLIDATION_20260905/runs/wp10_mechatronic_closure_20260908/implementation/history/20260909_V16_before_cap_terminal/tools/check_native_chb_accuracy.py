"""Read one unchanged native part using explicit SOLIDWORKS mass-property accuracy."""
from pathlib import Path
import sys,json,hashlib,importlib.util,traceback,gc,psutil
A=Path(__file__).resolve().parents[1]
helper=A.parents[1]/'wp09_interfaces_20260907_1525/tools/integrate_native_v5.py'
spec=importlib.util.spec_from_file_location('wp10_frozen_native_reader',helper);h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h);m=h.m
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
out=A/'results/NATIVE_CHB_ACCURACY_SCREEN.json';assert not out.exists()
owner=read('results/NATIVE_CHB_ACCURACY_OWNER.json')
native=read('results/NATIVE_COLD_COLD.json');part=A/'mechanical/native/C09.SLDPRT';before=sha(part)
assert any(Path(q['path'])==part and q['sha256']==before for q in native['components'])
diag=read('results/COLD_SOURCE_MATCH_DIAGNOSTIC.json');reference=diag['integration']['local_GK_span'][-1]
r=dict(schema='WP10_NATIVE_CHB_ACCURACY_SCREEN_V1',status='RUNNING',progress=[],rows=[],
 input_sha256={p:sha(A/p) for p in ['results/NATIVE_COLD_COLD.json','results/COLD_SOURCE_MATCH_DIAGNOSTIC.json','mechanical/NATIVE_COLD_INPUTS.json','sources/CHB500W_STANDARD_OEM.step']},
 native_path=str(part),native_sha256=before,owned_sw=owner,source_script_sha256=sha(__file__),
 reference_GK=reference,relative_threshold=1e-6,threshold_changed=False,geometry_changed=False,
 physical_mass_or_full_BRep_equivalence_verified=False,
 official_sources=[
 'https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IMassProperty2~AccuracyLevel.html',
 'https://help.solidworks.com/2020/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IMassProperty2~UseSystemUnits.html',
 'https://help.solidworks.com/2021/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IMassProperty2~Recalculate.html'],
 local_type_library='SW2024 gen_py 83A33D31-27C5-11CE-BFD4-00400513BB57x0x32x0.py; enum4687F359-55D0-4CD3-B6CF-2EB42C11F989x0x32x0.py Higher=2,Medium=1,Lower=0')
b=None;sw=None;model=None
try:
    p=psutil.Process(owner['pid']);assert p.name().lower()=='sldworks.exe' and abs(p.create_time()-owner['create_time'])<.01
    b=h.Builder(out,r);sw=b.sw;assert int(m.val(sw,'GetProcessID'))==owner['pid'] and not b.documents()
    opened=sw.OpenDoc6(str(part),1,3,'',0,0);assert opened[0] is not None and opened[1]==opened[2]==0
    model=b.wrap(opened[0],'IModelDoc2');model.ClearSelection2(True);r['dirty_before']=bool(m.val(model,'GetSaveFlag'))
    ext=b.wrap(m.val(model,'Extension'),'IModelDocExtension');mp=b.wrap(ext.CreateMassProperty2(),'IMassProperty2')
    mp.UseSystemUnits=True;mp.IncludeHiddenBodiesOrComponents=True
    r['initial_accuracy_level']=mp.AccuracyLevel
    for level in [0,1,2]:
        mp.AccuracyLevel=level;assert int(mp.AccuracyLevel)==level and mp.UseSystemUnits
        assert mp.Recalculate()
        volume=float(mp.Volume)*1e9
        err=abs(volume-reference['volume_mm3'])/reference['volume_mm3']
        r['rows'].append(dict(accuracy_level=level,volume_mm3=volume,relative_difference_to_GK=err,within_original_threshold=err<1e-6))
        b.checkpoint('accuracy_calculated',level=level,volume_mm3=volume)
    r['dirty_after']=bool(m.val(model,'GetSaveFlag'));r['source_volume_comparison_at_high_accuracy_passed']=r['rows'][-1]['within_original_threshold']
    r['status']='MAXIMUM_ACCURACY_COMPARISON_PASS' if r['source_volume_comparison_at_high_accuracy_passed'] else 'MAXIMUM_ACCURACY_COMPARISON_OPEN'
    mp=ext=None;gc.collect();sw.CloseDoc(m.val(model,'GetTitle'));model=None;assert not b.documents()
    r['native_sha256_after']=sha(part);assert r['native_sha256_after']==before
    b.checkpoint('read_only_probe_completed')
except Exception as e:
    r.update(status='FAILED',error=repr(e),traceback=traceback.format_exc())
    raise
finally:
    if sw:
        try:
            if model is not None:sw.CloseDoc(m.val(model,'GetTitle'))
            if not b.documents():sw.ExitApp();r['owned_empty_SW_exit_requested']=True
        except Exception:r['cleanup_exception']=traceback.format_exc()
    if b:b.pythoncom.CoUninitialize()
    out.write_text(json.dumps(r,indent=2),encoding='utf-8')
