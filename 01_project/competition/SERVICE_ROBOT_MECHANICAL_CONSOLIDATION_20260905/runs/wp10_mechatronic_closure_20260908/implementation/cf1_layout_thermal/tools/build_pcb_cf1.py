"""CF1 main-input board build: 3 oz stackup, 8 mm forward copper, B.Cu parallel copper + via arrays,
B.Cu return pour (TIM contact zone), footprint attributes. Always rebuilds from the locked V32 parent.
Run with KiCad 10 python (pcbnew)."""
from pathlib import Path
import hashlib, json, re, shutil, sys
import pcbnew as k

HERE = Path(__file__).resolve().parent
C = HERE.parent                      # cf1_layout_thermal
A = C.parent                         # implementation
PARENT = A / 'ecad/revisions/v32'
E = C / 'ecad'
R = C / 'results/pcb'
R.mkdir(parents=True, exist_ok=True)
MM = k.FromMM
KEEP_ALIVE = []


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def mm(v): return v / 1e6


def log(*a):
    print('[cf1]', *a, flush=True)


def geometry(b):
    """Fingerprint of footprints/pads (must stay identical) and tracks (will change)."""
    fps = []
    for f in b.GetFootprints():
        pads = [dict(pin=p.GetNumber(), net=p.GetNetname(), xy=[p.GetPosition().x, p.GetPosition().y],
                     size=[p.GetSize().x, p.GetSize().y], drill=[p.GetDrillSize().x, p.GetDrillSize().y],
                     shape=int(p.GetShape()), layers=list(p.GetLayerSet().Seq())) for p in f.Pads()]
        fps.append(dict(ref=f.GetReference(), fp=str(f.GetFPID().GetLibItemName()), xy=[f.GetPosition().x, f.GetPosition().y],
                        angle=f.GetOrientationDegrees(), jumpers=f.GetDuplicatePadNumbersAreJumpers(),
                        pads=sorted(pads, key=lambda p: (p['pin'], p['xy'][0], p['xy'][1]))))
    return sorted(fps, key=lambda x: x['ref'])


STACKUP = ('\t\t(stackup\n'
           '\t\t\t(layer "F.SilkS" (type "Top Silk Screen"))\n'
           '\t\t\t(layer "F.Paste" (type "Top Solder Paste"))\n'
           '\t\t\t(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))\n'
           '\t\t\t(layer "F.Cu" (type "copper") (thickness 0.105))\n'
           '\t\t\t(layer "dielectric 1" (type "core") (thickness 1.37) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))\n'
           '\t\t\t(layer "B.Cu" (type "copper") (thickness 0.105))\n'
           '\t\t\t(layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))\n'
           '\t\t\t(layer "B.Paste" (type "Bottom Solder Paste"))\n'
           '\t\t\t(layer "B.SilkS" (type "Bottom Silk Screen"))\n'
           '\t\t\t(copper_finish "None")\n'
           '\t\t\t(dielectric_constraints no)\n'
           '\t\t)\n')

# --- design tables (mm, KiCad y down) -------------------------------------------------------
REMOVE_TRACKS = [  # (net, layer, start, end, width)
    ('WP10_BAT_PROTECTED_PLUS', 'F.Cu', (7.0, 15.0), (15.325, 15.0), 3.0),
    ('WP10_MAIN_FUSED', 'F.Cu', (24.675, 15.0), (31.535, 14.11), 3.0),
    ('WP10_SENSE_MID', 'F.Cu', (36.465, 14.11), (42.535, 14.11), 3.0),
    ('WP10_MAIN_SENSE', 'F.Cu', (47.465, 14.11), (50.0, 14.11), 3.0),
    ('WP10_MAIN_SENSE', 'F.Cu', (50.0, 14.11), (50.0, 10.0), 3.0),
    ('WP10_MAIN_SENSE', 'F.Cu', (50.0, 10.0), (59.45, 10.0), 5.0),
    ('WP10_MAIN_SENSE', 'F.Cu', (59.45, 10.0), (59.45, 17.0), 2.6),
    ('WP10_PRECHARGED_PLUS', 'F.Cu', (64.9, 17.0), (69.0, 17.0), 2.6),
    ('WP10_PRECHARGED_PLUS', 'F.Cu', (69.0, 17.0), (90.0, 17.0), 6.0),
    ('WP10_PRECHARGED_PLUS', 'F.Cu', (90.0, 17.0), (93.0, 15.0), 6.0),
    # feeders re-routed so via arrays do not sit on narrow tracks (DRC track_not_centered_on_via)
    ('WP10_MAIN_FUSED', 'F.Cu', (24.675, 15.0), (27.0, 18.5), 0.8),
    ('WP10_MAIN_FUSED', 'F.Cu', (27.0, 18.5), (28.0, 24.0), 0.8),
    ('WP10_PRECHARGED_PLUS', 'F.Cu', (69.0, 17.0), (70.0, 23.0), 0.8),
    ('WP10_PRECHARGED_PLUS', 'F.Cu', (70.0, 23.0), (70.0, 33.0), 0.8),
    ('WP10_PRECHARGED_PLUS', 'F.Cu', (70.0, 33.0), (74.0, 33.0), 0.8),
    ('WP10_PRECHARGED_PLUS', 'F.Cu', (74.0, 33.0), (74.0, 39.0), 0.8),
]
ADD_TRACKS = [  # (net, layer, start, end, width) replacement feeders
    ('WP10_MAIN_FUSED', 'F.Cu', (24.5, 25.0), (27.0, 25.0), 1.5),      # D201 feeder -> C202 pad1
    ('WP10_MAIN_FUSED', 'F.Cu', (27.0, 25.0), (28.0, 24.0), 1.5),
    ('WP10_PRECHARGED_PLUS', 'F.Cu', (74.0, 16.0), (74.0, 39.0), 0.8),  # band -> C211 pad1
    ('WP10_PRECHARGED_PLUS', 'F.Cu', (84.11, 17.0), (84.11, 14.0), 1.5),  # D202 pad2 feeder into the band
]
# filled copper rectangles [x0,y0,x1,y1] per net/layer (forward band y 8-16, MAIN_SENSE y 7-15 to clear gate pad)
COPPER_RECTS = [
    ('WP10_BAT_PROTECTED_PLUS', 'F.Cu', (3.0, 8.0, 16.9, 16.0), 'FORWARD_BAND'),
    ('WP10_MAIN_FUSED', 'F.Cu', (23.1, 8.0, 32.8, 16.0), 'FORWARD_BAND'),
    ('WP10_SENSE_MID', 'F.Cu', (35.2, 8.0, 43.8, 16.0), 'FORWARD_BAND'),
    ('WP10_MAIN_SENSE', 'F.Cu', (46.2, 7.0, 61.3, 15.0), 'FORWARD_BAND'),
    ('WP10_MAIN_SENSE', 'F.Cu', (57.6, 15.0, 61.3, 17.0), 'PAD_STUB_Q201_DRAIN'),
    ('WP10_PRECHARGED_PLUS', 'F.Cu', (62.8, 8.0, 93.0, 16.0), 'FORWARD_BAND'),
    ('WP10_PRECHARGED_PLUS', 'F.Cu', (62.8, 15.0, 67.0, 17.0), 'PAD_STUB_Q201_SOURCE'),
    ('WP10_PRECHARGED_PLUS', 'B.Cu', (68.7, 15.0, 77.6, 22.0), 'PARALLEL_BCU'),
    ('WP10_PRECHARGED_PLUS', 'F.Cu', (68.8, 16.0, 71.0, 21.5), 'VIA_LANDING_FCU'),
    ('WP10_PRECHARGED_PLUS', 'F.Cu', (75.4, 16.0, 77.6, 21.5), 'VIA_LANDING_FCU'),
]
# MAIN_FUSED B.Cu parallel copper dropped: F.Cu feeders (D201 TVS, C202 timing, LM5069 sense) and the
# Kelvin sense lands occupy x 23-33 / y 16-22; via arrays there would land on narrow tracks or sense pads.
VIA_ROWS = [16.2, 17.4, 18.6, 19.8, 21.0]
VIA_ARRAYS = [  # net, x columns
    ('WP10_PRECHARGED_PLUS', [69.3, 70.5, 75.9, 77.1]),
]
COURTYARD_MARGIN_MM = 0.25   # for board-embedded footprints without F.CrtYd (MH1-4, PORT_*)
RETURN_ZONE = ('WP10_INPUT_RETURN', 'B.Cu', (18.0, 3.0, 82.0, 14.0))
FP_ATTR = {'IXTH_TO247_G1D2S3_P5p45_Slots': 'THT', 'MKP2_D031001F00_P5_Slot2': 'THT', 'MKS2_D041501M00_P5_Slot2': 'THT',
           'MKS2_D044701O00_P5_Slot2': 'THT', 'C201_MKP2_1uF_P5_Slot2': 'THT',
           'LM5069_DGS10_P0p5_NoEP': 'SMD', 'LT3013_DE12_EP13_3x4_Pin1LeftTop': 'SMD', 'SMBJ30A_A1K2': 'SMD',
           'STPS3H100U_A1K2': 'SMD', 'WSLP2726_KelvinSplit_TwoTerminals': 'SMD'}
ENABLE_RULES = ['missing_courtyard', 'footprint_filters_mismatch', 'footprint_type_mismatch',
                'track_not_centered_on_via', 'tuning_profile_track_geometries']


def near(a, b, tol=1e-3): return abs(a - b) <= tol


def track_matches(t, b, net, layer, s, e, w):
    if isinstance(t, k.PCB_VIA) or t.GetNetname() != net or b.GetLayerName(t.GetLayer()) != layer:
        return False
    if not near(mm(t.GetWidth()), w):
        return False
    S, E = (mm(t.GetStart().x), mm(t.GetStart().y)), (mm(t.GetEnd().x), mm(t.GetEnd().y))
    return (all(near(a, c) for a, c in zip(S, s)) and all(near(a, c) for a, c in zip(E, e))) or \
           (all(near(a, c) for a, c in zip(S, e)) and all(near(a, c) for a, c in zip(E, s)))


def add_rect(board, net, layer_name, rect, tag):
    x0, y0, x1, y1 = rect
    s = k.PCB_SHAPE(board)
    s.SetShape(k.SHAPE_T_POLY)
    s.SetFilled(True)
    s.SetLayer(board.GetLayerID(layer_name))
    pts = [k.VECTOR2I(MM(x0), MM(y0)), k.VECTOR2I(MM(x1), MM(y0)), k.VECTOR2I(MM(x1), MM(y1)), k.VECTOR2I(MM(x0), MM(y1))]
    s.SetPolyPoints(pts)
    s.SetNet(net)
    s.SetWidth(0)
    board.Add(s)
    return dict(net=net.GetNetname(), layer=layer_name, rect_mm=list(rect), tag=tag, area_mm2=(x1 - x0) * (y1 - y0))


def main():
    receipt = dict(schema='CF1_PCB_NATIVE_BUILD', KiCad_version=k.Version(), parent=str(PARENT.relative_to(A).as_posix()),
                   parent_board_sha256=sha(PARENT / 'wp10_main_input.kicad_pcb'))
    # 0. refresh CF1 ecad copy from the locked parent (libraries + schematic + project)
    for src in PARENT.rglob('*'):
        if src.is_file():
            dst = E / src.relative_to(PARENT)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    board_path = E / 'wp10_main_input.kicad_pcb'
    # 1. stackup (text insertion before pcbnew load)
    text = board_path.read_text(encoding='utf-8')
    assert '(stackup' not in text, 'parent already has a stackup'
    text = text.replace('\t(setup\n', '\t(setup\n' + STACKUP, 1)
    assert text.count('(thickness 0.105)') == 2
    board_path.write_text(text, encoding='utf-8')
    board = k.LoadBoard(str(board_path))
    log('loaded')
    fp_before = geometry(board)
    receipt['footprint_pad_fingerprint_sha256'] = hashlib.sha256(json.dumps(fp_before, sort_keys=True).encode()).hexdigest()
    class _Nets(dict):
        def __missing__(self, name):
            n = board.FindNet(name)
            assert n is not None, name
            self[name] = n
            return n
    nets = _Nets()
    # 2. remove narrow forward tracks (single pass over the track list, then remove)
    all_tracks = [t for t in board.GetTracks()]
    removed = []
    to_remove = []
    for spec in REMOVE_TRACKS:
        hit = [t for t in all_tracks if track_matches(t, board, *spec)]
        assert len(hit) == 1, ('track not uniquely found', spec, len(hit))
        to_remove.append(hit[0])
        removed.append(dict(net=spec[0], layer=spec[1], start=spec[2], end=spec[3], width_mm=spec[4]))
    for t in to_remove:
        board.Remove(t)
    # Keep the Python wrappers of removed tracks alive until the process ends: freeing them lets
    # SWIG delete C++ objects still referenced by connectivity, which segfaults on the next Add().
    KEEP_ALIVE.extend(to_remove)
    board.BuildConnectivity()
    added_tracks = []
    for net_name, layer, s, e, w in ADD_TRACKS:
        tr = k.PCB_TRACK(board)
        tr.SetLayer(board.GetLayerID(layer))
        tr.SetStart(k.VECTOR2I(MM(s[0]), MM(s[1])))
        tr.SetEnd(k.VECTOR2I(MM(e[0]), MM(e[1])))
        tr.SetWidth(MM(w))
        tr.SetNet(nets[net_name])
        board.Add(tr)
        added_tracks.append(dict(net=net_name, layer=layer, start=s, end=e, width_mm=w))
    receipt['added_tracks'] = added_tracks
    log('feeder tracks added', len(added_tracks))
    receipt['removed_tracks'] = removed
    log('tracks removed', len(removed))
    # 3. copper rectangles (F.Cu bands + stubs, B.Cu parallel copper)
    rects = []
    for net_name, layer, rect, tag in COPPER_RECTS:
        rects.append(add_rect(board, nets[net_name], layer, rect, tag))
    receipt['copper_rects'] = rects
    log('rects added', len(rects))
    # 4. via arrays
    vias = []
    for net_name, cols in VIA_ARRAYS:
        for x in cols:
            for y in VIA_ROWS:
                v = k.PCB_VIA(board)
                v.SetViaType(k.VIATYPE_THROUGH)
                v.SetLayerPair(k.F_Cu, k.B_Cu)
                v.SetPosition(k.VECTOR2I(MM(x), MM(y)))
                v.SetDrill(MM(0.6))
                v.SetWidth(MM(1.0))
                v.SetNet(nets[net_name])
                board.Add(v)
                vias.append(dict(net=net_name, xy_mm=[x, y]))
    receipt['vias_added'] = len(vias)
    log('vias added', len(vias))
    # 5. B.Cu return zone (TIM contact copper)
    zn, zl, (x0, y0, x1, y1) = RETURN_ZONE
    z = k.ZONE(board)
    z.SetLayer(board.GetLayerID(zl))
    z.SetNet(nets[zn])
    z.SetZoneName('CF1_RETURN_TIM_CONTACT')
    z.Outline().NewOutline()
    for x, y in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]:
        z.Outline().Append(MM(x), MM(y))
    z.SetMinThickness(MM(0.25))
    z.SetLocalClearance(MM(0.3))
    z.SetPadConnection(k.ZONE_CONNECTION_FULL)
    log('zone outline done')
    board.Add(z)
    filler = k.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    zone_area = z.GetFilledArea() / 1e12  # nm^2 -> mm^2
    log('zone filled', zone_area)
    receipt['return_zone'] = dict(net=zn, layer=zl, rect_mm=[x0, y0, x1, y1], filled_area_mm2=zone_area)
    # 6. footprint attributes (board instances)
    attrs = []
    for f in board.GetFootprints():
        name = str(f.GetFPID().GetLibItemName())
        if name in FP_ATTR:
            want = k.FP_THROUGH_HOLE if FP_ATTR[name] == 'THT' else k.FP_SMD
            before = f.GetAttributes()
            f.SetAttributes((before & ~(k.FP_THROUGH_HOLE | k.FP_SMD)) | want)
            attrs.append(dict(ref=f.GetReference(), fp=name, before=int(before), after=int(f.GetAttributes())))
    receipt['footprint_attributes_set'] = attrs
    # courtyards for board-embedded footprints that have none (pad bounding box + margin)
    courtyards = []
    for f in board.GetFootprints():
        has = any(it.GetLayer() == k.F_CrtYd for it in f.GraphicalItems())
        if has:
            continue
        pads = list(f.Pads())
        if not pads:
            continue
        xs = [mm(p.GetPosition().x) for p in pads]; ys = [mm(p.GetPosition().y) for p in pads]
        hw = max(mm(p.GetSize().x) for p in pads) / 2 + COURTYARD_MARGIN_MM
        hh = max(mm(p.GetSize().y) for p in pads) / 2 + COURTYARD_MARGIN_MM
        x0, x1, y0, y1 = min(xs) - hw, max(xs) + hw, min(ys) - hh, max(ys) + hh
        layers = [k.F_CrtYd] + ([k.B_CrtYd] if any(mm(p.GetDrillSize().x) > 0 for p in pads) else [])
        for layer in layers:
            r = k.PCB_SHAPE(f)
            r.SetShape(k.SHAPE_T_RECT)
            r.SetStart(k.VECTOR2I(MM(x0), MM(y0)))
            r.SetEnd(k.VECTOR2I(MM(x1), MM(y1)))
            r.SetLayer(layer)
            r.SetWidth(MM(0.05))
            f.Add(r)
        courtyards.append(dict(ref=f.GetReference(), rect_mm=[x0, y0, x1, y1], layers=[board.GetLayerName(l) for l in layers]))
    receipt['courtyards_added'] = courtyards
    log('courtyards added', len(courtyards))
    log('attrs set', len(attrs))
    assert geometry(board) == fp_before, 'footprint/pad fingerprint changed'
    k.SaveBoard(str(board_path), board)
    log('board saved')
    # 6b. library footprints attributes
    lib_changes = []
    for lib in ['WP10_INPUT.pretty', 'WP10_TIMING.pretty']:
        for mod in sorted((E / lib).glob('*.kicad_mod')):
            if mod.stem in FP_ATTR:
                fp = k.FootprintLoad(str(E / lib), mod.stem)
                want = k.FP_THROUGH_HOLE if FP_ATTR[mod.stem] == 'THT' else k.FP_SMD
                fp.SetAttributes((fp.GetAttributes() & ~(k.FP_THROUGH_HOLE | k.FP_SMD)) | want)
                k.FootprintSave(str(E / lib), fp)
                lib_changes.append(dict(lib=lib, footprint=mod.stem, attr=FP_ATTR[mod.stem]))
    receipt['library_attributes_set'] = lib_changes
    log('library attrs', len(lib_changes))
    # 7. project DRC severities
    pro = E / 'wp10_main_input.kicad_pro'
    p = json.loads(pro.read_text(encoding='utf-8-sig'))
    sev = p['board']['design_settings']['rule_severities']
    for rule in ENABLE_RULES:
        sev[rule] = 'error'
    pro.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding='utf-8')
    receipt['drc_rules_enabled'] = ENABLE_RULES
    # 8. reload check
    check = k.LoadBoard(str(board_path))
    log('reloaded')
    assert geometry(check) == fp_before
    saved = board_path.read_text(encoding='utf-8')
    receipt['stackup_persisted'] = saved.count('(thickness 0.105)') == 2
    receipt['board_sha256'] = sha(board_path)
    receipt['tracks_now'] = sum(1 for t in check.GetTracks() if not isinstance(t, k.PCB_VIA))
    receipt['vias_now'] = sum(1 for t in check.GetTracks() if isinstance(t, k.PCB_VIA))
    receipt['zones_now'] = check.GetAreaCount()
    receipt['scope'] = 'EDA layout increment on the V32 parent; no schematic/net change; no fabrication/energization credit'
    (R / 'NATIVE_BUILD.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k_: v for k_, v in receipt.items() if k_ not in ('removed_tracks', 'copper_rects', 'footprint_attributes_set', 'library_attributes_set')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
