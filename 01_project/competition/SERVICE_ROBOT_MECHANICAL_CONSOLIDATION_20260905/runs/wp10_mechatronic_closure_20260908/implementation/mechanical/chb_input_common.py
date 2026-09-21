"""CHB terminal assembly in S mm. Project geometry, no qualified threads."""
from pathlib import Path
import json
from build123d import Box,Cylinder,Pos,Color,RegularPolygon,extrude
A=Path(__file__).resolve().parents[1]
def config():return json.loads((A/'power/CHB_INPUT_DEFINITION.json').read_text())
def cz(r,a,b,x=0,y=0):return Pos(x,y,(a+b)/2)*Cylinder(r,b-a)
def make(kind):
 c=config()
 if kind=='pcb':
  x0,y0,z0,x1,y1,z1=c['board_bounds_S_mm'];s=Pos((x0+x1)/2,(y0+y1)/2,(z0+z1)/2)*Box(x1-x0,y1-y0,z1-z0)
  for p in c['pads']:s=s-cz(p['drill_mm']/2,z0-1,z1+1,*p['S_xy_mm'])
  for x,y in c['mount_S_xy_mm']:s=s-cz(1.7,z0-1,z1+1,x,y)
  color=(.12,.4,.28)
 elif kind=='spacer':
  # local bottom=0; stem seats on the OEM metal insert in its recessed mouth.
  h=c['spacer_z_mm'][1]-c['spacer_z_mm'][0];od,inner=c['spacer_stem_OD_ID_mm'];flange=c['spacer_flange_OD_mm'];shoulder=c['spacer_flange_start_above_seat_mm']
  assert 0<inner<od<flange and 0<shoulder<h
  s=(cz(od/2,0,h)+cz(flange/2,shoulder,h))-cz(inner/2,-1,h+1);color=(.76,.64,.42)
 elif kind=='screw':
  # local underhead=0, shaft toward -Z; no helical representation.
  s=cz(1.5,-c['screw_underhead_length_mm'],0)+cz(2.75,0,3)
  s=s-Pos(0,0,1.5)*extrude(RegularPolygon(1.15,6),amount=1.6);color=(.35,.37,.4)
 else:raise ValueError(kind)
 s.label='WP10_CHB_INPUT_'+kind.upper()+'__PROJECT_CANDIDATE';s.color=Color(*color);return s
