"""Rebuild the R5E selection projection. Reads sealed designs; never writes ECAD.

Run from anywhere with Python 3.11+. Fail closed on the locked netlist or BOM.
R5E is a candidate-selection release, not procurement or energization permission.
"""
from pathlib import Path
import csv
import hashlib
import itertools
import json
import shutil
import xml.etree.ElementTree as ET

D = Path(__file__).resolve().parents[1]
ROOT = D.parents[1]
IMPL = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation'
LEGACY = IMPL / 'results/electrical_selection_20260917'
XML = IMPL / 'results/stop_v36/pcb/thermal_filter_20260916/native_20260916_a/wp10_system.xml'
XML_SHA = '90497ad91d4b8ec2c39e6eda819b94e3fbcf9f908861aae22e6c90c5bf1a1939'
BOM_SHA = '80a24ab6da5992ddc9223496b78359127dec6980f0b49671dee2256f6fec1759'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def write(rel, x):
    p = D / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(x, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
def csvwrite(rel, rows):
    p = D / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:
            w.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in r.items()})
def require(ok, message):
    if not ok: raise ValueError(message)

def check_input(xml_path=XML, expected=XML_SHA):
    require(sha(xml_path) == expected, 'Netlist SHA mismatch; source rejected')
    root = ET.parse(xml_path).getroot()
    comps = {c.attrib['ref']: c for c in root.findall('./components/comp')}
    require(len(comps) == 249, 'Netlist component count differs')
    require(len(root.findall('./nets/net/node')) == 795, 'Pin-net pair count differs')
    require(sha(LEGACY / 'SELECTION_BOM_V36.csv') == BOM_SHA, 'Historical BOM SHA mismatch')
    return root, comps

def build():
    root, comps = check_input()
    old = list(csv.DictReader((LEGACY / 'SELECTION_BOM_V36.csv').open(encoding='utf-8-sig', newline='')))
    require({r['ref'] for r in old} == set(comps), 'Historical BOM/netlist reference mismatch')
    ann = {}
    for n in ['STOP_RATING_ANNOTATION_20260917.json', 'SYSTEM_RATING_ANNOTATION_20260917.json']:
        for r in read(LEGACY / n)['rows']: ann[r['ref']] = r
    oldgaps = read(LEGACY / 'SELECTION_GAPS_UPDATE2_20260917.json')['changes']['rating']['remaining_refs']
    src = read(D / 'inputs/PRIMARY_SOURCES.json')
    selected = read(D / 'inputs/SELECTION_UPDATES.json')
    require(len(selected) == len({r['ref'] for r in selected}), 'Duplicate selection reference')
    require(set(oldgaps) == {r['ref'] for r in selected}, '45-gap disposition must be exhaustive')
    update = {r['ref']: r for r in selected}
    for r in selected:
        require(r['ref'] in comps, 'Selection has unknown reference')
        require(r['source_id'] in src or r['source_id'] == 'PROJECT_CLASSIFICATION', 'Missing source')
        require(r['procurement_release'] is False, 'Candidate cannot release procurement')
    # Byte-preserved evidence snapshot, not an edited netlist or schematic.
    (D / 'inputs').mkdir(exist_ok=True)
    shutil.copyfile(XML, D / 'inputs/LOCKED_SYSTEM_249.xml')
    sources = [{'path': str(XML.relative_to(ROOT)).replace('\\', '/'), 'sha256': sha(XML)},
               {'path': str((LEGACY / 'SELECTION_BOM_V36.csv').relative_to(ROOT)).replace('\\', '/'), 'sha256': BOM_SHA}]
    # Keep the source annotations intact, including their low-confidence evidence classes.
    for n in ['STOP_RATING_ANNOTATION_20260917.json', 'SYSTEM_RATING_ANNOTATION_20260917.json', 'SELECTION_GAPS_UPDATE2_20260917.json']:
        sources.append({'path': str((LEGACY / n).relative_to(ROOT)).replace('\\', '/'), 'sha256': sha(LEGACY / n)})
    for sid, s in src.items():
        if s.get('local_origin'):
            p = ROOT / s['local_origin']
            require(p.exists(), 'Missing local primary source ' + sid)
            target = D / 'docs/hardware/datasheets' / p.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, target)
            s.update(local_archive=str(target.relative_to(D)).replace('\\', '/'), sha256=sha(target))
            sources.append({'path': str(p.relative_to(ROOT)).replace('\\', '/'), 'sha256': sha(p)})
    write('results/PRIMARY_SOURCE_ARCHIVE.json', src)
    board_audit = read(D / 'results/reviewer/LOCKED_249_XML_BOARD_AUDIT.json')
    physical = {ref: b for b, v in board_audit['boards'].items() for ref in v['xml_refs']}
    rows, gap_disposition, eco = [], [], []
    for r in old:
        ref = r['ref']; a = ann.get(ref, {}); u = update.get(ref)
        out = {
            'ref': ref, 'source_class': r['class_'], 'current_class': r['class_'],
            'actual_board': physical.get(ref, 'NOT_IN_THREE_AUDITED_BOARDS'),
            'source_value': comps[ref].findtext('value') or '',
            'source_MPN': r['MPN'], 'candidate_MPN': r['MPN'], 'manufacturer': r['manufacturer'],
            'source_footprint': comps[ref].findtext('footprint') or '',
            'candidate_footprint': comps[ref].findtext('footprint') or '',
            'symbol_qty': 1, 'candidate_piece_qty': 1 if r['class_'] == 'REAL_PART_CANDIDATE' else 0,
            'rating': a.get('rating', {}), 'rating_evidence_class': a.get('rating_source_class', 'NOT_APPLICABLE'),
            'source': r['source'], 'substitution_limit': a.get('substitution_limit', ''),
            'selection_status': 'INHERITED_NOT_REQUALIFIED',
            'open_items': a.get('named_gaps', []),
            'ecad_applied_this_round': False, 'procurement_release': False, 'flight_qualified': False,
        }
        if u:
            out.update(current_class=u['class'], candidate_MPN=u.get('MPN') or '', manufacturer=u.get('manufacturer') or '',
                       candidate_footprint=u.get('footprint') or '', candidate_piece_qty=u['piece_qty'],
                       rating=u['rating'], rating_evidence_class=u['evidence_class'],
                       source=src[u['source_id']]['url'] if u['source_id'] in src else 'PROJECT_SOURCE_NETLIST_AND_PCB',
                       substitution_limit=u['substitution_limit'], selection_status=u['status'],
                       open_items=u['open_items'])
            gap_disposition.append({'ref': ref, 'disposition': u['status'], 'MPN': u.get('MPN'),
                                    'source_id': u['source_id'], 'remaining': u['open_items']})
            eco.append({'ref': ref, 'source_value': out['source_value'], 'source_footprint': out['source_footprint'],
                        'candidate_MPN': out['candidate_MPN'], 'candidate_footprint': out['candidate_footprint'],
                        'action': u['ecad_action'], 'status': 'NOT_APPLIED', 'preconditions': u['open_items']})
        if ref == 'U301':
            # Exact code already present in the locked source Value; do not infer a new IC.
            require(out['source_value'] == 'LT3013EDE#PBF', 'U301 source identity changed')
            out.update(candidate_MPN='LT3013EDE#PBF', manufacturer='Analog Devices',
                       candidate_footprint='WP10_INPUT:LT3013_DE12_EP13_3x4_Pin1LeftTop',
                       source='https://www.analog.com/media/en/technical-documentation/data-sheets/3013fe.pdf',
                       selection_status='STRUCTURED_MPN_RECOVERED_FROM_LOCKED_SOURCE_VALUE',
                       open_items=['Same exact IC as U205; new U301 placement and pin-map/thermal implementation remain open'])
            eco.append({'ref': ref, 'source_value': out['source_value'], 'source_footprint': '',
                        'candidate_MPN': out['candidate_MPN'], 'candidate_footprint': out['candidate_footprint'],
                        'action': 'Recover exact source Value into MPN field; reuse exact U205 footprint only after pin-map and placement checks',
                        'status': 'NOT_APPLIED', 'preconditions': out['open_items']})
        rows.append(out)
    csvwrite('bom/ELECTRICAL_SELECTION_BOM_R5E.csv', rows)
    write('bom/ELECTRICAL_SELECTION_BOM_R5E.json', rows)
    csvwrite('bom/ECAD_ECO_R5E.csv', eco)
    write('results/GAP_DISPOSITION_45.json', {
        'schema': 'R5E_GAP_DISPOSITION_V1', 'historical_gap_count': 45,
        'disposition_count': len(gap_disposition),
        'semantics': 'Addressed is not electrically qualified. Ref-level MPN/evidence update and engineering acceptance are separate.',
        'items': gap_disposition, 'all_engineering_gaps_closed': False,
        'whole_design_complete': False, 'ready_to_power': False, 'flight_ready': False,
    })
    # Expand R305 for candidate costing only; the original ref remains one logical element.
    candidates = []
    for r in rows:
        if r['current_class'] != 'REAL_PART_CANDIDATE': continue
        if r['ref'] == 'R305':
            for ref, mpn, fp, ohm in [('R305A_PROPOSED', 'TNPW0805665KBEEA', 'Resistor_SMD:R_0805_2012Metric', 665000),
                                      ('R305B_PROPOSED', 'TNPW060311K0BEEA', 'Resistor_SMD:R_0603_1608Metric', 11000)]:
                candidates.append({'logical_ref': 'R305', 'candidate_ref': ref, 'MPN': mpn, 'qty': 1,
                                   'footprint': fp, 'status': 'ECO_NOT_IMPLEMENTED', 'resistance_ohm': ohm,
                                   'price': None, 'stock': None, 'procurement_release': False})
        else:
            candidates.append({'logical_ref': r['ref'], 'candidate_ref': r['ref'], 'MPN': r['candidate_MPN'], 'qty': 1,
                               'footprint': r['candidate_footprint'], 'status': r['selection_status'],
                               'resistance_ohm': None, 'price': None, 'stock': None, 'procurement_release': False})
    csvwrite('bom/PROCUREMENT_CANDIDATES_NOT_RELEASED.csv', candidates)
    # R202 correction. Component TCR (not alloy TCR), referenced to nominal at 25 C.
    scenarios = []
    for current in [5, 10, 15, 20]:
        scenarios.append({'current_A': current, 'current_kind': 'CONSTANT_DC_SCENARIO',
                          'R201_W': current**2 * .002, 'R202_W': current**2 * .0005,
                          'sum_W': current**2 * .0025, 'old_sum_W': current**2 * .0022,
                          'delta_W': current**2 * .0003})
    thermal = {
        'schema': 'R5E_ELECTROTHERMAL_INPUTS_V1',
        'replaces_only': 'R201/R202 shunt identity and I-squared-R in future V36 thermal calculations; historical results immutable',
        'R201': {'MPN': 'WSLP27262L000FEA', 'R25_ohm': .002, 'tolerance_fraction': .01, 'component_TCR_per_K': 75e-6},
        'R202': {'MPN': 'WSLP2726L5000FEA', 'R25_ohm': .0005, 'tolerance_fraction': .01, 'component_TCR_per_K': 75e-6,
                 'height_mm_nominal': 2.95, 'height_mm_tolerance': .2, 'R_element_terminal_K_W': 6,
                 'rating_W_at_terminal100C_with_required_PCB_cooling': 12},
        'scenarios': scenarios,
        '20A_100C_resistance_scenario_upper_W': 20**2*.0025*1.01*(1+75e-6*75),
        'temperature_scenario_note': '100 C is assumed uniform resistor temperature, not solved terminal/junction/board temperature. Initial tolerance and TCR combined multiplicatively.',
        'actual_current_A': None, 'actual_current_RMS_A': None, 'actual_terminal_temperature_C': None,
        'R_element_ambient_K_W': None, 'whole_board_dissipation_W': None,
        'host_thermal_contact_K_W': None, 'installed_temperature_PASS': False,
        'old_temperature_result_reusable': False, 'whole_star_material_mass_recomputed': False,
    }
    write('results/ELECTROTHERMAL_INPUT_UPDATE.json', thermal)
    csvwrite('results/SHUNT_LOSS_SCENARIOS.csv', scenarios)
    corner = [{'R305A_sign': a, 'R305B_sign': b, 'R306_sign': c,
               'Rhigh_ohm': 665000*(1+a*.001)+11000*(1+b*.001),
               'ideal_trip_V': .4*(1+(665000*(1+a*.001)+11000*(1+b*.001))/(10000*(1+c*.001)))}
              for a, b, c in itertools.product([-1, 1], repeat=3)]
    calculations = {
        'schema': 'R5E_SELECTION_CALCULATIONS_V1',
        'R305': {'implementation': 'CANDIDATE_ONLY', 'series_sum_ohm': 676000,
                 'nominal_ideal_trip_V': 27.44, 'independent_initial_tolerance_corners': corner,
                 'ideal_trip_min_max_V': [min(c['ideal_trip_V'] for c in corner), max(c['ideal_trip_V'] for c in corner)],
                 'threshold_reference_V': .4, 'reference_tolerance_included': False, 'comparator_bias_hysteresis_TCR_included': False,
                 'guaranteed_trip_range_V': None, 'schematic_new_node': 'R305_SERIES_MID_PROPOSED', 'PCB_updated': False},
        'C301': {'candidate_initial_lower_uF': 1.5*.95, 'required_effective_min_uF': 1,
                 'remaining_retention_min_fraction': 1/(1.5*.95), 'combined_environmental_retention_verified': False},
        'C302': {'initial_and_TCC_lower_uF_without_bias_aging': 22*.8*.85, 'required_effective_min_uF': 10,
                 'remaining_bias_and_aging_retention_min_fraction': 10/(22*.8*.85), 'effective_min_verified': False},
        'C305': {'initial_and_TCC_lower_uF_without_bias_aging': 2.2*.9*.85, 'required_effective_min_uF': 1,
                 'remaining_bias_and_aging_retention_min_fraction': 1/(2.2*.9*.85), 'effective_min_verified': False},
        'C209_C210': {'nominal_sum_uF': 13.6, 'initial_tolerance_upper_uF': 16.32,
                     'initial_tolerance_and_positive_TCC_screen_upper_uF': 13.6*1.2*1.22,
                     'initial_tolerance_and_negative_TCC_before_DC_bias_lower_uF': 13.6*.8*.78,
                     'old_16p32uF_is_initial_tolerance_only': True, 'DC_bias_and_aging_included': False,
                     'actual_effective_total_uF': None, 'STOP_other_input_capacitance_uF': None, 'THN_transient_stability_PASS': False},
        'all_results_scope': 'Analytical screens using named candidate component parameters, not hardware characterization or closed-loop validation',
    }
    write('results/SELECTION_CALCULATIONS.json', calculations)
    summary = {
        'schema': 'R5E_BUILD_RECEIPT_V1', 'status': 'CANDIDATE_SELECTION_UPDATED__ENGINEERING_HOLDS_RETAINED',
        'source_xml_components': len(comps), 'source_pin_net_pairs': len(root.findall('./nets/net/node')),
        'BOM_symbol_rows': len(rows), 'real_candidate_logical_refs': sum(r['current_class']=='REAL_PART_CANDIDATE' for r in rows),
        'candidate_physical_pieces_including_unimplemented_R305_split': len(candidates),
        'historical_gap_dispositions': len(selected),
        'IC_rating_updates': sum(u['kind']=='IC_RATING' for u in selected),
        'passive_direct_candidates': sum(u['kind']=='PASSIVE' for u in selected),
        'passive_composite_ECO': sum(u['kind']=='COMPOSITE_ECO' for u in selected),
        'project_interface_or_fabrication_reclassifications': sum(u['kind']=='PROJECT_BOUNDARY' for u in selected),
        'supplemental_structured_MPN_recovery_refs': ['U301'],
        'missing_single_MPN_real_refs': [r['ref'] for r in rows if r['current_class']=='REAL_PART_CANDIDATE' and not r['candidate_MPN']],
        'source_paths_locked': sources, 'ready_to_power': False, 'manufacturing_release': False, 'flight_ready': False,
        'current_CAD': 'SERVICE_STAR_INTERNAL_LAYOUT_R4_20260920; no geometry update by R5E',
        'independent_review': 'BUILDER_RECEIPT_ONLY__SEE_results/RELEASE_STATUS.json_FOR_FINAL_SCOPE',
        'ecad_applied_this_round_field_semantics': 'Functional value, footprint and topology changes only; separate candidate custom-property annotations are audited in ECAD_CANDIDATE_VERIFICATION.json',
    }
    write('results/BUILD_RECEIPT.json', summary)
    print(json.dumps({k:v for k,v in summary.items() if k!='source_paths_locked'}, ensure_ascii=False, indent=2))

if __name__ == '__main__': build()
