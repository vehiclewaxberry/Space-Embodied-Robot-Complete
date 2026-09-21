"""Seal a portable package only after primary and physically relocated cold proofs."""
from pathlib import Path
import hashlib,json,zipfile
C=Path(__file__).resolve().parents[1];P=C/'mechanical/portable/package'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
names=['PORTABLE_INPUTS.json','PORTABLE_COPY_V2.json','PORTABLE_COLD_PRIMARY_V2.json','PORTABLE_MOVE_FORWARD.json','PORTABLE_MOVE_SHORT_PATH.json','PORTABLE_COLD_RELOCATED_V2.json','PORTABLE_MOVE_RETURN.json']
receipts={n:json.loads((C/'results'/n).read_text()) for n in names}
assert all(r['status'].startswith('PASS') or n=='PORTABLE_INPUTS.json' for n,r in receipts.items())
j=receipts['PORTABLE_INPUTS.json'];copy=receipts['PORTABLE_COPY_V2.json']
assert all(sha(Path(p))==d for p,d in j['input_sha256'].items())
for p in j['parts']:assert sha(P/p['copy_name'])==p['source_sha256'] and sha(Path(p['source']))==p['source_sha256']
for state,s in copy['states'].items():assert sha(P/Path(s['target']).name)==s['sha256']
manifest={'identity':'Portable fixed-pose native assembly candidate, not manufacturing/flight release',
 'parts':[{'file':q['copy_name'],'sha256':q['source_sha256'],'bytes':q['bytes']} for q in j['parts']],
 'states':{s:{'file':v['target_name'],'sha256':copy['states'][s]['sha256'],'components':705,'solids_hash_bound':1086,
    'instances':[{'id':q['id'],'part':q['copy_name'],'native_T_local_to_S':q['native_T_local_to_S'],'expected_solids':q['expected_solids']} for q in v['rows']]} for s,v in j['states'].items()},
 'coordinate_frame':'S frame, native part local transform with mm translations; SolidWorks API uses m',
 'copy_method':'Byte-identical part copies plus ISldWorks.ReplaceReferencedDocument on closed assembly copies; PackAndGo not executed',
 'path_constraint':{'maximum_tested_native_file_path_characters_in_delivery':max(len(str(p)) for p in P.iterdir() if p.is_file()),
   'relocated_verified_maximum_characters':242,'long_path_trial_missing_reference_failure_characters':261,
   'recommendation':'Extract to a short directory; keep full native file paths below 250 characters. API callers set assembly directory as current working directory before OpenDoc6.'},
 'actual_solid_recounts_this_package':0,'outside_native_dependencies_each_state':0,
 'source_parts_byte_identical':True,'physical_relocation_cold_check':True,'kinematic_mates_verified':False}
(P/'PACKAGE_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
(P/'README_ZH.md').write_text('''# 航天服务星三态 SolidWorks 可迁移装配包

本目录含 SERVICE、PARKING、RELEASED 三个原生固定姿态装配，508 个独立原生零件文件。每态 705 个组件、1086 个哈希绑定实体。零件与已封存父版逐字节相同；本轮不重新生成或统计实体。

将本目录整体复制到目标电脑，使用 SolidWorks 2024 SP5.0 或兼容后续版本打开 WP09_SERVICE.SLDASM、WP09_PARKING.SLDASM、WP09_RELEASED.SLDASM。保持三份装配与 P_*.SLDPRT 文件同目录，不单独移动装配文件。当前检查环境为 SolidWorks 32.5.0。

请解压到较短目录，例如 C:/CAD/WP09，完整原生文件路径控制在250个字符以内。本交付路径最长244字符，迁移通过路径最长242字符；261字符的长目录试验实际出现缺引用，失败证据已保留。使用“文件→打开”选择本目录的装配；自动化调用 OpenDoc6 前应先 SetCurrentWorkingDirectory 为装配所在目录，符合官方 API 的交互打开语义。

已经执行两组真实冷重开：当前目录三态，以及将整个目录实际移动到另一根目录、确认原路径不存在后再冷开三态。两组均验证705个组件身份、固定状态、原 native_T_local_to_S 变换、零件 SHA256 和实际引用路径；每态目录外原生依赖为0。迁移检验后，文件原样移回本交付目录。

PACKAGE_MANIFEST.json 记录相对文件名、SHA256 和逐实例变换。零件采用内容哈希短名，组件身份仍保留在 ComponentReference。几何为既有实体导入与固定姿态装配，未生成可驱动关节配合，也不据此声明连续运动、线束寿命、制造或飞行放行。
''',encoding='utf-8')
archive=C/'mechanical/portable/WP09_PORTABLE_NATIVE.zip';assert not archive.exists()
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in sorted(P.iterdir()):
  if p.is_file():z.write(p,'WP09_PORTABLE_NATIVE/'+p.name)
with zipfile.ZipFile(archive,'r') as z:
 assert z.testzip() is None
 assert len(z.infolist())==len([p for p in P.iterdir() if p.is_file()])
output={'status':'PASS_PORTABLE_THREE_STATE_NATIVE_COPY_AND_PHYSICAL_RELOCATION_COLD_REOPEN',
 'package':str(P),'archive':{'path':str(archive),'sha256':sha(archive),'bytes':archive.stat().st_size},
 'component_count_each':705,'solids_hash_bound_each':1086,'unique_part_files':508,'source_parts_identical':True,
 'external_dependencies_each':0,'cold_open_state_checks':6,'transform_tolerance_sw16':1e-8,
 'archive_crc_verified':True,'method':'controlled byte copy and closed-document ReplaceReferencedDocument, not PackAndGo',
 'path_constraint':manifest['path_constraint'],
 'historical_attempts':[
   {'receipt':str(C/'logs/portable_copy.run.json'),'outcome':'CopyDocument timeout; own process stopped with parent hashes checked'},
   {'receipt':str(C/'logs/portable_cold_primary.run.json'),'outcome':'Two states passed, third exceeded combined1400MiB; superseded by fresh process per state'},
   {'receipt':str(C/'results/PORTABLE_COLD_RELOCATED_SERVICE.json'),'outcome':'Long trial directory missing references'},
   {'receipt':str(C/'results/PORTABLE_COLD_RELOCATED_SERVICE_V3.json'),'outcome':'Working-directory fix alone still failed at261-character part paths; shorter242-character trial passed'}],
 'manufacturing_release':False,'continuous_motion_verified':False,
 'evidence':[{'path':str(C/'results'/n),'sha256':sha(C/'results'/n)} for n in names],
 'package_files':[{'file':p.name,'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(P.iterdir()) if p.is_file()]}
(C/'results/PORTABLE_DELIVERY.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:output[k] for k in ('status','package','unique_part_files','cold_open_state_checks','archive')}))
