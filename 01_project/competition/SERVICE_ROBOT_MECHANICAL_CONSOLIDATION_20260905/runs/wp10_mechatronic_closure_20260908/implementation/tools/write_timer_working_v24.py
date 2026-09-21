"""Publish source-bound V24 working overlay without changing the 37-row release."""
from pathlib import Path
import csv,datetime,hashlib,json,math,time
import markdown,psutil
A=Path(__file__).resolve().parents[1]
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def dump(p,v):(A/p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
n=read('results/TIMER_PASSIVES_NATIVE_V24.json');c=read('power/TIMER_PASSIVE_CALCULATIONS_V24.json')
r=read('power/HOTSWAP_TRANSIENT_CALCULATIONS_V24.json');m=read('results/MEMORY_CLEANUP_HARDENING_CHECK_V24.json')
review=read('results/TIMER_READONLY_REVIEW_V24.json')
checks=[];paths=set()
def ck(name,v):checks.append(dict(name=name,passed=bool(v)))
for name,o in [('native',n),('passives',c),('transient',r),('memory',m)]:
 ck(name+'_passed',o['passed'])
 bindings={**o.get('inputs',{}),**o.get('outputs',{}),**o.get('source_bindings',{})}
 ck(name+'_bindings_match',all(sha(p)==h for p,h in bindings.items()))
 paths.update(bindings)
ck('transient_definition_hash_matches',r['definition_sha256']==sha('power/HOTSWAP_TRANSIENT_DEFINITION_V24.json'))
ck('read_only_review_fixes_verified',review['postfix_review_received'])
ck('reviewed_snapshot_hashes_match',all(sha(p)==h for p,h in review['reviewed_source_hashes'].items()))
for p in ['README.md','REVIEW.html','SYSTEM_CLOSURE_MATRIX.csv','results/DELIVERY_DECISION.json']:
 ck('sealed_'+p,(A/p).read_bytes()==(A/'history/20260910_V22_before_brake_enable'/p).read_bytes())
ck('37rows_preserved',len(list(csv.DictReader((A/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig'))))==37)
ck('mechanical_V21_parent_plan_unchanged',sha('mechanical/CAP_HARNESS_RETAINED_PLAN_V21.json')=='6d2832a3dcbac517dbe97ed0e5e8d2a74fafd1f31de66fb4bb472ae6459119b6')
cmds=read('results/TIMER_CAD_COMMANDS_V24.json')
facts=json.loads(cmds[1]['stdout'])['tokens'][0]
ck('C201_three_shapes_and_nominal_bounds',facts['summary']['shapeCount']==3 and
 all(abs(a-b)<1e-7 for a,b in zip(facts['entryFacts']['size'],[7.2,11,22])))
ck('STEP_hash_matches_inspected_artifact',facts['stepHash']==sha('mechanical/c201_mkp2_body_v24.step'))
ck('C201_geometry_validated',json.loads(cmds[2]['stdout'])['ok'])
visual=read('results/TIMER_NATIVE_VISUAL_V24.json')
ck('native_footprint_load_and_drills_passed',visual['native_footprint']['passed'] and visual['native_footprint']['model_count']==1)
paths.update(['results/TIMER_PASSIVES_NATIVE_V24.json','power/TIMER_PASSIVE_CALCULATIONS_V24.json',
 'power/HOTSWAP_TRANSIENT_CALCULATIONS_V24.json','power/HOTSWAP_TRANSIENT_DEFINITION_V24.json',
 'power/HOTSWAP_WORST_PREFIX_TRACE_V24.csv','thermal/HOTSWAP_SHORT_BLOCK_LOADS_V24.csv',
 'power/STARTUP_CIRCUIT_CALCULATIONS.json','power/STOP_FULL_FAULT_BUDGET.json',
 'power/LOAD_SIDE_BRAKE_CALCULATIONS.json','power/BRAKE_READY_CALCULATIONS_V22.json',
 'ecad/POWER_LOOP_INTEGRATION.json','results/TIMER_CAD_COMMANDS_V24.json','results/TIMER_NATIVE_VISUAL_V24.json',
 'results/MEMORY_CLEANUP_HARDENING_CHECK_V24.json','results/TIMER_READONLY_REVIEW_V24.json',
 'results/BACKGROUND_MEMORY_CLEANUP_V24_resume_20260910_a.json',
 'results/CAP_TERMINAL_MEMORY_RECOVERY_V17_V24_hardened_20260910_a.json',
 'review/TIMER_R203_SCHEMATIC_V24.png','review/TIMER_C201_SCHEMATIC_V24.png',
 'review/C201_MKP2_V24_20260910T050000Z.png','mechanical/C201_MKP2_BRIEF_V24.md',
 'tools/sync_timer_corners_v24.py','tools/sync_timer_passives_v24.py','tools/write_timer_working_v24.py'])
samples=[]
for _ in range(3):samples.append(psutil.virtual_memory().available/2**20);time.sleep(1)
dump('results/MEMORY_CHECK_V24_FINISH.json',dict(time_local=datetime.datetime.now().astimezone().isoformat(),available_MiB=samples,threshold_MiB=2048,passed=min(samples)>=2048))
paths.add('results/MEMORY_CHECK_V24_FINISH.json')
ck('current_memory_start_threshold_met',min(samples)>=2048)
assert all(x['passed'] for x in checks),[x for x in checks if not x['passed']]
status=dict(schema='WP10_WORKING_STATUS_V24',time_local=datetime.datetime.now().astimezone().isoformat(),
 status='SIX_PASSIVES_BOUND_ECAD_AND_C201_FOOTPRINT_MODEL_INTEGRATED__SYSTEM_CLOSURE_OPEN',
 electrical_revision='V24;207symbols/13pages; all exported nets identical toV22',
 mechanical_revision='V21 whole assembly unchanged; C201 nominal STEP linked to its library footprint, not placed in whole PCB/assembly',
 original_parent_electrical_refs=99,original_parent_mechanical_components=873,original_37_rows_unchanged=True,
 current_instances_per_mechanical_state=974,last_sealed_release='V18',
 native_ERC_errors=n['errors'],native_ERC_warnings=n['warnings'],ignored_checks=n['ignored_checks'],
 native_checks=n['check_count'],passive_checks=len(c['checks']),transient_checks=len(r['checks']),
 transient_cases=r['case_count'],available_MiB=samples,source_bindings={p:sha(p) for p in sorted(paths)},
 whole_design_complete=False,manufacturing_release=False,power_on_authorized=False,physical_test_executed=False,
 next_work='Bind gate/bias dynamics, Q201 SOA and thermal boundary; place the newly assigned passives in the same candidate control PCB and validate layout/contamination leakage. Keep thermal, battery/PMM and same-revision propulsion ICD work open.')
dump('results/WORKING_STATUS_V24.json',status)
parts=read('power/TIMER_PASSIVE_SELECTION_V24.json')
lines=[]
for ref,v in parts.items():
 spec=(str(v['resistance_ohm']/1000)+'kΩ，0.1%，25ppm/K') if ref.startswith('R') else '1µF，初始±5%，63VDC'
 lines.append('|'+ref+'|'+v['MPN']+'|'+spec+'|')
f=r['refined_worst_prefix']
md=f"""# WP10 V24：内存达标并恢复电气工程化

2026-09-10 · 同一活动候选 · 整机详细设计仍开放

本轮关闭1个空闲Windows小组件进程，回收13个桌面进程和42个工具进程的驻留页。最后连续可用内存为{' / '.join(f'{v/1024:.2f}' for v in samples)}GiB，高于2GiB启动门槛。驻留页可能随使用重新载入；原生检查仍逐次重查内存，并保留512MiB运行保护。

当前清理入口已改为核验同一用户与会话、CPU和I/O样本、真实进程句柄的创建时间与程序路径。结束范围仅为无可见窗口和子进程的已知后台小组件/预加载器；其他命中工具只回收驻留页。重复回执在动作前拒绝，回归检查已执行。旧V21/V22基础脚本仅留作历史，不应直接运行。

本轮已修改真实KiCad原理图、物料表、针脚表来源与生成器，完成以下6个具体型号绑定：

|位号|候选型号|名义规格|
|---|---|---|
"""+"\n".join(lines)+f"""

C201封装采用Ø0.9圆孔加2.0×0.9镀槽，5mm中心距；原厂引出点节距为5±0.5mm。按明确的板孔/孔位/线径公差分配，计算剩余0.10mm节距余量。板厂公差和引脚实际公差尚未绑定，因此不授予制造合格结论。名义壳体7.2×11×16mm及两根引脚STEP已关联到封装，尚未加入974组件整机布置。

原生导出核验{n['check_count']}项通过：207符号、13页、ERC 0错误/0警告，4项既有忽略规则未放宽，全部导出网络保持不变。首次MCP操作遗漏了不存在的Footprint字段，源文件已补齐，原失败证据已归档并重跑通过。原生KiCad也读取了实际圆孔、镀槽和3D模型引用。两页原理图与STEP快照已查看。

器件初始公差条件下，C201到故障阈值的计算时间为29.767–85.647ms；上电插入阈值时间为446.500–1456.010ms。上限使用原厂20°C/50V绝缘电阻向定时电压转用的欧姆模型，板面污染漏电和全温电容仍未验证。0.9–1.1µF是保留的有效电容设计要求，不因初始±5%料号确定而自动满足。

独立审阅指出的两处问题已修正：封装检查现在拒绝槽旋转90°、孔位移到6mm和圆孔过小；初始公差与温度变化采用乘法包络，同时更新UVLO、OVLO和采样电阻敏感性。新384工况复算仍为192冷态欠压、172退出限幅阶段、20预充中欠压。最慢已完成限幅前缀细化为{f['active_limit_s']*1000:.3f}ms，不是完整上电时间上界。

Q201仍保留IXTH75N10L2。公开相近IXTH110N10L2材料也属Advance技术文件，不能据此解决保证SOA与实际壳温缺口。热保护、真实门极动态、完整PCB布置、物理试验以及推进同修订接口仍需继续；本轮没有把整机标为完成。

[查看13页原理图](ecad/wp10_system_v24.pdf) · [器件和定时计算](power/TIMER_PASSIVE_CALCULATIONS_V24.json) · [384工况](power/HOTSWAP_TRANSIENT_CALCULATIONS_V24.json) · [当前机器记录](results/WORKING_STATUS_V24.json) · [C201参数模型](mechanical/c201_mkp2_body_v24.step.py)

![C201名义外形，未加入整机布置](review/C201_MKP2_V24_20260910T050000Z.png)

依据：[WIMA MKP2 03.26原厂目录](https://www.wima.de/wp-content/uploads/media/e_WIMA_MKP_2.pdf)、[Vishay TNPW e3 Rev10-Apr-2026](https://www.vishay.com/docs/28758/tnpw_e3.pdf)、[TI LM5069 RevG](https://www.ti.com/lit/ds/symlink/lm5069.pdf)。所有数值按报告声明条件使用。
"""
(A/'WORKING_V24.md').write_text(md,encoding='utf-8')
body='<!doctype html><html lang="zh"><meta charset="utf-8"><title>WP10 V24 电气工程化</title><style>body{max-width:1050px;margin:36px auto;padding:0 24px;font:17px/1.7 system-ui;color:#182b3a}table{border-collapse:collapse;width:100%;margin:24px 0;font-size:15px}td,th{border-bottom:1px solid #ccd7e1;padding:10px;text-align:left}th{background:#eaf3f6}a{color:#08638a}img{max-width:65%;display:block;margin:auto}h1{font-size:29px}</style>'+markdown.markdown(md,extensions=['tables'])+'</html>'
(A/'WORKING_V24.html').write_text(body,encoding='utf-8')
final=dict(schema='WP10_FINAL_CHECK_V24',checks=checks,passed=all(q['passed'] for q in checks),
 source_count=len(paths),source_binding_mismatches=[p for p,h in status['source_bindings'].items() if sha(p)!=h],
 working_status_sha256=sha('results/WORKING_STATUS_V24.json'),working_md_sha256=sha('WORKING_V24.md'),
 working_html_sha256=sha('WORKING_V24.html'),whole_design_complete=False)
dump('results/FINAL_CHECK_V24.json',final)
assert not final['source_binding_mismatches']
print(json.dumps(dict(passed=final['passed'],source_count=len(paths),final_memory_MiB=samples,whole_design_complete=False)))
