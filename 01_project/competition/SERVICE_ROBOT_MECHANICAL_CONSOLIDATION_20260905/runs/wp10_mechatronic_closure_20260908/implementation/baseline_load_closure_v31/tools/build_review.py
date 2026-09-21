"""Publish a self-contained review of V31 inputs and actually computed scenarios."""
from pathlib import Path
import csv
import html
import json
from datetime import datetime
from power_phase_model import P,read

def write(name,obj):
    (P/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def main():
    v=read(P/'results/VALIDATION.json')
    if not v['passed']:raise ValueError('VALIDATION_NOT_PASSED')
    points=read(P/'results/STEADY_POWER_TRADE.json')['points']
    ledgers=read(P/'results/PHASE_ENERGY_TRADE.json')['ledgers']
    body=read(P/'mechanical/BODY_PARAMETER_CARD.json')
    baseline=read(P/'mechanical/MECHANICAL_BASELINE.json')
    memory=read(P/'results/MEMORY_CLEANUP.json')
    rows=[r for r in points if r['pack_V']==25.2 and r['shared_R_ohm']==.01 and r['eta_main']==.85]
    actions=[
      dict(id='V31-M01',object='B601 DM质量/修订',status='OPEN_SOURCE_CONFLICT',
           source='mechanical/BODY_PARAMETER_CARD.json',
           change='按实际电机修订与零件组成核对公开URDF连杆质量和整臂参考；逐link补入有来源的物性，不按比例放大。',
           acceptance='同一修订的完整质量所有者、COM、惯量与轴系一致；2.74448/4.5差异有逐项解释。'),
      dict(id='V31-E01',object='DM电气参数与负载谱',status='OPEN_AS_BUILT_INPUT',
           source='electrical/ARM_ELECTRICAL_PARAMETERS.json',
           change='核对4340P实际修订；从独立母线和关节记录识别待机/保持/运动/停止分量及温度相关电阻。',
           acceptance='实测波形或有依据区间与采样点绑定；相电流、RMS与母线电流不混用；地面重力项与在轨预测分开。'),
      dict(id='V31-E02',object='主输入PCB Kelvin连接',status='OPEN_KNOWN_DRC',
           source='../results/MAIN_INPUT_DRC_V29.json',
           change='在新ECAD改件身份中处理4项Kelvin连接，保持真实力线与取样支路分离，再复核网表、铜损和DRC。',
           acceptance='同版源图/PCB连接一致且4项实际关闭，不依赖豁免清零。'),
      dict(id='V31-P01',object='停止与加热供电支路',status='OPEN_TRANSIENT_AND_TOPOLOGY',
           source='inputs/REFERENCE_MISSION_V1.json',
           change='绑定停止速度/惯量/回生路径；确定加热器实际供电支路、线路损耗和保护。10秒只是相位预算。',
           acceptance='停止能量与波形可计算；加热电流/压降/保护重求；任务能源不再仅为部分相位小计。'),
      dict(id='V31-T01',object='转换器损耗—散热—舱内布局',status='OPEN_COUPLED_DESIGN',
           source='results/STEADY_POWER_TRADE.csv',
           change='以有来源负载谱校核效率曲线与保护损耗；同版加入翼、铰链、罩体和全部热源，确认辐射可用面后改安装。',
           acceptance='冷热边界与接触热阻声明充分，温限/裕量满足；主输入模块安装位和维护空间通过。'),
      dict(id='V31-A01',object='轮组/推进真实能力',status='OPEN_CONTROLLED_ICD',
           source='actuators/ACTUATOR_CONTRACT.json',
           change='确认轮轴布局、力矩/速度/储存包络与C-POD同修订喷口/并发/脉冲/羽流接口；用当前组合体COM重建分配。',
           acceptance='真实喷口和质心绑定；单向、并发、时窗及资源均评价；合成阵列没有硬件信用。'),
      dict(id='V31-N01',object='统一原生整机回装',status='OPEN_DOWNSTREAM_INTEGRATION',
           source='mechanical/MECHANICAL_BASELINE.json',
           change='将接受的974差量与V30模块按变更清单回装873宿主，同步BOM、线束、物性与姿态，逐项保持来源。',
           acceptance='实际保存/冷重开、依赖及受影响实体/装配/连续路径验证；新增模块不得仅靠计数升级。')]
    write('NEXT_ENGINEERING_ACTIONS.json',dict(actions=actions,scope='Specific open design responsibilities; not completed changes'))
    with (P/'NEXT_ENGINEERING_ACTIONS.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(actions[0]));w.writeheader();w.writerows(actions)
    total=sum(v['module_test_counts'].values())
    status=dict(revision='V31',status='INPUT_BASELINE_AND_CONDITIONAL_CALCULATION_PACKAGE_DELIVERED',
        time=datetime.now().astimezone().isoformat(),geometry_electrical_parent='V30',
        native_host_leaf_instances=873,source_plan_instances=974,source_pose_records=2922,
        uninstalled_V30_occurrences=56,uninstalled_V30_solids=60,
        physical_sources_complete=False,motor_actual_load_spectrum_complete=False,
        steady_power_scenarios=64,phase_energy_scenarios=32,scenario_inputs_are_assumptions=True,
        module_checks=total,electrical_artifact_assertions=7,unique_sources_verified=v['unique_source_files_checked'],
        source_intake_consistent=True,full_design_inputs_complete=False,
        whole_design_complete=False,full_cycle_energy_closed=False,thermal_closed=False,
        whole_harness_complete=False,current_native_assembly_updated=False,
        hardware_io=0,manufacturing_release=False,legacy_gate_modified=False,
        root_review_findings_resolved=True,available_memory_after_cleanup_MiB=memory['after']['available_MiB'],
        review='REVIEW.html',readme='README_ZH.md',next_actions='NEXT_ENGINEERING_ACTIONS.csv')
    write('DELIVERY_STATUS_V31.json',status)
    table='\n'.join(f"| {r['arm_path_W']:.0f} | {r['input_power_W']:.2f} | {r['battery_A']:.2f} | {r['CHB_loss_W']:.2f} | {r['known_nonarm_heat_W']:.2f} |" for r in rows)
    md=f'''# WP10 V31：统一基线、参考任务与负载计算

已交付可运行的输入包与条件计算。本轮没有重建CAD、执行硬件动作或改写旧科学Gate。原生宿主仍为873固定三态；最新完整源计划974；V30局部56子件/60实体仍未回装。

## 已完成的实际工作

- 建立974行实例/物性登记和2922行姿态记录；873→974为删除18、新增119，另29个原ID换源。
- 绑定地面340秒采集参考与5700秒在轨相位参考；后者3600秒日照/2100秒阴影是设计情景，轨道元素和姿态热边界仍未知。
- 建立7轴DM电气参数包、测量模板和母线/相电流分账函数；360W保留为筛查情景，不是已证实的负载上界。
- 分开轮组逐轴储存包络、0.300历史标量和与5.475外部角冲量示例；合成喷口的rank/单向/并发/时窗反例可运行，实际C-POD仍UNKNOWN。
- 执行64个稳态供电点、32个相位预算情景；与V29_COPPER同条件电流/电压/功率回放差为0。

## 对后续改件有用的计算

下表固定电池端25.2V、共享回路0.01Ω、变换效率0.85、铜温100°C及开关导通电阻高温倍率2。功率列是CHB输出侧臂支路分配量，另计1W制动偏置预算；实际机械臂入口前分配损耗未知。辅助支路输入全部作为系统内发热是本次预算假设。

| 臂路径分配 W | 电池输入 W | 电池电流 A | CHB损耗 W | 已计非臂热预算 W |
|---:|---:|---:|---:|---:|
{table}

这些行不能用于直接降低电源/线径/保护规格。实际运动、零速保持、峰值、回生及效率曲线未绑定。理想辐射面积仅是已知热预算在理想无遮挡条件下的面积下界，未求解新罩体温度。

32个情景的已建支路相位小计为{min(x['known_phase_subtotal_Wh'] for x in ledgers):.2f}–{max(x['known_phase_subtotal_Wh'] for x in ledgers):.2f}Wh。它排除了未知停止/回生和未布线加热支路；加热器另列20W/0.8×600s=4.17Wh理想额外预算，不沿用待机保护判定。全周期能量、最终电量与补能均保持null，不代表闭轨道能源预算。

## 新发现与未解决的差异

- 974实例物性分类：270项CAD估算、94项源数字参考、610项未知；只有10个臂link具有源COM/惯量，全机动态刚体归属尚未完整。
- 当前公开DM URDF合计2.744480913kg，与4.5kg整臂参考差1.755519087kg。差异原因未查明；未缩放质量，也未猜测差额都属于电机。
- 六叶1.08kg是叶片预算，不是完整双翼总质量；铰链、线束、锁止与CIC等需按所有者单列。
- DM4340P手册/默认导出相电阻0.88/0.610635Ω，DM4310为0.65/0.599754Ω；不同型号修订和电阻口径不能直接混用。
- 继承V30电气源：ERC 0错0警，PCB仍4项Kelvin未连接；现有热负结果和未接受安装位置未被本轮解除。

## 验证与范围

机械22项、电气13项、执行器14项、根计算16项，共{total}项软件/参数/针对性检查通过，另有7项电气产物断言；不是{total}项整机试验。最终核对{v['unique_source_files_checked']}个唯一来源字节与消费输入，见[验证回执](results/VALIDATION.json)。独立审阅发现的负加热能量、加热支路保护口径、测量面、单位往返伪核验和硬编码偏置已修正并补反例。

内存处理见[回执](results/MEMORY_CLEANUP.json)：停止闲置SolidWorks预载器、回收一个后台工作集；受保护厂商服务访问被拒，未停止。清理后可用约{memory['after']['available_MiB']/1024:.2f}GiB；未把内存自然变化归功于本次清理。

## 入口与复现

- [交互查看](REVIEW.html) · [完整下一批改件表](NEXT_ENGINEERING_ACTIONS.csv)
- [机械基线](mechanical/MECHANICAL_BASELINE.json) · [逐实例登记](mechanical/INSTANCE_BODY_MAP.csv) · [逐姿态表](mechanical/INSTANCE_POSES.csv)
- [参考任务](inputs/REFERENCE_MISSION_V1.json) · [物性卡](mechanical/BODY_PARAMETER_CARD.json) · [电气参数](electrical/ARM_ELECTRICAL_PARAMETERS.json) · [执行器卡](actuators/ACTUATOR_CONTRACT.json)
- [母线采集方案](electrical/BUS_CAPTURE_PLAN_ZH.md) · [相位计算](results/PHASE_ENERGY_TRADE.json) · [稳态计算](results/STEADY_POWER_TRADE.csv)

使用现有Python，依次运行`tools/build_reference_inputs.py`、`tools/run_v31_trade.py`、`tools/verify_v31.py`、`tools/build_review.py`。三个分包自身提供构建/复核入口。所有写入限于本V31目录；不调用旧run_all，不加载CAD。新输入包仍依赖当前工作区原始来源，不是自包含整星CAD发布包。

下一轮优先处理同修订DM物性/电气来源、实际负载与停止/加热支路；据此确定供电与热边界，随后回装已接受的模块。每项对象和退出条件见改件表。
'''
    (P/'README_ZH.md').write_text(md,encoding='utf-8')
    payload=json.dumps(dict(points=points,ledgers=ledgers,actions=actions),ensure_ascii=False).replace('</','<\\/')
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>WP10 V31 · 工程输入与负载计算</title>
<style>:root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#f2f5f7;color:#182b39;font:16px/1.7 system-ui,"Microsoft YaHei",sans-serif}main{max-width:1180px;margin:auto;padding:38px 26px}h1{font-size:32px;line-height:1.3;margin:8px 0 18px}h2{font-size:22px;margin:12px 0}.eyebrow{color:#237767;font-weight:700;letter-spacing:2px}section,.card{background:white;border:1px solid #d8e2e5;border-radius:14px;padding:23px;margin:18px 0}.notice{background:#fff2d9;border-left:5px solid #bd7c12;padding:14px 19px;border-radius:7px}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.card{margin:0}.big{font-size:32px;font-weight:750;color:#146b63}.muted{color:#526779;font-size:14px}label{display:inline-block;margin:0 18px 10px 0}select{font:inherit;padding:6px;border:1px solid #abbec8;border-radius:6px;background:#fff}table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:10px;border-bottom:1px solid #e0e7eb;vertical-align:top}th{background:#edf3f5}a{color:#116b93}.links{display:flex;gap:18px;flex-wrap:wrap}.chips{color:#576d7e;font-size:14px}svg{width:100%;height:auto}.scroll{overflow:auto}.negative{color:#a03427}footer{font-size:13px;color:#5c6d77;padding:20px 0}@media(max-width:720px){.grid{grid-template-columns:1fr}main{padding:20px 14px}h1{font-size:27px}}</style>
<main><div class="eyebrow">WP10 / V31 / 2026-09-11</div><h1>把整机版本、任务和负载放到同一条计算链</h1>
<p>已完成输入包、来源核对与条件计算。原生装配和电气几何保持父版身份。</p>
<div class="notice"><strong>整机设计仍未完成。</strong> 停止/回生、加热供电、完整物性、推进受控接口和主输入安装仍开放。本页数值是设计情景，不是实测能力或上电许可。</div>
<section><div class="grid"><div><div class="big">873</div>已验证原生宿主<br><span class="muted">固定三态；继承冷重开回执</span></div><div><div class="big">974</div>当前完整源计划<br><span class="muted">删除18 / 新增119 / 换源29</span></div><div><div class="big">56 / 60</div>V30局部子件 / 实体<br><span class="muted">未回装，不计入974</span></div></div></section>
<section><h2>供电与已知热预算</h2><p class="muted">扫描变量位于CHB输出臂路径分配面。实际臂入口前线损仍未知；不以扫描值定义真实功耗上下界。</p>
<label>电池端 V <select id="v"><option>20</option><option>22</option><option selected>25.2</option><option>29.4</option></select></label>
<label>共享回路 Ω <select id="r"><option selected>0.01</option><option>0.1</option></select></label>
<label>假设转换效率 <select id="eta"><option selected>0.85</option><option>0.9</option></select></label>
<svg id="chart" viewBox="0 0 920 300" role="img" aria-label="输入功率与已计非臂热预算"></svg>
<div class="scroll"><table><thead><tr><th>臂路径分配 W</th><th>电池输入 W</th><th>电池 A</th><th>CHB损耗 W</th><th>已计非臂热 W</th><th>静态保护筛查</th></tr></thead><tbody id="power"></tbody></table></div>
<p class="muted">蓝线：输入功率；橙线：已计非臂热预算。辅助支路输入全部作为系统内发热是假设。未求解实际新罩体温度。</p></section>
<section><h2>同一参考周期的部分能源预算</h2><p>5700秒参考周期：日照3600秒、阴影2100秒；轨道元素和太阳/地球姿态未绑定。地面340秒采集流程独立保存。</p><p class="muted">本表固定电池端25.2 V、共享回路0.01 Ω；沿用上方选择的效率。上方电压和电阻选择仅改变稳态表。</p>
<label>保持 / 待机输出分配 <select id="profile"><option value="PROFILE_A">20 W / 5 W</option><option value="PROFILE_B">60 W / 15 W</option></select></label>
<div class="scroll"><table><thead><tr><th>运动输出分配 W</th><th>已建支路相位小计 Wh</th><th>加热理想额外预算 Wh</th><th>完整周期能量</th></tr></thead><tbody id="phase"></tbody></table></div>
<p class="notice">表内相位小计不包括未知停止/回生；加热器额外预算未经过实际支路、电流和保护求解。完整周期与最终电量保持 UNKNOWN，不计未经验证的补能信用。</p></section>
<section><h2>参数差异已保留，避免错误定型</h2><div class="grid"><div><strong>机械臂质量</strong><p>公开DM模型 2.74448 kg<br>整臂参考 4.5 kg<br>差额来源尚未解释。</p></div><div><strong>974项物性分类</strong><p>270 CAD估算<br>94 源数字参考<br>610 未知；整机惯量未闭合。</p></div><div><strong>执行器物理量</strong><p>逐轴轮组储存与外部角冲量预算分开。合成阵列反例通过，实际C-POD仍未知。</p></div></div></section>
<section><h2>下一批具体改件</h2><div class="scroll"><table><thead><tr><th>对象</th><th>修改内容</th><th>验收条件</th></tr></thead><tbody id="actions"></tbody></table></div></section>
<section><h2>原始资料与复查</h2><div class="links"><a href="README_ZH.md">设计说明</a><a href="DELIVERY_STATUS_V31.json">机器状态</a><a href="results/VALIDATION.json">验证记录</a><a href="inputs/REFERENCE_MISSION_V1.json">参考任务卡</a><a href="mechanical/INSTANCE_BODY_MAP.csv">974实例表</a><a href="mechanical/BODY_PARAMETER_CARD.json">物性卡</a><a href="electrical/BUS_CAPTURE_PLAN_ZH.md">母线采集方案</a><a href="actuators/README_ZH.md">执行器语义与反例</a></div></section>
<footer>本页离线运行，无外部脚本。输入、计算与负结果分别绑定；文件数量和测试通过不等于整机完成。</footer></main>
<script>const data=__DATA__;const $=x=>document.getElementById(x);const f=x=>x==null?'UNKNOWN':Number(x).toFixed(2);const labels={BLOCKED_BY_UVLO_SCREEN:'欠压筛查拒绝',BLOCKED_BY_OVLO_SCREEN:'过压筛查拒绝',BLOCKED_BY_CURRENT_SCREEN:'限流筛查拒绝',PROTECTION_CORNER_DEPENDENT:'依赖器差边界',CONDITIONAL_STATIC_POINT_STARTUP_UNVERIFIED:'条件稳态点，启动未验证'};
function render(){const V=+$('v').value,R=+$('r').value,E=+$('eta').value;const rows=data.points.filter(x=>x.pack_V===V&&x.shared_R_ohm===R&&x.eta_main===E);$('power').innerHTML=rows.map(x=>`<tr><td>${x.arm_path_W}</td><td>${f(x.input_power_W)}</td><td>${f(x.battery_A)}</td><td>${f(x.CHB_loss_W)}</td><td>${f(x.known_nonarm_heat_W)}</td><td>${labels[x.protection_class]||'无代数平衡点'}</td></tr>`).join('');
const valid=rows.filter(x=>x.equilibrium_found),max=Math.max(100,...valid.map(x=>x.input_power_W))*1.1,X=x=>70+(x-60)/300*790,Y=y=>250-y/max*220;let svg=`<line x1="70" y1="250" x2="860" y2="250" stroke="#8da1ad"/><line x1="70" y1="30" x2="70" y2="250" stroke="#8da1ad"/><text x="8" y="25" fill="#526779" font-size="14">功率 W</text>`;for(let i=0;i<=4;i++){const y=max*i/4;svg+=`<line x1="70" y1="${Y(y)}" x2="860" y2="${Y(y)}" stroke="#e3ebee"/><text x="8" y="${Y(y)+5}" fill="#526779" font-size="13">${y.toFixed(0)}</text>`}for(const x of rows)svg+=`<text x="${X(x.arm_path_W)-10}" y="278" fill="#526779" font-size="14">${x.arm_path_W}</text>`;for(const [key,color] of [['input_power_W','#176b97'],['known_nonarm_heat_W','#c27214']]){svg+=`<polyline points="${valid.map(x=>`${X(x.arm_path_W)},${Y(x[key])}`).join(' ')}" stroke="${color}" fill="none" stroke-width="3"/>`;for(const x of valid)svg+=`<circle cx="${X(x.arm_path_W)}" cy="${Y(x[key])}" r="5" fill="${color}"/>`}$('chart').innerHTML=svg;
const ps=data.ledgers.filter(x=>x.profile===$('profile').value&&x.eta_main===E&&x.initial_fraction===.8);$('phase').innerHTML=ps.map(x=>`<tr><td>${x.motion_output_allocation_W}</td><td>${f(x.known_phase_subtotal_Wh)}</td><td>${f(x.heater_ideal_extra_budget_Wh)}</td><td class="negative">UNKNOWN</td></tr>`).join('')}
$('actions').innerHTML=data.actions.map(x=>`<tr><td><strong>${x.id}</strong><br>${x.object}</td><td>${x.change}</td><td>${x.acceptance}</td></tr>`).join('');['v','r','eta','profile'].forEach(x=>$(x).addEventListener('change',render));render();</script></html>'''.replace('__DATA__',payload)
    (P/'REVIEW.html').write_text(page,encoding='utf-8')
    print(json.dumps(dict(review=str(P/'REVIEW.html'),checks=total,source_files=v['unique_source_files_checked'],actions=len(actions))))

if __name__=='__main__':main()
