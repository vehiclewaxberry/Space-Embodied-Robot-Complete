from pathlib import Path
import json,hashlib
from build123d import Location,Plane
from cadgen.step_scene import import_step
from cadgen.assembly import AssemblyHelper
A=Path(__file__).resolve().parents[1]
def gen_step():
 p=json.loads((A/'mechanical/CAP_HARNESS_RETAINED_PLAN_V21.json').read_text())
 rows={r['id']:r for r in p['states']['service']['rows']}
 ids=['CHB_INPUT_PCB','CHB_INPUT_SPACER_0','CHB_INPUT_SPACER_1','CHB_INPUT_SCREW_0','CHB_INPUT_SCREW_1','U202_CHB','C203_BODY','C203_CARRIER','C203_PCB','C203_LOWER_A','C203_LOWER_B','C203_W_PLUS','C203_W_MINUS','C203_LACE_PLUS','C203_LACE_MINUS']
 ids += [f'C203_BOARD_SCREW_{i}' for i in range(4)]+[f'C203_CLAMP_SCREW_{i}' for i in range(4)]
 ids += ['C203_LINER_A_TOP','C203_LINER_A_BOTTOM','C203_LINER_B_TOP','C203_LINER_B_BOTTOM']
 a=AssemblyHelper('WP10_C203_CHB_27_INSTANCE_RETENTION_CANDIDATE');root=None
 for name in ids:
  r=rows[name];f=Path(r['step_path']);assert hashlib.sha256(f.read_bytes()).hexdigest()==r['source_sha256']
  h=a.add(import_step(str(f)),name);origin=a.rigid_frame(h,'source_origin',Location())
  if root is None:
   assert r['T_S_step']==[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]];root=h;continue
  T=r['T_S_step'];plane=Plane(origin=tuple(T[i][3] for i in range(3)),x_dir=tuple(T[i][0] for i in range(3)),z_dir=tuple(T[i][2] for i in range(3)))
  a.face_to_face(a.rigid_frame(root,name+'_S',plane.location),origin)
 return a.build()

