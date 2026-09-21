"""Space allocation candidate. No physical PCB or OEM connector is claimed."""
from pathlib import Path
import json, math
from build123d import Box, Cylinder, Pos, Compound, Color, Solid
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakeFace
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipe
from OCP.GC import GC_MakeArcOfCircle
from OCP.gp import gp_Pnt, gp_Circ, gp_Ax2, gp_Dir

PARAMS=Path(__file__).resolve().parents[1]/'inputs/BOARD_RESERVATION.json'
def path_shape(x0,x1,label):
    # Two tangent 90-deg bends, radius 2 mm. All geometry is a functional proxy.
    r=float(json.loads(PARAMS.read_text(encoding='utf-8'))['route_radius_mm']);assert r==2.; sign=1 if x1>x0 else -1
    pts=[(x0,-20,5),(x0,-19,5),(x0+sign*r,-17,5),(x1-sign*r,-17,5),(x1,-15,5)]
    w=BRepBuilderAPI_MakeWire()
    def line(a,b):w.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(*a),gp_Pnt(*b)).Edge())
    def arc(a,m,b):w.Add(BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(gp_Pnt(*a),gp_Pnt(*m),gp_Pnt(*b)).Value()).Edge())
    line(pts[0],pts[1]);arc(pts[1],(x0+sign*(r-r/math.sqrt(2)),-19+r/math.sqrt(2),5),pts[2])
    line(pts[2],pts[3]);arc(pts[3],(x1-sign*(r-r/math.sqrt(2)),-15-r/math.sqrt(2),5),pts[4])
    line(pts[4],(x1,-13,5))
    circle=BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(*pts[0]),gp_Dir(0,1,0)),1.5)).Edge()).Wire()
    pipe=BRepOffsetAPI_MakePipe(w.Wire(),BRepBuilderAPI_MakeFace(circle).Face());pipe.Build()
    assert pipe.IsDone()
    s=Solid(pipe.Shape());s.label=label;s.color=Color('gold')
    return s

def gen_step():
    p=json.loads(PARAMS.read_text(encoding='utf-8'))
    pcb=Pos(-100,-48,-0.8)*Box(60,40,1.6)
    for x,y,z in p['PCB_hole_centers_S_mm']:pcb=pcb-Pos(x,y,-.8)*Cylinder(1.6,3.2)
    pcb.label='R3_PCB_60x40_DESIGN_RESERVATION_NO_MPN';pcb.color=Color('green')
    height=Pos(-100,-48,9)*Box(60,40,18);height.label='COMPONENT_HEIGHT_ENVELOPE_NOT_PHYSICAL';height.color=Color(0.4,0.75,0.65,0.28)
    children=[pcb,height]
    for q in p['reserved_ports']:
        s=Pos(*q['center'])*Box(*q['size']);s.label=q['name']+'_FUNCTIONAL_PORT_NOT_OEM';s.color=Color('navy');children.append(s)
    children += [path_shape(-118,-108,'ARM_LOCAL_FUNCTIONAL_ROUTE'),path_shape(-80,-104,'HOST_LOCAL_FUNCTIONAL_ROUTE')]
    return Compound(children=children,label='B601_INTERFACE_SLOT_R3_DESIGN_ONLY')
