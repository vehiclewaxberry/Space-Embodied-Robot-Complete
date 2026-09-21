"""Pure arithmetic only. Unknown inputs propagate; no CAD, COM or hardware access."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def nonnegative(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: expected finite number")
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name}: expected finite nonnegative number")
    return value


def rounded_orthogonal_route(route):
    points, radius = route['waypoints'], route['radius_mm']
    nonnegative(radius, 'radius_mm')
    vectors = [[b[j] - a[j] for j in range(3)] for a, b in zip(points, points[1:])]
    lengths = [math.sqrt(sum(x*x for x in v)) for v in vectors]
    if len(lengths) < 2 or any(x <= 0 for x in lengths):
        raise ValueError('Route must contain nonzero segments and at least one bend')
    for a, b in zip(vectors, vectors[1:]):
        if abs(sum(x*y for x, y in zip(a, b))) > 1e-9:
            raise ValueError('This bounded checker requires orthogonal adjacent segments')
    trims = [radius] + [2*radius]*(len(lengths)-2) + [radius]
    residuals = [x-t for x, t in zip(lengths, trims)]
    if min(residuals) < -1e-9:
        raise ValueError('Fillets overlap or exceed a route endpoint')
    bends = len(lengths)-1
    arc_total = bends*math.pi*radius/2
    return {'polyline_segments_mm': lengths, 'polyline_total_mm': sum(lengths),
            'bend_count': bends, 'each_bend_degrees': 90, 'radius_mm': radius,
            'remaining_straights_mm': residuals, 'total_tangent_trim_mm': sum(trims),
            'arc_total_mm': arc_total, 'centerline_length_mm': sum(residuals)+arc_total}


def loop_result(values):
    fields = ['forward_length_mm', 'return_length_mm',
              'forward_resistance_ohm_per_m_at_temperature',
              'return_resistance_ohm_per_m_at_temperature',
              'series_contact_and_protection_resistances_ohm']
    missing = [k for k in fields if values.get(k) is None]
    # Unknown contact count/resistance is null, never an empty sum silently treated as zero.
    if values.get(fields[-1]) == []:
        missing.append('series_contact_and_protection_resistances_ohm: empty list has no evidence')
    out = {'status': 'UNKNOWN', 'missing': missing, 'wire_loop_resistance_ohm': None,
           'contact_and_protection_resistance_ohm': None, 'total_loop_resistance_ohm': None,
           'voltage_drop_v': None, 'loop_dissipation_w': None, 'load_voltage_v': None,
           'formula': 'Rloop=(Lf_mm/1000)*rf+(Lr_mm/1000)*rr+sum(R_each_series_contact_and_protection); dV=I*Rloop; Ploss=I^2*Rloop'}
    if missing:
        return out
    lf, lr, rf, rr = [nonnegative(values[k], k) for k in fields[:4]]
    contacts = values[fields[-1]]
    if not isinstance(contacts, list):
        raise ValueError('Contact resistance set must be a list, or null when unknown')
    rc = sum(nonnegative(x, 'contact resistance') for x in contacts)
    rw = lf/1000*rf + lr/1000*rr
    out.update(status='ARITHMETIC_WITH_SUPPLIED_INPUTS_ONLY', wire_loop_resistance_ohm=rw,
               contact_and_protection_resistance_ohm=rc, total_loop_resistance_ohm=rw+rc)
    current = values.get('actual_current_a')
    if current is not None:
        current = nonnegative(current, 'actual_current_a')
        out.update(voltage_drop_v=current*(rw+rc), loop_dissipation_w=current**2*(rw+rc))
        supply = values.get('source_voltage_v')
        if supply is not None:
            out['load_voltage_v'] = nonnegative(supply, 'source_voltage_v')-out['voltage_drop_v']
    return out


def self_check():
    checks = []
    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)
    unknown = dict.fromkeys(['forward_length_mm', 'return_length_mm',
                            'forward_resistance_ohm_per_m_at_temperature',
                            'return_resistance_ohm_per_m_at_temperature',
                            'series_contact_and_protection_resistances_ohm'])
    check('unknown_resistance_propagates', loop_result(unknown)['total_loop_resistance_ohm'] is None)
    synthetic = {'forward_length_mm': 1000, 'return_length_mm': 2000,
                 'forward_resistance_ohm_per_m_at_temperature': .1,
                 'return_resistance_ohm_per_m_at_temperature': .2,
                 'series_contact_and_protection_resistances_ohm': [.01, .02],
                 'actual_current_a': 2, 'source_voltage_v': 12}
    test = loop_result(synthetic)
    check('synthetic_unequal_return_and_contacts', math.isclose(test['total_loop_resistance_ohm'], .53))
    check('synthetic_voltage_drop', math.isclose(test['voltage_drop_v'], 1.06))
    check('synthetic_heat', math.isclose(test['loop_dissipation_w'], 2.12))
    synthetic['series_contact_and_protection_resistances_ohm'] = []
    check('empty_contacts_not_assumed_zero', loop_result(synthetic)['total_loop_resistance_ohm'] is None)
    check('24v_boundary_is_strict', not (25.5-24 > 1.5))
    check('24v_just_above_boundary', 25.500001-24 > 1.5)
    return {'status': 'PASS', 'checks': checks, 'scope': 'Synthetic arithmetic tests only; no device qualification'}


def emission_compare(run, routes, relative_path):
    p = run/relative_path
    if not p.exists():
        return {'status': 'PENDING_SELECTED_REVISION_EMISSION', 'path': str(p), 'geometry_credit': False}
    d = json.loads(p.read_text(encoding='utf-8'))
    comparisons = []
    for name, route in routes.items():
        value = d.get('routes', {}).get(name, {}).get('actual_curve_length_mm')
        match = (not isinstance(value, bool) and isinstance(value, (int, float))
                 and math.isfinite(value)
                 and math.isclose(value, route['centerline_length_mm'], abs_tol=1e-6, rel_tol=0))
        comparisons.append({'route': name, 'expected_centerline_mm': route['centerline_length_mm'],
                            'emission_field': '/routes/'+name+'/actual_curve_length_mm',
                            'observed_length_mm': value, 'arithmetic_length_match': match})
    return {'status': 'LENGTH_FIELDS_MATCH' if all(x['arithmetic_length_match'] for x in comparisons) else 'PENDING_EXPLICIT_EMISSION_FIELD_BINDING',
            'path': str(p), 'sha256': sha(p), 'comparisons': comparisons,
            'geometry_credit': False, 'note': 'Only compares lengths; parent CAD geometry verification remains separate.'}


def calculate(inputs, run):
    check_result = self_check()
    if inputs['hardware_selected'] is not False:
        raise ValueError('This reference-only work package does not accept actual selection claims')
    for source in inputs['standard_sources']:
        if sha(run/'ecad'/source['file']) != source['sha256']:
            raise ValueError('Standard source hash mismatch: '+source['id'])
    contract_path = Path(inputs['contract_path'])
    if sha(contract_path) != inputs['contract_sha256']:
        raise ValueError('Source contract changed: update the bounded input snapshot explicitly')
    contract = json.loads(contract_path.read_text(encoding='utf-8'))
    if inputs['routes'] != contract['routes']:
        raise ValueError('Route snapshot differs from selected revision contract')
    route_outputs = {}
    for name, route in inputs['routes'].items():
        out = rounded_orthogonal_route(route)
        expected = inputs['expected_centerline_lengths_mm'][name]
        if not math.isclose(out['centerline_length_mm'], expected, abs_tol=1e-9, rel_tol=0):
            raise ValueError('Route length does not match selected revision declared arithmetic')
        od = route['bundle_od_mm']
        out.update(waypoints_mm=route['waypoints'], frame=inputs['frame'],
                   endpoint_kind='ICD_HANDOFF_SECTIONS_NOT_DEVICE_CONNECTORS',
                   nominal_bundle_od_mm=od, bundle_od_status='DESIGN_PLACEHOLDER',
                   nominal_inner_bend_radius_mm=route['radius_mm']-od/2,
                   nominal_inner_radius_to_od=(route['radius_mm']-od/2)/od,
                   reference_3od_inner_radius_margin_mm=route['radius_mm']-od/2-3*od,
                   bend_workmanship_status='UNKNOWN_CABLE_STANDARD_TOLERANCES_NOT_BOUND',
                   cut_length_mm=None, actual_endpoint_binding=False,
                   termination_allowances=inputs['end_termination'][name])
        route_outputs[name] = out
    mips = inputs['mips_reference']
    power = mips['maximum_steady_state_power_w']
    vmin, vmax = mips['voltage_range_v']
    currents = [{'reference_load_terminal_voltage_v': v, 'conditional_current_a': power/v,
                 'basis': 'P/V using legacy 10 W maximum steady-state value; not transient peak certification'}
                for v in [vmin, 12.0, vmax]]
    current_bound = power/vmin
    pdu = inputs['pdu_reference']
    threshold = pdu['candidate_output_v']+pdu['strict_headroom_v']
    condition_samples = [{'reference_battery_min_v': v,
                          'strict_headroom_condition_met': v-pdu['candidate_output_v'] > pdu['strict_headroom_v']}
                         for v in [24.0, 25.5, 25.500001, 28.8, 33.6]]
    loop = loop_result(inputs['power_loop_measured_or_selected'])
    return {'schema': 'WP09_POWER_AND_HARNESS_CONDITIONS_RESULTS_V1',
            'status': 'ARITHMETIC_REPRODUCED__ACTUAL_ELECTRICAL_CLOSURE_NOT_EVALUATED',
            'route_revision': inputs['route_revision'],
            'hardware_selected': False, 'routes': route_outputs,
            'mips_conditional_currents': currents, 'actual_transient_peak_current_a': None,
            'mips_direct_24v_reference_connection_within_catalogue_range': vmin <= 24 <= vmax,
            'pdu_24v': {'battery_min_strictly_greater_than_v': threshold,
                       'condition_samples_only': condition_samples, 'per_channel_limit_a_reference': pdu['per_channel_max_a'],
                       'arithmetic_margin_vs_mips_10w_at_9v_a': pdu['per_channel_max_a']-current_bound,
                       'margin_is_not_interface_compatibility': True, 'actual_option_and_range_validated': False,
                       'parallel_channels_authorized': False},
            'power_loop_actual': loop,
            'geometric_roundtrip_reference': {'one_way_section_m': route_outputs['PROP_PWR']['centerline_length_mm']/1000,
                'equal_forward_return_section_m': 2*route_outputs['PROP_PWR']['centerline_length_mm']/1000,
                'scope': 'Equal forward/return ICD-section-only reference; not actual conductor length or resistance'},
            'conditional_resistance_ceilings': [{'reference_supply_v': v, 'minimum_load_voltage_v': vmin,
                'static_undervoltage_only_loop_resistance_ceiling_ohm': (v-vmin)/current_bound,
                'basis': 'Vload=9 V, I=10/9 A, includes all forward/return/contact/protection resistance; excludes transient, tolerance and thermal qualification'}
                for v in [9.0, 12.0, 12.6]],
            'emission_cross_check': emission_compare(run, route_outputs, inputs['emission_relative_path']),
            'self_checks': check_result, 'complete_electrical_branch_count': 0,
            'manufacturing_release': False, 'energization_allowed_by_this_artifact': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inputs', type=Path, default=Path(__file__).with_name('POWER_CONDITIONS_INPUTS.json'))
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('POWER_CONDITIONS_RESULTS.json'))
    args = parser.parse_args()
    inputs = json.loads(args.inputs.read_text(encoding='utf-8'))
    result = calculate(inputs, Path(__file__).resolve().parent.parent)
    result['input_sha256'] = sha(args.inputs)
    result['script_sha256'] = sha(__file__)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'output': str(args.output), 'self_checks': result['self_checks']['status'],
                      'route_lengths_mm': {k: v['centerline_length_mm'] for k, v in result['routes'].items()},
                      'actual_loop_resistance_ohm': result['power_loop_actual']['total_loop_resistance_ohm'],
                      'emission_cross_check': result['emission_cross_check']['status']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
