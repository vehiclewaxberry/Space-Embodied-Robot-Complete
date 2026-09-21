"""Independent, read-only R6 installation intake. Writes only reviewer evidence.

Run with KiCad's Python and -B. No PCB/SCH/STEP/SolidWorks file is changed.
The output is a source/identity audit, not assembly or energization approval.
"""
from pathlib import Path
import csv
import hashlib
import itertools
import json
import pcbnew

HERE = Path(__file__).resolve()
D = HERE.parents[2]
ROOT = D.parents[1]
E = ROOT / '20_engineering'
R4 = E / 'SERVICE_STAR_INTERNAL_LAYOUT_R4_20260920'
R5 = E / 'SERVICE_STAR_POWER_THERMAL_LAYOUT_R5_20260920'
R5E = E / 'SERVICE_STAR_ELECTRICAL_UPDATE_R5E_20260920'
R2 = E / 'SERVICE_STAR_INTERNAL_HARNESS_ORBIT_R2_20260919'
IMPL = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation'
PCB = IMPL / 'ecad/revisions/v36'
CONTRACT = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/system_completion/propulsion/resume_20260908/PROPULSION_INTERFACE_CONTRACT.json'
OUT = D / 'results/reviewer'
OUT.mkdir(parents=True, exist_ok=True)

locks = {}
checks = []


def rel(p):
    return str(Path(p).resolve().relative_to(ROOT)).replace('\\', '/')


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def lock(p):
    locks[rel(p)] = digest(p)
    return locks[rel(p)]


def read(p):
    lock(p)
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def check(name, value, detail=None):
    checks.append(dict(name=name, passed=bool(value), detail=detail))


native = read(R4 / 'inputs/NATIVE_ASSEMBLY_PLAN.json')
checkpoint = read(R5 / 'INTERRUPTION_CHECKPOINT.json')
constraints = read(R4 / 'inputs/DESIGN_CONSTRAINTS.json')
mount = read(R4 / 'inputs/MOUNT_LAYOUT.json')
ports = read(R4 / 'inputs/INTERFACE_DELTA.json')
order = read(R4 / 'inputs/NEXT_LAYOUT_WORK_ORDER.json')
release = read(R5E / 'results/RELEASE_STATUS.json')
updates = read(R5E / 'inputs/SELECTION_UPDATES.json')
bom = read(R5E / 'bom/ELECTRICAL_SELECTION_BOM_R5E.json')
by_ref = {r['ref']: r for r in bom}
trade = read(IMPL / 'results/propulsion_trade_20260917/PROPULSION_TRADE_MATRIX_20260917.json')
contract = read(CONTRACT)
routes = read(IMPL / 'mechanical/BATTERY_PROPULSION_ROUTING.json')
actuation = read(R2 / 'inputs/ACTUATION_CURRENT.json')
bounds = read(R2 / 'inputs/SOURCE_LOCAL_BOUNDS.json')['bounds_by_path']
lock(R2 / 'docs/PROPULSION_GAP_ACTIONS.csv')
lock(R2 / 'docs/PROPULSION_MODE_MATRIX.csv')
with (R2 / 'docs/PROPULSION_GAP_ACTIONS.csv').open(encoding='utf-8-sig', newline='') as f:
    propulsion_actions = list(csv.DictReader(f))

check('R4_1130_expected_leaves', len(native['expected_leaves']) == 1130)
check('R4_CF1_not_installed', native['CF1_installed'] is False)
check('R5_interrupted_no_installation', checkpoint['native_R5_assembly_created'] is False and checkpoint['layout_static_pass'] is False)
check('R5E_no_functional_or_PCB_change', release['functional_ECAD_changed'] is False and release['PCB_changed'] is False)
for key in ['ready_to_power', 'manufacturing_release', 'procurement_release', 'flight_ready']:
    check('R5E_' + key + '_false', release[key] is False)
for path, expected in release['evidence'].items():
    check('R5E_release_lock:' + path, lock(R5E / path) == expected)

maps = {}
for v in ['V30', 'V36']:
    path = R5 / 'inputs' / (v + '_SOURCE_MAP.json')
    data = read(path)
    check(v + '_map_hash', digest(path) == checkpoint['source_maps'][v]['sha256'])
    check(v + '_source_hash', lock(data['source_path']) == data['source_sha256'])
    for row in data['rows']:
        check(v + '_leaf_hash:' + row['id'], lock(row['step_path']) == row['source_sha256'])
    maps[v] = dict(path=rel(path), component_instances=data['component_instances'], solid_occurrences=data['solid_occurrences'], rows=data['rows'])

board_expected = {
    'MAIN': ('wp10_main_input.kicad_pcb', 'f99b06d58fd37e86c0327ba970048427a7da74c049e5ee405870c4d5df2daaad', 43, 35),
    'STOP': ('wp10_stop_control.kicad_pcb', 'd58b0240e63de229a4d64b3863b4b775a5507f75349d44feb258b0a19d0627e6', 107, 103),
    'AUX': ('wp10_aux_protection.kicad_pcb', 'c1f3419abb29f38dbd0127b62a79d806d64c84ff8ae5568b2bcc63bea12a2241', 32, 26),
}
boards = {}
for domain, (filename, expected_sha, nfp, nsymbols) in board_expected.items():
    path = PCB / filename
    check(domain + '_PCB_hash', lock(path) == expected_sha)
    board = pcbnew.LoadBoard(str(path))
    footprints = []
    for fp in board.GetFootprints():
        refs = fp.GetReference()
        footprints.append(dict(ref=refs, value=fp.GetValue(), footprint=str(fp.GetFPID().GetLibItemName()),
            x_pcb_mm=pcbnew.ToMM(fp.GetPosition().x), y_pcb_mm=pcbnew.ToMM(fp.GetPosition().y),
            declared_model_paths=[m.m_Filename for m in fp.Models()],
            source_symbol_bound=refs in by_ref,
            pad_count=len(list(fp.Pads()))))
    check(domain + '_footprint_count', len(footprints) == nfp)
    symbolic = [f for f in footprints if f['source_symbol_bound']]
    check(domain + '_symbol_count', len(symbolic) == nsymbols)
    edge = board.GetBoardEdgesBoundingBox()
    boards[domain] = dict(path=rel(path), thickness_mm=pcbnew.ToMM(board.GetDesignSettings().GetBoardThickness()),
        copper_layers=board.GetCopperLayerCount(), footprint_count=len(footprints), source_symbol_count=len(symbolic),
        edge_bbox_with_line_width_mm=[pcbnew.ToMM(edge.GetX()), pcbnew.ToMM(edge.GetY()), pcbnew.ToMM(edge.GetWidth()), pcbnew.ToMM(edge.GetHeight())],
        source_symbol_refs_without_declared_model=[f['ref'] for f in symbolic if not f['declared_model_paths']],
        source_symbol_refs_with_declared_model=[f['ref'] for f in symbolic if f['declared_model_paths']],
        footprints=footprints,
        source_bound_R4_leaves=[r['id'] for r in native['expected_leaves'] if filename.split('.')[0] in r.get('step_path', '')])

not_in_boards = [dict(ref=u['ref'], kind=u['kind'], candidate_MPN=by_ref[u['ref']]['candidate_MPN'],
                      selection_status=by_ref[u['ref']]['selection_status'])
                 for u in updates if by_ref[u['ref']]['actual_board'] == 'NOT_IN_THREE_AUDITED_BOARDS']
check('39_update_refs_not_in_three_boards', len(not_in_boards) == 39)
check('U301_supplemental_identity_not_in_three_boards', by_ref['U301']['actual_board'] == 'NOT_IN_THREE_AUDITED_BOARDS')
check('propulsion_9_OEM_gaps', len(trade['oem_icd_missing_fields']) == 9)
check('propulsion_12_next_actions', len(propulsion_actions) == 12)
check('propulsion_selection_not_frozen', trade['selection_frozen'] is False)
check('propulsion_unknown_installation_not_zero', actuation['installed_thruster_count'] is None and actuation['installation_transform'] is None)
check('CPOD_M3_direct_attachment_rejected', contract['mechanical']['generic_M3_direct_attachment'] == 'REJECTED_THREAD_MISMATCH')
check('CPOD_no_complete_pin_binding', contract['electrical']['source_and_load_complete_wiring'] is False)


def world_bb(row):
    local = bounds.get(row['step_path'])
    if local is None:
        return None
    t = row['T_S_local']
    corners = list(itertools.product(*zip(*local)))
    pts = [[sum(t[i][j] * p[j] for j in range(3)) + t[i][3] for i in range(3)] for p in corners]
    return [[min(x[i] for x in pts) for i in range(3)], [max(x[i] for x in pts) for i in range(3)]]


retain_ids = ['MIPS_CRADLE_B', 'MIPS_OEM_MAX_ENVELOPE', 'equipment_adcs_propulsion_allocation',
              'adapter_adcs_propulsion_allocation', 'connector_adcs_propulsion_allocation',
              'thermal_interface_adcs_propulsion_allocation', 'PROP_PWR_ROUTE', 'PROP_DATA_ROUTE',
              'P60_REFERENCE_B', 'P60_TRAY_B']
retained = []
for ident in retain_ids:
    row = next(r for r in native['expected_leaves'] if r['id'] == ident)
    check('retained_source_hash:' + ident, lock(row['step_path']) == row['source_sha256'])
    retained.append(dict(id=ident, representation_role=row['representation_role'],
        source_path=rel(row['step_path']), T_S_local=row['T_S_local'],
        S_frame_AABB_mm=world_bb(row),
        AABB_scope='Source bounding box + R4 transform; conservative search cue, not collision or OEM plume clearance.'))

interface = next(r for r in mount['replacements'] if r['id'] == 'equipment_arm_drive')
tim = next(r for r in mount['replacements'] if r['id'] == 'thermal_interface_arm_drive')
gap = interface['expected_local_bbox_mm']['min_mm'][2] - tim['expected_local_bbox_mm']['max_mm'][2]
check('interface_4p5mm_gap', abs(gap - 4.5) < 1e-12)
check('interface_board_is_unselected_envelope', interface['PCB_MPN'] is None and interface['representation_role'] == 'FUNCTIONAL_ENVELOPE')

before = dict(locks)
for path, expected in before.items():
    check('read_only_preservation:' + path, digest(ROOT / path) == expected)

result = dict(
    schema='R6_INDEPENDENT_INSTALLATION_INTAKE_V1', reviewer='/root/electrical_selection_review',
    phase='SOURCE_AND_INTERFACE_INTAKE_ONLY__R6_ASSEMBLY_NOT_YET_REVIEWED',
    scope='Read-only locked source, candidate population, and propulsion interface review. No CAD/ECAD mutation or hardware command.',
    status='PASS_WITH_ENGINEERING_HOLDS' if all(c['passed'] for c in checks) else 'FAIL_SOURCE_CHECK',
    checks=dict(passed=sum(c['passed'] for c in checks), total=len(checks), failed=[c for c in checks if not c['passed']]),
    checks_detail=checks, source_locks=locks,
    R4=dict(expected_leaves=len(native['expected_leaves']), CF1_installed=False,
            interface_board_role=interface['representation_role'], interface_board_MPN=None,
            interface_thermal_gap_mm=gap, reserved_interface_ports=ports['reserved_ports'],
            heat_bridge_candidate=dict(digital_design_allowed=True, aluminium_block_thickness_mm=4.0,
                insulating_pad_nominal_thickness_mm=0.5, total_nominal_thickness_mm=4.5,
                proposed_contact_stack_z_mm=[[-6.0, -2.0], [-2.0, -1.5]],
                coordinate_assumption='One valid uncompressed stack order, to be checked against final builder geometry and bottom-side copper/components.',
                thermal_conductance_W_per_K=None, dielectric_voltage_rating_V=None,
                pressure_Pa=None, compressed_thickness_mm=None,
                acceptance='Declare supported contact faces and exclusions around four mounts; verify exact solids and zero unintended penetration. Actual thermal/isolation performance remains unqualified, without blocking digital geometry.')),
    R5=dict(status=checkpoint['status'], sources=maps,
            V36_geometry_note='26 leaf solids cover 23 footprint references: C201 contributes one body plus two pins. Only 23 of 35 MAIN symbolic physical components have declared models. This is not a full PCBA.',
            V30_reuse_limit='Carrier and terminal source reference only. Old R202 geometry is not current 0.5 mOhm part. Do not delete pigtails to obtain a false fit; separate then restore routed conductors.'),
    electrical_boards=boards,
    R5E=dict(historical_update_refs_not_in_three_boards=not_in_boards,
             supplemental_uninstalled_identity='U301',
             total_symbol_refs_not_in_three_boards=sum(r['actual_board']=='NOT_IN_THREE_AUDITED_BOARDS' for r in bom),
             not_in_boards_scope='39 is a subset of the 45 updated historical gaps, not the full unplaced schematic count; some rows are boundaries rather than parts.',
             physical_ECO_and_new_midpoint_R305_implemented=False),
    propulsion=dict(trade_source=rel(IMPL/'results/propulsion_trade_20260917/PROPULSION_TRADE_MATRIX_20260917.json'),
        oem_icd_missing_fields=trade['oem_icd_missing_fields'],
        current_engineering_gap_actions=rel(R2/'docs/PROPULSION_GAP_ACTIONS.csv'),
        next_12_engineering_actions=propulsion_actions,
        interface_contract=rel(CONTRACT),
        mechanical_interface=contract['mechanical'], electrical_interface=contract['electrical'],
        retained_CAD_objects=retained, functional_routes=routes['routes'],
        nozzle_locations=None, force_directions=None, plume_keepout_angles=None,
        keepout_requirement='Retain physical allocation, power/data corridors, access and attachment space. OEM plume/contamination/temperature exclusions, target/arm/wing paths and post-capture COM remain unknown; no numeric plume cone is invented.',
        scalar_trade_limit='R1 is a lower thrust threshold only; all-PASS catalogue trade does not establish controllable minimum impulse, applicable installation, or whole-mission budget.'),
    review_recommendations=[
        'Use current PCB holes/pad/component positions; confirm component model identity and body envelope before crediting a populated digital board.',
        'Bind missing MAIN models, Q201 isolation and thermal interface, Kelvin shunt geometry, terminal torque/tool access and all conductors before complete CF1 credit.',
        'A 4.5 mm heat bridge may be modelled as a supported candidate with explicit mating areas; power, allowed PCB contacts, isolation, pressure, material and thermal limits remain HOLD.',
        'STOP and AUX have source-bound ECAD but no identified board-source leaf in R4. A new source-bound STEP export and placement are required for installation credit.',
        'Do not turn the 39 unplaced update refs or supplemental U301 into installed parts by metadata. R305 split requires a functional ECO and a new routed midpoint.',
        'Retain the propulsion ICD unknowns and existing reservation. CPOD 4-40 interface must not receive generic M3 hardware.',
    ],
    manufacturing_release=False, ready_to_power=False, flight_ready=False,
    next_review='Await R6 builder assembly receipt, geometry/source map, contact exceptions, route continuity and native cold-open verification.')
(OUT / 'INSTALLATION_INTAKE_REVIEW.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
lines = [
    '# R6 独立安装与接口输入审查', '',
    '本报告仅审查本轮布局的来源、对象和接口边界；尚未审查 R6 完成装配。可继续数字设计，制造、上电和飞行放行保持 HOLD。', '',
    f"只读检查 {result['checks']['passed']}/{result['checks']['total']}；源锁和完整数据见 `INSTALLATION_INTAKE_REVIEW.json`。本次没有修改旧包、ECAD 或 CAD。", '',
    '## 可进入本轮数字安装的对象', '',
    '- MAIN：可基于 V36 实际 PCB 的元件、孔位和电气身份建立数字装配；R5 导出 26 个叶体只覆盖 23/35 个逻辑物理部件，C201 为本体和两条引脚。缺失模型须补齐并区分库模型、OEM 目录包络和保守占位。',
    '- STOP、AUX：受检 PCB 分别为 90×70×1.6 mm、60×70×1.6 mm，存在原理图/焊盘/网络来源；R4 没有识别到对应 PCB 源路径叶实例。如本轮纳入，仍需单独导出、映射、支撑和三态检查。',
    '- 接口板热桥：允许 4 mm 铝块加 0.5 mm 名义绝缘垫的数字候选。一种堆叠为铝块 z=-6…-2 mm、绝缘垫 z=-2…-1.5 mm，下接现有 TIM 顶面、上接板底；须避开四支柱/螺栓及板底需绝缘的实际区域，受压厚度和公差另算。R4 接口板仍为功能包络，实际热源、热阻、耐压和接触压力为 UNKNOWN；因此只认几何安装信用。',
    '- V30 支架、端子和大件可作有来源参考。当前 R202 为 0.5 mΩ，最大本体高度 3.15 mm；旧 V30 本体高 3.81 mm 不可沿用为当前型号。布置时须保留 Q201、Kelvin 分流器和端子的电气相对关系，并恢复被分离的导线路径。', '',
    '## 未布板更新边界', '',
    '45 项历史更新中，下列 39 项不属于三张已审 PCB：', '',
    ', '.join(r['ref'] for r in not_in_boards) + '。', '',
    '另有 U301 仅恢复了器件型号，仍不属于三板。249 个符号中共 85 个不在三板，其中含模块、边界和待布局电路；不能把 39 理解为整套系统仅剩 39 个物理器件。R305 的 665k+11k 串联及新中点未实施。', '',
    '## 推进预留区与真值来源', '',
    '下表由 R4 `inputs/NATIVE_ASSEMBLY_PLAN.json` 的最终实例变换与 R2 `inputs/SOURCE_LOCAL_BOUNDS.json` 的源包围盒计算；对应 STEP SHA 已逐项复核。坐标为 S 系、单位 mm。包围盒仅供布局筛选，不能代替精确布尔体、装配可达性或 OEM 羽流边界。', '',
    '| 对象 | S 系最小点 → 最大点 | 对象性质 |',
    '|---|---|---|',
]
for r in retained:
    b = r['S_frame_AABB_mm']
    points = 'UNKNOWN' if b is None else f"{[round(v, 4) for v in b[0]]} → {[round(v, 4) for v in b[1]]}"
    lines.append(f"| {r['id']} | {points} | {r['representation_role']} |")
lines += [
    '', '保留旧推进/姿控分配盒、MIPS 预留、支架、端子/数据走廊和工具/拔插空间。它们不是已选 OEM 整机。喷口坐标、受力方向、羽流角、禁喷角和捕后质心均未绑定；不得从盒角或箭头补造这些参数。太阳翼、机械臂、捕获目标、导航视场及敏感热/光学表面的羽流排除域需由后续 ICD 和任务姿态确定。', '',
    '功能线束来源：`implementation/mechanical/BATTERY_PROPULSION_ROUTING.json`。PROP_PWR 起点 [-60,69,45]，末端 [144,48,-65]；PROP_DATA 起点 [45,34,59]，末端 [140,56,-45]。两束 OD6、中心线 R21，水平 y=34/48、z=59，双孔夹具 x65…95/y29…53/z52…66。actual_endpoint_binding=false；无下料长度或 OEM 针脚信用。', '',
    '目录级 CPOD 接口来源：`wp09_interfaces_20260907_1525/system_completion/propulsion/resume_20260908/PROPULSION_INTERFACE_CONTRACT.json`。孔螺纹为 #4-40 UNC-2B，直接 M3 安装已拒收；精确孔数/孔位/深度/扭矩仍 null。目录供电 9–12.6 V，候选 P60 为 12 V，具体供货和浪涌未绑定；推进侧连接器、针号、RS422 极性和机壳屏蔽连接均 null。不能因目录双机 5 W 将所有并发/预热电流视为已知。', '',
    '## 9 项现行 OEM 缺口', '',
    '精确列表来自 `implementation/results/propulsion_trade_20260917/PROPULSION_TRADE_MATRIX_20260917.json` 的 `oem_icd_missing_fields`；同目录 MD 归并成 8 条叙述。选型和任务预算均未闭合。原贸易 R1 只有推力下限，不能把全 PASS 解释为最小冲量、羽流和安装均已适用。', '',
]
lines += [f"{i}. {gap}" for i, gap in enumerate(trade['oem_icd_missing_fields'], 1)]
lines += ['', '## 下一步 12 个工程工作条目', '',
    '逐条继承 R2 `docs/PROPULSION_GAP_ACTIONS.csv`；以下不是新增批准或已完成声明。', '',
    '| ID / 优先级 | 内容 | 输入/动作 | 验收 |', '|---|---|---|---|']
for a in propulsion_actions:
    lines.append(f"| {a['id']} / {a['priority']} | {a['gap']} | {a['required_input_or_action']} | {a['acceptance']} |")
lines += ['', 'R6 完成后独立复核：来源/材料标签、安装变换、三态增量布尔结果、接触白名单、导线连续性、保留区、固有端子/螺钉工具空间、原生冷打开及旧源哈希。完整五维评审随最终装配证据补充，不提前授予整星完成信用。', '']
(OUT / 'INSTALLATION_INTAKE_REVIEW.md').write_text('\n'.join(lines), encoding='utf-8')
print(json.dumps(dict(status=result['status'], checks=result['checks'], unplaced_update_refs=len(not_in_boards), OEM_gaps=len(trade['oem_icd_missing_fields']), output=rel(OUT/'INSTALLATION_INTAKE_REVIEW.json')), ensure_ascii=False))
raise SystemExit(0 if all(c['passed'] for c in checks) else 2)
