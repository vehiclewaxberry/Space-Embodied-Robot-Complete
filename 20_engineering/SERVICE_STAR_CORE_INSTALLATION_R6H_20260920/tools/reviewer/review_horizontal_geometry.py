"""Independent R6H STEP/source/connection audit. No builder helpers imported."""
from pathlib import Path
import hashlib,itertools,json,math
import numpy as np
from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common,BRepAlgoAPI_Cut
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepGProp import BRepGProp
from OCP.Bnd import Bnd_Box
from OCP.GProp import GProp_GProps
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID,TopAbs_FACE
from OCP.gp import gp_Trsf

D=Path(__file__).resolve().parents[2];ROOT=D.parents[1];E=D.parent
R1=E/'SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919';R2=E/'SERVICE_STAR_INTERNAL_HARNESS_ORBIT_R2_20260919'
R3=E/'SERVICE_STAR_B601_INTERFACE_R3_20260920';R4=E/'SERVICE_STAR_INTERNAL_LAYOUT_R4_20260920'
R6=E/'SERVICE_STAR_CORE_INSTALLATION_R6_20260920';R5E=E/'SERVICE_STAR_ELECTRICAL_UPDATE_R5E_20260920'
OUT=D/'results/reviewer';OUT.mkdir(parents=True,exist_ok=True)
locks={};checks=[];raw={};world={};bboxes={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def lock(p):
 p=Path(p);k=str(p.resolve().relative_to(ROOT)).replace('\\','/');h=sha(p)
 if k in locks:assert locks[k]==h,'Changed source: '+k
 locks[k]=h;return h
def read(p):lock(p);return json.loads(Path(p).read_text(encoding='utf8'))
def ck(n,v,d=None):checks.append(dict(name=n,passed=bool(v),detail=d))
def topo(s,kind):
 e=TopExp_Explorer(s,kind);out=[]
 while e.More():out.append(e.Current());e.Next()
 return out
def volume(s):
 g=GProp_GProps();BRepGProp.VolumeProperties_s(s,g);return abs(g.Mass())
def area(s):
 g=GProp_GProps();BRepGProp.SurfaceProperties_s(s,g);return abs(g.Mass())
def bbox(s):
 b=Bnd_Box();BRepBndLib.AddOptimal_s(s,b,False,False);v=b.Get();return np.array([v[:3],v[3:]])
def move(s,t):
 q=gp_Trsf();q.SetValues(*[float(t[i][j]) for i in range(3) for j in range(4)])
 return BRepBuilderAPI_Transform(s,q,True).Shape()
def shape(r):
 p=r['step_path'];t=np.array(r['T_S_local']);key=(p,tuple(t.flat))
 if key not in world:
  if p not in raw:
   assert lock(p)==r['source_sha256'];q=STEPControl_Reader();assert q.ReadFile(p)==IFSelect_RetDone;assert q.TransferRoots()>0
   raw[p]=q.OneShape();assert BRepCheck_Analyzer(raw[p]).IsValid()
  world[key]=move(raw[p],t)
 return world[key]
def boolean(kind,a,b):
 q=kind(a,b);q.Build();assert q.IsDone();s=q.Shape();assert BRepCheck_Analyzer(s).IsValid();return s
def dist(a,b):
 q=BRepExtrema_DistShapeShape(a,b);q.Perform();assert q.IsDone();return q.Value()
def near(a,b,margin=0):return bool(np.all(a[0]<=b[1]+margin) and np.all(b[0]<=a[1]+margin))

lay=read(D/'inputs/INSTALLATION_LAYOUT.json');cov=read(D/'inputs/MAIN_GEOMETRY_COVERAGE.json')
native=read(D/'inputs/NATIVE_ASSEMBLY_PLAN.json');builder=read(D/'results/INCREMENT_STATIC_CHECK.json')
legacy=read(R1/'inputs/NEUTRAL_SOURCE_MAP.json');r2mods={r['id']:r for r in read(R2/'inputs/NATIVE_ROUTE_PLAN.json')['parts']}
r3=read(R3/'inputs/NATIVE_ASSEMBLY_PLAN.json')['part'];mount=read(R4/'inputs/MOUNT_LAYOUT.json');passage=read(R4/'inputs/PASSAGE_LAYOUT.json')
r4mods={r['id']:r for r in mount['replacements']+passage['replacements']};r4native=read(R4/'inputs/NATIVE_ASSEMBLY_PLAN.json')
oldbounds=read(R2/'inputs/SOURCE_LOCAL_BOUNDS.json');ck('R2_bounds_source_lock',oldbounds['map_sha256']==sha(R1/'inputs/NEUTRAL_SOURCE_MAP.json'));oldbounds=oldbounds['bounds_by_path']
states={}
for name,s in legacy['states'].items():
 rows=[dict(r,group=g['id']) for g in legacy['groups'] if g['id'] in s['groups'] for r in g['rows']]
 rows=[dict(r2mods.get(r['id'],r3 if r['id']==r3['id'] else r),group=r['group']) for r in rows]
 armgroup=next(r['group'] for r in rows if r['id']=='equipment_arm_drive')
 rows=[dict(r4mods.get(r['id'],r),group=r['group']) for r in rows]+[dict(r,group=armgroup) for r in mount['additions']]
 states[name]=rows;ck('R4_count_'+name,len(rows)==1130)
old={r['id']:r for r in states['service']}
for r in r4native['expected_leaves']:
 a=old[r['id']];ck('R4_identity:'+r['id'],Path(a['native_path']).resolve()==Path(r['native_path']).resolve() and np.max(np.abs(np.array(a['T_S_local'])-r['T_S_local']))<1e-10)
new={r['id']:r for r in lay['parts']};repl={r['id']:r for r in lay['replacements']};poses={r['id']:r for r in lay['pose_changes']}
mods=dict(repl);mods.update(poses);cur=dict(old);cur.update(mods);cur.update(new)
ck('counts_23_4_6',len(new)==23 and len(repl)==4 and len(poses)==6)
ck('native_counts_1153_1602',native['expected_leaf_count']==1153 and native['expected_solid_instances']==1602)
ck('native_layout_lock',native['source_layout_sha256']==sha(D/'inputs/INSTALLATION_LAYOUT.json')==builder['source_layout_sha256'])
ck('native_R4_lock',native['source_R4_plan_sha256']==sha(R4/'inputs/NATIVE_ASSEMBLY_PLAN.json'))
ck('MAIN_horizontal_exact',lay['T_S_MAIN']==[[1.,0.,0.,-164.],[0.,1.,0.,86.],[0.,0.,1.,11.5],[0.,0.,0.,1.]] and lay['board_out_of_plane_tilt_deg']==0)
for k in ['exterior_changed','other_equipment_poses_changed','battery_and_propulsion_routes_changed','nut_clocking_required','STOP_installed','AUX_installed','electrical_connections_completed','ready_to_power','flight_ready']:
 ck('scope:'+k,lay[k] is False)
native_rows={r['id']:r for r in native['expected_leaves']}
ck('native_ID_set',set(native_rows)==set(cur))
for ident,r in cur.items():
 n=native_rows[ident];ck('native_plan_pose:'+ident,np.max(np.abs(np.array(n['T_S_local'])-r['T_S_local']))<1e-10 and Path(n['native_path']).resolve()==Path(r['native_path']).resolve())
for ident in old:
 if ident not in mods:
  r=native_rows[ident];a=old[ident]
  ck('unchanged_host:'+ident,r['source_sha256']==a['source_sha256'] and r['step_path']==a['step_path'] and np.max(np.abs(np.array(r['T_S_local'])-a['T_S_local']))<1e-12)
for r in native['source_native_files']:ck('old_native_SHA:'+r['path'],lock(r['path'])==r['sha256'])
print('IDENTITIES',len(checks),flush=True)

def rb(r):
 key=(r['step_path'],tuple(np.array(r['T_S_local']).flat))
 if key not in bboxes:
  if r['step_path'] in oldbounds:
   lo,hi=oldbounds[r['step_path']];t=np.array(r['T_S_local']);pts=np.array(list(itertools.product(*zip(lo,hi))))@t[:3,:3].T+t[:3,3]
   bboxes[key]=np.array([pts.min(axis=0),pts.max(axis=0)])
  else:bboxes[key]=bbox(shape(r))
 return bboxes[key]

facts=[]
for r in list(new.values())+list(mods.values()):
 s=shape(r);n=len(topo(s,TopAbs_SOLID));facts.append(dict(id=r['id'],solids=n,volume_mm3=volume(s),bbox_mm=bbox(s).tolist()))
 ck('solid_count:'+r['id'],n==r['expected_solids'])
 if 'expected_volume_mm3' in r:ck('volume:'+r['id'],abs(volume(s)-r['expected_volume_mm3'])<max(1e-5,volume(s)*1e-7))
print('PARTS',len(facts),flush=True)

# Prove board-only thickness change and unchanged other bodies with signatures.
oldcore=shape(cov['original_source_board']);newcore=shape(cov['board'])
oldsol=topo(oldcore,TopAbs_SOLID);newsol=topo(newcore,TopAbs_SOLID)
def boardindex(ss):return next(i for i,s in enumerate(ss) if np.max(np.abs(bbox(s)[1][:2]-[100,0]))<1e-5 and np.max(np.abs(bbox(s)[0][:2]-[0,-80]))<1e-5)
oi=boardindex(oldsol);ni=boardindex(newsol);newboard=newsol[ni]
ck('old_new_body_counts40',len(oldsol)==len(newsol)==40)
ck('board_stack_bounds',np.max(np.abs(bbox(newboard)-np.array([[0,-80,0],[100,0,1.6]])))<1e-5)
# GTransform converts circular trimmed faces to BSplines. Default fixed integration
# undercounts the transformed board by 3.6999213 mm3; do not relax the ratio limit.
# Independent diagnosis includes adaptive/GK convergence, empty two-way shape cuts,
# and rejected 1.51/1.61 mm negative controls, tied to the exact two input STEP hashes.
diag=read(OUT/'BOARD_INTEGRATION_DIAGNOSIS.json')
for k,h in diag['source_locks'].items():ck('board_diagnosis_source_lock:'+k,lock(k)==h)
ck('board_diagnosis_complete',diag['status']=='PASS_CAUSE_ESTABLISHED')
for direction,dv in diag['independent_scaled_shape_symmetric_difference'].items():
 ck('board_independent_scale_empty_cut:'+direction,dv['solids']==0 and dv['faces']==0 and dv['volume_mm3']==0)
for name,nc in diag['negative_controls'].items():ck('board_wrong_thickness_rejected:'+name,nc['rejected'] is True)
def adaptive_volume(s):
 g=GProp_GProps();err=BRepGProp.VolumeProperties_s(s,g,Eps=1e-9,OnlyClosed=True,SkipShared=False)
 return abs(g.Mass()),err
av,ae=adaptive_volume(oldsol[oi]);bv,be=adaptive_volume(newboard)
ck('board_volume_scaling_only',abs(bv/av-1.6/1.51)<1e-7,dict(method='adaptive Gauss Eps=1e-9 OnlyClosed=True',old_volume_mm3=av,new_volume_mm3=bv,old_estimated_relative_error=ae,new_estimated_relative_error=be,ratio_error=bv/av-1.6/1.51,ratio_tolerance_unchanged=1e-7))
for i,(a,b) in enumerate(zip(oldsol,newsol)):
 if i==oi:continue
 ck('unchanged_component_geometry:'+str(i),np.max(np.abs(bbox(a)-bbox(b)))<1e-5 and abs(volume(a)-volume(b))<1e-4 and len(topo(a,TopAbs_FACE))==len(topo(b,TopAbs_FACE)))
ck('no_bulk_PCB_material',cov['board']['bulk_PCB_material_assigned'] is False)
ck('four_assumed_heights_explicit',set(cov['height_assumption_refs'])=={'D201','D202','U201','U205'})
audit=read(R5E/'results/reviewer/LOCKED_249_XML_BOARD_AUDIT.json')
ck('35_reference_IDs',set(a['ref'] for a in cov['coverage'])==set(audit['boards']['MAIN']['xml_refs']))
ib=shape(new['R6H_MAIN_PCBA_INSTALLED']);expected=move(newcore,lay['T_S_MAIN'])
for i,(a,b) in enumerate(zip(topo(expected,TopAbs_SOLID),topo(ib,TopAbs_SOLID))):
 ck('installed_translation_signature:'+str(i),np.max(np.abs(bbox(a)-bbox(b)))<1e-5 and abs(volume(a)-volume(b))<1e-4)
print('BOARD_SIGNATURES',flush=True)

paircache={};pairs=[];collisions=[];unknown=[];stat=[]
def pair(a,b,st):
 key=tuple(sorted([(a['source_sha256'],tuple(np.array(a['T_S_local']).flat)),(b['source_sha256'],tuple(np.array(b['T_S_local']).flat))]))
 if key not in paircache:paircache[key]=volume(boolean(BRepAlgoAPI_Common,shape(a),shape(b)))
 out=dict(state=st,a=a['id'],b=b['id'],overlap_mm3=paircache[key]);pairs.append(out)
 if out['overlap_mm3']>1e-5:collisions.append(out)
delta=list(new.values())+list(poses.values())
for st,rows in states.items():
 host=[mods.get(r['id'],r) for r in rows];n=0
 for a in delta:
  for b in host:
   if a['id']==b['id'] or not near(rb(a),rb(b),.1):continue
   n+=1
   try:pair(a,b,st)
   except Exception as e:unknown.append(dict(state=st,a=a['id'],b=b['id'],error=str(e)))
 stat.append(dict(state=st,host_rows=len(host),exact_pairs=n));print('STATE',st,n,len(collisions),len(unknown),flush=True)
for a,b in itertools.combinations(new.values(),2):
 if near(rb(a),rb(b),.1):
  try:pair(a,b,'new_internal')
  except Exception as e:unknown.append(dict(state='new_internal',a=a['id'],b=b['id'],error=str(e)))
modfacts=[]
for ident,r in repl.items():
 if ident=='P60_HOST_2_ROD':
  dv=volume(shape(r))-volume(shape(old[ident]));ck('rod_extension3mm',abs(dv-math.pi*1.5**2*3)<1e-5);continue
 add=boolean(BRepAlgoAPI_Cut,shape(r),shape(old[ident]));remove=boolean(BRepAlgoAPI_Cut,shape(old[ident]),shape(r));av=volume(add);rv=volume(remove)
 modfacts.append(dict(id=ident,added_mm3=av,removed_mm3=rv))
 if ident=='P60_TRAY_B':
  ck('tray_added_bored_tab_only',abs(av-(120-math.pi*1.7**2))<1e-5)
  for st,rows in states.items():
   rr=[mods.get(q['id'],q) for q in rows]+list(new.values())
   for q in rr:
    if q['id']==ident or not near(bbox(add),rb(q),.1):continue
    try:
     v=volume(boolean(BRepAlgoAPI_Common,add,shape(q)))
     if v>1e-5:collisions.append(dict(state=st,a='P60_TRAY_ADDED_TAB',b=q['id'],overlap_mm3=v))
    except Exception as ex:unknown.append(dict(state=st,a='P60_TRAY_ADDED_TAB',b=q['id'],error=str(ex)))
 else:ck('cut_only:'+ident,av<1e-5)
ck('new_hole_volumes',abs(modfacts[0]['removed_mm3']-5*math.pi*1.7**2*3)<1e-4 and abs(modfacts[-1]['removed_mm3']-math.pi*1.7**2*3)<1e-4)
ck('no_increment_collisions',not collisions,collisions);ck('no_boolean_unknowns',not unknown,unknown)
print('BOOLEANS',len(pairs),len(paircache),flush=True)

# Contact surfaces are tested using horizontal faces only, avoiding unrelated curved component surfaces.
def horizontal_faces(s,z):
 return [f for f in topo(s,TopAbs_FACE) if abs(bbox(f)[0][2]-z)<1e-5 and abs(bbox(f)[1][2]-z)<1e-5]
def contact_area(a,b,z):return sum(area(boolean(BRepAlgoAPI_Common,fa,fb)) for fa in horizontal_faces(a,z) for fb in horizontal_faces(b,z) if near(bbox(fa),bbox(fb),1e-6))
connections=[]
contract=[('R6H_IF_THERMAL_BRIDGE','R6H_IF_TOP_ISOLATION_PAD',-2),('R6H_IF_THERMAL_BRIDGE','thermal_interface_arm_drive',-6),('R6H_IF_TOP_ISOLATION_PAD','equipment_arm_drive',-1.5)]
contract += [(f'R6H_MAIN_SPACER_{n}','upper_equipment_deck_B',-8.5) for n in range(1,5)]
contract += [(f'R6H_MAIN_SPACER_{n}','R6H_MAIN_PCBA_INSTALLED',11.5) for n in range(1,5)]
contract += [(f'R6H_MAIN_WASHER_TOP_{n}','R6H_MAIN_PCBA_INSTALLED',13.1) for n in range(1,5)]
contract += [('P60_HOST_2_POST','upper_equipment_deck_B',-8.5),('P60_HOST_2_POST','P60_TRAY_B',53),('P60_HOST_2_TW','P60_TRAY_B',55),('P60_HOST_2_TN','P60_HOST_2_TW',55.5),('P60_HOST_2_BW','upper_deck_angle_1_0',-14.5),('P60_HOST_2_BN','P60_HOST_2_BW',-15),('upper_equipment_deck_B','upper_deck_angle_1_0',-11.5)]
boardworld=move(newboard,lay['T_S_MAIN'])
for aid,bid,z in contract:
 a=shape(cur[aid]);b=boardworld if bid=='R6H_MAIN_PCBA_INSTALLED' else shape(cur[bid])
 gap=dist(a,b);ar=contact_area(a,b,z);connections.append(dict(a=aid,b=bid,z_mm=z,gap_mm=gap,area_mm2=ar));ck('bearing_contact:'+aid+':'+bid,gap<1e-6 and ar>1e-6)
clear=[]
for aid,bid,expected_gap in [('P60_HOST_2_TN','P60_REFERENCE_B',4.25),('R6H_MAIN_SPACER_1','adapter_compute_communications',.5),('R6H_MAIN_PCBA_INSTALLED','P60_HOST_2_POST',2)]:
 v=dist(shape(cur[aid]),shape(cur[bid]));clear.append(dict(a=aid,b=bid,distance_mm=v));ck('declared_clearance:'+aid,abs(v-expected_gap)<1e-5)
for k,h in list(locks.items()):ck('read_only_preservation:'+k,sha(ROOT/k)==h)
result=dict(schema='R6H_INDEPENDENT_GEOMETRY_REVIEW_V2',status='PASS_WITH_DECLARED_ENGINEERING_HOLDS' if all(r['passed'] for r in checks) else 'FAIL_CHECKS',
 checks=dict(passed=sum(r['passed'] for r in checks),total=len(checks),failed=[r for r in checks if not r['passed']]),checks_detail=checks,
 source_locks=locks,method='Independent direct OCP STEP read, validity/common/cut/distance/horizontal-face area; R4 states independently reconstructed. +0.1mm broadphase. Unchanged-host overlaps, continuous insertion/full-motion and manufacturing strength/tolerances not qualified.',
 states=stat,parts=facts,exact_pairs=len(pairs),unique_exact_pairs=len(paircache),pair_records=pairs,collisions=collisions,unknown=unknown,
 modification_checks=modfacts,contact_checks=connections,critical_clearances=clear,
 resolved=['Horizontal pose and original adapter retention','0.085mm previous washer gap replaced by nominal 1.60mm stack envelope','P60 support has upper tray ear and lower frame-flange bearing; rod length adjusted'],
 observations=['Four component heights remain assumed 6mm; body poses, ring lugs, wiring and Q201 heat path not qualified','Total PCB stack is a mechanical envelope, not individual Cu/FR4/mask material geometry; some legacy model base planes are 1.595mm and can embed 0.005mm into the synthetic stack','0.5mm nearest spacer-adapter clearance requires tolerance confirmation','New tray ear/frame bore/support load distribution and fastener grades/preload/tool access require mechanical validation','Thermal bridge has nominal face contact but pad MPN/conductivity/dielectric/preload and retention are unknown'],
 supersedes_failed_attempt='GEOMETRY_REVIEW_ATTEMPT_01_FAILED_DEFAULT_VOLUME.json',board_integration_diagnosis_sha256=sha(OUT/'BOARD_INTEGRATION_DIAGNOSIS.json'),
 native_review_pending=True,manufacturing_release=False,ready_to_power=False,flight_ready=False)
(OUT/'GEOMETRY_REVIEW.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(dict(status=result['status'],checks=result['checks'],contacts=connections,clearances=clear),ensure_ascii=False),flush=True)
raise SystemExit(0 if all(r['passed'] for r in checks) else 2)
