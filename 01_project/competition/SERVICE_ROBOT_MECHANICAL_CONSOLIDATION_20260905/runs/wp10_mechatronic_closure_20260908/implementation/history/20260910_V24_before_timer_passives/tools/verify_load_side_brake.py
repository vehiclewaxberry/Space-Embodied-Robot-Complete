"""Independent scalar/native screening of the installed design, never a hardware test.

Read actual exported XML and actual part values. All unbounded dynamic, energy,
temperature-transfer and OEM limits remain explicit; no device I/O is used.
"""
from pathlib import Path
import csv, hashlib, itertools, json, math, re, xml.etree.ElementTree as ET
from brake_ready_analysis_v22 import evaluate as evaluate_ready
A=Path(__file__).resolve().parents[1]
def read(p): return json.loads((A/p).read_text(encoding='utf-8'))
def dump(p,v): (A/p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
parts=read('power/POWER_LOOP_PARTS.json')
definition=read('power/LOAD_SIDE_BRAKE_DEFINITION.json')
root=ET.parse(A/'ecad/wp10_system.xml').getroot()
comps={c.get('ref'):c.findtext('value') for c in root.findall('./components/comp')}
nets={(p.get('ref'),p.get('pin')):n.get('name') for n in root.findall('./nets/net') for p in n.findall('node')}
def net(ep): return nets.get(tuple(ep.split('.')))
def same(*eps): return net(eps[0]) is not None and len({net(e) for e in eps})==1
checks=[]
def ck(name,condition,**kw): checks.append(dict(name=name,passed=bool(condition),**kw))
def ohm(ref):
    v=parts[ref]['mpn']; m=re.match(r'([0-9.]+)(k|ohm)',v)
    assert m, (ref,v)
    return float(m[1])*(1000 if m[2]=='k' else 1)
def corner(r,t=.0035): return (r*(1-t),r*(1+t))

for ref in definition['refs']:
    ck('native_selected_value_'+ref,comps.get(ref)==parts[ref]['mpn'])
for i in range(3):
    q=f'Q{301+i}'; rb=f'RB{301+i}'; d=f'D{311+i}'
    ron=f'R{311+3*i}'; roff=f'R{312+3*i}'; rpd=f'R{313+3*i}'
    u=f'U{311+i}'; rt=f'RT{311+i}'
    ck(f'branch_{i+1}_load_side',same(rb+'.1','J203.1',d+'.2'))
    ck(f'branch_{i+1}_drain_and_recirculation',same(rb+'.2',q+'.2',d+'.1',d+'.3'))
    ck(f'branch_{i+1}_return',same(q+'.3',rpd+'.2','J203.2'))
    ck(f'branch_{i+1}_independent_gate',same(q+'.1',ron+'.2',roff+'.2',rpd+'.1'))
    ck(f'branch_{i+1}_split_driver',same('U303.2',ron+'.1') and same('U303.3',roff+'.1') and not same('U303.2','U303.3'))
    ck(f'temperature_{i+1}_upstream_supply',same(u+'.5','U120.3') and not same(u+'.5','J203.1'))
    ck(f'temperature_{i+1}_wired_fault_only',same(u+'.1',u+'.6','U106.2','U102.1','U103.1','U104.1') and not same(u+'.1','U106.4'))
    ck(f'temperature_{i+1}_return',same(u+'.2',rt+'.2','J203.2'))
ck('self_bias_all_input_pins_load_side',same('U301.10','U301.11','U301.8','J203.1'))
ck('bias_exposed_pad_is_ground',same('U301.13','U301.5','J203.2'))
ck('bias_outputs_joined',same('U301.2','U301.3','U302.5','U303.1'))
ck('READY_enables_driver_INplus',same('U304.4','U303.6','R310.1') and not same('U301.6','U303.6'))
ck('PG_retained_as_diagnostic_only',same('U301.6','R303.2') and not same('U301.6','U304.4'))
ck('READY_voltage_divider',same('U304.3','R308.2','R309.1') and same('R308.1','U301.2') and same('R309.2','J203.2'))
ck('READY_supply_and_EN',same('U304.1','U304.5','C308.1','U301.2') and same('U304.2','C308.2','J203.2'))
ck('READY_delay_and_receive_pulldown',same('U304.6','C307.1') and same('C307.2','R310.2','J203.2'))
ck('OV_controls_driver_INminus',same('U302.6','U303.5','R307.2'))
ck('thermal_alarm_does_not_remove_sink',not same('U106.2','U303.6') and not same('U106.2','U303.5'))
ck('fault_clears_latches_via_existing_buffer',same('U106.4','U107.1','U108.1'))
ck('three_branches_have_distinct_drains',len({net(f'Q{301+i}.2') for i in range(3)})==3)

source_rows=read('sources/LOAD_SIDE_BRAKE_SOURCE_MANIFEST.json')
for row in source_rows:
    if row['status']=='ACQUIRED': ck('local_source_'+row['file'],sha(A/'sources'/row['file'])==row['sha256'])
# The failed local ST download is recorded, not counted as a successful archive.
source_gaps=[r for r in source_rows if r['status']!='ACQUIRED']

rt,rl=ohm('R301'),ohm('R302'); pg=ohm('R303')
vnom=1.24*(1+rt/rl)+30e-9*rt
vext=[adj*(1+h/l)+iadj*h for adj,h,l,iadj in itertools.product([1.2,1.28],corner(rt),corner(rl),[0,100e-9])]
vmin,vmax=min(vext),max(vext)
bias=dict(MPN=parts['U301']['mpn'],nominal_V=vnom,voltage_sensitivity_V=[vmin,vmax],
          voltage_scope='ADJ full-temperature range plus IADJ 0..100nA 25C sensitivity; resistor0.1%+25ppm/K*100K allocation, not a combined OEM guarantee',
          PG_low_current_upper_sensitivity_A=vmax/min(corner(pg)),PG_max_allowed_sink_A=50e-6,
          PG_high_V_typical_200k_input=vnom*200000/(pg+200000),PG_high_guaranteed_min_V=None,
          PG_high_gaps=['LT3013 PWRGD high-state maximum leakage absent','UCC27511 internal input pull-down resistance tolerance absent'],
          legacy_PG_model_retired=True,PG_drives_enable=False,
          driver_VIH_max_V=2.0,driver_VIL_limit_V=0.8,
          CT_F=definition['parameters']['CT_F'],CT_typical_delay_s=1.6*definition['parameters']['CT_F']/3e-6,
          CT_guaranteed_delay_range_s=None,CT_scope='1.6V and3uA typical;6uA maximum only at25C; not a full delay guarantee',
          output_absolute_V=[-60,60],input_minus_output_absolute_V=[-80,80],reverse_output_protection_source='LT3013 RevE p17; reverse current <2uA is typical, not a guaranteed maximum',
          output_effective_min_cap_F=10e-6,selected_output_nominal_cap_F=22e-6,installed_cap_derating_verified=False)
ck('PG_low_current_screen_under_50uA',bias['PG_low_current_upper_sensitivity_A']<50e-6)
ready=evaluate_ready(parts,definition,bias)
for key,value in ready['checks'].items():ck('READY_'+key,value)
ck('PG_typical_model_has_no_current_enable_credit',not bias['PG_drives_enable'])

rh,rb=ohm('R305'),ohm('R306')
def ov_corners(thresholds):
    return [v*(1+h/l)+ib*h for v,h,l,ib in itertools.product(thresholds,corner(rh),corner(rb),[-15e-9,15e-9])]
ovrise=ov_corners([.396,.404]); ovfall=ov_corners([.387,.4])
ov=dict(nominal_rising_V=.4*(1+rh/rb),nominal_falling_V=.3945*(1+rh/rb),
        rising_sensitivity_V=[min(ovrise),max(ovrise)],falling_sensitivity_V=[min(ovfall),max(ovfall)],
        input_bias_scope='INB +/-15nA measured at0.1V; transferred to0.4V only as sensitivity',
        independent_corner_overlap_is_not_negative_hysteresis=True,hysteresis_guaranteed_min_V=None,
        resistor_temperature_allocation_C=100,filter_typical_RC_s=rh*rb/(rh+rb)*100e-12,
        comparator_delay_typical_us=[18,29],delay_scope='VDD5V,10mV overdrive only; circuit VDD~12V; max unspecified',
        guaranteed_bus_peak_V=None,DM_public_nominal_OV_setting_V=32.,DM_guaranteed_earliest_trip_V=None)
ck('nominal_chb_plus5pct_below_earliest_OV_screen',24*1.05<min(ovrise))
ck('static_OV_screen_below_public32_not_rating',max(ovrise)<32 and ov['guaranteed_bus_peak_V'] is None)

# Vishay material A full R-T nominal curve, p4. B variation is a declared
# sensitivity around that curve, not a fabricated guaranteed covariance model.
def ntc_R(temp,r25scale=1.,bscale=1.):
    tk=temp+273.15
    nominal=10000*math.exp(-14.6337+4791.842/tk-115334/tk**2-3.730535e6/tk**3)
    return nominal*r25scale*math.exp(3977*(bscale-1)*(1/tk-1/298.15))
def sensor_nodes(temp,vs=3.3,rh=8200.,ra=649000.,rb=100000.,r25scale=1.,bscale=1.,ia=0.,ib=0.,fault=None):
    if fault=='short': return 0.,-ib/(1/ra+1/rb)
    rn=math.inf if fault=='open' else ntc_R(temp,r25scale,bscale)
    aa=1/rh+1/rn+1/ra; bb=1/ra+1/rb; cross=-1/ra
    b1=vs/rh-ia; b2=-ib; det=aa*bb-cross*cross
    return (b1*bb-cross*b2)/det,(aa*b2-cross*b1)/det
def trip(th=.3945,**kw):
    lo,hi=-40.,125.
    assert sensor_nodes(lo,**kw)[0]>th>sensor_nodes(hi,**kw)[0]
    for _ in range(60):
        mid=(lo+hi)/2
        if sensor_nodes(mid,**kw)[0]>th:lo=mid
        else:hi=mid
    return (lo+hi)/2
stop_source=A.parent/'electrical/STOP_SUPPLY_CALCULATIONS.json'
stop=json.loads(stop_source.read_text())
rail=stop['rail3V3_V']
temp_corners=[]; reset_corners=[]; open_nodes=[]; at0_open=[]; at50_hot=[]
for vs,rh,ra,rb,r25s,bs,ia,ib in itertools.product(rail,corner(ohm('R341')),corner(ohm('R342')),corner(ohm('R343')),[.98,1.02],[.9925,1.0075],[-25e-9,25e-9],[-15e-9,15e-9]):
    kw=dict(vs=vs,rh=rh,ra=ra,rb=rb,r25scale=r25s,bscale=bs,ia=ia,ib=ib)
    for th in [.387,.4]: temp_corners.append(trip(th,**kw))
    for th in [.396,.404]: reset_corners.append(trip(th,**kw))
    open_nodes.append(sensor_nodes(25,fault='open',**kw)[1])
    at0_open.append(sensor_nodes(0,**kw)[1]);at50_hot.append(sensor_nodes(50,**kw)[0])
state=[]
for t in [-40,-20,0,25,50,80,85,100,120]:
    va,vb=sensor_nodes(t); rn=ntc_R(t)
    state.append(dict(temperature_C=t,nominal_R_ohm=rn,INA_V=va,INB_V=vb,hot_after_heating=va<.3945,open_or_cold_after_cooling=vb>.4,NTC_self_heating_W=va*va/rn))
thermal=dict(NTC_MPN=parts['RT311']['mpn'],nominal_curve_source='ntcle100.pdf07-May-2025 p4 materialA; T in kelvin',
    nominal_hot_trip_C=trip(),nominal_reset_C=trip(.4),hot_trip_sensitivity_C=[min(temp_corners),max(temp_corners)],reset_sensitivity_C=[min(reset_corners),max(reset_corners)],
    sensitivity_cases=len(temp_corners),corner_scope='R25 2%, B0.75% exponential sensitivity, 0.1%+25ppm/K*100K divider allocation, 25/15nA input bias transferred from different VI; old STOP static rail screen only',
    STOP3V3_static_assumption_V=rail,STOP3V3_source=str(stop_source),STOP3V3_source_sha256=sha(stop_source),STOP3V3_source_scope=stop['scope'],STOP3V3_dynamic_verified=False,guaranteed_resistor_case_trip_C=None,
    open_INB_sensitivity_min_V=min(open_nodes),open_upper_threshold_max_V=.404,short_INA_ideal_V=0.,
    nominal_temperature_states=state,NTC_nominal_dissipation_factor_W_per_K=.007,
    dissipation_factor_scope='information only, not vacuum or mounted thermal transfer',
    nominal_time_constant_s=15,thermal_time_constant_scope='information only; resistor-to-sensor response unbound',
    NTC_coating_insulation_rating=None,NTC_potting_permitted=False,
    six_outputs_added_leak_A=6*.3e-6,additional_FAULT_high_drop_V=6*.3e-6*(10000*1.01*1.0025),
    FAULT_low_single_output_pullup_current_A=rail[1]/(10000*.99*.9975),other_original_fault_leakage_budget_included=False,
    FAULT_pullup_R101_MPN='CRCW060310K0FKEA',FAULT_R101_TCR_per_K=100e-6,FAULT_R101_temperature_delta_K=25.,
    alarm_clears_existing_stop_latches=True,alarm_removes_sink=False,temperature_fault_does_not_prove_energy_capacity=True)
full_fault_path=A/'power/STOP_FULL_FAULT_BUDGET.json'
if full_fault_path.exists():
    full_fault=json.loads(full_fault_path.read_text(encoding='utf-8'))
    if full_fault['native_xml_sha256']==sha(A/'ecad/wp10_system.xml') and full_fault['checks_passed']:
        thermal.update(other_original_fault_leakage_budget_included=True,
            full_FAULT_inventory_source='power/STOP_FULL_FAULT_BUDGET.json',
            full_FAULT_inventory_sha256=sha(full_fault_path),
            full_FAULT_leak_sensitivity_A=full_fault['total_leak_sensitivity_A'],
            full_FAULT_high_min_sensitivity_V=full_fault['RAW_high_min_sensitivity_V'],
            full_FAULT_threshold_and_dynamic_guarantee=False)
ck('open_sensor_static_screen_detected',min(open_nodes)>.404)
ck('short_sensor_pulls_hot_alarm',sensor_nodes(25,fault='short')[0]<.387)
ck('normal_0to50_no_false_nominal_thermal_alarm',all(not x['hot_after_heating'] and not x['open_or_cold_after_cooling'] for x in state if 0<=x['temperature_C']<=50))
ck('normal_0to50_no_false_corner_thermal_alarm',max(at0_open)<.387 and min(at50_hot)>.404,zero_C_INB_max=max(at0_open),fifty_C_INA_min=min(at50_hot))
ck('STOP_source_is_static_not_measurement','NOT_MEASUREMENT' in stop['scope'])
ck('FAULT_new_leak_budget_included',thermal['additional_FAULT_high_drop_V']>0)
ck('resistor_case_limit_not_inferred_from_NTC',thermal['guaranteed_resistor_case_trip_C'] is None)

# Separate resistive on-state capacity from energy and hardware thermal limits.
rmin=1*(1-.05)*(1-.0005*95); rmax=1*(1+.05)*(1+.0005*95)
resistor=dict(MPN=parts['RB301']['mpn'],branches=3,R25_ohm=1.,nominal_parallel_ohm=1/3,
    resistance_120C_initial_TCR_screen_ohm=[rmin,rmax],temperature_reference_C=25.,working_layer_limit_C=120.,
    TCR_per_C=500e-6,tolerance=.05,end_of_life_drift_not_included=True,
    life_test_allowed_resistance_change_ohm=.005*1+.05,
    nominal_full_on_W=3*ov['nominal_rising_V']**2,
    full_on_screen_W=[3*min(ovrise)**2/rmax,3*max(ovrise)**2/rmin],
    branch_current_screen_max_A=max(ovrise)/rmin,continuous_OEM_rating_W_each=300,
    continuous_OEM_case_condition_C=85,junction_to_case_K_per_W=.112,
    overload_test_description='4x rated power for10s is a datasheet test; it is not authorization for arbitrary repetitive pulses',
    installed_heat_path_K_per_W=None,mission_energy_J=None,mission_regen_peak_A=None,
    mission_pulse_duration_s=None,repeat_duty_cycle=None,full_mission_capability_verified=False)

# Bias is an additional physical load; arm demand stays360W. One watt is a
# reserved main-output allocation to be verified, not a fabricated source maximum.
budget=dict(arm_task_power_W=360.,brake_main_output_reserved_W=1.,main_output_design_allocation_W=361.,
    startup_primary_reserved_W=.25,startup_primary_reserve_verified=False,
    reserved_brake_power_is_not_verified_maximum=True,gate_charge_10V_source_max_C=153e-9,
    gate_charge_source_conditions='CSD19536KTT: VGS10V,VDS50V,ID100A; not guaranteed for this12V drive',
    illustrative_switching_Hz=20000.,illustrative_3gate_10V_current_A=3*153e-9*20000,
    switching_frequency_guaranteed_max_Hz=None,gate_bias_12V_average_current_A=None,
    STOP_monitor_static_current_screen_A=3*(rail[1]/min(corner(8200.))+13e-6)+thermal['FAULT_low_single_output_pullup_current_A'],
    STOP_monitor_draw_allocated_within_existing_aux_10W=True,aux_total_allocation_W=16.8,
    source_limit_not_increased=True)
power=read('power/POWER_LOOP_CALCULATIONS.json')
updated=[]
for old in power['scenarios']:
    vb=old['battery_loaded_V'];r=old['series_R_ohm_assumed'];eta=old['main_eta_assumed']
    disc=vb*vb-4*r*(361/eta+budget['startup_primary_reserved_W'])
    im=(vb-math.sqrt(disc))/(2*r) if disc>=0 else None
    vfused=vb-im*old['resistance_before_MAIN_FUSED_ohm_assumed'] if im is not None else None
    usable=old['available_current_margin_after_UVLO_screen_A'] is not None and vfused>=max(power['UVLO_falling_screen_V'])
    updated.append(dict(battery_loaded_V=vb,main_eta_assumed=eta,path_R_ohm=r,main_input_A=im,
       aux_input_A=old['aux_input_A'],battery_total_A=im+old['aux_input_A'] if im else None,startup_primary_reserved_W=budget['startup_primary_reserved_W'],
       sense_voltage_V=vfused,conditional_limit_margin_A=power['current_limit_screen_A'][0]-im if usable else None))
budget['source_current_scenarios_361W']=updated
budget['READY_monitor_increment_sensitivity_W_at_assumed_bus32V']=ready['added_load_at_bus32V_sensitivity_W']
budget['READY_increment_is_within_unverified_1W_reserve_not_extra_task_load']=True
budget['replacement_driver_quiescent_max_test_A']=.001
budget['replacement_driver_IQ_scope']='MAX5048C non-switching at14V; replaces UCC27511, not added in parallel. Dynamic gate loss unbound.'
ck('task360W_preserved_plus_actual_bias_allocation',power['arm_output_W']==360 and budget['main_output_design_allocation_W']>360)
ck('independent_stop_load_not_double_counted',budget['aux_total_allocation_W']==power['aux_output_W']==16.8)

# Controlled falsifiers, not mission values: source loss while a motor returns
# 80A and the comparator/driver is delayed. Unknown installed capacitance is
# never filled with a retired commercial module's800uF.
delay_cases=[]
for assumed_C in [.0008,.01,.1]:
    for assumed_delay in [50e-6,.003]:
        delay_cases.append(dict(assumed_C_F=assumed_C,assumed_I_A=80.,assumed_delay_s=assumed_delay,
            starting_V=max(ovrise),unsunk_bus_V=max(ovrise)+80*assumed_delay/assumed_C,
            fictitious_stress_example_not_mission=True))
dynamic=dict(installed_bus_C_F=None,guaranteed_clamp_peak_V=None,delay_counterexamples=delay_cases,
    timing_guarantee_open=True,boot_into_regeneration_open=True,motor_as_built_trip_bound_open=True,
    sensor_temperature_not_resistor_film_temperature=True,inductor_current_after_switch_off_path_present=True,
    PCB_loop_inductance_and_diode_pulse_qualification_open=True)
ck('delayed_clamp_counterexample_reproduced',any(x['unsunk_bus_V']>32 for x in delay_cases))
out=dict(schema='WP10_LOAD_SIDE_BRAKE_ANALYTICAL_V22',status='READY_INTERFACE_CHANGED__CONDITIONAL_STATIC_SCREEN__DYNAMIC_ENERGY_THERMAL_OPEN',
    native_netlist_sha256=sha(A/'ecad/wp10_system.xml'),definition_sha256=sha(A/'power/LOAD_SIDE_BRAKE_DEFINITION.json'),
    selected_parts_sha256=sha(A/'power/POWER_LOOP_PARTS.json'),bias=bias,ready_interface=ready,absolute_OV=ov,thermal_monitor=thermal,
    resistor_branches=resistor,power_budget_delta=budget,dynamic_gaps_and_counterexamples=dynamic,
    source_local_archive_gaps=source_gaps,actual_circuit_integrated=True,physical_hardware_installed=False,
    whole_brake_function_verified=False,manufacture_release=False,energization_authorized=False,
    checks=checks,check_count=len(checks),checks_passed=all(x['passed'] for x in checks))
dump('power/LOAD_SIDE_BRAKE_CALCULATIONS.json',out)
dump('power/BRAKE_READY_CALCULATIONS_V22.json',dict(**ready,native_xml_sha256=sha(A/'ecad/wp10_system.xml'),calculator_sha256=sha(A/'tools/brake_ready_analysis_v22.py')))
dump('results/LOAD_SIDE_BRAKE_VERIFICATION.json',{k:v for k,v in out.items() if k in ['schema','status','native_netlist_sha256','definition_sha256','selected_parts_sha256','check_count','checks','checks_passed','whole_brake_function_verified','physical_hardware_installed']})
power['regen'].update(absolute_sink_circuit_integrated=True,selected_circuit='LT3013+MAX16053+TLV6700+MAX5048C+3xLPS0300H1R00JB+3xCSD19536KTT',
    absolute_circuit_calculations='power/LOAD_SIDE_BRAKE_CALCULATIONS.json',full_function_verified=False)
power['additional_brake_budget']=dict(reserved_main_W=1.,total_main_design_allocation_W=361.,arm_W_unchanged=360.,
    static_and_dynamic_details='power/LOAD_SIDE_BRAKE_CALCULATIONS.json',aux_monitors_within_existing_10W=True,
    reserved_main_allowance_verified=False)
power['startup_primary_budget']=dict(reserved_W=.25,reference='PRECHARGED_PLUS, input-side load outside CHB efficiency',already_in_brake_augmented_input_current_scenarios=True,verified_maximum=False)
dump('power/POWER_LOOP_CALCULATIONS.json',power)
print(json.dumps(dict(checks=len(checks),passed=out['checks_passed'],OV=ov['rising_sensitivity_V'],hot_C=thermal['hot_trip_sensitivity_C'],
    nominal_hot_C=thermal['nominal_hot_trip_C'],open_INB_min=thermal['open_INB_sensitivity_min_V'],full_function_verified=False)))
assert out['checks_passed'],[x for x in checks if not x['passed']]
