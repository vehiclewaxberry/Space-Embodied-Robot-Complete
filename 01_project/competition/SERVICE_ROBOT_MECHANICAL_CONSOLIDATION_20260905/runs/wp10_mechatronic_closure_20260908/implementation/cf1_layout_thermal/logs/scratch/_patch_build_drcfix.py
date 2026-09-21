"""One-off patch of build_pcb_cf1.py / current_density_cf1.py after the first DRC run (kept for traceability)."""
from pathlib import Path
HERE = Path(__file__).resolve().parent
# ---- current density script: KiCad 10 python has no PCB_SHAPE.IsFilled()
p = HERE / 'current_density_cf1.py'; t = p.read_text(encoding='utf-8')
t = t.replace("dr.GetShape() == k.SHAPE_T_POLY and dr.IsFilled() and", "dr.GetShape() == k.SHAPE_T_POLY and dr.GetNetname() and")
p.write_text(t, encoding='utf-8')
# ---- build script tables
p = HERE / 'build_pcb_cf1.py'; t = p.read_text(encoding='utf-8')
old = "    ('WP10_PRECHARGED_PLUS', 'F.Cu', (90.0, 17.0), (93.0, 15.0), 6.0),\n]\n"
new = ("    ('WP10_PRECHARGED_PLUS', 'F.Cu', (90.0, 17.0), (93.0, 15.0), 6.0),\n"
       "    # feeders re-routed so via arrays do not sit on narrow tracks (DRC track_not_centered_on_via)\n"
       "    ('WP10_MAIN_FUSED', 'F.Cu', (24.675, 15.0), (27.0, 18.5), 0.8),\n"
       "    ('WP10_MAIN_FUSED', 'F.Cu', (27.0, 18.5), (28.0, 24.0), 0.8),\n"
       "    ('WP10_PRECHARGED_PLUS', 'F.Cu', (69.0, 17.0), (70.0, 23.0), 0.8),\n"
       "    ('WP10_PRECHARGED_PLUS', 'F.Cu', (70.0, 23.0), (70.0, 33.0), 0.8),\n"
       "    ('WP10_PRECHARGED_PLUS', 'F.Cu', (70.0, 33.0), (74.0, 33.0), 0.8),\n"
       "    ('WP10_PRECHARGED_PLUS', 'F.Cu', (74.0, 33.0), (74.0, 39.0), 0.8),\n"
       "]\n"
       "ADD_TRACKS = [  # (net, layer, start, end, width) replacement feeders\n"
       "    ('WP10_MAIN_FUSED', 'F.Cu', (24.5, 25.0), (27.0, 25.0), 1.5),      # D201 feeder -> C202 pad1\n"
       "    ('WP10_MAIN_FUSED', 'F.Cu', (27.0, 25.0), (28.0, 24.0), 1.5),\n"
       "    ('WP10_PRECHARGED_PLUS', 'F.Cu', (74.0, 16.0), (74.0, 39.0), 0.8),  # band -> C211 pad1\n"
       "    ('WP10_PRECHARGED_PLUS', 'F.Cu', (84.11, 17.0), (84.11, 14.0), 1.5),  # D202 pad2 feeder into the band\n"
       "]\n")
assert old in t; t = t.replace(old, new, 1)
old = ("    ('WP10_MAIN_FUSED', 'B.Cu', (23.6, 15.0, 30.2, 22.0), 'PARALLEL_BCU'),\n"
       "    ('WP10_PRECHARGED_PLUS', 'B.Cu', (67.5, 15.0, 77.6, 22.0), 'PARALLEL_BCU'),\n"
       "]\n"
       "VIA_ROWS = [16.2, 17.4, 18.6, 19.8, 21.0]\n"
       "VIA_ARRAYS = [  # net, x columns\n"
       "    ('WP10_MAIN_FUSED', [24.2, 25.4, 28.4, 29.6]),\n"
       "    ('WP10_PRECHARGED_PLUS', [68.0, 69.2, 75.9, 77.1]),\n"
       "]\n")
new = ("    ('WP10_PRECHARGED_PLUS', 'B.Cu', (68.7, 15.0, 77.6, 22.0), 'PARALLEL_BCU'),\n"
       "    ('WP10_PRECHARGED_PLUS', 'F.Cu', (68.8, 16.0, 71.0, 21.5), 'VIA_LANDING_FCU'),\n"
       "    ('WP10_PRECHARGED_PLUS', 'F.Cu', (75.4, 16.0, 77.6, 21.5), 'VIA_LANDING_FCU'),\n"
       "]\n"
       "# MAIN_FUSED B.Cu parallel copper dropped: F.Cu feeders (D201 TVS, C202 timing, LM5069 sense) and the\n"
       "# Kelvin sense lands occupy x 23-33 / y 16-22; via arrays there would land on narrow tracks or sense pads.\n"
       "VIA_ROWS = [16.2, 17.4, 18.6, 19.8, 21.0]\n"
       "VIA_ARRAYS = [  # net, x columns\n"
       "    ('WP10_PRECHARGED_PLUS', [69.3, 70.5, 75.9, 77.1]),\n"
       "]\n"
       "COURTYARD_MARGIN_MM = 0.25   # for board-embedded footprints without F.CrtYd (MH1-4, PORT_*)\n")
assert old in t; t = t.replace(old, new, 1)
old = "    KEEP_ALIVE.extend(to_remove)\n    board.BuildConnectivity()\n"
new = ("    KEEP_ALIVE.extend(to_remove)\n    board.BuildConnectivity()\n"
       "    added_tracks = []\n"
       "    for net_name, layer, s, e, w in ADD_TRACKS:\n"
       "        tr = k.PCB_TRACK(board)\n"
       "        tr.SetLayer(board.GetLayerID(layer))\n"
       "        tr.SetStart(k.VECTOR2I(MM(s[0]), MM(s[1])))\n"
       "        tr.SetEnd(k.VECTOR2I(MM(e[0]), MM(e[1])))\n"
       "        tr.SetWidth(MM(w))\n"
       "        tr.SetNet(nets[net_name])\n"
       "        board.Add(tr)\n"
       "        added_tracks.append(dict(net=net_name, layer=layer, start=s, end=e, width_mm=w))\n"
       "    receipt['added_tracks'] = added_tracks\n"
       "    log('feeder tracks added', len(added_tracks))\n")
assert old in t; t = t.replace(old, new, 1)
old = "    receipt['footprint_attributes_set'] = attrs\n"
new = ("    receipt['footprint_attributes_set'] = attrs\n"
       "    # courtyards for board-embedded footprints that have none (pad bounding box + margin)\n"
       "    courtyards = []\n"
       "    for f in board.GetFootprints():\n"
       "        has = any(it.GetLayer() == k.F_CrtYd for it in f.GraphicalItems())\n"
       "        if has:\n"
       "            continue\n"
       "        pads = list(f.Pads())\n"
       "        if not pads:\n"
       "            continue\n"
       "        xs = [mm(p.GetPosition().x) for p in pads]; ys = [mm(p.GetPosition().y) for p in pads]\n"
       "        hw = max(mm(p.GetSize().x) for p in pads) / 2 + COURTYARD_MARGIN_MM\n"
       "        hh = max(mm(p.GetSize().y) for p in pads) / 2 + COURTYARD_MARGIN_MM\n"
       "        x0, x1, y0, y1 = min(xs) - hw, max(xs) + hw, min(ys) - hh, max(ys) + hh\n"
       "        layers = [k.F_CrtYd] + ([k.B_CrtYd] if any(mm(p.GetDrillSize().x) > 0 for p in pads) else [])\n"
       "        for layer in layers:\n"
       "            r = k.PCB_SHAPE(f)\n"
       "            r.SetShape(k.SHAPE_T_RECT)\n"
       "            r.SetStart(k.VECTOR2I(MM(x0), MM(y0)))\n"
       "            r.SetEnd(k.VECTOR2I(MM(x1), MM(y1)))\n"
       "            r.SetLayer(layer)\n"
       "            r.SetWidth(MM(0.05))\n"
       "            f.Add(r)\n"
       "        courtyards.append(dict(ref=f.GetReference(), rect_mm=[x0, y0, x1, y1], layers=[board.GetLayerName(l) for l in layers]))\n"
       "    receipt['courtyards_added'] = courtyards\n"
       "    log('courtyards added', len(courtyards))\n")
assert old in t; t = t.replace(old, new, 1)
p.write_text(t, encoding='utf-8')
print('patched build_pcb_cf1.py and current_density_cf1.py')
