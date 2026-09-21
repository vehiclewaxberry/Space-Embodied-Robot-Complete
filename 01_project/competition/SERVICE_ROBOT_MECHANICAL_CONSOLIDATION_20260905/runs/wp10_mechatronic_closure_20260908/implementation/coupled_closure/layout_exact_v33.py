"""Native solids check for three shortlisted module placements, all states."""
from pathlib import Path
import json,hashlib,numpy as np
from check_spreader_v33 import step,transform,op,volume,bbox
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
HERE=Path(__file__).resolve().parent;A=HERE.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def run():
 dest=HERE/'LAYOUT_EXACT_V33.json';assert not dest.exists()
 screen=read(HERE/'LAYOUT_SCREEN_V33.json');assert all(sha(k)==v for k,v in screen['source_lock'].items())
 plan=read(HERE/'SPREADER_INSTANCE_PLAN_V28.json');module=step(HERE/'main_input_lugs_v30.step');cache={};source_lock={};results=[]
 for i,c in enumerate(screen['best'][:3]):
  T=[[*r,c['translation_mm'][j]] for j,r in enumerate(c['R'])]+[[0,0,0,1]];m=transform(module,T);states={}
  for state,p in plan['states'].items():
   byid={r['id']:r for r in p['rows']};checked=[]
   for identity in c['three_state_AABB'][state]['host_ids']:
    r=byid[identity];path=r['step_path'];assert sha(path)==r['source_sha256'];source_lock[path]=r['source_sha256']
    key=(i,r['source_sha256'],json.dumps(r['T_S_step']))
    if key not in cache:
     host=transform(step(path),r['T_S_step']);d=BRepExtrema_DistShapeShape(m,host);d.Perform();assert d.IsDone()
     v=volume(op(BRepAlgoAPI_Common,m,host)) if d.Value()<1e-7 else 0.
     cache[key]=dict(clearance_mm=d.Value(),common_volume_mm3=v)
    checked.append(dict(id=identity,role=r['representation_role'],**cache[key]))
   states[state]=dict(checked=checked,positive_volume_intersections=[r for r in checked if r['common_volume_mm3']>1e-3])
  results.append(dict(shortlist_index=i,T_S_module=T,states=states,acceptable_clearance_candidate=all(not s['positive_volume_intersections'] for s in states.values())))
  print(i,{s:len(v['positive_volume_intersections']) for s,v in states.items()},flush=True)
 out=dict(schema='WP10_V33_THREE_PLACEMENTS_NATIVE_SCREEN',script_sha256=sha(__file__),helper_sha256=sha(HERE/'check_spreader_v33.py'),screen_sha256=sha(HERE/'LAYOUT_SCREEN_V33.json'),module_step_sha256=sha(HERE/'main_input_lugs_v30.step'),parent_plan_sha256=sha(HERE/'SPREADER_INSTANCE_PLAN_V28.json'),source_lock=source_lock,results=results,whole_design_complete=False,installed=False,scope='Existing 56-instance V30 module, same geometry with V32 ECAD flag-only fix. No missing 23 reference bodies, remote harness bends or new support/thermal interface modeled. Proxies retained. Positive native common volume rejects these specific poses, not all possible layouts.')
 with dest.open('x',encoding='utf-8') as f:json.dump(out,f,indent=2)
 print('Native shortlist check complete.')
if __name__=='__main__':run()
