"""Exact new-wire checks against current-state old-part bounding-box candidates."""
from pathlib import Path
import json,hashlib,sys,math
from chb_input_ocp import *
A=Path(__file__).resolve().parents[1];sys.path.insert(0,str(A/'mechanical'))
from cap_harness_path import fillet_path,slice_path
from prepare_cap_harness_plan_v19 import validate_plan,CHANGED
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads((A/p).read_text())
p=read('mechanical/CAP_HARNESS_INSTANCE_PLAN_V19.json');old=read(p['parent_plan']);c=read('power/CAP_HARNESS_DEFINITION_V19.json');path_result=read('results/CAP_HARNESS_PATH_V19.json')
assert not p.get('surface_profile_pending',False), 'Regenerate and bind current PCB/wires; old STEP is not current profile evidence'
assert all(not r.get('geometry_regeneration_required',False) for st in p['states'].values() for r in st['rows'])
validate_plan(p)
cache=read('mechanical/CURRENT_936_SOURCE_BOUNDS.json');cap=read('results/INPUT_CAP_MOUNT_EXACT.json');chb=read('results/CHB_INPUT_MECHANICAL_V18.json')
assert p['parent_plan_sha256']==sha(A/p['parent_plan']) and p['component_count']==972
assert all(sha(A/f)==h for f,h in path_result['inputs'].items())
assert chb['inputs']['mechanical/CHB_INPUT_INSTANCE_PLAN.json']==sha(A/p['parent_plan'])
assert cap['inputs']['mechanical/INPUT_CAP_MOUNT_INSTANCE_PLAN.json']==sha(A/'mechanical/INPUT_CAP_MOUNT_INSTANCE_PLAN.json')
inputs=['mechanical/CAP_HARNESS_INSTANCE_PLAN_V19.json',p['parent_plan'],'power/CAP_HARNESS_DEFINITION_V19.json','results/CAP_HARNESS_PATH_V19.json','mechanical/CURRENT_936_SOURCE_BOUNDS.json','results/INPUT_CAP_MOUNT_EXACT.json','results/CHB_INPUT_MECHANICAL_V18.json','mechanical/cap_harness_common.py','tools/check_cap_harness_exact_v19.py','tools/chb_input_ocp.py','mechanical/C203_SURFACE_PROFILE_V19.json','tools/prepare_cap_harness_plan_v19.py','tools/c203_surface_generation_contract_v19.py']
out=dict(schema='WP10_C203_WIRES_EXACT_V19',states={},inputs={f:sha(A/f) for f in inputs},whole_fit_verified=False,strain_relief_complete=False,physical_termination_qualified=False,continuous_motion_checked=False,physical_assembly_executed=False)
raw={}
def shape(r):
 f=Path(r['step_path']);h=r['source_sha256'];assert sha(f)==h
 if h not in raw:raw[h]=load(f)
 return transform(raw[h],r['T_S_step'])
for state,sp in p['states'].items():
 rows={r['id']:r for r in sp['rows']};prior={r['id']:r for r in old['states'][state]['rows']};added=sp['added_ids']
 assert len(rows)==972 and set(rows)-set(prior)==set(added) and all(rows[k]==v for k,v in prior.items() if k not in CHANGED)
 # Bind broad-phase cached transforms and every eight-corner bound to current
 # parent rows; an outdated placement must never hide a collision candidate.
 overrides=set(cap['states'][state]['changed_bboxes'])|set(chb['states'][state]['new_bboxes'])
 for cached in cache['states'][state]:
  k=cached['id']
  if k in overrides:continue
  r=prior[k]
  assert all(cached[f]==r[f] for f in ['source_sha256','T_S_step','is_ground_only']), 'Stale cache identity: '+k
  local=cache['raw_bounds_by_sha256'][r['source_sha256']];T=r['T_S_step']
  corners=[[sum(T[i][j]*v[j] for j in range(3))+T[i][3] for i in range(3)] for v in __import__('itertools').product(*[(local[i],local[i+3]) for i in range(3)])]
  expected=[min(q[i] for q in corners) for i in range(3)]+[max(q[i] for q in corners) for i in range(3)]
  assert max(abs(x-y) for x,y in zip(expected,cached['bbox_S_mm']))<1e-8,'Stale cache bounds: '+k
 bb={r['id']:r['bbox_S_mm'] for r in cache['states'][state]};bb.update(cap['states'][state]['changed_bboxes']);bb.update(chb['states'][state]['new_bboxes'])
 assert set(prior)<=set(bb),set(prior)-set(bb)
 geoms={}
 def get(k):
  if k not in geoms:geoms[k]=shape(rows[k])
  return geoms[k]
 for k in CHANGED:bb[k]=bounds(get(k))
 valid=[]
 for k in added:
  s=get(k);bb[k]=bounds(s);w=next(w for w in path_result['wires'] if w['id']==k);d=c['wire']
  expected=math.pi/4*(d['max_bare_D_mm']**2*w['analytic_cut_length_mm']+(d['max_insulation_D_mm']**2-d['max_bare_D_mm']**2)*w['insulated_length_mm'])
  valid.append(dict(id=k,valid=bool(BRepCheck_Analyzer(s).IsValid()),volume_mm3=vol(s),expected_envelope_volume_mm3=expected,volume_error_mm3=abs(vol(s)-expected),passed=bool(BRepCheck_Analyzer(s).IsValid()) and abs(vol(s)-expected)<.001,bbox=bb[k]))
 pairs=[];seen=set();screened=0
 allowed={tuple(sorted(['C203_PCB',other])) for other in ['C203_BODY','C203_CARRIER']+[f'C203_BOARD_SCREW_{i}' for i in range(4)]}
 allowed.update(tuple(sorted(['C203_CARRIER',f'C203_BOARD_SCREW_{i}'])) for i in range(4))
 for k in added+CHANGED:
  for j,r in rows.items():
   pair=tuple(sorted([k,j]))
   if k==j or pair in seen or r['is_ground_only']:continue
   seen.add(pair);screened+=1
   if not near(bb[k],bb[j],.3):continue
   q=exact(get(k),get(j));q.update(ids=list(pair),intended_nominal_contact=pair in allowed,passed=q['common_volume_mm3']<1e-6 and (pair in allowed or q['distance_mm']>1e-6));pairs.append(q)
 interfaces=[]
 for k in added:
  for board in ['C203_PCB','CHB_INPUT_PCB']:
   q=exact(get(k),get(board));interfaces.append(dict(ids=[k,board],**q,passed=q['common_volume_mm3']<1e-6 and q['distance_mm']>.1))
  q=exact(get(k),get('U202_CHB'));interfaces.append(dict(ids=[k,'U202_CHB'],**q,passed=q['common_volume_mm3']<1e-6 and q['distance_mm']>.3))
 # Adversarial translation offsets wire from the actual C203 drilled hole.
 T=[[1,0,0,0],[0,1,0,1],[0,0,1,0],[0,0,0,1]]
 shifted=transform(get('C203_W_PLUS'),T);bad=exact(shifted,get('C203_PCB'))
 fault=dict(name='wire_translated_1mm_into_actual_C203_hole_wall',**bad,rejected=bad['common_volume_mm3']>1e-5)
 sep=exact(get('C203_W_PLUS'),get('C203_W_MINUS'))
 contacts=[]
 def contact(name,a,b):
  q=exact(a,b);contacts.append(dict(name=name,**q,passed=q['distance_mm']<1e-6 and q['common_volume_mm3']<1e-6))
 contact('nominal_CAP_end_face_to_PCB',get('C203_BODY'),get('C203_PCB'))
 profile=read('mechanical/C203_SURFACE_PROFILE_V19.json')
 for i,(y,z) in enumerate(profile['mount_holes_yz_mm']):
  contact(f'head{i}_to_PCB',get(f'C203_BOARD_SCREW_{i}'),get('C203_PCB'))
  ring=op(BRepAlgoAPI_Cut,cyl(2.75,[-7.01,y,z],[1,0,0],.02),cyl(1.8,[-7.02,y,z],[1,0,0],.04))
  seat=op(BRepAlgoAPI_Common,get('C203_PCB'),ring);support=op(BRepAlgoAPI_Common,get('C203_CARRIER'),ring)
  assert vol(seat)>1e-6 and vol(support)>1e-6
  contact(f'local_support_ring{i}_to_PCB',seat,support)
 old_head_T=[[1,0,0,.14],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
 old_head=exact(transform(get('C203_BOARD_SCREW_0'),old_head_T),get('C203_PCB'))
 displaced_PCB=exact(transform(get('C203_PCB'),[[1,0,0,.07],[0,1,0,0],[0,0,1,0],[0,0,0,1]]),get('C203_BODY'))
 contact_faults=[dict(name='old_underhead_plane_leaves_gap',**old_head,rejected=old_head['distance_mm']>.1),dict(name='PCB_shift70um_loses_CAP_contact',**displaced_PCB,rejected=displaced_PCB['distance_mm']>.06)]
 pcb=get('C203_PCB');pcb_bound=bb['C203_PCB']
 pcb_geometry=dict(valid=bool(BRepCheck_Analyzer(pcb).IsValid()),bbox=pcb_bound,volume_mm3=vol(pcb),passed=bool(BRepCheck_Analyzer(pcb).IsValid()) and vol(pcb)>0 and abs(pcb_bound[0]-profile['faces_S_mm']['front_exposed_copper_x'])<1e-6 and abs(pcb_bound[3]-profile['faces_S_mm']['rear_mask_on_copper_x'])<1e-6)
 st=dict(source_rows=972,unchanged_parent_rows=965,changed_parent_ids=CHANGED,wire_geometry=valid,pcb_geometry=pcb_geometry,nominal_contacts=contacts,contact_faults=contact_faults,broadphase_pair_count=screened,exact_pairs=pairs,interfaces=interfaces,new_bboxes={k:bb[k] for k in added+CHANGED},fault=fault,wire_pair=sep)
 st['passed']=all(q['passed'] for q in valid+pairs+interfaces+contacts+[pcb_geometry]) and all(q['rejected'] for q in contact_faults) and fault['rejected'] and sep['distance_mm']>0 and sep['common_volume_mm3']<1e-6
 out['states'][state]=st
 (A/'results/CAP_HARNESS_EXACT_V19.json').write_text(json.dumps(out,indent=2));print(json.dumps(dict(state=state,passed=st['passed'],pairs=len(pairs),failed=[q for q in valid+pairs+interfaces if not q['passed']])),flush=True)
out['passed']=all(s['passed'] for s in out['states'].values())
(A/'results/CAP_HARNESS_EXACT_V19.json').write_text(json.dumps(out,indent=2));assert out['passed']
