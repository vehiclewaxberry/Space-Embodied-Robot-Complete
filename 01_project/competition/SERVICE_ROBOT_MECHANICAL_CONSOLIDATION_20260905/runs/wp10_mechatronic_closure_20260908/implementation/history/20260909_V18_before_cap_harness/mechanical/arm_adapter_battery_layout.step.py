"""Moved drive carrier with one real edge relief around the retained R01 screw."""
from pathlib import Path
import json,hashlib
import numpy as np
from build123d import Pos,Cylinder,Plane,Color
from cadgen.step_scene import import_step
A=Path(__file__).resolve().parents[1]
def gen_step():
    c=json.loads((A/'mechanical/BATTERY_BAY_LAYOUT.json').read_text());p=json.loads((A/c['source_plan']).read_text())
    assert hashlib.sha256((A/c['source_plan']).read_bytes()).hexdigest()==c['source_plan_sha256']
    r=next(x for x in p['states']['service']['rows'] if x['id']=='adapter_arm_drive');source=Path(r['step_path']);assert hashlib.sha256(source.read_bytes()).hexdigest()==r['source_sha256']
    g=next(x for x in c['rigid_group_moves'] if x['group']=='arm_drive');R=np.array(g['rotation_S']);D=np.eye(4);D[:3,:3]=R;D[:3,3]=np.array(g['to_center_S_mm'])-R@np.array(g['from_center_S_mm']);T=D@np.array(r['T_S_step'])
    s=import_step(str(source)).moved(Plane(origin=tuple(T[:3,3]),x_dir=tuple(T[:3,0]),z_dir=tuple(T[:3,2])).location)
    q=c['arm_adapter_relief'];x,y=q['center_xy_mm'];z0,z1=q['z_mm'];s=s-Pos(x,y,(z0+z1)/2)*Cylinder(q['diameter_mm']/2,z1-z0+2)
    s.label='adapter_arm_drive__BATTERY_LAYOUT_R01_EDGE_RELIEF';s.color=Color(.68,.72,.76);return s
