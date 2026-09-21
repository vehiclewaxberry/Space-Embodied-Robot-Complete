from pathlib import Path
import json,csv,hashlib,xml.etree.ElementTree as ET,itertools,math,collections
E=Path(__file__).resolve().parents[1];C=E.parents[1]/'wp09_interfaces_20260907_1525/system_completion'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
j=json.loads((E/'STOP_CIRCUIT_CONNECTIVITY.json').read_text(encoding='utf8'));parts={p['ref']:p for p in j['parts']}
ep={p['ref']+'.'+a['number']:a['net'] for p in j['parts'] for a in p['pins'] if a['net']}
actual={n.attrib['ref']+'.'+n.attrib['pin']:net.attrib['name'].lstrip('/') for net in ET.parse(E/'wp09_stop_circuit.net.xml').getroot().findall('./nets/net') for n in net.findall('node')}
checks=[]
def ck(n,ok,d=None):checks.append(dict(name=n,passed=bool(ok),detail=d))
for p,net in ep.items():ck('NET_'+p,actual.get(p)==net)
nc={p['ref']+'.'+a['number'] for p in j['parts'] for a in p['pins'] if a['net'] is None}
ck('NO_UNEXPECTED_ENDPOINTS',set(actual)==set(ep)|nc)
for p in nc:ck('EXPLICIT_NC_'+p,actual[p].startswith('unconnected-'))
ck('ACTUAL_SUPPLY_POWER_OUTPUTS',ep['U120.3']=='STOP_3V3' and ep['U121.3']=='STOP_5V' and all(a['electrical_type']=='power_out' for r in ['U120','U121'] for a in parts[r]['pins'] if a['number']=='3'))
ck('MODULES_UPSTREAM_K1',ep['U120.1']==ep['U121.1']==ep['J101.3']==ep['J104.1']=='STOP_24V')
ck('RETURN_COMMON',ep['U120.2']==ep['U121.2']==ep['J101.4']=='STOP_GND')
ck('AUX_NOT_SHORTED',ep['J105.1']!=ep['J105.2'])
ck('AUX_24V_DIVIDER',ep['J105.1']=='STOP_24V' and ep['R115.1']==ep['J105.2']=='AUX_RETURN' and ep['R115.2']==ep['R130.1']==ep['R116.1']=='AUX_DIV' and ep['R130.2']=='STOP_GND' and ep['R116.2']==ep['U113.2']=='AUX_SENSE')
ck('AHCT_SAME_RAIL_AS_DRIVER',ep['U119.5']==ep['U112.3']=='STOP_5V')
ck('NO_EXTERNAL_COIL_DIODE',not any(r.startswith('D') for r in parts))
ck('NO_PWR_FLAG','PWR_FLAG' not in ''.join(p['mpn'] for p in j['parts']))
erc=json.loads((E/'STOP_ERC.json').read_text());v=[a for s in erc['sheets'] for a in s['violations']]
ck('ONLY_TRUE_STANDALONE_INPUT_RAIL_ERC_ERRORS',len(v)==2 and all(a['type']=='power_pin_not_driven' for a in v) and all('U101 Pin 4' in str(a) or 'U120 Pin 1' in str(a) for a in v))
# All consumers recomputed for explicit GSE0..50C static rail contract.
T=[0,50];dt=max(abs(t-25) for t in T)
err=.02+.002+.004+.00015*dt
lo3,hi3=3.3*(1-err),3.3*(1+err);lo5,hi5=5*(1-err),5*(1+err)
# Conservative resistance screen spans film temperature0..250C, not onlyambient;
# plus separate soldering1%R+.05ohm and1000h endurance5%R+.1ohm allowances.
# This is not an arbitrary-life drift guarantee. Thermal layout still requires verification.
film_delta=225
rmin=lambda r:r*(1-.05)*(1-.00025*film_delta)-(.01*r+.05)-(.05*r+.1)
rmax=lambda r:r*(1+.05)*(1+.00025*film_delta)+(.01*r+.05)+(.05*r+.1)
pre=[]
for ref,r,lo,hi in [('R124',24,lo3,hi3),('R125',39,lo5,hi5)]:
 imin=lo/rmax(r);imax=hi/rmin(r);pmax=hi**2/rmin(r)
 row=dict(ref=ref,nominal_ohm=r,resistance_ohm=[rmin(r),rmax(r)],current_A=[imin,imax],dissipation_W_max=pmax,rated_W_at_ambient_le70C=2,ambient_C=T,temperature_resistance_screen_C=[0,250],TCR_bound_per_K=.00025,soldering_drift_fraction=.01,soldering_drift_ohm=.05,endurance1000h_drift_fraction=.05,endurance1000h_drift_ohm=.1,arbitrary_lifetime_guarantee=False,reference_Rth_K_W=75,hotspot_reference_screen_C=50+75*pmax,layout_hotspot_max_requirement_C=155,part_body_temperature_and_PCB_clearance_qualified=False)
 pre.append(row);ck('MIN_LOAD_GE10PCT_'+ref,imin>=.1,row);ck('RESISTOR_LOAD_LT50PCT_RATING_'+ref,pmax<=1,row)
ck('SOURCE_MAX_INPUT_36V_COVERS_STEADY',24.96<=36 and 23.04>=6.5)
ck('MODULE_NO_TEMP_DERATING_IN_SELECTED_GSE_RANGE',max(T)<=60)
restore3=3.07*(1+.0125)*(1+.025);restore5=4.65*(1+.015)*(1+.025)
ck('3V3_STATIC_RECOVERY_MARGIN',lo3>restore3,dict(supply_min=lo3,restore_max=restore3))
ck('5V_STATIC_RECOVERY_MARGIN',lo5>restore5,dict(supply_min=lo5,restore_max=restore5))
consumer=[]
for ref in ['U101','U102','U103','U104','U105','U106','U107','U108','U109','U110','U111','U113','U114','U115','U116','U117','U118']:
 low,high=(1.8,6.5) if ref=='U101' else ((1.7,6.5) if ref in ['U102','U103','U104'] else ((1.65,3.6) if ref in ['U107','U108'] else (1.65,5.5)))
 row=dict(ref=ref,rail='STOP_3V3',static_V=[lo3,hi3],recommended_supply_V=[low,high],functional3V3_threshold_table_used=True)
 consumer.append(row);ck('CONSUMER_SUPPLY_'+ref,lo3>=low and hi3<=high)
for ref,lim in [('U119',[4.5,5.5]),('U112',[4.5,18])]:
 consumer.append(dict(ref=ref,rail='STOP_5V',static_V=[lo5,hi5],recommended_supply_V=lim));ck('CONSUMER_SUPPLY_'+ref,lo5>=lim[0] and hi5<=lim[1])
ck('LVC_3V3_DC_TABLE_VALID',lo3>=2.7 and hi3<=3.6)
# All CRCW bounds include1% plus100ppm/C over25K, using2% conservative interval.
rlow,rhigh=.98,1.02
run_load=hi3/(47000*rlow)+6e-6
vh=(3.8-10e-6*(1000*rhigh))/(1+(1000*rhigh)/(10000*rlow))
vl=.44+10e-6*(1000*rhigh)
ck('LVC_TO_AHCT_LOAD_LT100UA',run_load<100e-6,run_load)
ck('LVC_TO_AHCT_HIGH',lo3-.2>2.0)
ck('AHCT_SOURCE_LOAD_LT8MA',hi5/(1000*rlow+10000*rlow)+10e-6<.008)
ck('TC4420_HIGH_INCLUDES_PUBLISHED_10UA',vh>=2.4,vh)
ck('TC4420_LOW_INCLUDES_PUBLISHED_10UA',vl<=.8,vl)
ck('AHCT_INPUT_POWER_OFF_BOUND_APPLIES',hi3<=5.5)
ck('TC4420_INPUT_NOT_DIRECTLY_CONNECTED_TO_3V3',ep['U112.1']=='RUN_DRIVE' and ep['R111.1']==ep['U119.4']=='RUN_LEVEL_5V')
# Aux leakage sign enumerated. Solve exact three resistor network.
aux=[]
for supply,rt,rb,rs,ii in itertools.product([23.04,24.96],[22000*rlow,22000*rhigh],[3900*rlow,3900*rhigh],[1000*rlow,1000*rhigh],[-5e-6,5e-6]):
 div=(supply/rt-ii)/(1/rt+1/rb);sense=div-ii*rs;current=(supply-div)/rt
 aux.append(dict(supply=supply,rt=rt,rb=rb,rs=rs,ii=ii,sense=sense,current=current,top_power=(supply-div)**2/rt,bottom_power=div**2/rb))
amin=min(x['sense'] for x in aux);amax=max(x['sense'] for x in aux);imin=min(x['current'] for x in aux);imax=max(x['current'] for x in aux)
openmax=5e-6*(3900*rhigh+1000*rhigh)
ck('AUX_MIN_WETTING_VOLTAGE',23.04>=5)
ck('AUX_MIN_WETTING_CURRENT',imin>=.0001,imin)
ck('AUX_NUMERICAL_SCREEN_GT2V_NOT_SCHMITT_GUARANTEE',amin>2,amin)
ck('AUX_CLOSED_INPUT_LE5V5',amax<=5.5,amax)
ck('AUX_OPEN_LOW_LT0V8',openmax<.8,openmax)
ck('AUX_RESISTORS_LT0V1W_50C',max(x['top_power'] for x in aux)<.1 and max(x['bottom_power'] for x in aux)<.1)
fault_hi=lo3-10200*(2e-6+3*.3e-6+5e-6)
ck('FAULT_HIGH_NUMERICAL_SCREEN_NOT_CONTINUOUS_VCC_SCHMITT_GUARANTEE',fault_hi>2)
ck('FAULT_SINK_RECOMPUTED',hi3/9800+8e-6<.001)
# Preserve core hardware state policy in a finite logical model, not analog simulation.
src=(C/'tools/stop_circuit_verify_r2.py').read_text(encoding='utf8');logic=src[src.index('def step('):src.index('# Calculated component ranges')]
exec(compile(logic,'parent_finite_logic_oracle','exec'),globals())
# Counterexamples prevent the limited static pass from expanding into hardware release.
falsifiers=[dict(id='RIPPLE_TYP_NOT_GUARANTEE',input=dict(max_ripple_V=None),result='UNKNOWN_INHIBIT',reason='50mVpp is typical, not a guaranteed maximum'),dict(id='FULL_MODULE_TEMPERATURE_RANGE',input=dict(C=[-40,85]),result='STATIC_G50_RESTORE_CAN_FAIL',supply_min=5*(1-.02-.002-.004-.00015*65),restore_max=restore5),dict(id='50PCT_LOAD_STEP',input=dict(drop_V=.2),result='CAN_CROSS_UV_THRESHOLD',lowest5V=lo5-.2,restore_max=restore5),dict(id='MODULE_FAIL_SHORT_24V_TO_LOGIC',input=dict(output_V=24),result='UNPROTECTED_OVERVOLTAGE_FAULT',reason='No claim of single-fault-tolerant redundant power protection'),dict(id='TC4420_BIAS_BELOW4V5',input=dict(VDD=3.0),result='OUTPUT_BEHAVIOR_NOT_GUARANTEED',reason='No UVLO guarantee; external monitored clear timing must be measured'),dict(id='EXTERNAL_MCU_DOMAIN_LOST',input=dict(MCU_VIO=0),result='STATUS_INVALID_INHIBIT',reason='No valid logic-high receiver observation'),dict(id='NO_BUS_DIAGNOSTIC',input=dict(BUS_MONITOR_OK=None),result='PULLDOWN_INHIBIT',reason='Bus ADC and welded-contact diagnosis not implemented')]
ck('COUNTEREXAMPLE_COLD_G50_STATIC_FAIL',falsifiers[1]['supply_min']<restore5)
ck('COUNTEREXAMPLE_TRANSIENT_CAN_RESET',lo5-.2<restore5)
ck('COUNTEREXAMPLE_MODULE_SHORT_EXCEEDS_LOGIC',24>5.5)
calc=dict(scope='GSE0..50C_STATIC_DESIGN_CANDIDATE_NOT_MEASUREMENT',module_ambient_C=T,static_fractional_error=err,error_stack=dict(set_accuracy=.02,line=.002,load10_to100pct=.004,tempco_per_K=.00015,delta_from25C_K=dt),rail3V3_V=[lo3,hi3],rail5V_V=[lo5,hi5],rail24V_V=[23.04,24.96],supervisor_restore_max_V=dict(G33=restore3,G50=restore5),restore_DC_margins_V=dict(G33=lo3-restore3,G50=lo5-restore5),preloads=pre,consumers=consumer,driver=dict(mpn='TC4420CAT',input_current_published_A=[-1e-5,1e-5],AHCT_source_VOH_min=3.8,AHCT_to_driver_high_min_V=vh,AHCT_to_driver_low_max_V=vl,full_operating_input_current_gap_closed=True,AHCT_poweroff_input_leakage_max_A=1e-6,AHCT_output_Ioff_claim=False,driver_UVLO_guarantee=False,drive_DC_screen_V=lo5-.025,loaded_driver_output_at5V_proven=False),aux=dict(wetting_current_A=[imin,imax],sense_closed_V=[amin,amax],sense_open_max_V=openmax,resistor_top_power_W_max=max(x['top_power'] for x in aux),resistor_bottom_power_W_max=max(x['bottom_power'] for x in aux),actual_contact_min_spec_V=5,actual_contact_min_spec_A=.0001,all_interval_corners=len(aux)),power_budget=dict(preload_output_W_max=sum(x['dissipation_W_max'] for x in pre),additional_3V3_load_budget_A_requirement=.03,additional_5V_load_budget_A_requirement=.02,measured_input_power_W=None,conversion_efficiency_guaranteed_min=None,fuse_coordination_complete=False),watchdog_parent120pf_unchanged=True,full_chain_100ms_closed=False,PCB_complete=False,hardware_io_count=0,counterexamples=falsifiers)
calc.update(schmitt_threshold_guarantee=dict(status='CONTINUOUS_VCC_BOUNDS_NOT_ESTABLISHED',part='SN74LVC1G17',revision='SCES351Y October2025',datasheet_VCC_test_points_V=[1.65,2.3,3,4.5,5.5],VTplus_max_V=[1.13,1.56,1.92,2.74,3.33],VTminus_min_V=[.35,.56,.89,1.51,1.88],actual_supply_V=[lo3,hi3],ordinary_LVC_VIH2V_is_not_substitute=True,applies_to=['U106 FAULT_N_RAW','U113 AUX_SENSE','U115 HEARTBEAT_FILTER','U105 dual-Schmitt RESET/START uses separate discrete table'],full_logic_hardware_level_guarantee=False),aux_poweroff_screen=dict(Ioff_max_A=10e-6,open_input_abs_V_max=10e-6*(3900*1.02+1000*1.02),closed_input_abs_upper_conservative_V=24.96*(3900*1.02)/(22000*.98+3900*1.02)+10e-6*(1000*1.02+3900*1.02),input_rating_Vmax=5.5,valid_output_when_VCC0=False),dynamic_supply_requirements=dict(guaranteed_negative_deviation_from_static_lower_V_max=dict(rail3V3=lo3-restore3,rail5V=lo5-restore5),proposed_design_budget_mV=10,actual_guaranteed_peak_deviation=None,prototype_probe_acceptance_not_executed=True,ripple_typical50mVpp_is_not_qualified_against_budget=True,existing50pct_step200mV_max_exceeds_budget=True,no_auto_restart_after_uv_recovery_requires_actual_timing_verification=True),dc_supply_selection_alternatives=dict(lower_supervisor_threshold='Not adopted: must preserve minimum logic/driver operational voltage and reset dynamics; reducing threshold solely for margin is not allowed',precision_postregulator='Potential revision needs headroom, power-off reverse behavior and output-fault protection design; not implemented or credited',flight_supply='Not selected by this GSE branch'))
dump(E/'STOP_SUPPLY_CALCULATIONS.json',calc)
ports=json.loads((C/'electrical_delta/STOP_PORT_MAP.json').read_text(encoding='utf8'))
ports.update(schematic=str(E/'wp09_stop_circuit.kicad_sch'),revision='WP10_AUX_SUPPLY_R3',source_binding='J101.3/.4 to protected24V/GND before K1. Test pins1/2 must not receive external source.',full_electrical_design_complete=False)
for a in ports['ports']:
 key=a['connector']+'.'+a['pin'];a['net']=ep[key];p=next(p for p in parts[a['connector']]['pins'] if p['number']==a['pin']);a['label']=p['name']
 if key in ['J101.1','J101.2']:a['hierarchical_direction']='output';a['status']='INTERNAL_SUPPLY_TEST_ONLY_NO_EXTERNAL_VOLTAGE'
for a in ports['legacy_mapping']:
 if a.get('wire_id')=='K1_FB2':a.update(net='STOP_24V',note='Physical auxiliary contact feed24V; return divides22k/3.9k, contact not bypassed')
 if a.get('wire_id')=='K1_COILP':a['source_unbound']=False;a['source_scope']='Parent Q1 protected24V upstream K1; branch coordination not closed'
dump(E/'STOP_PORT_MAP.json',ports)
status=dict(status='PASS_STATIC_SUPPLY_AND_PUBLISHED_DRIVER_INPUT_MARGIN__DYNAMIC_STOP_CHAIN_OPEN',components=len(parts),connected_pins=len(ep),nets=len(set(ep.values())),checks=len(checks),passed=sum(x['passed'] for x in checks),all_checks_pass=all(x['passed'] for x in checks),erc_errors=len(v),erc_status='TWO_EXTERNAL_INPUT24V_AND_RETURN_ERRORS_EXPECT_PARENT_BINDING',auxiliary_supply_components_bound=True,published_driver_input_current_gap_closed=True,source_static_scope_C=T,regulated_rails_all_dynamic_conditions_qualified=False,full_stop_chain_closed=False,full_electrical_design_complete=False,manufacturing_release=False,physical_tests=0,details=checks,input_sha256={str(p.relative_to(E)):sha(p) for p in [E/'STOP_CIRCUIT_CONNECTIVITY.json',E/'wp09_stop_circuit.kicad_sch',E/'wp09_stop_circuit.net.xml',E/'STOP_ERC.json',E/'STOP_SUPPLY_CALCULATIONS.json']})
dump(E/'results/STOP_SUPPLY_VERIFICATION.json',status)
print(json.dumps({k:status[k] for k in ['status','components','connected_pins','nets','checks','passed','all_checks_pass','erc_errors']}));print(json.dumps(dict(rails=[lo3,hi3,lo5,hi5],margins=calc['restore_DC_margins_V'],preload=pre,aux=calc['aux'],driver=calc['driver'])))
assert status['all_checks_pass']

