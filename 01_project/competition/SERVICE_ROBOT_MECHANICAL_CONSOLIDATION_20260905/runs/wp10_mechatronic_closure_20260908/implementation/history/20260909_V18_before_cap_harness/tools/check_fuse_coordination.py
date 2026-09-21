"""Specific fuse-source binding and counterexamples, not a fault-clearing PASS."""
from pathlib import Path
import json,hashlib,xml.etree.ElementTree as ET
from input_passive_definition import PASSIVES
A=Path(__file__).resolve().parents[1]
def read(q):return json.loads((A/q).read_text(encoding='utf-8-sig'))
def sha(q):return hashlib.sha256((A/q).read_bytes()).hexdigest()
def dump(q,v):(A/q).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
f,a=PASSIVES['F201'],PASSIVES['F202'];s=read('power/SHARED_BATTERY_PATH_CALCULATIONS.json')
old=read('history/20260909_V14_before_fuse_coordination/power/SHARED_BATTERY_PATH_CALCULATIONS.json')
checks=[]
def ck(n,v,**kw):checks.append(dict(name=n,passed=bool(v),**kw))
def netmap(p):
 r=ET.parse(A/p).getroot();return {(n.get('ref'),n.get('pin')):net.get('name') for net in r.findall('./nets/net') for n in net.findall('node')}
ck('native_topology_unchanged_by_passive_selection',netmap('ecad/wp10_system.xml')==netmap('history/20260909_V14_before_fuse_coordination/ecad/wp10_system.xml'))
ck('all192_cases_preserved',len(s['cases'])==len(old['cases'])==192)
changed=[]
for r,o in zip(s['cases'],old['cases']):
 assert r['id']==o['id']
 x=dict(r['inputs']);y=dict(o['inputs']);new_r=x.pop('aux_r');old_r=y.pop('aux_r');assert x==y
 if new_r!=old_r:
  assert old_r==0 and new_r==a['typical_cold_R_ohm']
  for state in ['run','cold']:
   assert r[state]['aux_A']>o[state]['aux_A'] and r[state]['aux_input_V']<o[state]['aux_input_V']
  changed.append(r['id'])
ck('old96_zero_aux_cases_now_include_selected_fuse',len(changed)==96)
heat=[]
for r in s['cases']:
 for state in ['run','cold']:
  z=r[state];heat.append(dict(case=r['id'],state=state,aux_A=z['aux_A'],F202_typical_cold_loss_W=z['aux_A']**2*a['typical_cold_R_ohm'],aux_total_R=r['inputs']['aux_r'],other_aux_R=r['inputs']['aux_r']-a['typical_cold_R_ohm'],operating_point_accepted=False))
ck('F202_cold_heat_within_total_aux_ledger',all(x['other_aux_R']>=0 for x in heat))
rate_a=a['rated_A'];rated_cold=rate_a**2*a['typical_cold_R_ohm'];rated_drop=rate_a*a['typical_drop_V_at_rated_current']
ck('rated_drop_demonstrates_cold_R_is_not_hot_loss',rated_drop>rated_cold)
ck('F201_native_pad_revision_bound',sha(f['footprint_source_file'])==f['footprint_source_sha256'])
ck('F202_revision_bound',sha(a['source_file'])==a['source_sha256'])
erc=read('results/POWER_LOOP_ERC.json');prior=read('history/20260909_V14_before_fuse_coordination/results/POWER_LOOP_ERC.json')
def violations(q):return [(s['path'],v['type'],v['severity'],[i['description'] for i in v['items']]) for s in q['sheets'] for v in s['violations']]
decl=read('results/ERC_SOURCE_VALIDATION.json')
assert all(sha(q)==h for q,h in decl['inputs'].items()),'stale ERC declaration source audit'
ck('ERC_declarations_audited_and_no_rule_suppression',not violations(erc) and len(violations(prior))==7 and erc['ignored_checks']==prior['ignored_checks'] and decl['passed'] and decl['declaration_count']==7)
inputs=['tools/input_passive_definition.py','tools/input_passive_footprint.py','tools/check_fuse_coordination.py','power/INPUT_PASSIVE_SELECTION.json','power/SHARED_BATTERY_PATH_DEFINITION.json','power/SHARED_BATTERY_PATH_CALCULATIONS.json','power/INPUT_PASSIVE_CALCULATIONS.json','thermal/INPUT_PASSIVE_HEAT_LOADS.csv','ecad/wp10_system.xml','results/POWER_LOOP_ERC.json',f['footprint_source_file'],a['source_file'],a['THN_recommendation']['document']]
inputs+=['results/ERC_SOURCE_VALIDATION.json','power/ERC_SOURCE_DECLARATIONS.json']
out=dict(schema='WP10_INPUT_FUSE_COORDINATION_V15',checks=checks,check_count=len(checks),passed=all(q['passed'] for q in checks),inputs={q:sha(q) for q in inputs},changed_zero_aux_cases=changed,
 F201=dict(MPN=f['MPN'],footprint=f['footprint'],pad_outer_span_mm=12.6,pad_pitch_mm=9.35,pad_gap_mm=6.10,recommended_copper_oz=3,recommended_trace_width_mm=10,trace_routed=False,
  graph_readout_at125C_current_range_A=[30*.85,30*.87],graph_readout_not_guaranteed=True,installed_temperature_C=None,
  protected_source_prospective_fault_current_A=None,actual_fault_LoverR_s=None,total_clearing_I2t_A2s=None,wire_and_MOSFET_survival_verified=False),
 F202=dict(MPN=a['MPN'],rated_A=rate_a,rated_VDC=a['rated_VDC'],interrupt_A=a['interrupt_A'],DC_test_LoverR_s=None,
  total_aux_R_scenarios_ohm=[.018,.04],cold_R_scope=a['resistance_test'],cold_model_rows=heat,
  rated_cold_formula_W=rated_cold,rated_typical_drop_W=rated_drop,rated_hot_R_inferred_ohm=a['typical_drop_V_at_rated_current']/rate_a,
  unsafe_constant_I2t_inference=dict(incorrect_time_at6A_s=a['typical_melting_I2t_A2s']/rate_a**2,valid=False,reason='10In typical melting I2t is not a universal clearing timer; rated-current table says 4 hours without explicit min/max. No minimum opening band or total-clearing bound is derived.'),
  fault_examples=[dict(current_A=3,opening_time_bound_s=None,reason='No promised opening time at this sub-rated fault current'),dict(current_A=8.1,maximum_open_s=3600,minimum_open_s=None),dict(current_A=12,maximum_open_s=120,minimum_open_s=None)],
  THN_inrush_waveform=None,branch_wire_damage_limit=None,upstream_BMS_fault_response=None,STOP_response_after_fuse_opens=None,PCB_formed_lead_pitch_mm=None),
 circuit_scope='F201 and F202 are parallel branch fuses; current-rating ratio is not upstream/downstream selectivity proof',
 thermal_scope='INPUT_PASSIVE_HEAT_LOADS refines SHARED_BATTERY_HEAT_LOADS; never add them. Typical cold fuse heat is not installed hotspot temperature.',
 physical_tests_executed=False,protection_coordination_verified=False,engineering_prototype_design_complete=False)
dump('power/INPUT_FUSE_COORDINATION.json',out)
print(json.dumps(dict(checks=len(checks),passed=out['passed'],changed_cases=len(changed),F202_A=[min(x['aux_A'] for x in heat),max(x['aux_A'] for x in heat)],F202_cold_W=[min(x['F202_typical_cold_loss_W'] for x in heat),max(x['F202_typical_cold_loss_W'] for x in heat)])))
assert out['passed'],[q for q in checks if not q['passed']]
