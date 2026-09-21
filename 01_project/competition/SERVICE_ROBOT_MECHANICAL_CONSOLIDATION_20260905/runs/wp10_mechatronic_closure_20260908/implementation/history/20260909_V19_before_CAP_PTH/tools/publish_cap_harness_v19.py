"""Publish physical wire delta only after actual geometry and source-bound evidence."""
from pathlib import Path
import json,csv,hashlib,html,sys,urllib.parse
A=Path(__file__).resolve().parents[1];H=A/'history/20260909_V18_before_cap_harness';REV='V19_C203_PHYSICAL_WIRE_ROUTES'
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def dump(p,v):(A/p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def check_decision(d):
 p=read(d['current_source_plan']);counts={s:len(v['rows']) for s,v in p['states'].items()}
 assert d['current_source_plan_sha256']==sha(d['current_source_plan'])
 assert d['current_source_instances_by_state']==counts
 assert set(counts.values())=={d['candidate_source_components']}=={d['source_candidate_components']}=={972}
 assert not any(d[k] for k in ['goal_complete','engineering_prototype_design_complete','manufacture_release','power_on_authorized','flight_release','current_source_plan_whole_fit_verified','current_full_native_assembly_generated'])
def validate_heat():
 t=read('power/CAP_HARNESS_ELECTROTHERMAL_V19.json');active=read('thermal/ACTIVE_HEAT_LOADS_V19.json')
 assert t['passed'] and t['state_count']==384 and t['heat_rows']==4800 and t['correlated_R_bound_scenarios']==1152
 assert len(t['faults'])==10 and all(f['rejected'] for f in t['faults'])
 assert t['local_allocation_tolerance_W']==1e-12 and t['all_other_heat_nodes_unchanged'] and t['cold_actual_capacitor_voltage'] is None
 assert t['actual_ripple_spectrum'] is None and not t['ripple_2p4A_reference_only']['included_in_heat_ledger']
 assert all(sha(p)==h for p,h in t['inputs'].items()) and sha(t['output_csv'])==t['output_sha256']
 assert active['heat_dataset']==t['output_csv'] and active['heat_dataset_sha256']==t['output_sha256']
 assert active['calculation_sha256']==sha(active['calculation']) and active['source_assembly_sha256']==sha(active['source_assembly'])
 assert not active['add_to_parent'] and not active['whole_thermal_verified'] and not t['whole_design_complete']
 review=read('results/CAP_HARNESS_HEAT_READONLY_REVIEW_V19.json')
 assert review['status']=='PASS_SCOPED_FIXED_LEAKAGE_REALLOCATION'
 assert all(sha(p)==h for p,h in review['reviewed_files'].items())
 return t
def validate(regression=True):
 validate_heat()
 source=read('results/C203_WIRE_PTH_SOURCE_CHECK_V19.json')
 assert source['passed'] and all(sha(p)==h for p,h in source['inputs'].items())
 reviewed=read('results/C203_WIRE_PTH_READONLY_REVIEW_V19.json')
 assert reviewed['status']=='PASS_SCOPED_SOURCE_DELTA_WITH_CONTACT_PROFILE_OPEN' and all(sha(p)==h for p,h in reviewed['reviewed_files'].items())
 repair=read('results/C203_WIRE_PTH_NATIVE_CHECK_V19.json')
 assert repair['passed'] and repair['native_readback_executed'] and repair['native_DRC_executed']
 assert all(sha(p)==h for p,h in repair['inputs'].items())
 assert repair['PTH_wire_holes']==2 and repair['NPTH_holes']==6 and repair['rules_unchanged']
 assert repair['remaining_DRC_errors']==6 and not repair['whole_design_complete']
 p=read('results/CAP_HARNESS_PATH_V19.json');g=read('results/CAP_HARNESS_EXACT_V19.json')
 for v in [p,g]:
  assert v['passed'] is True and all(sha(f)==h for f,h in v['inputs'].items())
 assert len(p['checks'])==22 and all(x['passed'] for x in p['checks'])
 assert len(p['faults'])==10 and all(x['rejected'] for x in p['faults'])
 assert set(g['states'])=={'service','parking','released'}
 for st in g['states'].values():
  assert st['passed'] and st['source_rows']==972 and st['unchanged_parent_rows']==970
  assert len(st['wire_geometry'])==2 and len(st['interfaces'])==6 and len(st['exact_pairs'])>=4
  assert all(x['passed'] for x in st['wire_geometry']+st['interfaces']+st['exact_pairs']) and st['fault']['rejected']
 plan=read('mechanical/CAP_HARNESS_INSTANCE_PLAN_V19.json');parent=read(plan['parent_plan'])
 assert plan['parent_plan_sha256']==sha(plan['parent_plan'])
 for state,st in plan['states'].items():
  rows={r['id']:r for r in st['rows']};old={r['id']:r for r in parent['states'][state]['rows']}
  assert len(rows)==972 and set(rows)-set(old)=={'C203_W_PLUS','C203_W_MINUS'} and all(rows[k]==v for k,v in old.items())
  for name in st['added_ids']:
   r=rows[name];assert hashlib.sha256(Path(r['step_path']).read_bytes()).hexdigest()==r['source_sha256']
 independent=read('results/CAP_HARNESS_READONLY_REVIEW_V19.json');assert independent['status']=='PASS_SCOPED_ANALYTIC_SOURCE_REPAIR'
 assert all(sha(f)==h for f,h in independent['reviewed_files'].items())
 cad=read('results/CAP_HARNESS_CAD_REVIEW_V19.json');assert cad['target_sha256']==sha(cad['target']) and all(sha(f)==h for f,h in cad['records'].items())
 v=read('results/CAP_HARNESS_VALIDATE_V19.json');assert v['ok'] and v['failureCount']==0 and v['occurrenceCount']>=13
 s=read('results/CAP_HARNESS_SNAPSHOT_V19.json');assert s['ok'] and s['target_sha256']==sha(s['target']) and s['published_sha256']==sha(s['published_image'])
 visual=read('results/CAP_HARNESS_VISUAL_REVIEW_V19.json');assert visual['actual_images_viewed'] and all(sha(f)==h for f,h in visual['images'].items())
 erc=read('results/ERC_MCP_CROSSCHECK.json');assert len(erc['inputs'])==16 and all(sha(f)==h for f,h in erc['inputs'].items()) and 'Errors: 0  Warnings: 0' in str(erc['result'])
 # C203 has an actual outboard PTH change; unchanged CHB and historical reports are preserved.
 for f in ['ecad/wp10_chb_input.kicad_pcb','results/CAP_TERMINAL_DRC_NATIVE_V17.json','results/CHB_INPUT_DRC_NATIVE_V18.json']:
  assert (A/f).read_bytes()==(H/f).read_bytes()
 oldrows=list(csv.DictReader((H/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig')));rows=list(csv.DictReader((A/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig')))
 assert len(rows)==37 and [(r['id'],r['status']) for r in rows]==[(r['id'],r['status']) for r in oldrows]
 parent_integrity=read('results/PARENT_INTEGRITY.json');assert parent_integrity['count']==444 and parent_integrity['all_parent_indexed_bytes_unchanged'] and not parent_integrity['mismatches']
 if regression:
  t=read('results/CAP_HARNESS_PUBLICATION_TESTS_V19.json');assert t['passed'] and t['publisher_sha256']==sha('tools/publish_cap_harness_v19.py') and len(t['faults'])==7 and all(f['rejected'] for f in t['faults'])
 return p,g
def decision(p,g):
 d=json.loads((H/'results/DELIVERY_DECISION.json').read_text());path='mechanical/CAP_HARNESS_INSTANCE_PLAN_V19.json';plan=read(path)
 d.update(schema='WP10_IMPLEMENTATION_DELIVERY_V19',revision=REV,review_revision=REV,status='C203_TWO_PHYSICAL_WIRE_ROUTES_INTEGRATED__STRAIN_RELIEF_AND_WHOLE_DESIGN_OPEN',current_source_plan=path,current_source_plan_sha256=sha(path),current_source_instances_by_state={s:len(v['rows']) for s,v in plan['states'].items()},candidate_source_components=972,source_candidate_components=972)
 d['internal_work_remaining']=[x.replace('Whole970','Whole972') for x in d['internal_work_remaining']]
 d.update(C203_wire_route_geometry_verified=True,C203_wire_route_instance_count=2,C203_wire_route_check_scope='Two nominal static conductors against current broadphase candidates in3 states; no unchanged-pair/full-motion/tolerance qualification',C203_wire_nominal_cut_lengths_mm={w['id']:w['analytic_cut_length_mm'] for w in p['wires']},C203_wire_strain_relief_complete=False,C203_wire_solder_process_qualified=False,C203_wire_route_evidence='results/CAP_HARNESS_EXACT_V19.json',C203_analytic_checks=len(p['checks']),C203_analytic_faults_rejected=len(p['faults']),C203_CHB_connection_complete=False,terminal_to_CHB_physical_connection_complete=False,CHB_terminal_to_C203_route_complete=False)
 d['route_complete_field_scope']='Complete harness fields remain false until retention/termination/tolerance definitions close; geometric route has its own true field.'
 d['C203_wire_DC_heat_refinement']=dict(calculation='power/CAP_HARNESS_ELECTROTHERMAL_V19.json',active_heat_ledger='thermal/ACTIVE_HEAT_LOADS_V19.json',case_states=384,DC_only=True,actual_ripple_known=False,whole_thermal_verified=False)
 d['C203_wire_PTH_repair']=dict(source_check='results/C203_WIRE_PTH_SOURCE_CHECK_V19.json',native_check='results/C203_WIRE_PTH_NATIVE_CHECK_V19.json',PTH_wire_holes=2,NPTH_holes=6,remaining_CAP_DRC_errors=6,whole_PCB_DRC_clean=False)
 d['C203_contact_surface_profile_verified']=False
 d['C203_surface_profile_open']='70um front copper can change local no-copper seating height; STEP envelope/holes preserved are not physical CAP/frame contact proof. Finished thickness, mask profile and flatness require joint review.'
 d['active_next_work_item']=dict(parent_id='B03',same_candidate=path,next_action='Design and integrate actual C203 wire strain relief and assembly/solder access; bind main/control-return conductors. Close single-face terminal CAM/solder definition, ripple/input-loop dynamics and fuse/BMS/SOA coordination; continue battery/PMM/thermal/propulsion duties.',read_inputs=['power/CAP_HARNESS_DEFINITION_V19.json','results/CAP_HARNESS_EXACT_V19.json','mechanical/INPUT_CAP_MOUNT_DESIGN.json','power/INPUT_FUSE_COORDINATION.json'])
 d['source_metadata_repair_V19']=dict(previous_counts=json.loads((H/'results/DELIVERY_DECISION.json').read_text())['current_source_instances_by_state'],previous_hash_stale=True,new_values_derived_from_actual_plan=True)
 check_decision(d);return d
def publish():
 p,g=validate();d=decision(p,g)
 rows=list(csv.DictReader((H/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig')))
 evidence_note='V19: two actual C203 wire STEP routes;22 analytic checks/10 negative cases;3-state exact delta. Strain relief, solder/CAM and system qualification remain OPEN.'
 for r in rows:
  if r['id'] in ['B03','E05','H03']:r['new_evidence']=(r['new_evidence']+' | '+evidence_note).strip(' |')
 with (A/'SYSTEM_CLOSURE_MATRIX.csv').open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
 dump('results/DELIVERY_DECISION.json',d)
 c=read('power/CAP_HARNESS_DEFINITION_V19.json');schedule=[];bom=[]
 for w in c['wires']:
  result=next(x for x in p['wires'] if x['id']==w['id']);L=result['analytic_cut_length_mm']
  schedule.append(dict(wire_id=w['id'],from_physical_feature=w['from_feature'],to_electrical_pin=w['logical_to'],to_physical_termination=w['to_feature'],net=w['net'],wire_MPN=c['wire']['MPN'],quantity_conductors=1,cut_length_mm=L,strip_length_mm='',strip_from_mm=w['strip_start_mm'],strip_to_mm=w['strip_end_mm'],geometry_route_verified=True,route_complete=False,termination_qualified=False,status='NOMINAL_STATIC_ROUTE_VERIFIED_RETENTION_AND_SOLDER_OPEN'))
  bom.append(dict(id=w['id'],MPN=c['wire']['MPN'],description='18AWG19/30 white ETFE insulated wire, nominal design length',quantity=1,unit='wire',nominal_cut_length_mm=L,strip_from_mm=w['strip_start_mm'],strip_to_mm=w['strip_end_mm'],manufacturing_tolerance='UNASSIGNED',manufacture_release=False))
 for path,values in [('power/C203_WIRE_SCHEDULE.csv',schedule),('mechanical/CAP_HARNESS_BOM_V19.csv',bom)]:
  with (A/path).open('w',newline='',encoding='utf-8-sig') as f:
   w=csv.DictWriter(f,fieldnames=values[0].keys());w.writeheader();w.writerows(values)
 dump('ecad/CAP_HARNESS_INTERFACE_V19.json',dict(definition='power/CAP_HARNESS_DEFINITION_V19.json',definition_sha256=sha('power/CAP_HARNESS_DEFINITION_V19.json'),source_plan=d['current_source_plan'],source_plan_sha256=d['current_source_plan_sha256'],wires=schedule,geometry_evidence='results/CAP_HARNESS_EXACT_V19.json',complete_connection=False,manufacturing_qualified=False))
 (A/'README.md').write_text('''# WP10 当前 V19：C203 至 CHB 的实体导线路线

同一候选新增两根实际导线STEP，三态源清单972行，原970行逐项保持。每根名义长52.763077mm、两端剥线4.1/3.6mm、圆弧R10。解析22检查/10反例、三态新线与邻件精确检查通过。

- [查看本轮实体图与证据](REVIEW.html)
- [局部STEP](mechanical/cap_harness_assembly.step) / [972行源清单](mechanical/CAP_HARNESS_INSTANCE_PLAN_V19.json)
- [两线BOM](mechanical/CAP_HARNESS_BOM_V19.csv) / [端接和裁线表](power/C203_WIRE_SCHEDULE.csv)
- [解析检查](results/CAP_HARNESS_PATH_V19.json) / [精确干涉检查](results/CAP_HARNESS_EXACT_V19.json) / [限定独立复核](results/CAP_HARNESS_READONLY_REVIEW_V19.json)
- [电热分配计算](power/CAP_HARNESS_ELECTROTHERMAL_V19.json) / [384状态热源替代表](thermal/CAP_HARNESS_REFINED_HEAT_LOADS_V19.csv) / [热量归属复核](results/CAP_HARNESS_HEAT_READONLY_REVIEW_V19.json)
- [原37行责任表](SYSTEM_CLOSURE_MATRIX.csv) / [机器裁决](results/DELIVERY_DECISION.json)

导线为静态名义路线，卡箍保持、装配/焊接工艺和公差尚未闭环。C203两处外接线孔改为真实PTH；原12项DRC保留为历史，当前两处CAP孔仍有6项DRC。CHB板及主原理图逻辑未变，ERC结论仍须匹配当前输入证据。整机设计、制造、上电及飞行放行均未完成，972件完整原生总装和连续动作未验证。V19同时修正了旧机器裁决中未同步的源计数和哈希字段。
''',encoding='utf-8')
 viewer='http://127.0.0.1:3245/'+urllib.parse.quote(A.as_posix(),safe='/:')+'?file=mechanical%2Fcap_harness_assembly.step.py'
 table=''.join('<tr>'+''.join('<td>'+html.escape(r[k])+'</td>' for k in ['id','object','status','remaining_design'])+'</tr>' for r in rows)
 page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>WP10 V19 · C203实体导线</title><style>body{margin:0;background:#f3f4ee;color:#233c35;font:16px/1.75 system-ui,"Microsoft YaHei",sans-serif}main{max-width:1160px;margin:auto;padding:32px 24px}h1{font-size:34px}.cards{display:flex;gap:16px;flex-wrap:wrap}.card{background:white;border:1px solid #cedbd1;border-radius:12px;padding:20px;flex:1}.big{font-size:32px;font-weight:700}nav{display:flex;gap:18px;flex-wrap:wrap;margin:20px 0}a{color:#116346}.notice{border-left:5px solid #b37a23;padding:12px 18px;background:#fff9e8}img{max-width:100%;height:auto}table{border-collapse:collapse;font-size:13px}td,th{padding:9px;border-bottom:1px solid #ccd8cf;text-align:left}.scroll{overflow:auto}</style><main><small>WP10 · V19 · 同一工程候选 · 2026-09-09</small><h1>C203 至 CHB 的两根实体导线已集成</h1><p>真实孔位、相切弯曲段、裸导体与绝缘区间进入 STEP 和同源线束表。</p><div class="cards"><div class="card"><div class="big">52.763 mm</div>每根名义裁线长度</div><div class="card"><div class="big">22 + 10</div>解析检查 / 拒绝反例</div><div class="card"><div class="big">972</div>源实例；原970保持</div></div><nav><a href="__VIEWER__">交互查看局部装配</a><a href="mechanical/cap_harness_assembly.step">下载局部STEP</a><a href="WP10_IMPLEMENTATION_DELTA.zip">下载当前包</a></nav><p class="notice">整机尚未完成。导线保持、焊接工艺、尺寸公差、低电感输入稳定性仍开放；C203原板12项DRC未消除。本轮未制造、通电或进行实物装配。</p><img src="review/CAP_HARNESS_ASSEMBLY_V19.png" alt="实际STEP中的两根白色绝缘导线与CHB/C203局部装配"><p>13个源实例的局部装配；导线各含导体外包络和绝缘。不是972件完整原生总装。三态检查覆盖新增线与当前候选邻件，未重验旧件彼此和连续动作。</p><nav><a href="results/CAP_HARNESS_EXACT_V19.json">三态精确检查</a><a href="results/CAP_HARNESS_PATH_V19.json">路线、长度和反例</a><a href="results/CAP_HARNESS_READONLY_REVIEW_V19.json">解析检查独立复核</a><a href="mechanical/CAP_HARNESS_BOM_V19.csv">线束BOM</a><a href="power/C203_WIRE_SCHEDULE.csv">端点与裁线表</a><a href="docs/hardware/CAP_HARNESS_BRIEF_V19.md">设计依据和限制</a></nav><h2>既有电路与剩余工作</h2><p>C203端接板仍有8项孔距、4项阻焊桥错误，来自无网NPTH与自身铜盘/走线组合。原厂密封侧和加工条件尚未支持直接改为普通PTH；没有修改规则或豁免。CHB板0错误/0警告和系统ERC0/0沿用完全相同源文件的既有报告，本轮未重跑ERC/DRC。</p><nav><a href="results/CAP_TERMINAL_DRC_V17.rpt">C203原DRC报告</a><a href="results/CHB_INPUT_DRC_V18.rpt">CHB原DRC报告</a><a href="ecad/wp10_system.pdf">系统原理图</a><a href="ecad/CAP_HARNESS_INTERFACE_V19.json">本轮机电接口</a></nav><p>下一步实际设计导线卡箍及应变释放，核对装配与焊接工具空间，补齐主馈和控制回线；其他电池/PMM、回生热动态和推进受控接口仍按原责任表推进。旧裁决的源计数/哈希未同步问题在V19修正，未改写V18历史。</p><details><summary>原37行：13限定完成 / 19内部开放 / 4外部接口 / 1实物未执行</summary><div class="scroll"><table><thead><tr><th>ID</th><th>对象</th><th>状态</th><th>剩余设计</th></tr></thead><tbody>__TABLE__</tbody></table></div></details><nav><a href="SYSTEM_CLOSURE_MATRIX.csv">完整责任表</a><a href="results/DELIVERY_DECISION.json">机器裁决</a><a href="mechanical/CAP_HARNESS_INSTANCE_PLAN_V19.json">当前源清单</a></nav></main></html>'''.replace('__VIEWER__',viewer).replace('__TABLE__',table)
 heat_section='<h2>实体线长接入漏电热账</h2><p>原192组工况、384个RUN/COLD状态保持；两根线在既有3mA漏电场景中合计1.9412e-8 W，从原漏电分配等量扣除。其余3648个热源节点逐行保持，局部守恒容差1e-12 W，10个反例均被拒绝。剩余分配仍包括尚未细分的PCB和焊点损耗。2.4 Arms线损参考没有混入实际热账，COLD实际电容电压仍未知。</p><nav><a href="power/CAP_HARNESS_ELECTROTHERMAL_V19.json">电热模型与1152相关场景</a><a href="thermal/CAP_HARNESS_REFINED_HEAT_LOADS_V19.csv">4800行热源替代表</a><a href="thermal/ACTIVE_HEAT_LOADS_V19.json">热账版本指针</a><a href="results/CAP_HARNESS_HEAT_READONLY_REVIEW_V19.json">独立热账复核</a></nav><p>热源替代表在该电阻场景下替代原INPUT_PASSIVE热账，禁止两表相加；没有获得实际纹波、线温或整星散热合格结论。</p>'
 page=page.replace('<h2>既有电路与剩余工作</h2>',heat_section+'<h2>既有电路与剩余工作</h2>')
 page=page.replace('C203原板12项DRC未消除','C203两处CAP孔仍有6项DRC').replace('C203端接板仍有8项孔距、4项阻焊桥错误，来自无网NPTH与自身铜盘/走线组合。原厂密封侧和加工条件尚未支持直接改为普通PTH；没有修改规则或豁免。CHB板0错误/0警告和系统ERC0/0沿用完全相同源文件的既有报告，本轮未重跑ERC/DRC。','C203外接线孔已经改为真实PTH，顶盘距最大电容投影2.549mm。两处CAP孔保留NPTH和背盘，仍有4项孔距、2项阻焊桥错误；没有修改规则或豁免。旧12项报告保留。CAP无前环PTH有厂家安装语义支持，具体孔铜、孔口和焊接工艺仍需设计验证。CHB板0/0沿用相同源的报告；当前C203 DRC和系统ERC必须通过发布前的同源核验。')
 page=page.replace('results/CAP_TERMINAL_DRC_V17.rpt','results/CAP_TERMINAL_DRC_V19.rpt').replace('C203原DRC报告','C203当前DRC报告')
 (A/'REVIEW.html').write_text(page,encoding='utf-8')
 evidence=['README.md','REVIEW.html','SYSTEM_CLOSURE_MATRIX.csv','results/DELIVERY_DECISION.json','power/C203_WIRE_SCHEDULE.csv','power/CAP_HARNESS_DEFINITION_V19.json','ecad/CAP_HARNESS_INTERFACE_V19.json','mechanical/CAP_HARNESS_BOM_V19.csv','mechanical/CAP_HARNESS_INSTANCE_PLAN_V19.json','docs/hardware/CAP_HARNESS_BRIEF_V19.md','tools/publish_cap_harness_v19.py']
 evidence += [p.relative_to(A).as_posix() for p in (A/'mechanical').glob('cap_harness*') if p.is_file()]
 evidence += ['tools/cap_harness_heat_v19.py','power/CAP_HARNESS_ELECTROTHERMAL_V19.json','thermal/CAP_HARNESS_REFINED_HEAT_LOADS_V19.csv','thermal/ACTIVE_HEAT_LOADS_V19.json']
 evidence += ['ecad/wp10_c203_terminal.kicad_pcb','power/CAP_TERMINAL_DEFINITION.json','results/C203_WIRE_PTH_SOURCE_CHECK_V19.json','results/C203_WIRE_PTH_NATIVE_CHECK_V19.json']
 evidence += [p.relative_to(A).as_posix() for p in (A/'results').glob('CAP_HARNESS*_V19.json') if p.name!='CAP_HARNESS_REVISION_INTEGRATION_V19.json']
 dump('results/CAP_HARNESS_REVISION_INTEGRATION_V19.json',dict(revision=REV,source_count=972,whole_design_complete=False,goal_complete=False,evidence={f:sha(f) for f in evidence}))
 print(json.dumps(dict(revision=REV,source_count=972,whole_design_complete=False)))
if __name__=='__main__':
 if '--check-only' in sys.argv:validate();print('V19 preflight accepted')
 else:publish()
