"""24 proper axis rotations, declared interior envelope; AABB is a screen only."""
from pathlib import Path
import itertools,json,hashlib
import numpy as np
HERE=Path(__file__).resolve().parent;A=HERE.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def run():
 dest=HERE/'LAYOUT_SCREEN_V33.json';assert not dest.exists()
 p=read(A/'mechanical/MAIN_INPUT_PLACEMENT_BOUNDS_V27.json');g=read(HERE/'LUG_GEOMETRY_CHECK_V30.json');current=read(HERE/'SPREADER_INSTANCE_PLAN_V28.json')
 assert g['source_sha256']==sha(HERE/'main_input_lugs_v30.step.py')
 refs=read(HERE/'LUG_REFS_V30.json');assert refs['tokens'][0]['stepHash']==sha(HERE/'main_input_lugs_v30.step')
 assert all(sha(A/k)==v for k,v in read(HERE/'LUG_SOURCE_LOCK_V30.json').items())
 assert sha(A/p['source_plan'])==p['source_plan_sha256']
 # V28 spreader differs only in z thickness; conservatively merge the old bounds
 # with validated replacement bounds, preserving all other retained host rows.
 spread=read(HERE/'SPREADER_REFS_V28.json')['tokens'][0]['summary']['bounds']
 hostrows={}
 for state,rows in p['states'].items():
  cur={r['id']:r for r in current['states'][state]['rows']};out=[]
  for r in rows:
   v=dict(r)
   if r['id']=='radiator_spreader':
    assert np.allclose(np.array(cur[r['id']]['T_S_step']),np.eye(4))
    v.update(step_path=cur[r['id']]['step_path'],source_sha256=cur[r['id']]['source_sha256'],bbox_S_mm=spread['min']+spread['max'])
   else:
    for k in ['step_path','source_sha256','T_S_step','representation_role','is_ground_only']:assert r[k]==cur[r['id']][k]
   out.append(v)
  hostrows[state]=out
 rows=hostrows['service'];host=np.array([r['bbox_S_mm'] for r in rows]);parts=np.array([r['bounds'] for r in g['component_bounds']]);mid=(parts[:,:3]+parts[:,3:])/2;half=(parts[:,3:]-parts[:,:3])/2
 origin=np.array([50.,-40.,8.]);outerhalf=np.array([97.0208,46.,24.])
 interior=np.array([[-170.,-95.,-97.],[168.,95.,97.]])
 rotations=[]
 for perm in itertools.permutations(range(3)):
  for signs in itertools.product([-1,1],repeat=3):
   R=np.zeros((3,3),dtype=int)
   for i,j in enumerate(perm):R[i,j]=signs[i]
   if round(np.linalg.det(R))==1:rotations.append(R)
 assert len(rotations)==24
 allbest=[];counts=[]
 for ri,R in enumerate(rotations):
  hs=abs(R)@outerhalf;lo=interior[0]+hs;hi=interior[1]-hs
  axes=[np.arange(np.ceil(lo[i]/10)*10,hi[i]+1e-9,10.) for i in range(3)]
  centers=np.array(list(itertools.product(*axes)))
  if len(centers)==0:counts.append(0);continue
  counts.append(len(centers));rank=[]
  for start in range(0,len(centers),128):
   q=centers[start:start+128];b0=q[:,None,:]-hs;b1=q[:,None,:]+hs
   overlap=np.maximum(np.minimum(b1,host[None,:,3:])-np.maximum(b0,host[None,:,:3]),0.)
   hits=(overlap>1e-5).all(axis=2);vol=np.prod(overlap,axis=2).sum(axis=1)
   for j in range(len(q)):rank.append((int(hits[j].sum()),float(vol[j]),start+j))
  rank.sort();pm=(mid-origin)@R.T;ph=half@abs(R).T
  fine=[]
  for _,_,idx in rank[:80]:
   center=centers[idx];b0=pm+center-ph;b1=pm+center+ph
   overlap=np.maximum(np.minimum(b1[:,None,:],host[None,:,3:])-np.maximum(b0[:,None,:],host[None,:,:3]),0.)
   hits=(overlap>1e-5).all(axis=2)
   fine.append(dict(rotation_index=ri,R=R.tolist(),center_S_mm=center.tolist(),translation_mm=(center-R@origin).tolist(),component_AABB_pair_count=int(hits.sum()),host_count=int(hits.any(axis=0).sum()),AABB_overlap_sum_mm3=float(np.prod(overlap,axis=2).sum()),host_ids=[rows[i]['id'] for i in np.flatnonzero(hits.any(axis=0))]))
  fine.sort(key=lambda x:(x['component_AABB_pair_count'],x['AABB_overlap_sum_mm3']));allbest.extend(fine[:8])
 allbest.sort(key=lambda x:(x['component_AABB_pair_count'],x['AABB_overlap_sum_mm3']))
 for row in allbest[:24]:
  R=np.array(row['R']);pm=(mid-origin)@R.T+row['center_S_mm'];ph=half@abs(R).T;b0=pm-ph;b1=pm+ph
  states={}
  for state,rr in hostrows.items():
   h=np.array([v['bbox_S_mm'] for v in rr]);hits=(np.minimum(b1[:,None,:],h[None,:,3:])-np.maximum(b0[:,None,:],h[None,:,:3])>1e-5).all(axis=2)
   states[state]=dict(pair_count=int(hits.sum()),host_ids=[rr[i]['id'] for i in np.flatnonzero(hits.any(axis=0))])
  row['three_state_AABB']=states
 source_files=[A/'mechanical/MAIN_INPUT_PLACEMENT_BOUNDS_V27.json',HERE/'SPREADER_INSTANCE_PLAN_V28.json',HERE/'LUG_GEOMETRY_CHECK_V30.json',HERE/'LUG_REFS_V30.json',HERE/'LUG_SOURCE_LOCK_V30.json',HERE/'main_input_lugs_v30.step',HERE/'SPREADER_REFS_V28.json']
 result=dict(schema='WP10_V33_ORTHOGONAL_LAYOUT_SCREEN',script_sha256=sha(__file__),source_lock={str(f):sha(f) for f in source_files},proper_rotations=24,positions_per_rotation=counts,total_envelope_poses=sum(counts),best=allbest[:24],interior_screen_box_S_mm=interior.tolist(),grid_mm=10,module_local_center_mm=origin.tolist(),host_rows=974,installed=False,whole_design_complete=False,search_complete=False,scope='Every retained host including proxies kept. Coarse envelope top80 per rotation refined with 56 component AABBs; heuristic ranking can miss valid layouts. Positive AABB intersections are not solid collisions; finite grid cannot prove infeasibility. Envelope is a declared conservative search box, not a launch envelope certification.')
 with dest.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
 print(json.dumps(dict(poses=sum(counts),best=result['best'][:3])))
if __name__=='__main__':run()
