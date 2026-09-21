from pathlib import Path
import json,hashlib,datetime,urllib.parse,re
R=Path(__file__).resolve().parents[1]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
names=['BASELINE_ACTUAL_STEP','C01_GEOMETRY','C01_PATH_FAILURE','PATH_AND_STATIC_CHECKS','PARAMETER_PROOF','BEARING_CONTACTS','NATIVE_EXECUTION_V2','NATIVE_ROUNDTRIP_CHECK','SCOPED_SOURCE_INTEGRITY','C01_EVIDENCE_RECOVERY']
checks={n:read(R/'results'/(n+'.json')) for n in names}
assert checks['BASELINE_ACTUAL_STEP']['counts']=={'PASS':30,'FAIL':4}
assert checks['C01_PATH_FAILURE']['counts']=={'PASS':3488,'FAIL':4}
for n in names:
    if n not in ['BASELINE_ACTUAL_STEP','C01_PATH_FAILURE']:assert checks[n]['status'].startswith('PASS'),(n,checks[n]['status'])
assert checks['PATH_AND_STATIC_CHECKS']['counts']=={'PASS':3780}
base='http://127.0.0.1:3245/'+urllib.parse.quote(R.as_posix(),safe='/:')
viewer=base+'?file=candidate/wp06_side_joint.step.py'
result={
 'schema':'WP06_LOCAL_MECHANICAL_DELIVERY_V1','generated_local':datetime.datetime.now().astimezone().isoformat(),
 'status':'LOCAL_NOMINAL_GEOMETRY_AND_CONDITIONAL_FASTENER_PATHS_VERIFIED__PHYSICAL_CLOSURE_OPEN',
 'user_request_scope':'Continue local mechanical design; attachment used as recommended work input, not an independent authorization or executed evidence',
 'design_candidate':'C01_GEOMETRY','adopted_procedure':'C02_TWO_COMPLETE_DECK_JOINTS_INSTALLED_AFTER_SIDE_JOINTS',
 'source_parent':'WP04 parameterized design and WP05 canonical per-instance STEP',
 'modified_structural_instances':8,'replaced_bare_screw_instances':4,'new_catalogue_fastener_instances':16,
 'delivered_native_parts':53,'native_assembly_instances':53,'native_assembly_solids':53,'unchanged_context_instances':29,
 'native_feature_representation':'IMPORTED_BREP_PARTS_FIXED_IDENTITY_ASSEMBLY; editable parameters reside in Python/JSON source, not a reconstructed native feature/mate tree',
 'measured_screw_pillar_clearance_mm':[x['minimum_distance_mm'] for x in checks['C01_GEOMETRY']['results'] if x['id'].startswith('screw_pillar')],
 'measured_cross_screw_clearance_mm':[x['minimum_distance_mm'] for x in checks['C01_GEOMETRY']['results'] if x['id'].startswith('cross_screws')],
 'nominal_inner_tool_deck_lower_bound_mm':.65,'nominal_inner_tool_U_slot_clearance_mm':.2,
 'nominal_nut_band_mm':2.4,'nominal_tip_protrusion_mm':.6,'physical_thread_engagement':'UNKNOWN',
 'verified_scope':['Four nominal relocated holes and fastener stacks','Actual planar bearing contact area for 20 pairs','Three-state local static hardware neighbourhood','Continuous conservative axial fastener/tool envelopes for C02 with two complete R01 joints installed afterwards','8 old-source material matches,24 parameter perturbations,24 restorations','53 native cold-reopen dependencies/body/placement checks and actual native STEP material comparisons'],
 'path_method':'Actual STEP AABB separation bounds plus OCC narrow-phase distance/Common; 3780 scoped checks, not 3780 independent experimental validations',
 'preconditions':['Decks,angles,webs,clips already positioned in frozen S-frame','Other deck fasteners remain installed','Support condition given; ground assembly fixture geometry and capacity are not modelled'],
 'open_items':[
 {'id':'R07-SIDE-PHYSICAL-THREAD','state':'OPEN','need':'Purchased fastener/thread runout, grade, full engagement, locking and preload specification'},
 {'id':'R01-SIDE-THIN-EDGE','state':'OPEN','need':'1.3 mm angle end ligament and 1.05 mm hole ligament: actual material/load/tolerance strength assessment'},
 {'id':'R07-SIDE-TOOLS-FIXTURE','state':'OPEN','need':'Actual tool and fixture geometry, support capacity and structure-body installation path'},
 {'id':'GLOBAL-LEGACY-HOLDS','state':'UNCHANGED','need':'Prior B601 native hold items, harness/mechanism/continuous motion and manufacturing gates remain as recorded'}],
 'history_note':'C01 failed receipt and checker preserved. C02 overwrote 24 sweep file timestamps; all 24 historical files were transparently recovered into c01_sweep_archive only after matching original full-file SHA256; see C01_EVIDENCE_RECOVERY.json.',
 'native_recovery_note':'First LoadFile4 return-value parser failed; imported unsaved document preserved to native/recovery before retry. Failure and recovery receipts retained.',
 'evidence':{n:{'path':str(R/'results'/(n+'.json')),'sha256':sha(R/'results'/(n+'.json')),'status':checks[n]['status']} for n in names},
 'native_assembly':str(R/'native/WP06_SIDE_JOINT_C02.SLDASM'),'source_entry':str(R/'candidate/wp06_side_joint.step.py'),'viewer_url':viewer,
 'physical_assembly_completed':False,'structural_strength_verified':False,'manufacturing_release':False,'changes_existing_engineering_gates':False,
 'next_single_work_package':'For these same four joints, bind actual tools/fixture and purchased M3 tolerances/preload inputs, then verify physical assembly readiness.'}
(R/'results/WP06_RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
report=f'''# WP06 四处侧连接机械整改交付

已完成四处旧侧连接的实体整改与局部数字验证，可进入该局部的样机试装准备。交付为 **53 个 SolidWorks 零件＋1 个局部装配**，其中八个结构件改动、十六件新紧固件、二十九件相邻结构。整星与 B601 主装配保持原版本；本次局部视图不代表整星全部设计完成。

四个侧孔由 X154 移到 X146，下孔轴由 Z−94 调至−93.5，上孔保持 Z94；夹块、柱梁原位置保留。四根裸杆替换为 ISO4762 M3×12 螺钉、DIN125 M3 双垫圈和 ISO4032 M3 螺母。下角材增加向顶边开放的 U 形工具槽，保留原剪力板承压面。实际螺钉—立柱距离由 **0 提高到5.5 mm**，横竖螺钉间距为1.0 mm；名义夹持厚度9 mm、穿出0.6 mm，完整牙啮合仍待实物规格确认。

首轮发现下层垫圈及套筒路径碰到两颗甲板螺钉头。采用已复核的 C02 工序：其余甲板连接保留，在给定支承条件下先完成侧接头，再补装 R01_D_lower_±1_140 两完整甲板接头的八件硬件。补装、上下工具及退出路径均重新检查。内工具到甲板名义间隙0.65 mm，到 U 槽0.20 mm。此结论以结构件已就位、位姿冻结为条件；工装及结构件本体装入未验证。

89项实体几何检查、20对真实承压面测量、3780项限定范围的静态与包络检查通过（含包围盒筛查）；旧源八件对拍、24件参数扰动及24件恢复通过。原生装配保存重开后，53件依赖、实体和位置通过；实际 SolidWorks STEP 回导也通过53/53项材料与位置对照。31个绑定源输入未变。原失败回执保留，历史扫掠文件的哈希恢复过程单独披露。

**待核定：** 1.3 mm 角材端部剩余边、1.05 mm 孔间薄壁的承载，材料与制造公差，实物螺纹、防松、预紧，真实工具及工装。现有 B601 几何 HOLD、整机连续动作和制造放行状态不变。SolidWorks 文件为导入实体及固定定位装配；可调参数保存在 Python/JSON 源中。

下一工包仍围绕这四处接头：绑定真实工具/工装和采购紧固件规格，完成公差、预紧与试装条件细化。

- [打开局部 SolidWorks 装配](native/WP06_SIDE_JOINT_C02.SLDASM) · [零件目录](native/parts) · [BOM](results/LOCAL_BOM.csv)
- [交互查看局部 CAD]({viewer}) · [内侧细节](results/snapshots/lower_inside_20260906T175759Z.png)
- [机器回执](results/WP06_RESULT.json) · [源参数](candidate/design_parameters.json) · [源改动](results/SOURCE_CHANGES.diff)

目录几何身份与校验值见[来源记录](inputs/CATALOGUE_PROVENANCE.json)。尺寸交叉依据：[Bossard M3 驱动规格](https://www.bossard.com/th-en/-/media/bossard-group/website/documents/technical-resources/en/f-077-en.pdf)、[Würth M3 螺母](https://eshop.wuerth.de/Hexagon-nut-ISO-4032-steel-6-8-plain-NUT-HEX-ISO4032-6-WS55-M3/031093.sku/en/US/EUR/)。几何目录与尺寸参考不构成采购或材料认证。
'''
report=re.sub(r'\]\(((?:native|results|candidate|inputs)/[^)]+)\)',lambda m:'](<'+(R/m.group(1)).as_posix()+'>)',report)
catalog_links=[]
for p in sorted((R/'inputs/catalog').glob('*.step')):
    catalog_links.append('['+p.stem+']('+base+'?file='+p.relative_to(R).as_posix()+')')
report+='\n目录件交互查看：'+' · '.join(catalog_links)+'。\n'
(R/'WP06_MECHANICAL_HANDOFF_ZH.md').write_text(report,encoding='utf-8')
print(json.dumps({'status':result['status'],'report':str(R/'WP06_MECHANICAL_HANDOFF_ZH.md'),'viewer':viewer},ensure_ascii=False))
