# -*- coding: utf-8 -*-
# s03: R17 八类拒绝负控（合成夹具，每类证明校验器能检出）+ 正控（基线夹具零违规）
import copy, hashlib, importlib.util, json, os, sys, time

RUN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENG = r'F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/service_robot_wp03_spacecraft_body_r1'
spec = importlib.util.spec_from_file_location('export_parts_and_bom', os.path.join(ENG, 'export_parts_and_bom.py'))
ex = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ex)

T_ROOT = [[1., 0., 0., 90.], [0., 1., 0., 0.], [0., 0., 1., 125.15], [0., 0., 0., 1.]]
Q = {'parking': [0, -30, -60, 40, 0, 0], 'released': [0, -45, -50, 35, 0, 0], 'service': [0, -80, -70, 30, 0, 0]}

def base_rows():
    return [
        {'id': 'struct_panel_a', 'pn': 'WP03-STRUCT-PANEL-A', 'product_role': 'ONBOARD_CANDIDATE',
         'representation_role': 'PHYSICAL_GEOMETRY', 'parent_assembly': 'ROOT_STRUCTURE',
         'mass_source': 'CAD_ESTIMATE', 'mass_owner': 'struct_panel_a', 'mass_kg': 0.5},
        {'id': 'equipment_battery', 'pn': 'BUDGET-EQ-BATT', 'product_role': 'ONBOARD_CANDIDATE',
         'representation_role': 'SIMPLIFIED_PROXY', 'parent_assembly': 'EQUIPMENT_BAY',
         'mass_source': 'BUDGET', 'mass_owner': 'equipment_battery', 'mass_kg': 1.0},
        {'id': 'fastener_candidate_x', 'pn': 'WP01-MT-M4X10-CANDIDATE', 'product_role': 'ONBOARD_CANDIDATE',
         'representation_role': 'SIMPLIFIED_PROXY', 'parent_assembly': 'ROOT_STRUCTURE',
         'mass_source': 'UNKNOWN', 'mass_owner': 'fastener_candidate_x', 'mass_kg': None}]

def base_receipt(state):
    return {'state': state, 'view': 'complete', 'q_deg': Q[state], 'finger_mm': 15.0,
            'T_S_arm_base': T_ROOT, 'source_sha256': ex.sha(ex.HERE / 'spacecraft_model.py'),
            'dependency_sha256': {}, 'instances': base_rows()}

def base_state(state, receipt):
    atoms = [{'id': r['id'], 'mass_owner': r['mass_owner'], 'product_role': r['product_role'],
              'representation_role': r['representation_role'], 'mass_kg': r['mass_kg'],
              'mass_source': r['mass_source']} for r in receipt['instances'] if r['mass_kg']]
    unknown = [{'id': r['id'], 'mass_owner': r['mass_owner'], 'product_role': r['product_role'],
                'representation_role': r['representation_role'], 'mass_source': r['mass_source'],
                'reason': 'MASS_UNKNOWN_NOT_ZERO'} for r in receipt['instances'] if r['mass_kg'] is None]
    groups = {}
    for role in ex.ROLES:
        n = sum(1 for r in receipt['instances'] if r['product_role'] == role)
        groups[role] = {'instance_count': n,
                        'known_mass_kg': sum(r['mass_kg'] for r in receipt['instances'] if r['mass_kg'] and r['product_role'] == role),
                        'mass_by_source_kg': ({'BUDGET': 1.0, 'CAD_ESTIMATE': 0.5} if role == 'ONBOARD_CANDIDATE' else {}),
                        'mass_atoms': atoms if role == 'ONBOARD_CANDIDATE' else [],
                        'unknown_mass_instances': unknown if role == 'ONBOARD_CANDIDATE' else [],
                        'known_mass_missing_properties': []}
    return {'state': state, 'q_deg': Q[state], 'finger_mm': 15.0, 'T_S_arm_base_mm': T_ROOT,
            'mass_owner_values': {'struct_panel_a': 0.5, 'equipment_battery': 1.0},
            'groups': groups, 'zero_contribution_instances': []}

def base_handoff(receipts):
    required = [ex.HERE / 'results' / f'{s}_instances.json' for s in ex.STATES] + [
        ex.URDF, ex.WP01_KIN, ex.HERE / 'dynamics_handoff.py', ex.HERE / 'spacecraft_model.py',
        ex.HERE / 'design_parameters.json', ex.HERE / 'kinematics.py', ex.HERE / 'wing_kinematics.py']
    return {'schema': ex.HANDOFF_SCHEMA,
            'input_sha256': {str(p.resolve()): ex.sha(p) for p in required if p.is_file()},
            'receipt_model_source_checks': [
                {'receipt': str((ex.HERE / 'results' / f'{s}_instances.json').resolve()),
                 'recorded_model_sha256': ex.sha(ex.HERE / 'spacecraft_model.py'),
                 'matches_current_model_source': True} for s in ex.STATES],
            'source_files_unchanged': True,
            'states': [base_state(s, receipts[s]) for s in ex.STATES],
            'cross_state_checks': {'root_transform_max_difference_mm_or_dimensionless': 0.0,
                                   'same_positive_mass_owners': True, 'max_per_owner_mass_difference_kg': 0.0}}

def run_all(handoff, receipts):
    v = ex.validate_handoff_provenance(handoff)
    for s in ex.STATES:
        v += ex.validate_receipt_for_bom(receipts[s], f'{s}_instances.json', s)
    v += ex.cross_validate(handoff, receipts)
    return v

t0 = time.time()
receipts0 = {s: base_receipt(s) for s in ex.STATES}
handoff0 = base_handoff(receipts0)
positive = run_all(handoff0, receipts0)

cases = []
def case(nc, title, mutate, expect, note=''):
    h = copy.deepcopy(handoff0)
    r = copy.deepcopy(receipts0)
    mutate(h, r)
    violations = run_all(h, r)
    hit = sorted({x.split(':')[0] for x in violations if any(e in x for e in expect)})
    cases.append({'nc': nc, 'category': title, 'expected_codes': expect, 'detected_codes': hit,
                  'all_violations': violations, 'detected': bool(hit), 'note': note})

# NC1 旧交接配新 CAD：HANDOFF 记录的必需输入哈希与当前文件不符
def m1(h, r):
    key = str((ex.HERE / 'results' / 'service_instances.json').resolve())
    h['input_sha256'][key] = '0' * 64
case('NC1', '旧交接配新 CAD（stale handoff input hash）', m1, ['HANDOFF_INPUT_HASH_MISMATCH'])

# NC2 同总质量但错源：两 owner 质量互换（合计不变）+ 来源分解互换
def m2(h, r):
    for s in h['states']:
        s['mass_owner_values'] = {'struct_panel_a': 1.0, 'equipment_battery': 0.5}
        s['groups']['ONBOARD_CANDIDATE']['mass_by_source_kg'] = {'BUDGET': 0.5, 'CAD_ESTIMATE': 1.0}
case('NC2', '同总质量但错源（owner 质量/来源分解错配）', m2, ['HANDOFF_OWNER_VALUE_MISMATCH', 'HANDOFF_MASS_BY_SOURCE_MISMATCH'])

# NC3 parking/service 混用：service 状态携带 parking 姿态
def m3(h, r):
    svc = next(s for s in h['states'] if s['state'] == 'service')
    svc['q_deg'] = Q['parking']
case('NC3', 'parking/service 配置混用（姿态/根变换错配）', m3, ['STATE_CONFIG_MISMATCH'])

# NC4 exploded：BOM 来源回执为 exploded 视图 + HANDOFF 混入 exploded 状态
def m4(h, r):
    r['service'] = dict(r['service'], view='exploded')
    h['states'] = h['states'] + [dict(h['states'][0], state='exploded')]
case('NC4', 'exploded 显示视图混入（视图/状态集合拒绝）', m4, ['RECEIPT_VIEW_NOT_COMPLETE', 'HANDOFF_STATE_SET_MISMATCH'])

# NC5 缺/重复 owner
def m5(h, r):
    r['service']['instances'][0] = dict(r['service']['instances'][0], mass_owner='')
    r['parking']['instances'][1] = dict(r['parking']['instances'][1], mass_owner='struct_panel_a')
case('NC5', '缺/重复 mass_owner', m5, ['MISSING_MASS_OWNER', 'DUPLICATE_MASS_OWNER'])

# NC6 UNKNOWN 零填：回执未知质量写 0 + 交接给未分配 owner 分配 0.0
def m6(h, r):
    r['service']['instances'][2] = dict(r['service']['instances'][2], mass_kg=0.0)
    for s in h['states']:
        s['mass_owner_values']['fastener_candidate_x'] = 0.0
case('NC6', 'UNKNOWN 零填（未分配质量写 0 而非 null）', m6, ['UNKNOWN_ZERO_FILL'])

# NC7 GSE 混入随星回执
def m7(h, r):
    gse = dict(r['service']['instances'][0], id='gse_stand_1', product_role='GSE', mass_owner='gse_stand_1')
    r['service']['instances'].append(gse)
    svc = next(s for s in h['states'] if s['state'] == 'service')
    svc['groups']['GSE']['instance_count'] = 1
    svc['groups']['GSE']['mass_atoms'] = [{'id': 'gse_stand_1', 'mass_owner': 'gse_stand_1',
                                           'product_role': 'GSE', 'representation_role': 'PHYSICAL_GEOMETRY',
                                           'mass_kg': 0.5, 'mass_source': 'CAD_ESTIMATE'}]
case('NC7', 'GSE 混入随星 BOM 回执', m7, ['GSE_IN_ONBOARD_RECEIPT'])

# NC8 标准件与父总成双计：设备舱总成预算之外，舱内紧固件再计正质量
def m8(h, r):
    extra = {'id': 'eq_mount_screw_1', 'pn': 'WP01-MT-M4X10', 'product_role': 'ONBOARD_CANDIDATE',
             'representation_role': 'SIMPLIFIED_PROXY', 'parent_assembly': 'EQUIPMENT_BAY',
             'mass_source': 'BUDGET', 'mass_owner': 'eq_mount_screw_1', 'mass_kg': 0.01}
    for s in ex.STATES:
        r[s]['instances'].append(dict(extra))
    for s in h['states']:
        s['mass_owner_values']['eq_mount_screw_1'] = 0.01
        s['groups']['ONBOARD_CANDIDATE']['instance_count'] += 1
        s['groups']['ONBOARD_CANDIDATE']['mass_atoms'].append(
            {'id': 'eq_mount_screw_1', 'mass_owner': 'eq_mount_screw_1', 'product_role': 'ONBOARD_CANDIDATE',
             'representation_role': 'SIMPLIFIED_PROXY', 'mass_kg': 0.01, 'mass_source': 'BUDGET'})
case('NC8', '标准件与父总成双计', m8, ['STANDARD_PART_PARENT_DOUBLE_COUNT'],
     note='翼叶逐件预算与释放/线束总成预算同舱合法共存（正控基线含此结构，不得误判）')

verdict = 'PASS' if not positive and all(c['detected'] for c in cases) else 'FAIL'
result = {'run': 'r17_export_chain_20260919', 'check': 'r17_eight_rejection_categories_negative_controls',
          'positive_control': {'fixture': '合成三态基线（含翼叶式逐件预算+总成预算合法共存结构）',
                               'violations': positive, 'pass': not positive},
          'negative_controls': cases, 'detected_count': sum(c['detected'] for c in cases), 'total': len(cases),
          'verdict': verdict, 'elapsed_s': round(time.time() - t0, 3)}
p = os.path.join(RUN, 'evidence', 'r17_negative_controls.json')
open(p, 'wb').write((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
h = hashlib.sha256(open(p, 'rb').read()).hexdigest()
rel = os.path.relpath(p, RUN).replace('\\', '/')
open(p + '.sha256', 'wb').write((h + '  ' + rel + '\n').encode('utf-8'))
print('verdict', verdict, 'positive_violations', len(positive), 'NC detected', result['detected_count'], '/', len(cases))
for c in cases:
    print(' ', c['nc'], c['category'], '->', c['detected_codes'])
