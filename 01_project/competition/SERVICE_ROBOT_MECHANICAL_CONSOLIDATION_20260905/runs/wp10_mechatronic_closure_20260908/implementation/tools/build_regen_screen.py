"""Source-bound regeneration screening; no hardware configuration or I/O.

The public DM export is evidence, never a command file to write to a motor.
Unpublished device tolerances and the mission's actual energy remain unknown.
"""
from pathlib import Path
import csv, hashlib, json, math, xml.etree.ElementTree as ET

A = Path(__file__).resolve().parents[1]
S = A / 'sources'

def dump(p, x):
    p.write_text(json.dumps(x, ensure_ascii=False, indent=2), encoding='utf-8')

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

sources = json.loads((S / 'REGEN_SCREEN_SOURCE_MANIFEST.json').read_text())
for s in sources:
    assert s['status'] == 'ACQUIRED' and sha(S / s['file']) == s['sha256']

motors = {}
for name in ['DM4310', 'DM4340P']:
    f = S / (name + '_Default_Parameters.txt')
    fields = {}
    for i, line in enumerate(f.read_text().splitlines(), 1):
        if ':' in line:
            k, v = line.split(':', 1)
            fields[k] = {'value': float(v.strip()), 'line': i}
    motors[name] = dict(source_file=str(f.relative_to(A)), sha256=sha(f),
                        public_fields=fields, as_built_readback=None,
                        application_rule='EVIDENCE_ONLY_DO_NOT_FLASH_DEFAULT_FILE',
                        guaranteed_bus_operating_range_V=None,
                        earliest_OV_trip_V=None, maximum_OV_delay_s=None,
                        absorption_energy_J=None)
    assert fields['OV_Value']['value'] == 32
    assert fields['UV_Value']['value'] == 15

dm = dict(schema='WP10_DM_PUBLIC_VOLTAGE_BINDING_V1', motors=motors,
          nominal_application_bus_V=24,
          source_scope='Seeed public B601-DM defaults; OEM manuals corroborate nominal 24V context, not as-built configuration',
          protocol_VMAX_TMAX_are_not_bus_or_energy_ratings=True,
          OV_disable_is_not_energy_absorption=True,
          default_exports_are_not_safe_commissioning_payloads=True,
          reason='Repeated device identities, SN=0 and TIMEOUT=0 are public file fields, not verified installed settings.',
          revision_conflicts=[
              'DM4340P manual V1.0 p4 separates 24V/48V configurations and recommends OV32/52.',
              'Same manual p5 generic driver section states min20/max65; p23 default UV20. These do not supersede Seeed UV15/OV32.'
          ],
          review='mechanical_intake; read-only official source review; no hardware I/O',
          field_command_emitted=False, full_protection_verified=False)
dump(A / 'power/DM_BUS_VOLTAGE_BINDING.json', dm)

# Source figures are separated from mission quantities and from installed hardware.
declared = dict(normal_bus_V=24, CHB_plus5pct_transient_example_V=24 * 1.05,
                public_nominal_OV_setting_V=32, actual_allowed_peak_bus_V=None,
                motor_trip_tolerance_V=None, regenerative_peak_A=None,
                regenerative_energy_J=None, pulse_duration_s=None,
                repetition_period_s=None, installed_load_side_capacitance_F=None,
                worst_wire_inductance_H=None)

trade = [
    dict(module='ODrive Regen Clamp', choice='NOT_ACCEPTED_AS_SOLE_ABSOLUTE_CLAMP',
         reason='Activation is Vout minus Vin; source-loss operation is not proved by the relative threshold specification.',
         source='sources/odrive_regen_clamp_20260909.html; Electrical table'),
    dict(module='Pololu 3775', choice='NOT_ACCEPTED_FOR_WHOLE_ARM_STOP_ENVELOPE',
         reason='OEM limits use to occasional tens-of-ms pulses; nominal 15W label does not establish the arm stop energy or sustained capability.',
         source='sources/pololu_3775.html'),
    dict(module='AMC SRST50', choice='REJECTED_NOMINAL_THRESHOLD',
         reason='50V standard set point exceeds public DM OV32 nominal setting.',
         source='sources/amc_srst_series.pdf p1'),
    dict(module='Roboteq SR2K60V25R, switch3 30V', choice='NOT_ACCEPTED_AS_COMPLETE_PROTECTION',
         reason='Second 5ohm resistor starts only beyond +2V: nominal dual-load boundary32V coincides with DM OV32. Tolerances and transient margin absent.',
         source='sources/sr2k60v25r_v1_1.pdf pp3,7,10-12'),
    dict(module='Roboteq SR2K60V25R, switch2 25V', choice='CONDITIONAL_REUSE_OPTION_NOT_SELECTED',
         reason='Absolute load-side topology is suitable in principle. CHB24V plus5pct can cross25V; pulse envelope, 0.22K/W heat sink and protection dropout remain unverified.',
         source='sources/sr2k60v25r_v1_1.pdf pp3,7,10-12')
]
with (A / 'power/REGEN_MODULE_TRADE.csv').open('w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=list(trade[0])); w.writeheader(); w.writerows(trade)

roboteq = dict(body_version='1.1 July7 2026', pinout_not_invented=True,
               preset_switch2_V=25, preset_switch3_V=30,
               second_resistor_overdrive_V=2, first_stage_ohm=5, both_stages_ohm=2.5,
               one_stage_resistive_at25V_W=25**2/5,
               full_on_resistive_W_at_nominal27V_boundary=27**2/2.5,
               one_stage_resistive_at30V_W=30**2/5,
               full_on_resistive_W_at_nominal32V_boundary=32**2/2.5,
               boundary_does_not_guarantee_dual_stage_on=True,
               actual_absorbed_power_at_boundary_W=None,
               nominal_dual_stage_to_DM_OV_margin_V=32-(30+2),
               power_rating_is_not_available_power_at_every_voltage=True,
               nominal_continuous_W=110, required_sink_K_per_W=.22,
               source_ambient_C=[0, 40], project_50C_verified=False,
               rated_power_requires_OEM_heatsink_condition=True,
               load_side_added_capacitance_if_selected_uF=1650,
               overload_cutout_C=80, restart_below_C=60,
               I2t_cutout_value=None, fixed_mode_response_time_max_s=None,
               preset_threshold_tolerance_V=None, cold_start_delay_max_s=None,
               input_range_document_conflict='p4 installation24..60V vs p10 table12..60V; do not silently select the wider range',
               alternate_return_path_after_thermal_cutout=None,
               installed=False)

# Analytic counterexamples, not simulations of an installed arm or new science gates.
examples = dict(capacitor_example=dict(C_F=.0008, V_initial=24, V_final=26,
                   added_energy_J=.5*.0008*(26**2-24**2), actual_installed=False),
                rectangular_example=dict(energy_J=50, duration_s=.2, average_W=50/.2,
                   actual_mission_bound=False),
                required_C_without_sink_for_same_example_F=2*50/(26**2-24**2),
                possible_CHB25V_threshold_crossing_V=24*1.05-25,
                single_resistor_W_at_that_example_V=(24*1.05)**2/5,
                no_credit_from_disconnected_ODrive_800uF=True)

# Read the exported native netlist, not only the generator's intended labels.
tree = ET.parse(A / 'ecad/wp10_system.xml')
nets = {(p.get('ref'), p.get('pin')): n.get('name')
        for n in tree.findall('./nets/net') for p in n.findall('node')}
endpoint_map = json.loads((A / 'ecad/SYSTEM_ENDPOINT_MAP.json').read_text())
def epnet(ep):
    x = endpoint_map[ep]
    return nets.get((x['ref'], x['pin']))
loadnet = nets.get(('J203', '1'))
ret = nets.get(('J203', '2'))
checks = [
    ('native_J203_positive_with_DM', loadnet is not None and loadnet == epnet('DM.VCC_REF')),
    ('native_J203_return_with_DM', ret is not None and ret == epnet('DM.RET_REF')),
    ('native_J203_on_K1_load_side', loadnet == epnet('K1.A1(-)') and loadnet != epnet('K1.A2(+)')),
    ('public_OV_not_hardware_rating', all(x['earliest_OV_trip_V'] is None for x in motors.values())),
    ('motor_energy_not_invented', declared['regenerative_energy_J'] is None),
    ('actual_bus_cap_not_borrowed_from_DNP_module', declared['installed_load_side_capacitance_F'] is None),
    ('capacitor_example_recomputed', math.isclose(examples['capacitor_example']['added_energy_J'], .04)),
    ('50J_would_require1F_for24to26_without_sink', math.isclose(examples['required_C_without_sink_for_same_example_F'], 1.0)),
    ('30V_Roboteq_no_nominal_dual_stage_margin', roboteq['nominal_dual_stage_to_DM_OV_margin_V'] == 0),
    ('25V_Roboteq_supply_transient_counterexample', examples['possible_CHB25V_threshold_crossing_V'] > 0),
    ('advertised_2000W_not_at32V', roboteq['full_on_resistive_W_at_nominal32V_boundary'] < 2000
        and roboteq['actual_absorbed_power_at_boundary_W'] is None),
    ('thermal_cutout_can_remove_sink', roboteq['alternate_return_path_after_thermal_cutout'] is None),
]
result = dict(schema='WP10_REGEN_SOURCE_AND_COUNTEREXAMPLE_V1', source_manifest=sources,
              native_netlist_sha256=sha(A / 'ecad/wp10_system.xml'),
              declared_inputs=declared, mature_module_comparison=trade,
              Roboteq_source_bound_candidate=roboteq, analytical_counterexamples=examples,
              selected_absorber=None, selected_absorber_scope='QUALIFIED_COMMERCIAL_MODULE_ONLY', absorber_fitted=False,
              native_J203_verified=True, actual_mission_envelope_evaluated=False,
              motor_voltage_protection_closed=False, whole_mechatronics_closed=False,
              checks=[dict(name=n, passed=bool(ok)) for n, ok in checks],
              checks_passed=all(ok for _, ok in checks), check_count=len(checks))
result['read_only_review_disposition'] = [
    dict(id='RGN-01', issue='At exactly +2V dual stage is not guaranteed on',
         fix='Full-on resistive capacity renamed; actual boundary absorption remains unknown', state='SOURCE_CORRECTED'),
    dict(id='RGN-02', issue='OEM ambient0..40C omitted',
         fix='Ambient range recorded; project50C explicitly unverified', state='SOURCE_CORRECTED')]
assert result['checks_passed']
dump(A / 'results/REGEN_SOURCE_SCREEN.json', result)

# This is part of the existing candidate budget, not a second project or new rating.
calcfile = A / 'power/POWER_LOOP_CALCULATIONS.json'
calc = json.loads(calcfile.read_text())
calc['regen'].update(voltage_evidence='power/DM_BUS_VOLTAGE_BINDING.json',
                     mature_module_screen='results/REGEN_SOURCE_SCREEN.json',
                     installed_load_side_C_F=None,
                     nominal_public_motor_OV_setting_V=32,
                     earliest_guaranteed_motor_OV_V=None,
                     selected_absorber=None, selected_absorber_scope='QUALIFIED_COMMERCIAL_MODULE_ONLY',
                     absorber_fitted=False)
dump(calcfile, calc)
print(json.dumps(dict(checks=len(checks), passed=True, selected_absorber=None,
                     new_hardware_ratings_claimed=False)))
