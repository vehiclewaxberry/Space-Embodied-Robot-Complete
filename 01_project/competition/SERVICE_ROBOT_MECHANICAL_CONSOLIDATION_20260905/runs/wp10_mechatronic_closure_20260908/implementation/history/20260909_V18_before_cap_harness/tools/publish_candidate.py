from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).resolve().with_name('publish_power_loop.py')),run_name='__main__')
raise SystemExit(0)
# Prior publisher below is retained as source lineage only.
import csv,json,hashlib,html,zipfile,urllib.parse
A=Path(__file__).resolve().parents[1];D=A.parent;BASE=D.parent.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def csvout(p,rows):
 with p.open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
changes={
 'A05':('转换器新安装板及厂家STEP已建；电池/PMM整舱未集成','机械 thermal carrier + power selection','导热界面与全舱安装/夹持/可维修性'),
 'B03':('单RRC3570-4+PMM35+CHB500W-24S24N候选已选','power/POWER_CHAIN_SELECTION.json','预充/保护及20A以下全工况能力，单针温升'),
 'B05':('储能/低电压/效率场景已计算，未冒充任务预算','power/POWER_BUDGET_SCREEN.json','真实任务时序和太阳侧充电闭环'),
 'C03':('新增CHB瞬态与停止板原输入合同冲突已定位','power/POWER_CHAIN_SELECTION.json','独立停止供源、启动路径、全动态链验证'),
 'C04':('禁止将回生回灌CHB；输出阻断边界落实于原理图','ecad/wp10_converter_reference.kicad_sch','选择及实现反向阻断/能量吸收实体和元件'),
 'E04':('10刚体9关节三态来源绑定；官方7电机SDK映射已定','mechanical/B601_DM_KINEMATIC_BINDING.json','本机零位/行程/SDK修订与状态监督绑定'),
 'E05':('PMM正式图示20个端点位置已录入，未杜撰针号','ecad/PMM35_TOPVIEW_ENDPOINTS.csv','端子受控图、两路功率线与真实走线/热'),
 'E06':('单变换器8物理引脚子图与本地sense回路已核验','ecad/CONVERTER_PHYSICAL_PIN_NET.csv','完成供源调理后再接入既有系统与停止回路'),
 'F02':('已补B601名义运动学子树；873物性字段原样保持','mechanical/PARAMETER_PACKET.json','逐运动link质量/COM/惯性，不继承混合URDF质量'),
 'F03':('导热板真实几何与0.2mm界面分配已建','mechanical/converter_installation.step','约42W筛选损耗的真实导热散热校核'),
 'G02':('三态名义FK与源CAD一致；未执行连续碰撞','results/B601_KINEMATIC_VERIFICATION.json','源绑定扫掠/线束/维护路径验证'),
 'H03':('发布同WP10活动改件候选，保留原工作包编号','README.md','推进内部设计责任及原23项闭环；不可制造放行')}
rows=list(csv.DictReader((A/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig')))
for r in rows:
 if r['id'] in changes:
  done,ev,nxt=changes[r['id']];r['execution_state']='SCOPED_SOURCE_CHANGE_DELIVERED__PARENT_PACKAGE_STILL_OPEN';r['new_evidence']=done+' | '+ev;r['next_source_edit']=nxt;r['acceptance_action']='按实际子项证据复核；不升级整项状态'
 if r['id'] in ['D02','D03','D04']:
  r['execution_state']='PUBLIC_LOOKUP_NO_ACCEPTABLE_NEW_ICD';r['new_evidence']='manufacturer historical PDF URL returned HTML, rejected; prior propulsion review retained'
csvout(A/'SYSTEM_CLOSURE_MATRIX.csv',rows)
arm=json.loads((A/'results/B601_KINEMATIC_VERIFICATION.json').read_text());elec=json.loads((A/'results/DELTA_SOURCE_VERIFICATION.json').read_text());dim=json.loads((A/'results/DIMENSION_CHECKS.json').read_text())
guards=[json.loads(p.read_text()) for p in (A/'logs').glob('*.run.json')];samples=[s for g in guards for s in g.get('samples',[])]
memory={'guard_receipts':len(guards),'statuses':[{'name':g['name'],'status':g['status']} for g in guards],'minimum_available_MiB':min(s['available_mib'] for s in samples),'maximum_sampled_combined_RSS_MiB':max(s.get('combined_rss_mib',s['child_tree_rss_mib']) for s in samples),'memory_guard_trigger_retained':True,'cleanup_scope':'guard-owned child tree only','one_brief_overlap':'refs process overlapped full OEM validation; all subsequent CAD was sequential','self_intersection_full_OEM_pass':False}
dump(A/'results/MEMORY_AUDIT.json',memory)
oldrows=list(csv.DictReader((D/'results/OUTPUT_SHA256.csv').open(encoding='utf-8-sig')));mismatch=[]
for r in oldrows:
 p=D/r['path']
 if not p.exists() or sha(p)!=r['sha256']:mismatch.append(r['path'])
assert not mismatch,mismatch
dump(A/'results/PARENT_INTEGRITY.json',{'verified_parent_manifest':str(D/'results/OUTPUT_SHA256.csv'),'count':len(oldrows),'mismatches':mismatch,'all_parent_indexed_bytes_unchanged':True})
decision={'schema':'WP10_IMPLEMENTATION_DELTA_DELIVERY_V1','status':'PUBLIC_SELECTION_AND_SOURCE_CHANGES_DELIVERED__FULL_MECHATRONICS_OPEN','B601_checks':arm['count'],'source_netlist_preservation_checks':elec['count'],'CAD_dimension_checks_passed':dim['all_checks_passed'],'COTS_candidate_count':3,'new_CAD_entries':2,'parent_original_workpackages':len(rows),'remaining_open_ids':[r['id'] for r in rows if r['status'] in ['INTERNAL_DESIGN_OPEN','EXTERNAL_INTERFACE_UNBOUND']],'new_power_system_connected_to_old_99ref_system':False,'new_power_carrier_installed_in_873':False,'engineering_prototype_design_complete':False,'manufacture_release':False,'power_on_authorized':False,'flight_release':False,'OEM_full_self_intersection':'MEMORY_GUARD_NOT_COMPLETED','physical_tests_executed':False,'public_input_missing':['PMM35 exact hardware/application note and mounting/terminal drawing','propulsion same-revision controlled ICD'],'internal_design_remaining':['input protection/precharge/charge budget','reverse blocking/regen/stop supply','battery retention/module layout and thermal','link inertias/drive limits/load paths/full-motion harness']}
assert len(decision['remaining_open_ids'])==23
dump(A/'results/DELIVERY_DECISION.json',decision)
viewer='http://127.0.0.1:3245/'+urllib.parse.quote(str(A).replace('\\','/'),safe='/:')
links={'assembly':viewer+'?file=mechanical%2Fconverter_installation.step.py','plate':viewer+'?file=mechanical%2Fconverter_carrier.step.py'}
dump(A/'results/VIEWER_LINKS.json',links)
iso=next((A/'review').glob('converter_iso_*.png')).relative_to(A).as_posix();plate=next((A/'review').glob('carrier_top_*.png')).relative_to(A).as_posix()
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>WP10 · 公开选型与实际改件</title><style>body{font:16px/1.65 system-ui,"Microsoft YaHei",sans-serif;margin:0;background:#f2f5f8;color:#203243}main{max-width:1100px;margin:36px auto;padding:0 24px}h1{font-size:32px;line-height:1.25}h2{margin-top:0;font-size:22px}.sub{color:#536576}.card{background:white;padding:25px;border-radius:12px;margin:20px 0;border:1px solid #dce4eb}.flag{border-left:5px solid #bc790e;background:#fff8e8;padding:15px 20px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}img{width:100%;height:auto;border-radius:8px}a{color:#075e9d}table{width:100%;border-collapse:collapse}th,td{text-align:left;vertical-align:top;border-bottom:1px solid #dfe5ec;padding:12px 10px}.buttons a{display:inline-block;padding:8px 14px;margin:6px 8px 4px 0;background:#e8f2f9;border-radius:7px}code{font-size:13px}details{margin:15px 0}@media(max-width:700px){.grid{grid-template-columns:1fr}table{font-size:14px}main{padding:0 12px}}</style><main><p class="sub">WP10 / 同一工作包的活动候选 / 2026-09-08</p><h1>公开选型已经落到源文件和机械改件</h1><p>本轮补齐机械臂名义运动树，选定三个电源模块候选，生成单变换器安装板与引脚电气子图。</p><div class="flag"><strong>交付状态：设计增量可查看，整机机电闭环仍开放。</strong><br>新电源尚未接入原99位号电气系统，也尚未安装进873组件总装。不能据此通电、制造或宣称飞行适用。</div><div class="card"><h2>当前选型决定</h2><table><tr><th>角色</th><th>候选</th><th>选择理由 / 当前边界</th></tr><tr><td>独立高功率储能</td><td>RRC3570-4 / 110338</td><td>复用厂家保护电池包；最低端电压、可用任务能量和整舱安装待验证。</td></tr><tr><td>充电与电源路径</td><td>RRC-PMM35 / 110297</td><td>厂家配套智能充电；20 A瓶颈、每针10 A、六针图示需按具体修订落实。</td></tr><tr><td>机械臂变换器</td><td>CHB500W-24S24N ×1</td><td>单模块消除双i7C均流依赖；开路关闭，回灌保护与停止板动态兼容尚未完成。</td></tr></table><div class="buttons"><a href="power/SELECTED_BOM.csv">选型BOM</a><a href="power/POWER_CHAIN_SELECTION.json">完整决策</a><a href="power/POWER_BUDGET_SCREEN.json">功率场景计算</a><a href="README.md">中文设计说明与来源</a></div></div><div class="grid"><div class="card"><h2>实际厂家件＋新安装板</h2><img src="__ISO__" alt="厂家CHB500W STEP与新90毫米安装板"><p>安装件是新责任设计；厂家细节原样复用。0.2 mm导热界面为设计分配，尚不代表选定垫片或热阻合格。</p><div class="buttons"><a href="__VIEW__">旋转查看装配</a><a href="mechanical/converter_installation.step">下载装配STEP</a></div></div><div class="card"><h2>可导入SolidWorks的责任件</h2><img src="__PLATE__" alt="八孔90x90x4毫米安装板"><p>板厚4 mm；器件孔距48.3×50.8 mm；承力接口76×76 mm。八孔与厚度已复核，承力接口还需整星验证。</p><div class="buttons"><a href="__PLATEVIEW__">查看安装板</a><a href="mechanical/converter_carrier.step">下载安装板STEP</a></div></div></div><div class="card"><h2>电源引脚子图</h2><p>8个真实变换器引脚，本地sense，独立输入与输出回流，Trim明确空接；输入保护与输出回生为开放边界。ERC保留2项未供源诊断。</p><div class="buttons"><a href="ecad/wp10_converter_reference.pdf">查看电气PDF</a><a href="ecad/wp10_converter_reference.kicad_sch">可编辑KiCad</a><a href="ecad/CONVERTER_PHYSICAL_PIN_NET.csv">引脚与网络</a><a href="ecad/PMM35_TOPVIEW_ENDPOINTS.csv">PMM图示端点</a></div><details><summary>展开实际电气图</summary><img src="review/converter_schematic.png" alt="本轮KiCad实际导出"></details></div><div class="card"><h2>B601 DM运动树已绑定</h2><p>当前10个刚体、9条关节与官方历史版本匹配。94项来源/姿态检查通过，三态最大FK矩阵残差2.22e-16。夹爪按单电机名义同步关系登记；实物零位、齿条换算及逐link惯性保持未测。</p><table><tr><th>状态</th><th>六关节 / °</th><th>双指位移 / m</th></tr><tr><td>service</td><td>0, -80, -70, 30, 0, 0</td><td>0.015 / 0.015</td></tr><tr><td>parking / released</td><td>0, -30, -60, 40, 0, 0</td><td>0.015 / 0.015</td></tr></table><div class="buttons"><a href="mechanical/B601_DM_KINEMATIC_BINDING.json">来源与运动树</a><a href="mechanical/PARAMETER_PACKET.json">更新后的873参数包</a><a href="../REVIEW.html">原873装配与电气父本</a></div></div><div class="card"><h2>尚需完成的具体设计</h2><ol><li>20 A路径的低电量能力、预充/保险/滤波、触点分流及充电功率调度。</li><li>反向阻断、回生能量吸收与独立停止供源。变换器瞬态±5%不覆盖旧停止板输入合同。</li><li>电池/PMM安装、整舱布置与导热路径；逐运动link物性、完整载荷及连续线束运动。</li><li>推进模块受控ICD：同一修订的针序、指令、喷口坐标、安装和并发点火限制。</li></ol><p>内存保护已执行并仅清理任务进程。厂商细节完整自相交检查未完成，后续轻量拓扑、正体积与尺寸检查完成；没有将未完成项写成通过。</p><div class="buttons"><a href="SYSTEM_CLOSURE_MATRIX.csv">原工作表与新增证据</a><a href="results/DELIVERY_DECISION.json">机器交付判定</a><a href="results/MEMORY_AUDIT.json">内存处置</a><a href="WP10_IMPLEMENTATION_DELTA.zip">下载本轮源文件包</a></div></div></main></html>'''
page=page.replace('__ISO__',iso).replace('__PLATE__',plate).replace('__VIEW__',html.escape(links['assembly'],quote=True)).replace('__PLATEVIEW__',html.escape(links['plate'],quote=True));(A/'REVIEW.html').write_text(page,encoding='utf-8')
current=BASE/'CURRENT_candidate.md';old=current.read_text(encoding='utf-8');marker='## WP10 当前活动改件候选（2026-09-08）'
if marker not in old:
 current.write_text(marker+'\n\n`runs/wp10_mechatronic_closure_20260908/implementation/`：公开模块选择、DM运动树绑定、单变换器安装板和电源子图。交付状态为有界设计增量；整机机电/通电/制造均未放行。\n\n[查看本轮](runs/wp10_mechatronic_closure_20260908/implementation/REVIEW.html)\n\n---\n\n'+old,encoding='utf-8')
files=[p for p in A.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name not in ['OUTPUT_SHA256.csv','WP10_IMPLEMENTATION_DELTA.zip']]
manifest=[{'path':p.relative_to(A).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(files)];csvout(A/'results/OUTPUT_SHA256.csv',manifest)
with zipfile.ZipFile(A/'WP10_IMPLEMENTATION_DELTA.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in files+[A/'results/OUTPUT_SHA256.csv']:z.write(p,p.relative_to(A))
with zipfile.ZipFile(A/'WP10_IMPLEMENTATION_DELTA.zip') as z:assert z.testzip() is None
print(json.dumps({'files':len(files),'parent_files_unchanged':len(oldrows),'zip_bytes':(A/'WP10_IMPLEMENTATION_DELTA.zip').stat().st_size,'viewer':links,'remaining_open_ids':decision['remaining_open_ids']},ensure_ascii=False))
