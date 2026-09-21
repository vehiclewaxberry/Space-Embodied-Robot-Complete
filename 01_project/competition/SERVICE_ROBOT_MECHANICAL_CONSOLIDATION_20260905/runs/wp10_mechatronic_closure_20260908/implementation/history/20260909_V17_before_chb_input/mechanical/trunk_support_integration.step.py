"""Current trunk supports and complete selected neighboring source geometry."""
from pathlib import Path
import json,hashlib
from build123d import Location,Plane
from cadgen.step_scene import import_step
from cadgen.assembly import AssemblyHelper
A=Path(__file__).resolve().parents[1]
def gen_step():
    p=json.loads((A/'mechanical/TRUNK_SUPPORT_PREVIEW_INPUTS.json').read_text());assert all(hashlib.sha256((A/k).read_bytes()).hexdigest()==h for k,h in p['inputs'].items())
    a=AssemblyHelper('WP10_TRUNK_SUPPORT_LOCAL__WHOLE_DESIGN_OPEN');root=None
    for r in p['rows']:
        path=Path(r['step_path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==r['source_sha256']
        part=a.add(import_step(str(path)),r['id']);source=a.rigid_frame(part,'source_origin',Location())
        if root is None:assert r['id']=='upper_equipment_deck_B';root=part;continue
        T=r['T_S_step'];target=a.rigid_frame(root,r['id']+'_S',Plane(origin=tuple(T[i][3] for i in range(3)),x_dir=tuple(T[i][0] for i in range(3)),z_dir=tuple(T[i][2] for i in range(3))).location);a.face_to_face(target,source)
    return a.build()
