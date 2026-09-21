"""Independent STEP material comparison of the eleven-part local native export."""
from pathlib import Path
import json,hashlib,sys,importlib.util,itertools,datetime,traceback
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1]
IDENTITY=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    out=R/'results/REAR_RIB_NATIVE_ROUNDTRIP_CHECK_V3.json'
    if out.exists():raise ValueError('Existing evidence protected')
    ep=R/'results/rear_rib/EMISSION.json';np=R/'results/REAR_RIB_NATIVE.json'
    e=json.loads(ep.read_text());n=json.loads(np.read_text())
    if n['status']!='PASS_NATIVE_FIXED_LOCAL_ASSEMBLY_COLD_REOPEN_ONLY':raise ValueError('Native not complete')
    gp=R.parent/'wp06_side_joint_20260907_0233/tools/verify_joint_geometry.py'
    pins={str(p):sha(p) for p in (ep,np,gp,Path(__file__))}
    pins[n['assembly_save']['path']]=n['assembly_save']['sha256']
    pins[n['roundtrip_export']['path']]=n['roundtrip_export']['sha256']
    for row in n['parts']:pins[row['native_save']['path']]=row['native_save']['sha256']
    for row in e['parts'].values():pins[row['path']]=row['sha256']
    report=dict(schema='WP08_REAR_NATIVE_ROUNDTRIP_MATERIAL_CHECK',status='RUNNING',input_sha256=pins,checks=[],
        linear_tolerance_mm=1e-4,volume_tolerance_mm3=1e-5,scope='Only eleven local rear-rib solids; no B601 or whole-star equivalence credit',manufacturing_release=False)
    def save():out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    save()
    try:
        if not all(sha(p)==d for p,d in pins.items()):raise ValueError('Source changed')
        spec=importlib.util.spec_from_file_location('rear_roundtrip_reader',gp);reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
        parts={key:{'path':row['path'],'sha256':row['sha256'],'T_S_local':IDENTITY} for key,row in e['parts'].items()}
        parts['native']={'path':n['roundtrip_export']['path'],'sha256':n['roundtrip_export']['sha256'],'T_S_local':IDENTITY}
        g=reader.Geometry({'parts':parts,'tolerances':{'linear_mm':1e-5,'volume_mm3':1e-5,'integration_eps':1e-7}},pins)
        from build123d import import_step
        g.import_step=import_step;whole=g.load('native');solids=list(whole.solids())
        report['native_step_facts']=g.facts(whole)
        if not whole.is_valid or len(solids)!=11:raise ValueError('Invalid native STEP or solid count')
        facts=[g.facts(s) for s in solids];unused=set(range(len(solids)))
        for ident in sorted(e['parts']):
            source=g.load(ident);source_facts=g.facts(source);ref=source_facts['bbox_mm']
            matches=[]
            for i in unused:
                b=facts[i]['bbox_mm'];err=max(abs(b[k][j]-ref[k][j]) for k in ('min_mm','max_mm') for j in range(3))
                if err<=1e-4:matches.append((i,err))
            if len(matches)!=1:raise ValueError('Nonunique native solid bbox identity: '+ident)
            i,err=matches[0];unused.remove(i)
            extra=g.volume(solids[i]-source);missing=g.volume(source-solids[i]);difference=extra+missing
            report['checks'].append(dict(id=ident,native_solid_index=i,bbox_max_error_mm=err,
                extra_material_mm3=extra,missing_material_mm3=missing,symmetric_difference_mm3=difference,
                status='PASS' if difference<=1e-5 else 'FAIL'))
            save()
        if unused:raise ValueError('Unmatched native solids')
        if not all(sha(p)==d for p,d in pins.items()):raise ValueError('Input changed during measurement')
        report['inputs_unchanged']=True
        report['status']='PASS_LOCAL_NATIVE_STEP_MATERIAL_EQUIVALENCE' if all(r['status']=='PASS' for r in report['checks']) else 'FAIL_MATERIAL_DIFFERENCE'
        report['completed_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();save();print(json.dumps({'status':report['status'],'solids':len(solids)}))
    except Exception as exc:
        report.update(status='INCOMPLETE',error=str(exc),traceback=traceback.format_exc());save();raise
if __name__=='__main__':main()

