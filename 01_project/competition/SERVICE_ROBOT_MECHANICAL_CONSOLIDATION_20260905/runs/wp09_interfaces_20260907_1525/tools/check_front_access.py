"""All-three-state check of the declared front service prism, explicitly not a plume model."""
from pathlib import Path
import json,sys,importlib.util,hashlib
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1]
c=json.loads((R/'inputs/INTEGRATION_HARNESS_CONTRACT_V6.json').read_text());mf=json.loads((R/'results/INTEGRATION_MANIFEST_V6.json').read_text());job={'parts':{},'tolerances':c['acceptance']};registry={};states={}
lo=[170,-44.5008,-94.15];hi=[220,44.5008,-5.1484]
for st,info in mf['states'].items():
    states[st]=[]
    for row in info['instances']:
        bb=row['bounds_mm']
        if not all(min(hi[i],bb['max_mm'][i])-max(lo[i],bb['min_mm'][i])>=-1e-5 for i in range(3)):continue
        sig=json.dumps([row['source_sha256'],row['T_S_local'],row['id']]);key=str(len(registry))
        if sig not in registry:
            registry[sig]=key;job['parts'][key]=dict(path=row['step_path'],sha256=row['source_sha256'],T_S_local=row['T_S_local'],id=row['id'],role=row['representation_role'])
        states[st].append(registry[sig])
spec=importlib.util.spec_from_file_location('front_access_reader',c['geometry_reader']);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);g=m.Geometry(job,{})
probe=g.Solid.make_box(*(hi[i]-lo[i] for i in range(3)),g.Plane(origin=lo));checks=[]
for key,row in job['parts'].items():
    v=g.volume(probe & g.load(key));checks.append(dict(id=row['id'],role=row['role'],intersection_volume_mm3=v,ok=v<=1e-5,states=[st for st,keys in states.items() if key in keys]))
out=dict(status='PASS_DECLARED_FRONT_SERVICE_PRISM' if all(q['ok'] for q in checks) else 'HOLD_DECLARED_FRONT_SERVICE_PRISM',checks=checks,probe_mm=dict(min=lo,max=hi),source='DESIGN_ASSUMED_SERVICE_PRISM',plume_half_angle=None,plume_verified=False,tool_models_bound=False,all_three_discrete_states=True)
(R/'results/FRONT_SERVICE_PRISM_CHECK.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(dict(status=out['status'],pairs=len(checks),overlaps=[x for x in checks if not x['ok']]),ensure_ascii=False))
