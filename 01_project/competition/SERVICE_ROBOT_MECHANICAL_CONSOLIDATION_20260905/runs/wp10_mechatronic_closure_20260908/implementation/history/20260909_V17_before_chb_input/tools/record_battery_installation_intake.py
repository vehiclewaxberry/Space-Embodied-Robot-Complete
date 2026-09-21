"""Record source-limited battery installation inputs; no invented OEM datums."""
from pathlib import Path
import json,hashlib
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(A/'sources/rrc3570_4.pdf')=='fe9bd820ccce9c18fa0dfce13475b32335a2eb0cc6e658b37cfeeaf101977c24'
assert sha(A/'sources/mc35.pdf')=='925f724eb89b2d562bcd67ac8923c914f82652d3df51a10c9085a0c457a7a912'
screen=json.loads((A/'results/RRC_BATTERY_PACKAGING_SCREEN.json').read_text())
assert screen['source_plan_sha256']==sha(A/'mechanical/FIXED_HEAT_INSTANCE_PLAN.json')
r=dict(schema='WP10_BATTERY_INSTALLATION_INTERFACE_INTAKE_V1',status='PUBLIC_OUTLINE_AND_CONNECTOR_PCB_LAYOUT_BOUND__BATTERY_RETENTION_AND_INSTALLATION_OPEN',
 source_script_sha256=sha(__file__),source_plan_sha256=screen['source_plan_sha256'],
 input_sha256={p:sha(A/p) for p in ['sources/rrc3570_4.pdf','sources/mc35.pdf','power/BATTERY_REVISION_CONFLICT.json','results/RRC_BATTERY_PACKAGING_SCREEN.json']},
 battery=dict(MPN='RRC3570-4',PN='110338',active_design_revision='D',as_built_revision=None,
  nominal_outline_mm=[188.5,85.,81.5],plus_tolerance_mm=[1.,.5,.7],maximum_outline_mm=[189.5,85.5,82.2],nominal_mass_kg=2.08,
  source_page=4,source_url='https://www.rrc-ps.com/fileadmin/user_upload/DS_RRC3570-4_D.pdf',
  legacy_battery_allocation_automatically_replaced=False,additional_high_power_battery_installed=False),
 connector=dict(MPN='RRC-MC35-180-30',PN='211947',battery_D_names_mating_part_page=5,
  document_revision='B',url_filename_revision='A',source_url='https://www.rrc-ps.com/fileadmin/Dokumente/Data-Sheets/DS_RRC-MC35-180-30_A.PDF',
  dimensional_page=3,contact_centers_1D_from_leftmost_mm=[0,7,12,17,22,29],power_contact_separation_mm=29,
  drawing_direction_and_electrical_pin_binding_verified=False,PCB_layout_tolerance_mm=.05,
  power_slot_mm=[1.90,6.60],power_land_mm=[2.50,7.20],signal_slot_mm=[1.,3.30],signal_land_mm=[1.60,3.90],
  body_envelope_nominal_mm=[35.,12.,18.5],overall_height_is_reference_dimension=True,
  contact_retention_force_is_pack_hold_down_capacity=False),
 unbound_manufacturer_facts=dict(socket_T_battery=None,mating_depth_and_stop_mm=None,T_slot_cross_section_and_tolerance=None,
  allowable_hold_down_contact_regions=None,allowable_clamp_force_N=None,handle_sweep=None,unmating_tool_clearance=None,connector_allowable_side_load_N=None),
 current_manual=dict(url='https://www.rrc-ps.com/fileadmin/user_upload/Manual_RRC3570-4.pdf',document_revision='A',pages=33,
  readonly_reviewer_retrieved_in_memory_sha256='c4ce636be2967fd137176ed200044807d52fdd8788ad46f0baefc700d5d66939',archived_locally=False,
  used_to_override_D=False,reason='Current manual electrical fields and nominal/max dimensions across language pages differ; no new controlled retention geometry was found.'),
 packaging_screen='results/RRC_BATTERY_PACKAGING_SCREEN.json',
 next_design_action='Find a bounded internal equipment-relocation set, then evaluate actual STEP intersections for the full D-max body and connector/support access; retain legacy battery function. Only after a defensible mount envelope is found should the carrier and deck changes be generated.',
 native_CAD_modified=False,physical_hardware_operated=False,mechanical_design_closed=False)
(A/'power/BATTERY_INSTALLATION_INTERFACE.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status=r['status'],maximum_outline_mm=r['battery']['maximum_outline_mm'],OEM_datum_invented=False)))
