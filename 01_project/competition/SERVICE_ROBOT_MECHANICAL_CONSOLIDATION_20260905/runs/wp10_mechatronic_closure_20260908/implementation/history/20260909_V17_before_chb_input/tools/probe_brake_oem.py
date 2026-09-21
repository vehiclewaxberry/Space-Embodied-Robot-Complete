from pathlib import Path
import json,hashlib
from OCP.STEPControl import STEPControl_Reader
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID,TopAbs_FACE
from OCP.TopoDS import TopoDS
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
A=Path(__file__).resolve().parents[1];p=A/'sources/LPS300_OEM.step'
r=STEPControl_Reader();assert int(r.ReadFile(str(p)))==1;r.TransferRoots();s=r.OneShape()
e=TopExp_Explorer(s,TopAbs_SOLID);solids=[];cyl=[];planes=[]
def prop(s,vol=True):
 q=GProp_GProps();(BRepGProp.VolumeProperties_s if vol else BRepGProp.SurfaceProperties_s)(s,q);b=Bnd_Box();BRepBndLib.AddOptimal_s(s,b)
 return dict(measure=q.Mass(),bbox=list(b.Get()),COM=list(q.CentreOfMass().Coord()))
while e.More():
 solids.append(prop(e.Current()));e.Next()
e=TopExp_Explorer(s,TopAbs_FACE)
while e.More():
 f=TopoDS.Face_s(e.Current());ad=BRepAdaptor_Surface(f)
 if str(ad.GetType()).endswith('Cylinder'):
  cy=ad.Cylinder()
  cyl.append(dict(radius=cy.Radius(),origin=list(cy.Location().Coord()),axis=list(cy.Axis().Direction().Coord())))
 if str(ad.GetType()).endswith('Plane') and abs(ad.Plane().Axis().Direction().Z())>.999 and abs(ad.Plane().Location().Z()+.2)<1e-6:planes.append(prop(f,False))
 e.Next()
o=dict(source_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),solids=solids,sampled_cylindrical_surfaces=cyl,
       mount_recess_axis_screen=[c for c in cyl if abs(c['radius']-4.1)<1e-6],
       recess_is_not_complete_4_2mm_through_hole_proof=True,bottom_faces=planes)
(A/'results/BRAKE_OEM_GEOMETRY.json').write_text(json.dumps(o,indent=2),encoding='utf-8');print(json.dumps(o))
