"""Publish the tested trunk support revision without claiming whole-system closure."""
import json,csv,html,urllib.parse
from pathlib import Path
from battery_variant_context import A,read,sha
r=read('results/TRUNK_SUPPORT_REVIEW.json');assert r['snapshots_actually_reviewed'] and not r['whole_design_complete']
assert all(sha(A/q)==h for q,h in r['inputs'].items()) and all(sha(A/q)==h for q,h in r['snapshots'].items())
plan=read('mechanical/TRUNK_SUPPORT_INSTANCE_PLAN.json')
def live(stem):return 'http://127.0.0.1:3245/'+urllib.parse.quote(A.as_posix(),safe='/:')+'?file='+urllib.parse.quote(f'mechanical/{stem}.step.py')
def shot(stem,view):return next(q for q in r['snapshots'] if Path(q).name.startswith(stem+'_'+view+'_'))
iso=shot('trunk_support_integration','iso');high=shot('trunk_high_base','iso')
v=read('results/DELIVERY_DECISION.json');assert len(v['remaining_open_ids'])==23
v['previous_893_source_variant']=dict(source_plan=v['current_source_plan'],source_plan_sha256=v['current_source_plan_sha256'],local_preview_instances=85,source_instances=893,source_geometry_evidence='results/PROP_ROUTING_REVIEW.json')
v.update(schema='WP10_IMPLEMENTATION_DELIVERY_V10',review_revision='V10_TRUNK_SUPPORTS',status='FOUR_TRUNK_SUPPORTS_AND931_SOURCE_TABLES_UPDATED__WHOLE_MECHATRONIC_CLOSURE_OPEN',current_source_plan='mechanical/TRUNK_SUPPORT_INSTANCE_PLAN.json',current_source_plan_sha256=sha(A/'mechanical/TRUNK_SUPPORT_INSTANCE_PLAN.json'),candidate_source_components=931,current_source_instances_by_state=r['source_instances_by_state'],current_local_source_assembly_instances=131,current_local_step='mechanical/trunk_support_integration.step',trunk_support_changed_pairs_by_state=r['exact_pairs_by_state'],trunk_required_contacts_by_state=r['required_contacts_by_state'],trunk_nominal_static_support_geometry_verified=True,trunk_material_preload_strength_qualified=False,current_pending_harness_source_ids=r['known_release_segments_retained'],current_pending_harness_features=['release_branch_and_parking_mast_interface','top_passage_liner_and_strain_relief','actual_wire_endpoints_and_electrical_lengths','liner_material_clamp_force_tolerance_and_full_motion'],full_harness_geometry_status='OPEN_RELEASE_BRANCHES_ROOT_PASSAGE_AND_MATERIAL_QUALIFICATION',current_source_plan_whole_fit_verified=False,current_full_native_assembly_generated=False,current_source_mass_inertia_thermal_requalified=False,current_source_view_screen_bound=False,current_source_thermal_network_calculated=False,current_source_CHB_temperature_C=None,goal_complete=False,engineering_prototype_design_complete=False)
v['internal_work_remaining']=[s.replace('Whole893 native assembly','Whole931 native assembly') for s in v['internal_work_remaining']]
v['thermal_core_native_scope']['current931_native_assembly_or_geometry_credit']=False
v['active_next_work_item']=dict(parent_id='A05',same_candidate='mechanical/TRUNK_SUPPORT_INSTANCE_PLAN.json',next_action='Resolve retained release branch/parking mast entry with an actual source interface change; finish root passage strain relief, battery/PMM/device retention, material/fastener qualifications and same-source mechanical-electrical-thermal integration.',read_inputs=['results/TRUNK_SUPPORT_REVIEW.json','results/RELEASE_PORT_CLEARANCE_COUNTEREXAMPLE.json','power/BATTERY_INSTALLATION_INTERFACE.json'])
(A/'results/DELIVERY_DECISION.json').write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
rows=list(csv.DictReader((A/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig')));assert len(rows)==37
for q in rows:
    q['next_source_edit']=q['next_source_edit'].replace('whole893 native','whole931 native')
    if q['id']=='A05':
        q['execution_state']='FOUR_TRUNK_SPLIT_SUPPORTS_WITH_NOMINAL_FASTENERS__WHOLE_ROW_OPEN'
        q['new_evidence']+=' | V10原8主干支撑ID实际替换；三块板源局部改孔/避让；8半衬套和30紧固件新增，完整三态931行源表与131件局部STEP已核。'
        q['next_source_edit']='处理4段释放支路及parking入口、顶端线束护套应变释放；完成真实电池/PMM保持、材料防松公差、强度热质量及全机验证。'
    if q['id']=='G02':q['new_evidence']+=' | V10三态各129对无穿透、54必需正面积接触通过；10组名义螺母轴向覆盖通过；释放旧反例仍保留。'
    if q['id']=='E05':q['new_evidence']+=' | V10机械49行增量BOM（11替换+38新增）绑定几何SHA；不产生新针序、裁线或通电信用。'
with (A/'SYSTEM_CLOSURE_MATRIX.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
intro=f'''# WP10 当前修订：连续主干线四站安装支撑

**四处主干支撑、固定孔和名义紧固件已实际集成；整机机电详细设计仍未完成。** 当前三态完整源表各931实例，局部STEP131实例；931是源表数量，没有生成当前整星原生SolidWorks或完整BRep装配。

[旋转查看131件局部装配]({live('trunk_support_integration')}) · [装配STEP](mechanical/trunk_support_integration.step) · [931源表](mechanical/TRUNK_SUPPORT_INSTANCE_PLAN.json) · [49行机械增量BOM](mechanical/TRUNK_SUPPORT_INSTANCE_BOM.csv) · [绑定证据](results/TRUNK_SUPPORT_REVIEW.json)

原4夹具/4高支柱ID已用四组split支座实际替换；增加8片半衬套和30件名义紧固件。低位支座贴甲板；高位支座轴S(-95,1.5,45)mm，柱通过设备间走廊，底脚直接承载于甲板。两块自制载板增加边缘避让，原安装孔保留；甲板新开8个Ø3.4孔。只在指定范围减料：甲板217.900866mm³、两载板各231mm³，增料、窗外减料及漏切均为零。[设计尺寸及装配顺序](mechanical/TRUNK_SUPPORT_BRIEF.md)

三态各129对变化近邻实际STEP检查均无正体积穿透、异常接触及电池间隙失败；各54处必需承载/衬套接触均为零距离且有正面积。10组名义紧固件覆盖完整螺母高度，最小伸出2.1mm。12个CAD入口几何有效，13张快照已查看。上述验证不等于螺纹、防松、夹持力、材料/放气、强度、公差、全线动态或实物合格。

初次检查确实发现高支架与驱动连接器460mm³穿透，以及悬臂填回螺钉通孔5.15638mm³；已移动高站15mm并重开通孔，通过同源复检。完整源表保留4段旧释放线路及其parking入口干涉，未通过删除反例取得整机通过。顶端穿孔护套/应变释放、真实电池/PMM保持和电气端接仍开放。

电气仍为201位号/11页既有原生源；本轮未改电路。当前931布局未重新完成质量、惯量、结构或热分析。894父布局的热计算和38件原生导热核心仍按原范围保留。原37行表仍13限定完成、19内部开放、4外部未绑定、1物理未执行。[当前机器裁决](results/DELIVERY_DECISION.json)

![当前局部装配]({iso})

![高位可拆线束支座]({high})

---

下文保留V9推进布线、V8电池布局及V7导热核心的历史范围；当前源表以上述V10为准。

'''
(A/'README.md').write_text(intro+(A/'README.md').read_text(encoding='utf-8'),encoding='utf-8')
links=[('旋转查看131件局部装配',live('trunk_support_integration')),('STEP','mechanical/trunk_support_integration.step'),('931完整源表','mechanical/TRUNK_SUPPORT_INSTANCE_PLAN.json'),('49行增量BOM','mechanical/TRUNK_SUPPORT_INSTANCE_BOM.csv'),('三态接触及干涉证据','results/TRUNK_SUPPORT_REVIEW.json'),('名义紧固堆叠','results/TRUNK_NOMINAL_STACK.json'),('设计尺寸','mechanical/TRUNK_SUPPORT_BRIEF.md')]
part_labels={'trunk_low_base':'低位支座','trunk_high_base':'高位支座','trunk_cap':'夹盖','trunk_liner_low':'下半衬套','trunk_liner_high':'上半衬套','trunk_screw_12':'底脚螺钉包络','trunk_screw_14':'高位螺钉包络','trunk_screw_20':'低位螺钉包络','trunk_deck':'更新甲板','trunk_drive_adapter':'驱动载板避让','trunk_compute_adapter':'计算载板避让'}
links += [(label,live(stem)) for stem,label in part_labels.items()]
section='<section><h2>当前四站主干支撑与131件局部装配</h2><p class="flag">三态各129对近邻和54处必需接触通过。931是完整源表数量，当前整星原生装配、机电详细设计仍未闭环。</p><img src="'+iso+'" alt="当前131件局部装配"><nav>'+''.join('<a href="'+html.escape(u,quote=True)+'">'+html.escape(t)+'</a>' for t,u in links)+'</nav><img src="'+high+'" alt="高位支座与底脚实际实体"><p>四夹具/四支撑ID已替换，增加8片衬套和30件紧固件，三块板源同步改孔/避让。4段释放支路与原入口反例仍保留；材料、防松、夹持力及全机验证未完成。</p></section>'
page=(A/'REVIEW.html').read_text(encoding='utf-8');page=page.replace('同一活动候选 · V9 推进线路与源装配','同一活动候选 · V10 四站主干支撑').replace('<h1>推进两线与电池舱源装配已更新</h1>','<h1>四站主干线支撑及安装实体已集成</h1>').replace('<section>',section+'<section>',1);(A/'REVIEW.html').write_text(page,encoding='utf-8')
print(json.dumps(dict(revision='V10',source_instances=931,local_instances=131,whole_design_complete=False)))
