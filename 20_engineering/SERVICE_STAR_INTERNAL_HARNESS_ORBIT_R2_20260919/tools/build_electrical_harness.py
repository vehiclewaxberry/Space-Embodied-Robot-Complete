"""Compile source-bound electrical harness candidate, preserving UNKNOWN and old evidence.

Run with Python >=3.10. This compiles data only; no KiCad edits, CAD operations or energising.
"""
from pathlib import Path
import json, csv, hashlib, math, copy, argparse, xml.etree.ElementTree as ET
from datetime import datetime, timezone

OUT=Path(__file__).resolve().parents[1]
ROOT=OUT.parents[1]
BASE=ROOT/'01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation'
SOURCES={}
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def require_digest(p,expected):
    if not isinstance(expected,str) or len(expected)!=64 or sha(Path(p))!=expected:raise ValueError('SOURCE_SHA256_MISMATCH: '+str(p))
def read(p):
    p=Path(p); SOURCES[str(p)] = sha(p)
    return json.loads(p.read_text(encoding='utf-8-sig'))
def readcsv(p):
    p=Path(p); SOURCES[str(p)]=sha(p)
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(name,obj):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
def writecsv(name,rows,fields):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items() if k in fields})
def circuit_check(rows,pins):
    errors=[]; ids=set()
    for r in rows:
        if not isinstance(r['active'],bool):errors.append((r['id'],'active_not_native_boolean'))
        if r['id'] in ids:errors.append((r['id'],'duplicate_id'))
        ids.add(r['id'])
        if not r['active']:continue
        for side in ['from','to']:
            k=r[side]['native_key']
            if not k:errors.append((r['id'],side+'_missing_native_pin_key'))
            elif k not in pins or pins[k]!=r['net']:errors.append((r['id'],side+'_pin_net_mismatch'))
        if r['cut_length_mm'] is not None and (isinstance(r['cut_length_mm'],bool) or not math.isfinite(r['cut_length_mm']) or r['cut_length_mm']<=0):errors.append((r['id'],'invalid_cut_length'))
        if r.get('ground_only') and r.get('flight_qualified'):errors.append((r['id'],'ground_promoted_to_flight'))
        if r['manufacturing_release'] and any(r.get(k) is not True for k in ['endpoint_termination_complete','route_verified_current_host','protection_coordination_verified','process_qualified','load_case_complete']):errors.append((r['id'],'release_with_unknown'))
        if r['manufacturing_release'] and any(r.get(k) is None for k in ['wire_MPN','AWG','cut_length_mm','cut_length_tolerance_mm','strip_start_mm','strip_end_mm','load_current_A','shield','shield_termination']):errors.append((r['id'],'release_missing_numeric_or_mpn_contract'))
        if r.get('wire_temperature_qualified') is not False:errors.append((r['id'],'unsupported_temperature_credit'))
    active_ids={r['id'] for r in rows if r['active']}
    for a,b in [('AUX_IN_P','AUX_IN_R'),('AUX_OUT_P','AUX_OUT_R'),('AUX_REMOTE','AUX_REMOTE_R'),('SC_PWR24','SC_RET'),('C203_W_PLUS','C203_W_MINUS'),('NTC_1_S','NTC_1_R'),('NTC_2_S','NTC_2_R'),('NTC_3_S','NTC_3_R')]:
        if (a in active_ids)!=(b in active_ids):errors.append((a+'/'+b,'missing_loop_leg'))
    return errors
def resistance_ohm(length_mm,r20_ohm_per_m):
    for v in (length_mm,r20_ohm_per_m):
        if v is not None and (isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0):raise ValueError('invalid conductor inputs')
    if length_mm is None or r20_ohm_per_m is None:return None
    return length_mm/1000.0*r20_ohm_per_m
def electrical_loss(length_mm,r20,current_A):
    if current_A is not None and (isinstance(current_A,bool) or not isinstance(current_A,(int,float)) or not math.isfinite(current_A) or current_A<0):raise ValueError('current must be a finite non-negative scalar magnitude or None')
    R=resistance_ohm(length_mm,r20)
    return {'R20_upper_ohm':R,'I_A':current_A,'drop_V':None if R is None or current_A is None else R*current_A,'loss_W':None if R is None or current_A is None else R*current_A**2}

def main():
    latest=read(BASE/'coupled_closure/HANDOFF_LATEST.json');entry=Path(latest['entry']);require_digest(entry,latest['entry_sha256']);entry_doc=read(entry)
    verification_binding=entry_doc['evidence']['verification'];verification_path=BASE/verification_binding['path'];require_digest(verification_path,verification_binding['sha256']);verify=read(verification_path)
    board_binding=entry_doc['evidence']['board'];require_digest(BASE/board_binding['path'],board_binding['sha256'])
    xml=BASE/verify['netlist_xml'];require_digest(xml,verify['netlist_xml_sha256']);SOURCES[str(xml)]=sha(xml)
    tree=ET.parse(xml).getroot(); components={}
    for c in tree.findall('./components/comp'):
        fields={f.get('name'):f.text for f in c.findall('./fields/field')}
        components[c.get('ref')]={'ref':c.get('ref'),'value':c.findtext('value'),'MPN':fields.get('MPN'),'manufacturer':fields.get('Manufacturer'),'footprint':c.findtext('footprint'),'datasheet':c.findtext('datasheet'),'sheet':c.find('sheetpath').get('names')}
    pins={}; pinrows=[]
    for net in tree.findall('./nets/net'):
        for n in net.findall('node'):
            k=n.get('ref')+'.'+n.get('pin');assert k not in pins or pins[k]==net.get('name')
            pins[k]=net.get('name');pinrows.append({'endpoint':k,'ref':n.get('ref'),'pin':n.get('pin'),'net':net.get('name'),'pinfunction':n.get('pinfunction'),'pintype':n.get('pintype')})
    aliases=read(BASE/'ecad/SYSTEM_ENDPOINT_MAP.json')
    master=readcsv(BASE/'ecad/MASTER_FROM_TO.csv')
    padread=read(OUT/'results/ELECTRICAL_PAD_READBACK.json');assert padread['source_xml_sha256']==sha(xml)
    for b in padread['boards']:
        require_digest(b['board'],b['sha256']);SOURCES[b['board']]=b['sha256']
    padmap={};connector_rows=[]
    for b in padread['boards']:
        for p in b['electrical_pads']:
            key=p['ref']+'.'+p['pin'];padmap.setdefault(key,[]).append({'board':Path(b['board']).name,'board_sha256':b['sha256'],**p})
            if p['ref'].startswith('J') or p['ref'].startswith('PORT_'):connector_rows.append({'board':Path(b['board']).name,**p, 'MPN':components.get(p['ref'],{}).get('MPN')})
    cdef=read(BASE/'power/CAP_HARNESS_DEFINITION_V19.json');cpath=read(BASE/'results/CAP_HARNESS_PATH_V19.json');cret=read(BASE/'power/CAP_HARNESS_RETENTION_V21.json');lug=read(BASE/'power/LUG_HARNESS_SELECTION_V30.json')
    r1=read(ROOT/'20_engineering/SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919/inputs/NEUTRAL_SOURCE_MAP.json')
    cap3d={w['id']:w for w in cdef['wires']}; caplength={w['id']:w for w in cpath['wires']}
    chbp=readcsv(BASE/'ecad/CHB_INPUT_ENDPOINTS_V18.csv')
    public={'retrieved_date':'2026-09-20','scope':'Manufacturer public design facts; source availability is not procurement or flight certification.', 'sources':[
      {'id':'TE55','url':'https://www.te.com/commerce/DocumentDelivery/DDEController?Action=srchrtrv&DocNm=55A0111&DocType=Customer+Drawing&DocLang=English','title':'55A0111 Rev R 24MAR11, Tables I-II; locally inspected scanned page 1','local_path':str(BASE/'sources/te_55a0111_drawing.pdf'),'sha256':sha(BASE/'sources/te_55a0111_drawing.pdf')},
      {'id':'TE20','url':'https://www.te.com/en/product-2160053004.html','facts':'55A0111-20-9, 20AWG, tin-coated copper, modified cross-linked ETFE, 600V, -65..150C; drawing governs dimensions.'},
      {'id':'MOLEX_CONTACT','url':'https://www.molex.com/en-us/products/part-detail/430300007','facts':'20/22/24AWG, insulation OD<=1.85mm; contact rating is not installed harness ampacity.'},
      {'id':'MOLEX_PS','url':'https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/productspecificationpdf/430/43045/PS-43045-001.pdf?inline=','facts':'Application current depends on wire, circuit count and end use; existing contact resistance scenarios retain their stated low-level test scope.'},
      {'id':'JST_GH','url':'https://www.jst-mfg.com/product/pdf/eng/eGH.pdf','facts':'SM06B-GHS-TB with GHR-06V-S / SSHL-002T-P0.2, AWG30..26 and insulation OD0.76..1.0mm, 50V, -40..105C including rise. SSHL-003 cannot mate GH.'},
      {'id':'NASA_HARNESS','url':'https://standards.nasa.gov/node/283','facts':'NASA-STD-8739.4A Change4 remains active; workmanship reference only, no claimed compliance.'}]}
    SOURCES[str(BASE/'sources/te_55a0111_drawing.pdf')]=public['sources'][0]['sha256']
    wirefamilies={
      '55A0111-20-9':{'AWG':20,'strands':'19x32','OD_mm':[.048*25.4,.052*25.4],'R20_upper_ohm_per_m':9.88/304.8,'voltage_rating_V':600,'temperature_range_C':[-65,150],'source':'TE55 page1 row20 / TE20','selection':'NEW_R2_GROUND_AUX_CANDIDATE'},
      '55A0111-26-9':{'AWG':26,'strands':'19x38','OD_mm':[.030*25.4,.034*25.4],'R20_upper_ohm_per_m':41.3/304.8,'voltage_rating_V':600,'temperature_range_C':[None,150],'cold_bend_test_temperature_C':[-68,-62],'lower_operating_limit_verified':False,'source':'TE55 page1 row26 and page2; cold bend temperature is not taken as an installed lower operating limit','selection':'NEW_R2_GROUND_NTC_CANDIDATE'},
      '55A0111-18-9':{'AWG':18,'strands':'19x30','OD_mm':[.058*25.4,.062*25.4],'R20_upper_ohm_per_m':cdef['wire']['max_R20_ohm_per_m'],'voltage_rating_V':600,'temperature_range_C':[None,150],'cold_bend_test_temperature_C':[-68,-62],'lower_operating_limit_verified':False,'source':'TE55 row18 / CAP_HARNESS_DEFINITION_V19; cold bend does not establish lower operating limit','selection':'RETAINED_C203_CANDIDATE'},
      '55A0111-10-9':{'AWG':10,'strands':'37x26','OD_mm':[.122*25.4,.134*25.4],'R20_upper_ohm_per_m':lug['wire']['R20_max_ohm_m'],'voltage_rating_V':600,'temperature_range_C':[-65,150],'source':'TE55 row10 / LUG_HARNESS_SELECTION_V30','selection':'RETAINED_LOCAL_LUG_ONLY'}}
    def endpoint(s):
        a=aliases.get(s);native=(a['ref']+'.'+a['pin']) if a else s
        if s.startswith('STOPBOARD.') and s[len('STOPBOARD.'):] in pins:native=s[len('STOPBOARD.'):]
        r,p=(native.split('.',1)+[''])[:2];c=components.get(r,{})
        return {'endpoint':s,'native_key':native if native in pins else None,'ref':r if native in pins else None,'pin':p if native in pins else None,'net':pins.get(native),'connector_or_component_MPN':c.get('MPN'),'component_value':c.get('value'),'pin_evidence':'PCB_PAD_AND_CURRENT_XML' if native in padmap else 'CURRENT_XML_LOGICAL_OR_EXTERNAL_REQUIREMENT','board_pad_positions':padmap.get(native,[]),'S_mm':None,'physical_mating_contact_S_mm':None,'mating_housing_MPN':None,'contact_MPN':None,'termination_process':None}
    def row(i,a,b,net=None):
        aa=endpoint(a);bb=endpoint(b)
        return {'id':i,'active':True,'from':aa,'to':bb,'net':net if net else aa['net'],'signal':net,'identity':'GROUND_ENGINEERING_CANDIDATE','ground_only':False,'flight_qualified':False,'nominal_voltage_V':None,'nominal_voltage_basis':None,'load_current_A':None,'load_current_basis':None,'wire_MPN':None,'AWG':None,'shield':None,'shield_termination':None,'cut_length_mm':None,'cut_length_tolerance_mm':None,'strip_start_mm':None,'strip_end_mm':None,'branch_group':None,'protection_chain':None,'protection_coordination_verified':False,'endpoint_termination_complete':False,'route_verified_current_host':False,'process_qualified':False,'load_case_complete':False,'wire_temperature_qualified':False,'manufacturing_release':False,'source':[],'missing_fields':[]}
    rows=[]
    for m in master:
        r=row(m['wire_id'],m['from_endpoint'],m['to_endpoint']);r['active']=m['active']=='true';r['signal']=m['signal'];r['legacy_status']=m['status'];r['legacy_wire_or_mate']=m['wire_or_mate'];r['source']=[{'path':str(BASE/'ecad/MASTER_FROM_TO.csv'),'wire_id':m['wire_id']},{'path':str(xml)}]
        if m['wire_id'].startswith('S') and m['wire_id'][1:].isdigit():r['ground_only']=True;r['identity']='GROUND_RS422_SPLICE_NETWORK_NOT_SINGLE_CUT_WIRE'
        if m['wire_id'] in ['L01','L02']:r['ground_only']=True;r['identity']='GROUND_OBC_P1_SHORT_LEAD_CANDIDATE';r['branch_group']='OBC_P1';r['AWG']=28;r['nominal_voltage_V']=3.3;r['nominal_voltage_basis']='Existing ground P1 constrained source3.29..3.32V +/-20mV; exact source must be verified';r['from']['mating_housing_MPN']='SFSD-15-28-G-03.00-S';r['to']['mating_housing_MPN']='510210400';r['to']['contact_MPN']='500798000'
        if m['wire_id'].startswith('PV'):r['identity']='ORBIT_ARRAY_INTERFACE_REQUIREMENT_NOT_GROUND_ENERGISED';r['protection_chain']='Per-string blocking diode required; selected diode/array topology not bound'
        if m['wire_id'].startswith('BP'):r['identity']='ORBIT_EPS_INTERFACE_REQUIREMENT_NOT_GROUND_ENERGISED';r['protection_chain']='RAW battery outputs lack short-circuit protection in cited BPX contract; harness protection remains open'
        if m['wire_id'] in ['A09','A10','C01','C02','C03','C04']:r['identity']='OEM_ARM_HARNESS_RETAINED_PIN_CAVITY_UNBOUND'
        if m['wire_id'] in ['SC_PWR24','SC_RET','K1_COILP','K1_COILR','K1_FB1','K1_FB2']:r['branch_group']='STOP_K1';r['protection_chain']='F202 -> AUX eFuse -> isolated THN; current, timing, coil suppression and fault coordination require measured contract'
        if m['wire_id'] in ['SC_PWR24','K1_COILP','K1_FB2']:r['nominal_voltage_V']=24;r['nominal_voltage_basis']='Existing isolated STOP24 design rail, not measured'
        if not r['active']:r['identity']='RETIRED_NO_REUSE'
        rows.append(r)
    # Add the present PCB external connectors absent from the old master harness sheet.
    aux=[('AUX_IN_P','J208.1','F202.2'),('AUX_IN_R','J208.2','J205.1'),('AUX_OUT_P','J209.1','U202.1'),('AUX_OUT_R','J209.2','U202.2'),('AUX_REMOTE','J211.1','U202.3'),('AUX_REMOTE_R','J211.2','U202.2')]
    for i,a,b in aux:
        r=row(i,a,b);r['identity']='NEW_R2_AUX_HARNESS_DESIGN_CANDIDATE';r['branch_group']='AUX_'+a.split('.')[0];r['wire_MPN']='55A0111-20-9';r['AWG']=20;r['from']['mating_housing_MPN']='430250200';r['from']['contact_MPN']='430300007';r['from']['termination_process']='CRIMP_PARAMETERS_AND_PULL_TEST_PENDING';r['protection_chain']='J208 upstream F202; J209 after U207 eFuse; J211 primary reference only';r['source']=[{'path':str(BASE/'ecad/revisions/v36/AUX_HARNESS_INTERFACE.csv')},{'path':str(xml)},{'source_id':'TE55'},{'source_id':'MOLEX_CONTACT'}];r['design_notes']='J208.2 primary return concretised to current J205.1 logical node; remote lug/branch attachment remains undefined. Identical 2-pin housings remain interchangeable: label AUX-IN/AUX-OUT/AUX-REMOTE at both ends; no hard keying claim.';rows.append(r)
    readcsv(BASE/'ecad/revisions/v36/AUX_HARNESS_INTERFACE.csv');readcsv(BASE/'ecad/revisions/v36/AUX_MATING_BOM.csv')
    for n,ref in enumerate(['RT311','RT312','RT313']):
        for side,pin in [('S',1),('R',2)]:
            r=row(f'NTC_{n+1}_{side}',f'J106.{2*n+pin}',f'{ref}.{pin}');r['identity']='NEW_R2_NTC_HARNESS_DESIGN_CANDIDATE';r['branch_group']=f'NTC_{n+1}';r['wire_MPN']='55A0111-26-9';r['AWG']=26;r['from']['mating_housing_MPN']='GHR-06V-S';r['from']['contact_MPN']='SSHL-002T-P0.2';r['from']['termination_process']='JST AP-K2N / MKS-L-10-3 / APLMK SSHL002-02 catalogue combination; strip/crimp setup and pull-test pending';r['to']['connector_or_component_MPN']='NTCLE100E3103GB0';r['protection_chain']='Existing RC/filter/comparator channels; sensor attachment, open/short fault and thermal calibration unverified';r['source']=[{'path':str(xml)},{'source_id':'TE55'},{'source_id':'JST_GH'}];r['design_notes']='Keep each odd sense with the following even return; route as separate labeled pair away from switching/coil paths. Twist pitch, shielding and sensor-end insulation remain null.';rows.append(r)
    for w in cdef['wires']:
        plus=w['id'].endswith('PLUS');r=row(w['id'],'C203.'+('1' if plus else '2'),w['logical_to'],w['net']);r['from']['physical_feature']=w['from_feature'];r['to']['physical_feature']=w['to_feature'];r['from']['S_mm']=w['conductor_tip_start_S_mm'];r['to']['S_mm']=w['conductor_tip_end_S_mm'];r['from']['pin_evidence']='SOLDER_PTH_PHYSICAL_FEATURE_AND_CURRENT_XML';r['to']['pin_evidence']='SOLDER_PTH_PHYSICAL_FEATURE_AND_CURRENT_XML';r['identity']='RETAINED_NOMINAL_STATIC_SOLDERED_WIRE';r['branch_group']='C203_PAIR';r['wire_MPN']=cdef['wire']['MPN'];r['AWG']=18;r['cut_length_mm']=caplength[w['id']]['analytic_cut_length_mm'];r['strip_start_mm']=w['strip_start_mm'];r['strip_end_mm']=w['strip_end_mm'];r['shield']='NONE_IN_SOURCE_SINGLE_WIRE';r['protection_chain']='F201 and precharge upstream; capacitor stored energy and transient coordination not qualified';r['source']=[{'path':str(BASE/'power/CAP_HARNESS_DEFINITION_V19.json')},{'path':str(BASE/'results/CAP_HARNESS_PATH_V19.json')}]
        found=[z for g in r1['groups'] for z in g['rows'] if z['id']==w['id']]
        assert found and all(z['T_S_local']==[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]] and sha(Path(z['step_path']))==z['source_sha256'] for z in found)
        r['r1_source_pose_identity_confirmed']=True;r['design_notes']='Nominal source and R1 poses match. Final R2 collision/termination tolerance revalidation remains separate; retained nominal cut length is not a release.';rows.append(r)
    # The four V30 segments are local termination envelopes, never entire battery/CHB wires.
    local=[]
    for m in lug['net_mapping']:
        local.append({'id':m['wire_id'],'near_ref':m['ref'],'net':m['net'],'wire_MPN':lug['wire']['mpn'],'AWG':10,'local_model_length_mm':lug['wire']['total_local_wire_length_mm'],'far_endpoint':None,'full_wire_cut_length_mm':None,'ring_lug_MPN':lug['lug']['mpn'],'strip_length_mm':lug['wire']['strip_length_mm'],'crimp_tool_MPN':lug['tool']['mpn'],'r20_local_segment_ohm':resistance_ohm(lug['wire']['total_local_wire_length_mm'],lug['wire']['R20_max_ohm_m']),'actual_current_A':None,'voltage_drop_V':None,'whole_harness_complete':False})
    for r in rows:
        if not r['active']:continue
        r['missing_fields']=[k for k in ['wire_MPN','load_current_A','cut_length_mm','cut_length_tolerance_mm','strip_start_mm','strip_end_mm','shield','shield_termination'] if r[k] is None]
        r['missing_fields']+=['remote_termination_or_crimp_process','protection_coordination','installed_temperature','as_built_continuity_insulation']
        if r['from']['S_mm'] is None or r['to']['S_mm'] is None:r['missing_fields'].append('mounted_mating_endpoint_and_route')
    errors=circuit_check(rows,pins);assert not errors,errors
    # Explicit forbidden joins, not assumed zero-resistance common grounds.
    forbidden=[['J210.2','J208.2'],['J210.2','J209.2'],['J211.2','J101.4'],['J209.2','U202.6']]
    assert all(pins[a]!=pins[b] for a,b in forbidden)
    circuits=[{'id':'AUX_INPUT','outgoing':'AUX_IN_P','return':'AUX_IN_R','voltage_V':None,'current_A':None,'drop_V':None,'protection':'F202; selected protection/current coordination pending'}, {'id':'AUX_OUTPUT','outgoing':'AUX_OUT_P','return':'AUX_OUT_R','voltage_V':None,'current_A':None,'drop_V':None,'protection':'U207 eFuse; wire and connector derating pending'}, {'id':'STOP_SUPPLY','outgoing':'SC_PWR24','return':'SC_RET','voltage_V':24,'current_A':None,'drop_V':None,'protection':'Existing THN isolation; K1 coil current missing'}, {'id':'C203_PAIR','outgoing':'C203_W_PLUS','return':'C203_W_MINUS','actual_current_A':None,'actual_drop_V':None,'actual_loss_W':None}]
    calculations=[]
    for r in rows:
        if r['id'].startswith('C203_W_'):
            d=electrical_loss(r['cut_length_mm'],cdef['wire']['max_R20_ohm_per_m'],.003)
            calculations.append({'wire_id':r['id'],'scenario':'LEGACY_FIXED_LEAKAGE_3mA_20C_NOT_MEASURED',**d,'current_source':'CAP_HARNESS_ELECTROTHERMAL_V19 leakage_current_scope','actual_current_A':None,'contacts_included':False})
    Rpair=sum(x['R20_upper_ohm'] for x in calculations)
    calculation={'formula':'R20=r20_ohm_per_m*L_mm/1000; drop=I*R; loss=I^2*R; two wire loop=sum(Rout,Rreturn), not double an already summed length', 'temperature_C':20,'scenario_rows':calculations,'C203_pair_3mA':{'R20_upper_ohm':Rpair,'drop_V':.003*Rpair,'loss_W':.003**2*Rpair},'C203_pair_2p4A_reference_only':{'R20_upper_ohm':Rpair,'drop_V':2.4*Rpair,'loss_W':2.4**2*Rpair,'included_in_heat_budget':False,'actual_ripple_spectrum':None},'AUX_actual_drop_V':None,'NTC_actual_drop_V':None,'hot_resistance_qualified':False,'actual_wire_temperature_C':None,'source':str(BASE/'power/CAP_HARNESS_ELECTROTHERMAL_V19.json')}
    read(BASE/'power/CAP_HARNESS_ELECTROTHERMAL_V19.json')
    pairfit=[{'group':'AUX_20AWG','wire':'55A0111-20-9','terminal':'430300007','wire_OD_max_mm':wirefamilies['55A0111-20-9']['OD_mm'][1],'terminal_OD_max_mm':1.85,'OD_margin_mm':1.85-wirefamilies['55A0111-20-9']['OD_mm'][1],'AWG_in_allowed_range':True,'dimensional_fit_candidate':True,'crimp_process_qualified':False}, {'group':'NTC_26AWG','wire':'55A0111-26-9','terminal':'SSHL-002T-P0.2','wire_OD_range_mm':wirefamilies['55A0111-26-9']['OD_mm'],'terminal_OD_range_mm':[.76,1.0],'OD_lower_margin_mm':wirefamilies['55A0111-26-9']['OD_mm'][0]-.76,'OD_upper_margin_mm':1-wirefamilies['55A0111-26-9']['OD_mm'][1],'AWG_in_allowed_range':True,'dimensional_fit_candidate':True,'crimp_process_qualified':False,'observation':'Lower OD margin only 0.002mm; actual insulation diameter and JST approval/crimp validation needed.'}]
    negative=[]
    def neg(name,fn):
        test=copy.deepcopy(rows);fn(test);negative.append({'name':name,'rejected':bool(circuit_check(test,pins))})
    neg('duplicate_wire_id',lambda r:r.append(copy.deepcopy(r[0])))
    neg('positive_wire_to_wrong_return',lambda r:r[0]['to'].update(native_key='J205.1'))
    neg('missing_pin_identity',lambda r:r[0]['from'].update(native_key='J200.999'))
    neg('zero_cut_length_unknown_filled',lambda r:r[0].update(cut_length_mm=0))
    neg('nan_cut_length',lambda r:r[0].update(cut_length_mm=float('nan')))
    neg('release_with_missing_inputs',lambda r:r[0].update(manufacturing_release=True))
    neg('ground_rs422_flight_promotion',lambda r:next(x for x in r if x['id']=='S01').update(flight_qualified=True))
    neg('unsupported_temperature_pass',lambda r:r[0].update(wire_temperature_qualified=True))
    neg('AUX_return_leg_removed',lambda r:next(x for x in r if x['id']=='AUX_OUT_R').update(active=False))
    neg('NTC_return_leg_removed',lambda r:next(x for x in r if x['id']=='NTC_1_R').update(active=False))
    neg('flags_only_release_bypasses_unknown_fields',lambda r:r[0].update(manufacturing_release=True,endpoint_termination_complete=True,route_verified_current_host=True,protection_coordination_verified=True,process_qualified=True,load_case_complete=True))
    neg('null_native_endpoint_key',lambda r:r[0]['from'].update(native_key=None))
    neg('string_false_active',lambda r:r[0].update(active='false'))
    # Dimensional and null arithmetic guards are independent of actual pending harness length.
    negative.append({'name':'mm_to_m_factor','rejected':math.isclose(resistance_ohm(1000,0.1),.1)})
    negative.append({'name':'unknown_current_no_zero_loss','rejected':electrical_loss(100,.1,None)['loss_W'] is None})
    negative.append({'name':'unknown_length_no_zero_resistance','rejected':electrical_loss(None,.1,1)['R20_upper_ohm'] is None})
    for name,args in [('boolean_resistance',(100,True,1)),('nan_resistance',(100,float('nan'),1)),('negative_current',(100,.1,-1)),('boolean_current',(100,.1,True)),('nan_current',(100,.1,float('nan'))),('boolean_length',(True,.1,1))]:
        try:electrical_loss(*args)
        except ValueError:negative.append({'name':name,'rejected':True})
        else:negative.append({'name':name,'rejected':False})
    try:require_digest(verification_path,'0'*64)
    except ValueError:negative.append({'name':'handoff_verification_digest_mismatch','rejected':True})
    else:negative.append({'name':'handoff_verification_digest_mismatch','rejected':False})
    assert all(n['rejected'] for n in negative)
    rawgap=read(BASE/'results/electrical_selection_20260917/SELECTION_GAPS_UPDATE2_20260917.json')
    selected={'schema':'R2_HARNESS_SELECTION_V1','wire_families':wirefamilies,'rating_scope':'55A0111 RevR page2 voltage600Vrms at sea level; cold bend test at-65C is not an installed lifetime/space qualification. Product temperatures and connector limits require end-use validation.','fit_checks':pairfit,'NTC_mating_BOM':{'GHR-06V-S':1,'SSHL-002T-P0.2':6},'AUX_mating_BOM':{'430250200':3,'430300007':6},'procurement_approved':False,'flight_qualified':False,'new_design':'12 new external conductors are explicitly mapped from current nets; endpoint poses and cut lists await mounting. Four V30 local segments kept separate.'}
    write('inputs/ELECTRICAL_PUBLIC_SOURCES.json',public);write('inputs/HARNESS_SELECTION_R2.json',selected)
    write('inputs/ELECTRICAL_CURRENT_BASELINE.json',{'schema':'R2_CURRENT_ELECTRICAL_BASELINE','handoff_latest':str(BASE/'coupled_closure/HANDOFF_LATEST.json'),'current_xml':str(xml),'current_xml_sha256':sha(xml),'current_refs':len(components),'current_pin_records':len(pinrows),'components':list(components.values()),'pin_records':pinrows,'old_v36_root_xml_is_stale':True,'whole_design_complete':False})
    write('inputs/HARNESS_CONNECTION_MATRIX.json',{'schema':'R2_HARNESS_CONNECTION_MATRIX_V1','source_xml':str(xml),'source_xml_sha256':sha(xml),'rows':rows,'local_segments_not_whole_wires':local,'circuits':circuits,'forbidden_direct_join_pairs':forbidden,'unknown_policy':'JSON null is unknown, never zero; net parity is not physical pin-mating/ampacity/continuity qualification.','manufacturing_release':False})
    write('inputs/HARNESS_3D_ENDPOINTS.json',{'schema':'R2_HARNESS_ENDPOINT_POSES','frame':'S_mm','C203_wire_tip_endpoints':[{'id':w['id'],'from_feature':w['from_feature'],'to_feature':w['to_feature'],'from_S_mm':w['conductor_tip_start_S_mm'],'to_S_mm':w['conductor_tip_end_S_mm'],'nominal_cut_length_mm':caplength[w['id']]['analytic_cut_length_mm'],'r1_pose_preserved':True,'final_R2_interference_verified':False} for w in cdef['wires']],'CHB_terminal_faces':chbp,'PCB_connector_pads':connector_rows,'PCB_host_transforms':None,'scope':'Solder tips and terminal PCB faces explicitly distinguished from mating pin/cable exit. Board coordinates are local only.'})
    write('results/ELECTRICAL_RESISTANCE_SCREEN.json',calculation)
    flat=[]
    for r in rows:
        flat.append({'wire_id':r['id'],'active':r['active'],'from_endpoint':r['from']['endpoint'],'from_ref_pin':r['from']['native_key'],'from_MPN':r['from']['connector_or_component_MPN'],'from_housing':r['from']['mating_housing_MPN'],'from_contact':r['from']['contact_MPN'],'to_endpoint':r['to']['endpoint'],'to_ref_pin':r['to']['native_key'],'to_MPN':r['to']['connector_or_component_MPN'],'to_housing':r['to']['mating_housing_MPN'],'to_contact':r['to']['contact_MPN'],'net':r['net'],'identity':r['identity'],'voltage_V':r['nominal_voltage_V'],'current_A':r['load_current_A'],'wire_MPN':r['wire_MPN'],'AWG':r['AWG'],'cut_length_mm':r['cut_length_mm'],'cut_tolerance_mm':r['cut_length_tolerance_mm'],'strip_start_mm':r['strip_start_mm'],'strip_end_mm':r['strip_end_mm'],'shield':r['shield'],'shield_termination':r['shield_termination'],'protection':r['protection_chain'],'missing_fields':r['missing_fields'],'source':r['source'],'manufacturing_release':False})
    writecsv('docs/ELECTRICAL_CONNECTION_MATRIX.csv',flat,list(flat[0]));writecsv('docs/ELECTRICAL_CURRENT_PIN_NET.csv',pinrows,list(pinrows[0]));writecsv('docs/ELECTRICAL_CURRENT_COMPONENTS.csv',list(components.values()),list(next(iter(components.values()))))
    writecsv('docs/ELECTRICAL_LOCAL_LUG_SEGMENTS.csv',local,list(local[0]))
    report={'schema':'R2_ELECTRICAL_HARNESS_CHECKS_V1','generated_utc':datetime.now(timezone.utc).isoformat(),'verdict':'PASS_SCOPED_SOURCE_NET_AND_DIMENSION_COMPILATION__HARNESS_MANUFACTURING_HOLD','current_xml_refs':len(components),'current_xml_pin_records':len(pinrows),'active_master_rows':sum(r['active'] for r in rows if r['id'] in {m['wire_id'] for m in master}),'compiled_rows':len(rows),'active_rows':sum(r['active'] for r in rows),'new_AUX_conductors':6,'new_NTC_conductors':6,'retained_C203_wires':2,'local_lug_segments_not_complete_wires':4,'active_connection_net_conflicts':errors,'mapped_pad_net_parity':padread['mapped_pad_net_parity'],'board_only_PORT_pads_without_schematic_ref':4,'forbidden_direct_ground_joins_separated':True,'negative_controls':negative,'known_nominal_cut_lengths':sum(r['cut_length_mm'] is not None for r in rows),'known_actual_currents':0,'fully_released_harness_rows':0,'rating_gap_count_preserved':rawgap['changes']['rating']['after'],'sources':SOURCES,'source_files_unchanged':all(sha(Path(p))==s for p,s in SOURCES.items()),'whole_electrical_design_complete':False,'manufacturing_release':False,'power_on_authorized_by_this_report':False,'flight_qualified':False}
    assert report['source_files_unchanged']
    write('results/ELECTRICAL_HARNESS_CHECKS.json',report)
    print(json.dumps({k:v for k,v in report.items() if k in ['verdict','compiled_rows','active_rows','current_xml_refs','current_xml_pin_records','known_nominal_cut_lengths','fully_released_harness_rows','source_files_unchanged']},ensure_ascii=False))

if __name__=='__main__':main()
