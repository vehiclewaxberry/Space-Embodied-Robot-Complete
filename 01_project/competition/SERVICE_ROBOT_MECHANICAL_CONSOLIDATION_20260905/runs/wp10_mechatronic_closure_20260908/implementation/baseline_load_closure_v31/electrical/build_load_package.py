"""Build V31 source-bound arm electrical inputs; Python standard library only.

Run from any directory. It writes only alongside this file. No CAD, firmware,
serial/CAN, network, or prior engineering source is modified.
"""
import csv
import hashlib
import json
import re
from pathlib import Path
from load_model import complete_sensitivity_scenario, evaluate_axis_power

HERE=Path(__file__).resolve().parent
SOURCES=HERE/'sources'
IMPLEMENTATION=HERE.parent.parent

EXPECTED={
 'official_dm_motor.yaml':'b58928907d9524b9591a5b5a5f01f05b0473085669bcb98d54334b1f7e767dab',
 'DM4310_Default_Parameters.txt':'ae476a72a6afa4e72371a748b62162ac62e8c285be1013f3dad1a48c557d5653',
 'DM4340P_Default_Parameters.txt':'55c72881574179bdccdfc39fc229edf1cdbb49ca8974b053fe7a35fef42aeb42',
 'dm4310_v1_1_manual_v1_0.pdf':'3aa891a9014e0b9d8310b7603acaa29205e861f21cd6444d64d273215dc756dc',
 'dm4340p_manual_v1_0.pdf':'f044a7f283ebd995e1f99ea6584c2e1141f8d32f7fa7948f8e353ce44c889b89',
}
URLS={
 'official_dm_motor.yaml':'https://raw.githubusercontent.com/Seeed-Projects/reBotArm_control_py/1bcd81b22c182ec257bf04f5746e1e3d556a5f1c/config/rebotarm_dm.yaml',
 'DM4310_Default_Parameters.txt':'https://files.seeedstudio.com/wiki/robotics/projects/rebot_arm/DM4310_Default_Parameters.txt',
 'DM4340P_Default_Parameters.txt':'https://files.seeedstudio.com/wiki/robotics/projects/rebot_arm/DM4340P_Default_Parameters.txt',
 'dm4310_v1_1_manual_v1_0.pdf':'https://raw.githubusercontent.com/dmBots/DM-J4310-2EC/master/manual/DM-J4310-2EC%20V1.1%E5%87%8F%E9%80%9F%E7%94%B5%E6%9C%BA%E8%AF%B4%E6%98%8E%E4%B9%A6V1.0.pdf',
 'dm4340p_manual_v1_0.pdf':'https://raw.githubusercontent.com/dmBots/DM-J4340P-2EC/master/manual/DM-J4340P-2EC%E5%87%8F%E9%80%9F%E7%94%B5%E6%9C%BA%E8%AF%B4%E6%98%8E%E4%B9%A6V1.0.pdf',
}

def write(name,value):
 (HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def defaults(filename):
 return {k:float(v) for k,v in (line.split(':',1) for line in (SOURCES/filename).read_text(encoding='utf-8').splitlines() if ':' in line)}

def build():
 source_records=[]
 for filename,expected in EXPECTED.items():
  path=SOURCES/filename
  digest=hashlib.sha256(path.read_bytes()).hexdigest()
  if digest!=expected: raise RuntimeError(f'SOURCE_HASH_CHANGED: {filename}')
  upstream=IMPLEMENTATION/'sources'/filename
  if upstream.exists() and hashlib.sha256(upstream.read_bytes()).hexdigest()!=expected:
   raise RuntimeError(f'UPSTREAM_SOURCE_CHANGED: {filename}')
  source_records.append({'source_id':filename,'package_path':'sources/'+filename,'upstream_local_path':str(upstream),
                         'sha256':digest,'bytes':path.stat().st_size,'url':URLS[filename],
                         'retrieval_status':'INHERITED_LOCAL_HASH_VERIFIED',
                         'live_url_check_20260911':'404_WEB_FETCH' if filename.endswith('.pdf') else 'NOT_REDOWNLOADED',
                         'claim_scope':'PUBLIC_REFERENCE_NOT_INSTALLED_UNIT'})
 capture=SOURCES/'WEB_CAPTURE.json'
 if capture.exists():
  for row in json.loads(capture.read_text(encoding='utf-8')):
   if row.get('status')=='ACQUIRED':
    if hashlib.sha256((SOURCES/row['path']).read_bytes()).hexdigest()!=row['sha256']:
     raise RuntimeError('WEB_CAPTURE_HASH_CHANGED')
   source_records.append(row)
 write('SOURCE_MANIFEST.json',{'schema_version':'V31_ELECTRICAL_SOURCES_1','sources':source_records,
                             'web_review_date':'2026-09-11',
                             'additional_web_evidence':[{
                              'url':'https://doc.switch-science.com/media/files/5e033168-99f1-4d2d-b758-e03192a1f071.pdf',
                              'origin':'DAMIAO authored manual hosted by distributor',
                              'revision':'14-page V1.0 dated 2025-01-10',
                              'claim':'p11 corroborates 24V, 2.5A, 8A, 9/27Nm, 40:1, 0.88ohm; not installed revision',
                              'local_snapshot_sha256':None,'status':'WEB_TEXT_REVIEWED_NOT_ARCHIVED'},
                             {'url':'https://www.dmbot.cn/index.php?c=category&id=22',
                              'origin':'DAMIAO manufacturer product list',
                              'claim':'Distinct DM-J4340P-2EC 9/27Nm and V1.1 12/40Nm listings coexist; actual revision unbound.',
                              'local_snapshot_sha256':None,
                              'status':'WEB_SEARCH_TEXT_REVIEWED_LOCAL_HTTP_CAPTURE_TIMEOUT'}]})
 motor_text=(SOURCES/'official_dm_motor.yaml').read_text(encoding='utf-8')
 axes=[]
 for match in re.finditer(r'  - name: (\w+)\s+motor_id: (0x[0-9A-Fa-f]+)\s+feedback_id: (0x[0-9A-Fa-f]+)\s+model: "([^"]+)"',motor_text):
  name,mid,fid,model=match.groups()
  axes.append({'axis':name,'motor_family':'DM'+model,'motor_id':mid,'feedback_id':fid,
               'role':'GRIPPER' if name=='gripper' else 'ARM_REVOLUTE',
               'binding_status':'OFFICIAL_SDK_REFERENCE_ONLY','as_built_motor_revision':None,
               'as_built_serial':None,'as_built_readback':None,'source_id':'official_dm_motor.yaml'})
 if len(axes)!=7: raise RuntimeError('EXPECTED_SEVEN_OFFICIAL_AXES')
 families={}
 manual_values={
 'DM4310':{'manual':'dm4310_v1_1_manual_v1_0.pdf','page':9,'revision':'DM-J4310-2EC V1.1 / manual V1.0 2023-11-16',
           'nominal_voltage_V':24,'rated_current_table_A':2.5,'peak_current_table_A':7.5,
           'rated_output_torque_Nm':3,'peak_output_torque_Nm':7,'rated_output_speed_rpm':120,
           'no_load_output_speed_rpm':200,'gear_ratio':10,'phase_resistance_table_ohm':0.65,
           'phase_inductance_table_H':0.00034,'mass_approx_kg':0.3},
 'DM4340P':{'manual':'dm4340p_manual_v1_0.pdf','page':4,'revision':'43-page DM-J4340P-2EC manual V1.0 date placeholder 2025.xx.xx',
           'nominal_voltage_V':24,'rated_current_table_A':2.5,'peak_current_table_A':8,
           'rated_output_torque_Nm':9,'peak_output_torque_Nm':27,'rated_output_speed_rpm':36,
           'no_load_output_speed_rpm':52,'gear_ratio':40,'phase_resistance_table_ohm':0.88,
           'phase_inductance_table_H':0.00036,'mass_approx_kg':0.375},
 }
 for family in ['DM4310','DM4340P']:
  vals=defaults(family+'_Default_Parameters.txt')
  families[family]={
   'manual_reference_values':manual_values[family],
   'manual_current_convention':'TABLE_DOES_NOT_ESTABLISH_RMS_VS_PEAK_OR_BUS_INPUT; DO_NOT_SUM_AS_BUS_CURRENT',
   'public_default_export':{'source_id':family+'_Default_Parameters.txt','values':vals,
                            'scope':'EXAMPLE_EXPORT_NOT_AS_BUILT_NOT_FIRMWARE_PAYLOAD'},
   'conditional_Kt_from_public_flux_Nm_per_A':1.5*vals['POLE']*vals['Flux']*vals['Gr']*vals['GREF'],
   'conditional_Kt_scope':'MANUAL_FORMULA_WITH_PUBLIC_EXPORTS; IQ_NORMALIZATION_GREF_AND_INSTALLED_REVISION_UNVERIFIED; DO_NOT_USE_FOR_ACTUAL_CURRENT',
   'accepted_model_inputs':{
    'phase_resistance_at_winding_temperature_ohm':None,
    'phase_current_rms_mapping':None,'output_torque_constant_Nm_per_A':None,
    'driver_loss_map_W':None,'gearbox_loss_map_W':None,'core_and_mechanical_loss_map_W':None,
    'electronics_standby_W':None,'holding_bus_power_W':None,'bus_voltage_guaranteed_range_V':None,
    'regen_absorption_J':None,'safe_continuous_output_torque_Nm':None,'peak_duration_s':None,
   },
   'revision_conflicts':[
    'Seeed developer BOM V4 does not uniquely identify the motor/manual hardware revision.',
    f"Manual phase resistance {manual_values[family]['phase_resistance_table_ohm']} ohm differs from public default Rs={vals['Rs']} ohm; no automatic selection.",
    'KT_Value=0 is a public configuration field, not zero physical torque constant.',
    'TMAX/VMAX are protocol mapping ranges, not validated torque-speed/power limits.',
   ]}
 families['DM4340P']['revision_conflicts'].extend([
  'Current DAMIAO product list shows separate older 9/27Nm and V1.1 12/40Nm variants; latter is not assigned to the installed B601.',
  '43-page manual p4 suggests UV15/OV32 for 24V, p5 generic driver text says min20/max65; this is not a guaranteed installed operating envelope.',
 ])
 package={'schema_version':'V31_ARM_ELECTRICAL_PARAMETERS_1','scope':'B601_DM_ARM_BRANCH_6R_PLUS_GRIPPER',
          'status':'PUBLIC_PARAMETERS_SOURCE_BOUND__TASK_LOAD_UNMEASURED','hardware_io_executed':False,
          'axis_bindings':axes,'motor_families':families,
          'arm_bus':{'nominal_V':24,'nominal_source':'seeed_quickstart',
                     'recommended_external_supply_A':15,'recommended_external_supply_product_W':360,
                     'supply_recommendation_is_measured_load':False,'supply_recommendation_is_task_upper_bound':False,
                     'actual_peak_bus_current_A':None,'actual_continuous_bus_power_W':None,
                     'actual_disabled_standby_bus_power_W':None,'actual_enabled_holding_bus_power_W':None,
                     'actual_regenerative_energy_J':None,'host_computer_power_included':False,
                     'camera_and_external_controller_power_included':False},
          'power_accounting':{'positive_direction':'source_to_arm','shaft_coordinate':'output shaft',
             'equation':'P_bus=tau_out*omega_out+P_gear+sum(R_phase*I_phase_rms^2)+P_core_mech+P_driver+P_electronics+dE_internal/dt',
             'hold_rule':'omega=0 removes shaft power only; copper and electronics losses remain.',
             'regeneration_rule':'negative demanded bus power needs verified sink; returned energy at arm port is not battery recovery credit.',
             'prohibited_inferences':['sum phase-current ratings equals bus current','rated torque times rated speed is task input lower bound','360W is hardware/task ceiling','public defaults equal installed calibration','zero shaft speed equals zero load']},
          'required_measurements':['installed revision and parameter export','signed synchronized arm-port voltage/current waveform',
             'joint position/speed/torque-estimate and driver/winding-temperature telemetry',
             'disable/hold/motion/grip/stop/regen phases with thermal boundary metadata',
             'sensor offset/gain/bandwidth and common-timebase qualification'],
          'design_complete':False}
 write('ARM_ELECTRICAL_PARAMETERS.json',package)
 scenarios=[]
 for power in [60,120,240,360]:
  r=complete_sensitivity_scenario(power,hold_bus_power_W=None,standby_bus_power_W=None,gripper_bus_power_W=None)
  r['scenario_id']=f'ARM_MOTION_SCAN_{power:03d}W'
  r['current_at_nominal_24V_A']=power/24
  r['usage']='Only constant mean-power sensitivity. No prediction of physical task, transients, current limit or thermal validation.'
  scenarios.append(r)
 write('LOAD_SENSITIVITY_SCENARIOS.json',{'schema_version':'V31_ARM_LOAD_SENSITIVITY_1',
       'label':'DESIGN_SENSITIVITY_NOT_MOTOR_PREDICTION','scenarios':scenarios,
       'scope':'ARM_BRANCH_TOTAL; gripper must not be counted again if included in supplied motion/hold measurement',
       'phase_assignment':'Only one total arm-branch power per phase. Separate gripper power is additive only when explicitly excluded from arm figure.',
       'recommended_supply_360W_not_upper_bound':True})
 for filename,header in [
  ('BUS_CAPTURE_TEMPLATE.csv',['run_id','time_s','phase_id','bus_voltage_V','bus_current_A','measurement_plane','timebase_id','sensor_calibration_id','sample_valid','ambient_C','base_interface_C','can_sync_event_id']),
  ('JOINT_CAPTURE_TEMPLATE.csv',['run_id','time_s','axis','motor_serial','hardware_revision','firmware_revision','control_mode','q_rad','qd_rad_s','torque_command_Nm','torque_feedback_estimate_Nm','iq_telemetry_A','iq_normalization','winding_temperature_C','mos_temperature_C','fault_code','sample_valid']),
  ('AS_BUILT_READBACK_TEMPLATE.csv',['axis','motor_model_label','hardware_revision','firmware_revision','serial','export_path','export_sha256','UV_Value','OV_Value','OT_Value','OC_Value','TIMEOUT','Rs','Ls','Flux','Gr','GREF','current_scale_definition','read_date','operator'])]:
  path=HERE/filename
  if path.exists() and len(path.read_text(encoding='utf-8').splitlines())>1:
   raise RuntimeError(f'REFUSE_TO_OVERWRITE_CAPTURE_DATA: {filename}')
  with path.open('w',encoding='utf-8',newline='') as f: csv.writer(f).writerow(header)
 write('POWER_MODEL_READINESS.json',{'schema_version':'V31_POWER_MODEL_READINESS_1',
      'software_interface_ready':True,'official_sdk_axis_bindings':len(axes),
      'actual_axis_power_prediction_ready':False,'measured_task_load_spectrum_ready':False,
      'hold_standby_gripper_unknowns_preserved':True,'design_sensitivity_scenarios':len(scenarios),
      'worst_case_power_bounded':False,'thermal_closure_claimed':False,'hardware_io_executed':False,
      'empty_model_example':evaluate_axis_power(torque_output_Nm=0,omega_output_rad_s=0,bus_voltage_V=24)})
 print(json.dumps({'electrical_package':'BUILT','axes':len(axes),'scenarios':len(scenarios),
                   'sources':len(source_records),'actual_load_known':False}))

if __name__=='__main__': build()
