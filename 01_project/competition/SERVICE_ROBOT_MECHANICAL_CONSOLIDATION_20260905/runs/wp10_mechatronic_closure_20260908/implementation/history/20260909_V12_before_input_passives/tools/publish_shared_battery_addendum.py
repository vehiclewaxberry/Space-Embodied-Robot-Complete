"""Publish one shared-path design update after the existing V11 publisher.

Preserves the original 37 status values, native ECAD and 936 CAD source table.
This is a discharge-model correction, not a completed PMM/battery installation.
"""
from pathlib import Path
import csv
import hashlib
import html
import json
import runpy

A=Path(__file__).resolve().parents[1]
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def dump(p,v):(A/p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')

runpy.run_path(str(A/'tools/check_shared_battery_path.py'),run_name='__main__')
r=read('power/SHARED_BATTERY_PATH_CALCULATIONS.json')
assert r['checks_passed'] and all(sha(p)==h for p,h in r['inputs'].items())
assert all(sha(p)==h for p,h in r['source_scripts'].items())
anchor=next(q for q in r['cases'] if q['id']=='SBP132')
assert anchor['inputs']['pack_v']==25.2 and anchor['inputs']['shared_r']==.1
sel=read('power/POWER_CHAIN_SELECTION.json')
sel['shared_battery_path']=dict(active_model='tools/shared_battery_path.py',
    definition='power/SHARED_BATTERY_PATH_DEFINITION.json',
    calculations='power/SHARED_BATTERY_PATH_CALCULATIONS.json',
    old_uncoupled_sensitivities_retained=True,
    meaning='Both discharge branches now see shared MC35 loop drop; main and AUX branch resistances exclude that loop.',
    OEM_50mOhm_test_definition_confirmed=False,full_power_thermal_verified=False)
sel['manager']['public_mount_hole_count']=4
sel['manager']['public_hole_centers_mm']=None
sel['manager']['integrated_battery_connector_angle_deg']=90
dump('power/POWER_CHAIN_SELECTION.json',sel)

bounds=[q['boundary'] for q in r['hold_boundaries_at_25p2V'] if q['boundary']]
review=dict(schema='WP10_SHARED_BATTERY_PATH_REVIEW_V1',
    native_schematic_unchanged=True,source_geometry_unchanged=True,
    current_source_plan='mechanical/ROOT_BUSHING_INSTANCE_PLAN.json',
    current_source_plan_sha256=sha('mechanical/ROOT_BUSHING_INSTANCE_PLAN.json'),
    full_source_instances_by_state={state:len(v['rows']) for state,v in read('mechanical/ROOT_BUSHING_INSTANCE_PLAN.json')['states'].items()},
    model_sha256=sha('tools/shared_battery_path.py'),
    checks_sha256=sha('tools/check_shared_battery_path.py'),
    calculations_sha256=sha('power/SHARED_BATTERY_PATH_CALCULATIONS.json'),
    check_count=r['check_count'],case_count=r['case_count'],
    previously_ON_hold_counterexample_count=len(r['counterexample_ids']),
    battery_PMM_mount_review=dict(PMM_mount_holes=4,PMM_hole_coordinates_mm=None,
        PMM_integrated_connector='90 degree; not MC35-180 body transform',
        public_board_size_approx_mm=[80,75],includes_connectors_and_cables=False,
        battery_socket_transform=None,hold_down_contact_regions=None,
        sources={p:sha(p) for p in ['sources/pmm35.pdf','sources/mc35.pdf','sources/rrc3570_4.pdf']}),
    package_release=False,power_on_release=False,goal_complete=False)
if (A/'results/SHARED_BATTERY_READONLY_REVIEW.json').exists():
    review['readonly_review']='results/SHARED_BATTERY_READONLY_REVIEW.json'
    review['readonly_review_sha256']=sha(review['readonly_review'])
    rr=read(review['readonly_review'])
    assert rr['reviewed_calculations_sha256']==sha('power/SHARED_BATTERY_PATH_CALCULATIONS.json')
    assert rr['reviewed_thermal_csv_sha256']==sha('thermal/SHARED_BATTERY_HEAT_LOADS.csv')
dump('results/SHARED_BATTERY_PATH_REVIEW.json',review)

lines=[]
for rc in [0,.01,.1]:
    q=next(q for q in r['cases'] if q['inputs']==dict(anchor['inputs'],shared_r=rc))
    v=q['run']
    lines.append(f"|{rc*1000:.0f}|{v['junction_V']:.6f}|{v['main_fused_V']:.6f}|{v['battery_A']:.6f}|{v['heat_W']['shared_contact_loop']:.6f}|{q['held_LM5069_screen']}|")
table='\n'.join(lines)
doc=f'''# WP10 共享电池连接器压降与热预算修订

MC35 的共用接点已加入当前主／辅助电源模型。192组条件、{r['check_count']}项计算与原生拓扑检查通过；16组场景从忽略共享电阻时的全部容差可保持，变为部分容差不能保证保持。这里的“检查通过”只证明模型绑定和复算一致，整机电源与机械安装仍开放。

## 来源与采用方式

[RRC-MC35-180-30 数据表正文B版第2页](https://www.rrc-ps.com/fileadmin/Dokumente/Data-Sheets/DS_RRC-MC35-180-30_A.PDF)列出接触电阻最大50mΩ、功率针最大30A。文档没有给出测量方法、温度、老化状态或清晰的单触点定义。本轮把每个配对功率极0.05Ω、正负极串联合计0.10Ω作为明确的保守场景；没有把公母两半再算两次，也没有称其为实测或已确认的热保证。0.01Ω是未测敏感性，0Ω只是对照。

## 改动的实际模型

受保护电池端电压 → 两功率极的共用回路电阻 → J200工程输出端 → F201主路／F202辅助路。原生XML已经确认两个支路在J200处分开，欠压检测仍在F201之后。PMM未接入主放电回路。

主转换器输出预算361W（360W机械臂＋1W制动侧分配），主侧启动另0.25W；辅助输出16.8W保持。共用压降用总电流求解，辅助恒功率电流也随压降增加。主路0.04／0.06Ω明确定义为J200之后，避免与MC35重复计数；这些仍是设计分配，不是实测总阻抗。输入控制器另有3mA场景分配，计入F201前段压降和功率。

求解器选高电压代数分支，计算母线、电流、热量与源端能量账。支路高电压根不存在时不会用零电流判通过。冷启动场景关闭主转换器但保留辅助满分配负载；这不能替代预充、UVLO跳变、时域稳定性或故障响应验证。

## 同条件比较

下表电池端为25.2V；主／辅助效率0.85／0.80；主分支0.04Ω，其中欠压检测之前0.005Ω；辅助0.04Ω。电池电压在接点之前，已经包含电池内部带载压降，不能当作开路电压或J200电压。

|共享正负接点回路 / mΩ|J200电压 / V|欠压检测电压 / V|电池电流 / A|接点损耗 / W|保持筛查|
|---:|---:|---:|---:|---:|---|
{table}

0.10Ω场景的接点损耗39.320039W，不能被旧CHB单热源计算覆盖。它在部分UVLO容差组合下不能维持假设工作点；**不能据此宣称硬件会稳定持续发热39.32W**，实际跳变和占空比尚未计算。启动初始检测点25.115961V可通过现有上升门槛，而运行后23.122455V低于部分下降门槛，说明“可以启动”不足以证明持续工作。

对现有门槛做反算，25.2V和本轮阻抗／效率场景下，全容差保持所允许的共享回路电阻上限约{min(q['maximum_shared_loop_R_ohm_at_given_pack_V'] for q in bounds)*1000:.3f}–{max(q['maximum_shared_loop_R_ohm_at_given_pack_V'] for q in bounds)*1000:.3f}mΩ；固定0.10Ω时，门槛对应电池端约{min(q['required_pack_V_for_given_shared_R'] for q in bounds):.6f}–{max(q['required_pack_V_for_given_shared_R'] for q in bounds):.6f}V。这些是条件边界，不是选定的任务最低电压、BMS设置或可用能量保证。360W任务和既有UVLO源值均保留。

## 与机械和热设计的衔接

热源清单已写入[SHARED_BATTERY_HEAT_LOADS.csv](../thermal/SHARED_BATTERY_HEAT_LOADS.csv)，按RUN／COLD分别列出共用接点、主路前后段、辅助线损、输入控制器、CHB／THN损耗与启动分配。只读审阅发现初版COLD漏列THN的4.2W转换热，且将断开开关之后的电压写成零负载代数延拓；现已补齐热账，并把真实PRECHARGED电压置空。锚点COLD电源21.173987W＝辅助输出16.8W＋总损耗4.373987W；该电容的初始电压和保持过程仍未计算。

连接器的安装位置、热沉节点及接触热阻仍为空；没有自动归入电池壳体或旧辐射面。电池内部损耗、转换器输出防回流／接触器／机械臂损耗和实测任务热史仍未包括。输出功率边界是两转换器输出分配面。

PMM A版公开资料只给约80×75mm板尺寸（不含线缆和连接器）、四孔及集成90°电池插口，没有孔坐标、孔径、板厚和完整安装变换。[PMM官方第3页](https://www.rrc-ps.com/fileadmin/Dokumente/Data-Sheets/DS_RRC-PMM35_A_01.pdf)不能支持按照片定孔；直插MC35尺寸也不能充当PMM的90°接口位置。电池保持区域、受控插座基准和插拔止挡继续逐字段开放。

## 当前设计决定

- 保留保护电池、独立主辅支路和负载侧回生架构，将共享接点损耗纳入放电与热预算。
- MC35继续作为匹配候选；其受控接触阻抗、温升和安装接口未确认前，不以30A目录值冻结满任务供电、载板端接或电池保持设计。
- PMM仍为未连接的充电候选，四孔数量可绑定；充电并联负载行为、受控孔位及插口变换不能补猜。
- 共用接点开路会同时中断两条输入支路。辅助供电是分支独立，无法因此宣称电源冗余；储能保持时间和实际STOP响应仍需验证。负载侧回生电路拓扑保留。

本轮没有修改201位号／11页电气源和936实例几何源，没有执行实物或新增装配。V11的局部CAD证据维持原范围。复算：`python tools/check_shared_battery_path.py`。主模型[shared_battery_path.py](../tools/shared_battery_path.py)，定义[JSON](SHARED_BATTERY_PATH_DEFINITION.json)，计算[JSON](SHARED_BATTERY_PATH_CALCULATIONS.json)。
'''
(A/'power/SHARED_BATTERY_PATH_DESIGN.md').write_text(doc,encoding='utf-8')

v=read('results/DELIVERY_DECISION.json')
assert v['current_source_plan']=='mechanical/ROOT_BUSHING_INSTANCE_PLAN.json' if 'current_source_plan' in v else True
v.update(schema='WP10_IMPLEMENTATION_DELIVERY_V12',revision='V12_SHARED_BATTERY_PATH',
         status='SHARED_CONTACT_DC_AND_HEAT_BUDGET_CORRECTED__WHOLE_MECHATRONIC_CLOSURE_OPEN',
         shared_battery_path_review='results/SHARED_BATTERY_PATH_REVIEW.json',
         shared_battery_DC_cases=r['case_count'],shared_battery_DC_checks=r['check_count'],
         shared_path_hold_counterexamples=len(r['counterexample_ids']),
         shared_connector_thermal_and_OEM_pinout_qualified=False,
         engineering_prototype_design_complete=False,goal_complete=False)
v['active_next_work_item']=dict(parent_id='B03',same_candidate='mechanical/ROOT_BUSHING_INSTANCE_PLAN.json',
    next_action='Resolve shared protected-contact resistance/temperature and actual socket/retention datum; retain 360W task and existing UVLO. Continue charging source/PMM behavior, full heat sources and physical PCB/fuse/SOA/STOP design without inventing OEM inputs.',
    read_inputs=['power/SHARED_BATTERY_PATH_DESIGN.md','power/SHARED_BATTERY_PATH_CALCULATIONS.json','power/BATTERY_INSTALLATION_INTERFACE.json'])
dump('results/DELIVERY_DECISION.json',v)
rows=list(csv.DictReader((A/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig')))
assert len(rows)==37
for q in rows:
    if q['id'] in ['B03','B05','A05']:
        q['new_evidence']+=' | V12共享MC35接点与主辅恒功率耦合192场景；16个欠压保持反例，接点及辅助热量单列。实际安装/温升/针序未完成。'
    if q['id']=='B03':
        q['execution_state']='SHARED_CONTACT_DC_MODEL_CORRECTED__PROTECTED_INTERFACE_AND_WHOLE_POWER_OPEN'
        q['next_source_edit']='绑定同修订受保护接点阻抗/温升/插座基准；完成实际端接保持、充电、保险与SOA，继续全热源和STOP动态。'
with (A/'SYSTEM_CLOSURE_MATRIX.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
intro=f'''# WP10 当前修订：共享电池接点的供电与热预算

已修正主／辅助支路共同承担的MC35接点压降。{r['case_count']}组条件、{r['check_count']}项模型和原生拓扑检查完成；发现16组欠压保持反例。25.2V、共享0.10Ω的保守场景下，欠压检测点23.122455V、接点损耗39.320039W，部分容差无法保证保持。这不是实测温升，也没有证明实际跳变下会持续产生该热量。

[设计说明及比较表](power/SHARED_BATTERY_PATH_DESIGN.md) · [模型与电气绑定](power/SHARED_BATTERY_PATH_CALCULATIONS.json) · [实际Python源](tools/shared_battery_path.py) · [新增热源账](thermal/SHARED_BATTERY_HEAT_LOADS.csv) · [当前交付判定](results/DELIVERY_DECISION.json)

整机机电设计仍未完成。电池／PMM保持和插口坐标、接点温升、充电、全热源、停止动态和受控推进接口继续开放。电气201位号／11页、V11完整936实例源表与局部136件STEP保持原版本，本轮没有重新生成整机原生SolidWorks。

下文为V11及更早机械增量，验证范围按各自源版本保留。

---

'''
(A/'README.md').write_text(intro+(A/'README.md').read_text(encoding='utf-8'),encoding='utf-8')
body='<section><h2>当前：共享接点的压降与发热已计入</h2><p class="flag">192组条件，'+str(r['check_count'])+'项模型及原生连接检查；16组欠压保持反例。整机仍未完成。</p><p>25.2V保守接点场景：检测点23.122455V，接点损耗39.320039W。数值为假设导通的代数计算，实际跳变和温升未验证。</p><nav>'+''.join('<a href="'+html.escape(u)+'">'+html.escape(t)+'</a>' for t,u in [('设计与比较','power/SHARED_BATTERY_PATH_DESIGN.md'),('同源计算','power/SHARED_BATTERY_PATH_CALCULATIONS.json'),('实际计算源','tools/shared_battery_path.py'),('热源清单','thermal/SHARED_BATTERY_HEAT_LOADS.csv'),('来源与绑定','results/SHARED_BATTERY_PATH_REVIEW.json')])+'</nav><p>保留360W任务与原UVLO。电池/PMM实际安装、受控插口和热阻仍缺；本轮不改936机械源表。下方V11局部装配可继续查看。</p></section>'
page=(A/'REVIEW.html').read_text(encoding='utf-8').replace('同一活动候选 · V11 桥板线束衬套','同一活动候选 · V12 共享电池接点预算').replace('<h1>桥板过孔衬套与保持实体已集成</h1>','<h1>共享电池接点的供电与热预算已修正</h1>').replace('<section>',body+'<section>',1)
(A/'REVIEW.html').write_text(page,encoding='utf-8')
print(json.dumps(dict(revision='V12',native_schematic_changed=False,geometry_changed=False,case_count=r['case_count'],goal_complete=False)))
