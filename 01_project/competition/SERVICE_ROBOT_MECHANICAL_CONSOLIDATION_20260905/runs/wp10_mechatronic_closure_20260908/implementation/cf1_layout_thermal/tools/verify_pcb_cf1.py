"""CF1 PCB validation aggregate (KiCad 10 python). Writes results/pcb/VALIDATION.json.
Every check names what it does and does not establish; a check that cannot fail is not a check."""
from pathlib import Path
import hashlib, json
import pcbnew as k

HERE = Path(__file__).resolve().parent
C = HERE.parent
A = C.parent
E = C / 'ecad'
R = C / 'results/pcb'
PARENT = A / 'ecad/revisions/v32'
VIA_ARRAY_MIN = 12          # DESIGN_SPEC_CF1.md section 4.3 (">=12 holes per array")
mm = lambda v: v / 1e6


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def fingerprint(b):
    fps = []
    for f in b.GetFootprints():
        pads = [dict(pin=p.GetNumber(), net=p.GetNetname(), xy=[p.GetPosition().x, p.GetPosition().y],
                     size=[p.GetSize().x, p.GetSize().y], drill=[p.GetDrillSize().x, p.GetDrillSize().y],
                     shape=int(p.GetShape()), layers=list(p.GetLayerSet().Seq())) for p in f.Pads()]
        fps.append(dict(ref=f.GetReference(), fp=str(f.GetFPID().GetLibItemName()), xy=[f.GetPosition().x, f.GetPosition().y],
                        angle=f.GetOrientationDegrees(), jumpers=f.GetDuplicatePadNumbersAreJumpers(),
                        pads=sorted(pads, key=lambda p: (p['pin'], p['xy'][0], p['xy'][1]))))
    return sorted(fps, key=lambda x: x['ref'])


def main():
    checks = []
    def ck(name, passed, **detail):
        checks.append(dict(name=name, passed=bool(passed), **detail))
    lock = read(C / 'results/PARENT_SOURCE_LOCK.json')
    parent_files = {p: h for p, h in lock['sources'].items() if p.startswith('ecad/revisions/v32/')}
    drift = [p for p, h in parent_files.items() if not (A / p).is_file() or sha(A / p) != h]
    ck('parent_V32_ecad_bytes_unchanged', not drift, files=len(parent_files), drift=drift)
    build = read(R / 'NATIVE_BUILD.json')
    board_path = E / 'wp10_main_input.kicad_pcb'
    board = k.LoadBoard(str(board_path))
    parent = k.LoadBoard(str(PARENT / 'wp10_main_input.kicad_pcb'))
    board_sha = sha(board_path)
    ck('board_sha256_matches_build_receipt', board_sha == build['board_sha256'])
    fp_b, fp_p = fingerprint(board), fingerprint(parent)
    ck('pad_geometry_and_net_fingerprint_identical_to_parent', fp_b == fp_p, footprints=len(fp_b),
       covers='reference, library name, position, angle, jumper flag, pad number/net/xy/size/drill/shape/layers',
       not_covered_but_changed_by_the_build=dict(footprint_type_attributes_set=len(build['footprint_attributes_set']),
                                                  courtyards_added=len(build['courtyards_added']),
                                                  library_files_rewritten=len(build['library_attributes_set'])),
       note='43 footprints = 35 component references + MH1-4 + 4 PORT_* embedded footprints')
    ck('kelvin_internal_connection_attributes_retained',
       all(f.GetDuplicatePadNumbersAreJumpers() for f in board.GetFootprints() if f.GetReference() in ('R201', 'R202')))
    text = board_path.read_text(encoding='utf-8')
    ck('stackup_3oz_both_outer_layers_persisted', text.count('(thickness 0.105)') == 2 and '(stackup' in text,
       note='text-level guard; current_density_cf1.py reads the same stackup block and asserts it')
    rects = [(dr.GetNetname(), board.GetLayerName(dr.GetLayer()), round(mm(dr.GetBoundingBox().GetLeft()), 2), round(mm(dr.GetBoundingBox().GetTop()), 2),
              round(mm(dr.GetBoundingBox().GetRight()), 2), round(mm(dr.GetBoundingBox().GetBottom()), 2))
             for dr in board.GetDrawings() if isinstance(dr, k.PCB_SHAPE) and dr.GetShape() == k.SHAPE_T_POLY and dr.GetNetname()]
    expected = [(r['net'], r['layer'], *[round(v, 2) for v in r['rect_mm']]) for r in build['copper_rects']]
    ck('copper_rectangles_match_build_table', sorted(rects) == sorted(expected), count=len(rects))
    bands = [r for r in rects if r[1] == 'F.Cu' and r[3] < 10 and (r[4] - r[2]) > (r[5] - r[3])]
    ck('forward_bands_width_ge_8mm', all((r[5] - r[3]) >= 8.0 - 1e-6 for r in bands) and len(bands) == 5, bands=len(bands),
       spec_deviation='DESIGN_SPEC_CF1.md 4.2 asked for a 10 mm F201 land connection; delivered bands are 8 mm (plan corridor y 8-16)')
    strip = [r for r in rects if r[1] == 'B.Cu' and r[0] == 'WP10_PRECHARGED_PLUS']
    vias = [t for t in board.GetTracks() if isinstance(t, k.PCB_VIA)]
    inside = 0
    if len(strip) == 1:
        s = strip[0]
        inside = sum(1 for v in vias if v.GetNetname() == 'WP10_PRECHARGED_PLUS' and s[2] <= mm(v.GetPosition().x) <= s[4] and s[3] <= mm(v.GetPosition().y) <= s[5])
    ck('parallel_copper_strip_with_via_array', len(strip) == 1 and inside >= VIA_ARRAY_MIN, vias_inside=inside, vias_total=len(vias), threshold=VIA_ARRAY_MIN,
       spec_deviation='DESIGN_SPEC_CF1.md 4.3 asked for B.Cu parallel copper at both ends of F201 and of R201/R202; the B.Cu under those bands is the return pour, '
                      'so one strip on WP10_PRECHARGED_PLUS was built instead (see README_CF1.md section 3 deviations)')
    zones = [z for z in board.Zones()]
    zone = [z for z in zones if z.GetZoneName() == 'CF1_RETURN_TIM_CONTACT']
    area = zone[0].GetFilledArea() / 1e12 if zone else 0.0
    ck('return_TIM_contact_zone_filled', len(zone) == 1 and zone[0].GetNetname() == 'WP10_INPUT_RETURN' and area >= 600.0, filled_area_mm2=area,
       spec_deviation='DESIGN_SPEC_CF1.md 4.4 asked for return + forward pours totalling >= 60x40 mm with forward thermal vias; delivered is the return pour only, 704 mm2 outline')
    attr_ok = True; missing_cy = []
    for f in board.GetFootprints():
        if not any(it.GetLayer() == k.F_CrtYd for it in f.GraphicalItems()):
            missing_cy.append(f.GetReference())
        if f.GetReference() in ('Q201', 'C201', 'C202', 'C211', 'C212', 'C213') and not (f.GetAttributes() & k.FP_THROUGH_HOLE):
            attr_ok = False
        if f.GetReference() in ('U201', 'U205', 'D201', 'D202', 'R201', 'R202') and not (f.GetAttributes() & k.FP_SMD):
            attr_ok = False
    ck('footprint_type_attributes_set', attr_ok)
    ck('every_footprint_has_courtyard', not missing_cy, missing=missing_cy)
    drc = read(R / 'MAIN_INPUT_DRC.json')
    ck('native_DRC_clean_all_rule_severities_enabled', not drc['violations'] and not drc['unconnected_items'] and not drc['ignored_checks'],
       kicad=drc.get('kicad_version'), ignored=[x['key'] for x in drc['ignored_checks']],
       note='severity statement: footprint_filters_mismatch is evaluated by the schematic-parity provider, which could not run (see parity check)')
    erc = read(R / 'SYSTEM_ERC.json')
    ck('system_ERC_no_violations', sum(len(s['violations']) for s in erc['sheets']) == 0, sheets=len(erc['sheets']),
       default_ignored_checks=[x['key'] for x in erc.get('ignored_checks', [])],
       note='wp10_system.kicad_pro is an empty project, so ERC ran with KiCad default severities (4 checks ignored by default)')
    parity_json = R / 'MAIN_INPUT_DRC_PARITY.json'; parity_log = R / 'MAIN_INPUT_DRC_PARITY.log'
    pj = read(parity_json) if parity_json.exists() else None
    plog = parity_log.read_text(encoding='utf-8', errors='replace') if parity_log.exists() else ''
    parity_ok = (pj is not None and pj.get('source') == 'wp10_main_input.kicad_pcb' and not pj['violations'] and not pj['unconnected_items']
                 and 'Schematic parity tests require a fully annotated schematic' in plog
                 and parity_json.stat().st_mtime >= board_path.stat().st_mtime)
    ck('schematic_parity_refusal_recorded_for_delivered_board', parity_ok, status='NOT_EXECUTABLE_SCHEMATIC_NOT_FULLY_ANNOTATED' if parity_ok else 'RECEIPT_MISSING_OR_STALE',
       receipt_date=(pj or {}).get('date'), board_sha256=board_sha,
       note='kicad-cli pcb drc --schematic-parity on the delivered board: refusal text captured in MAIN_INPUT_DRC_PARITY.log; same limit as V32')
    cd = read(R / 'CURRENT_DENSITY_CF1.json')
    acc = cd['acceptance']
    ck('stackup_copper_thickness_read_by_density_model', abs(acc['stackup_copper_thickness_mm'] - 0.105) < 1e-9)
    ck('forward_band_current_density_le_35', acc['forward_band_density_ok'], worst_band_A_mm2=cd['cf1']['worst_band_current_density_A_mm2'])
    ck('forward_current_density_le_35_including_Q201_pad_entry_necks', acc['forward_density_ok_including_pad_entry_necks'],
       worst_neck_A_mm2=acc['pad_entry_neck_density_A_mm2'], note=acc['pad_entry_neck_note'])
    ck('copper_loss_reduction_ge_40pct_same_path_definition_as_V29', acc['loss_reduction_ok'] and acc['parent_model_replays_recorded_loss'],
       cf1_R20_mohm=cd['cf1']['R20_total_ohm'] * 1e3, parent_R20_mohm=cd['parent']['R20_total_ohm'] * 1e3,
       cf1_loss_20A_100C_W=cd['cf1']['loss_20A_100C_W'], reduction=acc['loss_reduction_vs_V29_recorded'], reduction_bands_only_model=acc['loss_reduction_bands_only_model'])
    ck('density_model_controls', acc['arithmetic_control_3mm_band_exceeds_limit'] and acc['segment_selection_control_necks_change_worst_density'])
    ce = read(R / 'COUNTEREXAMPLES.json')
    ck('layout_negative_controls_detected', ce['passed'] and ce['nominal_board_unchanged'], cases=[(c['case'], c['detection_passed']) for c in ce['cases']],
       note='the DESIGN_SPEC wrong-net-via case is replaced by a via moved into the return pour (KiCad net propagation makes a persistent wrong-net via inexpressible)')
    # DESIGN_SPEC_CF1.md section 4 conformance: these are the spec values, not the as-built ones; they FAIL until the owner accepts the deviations
    f201 = [r for r in bands if r[0] == 'WP10_MAIN_FUSED']
    ck('SPEC_4_2_F201_land_width_ge_10mm', bool(f201) and all((r[5] - r[3]) >= 10.0 - 1e-6 for r in f201), delivered_mm=[round(r[5] - r[3], 2) for r in f201], spec_conformance=True)
    bcu_nets = {r[0] for r in rects if r[1] == 'B.Cu' and r[0] in ('WP10_MAIN_FUSED', 'WP10_SENSE_MID', 'WP10_MAIN_SENSE')}
    ck('SPEC_4_3_parallel_copper_at_F201_and_R201_R202_ends', bcu_nets >= {'WP10_MAIN_FUSED', 'WP10_SENSE_MID', 'WP10_MAIN_SENSE'}, delivered_bcu_nets=sorted(bcu_nets), spec_conformance=True)
    fwd_pour = [z for z in zones if z.GetNetname() in ('WP10_MAIN_SENSE', 'WP10_PRECHARGED_PLUS', 'WP10_MAIN_FUSED') and board.GetLayerName(z.GetLayer()) == 'B.Cu']
    ck('SPEC_4_4_TIM_pours_return_plus_forward_ge_2400mm2', area + sum(z.GetFilledArea() / 1e12 for z in fwd_pour) >= 2400.0 and bool(fwd_pour),
       delivered_return_mm2=area, delivered_forward_pours=len(fwd_pour), spec_conformance=True)
    out = dict(schema='CF1_PCB_VALIDATION', passed=all(c['passed'] for c in checks), checks_run=len(checks),
               failed=[c['name'] for c in checks if not c['passed']], checks=checks,
               scope='EDA layout increment on the V32 parent (Kelvin-corrected). No fabrication, ampacity, SOA, assembly or energization credit.',
               parent_board_sha256=build['parent_board_sha256'], board_sha256=build['board_sha256'],
               hardware_tests=0, whole_design_complete=False)
    (R / 'VALIDATION.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(passed=out['passed'], failed=out['failed'], checks=[(c['name'], c['passed']) for c in checks]), ensure_ascii=False))


if __name__ == '__main__':
    main()
