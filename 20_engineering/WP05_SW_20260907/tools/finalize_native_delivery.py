"""Publish only measured native CAD delivery facts; never grant engineering release."""
from pathlib import Path
from collections import Counter
import json,hashlib,datetime,csv
R=Path(__file__).resolve().parents[1]
P=R.parents[1]
OLD=P/'01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp04_robot_assembly_20260906_175153'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.file_digest(Path(p).open('rb'),'sha256').hexdigest()
def write(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def link(label,p):return '['+label+'](<'+str(Path(p).resolve()).replace('\\','/')+'>)'
def main():
 mf=read(R/'results/PARTS_SOURCE_MANIFEST_DEDUP.json');ip=read(R/'results/NATIVE_IMPORTS.json')
 audit=read(R/'results/INDEPENDENT_NATIVE_DELIVERY_CHECK.json')
 scoped=read(R/'results/INDEPENDENT_SCOPED_ASSEMBLY_CHECK.json')
 assert len(scoped['results'])==2
 visual=read(R/'results/VISUAL_REVIEW.json')
 assert visual['status']=='PASS_VISUAL_PRESENTATION_ONLY'
 assert len(visual['images'])==5 and len({v['name'] for v in visual['images']})==5
 for v in visual['images']:
  assert sha(v['source'])==v['source_sha256'] and sha(v['target'])==v['target_sha256']
  assert sha(R/'results'/(v['name']+'_COLD.json'))==v['cold_receipt_sha256']
 scenes={s:read(R/'results'/('WP05_ROBOT_'+s.upper()+'_COLD.json')) for s in ['service','parking','released']}
 local=read(R/'results/WP05_R07_CONNECTIONS_COLD.json')
 arm=read(R/'results/WP05_B601_SERVICE_COLD.json')
 opened=read(R/'results/USER_OPEN_RECEIPT.json')
 assert opened['status']=='VERIFIED_ASSEMBLY_OPEN_FOR_USER' and opened['component_count']==585
 assert opened['sha256']==scenes['service']['target_sha256'] and opened['native_file_unchanged']
 assert len(ip['parts'])==len(mf['parts']) and all(c['component_count']==585 for c in scenes.values())
 source_checks=[{'path':p,'expected_sha256':h,'actual_sha256':sha(p)} for p,h in mf['source_sha256_before'].items()]
 original=read(OLD/'results/FINAL_ARTIFACT_MANIFEST.json')
 previous_checks=[{'path':str(OLD/f['path']),'expected_sha256':f['sha256'],'actual_sha256':sha(OLD/f['path'])} for f in original['files']]
 assert all(c['expected_sha256']==c['actual_sha256'] for c in source_checks+previous_checks)
 write(R/'results/SOURCE_PRESERVATION_FINAL.json',{'status':'PASS_EXACT_FILE_HASH_PRESERVATION','source_checks':source_checks,'previous_sealed_checks':previous_checks,'previous_seal_sha256':sha(OLD/'results/FINAL_ARTIFACT_MANIFEST.json')})
 pending=[p for p in ip['parts'] if not p['source_comparison']['pass']]
 holds=[]
 for part in pending:
  ev=part['source_comparison'].get('roundtrip_validation',{})
  if ev.get('status')=='PASS':continue
  validity=ev.get('validity_preflight') or {}
  holds.append({'part_key':part['part_key'],'status':ev.get('status','NOT_EVALUATED'),'reason':ev.get('reason',''),
   'source_invalid_solid_indices':validity.get('source',{}).get('invalid_solid_indices'),
   'roundtrip_invalid_solid_indices':validity.get('roundtrip',{}).get('invalid_solid_indices'),
   'unmatched_source_indices':ev.get('unmatched_source_indices',ev.get('unmatched_source_body_indices')),
   'volume_difference_mm3':ev.get('volume_difference_mm3'),'symmetric_difference_mm3':ev.get('symmetric_difference_mm3')})
 verification_levels={'native_scalar_solid_count_bbox_pass':len(ip['parts'])-len(pending),'additional_same_kernel_roundtrip_pass':sum(p['source_comparison'].get('roundtrip_validation',{}).get('status')=='PASS' for p in pending),'geometry_holds':len(holds)}
 write(R/'results/GEOMETRY_HOLD_REGISTER.json',{'native_parts_passing_declared_geometry_checks':len(ip['parts'])-len(holds),'verification_levels':verification_levels,'geometry_holds':holds,'index_base':0,'source_or_roundtrip_validity_is_occ_kernel_specific':True,'all_parts_same_kernel_material_equivalence_proven':False,'no_threshold_relaxation':True})
 if holds:
  with (R/'results/GEOMETRY_HOLD_REGISTER.csv').open('w',encoding='utf-8-sig',newline='') as f:
   writer=csv.DictWriter(f,fieldnames=list(holds[0]));writer.writeheader();writer.writerows(holds)
 def cell(v):return '未取得结果' if v is None else str(v)
 hold_text=''
 if holds:
  hold_text='\n\n**几何保留项：'+str(len(holds))+' 个零件未通过完整材料传递核验。** 当前文件可用于查看与继续修复，不得声明全套几何等价已通过。无效实体指标属于 OCC 对源或回导 BRep 的检查结果，不能直接认定为实物缺陷。逐零件/实体索引与数值见 '+link('几何问题清单',R/'results/GEOMETRY_HOLD_REGISTER.json')+'。\n\n| 零件 | 核验结果 | 源无效实体索引 | 回导无效实体索引 | 同核体积差 mm³ |\n|---|---|---|---|---:|\n'
  hold_text+='\n'.join('| '+' | '.join([h['part_key'],h['status'],cell(h['source_invalid_solid_indices']),cell(h['roundtrip_invalid_solid_indices']),cell(h['volume_difference_mm3'])])+' |' for h in holds)
 role=Counter(x['representation_role'] for x in mf['states']['service']['instances'])
 assembly_checks=[c for c in audit['checks'] if c['required'] and c['check'].startswith(('assembly:','state:'))]
 assert assembly_checks and all(c['status']=='PASS' for c in assembly_checks)
 assembly_check_summary={'status':'PASS_RECORDED_FILES_POSES_BODIES_AND_REFERENCES_ONLY','counts':dict(Counter(c['status'] for c in assembly_checks))}
 result={'schema':'WP05_NATIVE_SOLIDWORKS_DELIVERY_V1','generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
  'status':'NATIVE_CAD_DELIVERED_AND_VERIFIED' if audit['status']=='PASS_RECORDED_NATIVE_DELIVERY_EVIDENCE_ONLY' and all(a['status']=='PASS_RECORDED_NATIVE_DELIVERY_EVIDENCE_ONLY' for a in scoped['results']) else 'NATIVE_CAD_DELIVERED_WITH_RECORDED_VERIFICATION_HOLDS',
  'native_part_count':len(ip['parts']),'states':{s:{'assembly':c['target'],'instances':c['component_count'],'resolved_solids':c['resolved_solid_total'],'sha256':c['target_sha256']} for s,c in scenes.items()},
  'connection_assembly':{'path':local['target'],'instances':local['component_count']},'arm_assembly':{'path':arm['target'],'instances':arm['component_count']},'roles_per_state':dict(role),
  'independent_receipt_audit':{'status':audit['status'],'required_counts':audit['counts'],'diagnostic_counts':audit['diagnostic_counts'],'path':str(R/'results/INDEPENDENT_NATIVE_DELIVERY_CHECK.json')},
  'assembly_file_pose_body_reference_checks':assembly_check_summary,
  'independent_scoped_assembly_audits':[{'name':a['name'],'status':a['status'],'counts':a['counts']} for a in scoped['results']],
  'original_scalar_volume_diagnostic_failures_retained':len(pending),'roundtrip_geometry_results':dict(Counter(p['source_comparison'].get('roundtrip_validation',{}).get('status','NOT_EVALUATED') for p in pending)),
  'native_parts_passing_declared_geometry_checks':len(ip['parts'])-len(holds),'geometry_hold_count':len(holds),'verification_levels':verification_levels,'all_parts_same_kernel_material_equivalence_proven':False,
  'previous_sealed_files_unchanged':len(previous_checks),'original_inputs_unchanged':len(source_checks),
  'all_mechanical_design_complete':False,'manufacturing_release':False,'physical_assembly_completed':False,'continuous_motion_verified':False,'flight_qualified':False,
  'native_feature_history':'IMPORTED_BREP','assembly_constraints':'FIXED_POSE_COMPONENTS','hardware_command_authorized':False}
 write(R/'results/WP05_RESULT.json',result)
 labels={'service':'服务态','parking':'开放停放态','released':'释放态'}
 rows='\n'.join('| '+labels[s]+' | '+link(Path(c['target']).name,c['target'])+' | '+str(c['component_count'])+' | '+str(c['resolved_solid_total'])+' |' for s,c in scenes.items())
 text=f'''# 航天服务星与 B601：SolidWorks 原生零件及装配

本次接续中断工作，已把 WP04 的三态数字装配候选转换为 **{len(ip['parts'])} 个可复用 .SLDPRT 零件、3 个整机 .SLDASM、1 个连接局部 .SLDASM 和 1 个 B601 机械臂 .SLDASM**。零件含实际边界表示实体，整机引用这些零件，可在 SolidWorks 2024 中展开组件树、逐件选择、隐藏和继续设计。

{link('服务态整机',scenes['service']['target'])} · {link('零件目录',R/'parts')} · {link('原生交付核验',R/'results/INDEPENDENT_NATIVE_DELIVERY_CHECK.json')} · {link('实例与零件清单',R/'bom')}

![SolidWorks 服务态整机](<{(R/'screenshots/WP05_ROBOT_SERVICE.png').as_posix()}>)

| 配置 | 原生装配文件 | 组件实例 | 解析实体数 |
|---|---|---:|---:|
{rows}

{link('R07 连接局部装配',local['target'])}含 {local['component_count']} 个实例，用于检查主结构、端塞、跨板、套管与相关连接关系；{link('B601 机械臂服务态装配',arm['target'])}含 {arm['component_count']} 个链接组件，保留整机 S 系下的服务姿态坐标。“开放停放态”不表示已满足发射收拢包络。

零件全部执行保存、关闭、重新打开，记录实体数、曲面体数、体积、包围盒和外部引用。整机保存后重新打开，逐项核对组件编号、实际依赖路径、安装变换、表示角色、固定状态和可解析实体。三态装配的组件、坐标、依赖和实体数量核对已通过。包含几何传递判据在内的独立回执核验状态为 **{audit['status']}**，必需检查计数为 `{audit['counts']}`。此独立检查读取真实 COM 执行回执和文件 SHA；没有把回执检查称为另一 CAD 内核的独立装配试验。
{hold_text}

有 {verification_levels['native_scalar_solid_count_bbox_pass']} 个零件通过实体数、曲面体数、体积及包围盒核对；这些指标不等同于逐面材料等价证明。另保留了 {len(pending)} 项跨内核标量体积差诊断，未放宽原数值阈值。对这 {len(pending)} 项执行了 SolidWorks 实际 STEP 回导，并逐件进行有时间上限的同一 OCC 内核材料差检查，结果为 `{result['roundtrip_geometry_results']}`；FAIL 与 INCOMPLETE 均保留为未关闭项。详见 {link('回导几何验证',R/'results/NATIVE_ROUNDTRIP_VALIDATION.json')}。STEP 导出前需激活目标文档并清空选择，依据 [SOLIDWORKS API 文档](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDocExtension~SaveAs.html)。早期导出崩溃及失败诊断保留在 queue 与 results 中。

每态仍是 **{role['PHYSICAL_GEOMETRY']} 项物理几何、{role['SIMPLIFIED_PROXY']} 项简化代理、{role['FUNCTIONAL_ENVELOPE']} 项功能包络**；功能包络在原生主视图中隐藏，可通过组件树查看。585 个实例不等于 585 件完成选型的实物零件。10 个机械臂链接按原 STEP 内部实体与链接局部坐标保留；不同构型引用各自的安装变换。

现有 .SLDPRT 使用导入 BRep 特征，尚未重建全套草图、尺寸和加工特征树；.SLDASM 使用固定姿态组件，尚未建立可驱动的完整配合机构。不能从本次原生转换推导全机无干涉、连续动作通过、强度通过或制造放行。SW 默认材质或密度不用于整机质量结论。质量未知字段保留为空；历史零件号按来源保留，仍需结合实际候选几何校核，特别是旧 M4×22 标识与已缩短的前端螺钉。

为控制内存，建议一次打开一个整机装配；整机按轻化形式保存，编辑时再解析所需组件。打开时保留本目录的 `assemblies/` 与 `parts/` 相对目录关系；当前实际重开检查的依赖均在本交付目录内。此轮未进行搬移目录后的独立重开试验。`bom/WP05_INSTANCES_*.csv` 每态逐实例列出原编号、角色、原零件号、规范零件路径及来源；`WP05_CANONICAL_PARTS.csv` 分态列数量并取三态最大值，不把互斥配置用量相加作采购数量。

质量表分别保存 CAD 来源字段与已绑定的数字身体分配字段。原来源字段有 188 项非空；数字身体账本有 198 项分配与 387 项 UNKNOWN，其中 10 个机械臂链接质量从已接受 URDF 逐链接核对、仅计一次。数字分配合计 20.733608541407722 kg，不是完整整机实测质量，也不能与原来源列再次相加。

现在可以进入 SolidWorks 接口细化与装配设计审查：先逐项处理几何保留项、重建关键连接件参数特征，再建立保持器导向、防脱、止挡及退出锁止的完整结构和运动配合，再检查盖板、设备、工具与线束装入路径。随后用实际 B601/器件 ICD、材料、紧固件和载荷输入完成尺寸链、连接承载、预紧及完整制造图。既有重点未关闭项包括 2.5 mm 沉孔残底、1.13276253 mm 叉座净距、0 mm 旧侧螺钉名义间隙、八处螺纹代理未知、整机连续避碰以及质量未知项，仍以 {link('WP04 详细设计输入清单',OLD/'MECHANICAL_INPUT_REGISTER_ZH.md')} 和 {link('装配工序',OLD/'ASSEMBLY_PROCEDURE_ZH.md')} 为入口。

已另附 {link('SolidWorks 后续细化与检查工序',P/'01_project/competition/WP05_SolidWorks后续细化与检查工序_20260907.md')}，明确几何修复、参数特征、可动配合、保持机构、装入路径与图纸的后续执行顺序。这些步骤仍待实施。

本轮 {len(source_checks)} 项输入文件和前轮封存的 {len(previous_checks)} 个文件 SHA 均保持一致，见 {link('来源保护',R/'results/SOURCE_PRESERVATION_FINAL.json')}。原研究 Gate、制造状态和硬件许可没有升级。
'''
 (R/'README_ZH.md').write_text(text,encoding='utf-8')
 report=P/'01_project/competition/WP05_SolidWorks原生机械装配交付_20260907.md';report.write_text(text,encoding='utf-8')
 excluded={'ARTIFACT_MANIFEST.json'}
 files=[p for p in R.rglob('*') if p.is_file() and p.name not in excluded and not any(s in {'__pycache__','__cadgen__'} for s in p.parts) and p.suffix.lower() not in {'.pyc','.tmp'} and not p.name.startswith('~$')]
 inventory=[{'path':str(p.relative_to(R)).replace('\\','/'),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(files)]
 actual_native_hashes={str((R/f['path']).resolve()).casefold():f['sha256'] for f in inventory}
 expected_native_hashes={str(Path(p['target']).resolve()).casefold():p['native_save']['sha256'] for p in ip['parts']}
 expected_native_hashes.update({str(Path(c['target']).resolve()).casefold():c['target_sha256'] for c in [*scenes.values(),local,arm]})
 assert all(actual_native_hashes.get(p)==h for p,h in expected_native_hashes.items())
 next_doc=P/'01_project/competition/WP05_SolidWorks后续细化与检查工序_20260907.md'
 write(R/'results/ARTIFACT_MANIFEST.json',{'schema':'WP05_ARTIFACT_INTEGRITY_V1','files':inventory,'file_count':len(inventory),'bytes':sum(f['bytes'] for f in inventory),'native_files_reconciled_to_execution_sha256':len(expected_native_hashes),'report':{'path':str(report),'sha256':sha(report)},'detailing_procedure':{'path':str(next_doc),'sha256':sha(next_doc)},'self_excluded':True,'manufacturing_release':False})
 print(json.dumps({'result':str(R/'results/WP05_RESULT.json'),'status':result['status'],'files':len(inventory)},ensure_ascii=False))
if __name__=='__main__':main()
