"""Bind native topology, solve shared contact loss, and register thermal loads.

This updates the current discharge design model, not the manufacturer's pinout
or PCB. The older 0.04/0.06-ohm screens remain scoped historical sensitivities.
"""
from pathlib import Path
import csv
import hashlib
import itertools
import json
import math
import xml.etree.ElementTree as ET
from shared_battery_path import solve, current, hold_boundary

A = Path(__file__).resolve().parents[1]

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads((A/p).read_text(encoding='utf-8-sig'))
def dump(p, v): (A/p).write_text(json.dumps(v, ensure_ascii=False, indent=2), encoding='utf-8')

c = read('power/SHARED_BATTERY_PATH_DEFINITION.json')
p = read('power/POWER_LOOP_CALCULATIONS.json')
s = read('power/STARTUP_CIRCUIT_CALCULATIONS.json')
parts = read('power/POWER_LOOP_PARTS.json')
assert sha(A/c['connector']['document']) == c['connector']['document_sha256']
assert p['battery_revision_locked'] == 'D'
assert p['additional_brake_budget']['total_main_design_allocation_W'] == c['load_binding']['main_output_W'] == 361
assert p['startup_primary_budget']['reserved_W'] == c['load_binding']['startup_bias_input_W'] == .25
assert p['aux_output_W'] == c['load_binding']['aux_output_W'] == 16.8
assert parts['J200']['status'] == 'OEM_SIDE_UNBOUND'
xml = ET.parse(A/'ecad/wp10_system.xml').getroot()
nets = {(n.get('ref'), n.get('pin')): net.get('name') for net in xml.findall('./nets/net') for n in net.findall('node')}
def same(*eps):
    found = [nets.get(tuple(ep.split('.'))) for ep in eps]
    return found[0] is not None and len(set(found)) == 1

checks=[]
def ck(name, flag, **kw): checks.append(dict(name=name, passed=bool(flag), **kw))
ck('shared_positive_before_two_fuses',same('J200.1','F201.1','F202.1'))
ck('both_returns_share_J200',same('J200.2','U202.2','U203.4'))
ck('UVLO_and_startup_sense_after_main_fuse',same('F201.2','U201.2','R215.1','R203.1'))
ck('AUX_is_not_downstream_of_Q201',same('F202.2','U202.1') and not same('U202.1','Q201.3'))
ck('bias_after_main_precharge',same('Q201.3','U203.1','U205.10'))
ck('no_new_OEM_pin_assignment',parts['J200']['status']=='OEM_SIDE_UNBOUND')
ck('PMM_stays_out_of_discharge_netlist',not any('PMM35' in x.findtext('value','') for x in xml.findall('./components/comp')))

# Independent analytic limiting cases, not a duplicate implementation assertion.
q=solve(25,.1,.04,.005,0,400,0,controller_a=0)
expected=400/(.5*(25+math.sqrt(25**2-4*.14*400)))
ck('single_branch_matches_total_series_quadratic',abs(q['main_A']-expected)<1e-10)
q=solve(25,.1,0,0,0,400,20,controller_a=0)
expected=420/(.5*(25+math.sqrt(25**2-4*.1*420)))
ck('zero_branch_resistance_matches_combined_load_quadratic',abs(q['battery_A']-expected)<1e-10)
q=solve(25,0,.04,.005,.04,400,20,controller_a=0)
ck('zero_shared_R_separates_branches',abs(q['main_A']-current(25,.04,400))<1e-10 and abs(q['aux_A']-current(25,.04,20))<1e-10)
ck('unavailable_high_voltage_equilibrium_is_not_zero_current_PASS',not solve(10,1,0,0,0,400,20,0)['equilibrium_found'])
q=solve(25,.1,.04,.005,.04,0,20)
ck('CHB_OFF_retains_AUX_contact_loss',q['main_A']==0 and q['aux_A']>0 and q['heat_W']['shared_contact_loop']>0)

def status(value, limits):
    if value is None: return 'NO_EQUILIBRIUM_IN_MODEL'
    return 'ALL_CORNERS_ON' if value>=max(limits) else 'ALL_CORNERS_OFF' if value<min(limits) else 'CORNER_DEPENDENT'

rows=[]
cases=c['cases']
uvfall=p['UVLO_falling_screen_V']; uvrise=p['UVLO_rising_screen_V']
startfall=s['qualification']['fall_sensitivity_V']
boundaries=[]
for vb, rc, mr, ar, eta, aeta in itertools.product(cases['pack_V'], cases['shared_contact_loop_R_ohm'], cases['main_branch_allocations_ohm'], cases['aux_branch_R_ohm'], cases['main_efficiency'], cases['aux_efficiency']):
    mw=361/eta+.25; aw=16.8/aeta; ctrl=cases['controller_input_A']
    args=dict(pack_v=vb,shared_r=rc,main_r=mr['total'],main_pre_r=mr['before_MAIN_FUSED'],aux_r=ar,main_w=mw,aux_w=aw,controller_a=ctrl)
    run=solve(**args); cold=solve(**dict(args,main_w=0))
    initial=status(cold.get('main_fused_V'),uvrise)
    hold=status(run.get('main_fused_V'),uvfall)
    start=status(run.get('main_fused_V'),startfall)
    limiting=run.get('main_A',math.inf)>p['current_limit_screen_A'][0]
    rating=run.get('battery_A',math.inf)<=c['connector']['published_power_pin_current_max_A']
    row=dict(id=f'SBP{len(rows):03}',inputs=args,main_eta=eta,aux_eta=aeta,run=run,cold=cold,
             cold_LM5069_screen=initial,held_LM5069_screen=hold,held_startup_supervisor_screen=start,
             exceeds_minimum_main_current_limit_corner=limiting,
             under_published_connector_30A_rating=rating,
             coupled_DC_allocation_screen_satisfied=bool(initial=='ALL_CORNERS_ON' and hold=='ALL_CORNERS_ON' and start=='ALL_CORNERS_ON' and not limiting and rating),
             hardware_permission=False,thermal_verified=False)
    if run['equilibrium_found']:
        run['conversion_and_bias_heat_W']=dict(CHB_conversion=361*(1/eta-1),
                                                THN_conversion=16.8*(1/aeta-1),
                                                startup_bias_allocation=.25)
        # Input-load equation includes .25W in Pm; output-load equation counts
        # it as a separate bias allocation exactly once.
        run['delivered_output_allocation_W']=361+16.8
        run['source_to_output_balance_residual_W']=run['input_power_W']-run['delivered_output_allocation_W']-sum(run['heat_W'].values())-sum(run['conversion_and_bias_heat_W'].values())
        old=solve(**dict(args,shared_r=0))
        row['comparison_same_allocations_shared_R_zero']=dict(
            junction_V=old.get('junction_V'),main_A=old.get('main_A'),aux_A=old.get('aux_A'),
            held_LM5069_screen=status(old.get('main_fused_V'),uvfall),
            main_delta_A=run['main_A']-old['main_A'],aux_delta_A=run['aux_A']-old['aux_A']) if old['equilibrium_found'] else None
    rows.append(row)

for mr, ar, eta, aeta in itertools.product(cases['main_branch_allocations_ohm'],cases['aux_branch_R_ohm'],cases['main_efficiency'],cases['aux_efficiency']):
    q=hold_boundary(25.2,max(uvfall),.1,mr['total'],mr['before_MAIN_FUSED'],ar,361/eta+.25,16.8/aeta,cases['controller_input_A'])
    if q:
        verify=solve(q['required_pack_V_for_given_shared_R'],.1,mr['total'],mr['before_MAIN_FUSED'],ar,361/eta+.25,16.8/aeta,cases['controller_input_A'])
        ck('inverted_hold_boundary_'+str(len(boundaries)),verify['equilibrium_found'] and abs(verify['main_fused_V']-max(uvfall))<1e-8)
    boundaries.append(dict(main_allocation_ohm=mr,aux_R_ohm=ar,main_eta=eta,aux_eta=aeta,boundary=q))

changed=[r for r in rows if r.get('comparison_same_allocations_shared_R_zero') and r['comparison_same_allocations_shared_R_zero']['held_LM5069_screen']=='ALL_CORNERS_ON' and r['held_LM5069_screen']!='ALL_CORNERS_ON']
ck('shared_path_changes_previously_ON_hold_classification',bool(changed))
ck('each_solved_case_closes_power_balance',all(abs(r['run']['power_balance_residual_W'])<1e-7 for r in rows if r['run']['equilibrium_found']))
ck('source_to_outputs_heat_ledger_closes_without_double_count',all(abs(r['run']['source_to_output_balance_residual_W'])<1e-7 for r in rows if r['run']['equilibrium_found']))
ck('monotonic_shared_R_current_increase_on_solved_high_branch',all(r['comparison_same_allocations_shared_R_zero']['main_delta_A']>=-1e-10 and r['comparison_same_allocations_shared_R_zero']['aux_delta_A']>=-1e-10 for r in rows if r.get('comparison_same_allocations_shared_R_zero')))
inputs=['power/SHARED_BATTERY_PATH_DEFINITION.json','power/POWER_LOOP_CALCULATIONS.json','power/STARTUP_CIRCUIT_CALCULATIONS.json','power/POWER_LOOP_PARTS.json','ecad/wp10_system.xml',c['active_geometry_plan'],c['connector']['document'],'sources/pmm35.pdf','power/BATTERY_INSTALLATION_INTERFACE.json']
out=dict(schema='WP10_COUPLED_SHARED_BATTERY_DC_V1',status='SHARED_CONTACT_LOSS_AND_HOLD_COUNTEREXAMPLE_BOUND__WHOLE_POWER_OPEN',
         inputs={q:sha(A/q) for q in inputs},source_scripts={q:sha(A/q) for q in ['tools/shared_battery_path.py','tools/check_shared_battery_path.py']},
         case_count=len(rows),cases=rows,hold_boundaries_at_25p2V=boundaries,counterexample_ids=[r['id'] for r in changed],
         check_count=len(checks),checks=checks,checks_passed=all(x['passed'] for x in checks),
         all_currents_are_assuming_on_algebraic_roots=True,
         losses_during_actual_UVLO_tripping_not_calculated=True,
         same_source_native_topology_bound=True,native_schematic_modified=False,
         thermal_node_position_bound=False,thermal_material_temperature_verified=False,
         common_connector_open_circuit=dict(
             DC_source_to_both_input_branches='INTERRUPTED',
             independent_aux_branch_is_not_redundant_source=True,
             upstream_loss_does_not_remove_load_side_brake_topology=True,
             capacitor_hold_up_and_actual_STOP_response_verified=False),
         continuous_motion_or_936_geometry_requalified=False,
         physical_tests_executed=False,goal_complete=False)
dump('power/SHARED_BATTERY_PATH_CALCULATIONS.json',out)
thermal=[]
for r in rows:
    if not r['run']['equilibrium_found']:continue
    for node, watts in (r['run']['heat_W']|r['run']['conversion_and_bias_heat_W']).items():
        thermal.append(dict(case_id=r['id'],node=node,heat_W=watts,condition='ASSUMING_ON_DC_ALLOCATION_NOT_MEASURED',
                            mechanical_sink_node='',thermal_contact_R_K_W='',qualification='UNBOUND'))
with (A/'thermal/SHARED_BATTERY_HEAT_LOADS.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=list(thermal[0]));w.writeheader();w.writerows(thermal)
anchor=next(r for r in rows if r['inputs']==dict(pack_v=25.2,shared_r=.1,main_r=.04,main_pre_r=.005,aux_r=.04,main_w=361/.85+.25,aux_w=16.8/.8,controller_a=.003))
print(json.dumps(dict(case_count=len(rows),checks=len(checks),passed=out['checks_passed'],counterexample_count=len(changed),anchor=anchor),ensure_ascii=False))
assert out['checks_passed'],[q for q in checks if not q['passed']]
