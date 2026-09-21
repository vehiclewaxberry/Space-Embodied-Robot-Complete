"""Read-back geometry: no mechanical or thermal flight certification."""
from pathlib import Path
import json,hashlib,itertools,math
from OCP.STEPControl import STEPControl_Reader
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID,TopAbs_FACE
from OCP.TopoDS import TopoDS
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
A=Path(__file__).resolve().parents[1]
def read(p):
    r=STEPControl_Reader();assert int(r.ReadFile(str(p)))==1;r.TransferRoots();return r.OneShape()
def parts(s):
    e=TopExp_Explorer(s,TopAbs_SOLID);out=[]
    while e.More():out.append(e.Current());e.Next()
    return out
def prop(s,volume=True):
    g=GProp_GProps();(BRepGProp.VolumeProperties_s if volume else BRepGProp.SurfaceProperties_s)(s,g)
    b=Bnd_Box();BRepBndLib.AddOptimal_s(s,b)
    return dict(measure=g.Mass(),COM=list(g.CentreOfMass().Coord()),bbox=list(b.Get()) if not b.IsVoid() else None)
def faces_y(s,y):
    e=TopExp_Explorer(s,TopAbs_FACE);out=[]
    while e.More():
        f=TopoDS.Face_s(e.Current());ad=BRepAdaptor_Surface(f)
        if str(ad.GetType()).endswith('Plane') and abs(ad.Plane().Axis().Direction().Y())>.999 and abs(ad.Plane().Location().Y()-y)<1e-5:out.append(f)
        e.Next()
    return out

def faces_z(s,z):
    e=TopExp_Explorer(s,TopAbs_FACE);out=[]
    while e.More():
        f=TopoDS.Face_s(e.Current());ad=BRepAdaptor_Surface(f)
        if str(ad.GetType()).endswith('Plane') and abs(ad.Plane().Axis().Direction().Z())>.999 and abs(ad.Plane().Location().Z()-z)<1e-5:out.append(f)
        e.Next()
    return out
def common(a,b,volume=True):
    op=BRepAlgoAPI_Common(a,b);op.Build();assert op.IsDone()
    return sum(prop(s)['measure'] for s in parts(op.Shape())) if volume else prop(op.Shape(),False)['measure']
path=A/'mechanical/fixed_heat_installation.step';solids=parts(read(path));facts=[prop(s) for s in solids]
checks=[]
def ck(n,value,**kw):checks.append(dict(name=n,passed=bool(value),**kw))
ck('22_valid_positive_solids',len(solids)==22 and all(BRepCheck_Analyzer(s).IsValid() and f['measure']>0 for s,f in zip(solids,facts)))
walls={str(s):read(A/f'mechanical/fixed_heat_wall_{"pos" if s==1 else "neg"}.step') for s in [-1,1]}
ck('each_wall_one_connected_solid',all(len(parts(w))==1 for w in walls.values()))
areas={s:sum(prop(f,False)['measure'] for f in faces_y(w,int(s)*113.15)) for s,w in walls.items()}
ck('outward_face_area_bounded',all(55000<a<344*180 for a in areas.values()))
config=json.loads((A/'thermal/FIXED_HEAT_PATH.json').read_text());contacts=[];groups={}
for d in config['devices']:
    key=d['id'];x,z=d['center_xz_mm'];s=d['side'];size=d['TIM_mm'];vol=size[0]*size[1]*size[2]
    if key=='U202_CHB':vol=(size[0]*size[1]-4*math.pi*(4.5/2)**2)*size[2]
    is_bottom=d.get('mount_type')=='BOTTOM_PEDESTAL'
    if is_bottom:
        x,y,z=d['seat_origin_S_mm']
        pad=next(i for i,f in enumerate(facts) if abs(f['measure']-vol)<1e-4 and abs(f['COM'][0]-x)<.1 and abs(f['COM'][1]-y)<.1)
        idx=[i for i,f in enumerate(facts) if i!=pad and f['measure']<200000 and abs(f['COM'][0]-x)<31 and abs(f['COM'][1]-y)<31 and z<=f['COM'][2]<=z+20]
    else:
        pad=next(i for i,f in enumerate(facts) if abs(f['measure']-vol)<1e-4 and abs(f['COM'][0]-x)<.1 and abs(f['COM'][2]-z)<.1)
        idx=[i for i,f in enumerate(facts) if i!=pad and f['measure']<200000 and f['COM'][1]*s>0 and abs(f['COM'][0]-x)<31 and abs(f['COM'][2]-z)<31]
    ck(key+'_OEM_group_size',len(idx)==(1 if key=='U202_CHB' else 5))
    groups[key]=[pad]+idx
    if is_bottom:
        plate=read(A/'mechanical/bottom_radiator.step');top=z+size[2]
        bottomarea=sum(common(pf,wf,False) for pf in faces_z(solids[pad],z) for wf in faces_z(plate,z))
        toparea=sum(common(pf,of,False) for pf in faces_z(solids[pad],top) for i in idx for of in faces_z(solids[i],top))
    else:
        y=s*(d['carrier_back_abs_y_mm']-d['carrier_size_mm'][2]);top=y-s*size[2]
        bottomarea=sum(common(pf,wf,False) for pf in faces_y(solids[pad],y) for wf in faces_y(walls[str(s)],y))
        toparea=sum(common(pf,of,False) for pf in faces_y(solids[pad],top) for i in idx for of in faces_y(solids[i],top))
    contacts.append(dict(id=key,area_wall_TIM_mm2=bottomarea,area_TIM_OEM_mm2=toparea))
    expected=3234.4827487648063 if key=='U202_CHB' else 2856.
    ck(key+'_two_contact_faces',abs(bottomarea-expected)<1e-4 and abs(toparea-expected)<1e-4,actual=contacts[-1])
overlaps=[]
for i,j in itertools.combinations(range(len(solids)),2):
    if any(i in g and j in g and i!=g[0] and j!=g[0] for g in groups.values()):continue
    a,b=facts[i]['bbox'],facts[j]['bbox']
    if any(min(a[k+3],b[k+3])-max(a[k],b[k])<1e-6 for k in range(3)):continue
    v=common(solids[i],solids[j]);overlaps.append(dict(pair=[i,j],common_volume_mm3=v))
ck('no_nonOEM_internal_interference',all(abs(v['common_volume_mm3'])<1e-5 for v in overlaps))
out=dict(schema='WP10_FIXED_HEAT_GEOMETRY_V1',checks=checks,check_count=len(checks),checks_passed=all(c['passed'] for c in checks),
  source_step_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),facts=facts,groups=groups,contacts=contacts,overlaps=overlaps,
  outward_radiating_face_area_mm2_by_side=areas,CHB_TIM_contact_area_mm2=contacts[0]['area_TIM_OEM_mm2'],
  wall_volume_mm3_by_side={s:prop(w)['measure'] for s,w in walls.items()},
  wall_mass_estimate_kg_by_side={s:prop(w)['measure']*2700e-9 for s,w in walls.items()},
  prototype_thermal_contact_verified=False,CHB_mount_type=config['devices'][0].get('mount_type','SIDE_WALL'),source_geometry_continuous=True,whole_vehicle_interference_verified=False)
(A/'results/FIXED_HEAT_GEOMETRY.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in out.items() if k not in ['facts','groups','overlaps']}));assert out['checks_passed']
