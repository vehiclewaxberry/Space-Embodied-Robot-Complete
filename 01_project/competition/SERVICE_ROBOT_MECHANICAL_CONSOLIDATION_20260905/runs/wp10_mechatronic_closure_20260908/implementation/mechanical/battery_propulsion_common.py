"""Actual routing and support changes for the existing battery-bay candidate."""
from pathlib import Path
import json,hashlib
from build123d import Box,Pos,Cylinder,Plane,Wire,Face,Solid,Color
from cadgen.step_scene import import_step
from heat_layout_relocation import Route
A=Path(__file__).resolve().parents[1]
def config():return json.loads((A/'mechanical/BATTERY_PROPULSION_ROUTING.json').read_text())
def make_route(name):
    c=config()['routes'][name];r=Route(c['start'])
    for q in c['commands']:
        if 'line' in q:r.line(q['line'])
        elif 'offset' in q:r.offset(**q['offset'])
        else:r.arc(**q['arc'])
    assert min(a['radius_mm'] for a in r.arcs)>=c['minimum_bend_radius_mm']-1e-9
    assert max(abs(a-b) for a,b in zip(r.p,c['expected_end']))<1e-8
    wire=Wire(r.edges);profile=Wire.make_circle(c['outer_diameter_mm']/2,Plane(origin=r.start,z_dir=r.edges[0].tangent_at(0)))
    s=Solid.sweep(Face(profile),wire);s.label=name+'__BATTERY_CORRIDOR_FUNCTIONAL_NO_PINS_OR_CUT_LENGTH';s.color=Color(.85,.25,.08) if name=='PROP_PWR_ROUTE' else Color(.12,.4,.85)
    return s
def support(name):
    c=config();d=c['dual_clamp']
    if name in ['BASE','LID']:
        x0,x1=d['x_mm'];y0,y1=d['y_mm'];z0,z1=d[name.lower()+'_z_mm'];s=Pos((x0+x1)/2,(y0+y1)/2,(z0+z1)/2)*Box(x1-x0,y1-y0,z1-z0)
        for y,z in d['bore_centers_yz_mm']:s=s-Plane(origin=((x0+x1)/2,y,z),z_dir=(1,0,0)).location*Cylinder(d['bore_diameter_mm']/2,x1-x0+2)
        for x,y in d['stud_xy_mm']:s=s-Pos(x,y,(z0+z1)/2)*Cylinder(d['clearance_bore_diameter_mm']/2,z1-z0+2)
    elif name=='POST':
        lo,hi=d['post_z_mm'];h=hi-lo;s=Pos(0,0,h/2)*(Cylinder(d['post_outer_diameter_mm']/2,h)-Cylinder(d['post_inner_diameter_mm']/2,h+2))
    elif name=='ROD':
        lo,hi=d['rod_z_mm'];h=hi-lo;s=Pos(0,0,h/2)*Cylinder(d['rod_nominal_diameter_mm']/2,h)
    elif name=='DECK':
        p=A/c['deck_baseline'];assert hashlib.sha256(p.read_bytes()).hexdigest()==c['deck_baseline_sha256'];s=import_step(str(p))
        for x,y in d['stud_xy_mm']:s=s-Pos(x,y,-10)*Cylinder(d['clearance_bore_diameter_mm']/2,8)
    else:raise ValueError(name)
    s.label='WP10_BATTERY_DUAL_'+name+'__PRELOAD_AND_MATERIAL_PENDING';return s
