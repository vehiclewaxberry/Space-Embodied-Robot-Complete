"""Publish the reviewed V34 delta within the same WP10 candidate and source tree."""
from pathlib import Path
import csv,copy,datetime,hashlib,html,json,re,shutil,zipfile,xml.etree.ElementTree as ET
A=Path(__file__).resolve().parents[1];D=A/'ecad/revisions/v34';R=A/'results/aux_v34';C=A/'coupled_closure'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def csvwrite(p,fields,rows):
    with p.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def main():
    v=read(R/'VERIFICATION.json');assert v['scoped_verification_passed']
    c=read(R/'CALCULATIONS.json');n=read(R/'NATIVE_AUDIT.json');con=read(R/'CONNECTOR_INTERFACE.json')
    assert all(sha(Path(p))==h for p,h in c['source_bindings'].items())
    x=ET.parse(D/'wp10_system.xml').getroot();rows=[]
    for co in x.findall('./components/comp'):
        props={f.get('name'):f.text for f in co.findall('./fields/field')}
        rows.append(dict(ref=co.get('ref'),value=co.findtext('value'),footprint=co.findtext('footprint') or '',
          sheet=co.find('sheetpath').get('names'),source_revision='V34',MPN=props.get('MPN',''),
          manufacturer=props.get('Manufacturer',''),datasheet=co.findtext('datasheet') or ''))
    csvwrite(D/'SYSTEM_BOM.csv',list(rows[0]),rows)
    newrefs=set(n['added_refs'])|{'R202'};delta=[r for r in rows if r['ref'] in newrefs]
    csvwrite(D/'BOM_DELTA_V34.csv',list(rows[0]),delta)
    pins=[dict(net=net.get('name'),ref=z.get('ref'),pin=z.get('pin'),pinfunction=z.get('pinfunction',''),pintype=z.get('pintype','')) for net in x.findall('./nets/net') for z in net.findall('node')]
    assert len(rows)==222 and len(pins)==714
    csvwrite(D/'PIN_NET_TABLE.csv',list(pins[0]),pins)
    harness=[
      dict(port='J208.1',net='WP10_AUX_FUSED',remote='F202.2',role='Auxiliary protected-pack positive input'),
      dict(port='J208.2',net='WP10_INPUT_RETURN',remote='Primary battery return node',role='Input return'),
      dict(port='J209.1',net='WP10_AUX_LIMITED',remote='U202.1',role='THN positive input after eFuse'),
      dict(port='J209.2',net='WP10_INPUT_RETURN',remote='U202.2',role='THN primary-side return'),
      dict(port='J210.1',net='WP10_AUX_RESET',remote='Local dry short to J210.2 only',role='Local manual reset test pad; no external logic'),
      dict(port='J210.2',net='WP10_AUX_PROTECT_RTN',remote='U207.8 and EP17',role='Floating IC RTN; never external primary GND short')]
    csvwrite(D/'AUX_HARNESS_INTERFACE.csv',list(harness[0]),harness)
    csvwrite(D/'AUX_MATING_BOM.csv',['item','MPN','quantity','selection_status'],[
      dict(item='J208/J209 mating receptacle',MPN='430250200',quantity=2,selection_status='Public family match; installation not verified'),
      dict(item='Female tin crimp terminal',MPN='430300007',quantity=4,selection_status='20 AWG candidate; insulation OD <=1.85mm; actual wire MPN and cut length open')])
    stage=dict(revision='V34',time=datetime.datetime.now().astimezone().isoformat(),
      status='ECAD_AND_CONDITIONAL_CALCULATION_CANDIDATE_VERIFIED',same_WP10_candidate=True,
      electrical_refs=222,pin_records=714,schematic_pages=14,main_PCB_electrical_footprints=43,
      auxiliary_PCB_electrical_footprints=11,auxiliary_board_only_mounting_holes=4,
      aux_PCB_dimensions_mm=[60,40,1.6],whole_design_complete=False,manufacturing_release=False,
      hardware_tests=0,propulsion_release=False,board_3D_or_native_whole_assembly_newly_integrated=False,
      original_873_component_parent_preserved=True,original_99_ref_lineage_preserved=True,
      original_37_row_matrix_preserved=v['prior_parent_files_unchanged'],
      geometry_revision='V30/V28',rejected_V33_trial_still_rejected=True,
      verification='results/aux_v34/VERIFICATION.json',calculation='results/aux_v34/CALCULATIONS.json',
      approved_scope='Same-version schematic net connectivity, two-board DRC under recorded rules, explicit algebraic scenarios and mutation checks.',
      open_items=[
        'Joint auxiliary-eFuse/THN/STOP cold startup, shutdown and manual re-arm; THN input capacitor/inrush still unbound.',
        'Fast fault overshoot, BMS/fuse/TVS/connector coordination and maximum fault-to-latch time.',
        'Continuous CHB/TIM/carrier/radiator thermal path and accepted host installation; V33 negative result retained.',
        'New auxiliary board host placement, harness cuts and actual wire/termination process; R202 CAD height not newly integrated.',
        'Measured B601 electrical load, stop/regen energy, current whole-body material and joint inertia.',
        'Controlled propulsion ICD and mission capability, charging/replenishment and whole-spacecraft native assembly.',
        'Remaining STOP/regen/detail pages are not all routed physical PCBs; full-system PCB parity not claimed.'])
    dump(C/'DELIVERY_STATUS_V34.json',stage)
    old=read(C/'CANDIDATE_V32.json');new=copy.deepcopy(old)
    new.update(schema='WP10_ACTIVE_DESIGN_DELTA_V34',revision='V34',parent_candidate=str(C/'CANDIDATE_V32.json'),parent_sha256=sha(C/'CANDIDATE_V32.json'),
      electrical_refs=222,pin_records=714,electrical_model_consumer='tools/aux_operating_point_v34.py',
      electrical_model_file=str(R/'ELECTRICAL_CANDIDATE.json'),inherited_nonclosures=stage['open_items'])
    new['active_sources']={k:str(D/name) for k,name in dict(system_schematic='wp10_system.kicad_sch',system_netlist='wp10_system.xml',
      main_input_PCB='wp10_main_input.kicad_pcb',auxiliary_protection_PCB='wp10_aux_protection.kicad_pcb',BOM='SYSTEM_BOM.csv',pin_net_table='PIN_NET_TABLE.csv',aux_harness='AUX_HARNESS_INTERFACE.csv').items()}
    new['active_sources'].update(calculation=str(R/'CALCULATIONS.json'),verification=str(R/'VERIFICATION.json'))
    new['scoped_acceptance']=dict(system_ERC_errors=0,system_ERC_warnings=0,main_input_DRC_violations=0,main_input_DRC_unconnected=0,
      auxiliary_DRC_violations=0,auxiliary_DRC_unconnected=0,saved_operating_points=96,calculation_negative_controls=7,
      native_shorted_copy_rejected=True,ignored_rules_disclosed=True,full_system_PCB_parity_checked=False)
    designfiles=[p for p in D.rglob('*') if p.is_file() and p.suffix not in ['.kicad_prl','.lck']]
    new['source_lock']={str(p):sha(p) for p in designfiles+[R/'CALCULATIONS.json',R/'ELECTRICAL_CANDIDATE.json',R/'VERIFICATION.json',R/'CONNECTOR_INTERFACE.json']}
    dump(C/'CANDIDATE_V34.json',new)
    dump(C/'SOURCE_ACTIVATION_V34.json',dict(revision='V34',candidate_sha256=sha(C/'CANDIDATE_V34.json'),sources_activated=new['active_sources'],
      native_whole_assembly_updated=False,geometry_revision='V30',manufacturing_release=False,whole_design_complete=False))
    review='''# WP10 V34 · 电源接口与辅助保护 PCB

2026-09-14。本版完成同版本 ECAD 候选，整星机电设计尚未闭环。

本轮新增 60 × 40 mm 双层辅助保护板：F202 后接 TPS26600，再供给 THN 隔离电源和 STOP 控制。它与主 Q201 开关支路分开，但共用电池；不是冗余电池电源。主输入板承担 LM5069 预充/限流及相关启动接口，本轮把主采样电阻 R202 改为 0.5 mΩ，总采样电阻 2.5 mΩ。负载侧回生吸收仍在既有独立设计链中，不由这块辅助板吸收电机制动能量。

已完成 14 页整机 ERC（0 错误、0 警告），主板 43 个电气封装及辅助板 11 个电气封装分别 DRC 0 违规、0 未连接。辅助板另有 4 个非电气安装孔、9 个 RTN 散热过孔、与主回流隔离的背面铜区。电气位号由 211 增至 222，针脚网络由 677 增至 714；原位号仅 U202.1 网络和 R202 规格变化。原 873 组件父本、99 位号谱系及 37 行闭环表保持。

96 个保存工况完成独立 KCL/KVL/功率/器件分项热量核对；7 个旧字段/NaN/热量错分负控被检测。RTN–GND 短接副本触发 4 条原生 DRC 违规，活动板未改变。忽略项逐条见 VERIFICATION.json：ERC 4 类，DRC 5 类。上述检查不是所有规则、所有板或硬件性能的合格证。

主限流条件范围约 18.99–25.14 A，辅助约 2.103–2.358 A；限流平台相加约 27.504 A，仅在所列器件参数迁移条件下成立，不能作为瞬态 30 A 上界。360 W 机械臂筛查需求未降低。32 个配对工况仍为 16 个 UVLO 阻断、13 个条件保持、3 个角点相关。

384 个主启动端点场景中，192 冷态 UVLO 关闭、16 在预充期间 UVLO、176 退出限流区。15.531 ms 是完成子集的最差调节时间；28.2 ms 定时器最小值扣除 1.5 倍项目分配后余 4.904 ms。模型假设辅助保护已经导通，不是联合冷启动证明。THN 在 8/9 V 开始吸取满辅助恒功率时仍有负的充电电流余量反例。

新增铜阻按原生走线长度/宽度、35 µm 铜、100°C、20 µm 过孔镀铜假设分项计入；不视作实测阻抗。Molex 配套壳体 430250200、端子 430300007 已选为候选，20 AWG、绝缘外径须≤1.85 mm；线材具体料号、裁线长度和压接过程仍待整机布置绑定。依 PS-43045 Rev R，四个配对接点和四个压接点采用初始合计 0.060 Ω，以及规定应力试验变化量转移后的 0.140 Ω 场景。不得把这些表格条件扩展成空间环境保证。

为什么继续复用成熟方案：B601 DM 的结构、电机及软件沿用开源项目；卫星低功耗电源/背板参考 OreSat 与 P60。本项目新增的仅是现有模块之间的高功率保护和停止接口。GomSpace PDU-200 公布单通道 2 A，与本项目保留的 24 V/15 A 筛查工况不匹配；OreSat 的 1U–3U、7.2 V 电池卡也不能不经重设计就移植为本机高功率系统。GITAI S1 的 ISS 舱内机械臂演示可以参考任务与验证方法，其公开页面不是本项目 12U 自由漂浮整机的完整制造设计。

原厂/项目依据：
- [B601 开源项目](https://github.com/Seeed-Projects/reBot-DevArm/blob/main/README.md)
- [GomSpace P60 PDU-200](https://gomspace.com/UserFiles/Subsystems/datasheet/gs-ds-nanopower-p60-pdu200-26.pdf)
- [OreSat 子系统](https://www.oresat.org/technologies/cubesat-subsystems)
- [GITAI S1 ISS 演示](https://gitai.tech/2021/10/28/iss-tech-demo-ja/)
- [TI TPS2660](https://www.ti.com/lit/ds/symlink/tps2660.pdf)
- [Vishay WSLP2726](https://www.vishay.com/docs/30179/wslp2726.pdf)
- [Molex PS-43045](https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/productspecificationpdf/430/43045/PS-43045-001.pdf?inline=)

下一项应解决辅助电源/STOP 的联合冷启动与复位，再开展剩余 STOP/回生板布线、热通路及整舱集成。FLT/IMON 本版未接遥测；J210 只是相对于 RTN 的本地短接复位测试点。安装位置、热边界、制动能量和推进受控接口仍开放。未制造、未接电、未驱动实物，未宣布制造或飞行放行。

KiCad 打开 ecad/revisions/v34/wp10_system.kicad_sch 查看整机层次，第 14 页是辅助板。PCB 分别打开 wp10_main_input.kicad_pcb 与 wp10_aux_protection.kicad_pcb；MCP 与 GUI 不是实时同步，重新载入已保存文件后查看。标准 3D 模型依赖本机 KiCad 10 模型库；本次并未生成完整实体或更新整机 CAD。包内 PDF/PNG/CSV 可直接查看，复算使用原工作区及记录的运行时路径。
'''
    (C/'README_V34.md').write_text(review,encoding='utf-8')
    body=''.join('<tr>'+''.join('<td>'+html.escape(str(r[k]))+'</td>' for k in ['ref','value','MPN','footprint'])+'</tr>' for r in delta)
    openrows=''.join('<li>'+html.escape(s)+'</li>' for s in stage['open_items'])
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>WP10 V34 电源保护 PCB</title>
<style>body{margin:0;background:#edf2f5;color:#142734;font:16px/1.7 system-ui,"Microsoft Yahei",sans-serif}main{max-width:1120px;margin:auto;padding:32px 24px}header{background:#132e43;color:white;padding:28px;border-radius:16px}h1{font-size:30px;margin:8px 0}h2{font-size:21px}.cards{display:flex;gap:14px;flex-wrap:wrap}.card,section{background:white;padding:22px;border-radius:12px;margin-top:20px}.card{flex:1;min-width:180px}.num{font-size:32px;font-weight:700;color:#126078}.note{background:#fff1d7;padding:14px;border-left:4px solid #bc8319}.flow{background:#ecf6fb;padding:14px;margin:12px 0;border-radius:8px}button,a{color:#075a85}button{border:1px solid #a7bdc9;background:white;padding:9px 18px;border-radius:7px;cursor:pointer;margin:5px}button[aria-pressed="true"]{background:#075a85;color:white}img{width:100%;height:auto;border:1px solid #cad5da}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:9px;border-bottom:1px solid #ddd;text-align:left;word-break:break-word}.scroll{overflow:auto}small{color:#586c78}.links a{display:inline-block;margin-right:20px}li{margin:8px 0}</style>
<main><header><small style="color:#9fd7ee">WP10 · V34 · 2026-09-14</small><h1>电源接口与辅助保护 PCB</h1><p>已验证的 ECAD 候选 · 原理图、两块板与条件计算处于同一版本</p></header>
<div class="note">整星机电闭环仍开放。此页不构成制造、接电或飞行放行。</div>
<div class="cards"><div class="card"><div class="num">222 / 714</div>整机位号 / 针脚网络记录</div><div class="card"><div class="num">14 页 · ERC 0</div>主板与辅助板 DRC 各 0 违规 / 0 未连接</div><div class="card"><div class="num">96 + 8</div>保存工况核对 / 7 个计算负控 + 1 个原生短接负控</div></div>
<section><h2>这两块板分别做什么</h2><div class="flow">主支路：受保护电池 → 输入保护与预充板 → CHB 转换模块 → 接触器与机械臂</div><div class="flow">辅助支路：同一电池 → F202 → <b>本轮 TPS26600 辅助保护板</b> → THN 隔离电源 → STOP 控制</div><p>辅助保护板限制辅助支路故障电流、控制输出上升，并提供 UV/OV/反向输入保护和过流后热故障锁存配置。它独立于主功率开关，共用电池；不会承担机械臂 360 W 功率，也不吸收电机制动能量。</p><p>辅助板 60 × 40 × 1.6 mm，11 个电气器件、4 个安装孔、9 个散热过孔。RTN 铜区与主回流保持隔离。本地复位测试点不接外部逻辑电压。</p></section>
<section><h2>直接查看设计</h2><div id="tabs"><button aria-pressed="true" data-img="AUX_PCB_FRONT.png">辅助板正面</button><button aria-pressed="false" data-img="AUX_PCB_BACK.png">背面铜区</button><button aria-pressed="false" data-img="AUX_SCHEMATIC.png">辅助原理图</button></div><img id="design" alt="原生 KiCad 导出设计图" src="../results/aux_v34/AUX_PCB_FRONT.png"><p class="links"><a href="../results/aux_v34/WP10_SYSTEM_V34.pdf">整机 14 页原理图 PDF</a><a href="../ecad/revisions/v34/wp10_aux_protection.kicad_pcb">辅助 PCB 源</a><a href="../ecad/revisions/v34/wp10_main_input.kicad_pcb">主输入 PCB 源</a><a href="WP10_V34_ECAD_CANDIDATE.zip">同版本源与证据包</a></p></section>
<section><h2>成熟方案应继续复用</h2><p>B601 DM 沿用公开结构、电机与软件；OreSat 可复用背板、供电监测和子系统设计思路；P60 可承担匹配其额定范围的卫星低功耗配电。新增板用于处理现有模块之间的保护与接口差异。</p><p><a href="https://gomspace.com/UserFiles/Subsystems/datasheet/gs-ds-nanopower-p60-pdu200-26.pdf">PDU-200</a> 公布单通道 2 A，不能直接等同于本项目 24 V / 15 A 的机械臂筛查供电。<a href="https://www.oresat.org/technologies/cubesat-subsystems">OreSat</a> 的 1U–3U 平台与 7.2 V 电池卡也需重新匹配功率和接口。<a href="https://gitai.tech/2021/10/28/iss-tech-demo-ja/">GITAI S1</a> 的 ISS 舱内演示可参考验证方法，其公开页面未提供本项目同构型整机的可直接移植完整设计。</p><p>采购或复用的成熟模块若能满足同样负载、故障行为和受控接口，可替换对应适配功能；本项目没有要求所有电路自研。</p></section>
<section><h2>本轮真实源修改</h2><div class="scroll"><table><thead><tr><th>位号</th><th>值/型号</th><th>MPN</th><th>封装</th></tr></thead><tbody>'''+body+'''</tbody></table></div><p><a href="../ecad/revisions/v34/SYSTEM_BOM.csv">222 位号 BOM</a> · <a href="../ecad/revisions/v34/PIN_NET_TABLE.csv">714 针脚表</a> · <a href="../ecad/revisions/v34/AUX_HARNESS_INTERFACE.csv">线束端点</a> · <a href="../ecad/revisions/v34/AUX_MATING_BOM.csv">配套连接器</a></p></section>
<section><h2>已证明的范围</h2><p>32 个配对工况的主支路分类未变：16 个 UVLO 阻断、13 个条件保持、3 个角点相关。增加实际板铜及连接器/压接电阻场景后仍保留 360 W 需求。限流平台合计约 27.504 A，属于参数表条件迁移下的计算，不能解释成瞬态电池电流上限。</p><p>384 个主启动端点中，176 个退出限流区；192 个冷态 UVLO 关闭，16 个预充中 UVLO。完成子集最差调节时间约 15.531 ms。辅助 eFuse/THN 联合冷启动尚未证明，8/9 V 满辅助负载仍有代数负余量反例。</p><p><a href="../results/aux_v34/VERIFICATION.json">检查明细与忽略项</a> · <a href="../results/aux_v34/CALCULATIONS.json">完整计算</a> · <a href="../results/aux_v34/counterexamples/SHORT_DRC.json">短接反例</a> · <a href="README_V34.md">完整说明与原厂依据</a></p><small>ERC 沿用 4 类忽略项，DRC 5 类，逐项记录；全系统 PCB 一致性与实物检查不在本次通过范围。</small></section>
<section><h2>接下来仍需关闭</h2><ul>'''+openrows+'''</ul><p><a href="DELIVERY_STATUS_V34.json">当前机器状态</a> · <a href="REVIEW_V33.html">保留的 V33 散热/布局负结果</a></p></section>
<script>for(const b of document.querySelectorAll('[data-img]'))b.onclick=()=>{document.querySelector('#design').src='../results/aux_v34/'+b.dataset.img;for(const t of document.querySelectorAll('[data-img]'))t.setAttribute('aria-pressed',String(t===b));};</script></main></html>'''
    (C/'REVIEW_V34.html').write_text(page,encoding='utf-8')
    review_note={'reviewer':'readonly hardware-reviewer /root/v34_readonly_review','status':'ACCEPT_WITH_DECLARED_SCOPE',
      'resolved':['Stale saved power and heat fields','Missing explicit new path resistance','IQ split not varied with contact sensitivity','NaN fail-open','Same-sum heat misattribution'],
      'scope':'Source consistency, algebraic model and ECAD checks. Final connector resistance expanded after review to public initial/stress scenarios; same equations reverified.',
      'not_accepted':['Joint cold startup','Transient protection coordination','Thermal qualification','Whole-system completion']}
    dump(R/'INDEPENDENT_REVIEW_DISPOSITION.json',review_note)
    pointer=read(A/'CURRENT_WORKING_CANDIDATE.json');pointer.update(revision='V34',entry='coupled_closure/REVIEW_V34.html',candidate='coupled_closure/CANDIDATE_V34.json',
      source_activation='coupled_closure/SOURCE_ACTIVATION_V34.json',latest_review='coupled_closure/REVIEW_V34.html',latest_experiment='coupled_closure/DELIVERY_STATUS_V34.json',whole_design_complete=False)
    dump(A/'CURRENT_WORKING_CANDIDATE.json',pointer)
    for name in ['wslp2726.pdf','tnpw_e3_20260410_v24.pdf']:
        shutil.copy2(A/'sources'/name,R/'sources'/name)
    files=set(designfiles)|{p for p in R.rglob('*') if p.is_file() and not p.name.endswith('.kicad_prl')}|set(A.joinpath('tools').glob('*v34.py'))
    files|={C/name for name in ['README_V34.md','REVIEW_V34.html','CANDIDATE_V34.json','DELIVERY_STATUS_V34.json','SOURCE_ACTIVATION_V34.json']}
    files|={A/'CURRENT_WORKING_CANDIDATE.json',A/'tools/shared_battery_path.py',A/'tools/hotswap_transient_model_v23.py',A/'tools/erc_source_contract.py',A/'tools/native_delta_guard.py',A/'coupled_closure/coupled_adapter.py',A/'coupled_closure/CANDIDATE_V30.json',A/'coupled_closure/CANDIDATE_V32.json',A/'power/POWER_LOOP_CALCULATIONS.json',A/'power/SHARED_BATTERY_PATH_DEFINITION.json'}
    # Preserve existing project-relative 3D references; standard KiCad libraries remain runtime dependencies.
    for pcb in D.glob('*.kicad_pcb'):
        for rel in re.findall(r'\(model "\$\{KIPRJMOD\}/([^"\n]+)"',pcb.read_text()):
            q=(D/rel).resolve()
            if q.is_file() and q.is_relative_to(A):files.add(q)
    files|=set(A.joinpath('logs').glob('native_delta_v34*.run.json'))
    records=[dict(file=str(p.relative_to(A)).replace('\\','/'),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(files)]
    manifest=C/'PACKAGE_MANIFEST_V34.json';dump(manifest,records);files.add(manifest)
    package=C/'WP10_V34_ECAD_CANDIDATE.zip'
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(files):z.write(p,str(p.relative_to(A)).replace('\\','/'))
    with zipfile.ZipFile(package) as z:
        assert z.testzip() is None
        assert all(hashlib.sha256(z.read(row['file'])).hexdigest()==row['sha256'] for row in records)
    dump(C/'PACKAGE_VERIFICATION_V34.json',dict(files=len(files),bytes=package.stat().st_size,sha256=sha(package),zip_integrity=True,manifest_hashes_match=True))
    print(json.dumps(dict(entry=str(C/'REVIEW_V34.html'),package=str(package),files=len(files),bytes=package.stat().st_size,whole_design_complete=False)))
if __name__=='__main__':main()
