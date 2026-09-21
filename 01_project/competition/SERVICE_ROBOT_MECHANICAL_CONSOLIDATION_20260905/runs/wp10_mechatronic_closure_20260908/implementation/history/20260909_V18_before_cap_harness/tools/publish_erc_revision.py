"""Publish the reviewed V16 ERC improvement without upgrading engineering gates."""
from pathlib import Path
import collections,csv,hashlib,html,json,urllib.parse
A=Path(__file__).resolve().parents[1]
H=A/'history/20260909_V15_before_erc_declarations'
def read(q):return json.loads((A/q).read_text(encoding='utf-8-sig'))
def sha(q):return hashlib.sha256((A/q).read_bytes()).hexdigest()
def dump(q,x):(A/q).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
v=read('results/POWER_LOOP_VERIFICATION.json');s=read('results/ERC_SOURCE_VALIDATION.json');t=read('results/ERC_REGRESSION_TESTS.json');r=read('results/ERC_READONLY_REVIEW.json');g=read('results/INPUT_CAP_MOUNT_EXACT.json')
assert v['ERC_clean'] and v['all_connectivity_checks_passed'] and s['passed'] and t['passed'] and r['review_complete'] and not r['unrepaired_findings'] and g['passed']
for data,key in [(s,'inputs'),(t,'inputs'),(r,'reviewed_files'),(g,'inputs')]:assert all(sha(q)==h for q,h in data[key].items()),key
for name in ['native_delta_erc_v16_final_retry','native_delta_cap_binding_v16']:
    guard=read('logs/'+name+'.run.json');assert guard['status']=='COMPLETED' and guard['returncode']==0
old=read('history/20260909_V15_before_erc_declarations/results/DELIVERY_DECISION.json')
d=dict(old)
d.update(schema='WP10_IMPLEMENTATION_DELIVERY_V16',revision='V16_MCP_CONDITIONAL_ERC_DECLARATIONS',review_revision='V16_MCP_CONDITIONAL_ERC_DECLARATIONS',status='NATIVE_ERC_CLEAN_WITH_AUDITED_DECLARATIONS__WHOLE_ENGINEERING_CLOSURE_OPEN',native_schematic_pages=12,connectivity_and_counterexample_checks=v['count'],ERC_open=0,ERC_types={},ERC_clean=True,ERC_source_audit_checks=s['check_count'],ERC_regression_tests=t['tests'],ERC_ignored_rule_keys=[q['key'] for q in v['ERC_ignored_checks']],nonphysical_source_declarations=7,goal_complete=False,engineering_prototype_design_complete=False)
d['active_next_work_item']['next_action']='Continue B03 physical input PCB/conductor/C203-to-CHB termination, inrush and fuse/BMS/MOSFET coordination; battery OEM interface and PMM charging boundary, STOP/regen thermal dynamics and same-revision propulsion ICD remain open. ERC declarations do not close these physical responsibilities.'
d['CAD_viewer_runtime_status']='UNAVAILABLE_BUILD123D_SYSTEM_FONT_TTLIBERROR; STEP and static assembly image provided'
dump('results/DELIVERY_DECISION.json',d)
rows=list(csv.DictReader((A/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig')))
prior=list(csv.DictReader((H/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig')))
assert len(rows)==37 and {q['id']:q['status'] for q in rows}=={q['id']:q['status'] for q in prior}
for row in rows:
    if row['id']=='B03':
        note=' | V16 原生ERC与MCP复核0错误0警告；7个有条件电源声明经源级审计，201实体/657引脚连接与类型不变，物理保护及端接仍开放。'
        if note not in row['new_evidence']:row['new_evidence']+=note
with (A/'SYSTEM_CLOSURE_MATRIX.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
counts=collections.Counter(q['status'] for q in rows)
assert dict(counts)==old['status_counts']
source=read('power/ERC_SOURCE_DECLARATIONS.json')
notes='\n'.join('- `'+q['reference']+'` → `'+q['net']+'`：'+q['condition'] for q in source['declarations'])
report=f'''# WP10 V16：KiCad MCP 接入与 ERC 优化

日期：2026-09-09。范围：既有工程样机方案的电源声明、检查器和同版本证据；沿用已授权的快速执行方式、B601 DM 和单受保护电池/CHB/独立 THN 架构，未新增器件选型或物理装配。

当前原生 KiCad 10.0.6 检查为 **0 错误、0 警告**，MCP 独立调用同样为零。原四项 ignored 检查保持：single_global_label、four_way_junction、simulation_model_issue、footprint_filter；零结果仅覆盖已启用规则。

7 个报告错误对应 7 个网络，而不是仅有 7 个电源输入引脚。原有供电图已包含保险丝、开关、转换器、接触器和回流；采用有条件的标准 PWR_FLAG 声明。保留电源输入类型、共漏极 VS、负载侧 U301 和输入/次级隔离；201 实体位号、657 引脚网络及类型与 V15 完全相同。7 个非物料声明不进入采购 BOM，实际原理图从 11 页变为 12 页。

实现取舍：增加可审计的标准声明，保留真实器件属性。把引脚改为 passive、改接 VS 或合并隔离回流会破坏模型或设计意图；整体屏蔽 power_pin_not_driven 会丢失后续检查能力。正常声明符合 [KiCad 原厂说明](https://docs.kicad.org/10.0/en/eeschema/eeschema.html#power-pins-and-power-flags)，用户 WP09R 第108行及 WP10 第166行亦允许有实际依据的标记。

## 逐网依据

{notes}

## 实际修改和验证

KiCad MCP 创建了声明页、七个原厂库符号、网络标签和可见条件说明。其自动工程名和层级路径发生适配问题，已仅对新页元数据进行规范化；未改动原有实体。声明页以 MCP 生成的原生源文件和根层级节点存档，现有生成器每次重建都会导入，避免手工修图后重建丢失。新增工程内 power 库副本以保持路径可移植。

旧的 XML-only 禁旗标检查无法可靠发现 # 电源符号。本轮改为原理图源级白名单，校验实例、UUID、网络、原厂库、位置、BOM/板属性、源文件哈希以及 201/657 不变性。原生命令失败会停止；即使命令成功，空报告、错源文件、漏页或检查范围变化也不能判 ERC_clean。

本轮 {v['count']} 项原有连通性与合同检查通过，声明审计 {s['check_count']} 项通过，{t['tests']} 项回归通过。独立审阅以有向图核对 256 个布尔条件组合，与条件路径模型一致；这不是器件动态仿真。C203 同版本 CAD/ECAD 接口重新检查，三姿态局部几何检查通过；CAD 源和安装件未发生几何改动。

## 保留的工程边界

J200 仍是项目适配端，厂家电池腔位及 Sys Detect 未绑定。保险丝/电池 BMS/MOSFET/线材保护配合、C203 实际铜箔和 CHB 端接、预充稳定性、停止与回生动态及热设计、PMM 充电和同修订推进 ICD 仍需完成。原 37 行状态保持 13 个限定子项完成、19 个内部设计开放、4 个外部接口未绑定、1 个实物未执行。所有整机完成、制造、上电和飞行放行字段保持 false。

内存不足时先清理已识别的空闲 Codex 工具工作集；未终止用户应用。记录了被 2 GiB 启动保护拦截的尝试和清理后的成功重试。工作集可再次加载，释放量不构成持续可用内存保证。

复现：先运行 tools/build_input_passive_revision.py（通过 native_delta_guard 串行启动），再运行 tools/test_erc_source_contract.py；修改 XML 后按现有 C203 接口流程重新绑定。所有结果须与其 inputs 哈希匹配。
'''
(A/'docs/hardware').mkdir(parents=True,exist_ok=True)
(A/'docs/hardware/ERC_OPTIMIZATION_V16.md').write_text(report,encoding='utf-8')
readme=f'''# WP10 当前 V16：ERC 声明与检查器已优化

KiCad CLI + MCP：**0 错误、0 警告**（原4项忽略规则保持）。{v['count']}项连接/合同检查、{s['check_count']}项源声明审计、{t['tests']}项回归通过。新增7个有条件的非物料电源声明，201实体/657引脚连接和类型保持；原理图12页。

当前为工程候选，整机详细设计尚未完成。原37行状态13/19/4/1保持；机械965组件候选未重建，C203接口已对新网表复核。

- [查看当前交付页](REVIEW.html)
- [完整原理图PDF](ecad/wp10_system.pdf)
- [ERC优化说明](docs/hardware/ERC_OPTIMIZATION_V16.md)
- [原生ERC报告](results/POWER_LOOP_ERC.json)
- [逐网声明](power/ERC_SOURCE_DECLARATIONS.json)
- [源级校验](results/ERC_SOURCE_VALIDATION.json) / [回归](results/ERC_REGRESSION_TESTS.json) / [独立复核](results/ERC_READONLY_REVIEW.json)
- [原37行闭环表](SYSTEM_CLOSURE_MATRIX.csv) / [当前裁决](results/DELIVERY_DECISION.json)
- [输入保护设计](power/INPUT_PASSIVE_DESIGN.md) / [C203机械接口](ecad/C203_MECHANICAL_INTERFACE.json)

下一责任项：B03 实际 PCB/导线/C203—CHB 端接及保护配合。电池厂家接口、PMM充电、停止回生热动态与同修订推进ICD继续开放。ERC清零不提供制造、上电或飞行放行。
'''
(A/'README.md').write_text(readme,encoding='utf-8')
listrows=''.join(f'<tr><td>{html.escape(q["id"])}</td><td>{html.escape(q["object"])}</td><td>{html.escape(q["status"])}</td><td>{html.escape(q["remaining_design"])}</td></tr>' for q in rows)
page=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>WP10 V16 · ERC优化</title><style>body{{margin:0;background:#f5f5f0;color:#18302b;font:16px/1.7 system-ui,"Microsoft YaHei",sans-serif}}main{{max-width:1150px;margin:auto;padding:36px 24px}}h1{{font-size:34px;line-height:1.3}}h2{{margin-top:34px}}.eyebrow{{color:#42685e;letter-spacing:.12em}}.cards{{display:flex;gap:16px;flex-wrap:wrap}}.card,section{{background:white;border:1px solid #d8e3db;border-radius:14px;padding:22px}}.card{{flex:1;min-width:140px}}.big{{font-size:38px;font-weight:700;color:#12624a}}.muted{{color:#53655e}}a{{color:#12624a}}nav{{display:flex;gap:18px;flex-wrap:wrap;margin:22px 0}}img{{width:100%;height:auto;border:1px solid #ddd}}table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{border-bottom:1px solid #dde5df;text-align:left;padding:9px;vertical-align:top}}.scroll{{overflow:auto}}details{{margin-top:25px}}.notice{{border-left:5px solid #b08224;padding-left:18px}}</style><main><div class="eyebrow">WP10 · V16 · 2026-09-09</div><h1>电源声明已接入，ERC 错误已清零</h1><p>新增 KiCad MCP 与 hardware-solution 审阅流程已用于实际源文件修改和原生检查。</p><div class="cards"><div class="card"><div class="big">0 / 0</div>ERC 错误 / 警告</div><div class="card"><div class="big">201</div>实体位号保持</div><div class="card"><div class="big">657</div>引脚连接与类型保持</div><div class="card"><div class="big">{t['tests']}</div>回归测试通过</div></div><nav><a href="ecad/wp10_system.pdf">查看12页原理图</a><a href="docs/hardware/ERC_OPTIMIZATION_V16.md">优化说明</a><a href="results/ERC_READONLY_REVIEW.json">独立复核</a><a href="WP10_IMPLEMENTATION_DELTA.zip">下载当前包</a></nav><p class="notice">本轮完成 ERC 建模与检查器修正。电池厂家接口、保护配合、PCB/线束实物端接、停止回生热动态和推进 ICD 仍开放；整机未获制造、上电或飞行放行。原4项忽略规则保持，0/0仅针对已启用规则。</p><h2>可追溯的供电声明</h2><p>7个非物料标记均绑定真实设计路径和条件。输入与次级回流分开，U204 VS 保持共漏极，U301 保持接触器后的负载侧。原有10个电气子页的实体设计保持。</p><a href="review/ERC_POWER_DECLARATIONS_V16.png"><img src="review/ERC_POWER_DECLARATIONS_V16.png" alt="原生KiCad导出的电源声明页"></a><nav><a href="results/POWER_LOOP_ERC.json">原生ERC</a><a href="results/ERC_MCP_CROSSCHECK.json">MCP复查</a><a href="results/ERC_SOURCE_VALIDATION.json">源级审计</a><a href="results/ERC_REGRESSION_TESTS.json">回归证据</a></nav><h2>整机候选继续沿用</h2><section><p>965组件机械候选与原873组件/99位号父本保留。C203接口对当前网表重新检查；本次没有新的实体几何修改。</p><a href="ecad/C203_MECHANICAL_INTERFACE.json">查看当前C203机电接口</a> · <a href="results/INPUT_CAP_MOUNT_EXACT.json">查看三姿态局部检查</a> · <a href="mechanical/INPUT_CAP_MOUNT_INSTANCE_PLAN.json">当前装配清单</a><p>下一步：B03 实际 PCB、导线、C203—CHB 端接和故障保护配合。</p></section><details><summary>查看原37行责任项：13限定完成 / 19内部开放 / 4外部接口 / 1实物未执行</summary><div class="scroll"><table><thead><tr><th>ID</th><th>对象</th><th>状态</th><th>剩余设计</th></tr></thead><tbody>{listrows}</tbody></table></div></details><nav><a href="SYSTEM_CLOSURE_MATRIX.csv">下载闭环表</a><a href="results/DELIVERY_DECISION.json">机器裁决</a></nav></main></html>'''
assert (A/'mechanical/input_cap_integration.step').exists()
page=page.replace('<a href="ecad/C203_MECHANICAL_INTERFACE.json">','<a href="mechanical/input_cap_integration.step">下载现有C203/CHB局部装配STEP</a> · <a href="review/input_cap_chb_detail_20260909T044432Z.png">查看原有装配静态图</a><p class="muted">3D浏览服务因本机 build123d 字体读取异常未恢复；STEP文件与原生电气查看正常。</p><a href="ecad/C203_MECHANICAL_INTERFACE.json">')
(A/'REVIEW.html').write_text(page,encoding='utf-8')
for target in ['results/INPUT_PASSIVE_READONLY_REVIEW.json','results/INPUT_CAP_MOUNT_READONLY_REVIEW.json']:
    prior_review=json.loads((H/target).read_text(encoding='utf-8-sig'))
    dump(target,dict(schema='WP10_V16_READONLY_SCOPE_POINTER',review_complete=True,current_review='results/ERC_READONLY_REVIEW.json',current_review_sha256=sha('results/ERC_READONLY_REVIEW.json'),reviewed_files=r['reviewed_files'],historical_review=(H/target).relative_to(A).as_posix(),scope='V16 topology/source equivalence and current binding; V15 independent numeric and V14 geometry reviews remain historical evidence. No new physical qualification.',whole_design_complete=False))
for target in ['results/SHARED_BATTERY_READONLY_REVIEW.json','results/SHARED_BATTERY_PATH_REVIEW.json']:
    dump(target,dict(schema='WP10_V16_SHARED_MODEL_REVIEW_POINTER',current_review='results/ERC_READONLY_REVIEW.json',current_review_sha256=sha('results/ERC_READONLY_REVIEW.json'),calculations_sha256=sha('power/SHARED_BATTERY_PATH_CALCULATIONS.json'),scope='V15 numerical cases preserved; V16 source binding verified',whole_design_complete=False))
evidence=['README.md','REVIEW.html','SYSTEM_CLOSURE_MATRIX.csv','results/DELIVERY_DECISION.json','docs/hardware/ERC_OPTIMIZATION_V16.md','results/ERC_READONLY_REVIEW.json','results/ERC_SOURCE_VALIDATION.json','results/ERC_REGRESSION_TESTS.json','results/POWER_LOOP_ERC.json','ecad/C203_MECHANICAL_INTERFACE.json']
dump('results/ERC_REVISION_INTEGRATION.json',dict(schema='WP10_V16_ERC_INTEGRATION',revision=d['revision'],evidence={q:sha(q) for q in evidence},same_candidate=True,physical_design_changed=False,source_design_edited=True,ERC_clean=True,original37_statuses_preserved=True,goal_complete=False,physical_tests_executed=False))
print(json.dumps(dict(revision=d['revision'],ERC_errors=0,ERC_warnings=0,tests=t['tests'],entities=201,original37_statuses_preserved=True,goal_complete=False)))
