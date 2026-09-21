"""WP06 source assembly. Imported canonical context and catalogue hardware; mm in S.
Catalogue +Z is outward normal, screw shoulder Z=0, washer/nut bottom Z=0.
Measured catalogue bounding boxes are in BASELINE_ACTUAL_STEP.json.
"""
from pathlib import Path
import sys,json
HERE=Path(__file__).resolve().parent;R=HERE.parent
sys.path.insert(0,str(HERE))
import side_joint_design as design
from build123d import Plane,Location,Color
from cadgen.step_scene import import_step
from cadgen.assembly import AssemblyHelper
from OCP.gp import gp_Trsf

def detached(shape):return type(shape)(shape.wrapped).located(shape.global_location)
def load(path):return detached(import_step(path))
def location(T):
    t=gp_Trsf();t.SetValues(*[v for row in T[:3] for v in row]);return Location(t)
def hardware(P):
    w=P['wp06'];out={}
    names={'screw':'iso4762_socket_head_cap_screw_m3x12','washer_outer':'din125_flat_washer_m3','washer_inner':'din125_flat_washer_m3','nut':'iso4032_hex_nut_m3'}
    bases={'screw':109.65,'washer_outer':109.15,'washer_inner':100.65,'nut':98.25}
    for s in [-1,1]:
        for z0 in [-94,94]:
            z=w['lower_axis_z_mm'] if z0<0 else w['upper_axis_z_mm']
            for role,name in names.items():
                shape=load(R/'inputs/catalog'/(name+'.step'))
                pose=Plane(origin=(w['joint_x_mm'],s*bases[role],z),x_dir=(1,0,0),z_dir=(0,s,0)).location
                out[f'WP06_{role}_{s}_{z0}']=shape.moved(pose)
    return out
def parts(P=None,include_context=True):
    if P is None:P=design.parameters()
    out=design.build_changed(P);out.update(hardware(P))
    if include_context:
        for item in json.loads((R/'inputs/CONTEXT.json').read_text())['states']['service']:
            out[item['id']]=load(item['path']).moved(location(item['T_S_local']))
    return out
def assembly(P=None,include_context=True):
    a=AssemblyHelper('WP06_SIDE_JOINT_C01')
    for name,shape in parts(P,include_context).items():
        shape=detached(shape)
        shape.color=Color(0.72,0.75,0.80) if name.startswith('WP06') else Color(0.28,0.53,0.69) if name.startswith('shear') else Color(0.64,0.65,0.66)
        a.add(shape,name)
    return a.build()
