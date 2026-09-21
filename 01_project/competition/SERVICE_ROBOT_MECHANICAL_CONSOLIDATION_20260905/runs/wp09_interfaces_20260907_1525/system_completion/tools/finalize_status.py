"""Bind actual accepted deltas without promoting the incomplete entire system."""
import csv,hashlib,json,shutil
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
C=Path(__file__).resolve().parents[1]
def read(rel):return json.loads((C/rel).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bind(rel):
    p=C/rel
    return {'path':rel,'sha256':sha(p)}
n=read('results/NATIVE_DELTA_DELIVERY.json')
e=read('results/ELECTRICAL_REFERENCE_DELIVERY.json')
m=read('results/MASS_ROLLFORWARD_873.json')
p=read('results/PARENT_PRESERVATION.json')
assert n['status']=='PASS_873_FIXED_POSE_NATIVE_DELTA_AND_PHYSICAL_RELOCATION_DELIVERY'
assert n['component_count_each']==873 and n['expected_solids_each']==1254
assert n['new_unique_native_parts_individually_cold_read']==138
assert n['archive_crc_verified'] and n['archive_entry_sha256_verified']
assert n['actual_all_1254_body_readback'] is False
assert n['top_level_container_count_each']==10 and n['unique_fixed_subassembly_files_in_archive']==19
assert n['actual_relocated_cold_state_count']==3
assert str(e.get('status','')).startswith('PASS')
assert p['status']=='PASS'
assert m['native_cold_receipt_binding_completed'] and m['native_cold_all_pass']
assemblies=[Path(n['assembly_paths'][s]) for s in ('service','parking','released')]
assert len(assemblies)==3
assert all(x.is_file() and x.stat().st_size>0 for x in assemblies)
history=C/'review/history/system_review_before_native_acceptance'
history.mkdir(parents=True,exist_ok=True)
for rel in ['review/SYSTEM_ACCEPTANCE_MATRIX.csv','review/SYSTEM_REVIEW_ZH.md','results/SYSTEM_ACCEPTANCE_REVIEW.json']:
    src=C/rel;dest=history/src.name
    if not dest.exists():shutil.copy2(src,dest)
matrix=C/'review/SYSTEM_ACCEPTANCE_MATRIX.csv'
rows=list(csv.DictReader(matrix.open(encoding='utf-8-sig',newline='')))
for row in rows:
    if row['id']=='H02':
        row.update(status='COMPLETE_SCOPED_SUBITEM',completed_evidence_scope='太阳翼/R01真实STEP与原生零件、873组件三态身份/变换/本地依赖冷核验及便携交付；以NATIVE_DELTA_DELIVERY实际回执为准',remaining_design='本轮增量交付子项关闭；全机电一致及未完成设计仍在H03和A-G',required_input='已绑定当前增量source与实际原生冷读',next_concrete_operation='保持本轮原生与来源hash，不重复重建未变对象',closure_evidence='results/NATIVE_DELTA_DELIVERY.json',evidence_paths=str(C/'results/NATIVE_DELTA_DELIVERY.json'))
    if row['id']=='H01':
        row['completed_evidence_scope']+='；另完成85件原样ECAD/DM迁移、47网表一致/地面板DRC/29项Python离线路径复验，见ELECTRICAL_REFERENCE_DELIVERY'
    if row['id']=='F01':
        row.update(object='873 实例质量责任归属和 R01 子账',completed_evidence_scope='873/873归属43个owner；400/872物理或代表实例有材料模型/整模块参考质量；全星质量仍未知',remaining_design='责任归属子项完成；472实例/30个owner数值未闭合，完整m/COM/I属于F02',next_concrete_operation='保持整模块质量只计一次；数值未知保留null，按F02完成材料/厂家质量绑定',closure_evidence='最终实例身份与3态原生冷读绑定；不把归属完整当数值质量完整',evidence_paths=str(C/'results/MASS_ROLLFORWARD_873.json'))
    if row['id']=='F02':
        row.update(completed_evidence_scope='最终873实例责任账已绑定；材料模型部分小计7.872303367396381kg，B601整模块4.5kg和84 CIC目录平均0.3024kg单列，均不冒充整星总量',remaining_design='472实例/30个owner数值未闭合；胶/新电源/真实推进及推进剂、完整COM/惯量与不确定性仍缺',evidence_paths=str(C/'results/MASS_ROLLFORWARD_873.json'))
    if row['id']=='H03':
        row['completed_evidence_scope']='705母版和873增量原生机械包均已实际冷读与搬迁；85份原生ECAD/DM参考文件原样迁移且47网表、地面板DRC和29项Python离线复验通过；完整机电功能设计仍未齐'
    updates={
      'C01':dict(completed_evidence_scope='GX11CAB正线切断、连续回流、辅助NO身份已锁；原厂25°C表的Release Time Max=12 ms已更正，旧typical描述保留勘误'),
      'C03':dict(completed_evidence_scope='实际71器件停止子电路、222已接脚/39网/183内部连接；420项检查及837项独立复核；120pF看门狗、双锁存及200V线圈MOSFET候选已实现到原理图',
        remaining_design='3.3/5.1V与MCU源未绑定；UCC输入吸收电流上界未知，需≤1.12765mA条件；CWD板漏电未计；母线测量/诊断与PCB及全温时序仍缺，整链100ms不通过',
        closure_evidence='实际KiCad网表及状态逻辑/器件计算；不是板级瞬态或实物功能安全证明',evidence_paths=str(C/'results/STOP_CIRCUIT_DELIVERY.json')),
      'D01':dict(completed_evidence_scope='四候选及C-POD同PN/Rev冲突保留；本轮再完成20项接口/上下界检查；0.50mNs MIB与<10ms阀响应分账'),
      'D02':dict(completed_evidence_scope='C-POD公开安装螺纹.112-40 UNC-2B已绑定，不再误认M3；PDU200 CH1/Reg0的源侧针位已绑定',
        remaining_design='总孔数/坐标/深度/保持载荷、实际喷口方向/命令映射/并发/推进器针表/CRC遥测与故障态仍未获得受控ICD',evidence_paths=str(C/'propulsion/resume_20260908/PROPULSION_INTERFACE_CONTRACT.json')),
      'E01':dict(completed_evidence_scope='系统原理图已集成实际71器件子页；94元件/96网/72条外部连接；191项实际网表与身份检查通过',
        remaining_design='接口分区一致性子项完成；实际系统ERC仍3项供源问题，完整功能电气未闭合',evidence_paths=str(C/'results/STOP_ECAD_INTEGRATION.json')),
      'E03':dict(completed_evidence_scope='保留29项Python历史测试；本轮实际加载官方cp313 Win64 MotorBridge0.5.3 DLL，18项ABI版本/空句柄/未绑定控制器生命周期与错误传播通过；独立155项复核',
        remaining_design='未本机重编Rust；原生MIT编码/串口后端与硬件I/O未执行。ctypes布局仅匹配reprC声明，未在DLL内部探测布局',closure_evidence='父版29项Python测试保留历史；当前18项真实原生ABI边界执行，physical_io=0；不扩大为MIT编码或串口后端通过',evidence_paths=str(C/'results/DM_NATIVE_VERIFICATION.json')),
      'E04':dict(completed_evidence_scope='Owner确认DM；Seeed锁定配置将J1-J3=4340P，J4-J6/夹爪=4310，ID1-7/反馈0x11-17；明确绕开默认RS通用配置。串行链路预算排除七轴500Hz',
        remaining_design='公开参考不等于出货实机；方向/传动比/零位/机械限位/针位视向/固件与星上CAN后端仍未绑定',evidence_paths=str(C/'results/DM_PUBLIC_REFERENCE_DELTA.json')),
      'E06':dict(completed_evidence_scope='STOP_CONTROL/STOP_MONITOR已由实际看门狗/逻辑/驱动/辅助反馈电路替代并接入系统原理图；24V和回流接线已定义',
        remaining_design='两辅助供源/MCU逻辑域/母线监测真实实现及保持/释放/姿控等全部反馈未齐，不能将接口信号名当可用观测',evidence_paths=str(C/'ecad/MASTER_FROM_TO.csv'))
    }
    if row['id'] in updates: row.update(updates[row['id']])
with matrix.open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
open_ids=[r['id'] for r in rows if r['status'] in ['INTERNAL_DESIGN_OPEN','EXTERNAL_INTERFACE_UNBOUND','NATIVE_DELTA_PENDING']]
audit=read('results/SYSTEM_ACCEPTANCE_REVIEW.json')
audit['original_snapshot_output_fields']={k:audit.pop(k) for k in ['output_files','root_in_flight_receipts_not_yet_credited'] if k in audit}
audit.update(status='REVIEW_UPDATED_WITH_ACTUAL_NATIVE_AND_ELECTRICAL_DELIVERY__SYSTEM_DESIGN_NOT_COMPLETE',
 updated_utc=datetime.now(timezone.utc).isoformat(),snapshot_scope='Original bounded review plus root binding of completed native873/electrical migration and mass ownership; earlier snapshot preserved.',
 work_package_status_counts=dict(Counter(r['status'] for r in rows)),open_work_package_ids=open_ids,required_design_open_count=len(open_ids),
 open_count_unit='remaining declared A-H design work packages; not atomic requirements or function percentage',
 delta_binding=[bind(r) for r in ['results/NATIVE_DELTA_DELIVERY.json','results/ELECTRICAL_REFERENCE_DELIVERY.json','results/MASS_ROLLFORWARD_873.json','results/STOP_ECAD_INTEGRATION.json','results/DM_NATIVE_VERIFICATION.json','results/PROPULSION_RESUME_20260908.json']])
audit['acceptance_fields_at_review_snapshot']['mass_assignment_coverage']['final_delta_percent']=100
audit['matrix_sha256_current']=sha(matrix)
audit['group_review']['H']['completed_subitems']=sorted(set(audit['group_review']['H'].get('completed_subitems',[])+['H02']))
audit['group_review']['H']['open_packages']=[x for x in audit['group_review']['H'].get('open_packages',[]) if x!='H02']
(C/'results/SYSTEM_ACCEPTANCE_REVIEW.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
review=C/'review/SYSTEM_REVIEW_ZH.md'
prior=(history/review.name).read_text(encoding='utf-8')
review.write_text('''# 实际增量交付后的更新

原生太阳翼/R01联合增量已由实际交付回执绑定，H02关闭；原生电气参考包的迁移复验亦已完成。最终873实例归属已结转。下面原始独立复核为生成时快照，其中“进行中/pending”仅代表该历史时刻；现行工作包状态以同目录SYSTEM_ACCEPTANCE_MATRIX.csv和results/DELIVERY_STATUS.json为准。

实际停止电路已实现到71器件原理图并完成191项系统网表检查；原生MotorBridge DLL已执行18项边界ABI测试。C03/E04/E06保留未满足的供源、实机接口、监测与PCB等责任；推进源侧接口补充亦不等于推进模块ICD完成。最终设计开放工作包仍为 '''+str(len(open_ids))+''' 项，完整功能覆盖率未由行数推算。

---

'''+prior,encoding='utf-8')
audit['output_files_current']=[bind('review/SYSTEM_ACCEPTANCE_MATRIX.csv'),bind('review/SYSTEM_REVIEW_ZH.md')]
(C/'results/SYSTEM_ACCEPTANCE_REVIEW.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
result={'schema':'WP09R_SYSTEM_COMPLETION_DELIVERY_V1','created_utc':datetime.now(timezone.utc).isoformat(),
 'status':'VERIFIED_NATIVE_ASSEMBLIES_STOP_SCHEMATIC_DM_ABI_AND_PROPULSION_INTERFACE_DELTA__SYSTEM_DETAILED_DESIGN_INCOMPLETE',
 'parent':'../reuse_closure','parent_preserved':True,
 'mechanical':{'component_count_each':n['component_count_each'],'expected_solids_each':n['expected_solids_each'],'evidence':bind('results/NATIVE_DELTA_DELIVERY.json'),
   'component_count_semantics':n['component_count_semantics'],'top_level_container_count_each':10,'unique_subassemblies':19,'actual_relocated_cold_states':3,
   'assembly_paths':[str(x.relative_to(C)) for x in assemblies],'instance_delta_added':168,'changed_existing_instances':152,
   'fixed_pose_native_delivery_passed':True,'whole_motion_or_strength_credit':False,'SW_mass_scalar_is_not_full_geometric_equivalence_test':True},
 'electrical_reference':{'evidence':bind('results/ELECTRICAL_REFERENCE_DELIVERY.json'),'source_files_unchanged':85,'nets_equal':47,'hardware_io':0,'native_Rust_executed':False,'system_ERC_open_errors':1},
 'electrical_resume':{'evidence':bind('results/STOP_ECAD_INTEGRATION.json'),'actual_schematic_components':94,'stop_subpage_components':71,'actual_system_nets':96,'external_master_connections':72,'integration_checks_passed':191,'system_ERC_open_errors':3,'PCB_layout_created':False,'scope':'Current actual two-sheet design; electrical_reference above is immutable earlier scope.'},
 'DM_native_resume':{'evidence':bind('results/DM_NATIVE_VERIFICATION.json'),'actual_native_Rust_ABI_executed':True,'checks_passed':18,'native_MIT_codec_executed':False,'native_serial_backend_executed':False,'hardware_io':0,'native_build_from_source_executed':False,'source_config_models_bound':True,'as_built_config_bound':False},
 'propulsion_resume':{'evidence':bind('results/PROPULSION_RESUME_20260908.json'),'checks_passed':20,'new_OEM_command_or_pin_bindings':0,'mechanical_thread':'.112-40 UNC-2B','source_side_power_endpoints_bound':True,'actual_wrench_allocation_closed':False},
 'required_design_open_count':len(open_ids),'design_open_count_unit':'remaining declared A-H work packages, not atomic requirements',
 'open_work_package_ids':open_ids,'unbound_critical_interface_count':None,'unsupported_design_assumption_count':None,'required_function_coverage':None,
 'unknown_count_policy':'No complete atomic inventory/end-to-end proof exists; null fails the completion condition and is not zero.',
 'flight_arm_power_design_closed':False,'stop_regeneration_design_closed':False,'propulsion_interface_and_capability_closed':False,
 'required_control_and_feedback_closed':False,'required_harness_and_installation_closed':False,
 'mass_assignment_coverage':1.0,'mass_assignment_scope':'873/873 responsibility ownership; unknown numerical masses remain null; not full mass/COM/inertia.',
 'mass_evidence':bind('results/MASS_ROLLFORWARD_873.json'),
 'thermal_structural_motion_design_checks_passed':False,'cad_ecad_bom_interface_consistency_passed':False,
 'reproducible_delivery_passed':False,'scoped_native_and_ECAD_reference_portability_passed':True,
 'whole_mechatronic_detailed_design_complete':False,'hardware_commissioning':'NOT_EXECUTED','flight_qualification':'NOT_CLAIMED',
 'physical_checks_executed':0,'physical_checks_registered':24,
 'evidence_index':[bind(r) for r in ['results/PORTABLE_DELIVERY.json','results/NATIVE_DELTA_DELIVERY.json','results/ELECTRICAL_REFERENCE_DELIVERY.json','results/INDEPENDENT_DELTA_REVIEW.json','results/MASS_ROLLFORWARD_873.json','results/POWER_COMPLETION_ANALYSIS.json','results/STOP_POLICY_TESTS.json','results/SYSTEM_ACCEPTANCE_REVIEW.json','results/PARENT_PRESERVATION.json']]}
(C/'results/DELIVERY_STATUS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'status':result['status'],'open_work_packages':len(open_ids),'native_assemblies':len(assemblies)}))
