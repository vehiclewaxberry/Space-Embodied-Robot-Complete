"""Additional independent MAIN head/washer/nut contacts and retained-hole ligament."""
from pathlib import Path
import hashlib,json,math
from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.TopoDS import TopoDS
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE,TopAbs_EDGE
from OCP.GeomAbs import GeomAbs_Circle
from OCP.gp import gp_Trsf
D=Path(__file__).resolve().parents[2];checks=[];locks={};cache={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):locks[str(p.resolve())]=sha(p);return json.loads(p.read_text(encoding='utf8'))
def ck(n,v,d=None):checks.append(dict(name=n,passed=bool(v),detail=d))
lay=read(D/'inputs/INSTALLATION_LAYOUT.json');geo=read(D/'results/reviewer/GEOMETRY_REVIEW.json')
r4=read(D.parent/'SERVICE_STAR_INTERNAL_LAYOUT_R4_20260920/inputs/NATIVE_ASSEMBLY_PLAN.json')
rows={r['id']:r for r in lay['parts']+lay['replacements']}
def shape(r):
 if r['id'] not in cache:
  locks[r['step_path']]=sha(r['step_path']);assert locks[r['step_path']]==r['source_sha256']
  q=STEPControl_Reader();assert q.ReadFile(r['step_path'])==IFSelect_RetDone;assert q.TransferRoots()>0
  t=gp_Trsf();t.SetValues(*[float(r['T_S_local'][i][j]) for i in range(3) for j in range(4)])
  s=BRepBuilderAPI_Transform(q.OneShape(),t,True).Shape();assert BRepCheck_Analyzer(s).IsValid();cache[r['id']]=s
 return cache[r['id']]
def topo(s,k):
 e=TopExp_Explorer(s,k);a=[]
 while e.More():a.append(e.Current());e.Next()
 return a
def bbox(s):
 b=Bnd_Box();BRepBndLib.AddOptimal_s(s,b,False,False);return b.Get()
def atz(s,z):return [f for f in topo(s,TopAbs_FACE) if abs(bbox(f)[2]-z)<1e-5 and abs(bbox(f)[5]-z)<1e-5]
def contact(a,b,z):
 q=BRepExtrema_DistShapeShape(a,b);q.Perform();assert q.IsDone();ar=0
 for fa in atz(a,z):
  for fb in atz(b,z):
   c=BRepAlgoAPI_Common(fa,fb);c.Build();assert c.IsDone();s=c.Shape();assert BRepCheck_Analyzer(s).IsValid()
   g=GProp_GProps();BRepGProp.SurfaceProperties_s(s,g);ar+=abs(g.Mass())
 return q.Value(),ar
out=[]
for n in range(1,5):
 for a,b,z in [(f'R6H_MAIN_BOLT_{n}',f'R6H_MAIN_WASHER_TOP_{n}',13.6),(f'R6H_MAIN_WASHER_BOTTOM_{n}','upper_equipment_deck_B',-11.5),(f'R6H_MAIN_NUT_{n}',f'R6H_MAIN_WASHER_BOTTOM_{n}',-12)]:
  gap,ar=contact(shape(rows[a]),shape(rows[b]),z);r=dict(a=a,b=b,z_mm=z,gap_mm=gap,area_mm2=ar);out.append(r);ck('additional_bearing:'+a+':'+b,gap<1e-6 and ar>1e-6,r)
old=dict(next(r for r in r4['expected_leaves'] if r['id']=='upper_equipment_deck_B'));old['id']='old_deck';centers=set()
for e in topo(shape(old),TopAbs_EDGE):
 c=BRepAdaptor_Curve(TopoDS.Edge_s(e))
 if c.GetType()==GeomAbs_Circle:
  a=c.Circle();p=a.Location()
  if abs(p.X()+68)<8 and abs(p.Y()-82)<8:centers.add(tuple(round(x,9) for x in [p.X(),p.Y(),p.Z(),a.Radius()]))
ck('existing_hole_source_verified',(-64.,80.,-8.5,1.7) in centers and (-64.,80.,-11.5,1.7) in centers)
nominal_area=math.pi*(3**2-1.7**2);contact2=next(r for r in geo['contact_checks'] if r['a']=='R6H_MAIN_SPACER_2' and r['b']=='upper_equipment_deck_B')['area_mm2']
observation=dict(new_hole_center_S_mm=[-68,82],retained_hole_center_S_mm=[-64,80],both_hole_diameter_mm=3.4,center_distance_mm=math.sqrt(20),nominal_edge_ligament_mm=math.sqrt(20)-3.4,full_spacer_annulus_mm2=nominal_area,actual_spacer_bearing_mm2=contact2,bearing_loss_mm2=nominal_area-contact2,bearing_loss_percent=100*(nominal_area-contact2)/nominal_area,source_hole_edges=sorted(centers),strength_qualified=False,action='Include both holes in local bearing/net-section/fatigue and preload calculation; retain nominal geometry candidate unless the selected load/tolerance case fails.')
for p,h in locks.items():ck('read_only_preservation:'+p,sha(p)==h)
result=dict(schema='R6H_ADDITIONAL_BEARING_REVIEW_V1',status='PASS_NOMINAL_CONTACTS_WITH_STRENGTH_HOLD' if all(x['passed'] for x in checks) else 'FAIL',checks=dict(total=len(checks),passed=sum(x['passed'] for x in checks),failed=[x for x in checks if not x['passed']]),checks_detail=checks,source_locks=locks,additional_contact_count=len(out),combined_nominal_contact_count=len(out)+len(geo['contact_checks']),contacts=out,retained_hole_observation=observation,tool_access_verified=False,thread_engagement_verified=False,manufacturing_release=False)
(D/'results/reviewer/BEARING_STACK_REVIEW.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:result[k] for k in ['status','checks','combined_nominal_contact_count','contacts','retained_hole_observation']},ensure_ascii=False),flush=True)
raise SystemExit(0 if all(x['passed'] for x in checks) else 2)
