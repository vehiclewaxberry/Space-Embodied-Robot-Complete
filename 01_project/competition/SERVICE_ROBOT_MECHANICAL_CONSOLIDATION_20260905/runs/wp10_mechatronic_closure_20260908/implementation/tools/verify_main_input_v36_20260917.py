"""Same-version receipt for the V36 main-input board after the CF1 port (read-only).
- pad/net + footprint fingerprint against the V36 native netlist (249-ref XML) for the 43 main-input footprints;
- copper-loss / current-density model re-run on the V36 board bytes (reuses cf1_layout_thermal/tools/current_density_cf1.py);
- DRC / parity counts from the fresh kicad-cli reports in the same directory;
- sha256 chain to the port receipt. Output: results/main_input_v36_cf1_port_20260917/MAIN_INPUT_V36_VERIFICATION.json (+.sha256)."""
from pathlib import Path
import hashlib, json, sys, xml.etree.ElementTree as ET
import pcbnew as k

A = Path(__file__).resolve().parents[1]
OUT = A / 'results/main_input_v36_cf1_port_20260917'
BOARD = A / 'ecad/revisions/v36/wp10_main_input.kicad_pcb'
XML = A / 'results/stop_v36/pcb/thermal_filter_20260916/native_20260916_a/wp10_system.xml'
sys.path.insert(0, str(A / 'cf1_layout_thermal/tools'))
import current_density_cf1 as cd   # noqa: E402  (KiCad python; read-only functions)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    b = k.LoadBoard(str(BOARD))
    root = ET.parse(XML).getroot()
    xml_nets = {(n.get('ref'), n.get('pin')): net.get('name') for net in root.iter('net') for n in net.findall('node')}
    xml_vals = {c.get('ref'): c.findtext('value') for c in root.iter('comp')}
    mism = []; pads = 0; refs = []
    for f in b.GetFootprints():
        r = f.GetReference(); refs.append(r)
        for p in f.Pads():
            pads += 1; key = (r, p.GetNumber()); bn = p.GetNetname(); xn = xml_nets.get(key)
            if xn is None and bn == '':
                continue
            if r.startswith(('MH', 'PORT_')):
                continue
            if (xn or '') != bn and not (bn == '' and (xn or '').startswith('unconnected-(')):   # KiCad boards leave NC pads unnamed
                mism.append(dict(ref=r, pad=key[1], board_net=bn, xml_net=xn))
    val_mism = [dict(ref=f.GetReference(), board=f.GetValue(), xml=xml_vals.get(f.GetReference())) for f in b.GetFootprints()
                if f.GetReference() in xml_vals and xml_vals[f.GetReference()] not in (None, '') and f.GetValue().split(' / ')[0] != xml_vals[f.GetReference()].split(' / ')[0]]
    segs, thick = cd.cf1_segments(BOARD)
    summ = cd.summarize('V36_MAIN_INPUT_105um_bands_plus_pad_entry_necks', segs, thick)
    p_segs, p_thick = cd.parent_segments(); parent = cd.summarize('V29_parent_70um', p_segs, p_thick)
    drc = json.loads((OUT / 'MAIN_INPUT_DRC.json').read_text(encoding='utf-8-sig'))
    par = json.loads((OUT / 'MAIN_INPUT_DRC_PARITY.json').read_text(encoding='utf-8-sig'))
    plog = (OUT / 'MAIN_INPUT_DRC_PARITY.log').read_text(encoding='utf-8', errors='replace')
    port = json.loads((OUT / 'PORT_RECEIPT.json').read_text(encoding='utf-8'))
    out = dict(schema='WP10_V36_MAIN_INPUT_VERIFICATION', date='2026-09-17', board_sha256=sha(BOARD), port_receipt_result_sha256=port['result_board_sha256'],
               board_equals_port_result=(sha(BOARD) == port['result_board_sha256']), netlist_xml_sha256=sha(XML),
               footprints=len(refs), pads_checked=pads, pad_net_mismatches=mism, value_mismatches_vs_netlist=val_mism,
               drc=dict(violations=len(drc['violations']), unconnected=len(drc['unconnected_items']), ignored_checks=[x['key'] for x in drc['ignored_checks']], date=drc['date']),
               schematic_parity=dict(executable=('Schematic parity tests require a fully annotated schematic' not in plog), violations=len(par['violations']),
                                     note='kicad-cli refusal text captured in MAIN_INPUT_DRC_PARITY.log when not executable'),
               copper_model=dict(copper_thickness_mm=thick, R20_total_mohm=summ['R20_total_ohm'] * 1e3, parent_R20_total_mohm=parent['R20_total_ohm'] * 1e3,
                                 loss_20A_100C_W=summ['loss_20A_100C_W'], loss_reduction_vs_V29=1 - summ['loss_20A_100C_W'] / parent['loss_20A_100C_W'],
                                 worst_band_current_density_A_mm2=summ['worst_band_current_density_A_mm2'], worst_neck_current_density_A_mm2=summ['worst_neck_current_density_A_mm2'],
                                 limit_A_mm2=cd.J_LIMIT, band_ok=summ['worst_band_current_density_A_mm2'] <= cd.J_LIMIT, neck_ok=summ['worst_neck_current_density_A_mm2'] <= cd.J_LIMIT),
               open_items_carried_from_CF1=['Q201 pad-entry neck density exceeds 35 A/mm2 (footprint-bound)', 'DESIGN_SPEC_CF1 4.2/4.3/4.4 deviations and the substituted negative case, owner-accepted 2026-09-17'],
               scope='EDA-level verification of the ported layout in the V36 working revision. No fabrication, ampacity test, SOA, assembly or energization credit.',
               whole_design_complete=False, manufacturing_release=False)
    p = OUT / 'MAIN_INPUT_V36_VERIFICATION.json'
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (OUT / 'MAIN_INPUT_V36_VERIFICATION.sha256').write_text(sha(p) + '  MAIN_INPUT_V36_VERIFICATION.json\n', encoding='utf-8')
    print(json.dumps(dict(board=out['board_sha256'][:16], equals_port=out['board_equals_port_result'], footprints=len(refs), pads=pads, mismatches=len(mism), value_mismatches=val_mism,
                          drc=(out['drc']['violations'], out['drc']['unconnected']), parity_exec=out['schematic_parity']['executable'],
                          R20=round(out['copper_model']['R20_total_mohm'], 3), reduction=round(out['copper_model']['loss_reduction_vs_V29'], 4),
                          bandJ=round(out['copper_model']['worst_band_current_density_A_mm2'], 1), neckJ=round(out['copper_model']['worst_neck_current_density_A_mm2'], 1))))


if __name__ == '__main__':
    main()
