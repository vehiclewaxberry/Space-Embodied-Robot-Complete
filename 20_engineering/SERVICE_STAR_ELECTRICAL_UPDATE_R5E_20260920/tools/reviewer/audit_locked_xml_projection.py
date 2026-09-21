"""Qualify the independent PCB readback against the verified 249-ref XML.

Only declared board pads/NCs are exempted, with every exemption enumerated.
No source or ECAD file is changed.
"""
from pathlib import Path
import hashlib
import json
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
D = ROOT / '20_engineering/SERVICE_STAR_ELECTRICAL_UPDATE_R5E_20260920'
I = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation'
OUT = D/'results/reviewer'
RAW = OUT/'CURRENT_V36_SOURCE_AUDIT.json'
XML = I/'results/stop_v36/pcb/thermal_filter_20260916/native_20260916_a/wp10_system.xml'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
raw = json.loads(RAW.read_text(encoding='utf-8'))
for path, expected in raw['source_hashes_before'].items():
    assert sha(ROOT/path) == expected, ('Source drift since readback',path)
xml = ET.parse(XML).getroot()
assert sha(XML) == '90497ad91d4b8ec2c39e6eda819b94e3fbcf9f908861aae22e6c90c5bf1a1939'
comps = {c.attrib['ref']:c for c in xml.findall('components/comp')}
nets = {(n.attrib['ref'],n.attrib['pin']):net.attrib['name'] for net in xml.findall('nets/net') for n in net.findall('node')}
port_endpoints = {'PORT_ENABLE':('Q204','3'), 'PORT_RESET':('U201','3'), 'PORT_PGD':('U201','8'), 'PORT_SIGNAL_RETURN':('U201','5')}
mounting = {'MAIN':{'MH1','MH2','MH3','MH4'},'STOP':{'HSTOP1','HSTOP2','HSTOP3','HSTOP4'},'AUX':{'MH34_1','MH34_2','MH34_3','MH34_4','MH35_1','MH35_2'}}
boards = {}
for label, b in raw['boards'].items():
    rec = {'path':b['path'],'sha256':b['sha256'], 'footprints_total':b['footprints_total'],
        'xml_refs':[], 'mechanical_refs':[], 'declared_board_ports':[],
        'pads_total':b['pad_occurrences_total'],
        'net_matches_exact':0, 'explicit_nc_empty_matches':[],
        'board_port_matches':[], 'non_electrical_empty_pads':[],
        'unknown_references':[], 'net_mismatches':[], 'value_mismatches':[],
        'value_annotation_only_differences':[], 'footprint_exact_matches':0,
        'footprint_library_nickname_missing':[], 'footprint_mismatches':[],
        'missing_schematic_pins':[], 'embedded_testpad_refs':[]}
    for row in b['rows']:
        ref = row['ref']
        c = comps.get(ref)
        is_mount = ref in mounting[label]
        is_port = label == 'MAIN' and ref in port_endpoints
        if is_mount:
            rec['mechanical_refs'].append(ref)
        elif is_port:
            rec['declared_board_ports'].append(ref)
        elif c is None:
            rec['unknown_references'].append(ref)
        else:
            rec['xml_refs'].append(ref)
            value, fp = c.findtext('value',''), c.findtext('footprint','')
            if row['value'] != value:
                delta = {'ref':ref,'pcb':row['value'],'xml':value}
                if row['value'].split(' / ')[0] == value.split(' / ')[0]:
                    rec['value_annotation_only_differences'].append(delta)
                else:
                    rec['value_mismatches'].append(delta)
            if row['footprint'] == fp:
                rec['footprint_exact_matches'] += 1
            elif row['footprint'].startswith(':') and row['footprint'][1:] == fp.split(':')[-1]:
                rec['footprint_library_nickname_missing'].append({'ref':ref,'pcb':row['footprint'],'xml':fp,'status':'Item name matches; library nickname absent in embedded footprint; not a pad-geometry equivalence claim.'})
            else:
                rec['footprint_mismatches'].append({'ref':ref,'pcb':row['footprint'],'xml':fp})
            sp = {p.attrib['num'] for p in c.findall('units/unit/pins/pin')}
            missing = sp - {p['pin'] for p in row['pads']}
            if missing:
                rec['missing_schematic_pins'].append({'ref':ref,'pins':sorted(missing)})
            if label == 'AUX' and ref == 'J210' and value == 'LOCAL_RESET_TEST_PADS':
                rec['embedded_testpad_refs'].append({'ref':ref,'value':value,'footprint':row['footprint'],'procurement':'BOARD_COPPER_NOT_A_PURCHASABLE_CONNECTOR'})
        for p in row['pads']:
            pin,actual = p['pin'],p['pcb_net']
            expected = nets.get((ref,pin))
            if is_port:
                endpoint = port_endpoints[ref]
                expected = nets.get(endpoint)
                if pin == '1' and actual == expected:
                    rec['board_port_matches'].append({'ref':ref,'pin':pin,'net':actual,'source_endpoint':'.'.join(endpoint)})
                else:
                    rec['net_mismatches'].append({'ref':ref,'pin':pin,'pcb':actual,'xml_endpoint_net':expected})
            elif not pin and not actual and expected is None:
                rec['non_electrical_empty_pads'].append({'ref':ref,'pin':pin,'kind':'mounting_hole' if is_mount else 'unconnected_mechanical_footprint_pad'})
            elif label == 'STOP' and ref == 'J106' and pin == 'MP' and not actual and expected is None:
                rec['non_electrical_empty_pads'].append({'ref':ref,'pin':pin,'kind':'connector_mount_pad'})
            elif expected == actual and expected is not None:
                rec['net_matches_exact'] += 1
            elif actual == '' and expected and expected.startswith('unconnected-(') and expected.endswith('-Pad'+pin+')') and expected.startswith('unconnected-('+ref+'-'):
                rec['explicit_nc_empty_matches'].append({'ref':ref,'pin':pin,'xml':expected})
            else:
                rec['net_mismatches'].append({'ref':ref,'pin':pin,'pcb':actual,'xml':expected})
    rec['xml_ref_count'] = len(rec['xml_refs'])
    rec['pad_accounting_complete'] = rec['pads_total'] == rec['net_matches_exact'] + len(rec['explicit_nc_empty_matches']) + len(rec['board_port_matches']) + len(rec['non_electrical_empty_pads']) + len(rec['net_mismatches'])
    rec['net_parity_with_enumerated_exceptions'] = not rec['net_mismatches'] and rec['pad_accounting_complete'] and not rec['unknown_references']
    boards[label] = rec

out = {'schema':'R5E_INDEPENDENT_LOCKED_XML_PROJECTION_V1',
    'source_xml':XML.relative_to(ROOT).as_posix(),'source_xml_sha256':sha(XML),
    'raw_readback':RAW.relative_to(ROOT).as_posix(),'raw_readback_sha256':sha(RAW),
    'xml_component_count':len(comps),'xml_pin_net_pairs':len(nets),
    'boards':boards,
    'contract_sources':[str((I/'tools/build_main_board_native_v25.py').relative_to(ROOT)),str((I/'tools/verify_main_input_v36_20260917.py').relative_to(ROOT))],
    'all_boards_pad_net_pass':all(b['net_parity_with_enumerated_exceptions'] for b in boards.values()),
    'full_footprint_library_geometry_equivalence_verified':False,
    'engineering_release':False,
    'scope':'249-ref XML vs actual immutable V36 PCB readback; MAIN four board ports are validated against exact schematic source endpoints, not blindly skipped. Explicit NC and mechanical pads are individually enumerated. Footprint IDs are compared; embedded pad-vs-library geometry not certified.'}
(OUT/'LOCKED_249_XML_BOARD_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'all_boards_pad_net_pass':out['all_boards_pad_net_pass'],'boards':{k:{kk:vv for kk,vv in v.items() if kk not in ['xml_refs','non_electrical_empty_pads']} for k,v in boards.items()}},ensure_ascii=False,indent=2))
