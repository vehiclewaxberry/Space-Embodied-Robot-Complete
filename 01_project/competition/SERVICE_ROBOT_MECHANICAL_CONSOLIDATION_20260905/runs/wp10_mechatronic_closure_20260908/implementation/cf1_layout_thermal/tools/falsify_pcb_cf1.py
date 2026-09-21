"""CF1 PCB negative controls on throwaway copies (nominal board untouched). KiCad 10 python + kicad-cli.
(a) remove the PRECHARGED via array           -> parallel-copper check must FAIL (B.Cu strip isolated)
(b) delete the Q201 drain stub polygon        -> native DRC must report >=1 unconnected item
(c) move one PRECHARGED via into the B.Cu return pour -> native DRC must report shorting_items / clearance error
(d) shrink the MAIN_FUSED band to 3 mm (in memory) -> current-density screen must FAIL (done in current_density_cf1.py)"""
from pathlib import Path
import hashlib, json, shutil, subprocess
import pcbnew as k

HERE = Path(__file__).resolve().parent
C = HERE.parent
A = C.parent
ROOT = next(p for p in A.parents if (p / 'PROJECT_MAP.md').is_file())
CLI = ROOT / '70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe'
E = C / 'ecad'
R = C / 'results/pcb'
MM = k.FromMM
mm = lambda v: v / 1e6


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def drc(board_path, out):
    q = subprocess.run([str(CLI), 'pcb', 'drc', '--format', 'json', '--severity-all', '-o', str(out), str(board_path)],
                       cwd=E, capture_output=True, text=True, encoding='utf-8', errors='replace')
    d = json.loads(Path(out).read_text(encoding='utf-8-sig'))
    return dict(returncode=q.returncode, stdout=q.stdout.strip(), violations=len(d['violations']),
                unconnected=len(d['unconnected_items']), types=sorted({v['type'] for v in d['violations']}))


def parallel_copper_ok(board):
    """B.Cu PRECHARGED strip must be tied to F.Cu by >=12 vias of the same net inside its outline (DESIGN_SPEC 4.3)."""
    strips = [dr for dr in board.GetDrawings() if isinstance(dr, k.PCB_SHAPE) and dr.GetShape() == k.SHAPE_T_POLY
              and dr.GetNetname() == 'WP10_PRECHARGED_PLUS' and board.GetLayerName(dr.GetLayer()) == 'B.Cu']
    if len(strips) != 1:
        return False, dict(strips=len(strips))
    bb = strips[0].GetBoundingBox()
    n = 0
    for t in board.GetTracks():
        if isinstance(t, k.PCB_VIA) and t.GetNetname() == 'WP10_PRECHARGED_PLUS':
            p = t.GetPosition()
            if bb.GetLeft() <= p.x <= bb.GetRight() and bb.GetTop() <= p.y <= bb.GetBottom():
                n += 1
    return n >= 12, dict(strips=1, vias_inside=n)


def main():
    nominal = E / 'wp10_main_input.kicad_pcb'
    nominal_sha = sha(nominal)
    pro = E / 'wp10_main_input.kicad_pro'
    cases = []
    # (a) via array removed
    pa = E / 'negative_cf1_no_via_array.kicad_pcb'
    b = k.LoadBoard(str(nominal))
    removed = [t for t in b.GetTracks() if isinstance(t, k.PCB_VIA) and t.GetNetname() == 'WP10_PRECHARGED_PLUS']
    for t in removed:
        b.Remove(t)
    keep = removed  # keep wrappers alive
    b.BuildConnectivity()
    ok, detail = parallel_copper_ok(b)
    k.SaveBoard(str(pa), b)
    shutil.copy2(pro, pa.with_suffix('.kicad_pro'))
    cases.append(dict(case='negative_no_via_array', edit=dict(vias_removed=len(removed)), parallel_copper_check_ok=ok, detail=detail,
                      detection_passed=(not ok), fixture_sha256=sha(pa)))
    # (b) drain stub removed
    pb = E / 'negative_cf1_no_drain_stub.kicad_pcb'
    b = k.LoadBoard(str(nominal))
    stub = None
    for dr in b.GetDrawings():
        if isinstance(dr, k.PCB_SHAPE) and dr.GetShape() == k.SHAPE_T_POLY and dr.GetNetname() == 'WP10_MAIN_SENSE':
            bb = dr.GetBoundingBox()
            if abs(mm(bb.GetTop()) - 15.0) < 1e-3 and abs(mm(bb.GetBottom()) - 17.0) < 1e-3:
                stub = dr
    assert stub is not None
    b.Remove(stub); keep.append(stub); b.BuildConnectivity()
    k.SaveBoard(str(pb), b)
    shutil.copy2(pro, pb.with_suffix('.kicad_pro'))
    rb = drc(pb, R / 'negative_cf1_no_drain_stub_DRC.json')
    cases.append(dict(case='negative_no_drain_stub', edit=dict(removed='MAIN_SENSE stub polygon x57.6-61.3 y15-17'), drc=rb,
                      detection_passed=rb['unconnected'] >= 1, fixture_sha256=sha(pb)))
    # (c) one PRECHARGED via moved into the B.Cu return pour (y 12): F.Cu side still on the PRECHARGED band,
    #     B.Cu side lands in WP10_INPUT_RETURN copper -> a real short that native DRC must report.
    #     (KiCad net propagation re-assigns a via's net from the copper it touches, so a "wrong-net via"
    #     cannot be expressed as a persistent edit; a mis-placed via is the physical counterexample.)
    pc = E / 'negative_cf1_via_in_return_pour.kicad_pcb'
    b = k.LoadBoard(str(nominal))
    vias = [t for t in b.GetTracks() if isinstance(t, k.PCB_VIA) and t.GetNetname() == 'WP10_PRECHARGED_PLUS']
    moved = vias[0]
    old_xy = [mm(moved.GetPosition().x), mm(moved.GetPosition().y)]
    moved.SetPosition(k.VECTOR2I(MM(69.3), MM(12.0)))
    b.BuildConnectivity()
    k.SaveBoard(str(pc), b)
    chk = k.LoadBoard(str(pc))
    at = [t for t in chk.GetTracks() if isinstance(t, k.PCB_VIA) and abs(mm(t.GetPosition().x) - 69.3) < 1e-3 and abs(mm(t.GetPosition().y) - 12.0) < 1e-3]
    assert len(at) == 1, 'via move did not persist'
    shutil.copy2(pro, pc.with_suffix('.kicad_pro'))
    rc = drc(pc, R / 'negative_cf1_via_in_return_pour_DRC.json')
    cases.append(dict(case='negative_via_in_return_pour', edit=dict(via_moved_from_mm=old_xy, to_mm=[69.3, 12.0], net_after_reload=at[0].GetNetname()),
                      drc=rc, detection_passed=(rc['violations'] >= 1 and any(t in ('shorting_items', 'clearance', 'copper_sliver') for t in rc['types'])),
                      fixture_sha256=sha(pc)))
    nominal_ok, nominal_detail = parallel_copper_ok(k.LoadBoard(str(nominal)))
    out = dict(schema='CF1_PCB_COUNTEREXAMPLES', passed=all(c['detection_passed'] for c in cases) and nominal_ok,
               nominal_board_sha256_before=nominal_sha, nominal_board_unchanged=sha(nominal) == nominal_sha,
               nominal_parallel_copper_check=nominal_detail, cases=cases, hardware_tests=0)
    (R / 'COUNTEREXAMPLES.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(passed=out['passed'], nominal_unchanged=out['nominal_board_unchanged'],
                          cases=[(c['case'], c['detection_passed']) for c in cases])))


if __name__ == '__main__':
    main()
