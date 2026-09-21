"""V31 bounded actuator bookkeeping. Stdlib only; no device I/O.

Wheel momentum is internal storage. Thruster angular impulse changes total
system angular momentum. All synthetic geometry is expressed about its own
declared reference COM, never the unknown current spacecraft COM.
"""
import math


def _vec(values, n, name):
    out = [float(v) for v in values]
    if len(out) != n or not all(math.isfinite(v) for v in out):
        raise ValueError(name + ': expected finite vector of length ' + str(n))
    return out


def _positive(value, name):
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(name + ': must be positive and finite')
    return value


def wheel_storage_check(delta_H_Nms, initial_H_Nms=(0, 0, 0),
                        capacity_per_axis_Nms=(0.1, 0.1, 0.1)):
    """Check desired INTERNAL wheel storage increment in the wheel-box axes.

    This function does not remove angular momentum from the whole system and
    does not test torque, slew time, actual wheel geometry or hardware validity.
    """
    delta = _vec(delta_H_Nms, 3, 'delta_H_Nms')
    initial = _vec(initial_H_Nms, 3, 'initial_H_Nms')
    caps = _vec(capacity_per_axis_Nms, 3, 'capacity_per_axis_Nms')
    if min(caps) <= 0:
        raise ValueError('wheel capacities must be positive')
    final = [a + b for a, b in zip(initial, delta)]
    initial_valid = all(abs(h) <= c for h, c in zip(initial, caps))
    margins = [c - abs(h) for h, c in zip(final, caps)]
    valid = initial_valid and min(margins) >= -1e-12
    return {'schema': 'V31_WHEEL_STORAGE_CHECK',
            'model_scope': 'DECLARED_AXIS_BOX_RESEARCH_ONLY',
            'frame': 'WHEEL_BOX_AXES', 'initial_valid': initial_valid,
            'delta_storage_Nms': delta, 'final_storage_Nms': final,
            'axis_margin_Nms': margins, 'storage_feasible': valid,
            'system_external_angular_impulse_Nms': [0.0, 0.0, 0.0],
            'actual_hardware_validated': False}


def wheel_direction_capacity(direction, initial_H_Nms=(0, 0, 0),
                             capacity_per_axis_Nms=(0.1, 0.1, 0.1)):
    """Maximum nonnegative increment along a unit direction in wheel axes."""
    direction = _vec(direction, 3, 'direction')
    norm = math.sqrt(sum(v*v for v in direction))
    if norm == 0:
        raise ValueError('zero direction')
    unit = [v/norm for v in direction]
    initial = _vec(initial_H_Nms, 3, 'initial_H_Nms')
    caps = _vec(capacity_per_axis_Nms, 3, 'capacity_per_axis_Nms')
    if min(caps) <= 0 or any(abs(h) > c for h, c in zip(initial, caps)):
        raise ValueError('invalid initial wheel storage or capacities')
    bounds = [(c-h)/u if u > 0 else (-c-h)/u
              for u, h, c in zip(unit, initial, caps) if u != 0]
    limit = min(bounds)
    return {'schema': 'V31_DIRECTIONAL_WHEEL_CAPACITY',
            'direction_unit_in_wheel_axes': unit,
            'additional_storage_capacity_Nms': limit,
            'capacity_is_direction_dependent': True,
            'scalar_sum_is_not_isotropic_capacity': True,
            'actual_hardware_validated': False}


def synthetic_reference(lever_m=0.15, force_N=0.012,
                        minimum_pulse_s=0.02, maximum_concurrent=2):
    """12 ideal on/off jets: two opposed jets at each of six positions.

    Fx/Tz, Fy/Tx, Fz/Ty are separate pairs. Fixed force when on; no throttle.
    Values are chosen research parameters, not attributed to C-POD.
    """
    a = _positive(lever_m, 'lever_m')
    force = _positive(force_N, 'force_N')
    pulse = _positive(minimum_pulse_s, 'minimum_pulse_s')
    if not isinstance(maximum_concurrent, int) or not 1 <= maximum_concurrent <= 12:
        raise ValueError('maximum_concurrent must be integer 1..12')
    nozzles = []
    for force_axis, offset_axis in ((0, 1), (1, 2), (2, 0)):
        for offset_sign in (1, -1):
            for force_sign in (1, -1):
                r = [0.0]*3
                d = [0.0]*3
                r[offset_axis] = offset_sign*a
                d[force_axis] = float(force_sign)
                nozzles.append({'id': 'SYN_F%d_R%+d_D%+d' % (force_axis, offset_sign, force_sign),
                                'force_axis': force_axis, 'offset_sign': offset_sign,
                                'force_sign': force_sign,
                                'position_m': r, 'direction_unit': d,
                                'on_force_N': force, 'unidirectional': True})
    return {'schema': 'V31_SYNTHETIC_ARRAY_REFERENCE',
            'classification': 'DESIGN_SYNTHETIC_NOT_C_POD_NOT_INSTALLED',
            'origin': 'SYNTHETIC_REFERENCE_COM', 'reference_COM_m': [0, 0, 0],
            'actual_spacecraft_COM_bound': False, 'lever_m': a,
            'minimum_pulse_s': pulse, 'maximum_concurrent': maximum_concurrent,
            'minimum_pulse_is_assumed_not_catalog_equivalent_MIB': True,
            'scheduling_policy': 'ONE_RECTANGULAR_PULSE_PER_SELECTED_JET_ALL_START_AT_ZERO',
            'plume_constraints': 'NOT_MODELLED_SYNTHETIC_REFERENCE_ONLY',
            'thermal_power_valve_life_and_propellant_constraints': 'NOT_MODELLED',
            'nozzles': nozzles, 'hardware_capability_credit': False,
            'manufacturing_release': False}


def wrench_matrix(nozzles, com_m=(0, 0, 0)):
    """Return 6xN [unit force direction; (r-COM) cross direction].

    A column multiplies nonnegative force in N to give N and N*m, or
    nonnegative impulse in N*s to give N*s and N*m*s. Mixed row units are
    explicit. This is NOT a single-unit six-vector norm or a feasibility test.
    """
    com = _vec(com_m, 3, 'com_m')
    columns = []
    for nozzle in nozzles:
        d = _vec(nozzle['direction_unit'], 3, 'direction_unit')
        if abs(sum(x*x for x in d)-1.0) > 1e-10:
            raise ValueError('direction must be unit length')
        r = [a-b for a, b in zip(_vec(nozzle['position_m'], 3, 'position_m'), com)]
        cross = [r[1]*d[2]-r[2]*d[1], r[2]*d[0]-r[0]*d[2], r[0]*d[1]-r[1]*d[0]]
        columns.append(d+cross)
    return [[column[row] for column in columns] for row in range(6)]


def matrix_rank(matrix, relative_tolerance=1e-12):
    """Small rank calculation after each row is independently normalized.

    Row normalization avoids treating force and moment rows as one unit.
    This diagnostic proves only linear span, not a positive control cone.
    """
    if not matrix:
        return 0
    n = len(matrix[0])
    a = [_vec(row, n, 'matrix row') for row in matrix]
    if n == 0:
        return 0
    for i, row in enumerate(a):
        scale = max(abs(v) for v in row)
        if scale:
            a[i] = [v/scale for v in row]
    rank = 0
    for col in range(n):
        pivot = max(range(rank, len(a)), key=lambda i: abs(a[i][col]))
        if abs(a[pivot][col]) <= relative_tolerance:
            continue
        a[rank], a[pivot] = a[pivot], a[rank]
        divisor = a[rank][col]
        a[rank] = [v/divisor for v in a[rank]]
        for row in range(rank+1, len(a)):
            factor = a[row][col]
            a[row] = [v-factor*w for v, w in zip(a[row], a[rank])]
        rank += 1
        if rank == len(a):
            break
    return rank


def allocate_reference_impulse(desired_impulse, window_s, reference=None):
    """Analytic plan for the declared symmetric synthetic array only.

    Input [Jx,Jy,Jz,Lx,Ly,Lz]: first 3 N*s, last 3 N*m*s. The COM must equal
    the synthetic origin. This evaluates one simultaneous rectangular-pulse
    plan, NOT all possible sequential or cancelling-pulse schedules. A rejected
    plan is not a theorem of global infeasibility. No actual jets are fired.
    """
    ref = reference if reference is not None else synthetic_reference()
    if ref.get('classification') != 'DESIGN_SYNTHETIC_NOT_C_POD_NOT_INSTALLED':
        raise ValueError('allocator accepts explicit synthetic reference only')
    if _vec(ref['reference_COM_m'], 3, 'reference_COM_m') != [0.0, 0.0, 0.0]:
        raise ValueError('analytic allocation assumes synthetic COM at origin')
    desired = _vec(desired_impulse, 6, 'desired_impulse')
    window = _positive(window_s, 'window_s')
    a = _positive(ref['lever_m'], 'lever_m')
    available = {(n['force_axis'], n['offset_sign'], n['force_sign']): n for n in ref['nozzles']}
    plan = []
    violations = []
    for force_axis, torque_axis in ((0, 5), (1, 3), (2, 4)):
        for offset_sign in (1, -1):
            signed_impulse = (desired[force_axis]-offset_sign*desired[torque_axis]/a)/2
            if abs(signed_impulse) <= 1e-15:
                continue
            sign = 1 if signed_impulse > 0 else -1
            nozzle = available.get((force_axis, offset_sign, sign))
            if nozzle is None:
                violations.append('REQUIRED_UNILATERAL_DIRECTION_NOT_AVAILABLE')
                continue
            on_force = _positive(nozzle['on_force_N'], 'on_force_N')
            duration = abs(signed_impulse)/on_force
            if duration + 1e-12 < ref['minimum_pulse_s']:
                violations.append('PULSE_BELOW_MINIMUM_FOR_THIS_EXACT_PLAN')
            if duration > window+1e-12:
                violations.append('PULSE_EXCEEDS_WINDOW_AT_FIXED_ON_FORCE')
            plan.append({'nozzle_id': nozzle['id'], 'start_s': 0.0,
                         'duration_s': duration, 'force_N': on_force,
                         'impulse_Ns': abs(signed_impulse)})
    if len(plan) > ref['maximum_concurrent']:
        violations.append('MAXIMUM_CONCURRENCY_EXCEEDED_FOR_THIS_PLAN')
    B = wrench_matrix(ref['nozzles'], ref['reference_COM_m'])
    impulses = {p['nozzle_id']: p['impulse_Ns'] for p in plan}
    actual = [sum(b*impulses.get(n['id'], 0.0) for b, n in zip(row, ref['nozzles'])) for row in B]
    residual_force = [actual[i]-desired[i] for i in range(3)]
    residual_torque = [actual[i]-desired[i] for i in range(3, 6)]
    # Separate absolute tolerances: never compare a mixed-unit 6-vector norm.
    linear_tolerance_Ns = 1e-12
    angular_tolerance_Nms = 1e-12
    if (max(abs(v) for v in residual_force) > linear_tolerance_Ns or
            max(abs(v) for v in residual_torque) > angular_tolerance_Nms):
        violations.append('ALGEBRAIC_RECONSTRUCTION_MISMATCH')
    return {'schema': 'V31_SYNTHETIC_IMPULSE_ALLOCATION',
            'classification': ref['classification'], 'wrench_linear_rank': matrix_rank(B),
            'requested_linear_impulse_Ns': desired[:3],
            'requested_angular_impulse_Nms': desired[3:], 'window_s': window,
            'pulse_plan': plan, 'simultaneous_jet_count': len(plan),
            'algebraic_linear_residual_Ns': residual_force,
            'algebraic_angular_residual_Nms': residual_torque,
            'linear_residual_tolerance_Ns': linear_tolerance_Ns,
            'angular_residual_tolerance_Nms': angular_tolerance_Nms,
            'plan_feasible_within_declared_constraints': not violations,
            'violations': sorted(set(violations)),
            'global_reachability_proven': False,
            'hardware_capability_credit': False, 'hardware_io_executed': False}


def current_cpod_capability():
    return {'schema': 'V31_CURRENT_CPOD_CAPABILITY',
            'status': 'UNKNOWN_CONTROLLED_ICD_AND_INSTALLED_COM_UNBOUND',
            'wrench_matrix': None, 'rank': None, 'nozzle_positions_m': None,
            'nozzle_directions': None, 'concurrency_limit': None,
            'minimum_command_pulse_s': None, 'installed_COM_m': None,
            'actual_6DOF_capability_verified': False,
            'manufacturing_release': False, 'hardware_io_executed': False}
