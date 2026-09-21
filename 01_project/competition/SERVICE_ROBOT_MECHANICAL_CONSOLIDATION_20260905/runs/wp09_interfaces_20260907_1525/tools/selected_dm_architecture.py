"""Implement the owner's DM confirmation and the selected ground-prototype architecture."""
from pathlib import Path
import json,csv,hashlib
R=Path(__file__).resolve().parents[1]
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
selection=R/'research/FINAL_SELECTION_DM.json';assert selection.exists()
owner={'B601_variant':'DM','evidence_type':'USER_DIRECT_CONFIRMATION','user_text':'B601是DM版本，其他请你参考公开资料直接帮助我得出最佳选择即可','selection_authority':'ASSISTANT_MAY_SELECT_OTHER_ENGINEERING_REFERENCES_FROM_PUBLIC_SOURCES','other_actual_hardware_purchased':None}
(R/'inputs/OWNER_DM_CONFIRMATION.json').write_text(json.dumps(owner,ensure_ascii=False,indent=2),encoding='utf-8')
d=dict(status='SELECTED_ENGINEERING_REFERENCE_ARCHITECTURE_NOT_AS_BUILT',owner_confirmation_sha256=sha(R/'inputs/OWNER_DM_CONFIRMATION.json'),selection_sha256=sha(selection),
 arm_branch=dict(source='MEAN WELL RSP-500-24',location='EXTERNAL_GROUND_SUPPORT',voltage_V=24,rated_current_A=21,reference_load_A=15,reference_load_is_measured_peak=False,source_terminals={'positive_group':[4,5,6],'negative_group':[1,2,3],'connector':'TB2'},protective_disconnect={'device':None,'rating':None},destination='B601 DM',actual_destination_contact_map=None,regeneration_absorption=None),
 low_power_branch=dict(battery='GomSpace BPX 8S1P 100 Wh class',recommended_window_V=[23.6,32],public_discharge_limit_A=6,distribution='P60/PDU200 with complete Dock option TBD',mips_design_option='Reg0 CH1 12 V',pdu_channel_limit_A=2),
 propulsion=dict(reference='VACCO X14029003-1 Rev6/15',present_implementation='UNPRESSURIZED_GEOMETRIC_INTERFACE_MOCKUP',flight_unit_purchase_selected=False,RS422_pinmap=None),
 deferred_internal_arm_conversion=dict(reference='2 x TDK i7C4W012A050V-PC3-R',connected_in_current_architecture=False,battery_power_compatibility_with_15A_output=False),
 ground_relations={'arm_power_return_to_logic_reference':None,'arm_power_return_to_chassis':None,'shield_termination':None,'CAN_isolation':None,'RS422_isolation':None},
 actual_fabrication_complete=False,energization_authorized_by_design=False,flight_release=False)
(R/'ecad/SELECTED_DM_ARCHITECTURE.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
rows=[dict(net='ARM_24V',from_device='RSP-500-24',from_connector='TB2',from_contact_group='4;5;6',selected_contact=None,to_device='protective disconnect then B601 DM',to_connector='XT30 2+2 exact shipping revision unbound',to_contact=None,conductor_mm2=None,current_profile=None,length_mm=None,status='SOURCE_GROUP_KNOWN_DESTINATION_AND_PROTECTION_OPEN'),
dict(net='ARM_POWER_RETURN',from_device='RSP-500-24',from_connector='TB2',from_contact_group='1;2;3',selected_contact=None,to_device='B601 DM',to_connector='XT30 2+2 exact shipping revision unbound',to_contact=None,conductor_mm2=None,current_profile=None,length_mm=None,status='DO_NOT_AUTO_BOND_TO_CHASSIS_OR_SIGNAL_REFERENCE'),
dict(net='ARM_CAN_H',from_device='Seeed 100011896',from_connector=None,from_contact_group=None,selected_contact=None,to_device='Seeed 100045091 / B601 DM',to_connector='GH1.25 2pin family only',to_contact=None,conductor_mm2=None,current_profile=None,length_mm=None,status='EXACT_CAVITY_POLARITY_UNBOUND'),
dict(net='ARM_CAN_L',from_device='Seeed 100011896',from_connector=None,from_contact_group=None,selected_contact=None,to_device='Seeed 100045091 / B601 DM',to_connector='GH1.25 2pin family only',to_contact=None,conductor_mm2=None,current_profile=None,length_mm=None,status='EXACT_CAVITY_POLARITY_UNBOUND')]
with (R/'ecad/DM_SELECTED_FROM_TO.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
text='''# DM 工程样机供电架构

用户确认 DM 后，采用外置 RSP-500-24 驱动机械臂；BPX 8S + P60/PDU 仅承担低功率航电与推进接口试验。所选为工程参考，已采购器件及出货修订尚未核对。

```mermaid
flowchart LR
  GSE[外置 RSP-500-24\n24 V / 21 A] --> PROT[专用保护与断电接口\n元件与整定待定]
  PROT --> DM[B601 DM\n15 A 是电源参考要求]
  USB[USB-CAN 100011896] --> CAN[分线板 100045091\n针脚核对未完成]
  CAN --> DM
  BPX[BPX 8S1P\n最大放电 6 A] --> P60[P60/PDU200\n完整 Dock 与选件待定]
  P60 --> AV[低功率航电]
  P60 --> MIPS[12 V 推进支路参考\n当前为未加压接口样件]
  CPU[推进控制端\n实际接口待定] -. RS-422 .-> MIPS
```

不将地面电源算作星内体积或飞行硬件；不把分开供电视作隔离已完成。电源回流、信号参考、机壳搭接与屏蔽端接分别保留设计字段。RSP 的感测/遥控 CN100 不承担主负载电流。

原厂端子组已知，但本图还不是针脚级接线图。主线两条已选需求见 `DM_SELECTED_FROM_TO.csv`；推进固定段见 `From-To.csv`、V6 路线图及预制检验单。未知单元保持空值，完整可裁线支路仍为 0。实际硬件上电、压接、采购和压力操作均未执行。

器件依据与电流反例见 [最终选型研究](../research/FINAL_SELECTION_DM_ZH.md)。当前 82 个几何实例覆盖推进支架、供电托盘、舱板与预布线；不因此获得实际 PCB、推进电连接器或线夹应力释放完成信用。
'''
(R/'docs/SELECTED_DM_ARCHITECTURE_ZH.md').write_text(text,encoding='utf-8')
print('DM confirmation and selected architecture written')
