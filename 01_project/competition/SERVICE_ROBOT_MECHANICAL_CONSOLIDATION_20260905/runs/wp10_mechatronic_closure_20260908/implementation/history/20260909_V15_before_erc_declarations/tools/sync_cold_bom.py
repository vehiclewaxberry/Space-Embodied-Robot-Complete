"""Publish current material and instance mapping; keep predecessor studies unchanged."""
from pathlib import Path
import json,csv,hashlib,ast
A=Path(__file__).resolve().parents[1]
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def dump(p,v):(A/p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
c=read('thermal/BOTTOM_RADIATOR_MOUNT.json')['chb_path'];n=read('mechanical/NATIVE_COLD_INPUTS.json');g=read('results/COLD_PATH_GEOMETRY.json');net=read('thermal/SPATIAL_RADIATOR_NETWORK_SCREEN.json')
assert net['selected_TIM_family']==c['TIM_family'] and net['checks_passed']
params=next(ast.literal_eval(v.value) for v in ast.parse((A/'mechanical/carrier_common.py').read_text()).body if isinstance(v,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PARAMS' for t in v.targets))
contract=dict(schema='WP10_CURRENT_COLD_TIM_INTERFACE_V1',selected_material=c['TIM_family'],
 source_selection='sources/COLD_TIM_SELECTION.json',source_selection_sha256=sha('sources/COLD_TIM_SELECTION.json'),
 source_plan_sha256=n['source_plan_sha256'],geometry_sha256=sha('results/COLD_PATH_GEOMETRY.json'),
 nominal_uncompressed_thickness_mm=c['TIM_thickness_mm'],compressed_thickness_mm=None,
 stock_tolerance_mm=None,actual_uniform_pressure_psi=None,nominal_reference_pressure_psi=25,
 CHB=dict(CAD_instance='U202_CHB_TIM',device_electrical_ref='U203',
  project_cut_xy_mm=[params['tim_x_mm'],params['tim_y_mm']],hole_d_mm=params['tim_hole_d_mm'],
  hole_centers_xy_mm=[[sx*params['oem_pitch_x_mm']/2,sy*params['oem_pitch_y_mm']/2] for sx in [-1,1] for sy in [-1,1]],
  OEM_STEP_hole_pitch_mm=[c['OEM_STEP_pitch_x_mm'],2*c['oem_hole_y_offsets_mm'][1]],
  hole_pitch_rounding_disposition=c['hole_pitch_disposition'],
  net_contact_area_mm2=g['CHB_TIM_contact_mm2'],seat_z_S_mm=c['seat_z_mm'],OEM_base_z_S_mm=c['oem_base_z_mm'],
  source='mechanical/chb_bottom_tim.step.py'),
 wall_TIM=dict(quantity=2,project_cut_xz_mm=c['wall_TIM_size_mm'],net_contact_area_mm2=g['wall_joints'][0]['contact_area_mm2'],
  hole_d_mm=4.5,hole_centers_local_xz_mm=[[-18,0],[18,0]],source='mechanical/cold_finger_tim.step.py'),
 pressure_sensitivity=net['pressure_sensitivity'],uniform_force_requirements=net['uniform_pressure_clamp_force_requirements'],
 impedance_includes_both_interfaces=True,extra_TIM_t_over_kA_added=False,
 material_insulating=True,assembly_electrical_isolation_verified=False,
 preload_verified=False,thread_effective_engagement_verified=False,thermal_release=False,manufacturing_release=False,
 predecessor='power/THERMAL_INTERFACE_CONTRACT.json and converter_installation.step are retained predecessor component studies; not the current mounted interface')
dump('thermal/COLD_TIM_INTERFACE_CONTRACT.json',contract)
path=A/'power/SELECTED_BOM.csv'
rows=list(csv.DictReader(path.open(encoding='utf-8-sig')));fields=list(rows[0])
assert sum(r['role'].startswith('TIM201:') for r in rows)==1
for r in rows:
    if r['role'].startswith('TIM201:'):
        r.update(manufacturer='Henkel stock / project cut',MPN='BERGQUIST SIL PAD TSP1800ST 0.203mm nominal; project cut55.9x59mm',quantity='1',status='CURRENT_GEOMETRY_INSTALLED__PRELOAD_COMPRESSION_UNVERIFIED',source='thermal/COLD_TIM_INTERFACE_CONTRACT.json;mechanical/chb_bottom_tim.step.py;sources/COLD_TIM_SELECTION.json')
    if r['role']=='local thermal carrier':
        r.update(MPN='WP10_MONOLITHIC_BOTTOM_PEDESTAL_DUAL_COLD_FINGERS_6061',quantity='1',status='CURRENT_SOURCE_GEOMETRY__NO_MANUFACTURING_RELEASE',source='mechanical/bottom_radiator.step.py;thermal/BOTTOM_RADIATOR_MOUNT.json')
role='mechanical cold-finger wall TIMs; no electrical ref'
rows=[r for r in rows if r['role']!=role]
rows.append(dict(role=role,manufacturer='Henkel stock / project cut',MPN='BERGQUIST SIL PAD TSP1800ST 0.203mm nominal; project cut58x24mm',quantity='2',status='CURRENT_GEOMETRY_INSTALLED__PRELOAD_COMPRESSION_UNVERIFIED',source='thermal/COLD_TIM_INTERFACE_CONTRACT.json;mechanical/cold_finger_tim.step.py'))
with path.open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
out=[]
for r in n['rows']:
    out.append(dict(instance_id=r['id'],quantity=1,native_part_id=r['native_part_id'],
     source_step=r['step_path'],source_sha256=r['source_sha256'],native_part=r['native_path'],
     status='CURRENT_FIXED_POSE_GEOMETRY_NOT_MANUFACTURING_RELEASE',
     interface_material=c['TIM_family'] if ('TIM' in r['id']) else '',
     source_doc='thermal/COLD_TIM_INTERFACE_CONTRACT.json' if 'TIM' in r['id'] else 'mechanical/CHB_BOTTOM_COLD_PATH_BRIEF.md'))
with (A/'mechanical/COLD_PATH_INSTANCE_BOM.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
path=A/'mechanical/CAD_BRIEF.md';old=path.read_text(encoding='utf-8')
prefix='当前整星安装版本为V7 CHB底部双侧壁路径'
if not old.startswith(prefix):
    path.write_text(prefix+'：三处TSP1800ST名义0.203mm；以CHB_BOTTOM_COLD_PATH_BRIEF.md、thermal_core.step和../thermal/COLD_TIM_INTERFACE_CONTRACT.json为准。下述converter_installation/TSP1600S是保留的前版局部研究，不是当前894实例中的已装接口。\n\n---\n\n'+old,encoding='utf-8')
print(json.dumps(dict(instance_BOM_rows=len(out),current_TIM_pieces=3,electrical_ref_count_changed=False)))
