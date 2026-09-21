"""Publish only after same-source geometry, thermal calculation and native cold read."""
from pathlib import Path
import json,hashlib,csv,html,urllib.parse,zipfile,runpy
A=Path(__file__).resolve().parents[1]
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,r):(A/p).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
p=read('mechanical/FIXED_HEAT_INSTANCE_PLAN.json');ph=sha(A/'mechanical/FIXED_HEAT_INSTANCE_PLAN.json')
g=read('results/COLD_PATH_GEOMETRY.json');bottom=read('results/BOTTOM_MOUNT_GEOMETRY.json');t=read('results/COLD_PATH_TOOL_ACCESS.json');net=read('thermal/SPATIAL_RADIATOR_NETWORK_SCREEN.json');view=read('thermal/RADIATOR_MESH_VIEW_SCREEN.json')
n=read('results/NATIVE_COLD_COLD.json');np=read('mechanical/NATIVE_COLD_INPUTS.json');review=read('results/COLD_PATH_REVIEW_DISPOSITION.json')
assert all(x['checks_passed'] for x in [g,bottom,t,net,view])
assert review['snapshots_actually_reviewed'] and review['all_current_source_checks_recorded']
assert review['source_plan_sha256']==ph
assert all(sha(A/path)==digest for path,digest in review['inputs'].items())
assert all(sha(A/path)==review['snapshot_sha256'][key] for key,path in review['snapshots'].items())
assert net['source_sha256']==sha(A/'tools/spatial_radiator_network.py')
assert view['source_sha256']==sha(A/'tools/radiator_mesh_view_screen.py')
assert g['source_plan_sha256']==t['source_plan_sha256']==n['source_plan_sha256']==np['source_plan_sha256']==ph
assert n['status']=='PASS_COLD_NATIVE_38_INSTANCES_38_SOLIDS_TRANSFORMS_LOCAL_DEPENDENCIES' and n['input_sha256']==sha(A/'mechanical/NATIVE_COLD_INPUTS.json')
assert n['native_sha256']==sha(np['assembly_path'])
assert all(sha(A/path)==digest for rec in [net,view] for path,digest in rec['inputs'].items())
assert g['config_sha256']==bottom['source_config_sha256']==sha(A/'thermal/BOTTOM_RADIATOR_MOUNT.json')
allpaths={r['step_path']:r['source_sha256'] for s in p['states'].values() for r in s['rows']};assert all(sha(path)==digest for path,digest in allpaths.items())
native={q['path']:q['sha256'] for q in n['components']};assert len(native)==14 and all(sha(path)==digest for path,digest in native.items())
assert n['independent_cold_process_verified']
assert not n['source_volume_comparison_all_passed'] and [q['id'] for q in n['source_volume_comparison_open']]==['C09']
accuracy=read('results/NATIVE_CHB_ACCURACY_SCREEN.json')
assert accuracy['status']=='MAXIMUM_ACCURACY_COMPARISON_OPEN'
assert accuracy['source_script_sha256']==sha(A/'tools/check_native_chb_accuracy.py')
assert all(sha(A/path)==digest for path,digest in accuracy['input_sha256'].items())
assert accuracy['native_sha256']==accuracy['native_sha256_after']==sha(accuracy['native_path'])
assert accuracy['relative_threshold']==1e-6 and not accuracy['threshold_changed']
assert [r['accuracy_level'] for r in accuracy['rows']]==[0,1,2]
assert all(not r['within_original_threshold'] for r in accuracy['rows'])
qualification=read('results/NATIVE_CHB_ACCURACY_QUALIFICATION.json')
assert qualification['status']=='SOURCE_BOUND_RECOMPARISON_OPEN' and qualification['input_binding_checks_passed']
assert qualification['source_script_sha256']==sha(A/'tools/qualify_native_chb_accuracy.py')
assert all(sha(A/path)==digest for path,digest in qualification['input_sha256'].items())
battery=read('power/BATTERY_INSTALLATION_INTERFACE.json');packaging=read('results/RRC_BATTERY_PACKAGING_SCREEN.json')
assert battery['source_plan_sha256']==packaging['source_plan_sha256']==ph
assert battery['source_script_sha256']==sha(A/'tools/record_battery_installation_intake.py')
assert packaging['source_script_sha256']==sha(A/'tools/scan_rrc_packaging.py')
assert all(sha(A/path)==digest for rec in [battery,packaging] for path,digest in rec['input_sha256'].items())
assert {Path(q['native_path']).resolve() for q in np['parts']}=={Path(path).resolve() for path in native}
runpy.run_path(str(A/'tools/sync_cold_bom.py'),run_name='__main__')
interfaces={};inputs={}
for state in p['states']:
    path=f'results/FIXED_HEAT_{state.upper()}_INTERFACES.json';r=read(path)
    assert r['source_plan_sha256']==ph and r['zero_positive_volume_intersections'] and r['complete_coverage']
    interfaces[state]=len(r['exact_pairs']);inputs[path]=sha(A/path)
dump('results/FIXED_HEAT_INTERFACE_SUMMARY.json',dict(schema='WP10_FIXED_HEAT_INTERFACE_SUMMARY_V4_COLD_PATH',source_plan_sha256=ph,inputs=inputs,exact_pairs_by_state=interfaces,all_changed_neighborhoods_clear=True,whole_assembly_checked=False,continuous_motion_evaluated=False))
normal=net['link_nominal_1D_R_K_W'];scenarios=[r for r in net['rows'] if r['per_link_R_K_W']==normal]
fold=next(r for r in scenarios if r['state']=='released' and r['sun_on_plus_Y'] and r['occluder_K']==330)
hot=next(r for r in scenarios if r['state']=='released' and r['sun_on_plus_Y'] and r['occluder_K']==350)
v=read('results/DELIVERY_DECISION.json');v.update(schema='WP10_IMPLEMENTATION_DELIVERY_V7',status='ACTUAL_CHB_BOTTOM_DUAL_WALL_PATH_AND_NATIVE38_BUILT__THERMAL_MARGIN_AND_WHOLE_MECHATRONIC_CLOSURE_OPEN',
 candidate_source_components=p['candidate_component_count'],fixed_heat_3state_source_instance_count=p['candidate_component_count'],fixed_heat_exact_interface_pairs_by_state=interfaces,
 fixed_heat_geometry_checks=read('results/FIXED_HEAT_GEOMETRY.json')['check_count'],cold_path_geometry_checks=g['check_count'],bottom_mount_geometry_checks=bottom['check_count'],
 thermal_core_native_components=38,thermal_core_native_solids=38,thermal_core_native_unique_parts=14,thermal_core_native_cold_verified=True,
 native_core_source_volume_comparison_all_passed=False,native_core_volume_comparison_open_ids=['C09'],native_geometry_clearance_verified=False,
 native_C09_explicit_high_accuracy_probe='MAXIMUM_ACCURACY_COMPARISON_OPEN',native_C09_accuracy_probe_sha256=sha(A/'results/NATIVE_CHB_ACCURACY_SCREEN.json'),
 bottom_mount_native_cold_verified=False,bottom_mount_native_scope='Previous V6 native24 only; superseded by current native38 thermal core',
 bottom_radiator_source_installed=True,bottom_radiator_CHB_heat_connection_installed=True,external_radiator_installed=True,
 same_revision_view_screen_bound=True,local_view_network_calculated=True,CHB_only_nominal_folded330K_case_C=fold['case_C'],CHB_only_hot350K_case_C=hot['case_C'],
 continuous_full_vehicle_thermal_verified=False,full_native_fixed_heat_assembly_generated=False,engineering_prototype_design_complete=False,goal_complete=False)
v.update(battery_packaging_screen_executed=True,battery_current_instance_integrated=False,
 battery_packaging_screen_status=packaging['status'],battery_retention_geometry_bound=False)
v['active_next_work_item']=dict(parent_id='A05',same_candidate='mechanical/FIXED_HEAT_INSTANCE_PLAN.json',
 next_action='Identify a bounded set of equipment relocations for the D-max RRC body; use exact STEP checks for nonconvex thermal parts before committing battery carrier/deck changes. Retain old battery function,360W arm task and all required devices.',
 read_inputs=['power/BATTERY_INSTALLATION_INTERFACE.json','results/RRC_BATTERY_PACKAGING_SCREEN.json'],
 resources_recovered=True,whole_goal_complete=False)
v['internal_work_remaining']=['Close thermal margin with all actual module losses, orbit/attitude and mounted contact/3D conduction; current CHB-only geometry is not full thermal qualification','Battery/PMM real retention, protected high-current and charging interfaces, PCB/harness physical endpoints','Brake energy and dynamics, STOP/startup dynamics, fuse/capacitor/SOA protection coordination','Whole894 native assembly, unchanged-pair/motion/tolerance/structural and full tool insertion verification','Controlled same-revision propulsion ICD and task/hardware binding']
dump('results/DELIVERY_DECISION.json',v)
rows=list(csv.DictReader((A/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig')));assert len(rows)==37
for r in rows:
    if r['id']=='A05':
        r.update(execution_state='CHB_CORE_NATIVE38__RRC_BATTERY_RELAYOUT_OPEN',new_evidence='CHB core38 saved/cold-read. RRC3570-4 D maximum189.5x85.5x82.2mm and MC35 B PCB layout sourced; conservative six-orientation2mm-gap packaging search found no clear box. Nonconvex AABB screening is not a proof of geometric infeasibility; old battery allocation retained. Battery socket datum and retaining interface remain unbound.',next_source_edit='Bound a local relocation set and run actual STEP narrow-phase packaging with battery connector/support access before creating carrier/deck source changes.')
    if r['id'] in ['F03','H03','E05']:
        r.update(execution_state='ACTUAL_CHB_BOTTOM_AND_DUAL_WALL_PATH_NATIVE38__THERMAL_MARGIN_OPEN',new_evidence=f"894 source instances; each state642 changed-neighborhood exact pairs clear; real CHB/TIM/monolithic bottom/L-fingers/two wall TIM joints; native38 instances14 parts cold read. {g['check_count']} cold geometry checks; 48 bottom checks; tools36 base +24 new with8 expected folded blockages. Actual local-view thermal network, hot and added-heat counterexamples retained.",next_source_edit='All-module heat and mounting-contact/3D thermal margin; battery/PMM/protected power interfaces; whole894 native, functional and propulsion closure')
with (A/'SYSTEM_CLOSURE_MATRIX.csv').open('w',newline='',encoding='utf-8-sig') as f:
    for r in rows:
        if r['id'] in ['F03','H03','E05']:
            r['new_evidence']+=' C09 native cross-kernel volume comparison OPEN; STEP clearance is not nativeC09 clearance credit.'
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
with zipfile.ZipFile(A/'mechanical/WP10_THERMAL_CORE_SOLIDWORKS.zip','w',zipfile.ZIP_DEFLATED) as z:
    for path in [Path(np['assembly_path']),*[Path(q['native_path']) for q in np['parts']]]:z.write(path,path.name)
    z.write(A/'results/NATIVE_COLD_COLD.json','NATIVE_COLD_COLD.json')
    z.write(A/'results/NATIVE_CHB_ACCURACY_SCREEN.json','NATIVE_CHB_ACCURACY_SCREEN.json')
    z.write(A/'results/NATIVE_CHB_ACCURACY_QUALIFICATION.json','NATIVE_CHB_ACCURACY_QUALIFICATION.json')
    z.writestr('README_ZH.txt','当前V7 CHB底部与双侧壁导热核心：38实例/38实体，14个SLDPRT与WP10_THERMAL_CORE.SLDASM。C09 CHB跨内核体积比较仍OPEN：SW与GK相对差1.16178e-6超过未改变的1e-6判据；文件冷读/定位/依赖通过不代表源形状等价。原STEP接触与干涉结论没有授予原生C09。全部解压到同一目录打开。原目录独立进程冷读已验证，移动目录后的冷读未执行。固定源基准，没有运动配合/公差/预紧/制造或通电放行。不能替代894实例整星总装。')
    assert z.testzip() is None
base='http://127.0.0.1:3245/'+urllib.parse.quote(A.as_posix(),safe='/:')
live=base+'?file=mechanical%2Fthermal_core.step.py';bay=base+'?file=mechanical%2Ffixed_heat_bay.step.py'
dump('results/VIEWER_LINKS.json',dict(current_thermal_core=live,current_thermal_bay=bay,native_thermal_core=np['assembly_path'],source_instance_plan='mechanical/FIXED_HEAT_INSTANCE_PLAN.json',full_native894_available=False))
shot=review['snapshots']['thermal_core_iso'];bay_shot=review['snapshots']['fixed_heat_bay_iso']
table='\n'.join(f"|{r['state']}|{r['occluder_K']:.0f}|{'有' if r['sun_on_plus_Y'] else '无'}|{r['case_C']:.2f}|" for r in scenarios)
extras='；'.join(f"增加{r['extra_unassigned_heat_W']:.0f}W未分配热源时{r['case_C']:.2f}°C" for r in net['unassigned_extra_heat_sensitivity'])
pressure='；'.join(f"{r['psi']}psi → {r['case_C']:.2f}°C" for r in net['pressure_sensitivity'])
refined=net['mesh_refinement'][-1]
text=f'''# WP10 当前候选：CHB 底部与双侧壁实际导热核心

已将厂家CHB实体改装到底部短台座，生成两根与底板一体的L形导热臂、侧壁接耳、两片TIM及8枚新增螺钉。**当前38实例/38实体的SolidWorks导热核心已保存并独立冷读；C09 CHB跨内核体积比较仍OPEN，整机机电详细设计未完成。** 894实例是同一候选的三个状态源表，尚非完整原生整星装配。

[统一查看](REVIEW.html) · [旋转查看导热核心]({live}) · [当前整舱改件]({bay}) · [SolidWorks组件包](mechanical/WP10_THERMAL_CORE_SOLIDWORKS.zip) · [导热核心STEP](mechanical/thermal_core.step) · [全部当前增量包](WP10_IMPLEMENTATION_DELTA.zip)

CHB基面S(-25,0,-96.15)mm，针脚朝+Z；58×62mm台座面z=-96.353，TSP1800ST名义厚0.203mm（未验证压缩厚度）。底板、两根58mm宽的L臂为单一实体；两侧58×24mm接耳与冷指间由0.203mm项目裁切TIM填实。每侧净TIM接触面积{g['wall_joints'][0]['contact_area_mm2']:.6f}mm²，CHB双侧TIM接触面积{g['CHB_TIM_contact_mm2']:.6f}mm²。甲板实际开60×96窗口，原六组底板夹紧点保留。详见[设计参数](thermal/BOTTOM_RADIATOR_MOUNT.json)及[设计说明](mechanical/CHB_BOTTOM_COLD_PATH_BRIEF.md)。

三处TIM同时选为TSP1800ST：25psi典型面积热阻0.28K·in²/W，已含两个接触界面；不额外叠加TIM的t/kA。它仍是绝缘材料，但典型击穿由原TSP1600S的5500Vac降到3000Vac，且贯穿的金属螺钉形成电气旁路，组件绝缘未经证明。目标25psi对应CHB总平均承压力557.524N、每侧234.455N，实际压强分布、压缩厚度和预紧未验证。厂家放气TML0.23%/CVCM0.05%是材料筛选数据。[厂家资料与选择](sources/COLD_TIM_SELECTION.json)。

新增螺钉复用Würth4123 53 20公开尺寸，CAD为简化螺纹名义重建体。CHB名义伸入2mm，侧壁冷指3.147mm/孔深5mm；有效啮合、压紧、预紧、防松及公差仍未验收。厂家STEP孔距48.26与图纸48.3mm差异保留。CAD旧ID U202_CHB现明确绑定实际电气位号U203，无重复位号。

底部净平面辐射面积{bottom['actual_outward_planar_radiating_area_mm2']/1e6:.8f}m²，底板及一体臂按2700kg/m³估算质量{bottom['plate_mass_estimate_kg']:.6f}kg；未将其冒充整星质量闭环。旧底部V6及其24实例原生文件保留历史，当前以38实例导热核心为准。

本次证据：{g['check_count']}项冷路径接触/定位/螺钉检查、48项底部几何检查；三个状态各642对改件邻域精确STEP检查无正体积穿透与未知。原六夹紧点36个局部工具域通过；新增24个工具域中16个可用，8个折叠侧壁域被帆板遮挡，已明确展开预装顺序。以上不覆盖完整插入轨迹、连续动作、公差及未改件之间的全配对。

原生SolidWorks2024导热核心含14个SLDPRT及38个固定实例；各零件保存、关闭、重开，装配另启会话冷读38实体/0曲面、显式坐标变换与14个本地依赖。源STEP、原生SHA与三态源表绑定。目录迁移后的冷读、运动配合及894整星原生集成未执行。见[原生回执](results/NATIVE_COLD_COLD.json)。

C09 CHB的SW体积44063.953594mm³，与GK参考44064.004787mm³相差1.16178×10⁻⁶，超过未改变的1×10⁻⁶相对判据；原始失败和积分方法差异均保留，13件其它零件维持原体积检查。文件读回、实体数和定位通过不能替代源形状等价；STEP接触与干涉结论未自动授予SW C09。该体积不用于整星质量预算。[积分诊断](results/COLD_SOURCE_MATCH_DIAGNOSTIC.json) · [STEP序列化筛查及精度边界](results/THERMAL_CORE_SOURCE_MATCH.json)。

补充只读复算显式使用SolidWorks IMassProperty2，设置SI单位并分别在低、中、高精度重算；三档均返回44063.953594mm³，最高精度比较仍未通过。原生文件SHA未改变，不能将异常归因于“只需提高精度”；也不能单凭体积差异认定几何损坏。[三档精度实际回执](results/NATIVE_CHB_ACCURACY_SCREEN.json) · [当前源绑定复核及限定](results/NATIVE_CHB_ACCURACY_QUALIFICATION.json)。

热模型改为实际三面非等温网络：保持361W CHB输出（360W臂＋1W制动偏置），85%效率敏感性损耗{net['source_load_W']:.6f}W；底板热源与两个立柱足分别连接，未绕过底板扩散。当前894实例STEP局部遮挡场已重建，新增沉孔进入实际平面面积掩膜。每侧1D中心线热阻估算{normal:.6f}K/W，其中TIM典型值{net['link_nominal_1D_terms_K_W']['TIM_typical25psi']:.6f}K/W；这不是实测或保证上界。被遮方向与指定温度部件换热，链接允许热流反向。

|状态|遮挡物温度K|+Y入射1361W/m²|CHB壳温°C|
|---|---:|---|---:|
{table}

表格为5mm网格条件算例。折叠330K/+Y光照工况加密到{refined['pitch_requested_mm']}mm得到{refined['case_C']:.2f}°C，原TSP1600S同口径为105.14°C。三片垫同时取相同参考压强的敏感性为：{pressure}；这些数据不证明已经建立了所需压强。[当前TIM接口合同](thermal/COLD_TIM_INTERFACE_CONTRACT.json) · [38实例物料映射](mechanical/COLD_PATH_INSTANCE_BOM.csv)。

上述环境均为注明条件的敏感性，未绑定真实轨道/姿态。折叠330K/+Y光照条件下，{extras}；这说明仍需给其它设备与接触误差留出真实热余量。网格加密和能量守恒检查仅验证数值实现，未升级为整星热通过。原单侧失败、底板单面失败与更热遮挡物反例均保留。[当前热网络](thermal/SPATIAL_RADIATOR_NETWORK_SCREEN.json) · [当前表面视场](thermal/RADIATOR_MESH_VIEW_SCREEN.json)。

电气维持201位号/11页KiCad以及各自已绑定的435原生网表、104制动、50启动静态、8全故障网清点回执；7个power_pin_not_driven ERC仍披露。本轮未代替电池/PMM受保护端、PCB及实际线束端接、制动能量与停止/启动动态、保险/电容/SOA、充电、推进同修订ICD和任务能力验证。37行责任表的完成等级保持原口径。[电气PDF](ecad/wp10_system.pdf) · [KiCad源](ecad/wp10_system.kicad_sch) · [BOM](power/SELECTED_BOM.csv) · [From–To](ecad/MASTER_FROM_TO.csv) · [闭环表](SYSTEM_CLOSURE_MATRIX.csv) · [机器裁决](results/DELIVERY_DECISION.json)。

电池安装已进一步核对：RRC3570-4 D版最大外形189.5×85.5×82.2mm，当前90×170×65mm旧电池占位保持原功能，未拿它冒充新高功率电池。保留现有设备，在当前service态CAD表示中，六种轴向姿态在声明舱域及2mm设计间隙下没有找到清晰的包围盒位置；忽略三件非凸热结构外包围盒的待精查分支也未找到位置。这不是实际STEP几何、全姿态或实物不可能的证明，下一步必须先确定设备局部迁移和窄相位检查，再生成托架。厂家MC35文件名A但页脚B，两个功率脚实际中心距29mm；电池插座相对外壳的定位、保持区、配合行程和允许夹紧仍没有受控依据。[电池接口输入](power/BATTERY_INSTALLATION_INTERFACE.json) · [同894候选包装初筛](results/RRC_BATTERY_PACKAGING_SCREEN.json)。

本轮出现一次启动前内存不足，任务未启动；对已识别闲置Codex工具服务回收可重新载入的工作集后，可用内存恢复并完成后续串行工作。没有结束应用/会话。启动≥2GiB、运行≥512MiB、任务与自有SW合计≤1400MiB的约束保持。[内存回收记录](results/COLD_PATH_MEMORY_RECOVERY.json) · [本轮运行记录](results/COLD_PATH_MEMORY_AUDIT.json) · [审阅处置](results/COLD_PATH_REVIEW_DISPOSITION.json)。

![当前导热核心]({shot})
'''
(A/'README.md').write_text(text,encoding='utf-8')
def links(items):return '<nav>'+''.join('<a href="'+html.escape(u,quote=True)+'">'+html.escape(label)+'</a>' for label,u in items)+'</nav>'
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>WP10 · CHB底部双侧壁导热核心</title><style>body{font:16px/1.7 system-ui,"Microsoft YaHei",sans-serif;background:#f2f5f8;color:#213447;margin:0}main{max-width:1100px;margin:30px auto;padding:20px}section{background:white;border:1px solid #dce3ec;border-radius:10px;padding:24px;margin:18px 0}.flag{background:#fff3db;padding:16px;border-left:5px solid #b77d1a}h1{font-size:30px}a{color:#075d97}nav a{display:inline-block;background:#e9f2f8;padding:8px 12px;margin:6px}img{max-width:100%}</style><main><p>WP10 · 同一活动候选 · V7</p><h1>CHB底部与双侧壁导热核心已生成</h1><p class="flag">38实例/38实体原生SolidWorks已冷读；894为三态候选源表。整机机电与热余量仍开放，没有制造、通电或飞行放行。</p>'''
page+='<section><h2>查看本轮实际装配</h2><img src="'+shot+'" alt="当前38实例导热核心">'+links([('旋转导热核心',live),('下载SolidWorks组件包','mechanical/WP10_THERMAL_CORE_SOLIDWORKS.zip'),('STEP','mechanical/thermal_core.step'),('完整设计说明','README.md'),('原生冷读','results/NATIVE_COLD_COLD.json')])+'</section>'
page+='<section><h2>顶部导热路径</h2><p>中央为CHB模块，两侧一体导热臂伸向壁座。薄TIM接触和隐藏区域以STEP接触检查为证据。</p><img src="'+review['snapshots']['thermal_core_top']+'" alt="当前导热核心顶视图">'+links([('TIM接口合同','thermal/COLD_TIM_INTERFACE_CONTRACT.json'),('38实例物料映射','mechanical/COLD_PATH_INSTANCE_BOM.csv')])+'</section>'
page+='<section><h2>当前整舱改件</h2><img src="'+bay_shot+'" alt="当前整舱改件">'+links([('旋转整舱改件',bay),('几何检查','results/COLD_PATH_GEOMETRY.json'),('三态接口','results/FIXED_HEAT_INTERFACE_SUMMARY.json'),('工具与展开预装','results/COLD_PATH_TOOL_ACCESS.json')])+'</section>'
page+='<section><h2>热计算及未闭环项</h2><p>真实底板与双冷指已安装。模型纳入局部遮挡、反向热流和各接口热阻；其它模块、接触/涂层误差及真实轨道热环境仍需收束。数值检查通过不代表整星热通过。</p>'+links([('当前热网络','thermal/SPATIAL_RADIATOR_NETWORK_SCREEN.json'),('当前STEP视场','thermal/RADIATOR_MESH_VIEW_SCREEN.json'),('37行责任表','SYSTEM_CLOSURE_MATRIX.csv'),('机器裁决','results/DELIVERY_DECISION.json'),('内存回收','results/COLD_PATH_MEMORY_RECOVERY.json')])+'</section>'
page+='<section><h2>同一候选电气与全部源包</h2>'+links([('电气PDF','ecad/wp10_system.pdf'),('KiCad','ecad/wp10_system.kicad_sch'),('电气BOM','power/SELECTED_BOM.csv'),('线束From–To','ecad/MASTER_FROM_TO.csv'),('全部当前增量包','WP10_IMPLEMENTATION_DELTA.zip')])+'</section></main></html>'
page=page.replace('38实例/38实体原生SolidWorks已冷读；894为三态候选源表。','38实例/38实体原生SolidWorks已冷读；C09 CHB跨内核体积比较仍OPEN（1.16178e-6超过原1e-6判据），源STEP干涉结论未授予原生C09。894为三态候选源表。')
page=page.replace('</main>', '<section><h2>CHB 原生体积补充核查</h2><p>显式低、中、高精度计算返回相同体积，最高精度比较仍未通过；原文件没有改动。</p>'+links([('三档精度实际回执','results/NATIVE_CHB_ACCURACY_SCREEN.json')])+'</section></main>')
page=page.replace('</main>', '<section><h2>电池安装的下一处实际约束</h2><p>RRC3570-4 D最大外形189.5×85.5×82.2mm，当前舱内初筛需要局部重新布置；尚未生成或安装电池托架。旧电池功能保留，厂家插座定位和保持区尺寸仍未绑定。</p>'+links([('厂家机械输入与精确缺项','power/BATTERY_INSTALLATION_INTERFACE.json'),('当前候选包装初筛','results/RRC_BATTERY_PACKAGING_SCREEN.json')])+'</section></main>')
(A/'REVIEW.html').write_text(page,encoding='utf-8');print(json.dumps(dict(revision='V7',source_instances=894,native_core_instances=38,full_design_complete=False)))
