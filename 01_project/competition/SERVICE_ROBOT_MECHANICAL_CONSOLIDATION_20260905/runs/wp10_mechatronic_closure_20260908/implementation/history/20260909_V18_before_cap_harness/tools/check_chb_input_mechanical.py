"""Current 970-source delta, not whole assembly certification."""
from pathlib import Path
import json,hashlib,itertools,math
from chb_input_ocp import *
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads((A/p).read_text())
plan=read('mechanical/CHB_INPUT_INSTANCE_PLAN.json');parent=read(plan['parent_plan']);d=read('power/CHB_INPUT_DEFINITION.json');cache=read('mechanical/CURRENT_936_SOURCE_BOUNDS.json');cap=read('results/INPUT_CAP_MOUNT_EXACT.json')
assert plan['parent_plan_sha256']==sha(A/plan['parent_plan']) and plan['component_count']==970
assert cap['inputs']['mechanical/INPUT_CAP_MOUNT_INSTANCE_PLAN.json']==sha(A/plan['parent_plan'])
result=dict(schema='WP10_CHB_INPUT_DELTA_EXACT_V18',states={},whole_fit_verified=False,effective_thread_engagement_qualified=False,physical_assembly_executed=False,inputs={p:sha(A/p) for p in ['mechanical/CHB_INPUT_INSTANCE_PLAN.json','mechanical/INPUT_CAP_MOUNT_INSTANCE_PLAN.json','power/CHB_INPUT_DEFINITION.json','mechanical/CURRENT_936_SOURCE_BOUNDS.json','results/INPUT_CAP_MOUNT_EXACT.json','tools/check_chb_input_mechanical.py','tools/chb_input_ocp.py']})
raw={}
def shape(r):
 path=Path(r['step_path']);h=r['source_sha256'];assert sha(path)==h
 if h not in raw:raw[h]=load(path)
 return transform(raw[h],r['T_S_step'])
for state,sp in plan['states'].items():
 rows={r['id']:r for r in sp['rows']};old={r['id']:r for r in parent['states'][state]['rows']};added=sp['added_ids'];assert len(rows)==970 and len(added)==5 and set(rows)-set(old)==set(added)
 assert all(rows[k]==v for k,v in old.items()),'Parent row changed'
 bb={r['id']:r['bbox_S_mm'] for r in cache['states'][state]};bb.update(cap['states'][state]['changed_bboxes']);geoms={}
 def get(k):
  if k not in geoms:geoms[k]=shape(rows[k])
  return geoms[k]
 valid=[]
 for k in added:
  s=get(k);bb[k]=bounds(s);valid.append(dict(id=k,valid=bool(BRepCheck_Analyzer(s).IsValid()),volume_mm3=vol(s),bbox=bb[k]))
 allowed={tuple(sorted([f'CHB_INPUT_{kind}_{i}','CHB_INPUT_PCB'])) for i in range(2) for kind in ['SPACER','SCREW']}
 allowed |= {tuple(sorted([f'CHB_INPUT_SPACER_{i}','U202_CHB'])) for i in range(2)}
 pairs=[];seen=set()
 for k in added:
  for j,r in rows.items():
   pair=tuple(sorted([k,j]))
   if j==k or pair in seen or r['is_ground_only']:continue
   seen.add(pair)
   if not near(bb[k],bb[j],.3):continue
   q=exact(get(k),get(j));q.update(ids=list(pair),nominal_contact_allowed=pair in allowed)
   if 'U202_CHB' in pair and any(x.startswith('CHB_INPUT_SCREW_') for x in pair):
    name=next(x for x in pair if x.startswith('CHB_INPUT_SCREW_'));i=int(name[-1]);x,y=d['mount_S_xy_mm'][i]
    tool=cyl(1.500001,[x,y,-93],[0,0,1],9.05)
    common=op(BRepAlgoAPI_Common,get(k),get(j));residual=op(BRepAlgoAPI_Cut,common,tool)
    q.update(thread_major_minor_overlap_disposition='Unqualified nominal M3 screw vs OEM minor-diameter bore, allowed only inside declared insert segment',thread_residual_mm3=vol(residual),passed=vol(residual)<1e-6)
   else:q['passed']=q['common_volume_mm3']<1e-6 and (q['distance_mm']>1e-7 or q['nominal_contact_allowed'])
   pairs.append(q)
 contacts=[]
 for pair in sorted(allowed):
  q=exact(get(pair[0]),get(pair[1]));contacts.append(dict(ids=list(pair),**q,passed=q['distance_mm']<1e-6 and q['common_volume_mm3']<1e-6))
 pins=[]
 for p in d['pads']:
  x,y=p['S_xy_mm'];s=cyl(p['drill_mm']/2,[x,y,-82],[0,0,1],4);q=exact(s,get('CHB_INPUT_PCB'));pins.append(dict(id=p['id'],actual_hole_void_mm3=q['common_volume_mm3'],passed=q['common_volume_mm3']<1e-6))
 for i,(x,y) in enumerate(d['mount_S_xy_mm']):
  top=get('CHB_INPUT_SCREW_'+str(i));bottom=get('WP10_CHB_'+str(i)+'_SCREW');q=exact(top,bottom);pins.append(dict(id='OPPOSING_SCREWS_'+str(i),**q,passed=q['distance_mm']>1))
 b=d['board_bounds_S_mm'];got=bb['CHB_INPUT_PCB'];pins.append(dict(id='ACTUAL_FINISHED_PCB_BOUNDS',passed=max(abs(x-y) for x,y in zip(b,got))<1e-5,actual=got))
 # Source-cylinder maximum diameter envelope is separate from unbound positions.
 for num,y,maxr in [('1',-17.78,1.05),('2',-7.62,.55),('4',17.78,1.05)]:
  s=cyl(maxr,[-49.13,y,-83.45],[0,0,1],5.8);q=exact(s,get('CHB_INPUT_PCB'));pins.append(dict(id='MAX_PIN_DIAMETER_'+num,**q,passed=q['common_volume_mm3']<1e-6,position_tolerances_included=False))
 st=dict(geometry=valid,pairs=pairs,contacts=contacts,interface=pins,unchanged_parent_rows=965,source_rows=970,new_bboxes={k:bb[k] for k in added})
 st['passed']=all(q['valid'] and q['volume_mm3']>0 for q in valid) and all(q['passed'] for q in pairs+contacts+pins)
 result['states'][state]=st
 (A/'results/CHB_INPUT_MECHANICAL_V18.json').write_text(json.dumps(result,indent=2));print(json.dumps(dict(state=state,passed=st['passed'],failures=[q for q in pairs+contacts+pins if not q['passed']])),flush=True)
result['passed']=all(s['passed'] for s in result['states'].values())
result['lead_projection_min_nominal_mm']=(5.3-.5)-(d['board_bounds_S_mm'][5]-(-83.45))
result['tolerance_stack_complete']=False
(A/'results/CHB_INPUT_MECHANICAL_V18.json').write_text(json.dumps(result,indent=2));assert result['passed']
