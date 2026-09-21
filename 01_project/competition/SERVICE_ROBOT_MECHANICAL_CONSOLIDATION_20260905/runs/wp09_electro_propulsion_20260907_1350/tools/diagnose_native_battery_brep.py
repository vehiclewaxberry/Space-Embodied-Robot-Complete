from pathlib import Path
import json,hashlib,sys
sys.dont_write_bytecode=True
from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
from OCP.gp import gp_Pnt
from OCP.IGESControl import IGESControl_Writer,IGESControl_Reader
R=Path(r'''F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_electro_propulsion_20260907_1350''')
def read(p,iges=False):
    r=IGESControl_Reader() if iges else STEPControl_Reader();assert r.ReadFile(str(p))==IFSelect_RetDone;assert r.TransferRoots()>0;return r.OneShape()
def volume(s):
    g=GProp_GProps();BRepGProp.VolumeProperties_s(s,g);return g.Mass()
def diff(a,b):
    q=BRepAlgoAPI_Cut(a,b);q.SetFuzzyValue(0);q.Build();assert q.IsDone();return volume(q.Shape())
def bounds(s):
    b=Bnd_Box();BRepBndLib.AddOptimal_s(s,b,False,False);return b.Get()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
dp=R/'results/BATTERY_NATIVE_DIAGNOSTIC.json';d=json.loads(dp.read_text());rp=R/'results/battery_mount_NATIVE_BOUNDED_B3.json';n=json.loads(rp.read_text());src=Path(n['parts'][0]['source']);rt=Path(d['roundtrip_export']['path']);a,b=read(src),read(rt)
q=[1000*x for x in d['extreme_z_raw'][-3:]];vertex=BRepBuilderAPI_MakeVertex(gp_Pnt(*q)).Vertex();dist=BRepExtrema_DistShapeShape(vertex,a);dist.Perform();assert dist.IsDone()
result=dict(schema='WP09_BATTERY_IMPORT_BREP_DIAGNOSTIC',no_tolerance_change=True,native_import_credit=False,source_bbox=bounds(a),native_roundtrip_bbox=bounds(b),source_volume_mm3=volume(a),native_roundtrip_volume_mm3=volume(b),source_minus_native_mm3=diff(a,b),native_minus_source_mm3=diff(b,a),extreme_point_to_source_mm=dist.Value())
ig=R/'results/battery_diagnostic_source.igs';assert not ig.exists();w=IGESControl_Writer('MM',1);assert w.AddShape(a);w.ComputeModel();assert w.Write(str(ig));c=read(ig,True)
result['iges_source_roundtrip']=dict(path=str(ig),sha256=sha(ig),bbox=bounds(c),source_minus_iges_mm3=diff(a,c),iges_minus_source_mm3=diff(c,a),volume_mm3=volume(c))
result['input_sha256']={str(p):sha(p) for p in [dp,rp,src,rt,Path(__file__)]}
out=R/'results/BATTERY_IMPORT_BREP_DIAGNOSTIC.json';assert not out.exists();out.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
