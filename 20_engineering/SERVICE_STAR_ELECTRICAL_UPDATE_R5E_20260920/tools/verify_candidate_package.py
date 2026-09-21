"""Verify native candidate annotations and preservation of locked electrical data.

Never edits EDA. Its stale-source negative control only reads existing evidence.
"""
from build_electrical_update import D, ROOT, IMPL, check_input, read, write, sha
import xml.etree.ElementTree as ET

checks = []
def check(name, ok, detail=None):
    checks.append({'name': name, 'pass': bool(ok), 'detail': detail})

def components(tree):
    return {c.get('ref'): c for c in tree.findall('./components/comp')}

def field_map(c, candidate=False):
    return {e.get('name'): e.text or '' for e in c.findall('./fields/field')
            if e.get('name', '').startswith('R5E_') == candidate}

def properties(c, candidate=False):
    return {e.get('name'): e.get('value', '') for e in c.findall('./property')
            if e.get('name', '').startswith('R5E_') == candidate}

def core(c):
    return {'value':c.findtext('value') or '', 'footprint':c.findtext('footprint') or '',
            'datasheet':c.findtext('datasheet') or '', 'description':c.findtext('description') or '',
            'fields':field_map(c), 'properties':properties(c),
            'libsource':c.find('libsource').attrib, 'sheetpath':c.find('sheetpath').attrib,
            'tstamps':c.findtext('tstamps'),
            'units':[(u.get('name'), sorted(p.get('num') for p in u.findall('./pins/pin')))
                     for u in c.findall('./units/unit')]}

def pin_nets(tree):
    return sorted((net.get('name'), tuple(sorted(node.attrib.items())))
                  for net in tree.findall('./nets/net') for node in net.findall('./node'))

base, _ = check_input()
candidate_path=D/'results/ECAD_CANDIDATE.xml'
new=ET.parse(candidate_path).getroot()
oldc, newc = components(base), components(new)
check('unique_reference_set_249', len(newc)==249 and set(oldc)==set(newc))
check('pin_net_pairs_795_unchanged', len(pin_nets(new))==795 and pin_nets(base)==pin_nets(new))
changes=[r for r in oldc if r not in newc or core(oldc[r])!=core(newc[r])]
check('all_original_component_semantics_unchanged', not changes, changes)
plan=read(D/'inputs/ECAD_MCP_EDIT_PLAN.json')
expected={r:v['properties'] for sheet in plan['sheets'].values() for r,v in sheet.items()}
actual={r:field_map(c,True) for r,c in newc.items() if field_map(c,True)}
check('exact_46_annotated_refs', set(actual)==set(expected) and len(actual)==46)
for ref, props in expected.items():
    check('candidate_properties_'+ref, actual.get(ref)==props and properties(newc[ref],True)==props)
check('C301_candidate_value_distinct_from_source', newc['C301'].findtext('value')=='1uF_100V_EFFECTIVE_MIN1uF'
      and actual['C301']['R5E_CandidateValue']=='1.5uF 100V +/-5%')
negative={'path':str((IMPL/'ecad/revisions/v36/wp10_system.xml').relative_to(ROOT)).replace('\\','/')}
try:
    check_input(IMPL/'ecad/revisions/v36/wp10_system.xml')
    negative.update(rejected=False)
except ValueError as exc:
    negative.update(rejected=True, reason=str(exc))
check('239_ref_stale_source_rejected', negative['rejected'], negative)
source_checks=[]
build=read(D/'results/BUILD_RECEIPT.json')
for s in build['source_paths_locked']:
    source_checks.append({'path':s['path'], 'sha256':sha(ROOT/s['path']), 'unchanged':sha(ROOT/s['path'])==s['sha256']})
for s in read(D/'results/reviewer/SCHEMATIC_SOURCE_HASH_AUDIT.json')['schematics']:
    source_checks.append({'path':s['path'], 'sha256':sha(ROOT/s['path']), 'unchanged':sha(ROOT/s['path'])==s['expected']})
for s in read(D/'results/reviewer/LOCKED_249_XML_BOARD_AUDIT.json')['boards'].values():
    source_checks.append({'path':s['path'], 'sha256':sha(ROOT/s['path']), 'unchanged':sha(ROOT/s['path'])==s['sha256']})
check('locked_sources_schematics_boards_unchanged', all(s['unchanged'] for s in source_checks))
bom=read(D/'bom/ELECTRICAL_SELECTION_BOM_R5E.json')
check('249_BOM_rows_match_source_refs', len(bom)==249 and {r['ref'] for r in bom}==set(oldc))
check('MPNs_preserved_in_annotations', all(actual[r['ref']]['R5E_CandidateMPN']==r['candidate_MPN']
      for r in bom if r['ref'] in actual and r['candidate_MPN']))
check('no_procurement_or_flight_release', all(r['procurement_release'] is False and r['flight_qualified'] is False for r in bom))
check('no_functional_ECAD_change', all(r['ecad_applied_this_round'] is False for r in bom))
thermal=read(D/'results/ELECTROTHERMAL_INPUT_UPDATE.json')
check('unknown_actual_current_temperature_remain_null', all(thermal[k] is None for k in
      ['actual_current_A','actual_current_RMS_A','actual_terminal_temperature_C','whole_board_dissipation_W','host_thermal_contact_K_W']))
result={'schema':'R5E_NATIVE_CANDIDATE_VERIFICATION_V1','status':'PASS' if all(c['pass'] for c in checks) else 'FAIL',
        'checks_passed':sum(c['pass'] for c in checks),'checks_total':len(checks),'checks':checks,
        'candidate_xml_sha256':sha(candidate_path),'source_xml_sha256':sha(D/'inputs/LOCKED_SYSTEM_249.xml'),
        'plan_sha256':sha(D/'inputs/ECAD_MCP_EDIT_PLAN.json'), 'source_unchanged_checks':source_checks,
        'candidate_annotation_applied':True,'functional_ecad_change_applied':False,
        'new_ERC_DRC_executed':False,'ready_to_power':False,'manufacturing_release':False,'flight_ready':False}
write('results/ECAD_CANDIDATE_VERIFICATION.json',result)
print({k:result[k] for k in ['status','checks_passed','checks_total','candidate_xml_sha256']})
if result['status']!='PASS':
    print([c for c in checks if not c['pass']])
    raise SystemExit(2)
