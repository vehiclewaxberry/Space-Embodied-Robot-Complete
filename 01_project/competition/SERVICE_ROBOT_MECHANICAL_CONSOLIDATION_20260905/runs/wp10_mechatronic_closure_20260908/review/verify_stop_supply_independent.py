"""Independent read-only net/source/interval review; no author validator execution."""
from pathlib import Path
import csv, json, hashlib, xml.etree.ElementTree as ET, itertools, math, datetime
from pypdf import PdfReader

R=Path(__file__).resolve().parent;D=R.parent;E=D/'electrical'
C=D.parent/'wp09_interfaces_20260907_1525'/'system_completion'
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
checks=[]
def ck(n,passed,detail=None):checks.append(dict(id=n,passed=bool(passed),detail=detail))
def close(a,b):return math.isclose(a,b,rel_tol=1e-11,abs_tol=1e-12)
new=load(E/'STOP_CIRCUIT_CONNECTIVITY.json');parts={x['ref']:x for x in new['parts']}
parent=load(C/'electrical_delta/STOP_CIRCUIT_CONNECTIVITY.json');old={x['ref']:x for x in parent['parts']}
calc=load(E/'STOP_SUPPLY_CALCULATIONS.json')
xml=ET.parse(E/'wp09_stop_circuit.net.xml').getroot()
nodes={f"{x.attrib['ref']}.{x.attrib['pin']}":n.attrib['name'].lstrip('/') for n in xml.findall('./nets/net') for x in n.findall('node')}
expected={f"{p['ref']}.{x['number']}":x['net'] for p in parts.values() for x in p['pins']}
for ep,net in expected.items():ck('EXPORTED_NET/'+ep,nodes.get(ep)==net if net is not None else nodes.get(ep,'').startswith('unconnected-'))
ck('EXPORTED_ENDPOINT_SET',set(nodes)==set(expected))
ck('76_ACTUAL_COMPONENTS',len(parts)==len(xml.findall('./components/comp'))==76)
ck('234_CONNECTED_PINS_40_NETS',sum(v is not None for v in expected.values())==234 and len({v for v in expected.values() if v is not None})==40)
for p in xml.findall('./components/comp'):
    part=parts[p.attrib['ref']]
    ck('XML_VALUE/'+p.attrib['ref'],p.findtext('value')==part['mpn']+' / '+part['value'])
def net(ep):return nodes[ep]
connections=[('U120.1','U121.1','J101.3','J104.1','J105.1'),('U120.2','U121.2','J101.4','U112.2','U112.4'),
             ('U120.3','U101.1','U102.6','U103.6','U104.6','R124.1','J101.1'),
             ('U121.3','U112.3','U119.5','U103.5','R125.1','J101.2'),
             ('U112.1','R111.2','R112.1'),('U119.4','R111.1'),('J105.2','R115.1'),
             ('R115.2','R130.1','R116.1'),('R130.2','R112.2','J101.4'),('R116.2','U113.2')]
for group in connections:ck('PIN_PATH/'+'/'.join(group),len({net(x) for x in group})==1)
ck('AUX_CONTACT_NOT_BYPASSED',net('J105.1')!=net('J105.2'))
ck('COIL_POS_NEG_DISTINCT',net('J104.1')!=net('J104.2'))
ck('MCU_STATUS_SEPARATE_RAIL',net('J102.8') not in {net('U120.3'),net('U121.3')})
for ref in ['U116','U117','U118']:ck('OPEN_DRAIN_STATUS/'+ref,parts[ref]['mpn']=='SN74LVC1G07DBVR' and net(ref+'.5')==net('U120.3'))
changed_pin_refs={'U112','R115','R116','J105'}
for ref,p in old.items():
    if ref not in changed_pin_refs:
        a={q['number']:q['net'] for q in p['pins']};b={q['number']:q['net'] for q in parts[ref]['pins']}
        ck('RETAINED_CORE_PIN_NET/'+ref,a==b)
for ref in ['U101','U102','U103','U104','U105','U106','U107','U108','U109','U110','U111','U114','U115','C101']:
    ck('RETAINED_CORE_MPN/'+ref,parts[ref]['mpn']==old[ref]['mpn'])
ck('WATCHDOG_EXACT120PF',parts['C101']['mpn']=='C0603C121F5GACTU')
ck('TC4420_NONINVERTING_TO220_PINMAP',parts['U112']['mpn']=='TC4420CAT' and {q['number']:q['name'] for q in parts['U112']['pins']}=={'1':'INPUT','2':'GND','3':'VDD_TAB','4':'GND','5':'OUTPUT'})
ck('NO_ARTIFICIAL_POWER_FLAGS',all('PWR_FLAG' not in p['mpn'] for p in parts.values()))
ck('NO_EXTERNAL_COIL_DIODE',not any(k.startswith('D') for k in parts))
erc=load(E/'STOP_ERC.json');errors=[x for s in erc['sheets'] for x in s['violations']]
ck('TWO_EXTERNAL_SUPPLY_ERC_ERRORS',len(errors)==2 and all(x['type']=='power_pin_not_driven' for x in errors))

# Independently stack nominal-output fractional limits, with no probability assignment.
error=.02+.002+.004+25*.00015
rails={'STOP_3V3':[3.3*(1-error),3.3*(1+error)],'STOP_5V':[5*(1-error),5*(1+error)]}
for r,key in [('STOP_3V3','rail3V3_V'),('STOP_5V','rail5V_V')]:ck('RAIL_INTERVAL/'+r,all(close(a,b) for a,b in zip(rails[r],calc[key])))
restore={'G33':3.07*(1+.0125)*(1+.025),'G50':4.65*(1+.015)*(1+.025)}
for k,v in restore.items():ck('TPS3808_RESTORE/'+k,close(v,calc['supervisor_restore_max_V'][k]))
ck('LIMITED_GSE_AMBIENT',calc['module_ambient_C']==[0,50])
for x in calc['consumers']:ck('SUPPLY_WINDOW/'+x['ref'],x['static_V'][0]>=x['recommended_supply_V'][0] and x['static_V'][1]<=x['recommended_supply_V'][1])

preload=[]
for ref,nom,rail in [('R124',24,'STOP_3V3'),('R125',39,'STOP_5V')]:
    lo,hi=rails[rail]
    # Initial tolerance × film-temperature coefficient; separate qualified-test drifts.
    rlo=nom*.95*(1-225*.00025)-.01*nom-.05-.05*nom-.1
    rhi=nom*1.05*(1+225*.00025)+.01*nom+.05+.05*nom+.1
    imin=lo/rhi;pmax=hi*hi/rlo
    actual=next(x for x in calc['preloads'] if x['ref']==ref)
    ck('PRELOAD_NOMINAL/'+ref,actual['nominal_ohm']==nom)
    ck('PRELOAD_FILM_TEMP_DRIFT/'+ref,all(close(a,b) for a,b in zip([rlo,rhi],actual['resistance_ohm'])))
    ck('PRELOAD_LOAD_REGULATION_DOMAIN/'+ref,imin>=.1 and close(imin,actual['current_A'][0]))
    ck('PRELOAD_POWER/'+ref,pmax<1 and close(pmax,actual['dissipation_W_max']))
    ck('PRELOAD_NOT_THERMALLY_QUALIFIED/'+ref,actual['part_body_temperature_and_PCB_clearance_qualified'] is False and actual['arbitrary_lifetime_guarantee'] is False)
    preload.append(dict(ref=ref,minimum_current_A=imin,maximum_dissipation_W=pmax,
        reference_hotspot_C=50+75*pmax,reference_not_layout_thermal_guarantee=True))

# TC4420 ±10uA applies throughout selected C temperature range while VDD >=4.5V.
vhigh=(3.8-.000010*1020)/(1+1020/9800)
vlow=.44+.000010*1020
ck('TC4420_HIGH',vhigh>2.4 and close(vhigh,calc['driver']['AHCT_to_driver_high_min_V']))
ck('TC4420_LOW',vlow<.8 and close(vlow,calc['driver']['AHCT_to_driver_low_max_V']))
ck('AHCT_AND_TC_SAME_SUPPLY',net('U119.5')==net('U112.3'))
ck('AHCT_NO_OUTPUT_IOFF_INVENTED',calc['driver']['AHCT_output_Ioff_claim'] is False)
ck('TC4420_BROWNOUT_NOT_GUARANTEED',calc['driver']['driver_UVLO_guarantee'] is False)
ck('LOADED_DRIVER_OUTPUT_NOT_CERTIFIED',calc['driver']['loaded_driver_output_at5V_proven'] is False)

def aux(leak):
    values=[]
    for v,rt,rb,rs,ii in itertools.product([23.04,24.96],[22000*.98,22000*1.02],[3900*.98,3900*1.02],[1000*.98,1000*1.02],[-leak,leak]):
        vd=(v/rt-ii)/(1/rt+1/rb);vi=vd-ii*rs
        values.append(dict(input_V=vi,contact_A=(v-vd)/rt,top_W=(v-vd)**2/rt,bottom_W=vd*vd/rb))
    return dict(input_V=[min(x['input_V'] for x in values),max(x['input_V'] for x in values)],
        contact_A=[min(x['contact_A'] for x in values),max(x['contact_A'] for x in values)],
        open_input_V_max=leak*(3900*1.02+1000*1.02),corners=len(values))
aux_on,aux_off=aux(5e-6),aux(10e-6)
ck('AUX_POWERED_SENSE_INTERVAL',all(close(a,b) for a,b in zip(aux_on['input_V'],calc['aux']['sense_closed_V'])))
ck('AUX_WETTING_0V1MA',aux_on['contact_A'][0]>.0001 and 23.04>5)
ck('AUX_OPEN_MAX',close(aux_on['open_input_V_max'],calc['aux']['sense_open_max_V']))
ck('AUX_POWER_OFF_10UA_INPUT_VOLTAGE',aux_off['input_V'][1]<5.5 and aux_off['open_input_V_max']<.8)

# Independent discrete event fixture tied to retained FF/clear nets. Not analog transient proof.
def event(state, safe=True, heartbeat_falling=False, reset_rising=False, reset_held=False,start_rising=False):
    armed,run,hb=state
    if not safe:return (False,False,False)
    old_armed,old_hb=armed,hb
    if heartbeat_falling:hb=True
    if reset_rising:armed=old_hb
    if reset_held:run=False
    elif start_rising:run=old_armed
    return (armed,run,hb)
s=(False,False,False)
ck('NO_START_BEFORE_HEARTBEAT_RESET',event(s,start_rising=True)[1] is False)
s=event(s,heartbeat_falling=True);s=event(s,reset_rising=True,reset_held=True);s=event(s,start_rising=True)
ck('EXPLICIT_HB_RESET_START_CAN_LATCH',s==(True,True,True))
ck('RESET_HELD_PREVENTS_RUN',event(s,reset_held=True,start_rising=True)[1] is False)
s=event(s,safe=False)
ck('FAULT_CLEARS_BOTH_LATCHES_AND_HB',s==(False,False,False))
ck('FAULT_RELEASE_NO_AUTORESTART',event(s)==s)
ck('FAULT_RELEASE_START_ALONE_NO_RUN',event(s,start_rising=True)[1] is False)

# Only primary source documents support numerical device limits.
bindings=[]
for item in load(E/'sources/SOURCE_LOCK.json'):
    p=Path(item['path']);p=p if p.is_absolute() else E/'sources'/p
    ck('SOURCE_LOCK/'+item['id'],sha(p)==item['sha256']);bindings.append(dict(path=str(p),sha256=sha(p),source_id=item['id'],url=item.get('url')))
sourcepages={
    'tc4420':(E/'sources/tc4420.pdf',[3,7,18]),
    'vishay_pr':(E/'sources/vishay_pr.pdf',[0,1,2]),
    'tps3808':(C/'electrical_delta/sources/tps3808.pdf',[5]),
    'sn74ahct1g125':(C/'electrical_delta/sources/sn74ahct1g125.pdf',[3,4]),
    'sn74lvc1g17':(C/'electrical_delta/sources/sn74lvc1g17.pdf',[5]),
    'sn74lvc1g07':(C/'electrical_delta/sources/sn74lvc1g07.pdf',[5])}
for name,(p,pages) in sourcepages.items():
    reader=PdfReader(p)
    text='\n'.join(reader.pages[i].extract_text() for i in pages)
    ck('PRIMARY_SOURCE_READ/'+name,len(text)>400)
    bindings.append(dict(source_id=name,path=str(p),sha256=sha(p),pages_1based=[i+1 for i in pages]))

schmitt=calc.get('schmitt_threshold_guarantee',{}).get('status')
ck('SCHMITT_2V_NOT_MISSTATED',schmitt=='CONTINUOUS_VCC_BOUNDS_NOT_ESTABLISHED' and calc['schmitt_threshold_guarantee']['ordinary_LVC_VIH2V_is_not_substitute'] is True)
ck('AUX_OFF_STATE_LEAKAGE_DECLARED',calc['aux_poweroff_screen']['Ioff_max_A']==1e-5 and calc['aux_poweroff_screen']['valid_output_when_VCC0'] is False)
ck('CAT_OPERATING_TEMPERATURE_COVERS_GSE',calc['module_ambient_C'][0]>=0 and calc['module_ambient_C'][1]<=70)
findings=[
 dict(id='R_PRELOAD_SELF_HEAT',severity='RESOLVED',finding='Initial ambient-only TCR analysis omitted self heating. Candidate changed 27/43ohm to24/39ohm and includes full film-temperature envelope plus solder/endurance drift.',current_preload=preload),
 dict(id='R_SCHMITT_THRESHOLD',severity='DECLARED_LIMITATION' if schmitt else 'OPEN_DOCUMENTATION_CORRECTION',finding='SN74LVC1G17 SCES351Y uses VT+ points (3V:1.92V,4.5V:2.74V,5.5V:3.33V), not a universal2.0V VIH. Continuous3.201825..3.398175V threshold guarantee requires binding or explicit conditional screen.',author_threshold_status=schmitt),
 dict(id='R_RIPPLE_RECOVERY',severity='OPEN_ENGINEERING_INPUT',finding='Only13.506mV/15.741mV DC recovery margins. Typical ripple is not maximum. Ripple, load steps and loss-of-power sequences remain unqualified.'),
 dict(id='R_POWER_DOMAIN',severity='SCOPED_TOPOLOGY_PASS_DYNAMIC_OPEN',finding='AHCT andTC4420 share5V; AHCT input leakage atVCC0 is bounded. MCU status uses Ioff open-drain buffers. Brownout transitions below recommendedVDD and external rail faults are not proven.'),
 dict(id='R_THERMAL_LIFE',severity='OPEN_LAYOUT_QUALIFICATION',finding='PR02 power and Rth screens are not PCB hotspot proof; film/lead/board temperature and life profile must meet documented limits.1000h endurance screen is not arbitrary lifetime assurance.'),
 dict(id='R_ERC',severity='EXPECTED_BOUNDARY',finding='Standalone2 undriven power-pin errors are external protected24V and return boundaries; actual modules drive3.3V/5V. Top-level integration may legitimately remove them, without certifying functional or safety completeness.'),
 dict(id='R_NO_RESTART',severity='RETAINED_DIGITAL_LOGIC_SCOPE',finding='Watchdog120pF and reset/start/heartbeat FF graph are unchanged and actual exported netlist-bound. Digital event fixtures pass; no analog brownout or100ms full-chain proof.'),
]
inputs=[E/x for x in ['STOP_CIRCUIT_CONNECTIVITY.json','STOP_SUPPLY_CALCULATIONS.json','STOP_PORT_MAP.json','STOP_BOM.csv','wp09_stop_circuit.net.xml','wp09_stop_circuit.kicad_sch','STOP_ERC.json']]
out=dict(status='PASS_WITH_DECLARED_STATIC_SCOPE__MECHATRONIC_STOP_CHAIN_NOT_COMPLETE' if all(x['passed'] for x in checks) else 'FAIL_INDEPENDENT_CHECK',
    generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),checks_total=len(checks),checks_passed=sum(x['passed'] for x in checks),
    failed_checks=[x for x in checks if not x['passed']],checks=checks,findings=findings,
    independent_calculations=dict(rails_V=rails,restore_threshold_max_V=restore,preload=preload,driver_high_min_V=vhigh,driver_low_max_V=vlow,aux_powered=aux_on,aux_poweroff=aux_off),
    source_bindings=bindings,input_sha256={str(p):sha(p) for p in inputs},reviewer_script_sha256=sha(Path(__file__)),
    parent_core_graph_retained=True,author_validator_executed=False,physical_tests=0,CAD_or_COM_executed=False,
    regulated_rails_dynamic_qualification=False,whole_stop_chain100ms=False,PCB_complete=False,full_electrical_design_complete=False,
    scientific_GATE_credit=False,manufacturing_release=False)
(R/'STOP_SUPPLY_INDEPENDENT_REVIEW.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:out[k] for k in ['status','checks_total','checks_passed','failed_checks']}))
print(json.dumps({'aux_on':aux_on,'aux_off':aux_off,'schmitt_status':schmitt,'findings':[x['id']+':'+x['severity'] for x in findings]}))
raise SystemExit(0 if all(x['passed'] for x in checks) else 1)
