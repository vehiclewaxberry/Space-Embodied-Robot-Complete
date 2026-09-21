"""Current-source exact passage checks; no inherited whole-system PASS."""
import argparse,json,math,numpy as np
from battery_variant_context import A,read,sha,baseline,translation
from OCP.STEPControl import STEPControl_Reader
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder,BRepPrimAPI_MakeBox
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common,BRepAlgoAPI_Cut,BRepAlgoAPI_Fuse
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE,TopAbs_IN
from OCP.TopoDS import TopoDS
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.gp import gp_Trsf,gp_Pnt,gp_Ax2,gp_Dir
def transform(s,T):
    t=gp_Trsf();t.SetValues(*[float(T[i][j]) for i in range(3) for j in range(4)]);return BRepBuilderAPI_Transform(s,t,True).Shape()
def load(r):
    q=STEPControl_Reader();assert int(q.ReadFile(r['step_path']))==1;q.TransferRoots();return transform(q.OneShape(),r['T_S_step'])
def op(cls,a,b):
    q=cls(a,b);q.Build();assert q.IsDone();return q.Shape()
def volume(s):
    q=GProp_GProps();BRepGProp.VolumeProperties_s(s,q);return float(q.Mass())
def bounds(s):
    b=Bnd_Box();BRepBndLib.AddOptimal_s(s,b);return list(b.Get())
def near(a,b,g=0):return all(a[i]<=b[i+3]+g+1e-7 and a[i+3]>=b[i]-g-1e-7 for i in range(3))
def exact(a,b):
    q=BRepExtrema_DistShapeShape(a,b);q.Perform();assert q.IsDone();d=float(q.Value());v=volume(op(BRepAlgoAPI_Common,a,b)) if d<1e-7 else 0.;assert math.isfinite(d) and math.isfinite(v);return dict(distance_mm=d,common_volume_mm3=v)
def faces(s):
    out=[];e=TopExp_Explorer(s,TopAbs_FACE)
    while e.More():
        f=TopoDS.Face_s(e.Current());out.append((f,bounds(f)));e.Next()
    return out
def contact_area(a,b):
    total=0
    for f,fb in faces(a):
        for g,gb in faces(b):
            if not near(fb,gb):continue
            q=BRepExtrema_DistShapeShape(f,g);q.Perform();assert q.IsDone()
            if q.Value()>1e-7:continue
            prop=GProp_GProps();BRepGProp.SurfaceProperties_s(op(BRepAlgoAPI_Common,f,g),prop);total+=prop.Mass()
    return float(total)
p=argparse.ArgumentParser();p.add_argument('--state',choices=['service','parking','released'],required=True);a=p.parse_args()
c=read('mechanical/ROOT_BUSHING_DESIGN.json');plan=read('mechanical/ROOT_BUSHING_INSTANCE_PLAN.json');sp=plan['states'][a.state];rows={r['id']:r for r in sp['rows']};changed=sp['changed_ids']+sp['added_ids']
assert all(sha(A/q)==h for q,h in plan['inputs'].items()) and plan['source_script_sha256']==sha(A/'tools/prepare_root_bushing.py')
base=baseline(a.state);bb={k:r['bbox_S_mm'] for k,r in base.items() if k in rows};cache={};hashes={}
def shape(k):
    if k not in cache:
        r=rows[k];assert sha(r['step_path'])==r['source_sha256'];hashes[r['step_path']]=r['source_sha256'];cache[k]=load(r)
    return cache[k]
for k,r in rows.items():
    if k not in base or r['step_path']!=base[k]['step_path'] or np.max(abs(np.asarray(r['T_S_step'])-np.asarray(base[k]['T_S_step'])))>1e-12 or k in changed:bb[k]=bounds(shape(k))
assert set(bb)==set(rows)
bridge='WP01-RB-BRIDGE-R2';wire='WP10_INTERNAL_BATTERY_BYPASS';allowed=set();required=set()
def allow(a,b):allowed.add(tuple(sorted([a,b])))
def require(a,b):allow(a,b);required.add(tuple(sorted([a,b])))
require('ROOT_BUSH_LEFT','ROOT_BUSH_RIGHT')
for n,side in enumerate(['LEFT','RIGHT']):
    require('ROOT_BUSH_'+side,bridge);require('ROOT_KEEPER',bridge);require('ROOT_KEEPER',f'ROOT_SCREW_{n}');allow(f'ROOT_SCREW_{n}',bridge)
inputs=['mechanical/ROOT_BUSHING_DESIGN.json','mechanical/ROOT_BUSHING_INSTANCE_PLAN.json','mechanical/root_bushing_common.py',c['parent_source_plan'],'tools/battery_variant_context.py','thermal/RADIATOR_OBSTACLE_BOUNDS.json']
out=dict(schema='WP10_ROOT_PASSAGE_EXACT_V1',state=a.state,status='RUNNING',source_script_sha256=sha(__file__),inputs={q:sha(A/q) for q in inputs},source_plan_sha256=sha(A/'mechanical/ROOT_BUSHING_INSTANCE_PLAN.json'),changed_ids=changed,tests=[],contacts=[],capture_stops=[],tool_allocation_tests=[],source_hashes=hashes,unchanged_pairs_not_rechecked=True,full_harness_verified=False,whole_design_complete=False)
def save():(A/f'results/ROOT_BUSHING_SCREEN_{a.state.upper()}.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
src=c['bridge_source'];oldp=read(c['parent_source_plan']);old=next(r for r in oldp['states'][a.state]['rows'] if r['id']==bridge);assert all(old[q]==src[q] for q in ['step_path','source_sha256','T_S_step']) and sha(src['step_path'])==src['source_sha256'];hashes[src['step_path']]=src['source_sha256'];previous=load(src)
tools=[BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x,y,107.05),gp_Dir(0,0,1)),1.5,4.6).Shape() for x,y in c['screw_xy_S_mm']];tool=op(BRepAlgoAPI_Fuse,*tools);removed=op(BRepAlgoAPI_Cut,previous,shape(bridge));expected=op(BRepAlgoAPI_Common,previous,tool)
out['bridge_cut_locality']=dict(removed_mm3=volume(removed),added_mm3=volume(op(BRepAlgoAPI_Cut,shape(bridge),previous)),outside_cut_mm3=volume(op(BRepAlgoAPI_Cut,removed,expected)),missing_cut_mm3=volume(op(BRepAlgoAPI_Cut,expected,removed)))
assert all(abs(out['bridge_cut_locality'][k])<1e-6 for k in ['added_mm3','outside_cut_mm3','missing_cut_mm3'])
seen=set()
for k in changed:
    for j,r in rows.items():
        pair=tuple(sorted([k,j]))
        if k==j or pair in seen or r['is_ground_only']:continue
        seen.add(pair)
        if k==bridge and j not in changed and not any(near(bb[j],bounds(t)) for t in tools):continue
        if not near(bb[k],bb[j]):continue
        q=exact(shape(k),shape(j));out['tests'].append(dict(ids=list(pair),**q,nominal_contact_allowed=pair in allowed));save()
out['collisions']=[r for r in out['tests'] if r['common_volume_mm3']>1e-6]
out['unexpected_contacts']=[r for r in out['tests'] if r['distance_mm']<1e-7 and r['common_volume_mm3']<=1e-6 and not r['nominal_contact_allowed']]
for x,y in sorted(required):
    q=exact(shape(x),shape(y));area=contact_area(shape(x),shape(y));out['contacts'].append(dict(ids=[x,y],**q,area_mm2=area,passed=q['distance_mm']<1e-7 and q['common_volume_mm3']<=1e-6 and area>1e-4))
for side in ['LEFT','RIGHT']:
    k='ROOT_BUSH_'+side;keeper='ROOT_KEEPER'
    radial=exact(shape(k),shape(wire));float_gap=exact(shape(k),shape(keeper))['distance_mm']
    stop_shape=transform(shape(k),translation(0,0,-.1));stop_contact=exact(stop_shape,shape(keeper));stop_area=contact_area(stop_shape,shape(keeper))
    upper_hit=volume(op(BRepAlgoAPI_Common,transform(shape(k),translation(0,0,.01)),shape(bridge)))
    lower_hit=volume(op(BRepAlgoAPI_Common,transform(shape(k),translation(0,0,-.11)),shape(keeper)))
    out['capture_stops'].append(dict(id=k,nominal_wire_gap_mm=radial['distance_mm'],keeper_gap_mm=float_gap,down_0p1_stop_contact_area_mm2=stop_area,down_0p1_stop_distance_mm=stop_contact['distance_mm'],up_0p01_interference_mm3=upper_hit,down_0p11_interference_mm3=lower_hit,passed=radial['distance_mm']>=.3-1e-6 and abs(float_gap-.1)<1e-6 and stop_contact['distance_mm']<1e-7 and stop_contact['common_volume_mm3']<=1e-6 and stop_area>1e-4 and upper_hit>1e-4 and lower_hit>1e-4,full_6d_escape_or_clamp_force_proof=False))
for n,(x,y) in enumerate(c['screw_xy_S_mm']):
    shaft=BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x,y,78.15),gp_Dir(0,0,1)),2.5,25).Shape();tb=bounds(shaft)
    for k,r in rows.items():
        if k==f'ROOT_SCREW_{n}' or r['is_ground_only'] or not near(tb,bb[k]):continue
        q=exact(shaft,shape(k));out['tool_allocation_tests'].append(dict(screw=n,obstacle=k,**q,passed=q['common_volume_mm3']<=1e-6))
# Conservative20mm translation sweep: screw bores are filled, never remove obstacles to pass.
# New screws are inserted only after the keeper reaches its final location.
def box(x0,x1,y0,y1,z0,z1):return BRepPrimAPI_MakeBox(gp_Pnt(x0,y0,z0),x1-x0,y1-y0,z1-z0).Shape()
cx,cy,cz=c['datum_S_mm'];x0,x1,y0,y1=c['keeper_outline_xy_local_mm'];k0,k1=c['keeper_z_local_mm'];b0,b1=c['keeper_boss_z_local_mm'];bx0,bx1=c['keeper_boss_x_local_mm'];rr=c['keeper_throat_ID_mm']/2
sweep_base=box(cx+x0-20,cx+x1,cy+y0,cy+y1,cz+k0,cz+k1)
end_bore=BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(cx,cy,cz+k0-1),gp_Dir(0,0,1)),rr,k1-k0+2).Shape()
sweep_base=op(BRepAlgoAPI_Cut,sweep_base,end_bore);sweep_base=op(BRepAlgoAPI_Cut,sweep_base,box(cx,cx+x1+1,cy-rr,cy+rr,cz+k0-1,cz+k1+1))
swept=op(BRepAlgoAPI_Fuse,sweep_base,box(cx+bx0-20,cx+bx1,cy+y0,cy+y1,cz+b0,cz+b1))
# Inclusion is independently checked at representative translations; extrusion construction
# provides the continuous conservative envelope for this fixed profile and translation.
inclusion=[]
for dx in [-20,-15,-10,-5,0]:
    residual=volume(op(BRepAlgoAPI_Cut,transform(shape('ROOT_KEEPER'),translation(dx,0,0)),swept));assert abs(residual)<1e-6;inclusion.append(dict(dx_mm=dx,outside_sweep_volume_mm3=residual))
sweep_tests=[];sbb=bounds(swept);excluded=['ROOT_KEEPER','ROOT_SCREW_0','ROOT_SCREW_1']
for k,row in rows.items():
    if k in excluded or row['is_ground_only'] or not near(sbb,bb[k]):continue
    q=exact(swept,shape(k));sweep_tests.append(dict(obstacle=k,**q,passed=q['common_volume_mm3']<=1e-6))
out['keeper_insertion']=dict(direction_S=[1,0,0],travel_mm=20,sweep_type='CONSERVATIVE_CSG_TRANSLATIONAL_ENVELOPE_WITH_SCREW_BORES_FILLED',inclusion_samples=inclusion,tests=sweep_tests,excluded_ordered_parts=excluded,screws_installed_after_keeper=True,passed=all(q['passed'] for q in sweep_tests),physical_assembly_or_full_tool_qualified=False)
if a.state=='parking':
    theta=math.radians(10);R=np.eye(4);R[1:3,1:3]=[[math.cos(theta),-math.sin(theta)],[math.sin(theta),math.cos(theta)]]
    out['release_10deg_counterexample']=[]
    for n,x in enumerate([-115,-40]):
        k=f'hold_fold_mast_{n}';pivot=translation(x,-99,135.15);rotated=transform(shape(k),pivot@R@np.linalg.inv(pivot));point=gp_Pnt(x,-110,149.15)
        classifier=BRepClass3d_SolidClassifier(rotated,point,1e-7);inside=classifier.State()==TopAbs_IN
        out['release_10deg_counterexample'].append(dict(station=n,endpoint_S_mm=[x,-110,149.15],endpoint_center_inside_current_mast=inside,scope='Specific fixed unbound endpoint at10degrees, not universal route impossibility'));assert inside
out['failures']=[q for q in out['keeper_insertion']['tests'] if not q['passed']]+[r for group in ['contacts','capture_stops','tool_allocation_tests'] for r in out[group] if not r['passed']]
out.update(status='ROOT_PASSAGE_GEOMETRY_COUNTEREXAMPLE' if out['collisions'] or out['unexpected_contacts'] or out['failures'] else 'ROOT_PASSAGE_STATIC_CAPTURE_CLEAR__THREAD_STRAIN_RELIEF_AND_RELEASE_OPEN',test_count=len(out['tests']),changed_bboxes={k:bb[k] for k in changed},retained_release_ids=sp['retained_release_ids'],inputs_unchanged=all(sha(A/q)==h for q,h in out['inputs'].items()),sources_unchanged=all(sha(p)==h for p,h in hashes.items()))
assert out['inputs_unchanged'] and out['sources_unchanged'];save();print(json.dumps({k:out[k] for k in ['status','state','test_count','bridge_cut_locality','collisions','unexpected_contacts','failures','capture_stops']}))

raise SystemExit(0 if out['status']=='ROOT_PASSAGE_STATIC_CAPTURE_CLEAR__THREAD_STRAIN_RELIEF_AND_RELEASE_OPEN' else 2)
