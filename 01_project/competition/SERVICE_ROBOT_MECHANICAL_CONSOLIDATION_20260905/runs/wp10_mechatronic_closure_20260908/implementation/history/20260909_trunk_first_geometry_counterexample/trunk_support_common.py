"""Four project split saddles, liners and nominal countersunk M3 fasteners."""
from pathlib import Path
import json,hashlib
from build123d import Box,Cylinder,Cone,Pos,Plane,Color
from cadgen.step_scene import import_step
A=Path(__file__).resolve().parents[1]
def config():return json.loads((A/'mechanical/TRUNK_SUPPORT_DESIGN.json').read_text())
def block(x0,x1,y0,y1,z0,z1):return Pos((x0+x1)/2,(y0+y1)/2,(z0+z1)/2)*Box(x1-x0,y1-y0,z1-z0)
def bore(r,h,x=0,y=0,z=0):return Pos(x,y,z)*Cylinder(r,h)
def make(name):
    c=config()
    if name in ['LOW_BASE','HIGH_BASE','CAP']:
        lo,hi=(-6.5,0) if name=='LOW_BASE' else (-5,0) if name=='HIGH_BASE' else (0,4)
        s=block(-6,6,-12,12,lo,hi)
        s=s-Plane(origin=(0,0,0),z_dir=(1,0,0)).location*Cylinder(3.5,14)
        for y in [-8,8]:
            s=s-bore(1.7,20,y=y)
            if name=='CAP':s=s-Pos(0,y,3.25)*Cone(1.5,3.0,1.5)
        if name=='HIGH_BASE':
            # Coordinates local to the cable axis(-110,1.5,45).
            foot=block(-16,16,-16.5,-8.5,-53.5,-50.5)
            for x in [-10,10]:
                foot=foot-bore(1.7,6,x=x,y=-12.5,z=-52)
                foot=foot-Pos(x,-12.5,-51.25)*Cone(1.5,3.0,1.5)
            post=block(-6,6,-16.5,-12.5,-50.5,-5)
            shelf=block(-6,6,-16.5,-8.5,-5,-2.5)
            s=s+foot+post+shelf
    elif name in ['LINER_LOW','LINER_HIGH']:
        ring=Plane(origin=(0,0,0),z_dir=(1,0,0)).location*(Cylinder(3.5,12)-Cylinder(3,14))
        s=ring & block(-7,7,-4,4,-4 if name=='LINER_LOW' else 0,0 if name=='LINER_LOW' else 4)
        s.color=Color(.18,.24,.3)
    elif name.startswith('SCREW_'):
        L=float(name.split('_')[1]);s=Pos(0,0,-L/2)*Cylinder(1.5,L)
        s=s+Pos(0,0,-.75)*Cone(1.5,3,1.5)
        # Nominal hex socket allocated, no thread-form or catalogue qualification.
        s=s-block(-.8,.8,-.8,.8,-.8,.2)
    elif name in ['DECK','DRIVE_ADAPTER','COMPUTE_ADAPTER']:
        src=c['modified_sources'][name];p=Path(src['path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==src['sha256'];T=src['T_S_step']
        s=Plane(origin=tuple(T[i][3] for i in range(3)),x_dir=tuple(T[i][0] for i in range(3)),z_dir=tuple(T[i][2] for i in range(3))).location*import_step(str(p))
        if name=='DECK':
            for x,y in c['deck_holes_xy_mm']:s=s-bore(1.7,8,x=x,y=y,z=-10)
        else:s=s-block(-126.5,-93.5,-15.5,-6.5,-12,-4)
    else:raise ValueError(name)
    s.label='WP10_TRUNK_'+name+'__NOMINAL_GEOMETRY_MATERIAL_AND_PRELOAD_OPEN'
    return s
