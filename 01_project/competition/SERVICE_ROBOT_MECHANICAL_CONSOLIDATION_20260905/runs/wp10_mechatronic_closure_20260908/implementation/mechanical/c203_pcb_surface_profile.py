"""Nominal copper/mask surface profile; finished bores, not fabrication mass."""
from pathlib import Path
import json,math,hashlib,sys
A=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(A/'tools'))
from c203_surface_source_contract_v19 import validate_profile
def definition():
 c=json.loads((A/'mechanical/C203_SURFACE_PROFILE_V19.json').read_text())
 assert all(hashlib.sha256((A/p).read_bytes()).hexdigest()==h for p,h in c['inputs'].items())
 validate_profile(c)
 return c
def on_layer(p,layer):return layer in p['layers'] or ('*.Cu' if layer.endswith('.Cu') else '*.Mask') in p['layers']
def distance_segment(q,a,b):
 dx,dy=b[0]-a[0],b[1]-a[1];den=dx*dx+dy*dy;assert den>0
 t=max(0.,min(1.,((q[0]-a[0])*dx+(q[1]-a[1])*dy)/den))
 return math.hypot(q[0]-a[0]-t*dx,q[1]-a[1]-t*dy)
def copper_at(c,layer,q):
 if any(p['pin'] and on_layer(p,layer) and math.dist(q,p['local_xy_mm'])<p['diameter_mm']/2 for p in c['pads']):return True
 return layer=='B.Cu' and any(distance_segment(q,t['start_local_mm'],t['end_local_mm'])<t['width_mm']/2 for t in c['back_tracks'])
def aperture_at(c,layer,q):return any(on_layer(p,layer) and math.dist(q,p['local_xy_mm'])<p['diameter_mm']/2 for p in c['pads'])
def surface_at(c,side,q):
 assert side in ['F','B']
 if not(c['board_y_mm'][0]<=q[0]<=c['board_y_mm'][1] and c['board_z_mm'][0]<=-50-q[1]<=c['board_z_mm'][1]):return None
 if any(math.dist(q,h['local_xy_mm'])<h['finished_drill_mm']/2 for h in c['holes']):return None
 f=c['faces_S_mm'];has_cu=copper_at(c,side+'.Cu',q);open_mask=aperture_at(c,side+'.Mask',q)
 if side=='F':return (f['front_exposed_copper_x'] if has_cu else f['core_front_x'])-(0 if open_mask else c['layers_mm']['F.Mask'])
 assert side=='B';return (f['rear_exposed_copper_x'] if has_cu else f['core_back_x'])+(0 if open_mask else c['layers_mm']['B.Mask'])
def make():
 from build123d import Box,Cylinder,Pos,Rot,Color,Compound
 c=definition();f=c['faces_S_mm'];layers=c['layers_mm']
 def slab(a,b):return Pos((a+b)/2,sum(c['board_y_mm'])/2,sum(c['board_z_mm'])/2)*Box(b-a,c['board_y_mm'][1]-c['board_y_mm'][0],c['board_z_mm'][1]-c['board_z_mm'][0])
 def disk(a,b,q,r):return Pos((a+b)/2,q[0],-50-q[1])*Rot(0,90,0)*Cylinder(r,b-a)
 def union(parts):
  if not parts:return None
  s=parts[0]
  for x in parts[1:]:s=s+x
  return s
 def cut(s,tool):return s if tool is None else s-tool
 def drill(s):
  if s is None or abs(s.volume)<1e-10:return None
  for h in c['holes']:s=s-disk(-8,-4,h['local_xy_mm'],h['finished_drill_mm']/2)
  return s
 def copper(layer,a,b):
  parts=[disk(a,b,p['local_xy_mm'],p['diameter_mm']/2) for p in c['pads'] if p['pin'] and on_layer(p,layer)]
  if layer=='B.Cu':
   for t in c['back_tracks']:
    p,q=t['start_local_mm'],t['end_local_mm'];L=math.dist(p,q);w=t['width_mm'];angle=math.degrees(math.atan2(-(q[1]-p[1]),q[0]-p[0]))
    rect=Pos((a+b)/2,(p[0]+q[0])/2,-50-(p[1]+q[1])/2)*Rot(angle,0,0)*Box(b-a,L,w)
    parts += [rect,disk(a,b,p,w/2),disk(a,b,q,w/2)]
  return union(parts)
 def openings(layer,a,b):return union([disk(a,b,p['local_xy_mm'],p['diameter_mm']/2) for p in c['pads'] if on_layer(p,layer)])
 parts=[]
 def append(s,label,color):
  if s is None or abs(s.volume)<1e-10:return
  assert s.is_valid,label
  s.label=label;s.color=Color(*color);parts.append(s)
 append(drill(slab(f['core_front_x'],f['core_back_x'])),'C203_CORE_FINISHED_BORE_ENVELOPE',(.35,.45,.28))
 append(drill(copper('F.Cu',f['front_exposed_copper_x'],f['core_front_x'])),'C203_FRONT_WIRE_ANNULI',(.72,.45,.16))
 append(drill(copper('B.Cu',f['core_back_x'],f['rear_exposed_copper_x'])),'C203_BACK_TRACES_AND_LANDS',(.72,.45,.16))
 for side,core_face,outer_copper,sign in [('F',f['core_front_x'],f['front_exposed_copper_x'],-1),('B',f['core_back_x'],f['rear_exposed_copper_x'],1)]:
  th=layers[side+'.Mask']
  a,b=sorted([core_face,core_face+sign*th]);core_mask=cut(slab(a,b),copper(side+'.Cu',a-.01,b+.01));core_mask=cut(core_mask,openings(side+'.Mask',a-.01,b+.01))
  append(drill(core_mask),'C203_'+side+'_MASK_ON_CORE',(.08,.30,.18))
  a,b=sorted([outer_copper,outer_copper+sign*th]);cu_mask=copper(side+'.Cu',a,b);cu_mask=cut(cu_mask,openings(side+'.Mask',a-.01,b+.01)) if cu_mask is not None else None
  append(drill(cu_mask),'C203_'+side+'_MASK_ON_COPPER',(.08,.30,.18))
 result=Compound(children=parts);result.label='C203_NOMINAL_SURFACE_PROFILE__BARRELS_AND_TOLERANCE_UNQUALIFIED'
 return result
