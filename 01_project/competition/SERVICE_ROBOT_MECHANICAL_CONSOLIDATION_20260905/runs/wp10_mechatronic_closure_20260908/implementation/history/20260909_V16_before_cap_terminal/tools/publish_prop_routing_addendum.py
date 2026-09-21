"""Publish the reviewed same-candidate source variant and its actual local STEP."""
from pathlib import Path
import json,csv,html,urllib.parse
from battery_variant_context import A,read,sha
r=read('results/PROP_ROUTING_REVIEW.json');plan=read('mechanical/BATTERY_ROUTE_INSTANCE_PLAN.json');mem=read('results/PROP_ROUTING_MEMORY_AUDIT.json')
assert r['snapshots_actually_reviewed'] and r['local_preview_instances']==85 and not r['whole_design_complete'] and mem['all_jobs_terminal']
assert all(sha(A/q)==h for q,h in r['inputs'].items()) and all(sha(A/q)==h for q,h in r['snapshots'].items())
def live(stem):
    assert (A/f'mechanical/{stem}.step.py').exists();return 'http://127.0.0.1:3245/'+urllib.parse.quote(A.as_posix(),safe='/:')+'?file='+urllib.parse.quote(f'mechanical/{stem}.step.py')
def shot(stem,view):return next(q for q in r['snapshots'] if Path(q).name.startswith(f'{stem}_{view}_'))
iso=shot('battery_route_integration','iso');top=shot('battery_route_integration','top')
v=read('results/DELIVERY_DECISION.json');assert len(v['remaining_open_ids'])==23
v.update(review_revision='V9_PROPULSION_ROUTING_SOURCE_VARIANT',status='PROPULSION_ROUTES_DUAL_SUPPORT_AND893_SOURCE_VARIANT_UPDATED__WHOLE_MECHATRONIC_CLOSURE_OPEN',current_source_plan='mechanical/BATTERY_ROUTE_INSTANCE_PLAN.json',candidate_source_components=893,current_source_instances_by_state=r['complete_source_instance_count_by_state'],local_propulsion_source_assembly_instances=85,propulsion_changed_instance_count=17,propulsion_changed_pairs_by_state=r['geometry_pair_checks_by_state'],propulsion_full_electrical_endpoints_bound=False,battery_body_present_in_current_source_plan=True,battery_retention_geometry_bound=False,current_source_plan_whole_fit_verified=False,current_full_native_assembly_generated=False,current_source_mass_inertia_thermal_requalified=False,current_pending_harness_source_ids=r['remaining_pending_harness_ids'],full_harness_geometry_status='OPEN_TRUNK_SUPPORTS_AND_RELEASE_BRANCH_INTERFACE',goal_complete=False,engineering_prototype_design_complete=False)
v['active_next_work_item']=dict(parent_id='A05',same_candidate='mechanical/BATTERY_ROUTE_INSTANCE_PLAN.json',next_action='Replace8 retained main-trunk clip/support instances with supports for the new continuous path; redesign the fixed release-entry/parking-mast conflict without inventing vendor pins; finish real battery/PMM and device retention, liners, strength/thermal/mass and complete CAD/ECAD/harness binding.',read_inputs=['results/PROP_ROUTING_REVIEW.json','results/RELEASE_PORT_CLEARANCE_COUNTEREXAMPLE.json','power/BATTERY_INSTALLATION_INTERFACE.json'])
legacy_keys=['same_revision_view_screen_bound','local_view_network_calculated','CHB_only_nominal_folded330K_case_C','CHB_only_hot350K_case_C']
v['legacy_894_thermal_evidence']=dict(source_plan='mechanical/FIXED_HEAT_INSTANCE_PLAN.json',source_plan_sha256=sha(A/'mechanical/FIXED_HEAT_INSTANCE_PLAN.json'),source_instance_count=894,scope='V7 fixed heat layout only; not a thermal evaluation of the current893 source variant',values={k:v.pop(k) for k in legacy_keys},evidence_sha256={q:sha(A/q) for q in ['thermal/SPATIAL_RADIATOR_NETWORK_SCREEN.json','thermal/RADIATOR_MESH_VIEW_SCREEN.json','results/FIXED_HEAT_INTERFACE_SUMMARY.json','results/NATIVE_COLD_COLD.json']})
v.update(schema='WP10_IMPLEMENTATION_DELIVERY_V9',current_source_plan_sha256=sha(A/'mechanical/BATTERY_ROUTE_INSTANCE_PLAN.json'),current_source_view_screen_bound=False,current_source_thermal_network_calculated=False,current_source_CHB_temperature_C=None)
v['thermal_core_native_scope']=dict(source_plan='mechanical/FIXED_HEAT_INSTANCE_PLAN.json',source_plan_sha256=sha(A/'mechanical/FIXED_HEAT_INSTANCE_PLAN.json'),native_instances=38,current893_native_assembly_or_geometry_credit=False)
v['internal_work_remaining']=[s.replace('Whole894 native assembly','Whole893 native assembly').replace('current CHB-only geometry','legacy894 CHB-only geometry') for s in v['internal_work_remaining']]
(A/'results/DELIVERY_DECISION.json').write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
rows=list(csv.DictReader((A/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig')));assert len(rows)==37
for q in rows:
    q['next_source_edit']=q['next_source_edit'].replace('whole894 native','whole893 native')
    if q['id']=='A05':
        q['new_evidence']+=' | V9：推进两线/双孔夹具/支柱/拉杆/8复用紧固件及甲板17实例已集成到三态各893行源表；85件局部STEP已验证，12件未闭环线束仍在完整表中。'
        q['next_source_edit']='按893源表重做8主干支撑、4段释放分支及其停车态入口冲突；完成实际电池/PMM/设备保持、护套、强度热质量及端接。'
    if q['id']=='G02':q['new_evidence']+=' | V9推进改件三态各66对0反例；释放末段与parking保持杆各约208.889mm³穿透保留。'
    if q['id']=='E05':q['new_evidence']+=' | 推进DATA机械起点改为未绑定功能交接位置，未产生厂家针脚/裁线信用；机械17行增量BOM已单列。'
with (A/'SYSTEM_CLOSURE_MATRIX.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
text=f'''# WP10 当前修订：推进两线与电池舱源装配

**推进线路与安装支撑已实际更新，整机机电详细设计仍OPEN。** 三态完整候选源表均为893实例；85件局部STEP已生成、检查并查看。893是完整源表数量，尚未生成当前整星原生SolidWorks装配，也未证明全件装配通过。

[旋转查看85件局部装配]({live('battery_route_integration')}) · [局部装配STEP](mechanical/battery_route_integration.step) · [三态893实例完整源表](mechanical/BATTERY_ROUTE_INSTANCE_PLAN.json) · [17实例改件BOM](mechanical/BATTERY_PROPULSION_INSTANCE_BOM.csv) · [本轮源绑定与审阅](results/PROP_ROUTING_REVIEW.json)

本轮更新17实例：推进供电/数据两条OD6、中心线R21包络，双孔夹具底座/盖、两支柱、两根名义M3杆、8件原来源垫圈/螺母及甲板。原PWR起点和单路夹具保留；DATA原功能起点进入电池，因此迁到S(45,34,59)的功能交接位置。该位置没有厂家针脚依据，上游真实接续仍未完成。两个模块侧功能末端保持原坐标。

夹具孔径8mm，中心线y34/48、z59mm；支柱中心(72,41)/(88,41)，高度60.5mm。甲板增加两Ø3.4通孔，实际只移除54.475216613mm³指定材料，增料、柱外减料及漏切为零，旧孔保留。支撑孔与OD6存在约1mm径向空间，不能称为已夹紧；护套、夹持力、材料、防松、螺纹、强度及公差仍待完成。[设计源与说明](mechanical/BATTERY_PROPULSION_ROUTE_BRIEF.md)

三态分别完成66对变化邻域实际STEP检查，均无正体积穿透及意外零间隙；两推进线最小间隙3.123238mm，PWR/DATA到导航盒分别3/2mm，夹具到导航盒1mm。8个CAD入口通过refs及几何有效性检查，9张快照已实际查看。以上只证明相应固定状态的几何，不证明端接、温升、连续运动、完整整星或实物。

完整源表计数为894−3旧中央线段＋1新连续主线＋1电池最大盒＝893。8件旧主干夹具/支柱及4段旧释放线路均仍保留在表中并标明责任，未通过删除负例取得完整装配信用。旧电池功能也保留；新RRC仍是D版最大外包络，电池保持和PMM实际安装未完成。

释放支路的停车态入口已做实际STEP诊断：原功能端点中心到保持杆仅1mm，原末段每条与杆穿透约208.889mm³；特定R14侧向接近样点落在杆壁内。service/released旧末段也仍穿透约184.715mm³。保留原端点并登记局部接口需改，不改成背面端口冒充解决。该诊断不声称证明所有可能路线均不可行。[真实端部反例](results/RELEASE_PORT_CLEARANCE_COUNTEREXAMPLE.json)

当前893布局的质量/惯量、热分布与结构校核未完成，原894热布局和38件原生导热核心的限定证据单独保留，不自动授予本次迁移布局。37行闭环表仍为13项限定完成、19项内部开放、4项外部未绑定、1项物理未执行。[机器裁决](results/DELIVERY_DECISION.json)

本轮所有重型任务已串行结束，最低记录可用内存{mem['minimum_available_mib']:.0f}MiB、最大任务工作集{mem['maximum_combined_rss_mib']:.0f}MiB；未突破原内存守卫阈值。[内存记录](results/PROP_ROUTING_MEMORY_AUDIT.json)

![当前85件局部修改]({iso})

---

下文保留V8电池布局基础和V7导热核心的具体范围；当前候选源表以上述V9为准。

'''
(A/'README.md').write_text(text+(A/'README.md').read_text(encoding='utf-8'),encoding='utf-8')
def links(items):return '<nav>'+''.join('<a href="'+html.escape(u,quote=True)+'">'+html.escape(t)+'</a>' for t,u in items)+'</nav>'
section='<section><h2>当前85件推进布线与电池舱局部装配</h2><p class="flag">三态完整源表各893实例，仍保留12件未解决线束对象。85件是本轮局部STEP，当前整星原生SolidWorks和整机闭环未完成。</p><img src="'+iso+'" alt="当前85件推进线束和支撑修改">'+links([('旋转查看当前局部装配',live('battery_route_integration')),('局部STEP','mechanical/battery_route_integration.step'),('完整893实例源表','mechanical/BATTERY_ROUTE_INSTANCE_PLAN.json'),('17行改件BOM','mechanical/BATTERY_PROPULSION_INSTANCE_BOM.csv'),('当前审阅与源绑定','results/PROP_ROUTING_REVIEW.json')])+'<img src="'+top+'" alt="当前推进布局顶视图"><p>17实例更新，三态各66对检查未发现穿透；两线最小间隙3.123238mm。DATA起点为未绑定的功能交接位置，夹具护套与夹持力未完成。释放入口及旧线路穿透保留，整体线束仍OPEN。</p>'+links([(stem,live(stem)) for stem in ['battery_prop_power','battery_prop_data','battery_dual_base','battery_dual_lid','battery_dual_post','battery_dual_rod','battery_route_deck']])+links([('释放端口真实反例','results/RELEASE_PORT_CLEARANCE_COUNTEREXAMPLE.json'),('本轮内存记录','results/PROP_ROUTING_MEMORY_AUDIT.json')])+'</section>'
page=(A/'REVIEW.html').read_text(encoding='utf-8');page=page.replace('同一活动候选 · V8 局部修订','同一活动候选 · V9 推进线路与源装配').replace('<h1>电池舱重布置与主干线通道已生成</h1>','<h1>推进两线与电池舱源装配已更新</h1>');page=page.replace('<section>',section+'<section>',1);(A/'REVIEW.html').write_text(page,encoding='utf-8')
print(json.dumps(dict(revision='V9',source_instances=893,local_instances=85,whole_design_complete=False)))
