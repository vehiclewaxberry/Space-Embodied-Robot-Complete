"""V29 PCB source + OEM lugs + source-positioned project wire retainers/covers."""
from pathlib import Path
import importlib.util,json,hashlib,math
from build123d import Compound,Pos,Rot,Plane,Wire,Face,extrude,RegularPolygon,Location,RigidJoint
from cadgen.step_scene import import_step
HERE=Path(__file__).resolve().parent;A=HERE.parent;S=A/'sources/lugs_v30'
spec=importlib.util.spec_from_file_location('v29_lug_parent',HERE/'main_input_terminals_v29.step.py');v29=importlib.util.module_from_spec(spec);spec.loader.exec_module(v29);m=v29.m
WIRE_D=3.2512;WIRE_R=WIRE_D/2;LUG_SEAT=3.5;LUG_T=.9779;WIRE_Z=LUG_SEAT+2.8067
V_APEX=WIRE_Z-WIRE_R*math.sqrt(2);LID_TOP=13.5;BASE_TOP=.7+2.6
ROWS=[('J204',7,-15,-1),('J205',7,-28,-1),('J206',93,-15,1),('J207',93,-28,1)]

def mirror_side(s,right):return Pos(100,-43,0)*Rot(0,0,180)*s if right else s
def lug_local():return Rot(0,0,90)*Rot(90,0,0)*import_step(S/'c-130191-c-3d.stp')
def lug(ref,x,y,side,angle=0):
 s=Pos(x,y,LUG_SEAT)*Rot(0,0,(180 if side>0 else 0)+angle)*lug_local()
 return m.tag(s,ref+'_TE130191_OEM_C_A3_DIMENSION_CHECKED_UNCRIMPED',(.76,.78,.80))
def m5_nut():
 # DIN934 H4, AF8. Smooth >=major-diameter bore is an assembly envelope,
 # not a helical thread/strength model. Catalog ISO4032 H4.7 was not substituted.
 s=extrude(RegularPolygon(8/math.sqrt(3),6),amount=4)-m.hole_z(0,0,-.1,5.05,4.2)
 return s
def washer(d,D,h):return m.hole_z(0,0,0,D,h)-m.hole_z(0,0,-.1,d,h+.2)
def left_base(wire_d=WIRE_D):
 apex=WIRE_Z-wire_d/2*math.sqrt(2)
 s=m.box_at(-14,-39,-7.6,8,35,WIRE_Z+7.6)
 s+=m.box_at(-6,-35.5,.7,20.5,28,2.6)
 for y in [-15,-28]:
  s-=m.box_at(1.8,y-5.2,.6,10.4,10.4,2.9)
  f=Face(Wire.make_polygon([(-14.1,y-4,apex+4),(-14.1,y,apex),(-14.1,y+4,apex+4)],close=True))
  s-=extrude(f,amount=5.6,dir=(1,0,0))
  s-=m.hole_x(-8.5,y,WIRE_Z,6.4,2.6)
 for y in [-9,-34]:s-=m.hole_z(-10,y,-8,3.4,16)
 return m.tag(s,'MC02_V30_PEEK450G_V_GROOVE_AND_TERMINAL_GUIDE_LEFT',(.76,.69,.49))
def left_cover(wire_d=WIRE_D):
 # Fixed cover/root datums and wire axis. Groove/aperture sizes form a matched
 # digital size family; three passing models do NOT qualify one fixed clamp
 # over all cable tolerances. Actual clamp force/compression remains open.
 zflat=WIRE_Z+wire_d/2
 s=m.box_at(-14,-39,zflat,8,35,LID_TOP-zflat)
 s+=m.box_at(-6,-35.5,BASE_TOP,20.5,28,LID_TOP-BASE_TOP)
 for y in [-15,-28]:
  s-=m.box_at(-8.5,y-5.5,3.0,21,11,8.5)
  s-=m.hole_x(-8.5,y,WIRE_Z,6.4,2.6)
 for y in [-9,-34]:s-=m.hole_z(-10,y,6,3.4,12)
 return m.tag(s,'MC03_V30_PEEK450G_REMOVABLE_TWO_POLE_COVER_LEFT',(.55,.46,.28))
def wire_segment(ref,x,y,side,d=WIRE_D):
 # The first .5 mm beyond the OEM barrel inlet is bare stripped conductor;
 # no fake solid-copper diameter is used for resistance or mass.
 end=x+side*14.0208;zz=WIRE_Z
 start=min(end+side*.5,end+side*40)
 s=m.hole_x(start,y,zz,d,39.5)
 return m.tag(s,ref+'_55A0111_10_9_LOCAL_39p5mm_JACKET_ENVELOPE',(.85,.85,.78))
def bare_segment(ref,x,y,side):
 end=x+side*14.0208
 s=m.hole_x(min(end,end+side*.5),y,WIRE_Z,2.8702,.5)
 return m.tag(s,ref+'_STRIPPED_BUNDLE_MAX_ENVELOPE_NO_SOLID_COPPER_MASS_CREDIT',(.69,.39,.19))
def clamp_fasteners():
 p=[]
 for x in [-10,110]:
  for y in [-9,-34]:
   stem=f'M3_CLAMP_{x}_{y}'
   p.append(m.tag(Pos(x,y,LID_TOP+.5)*import_step(S/'iso4762_socket_head_cap_screw_m3x30.step'),stem+'_ISO4762_M3X30_CATALOG_REFERENCE',(.48,.51,.54)))
   p.append(m.tag(Pos(x,y,-14.5)*import_step(S/'iso4032_hex_nut_m3.step'),stem+'_ISO4032_M3_CATALOG_REFERENCE',(.48,.51,.54)))
   for z in [LID_TOP,-12.1]:p.append(m.tag(Pos(x,y,z)*washer(3.2,7,.5),stem+f'_ISO7089_WASHER_0p5_REF_{z}',(.48,.51,.54)))
 return p
def gen_step():
 lock=json.loads((HERE/'LUG_SOURCE_LOCK_V30.json').read_text())
 for rel,h in lock.items():assert hashlib.sha256((A/rel).read_bytes()).hexdigest()==h,'SOURCE_DRIFT '+rel
 parent=v29.gen_step();p=list(parent.children);p=p[:5]+p[9:]
 for right in [False,True]:
  for f in [left_base,left_cover]:
   s=mirror_side(f(),right);s.label=s.label.replace('LEFT','RIGHT') if right else s.label;p.append(s)
 for ref,x,y,side in ROWS:
  l=lug(ref,x,y,side);p.append(l)
  w=m.tag(washer(5.3,10,1),ref+'_ETTINGER00305059_M5_WASHER_REFERENCE',(.58,.62,.65))
  n=m.tag(m5_nut(),ref+'_HPC_SHN5BRB_M5_NUT_SMOOTH_THREAD_REFERENCE',(.69,.56,.24))
  # Fixed ring-top datum -> washer bottom -> nut bottom, represented as source joints.
  RigidJoint('washer_seat',l,Location((x,y,LUG_SEAT+LUG_T)));RigidJoint('bottom',w,Location((0,0,0)))
  l.joints['washer_seat'].connect_to(w.joints['bottom']);RigidJoint('nut_seat',w,Location((x,y,LUG_SEAT+LUG_T+1)));RigidJoint('bottom',n,Location((0,0,0)));w.joints['nut_seat'].connect_to(n.joints['bottom'])
  p.extend([w,n,wire_segment(ref,x,y,side),bare_segment(ref,x,y,side)])
 p.extend(clamp_fasteners())
 return Compound(label='WP10_V30_LUG_AND_LOCAL_WIRE_CANDIDATE__HOST_AND_CLAMP_LOAD_OPEN',children=p)
