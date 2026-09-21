from pathlib import Path
import json, hashlib, csv, shutil

D=Path(__file__).resolve().parents[1]
ROOT=D.parents[1]
R1=ROOT/'20_engineering/SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919'
R2=ROOT/'20_engineering/SERVICE_STAR_INTERNAL_HARNESS_ORBIT_R2_20260919'
WP=ROOT/'01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):
    p=D/p;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def table(p,rows):
    with (D/p).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

for sub in ['inputs','results','docs','cad','views']: (D/sub).mkdir(exist_ok=True)
source_files=[R1/'inputs/NEUTRAL_SOURCE_MAP.json',R1/'inputs/INTEGRATED_ASSEMBLY_PLAN.json',R2/'inputs/SOURCE_LOCAL_BOUNDS.json',R2/'inputs/HARNESS_CONNECTION_MATRIX.json',R2/'inputs/ELECTRICAL_CURRENT_BASELINE.json',WP/'power/DM_BUS_VOLTAGE_BINDING.json',WP/'power/POWER_CHAIN_SELECTION.json',WP/'sources/official_dm_motor.yaml',WP/'coupled_closure/HANDOFF_LATEST.json']
for name in ['dm4310_v1_1_manual_v1_0.pdf','dm4340p_manual_v1_0.pdf','DM4310_Default_Parameters.txt','DM4340P_Default_Parameters.txt']:
    p=WP/'sources'/name;shutil.copyfile(p,D/'sources'/name);source_files.append(p)
manifest=read(WP/'sources/REGEN_SCREEN_SOURCE_MANIFEST.json')
write('sources/LOCAL_MANUAL_PROVENANCE.json',[x for x in manifest if x.get('file') in [p.name for p in source_files]])
public=read(D/'sources/PUBLIC_SOURCE_MANIFEST.json')
baseline=read(R2/'inputs/ELECTRICAL_CURRENT_BASELINE.json')
assert sha(baseline['current_xml'])==baseline['current_xml_sha256'];source_files.append(Path(baseline['current_xml']))
write('inputs/SOURCE_LOCK.json',{'schema':'R3_INPUT_LOCK_V1','files':[{'path':str(p),'sha256':sha(p)} for p in source_files],'public_repositories':public['repositories']})
write('inputs/DESIGN_ASSUMPTIONS.json',{'schema':'R3_USER_SCOPED_ASSUMPTIONS_V1','user_scope':'未采购；参考B601；假设可连接服务星主机；先设计线缆连接和控制板预留','ground_candidate':True,'host_interface_available':'USER_AUTHORIZED_DESIGN_ASSUMPTION_NOT_VERIFIED_HARDWARE','host_protocol_candidate':'dedicated Classic CAN 1 Mbit/s; dedicated gateway if host differs','host_real_pinout':None,'controller_board_MPN':None,'physical_hardware_connected':False,'flight_qualified':False,'manufacturing_release':False,'scope_excludes':['元件级接口板电路','原有MAIN/AUX/STOP的改板','整臂动态布线定型','实物上电','飞行资格认定']})
joints=[]
for i in range(1,8):
    joints.append({'node':'J'+str(i) if i<7 else 'GRIPPER','role':'arm_joint' if i<7 else 'gripper','model_family':'DM4340P' if i<=3 else 'DM4310','repository_order_variant':'V4 / 24 V requested','quantity':1,'driver_location':'INTEGRATED_IN_JOINT','CAN_ID':i,'feedback_ID':16+i,'design_bus_V':24,'as_built_revision':None,'V4_controlled_manual':None,'rated_bus_current_A':None,'flight_qualified':False})
write('inputs/B601_DRIVER_BASELINE.json',{'schema':'R3_B601_DESIGN_CANDIDATE_V1','joints':joints,'evidence':'pinned B601 BOM V4 quantities + pinned SDK joint map; legacy OEM manuals show integrated driver','CAN_bitrate_bps':1000000,'serial_bridge_baud_not_CAN_bitrate':921600,'historical_UV15_OV32_are_guaranteed_operating_range':False,'TIMEOUT0_is_safety_verified':False,'public_config_is_flash_authority':False,'V4_specific_ratings_confirmed':False})
table('docs/B601_JOINT_MAP.csv',joints)
rows=read(R2/'inputs/HARNESS_CONNECTION_MATRIX.json')['rows']; old={x['id']:x for x in rows}
links=[]
for id in ['A07','A08','A09','A10','C01','C02','C03','C04']:
    x=old[id];links.append({'id':id,'from':x['from']['endpoint'],'to':x['to']['endpoint'],'net':x['net'],'status':'INHERITED_LOGICAL_CONNECTION','physical_pin_verified':False,'wire_MPN':None,'cut_length_mm':None})
pins=[
 {'port':'R3-JHOST','pin':1,'signal':'CAN_H_HOST','domain':'HOST_CAN','direction':'bidirectional'},
 {'port':'R3-JHOST','pin':2,'signal':'CAN_L_HOST','domain':'HOST_CAN','direction':'bidirectional'},
 {'port':'R3-JHOST','pin':3,'signal':'HOST_CAN_REFERENCE','domain':'HOST_CAN','direction':'reference'},
 {'port':'R3-JHOST','pin':4,'signal':'SHIELD_CHASSIS_RESERVATION','domain':'CHASSIS','direction':'shield'},
 {'port':'R3-JARM','pin':1,'signal':'WP10_ARM_BUS_PLUS','domain':'ARM_POWER','direction':'to_arm'},
 {'port':'R3-JARM','pin':2,'signal':'WP10_ARM_RETURN','domain':'ARM_POWER','direction':'return'},
 {'port':'R3-JARM','pin':3,'signal':'WP10_LEGACY_075','domain':'ARM_CAN','direction':'bidirectional'},
 {'port':'R3-JARM','pin':4,'signal':'WP10_LEGACY_076','domain':'ARM_CAN','direction':'bidirectional'},
 {'port':'R3-JLOGIC','pin':1,'signal':'CTRL_LOGIC_SUPPLY_RESERVED','domain':'CTRL_LOGIC','direction':'input'},
 {'port':'R3-JLOGIC','pin':2,'signal':'CTRL_LOGIC_RETURN_RESERVED','domain':'CTRL_LOGIC','direction':'return'},
 {'port':'R3-JSAFE','pin':1,'signal':'INHIBIT_REQUEST_RESERVED','domain':'STOP_INTERFACE','direction':'to_existing_STOP'},
 {'port':'R3-JSAFE','pin':2,'signal':'STOP_STATE_RESERVED','domain':'STOP_INTERFACE','direction':'from_existing_STOP'},
 {'port':'R3-JSAFE','pin':3,'signal':'STOP_REFERENCE_RESERVED','domain':'STOP_INTERFACE','direction':'reference'},
 {'port':'R3-JSAFE','pin':4,'signal':'SPARE_DO_NOT_CONNECT','domain':'NONE','direction':'none'}]
for x in pins:x.update({'pin_number_scope':'R3_DESIGN_ONLY_NOT_OEM_PIN_NUMBER','physical_pin_verified':False,'connector_MPN':None})
write('inputs/INTERFACE_CONNECTIONS.json',{'schema':'R3_B601_FUNCTIONAL_ICD_V1','inherited_R2_links':links,'proposed_project_pin_assignments':pins,'wiring_release':False,'OEM_XT30_contact_numbering':None,'reserved_logic_voltage_V':None,'power_rule':'JARM power is a separately sized protected bypass path from J203; not routed through an unselected signal PCB','isolation_rule':'HOST_CAN and ARM_CAN need a gateway or a separately reviewed direct-bus option; no connection between domains is silently added','forbidden_short_pairs':[['WP10_ARM_RETURN','WP10_INPUT_RETURN'],['WP10_AUX_PROTECT_RTN','WP10_INPUT_RETURN'],['HOST_CAN_REFERENCE','WP10_ARM_RETURN'],['SHIELD_CHASSIS_RESERVATION','WP10_ARM_RETURN']],'forbidden_pair_scope':'R3 adapter adds none; not a claim that all upstream domains lack intentional connections','STOP_rule':'reserved handshake only, no bypass or new enable command; hard STOP/K1 remains upstream','physical_connector_mating_transform':None})
table('docs/PROPOSED_INTERFACE_PINS.csv',pins)
cables=[
 {'id':'R3-H01','from':'assumed service-star host','to':'R3-JHOST','conductors':'CAN_H + CAN_L twisted pair, reference, shield reservation','quantity':1,'route_status':'LOGICAL_ONLY','length_mm':None,'spec_basis':'dedicated CAN design assumption'},
 {'id':'R3-H02','from':'J203 / existing protected arm supply','to':'R3-JARM power path','conductors':'ARM_BUS_PLUS / ARM_RETURN','quantity':1,'route_status':'R2 A07-A10 retained; full S endpoints unbound','length_mm':None,'spec_basis':'no bypass of K1 or regenerative brake'},
 {'id':'R3-H03','from':'CAN interface / SEP','to':'R3-JARM CAN path','conductors':'CAN_H / CAN_L','quantity':1,'route_status':'R2 C01-C04 retained','length_mm':None,'spec_basis':'1 Mbit/s Classic CAN candidate'},
 {'id':'R3-H04','from':'J1','to':'J2','conductors':'OEM XT30(2+2) integrated power + CAN','quantity':1,'route_status':'B601 chain topology; installed length not assigned','length_mm':None,'spec_basis':'OEM V4 mating pin drawing required'},
 {'id':'R3-H05','from':'J2','to':'J3','conductors':'OEM XT30(2+2) integrated power + CAN','quantity':1,'route_status':'B601 chain topology; installed length not assigned','length_mm':None,'spec_basis':'OEM V4 mating pin drawing required'},
 {'id':'R3-H06','from':'J3','to':'J4','conductors':'OEM XT30(2+2) integrated power + CAN','quantity':1,'route_status':'B601 chain topology; installed length not assigned','length_mm':None,'spec_basis':'OEM V4 mating pin drawing required'},
 {'id':'R3-H07','from':'J4','to':'J5','conductors':'OEM XT30(2+2) integrated power + CAN','quantity':1,'route_status':'B601 chain topology; installed length not assigned','length_mm':None,'spec_basis':'OEM V4 mating pin drawing required'},
 {'id':'R3-H08','from':'J5','to':'J6','conductors':'OEM XT30(2+2) integrated power + CAN','quantity':1,'route_status':'B601 chain topology; installed length not assigned','length_mm':None,'spec_basis':'OEM V4 mating pin drawing required'},
 {'id':'R3-H09','from':'J6','to':'GRIPPER','conductors':'OEM XT30(2+2) integrated power + CAN','quantity':1,'route_status':'B601 chain topology; installed length not assigned','length_mm':None,'spec_basis':'OEM V4 mating pin drawing required'},
 {'id':'R3-H10','from':'R3-JARM','to':'J1 input','conductors':'OEM XT30(2+2) compatible hybrid feed','quantity':1,'route_status':'functional termination only; no complete CAD route','length_mm':None,'spec_basis':'branch current sums downstream; connector-through current unknown'},
 {'id':'R3-H11','from':'assumed logic supply','to':'R3-JLOGIC','conductors':'logic supply / return','quantity':1,'route_status':'RESERVED_NO_VOLTAGE_ASSIGNED','length_mm':None,'spec_basis':'selection follows host ICD'},
 {'id':'R3-H12','from':'R3-JSAFE','to':'existing STOP interface boundary','conductors':'inhibit request / state / reference','quantity':1,'route_status':'RESERVED_NO_ELECTRICAL_CONNECTION_AUTHORIZED','length_mm':None,'spec_basis':'logic levels, isolation and STOP pin correspondence unbound'}]
write('inputs/CABLE_CONNECTION_PLAN.json',{'schema':'R3_CABLE_TOPOLOGY_V1','records':cables,'records_are_not_additive_to_R2_BOM':True,'OEM_harness_reference_pack':[{'nominal_mm':350,'both_angled_qty':2,'one_angled_one_straight_qty':1},{'nominal_mm':200,'both_angled_qty':3,'custom_both_straight_qty':1}],'OEM_pack_lengths_are_current_spacecraft_cut_lengths':False,'all_joint_endpoints_are_designed_logical_nodes':True})
table('docs/CABLE_CONNECTION_PLAN.csv',cables)
board={'schema':'R3_BOARD_SPACE_RESERVATION_V1','replaces_functional_proxy':'equipment_arm_drive','source_proxy_role':'SIMPLIFIED_PROXY','source_proxy_budget_mass_kg':0.8,'new_physical_mass_kg':None,'frame':'S_mm','reserved_box_min':[-142.5,-83,-6],'reserved_box_max':[-57.5,-13,34],'PCB_min':[-130,-68,-1.6],'PCB_size':[60,40,1.6],'component_height_mm':18,'PCB_hole_centers_S_mm':[[-125,-63,0],[-75,-63,0],[-125,-33,0],[-75,-33,0]],'PCB_hole_diameter_mm':3.2,'mounting_holes_are_candidate':True,'source_structure_cut':False,'native_assembly_modified':False,'physical_board_selected':False,'PCB_material_assignment':None,'reserved_ports':[{'name':'JHOST','center':[-80,-24,5],'size':[12,8,8]},{'name':'JARM','center':[-118,-24,5],'size':[12,8,8]},{'name':'JLOGIC','center':[-90,-72,4],'size':[8,8,6]},{'name':'JSAFE','center':[-110,-72,4],'size':[12,8,6]}],'route_radius_mm':2,'route_OD_mm':3,'route_radius_scope':'display geometry within reserved unit, not OEM bending qualification','connector_exit_plane_Y_mm':-13,'installation_and_tool_clearance_validated':False}
write('inputs/BOARD_RESERVATION.json',board)
print('R3 contracts generated; no upstream files changed.')
