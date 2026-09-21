from pathlib import Path
import json,hashlib
from OCP.STEPControl import STEPControl_Reader
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS
from OCP.TopAbs import TopAbs_FACE
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box
A=Path(__file__).resolve().parents[1]
p=A/'sources/CHB500W_STANDARD_OEM.step'
r=STEPControl_Reader();assert int(r.ReadFile(str(p)))==1;r.TransferRoots();s=r.OneShape()
ex=TopExp_Explorer(s,TopAbs_FACE);rows=[]
while ex.More():
 f=TopoDS.Face_s(ex.Current());a=BRepAdaptor_Surface(f)
 if a.GetType()==GeomAbs_Cylinder:
  c=a.Cylinder();b=Bnd_Box();BRepBndLib.AddOptimal_s(f,b)
  rows.append(dict(radius=c.Radius(),axis=list(c.Axis().Direction().Coord()),center=list(c.Location().Coord()),bounds=list(b.Get())))
 ex.Next()
out=dict(source=str(p),source_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),cylinders=rows)
(A/'results/CHB_INPUT_OEM_PROBE_V18.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out))
