"""Publish the current bounded board work without overwriting sealed whole-system entries."""
from pathlib import Path
import collections,csv,hashlib,html,json,time
import psutil
A=Path(__file__).resolve().parents[1]
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def dump(p,v):(A/p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
native=read('results/MAIN_BOARD_NATIVE_V25.json');board=read('power/MAIN_INPUT_BOARD_DEFINITION_V25.json');drc=read('results/MAIN_INPUT_BOARD_DRC_V25.json')
startup=read('power/STARTUP_CIRCUIT_CALCULATIONS.json');rev=read('results/MAIN_BOARD_READONLY_REVIEW_V25.json')
cad=read('results/MAIN_INPUT_BOARD_CAD_COMMANDS_V25.json');assert all(q['returncode']==0 for q in cad)
png=Path(json.loads(cad[-1]['stdout'])['outputs'][0]['path']).relative_to(A).as_posix()
mem=[read('results/BACKGROUND_MEMORY_CLEANUP_V25_resume_20260910_a.json'),read('results/CAP_TERMINAL_MEMORY_RECOVERY_V17_V25_resume_20260910_a.json')]
samples=[]
for _ in range(3):samples.append(psutil.virtual_memory().available/2**20);time.sleep(1)
dump('results/MEMORY_CHECK_V25_FINISH.json',dict(samples_MiB=samples,threshold_MiB=2048,passed=min(samples)>=2048,no_permanent_memory_guarantee=True))
errors=sum(v['severity']=='error' for v in drc['violations']);warnings=sum(v['severity']=='warning' for v in drc['violations']);unconnected=len(drc['unconnected_items'])
selected=read('power/MAIN_BOARD_SELECTION_V25.json')
rows=[dict(reference=r['ref'],MPN=r['MPN'],footprint=r['footprint'],x_mm=r['position_mm'][0],y_mm=r['position_mm'][1],rotation_deg=r['rotation_deg']) for r in board['refs']]
with (A/'power/MAIN_BOARD_PLACEMENT_V25.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
status=dict(schema='WP10_WORKING_STATUS_V25',revision='V25',scope='MEMORY_RECOVERY_AND_31_REF_MAIN_INPUT_PCB_CANDIDATE',
 memory_trimmed=sum(sum(r.get('trim_ok',False) for r in m['rows']) for m in mem),
 memory_processes_terminated=sum(len(m['processes_terminated']) for m in mem),memory_finish_MiB=samples,
 schematic=dict(symbols=native['components'],pages=native['pages'],ERC_errors=native['errors'],ERC_warnings=native['warnings'],all_pin_nets_preserved=True),
 board=dict(functional_refs=31,wire_landings=8,mounting_holes=4,outline_mm=[100,80],thickness_mm=1.6,
  DRC_geometry_errors=errors,DRC_warnings=warnings,DRC_unconnected_errors=unconnected,DRC_ignored_checks=drc['ignored_checks'],routing_complete=False),
 whole_assembly=dict(plan='mechanical/CAP_HARNESS_RETAINED_PLAN_V21.json',components_each_state=974,plan_unchanged=True,new_board_installed=False),
 physical_tests_executed=False,manufacturing_release=False,whole_design_complete=False,
 CAD_view=dict(source='mechanical/main_input_board_v25.step.py',STEP='mechanical/main_input_board_v25.step',snapshot=png,
  scope='Partial substrate/drill geometry, rectangular copper envelopes and5 nominal film-capacitor bodies; semiconductor/resistor bodies, heatsink and harness absent'),
 next_required=['Route remaining70 connections with high-current/return and Kelvin constraints; finish C201 silk',
 'Bind PCB copper stackup, high-current landings/lugs and Q201 electrically insulated thermal support',
 'Bind supply-side buffer/input L, hot-short TVS/diode trajectory and full startup brown-ramp behavior',
 'Fit this board into current974 layout and update actual routing, clearance and mass before whole integration'])
dump('results/WORKING_STATUS_V25.json',status)
md=f'''# WP10 V25：内存达标，输入保护板进入实际 PCB 布置

2026-09-10 · 同一活动候选 · **整机尚未交付，板件尚未制板放行**

本轮释放{status['memory_trimmed']}个进程的驻留内存，未结束可见应用。没有找到符合关闭条件的闲置后台小组件或预加载器。清理后约3.15GiB；结束前连续可用内存为{' / '.join(f'{x/1024:.2f}' for x in samples)}GiB，2GiB启动门槛仍由每次原生启动重新核查。

已经把主输入保护、预充定时及CHB启动监督组成同一31位号PCB模块：100×80×1.6mm，4个M3安装孔，8个明确标为项目定义的线缆焊接/测试落点。模块直接读取当前207位号系统XML；没有另建原理图项目，C203和CHB既有端接板保持外部实例，独立辅助供电仍在主保险之前。

11个启动电阻和4个电容落实到完整料号；R215选0805、R218选1210以满足阻值系列范围。过时的MBR3100替换为原厂标为Active的STPS3H100U。两只二极管保持项目1=A、2=K，阴极标记明确靠pad2。新件的3A和75A/10ms规格不是整机钳位验证。

WSLP2726落实分开的功率盘和Kelvin盘，R201/R202本体高度分别为2.90/3.81mm。两条感测铜从外端窄盘独立接入U201，未取串联中点。Q201保留IXTH75N10L2，改用圆孔和横槽容纳引脚截面与节距分配；板厂公差、引脚整形、带电Drain散热片和SOA仍待完成。

原生原理图导出：207符号、13页、ERC 0错误/0警告，全部针脚网络与V24相同。启动和故障网复算50+8项通过，门极静态敏感性为{startup['qualification']['gate_high_sensitivity_V'][0]:.6f}–{startup['qualification']['gate_high_sensitivity_V'][1]:.6f}V；制动接口124项检查通过。以上不是整机功能试验。

C211为1.5µF/100V；C212由10µF名义占位改为4.7µF/100V，初始下限4.465µF大于3.3µF要求。已更新容量和ESR口径，未继承旧10µF掉电储能。全温有效容量、ESR及启动动态仍开放。

首次PCB检查发现R218与C213短路，以及U205地线靠近ADJ，均已改源重跑并保留失败证据。当前报告为**{unconnected}项未连接错误＋{warnings}项丝印警告**；其余几何/短路错误{errors}项。默认忽略规则为{len(drc['ignored_checks'])}项，报告已完整保留。不得把原理图ERC清零称作PCB布线完成。

[查看原生原理图](ecad/wp10_system_v25.pdf) · [PCB源](ecad/wp10_main_input.kicad_pcb) · [31位号布局表](power/MAIN_BOARD_PLACEMENT_V25.csv) · [实际DRC报告](results/MAIN_INPUT_BOARD_DRC_V25.json)

![PCB部分机械视图]({png})

三维视图含真实板形/孔槽、矩形铜盘包络及5个薄膜电容名义外形；**没有包含半导体/电阻本体、Q201散热组件或线束**。铜盘仅作矩形包络，不能导出替代CAM。模型尚未装入974组件总装，873父本和原37行闭环表未改写。

下一步继续完成70项连接的布线、铜厚和高电流端接/Q201热支撑，并完成供电侧缓冲与热短路验证，再将此板实际装入当前整机布置。

资料：[STPS3H100U原厂状态](https://www.st.com/en/diodes-and-rectifiers/stps3h100.html)、[ST数据表](https://www.st.com/resource/en/datasheet/stps3h100.pdf)、[WIMA MKS2](https://www.wima.de/wp-content/uploads/media/e_WIMA_MKS_2.pdf)、[TNPW e3](https://www.vishay.com/docs/28758/tnpw_e3.pdf)。ST二进制本地下载超时；使用已读取的原厂在线资料，不填造本地PDF哈希。
'''
(A/'WORKING_V25.md').write_text(md,encoding='utf-8')
table=''.join('<tr>'+''.join('<td>'+html.escape(str(r[k]))+'</td>' for k in rows[0])+'</tr>' for r in rows)
svg=(A/'review/MAIN_INPUT_BOARD_V25.svg').read_text(encoding='utf-8');svg=svg[svg.index('<svg'):]
page=f'''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>WP10 V25 输入保护板候选</title>
<style>body{{font:16px system-ui;background:#eef2f4;color:#182736;max-width:1250px;margin:30px auto;padding:0 22px;line-height:1.6}}section{{background:white;padding:22px;margin:18px 0;border-radius:12px}}h1{{font-size:28px}}.warn{{border-left:6px solid #b76a19}}.fig{{overflow:auto}}.fig svg{{width:100%;height:auto;min-width:760px;background:#fff}}img{{max-width:100%}}table{{border-collapse:collapse;font-size:13px}}td,th{{border:1px solid #ccd5dc;padding:6px}}a{{color:#14558b}}.facts{{display:flex;gap:20px;flex-wrap:wrap}}.facts b{{font-size:25px;display:block}}button{{padding:8px 16px}}</style>
<h1>WP10 V25 · 主输入保护与启动许可板</h1><p>同一活动候选 · 2026-09-10 · 内存达标后完成实际板级落源</p>
<section class="facts"><div><b>31</b>板上功能位号</div><div><b>100 × 80 mm</b>4个安装孔 · 8个项目落点</div><div><b>ERC 0 / 0</b>207符号 · 13页</div><div><b>{samples[-1]/1024:.2f} GiB</b>结束前可用内存</div></section>
<section class="warn"><b>当前交付范围：可继续布线的板级设计候选。</b><p>PCB仍有{unconnected}项未连接错误及{warnings}项C201丝印警告。还未完成高电流铜厚/端接、Q201热支撑和整机安装。本轮未制造、接电或开展物理试验。</p></section>
<section><h2>实际 PCB 图</h2><p>下图直接来自KiCad原生SVG导出。包括已放置的真实封装、孔位、初步功率路径和两条Kelvin感测铜；参考位号放在Fab层。</p><div class="fig">{svg}</div></section>
<section><h2>部分机械视图</h2><p>板形、孔槽、铜盘矩形包络及5个薄膜电容。半导体/电阻本体、Q201散热支撑和线束未建入；尚未加入974组件总装。</p><img src="{png}" alt="部分PCB机械模型"><p><a href="mechanical/main_input_board_v25.step">下载部分STEP</a> · <a href="mechanical/main_input_board_v25.step.py">参数源</a></p></section>
<section><h2>本轮实际修正</h2><p>15个被动器件完成精确选型；D202换用STPS3H100U。R201/R202采用分离的功率与Kelvin焊盘。U205使用正确DE-12和接地EP13。Q201扩大孔槽以适配最大引脚截面。已修复R218/C213短路和U205地线间距问题。</p><p>C212现在为4.7µF，初始下限4.465µF；全温有效电容和完整启动动态仍待验证。当前PCB的原生DRC问题没有被隐藏。</p></section>
<section><h2>源文件与证据</h2><p><a href="ecad/wp10_system_v25.pdf">13页原理图</a> · <a href="ecad/wp10_main_input.kicad_pcb">PCB源</a> · <a href="results/MAIN_INPUT_BOARD_DRC_V25.json">完整DRC</a> · <a href="power/MAIN_BOARD_PLACEMENT_V25.csv">布局CSV</a> · <a href="WORKING_V25.md">详细记录</a></p><details><summary>展开31位号表</summary><table><tr>{''.join('<th>'+k+'</th>' for k in rows[0])}</tr>{table}</table></details></section></html>'''
(A/'WORKING_V25.html').write_text(page,encoding='utf-8')
# Bind current deliverables, not the historical working reports, into one snapshot.
paths=set(native['inputs'])|set(native['outputs'])|set(rev['source_hashes'])
paths.update(['WORKING_V25.md','WORKING_V25.html','results/WORKING_STATUS_V25.json','results/MAIN_BOARD_READONLY_REVIEW_V25.json',
 'results/MEMORY_CHECK_V25_FINISH.json','power/POWER_LOOP_PARTS.json','power/SELECTED_BOM.csv','ecad/POWER_LOOP_PIN_NET.csv',
 'power/MAIN_BOARD_PLACEMENT_V25.csv','power/STARTUP_CIRCUIT_CALCULATIONS.json','power/STOP_FULL_FAULT_BUDGET.json',
 'power/BRAKE_READY_CALCULATIONS_V22.json','tools/verify_startup_and_fault.py','tools/startup_circuit_definition.py',
 'mechanical/main_input_board_v25.step.py','mechanical/main_input_board_v25.step','results/MAIN_INPUT_BOARD_CAD_COMMANDS_V25.json',png,'review/MAIN_INPUT_BOARD_V25.svg'])
paths.update(['sources/wima_mks2_v25.pdf','sources/wima_mkp2_v24.pdf','sources/tnpw_e3_20260410_v24.pdf',
 'sources/lm5069_rev_g.pdf','sources/wslp2726.pdf','sources/lt3013.pdf','sources/startup_tps3808.pdf',
 'tools/run_main_board_v25.py','tools/build_main_board_cad_v25.py','tools/integrate_power_loop.py',
 'tools/write_main_board_working_v25.py','results/MAIN_INPUT_BOARD_COMMANDS_V25.json'])
for row in board['refs']:
 lib,name=row['footprint'].split(':');paths.add('ecad/'+lib+'.pretty/'+name+'.kicad_mod')
sealed=['README.md','REVIEW.html','SYSTEM_CLOSURE_MATRIX.csv','results/DELIVERY_DECISION.json']
checks=dict(native_binding=native['passed'],source_still_current=all(sha(p)==h for p,h in native['inputs'].items()),
 review_still_current=all(sha(p)==h for p,h in rev['source_hashes'].items()),
 sealed_whole_records_unchanged=all(sha(p)==sha('history/20260910_V22_before_brake_enable/'+p) for p in sealed),
 whole974_plan_unchanged=sha('mechanical/CAP_HARNESS_RETAINED_PLAN_V21.json')=='6d2832a3dcbac517dbe97ed0e5e8d2a74fafd1f31de66fb4bb472ae6459119b6',
 CAD_commands_completed=all(q['returncode']==0 for q in cad),memory_minimum=min(samples)>=2048)
dump('results/FINAL_CHECK_V25.json',dict(passed=all(checks.values()),checks=checks,source_hashes={p:sha(p) for p in sorted(paths)},
 source_file_count=len(paths),whole_design_complete=False,PCB_DRC_passed=False,unconnected_items=unconnected))
print(json.dumps(dict(snapshot_checks=checks,files=len(paths),whole_design_complete=False,memory_MiB=samples)))
assert all(checks.values()),checks
