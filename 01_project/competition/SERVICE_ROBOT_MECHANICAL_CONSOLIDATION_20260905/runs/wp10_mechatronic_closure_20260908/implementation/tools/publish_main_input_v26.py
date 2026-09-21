"""Activate the reviewed board in the same WP10 candidate; preserve sealed whole-system records."""
from pathlib import Path
import collections,csv,datetime,hashlib,html,json,shutil,time
import psutil
A=Path(__file__).resolve().parents[1]
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def dump(p,x):(A/p).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
review_hashes={
 'tools/main_input_route_v26.py':'5cfd534cd09a1c1ace4394902ddc3ce28f978f6c64f331f1435a688e262ddb8d',
 'tools/finish_main_input_route_v26.py':'504f6b7382f4e90b351e5c61f4b227697e4702e4cb952d872e3de564a6970fbc',
 'results/MAIN_INPUT_CANDIDATE_DRC_V26.json':'1d6df156259f70c23f27988fdd5d17e149311d387b3834f5176f7f13aac50b32',
 'ecad/wp10_main_input_v26_candidate.kicad_pcb':'271d9d25eee29f0e889864747d6b781c65a305eebc4d2da4e713ba73c227c1c4'}
assert all(sha(p)==h for p,h in review_hashes.items())
integrity=read('results/MAIN_INPUT_COPPER_INTEGRITY_V26.json');assert integrity['passed']
assert all(sha(p)==h for p,h in integrity['source_hashes'].items())
native=read('results/MAIN_INPUT_NATIVE_READBACK_V26.json');drc=read('results/MAIN_INPUT_CANDIDATE_DRC_V26.json');d=read('power/MAIN_INPUT_BOARD_DEFINITION_V26.json');loss=read('power/MAIN_INPUT_COPPER_LOSS_V26.json')
assert native['passed'] and native['PCB_sha256']==d['PCB_sha256']==loss['PCB_sha256']==sha('ecad/wp10_main_input_v26_candidate.kicad_pcb')
assert len(drc['unconnected_items'])==4 and drc['violations']==[]
mem=[]
for _ in range(3):mem.append(psutil.virtual_memory().available/2**20);time.sleep(1)
assert min(mem)>=2048,mem
sealed=['README.md','REVIEW.html','SYSTEM_CLOSURE_MATRIX.csv','results/DELIVERY_DECISION.json']
assert all(sha(p)==sha('history/20260910_V22_before_brake_enable/'+p) for p in sealed)
assert sha('mechanical/CAP_HARNESS_RETAINED_PLAN_V21.json')=='6d2832a3dcbac517dbe97ed0e5e8d2a74fafd1f31de66fb4bb472ae6459119b6'
H=A/'history/20260910_V26_before_activation';H.mkdir(exist_ok=False)
for p in ['ecad/wp10_main_input.kicad_pcb','ecad/POWER_LOOP_INTEGRATION.json']:
 dest=H/p;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(A/p,dest)
assert sha('ecad/wp10_main_input.kicad_pcb')=='a0f07733ad6455ce76246eee0c708c56945476ed0fc76024d21498bc58773ab0'
shutil.copy2(A/'ecad/wp10_main_input_v26_candidate.kicad_pcb',A/'ecad/wp10_main_input.kicad_pcb')
e=read('ecad/POWER_LOOP_INTEGRATION.json');e.update(active_revision='V26',main_input_PCB='ecad/wp10_main_input.kicad_pcb',
 main_input_PCB_sha256=sha('ecad/wp10_main_input.kicad_pcb'),main_input_board_definition='power/MAIN_INPUT_BOARD_DEFINITION_V26.json',
 main_input_board_DRC='results/MAIN_INPUT_CANDIDATE_DRC_V26.json',main_input_copper_loss='power/MAIN_INPUT_COPPER_LOSS_V26.json',
 main_input_DRC_clean=False,main_input_installed_in_whole_assembly=False,whole_power_design_closed=False)
dump('ecad/POWER_LOOP_INTEGRATION.json',e)
review=dict(schema='WP10_V26_READONLY_BOARD_REVIEW',reviewer='/root/cap_terminal_review',status='PASS_FOR_UNRELEASED_ACTIVE_CANDIDATE_UPDATE_ONLY',
 source_hashes=review_hashes,scope='Read-only text and light copper/footprint comparison; no native launch by reviewer',
 findings=['7 fixed nets and 43 footprints preserved against fixed copper',
 'MAIN_RETURN B.Cu y10 corridor; two local ground injection points at x46.5 and x68, not one common star point',
 '4 split-terminal DRC items must remain visible and must not be bridged by board copper',
 'Physical WSLP terminal and correct soldering must connect split lands; fitted continuity unverified',
 'Whole installation, power thermal path and current-qualified termination remain open'],
 manufacturing_release=False,whole_design_complete=False)
dump('results/MAIN_INPUT_READONLY_REVIEW_V26.json',review)
v25=read('results/MAIN_BOARD_NATIVE_V25.json');schematic_inputs={p:h for p,h in v25['inputs'].items() if p.endswith('.kicad_sch') or p.endswith('.kicad_pro')}
assert schematic_inputs and all(sha(p)==h for p,h in schematic_inputs.items())
status=dict(schema='WP10_WORKING_STATUS_V26',revision='V26',time=datetime.datetime.now().astimezone().isoformat(),
 memory_finish_MiB=mem,memory_threshold_MiB=2048,memory_gate_passed=True,
 schematic=dict(symbols=207,pages=13,ERC_errors=0,ERC_warnings=0,ERC_run='V25; schematic and rule inputs unchanged',unchanged_source_hashes=schematic_inputs),
 board=dict(functional_refs=31,footprints=43,pads=103,copper_items=len(native['tracks']),outline_mm=[100,80],
  DRC_unconnected_errors=4,DRC_other_errors=0,DRC_warnings=0,DRC_clean=False,default_ignored_checks=drc['ignored_checks'],
  ordinary_signal_connections_routed=True,Kelvin_split_lands_require_physical_terminal_bridge=True,active_source='ecad/wp10_main_input.kicad_pcb'),
 copper_loss=dict(thickness_assumed_um=70,R20_ohm=loss['R20_ohm'],loss_W_20A_20C=loss['cases'][0]['loss_W'],loss_W_20A_100C=loss['cases'][2]['loss_W'],thermal_path_qualified=False),
 whole_assembly=dict(components_each_state=974,plan_unchanged=True,new_board_installed=False,CAD_update_not_claimed=True),
 closure_matrix_37_rows_unchanged=True,physical_tests_executed=False,manufacturing_release=False,whole_design_complete=False,
 next_required=['Bind actual PCB copper stackup and current-qualified high-power terminations',
 'Create Q201 insulated thermal support and include new copper heat in real TIM/carrier/radiator analysis',
 'Validate fitted split-terminal continuity and Kelvin sensing',
 'Integrate board and support into current 974 assembly, update harness/clearance/mass',
 'Continue source-side buffer, input L/hot-short/full startup and propulsion same-revision ICD closure'])
dump('results/WORKING_STATUS_V26.json',status)
rows=d['refs']
with (A/'power/MAIN_BOARD_PLACEMENT_V26.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f);w.writerow(['ref','MPN','footprint','x_mm','y_mm','rotation_deg'])
 for r in rows:w.writerow([r['ref'],r['MPN'],r['footprint'],*r['position_mm'],r['rotation_deg']])
table='\n'.join(f"| {r['ref']}.{r['pin']} | {r['net']} | {r['power_center_mm']} | {r['sense_center_mm']} |" for r in integrity['terminals'])
md=f'''# WP10 V26：内存恢复，输入保护板完成普通信号布线

2026-09-10 · 同一活动候选 · **整机未交付，板件未制造或通电放行**

末次连续可用内存：{' / '.join(f'{x/1024:.2f}' for x in mem)} GiB，均高于 2 GiB 启动门槛。期间内存再次降到门槛以下，已暂停原生任务并清理后继续。清理记录保留；驻留页回收不等于关闭应用，不保证内存永久保持。

实际板源已经更新为 V26：31 个功能位号、43 个封装、103 个焊盘、{len(native['tracks'])} 个铜线/过孔项，100×80 mm。主功率、回流、Kelvin、门极与本地地线由参数源固定；其余低流信号采用白名单导入并补齐 LDO 引出。Q201 从 (66,17) 移至 (54,17)，其余器件位置不变。

主回流移至 B.Cu 的 y=10 mm 走廊，减小与主正线的横向距离并避开正极通孔。HS 与 LDO 在 x=46.5/68 mm 分别接入主回流；这是两个局部单点接入，**不是统一理想星点**，尚未取得寄生电感或地电位差验证。

原生 DRC：**4 项未连接错误，其他错误 0，警告 0**；V25 为 70 项未连接与 1 项警告。原有 5 项默认忽略未新增或放宽。4 项均为 WSLP 分裂焊盘，原始报告没有隐藏：

| 端子 | 网络 | 功率盘中心/mm | 分离盘中心/mm |
|---|---|---|---|
{table}

这四组分别依赖器件的同一实体端金属及正确焊接连接；裸板铜必须保持隔离，不能为了消除 DRC 提示跨接 0.89 mm 间隙。实装导通、感测偏差和焊接工艺仍未验证。因此 **PCB_DRC_clean=false**，不是“零错误放行”。

铜连接图按实际几何与层建立，重复 pad 编号不会自动添加连接。10 项检查通过，6 类反例均被检出：直接跨槽、外围绕接、双面过孔旁路、C202 搭接感测、感测断线与相切跨槽。31 位号全部焊盘网络与当前整机 XML 相符。原理图源及规则未改变，沿用 V25 的 207 符号/13 页/ERC 0 错误 0 警告记录；本轮未假称重新执行 ERC。

按 70 μm 成品铜厚、20°C 参考电阻率和走线中心线矩形近似，主功率正反向铜电阻约 **{loss['R20_ohm']*1000:.3f} mΩ**，20 A 时铜损 **{loss['cases'][0]['loss_W']:.3f} W**；铜温 100°C 的敏感性约 **{loss['cases'][2]['loss_W']:.3f} W**。70 μm 是待绑定制造条件，尚未得到板厂保证；计算不包含焊盘电流扩散、焊接/接触、通孔镀铜、器件与保险损耗，不构成温升或载流认证，也不能自动回填旧 40 mΩ 总路径假设。参考：[美国国家标准局铜线表](https://www.govinfo.gov/content/pkg/GOVPUB-C13-3b218703c40cd48e0384d3a8b2aff743/pdf/GOVPUB-C13-3b218703c40cd48e0384d3a8b2aff743.pdf)。

已保留失败布线与原生互操作记录。Freerouting 空封装标识的引号已规范化后导入；KiCad 10 过孔 GetWidth 必须指定层，否则会触发原生断言等待。已修复并完成原生回读，不把这些程序问题归因于内存。

[查看实际板图](review/MAIN_INPUT_BOARD_V26.svg) · [当前 PCB 源](ecad/wp10_main_input.kicad_pcb) · [原生 DRC](results/MAIN_INPUT_CANDIDATE_DRC_V26.json) · [铜连接与反例证据](results/MAIN_INPUT_COPPER_INTEGRITY_V26.json) · [铜损计算](power/MAIN_INPUT_COPPER_LOSS_V26.json) · [布局表](power/MAIN_BOARD_PLACEMENT_V26.csv)

本板尚未安装到 974 组件整机；本轮没有更新整机 CAD 或借用 V25 部分三维视图证明新布线。873 组件父本、99 位号父本及原 37 行闭环表保持原有结论。下一步是高电流端接/铜厚、Q201 绝缘热支撑和新增铜损入热路径，再做实体装配与线束配合；供电侧缓冲、热短路、完整启动和推进同修订 ICD 仍需继续收束。
'''
(A/'WORKING_V26.md').write_text(md,encoding='utf-8')
svg=(A/'review/MAIN_INPUT_BOARD_V26.svg').read_text(encoding='utf-8');svg=svg[svg.index('<svg'):]
page=f'''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>WP10 V26 输入保护板</title>
<style>body{{font:16px system-ui;line-height:1.65;background:#eef2f5;color:#152837;max-width:1220px;margin:30px auto;padding:0 22px}}section{{background:#fff;border-radius:12px;padding:22px;margin:18px 0}}.warn{{border-left:6px solid #b46e18}}.fig{{overflow:auto}}svg{{width:100%;height:auto;min-width:850px}}a{{color:#155885}}.facts{{display:flex;gap:32px;flex-wrap:wrap}}.facts b{{display:block;font-size:26px}}</style>
<h1>WP10 V26 · 输入保护与启动监督板</h1><p>同一活动候选 · 已完成普通信号布线 · 整机尚未交付</p>
<section class="facts"><div><b>{mem[-1]/1024:.2f} GiB</b>末次可用内存</div><div><b>31</b>功能位号</div><div><b>4 / 0 / 0</b>未连接 / 其他错误 / 警告</div><div><b>3.43 W</b>20 A、20°C、70 μm 铜假设</div></section>
<section class="warn"><b>未制造或通电放行。</b><p>4 项未连接对应分流电阻的分裂焊盘，依赖器件端金属和正确实装；不得加板铜跨接或隐藏原始 DRC。铜厚、端接、Q201 热支撑及整机安装尚未完成。</p></section>
<section><h2>当前实际 PCB</h2><p>KiCad 原生导出：正面/背面铜、Fab 位号、丝印、外形和安装保留区。回流在 B.Cu y=10 走廊；信号与功率铜未自动混合导入。</p><div class="fig">{svg}</div></section>
<section><h2>验证与后续</h2><p>43 个封装及全部功能焊盘网络回读一致，10 项铜连接检查与 6 类反例通过。原理图保持 V25 的 ERC 0/0，源和规则未改变。本轮没有三维整机装配或物理试验。</p><p>新增约3.43 W铜损必须进入真实热路径；70 μm铜厚尚未制造绑定。整机仍为原974组件计划，板件未安装，原37行闭环表未升级。</p><p><a href="WORKING_V26.md">详细工作记录</a> · <a href="ecad/wp10_main_input.kicad_pcb">当前PCB</a> · <a href="results/MAIN_INPUT_CANDIDATE_DRC_V26.json">完整DRC</a> · <a href="results/MAIN_INPUT_COPPER_INTEGRITY_V26.json">铜连接证据</a> · <a href="power/MAIN_INPUT_COPPER_LOSS_V26.json">铜损计算</a> · <a href="power/MAIN_BOARD_PLACEMENT_V26.csv">布局表</a></p></section></html>'''
(A/'WORKING_V26.html').write_text(page,encoding='utf-8')
paths=set(review_hashes)|set(integrity['source_hashes'])|set(schematic_inputs)|set(sealed)
paths.update(['WORKING_V26.md','WORKING_V26.html','ecad/wp10_main_input.kicad_pcb','ecad/POWER_LOOP_INTEGRATION.json','ecad/wp10_system.xml',
 'results/WORKING_STATUS_V26.json','results/MAIN_INPUT_COPPER_INTEGRITY_V26.json','results/MAIN_INPUT_READONLY_REVIEW_V26.json',
 'power/MAIN_INPUT_BOARD_DEFINITION_V26.json','power/MAIN_INPUT_FIXED_COPPER_V26.json','power/MAIN_INPUT_COPPER_LOSS_V26.json','power/MAIN_BOARD_PLACEMENT_V26.csv',
 'review/MAIN_INPUT_BOARD_V26.svg','tools/publish_main_input_v26.py','tools/check_main_input_candidate_v26.py',
 'tools/memory_reclaim_safe_v24.py','tools/reclaim_idle_app_pages_v26.py','tools/reclaim_ui_resident_pages_v26.py',
 'results/UI_RESIDENT_RECOVERY_V26_recover_20260910_e.json','results/MAIN_INPUT_READBACK_COMMANDS_V26.json','results/MAIN_INPUT_FINISH_COMMANDS_V26.json',
 'ecad/WP10_TIMING.pretty/C201_MKP2_1uF_P5_Slot2.kicad_mod','mechanical/CAP_HARNESS_RETAINED_PLAN_V21.json'])
out=dict(schema='WP10_FINAL_CHECK_V26',passed=True,scope='Reviewed same-candidate board update, not whole delivery',
 source_hashes={p:sha(p) for p in sorted(paths)},file_count=len(paths),memory_samples_MiB=mem,
 PCB_DRC_passed=False,manufacturing_release=False,whole_design_complete=False)
dump('results/FINAL_CHECK_V26.json',out)
print(json.dumps(dict(passed=True,files=len(paths),active_PCB_sha256=sha('ecad/wp10_main_input.kicad_pcb'),memory_MiB=mem,whole_design_complete=False)))
