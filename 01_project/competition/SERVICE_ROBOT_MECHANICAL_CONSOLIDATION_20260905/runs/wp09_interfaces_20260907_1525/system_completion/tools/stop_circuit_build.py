from pathlib import Path
import json,uuid,csv,collections
C=Path(__file__).resolve().parents[1];E=C/'electrical_delta';E.mkdir(exist_ok=True)
def uid(s):return str(uuid.uuid5(uuid.NAMESPACE_URL,'wp09-stop-20260908:'+s))
def q(s):return json.dumps(str(s),ensure_ascii=False)
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
parts=[]
def part(ref,mpn,pins,source,fp='',scope='SELECTED_CIRCUIT_CANDIDATE'):
 parts.append(dict(ref=ref,mpn=mpn,pins=[dict(number=str(n),name=nm,electrical_type=t,net=net) for n,nm,t,net in pins],source=source,footprint=fp,scope=scope))
def two(ref,val,a,b,source='Passive value/rating requirement; manufacturer code pending',mpn=None):
 part(ref,mpn or val,[(1,val,'passive',a),(2,'','passive',b)],source,'Resistor_SMD:R_0603_1608Metric' if ref[0]=='R' else 'Capacitor_SMD:C_0603_1608Metric', 'VALUE_SELECTED_MPN_PENDING' if mpn is None else 'SELECTED_CIRCUIT_CANDIDATE')
V='STOP_3V3';G='STOP_GND';V5='STOP_5V';V24='STOP_24V'
part('U101','TPS3431SDRBR',[(1,'VDD','power_in',V),(2,'CWD','input','CWD'),(3,'EN','input','EN_STOP'),(4,'GND','power_in',G),(5,'SET1','input',V),(6,'WDI','input','WDI'),(7,'WDO_N','open_collector','FAULT_N_RAW'),(8,'ENOUT','open_collector','FAULT_N_RAW'),(9,'EP','power_in',G)],'TPS3431 Rev A p3/14/17','Package_DFN_QFN:VSON-8-1EP_3x3mm_P0.65mm_EP1.5x2.4mm')
for ref,mpn,sense in [('U102','TPS3808G33DBVR',V),('U103','TPS3808G50DBVR',V5),('U104','TPS3808G01DBVR','SENSE_24V')]:
 part(ref,mpn,[(1,'RESET_N','open_collector','FAULT_N_RAW'),(2,'GND','power_in',G),(3,'MR_N','input',V),(4,'CT_OPEN','input',None),(5,'SENSE','input',sense),(6,'VDD','power_in',V)],'TPS3808 Rev N p4/6/7','Package_TO_SOT_SMD:SOT-23-6')
part('U105','SN74LVC2G17DBVR',[(1,'RESET_A','input','RESET_RC'),(2,'GND','power_in',G),(3,'START_A','input','START_RC'),(4,'START_Y','output','START_EDGE'),(5,'VCC','power_in',V),(6,'RESET_Y','output','RESET_EDGE')],'SN74LVC2G17 Rev N p3/5','Package_TO_SOT_SMD:SOT-23-6')
def single(ref,mpn,a,y):
 part(ref,mpn,[(1,'NC','no_connect',None),(2,'A','input',a),(3,'GND','power_in',G),(4,'Y','output',y),(5,'VCC','power_in',V)],mpn+' official DBV pin table p3','Package_TO_SOT_SMD:SOT-23-5')
single('U106','SN74LVC1G17DBVR','FAULT_N_RAW','SAFE_N')
def ff(ref,c1,d1,k1,q1,qb1,c2,d2,k2,q2,qb2):
 part(ref,'SN74LVC74APWR',[(1,'1CLR_N','input',c1),(2,'1D','input',d1),(3,'1CLK','input',k1),(4,'1PRE_N','input',V),(5,'1Q','output',q1),(6,'1Q_N','output',qb1),(7,'GND','power_in',G),(8,'2Q_N','output',qb2),(9,'2Q','output',q2),(10,'2PRE_N','input',V),(11,'2CLK','input',k2),(12,'2D','input',d2),(13,'2CLR_N','input',c2),(14,'VCC','power_in',V)],'SN74LVC74A Rev W p3/5/8','Package_SO:TSSOP-14_4.4x5mm_P0.65mm')
ff('U107','SAFE_N','HB_SEEN','RESET_EDGE','ARMED',None,'RUN_CLEAR_N','ARMED','START_EDGE','RUN_LATCH',None)
ff('U108','SAFE_N',V,'WDI_FALL','HB_SEEN',None,G,G,G,None,None)
single('U109','SN74LVC1G04DBVR','RESET_EDGE','RESET_N')
single('U110','SN74LVC1G04DBVR','WDI','WDI_FALL')
part('U111','SN74LVC1G08DBVR',[(1,'A','input','SAFE_N'),(2,'B','input','RESET_N'),(3,'GND','power_in',G),(4,'Y','output','RUN_CLEAR_N'),(5,'VCC','power_in',V)],'SN74LVC1G08 Rev AA p3','Package_TO_SOT_SMD:SOT-23-5')
part('U112','UCC27517DBVR',[(1,'VDD','power_in',V5),(2,'GND','power_in',G),(3,'IN+','input','RUN_DRIVE'),(4,'IN-','input',G),(5,'OUT','output','GATE_DRV')],'UCC27517 Rev D p4/5/6/15','Package_TO_SOT_SMD:SOT-23-5')
part('Q101','IRL630PbF',[(1,'G','input','K1_GATE'),(2,'D_TAB','passive','K1_COIL_MINUS'),(3,'S','passive',G)],'Vishay 91303 Rev C p1/2; TO-220AB G-D-S; tab D','Package_TO_SOT_THT:TO-220-3_Vertical')
two('C101','120pF 1% C0G','CWD',G,'KEMET C1003_C0G 2025-02-20 p1/4; TI TIDA-01365 BOM C24','C0603C121F5GACTU')
for r,v,a,b in [('R101','10k 1%',V,'FAULT_N_RAW'),('R102','10k 1%','EN_STOP',G),('R103','47k 1%','WDI',G),('R104','1k 1%','HEARTBEAT_IN','HEARTBEAT_FILTER'),('R105','510k 0.1% 25ppm',V24,'SENSE_24V'),('R106','10k 0.1% 25ppm','SENSE_24V',G),('R107','10k 1%','RESET_CONTACT','RESET_RC'),('R108','10k 1%','START_CONTACT','START_RC'),('R109','100k 1%','RESET_RC',G),('R110','100k 1%','START_RC',G),('R111','1k 1%','RUN_LATCH','RUN_DRIVE'),('R112','10k 1%','RUN_DRIVE',G),('R113','22R 1%','GATE_DRV','K1_GATE'),('R114','10k 1%','K1_GATE',G)]:two(r,v,a,b)
two('C102','1uF X7R 16V 10%','RESET_RC',G);two('C103','1uF X7R 16V 10%','START_RC',G)
for i,p in enumerate([x for x in parts if x['ref'][0]=='U'],110):two('C'+str(i),'100nF X7R 16V 10%',V5 if p['ref']=='U112' else V,G)
two('C122','1uF X7R 16V 10%',V5,G)
part('J101','LOCAL_POWER_BOUNDARY',[(1,'3V3_3.234..3.366','passive',V),(2,'5V_5.049..5.151','passive',V5),(3,'24V_23.04..24.96','passive',V24),(4,'RETURN','passive',G)],'Project local connector; upstream sources NOT BOUND',scope='UNBOUND_EXTERNAL_SUPPLY_CONNECTOR')
part('J102','LOCAL_CONTROL_BOUNDARY',[(1,'HEARTBEAT_3V3','passive','HEARTBEAT_IN'),(2,'HW_PERMIT_3V3','passive','HW_PERMIT_IN'),(3,'GND','passive',G),(4,'RUN_STATUS','passive','RUN_LATCH'),(5,'FAULT_STATUS_N','passive','SAFE_N')],'Project local signal assignment; physical GPIO/connector NOT BOUND',scope='UNBOUND_CONTROLLER_CONNECTOR')
part('J103','MANUAL_CONTACTS_BOUNDARY',[(1,'RESET_FEED','passive',V),(2,'RESET_NO_RETURN','passive','RESET_CONTACT'),(3,'START_FEED','passive',V),(4,'START_NO_RETURN','passive','START_CONTACT'),(5,'STOP_NC_FEED','passive','PERMIT_BEFORE_STOP'),(6,'STOP_NC_RETURN','passive','EN_STOP')],'External RESET NO/START NO/STOP NC; switches and debounce not hardware-tested',scope='UNBOUND_SWITCH_CONNECTOR')
part('J104','GX11_COIL_BOUNDARY',[(1,'X1_POS','passive',V24),(2,'X2_NEG','passive','K1_COIL_MINUS')],'GX11 Rev6 p3 X1(+)/X2(-), no external suppression diode',scope='CONTACTOR_TERMINALS_DEFINED_MATE_OPEN')

# Auxiliary contact observation and external bus health boundary.
single('U115','SN74LVC1G17DBVR','HEARTBEAT_FILTER','WDI')
two('R119','47k 1%','HEARTBEAT_FILTER',G)
two('C125','100nF X7R 16V 10%',V,G)
single('U113','SN74LVC1G17DBVR','AUX_SENSE','AUX_CLOSED_3V3')
two('R115','10k 1%','AUX_RETURN',G)
two('R116','1k 1%','AUX_RETURN','AUX_SENSE')
part('U114','SN74LVC1G08DBVR',[(1,'A','input','HW_PERMIT_IN'),(2,'B','input','BUS_MONITOR_OK'),(3,'GND','power_in',G),(4,'Y','output','PERMIT_BEFORE_STOP'),(5,'VCC','power_in',V)],'SN74LVC1G08 Rev AA p3','Package_TO_SOT_SMD:SOT-23-5')
two('R117','10k 1%','BUS_MONITOR_OK',G);two('R118','10k 1%','HW_PERMIT_IN',G)
two('C123','100nF X7R 16V 10%',V,G);two('C124','100nF X7R 16V 10%',V,G)
part('J105','GX11_AUX_BOUNDARY',[(1,'T2_FEED','passive',V5),(2,'T1_RETURN','passive','AUX_RETURN')],'GX11 minimum wetting 5V / 0.1mA; selected source minimum5.049V REQUIRED not supplied here',scope='CONTACTOR_TERMINALS_DEFINED_MATE_OPEN')

# All MCU-bound status outputs are open drain, pulled only to the receiving MCU rail.
for ref,inn,out,r,cap in [('U116','RUN_LATCH','RUN_STATUS_MCU','R120','C126'),('U117','SAFE_N','SAFE_STATUS_MCU','R121','C127'),('U118','AUX_CLOSED_3V3','AUX_STATUS_MCU','R122','C128')]:
 part(ref,'SN74LVC1G07DBVR',[(1,'NC','no_connect',None),(2,'A','input',inn),(3,'GND','power_in',G),(4,'Y','open_collector',out),(5,'VCC','power_in',V)],'SN74LVC1G07 Rev AG p3/4/5/6, Ioff and open drain output')
 two(r,'10k 1%','MCU_VIO',out)
 two(cap,'100nF X7R 16V 10%',V,G)

for p in parts:
 if p['ref']=='J102':p['pins'] += [dict(number='6',name='AUX_CLOSED',electrical_type='passive',net='AUX_STATUS_MCU'),dict(number='7',name='BUS_MONITOR_OK_3V3',electrical_type='passive',net='BUS_MONITOR_OK'),dict(number='8',name='MCU_VIO_RECEIVER_RAIL',electrical_type='passive',net='MCU_VIO')]
 if p['ref']=='J102':
  for pin in p['pins']:
   if pin['number']=='4':pin['net']='RUN_STATUS_MCU'
   if pin['number']=='5':pin['net']='SAFE_STATUS_MCU'
 # Footprints deliberately not emitted until land-pattern verification/PCB stage.
 p['package_reference_unverified']=p['footprint'];p['footprint']=''
 p['value']=p['mpn']
 if p['ref'][0]=='R':
  val=p['value']
  code={'10k 1%':'10K0','47k 1%':'47K0','1k 1%':'1K00','100k 1%':'100K','22R 1%':'22R0'}.get(val)
  if code:p['mpn']='CRCW0603'+code+'FKEA';p['source']='Vishay D/CRCW e3 20035 order code, 1%,100ppm/C';p['scope']='SERIES_ORDER_CODE_SELECTED'
  elif p['ref']=='R105':p['mpn']='TNPW0603510KBEEA';p['source']='Vishay TNPW e3 28758 order code,0.1%,25ppm/C';p['scope']='SERIES_ORDER_CODE_SELECTED'
  elif p['ref']=='R106':p['mpn']='TNPW060310K0BEEA';p['source']='Vishay TNPW e3 28758 order code,0.1%,25ppm/C';p['scope']='SERIES_ORDER_CODE_SELECTED'
 if p['ref'][0]=='C' and p['ref']!='C101':
  p['mpn']='C0603C105K4RACTU' if p['value'].startswith('1uF') else 'C0603C104K3RACTU'
  p['source']='KEMET CER_ENG_KIT_29 and C0603C105K4RACTU specsheet, X7R';p['scope']='SELECTED_CIRCUIT_CANDIDATE'

dump(E/'STOP_CIRCUIT_CONNECTIVITY.json',dict(format=1,name='WP09D_STOP_CIRCUIT',parts=parts,original_master_mutated=False,full_system_closed=False))
name='wp09_stop_circuit';root=uid(name);defs=[];instances=[];wires=[];libdefs=[];pinmap=[]
for i,p in enumerate(parts):
 ref=p['ref'];lib='WP09STOP:'+ref;n=len(p['pins']);h=max(10,(n+1)*2.54);pins=''
 for j,pin in enumerate(p['pins']):
  pins+=f'(pin {pin["electrical_type"]} line (at 25.4 {-2.54*(j+1)} 180) (length 5.08) (name {q(pin["name"])} (effects (font (size 1 1)))) (number {q(pin["number"])} (effects (font (size 1 1)))))'
 sd=f'(symbol {q(lib)} (pin_names (offset 0.508)) (in_bom yes) (on_board yes) (property "Reference" {q(ref)} (at 0 3 0) (effects (font (size 1.27 1.27)))) (property "Value" {q(p["mpn"])} (at 0 0 0) (effects (font (size 1 1)))) (symbol {q(ref+"_0_1")} (rectangle (start -20.32 0) (end 20.32 {-h}) (stroke (width 0.254) (type default)) (fill (type background)))) (symbol {q(ref+"_1_1")} {pins}))'
 defs.append(sd);libdefs.append(sd.replace(q(lib),q(ref),1));x=35.56+(i%7)*116.84;y=30.48+(i//7)*50.8;ins=uid(ref)
 props=''.join(f'(property {q(k)} {q(v)} (at {x} {y+d} 0) (effects (font (size 1 1)){hide}))' for k,v,d,hide in [('Reference',ref,-7,''),('Value',p['mpn']+' / '+p.get('value',''),-4,''),('Footprint',p['footprint'],0,' (hide yes)'),('Datasheet',p['source'],0,' (hide yes)')])
 instances.append(f'(symbol (lib_id {q(lib)}) (at {x} {y} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {q(ins)}) {props} '+''.join(f'(pin {q(a["number"])} (uuid {q(uid(ref+"pin"+a["number"]))}))' for a in p['pins'])+f'(instances (project {q(name)} (path {q("/"+root)} (reference {q(ref)}) (unit 1)))))')
 for j,a in enumerate(p['pins']):
  px=x+25.4;py=y+2.54*(j+1)
  if a['net'] is None:wires.append(f'(no_connect (at {px} {py}) (uuid {q(uid(ref+"nc"+a["number"]))}))');continue
  lx=px+5.08;wires.append(f'(wire (pts (xy {px} {py}) (xy {lx} {py})) (stroke (width 0) (type default)) (uuid {q(uid(ref+"w"+a["number"]))})) (label {q(a["net"])} (at {lx} {py} 0) (effects (font (size 1 1)) (justify left bottom)) (uuid {q(uid(ref+"l"+a["number"]))}))')
  pinmap.append(dict(reference=ref,pin=a['number'],pin_name=a['name'],net=a['net'],electrical_type=a['electrical_type']))
notes='Actual component pins; upstream 3.3V / 5V / 24V rails require binding. No PWR_FLAG. Single-channel candidate, no SIL/PL. No PCB manufacture or energization release.'
s=f'(kicad_sch (version 20250114) (generator "eeschema") (generator_version "10.0") (uuid {q(root)}) (paper "A1") (title_block (title "WP09D stop watchdog, reset/start latch and GX11 driver") (date "2026-09-08") (rev "CIRCUIT_CANDIDATE_R1")) (lib_symbols {"".join(defs)}) {"".join(instances)} {"".join(wires)} (text {q(notes)} (at 20 548 0) (effects (font (size 1.5 1.5)) (justify left)) (uuid {q(uid("notes"))})) (sheet_instances (path "/" (page "1"))))'
(E/(name+'.kicad_sch')).write_text(s,encoding='utf8');(E/(name+'.kicad_pro')).write_text('{}',encoding='utf8')
(E/'WP09STOP.kicad_sym').write_text('(kicad_symbol_lib (version 20250114) (generator "kicad_symbol_editor") '+''.join(libdefs)+')',encoding='utf8')
(E/'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "WP09STOP") (type "KiCad") (uri "'+chr(36)+'{KIPRJMOD}/WP09STOP.kicad_sym") (options "") (descr "Actual selected IC pin maps; prototype candidate")))',encoding='utf8')
def csvout(fn,rows):
 with (E/fn).open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
csvout('STOP_PIN_NET_MAP.csv',pinmap)
csvout('STOP_BOM.csv',[dict(reference=p['ref'],mpn=p['mpn'],quantity=1,footprint=p['footprint'],value=p['value'],package_reference_unverified=p['package_reference_unverified'],source=p['source'],scope=p['scope'],grade='COMMERCIAL_PROTOTYPE',fabrication_release=False) for p in parts])
nets=collections.defaultdict(list)
for r in pinmap:nets[r['net']].append(r['reference']+'.'+r['pin'])
rows=[]
for net,eps in sorted(nets.items()):
 for b in eps[1:]:rows.append(dict(delta_id='SC%03d'%(len(rows)+1),net=net,from_endpoint=eps[0],to_endpoint=b,scope='LOCAL_SUBPAGE_ONLY_NOT_MASTER',physical_test='NOT_EXECUTED'))
csvout('STOP_FROM_TO_DELTA.csv',rows)
print(json.dumps(dict(parts=len(parts),pins=len(pinmap),nets=len(nets),delta_edges=len(rows))))
