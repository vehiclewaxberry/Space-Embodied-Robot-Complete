from pathlib import Path
import json,hashlib
from OCP.STEPControl import STEPControl_Reader
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE
from OCP.TopoDS import TopoDS
A=Path(__file__).resolve().parents[1];out=[]
for r in json.loads((A/'sources/BOTTOM_HARDWARE_CATALOG.json').read_text()):
    p=A/r['path'];assert hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256']
    rr=STEPControl_Reader();assert int(rr.ReadFile(str(p)))==1;rr.TransferRoots();s=rr.OneShape();b=Bnd_Box();BRepBndLib.AddOptimal_s(s,b)
    exp=TopExp_Explorer(s,TopAbs_FACE);planes=[];cyl=[];cones=[]
    while exp.More():
        ad=BRepAdaptor_Surface(TopoDS.Face_s(exp.Current()));kind=str(ad.GetType())
        if kind.endswith('Plane'):
            q=ad.Plane();planes.append(dict(point=list(q.Location().Coord()),normal=list(q.Axis().Direction().Coord())))
        elif kind.endswith('Cylinder'):
            q=ad.Cylinder();cyl.append(dict(radius=q.Radius(),point=list(q.Location().Coord()),axis=list(q.Axis().Direction().Coord())))
        elif kind.endswith('Cone'):
            q=ad.Cone();cones.append(dict(ref_radius=q.RefRadius(),semi_angle=q.SemiAngle(),point=list(q.Location().Coord()),axis=list(q.Axis().Direction().Coord())))
        exp.Next()
    out.append(dict(**r,bbox=list(b.Get()),planes=planes,cylinders=cyl,cones=cones))
(A/'results/BOTTOM_HARDWARE_GEOMETRY.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps([dict(id=r['id'],bbox=r['bbox'],cones=r['cones'],z_planes=[p for p in r['planes'] if abs(p['normal'][2])>.99]) for r in out]))
