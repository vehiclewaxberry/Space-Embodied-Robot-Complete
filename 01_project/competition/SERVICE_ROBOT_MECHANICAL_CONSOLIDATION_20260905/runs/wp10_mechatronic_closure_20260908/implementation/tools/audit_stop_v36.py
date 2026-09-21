"""Native-netlist delta and bounded STOP interface checks. No hardware credit."""
from pathlib import Path
import json,hashlib,csv,copy,itertools,xml.etree.ElementTree as ET
from erc_source_contract import parse,children,node_uuid
A=Path(__file__).resolve().parents[1];D=A/'ecad/revisions/v36';P=D.parent/'v35';R=A/'results/stop_v36'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def load_xml(p):
    rt=ET.parse(p).getroot();cs={c.get('ref'):c for c in rt.findall('./components/comp')};nets={n.get('ref')+'.'+n.get('pin'):net.get('name') for net in rt.findall('./nets/net') for n in net.findall('node')};return cs,nets
# This validator belongs to the239-ref source checkpoint. Refuse to bind current
# edited schematics to old XML/ERC. Updated PCB work uses a fresh native receipt.
prior=read(A/'history/V36_STOP_SOURCE_BEFORE_PCB_20260915/results/SOURCE_VERIFICATION.json')
stale=[p for p,h in prior['source_bindings'].items() if Path(p).resolve()!=Path(__file__).resolve() and (not Path(p).is_file() or sha(p)!=h)]
if stale:
    raise RuntimeError('STALE_NATIVE_INPUTS: legacy239-ref validator cannot validate edited source. Export and verify the new checkpoint first. Mismatches: '+repr(stale))
oldc,oldn=load_xml(P/'wp10_system.xml');cs,nets=load_xml(D/'wp10_system.xml')
local='/Actual watchdog and contactor driver/'
expected=dict(oldn)
desired={
 'U112.1':local+'STOP_5V','U112.2':'WP10_ARM_RETURN','U112.3':'WP10_BRAKE_THERMAL_FAULT_N','U112.4':local+'RUN_INHIBIT_5V','U112.5':local+'GATE_DRV',
 'U119.1':'unconnected-(U119-NC-Pad1)','U119.2':local+'RUN_DRIVE','U119.3':'WP10_ARM_RETURN','U119.4':local+'RUN_INHIBIT_5V','U119.5':local+'STOP_5V',
 'R111.1':local+'RUN_LATCH','U102.3':local+'STOP_5V','U102.6':local+'STOP_5V','C111.1':local+'STOP_5V',
 'R180.1':local+'STOP_5V','R180.2':local+'RUN_INHIBIT_5V','R181.1':'WP10_BRAKE_THERMAL_FAULT_N','R181.2':'WP10_ARM_RETURN'}
expected.update(desired)
def topology_errors(n):return [{'pin':k,'expected':v,'actual':n.get(k)} for k,v in expected.items() if n.get(k)!=v]+[{'extra_pin':k} for k in n if k not in expected]
topo_errors=topology_errors(nets);allowed={'U102','U112','U119','R101','R111'}
unchanged_parts=all((cs[k].findtext('value'),cs[k].findtext('footprint'))==(c.findtext('value'),c.findtext('footprint')) for k,c in oldc.items() if k not in allowed)
erc=read(R/'SYSTEM_ERC.json');ev=[v for s in erc['sheets'] for v in s['violations']];root=parse((D/'wp10_system.kicad_sch').read_text());rid='/'+node_uuid(root);paths={rid}|{rid+'/'+node_uuid(s) for s in children(root,'sheet')}
parent_erc=read(A/'results/aux_v35/SYSTEM_ERC.json')
erc_ok=not ev and erc.get('kicad_version')=='10.0.6' and len(erc['sheets'])==len(paths)==15 and {s['uuid_path'] for s in erc['sheets']}==paths and set(erc.get('included_severities',[]))=={'error','warning'} and erc.get('ignored_checks',[])==parent_erc.get('ignored_checks',[])
parent=read(R/'PARENT_SOURCE_LOCK.json');parents_ok=all(sha(p)==h for p,h in parent.items())
supply=read(A.parent/'electrical/STOP_SUPPLY_CALCULATIONS.json');leak=read(A/'power/STOP_FULL_FAULT_BUDGET.json')
known=sum(z['max_leak_A'] for z in leak['inventory']);assert abs(known-9.7e-6)<1e-12
vmin,vmax=supply['rail3V3_V'];reserve=1e-6;ileak=known+reserve
lo=.99*.9975;hi=1.01*1.0025;ru=4700*hi;rd=47000*lo
def max_input_sink(v):return (vmin-v)/ru-v/rd-ileak
def raw_with_input_r(r):return (vmin/ru-ileak)/(1/ru+1/rd+1/r)
corners=[]
for rs,rp in itertools.product([100*lo,100*hi],[10000*lo,10000*hi]):
    rth=rs*rp/(rs+rp);vh=(2.4/rs-1e-6)/(1/rs+1/rp);vl=(.55/rs+1e-6)/(1/rs+1/rp)
    corners.append(dict(R111_ohm=rs,R112_ohm=rp,high_V=vh,low_V=vl,rise_RC_ns_per_V=rth*20e-12/(vh-2.11)*1e9,fall_RC_ns_per_V=rth*20e-12/(.8-vl)*1e9))
logic=[dict(raw_healthy=raw,run=run,uvlo_active=uvlo,out=raw and run and not uvlo) for raw,run,uvlo in itertools.product([False,True],repeat=3)]
calc=dict(scope='0..50C CONDITIONAL STATIC AND DECLARED RC BUDGET; NOT TRANSIENT SIMULATION',rail3V3_V=[vmin,vmax],rail5V_V=supply['rail5V_V'],resistor_factors=[lo,hi],
 legacy_leakage_testpoint_transfer_sensitivity_A=known,additional_leakage_engineering_allocation_A=reserve,UCC_input_current_max_published=False,
 RAW_allowed_additional_UCC_sink_A={str(v):max_input_sink(v) for v in [2.4,2.74]},RAW_conditional_voltage_V={str(r):raw_with_input_r(r) for r in [100000,200000]},
 R101_open_existing_leakage_voltage_V=ileak*47000*hi,R101_open_allowed_UCC_source_A=1/(47000*hi)-ileak,
 R101_max_pullup_current_A=vmax/(4700*lo),TPS3808_recommended_pullup_ohm=[10000,1000000],
 pullup_deviation_basis='4.7k below recommended10k; normal VDD>=1.8V, TPS3808 IOL1mA/VOL0.4V test point screens load. Other OD sink ratings, transient and leakage condition transfer still require verification.',
 RUN_corner_models=corners,RUN_high_min_V=min(z['high_V'] for z in corners),RUN_low_max_V=max(z['low_V'] for z in corners),
 RUN_source_edge_engineering_allocation_ns_per_V=10,RUN_total_C_engineering_allocation_pF=20,
 RUN_rise_slew_budget_ns_per_V=10+max(z['rise_RC_ns_per_V'] for z in corners),RUN_fall_slew_budget_ns_per_V=10+max(z['fall_RC_ns_per_V'] for z in corners),
 RUN_model_limit='LVC74A VOH2.4V at3V/-12mA and VOL0.55V at3V/24mA transferred conservatively to low-load screening; Q output edge and source impedance not bound. 10ns/V is an allocation, NOT LVC74A output guarantee. 100ohm does not inherit 1kohm fault-current limiting.',
 LV1T04_additional_ICC_screen_A=.0015,UCC_UVLO_rising_V=[3.70,4.65],UCC_UVLO_falling_V=[3.45,4.35],
 truth_table=logic,all_brownouts_verified=False,manual_rearm_verified=False,STOP_PCB_implemented=False,whole_design_complete=False,hardware_tests=0)
dump(R/'CALCULATIONS.json',calc)
negative=[]
for name,pin,wrong in [('RAW_bypassed','U112.3','WP10_BRAKE_STOP_3V3'),('driver_inputs_swapped','U112.4','WP10_BRAKE_THERMAL_FAULT_N'),('supervisor_loses_bias_with_logic','U102.6','WP10_BRAKE_STOP_3V3'),('wrong_decoupling_rail','C111.1','WP10_BRAKE_STOP_3V3'),('inhibit_pullup_removed','R180.1','DISCONNECTED')]:
    bad=dict(nets);bad[pin]=wrong;negative.append(dict(case=name,detected=bool(topology_errors(bad))))
checks=dict(exact_239_components=set(cs)==set(oldc)|{'R180','R181'} and len(cs)==239,exact_771_pin_nets=len(nets)==771 and not topo_errors,unaffected_components_preserved=unchanged_parts,native_ERC_15_sheets_clean=erc_ok,parent70files_unchanged=parents_ok,main_PCB_inherited_unchanged=sha(D/'wp10_main_input.kicad_pcb')==sha(P/'wp10_main_input.kicad_pcb') if (D/'wp10_main_input.kicad_pcb').exists() else False,
 all_mutated_negative_controls_detected=all(x['detected'] for x in negative),conditional_RUN_levels=min(z['high_V'] for z in corners)>2.11 and max(z['low_V'] for z in corners)<.8,
 conditional_RC_slew_budget=calc['RUN_rise_slew_budget_ns_per_V']<20 and calc['RUN_fall_slew_budget_ns_per_V']<20,
 UCC_input_unknown_preserved=calc['UCC_input_current_max_published'] is False,formal_pointer_remains_V35=read(A/'CURRENT_WORKING_CANDIDATE.json')['revision']=='V35')
# Board file name is inherited from the parent; find the main file without guessing an alias.
boards={p.name:sha(p)==sha(P/p.name) for p in D.glob('*.kicad_pcb')};checks['main_PCB_inherited_unchanged']=bool(boards) and all(boards.values())
checks['selected_resistances_match_native_source']=all(cs[k].findtext('value')==v for k,v in {'R101':'4.7k','R111':'100','R180':'10k','R181':'47k'}.items())
checks['two_IC_MPNs_match_native_source']=cs['U112'].findtext('value')=='UCC27517DBVR' and cs['U119'].findtext('value')=='SN74LV1T04DBVR'
bound=list(D.glob('*.kicad_sch'))+[D/'wp10_system.xml',D/'WP10STOP36.kicad_sym',D/'sym-lib-table',D/'fp-lib-table',D/'Package_TO_SOT_SMD.pretty/SOT-23-5.kicad_mod',R/'SYSTEM_ERC.json',R/'CALCULATIONS.json',R/'SELECTED_PARTS.json',R/'PARENT_SOURCE_LOCK.json',A.parent/'electrical/STOP_SUPPLY_CALCULATIONS.json',A/'power/STOP_FULL_FAULT_BUDGET.json',Path(__file__)]
result=dict(revision='V36_WORKING',scope='NATIVE_SOURCE_DELTA_AND_CONDITIONAL_INTERFACE_CALCULATION_ONLY',checks=checks,scoped_source_check_passed=all(checks.values()),pin_mismatches=topo_errors,negative_controls=negative,ERC_errors=sum(v['severity']=='error' for v in ev),ERC_warnings=sum(v['severity']=='warning' for v in ev),electrical_refs=len(cs),pin_records=len(nets),inherited_PCB_hash_match=boards,STOP_PCB_implemented=False,whole_design_complete=False,power_on_release=False,source_bindings={str(p):sha(p) for p in bound})
result['ERC_ignored_checks_inherited_unchanged']=erc.get('ignored_checks',[])
dump(R/'SOURCE_VERIFICATION.json',result)
for filename,header,rows in [('V36_SYSTEM_BOM.csv',['Reference','Value','Footprint','MPN'],[[k,c.findtext('value'),c.findtext('footprint'),c.findtext("./fields/field[@name='MPN']")] for k,c in sorted(cs.items())]),('V36_PIN_NETS.csv',['Endpoint','Net'],sorted(nets.items()))]:
    with (R/filename).open('w',newline='',encoding='utf-8-sig') as f:w=csv.writer(f);w.writerow(header);w.writerows(rows)
print(json.dumps({k:result[k] for k in ['scoped_source_check_passed','electrical_refs','pin_records','ERC_errors','ERC_warnings','pin_mismatches','checks']},ensure_ascii=False));assert result['scoped_source_check_passed']
