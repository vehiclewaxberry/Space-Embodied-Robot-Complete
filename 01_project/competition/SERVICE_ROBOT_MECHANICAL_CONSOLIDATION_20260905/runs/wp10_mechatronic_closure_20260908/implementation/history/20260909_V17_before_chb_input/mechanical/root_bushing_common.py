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
    c=config();z0,z1=c['stem_z_local_mm'];f0,f1=c['flange_z_local_mm'];k0,k1=c['keeper_z_local_mm'];b0,b1=c['keeper_boss_z_local_mm']
    if name.startswith('BUSH_'):
        s=cyl(c['stem_OD_mm']/2,z0,z1)+cyl(c['flange_OD_mm']/2,f0,f1)
        s=s-cyl(c['bore_ID_mm']/2,f0-1,z1+1)
        # 0.5 x 45 degree entry chamfers; no sharp metallic edge at bridge bore.
        s=s-Pos(0,0,z1-c['entry_chamfer_mm']/2)*Cone(c['bore_ID_mm']/2,c['bore_ID_mm']/2+c['entry_chamfer_mm'],c['entry_chamfer_mm'])-Pos(0,0,f0+c['entry_chamfer_mm']/2)*Cone(c['bore_ID_mm']/2+c['entry_chamfer_mm'],c['bore_ID_mm']/2,c['entry_chamfer_mm'])
        s=s & block(-c['flange_OD_mm'],0,-c['flange_OD_mm'],c['flange_OD_mm'],f0-1,z1+1) if name.endswith('LEFT') else s & block(0,c['flange_OD_mm'],-c['flange_OD_mm'],c['flange_OD_mm'],f0-1,z1+1)
        s.color=Color(.74,.65,.44)
    elif name=='KEEPER':
        x0,x1,y0,y1=c['keeper_outline_xy_local_mm'];a,b=c['keeper_boss_x_local_mm'];r=c['keeper_throat_ID_mm']/2
        s=block(x0,x1,y0,y1,k0,k1)+block(a,b,y0,y1,b0,b1)
        s=s-cyl(r,k0-1,b1+1)-block(0,x1+1,-r,r,k0-1,b1+1)
        for x,y in c['screw_xy_local_mm']:
            s=s-cyl(c['clearance_hole_D_mm']/2,k0-1,b1+1,x,y)
            s=s-Pos(x,y,k0+c['head_height_mm']/2)*Cone(c['head_D_mm']/2,c['screw_D_mm']/2,c['head_height_mm'])
        s.color=Color(.55,.62,.68)
    elif name=='SCREW_8':
        s=cyl(c['screw_D_mm']/2,0,c['screw_nominal_total_length_mm'])+Pos(0,0,c['head_height_mm']/2)*Cone(c['head_D_mm']/2,c['screw_D_mm']/2,c['head_height_mm'])
        s=s-Pos(0,0,-.1)*extrude(RegularPolygon(.8,6),amount=1.0)
        s.color=Color(.22,.25,.28)
    elif name=='BRIDGE':
        src=c['bridge_source'];p=Path(src['step_path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==src['source_sha256'];T=src['T_S_step']
        s=Plane(origin=tuple(T[i][3] for i in range(3)),x_dir=tuple(T[i][0] for i in range(3)),z_dir=tuple(T[i][2] for i in range(3))).location*import_step(str(p))
        for x,y in c['screw_xy_S_mm']:s=s-Pos(x,y,c['datum_S_mm'][2]+(c['thread_envelope_depth_mm']-.1)/2)*Cylinder(c['screw_D_mm']/2,c['thread_envelope_depth_mm']+.1)
        s.color=Color(.52,.59,.68)
    else:raise ValueError(name)
    s.label='WP10_ROOT_'+name+'__NOMINAL_CAPTURE_NO_STRAIN_RELIEF_OR_FLIGHT_CREDIT'
    return s
