"""Saved-state conservation, source and native-rule validation; no hardware credit."""
from pathlib import Path
import copy,csv,hashlib,json,math,re,xml.etree.ElementTree as ET
from erc_source_contract import parse,children,node_uuid
A=Path(__file__).resolve().parents[1];D=A/'ecad/revisions/v35';R=A/'results/aux_v35'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def errors(z,e):
    if not z.get('equilibrium_found'):return ['NO_ALGEBRAIC_ROOT']
    im,ia,ib=z['main_A'],z['aux_A'],z['battery_A'];ctl=e['sequence_input_allocation_A'];iq=e['aux_protection_model']['quiescent_current_A']
    v=z['junction_V'];vf=z['main_fused_V'];vm=z['main_input_V'];va=z['efuse_input_V'];vt=z['aux_input_V']
    r=z['main_R_breakdown_ohm'];pre=r['fuse_typical_20C'];rm=sum(r.values());ra=z['aux_R_ohm'];apre=z['aux_before_IQ_R_ohm'];ron=e['aux_protection_model']['on_resistance_ohm']
    check={'battery_KCL':ib-im-ia-.003-iq,'shared_KVL':z['pack_V']-v-z['shared_R_ohm']*ib,
      'main_pre_KVL':v-vf-pre*(im+.003),'main_post_KVL':vf-vm-(rm-pre)*im,
      'aux_pre_KVL':v-va-apre*(ia+iq),'aux_post_KVL':va-vt-(ra-apre)*ia,
      'main_CPL':vm*(im-.003)-e['main_output_W']/z['eta_main']-e['startup_input_W'],
      'aux_CPL':vt*(ia-ctl)-e['aux_output_W']/e['eta_aux'],
      'sequence_allocation':z['sequence_input_A']-ctl,'THN_current':z['THN_input_A']-ia+ctl,
      'saved_input_power':z['input_power_W']-z['pack_V']*ib,
      'total_non_arm_heat':z['input_power_W']-360-sum(z['heat_breakdown_W'].values()),
      'saved_heat_sum':z['accounted_non_arm_heat_W']-sum(z['heat_breakdown_W'].values()),
      'power_residual':z['power_balance_residual_W']-(z['input_power_W']-e['main_output_W']/z['eta_main']-e['startup_input_W']-e['aux_output_W']/e['eta_aux']-vt*ctl-sum(z['heat_W'].values())),
      'heat_residual':z['heat_balance_residual_W']-(z['input_power_W']-360-sum(z['heat_breakdown_W'].values())),
      'battery_margin':z['battery_current_margin_A']-(e['battery_current_limit_A']-ib)}
    expected={'Q201':im**2*r['Q201_25C'],'shunts':im**2*r['shunts'],'fuse':(im+.003)**2*pre,
      'copper':im**2*r['copper_20C'],'other_main':im**2*r['other_wiring_contacts_allocation'],
      'shared_contact':ib**2*z['shared_R_ohm'],'aux_branch':apre*(ia+iq)**2+(ra-apre-ron)*ia**2,
      'efuse_conduction':ia**2*ron,'efuse_quiescent':va*iq,'CHB':e['main_output_W']*(1/z['eta_main']-1),
      'THN':e['aux_output_W']*(1/e['eta_aux']-1),'input_startup':e['startup_input_W'],
      'input_controller':vf*.003,'input_capacitor_leakage':vm*.003,'aux_sequence_allocation':vt*ctl,
      'STOP_output_allocation':e['aux_output_W'],'brake_bias_output_allocation':1.}
    check.update({'heat_'+key:z['heat_breakdown_W'][key]-val for key,val in expected.items()})
    return [dict(identity=key,residual=val if math.isfinite(val) else 'NONFINITE') for key,val in check.items() if not math.isfinite(val) or abs(val)>1e-7]
def source_errors(c,e,selected,cs):
    er=[]
    if e['aux_protection_model']['consumer']!='tools/aux_operating_point_v35.py':er.append('STALE_CONSUMER')
    if e['sequence_input_allocation_A']!=.030:er.append('WRONG_CONTROL_ALLOCATION')
    if e['main_output_W']!=361 or e['aux_output_W']!=16.8:er.append('TASK_BUDGET_CHANGED')
    for ref,s in selected.items():
        if 'resistance_ohm' not in s:continue
        value=cs[ref].findtext('value');m=re.fullmatch(r'([\d.]+)([kKmM]?)',value)
        if not m or float(m[1])*{'':1,'k':1e3,'K':1e3,'m':1e6,'M':1e6}[m[2]]!=s['resistance_ohm']:er.append('RESISTOR_SOURCE_'+ref)
    s=c['static'];expected=s['bias_V'][0]/(selected['R231']['resistance_ohm']*1.01*1.0025)-.0005-.001
    if s['D210_reverse_leakage_screen_A']!=.001 or abs(s['bleed_minus_remote_source_A']-expected)>1e-12 or expected<=.001:er.append('MINIMUM_LOAD_WITH_LEAKAGE')
    for name in ['hardware_startup_inrush_known','STOP_manual_rearm_brownout_verified','whole_design_complete','power_on_release','joint_time_domain_simulation_completed']:
        if c[name] is not False:er.append('UNPROVEN_SCOPE_'+name)
    return er
def main():
    c=read(R/'CALCULATIONS.json');e=read(R/'ELECTRICAL_CANDIDATE.json');n=read(R/'NATIVE_AUDIT.json');selected=read(R/'SELECTED_PARTS.json')
    cs={z.get('ref'):z for z in ET.parse(D/'wp10_system.xml').getroot().findall('./components/comp')}
    rows=[q['result'] for q in c['paired_cases']]
    failed=[dict(case=i,errors=er) for i,z in enumerate(rows) if (er:=errors(z,e))]
    inputs_bad=source_errors(c,e,selected,cs);neg=[]
    for field,change in [('battery_A',.01),('input_power_W',float('nan')),('aux_input_V',-.02),('sequence_input_A',-.005)]:
        z=copy.deepcopy(rows[-1]);z[field]+=change;er=errors(z,e);neg.append(dict(case=field,detected=bool(er),errors=er))
    z=copy.deepcopy(rows[-1]);z['heat_breakdown_W']['aux_sequence_allocation']-=.1;z['heat_breakdown_W']['CHB']+=.1
    er=errors(z,e);neg.append(dict(case='same_sum_wrong_heat_assignment',detected=bool(er),errors=er))
    for key in ['stale_consumer','wrong_R231','missing_D210_leak']:
        cc=copy.deepcopy(c);ee=copy.deepcopy(e);ss=copy.deepcopy(selected)
        if key=='stale_consumer':ee['aux_protection_model']['consumer']='tools/aux_operating_point_v34.py'
        if key=='wrong_R231':ss['R231']['resistance_ohm']=2700
        if key=='missing_D210_leak':cc['static']['D210_reverse_leakage_screen_A']=0
        er=source_errors(cc,ee,ss,cs);neg.append(dict(case=key,detected=bool(er),errors=er))
    mismatch=[p for bundle in [c['source_bindings'],n['source_bindings']] for p,h in bundle.items() if sha(p)!=h]
    erc=read(R/'SYSTEM_ERC.json');drc=read(R/'AUX_DRC.json');main=read(A/'results/aux_v34/MAIN_DRC.json')
    ev=[z for s in erc['sheets'] for z in s['violations']]
    root=parse((D/'wp10_system.kicad_sch').read_text(encoding='utf-8'));root_id='/'+node_uuid(root)
    expected_paths={root_id}|{root_id+'/'+node_uuid(s) for s in children(root,'sheet')}
    erc_valid=erc.get('kicad_version')=='10.0.6' and set(erc.get('included_severities',[]))=={'error','warning'} and len(erc['sheets'])==len(expected_paths)==15 and {s['uuid_path'] for s in erc['sheets']}==expected_paths
    locks=[read(R/'PARENT_SOURCE_LOCK.json'),read(A/'results/aux_v34/PARENT_SOURCE_LOCK.json')]
    preserved=all(sha(p)==h for lock in locks for p,h in lock.items())
    matrix_rows=list(csv.DictReader((A/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig')))
    native_ok=all(n[key] for key in ['all_aux_pads_net_and_values_match','original_power_segments_covered','all_original_segments_covered','old_vias_preserved','primary_internal_RTN_and_secondary_domains_separate','original_parent_files_unchanged','main_board_byte_identical_to_V34'])
    assert n['native_components']==237 and n['native_pin_net_records']==767 and n['source_pages']==15
    native_results={label:dict(violations=len(report['violations']),unconnected=len(report['unconnected_items']),ignored_checks=report.get('ignored_checks',[])) for label,report in [('AUX_V35',drc),('MAIN_BYTE_IDENTICAL_V34',main)]}
    ok=not failed and not inputs_bad and not mismatch and all(t['detected'] for t in neg) and erc_valid and not ev and all(not z['violations'] and not z['unconnected'] for z in native_results.values()) and native_ok and preserved and len(matrix_rows)==37 and c['scoped_checks_passed']
    bound_files=[R/nm for nm in ['CALCULATIONS.json','ELECTRICAL_CANDIDATE.json','NATIVE_AUDIT.json','SYSTEM_ERC.json','AUX_DRC.json','PARENT_SOURCE_LOCK.json','SELECTED_PARTS.json']]+[A/'results/aux_v34/MAIN_DRC.json',A/'results/aux_v34/PARENT_SOURCE_LOCK.json',A/'SYSTEM_CLOSURE_MATRIX.csv',Path(__file__).resolve()]
    result=dict(revision='V35',saved_operating_points=len(rows),saved_identity_failures=failed,source_contract_failures=inputs_bad,
      negative_controls=neg,source_hash_mismatches=mismatch,native_ERC_violations=len(ev),native_ERC_sheets=len(erc['sheets']),ERC_ignored_checks=erc.get('ignored_checks',[]),native_DRC=native_results,
      native_audit_passed=native_ok,native_ERC_hierarchy_valid=erc_valid,parent_sources_unchanged=preserved,original_closure_matrix_rows=len(matrix_rows),
      original_873_and_99_lineage_not_new_native_integration=True,calculation_checks=c['checks'],
      scoped_verification_passed=ok,hardware_tests=0,complete_system_PCB_parity_checked=False,whole_design_complete=False,power_on_release=False,
      original_main_DRC_scope='Inherited exact V34 main board; not rerun or claimed as new V35 physical PCB build',
      source_bindings={str(p):sha(p) for p in bound_files})
    (R/'VERIFICATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['saved_operating_points','saved_identity_failures','source_contract_failures','source_hash_mismatches','native_ERC_violations','native_ERC_sheets','original_closure_matrix_rows','scoped_verification_passed']}));assert ok
if __name__=='__main__':main()
