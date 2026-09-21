"""PCB substrate, real pad positions and five selected film capacitor envelopes.

Partial mechanical model: semiconductors, resistor bodies, wires and heatsink
are intentionally not represented. This is not a populated-board assembly.
"""
from pathlib import Path
import json
from build123d import Box,Cylinder,Pos,Rot,Compound,Color,Align
A=Path(__file__).resolve().parents[1]
def gen_step():
 d=json.loads((A/'power/MAIN_INPUT_BOARD_DEFINITION_V25.json').read_text())
 board=Pos(50,-40,-.8)*Box(100,80,1.6)
 for x,y in d['mounting_holes_mm']:board-=Pos(x,-y,-2)*Cylinder(1.6,3,align=(Align.CENTER,Align.CENTER,Align.MIN))
 # All actual drilled pad holes are cut; slots use two semicircles + middle.
 holes={}
 for p in d['pads']:
  dx,dy=p['drill_mm'];x,y=p['xy_mm']
  if dx==0 or dy==0 or p['ref'].startswith('MH'):continue
  if abs(dx-dy)<1e-8:hole=Pos(x,-y,-2)*Cylinder(dx/2,3,align=(Align.CENTER,Align.CENTER,Align.MIN))
  else:
   # V25 selected THT bodies have in-plane rotation0, actual long axis horizontal.
   assert dx>=dy
   hole=Pos(x,-y,-.5)*Box(dx-dy,dy,3)
   for off in [-(dx-dy)/2,(dx-dy)/2]:hole+=Pos(x+off,-y,-2)*Cylinder(dy/2,3,align=(Align.CENTER,Align.CENTER,Align.MIN))
  board-=hole;holes[(p['ref'],p['pin'])]=hole
 board.label='PCB_100x80x1p6_WITH_ACTUAL_DRILLS_NO_COMPONENT_POPULATION_CREDIT';board.color=Color(.04,.27,.15)
 shapes=[board];refs={r['ref']:r for r in d['refs']}
 for p in d['pads']:
  if not p['pin']:continue
  x,y=p['xy_mm'];w,h=p['size_mm']
  # Copper is a footprint-size marker, not an exact mask/roundrect CAM solid.
  angle=refs.get(p['ref'],{}).get('rotation_deg',0)
  copper=Pos(x,-y,.025)*Rot(0,0,angle)*Box(w,h,.05)
  if (p['ref'],p['pin']) in holes:copper-=holes[(p['ref'],p['pin'])]
  copper.label=p['ref']+'_pad_'+p['pin']+'_DRILLED_COPPER_RECT_ENVELOPE';copper.color=Color(.75,.55,.15);shapes.append(copper)
 sels=json.loads((A/'power/MAIN_BOARD_PASSIVE_SELECTION_V25.json').read_text())
 sels['C201']=json.loads((A/'power/TIMER_PASSIVE_SELECTION_V24.json').read_text())['C201']
 for ref in ['C201','C202','C211','C212','C213']:
  x,y=refs[ref]['position_mm'];angle=refs[ref]['rotation_deg'];assert angle==0
  l,w,h=sels[ref]['body_LWH_mm']
  body=Pos(x+2.5,-y,h/2+.5)*Box(l,w,h)
  body.label=ref+'_'+sels[ref]['MPN']+'_NOMINAL_CATALOG_BODY_PROJECT_0p5_STANDOFF';body.color=Color(.65,.035,.035);shapes.append(body)
 return Compound(label='WP10_V25_PARTIAL_PCB_MECHANICAL_VIEW_NOT_INSTALLED_IN_WHOLE_SPACECRAFT',children=shapes)
