"""Exact changed-part and knot-envelope checks against hash-bound parent bounds."""
from pathlib import Path
import hashlib,json,sys,itertools
from chb_input_ocp import *
A=Path(__file__).resolve().parents[1]
def read(p):return json.loads((A/p).read_text())
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
p=read('mechanical/CAP_HARNESS_RETAINED_PLAN_V21.json');parent=read(p['parent_plan'])
assert p['parent_plan_sha256']==sha(p['parent_plan'])
assert all(sha(f)==h for f,h in p['inputs'].items())
old_exact=read('results/CAP_HARNESS_EXACT_V19.json');assert old_exact['passed']
assert all(sha(f)==h for f,h in old_exact['inputs'].items())
cache=read('mechanical/CURRENT_936_SOURCE_BOUNDS.json');cap=read('results/INPUT_CAP_MOUNT_EXACT.json');chb=read('results/CHB_INPUT_MECHANICAL_V18.json')
c=read('power/CAP_HARNESS_RETENTION_V21.json');d=c['design']
paths=['mechanical/CAP_HARNESS_RETAINED_PLAN_V21.json',p['parent_plan'],'results/CAP_HARNESS_EXACT_V19.json','mechanical/CURRENT_936_SOURCE_BOUNDS.json','results/INPUT_CAP_MOUNT_EXACT.json','results/CHB_INPUT_MECHANICAL_V18.json','power/CAP_HARNESS_RETENTION_V21.json','tools/check_cap_retention_exact_v21.py','tools/chb_input_ocp.py']
out=dict(schema='WP10_CAP_RETENTION_EXACT_V21',inputs={f:sha(f) for f in paths},states={},whole_fit_verified=False,strain_relief_complete=False,continuous_motion_checked=False,physical_assembly_executed=False,scope='All non-ground parent rows broad-phase screened in three discrete states; exact delta neighbors and knot envelopes only; no whole-body or tolerance credit.')
raw={}
def shape(r):
 path=Path(r['step_path']);h=r['source_sha256'];assert hashlib.sha256(path.read_bytes()).hexdigest()==h
 if h not in raw:raw[h]=load(path)
 return transform(raw[h],r['T_S_step'])
changed=['C203_LOWER_B','C203_LACE_PLUS','C203_LACE_MINUS']
for state,st in p['states'].items():
 rows={r['id']:r for r in st['rows']};prior={r['id']:r for r in parent['states'][state]['rows']}
 assert len(rows)==974 and len(prior)==972 and set(rows)-set(prior)=={'C203_LACE_PLUS','C203_LACE_MINUS'}
 assert all(rows[k]==v for k,v in prior.items() if k!='C203_LOWER_B')
 # Prior exact receipt was computed with this exact parent and cache. Recheck
 # unchanged cache transformations, and obtain all delta boxes from receipts.
 overrides=set(cap['states'][state]['changed_bboxes'])|set(chb['states'][state]['new_bboxes'])|set(old_exact['states'][state]['new_bboxes'])
 for q in cache['states'][state]:
  if q['id'] in overrides:continue
  row=prior[q['id']]
  assert all(row[k]==q[k] for k in ['source_sha256','T_S_step','is_ground_only'])
  local=cache['raw_bounds_by_sha256'][row['source_sha256']];T=row['T_S_step']
  corners=[[sum(T[i][j]*v[j] for j in range(3))+T[i][3] for i in range(3)] for v in itertools.product(*[(local[i],local[i+3]) for i in range(3)])]
  expected=[min(v[i] for v in corners) for i in range(3)]+[max(v[i] for v in corners) for i in range(3)]
  assert max(abs(x-y) for x,y in zip(expected,q['bbox_S_mm']))<1e-8
 bb={q['id']:q['bbox_S_mm'] for q in cache['states'][state]}
 for mapping in [cap['states'][state]['changed_bboxes'],chb['states'][state]['new_bboxes'],old_exact['states'][state]['new_bboxes']]:bb.update(mapping)
 assert set(prior)<=set(bb)
 geom={}
 def get(k):
  if k not in geom:geom[k]=shape(rows[k])
  return geom[k]
 valid=[]
 for k in changed:
  s=get(k);bb[k]=bounds(s)
  valid.append(dict(id=k,valid=bool(BRepCheck_Analyzer(s).IsValid()),solids=count(s),volume_mm3=vol(s),bbox_mm=bb[k],passed=bool(BRepCheck_Analyzer(s).IsValid()) and count(s)==1 and vol(s)>0))
 allowed={tuple(sorted(q['ids'])) for q in cap['states'][state]['tests'] if q.get('nominal_contact_allowed') and 'C203_LOWER_B' in q['ids']}
 for sign in ['PLUS','MINUS']:
  allowed.add(tuple(sorted(['C203_LACE_'+sign,'C203_W_'+sign])))
  allowed.add(tuple(sorted(['C203_LACE_'+sign,'C203_LOWER_B'])))
  allowed.add(tuple(sorted(['C203_W_'+sign,'C203_LOWER_B'])))
 seen=set();pairs=[];screened=0
 for k in changed:
  for j,row in rows.items():
   key=tuple(sorted([k,j]))
   if j==k or key in seen or row['is_ground_only']:continue
   seen.add(key);screened+=1
   if not near(bb[k],bb[j],.5):continue
   q=exact(get(k),get(j));q.update(ids=list(key),nominal_contact_allowed=key in allowed)
   q['passed']=q['common_volume_mm3']<1e-6 and (key in allowed or q['distance_mm']>1e-6);pairs.append(q)
 band=get('C203_LOWER_B');original=shape(prior['C203_LOWER_B'])
 delta=op(BRepAlgoAPI_Cut,band,original);removed=vol(op(BRepAlgoAPI_Cut,original,band))
 preservation=dict(original_volume_mm3=vol(original),retained_volume_mm3=vol(band),removed_parent_material_mm3=removed,added_mm3=vol(delta),passed=removed<1e-6 and vol(delta)>0)
 interfaces=[]
 for sign in ['PLUS','MINUS']:
  for a,b in [('C203_LOWER_B','C203_W_'+sign),('C203_LOWER_B','C203_LACE_'+sign),('C203_W_'+sign,'C203_LACE_'+sign)]:
   q=exact(get(a),get(b));q.update(ids=[a,b],passed=q['distance_mm']<1e-6 and q['common_volume_mm3']<1e-6);interfaces.append(q)
 # Only new material is checked against clamp-head and tool volumes; existing
 # clamp/head contact remains legitimate and is tested above.
 tools=[]
 for i in [2,3]:
  sr=rows[f'C203_CLAMP_SCREW_{i}'];T=sr['T_S_step'];x,y,z=[T[k][3] for k in range(3)]
  tip=cyl(2.,[x,y,z-14.],[0,0,1],12.5)
  q=exact(delta,tip);tools.append(dict(name=f'local_d4_tool_for_clamp_{i}',**q,passed=q['distance_mm']>0 and q['common_volume_mm3']<1e-6,scope='Only local 12.5 mm shaft segment, not whole tool approach'))
  q=exact(delta,get(f'C203_CLAMP_SCREW_{i}'));tools.append(dict(name=f'added_material_to_clamp_head_{i}',**q,passed=q['distance_mm']>.1 and q['common_volume_mm3']<1e-6))
 knots=[]
 r=read(c['wire_definition'])['wire']['max_insulation_D_mm']/2
 bottom=d['wire_z_mm']-r-d['saddle_depth_mm'];kx,ky,kz=d['knot_keepout_mm']
 for sign in [-1,1]:
  lo=[d['tie_center_x_mm']-kx/2,sign*d['saddle_center_abs_y_mm']-ky/2,bottom-d['knot_gap_below_saddle_mm']-kz]
  box=BRepPrimAPI_MakeBox(gp_Pnt(*lo),kx,ky,kz).Shape();bbox=bounds(box)
  hits=[]
  for j,row in rows.items():
   if row['is_ground_only'] or not near(bbox,bb[j],.1):continue
   q=exact(box,get(j));hits.append(dict(id=j,**q,passed=q['distance_mm']>1e-6 and q['common_volume_mm3']<1e-6))
  knots.append(dict(side=sign,bbox_mm=bbox,hits=hits,passed=all(q['passed'] for q in hits),scope='Declared knot/trim-tail allowance only, not actual tied geometry or hand clearance'))
 # Geometry adversary: push the same lace half a millimetre into insulation.
 shifted=transform(get('C203_LACE_PLUS'),[[1,0,0,0],[0,1,0,0],[0,0,1,-.5],[0,0,0,1]])
 bad=exact(shifted,get('C203_W_PLUS'));fault=dict(name='lace_shifted_down_0p5_into_wire',**bad,rejected=bad['common_volume_mm3']>1e-5)
 result=dict(source_rows=974,unchanged_parent_rows=971,geometry=valid,preservation=preservation,broadphase_pair_count=screened,exact_pairs=pairs,interfaces=interfaces,tool_checks=tools,knot_checks=knots,geometry_fault=fault,new_bboxes={k:bb[k] for k in changed})
 result['passed']=all(x['passed'] for x in valid+pairs+interfaces+tools+knots+[preservation]) and fault['rejected']
 out['states'][state]=result
 (A/'results/CAP_RETENTION_EXACT_V21.json').write_text(json.dumps(out,indent=2))
 print(json.dumps(dict(state=state,passed=result['passed'],pairs=len(pairs),failed=[x for x in valid+pairs+interfaces+tools+knots+[preservation] if not x['passed']])),flush=True)
out['passed']=all(st['passed'] for st in out['states'].values())
(A/'results/CAP_RETENTION_EXACT_V21.json').write_text(json.dumps(out,indent=2));assert out['passed']

