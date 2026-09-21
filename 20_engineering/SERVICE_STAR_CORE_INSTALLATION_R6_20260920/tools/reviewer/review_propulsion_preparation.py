"""Independent read-only propulsion preparation projection check."""
from pathlib import Path
import csv,hashlib,json
D=Path(__file__).resolve().parents[2];ROOT=D.parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
p=D/'inputs/PROPULSION_ASSEMBLY_PREPARATION.json';prep=read(p)
intake=read(D/'results/reviewer/INSTALLATION_INTAKE_REVIEW.json')
template=read(D/'inputs/PROPULSION_OEM_INPUT_TEMPLATE.json')
checks=[]
def check(n,v,detail=None):checks.append(dict(name=n,passed=bool(v),detail=detail))
for r in prep['source_locks']:check('source_lock:'+r['path'],sha(r['path'])==r['sha256'])
prior=intake['propulsion']
check('OEM_9_gaps_exact',prep['oem_icd_missing_fields']==prior['oem_icd_missing_fields'] and len(prep['oem_icd_missing_fields'])==9)
check('PA01_PA12_exact',prep['work_orders']==prior['next_12_engineering_actions'] and len(prep['work_orders'])==12)
with (D/'docs/PROPULSION_NEXT_WORK_ORDERS.csv').open(encoding='utf-8-sig',newline='') as f:workcsv=list(csv.DictReader(f))
check('CSV12_work_orders_exact',workcsv==prior['next_12_engineering_actions'])
for key in ['mechanical_interface','electrical_interface','functional_routes']:check(key+'_exact',prep[key]==prior[key])
ref={r['id']:r for r in prior['retained_CAD_objects']}
check('10_reserved_objects',len(prep['retained_CAD_objects'])==10 and set(r['id'] for r in prep['retained_CAD_objects'])==set(ref))
for r in prep['retained_CAD_objects']:
    a=ref[r['id']]
    check('object:'+r['id'],r['T_S_local']==a['T_S_local'] and r['S_frame_AABB_mm']==a['S_frame_AABB_mm'] and r['representation_role']==a['representation_role'])
    check('STEP_SHA:'+r['id'],sha(r['source_path'])==r['source_sha256'])
for key in ['selected_flight_MPN','nozzle_positions_S_mm','spacecraft_force_directions_S','plume_half_angle_deg','dry_mass_kg','wet_mass_kg','flight_pressure_contract']:
    check('UNKNOWN_preserved:'+key,prep[key] is None)
for key in ['source_and_load_complete_wiring','nozzle_and_tank_assembly_frozen','thruster_firing_authorized','ready_to_power','flight_ready']:
    check('HOLD_preserved:'+key,prep[key] is False)
known_template={'schema','units','purpose','mount_thread'}
for k,v in template.items():
    if k not in known_template:check('template_unknown:'+k,v is None)
check('template_other_MPN_rebind','other MPN must rebind' in template['mount_thread'])
current_layout_sha=sha(D/'inputs/INSTALLATION_LAYOUT.json')
layout_bound=prep['source_R6_layout_sha256']==current_layout_sha
out=dict(schema='R6_INDEPENDENT_PROPULSION_PREPARATION_REVIEW_V1',
    status='PREPARATION_CONTENT_PASS__FINAL_LAYOUT_BINDING_PENDING' if all(r['passed'] for r in checks) and not layout_bound else ('PREPARATION_CONTENT_PASS_WITH_OEM_HOLDS' if all(r['passed'] for r in checks) else 'FAIL'),
    checks=dict(passed=sum(r['passed'] for r in checks),total=len(checks),failed=[r for r in checks if not r['passed']]),
    checks_detail=checks,preparation_file_sha256=sha(p),
    final_layout_binding=dict(passed=layout_bound,recorded=prep['source_R6_layout_sha256'],current=current_layout_sha,
      action='Regenerate binding against the user-approved final horizontal layout after it is frozen; tilted proposals are historical only.'),
    scope='Content/source projection audit only. No new propulsion selection, pressure-system design, nozzle geometry, wiring, firing or flight capability has been approved.',
    manufacturing_release=False,ready_to_power=False,flight_ready=False)
(D/'results/reviewer/PROPULSION_PREPARATION_REVIEW.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(dict(status=out['status'],checks=out['checks'],final_layout_binding_passed=layout_bound),ensure_ascii=False))
