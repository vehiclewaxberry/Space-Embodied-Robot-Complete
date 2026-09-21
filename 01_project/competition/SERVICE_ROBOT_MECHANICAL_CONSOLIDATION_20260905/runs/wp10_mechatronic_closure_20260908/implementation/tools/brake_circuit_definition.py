"""Physical-pin candidate: self-powered sink plus upstream-powered thermal alarm.

No activation command is emitted. Actual motion energy and installed thermal
capability are not implied by this circuit's presence in the native schematic.
"""
PARAMS=dict(bias_top_ohm=86600.,bias_bottom_ohm=10000.,bias_bleed_ohm=10000.,
 pg_pullup_ohm=270000.,CT_F=4.7e-9,OV_top_ohm=676000.,OV_bottom_ohm=10000.,
 OUTB_pullup_ohm=10000.,sense_filter_F=100e-12,branch_count=3,
 brake_R25_ohm=1.,brake_R_tol=.05,brake_TCR_per_C=500e-6,
 thermal_bias_ohm=8200.,thermal_open_top_ohm=649000.,thermal_open_bottom_ohm=100000.,
 NTC_R25_ohm=10000.,NTC_R25_tol=.02,NTC_B25_85_K=3977.,NTC_B_tol=.0075,
 ready_top_ohm=200000.,ready_bottom_ohm=10000.,ready_pulldown_ohm=100000.,
 ready_delay_F=1e-9,ready_delay_tolerance=.05,ready_bypass_F=100e-9)

def add_brake(part,passive,parts,groups,nc):
 before=set(parts)
 part('U301','LT3013EDE#PBF',{'1':'NC','2':'OUT','3':'OUT','4':'ADJ','5':'GND','6':'PWRGD','7':'CT','8':'SHDN','9':'NC','10':'IN','11':'IN','12':'NC','13':'GND_EP'},'lt3013.pdf RevE pp2,3,11-13,17','Load-side12V bias with reverse-output protection')
 cmp={'1':'OUTA','2':'GND','3':'INA+','4':'INB-','5':'VDD','6':'OUTB'}
 part('U302','TLV6700DDCR',cmp,'tlv6700.pdf RevB pp3,5,6','Absolute bus comparator; startup/propagation bounds OPEN')
 part('U303','MAX5048CAUT+T',{'1':'V+','2':'P_OUT','3':'N_OUT','4':'GND','5':'IN-','6':'IN+'},'https://www.analog.com/media/en/technical-documentation/data-sheets/MAX5048C.pdf Rev1 pp2,3,6,8','Split gate driver; ON only with independent bias READY high and absolute OV low')
 part('U304','MAX16053AUT+T',{'1':'EN','2':'GND','3':'IN','4':'OUT','5':'VCC','6':'CDELAY'},'https://www.analog.com/media/en/technical-documentation/data-sheets/MAX16052-MAX16053.pdf Rev7 pp2,3,7','Push-pull 10.5V nominal bias monitor; cold-start blanking; restart and maximum delay qualification OPEN')
 for ref,value,role in [('R308','200k_0.1pct_25ppm','READY bias divider upper'),('R309','10k_0.1pct_25ppm','READY bias divider lower'),('R310','100k_1pct','Driver IN+ external pulldown for disconnected READY'),('C307','1nF_5pct_50V_C0G','READY delay capacitor; finite timing envelope is a sensitivity'),('C308','100nF_25V','READY monitor local supply bypass')]:
  passive(ref,value,role)
 parts['C307'].update(manufacturer_part_number='C0603C102J5GACTU',manufacturer='KEMET',footprint='Capacitor_SMD:C_0603_1608Metric',source='KEMET CER_ENG_KIT_29.pdf; 1nF 5% 50V C0G; mounting and leakage unqualified',status='SELECTED_CANDIDATE')
 parts['U303']['footprint']='Package_TO_SOT_SMD:SOT-23-6'
 parts['U304']['footprint']='Package_TO_SOT_SMD:SOT-23-6'
 for ref,value,role in [
  ('R301','86.6k_0.1pct_25ppm','12V bias upper'),('R302','10k_0.1pct_25ppm','12V bias lower'),
  ('R303','270k_0.1pct_25ppm','Legacy PG diagnostic only; never exceed50uA sink; does not enable driver'),
  ('R304','10k_1pct','Bias minimum load'),('R305','676k_0.1pct_25ppm','Absolute OV sense upper'),
  ('R306','10k_0.1pct_25ppm','Absolute OV sense lower'),('R307','10k_1pct','OV high normal pullup'),
  ('C301','1uF_100V_EFFECTIVE_MIN1uF','Bias input bypass; MPN not released'),
  ('C302','22uF_50V_EFFECTIVE_MIN10uF','Bias reservoir: target >=10uF effective at voltage/temperature; MPN and DC-bias qualification OPEN'),
  ('C303','4.7nF_10pct_16V_C0G','PG delay; max startup duration unbound'),
  ('C304','100nF_25V','OV comparator local bypass'),('C305','2.2uF_25V_EFFECTIVE_MIN1uF','Gate driver near-pin low-ESR bypass: target >=1uF effective; MPN and layout qualification OPEN'),
  ('C306','100pF_5pct_C0G','OV input filter; wiring noise not qualified')]:passive(ref,value,role)
 def g(n,*eps):groups.setdefault(n,[]).extend(eps)
 g('ARM_BUS_PLUS','U301.10','U301.11','U301.8','C301.1','R305.1')
 g('ARM_RETURN','U301.5','U301.13','R302.2','R304.2','C301.2','C302.2','C303.2','U302.2','U302.3','U303.4','R306.2','C304.2','C305.2','C306.2')
 g('BRAKE_12V','U301.2','U301.3','R301.1','R303.1','R304.1','C302.1','U302.5','U303.1','C304.1','C305.1','R307.1')
 g('BRAKE_BIAS_ADJ','U301.4','R301.2','R302.1')
 g('BRAKE_BIAS_CT','U301.7','C303.1')
 g('BRAKE_BIAS_PG','U301.6','R303.2')
 g('BRAKE_12V','U304.1','U304.5','R308.1','C308.1')
 g('ARM_RETURN','U304.2','R309.2','R310.2','C307.2','C308.2')
 g('BRAKE_READY_DIV','R308.2','R309.1','U304.3')
 g('BRAKE_READY_DELAY','U304.6','C307.1')
 g('BRAKE_BIAS_READY','U304.4','U303.6','R310.1')
 g('BRAKE_OV_DIV','R305.2','R306.1','U302.4','C306.1')
 g('BRAKE_OV_N','U302.6','R307.2','U303.5')
 g('BRAKE_GATE_SOURCE','U303.2');g('BRAKE_GATE_SINK','U303.3')
 nc.update({'U301.1','U301.9','U301.12','U302.1'})
 for i in range(3):
  q='Q'+str(301+i);r='RB'+str(301+i);di='D'+str(311+i)
  on='R'+str(311+3*i);off='R'+str(312+3*i);pd='R'+str(313+3*i)
  part(r,'LPS0300H1R00JB',{'1':'TERMINAL_1','2':'TERMINAL_2'},'lps300.pdf pp1-4; terminals project IDs, electrically interchangeable','1ohm branch resistor; pulse/heat-path not yet qualified')
  part(q,'CSD19536KTT',{'1':'G','2':'D','3':'S'},'csd19536ktt.pdf RevC pp1,3','Dedicated switch for resistor branch '+str(i+1))
  part(di,'STPS30H100CT',{'1':'A1','2':'K','3':'A2'},'stps30h100c.pdf Rev9 pp1,2,8','Local resistor inductance recirculation; both anodes tied')
  passive(on,'10ohm_1pct','Separate turn-on gate resistor')
  passive(off,'2.2ohm_1pct','Separate turn-off gate resistor')
  passive(pd,'10k_1pct','Local gate-source passive discharge')
  g('ARM_BUS_PLUS',r+'.1',di+'.2')
  g('ARM_RETURN',q+'.3',pd+'.2')
  g('BRAKE_BRANCH_'+str(i+1),r+'.2',q+'.2',di+'.1',di+'.3')
  g('BRAKE_GATE_'+str(i+1),q+'.1',on+'.2',off+'.2',pd+'.1')
  g('BRAKE_GATE_SOURCE',on+'.1');g('BRAKE_GATE_SINK',off+'.1')
  # Three separate resistor temperature sensors; no average-temperature shortcut.
  uc='U'+str(311+i);ntc='RT'+str(311+i);ca='C'+str(311+i)
  rb='R'+str(341+3*i);rt='R'+str(342+3*i);rl='R'+str(343+3*i)
  part(uc,'TLV6700DDCR',cmp,'tlv6700.pdf RevB pp3,5','Hot/short and open-sensor alarm for branch '+str(i+1))
  part(ntc,'NTCLE100E3103GB0',{'1':'SENSOR','2':'RETURN'},'ntcle100.pdf Doc29049;10k2pct,B25/85=3977K','Temperature sensor at resistor body; attachment lag unbound')
  passive(rb,'8.2k_0.1pct_25ppm','Sensor bias from independent STOP3V3')
  passive(rt,'649k_0.1pct_25ppm','Open-sensor window upper')
  passive(rl,'100k_0.1pct_25ppm','Open-sensor window lower')
  passive(ca,'100nF_25V','Temperature comparator bypass')
  g('BRAKE_STOP_3V3',uc+'.5',rb+'.1',ca+'.1')
  g('ARM_RETURN',uc+'.2',ntc+'.2',rl+'.2',ca+'.2')
  g('BRAKE_TEMP_'+str(i+1),ntc+'.1',rb+'.2',uc+'.3',rt+'.1')
  g('BRAKE_TEMP_OPEN_'+str(i+1),rt+'.2',rl+'.1',uc+'.4')
  g('BRAKE_THERMAL_FAULT_N',uc+'.1',uc+'.6')
 g('BRAKE_STOP_3V3','STOPBOARD.U120.3')
 g('BRAKE_THERMAL_FAULT_N','STOPBOARD.U106.2')
 parts['J203']['role']='Load-side sink now connected; energy, dynamic and thermal qualification OPEN'
 parts['J203']['status']='ABSOLUTE_SINK_CIRCUIT_INTEGRATED_NOT_QUALIFIED'
 return sorted(set(parts)-before)

def pin_type(ref,p):
 if ref=='U301':
  return 'no_connect' if p in ['1','9','12'] else 'power_out' if p=='2' else 'passive' if p=='3' else 'open_collector' if p=='6' else 'power_in' if p in ['5','10','11','13'] else 'input'
 if ref in ['U302','U311','U312','U313']:
  return 'open_collector' if p in ['1','6'] else 'power_in' if p in ['2','5'] else 'input'
 if ref=='U303':return 'output' if p in ['2','3'] else 'power_in' if p in ['1','4'] else 'input'
 if ref=='U304':return 'output' if p=='4' else 'power_in' if p in ['2','5'] else 'passive' if p=='6' else 'input'
 return None
