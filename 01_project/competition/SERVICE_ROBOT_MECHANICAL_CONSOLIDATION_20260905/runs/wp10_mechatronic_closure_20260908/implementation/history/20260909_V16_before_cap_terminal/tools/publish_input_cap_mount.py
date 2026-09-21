"""Publish same-candidate V14 only from reviewed, hash-matched actual artifacts."""
from pathlib import Path
import json,hashlib,csv,html,collections,urllib.parse
A=Path(__file__).resolve().parents[1]
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def dump(p,v):(A/p).write_text(json.dumps(v,indent=2,ensure_ascii=False),encoding='utf-8')
g=read('results/INPUT_CAP_MOUNT_EXACT.json');er=read('results/INPUT_PASSIVE_READONLY_REVIEW.json');rv=read('results/INPUT_CAP_MOUNT_READONLY_REVIEW.json');v=read('results/POWER_LOOP_VERIFICATION.json');p=read('mechanical/INPUT_CAP_MOUNT_INSTANCE_PLAN.json');visual=read('results/INPUT_CAP_VISUAL_REVIEW.json')
assert g['passed'] and visual['images_inspected'] and rv['review_complete']
for d,k in [(g,'inputs'),(p,'inputs'),(rv,'reviewed_files'),(er,'reviewed_files')]:assert all(sha(q)==h for q,h in d[k].items())
for n in ['native_delta_input_footprint_order_fix','native_delta_input_cap_exact_final','native_delta_input_cap_views']:
 r=read('logs/'+n+'.run.json');assert r['status']=='COMPLETED' and r['returncode']==0
decision=read('results/DELIVERY_DECISION.json')
decision.update(schema='WP10_IMPLEMENTATION_DELIVERY_V14',revision='V14_C203_INSTALLATION_CANDIDATE',review_revision='V14_C203_INSTALLATION_CANDIDATE',status='C203_MOUNT_CAD_ECAD_DATUM_BOUND__WHOLE_MECHATRONIC_CLOSURE_OPEN',ERC_open=v['ERC_count'],ERC_types=v['ERC_types'],candidate_source_components=965,current_source_plan='mechanical/INPUT_CAP_MOUNT_INSTANCE_PLAN.json',current_source_plan_sha256=sha('mechanical/INPUT_CAP_MOUNT_INSTANCE_PLAN.json'),current_source_instances_by_state={s:len(r['rows']) for s,r in p['states'].items()},current_local_source_assembly_instances=37,current_local_step='mechanical/input_cap_integration.step',C203_mount_nominal_geometry_screened=True,C203_retention_qualified=False,C203_thermal_environment_verified=False,C203_CHB_connection_complete=False,C203_installation_review='results/INPUT_CAP_MOUNT_READONLY_REVIEW.json',C203_delta_pairs_by_state={s:len(r['tests']) for s,r in g['states'].items()},C203_required_contacts_by_state={s:len(r['required_contacts']) for s,r in g['states'].items()},C203_ecad_mechanical_interface='ecad/C203_MECHANICAL_INTERFACE.json',C203_installation_BOM='mechanical/INPUT_CAP_INSTALLATION_BOM.csv',whole_CAD_source_import_quality_verified=False,goal_complete=False,engineering_prototype_design_complete=False)
decision['previous_936_source_variant']=dict(source_plan='mechanical/ROOT_BUSHING_INSTANCE_PLAN.json',source_instances=936,local_preview_instances=136,source_plan_sha256=sha('mechanical/ROOT_BUSHING_INSTANCE_PLAN.json'))
decision['thermal_core_native_scope']['current965_native_assembly_or_geometry_credit']=False
decision['internal_work_remaining']=[s.replace('Whole936','Whole965') for s in decision['internal_work_remaining']]
decision['active_next_work_item']=dict(parent_id='B03',same_candidate='mechanical/INPUT_CAP_MOUNT_INSTANCE_PLAN.json',next_action='Resolve C203 near-CHB thermal/ripple lifetime and qualified board-to-CHB low-inductance termination; F201/F202 coordination and fuse footprint; actual clamp retention and complete tool access; continue protected battery/PMM, full STOP/heat/propulsion controlled ICD.',read_inputs=['mechanical/INPUT_CAP_MOUNT_BRIEF.md','ecad/C203_MECHANICAL_INTERFACE.json','power/INPUT_PASSIVE_DESIGN.md'])
dump('results/DELIVERY_DECISION.json',decision)
rows=list(csv.DictReader((A/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig')));before=list(csv.DictReader((A/'history/20260909_V13_before_cap_mount/SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig')))
assert len(rows)==37 and {r['id']:r['status'] for r in rows}=={r['id']:r['status'] for r in before}
for r in rows:
 if r['id'] in ['A05','B03','B05']:
  note=' | V14 C203安装候选新增29实例、改甲板四孔；三态各79对/35接触、实际封装/原生网络绑定通过。夹紧力、热、纹波、CHB端接及整机闭环仍开放。'
  if note not in r['new_evidence']:r['new_evidence']+=note
 if r['id']=='B03':r['execution_state']='C203_NOMINAL_INSTALLATION_AND_ECAD_DATUM_BOUND__FUNCTION_AND_QUALIFICATION_OPEN'
with (A/'SYSTEM_CLOSURE_MATRIX.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
dump('results/SHARED_BATTERY_READONLY_REVIEW.json',dict(schema='WP10_SHARED_BATTERY_REVIEW_CURRENT_POINTER_V3',current_review='results/INPUT_PASSIVE_READONLY_REVIEW.json',current_review_sha256=sha('results/INPUT_PASSIVE_READONLY_REVIEW.json'),scope='Current scalar results equal previously reviewed V13; ERC-order fix independently compared',whole_design_complete=False))
dump('results/SHARED_BATTERY_PATH_REVIEW.json',dict(schema='WP10_SHARED_BATTERY_PATH_REVIEW_V3',calculations_sha256=sha('power/SHARED_BATTERY_PATH_CALCULATIONS.json'),readonly_review='results/INPUT_PASSIVE_READONLY_REVIEW.json',readonly_review_sha256=sha('results/INPUT_PASSIVE_READONLY_REVIEW.json'),case_count=192,check_count=36,whole_design_complete=False))
sel=read('power/POWER_CHAIN_SELECTION.json');sel['input_capacitor_mechanical_interface']='ecad/C203_MECHANICAL_INTERFACE.json';sel['current_mechanical_source_plan']='mechanical/INPUT_CAP_MOUNT_INSTANCE_PLAN.json';dump('power/POWER_CHAIN_SELECTION.json',sel)
detail=visual['detail_image'];context=visual['context_image'];viewer='http://127.0.0.1:3245/'+urllib.parse.quote(A.as_posix(),safe='/:')+'?file=mechanical%2Finput_cap_detail.step.py';viewctx=viewer.replace('input_cap_detail','input_cap_integration')
doc=f'''# WP10 V14：C203输入电容机械安装候选

当前候选已增加29个安装实例、修改上甲板4个孔，总源表965实例。C203正负极、实际KiCad封装和整星坐标已绑定。整机详细设计尚未闭环，原37行裁决状态保持：13个有范围的子项完成，19个内部设计开放，4个外部接口未绑定，1个实物项目未执行。

[查看29件安装架]({viewer}) · [查看37件局部安装关系]({viewctx}) · [整合包](WP10_IMPLEMENTATION_DELTA.zip)

![安装架]({detail})

本次新增真实源：[参数与安装约束](mechanical/INPUT_CAP_MOUNT_BRIEF.md)、[参数JSON](mechanical/INPUT_CAP_MOUNT_DESIGN.json)、[保持架构建器](mechanical/input_cap_mount_common.py)、[965实例源表](mechanical/INPUT_CAP_MOUNT_INSTANCE_PLAN.json)、[29行安装BOM](mechanical/INPUT_CAP_INSTALLATION_BOM.csv)、[CAD/ECAD接口](ecad/C203_MECHANICAL_INTERFACE.json)。C203沿用电气BOM已有物料，安装BOM明确禁止重复计购。STEP可导入SolidWorks；本轮没有声称生成965件原生SLDASM。

采用Chemi-Con ELXG101VSN222MR50S，名义Ø30×50、最大Ø31×52。本体端封贴PCB x=-7，厚1.6；pad1正极y=-5，pad2负极y=+5。最短引脚通过板后有1.9mm名义投影。最大外形末端沿−X保留3mm泄压空间。尺寸与使用限制依据[厂家产品页](https://www.chemi-con.co.jp/en/products/detail-condenser.php?part_number=ELXG101VSN222MR50S)和[厂家安装注意事项](https://www.chemi-con.co.jp/products/relatedfiles/capacitor/catalog/al-precaution-e.pdf)；本体是标识清楚的尺寸外形，未伪造OEM内部结构和引脚形状。

两处下挂分体箍中心x=-48/-20，PEEK名义衬套配合Ø30本体。甲板孔y=±32.5，下箍孔y=±22.5。实查发现并修复4个螺钉头埋入竖腿及2个被连接筋填回的板孔；原失败回执保留。三态分别执行79对精确BRep检查、35个必须接触、10个外形/端子/泄压空间检查、4个工具末段检查，均通过。甲板去料108.950433mm³，仅对应4个Ø3.4通孔。额外10项实际电路/封装/坐标判据通过。证据：[精确结果](results/INPUT_CAP_MOUNT_EXACT.json)、[只读复核](results/INPUT_CAP_MOUNT_READONLY_REVIEW.json)、[名义紧固件叠层](results/INPUT_CAP_FASTENER_STACK.json)。几何接触不代表夹紧力或载荷保持通过。

原生电气保持201位号、11页、原99位号父本；435项连接/反例检查通过。修正了先验证后生成封装库的顺序问题：原8条ERC违规由7个error和1个库链接warning构成，现仅消去该warning，仍有7个电源引脚未驱动error。没有更改忽略规则。之前查看页直接写7而机器为8的差异已披露并纠正。当前结论读自机器结果：[原生检查](results/POWER_LOOP_VERIFICATION.json)、[同源只读审阅](results/INPUT_PASSIVE_READONLY_REVIEW.json)。共享电源192场景、36项检查及26项无源器件检查的数值未变。

![局部安装关系]({context})

查看范围和几何验证边界见[图像及验证说明](results/INPUT_CAP_VISUAL_REVIEW.json)。29件视图省略甲板，所以垫圈与法兰之间显示甲板预留厚度；37件三维文件含邻近源实体，以上截图为看清位置，仅显示29件安装架与CHB，隐藏甲板、散热板及两侧设备。这些实体仍参与精确检查。新增29件和修改甲板共30件完成含自交的完整验证；37件拓扑/闭合/正体积通过，但既有背景件全量自交因1400MiB任务保护中止，未取得通过信用。清理闲置内存后完成了上述分项检查。583个旧STEP文本引用审计未找到缺失编号，但原bounds刷新有一次未归因的OCP导入警告，不能据此宣称全部旧源完整或全整机间隙通过。

尚待完成：C203紧邻CHB的温度/纹波自热/寿命及低温条件；实际夹紧力、轴向抗滑、PEEK蠕变和全装配工具路径；板铜箔与CHB输入端接（当前引脚末端直线距离约56mm，不能称近端低阻抗回路）；F201/F202热降额与保护协调；电池/PMM受保护接口与固定、完整STOP/回生动态、全热路径、同修订推进ICD。当前所有整机交付、制造、接电、飞行和实物测试布尔均为false。

内存清理只回收80个闲置工具服务的驻留页，进程结束数0；约3002→3041MiB，页面可按需重新载入。重CAD串行运行，启动门槛2048MiB与512MiB运行保护保持。
'''
(A/'README.md').write_text(doc,encoding='utf-8')
links=[('29件安装架 STEP','mechanical/input_cap_detail.step'),('37件局部总装 STEP','mechanical/input_cap_integration.step'),('965实例表','mechanical/INPUT_CAP_MOUNT_INSTANCE_PLAN.json'),('安装BOM','mechanical/INPUT_CAP_INSTALLATION_BOM.csv'),('原生电路PDF','ecad/wp10_system.pdf'),('精确验证','results/INPUT_CAP_MOUNT_EXACT.json'),('只读审阅','results/INPUT_CAP_MOUNT_READONLY_REVIEW.json'),('CAD/ECAD接口','ecad/C203_MECHANICAL_INTERFACE.json'),('37行闭环矩阵','SYSTEM_CLOSURE_MATRIX.csv'),('当前机器裁决','results/DELIVERY_DECISION.json'),('完整说明','README.md'),('整合ZIP','WP10_IMPLEMENTATION_DELTA.zip')]
body=''.join('<a class="link" href="'+html.escape(path)+'">'+html.escape(label)+'</a>' for label,path in links)
(A/'REVIEW.html').write_text(f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>WP10 V14 C203 安装候选</title><style>body{{font-family:system-ui,"Microsoft YaHei",sans-serif;background:#eef2f5;color:#172c37;margin:0}}main{{max-width:1180px;margin:auto;padding:38px 24px}}h1{{font-size:32px}}.note{{background:#fff1d7;padding:18px;border-left:4px solid #bb7200}}.cards{{display:flex;gap:16px;flex-wrap:wrap;margin:25px 0}}.card{{padding:18px 24px;background:white;flex:1;min-width:170px;border-radius:10px}}b{{display:block;font-size:28px}}img{{width:100%;border-radius:12px;margin:15px 0}}.link{{display:inline-block;margin:6px;padding:12px 16px;background:#fff;color:#075f71;border-radius:7px}}p{{line-height:1.8}}.cta{{background:#095e6b;color:white;padding:13px 20px;border-radius:6px;display:inline-block;margin:8px 8px 8px 0}}</style><main><p>航天服务星 · B601 DM · 同一 WP10 候选</p><h1>C203 输入电容机械安装候选</h1><div class="note">本轮实际改件已完成几何与接口核对。整机机电设计仍开放；未制造、未接电，未获得飞行放行。</div><div class="cards"><div class="card"><b>965</b>当前三态源实例</div><div class="card"><b>29</b>新增安装实例</div><div class="card"><b>79 × 3</b>局部精确实体对</div><div class="card"><b>{v['ERC_count']}</b>仍开放的ERC问题</div></div><a class="cta" href="{viewer}">打开安装架三维模型</a><a class="cta" href="{viewctx}">打开局部装配三维模型</a><img src="{detail}" alt="C203横卧电容、端子板和保持架，甲板省略"><p>四个甲板孔已外移至y±32.5；两个板孔已改为连接筋合并后钻孔。三态各35个必需接触及泄压/工具末段检查通过。PCB铜箔、CHB端接、夹紧力与热环境仍需完成。</p><img src="{context}" alt="37件局部设备舱源模型"><p>电气保留201位号和11页；ERC修复消除的是1个封装库warning，其余7个error保留。旧热模型与38件SolidWorks热核不取得本次965实例的整机信用。</p>{body}</main></html>''',encoding='utf-8')
page=A/'REVIEW.html';s=page.read_text(encoding='utf-8');s=s.replace('<p>电气保留201位号','<p>上图仅显示29件安装架与CHB，其余7组邻件为观察而隐藏，仍在三维文件和精确检查中。新增件和修改甲板共30件完成含自交验证；既有背景件全量自交触发内存保护，保留为未完成。</p><p>电气保留201位号');page.write_text(s,encoding='utf-8')
print(json.dumps(dict(revision=decision['revision'],instances=965,ERC=v['ERC_count'],goal_complete=False)))
