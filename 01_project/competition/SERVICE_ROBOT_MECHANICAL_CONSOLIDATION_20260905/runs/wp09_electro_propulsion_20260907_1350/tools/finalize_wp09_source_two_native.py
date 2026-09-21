"""Consolidate completed WP09 artifacts; never upgrade whole-spacecraft qualification."""
from pathlib import Path
import json,hashlib,csv,collections,re,datetime
R=Path(__file__).resolve().parents[1]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def link(p,label):return '['+label+'](<'+str(Path(p).resolve()).replace('\\','/')+'>)'
def choose(paths,status):
    matches=[p for p in paths if read(p).get('status')==status]
    assert len(matches)==1,(status,[str(x) for x in matches])
    return matches[0]
mods={};pins={};bom=[]
preview_paths={}
for kind,pattern in [('a3200','a3200_iso_*.png'),('mips','mips_opposite_*.png'),('battery_mount','battery_mount_v2_opposite_*.png')]:
    matches=list((R/'viewer').glob(pattern));assert len(matches)==1,(kind,matches)
    preview_paths[kind]=matches[0]
extra_inputs=[Path(__file__),R/'results/COMPONENT_ENVELOPE_SCREEN.json',R/'docs/DIMENSIONS_AND_ASSEMBLY_SEQUENCE_ZH.md',
 R/'results/BATTERY_NATIVE_BLOCKER.json',R/'results/battery_iges_transfer_v3/CHECK.json',R/'docs/ELECTRO_PROPULSION_MECHANICAL_WORK_PACKAGE_ZH.md',R/'docs/INDEPENDENT_DELIVERY_REVIEW_ZH.md',R/'research/ELECTRICAL_HARDWARE_RESEARCH.md',
 R/'research/PROPULSION_HARDWARE_RESEARCH.md',R/'research/MECHANICAL_ALLOCATION_DECISIONS.md',*preview_paths.values()]
for path in extra_inputs:pins[str(path)]=sha(path)
screen=read(R/'results/COMPONENT_ENVELOPE_SCREEN.json')
assert screen['all_inputs_unchanged'] and screen['input_sha256_before']==screen['input_sha256_after']
pins.update(screen['input_sha256_before'])
for kind in ['battery_mount','a3200','mips']:
    result_dir=R/'results'/('battery_mount_v2' if kind=='battery_mount' else kind)
    ep=result_dir/'EMISSION.json';em=read(ep)
    local=choose(result_dir.glob('CHECK*.json'),'PASS_LOCAL_BATTERY_CARRIER_NOMINAL_GEOMETRY_ONLY' if kind=='battery_mount' else 'PASS_SCOPED_LOCAL_MODULE_CARRIER_STEP_GEOMETRY')
    if kind=='battery_mount':
        d=read(local);pins[str(local)]=sha(local);pins.update(d['input_sha256_before'])
        bound={str(Path(p).resolve()).casefold():h for p,h in d['input_sha256_before'].items()}
        assert bound.get(str(ep.resolve()).casefold())==sha(ep)
        roles=collections.Counter()
        for ident,row in em['parts'].items():
            b=row['bbox_mm'];roles[row['representation_role']]+=1
            bom.append(dict(module=kind,instance_id=ident,representation_role=row['representation_role'],quantity=1,
              source_step=row['path'],source_sha256=row['sha256'],native_part='',native_sha256='',
              x_mm=b['max_mm'][0]-b['min_mm'][0],y_mm=b['max_mm'][1]-b['min_mm'][1],z_mm=b['max_mm'][2]-b['min_mm'][2],
              actual_hardware_selected=False,manufacturing_release=False))
        mods[kind]=dict(instances=em['instances'],roles=dict(roles),source_emission=str(ep),source_assembly=em['assembly_step'],
          local_check=str(local),local_check_count=d['counts'],native_receipt=None,native_assembly=None,
          native_material_check=None,native_material_check_count=None,native_status='HOLD_NO_VERIFIED_NATIVE_SOLID_TRANSFER',
          native_blocker=str(R/'results/BATTERY_NATIVE_BLOCKER.json'),frame='S_WORLD_MM_IDENTITY',integrated_into_wp08=False)
        for b in range(1,7):
            failed=R/f'results/battery_mount_NATIVE_BOUNDED_B{b}.json';pins[str(failed)]=sha(failed)
        continue
    np=choose((R/'results').glob(kind+'_NATIVE_BOUNDED_B*.json'),'PASS_NATIVE_FIXED_LOCAL_ASSEMBLY_COLD_REOPEN_ONLY');n=read(np)
    mp=R/'results'/(kind+'_NATIVE_MATERIAL_CHECK.json');v=read(mp)
    assert v['status']=='PASS_LOCAL_NATIVE_STEP_MATERIAL_EQUIVALENCE'
    def norm(p):return str(Path(p).resolve()).replace('\\','/').casefold()
    for receipt,dependencies in [(read(local),[ep]),(n,[ep,local]),(v,[ep,local,np])]:
        bound={norm(p):h for p,h in receipt['input_sha256_before'].items()}
        assert all(bound.get(norm(p))==sha(p) for p in dependencies),('mismatched revision chain',kind)
    assert len(n['parts'])==em['instances'] and len({x['id'] for x in n['parts']})==em['instances']
    for rp in [local,np,mp]:
        d=read(rp);pins[str(rp)]=sha(rp)
        for p,h in d['input_sha256_before'].items():
            assert p not in pins or pins[p]==h,('conflicting source pin',p)
            pins[p]=h
    expected={x['id']:x for x in n['parts']}
    roles=collections.Counter()
    for ident,row in em['parts'].items():
        assert norm(expected[ident]['source'])==norm(row['path']) and expected[ident]['source_sha256']==row['sha256'],('wrong native source revision',kind,ident)
        native=expected[ident]['native_save'];b=row['bbox_mm'];roles[row['representation_role']]+=1
        bom.append(dict(module=kind,instance_id=ident,representation_role=row['representation_role'],quantity=1,
          source_step=row['path'],source_sha256=row['sha256'],native_part=native['path'],native_sha256=native['sha256'],
          x_mm=b['max_mm'][0]-b['min_mm'][0],y_mm=b['max_mm'][1]-b['min_mm'][1],z_mm=b['max_mm'][2]-b['min_mm'][2],
          actual_hardware_selected=False,manufacturing_release=False))
    mods[kind]=dict(instances=em['instances'],roles=dict(roles),source_emission=str(ep),local_check=str(local),
      local_check_count=read(local)['counts'],native_receipt=str(np),native_assembly=n['assembly_save'],
      native_material_check=str(mp),native_material_check_count=v['counts'],frame=n['coordinate_frame'],
      integrated_into_wp08=False)
changed=[p for p,h in pins.items() if not Path(p).is_file() or sha(p)!=h];assert not changed,changed
assert len(bom)==44
bp=R/'docs/LOCAL_INSTANCE_BOM.csv';assert not bp.exists()
with bp.open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(bom[0]));w.writeheader();w.writerows(bom)
status=dict(schema='WP09_DELIVERY_STATUS',status='THREE_LOCAL_STEP_PACKAGES_TWO_NATIVE_ASSEMBLIES_VERIFIED__BATTERY_NATIVE_HOLD__INTEGRATION_OPEN',
 date=datetime.datetime.now().astimezone().isoformat(),modules=mods,total_local_instances=44,total_native_parts=28,total_native_assemblies=2,verified_native_modules=['a3200','mips'],native_holds=['battery_mount'],
 local_nominal_geometry_verified=True,native_cold_reopen_verified=dict(a3200=True,mips=True,battery_mount=False),native_source_material_transfer_verified=dict(a3200=True,mips=True,battery_mount=False),
 complete_electrical_design=False,complete_propulsion_design=False,complete_spacecraft_mechanical_design=False,
 physical_assembly_completed=False,as_built=False,manufacturing_release=False,flight_qualification=False,
 historical_science_or_mass_budget_changed=False,wp08_full_assembly_modified=False,
 official_hardware_allocation_screen='results/COMPONENT_ENVELOPE_SCREEN.json',
 source_files_rechecked=len(pins),all_bound_inputs_unchanged=True,
 open_items=['Battery countersunk screw native solid transfer HOLD','Actual B601 revision and power/regeneration profile','P60/BPX layout and power compatibility','Battery self retention and material/preload','A3200 populated board and FSI/EMC/thermal/host attachment','MiPS thread depth/fastener and actual connector/plume/thrust vectors','Shared ADCS/propulsion layout and whole-star neighbour clearance','Structural/thermal/environmental validation'])
sp=R/'results/DELIVERY_STATUS.json';assert not sp.exists()
names={'battery_mount':'电池载板—甲板固定','a3200':'A3200 参考载板','mips':'MiPS 推进外托架'}
lines=['# WP09 电气与推进部件机械设计候选','',
 '本轮完成三套可查看的局部 STEP 模型，共44个局部实体；其中A3200与MiPS交付28个验证过的原生零件文件和2套SolidWorks固定定位装配。三套源几何检查共726项通过，专项检查了电池连接的实际接触面积；另两套完成原生冷重开与STEP回导材料等价。电池沉头螺钉跨内核导入仍不合格，因此电池原生装配保持HOLD。可继续硬件型号绑定和受控整星布置调整，整星电气、推进、实物装配与制造放行尚未完成。','',
 '## 直接查看','',
 '| 组件 | 原生装配 | 局部检查 | 回导材料检查 |','|---|---|---|---|']
for k,d in mods.items():
    native_link=link(d['native_assembly']['path'],'打开 SLDASM') if d['native_assembly'] else link(d['source_assembly']['path'],'打开源 STEP（原生HOLD）')
    material_link=link(d['native_material_check'],str(d['native_material_check_count']['PASS'])+'项通过') if d['native_material_check'] else link(d['native_blocker'],'未通过转换')
    lines.append('|'+names[k]+'（'+str(d['instances'])+'实体）|'+native_link+'|'+link(d['local_check'],str(d['local_check_count']['PASS'])+'项通过')+'|'+material_link+'|')
lines+=['','已交付的两套SolidWorks零件为源STEP导入实体，装配采用固定定位，没有可动配合。native目录还保留失败诊断文件；有效交付仅限上表与BOM所指28件。尺寸合同和构建源位于 inputs/ 与 candidate/，可按合同改版重建；当前原生实体没有完整的特征历史。保留 native/<模块>/parts 全部依赖；尚未进行异机路径迁移测试。','',
 '## 本轮实际变化','',
 '- 电池：在既有载板/下设备甲板源实体上完成4处沉头座和甲板通孔，加入12个目录紧固件；固定的是载板，电池本体压紧、防窜和绝缘仍未定。三态新增硬件/邻件筛查与工具空间分阶段核验。顶部工具在电池/热垫装入后受阻，要求先固定载板再装电池；底部工具只证明接近螺母外端的空间。',
 '- A3200：85×60×2载板、4根3mm支柱、65×40×1.8 PCB参考板及M3紧固堆栈。厂家图中部分孔位通过对称性推导；没有真实器件、铜层、完整FSI连接器和绝缘/热设计。参考依据：[GomSpace A3200 DS1006901 Rev2.0](https://gomspace.com/wp-content/uploads/2025/09/gs-ds-nanomind-a3200_1006901-2.0.pdf)。',
 '- MiPS：依据厂家外形与两侧4-40 UNC-2B孔基准建立非承压外托架和4片接口垫。透明体为最大外形包络；螺孔有效深度、螺钉长度、端口和三维喷口/羽流资料未知。局部托架当前高97mm，不能按当前姿态进入75mm共享舱。参考依据：[VACCO Standard MiPS](https://www.vacco.com/images/uploads/pdfs/MiPS_standard_0714.pdf)。','',
 '## 研究已识别的布局与电气约束','',
 'P60 各份资料的尺寸口径均不能装入现有65×70×30 EPS预算；BPX单块外形有可行排列，双块的全部轴对齐并列方式失败。MiPS单盒的可行排列要求30mm深度沿现有预算Z轴，但尚未证明与ADCS共存。A3200单载板可继续细化，其箱体还承担通信设备，不能独占预算。完整计算见 '+link(R/'results/COMPONENT_ENVELOPE_SCREEN.json','包络筛查')+'。','',
 'P60的24V降压选项要求电池最低输入大于25.5V，不能覆盖本轮BPX候选的全部低电压工作段；机械臂应单列稳压、保护、回生处理和导热安装设计。实际B601版本/电流谱未确认，未按地面电源铭牌冒充航天功耗。来源和相互冲突的口径见 '+link(R/'research/ELECTRICAL_HARDWARE_RESEARCH.md','电气资料核验')+'。','',
 '## 工程交接','',
 '- '+link(R/'docs/DIMENSIONS_AND_ASSEMBLY_SEQUENCE_ZH.md','尺寸与装配顺序卡'),
 '- '+link(bp,'44项局部实例 BOM'),
 '- '+link(R/'results/BATTERY_NATIVE_BLOCKER.json',R/'results/battery_iges_transfer_v3/CHECK.json',R/'docs/ELECTRO_PROPULSION_MECHANICAL_WORK_PACKAGE_ZH.md','12项后续机械工程工作包'),
 '- '+link(R/'research/PROPULSION_HARDWARE_RESEARCH.md','推进硬件来源核验'),
 '- '+link(R/'research/MECHANICAL_ALLOCATION_DECISIONS.md','受控布置调整依据'),
 '- '+link(sp,'机器交付状态'), '',
 '三组局部模型均未合入 WP08 的625实例整机，也不包含此前未合入整机的后肋板局部候选。现有整机、质量预算、科学 Gate 与历史负结果保持原样。','',
 '## 运行记录','',
 'A3200 首轮原生导入触发512MiB空闲内存保护；已核对唯一中断时保存的干净文件，退出空CAD会话，分批恢复并完成22件冷重开和材料等价。原始保存API确认在该一件上仍为UNKNOWN；后续检查证明文件可读与几何一致，不回填旧确认。首轮原生回执与守卫日志原样保留。','',
 '电池初版主锥角识别采用了合同外角度阈值，首轮失败保留；修复识别后实际接触面积仍为零，第二次失败亦保留。修正版仅把沉头座解析参数匹配到目录螺钉实际主锥，独立重查去材、接触、邻件及工具空间；名义90°尺寸和原接受阈值保持，未给加工公差或强度信用。','',
 '直接STEP导入电池沉头螺钉的四次尝试因COM极值检测与源相差约5.639µm而失败。补充高精度体积、极值点与源距离、原生STEP回导诊断未建立等价证明，故原失败保留。随后源STEP→IGES BRep回读29项通过，但两种SolidWorks IGES实体导入模式均只得到7个曲面体、0个实体，未建立电池原生装配。失败曲面文件已保存用于诊断；当前可查看的电池交付为已验证源STEP。转换HOLD详情见 '+link(R/'results/BATTERY_NATIVE_BLOCKER.json','电池原生阻塞记录')+'。验收阈值未放宽。IGES检查初版的内核零值断言和第二版临时文件替换失败均保留；修正版仅解释内核固有1e−7mm底线并重试瞬时文件锁，不改变几何。','',
 '交付复查意见见 '+link(R/'docs/INDEPENDENT_DELIVERY_REVIEW_ZH.md','独立于CAD执行的文档和证据复查')+'。该复查是时间快照；后续原生转换结果由上表当前机器回执给出。MiPS检漏/功能检查已明确划为未来供应商许可规程阶段。','',
 '## 预览','']
for k,picture in preview_paths.items():
    lines+=['### '+names[k],'','!['+names[k]+']('+str(picture).replace('\\','/')+')','']
rp=R/'README.md';assert not rp.exists();rp.write_text('\n'.join(lines),encoding='utf-8')
pinout=R/'results/VERIFIED_INPUT_SHA256.json';pinout.write_text(json.dumps(pins,indent=2),encoding='utf-8')
assert all(sha(p)==h for p,h in pins.items()),'Delivery input changed while preparing files'
temp=sp.with_suffix('.json.tmp');temp.write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(sp)
print(json.dumps(dict(status=status['status'],instances=len(bom),verified_inputs=len(pins),readme=str(rp)),ensure_ascii=False))
