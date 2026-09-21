"""Rebuild only this directory's V31 evidence; read historical sources only."""
import hashlib
import json
from pathlib import Path
from actuator_model import (synthetic_reference, wrench_matrix, matrix_rank,
                            wheel_storage_check, wheel_direction_capacity,
                            allocate_reference_impulse, current_cpod_capability)

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in HERE.parents if (p/'PROJECT_MAP.md').exists())
SOURCES = {
    'legacy_threshold_registry': '30_simulation/e15_core_coverage/config/threshold_registry_core_v1.yaml',
    'threshold_original_semantics': '20_engineering/config/grasp_evaluator/hard_constraints_v1.yaml',
    'legacy_scalar_wheel_tier': '20_engineering/config/mission_feasibility/scan_v0.yaml',
    'control_axis_box_and_external_budget': '20_engineering/config/attitude_stab/attitude_stab_v0.yaml',
    'control_mapping_consumer': '30_simulation/control_02_base_attitude/src/config_loader.py',
    'control_separate_physical_consumers': '30_simulation/control_02_base_attitude/src/phase_b.py',
    'control_scope': '30_simulation/control_02_base_attitude/README.md',
    'current_catalog_propulsion_screen': '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation/coupled_closure/PROPULSION_RESOURCE_SCREEN.json',
}


def source_bindings():
    result = {}
    for key, rel in SOURCES.items():
        raw = (ROOT/rel).read_bytes()
        result[key] = {'path_relative_to_workspace': rel, 'bytes': len(raw),
                       'sha256_raw': hashlib.sha256(raw).hexdigest()}
    return result


def build():
    bindings = source_bindings()
    previous = HERE/'SOURCE_BINDINGS.json'
    if previous.exists() and json.loads(previous.read_text(encoding='utf-8')) != bindings:
        raise RuntimeError('source drift: preserve V31 evidence; explicit new revision required')
    ref = synthetic_reference()
    B = wrench_matrix(ref['nozzles'])
    positive_only = synthetic_reference()
    positive_only['nozzles'] = [n for n in positive_only['nozzles'] if n['force_sign'] == 1]
    cases = {
        'axis_storage_accepted': wheel_storage_check([0.08, 0.0, 0.0]),
        'legacy_scalar_false_positive_rejected': wheel_storage_check([0.25, 0, 0]),
        'prebiased_storage_rejected': wheel_storage_check([0.03, 0, 0], [0.09, 0, 0]),
        'axis_direction_capacity': wheel_direction_capacity([1, 0, 0]),
        'diagonal_direction_capacity': wheel_direction_capacity([1, 1, 1]),
        'pure_torque_pair_accepted': allocate_reference_impulse([0, 0, 0, 0, 0, 0.00036], 1, ref),
        'rank6_unilateral_negative_force_rejected': allocate_reference_impulse([-0.0012, 0, 0, 0, 0, 0], 1, positive_only),
        'rank6_four_simultaneous_jets_rejected': allocate_reference_impulse([0, 0, 0, 0.00036, 0.00036, 0], 1, ref),
        'rank6_subminimum_pulse_rejected': allocate_reference_impulse([0, 0, 0, 0, 0, 0.00001], 1, ref),
        'rank6_force_window_exceeded_rejected': allocate_reference_impulse([0, 0, 0, 0, 0, 0.0036], 0.5, ref),
    }
    contract = {
        'schema': 'WP10_V31_ACTUATOR_SEMANTICS_AND_BOUNDED_CAPABILITY_V1',
        'status': 'RESEARCH_CONTRACT_AND_SYNTHETIC_COUNTEREXAMPLES_ONLY',
        'historical_sources_unchanged': True,
        'wheel_storage': {
            'classification': 'LEGACY_PROVISIONAL_RESEARCH_BOX_NOT_SELECTED_HARDWARE',
            'frame': 'WHEEL_BOX_AXES', 'capacity_per_axis_Nms': [0.1, 0.1, 0.1],
            'legacy_scalar_sum_Nms': 0.3,
            'scalar_sum_is_not_isotropic_directional_capacity': True,
            'equation': 'Hwheel_final = Hwheel_initial + delta_Hwheel; abs(Hwheel_final_i) <= Hmax_i',
            'system_total_angular_momentum_removed_Nms': 0,
            'wheel_axis_installation_matrix': None,
            'current_hardware_model': None, 'current_hardware_verified': False,
            'torque_speed_power_and_slew_constraints_evaluated': False},
        'historical_external_budget': {
            'value_Nms': 5.475, 'historical_anchor_Nms': 3.65, 'factor': 1.5,
            'meaning': 'EXAMPLE_THRUSTER_COUPLE_EXTERNAL_ANGULAR_IMPULSE_BUDGET',
            'is_reaction_wheel_capacity': False, 'is_current_task_requirement': False,
            'is_current_cpod_capability': False,
            'legacy_misleading_key': 'thresholds.wheel_momentum_max_Nms',
            'CTRL02_consumer_key': 'gates.external_removal_capacity_Nms',
            'derivatives': {'lever_m': 0.17, 'Isp_s': 60.0,
                            'thruster_impulse_Ns': 5.475/0.17,
                            'propellant_g': 1000*5.475/0.17/(60*9.80665)},
            'authority': 'PROVISIONAL_UNVERIFIED_HISTORICAL_SCREEN_ONLY'},
        'field_semantic_mapping': [
            {'source': 'legacy_scalar_wheel_tier', 'field': 'actuator_tiers.wheel_capacity_Nms.wheels_large',
             'value': 0.3, 'meaning': 'LEGACY_SCALAR_SUM_TIER_NOT_DIRECTIONAL_BOX'},
            {'source': 'control_axis_box_and_external_budget', 'field': 'stage_b.wheel_capacity_per_axis_Nms',
             'value': [0.1, 0.1, 0.1], 'meaning': 'INTERNAL_STORAGE_AXIS_BOX'},
            {'source': 'threshold_original_semantics', 'field': 'constraints.wheel_momentum_max_Nms',
             'value': 5.475, 'meaning': 'LEGACY_KEY_EXTERNAL_THRUSTER_COUPLE_BUDGET_SEE_SOURCE_COMMENT'},
            {'source': 'control_mapping_consumer', 'field': 'exact_pairs external_removal_capacity_Nms -> wheel_momentum_max_Nms',
             'meaning': 'EXPLICIT_RENAME_WHILE_RETAINING_LEGACY_HASH_AUTHORITY'},
            {'source': 'control_separate_physical_consumers', 'field': 'stage_b wheel box versus gates external_removal_capacity_Nms',
             'meaning': 'WHEEL_CLIP_AND_EXTERNAL_DEMAND_SCALE_ARE_SEPARATE_OPERATIONS'}],
        'actual_C_POD': current_cpod_capability(),
        'synthetic_reference': ref,
        'synthetic_wrench_matrix': {'column_order': [n['id'] for n in ref['nozzles']],
                                   'B': B, 'linear_span_rank': matrix_rank(B),
                                   'top_row_units': 'dimensionless direction; multiply N or N*s',
                                   'bottom_row_units': 'm; multiply N or N*s',
                                   'rank_is_not_positive_cone_or_schedule_feasibility': True,
                                   'positive_direction_only_subarray_rank': matrix_rank(wrench_matrix(positive_only['nozzles']))},
        'case_results': cases,
        'source_bindings': bindings,
        'public_function_interface': {
            'wheel_storage_check': {'input': 'delta_H_Nms[3], initial_H_Nms[3], capacity_per_axis_Nms[3] in wheel-box axes',
                                    'output_key': 'storage_feasible; hardware validity always false'},
            'wheel_direction_capacity': {'input': 'direction[3], initial_H_Nms[3], capacity_per_axis_Nms[3]',
                                         'output_key': 'additional_storage_capacity_Nms'},
            'wrench_matrix': {'input': 'nozzles list: position_m, direction_unit; com_m[3]',
                              'output': '6xN; top force directions, bottom moment arms'},
            'allocate_reference_impulse': {'input': '[Jx,Jy,Jz,Lx,Ly,Lz], window_s, explicit synthetic reference',
                                            'units': ['N*s']*3+['N*m*s']*3,
                                            'output_key': 'plan_feasible_within_declared_constraints',
                                            'scope': 'single simultaneous-pulse plan only; rejected != all schedules impossible'},
            'current_cpod_capability': {'input': 'none', 'output': 'UNKNOWN; no actual wrench matrix or hardware credit'}},
        'whole_system_binding': False, 'physical_tests_executed': False,
        'manufacturing_release': False, 'hardware_io_executed': False,
    }
    # Re-check all source bytes before writing our own derived evidence.
    if source_bindings() != bindings:
        raise RuntimeError('upstream changed during readback')
    for name, value in [('ACTUATOR_CONTRACT.json', contract), ('SOURCE_BINDINGS.json', bindings),
                        ('SYNTHETIC_ARRAY_REFERENCE.json', ref), ('ACTUATOR_CASE_RESULTS.json', cases)]:
        (HERE/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'wheel_counterexamples': 2, 'synthetic_rank': matrix_rank(B),
                      'synthetic_negative_cases': 4, 'actual_C_POD_status': contract['actual_C_POD']['status'],
                      'hardware_io_executed': False}))


if __name__ == '__main__':
    build()
