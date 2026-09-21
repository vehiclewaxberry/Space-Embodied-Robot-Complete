from pathlib import Path
import json,runpy,itertools
import numpy as np
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.gp import gp_Trsf
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
A=Path(__file__).resolve().parents[1];h=runpy.run_path(str(A/'tools/check_fixed_heat_geometry.py'))
n=json.loads((A/'mechanical/NATIVE_COLD_INPUTS.json').read_text())
r=next(r for r in n['rows'] if r['id']=='U202_CHB');q=next(q for q in n['parts'] if q['id']==r['native_part_id'])
facts=[h['prop'](s) for s in h['parts'](h['read'](A/'mechanical/thermal_core.step'))]
b=q['expected_local_bbox_mm'];corners=np.array(list(itertools.product(*zip(b['min_mm'],b['max_mm']))));T=np.array(r['T_S_step'])
pts=corners@T[:3,:3].T+T[:3,3];expected=np.r_[pts.min(0),pts.max(0)]
out=dict(id=r['id'],expected_bbox=expected.tolist(),expected_volume=q['expected_volume_mm3'],
 nearest=sorted([dict(index=i,bbox_error=float(np.max(abs(np.array(f['bbox'])-expected))),volume_error=f['measure']-q['expected_volume_mm3'],facts=f) for i,f in enumerate(facts)],key=lambda f:abs(f['volume_error']))[:3])
tr=gp_Trsf();tr.SetValues(*[float(T[j,k]) for j in range(3) for k in range(4)])
shapes={'local':h['read'](q['step_path']),'transformed':BRepBuilderAPI_Transform(h['read'](q['step_path']),tr,True).Shape(),
 'assembly':h['parts'](h['read'](A/'mechanical/thermal_core.step'))[out['nearest'][0]['index']]}
out['integration']={}
for name,shape in shapes.items():
    vals=[]
    for eps in [1e-6,1e-8,1e-10,1e-12]:
        gp=GProp_GProps();error=BRepGProp.VolumeProperties_s(shape,gp,Eps=eps,OnlyClosed=True,SkipShared=False)
        vals.append(dict(Eps=eps,error=error,volume_mm3=gp.Mass()))
    out['integration'][name]=vals
    vals=[]
    for eps in [1e-8,1e-10]:
        gp=GProp_GProps();error=BRepGProp.VolumePropertiesGK_s(shape,gp,Eps=eps,OnlyClosed=True,IsUseSpan=True)
        vals.append(dict(Eps=eps,error=error,volume_mm3=gp.Mass()))
    out['integration'][name+'_GK_span']=vals
(A/'results/COLD_SOURCE_MATCH_DIAGNOSTIC.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
