"""WP10 source-locked engineering adapter; UNKNOWN is never operating permission.

Imports existing solvers without invoking their main functions. All new outputs
belong to this folder. Legacy capture/actuator gates are untouched.
"""
from pathlib import Path
import csv, hashlib, importlib.util, json, math, sys
import numpy as np

HERE=Path(__file__).resolve().parent
A=HERE.parent
PROJECT=next(p for p in HERE.parents if (p/'AGENTS.md').exists())
WP09=A.parents[1]/'wp09_interfaces_20260907_1525'

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(name,obj):
    (HERE/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def load_candidate(path=HERE/'CANDIDATE.json'):
    c=read(path)
    drift=[p for p,h in c['source_lock'].items() if not Path(p).exists() or sha(p)!=h]
    if drift:raise ValueError('SOURCE_DRIFT: '+str(drift))
    return c

load_candidate()  # Refuse source drift before executing either imported consumer.
power=module('wp10_shared_battery_path',A/'tools/shared_battery_path.py')
prop=module('wp09_propulsion_screen',WP09/'functional_closure/tools/propulsion_screen.py')

def operating_point(c,pack_V,shared_R,eta=.85,hot_multiplier=2.,copper_C=100.,active=True):
    """Separate voltage planes and heat; no battery voltage/energy guarantee."""
    e=c['electrical'];r=dict(e['main_R_components_ohm'])
    vals=[pack_V,shared_R,eta,hot_multiplier,copper_C,e['eta_aux'],e['aux_R_ohm'],*r.values()]
    if not all(math.isfinite(v) for v in vals) or pack_V<=0 or shared_R<0 or hot_multiplier<=0 or not 0<eta<=1 or not 0<e['eta_aux']<=1 or min(r.values())<0 or e['aux_R_ohm']<0:
        raise ValueError('NONPHYSICAL_ELECTRICAL_INPUT')
    if 1+.00393*(copper_C-20)<=0:raise ValueError('COPPER_MODEL_OUT_OF_DOMAIN')
    r['Q201_25C']*=hot_multiplier
    r['copper_20C']*=1+.00393*(copper_C-20)
    main_R=sum(r.values())
    main_w=e['main_output_W']/eta+e['startup_input_W'] if active else 0.
    aux_w=e['aux_output_W']/e['eta_aux']
    result=power.solve(pack_V,shared_R,main_R,r['fuse_typical_20C'],e['aux_R_ohm'],
                       main_w,aux_w,controller_a=.003,main_leak_a=.003 if active else 0.)
    result.update(pack_V=pack_V,shared_R_ohm=shared_R,main_R_ohm=main_R,
                  main_R_breakdown_ohm=r,active=active,eta_main=eta,
                  hardware_feasibility='UNKNOWN_UNMEASURED_INPUTS_AND_MISSING_HEAT_PATHS')
    if not result['equilibrium_found']:return result
    im=result['main_A'];it=result['battery_A'];ia=result['aux_A']
    h=dict(Q201=im*im*r['Q201_25C'],shunts=im*im*r['shunts'],
      fuse=(im+.003)**2*r['fuse_typical_20C'],copper=im*im*r['copper_20C'],
      other_main=im*im*r['other_wiring_contacts_allocation'],
      shared_contact=it*it*shared_R,aux_branch=ia*ia*e['aux_R_ohm'],
      CHB=(e['main_output_W']*(1/eta-1)) if active else 0.,
      THN=e['aux_output_W']*(1/e['eta_aux']-1),
      input_startup=e['startup_input_W'] if active else 0.,
      input_controller=result['heat_W']['controller_allocation'],
      input_capacitor_leakage=result['heat_W']['input_capacitor_leakage'])
    # STOP output allocation is consumed locally, unlike motor mechanical work.
    h['STOP_output_allocation']=e['aux_output_W']
    h['brake_bias_output_allocation']=1. if active else 0.
    delivered_main=(e['main_output_W']-1.) if active else 0.
    residual=result['input_power_W']-delivered_main-sum(h.values())
    if abs(residual)>1e-7:raise ArithmeticError('Heat/electrical boundary mismatch')
    result.update(heat_breakdown_W=h,accounted_non_arm_heat_W=sum(h.values()),
       heat_balance_residual_W=residual,
       battery_current_margin_A=e['battery_current_limit_A']-it,
       main_converter_input_margin_V=result['main_input_V']-9.5,
       real_motor_terminal_power_W=None,
       output_distribution_loss_W=e['output_distribution_losses_W'],
       arm_heat_W=e['arm_local_heat_W'],
       scope='ALGEBRAIC_SENSITIVITY_NOT_DYNAMIC_STABILITY_OR_APPROVED_MISSION')
    screens=e['protection_screens'];vf=result['main_fused_V'];uv=screens['UVLO_falling_screen_V'];ov=screens['OVLO_rising_screen_V'];il=screens['current_limit_screen_A']
    state='AUX_ONLY_CHB_OFF'
    if active:
        state=('ASSUMED_ON_POINT_BLOCKED_BY_UVLO' if vf<uv[0] else
               'ASSUMED_ON_POINT_BLOCKED_BY_OVLO' if vf>ov[1] else
               'ASSUMED_ON_POINT_BLOCKED_BY_CURRENT_LIMIT' if im>il[1] else
               'PROTECTION_CORNER_DEPENDENT' if vf<uv[1] or vf>ov[0] or im>il[0] else
               'CONDITIONAL_HOLD_STARTUP_UNVERIFIED')
    result.update(protection_class=state,protection_screens_are_unqualified=True,
                  hypothetical_on_heat_not_actual_if_protection_trips=True)
    return result

def validate_array(a):
    required=['positions_m','directions','center_m','force_N','min_impulse_Ns',
              'min_on_s','min_off_s','max_simultaneous','idle_W','per_jet_W','power_limit_W']
    if any(a.get(k) is None for k in required):raise ValueError('INCOMPLETE_ACTUATOR_CONTRACT')
    for key in required:
        if not np.isfinite(np.asarray(a[key],float)).all():raise ValueError('NONFINITE_ACTUATOR_INPUT')
    if np.asarray(a['center_m']).shape!=(3,):raise ValueError('CENTER_SHAPE')
    if min(a['force_N'],a['min_impulse_Ns'],a['min_on_s'])<=0 or a['min_off_s']<0:
        raise ValueError('NONPOSITIVE_PULSE_INPUT')
    if a['max_simultaneous']<1 or a['max_simultaneous']!=int(a['max_simultaneous']):
        raise ValueError('INVALID_CONCURRENCY')
    if min(a['idle_W'],a['per_jet_W'],a['power_limit_W'])<0:raise ValueError('NEGATIVE_POWER')
    return prop.wrench_matrix(a['positions_m'],a['directions'],a['center_m'],'spacecraft_force')

def check_schedule(a,events,budget_Ns,duration_s,demand=None):
    """Check supplied piecewise-constant pulses, not infer them from the MIB.

    Fixed-frame impulse accounting only; finite attitude propagation remains a
    downstream task. A successful synthetic schedule never certifies C-POD.
    """
    B=validate_array(a);count=B.shape[1];used=np.zeros(count);byjet={j:[] for j in range(count)}
    if not math.isfinite(budget_Ns) or budget_Ns<0 or not math.isfinite(duration_s) or duration_s<=0:
        raise ValueError('INVALID_BUDGET')
    issues=[];boundaries={0.,duration_s}
    for event in events:
        j=event['jet'];t0=event['start_s'];t1=event['end_s']
        if not isinstance(j,int) or j not in byjet:raise ValueError('INVALID_JET')
        if not all(math.isfinite(x) for x in [t0,t1]) or not 0<=t0<t1<=duration_s:
            raise ValueError('INVALID_EVENT_TIME')
        dt=t1-t0;impulse=dt*a['force_N'];used[j]+=impulse
        if dt<a['min_on_s']-1e-12 or impulse<a['min_impulse_Ns']-1e-12:issues.append('SUBMINIMUM_PULSE')
        if j in a.get('plume_blocked_jets',[]):issues.append('PLUME_BLOCKED')
        byjet[j].append((t0,t1));boundaries.update([t0,t1])
    for items in byjet.values():
        items.sort()
        for prev,nxt in zip(items,items[1:]):
            if nxt[0]-prev[1]<a['min_off_s']-1e-12:issues.append('OVERLAP_OR_MIN_OFF')
    energy_J=0.;peak=0.;concurrency=0;times=sorted(boundaries)
    for left,right in zip(times,times[1:]):
        mid=(left+right)/2
        n=sum(t0<=mid<t1 for items in byjet.values() for t0,t1 in items)
        P=a['idle_W']+n*a['per_jet_W'];energy_J+=P*(right-left)
        peak=max(peak,P);concurrency=max(concurrency,n)
        if n>a['max_simultaneous']:issues.append('CONCURRENCY')
        if P>a['power_limit_W']+1e-12:issues.append('INSTANTANEOUS_POWER')
    if used.sum()>budget_Ns+1e-12:issues.append('IMPULSE_BUDGET')
    actual=B@used
    if demand is not None:
        demand=np.asarray(demand,float)
        if demand.shape!=(6,) or not np.isfinite(demand).all():raise ValueError('INVALID_DEMAND')
        if np.max(np.abs(actual-demand))>1e-9:issues.append('IMPULSE_RESIDUAL')
    return dict(status='VERIFIED_FIXED_FRAME_SCHEDULE' if not issues else 'REJECTED_SCHEDULE',
       issues=sorted(set(issues)),per_jet_impulse_Ns=used.tolist(),total_impulse_Ns=float(used.sum()),
       impulse_remaining_Ns=float(budget_Ns-used.sum()),wrench_impulse=actual.tolist(),
       energy_Wh=energy_J/3600,peak_W=peak,max_simultaneous=concurrency,
       attitude_propagation=False,flight_or_C_POD_credit=False)

def allocate_relaxed(a,demand,budget_Ns,duration_s):
    B=validate_array(a);d=np.asarray(demand,float)
    if d.shape!=(6,) or not np.isfinite(d).all():raise ValueError('INVALID_DEMAND')
    if not math.isfinite(budget_Ns) or not math.isfinite(duration_s) or budget_Ns<0 or duration_s<=0:raise ValueError('INVALID_BUDGET')
    if np.linalg.norm(d)==0:
        return dict(status='ZERO_DEMAND',total_impulse_used_Ns=0.,time_lower_bound_in_relaxed_model_s=0.)
    return prop.allocate(B,d,a['force_N'],budget_Ns,duration_s,a['idle_W'],a['per_jet_W'],
                         a['power_limit_W'],a['max_simultaneous'])

def candidate_propulsion(c):
    p=c['propulsion']
    required=['nozzle_positions_S_m','force_directions_S_unit','combined_COM_S_m',
              'minimum_command_width_s','allowed_concurrency','command_map','plume_exclusions']
    missing=[k for k in required if p[k] is None]
    return dict(status='UNKNOWN' if missing else 'REQUIRES_INSTALLED_WRENCH_VERIFICATION',
       missing=missing,allow=False,minimum_impulse_bit_Ns=p['minimum_impulse_bit_Ns'],
       min_equivalent_rectangular_duration_s=[p['minimum_impulse_bit_Ns']/f for f in reversed(p['per_nozzle_force_N_bounds'])],
       equivalent_duration_is_command_limit=False,installed_cpod=False)

def capture_state(bodies):
    """Call real existing capture solver only for explicit coherent rigid inputs."""
    if bodies is None:return dict(status='UNKNOWN_CURRENT_MULTIBODY_INPUTS_UNBOUND')
    load_candidate()  # Locks both the actual solver and rigid_body import before loading.
    for b in bodies:
        if not math.isfinite(b['m']) or b['m']<=0:raise ValueError('INVALID_MASS')
        I=np.asarray(b['I'],float)
        if I.shape!=(3,3) or not np.isfinite(I).all() or not np.allclose(I,I.T,atol=1e-12):
            raise ValueError('INVALID_INERTIA')
        eig=np.linalg.eigvalsh(I)
        if eig.min()<=0 or eig.max()>eig.sum()-eig.max()+1e-12:raise ValueError('NONPHYSICAL_INERTIA')
        for key in ['r','v','w']:
            v=np.asarray(b[key],float)
            if v.shape!=(3,) or not np.isfinite(v).all():raise ValueError('INVALID_STATE')
    common=PROJECT/'30_simulation/common'
    sys.path.insert(0,str(common))
    try:solver=module('wp10_capture_impulse_consumer',common/'capture_impulse.py')
    finally:sys.path.remove(str(common))
    r=solver.rigidize(bodies)
    return {k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in r.items() if k!='impulses'}

def phase_ledger(c,phases,initial_Wh):
    """Carry resources without reset; unknown transition/charging is not allowed."""
    energy=initial_Wh;rows=[]
    if not math.isfinite(energy) or energy<0:raise ValueError('INVALID_ENERGY')
    for phase in phases:
        mode=phase['mode'];dt=phase.get('duration_s')
        if mode not in ['RUN','SAFE_COOLDOWN','PRECHARGE','CONTROLLED_STOP','ISOLATED_REGEN','OFFLINE_CHARGE']:
            raise ValueError('UNKNOWN_PHASE')
        if dt is None or mode in ['PRECHARGE','CONTROLLED_STOP','ISOLATED_REGEN','OFFLINE_CHARGE']:
            return dict(status='UNKNOWN',allow=False,reason='UNBOUND_PHASE_DURATION_OR_TRANSIENT',
                        stopped_at=mode,energy_after_known_prefix_Wh=energy,rows=rows)
        if not math.isfinite(dt) or dt<=0:raise ValueError('INVALID_DURATION')
        sc=c['analysis_scenario']
        point=operating_point(c,phase['pack_V'],phase['shared_R'],sc['eta_main'],sc['hot_R_multiplier'],sc['copper_C'],active=mode=='RUN')
        if not point['equilibrium_found']:
            return dict(status='NO_ALGEBRAIC_EQUILIBRIUM',allow=False,rows=rows)
        if mode=='RUN' and point['protection_class']!='CONDITIONAL_HOLD_STARTUP_UNVERIFIED':
            return dict(status=point['protection_class'],allow=False,rows=rows,point=point)
        used=point['input_power_W']*dt/3600;energy-=used
        rows.append(dict(mode=mode,duration_s=dt,pack_V=phase['pack_V'],energy_used_Wh=used,
                         energy_remaining_Wh=energy,point=point))
        if energy<0:return dict(status='ENERGY_EXHAUSTED',allow=False,rows=rows)
    return dict(status='CONDITIONAL_KNOWN_PHASE_LEDGER',allow=False,energy_remaining_Wh=energy,rows=rows,
                reason='Operating voltage, energy fraction and phase lengths are unmeasured scenarios')

def run():
    c=load_candidate();rows=[]
    for V in c['electrical']['pack_V_scenarios']:
        for R in c['electrical']['shared_R_scenarios_ohm']:
            for eta in c['electrical']['eta_main_scenarios']:
                for mult,T in [(1.,20.),(2.,100.)]:
                    rows.append(operating_point(c,V,R,eta,mult,T))
    sc=c['analysis_scenario'];initial=c['electrical']['nominal_energy_Wh']*sc['initial_energy_fraction']
    phases=[dict(**p,pack_V=sc['pack_V'],shared_R=sc['shared_R_ohm']) for p in sc['phases']]
    ledger=phase_ledger(c,phases,initial)
    missing=phase_ledger(c,[dict(mode='PRECHARGE',duration_s=None)],initial)
    out=dict(candidate_sha256=sha(HERE/'CANDIDATE.json'),adapter_sha256=sha(__file__),
        source_checks_passed=True,operating_points=rows,
        declared_600s_two_cycle_sensitivity=ledger,real_mission=missing,
        propulsion=candidate_propulsion(c),capture=capture_state(None),
        consumers=[str(A/'tools/shared_battery_path.py')+'::solve',
                   str(WP09/'functional_closure/tools/propulsion_screen.py')+'::wrench_matrix/allocate',
                   str(PROJECT/'30_simulation/common/capture_impulse.py')+'::rigidize'],
        consumer_scope=dict(candidate_executed=['shared_battery_path.solve'],
            synthetic_tests_executed=['propulsion_screen.wrench_matrix','propulsion_screen.allocate','capture_impulse.rigidize'],
            current_capture_and_thrusters='UNKNOWN; actual873 mass packet cannot stand in for974 articulated input'),
        whole_candidate_validated=False)
    dump('COUPLED_RESULTS.json',out)
    print(json.dumps(dict(cases=len(rows),propulsion=out['propulsion']['status'],
                         mission=missing['status'],energy_after_two_cycles_Wh=ledger.get('energy_remaining_Wh'))))

if __name__=='__main__':run()
