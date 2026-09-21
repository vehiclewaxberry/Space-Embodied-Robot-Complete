import sys, pcbnew as k
def log(*a): print(*a, flush=True)
MM=k.FromMM
b=k.LoadBoard('ecad/wp10_main_input.kicad_pcb'); log('loaded', len(b.GetTracks()))
n=b.FindNet('WP10_MAIN_FUSED'); log('net', n.GetNetname())
ts=[t for t in b.GetTracks() if not isinstance(t,k.PCB_VIA) and t.GetNetname()=='WP10_MAIN_FUSED' and abs(t.GetWidth()/1e6-3.0)<1e-3]
log('match', len(ts))
b.Remove(ts[0]); log('removed; tracks now', len(b.GetTracks()))
stage=sys.argv[1] if len(sys.argv)>1 else 'all'
if stage in ('rect','all'):
    s=k.PCB_SHAPE(b); s.SetShape(k.SHAPE_T_POLY); log('shape created')
    s.SetFilled(True); s.SetLayer(k.F_Cu); log('layer set')
    try:
        pts=[k.VECTOR2I(MM(23.1),MM(8)),k.VECTOR2I(MM(32.8),MM(8)),k.VECTOR2I(MM(32.8),MM(16)),k.VECTOR2I(MM(23.1),MM(16))]
        s.SetPolyPoints(pts); log('SetPolyPoints(list) ok')
    except Exception as e:
        log('SetPolyPoints(list) failed', repr(e))
        poly=k.SHAPE_POLY_SET(); poly.NewOutline()
        for x,y in [(23.1,8),(32.8,8),(32.8,16),(23.1,16)]: poly.Append(MM(x),MM(y))
        s.SetPolyShape(poly); log('SetPolyShape ok')
    s.SetNet(n); log('net set'); s.SetWidth(0); log('width set'); b.Add(s); log('rect added')
if stage in ('via','all'):
    v=k.PCB_VIA(b); v.SetViaType(k.VIATYPE_THROUGH); log('via type'); v.SetLayerPair(k.F_Cu,k.B_Cu); log('layer pair')
    v.SetPosition(k.VECTOR2I(MM(24.2),MM(16.2))); log('pos'); v.SetDrill(MM(0.6)); log('drill')
    try: v.SetWidth(MM(1.0)); log('SetWidth(int) ok')
    except Exception as e:
        log('SetWidth(int) failed',repr(e)); v.SetWidth(k.F_Cu,MM(1.0)); log('SetWidth(layer,int) ok')
    v.SetNet(n); b.Add(v); log('via added')
if stage in ('zone','all'):
    z=k.ZONE(b); z.SetLayer(k.B_Cu); z.SetNet(b.FindNet('WP10_INPUT_RETURN')); log('zone basic')
    z.SetZoneName('CF1_TEST'); z.Outline().NewOutline()
    for x,y in [(18,3),(82,3),(82,14),(18,14)]: z.Outline().Append(MM(x),MM(y))
    log('outline'); z.SetMinThickness(MM(0.25)); log('minthick')
    try: z.SetLocalClearance(MM(0.3)); log('local clearance ok')
    except Exception as e: log('SetLocalClearance failed',repr(e))
    z.SetPadConnection(k.ZONE_CONNECTION_FULL); log('padconn'); b.Add(z); log('zone added')
    f=k.ZONE_FILLER(b); log('filler'); f.Fill(b.Zones()); log('filled area mm2', z.GetFilledArea()/1e6)
if stage in ('attr','all'):
    for fp in b.GetFootprints():
        if fp.GetReference()=='Q201':
            a=fp.GetAttributes(); fp.SetAttributes((a & ~(k.FP_THROUGH_HOLE|k.FP_SMD))|k.FP_THROUGH_HOLE); log('attr',a,fp.GetAttributes())
k.SaveBoard('logs/_probe_out.kicad_pcb', b); log('saved')
