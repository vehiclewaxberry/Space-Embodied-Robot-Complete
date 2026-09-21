"""Publish a bounded local design review, not a spacecraft RELEASE gate."""
from pathlib import Path
import csv,datetime,hashlib,html,json,urllib.parse,urllib.request,zipfile
from coupled_adapter import HERE,A,load_candidate,read,dump,sha

def main():
    c=load_candidate();e=read(HERE/'COUPLED_RESULTS.json');t=read(HERE/'THERMAL_RESULTS.json');g=read(HERE/'MECHANICAL_VERIFICATION.json')
    host=read(HERE/'HOST_NARROWPHASE.json');placement=read(HERE/'PLACEMENT_TRANSLATION_SCREEN.json')
    assert host['script_sha256']==sha(HERE/'host_narrowphase.py')
    assert host['mechanical_source_sha256']==sha(HERE/'mechanical_parts.py')
    assert host['bounds_source_sha256']==sha(A/'mechanical/MAIN_INPUT_PLACEMENT_BOUNDS_V27.json')
    assert g['host_placement']['narrowphase_sha256']==sha(HERE/'HOST_NARROWPHASE.json')
    assert placement['script_sha256']==sha(HERE/'placement_screen.py')
    assert all(sha(p)==h for p,h in host['source_lock'].items())
    assert e['adapter_sha256']==sha(HERE/'coupled_adapter.py') and t['script_sha256']==sha(HERE/'thermal_closure.py')
    assert all(x['candidate_sha256']==sha(HERE/'CANDIDATE.json') for x in [e,t,g])
    import xml.etree.ElementTree as ET
    suites=ET.parse(HERE/'TEST_RESULTS.xml').getroot();suite=suites.find('testsuite')
    assert int(suite.get('failures'))==0 and int(suite.get('errors'))==0
    n=int(suite.get('tests'));assert n==35
    assert g['checks']['local_no_unintended_volume_intersections']
    mainpng=next(HERE.glob('MAIN_MODULE_*.png'));proppng=next(HERE.glob('PROPULSION_KIT_*.png'))
    cases=[r for r in t['spatial_cases'] if r['pitch_mm']==5]
    power=next(r for r in e['operating_points'] if r['pack_V']==25.2 and r['shared_R_ohm']==.01 and r['eta_main']==.85 and r['main_R_breakdown_ohm']['Q201_25C']>.03)
    cold=next(r for r in t['transient_screens'] if r['cold'] and r['step_s']==1)
    scope=[
       ['电气位号与针脚','同源派生一致','207位号 / 673针脚网络；U303与U304纠正；未改ERC规则或Kelvin分裂盘','ACTIVE_ELECTRICAL_BOM.csv'],
       ['供电与相位预算','有界计算完成，实际任务未闭环','32工况消费原有电源求解器，UVLO/限流角点进入相位拒绝；充电/预充/真实回生仍UNKNOWN','COUPLED_RESULTS.json'],
       ['热控','发现连续运行超限','同源板热加入后超过105°C；冷加热与能量守恒已计算，真实热路/在轨工况未绑定','THERMAL_RESULTS.json'],
       ['推进能力','目录候选及程序边界已定义','真实喷口/作用点/命令/并发/喷流ICD为null，不发出动作许可','PROPULSION_RESOURCE_SCREEN.json'],
       ['机械物理件','局部参数化STEP完成，整机候选安装位置被拒绝','主输入模块14实体、推进接口套件3实体；每态42组包围盒命中已做实体检查，各18处交叠；未装入974实例','MECHANICAL_VERIFICATION.json'],
       ['研究接入','实际函数的参数消费测试通过','电源为当前输入；推进/rigidize仅合成测试；当前873物性缺失，未冒充974关节多体','TEST_RESULTS.xml']]
    with (HERE/'CLOSURE_MATRIX.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['scope','status','evidence_boundary','artifact']);w.writerows(scope)
    report=f'''# WP10 电气—热控—推进联合候选与机械件交付

2026-09-10。已完成来源统一、可执行约束与局部机械件设计；**完整星载电气/热控/推进、整机安装和制造放行尚未完成**。本次读取附件作为参考工单，执行范围来自用户“读取现状做出电气设计/动力推进系统闭环，完成相关机械结构物理件设计”。未采用附件Stage A的只读停止要求作为本次任务边界，也未把附件文本视为额外硬件操作授权。

实际输入为V26电气/PCB与V21的974实例计划。43个决定性文件以SHA锁定，另保留873物性包的实际身份。所有新产物集中在本目录；既有CAD、PCB、科研Gate和失败记录未改写。本次没有制造、上电、充电、加压、点火或外部联系。

**保留的工程选择与理由。** 保留RRC3570-4 Rev D、单路CHB500W-24S24N、独立THN30-2415WIR。主输出361W（360W臂端分配+1W制动偏置），辅助输出16.8W，输入启动另0.25W。PMM35的20A能力不能保证低压端全功率，维持未接入主放电路径的充电候选；地面RSP外供不记入星载供能。当前候选优先完成已选模块的热/连接验证；若原接口或效率证据不支持，再换型并重验，不能仅为安装方便换电池/缩短任务求PASS。

**电气闭环产物。** [实际BOM](ACTIVE_ELECTRICAL_BOM.csv)与[针脚网络](ACTIVE_PIN_NETS.csv)直接派生自当前XML；逐项比对207个功能位号。U303已由旧汇总的UCC27511改为实际MAX5048CAUT+T，补入U304 MAX16053AUT+T。数值/标签不是采购保证。原PCB仍有4项Kelvin分裂盘未连DRC，未跨铜消错。F201原厂3oz/10mm走线条件与V26的70μm/8mm情景不等价，铜厚、端接电流、焊接与保险配合均未制造放行。

共同回路逐项计入Q201、shunt、铜、保险、线束分配与MC35接点；25.2V/.01Ω/η=.85/热态Q201×2情景输入约{power['input_power_W']:.3f}W，非机械臂热量约{power['accounted_non_arm_heat_W']:.3f}W（不含尚未知的臂局部热、电池内部热和输出分配损耗）。主铜8.577mΩ来源保持；新增线束10mΩ是明确未测分配，未复用旧40/60mΩ总阻再重复加器件。20/22V RUN点会被既有UVLO屏幕拒绝；25.2V高接触阻情景可能依赖器件角点。保持运行判断不证明可以启动。

共同情景是**演示性600s运行/1200s冷却、两周期**，不是已批准任务。以名义407.43Wh×80%为初始可用能量假设，两周期剩{e['declared_600s_two_cycle_sensitivity']['energy_remaining_Wh']:.3f}Wh，跨相位不重置能源。真实任务时长、SOC可用能量、轨道/太阳补能与回生波形未绑定时，程序输出UNKNOWN并拒绝操作许可。

**联合热结果（继承released姿态、330K遮挡、+Y侧1361W/m²、25psi典型TIM参数）。**

| 情景 | CHB壳温 | 相对105°C余量 | 证据含义 |
|---|---:|---:|---|
| CHB单独重放 | {cases[0]['CHB_case_C']:.3f}°C | {cases[0]['CHB_margin_C']:.3f}°C | 原单模块口径复现 |
| CHB+新输入板含0.25W启动 | {cases[1]['CHB_case_C']:.3f}°C | {cases[1]['CHB_margin_C']:.3f}°C | 新板拟议热路下已超限 |
| 已知非臂热全部接入假设 | {cases[2]['CHB_case_C']:.3f}°C | {cases[2]['CHB_margin_C']:.3f}°C | 含未安装/未证实热路的压力筛查 |
| 高接点电阻同口径 | {cases[3]['CHB_case_C']:.3f}°C | {cases[3]['CHB_margin_C']:.3f}°C | 假定保持导通的压力筛查，保护可能先动作 |

新板热路位置和接触阻未完成整机验证，以上不是实机温度预测。局部最大温度来自已有二维导热/辐射求解器；步长/网格、正负热流和守恒均保留。10→5mm网格差最大{max(t['mesh_delta_C'].values()):.3f}°C，稳态能量差最大{t['energy_balance_max_W']:.3g}W。瞬态另外采用三散热面理想混温的乐观筛查，不假装得到器件或电池温度；冷起点-10°C确实触发加热，输出{cold['heater_output_Wh']:.4f}Wh，转换损耗{cold['heater_conversion_loss_Wh']:.4f}Wh同时进入热量与电池账。连续360W任务的热闭环未达成，不能用理想混温或减少时长抹掉超限。

**机械设计与检查。** [主输入板模块STEP](main_input_module.step)含整体载板/跨板前缘导热悬臂、4支柱、两组双槽导向件、绝缘垫与肩套，以及实际钻孔PCB和6个器件尺寸参考体，共14实体。[推进接口套件STEP](propulsion_interface_kit.step)为项目侧载板与分离的OD6双槽导向件，共3实体。8种项目零件几何由[参数源](mechanical_parts.py)定义；[机械任务书](MECHANICAL_BRIEF.md)记录孔位、材料/公差责任和配合条件。主载板铝几何质量{g['main_aluminum_carrier_mass_kg']*1000:.3f}g，推进载板{g['propulsion_blank_mass_kg']*1000:.3f}g；非实测质量，未知TIM/器件物性未补零。原生SolidWorks总装没有新建，STEP为本次交付几何。

17实体均为有效闭合正体积实体，局部非预期体积干涉0；推进板独立解析体积与CAD一致，载板宽度+2mm确实产生相应几何体积变化。Q201垫厚0.203mm；肩套对最小器件孔径名义径向余隙0.075mm；金属螺钉/预紧/热循环/绝缘验证未完成。主板尚有25个位号未建立完整器件形状，不称整板装配通过。

整机候选位置已完成[实体窄相位检查](HOST_NARROWPHASE.json)：每态42组包围盒命中涉及27个旧实例、25份哈希一致的STEP。以新零件index保留两个同名导向件身份，串行加载旧件，42组不同的实体配对计算后按相同来源及变换复用于三态；**service/parking/released各18处体积交叠，该位置被拒绝**。载板与真实剪切腹板交叠约24078.393mm³，同时撞P60托盘等；P60参考盒与计算设备代理分别保留FUNCTIONAL_ENVELOPE/SIMPLIFIED_PROXY身份，不混成实测几何。未写入974实例计划。

[单朝向平移筛查](PLACEMENT_TRANSLATION_SCREEN.json)另检查3465个service位置，未找到AABB全分离点，最少仍15组候选配对。包围盒重叠不等于实体干涉，该有限网格也不证明所有布局都不可行；须调整舱内布置/安装方案后重新设计，不以局部STEP无干涉替代整机安装通过。推进导向孔对OD6线束留径向0.2mm间隙，无已验证夹持/应变释放信用；其孔与载板不配对，需另绑安装点。

**推进裁决。** C-POD X13003000-01仍为资料候选；旧MiPS模型仍是已存在的非承压参考件，两者未混同。官方锁定目录给174Ns、8×10±2mN、0.50mNs MIB等，未给受控喷口坐标、唯一安装孔坐标/深度、允许组合、命令表和完整最大包络。项目载板不加工推测OEM孔；#4-40不能当M3。MIB/推力仅得41.67–62.5ms等效矩形时长，不作为最小命令脉宽。

程序实际调用旧wrench_matrix/allocate，并新增有限脉冲的单向命令、最小开关时间、总冲量、瞬时电力、并发数量及喷流禁用检查。真实喷口输入为null时保持UNKNOWN。脉冲测试使用明确合成阵列，不包含姿态传播、OEM故障/允许组合和实际阀传递函数。历史150kg目标的3.65099Nms仅作独立资源参考；若喷口位于目录盒内且累计零合力，C-POD乐观推进剂下界约109.45g。实际喷口包络前提未知，所以这个条件计算不证明本星可以或不可以消旋。

**研究接入与验证。** 35项pytest通过，包括完整BOM比对、源漂移、NaN/Inf/效率>1/负电阻拒绝、UVLO、跨相位能源、冷加热、错误方向/冲量/并发/瞬时功率/喷流、真实函数参数扰动与能量动量守恒。当前输入实际消费shared_battery_path.solve；wrench_matrix/allocate及30_simulation/common/capture_impulse.rigidize在合成测试中消费。rigidize是完全刚性锁定瞬间算子，非关节/柔性运动求解器。当前PARAMETER_PACKET仍873实例、物性缺失、并非974，因此未重绑整机捕获模型，也未改写旧科研PASS。

独立只读审查修正了保护范围、物理输入校验、启动板热、加热转换损失、源锁导入顺序及共同参数消费。首次pytest临时目录权限错误改用项目隔离临时目录；CAD独立检查复用已有进程内字体过滤，不修改系统字体。最终原始回执见[测试日志](TEST_LOG.txt)、[测试XML](TEST_RESULTS.xml)、[机械检查](MECHANICAL_VERIFICATION.json)、[数值结果](COUPLED_RESULTS.json)及[热结果](THERMAL_RESULTS.json)。

**剩余最少输入与退出条件。**

1. 任务方固定轨道热环境、实际服务/停止/冷却/退避时序与允许资源；退出条件是同一相位表覆盖发电、SOC、热、推进，实测或有界参数不留隐式默认。
2. RRC/驱动资料或台架绑定MC35针位/SysDetect、接点热/压降、真实回生与关断延迟、启动和热短路条件；退出条件是针脚端到端连接和波形/保护/温度界均有证据。
3. VACCO提供与硬件/固件同修订的电气+机械+喷口ICD；退出条件是可生成真实B矩阵、实际单向脉冲排程与安装件，并通过含目标COM的任务冲量/退避预算。

同时还有内部工程工作：新输入板全器件形状/线束/整机干涉，额外热量对应的真实散热能力，974构型逐link质量惯量。下一项研究动作应先用这个冻结接口做同一任务时序下的热/电资源可执行性比较；真实推进与捕获输入绑定前不开展或宣称全星消旋验证。

复现：在本目录用现有Anaconda Python依次运行coupled_adapter.py、thermal_closure.py、propulsion_resources.py与pytest test_coupled_adapter.py；先读CANDIDATE源锁。build_inputs.py只在明确接收上游改版时执行，不能为使源漂移测试通过而盲目刷新。CAD以对应.step.py运行已安装cad/scripts/gen --write，再执行inspect validate与snapshot。机械独立检查verify_mechanical.py（含真实STEP窄相位）须使用父目录tools/cad_runtime进程内字体过滤（见MECHANICAL_CHECK_LOG）；placement_screen.py复现有限网格筛查。

厂商来源：[Q201原厂数据](https://www.littelfuse.com/assetdocs/Littelfuse-Discrete-MOSFETs-N-Channel-Linear-IXT-75N10-Datasheet.PDF?assetguid=EA051E16-AAA9-4983-A975-8D0C07325D72)、[TSP1800ST](https://datasheets.tdx.henkel.com/BERGQUIST-SIL-PAD-TSP-1800ST-en_GL.pdf)、[C-POD锁定目录](https://cubesat-propulsion.com/wp-content/uploads/2022/04/X13003000-01_RCM_2016update.pdf)。Q201 exact step.parts查询无结果，采用明确标记的原厂尺寸参考体；不将公开宣传、旧版本或无实物校验的外形转作飞行合格证据。
'''
    (HERE/'README.md').write_text(report,encoding='utf-8')
    viewer_root='http://127.0.0.1:3245/'+urllib.parse.quote(HERE.as_posix(),safe='/:')
    viewer={name:viewer_root+'?file='+name for name in ['main_input_module.step.py','propulsion_interface_kit.step.py']}
    try:
        with urllib.request.urlopen('http://127.0.0.1:3245/',timeout=5) as res:live=res.status==200
    except Exception:live=False
    dump('VIEWER_LINKS.json',dict(verified_server_reachable=live,links=viewer))
    tab=''.join('<tr><td>'+html.escape(r['case'])+'</td><td>'+f"{r['CHB_case_C']:.3f}°C"+'</td><td>'+f"{r['CHB_margin_C']:.3f}°C"+'</td></tr>' for r in cases)
    scopes=''.join('<tr>'+''.join('<td>'+html.escape(x)+'</td>' for x in row[:3])+'</tr>' for row in scope)
    page=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>WP10联合候选</title>
<style>body{{font:16px/1.7 system-ui,"Microsoft Yahei";max-width:1100px;margin:40px auto;padding:0 24px;background:#f1f5f8;color:#163041}}h1{{font-size:32px}}.card{{background:white;padding:24px;margin:20px 0;border-radius:12px}}.warn{{border-left:5px solid #c77821}}img{{width:100%;border-radius:8px}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{padding:10px;border-bottom:1px solid #dbe4ea;text-align:left}}a{{color:#066d9b}}small{{color:#557}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}@media(max-width:750px){{.grid{{display:block}}}}</style>
<h1>电气 · 热控 · 推进<br>同源工程候选与机械件</h1><p>2026-09-10 · 43项源锁 · 207位号 · 35项测试 · 17个局部实体</p>
<div class="card warn"><b>局部数字设计已交付；整星机电闭环尚未达到。</b><p>新输入板热量计入后CHB约107.060°C，超过105°C限值。新模块候选安装位置三态各18处实体交叠，已拒绝；推进ICD及974实例逐link物性未绑定。制造、通电、承压和飞行均未放行。</p><a href="README.md">完整中文报告</a> · <a href="CANDIDATE.json">受控候选参数</a> · <a href="TEST_LOG.txt">原始测试记录</a></div>
<div class="grid"><div class="card"><h2>主输入板局部结构</h2><img src="{mainpng.name}"><p>载板与导热悬臂、绝缘件、双槽导向件；PCB只含部分器件参考体。局部无非预期体积干涉。</p><a href="{viewer['main_input_module.step.py']}">交互查看</a> · <a href="main_input_module.step">STEP</a> · <a href="mechanical_parts.py">参数源</a></div>
<div class="card"><h2>推进项目侧接口套件</h2><img src="{proppng.name}"><p>项目载板与分离导向件。OEM孔位未知、未装配，不包含承压结构或喷口推测。</p><a href="{viewer['propulsion_interface_kit.step.py']}">交互查看</a> · <a href="propulsion_interface_kit.step">STEP</a> · <a href="MECHANICAL_BRIEF.md">尺寸与配合</a></div></div>
<div class="card"><h2>同工况热结果</h2><small>继承的示例环境/典型TIM；新热路仍为拟议边界，非实机预测。</small><table><tr><th>情景</th><th>CHB壳温</th><th>105°C余量</th></tr>{tab}</table><a href="THERMAL_RESULTS.json">网格、守恒与冷加热原始结果</a></div>
<div class="card"><h2>本轮范围</h2><table>{scopes}</table></div>
<div class="card"><a href="ACTIVE_ELECTRICAL_BOM.csv">电气BOM</a> · <a href="ACTIVE_PIN_NETS.csv">针脚网络</a> · <a href="MECHANICAL_BOM.csv">机械BOM</a> · <a href="COUPLED_RESULTS.json">相位/保护预算</a> · <a href="PROPULSION_RESOURCE_SCREEN.json">条件推进资源筛查</a> · <a href="MECHANICAL_VERIFICATION.json">机械验证</a></div></html>'''
    (HERE/'REVIEW.html').write_text(page,encoding='utf-8')
    dump('DELIVERY_STATUS.json',dict(scope='WP10_LOCAL_COUPLED_DIGITAL_INCREMENT',
       source_locked_files=43,electrical_refs=207,pin_net_records=673,tests_passed=n,
       local_CAD_valid_solids=17,local_volume_interferences=0,
       host_narrowphase_performed=host['narrowphase_performed'],
       host_candidate_pose_rejected=any(v['collisions'] for v in host['states'].values()),
       host_intersections_by_state={k:len(v['collisions']) for k,v in host['states'].items()},
       installation_source_files_checked=len(host['source_lock']),
       placement_translation_grid_poses=placement['poses_screened'],
       electrical_end_to_end_closed=False,thermal_continuous_closed=False,propulsion_installed_and_verified=False,
       current_full_multibody_bound=False,new_parts_installed_in_whole=False,
       physical_tests_executed=False,manufacturing_release=False,flight_qualified=False,
       source_stability_rechecked=True,whole_design_complete=False,
       reviewers='Two independent read-only reviewers; final code/physics findings disposition in README',
       former_test_environment_errors='pytest Temp ACL and invalid Windows font; repaired by isolated temp/process-local existing filter',
       attachments_are_reference_not_authorization=True))
    files=[p for p in HERE.iterdir() if p.is_file() and p.suffix!='.zip' and p.name!='SHA256.csv']
    with (HERE/'SHA256.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['file','sha256']);w.writerows((p.name,sha(p)) for p in sorted(files))
    with zipfile.ZipFile(HERE/'WP10_COUPLED_CANDIDATE.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in files+[HERE/'SHA256.csv']:z.write(p,p.name)
    print(json.dumps(dict(report=str(HERE/'REVIEW.html'),viewer=live,files=len(files),tests=n)))

if __name__=='__main__':main()
