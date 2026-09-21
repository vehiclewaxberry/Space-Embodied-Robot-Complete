"""Bounded native routing preparation and SES import; no hardware writes."""
from pathlib import Path
import sys,json,subprocess
import pcbnew as k
from build_aux_v34 import mm,layers
A=Path(__file__).resolve().parents[1];D=A/'ecad/revisions/v34';R=A/'results/aux_v34'
P=D/'wp10_aux_protection.kicad_pcb'
def main():
    b=k.LoadBoard(str(P))
    if '--import' in sys.argv:
        assert k.ImportSpecctraSES(b,str(R/'aux_routed.ses'))
        k.SaveBoard(str(P),b);print('Imported routed SES');return
    fps={f.GetReference():f for f in b.GetFootprints()}
    nets={n.GetNetname():n for n in b.GetNetsByName().values()}
    def point(ref,n):
        p=next(p for p in fps[ref].Pads() if p.GetNumber()==str(n));return (k.ToMM(p.GetPosition().x),k.ToMM(p.GetPosition().y))
    def track(net,pts,w,layer=k.F_Cu):
        for a,z in zip(pts,pts[1:]):
            if a==z:continue
            t=k.PCB_TRACK(b);t.SetStart(mm(*a));t.SetEnd(mm(*z));t.SetWidth(k.FromMM(w));t.SetLayer(layer);t.SetNet(nets[net]);b.Add(t)
    # Replace provisional power trunks with exact-pad routes; retain pin necks and thermal vias.
    assert not any(t.GetWidth()>=k.FromMM(1) for t in b.GetTracks() if not isinstance(t,k.PCB_VIA)), 'Start from the unrouted builder source'
    track('WP10_AUX_FUSED',[point('J208',1),(8,5.85),point('D207',2)],2)
    track('WP10_AUX_FUSED',[point('D207',2),(19.5,5.85),(19.5,19.175),point('C214',1),(25.2,19.175),(25.2,17.725)],1.5)
    track('WP10_AUX_LIMITED',[(34.5,17.725),(34.5,18.375),point('C215',1)],1.2)
    track('WP10_AUX_LIMITED',[point('C215',1),(40.8,18.275),(40.8,5.89),point('D208',1),(52,5.89),point('J209',1)],1.5)
    # Broad ground backbone, independent of the RTN heat-spreading island.
    track('WP10_INPUT_RETURN',[point('J208',2),(5,8),(55,8),point('J209',2)],2,k.B_Cu)
    for ref,pn in [('D207',1),('D208',2),('C214',2),('C215',2),('U207',9)]:
        a=point(ref,pn)
        if ref=='U207':a=(33.8,22.275)
        if ref in ['D207','D208']:
            v=k.PCB_VIA(b);v.SetPosition(mm(*a));v.SetWidth(k.FromMM(.8));v.SetDrill(k.FromMM(.4));v.SetViaType(k.VIATYPE_THROUGH);v.SetLayerPair(k.F_Cu,k.B_Cu);v.SetNet(nets['WP10_INPUT_RETURN']);b.Add(v)
        # Leave local chip return for the signal router to avoid cutting through RTN vias.
        if ref!='U207':track('WP10_INPUT_RETURN',[a,(a[0],8)],1.5,k.B_Cu)
    # Compact thermal island connects the EP vias and supports. Copper zones added after routing.
    for x in [28.9,30,31.1]:track('WP10_AUX_PROTECT_RTN',[(x,18.9),(x,21.1)],.7,k.B_Cu)
    track('WP10_AUX_PROTECT_RTN',[(28.9,20),(31.1,20)],.7,k.B_Cu)
    k.SaveBoard(str(P),b)
    # Project rule values rather than modifying the user's global EDA preferences.
    pro={'board':{'design_settings':{'rules':{'min_clearance':.15,'min_track_width':.15,'min_via_diameter':.6,'min_through_hole_diameter':.3}}},
         'net_settings':{'classes':[{'name':'Default','clearance':.15,'track_width':.25,'via_diameter':.6,'via_drill':.3,'microvia_diameter':.3,'microvia_drill':.1,'diff_pair_width':.25,'diff_pair_gap':.2,'diff_pair_via_gap':.25}]}}
    P.with_suffix('.kicad_pro').write_text(json.dumps(pro,indent=2)+'\n')
    # Reload settings for export.
    b=k.LoadBoard(str(P));assert k.ExportSpecctraDSN(b,str(R/'aux.dsn'))
    print('Power traces and paired pin necks retained; signal DSN exported')
if __name__=='__main__':main()
