"""Bind new vendor public joint mappings; physical execution stays disabled."""
from pathlib import Path
import csv,hashlib,json,yaml
from datetime import datetime,timezone
D=Path(__file__).resolve().parent;C=D.parent;N=C.parent/'reuse_closure'
S=D/'sources/seeed_dm_config'; src=S/'config/rebotarm_dm.yaml'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((S/'manifest.json').read_text(encoding='utf-8'))
row=next(x for x in manifest['rows'] if Path(x['path']).as_posix()=='config/rebotarm_dm.yaml')
assert sha(src)==row['sha256']
public=yaml.safe_load(src.read_text(encoding='utf-8'))
base=N/'software/DM_REFERENCE_CONFIG.json';config=json.loads(base.read_text(encoding='utf-8'))
assert len(public['joints'])==len(config['joints'])==7
assert [x['name'] for x in public['joints']]==['joint1','joint2','joint3','joint4','joint5','joint6','gripper']
assert [x['model'] for x in public['joints']]==['4340P']*3+['4310']*4
for i,(ref,new) in enumerate(zip(config['joints'],public['joints']),1):
    assert ref['motor_can_id_reference']==new['motor_id']==i
    assert ref['feedback_can_id_reference']==new['feedback_id']==i+16
    assert new['vendor']=='damiao'
    ref.update(model_reference=new['model'],model_assignment_status='BOUND_PUBLIC_SEEED_DM_CONFIG__NOT_AS_BUILT',reference_source={'commit':manifest['commit'],'path':row['path'],'sha256':row['sha256'],'upstream_joint_name':new['name']})
config['identity']='PINNED_PUBLIC_DM_MAPPING_NOT_AS_BUILT'
config['source_parent']={'path':str(base),'sha256':sha(base)}
config['public_mapping_source']={'repository':manifest['repository'],'commit':manifest['commit'],'url':row['url'],'sha256':row['sha256']}
config['enable_physical_io']=False
config['runtime_policy']={'auto_select_generic_rebotarm_yaml':False,'generic_yaml_current_target':'rebotarm_rs.yaml','import_reference_gains_as_operating_limits':False,'as_built_bindings_still_required':True}
out=D/'DM_REFERENCE_CONFIG.json';out.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
baud=config['serial_baud_candidate'];tx=30;rx=16
serial_source=N/'sources/motorbridge/motor_core/src/dm_serial.rs'
serial_text=serial_source.read_text(encoding='utf-8')
assert all(s in serial_text for s in ['TX_FRAME_LEN: usize = 30','RX_FRAME_LEN: usize = 16','DataBits::Eight','StopBits::One','Parity::None'])
rates=[]
for arm_hz,gripper_hz in [(500,500),(500,0),(250,50),(250,0),(100,20)]:
    cps=6*arm_hz+gripper_hz
    rates.append({'arm_rate_hz':arm_hz,'gripper_rate_hz':gripper_hz,'commands_per_second':cps,'TX_bytes_per_second':cps*tx,'TX_serial_utilization_8N1':cps*tx*10/baud,'RX_utilization_if_one_reply_per_command_8N1':cps*rx*10/baud,'TX_fits_ideal_no_overhead':cps*tx*10<=baud,'scope':'serial wire budget; scheduler/CAN/USB latency and actual feedback policy not measured'})
receipt={'schema':'DM_PUBLIC_REFERENCE_MAPPING_DELTA_V1','utc':datetime.now(timezone.utc).isoformat(),'status':'PASS_SEVEN_PUBLIC_DM_MODEL_ID_BINDINGS__DEPLOYMENT_NOT_AUTHORIZED',
 'source':config['public_mapping_source'],'parent':config['source_parent'],'child':{'path':str(out),'sha256':sha(out)},
 'previously_unbound_public_model_count':6,'now_bound_public_model_count':7,'as_built_bound':False,
 'generic_config_is_RS_and_must_not_be_autoloaded':yaml.safe_load((S/'config/rebotarm.yaml').read_text())['hardware_yaml']=='rebotarm_rs.yaml',
 'serial_budget':{'baud':baud,'framing':'8N1 configured explicitly in pinned dm_serial.rs','source_path':str(serial_source),'source_sha256':sha(serial_source),'tx_packet_bytes':tx,'rx_packet_bytes':rx,'full_duplex_separate_TX_RX':True,'maximum_ideal_commands_per_second':baud/(tx*10),'source_public_rate_hz':public['rate'],'rows':rates},
 'physical_io':0,'motor_limits_calibration_firmware_and_connector_binding_complete':False,
 'checks':{'seven_unique_ids':len({x['motor_can_id_reference'] for x in config['joints']})==7,'seven_feedback_ids':len({x['feedback_can_id_reference'] for x in config['joints']})==7,'three_4340P_four_4310':True,'physical_inhibit_retained':not config['enable_physical_io'],'unknown_actual_ratio_limits_preserved':all(x['motor_rad_per_joint_rad'] is None and x['mechanical_position_bounds_rad'] is None for x in config['joints'])}}
assert all(receipt['checks'].values())
(C/'results/DM_PUBLIC_REFERENCE_DELTA.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
with (D/'SERIAL_BUDGET.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rates[0]));w.writeheader();w.writerows(rates)
print(json.dumps({'status':receipt['status'],'mapping':[x['model_reference'] for x in config['joints']],'serial_budget':rates},ensure_ascii=False))
