"""Independent solid-pair collision confirmation; no R7/builder imports or writes."""
from pathlib import Path
import hashlib,itertools,json,math
import numpy as np
from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID
from OCP.gp import gp_Trsf,gp_Pnt
D=Path(__file__).resolve().parents[2];E=D.parent;ROOT=D.parents[1]
R1=E/'SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919';R2=E/'SERVICE_STAR_INTERNAL_HARNESS_ORBIT_R2_20260919';R3=E/'SERVICE_STAR_B601_INTERFACE_R3_20260920';R4=E/'SERVICE_STAR_INTERNAL_LAYOUT_R4_20260920';R7=E/'SERVICE_STAR_AUX_STOP_INSTALLATION_R7_20260921'
locks={};checks=[];raw={};cache={};shape_solids={};bb={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def lock(p):
 k=str(Path(p).resolve());h=sha(p);assert k not in locks or locks[k]==h;locks[k]=h;return h
def read(p):lock(p);return json.loads(Path(p).read_text(encoding='utf8'))
def ck(n,v,d=None):checks.append(dict(name=n,passed=bool(v),detail=d))
def solids(s):
 out=[];e=TopExp_Explorer(s,TopAbs_SOLID)
 while e.More():out.append(e.Current());e.Next()
 assert out,'No solids in collision operand';return out
def bounds(s):
 b=Bnd_Box();BRepBndLib.AddOptimal_s(s,b,False,False);v=b.Get();return np.array([v[:3],v[3:]])
def near(a,b,margin=.1):return bool(np.all(a[0]<=b[1]+margin) and np.all(b[0]<=a[1]+margin))
def shape(r):
 key=(r['step_path'],tuple(np.array(r['T_S_local']).flat))
 if key not in cache:
  p=r['step_path']
  if p not in raw:
   assert lock(p)==r['source_sha256'];q=STEPControl_Reader();assert q.ReadFile(p)==IFSelect_RetDone;assert q.TransferRoots()>0;raw[p]=q.OneShape();assert BRepCheck_Analyzer(raw[p]).IsValid()
  t=gp_Trsf();t.SetValues(*[float(r['T_S_local'][i][j]) for i in range(3) for j in range(4)]);cache[key]=BRepBuilderAPI_Transform(raw[p],t,True).Shape()
 return cache[key]
def rowbounds(r):
 key=(r['step_path'],tuple(np.array(r['T_S_local']).flat))
 if key not in bb:
  if r['step_path'] in oldbounds:
   lo,hi=oldbounds[r['step_path']];t=np.array(r['T_S_local']);p=np.array(list(itertools.product(*zip(lo,hi))))@t[:3,:3].T+t[:3,3];bb[key]=np.array([p.min(axis=0),p.max(axis=0)])
  else:bb[key]=bounds(shape(r))
 return bb[key]
def common_volume(a,b):
 q=BRepAlgoAPI_Common(a,b);q.Build();assert q.IsDone();s=q.Shape();assert BRepCheck_Analyzer(s).IsValid();v=GProp_GProps();error=BRepGProp.VolumeProperties_s(s,v,Eps=1e-9,OnlyClosed=True,SkipShared=False);return abs(v.Mass()),error
def solidwise(a,b):
 sa=solids(a);sb=solids(b);av=[bounds(x) for x in sa];bv=[bounds(x) for x in sb];total=0.;details=[]
 for i,x in enumerate(sa):
  assert BRepCheck_Analyzer(x).IsValid()
  for j,y in enumerate(sb):
   if not near(av[i],bv[j],.00001):continue
   assert BRepCheck_Analyzer(y).IsValid();v,e=common_volume(x,y);total+=v;details.append(dict(a_solid=i,b_solid=j,overlap_mm3=v,relative_integration_error=e))
 return total,details
lay=read(D/'inputs/INSTALLATION_LAYOUT.json');builder=read(D/'results/INCREMENT_STATIC_CHECK.json');prior=read(D/'results/reviewer/GEOMETRY_REVIEW.json');r7=read(R7/'results/R6H_SOLIDWISE_RECHECK.json')
for p in [R7/'tools/recheck_r6h.py',R7/'tools/solid_wise.py',R7/'tools/geometry.py']:lock(p)
ck('R7_layout_check_binding',r7['r6h_layout_sha256']==sha(D/'inputs/INSTALLATION_LAYOUT.json') and r7['r6h_check_sha256']==sha(D/'results/INCREMENT_STATIC_CHECK.json'))
ck('R7_historical_content',r7['status']=='PASS_R6H_HORIZONTAL_CONFIRMED_PER_SOLID' and r7['pairs_checked']==129 and r7['pairs_involving_affected_part']==12 and not r7['collisions'] and not r7['unknown'])
legacy=read(R1/'inputs/NEUTRAL_SOURCE_MAP.json');r2={r['id']:r for r in read(R2/'inputs/NATIVE_ROUTE_PLAN.json')['parts']};r3=read(R3/'inputs/NATIVE_ASSEMBLY_PLAN.json')['part'];mount=read(R4/'inputs/MOUNT_LAYOUT.json');passage=read(R4/'inputs/PASSAGE_LAYOUT.json');r4mods={r['id']:r for r in mount['replacements']+passage['replacements']}
ob=read(R2/'inputs/SOURCE_LOCAL_BOUNDS.json');ck('R2_bounds_lock',ob['map_sha256']==sha(R1/'inputs/NEUTRAL_SOURCE_MAP.json'));oldbounds=ob['bounds_by_path']
states={}
for st,ss in legacy['states'].items():
 rr=[r for g in legacy['groups'] if g['id'] in ss['groups'] for r in g['rows']];rr=[r2.get(r['id'],r3 if r['id']==r3['id'] else r) for r in rr];rr=[r4mods.get(r['id'],r) for r in rr]+mount['additions'];states[st]=rr;ck('host_count:'+st,len(rr)==1130)
mods={r['id']:r for r in lay['replacements']+lay['pose_changes']};delta=lay['parts']+lay['pose_changes'];new=lay['parts'];records=[];uniques={};collisions=[];unknown=[];counts=[]
def pair(a,b,st):
 key=tuple(sorted([(a['source_sha256'],tuple(np.array(a['T_S_local']).flat)),(b['source_sha256'],tuple(np.array(b['T_S_local']).flat))]))
 if key not in uniques:uniques[key]=solidwise(shape(a),shape(b))
 v,ds=uniques[key];r=dict(state=st,a=a['id'],b=b['id'],overlap_mm3=v,solid_pair_checks=len(ds),solid_details=ds);records.append(r)
 if v>1e-5:collisions.append(r)
for st,rr in states.items():
 host=[mods.get(r['id'],r) for r in rr];n=0
 for a in delta:
  for b in host:
   if a['id']==b['id'] or not near(rowbounds(a),rowbounds(b)):continue
   n+=1
   try:pair(a,b,st)
   except Exception as e:unknown.append(dict(state=st,a=a['id'],b=b['id'],error=str(e)))
 counts.append(dict(state=st,pairs=n));print('STATE',st,n,'collisions',len(collisions),'unknown',len(unknown),flush=True)
for a,b in itertools.combinations(new,2):
 if not near(rowbounds(a),rowbounds(b)):continue
 try:pair(a,b,'new_internal')
 except Exception as e:unknown.append(dict(state='new_internal',a=a['id'],b=b['id'],error=str(e)))
previous={(r['state'],r['a'],r['b']) for r in prior['pair_records']};current={(r['state'],r['a'],r['b']) for r in records}
ck('reproduces_165_pair_selection',previous==current and len(records)==165,dict(missing=sorted(previous-current),extra=sorted(current-previous)))
ck('70_unique_pairs',len(uniques)==70);ck('no_collisions_per_solid',not collisions,collisions);ck('no_unknowns',not unknown,unknown)
main=shape(next(r for r in new if r['id']=='R6H_MAIN_PCBA_INSTALLED'))
# Explicitly reproducible collision witness in the empty lower-left PCB area.
pin=BRepPrimAPI_MakeBox(gp_Pnt(-145,15,10),2,2,5).Shape();clear=BRepPrimAPI_MakeBox(gp_Pnt(-180,15,10),2,2,5).Shape()
whole,we=common_volume(main,pin);per,ds=solidwise(main,pin);safe,sd=solidwise(main,clear)
control=dict(collision_probe_box_S_mm=[[-145,15,10],[-143,17,15]],analytical_board_overlap_mm3=6.4,whole_compound_overlap_mm3=whole,per_solid_overlap_mm3=per,per_solid_details=ds,clear_probe_box_S_mm=[[-180,15,10],[-178,17,15]],clear_per_solid_overlap_mm3=safe)
ck('known_collision_probe_detected',abs(per-6.4)<1e-5,control);ck('clear_probe_zero',safe==0)
# R7's historical 70.4 mm3 probe has no coordinate record. Failure to reproduce
# its anecdote is not a safety failure and must not be required to prove this
# installation clear. Retain the first inappropriate assertion's failed receipt.
ck('whole_compound_known_probe_matches_physics',abs(whole-6.4)<1e-5,control)
for p,h in list(locks.items()):ck('source_preserved:'+p,sha(p)==h)
out=dict(schema='R6H_INDEPENDENT_SOLIDWISE_CONFIRMATION_V2',status='PASS_R6H_INCREMENT_CONFIRMED_SOLID_BY_SOLID' if all(x['passed'] for x in checks) else 'FAIL_SOLIDWISE_CONFIRMATION',checks=dict(passed=sum(x['passed'] for x in checks),total=len(checks),failed=[x for x in checks if not x['passed']]),checks_detail=checks,source_locks=locks,states=counts,pairs_checked=len(records),unique_pairs=len(uniques),pairs_involving_MAIN=sum('R6H_MAIN_PCBA_INSTALLED' in [x['a'],x['b']] for x in records),pair_records=records,collisions=collisions,unknown=unknown,negative_control=control,R7_assessment='Current R7 hashes match; its 129 pairs cover delta-versus-host only, 12 involving MAIN. Its 70.4 mm3 example is prose without recorded coordinates; a search of its nonbinary scripts/inputs/results found no reproducible probe definition. The historical false-zero example is NOT_REPRODUCED. Both methods detect this new 6.4 mm3 coordinate-defined probe. This independent replay covers the 165 original reviewer pairs including new-versus-new.',historical_false_zero_reproduced=False,first_attempt_preserved=dict(path='SOLIDWISE_ATTEMPT_01_FALSE_ZERO_NOT_REPRODUCED.json',sha256=sha(D/'results/reviewer/SOLIDWISE_ATTEMPT_01_FALSE_ZERO_NOT_REPRODUCED.json'),reason='Inappropriately required a whole-compound miss on an unrelated probe; revised acceptance uses known physical overlap and independent per-solid collision results, not replication of undocumented historical coordinates.'),scope='Three discrete states and bounded installation increment only; MAIN internal component self-overlaps, unchanged-host pairs, full continuous insertion/motion/plume, tolerances and strength are excluded. Per-solid sums are a collision predicate, not a deduplicated union-intersection volume for mass use.',supersedes_collision_credit_from=['results/INCREMENT_STATIC_CHECK.json whole-compound result alone','results/reviewer/GEOMETRY_REVIEW.json whole-compound collision predicate alone'],full_assembly_zero_interference=False,manufacturing_release=False,ready_to_power=False,flight_ready=False)
(D/'results/reviewer/SOLIDWISE_CONFIRMATION_REVIEW.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:out[k] for k in ['status','checks','pairs_checked','unique_pairs','pairs_involving_MAIN','negative_control']},ensure_ascii=False),flush=True)
raise SystemExit(0 if all(x['passed'] for x in checks) else 2)
