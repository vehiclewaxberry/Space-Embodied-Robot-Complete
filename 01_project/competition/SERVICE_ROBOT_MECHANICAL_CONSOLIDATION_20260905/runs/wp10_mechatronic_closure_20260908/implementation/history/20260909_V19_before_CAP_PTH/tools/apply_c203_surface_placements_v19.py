"""Apply corrected screw locations and invalidate stale generated STEP bindings."""
from pathlib import Path
import json,hashlib,copy
A=Path(__file__).resolve().parents[1]
def read(p):return json.loads((A/p).read_text())
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def dump(p,v):(A/p).write_text(json.dumps(v,indent=2),encoding='utf-8')
profile=read('mechanical/C203_SURFACE_PROFILE_V19.json');plan=read('mechanical/CAP_HARNESS_INSTANCE_PLAN_V19.json')
assert not plan.get('surface_profile_pending'), 'Already applied; do not replay'
for state,st in plan['states'].items():
 rows={r['id']:r for r in st['rows']}
 for i in range(4):
  r=rows[f'C203_BOARD_SCREW_{i}'];assert r['T_S_step'][0][3]==-5.4
  assert [r['T_S_step'][j][2] for j in range(3)]==[-1,0,0]
  r['T_S_step'][0][3]=profile['screw_underhead_x_mm']
  r['representation_role']='NOMINAL_M3_HEAD_POSITION_DERIVED_FROM_NO_COPPER_BEARING_SURFACE'
 for name,source in [('C203_PCB','mechanical/input_cap_pcb.step.py'),('C203_W_PLUS','mechanical/cap_harness_plus.step.py'),('C203_W_MINUS','mechanical/cap_harness_minus.step.py')]:
  r=rows[name];r['geometry_regeneration_required']=True;r['expected_generator_source']=source;r['expected_generator_sha256']=sha(source)
  r['geometry_state']='OLD_STEP_RETAINED_FOR_HISTORY__NOT_CURRENT_SURFACE_REVISION'
 st['changed_ids']=['C203_PCB']+[f'C203_BOARD_SCREW_{i}' for i in range(4)];st['unchanged_parent_instances']=965
plan.update(surface_profile_pending=True,source_geometry_fresh=False,source_surface_profile='mechanical/C203_SURFACE_PROFILE_V19.json',source_surface_profile_sha256=sha('mechanical/C203_SURFACE_PROFILE_V19.json'),whole_fit_verified=False)
plan['inputs'].update({'power/CAP_HARNESS_DEFINITION_V19.json':sha('power/CAP_HARNESS_DEFINITION_V19.json'),'mechanical/C203_SURFACE_PROFILE_V19.json':sha('mechanical/C203_SURFACE_PROFILE_V19.json')})
dump('mechanical/CAP_HARNESS_INSTANCE_PLAN_V19.json',plan)
print('Four screw positions updated in all3 states; PCB/wire STEP explicitly invalidated pending regeneration')
