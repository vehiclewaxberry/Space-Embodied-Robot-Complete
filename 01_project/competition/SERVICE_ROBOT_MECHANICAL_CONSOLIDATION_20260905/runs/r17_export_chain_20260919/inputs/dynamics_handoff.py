"""WP03 mass-property handoff; reads JSON/XML only, never CAD or a simulator.

Consumes results/{parking,released,service}_instances.json from the assembly
writer. Source geometry/URDF are not changed. Run --self-test for the analytical
parallel-axis test and an independent SciPy/WP01 FK comparison without receipts.
"""
from pathlib import Path
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import math
import sys
import xml.etree.ElementTree as ET

import numpy as np

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ENGINEERING = HERE.parent
URDF = ENGINEERING / 'cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf'
WP01_KIN = ENGINEERING / 'service_robot_wp01_20260905/kinematics.py'
STATES = ('parking', 'released', 'service')
ROLES = ('ONBOARD_CANDIDATE', 'GSE', 'TEST_DUMMY', 'UNKNOWN')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def skew(v):
    x, y, z = np.asarray(v, dtype=float)
    return np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])


def rotation(axis, angle):
    axis = np.asarray(axis, dtype=float)
    length = np.linalg.norm(axis)
    if length <= 0:
        raise ValueError('Joint axis is zero')
    k = skew(axis / length)
    return np.eye(3) + math.sin(angle) * k + (1 - math.cos(angle)) * (k @ k)


def rpy_rotation(rpy):
    roll, pitch, yaw = rpy
    return rotation([0, 0, 1], yaw) @ rotation([0, 1, 0], pitch) @ rotation([1, 0, 0], roll)


def transform(xyz=(0, 0, 0), rpy=(0, 0, 0)):
    result = np.eye(4)
    result[:3, :3] = rpy_rotation(rpy)
    result[:3, 3] = xyz
    return result


def vector_attr(element, name, default='0 0 0'):
    return [float(x) for x in (default if element is None else element.get(name, default)).split()]


def matrix_check(matrix):
    matrix = np.asarray(matrix, dtype=float)
    if matrix.shape != (4, 4) or not np.isfinite(matrix).all():
        raise ValueError('Transform must be a finite 4 by 4 matrix')
    r = matrix[:3, :3]
    if not np.allclose(r.T @ r, np.eye(3), atol=1e-10, rtol=0) or abs(np.linalg.det(r) - 1) > 1e-10:
        raise ValueError('Transform rotation is not a proper rigid rotation')
    if not np.allclose(matrix[3], [0, 0, 0, 1], atol=1e-12, rtol=0):
        raise ValueError('Bad homogeneous transform bottom row')
    return matrix


def inertia_check(inertia):
    inertia = np.asarray(inertia, dtype=float)
    if inertia.shape != (3, 3) or not np.isfinite(inertia).all():
        raise ValueError('Inertia must be a finite 3 by 3 matrix')
    scale = max(float(np.max(np.abs(inertia))), 1e-15)
    symmetry = float(np.max(np.abs(inertia - inertia.T)))
    eigen = np.linalg.eigvalsh((inertia + inertia.T) / 2)
    triangle = float(eigen[0] + eigen[1] - eigen[2])
    valid = symmetry <= 1e-9 * scale + 1e-14 and eigen[0] >= -1e-9 * scale - 1e-14 and triangle >= -1e-8 * scale - 1e-14
    return {'symmetric_error_kg_m2': symmetry, 'principal_inertias_kg_m2': eigen.tolist(),
            'positive_definite': bool(eigen[0] > 0), 'physical_triangle_min_kg_m2': triangle,
            'tensor_numerically_physical': bool(valid)}


def source_urdf():
    tree = ET.parse(URDF).getroot()
    bodies = {}
    for link in tree.findall('link'):
        inertial = link.find('inertial')
        if inertial is None:
            raise ValueError('Accepted link has no inertia: ' + link.get('name'))
        origin = inertial.find('origin')
        attrs = inertial.find('inertia').attrib
        xx, xy, xz, yy, yz, zz = [float(attrs[x]) for x in ('ixx', 'ixy', 'ixz', 'iyy', 'iyz', 'izz')]
        tensor = np.array([[xx, xy, xz], [xy, yy, yz], [xz, yz, zz]])
        check = inertia_check(tensor)
        if not check['tensor_numerically_physical'] or not check['positive_definite']:
            raise ValueError('Accepted inertia is invalid: ' + link.get('name'))
        bodies[link.get('name')] = {
            'mass_kg': float(inertial.find('mass').get('value')),
            'center_of_mass_link_m': vector_attr(origin, 'xyz'),
            'inertial_rpy_rad': vector_attr(origin, 'rpy'),
            'inertia_about_COM_inertial_axes_kg_m2': tensor.tolist(),
            'numerical_check': check,
        }
    joints = []
    for joint in tree.findall('joint'):
        origin = joint.find('origin')
        limit = joint.find('limit')
        joints.append({'name': joint.get('name'), 'type': joint.get('type'),
                       'parent': joint.find('parent').get('link'), 'child': joint.find('child').get('link'),
                       'origin_xyz_m': vector_attr(origin, 'xyz'), 'origin_rpy_rad': vector_attr(origin, 'rpy'),
                       'axis_joint': vector_attr(joint.find('axis'), 'xyz', '1 0 0'),
                       'limit': None if limit is None else {k: float(v) for k, v in limit.attrib.items()}})
    roots = set(bodies) - {j['child'] for j in joints}
    if roots != {'base_link'} or len(bodies) != 10:
        raise ValueError('Expected the unchanged ten-link accepted B601 tree')
    return bodies, joints


def fk(joints, q_deg, finger_mm, root_mm):
    root = matrix_check(root_mm).copy()
    root[:3, 3] *= .001
    frames = {'base_link': root}
    q = iter(np.deg2rad(np.asarray(q_deg, dtype=float)))
    n_revolute = 0
    limits = []
    for joint in joints:
        origin = transform(joint['origin_xyz_m'], joint['origin_rpy_rad'])
        motion = np.eye(4)
        value = 0.
        if joint['type'] in ('revolute', 'continuous'):
            value = float(next(q)); n_revolute += 1
            motion[:3, :3] = rotation(joint['axis_joint'], value)
        elif joint['type'] == 'prismatic':
            value = float(finger_mm[joint['name']] if isinstance(finger_mm, dict) else finger_mm) * .001
            motion[:3, 3] = np.asarray(joint['axis_joint']) * value
        elif joint['type'] != 'fixed':
            raise ValueError('Unsupported joint type: ' + joint['type'])
        frames[joint['child']] = frames[joint['parent']] @ origin @ motion
        lim = joint['limit']
        if lim is not None and 'lower' in lim and 'upper' in lim:
            limits.append({'joint': joint['name'], 'value_SI': value,
                           'unit': 'm' if joint['type'] == 'prismatic' else 'rad',
                           'lower': lim['lower'], 'upper': lim['upper'],
                           'within_source_limits': bool(lim['lower'] <= value <= lim['upper'])})
    if n_revolute != len(q_deg):
        raise ValueError('Unexpected revolute coordinate count')
    return frames, limits


def parallel_axis(mass, displacement):
    d = np.asarray(displacement, dtype=float)
    return mass * (float(d @ d) * np.eye(3) - np.outer(d, d))


def aggregate(atoms):
    mass = math.fsum(atom['mass_kg'] for atom in atoms)
    if mass <= 0:
        return {'mass_kg': mass, 'center_of_mass_S_m': None,
                'inertia_about_COM_S_kg_m2': None, 'inertia_about_S_origin_S_kg_m2': None}
    center = sum((a['mass_kg'] * np.asarray(a['center_of_mass_S_m']) for a in atoms), np.zeros(3)) / mass
    origin_i = sum((np.asarray(a['inertia_about_COM_S_kg_m2']) + parallel_axis(a['mass_kg'], a['center_of_mass_S_m']) for a in atoms), np.zeros((3, 3)))
    direct_i = sum((np.asarray(a['inertia_about_COM_S_kg_m2']) + parallel_axis(a['mass_kg'], np.asarray(a['center_of_mass_S_m']) - center) for a in atoms), np.zeros((3, 3)))
    subtraction_i = origin_i - parallel_axis(mass, center)
    return {'mass_kg': mass, 'center_of_mass_S_m': center.tolist(),
            'inertia_about_COM_S_kg_m2': direct_i.tolist(),
            'inertia_about_S_origin_S_kg_m2': origin_i.tolist(),
            'parallel_axis_two_methods_max_error_kg_m2': float(np.max(np.abs(direct_i - subtraction_i))),
            'numerical_tensor_check': inertia_check(direct_i)}


def arm_atom(name, body, frame):
    rotation_s_i = frame[:3, :3] @ rpy_rotation(body['inertial_rpy_rad'])
    center = frame[:3, :3] @ np.asarray(body['center_of_mass_link_m']) + frame[:3, 3]
    inertia = rotation_s_i @ np.asarray(body['inertia_about_COM_inertial_axes_kg_m2']) @ rotation_s_i.T
    return {'arm_link': name, 'mass_kg': body['mass_kg'], 'center_of_mass_S_m': center.tolist(),
            'inertia_about_COM_S_kg_m2': inertia.tolist(), 'T_S_link_m': frame.tolist(),
            'mass_source': 'SOURCE_DIGITAL', 'mass_basis': 'ACCEPTED_URDF_DIGITAL_NOT_MEASURED',
            'inertia_basis': 'ACCEPTED_URDF_COM_TENSOR_ROTATED_TO_S'}


def static_gravity_arm(atoms, root_mm):
    total = aggregate(atoms)
    center = np.asarray(total['center_of_mass_S_m'])
    force = np.array([0., 0., -total['mass_kg'] * 9.80665])
    root = np.asarray(root_mm, dtype=float).copy(); root[:3, 3] *= .001
    points = {'S_origin': np.zeros(3), 'URDF_base_A0': root[:3, 3],
              'nominal_bearing_plane_center': root[:3, :3] @ np.array([0., 0., .002405]) + root[:3, 3]}
    return {'scope': 'CONDITIONAL_GROUND_1G_ONLY_NOT_ALLOWABLE_LAUNCH_LOAD',
            'gravity_S_m_s2': [0., 0., -9.80665], 'force_S_N': force.tolist(),
            'moments': {key: {'reference_point_S_m': point.tolist(), 'moment_S_Nm': np.cross(center - point, force).tolist()} for key, point in points.items()},
            'on_orbit_root_dynamic_load': None,
            'dynamic_load_missing_inputs': ['q_dot', 'q_ddot', 'base_motion', 'external_contact_wrench', 'actuator_and_compliance_models']}


def process_state(data, bodies, joints):
    state = data['state']
    frames, limits = fk(joints, data['q_deg'], data['finger_mm'], data['T_S_arm_base'])
    atoms_by_role = {role: [] for role in ROLES}
    known_mass_by_role = {role: [] for role in ROLES}
    unknown_by_role = {role: [] for role in ROLES}
    missing_by_role = {role: [] for role in ROLES}
    counts = {role: 0 for role in ROLES}
    claimed = {}; arm_seen = set(); ids = set(); comparisons = []; budget_checks = []; zero = []; geometry_flags = []
    for row in data['instances']:
        instance = row['id']
        if instance in ids:
            raise ValueError(f'{state}: duplicate instance id {instance}')
        ids.add(instance)
        role = row['product_role']
        if role not in ROLES:
            raise ValueError(f'{state}: unknown product_role {role}')
        counts[role] += 1
        owner = row.get('mass_owner')
        common = {key: row.get(key) for key in ('id', 'pn', 'product_role', 'representation_role', 'parent_assembly', 'mount_interface', 'mass_owner', 'source_revision', 'evidence_scope')}
        name = row.get('arm_link')
        if name is not None:
            if name not in bodies or name in arm_seen or role != 'ONBOARD_CANDIDATE':
                raise ValueError(f'{state}: invalid/duplicated/non-onboard arm_link {name}')
            arm_seen.add(name)
            atom = {**common, **arm_atom(name, bodies[name], frames[name])}
            comp = {'id': instance, 'arm_link': name}
            if row.get('T_S_local') is not None:
                source_frame = frames[name].copy(); source_frame[:3, 3] *= 1000
                comp['max_link_transform_difference_mm_or_dimensionless'] = float(np.max(np.abs(matrix_check(row['T_S_local']) - source_frame)))
                if comp['max_link_transform_difference_mm_or_dimensionless'] > 1e-8:
                    raise ValueError(f'{state}: CAD placement differs from independent URDF FK: {instance}')
            if row.get('mass_kg') is not None:
                comp['mass_difference_kg'] = float(row['mass_kg']) - atom['mass_kg']
            if row.get('center_of_mass_S_mm') is not None:
                comp['max_COM_difference_mm'] = float(np.max(np.abs(np.asarray(row['center_of_mass_S_mm']) - 1000 * np.asarray(atom['center_of_mass_S_m']))))
                comp['receipt_center_semantics'] = 'NOMINAL_BREP_GEOMETRIC_CENTER_NOT_USED_FOR_DYNAMICS' if row.get('mass_kg') is None and row.get('inertia_about_COM_S_kg_mm2') is None else 'RECEIPT_DECLARATION_COMPARED_WITH_ACCEPTED_URDF'
            if row.get('inertia_about_COM_S_kg_mm2') is not None:
                comp['max_inertia_difference_kg_mm2'] = float(np.max(np.abs(np.asarray(row['inertia_about_COM_S_kg_mm2']) - 1e6 * np.asarray(atom['inertia_about_COM_S_kg_m2']))))
            comparisons.append(comp)
            mass = atom['mass_kg']
        else:
            mass = row.get('mass_kg')
            if mass is None:
                unknown_by_role[role].append({**common, 'mass_source': row.get('mass_source'), 'reason': 'MASS_UNKNOWN_NOT_ZERO'})
                continue
            mass = float(mass)
            if not math.isfinite(mass) or mass < 0:
                raise ValueError(f'{state}: negative or nonfinite mass {instance}')
            if mass == 0:
                zero.append({**common, 'reason': 'EXPLICIT_ZERO_RECEIPT_CONTRIBUTION', 'mass_basis': row.get('mass_basis')})
                continue
            atom = {**common, 'mass_kg': mass, 'mass_source': row.get('mass_source') or 'UNKNOWN',
                    'mass_basis': row.get('mass_basis', 'ASSEMBLY_RECEIPT_DECLARATION'),
                    'inertia_basis': row.get('inertia_basis', 'UNIFORM_PROXY_GEOMETRY_FOR_BUDGET' if row.get('mass_source') == 'BUDGET' else 'CAD_MASS_PROPERTIES_WITH_CANDIDATE_DENSITY' if row.get('mass_source') == 'CAD_ESTIMATE' else 'ASSEMBLY_RECEIPT_DECLARATION')}
            if row.get('center_of_mass_S_mm') is not None and row.get('inertia_about_COM_S_kg_mm2') is not None:
                center = np.asarray(row['center_of_mass_S_mm'], dtype=float) * .001
                if center.shape != (3,) or not np.isfinite(center).all():
                    raise ValueError(f'{state}: bad center of mass {instance}')
                atom['center_of_mass_S_m'] = center.tolist()
                atom['inertia_about_COM_S_kg_m2'] = (np.asarray(row['inertia_about_COM_S_kg_mm2'], dtype=float) * 1e-6).tolist()
                # These seventeen budget geometries are literal centered boxes in
                # the frozen CAD source; check OCC integrals against box formulas.
                box_budget = instance.startswith(('equipment_', 'wing_release_budget_', 'wing_harness_budget_')) or instance == 'navigation_camera' or (instance.startswith('wing_') and '_leaf_' in instance)
                if atom['mass_source'] == 'BUDGET' and box_budget and row.get('local_bounds') and row.get('T_S_local'):
                    local = row['local_bounds']; t = matrix_check(row['T_S_local'])
                    size = np.asarray(local['size_mm'], dtype=float)
                    local_c = (np.asarray(local['min_mm']) + local['max_mm']) / 2
                    expected_c = t[:3, :3] @ local_c + t[:3, 3]
                    own = mass/12 * np.diag([size[1]**2+size[2]**2, size[0]**2+size[2]**2, size[0]**2+size[1]**2])
                    expected_i = t[:3, :3] @ own @ t[:3, :3].T
                    check = {'id': instance, 'max_COM_difference_mm': float(np.max(np.abs(expected_c - 1000*center))),
                             'max_inertia_difference_kg_mm2': float(np.max(np.abs(expected_i - row['inertia_about_COM_S_kg_mm2']))),
                             'scope': 'CAD_UNIFORM_BOX_INTEGRAL_VS_ANALYTICAL_BOX_NOT_REAL_DEVICE_VALIDATION'}
                    if check['max_COM_difference_mm'] > 1e-6 or check['max_inertia_difference_kg_mm2'] > 1e-5:
                        raise ValueError(f'{state}: budget box integral differs from analytical COM inertia: {check}')
                    budget_checks.append(check)
        if not isinstance(owner, str) or not owner.strip():
            raise ValueError(f'{state}: positive mass needs a unique mass_owner: {instance}')
        if owner in claimed:
            raise ValueError(f'{state}: duplicate positive mass owner {owner}: {claimed[owner]} and {instance}')
        claimed[owner] = instance
        known_mass_by_role[role].append({'id': instance, 'mass_owner': owner, 'mass_kg': mass, 'mass_source': atom['mass_source']})
        if row.get('shape_valid') is False:
            geometry_flags.append({'id': instance, 'shape_valid': False,
                                   'mass_effect': 'URDF_MASS_INDEPENDENT_OF_BREP' if name else 'CAD_DISTRIBUTION_PROVISIONAL_GEOMETRY_FLAG'})
        if 'inertia_about_COM_S_kg_m2' not in atom:
            missing_by_role[role].append({**common, 'mass_kg': mass, 'reason': 'MASS_KNOWN_COM_OR_INERTIA_UNKNOWN'})
            continue
        check = inertia_check(atom['inertia_about_COM_S_kg_m2'])
        if not check['tensor_numerically_physical']:
            raise ValueError(f'{state}: nonphysical numerical inertia: {instance}, {check}')
        atom['numerical_tensor_check'] = check
        atoms_by_role[role].append(atom)
    if arm_seen != set(bodies):
        raise ValueError(f'{state}: expected exactly ten arm_link atoms, missing {set(bodies) - arm_seen}')
    groups = {}
    for role in ROLES:
        full = aggregate(atoms_by_role[role])
        known_mass = math.fsum(row['mass_kg'] for row in known_mass_by_role[role])
        groups[role] = {'instance_count': counts[role], 'known_mass_kg': known_mass,
                        'ledger_scope': 'DECLARED_INSTANCES_IN_THIS_RECEIPT' if counts[role] else 'NO_INSTANCES_IN_THIS_VIEW_NOT_A_ZERO_PHYSICAL_MASS_CLAIM',
                        'mass_by_source_kg': {source: math.fsum(row['mass_kg'] for row in known_mass_by_role[role] if row['mass_source'] == source) for source in sorted({str(row['mass_source']) for row in known_mass_by_role[role]})},
                        'allocated_complete_property_subset': full,
                        'all_known_mass_has_COM_and_inertia': not missing_by_role[role],
                        'all_declared_instances_have_allocated_mass': not unknown_by_role[role],
                        'unknown_mass_instances': unknown_by_role[role],
                        'known_mass_missing_properties': missing_by_role[role],
                        'mass_atoms': atoms_by_role[role]}
    arm = [a for a in atoms_by_role['ONBOARD_CANDIDATE'] if a.get('arm_link')]
    return {'state': state, 'q_deg': data['q_deg'], 'finger_mm': data['finger_mm'],
            'T_S_arm_base_mm': data['T_S_arm_base'], 'source_joint_limit_checks': limits,
            'all_source_joint_limits_satisfied': all(x['within_source_limits'] for x in limits),
            'groups': groups, 'unique_positive_mass_owner_count': len(claimed),
            'zero_contribution_instances': zero, 'source_geometry_flags': geometry_flags,
            'arm_receipt_vs_independent_URDF': comparisons,
            'budget_box_receipt_vs_analytical': budget_checks,
            'arm_only_mass_properties': aggregate(arm),
            'arm_conditional_ground_1g': static_gravity_arm(arm, data['T_S_arm_base']),
            'onboard_full_physical_mass_properties_complete': False,
            'completeness_reason': 'DIGITAL_AND_CANDIDATE_INPUTS_NOT_AS_BUILT; UNKNOWN_MASSES_AND_DISTRIBUTIONS_RETAINED',
            'mass_owner_values_by_role': {role: {row['mass_owner']: row['mass_kg'] for row in rows} for role, rows in known_mass_by_role.items()},
            'mass_owner_values': {row['mass_owner']: row['mass_kg'] for rows in known_mass_by_role.values() for row in rows}}


def self_test(bodies, joints):
    atoms = [{'mass_kg': 1., 'center_of_mass_S_m': [x, 0, 0], 'inertia_about_COM_S_kg_m2': (np.eye(3) * .1).tolist()} for x in (-1., 1.)]
    total = aggregate(atoms)
    analytical_error = float(np.max(np.abs(np.asarray(total['inertia_about_COM_S_kg_m2']) - np.diag([.2, 2.2, 2.2]))))
    offset = np.array([3., -4., 5.])
    translated = [{**a, 'center_of_mass_S_m': (np.asarray(a['center_of_mass_S_m']) + offset).tolist()} for a in atoms]
    translation_error = float(np.max(np.abs(np.asarray(total['inertia_about_COM_S_kg_m2']) - aggregate(translated)['inertia_about_COM_S_kg_m2'])))
    spec = importlib.util.spec_from_file_location('wp01_kin_independent', WP01_KIN)
    independent = importlib.util.module_from_spec(spec); spec.loader.exec_module(independent)
    root = transform([90, 0, 125.15], [.2, -.3, .4])
    fk_error = 0.
    for q in ([0, 0, 0, 0, 0, 0], [0, -30, -60, 40, 0, 0], [0, -80, -70, 30, 0, 0], [13, -42, -33, 27, 18, -9]):
        ours, _ = fk(joints, q, 15., root)
        reference = independent.fk(q, root, 15.)
        for name in bodies:
            comparison = ours[name].copy(); comparison[:3, 3] *= 1000
            fk_error = max(fk_error, float(np.max(np.abs(comparison - reference[name]))))
    mass = math.fsum(x['mass_kg'] for x in bodies.values())
    test_root = transform([90, 0, 125.15])
    fixture_rows = [{'id': name, 'arm_link': name, 'mass_owner': 'arm:' + name,
                     'product_role': 'ONBOARD_CANDIDATE'} for name in bodies]
    fixture_rows += [
        {'id': 'GSE_test', 'mass_owner': 'GSE_test', 'product_role': 'GSE', 'mass_source': 'BUDGET',
         'mass_kg': 20., 'center_of_mass_S_mm': [0, 0, -200], 'inertia_about_COM_S_kg_mm2': (np.eye(3) * 1e6).tolist()},
        {'id': 'unselected_test', 'mass_owner': 'unselected_test', 'product_role': 'ONBOARD_CANDIDATE',
         'mass_source': 'UNKNOWN', 'mass_kg': None}]
    fixture = {'state': 'NUMERICAL_SELF_TEST', 'q_deg': [0, -30, -60, 40, 0, 0], 'finger_mm': 15.,
               'T_S_arm_base': test_root.tolist(), 'instances': fixture_rows}
    sample = process_state(fixture, bodies, joints)
    gse_separated = sample['groups']['GSE']['known_mass_kg'] == 20. and abs(sample['groups']['ONBOARD_CANDIDATE']['known_mass_kg'] - mass) < 1e-13
    unknown_preserved = len(sample['groups']['ONBOARD_CANDIDATE']['unknown_mass_instances']) == 1
    duplicate = {**fixture, 'instances': fixture_rows + [{**fixture_rows[-2], 'id': 'GSE_duplicate'}]}
    duplicate_rejected = False
    try:
        process_state(duplicate, bodies, joints)
    except ValueError as exc:
        duplicate_rejected = 'duplicate positive mass owner' in str(exc)
    result = {'analytical_two_sphere_parallel_axis_error_kg_m2': analytical_error,
              'global_translation_invariance_error_kg_m2': translation_error,
              'independent_WP01_SciPy_FK_max_matrix_error_mm_or_dimensionless': fk_error,
              'FK_samples': 4, 'FK_links_per_sample': len(bodies),
              'accepted_arm_mass_kg': mass,
              'synthetic_GSE_excluded_from_onboard': gse_separated,
              'synthetic_unknown_mass_preserved': unknown_preserved,
              'synthetic_duplicate_mass_owner_rejected': duplicate_rejected,
              'all_accepted_inertias_physical': all(b['numerical_check']['tensor_numerically_physical'] for b in bodies.values())}
    if analytical_error > 1e-12 or translation_error > 1e-12 or fk_error > 1e-9 or abs(mass - 4.695555949342986) > 1e-13 or not (gse_separated and unknown_preserved and duplicate_rejected):
        raise AssertionError(result)
    result['arithmetic_and_FK_tests_pass'] = True
    result['scope'] = 'NUMERICAL_IMPLEMENTATION_ONLY_NOT_SCIENTIFIC_OR_HARDWARE_VERIFICATION'
    return result


def write_chinese_summary(result, json_path):
    states = result['states']
    labels = {'parking': '开放停放参考（非发射收拢）', 'released': '释放后静态候选', 'service': '服务工作候选'}
    lines = ['# WP03 随星质量与惯量计算摘要', '',
             '对象为当前冻结几何的已分配质量部分。B601 使用 accepted URDF 数字惯性，新结构使用候选材料的 CAD 估计，设备/翼片使用明确预算。未知项没有置零补齐；这些数值不是实物整星质量、发射资格或控制验证结果。', '',
             '## 三种配置', '',
             'S 原点位于母线核心几何中心；X 纵向、Y 横向、Z 朝屋顶。所有状态的臂根 A0=[90, 0, 125.15] mm，实体承载面中心为 [90, 0, 127.555] mm。', '',
             '| 配置 | 随星已知质量小计 / kg | 已分配部分 COM：S.x, S.y, S.z / mm | 未分配质量实例数 |',
             '|---|---:|---|---:|']
    for state in states:
        group = state['groups']['ONBOARD_CANDIDATE']; props = group['allocated_complete_property_subset']
        center = ', '.join(f'{1000*x:.6f}' for x in props['center_of_mass_S_m'])
        lines.append(f"| {state['state']}：{labels[state['state']]} | {group['known_mass_kg']:.12f} | [{center}] | {len(group['unknown_mass_instances'])} |")
    mass_values = [s['groups']['ONBOARD_CANDIDATE']['known_mass_kg'] for s in states]
    lines += ['', f'三态已知质量最大差 {max(mass_values)-min(mass_values):.3e} kg；跨状态正质量所有者集合一致={result["cross_state_checks"]["same_positive_mass_owners"]}。尾数仅用于复算对账，不代表测量精度。释放件保留在星体上，姿态改变不会删除质量。', '',
              '## 不重复计量的质量分解', '', '| 来源 | parking 已知质量 / kg | 含义 |', '|---|---:|---|']
    groups = states[0]['groups']['ONBOARD_CANDIDATE']
    meanings = {'SOURCE_DIGITAL': '10 个 B601 link；覆盖其显示 BRep，不加 BRep 均质质量',
                'CAD_ESTIMATE': '当前实件体积及质量分布×候选铝/钢密度；非实测',
                'BUDGET': '设备、相机、六翼片和翼释放/线束的声明分配；惯量按代理几何分布'}
    for source, mass in groups['mass_by_source_kg'].items():
        lines.append(f'| {source} | {mass:.12f} | {meanings.get(source,"以原子记录的来源说明为准")} |')
    lines += ['', 'B601 的 4.695555949342986 kg 仅计一次。六个设备合计 6.55 kg；导航相机预算 0.15 kg；六片 R2 尺寸叶片预算 1.08 kg；两翼释放器预算 0.16 kg、翼线束预算 0.10 kg。新铰链、轴销、边框和支架按本轮 CAD 计量，未再加入旧 R2 铰链预算。未采用旧 31.0229 kg 整星总额。', '',
              '本轮翼根为 y=±121.15 mm、z=−108.15 mm，采用 WP03 R3 固定偏置串联铰链。每一叶片和随动实件使用该状态的收据变换计算惯量，未搬用旧 R2 聚合张量。', '',
              '## 惯量矩阵', '',
              '以下单位均为 kg·m²，行列均按 S.x、S.y、S.z 排列。I_C 关于已分配部分的共同质心，I_S 关于 S 原点；二者都以 S 轴表达。必须连同参考点使用，不能把 I_S 当 COM 张量输入。']
    for state in states:
        props = state['groups']['ONBOARD_CANDIDATE']['allocated_complete_property_subset']
        lines += ['', f'### {state["state"]} / {labels[state["state"]]}', '', f'关节角 q / deg：{state["q_deg"]}；双指移动坐标 {state["finger_mm"]} mm。', '', '```text']
        for name, field in [('I_C', 'inertia_about_COM_S_kg_m2'), ('I_S', 'inertia_about_S_origin_S_kg_m2')]:
            lines.append(name+' =')
            for row in props[field]:
                lines.append('  ['+', '.join(f'{x: .12f}' for x in row)+']')
        lines += ['```', '', f'共同质心惯量最小主值 {min(props["numerical_tensor_check"]["principal_inertias_kg_m2"]):.9g} kg·m²；两种平行轴算法最大差 {props["parallel_axis_two_methods_max_error_kg_m2"]:.3e} kg·m²。']
    lines += ['', '## GSE 与未定项', '']
    if result['ground_AIT_views']:
        for ground in result['ground_AIT_views']:
            gse = ground['GSE_ledger']; combo = ground['combined_AIT_allocated_property_subset']
            lines.append(f'parking_ground 单独含 {gse["instance_count"]} 个 GSE 实例，已知 GSE 质量 {gse["known_mass_kg"]:.12f} kg；AIT 已分配组合为 {combo["mass_kg"]:.12f} kg。该 GSE 质量不进入上表任何随星小计。地面视图所引用随星 owner、质量、COM 和惯量已与 parking 对拍，最大惯量差 {ground["onboard_reference_consistency"]["max_inertia_difference_kg_m2"]:.3e} kg·m²。')
    else:
        lines.append('没有可用地面组合收据；未核算 GSE，不能据此声称其质量为零。')
    unknown = groups['unknown_mass_instances']; counts = Counter(str(x.get('parent_assembly')) for x in unknown)
    lines += ['', '| parking 未分配质量实例所属装配 | 实例数 |', '|---|---:|']
    lines += [f'| {parent} | {count} |' for parent, count in sorted(counts.items())]
    lines += ['', f'已知质量但缺 COM/惯量的实例数：{len(groups["known_mass_missing_properties"])}。完整名单见 JSON 的 `states[*].groups.ONBOARD_CANDIDATE.unknown_mass_instances` 和 `known_mass_missing_properties`。', '',
              '未分配项目包括未选紧固件、热界面/热带、接触垫、保持释放驱动/弹簧/传感器、部分电缆/连接器和外部接口。计数还包含纯保留体或设备功能表示，不能直接解释为同样数量的缺失实物件；补充质量前需先查设备总成预算的含件范围。UNKNOWN 的真实质量及质量分布未给出可用界限，因此无法给出真实整星质量、COM 或惯量误差上界。', '',
              '## 计算核对与下一步导入', '',
              f'- XML/Rodrigues FK 与独立 WP01/SciPy FK 对拍：4 姿态×10 link，最大矩阵差 {result["tests"]["independent_WP01_SciPy_FK_max_matrix_error_mm_or_dimensionless"]:.3e} mm 或无量纲旋转元素。',
              '- 正质量 mass_owner 重复会拒绝；三态根变换和 owner 质量一致性已检查；预算/未知/GSE 与 B601 数字质量分别保留。',
              f'- 输入文件在计算期间保持不变={result["source_files_unchanged"]}。三态收据均核对冻结生成器哈希；这是可复算输入绑定，不代表环境或载荷资格。',
              '- 后续多体模型读取 `source_joint_tree`、`source_arm_bodies`、根变换及每个 `mass_atoms`。保持关节树与各 link COM 张量；只在相对运动锁定的快照计算中使用整星 I_C。',
              '- 以当前安装变换绑定星体新增刚体和翼铰。动态关节速度/加速度、目标接触、关节/连接/翼柔性与执行器动态尚须另行定义；本轮没有运行新动力学仿真。',
              '- `arm_conditional_ground_1g` 是单独数字臂沿 −S.Z 的 46.0477 N 量级地面重力输入，保留关于 S、A0、承载面三种力矩。它不表示发射许用载荷，也未假定鞍座反力均分。',
              '- 当前独立梁架筛查见 `FRAME_STIFFNESS_SCREEN.json`；后端夹固、GSE 夹固与自由体边界分开。六个自由体刚体模态使绝对静刚度不可逆，不能用地面约束矩阵代替自由飞行。', '',
              f'计算结果：`{json_path.name}`，SHA256 `{sha(json_path)}`。',
              '复算命令：`python dynamics_handoff.py`。脚本读取三份随星及可选的 GSE 组合收据，重新生成本摘要；不启动 CAD，不更改源资产或历史 Gate。', '']
    summary = json_path.parent/'DYNAMICS_SUMMARY_ZH.md'
    summary.write_text('\n'.join(lines), encoding='utf-8')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--input-dir', type=Path, default=HERE / 'results')
    parser.add_argument('--output', type=Path, default=HERE / 'results/DYNAMICS_HANDOFF.json')
    args = parser.parse_args()
    bodies, joints = source_urdf()
    tests = self_test(bodies, joints)
    if args.self_test:
        print(json.dumps(tests, indent=2)); return
    paths = [args.input_dir / f'{state}_instances.json' for state in STATES]
    ground_paths = [p for p in [args.input_dir / 'parking_ground_instances.json'] if p.is_file()]
    model_path = HERE / 'spacecraft_model.py'
    provenance = [Path(__file__).resolve(), model_path, HERE/'design_parameters.json', HERE/'kinematics.py', HERE/'wing_kinematics.py']
    hashes = {str(path.resolve()): sha(path) for path in [URDF, WP01_KIN, *paths, *ground_paths, *[p for p in provenance if p.is_file()]]}
    receipts = [json.loads(path.read_text(encoding='utf-8-sig')) for path in paths]
    source_checks = []
    for path, data in zip(paths, receipts):
        matched = data.get('source_sha256') == sha(model_path) if data.get('source_sha256') is not None else None
        source_checks.append({'receipt': str(path.resolve()), 'recorded_model_sha256': data.get('source_sha256'), 'matches_current_model_source': matched})
        if matched is False:
            raise ValueError('Stale assembly receipt does not match frozen model source: ' + str(path))
    results = [process_state(data, bodies, joints) for data in receipts]
    if [r['state'] for r in results] != list(STATES):
        raise ValueError('Receipt state labels do not match requested file states')
    root_error = max(float(np.max(np.abs(np.asarray(r['T_S_arm_base_mm']) - results[0]['T_S_arm_base_mm']))) for r in results)
    owners = results[0]['mass_owner_values']
    identities = all(set(r['mass_owner_values']) == set(owners) for r in results)
    mass_error = max((abs(r['mass_owner_values'][k] - value) for r in results for k, value in owners.items() if k in r['mass_owner_values']), default=0.)
    if root_error > 1e-10:
        raise ValueError('Root transform changed between poses')
    if not identities or mass_error > 1e-9:
        raise ValueError('Mass owners or per-owner masses changed; explicit configuration difference disposition required')
    ground_results = []
    for path in ground_paths:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        if data.get('source_sha256') is not None and data['source_sha256'] != sha(model_path):
            raise ValueError('Stale ground receipt does not match frozen model source: ' + str(path))
        ground = process_state(data, bodies, joints)
        corresponding = next(r for r in results if r['state'] == ground['state'])
        expected = corresponding['mass_owner_values_by_role']['ONBOARD_CANDIDATE']
        actual = ground['mass_owner_values_by_role']['ONBOARD_CANDIDATE']
        same_owners = set(expected) == set(actual)
        difference = max((abs(actual[k] - value) for k, value in expected.items() if k in actual), default=0.)
        expected_props = corresponding['groups']['ONBOARD_CANDIDATE']['allocated_complete_property_subset']
        actual_props = ground['groups']['ONBOARD_CANDIDATE']['allocated_complete_property_subset']
        center_difference = float(np.max(np.abs(np.asarray(expected_props['center_of_mass_S_m']) - actual_props['center_of_mass_S_m'])))
        inertia_difference = float(np.max(np.abs(np.asarray(expected_props['inertia_about_COM_S_kg_m2']) - actual_props['inertia_about_COM_S_kg_m2'])))
        if not same_owners or difference > 1e-9 or center_difference > 1e-10 or inertia_difference > 1e-10:
            raise ValueError('Ground view changed referenced onboard mass owners or mass properties')
        ground_results.append({'receipt': str(path.resolve()), 'state': ground['state'],
                               'onboard_reference_consistency': {'same_mass_owners': same_owners,
                                    'max_mass_difference_kg': difference, 'max_COM_difference_m': center_difference,
                                    'max_inertia_difference_kg_m2': inertia_difference},
                               'GSE_ledger': ground['groups']['GSE'],
                               'combined_AIT_allocated_property_subset': aggregate([*ground['groups']['ONBOARD_CANDIDATE']['mass_atoms'], *ground['groups']['GSE']['mass_atoms']]),
                               'scope': 'AIT_PRODUCT_ONLY_GSE_EXCLUDED_FROM_EVERY_ONBOARD_TOTAL'})
    unchanged = all(sha(path) == value for path, value in hashes.items())
    if not unchanged:
        raise RuntimeError('Input changed during mass calculation; rerun against stable receipts')
    result = {'schema': 'WP03_DYNAMICS_HANDOFF_V1', 'status': 'CANDIDATE_ALLOCATED_MASS_PROPERTIES_NO_QUALIFICATION_CREDIT',
              'units': {'length': 'm', 'mass': 'kg', 'inertia': 'kg m^2', 'force': 'N', 'moment': 'N m', 'receipt_transform_translation': 'mm'},
              'frame_S': {'origin': 'bus_core_geometric_center', 'X': 'longitudinal', 'Y': 'transverse', 'Z': 'roof_normal'},
              'tensor_convention': '3x3 mathematical inertia tensor; URDF off-diagonal signs unchanged; tensors expressed in S axes',
              'input_sha256': hashes, 'source_files_unchanged': unchanged,
              'receipt_model_source_checks': source_checks,
              'source_arm_bodies': bodies, 'source_joint_tree': joints,
              'tests': tests,
              'cross_state_checks': {'root_transform_max_difference_mm_or_dimensionless': root_error,
                                     'same_positive_mass_owners': identities, 'max_per_owner_mass_difference_kg': mass_error},
              'states': results,
              'ground_AIT_views': ground_results,
              'ground_AIT_scope': 'SEPARATE_GSE_LEDGER_COMPUTED' if ground_results else 'NO_GROUND_RECEIPT_AVAILABLE_NOT_A_ZERO_GSE_MASS_CLAIM',
              'not_computed': ['new_dynamics_simulation', 'control_stability', 'launch_strength_margin', 'full_flight_qualification', 'unknown_mass_bounds'],
              'configuration_notes': ['ONBOARD, GSE, TEST_DUMMY and UNKNOWN are separate ledgers',
                                      'B601 URDF digital link mass replaces each arm visual BRep density mass',
                                      'R2 six leaves contribute 1.08 kg; current CAD hinges replace legacy hinge budgets',
                                      'Uniform proxy equipment inertia is a distribution assumption, not vendor or measured inertia',
                                      'WP03 R3 wing root absY121.15 mm replaces historic115.4 mm; fixed-offset serial hinges replace old normal reassignment',
                                      'Wing frame continuity and deployment collision checks are separate from mass integration',
                                      'OPEN_PARKING is not LAUNCH_STOWED; fixed GSE compliance does not represent a free spacecraft']}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    summary = write_chinese_summary(result, args.output)
    print(json.dumps({'output': str(args.output), 'summary': str(summary), 'states': [{ 'state': r['state'], 'allocated_onboard_mass_kg': r['groups']['ONBOARD_CANDIDATE']['known_mass_kg'], 'allocated_subset_COM_S_m': r['groups']['ONBOARD_CANDIDATE']['allocated_complete_property_subset']['center_of_mass_S_m'], 'unknown_onboard_mass_count': len(r['groups']['ONBOARD_CANDIDATE']['unknown_mass_instances'])} for r in results], 'tests': tests}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
