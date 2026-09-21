"""Read-only verification of the current V36 STOP board against the 249-ref native netlist.

Writes results/stop_v36/pcb/verify_20260917/STOP_BOARD_VERIFICATION_20260917.json (+ .sha256):
  * board sha256 and the repair-chain link (ESCAPE_APPLIED.board_after_sha256 must equal the current file);
  * per-pad net parity for every STOP-board footprint against results/stop_v36/pcb/thermal_filter_20260916/native_20260916_a/wp10_system.xml;
  * footprint positions vs PLACEMENT.json (placement unchanged by routing);
  * routing inventory: tracks/vias per net, min width per netclass, via drill/diameter set, layer usage, unrouted pads;
  * a compact net table (net -> [(ref, pad, pin function)]) for the engineering review;
  * the fresh full-DRC counts from STOP_DRC_CURRENT.json.
KiCad 10 python. No board write."""
from pathlib import Path
import hashlib, json, collections, xml.etree.ElementTree as ET
import pcbnew as k

A = Path(__file__).resolve().parents[1]
E = A / 'ecad/revisions/v36'
L = A / 'results/stop_v36/pcb/layout_20260916'
OUT = A / 'results/stop_v36/pcb/verify_20260917'
XML = A / 'results/stop_v36/pcb/thermal_filter_20260916/native_20260916_a/wp10_system.xml'
mm = lambda v: v / 1e6


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    board_path = E / 'wp10_stop_control.kicad_pcb'
    b = k.LoadBoard(str(board_path))
    board_sha = sha(board_path)
    esc = json.loads((L / 'return_repair_e/ESCAPE_APPLIED.json').read_text(encoding='utf-8-sig'))  # chain link e: 2026-09-17 neck widen 0.25->0.4 mm (supersedes d as latest link; d kept in history)
    imp = json.loads((L / 'routing_import_a/IMPORT_VERIFICATION.json').read_text(encoding='utf-8-sig'))
    # netlist from the native XML
    root = ET.parse(XML).getroot()
    xml_nets = {}          # (ref, pin) -> net
    pin_names = {}         # (ref, pin) -> pinfunction
    for net in root.iter('net'):
        for node in net.findall('node'):
            xml_nets[(node.get('ref'), node.get('pin'))] = net.get('name')
            pin_names[(node.get('ref'), node.get('pin'))] = node.get('pinfunction') or ''
    xml_refs = {c.get('ref') for c in root.iter('comp')}
    fps = list(b.GetFootprints())
    elec = [f for f in fps if not f.GetReference().startswith('HSTOP')]
    mismatches = []; board_pads = 0
    for f in elec:
        for p in f.Pads():
            board_pads += 1
            key = (f.GetReference(), p.GetNumber()); bn = p.GetNetname()
            xn = xml_nets.get(key)
            if xn is None and bn == '':
                continue
            if (xn or '') != bn:
                mismatches.append(dict(ref=key[0], pad=key[1], board_net=bn, xml_net=xn))
    # placement parity
    pl = json.loads((L / 'PLACEMENT.json').read_text(encoding='utf-8-sig'))
    pos_ref = pl['position_mm_degrees']
    moved = []
    for f in fps:
        r = f.GetReference()
        if r in pos_ref:
            x, y = mm(f.GetPosition().x), mm(f.GetPosition().y); rot = f.GetOrientationDegrees()
            px, py, prot = pos_ref[r][0], pos_ref[r][1], pos_ref[r][2]
            if abs(x - px) > 1e-3 or abs(y - py) > 1e-3 or abs(((rot - prot) + 180) % 360 - 180) > 1e-3:
                moved.append(dict(ref=r, board=[x, y, rot], placement=[px, py, prot]))
    # routing inventory
    tracks = [t for t in b.GetTracks() if not isinstance(t, k.PCB_VIA)]; vias = [t for t in b.GetTracks() if isinstance(t, k.PCB_VIA)]
    per_net = collections.defaultdict(lambda: dict(segments=0, vias=0, length_mm=0.0, min_width_mm=None, layers=set()))
    for t in tracks:
        d = per_net[t.GetNetname()]; d['segments'] += 1; d['length_mm'] += mm(t.GetLength()); w = mm(t.GetWidth())
        d['min_width_mm'] = w if d['min_width_mm'] is None else min(d['min_width_mm'], w); d['layers'].add(b.GetLayerName(t.GetLayer()))
    for v in vias:
        per_net[v.GetNetname()]['vias'] += 1
    via_set = collections.Counter((round(mm(v.GetWidth(k.F_Cu)), 3), round(mm(v.GetDrillValue()), 3)) for v in vias)
    # pads without any track on their net (unrouted single-pad nets are legitimate only if the net has one pad)
    net_pads = collections.defaultdict(list)
    for f in elec:
        for p in f.Pads():
            if p.GetNetname():
                net_pads[p.GetNetname()].append((f.GetReference(), p.GetNumber()))
    unrouted_multi_pad_nets = [n for n, pads in net_pads.items() if len(pads) > 1 and per_net[n]['segments'] == 0]
    drc = json.loads((OUT / 'STOP_DRC_CURRENT.json').read_text(encoding='utf-8-sig'))
    net_table = {n: [(r, p, pin_names.get((r, p), '')) for r, p in sorted(pads)] for n, pads in net_pads.items()}
    out = dict(
        schema='WP10_V36_STOP_BOARD_VERIFICATION', date='2026-09-17',
        board=str(board_path.relative_to(A)).replace('\\', '/'), board_sha256=board_sha,
        repair_chain=dict(pre_import_sha256=imp['source_bindings'] if isinstance(imp['source_bindings'], dict) else 'see IMPORT_VERIFICATION.json',
                          escape_applied_after_sha256=esc['board_after_sha256'], current_equals_escape_applied=(esc['board_after_sha256'] == board_sha)),
        netlist_xml=str(XML.relative_to(A)).replace('\\', '/'), netlist_xml_sha256=sha(XML), netlist_refs=len(xml_refs),
        footprints=len(fps), electrical_footprints=len(elec), mounting_holes=len(fps) - len(elec), board_pads_checked=board_pads,
        pad_net_mismatches=mismatches, pad_net_parity=not mismatches,
        placement_reference_sha256=pl['board_sha256'], footprints_moved_since_placement=moved, placement_unchanged=not moved,
        copper_layers=b.GetCopperLayerCount(), zones=len(list(b.Zones())), tracks=len(tracks), vias=len(vias),
        via_diameter_drill_set=[dict(diameter_mm=a, drill_mm=d, count=c) for (a, d), c in via_set.items()],
        per_net={n: dict(segments=d['segments'], vias=d['vias'], length_mm=round(d['length_mm'], 2), min_width_mm=d['min_width_mm'], layers=sorted(d['layers'])) for n, d in per_net.items()},
        unrouted_multi_pad_nets=unrouted_multi_pad_nets,
        drc=dict(file='results/stop_v36/pcb/verify_20260917/STOP_DRC_CURRENT.json', date=drc['date'], violations=len(drc['violations']), unconnected_items=len(drc['unconnected_items']),
                 ignored_checks=[x['key'] for x in drc['ignored_checks']], included_severities=drc.get('included_severities')),
        net_table=net_table,
        scope='Connectivity/geometry parity and rule-check counts only. Not current capacity, thermal, transient, EMC or assembly evidence; no hardware test.',
        whole_design_complete=False, manufacturing_release=False)
    p = OUT / 'STOP_BOARD_VERIFICATION_20260917.json'
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (OUT / 'STOP_BOARD_VERIFICATION_20260917.sha256').write_text(sha(p) + '  STOP_BOARD_VERIFICATION_20260917.json\n', encoding='utf-8')
    print(json.dumps(dict(board_sha=board_sha[:16], chain_ok=out['repair_chain']['current_equals_escape_applied'], pads=board_pads, mismatches=len(mismatches), moved=len(moved),
                          tracks=len(tracks), vias=len(vias), zones=out['zones'], unrouted_multi=unrouted_multi_pad_nets, drc=(out['drc']['violations'], out['drc']['unconnected_items']),
                          vias_set=out['via_diameter_drill_set'])))


if __name__ == '__main__':
    main()
