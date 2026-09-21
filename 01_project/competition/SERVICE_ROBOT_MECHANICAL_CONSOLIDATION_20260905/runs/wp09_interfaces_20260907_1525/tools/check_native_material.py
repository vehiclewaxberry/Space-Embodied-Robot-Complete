"""Cold native->STEP material comparison, same 1e-5 mm/mm3 thresholds."""
from pathlib import Path
import sys,json,importlib.util,hashlib
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1]
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
c=json.loads((R/'inputs/INTEGRATION_HARNESS_CONTRACT_V6.json').read_text());cm=json.loads((R/'results/CANONICAL_NATIVE_INPUTS.json').read_text())
spec=importlib.util.spec_from_file_location('native_material_reader',c['geometry_reader']);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
I=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]];job=dict(parts={},tolerances=c['acceptance']);pins={}
for p in cm['unique_parts']:
    k=p['id'];rt=R/'native/rt'/(k+'.step');native=R/'native/p'/(k+'.SLDPRT');assert rt.exists() and native.exists()
    job['parts'][k+'S']=dict(path=p['path'],sha256=p['sha256'],T_S_local=I);job['parts'][k+'N']=dict(path=str(rt),sha256=sha(rt),T_S_local=I);pins[str(native)]=sha(native)
g=m.Geometry(job,pins);checks=[]
for p in cm['unique_parts']:
    k=p['id'];a=g.load(k+'S');b=g.load(k+'N');fa=g.facts(a);fb=g.facts(b)
    ab=g.volume(a-b);ba=g.volume(b-a);ve=abs(fa['volume_mm3']-fb['volume_mm3']);be=max(abs(fa['bbox_mm'][key][i]-fb['bbox_mm'][key][i]) for key in ('min_mm','max_mm') for i in range(3))
    ok=fa['shape_valid'] and fb['shape_valid'] and fa['solid_count']==fb['solid_count']==1 and max(ab,ba,ve)<=1e-5 and be<=1e-5
    checks.append(dict(id=k,ok=ok,source_minus_native_mm3=ab,native_minus_source_mm3=ba,volume_delta_mm3=ve,bbox_delta_mm=be,source_facts=fa,native_facts=fb));print(k,ok,flush=True)
out=dict(status='PASS_ALL_CANONICAL_NATIVE_MATERIAL_TRANSFERS' if all(x['ok'] for x in checks) else 'HOLD_NATIVE_MATERIAL_DIFFERENCE',canonical_count=len(checks),instance_count=len(cm['instances']),checks=checks,input_sha256={**pins,**{v['path']:v['sha256'] for v in job['parts'].values()}},canonical_manifest_sha256=sha(R/'results/CANONICAL_NATIVE_INPUTS.json'))
(R/'results/NATIVE_MATERIAL_CHECK.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');assert out['status'].startswith('PASS')
