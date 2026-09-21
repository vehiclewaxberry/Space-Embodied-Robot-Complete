"""Keep preliminary module selection consistent with actual design falsifiers."""
from pathlib import Path
import json,hashlib
A=Path(__file__).resolve().parents[1]
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def dump(p,o):(A/p).write_text(json.dumps(o,ensure_ascii=False,indent=2),encoding='utf-8')
b=read('thermal/TWO_PANEL_BRIDGE_BUDGET.json');s=read('thermal/FIXED_HEAT_TRANSFER_SELECTION.json')
assert b['checks_passed']
s['schema']='WP10_FIXED_HEAT_TRANSFER_TRADE_V2'
s['status']='HEAT_PIPE_PRINCIPLE_RETAINED__300MM_SKU_AND40W_ALLOCATION_NOT_FROZEN_AFTER_COUPLED_AND_ROUTE_CHECKS'
s['heat_to_transport_design_scenario_role']='Early capacity example, not a prescribed passive transfer, not sufficient for every paired environment'
s['preferred_candidate']['selection_state']='PUBLIC_REFERENCE_CANDIDATE_ONLY; declared200mm U-route with50mm contacts exceeds300mm+2%'
s['preferred_candidate']['actual_cad_route_and_STEP_bound']=False
s['next_actual_work']='Bind actual deployed/stowed panel view factors and needed net effective area; include brake/battery/PMM heat. Then select a pipe length and collectors fitting the actual route and solve the branch-specific thermal network.'
s['coupled_design_evidence']='thermal/TWO_PANEL_BRIDGE_BUDGET.json'
s['coupled_design_sha256']=hashlib.sha256((A/s['coupled_design_evidence']).read_bytes()).hexdigest()
s['qualified_bridge_R_K_W']=None
s['unresolved_design_constraints']={
 'forty_W_fixed_split_accepted':False,
 'current_two_panel_area_verified_for_hot_wing_pressure_cases':False,
 'declared300mm_U_route_fits':False,
 'low_load_outside_public_temperature_range_performance':'UNKNOWN; isothermal contact nodes are not measured pipe fluid temperatures',
 'additional_surface_area_can_be_counted_without_conductive_link_and_view_factor':False}
dump('thermal/FIXED_HEAT_TRANSFER_SELECTION.json',s)
r=read('results/FIXED_HEAT_REVIEW_DISPOSITION.json')
r['repaired']=[x for x in r['repaired'] if x['id'] not in ['HT06','HT07','HT08']]+[
 dict(id='HT06',issue='Nominal40W was at risk of being treated as a prescribed passive split',change='Solved bridge heat from mean contact temperature difference and energy balances; .25K/W remains numerical allocation',evidence='thermal/TWO_PANEL_BRIDGE_BUDGET.json'),
 dict(id='HT07',issue='Opposite radiator faces cannot both receive the same normal direct sunlight',change='New paired environments have direct sunlight only on +Y; old equal-environment cases retained as independent pressure examples',evidence='thermal/TWO_PANEL_BRIDGE_SCENARIO.json'),
 dict(id='HT08',issue='300mm selection and30–120C public pipe range insufficiently tied to layout and load',change='Declared U route needs334.24778mm versus306mm longest tolerance; low-load node diagnosis withholds temperature/transport qualification; SKU is not frozen',evidence='thermal/FIXED_HEAT_TRANSFER_SELECTION.json')]
r['thermal_network_topology']='Bridge proposed between outer-wall nodes; existing TIM and16.65mm metal R shared only for this topology. An earlier branch requires a new network.'
r['final_readonly_code_review']=dict(reviewer='thermal_layout_readonly',scope='Actual two_panel_bridge_budget.py and both scenario/result JSON read; independent scalar/energy/passivity recalculation; no CAD executed',
    publication_blocker_found_in_declared_four_cases=False,
    independent_max_energy_residual_W=3.37e-8,independent_max_bridge_residual_K=8.46e-8,
    boundary='Sheet solver currently supports only0<=q<=CHB_loss; explicit fail-closed error now reports unbracketed reverse/environment-fed scenarios. No generalized reverse-flow credit.',
    future_extension='Signed transfer intervals before adding hotter-negative-side or ambient-fed cases; additional heat-source ledger and coupled mesh refinement remain open')
dump('results/FIXED_HEAT_REVIEW_DISPOSITION.json',r)
print(json.dumps(dict(selection_status=s['status'],checks=b['check_count'])))
