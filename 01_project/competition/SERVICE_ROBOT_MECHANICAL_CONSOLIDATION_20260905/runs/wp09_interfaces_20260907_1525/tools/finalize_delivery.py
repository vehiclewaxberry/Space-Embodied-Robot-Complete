"""Independent file/receipt binding; no CAD execution or scientific Gate mutation."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import json,hashlib,csv,copy
R=Path(__file__).resolve().parents[1]
def read(p):return json.loads((R/p).read_text(encoding='utf-8'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def dump(p,d):(R/p).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def fact(p):
    p=Path(p);p=p if p.is_absolute() else R/p
    return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def norm(p):return str(Path(p).resolve()).casefold()
def t16(T):return [T[i][j] for j in range(3) for i in range(3)]+[T[i][3]/1000 for i in range(3)]+[1.,0.,0.,0.]
def writecsv(p,rows):
    with (R/p).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
c=read('inputs/INTEGRATION_HARNESS_CONTRACT_V6.json');cm=read('results/CANONICAL_NATIVE_INPUTS.json');mf=read('results/INTEGRATION_MANIFEST_V6.json');em=read('results/EMISSION_V6.json');geo=read('results/INTEGRATION_CHECK_V6.json');mat=read('results/NATIVE_MATERIAL_CHECK_V2.json')
assert geo['status']=='DELTA_GEOMETRY_CLEAR' and not geo['unapproved'] and not geo['functional_conflicts']
assert mat['status']=='PASS_ALL_CANONICAL_NATIVE_MATERIAL_TRANSFERS'
new={x['id']:x for x in cm['instances']};assert len(new)==82 and len(cm['unique_parts'])==21
frozen=[dict(path=p,expected_sha256=h,actual_sha256=sha(p)) for p,h in c['source_inputs'].items()]
assert all(x['expected_sha256']==x['actual_sha256'] for x in frozen)
states={};dependencies={};boms={};bindings={}
for state in ('service','parking','released'):
    rp={'service':'results/NATIVE_SERVICE_RECOVERY.json','parking':'results/NATIVE_PARKING_RECOVERY_V3.json','released':'results/NATIVE_RELEASED.json'}[state]
    receipt=read(rp);expected_status='PASS_FIXED_POSE_NATIVE_DELTA_COLD_BODY_AND_TRANSFORM_CHECK' if state=='service' else 'PASS_FIXED_POSE_NATIVE_NEW_BODY_AND_ALL_METADATA_WITH_HASH_BOUND_PARENT'
    assert receipt['status']==expected_status
    np=R/'native'/('WP09_'+state.upper()+'.SLDASM');native=fact(np)
    assert native['sha256']==(receipt['native_sha256'] if state=='service' else receipt['native_save']['sha256'])
    rows=copy.deepcopy(mf['states'][state]['instances']);observed={x['id']:x for x in receipt['cold_components']}
    assert len(rows)==len(observed)==len(receipt['cold_components'])==701
    assert {x['id'] for x in rows}==set(observed)
    bom=[]
    for row in rows:
        k=row['id'];assert sha(row['step_path'])==row['source_sha256'];o=observed[k]
        if k in new:
            q=new[k];row.update(native_path=str(R/'native/p'/(q['canonical_id']+'.SLDPRT')),native_T_local_to_S=q['T_native_to_S'],canonical_id=q['canonical_id'])
        else:row.update(native_T_local_to_S=row['T_S_local'],canonical_id=None)
        npart=Path(row['native_path']);h=sha(npart)
        assert norm(o['path'])==norm(npart) and o['sha256']==h and o['fixed']
        if k not in new:assert h==row['native_sha256']
        assert len(o['transform_sw16'])==16 and max(abs(a-b) for a,b in zip(o['transform_sw16'],t16(row['native_T_local_to_S'])))<=1e-8
        if state=='service' or k in new:
            assert o['actual_solids']==row.get('expected_solids',1) and o['actual_sheets']==0
        if k in new:assert o['basis_max_error_mm']<=1e-5
        row['native_sha256']=h;dependencies[norm(npart)]=fact(npart)
        row['body_evidence']='ACTUAL_CURRENT_COLD_READBACK' if state=='service' or k in new else 'HASH_BOUND_WP08_STATE_RECEIPT_CURRENT_METADATA_VERIFIED'
        bom.append(dict(state=state,id=k,change=row.get('change','RETAIN'),representation_role=row['representation_role'],canonical_id=row['canonical_id'] or '',expected_solids=row.get('expected_solids',1),source_step=row['step_path'],source_sha256=row['source_sha256'],native_path=str(npart),native_sha256=h,native_T_local_to_S=json.dumps(row['native_T_local_to_S']),body_evidence=row['body_evidence'],material='UNBOUND_THIS_ROUND',mass_kg='',mass_note='No total mass/inertia update credited by this geometry delivery'))
    total=sum(x.get('expected_solids',1) for x in rows);assert total==1082
    actual_count=sum(x.get('actual_solids',0) for x in observed.values())
    assert actual_count==(1082 if state=='service' else 82)
    states[state]=dict(native=native,execution_receipt=fact(rp),component_count=701,expected_solid_count=1082,actual_current_cold_solid_count=actual_count,hash_bound_retained_solid_count=0 if state=='service' else 1000,all_component_identity_file_hash_transform_fixed_state_verified=True,new_instances_4_point_basis_verified=82,representation_roles=dict(Counter(x['representation_role'] for x in rows)),fixed_pose_only=True)
    bindings[state]=rows;boms[state]=bom;writecsv('results/ASSEMBLY_BOM_'+state.upper()+'.csv',bom)
delta=[]
for k,q in new.items():
    p=em['parts'][k]
    delta.append(dict(id=k,canonical_id=q['canonical_id'],representation_role=q['source_role'],operation=p['operation'],qualification=p.get('qualification','NOT_EVALUATED'),source_step=q['source_step'],native_path=str(R/'native/p'/(q['canonical_id']+'.SLDPRT')),nominal_volume_mm3=p['volume_mm3'],material='',mass_kg='',manufacturing_release=False))
writecsv('results/DELTA_BOM_82.csv',delta);writecsv('results/NATIVE_DEPENDENCIES.csv',list(dependencies.values()))
dump('results/NATIVE_BINDING_MANIFEST.json',dict(schema='WP09_NATIVE_SOURCE_BINDING_V1',source_manifest=fact('results/INTEGRATION_MANIFEST_V6.json'),canonical_manifest=fact('results/CANONICAL_NATIVE_INPUTS.json'),states=bindings,transform_note='Source STEP T_S_local and native_T_local_to_S differ for translation-normalized canonical parts. Never apply source identity to a canonical native part.'))
dump('results/INDEPENDENT_NATIVE_BINDING_CHECK.json',dict(status='PASS_ALL_THREE_FIXED_POSE_FILE_RECEIPT_BINDINGS',states=states,unique_native_dependencies=len(dependencies),frozen_input_count=len(frozen),frozen_inputs_unchanged=True,check_scope='Independent Python JSON/file/hash/matrix check; uses actual SolidWorks receipts and does not repeat COM reads.',no_new_motion_or_manufacturing_credit=True))
dump('results/FROZEN_INPUT_RECHECK.json',dict(status='PASS',count=len(frozen),files=frozen))
closed=read('results/FRONT_SERVICE_PRISM_CHECK.json');conditional=read('results/FRONT_SERVICE_ACCESS_CONDITIONAL.json')
status=dict(schema='WP09_INTERFACE_DELIVERY_FACT_SNAPSHOT',utc=datetime.now(timezone.utc).isoformat(),status='THREE_NATIVE_FIXED_POSES_AND_V6_DELTA_VERIFIED__DM_GROUND_POWER_SELECTED__ELECTRICAL_AND_FLIGHT_RELEASE_OPEN',target='可装配工程样机设计候选',native_states=states,retained_components_per_state=619,removed_components=mf['removed_parent_ids'],new_or_replacement_instances=82,unique_new_native_parts=21,whole_step_export='NOT_DELIVERED_MEMORY_GUARD; LOCAL_BAY_STEP_DELIVERED',local_bay_step=fact('candidate/integrated_bay_v6.step'),source=fact('candidate/integrated_bay.step.py'),geometry=dict(check=fact('results/INTEGRATION_CHECK_V6.json'),narrow_phase_pairs=geo['pair_count'],unapproved_material_overlap=0,functional_conflicts=0,full_parent_parent_recheck=False,continuous_motion=False),service_access=dict(closed_cover_status=closed['status'],conditional_status=conditional['status'],tool_access_verified=False,plume_verified=False),electrical=dict(dm_version_confirmed=True,arm_supply='EXTERNAL_GSE_MEAN_WELL_RSP-500-24',bpx_scope='LOW_POWER_AVIONICS_AND_PROPULSION_INTERFACE_ONLY',complete_end_to_end_circuits=0,actual_wire_area_and_cut_length_bound=False,prefab_steps_executed=0,power_on_verified=False),propulsion=dict(candidate='OLD_VACCO_X14029003-1_REV6_15_MECHANICAL_INTERFACE_REFERENCE',nonpressure_mockup_only=True,flight_unit_selected=False,pressure_release=False),b601_geometry_revision='DM_SHIPMENT_MECHANICAL_REVISION_NOT_YET_BOUND',manufacturing_release=False,flight_release=False,continuous_mate_motion_verified=False,self_contained_pack_and_go=False,reference_scope='Native assemblies reference inherited local project dependencies; see NATIVE_DEPENDENCIES.csv.',evidence_links=[fact(x) for x in ['research/FINAL_SELECTION_DM_ZH.md','research/B601_DM_GEOMETRY_PROVENANCE_NOTE.json','docs/SELECTED_DM_ARCHITECTURE_ZH.md','docs/HARNESS_LAYOUT_S_WORLD.svg','docs/CLOSURE_DELTA_AND_OPEN_ITEMS_ZH.md','results/CLOSURE_ISSUE_LEDGER.json','ecad/From-To.csv','ecad/DM_SELECTED_FROM_TO.csv','results/NATIVE_MATERIAL_CHECK_V2.json','results/INDEPENDENT_NATIVE_BINDING_CHECK.json']])
dump('results/DELIVERY_STATUS.json',status)
def link(label,p):return '['+label+'](<'+(R/p).as_posix()+'>)'
viewer='http://127.0.0.1:3245/F:/China%20Graduate%20Future%20Flight%20Vehicle%20Innovation%20Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525?file=candidate%2Fintegrated_bay.step.py'
lines=['# WP09 共享舱、推进接口与静态线束交付','',
'已生成三套 SolidWorks 固定姿态总装，每套 **701 个组件、1082 个几何实体**。本轮保留619个旧组件，移除6个责任件，插入82个新/替换实例；新实例共享21个原生零件。实体统计包含设备与线束功能包络，不等于1082件可采购零件。','',
'交付等级：**工程样机设计候选**。整星机械、电气、制造与飞行放行仍开放。','',
'组件角色为231个PHYSICAL_GEOMETRY、430个SIMPLIFIED_PROXY、40个FUNCTIONAL_ENVELOPE。这些是源合同的表示类别；实体几何本身也不等于已经获得制造细节或实物符合性验证。','',
'| 查看内容 | 文件 |','|---|---|',
'| 服务姿态总装 | '+link('WP09_SERVICE.SLDASM','native/WP09_SERVICE.SLDASM')+' |',
'| 停放姿态总装 | '+link('WP09_PARKING.SLDASM','native/WP09_PARKING.SLDASM')+' |',
'| 释放姿态总装 | '+link('WP09_RELEASED.SLDASM','native/WP09_RELEASED.SLDASM')+' |',
'| 共享舱与推进线束局部 STEP | '+link('integrated_bay_v6.step','candidate/integrated_bay_v6.step')+' |',
'| 参数化源模型 | '+link('integrated_bay.step.py','candidate/integrated_bay.step.py')+' |',
'| 可旋转 CAD 查看 | [打开 CAD Viewer]('+viewer+') |','',
'SolidWorks使用2024版生成的原生SLDASM/SLDPRT，几何由经过回导验证的STEP导入。装配采用固定实例与明确变换；没有运动配合或可编辑的原生特征历史。总装仍引用本机既有项目零件，依赖清单见 '+link('NATIVE_DEPENDENCIES.csv','results/NATIVE_DEPENDENCIES.csv')+'；本目录不是独立Pack-and-Go包。完整整星STEP导出触发内存保护，因此只交付经验证的局部STEP及完整原生总装。','',
'## 本轮具体改变','',
'- 旧型号MiPS接口样件改至+X侧非承压托架，上甲板开缺口，原ADCS空间预留保留。旧MiPS与新版商品参数没有混用。',
'- P60保守包络移至上层，新增载板、支柱、拉杆和紧固件。真实PCB到载板的孔系与器件支撑仍待绑定。',
'- 推进电源和RS-422数据分路，新增穿舱护圈、可拆导向块及支承。名义束径6mm、中心线半径21mm；PWR路径316.9734mm、DATA路径204.9734mm。路径长度不是下料长度。',
'- 用户已确认B601 DM。工程样机选外置RSP-500-24（24V/21A），BPX 8S/P60限低功率支路。现有CAD与DM出货机械修订尚未核对。','',
'选型理由和官方来源见 '+link('DM选型说明','research/FINAL_SELECTION_DM_ZH.md')+'；供电架构见 '+link('供电与接口图','docs/SELECTED_DM_ARCHITECTURE_ZH.md')+'。旧MiPS仅作非承压机械接口参考，实际飞行推进单元尚未选定。','',
'## 验证与边界','',
f"V6完成{geo['pair_count']}组去重BRep窄相检查，新件之间及新件对三态邻件未发现未许可材料重叠或原功能预留冲突。旧件之间不重复获得本轮检查信用。21个新原生零件均通过冷重开、实体/单位/包络核对和材料回导比较。服务态实读全部701组件/1082实体；停放和释放态实读82个新实体，并核对全部701组件的身份、文件哈希、变换和固定状态；旧1000实体的体数继承经过哈希绑定的WP08冷读证据。",'',
'正面服务棱柱在合盖时被前维护盖遮挡，交叠15842.56960512mm³。仅在前盖已经移除这一条件下，其余已检查几何不挡该棱柱；真实工具、拆盖动作和羽流未验证。Ø8导向孔对Ø6束径是导向预留，不能认定已实现夹紧或应变释放。','',
'目前完整端到端电气回路为0，24项试制检查均未执行。真实设备针脚、保护器件、导线截面、端部余量、DM实际任务电流仍待绑定；没有通电、承压、制造或连续运动验证。WP08后肋局部、前轮A3200局部细化和电池原生HOLD不会因这次总装生成而自动获得集成/通过信用。','',
'## 设计与检查文件','',
'- '+link('线束路径图','docs/HARNESS_LAYOUT_S_WORLD.svg')+' · '+link('From–To表','ecad/From-To.csv')+' · '+link('DM供电/CAN分支表','ecad/DM_SELECTED_FROM_TO.csv'),
'- '+link('名义装配与局部试制步骤','docs/NOMINAL_ASSEMBLY_AND_PREFAB_ZH.md')+' · '+link('机械接口表','docs/MECHANICAL_INTERFACE_TABLE.csv'),
'- '+link('82实例增量BOM','results/DELTA_BOM_82.csv')+' · '+link('整机服务态BOM','results/ASSEMBLY_BOM_SERVICE.csv'),
'- '+link('关闭项与开放项','docs/CLOSURE_DELTA_AND_OPEN_ITEMS_ZH.md')+' · '+link('机器交付状态','results/DELIVERY_STATUS.json'),
'- '+link('原生独立绑定检查','results/INDEPENDENT_NATIVE_BINDING_CHECK.json')+' · '+link('几何检查','results/INTEGRATION_CHECK_V6.json')+' · '+link('原生材料回导','results/NATIVE_MATERIAL_CHECK_V2.json'),
'- '+link('执行限制与恢复记录','docs/EXECUTION_LIMITS_AND_RECOVERY_ZH.md'),'',
'## 模型预览','',
'![SolidWorks服务态实际整机视图](<'+(R/'viewer/WP09_SERVICE_NATIVE.png').as_posix()+'>)','',
'![共享舱实际CAD快照](<'+(R/'viewer/bay_iso_20260907T065738Z.png').as_posix()+'>)','',
'下一批实作优先绑定DM出货图、P60机械/电气接口、实际线材与保护器件，然后完成设备支撑、端接、工具路径与断电线束试制。实际压力推进选型和任务推力分配另需设备ICD与性能约束；本轮不由理想上界推导任务可行。','']
lines=[line.replace('材料回导比较','双向实体几何及体积回导比较') for line in lines]
(R/'README.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps(dict(status=status['status'],states=3,components_each=701,solids_each=1082,new_instances=82,new_native=21,frozen_inputs=len(frozen),unique_native_dependencies=len(dependencies)),ensure_ascii=False))
