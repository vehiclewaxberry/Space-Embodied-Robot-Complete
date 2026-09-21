"""Record explicitly reviewed candidate choices; no ECAD or old-source mutation."""
from build_electrical_update import D, ROOT, IMPL, XML, write
import xml.etree.ElementTree as ET

comps = {c.attrib['ref']: c for c in ET.parse(XML).getroot().findall('./components/comp')}
sources = {}
def source(key, url, local=None, pages=None, note=None):
    sources[key] = {'url': url, 'accessed_date': '2026-09-20', 'publisher_kind': 'MANUFACTURER_PRIMARY',
                    'local_origin': str(local.relative_to(ROOT)).replace('\\','/') if local else None,
                    'pages_or_section': pages, 'notes': note,
                    'price': None, 'stock': None, 'flight_qualification': False}
source('TPS3431', 'https://www.ti.com/lit/ds/symlink/tps3431.pdf', IMPL/'results/stop_v36/pcb/sources/tps3431.pdf', '3-6; DRB drawing')
source('TLV6700', 'https://www.ti.com/lit/ds/symlink/tlv6700.pdf', IMPL/'sources/tlv6700.pdf', '3-5; DDC drawing')
source('TPS2660', 'https://www.ti.com/lit/ds/symlink/tps2660.pdf', IMPL/'results/aux_v34/sources/tps2660_rev_g.pdf', '4-8; PWP drawing')
source('LT3013', 'https://www.analog.com/media/en/technical-documentation/data-sheets/3013fe.pdf', pages='2; DE package and ordering table', note='Supplemental U301 identity recovered from locked source Value; exact LT3013EDE#PBF ordering code verified on manufacturer primary PDF. Local archive unavailable. No new operating qualification claimed.')
source('MAX5048C', 'https://www.analog.com/media/en/technical-documentation/data-sheets/MAX5048C.pdf', pages='1-3, 6, 8', note='Primary web read; local PDF remains unavailable; do not describe as archived')
source('MAX16053', 'https://www.analog.com/media/en/technical-documentation/data-sheets/MAX16052-MAX16053.pdf', pages='1-3, 6-7', note='Primary web read; local PDF remains unavailable; do not substitute MAX16052 open-drain')
source('TNPW', 'https://www.vishay.com/docs/28758/tnpw_e3.pdf', IMPL/'sources/tnpw_e3_20260410_v24.pdf', '1-4; family size/value/tolerance/TCR ordering tables', 'Family-table-qualified ordering codes; exact supply availability unknown')
source('WSLP', 'https://www.vishay.com/docs/30179/wslp2726.pdf', IMPL/'sources/wslp2726.pdf', '1-2', 'L5000=0.0005 ohm; finished component TCR differs from alloy TCR')
source('WIMA', 'https://www.wima.de/wp-content/uploads/media/e_WIMA_MKS_2.pdf', IMPL/'sources/wima_mks2_v25.pdf', '1-2', 'C301 reuses the already selected C211 ordering code; new use needs layout and effective-C validation')
source('SVPF10', 'https://industrial.panasonic.com/tw/products/pt/os-con/models/50SVPF10M', pages='Specification', note='Web primary product table; nominal body diameter6.3mm/height5.9mm from SVPF catalogue; land pattern verification pending')
for key, part in [('TDK1','CGA6L2X7R1H105K160AA'), ('TDK6R8','CGA6P3X7S1H685M250AB'), ('TDK22','C3225X7R1H226M250AC')]:
    source(key, 'https://product.tdk.com/en/search/capacitor/ceramic/mlcc/info?part_no='+part,
           pages='Size; Electrical Characteristics; Other', note='Primary product page; characteristic curves are typical, not a guaranteed DC-bias bound')
for key, part in [('K100N100','C1210C104J1GACTU'), ('K100N25','C0603C104K3RACTU'), ('K2R2','C0805C225K3RACTU'), ('K100P','C0603C101J5GACTU')]:
    source(key, 'https://search.kemet.com/component-documentation/download/specsheet/'+part, D/'sources'/(part+'.pdf'), '1', 'Exact MPN sheet; graphs are typical only')
source('K4N7','https://yageogroup.com/download/specsheet/C0603C472J5GACTU',pages='1',note='Primary web PDF read; local archive not acquired')
write('inputs/PRIMARY_SOURCES.json', sources)

updates=[]
def add(refs, kind, mpn, maker, fp, sid, rating, limit, opened, status=None, action=None, evidence='PRIMARY_DATASHEET_OR_PRODUCT_PAGE'):
    for ref in refs.split():
        updates.append({'ref':ref,'kind':kind,'class':'REAL_PART_CANDIDATE','MPN':mpn,'manufacturer':maker,
                        'footprint': fp or comps[ref].findtext('footprint') or None, 'piece_qty':1,
                        'source_id':sid,'rating':rating,'evidence_class':evidence,
                        'substitution_limit':limit,'open_items':opened,
                        'status':status or ('RATING_RECORD_UPDATED_EXISTING_DESIGN' if kind=='IC_RATING' else 'CANDIDATE_SELECTED_ECAD_PENDING'),
                        'ecad_action':action or ('Keep exact part and current pad-net mapping; annotate ratings in next controlled ECAD revision' if kind=='IC_RATING' else 'Set MPN/manufacturer/datasheet/footprint only after placement, pad map and contract review'),
                        'procurement_url':None,'procurement_url_status':'需采购时核验原厂或授权分销商精确订货页；本轮未询价',
                        'footprint_download_url':None,'footprint_download_status':'Existing/local KiCad footprint reference or proposed package; OEM land/pin check required before release',
                        'procurement_release':False,'flight_qualified':False})
add('U101','IC_RATING','TPS3431SDRBR','Texas Instruments',None,'TPS3431',
    {'supply_operating_V':[1.8,6.5],'supply_absolute_V':[-.3,7],'operating_junction_C':[-40,125],'package':'VSON-8 DRB plus grounded pad','max_supply_current_uA':19},
    'Keep DRB pinout, open-drain WDO+ENOUT, SET1 and CWD timing equation; cannot replace with arbitrary watchdog.',
    ['Watchdog timeout including CWD tolerance, slow supply ramp and reset/no-restart bench verification remain open'])
add('U311 U312 U313','IC_RATING','TLV6700DDCR','Texas Instruments',None,'TLV6700',
    {'supply_operating_V':[1.8,18],'input_operating_V':[0,6.5],'supply_absolute_V':[-.3,20],'input_absolute_V':[-.3,7],'reference_V':.4,'package':'DDC SOT-23-THIN-6'},
    'Keep DDC pinout, dual open-drain polarity, 0.4V reference, bias/hysteresis; preserve the six C314-C319 and R350-R352 filter elements in the 249-ref source.',
    ['Actual NTC tolerance, thermal attachment and fault threshold/time bench verification remain open'])
add('U303','IC_RATING','MAX5048CAUT+T','Analog Devices','Package_TO_SOT_SMD:SOT-23-6','MAX5048C',
    {'supply_operating_V':[4,14],'pin_absolute_V':[-.3,16],'operating_temperature_C':[-40,125],'peak_source_A':3,'peak_sink_A':7,'max_static_supply_mA_at14V':1},
    'Keep six-pin source/sink split and input truth table; peak current is not continuous current and does not prove three MOSFET gate loading.',
    ['Local PDF archive unavailable; web primary verified','Gate-charge/switching-frequency loss, 12V transient headroom and local decoupling/layout remain open'])
add('U304','IC_RATING','MAX16053AUT+T','Analog Devices',None,'MAX16053',
    {'supply_operating_V':[2.25,28],'supply_absolute_V':[-.3,30],'operating_temperature_C':[-40,125],'output':'ACTIVE_HIGH_PUSH_PULL','reference_V':.5,'reference_range_V':[.491,.509],'max_static_supply_uA_at12V':57},
    'Keep MAX16053 push-pull active-high OUT, EN and CDELAY behavior; MAX16052 open-drain is not a direct substitution.',
    ['Local PDF archive unavailable; web primary verified','Delay corners, brownout sequencing and no-auto-restart bench verification remain open'])
add('U207','IC_RATING','TPS26600PWPR','Texas Instruments',None,'TPS2660',
    {'forward_operating_supply_V':[4.2,60],'supply_absolute_V':[-60,62],'operating_junction_C':[-40,125],'adjustable_limit_A':[.1,2.23],'ILIM_at5p36kohm_typ_A':2.23,'ILIM_at5p36kohm_max_A':2.35,'package':'HTSSOP-16 PWP plus EP','R_ILIM_allowed_kohm':[5.36,120]},
    'Keep exact TPS26600 fault/mode variant, PWP footprint and RTN/GND separation. Never carry 20A MAIN through the 2A AUX eFuse.',
    ['AUX inrush/current-limit tolerance, thermal dissipation, output fault and recovery behavior still require validation'])

def cap(refs,mpn,maker,case,sid,uF,V,tol,dielectric,opened=None,status=None):
    fp='Capacitor_SMD:C_'+{'0603':'0603_1608Metric','0805':'0805_2012Metric','1210':'1210_3225Metric'}[case] if case in ['0603','0805','1210'] else case
    add(refs,'PASSIVE',mpn,maker,fp,sid,{'capacitance_uF':uF,'rated_VDC':V,'initial_tolerance_fraction':tol,'dielectric':dielectric},
        'Replacement requires same function, adequate rated voltage and tolerance, verified effective capacitance/ESR, package and lead/polarity map; no nominal-value-only substitution.',
        opened or ['Placement/land pattern and transient/ripple/installed temperature verification remain open'],status=status)
cap('C204','50SVPF10M','Panasonic',None,'SVPF10',10,50,.2,'CONDUCTIVE_POLYMER',
    ['OEM land pattern and 6.3mm diameter/5.9mm nominal height need PCBA placement','Polarized; 40mohm ESR at100kHz and 2.5Arms at105C/100kHz do not bound actual ripple'])
cap('C205','CGA6L2X7R1H105K160AA','TDK','1210','TDK1',1,50,.1,'X7R',
    ['New1210 footprint placement; DC-bias/ripple check remains open','Commercial C3225X7R1H105K160AA page says NRND; selected automotive CGA variant is a different exact part; AEC-Q200 is not space qualification'])
cap('C206 C208','C1210C104J1GACTU','KEMET','1210','K100N100',.1,100,.05,'C0G')
cap('C207 C304 C308','C0603C104K3RACTU','KEMET','0603','K100N25',.1,25,.1,'X7R')
cap('C209 C210','CGA6P3X7S1H685M250AB','TDK','1210','TDK6R8',6.8,50,.2,'X7S',
    ['X7S +/-22% TCC plus DC bias and aging must enter STOP24 filter budget','THN output total capacitance and ESR incl all STOP loads are UNKNOWN; no transient PASS'],status='CANDIDATE_SELECTED_CAPACITANCE_HOLD')
cap('C301','MKS2D041501M00JSSD','WIMA','WP10_INPUT:MKS2_D041501M00_P5_Slot2','WIMA',1.5,100,.05,'PET_FILM',
    ['Change nominal1uF to1.5uF to reserve initial tolerance; verify inrush/regulator stability and7.2x8.5x14mm nominal space','Effective >=1uF across environment and life remains unverified; OEM voltage derating above85C required'],status='CANDIDATE_SELECTED_CAPACITANCE_HOLD')
cap('C302','C3225X7R1H226M250AC','TDK','1210','TDK22',22,50,.2,'X7R',
    ['Effective >=10uF at12V including bias,TCC,tolerance,aging and regulator ESR stability remains unverified'],status='CANDIDATE_SELECTED_CAPACITANCE_HOLD')
cap('C303','C0603C472J5GACTU','KEMET','0603','K4N7',.0047,50,.05,'C0G',
    ['4.7nF +/-5% replaces +/-10% requirement; delay worst corners and layout remain open','Local PDF archive unavailable; exact primary web sheet verified'])
cap('C305','C0805C225K3RACTU','KEMET','0805','K2R2',2.2,25,.1,'X7R',
    ['Effective >=1uF at12V including DC bias,TCC,tolerance and aging remains unverified'],status='CANDIDATE_SELECTED_CAPACITANCE_HOLD')
cap('C306','C0603C101J5GACTU','KEMET','0603','K100P',.0001,50,.05,'C0G')

for refs,code,ohm,tol in [
    ('R301','86K6',86600,.001),('R302 R306 R309','10K0',10000,.001),('R303','270K',270000,.001),
    ('R308','200K',200000,.001),('R304 R307 R313 R316 R319','10K0',10000,.01),
    ('R310','100K',100000,.01),('R311 R314 R317','10R0',10,.01),('R312 R315 R318','2R20',2.2,.01)]:
    add(refs,'PASSIVE','TNPW0603'+code+('B' if tol==.001 else 'F')+'EEA','Vishay',
        'Resistor_SMD:R_0603_1608Metric','TNPW',
        {'resistance_ohm':ohm,'initial_tolerance_fraction':tol,'TCR_ppm_K':25,'general_mode_P70_W':.11,'general_mode_film_max_C':125,'working_voltage_max_V':100},
        'Keep resistance,tolerance,TCR and package; permissible working voltage also limited by sqrt(P*R); check pulse load separately.',
        ['PCB placement, installed-film temperature and gate pulse load where applicable remain unverified'],evidence='FAMILY_ORDERING_TABLE_QUALIFIED_NOT_STOCK_VERIFIED')
add('R305','COMPOSITE_ECO',None,'Vishay',None,'TNPW',
    {'series_resistance_ohm':676000,'initial_tolerance_fraction':.001,'TCR_each_ppm_K':25,
     'proposed_parts':[{'ref':'R305A_PROPOSED','MPN':'TNPW0805665KBEEA','R_ohm':665000,'P70_W':.14},
                       {'ref':'R305B_PROPOSED','MPN':'TNPW060311K0BEEA','R_ohm':11000,'P70_W':.11}]},
    'No invented676k standard MPN; 665k0805 plus11k0603 preserves nominal676k. Do not buy or fit both on the old single footprint.',
    ['New mid-node, two footprints and 8 tolerance corners; reference/bias/hysteresis/TCR full trip limits remain open'],
    status='COMPOSITE_CANDIDATE_ECO_REQUIRED',action='Replace logical R305 by series R305A/R305B and new middle net; not implemented',
    evidence='FAMILY_ORDERING_TABLE_QUALIFIED_NOT_STOCK_VERIFIED')
updates[-1]['piece_qty']=2
for ref,clas,note in [
    ('J200','INTERFACE_BOUNDARY_OPEN','Battery adapter output boundary. Physical mating connector, keying and rated current remain open; do not add a fictitious connector.'),
    ('J201','PCB_TEST_POINT_DEFINITION','CHB enable test points explicitly NO JUMPER; future copper/test-pad geometry and accessibility remain open.'),
    ('J202','INTERFACE_BOUNDARY_OPEN','Hot-swap reset boundary; actual reset switch/harness/board test interface not selected.'),
    ('J203','INTERFACE_BOUNDARY_OPEN','Load-side brake power port; mating termination, current rating and cable definition remain open.'),
    ('J210','PCB_FABRICATION_FEATURE','AUX ResetTestPads are existing board copper; no separately purchased component.')]:
    updates.append({'ref':ref,'kind':'PROJECT_BOUNDARY','class':clas,'MPN':None,'manufacturer':None,
                    'footprint':comps[ref].findtext('footprint'),'piece_qty':0,'source_id':'PROJECT_CLASSIFICATION',
                    'rating':{'installed_port_current_A':None,'installed_port_voltage_V':None},
                    'evidence_class':'SOURCE_NETLIST_PLUS_BOARD_READBACK','substitution_limit':note,
                    'open_items':[note],'status':'CLASSIFIED_INTERFACE_OR_FABRICATION_NOT_PROCUREMENT_CLOSED',
                    'ecad_action':'Keep logical interface; realize/verify actual connection in interface ECO without double counting',
                    'procurement_release':False,'flight_qualified':False})
write('inputs/SELECTION_UPDATES.json',updates)
print('Prepared',len(updates),'reference dispositions and',len(sources),'primary source records')
