"""Publish the same current candidate; all whole-design release flags remain false."""
from pathlib import Path
import csv,hashlib,html,json,runpy,urllib.parse,zipfile
A=Path(__file__).resolve().parents[1];D=A.parent
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):(A/p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def csvout(p,rows):
 with (A/p).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
runpy.run_path(str(A/'tools/build_regen_screen.py'),run_name='__main__')
runpy.run_path(str(A/'tools/verify_startup_and_fault.py'),run_name='__main__')
runpy.run_path(str(A/'tools/verify_load_side_brake.py'),run_name='__main__')
startup=read('power/STARTUP_CIRCUIT_CALCULATIONS.json');fault=read('power/STOP_FULL_FAULT_BUDGET.json')
assert startup['checks_passed'] and fault['checks_passed']
v=read('results/POWER_LOOP_VERIFICATION.json');b=read('power/LOAD_SIDE_BRAKE_CALCULATIONS.json')
g=read('results/BRAKE_CONTACT_GEOMETRY.json');it=read('ecad/POWER_LOOP_INTEGRATION.json')
assert v['all_connectivity_checks_passed'] and b['checks_passed'] and g['checks_passed']
assert b['native_netlist_sha256']==sha(A/'ecad/wp10_system.xml')
assert g['source_step_sha256']==sha(A/'mechanical/brake_resistor_installation.step')
assert all(x['returncode']==0 for x in read('results/BRAKE_FINAL_GEOMETRY_SEQUENCE.json'))
n=v['native_components'];added=it['added_refs'];pages=2+len(it['power_pages'])
assert n==99+added
it['absolute_sink_circuit_integrated']=True;dump('ecad/POWER_LOOP_INTEGRATION.json',it)
parent=list(csv.DictReader((D/'results/OUTPUT_SHA256.csv').open(encoding='utf-8-sig')))
bad=[r['path'] for r in parent if not (D/r['path']).exists() or sha(D/r['path'])!=r['sha256']]
assert not bad,bad
dump('results/PARENT_INTEGRITY.json',dict(count=len(parent),mismatches=bad,all_parent_indexed_bytes_unchanged=True))
rows=list(csv.DictReader((A/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig')))
changes={
'B03':('受保护电池独立主辅支路；PMM20A主路停用；360W保持','电池端接口、保险电容、热SOA和充电源'),
'B05':('360W任务＋1W制动偏置；输入侧启动另预留0.25W，STOP16.8W独立','预留上界、真实任务能量和充电闭环'),
'C03':('全部11开漏和输入漏电清点；主域LT3013/TPS3808/MOS启动源已集成','停止动态、连续阈值、启动掉电及复位验证'),
'C04':('负载侧自供电绝对阈值制动已入原生源和三电阻局部装配','PG时序、过压峰值、回生能量、开关PCB与热'),
'E05':('72原线号保留；新增制动PCB内实际端点入网表','新外部线束段号、腔位压接、长度和走线'),
'E06':(f'原99＋新增{added}位号，{pages}页原生源；{v["count"]}项有界核验','ERC供电驱动诊断、动态和采购级无源选型、PCB'),
'F03':('CHB材料绑定的TIM几何保持；三LPS300＋三Q2500＋承载板已在CAD建模','温感保持、紧固件、外固定辐射面、电池PMM安装'),
'H03':('同候选电气源、制动实体、BOM和证据更新','23项设计责任仍开放；完整873装配待集成')}
for r in rows:
 if r['id'] in changes:
  r.update(execution_state='ACTUAL_SOURCE_INTEGRATION__WHOLE_ROW_STILL_OPEN',new_evidence=changes[r['id']][0]+' | power/LOAD_SIDE_BRAKE_CALCULATIONS.json; results/BRAKE_CONTACT_GEOMETRY.json',next_source_edit=changes[r['id']][1],acceptance_action='核验真实增量；整项状态保持')
counts={s:sum(r['status']==s for r in rows) for s in set(r['status'] for r in rows)}
for r in rows:
 if r['id'] in ['B05','C03','E06']:
  r['new_evidence']+=' | power/STARTUP_CIRCUIT_CALCULATIONS.json; power/STOP_FULL_FAULT_BUDGET.json'
assert len(rows)==37 and counts=={'COMPLETE_SCOPED_SUBITEM':13,'INTERNAL_DESIGN_OPEN':19,'EXTERNAL_INTERFACE_UNBOUND':4,'PHYSICAL_NOT_EXECUTED':1}
csvout('SYSTEM_CLOSURE_MATRIX.csv',rows)
src=read('sources/BRAKE_MECHANICAL_SOURCE_MANIFEST.json')
src['TIM']=dict(material='Q2500 (Q-PAD II)',revision='September2019',url='https://datasheets.tdx.henkel.com/BERGQUIST-SIL-PAD-TSP-Q2500-en_GL.pdf',file='sources/bergquist_q2500.pdf',sha256=sha(A/'sources/bergquist_q2500.pdf'),bytes=(A/'sources/bergquist_q2500.pdf').stat().st_size,variant='NO_PSA_PROJECT_CUT',sheet_SKU_unbound=True,electrical_insulation=False)
src['model_limits']=dict(unresolved_STEP_reference_diagnostic_count=1,imported_solids_valid=5,guaranteed_latest_drawing=False,PDF_pitch_mm=57.,CAD_recess_axis_pitch_mm=56.5,complete_mount_through_hole_proof=False)
dump('sources/BRAKE_MECHANICAL_SOURCE_MANIFEST.json',src)
csvout('mechanical/BRAKE_COMPONENT_BOM.csv',[
dict(item='RB301;RB302;RB303',description='LPS0300H1R00JB',quantity=3,status='ECAD_REFS_REUSED_NO_DOUBLE_COUNT',source='sources/LPS300_OEM.step'),
dict(item='TIM_RB301;TIM_RB302;TIM_RB303',description='Q2500 noPSA56x51x0.152 project cut',quantity=3,status='SHEET_SKU_PRESSURE_OUTGASSING_OPEN',source='sources/bergquist_q2500.pdf'),
dict(item='BRAKE_CARRIER',description='6061 candidate150x160x6',quantity=1,status='FRAME_MATES_FASTENERS_HEAT_EXIT_OPEN',source='mechanical/brake_carrier.step.py')])
selection=read('power/POWER_CHAIN_SELECTION.json')
selection['load_side_brake']=dict(actual_circuit_integrated=True,local_CAD_integrated=True,physical_hardware_installed=False,qualified=False)
selection['known_blockers']=[s.replace('load-side absolute brake sizing/circuit remain open','absolute brake circuit integrated; timing/energy/thermal qualification remains open') for s in selection['known_blockers']]
dump('power/POWER_CHAIN_SELECTION.json',selection)
dump('results/BRAKE_REVIEW_DISPOSITION.json',dict(method='One read-only reviewer per wave; root sole writer; no reviewer CAD execution',reviewer='mechanical_intake',repaired=[
dict(id='BRK01',issue='PG5V and reverse-output exposure',change='LT3013 selected, correct native pins; timing/high-state min still open'),
dict(id='BRK02',issue='Thermal alarm must not remove residual energy sink',change='Six open drains to originalFAULT_N_RAW, independentSTOP3V3'),
dict(id='BRK03',issue='NTC loading and actual temperature curve',change='749k loading, officialmaterialA curve, STOP sourceSHA and corners'),
dict(id='BRK04',issue='Fault pull-up temperature coefficient',change='100ppm/K25K included in added leakage; old-chain complete budget remains open'),
dict(id='BRK05',issue='Recess axes were called through holes',change='sampled_cylindrical_surfaces renamed; M4 bore/tool proof remains open'),
dict(id='BRK06',issue='Q2500 version/PSA unknown',change='PDF hash bound; noPSA cut selected; sheetSKU still open'),
dict(id='ROOT07',issue='TIM top mate created after relocation misplaced OEMs',change='Both local frames created before move; failed geometry evidence retained; actual placement/contact rerun')],
independent_hot_C=[80.91192436630362,86.73358928081069],whole_design_verified=False))
guards=[json.loads(p.read_text()) for p in (A/'logs').glob('native_delta_*.run.json') if any(k in p.name for k in ['power_loop','_tim_','_brake_'])]
samples=[s for q in guards for s in q.get('samples',[])]
dump('results/POWER_LOOP_MEMORY_AUDIT.json',dict(statuses=[dict(name=q['name'],status=q['status'],available_start_mib=q['available_start_mib']) for q in guards],minimum_runtime_available_mib=min(s['available_mib'] for s in samples),maximum_sampled_task_RSS_mib=max(s.get('combined_rss_mib',s.get('child_tree_rss_mib',0)) for s in samples),user_closed_other_pages=True,working_set_cleanup=read('logs/browser_workingset_cleanup_20260909.json'),no_external_process_killed=True,resource_block_recovered=True))
decision=dict(schema='WP10_IMPLEMENTATION_DELIVERY_V3',status='ABSOLUTE_BRAKE_CIRCUIT_AND_LOCAL_CAD_VERIFIED__WHOLE_MECHATRONICS_OPEN',native_system_components=n,preserved_parent_refs=99,added_refs=added,native_schematic_pages=pages,connectivity_and_counterexample_checks=v['count'],brake_scalar_and_topology_checks=b['check_count'],brake_geometry_checks=g['check_count'],ERC_open=v['ERC_count'],ERC_types=v['ERC_types'],original_workpackages=37,status_counts=counts,remaining_open_ids=[r['id'] for r in rows if r['status'] in ['INTERNAL_DESIGN_OPEN','EXTERNAL_INTERFACE_UNBOUND']],sealed_parent_873_and_99_refs_unchanged=True,absolute_sink_circuit_integrated=True,brake_local_assembly_generated=True,brake_sink_physically_installed=False,TIM_geometry_present_in_local_converter_CAD=True,new_power_carrier_installed_in_873=False,external_radiator_installed=False,engineering_prototype_design_complete=False,manufacture_release=False,power_on_authorized=False,flight_release=False,physical_tests_executed=False,goal_complete=False,external_input_missing=['same-revision batterySysDetect/connector/PMM parallel-load behavior','same-revision propulsion controlledICD'],internal_work_remaining=['PG/startup/clamp peak and actual regen envelope','STOP dynamics and full fault-budget, isolated automatic startup/reset','fuse/capacitor/SOA/charge design','sensor/fastener/radiator/battery/PMM and873 integration'])
dump('results/DELIVERY_DECISION.json',decision)
decision.update(schema='WP10_IMPLEMENTATION_DELIVERY_V4',status='PRIMARY_STARTUP_AND_FULL_FAULT_INVENTORY_INTEGRATED__WHOLE_MECHATRONICS_OPEN',startup_static_and_counterexample_checks=startup['check_count'],fault_inventory_checks=fault['check_count'],primary_automatic_enable_circuit_integrated=True,primary_automatic_enable_function_verified=False,full_fault_pin_inventory_included=True)
decision['internal_work_remaining']=['Brake PG/startup/clamp peak and actual regen envelope','STOP dynamics and continuous threshold guarantee; startup brown-ramp and reset','fuse/capacitor/SOA/charge design','sensor/fastener/radiator/battery/PMM and873 integration']
dump('results/DELIVERY_DECISION.json',decision)
report=f"""# WP10 当前活动候选：回生电路与安装实体

已生成 **{pages}页KiCad、{n}位号（原99＋新增{added}）**，并把三路制动电阻、三片真实导热片和承载板做成局部装配。{v['count']}项原生连接/反例检查、{b['check_count']}项制动静态/拓扑检查、{g['check_count']}项接触几何检查通过。仍有{v['ERC_count']}项ERC供电驱动诊断。

**整机详细设计仍未完成。** 原37行保持13有界子项完成、19内部开放、4外部接口未绑定、1物理未执行。873组件/99位号封存父本共{len(parent)}个索引文件原字节保持。未执行硬件试验，没有制造、通电或飞行放行。

[统一查看](REVIEW.html) · [完整电气PDF](ecad/wp10_system.pdf) · [原生KiCad](ecad/wp10_system.kicad_sch) · [37行闭环表](SYSTEM_CLOSURE_MATRIX.csv) · [机器裁决](results/DELIVERY_DECISION.json)

|对象|已写入的设计|仍需完成|
|---|---|---|
|主电源|RRC3570-4 D受保护端→LM5069锁存保护→CHB500W→LM74800双MOS→K1→B601 DM；PMM20A主路和地面RSP退出|电池真实端点、保险/电容、热SOA、充电源、隔离自动启动|
|分账|臂任务360W保持；制动偏置另预留1W，主路361W重新计算；THN独立STOP16.8W|1W预留是否足够、真实效率/温度/能量；22V冷启动反例保持|
|制动|K1负载侧LT3013自供12V、TLV6700绝对阈值、UCC27511、三只CSD19536KTT与三只1Ω LPS300|PG高态/启动时序、母线峰值、真实回生能量、PCB和温升|
|温度停止|三只NTCLE100E3103GB0、六开漏接原FAULT_N_RAW；报警请求停机而吸能支路保留|温感固定/绝缘/热滞后、旧故障链完整预算和动态|
|机械|三厂家电阻模型＋三Q2500＋150×160×6承载板；真实热面定位和纵槽|M4通孔/紧固件/工具、外固定辐射面和整星873安装|

制动启动名义27.44V；声明的分压温漂/偏置敏感性为{b['absolute_OV']['rising_sensitivity_V'][0]:.4f}–{b['absolute_OV']['rising_sensitivity_V'][1]:.4f}V，**不是保证的母线峰值**。DM公开OV32只代表源文件设定，实机阈值/最早跳闸仍未知；[商业模块反例](power/REGEN_MODULE_TRADE.csv)继续保留。

温感名义报警{b['thermal_monitor']['nominal_hot_trip_C']:.4f}°C、复位{b['thermal_monitor']['nominal_reset_C']:.4f}°C，报警角点{b['thermal_monitor']['hot_trip_sensitivity_C'][0]:.4f}–{b['thermal_monitor']['hot_trip_sensitivity_C'][1]:.4f}°C。已计749k并联负载与官方R–T曲线。传感器温度不是电阻膜温度，典型15s时间常数不构成快速脉冲保护。开/短路静态检出和0–50°C角点已核验；低温误报、启动与热传递仍有界限。

Q2500无PSA裁片56×51×0.152mm，非绝缘。各2856mm²精确接触，板/膜/电阻外部零体积重叠。50psi下每片典型热阻投影0.049697K/W、均匀夹力目标984.6N/只；厂家2Nm扭矩不能证明实际压力。公开模型安装凹槽轴间距56.5mm与图纸57mm不同，4.5×6纵槽预留调整量，未获得同修订接口信用。三只电阻约0.249kg，板估计{g['carrier_mass_estimate_kg']:.6f}kg，尚未加入873质量真值。

[制动装配STEP](mechanical/brake_resistor_installation.step) · [承载板STEP](mechanical/brake_carrier.step) · [导热片STEP](mechanical/brake_tim.step) · [机械BOM](mechanical/BRAKE_COMPONENT_BOM.csv) · [几何证据](results/BRAKE_CONTACT_GEOMETRY.json)。STEP可供SolidWorks导入，本轮没有生成新原生SLDASM。原CHB/TSP1600S局部装配保持，外热出口与电池PMM安装继续开放。

[引脚网表](ecad/POWER_LOOP_PIN_NET.csv) · [From–To](ecad/MASTER_FROM_TO.csv) · [电气BOM](power/SELECTED_BOM.csv) · [主预算](power/POWER_LOOP_CALCULATIONS.json) · [制动计算](power/LOAD_SIDE_BRAKE_CALCULATIONS.json) · [审阅处置](results/BRAKE_REVIEW_DISPOSITION.json)。新增PCB内部连线不冒称新外部线束腔位完成。PG、延迟、能量和实际温升未验证项以null/false保留。

复建入口：tools/build_power.py；经内存守卫执行tools/verify_power_loop.py；tools/verify_load_side_brake.py读实际XML复算；显式CAD源见mechanical/brake_*.step.py；最终tools/publish_candidate.py更新同一查看页和包。CAD/OCC/COM串行。源级配合顺序错误曾令电阻叠在原点，现已修复并重跑，失败见[反例](results/BRAKE_MATE_COUNTEREXAMPLE.json)。

来源：[LT3013](https://www.analog.com/media/en/technical-documentation/data-sheets/3013fe.pdf)、[TLV6700](https://www.ti.com/lit/ds/symlink/tlv6700.pdf)、[UCC27511](https://www.ti.com/lit/ds/symlink/ucc27511.pdf)、[NTC](https://www.vishay.com/docs/29049/ntcle100.pdf)、[LPS300](https://www.vishay.com/docs/50052/lps300.pdf)、[Q2500](https://datasheets.tdx.henkel.com/BERGQUIST-SIL-PAD-TSP-Q2500-en_GL.pdf)。版本和SHA见sources/LOAD_SIDE_BRAKE_SOURCE_MANIFEST.json与sources/BRAKE_MECHANICAL_SOURCE_MANIFEST.json。ST二极管本地PDF未成功下载，官方在线已核阅；不伪造归档。OEM STEP保留一个引用诊断，五实体有效不代表最新受控制造图。

下一项实际责任：制动动态/能量与停止链全预算，然后传感器/紧固件/外热面、电池PMM安装与873完整集成。推进同修订ICD缺项单列，当前不宣称机电完全交付。
"""
report=report.replace('旧故障链完整预算和动态','全故障阈值保证和停止动态').replace('隔离自动启动','启动掉电/复位验证').replace('旧故障链完整预算','完整故障阈值保证').replace('下一项实际责任：制动动态/能量与停止链全预算','下一项实际责任：制动动态/能量、停止动态与启动掉电验证')
report+='\n## 本轮输入侧启动电路\n\n新增17个实际器件，LT3013偏置＋TPS3808G01＋Diodes 2N7002K-7及无源网络。MAIN_FUSED欠压和预充PGD共同许可CHB；启动不读取CHB输出或RUN_LATCH。修复了带电预充电容掩盖输入掉电，以及PGD下游连接开路被上拉成许可的反例。门极最低静态敏感性'+f"{startup['qualification']['gate_high_sensitivity_V'][0]:.6f}"+'V；全故障网漏电敏感性9.7µA，RAW最低'+f"{fault['RAW_high_min_sensitivity_V']:.6f}"+'V。器件测试条件迁移、POR/掉电斜坡和最长关断响应仍未验证。\n\n'+f"{startup['check_count']}项启动静态/反例、{fault['check_count']}项全故障网清点通过。"+'[启动设计说明](power/STARTUP_DESIGN.md) · [启动复算](power/STARTUP_CIRCUIT_CALCULATIONS.json) · [全故障预算](power/STOP_FULL_FAULT_BUDGET.json)。0.25W主侧预留已在输入电流增量场景计入，不改变360W臂任务。\n'
(A/'README.md').write_text(report,encoding='utf-8')
viewer='http://127.0.0.1:3245/'+urllib.parse.quote(A.as_posix(),safe='/:')
def live(stem):return viewer+'?file='+urllib.parse.quote('mechanical/'+stem+'.step.py',safe='')
def links(items):return '<nav>'+''.join('<a href="'+html.escape(u,quote=True)+'">'+html.escape(l)+'</a>' for l,u in items)+'</nav>'
shot=sorted((A/'review').glob('brake_resistor_installation_iso_*.png'))[-1].relative_to(A).as_posix()
sections=[
('本轮启动与停止预算','17个器件已接入输入侧自动启动；修复带电电容与PGD下游断线反例。完整故障网覆盖11个开漏输出。物理启动及停止动态尚未验证。',[('启动设计说明','power/STARTUP_DESIGN.md'),('启动复算','power/STARTUP_CIRCUIT_CALCULATIONS.json'),('完整故障预算','power/STOP_FULL_FAULT_BUDGET.json')]),
('实际电气源','负载侧自供电制动与三温感停止链已接入；动态、真实回生能量和PCB仍待完成。',[('完整电气PDF','ecad/wp10_system.pdf'),('可编辑原理图','ecad/wp10_system.kicad_sch'),('电气BOM','power/SELECTED_BOM.csv'),('制动计算','power/LOAD_SIDE_BRAKE_CALCULATIONS.json')]),
('局部机械装配','厂家LPS300实体、三片Q2500与承载板；温感安装、紧固件、外热出口与873整星集成尚未完成。',[('旋转查看装配',live('brake_resistor_installation')),('装配STEP','mechanical/brake_resistor_installation.step'),('查看承载板',live('brake_carrier')),('承载板STEP','mechanical/brake_carrier.step'),('查看导热片',live('brake_tim')),('导热片STEP','mechanical/brake_tim.step'),('接触检查','results/BRAKE_CONTACT_GEOMETRY.json')]),
('已有转换器接口','真实TSP1600S接口保持；873组件封存父本原字节保持。',[('CHB装配',live('converter_installation')),('873参数包','mechanical/PARAMETER_PACKET.json'),('封存父本','../REVIEW.html')]),
('交付状态','原37行保持13有界子项完成、19内部开放、4外部未绑定、1物理未执行。整机机电详细设计仍开放。',[('设计说明','README.md'),('原37行表','SYSTEM_CLOSURE_MATRIX.csv'),('原生核验','results/POWER_LOOP_VERIFICATION.json'),('制动核验','results/LOAD_SIDE_BRAKE_VERIFICATION.json'),('机器裁决','results/DELIVERY_DECISION.json'),('当前全部源包','WP10_IMPLEMENTATION_DELTA.zip')])]
body=''.join('<section><h2>'+h+'</h2><p>'+s+'</p>'+('<img src="'+shot+'" alt="实际三电阻与承载板装配快照">' if h=='局部机械装配' else '')+links(ls)+'</section>' for h,s,ls in sections)
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>WP10 · 回生电路与安装实体</title><style>body{font:16px/1.7 system-ui,"Microsoft YaHei",sans-serif;background:#f2f5f8;color:#213447;margin:0}main{max-width:1100px;margin:30px auto;padding:20px}section{background:white;border:1px solid #dce3ec;border-radius:10px;padding:24px;margin:18px 0}.flag{background:#fff3db;padding:16px;border-left:5px solid #b77d1a}h1{font-size:30px}a{color:#075d97}nav a{display:inline-block;background:#e9f2f8;padding:8px 12px;margin:6px}img{max-width:100%}.stat{font-size:22px;background:white;padding:20px}</style><main><p>WP10 · 同一活动候选 · 2026-09-09</p><h1>回生电路与三电阻局部装配已生成</h1><div class="flag"><b>设计增量可查看，整机闭环仍开放。</b><br>任务吸能、动态、完整热路径和整星装配仍需完成；没有制造、通电或飞行放行。</div>'''+f'<p class="stat">{n}位号 · {pages}页原理图 · {v["count"]}项原生检查 · {b["check_count"]}项制动检查</p>'+body+'<section><details><summary>原生电气导出节选</summary><img src="review/power_brake_page_8.png" alt="实际制动和温感原生连接页"></details></section></main></html>'
page=page.replace('回生电路与三电阻局部装配已生成','输入侧启动电路与完整故障预算已集成').replace('review/power_brake_page_8.png','review/power_startup_page_5.png').replace('实际制动和温感原生连接页','当前实际输入侧启动原生页')
(A/'REVIEW.html').write_text(page,encoding='utf-8')
if (A/'results/NATIVE_COLD_COLD.json').exists():
 runpy.run_path(str(A/'tools/publish_cold_path_addendum.py'),run_name='__main__')
elif (A/'results/FIXED_HEAT_GEOMETRY.json').exists():
 runpy.run_path(str(A/'tools/publish_fixed_heat_addendum.py'),run_name='__main__')
if not (A/'results/NATIVE_COLD_COLD.json').exists() and (A/'results/NATIVE_BOTTOM_COLD.json').exists():
 runpy.run_path(str(A/'tools/publish_bottom_addendum.py'),run_name='__main__')
if (A/'results/BATTERY_BAY_REVIEW.json').exists():
 runpy.run_path(str(A/'tools/publish_battery_bay_addendum.py'),run_name='__main__')
if (A/'results/PROP_ROUTING_REVIEW.json').exists():
 runpy.run_path(str(A/'tools/publish_prop_routing_addendum.py'),run_name='__main__')
if (A/'results/TRUNK_SUPPORT_REVIEW.json').exists():
 runpy.run_path(str(A/'tools/publish_trunk_support_addendum.py'),run_name='__main__')
if (A/'results/ROOT_BUSHING_REVIEW.json').exists():
 runpy.run_path(str(A/'tools/publish_root_bushing_addendum.py'),run_name='__main__')
files=[p for p in A.rglob('*') if p.is_file() and not {'__pycache__','history'}.intersection(p.relative_to(A).parts) and p.name not in ['OUTPUT_SHA256.csv','WP10_IMPLEMENTATION_DELTA.zip']]
csvout('results/OUTPUT_SHA256.csv',[dict(path=p.relative_to(A).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(files)])
with zipfile.ZipFile(A/'WP10_IMPLEMENTATION_DELTA.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in files+[A/'results/OUTPUT_SHA256.csv']:z.write(p,p.relative_to(A))
with zipfile.ZipFile(A/'WP10_IMPLEMENTATION_DELTA.zip') as z:assert z.testzip() is None
print(json.dumps(dict(files=len(files),parent_preserved=len(parent),native_refs=n,pages=pages,zip_bytes=(A/'WP10_IMPLEMENTATION_DELTA.zip').stat().st_size,goal_complete=False)))
