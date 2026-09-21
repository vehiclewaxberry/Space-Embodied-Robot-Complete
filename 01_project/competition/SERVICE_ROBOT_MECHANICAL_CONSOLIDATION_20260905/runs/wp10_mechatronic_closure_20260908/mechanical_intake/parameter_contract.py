"""Unit-explicit, fail-closed mechanical parameter intake. No CAD or simulation imports."""
import math
import numpy as np

CONVERSIONS = {('mm', 'm'): 1e-3, ('mm^3', 'm^3'): 1e-9,
               ('kg/mm^3', 'kg/m^3'): 1e9, ('kg*mm^2', 'kg*m^2'): 1e-6,
               ('g', 'kg'): 1e-3, ('kg', 'kg'): 1., ('m', 'm'): 1.,
               ('kg*m^2', 'kg*m^2'): 1.}

def convert(value, source_unit, target_unit):
    """Unknown stays unknown; units must be in the explicit whitelist."""
    factor = CONVERSIONS[(source_unit, target_unit)]
    if value is None:
        return None
    array = np.asarray(value, dtype=float)
    if not np.all(np.isfinite(array)):
        raise ValueError('NONFINITE_QUANTITY')
    result = array * factor
    return float(result) if result.ndim == 0 else result.tolist()

def quantity(estimate, unit, identity, source_pointer):
    return dict(estimate=estimate, unit=unit, identity=identity,
                standard_uncertainty=None, distribution=None, degrees_of_freedom=None,
                lower_bound=None, upper_bound=None, correlation_group=None,
                uncertainty_status='NOT_CHARACTERIZED_NO_PROBABILITY_ASSIGNED',
                source_pointer=source_pointer)

def validate_transform(T, atol=1e-8):
    a = np.asarray(T, dtype=float)
    if a.shape != (4, 4) or not np.all(np.isfinite(a)):
        raise ValueError('TRANSFORM_SHAPE_OR_FINITE')
    if not np.allclose(a[3], [0, 0, 0, 1], atol=atol, rtol=0):
        raise ValueError('TRANSFORM_HOMOGENEOUS_ROW')
    R = a[:3, :3]
    if not np.allclose(R.T @ R, np.eye(3), atol=atol, rtol=0):
        raise ValueError('ROTATION_NOT_ORTHOGONAL')
    if not math.isclose(float(np.linalg.det(R)), 1., abs_tol=atol, rel_tol=0):
        raise ValueError('ROTATION_NOT_RIGHT_HANDED')
    return True

def transform_mm_to_m(T):
    validate_transform(T)
    a = np.array(T, dtype=float)
    a[:3, 3] = convert(a[:3, 3], 'mm', 'm')
    return a.tolist()

def sw16_to_T_m(values):
    v = np.asarray(values, dtype=float)
    if v.shape != (16,) or not np.all(np.isfinite(v)):
        raise ValueError('SW16_SHAPE_OR_FINITE')
    if not np.allclose(v[12:], [1, 0, 0, 0], rtol=0, atol=1e-12):
        raise ValueError('SW16_SCALE_OR_UNUSED_FIELDS')
    T = np.eye(4)
    # Locked writer's t16 contract uses column-major rotation and metre translation.
    T[:3, :3] = v[:9].reshape((3, 3), order='F')
    T[:3, 3] = v[9:12]
    validate_transform(T)
    return T.tolist()

def validate_inertia(I, unit, about='COM', expressed_in='local', atol=1e-12):
    if I is None:
        raise ValueError('INERTIA_UNKNOWN')
    if about != 'COM' or not expressed_in:
        raise ValueError('INERTIA_REFERENCE_AMBIGUOUS')
    a = np.asarray(convert(I, unit, 'kg*m^2'), dtype=float)
    if a.shape != (3, 3):
        raise ValueError('INERTIA_SHAPE')
    if not np.allclose(a, a.T, atol=atol, rtol=0):
        raise ValueError('INERTIA_NOT_SYMMETRIC')
    eig = np.linalg.eigvalsh(a)
    if eig[0] < -atol:
        raise ValueError('INERTIA_NOT_PSD')
    if eig[2] > eig[0] + eig[1] + atol:
        raise ValueError('INERTIA_PRINCIPAL_TRIANGLE')
    return {'matrix_kg_m2': a.tolist(), 'principal_moments_kg_m2': eig.tolist()}

def validate_complete_rigid_body(body):
    if not body.get('physical_mass_applicable', False):
        raise ValueError('RESERVED_VOLUME_NOT_PHYSICAL_BODY')
    mass = body['mass']['estimate']
    if body['mass']['unit'] != 'kg' or mass is None or not math.isfinite(mass) or mass <= 0:
        raise ValueError('POSITIVE_MASS_UNKNOWN_OR_INVALID')
    if body['center_of_mass_local']['unit'] != 'm':
        raise ValueError('COM_UNIT')
    com = body['center_of_mass_local']['estimate']
    if com is None or np.asarray(com).shape != (3,) or not np.all(np.isfinite(com)):
        raise ValueError('COM_UNKNOWN_OR_INVALID')
    inertia = body['inertia_about_COM_local']
    return validate_inertia(inertia['estimate'], inertia['unit'])

def validate_mass_selection(packet, component_ids, owner_ids):
    """Reject repeated hardware/whole-module + children. This does not authorize summation."""
    if len(component_ids) != len(set(component_ids)) or len(owner_ids) != len(set(owner_ids)):
        raise ValueError('DUPLICATE_MASS_TOKEN')
    components = {x['id']: x for x in packet['instances']}
    owners = {x['owner']: x for x in packet['owners']}
    covered = set()
    for owner_id in owner_ids:
        owner = owners[owner_id]
        if owner['module_reference_mass']['estimate'] is None:
            raise ValueError('WHOLE_MODULE_MASS_UNKNOWN')
        ids = set(owner['instance_ids'])
        if covered & ids:
            raise ValueError('OVERLAPPING_MODULE_MASS')
        covered |= ids
    if covered & set(component_ids):
        raise ValueError('WHOLE_MODULE_AND_CHILD_DOUBLE_COUNT')
    for ident in component_ids:
        if components[ident]['mass']['estimate'] is None:
            raise ValueError('INSTANCE_MASS_UNKNOWN')
    return True

def physical_readiness(packet):
    failures = []
    for body in packet['instances']:
        if body['physical_mass_applicable']:
            try:
                validate_complete_rigid_body(body)
            except (ValueError, KeyError) as exc:
                failures.append({'id': body['id'], 'reason': str(exc)})
    if packet['joint_tree']['status'] != 'VALIDATED_CURRENT_HARDWARE_TREE':
        failures.append({'id': '__KINEMATIC_TREE__', 'reason': 'STATIC_POSES_DO_NOT_DEFINE_JOINTS'})
    return {'physical_dynamics_ready': not failures, 'failure_count': len(failures), 'failures': failures}

def validate_packet_integrity(packet):
    """Validate this revision's coverage and explicit source/SI transform contract."""
    ids = [x['id'] for x in packet['instances']]
    if len(ids) != 873 or len(set(ids)) != 873:
        raise ValueError('INSTANCE_COVERAGE_OR_DUPLICATE')
    if set(packet['state_names']) != {'service', 'parking', 'released'}:
        raise ValueError('THREE_STATE_COVERAGE')
    owners = packet['owners']
    if len(owners) != 43 or len({x['owner'] for x in owners}) != 43:
        raise ValueError('OWNER_COVERAGE_OR_DUPLICATE')
    owned = [i for x in owners for i in x['instance_ids']]
    if len(owned) != 873 or set(owned) != set(ids):
        raise ValueError('OWNER_INSTANCE_OVERLAP_OR_MISSING')
    for body in packet['instances']:
        for key, unit in [('mass','kg'),('center_of_mass_local','m'),('inertia_about_COM_local','kg*m^2')]:
            q = body[key]
            if q['unit'] != unit:
                raise ValueError('QUANTITY_UNIT_CONTRACT')
            for field in ['estimate','standard_uncertainty','distribution','degrees_of_freedom','identity']:
                if field not in q:
                    raise ValueError('QUANTITY_UNCERTAINTY_IDENTITY_MISSING')
        if set(body['geometry_by_state']) != set(packet['state_names']):
            raise ValueError('INSTANCE_STATE_MISSING')
        for state in packet['state_names']:
            g = body['geometry_by_state'][state]
            if g['translation_unit'] != 'm' or g['rotation_unit'] != '1' or g['source_translation_unit'] != 'mm':
                raise ValueError('TRANSFORM_UNIT_CONTRACT')
            source = transform_mm_to_m(g['T_local_to_S_source_mm'])
            si = g['T_local_to_S_SI_m']
            observed = g['observed_T_local_to_S_SI_m']
            validate_transform(si)
            validate_transform(observed)
            if not np.allclose(source, si, atol=1e-12, rtol=0):
                raise ValueError('SOURCE_TO_SI_TRANSFORM_MISMATCH')
            if not np.allclose(si, observed, atol=1e-8, rtol=0):
                raise ValueError('COLD_OBSERVED_TRANSFORM_MISMATCH')
    return True
