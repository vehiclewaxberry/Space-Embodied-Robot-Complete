"""Actual dependent source edits for the CHB installation window, S frame mm."""
from pathlib import Path
import math,json
from build123d import Pos,Plane,Cylinder,Edge,Wire,Face,Vector,Solid,Compound,Color
from cadgen.step_scene import import_step
from fixed_heat_common import assembly as heat_assembly

A=Path(__file__).resolve().parents[1]
V6=A.parents[1]/'wp09_interfaces_20260907_1525/candidate/v6parts'
DUAL_IDS=[f'CLAMP_DUAL_{i}_{tag}' for i in [0,1] for tag in ['BN','BW','TN','TW']]+[
 'CLAMP_DUAL_BASE','CLAMP_DUAL_LID','POST_DUAL_0','POST_DUAL_1','TIEROD_DUAL_0','TIEROD_DUAL_1']

def upper_deck():
    s=import_step(str(V6/'upper_equipment_deck_B.step'))
    for y in [36,69]:s=s-Pos(100,y,-10)*Cylinder(1.7,20)
    s.label='upper_equipment_deck_B__DUAL_NEW_BORES_OLD_BORES_RETAINED';return s

def dual_parts():
    out={}
    for key in DUAL_IDS:
        s=Pos(0,-10,0)*import_step(str(V6/(key+'.step')));s.label=key;out[key]=s
    return out

class Route:
    def __init__(self,start):self.start=Vector(start);self.p=self.start;self.edges=[];self.arcs=[]
    def line(self,end):
        q=Vector(end)
        if (q-self.p).length>1e-9:self.edges.append(Edge.make_line(self.p,q))
        self.p=q
    def arc(self,center,normal,angle):
        center=Vector(center);n=Vector(normal).normalized();v=self.p-center
        def rot(a):return v*math.cos(a)+n.cross(v)*math.sin(a)+n*n.dot(v)*(1-math.cos(a))
        end=center+rot(angle);mid=center+rot(angle/2)
        self.edges.append(Edge.make_three_point_arc(self.p,mid,end))
        self.arcs.append(dict(radius_mm=v.length,angle_rad=angle,start=list(self.p),end=list(end),center=list(center)))
        self.p=end
    def offset(self,tangent,shift,delta,r=21.):
        # Equal/opposite circular arcs give a parallel offset with identical
        # endpoint tangent and radius r; avoids two impossible 10mm R21 corners.
        u=Vector(tangent).normalized();v=Vector(shift).normalized();assert abs(u.dot(v))<1e-10
        theta=math.acos(1-delta/(2*r));n=u.cross(v)
        self.arc(self.p+v*r,n,theta)
        tangent2=u*math.cos(theta)+v*math.sin(theta)
        toward2=n.cross(tangent2)
        self.arc(self.p-toward2*r,n,-theta)
    def solid(self,name):
        wire=Wire(self.edges);profile=Wire.make_circle(3,Plane(origin=self.start,z_dir=self.edges[0].tangent_at(0)))
        s=Solid.sweep(Face(profile),wire);s.label=name+'_STATIC_BUNDLE_OD6';s.color=Color(.85,.25,.08) if name=='PROP_PWR' else Color(.12,.4,.85)
        return s,dict(radius_min_mm=min(x['radius_mm'] for x in self.arcs),arcs=self.arcs,
          centerline_length_mm=wire.length,start=list(self.start),end=list(self.p),
          endpoint_binding=False,cut_length_mm=None,role='FUNCTIONAL_ENVELOPE_NOT_CUT_WIRE')

def route(name):
    if name=='PROP_PWR':
        r=Route((-60,69,45));r.line((-24,69,45));r.offset((1,0,0),(0,-1,0),10)
        r.line((123,59,45));r.arc((123,59,24),(0,1,0),math.pi/2)
        r.offset((0,0,-1),(0,1,0),10);r.line((144,69,-44))
        r.arc((144,48,-44),(-1,0,0),math.pi/2)
    elif name=='PROP_DATA':
        r=Route((78,-15,45));r.offset((0,1,0),(-1,0,0),6)
        r.line((72,25,45));r.arc((93,25,45),(0,0,-1),math.pi/2)
        r.line((119,46,45));r.arc((119,46,24),(0,1,0),math.pi/2)
        r.offset((0,0,-1),(0,1,0),10);r.line((140,56,-45))
    else:raise ValueError(name)
    return r.solid(name)

def assembly():
    children=[heat_assembly(),upper_deck(),*dual_parts().values(),route('PROP_PWR')[0],route('PROP_DATA')[0]]
    return Compound(label='WP10_FIXED_THERMAL_BAY_WITH_DECK_CLAMP_AND_ROUTES',children=children)
