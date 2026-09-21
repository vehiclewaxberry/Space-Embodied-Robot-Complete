"""Derive one reviewable candidate from real WP10 sources; never rewrite parents."""
from pathlib import Path
import csv, hashlib, json, xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
A = HERE.parent
RUNS = A.parents[1]
WP09 = RUNS / 'wp09_interfaces_20260907_1525'
PROJECT=next(p for p in HERE.parents if (p/'AGENTS.md').exists())

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def dump(name, obj):
    (HERE/name).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')

def build():
    xml = A/'ecad/wp10_system.xml'
    tree = ET.parse(xml).getroot()
    components = tree.findall('./components/comp')
    rows = []
    for c in components:
        rows.append(dict(ref=c.get('ref'), value_or_MPN=c.findtext('value'),
                         footprint=c.findtext('footprint') or '',
                         sheet=c.find('sheetpath').get('names'),
                         source='ecad/wp10_system.xml', source_sha256=sha(xml),
                         selection_status='ACTUAL_NETLIST_VALUE_NOT_PROCUREMENT_RELEASE'))
    assert len({r['ref'] for r in rows}) == len(rows)
    byref = {r['ref']:r for r in rows}
    assert byref['U303']['value_or_MPN'] == 'MAX5048CAUT+T'
    assert byref['U304']['value_or_MPN'] == 'MAX16053AUT+T'
    with (HERE/'ACTIVE_ELECTRICAL_BOM.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    netrows=[]
    for n in tree.findall('./nets/net'):
        for node in n.findall('node'):
            netrows.append(dict(net=n.get('name'),ref=node.get('ref'),pin=node.get('pin'),
                                pinfunction=node.get('pinfunction',''),pintype=node.get('pintype','')))
    with (HERE/'ACTIVE_PIN_NETS.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(netrows[0]));w.writeheader();w.writerows(netrows)
    prop=WP09/'system_completion/propulsion/resume_20260908/PROPULSION_INTERFACE_CONTRACT.json'
    inputs=[xml,A/'ecad/wp10_main_input.kicad_pcb',A/'power/MAIN_INPUT_BOARD_DEFINITION_V26.json',
            A/'power/POWER_CHAIN_SELECTION.json',A/'power/SHARED_BATTERY_PATH_DEFINITION.json',
            A/'power/MAIN_INPUT_COPPER_LOSS_V26.json',A/'power/INPUT_PASSIVE_SELECTION.json',
            A/'power/LOAD_SIDE_BRAKE_DEFINITION.json',A/'power/POWER_LOOP_PARTS.json',A/'power/POWER_LOOP_CALCULATIONS.json',
            A/'thermal/BOTTOM_RADIATOR_MOUNT.json',A/'thermal/COLD_TIM_INTERFACE_CONTRACT.json',
            A/'thermal/SPATIAL_RADIATOR_NETWORK_SCREEN.json',A/'thermal/RADIATOR_MESH_VIEW_SCREEN.json',
            A/'results/FIXED_HEAT_GEOMETRY.json',A/'results/COLD_PATH_GEOMETRY.json',
            A/'mechanical/CAP_HARNESS_RETAINED_PLAN_V21.json',
            A/'mechanical/MAIN_INPUT_PLACEMENT_BOUNDS_V27.json',
            A/'tools/shared_battery_path.py',A/'tools/spatial_radiator_network.py',prop,
            WP09/'functional_closure/tools/propulsion_screen.py',
            A/'sources/COLD_TIM_SELECTION.json',PROJECT/'30_simulation/common/capture_impulse.py',
            PROJECT/'30_simulation/common/rigid_body.py',A/'mechanical/PARAMETER_PACKET.json',
            A/'power/MAIN_BOARD_PASSIVE_SELECTION_V25.json',A/'power/TIMER_PASSIVE_SELECTION_V24.json']
    inputs += sorted((A/'ecad').glob('wp10_*.kicad_sch'))
    cfg=dict(schema='WP10_COUPLED_CANDIDATE_20260910',
       scope='DIGITAL_DESIGN_AND_DECLARED_SCENARIOS; NOT BENCH OR FLIGHT EVIDENCE',
       parent='WP10 V26 ECAD + V21 974-instance plan; V27 rejected placements retained',
       source_lock={str(p.resolve()):sha(p) for p in inputs},
       evidence=dict(physical_tests=False,flight_qualified=False,whole_design_complete=False),
       mission=dict(approved_orbit=None,approved_service_duration_s=None,approved_phase_profile=None,
                    target_and_postcapture_state=None,solar_recharge_Wh=None,
                    note='Existing 95-minute cycle is sensitivity, not approved mission. No chosen target is changed.'),
       analysis_scenario=dict(status='DECLARED_SENSITIVITY_NOT_APPROVED_MISSION',
          initial_energy_fraction=.8,pack_V=25.2,shared_R_ohm=.01,eta_main=.85,
          hot_R_multiplier=2.,copper_C=100.,hot_initial_C=25.,cold_initial_C=-10.,
          cold_environment_K=250.,cold_duration_s=3600.,
          phases=[dict(mode=mode,duration_s=dt) for mode,dt in [('RUN',600),('SAFE_COOLDOWN',1200),('RUN',600),('SAFE_COOLDOWN',1200)]]),
       electrical=dict(battery='RRC3570-4 Rev D / 110338',nominal_energy_Wh=407.43,
          usable_energy_fraction_scenarios=[0.5,0.8],pack_V_scenarios=[20.,22.,25.2,29.4],
          pack_V_definition='protected pack before MC35; held constant only within each sensitivity case',
          battery_current_limit_A=30.,main_output_W=361.,aux_output_W=16.8,startup_input_W=.25,
          eta_main_scenarios=[.85,.9],eta_aux=.8,shared_R_scenarios_ohm=[.01,.1],aux_R_ohm=.04,
          main_R_components_ohm=dict(Q201_25C=.021,shunts=.0022,fuse_typical_20C=.0017,
              copper_20C=read(A/'power/MAIN_INPUT_COPPER_LOSS_V26.json')['R20_ohm'],
              other_wiring_contacts_allocation=.01),
          Q201_hot_R_multiplier_scenarios=[1.,2.],copper_temperature_C_scenarios=[20.,100.],
          protection_screens={k:read(A/'power/POWER_LOOP_CALCULATIONS.json')[k] for k in ['UVLO_falling_screen_V','OVLO_rising_screen_V','current_limit_screen_A']},
          output_distribution_losses_W=None,battery_internal_heat_W=None,arm_local_heat_W=None,
          charge_mode='OFFLINE_ONLY_NOT_WIRED; PMM35 excluded from discharge; no regen credit to battery',
          source_voltage_floor_confirmed=False,efficiencies_guaranteed=False,
          stop_regeneration_energy_J=None,thermal_path_verified=False),
       thermal=dict(environment=dict(status='INHERITED_ILLUSTRATIVE_NOT_ORBIT',state='released',occluder_K=330.,space_K=3.,solar_W_m2=1361.),
          nominal_TIM='TSP1800ST 0.203mm, 25psi reference impedance; no measured preload',
          Q201_Rjc_K_W=.31,Q201_junction_limit_C=150.,CHB_case_limit_C=105.,
          new_board_heat_connection='proposed source attachment to +Y radiator; actual install not proven',
          uniform_node_transient='ideal mixing of modelled radiator area; optimistic screening only',
          cold_safe_heater_limit_W=20.,heater_limit_status='DESIGN_ALLOCATION_NOT_INSTALLED',
          heater_efficiency=.8,heater_setpoint_C=0.,heater_gain_W_K=5.,aluminum_cp_J_kgK=900.,aluminum_density_kg_m3=2700.,
          regulator_unknown_losses_included=False),
       propulsion=dict(candidate='VACCO C-POD X13003000-01 frozen Rev7/14',
          installed_geometry='MiPS nonpressure reference only; C-POD not installed',
          total_impulse_catalogue_Ns=174.,per_nozzle_force_N_bounds=[.008,.012],
          minimum_impulse_bit_Ns=.0005,minimum_command_width_s=None,
          nominal_Isp_s=40.,source_contract=str(prop.resolve()),
          nozzle_positions_S_m=None,force_directions_S_unit=None,combined_COM_S_m=None,
          allowed_concurrency=None,command_map=None,plume_exclusions=None,
          electrical_catalogue_V=[9.,12.6],catalogue_two_jet_power_W=5.,
          allocated_onboard_power_W=None,mission_required_angular_impulse_Nms=None,
          actual_wrench_status='UNKNOWN_ICD_AND_CURRENT_CAPTURE_STATE_UNBOUND'),
       mechanical=dict(complete_plan_instances_each_state=974,
          new_main_module_installed=False,complete_spacecraft_mass_kg=None,
          units='mm',main_board_size_mm=[100,80,1.6],board_holes_mm=[[4,4],[96,4],[4,76],[96,76]],
          main_carrier_mm=[132,92,4],new_carrier_material='6061-T6 density2700 kg/m3 design value',
          terminal_wire_OD_mm=4.5,terminal_wire_core_area_mm2=3.3,
          terminal_wire_size_status='PROJECT_12AWG_CLASS_ALLOCATION; actual insulation/ampacity unbound',
          CPOD_project_carrier_mm=[116,112,4],CPOD_OEM_holes=None,
          CPOD_carrier_status='UNINSTALLED_PROJECT_SIDE_BLANK; no pressure wall or OEM clamp design'),
       blockers=[
        'Approved orbit/phases, usable battery energy and solar charging topology unbound',
        'MC35 terminal/SysDetect and heat path, output distribution and arm heat unbound',
        'Q201 hot SOA, source hot-short L/R, source buffering and full stop measured waveform unbound',
        'F201 OEM asks 3oz copper/10mm trace; V26 70um/8mm scenarios do not establish this condition',
        'C-POD nozzle, mounting, command, firmware and plume ICD absent; old MiPS CAD incompatible',
        'New main board module and proposed carrier require populated whole-spacecraft interference check'])
    dump('CANDIDATE.json',cfg)
    dump('ELECTRICAL_RECONCILIATION.json',dict(symbols=len(rows),pins=len(netrows),
       U303=byref['U303'],U304=byref['U304'],actual_xml_sha256=sha(xml),
       old_SELECTED_BOM_superseded_for_electrical_ref_identity=True,
       old_selected_module_BOM_retained_as_history=True,rule_check_rerun=False,
       BOM_source_consistency=True,unknown_MPNs_not_resolved_by_netlist=True))
    print(json.dumps(dict(symbols=len(rows),pins=len(netrows),locked_inputs=len(inputs))))

if __name__=='__main__':build()
