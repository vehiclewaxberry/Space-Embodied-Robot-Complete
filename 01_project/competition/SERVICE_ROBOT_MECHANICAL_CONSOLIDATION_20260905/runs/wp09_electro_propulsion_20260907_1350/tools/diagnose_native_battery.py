from pathlib import Path
import sys,json,importlib.util,math
sys.dont_write_bytecode=True
R=Path(r'''F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_electro_propulsion_20260907_1350''')
s=importlib.util.spec_from_file_location('native_diagnostic_parent',R/'tools/build_module_native.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
rp=R/'results/battery_mount_NATIVE_BOUNDED_B3.json';d=json.loads(rp.read_text());assert d['status']=='FAILED'
part=d['parts'][0];native=Path(part['native_save']['path']);out=R/'results/BATTERY_NATIVE_DIAGNOSTIC.json';assert not out.exists()
report=dict(schema='WP09_NATIVE_DIAGNOSTIC',status='RUNNING',progress=[],parts=[],save_attempts=[],input_sha256_before={str(rp):m.sha(rp),str(native):part['native_save']['sha256'],part['source']:part['source_sha256']})
b=m.ModuleBuilder(out,report)
try:
    docs=b.documents();assert len(docs)==1
    model,f=docs[0];assert m.normalized(f['path'])==m.normalized(native) and not f['dirty'] and m.sha(native)==part['native_save']['sha256']
    model=b.wrap(model,'IModelDoc2');body=b.wrap(b.wrap(model,'IPartDoc').GetBodies2(0,False)[0],'IBody2')
    extreme=body.GetExtremePoint(0.,0.,1.);report['extreme_z_raw']=extreme
    try:
        extension=b.wrap(model.Extension,'IModelDocExtension')
        report['high_accuracy_mass_properties2']=extension.GetMassProperties2(2,0,False)
    except Exception as exc:report['high_accuracy_error']=repr(exc)
    pt=list(extreme)[-3:];faces=[]
    for i,raw in enumerate(body.GetFaces()):
        face=b.wrap(raw,'IFace2')
        try:
            closest=list(face.GetClosestPointOn(*pt));faces.append(dict(index=i,closest_raw=closest,distance_mm=1000*math.dist(pt,closest[:3])))
        except Exception as exc:faces.append(dict(index=i,error=repr(exc)))
    report['extreme_to_face_projections']=faces
    b.activate(model,native);model.ClearSelection2(True)
    report['roundtrip_export']=b.save_new(model,R/'results/battery_failed_native_roundtrip.step')
    assert m.sha(native)==part['native_save']['sha256']
    report['input_files_unchanged']=all(m.sha(p)==h for p,h in report['input_sha256_before'].items())
    report['status']='DIAGNOSTIC_RECORDED_NO_PASS_CREDIT';b.checkpoint('diagnostic_complete')
finally:b.pythoncom.CoUninitialize()
