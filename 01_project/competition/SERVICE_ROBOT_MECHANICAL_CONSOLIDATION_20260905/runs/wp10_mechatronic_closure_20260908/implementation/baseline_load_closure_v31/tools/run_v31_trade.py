"""Consume V31 mission/electrical/mechanical/actuator inputs in isolated results."""
from pathlib import Path
import csv
import hashlib
import importlib.util
import itertools
import json
import sys

from power_phase_model import P, read, source_check, operating_point, phase_ledger, ideal_radiating_area_m2, validate_timeline

def write(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def module(name, path):
    spec=importlib.util.spec_from_file_location(name, path)
    result=importlib.util.module_from_spec(spec)
    sys.modules[name]=result
    spec.loader.exec_module(result)
    return result

def main():
    source_check()
    mission_path=P/'inputs/REFERENCE_MISSION_V1.json'
    trade_path=P/'inputs/LOAD_TRADE_INPUTS_V1.json'
    mission, trade=read(mission_path), read(trade_path)
    mechanical=read(P/'mechanical/BODY_PARAMETER_CARD.json')
    electrical=read(P/'electrical/ARM_ELECTRICAL_PARAMETERS.json')
    electrical_readiness=read(P/'electrical/POWER_MODEL_READINESS.json')
    actuator=read(P/'actuators/ACTUATOR_CONTRACT.json')
    energy_model=module('v31_dm_energy_model',P/'electrical/load_model.py')
    for profile in ['ground','orbital_reference']:
        block=mission[profile]
        validate_timeline(block['phases'],block.get('duration_s',block.get('period_s')))
    orbit=mission['orbital_reference']
    lit=sum(p['duration_s'] for p in orbit['phases'] if p['illumination']=='sunlit')
    eclipse=sum(p['duration_s'] for p in orbit['phases'] if p['illumination']=='eclipse')
    if (lit,eclipse)!=(orbit['sunlit_s'],orbit['eclipse_s']):
        raise ValueError('ILLUMINATION_TOTAL_MISMATCH')
    points=[]
    for power,V,R,eta in itertools.product(trade['motion_bus_power_W'],trade['pack_V'],trade['shared_R_ohm'],trade['eta_main']):
        point=operating_point(power,V,R,eta)
        if point['equilibrium_found']:
            rs=trade['radiator_screen']
            point['ideal_area_known_nonarm_heat_m2']={str(T):ideal_radiating_area_m2(
                point['known_nonarm_heat_W'],T+273.15,rs['sink_K'],rs['emissivity'],rs['absorbed_W_per_m2'])
                for T in rs['radiator_C']}
        points.append(point)
    write(P/'results/STEADY_POWER_TRADE.json',dict(scope=trade['status'],points=points,
        physical_load_bounds=None,whole_spacecraft_heat_known=False,temperature_solution_executed=False,
        radiator_result_scope=trade['radiator_screen']))
    columns=['arm_path_W','pack_V','shared_R_ohm','eta_main','equilibrium_found','input_power_W',
             'battery_A','main_fused_V','protection_class','CHB_loss_W','known_nonarm_heat_W',
             'Q201_heat_W','battery_margin_A']
    with (P/'results/STEADY_POWER_TRADE.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');w.writeheader();w.writerows(points)
    ledgers=[]
    for power,profile,eta in itertools.product(trade['motion_bus_power_W'],trade['profiles'],trade['eta_main']):
        for fraction in trade['initial_fraction']:
            initial=trade['candidate_nominal_Wh']*fraction
            result=phase_ledger(mission,power,profile['hold_W'],profile['standby_W'],eta_main=eta,initial_Wh=initial)
            result.update(motion_output_allocation_W=power,profile=profile['id'],hold_output_allocation_W=profile['hold_W'],
                          standby_output_allocation_W=profile['standby_W'],eta_main=eta,initial_fraction=fraction,
                          measurement_plane=trade['sweep_measurement_plane'])
            # Independent worker function checks the same explicit W,s -> Wh boundary.
            for row in result['rows']:
                if row.get('energy_Wh') is not None:
                    E=energy_model.phase_energy_Wh(row['base_input_power_W'],row['duration_s'])
                    if isinstance(E,dict):
                        E=E.get('energy_Wh',E.get('value'))
                    if E is None or abs(E-row['energy_Wh'])>1e-10:
                        raise ArithmeticError('INDEPENDENT_UNIT_BOUNDARY_MISMATCH')
            ledgers.append(result)
    write(P/'results/PHASE_ENERGY_TRADE.json',dict(mission_sha256=sha(mission_path),ledgers=ledgers,
        actual_cycle_energy=None,actual_cycle_remaining_energy=None,actual_recharge=None,
        unknown_stop_is_not_zero=True))
    # V30 retains V29 copper. Compare to V29_COPPER, not the different V28 replay branch.
    old=read(P.parent/'coupled_closure/TERMINAL_THERMAL_V29.json')['points']['V29_COPPER']
    replay=operating_point(360,25.2,.01,.85)
    replay_deltas={key:replay[key]-old[key] for key in ['battery_A','main_A','main_fused_V','input_power_W']}
    if max(abs(v) for v in replay_deltas.values())>1e-8:
        raise ArithmeticError('UNCHANGED_SOLVER_REPLAY_MISMATCH')
    unknowns_preserved=dict(full_cycle_energy=all(x['full_cycle_energy_Wh'] is None for x in ledgers),
        full_body_mass=mechanical['whole_system']['mass_kg'] is None,
        full_body_inertia=mechanical['whole_system']['inertia_COM_S_kg_m2'] is None,
        actual_motor_peak=not electrical_readiness['worst_case_power_bounded'],
        actual_C_POD_array=actuator['actual_C_POD']['wrench_matrix'] is None,
        target_inertias=all(x['inertia_COM_kg_m2'] is None for x in mission['targets']))
    if not all(unknowns_preserved.values()):
        raise ValueError('INPUT_SCOPE_CHANGED_REVIEW_REQUIRED')
    consumption=dict(schema='V31_SHARED_CONSUMER_RECEIPT',
        consumed_files=[dict(path=str(p),sha256=sha(p)) for p in [mission_path,trade_path,
           P/'inputs/UNIT_CONTRACT.json',P/'inputs/V30_ELECTRICAL_SOURCE.json',
           P/'mechanical/BODY_PARAMETER_CARD.json',P/'electrical/ARM_ELECTRICAL_PARAMETERS.json',
           P/'electrical/POWER_MODEL_READINESS.json',
           P/'electrical/load_model.py',P/'actuators/ACTUATOR_CONTRACT.json']],
        mission_id=orbit['id'],timeline_duration_s=orbit['period_s'],sunlit_s=lit,eclipse_s=eclipse,
        consumers=dict(power_phase='Executed 64 steady points and 32 phase subtotal cases',
                       thermal='Executed ideal radiative area sensitivity for same known heat; no temperature solve',
                       mechanical='Read same-version body card; full body dynamics blocked by unknown physical inputs',
                       actuators='Read separated wheel/external impulse contract; current C-POD and capture demand remain unknown'),
        numerical_source_replay_deltas=replay_deltas,
        unknowns_preserved=unknowns_preserved,
        source_checks=source_check(),legacy_models_executed=False,hardware_io=0,
        selected_motor_models_frozen=False,full_system_design_complete=False)
    write(P/'results/SHARED_CONSUMER_RECEIPT.json',consumption)
    print(json.dumps(dict(steady_points=len(points),phase_cases=len(ledgers),
        replay_max_delta=max(abs(v) for v in replay_deltas.values()),
        known_phase_subtotal_Wh_range=[min(x['known_phase_subtotal_Wh'] for x in ledgers),max(x['known_phase_subtotal_Wh'] for x in ledgers)],
        full_cycle_energy=None)))

if __name__=='__main__':
    main()
