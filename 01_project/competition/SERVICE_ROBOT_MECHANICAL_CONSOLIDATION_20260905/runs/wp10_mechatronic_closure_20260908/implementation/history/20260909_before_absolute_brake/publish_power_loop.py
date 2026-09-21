"""Publish same-candidate power integration; never promote connectivity to release."""
from pathlib import Path
import csv,hashlib,html,json,zipfile
A=Path(__file__).resolve().parents[1];D=A.parent

# Scalar public-source screen reads the actual XML. It performs no CAD or I/O
# with hardware, and must run after native export before this package is sealed.
import runpy
runpy.run_path(str(A/'tools/build_regen_screen.py'),run_name='__main__')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def csvout(p,rows):
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
v=json.loads((A/'results/POWER_LOOP_VERIFICATION.json').read_text());assert v['all_connectivity_checks_passed']
c=json.loads((A/'power/POWER_LOOP_CALCULATIONS.json').read_text())
tim=json.loads((A/'power/THERMAL_INTERFACE_CONTRACT.json').read_text())
dim=json.loads((A/'results/DIMENSION_CHECKS.json').read_text());assert dim['all_checks_passed'] and dim['source_bound_thermal_face_gap_mm']==.229
contact=json.loads((A/'results/TIM_CONTACT_GEOMETRY.json').read_text());assert contact['source_step_sha256']==sha(A/'mechanical/converter_installation.step')
rows=list(csv.DictReader((A/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig')))
changes={'B03':('受保护电池端＋锁存热插拔候选；PMM20A主路停用；360W保持','电池端检测/适配、保险熔断、效率、热SOA与充电源'),'B05':('360W主路/16.8W辅路分账；22V冷启动反例落实','同任务时序可用能量和太阳充电闭环'),'C03':('THN常开独立供源已接原STOP板；源不依赖主接触器','停止24V及3.3/5V动态、故障过压、自动隔离许可与复位'),'C04':('LM74800共漏双MOS已集成，J203留在K1负载侧','绝对电压吸能电路及同任务能量/峰值/脉冲边界'),'E05':('72原线号追溯；9条修改、2条旧制动线停用','线束腔位/压接/长度/走线与热'),'E06':('99原位号保留＋33新增位号，5页原生层级集成','六项供电驱动诊断、控制/充电/保护链及PCB'),'F03':('主变换损耗40W@90%；新线性保护器件损耗额外计入','真实TIM、承载热板和外固定辐射面'),'H03':('同WP10源/网表/BOM已集成，244项有界核验通过','23项设计责任仍开放；不作制造/整机完成放行')}
for r in rows:
 if r['id'] in changes:
  r['execution_state']='ACTUAL_SOURCE_INTEGRATION__WHOLE_ROW_STILL_OPEN';r['new_evidence']=changes[r['id']][0]+' | results/POWER_LOOP_VERIFICATION.json; power/POWER_LOOP_CALCULATIONS.json';r['next_source_edit']=changes[r['id']][1];r['acceptance_action']='核验实际增量；整项状态保持'
 if r['id']=='F03':r['new_evidence']='实际TSP1600S 0.229mm实体已装入局部装配；3234.483mm²共面接触与零重叠已核验 | power/THERMAL_INTERFACE_CONTRACT.json; results/TIM_CONTACT_GEOMETRY.json';r['next_source_edit']='承载热板到外固定辐射面的实体连接、热网络和压紧/FG方案'
 if r['id']=='C04':r['new_evidence']+=' | Seeed DM公开OV32已绑定，未借作硬件保证；商业模块反例见results/REGEN_SOURCE_SCREEN.json'
counts={s:sum(r['status']==s for r in rows) for s in set(r['status'] for r in rows)}
assert len(rows)==37 and counts=={'COMPLETE_SCOPED_SUBITEM':13,'INTERNAL_DESIGN_OPEN':19,'EXTERNAL_INTERFACE_UNBOUND':4,'PHYSICAL_NOT_EXECUTED':1}
csvout(A/'SYSTEM_CLOSURE_MATRIX.csv',rows)
parent=list(csv.DictReader((D/'results/OUTPUT_SHA256.csv').open(encoding='utf-8-sig')))
bad=[r['path'] for r in parent if not (D/r['path']).exists() or sha(D/r['path'])!=r['sha256']];assert not bad,bad
dump(A/'results/PARENT_INTEGRITY.json',dict(count=len(parent),mismatches=bad,all_parent_indexed_bytes_unchanged=True))
dump(A/'results/DELIVERY_DECISION.json',dict(schema='WP10_IMPLEMENTATION_DELIVERY_V2',status='INTEGRATED_POWER_SOURCE_DELTA_VERIFIED__FULL_MECHATRONICS_OPEN',native_system_components=v['native_components'],preserved_parent_refs=99,added_refs=33,native_schematic_pages=5,connectivity_and_counterexample_checks=v['count'],ERC_open=v['ERC_count'],ERC_types=v['ERC_types'],original_workpackages=37,status_counts=counts,remaining_open_ids=[r['id'] for r in rows if r['status'] in ['INTERNAL_DESIGN_OPEN','EXTERNAL_INTERFACE_UNBOUND']],new_power_system_connected_to_derived_99ref_system=True,sealed_parent_99ref_system_unchanged=True,new_power_carrier_installed_in_873=False,engineering_prototype_design_complete=False,manufacture_release=False,power_on_authorized=False,flight_release=False,physical_tests_executed=False,goal_complete=False,external_input_missing=['same-revision battery SysDetect/connector/PMM parallel-load behavior','same-revision propulsion controlled ICD'],internal_work_remaining=['absolute load-side regen and energy bound','STOP dynamic rails and isolated automatic startup/reset','input fuse,capacitors,inrush/short SOA and charge budget','actual TIM/load-bearing heat path/fixed radiator and battery/PMM retention','remaining mechanical/harness/mass/load/continuous-motion design']))
dump(A/'results/POWER_REVIEW_DISPOSITION.json',dict(method='Real collaboration agent read-only; one reviewer per wave; root sole writer',reviewer='mechanical_intake',findings=[dict(id='PLR-01',problem='UVLO rising threshold and sense-node drop omitted',fix='cold start/held states and pre-fuse drop separated;22V not startable',state='SOURCE_AND_NATIVE_CHECK_REPAIRED'),dict(id='PLR-02',problem='MC35 body revision mislabeled A',fix='body RevB with existing SHA',state='SOURCE_REPAIRED'),dict(id='ROOT-03',problem='0.02ohm path smaller than selected MOSFET and shunt',fix='rejected scenario;40/60mOhm allocation corners',state='COUNTEREXAMPLE_RETAINED'),dict(id='ERC-01',problem='two secondary returns typed as independent driven power outputs',fix='negative returns passive, positive power_out and supply power_in unchanged;no PWR_FLAG',state='NATIVE_PIN_TYPE_CONFLICT_REMOVED')],whole_system_verified=False))
guards=[json.loads(p.read_text()) for p in (A/'logs').glob('native_delta_*.run.json') if 'power_loop' in p.name or '_tim_' in p.name];samples=[s for g in guards for s in g.get('samples',[])]
cleanup=json.loads((A/'logs/browser_workingset_cleanup_20260909.json').read_text(encoding='utf-8-sig'))
dump(A/'results/POWER_LOOP_MEMORY_AUDIT.json',dict(statuses=[dict(name=g['name'],status=g['status'],available_start_mib=g['available_start_mib']) for g in guards],minimum_runtime_available_mib=min([s['available_mib'] for s in samples],default=None),maximum_sampled_task_RSS_mib=max([s.get('combined_rss_mib',s.get('child_tree_rss_mib',0)) for s in samples],default=None),user_closed_other_pages=True,working_set_cleanup=cleanup,no_external_process_killed=True,resource_block_recovered=True))
report='''# WP10 同一活动候选：整机供电源已集成

本轮实际交付：**5页原生KiCad、132位号（原99＋新增33）、72原线号追溯与供电反例计算**。244项有界连线/反例/父本检查通过；六项ERC供电驱动诊断保留。873机械父本未修改。整机机电设计仍未完成，不能据此通电或制造。

[统一查看页](REVIEW.html) · [整机电气PDF](ecad/wp10_system.pdf) · [可编辑原理图](ecad/wp10_system.kicad_sch) · [原37行闭环表](SYSTEM_CLOSURE_MATRIX.csv)

## 实际决定与边界

|对象|源文件中的决定|当前边界|
|---|---|---|
|电池|保留RRC3570-4 D版，保护后端供独立主/辅支路|J200是项目适配板端点，OEM腔位和Sys Detect未绑定；E版单独归档。|
|PMM35|20A应用输出退出360W主路，charger-only保持未连接|10/15mΩ触点会分流11.418/7.612A；并联负载、充电终止及接线未获厂家确认。|
|主保护|LM5069MM-1、2mΩ＋0.2mΩ采样、UVLO/OVLO及1µF故障定时|限流筛选21.570–28.585A；含初始公差/TCR/Kelvin误差分配。48V表格适用转移、寿命漂移、保险和SOA仍需证明。|
|线性管|IXTH75N10L2候选|官方链接仍为Advance Technical Information；完整热SOA及正式器件来源未闭。不能只凭低导通电阻替代线性耗散验证。|
|独立停止辅源|THN30-2415WIR常开，接到原STOP J101.3/4|静态筛选23.544–24.456V；动态幅度无最大值，旧板3.3/5V动态也仍未闭。|
|主变换器|CHB500W-24S24N只计360W主负载|6.8W线圈＋10W辅助单列THN预算；损耗40W@90%或63.53W@85%都是条件场景。|
|反向阻断|LM74800-Q1＋两只CSD19536KTT共漏|CAP对VS、EP悬空、本地Sense。两模块负端共回流，输入侧仍隔离；反灌瞬态未实测。|
|负载侧制动|J203留在K1负载侧、与DM同网|目前仅电路端口，吸能器尚未完成。800µF从24到26V仅0.04J；50J/0.2s不是真实回生边界。|

22V电流解不代表可启动：UVLO下降21.990–23.272V、上升22.558–24.702V。已分别计算初始上电/保持导通，并纳入F201前段压降；22V冷启动明确阻断。该窗口影响真实任务可用能量，仍需预算，360W要求保持。

## 查看与复建

- [引脚表](ecad/POWER_LOOP_PIN_NET.csv)、[BOM](power/SELECTED_BOM.csv)、[线号变更](ecad/POWER_MASTER_LINEAGE.csv)、[条件计算](power/POWER_LOOP_CALCULATIONS.json)。未完成完整MPN/熔断/热选型的保险与电容在表中明示。
- [原生核验](results/POWER_LOOP_VERIFICATION.json)、[独立审阅处置](results/POWER_REVIEW_DISPOSITION.json)、[内存恢复](results/POWER_LOOP_MEMORY_AUDIT.json)、[机器裁决](results/DELIVERY_DECISION.json)。连线通过不代表硬件保护或整机功能通过。
- `tools/build_power.py`复建同目录电气；`tools/verify_power_loop.py`经`tools/native_delta_guard.py`串行核验；`tools/publish_candidate.py`更新包。旧7符号子图与旧376.8W共同供源预算保留为被替代的历史；活动入口为`ecad/wp10_system.kicad_sch`与`power/POWER_LOOP_CALCULATIONS.json`。
- [转换器装配STEP](mechanical/converter_installation.step)、[安装板STEP](mechanical/converter_carrier.step)、[873参数包](mechanical/PARAMETER_PACKET.json)保持原证据。实际TIM、热出口和电池/PMM夹持尚未获得新总装信用。

## 继续的实际责任

绝对电压负载侧制动、独立停止动态链与自动隔离启动/复位、保险/电容/预充SOA、充电源和完整热路径继续执行。推进同修订ICD缺项保留，其他内部责任继续。37行仍为13有界子项完成、19内部开放、4外部接口未绑定、1物理未执行，未改统计收口。

公开来源：[TI LM5069](https://www.ti.com/lit/ds/symlink/lm5069.pdf)、[TI LM7480](https://www.ti.com/lit/ds/symlink/lm7480-q1.pdf)、[THN30WIR](https://www.tracopower.com/thn30wir-datasheet)、[WSLP2726](https://www.vishay.com/docs/30179/wslp2726.pdf)。实际版本/SHA见`sources/POWER_LOOP_SOURCE_MANIFEST.json`。IXTH完整PDF下载403，官方在线内容已审阅，未伪造本地PDF。
'''
report=report.replace('实际TIM、热出口和电池/PMM夹持尚未获得新总装信用。','实际TSP1600S导热片（0.229mm，55.9×59mm，4个Ø4.5孔）已装入局部转换器装配；[导热片STEP](mechanical/converter_tim.step)、[接触几何](results/TIM_CONTACT_GEOMETRY.json)。精确共面接触3234.483mm²、与OEM和板均零体积重叠。普通包围盒曾误导最低点校验，已改验实际导热平面，失败记录保留。外辐射面和电池/PMM夹持仍未集成进873。')
report+='\n导热材料采用[Henkel TSP1600S正式TDS](https://datasheets.tdx.henkel.com/BERGQUIST-SIL-PAD-TSP-1600S-en_GL.pdf)。25psi均匀压力仅为验证目标；包含接触面的典型热阻投影0.149597K/W，对应总夹力557.524N。螺钉会旁路材料电隔离，组件绝缘不给信用；真空出气与整条热出口未闭。\n'
report+='''

## 回生选型的实际复算

[DM母线证据](power/DM_BUS_VOLTAGE_BINDING.json)绑定Seeed公开UV15/OV32参数；未宣称是实机读回，也不将32V作为保证耐压。参数文件仅作证据，不生成写入电机的命令。

[商业模块比较](power/REGEN_MODULE_TRADE.csv)及[12项源/拓扑/反例检查](results/REGEN_SOURCE_SCREEN.json)已加入同一预算。Roboteq30V档到+2V才启用双负载，与OV32名义值没有裕度；25V档会被24V加5%的条件阶跃跨过。其2000W标称不能搬到任意电压。Pololu3775的短脉冲用途也尚未覆盖整臂停止包络。上述结论来自公开资料和计算，不是硬件试验。

当前实际负载侧电容量保持未知，停用ODrive的800µF不计入硬件。50J、0.2s仍是反例：若只靠电容在24→26V容纳50J，需要1F，而非800µF。回生能量、阈值容差、吸能退出后的剩余能量与热路径继续作为实际设计责任。
'''
(A/'README.md').write_text(report,encoding='utf-8')
blocks=[('实际修改','主路：受保护电池端 → 保护/预充 → CHB → LM74800双MOS → K1 → 机械臂。辅路：保护后电池端 → 常开THN → 原STOP板。J203留在K1负载侧，吸能器尚未完成。',[('整机电气PDF','ecad/wp10_system.pdf'),('可编辑KiCad','ecad/wp10_system.kicad_sch'),('选型BOM','power/SELECTED_BOM.csv'),('From–To','ecad/MASTER_FROM_TO.csv'),('计算与反例','power/POWER_LOOP_CALCULATIONS.json')]),('机械资产保持','873组件父本、B601运动树、转换器与安装板保持；真实TIM、固定辐射面和电池/PMM安装正在落实，尚未新增总装信用。',[('转换器装配STEP','mechanical/converter_installation.step'),('安装板STEP','mechanical/converter_carrier.step'),('873参数包','mechanical/PARAMETER_PACKET.json'),('封存父本','../REVIEW.html')]),('验收与继续执行','244项连线/反例/父本检查通过；6项ERC供电驱动诊断保留。原37行：13有界子项完成、19内部设计开放、4外部接口未绑定、1物理未执行。用户关闭页面后可用内存恢复约5GiB，原生检查通过启动门槛；没有结束外部应用进程。',[('设计说明','README.md'),('原37行表','SYSTEM_CLOSURE_MATRIX.csv'),('核验记录','results/POWER_LOOP_VERIFICATION.json'),('审阅处置','results/POWER_REVIEW_DISPOSITION.json'),('机器裁决','results/DELIVERY_DECISION.json'),('当前源包','WP10_IMPLEMENTATION_DELTA.zip')])]
body=''.join('<section><h2>'+h+'</h2><p>'+s+'</p><nav>'+''.join('<a href="'+u+'">'+l+'</a>' for l,u in links)+'</nav></section>' for h,s,links in blocks)
body=body.replace('真实TIM、固定辐射面和电池/PMM安装正在落实，尚未新增总装信用。','真实0.229mm TSP1600S已装入转换器局部装配；固定辐射面与电池/PMM保持件尚未集成进873。')
body+='<section><h2>回生模块选型复核</h2><p>B601 DM公开过压设定32V已绑定；实机阈值容差与回生能量仍未知。12项源、负载侧拓扑和反例检查通过，未把商业模块标称功率或停用模块电容当作整臂保护能力。</p><nav><a href="power/REGEN_MODULE_TRADE.csv">模块比较</a><a href="power/DM_BUS_VOLTAGE_BINDING.json">电机母线证据</a><a href="results/REGEN_SOURCE_SCREEN.json">选型复算</a></nav></section>'
import urllib.parse
viewer='http://127.0.0.1:3245/'+urllib.parse.quote(A.as_posix(),safe='/:')
body+='<section><h2>实际导热片已入装配</h2><p>55.9×59×0.229mm，四个Ø4.5孔；几何净接触3234.483mm²，无体积重叠。压紧力、实际热阻与真空排热未验证。</p><img src="review/converter_iso_20260908T182135Z.png" alt="厂家转换器、粉色薄导热片和铝安装板实际装配快照"><nav><a href="'+viewer+'?file=mechanical%2Fconverter_installation.step.py">旋转查看装配</a><a href="'+viewer+'?file=mechanical%2Fconverter_tim.step.py">查看导热片</a><a href="mechanical/converter_tim.step">导热片STEP</a><a href="power/THERMAL_INTERFACE_CONTRACT.json">材料和热接口</a><a href="results/DIMENSION_CHECKS.json">尺寸核验</a></nav></section>'
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>WP10 · 整机供电源集成</title><style>body{font:16px/1.7 system-ui,"Microsoft YaHei",sans-serif;background:#f2f5f8;color:#213447;margin:0}main{max-width:1100px;margin:30px auto;padding:20px}section{background:white;border:1px solid #dce3ec;border-radius:10px;padding:24px;margin:18px 0}.flag{background:#fff3db;padding:16px;border-left:5px solid #b77d1a}h1{font-size:30px}a{color:#075d97}nav a{display:inline-block;background:#e9f2f8;padding:8px 12px;margin:6px}img{max-width:100%}.stat{font-size:22px;background:white;padding:20px}</style><main><p>WP10 · 同一活动候选 · 2026-09-09</p><h1>高功率电源已接入整机电气源</h1><div class="flag"><b>本轮设计增量可查看，整机机电闭环仍开放。</b><br>制动吸能、停止动态、启动监督、热与充电设计仍需完成。没有通电、制造或飞行放行。</div><p class="stat">132位号（原99＋33） · 5页原理图 · 244项有界检查通过</p>'''+body+'''<section><details><summary>展开实际电气页面</summary><img src="review/power_loop_page_5.png" alt="独立辅源、主变换器、反向阻断与负载侧接口实际KiCad导出"></details></section></main></html>'''
(A/'REVIEW.html').write_text(page,encoding='utf-8')
decision=json.loads((A/'results/DELIVERY_DECISION.json').read_text());decision.update(real_TIM_installed_in_local_converter_assembly=True,TIM_geometry_checks=len(dim['checks']),TIM_thermal_performance_verified=False,external_radiator_installed=False)
regen=json.loads((A/'results/REGEN_SOURCE_SCREEN.json').read_text());assert regen['checks_passed'] and regen['native_netlist_sha256']==sha(A/'ecad/wp10_system.xml')
decision.update(regen_source_screen_checks=regen['check_count'],regen_absorber_fitted=False,DM_public_parameter_files_bound=True,DM_as_built_threshold_bound=False)
dump(A/'results/DELIVERY_DECISION.json',decision)
dump(A/'results/TIM_REVIEW_DISPOSITION.json',dict(reviewer='mechanical_intake',method='read-only AST/source facts and independent scalar recomputation; no reviewer CAD execution',source_review_no_new_issue=True,actual_kernel_verification_by='root',bbox_counterexample='ordinary whole-body bounding box not equivalent to actual thermal plane; face and contact-area verification used',exact_common_volume_mm3=[x['volume_mm3'] for x in contact['intersections']],coplanar_contact_area_mm2=sum(x['measure'] for x in contact['OEM_TIM_coplanar_contact']),thermal_closure=False))
files=[p for p in A.rglob('*') if p.is_file() and not {'__pycache__','history'}.intersection(p.relative_to(A).parts) and p.name not in ['OUTPUT_SHA256.csv','WP10_IMPLEMENTATION_DELTA.zip']]
csvout(A/'results/OUTPUT_SHA256.csv',[dict(path=p.relative_to(A).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(files)])
with zipfile.ZipFile(A/'WP10_IMPLEMENTATION_DELTA.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in files+[A/'results/OUTPUT_SHA256.csv']:z.write(p,p.relative_to(A))
with zipfile.ZipFile(A/'WP10_IMPLEMENTATION_DELTA.zip') as z:assert z.testzip() is None
print(json.dumps(dict(files=len(files),parent_files_preserved=len(parent),zip_bytes=(A/'WP10_IMPLEMENTATION_DELTA.zip').stat().st_size,status_counts=counts,goal_complete=False),ensure_ascii=False))
