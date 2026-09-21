"""Refresh all current-source conservative bounds without retaining all BReps."""
from pathlib import Path
import json,hashlib,itertools,gc
import numpy as np
from OCP.STEPControl import STEPControl_Reader
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
A=Path(__file__).resolve().parents[1]
p=A/'mechanical/ROOT_BUSHING_INSTANCE_PLAN.json'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
plan=json.loads(p.read_text());cache={};rows={}
for state,st in plan['states'].items():
 rows[state]=[]
 for r in st['rows']:
  path=Path(r['step_path']);h=r['source_sha256']
  if h not in cache:
   assert sha(path)==h,str(path)
   reader=STEPControl_Reader();assert int(reader.ReadFile(str(path)))==1;reader.TransferRoots()
   shape=reader.OneShape();b=Bnd_Box();BRepBndLib.AddOptimal_s(shape,b)
   cache[h]=list(b.Get())
   del reader,shape,b;gc.collect()
  bb=cache[h];T=np.asarray(r['T_S_step'])
  pts=np.array([[x,y,z,1] for x,y,z in itertools.product([bb[0],bb[3]],[bb[1],bb[4]],[bb[2],bb[5]])])@T.T
  world=np.r_[pts[:,:3].min(0),pts[:,:3].max(0)].tolist()
  rows[state].append(dict(id=r['id'],source_sha256=h,T_S_step=r['T_S_step'],bbox_S_mm=world,is_ground_only=r['is_ground_only']))
out=dict(schema='WP10_CURRENT_936_SOURCE_BOUNDS_V1',source_plan='mechanical/ROOT_BUSHING_INSTANCE_PLAN.json',source_plan_sha256=sha(p),
 method='OCP source-local optimal AABB, transformed eight corners; conservative S bounds. No intersection, solid validity, whole fit or flight claim.',
 source_script_sha256=sha(__file__),raw_bounds_by_sha256=cache,states=rows,source_geometry_changed=False,whole_fit_verified=False)
(A/'mechanical/CURRENT_936_SOURCE_BOUNDS.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(dict(states={k:len(v) for k,v in rows.items()},unique_sources=len(cache))))
for r in rows['service']:
 bb=r['bbox_S_mm']
 if r['id'] in ['U202_CHB','U202_CHB_OEM','WP10_RRC3570_4_D_MAX_ENVELOPE'] or ('CHB' in r['id'] and 'SCREW' not in r['id']):
  print(json.dumps(r))
# Candidate input area: only spatial inventory, not a selected placement.
q=[-65,-70,-100,45,70,-10]
hits=[dict(id=r['id'],bbox=r['bbox_S_mm']) for r in rows['service'] if not r['is_ground_only'] and all(r['bbox_S_mm'][i]<=q[i+3] and r['bbox_S_mm'][i+3]>=q[i] for i in range(3))]
(A/'results/INPUT_INSTALLATION_SPATIAL_INVENTORY.json').write_text(json.dumps(hits,indent=2),encoding='utf-8')
print(json.dumps(dict(neighbor_count=len(hits),neighbors=[r['id'] for r in hits])))

