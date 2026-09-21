"""Four integral supports for relocated navigation carrier; S frame mm."""
from pathlib import Path
import json,hashlib
from build123d import Pos,Rot,Cylinder,Color
from cadgen.step_scene import import_step
A=Path(__file__).resolve().parents[1]
def gen_step():
    p=json.loads((A/'mechanical/BATTERY_BAY_LAYOUT.json').read_text())['navigation_wall_edit']
    source=A/p['baseline_step'];assert hashlib.sha256(source.read_bytes()).hexdigest()==p['baseline_sha256']
    s=import_step(str(source));y0,y1=p['boss_y_mm']
    for x,z in p['boss_centers_xz_mm']:
        s=s+Pos(x,(y0+y1+.01)/2,z)*Rot(90,0,0)*Cylinder(p['boss_diameter_mm']/2,y1+.01-y0)
        end=p['blind_hole_end_y_mm']
        s=s-Pos(x,(y0-1+end)/2,z)*Rot(90,0,0)*Cylinder(p['nominal_thread_major_diameter_mm']/2,end-y0+1)
    s.label='shear_web_1__NAVIGATION_FOUR_INTEGRAL_SUPPORT_BOSSES';s.color=Color(.68,.72,.76)
    return s
