"""Build declared V31 engineering inputs; never changes a legacy candidate/Gate."""
from pathlib import Path
import hashlib
import json

P = Path(__file__).resolve().parents[1]
A = P.parent
ROOT = next(p for p in P.parents if (p / 'AGENTS.md').exists())

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')

def parameter(value, unit, basis, status='DESIGN_ASSUMPTION'):
    return dict(value=value, unit=unit, evidence_class=status, basis=basis,
                standard_uncertainty=None, distribution='NOT_ESTABLISHED', degrees_of_freedom=None,
                uncertainty_note='Design scenarios are not confidence intervals or measured limits.')

def phase(name, start, duration, power_class, illumination, **extra):
    return dict(id=name, start_s=start, duration_s=duration, power_class=power_class,
                illumination=illumination, hardware_command=False, **extra)

def main():
    candidate_path = A / 'coupled_closure/CANDIDATE_V30.json'
    c = read(candidate_path)
    protected = [candidate_path, A / 'coupled_closure/DELIVERY_STATUS_V30.json',
                 A / 'coupled_closure/SOURCE_ACTIVATION_V30.json', A / 'tools/shared_battery_path.py',
                 A / 'coupled_closure/TERMINAL_THERMAL_V29.json', A / 'results/SYSTEM_ERC_V29.json',
                 A / 'results/MAIN_INPUT_DRC_V29.json']
    lock = dict(schema='V31_ROOT_INPUT_LOCK', files=[dict(path=str(p), sha256=sha(p)) for p in protected])
    lock_path = P / 'inputs/ROOT_SOURCE_LOCK.json'
    if lock_path.exists() and read(lock_path) != lock:
        raise ValueError('EXISTING_V31_INPUT_IDENTITY_CHANGED; create/review a new revision')
    write(lock_path, lock)
    write(P / 'inputs/V30_ELECTRICAL_SOURCE.json', dict(
        schema='V31_UNCHANGED_V30_ELECTRICAL_INTAKE', source_path=str(candidate_path), source_sha256=sha(candidate_path),
        electrical=c['electrical'], thermal=c['thermal'],
        limits_are_inherited_candidate_screens=True, efficiencies_guaranteed=False,
        main_output_W_role='361 W legacy screening point = 360 W arm-path assumption plus 1 W brake-bias allocation',
        no_hardware_or_continuous_thermal_credit=True))
    # A reference timeline is constructed coherently here, not approved as an orbit or a real control sequence.
    orbital = [phase('LIT_INSPECTION', 0, 900, 'standby', 'sunlit'),
               phase('LIT_ARM_MOTION', 900, 600, 'motion', 'sunlit'),
               phase('LIT_CONTACT_HOLD', 1500, 180, 'hold', 'sunlit'),
               phase('LIT_STOP_WINDOW', 1680, 10, 'unbound_stop', 'sunlit',
                     note='Scheduling allocation only; not measured stopping time or regenerative pulse width.'),
               phase('LIT_SAFE_HOLD', 1690, 1200, 'hold', 'sunlit',
                     note='Retains holding consumption; no zero-power restraint assumption.'),
               phase('LIT_REPOSITION', 2890, 300, 'motion', 'sunlit'),
               phase('LIT_STANDBY', 3190, 410, 'standby', 'sunlit'),
               phase('ECLIPSE_STANDBY', 3600, 1500, 'standby', 'eclipse'),
               phase('ECLIPSE_COLD_HOLD', 5100, 600, 'standby', 'eclipse',
                     heater_thermal_output_W=20.0, heater_efficiency=0.8,
                     heater_note='Explicit full-on heater sensitivity; no thermostat/physical heater claim.')]
    ground = [phase('BENCH_STANDBY', 0, 60, 'standby', 'laboratory'),
              phase('BENCH_MOTION', 60, 30, 'motion', 'laboratory'),
              phase('BENCH_HOLD', 90, 180, 'hold', 'laboratory'),
              phase('BENCH_STOP_WINDOW', 270, 10, 'unbound_stop', 'laboratory'),
              phase('BENCH_POST_STANDBY', 280, 60, 'standby', 'laboratory')]
    mission = dict(schema='V31_REFERENCE_MISSION', status='DESIGN_REFERENCE_NOT_APPROVED_OPERATION',
        engineering_goal='可装配地面工程样机；在轨能力另作有界设计研究',
        no_hardware_commands=True, source_candidate_sha256=sha(candidate_path),
        reference_selection='Owner requested autonomous engineering refinement; timeline selected by designer, not a measured/approved mission.',
        ground=dict(id='GROUND_DM_INTAKE_V1', gravity='EARTH_GROUND', cooling='AMBIENT_AIR',
                    supply_role='EXTERNAL_24V_BENCH_SUPPLY', phases=ground, duration_s=340,
                    actual_trajectory=None, fixture_and_stop_review_complete=False,
                    data_use='Identify baseline/holding/transient terms; do not transfer ground gravity or cooling to orbit.'),
        orbital_reference=dict(id='ORBITAL_PHASE_REFERENCE_V1', period_s=5700, sunlit_s=3600, eclipse_s=2100,
            orbit_elements=None, sun_earth_attitude_history=None, phases=orbital,
            period_basis='95 min / 35 min inherited illustration; not a selected physical orbit.',
            recharge_Wh=None, recharge_credit_allowed=False, mission_feasibility=None),
        targets=[dict(id='TARGET_22KG_REFERENCE', mass=parameter(22, 'kg', 'Existing user project target', 'PROJECT_TARGET'),
                      pre_capture_rate=parameter(3, 'deg/s', 'Designer reference scenario; not measured target state'),
                      inertia_COM_kg_m2=None, capture_geometry=None, postcapture_state=None),
                 dict(id='TARGET_150KG_REFERENCE', mass=parameter(150, 'kg', 'Existing user project target', 'PROJECT_TARGET'),
                      pre_capture_rate=parameter(3, 'deg/s', 'Historical stress anchor reused as a declared input'),
                      inertia_COM_kg_m2=None, capture_geometry=None, postcapture_state=None)],
        constraints=dict(postcapture_rate_reference=parameter(2, 'deg/s', 'Legacy screening threshold; revised mission acceptance pending'),
                         mechanical_launch_stow_verified=False, actual_orbit_ready=False),
        missing=['Real orbit/attitude thermal boundaries', 'Target inertia/capture configuration',
                 'Stopping dynamics and regenerative waveform', 'Onboard charging and energy replenishment'])
    write(P / 'inputs/REFERENCE_MISSION_V1.json', mission)
    trade = dict(schema='V31_DECLARED_TRADE_INPUTS', status='DESIGN_SENSITIVITY_NOT_MOTOR_PREDICTION',
        sweep_measurement_plane='CHB_OUTPUT_ARM_PATH_ALLOCATION_AFTER_SEPARATE_BRAKE_BIAS',
        arm_connector_measurements_require_distribution_loss_correction=True,
        actual_arm_connector_power_W=None,
        physical_load_lower_bound_W=None, physical_load_upper_bound_W=None,
        motion_bus_power_W=[60, 120, 240, 360], hold_bus_power_W=[20, 60], standby_bus_power_W=[5, 15],
        selection_basis='Independent design sweeps chosen to expose sizing sensitivity; none are device measurements or guaranteed bounds.',
        profiles=[dict(id='PROFILE_A', hold_W=20, standby_W=5), dict(id='PROFILE_B', hold_W=60, standby_W=15)],
        pack_V=[20, 22, 25.2, 29.4], shared_R_ohm=[0.01, 0.1], eta_main=[0.85, 0.90],
        candidate_nominal_Wh=c['electrical']['nominal_energy_Wh'], initial_fraction=[0.5, 0.8],
        unknown_stopping_energy_Wh=None, unknown_regenerated_energy_J=None,
        brake_bias_W=parameter(1.0, 'W', 'Existing V30 361/360 W split; not measured idle draw', 'INHERITED_DESIGN_ALLOCATION'),
        radiator_screen=dict(radiator_C=[60, 80], sink_K=3.0, emissivity=0.89, absorbed_W_per_m2=0.0,
            status='OPTIMISTIC_RADIATION_ONLY_AREA_LOWER_BOUND_FOR_KNOWN_NONARM_HEAT',
            excludes=['Arm/battery internal heat', 'View blockage', 'Sun/Earth absorption', 'TIM/spreading resistance', 'V30 cover effect']),
        no_capacity_downrating_from_sweep=True,
        uncertainty=dict(standard_uncertainties=None, distribution='NOT_ESTABLISHED', confidence_interval=False))
    write(P / 'inputs/LOAD_TRADE_INPUTS_V1.json', trade)
    unit_map = dict(schema='V31_UNIT_CONTRACT',
        units=dict(time='s', mass='kg', position='m', force='N', force_impulse='N*s',
                   angular_momentum='kg*m^2/s', angular_impulse='N*m*s', inertia='kg*m^2',
                   voltage='V', current='A', resistance='ohm', power='W', energy='J', report_energy='Wh',
                   radiation_temperature='K', reported_temperature='degC'),
        conversions=dict(Wh_to_J=3600.0, mm_to_m=0.001, deg_to_rad='pi/180', degC_to_K_offset=273.15),
        semantic_distinctions=['Wheel stored momentum != externally removed angular impulse despite same dimensions',
                              'Motor phase RMS current != DC bus current', 'Mechanical output != electrical input',
                              'Six leaf budget != complete solar wing', 'Design scenarios != measured uncertainty bounds'])
    write(P / 'inputs/UNIT_CONTRACT.json', unit_map)
    print(json.dumps(dict(reference_profiles=2, targets=2, protected_sources=len(protected))))

if __name__ == '__main__':
    main()
