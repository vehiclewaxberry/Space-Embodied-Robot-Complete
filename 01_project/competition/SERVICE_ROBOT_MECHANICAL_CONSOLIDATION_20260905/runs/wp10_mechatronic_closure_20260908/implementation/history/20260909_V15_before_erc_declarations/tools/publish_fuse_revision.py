"""Integrate reviewed V15 power changes into the same WP10 delivery."""
from pathlib import Path
import json,hashlib,csv,html,urllib.parse,collections
A=Path(__file__).resolve().parents[1]
def read(q):return json.loads((A/q).read_text(encoding='utf-8-sig'))
def sha(q):return hashlib.sha256((A/q).read_bytes()).hexdigest()
def dump(q,v):(A/q).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
v=read('results/POWER_LOOP_VERIFICATION.json');c=read('power/INPUT_PASSIVE_CALCULATIONS.json');s=read('power/SHARED_BATTERY_PATH_CALCULATIONS.json');f=read('power/INPUT_FUSE_COORDINATION.json');g=read('results/INPUT_CAP_MOUNT_EXACT.json');visual=read('results/INPUT_CAP_VISUAL_REVIEW.json')
assert v['all_connectivity_checks_passed'] and c['passed'] and s['checks_passed'] and f['passed'] and g['passed']
for obj,key in [(c,'bindings'),(s,'inputs'),(s,'source_scripts'),(f,'inputs'),(g,'inputs'),(visual,'source_bindings'),(visual,'inspected_images_sha256')]:assert all(sha(q)==h for q,h in obj[key].items())
for p in ['results/INPUT_PASSIVE_READONLY_REVIEW.json','results/INPUT_CAP_MOUNT_READONLY_REVIEW.json']:
 r=read(p);assert r['review_complete'] and all(sha(q)==h for q,h in r['reviewed_files'].items())
for n in ['native_delta_input_protection_v15','native_delta_fuse_footprint_export_v15','native_delta_cap_binding_v15']:
 r=read('logs/'+n+'.run.json');assert r['status']=='COMPLETED' and r['returncode']==0
assert read('results/INPUT_PASSIVE_FOOTPRINT_NATIVE.json')['footprint_parse_and_export_pass']
d=read('results/DELIVERY_DECISION.json')
d.update(schema='WP10_IMPLEMENTATION_DELIVERY_V15',revision='V15_SELECTED_INPUT_FUSE_AND_NATIVE_BINDING',review_revision='V15_SELECTED_INPUT_FUSE_AND_NATIVE_BINDING',status='F201_PAD_AND_F202_SELECTION_INTEGRATED__FAULT_COORDINATION_AND_WHOLE_MECHATRONIC_CLOSURE_OPEN',ERC_open=v['ERC_count'],ERC_types=v['ERC_types'],shared_battery_DC_checks=s['check_count'],input_passive_checks=c['check_count'],input_fuse_coordination_checks=f['check_count'],input_fuse_coordination='power/INPUT_FUSE_COORDINATION.json',input_passive_heat_rows=4032,F201_native_footprint_bound=True,F202_MPN='MDA-V-6-R',F202_native_value_bound=True,F202_footprint_and_assembly_bound=False,F201_F202_protection_coordination_verified=False,protection_coordination_verified=False,goal_complete=False,engineering_prototype_design_complete=False)
d['active_next_work_item']=dict(parent_id='B03',same_candidate='mechanical/INPUT_CAP_MOUNT_INSTANCE_PLAN.json',next_action='Complete the selected input protection circuit installation and actual conductor/PCB/CHB termination; bind inrush, fuse/BMS/MOSFET fault behavior and wire damage limits. Continue C203 ripple/temperature, battery/PMM protected interface, STOP/regen thermal dynamics and same-revision propulsion ICD; preserve original37 requirements.',read_inputs=['power/INPUT_PASSIVE_DESIGN.md','power/INPUT_FUSE_COORDINATION.json','ecad/C203_MECHANICAL_INTERFACE.json'])
dump('results/DELIVERY_DECISION.json',d)
rows=list(csv.DictReader((A/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig')))
before=list(csv.DictReader((A/'history/20260909_V14_before_fuse_coordination/SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig')))
assert len(rows)==37 and {r['id']:r['status'] for r in rows}=={r['id']:r['status'] for r in before}
for r in rows:
 if r['id']=='B03':
  note=' | V15 F201原厂9.35mm焊盘中心距已绑定；F202=MDA-V-6-R进入原理图/BOM；典型冷阻计入192场景和4032行热账，保护协调与布板/端接仍开放。'
  if note not in r['new_evidence']:r['new_evidence']+=note
  r['execution_state']='SELECTED_INPUT_FUSES_NATIVE_AND_COLD_LOSS_BOUND__FAULT_AND_INSTALLATION_OPEN'
with (A/'SYSTEM_CLOSURE_MATRIX.csv').open('w',encoding='utf-8-sig',newline='') as h:w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
dump('results/SHARED_BATTERY_READONLY_REVIEW.json',dict(schema='WP10_SHARED_BATTERY_REVIEW_CURRENT_POINTER_V4',current_review='results/INPUT_PASSIVE_READONLY_REVIEW.json',current_review_sha256=sha('results/INPUT_PASSIVE_READONLY_REVIEW.json'),scope='V15 independent two-current Newton and complete source-to-output thermal recomputation; not dynamic or installed thermal qualification',whole_design_complete=False))
dump('results/SHARED_BATTERY_PATH_REVIEW.json',dict(schema='WP10_SHARED_BATTERY_PATH_REVIEW_V4',calculations_sha256=sha('power/SHARED_BATTERY_PATH_CALCULATIONS.json'),readonly_review='results/INPUT_PASSIVE_READONLY_REVIEW.json',readonly_review_sha256=sha('results/INPUT_PASSIVE_READONLY_REVIEW.json'),case_count=s['case_count'],check_count=s['check_count'],whole_design_complete=False))
sel=read('power/POWER_CHAIN_SELECTION.json');sel.update(input_capacitor_mechanical_interface='ecad/C203_MECHANICAL_INTERFACE.json',current_mechanical_source_plan='mechanical/INPUT_CAP_MOUNT_INSTANCE_PLAN.json',input_fuse_coordination='power/INPUT_FUSE_COORDINATION.json');dump('power/POWER_CHAIN_SELECTION.json',sel)
fuse_url='https://www.eaton.com/content/dam/eaton/products/electronic-components/resources/data-sheet/eaton-1025hc-surface-mount-ceramic-tube-fuses-data-sheet.pdf'
aux_url='https://www.eaton.com/content/dam/eaton/products/electronic-components/resources/data-sheet/eaton-mda-time-delay-ceramic-tube-fuses-data-sheet.pdf'
design=f'''# WP10 输入保险丝、电容与共享电源：当前 V15 设计

本文件与原生网表、INPUT_PASSIVE_SELECTION.json、INPUT_FUSE_COORDINATION.json 同版本。既定机械臂360W、辅助16.8W及制动控制1W/启动偏置0.25W分账保持；没有下调任务负载。

F201=1025HC30-RTR。依据[Eaton10572，2025年6月]({fuse_url})第2页，实际封装每焊盘3.25×3.43mm、两外缘跨距12.60mm，所以中心距9.35mm、内距6.10mm。第2页推荐3oz铜、20–30A走线至少10mm宽；本轮完成封装及原生属性，尚未完成PCB电流/温升路径。125°C处降额曲线约0.86±0.01，为图读范围，未冒充保证曲线或实际器件温度。30A、72VDC、500A分断的特定测试L/R<1µs，不能直接继承到未知电池短路回路。

F202=MDA-V-6-R，轴向引线版本；依据[Eaton2002，2025年11月]({aux_url})及THN原厂6A慢断建议。6A、125VDC、10kA分断，直流试验L/R未给。典型冷阻18mΩ（25°C、<0.1In），典型熔化I²t=98.1A²s是在60A下取得，不是所有故障电流下通用计时常数，也不是总清除上界。8.1A及12A的最大动作时间分别3600s、120s；最小动作包络缺失。额定电流条目仅记“4hours”，本设计不擅自增加min/max限定。持续3A异常不能从这些资料推出及时切除保证。

MDA轴向本体长32.82±0.79mm，直径6.76mm为参考值，引线Ø0.81±0.05mm，单侧直引线38.1mm为参考长度。弯脚PCB孔距、离板高度和保持方式仍待设计；直引线长度未冒充PCB孔距。当前没有为F202伪造封装或安装实体。

当前辅助支路总电阻场景为0.018/0.040Ω：包含保险丝一次，其余回路分别为理想0/未测0.022Ω。原0Ω支路数据保留在V14历史中。192场景中的96场景因该修改改变，其余96及SBP132锚点保持。电压是带载保护包侧电压场景；求得ON代数解不代表启动许可或动态稳定。实际热态电阻和输入浪涌未知。

INPUT_PASSIVE_HEAT_LOADS.csv 的4032行是 SHARED_BATTERY_HEAT_LOADS.csv 的细分替代，二者不能相加。F201与F202的冷阻损耗均从原支路分配中拆出。F202候选场景冷阻损耗约7.26–27.20mW；6A时原厂典型压降对应0.996W，而冷阻公式仅0.648W，说明冷阻不能承担全电流热态损耗保证。PCB和连接件损伤限值、上游BMS切断时序及STOP失电响应未验证。

C203=ELXG101VSN222MR50S。名义2200µF±20%、100V；初始20°C/120Hz的DF推得ESR上界0.113036Ω，寿命后上界0.376787Ω；30kHz阻抗0.03Ω不替代全温全频保证。纹波谱、紧邻CHB热环境、低温并联需求及近端铜箔/端接未完成。名义29件保持架和修改甲板已在965实例源表中，正负极和新网表已重新绑定；实际夹紧力、抗滑、蠕变及整体装配不继承几何通过。

本轮201位号/11页原理图与435项连接检查通过；ERC仍有7个电源输入未驱动错误。共享电源37检查、输入无源37检查和保险来源/反例8检查通过；这些检查没有授予故障保护、全热设计、上电或飞行资格。
'''
(A/'power/INPUT_PASSIVE_DESIGN.md').write_text(design,encoding='utf-8')
detail=visual['detail_image'];context=visual['context_image'];svg='review/input_passive_footprint/Fuse_Eaton_1025HC_20to30A_3p25x3p43_P9p35.svg'
viewer='http://127.0.0.1:3245/'+urllib.parse.quote(A.as_posix(),safe='/:')+'?file=mechanical%2Finput_cap_detail.step.py'
viewctx=viewer.replace('input_cap_detail','input_cap_integration')
readme=f'''# WP10 V15：输入保护选件、封装与机电接口集成

F201原厂焊盘已进入原理图封装属性，F202具体型号MDA-V-6-R已进入同一201位号电气系统和BOM。辅助支路包含选定保险丝典型冷阻；共享电源192场景和4032行细分热账已复算。当前三态源表仍为965实例，C203与新网表的接口已重验；本轮没有新增机械实例。

整机机电详细设计尚未闭环。原37行状态保持13个有范围子项完成、19个内部设计开放、4个外部接口未绑定、1个实物项目未执行。ERC仍为7个error、0个warning。当前未制造、未接电、未获得飞行放行。

[完整查看页](REVIEW.html) · [整合ZIP](WP10_IMPLEMENTATION_DELTA.zip) · [原生电路PDF](ecad/wp10_system.pdf) · [当前BOM](power/SELECTED_BOM.csv) · [设计说明](power/INPUT_PASSIVE_DESIGN.md)

F201焊盘中心距9.35mm、每焊盘3.25×3.43mm；12.60mm是外缘总跨距。实际KiCad库解析与SVG导出通过。[查看原生封装SVG]({svg})。3oz铜和10mm走线建议仍需要真实布板与热验证。F202采用6A慢断轴向候选，原厂完整PDF已缓存锁定；弯脚、安装及保护协调仍开放。

共享电源37检查、输入无源37检查、保险来源和反例8检查通过。只读审阅者独立解384个状态，最大电流/电压差约1.07e-14；4032热单元独立重建，CSV能量残差约3.41e-13W。两个热CSV是粗分/细分关系，禁止相加。冷阻、典型效率和假定导通解不构成实物或动态通过。证据：[独立复核](results/INPUT_PASSIVE_READONLY_REVIEW.json)、[保险协调边界](power/INPUT_FUSE_COORDINATION.json)、[共享电源结果](power/SHARED_BATTERY_PATH_CALCULATIONS.json)、[ERC](results/POWER_LOOP_ERC.json)。

[打开29件安装架]({viewer}) · [打开37件局部三维]({viewctx}) · [29件STEP](mechanical/input_cap_detail.step) · [37件STEP](mechanical/input_cap_integration.step)

![当前C203安装候选]({detail})

C203几何源保持V14；在新XML下重新执行三态各79对实体、35个必需接触、10个空间和4个工具末段检查，另10项接口判据通过。[当前精确结果](results/INPUT_CAP_MOUNT_EXACT.json)、[机械只读复核](results/INPUT_CAP_MOUNT_READONLY_REVIEW.json)、[CAD/ECAD接口](ecad/C203_MECHANICAL_INTERFACE.json)。原新增29件与修改甲板共30件的含自交验证仍有效；旧37件背景全量自交受内存保护中止，未取得通过信用。965实例尚非已验证的原生SolidWorks全总装。

![C203与CHB安装关系]({context})

上图显示29件安装架与CHB，其余7组邻件仅为观察隐藏，仍在源模型与精确检查中。板到CHB输入端的实际线路、保持力、纹波温升和连续动作仍待完成。已有STEP可导入SolidWorks，不冒充新原生整机SLDASM。

后续沿同一责任项完成实际保护回路安装、线材/PCB/连接器损伤边界及启动和故障时序，继而继续整星热路径、受保护电池/PMM和推进同修订接口。所有原有必要工作继续保留于[37行闭环表](SYSTEM_CLOSURE_MATRIX.csv)及[机器裁决](results/DELIVERY_DECISION.json)。

本轮清理128个闲置工具服务的驻留页，未结束应用。清理期间可用内存受并行活动影响波动，并未声称净增加；重几何在2736MiB可用内存下启动，38.85s完成，2048/512MiB门槛保持。
'''
(A/'README.md').write_text(readme,encoding='utf-8')
links=[('原生电路PDF','ecad/wp10_system.pdf'),('当前电气BOM','power/SELECTED_BOM.csv'),('输入保护设计说明','power/INPUT_PASSIVE_DESIGN.md'),('F201实际封装SVG',svg),('保险协调与反例','power/INPUT_FUSE_COORDINATION.json'),('输入无源只读复核','results/INPUT_PASSIVE_READONLY_REVIEW.json'),('C203精确检查','results/INPUT_CAP_MOUNT_EXACT.json'),('CAD/ECAD接口','ecad/C203_MECHANICAL_INTERFACE.json'),('安装BOM','mechanical/INPUT_CAP_INSTALLATION_BOM.csv'),('29件安装架STEP','mechanical/input_cap_detail.step'),('37件局部STEP','mechanical/input_cap_integration.step'),('965实例源表','mechanical/INPUT_CAP_MOUNT_INSTANCE_PLAN.json'),('37行闭环矩阵','SYSTEM_CLOSURE_MATRIX.csv'),('当前机器裁决','results/DELIVERY_DECISION.json'),('完整说明','README.md'),('整合ZIP','WP10_IMPLEMENTATION_DELTA.zip')]
body=''.join(f'<a class="link" href="{html.escape(p)}">{html.escape(n)}</a>' for n,p in links)
(A/'REVIEW.html').write_text(f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>WP10 V15 输入保护与机电集成</title><style>body{{font-family:system-ui,"Microsoft YaHei",sans-serif;background:#eef2f5;color:#172c37;margin:0}}main{{max-width:1180px;margin:auto;padding:36px 24px}}p{{line-height:1.8}}.note{{background:#fff1d7;padding:18px;border-left:4px solid #bb7200}}.cards{{display:flex;gap:16px;flex-wrap:wrap;margin:25px 0}}.card{{padding:18px;background:white;flex:1;min-width:160px;border-radius:10px}}b{{display:block;font-size:26px}}img{{width:100%;border-radius:12px;margin:15px 0}}.link{{display:inline-block;margin:6px;padding:12px 16px;background:white;color:#075f71;border-radius:7px}}.cta{{display:inline-block;padding:13px 20px;background:#095e6b;color:white;margin:8px;border-radius:6px}}</style><main><p>航天服务星 · B601 DM · 同一 WP10 候选</p><h1>V15 输入保护选件与机电接口集成</h1><div class="note">F201封装、F202具体型号和冷阻已进入原理图/BOM/计算；整机设计与故障保护仍开放。未制造、未接电，未获得飞行放行。</div><div class="cards"><div class="card"><b>201 / 11</b>电气位号 / 页</div><div class="card"><b>192</b>共享电源场景</div><div class="card"><b>4032</b>细分热账行</div><div class="card"><b>7</b>仍开放的ERC错误</div></div><p>F201焊盘中心距9.35mm，12.60mm为外缘总跨距。F202选定MDA-V-6-R，典型冷阻18mΩ在辅助支路计入一次。保护动作、输入浪涌、热态阻值和实际布板/端接仍需完成；两个热CSV不能相加。</p>{body}<h2>当前机械安装关系</h2><p>965实例源表保持；本轮重验了C203与新网表的绑定，三态各79实体对/35必需接触及空间、工具末段检查通过。实际保持力、热环境、近端线路和整机装配仍开放。</p><a class="cta" href="{viewer}">查看29件安装架</a><a class="cta" href="{viewctx}">查看37件局部三维</a><img src="{detail}" alt="C203安装架，甲板省略"><img src="{context}" alt="C203与CHB局部安装关系"><p>第二张图为观察隐藏7组邻件，源模型与检查仍包含它们。30个新增/修改实体有含自交验证；旧背景件全量自交受内存保护中止。原37行状态仍为13个限定子项完成、19内部开放、4外部接口未绑定、1实物未执行。</p></main></html>''',encoding='utf-8')
dump('results/FUSE_REVISION_INTEGRATION.json',dict(schema='WP10_V15_INTEGRATION',revision=d['revision'],evidence={q:sha(q) for q in ['results/DELIVERY_DECISION.json','SYSTEM_CLOSURE_MATRIX.csv','power/INPUT_PASSIVE_DESIGN.md','ecad/C203_MECHANICAL_INTERFACE.json','power/POWER_CHAIN_SELECTION.json','README.md','REVIEW.html']},original37_statuses_preserved=True,previous_goal_turn_classification='NO_PROGRESS_STATUS_QUERY_ONLY; continued executable V15 source work now',current_turn_classification='PROGRESS_SOURCE_NATIVE_MODEL_AND_CAD_ECAD_BINDING',goal_complete=False))
print(json.dumps(dict(revision=d['revision'],ERC=v['ERC_count'],source_instances=965,goal_complete=False)))
