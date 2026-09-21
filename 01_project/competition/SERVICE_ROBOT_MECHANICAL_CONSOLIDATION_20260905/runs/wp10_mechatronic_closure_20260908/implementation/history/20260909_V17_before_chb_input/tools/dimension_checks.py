from pathlib import Path
from OCP.STEPControl import STEPControl_Reader
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE,TopAbs_SOLID
from OCP.TopoDS import TopoDS
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
import json,math,hashlib
A=Path(__file__).resolve().parents[1];checks=[]
def read(p):
 r=STEPControl_Reader();assert int(r.ReadFile(str(p)))==1;r.TransferRoots();return r.OneShape()
def ck(n,b,**d):checks.append(dict(name=n,passed=bool(b),**d))
s=read(A/'mechanical/converter_carrier.step');b=Bnd_Box();BRepBndLib.Add_s(s,b);v=b.Get();ck('90x90x4',all(abs((v[i+3]-v[i])-n)<1e-5 for i,n in enumerate([90,90,4])),bbox=v)
e=TopExp_Explorer(s,TopAbs_FACE);holes=[]
while e.More():
 a=BRepAdaptor_Surface(TopoDS.Face_s(e.Current()))
 if str(a.GetType()).endswith('Cylinder'):
  c=a.Cylinder();holes.append([*list(c.Location().Coord())[:2],c.Radius()])
 e.Next()
for px,py,r in [(48.3,50.8,2.),(76.,76.,2.25)]:
 for x in [-px/2,px/2]:
  for y in [-py/2,py/2]:ck(f'hole_{x}_{y}_{r}',any(abs(h[0]-x)<1e-6 and abs(h[1]-y)<1e-6 and abs(h[2]-r)<1e-6 for h in holes))
g=GProp_GProps();BRepGProp.VolumeProperties_s(s,g);expected=90*90*4-4*math.pi*(2**2+2.25**2)*4
ck('eight_through_holes_volume',abs(g.Mass()-expected)<1e-6,volume_mm3=g.Mass(),mass_kg_model_density2700=g.Mass()*2.7e-6)
ck('valid_carrier',BRepCheck_Analyzer(s).IsValid())
# OEM vertices are above the carrier upper face; bounding planes give conservative separation.
ass=read(A/'mechanical/converter_installation.step');e=TopExp_Explorer(ass,TopAbs_SOLID);mins=[];vols=[]
while e.More():
 solid=e.Current();bb=Bnd_Box();BRepBndLib.Add_s(solid,bb);p=GProp_GProps();BRepGProp.VolumeProperties_s(solid,p);mins.append(bb.Get()[2]);vols.append(p.Mass());e.Next()
ck('all_exported_solids_positive',all(x>0 for x in vols),count=len(vols));ck('no_OEM_below_plate_upper_plane',all(z>3.99999 or abs(z)<1e-5 for z in mins),solid_min_z=mins)
tim=read(A/'mechanical/converter_tim.step');tb=Bnd_Box();BRepBndLib.Add_s(tim,tb);tv=tb.Get();tg=GProp_GProps();BRepGProp.VolumeProperties_s(tim,tg)
area=55.9*59-4*math.pi*2.25**2
ck('TIM_stock_dimensions',all(abs((tv[i+3]-tv[i])-n)<1e-5 for i,n in enumerate([55.9,59,.229])))
ck('TIM_four_holes_net_volume',abs(tg.Mass()-area*.229)<1e-6,net_area_mm2=area,volume_mm3=tg.Mass())
ck('TIM_valid',BRepCheck_Analyzer(tim).IsValid())
te=TopExp_Explorer(tim,TopAbs_FACE);ths=[]
while te.More():
 a=BRepAdaptor_Surface(TopoDS.Face_s(te.Current()))
 if str(a.GetType()).endswith('Cylinder'):
  cc=a.Cylinder();ths.append([cc.Location().X(),cc.Location().Y(),cc.Radius()])
 te.Next()
for x in [-24.15,24.15]:
 for y in [-25.4,25.4]:ck('TIM_hole_'+str(x)+'_'+str(y),any(abs(h[0]-x)<1e-6 and abs(h[1]-y)<1e-6 and abs(h[2]-2.25)<1e-6 for h in ths))
ck('TIM_installed_at_carrier_top',any(abs(z-4)<1e-5 for z in mins))
contact=json.loads((A/'results/TIM_CONTACT_GEOMETRY.json').read_text())
ck('contact_source_matches_export',contact['source_step_sha256']==hashlib.sha256((A/'mechanical/converter_installation.step').read_bytes()).hexdigest())
ck('OEM_actual_plane_at_selected_stock_top',any(abs(p['COM'][2]-4.229)<1e-6 and p['measure']>area for p in contact['OEM_lower_horizontal_planes']))
ck('no_actual_TIM_volume_overlap',all(abs(p['volume_mm3'])<1e-7 for p in contact['intersections']))
ck('full_cut_area_contacts_OEM_plane',abs(sum(p['measure'] for p in contact['OEM_TIM_coplanar_contact'])-area)<1e-5)
out=dict(all_checks_passed=all(c['passed'] for c in checks),checks=checks,source_bound_thermal_face_gap_mm=.229,installed_stock='TSP1600S_UNCOMPRESSED_NOMINAL',compressed_thickness_mm=None,OEM_self_intersection='NOT_COMPLETED_MEMORY_GUARD; no inherited pass',manufacturing_release=False)
(A/'results/DIMENSION_CHECKS.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out));assert out['all_checks_passed']
