"""Geometry primitives only. No import-time validation or design mutation."""
import math
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder,BRepPrimAPI_MakeBox
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse,BRepAlgoAPI_Cut,BRepAlgoAPI_Common
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box
from OCP.gp import gp_Pnt,gp_Dir,gp_Ax2,gp_Trsf
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.STEPControl import STEPControl_Reader
def op(cls,a,b):q=cls(a,b);q.Build();assert q.IsDone();return q.Shape()
def union(items):
 assert items
 s=items[0]
 for x in items[1:]:s=op(BRepAlgoAPI_Fuse,s,x)
 return s
def cyl(r,xyz,axis,L):return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(*xyz),gp_Dir(*axis)),r,L).Shape()
def disk(x,y,r,z=0,h=1):return cyl(r,[x,y,z],[0,0,1],h)
def vol(s):p=GProp_GProps();BRepGProp.VolumeProperties_s(s,p);return p.Mass()
def count(s):
 e=TopExp_Explorer(s,TopAbs_SOLID);n=0
 while e.More():n+=1;e.Next()
 return n
def transform(s,T):t=gp_Trsf();t.SetValues(*[float(T[i][j]) for i in range(3) for j in range(4)]);return BRepBuilderAPI_Transform(s,t,True).Shape()
def bounds(s):b=Bnd_Box();BRepBndLib.AddOptimal_s(s,b);return list(b.Get())
def near(a,b,g=0):return all(a[i]<=b[i+3]+g+1e-7 and a[i+3]>=b[i]-g-1e-7 for i in range(3))
def exact(a,b):
 q=BRepExtrema_DistShapeShape(a,b);q.Perform();assert q.IsDone();d=q.Value();v=vol(op(BRepAlgoAPI_Common,a,b)) if d<1e-7 else 0
 return dict(distance_mm=d,common_volume_mm3=v)
def load(p):q=STEPControl_Reader();assert int(q.ReadFile(str(p)))==1;q.TransferRoots();return q.OneShape()
def capsule(t):
 x0,y0=t['start_mm'];x1,y1=t['end_mm'];w=t['width_mm'];L=math.hypot(x1-x0,y1-y0);assert L>0
 b=BRepPrimAPI_MakeBox(L,w,1).Shape();c=(x1-x0)/L;s=(y1-y0)/L
 T=[[c,-s,0,x0+s*w/2],[s,c,0,y0-c*w/2],[0,0,1,0]]
 return union([transform(b,T),disk(x0,y0,w/2),disk(x1,y1,w/2)])
