"""Actual nine-pin power terminals, new board drills, and bounded shunt clearance."""
from pathlib import Path
import importlib.util,json,hashlib
from build123d import Compound,Pos,import_step,Color
HERE=Path(__file__).resolve().parent;A=HERE.parent
spec=importlib.util.spec_from_file_location('wp10_coupled_parts_v29',HERE/'mechanical_parts.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def board():
 d=json.loads((A/'power/MAIN_INPUT_BOARD_DEFINITION_V29.json').read_text())
 s=m.box_at(0,-80,-1.6,100,80,1.6)
 for p in d['pads']:
  dx,dy=p['drill_mm'];x,y=p['xy_mm']
  if dx<=0:continue
  if abs(dx-dy)<1e-8:cut=m.hole_z(x,-y,-2,dx,3)
  else:
   assert dx>=dy;cut=m.box_at(x-(dx-dy)/2,-y-dy/2,-2,dx-dy,dy,3)
   for off in [-(dx-dy)/2,(dx-dy)/2]:cut+=m.hole_z(x+off,-y,-2,dy,3)
  s-=cut
 return m.tag(s,'V29_PCB_ACTUAL_135_PAD_DRILLS_1p6_NOMINAL',(.03,.30,.16))

def shunt(ref):
 x=34 if ref=='R201' else 45;h=3.1 if ref=='R201' else 4.01
 return m.tag(m.box_at(x-3.55,-18.45,.2,7.1,6.9,h),'REF_'+ref+'_MAX_DRAWING_ENVELOPE_PLUS_0p2_SOLDER_ALLOWANCE',(.64,.43,.22))

def carrier():
 s=m.main_carrier()-m.box_at(40.45,-14.597,3,9.1,5,3)
 return m.tag(s,'MC01_V29_R202_LOWER_LEFT_CLEARANCE_NOTCH__HOST_OPEN',m.AL)

def physical_shunt(ref):
 x=34 if ref=='R201' else 45
 name='WSLP2726 (0.002).stp' if ref=='R201' else 'WSLP2726 (0.2mohm).stp'
 s=import_step(A/'sources/terminal_v29'/name);z=s.bounding_box().min.Z
 # OEM y=0..6.6; underside z differs with resistance. Center the body on
 # the footprint and use the explicitly unqualified 0.2 mm solder stand-off.
 return m.tag(Pos(x,-18.3,.2-z)*s,ref+'_VISHAY_OEM_3_SOLIDS_PROJECT_SOLDER_DATUM',(.64,.43,.22))

def gen_step():
 lock=json.loads((HERE/'TERMINAL_GEOMETRY_INPUTS_V29.json').read_text())
 for rel,h in lock['source_lock'].items():assert hashlib.sha256((A/rel).read_bytes()).hexdigest()==h,'SOURCE_DRIFT '+rel
 parts=m.main_parts();parts[0]=carrier();parts[1]=board()
 src=A/'sources/terminal_v29/MP_Wurth_WP-THRSH_74651195.step'
 for ref,x,y in [('J204',7,15),('J205',7,28),('J206',93,15),('J207',93,28)]:
  s=Pos(x,-y,.5)*import_step(src);parts.append(m.tag(s,ref+'_WURTH_74651195R_OEM_MODEL_STANDOFF_DATUM_CORRECTED',(.67,.70,.74)))
 parts.extend([physical_shunt('R201'),physical_shunt('R202')])
 return Compound(label='WP10_V29_MAIN_INPUT_PARTIAL_MODULE__NO_HOST_INSTALL_NO_CURRENT_QUALIFICATION',children=parts)
