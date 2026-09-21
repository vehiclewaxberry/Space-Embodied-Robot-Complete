"""Bounded, source-pinned static wrench/impulse LP. Never imports historical solvers.

Run with a Python containing NumPy and SciPy. Real vendor layouts remain UNKNOWN.
The two artificial arrays are explicitly separate numerical test fixtures.
"""
from pathlib import Path
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
import argparse
import copy
import hashlib
import itertools
import json
import numpy as np
import scipy
from scipy.optimize import linprog

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def steiner(mass, displacement):
    d = np.asarray(displacement, float)
    return mass * (d @ d * np.eye(3) - np.outer(d, d))


def wrench_matrix(positions, directions, center, direction_kind, rotation=None):
    """Columns [force unit vector; moment arm x force direction], all about C.

    rotation maps S to one frozen inertial frame. No attitude propagation occurs.
    """
    p, d, c = [np.asarray(x, float) for x in (positions, directions, center)]
    if p.shape != d.shape or p.ndim != 2 or p.shape[1] != 3:
        raise ValueError('Expected matching N x 3 position/direction arrays')
    if direction_kind == 'exhaust_axis':
        d = -d
    elif direction_kind != 'spacecraft_force':
        raise ValueError('Force versus exhaust direction must be explicit')
    if not np.isfinite(p).all() or not np.isfinite(d).all():
        raise ValueError('Nonfinite geometry input')
    if not np.allclose(np.linalg.norm(d, axis=1), 1, atol=1e-12):
        raise ValueError('Directions must be unit vectors; do not silently normalize')
    Q = np.eye(3) if rotation is None else np.asarray(rotation, float)
    if not np.allclose(Q.T @ Q, np.eye(3), atol=1e-12) or np.linalg.det(Q) < 0:
        raise ValueError('Rotation must be right-handed orthonormal')
    return np.vstack(((d @ Q.T).T, (np.cross(p - c, d) @ Q.T).T))


def body_case(parameters, case):
    src = parameters['mass_references']['WP03_service_allocated_subset']
    mass = src['mass_kg']
    center = np.array(src['center_of_mass_S_m'])
    inertia = np.array(src['inertia_about_COM_S_kg_m2'])
    if case['body_model'] == 'WP03_allocated_service_subset':
        H = inertia @ np.array(case['initial_omega_S_rad_s'])
        label = 'WP03_ALLOCATED_SUBSET_AND_ASSUMED_RATE_NOT_V6_MASS'
    else:
        target = next(t for t in parameters['mass_references']['targets']
                      if t['id'] == case['target_id'])
        mt = target['mass_kg']
        ct = np.array(case['target_COM_S_m'])
        Rst = np.array(case['target_rotation_S_body'])
        combined_c = (mass * center + mt * ct) / (mass + mt)
        inertia = (inertia + steiner(mass, center - combined_c)
                   + Rst @ np.array(target['I_C_body_kg_m2']) @ Rst.T
                   + steiner(mt, ct - combined_c))
        mass, center = mass + mt, combined_c
        direction = np.array(case['H_direction_S_unit'], float)
        assert abs(np.linalg.norm(direction) - 1) < 1e-12
        H = case['H_magnitude_Nms'] * direction
        label = 'HYBRID_SENSITIVITY_NOT_RECOMPUTED_CAPTURE_STATE'
    demand = np.r_[case['linear_impulse_target_S_Ns'], -H]
    return dict(scope=label, mass_kg=mass, COM_S_m=center.tolist(),
                I_C_S_kg_m2=inertia.tolist(), H_initial_C_S_Nms=H.tolist(),
                demand_impulse_C_S=demand.tolist(),
                initial_rate_from_assumed_H_rad_s=np.linalg.solve(inertia, H).tolist(),
                actual_V6_state=False)


def allocate(B, demand, fmax, total_impulse, duration, idle_W, per_jet_W,
             available_W, duty_cap, failed=(), max_time_s=5):
    """Minimize T using per-jet impulses u_i >=0; no discrete pulse model.

    B u = [J_linear; Delta H_C]; u_i <= F_i*T;
    sum u <= shared delivered impulse; sum(u_i/F_i) <= duty_cap*T;
    sum(P_i*u_i/F_i) <= (P_available-P_idle)*T.
    All power coefficients and concurrency are declared DESIGN assumptions.
    """
    B, demand = np.asarray(B, float), np.asarray(demand, float)
    count = B.shape[1]
    f = np.broadcast_to(np.asarray(fmax, float), (count,)).copy()
    powers = np.broadcast_to(np.asarray(per_jet_W, float), (count,))
    if available_W < idle_W:
        return dict(status='INFEASIBLE_ASSUMED_POWER_BELOW_IDLE', feasible=False)
    if np.any(f <= 0) or total_impulse < 0 or duration <= 0 or duty_cap < 0:
        raise ValueError('Invalid actuator/resource input')
    eq = np.column_stack((B, np.zeros(6)))
    ub = np.column_stack((np.eye(count), -f))
    rhs = np.zeros(count)
    ub = np.vstack((ub, np.r_[np.ones(count), 0],
                    np.r_[1 / f, -duty_cap],
                    np.r_[powers / f, -(available_W - idle_W)]))
    rhs = np.r_[rhs, total_impulse, 0, 0]
    bounds = [(0, 0 if i in failed else None) for i in range(count)]
    bounds.append((0, duration))
    objective = np.r_[np.zeros(count), 1]
    solution = linprog(objective, A_ub=ub, b_ub=rhs, A_eq=eq, b_eq=demand,
                       bounds=bounds, method='highs-ds',
                       options={'time_limit': max_time_s})
    result = dict(status='RELAXED_LP_FEASIBLE' if solution.success else
                  ('INFEASIBLE_UNDER_DESIGN_ASSUMPTIONS' if solution.status == 2
                   else 'UNKNOWN_SOLVER_DID_NOT_ESTABLISH_RESULT'),
                  feasible=bool(solution.success), scipy_status=int(solution.status),
                  solver_message=solution.message)
    if not solution.success:
        return result
    u, T = solution.x[:-1], float(solution.x[-1])
    assert T > 0
    eq_error = float(np.max(np.abs(B @ u - demand)))
    inequality_violation = float(max(0, np.max(ub @ solution.x - rhs)))
    assert eq_error < 1e-8 and inequality_violation < 1e-8
    result.update(time_lower_bound_in_relaxed_model_s=T,
                  per_jet_impulse_Ns=u.tolist(), total_impulse_used_Ns=float(u.sum()),
                  impulse_remaining_Ns=float(total_impulse - u.sum()),
                  per_jet_mean_force_N=(u/T).tolist(),
                  per_jet_equivalent_duty=(u/(T*f)).tolist(),
                  sum_equivalent_duty=float(np.sum(u/(T*f))),
                  mean_power_design_model_W=float(idle_W + powers @ (u/(T*f))),
                  residual_linear_impulse_Ns=(B @ u - demand)[:3].tolist(),
                  residual_angular_impulse_Nms=(B @ u - demand)[3:].tolist(),
                  max_equality_residual=eq_error,
                  max_inequality_violation=inequality_violation,
                  operational_or_time_domain_pass=False)
    return result


def run_case(parameters, array, case, force_scale=1, failed_override=None):
    candidate = next(c for c in parameters['candidates']
                     if c['id'] == array['candidate_resource_id'])
    body = body_case(parameters, case)
    B = wrench_matrix(array['positions_S_m'], array['directions_S_unit'],
                      body['COM_S_m'], array['directions_kind'])
    J = candidate['total_impulse_Ns'] * case['resource_remaining_fraction']
    f = candidate['nominal_thrust_N'] * force_scale
    failed = case['failed_jet_indices'] if failed_override is None else failed_override
    args = dict(B=B, demand=body['demand_impulse_C_S'], fmax=f, total_impulse=J,
                duration=case['time_limit_s'], idle_W=candidate['standby_W'],
                per_jet_W=array['linear_incremental_power_per_on_jet_W'],
                available_W=array['assigned_mean_power_W'],
                duty_cap=array['simultaneous_equivalent_duty_cap'], failed=failed,
                max_time_s=parameters['numerics']['max_lp_s'])
    result = allocate(**args)
    unlimited_resource = allocate(**dict(args, total_impulse=1e6))
    relaxed_window = allocate(**dict(args, duration=1e7))
    scale = parameters['numerics']['length_scale_for_dimensionless_wrench_m']
    singular = np.linalg.svd(np.vstack((B[:3], B[3:]/scale)), compute_uv=False)
    rank = int(np.sum(singular > max(singular)*1e-12))
    available_columns = [i for i in range(B.shape[1]) if i not in failed]
    scaled_active = np.vstack((B[:3, available_columns], B[3:, available_columns]/scale))
    active_rank = int(np.linalg.matrix_rank(scaled_active, tol=1e-12))
    output = dict(case=case['id'], array=array['id'], candidate_resource=candidate['id'],
                  layout_is_vendor=False, body=body, B_force_and_moment=B.tolist(),
                  dimensionless_wrench_length_scale_m=scale,
                  scaled_singular_values=singular.tolist(), rank=rank,
                  active_rank_after_failure=active_rank,
                  rank_is_not_nonnegative_constrained_reachability=True,
                  condition_number_on_nonzero_singular_subspace=float(singular[0]/singular[rank-1]),
                  failed_jet_indices=list(failed), nominal_force_scale=force_scale,
                  total_impulse_budget_Ns=J, time_limit_s=case['time_limit_s'], result=result,
                  without_total_impulse_limit_diagnostic=unlimited_resource,
                  without_original_time_limit_diagnostic=relaxed_window,
                  MIB_Ns=candidate['MIB_Ns'], nominal_MIB_over_thrust_s=candidate['MIB_Ns']/f,
                  MIB_is_not_valve_response_or_command_duration=True,
                  actual_MIB_schedule_status='UNKNOWN_DISCRETE_PULSE_SCHEDULER_NOT_EVALUATED',
                  plume_status='UNKNOWN_NO_BODY_OR_TARGET_PLUME_EVALUATION',
                  actual_vendor_or_V6_capacity_status='UNKNOWN')
    if result['feasible']:
        output['continuous_solution_in_MIB_units'] = (np.array(result['per_jet_impulse_Ns'])/candidate['MIB_Ns']).tolist()
    return output


def self_checks():
    checks = []
    def check(name, condition):
        checks.append(dict(id=name, passed=bool(condition)))
        assert condition, name
    p = [[0, 1, 0]]
    B = wrench_matrix(p, [[1, 0, 0]], [0, 0, 0], 'spacecraft_force')
    check('cross_product_sign', np.allclose(B[:,0], [1,0,0,0,0,-1]))
    check('plume_is_opposite_force', np.allclose(
        B, wrench_matrix(p, [[-1,0,0]], [0,0,0], 'exhaust_axis')))
    try:
        wrench_matrix(p, [[1,0,0]], [0,0,0], 'UNKNOWN')
        rejected = False
    except ValueError:
        rejected = True
    check('unknown_arrow_semantics_rejected', rejected)
    c = np.array([.2,.3,.4])
    Bc = wrench_matrix(p, [[1,0,0]], c, 'spacecraft_force')
    check('reference_point_shift', np.allclose(Bc[3:,0], B[3:,0]-np.cross(c,B[:3,0])))
    Q = np.array([[0,-1,0],[1,0,0],[0,0,1]])
    check('rigid_frame_rotation', np.allclose(
        wrench_matrix(p, [[1,0,0]], c, 'spacecraft_force', Q), np.vstack((Q@Bc[:3],Q@Bc[3:]))))
    matrix = np.eye(6)
    options = dict(B=matrix, demand=[1,0,0,0,0,0], fmax=1,
                   total_impulse=2, duration=10, idle_W=.25,
                   per_jet_W=1, available_W=2.25, duty_cap=2)
    check('positive_control_feasible', allocate(**options)['feasible'])
    check('full_rank_not_positive_cone', not allocate(**dict(options,demand=[-1,0,0,0,0,0]))['feasible'])
    check('fewer_than_six_jets_can_meet_a_specific_task', allocate(**dict(options,B=matrix[:,:5]))['feasible'])
    check('missing_total_impulse_not_multiplied', not allocate(**dict(options,total_impulse=.5))['feasible'])
    check('failed_only_required_jet_infeasible', not allocate(**dict(options,failed=[0]))['feasible'])
    check('time_limit_enforced', not allocate(**dict(options,duration=.5))['feasible'])
    check('idle_power_limit_enforced', not allocate(**dict(options,available_W=.2))['feasible'])
    slower = allocate(**dict(options,available_W=.75))
    check('common_power_changes_time', slower['feasible'] and abs(slower['time_lower_bound_in_relaxed_model_s']-2)<1e-9)
    check('MIB_unit_conversion', abs(.05e-3-5e-5)<1e-18 and abs(.50e-3-5e-4)<1e-18)
    check('parallel_axis_positive_semidefinite', min(np.linalg.eigvalsh(steiner(3,[1,2,3])))>-1e-12)
    return checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inputs', type=Path, default=ROOT/'inputs/PROPULSION_SCREEN_INPUTS.json')
    parser.add_argument('--output', type=Path, default=ROOT/'results/PROPULSION_SCREEN_RESULTS.json')
    args = parser.parse_args()
    parameters = json.loads(args.inputs.read_text(encoding='utf-8'))
    for source in parameters['source_bindings'].values():
        assert sha(source['path']) == source['sha256'], 'Pinned input changed: '+source['path']
    checks = self_checks()
    results = [run_case(parameters, array, case)
               for array in parameters['design_assumption_arrays']
               for case in parameters['conditional_cases']]
    array = parameters['design_assumption_arrays'][1]
    captured = parameters['conditional_cases'][1]
    sensitivity = [run_case(parameters, array, captured, failed_override=[0]),
                   run_case(parameters, array, captured, force_scale=.8)]
    box = [110,160,75]
    envelopes = []
    for candidate in parameters['candidates']:
        fits = [list(o) for o in itertools.permutations(candidate['envelope_mm'])
                if all(a<=b for a,b in zip(o,box))]
        envelopes.append(dict(candidate=candidate['id'], body_envelope_mm=candidate['envelope_mm'],
                              reference_shared_box_mm=box, body_only_axis_aligned_fit=bool(fits),
                              fitting_orientations_mm=fits,
                              actual_V6_installation_credit=False,
                              scope='Optional shared-box body-only screen, not a re-test of current external legacy-MiPS V6 placement'))
    actual = [dict(candidate=c['id'], part=c['part'], status='UNKNOWN_INPUTS_MISSING',
                   missing=parameters['actual_missing_inputs'], vendor_layout_lp_executed=False)
              for c in parameters['candidates']]
    Href = parameters['task_reference']['historical_capture']['H_combined_COM_magnitude_Nms_csv']
    Tref = parameters['task_reference']['historical_detumble_time_s']
    scalar = []
    for lever in (.05, .10, .17):
        scalar.append(dict(assumed_each_jet_effective_arm_m=lever,
                           required_shared_total_impulse_Ns=Href/lever,
                           required_each_jet_force_N=Href/(2*lever*Tref),
                           two_jet_nominal_10mN_time_lower_s=Href/(2*lever*.01),
                           assumption='Ideal balanced pair, each jet lever r; tau=2*F*r, total J=sum both jets=H/r; not an OEM placement',
                           candidate_necessary_resource_tests={c['id']:Href/lever<=c['total_impulse_Ns']
                                                               for c in parameters['candidates']}))
    assert all(x['status']=='UNKNOWN_INPUTS_MISSING' for x in actual)
    checks.append(dict(id='actual_vendor_missing_inputs_fail_closed',passed=True))
    output = dict(schema='SEI_PROPULSION_SCREEN_RESULTS_V1',
                  status='CONDITIONAL_LP_COMPLETED__ACTUAL_V6_AND_VENDOR_CAPABILITY_UNKNOWN',
                  inputs_sha256=sha(args.inputs), script_sha256=sha(__file__),
                  numpy_version=np.__version__, scipy_version=scipy.__version__,
                  method='scipy.linprog highs-ds; static integrated-wrench LP, no ODE or historical solver import',
                  source_binding_count=len(parameters['source_bindings']),
                  actual_candidate_results=actual, conditional_results=results,
                  additional_sensitivity_results=sensitivity, envelope_screens=envelopes,
                  historical_scalar_balanced_pair_references=scalar,
                  self_checks=checks, self_check_count=len(checks),
                  source_inputs_unchanged_after=True,
                  no_credit=dict(flight_selection_frozen=False, mission_pass=False,
                                 actual_V6_mass_updated=False, pulse_schedule_validated=False,
                                 closed_loop_stability=False, plume_or_thermal_pass=False,
                                 hardware_test=False, historical_gate_modified=False))
    for source in parameters['source_bindings'].values():
        assert sha(source['path']) == source['sha256']
    args.output.write_text(json.dumps(output,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=output['status'], self_checks=len(checks),
                         cases=[dict(array=x['array'],case=x['case'],status=x['result']['status'],
                                     time_s=x['result'].get('time_lower_bound_in_relaxed_model_s'),
                                     impulse_Ns=x['result'].get('total_impulse_used_Ns')) for x in results],
                         sensitivity=[dict(failed=x['failed_jet_indices'],force_scale=x['nominal_force_scale'],
                                           status=x['result']['status']) for x in sensitivity]),ensure_ascii=False))


if __name__ == '__main__':
    main()
