from pathlib import Path
import json
from build123d import import_step,GeomType
from OCP.BRepAdaptor import BRepAdaptor_Surface
A=Path(__file__).resolve().parents[1];p=A/'sources/lugs_v30/c-130191-c-3d.stp';s=import_step(p);out=dict(valid=s.is_valid,solids=len(s.solids()),volume_mm3=s.volume,bounds_mm=list(s.bounding_box().min)+list(s.bounding_box().max),faces=[])
for f in s.faces():
 a=BRepAdaptor_Surface(f.wrapped);r=dict(type=str(f.geom_type),area=f.area,center=list(f.center()),bounds=list(f.bounding_box().min)+list(f.bounding_box().max))
 if f.geom_type==GeomType.CYLINDER:
  c=a.Cylinder();r.update(radius=c.Radius(),axis=[c.Axis().Direction().X(),c.Axis().Direction().Y(),c.Axis().Direction().Z()],origin=[c.Location().X(),c.Location().Y(),c.Location().Z()])
 out['faces'].append(r)
(A/'coupled_closure/LUG_OEM_INSPECTION_V30.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
