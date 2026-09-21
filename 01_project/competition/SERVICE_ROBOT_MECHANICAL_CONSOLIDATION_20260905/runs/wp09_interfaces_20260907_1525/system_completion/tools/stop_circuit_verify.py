from pathlib import Path
import json,csv,hashlib,collections,xml.etree.ElementTree as ET,itertools,math
C=Path(__file__).resolve().parents[1];E=C/'electrical_delta'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
j=json.loads((E/'STOP_CIRCUIT_CONNECTIVITY.json').read_text(encoding='utf8'));parts={p['ref']:p for p in j['parts']}
expected={p['ref']+'.'+a['number']:a['net'] for p in j['parts'] for a in p['pins'] if a['net']}
xml=ET.parse(E/'wp09_stop_circuit.net.xml').getroot();actual={}
for net in xml.findall('./nets/net'):
 for node in net.findall('node'):actual[node.attrib['ref']+'.'+node.attrib['pin']]=net.attrib['name'].lstrip('/')
checks=[]
def ck(name,ok,detail=None):checks.append(dict(name=name,passed=bool(ok),detail=detail))
for ep,net in expected.items():ck('NET_'+ep,actual.get(ep)==net,dict(expected=net,actual=actual.get(ep)))
nc={p['ref']+'.'+a['number'] for p in j['parts'] for a in p['pins'] if a['net'] is None}
ck('NO_UNEXPECTED_NET_ENDPOINTS',set(actual)==set(expected)|nc)
for ep in nc:ck('EXPLICIT_NC_'+ep,actual.get(ep,'').startswith('unconnected-'))
for net in xml.findall('./nets/net'):
 if net.attrib['name'].startswith('unconnected-'):ck('SINGLE_ISOLATED_NC_'+net.attrib['name'],len(net.findall('node'))==1)
for ref in ['U101','U102','U103','U104']:ck('OPEN_DRAIN_'+ref,all(a['electrical_type']=='open_collector' for a in parts[ref]['pins'] if a['net']=='FAULT_N_RAW'))
for ref in ['U107','U108']:
 ck('PRESET_TIED_HIGH_'+ref,all(a['net']=='STOP_3V3' for a in parts[ref]['pins'] if a['number'] in ['4','10']))
ck('INVERTING_DRIVER_INPUT_IS_GROUND',expected['U112.4']=='STOP_GND')
ck('EXTERNAL_HEARTBEAT_HAS_IOFF_BUFFER',expected['U101.6']==expected['U115.4']=='WDI' and expected['U115.2']=='HEARTBEAT_FILTER')
ck('NO_COIL_EXTERNAL_SUPPRESSION',not any(p['ref'][0]=='D' for p in j['parts']))
erc=json.loads((E/'STOP_ERC.json').read_text());v=[x for s in erc['sheets'] for x in s['violations']]
ck('ONLY_THREE_UNBOUND_SUPPLY_ERC_ERRORS',len(v)==3 and all(x['type']=='power_pin_not_driven' and x['severity']=='error' for x in v))
# Component-level logic transition oracle; no analog/timing simulator and no I/O.
def step(state,safe,reset,start,hb,reset_rise=False,start_rise=False,hb_fall=False):
 armed,run,seen=state
 if not safe:return (0,0,0)
 out_armed=seen if reset_rise else armed
 out_seen=1 if hb_fall else seen
 out_run=0 if reset else (armed if start_rise else run)
 return tuple(map(int,(out_armed,out_run,out_seen)))
logic=[]
def scenario(name,seq,end):
 s=(0,0,0);trace=[]
 for kw in seq:
  s=step(s,**({'safe':True,'reset':False,'start':False,'hb':False}|kw))
  trace.append(s)
 ck(name,s==end,trace);logic.append(dict(name=name,trace=trace,expected=end))
scenario('RESET_BEFORE_HEARTBEAT_CANNOT_ARM',[dict(reset=True,reset_rise=True),dict(reset=False),dict(start=True,start_rise=True)],(0,0,0))
scenario('HB_RESET_RELEASE_NEW_START_CAN_RUN',[dict(hb_fall=True),dict(reset=True,reset_rise=True),dict(reset=False),dict(start=True,start_rise=True)],(1,1,1))
scenario('START_HELD_BEFORE_RESET_NEEDS_NEW_EDGE',[dict(hb_fall=True),dict(start=True,start_rise=True),dict(start=True,reset=True,reset_rise=True),dict(start=True)],(1,0,1))
scenario('RESET_HELD_ALWAYS_CLEARS_RUN',[dict(hb_fall=True),dict(reset=True,reset_rise=True),dict(reset=True,start=True,start_rise=True)],(1,0,1))
scenario('FAULT_RECOVERY_HELD_START_NO_RESTART',[dict(hb_fall=True),dict(reset=True,reset_rise=True),dict(start=True,start_rise=True),dict(safe=False,start=True),dict(start=True,hb_fall=True),dict(start=True)],(0,0,1))
scenario('HELD_RESET_ACROSS_FAULT_NEEDS_NEW_EDGE',[dict(hb_fall=True),dict(reset=True,reset_rise=True),dict(safe=False,reset=True),dict(reset=True,hb_fall=True),dict(reset=True,start=True,start_rise=True)],(0,0,1))
for state in itertools.product([0,1],repeat=3):
 for levels in itertools.product([0,1],repeat=3):
  ck('ANY_STATE_FAULT_'+str(state)+str(levels),step(state,False,*levels)==(0,0,0))
  ck('ANY_STATE_HELD_RESET_'+str(state)+str(levels),step(state,True,True,levels[0],levels[1],bool(levels[2]),True,True)[1]==0)
# Calculated component ranges (not circuit measurements).
capmin=120*(1-.01)*(1-.003);capmax=120*(1+.01)*(1+.003)
wdmin=.905*(77.4*capmin/1000+55)
wdmax=1.095*(77.4*(capmax+5)/1000+55)
ck('CAP_MIN_GT_DATASHEET_100PF',capmin>=100,capmin)
ck('WATCHDOG_CANDIDATE_LT100MS',wdmax<100,wdmax)
ck('HEARTBEAT_MAX_INTERVAL30MS_LT_MIN_TIMEOUT',30<wdmin)
rpmin=10000*.98;rpmax=10000*1.02
low_current=3.366/rpmin+8e-6
highmin=3.234-rpmax*(2e-6+3*.3e-6+5e-6)
ck('FAULT_PULL_CURRENT_LT1MA',low_current<.001,low_current)
ck('FAULT_VOL04_LT_SCHMITT_LOW08',.4<.8)
ck('FAULT_HIGH_GT_SCHMITT_VT_PLUS2V',highmin>2,highmin)
ck('EN_WIRE_OPEN_PULLDOWN',.7e-6*rpmax<.25)
aux_min=5.049/(10000*1.02);aux_max=5.151/(10000*.98)
ck('AUX_WETTING_VOLTAGE_MIN',5.049>=5)
ck('AUX_WETTING_CURRENT_MIN',aux_min>=.0001)
ck('AUX_RECEIVER_ABS_AND_RECOMMENDED_INPUT',5.151<=5.5)
# 1k series +10k pulldown load ~0.3mA; use full output1mA source rail loss screen, NOT100uA guarantee.
drive_high_requirement=2.4*(1+1020/9800)
ck('LVC_TO_DRIVER_REQUIRED_OUTPUT_BELOW_RAIL',drive_high_requirement<3.234)
rerr=.001+.0025
rtmin=510000*(1-rerr);rtmax=510000*(1+rerr)
rbmin=10000*(1-rerr);rbmax=10000*(1+rerr)
uvmin=(.405*.98)*(1+rtmin/rbmax)-25e-9*rtmax
uvmax=(.405*1.02)*(1+rtmax/rbmin)+25e-9*rtmax
uvrestore=uvmax*1.03
ck('24V_UV_RECOVERY_BELOW_ACCEPTED_MIN',uvrestore<23.04,uvrestore)
calc=dict(kind='DATASHEET_BASED_DESIGN_CALCULATION_NOT_MEASUREMENT',cwd_mpn='C0603C121F5GACTU',cwd_tolerance=.01,temperature_delta_max_C=100,tempco_ppm_per_C=30,capacitance_pf=[capmin,capmax],board_stray_cap_pf_max_requirement=5,watchdog_ms=[wdmin,wdmax],watchdog_formula_scope='TI application equations 1,3,4,9.5% bound; layout leakage/parasitics must be validated',watchdog_reset_hold_ms=[170,230],heartbeat_max_interval_ms=30,heartbeat_min_high_low_us=100,manual_reset_start_min_press_release_ms=100,full_contact_open_100ms_proven=False,remaining_100ms_after_watchdog_ms=100-wdmax,gx11_release_table_max_ms_25C=12,full_chain_ns_timing_not_qualified=True,coil_VDS_nominal_screen=32+55,mosfet_VDS_abs_V=200,mosfet_VGS_abs_V=10,gate_drive_input_min_output_required_V=drive_high_requirement,gate_supply_required_V=[5.049,5.151],RDS_max_25C_VGS4V_ohm=.5,coil_current25C_nom_A=.28,mosfet_conduction_nominal25C_W=.28**2*.5,mosfet_conduction_06A_screen_W=.6**2*.5,coil_current_06A_is_design_screen_not_supplier_bound=True,FAULT_pullup_sink_A=low_current,FAULT_high_min_V=highmin,aux_wetting_current_A=[aux_min,aux_max],rail_24V_UV_threshold_V=[uvmin,uvmax],rail_24V_UV_restore_screen_V=uvrestore,coil_negative_voltage_and_cable_transients='NOT_BOUNDED; no added coil diode; body diode is not a verified reverse-polarity protector',power_on_off_ramps='Only component logic basis; actual sequencing and backfeed need bench observation',manufacturing_release=False,hardware_io_count=0)
dump(E/'STOP_CIRCUIT_CALCULATIONS.json',calc)
dump(E/'STOP_LOGIC_SCENARIOS.json',logic)
ports=[]
direction={'STOP_3V3':'input','STOP_5V':'input','STOP_24V':'input','STOP_GND':'bidirectional','RUN_LATCH':'output','SAFE_N':'output','AUX_CLOSED_3V3':'output','RUN_STATUS_MCU':'output','SAFE_STATUS_MCU':'output','AUX_STATUS_MCU':'output','MCU_VIO':'input'}
for p in j['parts']:
 if p['ref'][0]=='J':
  for a in p['pins']:ports.append(dict(connector=p['ref'],pin=a['number'],label=a['name'],net=a['net'],hierarchical_direction=direction.get(a['net'],'bidirectional'),status=p['scope']))
dump(E/'STOP_PORT_MAP.json',dict(schematic=str(E/'wp09_stop_circuit.kicad_sch'),labels='local labels; parent must attach hierarchical labels at matching terminal wire',ports=ports,legacy_mapping=[dict(wire_id='K1_COILP',new_local='J104.1',K1='X1(+)',upstream_input='J101.3',source_unbound=True),dict(wire_id='K1_COILR',new_local='J104.2',K1='X2(-)',upstream_return='J101.4',note='Switched drain return, not continuous ground'),dict(wire_id='K1_FB1',new_local='J105.2',K1='T1',net='AUX_RETURN'),dict(wire_id='K1_FB2',new_local='J105.1',K1='T2',net='STOP_5V',note='Distinct feed and return names; old shared signal name alone did not prove electrical short')]))
status=dict(status='PIN_LEVEL_CIRCUIT_CANDIDATE_GENERATED_AND_NETLIST_VERIFIED__EXTERNAL_SUPPLY_AND_FEEDBACK_MONITOR_OPEN',checks=len(checks),passed=sum(x['passed'] for x in checks),all_checks_pass=all(x['passed'] for x in checks),components=len(parts),connected_pins=len(expected),nets=len(set(expected.values())),erc_errors=len(v),erc_errors_expected_unbound_supplies=3,erc_PASS=False,PCB_layout_complete=False,physical_tests_executed=0,full_stop_chain_100ms_closed=False,full_electrical_design_complete=False,checks_detail=checks,input_sha256={str(p):sha(p) for p in [E/'wp09_stop_circuit.kicad_sch',E/'STOP_CIRCUIT_CONNECTIVITY.json',E/'wp09_stop_circuit.net.xml',E/'STOP_ERC.json']})
dump(C/'results/STOP_CIRCUIT_VERIFICATION.json',status)
old=C.parent/'reuse_closure/sources/power/CONTACTOR_OFFICIAL_WEB_RETRIEVAL.json'
dump(C/'results/STOP_CIRCUIT_GX11_ERRATUM.json',dict(correction='12 ms is table MAX, not TYP; confined to COIL RATINGS at25C',official_url='https://www.sensata.com/sites/default/files/a/sensata-gigavac-gx11-series-open-contactors-datasheet.pdf',page=2,table='COIL RATINGS at 25C',column='C (24 V single coil)',quoted_row='Release Time, Max (ms)',cell_ms=12,source_text_receipt=str(old),source_text_sha256=sha(old),original_pdf_download='HTTP403',original_pdf_sha256=None,visual_pdf_table_verified=False,full_chain_stop_release=False,parent_files_modified=False))
print(json.dumps({k:status[k] for k in ['status','checks','passed','components','connected_pins','nets','erc_errors']}));print(json.dumps(calc))
