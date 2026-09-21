from pathlib import Path
import csv, datetime, hashlib, io, json, shutil, unittest
from propulsion_contract import LOCKED_SHA,source_config,supply_screen,pulse_screen,mounting_screen,wrench_model

P=Path(__file__).resolve().parent
C=P.parents[1]; R=C.parent; N=R/'reuse_closure'; F=R/'functional_closure'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def bind(path): return {'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size}
def write(name,data):
 p=P/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');return p
sources={
 'CPOD_LOCKED':C/'sources/propulsion_intake/VACCO_C_POD_frozen_Rev7_14.pdf',
 'CPOD_CONFLICT':C/'sources/propulsion_intake/VACCO_C_POD_downloads_index.pdf',
 'PDU_DS':N/'sources/power/P60_PDU200_2_6.pdf',
 'PDU_OPTION':N/'sources/power/PDU200_OPTION_1021197_4_5.pdf',
 'FROZEN_PROPULSION_MODEL':F/'inputs/PROPULSION_SCREEN_INPUTS.json',
 'CURRENT_MASTER_FROM_TO':N/'ecad/MASTER_FROM_TO.csv',
 'CPOD_CATALOGUE_PAGE2_RENDER':F/'research/propulsion_cpod_page2.png',
}
bindings={k:bind(v) for k,v in sources.items()}
assert bindings['CPOD_LOCKED']['sha256']==LOCKED_SHA
assert bindings['CPOD_CONFLICT']['sha256']=='2bf995824f1c4f2374fe3f7707e6b86f6b138d80bcd75cfdee938938019813a3'
write('SOURCE_BINDINGS.json',bindings)
contract={
 'schema':'WP09_PROPULSION_SOURCE_BOUND_INTERFACE_V1',
 'status':'CATALOGUE_INTERFACE_CONSTRAINTS_IMPLEMENTED__DELIVERED_OEM_ICD_UNBOUND',
 'source_sha256':LOCKED_SHA,'part_number':'X13003000-01','propellant':'R236fa',
 'configuration_identity':'2016update filename / footer Rev7/14 / exact SHA; hardware and firmware applicability unbound',
 'source_references':bindings,
 'mechanical':{
  'catalogue_page':2,'mounting_callout':'.112-40 UNC-2B',
  'designation_equivalent':'#4-40 UNC internal thread class 2B',
  'nominal_major_diameter_mm':.112*25.4,'pitch_mm':25.4/40,
  'visible_callout_groups':[{'count_label':2,'view':'left side projection'},{'count_label':2,'view':'right side projection'}],
  'unique_hole_count':None,'hole_centers_in_controlled_frame_mm':None,'thread_depth_mm':None,
  'torque_Nm':None,'fastener_part_number':None,'allowable_loads':None,
  'interpretation':'Two side-view callouts are not used to assert a controlled unique hole count or coordinate set.',
  'dimension_callouts_inch':[3.878,3.720,3.995],
  'dimension_callouts_mm':[3.878*25.4,3.720*25.4,3.995*25.4],
  'complete_tolerance_maximum_installed_envelope':None,
  'generic_M3_direct_attachment':'REJECTED_THREAD_MISMATCH',
  'adapter_manufacturing_release':False},
 'electrical':{
  'load_voltage_catalogue_V':[9,12.6],'max_standby_catalogue_W':.25,
  'max_two_thruster_scope_W':5,'two_thruster_mode_current_bound_A_at_9V':5/9,
  'startup_heater_all_concurrent_current_profile':None,
  'source_candidate':{'device':'P60 PDU200','datasheet':'1014111 2.6','option_sheet':'1021197 4.5',
    'regulator':0,'voltage_V':12,'high_voltage_channel':1,'battery_min_V':24,
    'source_pin_identity':{'connector':'Samtec TFM-115-02-L-DH','positive_same_output_pins':[1,3],'return_pins':[2,4],'polarization_key_next_to_pin':30},
    'max_catalogue_total_channel_current_A':2,'two_positive_pins_do_not_make_two_channels':True,
    'shipped_configuration_bound':False,'output_guaranteed_tolerance_and_transients':None},
  'propulsion_mating_connector':None,'propulsion_power_pin':None,'propulsion_return_pin':None,
  'RS422_TX_RX_pin_polarity':None,'chassis_screen_bond_scheme':None,
  'source_and_load_complete_wiring':False,'cut_length_mm':None,'energization_allowed':False},
 'pulse':{'minimum_impulse_bit_catalogue_Ns':.0005,'thrust_catalogue_range_N':[.008,.012],
   'valve_response_strict_upper_s':.01,'MIB_rectangular_equivalent_duration_s':[.0005/.012,.0005/.008],
   'nominal_rectangular_duration_s':.05,'command_width_from_this_calculation':None,
   'steady_rectangular_surrogate_only':True,'OEM_pulse_transfer_function':None},
 'configuration_binding':None,'nozzle_xyz_m':None,'force_directions_unit':None,
 'allowed_concurrency':None,'installation_transform':None,'combined_com_m':None,'command_map':None,
 'wrench_matrix':None,'actual_operational_capacity_status':'UNKNOWN_INPUTS_MISSING',
 'physical_commands_emitted':0,'flight_release':False,
}
write('PROPULSION_INTERFACE_CONTRACT.json',contract)
rows=[
 {'id':'PROP_SRC_P1','source_connector':'PDU200 TFM-115-02-L-DH','source_pin':1,'source_signal':'CH1 regulated output','DUT_connector':'','DUT_pin':'','status':'SOURCE_ONLY_BOUND'},
 {'id':'PROP_SRC_P3','source_connector':'PDU200 TFM-115-02-L-DH','source_pin':3,'source_signal':'same CH1 regulated output','DUT_connector':'','DUT_pin':'','status':'SOURCE_ONLY_BOUND'},
 {'id':'PROP_SRC_R2','source_connector':'PDU200 TFM-115-02-L-DH','source_pin':2,'source_signal':'GND return','DUT_connector':'','DUT_pin':'','status':'SOURCE_ONLY_BOUND'},
 {'id':'PROP_SRC_R4','source_connector':'PDU200 TFM-115-02-L-DH','source_pin':4,'source_signal':'GND return','DUT_connector':'','DUT_pin':'','status':'SOURCE_ONLY_BOUND'},
]
with (P/'SOURCE_SIDE_INTERFACE_ROWS.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
calc={
 'catalogue_scalar_sources_unchanged':True,
 'source_candidate_admission':source_config(24,0,1,12),
 'source_bounds_current_status':supply_screen(None,None,None,None,None),
 'nominal_12V_positive_headroom_V':12.6-12,
 'headroom_is_total_static_positive_error_plus_ripple_plus_transient_requirement_not_source_guarantee':True,
 'source_validation_example_not_selected_hardware':supply_screen(11.8,12.2,.1,.1,.3),
 'ten_ms_at_nominal_impulse_Ns':.01*.01,
 'ten_ms_nominal_pulse':pulse_screen(.01*.01),
 'catalogue_MIB_screen':pulse_screen(.0005),
 'thread_correct_type_only':mounting_screen('.112-40 UNC-2B'),
 'generic_metric_M3_direct_mate':mounting_screen('M3x0.5'),
 'actual_thrust_mapping':wrench_model(contract),
}
write('CALCULATIONS.json',calc)
suite=unittest.defaultTestLoader.discover(str(P),pattern='test_propulsion_contract.py')
stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
(P/'TEST_OUTPUT.txt').write_text(stream.getvalue(),encoding='utf-8')
assert result.wasSuccessful()
assert bindings=={k:bind(v) for k,v in sources.items()}
receipt={
 'schema':'WP09_PROPULSION_RESUME_RECEIPT_V1','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'status':'PASS_SOURCE_BOUND_INTERFACE_IMPLEMENTATION__ACTUAL_PROPULSION_DESIGN_STILL_OPEN',
 'tests':{'executed':result.testsRun,'failed':len(result.failures),'errors':len(result.errors),'passed':result.testsRun-len(result.failures)-len(result.errors)},
 'new_concrete_items':['OEM .112-40 UNC-2B mounting constraint','PDU CH1 four source-side pin identities and single 2A channel limit','MIB versus valve response distinction','bounded source voltage and hot loop checker'],
 'new_OEM_wiring_pins_obtained':0,'new_OEM_protocol_commands_obtained':0,
 'current_full_circuit_complete':False,'actual_wrench_model_complete':False,
 'catalogue_scalars_unchanged':True,'parent_sources_byte_preserved':True,
 'physical_commands_emitted':0,'hardware_connected':False,'pressure_work_executed':False,
 'supplier_contacted':False,'manufacturing_release':False,'flight_release':False,
 'source_bindings':bindings,'contract':bind(P/'PROPULSION_INTERFACE_CONTRACT.json'),
 'calculations':bind(P/'CALCULATIONS.json'),'implementation':bind(P/'propulsion_contract.py'),
 'tests_file':bind(P/'test_propulsion_contract.py'),'test_output':bind(P/'TEST_OUTPUT.txt'),
 'research_intake':bind(P/'sources/INTAKE_MANIFEST.json'),
}
out=C/'results/PROPULSION_RESUME_20260908.json';out.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'result':str(out),'tests':receipt['tests'],'status':receipt['status']},ensure_ascii=False))
