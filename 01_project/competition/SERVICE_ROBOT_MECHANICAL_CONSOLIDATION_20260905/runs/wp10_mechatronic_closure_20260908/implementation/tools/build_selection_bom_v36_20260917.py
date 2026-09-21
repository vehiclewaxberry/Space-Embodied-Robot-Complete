"""WP-2 groundwork: a traceable selection BOM for the V36 source, separating real purchasable parts, mature modules /
boundary symbols and logic ports, and listing per real line which of {model, qty, footprint, rating, source, substitution
limit} is missing. Deterministic; reads only the V36 BOM/netlist/selection records. No procurement claim.
Outputs: results/electrical_selection_20260917/SELECTION_BOM_V36.csv, SELECTION_GAPS.json (+ .sha256)."""
from pathlib import Path
import csv, hashlib, json, re, xml.etree.ElementTree as ET
from collections import Counter, defaultdict

A = Path(__file__).resolve().parents[1]
OUT = A / 'results/electrical_selection_20260917'
XML = A / 'results/stop_v36/pcb/thermal_filter_20260916/native_20260916_a/wp10_system.xml'
MODULE_VALUES = {'ACU', 'BPX', 'CAN', 'DM', 'DOCK', 'FPP', 'K1', 'OBC', 'PDU', 'SEP', 'STOPBOARD', 'THN 30-2415WIR'}
BOARD_OF = [(re.compile(r'^(U1\d\d|R1\d\d|C1\d\d|J10\d|Q101|U31\d|R3[45]\d|C31\d)$'), 'STOP_CONTROL_PCB'),
            (re.compile(r'^(U2\d\d|R2\d\d|C2\d\d|J20\d|Q2\d\d|D2\d\d|F2\d\d|RT2\d\d|MH\d)$'), 'MAIN_INPUT_OR_AUX_PCB'),
            (re.compile(r'^(U30\d|R30\d|R31\d|C30\d|Q30\d|J30\d|RT31\d)$'), 'BRAKE_READY_OR_AUX_PCB')]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    root = ET.parse(XML).getroot()
    comps = []
    for c in root.iter('comp'):
        props = {p.get('name'): p.get('value') for p in c.findall('property')}
        comps.append(dict(ref=c.get('ref'), value=c.findtext('value') or '', footprint=c.findtext('footprint') or '', datasheet=c.findtext('datasheet') or '',
                          MPN=props.get('MPN') or '', manufacturer=props.get('Manufacturer') or '', sheet=(c.find('sheetpath').get('names') if c.find('sheetpath') is not None else '')))
    sel = json.loads((A / 'results/stop_v36/SELECTED_PARTS.json').read_text(encoding='utf-8-sig'))
    intake = {x['Reference']: x for x in json.loads((A / 'results/stop_v36/STOP_PARTS_INTAKE.json').read_text(encoding='utf-8-sig'))}
    pub = json.loads((A / 'results/stop_v36/PUBLIC_SOURCES.json').read_text(encoding='utf-8-sig'))
    pub_parts = {s['part']: s for s in pub['sources']}
    # main-input / aux PCB BOMs carry MPN columns for the 2xx parts
    mpn_from_bom = {}
    for f in ['MAIN_INPUT_PCB_BOM.csv', 'AUX_PROTECTION_SEQUENCE_PCB_BOM.csv', 'SYSTEM_BOM.csv']:
        p = A / 'ecad/revisions/v36' / f
        if p.exists():
            with p.open(encoding='utf-8-sig') as fh:
                for row in csv.DictReader(fh):
                    ref = row.get('Reference') or row.get('Ref') or ''
                    for key in ('MPN', 'Manufacturer Part Number', 'Part Number'):
                        if row.get(key):
                            mpn_from_bom.setdefault(ref, {})[f] = row[key]
    rows = []; gaps = defaultdict(list); classes = Counter()
    for c in comps:
        ref = c['ref']; val = c['value']
        if val in MODULE_VALUES or val.startswith(('PV_BRANCH', 'RS_')) or 'RETIRED' in val:
            cls = 'MODULE_OR_BOUNDARY_SYMBOL' if 'RETIRED' not in val else 'RETIRED_GSE_SYMBOL'
        elif ref.startswith(('PORT', 'TP', 'NT', 'H')) or val.upper() in ('PORT', 'TESTPOINT', 'NET-TIE'):
            cls = 'LOGIC_PORT_OR_MECHANICAL'
        else:
            cls = 'REAL_PART_CANDIDATE'
        classes[cls] += 1
        board = next((b for rx, b in BOARD_OF if rx.match(ref)), 'SYSTEM_OR_HARNESS')
        mpn = c['MPN'] or (sel.get(ref, {}).get('MPN') if ref in sel else '') or (intake.get(ref, {}).get('MPN') or '') or (val.split(' / ')[0] if re.match(r'^[A-Z0-9][A-Z0-9\-\.]{6,}$', val.split(' / ')[0]) else '')
        mfr = c['manufacturer'] or sel.get(ref, {}).get('Manufacturer', '') or intake.get(ref, {}).get('Manufacturer', '')
        src = c['datasheet'] or sel.get(ref, {}).get('Datasheet', '') or intake.get(ref, {}).get('Datasheet', '')
        pub_hit = next((k for k in pub_parts if mpn and (k in mpn or mpn in k)), '')
        missing = []
        if cls == 'REAL_PART_CANDIDATE':
            if not mpn: missing.append('model')
            if not c['footprint']: missing.append('footprint')
            if not src: missing.append('source')
            missing.append('rating')             # ratings are not carried in the BOM/netlist for any line: recorded uniformly
            missing.append('substitution_limit')
            for m in missing: gaps[m].append(ref)
        rows.append(dict(ref=ref, class_=cls, board=board, value=val, MPN=mpn, manufacturer=mfr, footprint=c['footprint'], source=src,
                         public_source_verified=pub_hit, bom_mpn_records=json.dumps(mpn_from_bom.get(ref, {}), ensure_ascii=False) if mpn_from_bom.get(ref) else '',
                         qty=1, missing_fields=';'.join(missing), sheet=c['sheet']))
    with (OUT / 'SELECTION_BOM_V36.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    real = [r for r in rows if r['class_'] == 'REAL_PART_CANDIDATE']
    g = dict(schema='WP10_V36_SELECTION_GAPS', date='2026-09-17', netlist_xml_sha256=sha(XML), refs=len(rows), classes=dict(classes),
             real_part_lines=len(real), real_lines_with_model=sum(1 for r in real if r['MPN']), real_lines_with_footprint=sum(1 for r in real if r['footprint']),
             real_lines_with_source=sum(1 for r in real if r['source']), real_lines_public_source_verified=sum(1 for r in real if r['public_source_verified']),
             gaps={k: dict(count=len(v), refs=v) for k, v in gaps.items()},
             exit_condition_WP2='every real procurement line has model/qty/footprint/rating/source/substitution limit',
             exit_condition_met=False,
             note='rating and substitution_limit are not represented in any V36 BOM/netlist field; they must be authored per line against the archived datasheets before the WP-2 exit condition can be evaluated. Modules/boundary symbols (ACU, BPX, CAN, DM, DOCK, FPP, K1, OBC, PDU, SEP, STOPBOARD, THN, PV_BRANCH_x, RS_x) need controlled ICDs, not MPNs.')
    p = OUT / 'SELECTION_GAPS.json'; p.write_text(json.dumps(g, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (OUT / 'SELECTION_GAPS.sha256').write_text(sha(p) + '  SELECTION_GAPS.json\n', encoding='utf-8')
    (OUT / 'SELECTION_BOM_V36.sha256').write_text(sha(OUT / 'SELECTION_BOM_V36.csv') + '  SELECTION_BOM_V36.csv\n', encoding='utf-8')
    print(json.dumps(dict(refs=len(rows), classes=dict(classes), real=len(real), with_model=g['real_lines_with_model'], with_footprint=g['real_lines_with_footprint'], with_source=g['real_lines_with_source'], public_verified=g['real_lines_public_source_verified'])))


if __name__ == '__main__':
    main()
