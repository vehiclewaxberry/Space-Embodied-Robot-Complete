"""R2 source-bound internal harness edge protection; OCP only, millimetres.

Uses the R1 canonical STEP map, never raw legacy transforms. No upstream writes.
"""
from pathlib import Path
import argparse, gc, hashlib, json, math, sys
import numpy as np
from OCP.STEPControl import STEPControl_Reader, STEPControl_Writer, STEPControl_AsIs
from OCP.IFSelect import IFSelect_RetDone
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.gp import gp_Trsf, gp_Pnt, gp_Dir, gp_Ax2, gp_Circ
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform, BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakeFace
from OCP.GC import GC_MakeArcOfCircle
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipe
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeBox
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID

D=Path(__file__).resolve().parents[1]
ROOT=D.parents[1]
R1=D.parent/'SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919'
MAP=R1/'inputs/NEUTRAL_SOURCE_MAP.json'
I=np.eye(4).tolist()

def read(p): return json.loads(Path(p).read_text(encoding='utf8'))
def write(p,d): Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
def sha(p): return hashlib.file_digest(Path(p).open('rb'),'sha256').hexdigest()
def load(p):
    r=STEPControl_Reader(); assert r.ReadFile(str(p))==IFSelect_RetDone
    assert r.TransferRoots()>0
    return r.OneShape()
def bounds(s):
    b=Bnd_Box(); BRepBndLib.Add_s(s,b,False)
    v=b.Get(); return [list(v[:3]),list(v[3:])]
def precise_bounds(s):
    b=Bnd_Box(); BRepBndLib.AddOptimal_s(s,b,False,False)
    v=b.Get(); return [list(v[:3]),list(v[3:])]
def volume(s):
    g=GProp_GProps(); BRepGProp.VolumeProperties_s(s,g)
    return abs(g.Mass())
def count(s):
    e=TopExp_Explorer(s,TopAbs_SOLID); n=0
    while e.More(): n+=1; e.Next()
    return n
def moved(s,T):
    t=gp_Trsf(); t.SetValues(*[float(T[i][j]) for i in range(3) for j in range(4)])
    return BRepBuilderAPI_Transform(s,t,True).Shape()
def cylinder(r,z0,z1,x=65.,y=-80.):
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x,y,z0),gp_Dir(0,0,1)),r,z1-z0).Shape()
def block(x0,y0,z0,x1,y1,z1): return BRepPrimAPI_MakeBox(gp_Pnt(x0,y0,z0),x1-x0,y1-y0,z1-z0).Shape()
def boolean(typ,a,b):
    op=typ(a,b); op.Build(); assert op.IsDone(),str(typ)
    s=op.Shape(); assert BRepCheck_Analyzer(s).IsValid(),str(typ)
    return s
def cut(a,b): return boolean(BRepAlgoAPI_Cut,a,b)
def union(a,b): return boolean(BRepAlgoAPI_Fuse,a,b)
def common(a,b): return boolean(BRepAlgoAPI_Common,a,b)
def distance(a,b):
    v=BRepExtrema_DistShapeShape(a,b); v.Perform(); assert v.IsDone()
    return v.Value()
def dump(s,p):
    w=STEPControl_Writer(); assert w.Transfer(s,STEPControl_AsIs)==IFSelect_RetDone
    assert w.Write(str(p))==IFSelect_RetDone
    t=load(p); assert count(t)==count(s) and BRepCheck_Analyzer(t).IsValid()
    assert abs(volume(t)-volume(s))<=max(1e-6,volume(s)*1e-7)
    return {'path':str(p),'sha256':sha(p),'volume_mm3':volume(t),'bounds_mm':precise_bounds(t),'solids':count(t)}
def rows():
    data=read(MAP); assert not data['blockers']
    return data,[dict(r,group=g['id']) for g in data['groups'] for r in g['rows']]
def inspect():
    data,rr=rows(); pathcache={}; out=[]
    # Conservative search box encloses passage, support candidates and insertion travel.
    low=np.array([-123.,-124.,100.]); high=np.array([90.,-57.,140.])
    cachepath=D/'inputs/SOURCE_LOCAL_BOUNDS.json'
    if cachepath.exists():
        cache=read(cachepath); assert cache['map_sha256']==sha(MAP),'Stale bounds cache'
        pathcache=cache['bounds_by_path']
    for n,r in enumerate(rr):
        p=r['step_path']; assert sha(p)==r['source_sha256']
        if p not in pathcache:
            s=load(p); pathcache[p]=bounds(s); del s
        lo,hi=map(np.array,pathcache[p]); T=np.array(r['T_S_local'])
        corners=np.array([[x,y,z] for x in [lo[0],hi[0]] for y in [lo[1],hi[1]] for z in [lo[2],hi[2]]])
        corners=corners@T[:3,:3].T+T[:3,3]; a,b=corners.min(0),corners.max(0)
        if np.all(a<=high)&np.all(b>=low):
            q=dict(r); q['conservative_S_bounds_mm']=[a.tolist(),b.tolist()]
            out.append(q)
        if n%100==0: print('broadphase',n,len(rr),flush=True); gc.collect()
    write(cachepath,{'map_sha256':sha(MAP),'bounds_by_path':pathcache})
    write(D/'inputs/PASSAGE_CONTEXT.json',{'schema':'R2_PASSAGE_CONTEXT_V1','R1_map_sha256':sha(MAP),'search_box_S_mm':[low.tolist(),high.tolist()],
        'method':'all map rows; exact local BRep bbox corners transformed once, conservative S AABB',
        'source_unique_parts':len(pathcache),'source_rows':len(rr),'rows':out,'state_groups':{k:v['groups'] for k,v in data['states'].items()}})
    unique={r['id']:r for r in out}
    for k,r in unique.items():
        print(k,r['conservative_S_bounds_mm'])
    for name in ('WP01-RB-BRIDGE-R2','WP01-MT-M3RB-REUSED'):
        r=unique[name]; s=moved(load(r['step_path']),r['T_S_local'])
        local=common(s,cylinder(9,98,136))
        print('LOCAL_HOST',name,bounds(local),volume(local))
    print('context rows',len(out),'unique IDs',len(unique),flush=True)

def route_shape(end_x,deep_y,radius=14.,z=118.):
    # Tangent-continuous U route. Endpoints are inherited FUNCTIONAL locations.
    cy=deep_y+radius
    pts=[(65.,-80.,z),(65.,cy,z),(65.-radius,deep_y,z),
         (end_x+radius,deep_y,z),(end_x,cy,z),(end_x,-80.,z)]
    wire=BRepBuilderAPI_MakeWire()
    def line(a,b): wire.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(*a),gp_Pnt(*b)).Edge())
    def arc(a,m,b):
        wire.Add(BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(gp_Pnt(*a),gp_Pnt(*m),gp_Pnt(*b)).Value()).Edge())
    line(pts[0],pts[1])
    k=radius/math.sqrt(2)
    arc(pts[1],(65.-radius+k,cy-k,z),pts[2])
    line(pts[2],pts[3])
    arc(pts[3],(end_x+radius-k,cy-k,z),pts[4])
    line(pts[4],pts[5]); assert wire.IsDone()
    profile=BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(*pts[0]),gp_Dir(0,-1,0)),2.)).Edge()).Wire()
    face=BRepBuilderAPI_MakeFace(profile).Face()
    pipe=BRepOffsetAPI_MakePipe(wire.Wire(),face); pipe.Build(); assert pipe.IsDone()
    s=pipe.Shape(); assert count(s)==1 and BRepCheck_Analyzer(s).IsValid()
    length=2*abs(cy+80)+(65.-end_x-2*radius)+math.pi*radius
    return s,{'frame':'S_mm','start':list(pts[0]),'end':list(pts[-1]),'tangent_points':pts,'arc_radius_mm':radius,
        'outer_diameter_mm':4.,'centerline_length_mm':length,'cut_length_mm':None,
        'current_actual_wire_spec':None,'endpoints_are_manufacturer_pins':False,
        'bend_radius_status':'NOMINAL_ROUTING_PARAMETER_NOT_CABLE_QUALIFICATION'}

def compact_route(end_x,radius=14.,z=118.,return_x=0.):
    # Exit the open -Y half of M3RB, pass its edge, return only after x<5.
    # Both logical branches intentionally retain a shared FUNCTIONAL corridor.
    r=radius; angle=math.pi/3; run=2*r*math.sin(angle)
    p=[(65.,-80.,z),(65.-r,-80.-r,z),(return_x,-80.-r,z),
       (return_x-r*math.sin(angle),-80.-r*math.cos(angle),z),
       (return_x-run,-80.,z),(end_x,-80.,z)]
    wire=BRepBuilderAPI_MakeWire()
    def line(a,b):
        if np.linalg.norm(np.array(a)-b)>1e-8: wire.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(*a),gp_Pnt(*b)).Edge())
    def arc(a,m,b): wire.Add(BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(gp_Pnt(*a),gp_Pnt(*m),gp_Pnt(*b)).Value()).Edge())
    arc(p[0],(65-r+r/math.sqrt(2),-80-r/math.sqrt(2),z),p[1]); line(p[1],p[2])
    arc(p[2],(return_x-r*math.sin(angle/2),-80-r*math.cos(angle/2),z),p[3])
    arc(p[3],(return_x-run+r*math.sin(angle/2),-80-r+r*math.cos(angle/2),z),p[4]); line(p[4],p[5])
    assert wire.IsDone()
    profile=BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(*p[0]),gp_Dir(0,-1,0)),2.)).Edge()).Wire()
    pipe=BRepOffsetAPI_MakePipe(wire.Wire(),BRepBuilderAPI_MakeFace(profile).Face()); pipe.Build(); assert pipe.IsDone()
    s=pipe.Shape(); assert count(s)==1 and BRepCheck_Analyzer(s).IsValid()
    length=r*(math.pi/2+2*angle)+(65-r-return_x)+(return_x-run-end_x)
    return s,{'frame':'S_mm','start':list(p[0]),'end':list(p[-1]),'tangent_points':p,'arc_radius_mm':r,
        'arc_angles_deg':[90.,60.,60.],'outer_diameter_mm':4.,'centerline_length_mm':length,'cut_length_mm':None,
        'current_actual_wire_spec':None,'endpoints_are_manufacturer_pins':False,
        'shared_corridor_status':'TWO_LOGICAL_BRANCHES_NOT_TWO_PHYSICALLY_SEPARATED_CABLES',
        'bend_radius_status':'NOMINAL_ROUTING_PARAMETER_NOT_CABLE_QUALIFICATION'}

class Path3D:
    def __init__(self,p,tangent):
        self.start=self.p=np.array(p,dtype=float); self.initial_tangent=tangent
        self.edges=[]; self.arcs=[]; self.length=0.; self.commands=[]
    def line(self,q):
        q=np.array(q,dtype=float); length=np.linalg.norm(q-self.p)
        if length>1e-8:
            self.edges.append(BRepBuilderAPI_MakeEdge(gp_Pnt(*self.p),gp_Pnt(*q)).Edge()); self.length+=length
            self.commands.append({'line_start':self.p.tolist(),'line_end':q.tolist(),'length_mm':float(length)})
        self.p=q
    def arc(self,center,normal,angle):
        center=np.array(center,dtype=float); n=np.array(normal,dtype=float); n/=np.linalg.norm(n); v=self.p-center
        def point(a): return center+v*math.cos(a)+np.cross(n,v)*math.sin(a)+n*np.dot(n,v)*(1-math.cos(a))
        end=point(angle); mid=point(angle/2)
        self.edges.append(BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(gp_Pnt(*self.p),gp_Pnt(*mid),gp_Pnt(*end)).Value()).Edge())
        radius=np.linalg.norm(v); self.length+=abs(angle)*radius
        row={'radius_mm':float(radius),'angle_rad':angle,'start':self.p.tolist(),'end':end.tolist(),'center':center.tolist(),'normal':n.tolist()}
        self.arcs.append(row); self.commands.append({'arc':row}); self.p=end
    def offset(self,u,v,delta,r=14.):
        u=np.array(u,dtype=float);u/=np.linalg.norm(u); v=np.array(v,dtype=float);v/=np.linalg.norm(v)
        assert abs(np.dot(u,v))<1e-10 and 0<delta<2*r
        theta=math.acos(1-delta/(2*r)); n=np.cross(u,v)
        self.arc(self.p+v*r,n,theta); tangent=u*math.cos(theta)+v*math.sin(theta)
        self.arc(self.p-np.cross(n,tangent)*r,n,-theta)
    def solid(self):
        w=BRepBuilderAPI_MakeWire()
        for e in self.edges:w.Add(e)
        assert w.IsDone()
        circle=gp_Circ(gp_Ax2(gp_Pnt(*self.start),gp_Dir(*self.initial_tangent)),2.)
        profile=BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(circle).Edge()).Wire()
        pipe=BRepOffsetAPI_MakePipe(w.Wire(),BRepBuilderAPI_MakeFace(profile).Face());pipe.Build();assert pipe.IsDone()
        s=pipe.Shape(); assert count(s)==1 and BRepCheck_Analyzer(s).IsValid()
        return s

def raised_compact_route(end_x):
    r=14.; dz=2.; dy=-math.sqrt(r*r-dz*dz)
    v=np.array([0.,dy/r,dz/r]); u=np.array([-1.,0,0])
    # First quarter-circle rises 2 mm and exits the open edge without crossing M3RB.
    path=Path3D([65,-80,118],v.tolist())
    path.arc([51,-80,118],np.cross(v,u),math.pi/2)
    path.line([49,path.p[1],120]); path.offset(u,[0,1,0],-87.75-path.p[1],r)
    path.line([0,-87.75,120]); path.offset(u,[0,1,0],7.75,r)
    path.offset(u,[0,0,-1],2.,r); path.line([end_x,-80,118])
    s=path.solid()
    return s,{'frame':'S_mm','start':path.start.tolist(),'end':path.p.tolist(),'commands':path.commands,'arcs':path.arcs,
        'outer_diameter_mm':4.,'arc_radius_mm':14.,'centerline_length_mm':float(path.length),'cut_length_mm':None,
        'current_actual_wire_spec':None,'endpoints_are_manufacturer_pins':False,
        'shared_corridor_status':'TWO_LOGICAL_BRANCHES_NOT_TWO_PHYSICALLY_SEPARATED_CABLES',
        'bend_radius_status':'NOMINAL_ROUTING_PARAMETER_NOT_CABLE_QUALIFICATION'}

def build():
    context=read(D/'inputs/PASSAGE_CONTEXT.json'); assert context['R1_map_sha256']==sha(MAP)
    unique={r['id']:r for r in context['rows']}
    targets=['release_power_data_route_0_0','release_power_data_route_1_0']
    shapes={}; routefacts=[]; source_checks=[]
    for name,x,y in [(targets[0],-115.,-116.),(targets[1],-40.,-104.)]:
        old=unique[name]; assert sha(old['step_path'])==old['source_sha256']
        s,param=raised_compact_route(x); dst=D/'cad'/(name+'_R2.step'); receipt=dump(s,dst)
        assert np.allclose(param['start'],[65,-80,118],rtol=0,atol=1e-8)
        assert np.allclose(param['end'],[x,-80,118],rtol=0,atol=1e-8)
        tangent_errors=[]; last_tangent=None
        for cmd in param['commands']:
            if 'arc' in cmd:
                c=cmd['arc'];n=np.array(c['normal']);sgn=1 if c['angle_rad']>0 else -1
                a=np.cross(n,np.array(c['start'])-c['center'])*sgn
                b=np.cross(n,np.array(c['end'])-c['center'])*sgn
            else:a=b=np.array(cmd['line_end'])-cmd['line_start']
            a/=np.linalg.norm(a);b/=np.linalg.norm(b)
            if last_tangent is not None:tangent_errors.append(float(np.linalg.norm(a-last_tangent)))
            last_tangent=b
        assert max(tangent_errors)<1e-8
        analytic=math.pi*2**2*param['centerline_length_mm']
        assert abs(volume(s)-analytic)<1e-5
        shapes[name]=s
        routefacts.append(dict(id=name,source=old,parameters=param,output=receipt,
            representation_role='FUNCTIONAL_ROUTE_ENVELOPE_NOT_MANUFACTURING_HARNESS',
            geometry_analytic_volume_error_mm3=abs(volume(s)-analytic),tangent_continuity_max_error=max(tangent_errors),
            material_assignment=None,material_reason='Composite wire construction and real length not frozen'))
    # Reuse exact current canonical shapes only within the conservative corridor.
    obstacles={}; obstacle_rows={}
    for r in context['rows']:
        signature=(r['id'],r['step_path'],json.dumps(r['T_S_local']))
        if signature in obstacles: continue
        assert sha(r['step_path'])==r['source_sha256']; source_checks.append({'path':r['step_path'],'sha256':r['source_sha256']})
        obstacles[signature]=moved(load(r['step_path']),r['T_S_local']);obstacle_rows[signature]=r
    comparisons=[]
    for name in targets:
        old=moved(load(unique[name]['step_path']),unique[name]['T_S_local']); new=shapes[name]
        for signature,shape in obstacles.items():
            obs=signature[0]; row=obstacle_rows[signature]
            if obs in targets: continue
            # Coarse rejection uses envelopes, expanded 1 mm for distance screen.
            a,b=map(np.array,bounds(new)); c,d=map(np.array,bounds(shape))
            if np.any(a>d+1.) or np.any(c>b+1.): continue
            physical=row['representation_role']=='PHYSICAL_GEOMETRY' or obs.startswith(('ROOT_','M5_'))
            active_states=[state for state,groups in context['state_groups'].items() if any(q['id']==obs and q['step_path']==row['step_path'] and q['T_S_local']==row['T_S_local'] and q['group'] in groups for q in context['rows'])]
            comparisons.append({'route':name,'obstacle':obs,'obstacle_role':row['representation_role'],'states':active_states,
                'source_sha256':row['source_sha256'],'T_S_local':row['T_S_local'],
                'physical_obstacle':physical,'old_common_mm3':volume(common(old,shape)),
                'new_common_mm3':volume(common(new,shape)),'new_distance_mm':distance(new,shape)})
            print('pair',name,obs,comparisons[-1]['new_common_mm3'],flush=True)
    joint=common(shapes[targets[0]],shapes[targets[1]])
    # Only explicitly bounded inherited FUNCTIONAL junctions are admissible.
    # Equal volume alone cannot establish that an intersection stayed in place.
    zones={targets[0]:{'WP10_INTERNAL_BATTERY_BYPASS':[60,-85,113,70,-75,123],
              'release_power_data_route_0_1':[-118,-83,115,-112,-77,121],
              'release_power_data_route_1_1':[-43,-83,115,-37,-77,121]},
           targets[1]:{'WP10_INTERNAL_BATTERY_BYPASS':[60,-85,113,70,-75,123],
              'release_power_data_route_1_1':[-43,-83,115,-37,-77,121]}}
    allowed={k:set() for k in targets}
    for x in comparisons:
        box=zones[x['route']].get(x['obstacle'])
        if box is not None:
            signature=next(k for k in obstacles if k[0]==x['obstacle'])
            overlap=common(shapes[x['route']],obstacles[signature])
            outside=volume(cut(overlap,block(*box)))
            x['functional_junction_zone_S_mm']=box
            x['intersection_outside_declared_zone_mm3']=outside
            if outside<=1e-5:allowed[x['route']].add(x['obstacle'])
    failures=[x for x in comparisons if x['new_common_mm3']>1e-5 and x['obstacle'] not in allowed[x['route']]]
    # Overlap at the inherited trunk/branch junction is reported, never accepted as a manufactured junction.
    report={'schema':'R2_RELEASE_ROUTE_STATIC_SCREEN_V1','R1_map_sha256':sha(MAP),'generator_sha256':sha(__file__),
        'status':'STATIC_CORRIDOR_CANDIDATE_NO_UNCLASSIFIED_INTERSECTION' if not failures else 'FAILED_CANDIDATE_COLLISIONS',
        'rows':routefacts,'pair_checks':comparisons,'unclassified_collisions':failures,
        'route_route_common_mm3':volume(joint),'route_route_common_bounds_mm':bounds(joint),
        'route_route_common_scope':'GENERATOR_MEMORY_ONLY; NEAR_COINCIDENT_STEP_BOOLEAN_MAY_BE_INVALID',
        'junction_design_status':'UNKNOWN_SHARED_FUNCTIONAL_NODE_NOT_PHYSICAL_TWO_CABLE_SPLICE',
        'declared_functional_terminal_overlaps':{k:sorted(v) for k,v in allowed.items()},
        'all_three_fixed_states_same_local_geometry':all(len({(r['step_path'],json.dumps(r['T_S_local'])) for r in context['rows'] if r['id']==k})==1 for k in unique),
        'full_motion_swept_volume_checked':False,'wire_manufacturing_release':False,'whole_harness_complete':False,
        'source_checks':source_checks,'R1_sources_unchanged':all(sha(x['path'])==x['sha256'] for x in source_checks)}
    report['state_screen']={state:{'local_source_rows':sum(r['group'] in groups for r in context['rows']),
        'pair_checks':sum(state in x['states'] for x in comparisons),
        'unclassified_collision_count':sum(state in x['states'] for x in failures)} for state,groups in context['state_groups'].items()}
    try:
        cold_joint=common(load(routefacts[0]['output']['path']),load(routefacts[1]['output']['path']))
        report['STEP_route_route_common_mm3']=volume(cold_joint)
        report['STEP_route_route_common_status']='VALID_BOOLEAN'
    except AssertionError:
        report['STEP_route_route_common_mm3']=None
        report['STEP_route_route_common_status']='UNKNOWN_INVALID_NEAR_COINCIDENT_BOOLEAN'
    write(D/'results/RELEASE_ROUTE_STATIC_CHECK.json',report)
    write(D/'inputs/INTERNAL_ROUTE_PARAMETERS.json',{'rows':[{k:x[k] for k in ['id','parameters','representation_role']} for x in routefacts],
        'scope':'Two fixed-endpoint functional release branch reroutes only; no physical wire or endpoint upgrade'})
    print(report['status'],len(failures),flush=True)

if __name__=='__main__':
    a=argparse.ArgumentParser(); a.add_argument('mode',choices=['inspect','build']); arg=a.parse_args()
    inspect() if arg.mode=='inspect' else build()
