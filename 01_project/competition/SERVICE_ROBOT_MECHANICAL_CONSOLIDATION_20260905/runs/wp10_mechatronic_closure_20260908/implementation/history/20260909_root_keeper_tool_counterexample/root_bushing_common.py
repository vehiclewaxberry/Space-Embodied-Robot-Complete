"""Split, axially captured passage sleeve. S datum is bridge underside at (65,-80,107.15)."""
from pathlib import Path
import json,hashlib
from build123d import Box,Cylinder,Cone,Pos,Plane,Color,RegularPolygon,extrude
from cadgen.step_scene import import_step
A=Path(__file__).resolve().parents[1]
def config():return json.loads((A/'mechanical/ROOT_BUSHING_DESIGN.json').read_text())
def block(x0,x1,y0,y1,z0,z1):return Pos((x0+x1)/2,(y0+y1)/2,(z0+z1)/2)*Box(x1-x0,y1-y0,z1-z0)
def cyl(r,z0,z1,x=0,y=0):return Pos(x,y,(z0+z1)/2)*Cylinder(r,z1-z0)
def make(name):
    c=config()
    if name.startswith('BUSH_'):
        s=cyl(c['stem_OD_mm']/2,0,8)+cyl(c['flange_OD_mm']/2,-2,0)
        s=s-cyl(c['bore_ID_mm']/2,-3,9)
        # 0.5 x 45 degree entry chamfers; no sharp metallic edge at bridge bore.
        s=s-Pos(0,0,7.75)*Cone(3.3,3.8,.5)-Pos(0,0,-1.75)*Cone(3.8,3.3,.5)
        s=s & block(-8,0,-8,8,-3,9) if name.endswith('LEFT') else s & block(0,8,-8,8,-3,9)
        s.color=Color(.74,.65,.44)
    elif name.startswith('KEEPER_'):
        left=name.endswith('LEFT');x0,x1=(-16,-.1) if left else (.1,16);a,b=(-16,-9) if left else (9,16);x=-12 if left else 12
        s=block(x0,x1,-8,8,-4,-2.1)+block(a,b,-8,8,-2.1,0)
        s=s-cyl(3.5,-5,1)-cyl(1.7,-5,1,x)
        s=s-Pos(x,0,-3.25)*Cone(3,1.5,1.5)
        s.color=Color(.55,.62,.68)
    elif name=='SCREW_8':
        s=cyl(1.5,0,8)+Pos(0,0,.75)*Cone(3,1.5,1.5)
        s=s-Pos(0,0,-.1)*extrude(RegularPolygon(.8,6),amount=1.0)
        s.color=Color(.22,.25,.28)
    elif name=='BRIDGE':
        src=c['bridge_source'];p=Path(src['step_path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==src['source_sha256'];T=src['T_S_step']
        s=Plane(origin=tuple(T[i][3] for i in range(3)),x_dir=tuple(T[i][0] for i in range(3)),z_dir=tuple(T[i][2] for i in range(3))).location*import_step(str(p))
        for x,y in c['screw_xy_S_mm']:s=s-Pos(x,y,109.35)*Cylinder(1.5,4.6)
        s.color=Color(.52,.59,.68)
    else:raise ValueError(name)
    s.label='WP10_ROOT_'+name+'__NOMINAL_CAPTURE_NO_STRAIN_RELIEF_OR_FLIGHT_CREDIT'
    return s
