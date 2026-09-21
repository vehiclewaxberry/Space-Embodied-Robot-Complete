"""Read-only, standard-library V31 mechanical intake; writes only beside this script.

No CAD/COM, simulation, material assignment, geometry regeneration or hardware command.
Source URDF inertials are a separate digital model, never apportioned from 4.5 kg.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET
from collections import Counter

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in HERE.parents if (p / 'PROJECT_MAP.md').is_file())
IMPL = HERE.parent.parent
RUNS = IMPL.parent.parent
NATIVE = RUNS / 'wp09_interfaces_20260907_1525/system_completion'
PLAN = IMPL / 'coupled_closure/SPREADER_INSTANCE_PLAN_V28.json'
PACKET = IMPL / 'mechanical/PARAMETER_PACKET.json'
BINDING = IMPL / 'mechanical/B601_DM_KINEMATIC_BINDING.json'
URDF = IMPL / 'sources/official_matched_dm.urdf'
WP03 = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1/design_parameters.json'
LOCKS = {}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def register(path, role, expected=None):
    path = Path(path).resolve()
    key = str(path)
    if key not in LOCKS:
        LOCKS[key] = {'path': key, 'bytes': path.stat().st_size if path.is_file() else None,
                      'sha256': sha(path) if path.is_file() else None, 'roles': [],
                      'expected_sha256': []}
    item = LOCKS[key]
    if role not in item['roles']:
        item['roles'].append(role)
    if expected and expected not in item['expected_sha256']:
        item['expected_sha256'].append(expected)
    item['matches_all_expected'] = bool(item['sha256']) and all(
        item['sha256'] == e for e in item['expected_sha256'])
    return item


def read(path, role='INPUT_JSON'):
    register(path, role)
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(name, obj):
    (HERE / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def write_csv(name, rows):
    with (HERE / name).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        for row in rows:
            w.writerow({k: json.dumps(v, ensure_ascii=False, separators=(',', ':'))
                        if isinstance(v, (list, dict)) else v for k, v in row.items()})


def quantity(estimate, unit, evidence, source, scope, frame=None, reference_point=None):
    return {'estimate': estimate, 'unit': unit, 'evidence_class': evidence,
            'source_pointer': source, 'scope': scope, 'frame': frame,
            'reference_point': reference_point, 'standard_uncertainty': None,
            'distribution': None, 'degrees_of_freedom': None, 'correlation_group': None,
            'uncertainty_status': 'NOT_CHARACTERIZED_NOT_ZERO'}


def det3(a):
    return (a[0][0]*(a[1][1]*a[2][2]-a[1][2]*a[2][1])
            -a[0][1]*(a[1][0]*a[2][2]-a[1][2]*a[2][0])
            +a[0][2]*(a[1][0]*a[2][1]-a[1][1]*a[2][0]))


def positive_definite(a):
    return (a[0][0] > 0 and a[0][0]*a[1][1]-a[0][1]*a[1][0] > 0 and det3(a) > 0)


def valid_rotation(a):
    return (abs(det3(a)-1) < 1e-8 and
            max(abs(sum(a[k][i]*a[k][j] for k in range(3))-(1 if i == j else 0))
                for i in range(3) for j in range(3)) < 1e-8)


def T_to_m(t):
    o = copy.deepcopy(t)
    for i in range(3):
        o[i][3] *= 0.001
    return o


def same_matrix(a, b):
    return max(abs(a[i][j]-b[i][j]) for i in range(4) for j in range(4)) < 1e-8


def require_whole_system_mass(card):
    whole = card['whole_system']
    if not whole['ready'] or whole['mass_kg'] is None:
        raise ValueError('WHOLE_SYSTEM_MASS_UNKNOWN: subset or legacy totals cannot substitute')
    return whole['mass_kg']


def require_whole_wing_mass(card):
    if card['solar_leaf_budget']['whole_wing_mass_kg'] is None:
        raise ValueError('WHOLE_WING_MASS_UNKNOWN: six leaf budgets exclude complete hinge/frame/wiring systems')
    return card['solar_leaf_budget']['whole_wing_mass_kg']


def validate_installed_candidate(card):
    if not card['whole_system']['current_plan_native_installed']:
        raise ValueError('CURRENT_PLAN_NOT_NATIVE_INSTALLED: do not sum uninstalled V30 local module into host')


def validate_base_frame(T_S_base_m, frame='S', unit='m'):
    if frame != 'S' or unit != 'm':
        raise ValueError('FRAME_OR_UNIT_MISMATCH')
    expected = [[1.,0.,0.,.09],[0.,1.,0.,0.],[0.,0.,1.,.12515],[0.,0.,0.,1.]]
    if not same_matrix(T_S_base_m, expected):
        raise ValueError('BASE_INSTALLATION_MISMATCH: top mounted link origin is not bearing surface or legacy mount')


def prevent_parent_child_double_count(selection):
    owners = {r['owner'] for r in selection if r['level'] == 'owner'}
    if any(r['owner'] in owners and r['level'] == 'child' for r in selection):
        raise ValueError('PARENT_CHILD_DOUBLE_COUNT')


def parse_arm(binding):
    register(URDF, 'PINNED_VENDOR_DM_URDF_SOURCE', binding['sources'][0]['sha256'])
    result = []
    xml = ET.parse(URDF).getroot()
    for node in xml.findall('link'):
        name = node.attrib['name']
        inert = node.find('inertial')
        if inert is None:
            continue
        ptr = str(URDF) + '#link/' + name + '/inertial'
        origin = inert.find('origin')
        com = [float(v) for v in origin.attrib.get('xyz', '0 0 0').split()]
        rpy = [float(v) for v in origin.attrib.get('rpy', '0 0 0').split()]
        m = float(inert.find('mass').attrib['value'])
        ii = {k: float(v) for k, v in inert.find('inertia').attrib.items()}
        I = [[ii['ixx'],ii['ixy'],ii['ixz']], [ii['ixy'],ii['iyy'],ii['iyz']], [ii['ixz'],ii['iyz'],ii['izz']]]
        # Existing source inertial origins have zero orientation. Refuse silent tensor-frame reuse otherwise.
        if any(v != 0 for v in rpy):
            raise ValueError('Nonzero inertial orientation requires explicit tensor rotation')
        covariance = [[(sum(I[k][k] for k in range(3))/2 if i == j else 0)-I[i][j]
                       for j in range(3)] for i in range(3)]
        result.append({'link_id': name, 'instance_id': binding['link_instance_map'][name],
                       'parent_joint': next((j['name'] for j in binding['joints'] if j['child_link']==name), 'S_to_base_fixed_installation'),
                       'mass': quantity(m,'kg','SOURCE_DIGITAL',ptr,'PINNED_VENDOR_DIGITAL_LINK_NOT_AS_BUILT'),
                       'mass_kg': m,
                       'COM_link_m': com,
                       'inertia_COM_link_kg_m2': I,
                       'center_of_mass': quantity(com,'m','SOURCE_DIGITAL',ptr,'PINNED_VENDOR_DIGITAL_LINK',name,'link_origin'),
                       'inertia': quantity(I,'kg*m^2','SOURCE_DIGITAL',ptr,'PINNED_VENDOR_DIGITAL_LINK',name,'link_COM'),
                       'inertial_origin_rpy_rad': rpy, 'tensor_positive_definite': positive_definite(I),
                       'tensor_triangle_inequality_satisfied': positive_definite(covariance),
                       'evidence_class': 'SOURCE_DIGITAL', 'as_built_mass_kg': None,
                       'validated_current_hardware': False})
    return result


def main():
    HERE.mkdir(parents=True, exist_ok=True)
    register(Path(__file__), 'REPRODUCIBLE_BUILDER')
    packet = read(PACKET)
    binding = read(BINDING)
    plan = read(PLAN)
    wp03 = read(WP03)
    native = read(NATIVE / 'results/NATIVE_DELTA_DELIVERY.json')
    current = read(IMPL / 'coupled_closure/CANDIDATE_V30.json')
    v30 = read(IMPL / 'coupled_closure/DELIVERY_STATUS_V30.json')
    spreader = read(IMPL / 'coupled_closure/SPREADER_GEOMETRY_V28.json')
    old = {r['id']: r for r in packet['instances']}
    whole_arm_owner = next(o for o in packet['owners'] if o['owner'] == 'B601_DM_COMPLETE')
    whole_arm_ref = whole_arm_owner['module_reference_mass']['estimate']
    arm = parse_arm(binding)
    arm_by_id = {r['instance_id']: r for r in arm}
    validate_base_frame(binding['base_installation_T'])
    assert wp03['frame_S']['origin'] == 'bus_geometric_center'
    assert abs(wp03['bus_mm'][2]/2 + 12 - binding['base_installation_T'][2][3]*1000) < 1e-10
    native_files = {p['file']: p for p in native['package_files']}
    native_observed = {}
    for state, path in native['assembly_paths'].items():
        rec = register(path, 'NATIVE_TOPLEVEL_ONLY_NOT_OPENED', native_files[Path(path).name]['sha256'])
        native_observed[state] = {'path': path, 'sha256': rec['sha256'], 'matches_delivery_receipt': rec['matches_all_expected']}
    current_plan_ids = {r['id'] for r in plan['states']['service']['rows']}
    native_ids = set(old)
    removed = sorted(native_ids-current_plan_ids)
    added = sorted(current_plan_ids-native_ids)
    changed = []
    rows = []
    poses = []
    for row in plan['states']['service']['rows']:
        ident = row['id']
        src = register(row['step_path'], 'PLAN_LEAF_SOURCE_GEOMETRY_HASH_ONLY', row['source_sha256'])
        prev = old.get(ident)
        source_same = bool(prev and prev['geometry_by_state']['service']['source_step']['sha256'] == row['source_sha256'])
        if prev and not source_same:
            changed.append(ident)
        status = 'UNCHANGED_SOURCE_FROM_873' if source_same else 'SAME_ID_CHANGED_SOURCE' if prev else 'NEW_INSTANCE_SINCE_873'
        source_group = prev['geometry_by_state']['service']['source_parent_assembly_label'] if prev else None
        owner = prev['responsibility_owner'] if prev else None
        mass = None
        evidence = 'UNKNOWN'
        mass_scope = 'UNKNOWN_CURRENT_INSTANCE'
        pointer = None
        parent_reference = None
        if prev:
            par = next((o for o in packet['owners'] if o['owner'] == owner), None)
            parent_reference = par['module_reference_mass']['estimate'] if par else None
        if source_same and src['matches_all_expected'] and prev['mass']['estimate'] is not None:
            mass = prev['mass']['estimate']
            evidence = 'CAD_ESTIMATE' if prev['mass']['identity'] == 'CANDIDATE_GEOMETRY_MATERIAL_MODEL' else 'SOURCE_DIGITAL'
            mass_scope = prev['mass']['identity']
            pointer = str(PACKET) + '#instances/' + str(packet['instances'].index(prev)) + '/mass'
        if ident == 'radiator_spreader' and row['source_sha256'] == spreader['new_step_sha256'] and src['matches_all_expected']:
            mass = spreader['new_mass_kg']
            evidence = 'CAD_ESTIMATE'
            mass_scope = 'V28_GEOMETRY_TIMES_2700_KG_M3_CANDIDATE'
            pointer = str(IMPL / 'coupled_closure/SPREADER_GEOMETRY_V28.json') + '#new_mass_kg'
        link = arm_by_id.get(ident) if source_same and src['matches_all_expected'] else None
        if link:
            mass = link['mass_kg']
            evidence = 'SOURCE_DIGITAL'
            mass_scope = 'PINNED_DM_URDF_DIGITAL_LINK_ALTERNATIVE_TO_WHOLE_ARM_REFERENCE'
            pointer = link['mass']['source_pointer']
        budget = prev['legacy_planning_budget']['estimate'] if prev else None
        rows.append({'instance_id': ident, 'baseline_relation': status, 'responsibility_owner': owner,
                     'source_container_label': source_group, 'container_is_dynamic_body': False,
                     'dynamic_link_id': link['link_id'] if link else None,
                     'rigid_group_id': 'arm/' + link['link_id'] if link else None,
                     'rigid_group_mapping_status': 'SOURCE_NOMINAL_KINEMATIC_LINK' if link else 'UNKNOWN_NOT_INFERRED_FROM_STATIC_GROUP',
                     'dynamic_parent_joint': link['parent_joint'] if link else None,
                     'source_URDF_link_record_complete': bool(link),
                     'whole_body_ownership_complete': False,
                     'source_frame': link['link_id'] if link else 'STEP_LOCAL:' + ident,
                     'source_step_path': row['step_path'], 'source_sha256': row['source_sha256'],
                     'source_hash_verified': src['matches_all_expected'],
                     'representation_role': row['representation_role'], 'is_ground_only': row['is_ground_only'],
                     'native_current_whole_plan_installed': False,
                     'mass_evidence_class': evidence, 'mass_kg': mass,
                     'mass_scope': mass_scope, 'mass_source_pointer': pointer,
                     'COM_local_m': link['COM_link_m'] if link else None,
                     'inertia_COM_local_kg_m2': link['inertia_COM_link_kg_m2'] if link else None,
                     'inertia_expressed_in': link['link_id'] if link else None,
                     'inertia_reference_point': 'link_COM' if link else None,
                     'legacy_budget_mass_kg': budget, 'legacy_budget_evidence_class': 'BUDGET' if budget is not None else 'UNKNOWN',
                     'budget_is_additive_to_mass': False,
                     'owner_reference_mass_kg': parent_reference, 'owner_reference_additive_to_children': False,
                     'as_built_mass_kg': None, 'uncertainty_status': 'UNKNOWN_NOT_ZERO'})
    for state, state_data in plan['states'].items():
        for row in state_data['rows']:
            rec = register(row['step_path'], 'PLAN_LEAF_SOURCE_GEOMETRY_HASH_ONLY', row['source_sha256'])
            prev = old.get(row['id'])
            same_geom = bool(prev and prev['geometry_by_state'][state]['source_step']['sha256'] == row['source_sha256'])
            t = row['T_S_step']
            poses.append({'state': state, 'instance_id': row['id'], 'T_S_step_m': T_to_m(t),
                          'transform_equation': 'p_S_m = R_S_step * p_step_m + t_S_m',
                          'source_frame': 'STEP_LOCAL:' + row['id'], 'target_frame': 'S', 'translation_unit': 'm',
                          'source_translation_unit': 'mm', 'rotation_valid': valid_rotation(t),
                          'same_geometry_as_873': same_geom,
                          'same_transform_as_873': bool(prev and same_matrix(t, prev['geometry_by_state'][state]['T_local_to_S_source_mm'])),
                          'native_whole_plan_current': False, 'source_hash_verified': rec['matches_all_expected']})
    leaf_ids = [r['id'] for r in packet['instances'] if r['responsibility_owner'] == 'SOLAR_CURRENT_LEAF_LAMINATES']
    leaf_budget = sum(old[i]['legacy_planning_budget']['estimate'] for i in leaf_ids)
    mass_counts = dict(Counter(r['mass_evidence_class'] for r in rows))
    current_cad_mass_subset = sum(r['mass_kg'] for r in rows if r['mass_evidence_class']=='CAD_ESTIMATE')
    source_arm_mass = sum(r['mass_kg'] for r in arm)
    card = {'schema': 'WP10_V31_BODY_PARAMETER_CARD',
            'status': 'SOURCE_BOUND_PARAMETER_INTAKE_PARTIAL_BODY_PHYSICS',
            'consumer_contract': 'Independent evidence channels; do not sum digital, CAD estimate, budget and module references into an asserted full spacecraft mass.',
            'frames': {'world_frame': 'S', 'origin': wp03['frame_S']['origin'],
                       'axes': {k:v for k,v in wp03['frame_S'].items() if k != 'origin'},
                       'positions_unit': 'm', 'inertia_unit': 'kg*m^2', 'column_vectors': True,
                       'body_COM_at_S_origin': False, 'source_pose_translation_unit': 'mm',
                       'matrix_equation': 'p_S = R_S_local p_local + t_S'},
            'b601': {'variant': 'B601_DM', 'base_installation_T_S_base_m': binding['base_installation_T'],
                     'base_link_origin_z_S_m': binding['base_installation_T'][2][3],
                     'bearing_plane_z_S_m': (wp03['bus_mm'][2]/2 + 12 + wp03['nominal_base_bearing_local_z_mm'])/1000,
                     'links': arm, 'joints': binding['joints'],
                     'source_digital_mass_sum_kg': source_arm_mass,
                     'vendor_whole_arm_nominal_reference_kg': whole_arm_ref,
                     'vendor_reference_source': whole_arm_owner['module_reference_mass']['source_pointer'],
                     'digital_vs_vendor_difference_kg': whole_arm_ref-source_arm_mass,
                     'difference_disposition': 'UNRESOLVED_SCOPE_OR_MODEL_DIFFERENCE; no proportional rescaling or guessed ballast',
                     'source_digital_inertials_complete_for_10_links': len(arm)==10,
                     'as_built_complete': False, 'accepted_local_URDF_modified': False},
            'whole_system': {'instance_count_per_state': 974, 'state_count': 3,
                             'mass_kg': None, 'COM_S_m': None, 'inertia_COM_S_kg_m2': None,
                             'ready': False, 'current_plan_native_installed': False,
                             'source_digital_arm_not_current_whole_system': True,
                             'missing': ['non_arm_dynamic_link_mapping','complete_mass_ownership',
                                         'non_arm_COM_and_inertia','installed_candidate_identity','as_built_parameters'],
                             'historical_24kg_or_31kg_totals_may_be_substituted': False},
            'solar_leaf_budget': {'leaf_count': len(leaf_ids), 'instance_ids': leaf_ids,
                                  'mass_kg': leaf_budget, 'per_leaf_mass_kg': 0.18,
                                  'evidence_class': 'BUDGET', 'source': str(PACKET),
                                  'scope': 'SIX_LEAF_LAMINATES_ONLY_NOT_COMPLETE_WINGS',
                                  'whole_wing_mass_kg': None,
                                  'excluded_or_separate': ['hinges','frames','CIC','bondline','release_kits','wiring'],
                                  'source_geometry_dimensions_not_mass_requalification': True},
            'nonadditive_evidence_channels': {'current_CAD_estimate_subset_kg': current_cad_mass_subset,
                                             'source_digital_arm_kg': source_arm_mass,
                                             'vendor_whole_arm_reference_kg': whole_arm_ref,
                                             'six_leaf_budget_kg': leaf_budget,
                                             'total_spacecraft_mass_kg': None},
            'coverage': {'current_instances': len(rows), 'pose_records': len(poses),
                         'dynamic_link_mapped_instances': sum(r['dynamic_link_id'] is not None for r in rows),
                         'dynamic_link_unresolved_instances': sum(r['dynamic_link_id'] is None for r in rows),
                         'mass_evidence_class_counts': mass_counts,
                         'COM_and_inertia_source_digital_links': len(arm), 'measured_instances': 0},
            'files': {'instances': 'INSTANCE_BODY_MAP.csv', 'poses': 'INSTANCE_POSES.csv',
                      'source_lock': 'SOURCE_LOCK.json', 'baseline': 'MECHANICAL_BASELINE.json'},
            'scope': {'CAD_loaded': False,'simulation_run': False,'hardware_commands_sent': False,
                      'whole_design_complete': False,'manufacturing_release': False}}
    baseline = {'schema': 'WP10_V31_MECHANICAL_BASELINE',
                'native_host': {'id':'WP09D_873_FIXED_POSE_NATIVE', 'leaf_instances_each_state':873,
                                'states':native_observed, 'evidence':str(NATIVE/'results/NATIVE_DELTA_DELIVERY.json'),
                                'credit':'SAVED_COLD_REOPEN_AND_RELOCATION_RECEIPT_INHERITED; top file hashes checked now; no CAD opened now',
                                'mate_based_motion':native['mate_based_motion'],
                                'continuous_motion_verified':native['continuous_motion_verified']},
                'current_full_plan': {'id':'WP10_V28_974_SOURCE_PLAN_INHERITED_BY_V30', 'source':str(PLAN),
                                      'sha256':sha(PLAN), 'instances_each_state':974,
                                      'native_assembly_updated':plan['native_SolidWorks_assembly_updated'],
                                      'whole_fit_verified':plan['whole_fit_verified'],
                                      'mass_inertia_requalified':plan['whole_mass_inertia_requalified'],
                                      'delta_from_873':{'retained_same_source_count':len(native_ids & current_plan_ids)-len(changed),
                                                        'same_id_changed_source_count':len(changed),'added_ids':added,
                                                        'removed_ids':removed,'changed_source_ids':changed,
                                                        'equation':'873 - 18 + 119 = 974; 29 retained IDs also change source geometry'}},
                'uninstalled_local_module': {'id':'V30_MAIN_INPUT_LOCAL_MODULE', 'occurrences':v30['occurrences'],
                                             'valid_solids_in_receipt':v30['solids'], 'host_installed':v30['host_installed'],
                                             'full_harness_complete':v30['whole_harness_complete'],
                                             'included_in_974_instance_count':False,
                                             'source':str(IMPL/'coupled_closure/CANDIDATE_V30.json'),
                                             'native_SLDASM':False},
                'WP03_frame_lineage': {'source':str(WP03),'frame_S':wp03['frame_S'],
                                      'bus_mm':wp03['bus_mm'],'base_policy':wp03['base_origin_policy'],
                                      'parking_semantics':wp03['states']['parking']['meaning'],
                                      'parking_is_launch_stowed':False},
                'whole_design_complete':False,'as_built_complete':False}
    write_csv('INSTANCE_BODY_MAP.csv',rows)
    write_csv('INSTANCE_POSES.csv',poses)
    write('BODY_PARAMETER_CARD.json',card)
    write('MECHANICAL_BASELINE.json',baseline)
    write('SOURCE_LOCK.json', {'schema':'WP10_V31_MECHANICAL_SOURCE_LOCK','algorithm':'SHA256',
                             'verification_method':'STREAM_BYTES_ONLY_NO_CAD_LOAD',
                             'files':list(LOCKS.values()),
                             'all_expected_hashes_match':all(v['matches_all_expected'] for v in LOCKS.values())})
    tests = []
    def check(name, cond):
        tests.append({'name':name,'passed':bool(cond)})
    def rejects(name, func):
        try:
            func()
        except ValueError:
            check(name,True)
        else:
            check(name,False)
    check('974_unique_ids_each_of_three_states',all(len(v['rows'])==974 and len({r['id'] for r in v['rows']})==974 for v in plan['states'].values()))
    check('same_hardware_ID_set_all_states',all({r['id'] for r in v['rows']}==current_plan_ids for v in plan['states'].values()))
    check('native_873_minus_removed_plus_added',873-len(removed)+len(added)==974)
    check('same_source_mass_only_or_explicit_V28_or_source_DM',all(r['mass_kg'] is None or r['baseline_relation']=='UNCHANGED_SOURCE_FROM_873' or r['instance_id']=='radiator_spreader' for r in rows))
    check('all_plan_and_reference_hashes_current',all(v['matches_all_expected'] for v in LOCKS.values()))
    check('native_three_top_hashes_match_receipt',all(r['matches_delivery_receipt'] for r in native_observed.values()))
    check('all_pose_rotations_right_handed_orthonormal',all(r['rotation_valid'] for r in poses))
    check('10_source_DM_link_positive_mass',len(arm)==10 and all(r['mass_kg']>0 for r in arm))
    check('source_DM_inertia_physical_tensor_checks',all(r['tensor_positive_definite'] and r['tensor_triangle_inequality_satisfied'] for r in arm))
    check('base_transform_uses_current_top_mount',same_matrix(binding['base_installation_T'],[[1,0,0,.09],[0,1,0,0],[0,0,1,.12515],[0,0,0,1]]))
    check('digital_arm_reference_discrepancy_preserved',abs(source_arm_mass-4.5)>1)
    check('source_digital_no_measured_credit',card['coverage']['measured_instances']==0 and not card['b601']['as_built_complete'])
    check('leaf_mass_budget_not_complete_wing',abs(leaf_budget-1.08)<1e-12 and card['solar_leaf_budget']['whole_wing_mass_kg'] is None)
    check('V30_module_not_added_to974',not baseline['uninstalled_local_module']['included_in_974_instance_count'] and not v30['host_installed'])
    rejects('negative_reject_whole_mass_substitution',lambda:require_whole_system_mass(card))
    bad = copy.deepcopy(card); bad['whole_system']['mass_kg']=31.022864807342987
    rejects('negative_reject_old31kg_in_unready_current_model',lambda:require_whole_system_mass(bad))
    rejects('negative_reject_leaf_budget_as_whole_wing',lambda:require_whole_wing_mass(card))
    rejects('negative_reject_uninstalled_candidate',lambda:validate_installed_candidate(card))
    rejects('negative_reject_mm_as_m',lambda:validate_base_frame([[1,0,0,90],[0,1,0,0],[0,0,1,125.15],[0,0,0,1]]))
    rejects('negative_reject_wrong_frame',lambda:validate_base_frame(binding['base_installation_T'],'legacy_front_frame'))
    rejects('negative_reject_parent_child_double_count',lambda:prevent_parent_child_double_count([{'owner':'B601','level':'owner'},{'owner':'B601','level':'child'}]))
    check('full_body_not_promoted_by_parameter_checks',not card['whole_system']['ready'] and not baseline['whole_design_complete'])
    report = {'schema':'WP10_V31_MECHANICAL_INTAKE_VALIDATION', 'checks':tests,
              'passed':sum(t['passed'] for t in tests),'total':len(tests),
              'result':'PASS' if all(t['passed'] for t in tests) else 'FAIL',
              'credit':'PARAMETER_INTAKE_AND_NEGATIVE_GUARDS_ONLY_NOT_ENGINEERING_OR_SCIENCE_GATE'}
    write('VALIDATION.json',report)
    readme = f'''# V31 机械输入包

已将 873 原生宿主、974 三态源计划和 V30 未安装模块分开登记。当前计划为 `SPREADER_INSTANCE_PLAN_V28.json`，V30 继承该计划。差分为 18 个删除、119 个新增、29 个原 ID 改源；不能将旧质量表整表继承。

`INSTANCE_BODY_MAP.csv` 是 974 个唯一实例的证据表；`INSTANCE_POSES.csv` 是 2922 个三态变换记录。静态装配容器和责任分组不冒充运动连杆。10 个 B601 DM 源连杆已有名义映射，其余 964 个实例的完整动态刚体归属保留 UNKNOWN。

公开匹配 DM URDF 的 10 个源连杆质量、质心和惯量已读入 `BODY_PARAMETER_CARD.json`，数字质量合计 **{source_arm_mass:.9f} kg**；4.5 kg 整臂名义参考独立保留，差 **{4.5-source_arm_mass:.9f} kg** 未解释。不给源质量按比例放大，不新增猜测配重，也不把数字 URDF 认作实测本机。

同源材料模型和 V28 散热板形成 **{current_cad_mass_subset:.9f} kg** 的局部 CAD 估算通道；它不是整机质量。六叶 **1.08 kg** 是叶片预算，不含完整翼组件。整机质量、质心、惯量及非臂物性仍为 null，禁止替换成旧 24 kg 或 31 kg 总数。

坐标采用当前 WP03 的 S：星体几何中心、X 纵向、Y 横向、Z 顶面法向。B601 基准原点是 `[0.09, 0, 0.12515] m`，承载接触面高度为 0.127555 m，两者有意不同。惯量均注明质心参考点与表达坐标；所有不确定度未知量保持 null。

源锁采用流式 SHA256 读取源文档、当前计划 STEP 和三个原生顶层文件，不加载 CAD；检查通过只说明参数、来源、单位与禁止混用规则成立。

复现：`python -B build_mechanical_intake.py`。本目录可独立再生成；上游文件不修改。当前参数检查 **{report['passed']}/{report['total']}**，整机工程合格状态仍未通过。
'''
    (HERE/'README.md').write_text(readme,encoding='utf-8')
    print(json.dumps({'validation':report['result'],'checks':report['passed'],'total':report['total'],
                      'instances':len(rows),'poses':len(poses),'arm_source_mass_kg':source_arm_mass,
                      'mass_classes':mass_counts,'source_locks':len(LOCKS),
                      'source_failures':[r for r in LOCKS.values() if not r['matches_all_expected']]},ensure_ascii=False))
    return 0 if report['result']=='PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
