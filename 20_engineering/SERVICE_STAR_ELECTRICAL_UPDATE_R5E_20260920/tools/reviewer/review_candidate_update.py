"""Independent candidate data and analytical-screen review; no builder imports.

Engineering HOLD flags are required even when arithmetic passes.
"""
from pathlib import Path
from decimal import Decimal
from itertools import product
import hashlib
import json
import re
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[4]
D=ROOT/'20_engineering/SERVICE_STAR_ELECTRICAL_UPDATE_R5E_20260920'
R=D/'results/reviewer'
paths=[D/p for p in ['inputs/SELECTION_UPDATES.json','inputs/LOCKED_SYSTEM_249.xml','bom/ELECTRICAL_SELECTION_BOM_R5E.json','results/SELECTION_CALCULATIONS.json','results/ELECTROTHERMAL_INPUT_UPDATE.json','results/BUILD_RECEIPT.json','results/GAP_DISPOSITION_45.json']]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
before={p.relative_to(ROOT).as_posix():sha(p) for p in paths}
u=read(paths[0]); by_ref={x['ref']:x for x in u}
xml=ET.parse(paths[1]).getroot(); refs={c.attrib['ref'] for c in xml.findall('components/comp')}
bom=read(paths[2]); calc=read(paths[3]); heat=read(paths[4]); build=read(paths[5]); gaps=read(paths[6])
checks=[]
def ck(name,actual,expected,note=''):
    passed=(actual==expected)
    checks.append({'name':name,'actual':actual,'expected':expected,'pass':passed,'note':note})
def near(name,actual,expected,note=''):
    checks.append({'name':name,'actual':actual,'expected':float(expected),'pass':abs(float(actual)-float(expected))<=1e-10,'note':note})
ck('authoritative_xml_sha',sha(paths[1]),'90497ad91d4b8ec2c39e6eda819b94e3fbcf9f908861aae22e6c90c5bf1a1939')
ck('unique_update_refs',len(by_ref),len(u))
ck('historical_gap_set',sorted(by_ref),sorted(x['ref'] for x in gaps['items']))
ck('BOM_ref_set',sorted(x['ref'] for x in bom),sorted(refs))
ck('no_duplicate_BOM_refs',len({x['ref'] for x in bom}),len(bom))
ck('candidate_procurement_flags_closed',all(x['procurement_release'] is False and x['flight_qualified'] is False for x in bom),True)
ck('release_flags_closed',all(build[k] is False for k in ['ready_to_power','manufacturing_release','flight_ready']),True)
bb={x['ref']:x for x in bom}
for ref in ['J200','J201','J202','J203','J210']:
    ck(ref+'_procurement_piece_count',bb[ref]['candidate_piece_qty'],0)
ck('R305_composite_piece_count',bb['R305']['candidate_piece_qty'],2)
ck('R305_no_invented_single_MPN',bb['R305']['candidate_MPN'],'')
ck('R305_PCB_not_claimed',calc['R305']['PCB_updated'],False)
ck('R305_trip_guarantee_not_claimed',calc['R305']['guaranteed_trip_range_V'],None)
ck('R305_topology_not_applied_in_BOM',bb['R305']['ecad_applied_this_round'],False)
for ref in ['C209','C210','C301','C302','C305']:
    ck(ref+'_effective_C_HOLD','HOLD' in by_ref[ref]['status'],True)
for ref in ['C302','C305']:
    ck(ref+'_not_effectively_qualified',calc[ref]['effective_min_verified'],False)

# TI TPS2660 Rev.G p1,7-8: adjustable current-limit typical range, not load rating.
ck('U207_forward_supply_from_primary',by_ref['U207']['rating']['forward_operating_supply_V'],[4.2,60], 'TI SLVSDG2G p1, p7')
ck('U207_current_limit_from_primary',by_ref['U207']['rating']['adjustable_limit_A'],[0.1,2.23], 'TI SLVSDG2G p1; at RILIM=5.36k nominal2.23A, guaranteed max2.35A')
ck('U207_RILIM_range_from_primary',by_ref['U207']['rating']['R_ILIM_allowed_kohm'],[5.36,120], 'TI SLVSDG2G p6')

def dec(v):return Decimal(str(v))
r305=by_ref['R305']['rating']; r306=by_ref['R306']['rating']
parts=r305['proposed_parts']; rA,rB=[dec(x['R_ohm']) for x in parts]
rt=dec(r305['initial_tolerance_fraction']); rb=dec(r306['resistance_ohm']); rbt=dec(r306['initial_tolerance_fraction'])
vref=Decimal('.4')
near('R305_series_nominal',calc['R305']['series_sum_ohm'],rA+rB)
near('R305_nominal_ideal_trip',calc['R305']['nominal_ideal_trip_V'],vref*(1+(rA+rB)/rb))
corner_map={(x['R305A_sign'],x['R305B_sign'],x['R306_sign']):x for x in calc['R305']['independent_initial_tolerance_corners']}
ck('R305_eight_independent_corners',sorted(corner_map),sorted(product([-1,1],repeat=3)))
for a,b,c in product([-1,1],repeat=3):
    expected=vref*(1+(rA*(1+a*rt)+rB*(1+b*rt))/(rb*(1+c*rbt)))
    near('R305_corner_'+str((a,b,c)),corner_map[(a,b,c)]['ideal_trip_V'],expected)

c301=by_ref['C301']['rating']
near('C301_initial_min',calc['C301']['candidate_initial_lower_uF'],dec(c301['capacitance_uF'])*(1-dec(c301['initial_tolerance_fraction'])))
for ref in ['C302','C305']:
    rt=by_ref[ref]['rating']
    expected=dec(rt['capacitance_uF'])*(1-dec(rt['initial_tolerance_fraction']))*Decimal('.85')
    near(ref+'_initial_TCC_min',calc[ref]['initial_and_TCC_lower_uF_without_bias_aging'],expected)
    required=dec(calc[ref]['required_effective_min_uF'])
    near(ref+'_required_retention',calc[ref]['remaining_bias_and_aging_retention_min_fraction'],required/expected)
cc=[by_ref[x]['rating'] for x in ['C209','C210']]
near('C209_210_initial_TCC_upper',calc['C209_C210']['initial_tolerance_and_positive_TCC_screen_upper_uF'],sum(dec(x['capacitance_uF'])*(1+dec(x['initial_tolerance_fraction']))*Decimal('1.22') for x in cc))
near('C209_210_initial_TCC_lower',calc['C209_C210']['initial_tolerance_and_negative_TCC_before_DC_bias_lower_uF'],sum(dec(x['capacitance_uF'])*(1-dec(x['initial_tolerance_fraction']))*Decimal('.78') for x in cc))

ck('R202_resistance_from_primary',heat['R202']['R25_ohm'],.0005,'Vishay WSLP2726 p1, L5000 code')
ck('R201_resistance_from_primary',heat['R201']['R25_ohm'],.002,'Vishay WSLP2726 p1, 2L000 code')
ck('R202_component_TCR',heat['R202']['component_TCR_per_K'],75e-6)
for row in heat['scenarios']:
    i=dec(row['current_A'])
    r1=dec(heat['R201']['R25_ohm']);r2=dec(heat['R202']['R25_ohm'])
    near('shunt_sum_'+str(row['current_A'])+'A',row['sum_W'],i*i*(r1+r2))
    near('shunt_increment_'+str(row['current_A'])+'A',row['delta_W'],i*i*(r2-Decimal('.0002')))
near('20A_100C_uniform_resistance_screen',heat['20A_100C_resistance_scenario_upper_W'],Decimal(20)**2*Decimal('.0025')*Decimal('1.01')*(1+Decimal('0.000075')*(100-25)))
for field in ['actual_current_A','actual_current_RMS_A','actual_terminal_temperature_C','R_element_ambient_K_W','whole_board_dissipation_W','host_thermal_contact_K_W']:
    ck('unknown_'+field,heat[field],None)
ck('no_installed_temperature_PASS',heat['installed_temperature_PASS'],False)
after={p.relative_to(ROOT).as_posix():sha(p) for p in paths}
ck('reviewed_files_stable_during_check',after,before)
out={'schema':'R5E_INDEPENDENT_SELECTION_CHECKS_V1','checks':checks,'passed':sum(x['pass'] for x in checks),'total':len(checks),'failed':[x for x in checks if not x['pass']],
    'reviewed_hashes':before,'reviewed_hashes_after':after,'engineering_release':False,
    'scope':'Candidate scope/accounting, selected primary datasheet claims and independent Decimal recomputation; not complete component qualification, hardware tests, or full PCB audit.'}
(R/'INDEPENDENT_SELECTION_CHECKS.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'passed':out['passed'],'total':out['total'],'failed':out['failed']},ensure_ascii=False,indent=2))
