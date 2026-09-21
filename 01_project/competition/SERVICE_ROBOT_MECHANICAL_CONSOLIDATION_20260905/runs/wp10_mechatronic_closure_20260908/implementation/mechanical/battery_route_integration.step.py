"""Local review assembly selected from the complete893-instance source variant."""
from pathlib import Path
import json,hashlib
from build123d import Location,Plane
from cadgen.step_scene import import_step
from cadgen.assembly import AssemblyHelper
A=Path(__file__).resolve().parents[1]
def gen_step():
    p=json.loads((A/'mechanical/BATTERY_ROUTE_PREVIEW_INPUTS.json').read_text())
    assert all(hashlib.sha256((A/k).read_bytes()).hexdigest()==v for k,v in p['input_sha256'].items())
    a=AssemblyHelper('WP10_BATTERY_PROPULSION_ROUTE_LOCAL__FULL_HARNESS_OPEN');root=None
    for r in p['rows']:
        path=Path(r['step_path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==r['source_sha256']
        part=a.add(import_step(str(path)),r['id']);source=a.rigid_frame(part,'source_local_origin',Location())
        if root is None:assert r['id']=='upper_equipment_deck_B';root=part;continue
        T=r['T_S_step'];target=a.rigid_frame(root,r['id']+'_S_target',Plane(origin=tuple(T[i][3] for i in range(3)),x_dir=tuple(T[i][0] for i in range(3)),z_dir=tuple(T[i][2] for i in range(3))).location);a.face_to_face(target,source)
    return a.build()
