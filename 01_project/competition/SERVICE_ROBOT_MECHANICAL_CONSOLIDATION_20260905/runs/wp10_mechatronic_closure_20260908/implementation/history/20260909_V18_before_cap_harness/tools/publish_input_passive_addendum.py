"""Publish V13 only after native checks and the same-source read-only review."""
from pathlib import Path
import csv,hashlib,html,json,collections
A=Path(__file__).resolve().parents[1];H=A/'history/20260909_V12_before_input_passives'
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def dump(p,v):(A/p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
r=read('power/INPUT_PASSIVE_CALCULATIONS.json'); sb=read('power/SHARED_BATTERY_PATH_CALCULATIONS.json')
rv=read('results/INPUT_PASSIVE_READONLY_REVIEW.json'); nv=read('results/POWER_LOOP_VERIFICATION.json')
assert r['passed'] and sb['checks_passed'] and nv['all_connectivity_checks_passed']
assert all(sha(p)==v for p,v in r['bindings'].items())
assert all(sha(p)==v for p,v in sb['inputs'].items())
assert all(sha(p)==v for p,v in sb['source_scripts'].items())
assert all(sha(p)==v for p,v in rv['reviewed_files'].items())
assert rv['review_complete'] and not rv['unrepaired_findings']
assert sha('mechanical/ROOT_BUSHING_INSTANCE_PLAN.json')=='c302bf5b4d5bf42ece6e9cec85c4c67d4b8b70631b79d7e838cadb3ce9151533'
for name in ['native_delta_input_passive_build','native_delta_input_passive_footprint']:
 g=read('logs/'+name+'.run.json');assert g['status']=='COMPLETED' and g['returncode']==0
fp=read('results/INPUT_PASSIVE_FOOTPRINT_NATIVE.json');assert fp['footprint_parse_and_export_pass']
anchor=next(q for q in sb['cases'] if q['id']=='SBP132')
v=anchor['run']; f201=(v['main_A']+v['controller_A'])**2*.0017
# The old read-only receipt remains in the archived V12. Current path points at V13.
compat=dict(schema='WP10_SHARED_BATTERY_READONLY_REVIEW_V2',reviewer=rv['reviewer'],
 reviewed_calculations_sha256=sha('power/SHARED_BATTERY_PATH_CALCULATIONS.json'),
 reviewed_thermal_csv_sha256=sha('thermal/SHARED_BATTERY_HEAT_LOADS.csv'),
 current_review='results/INPUT_PASSIVE_READONLY_REVIEW.json',current_review_sha256=sha('results/INPUT_PASSIVE_READONLY_REVIEW.json'),
 old_review='history/20260909_V12_before_input_passives/results/SHARED_BATTERY_READONLY_REVIEW.json',
 physical_tests_executed=False,whole_design_complete=False)
dump('results/SHARED_BATTERY_READONLY_REVIEW.json',compat)
review=dict(schema='WP10_SHARED_BATTERY_PATH_REVIEW_V2',native_schematic_unchanged=False,source_geometry_unchanged=True,
 current_source_plan='mechanical/ROOT_BUSHING_INSTANCE_PLAN.json',current_source_plan_sha256=sha('mechanical/ROOT_BUSHING_INSTANCE_PLAN.json'),
 model_sha256=sha('tools/shared_battery_path.py'),checks_sha256=sha('tools/check_shared_battery_path.py'),
 calculations_sha256=sha('power/SHARED_BATTERY_PATH_CALCULATIONS.json'),check_count=sb['check_count'],case_count=sb['case_count'],
 previously_ON_hold_counterexample_count=len(sb['counterexample_ids']),
 readonly_review='results/INPUT_PASSIVE_READONLY_REVIEW.json',package_release=False,power_on_release=False,goal_complete=False)
dump('results/SHARED_BATTERY_PATH_REVIEW.json',review)
sel=read('power/POWER_CHAIN_SELECTION.json')
sel['input_passives']='power/INPUT_PASSIVE_SELECTION.json'
sel['input_passive_calculations']='power/INPUT_PASSIVE_CALCULATIONS.json'
sel['shared_battery_path'].update(calculations='power/SHARED_BATTERY_PATH_CALCULATIONS.json',input_capacitor_leakage_scenario_A=.003)
sel['manager'].update(public_mount_hole_count=4,public_hole_centers_mm=None,integrated_battery_connector_angle_deg=90)
sel['known_blockers']=[s.replace('radiator, battery/PMM retention and full873 integration remain open','current936 full-heat qualification, battery/PMM retention and whole native integration remain open') for s in sel['known_blockers']]
dump('power/POWER_CHAIN_SELECTION.json',sel)
before=list(csv.DictReader((H/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig')))
rows=list(csv.DictReader((A/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig')))
assert len(rows)==37 and {q['id']:q['status'] for q in rows}=={q['id']:q['status'] for q in before}
for q in rows:
 if q['id'] in ['A05','B03','B05']:
  note=' | V13 F201/C203真实MPN和C203极性/封装进入原生201位号；192场景计入泄漏，F201热量在原分配内拆分。保护协调、纹波、全温和安装仍开放。'
  if note not in q['new_evidence']:q['new_evidence']+=note
 if q['id']=='B03':
  q['execution_state']='INPUT_PASSIVE_MPN_AND_NATIVE_POLARITY_BOUND__PROTECTION_ENVIRONMENT_AND_INSTALLATION_OPEN'
  q['next_source_edit']='主辅保险协调/热降额与故障L/R、C203纹波及寿命环境、PCB载板/端接实体、完整SOA与停止动态；电池接口不补猜。'
with (A/'SYSTEM_CLOSURE_MATRIX.csv').open('w',encoding='utf-8-sig',newline='') as ff:
 w=csv.DictWriter(ff,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
decision=read('results/DELIVERY_DECISION.json')
decision.update(schema='WP10_IMPLEMENTATION_DELIVERY_V13',revision='V13_INPUT_PASSIVE_SELECTION',
 status='INPUT_FUSE_AND_POLARIZED_CAPACITOR_NATIVE_DESIGN_UPDATED__WHOLE_MECHATRONIC_CLOSURE_OPEN',
 native_system_components=nv['native_components'],native_schematic_pages=11,
 connectivity_and_counterexample_checks=nv['count'],ERC_open=nv['ERC_count'],ERC_types=nv['ERC_types'],
 shared_battery_DC_checks=sb['check_count'],shared_battery_DC_cases=sb['case_count'],
 input_passive_checks=r['check_count'],input_passive_review='results/INPUT_PASSIVE_READONLY_REVIEW.json',
 F201_MPN='1025HC30-RTR',C203_MPN='ELXG101VSN222MR50S',C203_polarity_and_native_footprint_bound=True,
 C203_F201_physical_assembly_installed=False,protection_coordination_verified=False,
 engineering_prototype_design_complete=False,goal_complete=False)
decision['active_next_work_item']=dict(parent_id='B03',same_candidate='mechanical/ROOT_BUSHING_INSTANCE_PLAN.json',
 next_action='Complete input PCB/support placement using qualified envelope and vent/insulation space; bind F202, F201 thermal/fault L/R and C203 ripple/environment. Continue battery/PMM installation and full heat/STOP/propulsion ICD without inventing OEM data.',
 read_inputs=['power/INPUT_PASSIVE_DESIGN.md','power/INPUT_PASSIVE_CALCULATIONS.json','power/SHARED_BATTERY_PATH_CALCULATIONS.json'])
dump('results/DELIVERY_DECISION.json',decision)
doc=f'''# WP10 V13 输入保险与电容改件
F201、C203具体型号、C203正负极与封装已进入当前原生电气源。201位号、11页、原99位号父本保持；{nv['count']}项连接检查、{sb['check_count']}项共享电源检查、{r['check_count']}项器件筛查通过。7项电源引脚未驱动ERC仍开放。检查结果不等于整机完成。

|位号|当前候选|本轮实际绑定|
|---|---|---|
|F201|Eaton 1025HC30-RTR|30A、72VDC；主支路后备保险；BOM/原生图纸|
|C203|Chemi-Con ELXG101VSN222MR50S|2200µF±20%、100V；工程pad1正、pad2负；VS两孔封装|
|F202|6A慢断，MPN未定|保留辅助支路，尚未完成保护协调|

## 选择依据和限制
[Eaton官方10572（June2025）](https://www.eaton.com/content/dam/eaton/products/electronic-components/resources/data-sheet/eaton-1025hc-surface-mount-ceramic-tube-fuses-data-sheet.pdf)给出的500A直流分断只对应电池源、72VDC、L/R小于1µs的试验。现有BMS故障电流与线束电感未知，不能继承分断通过。示例1µH/0.1Ω已有10µs。典型1.7mΩ冷阻为20°C、低于0.1额定电流参考；112A²s为10倍额定电流下典型熔化值，不是总清除能量。温度降额图和实际PCB散热尚未数值绑定。30A额定值保持，未为规避限制提高电流。

原候选0456030.ER因其数据表明确排除航空航天用途而被拒；记录见[来源与淘汰项](../sources/INPUT_PASSIVE_DECISION_RECORD.json)。Eaton未见该条排除不构成航天合格证明。其PDF正文已通过官方网页读取，但本地文件下载超时、推荐焊盘尚未完成视觉核对，因此F201封装与安装坐标保持空值。

[Chemi-Con产品页](https://www.chemi-con.co.jp/en/products/detail-condenser.php?part_number=ELXG101VSN222MR50S)与[LXG系列目录](https://www.chemi-con.co.jp/products/relatedfiles/capacitor/catalog/LXGN-e.PDF)支持C203的参数。由初始20°C、120Hz的tanδ及最小容量计算，ESR上界为{r['electrical']['initial_ESR120Hz_upper_from_DF_ohm']:.6f}Ω；同温30kHz的阻抗上界0.03Ω只能给该频点的ESR界限。按寿命试验后的容量/损耗角允许变化，120Hz上界可至{r['electrical']['endurance_ESR120Hz_upper_from_DF_ohm']:.6f}Ω，不能把初始小于0.12Ω的结果延用到全寿命。

纹波额定2.4Arms对应105°C、120Hz；模型保存了频率系数，实际电流频谱仍为空。主支路约20A直流不能充当电容纹波RMS。Cincon应用说明的低于−20°C输入电容增配条件也未闭合。[电容使用注意事项](https://www.chemi-con.co.jp/products/relatedfiles/capacitor/catalog/al-precaution-e.pdf)要求航天用途预先协商；没有替用户联系厂商。

## 电路、预算与机械接口
实际源：[integrate_power_loop.py](../tools/integrate_power_loop.py)、[器件参数源](../tools/input_passive_definition.py)、[原生电路PDF](../ecad/wp10_system.pdf)。C203正极在Q201后的PRECHARGED，负极在INPUT_RETURN，与机械臂侧隔离返回分开。工程pin1/2是本项目编号，不冒充厂家针号。

电容3mA泄漏为20°C、5分钟测试条件下的目录值，本轮按工作电压场景移用，独立计入预充之后的负载；与主控3mA、启动0.25W分别记账。192场景重算后，SBP132锚点：电池电流{v['battery_A']:.9f}A、欠压检测{v['main_fused_V']:.9f}V、共享接点损耗{v['heat_W']['shared_contact_loop']:.9f}W、电容泄漏损耗{v['heat_W']['input_capacitor_leakage']:.9f}W。16组欠压保持反例仍在。冷态开关断开时不从电池端虚构电容泄漏供电，电容电压保持为空。COLD泄漏热记0仅指电池输入贡献；未知储能电容的实际放电热没有被算成0。

F201按典型冷阻移用的锚点损耗{f201:.9f}W，从原主支路前段损耗中拆出，不重复增加总电阻。[新热源账](../thermal/INPUT_PASSIVE_HEAT_LOADS.csv)共3648行，包含RUN/COLD。它取代同场景的聚合前段记账，不能与旧CSV相加；安装热节点仍未绑定。

C203容量上界2.64mF、29.4V储能上界{r['electrical']['energy_J_at29p4V_max_C']:.7f}J。预充积分与闭式解已对拍，但理想轨迹省略源阻抗、启动负载和实际时序，只作诊断；没有因此判保险寿命、MOSFET SOA或启动动态通过。LM5069限流低于30A，不能要求F201在正常限流值下承担快速断电。

C203最大外形Ø31×52mm；顶部泄压另留至少3mm，接脚向PCB下方最大4.5mm。VS端子为两Ø2mm圆孔、10mm孔距；本项目焊盘3.5mm是候选分配，未当制造保证。封装已通过KiCad原生解析：[SVG](../review/input_passive_footprint/CP_ChemiCon_VS_D30_P10_2mm_Candidate.svg)。正极矩形pad1在顶视图左侧、负极圆形pad2在右侧；实际装配须对照负极条纹。

厂家CAD下载返回维护页、step.parts精确检索无匹配，未取得OEM BRep。没有将该电容虚假计入现有936实例整机；保持、绝缘、顶部泄压区及与CHB输入端的短回路布置仍需实体设计。套管不能当绝缘保证。端封面下的铜箔避让尚未进入实际PCB，封装的二维外框不能代替该项检查。

## 复核和后续执行
[独立审阅](../results/INPUT_PASSIVE_READONLY_REVIEW.json)绑定本轮计算和源文件SHA。[V12历史](../history/20260909_V12_before_input_passives/power/SHARED_BATTERY_PATH_CALCULATIONS.json)保持原值；[当前V13共享模型](SHARED_BATTERY_PATH_CALCULATIONS.json)含C203泄漏。936机械源、局部136件STEP和既有38件SolidWorks热组件仍按各自旧验证范围使用。

接下来继续输入PCB/载板和器件保持、主辅保险与短路路径、C203全温纹波/寿命、完整SOA和STOP动态；电池/PMM受控接口、全热源和推进ICD仍开放。37行闭环表状态未升级。本轮没有制造、接电或实物试验。
'''
(A/'power/INPUT_PASSIVE_DESIGN.md').write_text(doc,encoding='utf-8')
(A/'power/SHARED_BATTERY_PATH_DESIGN.md').write_text(f'''# 共享电池路径：当前V13
当前模型已加入C203泄漏。192场景、36项检查、16组保持反例。SBP132欠压检测{v['main_fused_V']:.9f}V、电池{v['battery_A']:.9f}A、共享接点{v['heat_W']['shared_contact_loop']:.9f}W。
[完整V13说明](INPUT_PASSIVE_DESIGN.md) · [当前计算](SHARED_BATTERY_PATH_CALCULATIONS.json) · [输入器件热账](../thermal/INPUT_PASSIVE_HEAT_LOADS.csv) · [V12历史说明](../history/20260909_V12_before_input_passives/power/SHARED_BATTERY_PATH_DESIGN.md)。
旧V12的39.320039W为无C203泄漏的同条件历史值，不能作为当前V13值。全部为假设导通的代数分支，实际UVLO时域、温升与整机资格未验证。
''',encoding='utf-8')
readme=f'''# WP10 当前V13：主保险和输入电容已进入电路源
F201选1025HC30-RTR；C203选ELXG101VSN222MR50S，正负极、KiCad封装及泄漏预算已绑定。原生201位号/11页，435项连接检查、192场景36项电源检查、26项器件筛查通过。7项ERC、保护协调、全温纹波与实体安装仍开放，整机尚未完成。

[查看页](REVIEW.html) · [设计说明](power/INPUT_PASSIVE_DESIGN.md) · [原生图纸PDF](ecad/wp10_system.pdf) · [完整源与STEP包](WP10_IMPLEMENTATION_DELTA.zip) · [本轮独立复核](results/INPUT_PASSIVE_READONLY_REVIEW.json) · [37行闭环表](SYSTEM_CLOSURE_MATRIX.csv) · [机器判定](results/DELIVERY_DECISION.json)

936实例机械源表与136件局部STEP保持V11。38件SolidWorks热组件保持原范围；完整936件原生装配、热/承载/运动及实物验证未完成。C203/F201尚未计入整机CAD。

复算顺序：在内存保护器下执行tools/build_input_passive_revision.py、tools/export_input_passive_footprint.py；改动后重新审阅并绑定SHA，再执行tools/publish_input_passive_addendum.py和tools/seal_completed_package.py。结果随源或XML变化即需重绑审阅，不能复用旧哈希。
'''
(A/'README.md').write_text(readme,encoding='utf-8')
links=[('设计说明','power/INPUT_PASSIVE_DESIGN.md'),('11页电气图纸','ecad/wp10_system.pdf'),('计算与反例','power/INPUT_PASSIVE_CALCULATIONS.json'),('192场景电源计算','power/SHARED_BATTERY_PATH_CALCULATIONS.json'),('独立复核','results/INPUT_PASSIVE_READONLY_REVIEW.json'),('BOM','power/SELECTED_BOM.csv'),('37行闭环表','SYSTEM_CLOSURE_MATRIX.csv'),('完整下载包','WP10_IMPLEMENTATION_DELTA.zip')]
nav=''.join(f'<a href="{html.escape(u)}">{html.escape(t)}</a>' for t,u in links)
cad='http://127.0.0.1:3245/'+A.as_posix()+'?file=mechanical%2Froot_bushing_integration.step.py'
page=f'''<!doctype html><html lang="zh"><meta charset="utf-8"><title>WP10 V13 输入器件与机电候选</title>
<style>body{{font:16px/1.65 system-ui;background:#f1f4f8;color:#182332;max-width:1180px;margin:auto;padding:30px}}h1{{font-size:30px}}section{{background:white;margin:22px 0;padding:24px;border-radius:12px}}nav{{display:flex;gap:12px;flex-wrap:wrap}}a{{color:#185a98}}nav a{{padding:9px 15px;background:#edf4ff;border-radius:6px}}.flag{{border-left:5px solid #c78322;padding-left:14px}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:22px}}img{{max-width:100%;background:white}}small{{color:#576273}}table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #ddd;text-align:left;padding:10px}}</style>
<small>同一活动候选 · V13 输入器件改件 · 2026-09-09</small>
<h1>主保险、极性电容与实际电路已绑定</h1>
<p class="flag">本轮改件完成；整机机电设计仍开放。器件筛查、网表一致与独立复算通过，未执行制造、接电或实物试验。</p>
<nav>{nav}</nav>
<section><table><tr><th>改动</th><th>当前结果</th></tr><tr><td>F201主保险</td><td>1025HC30-RTR / 30A / 72VDC；故障L/R、温度降额和清除协调未闭合</td></tr><tr><td>C203输入电容</td><td>ELXG101VSN222MR50S / 2200µF / 100V；pad1正、pad2负；全温纹波/寿命与安装开放</td></tr><tr><td>原生电气</td><td>201位号 / 11页 / 435项连接检查；保留7项未驱动电源引脚ERC</td></tr><tr><td>电源与热账</td><td>192场景，36项电源检查、26项器件筛查；16组欠压保持反例继续保留</td></tr></table></section>
<section><h2>输入电容的实际封装</h2><div class="grid"><div><img src="review/input_passive_footprint/CP_ChemiCon_VS_D30_P10_2mm_Candidate.svg" alt="KiCad原生导出C203封装"></div><div><p>两Ø2mm圆孔，孔距10mm。顶视图左侧矩形pad1为正，右侧圆形pad2为负。</p><p>最大本体Ø31×52mm，顶部泄压再留3mm，接脚向下最大4.5mm。焊盘3.5mm为项目候选。</p><p>这份封装尚未路由到PCB或计入936实例装配；保持、绝缘和短输入回路需要实体落实。</p><p>初始120Hz ESR上界0.113036Ω；寿命试验后的参数边界可至0.376787Ω，不能继承全寿命通过。</p></div></div></section>
<section><h2>原生改件页</h2><div class="grid"><a href="review/input_passive_native_page_3.png"><img src="review/input_passive_native_page_3.png" alt="F201原生图纸"></a><a href="review/input_passive_native_page_4.png"><img src="review/input_passive_native_page_4.png" alt="C203极性原生图纸"></a></div></section>
<section><h2>机械候选维持原版本</h2><p>当前源表936实例、V11局部136件STEP未修改。既有38件原生SolidWorks热组件按旧验证范围保留；完整原生装配、承载/连续运动/全热验证尚未完成。</p><nav><a href="{html.escape(cad)}">查看现有局部装配</a><a href="mechanical/root_bushing_integration.step">局部STEP</a><a href="mechanical/ROOT_BUSHING_INSTANCE_PLAN.json">936实例源表</a><a href="mechanical/WP10_THERMAL_CORE_SOLIDWORKS.zip">既有SolidWorks热组件</a></nav></section>
<section><h2>下一项实际设计</h2><p>输入PCB与器件保持、保险和故障路径、C203纹波/寿命、SOA与停止动态。电池/PMM同修订安装接口、全热源和推进受控ICD继续逐项闭合。</p><p>内存清理回收闲置工具服务的可重载页，未结束应用；本轮原生构建均未触发内存保护。</p></section></html>'''
(A/'REVIEW.html').write_text(page,encoding='utf-8')
print(json.dumps(dict(revision='V13',source_counts=[201,936],native_tests=nv['count'],power_checks=sb['check_count'],passive_checks=r['check_count'],goal_complete=False)))

