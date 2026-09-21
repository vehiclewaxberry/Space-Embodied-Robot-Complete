"""Current candidate publication after bottom source, native and view evidence."""
from pathlib import Path
import json,hashlib,csv,html,urllib.parse,zipfile
A=Path(__file__).resolve().parents[1]
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,r):(A/p).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
p=read('mechanical/FIXED_HEAT_INSTANCE_PLAN.json');ph=sha(A/'mechanical/FIXED_HEAT_INSTANCE_PLAN.json');g=read('results/BOTTOM_MOUNT_GEOMETRY.json');c=read('results/FIXED_HEAT_INTERFACE_SUMMARY.json');t=read('results/BOTTOM_LOCAL_TOOL_CLEARANCE.json');view=read('thermal/RADIATOR_MESH_VIEW_SCREEN.json')
assert g['checks_passed'] and c['all_changed_neighborhoods_clear'] and t['checks_passed'] and view['checks_passed']
assert c['source_plan_sha256']==t['source_plan_sha256']==ph==view['inputs']['mechanical/FIXED_HEAT_INSTANCE_PLAN.json']
assert g['source_config_sha256']==sha(A/'thermal/BOTTOM_RADIATOR_MOUNT.json')
n=read('results/NATIVE_BOTTOM_COLD.json');assert n['status']=='PASS_COLD_NATIVE_24_INSTANCES_24_SOLIDS_TRANSFORMS_LOCAL_DEPENDENCIES' and n['source_plan_sha256']==ph
np=read('mechanical/NATIVE_BOTTOM_INPUTS.json');assert n['input_sha256']==sha(A/'mechanical/NATIVE_BOTTOM_INPUTS.json') and n['native_sha256']==sha(np['assembly_path'])
source_paths={q['step_path']:q['source_sha256'] for st in p['states'].values() for q in st['rows']}
assert all(sha(path)==digest for path,digest in source_paths.items())
assert all(sha(A/q['path'])==q['sha256'] for q in g['source_steps'].values())
native_digests={q['path']:q['sha256'] for q in n['components']}
assert len(native_digests)==9 and all(sha(path)==digest for path,digest in native_digests.items())
assert {Path(q['native_path']).resolve() for q in np['parts']}=={Path(path).resolve() for path in native_digests}
assert all(sha(A/path)==digest for path,digest in c['inputs'].items())
assert all(sha(A/path)==digest for path,digest in view['inputs'].items())
v=read('results/DELIVERY_DECISION.json');v.update(schema='WP10_IMPLEMENTATION_DELIVERY_V6',status='BOTTOM_RADIATOR_AND_NATIVE24_MOUNT_BUILT__WHOLE_MECHATRONIC_CLOSURE_OPEN',
 candidate_source_components=p['candidate_component_count'],fixed_heat_3state_source_instance_count=p['candidate_component_count'],fixed_heat_exact_interface_pairs_by_state=c['exact_pairs_by_state'],bottom_mount_geometry_checks=g['check_count'],local_tool_checks=t['count'],bottom_mount_native_components=24,bottom_mount_native_solids=24,
 bottom_mount_native_unique_parts=9,bottom_mount_native_cold_verified=True,bottom_radiator_source_installed=True,bottom_radiator_CHB_heat_connection_installed=False,
 same_revision_view_screen_bound=True,full_native_fixed_heat_assembly_generated=False,engineering_prototype_design_complete=False,goal_complete=False)
v['internal_work_remaining']=['Install and verify actual CHB heat-transfer path to bottom radiator; bind local view fields and all other heat sources','Controlled battery/PMM thermal and electrical interfaces; high-current hardware and harness termination','Brake energy/dynamics, STOP/startup dynamics, PCB, fuse/capacitor/SOA and charge protection','Whole884 native assembly, unchanged-pair coverage, motion, full tool insertion, tolerance, structural and thermal verification','Controlled propulsion ICD, actual task and hardware evidence']
dump('results/DELIVERY_DECISION.json',v)
rows=list(csv.DictReader((A/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig')))
for r in rows:
    if r['id'] in ['F03','H03','E05']:
        r.update(execution_state='ACTUAL_BOTTOM_AND_NATIVE24_INTEGRATION__FULL_THERMAL_PATH_OPEN',
          new_evidence='884-source-state plan; three states531 exact pairs each clear; bottom48geometry/36localtool checks; native24instance24solid9part cold read; actual STEP surface view. results/BOTTOM_MOUNT_GEOMETRY.json; results/NATIVE_BOTTOM_COLD.json; thermal/RADIATOR_MESH_VIEW_SCREEN.json',
          next_source_edit='Actual CHB-to-bottom heat transfer and coupled local-view thermal budget; battery/PMM, whole884 native and electropropulsion closure')
assert len(rows)==37
with (A/'SYSTEM_CLOSURE_MATRIX.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
native_files=[Path(np['assembly_path']),*[Path(q['native_path']) for q in np['parts']]]
with zipfile.ZipFile(A/'mechanical/WP10_BOTTOM_SOLIDWORKS.zip','w',zipfile.ZIP_DEFLATED) as z:
    for path in native_files:z.write(path,path.name)
    z.write(A/'results/NATIVE_BOTTOM_COLD.json','NATIVE_BOTTOM_COLD.json')
    z.writestr('README_ZH.txt','底部安装候选：24实例、9个SLDPRT、1个SLDASM。解压全部文件到同一目录后打开SLDASM。原目录冷读已验证；移动到其他目录后的冷读尚未验证。固定源基准位置，无运动配合、材料/公差/防松/制造放行。整机884组件尚未原生集成。')
    assert z.testzip() is None
values={}
for r in view['results']:
    if r['face']['id'] in ['FIXED_MINUS_Y','FIXED_PLUS_Y','FIXED_MINUS_Z_BOTTOM_PLATE']:
        values.setdefault(r['state'],{})[r['face']['id']]=r['model_surface_refinement'][-1]['estimated_model_surface_obstruction_fraction']
table='\n'.join('|'+s+'|'+ '|'.join(f'{q[k]:.2%}' for k in ['FIXED_MINUS_Y','FIXED_PLUS_Y','FIXED_MINUS_Z_BOTTOM_PLATE'])+'|' for s,q in values.items())
viewer='http://127.0.0.1:3245/'+urllib.parse.quote(A.as_posix(),safe='/:')
live=viewer+'?file=mechanical%2Ffixed_heat_bay.step.py';bottomlive=viewer+'?file=mechanical%2Fbottom_mount_assembly.step.py'
dump('results/VIEWER_LINKS.json',dict(current_thermal_bay=live,bottom_mount=bottomlive,native_bottom_assembly=np['assembly_path'],source_instance_plan='mechanical/FIXED_HEAT_INSTANCE_PLAN.json',full_native884_available=False))
shot='review/fixed_heat_bay_bottom_revision_iso_20260908T220527Z.png'
report=f'''# WP10 当前候选：底部散热结构与原生安装组件

已完成底部散热板、甲板与四个下层角码改件，安装六组紧固件；生成并冷读验证24实例/24实体的SolidWorks底部安装组件。整机候选源表为884实例、三个离散状态。**整机机电详细设计仍未完成，尚不能按完整工程样机、通电或飞行设计交付。**

[统一查看](REVIEW.html) · [旋转查看当前整舱改件]({live}) · [旋转查看底部安装]({bottomlive}) · [SolidWorks组件包](mechanical/WP10_BOTTOM_SOLIDWORKS.zip) · [当前全部设计增量包](WP10_IMPLEMENTATION_DELTA.zip)

底板344×196.3×8mm，外表面S z=-114.15；六座为(-140,±93.5)、(-60,±33)、(120,±93.5)。外四座接触角码底面，内两座接触甲板底面。四角码与甲板同轴新孔进入源文件。横梁、原拉杆/螺母、甲板螺钉和MiPS脚螺钉均有具体避让。净平面辐射面积{g['actual_outward_planar_radiating_area_mm2']/1e6:.8f}m²；按2700kg/m³估计底板质量{g['plate_mass_estimate_kg']:.6f}kg，未计为整星质量收口。最薄盲孔底皮3.95mm；载荷、预紧、公差和热接触性能仍需验证。

紧固件按Würth4123 53 20（ISO10642 M3×20，头径6.72/头高1.86）、norelem07300-03（垫圈Ø7/Ø3.2/厚0.5）与07210-403（M3螺母高2.4/对边5.5）公开尺寸选取。CAD为项目名义重建体，螺纹简化；目录中垫圈实际1.1mm、螺钉头径约5.639mm的错误模型已拒绝。未采购、未绑定到货修订/涂层适用性。见[厂家证据](sources/BOTTOM_VENDOR_SOURCES.json)。

原873封存父本保持：移除14个旧盖系统件和旧battery_thermal_link，加入8个器件/TIM与18个紧固件，得到884；11个原ID形状替换、14夹具件移位不增计数。删除旧电池热连接是设计处置，**电池受控热接口仍开放**。当前24件原生组件不能替代884整星原生总装。

本轮验证：48项底部实体/接触/定位检查；工作、收拢、释放状态各531对改件邻域STEP精确相交检查均零正体积交集、零未知；36个局部工具包络检查通过。工具为OD8/ID6.4套筒及OD4外侧内六角杆、20mm局部长度，不代表完整插入路径或公差检查。11个STEP目标已完成refs及有效性检查；装配通用自交跳过，局部24体和改件邻域由上述独立成对布尔检查承担。五张快照已核阅。

SolidWorks2024原生结果：9个SLDPRT分别保存、关闭、重新打开核验单位/实体/极值包围盒/体积及无外部几何引用；SLDASM在新会话冷读24唯一实例、24实体、0曲面、全部坐标变换与9本地依赖。源级刚性基准被解析为固定实例，无运动配合。原生文件与依赖见[底部原生装配](mechanical/native/WP10_BOTTOM_MOUNT.SLDASM)、[冷读回执](results/NATIVE_BOTTOM_COLD.json)。

帆板后续间距曾在STEP实例变换恢复时丢失，现已用当前与基线原生刚性差修复；18个帆板STEP位置读回最大误差1.43e-14mm。表面遮挡重算绑定当前884实例及当前底板净面（含孔/缺口），结果为面积与余弦加权半球方向采样：

|状态|−Y遮挡|+Y遮挡|底部−Z遮挡|
|---|---:|---:|---:|
{table}

这些是当前CAD表示的有限采样结果，并非太阳入射阴影、严格误差界或实测。被遮方向仍与帆板/星体辐射换热，不能直接把面积乘(1−遮挡比例)视为散热能力；还需局部空间视因子、温度、其他热源和真实任务环境。旧单侧85%效率满功率热失败仍保留；旧两板桥计算仍仅为注明边界的方案研究。**CHB至新底板的实际导热连接尚未安装，新增面积没有获得满功率热通过信用。**

电气源保持201位号、11页KiCad；435原生网表检查、104制动检查、50启动静态检查、8故障网清点沿用各自已绑定回执，7个power_pin_not_driven ERC仍披露。360W臂任务不变。制动真实能量/动态、独立STOP和启动动态、PCB/保护配合、电池PMM/高电流接口、线束真实端接，以及推进同修订ICD/任务能力仍须完成。37行责任表的完成等级未因本轮局部进展升级。

[电气PDF](ecad/wp10_system.pdf) · [KiCad源](ecad/wp10_system.kicad_sch) · [电气BOM](power/SELECTED_BOM.csv) · [线束From–To](ecad/MASTER_FROM_TO.csv) · [37行责任表](SYSTEM_CLOSURE_MATRIX.csv) · [机器裁决](results/DELIVERY_DECISION.json)

[底部几何](results/BOTTOM_MOUNT_GEOMETRY.json) · [三态接口](results/FIXED_HEAT_INTERFACE_SUMMARY.json) · [工具检查](results/BOTTOM_LOCAL_TOOL_CLEARANCE.json) · [表面遮挡](thermal/RADIATOR_MESH_VIEW_SCREEN.json) · [源变换修复](results/FIXED_HEAT_STEP_FRAME_REPAIR.json) · [BOM增量](mechanical/FIXED_HEAT_BOM_DELTA.csv) · [源参数](thermal/BOTTOM_RADIATOR_MOUNT.json) · [审阅处置](results/BOTTOM_REVIEW_DISPOSITION.json) · [内存记录](results/BOTTOM_MEMORY_AUDIT.json)

运行采用启动≥2GiB、运行≥512MiB、任务/Python与自有SW合计≤1400MiB。未终止无关应用。一次240秒CAD批次超时已清理自有树；只复用源SHA一致的已完成检查。本包仍为同项目候选增量，CAD源复建引用工作区父源与已安装CAD运行时。

![本轮当前整舱改件]({shot})
'''
(A/'README.md').write_text(report,encoding='utf-8')
page=(A/'REVIEW.html').read_text(encoding='utf-8').replace('各345对','各531对').replace('三状态各345对','三状态各531对').replace('原生867','原生884')
page=page.replace('固定散热壁、舱板与线束改件已生成；热分配仍需修改','底部散热结构与24件原生SolidWorks安装组件已生成')
card='<section><h2>当前底部安装交付</h2><p>底板、甲板、四角码、18紧固件，共24实例/24实体；9个原生SLDPRT与SLDASM已保存并独立冷读。三个状态各531对改件邻域零穿透。整星884原生总装、CHB到底板热连接及机电全功能闭环仍开放。</p><img src="'+shot+'" alt="当前整舱改件"><nav><a href="mechanical/WP10_BOTTOM_SOLIDWORKS.zip">下载SolidWorks组件包</a><a href="'+html.escape(bottomlive,quote=True)+'">旋转查看底部安装</a><a href="README.md">完整当前说明</a><a href="results/NATIVE_BOTTOM_COLD.json">原生冷读证据</a><a href="thermal/RADIATOR_MESH_VIEW_SCREEN.json">当前三态遮挡</a><a href="results/BOTTOM_LOCAL_TOOL_CLEARANCE.json">工具空间</a></nav></section>'
page=page.replace('<section><h2>本轮实际整舱改件',card+'<section><h2>本轮实际整舱改件',1)
(A/'REVIEW.html').write_text(page,encoding='utf-8')
print(json.dumps(dict(revision='V6',source_instances=884,native_bottom_instances=24,full_design_complete=False)))
