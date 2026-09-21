"""Independent, read-only XML/PCB/source-lock audit. Writes reviewer evidence only.

Run with KiCad's bundled Python; never saves an ECAD file.
"""
from pathlib import Path
from collections import Counter, defaultdict
import datetime
import hashlib
import json
import xml.etree.ElementTree as ET
import pcbnew

ROOT = Path(__file__).resolve().parents[4]
D = ROOT / '20_engineering/SERVICE_STAR_ELECTRICAL_UPDATE_R5E_20260920'
I = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation'
OUT = D / 'results/reviewer'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def rel(path):
    return path.relative_to(ROOT).as_posix()

def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def parse_xml(path):
    root = ET.parse(path).getroot()
    comps = {}
    for item in root.findall('components/comp'):
        ref = item.attrib['ref']
        assert ref not in comps, ref
        comps[ref] = {
            'value': item.findtext('value', ''),
            'footprint': item.findtext('footprint', ''),
            'datasheet': item.findtext('datasheet', ''),
            'fields': {x.attrib['name']: (x.text or '') for x in item.findall('fields/field')},
            'properties': {x.attrib['name']: x.attrib.get('value', '') for x in item.findall('property')},
            'pins': sorted(set(x.attrib['num'] for x in item.findall('units/unit/pins/pin'))),
        }
    pins = {}
    leaf_names = defaultdict(set)
    for net in root.findall('nets/net'):
        name = net.attrib['name']
        leaf_names[name.rsplit('/', 1)[-1]].add(name)
        for item in net.findall('node'):
            key = item.attrib['ref'], item.attrib['pin']
            assert key not in pins or pins[key] == name, (key, name, pins.get(key))
            pins[key] = name
    return comps, pins, leaf_names

current_path = I / 'ecad/revisions/v36/wp10_system.xml'
old_path = I / 'results/stop_v36/pcb/thermal_filter_20260916/native_20260916_a/wp10_system.xml'
cc, cp, leaves = parse_xml(current_path)
oc, op, _ = parse_xml(old_path)
boards = {label: I / f'ecad/revisions/v36/{name}' for label, name in {
    'MAIN': 'wp10_main_input.kicad_pcb',
    'STOP': 'wp10_stop_control.kicad_pcb',
    'AUX': 'wp10_aux_protection.kicad_pcb',
}.items()}
delta_path = I / 'coupled_closure/HANDOFF_DELTA_20260917_STOP_REVIEW_COMPLETE.json'
latest_path = I / 'coupled_closure/HANDOFF_LATEST.json'
working_path = I / 'ecad/revisions/v36/WORKING_REVISION.json'
sources = [current_path, old_path, delta_path, latest_path, working_path, *boards.values()]
locks = {rel(p): sha(p) for p in sources}
board_results = {}
for label, path in boards.items():
    board = pcbnew.LoadBoard(str(path))
    refs = Counter(f.GetReference() for f in board.GetFootprints())
    result = {
        'path': rel(path), 'sha256': sha(path),
        'footprints_total': len(list(board.GetFootprints())),
        'duplicate_references': {k:v for k,v in refs.items() if v != 1},
        'electrical_refs': [], 'board_only_refs': [],
        'pad_occurrences_total': 0, 'numbered_pad_occurrences': 0,
        'unnumbered_pad_occurrences': 0,
        'pad_net_matches_exact': 0, 'pad_net_matches_unique_hierarchical_leaf': 0,
        'hierarchical_aliases_used': [],
        'pad_net_mismatches': [], 'footprint_mismatches': [], 'value_mismatches': [],
        'missing_schematic_pin_numbers': [],
        'rows': [],
    }
    for f in sorted(board.GetFootprints(), key=lambda f:f.GetReference()):
        ref = f.GetReference()
        fp = str(f.GetFPID().GetLibNickname()) + ':' + str(f.GetFPID().GetLibItemName())
        value = f.GetValue()
        row = {'ref':ref, 'value':value, 'footprint':fp, 'pads':[]}
        if ref not in cc:
            result['board_only_refs'].append(ref)
        else:
            result['electrical_refs'].append(ref)
            if value != cc[ref]['value']:
                result['value_mismatches'].append({'ref':ref,'pcb':value,'xml':cc[ref]['value']})
            if fp != cc[ref]['footprint']:
                result['footprint_mismatches'].append({'ref':ref,'pcb':fp,'xml':cc[ref]['footprint']})
        pcb_pins = set()
        for pad in f.Pads():
            result['pad_occurrences_total'] += 1
            pn, actual = pad.GetNumber(), pad.GetNetname()
            pcb_pins.add(pn)
            expected = cp.get((ref,pn))
            row['pads'].append({'pin':pn,'pcb_net':actual,'xml_net':expected})
            if not pn:
                result['unnumbered_pad_occurrences'] += 1
                if actual:
                    result['pad_net_mismatches'].append({'ref':ref,'pin':pn,'pcb':actual,'xml':expected,'reason':'unnumbered net-bearing pad'})
                continue
            result['numbered_pad_occurrences'] += 1
            if expected is None:
                result['pad_net_mismatches'].append({'ref':ref,'pin':pn,'pcb':actual,'xml':None,'reason':'numbered pad absent from XML nets'})
            elif actual == expected:
                result['pad_net_matches_exact'] += 1
            elif actual == expected.rsplit('/',1)[-1] and leaves[actual] == {expected}:
                result['pad_net_matches_unique_hierarchical_leaf'] += 1
                result['hierarchical_aliases_used'].append({'ref':ref,'pin':pn,'pcb':actual,'xml':expected})
            else:
                result['pad_net_mismatches'].append({'ref':ref,'pin':pn,'pcb':actual,'xml':expected,'reason':'net name unequal'})
        if ref in cc:
            missing = set(cc[ref]['pins']) - pcb_pins
            if missing:
                result['missing_schematic_pin_numbers'].append({'ref':ref,'pins':sorted(missing)})
        result['rows'].append(row)
    result['electrical_footprints'] = len(result['electrical_refs'])
    board_results[label] = result

changed = []
for ref in sorted(set(cc) | set(oc)):
    if cc.get(ref) != oc.get(ref):
        fields = {key:{'old':oc.get(ref,{}).get(key),'current':cc.get(ref,{}).get(key)} for key in set(cc.get(ref,{})) | set(oc.get(ref,{})) if oc.get(ref,{}).get(key) != cc.get(ref,{}).get(key)}
        changed.append({'ref':ref,'changed_fields':fields})
pin_delta = [{'ref':key[0],'pin':key[1],'old':op.get(key),'current':cp.get(key)} for key in sorted(set(cp)|set(op)) if cp.get(key) != op.get(key)]
handoff = []
for name, item in read(delta_path)['evidence'].items():
    path = I/item['path']
    actual = sha(path) if path.is_file() else None
    handoff.append({'entry':name,'path':rel(path),'expected_sha256':item['sha256'],'actual_sha256':actual,'match':actual==item['sha256']})
after = {rel(p): sha(p) for p in sources}
assert locks == after, 'Source files mutated during audit; refusing a mixed snapshot.'
out = {
    'schema':'R5E_INDEPENDENT_CURRENT_V36_AUDIT_V1',
    'utc_generated':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'reviewer':'electrical_selection_review',
    'scope':'Read-only file consistency audit; no DRC rerun, hardware power, manufacturing, flight, or thermal qualification.',
    'source_hashes_before':locks,'source_hashes_after':after,'sources_unchanged':True,
    'xml_current':{'path':rel(current_path),'sha256':sha(current_path),'components':len(cc),'pin_net_pairs':len(cp)},
    'xml_old':{'path':rel(old_path),'sha256':sha(old_path),'components':len(oc),'pin_net_pairs':len(op)},
    'xml_components_changed':changed,'xml_pin_net_changes':pin_delta,
    'boards':board_results,'handoff_evidence':handoff,
    'handoff_all_evidence_hashes_match':all(x['match'] for x in handoff),
    'latest_handoff':read(latest_path),
    'engineering_release':False,
}
dump(OUT/'CURRENT_V36_SOURCE_AUDIT.json',out)
print(json.dumps({
    'xml_current':out['xml_current'],'xml_old':out['xml_old'],
    'component_changes':len(changed),'pin_net_changes':len(pin_delta),
    'boards':{k:{kk:vv for kk,vv in v.items() if kk not in ['rows','electrical_refs','hierarchical_aliases_used']} for k,v in board_results.items()},
    'handoff_mismatches':[x for x in handoff if not x['match']],
    'output':rel(OUT/'CURRENT_V36_SOURCE_AUDIT.json'),
},ensure_ascii=False,indent=2))
