from pathlib import Path
import json,hashlib
from OCP.STEPControl import STEPControl_Reader
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID,TopAbs_FACE
from OCP.TopoDS import TopoDS
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
A=Path(__file__).resolve().parents[1]
r=STEPControl_Reader();assert int(r.ReadFile(str(A/'mechanical/converter_installation.step')))==1;r.TransferRoots();root=r.OneShape();e=TopExp_Explorer(root,TopAbs_SOLID);solids=[]
while e.More():solids.append(e.Current());e.Next()
assert len(solids)==3
def props(s,vol=True):
 p=GProp_GProps();(BRepGProp.VolumeProperties_s if vol else BRepGProp.SurfaceProperties_s)(s,p);b=Bnd_Box();BRepBndLib.Add_s(s,b)
 return dict(measure=p.Mass(),bbox=list(b.Get()) if not b.IsVoid() else None,COM=list(p.CentreOfMass().Coord()))
out=dict(solids=[props(s) for s in solids],intersections=[])
for i,j in [(0,2),(1,2)]:
 op=BRepAlgoAPI_Common(solids[i],solids[j]);op.Build();assert op.IsDone();inter=op.Shape();ss=TopExp_Explorer(inter,TopAbs_SOLID);bits=[]
 while ss.More():bits.append(props(ss.Current()));ss.Next()
 out['intersections'].append(dict(pair=[i,j],pieces=bits,volume_mm3=sum(x['measure'] for x in bits)))
f=TopExp_Explorer(solids[1],TopAbs_FACE);planes=[];plane_faces=[]
while f.More():
 face=TopoDS.Face_s(f.Current());a=BRepAdaptor_Surface(face)
 if str(a.GetType()).endswith('Plane'):
  pl=a.Plane();n=pl.Axis().Direction()
  if abs(n.Z())>.999:
   p=props(face,False)
   if p['bbox'][2]<4.25:planes.append(p);plane_faces.append(face)
 f.Next()
out['OEM_lower_horizontal_planes']=planes
tf=TopExp_Explorer(solids[2],TopAbs_FACE);contacts=[]
while tf.More():
 face=TopoDS.Face_s(tf.Current());ad=BRepAdaptor_Surface(face)
 if str(ad.GetType()).endswith('Plane') and abs(ad.Plane().Axis().Direction().Z())>.999 and abs(ad.Plane().Location().Z()-4.229)<1e-6:
  for of in plane_faces:
   op=BRepAlgoAPI_Common(face,of);op.Build();assert op.IsDone();contacts.append(props(op.Shape(),False))
 tf.Next()
out['OEM_TIM_coplanar_contact']=contacts
out['source_step_sha256']=hashlib.sha256((A/'mechanical/converter_installation.step').read_bytes()).hexdigest()
(A/'results/TIM_CONTACT_GEOMETRY.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out))
