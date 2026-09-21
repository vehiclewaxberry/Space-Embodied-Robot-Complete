"""Material-checked translation-only sharing, never merge by bbox alone."""
from pathlib import Path
import sys,json,importlib.util,hashlib
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1]
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
c=json.loads((R/'inputs/INTEGRATION_HARNESS_CONTRACT_V6.json').read_text());em=json.loads((R/'results/EMISSION_V6.json').read_text());ch=json.loads((R/'results/INTEGRATION_CHECK_V6.json').read_text());assert ch['status']=='DELTA_GEOMETRY_CLEAR'
spec=importlib.util.spec_from_file_location('canonical_reader',c['geometry_reader']);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
I=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
g=m.Geometry({'parts':{k:dict(path=v['path'],sha256=v['sha256'],T_S_local=I) for k,v in em['parts'].items()},'tolerances':c['acceptance']},{})
from build123d import Location,export_step
out=R/'candidate/canonical';out.mkdir(exist_ok=True);groups=[];instances=[]
for k,v in em['parts'].items():
    s=g.load(k);origin=v['bbox_mm']['min_mm'];local=s.moved(Location(tuple(-x for x in origin)));f=g.facts(local);found=None;comparison=None
    for n,q in enumerate(groups):
        if abs(f['volume_mm3']-q['facts']['volume_mm3'])>1e-5 or max(abs(x-y) for x,y in zip(f['bbox_mm']['size_mm'],q['facts']['bbox_mm']['size_mm']))>1e-5:continue
        a=g.volume(local-q['shape']);b=g.volume(q['shape']-local)
        if max(a,b)<=1e-5:found=n;comparison=[a,b];break
    if found is None:
        found=len(groups);p=out/f'C{found:03}.step';assert not p.exists();export_step(local,p)
        groups.append(dict(id=f'C{found:03}',shape=local,path=str(p),sha256=sha(p),facts=f,representation_role=v['representation_role']));comparison=[0.,0.]
    T=[r[:] for r in I]
    for i in range(3):T[i][3]=origin[i]
    instances.append(dict(id=k,canonical_id=groups[found]['id'],T_native_to_S=T,source_step=v['path'],source_sha256=v['sha256'],source_role=v['representation_role'],canonical_material_difference_mm3=comparison))
for q in groups:q.pop('shape')
d=dict(status='PASS_TRANSLATION_ONLY_MATERIAL_SHARING',unique_parts=groups,instances=instances,emission_sha256=sha(R/'results/EMISSION_V6.json'),geometry_check_sha256=sha(R/'results/INTEGRATION_CHECK_V6.json'),no_rotation_or_scaling=True)
(R/'results/CANONICAL_NATIVE_INPUTS.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8');print('CANONICAL',len(groups),'INSTANCES',len(instances))
