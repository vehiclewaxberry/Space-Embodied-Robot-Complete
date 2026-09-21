"""One-time, bounded input capture and literal extraction of the WP02 root builder."""
from pathlib import Path
import hashlib,json,shutil
HERE=Path(__file__).resolve().parent
W1=HERE.parent/'service_robot_wp01_20260905';W2=HERE.parent/'service_robot_wp02_20260905'
for d in ['results','parts','drawings','snapshots','inputs','runtime']: (HERE/d).mkdir(exist_ok=True)
def sh(p):return hashlib.sha256(p.read_bytes()).hexdigest()
files=[W1/'design_parameters.json',W1/'SOURCE_INPUTS.json',W1/'kinematics.py',W1/'service_robot_common.py',W2/'parts_model.py',W2/'design_parameters.json',W2/'results/CONTACT_REGISTRATION.json',W2/'results/DELIVERY_RECEIPT.json',Path('C:/Users/stude/Downloads/WP03_SPACECRAFT_BODY_REFOCUS_PROMPT_ZH.md')]
(HERE/'inputs/LOCAL_INPUT_HASHES.json').write_text(json.dumps([{'path':str(p),'sha256':sh(p)} for p in files],indent=2),encoding='utf-8')
shutil.copy2(W1/'kinematics.py',HERE/'kinematics.py')
shutil.copy2(W2/'runtime/sitecustomize.py',HERE/'runtime/sitecustomize.py')
solar=HERE.parent/'F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/solar_array_r2_kinematics.py'
shutil.copy2(solar,HERE/'solar_kinematics_source.py')
source=(W2/'parts_model.py').read_text(encoding='utf-8')
section=source[source.index('    # Flight-candidate root frame'):source.index('    # Standalone GSE')]
section='\n'.join(s for s in section.splitlines() if 'asm.rigid_frame' not in s)
header='''"""Literal WP02 root geometry reused in WP03; no call to WP02 build or writes to WP02."""
from pathlib import Path
import importlib.util,math,json
from build123d import Box,Cylinder,Location
from cadgen.step_scene import import_step
ORIGINAL=Path(__file__).resolve().parent.parent/'service_robot_wp02_20260905'
spec=importlib.util.spec_from_file_location('wp02_readonly_helpers',ORIGINAL/'parts_model.py')
w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
P=w.P;R=w.R;HERE=ORIGINAL
box=w.box;tube=w.tube;bore=w.bore;plate=w.plate;screw=w.screw;ring=w.ring
ON=w.ON;HW=w.HW;GOLD=w.GOLD;DARK=w.DARK
def build_root(add):
'''
(HERE/'root_structure.py').write_text(header+section+'\n',encoding='utf-8')
p=json.loads((W1/'design_parameters.json').read_text(encoding='utf-8'))
p.update(configuration_id='WP03_SERVICER_ONBOARD_R1',physical_status='ENGINEERING_DESIGN_CANDIDATE',
    qualification_status='NOT_EVALUATED',material_density_kg_mm3={'AL_CANDIDATE':2.7e-6,'STEEL_CANDIDATE':7.85e-6},
    wing_source={'path':str(solar),'sha256':sh(solar),'leaves_per_wing':3,'leaf_mm':[300,200,2.5],'leaf_mass_budget_kg':.18,'root_abs_y_mm':115.4,'root_z_mm':-108.15},
    retention={'station_x_mm':[-115,-40],'hinge_y_mm':-99,'hinge_z_mm':125.15,'fold_deg_released':90,'cap_open_deg':100,'latch_withdraw_mm':12,'physical_energy_source':'ONBOARD_EPS_RELEASE_CHANNEL_CANDIDATE','drive_status':'SPRING_PLUS_ELECTRICAL_PIN_PULLER_INTERFACE_NOT_SELECTED'},
    launch_interface={'direction_S':[-1,0,0],'frame_origin_S_mm':[-195,0,0],'vendor_pattern':None,'load_envelope':None,'status':'STRUCTURAL_RESERVATION_ONLY'},
    states={'parking':{'q_deg':[0,-30,-60,40,0,0],'finger_mm':15,'wing_angles_deg':[0,0,0],'retention_fold_deg':0,'cap_open_deg':0,'meaning':'OPEN_PARKING_REFERENCE_WITH_ONBOARD_HOLDING_CANDIDATE'},'released':{'q_deg':[0,-30,-60,40,0,0],'finger_mm':15,'wing_angles_deg':[0,0,0],'retention_fold_deg':90,'cap_open_deg':100,'meaning':'RELEASED_CANDIDATE_STATIC_KEYFRAME'},'service':{'q_deg':[0,-80,-70,30,0,0],'finger_mm':15,'wing_angles_deg':[90,180,180],'retention_fold_deg':90,'cap_open_deg':100,'meaning':'SERVICE_CONFIGURATION_CANDIDATE'}})
(HERE/'design_parameters.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
print('WP03 source scaffold and pinned inputs created')
