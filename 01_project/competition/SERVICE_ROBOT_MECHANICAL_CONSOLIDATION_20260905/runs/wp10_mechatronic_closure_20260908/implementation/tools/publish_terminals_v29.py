"""Publish a source-bound increment; never turn local checks into whole release."""
from pathlib import Path
import json,csv,hashlib,zipfile,datetime,html,urllib.request,urllib.parse,shutil,psutil
from terminals_v29 import A,H,sha,dump
C=A/'coupled_closure';c=json.loads((C/'CANDIDATE_V29.json').read_text());assert all(sha(p)==h for p,h in c['source_lock'].items())
review=json.loads((C/'READONLY_REVIEW_V29.json').read_text());assert all(sha(A/p)==h for p,h in review['reviewed_hashes'].items())
with (C/'SHA256.csv').open(encoding='utf-8-sig') as f:original=list(csv.DictReader(f))
assert all(sha(C/r['file'])==r['sha256'] for r in original)
e=json.loads((A/'results/TERMINAL_ELECTRICAL_AUDIT_V29.json').read_text());g=json.loads((C/'TERMINAL_GEOMETRY_CHECK_V29.json').read_text());t=json.loads((C/'TERMINAL_THERMAL_V29.json').read_text());v=json.loads((C/'TERMINAL_VALIDATION_V29.json').read_text())
assert e['passed'] and g['passed'] and all(t['checks'].values()) and v['ok']
pr=A/'logs/native_delta_cap19_terminal29_project_si_a_a1.run.json';p=json.loads(pr.read_text());assert p['status']=='COMPLETED' and p['returncode']==0
project_si=json.loads(Path(p['stdout']).read_text());assert project_si['ok'] and project_si['occurrenceCount']==2;dump(C/'TERMINAL_PROJECT_SELF_INTERSECTION_V29.json',project_si)
fine=[r for r in t['cases'] if r['version']=='V29_COPPER' and r['pitch_mm']==5];assert min(r['CHB_case_C'] for r in fine)>105
stamp=datetime.datetime.now().astimezone().isoformat();free=psutil.virtual_memory().available/2**20
viewer='http://127.0.0.1:3245/'+urllib.parse.quote(C.as_posix(),safe='/:')+'?file=main_input_terminals_v29.step.py'
with urllib.request.urlopen(viewer,timeout=12) as response:http_status=response.status
dump(C/'VIEWER_LINKS_V29.json',dict(url=viewer,target=str(C/'main_input_terminals_v29.step.py'),target_exists=True,http_status=http_status,checked_local=stamp))
status=dict(schema='WP10_V29_TERMINAL_INCREMENT',time_local=stamp,whole_design_complete=False,manufacturing_release=False,continuous_thermal_closed=False,active_electrical_refs=211,pin_network_records=677,PCB_functional_refs=35,PCB_footprints=43,PCB_pads=135,PCB_copper_items=356,ERC_errors=0,ERC_warnings=0,DRC_unconnected_Kelvin_items=4,DRC_other_errors=0,DRC_other_warnings=0,electrical_checks=len(e['checks']),electrical_checks_passed=True,geometry_checks=len(g['checks']),geometry_checks_passed=True,thermal_numeric_checks=len(t['checks']),thermal_numeric_checks_passed=True,module_solids=24,module_occurrences=20,unmodeled_board_electrical_refs=23,full_module_topology_closure_orientation_valid=True,full_module_boolean_self_intersection='TIMEOUT_240_S_NOT_PASSED',changed_carrier_and_PCB_boolean_self_intersection='PASS_2_OCCURRENCES',host_module_installed=False,whole_instance_plan_rows_per_state=974,original_package_files_unchanged=len(original),original_37_row_closure_unchanged=True,available_memory_MiB=free,viewer_url=viewer,archive_requires_existing_WP10_baseline=True)
dump(C/'DELIVERY_STATUS_V29.json',status)
imgs={k:next(C.glob('TERMINAL_'+k+'_V29_*.png')).name for k in ['ISO','OPPOSITE','TOP','FRONT']}
dump(C/'VISUAL_REVIEW_V29.json',dict(reviewer='root',viewed_images=[dict(file=n,sha256=sha(C/n)) for n in imgs.values()],observations=['Four OEM studs and their board spacing visible; +0.5 datum seats feet at board surface.', 'Two OEM shunts visible; lower-left carrier notch clears R202.', 'Retained partial Q201/TIM/shoulder and five capacitor references visible.', 'Underside standoffs, board drills and carrier holes visible; no full-population or host-install credit.']))
source='https://www.we-online.com/components/products/datasheet/74651195R.pdf'
md=f'''# WP10 V29 端接与载板改件

本轮已落实四个主电源实物端子、相关PCB改线和载板退让口，整机详细设计仍未闭环。原873组件/99位号父本、37行闭环表和V28整星974实例计划保留；未安装的主输入模块没有计入整星实例数。

- 系统211位号、677针脚网络记录；原207器件和673记录保持，新增J204–J207。
- ERC 0错误/0警告；DRC仍有4项分流电阻Kelvin分离焊盘未连接，其余错误/警告0。没有隐藏或短接这些焊盘。
- 四个74651195R真实九针端子；F201右移2mm、D202左移2mm并重布钳位线；B面回流走廊改为x18/82。
- 端子OEM模型安装偏移+0.5mm，修正支脚插入PCB的问题。R202原厂STEP与旧载板交叠16.3145mm³→0；最大包络间隙1.0mm。载板切除136.5mm³，未给额外散热信用。
- 局部模块24个有效实体、20个部件实例，已导出可供SolidWorks导入的STEP；没有生成原生SLDASM/SLDPRT。板上仍有23个位号未建机械实体，整舱位置未接纳。

{len(e['checks'])}项电气审计、{len(g['checks'])}项针对性几何检查、{len(t['checks'])}项同版数值检查通过。只读复审提出的外包框假连通和DRC身份漏洞已修复。原联合包35项测试属于旧版本，没有复用为本轮测试数量。

全模块拓扑、闭合和方向检查通过；全模块布尔自交检查达到240秒超时，未取得通过信用。另对改动的载板和PCB做了包含自交的专项检查，两件均通过。

## 同版连续热工况

保持V28局部加厚散热板、25.2V/360W机械臂输出场景、原10mΩ线束与接点电阻分配及原示例环境。只将已记账损耗在板上和板外重新分配，没有重复增加电阻。+Y热连接仍为未实现的边界假设。

| 既有接点/线束损耗分到本板的比例 | 本板热耗W | CHB壳温°C | 105°C裕度°C |
|---:|---:|---:|---:|
'''
for r in fine:md+=f"| {r['existing_10mOhm_allocation_fraction_dissipated_on_board']:.0%} | {r['board_heat_W']:.5f} | {r['CHB_case_C']:.5f} | {r['CHB_margin_C']:.5f} |\n"
md+=f'''
以上均未通过连续运行要求。零比例不代表真实接点没有发热。任务轨道、接点电阻、热路径、臂/电池/回生热量尚未完全绑定。

## 原厂限制与剩余改件

[Wurth原厂PDF]({source}) Rev002.001（2022-02-21）的85A仅为20°C条件，受PCB、线耳和线径影响，不能作为本系统额定电流。9针同属一个实体电极。板厚1.6–2.0mm、2.2N·m安装要求需落实；专属条款不适用波峰焊。当前还需M5线耳/螺母/绝缘罩、抗扭支撑、成品板厚与铜厚、焊接和温升验证。项目保留工程样机候选性质。

还需补齐板上实体、重新收敛整舱位置和Q201真实热支撑；核验降损MOSFET的热态SOA与驱动后方可替换。推进仍缺同修订受控ICD，当前全臂逐关节质量惯量未绑定。未开展采购、接电、运动、充装或承压。

## 查看与复现

[交互CAD]({viewer}) · [主输入板SVG](MAIN_INPUT_BOARD_V29.svg) · [STEP](main_input_terminals_v29.step) · [完整电气BOM](ACTIVE_ELECTRICAL_BOM_V29.csv) · [针脚网络](PIN_NETWORKS_V29.csv)

入口CANDIDATE_V29.json绑定59项源；SOURCE_ACTIVATION_V29.json记录实际源替换。旧联合包40个文件保持原哈希，旧输入76文件快照保存在 implementation/history/20260910_V29_before_terminals/。旧CANDIDATE.json应按该历史快照复现，不能据当前已修改的原理图静默更新它的锁。

交付ZIP是当前WP10工作区的增量，依赖既有WP10源与本机受控运行环境。只校验文件可运行 tools/verify_terminal_delivery_v29.py；CAD重建应经现有run_cap19_serial.py守护运行CAD gen命令。不要再次执行prepare/activate脚本覆盖历史。

四视图已由根代理逐张查看。发布时可用内存{free:.1f}MiB；原生任务串行，240秒超时与清理记录均保留。
'''
md+=f'\n![局部模块]({imgs["ISO"]})\n'
(C/'README_V29.md').write_text(md,encoding='utf-8')
trs=''.join(f'<tr><td>{r["existing_10mOhm_allocation_fraction_dissipated_on_board"]:.0%}</td><td>{r["board_heat_W"]:.3f}</td><td>{r["CHB_case_C"]:.3f}</td><td class="bad">{r["CHB_margin_C"]:.3f}</td></tr>' for r in fine)
page=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>WP10 V29｜端接与载板改件</title><style>body{{font:16px/1.7 system-ui,"Microsoft YaHei",sans-serif;color:#203449;background:#f0f4f7;margin:0}}main{{max-width:1100px;margin:auto;padding:36px}}h1{{font-size:32px;line-height:1.3}}h2{{font-size:22px;margin-top:32px}}.lead{{background:#fff2db;border-left:5px solid #b77710;padding:18px}}.cards,.views{{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}}.card,section{{background:white;border-radius:10px;padding:20px;margin:18px 0}}.card strong{{font-size:30px;display:block;color:#176a60}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;border-bottom:1px solid #dde5eb;text-align:left}}.bad{{color:#a02b20;font-weight:650}}img{{width:100%;height:auto;border-radius:8px}}a{{color:#096b9e}}code{{overflow-wrap:anywhere}}.small{{font-size:14px;color:#526779}}@media(max-width:650px){{main{{padding:18px}}.cards,.views{{grid-template-columns:1fr}}}}</style><main>
<p class="small">WP10 · V29 · {html.escape(stamp)}</p><h1>四个实物端子与载板退让口已落地</h1><p class="lead"><b>整机尚不能完全交付。</b> 本轮源文件、PCB与局部STEP已同步；CHB连续热工况仍超温，整舱安装位置未接纳。</p>
<p><a href="{viewer}">打开交互CAD</a> · <a href="main_input_terminals_v29.step">下载STEP</a> · <a href="WP10_V29_TERMINAL_DELTA.zip">下载增量交付包</a> · <a href="README_V29.md">完整说明与复现入口</a></p>
<div class="cards"><div class="card"><strong>211 / 677</strong>位号 / 针脚网络记录；原207 / 673保持</div><div class="card"><strong>24</strong>局部有效实体；20个实例，仍有23个位号未建模</div><div class="card"><strong>ERC 0 / 0</strong>错误 / 警告</div><div class="card"><strong>DRC 4</strong>Kelvin分离焊盘未连接；其余错误/警告0</div></div>
<img src="{imgs['ISO']}" alt="主输入模块，四个M5端子与分流器原厂实体及修改载板">
<section><h2>具体修改与验收范围</h2><ul><li>J204–J207采用74651195R原厂九针封装和STEP，端子铜环与双面铜线连通。</li><li>F201右移2mm避开端子钻孔；D202左移2mm并重新布置钳位线；回流走廊改至x18/82。</li><li>原厂模型偏移+0.5mm后不再插入PCB。R202原厂实体旧交叠16.3145mm³→0，最大包络距改件1.0mm。</li><li>电气{len(e['checks'])}项、针对性几何{len(g['checks'])}项、数值{len(t['checks'])}项检查通过；假接线、错pad和同数量错DRC反例被拒绝。</li></ul><p>全模块拓扑/闭合/方向检查通过；整模块布尔自交检查240秒超时未计通过。改动的载板与PCB另做完整自交检查，两件通过。源文件与旧37行闭环表保留可追溯关系，没有给未安装模块增加整星实例数。</p></section>
<section><h2>连续热工况仍不满足</h2><p>既有10mΩ线束/接点分配只改变热量位置，不重复加阻。V28加厚板、示例环境及未实现的+Y连接边界保持。</p><table><thead><tr><th>既有损耗分到本板</th><th>本板热耗 W</th><th>CHB壳温 °C</th><th>105°C裕度</th></tr></thead><tbody>{trs}</tbody></table><p class="bad">所有情景仍超温；没有通过连续运行、飞行或制造放行。</p></section>
<section><h2>实件条件与剩余工作</h2><p><a href="{source}">原厂85A额定条件</a>不能替代整板与线耳载流温升验证。线耳、螺母、绝缘罩、抗扭支撑、焊接工艺和成品板厚仍须绑定；九针是同一个电极。</p><p>继续补全板上23个位号实体与紧固件、压缩载板/热支撑并收敛舱内位置。Q201低损候选尚未替换，需要热态SOA与驱动验证。推进同修订受控ICD、整机逐关节质量惯量仍未绑定。</p><p><a href="Q201_ALTERNATIVES_REVIEW_V29.md">Q201候选核验记录</a> · <a href="ACTIVE_ELECTRICAL_BOM_V29.csv">电气BOM</a> · <a href="PIN_NETWORKS_V29.csv">针脚网络</a> · <a href="MAIN_INPUT_BOARD_V29.svg">原生PCB SVG</a></p></section>
<div class="views">{''.join('<img src="'+imgs[k]+'" alt="'+k+'视图">' for k in ['OPPOSITE','TOP','FRONT'])}</div><p class="small">STEP可供SolidWorks导入；未生成原生SLDASM/SLDPRT。增量包依赖既有WP10基线。旧联合包40文件原哈希保持，当前可用内存{free:.1f}MiB。</p></main></html>'''
(C/'REVIEW_V29.html').write_text(page,encoding='utf-8')
dump(A/'CURRENT_WORKING_CANDIDATE.json',dict(revision='V29',same_WP10_candidate=True,entry='coupled_closure/REVIEW_V29.html',candidate='coupled_closure/CANDIDATE_V29.json',whole_design_complete=False,source_activation='coupled_closure/SOURCE_ACTIVATION_V29.json'))
readme=A/'README.md';shutil.copy2(readme,H/'README.md')
prefix='> 当前工作入口：[V29 端接与载板改件](coupled_closure/REVIEW_V29.html)。211位号/677针脚记录，整机仍未闭环；下列旧版发布信息按其原版本理解。\n\n'
readme.write_text(prefix+readme.read_text(encoding='utf-8-sig'),encoding='utf-8')
files=set(C.glob('*V29*'))|{C/'main_input_terminals_v29.step.py',C/'main_input_terminals_v29.step',C/'mechanical_parts.py',A/'CURRENT_WORKING_CANDIDATE.json',A/'SYSTEM_CLOSURE_MATRIX.csv',A/'tools/verify_terminal_delivery_v29.py',A/'tools/terminals_v29.py'}
for folder,pattern in [('tools','*v29.py'),('results','*V29*.json'),('power','*V29*.json')]:files.update((A/folder).glob(pattern))
for r in ['ecad/wp10_system.xml','ecad/wp10_main_input.kicad_pcb','ecad/wp10_system_v29.xml','ecad/wp10_main_input_v29_candidate.kicad_pcb','ecad/fp-lib-table','ecad/sym-lib-table','power/SELECTED_BOM.csv','power/MAIN_INPUT_BOARD_DEFINITION_V26.json','power/MAIN_BOARD_PASSIVE_SELECTION_V25.json','power/TIMER_PASSIVE_SELECTION_V24.json']:files.add(A/r)
files.update((A/'ecad').glob('*.kicad_sch'));files.update((A/'ecad').glob('*.kicad_pro'));files.update((A/'ecad').glob('*.pretty/*.kicad_mod'))
files.update((A/'sources/terminal_v29').glob('*'));files.add(A/'sources/wslp2726.pdf')
files.update((A/'logs').glob('*terminal29*.run.json'));files.update((A/'logs').glob('*terminal29*.stdout.log'));files.update((A/'logs').glob('CAP19_SERIAL_terminal29*.json'))
files.update((A/'logs').glob('*shunt29*.run.json'))
files={p for p in files if p.is_file() and p.suffix.lower()!='.zip' and p.name not in ['SHA256_V29.csv','DELIVERY_PACKAGE_CHECK_V29.json']}
manifest=C/'SHA256_V29.csv'
with manifest.open('w',encoding='utf-8',newline='') as f:
 w=csv.writer(f);w.writerow(['file','sha256','bytes'])
 for p in sorted(files):w.writerow([p.relative_to(A).as_posix(),sha(p),p.stat().st_size])
dest=C/'WP10_V29_TERMINAL_DELTA.zip';assert not dest.exists();files.add(manifest)
with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in sorted(files):z.write(p,p.relative_to(A).as_posix())
with zipfile.ZipFile(dest) as z:
 assert z.testzip() is None
 with manifest.open(encoding='utf-8') as f:
  expected=list(csv.DictReader(f))
 for r in expected:assert hashlib.sha256(z.read(r['file'])).hexdigest()==r['sha256']
dump(C/'DELIVERY_PACKAGE_CHECK_V29.json',dict(file_count=len(files),archive_bytes=dest.stat().st_size,archive_sha256=sha(dest),CRC_pass=True,all_manifest_hashes_pass=True,requires_existing_WP10_baseline=True))
print(json.dumps(dict(published=True,archive_files=len(files),archive_bytes=dest.stat().st_size,available_MiB=free,viewer=viewer)))
