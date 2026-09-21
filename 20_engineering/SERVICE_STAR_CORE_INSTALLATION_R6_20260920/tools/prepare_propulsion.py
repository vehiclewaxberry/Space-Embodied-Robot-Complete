"""Source-bound propulsion handoff; unknown OEM quantities stay null."""
from geometry import *
import csv
ip=D/'results/reviewer/INSTALLATION_INTAKE_REVIEW.json';intake=read(ip);p=intake['propulsion']
plan=read(D/'inputs/NATIVE_ASSEMBLY_PLAN.json');rows={r['id']:r for r in plan['expected_leaves']}
old={r['id']:r for r in read(R4/'inputs/NATIVE_ASSEMBLY_PLAN.json')['expected_leaves']}
locks=[]
for f in [ip,ROOT/p['trade_source'],ROOT/p['interface_contract'],ROOT/p['current_engineering_gap_actions'],IMPL/'mechanical/BATTERY_PROPULSION_ROUTING.json',R4/'inputs/NATIVE_ASSEMBLY_PLAN.json']:
    locks.append(dict(path=str(f),sha256=sha(f)))
retained=[]
for x in p['retained_CAD_objects']:
    r=rows[x['id']];o=old[x['id']]
    assert r['source_sha256']==o['source_sha256'] and r['T_S_local']==o['T_S_local']
    assert sha(r['step_path'])==r['source_sha256']
    retained.append(dict(id=r['id'],source_path=r['step_path'],source_sha256=r['source_sha256'],T_S_local=r['T_S_local'],S_frame_AABB_mm=[a.tolist() for a in world_bounds(r)],representation_role=r['representation_role'],R4_identity_and_pose_preserved=True))
out=dict(schema='R6_PROPULSION_PREPARATION_V1',status='PREPARATION_READY_OEM_INPUTS_OPEN',coordinate_frame='S_mm',source_locks=locks,
 source_R6_layout_sha256=sha(D/'inputs/INSTALLATION_LAYOUT.json'),retained_CAD_objects=retained,functional_routes=p['functional_routes'],
 mechanical_interface=p['mechanical_interface'],electrical_interface=p['electrical_interface'],oem_icd_missing_fields=p['oem_icd_missing_fields'],work_orders=p['next_12_engineering_actions'],
 selected_flight_MPN=None,nozzle_positions_S_mm=None,spacecraft_force_directions_S=None,plume_half_angle_deg=None,
 dry_mass_kg=None,wet_mass_kg=None,flight_pressure_contract=None,source_and_load_complete_wiring=False,
 nozzle_and_tank_assembly_frozen=False,thruster_firing_authorized=False,ready_to_power=False,flight_ready=False)
assert len(out['oem_icd_missing_fields'])==9 and len(retained)==10 and len(out['work_orders'])==12
write(D/'inputs/PROPULSION_ASSEMBLY_PREPARATION.json',out)
template=dict(schema='OEM_PROPULSION_INTERFACE_REQUEST_V1',units={'length':'mm','force':'N','mass':'kg','voltage':'V','time':'s','pressure':'Pa'},
 purpose='Populate from controlled OEM ICD and selected delivered configuration; null is UNKNOWN, never zero-fill.',
 OEM_name=None,MPN=None,revision=None,ICD_document=None,ICD_sha256=None,
 CAD_file=None,CAD_sha256=None,OEM_frame_definition=None,T_S_OEM=None,
 max_installed_envelope_mm=None,mount_thread='CPOD catalogue candidate only: #4-40 UNC-2B; other MPN must rebind',
 hole_count=None,hole_coordinates_OEM_mm=None,thread_depth_mm=None,bolt_MPN=None,torque_Nm=None,interface_allowable_loads=None,
 connector_MPN=None,mating_connector_MPN=None,pin_map=None,return_and_chassis_bond=None,
 voltage_min_V=None,voltage_max_V=None,steady_current_A=None,startup_current_profile=None,heater_current_profile=None,
 ARM_INHIBIT_contract=None,communication_pin_polarity=None,command_protocol_revision=None,
 nozzle_count=None,nozzles=None,command_min_width_s=None,command_max_width_s=None,latency_s=None,concurrency_matrix=None,
 force_pressure_temperature_contract=None,plume_exclusion_geometry=None,thermal_interface=None,
 tank_feed_pressure_contract=None,propellant=None,dry_mass_kg=None,wet_mass_kg=None,COM_OEM_mm=None,inertia_OEM_kg_m2=None,
 qualification_evidence=None)
write(D/'inputs/PROPULSION_OEM_INPUT_TEMPLATE.json',template)
with (D/'docs/PROPULSION_NEXT_WORK_ORDERS.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(out['work_orders'][0]));w.writeheader();w.writerows(out['work_orders'])
write(D/'results/PROPULSION_PREPARATION_CHECK.json',dict(status='PASS_SOURCE_BOUND_PREPARATION_ONLY',retained_objects_unchanged=len(retained),source_locks_verified=len(locks),oem_open_items=9,engineering_work_orders=12,selected_flight_MPN=None,assembly_frozen=False,ready_to_power=False))
print('PROPULSION PREP',len(retained),'retained objects;',9,'OEM gaps;',12,'work orders')
