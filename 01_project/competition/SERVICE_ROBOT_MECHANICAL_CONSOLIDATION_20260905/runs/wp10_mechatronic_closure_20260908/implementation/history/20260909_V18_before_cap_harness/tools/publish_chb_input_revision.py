"""Publish V18 only after source-bound native, geometry and visual evidence."""
from pathlib import Path
import json,csv,hashlib,collections,html,sys
A=Path(__file__).resolve().parents[1];H=A/'history/20260909_V17_before_chb_input'
REV='V18_CHB_INPUT_TERMINAL_AND_MOUNT'
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def dump(p,v):(A/p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def validate(require_regression=True):
 for p in ['results/CHB_INPUT_COPPER_V18.json','results/CHB_INPUT_MECHANICAL_V18.json','results/CHB_INPUT_PARAMETRICS_V18.json']:
  v=read(p);assert v['passed'] is True;assert all(sha(q)==h for q,h in v['inputs'].items())
 c=read('results/CHB_INPUT_COPPER_V18.json');assert len(c['checks'])==6 and len(c['faults'])==7 and all(x['passed'] for x in c['checks']) and all(x['rejected'] for x in c['faults'])
 m=read('results/CHB_INPUT_MECHANICAL_V18.json');assert set(m['states'])=={'service','parking','released'} and all(x['passed'] and x['source_rows']==970 and x['unchanged_parent_rows']==965 for x in m['states'].values())
 p=read('results/CHB_INPUT_PARAMETRICS_V18.json');assert len(p['tests'])==3 and all(x['passed'] for x in p['tests'])
 n=read('results/CHB_INPUT_NATIVE_V18.json');assert n['board_sha256']==sha('ecad/wp10_chb_input.kicad_pcb') and n['source_xml_sha256']==sha('ecad/wp10_system.xml')
 r=read('results/CHB_INPUT_READONLY_REVIEW_V18.json');assert r['review_complete'] and r['status']=='PASS_SCOPED_SOURCE_AND_EXISTING_JSON' and all(sha(q)==h for q,h in r['reviewed_files'].items())
 ex=read('results/CHB_INPUT_LAYOUT_EXPORT_V18.json');assert ex['native_export'] and ex['board_sha256']==n['board_sha256'] and all(sha(q)==h for q,h in ex['outputs'].items())
 drc=read('results/CHB_INPUT_DRC_NATIVE_V18.json');assert drc['violations']==[] and drc['unconnected_items']==[] and len(drc['ignored_checks'])==5
 erc=read('results/ERC_MCP_CROSSCHECK.json');assert len(erc['inputs'])==16 and all(sha(q)==h for q,h in erc['inputs'].items())
 assert 'Errors: 0  Warnings: 0' in str(erc['result'])
 vis=read('results/CHB_INPUT_VISUAL_REVIEW_V18.json');assert vis['actual_images_viewed'] and len(vis['images'])==3 and all(sha(q)==h for q,h in vis['images'].items())
 for kind,count in [('pcb',1),('assembly',11)]:
  p=read('results/CHB_INPUT_review_'+kind+'_V18.json');assert p['target']=='mechanical/chb_input_'+kind+'.step' and p['target_sha256']==sha(p['target'])
  assert set(p['records'])=={'results/CHB_INPUT_review_'+kind+'_'+q+'_V18.json' for q in ['refs','validate']}
  for record in p['records']:
   v=read(record);assert v['ok'] is True
   if '_validate_' in record:assert v['failureCount']==0 and v['occurrenceCount']==count
 for suffix in ['', '_DETAIL']:
  p=read('results/CHB_INPUT_SNAPSHOT'+suffix+'_V18.json');assert p['ok'] is True and len(p['outputs'])==1
  assert p['target_sha256']==sha('mechanical/chb_input_assembly.step')
  assert p['published_image']=='review/CHB_INPUT_ASSEMBLY'+suffix+'_V18.png'
  assert p['published_sha256']==sha(p['published_image'])==hashlib.sha256(Path(p['outputs'][0]['path']).read_bytes()).hexdigest()
 parent=read('results/PARENT_INTEGRITY.json');assert parent['count']==444 and parent['all_parent_indexed_bytes_unchanged'] and parent['mismatches']==[]
 rows=list(csv.DictReader((A/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig')));old=list(csv.DictReader((H/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig')))
 assert len(rows)==37 and [(q['id'],q['status']) for q in rows]==[(q['id'],q['status']) for q in old]
 if require_regression:
  t=read('results/CHB_INPUT_PUBLICATION_TESTS_V18.json');assert t['passed'] and t['publisher_sha256']==sha('tools/publish_chb_input_revision.py') and len(t['faults'])==5 and all(q['rejected'] for q in t['faults'])
 return dict(rows=rows,copper=c,mechanical=m,native=n,visual=vis)
def publish(v):
 rows=v['rows'];d=json.loads((H/'results/DELIVERY_DECISION.json').read_text())
 d.update(schema='WP10_IMPLEMENTATION_DELIVERY_V18',revision=REV,review_revision=REV,status='CHB_INPUT_NATIVE_PCB_AND_FIVE_MOUNT_INSTANCES_INTEGRATED__HARNESS_AND_WHOLE_ENGINEERING_OPEN',candidate_source_components=970,source_candidate_components=970,current_source_plan='mechanical/CHB_INPUT_INSTANCE_PLAN.json',new_CHB_terminal_board='ecad/wp10_chb_input.kicad_pcb',CHB_terminal_DRC_errors=0,CHB_terminal_DRC_warnings=0,CHB_terminal_DRC_ignored_rules=5,CHB_terminal_copper_checks=6,CHB_terminal_faults_rejected=7,CHB_terminal_parametric_checks=3,CHB_terminal_source_assembly_instances=11,CHB_terminal_to_C203_route_complete=False,goal_complete=False,engineering_prototype_design_complete=False,manufacture_release=False,power_on_authorized=False,flight_release=False,physical_tests_executed=False)
 d['internal_work_remaining']=[x.replace('Whole965','Whole970') for x in d['internal_work_remaining']]
 d['active_next_work_item']['next_action']='B03: route actual paired C203 conductors to the now-built CHB terminal, add strain relief and main/control-return wire endpoints; then qualify NPTH/CAM/solder, ripple/startup and fuse/BMS/MOSFET coordination. Whole-system duties remain open.'
 d['CAD_viewer_runtime_status']=read('results/CHB_INPUT_VIEWER_V18.json')['status']
 note=' | V18 CHB输入原生PCB及5安装实例进入三态970行；旧965行不变；新板DRC0/0、铜6检查/7反例、参数扰动3项、局部16对/6接触/14接口通过。C203/主馈/控制回线与制造资格仍开放。'
 for r in rows:
  if r['id']=='B03' and note not in r['new_evidence']:r['new_evidence']+=note
 # Physical destinations are now real holes; route/cut/termination status stays open.
 f=A/'power/C203_WIRE_SCHEDULE.csv';wires=list(csv.DictReader(f.open(encoding='utf-8-sig')))
 for r in wires:
  num='1' if r['to_electrical_pin']=='U203.1' else '4';assert r['to_electrical_pin'] in ['U203.1','U203.4']
  r['to_physical_termination']='CHB_INPUT_PCB.CAP_'+num;r['status']='TWO_PHYSICAL_BOARD_ENDPOINTS_DEFINED_ROUTE_AND_STRAIN_RELIEF_OPEN'
  assert r['route_complete']=='False' and r['termination_qualified']=='False' and not r['cut_length_mm']
 with f.open('w',newline='',encoding='utf-8-sig') as out:w=csv.DictWriter(out,fieldnames=list(wires[0]));w.writeheader();w.writerows(wires)
 interface=dict(schema='WP10_CHB_INPUT_MECHANICAL_INTERFACE_V18',electrical_ref='U203',mechanical_module_id='U202_CHB',input_pins_only=['1','2','4'],native_board='ecad/wp10_chb_input.kicad_pcb',endpoint_table='ecad/CHB_INPUT_ENDPOINTS_V18.csv',source_plan='mechanical/CHB_INPUT_INSTANCE_PLAN.json',native_board_sha256=sha('ecad/wp10_chb_input.kicad_pcb'),source_plan_sha256=sha('mechanical/CHB_INPUT_INSTANCE_PLAN.json'),definition_sha256=sha('power/CHB_INPUT_DEFINITION.json'),original_system_xml_sha256=sha('ecad/wp10_system.xml'),terminal_PCB_and_mount_nominal_geometry_complete=True,main_feed_wire_complete=False,control_return_wire_complete=False,C203_route_complete=False,cut_lengths_bound=False,manufacturing_qualified=False,whole_design_complete=False)
 dump('ecad/CHB_INPUT_MECHANICAL_INTERFACE.json',interface);dump('results/DELIVERY_DECISION.json',d)
 with (A/'SYSTEM_CLOSURE_MATRIX.csv').open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 (A/'README.md').write_text('''# WP10 当前 V18：CHB 输入端接板与固定实体

同一候选新增5个安装实例，三态源清单970行，原965行保持。新板DRC0错误/0警告，铜路6检查/7反例和3项实体参数扰动通过；11件局部装配可查看。

- [查看本轮设计与图像](REVIEW.html)
- [原生CHB PCB](ecad/wp10_chb_input.kicad_pcb) / [实际铜图PDF](review/CHB_INPUT_LAYOUT_V18.pdf)
- [11件局部STEP](mechanical/chb_input_assembly.step) / [970行源清单](mechanical/CHB_INPUT_INSTANCE_PLAN.json)
- [设计说明与剩余工作](docs/hardware/CHB_INPUT_V18.md) / [独立只读复核](results/CHB_INPUT_READONLY_REVIEW_V18.json)
- [原37行责任表](SYSTEM_CLOSURE_MATRIX.csv) / [机器裁决](results/DELIVERY_DECISION.json)

整机设计仍开放。C203原板12项DRC、实际配对导线/保持、主馈和使能回线、保护配合、电池/PMM、停止回生/热动态及推进ICD未完成。本轮没有生成970件完整原生SolidWorks总装，也未获制造、上电或飞行放行。
''',encoding='utf-8')
 tr=''.join('<tr>'+''.join('<td>'+html.escape(r[k])+'</td>' for k in ['id','object','status','remaining_design'])+'</tr>' for r in rows)
 viewer=read('results/CHB_INPUT_VIEWER_V18.json');link=('<a href="'+html.escape(viewer['url'],quote=True)+'">交互查看局部装配</a>') if viewer['status']=='RUNNING_HTTP_VERIFIED' else '<span>交互查看器未就绪；可查看下方实际STEP图。</span>'
 page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>WP10 V18 · CHB输入端接</title><style>body{margin:0;background:#f3f4ee;color:#233c35;font:16px/1.75 system-ui,"Microsoft YaHei",sans-serif}main{max-width:1160px;margin:auto;padding:32px 24px}h1{font-size:34px}.cards{display:flex;gap:16px;flex-wrap:wrap}.card{background:white;border:1px solid #cedbd1;border-radius:12px;padding:20px;flex:1;min-width:150px}.big{font-size:34px;font-weight:700;color:#166146}nav{display:flex;gap:18px;flex-wrap:wrap;margin:20px 0}a{color:#116346}.notice{border-left:5px solid #b37a23;padding:12px 18px;background:#fff9e8}img{max-width:100%;height:auto;border:1px solid #d6ddd5}.two{display:grid;grid-template-columns:1fr 1fr;gap:18px}table{border-collapse:collapse;font-size:13px}td,th{padding:9px;border-bottom:1px solid #ccd8cf;text-align:left;vertical-align:top}.scroll{overflow:auto}@media(max-width:760px){.two{grid-template-columns:1fr}}</style><main><small>WP10 · V18 · 同一工程候选 · 2026-09-09</small><h1>CHB输入端接板及固定结构已集成</h1><p>主馈、电容支线与使能端已落实到原生PCB、具体孔位和装配实体。</p><div class="cards"><div class="card"><div class="big">0 / 0</div>新CHB板 DRC错误 / 警告</div><div class="card"><div class="big">6 + 7</div>铜检查 / 故障反例通过</div><div class="card"><div class="big">970</div>三态源清单；原965行保持</div><div class="card"><div class="big">11</div>可查看的局部装配实例</div></div><nav>__VIEWER__<a href="mechanical/chb_input_assembly.step">下载局部STEP</a><a href="ecad/wp10_chb_input.kicad_pcb">原生PCB</a><a href="WP10_IMPLEMENTATION_DELTA.zip">下载当前包</a></nav><p class="notice">整机详细设计尚未完成。实际C203导线、主馈和控制回线、应力释放及保护配合仍开放；原C203板的12项DRC未消除。新板0/0覆盖启用规则，原5项默认忽略保持。未制造、上电或飞行放行。</p><h2>实际装配</h2><img src="review/CHB_INPUT_ASSEMBLY_V18.png" alt="由当前11件STEP生成的CHB、C203与端接板装配图"><p>新增输入板、两个阶梯垫柱和两个螺钉。旧965实例逐行保持；970件为源清单，本轮没有完成970件SolidWorks整机原生装配或连续动作验收。</p><div class="two"><div><img src="review/CHB_INPUT_ASSEMBLY_DETAIL_V18.png" alt="同STEP隐藏5个C203背景件后的6件端接细节"><p>细节图隐藏5个C203背景件，仅影响查看。螺钉两端名义间距6.45mm；孔位公差、预紧与蠕变仍需验证。</p></div><div><a href="review/CHB_INPUT_LAYOUT_V18.pdf"><img src="review/CHB_INPUT_LAYOUT_V18.png" alt="原生KiCad导出的CHB输入铜图"></a><p>24×60×1.6mm，双面各70μm铜。成品孔和铜盘为项目尺寸，厂家没有给推荐数值。</p></div></div><nav><a href="results/CHB_INPUT_MECHANICAL_V18.json">三态局部检查</a><a href="results/CHB_INPUT_COPPER_V18.json">铜与反例证据</a><a href="results/CHB_INPUT_PARAMETRICS_V18.json">3项实体参数扰动</a><a href="results/CHB_INPUT_DRC_V18.rpt">DRC原始报告</a><a href="results/CHB_INPUT_READONLY_REVIEW_V18.json">限定范围独立审阅</a></nav><h2>仍需落实的导线与整机工作</h2><p>C203两端孔已定义，下一步生成连续配对路线和保持结构，核查弯曲、端部、低电感与安装次序；同时补主馈/使能参考回线和C203单面NPTH工艺。电池/PMM、停止回生热动态和同修订推进ICD继续按原责任表推进。</p><nav><a href="ecad/CHB_INPUT_ENDPOINTS_V18.csv">8个实体端点</a><a href="ecad/CHB_INPUT_MECHANICAL_INTERFACE.json">机电接口</a><a href="mechanical/CHB_INPUT_BOM_V18.csv">新增安装件BOM</a><a href="power/C203_WIRE_SCHEDULE.csv">C203导线状态</a><a href="docs/hardware/CHB_INPUT_V18.md">依据、结果与限制</a><a href="ecad/wp10_system.pdf">12页原系统原理图</a><a href="results/CAP_TERMINAL_DRC_V17.rpt">C203原板12项问题</a></nav><p>主原理图源哈希未变，沿用已验证的ERC0/0及原4项忽略；本轮没有以空白板项目原理图重跑ERC。</p><details><summary>原37行：13限定完成 / 19内部开放 / 4外部接口 / 1实物未执行</summary><div class="scroll"><table><thead><tr><th>ID</th><th>对象</th><th>状态</th><th>剩余设计</th></tr></thead><tbody>__ROWS__</tbody></table></div></details><nav><a href="SYSTEM_CLOSURE_MATRIX.csv">完整责任表</a><a href="results/DELIVERY_DECISION.json">机器裁决</a><a href="mechanical/CHB_INPUT_INSTANCE_PLAN.json">当前源装配清单</a></nav></main></html>'''.replace('__ROWS__',tr).replace('__VIEWER__',link)
 (A/'REVIEW.html').write_text(page,encoding='utf-8')
 evidence=['README.md','REVIEW.html','SYSTEM_CLOSURE_MATRIX.csv','results/DELIVERY_DECISION.json','docs/hardware/CHB_INPUT_V18.md','power/CHB_INPUT_DEFINITION.json','power/C203_WIRE_SCHEDULE.csv','ecad/CHB_INPUT_MECHANICAL_INTERFACE.json','ecad/CHB_INPUT_ENDPOINTS_V18.csv','mechanical/CHB_INPUT_BOM_V18.csv','mechanical/CHB_INPUT_INSTANCE_PLAN.json','ecad/wp10_chb_input.kicad_pcb','ecad/WP10_PASSIVES.pretty/CHB_Input_124_Terminal_V18.kicad_mod','mechanical/chb_input_common.py','mechanical/chb_input_pcb.step','mechanical/chb_input_spacer.step','mechanical/chb_input_screw.step','mechanical/chb_input_assembly.step','tools/publish_chb_input_revision.py','tools/chb_input_cad.py']
 evidence += [p.relative_to(A).as_posix() for p in (A/'results').glob('CHB_INPUT*_V18.json') if p.name!='CHB_INPUT_REVISION_INTEGRATION_V18.json']
 dump('results/CHB_INPUT_REVISION_INTEGRATION_V18.json',dict(revision=REV,evidence={p:sha(p) for p in sorted(set(evidence))},original37_statuses_preserved=True,unchanged_parent_instances=965,added_instances=5,source_candidate_instances=970,whole_design_complete=False,goal_complete=False))
 print(json.dumps(dict(revision=REV,instances=970,DRC_errors=0,DRC_warnings=0,whole_design_complete=False)))
if __name__=='__main__':
 v=validate(require_regression='--check-only' not in sys.argv)
 if '--check-only' in sys.argv:print('V18 publication preconditions passed; no files written')
 else:publish(v)
