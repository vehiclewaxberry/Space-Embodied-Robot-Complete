from pathlib import Path
import json
from build123d import import_step
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
C=Path(__file__).resolve().parents[1]
j=json.loads((C/'results/NATIVE_DELTA_INPUTS.json').read_text());rows=[]
for q in j['parts'][:10]:
 s=import_step(q['step_path']);d=dict(id=q['id'],default_volume_mm3=float(s.volume),adaptive=[])
 for eps in (1e-5,1e-7,1e-9,1e-11):
  p=GProp_GProps();error=BRepGProp.VolumeProperties_s(s.wrapped,p,eps,True,False)
  d['adaptive'].append(dict(eps=eps,estimated_relative_error=error,volume_mm3=p.Mass()))
 rows.append(d)
r=dict(status='NUMERICAL_VOLUME_DIAGNOSTIC',rows=rows)
(C/'results/NATIVE_DELTA_VOLUME_PROBE.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
print(json.dumps(r))
