"""Resolve one near-threshold adaptive volume comparison without changing acceptance."""
from pathlib import Path
import json,sys,hashlib,importlib.util
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1]
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
oldp=R/'results/NATIVE_MATERIAL_CHECK.json';old=json.loads(oldp.read_text());assert [r['id'] for r in old['checks'] if not r['ok']]==['C019']
c=json.loads((R/'inputs/INTEGRATION_HARNESS_CONTRACT_V6.json').read_text());cm=json.loads((R/'results/CANONICAL_NATIVE_INPUTS.json').read_text());p=next(x for x in cm['unique_parts'] if x['id']=='C019')
spec=importlib.util.spec_from_file_location('refined_material_reader',c['geometry_reader']);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
I=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
g=m.Geometry({'parts':{'S':dict(path=p['path'],sha256=p['sha256'],T_S_local=I),'N':dict(path=str(R/'native/rt/C019.step'),sha256=sha(R/'native/rt/C019.step'),T_S_local=I)},'tolerances':c['acceptance']},{})
a=g.load('S');b=g.load('N');chain=[]
for eps in [1e-7,1e-9,1e-11]:
    g.eps=eps;va=g.volume(a);vb=g.volume(b);chain.append(dict(integration_eps=eps,source_volume_mm3=va,native_volume_mm3=vb,delta_mm3=abs(va-vb),source_minus_native_mm3=g.volume(a-b),native_minus_source_mm3=g.volume(b-a)))
print(json.dumps(chain),flush=True)
last=chain[-1];convergence=max(abs(last[k]-chain[-2][k]) for k in ('source_volume_mm3','native_volume_mm3'))
ok=max(last['delta_mm3'],last['source_minus_native_mm3'],last['native_minus_source_mm3'])<=1e-5 and convergence<=1e-6
out={**old,'previous_check_sha256':sha(oldp),'previous_check_status':old['status'],'refined_part':'C019','integration_convergence_chain':chain,'integration_refinement_is_not_acceptance_relaxation':True,'volume_acceptance_mm3':1e-5,'linear_acceptance_mm':1e-5,'fine_chain_convergence_mm3':convergence,'status':'PASS_ALL_CANONICAL_NATIVE_MATERIAL_TRANSFERS' if ok else 'HOLD_REFINED_NATIVE_MATERIAL_DIFFERENCE'}
out['checks']=[{**r,'ok':True,'volume_delta_mm3':last['delta_mm3'],'integration_eps':1e-11} if r['id']=='C019' and ok else r for r in old['checks']]
(R/'results/NATIVE_MATERIAL_CHECK_V2.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');assert ok
