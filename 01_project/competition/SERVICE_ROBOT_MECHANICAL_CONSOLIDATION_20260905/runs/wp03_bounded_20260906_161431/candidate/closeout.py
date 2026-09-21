"""Freeze a scoped mechanical round from actual evidence, without editing legacy gates."""
from pathlib import Path
import json,hashlib,datetime,csv
from candidate_context import HERE,RUN,verify_upstream
from provenance_binding import verify_hashes,sha,validate_receipt_source
from export_parts_and_bom import validate_handoff_binding
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,d):Path(p).write_text(json.dumps(d,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
def link(label,p):return '['+label+'](<'+str(Path(p).resolve()).replace('\\','/')+'>)'
def main():
    upstream=verify_upstream();verify_hashes(load(RUN/'inputs/ARM_REUSE_INPUT_EXTENSION.json')['source_sha256'])
    mech=load(RUN/'review/R01_REVIEW_CANDIDATE2.json');three=load(RUN/'review/R01_THREE_STATE_CONTEXT_RECHECK.json')
    protocol=load(RUN/'review/PROVENANCE_PROTOCOL_CONTROLS.json');composition=load(RUN/'review/COMPOSITION_CONTROLS.json');ledger=load(RUN/'review/ACTUAL_LEDGER_RECHECK.json')
    assert mech['status']=='SCOPED_NOMINAL_GEOMETRY_ASSEMBLY_PASS_PARENT_OPEN'
    assert three['status']=='THREE_STATE_R01_NONARM_RELATED_STATIC_COMPOSITE_PASS'
    assert protocol['all_passed'] and composition['all_passed'] and ledger['all_passed']
    cp=HERE/'results/r01_connections.json';contract=load(cp)
    assert sha(cp)==mech['contract_sha256'] and sha(contract['step_path'])==contract['step_sha256']
    assert sha(RUN/'review/review_r01.py')==mech['reviewer_source_sha256']
    verify_hashes({row['step_path']:row['step_sha256'] for row in contract['instances'] if row.get('step_path')})
    for entry in mech['step_import_metadata']:
        if isinstance(entry,dict) and entry.get('path') and entry.get('sha256'):assert sha(entry['path'])==entry['sha256']
    h=load(HERE/'results/DYNAMICS_HANDOFF.json');verify_hashes(h['input_sha256'])
    for state in ['parking','released','service']:validate_receipt_source(load(HERE/'results'/f'{state}_instances.json'),HERE)
    receipt=load(HERE/'results/service_instances.json');validate_handoff_binding(receipt,h,HERE/'results/service_instances.json',HERE)
    b=load(HERE/'results/BOM_BINDING.json');assert b['BOM_sha256']==sha(HERE/'BOM.csv')
    assert b['handoff_sha256']==sha(HERE/'results/DYNAMICS_HANDOFF.json')
    assert load(HERE/'results/PARAMETER_PROPAGATION.json')['status']=='PASS'
    surface=load(HERE/'results/POSE_SCREEN.json')
    for pose in surface['poses']:
        verify_hashes(pose['contract']['input_sha256'])
        assert pose['classification']['status']=='DECLARED_NONADJACENT_BODY_PAIR_SURFACES_DISJOINT_ONLY'
    drawing=load(HERE/'results/R01_DRAWING_PROVENANCE.json');assert drawing['final_step_sha256']==sha(HERE/'r01_local.step')
    static=load(HERE/'results/DRAWING_STATIC_REVIEW.json');assert static['source_sha256']==sha(HERE/'r01_interfaces.dxf')
    write(RUN/'results/SOURCE_PROTECTION_FINAL.json',dict(status='PASS',original_files_checked=len(upstream),original_source_changes=[],input_sha256=upstream,arm_input_extension_unchanged=True,shared_loop0_ledgers_changed=False,historical_gates_changed=False,current_pointer_promoted=False))
    mass=h['states'][0]['groups']['ONBOARD_CANDIDATE']['known_mass_kg']
    result=dict(schema='WP03_BOUNDED_MECHANICAL_ROUND_V1',run_id=RUN.name,closed_local=datetime.datetime.now().astimezone().isoformat(),status='R01_SCOPED_DIGITAL_CONNECTION_CLOSURE_AND_R17_FINAL_BINDING_COMPLETED',geometry_candidate='R01_CANDIDATE_2',modified_existing_parts=12,new_nominal_fastener_sets=32,new_nominal_hardware_instances=128,physical_assembly_completed=False,manufacturing_release=False,flight_qualification=False,R01_parent_closed=False,R07_closed=False,full_assembly_collision_pass=None,monolithic_complete_step_generated=False,states=['parking','released','service'],instances_per_composite_state=489,known_mass_atoms=194,unknown_mass_instances=295,allocated_mass_kg=mass,geometry_evidence=dict(valid_instances=479,paired_member_holes=64,bearing_surfaces=64,thermal_and_existing_screw_reliefs=11,service_tool_and_hardware_paths=192,service_affected_static_pairs=52010,service_static_findings=0,three_state_affected_nonarm_static='PASS',continuous_motion='NOT_VERIFIED'),software_evidence=dict(protocol_controls=110,composition_controls=19,actual_ledger_recheck=True,actual_surface_worker_states=3,declared_nonadjacent_arm_body_pairs_per_state=35,finger_pair='UNKNOWN',volume_containment='UNKNOWN'),evidence_paths=[str(RUN/'review'/n) for n in ['R01_REVIEW_CANDIDATE2.json','R01_THREE_STATE_CONTEXT_RECHECK.json','PROVENANCE_PROTOCOL_CONTROLS.json','COMPOSITION_CONTROLS.json','ACTUAL_LEDGER_RECHECK.json']],next_bounded_design='R07A_ROOT_BRIDGE_CROSSBEAM_TO_MAIN_LONGERONS')
    write(RUN/'results/ROUND_RESULT.json',result)
    next_work=dict(ticket='R07A_ROOT_BRIDGE_CROSSBEAM_TO_MAIN_LONGERONS',status='NEXT_BOUNDED_DESIGN_READY_NOT_EXECUTED_THIS_ROUND',objective='建立臂根桥架/横梁向主纵梁传力的真实机械连接',first_actions=['从本轮三态组装索引读取臂根、桥架、横梁和四主纵梁的接口与净空','建立每个连接边的双侧零件ID、基准、定位方式、紧固方向与可维护顺序','参数化连接件和对偶孔；保留材料、紧固件等级及预紧字段待来源落实','核对装入/工具通道、相关三态静态干涉和质量归属；加入错孔/漏孔/垫圈撞入负控','取得载荷后完成螺栓群、孔壁承压、净截面/撕裂、连接刚度及局部板弯曲计算'],required_physical_inputs=dict(material_and_temper=None,fastener_grade_and_thread_standard=None,preload_and_locking=None,root_force_moment_envelope_S=None,handling_and_ground_support_cases=None,as_built_B601_root_interface=None),acceptance=['每条连接边存在双侧真实承压/定位几何及完整对偶孔','紧固件装入和所选工具路径可验证','相关静态和参数扰动检查通过，质量只归属一次','有载荷/材料来源的连接校核；缺数据的力学结论保持UNKNOWN'],parallel_R01_followups=['选择32套螺钉/垫圈/螺母，确认有效啮合与防松','核定新增孔后的边距、净截面、孔壁承压和公差','落实真实导热件截面、绝缘/护口及热接口','验证后装适配板、设备、侧盖本身的安装路径','制定并执行局部实物试装与测量记录'])
    write(RUN/'results/NEXT_R07A_WORK_ORDER.json',next_work)
    write(RUN/'results/ISSUE_DELTA.json',dict(scope='This run evidence delta; historical loop0 issue records preserved',updates=[dict(id='R01',digital_subscope='CLOSED_NOMINAL_GEOMETRY_AND_FASTENER_INSTALLATION_PHASE',parent_engineering_issue_closed=False,evidence='review/R01_REVIEW_CANDIDATE2.json'),dict(id='R17',subscope='FINAL_GEOMETRY_HANDOFF_BOM_BINDING_VERIFIED',scope_limit='This candidate pipeline and records'),dict(id='R07A',status='NEXT_DETAILED_DESIGN',executed=False)]))
    image=next((HERE/'results').glob('r01_local_opposite_*.png'))
    urls=load(RUN/'results/VIEWER_LINKS.json') if (RUN/'results/VIEWER_LINKS.json').exists() else {}
    report=f'''# WP03 第一轮机械细化交付记录

本轮已完成 **R01 甲板—角材—剪力板连接的有界数字闭环**，并完成 **R17 最终几何→动力学参数交接→BOM 的同源绑定**。可进入下一组 R07A 臂根桥架／横梁—主纵梁连接细化。材料、螺纹/预紧、结构强度及实物试装仍是 R01 父问题的后续验收项。

执行目录：`{RUN.name}`。所有新设计和证据均在本目录；原 WP01/WP02/WP03、历史科学裁决及 loop0 账本作为来源保留。

## 实际改动

| 对象 | 本轮结果 |
|---|---|
| 两层甲板 | 保留 344×196.3×3 mm 外形和柱避口；每层8个 Ø3.4 完整紧固孔，X=−150/−50/50/140 mm、Y=±92.65 mm |
| 八段角材 | 补齐与甲板及剪力板的对偶孔，保留原外形与分段位置 |
| 两侧剪力板 | 补齐角材接口孔，X=−130/−70/60/130 mm，Z=−94.15/−18.5 mm |
| 紧固件 | 16组甲板—角材＋16组角材—剪力板，共32套；每套螺钉、两垫圈、螺母，合计128个名义实例 |
| 本轮揭示并修正的干涉 | 下甲板为 Ø10 导热代理增加 Ø12 贯通避让；下角材为10个既有螺钉末端增加 Ø3.4 避让 |

紧固件是未选型的名义无螺纹几何。甲板连接名义夹持厚度6 mm、螺钉头下长12 mm；剪力板连接为5 mm、10 mm。垫圈外径6 mm、内径3.4 mm、厚0.5 mm。工具轴/空心套筒是声明的检查包络，不能代替实际工具选型及传扭校核。

新热件孔提供名义径向1 mm避让；既有 Ø3 螺钉与 Ø3.4 避让孔的名义径向间隙为0.2 mm。它们均未包含制造、装配和热变形公差。

## 证据与边界

| 实际检查 | 结果 |
|---|---|
| STEP 读回实体有效性 | 479/479；包含明确标注的功能包络，几何有效不代表硬件落实 |
| 连接孔、承压区域 | 64个配对成员孔、64处垫圈承压面全部通过 |
| 孔清单、柱避口及新增避让 | 精确孔轴/孔径集合、8处柱避让、11处新增避让全部通过 |
| 服务态相关静态材料干涉 | 52,010个相关配对，273个进入窄相；最终0处正体积相交 |
| 紧固件及工具通道 | 服务态指定装配阶段192条路径通过；128个标准件装入＋64个工具包络 |
| 另外两态相关静态 | R01的140个实例三态逐值相同；parking新增8,540对、released新增3,780对均严格AABB分离，最小可证轴向间隙13.25 mm |
| 参数化传播 | 将一处X孔位140→138 mm，在内存重新生成甲板与角材，两侧同步变化；最终参数文件未改动 |
| 独立负控/软件 | 110项协议检查、19项组合来源检查通过；保留第一次几何失败及软件缺口回执 |

三态静态结果限于 R01 相关非臂几何。192条工具/装入路径的证据只属于服务态指定装配阶段。后装的设备、适配板、热垫和侧盖自身安装路径，仍需单独验证。

实际机械臂表面 worker 已运行三态；每态35组声明的非相邻臂体表面未检出相交。夹指对、相邻关节、体积包含、臂—星体全范围和连续路径仍不能据此判 PASS。

## 装配次序与下一阶段

1. 对甲板、分段角材、剪力板进行基准定位及临时支撑；临时支撑工装另行落实。
2. 在设备、适配板、热垫和侧盖安装之前，逐连接装入两侧垫圈、螺钉、螺母，并按对应工具包络检查可达性。
3. 选定真实紧固件和工艺后确定预紧、防松与检查方法；目前不填写未经来源确认的扭矩值。
4. 验证后装件自身路径，再进行局部实物试装及孔位/间隙测量。

下一组为 **R07A 臂根桥架／横梁—主纵梁连接**：建立完整接口和双侧对偶孔、确定定位/紧固方向、验证装入与工具空间；取得臂根六分量载荷、材料及紧固件数据后，完成螺栓群、孔壁承压、净截面/撕裂和局部刚度校核。任务输入及验收项已写入 {link('下一轮工作单',RUN/'results/NEXT_R07A_WORK_ORDER.json')}。

## 数字装配和质量交接

每态489实例由 **479个本轮重建的非臂实例＋10个哈希锁定的未改动臂实例** 组成。三份新 STEP 只含非臂几何；完整组合包通过装配索引引用原臂 BRep 与其位姿，`monolithic_complete_step_generated=false`。旧臂几何、姿态和原始属性逐项保留，未继承旧碰撞结论。

已分配质量小计 **{mass:.12f} kg**，194个质量原子；295实例质量仍未知，其中含本轮新增128个紧固件实例。这个小计包含 CAD 估算、设备预算和 URDF 数字质量，不能作为整星实测质量。三态质量一致，COM 和惯量按各自位姿重新计算。独立复算质量差为0，COM最大差约1.39e−17 m，惯量最大差约6.66e−16 kg·m²；这些是数值一致性结果。

{link('BOM',HERE/'BOM.csv')} · {link('接口清单',HERE/'INTERFACES.csv')} · {link('动力学参数交接',HERE/'results/DYNAMICS_HANDOFF.json')} · {link('独立账本复算',RUN/'review/ACTUAL_LEDGER_RECHECK.json')}

## 交付入口

- {link('R01局部连接STEP',HERE/'r01_local.step')}（12个改件＋128个名义紧固件）
- {link('接口参考图DXF',HERE/'r01_interfaces.dxf')}（11视图、22个尺寸实体；制造公差/材料/工艺未放行）
- {link('停放态星体STEP',HERE/'servicer_structure_parking.step')} · {link('释放态星体STEP',HERE/'servicer_structure_released.step')} · {link('服务态星体STEP',HERE/'servicer_structure_service.step')}
- {link('服务态完整组合索引',HERE/'results/service_COMPOSITE_ASSEMBLY_INDEX.json')} · {link('参数文件',HERE/'design_parameters.json')}
- {link('独立机械复核',RUN/'review/R01_REVIEW_CANDIDATE2.json')} · {link('三态静态补充复核',RUN/'review/R01_THREE_STATE_CONTEXT_RECHECK.json')} · {link('本轮机器记录',RUN/'results/ROUND_RESULT.json')}

{('[交互查看R01]('+urls['r01']+') · [交互查看服务态星体]('+urls['service']+')') if urls else '交互查看链接另见 VIEWER_LINKS.json。'}

![R01背侧与甲板避让孔](<{str(image).replace(chr(92),'/')}>)

## 执行记录说明

本轮使用1名生产构建者与2名独立审阅者。首版几何暴露11处真实静态干涉、16条被后装件阻挡的路径及64项垫圈装入覆盖缺失；第二版逐项修复并复核。首次完整STEP复核还暴露了检查器复制父装配树的内存问题，随后采用脱离装配树的单实体定位，并增加操作系统级1,400 MiB子进程内存硬上限。原失败和恢复说明保留在 logs/ 与 review/。

CAD的9张快照已检查。安装的DXF构建器与快照器预览格式不一致，DXF交换文件验证通过；4张静态图直接由该DXF渲染并核对，未改变图纸几何。原WP来源哈希复核见 {link('来源保护记录',RUN/'results/SOURCE_PROTECTION_FINAL.json')}。
'''
    (RUN/'ROUND_RESULT_ZH.md').write_text(report,encoding='utf-8')
    artifacts=[]
    for p in sorted(RUN.rglob('*')):
        if not p.is_file() or '__cadgen__' in p.parts or '__pycache__' in p.parts or p.name=='FINAL_ARTIFACT_MANIFEST.json' or (p.name.startswith('viewer_font_compat.') and p.suffix=='.log'):continue
        artifacts.append(dict(path=str(p.relative_to(RUN)).replace('\\','/'),bytes=p.stat().st_size,sha256=sha(p)))
    write(RUN/'results/FINAL_ARTIFACT_MANIFEST.json',dict(schema='BOUNDED_RUN_FILE_HASHES_V1',scope='This run only; renderer caches/bytecode/live viewer logs excluded; not a project release gate',artifacts=artifacts))
    print(json.dumps(dict(status=result['status'],report=str(RUN/'ROUND_RESULT_ZH.md'),files=len(artifacts))))
if __name__=='__main__':main()
