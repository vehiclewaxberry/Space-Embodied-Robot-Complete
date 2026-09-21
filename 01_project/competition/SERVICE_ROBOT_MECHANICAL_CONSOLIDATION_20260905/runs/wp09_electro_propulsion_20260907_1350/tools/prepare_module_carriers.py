"""Prepare source-bound WP09 local interface candidates; no device selection."""
from pathlib import Path
import json,hashlib
R=Path(__file__).resolve().parents[1]
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
w6=R.parent/'wp06_side_joint_20260907_0233'
sources=[R/'inputs/electrical_sources/A3200_DS1006901_2_0.pdf',R/'inputs/propulsion_sources/VACCO_MiPS_standard_0714.pdf',R/'research/ELECTRICAL_SOURCE_FACTS.json',R/'research/PROPULSION_SOURCE_FACTS.json',Path(__file__)]
cat={}
for role,name in [('screw','iso4762_socket_head_cap_screw_m3x12'),('washer','din125_flat_washer_m3'),('nut','iso4032_hex_nut_m3')]:
    p=w6/'inputs/catalog'/(name+'.step');sources.append(p);cat[role]=dict(path=str(p),sha256=sha(p))
c=dict(schema='WP09_MODULE_CARRIERS_CONTRACT',status='LOCAL_NOMINAL_CANDIDATES_NOT_SELECTED_HARDWARE',
 geometry_reader=str(w6/'tools/verify_joint_geometry.py'),source_inputs={str(p):sha(p) for p in sources},
 acceptance=dict(linear_mm=1e-5,volume_mm3=1e-5,integration_eps=1e-7),catalogue_parts=cat,
 a3200=dict(frame='A_LOCAL_MM_X_BOARD_LONG_Y_BOARD_SHORT_Z_UP',board_box_mm=[[0,0,5],[65,40,6.8]],
 board_holes_xy_mm=[[3,3],[62,3],[3,37],[62,37]],board_hole_d_mm=3.2,
 hole_basis='OEM p14 one corner offsets3/3 plus hole dia3.2; other corners DERIVED_SYMMETRIC_PATTERN, tolerances unknown',
 carrier_box_mm=[[-10,-10,0],[75,50,2]],carrier_holes_xy_mm=[[-5,-5],[70,-5],[-5,45],[70,45]],carrier_hole_d_mm=3.4,
 spacer_outer_d_mm=5.5,spacer_inner_d_mm=3.2,spacer_z_mm=[2,5],
 top_washer_z_mm=[6.8,7.3],screw_underhead_z_mm=7.3,screw_tip_z_mm=-4.7,
 bottom_washer_z_mm=[-.5,0],nut_z_mm=[-2.9,-.5],
 oem_board_thickness_mm=1.8,oem_component_above_board_mm=4.0,oem_component_below_board_mm=1.3,
 oem_3mm_standoff_source='DS1006901 Rev2.0 p9',expected_instances=22,
 unknowns=['Actual populated PCB component map and mounting lands','FSI exact mating variant and pinout','Carrier-to-spacecraft fastening','Preload/insulation/EMC/thermal/vibration']),
 mips=dict(frame='V_LOCAL_MM_X_FRONT_TO_REAR_Y_RIGHT_Z_UP_BOTTOM_DATUM',
 equipment_envelope_mm=[[0,-44.5008,0],[30,44.5008,89.0016]],
 mounting_holes_x_mm=3.175,mounting_holes_z_mm=[6.3754,82.5754],mounting_y_mm=[-44.5008,44.5008],
 oem_thread='4-40 UNC-2B',thread_major_d_mm=2.8448,thread_pitch_mm=.635,
 effective_thread_depth_mm=None,selected_screw_length_mm=None,
 carrier_union_boxes_mm=[[[31,-48,-4],[34,48,93]],[[20,-48,-4],[46,48,-1]],
 [[0,44.7508,1],[34,46.7508,12]],[[0,44.7508,77],[34,46.7508,88.5]],
 [[0,-46.7508,1],[34,-44.7508,12]],[[0,-46.7508,77],[34,-44.7508,88.5]]],
 side_hole_d_mm=3.2,side_hole_axis='Y',side_hole_basis='DESIGN_CLEARANCE_FOR_4_40_NOT_M3_THREAD',
 shim_outer_d_mm=7,shim_inner_d_mm=3.2,shim_thickness_mm=.25,
 base_mount_holes_xy_mm=[[24,-35],[24,35],[41,-35],[41,35]],base_mount_hole_d_mm=3.4,
 front_design_keepout_mm=[[-50,-44.5008,0],[0,44.5008,89.0016]],
 front_keepout_basis='DECLARED_50MM_FULL_FACE_AXIAL_SERVICE_KEEP_OUT_NOT_PLUME_MODEL',
 expected_instances=6, current_shared_compartment_fit=False,
 current_shared_compartment_note='Local carrier97mm Z exceeds existing75mm shared ADCS/propulsion height; NOT integrated. Bare unit axis permutation fit cannot qualify this orientation/carrier.',
 unknowns=['OEM3D/pinout connector location and service clearance','Nozzle centers/3D thrust vectors/plume','Thread depth and actual fastener/torque','Bracket strength and tolerances','Actual pressure hardware and qualification']),
 integrated_into_wp08=False,as_built=False,manufacturing_release=False,electrical_complete=False,pressure_system_designed=False)
cp=R/'inputs/MODULE_CARRIERS_CONTRACT.json';assert not cp.exists()
cp.write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding='utf-8')
print(cp)

