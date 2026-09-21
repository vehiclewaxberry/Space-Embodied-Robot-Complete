"""Offline design generator and independent-rule negative controls. NO hardware API."""
from pathlib import Path
import json,csv,hashlib,math,copy,html,itertools
F=Path(__file__).resolve().parents[1];R=F.parent
def write(p,j):Path(p).write_text(json.dumps(j,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def csvout(p,rows):
 with Path(p).open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
sources={
 'DM_PUBLIC':dict(url='https://github.com/Seeed-Projects/reBot-DevArm',revision=json.loads((F/'research/rebot_repo_tree.json').read_text())['sha'],scope='Public DM V4 BOM; shipping identity not confirmed'),
 'DM_2023':dict(url='https://files.seeedstudio.com/products/Damiao/DM-J4310-en.pdf',revision='2023-11-16 V1.0 for DM-J4310-2EC V1.1',pages=[4,9,13,14],scope='Legacy interface reference only; NOT V4 pin certification'),
 'RSP':dict(url='https://www.meanwell.com/Upload/PDF/RSP-500/RSP-500-SPEC.PDF',revision='2025-09-26',pages=[2,4,5]),
 'ETA':dict(url='https://www.e-t-a.de/fileadmin/user_upload/Ordnerstruktur/pdf-Data/Products/Elek_Ueberstromschutz/DC/1_de/D_ESX10_DC24V-16A-E_de.pdf',revision='2405',pages=[2,3,4]),
 'REGEN':dict(url='https://docs.odriverobotics.com/v/latest/hardware/regen-clamp-datasheet.html',revision='docs0.6.12 accessed2026-09-07',scope='Ground COTS candidate; DM compatibility untested'),
 'A3200':dict(url='https://gomspace.com/wp-content/uploads/2025/09/gs-ds-nanomind-a3200_1006901-2.0.pdf',revision='DS1006901 2.0 2025-03-26',pages=[7,9,11]),
 'PDU':dict(url='https://gomspace.com/wp-content/uploads/2025/09/gs-ds-nanopower-p60-pdu200-26.pdf',revision='DS1014111 2.6',pages=[6,8]),
 'PDU_OPTION':dict(url='https://gomspace.com/wp-content/uploads/2025/09/gs-osf-nanopower_pdu200_OSF_-_1021197_-_1_-_45_-_1.pdf',revision='OSF1021197 4.5',pages=[1,2]),
 'SFSD':dict(url='https://suddendocs.samtec.com/catalog_english/sfsd.pdf',revision='accessed2026-09-07',pages=[1]),
 'MOLEX':dict(url='https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/salesdrawingpdf/510/51021/510210700_sd.pdf',revision='indexed official family drawing; local download timed out'),
 'LAPP_CABLE':dict(url='https://products.lappgroup.com/online-catalogue/power-and-control-cables/various-applications/pvc-outer-sheath-and-numbered-cores/oelflex-classic-110-lt.html',revision='accessed2026-09-07'),
 'LAPP_GLAND':dict(url='https://products.lappgroup.com/online-catalogue/cable-glands/skintop-cable-glands-plastic-metric/standard/skintop-st-m.html',revision='accessed2026-09-07'),
 'FTDI':dict(url='https://ftdichip.com/products/usb-rs422-we-1800-bt/',datasheet='https://ftdichip.com/wp-content/uploads/2023/07/DS_USB_RS422_CABLES.pdf',revision='v1.4 linked; download403, wire-color table separately indexed in official v1.3',scope='Physical signal definition; internal termination and received cable revision require binding'),
 'BELDEN':dict(url='https://www.belden.com/products/cable/electronic-wire-cable/multi-pair-cable/8723',revision='accessed2026-09-07',scope='Rejected for unmodified R21; official minimum41mm'),
 'FUSE_REJECT':dict(url='https://www.littelfuse.com/assetdocs/fuse-451-and-453-datasheet?assetguid=533cd5cc-956c-4243-867f-6ab5a62f6ba1',revision='GD12/01/25',scope='15A fuse alone rejected; guaranteed opening point30A exceeds source lower current limit22.05A')}
devices={
 'PS1':dict(pn='MEAN WELL RSP-500-24',role='EXTERNAL_GSE',pins={'TB2.4':'+24V','TB2.1':'ARM_RET','TB1.FG':'PE_CHASSIS','CN100.3':'RC-','CN100.4':'RC+'},source='RSP'),
 'Q1':dict(pn='E-T-A ESX10-105-DC24V-16A-E',role='EXTERNAL_GSE_CANDIDATE',pins={'1':'LINE+','2':'LOAD+','11':'GND','13':'SC','14':'SO'},source='ETA'),
 'K1':dict(pn=None,role='OPEN_COMPONENT_SELECTION',pins={'P_IN':'CONTACT_REQUIREMENT','P_OUT':'CONTACT_REQUIREMENT','R_IN':'CONTACT_REQUIREMENT','R_OUT':'CONTACT_REQUIREMENT','COIL+':'CONTROL_REQUIREMENT','COIL-':'CONTROL_REQUIREMENT'},source='DESIGN_REQUIREMENT; two-pole NO, monitored feedback, actual DC break rating >= fault case required'),
 'U1':dict(pn='ODrive Regen Clamp / screw terminals TB005-762-06BE',role='EXTERNAL_GSE_CANDIDATE',pins={p:p for p in ['IN+','IN-','OUT+','OUT-','R+','R-']},source='REGEN'),
 'RB1':dict(pn='ODrive supplied 2ohm 50W resistor; detailed pulse curve pending',role='EXTERNAL_GSE_CANDIDATE',pins={'A':'BRAKE','B':'BRAKE'},source='REGEN'),
 'DM':dict(pn='reBot B601 DM, public V4 BOM',role='GROUND_ROBOT',pins={'VCC_REF':'V4_PIN_UNBOUND','RET_REF':'V4_PIN_UNBOUND','CANH_REF':'V4_PIN_UNBOUND','CANL_REF':'V4_PIN_UNBOUND'},source='DM_PUBLIC'),
 'SEP':dict(pn='Seeed 100045091 XT30 2+2 splitter',role='GROUND_ROBOT',pins={'PWR':'POWER_CAVITY_UNBOUND','RET':'RETURN_CAVITY_UNBOUND','H':'GH_2PIN_CAVITY_UNBOUND','L':'GH_2PIN_CAVITY_UNBOUND'},source='DM_PUBLIC'),
 'CAN':dict(pn='Seeed 100011896 USB-CAN board',role='EXTERNAL_GSE',pins={'USB':'USB_5V_DATA','H':'CAN_CAVITY_UNBOUND','L':'CAN_CAVITY_UNBOUND'},source='DM_PUBLIC'),
 'PDU':dict(pn='P60 PDU200; 8S option; candidate Dock X1; Reg0=12V CH1; Reg1=3.3V CH2; Reg2=5V unused',role='LOW_POWER_CANDIDATE',pins={'TFM.9':'CH2_3V3','TFM.10':'EPS_RET','TFM.1':'CH1_12V','TFM.2':'EPS_RET','TFM.23':'CSP_CANH','TFM.24':'CSP_CANL'},source='PDU;PDU_OPTION'),
 'OBC':dict(pn='NanoMind A3200 200284 / DS2.0',role='LOW_POWER_GROUND_CHECKOUT_CANDIDATE',pins={'P1.1':'EPS_RET','P1.2':'VCC_OBC','P1.3':'USART2_RX','P1.4':'USART2_TX'},source='A3200'),
 'PC':dict(pn='Existing user computer; USB model unspecified',role='EXTERNAL_GSE',pins={'USB_A':'USB_PORT','USB_B':'USB_PORT','USB_CAN':'USB_PORT'},source='HOST_REQUIREMENT'),
}
ftdi_pins={'black':'GND','red':'TXD-','orange':'TXD+','yellow':'RXD+','white':'RXD-','brown':'CTS+','grey':'CTS-','green':'RTS+','blue':'RTS-'}
for ident in ['RS_A','RS_B']:devices[ident]=dict(pn='FTDI USB-RS422-WE-1800-BT',role='EXTERNAL_OWN_PROTOCOL_LOOP_ENDPOINT',pins=ftdi_pins,source='FTDI')
rows=[]
def wire(k,net,fr,fp,to,tp,part,status,source,view='NAMED_TERMINALS; no inferred cavity numbering',length=None):
 rows.append(dict(wire_id=k,net=net,from_device=fr,from_pin=fp,to_device=to,to_pin=tp,wire_or_mate=part,pin_view=view,design_status=status,source=source,cut_length_mm=length,physical_status='NOT_EXECUTED',build_approved=False))
wire('A01','ARM_RAW+', 'PS1','TB2.4','Q1','1','LAPP1120762 2x2.5mm2 core1','PIN_DESIGN; TERMINAL_LUG_SELECTION_OPEN','RSP;ETA')
wire('A02','ARM_Q+','Q1','2','K1','P_IN','LAPP1120762 core1','K1_OPEN','ETA')
wire('A03','ARM_SW+','K1','P_OUT','U1','IN+','LAPP1120762 core1','K1_OPEN','REGEN')
wire('A04','ARM_RET','PS1','TB2.1','K1','R_IN','LAPP1120762 core2','K1_OPEN','RSP')
wire('A05','ARM_RET_SW','K1','R_OUT','U1','IN-','LAPP1120762 core2','K1_OPEN','REGEN')
wire('A06','ARM_RET','PS1','TB2.1','Q1','11','separate rated reference lead, PN pending','REFERENCE_PIN_DESIGN','ETA')
wire('A07','ARM_BUS+','U1','OUT+','SEP','PWR','LAPP1120762 to OEM copper-lug harness; transition terminal pending','V4_SPLITTER_CAVITY_OPEN','DM_PUBLIC;REGEN')
wire('A08','ARM_BUS_RET','U1','OUT-','SEP','RET','LAPP1120762 to OEM copper-lug harness; transition terminal pending','V4_SPLITTER_CAVITY_OPEN','DM_PUBLIC;REGEN')
wire('A09','ARM_BUS+','SEP','PWR','DM','VCC_REF','OEM XT30(2+2) harness retained','V4_PIN_OPEN','DM_PUBLIC;DM_2023')
wire('A10','ARM_BUS_RET','SEP','RET','DM','RET_REF','OEM XT30(2+2) harness retained','V4_PIN_OPEN','DM_PUBLIC;DM_2023')
wire('A11','BRAKE+','U1','R+','RB1','A','supplied resistor leads; fit to terminal to verify','PIN_DESIGN_PULSE_THERMAL_OPEN','REGEN')
wire('A12','BRAKE-','U1','R-','RB1','B','supplied resistor leads','PIN_DESIGN_PULSE_THERMAL_OPEN','REGEN')
wire('C01','DM_CANH','CAN','H','SEP','H','OEM GH1.25 two-pin lead','BOTH_CAVITIES_OPEN','DM_PUBLIC')
wire('C02','DM_CANL','CAN','L','SEP','L','OEM GH1.25 two-pin lead','BOTH_CAVITIES_OPEN','DM_PUBLIC')
wire('C03','DM_CANH','SEP','H','DM','CANH_REF','OEM XT302+2 signal pair','V4_PIN_OPEN','DM_PUBLIC;DM_2023')
wire('C04','DM_CANL','SEP','L','DM','CANL_REF','OEM XT302+2 signal pair','V4_PIN_OPEN','DM_PUBLIC;DM_2023')
mate='Samtec SFSD-15-28-G-10.00-S -> Molex510210400 +500798000; wire/insulation crimp fit pending'
view='PDU TFM key adjacent pin30; identify9/10 from DS2.6 mating-face drawing. OBC P1 header view DS2.0 p7; cable wiring-face is mirrored, match cavity marks'
wire('L01','OBC_3V3','PDU','TFM.9','OBC','P1.2',mate,'FUNCTIONAL_PIN_MAP_COMPLETE; VOLTAGE_PROTECTION_CRIMP_OPEN','PDU;PDU_OPTION;A3200;SFSD;MOLEX',view)
wire('L02','EPS_RET','PDU','TFM.10','OBC','P1.1',mate,'FUNCTIONAL_PIN_MAP_COMPLETE; RETURN_INCLUDED','PDU;A3200;SFSD;MOLEX',view)
for n,(ca,cb) in enumerate([('orange','yellow'),('red','white'),('yellow','orange'),('white','red'),('black','black')],1):
 wire('S0'+str(n),'RS_LOOP_'+str(n),'RS_A',ca,'RS_B',cb,'Two original FTDI wire-ended cables; insulated labelled splice S'+str(n),'SIGNAL_MAP_COMPLETE; RECEIVER_TERMINATION_REVISION_OPEN','FTDI','Color names are wire identity, not connector cavities; self-defined ground test link')
model=dict(schema='WP09_FUNCTIONAL_ELECTRICAL_CANDIDATE',devices=devices,wires=rows,sources=sources,
 circuit_groups={'arm':['A%02d'%i for i in range(1,13)],'dm_can':['C%02d'%i for i in range(1,5)],'obc':['L01','L02'],'rs422_loop':['S%02d'%i for i in range(1,6)]},
 net_rules={'different_networks':['ARM_RET','EPS_RET','USB_REF','PE_CHASSIS','CABLE_SHIELD'],'binding_policy':'No automatic net tie. PE bonds external RSP chassis. No EPS return to ARM return; explicit galvanic-interface/bonding review required. FTDI loop GND is common USB reference of same ground host only; never directly connect to flight RS422.', 'no_parallel_sources':True,'A3200_bottom_power_allowed':False,'A3200_debug_P1_2_only_source':True,'CAN_rate_reference_bit_s':1000000,'USB_serial_reference_bit_s':921600,'CAN_V4_actual_rate':None,'CAN_termination_installed_inventory':None,'extra_terminators_to_fit':None,'default_reset_allows_motion':False},
 no_connect={'OBC.P1.3':'NC until separate3.3V UART adapter matched; do not connect RS422 voltage','OBC.P1.4':'NC','OBC.X1.VCC':'NO powered motherboard in P1 checkout configuration','PDU.TFM.unused':'Other flying leads individually insulated; do not bus all odd pins; TFM5/6 are I2C not power','RS_A.handshake':'RTS outputs isolated separately; CTS unused with hardware flow control disabled','RS_B.handshake':'same','PS1.CN100.RC':'Auxiliary shutdown only; OPEN=ON, not fail-open stop','PS1.TB1.AC':'Qualified AC enclosure design/PE work pending; not wired'},
 completeness={'pin_level_functional_supply_designs':1,'pin_level_signal_mappings':1,'fully_build_released_device_circuits':0,'verified_physical_circuits':0,'native_eda_erc':False,'native_eda_available':False,'unknowns_preserved':True})
write(F/'ecad/CIRCUIT_MODEL.json',model);csvout(F/'ecad/DM_SELECTED_FROM_TO.csv',[r for r in rows if r['wire_id'][0] in 'AC']);csvout(F/'ecad/FUNCTIONAL_FROM_TO.csv',rows)
# Same-source graph netlist: each wire is a physical edge; devices are not automatically internally shorted.
write(F/'ecad/NETLIST.json',dict(schema='PIN_GRAPH_NOT_EDA_ERC',pins={k:v['pins'] for k,v in devices.items()},edges=[dict(id=r['wire_id'],net=r['net'],a=r['from_device']+'.'+r['from_pin'],b=r['to_device']+'.'+r['to_pin'],status=r['design_status']) for r in rows],no_connect=model['no_connect'],circuit_model_sha256=hashlib.sha256((F/'ecad/CIRCUIT_MODEL.json').read_bytes()).hexdigest()))
csvout(F/'ecad/ELECTRICAL_BOM.csv',[dict(ref=k,pn=v['pn'] or 'UNSELECTED',quantity=1,role=v['role'],source=v['source'],ordered=False,qualified=False) for k,v in devices.items()])

# Explicit assumptions, separate from real manufacturer limits. Copper resistances are screening inputs requiring cable certificate.
calc_input=dict(arm=dict(source_nominal_v=24,source_tolerance_fraction=.01,source_rated_a=21,source_current_limit_fraction=[1.05,1.30],psu_nameplate_not_measured=True,series_cable='LAPP1120762',each_conductor_length_m=1.5,cable_length_is_design_allowance_not_cut=True,resistance20_ohm_m=.00806,resistance_source='IEC60228class5 table screening value; purchased cable max certificate not bound',temperature_c=70,alpha_cu_per_c=.00393,contacts_ohm_total=.020,contacts_basis='allocated max for all plugs,lugs and K1; NOT measured',esx_drop_v_at16_typ=.110,regen_drop_max_v=.055,cases_a=[5,10,15,16,18.4],oem_tail_resistance_ohm=None),
 obc=dict(source_nominal_v=3.3,required_source_min_v=3.27,required_source_max_v=3.4,source_limits_verified=False,allowed_v=[3.2,3.4],max_power_w=.9,typ_power_w=.17,each_conductor_m=.254,resistance20_ohm_m=.237,wire_resistance_basis='28AWG screening assumption; Samtec selected assembly resistance certificate missing',temperature_c=75,contacts_total_ohm=.040,contacts_basis='allocated ceiling for both connector interfaces; not manufacturer guarantee',limit_current_request_a=.4,limit_current_verified=False,latch_time_typ_s=.020),
 regen=dict(resistor_ohm=2,resistor_continuous_w=50,activation_above_input_max_v=2.5,onboard_capacitance_f=.0008,brake_free_air_limit_a=20,brake_peak_a=80,peak_time_limit_s=3,required_actual_energy_and_pulse_curve=False),
 electrical_assurance='Calculations are conditional screens; no unmeasured maxima silently treated as guarantees')
write(F/'inputs/ELECTRICAL_CASES.json',calc_input)
a=calc_input['arm'];rwire=2*a['each_conductor_length_m']*a['resistance20_ohm_m']*(1+a['alpha_cu_per_c']*(a['temperature_c']-20));rr=rwire+a['contacts_ohm_total']+a['esx_drop_v_at16_typ']/16
arm_cases=[dict(current_a=i,R_loop_ohm=rr,wire_ohm=rwire,v_after_selected_cable_and_devices=24*.99-i*rr-.055,loss_w=i*i*rr+i*.055,OEM_tail_included=False,assurance='CONDITIONAL; not worst-case certified') for i in a['cases_a']]
o=calc_input['obc'];ro=2*o['each_conductor_m']*o['resistance20_ohm_m']*(1+.00393*(o['temperature_c']-20))+o['contacts_total_ohm'];obc_cases=[]
for vs,p in itertools.product([3.2,3.27,3.3],[.17,.9]):
 disc=vs*vs-4*ro*p;vl=(vs+math.sqrt(disc))/2 if disc>=0 else None
 obc_cases.append(dict(source_v=vs,power_w=p,loop_ohm=ro,load_v=vl,current_a=p/vl if vl else None,loss_w=p*p/vl**2*ro if vl else None,voltage_range_met=bool(vl and 3.2<=vl<=3.4)))
regen=[]
for name,E,t,period in [('screen_small',10,.5,10),('screen_fast',50,.2,5),('screen_excess_peak',200,.2,5),('screen_excess_average',100,1,1)]:
 p=E/t;v=24*1.01+2.5;pres=v*v/2;regen.append(dict(case=name,assumed_energy_j=E,duration_s=t,repeat_s=period,required_power_w=p,resistor_on_power_w=pres,brake_current_a=v/2,average_w=E/period,arithmetic_feasible=p<=pres and E/period<=50 and v/2<=20,actual_resistor_pulse_rating_verified=False,actual_DM_bus_transient_rating_verified=False))
for q in regen:
 q['resistor_on_power_interval_w']=[(24*.99+.5)**2/2,(24*1.01+2.5)**2/2]
 q['arithmetic_feasible']=q['required_power_w']<=q['resistor_on_power_interval_w'][0] and q['average_w']<=50 and q['brake_current_a']<=20
 q['interval_note']='Uses min deactivation offset0.5V and max activation2.5V; source nominal24V+/-1%. Excludes resistor tolerance, ripple, dynamic overshoot, hot ratings and dropout. No guaranteed thermal absorption credit.'
result=dict(status='OFFLINE_ELECTRICAL_DESIGN_SCREENS_COMPLETED_WITH_OPEN_INPUTS',arm=arm_cases,obc=obc_cases,obc_required_source_min_at_0_9W_v=3.2+ro*.9/3.2,protection=dict(selected='ESX10-105-DC24V-16A-E standalone mounting at25C',typical_limit_a=18.4,typical_trip_s=.1,typical_I2t_a2s=18.4**2*.1,typical_fault_cable_j=18.4**2*rwire*.1,psu_lower_limit_a=22.05,typical_selectivity_margin_a=22.05-18.4,not_guaranteed=True,required='Limit tolerance, time maximum, internal25A element let-through, cable/contact withstand and installed grouping/temperature',rejected_fuse_only=dict(fuse_a=15,guaranteed_200percent_point_a=30,source_lower_limit_a=22.05,assured_opening=False)),regen=regen,capacitor_storage_between24_and26_74_j=.5*.0008*(26.74**2-24**2),bpX_limit=dict(recommended_min_v=23.6,max_discharge_a=6,ideal_w=141.6,arm_reference_supply_w=360,arm_orbit_power_closed=False,pdu_bpx_voltage_intersection_v=[24,32],intersection_includes_Dock_guarantee=False,pdu_efficiency_at8S_verified=False),cut_lengths_approved=False)

# Semantic fault injection into independently specified expected connections and system properties.
def validate(x):
 errors=[];lookup={r['wire_id']:r for r in x['wires']}
 for r in x['wires']:
  for side in ['from','to']:
   d=r[side+'_device'];p=r[side+'_pin']
   if d not in x['devices']:errors.append('MISSING_DEVICE_'+d)
   elif p not in x['devices'][d]['pins']:errors.append('UNDECLARED_PIN_'+d+'.'+p)
  domains={x['devices'].get(r[s+'_device'],{}).get('role','') for s in ['from','to']}
  if 'GROUND_ROBOT' in domains and any('LOW_POWER' in d for d in domains):errors.append('UNREVIEWED_ARM_EPS_NET_TIE')
 def reaches(channel,disabled=None):
  graph={}
  def edge(a,b):graph.setdefault(a,set()).add(b);graph.setdefault(b,set()).add(a)
  for r in x['wires']:
   if (channel=='positive' and r['net'].startswith('ARM') and r['net'].endswith('+')) or (channel=='return' and r['net'].startswith('ARM') and 'RET' in r['net']):edge(r['from_device']+'.'+r['from_pin'],r['to_device']+'.'+r['to_pin'])
  internal={'Q1':('1','2'),'K1':('P_IN','P_OUT'),'U1':('IN+','OUT+'),'SEP':('PWR','PWR')} if channel=='positive' else {'K1':('R_IN','R_OUT'),'U1':('IN-','OUT-'),'SEP':('RET','RET')}
  for d,(a,b) in internal.items():
   if d in x['devices'] and d!=disabled:edge(d+'.'+a,d+'.'+b)
  start='PS1.TB2.4' if channel=='positive' else 'PS1.TB2.1';target='DM.VCC_REF' if channel=='positive' else 'DM.RET_REF';seen={start};queue=[start]
  while queue:
   node=queue.pop()
   for n in graph.get(node,set())-seen:seen.add(n);queue.append(n)
  return target in seen
 if not reaches('positive'):errors.append('ARM_FEED_PATH_OPEN')
 if not reaches('return'):errors.append('ARM_RETURN_PATH_OPEN')
 if reaches('positive','K1'):errors.append('K1_BYPASS_PATH')
 if reaches('positive','Q1'):errors.append('Q1_BYPASS_PATH')
 for ident,ends in {'L01':('PDU','TFM.9','OBC','P1.2'),'L02':('PDU','TFM.10','OBC','P1.1'),'S01':('RS_A','orange','RS_B','yellow'),'S02':('RS_A','red','RS_B','white'),'S03':('RS_A','yellow','RS_B','orange'),'S04':('RS_A','white','RS_B','red'),'S05':('RS_A','black','RS_B','black')}.items():
  q=lookup.get(ident)
  if not q:errors.append('MISSING_'+ident)
  elif tuple(q[k] for k in ['from_device','from_pin','to_device','to_pin'])!=ends:errors.append('PIN_OR_POLARITY_'+ident)
 z=x.get('review_case',{})
 if z.get('current_a',.3)>z.get('weakest_contact_rating_a',1):errors.append('CONNECTOR_OVERLOAD')
 if not z.get('protection_present',True):errors.append('MISSING_PROTECTION')
 if z.get('fuse_only',False) and z.get('source_fault_min_a',22.05)<z.get('fuse_guaranteed_open_a',30):errors.append('PROTECTION_NOT_COORDINATED')
 if z.get('can_terminators',2)!=2:errors.append('CAN_TERMINATION_COUNT')
 if z.get('rc_open_output_on',True) is not True:errors.append('RC_OPEN_IS_ON')
 if x['net_rules']['A3200_bottom_power_allowed']:errors.append('DUAL_OBC_SUPPLY')
 if z.get('physical_permission_inferred',False):errors.append('NO_PHYSICAL_CREDIT')
 return errors
negative=[]
def test(name,mut,expect):
 x=copy.deepcopy(model);mut(x);errors=validate(x);negative.append(dict(name=name,errors=errors,expected=expect,detected=expect in errors));assert expect in errors
assert validate(model)==[]
test('mirror_P1_view',lambda x:x['wires'].__setitem__(16,{**x['wires'][16],'to_pin':'P1.3'}),'PIN_OR_POLARITY_L01')
test('missing_return',lambda x:x.__setitem__('wires',[r for r in x['wires'] if r['wire_id']!='L02']),'MISSING_L02')
test('RS422_polarity_reverse',lambda x:next(r for r in x['wires'] if r['wire_id']=='S01').update(to_pin='white'),'PIN_OR_POLARITY_S01')
for name,kw,expected in [('over_contact',{'current_a':2,'weakest_contact_rating_a':1},'CONNECTOR_OVERLOAD'),('no_protection',{'protection_present':False},'MISSING_PROTECTION'),('15A_fuse_not_assured',{'fuse_only':True},'PROTECTION_NOT_COORDINATED'),('third_CAN_termination',{'can_terminators':3},'CAN_TERMINATION_COUNT'),('RC_wire_break_claims_off',{'rc_open_output_on':False},'RC_OPEN_IS_ON'),('simulation_is_not_physical',{'physical_permission_inferred':True},'NO_PHYSICAL_CREDIT')]:test(name,lambda x,k=kw:x.update(review_case=k),expected)
test('A3200_double_feed',lambda x:x['net_rules'].update(A3200_bottom_power_allowed=True),'DUAL_OBC_SUPPLY')
test('remove_real_Q1_device',lambda x:x['devices'].pop('Q1'),'MISSING_DEVICE_Q1')
test('delete_real_arm_return',lambda x:x.__setitem__('wires',[r for r in x['wires'] if r['wire_id']!='A10']),'ARM_RETURN_PATH_OPEN')
test('wire_bypasses_K1',lambda x:x['wires'].append(dict(wire_id='FAULT',net='ARM_BYPASS+',from_device='Q1',from_pin='2',to_device='U1',to_pin='IN+')),'K1_BYPASS_PATH')
test('wire_bypasses_Q1',lambda x:x['wires'].append(dict(wire_id='FAULT',net='ARM_BYPASS+',from_device='PS1',from_pin='TB2.4',to_device='K1',to_pin='P_IN')),'Q1_BYPASS_PATH')
test('wrong_ARM_EPS_tie',lambda x:x['wires'].append(dict(wire_id='FAULT',net='EPS_RET',from_device='DM',from_pin='RET_REF',to_device='OBC',to_pin='P1.1')),'UNREVIEWED_ARM_EPS_NET_TIE')
result['protection']['psu_lower_limit_a_basis']='22.05A = 105%*504W/24V at rated output reference ONLY; not a guaranteed source short-circuit minimum at all AC, load voltage or temperature states'
result['protection']['guaranteed_source_fault_current_a']=None
result['negative_controls']=negative;result['negative_controls_passed']=all(x['detected'] for x in negative);result['nominal_schema_checks_passed']=True;result['native_eda_erc']=False;result['hardware_tests_executed']=0
write(F/'results/ELECTRICAL_CALCULATIONS.json',result)

# Pin-to-pin wiring schematics rendered from the exact netlist rows, not independently hand-transcribed.
for group,title in [('arm','地面机械臂供电：端子与能量回路'),('obc','低功率支路：PDU CH2 → A3200 P1'),('dm_can','B601 DM CAN：待绑定的原厂接口'),('rs422_loop','RS-422：两只 FTDI 的自有协议地面回环')]:
 wr=[r for r in rows if r['wire_id'] in model['circuit_groups'][group]];height=180+len(wr)*96
 svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1380" height="'+str(height)+'" viewBox="0 0 1380 '+str(height)+'"><rect width="100%" height="100%" fill="#f3f6fa"/><style>text{font-family:Microsoft YaHei,Arial;fill:#163047}.small{font-size:13px}.pin{font-size:18px;font-weight:600}.note{font-size:14px;fill:#845212}</style>',f'<text x="36" y="44" font-size="27" font-weight="700">{title}</text>','<text x="36" y="76" font-size="16">候选接线原理图 · 与 NETLIST.json 同源 · 未获接线/通电放行 · 未运行原生 EDA/ERC</text>']
 for i,r in enumerate(wr):
  y=118+i*96;esc=html.escape;col='#bd6430' if 'OPEN' in r['design_status'] else '#19827b';style='stroke-dasharray="7 4"' if 'OPEN' in r['design_status'] else ''
  svg.extend([f'<rect x="30" y="{y-20}" width="1320" height="85" rx="8" fill="white"/>',f'<text class="small" x="45" y="{y}">{r["wire_id"]}</text>',f'<text class="pin" x="112" y="{y}">{esc(r["from_device"]+"  "+r["from_pin"])}</text>',f'<line x1="415" y1="{y-5}" x2="953" y2="{y-5}" stroke="{col}" stroke-width="3" {style}/>',f'<circle cx="415" cy="{y-5}" r="4" fill="{col}"/><circle cx="953" cy="{y-5}" r="4" fill="{col}"/>',f'<text class="small" x="540" y="{y-12}">{esc(r["net"])}</text>',f'<text class="pin" x="980" y="{y}">{esc(r["to_device"]+"  "+r["to_pin"])}</text>',f'<text class="small" x="112" y="{y+25}">{esc(r["wire_or_mate"])}</text>',f'<text class="note" x="112" y="{y+47}">{esc(r["design_status"])}</text>'])
 svg.extend([f'<text x="36" y="{height-23}" class="small">虚线表示器件/端点未定；逐行表示独立导体。内部连接与网络隔离规则见 CIRCUIT_MODEL.json。</text>','</svg>']);(F/'ecad'/('SCHEMATIC_'+group+'.svg')).write_text('\n'.join(svg),encoding='utf-8')
print(json.dumps(dict(wires=len(rows),negative_controls=len(negative),physical_tests=0,arm15A=arm_cases[2],obc3V27=[x for x in obc_cases if x['source_v']==3.27 and x['power_w']==.9]),ensure_ascii=False))
