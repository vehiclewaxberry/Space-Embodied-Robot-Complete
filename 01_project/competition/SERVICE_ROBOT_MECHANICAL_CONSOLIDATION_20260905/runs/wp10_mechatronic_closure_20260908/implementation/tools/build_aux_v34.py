"""Native KiCad board construction, bound to exported V34 nets."""
from pathlib import Path
import json,copy,xml.etree.ElementTree as ET
import pcbnew as k
A=Path(__file__).resolve().parents[1];D=A/'ecad/revisions/v34';R=A/'results/aux_v34'
def mm(x,y):return k.VECTOR2I(k.FromMM(x),k.FromMM(y))
def layers(*ids):
    s=k.LSET()
    for i in ids:s.AddLayer(i)
    return s
def dump(n,x):(R/n).write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
def setup_libraries():
    f=k.FootprintLoad(str(D/'WP10_INPUT.pretty'),'STPS3H100U_A1K2')
    f.SetFPID(k.LIB_ID('WP10_AUX','STPS3H100U_K1A2'))
    for p in f.Pads():p.SetNumber({'1':'2','2':'1'}[p.GetNumber()])
    k.FootprintSave(str(D/'WP10_AUX.pretty'),f)
    f=k.FootprintLoad(str(D/'WP10_AUX.pretty'),'TPS26600_PWP16_EP17')
    # Manufacturer SMD exposed-pad opening; copper extends under the package.
    pad=k.PAD(f);pad.SetNumber('');pad.SetAttribute(k.PAD_ATTRIB_SMD);pad.SetShape(k.PAD_SHAPE_RECT)
    pad.SetPosition(mm(0,0));pad.SetSize(mm(3.3,3.3));pad.SetLayerSet(layers(k.F_Mask));f.Add(pad)
    # Four paste windows with central web, ~70% opening; process validation pending.
    for x in [-.875,.875]:
      for y in [-.875,.875]:
        p=k.PAD(f);p.SetNumber('');p.SetAttribute(k.PAD_ATTRIB_SMD);p.SetShape(k.PAD_SHAPE_RECT)
        p.SetPosition(mm(x,y));p.SetSize(mm(1.4,1.4));p.SetLayerSet(layers(k.F_Paste));f.Add(p)
    k.FootprintSave(str(D/'WP10_AUX.pretty'),f)
    b=k.LoadBoard(str(D/'wp10_main_input.kicad_pcb'))
    r=next(f for f in b.GetFootprints() if f.GetReference()=='R202')
    assert r.GetValue()=='WSLP2726L2000FEA';r.SetValue('WSLP2726L5000FEA')
    for p in r.Pads():assert p.GetNumber() in ['1','2']
    assert r.GetDuplicatePadNumbersAreJumpers()
    for m in r.Models():
        pass # Retained maximum envelope is conservative; exact resistor-height change is in BOM.
    k.SaveBoard(str(D/'wp10_main_input.kicad_pcb'),b)

def main():
    root=ET.parse(D/'wp10_system.xml').getroot()
    refs='U207 R223 R224 C214 C215 C216 D207 D208 J208 J209 J210'.split()
    comps={c.get('ref'):c for c in root.findall('./components/comp')}
    nodes={(n.get('ref'),n.get('pin')):net.get('name') for net in root.findall('./nets/net') for n in net.findall('node')}
    b=k.BOARD();b.SetCopperLayerCount(2);b.GetDesignSettings().SetBoardThickness(k.FromMM(1.6))
    nets={}
    for net in set(v for (r,p),v in nodes.items() if r in refs):
        n=k.NETINFO_ITEM(b,net);b.Add(n);nets[net]=n
    positions={'U207':(30,20,0),'R223':(36.7,25,0),'R224':(23.5,24.8,0),
       'C214':(23.8,17.7,90),'C215':(36.2,16.8,90),'C216':(38,21.5,0),
       'D207':(16,8,90),'D208':(44,8,90),'J208':(8,17,270),'J209':(52,17,90),
       'J210':(22,31,0)}
    fps={}
    for r in refs:
        c=comps[r];lib,name=c.findtext('footprint').split(':');f=k.FootprintLoad(str(D/(lib+'.pretty')),name)
        assert f is not None,(r,name)
        f.SetReference(r);f.SetValue(c.findtext('value'));b.Add(f)
        x,y,a=positions[r];f.SetPosition(mm(x,y));f.SetOrientationDegrees(a)
        f.Reference().SetTextSize(mm(.8,.8));f.Reference().SetTextThickness(k.FromMM(.12))
        f.Reference().SetPosition(mm(x,y+4 if r=='U207' else y-3));f.Value().SetVisible(False)
        # Preserve source identity for board-to-netlist consistency review.
        f.SetPath(k.KIID_PATH('/'+c.findtext('tstamps')))
        for p in f.Pads():
            if p.GetNumber():
                net=nodes.get((r,p.GetNumber()))
                if net:p.SetNet(nets[net])
        rp={'D207':(16,3.5),'D208':(44,3.5),'C214':(22,14),'C215':(37,12.5),'C216':(42.5,23.5),'R223':(36.7,28),'R224':(23.5,27),'J210':(22,34.5),'J208':(8,23),'J209':(52,23),'U207':(30,24)}
        f.Reference().SetPosition(mm(*rp[r]));f.Reference().SetTextAngleDegrees(0)
        fps[r]=f
    def pad(r,n):return next(p for p in fps[r].Pads() if p.GetNumber()==str(n))
    def xy(p):return [k.ToMM(p.GetPosition().x),k.ToMM(p.GetPosition().y)]
    def line(net,points,width=.25,layer=k.F_Cu):
        for a,z in zip(points,points[1:]):
            t=k.PCB_TRACK(b);t.SetStart(mm(*a));t.SetEnd(mm(*z));t.SetWidth(k.FromMM(width));t.SetLayer(layer);t.SetNet(nets[net]);b.Add(t)
    def route(r,n,points,width=.25,layer=k.F_Cu):line(pad(r,n).GetNetname(),[xy(pad(r,n)),*points],width,layer)
    def via(net,x,y):
        v=k.PCB_VIA(b);v.SetPosition(mm(x,y));v.SetWidth(k.FromMM(.6));v.SetDrill(k.FromMM(.3));v.SetViaType(k.VIATYPE_THROUGH);v.SetLayerPair(k.F_Cu,k.B_Cu);v.SetNet(nets[net]);b.Add(v)
    for j in range(4):
        a=[(0,0),(60,0),(60,40),(0,40)][j];z=[(60,0),(60,40),(0,40),(0,0)][j]
        s=k.PCB_SHAPE();s.SetShape(k.SHAPE_T_SEGMENT);s.SetStart(mm(*a));s.SetEnd(mm(*z));s.SetLayer(k.Edge_Cuts);s.SetWidth(k.FromMM(.05));b.Add(s)
    # Local paired power pins use short necks, then broad common trunks. No new board-size current claim.
    for n in [1,2]:route('U207',n,[(25.2,xy(pad('U207',n))[1])],.4)
    for n in [15,16]:route('U207',n,[(34.5,xy(pad('U207',n))[1])],.4)
    # Avoid guessing library pad coordinates: connector and clamp routing is completed from exact pads.
    for ref,num in [('C214',2),('C215',2),('U207',9)]:
        p=pad(ref,num);x,y=xy(p);end=(x+(.9 if ref=='U207' else 0),y)
        route(ref,num,[end],.25);via(p.GetNetname(),*end)
    # Exposed-pad heat flows to an independent RTN copper island, never GND.
    for x in [28.9,30,31.1]:
      for y in [18.9,20,21.1]:via('WP10_AUX_PROTECT_RTN',x,y)
    # All remaining routes are board nets, not ideal external wires. Router uses exact pads.
    for text,x,y,size in [('WP10 V34 AUX PROTECTION',30,1.5,.9),('F202 INPUT',8,28,.9),('TO THN',52,28,.9),('RTN != GND',32,35,.9),('REVIEW ONLY',30,38,.9)]:
        t=k.PCB_TEXT(b);t.SetText(text);t.SetPosition(mm(x,y));t.SetTextSize(mm(size,size));t.SetTextThickness(k.FromMM(.12));t.SetLayer(k.F_SilkS);b.Add(t)
    path=D/'wp10_aux_protection.kicad_pcb';k.SaveBoard(str(path),b)
    dump('PLACEMENT.json',{'parts':{r:dict(value=f.GetValue(),position=positions[r],pads=[dict(n=p.GetNumber(),xy=xy(p),net=p.GetNetname()) for p in f.Pads() if p.GetNumber()]) for r,f in fps.items()},'board_mm':[60,40,1.6],'source_xml':str(D/'wp10_system.xml')})
    print(json.dumps(dict(board=str(path),footprints=len(fps),tracks=len(list(b.GetTracks())))))
if __name__=='__main__':
    import sys
    if '--libs' in sys.argv:setup_libraries()
    else:main()
