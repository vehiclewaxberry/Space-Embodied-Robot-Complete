"""Add the reviewed local battery increment without replacing the thermal baseline."""
from pathlib import Path
import json,hashlib,csv,html,urllib.parse
A=Path(__file__).resolve().parents[1]
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
r=read('results/BATTERY_BAY_REVIEW.json');route=read('results/BATTERY_INTERNAL_ROUTE_SCREEN.json');mem=read('results/BATTERY_MEMORY_AUDIT.json')
assert r['snapshots_actually_reviewed'] and r['local_instances']==55 and not r['whole_design_complete']
assert all(sha(A/q)==h for q,h in r['inputs'].items()) and all(sha(A/q)==h for q,h in r['snapshots'].items())
assert not route['branch_fit_proved'] and not r['whole_candidate_integrated'] and mem['all_current_jobs_terminal']
def live(stem):
    assert (A/f'mechanical/{stem}.step.py').exists()
    return 'http://127.0.0.1:3245/'+urllib.parse.quote(A.as_posix(),safe='/:')+'?file='+urllib.parse.quote(f'mechanical/{stem}.step.py')
def shot(stem,view):return next(q for q in r['snapshots'] if Path(q).name.startswith(f'{stem}_{view}_'))
iso=shot('battery_bay_layout','iso');top=shot('battery_bay_layout','top')
v=read('results/DELIVERY_DECISION.json');assert len(v['remaining_open_ids'])==23
v.update(review_revision='V8_LOCAL_BATTERY_RELAYOUT',battery_packaging_screen_status='EXACT_LOCAL_RELAYOUT_CLEAR__MOUNT_ROUTES_AND_INTEGRATION_PENDING',battery_local_preview_instances=55,battery_moved_instances=38,battery_local_geometry_reviewed=True,battery_current_instance_integrated=False,battery_retention_geometry_bound=False,battery_internal_route_geometry_status=route['status'],full_harness_geometry_status=route['full_harness_geometry_status'],battery_local_step='mechanical/battery_bay_layout.step',battery_review_evidence='results/BATTERY_BAY_REVIEW.json',whole_new_layout_thermal_verified=False,new_native_battery_assembly_generated=False,engineering_prototype_design_complete=False,goal_complete=False)
v['active_next_work_item']=dict(parent_id='A05',same_candidate='mechanical/FIXED_HEAT_INSTANCE_PLAN.json',local_edit_contract='mechanical/BATTERY_BAY_LAYOUT.json',next_action='Redesign retained release branches, propulsion routes and27 pending route/clamp instances; complete actual device hold-down and battery/PMM mechanical interfaces, passage sleeve/strain relief and affected strength/thermal checks before replacing894 parent layout.',read_inputs=['results/BATTERY_BAY_REVIEW.json','results/BATTERY_INTERNAL_ROUTE_SCREEN.json','power/BATTERY_INSTALLATION_INTERFACE.json'])
(A/'results/DELIVERY_DECISION.json').write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
rows=list(csv.DictReader((A/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig')));assert len(rows)==37
for row in rows:
    if row['id']=='A05':
        row['new_evidence']='55件电池舱局部STEP：38实例迁移、甲板四孔、导航四支座、驱动载板避让、桥板穿孔/M3RB开边槽及OD6/R21主线；源SHA/实体检查/8快照已绑定。厂家最大电池包络不是OEM实体。 | results/BATTERY_BAY_REVIEW.json'
        row['next_source_edit']='保留功能重做27件线路夹具及2条释放支路；完成电池保持、PMM及设备固定、护套和受影响热/强度后整舱集成。'
    if row['id']=='G02':row['new_evidence']+=' | 本轮主线service态38对局部STEP筛查；两条释放支路各与M3RB穿透仍开放，不授予完整线束或连续动作信用。'
with (A/'SYSTEM_CLOSURE_MATRIX.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
text=f'''# WP10 新增：电池舱重布置与主干线通道

**55件局部装配已生成并查看，整机机电设计仍未完成。** 当前894实例热设计父布局及38件原生SolidWorks导热核心保留；本次55件STEP是同一候选的局部修改验证件，尚未替代整舱或生成新的原生SolidWorks装配。

[旋转查看55件装配]({live('battery_bay_layout')}) · [下载局部STEP](mechanical/battery_bay_layout.step) · [改件说明](mechanical/BATTERY_BAY_BRIEF.md) · [本轮审阅与源绑定](results/BATTERY_BAY_REVIEW.json)

RRC3570-4 D最大矩形包络189.5×85.5×82.2mm，按S系轴序189.5×82.2×85.5mm布置。38个原设备/托盘/支撑实例整体迁移，保留原功能；实际增加四个甲板孔、四个导航壁面支座、驱动载板边缘避让。当前设备仍含功能盒表示；电池插座、夹持接触区及保持结构未绑定。初始反例与历次修复保留在history。

中央主线改为连续OD6、中心线弯曲半径≥21mm，从电池下方通过。对最大电池盒实体间隙{r['battery_clearance_mm']:.6f}mm；原上升段穿透桥板169.646003mm³、M3RB68.565260mm³，已通过桥板Ø10通孔和M3RB R5开边槽修复。两件各只移除规定区域471.238898mm³，柱外减料、漏切和增料均为0。原固定孔位保留；护套、应变释放、孔边强度及公差仍未完成。[主线窄相位及反例](results/BATTERY_INTERNAL_ROUTE_SCREEN.json)

**完整线束仍OPEN。** 两条原释放支路同轴重合105mm／1319.468915mm³，各与新M3RB仍穿透456.336140mm³。主线接续例外仅限终点附近10mm立方区，未把整条支路豁免。原27件待重做线路/夹具，加上这2条释放支路，均保留设计责任。未获得真实针脚、分线器、裁线、电流、动态寿命或全线束装配信用。

本次8个CAD入口均通过refs和几何有效性检查，主线检查38个邻近对象；局部装配采用固定根和部件局部基准。8张视图已实际检查。迁移后整舱热分布与强度须重算，原894布局的热结果不自动授予本次55件修改。37行责任表的完成等级保持不变。

本轮串行任务已结束并释放任务资源，记录中最低可用内存{mem['minimum_sampled_available_mib']:.0f}MiB、最大任务合计工作集{mem['maximum_sampled_combined_rss_mib']:.0f}MiB；启动2GiB、运行512MiB及任务1400MiB约束保持。[内存回执](results/BATTERY_MEMORY_AUDIT.json)

![55件电池舱局部修改]({iso})

---

'''
old=(A/'README.md').read_text(encoding='utf-8')
old=old.replace('下一步必须先确定设备局部迁移和窄相位检查，再生成托架。','该初筛现作为历史输入；本轮已完成上文局部迁移和主线窄相位，托架及整舱集成仍待完成。')
(A/'README.md').write_text(text+old,encoding='utf-8')
def links(items):return '<nav>'+''.join('<a href="'+html.escape(url,quote=True)+'">'+html.escape(label)+'</a>' for label,url in items)+'</nav>'
section='<section><h2>新增55件电池舱局部装配</h2><p class="flag">电池采用厂家最大外包络，设备保持、27件线路夹具和2条释放支路仍需完善。本STEP未替代894整舱，未生成新的原生SolidWorks装配。</p><img src="'+iso+'" alt="55件局部装配：电池外包络、迁移设备和主线通道">'+links([('旋转55件装配',live('battery_bay_layout')),('局部装配STEP','mechanical/battery_bay_layout.step'),('实际改件说明','mechanical/BATTERY_BAY_BRIEF.md'),('当前源绑定与审阅','results/BATTERY_BAY_REVIEW.json'),('内存回执','results/BATTERY_MEMORY_AUDIT.json')])+'<img src="'+top+'" alt="电池舱局部顶视图"><p>主线对电池间隙4.107556mm；桥板Ø10通孔与M3RB R5开边槽已清除原立段干涉。两条释放支路原105mm重合与各456.336140mm³安装板穿透仍OPEN。孔边强度、护套、夹具和端接尚未验收。</p>'+links([(stem,live(stem)) for stem in ['upper_deck_battery_layout','wall_navigation_bosses','arm_adapter_battery_layout','bridge_harness_passage','m3rb_harness_relief','battery_internal_route']])+links([('主线实体距离与支路负结果','results/BATTERY_INTERNAL_ROUTE_SCREEN.json')])+'</section>'
page=(A/'REVIEW.html').read_text(encoding='utf-8');page=page.replace('同一活动候选 · V7','同一活动候选 · V8 局部修订').replace('<h1>CHB底部与双侧壁导热核心已生成</h1>','<h1>电池舱重布置与主干线通道已生成</h1>');page=page.replace('<section>',section+'<section>',1)
page=page.replace('当前舱内初筛需要局部重新布置；尚未生成或安装电池托架。','本轮已形成55件局部迁移与主线通道验证装配；电池托架及完整布置仍未完成。')
(A/'REVIEW.html').write_text(page,encoding='utf-8');print(json.dumps(dict(revision='V8_LOCAL_BATTERY_RELAYOUT',local_instances=55,remaining_parent_open=23,whole_design_complete=False)))
