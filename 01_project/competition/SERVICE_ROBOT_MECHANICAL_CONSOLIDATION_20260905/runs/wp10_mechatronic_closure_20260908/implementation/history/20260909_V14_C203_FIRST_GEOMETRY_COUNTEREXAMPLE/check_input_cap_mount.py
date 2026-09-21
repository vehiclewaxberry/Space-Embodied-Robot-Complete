"""Serial, current-source delta checks. Never inherits an old whole-assembly PASS."""
from pathlib import Path
import json,hashlib,math,itertools,gc
import numpy as np
from OCP.STEPControl import STEPControl_Reader
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common,BRepAlgoAPI_Cut,BRepAlgoAPI_Fuse
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box
from OCP.gp import gp_Trsf,gp_Pnt,gp_Ax2,gp_Dir
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def dump(p,v):(A/p).write_text(json.dumps(v,indent=2),encoding='utf-8')
def transform(s,T):t=gp_Trsf();t.SetValues(*[float(T[i][j]) for i in range(3) for j in range(4)]);return BRepBuilderAPI_Transform(s,t,True).Shape()
def load(r):
 assert sha(r['step_path'])==r['source_sha256'];print('IMPORT '+r['id'],flush=True)
 q=STEPControl_Reader();assert int(q.ReadFile(r['step_path']))==1;q.TransferRoots();return transform(q.OneShape(),r['T_S_step'])
def op(cls,a,b):q=cls(a,b);q.Build();assert q.IsDone();return q.Shape()
def volume(s):q=GProp_GProps();BRepGProp.VolumeProperties_s(s,q);return float(q.Mass())
def bounds(s):b=Bnd_Box();BRepBndLib.AddOptimal_s(s,b);return list(b.Get())
def near(a,b,g=0):return all(a[i]<=b[i+3]+g+1e-7 and a[i+3]>=b[i]-g-1e-7 for i in range(3))
def exact(a,b):
 q=BRepExtrema_DistShapeShape(a,b);q.Perform();assert q.IsDone();d=float(q.Value());v=volume(op(BRepAlgoAPI_Common,a,b)) if d<1e-7 else 0
 assert math.isfinite(d) and math.isfinite(v);return dict(distance_mm=d,common_volume_mm3=v)
def cylinder(r,start,direction,L):return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(*start),gp_Dir(*direction)),r,L).Shape()
c=read('mechanical/INPUT_CAP_MOUNT_DESIGN.json');plan=read('mechanical/INPUT_CAP_MOUNT_INSTANCE_PLAN.json');old=read(c['parent_plan']);inv=read('mechanical/CURRENT_936_SOURCE_BOUNDS.json')
assert all(sha(A/p)==h for p,h in plan['inputs'].items()) and inv['source_plan_sha256']==sha(A/c['parent_plan'])
out=dict(schema='WP10_C203_INSTALLATION_DELTA_EXACT_V1',inputs={q:sha(A/q) for q in ['tools/check_input_cap_mount.py','mechanical/INPUT_CAP_MOUNT_DESIGN.json','mechanical/INPUT_CAP_MOUNT_INSTANCE_PLAN.json','mechanical/CURRENT_936_SOURCE_BOUNDS.json']},states={},source_plan_instances=965,whole_fit_verified=False,load_retention_qualified=False,thermal_environment_verified=False,physical_assembly_executed=False)
required=set();allowed=set()
def allow(a,b):allowed.add(tuple(sorted([a,b])))
def require(a,b):allow(a,b);required.add(tuple(sorted([a,b])))
require('C203_BODY','C203_PCB');require('C203_CARRIER','C203_PCB');require('C203_CARRIER','upper_equipment_deck_B')
for band in ['A','B']:
 require('C203_CARRIER','C203_LOWER_'+band);require('C203_LINER_'+band+'_TOP','C203_LINER_'+band+'_BOTTOM')
 for half,target in [('TOP','C203_CARRIER'),('BOTTOM','C203_LOWER_'+band)]:require('C203_LINER_'+band+'_'+half,target);require('C203_BODY','C203_LINER_'+band+'_'+half)
for i in range(4):
 for a,b in [(f'C203_DECK_SCREW_{i}','C203_CARRIER'),(f'C203_DECK_NUT_{i}',f'C203_DECK_WASHER_{i}'),(f'C203_DECK_WASHER_{i}','upper_equipment_deck_B'),(f'C203_CLAMP_SCREW_{i}','C203_LOWER_'+('A' if i<2 else 'B')),(f'C203_BOARD_SCREW_{i}','C203_PCB')]:require(a,b)
 for a,b in [(f'C203_DECK_SCREW_{i}',f'C203_DECK_NUT_{i}'),(f'C203_CLAMP_SCREW_{i}','C203_CARRIER'),(f'C203_BOARD_SCREW_{i}','C203_CARRIER')]:allow(a,b)
checks=[]
T=np.asarray(c['cap_local_to_S']);checks.append(dict(id='RIGHT_HANDED_FRAME',passed=bool(abs(np.linalg.det(T[:3,:3])-1)<1e-12)))
for p in c['pads']:
 s=(T@np.array([*p['local_xy_mm'],0,1]))[:3].tolist();checks.append(dict(id='POLARITY_'+p['number'],expected_S=p['S_face_mm'],actual_S=s,passed=s==p['S_face_mm']))
checks += [dict(id='BOARD_FLUSH',passed=c['board_x_mm'][0]==c['body_face_S_mm'][0]),dict(id='MIN_LEAD_PROJECTION_AFTER_BOARD',value_mm=c['OEM_lead_projection_mm'][0]-(c['board_x_mm'][1]-c['board_x_mm'][0]),passed=abs(c['OEM_lead_projection_mm'][0]-(c['board_x_mm'][1]-c['board_x_mm'][0])-1.9)<1e-12)]
out['interface_checks']=checks
# Per-state imports are cached only for this delta; old-old pairs are not recomputed.
for state,sp in plan['states'].items():
 rows={r['id']:r for r in sp['rows']};parents={r['id']:r for r in old['states'][state]['rows']};b0={r['id']:r for r in inv['states'][state]};bb={k:r['bbox_S_mm'] for k,r in b0.items()};cache={}
 assert all(b0[k]['source_sha256']==r['source_sha256'] and b0[k]['T_S_step']==r['T_S_step'] for k,r in parents.items())
 def shape(k):
  if k not in cache:cache[k]=load(rows[k])
  return cache[k]
 changed=sp['changed_ids']+sp['added_ids'];valid=[]
 for k in changed:
  s=shape(k);bb[k]=bounds(s);valid.append(dict(id=k,valid=bool(BRepCheck_Analyzer(s).IsValid()),volume_mm3=volume(s)))
 result=dict(tests=[],required_contacts=[],keepout_tests=[],tool_space_tests=[],new_geometry=valid,changed_bboxes={k:bb[k] for k in changed},unchanged_935_rows_identical=all(rows[k]==r for k,r in parents.items() if k!='upper_equipment_deck_B'))
 out['states'][state]=result
 holes=[cylinder(1.7,[x,y,-12],[0,0,1],4) for x,y in c['deck_holes_xy_mm']]
 tool=holes[0]
 for h in holes[1:]:tool=op(BRepAlgoAPI_Fuse,tool,h)
 deck='upper_equipment_deck_B';previous=load(parents[deck]);expected=op(BRepAlgoAPI_Common,previous,tool);removed=op(BRepAlgoAPI_Cut,previous,shape(deck))
 result['deck_cut_locality']=dict(removed_mm3=volume(removed),expected_mm3=volume(expected),added_mm3=volume(op(BRepAlgoAPI_Cut,shape(deck),previous)),outside_cut_mm3=volume(op(BRepAlgoAPI_Cut,removed,expected)),missing_cut_mm3=volume(op(BRepAlgoAPI_Cut,expected,removed)))
 seen=set()
 for k in changed:
  for j,r in rows.items():
   pair=tuple(sorted([k,j]))
   if k==j or pair in seen or r['is_ground_only']:continue
   seen.add(pair)
   if k==deck and j not in changed and not any(near(bb[j],bounds(h)) for h in holes):continue
   if not near(bb[k],bb[j]):continue
   q=exact(shape(k),shape(j));result['tests'].append(dict(ids=list(pair),**q,nominal_contact_allowed=pair in allowed))
 for pair in sorted(required):result['required_contacts'].append(dict(ids=list(pair),**exact(shape(pair[0]),shape(pair[1]))))
 # Max body is a reservation, liners explicitly excluded for the diameter variant.
 body=cylinder(15.5,[-7,0,-50],[-1,0,0],52);vent=cylinder(15.5,[-57,0,-50],[-1,0,0],5)
 lead=[cylinder(1,[-7,y,-50],[1,0,0],4.5) for y in [-5,5]]
 for name,s,exclude in [('MAX_BODY',body,{'C203_BODY'}|{k for k in rows if k.startswith('C203_LINER_')}),('VENT_LENGTH_VARIANT_SWEEP',vent,{'C203_BODY'}),('PLUS_LEAD_HOLE_ENVELOPE',lead[0],{'C203_BODY'}),('MINUS_LEAD_HOLE_ENVELOPE',lead[1],{'C203_BODY'})]:
  for k,r in rows.items():
   if k in exclude or r['is_ground_only'] or not near(bounds(s),bb[k]):continue
   q=exact(s,shape(k));result['keepout_tests'].append(dict(name=name,obstacle=k,**q))
 # Declared 5mm diameter straight driver allocation below mounting heads, no tool certification.
 for i,(x,y) in enumerate(c['deck_holes_xy_mm']):
  s=cylinder(2.5,[x,y,-43.5],[0,0,1],25)
  for k,r in rows.items():
   if k==f'C203_DECK_SCREW_{i}' or r['is_ground_only'] or not near(bounds(s),bb[k]):continue
   q=exact(s,shape(k));result['tool_space_tests'].append(dict(screw=i,obstacle=k,**q))
 result['collisions']=[r for r in result['tests'] if r['common_volume_mm3']>1e-6]
 result['unexpected_contacts']=[r for r in result['tests'] if r['distance_mm']<1e-7 and r['common_volume_mm3']<=1e-6 and not r['nominal_contact_allowed']]
 result['missing_contacts']=[r for r in result['required_contacts'] if r['distance_mm']>1e-7 or r['common_volume_mm3']>1e-6]
 result['keepout_collisions']=[r for r in result['keepout_tests'] if r['common_volume_mm3']>1e-6]
 result['tool_collisions']=[r for r in result['tool_space_tests'] if r['common_volume_mm3']>1e-6]
 result['passed']=all(r['valid'] and r['volume_mm3']>0 for r in valid) and not any(result[q] for q in ['collisions','unexpected_contacts','missing_contacts','keepout_collisions','tool_collisions']) and all(abs(result['deck_cut_locality'][q])<1e-6 for q in ['added_mm3','outside_cut_mm3','missing_cut_mm3'])
 dump('results/INPUT_CAP_MOUNT_EXACT.json',out);print(json.dumps(dict(state=state,passed=result['passed'],tests=len(result['tests']),collisions=result['collisions'],unexpected=result['unexpected_contacts'],missing=result['missing_contacts'],keepout_hits=result['keepout_collisions'],tool_hits=result['tool_collisions'])),flush=True)
 cache.clear();gc.collect()
out['passed']=all(s['passed'] for s in out['states'].values()) and all(c['passed'] for c in checks)
out['nominal_geometry_check_only']=True;dump('results/INPUT_CAP_MOUNT_EXACT.json',out)
assert out['passed'],'C203 installation delta check failed; keep result as counterexample and repair sources'
