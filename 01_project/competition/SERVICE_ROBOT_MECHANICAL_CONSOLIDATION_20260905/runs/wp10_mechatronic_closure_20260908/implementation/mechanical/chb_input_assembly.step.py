from pathlib import Path
import json,hashlib
from build123d import Location,Plane
from cadgen.step_scene import import_step
from cadgen.assembly import AssemblyHelper
A=Path(__file__).resolve().parents[1]
def gen_step():
 p=json.loads((A/'mechanical/CHB_INPUT_INSTANCE_PLAN.json').read_text());s=p['states']['service'];rows={r['id']:r for r in s['rows']}
 ids=['CHB_INPUT_PCB','CHB_INPUT_SPACER_0','CHB_INPUT_SPACER_1','CHB_INPUT_SCREW_0','CHB_INPUT_SCREW_1','U202_CHB','C203_BODY','C203_CARRIER','C203_PCB','C203_LOWER_A','C203_LOWER_B']
 a=AssemblyHelper('WP10_CHB_INPUT_11_PART_DETAIL__ROUTE_AND_QUALIFICATION_OPEN');root=None
 for name in ids:
  r=rows[name];p=Path(r['step_path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==r['source_sha256']
  h=a.add(import_step(str(p)),name);origin=a.rigid_frame(h,'source_origin',Location())
  if root is None:root=h;continue
  T=r['T_S_step'];f=Plane(origin=tuple(T[i][3] for i in range(3)),x_dir=tuple(T[i][0] for i in range(3)),z_dir=tuple(T[i][2] for i in range(3)))
  target=a.rigid_frame(root,name+'_S',f.location);a.face_to_face(target,origin)
 return a.build()
