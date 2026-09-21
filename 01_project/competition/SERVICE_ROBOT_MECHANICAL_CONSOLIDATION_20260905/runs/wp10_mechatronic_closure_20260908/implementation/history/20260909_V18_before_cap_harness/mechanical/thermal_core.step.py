"""38 source instances: actual CHB/bottom/two-wall thermal core, not full vehicle."""
from pathlib import Path
import json,hashlib
from build123d import Location,Plane
from cadgen.step_scene import import_step
from cadgen.assembly import AssemblyHelper
A=Path(__file__).resolve().parents[1]
def gen_step():
    p=json.loads((A/'mechanical/NATIVE_COLD_INPUTS.json').read_text());asm=AssemblyHelper('WP10_CHB_BOTTOM_DUAL_WALL_THERMAL_CORE')
    rows=sorted(p['rows'],key=lambda r:r['id']!='radiator_spreader');root=None
    for r in rows:
        path=Path(r['step_path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==r['source_sha256']
        h=asm.add(import_step(str(path)),r['id']);local=asm.rigid_frame(h,'source_origin',Location())
        if root is None:root=h;continue
        T=r['T_S_step'];origin=tuple(T[i][3] for i in range(3));xd=tuple(T[i][0] for i in range(3));zd=tuple(T[i][2] for i in range(3))
        target=asm.rigid_frame(root,r['id']+'_S_transform',Plane(origin=origin,x_dir=xd,z_dir=zd).location)
        asm.face_to_face(target,local)
    return asm.build()
