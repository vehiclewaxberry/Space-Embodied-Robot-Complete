"""Source-bound offline integration checks. No I/O to equipment; no OEM packets.

The catalogue bounds are screening values, not a delivered hardware ICD.
"""
import math

LOCKED_SHA='86d9f4b73df5948fa89a11d83e7f25979530173ee4d79c65cdb30b642216c088'

def finite(x):
    return isinstance(x,(float,int)) and not isinstance(x,bool) and math.isfinite(x)

def source_config(battery_min_V, regulator, channel, output_V, option_sheet_bound=False):
    errors=[]
    if not all(finite(v) for v in (battery_min_V,output_V)):
        return {'status':'UNKNOWN','issues':['FINITE_SOURCE_VALUES_REQUIRED']}
    if output_V > 8 and (regulator != 0 or channel not in (1,6)):
        errors.append('PDU_HIGH_REGULATED_OUTPUT_REQUIRES_REG0_CH1_OR_CH6')
    if output_V >= battery_min_V-1.5:
        errors.append('PDU_REQUIRES_MORE_THAN_1_5V_INPUT_HEADROOM')
    if not (9 <= output_V <= 12.6): errors.append('NOMINAL_SOURCE_OUTSIDE_CPOD_RANGE')
    return {'status':'REJECT' if errors else ('BOUND_CONFIG_ONLY' if option_sheet_bound else 'UNKNOWN'),
            'issues':errors if errors else ([] if option_sheet_bound else ['SHIPPED_OPTION_NOT_BOUND']),
            'channel_total_current_A_catalog_max':2.0,
            'channel_1_same_net_positive_pins':[1,3],
            'channel_1_return_pins':[2,4],
            'two_positive_pins_do_not_double_channel_limit':True,
            'energization_allowed':False}

def supply_screen(source_min_V,source_max_V,negative_transient_V,positive_transient_V,loop_resistance_hot_ohm,power_W=5.0):
    """One constant-power catalogue operating scope only, not startup/heater.

    Use I_upper=P/V_load_min for a conservative cable-drop bound once the
    resulting terminal lower bound itself proves V_load >= V_load_min.
    """
    vals=(source_min_V,source_max_V,negative_transient_V,positive_transient_V,loop_resistance_hot_ohm,power_W)
    if not all(finite(v) for v in vals):
        return {'status':'UNKNOWN','issues':['BOUNDED_SOURCE_TRANSIENT_AND_HOT_LOOP_REQUIRED'],'energization_allowed':False}
    if source_min_V > source_max_V or any(v<0 for v in vals[2:]) or source_min_V<=0:
        return {'status':'REJECT','issues':['INVALID_BOUND_INPUTS'],'energization_allowed':False}
    if power_W > 5:
        return {'status':'UNKNOWN','issues':['LOAD_SCOPE_EXCEEDS_PUBLISHED_TWO_THRUSTER_5W'],'energization_allowed':False}
    current_upper=power_W/9.0
    lo=source_min_V-negative_transient_V-current_upper*loop_resistance_hot_ohm
    hi=source_max_V+positive_transient_V  # no helpful drop credited at idle
    passed=lo >= 9 and hi <= 12.6 and current_upper<=2
    return {'status':'PASS_CONDITIONAL_STEADY_SCOPE' if passed else 'REJECT',
            'terminal_voltage_bounds_V':[lo,hi],'current_upper_A':current_upper,
            'power_scope':'catalogue maximum for two thrusters; startup/heater/concurrent states unbound',
            'startup_heater_peak_covered':False,'energization_allowed':False}

def pulse_screen(requested_impulse_Ns,source_sha=LOCKED_SHA):
    if source_sha != LOCKED_SHA:
        return {'status':'REJECT','issues':['SOURCE_CONFIGURATION_MISMATCH'],'oem_command':None}
    if not finite(requested_impulse_Ns) or requested_impulse_Ns <= 0:
        return {'status':'REJECT','issues':['POSITIVE_FINITE_IMPULSE_REQUIRED'],'oem_command':None}
    mib=0.0005
    if requested_impulse_Ns < mib:
        return {'status':'REJECT','issues':['REQUEST_BELOW_CATALOGUE_MINIMUM_IMPULSE'],'oem_command':None}
    return {'status':'UNKNOWN_OEM_PULSE_LAW',
            'requested_impulse_Ns':requested_impulse_Ns,
            'steady_rectangular_equivalent_duration_s':[requested_impulse_Ns/0.012,requested_impulse_Ns/0.008],
            'nominal_rectangular_equivalent_duration_s':requested_impulse_Ns/0.01,
            'duration_is_not_command_width_or_guaranteed_impulse':True,
            'valve_response_s_strict_upper':0.01,'oem_command':None}

def mounting_screen(proposed_thread, hole_centers_mm=None, thread_depth_mm=None, allowable_loads=None):
    if proposed_thread != '.112-40 UNC-2B':
        return {'status':'REJECT','issues':['OEM_MOUNTING_THREAD_MISMATCH'],'manufacturing_allowed':False}
    missing=[name for name,value in (('hole_centers_mm',hole_centers_mm),('thread_depth_mm',thread_depth_mm),('allowable_loads',allowable_loads)) if value is None]
    return {'status':'UNKNOWN' if missing else 'UNVERIFIED_ICD_EVIDENCE',
            'issues':missing or ['CONTROLLED_DRAWING_AND_FASTENER_PROOF_REQUIRED'],
            'manufacturing_allowed':False}

def wrench_model(contract):
    """Never synthesize a layout from jet count or artwork."""
    if contract.get('source_sha256') != LOCKED_SHA:
        return {'status':'REJECT','matrix':None,'issues':['SOURCE_CONFIGURATION_MISMATCH']}
    required=('configuration_binding','nozzle_xyz_m','force_directions_unit','allowed_concurrency','installation_transform','combined_com_m','command_map')
    missing=[k for k in required if contract.get(k) is None]
    return {'status':'UNKNOWN_INPUTS_MISSING' if missing else 'ICD_REVIEW_REQUIRED',
            'matrix':None,'issues':missing or ['SUPPLIED_ICD_REQUIRES_INDEPENDENT_VALIDATION'],
            'physical_commands_emitted':0}
