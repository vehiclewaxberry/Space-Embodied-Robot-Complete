"""Export custom local parts, then write full product BOM from complete receipts.

R17 production fix (2026-09-19, run r17_export_chain_20260919):
Forced order = valid input hashes -> build -> instance receipts -> dynamics
handoff -> handoff validation -> BOM. The BOM writer is fail-closed: it refuses
(stale/missing required input hashes, instance/owner mismatch, config mixup,
exploded view, missing/duplicate owner, UNKNOWN zero-fill, GSE contamination,
standard-part/parent double counting) and restores the previous BOM/INTERFACES
bytes instead of leaving half-updated deliverables. Unallocated masses stay
null (None -> empty CSV cell), never 0. '--bom-only' is a pure read path:
this module imports no CAD modules at top level; the CAD build import is lazy
inside the full-mode branch only.
"""
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINEERING = HERE.parent
STATES = ('parking', 'released', 'service')
ROLES = ('ONBOARD_CANDIDATE', 'GSE', 'TEST_DUMMY', 'UNKNOWN')
HANDOFF = HERE / 'results' / 'DYNAMICS_HANDOFF.json'
HANDOFF_SCHEMA = 'WP03_DYNAMICS_HANDOFF_V1'
URDF = ENGINEERING / 'cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf'
WP01_KIN = ENGINEERING / 'service_robot_wp01_20260905/kinematics.py'
ASSEMBLY_SCOPE_BUDGET_PREFIXES = ('equipment_', 'navigation_camera', 'wing_release_budget_', 'wing_harness_budget_')
FASTENER_TOKENS = ('screw', 'washer', 'bolt', 'nut', '-mt-')
BOM_TARGETS = (HERE / 'BOM.csv', HERE / 'INTERFACES.csv')


class HandoffRejected(Exception):
    def __init__(self, violations):
        self.violations = list(violations)
        super().__init__('R17 handoff/BOM validation rejected: ' + '; '.join(self.violations[:5]))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _recorded(handoff, path):
    return handoff.get('input_sha256', {}).get(str(Path(path).resolve()))


def validate_handoff_provenance(handoff):
    """HANDOFF 来源时序：模式、必需输入哈希、回执-源码绑定、计算期不变性。"""
    v = []
    if handoff.get('schema') != HANDOFF_SCHEMA:
        v.append(f'HANDOFF_SCHEMA_MISMATCH: {handoff.get("schema")!r}')
        return v
    required = [HERE / 'results' / f'{s}_instances.json' for s in STATES] + [
        URDF, WP01_KIN, HERE / 'dynamics_handoff.py', HERE / 'spacecraft_model.py',
        HERE / 'design_parameters.json', HERE / 'kinematics.py', HERE / 'wing_kinematics.py']
    if handoff.get('ground_AIT_views'):
        required.append(HERE / 'results' / 'parking_ground_instances.json')
    record = handoff.get('input_sha256')
    if not isinstance(record, dict):
        return v + ['HANDOFF_INPUT_HASH_RECORD_MISSING: input_sha256 缺失']
    for path in required:
        key = str(Path(path).resolve())
        if key not in record:
            v.append(f'HANDOFF_REQUIRED_INPUT_HASH_MISSING: {key}')
            continue
        if not Path(path).is_file():
            v.append(f'HANDOFF_INPUT_FILE_MISSING: {key}')
            continue
        if sha(path) != record[key]:
            v.append(f'HANDOFF_INPUT_HASH_MISMATCH: {key}（交接生成后输入已变化=旧交接配新 CAD）')
    checks = handoff.get('receipt_model_source_checks')
    if not isinstance(checks, list) or len(checks) != len(STATES):
        v.append('HANDOFF_RECEIPT_MODEL_CHECKS_MISSING_OR_INCOMPLETE')
    else:
        current = sha(HERE / 'spacecraft_model.py')
        for entry in checks:
            if entry.get('matches_current_model_source') is not True or entry.get('recorded_model_sha256') != current:
                v.append(f'HANDOFF_RECEIPT_MODEL_SOURCE_STALE: {entry.get("receipt")}')
    if handoff.get('source_files_unchanged') is not True:
        v.append('HANDOFF_SOURCE_FILES_CHANGED_DURING_COMPUTATION')
    return v


def validate_receipt_for_bom(receipt, name, expect_state):
    """BOM 目标回执逐项校验：身份、视图、角色、owner、UNKNOWN 零填、GSE、双计。"""
    v = []
    if receipt.get('state') != expect_state:
        v.append(f'RECEIPT_STATE_MISMATCH: {name} state={receipt.get("state")!r} expected={expect_state!r}（配置混用）')
    if receipt.get('view') != 'complete':
        v.append(f'RECEIPT_VIEW_NOT_COMPLETE: {name} view={receipt.get("view")!r}（exploded/cutaway/ground 视图不得作 BOM 来源）')
    current = sha(HERE / 'spacecraft_model.py')
    if receipt.get('source_sha256') != current:
        v.append(f'RECEIPT_MODEL_SOURCE_STALE: {name}（回执非现行源码生成）')
    for dep, h in receipt.get('dependency_sha256', {}).items():
        p = HERE / dep
        if not p.is_file() or sha(p) != h:
            v.append(f'RECEIPT_DEPENDENCY_STALE: {name} -> {dep}')
    rows = receipt.get('instances')
    if not isinstance(rows, list) or not rows:
        return v + [f'RECEIPT_INSTANCES_MISSING: {name}']
    ids, owners = set(), {}
    budget_parents = {}
    for row in rows:
        rid = row.get('id')
        if rid in ids:
            v.append(f'DUPLICATE_INSTANCE_ID: {name} {rid}')
        ids.add(rid)
        role = row.get('product_role')
        if role not in ROLES:
            v.append(f'RECEIPT_UNKNOWN_PRODUCT_ROLE: {name} {rid} {role!r}')
        if role in ('GSE', 'TEST_DUMMY'):
            v.append(f'{role}_IN_ONBOARD_RECEIPT: {name} {rid}（GSE/试验件不得混入随星 BOM 回执）')
        mass = row.get('mass_kg')
        owner = row.get('mass_owner')
        if mass is not None and not isinstance(mass, (int, float)):
            v.append(f'RECEIPT_MASS_NOT_NUMERIC: {name} {rid}')
            continue
        if mass is not None and mass > 0 and (not isinstance(owner, str) or not owner.strip()):
            v.append(f'MISSING_MASS_OWNER: {name} {rid}（正质量缺 mass_owner）')
        if isinstance(owner, str) and owner.strip():
            if owner in owners:
                v.append(f'DUPLICATE_MASS_OWNER: {name} {owner}（{owners[owner]} 与 {rid}；缺/重复 owner 拒绝）')
            owners[owner] = rid
        if mass == 0 and row.get('mass_source') in (None, 'UNKNOWN'):
            v.append(f'UNKNOWN_ZERO_FILL: {name} {rid}（未知质量写 0=UNKNOWN 零填，必须保持 null）')
        if mass and str(rid).startswith(ASSEMBLY_SCOPE_BUDGET_PREFIXES):
            budget_parents.setdefault(row.get('parent_assembly'), []).append(rid)
    for row in rows:
        mass = row.get('mass_kg')
        rid = str(row.get('id'))
        parent = row.get('parent_assembly')
        if not mass or parent not in budget_parents or rid.startswith(ASSEMBLY_SCOPE_BUDGET_PREFIXES):
            continue
        # 仅标准件/紧固件判双计：翼叶等逐件预算（BUDGET）与释放/线束总成预算为
        # 分别计量的不同实物（现行合法账），不得误判。
        text = (rid + ' ' + str(row.get('pn', ''))).lower()
        if any(t in text for t in FASTENER_TOKENS):
            v.append(f'STANDARD_PART_PARENT_DOUBLE_COUNT: {name} {rid} 在含总成预算行 {budget_parents[parent]} 的 {parent} 内重复计正质量（标准件与父总成双计）')
    return v


def _handoff_rows(state):
    for role in ROLES:
        group = state['groups'][role]
        for key in ('mass_atoms', 'unknown_mass_instances', 'known_mass_missing_properties'):
            for row in group.get(key, []):
                yield row
    for row in state.get('zero_contribution_instances', []):
        yield row


def cross_validate(handoff, receipts):
    """HANDOFF↔回执逐项核对：状态集合、配置、实例集合、owner/质量/来源/角色。"""
    v = []
    states = handoff.get('states')
    if not isinstance(states, list) or [s.get('state') for s in states] != list(STATES):
        return v + [f'HANDOFF_STATE_SET_MISMATCH: {[s.get("state") for s in states] if isinstance(states, list) else states!r}（须恰为 parking/released/service，exploded 等视图拒绝）']
    for state in states:
        name = state['state']
        receipt = receipts[name]
        if (state.get('q_deg') != receipt.get('q_deg') or state.get('finger_mm') != receipt.get('finger_mm')
                or state.get('T_S_arm_base_mm') != receipt.get('T_S_arm_base')):
            v.append(f'STATE_CONFIG_MISMATCH: {name}（HANDOFF 姿态/根变换与回执不一致=配置混用）')
        hrows = list(_handoff_rows(state))
        hids = [r.get('id') for r in hrows]
        if len(hids) != len(set(hids)):
            v.append(f'HANDOFF_DUPLICATE_INSTANCE_COVERAGE: {name}')
        rids = [r['id'] for r in receipt['instances']]
        if set(hids) != set(rids):
            v.append(f'HANDOFF_INSTANCE_SET_MISMATCH: {name}（交接实例集合≠回执实例集合）')
        hrow = {r.get('id'): r for r in hrows}
        positive = {}
        for row in receipt['instances']:
            hr = hrow.get(row['id'])
            if hr is None:
                continue
            for field in ('mass_owner', 'product_role', 'representation_role'):
                if hr.get(field) != row.get(field):
                    v.append(f'HANDOFF_ROW_FIELD_MISMATCH: {name} {row["id"]} {field}: {hr.get(field)!r} != {row.get(field)!r}')
            if row.get('mass_kg'):
                positive[row['mass_owner']] = float(row['mass_kg'])
        values = state.get('mass_owner_values', {})
        for owner, mass in positive.items():
            if owner not in values or abs(values[owner] - mass) > 1e-12:
                v.append(f'HANDOFF_OWNER_VALUE_MISMATCH: {name} {owner}（同总质量但错源/owner 错配拒绝）')
        for owner, mass in values.items():
            if not isinstance(mass, (int, float)) or mass <= 0:
                v.append(f'HANDOFF_UNKNOWN_ZERO_FILL: {name} {owner}={mass!r}（交接分配 0/非正值=UNKNOWN 零填）')
        # 臂 link 回执 mass_kg=None 属设计语义：其交接质量来自 accepted URDF（SOURCE_DIGITAL），
        # 不算未分配泄漏；其余未分配 owner 进入交接分配值即 UNKNOWN 零填/错配。
        unknown_owners = {r['mass_owner'] for r in receipt['instances']
                          if r.get('mass_kg') is None and r.get('mass_owner') and not r.get('arm_link')}
        leaked = unknown_owners & set(values)
        if leaked:
            v.append(f'HANDOFF_UNKNOWN_ZERO_FILL: {name} 未分配质量 owner 进入交接分配值 {sorted(leaked)[:3]}')
        by_source = {}
        for row in receipt['instances']:
            if row.get('mass_kg') and row.get('product_role') == 'ONBOARD_CANDIDATE':
                key = str(row.get('mass_source'))
                by_source[key] = by_source.get(key, 0.0) + float(row['mass_kg'])
        recorded = state['groups']['ONBOARD_CANDIDATE'].get('mass_by_source_kg', {})
        arm_digital = sum(m for o, m in values.items() if o not in positive)
        expected = dict(by_source)
        if arm_digital:
            expected['SOURCE_DIGITAL'] = expected.get('SOURCE_DIGITAL', 0.0) + arm_digital
        if set(expected) != set(recorded) or any(abs(expected[k] - recorded[k]) > 1e-9 for k in expected):
            v.append(f'HANDOFF_MASS_BY_SOURCE_MISMATCH: {name}（同总质量但错来源分解拒绝）')
        for role in ROLES:
            actual = sum(1 for r in receipt['instances'] if r.get('product_role') == role)
            if state['groups'][role].get('instance_count') != actual:
                v.append(f'HANDOFF_ROLE_COUNT_MISMATCH: {name} {role}')
    cross = handoff.get('cross_state_checks', {})
    per_state_values = [{k: float(x) for k, x in s.get('mass_owner_values', {}).items()} for s in states]
    same_owners = all(set(x) == set(per_state_values[0]) for x in per_state_values)
    max_diff = max((abs(x[k] - per_state_values[0][k]) for x in per_state_values for k in x if k in per_state_values[0]), default=0.0)
    if not same_owners or max_diff > 1e-9 or cross.get('same_positive_mass_owners') is not True:
        v.append('HANDOFF_CROSS_STATE_OWNER_MISMATCH（跨状态 owner/质量不一致，须显式配置差异处置）')
    if cross.get('root_transform_max_difference_mm_or_dimensionless', 0) > 1e-10:
        v.append('HANDOFF_CROSS_STATE_ROOT_TRANSFORM_CHANGED')
    return v


def _restore(targets_backup):
    for p, data in targets_backup.items():
        if data is None:
            if p.is_file():
                p.unlink()
        else:
            p.write_bytes(data)


def main():
    bom_only = '--bom-only' in sys.argv
    backup = {p: (p.read_bytes() if p.is_file() else None) for p in BOM_TARGETS}
    try:
        if not bom_only:
            from spacecraft_model import build  # lazy CAD import; --bom-only 永不触达
            build('service', include_arm=False, write_parts=True)
            subprocess.run([sys.executable, str(HERE / 'dynamics_handoff.py')], check=True, cwd=str(HERE))
        receipt_path = HERE / 'results' / 'service_instances.json'
        if not receipt_path.is_file():
            raise HandoffRejected(['RECEIPT_MISSING: results/service_instances.json（完整装配回执缺失）'])
        if not HANDOFF.is_file():
            raise HandoffRejected(['HANDOFF_MISSING: results/DYNAMICS_HANDOFF.json；BOM 须在动力学交接之后导出，缺失即拒绝（fail-closed）'])
        handoff = json.loads(HANDOFF.read_text(encoding='utf-8'))
        receipts = {}
        for state in STATES:
            p = HERE / 'results' / f'{state}_instances.json'
            if not p.is_file():
                raise HandoffRejected([f'RECEIPT_MISSING: results/{state}_instances.json'])
            receipts[state] = json.loads(p.read_text(encoding='utf-8'))
        violations = validate_handoff_provenance(handoff)
        for state in STATES:
            violations += validate_receipt_for_bom(receipts[state], f'{state}_instances.json', state)
        violations += cross_validate(handoff, receipts)
        if violations:
            raise HandoffRejected(violations)
        receipt = receipts['service']
        service_state = next(x for x in handoff['states'] if x['state'] == 'service')
        values = service_state['mass_owner_values']
        for row in receipt['instances']:
            row['allocated_dynamics_mass_kg'] = values.get(row['mass_owner'])  # 未分配保持 None，绝不写 0
            row['allocated_dynamics_mass_source'] = 'SOURCE_DIGITAL' if row.get('arm_link') else row['mass_source']
            row['allocated_mass_reference'] = 'results/DYNAMICS_HANDOFF.json'
        total = sum(v for v in (row['allocated_dynamics_mass_kg'] for row in receipt['instances']) if v is not None)
        if abs(total - service_state['groups']['ONBOARD_CANDIDATE']['known_mass_kg']) > 1e-10:
            raise HandoffRejected(['BOM_ALLOCATED_MASS_TOTAL_MISMATCH: 分配合计≠交接随星已知质量'])
        cols = ['id', 'pn', 'product_role', 'representation_role', 'qualification_status', 'parent_assembly',
                'mount_interface', 'mass_source', 'mass_owner', 'mass_kg', 'mass_basis', 'source_revision',
                'allocated_dynamics_mass_kg', 'allocated_dynamics_mass_source', 'allocated_mass_reference']
        with (HERE / 'BOM.csv').open('w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
            w.writeheader()
            w.writerows(receipt['instances'])
        with (HERE / 'INTERFACES.csv').open('w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(receipt['interfaces'][0]))
            w.writeheader()
            w.writerows(receipt['interfaces'])
        print(json.dumps({'verdict': 'PASS', 'mode': 'bom-only' if bom_only else 'full',
                          'order': 'valid-input-hashes -> build -> receipts -> dynamics_handoff -> handoff-validation -> BOM',
                          'instances': len(receipt['instances']),
                          'allocated_positive': sum(1 for r in receipt['instances'] if r['allocated_dynamics_mass_kg'] is not None),
                          'unallocated_null': sum(1 for r in receipt['instances'] if r['allocated_dynamics_mass_kg'] is None),
                          'handoff_sha256': sha(HANDOFF), 'bom_sha256': sha(HERE / 'BOM.csv'),
                          'interfaces_sha256': sha(HERE / 'INTERFACES.csv')}, ensure_ascii=False, indent=2))
    except Exception:
        _restore(backup)  # fail-closed：不留下半更新交付物
        raise


if __name__ == '__main__':
    try:
        main()
    except HandoffRejected as exc:
        print(json.dumps({'verdict': 'REJECTED_FAIL_CLOSED', 'violations': exc.violations,
                          'bom_interfaces_restored': True}, ensure_ascii=False, indent=2))
        sys.exit(2)
