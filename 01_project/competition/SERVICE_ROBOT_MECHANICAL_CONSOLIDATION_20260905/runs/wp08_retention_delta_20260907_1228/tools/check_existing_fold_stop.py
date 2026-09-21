"""Measure actual mast/clevis contact and +/-0.1 degree local stop probes.

Read-only source STEP, no model construction or accepted motion contract edits.
Positive result establishes nominal one-way local interference only, not a
park lock, loaded contact, allowable stress, hysteresis or full hinge motion.
"""
from pathlib import Path
import json,hashlib,sys,importlib.util,datetime,traceback
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1]
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def module(p,n):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
    output=R/'results/EXISTING_FOLD_STOP_CHECK.json'
    if output.exists():raise ValueError('Existing stop evidence protected')
    mp=R/'results/INTEGRATION_MANIFEST.json';m=json.loads(mp.read_text())
    rows={r['id']:r for r in m['states']['service']['instances']}
    w6=R.parent/'wp06_side_joint_20260907_0233'
    gp=w6/'tools/verify_joint_geometry.py';bp=w6/'tools/check_bearing_faces.py'
    pins={str(p):sha(p) for p in (mp,gp,bp,Path(__file__))}
    parts={}
    for k in (0,1):
        for stem in ('hold_fold_mast','hold_pivot_clevis'):
            ident=f'{stem}_{k}';row=rows[ident]
            if sha(row['step_path'])!=row['source_sha256']:raise ValueError('Source changed')
            parts[ident]={'path':row['step_path'],'sha256':row['source_sha256'],'T_S_local':row['T_S_local']}
            pins[row['step_path']]=row['source_sha256']
    report=dict(schema='WP08_EXISTING_FOLD_STOP_MEASUREMENT',status='RUNNING',checks=[],input_sha256=pins,
        probe_degrees=[89.9,90.0,90.1],linear_tolerance_mm=1e-5,volume_tolerance_mm3=1e-5,
        minimum_overtravel_material_mm3=.001,minimum_contact_mm2=1,
        scope='Two actual mast/clevis pairs in the SERVICE fold geometry; three local angular probes only',
        mast_park_locked=None,positive_fold_retention_verified=False,full_motion_sweep_verified=False,
        strength_verified=False,manufacturing_release=False)
    def save():output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    save()
    try:
        reader=module(gp,'stop_independent_geometry');bearing=module(bp,'stop_independent_bearing')
        g=reader.Geometry({'parts':parts,'tolerances':{'linear_mm':1e-5,'volume_mm3':1e-5,'integration_eps':1e-7}},pins)
        from build123d import import_step,Axis
        g.import_step=import_step
        for k in (0,1):
            mast=g.load(f'hold_fold_mast_{k}');foot=g.load(f'hold_pivot_clevis_{k}')
            row=rows[f'hold_fold_mast_{k}'];origin=[row['T_S_local'][i][3] for i in range(3)]
            nominal=g.separation(mast,foot)
            contact=bearing.contact_area(mast,foot,(0,0,1),origin[2]-10,tol_mm=1e-5)
            probes=[]
            for delta in (-.1,.1):
                probe=mast.rotate(Axis(origin,(1,0,0)),delta)
                probes.append(dict(fold_degrees=90+delta,**g.separation(probe,foot)))
            passed=(nominal['intersection_volume_mm3']<=1e-5 and contact['status']=='MEASURED'
                and contact['contact_area_mm2']>=1 and probes[0]['intersection_volume_mm3']<=1e-5
                and probes[1]['intersection_volume_mm3']>=.001)
            report['checks'].append(dict(station=k,status='PASS_NOMINAL_ONE_WAY_STOP' if passed else 'FAIL_OR_UNCONFIRMED',
                nominal=nominal,actual_trimmed_face_contact=contact,probes=probes))
            save()
        if not all(sha(p)==d for p,d in pins.items()):raise ValueError('Inputs changed during measurement')
        report['inputs_unchanged']=True
        report['status']='PASS_NOMINAL_ONE_WAY_STOP_ONLY' if all(x['status']=='PASS_NOMINAL_ONE_WAY_STOP' for x in report['checks']) else 'FAIL_OR_UNCONFIRMED'
        report['completed_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();save()
        print(json.dumps({'status':report['status'],'stations':len(report['checks'])}))
    except Exception as exc:
        report.update(status='INCOMPLETE',error=str(exc),traceback=traceback.format_exc());save();raise
if __name__=='__main__':main()
