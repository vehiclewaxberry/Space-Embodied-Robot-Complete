"""Independent checks of saved output identities, plus injected stale-field controls."""
from pathlib import Path
import json,copy,hashlib,collections,math
A=Path(__file__).resolve().parents[1];R=A/'results/aux_v34'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def errors(z,e):
    if not z['equilibrium_found']:return ['No equilibrium']
    im,ia,ib=z['main_A'],z['aux_A'],z['battery_A'];v=z['junction_V'];ic=.003;leak=.003;iq=e['aux_protection_model']['quiescent_current_A']
    rm=z['main_R_ohm'];ra=z['aux_R_ohm'];pre=z['main_R_breakdown_ohm']['fuse_typical_20C'];apre=z['aux_before_IQ_R_ohm']
    if ra-apre<e['aux_protection_model']['on_resistance_ohm']-1e-12:return ['Negative allocated after-IQ non-eFuse resistance']
    identities={'battery_KCL':ib-im-ia-ic-iq,'shared_KVL':z['pack_V']-v-z['shared_R_ohm']*ib,
      'main_pre_KVL':v-z['main_fused_V']-pre*(im+ic),
      'main_post_KVL':z['main_fused_V']-z['main_input_V']-(rm-pre)*im,
      'aux_pre_KVL':v-z['efuse_input_V']-apre*(ia+iq),
      'aux_post_KVL':z['efuse_input_V']-z['aux_input_V']-(ra-apre)*ia,
      'main_CPL':z['main_input_V']*(im-leak)-e['main_output_W']/z['eta_main']-e['startup_input_W'],
      'aux_CPL':z['aux_input_V']*ia-e['aux_output_W']/e['eta_aux'],
      'saved_input_power':z['input_power_W']-z['pack_V']*ib,
      'saved_heat_sum':z['accounted_non_arm_heat_W']-sum(z['heat_breakdown_W'].values()),
      'whole_heat':z['input_power_W']-360-sum(z['heat_breakdown_W'].values()),
      'heat_residual_field':z['heat_balance_residual_W']-(z['input_power_W']-360-sum(z['heat_breakdown_W'].values())),
      'power_residual_field':z['power_balance_residual_W']-(z['input_power_W']-e['main_output_W']/z['eta_main']-e['startup_input_W']-e['aux_output_W']/e['eta_aux']-sum(z['heat_W'].values())),
      'battery_margin':z['battery_current_margin_A']-(e['battery_current_limit_A']-ib),
      'converter_margin':z['main_converter_input_margin_V']-(z['main_input_V']-9.5)}
    r=z['main_R_breakdown_ohm'];expected_heat={
      'Q201':im*im*r['Q201_25C'],'shunts':im*im*r['shunts'],
      'fuse':(im+ic)**2*pre,'copper':im*im*r['copper_20C'],
      'other_main':im*im*r['other_wiring_contacts_allocation'],
      'shared_contact':ib*ib*z['shared_R_ohm'],
      'aux_branch':apre*(ia+iq)**2+(ra-apre-.25)*ia*ia,
      'efuse_conduction':ia*ia*.25,'efuse_quiescent':z['efuse_input_V']*iq,
      'CHB':e['main_output_W']*(1/z['eta_main']-1),'THN':e['aux_output_W']*(1/e['eta_aux']-1),
      'input_startup':e['startup_input_W'],'input_controller':z['main_fused_V']*ic,
      'input_capacitor_leakage':z['main_input_V']*leak,'STOP_output_allocation':e['aux_output_W'],
      'brake_bias_output_allocation':1.}
    identities.update({'heat_component_'+n:z['heat_breakdown_W'][n]-v for n,v in expected_heat.items()})
    return [dict(identity=n,residual=x if math.isfinite(x) else 'NONFINITE') for n,x in identities.items() if not math.isfinite(x) or abs(x)>1e-7]
def main():
    c=read(R/'CALCULATIONS.json');e=read(R/'ELECTRICAL_CANDIDATE.json')
    rows=[q['V34'] for q in c['paired_cases']]+[q['output'] for q in c['contact_resistance_sensitivity']]
    bad=[dict(case=i,errors=er) for i,z in enumerate(rows) if (er:=errors(z,e))]
    injected=[]
    for field in ['input_power_W','main_input_V','junction_V','accounted_non_arm_heat_W','battery_current_margin_A']:
        z=copy.deepcopy(rows[-1]);z[field]-=.01;err=errors(z,e)
        injected.append(dict(field=field,injected_delta=-.01,detected=bool(err),detections=err))
    z=copy.deepcopy(rows[-1]);z['input_power_W']=float('nan');err=errors(z,e)
    injected.append(dict(field='input_power_W',injected_delta='NaN',detected=bool(err),detections=err))
    z=copy.deepcopy(rows[-1]);z['heat_breakdown_W']['CHB']-=.01;z['heat_breakdown_W']['efuse_conduction']+=.01;err=errors(z,e)
    injected.append(dict(field='heat_misattribution_same_sum',injected_delta=.01,detected=bool(err),detections=err))
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    mismatch=[p for p,h in c['source_bindings'].items() if sha(p)!=h]
    native=read(R/'NATIVE_AUDIT.json');mismatch.extend(p for p,h in native['source_sha256'].items() if sha(p)!=h)
    injected_board=read(R/'counterexamples/INJECTION.json');bad_drc=read(R/'counterexamples/SHORT_DRC.json')
    short_detected=any('WP10_INPUT_RETURN' in json.dumps(v) and 'WP10_AUX_PROTECT_RTN' in json.dumps(v) for v in bad_drc['violations'])
    active_preserved=sha(A/'ecad/revisions/v34/wp10_aux_protection.kicad_pcb')==injected_board['active_board_sha256']
    erc=read(R/'SYSTEM_ERC.json');viol=[v for s in erc['sheets'] for v in s['violations']]
    drcs={n:read(R/n) for n in ['MAIN_DRC.json','AUX_DRC.json']}
    report=dict(revision='V34',saved_operating_points=len(rows),saved_identity_failures=bad,
      injected_stale_field_controls=injected,source_hash_mismatches=mismatch,
      native_aux_pin_net_mismatches=native['pad_net_mismatch'],native_ERC_violations=len(viol),
      ERC_ignored_checks=erc.get('ignored_checks',[]),
      native_DRC={n:dict(violations=len(d['violations']),unconnected=len(d['unconnected_items']),ignored_checks=d.get('ignored_checks',[])) for n,d in drcs.items()},
      prior_parent_files_unchanged=all(sha(p)==h for p,h in read(R/'PARENT_SOURCE_LOCK.json').items()),
      calculation_checks=c['checks'],hardware_or_complete_design_pass=False)
    report['native_RTN_GND_short_control']=dict(detected=short_detected,violations=len(bad_drc['violations']),active_board_unchanged=active_preserved)
    report['scoped_verification_passed']=not bad and not mismatch and all(x['detected'] for x in injected) and not viol and all(not d['violations'] and not d['unconnected_items'] for d in drcs.values()) and c['scoped_checks_passed'] and report['prior_parent_files_unchanged'] and not native['pad_net_mismatch'] and short_detected and active_preserved
    (R/'VERIFICATION.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({q:report[q] for q in ['saved_operating_points','saved_identity_failures','source_hash_mismatches','native_ERC_violations','prior_parent_files_unchanged','scoped_verification_passed']}))
    assert report['scoped_verification_passed']
if __name__=='__main__':main()
