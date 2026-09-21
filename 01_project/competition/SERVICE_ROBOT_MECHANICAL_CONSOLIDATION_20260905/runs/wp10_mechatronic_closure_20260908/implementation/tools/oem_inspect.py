from pathlib import Path
from OCP.STEPControl import STEPControl_Reader
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE
from OCP.TopoDS import TopoDS
import json
A=Path(__file__).resolve().parents[1];r=STEPControl_Reader();r.ReadFile(str(A/'sources/CHB500W_STANDARD_OEM.step'));r.TransferRoots();s=r.OneShape();b=Bnd_Box();BRepBndLib.Add_s(s,b)
e=TopExp_Explorer(s,TopAbs_FACE);planes=[]
while e.More():
 f=TopoDS.Face_s(e.Current());a=BRepAdaptor_Surface(f)
 if str(a.GetType()).endswith('Plane'):
  p=a.Plane();planes.append({'origin':list(p.Location().Coord()),'normal':list(p.Axis().Direction().Coord())})
 e.Next()
out={'bbox':b.Get(),'planes':planes}
(A/'results/OEM_GEOMETRY_FACTS.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out))
