"""Current source update with the original37 work-package statuses preserved."""
import csv,json,html,urllib.parse
from pathlib import Path
from battery_variant_context import A,read,sha
r=read('results/ROOT_BUSHING_REVIEW.json');assert r['snapshots_actually_reviewed'] and not r['whole_design_complete']
assert all(sha(A/q)==h for q,h in r['inputs'].items()) and all(sha(A/q)==h for q,h in r['snapshots'].items())
def live(stem):return 'http://127.0.0.1:3245/'+urllib.parse.quote(A.as_posix(),safe='/:')+'?file='+urllib.parse.quote(f'mechanical/{stem}.step.py',safe='')
def shot(stem,view):return next(q for q in r['snapshots'] if Path(q).name.startswith(stem+'_'+view+'_'))
v=read('results/DELIVERY_DECISION.json');assert v['candidate_source_components']==931
v['previous_931_source_variant']=dict(source_plan=v['current_source_plan'],source_plan_sha256=v['current_source_plan_sha256'],local_preview_instances=131,source_instances=931)
v.update(schema='WP10_IMPLEMENTATION_DELIVERY_V11',review_revision='V11_ROOT_PASSAGE_CAPTURE',status='ROOT_PASSAGE_CAPTURE_AND936_SOURCE_TABLES_UPDATED__WHOLE_MECHATRONIC_CLOSURE_OPEN',current_source_plan='mechanical/ROOT_BUSHING_INSTANCE_PLAN.json',current_source_plan_sha256=sha(A/'mechanical/ROOT_BUSHING_INSTANCE_PLAN.json'),candidate_source_components=936,current_source_instances_by_state=r['source_instances_by_state'],current_local_source_assembly_instances=136,current_local_step='mechanical/root_bushing_integration.step',root_passage_changed_pairs_by_state=r['exact_pairs_by_state'],root_passage_required_contacts_by_state=r['required_contacts_by_state'],root_passage_nominal_axial_capture_verified=True,root_passage_material_thread_and_strength_qualified=False,current_pending_harness_source_ids=r['known_release_segments_retained'],current_pending_harness_features=['release_branch_and_mast_entry_at_parking_and10degree_fold','upper_M3RB_relief_above115p15_and_strain_relief','actual_wire_endpoints_OD_and_electrical_lengths','liner_material_clamp_force_tolerance_and_full_motion'],full_harness_geometry_status='OPEN_RELEASE_BRANCHES_UPPER_RELIEF_STRAIN_RELIEF_AND_MATERIAL_QUALIFICATION',current_source_plan_whole_fit_verified=False,current_full_native_assembly_generated=False,current_source_mass_inertia_thermal_requalified=False,current_source_view_screen_bound=False,current_source_thermal_network_calculated=False,current_source_CHB_temperature_C=None,engineering_prototype_design_complete=False,goal_complete=False)
v['internal_work_remaining']=[s.replace('Whole931 native assembly','Whole936 native assembly') for s in v['internal_work_remaining']]
v['thermal_core_native_scope']['current936_native_assembly_or_geometry_credit']=False
v['active_next_work_item']=dict(parent_id='A05',same_candidate='mechanical/ROOT_BUSHING_INSTANCE_PLAN.json',next_action='Finish battery/PMM actual retention and protected electrical/charging interfaces; bind actual release hardware and revise branch/moving-mast interface, upper relief and strain relief; continue same-source thermal, fastening, whole-CAD and electrical verification.',read_inputs=['results/ROOT_BUSHING_REVIEW.json','power/BATTERY_INSTALLATION_INTERFACE.json','mechanical/ROOT_BUSHING_BRIEF.md'])
(A/'results/DELIVERY_DECISION.json').write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
rows=list(csv.DictReader((A/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig')));assert len(rows)==37
for q in rows:
    if q['id']=='A05':
        q['execution_state']='ROOT_PASSAGE_AXIAL_CAPTURE_INTEGRATED__WHOLE_ROW_OPEN'
        q['new_evidence']+=' | V11桥板两盲孔及5件分体衬套/开口压板/名义螺钉已集成；完整三态936行、局部136件；衬套保护到z115.15，上部边槽/应变释放仍开放。'
        q['next_source_edit']='真实电池/PMM保持与供电接口；绑定释放器并修正支路/运动入口；上部护套与应变释放、公差材料防松、热和全机验证。'
    if q['id']=='G02':q['new_evidence']+=' | V11三态各18近邻/6必需接触及左右轴向挡止通过；工具通道RB303反例已修复；两释放入口10°实体反例确认并保留。'
    if q['id']=='E05':q['new_evidence']+=' | V11机械6行增量BOM（桥板替换+5新增）绑定源SHA；没有新针序/裁线或通电信用。'
with (A/'SYSTEM_CLOSURE_MATRIX.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
detail=shot('root_bushing_detail','iso');bottom=shot('root_bushing_detail','bottom')
intro=f"""# WP10 当前修订：桥板线束衬套与侧向保持件

桥板过孔已加入可拆分衬套、一体开口金属压板和两颗名义螺钉；整机机电详细设计仍未完成。当前完整源表每态936实例，局部STEP136实例，衬套细节STEP5实例；没有生成当前936整星原生SolidWorks装配。

[旋转查看136件局部装配]({live('root_bushing_integration')}) · [STEP](mechanical/root_bushing_integration.step) · [5件细节]({live('root_bushing_detail')}) · [936完整源表](mechanical/ROOT_BUSHING_INSTANCE_PLAN.json) · [6行增量BOM](mechanical/ROOT_BUSHING_INSTANCE_BOM.csv) · [绑定证据](results/ROOT_BUSHING_REVIEW.json)

桥板新增两处名义螺纹主径盲孔，只减料63.617251mm³，原孔与其余源保留。两半衬套D9.8/内孔6.6，以D14法兰和0.1mm轴向间隙被保持；单件开口压板按20mm侧向通道设计，两固定轴移至S(53,-80)/(53,-70)。初版右螺钉工具杆被RB303挡住233.29788mm³，现已改件修复。

三态各18对改变近邻无穿透，6处必需接触成立；左右半衬套下降0.1mm的实际挡止面积54.286721/29.498275mm²，与只读审阅者独立复算一致。D5×25工具空间分配通过，压板20mm直线保守扫掠无穿透；未冒称已选工具或完整装配过程。7个CAD入口已检，8张快照已逐张查看。[尺寸、选材和装配顺序](mechanical/ROOT_BUSHING_BRIEF.md)

保护只到z115.15，M3RB上部边槽、应变释放和四段释放支路仍开放。当前桅杆实体已确认两个固定释放端点在折叠10°时进入管壁；释放器仍为未选型功能包络，不能直接改背面端口或切弱桅杆。公差场景计偏心后余量0.06mm，实际线束/孔位/热变形等未绑定，因此公差、螺纹、强度、材料放气和连续运动仍未获合格信用。

选材参考 [Victrex 450G March 2026官方数据表](https://www.victrex.com/-/media/downloads/datasheets/victrex_tds_450g.pdf?rev=66e2f2641768427097e4ad8ce08deb49)，成品料和批次未确认。电气仍是201位号/11页既有源。本轮未重算936布局的质量、惯量和热网络；旧894热证据、38件原生导热核心保持原范围。37行状态仍为13限定完成、19内部开放、4外部未绑定、1物理未执行。

![5件衬套及保持组件，桥板未显示]({detail})

![压板下方双螺钉]({bottom})

---

下文是V10及更早修订的历史验证范围。当前布局以上述V11源表为准。

"""
(A/'README.md').write_text(intro+(A/'README.md').read_text(encoding='utf-8'),encoding='utf-8')
links=[('136件局部装配',live('root_bushing_integration')),('局部装配STEP','mechanical/root_bushing_integration.step'),('5件细节',live('root_bushing_detail')),('完整936源表','mechanical/ROOT_BUSHING_INSTANCE_PLAN.json'),('增量BOM','mechanical/ROOT_BUSHING_INSTANCE_BOM.csv'),('检查证据','results/ROOT_BUSHING_REVIEW.json'),('设计尺寸','mechanical/ROOT_BUSHING_BRIEF.md')]+[(label,live(stem)) for label,stem in [('左半衬套','root_bush_left'),('右半衬套','root_bush_right'),('开口压板','root_keeper'),('名义螺钉','root_screw_8'),('更新桥板','root_bridge')]]
section='<section><h2>当前：桥板衬套与侧向保持件</h2><p class="flag">三态各18对近邻、6处必需接触及两半轴向挡止通过。936是完整源表数量，整机机电设计仍开放。</p><img src="'+detail+'" alt="5件衬套组件，桥板未显示"><nav>'+''.join('<a href="'+html.escape(u,quote=True)+'">'+html.escape(t)+'</a>' for t,u in links)+'</nav><img src="'+bottom+'" alt="压板底部双固定点"><p>工具通道反例已改件修复。只保护桥板和M3RB下部2mm；上部边槽、应变释放及释放入口10°干涉保留。螺纹、材料、公差、强度和全机热验证未完成。</p></section>'
page=(A/'REVIEW.html').read_text(encoding='utf-8').replace('同一活动候选 · V10 四站主干支撑','同一活动候选 · V11 桥板线束衬套').replace('<h1>四站主干线支撑及安装实体已集成</h1>','<h1>桥板过孔衬套与保持实体已集成</h1>').replace('<section>',section+'<section>',1)
(A/'REVIEW.html').write_text(page,encoding='utf-8')
print(json.dumps(dict(revision='V11',source_instances=936,local_instances=136,whole_design_complete=False)))
