"""WP06 bounded side-joint geometry branch; all returned shapes use S-frame mm.

Only eight affected structural instances are constructed. No assembly, STEP,
mesh, solver, or source directory is written by this module. Source parameters
without ``wp06`` retain the WP04 geometry of these same eight instances.
"""
from pathlib import Path
import importlib.util
import json
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # Install the existing guarded font loader before build123d.
from build123d import Box,Cylinder,Plane,Location


def _load_local(name):
    """Pin helpers to this run, regardless of another run's sys.modules entries."""
    spec=importlib.util.spec_from_file_location('wp06_side_joint_'+name,HERE/(name+'.py'))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


r01=_load_local('r01_design')
r07=_load_local('r07_design')


def parameters():
    return json.loads((HERE/'design_parameters.json').read_text(encoding='utf-8'))


def _cylinder(diameter,height,center=(0,0,0),axis=(0,0,1)):
    return Cylinder(diameter/2,height).moved(Plane(origin=tuple(center),z_dir=tuple(axis)).location)


def clip_shape(P,side,z):
    """Original 16x6x14.3 clip with unchanged vertical bore and optional side bore relocation."""
    if side not in (-1,1) or z not in (-94,94):
        raise ValueError('Only the four original X150 clips belong to this work package')
    hx,hz,diameter=4,0,3.4
    if P.get('wp06'):
        w=P['wp06'];hx=w['joint_x_mm']-150
        hz=(w['lower_axis_z_mm'] if z<0 else w['upper_axis_z_mm'])-z
        diameter=w['clearance_diameter_mm']
    shape=Box(16,6,14.3)
    shape=shape-_cylinder(diameter,12,(hx,0,hz),(0,1,0))
    shape=shape-_cylinder(2.5,18)
    return shape.moved(Location((150,side*106.15,z)))


def build_changed(P=None):
    """Return 2 webs, 4 X150 clips, and 2 lower segment-1 angles in global S coordinates."""
    if P is None:
        P=parameters()
    out={}
    for side in (-1,1):
        web=r07.modify_web(P,r01.web_shape(P,side),side)
        out[f'shear_web_{side}']=web.moved(Location((0,side*102.15,0)))
        for z in (-94,94):
            out[f'shear_clip_{side}_150_{z}']=clip_shape(P,side,z)
        angle=r01.angle_shape(P,'lower',side,1)
        out[f'lower_deck_angle_{side}_1']=angle.moved(Location(tuple(r01.angle_center(P,'lower',side,1))))
    return out
