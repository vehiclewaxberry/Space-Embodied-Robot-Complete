"""Compact, source-bound dossier of the V36 STOP chain for the fault-matrix work (WP-1).
Collects, from the native 249-ref netlist, the V36 BOM, the selection/intake records and the existing calculation receipts:
every STOP-board part (ref, value, MPN, footprint, datasheet note), every net with its (ref, pin, pinfunction) endpoints
including off-board endpoints, the connector pin functions, and pointers (with sha256) to the calculation receipts.
Output: results/stop_v36/fault_chain_20260917/STOP_DOSSIER.json (+ .sha256). Read-only on sources."""
from pathlib import Path
import csv, hashlib, json, re, xml.etree.ElementTree as ET

A = Path(__file__).resolve().parents[1]
RUN = A.parent
OUT = A / 'results/stop_v36/fault_chain_20260917'
XML = A / 'results/stop_v36/pcb/thermal_filter_20260916/native_20260916_a/wp10_system.xml'
STOP_RE = re.compile(r'^(U1\d\d|R1\d\d|C1\d\d|J10\d|Q101|U31\d|R3[45]\d|C31\d)$')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    root = ET.parse(XML).getroot()
    comps = {}
    for c in root.iter('comp'):
        props = {p.get('name'): p.get('value') for p in c.findall('property')}
        comps[c.get('ref')] = dict(value=c.findtext('value'), footprint=c.findtext('footprint'), datasheet=c.findtext('datasheet'),
                                   MPN=props.get('MPN'), manufacturer=props.get('Manufacturer'), sheet=(c.find('sheetpath').get('names') if c.find('sheetpath') is not None else None))
    nets = {}
    for net in root.iter('net'):
        nodes = [dict(ref=n.get('ref'), pin=n.get('pin'), pinfunction=n.get('pinfunction') or '', pintype=n.get('pintype') or '') for n in net.findall('node')]
        if any(STOP_RE.match(n['ref']) for n in nodes):
            nets[net.get('name')] = dict(on_board=[n for n in nodes if STOP_RE.match(n['ref'])], off_board=[n for n in nodes if not STOP_RE.match(n['ref'])])
    stop_parts = {r: comps[r] for r in sorted(comps) if STOP_RE.match(r)}
    intake = {x['Reference']: x for x in json.loads((A / 'results/stop_v36/STOP_PARTS_INTAKE.json').read_text(encoding='utf-8-sig'))}
    selected = json.loads((A / 'results/stop_v36/SELECTED_PARTS.json').read_text(encoding='utf-8-sig'))
    for r, p in stop_parts.items():
        if r in intake:
            p['datasheet_note'] = intake[r].get('Datasheet'); p['design_role'] = intake[r].get('Design_Role')
        if r in selected:
            p['selection'] = {k: v for k, v in selected[r].items() if k in ('MPN', 'Manufacturer', 'Datasheet', 'Design_Role', 'Selection_Revision')}
    pins = {}
    with (A / 'ecad/revisions/v36/PIN_NET_TABLE.csv').open(encoding='utf-8-sig') as f:
        for row in csv.reader(f):
            if len(row) >= 4 and row[1].startswith('J10'):
                pins.setdefault(row[1], []).append(dict(pin=row[2], function=row[3], net=row[0]))
    port_map = json.loads((RUN / 'electrical/STOP_PORT_MAP.json').read_text(encoding='utf-8-sig'))
    receipts = {}
    for rel in ['results/stop_v36/CALCULATIONS.json', 'results/stop_v36/pcb/thermal_filter_20260916/CALCULATIONS.json',
                'results/stop_v36/pcb/thermal_filter_20260916/INITIAL_STATE_EXTENSION.json', 'results/stop_v36/PUBLIC_SOURCES.json',
                'results/stop_v36/READONLY_REVIEW_DISPOSITION.json', 'results/stop_v36/CROSS_BOARD_INTAKE.json',
                'results/stop_v36/pcb/verify_20260917/STOP_BOARD_VERIFICATION_20260917.json']:
        receipts[rel] = sha(A / rel)
    for rel in ['electrical/STOP_SUPPLY_CALCULATIONS.json', 'electrical/STOP_PORT_MAP.json', 'electrical/STOP_CIRCUIT_CONNECTIVITY.json', 'electrical/README.md']:
        receipts['../' + rel] = sha(RUN / rel)
    sch_notes = []
    for f in ['wp10_stop_detail.kicad_sch', 'wp10_brake_ready.kicad_sch']:
        t = (A / 'ecad/revisions/v36' / f).read_text(encoding='utf-8')
        sch_notes += [dict(sheet=f, text=m.group(1).replace('\\n', ' | ')) for m in re.finditer(r'\(text\s+"((?:[^"\\]|\\.)*)"', t, re.S)]
    d = dict(schema='WP10_V36_STOP_DOSSIER', date='2026-09-17', netlist_xml=str(XML.relative_to(A)).replace('\\', '/'), netlist_xml_sha256=sha(XML),
             stop_parts=stop_parts, nets=nets, connector_pins=pins, port_map_wp09_candidate=dict(ports=port_map['ports'], legacy_mapping=port_map.get('legacy_mapping')),
             schematic_notes=sch_notes, receipts_sha256=receipts,
             lineage_note='electrical/README.md describes the earlier WP09/WP10 supply candidate (TC4420 driver); the V36 board uses U112 UCC27517DBVR per the V36 schematic and SELECTED_PARTS.json. Do not mix the two.',
             scope='Connectivity and selection facts only; no timing, energy or hardware claim.')
    p = OUT / 'STOP_DOSSIER.json'
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    (OUT / 'STOP_DOSSIER.sha256').write_text(sha(p) + '  STOP_DOSSIER.json\n', encoding='utf-8')
    print(json.dumps(dict(parts=len(stop_parts), nets=len(nets), connectors=list(pins), notes=len(sch_notes), sha=sha(p)[:16])))


if __name__ == '__main__':
    main()
