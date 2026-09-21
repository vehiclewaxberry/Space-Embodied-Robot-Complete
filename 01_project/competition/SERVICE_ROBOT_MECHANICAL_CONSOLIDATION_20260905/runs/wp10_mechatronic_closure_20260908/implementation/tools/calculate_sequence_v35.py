"""Native-netlist-bound static budgets and explicitly conditional startup envelopes."""
from pathlib import Path
import json,itertools,math,copy,hashlib,xml.etree.ElementTree as ET,collections
from aux_operating_point_v35 import operating_point
A=Path(__file__).resolve().parents[1];D=A/'ecad/revisions/v35';R=A/'results/aux_v35'
def dump(n,x):(R/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bounds(n,tol=.001):return n*(1-tol)*(1-.0025),n*(1+tol)*(1+.0025)
def main():
    x=ET.parse(D/'wp10_system.xml').getroot();cs={c.get('ref'):c for c in x.findall('./components/comp')}
    selected=json.loads((R/'SELECTED_PARTS.json').read_text())
    assert len(cs)==237 and cs['R231'].findtext('value')=='1.80k'
    for ref,p in selected.items():
        mpn=next(f.text for f in cs[ref].findall('./fields/field') if f.get('name')=='MPN');assert mpn==p['MPN'],(ref,mpn,p['MPN'])
    # R231 is taken from the active source and selection, not an earlier XML.
    rt=bounds(selected['R225']['resistance_ohm']);rb=bounds(selected['R226']['resistance_ohm']);rp=bounds(selected['R227']['resistance_ohm'])
    fvals=[];uvals=[]
    for top,bot,vref,leak,hys in itertools.product(rt,rb,[.792,.808],[-1e-7,1e-7],[.0394,.0406]):
        fvals.append(vref*(1+top/bot)+leak*top);uvals.append((vref+hys)*(1+top/bot)+leak*top)
    vf=[min(fvals),max(fvals)];vu=[min(uvals),max(uvals)]
    rhi=bounds(38300);rlo=bounds(10000);bleed=bounds(selected['R231']['resistance_ohm'],.01)
    bias=[1.2*(1+rhi[0]/rlo[1]),1.28*(1+rhi[1]/rlo[0])+1e-7*rhi[1]]
    rem=[bias[0]-(.001+.0000003)*rp[1],bias[1]+.0005*rp[1]]
    low_sink=bias[1]/rp[0]+.0005
    c=[1e-7*.95*.997,1e-7*1.05*1.003]
    trc=[-math.log(.31)*877000*c[0],-math.log(.25)*1147000*c[1]]
    slew=[4e-6*23.75/c[1],5.5e-6*25.5/c[0]]
    parent=json.loads((A/'results/aux_v34/CALCULATIONS.json').read_text());il=parent['auxiliary_limit_conditional_A']
    static=dict(UV_falling_V=vf,UV_rising_V=vu,bias_V=bias,remote_high_V=rem,remote_low_screen_V=.3,
        supervisor_sink_required_A=low_sink,bleed_minus_remote_source_A=bias[0]/bleed[1]-.0005-.001,
        D210_reverse_leakage_screen_A=.001,diode_leakage_basis='ST Rev3 Table3:1mA max at125C/VR100V pulse; conservative transfer to actual lower reverse bias, not measured leakage',
        bias_minimum_load_required_A=.001,RC_delay_cold_s=trc,typical_RC_delay_s=-math.log(.28)*.1,
        no_cap_delay_max_s_at_20pct_overdrive=.00004,initial_device_delay_max_s=.002,
        maximum_reset_latency_at_small_overdrive_s=None,CTR_full_discharge_min_duration_screen_s=.05*(trc[1]+.00004),
        eFuse_output_slew_screen_V_per_s=slew,aux_current_limit_conditional_A=il,
        U208_VDD_OR=['D209:AUX_LIMITED to SEQ_VDD','D210:REMOTE_BIAS to SEQ_VDD'],
        added_control_input_allocation_A=.030,control_allocation_is_not_manufacturer_guarantee=True,
        source_test_conditions_transfer='THN published defaults nominal input/resistive full load25C; TI currents/slew and resistor100K budget transferred as scenarios',
        capacitor_effective_C_and_LDO_transient_verified=False)
    # Keep 360W arm and16.8W secondary budgets; allocate additional primary control current.
    e=copy.deepcopy(json.loads((A/'results/aux_v34/ELECTRICAL_CANDIDATE.json').read_text()));e['sequence_input_allocation_A']=.030
    e['aux_protection_model']['consumer']='tools/aux_operating_point_v35.py'
    e['aux_protection_model']['previous_consumer_not_valid_for_V35']='tools/aux_operating_point_v34.py omits the new control-current allocation'
    e['sequence_allocation_scope']='AUX downstream lumped conservative allocation; not measured circuit current or exact distributed harness tap model'
    cases=[]
    for pack,shared,eta,hot,extra in itertools.product(e['pack_V_scenarios'],e['shared_R_scenarios_ohm'],e['eta_main_scenarios'],e['Q201_hot_R_multiplier_scenarios'],[-.06,0,.08]):
        point=operating_point({'electrical':e},pack,shared,eta,hot,contact_extra_ohm=extra)
        if point['equilibrium_found']:
            v=point['aux_input_V'];point['sequence_class']='NO_NEW_RELEASE_AT_ASSUMED_ON_POINT' if v<vu[0] else 'RELEASE_CORNER_DEPENDENT_AT_ASSUMED_ON_POINT' if v<vu[1] else 'VOLTAGE_QUALIFIED_AT_ASSUMED_ON_POINT'
            point['tCTR_max_test_overdrive_met']=v>=1.2*vu[1]
        cases.append(dict(inputs=[pack,shared,eta,hot,extra],result=point))
    # Simple positive charge invariant. It cannot prove THN internal startup current.
    old=[dict(THN_input_V=v,load_W=16.8,headroom_A=il[0]-.030-21/v) for v in [7.5,8,8.8,9]]
    headroom=il[0]-.030-21/vu[0]
    starts=[]
    for bus,cap,slope,delay in itertools.product([16.,18.,20.,22.,25.2,29.4],[10e-6,100e-6,470e-6,1e-3,2.2e-3],slew,[0,trc[0],trc[1]]):
        # Typical OFF current is explicitly a scenario; manufacturer max not provided.
        ioff=.030+.0025;rate=min(slope,(il[0]-ioff)/cap)
        if bus<vu[1]:row=dict(state='SOME_OR_ALL_CORNERS_HELD_OFF',bus_V=bus)
        else:
            v_at_enable=min(bus,vu[0]+rate*delay);needed=21/v_at_enable+.030
            row=dict(state='POSITIVE_CPL_CHARGE_MARGIN_SCENARIO',bus_V=bus,voltage_at_enable_V=v_at_enable,
                precharge_time_to_max_threshold_s=vu[1]/rate,required_after_enable_A=needed,charge_headroom_A=il[0]-needed,
                residual_cap_slew_V_per_s=min(slope,(il[0]-needed)/cap),delay_is_warm_zero_or_RC_scenario=True)
        row.update(C_input_scenario_F=cap,ramp_scenario_V_per_s=slope,release_delay_scenario_s=delay);starts.append(row)
    # Preserve counterexamples instead of filling timing gaps with ideal delays.
    warm=[]
    for frac,duration in itertools.product([0,.25,.5,.71],[1e-6,1e-4,.001,.01,.1]):
        warm.append(dict(CTR_initial_fraction_of_internal_charge_target=frac,fault_duration_s=duration,
            specified_full_discharge_duration_screen_met=duration>static['CTR_full_discharge_min_duration_screen_s'],
            possible_RC_to_threshold_s=0 if frac>=.69 else -math.log((1-.69)/(1-frac))*877000*c[0],
            actual_recovered_CTR_fraction=None,reason='Discharge trajectory and detection delay at arbitrary overdrive not bounded',system_state='UNKNOWN_NO_REARM_CREDIT'))
    counterexamples=[
        dict(name='OLD_OPEN_REMOTE_LOW_INPUT_CPL',observed=min(v['headroom_A'] for v in old),rejected_as_closed=min(v['headroom_A'] for v in old)<0),
        dict(name='WRONG_BLEED_4K7',net_A=bias[0]/bounds(4700,.01)[1]-.0005,rejected_as_closed=bias[0]/bounds(4700,.01)[1]-.0005<.001),
        dict(name='MISSED_OR_DIODE_REVERSE_LEAKAGE_2K7',net_A=bias[0]/bounds(2700,.01)[1]-.0005-.001,rejected_as_closed=bias[0]/bounds(2700,.01)[1]-.0005-.001<.001),
        dict(name='WARM_CHARGED_BIAS_OLD_DIRECT_VDD',AUX_V=1.,bias_V=6.,old_U208_VDD_V=1.,new_diode_OR_VDD_screen_min_V=5.,max_diode_drop_assumption_V=1.,status='OLD_LOW_VDD_INFERENCE_REJECTED; OR topology repairs supply loss under stated diode screen'),
        dict(name='REMOTE_WIRE_OPEN',result='THN defaults ON; sequence cannot be credited as independent STOP barrier'),
        dict(name='SHORT_BROWNOUT_WITH_RUN_RETAINED',result='UNKNOWN; U119 always enabled and U112 below4.5V not qualified; physical STOP recovery remains open')]
    checks=dict(active_native_R231_1k8=True,remote_high_within_3_to15=3<rem[0] and rem[1]<15,
        supervisor_sink_below5mA=low_sink<.005,remote_low_below1p2=.3<1.2,
        LDO_net_minimum_load_gt1mA=static['bleed_minus_remote_source_A']>.001,
        old_low_voltage_negative_margin_detected=any(v['headroom_A']<0 for v in old),
        qualified_voltage_positive_charge_margin=headroom>0,
        joint_96_power_residuals=all(not v['result']['equilibrium_found'] or max(abs(v['result'][k]) for k in ['power_balance_residual_W','heat_balance_residual_W'])<1e-7 for v in cases),
        warm_shortfall_retained=any(not w['specified_full_discharge_duration_screen_met'] for w in warm))
    dump('ELECTRICAL_CANDIDATE.json',e)
    files=[D/'wp10_system.xml',D/'wp10_aux_sequence.kicad_sch',R/'SELECTED_PARTS.json',R/'sources/tps3760_rev_a.pdf',A/'sources/lt3013.pdf',A/'sources/thn30wir_20260901.pdf',A/'tools/aux_operating_point_v35.py',A/'tools/shared_battery_path.py',A/'results/aux_v34/CALCULATIONS.json',A/'results/aux_v34/ELECTRICAL_CANDIDATE.json',Path(__file__).resolve()]
    files.append(R/'sources/ST_PUBLIC_SOURCE_RECORD.json')
    result=dict(revision='V35',source_bindings={str(p):sha(p) for p in files},static=static,checks=checks,scoped_checks_passed=all(checks.values()),
        paired_cases=cases,sequence_counts=dict(collections.Counter(x['result'].get('sequence_class','NO_ROOT') for x in cases)),
        main_counts=dict(collections.Counter(x['result']['protection_class'] for x in cases)),
        cold_and_warm_envelope_cases=starts,warm_counterexamples=warm,counterexamples=counterexamples,
        prior_open_remote_CPL=old,minimum_qualified_charge_headroom_A=headroom,hardware_startup_inrush_known=False,
        THN_internal_C_input_F=None,THN_input_startup_profile=None,efuse_thermal_fault_trip_time_bound_s=None,
        STOP_manual_rearm_brownout_verified=False,whole_design_complete=False,power_on_release=False,
        steady_model_scope='Downstream30mA allocation, original V34 branch R; board routing equality/upper-bound audit must bind this scenario; counterfactual ON roots do not determine actual switch states',
        joint_time_domain_simulation_completed=False)
    dump('CALCULATIONS.json',result);assert result['scoped_checks_passed'],checks
    print(json.dumps(dict(checks=checks,static=static,sequence_counts=result['sequence_counts'],conditional_charge_headroom_A=headroom)))
if __name__=='__main__':main()
