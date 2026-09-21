"""Place real STOP/control/thermal footprints from the fresh249-ref native netlist.

Fixed functional anchors plus conservative courtyard-aware passive placement.
Not a manufacturing or installed-host acceptance. Routing is a separate step.
"""
from pathlib import Path
import hashlib,json,math,shutil,xml.etree.ElementTree as ET
import pcbnew as k
A=Path(__file__).resolve().parents[1];D=A/'ecad/revisions/v36';P=A/'results/stop_v36/pcb';N=P/'thermal_filter_20260916/native_20260916_a';R=P/'layout_20260916'
def mm(x,y):return k.VECTOR2I(k.FromMM(x),k.FromMM(y))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def bbox(f):
    rects=[g.GetBoundingBox() for g in f.GraphicalItems() if g.GetLayer()==k.F_CrtYd]
    if not rects:rects=[f.GetBoundingBox(False,False)]
    return (min(k.ToMM(x.GetX()) for x in rects),min(k.ToMM(x.GetY()) for x in rects),max(k.ToMM(x.GetRight()) for x in rects),max(k.ToMM(x.GetBottom()) for x in rects))
def overlap(a,b,margin=.25):return a[0]<b[2]+margin and b[0]<a[2]+margin and a[1]<b[3]+margin and b[1]<a[3]+margin
def inside(q):return q[0]>=.25 and q[1]>=.25 and q[2]<=89.75 and q[3]<=69.75
def main():
    target=D/'wp10_stop_control.kicad_pcb'
    assert not target.exists(),'Keep any existing board; do not blindly overwrite placement/routing'
    check=json.loads((N/'VERIFICATION.json').read_text());assert check['scoped_pass']
    assert all(sha(p)==h for p,h in check['source_bindings'].items())
    parts=json.loads((P/'PHYSICAL_PARTS.json').read_text());assert len(parts)==103
    rt=ET.parse(N/'wp10_system.xml').getroot();cs={c.get('ref'):c for c in rt.findall('./components/comp')}
    pn={(n.get('ref'),n.get('pin')):net.get('name') for net in rt.findall('./nets/net') for n in net.findall('node')}
    b=k.BOARD();b.SetCopperLayerCount(2);b.GetDesignSettings().SetBoardThickness(k.FromMM(1.6))
    nets={}
    for name in sorted({n for (r,p),n in pn.items() if r in parts}):
        ni=k.NETINFO_ITEM(b,name);b.Add(ni);nets[name]=ni
    io=k.PCB_IO_KICAD_SEXPR();fps={};mechanical_pads=[]
    for ref,p in parts.items():
        lib,name=p['footprint'].split(':');f=io.FootprintLoad(str(D/(lib+'.pretty')),name);assert f is not None
        f.SetFPID(k.LIB_ID(lib,name));f.SetReference(ref);f.SetValue(cs[ref].findtext('value'));b.Add(f)
        f.SetPath(k.KIID_PATH(cs[ref].find('sheetpath').get('tstamps').rstrip('/')+'/'+cs[ref].findtext('tstamps')))
        for pad in f.Pads():
            number=pad.GetNumber()
            if number=='':continue
            if ref=='J106' and number=='MP':
                mechanical_pads.append(dict(ref=ref,pad=number,reason='OEM solder retention tabs; no electrical contact in6pin symbol'));continue
            assert (ref,number) in pn,(ref,number)
            pad.SetNet(nets[pn[ref,number]])
        f.Reference().SetTextSize(mm(.65,.65));f.Reference().SetTextThickness(k.FromMM(.1));f.Value().SetVisible(False)
        fps[ref]=f
    occupied={};positions={}
    def place(ref,x,y,angle=0,align=None):
        f=fps[ref];f.SetPosition(mm(x,y));f.SetOrientationDegrees(angle)
        q=bbox(f)
        if align=='bottom':
            x+=x-(q[0]+q[2])/2;y+=69.5-q[3];f.SetPosition(mm(x,y));q=bbox(f)
        elif align=='left':
            x+=.5-q[0];y+=y-(q[1]+q[3])/2;f.SetPosition(mm(x,y));q=bbox(f)
        assert inside(q),(ref,'board edge',q)
        hits=[r for r,v in occupied.items() if overlap(q,v)]
        assert not hits,(ref,'courtyard overlap',hits,q)
        occupied[ref]=q;positions[ref]=[x,y,angle]
        f.Reference().SetPosition(mm(x,y-2.6));f.Reference().SetTextAngleDegrees(0)
    # Four board-only mounting holes are real PCB features; host position remains unaccepted.
    name='MountingHole_2.7mm_M2.5';folder=D/'MountingHole.pretty';folder.mkdir(exist_ok=True)
    source=Path('G:/Windows_program_file/Kicad/share/kicad/footprints/MountingHole.pretty')/(name+'.kicad_mod')
    shutil.copy2(source,folder/source.name)
    for i,(x,y) in enumerate([(3.5,3.5),(86.5,3.5),(3.5,66.5),(86.5,66.5)],1):
        ref='HSTOP'+str(i);f=io.FootprintLoad(str(folder),name);f.SetReference(ref);f.SetValue('M2.5');f.SetAttributes(f.GetAttributes()|k.FP_BOARD_ONLY);b.Add(f);fps[ref]=f;place(ref,x,y);f.Reference().SetVisible(False)
    for ref,x in [('J101',13),('J102',35),('J103',57),('J104',77)]:place(ref,x,60,180,'bottom')
    place('J105',5,25,90,'left');place('J106',5,45,90,'left')
    anchors={'R124':(8.5,6),'R125':(30,6),'U120':(57,7),'U121':(74,7),
      'Q101':(77,46),'U112':(69.5,47),
      'U101':(14,18),'U102':(25,18),'U103':(36,18),'U104':(47,18),'U105':(58,18),'U117':(68,18),'U118':(78,18),
      'U106':(18,28),'U107':(26,29),'U108':(42,29),'U109':(56,29),'U110':(67,29),
      'U111':(14,39),'U113':(25,39),'U114':(36,39),'U115':(47,39),'U116':(58,39),'U119':(69,39),
      'U311':(19,49),'U312':(40,49),'U313':(60,49)}
    for ref,xy in anchors.items():place(ref,*xy)
    # Place decouplers first, close to their own IC instead of a generic global-rail center.
    owners={f'C{110+i}':f'U{101+i}' for i in range(12)}
    owners.update({f'C{123+i}':f'U{113+i}' for i in range(7)})
    owners.update(C101='U101',R105='U101',C122='U112',R113='Q101',R114='Q101',R180='U112',R181='U112',R111='U119',R112='U119')
    for i in range(3):
        u=f'U{311+i}';owners[f'C{311+i}']=u;owners[f'R{350+i}']=u
        for n in [314+2*i,315+2*i]:owners[f'C{n}']=u
        for n in range(341+3*i,344+3*i):owners[f'R{n}']=u
    passive_order=sorted(set(parts)-set(positions),key=lambda r:(0 if r in ['C101','R105'] else 1 if r[0]=='C' else 2,r))
    rail_names={'WP10_ARM_RETURN',pn['U101','1'],pn['U112','1'],pn['J101','3']}
    for ref in passive_order:
        f=fps[ref];f.SetPosition(mm(0,0));f.SetOrientationDegrees(0);local=bbox(f)
        own=owners.get(ref);targets=[]
        if own:
            # Use owning-IC center as bounded placement preference; trace-length check follows routing.
            targets.append((positions[own][0],positions[own][1],5.))
        else:
            mynets={n for (r,p),n in pn.items() if r==ref and n not in rail_names}
            for r,pos in positions.items():
                if r in parts and any(rr==r and n in mynets for (rr,pp),n in pn.items()):targets.append((pos[0],pos[1],1.))
        if not targets:targets=[(44,34,1.)]
        best=None
        for ix in range(8,173):
            x=ix*.5
            for iy in range(24,111):
                y=iy*.5;q=(local[0]+x,local[1]+y,local[2]+x,local[3]+y)
                if not inside(q) or any(overlap(q,v) for v in occupied.values()):continue
                score=sum(w*(abs(x-a)+abs(y-bb)) for a,bb,w in targets)
                # Reserve hot edge; precision/timing parts get >=12mm row allocation.
                if best is None or score<best[0]:best=(score,x,y)
        assert best is not None,('No placement fit',ref)
        place(ref,best[1],best[2])
    for a,z in zip([(0,0),(90,0),(90,70),(0,70)],[(90,0),(90,70),(0,70),(0,0)]):
        edge=k.PCB_SHAPE();edge.SetShape(k.SHAPE_T_SEGMENT);edge.SetStart(mm(*a));edge.SetEnd(mm(*z));edge.SetWidth(k.FromMM(.05));edge.SetLayer(k.Edge_Cuts);b.Add(edge)
    for s,x,y in [('WP10 V36 STOP / THERMAL - CANDIDATE',45,11),('ARM_RETURN - NO PRIMARY RETURN',45,68.7)]:
        t=k.PCB_TEXT(b);t.SetText(s);t.SetPosition(mm(x,y));t.SetTextSize(mm(.65,.65));t.SetTextThickness(k.FromMM(.1));t.SetLayer(k.F_SilkS);b.Add(t)
    R.mkdir(exist_ok=True);k.SaveBoard(str(target),b)
    project={'board':{'design_settings':{'rules':{'min_clearance':.15,'min_track_width':.15,'min_via_diameter':.6,'min_through_hole_diameter':.3}}},
        'net_settings':{'classes':[dict(name='Default',clearance=.15,track_width=.25,via_diameter=.6,via_drill=.3,microvia_diameter=.3,microvia_drill=.1,diff_pair_width=.25,diff_pair_gap=.2,diff_pair_via_gap=.25)]}}
    target.with_suffix('.kicad_pro').write_text(json.dumps(project,indent=2)+'\n',encoding='utf-8')
    cold=k.LoadBoard(str(target));assert len(list(cold.GetFootprints()))==107
    bound=[]
    for f in cold.GetFootprints():
        if f.GetReference() not in parts:continue
        for pad in f.Pads():
            n=pad.GetNumber()
            if n and n!='MP':
                assert pad.GetNetname()==pn[f.GetReference(),n]
                bound.append(dict(ref=f.GetReference(),pin=n,net=pad.GetNetname()))
    record=dict(schema='WP10_STOP_BOARD_PHYSICAL_PLACEMENT',board=str(target),board_sha256=sha(target),source_xml=str(N/'wp10_system.xml'),source_xml_sha256=sha(N/'wp10_system.xml'),
      electrical_footprints=103,board_only_mounting_holes=4,cold_native_load_passed=True,pad_net_bindings=bound,mechanical_retention_pads=mechanical_pads,
      position_mm_degrees=positions,courtyard_boxes_mm=occupied,courtyard_gap_allocation_mm=.25,board_mm=[90,70,1.6],
      phase='PLACEMENT_ONLY_UNROUTED',routed=False,DRC_executed=False,manufacturing_release=False,geometry_installed_in873host=False,whole_design_complete=False,
      pending=['Critical decap/gate/CWD route lengths and planes','Power trace classes/current and thermal checks','Silkscreen and connector mating/height checks','Full native DRC and imported-netlist parity','Host mounting/keepout and thermal installation'],
      source_bindings={str(p):sha(p) for p in [N/'VERIFICATION.json',P/'PHYSICAL_PARTS.json',P/'BOARD_SCOPE.json',Path(__file__)]})
    dump(R/'PLACEMENT.json',record)
    print(json.dumps(dict(board=str(target),electrical_footprints=103,mounting_holes=4,phase=record['phase'],native_cold_load=True)))
if __name__=='__main__':main()
