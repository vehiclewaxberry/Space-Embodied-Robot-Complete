"""Summarize completed WP10 subitems without promoting the incomplete system."""
from pathlib import Path
import csv,json,hashlib,html
from collections import Counter
from datetime import datetime,timezone
D=Path(__file__).resolve().parents[1];C=D.parent/'wp09_interfaces_20260907_1525/system_completion'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def bind(p):return {'path':str(p),'sha256':sha(p)}
base=read(D/'results/INPUT_BASELINE.json')
elec=read(D/'results/STOP_ECAD_INTEGRATION.json')
bom=read(D/'results/STOP_BOM_INTEGRATION.json')
mi=read(D/'mechanical_intake/INTAKE_VERIFICATION.json')
rr=read(D/'research_intake/RESEARCH_READINESS.json')
rv=read(D/'research_intake/RESEARCH_CONTRACT_VALIDATION.json')
er=read(D/'review/STOP_SUPPLY_INDEPENDENT_REVIEW.json')
inertia=read(D/'mechanical_inertia/MATERIAL_INERTIA_DELIVERY.json')
assert base['files_checked']==2669 and base['parent_mutations']==0
assert elec['actual_components']==99 and elec['actual_nets']==97 and elec['external_master_rows']==72
assert elec['checks_passed']==194 and bom['actual_schematic_refs']==99
assert er['checks_passed']==er['checks_total']==494
assert mi['instance_count']==873 and mi['numeric_mass_instance_count']==390
assert mi['whole_arm_only_covered_instances']==10 and mi['physical_dynamics_ready'] is False
assert rr['current_873_hardware_predictive_model_ready'] is False
assert rv['upstream_raw_pin_mismatches']==29
assert inertia['status']=='PASS_PARTIAL_MATERIAL_INERTIA_SUPPLEMENT__NO_COMPLETE_SPACECRAFT_MODEL'
assert inertia['instance_count']==inertia['target_instance_count']==306
assert inertia['unique_source_count']==inertia['successful_unique_source_count']==237 and not inertia['failed_unique_sources']
assert inertia['whole_spacecraft_inertia_complete'] is False and inertia['whole_spacecraft_mass_kg'] is None
publication=read(D/'review/MATERIAL_PUBLICATION_CHECK.json')
assert publication['status']=='PASS_EXACT_INERTIA_PUBLICATION_SCOPE_AND_INDEPENDENT_SUBSET_SUMS'
assert publication['source_receipt']['sha256']==sha(D/'mechanical_inertia/MATERIAL_INERTIA_DELIVERY.json')
assert publication['checks_passed']==publication['checks_total'] and publication['whole_spacecraft_model_complete'] is False
source_bind=read(D/'ecad/STOP_INTEGRATION_BINDING.json')
assert source_bind['child_subpage_source_sha256']==sha(D/'electrical/wp09_stop_circuit.kicad_sch')
parameter_entry={'schema':'WP10_PARAMETER_INPUT_ENTRY_V1','purpose':'Versioned source intake plus computed material-inertia supplement; not a complete dynamics model',
 'read_order':[{'role':'instance_identity_units_poses_and_original_accounting','artifact':bind(D/'mechanical_intake/PARAMETER_PACKET.json')},
 {'role':'computed_material_inertia_for_explicitly_listed_instances','artifact':bind(D/'mechanical_inertia/MATERIAL_INERTIA_DELIVERY.json')}],
 'merge_rules':['Match exact instance IDs and source geometry SHA; do not merge by visual name alone',
 'The supplement applies only to its declared material-model instances; preserve all other unknown inertias',
 'Material-derived mass and original mass are alternative model evaluations, not additive payloads; retain method differences',
 'Do not distribute the B601 whole-arm mass over links or add whole-module mass again to its children',
 'Use SI tensors at the stated COM and in the stated frame; use the actual kinematic tree to group rigid instances'],
 'whole_spacecraft_mass_kg':None,'whole_spacecraft_COM_m':None,'whole_spacecraft_inertia_kg_m2':None,
 'kinematic_tree_verified':False,'physical_dynamics_ready':False,'native_CAD_material_properties_updated':False}
(D/'MECHANICAL_PARAMETER_ENTRY.json').write_text(json.dumps(parameter_entry,ensure_ascii=False,indent=2),encoding='utf-8')
rows=list(csv.DictReader((C/'review/SYSTEM_ACCEPTANCE_MATRIX.csv').open(encoding='utf-8-sig')))
updates={
 'C03':{'completed_evidence_scope':'76器件真实子页；TSR1-2433/2450静态供源、TC4420CAT输入电流边界与24V辅助触点连接；440设计检查和494独立检查',
 'remaining_design':'纹波/启动/瞬态及15.7/13.5mV恢复裕度、Schmitt连续电压域阈值、棕断行为、MCU/母线健康、PCB热布局与全链100ms仍未闭合',
 'evidence_paths':str(D/'electrical/README.md')},
 'E01':{'completed_evidence_scope':'新系统99器件/97网/72外部连接；194实际网表/身份检查；107行分层BOM与99ref对应',
 'remaining_design':'保留2项抽象保护/开关后电源驱动ERC诊断，不加PWR_FLAG；ERC数量不代表功能覆盖', 'evidence_paths':str(D/'results/STOP_ECAD_INTEGRATION.json')},
 'E06':{'completed_evidence_scope':'两路实际辅助稳压/预负载/驱动及24V湿润反馈已接入，J101.1/.2改为测试输出并禁止外供',
 'remaining_design':'供源动态与掉电证明、MCU电压域和实际健康观测、连接器/PCB及其他设备状态反馈未齐',
 'evidence_paths':str(D/'electrical/STOP_PORT_MAP.json')},
 'F01':{'completed_evidence_scope':'873实例43owner已完成SI单位/三态位姿来源接入；390个直接质量+10个B601整模块覆盖，原400覆盖口径保留',
 'remaining_design':'归属及数据入口完成；整B6014.5kg不可平均分配为各link，未知物性继续F02',
 'evidence_paths':str(D/'mechanical_intake/PARAMETER_PACKET.json')},
 'F02':{'completed_evidence_scope':'当前三态SI参数包已形成，并补充已有材料/真实几何的惯性提取；新增补充不改写封存父账',
 'remaining_design':'B601逐link分布、设备包络/平均重量的真实惯性、全运动树/刚体分组及全星COM/I/推进剂状态仍未闭合',
 'evidence_paths':str(D/'mechanical_inertia/MATERIAL_INERTIA_DELIVERY.json')},
 'H03':{'completed_evidence_scope':'873叶原生包继承；本轮99元件系统图/72线主表/107行BOM及参数/研究接入口均有版本绑定',
 'remaining_design':'停止PCB/安装件、全部真实线束/图纸/控制和推进接口及整机物性仍未齐；不能以子包完整性宣布全部完成',
 'evidence_paths':str(D/'results/DELIVERY_DECISION.json')}
}
for row in rows:
    if row['id'] in updates:row.update(updates[row['id']])
matrix=D/'SYSTEM_CLOSURE_MATRIX.csv'
with matrix.open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
open_rows=[r for r in rows if r['status'] in ['INTERNAL_DESIGN_OPEN','EXTERNAL_INTERFACE_UNBOUND']]
assert len(open_rows)==23
decision={'schema':'WP10_ENGINEERING_DELIVERY_AND_RESEARCH_ADVISORY_V1','utc':datetime.now(timezone.utc).isoformat(),
 'status':'VERIFIED_ENGINEERING_DELTAS_AND_RESEARCH_INPUTS__FULL_SYSTEM_DELIVERY_NOT_READY',
 'user_target':'可装配工程样机设计并评估转入航天动力学/控制/智能抓取避障/强化学习研究',
 'complete_mechatronic_design_deliverable':False,'complete_assembly_ready_prototype_design':False,'flight_functional_system_closed':False,
 'flight_qualification_not_used_as_precondition_for_theoretical_research':True,'full_current873_dynamics_ready':False,
 'work_package_counts':dict(Counter(r['status'] for r in rows)),'remaining_declared_work_packages':23,
 'counts_are_not_atomic_requirements_or_completion_percent':True,'remaining_critical_atomic_interfaces':None,
 'delivered_scopes':['Inherited verified 873-leaf native static CAD','Actual revised 76-part stop subcircuit and 99-part system schematic',
 '72-wire master and 107-row hierarchical BOM','873-instance SI source/pose/parameter intake','Computed-from-CAD material-model inertia supplement (not hardware measurements)','Read-only historical evidence/source audit and research contracts'],
 'research_advice':{'can_begin_now':['原结果证据分析与输入版本梳理','物理单位/坐标/参数及运动树建模','声明假设的动力学方程与验证合同','确定性规划及后续RL的问题、边界与评价设计'],
 'next_recommended_phase':'PARAMETER_BOUND_FLOATING_BASE_MODEL_AND_CONSERVATION_VALIDATION',
 'cannot_claim_now':['当前873构型已具有经验证的真实动力学模型','旧PASS自动适用于当前硬件','当前checkout可逐位复现所有历史结果','控制或RL对当前机器人已有效','整机可制造/安全上电/推进或飞行放行'],
 'large_scale_current_hardware_RL_readiness':False,'simulation_executed_this_turn':False,'training_executed_this_turn':False,
 'advisory_not_a_new_authority_or_scientific_gate':True},
 'parent_mechanical_geometry_modified':False,'native_CAD_assemblies_rebuilt_this_turn':False,'geometry_reading_for_inertia_executed':True,
 'material_inertia_delivery':{'instances':306,'unique_STEP_sources':237,'partial_material_mass_kg':inertia['partial_mass_kg'],
 'whole_spacecraft_mass_kg':None,'whole_spacecraft_inertia_complete':False,'remaining_physical_instances_without_complete_model':inertia['remaining_physical_instances_without_complete_model']},
 'hardware_io':0,'manufacturing_release':False,'source_hash_drifts_found':29,'raw_pins_checked':107,
 'evidence':[bind(D/p) for p in ['results/INPUT_BASELINE.json','results/STOP_ECAD_INTEGRATION.json','results/STOP_BOM_INTEGRATION.json',
 'electrical/results/STOP_SUPPLY_FINAL_BINDING.json','review/STOP_SUPPLY_INDEPENDENT_REVIEW.json','mechanical_intake/INTAKE_VERIFICATION.json',
 'mechanical_intake/CONTRACT_TESTS.json','mechanical_inertia/MATERIAL_INERTIA_DELIVERY.json','research_intake/RESEARCH_READINESS.json',
 'research_intake/RESEARCH_CONTRACT_VALIDATION.json','results/ECAD_RELOCATION.json','review/MATERIAL_PUBLICATION_CHECK.json',
 'review/ELECTRICAL_RELEASE_SCOPE_REVIEW.json','MECHANICAL_PARAMETER_ENTRY.json','SYSTEM_CLOSURE_MATRIX.csv']]}
(D/'results/DELIVERY_DECISION.json').write_text(json.dumps(decision,ensure_ascii=False,indent=2),encoding='utf-8')
previous='../wp09_interfaces_20260907_1525/system_completion'
text=f"""# WP10 机电设计补全与研究交接

**现在还不能完整交付可装配工程样机的全部机电设计。可以进入模型建立与验证、理论和算法研究准备，并让动力学需求反向支撑机电收束。** 当前873构型尚不能作为已验证的真实硬件数字身体，用于宣称控制或RL性能。

[统一查看页](REVIEW.html) · [机器判定](results/DELIVERY_DECISION.json) · [完整工作包状态](SYSTEM_CLOSURE_MATRIX.csv) · [机电与研究共同输入](ENGINEERING_RESEARCH_LOOP_ZH.md)

## 本轮真正完成的设计工作

- 停止电路从71增至76器件，接入TSR1-2433/2450辅助供源、24Ω/39Ω预负载及TC4420CAT驱动。实际子页234已接脚/40网，440项设计检查、494项独立检查通过，范围为0–50°C地面静态候选。已关闭原UCC输入电流上界未知这一局部问题。
- 修订系统原理图包含99器件/97网、72条外部接线；194项网表与身份检查通过。BOM为107行，99个实际ref一一对应。J101.1/.2是内部电源测试端，禁止接外部供源。
- 从873实例/43owner构建三态SI参数入口，实际核对1081份几何文件SHA，完成25146项来源/坐标检查，以及31项单位、惯量和记账测试（其中包含负控）。
- 完成237份唯一STEP源、306个材料模型实例的质量/质心/惯量提取，提供三态SI参数及材料部分汇总；部分质量约7.872303 kg，不是整星质量。结果见[材料模型惯性补充](mechanical_inertia/README_ZH.md)。它是模型计算，不是实测；不会把整臂参考质量或设备包络配成实心。结果交付为SI参数文件，本轮未写回SLDPRT材料/质量属性，原生总装仍使用封存版本。
- 核对26份研究来源及107条历史raw SHA：78匹配、29漂移。旧结果仍可分析，当前目录不能据旧PASS宣称全部精确复现。文档合同120项检查与15个负控只证明合同和证据身份。

[两页实际电气原理图](ecad/exports/WP09_SYSTEM_AND_STOP.pdf) · [可编辑KiCad](ecad/wp09_system.kicad_sch) · [主接线表](ecad/MASTER_FROM_TO.csv) · [分层BOM](ecad/MASTER_BOM.csv) · [电路计算与限制](electrical/README.md)

计数说明：76个停止子页位号包含71个选型器件和5个逻辑接口；99个位号还包含23个顶层设备/边界。97个导出网络含16个显式NC隔离网（其余81个为非NC网络）。它们是原理图统计，不是已装配实物数量。

## “完整交付”还差什么

仍有23项开放工作包，包含真实内部设计责任，不只是到货后实测：星上高功率充电/BMS/均流/热、推进受控ICD与任务分配、逐运动link物性和驱动能力、完整线束/太阳翼连接/承托、PCB与停止动态/反馈，以及整机热/强度/连续运动。

辅助电源的DC恢复裕度约15.7/13.5mV，原厂纹波只有典型值；Schmitt输入跨整个供电域的阈值保证、棕断/启动/瞬态、布局散热和100ms完整停止链仍未证实。保留2项保护/开关后源节点的ERC诊断，已单列[解释](ecad/ERC_DISPOSITION.json)，不靠供源标志或忽略规则清零，也不以ERC数量代替功能覆盖。

原质量账“400项覆盖”中，390项有逐实例数值，另10项B601连杆只由整臂4.5kg共同覆盖。新增材料模型惯性不能补齐整臂分布、真实设备惯性或运动树。完整模型应按刚性link正确合并，**不是要求将每个螺母都建成独立动力学自由度**。读取时按[统一参数入口](MECHANICAL_PARAMETER_ENTRY.json)绑定原实例清单与新增材料惯性；两种质量算法结果不能相加，其他设备未知项继续保留。

## 可以进入哪一段研究

|阶段|现在的出口|工程结论边界|
|---|---|---|
|1. 模型身份与参数|用本次SI入口建立link/关节/惯量、恢复旧快照或新版本绑定，写出假设与未知|当前873真机预测仍未就绪|
|2. 自由漂浮动力学与控制基准|推导并准备守恒、锁关节/刚化退化和交叉求解验证，随后按明确任务执行|先验证模型与执行器能力，再评价控制性能|
|3. 抓取与避障|准备完整关节/碰撞模型、误差界及确定性规划基线，和接触/柔性研究并行|静态装配或离散无碰不能直接证明动态可执行|
|4. 强化学习|定义观察/候选/奖励/终止、训练测试隔离及消融，待环境合同与基线成立后实施|合成环境结果不改称当前硬件性能，物理约束与失效判据独立评价|

[研究准入报告](research_intake/RESEARCH_READINESS.md)区分旧sim05/10/11/12、R2/E23、Sim13合成与负控证据和当前构型。29处raw SHA漂移不自动推翻旧结果，也不能用规范化哈希代替原始字节；受影响精确复现须先恢复快照或另版验证。

机械与动力学相互提供输入：研究给出反作用、捕获载荷、速度/扭矩/能量与时窗，工程用它们定型连接、驱动、电源和停止/热路径。无需把全部理论研究一直等待到飞行鉴定之后，但也不能把当前机械设计的未知项转写成算法默认值。

## 文件与继承

- [873实例参数包](mechanical_intake/PARAMETER_PACKET.json)、[43模块补全清单](mechanical_intake/OWNER_CLOSURE_WORKLIST.csv)、[跨模型参数表](research_intake/MODEL_PARAMETER_CROSSWALK.csv)。
- [本轮完整ZIP](WP10_ENGINEERING_RESEARCH_INPUTS.zip)：包含本轮设计、SI数据、惯性补充、合同与源记录；父原生CAD单独继承。
- [三态873叶SolidWorks完整包]({previous}/mechanical/WP09D_NATIVE_873.zip)、[原生冷读/搬迁回执]({previous}/results/NATIVE_DELTA_DELIVERY.json)。
- 父本2669文件已按封存SHA核验，未修改父CAD、科学Gate、URDF或旧结果。本轮只做新目录增量；未启动控制、RL训练、机械动作、上电或推进。
- [最终文件完整性](results/FINAL_INTEGRITY.json)是项目目录中的外层回执，只证明文件与引用完整性，不增加工程放行信用。ZIP内含自己的逐文件SHA清单；为避免循环哈希，不内嵌ZIP自身及外层最终回执。历史原生CAD包和封存父版由项目目录中的独立链接提供，未重复打入本轮ZIP。

需求、设计验证与使用工况确认分别记账的组织依据见[NASA产品实现指南](https://www.nasa.gov/reference/5-0-product-realization/)。本项目没有据此宣称NASA标准符合性或飞行鉴定。
"""
(D/'README.md').write_text(text,encoding='utf-8')
table='<tr><th>工作包</th><th>状态</th><th>已完成范围</th><th>剩余设计</th></tr>'
for r in rows:table+='<tr>'+''.join('<td>'+html.escape(r[k])+'</td>' for k in ['object','status','completed_evidence_scope','remaining_design'])+'</tr>'
page="""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>WP10 机电收束与研究交接</title><style>
*{box-sizing:border-box}body{margin:0;color:#172c3e;background:#f4f7f9;font:16px/1.7 "Microsoft YaHei",sans-serif}main{max-width:1180px;margin:auto;padding:36px 24px}h1{font-size:34px;line-height:1.35}h2{font-size:23px;margin-top:30px}a{color:#075b9c}.meta{font-size:13px;color:#617687;letter-spacing:1.4px}.decision{background:#fff0d7;border-left:5px solid #b87719;padding:18px;margin:22px 0}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:15px}.card{background:white;border:1px solid #cbd6df;border-radius:7px;padding:20px;text-decoration:none}.card small{display:block;color:#617285}.links{display:flex;flex-wrap:wrap;gap:18px}.phase{background:#eaf2f7;padding:18px;border-left:5px solid #397697}details{padding:16px;background:white;border:1px solid #ccd6df;margin:20px 0}summary{cursor:pointer;font-weight:600}.scroll{overflow:auto}table{border-collapse:collapse;min-width:900px;font-size:13px}th,td{padding:10px;border:1px solid #d6dfe7;vertical-align:top;text-align:left;max-width:390px}footer{font-size:13px;color:#65798a;margin:30px 0}@media(max-width:700px){main{padding:22px 16px}.grid{grid-template-columns:1fr}h1{font-size:27px}}</style><main>
<div class="meta">WP10 · 2026-09-08 · 服务星与 B601 DM</div><h1>机电设计继续补全<br>研究从模型与验证开始</h1>
<div class="decision"><b>整机机电完全交付：尚未达到。</b><br>本轮补齐实际辅助供源与驱动设计、参数和惯性数据入口；仍有内部设计及受控接口缺口。当前873构型尚不能作为已验证的真实硬件动力学模型。</div>
<h2>本轮实际成果</h2><div class="grid"><a class="card" href="ecad/exports/WP09_SYSTEM_AND_STOP.pdf"><b>修订系统电气原理图</b><small>99位号 / 97网 / 72条外部线<br>76位号停止子页 · 静态候选</small></a>
<a class="card" href="mechanical_intake/README_ZH.md"><b>873实例SI参数入口</b><small>43模块责任 · 三态坐标<br>390直接质量 + 10整臂覆盖</small></a>
<a class="card" href="mechanical_inertia/README_ZH.md"><b>306实例材料模型惯性</b><small>237份STEP · 三态m/COM/I<br>部分材料约7.872303 kg</small></a></div>
<p class="links"><a href="electrical/README.md">供源/驱动计算</a><a href="ecad/MASTER_FROM_TO.csv">接线主表</a><a href="ecad/MASTER_BOM.csv">分层BOM</a><a href="WP10_ENGINEERING_RESEARCH_INPUTS.zip">下载本轮设计包</a></p><p>电气位号数包含逻辑接口，97网含16个显式NC隔离网；统计不代表已装配实物。</p>
<h2>进入动力学、控制和智能抓取研究</h2><div class="phase"><b>推荐先进入：参数绑定的自由漂浮模型与守恒验证。</b><p>先明确模型身份、运动树、单位、惯量和执行器边界，再建立确定性规划/控制基线，并按环境合同开展强化学习。纯数学与理论研究可以和机电整改并行；当前真实硬件性能验证尚未就绪。</p></div>
<p>历史107条原始SHA中有29条漂移。旧结果可用于分析；受影响算例的精确复现需要恢复原快照或另版验证。原PASS不转移到当前873构型。</p>
<p class="links"><a href="research_intake/RESEARCH_READINESS.md">研究准入与原始Gate审计</a><a href="research_intake/MODEL_PARAMETER_CROSSWALK.csv">跨版本参数表</a><a href="ENGINEERING_RESEARCH_LOOP_ZH.md">研究交回工程的载荷与接口</a></p>
<h2>完整交付仍需关闭的责任</h2><p>星上高功率能源链、推进受控ICD、逐link物性/驱动/运动树、线束与连接、停止动态及PCB，以及整机热/强度/连续运动。23是开放工作包数，不是原子要求或完成百分比。</p>
<details><summary>展开逐项工程状态</summary><div class="scroll"><table>"""+table+"""</table></div></details>
<p class="links"><a href="README.md">完整交付说明</a><a href="results/DELIVERY_DECISION.json">机器判定</a><a href="results/FINAL_INTEGRITY.json">文件完整性</a><a href="../wp09_interfaces_20260907_1525/system_completion/mechanical/WP09D_NATIVE_873.zip">继承的873叶原生装配包</a></p>
<footer>本轮未重建原生总装、未改历史Gate、未运行控制/RL、未上电或执行推进。材料惯性为模型计算，静态电路与文件检查不是实物验收或飞行鉴定。</footer></main></html>"""
(D/'REVIEW.html').write_text(page,encoding='utf-8')
print(json.dumps({'status':decision['status'],'work_packages_open':len(open_rows),'readme':str(D/'README.md')},ensure_ascii=False))
