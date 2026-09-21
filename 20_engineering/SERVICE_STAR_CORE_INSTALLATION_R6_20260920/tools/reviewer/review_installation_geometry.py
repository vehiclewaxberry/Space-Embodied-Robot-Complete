"""Independent R6 read-only STEP review; no builder geometry helpers imported."""
from pathlib import Path
import hashlib
import itertools
import json
import math
import numpy as np
from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID, TopAbs_FACE
from OCP.gp import gp_Trsf

D=Path(__file__).resolve().parents[2]
ROOT=D.parents[1]
E=D.parent
R1=E/'SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919'
R2=E/'SERVICE_STAR_INTERNAL_HARNESS_ORBIT_R2_20260919'
R3=E/'SERVICE_STAR_B601_INTERFACE_R3_20260920'
R4=E/'SERVICE_STAR_INTERNAL_LAYOUT_R4_20260920'
R5=E/'SERVICE_STAR_POWER_THERMAL_LAYOUT_R5_20260920'
R5E=E/'SERVICE_STAR_ELECTRICAL_UPDATE_R5E_20260920'
OUT=D/'results/reviewer'
checks=[]
locks={}
raw={}
world={}
bbox_cache={}


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def lock(p):
    p=Path(p).resolve()
    key=str(p.relative_to(ROOT)).replace('\\','/')
    current=sha(p)
    if key in locks: assert current==locks[key], 'Source changed during review: '+key
    locks[key]=current
    return current
def read(p):
    lock(p)
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def check(name, passed, details=None): checks.append(dict(name=name, passed=bool(passed), details=details))
def topo(s, kind):
    e=TopExp_Explorer(s,kind);out=[]
    while e.More(): out.append(e.Current());e.Next()
    return out
def vol(s):
    p=GProp_GProps();BRepGProp.VolumeProperties_s(s,p);return abs(p.Mass())
def area(s):
    p=GProp_GProps();BRepGProp.SurfaceProperties_s(s,p);return abs(p.Mass())
def bb(s):
    b=Bnd_Box();BRepBndLib.AddOptimal_s(s,b,False,False)
    a=b.Get();return np.array([a[:3],a[3:]])
def move(s,t):
    q=gp_Trsf();q.SetValues(*[float(t[i][j]) for i in range(3) for j in range(4)])
    return BRepBuilderAPI_Transform(s,q,True).Shape()
def shape(r):
    p=r['step_path'];t=np.array(r['T_S_local']);key=(p,tuple(t.flat))
    if key not in world:
        if p not in raw:
            assert lock(p)==r['source_sha256'], 'SHA mismatch '+r['id']
            reader=STEPControl_Reader();assert reader.ReadFile(p)==IFSelect_RetDone
            assert reader.TransferRoots()>0
            s=reader.OneShape();assert not s.IsNull()
            assert BRepCheck_Analyzer(s).IsValid(), 'Invalid source '+r['id']
            raw[p]=s
        world[key]=move(raw[p],t)
    return world[key]
def op(kind,a,b):
    o=kind(a,b);o.Build();assert o.IsDone(), 'OCP operation not done'
    s=o.Shape();assert BRepCheck_Analyzer(s).IsValid(), 'Invalid boolean'
    return s
def dist(a,b):
    o=BRepExtrema_DistShapeShape(a,b);o.Perform();assert o.IsDone()
    return o.Value()
def overlap_box(a,b,margin=0): return bool(np.all(a[0]<=b[1]+margin) and np.all(b[0]<=a[1]+margin))


layout=read(D/'inputs/INSTALLATION_LAYOUT.json')
coverage=read(D/'inputs/MAIN_GEOMETRY_COVERAGE.json')
pop=read(D/'inputs/MAIN_POPULATION_READBACK.json')
bridge=read(D/'inputs/INTERFACE_BRIDGE.json')
mainpose=read(D/'inputs/MAIN_INSTALL_POSE.json')
builder=read(D/'results/INCREMENT_STATIC_CHECK.json')
legacy=read(R1/'inputs/NEUTRAL_SOURCE_MAP.json')
r2mods={r['id']:r for r in read(R2/'inputs/NATIVE_ROUTE_PLAN.json')['parts']}
r3part=read(R3/'inputs/NATIVE_ASSEMBLY_PLAN.json')['part']
r4mount=read(R4/'inputs/MOUNT_LAYOUT.json')
r4pass=read(R4/'inputs/PASSAGE_LAYOUT.json')
r4native=read(R4/'inputs/NATIVE_ASSEMBLY_PLAN.json')
r4mods={r['id']:r for r in r4mount['replacements']+r4pass['replacements']}
old_bounds=read(R2/'inputs/SOURCE_LOCAL_BOUNDS.json')
check('Inherited_bounds_bound_to_R1_map',old_bounds['map_sha256']==sha(R1/'inputs/NEUTRAL_SOURCE_MAP.json'))
old_bounds=old_bounds['bounds_by_path']

states={}
for name,state in legacy['states'].items():
    rows=[dict(r,group=g['id']) for g in legacy['groups'] if g['id'] in state['groups'] for r in g['rows']]
    rows=[dict(r2mods.get(r['id'],r3part if r['id']==r3part['id'] else r),group=r['group']) for r in rows]
    group=next(r['group'] for r in rows if r['id']=='equipment_arm_drive')
    rows=[dict(r4mods.get(r['id'],r),group=r['group']) for r in rows]+[dict(r,group=group) for r in r4mount['additions']]
    states[name]=rows
    check('R4_count_'+name,len(rows)==1130)
service={r['id']:r for r in states['service']}
for row in r4native['expected_leaves']:
    r=service[row['id']]
    check('R4_native_identity:'+r['id'],Path(row['native_path']).resolve()==Path(r['native_path']).resolve() and np.max(np.abs(np.array(row['T_S_local'])-r['T_S_local']))<1e-10)


def bounds(r):
    key=(r['step_path'],tuple(np.array(r['T_S_local']).flat))
    if key not in bbox_cache:
        if r['step_path'] in old_bounds:
            lo,hi=old_bounds[r['step_path']];t=np.array(r['T_S_local'])
            pts=np.array(list(itertools.product(*zip(lo,hi))))
            pts=pts@t[:3,:3].T+t[:3,3]
            bbox_cache[key]=np.array([pts.min(axis=0),pts.max(axis=0)])
        else: bbox_cache[key]=bb(shape(r))
    return bbox_cache[key]


new=layout['parts'];replacements={r['id']:r for r in layout['replacements']};newmap={r['id']:r for r in new}
check('31_new_instances',len(new)==31)
check('2_cut_only_replacements',len(replacements)==2)
facts=[]
for row in new+list(replacements.values()):
    s=shape(row);n=len(topo(s,TopAbs_SOLID));v=vol(s)
    fact=dict(id=row['id'],solids=n,volume_mm3=v,S_bbox_mm=bb(s).tolist(),representation_role=row['representation_role'])
    facts.append(fact)
    check('solids:'+row['id'],n==row['expected_solids'])
    check('volume:'+row['id'],abs(v-row['expected_volume_mm3'])<=max(1e-5,v*1e-7))
    stored=np.array([row['expected_local_bbox_mm']['min_mm'],row['expected_local_bbox_mm']['max_mm']])
    check('bbox:'+row['id'],np.max(np.abs(bb(s)-stored))<1e-5)

yr=math.radians(10);xr=math.radians(-20)
rz=np.array([[math.cos(yr),-math.sin(yr),0],[math.sin(yr),math.cos(yr),0],[0,0,1]])
rx=np.array([[1,0,0],[0,math.cos(xr),-math.sin(xr)],[0,math.sin(xr),math.cos(xr)]])
t=np.array(mainpose['T_S_core'])
check('MAIN_Rz10_RxMinus20',np.max(np.abs(t[:3,:3]-rz@rx))<1e-12)
check('MAIN_base_center_S',np.max(np.abs((t@np.array([50,-40,0,1]))[:3]-[-114,44,19]))<1e-12)
local=shape(coverage['board']);installed=shape(newmap['R6_MAIN_PCBA_INSTALLED']);transformed=move(local,t)
expected_bodies=topo(transformed,TopAbs_SOLID);actual_bodies=topo(installed,TopAbs_SOLID)
unmatched=set(range(len(actual_bodies)));body_matches=[]
for i,s in enumerate(expected_bodies):
    bb_expected=bb(s);j=min(unmatched,key=lambda k:np.max(np.abs(bb(actual_bodies[k])-bb_expected)))
    a=actual_bodies[j];unmatched.remove(j)
    r=dict(expected_index=i,actual_index=j,bbox_error_mm=float(np.max(np.abs(bb(a)-bb_expected))),
           volume_difference_mm3=abs(vol(a)-vol(s)),face_count_equal=len(topo(a,TopAbs_FACE))==len(topo(s,TopAbs_FACE)))
    body_matches.append(r)
    check('MAIN_transformed_body_signature:'+str(i),r['bbox_error_mm']<1e-5 and r['volume_difference_mm3']<1e-4 and r['face_count_equal'])
print('PARTS_AND_POSE',len(facts),'body_matches',len(body_matches),flush=True)
fps={f['ref']:f for f in pop['footprints']}
audit=read(R5E/'results/reviewer/LOCKED_249_XML_BOARD_AUDIT.json')
check('MAIN35_identity_complete',set(r['ref'] for r in coverage['coverage'])==set(audit['boards']['MAIN']['xml_refs']))
check('MAIN_current_PCB_hash',lock(pop['source'])==audit['boards']['MAIN']['sha256']==layout['source_board_sha256'])
check('MAIN_four_declared_height_assumptions',set(coverage['height_assumption_refs'])=={'D201','D202','U201','U205'})
for row in coverage['coverage']:
    check('MPN_bound:'+row['ref'],row['MPN']==fps[row['ref']]['value'])
    if row['ref'] in coverage['height_assumption_refs']:
        check('height_unknown:'+row['ref'],row['manufacturer_max_height_mm'] is None and row['reserved_height_mm']==6)
for flag in ['STOP_installed','AUX_installed','electrical_connections_completed','propulsion_installation_frozen','ready_to_power','flight_ready']:
    check('scope_flag:'+flag,layout[flag] is False)

pair_cache={};pair_records=[];unknown=[];collisions=[]
state_stats=[]


def inspect_pair(a,b,state):
    key=tuple(sorted([(a['source_sha256'],tuple(np.array(a['T_S_local']).flat)),(b['source_sha256'],tuple(np.array(b['T_S_local']).flat))]))
    if key not in pair_cache:
        sa,sb=shape(a),shape(b)
        v=vol(op(BRepAlgoAPI_Common,sa,sb));gap=dist(sa,sb)
        pair_cache[key]=dict(volume_mm3=v,gap_mm=gap)
    record=dict(state=state,a=a['id'],b=b['id'],**pair_cache[key]);pair_records.append(record)
    if record['volume_mm3']>1e-5: collisions.append(record)


for name,rr in states.items():
    host=[replacements.get(r['id'],r) for r in rr];n=0
    for a in new:
        for b in host:
            if overlap_box(bounds(a),bounds(b),margin=1.0):
                n+=1
                try: inspect_pair(a,b,name)
                except Exception as e: unknown.append(dict(state=name,a=a['id'],b=b['id'],error=str(e)))
    state_stats.append(dict(state=name,host_rows=len(host),exact_pairs_with_1mm_broadphase=n))
    print('STATE',name,n,'collisions',len(collisions),'unknown',len(unknown),flush=True)
for a,b in itertools.combinations(new,2):
    if overlap_box(bounds(a),bounds(b),margin=1.0):
        try: inspect_pair(a,b,'new_internal')
        except Exception as e: unknown.append(dict(state='new_internal',a=a['id'],b=b['id'],error=str(e)))
check('independent_no_increment_collisions',not collisions,collisions)
check('independent_no_unknown_booleans',not unknown,unknown)

cut_facts=[]
for ident,row in replacements.items():
    before=shape(service[ident]);after=shape(row)
    extra=vol(op(BRepAlgoAPI_Cut,after,before));removed=vol(op(BRepAlgoAPI_Cut,before,after))
    cut_facts.append(dict(id=ident,added_mm3=extra,removed_mm3=removed))
    check('replacement_removes_only:'+ident,extra<1e-5 and removed>0)


def planar_contact_area(a,b):
    total=0
    for fa in topo(a,TopAbs_FACE):
        ba=bb(fa)
        for fb in topo(b,TopAbs_FACE):
            if overlap_box(ba,bb(fb),1e-6) and dist(fa,fb)<1e-7:
                total+=area(op(BRepAlgoAPI_Common,fa,fb))
    return total


contacts=[]
for aid,bid in [('R6_IF_THERMAL_BRIDGE','R6_IF_TOP_ISOLATION_PAD'),('R6_IF_THERMAL_BRIDGE','thermal_interface_arm_drive'),('R6_IF_TOP_ISOLATION_PAD','equipment_arm_drive'),('R6_MAIN_ANGLED_CARRIER','adapter_compute_communications')]:
    a=shape(newmap[aid]);b=shape(newmap.get(bid) or replacements.get(bid) or service[bid])
    contact=dict(a=aid,b=bid,distance_mm=dist(a,b),face_contact_area_mm2=planar_contact_area(a,b))
    contacts.append(contact);check('contact:'+aid+':'+bid,contact['distance_mm']<1e-6)
    if aid=='R6_IF_THERMAL_BRIDGE' or aid=='R6_IF_TOP_ISOLATION_PAD':check('contact_area880:'+bid,abs(contact['face_contact_area_mm2']-880)<1e-5)

pcb_support_gaps=[]
for n in range(1,5):
    gap=dist(installed,shape(newmap['R6_MAIN_PCB_WASHER_TOP_'+str(n)]))
    pcb_support_gaps.append(dict(corner=n,top_washer_to_STEP_board_gap_mm=gap))
    check('STEP_top_washer_gap_declared:'+str(n),abs(gap-.085)<1e-5)

carrier=shape(newmap['R6_MAIN_ANGLED_CARRIER']);carrier_solids=topo(carrier,TopAbs_SOLID)
carrier_supports=[]
for i,s in enumerate(carrier_solids,1):
    base=shape(replacements['adapter_compute_communications'])
    carrier_supports.append(dict(body=i,volume_mm3=vol(s),distance_to_host_mm=dist(s,base),face_contact_area_mm2=planar_contact_area(s,base)))
check('both_carrier_bodies_touch_host',len(carrier_supports)==2 and all(r['distance_to_host_mm']<1e-6 and r['face_contact_area_mm2']>0 for r in carrier_supports))

for key,expected in list(locks.items()):check('source_preserved:'+key,sha(ROOT/key)==expected)
result=dict(schema='R6_INDEPENDENT_GEOMETRY_REVIEW_V1',reviewer='/root/electrical_selection_review',
    status='PASS_WITH_DECLARED_ENGINEERING_HOLDS' if all(c['passed'] for c in checks) else 'FAIL_CHECKS',
    checks=dict(passed=sum(c['passed'] for c in checks),total=len(checks),failed=[c for c in checks if not c['passed']]),
    checks_detail=checks,source_locks=locks,parts=facts,states=state_stats,
    independent_method='Direct OCP STEP reader, shape validity, common/cut/distance and face-common area; all three R4 states rebuilt from R1/R2/R3/R4 JSON without importing builder geometry helpers. Broadphase uses independently transformed sealed bounds with +1 mm, then exact booleans. Existing unchanged-host overlaps and full motion are outside scope.',
    pairs_examined=len(pair_records),unique_exact_pairs=len(pair_cache),pair_records=pair_records,
    collisions=collisions,unknown=unknown,cut_only_modifications=cut_facts,contact_checks=contacts,
    MAIN_once_transformed_body_signature_checks=body_matches,MAIN_full_symmetric_difference_repeated=False,
    PCB_top_washer_gaps=pcb_support_gaps,carrier_independent_bodies=carrier_supports,
    open_findings=[
        dict(id='R6-R01',severity='CONCERN',finding='Carrier consists of two independently supported disconnected bodies, now explicitly quantity 2; drawing/strength/preload qualification remains open.'),
        dict(id='R6-R02',severity='CONCERN',finding='Third-corner previous zero-ligament issue mitigated by R4 mm local boss around R3 mm countersink opening, nominal radial ligament 1 mm. Fastener standard, pull-through, preload and tolerance remain unqualified.'),
        dict(id='R6-R03',severity='CONCERN',finding='Four top washers are separated from STEP board top by 0.085 mm. Current PCB stackup is 1.37 mm core + 2x0.105 mm copper + 2x0.01 mm mask = 1.6 mm; exported 1.51 mm body and 1.595 component datum are not a complete physical stackup.'),
        dict(id='R6-R04',severity='CONCERN',finding='Four 6 mm part-height reservations, catalogue body poses, missing lugs/wires/Q201 thermal clamp mean this is a mixed-geometry fit candidate, not verified whole-PCBA clearance.'),
        dict(id='R6-R05',severity='CONCERN',finding='Heat bridge geometric face contact is testable, while heat load, pad conductivity, dielectric withstand, preload and lateral retention remain unqualified.'),
    ],
    native_review_status='PENDING_FINAL_NATIVE_RECEIPT',manufacturing_release=False,ready_to_power=False,flight_ready=False)
(OUT/'INSTALLATION_GEOMETRY_REVIEW.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(status=result['status'],checks=result['checks'],pairs=result['pairs_examined'],unique=result['unique_exact_pairs'],contacts=contacts,carrier_supports=carrier_supports),ensure_ascii=False),flush=True)
raise SystemExit(0 if all(c['passed'] for c in checks) else 2)
