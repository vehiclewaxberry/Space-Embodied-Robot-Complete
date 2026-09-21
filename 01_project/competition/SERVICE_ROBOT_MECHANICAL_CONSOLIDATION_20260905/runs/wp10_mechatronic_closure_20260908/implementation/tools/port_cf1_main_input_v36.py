"""Port the owner-accepted CF1 main-input layout (3 oz outer copper, >=8 mm forward bands, B.Cu parallel strip + via array,
return TIM zone, courtyards/attributes, 5 DRC rules enabled) into the V36 working revision.

The V36 main-input board is byte-identical to V35 and differs from the CF1 parent (V32) only in the R202 Value property
(WSLP2726L2000FEA -> WSLP2726L5000FEA, the 5 mOhm shunt selected in V35). CF1 kept the V32 footprint/pad/net fingerprint,
so the port is: restore point of the V35-inherited files -> copy the CF1 board and project -> set R202 Value to the V35
string -> save with native pcbnew -> cold reload -> parity checks -> receipt. DRC and density receipts are re-run by the
caller with kicad-cli / the CF1 tools pointed at the V36 board. Native write: run through tools/native_delta_guard.py.
"""
from pathlib import Path
import hashlib, json, shutil, datetime
import pcbnew as k

A = Path(__file__).resolve().parents[1]
CF1 = A / 'cf1_layout_thermal'
V36 = A / 'ecad/revisions/v36'
V35 = A / 'ecad/revisions/v35'
HIST = A / 'history/V36_MAIN_INPUT_BEFORE_CF1_20260917'
OUT = A / 'results/main_input_v36_cf1_port_20260917'
R202_V35_VALUE = 'WSLP2726L5000FEA'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def fingerprint(b):
    fps = []
    for f in b.GetFootprints():
        pads = [dict(pin=p.GetNumber(), net=p.GetNetname(), xy=[p.GetPosition().x, p.GetPosition().y], size=[p.GetSize().x, p.GetSize().y],
                     drill=[p.GetDrillSize().x, p.GetDrillSize().y], shape=int(p.GetShape()), layers=list(p.GetLayerSet().Seq())) for p in f.Pads()]
        fps.append(dict(ref=f.GetReference(), fp=str(f.GetFPID().GetLibItemName()), xy=[f.GetPosition().x, f.GetPosition().y], angle=f.GetOrientationDegrees(),
                        pads=sorted(pads, key=lambda p: (p['pin'], p['xy'][0], p['xy'][1]))))
    return sorted(fps, key=lambda x: x['ref'])


def main():
    OUT.mkdir(parents=True, exist_ok=True); HIST.mkdir(parents=True, exist_ok=True)
    src_board = CF1 / 'ecad/wp10_main_input.kicad_pcb'; src_pro = CF1 / 'ecad/wp10_main_input.kicad_pro'; src_prl = CF1 / 'ecad/wp10_main_input.kicad_prl'
    dst_board = V36 / 'wp10_main_input.kicad_pcb'; dst_pro = V36 / 'wp10_main_input.kicad_pro'; dst_prl = V36 / 'wp10_main_input.kicad_prl'
    assert sha(dst_board) == sha(V35 / 'wp10_main_input.kicad_pcb'), 'V36 main-input board is no longer the V35 copy; port must be re-based'
    before = {p.name: sha(p) for p in (dst_board, dst_pro, dst_prl) if p.exists()}
    for p in (dst_board, dst_pro, dst_prl):
        if p.exists():
            shutil.copy2(p, HIST / p.name)
    cf1_lock = json.loads((CF1 / 'results/pcb/NATIVE_BUILD.json').read_text(encoding='utf-8'))
    assert sha(src_board) == cf1_lock['board_sha256'], 'CF1 board drifted from its build receipt'
    # V35 parent fingerprint (what the port must match, except the R202 Value text)
    parent = k.LoadBoard(str(dst_board)); parent_fp = fingerprint(parent)
    parent_values = {f.GetReference(): f.GetValue() for f in parent.GetFootprints()}
    # copy the CF1 project files, then the board with the R202 value set to the V35 selection
    shutil.copy2(src_pro, dst_pro); shutil.copy2(src_prl, dst_prl)
    b = k.LoadBoard(str(src_board))
    changed = []
    for f in b.GetFootprints():
        want = parent_values.get(f.GetReference())
        if want is not None and f.GetValue() != want:
            changed.append(dict(ref=f.GetReference(), cf1_value=f.GetValue(), v35_value=want)); f.SetValue(want)
    assert changed == [dict(ref='R202', cf1_value='WSLP2726L2000FEA', v35_value=R202_V35_VALUE)], changed
    k.SaveBoard(str(dst_board), b)
    # cold reload and parity
    b2 = k.LoadBoard(str(dst_board)); fp2 = fingerprint(b2)
    values2 = {f.GetReference(): f.GetValue() for f in b2.GetFootprints()}
    text = dst_board.read_text(encoding='utf-8')
    receipt = dict(
        schema='WP10_V36_MAIN_INPUT_CF1_PORT', date=datetime.date.today().isoformat(),
        source_cf1_board=str(src_board.relative_to(A)).replace('\\', '/'), source_cf1_board_sha256=sha(src_board), cf1_build_receipt_sha256=sha(CF1 / 'results/pcb/NATIVE_BUILD.json'),
        v35_inherited_before=before, restore_point=str(HIST.relative_to(A)).replace('\\', '/'),
        value_deltas_applied=changed,
        result_board_sha256=sha(dst_board), result_project_sha256=sha(dst_pro),
        fingerprint_identical_to_v35_parent=(fp2 == parent_fp), values_identical_to_v35=(values2 == parent_values),
        footprints=len(fp2), stackup_3oz_persisted=(text.count('(thickness 0.105)') == 2),
        zones=len(list(b2.Zones())), vias=sum(1 for t in b2.GetTracks() if isinstance(t, k.PCB_VIA)),
        project_rules_from_cf1=True,
        owner_acceptance='2026-09-17 owner message: all CF1 design opinions accepted; the four DESIGN_SPEC_CF1 deviations and the Q201 pad-entry neck remain recorded open items',
        scope='Layout port only. Schematic, BOM and libraries of V36 unchanged; DRC/density receipts follow in the same results directory.',
        whole_design_complete=False, manufacturing_release=False)
    p = OUT / 'PORT_RECEIPT.json'
    p.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (OUT / 'PORT_RECEIPT.sha256').write_text(sha(p) + '  PORT_RECEIPT.json\n', encoding='utf-8')
    print(json.dumps(dict(result_sha=receipt['result_board_sha256'][:16], fingerprint_ok=receipt['fingerprint_identical_to_v35_parent'], values_ok=receipt['values_identical_to_v35'],
                          stackup=receipt['stackup_3oz_persisted'], zones=receipt['zones'], vias=receipt['vias'])))


if __name__ == '__main__':
    main()
