"""Main-path copper loss and current density: V32 parent (70 um) vs CF1 (105 um). KiCad python (pcbnew).

Model: series centreline segments of the forward and return paths. For CF1 the forward path is made of
filled copper rectangles (PCB_SHAPE polygons): five bands (current along x, conductor length = x-extent,
width = y-extent) plus the two Q201 pad-entry necks (the 3.7 mm and 4.2 mm stubs between the MAIN_SENSE /
PRECHARGED bands and Q201 pads 2/3). The necks ARE series conductors: the whole main current crosses them.
Their resistance is booked with the parent V29 convention (length to the pad centre, 2.0 mm) so that the
parent/CF1 R20 comparison uses the same path definition; their current density is evaluated on the neck
width. B.Cu parallel rectangles are combined in parallel with the overlapping F.Cu length. Via resistance
is omitted (slightly optimistic for the parallel branch, ~0.02 mOhm). Copper thickness is read from the
board stackup text and asserted. 20 C resistivity 1.724e-8 ohm.m (matches the V29 receipt to 6e-5),
alpha 0.00393/K, evaluated at 100 C. Hot-case current 24.44 A (COUPLED_RESULTS point: pack 20 V, eta 0.85,
Q201 x2). One-dimensional vacuum estimate: segment heat conducts through 1.6 mm FR4 (k 0.3 W/mK) over the
segment footprint to the B.Cu return copper; delta-T = q*R_FR4. No convection credit."""
from pathlib import Path
import json, re
import pcbnew as k

HERE = Path(__file__).resolve().parent
C = HERE.parent
A = C.parent
R = C / 'results/pcb'
RHO20 = 1.724e-8
ALPHA = 0.00393
T_HOT = 100.0
I_HOT = 24.44
I_20A = 20.0
J_LIMIT = 35.0
FORWARD = ['WP10_BAT_PROTECTED_PLUS', 'WP10_MAIN_FUSED', 'WP10_SENSE_MID', 'WP10_MAIN_SENSE', 'WP10_PRECHARGED_PLUS']
RETURN = 'WP10_INPUT_RETURN'
NECK_LENGTH_PARENT_CONVENTION_MM = 2.0     # band edge (y 15) to pad centre (y 17), as V29 booked its 2.6 mm necks
NECK_LENGTH_TO_PAD_EDGE_MM = 0.5           # band edge (y 15) to pad copper edge (y 15.5): the physical neck
mm = lambda v: v / 1e6


def r20(length_mm, width_mm, thick_mm):
    return RHO20 * (length_mm * 1e-3) / ((width_mm * 1e-3) * (thick_mm * 1e-3))


def hot(r):
    return r * (1 + ALPHA * (T_HOT - 20))


def stackup_copper_thickness_mm(board_path):
    """Outer copper thickness from the saved stackup block (F.Cu and B.Cu must agree)."""
    txt = Path(board_path).read_text(encoding='utf-8')
    blk = txt[txt.index('(stackup'):]
    vals = []
    for layer in ('F.Cu', 'B.Cu'):
        m = re.search(r'\(layer "%s"[^)]*?\(type "copper"\)\s*\(thickness ([0-9.]+)\)' % re.escape(layer), blk, re.S)
        assert m, layer
        vals.append(float(m.group(1)))
    assert vals[0] == vals[1], vals
    return vals[0]


def parent_segments():
    """V29/V32 series centreline model (same numbers as power/MAIN_INPUT_COPPER_LOSS_V29.json)."""
    d = json.loads((A / 'power/MAIN_INPUT_COPPER_LOSS_V29.json').read_text(encoding='utf-8-sig'))
    out = []
    for s in d['main_path_segments']:
        out.append(dict(net=s['net'], layer=s['layer'], role=s['role'], length_mm=s['length_mm'], width_mm=s['width_mm'],
                        thick_mm=d['reference_copper_thickness_mm'], R20_ohm=r20(s['length_mm'], s['width_mm'], d['reference_copper_thickness_mm'])))
    return out, d['reference_copper_thickness_mm']


def cf1_segments(board_path, include_necks=True):
    b = k.LoadBoard(str(board_path))
    thick = stackup_copper_thickness_mm(board_path)
    rects = []
    for dr in b.GetDrawings():
        if isinstance(dr, k.PCB_SHAPE) and dr.GetShape() == k.SHAPE_T_POLY and dr.GetNetname() and b.GetLayerName(dr.GetLayer()).endswith('.Cu'):
            bb = dr.GetBoundingBox()
            rects.append(dict(net=dr.GetNetname(), layer=b.GetLayerName(dr.GetLayer()), x0=mm(bb.GetLeft()), x1=mm(bb.GetRight()),
                              y0=mm(bb.GetTop()), y1=mm(bb.GetBottom())))
    segs = []
    for r in rects:
        if r['net'] not in FORWARD or r['layer'] != 'F.Cu':
            continue
        is_band = r['y0'] < 10.0 and (r['x1'] - r['x0']) > (r['y1'] - r['y0'])
        is_neck = abs(r['y0'] - 15.0) < 1e-6 and (r['x1'] - r['x0']) < 6.0      # Q201 pad-entry stubs; via-landing rects start at y 16
        if is_band:
            L = r['x1'] - r['x0']; W = r['y1'] - r['y0']
            Rr = r20(L, W, thick)
            par = [p for p in rects if p['net'] == r['net'] and p['layer'] == 'B.Cu']
            for p in par:
                ov = max(0.0, min(r['x1'], p['x1']) - max(r['x0'], p['x0']))
                if ov > 0:
                    rf = r20(ov, W, thick); rb = r20(ov, p['y1'] - p['y0'], thick)
                    Rr = Rr - rf + (rf * rb) / (rf + rb)
            segs.append(dict(net=r['net'], layer='F.Cu(+B.Cu parallel)' if par else 'F.Cu', role='MAIN_FORWARD', length_mm=L, width_mm=W, thick_mm=thick, R20_ohm=Rr,
                             parallel_overlap_mm=sum(max(0.0, min(r['x1'], p['x1']) - max(r['x0'], p['x0'])) for p in par)))
        elif is_neck and include_necks:
            W = r['x1'] - r['x0']
            segs.append(dict(net=r['net'], layer='F.Cu', role='MAIN_FORWARD_NECK', length_mm=NECK_LENGTH_PARENT_CONVENTION_MM, width_mm=W, thick_mm=thick,
                             R20_ohm=r20(NECK_LENGTH_PARENT_CONVENTION_MM, W, thick), physical_neck_length_mm=NECK_LENGTH_TO_PAD_EDGE_MM,
                             note='Q201 pad-entry stub x %.1f-%.1f; length booked to the pad centre (V29 convention)' % (r['x0'], r['x1'])))
    for t in b.GetTracks():
        if isinstance(t, k.PCB_VIA) or t.GetNetname() != RETURN or b.GetLayerName(t.GetLayer()) != 'B.Cu' or abs(mm(t.GetWidth()) - 8.0) > 1e-3:
            continue
        L = mm(t.GetLength()); W = 8.0
        sx, ex = mm(t.GetStart().x), mm(t.GetEnd().x); sy, ey = mm(t.GetStart().y), mm(t.GetEnd().y)
        horizontal_in_zone = abs(sy - ey) < 1e-6 and abs(sy - 10.0) < 1e-6 and min(sx, ex) >= 18 - 1e-6 and max(sx, ex) <= 82 + 1e-6
        if horizontal_in_zone:
            W = 11.0  # zone y 3-14 merged with the 8 mm track (y 6-14)
        segs.append(dict(net=RETURN, layer='B.Cu' + ('+zone' if horizontal_in_zone else ''), role='MAIN_RETURN', length_mm=L, width_mm=W, thick_mm=thick,
                         R20_ohm=r20(L, W, thick)))
    return segs, thick


def summarize(label, segs, thick):
    fwd = [s for s in segs if s['role'].startswith('MAIN_FORWARD')]
    ret = [s for s in segs if s['role'] == 'MAIN_RETURN']
    R20f = sum(s['R20_ohm'] for s in fwd); R20r = sum(s['R20_ohm'] for s in ret); R20 = R20f + R20r
    rows = []; worst_dT = 0.0
    for s in segs:
        j = I_HOT / (s['width_mm'] * s['thick_mm'])
        q = I_HOT ** 2 * hot(s['R20_ohm'])
        area = s['length_mm'] * s['width_mm'] * 1e-6
        R_fr4 = 1.6e-3 / (0.3 * area) if area > 0 else float('inf')
        dT = q * R_fr4 if s['role'] != 'MAIN_FORWARD_NECK' else None   # a 0.5-2 mm neck spreads its heat laterally in copper; the 1-D FR4 estimate is meaningless there
        rows.append(dict(**s, current_density_A_mm2=j, hot_loss_W=q, R_FR4_K_W=R_fr4, vacuum_1D_deltaT_K=dT))
        if dT is not None:
            worst_dT = max(worst_dT, dT)
    bands = [r for r in rows if r['role'] == 'MAIN_FORWARD']; necks = [r for r in rows if r['role'] == 'MAIN_FORWARD_NECK']
    return dict(label=label, copper_thickness_mm=thick, R20_forward_ohm=R20f, R20_return_ohm=R20r, R20_total_ohm=R20,
                loss_20A_100C_W=I_20A ** 2 * hot(R20), loss_hot_24p44A_100C_W=I_HOT ** 2 * hot(R20),
                worst_forward_current_density_A_mm2=max(r['current_density_A_mm2'] for r in rows if r['role'].startswith('MAIN_FORWARD')),
                worst_band_current_density_A_mm2=max(r['current_density_A_mm2'] for r in bands) if bands else None,
                worst_neck_current_density_A_mm2=max(r['current_density_A_mm2'] for r in necks) if necks else None,
                worst_vacuum_1D_deltaT_K=worst_dT, segments=rows)


def main():
    p_segs, p_thick = parent_segments()
    board = C / 'ecad/wp10_main_input.kicad_pcb'
    c_segs, c_thick = cf1_segments(board)
    parent = summarize('V32_PARENT_70um_series_model', p_segs, p_thick)
    cf1 = summarize('CF1_105um_bands_plus_pad_entry_necks', c_segs, c_thick)
    bands_only = summarize('CF1_bands_only_(necks_excluded)', cf1_segments(board, include_necks=False)[0], c_thick)
    parent_loss = 4.510211938117723  # recorded in MAIN_INPUT_COPPER_LOSS_V29.json (20 A, 100 C)
    reduction = 1 - cf1['loss_20A_100C_W'] / parent_loss
    accept = dict(forward_density_limit_A_mm2=J_LIMIT,
                  forward_band_density_ok=cf1['worst_band_current_density_A_mm2'] <= J_LIMIT,
                  forward_density_ok_including_pad_entry_necks=cf1['worst_forward_current_density_A_mm2'] <= J_LIMIT,
                  pad_entry_neck_density_A_mm2=cf1['worst_neck_current_density_A_mm2'],
                  pad_entry_neck_note='The TO-247 pad entry (3.7 / 4.2 mm wide, 0.5 mm long, 105 um) carries the full main current; on F.Cu alone it cannot meet '
                                      '35 A/mm2 without a wider footprint or thicker copper. The parent V29 booked the same necks at 2.6 mm width (134 A/mm2 at 70 um). '
                                      'No part or footprint substitution is allowed in CF1, so this is an OPEN item, not a silent pass.',
                  loss_reduction_vs_V29_recorded=reduction, loss_reduction_min=0.40, loss_reduction_ok=reduction >= 0.40,
                  loss_reduction_bands_only_model=1 - bands_only['loss_20A_100C_W'] / parent_loss,
                  parent_model_replays_recorded_loss=abs(parent['loss_20A_100C_W'] - parent_loss) / parent_loss < 1e-3,
                  parent_replay_relative_error=abs(parent['loss_20A_100C_W'] - parent_loss) / parent_loss,
                  stackup_copper_thickness_mm=c_thick)
    # controls: (d) arithmetic: one band at 3 mm must exceed the limit; (e) dropping the necks must lower the worst density (shows the segment selection matters)
    neg = [dict(s) for s in c_segs]
    for s in neg:
        if s['net'] == 'WP10_MAIN_FUSED' and s['role'] == 'MAIN_FORWARD':
            s['width_mm'] = 3.0; s['R20_ohm'] = r20(s['length_mm'], 3.0, s['thick_mm']); s['layer'] = 'F.Cu(negative 3 mm)'
    negsum = summarize('ARITHMETIC_CONTROL_ONE_BAND_3mm', neg, c_thick)
    accept['arithmetic_control_3mm_band_exceeds_limit'] = negsum['worst_band_current_density_A_mm2'] > J_LIMIT
    accept['segment_selection_control_necks_change_worst_density'] = cf1['worst_forward_current_density_A_mm2'] > bands_only['worst_forward_current_density_A_mm2'] + 10.0
    out = dict(schema='CF1_COPPER_LOSS_AND_CURRENT_DENSITY', method=__doc__, hot_current_A=I_HOT, parent=parent, cf1=cf1,
               bands_only_model=dict(R20_total_ohm=bands_only['R20_total_ohm'], loss_20A_100C_W=bands_only['loss_20A_100C_W'],
                                     worst_forward_current_density_A_mm2=bands_only['worst_forward_current_density_A_mm2']),
               arithmetic_control=dict(worst_band_current_density_A_mm2=negsum['worst_band_current_density_A_mm2'], loss_20A_100C_W=negsum['loss_20A_100C_W']),
               acceptance=accept, excluded=['vias (omitted; slightly optimistic for the parallel branch)', 'lug and stud contacts', 'solder/pad spreading', 'PTH plating and barrel',
                                            'etch tolerance', 'temperature gradients', 'convection (none in vacuum)'],
               qualified=False)
    (R / 'CURRENT_DENSITY_CF1.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (R / 'COPPER_LOSS_CF1.json').write_text(json.dumps(dict(schema='CF1_CONDITIONAL_COPPER_LOSS', copper_thickness_mm=c_thick,
        R20_ohm=cf1['R20_total_ohm'], R20_forward_ohm=cf1['R20_forward_ohm'], R20_return_ohm=cf1['R20_return_ohm'],
        loss_20A_100C_W=cf1['loss_20A_100C_W'], loss_hot_24p44A_100C_W=cf1['loss_hot_24p44A_100C_W'],
        parent_R20_ohm=parent['R20_total_ohm'], parent_loss_20A_100C_W=parent['loss_20A_100C_W'],
        segments=cf1['segments'], qualified=False), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(parent_R20_mohm=parent['R20_total_ohm'] * 1e3, cf1_R20_mohm=cf1['R20_total_ohm'] * 1e3, bands_only_R20_mohm=bands_only['R20_total_ohm'] * 1e3,
                          parent_loss20=parent['loss_20A_100C_W'], cf1_loss20=cf1['loss_20A_100C_W'], reduction=reduction,
                          worst_band_J=cf1['worst_band_current_density_A_mm2'], worst_neck_J=cf1['worst_neck_current_density_A_mm2'],
                          cf1_worst_dT=cf1['worst_vacuum_1D_deltaT_K'], acceptance={k: v for k, v in accept.items() if not isinstance(v, str)}), ensure_ascii=False))


if __name__ == '__main__':
    main()
