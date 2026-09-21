from pathlib import Path
import json,hashlib,csv,uuid,collections
E=Path(__file__).resolve().parents[1]
C=E.parents[1]/'wp09_interfaces_20260907_1525/system_completion'
baseline=C/'electrical_delta/STOP_CIRCUIT_CONNECTIVITY.json'
parts=json.loads(baseline.read_text(encoding='utf8'))['parts']
V='STOP_3V3';G='STOP_GND';V5='STOP_5V';V24='STOP_24V'
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
def find(ref):return next(p for p in parts if p['ref']==ref)
def pin(n,name,typ,net):return dict(number=str(n),name=name,electrical_type=typ,net=net)
def editpin(ref,n,**kw):next(a for a in find(ref)['pins'] if a['number']==str(n)).update(kw)
def add(ref,mpn,pins,source,value=None,package=''):
 parts.append(dict(ref=ref,mpn=mpn,value=value or mpn,pins=pins,source=source,footprint='',package_reference_unverified=package,scope='SELECTED_GSE_CIRCUIT_CANDIDATE'))
def two(ref,mpn,val,a,b,source,package=''):
 add(ref,mpn,[pin(1,val,'passive',a),pin(2,'','passive',b)],source,val,package)
# 5-pin TO-220 pin map: input1, GND2/4, VDD3/tab, output5.
find('U112').update(mpn='TC4420CAT',value='TC4420CAT',pins=[pin(1,'INPUT','input','RUN_DRIVE'),pin(2,'GND','power_in',G),pin(3,'VDD_TAB','power_in',V5),pin(4,'GND','power_in',G),pin(5,'OUTPUT','output','GATE_DRV')],source='Microchip DS21419D p4 operating-temperature electrical limits; p8 TO-220 pin table; p19 ordercode AT C-temp-only0..70C',package_reference_unverified='Package_TO_SOT_THT:TO-220-5_Vertical')
# Retain AHCT same 5V domain: its input current is bounded when VCC=0.
# This avoids directly driving an unpowered TC4420 input from the live 3V3 rail.
find('U119')['source']='SN74AHCT1G125 Rev P p4/5; input II at VCC0..5.5V; output shares TC4420 5V domain, not an Ioff output'
for ref,mpn,out in [('U120','TSR 1-2433',V),('U121','TSR 1-2450',V5)]:
 add(ref,mpn,[pin(1,'VIN','power_in',V24),pin(2,'GND','power_in',G),pin(3,'VOUT','power_out',out)],'TRACO TSR1 official datasheet Feb7 2024; SIP3 pinout1VIN2GND3OUT; locked official web retrieval; binary403',package='SIP3, nominal11.7x7.5x10.1mm, layout drawing verification pending')
# Keep actual output load >=10%: load-regulation guarantee applies 10..100%.
two('R124','PR02000202409JA100','24R 5% 250ppm/C 2W',V,G,'Vishay28729 Rev08Jul2025 p3 order-code; PR02 standard Cu0.78 24.0ohm J A1 0','Axial PR02 0411')
two('R125','PR02000203909JA100','39R 5% 250ppm/C 2W',V5,G,'Vishay28729 Rev08Jul2025 p3 order-code; PR02 standard Cu0.78 39.0ohm J A1 0','Axial PR02 0411')
# Contact24V feed -> physical contact -> divider -> Ioff-capable Schmitt input.
editpin('J105',1,net=V24,name='T2_FEED_24V')
find('J105')['source']='GX11 aux minimum5V/0.1mA; protected upstream24V feed, distinct T1 return; not certified mirror'
find('R115').update(mpn='CRCW060322K0FKEA',value='22k 1% 100ppm/C',source='Vishay CRCW20035 E24 code')
editpin('R115',1,net='AUX_RETURN');editpin('R115',2,net='AUX_DIV')
editpin('R116',1,net='AUX_DIV')
two('R130','CRCW06033K90FKEA','3.9k 1% 100ppm/C','AUX_DIV',G,'Vishay CRCW20035 E24 code','Resistor_SMD:R_0603_1608Metric')
# Existing pins 1/2 are now test outputs, not unbound inputs.
editpin('J101',1,name='3V3_TEST_OUTPUT_NO_EXT_SUPPLY');editpin('J101',2,name='5V_TEST_OUTPUT_NO_EXT_SUPPLY')
find('J101').update(source='J101.3/.4 input from K1-upstream Q1-protected24V/return; .1/.2 test-only outputs, no external voltage injection',scope='POWER_INPUT_AND_TEST_OUTPUT_BOUNDARY')
for p in parts:
 p['footprint']=''
 p.setdefault('package_reference_unverified','')
dump(E/'STOP_CIRCUIT_CONNECTIVITY.json',dict(format=2,name='WP10_STOP_AUX_SUPPLY_CANDIDATE',parts=parts,parent_path=str(baseline),parent_sha256=hashlib.sha256(baseline.read_bytes()).hexdigest(),parent_mutated=False,full_system_closed=False,rail_design_temperature_C=[0,50],rail_dynamic_limits_closed=False))
# Reuse exact parent schematic serializer, never execute parent top-level writes.
src=(C/'tools/stop_circuit_build_r2.py').read_text(encoding='utf8')
emit=src[src.index("name='wp09_stop_circuit';"):]
emit=emit.replace("'wp09-stop-20260908:'","'wp10-stop-20260908:'")
emit=emit.replace('Actual component pins; upstream 3.3V / 5V / 24V rails require binding. No PWR_FLAG. Single-channel candidate, no SIL/PL. No PCB manufacture or energization release.','Actual TSR1 supplies and TC4420 driver. Input is Q1-protected24V upstream of K1. GSE candidate0..50C, static DC only; ripple/transient/PCB/hardware open. No PWR_FLAG.')
emit=emit.replace('WP09D stop watchdog, reset/start latch and GX11 driver','WP10 stop watchdog with actual auxiliary supplies and contactor driver').replace('CIRCUIT_CANDIDATE_R1','GSE_SUPPLY_CANDIDATE_R3')
def uid(s):return str(uuid.uuid5(uuid.NAMESPACE_URL,'wp10-stop-20260908:'+s))
def q(s):return json.dumps(str(s),ensure_ascii=False)
exec(compile(emit,str(E/'tools/build_stop_supply.py')+':serializer','exec'),globals())
dump(E/'results/BUILD_LINEAGE.json',dict(parent_files=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in [baseline,C/'tools/stop_circuit_build_r2.py']],parent_execution=False,serializer_copied_as_source_only=True,components=len(parts)))
