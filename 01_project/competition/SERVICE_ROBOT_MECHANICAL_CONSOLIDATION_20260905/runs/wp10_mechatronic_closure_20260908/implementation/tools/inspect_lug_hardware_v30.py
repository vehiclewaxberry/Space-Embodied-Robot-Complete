from pathlib import Path
import json
from build123d import import_step,GeomType
from OCP.BRepAdaptor import BRepAdaptor_Surface
A=Path(__file__).resolve().parents[1];rows=[]
for p in (A/'sources/lugs_v30').glob('*.step'):
 s=import_step(p);b=s.bounding_box();r=dict(file=p.name,valid=s.is_valid,bounds=list(b.min)+list(b.max),solids=len(s.solids()),cylinders=[])
 for f in s.faces():
  if f.geom_type==GeomType.CYLINDER:
   c=BRepAdaptor_Surface(f.wrapped).Cylinder();r['cylinders'].append(dict(radius=c.Radius(),axis=[c.Axis().Direction().X(),c.Axis().Direction().Y(),c.Axis().Direction().Z()],origin=[c.Location().X(),c.Location().Y(),c.Location().Z()]))
 rows.append(r)
(A/'coupled_closure/LUG_HARDWARE_INSPECTION_V30.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows))
