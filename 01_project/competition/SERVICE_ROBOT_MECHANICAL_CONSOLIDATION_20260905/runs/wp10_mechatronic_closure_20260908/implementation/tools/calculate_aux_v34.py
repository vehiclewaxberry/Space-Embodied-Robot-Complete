"""Same-task, source-bound auxiliary protection and main-limit comparison."""
from pathlib import Path
import ast,copy,hashlib,itertools,json,math,types,collections
from dataclasses import asdict
from shared_battery_path import current,solve
from hotswap_transient_model_v23 import Circuit
from aux_operating_point_v34 import operating_point as auxiliary_point
A=Path(__file__).resolve().parents[1];R=A/'results/aux_v34';D=A/'ecad/revisions/v34'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(n,x):(R/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
    parent=read(A/'coupled_closure/CANDIDATE_V30.json');new=copy.deepcopy(parent)
    p=read(A/'power/POWER_LOOP_CALCULATIONS.json');s=read(A/'power/SHARED_BATTERY_PATH_DEFINITION.json')
    rslo=.0025*(1-.017575)-.00001;rshi=.0025*(1+.017575)+.00001
    ilmain=[.0485/rshi,.0615/rslo]
    rtol=(1+.001)*(1+25e-6*100)-1
    auxlims=[2.11/(1+rtol),2.35/(1-rtol)]
    native=read(R/'NATIVE_AUDIT.json')
    connector=read(R/'CONNECTOR_INTERFACE.json');contact_nom=connector['initial_aggregate_resistance_scenario_ohm']
    # Actual routed track lengths/widths, 35um nominal copper, 100C sensitivity.
    # Via barrel: 0.3mm finished hole, 20um assumed copper plating, 1.6mm board.
    via_R20=1.724e-8*.0016/(math.pi*((.00015+.00002)**2-.00015**2))
    pcb_R100=(native['track_series_total_R20_ohm']+sum(native['power_net_via_counts'].values())*via_R20)*(1+.00393*80)
    e=new['electrical'];e['main_R_components_ohm']['shunts']=.0025
    e['aux_R_components_ohm']={'legacy_F202_typical_cold':.018,'legacy_unmeasured_wiring_budget':.022,
      'TPS26600_max_Ron_in_0p1_to_2A_domain':.25,'new_PCB_series_conservative_100C_model':pcb_R100,
      'four_mated_contacts_plus_four_crimps_initial_test_transfer':contact_nom}
    e['aux_R_ohm']=sum(e['aux_R_components_ohm'].values())
    # Allocation puts the new board return resistance before the IQ split as a loop equivalent.
    e['aux_protection_model']={'consumer':'tools/aux_operating_point_v34.py','quiescent_current_A':.00039,
      'on_resistance_ohm':.25,'before_efuse_IQ_ohm':.018+pcb_R100+contact_nom,
      'current_limit_conditional_A':auxlims,'UVLO_falling_screen_V':[13.25,14.75],
      'UVLO_rising_screen_V':[14.25,15.75],'OVP_rising_screen_V':[31,34],
      'source_voltage_spec_conditions_V':24,'cold_start_verified':False,
      'legacy_coupled_adapter_is_not_valid_consumer':True,'external_contact_bound_known':False}
    e['protection_screens']['current_limit_screen_A']=ilmain
    ns={'math':math,'power':types.SimpleNamespace(solve=solve)}
    src=ast.parse((A/'coupled_closure/coupled_adapter.py').read_text())
    exec(compile(ast.Module(body=[n for n in src.body if isinstance(n,ast.FunctionDef) and n.name=='operating_point'],type_ignores=[]),'audited_pure_operating_point','exec'),ns)
    # Exact device-IQ branch: existing 3mA remains main-fused, new390uA is after auxiliary pre-R.
    def point(c,pack,shared,eta,hot,iq=0):
      if not iq:return ns['operating_point'](c,pack,shared,eta,hot,100)
      return auxiliary_point(c,pack,shared,eta,hot)
    pairs=[]
    for pack,shared,eta,hot in itertools.product(e['pack_V_scenarios'],e['shared_R_scenarios_ohm'],e['eta_main_scenarios'],e['Q201_hot_R_multiplier_scenarios']):
      pairs.append(dict(inputs=[pack,shared,eta,hot],V32=point(parent,pack,shared,eta,hot),V34=point(new,pack,shared,eta,hot,.00039)))
    counts={rev:dict(collections.Counter(q[rev]['protection_class'] for q in pairs)) for rev in ['V32','V34']}
    good=[q['V34'] for q in pairs if q['V34']['protection_class']=='CONDITIONAL_HOLD_STARTUP_UNVERIFIED']
    contact_sensitivity=[dict(inputs=q['inputs'],mated_contacts_aggregate_scenario_ohm=contact,
      output=auxiliary_point(new,*q['inputs'],contact_extra_ohm=contact-contact_nom)) for q in pairs for contact in [0,connector['post_stress_aggregate_resistance_scenario_ohm']]]
    # 384 matching endpoint-model startup cases; all old physical assumptions retained and disclosed.
    cs=s['cases'];profiles=[(rshi,30100*(1-rtol),.76,.0485),(rslo,30100*(1+rtol),1.24,.0615)]
    rows=[];fault=[]
    for i,(vp,rsrc,rmain,raux,eta,pr,uvi) in enumerate(itertools.product(cs['pack_V'],cs['shared_contact_loop_R_ohm'],cs['main_branch_allocations_ohm'],cs['aux_branch_R_ohm'],cs['aux_efficiency'],profiles,[0,1])):
      c=Circuit(vp,rsrc,rmain['before_MAIN_FUSED'],rmain['total']+.0003,raux+(e['aux_R_ohm']-.04),16.8/eta,*pr,p['UVLO_rising_screen_V'][uvi],p['UVLO_falling_screen_V'][uvi],.00264)
      q=c.precharge();q.pop('trace');rows.append(dict(id=i,inputs=asdict(c),**q))
      if c.source(0)[2]>=c.uv_rise:
        f=c.regulated(0);fault.append(dict(id=i,current_A=f['main_a'],regulated_block_W=f['block_w'],regulated_only=True))
    completed=[q for q in rows if q['outcome']=='REGULATION_EXIT_REDUCED_MODEL'];worst=max(completed,key=lambda q:q['active_limit_s'])
    fine=Circuit(**worst['inputs']).precharge(.00625);fine.pop('trace')
    initial_timer_min=.9e-6*3.76/120e-6
    checks=[dict(name='32_cases_classification_preserved',passed=all(q['V32']['protection_class']==q['V34']['protection_class'] for q in pairs)),
      dict(name='360W_arm_plus_1W_bias_preserved',passed=e['main_output_W']==361),
      dict(name='steady_bounded_fault_sum_below_30A',passed=ilmain[1]+auxlims[1]+.003+.00039<30),
      dict(name='normal_aux_below_min_limit',passed=max(q['aux_A'] for q in good)<auxlims[0]),
      dict(name='normal_aux_inside_Ron_spec_current_domain',passed=max(q['aux_A'] for q in good)<2),
      dict(name='explicit_aux_hold_thresholds_at_32_points',passed=all(q['V34']['aux_protection_class']=='CONDITIONAL_AUX_ON_STARTUP_UNVERIFIED' for q in pairs)),
      dict(name='main_precharge_quadrature_converged',passed=abs(fine['active_limit_s']-worst['active_limit_s'])/fine['active_limit_s']<.005),
      dict(name='unchanged_1uF_timer_project_allowance',passed=initial_timer_min>fine['active_limit_s']*1.5),
      dict(name='parent_files_unchanged',passed=all(sha(Path(p))==h for p,h in read(R/'PARENT_SOURCE_LOCK.json').items()))]
    auxstart=[dict(output_load_W=w,THN_turn_on_voltage_scenario_V=v,input_power_W=w/.8,
      required_A=w/.8/v,limited_current_min_A=auxlims[0],cap_charge_margin_A=auxlims[0]-w/.8/v,
      status='NO_POSITIVE_CAP_CHARGE_MARGIN' if auxlims[0]<=w/.8/v else 'POSITIVE_ALGEBRAIC_MARGIN_ONLY') for w,v in itertools.product([10,16.8],[8,9,12,15])]
    source_paths=[D/'wp10_system.xml',D/'wp10_aux_protection.kicad_sch',D/'wp10_power_1.kicad_sch',D/'wp10_aux_protection.kicad_pcb',
      Path(__file__),A/'tools/aux_operating_point_v34.py',A/'tools/shared_battery_path.py',A/'tools/hotswap_transient_model_v23.py',
      A/'coupled_closure/coupled_adapter.py',A/'coupled_closure/CANDIDATE_V30.json',R/'NATIVE_AUDIT.json',
      A/'power/POWER_LOOP_CALCULATIONS.json',A/'power/SHARED_BATTERY_PATH_DEFINITION.json',R/'CONNECTOR_INTERFACE.json']
    out=dict(revision='V34',source_bindings={str(p):sha(p) for p in source_paths},
      main_total_shunt_ohm=.0025,main_shunt_including_TCR_Kelvin_ohm=[rslo,rshi],main_limit_conditional_A=ilmain,
      auxiliary_limit_conditional_A=auxlims,aux_RILIM_ohm=5360,aux_MODE_ohm=402000,
      steady_fault_sum_conditional_A=ilmain[1]+auxlims[1]+.003+.00039,
      instantaneous_battery_current_upper_bound_A=None,short_circuit_wire_fuse_coordinated=False,
      specification_transfer='LM5069 table48V; TPS26600 table24V/1V and5V drop. +/-100K resistor drift allocation. Not certified bounds over actual source/load transients.',
      checks=checks,scoped_checks_passed=all(q['passed'] for q in checks),paired_counts=counts,paired_cases=pairs,
      auxiliary_PCB_R100_series_model_ohm=pcb_R100,aux_via_barrel_R20_model_ohm=via_R20,
      aux_R_components_ohm=e['aux_R_components_ohm'],auxiliary_total_R_ohm=e['aux_R_ohm'],
      contacts_are_unmeasured_specification_transfer=True,connector_interface=connector,contact_resistance_sensitivity=contact_sensitivity,
      main_startup_cases=rows,main_startup_outcomes=dict(collections.Counter(q['outcome'] for q in rows)),main_startup_worst=worst,main_startup_refined=fine,
      timer_min_requirement_s=initial_timer_min,timer_after_1p5_project_allowance_s=initial_timer_min-fine['active_limit_s']*1.5,
      main_short_prefixes=fault,main_startup_scope='Existing reduced model, auxiliary eFuse already on. New390uA IQ not included in this legacy startup solver; not a complete combined cold-start proof.',
      auxiliary_startup_counterexamples=auxstart,THN_inrush_or_internal_input_capacitance_known=False,
      stop_manual_rearm_and_brownout_verified=False,efuse_fault_to_latch_time_max_s=None,efuse_Ron_fault_extrapolation_allowed=False,
      hardware_tests=0,whole_design_complete=False,power_on_release=False)
    dump('CALCULATIONS.json',out);dump('ELECTRICAL_CANDIDATE.json',new['electrical'])
    print(json.dumps(dict(counts=counts,main_limit=ilmain,aux_limit=auxlims,total=out['steady_fault_sum_conditional_A'],worst_s=fine['active_limit_s'],timer_margin_s=out['timer_after_1p5_project_allowance_s'],checks=checks)))
if __name__=='__main__':main()
