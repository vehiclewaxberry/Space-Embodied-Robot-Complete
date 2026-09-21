"""Adversarial consumer tests. Synthetic fixtures are never candidate hardware."""
import copy,csv,json,math,tempfile
import numpy as np
import pytest
import xml.etree.ElementTree as ET
import coupled_adapter as m

def array():
    # Pure -Z couple: forces cancel at +/-X. Numerical fixture, not C-POD.
    return dict(positions_m=[[.1,0,0],[-.1,0,0]],directions=[[0,-1,0],[0,1,0]],
       center_m=[0,0,0],force_N=.01,min_impulse_Ns=.0005,min_on_s=.05,min_off_s=.01,
       max_simultaneous=2,idle_W=.25,per_jet_W=2.,power_limit_W=5.,plume_blocked_jets=[])

def events():return [dict(jet=j,start_s=0.,end_s=1.) for j in [0,1]]

def test_current_sources_and_bom():
    c=m.load_candidate()
    with (m.HERE/'ACTIVE_ELECTRICAL_BOM.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
    b={r['ref']:r['value_or_MPN'] for r in rows}
    assert len(b)==207 and b['U303']=='MAX5048CAUT+T' and b['U304']=='MAX16053AUT+T'
    actual={x.get('ref'):x.findtext('value') for x in ET.parse(m.A/'ecad/wp10_system.xml').getroot().findall('./components/comp')}
    assert b==actual
    assert c['mechanical']['new_main_module_installed'] is False

def test_source_drift_refused():
    with tempfile.TemporaryDirectory(prefix='source_drift_',dir=m.HERE) as tmp:
        p=m.Path(tmp)/'dependency';p.write_text('before');c=m.load_candidate();c['source_lock']={str(p):m.sha(p)}
        cfg=m.Path(tmp)/'cfg.json';cfg.write_text(json.dumps(c));p.write_text('after')
        with pytest.raises(ValueError,match='SOURCE_DRIFT'):m.load_candidate(cfg)

def test_shared_contact_physical_effect_and_balance():
    c=m.load_candidate();good=m.operating_point(c,25.2,.01);bad=m.operating_point(c,25.2,.1)
    assert bad['main_input_V']<good['main_input_V']
    assert bad['heat_breakdown_W']['shared_contact']>good['heat_breakdown_W']['shared_contact']
    assert abs(bad['heat_balance_residual_W'])<1e-7
    assert abs(bad['input_power_W']-360-sum(bad['heat_breakdown_W'].values()))<1e-7

def test_phase_energy_carries_without_reset():
    c=m.load_candidate();p=dict(mode='RUN',duration_s=60.,pack_V=25.2,shared_R=.01)
    once=m.phase_ledger(c,[p],100);twice=m.phase_ledger(c,[p,p],100)
    assert math.isclose(100-twice['energy_remaining_Wh'],2*(100-once['energy_remaining_Wh']),abs_tol=1e-10)
    exhausted=m.phase_ledger(c,[p],1.)
    assert exhausted['status']=='ENERGY_EXHAUSTED' and exhausted['allow'] is False

@pytest.mark.parametrize('mode',['PRECHARGE','CONTROLLED_STOP','ISOLATED_REGEN','OFFLINE_CHARGE'])
def test_unmeasured_transitions_never_allow(mode):
    assert m.phase_ledger(m.load_candidate(),[dict(mode=mode,duration_s=10)],100)['status']=='UNKNOWN'

def test_current_nozzle_unknown_never_synthetic_default():
    r=m.candidate_propulsion(m.load_candidate())
    assert r['status']=='UNKNOWN' and not r['allow'] and not r['equivalent_duration_is_command_limit']

def test_actual_wrench_consumer_sign_frame_com():
    a=array();B=m.validate_array(a)
    np.testing.assert_allclose(B@np.array([.01,.01]),[0,0,0,0,0,-.002],atol=1e-15)
    a['center_m']=[.05,.03,0.];B2=m.validate_array(a)
    np.testing.assert_allclose(B2@np.array([.01,.01]),[0,0,0,0,0,-.002],atol=1e-15)
    assert not np.allclose(B[:,0],B2[:,0])

def test_relaxed_allocator_consumes_force():
    a=array();d=[0,0,0,0,0,-.002]
    one=m.allocate_relaxed(a,d,1.,10);a['force_N']*=.5;two=m.allocate_relaxed(a,d,1.,10)
    assert math.isclose(two['time_lower_bound_in_relaxed_model_s'],2*one['time_lower_bound_in_relaxed_model_s'])
    assert m.allocate_relaxed(a,[0]*6,1.,10)['status']=='ZERO_DEMAND'

def test_rank_not_enough_nonnegative_rejection():
    a=array();r=m.allocate_relaxed(a,[0,0,0,0,0,.002],1.,10)
    assert not r['feasible']

def test_fixed_frame_impulse_and_independent_rocket_mass():
    r=m.check_schedule(array(),events(),1.,2.,[0,0,0,0,0,-.002])
    assert r['status']=='VERIFIED_FIXED_FRAME_SCHEDULE'
    assert math.isclose(r['total_impulse_Ns'],.02)
    assert math.isclose(r['energy_Wh'],(4.*1.+.25*2.)/3600.)
    # Equal/opposite 0.01Ns impulses 0.2m apart yield 0.002Nms.
    assert math.isclose(abs(r['wrench_impulse'][5]),.01*.2)

@pytest.mark.parametrize('change,expected',[
    ('short','SUBMINIMUM_PULSE'),('concurrency','CONCURRENCY'),('power','INSTANTANEOUS_POWER'),
    ('plume','PLUME_BLOCKED'),('budget','IMPULSE_BUDGET'),('overlap','OVERLAP_OR_MIN_OFF')])
def test_bad_schedules_rejected(change,expected):
    a=array();ev=events();budget=1.
    if change=='short':ev[0]['end_s']=.01
    if change=='concurrency':a['max_simultaneous']=1
    if change=='power':a['power_limit_W']=3.
    if change=='plume':a['plume_blocked_jets']=[0]
    if change=='budget':budget=.001
    if change=='overlap':ev.append(dict(jet=0,start_s=.2,end_s=.5))
    r=m.check_schedule(a,ev,budget,2.)
    assert expected in r['issues'] and r['status']=='REJECTED_SCHEDULE'

@pytest.mark.parametrize('key,value',[('center_m',[float('nan'),0,0]),('center_m',[0,0]),('directions',[[0,-2,0],[0,1,0]])])
def test_invalid_geometry(key,value):
    a=array();a[key]=value
    with pytest.raises(ValueError):m.validate_array(a)

def test_actual_capture_consumer_perturbation_and_conservation():
    b=[dict(m=2.,I=np.diag([.1,.1,.1]).tolist(),r=[-.1,0,0],v=[0,0,0],w=[0,0,0]),
       dict(m=1.,I=np.diag([.02,.02,.02]).tolist(),r=[.2,0,0],v=[0,0,0],w=[0,0,.1])]
    r=m.capture_state(b);assert all(r['validity'].values())
    np.testing.assert_allclose(r['H_com'],[0,0,.002],atol=1e-15)
    assert math.isclose(r['w_plus'][2],.002/.18,rel_tol=1e-12)
    b[1]['I']=np.diag([.04,.04,.04]).tolist();changed=m.capture_state(b)
    assert changed['w_plus'][2]>r['w_plus'][2]
    assert m.capture_state(None)['status'].startswith('UNKNOWN')

def test_thermal_negative_result_and_numerics():
    r=m.read(m.HERE/'THERMAL_RESULTS.json')
    assert r['candidate_sha256']==m.sha(m.HERE/'CANDIDATE.json')
    assert r['adapter_sha256']==m.sha(m.HERE/'coupled_adapter.py')
    assert r['script_sha256']==m.sha(m.HERE/'thermal_closure.py')
    assert r['energy_balance_max_W']<1e-6 and max(r['mesh_delta_C'].values())<1.
    assert abs(r['reference_replay_difference_C'])<1e-7
    case=next(x for x in r['spatial_cases'] if x['case']=='CHB_PLUS_NEW_BOARD_PROPOSED_PATH' and x['pitch_mm']==5)
    assert case['CHB_case_C']>105 and r['continuous_thermal_closure'] is False
    assert max(abs(x['heat_balance_residual_J']) for x in r['transient_screens'])<1e-5
    assert all(x['heater_output_Wh']>0 for x in r['transient_screens'] if x['cold'])

@pytest.mark.parametrize('kwargs',[dict(eta=1.1),dict(eta=float('nan')),dict(hot_multiplier=-.1),dict(pack_V=float('inf')),dict(shared_R=-.01)])
def test_electrical_invalid_parameters(kwargs):
    args=dict(pack_V=25.2,shared_R=.01);args.update(kwargs)
    with pytest.raises(ValueError):m.operating_point(m.load_candidate(),**args)

@pytest.mark.parametrize('budget,duration',[(float('nan'),2.),(1.,float('nan')),(float('inf'),2.),(1.,float('inf'))])
def test_zero_demand_cannot_bypass_invalid_resources(budget,duration):
    with pytest.raises(ValueError):m.allocate_relaxed(array(),[0]*6,budget,duration)

def test_selected_uvlo_controls_phase_admission():
    c=m.load_candidate()
    assert m.operating_point(c,20.,.01)['protection_class']=='ASSUMED_ON_POINT_BLOCKED_BY_UVLO'
    assert m.operating_point(c,25.2,.1)['protection_class']=='PROTECTION_CORNER_DEPENDENT'
    p=dict(mode='RUN',duration_s=60,pack_V=20.,shared_R=.01)
    assert m.phase_ledger(c,[p],100)['status']=='ASSUMED_ON_POINT_BLOCKED_BY_UVLO'

def test_common_parameters_reach_both_consumers():
    import thermal_closure
    c=m.load_candidate();original=m.read(m.HERE/'THERMAL_RESULTS.json')
    changed=copy.deepcopy(c)
    changed['analysis_scenario']['initial_energy_fraction']=.5
    changed['analysis_scenario']['phases'][0]['duration_s']=300
    changed['thermal']['CHB_case_limit_C']+=5
    changed['thermal']['Q201_Rjc_K_W']+=.1
    changed['thermal']['cold_safe_heater_limit_W']=0
    alt=thermal_closure.run(changed,output_name=None)
    p0=original['spatial_cases'][1];p1=alt['spatial_cases'][1]
    assert math.isclose(p1['CHB_margin_C']-p0['CHB_margin_C'],5,abs_tol=1e-10)
    assert math.isclose(p1['Q201_required_total_case_to_radiator_R_K_W']-p0['Q201_required_total_case_to_radiator_R_K_W'],-.1,abs_tol=1e-10)
    assert all(x['heater_output_Wh']==0 for x in alt['transient_screens'] if x['cold'])
    sc=changed['analysis_scenario'];phases=[dict(**p,pack_V=sc['pack_V'],shared_R=sc['shared_R_ohm']) for p in sc['phases']]
    ledger=m.phase_ledger(changed,phases,changed['electrical']['nominal_energy_Wh']*sc['initial_energy_fraction'])
    assert math.isclose(alt['transient_screens'][1]['trace'][-1]['energy_Wh'],ledger['energy_remaining_Wh'],abs_tol=1e-7)
