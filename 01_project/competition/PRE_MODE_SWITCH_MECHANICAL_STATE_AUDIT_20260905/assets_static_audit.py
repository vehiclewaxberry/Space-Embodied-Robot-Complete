"""Read-only source audit; writes ONLY beside this script. Never imports CAD APIs."""
from pathlib import Path
import csv, hashlib, json, collections, zipfile, xml.etree.ElementTree as ET

ROOT = Path(r'F:\China Graduate Future Flight Vehicle Innovation Competition')
OUT = Path(__file__).resolve().parent
R2 = '20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/'
M7 = '20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/'
F3 = '20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/'
V5 = '20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE/'
F4 = '20_engineering/F4R1_INTERNAL_CONFIGURATION_COMPLETION_V1/'
M3 = '20_engineering/F3R2_MECHANICAL_DETAILED_DESIGN_V1/06_parameterized_parts/m3r/'
sources = set()
def p(rel):
    q = Path(rel)
    return q if q.is_absolute() else ROOT / q
def track(rel):
    q = p(rel).resolve(); sources.add(str(q)); return q
def sha(q):
    h=hashlib.sha256()
    with q.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest().upper()
def readj(rel): return json.loads(track(rel).read_text(encoding='utf-8-sig'))
def csvread(rel):
    with track(rel).open(encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))
def writej(name, obj): (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def writecsv(name,rows):
    if not rows:return
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

# Exact current disk bytes, compared with prior receipt pins where available.
files = []
def addfile(rel,role,expected=''):
    q=track(rel); exists=q.is_file(); actual=sha(q) if exists else ''
    files.append(dict(path=str(q),role=role,exists=exists,bytes=q.stat().st_size if exists else '',sha256=actual,expected_sha256=expected,pin_matches=(actual==expected.upper()) if expected and exists else 'NOT_BOUND'))
manifest=readj(R2+'01_BASELINE_MANIFEST.json')
for x in manifest['files']: addfile(R2+x['file'],'R2_MANIFEST_MEMBER',x['sha256'])

# Static FCStd ZIP/XML: counts and actual internal/external link records. No kernel load.
fcfiles=[R2+'03_MASTER_GEOMETRY.FCStd',M3+'M3R_STAGE_A_REVB_WORKING.FCStd',M3+'M3R_STAGE_B_REVB2_WORKING.FCStd',M3+'M3R_INTERFACE_ASSEMBLY_V2_WORKING.FCStd',M7+'ecr_solar_array_r2/SOLAR_ARRAY_R2_CANDIDATE_V1.FCStd',R2+'route_c/B601_ROUTE_C_GUIDED_DRESS_PACK_V9F.FCStd',F4+'70_c3_cad/CA_A_R1_INTERNAL_STRUCTURE_V2.FCStd','20_engineering/F3R2_V5R_FREECAD_OPERATIONAL_CLOSURE_20260820/03_fcstd/FC02B_FULL_SYSTEM_REPAIRED.FCStd']
fcsummary=[]; objects=[]; links=[]
for rel in fcfiles:
    q=track(rel)
    with zipfile.ZipFile(q) as z:
        r=ET.fromstring(z.read('Document.xml')); types={n.get('name'):n.get('type') for n in r.findall('./Objects/Object')}
        fcsummary.append(dict(path=str(q),sha256=sha(q),zip_crc_bad_entry=z.testzip(),zip_entries=len(z.namelist()),object_count=len(types),types=dict(collections.Counter(types.values())),static_only=True))
        for obj in r.findall('./ObjectData/Object'):
            values={}
            for prop in obj.findall('./Properties/Property'):
                if len(prop): values[prop.get('name')]={'tag':prop[0].tag,**prop[0].attrib}
            name=obj.get('name'); label=values.get('Label',{}).get('value',''); source=values.get('SourcePath',{}).get('value','')
            objects.append(dict(document=str(q),object_name=name,object_type=types.get(name),label=label,source_path=source,shape_file=values.get('Shape',{}).get('file','')))
            for el in obj.findall('.//XLink'):
                target=el.get('name',''); external=el.get('file',''); links.append(dict(document=str(q),instance=name,target_name=target,external_file=external,target_internal_exists=target in types if not external else 'EXTERNAL',source_path=source))
            if source.startswith('20_engineering/'):
                source=source.split('::')[0]; addfile(source,'FCSTD_PROVENANCE_STRING_NOT_EXTERNAL_DEPENDENCY')
writej('assets_fcstd_static_summary.json',fcsummary);writecsv('assets_fcstd_objects.csv',objects);writecsv('assets_fcstd_links.csv',links)

# F3R2 historical SW dependency copy inventory vs current disk.
deps=csvread(F3+'03_native_cad/F3R2_DEPENDENCY_INVENTORY.csv')
for row in deps:
    addfile(row['source'],'F3R1_HISTORICAL_DEPENDENCY',row['source_sha256'])
    addfile(row['destination'],'F3R2_HISTORICAL_DEPENDENCY',row['dest_sha256'])
comp=csvread(F3+'03_native_cad/F3R2_COMPONENT_INVENTORY.csv'); currentcomp=[]
cache={}
for row in comp:
    q=track(row['path'])
    if str(q) not in cache:cache[str(q)]=(q.is_file(),sha(q) if q.is_file() else '')
    exists,digest=cache[str(q)]
    currentcomp.append({**row,'path':str(q),'current_path_exists':exists,'current_sha256':digest,'scope':'HISTORICAL_NATIVE_REFERENCE_REPORT_NOT_CURRENT_OPEN'})
writecsv('assets_sw_reference_disk_audit.csv',currentcomp)

# V5 checkpoints: preserve narrowly scoped verdicts and recompute each CAD pin.
checkpoints=['V5_LOOP1A_CHECKPOINT_G07_PRIMARY_SUPPORT_V2.json','V5_LOOP1A_CHECKPOINT_G08_PRIMARY_SUPPORT_V2.json','V5_LOOP1A_CHECKPOINT_MID_BACKUP_SUPPORT_V2.json','V5_LOOP1D1_CHECKPOINT_ARM_HDRM_FUNCTIONAL_ENVELOPE.json','V5_LOOP1D_HDRM_CAMERA_HARNESS_RECEIPT.json']
checkpoint_summaries=[]
def walk(x):
    if isinstance(x,dict):
        if isinstance(x.get('path'),str) and x['path'].lower().endswith(('.sldasm','.sldprt','.fcstd','.step')): addfile(x['path'],'V5_CHECKPOINT_CAD',x.get('sha256',''))
        for v in x.values():walk(v)
    elif isinstance(x,list):
        for v in x:walk(v)
for name in checkpoints:
    d=readj(V5+'13_validation/'+name); walk(d)
    checkpoint_summaries.append({'path':str(p(V5+'13_validation/'+name)),'verdict':d.get('verdict'),'result_verdict':d.get('result',{}).get('verdict'),'target':d.get('target'),'scope':'HISTORICAL_SUBASSEMBLY_COLD_OPEN_NOT_CURRENT_FULL_ASSEMBLY'})
writej('assets_v5_checkpoint_summary.json',checkpoint_summaries)

# Primary provenance and selected geometry files, kept separate from root agent evidence.
extra=[
'PROJECT_MAP.md','01_project/current/CURRENT_RELEASE_POINTERS_V1.yaml',
R2+'_work/mode_a_native_design_r1/03_a3_4/A3_43_COMPONENT_TRUTH_TABLE.csv',
M3+'M3R_STAGE_A_REVB_WORKING.step',M3+'M3R_STAGE_B_REVB2_WORKING.step',M3+'M3R_INTERFACE_ASSEMBLY_V2_WORKING.step',M3+'M3R_INTERFACE_ASSEMBLY_V2_GEOMETRY_VALIDATION.json',
M7+'wp1_structure_cad/SUPPORT_AND_BRACKET_CANDIDATES_V1.yaml',M7+'wp1_structure_cad/DESIGN_FREEZE_ASSEMBLY_BUILD_REPORT_V1.json',M7+'wp5_mechanisms/HDRM_ENGINEERING_PACK_V1.yaml',M7+'wp12_secondary_structure_adjudication/SECONDARY_STRUCTURE_INTERFERENCE_RULING_V1.json',
M7+'ecr_solar_array_r2/SOLAR_ARRAY_R2_CANDIDATE_V1.step',M7+'ecr_solar_array_r2/SOLAR_R2_MECHANISM_ANALYTICAL_LEDGER_V1.yaml',M7+'ecr_solar_array_r2/SOLAR_ARRAY_R2_HDRM_LATCH_DESIGN_V1.yaml',
R2+'route_c/B601_ROUTE_C_BUILD_RECEIPT_V9F.json',R2+'route_c/B601_ROUTE_C_GUIDED_DRESS_PACK_V9F.step',R2+'route_c/B601_ROUTE_C_HARNESS_CENTERLINE_V9F.json',R2+'route_c/B601_ROUTE_C_CLAMP_AND_GUIDE_REGISTER_V9F.csv',R2+'route_c/ROUTE_C_MISSION_COVERAGE_GATE_V1.json',
R2+'_work/claude_takeover_closure_v1/03_m01/M01_OPERATIONAL_ASSET_MANIFEST_V1.json',R2+'_work/claude_takeover_closure_v1/CURRENT_TAKEOVER_AUTHORITY_INDEX_V1.json',
F3+'03_native_cad/F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.SLDASM',F3+'03_native_cad/F3R2_REFERENCE_AUDIT.json',F3+'03_native_cad/F3R2_PACK_AND_GO_PROOF.json',F3+'13_gate/F3R2_FINAL_GATE.json',F3+'07_hdrm/F3R2_ARM_HDRM_DEFINITION.json',
F3+'03_native_cad/M3_interface_authority/M3R_INTERFACE_AUTHORITY_GATE.json',
'20_engineering/F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806/03_native_cad/F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION_V3_CONFIGURED.SLDASM',
'20_engineering/F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806/03_native_cad/F3R1_TOP_INTEGRATION_REPORT.json',
'20_engineering/F3R2_V5R_FREECAD_OPERATIONAL_CLOSURE_20260820/06_validation/FC02_MILESTONE_REPORT.json',
'20_engineering/F3R2_V5R_FREECAD_OPERATIONAL_CLOSURE_20260820/06_validation/BREP_HEALTH_REPORT.json',
'20_engineering/F5R2_TERMINAL_CLOSURE_V1/00_frontier/CURRENT_FRONTIER_FABLE5_V1.json',
F4+'70_c3_cad/BUILD_RECEIPT_V2.json',F4+'70_c3_cad/GATE_C3_CHECK_V2.json',F4+'70_c3_cad/CA_A_R1_INTERNAL_STRUCTURE_V2.step',F4+'70_c3_cad/INTERFERENCE_REPORT_V2.json',F4+'50_c1_layout/EQUIPMENT_LIST_V1.yaml',F4+'50_c1_layout/GATE_C1_CHECK.json',F4+'50_c1_layout/LAYOUT_SCHEME_V1.md',
M7+'wp9_release_package/BOM_V3_DESIGN.csv',M7+'wp9_release_package/BOM_V3_DESIGN.meta.yaml',M7+'wp9_release_package/DRAWING_SET_INDEX_V1.csv',M7+'wp9_release_package/ASSEMBLY_PROCEDURE_V1.md',M7+'wp9_release_package/INSPECTION_PLAN_V1.csv',M7+'wp9_release_package/VERIFICATION_MATRIX_V1.csv',
M7+'wp4_fastener_design/M3R_FASTENER_DESIGN_V1.yaml',M7+'wp4_fastener_design/FASTENER_SCHEDULE_V1.csv',
'F:/SPACE_ROBOTICS_REFERENCE_LIBRARY/REFERENCE_LIBRARY_START_HERE.md','F:/SPACE_ROBOTICS_REFERENCE_LIBRARY/CAD_DONOR_REGISTER.csv']
for rel in extra: addfile(rel,'SELECTED_AUDIT_EVIDENCE')
for q in p(V5+'03_top_assembly').glob('*.SLDASM'): addfile(q,'V5_STAGING_TOP_NOT_AUTHORITY')
writecsv('assets_file_identity_audit.csv',files)
(OUT/'assets_sources.txt').write_text('\n'.join(sorted(sources))+'\n',encoding='utf-8')
writej('assets_audit_counts.json',{'source_paths':len(sources),'file_identity_rows':len(files),'manifest_mismatches':[x['path'] for x in files if x['role']=='R2_MANIFEST_MEMBER' and x['pin_matches'] is False], 'missing_files':[x['path'] for x in files if not x['exists']], 'sw_component_rows':len(currentcomp),'sw_unique_paths':len(cache),'sw_missing_unique_paths':[x for x,y in cache.items() if not y[0]],'fcstd_document_count':len(fcsummary),'cad_api_used':False,'source_mutation':False})
print(json.dumps(json.loads((OUT/'assets_audit_counts.json').read_text()),ensure_ascii=False,indent=2))

# Human-reviewed crosswalk: classification applies to the stated configuration,
# not to every historic branch that happens to share the component name.
matrix=[]
def row(cid,group,classification,design,integration,validation,configuration,asset,evidence,missing,action):
    matrix.append(dict(component_id=cid,group=group,asset_classification=classification,design_state=design,integration_state=integration,verification_state=validation,configuration_scope=configuration,source_asset_absolute=str(p(asset)),source_evidence_absolute=' | '.join(str(p(x)) for x in evidence),a3_missing_geometry=missing,next_required_evidence=action))
truth=R2+'_work/mode_a_native_design_r1/03_a3_4/A3_43_COMPONENT_TRUTH_TABLE.csv'
for cid,stage,filename in [('M3R_STAGE_A_RING','Stage A Rev-B','M3R_STAGE_A_REVB_WORKING'),('M3R_STAGE_B_DIFFUSION','Stage B Rev-B2','M3R_STAGE_B_REVB2_WORKING')]:
    row(cid,'A3_EIGHT','已存在且已接入当前装配',stage+' 单件 FCStd/STEP 均在；独立单件等价验证；非飞行实物','R2 主 FCStd 中 INST_M3R_INTERFACE_ASSEMBLY 为内部链接，2-solid compound；A3 未加载；当前完整装配 UNKNOWN','历史局部 PASS_WORKING_GEOMETRY_EQUIVALENT_TO_PINNED_REVB2；实配/紧固/公差 HOLD；逐级在主复合体内身份未在本轮内核核验','R2 默认展开态主几何；非 A3 收拢态',M3+filename+'.FCStd',[truth,R2+'02_PRODUCT_STRUCTURE.yaml',M3+'M3R_INTERFACE_ASSEMBLY_V2_GEOMETRY_VALIDATION.json'],True,'建立同一姿态下两级独立身份、安装变换与对偶面；不能重设计已有件代替绑定')
row('HDRM_ROOT','A3_EIGHT','已存在但未接入','V5 ARM_HDRM 功能候选含承载底座/锁闩滑块/硬止挡/传感器与连接器支架；root 专属身份未绑定','不在 R2 七个活动实例或 A3；generic ARM_HDRM 不能直接充当已选 root 装置','V5 子装配 cold/config/mate/reference PASS；interference_closure_claimed=false；实物释放/冲击/寿命 HOLD','V5 子系统候选，非当前完整收拢配置',V5+'02_native_subassemblies/ARM_HDRM_FUNCTIONAL_ENVELOPE.SLDASM',[truth,V5+'13_validation/V5_LOOP1D1_CHECKPOINT_ARM_HDRM_FUNCTIONAL_ENVELOPE.json',M7+'wp5_mechanisms/HDRM_ENGINEERING_PACK_V1.yaml'],True,'映射 root 装置身份、预紧与承载路径；选型/热真空/释放试验待证')
row('HDRM_DISTAL','A3_EIGHT','在已检索范围内未找到','未找到独立命名且已绑定 A3 distal 位置的释放器 B-rep；有 generic ARM_HDRM 候选与功能账本','A3 与 R2 未装入；不可把太阳翼 HDRM 或根部 generic 候选当第二套 distal 装置','独立末端约束/释放/承载验证 UNKNOWN','A3 专用 distal 槽位；检索范围为本工程 20_engineering 与参考库文件索引',V5+'02_native_subassemblies/ARM_HDRM_FUNCTIONAL_ENVELOPE.SLDASM',[truth,F3+'07_hdrm/F3R2_ARM_HDRM_DEFINITION.json',M7+'wp5_mechanisms/HDRM_ENGINEERING_PACK_V1.yaml'],True,'明确一套或多套 restraint 架构及部件身份后才能判设计缺口；不可由文件名匹配补齐')
for cid,g in [('STOW_SADDLE_A','G07'),('STOW_SADDLE_B','G08')]:
    row(cid,'A3_EIGHT','已存在但未接入',g+' V2 原生支承子装配、body/carrier/PTFE pad 已存在；另有 V4 STEP 与早期 cradle','R2 支承为 unresolved 槽位；A3 A/B 与 G07/G08 的逐件等价映射 UNKNOWN；V5 未被证明装入当前顶装','V5_NATIVE_SUBASSEMBLY_MATES_AND_COLD_REOPEN_PASS；旧 B51/G08 几何存在 2.254534 mm 穿入负结果；不可转授新姿态','V5 支承子件 / 历史 B51 收拢体系',V5+'02_native_subassemblies/'+g+'_PRIMARY_SUPPORT_V2.SLDASM',[truth,V5+'13_validation/V5_LOOP1A_CHECKPOINT_'+g+'_PRIMARY_SUPPORT_V2.json',M7+'wp12_secondary_structure_adjudication/SECONDARY_STRUCTURE_INTERFERENCE_RULING_V1.json'],True,'确认当前接触部位/对偶几何/垫片与弹簧；新姿态重新检查接触、间隙和承载')
row('HARNESS_TRUNK','A3_EIGHT','已存在但未接入','Route-C V9F FCStd 130 Part::Feature + 7 mesh + 1 group；中心线/导向件/夹持件/质量增量均有资产','R2 主 FCStd 与 A3 未加载；M01 是操作碰撞资产注册，非完整原生装配','V9F SOURCE_ONLY_DESIGN_CANDIDATE__NO_GATE_PASS__NO_RELEASE_CREDIT；早期 V1 mission gate FAIL_DOCUMENTED 不转授 V9F','V9F 候选自身参考姿态；非 A3 最新收拢态',R2+'route_c/B601_ROUTE_C_GUIDED_DRESS_PACK_V9F.FCStd',[truth,R2+'route_c/B601_ROUTE_C_BUILD_RECEIPT_V9F.json',R2+'route_c/ROUTE_C_MISSION_COVERAGE_GATE_V1.json'],True,'选定版本并绑定同一收拢/展开运动、弯曲半径/扭矩/固定点/接口与碰撞')
row('CONNECTOR_SET','A3_EIGHT','只有占位几何','Route-C V9F 有 CN-BUS/CN-BASE 安装板和 CN-WR-D1/P1 Micro-D 风格候选块；V5 有 connector mount','A3 未建模，R2 活动实例无 connector；实际供应商型号和插拔空间未绑定','候选建模可证；实际插接/锁紧/防呆/应力释放/维护空间 UNKNOWN','Route-C/V5 几何候选',R2+'route_c/B601_ROUTE_C_GUIDED_DRESS_PACK_V9F.FCStd',[truth,R2+'route_c/B601_ROUTE_C_BUILD_RECEIPT_V9F.json',V5+'13_validation/V5_LOOP1D_HDRM_CAMERA_HARNESS_RECEIPT.json'],True,'不能说完全没画过；需选择并绑定实际连接器或明示的工程等效包络')
row('BUS_PRIMARY_STRUCTURE_R2','SYSTEM','只有占位几何','R2 6 解析实体复合母线包络，包含 legacy flange/nozzle/antenna；无真实内部舱和面板','已接入 R2 默认主装配；不是 V2_2 原生框梁制造结构','340.5 mm 中性母线 vs 366.0 mm 原生结构冲突；12U 尺寸与内部结构 HOLD','R2 主装配',R2+'03_MASTER_GEOMETRY.FCStd',[R2+'02_PRODUCT_STRUCTURE.yaml'],False,'先选择一致母线长度/坐标/面板与安装结构，不能继承包络块质量为实物')
row('BUS_NATIVE_STRUCTURE_V2_2','SYSTEM','已存在但身份/版本不符','框梁/端框/设备板/主结构原生子件存在，F3R2 inventory 可定位','历史 SW 体系有实例；R2 neutral geometry 未使用这些原生实体','当前路径存在；若干子装配哈希不同于早期 copy receipt；当前配置健康 UNKNOWN','F3R2 历史 SW 各配置',F3+'03_native_cad/SPACECRAFT_V2_2_NATIVE_COPY/01_Primary_Structure/01_Primary_Structure_V2_2.SLDASM',[F3+'03_native_cad/F3R2_COMPONENT_INVENTORY.csv',F3+'03_native_cad/F3R2_DEPENDENCY_INVENTORY.csv',R2+'02_PRODUCT_STRUCTURE.yaml'],False,'逐级对齐中性/原生身份与真实承载链，重新绑定适用验证')
row('BUS_INTERNAL_F4R1','SYSTEM','已存在但未接入','CA-A-R1 V2 32 Part::Feature：三设备板、肋、机架导轨/端板、臂背板/角撑、翼根支架、适配块、电池板、飞轮支架','独立 FCStd/STEP；冻结主 STEP 未改；40 设备只是解析用于布局，不是 40 真实设备原生装配','C3 PASS_WITH_DECLARED_OPEN_ITEM；结构 1244.9 g；非注册干涉阈值 >1000 mm3，低体积冲突可能为 CONTACT_NOTE；收拢/墙穿支架路径等 deferred','F4R1 展开态/冻结 340.5 mm 母线坐标',F4+'70_c3_cad/CA_A_R1_INTERNAL_STRUCTURE_V2.FCStd',[F4+'70_c3_cad/BUILD_RECEIPT_V2.json',F4+'70_c3_cad/GATE_C3_CHECK_V2.json',F4+'70_c3_cad/INTERFERENCE_REPORT_V2.json'],False,'与真实臂/翼/线束统一装配和零件身份；C3 零 violation 不等于零接触或制造合格')
row('AVIONICS_EQUIPMENT','SYSTEM','只有文档或分析账本','F4R1 EQUIPMENT_LIST 多文档 YAML；含 FRZ 冻结参考和 EQ 候选设备，质量/包络/安装面/电力/来源','有三舱布置和设备盒比较，未证明原型设备、连接器和全部安装孔装入总装','C1/C3 设计研究局部检查；power UNKNOWN 等字段保留；不能视为采购 BOM','F4R1 50_c1_layout',F4+'50_c1_layout/EQUIPMENT_LIST_V1.yaml',[F4+'50_c1_layout/GATE_C1_CHECK.json',F4+'50_c1_layout/LAYOUT_SCHEME_V1.md'],False,'确认航电型号/实际包络/热接口/插拔空间/紧固件与维护通道')
row('SOLAR_R2','SYSTEM','已存在但身份/版本不符','R2 候选独立 FCStd 23 Part::Feature；机构/锁闩/展开力矩账本存在','11_SOLAR_R2_MECHANISM 锁定候选；主 FCStd 实际仍是 v0 两平板代理，未证明装入 R2 候选','候选冻结和分析并不证明当前系统根部/收拢/展开路径安全','独立 Solar R2 候选 vs R2 主几何差异',M7+'ecr_solar_array_r2/SOLAR_ARRAY_R2_CANDIDATE_V1.FCStd',[R2+'11_SOLAR_R2_MECHANISM.yaml',R2+'02_PRODUCT_STRUCTURE.yaml'],False,'绑定对应版本两翼、铰链、HDRM、锁闩/止挡及展开路径')
row('SOLAR_HARNESS','SYSTEM','只有文档或分析账本','H-RUN-02/03 逻辑路由及太阳翼相关设计账本存在','无当前 R2 全翼展开线束几何与绑定证明','连续展开缆线/根部转动/连接器与失效态验证 UNKNOWN','R2 产品树与早期路由',M7+'wp1_structure_cad/HARNESS_ROUTING_V1.yaml',[R2+'02_PRODUCT_STRUCTURE.yaml',R2+'11_SOLAR_R2_MECHANISM.yaml'],False,'翼根电缆服务环/插头/包络与铰链统一建模后验证')
row('B601_ACCEPTED_ARM','SYSTEM','已存在但身份/版本不符','accepted URDF + 10 link meshes 是 A3 来源；6R+1F+2P；臂夹爪质量独立账本','A3 加载 fullarm 10 links；R2 master 使用 FRAME_AXIS_WITNESS，历史 B51 native 与 accepted meshes 版本不同','A3 子模型范围可复用；不能等同完整总装碰撞/接触/发射收拢验证','A3 accepted URDF vs R2 master witness',R2+'05_ACCEPTED_B601_URDF_REF.yaml',[truth,R2+'02_PRODUCT_STRUCTURE.yaml'],False,'统一 arm 身份、坐标变换、装配消费版本和适用质量/碰撞模型')
row('GRIPPER_R1','SYSTEM','已存在但身份/版本不符','R2 主装配有 R1 palm；accepted URDF 有两指，ODR60 有操作代理候选','主装配 SLOT_GRIPPER_R1_FINGERS_UNRESOLVED；后续 M01 操作几何不等于主 CAD 更新','有限接触合同/局部代理证据不能证明当前整星抓持和收拢','R2 master vs ODR60/M01 vs A3',R2+'03_MASTER_GEOMETRY.FCStd',[R2+'10_GRIPPER_INTERFACE.yaml',R2+'02_PRODUCT_STRUCTURE.yaml',R2+'_work/claude_takeover_closure_v1/03_m01/M01_OPERATIONAL_ASSET_MANIFEST_V1.json'],False,'选择掌/指/滑轨真实几何和接口，核查同一构型 2P 行程与接触')
row('MID_BACKUP_SUPPORT','SYSTEM','已存在但未接入','V5 MID_BACKUP_SUPPORT_V2 原生支承子装配存在','R2 未接入；非 A3 八项的一一指定槽位','历史子装配 mate/cold PASS；不能继承新姿态支承/载荷','V5 子系统候选',V5+'02_native_subassemblies/MID_BACKUP_SUPPORT_V2.SLDASM',[V5+'13_validation/V5_LOOP1A_CHECKPOINT_MID_BACKUP_SUPPORT_V2.json',M7+'wp1_structure_cad/SUPPORT_AND_BRACKET_CANDIDATES_V1.yaml'],False,'定义是否需中间支撑、间隙、故障承载和当前 arm 对偶面')
row('LOAD_BRIDGE','PRODUCT_CHAIN','已存在且已接入当前装配','M6 load bridge 中性 B-rep 被 R2 INST_SPACECRAFT_LOAD_BRIDGE 嵌入','当前 R2 7 实例之一；不要混同 V2_2 的 Load_Bridge_Left/Right','物理实配/锚固孔/预紧/结构连续性仍 HOLD','R2 默认主装配',R2+'03_MASTER_GEOMETRY.FCStd',[R2+'02_PRODUCT_STRUCTURE.yaml',M7+'wp9_release_package/DRAWING_SET_INDEX_V1.csv'],False,'臂载荷→两级→桥接件→母线锚点的紧固/预紧/接触/承载链')
row('FASTENERS_TOLERANCES','PRODUCT_CHAIN','只有文档或分析账本','M3R fastener design/schedule 与 tolerance 文件存在','R2 M3R.FASTENER_SET/LOCATOR_SET DEFINED_NOT_MODELLED','实配计量、公差、等级/预紧与滑移/强度验证未完成','M7/R2',M7+'wp4_fastener_design/M3R_FASTENER_DESIGN_V1.yaml',[M7+'wp4_fastener_design/FASTENER_SCHEDULE_V1.csv',R2+'09_M3R_ICD.yaml',R2+'02_PRODUCT_STRUCTURE.yaml'],False,'紧固件/销/螺纹啮合与实际对偶面、检验尺寸和载荷绑定')
row('DRAWINGS_BOM_MANUFACTURING','PRODUCT_CHAIN','只有文档或分析账本','M7 8 项图纸/表索引与 BOM V3、装配程序、检验计划存在','制造链为候选与计划；非同一实际整星配置完备图纸包','8 项 manufacturing_use=PROHIBITED；BOM release_effect=NONE_NOT_A_PROCUREMENT_BOM；无试制/验收完成证据','M7 工程候选包',M7+'wp9_release_package/DRAWING_SET_INDEX_V1.csv',[M7+'wp9_release_package/BOM_V3_DESIGN.meta.yaml',M7+'wp9_release_package/ASSEMBLY_PROCEDURE_V1.md',M7+'wp9_release_package/INSPECTION_PLAN_V1.csv'],False,'按选定配置建立图纸/材料/公差/制造/装配可达/检验记录闭环')
row('FULL_CURRENT_ASSEMBLY','SYSTEM','已存在但身份/版本不符','多代原生总装、neutral master、结构/线束/翼候选存在','没有证明同一总装同时消费 accepted arm、两级 M3R、真实 restraint/support、Solar R2、Route-C、航电和母线','UNKNOWN：没有当前完整配置 native cold-open + references + interference + motion + restraint 的统一证据','本次只读审计，不运行 CAD/生产检查',R2+'03_MASTER_GEOMETRY.FCStd',[R2+'01_BASELINE_MANIFEST.json',R2+'02_PRODUCT_STRUCTURE.yaml',R2+'08_CONFIGURATION_LIBRARY.yaml'],False,'先建立配置消费/产品身份绑定，再申请适用的集成验证；不自动换线')
writecsv('02_ASSET_INTEGRATION_VERIFICATION.csv',matrix)
for x in matrix:
    track(x['source_asset_absolute'])
    for q in x['source_evidence_absolute'].split(' | '):track(q)
(OUT/'assets_sources.txt').write_text('\n'.join(sorted(sources))+'\n',encoding='utf-8')
