from pathlib import Path
import json,hashlib
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=json.loads((A/'mechanical/INPUT_CAP_MOUNT_INSTANCE_PLAN.json').read_text());sp=p['states']['service'];rows={r['id']:r for r in sp['rows']}
detail=['C203_CARRIER']+[k for k in sp['added_ids'] if k!='C203_CARRIER']
context=['upper_equipment_deck_B']+detail+['U202_CHB','radiator_spreader','equipment_battery','adapter_battery','equipment_adcs_propulsion_allocation','adapter_adcs_propulsion_allocation','lower_equipment_deck_B']
assert all(k in rows for k in context)
out=dict(inputs={'mechanical/INPUT_CAP_MOUNT_INSTANCE_PLAN.json':sha(A/'mechanical/INPUT_CAP_MOUNT_INSTANCE_PLAN.json')},detail_ids=detail,rows=[rows[k] for k in context],local_only=True,other_928_instances_not_shown=True,whole_fit_verified=False)
(A/'mechanical/INPUT_CAP_MOUNT_PREVIEW_INPUTS.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
for name,ids in [('detail',detail),('integration',context)]:
 src='''from pathlib import Path
import json,hashlib
from build123d import Location,Plane
from cadgen.step_scene import import_step
from cadgen.assembly import AssemblyHelper
A=Path(__file__).resolve().parents[1]
def gen_step():
 p=json.loads((A/'mechanical/INPUT_CAP_MOUNT_PREVIEW_INPUTS.json').read_text());assert all(hashlib.sha256((A/q).read_bytes()).hexdigest()==h for q,h in p['inputs'].items())
 ids=IDS
 rows={r['id']:r for r in p['rows']};a=AssemblyHelper('WP10_C203_VIEW__MECHANICAL_AND_THERMAL_RELEASE_OPEN');root=None
 for k in ids:
  r=rows[k];path=Path(r['step_path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==r['source_sha256'];part=a.add(import_step(str(path)),k);source=a.rigid_frame(part,'source_origin',Location())
  if root is None:assert r['T_S_step']==[[1.0,0.0,0.0,0.0],[0.0,1.0,0.0,0.0],[0.0,0.0,1.0,0.0],[0.0,0.0,0.0,1.0]];root=part;continue
  T=r['T_S_step'];target=a.rigid_frame(root,k+'_S',Plane(origin=tuple(T[i][3] for i in range(3)),x_dir=tuple(T[i][0] for i in range(3)),z_dir=tuple(T[i][2] for i in range(3))).location);a.face_to_face(target,source)
 return a.build()
'''.replace('IDS',repr(ids))
 (A/f'mechanical/input_cap_{name}.step.py').write_text(src,encoding='utf-8')
print(json.dumps(dict(detail=len(detail),context=len(context))))
