from pathlib import Path
import json
from build123d import import_step
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
C=Path(__file__).resolve().parents[1]
j=json.loads((C/'results/NATIVE_DELTA_INPUTS.json').read_text());a=import_step(j['parts'][0]['step_path']);b=import_step(C/'cad/D000_probe.step')
def volume(shape):
 p=GProp_GProps();e=BRepGProp.VolumeProperties_s(shape.wrapped,p,1e-9,True,False);return dict(volume_mm3=p.Mass(),estimated_relative_error=e)
r=dict(original=volume(a),roundtrip=volume(b),original_valid=a.is_valid,roundtrip_valid=b.is_valid)
for name,shape in [('original_minus_roundtrip',a-b),('roundtrip_minus_original',b-a)]:
 r[name]=dict(volume(shape),solids=len(shape.solids()),valid=shape.is_valid)
(C/'results/NATIVE_DELTA_ROUNDTRIP_PROBE.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps(r))
