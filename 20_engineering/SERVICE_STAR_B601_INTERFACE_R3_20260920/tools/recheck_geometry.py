"""Fresh R3 region audit against final R2+R3 source assemblies; no sealed output overwritten."""
from pathlib import Path
import json,hashlib,numpy as np
from OCP.STEPControl import STEPControl_Reader
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.gp import gp_Trsf
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box

D=Path(__file__).resolve().parents[1]; R1=D.parent/'SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919'; R2=D.parent/'SERVICE_STAR_INTERNAL_HARNESS_ORBIT_R2_20260919'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):
    r=STEPControl_Reader();assert r.ReadFile(str(p))==1;assert r.TransferRoots()>0;return r.OneShape()
def volume(s):
    g=GProp_GProps();BRepGProp.VolumeProperties_s(s,g);return g.Mass()
def moved(s,T):
    t=gp_Trsf();t.SetValues(*[float(T[i][j]) for i in range(3) for j in range(4)])
    return BRepBuilderAPI_Transform(s,t,True).Shape()
def world_bounds(row):
    if row['step_path'] in bounds: lo,hi=map(np.array,bounds[row['step_path']])
    elif 'expected_local_bbox_mm' in row:
        box=row['expected_local_bbox_mm'];lo=np.array(box['min_mm']);hi=np.array(box['max_mm'])
    else:
        path=row['step_path'];assert sha(path)==row['source_sha256']
        raw_cache[path]=load(path);bb=Bnd_Box();BRepBndLib.AddOptimal_s(raw_cache[path],bb,False,False)
        a=bb.Get();lo=np.array(a[:3]);hi=np.array(a[3:]);bounds[path]=[lo.tolist(),hi.tolist()]
    T=np.array(row['T_S_local']);v=np.array([[x,y,z] for x in [lo[0],hi[0]] for y in [lo[1],hi[1]] for z in [lo[2],hi[2]]])
    v=v@T[:3,:3].T+T[:3,3];return v.min(0),v.max(0)

rp=D/'results/GEOMETRY_ASSEMBLY_RECHECK_V2.json';assert not rp.exists()
plan=read(D/'inputs/NATIVE_ASSEMBLY_PLAN.json'); m=read(R1/'inputs/NEUTRAL_SOURCE_MAP.json')
bound_record=read(R2/'inputs/SOURCE_LOCAL_BOUNDS.json')
assert bound_record['map_sha256']==sha(R1/'inputs/NEUTRAL_SOURCE_MAP.json')
bounds=bound_record['bounds_by_path']; prior=read(D/'results/RESERVATION_STATIC_CHECK.json')
part=plan['part'];assert sha(part['step_path'])==part['source_sha256']==prior['STEP_roundtrip']['sha256']
shape=load(part['step_path']);assert BRepCheck_Analyzer(shape).IsValid()
ex=TopExp_Explorer(shape,TopAbs_SOLID);solids=[]
while ex.More():solids.append(ex.Current());ex.Next()
assert len(solids)==8
changes={x['id']:x for x in read(R2/'inputs/NATIVE_ROUTE_PLAN.json')['parts']}
slot=read(D/'inputs/BOARD_RESERVATION.json');lo_slot=np.array(slot['reserved_box_min']);hi_slot=np.array(slot['reserved_box_max'])
result={'status':'RUNNING','scope':'R3 reservation versus surrounding geometry in three fixed poses, canonical source/transform binding verified against final native service plan, with current R2 route replacements; NOT all-pairs full-spacecraft collision certification',
        'source_plan_sha256':sha(D/'inputs/NATIVE_ASSEMBLY_PLAN.json'),
        'STEP_sha256':sha(part['step_path']),'geometry_tolerance_mm3':1e-6,
        'states':[], 'collisions':[], 'nominal_proximities_service':[], 'coordinate_artifact_recheck':[],
        'whole_assembly_interference_free':None,'dynamic_clearance_verified':False,
        'mounting_hardware_verified':False,'manufacturing_clearance_requirement_mm':None}
cache={};raw_cache={};paths={};exact=0;screened=0
for state,st in m['states'].items():
    rows=[row for g in m['groups'] if g['id'] in st['groups'] for row in g['rows']]
    rows=[changes.get(r['id'],r) for r in rows]
    if state=='service':
        canonical={r['id']:r for r in rows}
        matched=[]
        for expected in plan['expected_leaves']:
            if expected['id']==part['id']: matched.append(part);continue
            actual=canonical[expected['id']]
            assert Path(actual['native_path']).resolve()==Path(expected['native_path']).resolve()
            assert np.max(np.abs(np.array(actual['T_S_local'])-np.array(expected['T_S_local'])))<1e-10
            matched.append(actual)
        rows=matched
    rows=[dict(r,step_path=r['source_step']['path'],source_sha256=r['source_step']['sha256']) if 'step_path' not in r else r for r in rows]
    checked=0
    for row in rows:
        if row['id']==part['id']:continue
        screened+=1;lo,hi=world_bounds(row)
        artifact_probe=state=='service' and row['id'] in ('P60_HOST_1_POST','P60_HOST_1_ROD')
        if (np.any(lo>hi_slot+5) or np.any(hi<lo_slot-5)) and not artifact_probe:continue
        path=row['step_path'];T=np.array(row['T_S_local']);key=(path,tuple(T.flat))
        if key not in cache:
            assert sha(path)==row['source_sha256'];paths[path]=row['source_sha256']
            cache[key]=moved(raw_cache[path] if path in raw_cache else load(path),T)
        old=cache[key]
        if artifact_probe:
            common=BRepAlgoAPI_Common(shape,old);common.Build();assert common.IsDone()
            v=volume(common.Shape());dist=BRepExtrema_DistShapeShape(shape,old);dist.Perform();assert dist.IsDone()
            result['coordinate_artifact_recheck'].append({'id':row['id'],'canonical_step':path,
                'source_sha256':row['source_sha256'],'world_bounds_mm':[lo.tolist(),hi.tolist()],
                'exact_common_volume_mm3':v,'nominal_distance_mm':dist.Value()})
            assert v<=1e-6
        for solid,facts in zip(solids,prior['parts']):
            a,z=map(np.array,facts['bounds_mm'])
            if np.any(lo>=z) or np.any(hi<=a):continue
            common=BRepAlgoAPI_Common(solid,old);common.Build()
            assert common.IsDone() and BRepCheck_Analyzer(common.Shape()).IsValid()
            v=volume(common.Shape());exact+=1;checked+=1
            if v>1e-6:result['collisions'].append({'state':state,'R3_solid':facts['label'],'old_id':row['id'],'volume_mm3':v})
        if state=='service':
            dist=BRepExtrema_DistShapeShape(shape,old);dist.Perform();assert dist.IsDone()
            result['nominal_proximities_service'].append({'old_id':row['id'],'nominal_distance_mm':dist.Value(),
                'classification':'CONTACT_OR_TANGENCY' if dist.Value()<1e-6 else 'NOMINAL_ONLY_NO_TOLERANCE_CREDIT'})
    result['states'].append({'state':state,'leaf_rows':len(rows),'exact_intersections':checked})
result.update(status='PASS_R3_REGION_STATIC_RECHECK' if not result['collisions'] else 'FAIL_R3_REGION_INTERFERENCE',
              surrounding_instances_screened=screened,exact_intersections=exact,
              geometry_sources_read=paths,source_hashes_verified=True,
              current_R2_route_replacements_included=list(changes),
              final_service_native_source_and_transform_bindings_verified=True,
              previous_recheck_disposition={'path':str(D/'results/GEOMETRY_ASSEMBLY_RECHECK.json'),
                  'sha256':sha(D/'results/GEOMETRY_ASSEMBLY_RECHECK.json'),
                  'status':'INVALID_COORDINATE_PAIRING_DIAGNOSTIC_ONLY',
                  'reason':'Historical world-coordinate STEP paired with canonical-local-to-S transform; two reported penetrations were computational artifacts. No design geometry modified.'},
              no_new_external_penetrations=not result['collisions'])
result['nominal_proximities_service'].sort(key=lambda x:x['nominal_distance_mm'])
rp.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ('geometry_sources_read','nominal_proximities_service')},ensure_ascii=False,indent=2))
