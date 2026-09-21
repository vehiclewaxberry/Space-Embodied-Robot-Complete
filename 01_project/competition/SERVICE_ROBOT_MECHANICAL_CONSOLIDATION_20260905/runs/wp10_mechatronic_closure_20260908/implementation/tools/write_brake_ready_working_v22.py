"""Publish a hash-bound working record, without replacing the sealed release."""
from pathlib import Path
import csv, datetime, hashlib, html, json, psutil, xml.etree.ElementTree as ET
A=Path(__file__).resolve().parents[1];H=A/'history/20260910_V22_before_brake_enable'
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def dump(p,v):(A/p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
n=read('results/BRAKE_ENABLE_NATIVE_V22.json');r=read('power/BRAKE_READY_CALCULATIONS_V22.json')
b=read('power/LOAD_SIDE_BRAKE_CALCULATIONS.json');s=read('power/STARTUP_CIRCUIT_CALCULATIONS.json');f=read('power/STOP_FULL_FAULT_BUDGET.json')
xmlhash=sha('ecad/wp10_system.xml')
assert n['passed'] and r['checks_passed'] and b['checks_passed'] and s['checks_passed'] and f['checks_passed']
assert n['outputs']['ecad/wp10_system.xml']==r['native_xml_sha256']==b['native_netlist_sha256']==s['native_xml_sha256']==f['native_xml_sha256']==xmlhash
assert all(sha(p)==v for p,v in n['inputs'].items())
for p in ['README.md','REVIEW.html','SYSTEM_CLOSURE_MATRIX.csv','results/DELIVERY_DECISION.json']:
 assert sha(p)==hashlib.sha256((H/p).read_bytes()).hexdigest()
assert len(list(csv.DictReader((A/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig'))))==37
assert sha('mechanical/CAP_HARNESS_RETAINED_PLAN_V21.json')=='6d2832a3dcbac517dbe97ed0e5e8d2a74fafd1f31de66fb4bb472ae6459119b6'
assert sha('ecad/wp10_c203_terminal.kicad_pcb')=='66b69437ae0712038cda414a7f413baa4be517940f5097a3440812a1c39d52da'
assert sha('ecad/wp10_chb_input.kicad_pcb')=='7ba02034f6b6c3ddd5b52c72cf26b0eac40daff2f67e6668a97e9f68fd5dbae8'
sources=[
 dict(url='https://www.analog.com/media/en/technical-documentation/data-sheets/MAX5048C.pdf',revision='Rev1 1/15',pages='2,3,6,8',status='PRIMARY_WEB_READ__LOCAL_DOWNLOAD_TIMEOUT',local_pdf_sha256=None),
 dict(url='https://www.analog.com/media/en/technical-documentation/data-sheets/MAX16052-MAX16053.pdf',revision='Rev7 5/18',pages='2,3,7',status='PRIMARY_WEB_READ__LOCAL_DOWNLOAD_TIMEOUT',local_pdf_sha256=None),
 dict(url='https://search.kemet.com/component-documentation/download/specsheet/C0603C102J5GACTU',revision='Generated2026-09-10',pages='1',status='PRIMARY_WEB_READ',local_pdf_sha256=None)]
dump('sources/BRAKE_ENABLE_SOURCE_MANIFEST_V22.json',dict(sources=sources,download_failures=['urllib40s timeout','curl25s timeout for each ADI PDF'],source_local_archive_complete=False))
library=[]
for dest,origin in [('ecad/Device.kicad_sym','symbols/Device.kicad_sym'),('ecad/Package_TO_SOT_SMD.pretty/SOT-23-6.kicad_mod','footprints/Package_TO_SOT_SMD.pretty/SOT-23-6.kicad_mod'),('ecad/Resistor_SMD.pretty/R_0603_1608Metric.kicad_mod','footprints/Resistor_SMD.pretty/R_0603_1608Metric.kicad_mod'),('ecad/Capacitor_SMD.pretty/C_0603_1608Metric.kicad_mod','footprints/Capacitor_SMD.pretty/C_0603_1608Metric.kicad_mod')]:
 p=Path('G:/Windows_program_file/Kicad/share/kicad')/origin
 assert sha(dest)==hashlib.sha256(p.read_bytes()).hexdigest()
 library.append(dict(path=dest,origin=str(p),sha256=sha(dest)))
dump('sources/BRAKE_ENABLE_LIBRARY_MANIFEST_V22.json',library)
before=ET.parse(A/'history/20260910_V22_before_visual_cleanup/wp10_system.xml').getroot();after=ET.parse(A/'ecad/wp10_system.xml').getroot()
def graph(rt):
 return {frozenset((p.get('ref'),p.get('pin')) for p in nt.findall('node')) for nt in rt.findall('./nets/net')}
assert graph(before)==graph(after), 'Visual cleanup must not change connectivity'
native_footprints={c.get('ref'):c.findtext('footprint') for c in after.findall('./components/comp')}
bom_path=A/'ecad/BRAKE_ENABLE_BOM_DELTA_V22.csv'
bom=list(csv.DictReader(bom_path.open(encoding='utf-8-sig')))
for row in bom:
 footprint=native_footprints.get(row['reference'])
 if footprint:row['footprint']=footprint
 row['footprint_basis']='NATIVE_SCHEMATIC_CANDIDATE_NOT_PCB_PLACEMENT' if footprint else 'UNBOUND'
with bom_path.open('w',encoding='utf-8-sig',newline='') as target:
 writer=csv.DictWriter(target,fieldnames=list(bom[0]));writer.writeheader();writer.writerows(bom)
sync=read('results/BRAKE_ENABLE_SOURCE_SYNC_V22.json')
sync.update(native_match_pending=False,native_match_verified=True,native_xml_sha256=xmlhash,native_check='results/BRAKE_ENABLE_NATIVE_V22.json')
dump('results/BRAKE_ENABLE_SOURCE_SYNC_V22.json',sync)
integration_path=A/'ecad/POWER_LOOP_INTEGRATION.json'
saved=A/'history/20260910_V22_before_brake_enable/POWER_LOOP_INTEGRATION_before_metadata_refresh.json'
if not saved.exists():saved.write_bytes(integration_path.read_bytes())
integration=json.loads(integration_path.read_text(encoding='utf-8-sig'))
integration.update(added_refs=n['components']-99,active_revision='V22',native_xml_sha256=xmlhash,whole_power_design_closed=False)
if 'wp10_brake_ready' not in integration['power_pages']:integration['power_pages'].append('wp10_brake_ready')
dump('ecad/POWER_LOOP_INTEGRATION.json',integration)
render=read('results/BRAKE_READY_RENDER_V22.json')
assert render['native_pdf_sha256']==sha('ecad/wp10_system_v22.pdf') and render['image_sha256']==sha('review/BRAKE_READY_NATIVE_V22.png')
render.update(visual_review_pending=False,root_viewed_actual_image=True,scope='READY page readable after label wire stubs and field cleanup; full PDF visual audit and PCB layout not credited')
dump('results/BRAKE_READY_RENDER_V22.json',render)
review=dict(status='CONCERN_SCOPED_READONLY_REVIEW',reviewed_snapshot='Before final visual cleanup and last scalar wording fixes',
 findings=[dict(issue='2mA mislabeled as TLV specification',resolution='Replaced by project allocation; exact1.3V/0.4mA,1.8V/3mA,5V/5mA rows and12V transfer disclosed'),dict(issue='Sixth falsifier hardcoded true',resolution='Now five numerical counterexamples and a separately named scope declaration')],
 root_fix_and_rerun_executed=True,independent_postfix_rereview_executed=False,final_visual_graph_equal_to_reviewed_graph=True,hardware_or_release_credit=False)
dump('results/BRAKE_READY_READONLY_REVIEW_V22.json',review)
memory=read('results/BACKGROUND_MEMORY_CLEANUP_V22.json')
out=dict(schema='WP10_WORKING_STATUS_V22',status='BRAKE_READY_INTERFACE_IMPLEMENTED__CONDITIONAL_VALIDATION__SYSTEM_CLOSURE_OPEN',time_local=datetime.datetime.now().astimezone().isoformat(),
 mechanical_revision='V21 retained,974instances per state; geometric proofs retain their original scope',electrical_revision='V22',
 original_parent_refs=99,electrical_symbols=n['components'],new_electrical_refs=['U304','R308','R309','R310','C307','C308'],
 mechanical_ECAD_delta_integration_complete=False,new_brake_parts_placed_on_PCB=False,new_brake_parts_added_to_CAD=False,
 ERC_errors=n['errors'],ERC_warnings=n['warnings'],ERC_ignored_unchanged=len(n['ignored_checks']),native_checks=n['check_count'],
 brake_checks=b['check_count'],startup_checks=s['check_count'],fault_checks=f['check_count'],numerical_counterexamples=len(r['falsifiers']),
 memory_cleanup_threshold_met=memory['threshold_met'],available_memory_now_MiB=psutil.virtual_memory().available/2**20,
 last_sealed_release='V18',original_37_rows_unchanged=True,whole_design_complete=False,energization_authorized=False,manufacture_release=False,
 obsolete_binding_note='V20/V21 ERC and old XML-bound reports are historical evidence. V22 native and renewed scalar checks listed here are current. Existing mechanical geometry is not a V22 full electromechanical release.',
 next_work='Primary protection: normal precharge, startup into short and hot short with actual MOSFET SOA/source path; READY warm restart/gate-load/bypass qualification and PCB integration remain open.')
paths=list(n['inputs'])+['ecad/wp10_system.xml','ecad/wp10_system_v22.pdf','ecad/WP10POWER.kicad_sym','ecad/WP10READY.kicad_sym','ecad/Device.kicad_sym','ecad/sym-lib-table','ecad/fp-lib-table','ecad/BRAKE_ENABLE_BOM_DELTA_V22.csv',
 'power/LOAD_SIDE_BRAKE_DEFINITION.json','power/LOAD_SIDE_BRAKE_CALCULATIONS.json','power/BRAKE_READY_CALCULATIONS_V22.json','power/STARTUP_CIRCUIT_CALCULATIONS.json','power/STOP_FULL_FAULT_BUDGET.json','power/POWER_LOOP_CALCULATIONS.json',
 'tools/brake_circuit_definition.py','tools/brake_ready_analysis_v22.py','tools/verify_load_side_brake.py','tools/verify_startup_and_fault.py','tools/sync_brake_enable_v22.py','tools/render_brake_ready_v22.py','tools/write_brake_ready_working_v22.py',
 'results/BRAKE_ENABLE_NATIVE_V22.json','results/BRAKE_ENABLE_SOURCE_SYNC_V22.json','ecad/POWER_LOOP_INTEGRATION.json','results/BRAKE_READY_RENDER_V22.json','results/BRAKE_READY_READONLY_REVIEW_V22.json','sources/BRAKE_ENABLE_SOURCE_MANIFEST_V22.json','sources/BRAKE_ENABLE_LIBRARY_MANIFEST_V22.json','results/BACKGROUND_MEMORY_CLEANUP_V22.json','mechanical/CAP_HARNESS_RETAINED_PLAN_V21.json']
out['inputs']={p:sha(p) for p in sorted(set(paths))}
dump('results/WORKING_STATUS_V22.json',out)
md=f'''# WP10 V22：制动偏置 READY 接口已改件

2026-09-10 · 同一活动候选 · 机电整机闭环仍开放

内存清理后恢复工程检查。已关闭闲置 Windows 小组件，回收42个闲置工具及13个Claude进程的驻留页；Claude会话、Codex、系统服务保留。清理后连续可用内存为2.67/2.95/3.06GiB，超过2GiB启动门槛。原生任务采用串行内存保护。

本轮已通过KiCad MCP实际改动原生源：U303改为MAX5048CAUT+T；增加U304 MAX16053AUT+T、200k/10k分压、接收端100k下拉及延时/旁路电容，共新增6位号。LT3013 PG只作独立诊断，READY由偏置电压监测产生。绝对过压和独立STOP热故障连接保留。

|验证|本轮结果|范围|
|---|---|---|
|原生层级/网表|13页、207符号、521项通过|原99位号保留；原引脚仅U303.6改网|
|ERC|0错误、0警告；原4项忽略不变|首次误连/库路径问题已修复，失败记录保留|
|制动接口计算|124项通过|含5个数值反例；静态条件转用明列|
|启动与完整故障网|50项＋8项通过|同当前XML重新计算；不替代硬件试验|
|READY释放阈值|{r['rising_threshold_sensitivity_V'][0]:.6f}–{r['rising_threshold_sensitivity_V'][1]:.6f}V|名义10.5V，电阻/输入电流敏感性|
|READY高/低电平|≥{r['ready_high_min_sensitivity_V']:.6f}V / ≤0.4V|输入负载条件转用；接收阈值2.0/0.8V|

[查看完整原生电气图纸，第13页为新增接口](ecad/wp10_system_v22.pdf) · [新增/变更器件表](ecad/BRAKE_ENABLE_BOM_DELTA_V22.csv) · [机器记录](results/WORKING_STATUS_V22.json)

![实际原生PDF第13页](review/BRAKE_READY_NATIVE_V22.png)

C302改为22µF名义、要求有效≥10µF；C305改为2.2µF名义、要求有效≥1µF。有效电容、物料、偏压、温度及布局资格仍待核验。C307选定KEMET C0603C102J5GACTU。新增监测约8.246mW为32V声明场景下的敏感性账，计入原有未验证1W制动偏置预留；机械臂360W未降低。

首次连续冷启动的0.5ms禁止期与TLV6700的450µs有效等待分别绑定原厂条款。延时电容参数给出2.999–5.528ms敏感性范围，不能当作保证最大延时；暖启动残压、实际回生轨迹、驱动器热关断、总线寄生与电容仍开放。

机械模型保留V21每状态974实例；新增电气器件尚未布板或加入CAD。V18封存页和原37行表保持原样，旧XML绑定证据不冒充V22整机验收。下一项优先工作为主保护三类故障过程和SOA配合，并继续完成制动驱动/PCB与热路径验证。

依据：[MAX5048C Rev1](https://www.analog.com/media/en/technical-documentation/data-sheets/MAX5048C.pdf)、[MAX16053 Rev7](https://www.analog.com/media/en/technical-documentation/data-sheets/MAX16052-MAX16053.pdf)、[KEMET电容规格](https://search.kemet.com/component-documentation/download/specsheet/C0603C102J5GACTU)。ADI原厂正文已在线核阅，本地PDF下载超时，未编造归档哈希。
'''
(A/'WORKING_V22.md').write_text(md,encoding='utf-8')
page=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>WP10 V22 制动接口改型</title><style>body{{max-width:1120px;margin:36px auto;padding:0 24px;background:#f5f6f7;color:#182333;font:17px/1.8 system-ui}}article{{background:white;padding:30px;border-radius:14px}}img{{max-width:100%;border:1px solid #ccd4dc}}a{{color:#075c9b}}pre{{white-space:pre-wrap;font:inherit}}</style><article><h1>WP10 V22 · 制动偏置 READY</h1><p>已完成实际原理图改件和同源核验。<strong>13页，207符号，ERC 0错误 / 0警告。</strong></p><p><a href="ecad/wp10_system_v22.pdf">打开原生电气图纸</a> · <a href="ecad/BRAKE_ENABLE_BOM_DELTA_V22.csv">器件变更表</a> · <a href="WORKING_V22.md">详细说明</a> · <a href="results/WORKING_STATUS_V22.json">机器记录</a></p><p>内存清理后恢复串行检查。整机闭环仍开放：新增器件布板/装配、暖启动、实际回生与热路径尚未完成。</p><img src="review/BRAKE_READY_NATIVE_V22.png" alt="原生KiCad导出的READY接口页"><p>阈值10.221–10.783V为条件敏感性；机械模型仍为V21。未授予制造、接电或实物动作放行。</p></article></html>'''
(A/'WORKING_V22.html').write_text(page,encoding='utf-8')
print(json.dumps({k:out[k] for k in ['status','native_checks','brake_checks','startup_checks','fault_checks','available_memory_now_MiB','whole_design_complete']}))
