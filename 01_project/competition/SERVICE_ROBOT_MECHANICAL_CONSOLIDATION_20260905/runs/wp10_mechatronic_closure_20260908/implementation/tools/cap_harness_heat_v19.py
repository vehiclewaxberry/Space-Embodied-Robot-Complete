"""Refine the existing capacitor leakage allocation using actual routed wire R20.

Keep the original coupled DC current source and all operating-point judgments.
Wire resistance is a correlated scenario parameter, not added to the main 20A
path. This module has no CAD/COM dependency and performs no hardware action.
"""
from pathlib import Path
import json,csv,math,hashlib,collections,copy,xml.etree.ElementTree as ET
from shared_battery_path import solve
A=Path(__file__).resolve().parents[1]
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def dump(p,v):(A/p).write_text(json.dumps(v,indent=2),encoding='utf-8')
def refine_row(case,state,old,R,factor=1.):
 assert 0<=factor<=1 and len(R)==2 and all(math.isfinite(r) and r>0 for r in R.values())
 z=case[state];I=z['main_leak_A'];Vin=z['main_input_V']
 assert z['equilibrium_found']
 if state=='cold':assert I==0 and Vin is None
 else:assert state=='run' and I==case['inputs']['main_leak_a'] and Vin>0
 values={r['node']:float(r['heat_W']) for r in old}
 assert len(values)==len(old) and 'input_capacitor_leakage' in values
 assert all(math.isfinite(x) and x>=0 for x in values.values())
 old_leak=values['input_capacitor_leakage'];assert abs(old_leak-(I*Vin if Vin is not None else 0))<1e-12
 local={k:I*I*r*factor for k,r in R.items()}
 cap_voltage=Vin-I*sum(R.values())*factor if Vin is not None else None
 cap_heat=I*cap_voltage if cap_voltage is not None else 0.
 assert cap_heat>=0 and abs(old_leak-(cap_heat+math.fsum(local.values())))<1e-12
 new=[dict(r) for r in old]
 for r in new:
  if r['node']=='input_capacitor_leakage':
   r.update(heat_W=cap_heat,value_basis='Leakage-branch remainder after modeled wire loss; includes unmodeled PCB/solder/contact loss; not isolated capacitor-body heat or an independent upper bound',qualification='MODEL_SCENARIO_NOT_TEMPERATURE_QUALIFIED')
 for k,w in local.items():
  new.append(dict(case_id=case['id'],state=state,node=k+'_DC_WIRE',heat_W=w,value_basis='Actual nominal route length times OEM R20 maximum; only main_leak_A, not main_A; linked reduction of leakage-branch remainder',mechanical_sink_node=k,thermal_contact_R_K_W='',qualification='CONTACT_AND_TEMPERATURE_UNQUALIFIED'))
 assert len(new)==len(old)+2
 assert abs(math.fsum(float(r['heat_W']) for r in new)-math.fsum(values.values()))<1e-10
 return new,dict(case_id=case['id'],state=state,wire_R20_fraction=factor,main_leak_A=I,main_branch_A=z['main_A'],precharged_V=Vin,wire_only_downstream_scenario_V=cap_voltage,
  original_capacitor_leakage_allocation_W=old_leak,leakage_branch_remainder_after_modeled_wire_W=cap_heat,wire_heat_W=local,source_heat_total_W=math.fsum(values.values()),refined_heat_total_W=math.fsum(float(r['heat_W']) for r in new),operating_point_accepted=False,
  cold_state_scope='No battery-fed steady leakage allocated when main switch is open; stored-capacitor discharge transient not evaluated' if state=='cold' else None)
def verify_candidate(case,state,old,R,candidate):
 expected,detail=refine_row(case,state,old,R)
 actual={r['node']:float(r['heat_W']) for r in candidate};wanted={r['node']:float(r['heat_W']) for r in expected}
 assert len(actual)==len(candidate) and set(actual)==set(wanted)
 assert all(r['case_id']==case['id'] and r['state']==state for r in candidate)
 assert all(math.isfinite(v) and v>=0 for v in actual.values())
 expected_metadata={r['node']:{k:v for k,v in r.items() if k!='heat_W'} for r in expected}
 assert all({k:v for k,v in r.items() if k!='heat_W'}==expected_metadata[r['node']] for r in candidate)
 assert all(abs(actual[k]-v)<1e-12 for k,v in wanted.items())
 assert abs(math.fsum(actual.values())-math.fsum(float(r['heat_W']) for r in old))<1e-10
 return True
def build():
 path=read('results/CAP_HARNESS_PATH_V19.json');definition=read('power/CAP_HARNESS_DEFINITION_V19.json');cap=read('power/CAP_TERMINAL_DEFINITION.json')
 assert path['passed'] and all(sha(p)==h for p,h in path['inputs'].items())
 wire=definition['wire'];assert wire['max_R20_ohm_per_m']==cap['wire']['max_R20_ohm_per_m']>0
 R={w['id']:w['analytic_cut_length_mm']/1000*wire['max_R20_ohm_per_m'] for w in path['wires']}
 assert set(R)=={'C203_W_PLUS','C203_W_MINUS'} and all(abs(R[w['id']]-w['R20_max_ohm'])<1e-15 for w in path['wires'])
 net={(n.get('ref'),n.get('pin')):e.get('name') for e in ET.parse(A/'ecad/wp10_system.xml').getroot().findall('./nets/net') for n in e.findall('node')}
 assert net['C203','1']==net['U203','1']=='WP10_PRECHARGED_PLUS'
 assert net['C203','2']==net['U203','4']=='WP10_INPUT_RETURN' and net['C203','2']!=net['J203','2']
 sb=read('power/SHARED_BATTERY_PATH_CALCULATIONS.json');rows=list(csv.DictReader((A/'thermal/INPUT_PASSIVE_HEAT_LOADS.csv').open(encoding='utf-8-sig')))
 assert len(sb['cases'])==192 and len({q['id'] for q in sb['cases']})==192 and len(rows)==4032
 grouped=collections.defaultdict(list)
 for r in rows:grouped[r['case_id'],r['state']].append(r)
 assert len(grouped)==384
 outputs=[];scenarios=[];reproduction=[]
 for q in sb['cases']:
  for state in ['run','cold']:
   args=dict(q['inputs'])
   if state=='cold':args.update(main_w=0,main_leak_a=0)
   again=solve(**args);z=q[state];assert again['equilibrium_found']==z['equilibrium_found'] is True
   fields=['main_A','aux_A','controller_A','main_leak_A','battery_A','junction_V','main_fused_V','aux_input_V','input_power_W']
   differences={k:abs(again[k]-z[k]) for k in fields};assert max(differences.values())<1e-10
   if state=='run':assert abs(again['main_input_V']-z['main_input_V'])<1e-10
   reproduction.append(dict(case=q['id'],state=state,maximum_scalar_difference=max(differences.values())))
   old=grouped[q['id'],state]
   assert abs(math.fsum(float(r['heat_W']) for r in old)-(z['input_power_W']-z['delivered_output_allocation_W']))<1e-7
   new,detail=refine_row(q,state,old,R);assert verify_candidate(q,state,old,R,new);outputs+=new
   for fraction in [0.,.5,1.]:
    _,d=refine_row(q,state,old,R,fraction);scenarios.append(d)
 assert len(outputs)==4800 and len(scenarios)==1152 and len(reproduction)==384
 anchor=sb['cases'][0];original=grouped[anchor['id'],'run'];baseline,_=refine_row(anchor,'run',original,R);faults=[]
 def reject(name,mutate,state='run'):
  old=grouped[anchor['id'],state];candidate,_=refine_row(anchor,state,old,R);mutate(candidate)
  try:verify_candidate(anchor,state,old,R,candidate);rejected=False
  except AssertionError:rejected=True
  assert rejected,name;faults.append(dict(name=name,rejected=rejected))
 def set_node(candidate,name,value):
  next(r for r in candidate if r['node']==name)['heat_W']=value
 reject('capacitor_heat_not_reduced',lambda x:set_node(x,'input_capacitor_leakage',anchor['run']['heat_W']['input_capacitor_leakage']))
 reject('main_current_used_for_capacitor_wire',lambda x:set_node(x,'C203_W_PLUS_DC_WIRE',anchor['run']['main_A']**2*R['C203_W_PLUS']))
 reject('duplicate_same_wire_heat_node',lambda x:x.append(dict(next(r for r in x if r['node']=='C203_W_PLUS_DC_WIRE'))))
 reject('unknown_2p4Arms_added_as_actual_ripple',lambda x:set_node(x,'C203_W_PLUS_DC_WIRE',2.4**2*R['C203_W_PLUS']))
 reject('cold_open_branch_assigned_leakage',lambda x:set_node(x,'C203_W_PLUS_DC_WIRE',.003**2*R['C203_W_PLUS']),state='cold')
 reject('wire_heat_removed_without_capacitor_reallocation',lambda x:set_node(x,'C203_W_PLUS_DC_WIRE',0))
 reject('millimetres_used_as_metres',lambda x:set_node(x,'C203_W_PLUS_DC_WIRE',anchor['run']['main_leak_A']**2*R['C203_W_PLUS']*1000))
 other_node=next(r['node'] for r in original if r['node']!='input_capacitor_leakage')
 reject('unrelated_heat_node_changed',lambda x:set_node(x,other_node,next(float(r['heat_W']) for r in original if r['node']==other_node)+1e-5))
 reject('wire_row_assigned_to_wrong_state',lambda x:next(r for r in x if r['node']=='C203_W_PLUS_DC_WIRE').update(state='cold'))
 reject('unrelated_heat_sink_reassigned',lambda x:next(r for r in x if r['node']==other_node).update(mechanical_sink_node='C203_W_PLUS'))
 outpath='thermal/CAP_HARNESS_REFINED_HEAT_LOADS_V19.csv'
 with (A/outpath).open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(outputs)
 inputs=['tools/cap_harness_heat_v19.py','tools/shared_battery_path.py','results/CAP_HARNESS_PATH_V19.json','power/CAP_HARNESS_DEFINITION_V19.json','power/CAP_TERMINAL_DEFINITION.json','power/SHARED_BATTERY_PATH_CALCULATIONS.json','power/INPUT_PASSIVE_SELECTION.json','thermal/INPUT_PASSIVE_HEAT_LOADS.csv','ecad/wp10_system.xml',wire['source_file']]
 summary=dict(schema='WP10_CAP_HARNESS_ELECTROTHERMAL_V19',passed=True,case_count=192,state_count=384,heat_rows=4800,correlated_R_bound_scenarios=1152,R20_upper_ohm_by_wire=R,
  source_operating_points_reproduced=reproduction,scenarios=scenarios,faults=faults,inputs={p:sha(p) for p in inputs},output_csv=outpath,output_sha256=sha(outpath),
  actual_ripple_spectrum=None,ripple_2p4A_reference_only=dict(pair_W=2.4**2*sum(R.values()),included_in_heat_ledger=False),
  temperature_scope='20degC manufacturer wire resistance upper bound only; no hot resistance, wire temperature, contact thermal resistance, ripple skin effect or installed inductance qualified',
  source_scope='Current scalar DC inputs/outputs reproduced. Historical geometry-hash fields inside the upstream DC report are not reused as current geometry proof.',
  supersedes_heat_dataset='thermal/INPUT_PASSIVE_HEAT_LOADS.csv',combination_rule='REPLACE for this correlated R20 bookkeeping scenario; never sum parent and refined datasets',
  capacitor_bound_scope='Leakage-branch remainder is correlated with selected wire resistance, not an independent maximum or isolated capacitor-body heat. PCB, solder and contact losses remain within this remainder. R=0,.5Rmax,Rmax are explicitly evaluated; the zero endpoint is a mathematical lower limit, not a zero-resistance wire design.',
  leakage_current_scope='Existing fixed 3mA run scenario derived from the manufacturer 20degC leakage test value; not an all-temperature or actual-work-voltage guarantee.',
  local_allocation_tolerance_W=1e-12,all_other_heat_nodes_unchanged=True,cold_actual_capacitor_voltage=None,
  dynamic_stability_verified=False,wire_temperature_qualified=False,whole_design_complete=False)
 dump('power/CAP_HARNESS_ELECTROTHERMAL_V19.json',summary)
 dump('thermal/ACTIVE_HEAT_LOADS_V19.json',dict(status='CURRENT_WORKING_REFINEMENT_NOT_FULL_THERMAL_RELEASE',source_assembly='mechanical/CAP_HARNESS_INSTANCE_PLAN_V19.json',source_assembly_sha256=sha('mechanical/CAP_HARNESS_INSTANCE_PLAN_V19.json'),heat_dataset=outpath,heat_dataset_sha256=sha(outpath),calculation='power/CAP_HARNESS_ELECTROTHERMAL_V19.json',calculation_sha256=sha('power/CAP_HARNESS_ELECTROTHERMAL_V19.json'),replaces='thermal/INPUT_PASSIVE_HEAT_LOADS.csv',add_to_parent=False,geometry_verified=False,whole_thermal_verified=False))
 print(json.dumps(dict(passed=True,states=384,rows=4800,faults=len(faults),pair_R20=sum(R.values()),max_DC_wire_pair_W=max(math.fsum(s['wire_heat_W'].values()) for s in scenarios),reference_ripple_pair_W=2.4**2*sum(R.values()))))
if __name__=='__main__':build()
