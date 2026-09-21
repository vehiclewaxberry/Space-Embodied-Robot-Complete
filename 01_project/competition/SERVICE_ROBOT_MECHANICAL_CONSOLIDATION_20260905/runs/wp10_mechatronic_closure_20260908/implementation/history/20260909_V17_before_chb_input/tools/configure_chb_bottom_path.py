"""Root-writer revision: preserve V6 release, configure the actual short path."""
from pathlib import Path
import json,hashlib,shutil
A=Path(__file__).resolve().parents[1]
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def write(p,x):(A/p).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
archive=A/'history/20260909_before_CHB_bottom_cold_fingers';archive.mkdir(parents=True,exist_ok=True)
for name in ['WP10_IMPLEMENTATION_DELTA.zip','README.md','REVIEW.html','results/DELIVERY_DECISION.json']:
    p=A/name;dest=archive/Path(name).name
    if not dest.exists():shutil.copy2(p,dest)
p=read('thermal/BOTTOM_RADIATOR_MOUNT.json')
if p.get('chb_path',{}).get('TIM_family')=='BERGQUIST SIL PAD TSP 1800ST':
    print('Current TSP1800ST revision retained; initial TSP1600S configurator skipped.');raise SystemExit(0)
p['schema']='WP10_BOTTOM_RADIATOR_MOUNT_CANDIDATE_V2_CHB_COLD_FINGERS'
p['chb_path']={
 'enabled':True,'center_xy_mm':[-25,0],'seat_size_mm':[58,62],
 'seat_z_mm':-96.379,'oem_base_z_mm':-96.15,'TIM_thickness_mm':.229,
 'oem_hole_x_offsets_mm':[-24.13,24.13],'oem_hole_y_offsets_mm':[-25.4,25.4],
 'mechanical_drawing_pitch_x_mm':48.3,'OEM_STEP_pitch_x_mm':48.26,
 'hole_pitch_disposition':'STEP axes bind nominal screw alignment; drawing rounding difference0.02mm per side retained for tolerance review; no OEM machining',
 'clearance_bore_mm':3.4,'CHB_screw_inclusive_length_mm':20,
 'deck_window_size_mm':[60,96],'deck_window_center_xy_mm':[-25,0],
 'finger_x_mm':[-54,4],'finger_riser_abs_y_mm':[33,47],
 'finger_bottom_z_mm':-106.15,'finger_arm_z_mm':[-82,-58],
 'wall_seat_abs_y_mm':96.5,'wall_TIM_thickness_mm':.229,
 'wall_TIM_size_mm':[58,24],'wall_contact_center_xz_mm':[-25,-70],
 'wall_screw_centers_xz_mm':[[-43,-70],[-7,-70]],
 'wall_screw_inclusive_length_mm':20,'finger_thread_nominal_major_d_mm':3.,
 'finger_thread_nominal_depth_mm':5.,
 'wall_TIM_material':'TSP1600S project cut; nominal uncompressed0.229mm; typical0.75 K in2/W at25psi is not a guaranteed mounted resistance',
 'geometry_role':'ONE_PIECE_6061_BOTTOM_PEDESTAL_AND_TWO_COLD_FINGERS; two removable TIM joints to existing walls',
 'side_fastening_sequence':'Both solar wings deployed/service for outward driver access; folded access is explicitly blocked',
 'thread_model':'Cylindrical major-diameter void and simplified screw, no helical threads or effective engagement verification',
 'ecad_instance_id':'U202_CHB','ecad_ref':'U203',
 'alias_disposition':'Legacy CAD instance ID retained; actual integrated CHB schematic ref is U203. U202 is not reused as a new electrical ref.',
 'CHB_only_thermal_validation':False,'thermal_release':False,'structural_release':False}
p['qualification']['thermal_connection_to_CHB_installed']=False
p['qualification']['revision_state']='SOURCE_CONFIGURED_READBACK_PENDING'
write('thermal/BOTTOM_RADIATOR_MOUNT.json',p)
f=read('thermal/FIXED_HEAT_PATH.json');chb=next(d for d in f['devices'] if d['id']=='U202_CHB')
if 'previous_wall_mount' not in chb:chb['previous_wall_mount']={k:chb[k] for k in ['side','center_xz_mm','carrier_back_abs_y_mm','carrier_size_mm','metal_path_mm']}
chb.update(mount_type='BOTTOM_PEDESTAL',ecad_ref='U203',seat_origin_S_mm=[-25,0,-96.379],metal_path_mm=17.771)
f['CHB_mount_source']='thermal/BOTTOM_RADIATOR_MOUNT.json#chb_path'
for panel in f['panels']:
    panel['holes_xz_d_mm']=list(panel['tool_holes_xz_d_mm'])
    for d in f['devices']:
        if d['side']==panel['side'] and d.get('mount_type')!='BOTTOM_PEDESTAL':
            x,z=d['center_xz_mm']
            panel['holes_xz_d_mm'] += [[x+dx,z,4.5] for dx in [-28.5,28.5]]
    panel['holes_xz_d_mm'] += [[x,z,6.72] for x,z in p['chb_path']['wall_screw_centers_xz_mm']]
write('thermal/FIXED_HEAT_PATH.json',f)
print(json.dumps(dict(revision='V7_SHORT_METAL_PATH',archive=str(archive),geometry_generated=False)))
