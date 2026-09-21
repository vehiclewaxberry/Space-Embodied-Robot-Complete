"""Same-candidate local preview; source-local datums precede all placement."""
from pathlib import Path
import json,hashlib
from build123d import Location,Plane
from cadgen.step_scene import import_step
from cadgen.assembly import AssemblyHelper
A=Path(__file__).resolve().parents[1]
def gen_step():
    p=json.loads((A/'mechanical/BATTERY_BAY_PREVIEW_INPUTS.json').read_text())
    for name,digest in p['input_sha256'].items():assert hashlib.sha256((A/name).read_bytes()).hexdigest()==digest
    asm=AssemblyHelper('WP10_BATTERY_BAY_RELAYOUT__MAX_ENVELOPE_AND_REROUTE_PENDING');root=None
    for r in p['rows']:
        source=Path(r['step_path']);assert hashlib.sha256(source.read_bytes()).hexdigest()==r['source_sha256']
        part=asm.add(import_step(str(source)),r['id']);local=asm.rigid_frame(part,'source_local_origin',Location())
        if root is None:
            assert r['id']=='upper_equipment_deck_B' and r['T_S_step']==[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
            root=part;continue
        T=r['T_S_step'];target=asm.rigid_frame(root,r['id']+'_S_placement',Plane(origin=tuple(T[i][3] for i in range(3)),x_dir=tuple(T[i][0] for i in range(3)),z_dir=tuple(T[i][2] for i in range(3))).location)
        asm.face_to_face(target,local)
    return asm.build()
