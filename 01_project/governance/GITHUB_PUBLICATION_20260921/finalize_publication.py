from pathlib import Path
from datetime import datetime,timezone
import csv,hashlib,json,re,shutil

A=Path(__file__).resolve().parent;ROOT=A.parents[2]
S=ROOT/'20_engineering/SERVICE_STAR_HARDWARE_COMPACT_20260921'
P=ROOT/'20_engineering/SERVICE_STAR_PUBLICATION_20260921'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def jwrite(p,o):p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def files(base):return sorted(p for p in base.rglob('*') if p.is_file() and '.git' not in p.relative_to(base).parts)

for name in ['Plotly.js_v3.1.0_LICENSE.txt','Plotly.js_v3.1.0_LICENSE_SOURCE.json']:
    shutil.copy2(A/'license_candidates'/name,P/'00_release/licenses'/name)
missing=json.loads((A/'dependency_candidates/MOLEX_DEPENDENCY_CANDIDATES.json').read_text(encoding='utf-8-sig'))
jwrite(P/'02_electrical/verification/MOLEX_UPSTREAM_CHECK.json',missing)
shutil.copytree(A/'dependency_candidates/evidence',P/'02_electrical/verification/molex_upstream_evidence',dirs_exist_ok=True)

supplement=A/'R7_SUPPLEMENT_SELECTION.json'
if supplement.exists():
    selection=json.loads(supplement.read_text(encoding='utf-8-sig'))
    for item in selection['items']:
        assert item['include_by_default'] and sha(ROOT/item['source'])==item['source_sha256']
        dest=P/item['destination'];dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/item['source'],dest)
        assert sha(dest)==item['source_sha256']
    draft=P/selection['recommended_publication_directory']
    (draft/'README.md').write_text(selection['suggested_readme_content'],encoding='utf-8')
    jwrite(draft/'SOURCE_SELECTION.json',selection)
    readme=P/'README.md'
    readme.write_text(readme.read_text(encoding='utf-8').replace('4. 根据[下一阶段路线图]', '4. 查看[R7 AUX/STOP未安装草案](01_mechanical/drafts/R7_aux_stop_uninstalled/README.md)，其中两份独立PCBA STEP与候选姿态作为后续布局资料保留。\n5. 根据[下一阶段路线图]'),encoding='utf-8')

(P/'00_release/PUBLICATION_NOTES.md').write_text('''# 发布范围与使用说明

本版根据项目持有者要求，发布完整选定的四系统硬件设计及已存在的必要依赖，更新原仓库的当前内容。机械737文件的原生闭包、电气工程、BOM、线束、热控和推进资料均在发布清单中逐项列出。没有把原本不存在的零件或未完成的设计伪装成已交付内容。

当前版本以普通Git保存真实文件，未使用LFS指针代替CAD。`PUBLICATION_MANIFEST.csv`与兼容入口`PACKAGE_SHA256.csv`列出除两个清单自身之外的每个交付文件；运行`python 00_release/verify_package.py`检查文件大小与SHA-256。来源清单与历史验证回执的旧路径/哈希用于追溯，不应解释为当前机器上的运行路径。

5个Molex三维模型引用在原工程中缺文件；官方KiCad库核查也未取得同名模型，当前明确保留该缺项而没有替换成相似型号。这影响相关器件的3D查看与导出，不妨碍已提供原理图和PCB文本的打开。其他自定义器件的完整三维覆盖也尚未验收。请参阅电气说明与`02_electrical/verification/MOLEX_UPSTREAM_CHECK.json`。

版权和许可按具名来源分别适用。公开发布不等于所有资料已获得统一开源或商用授权。本项目未对自有文件新增统一的MIT/CERN-OHL授权；未另行标注的自有资料保留原权利。reBot/B601、KiCad、Plotly及其他第三方材料继续适用各自条款和署名要求。

Würth 74651195厂家模型及封装的具体再分发范围仍未闭合。厂家网站[版权说明](https://www.we-online.com/en/service/imprint)限制网站内容的商业复制、分发等用途；[通用销售条款§8.3](https://www.we-online.com/files/pdf1/gtc-we-eisos-germany-en.pdf)另限制客户取得的图纸/模型向第三方提供，其对免费公开CAD下载的具体适用关系尚未确认。未核得本次两个CAD文件的单独再分发许可。这些限制不能简化为全包MIT授权，也不据此推断所有非商业工程引用一律禁止。原厂家资产和已嵌入其几何的MAIN板体保留来源标记；商用或再分发应先核对厂家的适用条款。原件获取入口：[产品页](https://www.we-online.com/en/components/products/WP-THRSH)、[KiCad文件](https://www.we-online.com/components/products/download/KiCad_WP-THRSH%20%28rev26b%29.zip)、[STEP](https://www.we-online.com/components/products/download/74651195%20%28rev1%29.stp)。

原生CAD、STEP、预留包络与BOM各有用途，不能互相替代制造依据。完整性校验不证明全部材料赋值、整星质量闭合、电气可上电、推进选型冻结或飞行资格。
''',encoding='utf-8')
notices=(P/'00_release/THIRD_PARTY_NOTICES.md').read_text(encoding='utf-8')
notices+='''

## 本次发布补充（2026-09-21）

- 离线安装查看器内嵌Plotly.js 3.1.0；[MIT许可全文](licenses/Plotly.js_v3.1.0_LICENSE.txt)与[官方tag获取记录](licenses/Plotly.js_v3.1.0_LICENSE_SOURCE.json)已随包补齐。
- B601/reBot硬件来源见[Seeed-Projects/reBot-DevArm](https://github.com/Seeed-Projects/reBot-DevArm)，其硬件采用CERN-OHL-W-2.0。保留本包已有许可证、来源到目标映射及派生说明；旧仓库笼统的“B601一律只能内部使用”表述不作为当前依据。
- KiCad选中库的官方许可及设计例外文本见[电气库说明](../02_electrical/third_party_notices/README.md)。本地安装库的精确Git修订仍未知，不能将新核查的上游提交号回填为全部旧模型的来源修订。
- Würth原件涉及`02_electrical/kicad/wp10/WP10_TERMINALS.pretty/MP_Wurth_WP-THRSH_74651195R.kicad_mod`与`models/project/MP_Wurth_WP-THRSH_74651195.step`。相关几何已进入MAIN板：`01_mechanical/native/P_f011e65d5e5452c37d2b_e3e9a9.SLDPRT`、`01_mechanical/step/R6H_MAIN_PCBA_INSTALLED.step`及局部展示。它们不因合并为板体而获得新的OEM授权，适用范围见[发布使用说明](PUBLICATION_NOTES.md)。
- `GROUND_CANDIDATE_MATERIALS.sldmat`是项目脚本生成的候选材料文件，不是整套商业SolidWorks材料库；候选密度仍须用真实材料/实物数据核验。
'''
(P/'00_release/THIRD_PARTY_NOTICES.md').write_text(notices,encoding='utf-8')
coverage=[]
for source in files(S):
    rel=source.relative_to(S).as_posix(); dest=P/rel
    assert dest.is_file(),f'Missing original package file: {rel}'
    coverage.append({'source_package_path':rel,'source_sha256':sha(source),'published_sha256':sha(dest),'byte_identical':sha(source)==sha(dest)})
with (P/'00_release/SOURCE_COVERAGE.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(coverage[0]));w.writeheader();w.writerows(coverage)
native=list((P/'01_mechanical/native').glob('*'))
assert len(native)==737 and all(p.is_file() for p in native)
assert all(sha(p)==sha(S/p.relative_to(P)) for p in native),'Native CAD bytes changed'
old=json.loads((S/'00_release/PACKAGE_STATUS.json').read_text(encoding='utf-8'))
status={'schema':'HARDWARE_GITHUB_PUBLICATION_CONTENT_STATUS_V1','prepared_utc':datetime.now(timezone.utc).isoformat(),'project_name':'航天服务星具身智能机械臂机器人','repository':'https://github.com/vehiclewaxberry/Space-Embodied-Robot-Complete','scope':old['scope'],'publication_operation':'Replace main with the selected hardware tree as requested; no old-version backup branch','upload_result_location':'Publisher local governance receipt; actual public Git commit is the release identifier','source_package_files_covered':len(coverage),'source_package_paths_omitted':[],'native_files':737,'native_bytes_unchanged':True,'native_open_verification_inherited':old['native_copy_status'],'engineering_content_changed':False,'native_external_dependencies':0,'ecad_missing_3d_models':5,'all_ecad_3d_dependencies_closed':False,'original_git_history_included':False,'research_control_content_packaged':False,'whole_spacecraft_design_complete':False,'ready_to_power':False,'flight_ready':False,'unified_open_source_license_granted':False,'third_party_clearance_complete':False,'manifest_policy':'All delivered files except the two manifest CSVs themselves; source coverage excludes publication-only additions'}
jwrite(P/'00_release/PACKAGE_STATUS.json',status)
# Status and coverage are intentionally new publication metadata; original source stays untouched.
for r in coverage:
    r['published_sha256']=sha(P/r['source_package_path']);r['byte_identical']=r['source_sha256']==r['published_sha256']
with (P/'00_release/SOURCE_COVERAGE.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(coverage[0]));w.writeheader();w.writerows(coverage)
rows=[{'path':p.relative_to(P).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in files(P) if p.name not in ['PUBLICATION_MANIFEST.csv','PACKAGE_SHA256.csv']]
assert not any(r['bytes']>=100*1024**2 for r in rows)
for name in ['PUBLICATION_MANIFEST.csv','PACKAGE_SHA256.csv']:
    with (P/'00_release'/name).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['path','bytes','sha256']);w.writeheader();w.writerows(rows)
# Avoid a self-reference: the source package's old manifest is documented by its source hash only.
for r in coverage:
    if r['source_package_path']=='00_release/PACKAGE_SHA256.csv':
        r['published_sha256']='SEE_PUBLICATION_MANIFEST_SEPARATE_FROM_SOURCE_SNAPSHOT';r['byte_identical']=False
with (P/'00_release/SOURCE_COVERAGE.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(coverage[0]));w.writeheader();w.writerows(coverage)
for r in rows:
    if r['path']=='00_release/SOURCE_COVERAGE.csv':r.update(bytes=(P/r['path']).stat().st_size,sha256=sha(P/r['path']))
for name in ['PUBLICATION_MANIFEST.csv','PACKAGE_SHA256.csv']:
    with (P/'00_release'/name).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['path','bytes','sha256']);w.writeheader();w.writerows(rows)
jwrite(A/'PUBLICATION_BUILD.json',{'files':len(rows)+2,'manifest_rows':len(rows),'bytes':sum(r['bytes'] for r in rows)+sum((P/'00_release'/n).stat().st_size for n in ['PUBLICATION_MANIFEST.csv','PACKAGE_SHA256.csv']),'native_files_unchanged':737,'source_package_covered':len(coverage),'source_package_omitted':0,'ordinary_git_blobs':True,'source_compact_unchanged':True,'metadata_changes':[r['source_package_path'] for r in coverage if not r['byte_identical']]})
print((A/'PUBLICATION_BUILD.json').read_text(encoding='utf-8'))
