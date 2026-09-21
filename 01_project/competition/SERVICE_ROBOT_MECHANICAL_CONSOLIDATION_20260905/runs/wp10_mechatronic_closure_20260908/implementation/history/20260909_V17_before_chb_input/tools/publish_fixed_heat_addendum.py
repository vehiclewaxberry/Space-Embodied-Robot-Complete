"""Update this candidate's review after actual thermal-bay source changes."""
from pathlib import Path
import json,csv,html,hashlib,urllib.parse
A=Path(__file__).resolve().parents[1]
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def dump(p,o):(A/p).write_text(json.dumps(o,ensure_ascii=False,indent=2),encoding='utf-8')
g=read('results/FIXED_HEAT_GEOMETRY.json');b=read('thermal/FIXED_RADIATOR_BUDGET.json');p=read('mechanical/FIXED_HEAT_INSTANCE_PLAN.json')
interfaces=read('results/FIXED_HEAT_INTERFACE_SUMMARY.json')
bridge=read('thermal/TWO_PANEL_BRIDGE_BUDGET.json')
assert g['checks_passed'] and b['checks_passed']
assert interfaces['all_changed_neighborhoods_clear']
assert bridge['checks_passed']
assert b['config_sha256']==hashlib.sha256((A/'thermal/FIXED_HEAT_PATH.json').read_bytes()).hexdigest()
v=read('results/DELIVERY_DECISION.json')
v.update(schema='WP10_IMPLEMENTATION_DELIVERY_V5',status='FIXED_HEAT_PATH_AND_DEPENDENT_LAYOUT_SOURCE_BUILT__THERMAL_REDESIGN_REQUIRED',
 fixed_heat_source_geometry_continuous=True,fixed_heat_geometry_checks=g['check_count'],fixed_heat_sizing_checks=b['check_count'],passive_two_panel_design_checks=bridge['check_count'],
 fixed_heat_3state_source_instance_count=p['candidate_component_count'],fixed_heat_exact_interface_pairs_by_state=interfaces['exact_pairs_by_state'],full_native_fixed_heat_assembly_generated=False,
 new_power_carrier_installed_in_873=False,external_radiator_installed=False,
 single_side_85pct_full_power_thermal_design_rejected=True,engineering_prototype_design_complete=False,goal_complete=False)
v['internal_work_remaining']=['Distribute CHB heat to sufficient fixed external area; single +Y radiator fails 85% case','Full native assembly, unchanged-pair coverage, continuous motion, tools and tolerances','Battery/PMM and high-current interface installation; new harness termination','Brake timing/energy/PCB, STOP dynamics, startup reset; fuse/capacitor/SOA/charge','Controlled propulsion ICD and task binding']
dump('results/DELIVERY_DECISION.json',v)
rows=list(csv.DictReader((A/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig')))
for r in rows:
    if r['id'] in ['F03','H03','E05']:
        r.update(execution_state='ACTUAL_SOURCE_INTEGRATION__THERMAL_REDESIGN_REQUIRED',
          new_evidence='Two monolithic fixed thermal walls, four OEM/TIM mounts, moved14 DUAL S(+6,-10,0), deck bores at (106,36)/(106,69), repaired R21 routes; 345 exact pairs per state clear | results/FIXED_HEAT_GEOMETRY.json; results/FIXED_HEAT_INTERFACE_SUMMARY.json; thermal/FIXED_RADIATOR_BUDGET.json',
          next_source_edit='Spread heat beyond one +Y face; complete source867 native assembly, battery/PMM, motion/tool/tolerance checks')
with (A/'SYSTEM_CLOSURE_MATRIX.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
assert len(rows)==37
shots=sorted((A/'review').glob('fixed_heat_bay_iso_*.png'))
shot=shots[-1].relative_to(A).as_posix() if shots else None
viewer='http://127.0.0.1:3245/'+urllib.parse.quote(A.as_posix(),safe='/:')+'?file=mechanical%2Ffixed_heat_bay.step.py'
table='\n'.join('|'+f"{r['efficiency_scenario']:.0%}"+'|'+r['environment']['id']+'|'+f"{r['case_C_with_zero_coating_R']:.2f}"+'|' for r in b['scenarios'])
report=f'''# WP10 当前候选：固定热路径及整舱依赖改件

已生成两块一体化固定散热壁、CHB及三只LPS300原厂实体/真实TIM安装、DUAL整组14件移位、上舱板两个新孔和两条R21连续相切线束。原873/99位号父本保持，当前仍为201位号、11页KiCad。

**整机机电详细设计未完成；本轮单侧排热方案被热计算否定，需要继续修改热分配结构。** 360W臂任务保持。没有原生867组件SolidWorks总装、实测热接触、制造/通电/飞行放行。

[统一查看](REVIEW.html) · [旋转查看本轮整舱改件]({viewer}) · [整舱改件STEP](mechanical/fixed_heat_bay.step) · [可编辑CAD源](mechanical/fixed_heat_bay.step.py) · [电气PDF](ecad/wp10_system.pdf) · [原生KiCad](ecad/wp10_system.kicad_sch)

两侧净辐射面积为−Y {g['outward_radiating_face_area_mm2_by_side']['-1']/1e6:.8f}m²、+Y {g['outward_radiating_face_area_mm2_by_side']['1']/1e6:.8f}m²。两壁均为单一实体；四组TIM两侧接触面已核验，CHB为3234.482749mm²，每电阻为2856mm²。两壁总质量估计{sum(g['wall_mass_estimate_kg_by_side'].values()):.6f}kg（2700kg/m³假设），未冒充整星质量收口。

原150×160三电阻局部板保留为历史组件研究；本轮装配采用三个72×60一体座。替换2壁，移除2盖及12个盖专属安装柱；保留剪力夹并新增背面避让/工具孔。三状态同源实例表由873推导为867：−14旧盖系统＋8器件/TIM；14夹具件移位、5个原ID形状替换不增计数。该表为原生总装构建输入，未标为已导出原生SLDASM。

DUAL整组沿S(+6,−10,0)mm移位，上舱板新增(106,36)/(106,69)Ø3.4孔，旧孔保留并停用。两条推进线束保持原端点，通过新DUAL槽y46/y59；R21圆弧相切，作为6mm静态线束空间预留，长度不是裁线长度，厂家端点尚未绑定。

工作、收拢、释放三个状态各核验345对改件邻域STEP实体接口，均零正体积穿透、零未知；没有将未变更零件之间的全部配对、连续运动、工具或公差标成已通过。DATA与trunk_clip_65的45.8457mm³真实穿透已改源修复。P60支撑杆报警来自STEP源坐标与SolidWorks归一化坐标混用，检查器修正后原孔正确，没有追加P60孔。通用装配自相交检查触发1400MiB作业内存保护，后续采用逐实体有效性与上述定点精确接口核验；完整通用自相交检查仍未完成。

热计算：361W主输出、独立STOP16.8W不重复计入；当前CHB损耗35.70–63.71W。AZ-93光学参数采用公开ε=.89、α=.17；涂层厚度/覆盖/EOL及轨道边界未验证。k=130W/(m·K)是低于公开167典型值的敏感性，不是材料保证下界。计算已加入3.5mm口袋外皮厚度，并用源区最高温度判断。网格减半热点差{b['mesh_delta_C']:.4f}°C；这只验证数值稳定性。

|效率场景|外部边界示例（均非真实任务界）|零涂层热阻下壳温°C|
|---|---|---:|
{table}

85%场景即便整面等温深空，壳温乐观下界已117.54°C；面内扩散计算进一步升高。不能用降低360W、删掉85%场景或把两侧面积直接相加消除此反例；需实际热连接后重算。当前计算仅含CHB，未计THN、MOSFET、电池PMM和真实制动任务热量，完整热能力未通过。

[热预算](thermal/FIXED_RADIATOR_BUDGET.json) · [几何读回](results/FIXED_HEAT_GEOMETRY.json) · [三状态实例表](mechanical/FIXED_HEAT_INSTANCE_PLAN.json) · [BOM增量](mechanical/FIXED_HEAT_BOM_DELTA.csv) · [源参数](thermal/FIXED_HEAT_PATH.json) · [37行责任表](SYSTEM_CLOSURE_MATRIX.csv) · [机器裁决](results/DELIVERY_DECISION.json)

[三状态接口证据](results/FIXED_HEAT_INTERFACE_SUMMARY.json) · [审阅与修复记录](results/FIXED_HEAT_REVIEW_DISPOSITION.json) · [快照审阅](results/FIXED_HEAT_VISUAL_REVIEW.json) · [内存处置](results/FIXED_HEAT_MEMORY_AUDIT.json) · [跨板热传输候选](thermal/FIXED_HEAT_TRANSFER_SELECTION.json)。两根ATS热管目前仅为下一步接口布局候选；没有生成安装热管实体，也没有用公开容量公式冒充微重力适用性或整桥热阻保证。

[两面被动热网络](thermal/TWO_PANEL_BRIDGE_BUDGET.json)已计算实际热流，40W只保留为早期容量场景。85%效率、桥总热阻0.25K/W分配、当前壁厚/孔洞和数值接触面下，两面暗深空壳温74.42°C；仅+Y太阳直射为91.07°C；+Y同时有0.5热帆板视因子升至109.45°C；两侧各有0.5热帆板视因子、仍仅+Y直射则124.82°C。这些是布局筛选场景，实际帆板视因子未绑定，也未计其他热源。必须先确定视场与净辐射面积，再冻结热管与集热座。声明的200mm跨距、两次90°中心R30弯曲、两端各50mm直段需334.25mm，300±2%热管最长306mm不足此路线；并不代表所有路线都不可行。低负荷90/91%效率的等温暗深空节点低于30°C，公开热管温区以外的性能保持未知。

本包是当前候选增量：STEP可导入SolidWorks，CAD源复建仍引用同工作区的WP06/V6父源与已安装CAD运行时，不是脱离项目即可独立复建的整星制造包。

输入侧启动17位号、全故障预算等已完成源修改仍保留：[启动设计](power/STARTUP_DESIGN.md)、[启动计算](power/STARTUP_CIRCUIT_CALCULATIONS.json)、[完整故障预算](power/STOP_FULL_FAULT_BUDGET.json)、[负载侧制动](power/LOAD_SIDE_BRAKE_CALCULATIONS.json)。物理启动/停止动态、真实回生能量、保护配合及PCB仍开放。

来源：[NASA热控章](https://www.nasa.gov/smallsat-institute/sst-soa/thermal-control/)、[AZ-93原厂](https://www.aztechnology.com/product/1/az-93)、[Hydro6061原厂表](https://www.hydro.com/globalassets/01-products--services/extruded-profiles/americas/ena-resources/alloy-data-sheets/hydro_2019_data_sheet_6061.pdf)。本地文件SHA见sources/FIXED_HEAT_PATH_SOURCE_MANIFEST.json；典型材料数据不替代到货检验。
'''
(A/'README.md').write_text(report,encoding='utf-8')
page=(A/'REVIEW.html').read_text(encoding='utf-8')
heading='固定散热壁、舱板与线束改件已生成；热分配仍需修改'
page=page.replace('输入侧启动电路与完整故障预算已集成',heading)
card='<section><h2>本轮实际整舱改件</h2><p>两固定外壁、四组器件/TIM接触、14件夹具移位、新孔及R21线束。三状态各345对改件邻域接口零穿透；整星运动、工具、公差与原生总装仍需核验。单侧85%效率热场景失败，完整设计保持开放。</p>'
if shot:card+='<img src="'+shot+'" alt="本轮固定热路径与舱板线束实体快照">'
card+='<nav><a href="'+html.escape(viewer,quote=True)+'">旋转查看整舱改件</a><a href="mechanical/fixed_heat_bay.step">下载STEP</a><a href="thermal/FIXED_RADIATOR_BUDGET.json">热预算与失败场景</a><a href="results/FIXED_HEAT_INTERFACE_SUMMARY.json">三状态接口检查</a><a href="mechanical/FIXED_HEAT_INSTANCE_PLAN.json">三状态源实例表</a><a href="mechanical/FIXED_HEAT_BOM_DELTA.csv">BOM增量</a></nav></section>'
page=page.replace('<section><h2>本轮启动与停止预算',card+'<section><h2>本轮启动与停止预算',1)
page=page.replace('局部机械装配','前版局部组件研究').replace('温感安装、紧固件、外热出口与873整星集成尚未完成。','当前安装位置以本轮固定散热壁为准；温感、紧固件及原生整星集成仍开放。')
(A/'REVIEW.html').write_text(page,encoding='utf-8')
print(json.dumps(dict(fixed_heat_checks=g['check_count'],thermal_checks=b['check_count'],source_instance_count=p['candidate_component_count'],full_design_complete=False)))
