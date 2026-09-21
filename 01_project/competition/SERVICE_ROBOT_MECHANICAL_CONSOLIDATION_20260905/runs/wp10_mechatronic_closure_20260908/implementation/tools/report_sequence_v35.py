"""Publish the verified V35 ECAD candidate and evidence-based whole-system work plan."""
from pathlib import Path
import collections,copy,csv,datetime,hashlib,html,json,re,zipfile,xml.etree.ElementTree as ET
from erc_source_contract import parse,children,properties
A=Path(__file__).resolve().parents[1];D=A/'ecad/revisions/v35';R=A/'results/aux_v35';C=A/'coupled_closure'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def csvwrite(p,rows):
    with p.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def check_bindings(v):
    for p,h in v['source_bindings'].items():assert sha(p)==h,p
def main():
    v=read(R/'VERIFICATION.json');n=read(R/'NATIVE_AUDIT.json');cal=read(R/'CALCULATIONS.json');sel=read(R/'SELECTED_PARTS.json')
    assert v['scoped_verification_passed'];check_bindings(v);check_bindings(n);check_bindings(cal)
    boards={}
    for label,file in [('MAIN_INPUT_PCB','wp10_main_input.kicad_pcb'),('AUX_PROTECTION_SEQUENCE_PCB','wp10_aux_protection.kicad_pcb')]:
        node=parse((D/file).read_text());refs=[]
        for fp in children(node,'footprint'):
            attrs=children(fp,'attr')
            if attrs and 'board_only' in attrs[0]:continue
            refs.append(properties(fp)['Reference'])
        boards[label]=set(refs)
    x=ET.parse(D/'wp10_system.xml').getroot();rows=[]
    for co in x.findall('./components/comp'):
        props={f.get('name'):f.text for f in co.findall('./fields/field')};ref=co.get('ref')
        where=[label for label,refs in boards.items() if ref in refs]
        rows.append(dict(ref=ref,value=co.findtext('value'),footprint=co.findtext('footprint') or '',sheet=co.find('sheetpath').get('names'),
          source_revision='V35',MPN=props.get('MPN',''),manufacturer=props.get('Manufacturer',''),datasheet=co.findtext('datasheet') or '',
          placement_scope=';'.join(where) if where else 'SYSTEM_MODULE_OR_UNPLACED_DETAIL',
          selection_scope='Explicit MPN field; suitability not certified' if props.get('MPN') else 'MPN field absent; value may contain part code or system module alias'))
    pins=[dict(net=net.get('name'),ref=z.get('ref'),pin=z.get('pin'),pinfunction=z.get('pinfunction',''),pintype=z.get('pintype','')) for net in x.findall('./nets/net') for z in net.findall('node')]
    assert len(rows)==237 and len(pins)==767
    csvwrite(D/'SYSTEM_BOM.csv',rows);csvwrite(D/'PIN_NET_TABLE.csv',pins)
    csvwrite(D/'BOM_DELTA_V35.csv',[r for r in rows if r['ref'] in sel])
    for label,refs in boards.items():csvwrite(D/(label+'_BOM.csv'),[r for r in rows if r['ref'] in refs])
    stale=D/'BOM_DELTA_V34.csv'
    if stale.exists():
        assert stale.resolve().parent==D.resolve() and sha(stale)==sha(D.parent/'v34/BOM_DELTA_V34.csv')
        stale.unlink() # Remove only the unchanged copied historical CSV from this new revision.
    harness=list(csv.DictReader((D.parent/'v34/AUX_HARNESS_INTERFACE.csv').open(encoding='utf-8-sig')))
    harness.extend([dict(port='J211.1',net='WP10_THN_REMOTE',remote='U202.3',role='Primary-side THN voltage-qualification control; open wire defaults ON; not STOP barrier'),
      dict(port='J211.2',net='WP10_INPUT_RETURN',remote='U202.2 same primary return as J209.2',role='Remote reference; never connect to isolated ARM_RETURN')])
    csvwrite(D/'AUX_HARNESS_INTERFACE.csv',harness)
    csvwrite(D/'AUX_MATING_BOM.csv',[
      dict(item='J208/J209/J211 mating receptacle',MPN='430250200',quantity=3,selection_status='Public family match; new remote connector included; installed fit not verified'),
      dict(item='Female tin crimp terminal',MPN='430300007',quantity=6,selection_status='20 AWG candidate; actual wire MPN/cut length/crimp process and environment open')])
    coverage=dict(system_refs=len(rows),explicit_MPN_field_refs=sum(bool(r['MPN']) for r in rows),explicit_footprint_field_refs=sum(bool(r['footprint']) for r in rows),
      board_electrical_footprints={k:len(s) for k,s in boards.items()},
      meaning='237 is a system netlist count, including module ports and detailed circuits. Missing MPN fields do not prove no part was selected; part codes may be in Value. It is not a ready-to-order 237-part PCB BOM.',
      system_BOM_order_ready=False,complete_system_PCB_parity_checked=False)
    dump(R/'SELECTION_COVERAGE.json',coverage)
    nextsteps=[
      dict(order=1,domain='电气故障行为',actual_change='完成STOP失电默认关闭、短掉电复位、人工再启动；落实负载侧回生吸收与温度联锁；形成剩余原理图与PCB',outputs='同版本STOP/回生PCB、针脚表、故障时序矩阵、负控与故障能量账',acceptance='启动/关断/欠压/短掉电/卡键/断线的行为有依据；未测情况保持未知',external_dependency='THN输入启动特性、DM停止与回生边界；实际波形需另行试验',status='内部设计继续，硬件验证未执行'),
      dict(order=2,domain='储供电与全周期能量',actual_change='保留360W筛查需求，核定电池/保护路径；补太阳阵列到电池的稳压充电与任务功率调度',outputs='统一选型BOM、源到臂端电流/能量账、充电与动作互锁合同',acceptance='最低带载电压、峰值与持续电流、补能及任务时长均有同一边界',external_dependency='真实负载谱、电池/PMM受控接口及太阳阵列输出',status='条件计算已有，完整能量周期未闭合'),
      dict(order=3,domain='热结构与舱内布置',actual_change='重排主输入模块与60x70mm辅助板；补23个未建模主输入位号；建立CHB—TIM—承载件—固定辐射面热路',outputs='器件实体/高度、压紧TIM与紧固结构、CAD布置、热网络及线束端接表',acceptance='相同完整热边界下不超过器件限值；净空、安装和工具通道满足要求',external_dependency='界面材料压紧/热阻数据与真实发热/温升验证',status='V33加厚试验拒绝；须实际改件'),
      dict(order=4,domain='机械构型与物性',actual_change='在原873宿主逐项回装已接受模块；建立真实收拢/工作构型、关节与配合；解释DM质量差异并回写材料/COM/惯量',outputs='可冷重开的SLDASM/STEP、配置与配合、质量惯量参数卡、连续路径与线束检查',acceptance='计划与原生装配一致；parking不能代称发射收拢；未知物性不填占位真值',external_dependency='DM同修订组成/图纸、部分实测质量与COM',status='固定姿态数字布局已有，完整工程装配未完成'),
      dict(order=5,domain='推进与姿控接口',actual_change='以完整商业模块复用为主，绑定同修订喷口/电气/脉冲/并发/羽流接口，按当前COM重建推力分配',outputs='受控ICD映射、安装接口、真实喷口分配器、任务冲量/能量/窗口预算',acceptance='真实6自由度能力、禁喷与脉冲限制可评价；合成阵列不可冒充实物',external_dependency='C-POD受控ICD；轮组轴系及力矩/速度/功率包络',status='接口与目录资源筛查已有，真实任务能力未知'),
      dict(order=6,domain='同版本整机验收',actual_change='统一CAD/ECAD/线束/BOM/物性/推进数据并从干净环境重开复算',outputs='整机交付清单、版本哈希、装配/干涉/连续运动/电热/故障验收报告',acceptance='所有必要设计项通过或精确列出外部待验证项；设计交付与制造/接电/飞行放行分开',external_dependency='前序接口与必要实物证据',status='尚未开始最终验收')]
    csvwrite(C/'NEXT_ENGINEERING_ACTIONS_V35.csv',nextsteps)
    evidence=[A/'baseline_load_closure_v31/DELIVERY_STATUS_V31.json',A/'baseline_load_closure_v31/mechanical/MECHANICAL_BASELINE.json',
      A/'baseline_load_closure_v31/mechanical/BODY_PARAMETER_CARD.json',A/'baseline_load_closure_v31/actuators/ACTUATOR_CONTRACT.json',C/'PROPULSION_RESOURCE_SCREEN.json',C/'DELIVERY_STATUS_V33.json',A/'SYSTEM_CLOSURE_MATRIX.csv']
    maturity=dict(revision='V35',stage='系统详细设计与子系统局部验证',whole_design_complete=False,completion_percentage=None,
      reason_no_percentage='不同模块成熟度与外部依赖不同；不存在受控权重可生成可信完成百分比',electrical=coverage,
      mechanical=dict(native_host_instances=873,fixed_pose_count=3,planned_instances=974,planned_pose_records=2922,latest_geometry_revision='V30/V28',native_whole_integration_updated=False,
        V30_module_uninstalled_parts=56,V30_module_uninstalled_solids=60,parking_is_launch_stowed=False,whole_mass_COM_inertia_bound=False),
      propulsion=dict(catalog_resource_screen_available=True,controlled_same_revision_ICD_bound=False,actual_thruster_geometry_bound=False,actual_six_DOF_mission_capability='UNKNOWN'),
      thermal=dict(V33_trial_accepted=False,board_heat_scenario_CHB_C=[105.83691696291373,107.21357253174898],CHB_limit_C=105,three_shortlisted_placements_intersections=[8,7,7]),
      source_bindings={str(p):sha(p) for p in evidence},next_steps=nextsteps)
    dump(C/'SYSTEM_MATURITY_V35.json',maturity)
    opens=[s['domain']+'：'+s['status'] for s in nextsteps]
    stage=dict(revision='V35',time=datetime.datetime.now().astimezone().isoformat(),status='SCOPED_ECAD_AND_STATIC_INTERFACE_CANDIDATE_VERIFIED',same_WP10_candidate=True,
      electrical_refs=237,pin_records=767,schematic_pages=15,main_PCB_electrical_footprints=len(boards['MAIN_INPUT_PCB']),auxiliary_PCB_electrical_footprints=26,
      auxiliary_board_only_mounting_holes=6,aux_PCB_dimensions_mm=[60,70,1.6],new_component_nominal_max_height_mm=18,
      whole_design_complete=False,manufacturing_release=False,power_on_release=False,hardware_tests=0,propulsion_release=False,
      board_3D_or_native_whole_assembly_newly_integrated=False,geometry_revision='V30/V28',input_baseline_revision='V31',
      original_873_component_parent_preserved=True,original_99_ref_lineage_preserved=True,original_37_row_matrix_preserved=v['parent_sources_unchanged'],
      verification='results/aux_v35/VERIFICATION.json',calculation='results/aux_v35/CALCULATIONS.json',
      approved_scope='Native same-version schematic/auxiliary PCB consistency, inherited exact main PCB DRC, explicitly conditional static power/interface calculations.',
      joint_time_domain_startup_verified=False,STOP_manual_rearm_brownout_verified=False,open_items=opens)
    dump(C/'DELIVERY_STATUS_V35.json',stage)
    prior=C/'CANDIDATE_V34.json';candidate=copy.deepcopy(read(prior))
    candidate.update(schema='WP10_ACTIVE_DESIGN_DELTA_V35',revision='V35',parent_candidate=str(prior),parent_sha256=sha(prior),electrical_refs=237,pin_records=767,
      electrical_model_consumer='tools/aux_operating_point_v35.py',electrical_model_file=str(R/'ELECTRICAL_CANDIDATE.json'),inherited_nonclosures=opens)
    candidate['active_sources']={k:str(D/name) for k,name in dict(system_schematic='wp10_system.kicad_sch',system_netlist='wp10_system.xml',
      main_input_PCB='wp10_main_input.kicad_pcb',auxiliary_protection_PCB='wp10_aux_protection.kicad_pcb',BOM='SYSTEM_BOM.csv',pin_net_table='PIN_NET_TABLE.csv',aux_harness='AUX_HARNESS_INTERFACE.csv').items()}
    candidate['active_sources'].update(calculation=str(R/'CALCULATIONS.json'),verification=str(R/'VERIFICATION.json'),system_maturity=str(C/'SYSTEM_MATURITY_V35.json'))
    candidate['scoped_acceptance']=dict(system_ERC_errors=0,system_ERC_warnings=0,main_input_DRC='INHERITED_BYTE_IDENTICAL_V34',auxiliary_DRC_violations=0,auxiliary_DRC_unconnected=0,
      saved_operating_points=96,calculation_negative_controls=8,cold_warm_envelope_scenarios=180,warm_residual_counterexamples=20,ignored_rules_disclosed=True,full_system_PCB_parity_checked=False)
    designfiles={p for p in D.rglob('*') if p.is_file() and p.suffix not in ['.kicad_prl','.lck']}
    candidate['source_lock']={str(p):sha(p) for p in sorted(designfiles|{R/'CALCULATIONS.json',R/'ELECTRICAL_CANDIDATE.json',R/'VERIFICATION.json',R/'SELECTION_COVERAGE.json',C/'SYSTEM_MATURITY_V35.json'})}
    dump(C/'CANDIDATE_V35.json',candidate)
    dump(C/'SOURCE_ACTIVATION_V35.json',dict(revision='V35',candidate_sha256=sha(C/'CANDIDATE_V35.json'),sources_activated=candidate['active_sources'],
      native_whole_assembly_updated=False,geometry_revision='V30',manufacturing_release=False,whole_design_complete=False))
    md='''# WP10 V35 · 当前整机进度与电源时序 PCB

结论：系统详细设计与局部验证阶段；全部电气选型、完整机械装配和真实推进任务能力均未完成。本版可交付源文件供设计审阅，不能作为制造、接电或飞行放行。活动电气V35，几何V30/V28，输入基线V31。

本版新增THN启动电压监督与独立偏置，辅助板60×70×1.6 mm、26个电气封装、6安装孔；新器件最高标称18 mm，尚未置入整舱。主输入板43个电气封装沿用V34字节相同源。整机237位号/767针脚记录/15页原理图；ERC0，辅助DRC0，主板继承V34 DRC0。ERC4类和DRC5类忽略项保留并列于VERIFICATION.json，零违规不表示所有可能规则与性能均已通过。

两块板作用：主板提供输入预充、限流和功率开关接口；辅助板从同一电池的独立支路供给THN/STOP，并增加电压资格与启动延迟。辅助板不会为机械臂直接供给360W，也不承担电机制动能量吸收。低压启动恒功率反例促成本轮时序设计；它独立于主开关，共用电池。

U208 TPS3760A015DYYR经200k/10k分压监测AUX，U209 LT3013提供约6V偏置。D209/D210只保持监控器供电，许可仍来自AUX电压；不自动授予RUN。R231改1.8k，计入THN源向0.5mA和D210反漏1mA场景，净最小负载1.66258mA。释放电压17.323–17.960V；下降阈值16.502–17.102V；冷态RC部分97.28–167.46ms，温态残压可缩短。延迟参数的特定过驱动测试条件不可扩大成任意故障响应上界。

96个假设导通工作点保留360W臂筛查需求与16.8W辅助输出，加30mA控制支路分配，完成独立KCL/KVL和分项热账核对。84点满足新的释放电压条件、12点不能获得新释放；不是84次硬件启动通过。180个充电包络和20个CTR残压场景用于寻找反例，未完成联合时域。30mA不是原厂保证，THN内部输入电容、启动电流、eFuse热跳闸时间与STOP短掉电仍未知。REMOTE线开路时THN默认开启，故本时序不能计作独立停止屏障。

原873组件宿主仍为三个固定姿态；974实例/2922姿态是源计划，未回装为新总装。V30局部主输入56子件/60实体尚未安装，不应与974计划机械相加后宣称完成。parking不是发射收拢；配合、连续运动、真实整机质量/COM/惯量尚未形成一致验收。V31物性记录有270项CAD估算、94项数字来源、610项未知；不能把旧“全是水密度”概括作为现状。DM公开模型约2.74448kg与4.5kg参考差异仍需解释。

V33加厚热板试验继续拒绝：计入板端热分配后CHB约105.837–107.214°C，超过105°C；三个安装短名单分别8/7/7处交叠。只代表这些方案被拒绝，不是所有12U布局都不可行。下一步应实际重排模块与补真实TIM—承载件—外部固定辐射面，不继续仅加厚。

推进已有目录资源筛查、候选安装及合成阵列反例；实际C-POD同修订喷口位置/方向、并发、最小脉宽、羽流/指令和当前COM尚未绑定，真实六自由度任务能力UNKNOWN。继续复用完整商业推进模块，不自制压力内部件。

成熟案例能够复用：B601 DM继续用原厂开源机械/驱动/软件；OreSat参考背板、配电和监测架构；P60在额定范围内承担低功耗配电。公开完整同构12U+B601系统尚未取得。现有模块的母线电压、电流和失电行为需匹配本机，不能凭飞行案例名直接替代接口验证。GomSpace PDU-200公开单通道2A，不等同本机24V/15A筛查路径；这是接口不匹配判断，不是该模块质量问题。

下一步执行顺序见NEXT_ENGINEERING_ACTIONS_V35.csv：STOP/回生故障行为和剩余PCB→储供电与全周期能量→热结构与舱内安装→构型/配合/物性与原生回装→推进真实接口和当前COM任务能力→同版本整机验收。推进ICD收集可与内部改件并行。实测、外部文档、内部设计分别管理，未测量项目不回填PASS。

查看：整机PDF第13页为新时序图；原生入口ecad/revisions/v35/wp10_system.kicad_sch。主板/辅助板分别为wp10_main_input.kicad_pcb和wp10_aux_protection.kicad_pcb。已保存文件供KiCad重新加载查看，不宣称MCP与GUI实时同步。SYSTEM_BOM是混合系统位号清单，部分型号在Value文本；55项具有结构化MPN字段，不是只有55项曾选型，也不是237件均可直接采购。

复算：在原工作区implementation下运行tools/calculate_sequence_v35.py，再运行tools/verify_sequence_v35.py。原生作业串行使用native_delta_guard.py，启动可用内存≥2GiB；仅清理已识别的相关进程工作集。包内保留依赖路径和哈希，完整审计依赖原工作区；标准3D库依赖KiCad10，本版未生成全装配3D模型。

原厂资料：
- [B601 DM说明](https://wiki.seeedstudio.com/rebot_b601_dm_getting_started/)
- [THN30WIR](https://www.tracopower.com/products/thn30wir.pdf)
- [TPS3760](https://www.ti.com/lit/ds/symlink/tps3760.pdf)
- [LT3013](https://www.analog.com/media/en/technical-documentation/data-sheets/3013fe.pdf)
- [STPS3H100 Rev3](https://www.st.com/resource/en/datasheet/stps3h100.pdf)（公开PDF已核读；本机原PDF下载超时，包内明确为资料摘记）
- [OreSat子系统](https://www.oresat.org/technologies/cubesat-subsystems)
- [P60 PDU-200](https://gomspace.com/UserFiles/Subsystems/datasheet/gs-ds-nanopower-p60-pdu200-26.pdf)
'''
    (C/'README_V35.md').write_text(md,encoding='utf-8')
    nextrows=''.join('<tr>'+''.join('<td>'+html.escape(str(s[k]))+'</td>' for k in ['order','domain','actual_change','outputs','acceptance','external_dependency'])+'</tr>' for s in nextsteps)
    bomrows=''.join('<tr>'+''.join('<td>'+html.escape(str(r[k]))+'</td>' for k in ['ref','value','MPN','placement_scope'])+'</tr>' for r in rows)
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>WP10 V35 整机进度与电源时序板</title><style>
body{margin:0;background:#edf2f5;color:#172e3c;font:16px/1.75 system-ui,"Microsoft Yahei",sans-serif}main{max-width:1200px;margin:auto;padding:30px 22px}header{background:#123447;color:#fff;padding:28px;border-radius:14px}h1{font-size:30px;margin:8px 0}h2{font-size:22px}section,.card{background:white;border-radius:12px;padding:22px;margin-top:18px}.cards{display:flex;gap:14px;flex-wrap:wrap}.card{flex:1;min-width:180px}.num{font-weight:700;font-size:30px;color:#106477}.note{background:#fff0d6;border-left:4px solid #b27821;padding:16px;margin-top:18px}.flow{background:#e9f4f8;padding:14px;border-radius:8px;margin:10px 0}a,button{color:#08678b}button{background:white;border:1px solid #9bb4c1;border-radius:6px;padding:9px 14px;margin:4px;cursor:pointer}button[aria-pressed=true]{background:#08678b;color:white}img{width:100%;height:auto;border:1px solid #cedade}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;vertical-align:top;padding:10px;border-bottom:1px solid #dce3e8}th{background:#e9f3f7;position:sticky;top:0}.scroll{overflow:auto;max-height:560px}td{min-width:100px}small{color:#586f7b}.links a{display:inline-block;margin:5px 18px 5px 0}input{padding:10px;border:1px solid #9db4c0;width:min(90%,460px);border-radius:6px}li{margin:7px 0}</style>
<main><header><small style="color:#a3dbea">WP10 · V35 · 2026-09-14</small><h1>整机进度与辅助电源时序 PCB</h1><p>系统详细设计与子系统局部验证阶段。活动电气 V35 · 几何 V30/V28 · 输入基线 V31</p></header>
<div class="note"><b>全部电气选型、完整机械装配、真实推进任务能力尚未完成。</b> 本版可审阅源文件；未制造、未接电、未进行实物驱动或推进试验。</div>
<div class="cards"><div class="card"><div class="num">237 / 767</div>系统位号 / 针脚网络记录</div><div class="card"><div class="num">15页 · ERC 0</div>辅助 PCB DRC 0；主 PCB 继承字节相同 V34 检查</div><div class="card"><div class="num">96 + 8</div>独立复算工况 / 程序负控</div></div>
<section><h2>三条设计主线到哪一步</h2><div class="scroll"><table><tr><th>领域</th><th>已有成果</th><th>仍需完成</th></tr>
<tr><td>机械构型</td><td>873实例原生宿主、三种固定姿态；974实例源计划；局部模块实体</td><td>新模块回装、真实收拢、配合与连续运动、统一物性、热结构与净空。parking不是发射收拢。</td></tr>
<tr><td>电气</td><td>同版本系统原理图、主输入板与辅助保护/时序板；条件电流和热量账</td><td>STOP/回生等剩余PCB，联合启动与失电恢复，完整能源周期、整机线束与接插件验证</td></tr>
<tr><td>推进</td><td>商业整模块复用候选、目录资源筛查、接口与合成阵列反例</td><td>同修订真实喷口/脉冲/并发/羽流/指令ICD，当前COM、六自由度任务能力与能源预算</td></tr></table></div><p>没有可信的整体完成百分比。原37行闭环表保持，局部检查通过不会自动升级整机状态。</p></section>
<section><h2>这块 PCB 的作用</h2><div class="flow">主支路：受保护电池 → 主输入保护／预充板 → CHB → 接触器 → 机械臂</div><div class="flow">辅助支路：同一电池 → F202 → 辅助保护板 → THN隔离电源 → STOP控制<br><b>本轮新增：</b> TPS3760监控输入电压＋独立6V偏置＋THN远端启动资格</div><p>辅助板控制低压启动条件、限制辅助支路故障电流。它独立于主功率开关，共用电池；不直接供应机械臂360W，也不吸收制动能量。远端线开路使THN默认开启，本板不能计作独立停止屏障。</p><p>板外形60×70×1.6mm，26电气器件、6安装孔；新器件最高标称18mm。原功率走线与过孔保留，新增30mA支路采用分配场景，尚未提取其分布阻抗或完成整舱安装。</p></section>
<section><h2>直接查看</h2><div><button data-img="AUX_PCB_FRONT.png" aria-pressed="true">辅助板正面</button><button data-img="AUX_PCB_BACK.png" aria-pressed="false">背面铜区</button><button data-img="AUX_SEQUENCE.png" aria-pressed="false">新增时序原理图</button></div><img id="design" src="../results/aux_v35/AUX_PCB_FRONT.png" alt="原生KiCad辅助保护和时序板导出">
<p class="links"><a href="../results/aux_v35/WP10_SYSTEM_V35.pdf">15页系统原理图PDF（第13页为新时序）</a><a href="../ecad/revisions/v35/wp10_system.kicad_sch">系统原理图源</a><a href="../ecad/revisions/v35/wp10_aux_protection.kicad_pcb">辅助PCB源</a><a href="../ecad/revisions/v35/wp10_main_input.kicad_pcb">主输入PCB源</a><a href="WP10_V35_ECAD_CANDIDATE.zip">设计与证据包</a></p></section>
<section><h2>选型已落实，适用范围仍需验证</h2><p>新增U208 TPS3760A015DYYR、U209 LT3013、两只STPS3H100U及相应分压、延迟、电源和连接器器件。R231已按高温二极管反漏修正为1.8kΩ。当前释放阈值约17.323–17.960V；冷态RC部分约97.28–167.46ms。THN内部输入电容和启动电流尚未取得，不能据此宣布启动成功。</p><p>系统237个位号包括设备端口和电路细节；55项有明确MPN字段，其他型号可能写在Value。该数量不等于选型完整度，也不是可直接采购的237件PCB清单。</p><p><a href="../ecad/revisions/v35/SYSTEM_BOM.csv">系统BOM</a> · <a href="../ecad/revisions/v35/BOM_DELTA_V35.csv">本轮15项新增</a> · <a href="../ecad/revisions/v35/AUX_HARNESS_INTERFACE.csv">线束端点</a> · <a href="../ecad/revisions/v35/AUX_MATING_BOM.csv">配套连接器</a></p><input id="filter" aria-label="筛选BOM" placeholder="搜索位号、型号或所在PCB"><div class="scroll"><table id="bom"><thead><tr><th>位号</th><th>值／型号</th><th>MPN字段</th><th>实体PCB范围</th></tr></thead><tbody>'''+bomrows+'''</tbody></table></div></section>
<section><h2>为何仍需适配，成熟案例怎样复用</h2><p><a href="https://wiki.seeedstudio.com/rebot_b601_dm_getting_started/">B601 DM</a>的机械、驱动和软件继续复用；<a href="https://www.oresat.org/technologies/cubesat-subsystems">OreSat</a>用于背板、供电监控等架构参考。我们并不要求所有电路自研。</p><p><a href="https://gomspace.com/UserFiles/Subsystems/datasheet/gs-ds-nanopower-p60-pdu200-26.pdf">P60 PDU-200</a>公开单通道2A，不能直接承担本机24V/15A筛查供电。完整案例只有在母线、峰值功率、失电行为、热边界和受控接口匹配后，才可直接替代对应模块；当前没有取得与本机同构的完整可制造设计。</p></section>
<section><h2>当前硬问题与证据范围</h2><p>96个假设导通工作点中，84个满足释放电压，12个不能获得新释放；这不是硬件成功率。8项人为错误输入均被检测，另保留180个充电包络和20个CTR残压情景。30mA仅为设计分配，完整联合时域、元件温升及短掉电STOP未验证。</p><p>V33热板试验仍拒绝：计入板端热量后CHB约105.837–107.214°C，超105°C；三处安装短名单分别8/7/7处交叠。下一步需要实际重排和完整热出口。当前全机质量/COM/惯量仍未绑定，不能拿旧总质量填空。</p><p class="links"><a href="../results/aux_v35/VERIFICATION.json">验证与忽略规则</a><a href="../results/aux_v35/CALCULATIONS.json">条件计算</a><a href="../results/aux_v35/INDEPENDENT_REVIEW_DISPOSITION.json">独立审阅整改</a><a href="REVIEW_V33.html">保留的散热/布局负结果</a></p><small>ERC4类、DRC5类忽略项逐条披露；全系统PCB一致性、制造及实物检查未计入通过。</small></section>
<section><h2>下一步具体执行与完成标准</h2><p>推进受控资料核实可与内部电气和机械改件并行；其余工作按接口依赖推进。</p><div class="scroll"><table><tr><th>顺序</th><th>工作</th><th>实际修改</th><th>交付物</th><th>验收标准</th><th>外部／实测依赖</th></tr>'''+nextrows+'''</table></div><p class="links"><a href="NEXT_ENGINEERING_ACTIONS_V35.csv">执行清单CSV</a><a href="SYSTEM_MATURITY_V35.json">整机进度证据</a><a href="DELIVERY_STATUS_V35.json">当前机器状态</a><a href="README_V35.md">详细说明与原厂依据</a></p></section>
<script>for(const b of document.querySelectorAll('[data-img]'))b.onclick=()=>{document.querySelector('#design').src='../results/aux_v35/'+b.dataset.img;for(const t of document.querySelectorAll('[data-img]'))t.setAttribute('aria-pressed',String(t===b));};document.querySelector('#filter').oninput=e=>{const q=e.target.value.toLowerCase();for(const r of document.querySelectorAll('#bom tbody tr'))r.hidden=!r.textContent.toLowerCase().includes(q);};</script></main></html>'''
    (C/'REVIEW_V35.html').write_text(page,encoding='utf-8')
    files=designfiles|{p for p in R.rglob('*') if p.is_file() and p.suffix not in ['.kicad_prl','.lck']}|set(A.joinpath('tools').glob('*v35.py'))
    files|={C/name for name in ['README_V35.md','REVIEW_V35.html','CANDIDATE_V35.json','DELIVERY_STATUS_V35.json','SOURCE_ACTIVATION_V35.json','SYSTEM_MATURITY_V35.json','NEXT_ENGINEERING_ACTIONS_V35.csv']}
    files|={A/'tools/erc_source_contract.py',A/'tools/shared_battery_path.py',A/'tools/native_delta_guard.py',C/'CANDIDATE_V34.json'}
    files|=set(A.joinpath('logs').glob('native_delta_v35*.run.json'))
    # Include direct calculation/evidence dependencies under the implementation root.
    for bundle in [cal['source_bindings'],v['source_bindings'],maturity['source_bindings']]:
        files|={Path(p) for p in bundle if Path(p).is_relative_to(A)}
    # Public component sources already named by selection are included when present.
    for s in sel.values():
        if s.get('source_file') and (A/s['source_file']).is_file():files.add(A/s['source_file'])
    for pcb in D.glob('*.kicad_pcb'):
        for rel in re.findall(r'\(model "\$\{KIPRJMOD\}/([^"\n]+)"',pcb.read_text()):
            p=(D/rel).resolve()
            if p.is_file() and p.is_relative_to(A):files.add(p)
    records=[dict(file=p.relative_to(A).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(files)]
    manifest=C/'PACKAGE_MANIFEST_V35.json';dump(manifest,records);files.add(manifest)
    package=C/'WP10_V35_ECAD_CANDIDATE.zip'
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(files):z.write(p,p.relative_to(A).as_posix())
    with zipfile.ZipFile(package) as z:
        assert z.testzip() is None
        assert all(hashlib.sha256(z.read(row['file'])).hexdigest()==row['sha256'] for row in records)
    dump(C/'PACKAGE_VERIFICATION_V35.json',dict(files=len(files),bytes=package.stat().st_size,sha256=sha(package),zip_integrity=True,manifest_hashes_match=True,
      portable_ECAD_and_review=True,full_recalculation_audit_requires_original_workspace=True))
    pointer=read(A/'CURRENT_WORKING_CANDIDATE.json');pointer.update(revision='V35',entry='coupled_closure/REVIEW_V35.html',candidate='coupled_closure/CANDIDATE_V35.json',
      source_activation='coupled_closure/SOURCE_ACTIVATION_V35.json',latest_review='coupled_closure/REVIEW_V35.html',latest_experiment='coupled_closure/DELIVERY_STATUS_V35.json',whole_design_complete=False)
    dump(A/'CURRENT_WORKING_CANDIDATE.json',pointer)
    print(json.dumps(dict(entry=str(C/'REVIEW_V35.html'),package=str(package),files=len(files),bytes=package.stat().st_size,coverage=coverage,whole_design_complete=False)))
if __name__=='__main__':main()
