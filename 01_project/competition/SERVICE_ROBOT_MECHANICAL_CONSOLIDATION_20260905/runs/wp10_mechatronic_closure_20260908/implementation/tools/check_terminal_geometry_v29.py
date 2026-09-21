from pathlib import Path
import importlib.util,json,itertools
from build123d import Pos,import_step
from terminals_v29 import A,ROWS,sha,dump
P=A/'coupled_closure/main_input_terminals_v29.step.py';spec=importlib.util.spec_from_file_location('termv29',P);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def vol(a,b):
 c=a&b;return 0 if c is None else sum(s.volume for s in c.solids())
b=m.board();old=m.m.main_carrier();new=m.carrier();r=m.shunt('R202');model=import_step(A/'sources/terminal_v29/MP_Wurth_WP-THRSH_74651195.step');rows=[]
for ref,_,(x,y),_ in ROWS:
 zero=Pos(x,-y,0)*model;right=Pos(x,-y,.5)*model
 rows.append(dict(ref=ref,wrong_zero_offset_overlap_mm3=vol(zero,b),correct_offset_overlap_mm3=vol(right,b),body_bounds_mm=list(right.bounding_box().min)+list(right.bounding_box().max),new_carrier_gap_mm=right.distance_to(new)))
assembly=m.gen_step();parts=list(assembly.children);pairs=[]
for i in range(14,len(parts)):
 for j in range(i):
  v=vol(parts[i],parts[j])
  if v>1e-6:pairs.append(dict(a=parts[i].label,b=parts[j].label,overlap_mm3=v))
removed=vol(old,old-new);old_r=vol(old,r);new_r=vol(new,r);gap=new.distance_to(r)
checks=dict(all_24_solids_valid=len(assembly.solids())==24 and all(s.is_valid for s in assembly.solids()),zero_datum_detected=all(r['wrong_zero_offset_overlap_mm3']>1e-4 for r in rows),proper_datum_no_board_penetration=all(r['correct_offset_overlap_mm3']<1e-6 for r in rows),old_R202_envelope_conflict_detected=old_r>1e-4,new_R202_envelope_clear=new_r<1e-6 and gap>=.99,no_new_component_intersections=not pairs)
out=dict(passed=all(checks.values()),checks=checks,terminal_rows=rows,old_R202_max_envelope_overlap_mm3=old_r,new_R202_max_envelope_overlap_mm3=new_r,new_R202_max_envelope_clearance_mm=gap,carrier_removed_volume_mm3=removed,added_part_intersections=pairs,solid_count=len(assembly.solids()),unmodeled_electrical_refs=23,whole_assembly_pass=False,thermal_qualification=False,sources={str(p.relative_to(A)):sha(p) for p in [P,A/'power/MAIN_INPUT_BOARD_DEFINITION_V29.json']})
out.update(R202_OEM_old_carrier_overlap_mm3=vol(old,m.physical_shunt('R202')),R202_OEM_new_carrier_overlap_mm3=vol(new,m.physical_shunt('R202')),shunt_solder_standoff_mm=.2,shunt_solder_standoff_qualified=False)
dump(A/'coupled_closure/TERMINAL_GEOMETRY_CHECK_V29.json',out);print(json.dumps(out));assert all(checks.values()),checks
