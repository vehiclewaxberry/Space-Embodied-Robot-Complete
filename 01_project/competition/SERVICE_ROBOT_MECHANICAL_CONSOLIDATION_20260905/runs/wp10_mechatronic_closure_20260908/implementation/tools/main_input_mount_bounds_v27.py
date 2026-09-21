"""Refresh only missing source bounds for the current974 plan; serial native guard required."""
from pathlib import Path
import hashlib,json,itertools,gc
from OCP.STEPControl import STEPControl_Reader
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
src=A/'mechanical/CAP_HARNESS_RETAINED_PLAN_V21.json';p=json.loads(src.read_text())
base=A/'mechanical/CURRENT_936_SOURCE_BOUNDS.json';cache=dict(json.loads(base.read_text())['raw_bounds_by_sha256']);measured=[];verified={};states={}
for state,v in p['states'].items():
 rows=[]
 for r in v['rows']:
  path=Path(r['step_path']);h=r['source_sha256']
  if str(path) not in verified:assert sha(path)==h,str(path);verified[str(path)]=h
  if h not in cache:
   reader=STEPControl_Reader();assert int(reader.ReadFile(str(path)))==1;reader.TransferRoots();shape=reader.OneShape();b=Bnd_Box();BRepBndLib.AddOptimal_s(shape,b);cache[h]=list(b.Get());measured.append(str(path));del reader,shape;gc.collect()
  box=cache[h];T=r['T_S_step'];pts=[]
  for xyz in itertools.product(*[(box[i],box[i+3]) for i in range(3)]):pts.append([sum(T[i][j]*xyz[j] for j in range(3))+T[i][3] for i in range(3)])
  bb=[min(pt[i] for pt in pts) for i in range(3)]+[max(pt[i] for pt in pts) for i in range(3)]
  rows.append(dict(id=r['id'],bbox_S_mm=bb,step_path=str(path),source_sha256=h,T_S_step=T,is_ground_only=r.get('is_ground_only',False),representation_role=r.get('representation_role')))
 states[state]=rows
out=dict(schema='WP10_V27_MAIN_INPUT_PLACEMENT_BOUNDS',source_plan=src.relative_to(A).as_posix(),source_plan_sha256=sha(src),cache_source_sha256=sha(base),
 new_source_reads=measured,verified_file_count=len(verified),states=states,raw_bounds_by_sha256=cache,
 method='Hash-matched optimal source AABB transformed through current instance matrix; overlap is only broad-phase, no whole-fit claim',whole_fit_verified=False)
(A/'mechanical/MAIN_INPUT_PLACEMENT_BOUNDS_V27.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(dict(states={s:len(v) for s,v in states.items()},native_source_reads=len(measured),verified_files=len(verified))))
