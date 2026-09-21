"""Seal the bounded R6H delivery only after native and independent reviews pass."""
from pathlib import Path
from datetime import datetime, timezone
import csv
import hashlib
import json

D = Path(__file__).resolve().parents[1]
ROOT = D.parents[1]
POINTER = D.parent / 'SERVICE_STAR_CORE_INSTALLATION_LATEST.json'
REPORT = ROOT / '01_project/competition/核心电气水平安装与推进装配准备_R6H_20260921.md'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def rel(path):
    return Path(path).resolve().relative_to(ROOT).as_posix()

def ref(path):
    return dict(path=rel(path), sha256=sha(path))

def link(label, path):
    return f'[{label}](<{Path(path).as_posix()}>)'

assert not POINTER.exists(), 'Refuse to overwrite an existing current pointer'
assert not (D/'results/FINAL_DELIVERY_STATUS.json').exists(), 'Delivery already sealed'
plan = read(D/'inputs/NATIVE_ASSEMBLY_PLAN.json')
layout = read(D/'inputs/INSTALLATION_LAYOUT.json')
static = read(D/'results/INCREMENT_STATIC_CHECK.json')
native = read(D/'results/NATIVE_HIERARCHICAL_RECHECK_V2.json')
resume = read(D/'results/NATIVE_SERVICE_TOP_RESUME.json')
build = read(D/'results/NATIVE_ASSEMBLY_DELIVERY.json')
top = read(D/'results/EXISTING_TOP_INVENTORY.json')
prep = read(D/'results/PROPULSION_PREPARATION_CHECK.json')
view = read(D/'results/HORIZONTAL_VISUALIZATION.json')
assert static['valid'] and static['horizontal']
assert not static['collisions'] and not static['unknown'] and not static['internal_collisions']
assert plan['source_layout_sha256'] == static['source_layout_sha256'] == sha(D/'inputs/INSTALLATION_LAYOUT.json')
assert native['status'] == 'PASS_HIERARCHICAL_READ_ONLY_NATIVE_RECHECK'
assert native['leaf_count'] == plan['expected_leaf_count'] == 1153
assert native['actual_solid_instances'] == plan['expected_solid_instances'] == 1602
assert native['direct_group_count'] == len(native['groups']) == len(plan['top_rows']) == 15
assert native['documents_saved'] == 0 and not native['whole_assembly_simultaneously_resolved']
assert native['source_plan_sha256'] == sha(D/'inputs/NATIVE_ASSEMBLY_PLAN.json')
assert native['source_top_inventory_sha256'] == sha(D/'results/EXISTING_TOP_INVENTORY.json')
assert native['source_resume_sha256'] == sha(D/'results/NATIVE_SERVICE_TOP_RESUME.json')
assert len(native['leaves']) == len({x['id'] for x in native['leaves']}) == 1153
assert sum(x['actual_solids'] for x in native['leaves']) == 1602
assert resume['status'] == 'PASS_R6H_SERVICE_TOP_RESUMED_AND_COLD_VERIFIED'
assert top['status'] == 'READ_ONLY_INVENTORY_COMPLETE'
assert top['sha256'] == resume['service']['saved']['sha256'] == sha(resume['service']['saved']['path'])
assert build['status'] == 'FAILED_CLOSED' and len(build['parts']) == 27 and len(build['groups']) == 4
assert prep['status'] == 'PASS_SOURCE_BOUND_HORIZONTAL_PREPARATION_ONLY'
assert prep['oem_open_items'] == 9 and prep['work_orders'] == 12
assert view['status'] == 'PASS_VISUAL_REVIEW'
for item in view['outputs']:
    assert sha(item['path']) == item['sha256']

review = {}
expected_review_status = {
    'GEOMETRY_REVIEW.json': 'PASS_WITH_DECLARED_ENGINEERING_HOLDS',
    'BEARING_STACK_REVIEW.json': 'PASS_NOMINAL_CONTACTS_WITH_STRENGTH_HOLD',
    'PROPULSION_PREPARATION_REVIEW.json': 'PREPARATION_PASS_WITH_OEM_HOLDS',
    'ELECTRICAL_SOURCE_PRESERVATION.json': 'PASS_UNCHANGED_R5E_AND_V36',
    'NATIVE_ROUNDTRIP_REVIEW.json': 'PASS_PARTS_GROUPS_TOP_CHAIN_WITH_SCOPE_HOLDS',
    'NATIVE_FINAL_REVIEW.json': 'PASS_SOURCE_LOCKED_HIERARCHICAL_NATIVE_REVIEW',
}
for name, status in expected_review_status.items():
    row = read(D/'results/reviewer'/name)
    assert row['status'] == status, (name, row['status'])
    assert row['checks']['passed'] == row['checks']['total'] > 0 and not row['checks']['failed'], name
    review[name] = dict(**ref(D/'results/reviewer'/name), status=row['status'], checks=row['checks'])
solidwise = read(D/'results/reviewer/SOLIDWISE_CONFIRMATION_REVIEW.json')
assert solidwise['status'] == 'PASS_R6H_INCREMENT_CONFIRMED_SOLID_BY_SOLID', solidwise['status']
assert solidwise['checks']['passed'] == solidwise['checks']['total'] > 0 and not solidwise['checks']['failed']
review['SOLIDWISE_CONFIRMATION_REVIEW.json'] = dict(**ref(D/'results/reviewer/SOLIDWISE_CONFIRMATION_REVIEW.json'), status=solidwise['status'], checks=solidwise['checks'])
five = read(D/'results/reviewer/FIVE_DIMENSION_REVIEW.json')
assert five['status'] == 'DIGITAL_CANDIDATE_REVIEW_COMPLETE_WITH_ENGINEERING_HOLDS' and five['native_final_ready']
assert five['checks']['passed'] == five['checks']['total'] > 0 and not five['checks']['failed']
assert five['source_layout_sha256'] == sha(D/'inputs/INSTALLATION_LAYOUT.json')
assert five['source_plan_sha256'] == sha(D/'inputs/NATIVE_ASSEMBLY_PLAN.json')
review['FIVE_DIMENSION_REVIEW.json'] = dict(**ref(D/'results/reviewer/FIVE_DIMENSION_REVIEW.json'), status=five['status'])

locks = plan['source_native_files'] + [dict(path=p['target'], sha256=p['native_save']['sha256']) for p in build['parts']] + [g['saved'] for g in build['groups']] + [resume['service']['saved']]
locks = list({str(Path(r['path']).resolve()).lower(): r for r in locks}.values())
assert len(locks) == native['locked_files_unchanged']
for item in locks:
    assert sha(item['path']) == item['sha256'], item['path']
with (D/'SOURCE_DEPENDENCIES_SHA256.csv').open('w', encoding='utf-8-sig', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['path', 'sha256', 'inside_R6H'])
    writer.writeheader()
    for item in sorted(locks, key=lambda r: r['path']):
        writer.writerow(dict(path=rel(item['path']), sha256=item['sha256'], inside_R6H=Path(item['path']).is_relative_to(D)))

cad = Path(resume['service']['saved']['path'])
viewer = D/'views/R6H_HORIZONTAL_INSTALLATION_VIEWER.html'
figure = D/'views/R6H_HORIZONTAL_INSTALLATION.png'
install_doc = D/'docs/hardware/HORIZONTAL_INSTALLATION.md'
prop_doc = D/'docs/PROPULSION_ASSEMBLY_HANDOFF.md'
next_dir = D.parent/'SERVICE_STAR_AUX_STOP_INSTALLATION_R7_20260921'
next_pose = read(next_dir/'inputs/AUX_INSTALL_POSE.json')
assert next_pose['tilt_deg'] == 0 and not next_pose['mount_built']
body = f'''# 核心电气水平安装与推进装配准备 R6H

日期：2026-09-21。结论：本轮水平数字安装、原生总装复验和推进接口准备已完成；保留独立审查列出的工程待验项。当前等级为地面工程样机数字候选，整星完整设计、制造、上电和飞行资格均未完成。

## 交付入口

- {link('SolidWorks 服务姿态总装', cad)}
- {link('交互装配查看器（离线 HTML）', viewer)}；本机会话地址为 http://127.0.0.1:8768/R6H_HORIZONTAL_INSTALLATION_VIEWER.html。
- {link('水平安装说明、尺寸和顺序', install_doc)}
- {link('推进设计装配移交', prop_doc)}
- {link('独立五维审查及剩余项', D/'results/reviewer/FIVE_DIMENSION_REVIEW.md')}

原生总装依赖本工作区 R1/R4 等目录中的文件；保持目录结构后用 SolidWorks 2024 打开。尚未制作可脱离本工作区的 Pack and Go 包。零件含导入实体，装配以固定位置表示；不声明原生特征树或配合驱动运动已经完成。

## 本轮已完成

MAIN 主输入板保持水平，板原点 S=[-164,86,11.5] mm，旋转矩阵为 I。采用四点支撑，P60 仅调整一个支点并局部修改支承件；接口板增加传热块和绝缘垫。整星外形未扩展。

| 项目 | 已验证结果 |
|---|---|
| 装配改动 | 新增23个实例、4个几何改件、5个仅改变位姿的既有实例 |
| 原生文件 | 27个新SLDPRT、4个新建/重建子装配、1个服务姿态总装 |
| 装配核对 | 15个直接子装配、1153个叶实例、1602个实体实例；路径、固定状态与变换核对通过 |
| 干涉复核 | 三种固定姿态增量检查及独立逐实体增强复验通过；受检范围无体积穿透或未决布尔 |
| 承压接触 | 34处名义接触确认；不提供强度或预紧合格信用 |
| 材料 | 新增热桥6061 Alloy赋值并冷读回；混合PCBA、垫片及整星材料质量未闭合 |
| 推进准备 | 绑定9个保留对象与1个局部改托盘，整理9项OEM缺口及12项工作单 |

SolidWorks 复验采用顶层冷打开与15个子装配分别冷打开、完全解析的分层方法，组合核对全局变换；不宣称已在一个会话中同时完全解析整个装配。此次只读复验未保存CAD；既有失败与内存中止回执原样保留。所有受锁原生文件哈希一致。

MAIN 有35个位号的分级外形表示，四个元件仍使用6 mm假定高度。1.60 mm板体是总层机械包络，不是Cu/FR4逐层材料模型；原生往返40实体双向形状差为空，但不据此宣称PCBA内部零干涉或质量真值。详见安装说明与独立报告。

## 保留待验项与下一断点

1. **安装和承载**：最近隔柱与旧适配器名义间隙0.50 mm；隔柱2旁保留旧孔，孔间余肉1.072 mm。需公差、孔边承压/净截面/疲劳、预紧、工具及装入路径验证。P60托盘耳台需要带耳台加工件或经验证的连接工艺。
2. **继续AUX/STOP**：既有R7已建立板件与水平位置搜索，AUX当前候选原点为S≈[30.5,31.5,80] mm、平面内转90°，安装支架尚未建成。STOP尚无已接受的水平安装位置。搜索没有证明所有可用位置都不存在，不得直接删掉预留区或宣称必须扩大整星。下一步从R7输入和负结果接续最小改动的支架、走廊与位置复核。
3. **线缆与电热**：安装端口表仅为参考点，尚未完成实际插合点、逐针、电缆下料、应力释放、STOP/AUX实装与Q201热路径。热桥绝缘垫的MPN、导热率、压缩厚度、耐压、接触压力和保持方式待补。
4. **推进装配**：先补OEM同版本CAD/安装孔系和供电/命令接口，再建立喷口位置、方向、最小脉冲、并发限制、质心变化与欠驱动可达性账本；喷口、储箱、管路和羽流没有以假值冻结。

{link('R7 AUX候选位姿与未完成标记', next_dir/'inputs/AUX_INSTALL_POSE.json')}；{link('R7 搜索结果和STOP未找到记录', next_dir/'results/BOARD_POSE_SEARCH.json')}。R7是未完成的后续探索，不包含在本轮已安装计数中。

此前电气选型继续由 SERVICE_STAR_ELECTRICAL_LATEST.json 指向R5E；本轮只新增核心安装指针。R17历史移交、旧R1–R5E文件及科学Gate保持原有含义。撤下的倾斜R6不再作为现行装配入口。

![R6H 实际CAD装配图](<{figure.as_posix()}>)
'''
REPORT.write_text(body, encoding='utf-8')
readme = f'''# R6H 核心电气水平数字安装

本轮已完成水平MAIN、局部P60支承调整、接口板热桥及推进准备的数字候选。整星设计、制造、上电和飞行资格未完成。

主入口：{link('交付报告', REPORT)}。原生文件为 `native/SERVICE_STAR_SERVICE_R6H.SLDASM`；查看图为 `views/R6H_HORIZONTAL_INSTALLATION_VIEWER.html`。

机器状态：`results/FINAL_DELIVERY_STATUS.json`；独立审查：`results/reviewer/FIVE_DIMENSION_REVIEW.md`。最终15组/1153叶/1602实体以分层只读冷打开复验为准，不依赖已失败的整机同时解析尝试。

包内清单 `PACKAGE_SHA256.csv` 的路径相对于项目根；`SOURCE_DEPENDENCIES_SHA256.csv` 包含原生引用及其哈希。R1/R4等外部引用未复制，必须保留本工作区目录结构。本包没有Pack and Go、完整材料质量或运动配合放行信用。

历史失败回执、被拒候选和已撤下R6仅保留来源证据。后续AUX/STOP见R7，尚未计入本版总装。
'''
(D/'README.md').write_text(readme, encoding='utf-8')

evidence_paths = [
    'inputs/INSTALLATION_LAYOUT.json', 'inputs/NATIVE_ASSEMBLY_PLAN.json', 'inputs/MAIN_GEOMETRY_COVERAGE.json',
    'inputs/PROPULSION_ASSEMBLY_PREPARATION.json', 'inputs/PROPULSION_OEM_INPUT_TEMPLATE.json',
    'results/INCREMENT_STATIC_CHECK.json', 'results/NATIVE_ASSEMBLY_DELIVERY.json',
    'results/NATIVE_SERVICE_TOP_RESUME.json', 'results/EXISTING_TOP_INVENTORY.json',
    'results/NATIVE_HIERARCHICAL_RECHECK_V2.json', 'results/PROPULSION_PREPARATION_CHECK.json',
    'results/HORIZONTAL_VISUALIZATION.json', 'docs/INSTALLATION_BOM_DELTA.csv',
    'docs/INSTALLED_PORT_DATUMS.csv', 'docs/PROPULSION_NEXT_WORK_ORDERS.csv',
    'docs/hardware/HORIZONTAL_INSTALLATION.md', 'docs/PROPULSION_ASSEMBLY_HANDOFF.md',
    'SOURCE_DEPENDENCIES_SHA256.csv',
]
status = dict(
    schema='R6H_FINAL_DIGITAL_INSTALLATION_DELIVERY_V1', generated_utc=datetime.now(timezone.utc).isoformat(),
    status='PASS_DIGITAL_HORIZONTAL_INSTALLATION_WITH_ENGINEERING_HOLDS',
    scope='Horizontal MAIN plus local P60 support and interface heat bridge; service native assembly; three discrete-state incremental geometry; propulsion preparation only',
    direct_groups=15, leaf_instances=1153, solid_instances=1602,
    added_leaf_instances=23, geometry_replacements=4, pose_only_reused_instances=5,
    native_parts_created=27, native_groups_created_or_rebuilt=4,
    native_top=ref(cad), native_verification='TOP_PLUS_SEPARATELY_RESOLVED_COLD_GROUPS',
    whole_assembly_simultaneously_resolved=False, native_files_locked=len(locks), native_files_changed_during_recheck=0,
    MAIN_out_of_plane_tilt_deg=0, exterior_changed=False,
    STEP_nominal_collision_scope='Increment only; fixed service/parking/released states; declared proxies and height assumptions',
    bearing_contacts_nominal=34, thermal_bridge_material='6061 Alloy read back from SolidWorks material database',
    whole_material_mass_complete=False, tolerance_strength_tool_motion_qualified=False,
    STOP_installed=False, AUX_installed=False, electrical_connections_completed=False,
    propulsion_OEM_selected=False, propulsion_OEM_open_items=9, propulsion_work_orders=12,
    whole_design_complete=False, procurement_release=False, manufacturing_release=False, ready_to_power=False, flight_ready=False,
    portable_package=False, evidence={s:ref(D/s) for s in evidence_paths}, independent_reviews=review,
    user_report=ref(REPORT), views=[ref(figure),ref(viewer)],
    next_interruption_point=dict(package=rel(next_dir), current_AUX_pose=ref(next_dir/'inputs/AUX_INSTALL_POSE.json'), board_search=ref(next_dir/'results/BOARD_POSE_SEARCH.json'), installed_in_R6H=False),
    historical_failures_preserved=[ref(D/'results'/s) for s in ['NATIVE_ATTEMPT_01_EXPORT_FAILED.json','NATIVE_ASSEMBLY_DELIVERY.json','NATIVE_ASSEMBLY_RECHECK.json','NATIVE_TOP_RESUME.json','NATIVE_HIERARCHICAL_RECHECK.json']],
)
write(D/'results/FINAL_DELIVERY_STATUS.json', status)

manifest_path = D/'PACKAGE_SHA256.csv'
excluded = {'PACKAGE_SHA256.csv', 'PACKAGE_VALIDATION.json'}
rows = []
for path in sorted(D.rglob('*')):
    if not path.is_file() or path.name in excluded or path.suffix.lower() in {'.log','.pyc'}:
        continue
    if any(x in {'_generated_com','__pycache__'} for x in path.parts) or path.name.startswith('~$'):
        continue
    rows.append(dict(path=rel(path), size_bytes=path.stat().st_size, sha256=sha(path)))
rows.append(dict(path=rel(REPORT), size_bytes=REPORT.stat().st_size, sha256=sha(REPORT)))
with manifest_path.open('w', encoding='utf-8-sig', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['path','size_bytes','sha256']);writer.writeheader();writer.writerows(rows)
for row in rows:
    assert sha(ROOT/row['path']) == row['sha256'] and (ROOT/row['path']).stat().st_size == row['size_bytes']
validation = dict(status='PASS_MANIFEST_AND_SOURCE_LOCKS', package_files=len(rows), native_lock_files=len(locks), package_manifest_sha256=sha(manifest_path), exclusions=['manifest self','PACKAGE_VALIDATION.json','*.log','*.pyc','_generated_com/','__pycache__/','SolidWorks ~$ session lockfiles'], base_path=str(ROOT))
write(D/'PACKAGE_VALIDATION.json',validation)
write(POINTER,dict(schema='SERVICE_STAR_CORE_INSTALLATION_POINTER_V1',package=rel(D),status=ref(D/'results/FINAL_DELIVERY_STATUS.json'),manifest=ref(manifest_path),validation=ref(D/'PACKAGE_VALIDATION.json'),user_report=ref(REPORT),scope='R6H horizontal core digital installation only; R5E electrical pointer unchanged; R7 AUX/STOP not installed',ready_to_power=False,flight_ready=False))
print(json.dumps(dict(status=status['status'], manifest_rows=len(rows), native_locks=len(locks), report=str(REPORT), pointer=str(POINTER)),ensure_ascii=False),flush=True)
