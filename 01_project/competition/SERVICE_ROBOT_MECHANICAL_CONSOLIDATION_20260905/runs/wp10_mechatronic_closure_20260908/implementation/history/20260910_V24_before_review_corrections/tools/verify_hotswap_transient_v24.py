"""Source-bound reduced transient screening; never exports/regenerates KiCad."""
from pathlib import Path
from dataclasses import asdict
from collections import Counter
import csv, hashlib, itertools, json, math, re, time, xml.etree.ElementTree as ET
import psutil
from hotswap_transient_model_v23 import Circuit, timer_pulse_train
from timer_passive_definition_v24 import TIMING_PASSIVES as T

A=Path(__file__).resolve().parents[1]
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def dump(p,v):(A/p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    started=time.perf_counter();memory=psutil.virtual_memory().available/2**20
    assert memory>=2048,'Use authorized memory cleanup before this engineering job'
    paths=['tools/hotswap_transient_model_v23.py','tools/verify_hotswap_transient_v24.py',
        'tools/shared_battery_path.py','power/SHARED_BATTERY_PATH_DEFINITION.json',
        'power/POWER_LOOP_CALCULATIONS.json','tools/integrate_power_loop.py',
        'power/POWER_LOOP_PARTS.json','power/INPUT_PASSIVE_SELECTION.json',
        'ecad/wp10_system.xml','ecad/POWER_LOOP_PIN_NET.csv','sources/lm5069_rev_g.pdf',
        'results/TIMER_PASSIVES_NATIVE_V24.json','power/TIMER_PASSIVE_SELECTION_V24.json','power/TIMER_PASSIVE_CALCULATIONS_V24.json','tools/timer_passive_definition_v24.py','SYSTEM_CLOSURE_MATRIX.csv',
        'mechanical/CAP_HARNESS_RETAINED_PLAN_V21.json']
    hashes={p:sha(p) for p in paths}
    p=read('power/POWER_LOOP_CALCULATIONS.json');s=read('power/SHARED_BATTERY_PATH_DEFINITION.json')
    parts=read('power/POWER_LOOP_PARTS.json');checks=[]
    def ck(name,passed,**kw):checks.append(dict(name=name,passed=bool(passed),**kw))
    x=ET.parse(A/'ecad/wp10_system.xml').getroot()
    nc={q.get('ref'):q.findtext('value') for q in x.findall('./components/comp')}
    nets={(q.get('ref'),q.get('pin')):n.get('name') for n in x.findall('./nets/net') for q in n.findall('node')}
    for ref in ['U201','Q201','R201','R202','R207','C201','C203','U202','U203']:
        ck('selected_native_'+ref,nc[ref]==parts[ref]['mpn'])
    ck('latched_part_not_auto_retry',nc['U201']=='LM5069MM-1')
    ck('selected_C201_native_MPN',nc['C201']==T['C201']['MPN'])
    for name,endpoints in {'timer':['U201.6','C201.1'],
        'fused':['F201.2','U201.2','R201.1'],
        'drain':['R202.2','U201.1','Q201.2'],
        'out':['Q201.3','U201.9','C203.1','U203.1'],
        'independent_aux':['F202.2','U202.1']}.items():
        ck('native_topology_'+name,len({nets[tuple(e.split('.'))] for e in endpoints})==1)
    ck('no_reduction_in_arm_allocation',s['load_binding']['arm_task_W_unchanged']==p['arm_output_W']==360)
    ck('main_brake_and_aux_allocations_preserved',s['load_binding']['main_output_W']==361 and s['load_binding']['aux_output_W']==16.8)
    cs=s['cases'];load=s['load_binding'];cap=read('power/INPUT_PASSIVE_SELECTION.json')['C203']
    cmax=cap['C_nominal_F']*(1+cap['tolerance_fraction'])
    ck('C203_initial_cap_and_leak_bound_to_selection',abs(cmax-p['precharge']['Cmax_F'])<1e-15
        and cs['main_leak_A']==cap['max_leakage_A'] and nc['C203']==cap['MPN'])
    ck('approved_sense_pair_and_nominal_value',nc['R201']=='WSLP27262L000FEA'
        and nc['R202']=='WSLP2726L2000FEA' and p['Rs_nominal_ohm']==.0022)
    ck('Q201_25C_Rds_allocation_part',nc['Q201']=='IXTH75N10L2')
    rp_nom=T['R207']['resistance_ohm']
    rp_tol=T['R207']['initial_tolerance_fraction']+T['R207']['TCR_per_K']*100
    ck('R207_selected_native_code_and_bounds',nc['R207']==T['R207']['MPN'] and rp_nom==30100 and abs(rp_tol-.0035)<1e-12)
    profiles=[]
    for key,rs,rp,scale,vcl in [('LOW',max(p['Rs_including_TCR_and_Kelvin_allocation_ohm']),rp_nom*(1-rp_tol),.76,.0485),
        ('HIGH',min(p['Rs_including_TCR_and_Kelvin_allocation_ohm']),rp_nom*(1+rp_tol),1.24,.0615)]:
        profiles.append(dict(name=key,rs=rs,rpwr=rp,power_scale=scale,vcl=vcl))
    definition=dict(schema='WP10_HOTSWAP_REDUCED_TRANSIENT_V24',source_bindings=hashes,
        active_electrical_native_revision='V24',active_mechanical_revision='V21_UNCHANGED',
        C201_selected_nominal_F=1e-6,C201_effective_tolerance_requirement=.1,C201_initial_tolerance=.05,C201_MPN_bound=True,C201_environment_verified=False,
        regulated_profiles=profiles,main_arm_allocation_W=360,main_output_including_brake_W=361,
        base_source_cases=cs,voltage_step_V=.025,normal_model_end='First exit from current/power regulation',
        precharge_load='CHB externally held OFF for this screen. C203 3mA leakage plus primary bias 0.25A below1V /0.25W above1V, assumptions only.',
        resistor_accounting='Original main total split into pre-sense R, effective shunts Rs including Kelvin error allocation, controlled block R_on=total-pre-Rs. The block includes Q201 plus unallocated wire/PCB R; this is a declared lumped electrical model, not an extracted Q201 thermal model.',
        effective_capacitance_scope='C203 initial20C120Hz nominal+tolerance. Aging, low-temperature C/ESR and broadband ESR not modeled.',
        bias_low_voltage_model_guaranteed=False,CHB_enable_delay_proved=False,
        gate_charge_and_limited_loop_bandwidth_included=False,source_inductance_or_BMS_dynamics_included=False,
        UVLO_interruption='Stop and classify first UVLO interruption; recovery/chatter not modeled and not credited.',
        short_prefix_coverage='Only source cases meeting the cold-start rising UV threshold; warm-only UV hysteresis hold cases are not included in the short-prefix set.',
        parameter_scope='Two explicitly correlated endpoint profiles and two UVLO endpoint pairs, not an exhaustive independent-corner or full-temperature proof. LM min/max transferred from48V table; Eq9 application model.',
        source_evidence=[dict(url='https://www.ti.com/lit/ds/symlink/lm5069.pdf',revision='G',pages=[5,6,12,13,14,15,17,20,21],local='sources/lm5069_rev_g.pdf'),
          dict(url='https://www.littelfuse.com/assetdocs/littelfuse-discrete-mosfets-ixt-75n10-datasheet?assetguid=ea051e16-aaa9-4983-a975-8d0c07325d72',revision='DS100200(9/09) ADVANCE',pages=[1,2,5],local_download='HTTP403',SOA_digitized=False)],
        hardware_protection_qualified=False,SOA_verified=False)
    dump('power/HOTSWAP_TRANSIENT_DEFINITION_V24.json',definition)
    rows=[];faults=[];circuits={}
    product=itertools.product(cs['pack_V'],cs['shared_contact_loop_R_ohm'],cs['main_branch_allocations_ohm'],
        cs['aux_branch_R_ohm'],cs['aux_efficiency'],profiles,[0,1])
    for idx,(vp,rsrc,rmain,raux,eta,pr,uvidx) in enumerate(product):
        c=Circuit(vp,rsrc,rmain['before_MAIN_FUSED'],rmain['total'],raux,load['aux_output_W']/eta,
            pr['rs'],pr['rpwr'],pr['power_scale'],pr['vcl'],
            p['UVLO_rising_screen_V'][uvidx],p['UVLO_falling_screen_V'][uvidx],cmax,
            controller_a=cs['controller_input_A'],cap_leak_a=cs['main_leak_A'],
            bias_w=load['startup_bias_input_W'])
        cid=f'HS{idx:03d}';circuits[cid]=c;r=c.precharge();r.pop('trace')
        rows.append(dict(id=cid,profile=pr['name'],uv_corner=uvidx,inputs=asdict(c),**r))
        if c.source(0)[2]>=c.uv_rise:
            f=c.regulated(0)
            valid=f['fused_v']>=c.uv_fall and f['mode']!='ON'
            tmax=1e-6*1.1*4.16/51e-6
            faults.append(dict(case_id=cid,regulated_prefix_only=True,UVLO_continuous_regulation=valid,
                fault_block_V=f['block_drop_v'],fault_current_A=f['main_a'],fault_block_W=f['block_w'],
                max_timer_from_zero_s=tmax,
                block_energy_to_timer_threshold_J=f['block_w']*tmax if valid else None,
                eventual_gate_off_delay_max_s=None,start_into_short_whole_pass=False,
                hot_short_front_edge_peak_A=None,hot_short_whole_pass=False,
                C203_max_initial_energy_J=.5*cmax*vp*vp,
                C203_local_discharge_limited_by_F201=False))
    counts=dict(Counter(r['outcome'] for r in rows));successful=[r for r in rows if r['outcome']=='REGULATION_EXIT_REDUCED_MODEL']
    ck('384_declared_cases_evaluated',len(rows)==384)
    ck('source_low_voltage_cases_not_misreported_complete',any(r['outcome']=='COLD_UVLO_OFF' for r in rows))
    worst=max(successful,key=lambda r:r['active_limit_s']);c=circuits[worst['id']]
    fine=c.precharge(.00625,True);trace=fine.pop('trace')
    relative=abs(fine['active_limit_s']-worst['active_limit_s'])/fine['active_limit_s']
    ck('worst_case_voltage_quadrature_refinement',relative<.005,relative_difference=relative)
    ck('power_balance_closes_all_completed_prefixes',max(r['maximum_instantaneous_power_balance_residual_w'] for r in successful)<1e-7)
    ck('fuse_current_counts_controller_once',all(r['F201_I2t_a2s']>r['pass_path_I2t_a2s'] for r in successful))
    # Independent exact integral of variable P at ideal source; not another full model.
    pr=profiles[0];aa=pr['power_scale']*pr['rpwr']/(1.30e5*pr['rs']);bb=pr['power_scale']*.00118/pr['rs'];il=pr['vcl']/pr['rs'];vp=29.4
    transition=aa/(il-bb)
    exact=cmax/bb**2*(bb*(vp-transition)-aa*math.log((aa+bb*vp)/(aa+bb*transition)))+cmax*transition/il
    step=vp/20000
    quad=sum(cmax*step/min(il,aa/(vp-(j+.5)*step)+bb) for j in range(20000))
    fixed=aa+bb*vp;oldfixed=cmax/2*(vp*vp/fixed+fixed/il**2)
    ck('independent_variable_power_integral',abs(exact-quad)<1e-9)
    ck('reject_max_voltage_fixed_power_as_startup_upper_bound',exact>oldfixed,variable_s=exact,fixed_s=oldfixed)
    train=timer_pulse_train(1e-6,4,85e-6,2.5e-6,[(.02,True),(.01,False)]*3)
    reset_bug=timer_pulse_train(1e-6,4,85e-6,2.5e-6,[(.02,True)])
    ck('repeated_fault_timer_memory_counterexample',train['latched'] and not reset_bug['latched'])
    analytical_latch=.06+(4-(2*.02*85e-6-2*.01*2.5e-6)/1e-6)/(85e-6/1e-6)
    ck('timer_train_independent_charge_ledger',abs(train['latch_s']-analytical_latch)<1e-12)
    warm=timer_pulse_train(1e-6*.9,3.76,120e-6,1.25e-6,[(.2,True)],start_v=3.)
    ck('warm_fault_cannot_inherit_empty_timer_duration',warm['latch_s']<p['precharge']['fault_timer_spec_corner_s'][0])
    candidates=[]
    for cv in [.68e-6,.82e-6,1e-6]:
        tfmin=cv*.9*3.76/120e-6;tfmax=cv*1.1*4.16/51e-6
        candidates.append(dict(nominal_F=cv,effective_tolerance_requirement=.1,
            timer_threshold_from_zero_s=[tfmin,tfmax],insertion_from_zero_s=[cv*.9*3.76/8e-6,cv*1.1*4.16/3e-6],
            sampled_active_time_s=fine['active_limit_s'],project_1p5_allowance_not_guarantee_s=fine['active_limit_s']*1.5,
            remaining_after_project_allowance_s=tfmin-fine['active_limit_s']*1.5,
            present_in_native_candidate=cv==1e-6,physically_installed=False,
            chosen_new_part=cv==1e-6,SOA_verified=False,C_effective_and_leakage_verified=False))
    ck('do_not_select_680n_by_obsolete_fixed_power_test',candidates[0]['remaining_after_project_allowance_s']<0)
    ck('source_inputs_unchanged_through_job',hashes=={q:sha(q) for q in hashes})
    result=dict(schema='WP10_HOTSWAP_TRANSIENT_SCREEN_V24',source_bindings=hashes,
        definition_sha256=sha('power/HOTSWAP_TRANSIENT_DEFINITION_V24.json'),checks=checks,
        passed=all(r['passed'] for r in checks),case_count=len(rows),outcomes=counts,
        worst_sampled_completed_prefix={k:v for k,v in worst.items() if k!='inputs'},
        refined_worst_prefix=fine,refinement_relative_time=relative,
        ideal_variable_power_integral=dict(exact_s=exact,quadrature_s=quad,old_constant_at_max_V_s=oldfixed),
        repeated_fault_counterexample=train,warm_timer_counterexample=warm,timer_candidates=candidates,
        cases=rows,short_regulated_prefixes=faults,
        selection_decision='Select WIMA1uF5pct initial; use retained0.9..1.1uF effective-C requirement only as conditional screen. R207 selected0.1pct25ppm with100K allocation. Full temperature/leakage/gate dynamics and SOA open.',
        runtime_s=time.perf_counter()-started,available_MiB_at_start=memory,
        available_MiB_at_end=psutil.virtual_memory().available/2**20,process_RSS_MiB=psutil.Process().memory_info().rss/2**20,
        native_export_separate_from_this_scalar_job=True,native_revision='V24',whole_design_complete=False,
        SOA_full_trajectory_verified=False,physical_tests_executed=False,power_on_release=False)
    with (A/'power/HOTSWAP_WORST_PREFIX_TRACE_V24.csv').open('w',newline='',encoding='utf-8-sig') as g:
        w=csv.DictWriter(g,fieldnames=list(trace[0]));w.writeheader();w.writerows(trace)
    with (A/'thermal/HOTSWAP_SHORT_BLOCK_LOADS_V24.csv').open('w',newline='',encoding='utf-8-sig') as g:
        heats=[dict(case_id=f['case_id'],block_W=f['fault_block_W'],timer_threshold_s=f['max_timer_from_zero_s'],
            conditional_energy_J=f['block_energy_to_timer_threshold_J'],
            scope='Q201+unallocated wire block; controlled plateau only; physical thermal boundary UNBOUND')
            for f in faults if f['UVLO_continuous_regulation']]
        w=csv.DictWriter(g,fieldnames=list(heats[0]));w.writeheader();w.writerows(heats)
    dump('power/HOTSWAP_TRANSIENT_CALCULATIONS_V24.json',result)
    print(json.dumps({k:result[k] for k in ['passed','case_count','outcomes','worst_sampled_completed_prefix','runtime_s','process_RSS_MiB']},ensure_ascii=False))
    assert result['passed'],[q for q in checks if not q['passed']]

if __name__=='__main__':main()
