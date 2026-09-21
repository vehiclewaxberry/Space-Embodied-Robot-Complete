"""Editable project mechanical parts, in board XY-mm coordinates (KiCad y negated)."""
from pathlib import Path
import json
from build123d import Box,Cylinder,Pos,Rot,Align,Color,Compound
HERE=Path(__file__).resolve().parent
A=HERE.parent

def box_at(x,y,z,l,w,h):return Pos(x+l/2,y+w/2,z+h/2)*Box(l,w,h)
def hole_z(x,y,z,d,h):return Pos(x,y,z)*Cylinder(d/2,h,align=(Align.CENTER,Align.CENTER,Align.MIN))
def hole_y(x,y,z,d,h):return Pos(x,y,z)*Rot(-90,0,0)*Cylinder(d/2,h,align=(Align.CENTER,Align.CENTER,Align.MIN))
def hole_x(x,y,z,d,h):return Pos(x,y,z)*Rot(0,90,0)*Cylinder(d/2,h,align=(Align.CENTER,Align.CENTER,Align.MIN))
def tag(s,label,color):s.label=label;s.color=Color(*color);return s
AL=(.69,.73,.79);PLASTIC=(.17,.21,.24)

def main_carrier(width=132.,thickness=4.):
    s=box_at(50-width/2,-86,-7.6-thickness,width,92,thickness)
    for x,y in [(4,-4),(96,-4),(4,-76),(96,-76)]:
        s+=hole_z(x,y,-7.6,7.,6.)
        s-=hole_z(x,y,-13.,3.2,13.)
    for x in [-10,110]:
        for y in [-9,-34]:s-=hole_z(x,y,-13,3.4,7)
    # Continuous aluminum path: edge riser -> overhead bridge -> tab contact.
    s+=box_at(39.45,1,-7.6,40,5,39.6)
    s+=box_at(39.45,-14.597,27,40,20.597,5)
    s+=box_at(39.45,-14.597,3,40,5,29)
    s-=hole_y(59.45,-15,18.315,3.6,8)
    # Project-to-host slots not OEM holes; host interface remains unbound.
    for x in [-10,110]:
        for y in [-71,-51]:s-=hole_z(x,y,-13,3.4,7)
    return tag(s,'MC01_MAIN_CARRIER_MONOLITHIC_THERMAL_ARCH_6061',AL)

def terminal_retainer(x=-10.,cap=False,diameter=4.7):
    s=box_at(x-4,-39,2 if cap else -7.6,8,35,5 if cap else 9.6)
    for y in [-15,-28]:s-=hole_x(x-5,y,2,diameter,10)
    for y in [-9,-34]:s-=hole_z(x,y,-9,3.4,18)
    return tag(s,('MC03' if cap else 'MC02')+'_DUAL_WIRE_'+('CAP' if cap else 'BASE')+'_PEEK',PLASTIC)

def q201_reference():
    s=box_at(59.45-16.26/2,-20.1,3,16.26,5.3,21.46)
    s-=hole_y(59.45,-21,18.315,3.6,8)
    # Source-bounded reference body only. Not a lead-form manufacturing model.
    return tag(s,'REF_Q201_TO247_CATALOGUE_MAX_BODY_POSE_UNVERIFIED',(.08,.09,.11))

def q201_tim():
    s=box_at(59.45-18.26/2,-14.8,2,18.26,.203,23.46)
    s-=hole_y(59.45,-15,18.315,3.6,2)
    return tag(s,'MC04_TSP1800ST_PROJECT_CUT_0p203_UNCOMPRESSED',(.32,.50,.68))

def q201_shoulder():
    s=hole_y(59.45,-21.1,18.315,7.,1.)+hole_y(59.45,-20.1,18.315,3.4,5.7)
    s-=hole_y(59.45,-21.2,18.315,2.7,7.)
    return tag(s,'MC05_PEEK_M2p5_INSULATING_SHOULDER_NOT_QUALIFIED',(.89,.83,.62))

def board_reference():
    d=json.loads((A/'power/MAIN_INPUT_BOARD_DEFINITION_V26.json').read_text())
    s=box_at(0,-80,-1.6,100,80,1.6)
    for x,y in d['mounting_holes_mm']:s-=hole_z(x,-y,-2,3.2,3)
    for p in d['pads']:
        dx,dy=p['drill_mm'];x,y=p['xy_mm']
        if dx==0 or dy==0 or p['ref'].startswith('MH'):continue
        if abs(dx-dy)<1e-8:cut=hole_z(x,-y,-2,dx,3)
        else:
            assert dx>=dy
            cut=box_at(x-(dx-dy)/2,-y-dy/2,-2,dx-dy,dy,3)
            for off in [-(dx-dy)/2,(dx-dy)/2]:cut+=hole_z(x+off,-y,-2,dy,3)
        s-=cut
    return tag(s,'REF_V26_PCB_ACTUAL_DRILLS_PARTIAL_POPULATION',(.03,.30,.16))

def main_parts():
    parts=[main_carrier(),board_reference(),q201_reference(),q201_tim(),q201_shoulder()]
    for x in [-10,110]:
        for cap in [False,True]:parts.append(terminal_retainer(x,cap))
    d=json.loads((A/'power/MAIN_INPUT_BOARD_DEFINITION_V26.json').read_text())
    refs={r['ref']:r for r in d['refs']}
    sels=json.loads((A/'power/MAIN_BOARD_PASSIVE_SELECTION_V25.json').read_text())
    sels['C201']=json.loads((A/'power/TIMER_PASSIVE_SELECTION_V24.json').read_text())['C201']
    for ref in ['C201','C202','C211','C212','C213']:
        x,y=refs[ref]['position_mm'];l,w,h=sels[ref]['body_LWH_mm']
        parts.append(tag(box_at(x+2.5-l/2,-y-w/2,.5,l,w,h),'REF_'+ref+'_CATALOGUE_BODY_ONLY',(.65,.04,.04)))
    return parts

def propulsion_carrier():
    s=box_at(-58,-56,0,116,112,4)
    for x in [-48,48]:
        for y in [-46,46]:s-=hole_z(x,y,-1,3.4,6)
    return tag(s,'PC01_PROJECT_SIDE_CARRIER_NO_C_POD_OEM_HOLES',AL)

def propulsion_retainer(cap=False):
    s=box_at(-15,-10,6 if cap else 0,30,20,6)
    for x in [-6,6]:s-=hole_y(x,-11,6,6.4,22)
    for x in [-12,12]:s-=hole_z(x,0,-1,3.4,15)
    return tag(s,('PC03' if cap else 'PC02')+'_PROP_HARNESS_'+('CAP' if cap else 'BASE')+'_PEEK',PLASTIC)

def propulsion_parts():
    # Separate interface components in an exploded kit: no false OEM mating.
    return [propulsion_carrier(),Pos(0,75,0)*propulsion_retainer(),Pos(0,75,10)*propulsion_retainer(True)]
