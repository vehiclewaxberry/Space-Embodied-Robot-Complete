"""Retained lower clamp and source-defined maximum lacing cross-sections, S/mm."""
from pathlib import Path
import json,hashlib,math
from build123d import Box,Pos,Color,Axis,Edge,Wire,Face,extrude,fillet
from cadgen.step_scene import import_step
A=Path(__file__).resolve().parents[1]
def config():
 c=json.loads((A/'power/CAP_HARNESS_RETENTION_V21.json').read_text())
 for path,key in [(c['parent_plan'],'parent_plan_sha256'),(c['wire_definition'],'wire_definition_sha256')]:
  assert hashlib.sha256((A/path).read_bytes()).hexdigest()==c[key]
 return c
def block(x0,x1,y0,y1,z0,z1):return Pos((x0+x1)/2,(y0+y1)/2,(z0+z1)/2)*Box(x1-x0,y1-y0,z1-z0)
def make(name):
 c=config();d=c['design'];w=json.loads((A/c['wire_definition']).read_text())
 r=w['wire']['max_insulation_D_mm']/2;top=d['wire_z_mm']-r;bottom=top-d['saddle_depth_mm']
 x0,x1=d['saddle_x_mm'];yc=d['saddle_center_abs_y_mm'];half=d['saddle_width_y_mm']/2
 if name=='LOWER':
  old=c['parent_lower'];p=Path(old['step_path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==old['source_sha256']
  assert old['T_S_step']==[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
  s=import_step(str(p))
  for sign in [-1,1]:
   def mirrored_block(xx0,xx1,yy0,yy1,zz0,zz1):
    return block(xx0,xx1,*sorted([sign*yy0,sign*yy1]),zz0,zz1)
   saddle=mirrored_block(x0,x1,yc-half,yc+half,bottom,top)
   saddle=fillet(saddle.edges().filter_by(Axis.X),d['saddle_edge_radius_mm'])
   arm=mirrored_block(*d['arm_x_mm'],*d['arm_abs_y_mm'],*d['arm_z_mm'])
   drop=mirrored_block(x0,x1,*d['drop_abs_y_mm'],bottom,d['arm_z_mm'][1])
   bridge=mirrored_block(*d['bridge_x_mm'],yc+half-.5,d['drop_abs_y_mm'][1],bottom+.4,top-.4)
   # Shallow under-saddle channel locates the tape; support top remains intact.
   # Channel depth is cut from the lower surface only, between the X shoulders.
   slot=mirrored_block(*d['tie_channel_x_mm'],yc-half-1,yc+half+1,bottom-1,bottom+d['channel_depth_mm'])
   saddle=saddle-slot
   s=s+arm+drop+bridge+saddle
  assert s.is_valid and len(s.solids())==1,'Integral support must remain a connected valid solid'
  s.color=Color(.72,.62,.41);s.label='C203_LOWER_B_V21__INTEGRAL_SADDLES_PEEK_CANDIDATE';return s
 sign=-1 if name=='PLUS' else 1;assert name in ['PLUS','MINUS']
 # Inner convex loop: tangent to max wire, square saddle side/bottom envelope.
 # Rounded physical saddle edges sit inside this envelope. Channel makes .45 mm
 # vertical clearance beneath the loop; installed drape/knot is not modeled.
 a=half;ny=2*a*r/(a*a+r*r);nz=(a*a-r*r)/(a*a+r*r)
 y=sign*yc;z=d['wire_z_mm'];tx=d['tie_center_x_mm']-c['lacing']['width_min_max_mm'][1]/2
 right=(tx,y+r*ny,z+r*nz);left=(tx,y-r*ny,z+r*nz)
 points=[left,(tx,y-a,top),(tx,y-a,bottom),(tx,y+a,bottom),(tx,y+a,top),right]
 edges=[Edge.make_three_point_arc(right,(tx,y,z+r),left)]
 edges += [Edge.make_line(u,v) for u,v in zip(points,points[1:])]
 inner=Wire(edges);outer=inner.offset_2d(c['lacing']['thickness_min_max_mm'][1])
 fi=Face(inner);fo=Face(outer);assert fo.area>fi.area
 s=extrude(fo-fi,amount=c['lacing']['width_min_max_mm'][1],dir=(1,0,0))
 assert s.is_valid and len(s.solids())==1
 s.color=Color(.90,.89,.80);s.label='C203_LACE_'+name+'__MAX_SECTION_LOOP_KNOT_NOT_MODELED';return s

