"""OCC checks of reused interfaces; source contracts are not physical fit tests."""
from pathlib import Path
import json, sys, math
sys.path.insert(0,'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen
from cadgen.step_scene import import_step
from build123d import Location
from kinematics import TREE
HERE=Path(__file__).resolve().parent
def shape(n):return import_step(HERE/'inputs'/f'{n}.step')
def summary(s):
    b=s.bounding_box()
    return dict(min_mm=list(b.min),max_mm=list(b.max),solids=len(s.solids()),volume_mm3=sum(a.volume for a in s.solids()))
def pair(a,b):
    common=a.intersect(b)
    return dict(minimum_distance_mm=a.distance_to(b),common_volume_mm3=0 if common is None else sum(s.volume for s in common.solids()))
a=shape('m3r_a');b=shape('m3r_b');w=shape('link6')
g0=shape('gripper_link')
j=next(j for j in TREE.findall('joint') if j.find('child').get('link')=='gripper_link')
o=j.find('origin');xyz=[float(x)*1000 for x in o.get('xyz').split()];rpy=[math.degrees(float(x)) for x in o.get('rpy').split()]
g=g0.moved(Location(xyz,rpy))
base=shape('base_link')
out=dict(m3r_A=summary(a),m3r_B=summary(b),m3r_nesting=pair(a,b),m3r_A_to_nominal_base=pair(a,base),corrected_base_frame_origin_S_mm=[90,0,125.15],nominal_bearing_plane_S_z_mm=127.555,historical_incorrect_base_lift=dict(additional_z_mm=2.405,minimum_distance_mm=2.4049999999997698,common_volume_mm3=0,status='REJECTED_AND_CORRECTED'),link6=summary(w),palm_in_link6_frame=summary(g),wrist_nominal_interface_exact_urdf=pair(w,g),wrist_orthogonal_reference=pair(w,g0.moved(Location((0,0,159.71),(0,-90,0)))),urdf_fixed_origin_xyz_mm=xyz,urdf_fixed_rpy_deg=rpy,scope='NOMINAL_BREP_GEOMETRY_ONLY_NOT_HARDWARE_FIT')
(HERE/'results').mkdir(exist_ok=True)
(HERE/'results/INTERFACE_GEOMETRY.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))
