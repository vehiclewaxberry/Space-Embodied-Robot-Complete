"""Remove local passage material, preserving all original attachment holes."""
from pathlib import Path
import hashlib,json
from build123d import Plane,Pos,Cylinder
from cadgen.step_scene import import_step
A=Path(__file__).resolve().parents[1]
def part(key):
    c=json.loads((A/'mechanical/BATTERY_HARNESS_PASSAGE.json').read_text())
    path=A/c['source_plan'];assert hashlib.sha256(path.read_bytes()).hexdigest()==c['source_plan_sha256']
    r=next(r for r in json.loads(path.read_text())['states']['service']['rows'] if r['id']==key)
    source=Path(r['step_path']);assert hashlib.sha256(source.read_bytes()).hexdigest()==r['source_sha256']
    T=r['T_S_step'];loc=Plane(origin=tuple(T[i][3] for i in range(3)),x_dir=tuple(T[i][0] for i in range(3)),z_dir=tuple(T[i][2] for i in range(3))).location
    s=loc*import_step(str(source));x,y=c['center_xy_mm'];z0,z1=c['cut_z_mm']
    s=s-Pos(x,y,(z0+z1)/2)*Cylinder(c['diameter_mm']/2,z1-z0)
    s.label=key+'__D10_FUNCTIONAL_PASSAGE_LINER_AND_STRENGTH_PENDING'
    return s
