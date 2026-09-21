"""V31 conditional power/phase consumer with explicit SI input boundaries.

Pure algebra only. Unknown stopping, charging and motor parameters are not zero.
The unchanged V30 constant-power branch solver is imported only after its SHA check.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import math

P = Path(__file__).resolve().parents[1]
A = P.parent
SIGMA_W_M2_K4 = 5.670374419e-8

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def source_check():
    lock = read(P / 'inputs/ROOT_SOURCE_LOCK.json')
    errors = [r['path'] for r in lock['files']
              if hashlib.sha256(Path(r['path']).read_bytes()).hexdigest() != r['sha256']]
    if errors:
        raise ValueError('SOURCE_DRIFT: ' + repr(errors))
    return len(lock['files'])

def load_solver():
    source_check()
    spec = importlib.util.spec_from_file_location('v31_unchanged_branch_solver', A / 'tools/shared_battery_path.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def finite(value, name, low=0.0, strictly=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('INVALID_' + name)
    if (value <= low if strictly else value < low):
        raise ValueError('OUT_OF_DOMAIN_' + name)
    return float(value)

def input_quantity(item, expected_unit):
    """No implicit mm/m or rpm/rad/s conversion; callers must state canonical units."""
    if item.get('unit') != expected_unit:
        raise ValueError('UNIT_MISMATCH: expected ' + expected_unit)
    if item.get('value') is None:
        return None
    return finite(item['value'], expected_unit)

def operating_point(arm_path_W, pack_V, shared_R_ohm, eta_main, source=None, solver=None, brake_bias_W=None):
    for value, name in [(arm_path_W, 'ARM_POWER_W'), (shared_R_ohm, 'SHARED_R_OHM')]:
        finite(value, name)
    finite(pack_V, 'PACK_V', strictly=True)
    finite(eta_main, 'EFFICIENCY', strictly=True)
    if eta_main > 1:
        raise ValueError('EFFICIENCY_EXCEEDS_ONE')
    s = source or read(P / 'inputs/V30_ELECTRICAL_SOURCE.json')
    e = s['electrical']
    solver = solver or load_solver()
    r = dict(e['main_R_components_ohm'])
    r['Q201_25C'] *= 2.0
    r['copper_20C'] *= 1 + 0.00393 * (100 - 20)
    main_R = sum(r.values())
    if brake_bias_W is None:
        brake_bias_W = input_quantity(read(P/'inputs/LOAD_TRADE_INPUTS_V1.json')['brake_bias_W'], 'W')
    finite(brake_bias_W, 'BRAKE_BIAS_W')
    main_output_W = arm_path_W + brake_bias_W
    main_input_W = main_output_W / eta_main + e['startup_input_W']
    aux_input_W = e['aux_output_W'] / e['eta_aux']
    point = solver.solve(pack_V, shared_R_ohm, main_R, r['fuse_typical_20C'],
                         e['aux_R_ohm'], main_input_W, aux_input_W,
                         controller_a=0.003, main_leak_a=0.003)
    point.update(arm_path_W=arm_path_W, pack_V=pack_V, shared_R_ohm=shared_R_ohm,
                 eta_main=eta_main, main_output_W=main_output_W,
                 input_units='V, ohm, W; temperature reference 100 degC; solver SI boundary',
                 scope='DECLARED_STEADY_LOAD_SENSITIVITY_NOT_MOTOR_OR_BMS_PREDICTION',
                 hardware_ready=False, thermal_closed=False, arm_internal_heat_W=None)
    point.update(measurement_plane='CHB_OUTPUT_ARM_PATH_ALLOCATION_AFTER_SEPARATE_BRAKE_BIAS',
                 actual_arm_connector_power_W=None, downstream_distribution_loss_W=None,
                 brake_bias_allocation_W=brake_bias_W)
    if not point['equilibrium_found']:
        return point
    chb_loss_W = main_output_W * (1 / eta_main - 1)
    nonarm_heat_W = (sum(point['heat_W'].values()) + chb_loss_W + e['startup_input_W']
                    + aux_input_W + brake_bias_W)
    residual_W = point['input_power_W'] - arm_path_W - nonarm_heat_W
    if abs(residual_W) > 1e-7:
        raise ArithmeticError('POWER_ACCOUNTING_MISMATCH')
    vf = point['main_fused_V']
    im = point['main_A']
    screens = e['protection_screens']
    uv, ov, il = (screens[k] for k in ['UVLO_falling_screen_V', 'OVLO_rising_screen_V', 'current_limit_screen_A'])
    if vf < uv[0]: state = 'BLOCKED_BY_UVLO_SCREEN'
    elif vf > ov[1]: state = 'BLOCKED_BY_OVLO_SCREEN'
    elif im > il[1]: state = 'BLOCKED_BY_CURRENT_SCREEN'
    elif vf < uv[1] or vf > ov[0] or im > il[0]: state = 'PROTECTION_CORNER_DEPENDENT'
    else: state = 'CONDITIONAL_STATIC_POINT_STARTUP_UNVERIFIED'
    point.update(CHB_loss_W=chb_loss_W, known_nonarm_heat_W=nonarm_heat_W,
                 auxiliary_input_assumed_all_heat_within_system=True,
                 heat_is_conditional_budget_not_measurement=True,
                 heat_balance_residual_W=residual_W, protection_class=state,
                 battery_margin_A=e['battery_current_limit_A']-point['battery_A'],
                 Q201_heat_W=im*im*r['Q201_25C'],
                 whole_spacecraft_heat_W=None, candidate_voltage_floor_verified=False)
    return point

def validate_timeline(phases, total_s):
    finite(total_s, 'TOTAL_TIME_S', strictly=True)
    next_time = 0.0
    seen = set()
    for p in phases:
        dt = finite(p['duration_s'], 'PHASE_TIME_S', strictly=True)
        start = finite(p['start_s'], 'PHASE_START_S')
        if p['id'] in seen or abs(start-next_time) > 1e-9:
            raise ValueError('DUPLICATE_OR_NONCONTIGUOUS_PHASE')
        if p['power_class'] not in ['motion', 'hold', 'standby', 'unbound_stop']:
            raise ValueError('UNKNOWN_POWER_CLASS')
        next_time = start + dt
        seen.add(p['id'])
    if abs(next_time-total_s) > 1e-9:
        raise ValueError('PERIOD_MISMATCH')
    return True

def phase_ledger(mission, motion_W, hold_W, standby_W, pack_V=25.2,
                 shared_R_ohm=0.01, eta_main=0.85, initial_Wh=None):
    orbit = mission['orbital_reference']
    validate_timeline(orbit['phases'], orbit['period_s'])
    for value, name in [(motion_W, 'MOTION_W'), (hold_W, 'HOLD_W'), (standby_W, 'STANDBY_W')]:
        finite(value, name)
    points = {k: operating_point(v, pack_V, shared_R_ohm, eta_main)
              for k, v in dict(motion=motion_W, hold=hold_W, standby=standby_W).items()}
    rows, unknowns = [], []
    known_Wh = known_heat_Wh = heater_Wh = prefix_Wh = 0.0
    prefix_open = True
    screen_issues = []
    for phase in orbit['phases']:
        if phase['power_class'] == 'unbound_stop':
            unknowns.append(phase['id'])
            prefix_open = False
            rows.append(dict(id=phase['id'], duration_s=phase['duration_s'], energy_Wh=None,
                             heat_Wh=None, status='STOPPING_AND_REGENERATION_UNBOUND'))
            continue
        point = points[phase['power_class']]
        if not point['equilibrium_found']:
            unknowns.append(phase['id'])
            prefix_open = False
            rows.append(dict(id=phase['id'], energy_Wh=None, status='NO_ALGEBRAIC_POINT'))
            continue
        heater_output = phase.get('heater_thermal_output_W', 0.0)
        if heater_output is None:
            heater_input = None
        else:
            finite(heater_output, 'HEATER_OUTPUT_W')
            heater_eta = phase.get('heater_efficiency') if heater_output > 0 else 1.0
            finite(heater_eta, 'HEATER_EFFICIENCY', strictly=True)
            if heater_eta > 1:
                raise ValueError('INVALID_HEATER_EFFICIENCY')
            heater_input = heater_output / heater_eta
        dt = phase['duration_s']
        # Heater has no installed supply path. Keep the ideal extra budget separate;
        # never attach an unchanged standby protection decision to the combined load.
        E = point['input_power_W'] * dt / 3600
        Q = point['known_nonarm_heat_W'] * dt / 3600
        known_Wh += E
        known_heat_Wh += Q
        if heater_input is not None:
            heater_Wh += heater_input * dt / 3600
        if heater_input is None or heater_input > 0:
            unknowns.append(phase['id']+'_HEATER_SUPPLY_PATH')
            screen_issues.append(dict(phase=phase['id'], status='HEATER_COMBINED_PROTECTION_NOT_EVALUATED'))
        if prefix_open:
            prefix_Wh += E
        if point['protection_class'] != 'CONDITIONAL_STATIC_POINT_STARTUP_UNVERIFIED':
            screen_issues.append(dict(phase=phase['id'], status=point['protection_class']))
        rows.append(dict(id=phase['id'], duration_s=dt, energy_Wh=E, known_nonarm_heat_Wh=Q,
                         base_input_power_W=point['input_power_W'],
                         heater_ideal_extra_input_Wh=None if heater_input is None else heater_input*dt/3600,
                         heater_supply_path_verified=False,
                         combined_load_protection_status=None if heater_input is None or heater_input>0 else point['protection_class'],
                         status='HYPOTHETICAL_CONSTANT_VOLTAGE_POINT',
                         after_unbound_transition=not prefix_open))
    return dict(status='PARTIAL_PHASE_SUM_FULL_MISSION_UNKNOWN', rows=rows, unknown_phases=unknowns,
                known_phase_subtotal_Wh=known_Wh, known_nonarm_heat_subtotal_Wh=known_heat_Wh,
                prefix_before_first_unknown_Wh=prefix_Wh, heater_ideal_extra_budget_Wh=heater_Wh,
                known_subtotal_plus_known_ideal_heater_budget_Wh=known_Wh+heater_Wh,
                heater_budget_is_not_a_solved_supply_branch=True,
                full_cycle_energy_Wh=None, regenerated_energy_Wh=None, solar_recharge_Wh=None,
                initial_Wh=initial_Wh,
                initial_minus_known_subtotal_Wh=None if initial_Wh is None else initial_Wh-known_Wh,
                full_cycle_battery_remaining_Wh=None, protection_issues=screen_issues,
                hardware_ready=False, closed_orbit_energy=False,
                note='Subtotal after missing transition is arithmetic only, not a propagated executable state; no charge credit, no zero-filled stopping energy.')

def ideal_radiating_area_m2(heat_W, radiator_K, sink_K, emissivity, absorbed_W_per_m2=0):
    finite(heat_W, 'HEAT_W')
    finite(radiator_K, 'RADIATOR_K', strictly=True)
    finite(sink_K, 'SINK_K')
    finite(emissivity, 'EMISSIVITY', strictly=True)
    finite(absorbed_W_per_m2, 'ABSORBED_FLUX')
    if emissivity > 1:
        raise ValueError('EMISSIVITY_EXCEEDS_ONE')
    net_flux = emissivity*SIGMA_W_M2_K4*(radiator_K**4-sink_K**4)-absorbed_W_per_m2
    if net_flux <= 0:
        raise ValueError('NO_NET_RADIATIVE_REJECTION')
    return heat_W/net_flux
