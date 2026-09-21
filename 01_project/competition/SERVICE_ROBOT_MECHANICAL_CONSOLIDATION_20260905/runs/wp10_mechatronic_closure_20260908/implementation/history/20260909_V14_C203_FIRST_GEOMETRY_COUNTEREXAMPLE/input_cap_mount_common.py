"""C203 nominal horizontal fixture. Dimensions in S; hardware uses local +Z shaft."""
from pathlib import Path
import json,hashlib
from build123d import Box,Cylinder,Pos,Rot,Plane,Color,RegularPolygon,extrude
from cadgen.step_scene import import_step
A=Path(__file__).resolve().parents[1]
def config():return json.loads((A/'mechanical/INPUT_CAP_MOUNT_DESIGN.json').read_text())
def block(x0,x1,y0,y1,z0,z1):return Pos((x0+x1)/2,(y0+y1)/2,(z0+z1)/2)*Box(x1-x0,y1-y0,z1-z0)
def cz(r,z0,z1,x=0,y=0):return Pos(x,y,(z0+z1)/2)*Cylinder(r,z1-z0)
def cx(r,x0,x1,y=0,z=-50):return Pos((x0+x1)/2,y,z)*Rot(0,90,0)*Cylinder(r,x1-x0)
def make(name):
 c=config();centers=c['band_centers_x_mm'];nomR=c['nominal_D_L_mm'][0]/2;rin,rout=[q/2 for q in c['clamp_ID_OD_mm']]
 if name=='BODY':s=cx(nomR,-7-c['nominal_D_L_mm'][1],-7);color=(.16,.19,.23)
 elif name=='PCB':
  s=block(*c['board_x_mm'],*c['board_y_mm'],*c['board_z_mm'])
  for p in c['pads']:s=s-cx(c['pad_drill_D_mm']/2,-8,-4,p['S_face_mm'][1],-50)
  for y,z in c['board_holes_yz_mm']:s=s-cx(1.7,-8,-4,y,z)
  color=(.18,.43,.28)
 elif name=='CARRIER':
  s=None
  for x in centers:
   ring=(cx(rout,x-3,x+3)-cx(rin,x-4,x+4)) & block(x-4,x+4,-30,30,-50,-20)
   ring=ring+block(x-3,x+3,-26.5,-17.5,-50,-15.5)+block(x-3,x+3,17.5,26.5,-50,-15.5)+block(x-5,x+5,-27.5,27.5,-15.5,-11.5)
   for y in [-22.5,22.5]:ring=ring-cz(1.7,-16,-11,x,y)-cz(1.5,-50.1,-41.5,x,y)
   s=ring if s is None else s+ring
  # Rails join both yokes and the terminal-board edge frame, clear of the can.
  for y0,y1 in [(-24,-18),(18,24)]:s=s+block(-51,-7,y0,y1,-35,-29)
  frame=block(-14,-7,-25,25,-74,-26)-block(-15,-6,-16.5,16.5,-66.5,-33.5)
  for y,z in c['board_holes_yz_mm']:frame=frame-cx(1.5,-13.9,-6.9,y,z)
  s=s+frame;color=(.70,.59,.38)
 elif name.startswith('LOWER_'):
  x=centers[0 if name.endswith('A') else 1]
  s=((cx(rout,x-3,x+3)-cx(rin,x-4,x+4)) & block(x-4,x+4,-30,30,-80,-50))+block(x-3,x+3,-26.5,-17.5,-54,-50)+block(x-3,x+3,17.5,26.5,-54,-50)
  for y in [-22.5,22.5]:s=s-cz(1.7,-55,-49,x,y)
  color=(.75,.65,.43)
 elif name.startswith('LINER_'):
  x=centers[0 if '_A_' in name else 1];s=cx(rin,x-3,x+3)-cx(nomR,x-4,x+4)
  s=s & (block(x-4,x+4,-30,30,-50,-20) if name.endswith('TOP') else block(x-4,x+4,-30,30,-80,-50));color=(.91,.84,.62)
 elif name=='DECK':
  r=c['deck_source'];assert hashlib.sha256(Path(r['step_path']).read_bytes()).hexdigest()==r['source_sha256'];T=r['T_S_step']
  s=Plane(origin=tuple(T[i][3] for i in range(3)),x_dir=tuple(T[i][0] for i in range(3)),z_dir=tuple(T[i][2] for i in range(3))).location*import_step(r['step_path'])
  for x,y in c['deck_holes_xy_mm']:s=s-cz(1.7,-12,-8,x,y)
  color=(.50,.57,.64)
 elif name.startswith('SCREW_'):
  L=float(name.split('_')[-1]);s=cz(1.5,0,L)+cz(2.75,-3,0)
  s=s-Pos(0,0,-3.1)*extrude(RegularPolygon(1.15,6),amount=1.6);color=(.28,.31,.34)
 elif name=='WASHER':s=cz(3.5,0,.5)-cz(1.6,-1,1.5);color=(.52,.54,.58)
 elif name=='NUT':s=extrude(RegularPolygon(5.5/(3**.5),6),amount=2.4)-cz(1.5,-1,3.4);color=(.40,.43,.47)
 else:raise ValueError(name)
 s.color=Color(*color);s.label='WP10_C203_'+name+'__NOMINAL_GEOMETRY_THERMAL_AND_RETENTION_OPEN';return s
