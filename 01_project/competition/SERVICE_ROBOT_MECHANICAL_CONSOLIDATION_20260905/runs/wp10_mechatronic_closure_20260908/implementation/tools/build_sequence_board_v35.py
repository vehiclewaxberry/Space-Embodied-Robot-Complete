"""Extend the existing routed V34 auxiliary board; do not regenerate power traces."""
from pathlib import Path
import json,xml.etree.ElementTree as ET,sys
import pcbnew as k
from build_aux_v34 import mm,layers
A=Path(__file__).resolve().parents[1];D=A/'ecad/revisions/v35';R=A/'results/aux_v35';P=D/'wp10_aux_protection.kicad_pcb'
def main():
    b=k.LoadBoard(str(P))
    if '--import' in sys.argv:
        assert k.ImportSpecctraSES(b,str(R/'aux_routed_headless.ses'))
        cs={c.get('ref'):c for c in ET.parse(D/'wp10_system.xml').getroot().findall('./components/comp')}
        for f in b.GetFootprints():
            if f.GetReference() in cs:f.SetValue(cs[f.GetReference()].findtext('value'))
        k.SaveBoard(str(P),b);print('Imported V35 signal routes and refreshed all values from active XML');return
    assert len([f for f in b.GetFootprints() if not f.GetAttributes()&k.FP_BOARD_ONLY])==11
    # TI DYY0014A land pattern: 14 pads1.05x.3, two rows3mm apart, pitch.5mm.
    f=k.FOOTPRINT(None);f.SetFPID(k.LIB_ID('WP10_AUX','TPS3760_DYY14'));f.SetAttributes(k.FP_SMD)
    for i in range(1,15):
        p=k.PAD(f);p.SetNumber(str(i));p.SetAttribute(k.PAD_ATTRIB_SMD);p.SetShape(k.PAD_SHAPE_ROUNDRECT);p.SetRoundRectRadiusRatio(.16)
        p.SetPosition(mm(-1.5 if i<=7 else 1.5,-1.5+(i-1)*.5 if i<=7 else 1.5-(i-8)*.5));p.SetSize(mm(1.05,.3));p.SetLayerSet(layers(k.F_Cu,k.F_Mask,k.F_Paste));f.Add(p)
    def rect(fp,x1,y1,x2,y2,layer):
        s=k.PCB_SHAPE(fp);s.SetShape(k.SHAPE_T_RECT);s.SetStart(mm(x1,y1));s.SetEnd(mm(x2,y2));s.SetLayer(layer);s.SetWidth(k.FromMM(.1 if layer!=k.F_CrtYd else .05));fp.Add(s)
    rect(f,-.95,-2.05,.95,2.05,k.F_Fab);rect(f,-2.3,-2.3,2.3,2.3,k.F_CrtYd)
    rect(f,-.9,-2.2,.9,-1.95,k.F_SilkS);k.FootprintSave(str(D/'WP10_AUX.pretty'),f)
    rt=ET.parse(D/'wp10_system.xml').getroot();cs={c.get('ref'):c for c in rt.findall('./components/comp')}
    pn={(n.get('ref'),n.get('pin')):net.get('name') for net in rt.findall('./nets/net') for n in net.findall('node')}
    selected=json.loads((R/'SELECTED_PARTS.json').read_text());nets={n.GetNetname():n for n in b.GetNetsByName().values()}
    for name in sorted({v for (ref,n),v in pn.items() if ref in selected}-set(nets)):
        item=k.NETINFO_ITEM(b,name);b.Add(item);nets[name]=item
    pos={'U208':(11,49,0),'R225':(17,45.5,0),'R226':(17,49,0),'C217':(7,43,0),'C218':(17,54,0),
         'U209':(38,49,0),'R227':(24,50,0),'R229':(43,43,0),'R230':(43,46,0),'R231':(25,61,0),
         'C219':(28,43,0),'C220':(34,59,0),'J211':(52,53,90),'D209':(9,60,0),'D210':(17,60,0)}
    for ref in selected:
        c=cs[ref];lib,name=c.findtext('footprint').split(':');f=k.FootprintLoad(str(D/(lib+'.pretty')),name);assert f is not None,(ref,lib,name)
        f.SetFPID(k.LIB_ID(lib,name));f.SetReference(ref);f.SetValue(c.findtext('value'));b.Add(f)
        x,y,ang=pos[ref];f.SetPosition(mm(x,y));f.SetOrientationDegrees(ang)
        f.SetPath(k.KIID_PATH(c.find('sheetpath').get('tstamps').rstrip('/')+'/'+c.findtext('tstamps')))
        for p in f.Pads():
            if p.GetNumber():p.SetNet(nets[pn[ref,p.GetNumber()]])
        f.Reference().SetTextSize(mm(.8,.8));f.Reference().SetTextThickness(k.FromMM(.12));f.Reference().SetTextAngleDegrees(0);f.Reference().SetPosition(mm(x,y-3));f.Value().SetVisible(False)
        if ref in ['C219','C220']:f.Reference().SetPosition(mm(x+2.5,y+6.5))
        if ref in ['R225','R226','R229','R230']:f.Reference().SetPosition(mm(x+4,y))
        if ref=='J211':f.Reference().SetPosition(mm(52,58))
    # Retain four parent mounting holes; add two at the new lower edge.
    for i,(x,y) in enumerate([(3.5,66.5),(56.5,66.5)],1):
        f=k.FootprintLoad(str(D/'MountingHole.pretty'),'MountingHole_2.7mm_M2.5');f.SetReference('MH35_'+str(i));f.SetAttributes(f.GetAttributes()|k.FP_BOARD_ONLY);b.Add(f);f.SetPosition(mm(x,y));f.Reference().SetVisible(False);f.Value().SetVisible(False)
        for layer in [k.F_Cu,k.B_Cu]:
            z=k.ZONE(b);z.SetLayer(layer);z.SetIsRuleArea(True);z.SetDoNotAllowZoneFills(True);z.SetDoNotAllowTracks(True);z.SetDoNotAllowVias(True);z.SetDoNotAllowPads(False);z.SetDoNotAllowFootprints(False)
            o=z.Outline();o.NewOutline()
            for dx,dy in [(-3,-3),(3,-3),(3,3),(-3,3)]:o.Append(k.FromMM(x+dx),k.FromMM(y+dy))
            b.Add(z)
    for s in b.GetDrawings():
        if isinstance(s,k.PCB_SHAPE) and s.GetLayer()==k.Edge_Cuts:
            for getter,setter in [(s.GetStart,s.SetStart),(s.GetEnd,s.SetEnd)]:
                p=getter()
                if abs(k.ToMM(p.y)-40)<1e-5:setter(mm(k.ToMM(p.x),70))
        elif isinstance(s,k.PCB_TEXT) and 'V34' in s.GetText():s.SetText(s.GetText().replace('V34','V35'))
    z=k.ZONE(b);z.SetLayer(k.B_Cu);z.SetNet(nets['WP10_INPUT_RETURN']);z.SetAssignedPriority(2);z.SetLocalClearance(k.FromMM(.5));z.SetMinThickness(k.FromMM(.25));z.SetPadConnection(k.ZONE_CONNECTION_FULL)
    o=z.Outline();o.NewOutline()
    for x,y in [(.6,38.8),(59.4,38.8),(59.4,69.4),(.6,69.4)]:o.Append(k.FromMM(x),k.FromMM(y))
    b.Add(z)
    fps={f.GetReference():f for f in b.GetFootprints()}
    def point(ref,n):
        p=next(p for p in fps[ref].Pads() if p.GetNumber()==str(n));return k.ToMM(p.GetPosition().x),k.ToMM(p.GetPosition().y)
    def tr(net,pts,width=.25,layer=k.F_Cu):
        for a,z in zip(pts,pts[1:]):
            if a==z:continue
            t=k.PCB_TRACK(b);t.SetStart(mm(*a));t.SetEnd(mm(*z));t.SetWidth(k.FromMM(width));t.SetLayer(layer);t.SetNet(nets[net]);b.Add(t)
    # New bias load branches after protection; no changed current-limiting resistor or safety bypass.
    # New low-current bias branch is routed around the retained mounting keepouts by DSN router.
    # Thermal pad belongs to primary GND, unlike U207 isolated internal RTN.
    for dx,dy in [(-.5,-.9),(.5,-.9),(-.5,.9),(.5,.9)]:
        v=k.PCB_VIA(b);v.SetPosition(mm(38+dx,49+dy));v.SetWidth(k.FromMM(.6));v.SetDrill(k.FromMM(.3));v.SetViaType(k.VIATYPE_THROUGH);v.SetLayerPair(k.F_Cu,k.B_Cu);v.SetNet(nets['WP10_INPUT_RETURN']);b.Add(v)
    k.SaveBoard(str(P),b);assert k.ExportSpecctraDSN(b,str(R/'aux.dsn'))
    (R/'PCB_GEOMETRY.json').write_text(json.dumps(dict(board_mm=[60,70,1.6],electrical_footprints=26,board_only_holes=6,parent_power_routes_retained_before_router=True,whole_host_placement=None,new_max_component_nominal_height_mm=18,geometry_is_not_installed_CAD=True,positions=pos),indent=2)+'\n')
    print('V35 60x70mm,26 electrical footprints; old power routing retained; new signal DSN exported')
if __name__=='__main__':main()
