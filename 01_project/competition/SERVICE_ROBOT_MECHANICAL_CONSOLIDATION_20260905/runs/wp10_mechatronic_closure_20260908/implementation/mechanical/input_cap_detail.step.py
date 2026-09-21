from pathlib import Path
import json,hashlib
from build123d import Location,Plane
from cadgen.step_scene import import_step
from cadgen.assembly import AssemblyHelper
A=Path(__file__).resolve().parents[1]
def gen_step():
 p=json.loads((A/'mechanical/INPUT_CAP_MOUNT_PREVIEW_INPUTS.json').read_text());assert all(hashlib.sha256((A/q).read_bytes()).hexdigest()==h for q,h in p['inputs'].items())
 ids=['C203_CARRIER', 'C203_BODY', 'C203_PCB', 'C203_LOWER_A', 'C203_LOWER_B', 'C203_LINER_A_TOP', 'C203_LINER_A_BOTTOM', 'C203_LINER_B_TOP', 'C203_LINER_B_BOTTOM', 'C203_DECK_SCREW_0', 'C203_DECK_WASHER_0', 'C203_DECK_NUT_0', 'C203_DECK_SCREW_1', 'C203_DECK_WASHER_1', 'C203_DECK_NUT_1', 'C203_DECK_SCREW_2', 'C203_DECK_WASHER_2', 'C203_DECK_NUT_2', 'C203_DECK_SCREW_3', 'C203_DECK_WASHER_3', 'C203_DECK_NUT_3', 'C203_CLAMP_SCREW_0', 'C203_CLAMP_SCREW_1', 'C203_CLAMP_SCREW_2', 'C203_CLAMP_SCREW_3', 'C203_BOARD_SCREW_0', 'C203_BOARD_SCREW_1', 'C203_BOARD_SCREW_2', 'C203_BOARD_SCREW_3']
 rows={r['id']:r for r in p['rows']};a=AssemblyHelper('WP10_C203_VIEW__MECHANICAL_AND_THERMAL_RELEASE_OPEN');root=None
 for k in ids:
  r=rows[k];path=Path(r['step_path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==r['source_sha256'];part=a.add(import_step(str(path)),k);source=a.rigid_frame(part,'source_origin',Location())
  if root is None:assert r['T_S_step']==[[1.0,0.0,0.0,0.0],[0.0,1.0,0.0,0.0],[0.0,0.0,1.0,0.0],[0.0,0.0,0.0,1.0]];root=part;continue
  T=r['T_S_step'];target=a.rigid_frame(root,k+'_S',Plane(origin=tuple(T[i][3] for i in range(3)),x_dir=tuple(T[i][0] for i in range(3)),z_dir=tuple(T[i][2] for i in range(3))).location);a.face_to_face(target,source)
 return a.build()
