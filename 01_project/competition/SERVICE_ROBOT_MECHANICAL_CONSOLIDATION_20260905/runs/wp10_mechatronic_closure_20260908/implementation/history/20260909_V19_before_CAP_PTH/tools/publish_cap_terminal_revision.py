"""Publish V17 from existing verified native sources; never promote whole-system gates."""
from pathlib import Path
import json,csv,hashlib,collections,html,sys
A=Path(__file__).resolve().parents[1];H=A/'history/20260909_V16_before_cap_terminal'
checkpoint='--checkpoint' in sys.argv
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def dump(p,v):(A/p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
c=read('results/CAP_TERMINAL_COPPER_AUDIT.json');r=read('results/CAP_TERMINAL_READONLY_REVIEW.json');g=read('results/INPUT_CAP_MOUNT_EXACT.json')
s=read('results/ERC_SOURCE_VALIDATION.json');t=read('results/ERC_REGRESSION_TESTS.json');m=read('results/ERC_MCP_CROSSCHECK.json')
erc=read('results/POWER_LOOP_ERC.json');power=read('results/POWER_LOOP_VERIFICATION.json')
assert not m['result'].get('isError',False)
assert m['result']['content']==[{'type':'text','text':'ERC result: 0 violation(s)\n  Errors: 0  Warnings: 0  Info: 0'}]
assert power['ERC_command_succeeded'] and power['ERC_clean'] and power['all_connectivity_checks_passed']
assert power['ERC_count']==power['ERC_errors']==power['ERC_warnings']==0
assert len(erc['sheets'])==12 and set(erc['included_severities'])=={'error','warning'} and all(not q['violations'] for q in erc['sheets'])
assert {q['key'] for q in erc['ignored_checks']}=={'single_global_label','four_way_junction','simulation_model_issue','footprint_filter'}
rows=list(csv.DictReader((A/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig')))
prior=list(csv.DictReader((H/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig')))
old=read('history/20260909_V16_before_cap_terminal/results/DELIVERY_DECISION.json')
assert len(rows)==37 and {q['id']:q['status'] for q in rows}=={q['id']:q['status'] for q in prior}
assert dict(collections.Counter(q['status'] for q in rows))==old['status_counts']
assert c['passed'] and c['check_count']==20 and len(c['fault_injections'])==5
assert r['review_complete'] and not r['unrepaired_findings'] and g['passed'] and s['passed'] and t['passed']
for v,k in [(c,'inputs'),(r,'reviewed_files'),(g,'inputs'),(s,'inputs'),(t,'inputs'),(m,'inputs')]:
    assert all(sha(p)==h for p,h in v[k].items()),k
visual=read('results/CAP_TERMINAL_VISUAL_REVIEW_V17.json')
assert (checkpoint or visual['root_viewed_current_images']) and all(sha(p)==h for p,h in visual['inputs'].items())
for phase in (['PCB'] if checkpoint else ['PCB','ASSEMBLY','PCB_SHOT','ASSEMBLY_SHOT']):
    v=read('results/CAP_TERMINAL_CAD_'+phase+'_V17.json')
    assert len(v['results'])==2
    if phase.endswith('_SHOT'):
        assert sum('result' in q for q in v['results'])==1 and sum('image' in q for q in v['results'])==1
        expected_image='review/C203_'+('PCB' if phase=='PCB_SHOT' else 'ASSEMBLY')+'_V17.png'
        assert [q['image'] for q in v['results'] if 'image' in q]==[expected_image]
    expected={'results/CAP_TERMINAL_'+phase+'_V17.json'} if phase.endswith('_SHOT') else {'results/CAP_TERMINAL_'+phase+'_'+action+'_V17.json' for action in ['REFS','VALIDATE']}
    assert {q['result'] for q in v['results'] if 'result' in q}==expected
    assert sha(v['source'])==v['source_sha256'] and sha(v['source']+'.py')==v['source_generator_sha256']
    for q in v['results']:
        assert sha(q.get('result',q.get('image')))==q['sha256']
        if 'result' in q:
            result=read(q['result']);assert q['returncode']==0 and result['ok'] is True
            if q['result'].endswith('_VALIDATE_V17.json'):assert result['failureCount']==0 and result['occurrenceCount']>0
        else:
            assert sha(q['original_image'])==q['sha256']
if not checkpoint:
    export=read('results/CAP_TERMINAL_LAYOUT_EXPORT_V17.json')
    assert export['native_export'] and sha(export['board'])==export['board_sha256']
    assert set(export['outputs'])=={'review/C203_TERMINAL_LAYOUT_V17.pdf','review/C203_TERMINAL_LAYOUT_V17.png','results/CAP_TERMINAL_DRC_V17.rpt','results/CAP_TERMINAL_DRC_NATIVE_V17.json'}
    assert all(sha(p)==h for p,h in export['outputs'].items())
    drc=read('results/CAP_TERMINAL_DRC_NATIVE_V17.json')
    assert collections.Counter(q['type'] for q in drc['violations'])=={'hole_clearance':8,'solder_mask_bridge':4}
    assert all(q['severity']=='error' for q in drc['violations']) and not drc['unconnected_items']
for name in ['native_delta_cap_mount_v17','native_delta_cap_detail_retry3_v17','native_delta_cap_preview_v17','native_delta_cap_reviewer_copper_retry_v17']:
    v=read('logs/'+name+'.run.json');assert v['status']=='COMPLETED' and v['returncode']==0
d=dict(old)
d.update(schema='WP10_IMPLEMENTATION_DELIVERY_V17',revision='V17_NATIVE_C203_TERMINAL_AND_COPPER_AUDIT',review_revision='V17_NATIVE_C203_TERMINAL_AND_COPPER_AUDIT',
    status='NATIVE_C203_COPPER_AND_TWO_HOLE_CAD_INTEGRATED__PCB_PROCESS_AND_WHOLE_ENGINEERING_OPEN',
    native_terminal_board='ecad/wp10_c203_terminal.kicad_pcb',terminal_copper_checks=20,terminal_copper_faults_rejected=5,
    terminal_PCB_DRC_errors=12,terminal_PCB_DRC_warnings=0,terminal_PCB_DRC_types={'hole_clearance':8,'solder_mask_bridge':4},
    terminal_PCB_DRC_clean=False,terminal_to_CHB_physical_connection_complete=False,terminal_manufacturing_qualified=False,
    source_candidate_components=965,goal_complete=False,engineering_prototype_design_complete=False,
    manufacture_release=False,power_on_authorized=False,flight_release=False,physical_tests_executed=False)
d['active_next_work_item']['next_action']='B03: implement the real CHB input terminal board and short paired C203 conductors, retention and low-inductance route; close single-face NPTH/CAM/solder process and fuse/BMS/MOSFET coordination. Battery/PMM, STOP/regen/thermal dynamics and same-revision propulsion ICD remain open.'
d['CAD_viewer_runtime_status']=visual['viewer_runtime_status']
if checkpoint:
    d.update(status='V17_SOURCE_AND_COPPER_VERIFIED__NEW_CONTEXT_VISUAL_VALIDATION_RESOURCE_PENDING__WHOLE_ENGINEERING_OPEN',new_CAD_visual_acceptance=False,new_context37_CLI_validation_complete=False,preview_pending_items=visual['pending_items'])
dump('results/DELIVERY_DECISION.json',d)
for q in rows:
    if q['id']=='B03':
        note=' | V17 C203单面铜端接PCB与两导线孔STEP已集成，20项物理铜检查/5反例通过；ERC0/0保持；PCB DRC12项及CHB实体端接、保持、保护配合开放。'
        if note not in q['new_evidence']:q['new_evidence']+=note
with (A/'SYSTEM_CLOSURE_MATRIX.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
report="""# WP10 V17：C203 原生端接板、机械导线孔与检查器修复

同一工程候选，2026-09-09。已接入的 KiCad MCP 用于实际封装、板框、走线与原生 ERC；CAD skill 用于 STEP 生成、检查和实际图像。所有整机完成、制造、上电与飞行放行仍为 false。

## 已落地的改件

C203 保留 ELXG101VSN222MR50S。原生端接板为50×48×1.6 mm，背面70 μm铜、4 mm走线；四个物理电气端点对应两个逻辑引脚。两端接导线材料选用 TE 55A0111-18-9 / 18 AWG，线长、剥线、走线和 CHB 端部结构仍未定型。

PCB STEP 在原件上新增两个 Ø1.8 mm 通孔，差分确认只有这两处切除。29件支架局部装配和37件带 CHB 的背景装配均已重新生成。965组件是源装配清单；本次未生成或验证965件完整原生 SolidWorks 总装。

## 为什么改为背面单面铜

[Chemi-Con 2026 注意事项，第2页](../../sources/chemi_al_precautions_2026.pdf)规定端子封口侧及双面板下方布线限制。本轮据此淘汰双面布铜方案，保留完整背面焊接铜环，采用单面印制铜、无金属化孔候选。原厂对具体安装的接受、CAM加工与焊接可靠性仍需闭环，不能把公开通用条件当成该装配的批准。

原生栈厚回读为0.01 mm顶阻焊 + 0顶铜 + 1.50 mm芯板 + 0.07 mm背铜 + 0.02 mm背阻焊 = 1.60 mm。这是名义设计，FR4供方、Tg、热性能、放气、尺寸公差仍未限定。STEP只表达成品板包络，未把铜与芯板分别赋真实材料质量。

## ERC 与 PCB DRC 分开列示

| 检查对象 | 当前结果 | 含义 |
|---|---:|---|
| 整机原理图 ERC | 0 错误 / 0 警告 | CLI与MCP一致，既有4项忽略保持 |
| 源级审计 | 53 项通过 | 201实体/657引脚网络和类型保持；仅C203 footprint属性变化 |
| ERC回归 | 16 项通过 | 继续保留故障反例 |
| C203 PCB DRC | 12 错误 / 0 警告 | 8孔距、4阻焊桥，继续开放 |
| 实际铜连接 | 20 项通过 / 5 故障反例被拒绝 | 扣除真实钻孔后逐网检查，不靠重复引脚号判通路 |

8项孔距来自NPTH与自身背面焊盘/走线重叠，4项阻焊桥来自该复合端接开口。未新增豁免，未缩退铜环来掩盖错误，未把DRC标为通过。需要针对加工方式、封装表达和焊接工艺完成处置。

原生网表会把相同引脚号视为连接；独立几何检查另行证明每网两个物理端点之间铜连续，并检验正负最小距离。当前两网名义铜间距6 mm；这不是爬电、电气间隙或耐压资格。相切反例的交叠面积为0、距离为0，已被修复后的检查器拒绝。封装内部铜图形也纳入检查。

WIRE端 Ø3.5 mm焊盘自身侧隙2.54899 mm、窗口余量0.75 mm；4 mm走线圆端帽的实际铜包络侧隙2.29899 mm、窗口余量0.50 mm。均为名义投影尺寸，未含公差、焊锡、工具与导线转弯。铜走线长度各20.65685 mm；20°C均匀铜段电阻各约1.272 mΩ，2.4 A时两段合计约0.01465 W。该初筛排除焊点/端子/导线电阻及实际纹波，不能当作端接总损耗或电流额定值。

## 几何和审阅范围

三种固定姿态的既定局部干涉、接触、工具与保留空间检查通过。当前PCB完整几何合法性已检查；37件背景装配跳过昂贵的背景自交检查并明确记录。图中为便于查看隐藏了上/下设备板、外辐射板、电池及其适配板、推进分配块及其适配板，共7件；隐藏只影响显示，检查及装配清单仍保留。背面板图验收还发现顶部组合丝印存在左右极性误读风险，已改为各电容焊孔旁的独立极性标记。

一名只读审阅者核对原生板、提取几何、XML、铜检查、反例及哈希，提出两项检查器漏洞并经修复复核通过。该审阅未加载重CAD，也未独立审阅三姿态；后者为主执行者运行的既有局部检查，不能混作独立复算。

本机一个损坏的系统字体曾阻止 build123d 启动。项目内 opt-in 过滤器只在 build123d.text 调用时跳过已核对路径和SHA的无效字体；未删除系统字体、修改安装包或绕过未知文件。Box与真实文字实体均已生成验证。内存低于2 GiB时守卫拒绝启动，清理仅修剪已识别、低CPU采样的Codex工具服务工作集，排除自身和祖先进程。低CPU不能证明没有在途I/O或子任务；未终止进程或用户应用。

## 仍需完成

B03下一责任件为CHB输入端接板、C203至CHB短配对导线与保持结构；同时落实单面NPTH加工/焊接、实际低电感、冷启动及保护配合。电池厂家接口、PMM充电、停止与回生动态/热路径和同修订推进ICD继续开放。原37行状态保持13限定子项完成 /19内部开放 /4外部接口未绑定 /1实物未执行。

复现顺序：原生板保存后用 cap_terminal_native.py extract 提取；check_cap_terminal_copper.py 复核实体通路；在已有当前STEP与网表基础上使用 check_input_cap_mount.py 与 integrate_input_cap_mount.py 检查和绑定；review_cap_terminal_cad.py 各阶段串行通过 native_delta_guard 运行。若板栈厚改变，先 finalize、再 sync_cap_terminal_bindings，并重新生成所有依赖项。prepare_cap_terminal_sources.py 是一次性迁移脚本，已设防重复执行。
"""
if checkpoint:
    report=report.replace('当前PCB完整几何合法性已检查；37件背景装配跳过昂贵的背景自交检查并明确记录。图中为便于查看隐藏了上设备板、外辐射板、下设备板；隐藏只影响显示，检查及装配清单仍保留。','当前PCB完整几何合法性已检查。37件当前背景装配的CLI检查、新STEP截图和板图PDF尚未执行完成：反复清理后可用内存仍低于2 GiB启动门槛。已有三姿态局部OCP检查是本版本结果，但不替代缺席的整体背景检查或视觉验收。旧装配图不作为新两孔版本图形验收证据。')
    report='> 本页为V17工作检查点：实际源、铜审计和局部OCP已验证；新背景装配CLI/截图/PDF待资源恢复后继续。\n\n'+report
(A/'docs/hardware/CAP_TERMINAL_V17.md').write_text(report,encoding='utf-8')
readme="""# WP10 当前 V17：C203 端接板和检查器已改进

原生 KiCad C203 端接板已建立，背面70 μm铜和两导线孔已与机械STEP集成。铜检查20项、5个故障反例通过；当前ERC为0错误/0警告，PCB DRC仍有12项工艺问题。

- [查看当前设计](REVIEW.html)
- [原生C203 PCB](ecad/wp10_c203_terminal.kicad_pcb) / [背面铜图PDF](review/C203_TERMINAL_LAYOUT_V17.pdf)
- [37件C203/CHB局部装配STEP](mechanical/input_cap_integration.step) / [29件安装组件STEP](mechanical/input_cap_detail.step)
- [12页原理图PDF](ecad/wp10_system.pdf)
- [设计说明与限制](docs/hardware/CAP_TERMINAL_V17.md) / [独立审阅](results/CAP_TERMINAL_READONLY_REVIEW.json)
- [原37行闭环表](SYSTEM_CLOSURE_MATRIX.csv) / [机器裁决](results/DELIVERY_DECISION.json)

整体仍是工程候选：965组件为源装配清单，CHB端接、保持、保护配合及整机机电热推进责任项继续开放；未获制造、上电或飞行放行。
"""
if checkpoint:
    readme=readme.replace('[背面铜图PDF](review/C203_TERMINAL_LAYOUT_V17.pdf)','板图导出待完成；极性修正前的旧SVG已单独标为历史参考')
    readme=readme.replace('原生 KiCad C203', '**工作检查点：新背景装配CLI、STEP截图与板图PDF因低内存待检。**\n\n原生 KiCad C203')
(A/'README.md').write_text(readme,encoding='utf-8')
tr=''.join('<tr>'+''.join('<td>'+html.escape(q[k])+'</td>' for k in ['id','object','status','remaining_design'])+'</tr>' for q in rows)
page="""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>WP10 V17 · C203机电端接</title><style>
body{margin:0;background:#f3f4ee;color:#233c35;font:16px/1.75 system-ui,"Microsoft YaHei",sans-serif}main{max-width:1150px;margin:auto;padding:32px 24px}h1{font-size:34px;line-height:1.35}h2{margin-top:32px}.cards{display:flex;flex-wrap:wrap;gap:16px}.card{background:white;border:1px solid #cedbd1;border-radius:12px;padding:20px;flex:1;min-width:155px}.big{font-size:36px;font-weight:700;color:#166146}.open{color:#9a5612}nav{display:flex;gap:20px;flex-wrap:wrap;margin:20px 0}a{color:#116346}.notice{border-left:5px solid #b37a23;padding:12px 18px;background:#fff9e8}img{max-width:100%;height:auto;border:1px solid #d6ddd5;background:white}.twocol{display:grid;grid-template-columns:1fr 1fr;gap:18px}table{border-collapse:collapse;font-size:13px}td,th{border-bottom:1px solid #d6ddd5;padding:9px;text-align:left;vertical-align:top}.scroll{overflow:auto}@media(max-width:760px){.twocol{grid-template-columns:1fr}}small{color:#536b60}</style><main>
<small>WP10 · V17 · 2026-09-09 · 同一工程候选</small><h1>C203端接板已布铜，导线孔已集成</h1><p>KiCad MCP、参数化 CAD 和只读复核已用于实际源文件修改及反例修复。</p>
<div class="cards"><div class="card"><div class="big">0 / 0</div>整机 ERC 错误 / 警告</div><div class="card"><div class="big open">12</div>C203 PCB DRC 开放项</div><div class="card"><div class="big">20 + 5</div>铜检查 + 故障反例通过</div><div class="card"><div class="big">37</div>当前局部装配实体</div></div>
<nav><a href="ecad/wp10_system.pdf">12页整机原理图</a><a href="ecad/wp10_c203_terminal.kicad_pcb">原生C203 PCB</a><a href="mechanical/input_cap_integration.step">37件局部STEP</a><a href="WP10_IMPLEMENTATION_DELTA.zip">下载当前包</a></nav>
<p class="notice">整机详细设计尚未完成。C203板的8项孔距、4项阻焊桥错误仍需加工/焊接处置；CHB实际端接、导线保持和保护配合继续开放。ERC 0/0仅覆盖启用规则，原4项忽略保持。</p>
<h2>实际板图与孔位</h2><div class="twocol"><div><a href="review/C203_TERMINAL_LAYOUT_V17.pdf"><img src="review/C203_TERMINAL_LAYOUT_V17.png" alt="原生KiCad导出的C203背面铜图"></a><p>50×48 mm板，背面70 μm铜、4 mm走线；4个物理电气端点、8个无金属化孔。</p></div><div><a href="review/C203_PCB_V17.png"><img src="review/C203_PCB_V17.png" alt="当前C203 PCB STEP实物包络，包含两个新增导线孔"></a><p>机械STEP只表达1.6 mm成品包络。两个新导线孔Ø1.8 mm；铜和芯板材料未分别建模。</p></div></div>
<h2>同版本局部装配</h2><a href="review/C203_ASSEMBLY_V17.png"><img src="review/C203_ASSEMBLY_V17.png" alt="当前37件C203和CHB局部装配，隐藏7个遮挡背景件后显示30件"></a><p>为观察电容与CHB，查看图隐藏上/下设备板、外辐射板、电池及其适配板、推进分配块及其适配板，共7件。三姿态局部检查保留这些部件；未进行965组件整体或连续动作验收。</p>
<nav><a href="mechanical/input_cap_detail.step">29件安装组件STEP</a><a href="mechanical/INPUT_CAP_MOUNT_INSTANCE_PLAN.json">965组件源清单</a><a href="results/INPUT_CAP_MOUNT_EXACT.json">三姿态局部结果</a><a href="ecad/C203_MECHANICAL_INTERFACE.json">C203机电接口</a></nav>
<h2>检查器已修复的反例</h2><p>相同引脚号不再替代实际铜连通检查。移除走线、断开单段、桥接正负及零面积相切均被检出；封装内部铜图元已纳入检查。当前两网名义铜距6 mm，WIRE端铜包络窗口余量0.50 mm，均未取得公差或工艺资格。</p>
<nav><a href="results/CAP_TERMINAL_COPPER_AUDIT.json">20检查与5反例</a><a href="results/CAP_TERMINAL_READONLY_REVIEW.json">限定范围独立复核</a><a href="results/CAP_TERMINAL_DRC_V17.rpt">12项DRC明细</a><a href="results/ERC_MCP_CROSSCHECK.json">MCP ERC结果</a><a href="docs/hardware/CAP_TERMINAL_V17.md">设计依据、复现与限制</a></nav>
<h2>下一责任件</h2><p>CHB输入端接板、C203至CHB短配对导线及保持结构；同时补齐单面孔加工/焊接、低电感与保护配合。电池/PMM、停止回生热动态、同修订推进ICD继续按原闭环表推进。</p>
<details><summary>原37行状态：13限定完成 /19内部开放 /4外部接口 /1实物未执行</summary><div class="scroll"><table><thead><tr><th>ID</th><th>对象</th><th>状态</th><th>剩余设计</th></tr></thead><tbody>__ROWS__</tbody></table></div></details>
<nav><a href="SYSTEM_CLOSURE_MATRIX.csv">完整闭环表</a><a href="results/DELIVERY_DECISION.json">当前机器裁决</a></nav></main></html>""".replace('__ROWS__',tr)
if checkpoint:
    begin=page.index('<h2>实际板图与孔位</h2>');end=page.index('<nav><a href="mechanical/input_cap_detail.step">',begin)
    page=page[:begin]+'''<h2>当前可查看的源与检查范围</h2><p class="notice">这是V17工作检查点。当前PCB完整几何合法性已通过；37件新背景装配CLI检查、STEP截图和板图PDF尚待内存恢复后完成。所有启动仍保持2 GiB门槛，已有旧图片未作为当前几何证据展示。</p><p>50×48×1.6 mm成品板包络已新增两个Ø1.8 mm导线孔；29件安装组件和37件局部装配STEP已重新生成。三种固定姿态的局部OCP检查通过，965组件为源清单，完整总装和连续动作尚未验收。</p><nav><a href="review/C203_TERMINAL_LAYOUT_V17.svg">候选背面铜图SVG（视觉待检）</a><a href="mechanical/input_cap_pcb.step">当前PCB STEP</a><a href="results/CAP_TERMINAL_PCB_VALIDATE_V17.json">当前PCB完整合法性检查</a><a href="results/CAP_TERMINAL_VISUAL_REVIEW_V17.json">待检项目与资源记录</a></nav>'''+page[end:]
    page=page.replace('<h1>C203端接板已布铜，导线孔已集成</h1>','<h1>C203端接板已改进 · 图形验收待续</h1>')
(A/'REVIEW.html').write_text(page,encoding='utf-8')
for target in ['results/INPUT_PASSIVE_READONLY_REVIEW.json','results/INPUT_CAP_MOUNT_READONLY_REVIEW.json']:
    dump(target,dict(schema='WP10_V17_READONLY_SCOPE_POINTER',review_complete=True,current_review='results/CAP_TERMINAL_READONLY_REVIEW.json',current_review_sha256=sha('results/CAP_TERMINAL_READONLY_REVIEW.json'),reviewed_files=r['reviewed_files'],historical_review=(H/target).relative_to(A).as_posix(),scope='V17 native board/copper/source binding only. Prior numeric and geometry reviews are lineage; V17 three-state and previews are root-run, not independently CAD-reviewed.',whole_design_complete=False))
evidence=['README.md','REVIEW.html','SYSTEM_CLOSURE_MATRIX.csv','results/DELIVERY_DECISION.json','docs/hardware/CAP_TERMINAL_V17.md','results/CAP_TERMINAL_READONLY_REVIEW.json','results/CAP_TERMINAL_COPPER_AUDIT.json','results/CAP_TERMINAL_NATIVE_GEOMETRY.json','results/CAP_TERMINAL_STACKUP.json','results/INPUT_CAP_MOUNT_EXACT.json','results/ERC_SOURCE_VALIDATION.json','results/ERC_REGRESSION_TESTS.json','results/POWER_LOOP_ERC.json','results/ERC_MCP_CROSSCHECK.json','ecad/C203_MECHANICAL_INTERFACE.json','ecad/wp10_c203_terminal.kicad_pcb','mechanical/input_cap_pcb.step','mechanical/input_cap_detail.step','mechanical/input_cap_integration.step','results/CAP_TERMINAL_VISUAL_REVIEW_V17.json']
dump('results/CAP_TERMINAL_REVISION_INTEGRATION.json',dict(schema='WP10_V17_CAP_TERMINAL_INTEGRATION',revision=d['revision'],evidence={q:sha(q) for q in evidence},same_candidate=True,physical_design_source_changed=True,original37_statuses_preserved=True,ERC_clean=True,PCB_DRC_clean=False,checkpoint_only=checkpoint,new_visual_acceptance=not checkpoint,goal_complete=False,physical_tests_executed=False))
print(json.dumps(dict(revision=d['revision'],copper_checks=20,faults=5,PCB_DRC_errors=12,ERC_errors=0,original37_statuses_preserved=True,goal_complete=False)))
