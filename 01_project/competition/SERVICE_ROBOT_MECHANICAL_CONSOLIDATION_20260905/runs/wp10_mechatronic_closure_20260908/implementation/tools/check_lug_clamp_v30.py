from pathlib import Path
import sys,json,importlib.util,hashlib,math
sys.path.insert(0,'F:/codex_skill/AgentSkills/agents-skills/cad/scripts/packages/cadgen/src')
from build123d import Pos
A=Path(__file__).resolve().parents[1];C=A/'coupled_closure';f=C/'main_input_lugs_v30.step.py';spec=importlib.util.spec_from_file_location('clamp30',f);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def vol(a,b):
 s=a&b;return sum(x.volume for x in s.solids()) if s is not None else 0
def grip(base,cover,wires):return all(base.distance_to(w)<1e-5 and cover.distance_to(w)<1e-5 and vol(base,w)<1e-6 and vol(cover,w)<1e-6 for w in wires)
rows=[]
for d in [3.0988,3.2512,3.4036]:
 base=m.left_base(d);cover=m.left_cover(d);wires=[m.wire_segment(ref,x,y,s,d) for ref,x,y,s in m.ROWS[:2]]
 rows.append(dict(diameter_mm=d,base_cover_overlap_mm3=vol(base,cover),matched_family_contact=grip(base,cover,wires),floating_cover_rejected=not grip(base,Pos(0,0,100)*cover,wires),constant_wire_centerline_z=m.WIRE_Z,matched_size_family_only_not_one_fixed_part_tolerance_qualification=True))
base=m.left_base();cover=m.left_cover();holes=[]
for right in [False,True]:
 for y in [-9,-34]:
  x=110 if right else -10;probe=m.m.hole_z(x,y,-12,3.35,30)
  holes.append(dict(x=x,y=y,base_intrusion_mm3=vol(probe,m.mirror_side(base,right)),cover_intrusion_mm3=vol(probe,m.mirror_side(cover,right)),carrier_intrusion_mm3=vol(probe,m.v29.carrier())))
# A bad old d-min cover moved bodily into the base; preserve explicit point-volume counterexample.
dz=(3.0988/2-m.WIRE_R)*(1+math.sqrt(2));bad=Pos(0,0,dz)*m.left_cover();bad_overlap=vol(base,bad)
nominal_wires_max=[m.wire_segment(ref,x,y,s,3.4036) for ref,x,y,s in m.ROWS[:2]]
fixed_nominal_rejected=not grip(base,cover,nominal_wires_max)
checks=dict(matched_diameter_families_contact=all(r['matched_family_contact'] for r in rows),all_family_base_cover_clear=all(r['base_cover_overlap_mm3']<1e-6 for r in rows),lifted_cover_falsifier=all(r['floating_cover_rejected'] for r in rows),mount_hole_axes_clear=all(max(r[k] for k in ['base_intrusion_mm3','cover_intrusion_mm3','carrier_intrusion_mm3'])<1e-6 for r in holes),old_dmin_cover_interference_reproduced=bad_overlap>1e-4,one_nominal_clamp_not_false_tolerance_pass=fixed_nominal_rejected)
out=dict(checks=checks,passed=all(checks.values()),families=rows,mount_holes=holes,bad_old_dmin_overlap_mm3=bad_overlap,fixed_nominal_clamp_for_Dmax_rejected=fixed_nominal_rejected,clamp_preload_and_strain_relief_qualified=False,source_sha256=hashlib.sha256(f.read_bytes()).hexdigest())
(C/'LUG_CLAMP_CHECK_V30.json').write_text(json.dumps(out,indent=2));print(json.dumps(out));assert all(checks.values())
