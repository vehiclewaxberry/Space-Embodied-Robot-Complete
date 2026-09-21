"""Publish V21 local working result with fresh source, serial jobs, BOM and image."""
from pathlib import Path
import json,hashlib,csv,datetime,urllib.parse
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def read(p):return json.loads((A/p).read_text())
def bound(p,key='inputs'):
 v=read(p);assert all(sha(f)==h for f,h in v[key].items()),'Stale input: '+p;return v
plan=bound('mechanical/CAP_HARNESS_RETAINED_PLAN_V21.json')
exact=bound('results/CAP_RETENTION_EXACT_V21.json');assert exact['passed']
calc=bound('results/CAP_RETENTION_ANALYTIC_V21.json')
bom=bound('results/CAP_RETENTION_BOM_CHECK_V21.json','input_hashes');assert sha(bom['output'])==bom['output_sha256']
for phase in ['LOWER','PLUS','MINUS','ASSEMBLY']:
 r=bound(f'results/CAP_RETENTION_GENERATION_{phase}_V21.json');assert sha(r['output'])==r['output_sha256']
cad=read('results/CAP_RETENTION_CAD_REVIEW_V21.json');assert cad['validate']['ok'] and cad['validate']['failureCount']==0 and sha(cad['target'])==cad['target_sha256']
shot=read('results/CAP_RETENTION_SNAPSHOT_V21.json');assert shot['ok'] and sha(shot['published_image'])==shot['published_sha256'] and sha(shot['target'])==shot['target_sha256']
visual=read('results/CAP_RETENTION_VISUAL_REVIEW_V21.json');assert visual['actual_image_viewed'] and sha(visual['image'])==visual['image_sha256']
erc=bound('results/SYSTEM_ERC_CHECK_V20.json');assert erc['passed'] and erc['errors']==erc['warnings']==0
drc=bound('results/CAP_PTH_SOURCE_CHECK_V20.json');assert drc['passed']
released=['README.md','REVIEW.html','SYSTEM_CLOSURE_MATRIX.csv','results/DELIVERY_DECISION.json']
assert all((A/f).read_bytes()==(A/'history/20260909_V18_before_cap_harness'/f).read_bytes() for f in released)
original=list(csv.DictReader((A/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig')));assert len(original)==37
tags=['cap21_lower_p01','cap21_lower_p02','cap21_plus_p01','cap21_minus_p01','cap21_exact_p01','cap21_assembly_p01','cap21_review_p01','cap21_shot_p01']
serial=[]
for tag in tags:
 f=f'logs/CAP19_SERIAL_{tag}.json';v=read(f);assert v['returncode']==0 and v['workspace_mutex_held']
 resource=read(f'results/CAP_HARNESS_RESOURCE_{tag}_V19.json');assert resource['attempts'][-1]['status']=='COMPLETED'
 gf='logs/'+resource['attempts'][-1]['name']+'.run.json';g=read(gf);assert g['status']=='COMPLETED' and g['returncode']==0
 serial.append(dict(path=f,sha256=sha(f),start=v['started_local'],finish=v['finished_local'],guard=gf,guard_sha256=sha(gf),available_start_MiB=g['available_start_mib'],max_child_tree_MiB=max(x['child_tree_rss_mib'] for x in g['samples'])))
for x,y in zip(serial,serial[1:]):assert datetime.datetime.fromisoformat(x['finish'])<=datetime.datetime.fromisoformat(y['start'])
files=['mechanical/CAP_HARNESS_RETAINED_PLAN_V21.json','results/CAP_RETENTION_EXACT_V21.json','results/CAP_RETENTION_ANALYTIC_V21.json','results/CAP_RETENTION_BOM_CHECK_V21.json',bom['output'],'results/CAP_RETENTION_CAD_REVIEW_V21.json','results/CAP_RETENTION_SNAPSHOT_V21.json','results/CAP_RETENTION_VISUAL_REVIEW_V21.json','power/CAP_HARNESS_RETENTION_V21.json','results/SYSTEM_ERC_CHECK_V20.json','results/CAP_PTH_SOURCE_CHECK_V20.json','results/BACKGROUND_MEMORY_CLEANUP_V21.json','tools/write_cap_retention_working_v21.py',*released]
status=dict(schema='WP10_RETENTION_WORKING_STATUS_V21',status='LOCAL_RETENTION_GEOMETRY_AND_INSTALLATION_BOM_INTEGRATED__STRENGTH_KNOT_AND_WHOLE_DESIGN_OPEN',time_local=datetime.datetime.now().astimezone().isoformat(),source_plan='mechanical/CAP_HARNESS_RETAINED_PLAN_V21.json',component_count_by_state={k:len(v['rows']) for k,v in plan['states'].items()},changed_parent_rows=1,added_rows=2,unchanged_parent_rows=971,local_source_instances=27,native_occurrences=cad['validate']['occurrenceCount'],exact_pairs_by_state={k:len(v['exact_pairs']) for k,v in exact['states'].items()},nominal_interfaces_per_state=6,bom_rows=bom['rows'],original_37_rows_unchanged=True,last_sealed_release='V18',ERC_basis='V20 actual report, all current source hashes unchanged; not rerun V21',native_serial_sequence=serial,geometry_verified_in_declared_scope=True,strain_relief_complete=False,structural_qualification=False,whole_design_complete=False,manufacturing_release=False,physical_tests_executed=False,open_items=['PEEK stock allowable, force/load contract, bridge stiffness/creep/fatigue','Installed knot/slip/tape tension, minimum wire OD, tolerances and full tool approach','CHB board surface / PTH solder process','Main-path fault/SOA/fuse coordination, independent STOP and load-side regen dynamics','Full thermal path, battery/PMM and same-revision propulsion interfaces and capability','Whole-body tolerances, structural analysis and continuous motion'],inputs={f:sha(f) for f in files})
review=read('results/CAP_RETENTION_READONLY_REVIEW_V21.json')
assert all(sha(f)==h for f,h in review['reviewed_files'].items()) and all(sha(f)==h for f,h in review['root_verified_files'].items())
status['readonly_review']='Read-only reviewer concerns corrected and 8 counterexamples executed by root; no post-fix independent re-review'
status['inputs']['results/CAP_RETENTION_READONLY_REVIEW_V21.json']=sha('results/CAP_RETENTION_READONLY_REVIEW_V21.json')
(A/'results/CAP_RETENTION_WORKING_STATUS_V21.json').write_text(json.dumps(status,indent=2))
viewer='http://127.0.0.1:3245/'+urllib.parse.quote(A.as_posix(),safe='/:')+'?file=mechanical%2Fcap_harness_retained_assembly_v21.step.py'
md=f"""# WP10 V21 当前线束固定结构工作件

已清理内存并恢复串行工程化。当前是同一候选的局部固定结构增量；整机详细设计仍有开放项，最后封装发布保持 V18。

- 三态各 974 行：保留 V20 父清单的 971 行，替换 C203 下夹环 B，增加两条绑扎带。
- 生成 27 个源实例的局部装配，原生检查 34 个层级实例、0 失败。
- 每态 17 组精确邻件检查通过；六处鞍座／带环／导线名义接触无体积穿透。
- 原下夹环材料移除 0 mm³，新增 747.067937 mm³。新增结构到夹紧螺钉头最小名义间隙 0.559017 mm。
- 33 行 C203 安装 BOM 已覆盖当前板、夹环、两根导线及两段绑扎带，路径和 SHA256 重新绑定。
- 原理图与 PCB 源保持；沿用源哈希一致的 V20 ERC 0 错误／0 警告、C203 DRC 0 违规。V21 没有重跑电气检查。

[交互查看]({viewer}) · [装配 STEP](mechanical/cap_harness_retained_assembly_v21.step) · [固定座 STEP](mechanical/cap_harness_lower_retained_v21.step) · [安装 BOM](mechanical/CAP_HARNESS_BOM_V21.csv) · [当前机器证据](results/CAP_RETENTION_WORKING_STATUS_V21.json)

![当前装配快照](review/CAP_RETENTION_ASSEMBLY_V21.png)

可用直段长约 3.985 mm，通道宽 2.1 mm，对 1.78 mm 最大宽度绑扎带留出 0.32 mm 总名义余量。已将通道底部接触边建为圆角。绑扎带采用 [HellermannTyton LTHT3A4NA 的公开尺寸](https://www.hellermanntyton.com/products/cable-ties-without-serration/ltht3a4na/174-00011)建立安装路径包络；它不是厂家提供的带结实体。每段 150 mm 是项目试制下料余量，不是实测结长或采购数量。

**尚未闭合的工程条件：** 5 N 假设载荷下窄桥的单梁筛查名义应力约 67.6 MPa；材料许用值、真实载荷、蠕变、疲劳与安装张力未确定，不判强度通过。目录 66 N 为带材拉力参数，不能作为带结强度或导线抗拉脱能力。带结包络和一小段螺丝刀轴包络只验证了局部空间，未验证实际结头、完整工具路径或操作手部空间。

主供电故障保护、停止／回生动态、热路径、电池／PMM及推进接口、整机公差与连续动作仍需继续。原 37 行闭环表、873／99 父本及历史 Gate 未因本轮局部检查升级。STEP 为可供 SolidWorks 导入的几何，本轮未生成新的原生 SLDASM。
"""
(A/'WORKING_V21.md').write_text(md,encoding='utf-8')
page=f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>WP10 V21 线束固定结构</title><style>body{{font:17px/1.65 system-ui,"Microsoft YaHei";background:#111d2b;color:#e5edf5;max-width:1080px;margin:36px auto;padding:0 24px}}a{{color:#95d2ff}}img{{max-width:100%;border-radius:12px}}.cards{{display:flex;gap:14px;flex-wrap:wrap}}.card{{padding:20px;background:#20344a;border-radius:10px;flex:1}}strong{{color:#a9e0c5}}.note{{background:#3f3431;padding:16px;border-radius:10px}}</style><h1>C203—CHB 导线固定结构 · V21</h1><p>内存清理达标后，已完成新固定座、两条带环包络及局部装配的串行生成。整机详细设计仍有开放项。</p><div class="cards"><div class="card"><strong>974</strong><br>每态清单行数<br>971 保持＋1 改件＋2 新件</div><div class="card"><strong>17 × 3</strong><br>三态局部精确邻件<br>六处名义接口／态</div><div class="card"><strong>0.559 mm</strong><br>新增结构到夹紧头<br>名义最小间隙</div></div><p><a href="{viewer}">交互查看装配</a> · <a href="mechanical/cap_harness_retained_assembly_v21.step">下载装配 STEP</a> · <a href="mechanical/cap_harness_lower_retained_v21.step">下载固定座 STEP</a> · <a href="mechanical/CAP_HARNESS_BOM_V21.csv">33 行安装 BOM</a></p><img src="review/CAP_RETENTION_ASSEMBLY_V21.png" alt="27源实例的电容与电源模块线束固定结构"><p>当前 STEP 原生检查 34 个层级实例，0 失败。导线、鞍座及带环的局部名义接触已核验；部分零件被遮挡。</p><div class="note">强度与应变释放资格仍开放：5 N 假设载荷下窄桥单梁筛查约 67.6 MPa；缺材料许用值和任务载荷合同。带结、张力、拉脱、公差、完整工具路径均未试验。不可据此制造放行。</div><p>原理图和 PCB 源未变，沿用源哈希一致的 V20 ERC／DRC 结果；本轮未重跑电气检查。停止／回生、整星散热、电池／PMM及推进同修订接口继续保持开放。</p><p><a href="WORKING_V21.md">完整说明</a> · <a href="results/CAP_RETENTION_WORKING_STATUS_V21.json">机器证据</a> · <a href="results/CAP_RETENTION_EXACT_V21.json">精确检查</a> · <a href="results/CAP_RETENTION_ANALYTIC_V21.json">尺寸与梁筛查</a></p><p>最后封装发布仍为 V18，原 37 行状态保持。本轮 STEP 是 SolidWorks 可导入几何。</p></html>"""
(A/'WORKING_V21.html').write_text(page,encoding='utf-8')
print(json.dumps(dict(status=status['status'],viewer_url=viewer,bom_rows=bom['rows'])))
