from pathlib import Path
import sys,json,importlib.util,itertools,hashlib,math
sys.path.insert(0,'F:/codex_skill/AgentSkills/agents-skills/cad/scripts/packages/cadgen/src')
from build123d import Pos,Rot
A=Path(__file__).resolve().parents[1];C=A/'coupled_closure';f=C/'main_input_lugs_v30.step.py';spec=importlib.util.spec_from_file_location('v30check',f);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def overlap(a,b):
 c=a&b;return sum(s.volume for s in c.solids()) if c is not None else 0
def bounds(s):return list(s.bounding_box().min)+list(s.bounding_box().max)
start_hash=hashlib.sha256(f.read_bytes()).hexdigest();assembly=m.gen_step();parts=list(assembly.children);added=parts[16:];pairs=[];boxes=[bounds(p) for p in parts]
for i,a in enumerate(parts):
 for j,b in enumerate(parts[:i]):
  if i<16:continue
  aa=boxes[i];bb=boxes[j]
  if any(min(aa[k+3],bb[k+3])-max(aa[k],bb[k])<=1e-6 for k in range(3)):continue
  v=overlap(a,b)
  if v>1e-6:pairs.append(dict(a=a.label,b=b.label,overlap_mm3=v))
rows=[]
for ref,x,y,side in m.ROWS:
 l=next(p for p in parts if p.label.startswith(ref+'_TE'));w=next(p for p in parts if p.label.startswith(ref+'_ETT'));n=next(p for p in parts if p.label.startswith(ref+'_HPC'))
 rows.append(dict(ref=ref,lug_bounds=bounds(l),washer_bounds=bounds(w),nut_bounds=bounds(n),lug_to_washer_gap=l.distance_to(w),washer_to_nut_gap=w.distance_to(n),nominal_stud_protrusion=10.5-n.bounding_box().max.Z))
wrong=overlap(m.lug('bad',7,-15,-1,90),m.lug('bad2',7,-28,-1))
checks=dict(all_solids_valid=all(s.is_valid and s.volume>0 for s in assembly.solids()),expected_60_solids=len(assembly.solids())==60,no_added_penetration=not pairs,joint_mating_datums=all(abs(r['washer_bounds'][2]-(3.5+.9779))<1e-6 and abs(r['nut_bounds'][2]-(3.5+.9779+1))<1e-6 for r in rows),misoriented_lug_detected=wrong>1e-5)
checks['source_unchanged_during_execution']=start_hash==hashlib.sha256(f.read_bytes()).hexdigest()
out=dict(checks=checks,passed=all(checks.values()),solid_count=len(assembly.solids()),occurrence_count=len(parts),bounds_mm=bounds(assembly),component_bounds=[dict(label=p.label,bounds=bounds(p),volume_mm3=p.volume) for p in parts],intersections=pairs,stack_rows=rows,wrong_90_degree_lug_overlap_mm3=wrong,whole_assembly_clear=False,clamp_retention_qualified=False,source_sha256=start_hash)
(C/'LUG_GEOMETRY_CHECK_V30.json').write_text(json.dumps(out,indent=2));print(json.dumps({k:v for k,v in out.items() if k!='component_bounds'}));assert all(checks.values())
