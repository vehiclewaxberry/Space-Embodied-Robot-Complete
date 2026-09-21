"""Independent source reads, containment and collision checks; no downstream release."""
from pathlib import Path
import json,hashlib,math,numpy as np
from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.gp import gp_Trsf
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID

D=Path(__file__).resolve().parents[1]; ROOT=D.parents[1]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):
    r=STEPControl_Reader();assert r.ReadFile(str(p))==IFSelect_RetDone;assert r.TransferRoots()>0;return r.OneShape()
def bounds(s):
    b=Bnd_Box();BRepBndLib.AddOptimal_s(s,b,False,False);a=b.Get();return np.array(a[:3]),np.array(a[3:])
def volume(s):
    p=GProp_GProps();BRepGProp.VolumeProperties_s(s,p);return p.Mass()
def moved(s,T):
    t=gp_Trsf();t.SetValues(*[float(T[i][j]) for i in range(3) for j in range(4)]);return BRepBuilderAPI_Transform(s,t,True).Shape()
lock=read(D/'inputs/SOURCE_LOCK.json')
assert all(sha(x['path'])==x['sha256'] for x in lock['files'])
path=ROOT/'20_engineering/SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919/inputs/NEUTRAL_SOURCE_MAP.json'
m=read(path);b=read(ROOT/'20_engineering/SERVICE_STAR_INTERNAL_HARNESS_ORBIT_R2_20260919/inputs/SOURCE_LOCAL_BOUNDS.json');assert b['map_sha256']==sha(path)
out=load(D/'cad/B601_INTERFACE_RESERVATION.step');design=[];ex=TopExp_Explorer(out,TopAbs_SOLID)
while ex.More():design.append(ex.Current());ex.Next()
p=read(D/'inputs/BOARD_RESERVATION.json');minbox=np.array(p['reserved_box_min']);maxbox=np.array(p['reserved_box_max'])
parts=[]
for i,s in enumerate(design):
    lo,hi=bounds(s)
    parts.append({'label':'STEP_solid_'+str(i+1),'valid':bool(BRepCheck_Analyzer(s).IsValid()),'positive_volume':bool(volume(s)>0),'bounds_mm':[lo.tolist(),hi.tolist()],'inside_old_slot':bool(np.all(lo>=minbox-1e-7)&np.all(hi<=maxbox+1e-7))})
collisions=[]; cache={}; comparisons=0; broad_rejected=0;contexts={}
for state,st in m['states'].items():
    rr=[r for g in m['groups'] if g['id'] in st['groups'] for r in g['rows']]
    for row in rr:
        # This is a replacement-detail view of a same-function budget box, not an intersection waiver for hardware.
        if row['id']=='equipment_arm_drive':continue
        a,z=map(np.array,b['bounds_by_path'][row['step_path']]);T=np.array(row['T_S_local'])
        v=np.array([[x,y,t] for x in [a[0],z[0]] for y in [a[1],z[1]] for t in [a[2],z[2]]])@T[:3,:3].T+T[:3,3];lo,hi=v.min(0),v.max(0)
        if np.any(lo>maxbox+4) or np.any(hi<minbox-4):continue
        contexts[row['id']]=row
        for child,piece in zip(design,parts):
            a,z=map(np.array,piece['bounds_mm'])
            if np.any(lo>=z) or np.any(hi<=a):broad_rejected+=1;continue
            key=(row['step_path'],tuple(T.flatten()))
            if key not in cache:
                assert sha(row['step_path'])==row['source_sha256'];cache[key]=moved(load(row['step_path']),T)
            common=BRepAlgoAPI_Common(child,cache[key]);common.Build();comparisons+=1
            assert common.IsDone() and BRepCheck_Analyzer(common.Shape()).IsValid()
            vol=volume(common.Shape())
            if vol>1e-6:collisions.append({'state':state,'new':piece['label'],'old':row['id'],'volume_mm3':vol})
# Source STEP is tested separately from the source-level object.
vsum=60*40*1.6-4*math.pi*1.6**2*1.6+60*40*18+2*12*8*8+8*8*6+12*8*6+math.pi*1.5**2*(1+6+2*math.pi+2+1+20+2*math.pi+2)
roundtrip={'valid':bool(BRepCheck_Analyzer(out).IsValid()),'solid_count':len(design),'expected_solid_count':8,'volume_mm3':volume(out),'analytic_sum_volume_mm3':vsum,'volume_match':abs(volume(out)-vsum)<1e-5,'sha256':sha(D/'cad/B601_INTERFACE_RESERVATION.step')}
result={'schema':'R3_RESERVATION_STATIC_CHECK_V1','scope':'same-function slot subdivision, three fixed source poses; no installation, stiffness, motion, material or electrical release','parts':parts,'same_function_proxy_replaced_only':'equipment_arm_drive','source_state_count':len(m['states']),'candidate_part_exact_intersection_checks':comparisons,'broadphase_rejections':broad_rejected,'collisions':collisions,'STEP_roundtrip':roundtrip,'geometry_valid_and_contained':all(x['valid'] and x['positive_volume'] and x['inside_old_slot'] for x in parts),'external_static_intersections_clear':len(collisions)==0,'ready_to_wire':False,'ready_to_power':False}
(D/'results/RESERVATION_STATIC_CHECK.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
(D/'inputs/RESERVATION_CONTEXT.json').write_text(json.dumps({'rows':list(contexts.values())},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['parts']},ensure_ascii=False,indent=2))
