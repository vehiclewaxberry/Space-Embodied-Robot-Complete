"""Publish bounded evidence and a trial source plan; retain active V32 design."""
from pathlib import Path
import copy,csv,datetime,hashlib,html,json,zipfile
import psutil
A=Path(__file__).resolve().parents[1];C=A/'coupled_closure'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def dump(p,v):
 with p.open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,ensure_ascii=False)
def main():
 g=read(C/'SPREADER_GEOMETRY_V33.json');t=read(C/'SPREADER_THERMAL_V33.json');screen=read(C/'LAYOUT_SCREEN_V33.json');exact=read(C/'LAYOUT_EXACT_V33.json');v=read(A/'results/kelvin_v32/VALIDATION.json')
 assert all(g['checks'].values()) and all(t['checks'].values())
 assert t['script_sha256']==sha(C/'thermal_spreader_v33.py') and t['geometry_sha256']==sha(C/'SPREADER_GEOMETRY_V33.json')
 assert all(sha(C/k)==h for k,h in t['replay_reference_source_lock'].items())
 assert read(C/'SPREADER_VALIDATION_V33.json')['ok']
 assert exact['screen_sha256']==sha(C/'LAYOUT_SCREEN_V33.json')
 assert not any(r['acceptable_clearance_candidate'] for r in exact['results'])
 rows=list(csv.DictReader((A/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig')));assert len(rows)==37
 matrix_hash=sha(A/'SYSTEM_CLOSURE_MATRIX.csv')
 # Same 974 rows, source-only trial. Do not make the thermally poor candidate active.
 parent=read(C/'SPREADER_INSTANCE_PLAN_V28.json');plan=copy.deepcopy(parent)
 plan.update(schema='WP10_V33_SPREADER_TRIAL_SOURCE_PLAN',parent_plan='coupled_closure/SPREADER_INSTANCE_PLAN_V28.json',parent_plan_sha256=sha(C/'SPREADER_INSTANCE_PLAN_V28.json'),trial_only=True,adopted_as_active_geometry=False,known_mass_delta_kg=g['added_mass_kg'],mass_delta_basis='Relative to original bottom_radiator, not additive to V28 delta',increment_vs_V28_mass_kg=g['increment_vs_V28_mass_kg'])
 for state,entry in plan['states'].items():
  old={r['id']:r for r in parent['states'][state]['rows']};count=0
  for r in entry['rows']:
   if r['id']=='radiator_spreader':
    r.update(step_path=str(C/'spreader_v33.step'),source_sha256=sha(C/'spreader_v33.step'),current_STEP_validated=True,native_geometry_current=False,source_parent_lookup=dict(plan='coupled_closure/SPREADER_INSTANCE_PLAN_V28.json',state=state,id='radiator_spreader'));count+=1
   else:assert r==old[r['id']]
  assert count==1 and len(entry['rows'])==974
 plan['V33_inputs']={str(p.relative_to(A)):sha(p) for p in [C/'spreader_v33.step.py',C/'spreader_v33.step',C/'SPREADER_PARAMETERS_V33.json',C/'SPREADER_GEOMETRY_V33.json',C/'SPREADER_THERMAL_V33.json']}
 dump(C/'SPREADER_INSTANCE_PLAN_V33_TRIAL.json',plan)
 # Bind the completed manual and independent reviews to actual source artifacts.
 snapshot=read(C/'SPREADER_SNAPSHOT_RESULT_V33.json');images=[Path(r['path']) for r in snapshot['outputs']];assert len(images)==4 and all(p.exists() for p in images)
 dump(C/'SPREADER_VISUAL_REVIEW_V33.json',dict(reviewer='root',date='2026-09-13',source_step_sha256=sha(C/'spreader_v33.step'),images={p.name:sha(p) for p in images},four_views_reviewed=True,findings=['One coherent bottom plate and integral cold fingers.','Both extended beam slots and four MIPS pockets visible; outer flat radiator retained.','No inferred manufacturability from image; exact gap checks govern.'],geometry_credit_only=True))
 dump(C/'SPREADER_INDEPENDENT_REVIEW_V33.json',dict(reviewer='/root/v31_mechanical',mode='READ_ONLY_NO_HEAVY_REEXECUTION',date='2026-09-13',verdict='PASS_SCOPED_SOURCE_PLAN_TRIAL__THERMAL_AND_INSTALLATION_OPEN',geometry_evidence_sha256=sha(C/'SPREADER_GEOMETRY_V33.json'),reviewed_initial_thermal_sha256=sha(C/'history/V33_initial_replay/SPREADER_THERMAL_V33.json'),final_thermal_sha256=sha(C/'SPREADER_THERMAL_V33.json'),corrective_action='Bound both replay reference hashes in source; reran thermal model with identical numerical results.',new_near_gaps_mm={'lower_beams':.25,'MIPS_nut_proxies':.325},whole_design_complete=False))
 heat=[r for r in t['cases'] if r['variant']=='V33' and r['pitch_mm']==5]
 jobs=[]
 for p in sorted((A/'logs').glob('native_delta_v33_*20260913.run.json')):
  j=read(p);samples=j.get('samples',[])
  jobs.append(dict(name=j['name'],status=j['status'],elapsed_s=j['elapsed_s'],start_available_MiB=j['available_start_mib'],min_available_MiB=min((s['available_mib'] for s in samples),default=j['available_start_mib']),max_tree_RSS_MiB=max((s['child_tree_rss_mib'] for s in samples),default=0),receipt=str(p.relative_to(A)),sha256=sha(p)))
 assert all(j['status']=='COMPLETED' for j in jobs)
 memoryfiles=[p for p in (A/'results').glob('*V32_resume_20260913*.json')]
 status=dict(schema='WP10_V33_RESUMPTION_AND_STRUCTURAL_TRIAL',date=datetime.datetime.now().astimezone().isoformat(),active_revision='V32',active_geometry_revision='V30/V28',electrical_refs=211,pin_records=677,scoped_ERC='13 pages 0 errors 0 warnings',scoped_DRC='Main input only, inherited rules, 0 violations 0 unconnected',native_source_checks=v['checks_run'],trial_geometry='SPREADER_INSTANCE_PLAN_V33_TRIAL.json',trial_plan_rows=974,trial_native_whole_assembly_updated=False,trial_adopted=False,decision='HOLD_V33_SPREADER__LOW_THERMAL_BENEFIT_AND_TIGHT_GAPS',mass_added_vs_V28_kg=g['increment_vs_V28_mass_kg'],thermal_cases=[dict(case=r['case'],CHB_case_C=r['CHB_case_C'],margin_C=r['CHB_margin_C']) for r in heat],native_layout_rejections=[dict(index=r['shortlist_index'],collisions_by_state={s:len(q['positive_volume_intersections']) for s,q in r['states'].items()}) for r in exact['results']],memory_cleanup_receipts={str(p.relative_to(A)):sha(p) for p in memoryfiles},available_memory_now_MiB=psutil.virtual_memory().available/2**20,guarded_jobs=jobs,source_closure_matrix_sha256=matrix_hash,original_37_rows_unchanged=True,whole_design_complete=False,manufacturing_release=False,hardware_tests=0,next_actual_work=['Repackage main-input module and resolve its 23 unmodeled component references before host mounting.','Bind a real carrier-to-fixed-radiator interface, TIM contact area and pressure; re-evaluate full heat load.','Resolve battery protection/STOP/regen and controlled propulsion ICD with current arm mass/inertia before whole-system release.'])
 dump(C/'DELIVERY_STATUS_V33.json',status)
 table=''.join(f'<tr><td>{html.escape(r["case"])}</td><td>{r["CHB_case_C"]:.3f}</td><td>{r["CHB_margin_C"]:.3f}</td></tr>' for r in heat)
 md=f'''# WP10恢复执行：V32电气 + V33结构试验

当前活动设计保持V32电气、V30/V28几何。V33是同一974实例源计划的单件替代试验，尚未采用为活动底板，也未回装为新的整机SLDASM。整机设计未完成。

## 已执行

- 进一步释放内存：59个闲置工具进程工作集回收、1个空闲预载器关闭、4个UI进程工作集回收。最高采样4206 MiB；不是持续可用保证。所有V33重型任务均受2048 MiB启动/512 MiB运行/1400 MiB任务树保护，完成无内存中止。
- V32实际原理图库、PCB与封装内部连接表达修复；211位号677针脚；13页ERC零错零警，主输入板在继承规则下DRC零违规零未连接。反例仍能检出真实断线；不代表整机电气已放行。
- V33底板一体扩展区从xmax10扩大至168 mm、厚3.5 mm，保留孔槽与界面。1个有效实体，原金属未移除；相对V28新增{g['increment_vs_V28_mass_kg']:.9f} kg。原生验证及四视图完成。
- 973个非替代宿主逐项保持；三态新增金属无体积碰撞。甲板1.5 mm、侧角件1.65 mm；两条梁只有0.25 mm、螺母代理0.325 mm，公差和工具空间未验收。
- 10/5 mm两网格同热输入回算通过数值一致性检查；网格温差最大{max(t['mesh_delta_C'].values()):.5f}°C；热模型没有重复叠加V28厚度，也没有增加辐射面积或降低360 W筛查负载。
- 当前V30的56个局部实例完成枚举24个正交朝向，其中8个能在声明搜索箱内生成网格、16个不适配，共18000位置有限筛查。三个短名单位置三态分别有8、7、7个宿主体积交叠，全部拒绝。保留设备代理及厂家最大包络，没有据此证明全部布局不可行。

## 设计裁决

扩大导热截面仅降约0.36—0.45°C，却增加约207g。主板共热工况仍超过105°C；该方案保留为试验，不作为最终底板。全部已知非臂热假定路线仍117.430°C。实际载板到辐射面的导热接口、TIM压力、罩体影响、未建23个位号、远端线束、未知臂/电池/回生热仍未闭合。

STEP可独立导入SolidWorks；参数源和974实例计划依赖当前工作区，交付包不是可迁移的整机Pack-and-Go或制造包。原37行闭环表、原873宿主和99位号父本未改写。

入口：[交互图文报告](REVIEW_V33.html)、[STEP](spreader_v33.step)、[源计划](SPREADER_INSTANCE_PLAN_V33_TRIAL.json)、[热回执](SPREADER_THERMAL_V33.json)、[三位置原生检查](LAYOUT_EXACT_V33.json)、[当前电气源](REVIEW_V32.html)。
'''
 with (C/'README_V33.md').open('x',encoding='utf-8') as f:f.write(md)
 viewer='http://127.0.0.1:3245/'+str(C).replace('\\','/').replace(' ','%20')+'?file=spreader_v33.step.py'
 page=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>WP10恢复执行与V33结构试验</title><style>body{{font:17px/1.8 system-ui;background:#eef3f6;color:#173445;margin:0}}main{{max-width:1120px;margin:auto;padding:32px}}section{{background:white;padding:24px;margin:20px 0;border-radius:12px}}h1{{font-size:30px}}.hold{{background:#fff1d2;border-left:5px solid #b07814;padding:18px}}img{{width:100%;max-height:620px;object-fit:contain}}a{{color:#06758b}}table{{border-collapse:collapse;width:100%}}td,th{{padding:9px;text-align:left;border-bottom:1px solid #d8e3e9}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:20px}}</style><main><h1>WP10：恢复执行与底板结构试验</h1><p class="hold"><strong>整机尚未闭环。</strong>活动设计保持 V32 电气 / V30、V28 几何。V33增加约207 g仅降约0.4°C，并出现0.25 mm近隙，保留试验，不采用为最终底板。</p><section class="grid"><div><b>内存清理后继续执行</b><p>最高采样4.1 GiB；本轮重型检查均完成，无内存保护中止。</p></div><div><b>实际电气修复</b><p>211位号 / 677针脚<br>13页ERC零错零警<br>主输入DRC零违规零未连接</p></div><div><b>真实CAD改件</b><p>一个有效实体<br>三态新增金属零碰撞<br>保留974实例试验源计划</p></div></section><section><h2>扩大导热截面的实际几何</h2><img src="{images[0].name}" alt="实际生成的V33一体底板CAD"><p>加厚区3.5 mm；梁槽、CHB座、安装孔与盲孔保留。底板外辐射面积不变。甲板间隙1.5 mm、角件1.65 mm；梁0.25 mm、螺母代理0.325 mm仍需公差与工具检查。</p><a href="{viewer}">打开CAD交互查看</a> · <a href="spreader_v33.step">下载STEP</a> · <a href="SPREADER_INSTANCE_PLAN_V33_TRIAL.json">974实例试验计划</a></section><section><h2>同一输入热计算：仍然超温</h2><table><tr><th>5 mm网格情景</th><th>CHB壳温/°C</th><th>距105°C余量</th></tr>{table}</table><p>360 W筛查点、25 psi典型TIM参数与示例环境均保留。主板+Y热源块尚无实际安装热路；这些数值不是轨道或实测资格。数值验收通过不能替代温度合格。</p></section><section><h2>安装位置筛查</h2><p>枚举24个正交朝向，其中8个在声明搜索箱内生成网格、16个不适配，共18,000个有限网格位置；当前56个局部实例的3个短名单，经三态原生实体检查各有8、7、7个宿主交叠，全部拒绝。真实冲突含现行散热板、上甲板和机械臂驱动接口；旧设备预算体也保留分账。本次没有证明其他布局不可行。</p><a href="LAYOUT_EXACT_V33.json">逐位置、逐状态原生证据</a> · <a href="LAYOUT_SCREEN_V33.json">筛查输入与排序</a></section><section><h2>查看与下载</h2><a href="REVIEW_V32.html">当前电气修订</a> · <a href="README_V33.md">完整说明</a> · <a href="DELIVERY_STATUS_V33.json">状态与内存回执</a> · <a href="WP10_RESUME_V32_V33_REVIEW.zip">本轮审阅包</a><p>STEP可导入SolidWorks；源计划与参数源依赖当前工作区。此包不是整机Pack-and-Go、制造或上电放行。</p></section></main></html>'''
 with (C/'REVIEW_V33.html').open('x',encoding='utf-8') as f:f.write(page)
 sources=[p for p in C.iterdir() if p.is_file() and ('V33' in p.name or 'v33' in p.name) and p.suffix!='.zip']
 sources += [A/'tools/prepare_spreader_v33.py',A/'tools/publish_spreader_v33.py',A/'tools/run_spreader_visual_v33.py',C/'spreader_design_v28.py',A/'mechanical/bottom_radiator_common.py',A/'thermal/BOTTOM_RADIATOR_MOUNT.json']
 sources += [C/'CANDIDATE_V32.json',C/'REVIEW_V32.html',C/'README_V32.md',A/'results/kelvin_v32/VALIDATION.json',A/'results/kelvin_v32/COUNTEREXAMPLES.json',A/'results/kelvin_v32/MAIN_INPUT_TOP.png']
 sources += [A/j['receipt'] for j in jobs]+memoryfiles
 manifest={str(p.relative_to(A)):sha(p) for p in sources}
 dump(C/'V33_REVIEW_SOURCE_MANIFEST.json',manifest)
 archive=C/'WP10_RESUME_V32_V33_REVIEW.zip';assert not archive.exists()
 with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
  for p in sources+[C/'V33_REVIEW_SOURCE_MANIFEST.json']:z.write(p,str(p.relative_to(A)).replace('\\','/'))
 with zipfile.ZipFile(archive) as z:assert z.testzip() is None
 # Active design remains V32; attach the completed experiment as latest work.
 pointer=A/'CURRENT_WORKING_CANDIDATE.json';old=read(pointer);assert old['revision']=='V32'
 history=A/'history/20260913_V33_review';history.mkdir(exist_ok=True)
 (history/pointer.name).write_bytes(pointer.read_bytes())
 old['latest_review']='coupled_closure/REVIEW_V33.html';old['latest_experiment']='coupled_closure/DELIVERY_STATUS_V33.json'
 pointer.write_text(json.dumps(old,indent=2,ensure_ascii=False),encoding='utf-8')
 assert sha(A/'SYSTEM_CLOSURE_MATRIX.csv')==matrix_hash
 receipt=dict(report=str(C/'REVIEW_V33.html'),archive=str(archive),archive_sha256=sha(archive),files=len(sources)+1,active_revision='V32',trial_adopted=False,whole_design_complete=False)
 dump(C/'PUBLISH_RECEIPT_V33.json',receipt);print(json.dumps(receipt))
if __name__=='__main__':main()
