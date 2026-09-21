"""Publish current V23 analysis overlay; preserve the native V22 and V18 release."""
from pathlib import Path
import csv, datetime, hashlib, html, json
import psutil
import markdown
A=Path(__file__).resolve().parents[1]
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def dump(p,v):(A/p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')

r=read('power/HOTSWAP_TRANSIENT_CALCULATIONS_V23.json');n=read('results/BRAKE_ENABLE_NATIVE_V22.json')
assert r['passed'] and n['passed']
assert all(sha(p)==h for p,h in r['source_bindings'].items())
assert r['definition_sha256']==sha('power/HOTSWAP_TRANSIENT_DEFINITION_V23.json')
assert all(sha(p)==h for p,h in {**n['inputs'],**n['outputs']}.items())
for p in ['README.md','REVIEW.html','SYSTEM_CLOSURE_MATRIX.csv','results/DELIVERY_DECISION.json']:
    assert (A/p).read_bytes()==(A/'history/20260910_V22_before_brake_enable'/p).read_bytes()
assert len(list(csv.DictReader((A/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig'))))==37
assert sha('mechanical/CAP_HARNESS_RETAINED_PLAN_V21.json')=='6d2832a3dcbac517dbe97ed0e5e8d2a74fafd1f31de66fb4bb472ae6459119b6'
review=read('results/HOTSWAP_READONLY_REVIEW_V23.json')
assert review['postfix_code_review_received']
old=read('history/20260910_V23_before_scope_wording/power/HOTSWAP_TRANSIENT_CALCULATIONS_V23.json')
for key in ['cases','short_regulated_prefixes','refined_worst_prefix','ideal_variable_power_integral',
            'repeated_fault_counterexample','warm_timer_counterexample']:
    assert old[key]==r[key],key+' changed after scoped wording/field-name review'
for previous,current in zip(old['timer_candidates'],r['timer_candidates']):
    previous=dict(previous);previous['present_in_native_candidate']=previous.pop('installed')
    previous['physically_installed']=False
    assert previous==current
assert sha('tools/hotswap_transient_model_v23.py')==review['reviewed_source_hashes']['tools/hotswap_transient_model_v23.py']
review['root_final_numeric_comparison_to_reviewed_snapshot_passed']=True
dump('results/HOTSWAP_READONLY_REVIEW_V23.json',review)
f=r['refined_worst_prefix'];m=read('results/BACKGROUND_MEMORY_CLEANUP_V23_begin_20260910.json')
paths=sorted(set(list(r['source_bindings'])+list(n['inputs'])+list(n['outputs'])+[
    'power/HOTSWAP_TRANSIENT_DEFINITION_V23.json','power/HOTSWAP_TRANSIENT_CALCULATIONS_V23.json',
    'power/HOTSWAP_WORST_PREFIX_TRACE_V23.csv','thermal/HOTSWAP_SHORT_BLOCK_LOADS_V23.csv',
    'tools/write_hotswap_working_v23.py','results/HOTSWAP_READONLY_REVIEW_V23.json',
    'results/BACKGROUND_MEMORY_CLEANUP_V23_begin_20260910.json',
    'results/CAP_TERMINAL_MEMORY_RECOVERY_V17_V23_begin_20260910.json',
    'ecad/wp10_c203_terminal.kicad_pcb','ecad/wp10_chb_input.kicad_pcb']))
status=dict(schema='WP10_WORKING_STATUS_V23',time_local=datetime.datetime.now().astimezone().isoformat(),
    status='REDUCED_PROTECTION_TRANSIENT_AND_TIMER_MODEL_INTEGRATED__SYSTEM_CLOSURE_OPEN',
    electrical_revision='V22 native sources unchanged,207symbols/13pages; V23 analysis overlay',
    mechanical_revision='V21,974instances per state; V22 added electrical refs not yet placed in CAD/PCB',
    original_parent_electrical_refs=99,original_parent_mechanical_components=873,
    original_37_rows_unchanged=True,last_sealed_release='V18',
    memory_cleanup_threshold_met=m['threshold_met'],available_memory_now_MiB=psutil.virtual_memory().available/2**20,
    scalar_checks=len(r['checks']),native_ERC_rerun=False,
    native_ERC_evidence_reused_by_exact_source_hash=True,ERC_errors=n['errors'],ERC_warnings=n['warnings'],
    declared_case_outcomes=r['outcomes'],design_decision='Retain1uF C201 allocation; no newly qualified timer or SOA claim',
    inputs={p:sha(p) for p in paths},whole_design_complete=False,physical_tests_executed=False,
    power_on_authorized=False,manufacturing_release=False,
    next_work='Qualify actual gate ramp/control timing and select effective C201/R207 parts; bind Q201 thermal boundary/SOA before changing protection timing; continue same candidate PCB/thermal/mechanical integration.')
dump('results/WORKING_STATUS_V23.json',status)
md=f'''# WP10 V23：内存达标后完成主保护模型修正

2026-09-10 · 同一活动候选 · 整机详细设计仍开放

已回收42个空闲工具进程与14个桌面进程的驻留页，保留正在工作的会话。本次未找到需要终止的已确认闲置辅助进程。连续可用内存2.66/2.82/2.90GiB，达到2GiB启动门槛；随后恢复工程计算。384工况计算进程驻留约{r['process_RSS_MiB']:.1f}MiB。

本轮修改了当前预充计算和生成器中的范围声明，新增可执行限功率及定时电荷模型。原理图保留V22的207符号、13页，原生输入和输出哈希与上轮核验完全一致，原ERC为0错误、0警告。本轮没有重复启动KiCad，也没有新增实物测试。

|声明工况结果|数量|含义|
|---|---:|---|
|冷态欠压，不启动|192|固定的20/22V等低压场景按当前阈值退出|
|退出限流/限功率阶段|172|简化模型的预充前缀完成，不等于整个上电流程通过|
|预充中欠压中断|20|记录中断；恢复、反复启停和BMS行为未模拟|

模型计入共享接点电阻、独立辅助负载、控制器及偏置分账，并随开关压降改变限功率。当前采样中最慢的已完成限幅阶段，经加密为{f['active_limit_s']*1000:.3f}ms；步长加密差{r['refinement_relative_time']*100:.4f}%。这些数值来自声明的集总电路，未包含真实门极充电、控制环带宽和CHB释放过程，不能当作最大上电时间。

定时器在间隔故障之间保留电荷。一个声明反例中，20ms限制、10ms解除重复三次，会在{r['repeated_fault_counterexample']['latch_s']*1000:.3f}ms达到锁断阈值；错误地每次清零会漏判。另一个3V初始残压角点只余{r['warm_timer_counterexample']['latch_s']*1000:.3f}ms至阈值，不继承空电容故障时间。

|C201名义候选|至故障阈值的条件时间|扣除本轮采样1.5倍项目余量后|决定|
|---|---|---|---|
'''
for c in r['timer_candidates']:
    low,high=c['timer_threshold_from_zero_s'];margin=c['remaining_after_project_allowance_s']
    label='保留现有分配，尚未物料资格核验' if c['present_in_native_candidate'] else '不选定'
    md+=f"|{c['nominal_F']*1e9:.0f}nF|{low*1000:.3f}–{high*1000:.3f}ms|{margin*1000:+.3f}ms|{label}|\n"
md+='''
1.5倍为项目筛查余量，不是原厂保证。C201仍保留1µF；680nF在此筛查中余量为负，820nF也未取得门极动态、有效电容、漏电、温度及SOA验证，不能据此替换。机械臂360W和主路361W分配保留。

对上电短路和运行中短路，本轮只计算满足冷启动电压条件的案例在调节建立后的持续应力与定时器到阈值时间；未覆盖仅靠欠压迟滞仍保持ON的所有暖态案例。微秒级快速拉栅不等于永久断电；前沿峰值、最大关断延时、线感过压仍开放。受控块包含Q201及尚未分配的线路损耗，其应力表不是已提取的Q201热模型；C203本地短路储能也不受上游F201限流保障。原厂SOA图未数字化，真实壳温和连续/重复热史未绑定，完整SOA不判通过。

[机器计算与384工况](power/HOTSWAP_TRANSIENT_CALCULATIONS_V23.json) · [最慢前缀轨迹](power/HOTSWAP_WORST_PREFIX_TRACE_V23.csv) · [持续短路块应力](thermal/HOTSWAP_SHORT_BLOCK_LOADS_V23.csv) · [当前记录](results/WORKING_STATUS_V23.json) · [现有电气原生图纸](ecad/wp10_system_v22.pdf)

原873组件/99位号父本与37行闭环表保留。机械停留V21集成状态；本轮计算不授予制造、通电、运动或整机完成信用。后续继续绑定真实门极/偏置时序、定时物料和Q201热边界，再决定是否改件。

依据：[TI LM5069 RevG](https://www.ti.com/lit/ds/symlink/lm5069.pdf)；[IXYS DS100200(9/09)，Advance](https://www.littelfuse.com/assetdocs/littelfuse-discrete-mosfets-ixt-75n10-datasheet?assetguid=ea051e16-aaa9-4983-a975-8d0c07325d72)。前者本地PDF已锁哈希；后者在线核阅，本地下载403，未编造归档或SOA数值。
'''
(A/'WORKING_V23.md').write_text(md,encoding='utf-8')
body='<!doctype html><html lang="zh"><meta charset="utf-8"><title>WP10 V23 主保护计算</title><style>body{max-width:980px;margin:36px auto;padding:0 24px;font:17px/1.7 system-ui;color:#172b3a}table{border-collapse:collapse;width:100%;margin:24px 0;font-size:15px}td,th{border-bottom:1px solid #cbd9e3;padding:10px;text-align:left}th{background:#edf4f8}a{color:#086388}h1{font-size:30px}</style>'+markdown.markdown(md,extensions=['tables'])+'</html>'
(A/'WORKING_V23.html').write_text(body,encoding='utf-8')
final=dict(source_binding_mismatches=[p for p,h in status['inputs'].items() if sha(p)!=h],
    working_status_sha256=sha('results/WORKING_STATUS_V23.json'),working_md_sha256=sha('WORKING_V23.md'),
    source_count=len(status['inputs']),native_job_launched=False,whole_design_complete=False)
dump('results/FINAL_CHECK_V23.json',final)
assert not final['source_binding_mismatches']
print(json.dumps(dict(files_verified=final['source_count'],checks=status['scalar_checks'],memory_MiB=status['available_memory_now_MiB'],whole_design_complete=False)))
