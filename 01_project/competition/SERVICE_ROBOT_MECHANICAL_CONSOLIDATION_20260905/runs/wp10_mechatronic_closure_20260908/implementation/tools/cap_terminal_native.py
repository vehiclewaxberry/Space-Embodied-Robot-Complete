"""Native pcbnew operations missing from MCP: bootstrap and pad/net/stackup binding.

Footprints, outline and copper tracks are authored through KiCad MCP.
"""
from pathlib import Path
import json,hashlib,sys,xml.etree.ElementTree as ET
import pcbnew as k
A=Path(__file__).resolve().parents[1];E=A/'ecad';P=E/'wp10_c203_terminal.kicad_pcb'
phase=sys.argv[1]
io=k.PCB_IO_KICAD_SEXPR()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,indent=2),encoding='utf-8')
if phase=='label_polarity':
    b=k.LoadBoard(str(P));matched=[]
    for item in b.GetDrawings():
        if item.GetLayer()==k.B_SilkS and item.GetText()=='C203  |  +1        2-':
            item.SetText('C203');item.SetPosition(k.VECTOR2I(k.FromMM(100),k.FromMM(88)));matched.append(item)
    assert len(matched)==1, 'Apply this label repair once'
    for text,x in [('1 +',95),('2 -',105)]:
        item=k.PCB_TEXT(b);item.SetText(text);item.SetPosition(k.VECTOR2I(k.FromMM(x),k.FromMM(94)));item.SetLayer(k.B_SilkS)
        item.SetTextSize(k.VECTOR2I(k.FromMM(1),k.FromMM(1)));item.SetTextThickness(k.FromMM(.15));item.SetMirrored(True);b.Add(item)
    assert k.SaveBoard(str(P),b)
    print('Silkscreen polarity labels individually aligned with native cap pads')
elif phase=='bootstrap':
    assert not P.exists(),'Refuse to replace an existing board'
    b=k.BOARD();b.SetFileName(str(P));b.GetDesignSettings().SetBoardThickness(k.FromMM(1.6))
    for name in ['C203_SingleFace_Terminal_D30_P10_W18','C203_BoardMount_4xM3_NPTH']:
        fp=io.FootprintLoad(str(E/'WP10_PASSIVES.pretty'),name)
        assert fp is not None,name
    assert k.SaveBoard(str(P),b)
    print(json.dumps(dict(bootstrap=True,board=str(P))))
elif phase=='bind':
    b=k.LoadBoard(str(P));rt=ET.parse(E/'wp10_system.xml').getroot()
    for old in list(b.GetFootprints()):b.Remove(old)
    if not list(b.GetFootprints()):
        # MCP placement failed to resolve the project library (three attempts),
        # although native FootprintLoad parsed both files. Use this supported API.
        for ref,name,value in [('C203','C203_SingleFace_Terminal_D30_P10_W18','ELXG101VSN222MR50S'),('H_C203','C203_BoardMount_4xM3_NPTH','BOARD_ONLY_4xM3')]:
            fp=io.FootprintLoad(str(E/'WP10_PASSIVES.pretty'),name);assert fp is not None
            fp.SetFPIDAsString('WP10_PASSIVES:'+name);fp.SetReference(ref);fp.SetValue(value)
            fp.SetPosition(k.VECTOR2I(k.FromMM(100),k.FromMM(100)));b.Add(fp)
            if ref=='C203':
                fp.SetAttributes(k.FP_THROUGH_HOLE)
                lib=io.FootprintLoad(str(E/'WP10_PASSIVES.pretty'),name);lib.SetAttributes(k.FP_THROUGH_HOLE)
                io.FootprintSave(str(E/'WP10_PASSIVES.pretty'),lib)
    native={n.get('pin'):net.get('name') for net in rt.findall('./nets/net') for n in net.findall('node') if n.get('ref')=='C203'}
    assert native=={'1':'WP10_PRECHARGED_PLUS','2':'WP10_INPUT_RETURN'}
    nets={}
    for name in native.values():
        existing=b.FindNet(name)
        if existing is None:existing=k.NETINFO_ITEM(b,name);b.Add(existing)
        nets[name]=existing
    found=[]
    for fp in b.GetFootprints():
        if fp.GetReference()=='C203':
            for pad in fp.Pads():
                if pad.GetAttribute()==k.PAD_ATTRIB_NPTH:continue
                assert pad.GetNumber() in native
                pad.SetNet(nets[native[pad.GetNumber()]]);found.append(pad.GetNumber())
        elif fp.GetReference()=='H_C203':
            fp.SetAttributes(k.FP_EXCLUDE_FROM_BOM|k.FP_EXCLUDE_FROM_POS_FILES|k.FP_BOARD_ONLY)
        else:raise AssertionError(fp.GetReference())
    assert sorted(found)==['1','1','2','2']
    b.GetDesignSettings().SetBoardThickness(k.FromMM(1.6))
    assert k.SaveBoard(str(P),b)
    dump(A/'results/CAP_TERMINAL_NATIVE_BINDING.json',dict(board_sha256=sha(P),source_xml_sha256=sha(E/'wp10_system.xml'),native_C203_pins=native,physical_electrical_pads=4,logical_pins=2,
        board_scope='C203 capacitor terminal board only; not 201-ref full PCB or CHB terminal connection',
        single_face_process_qualified=False,whole_design_complete=False))
    print(json.dumps(dict(bound=True,pads=4)))
elif phase=='finalize':
    # PCB stackup objects are opaque in the installed SWIG interface and no
    # loaded MCP setter exposes thickness. Modify only this structured metadata
    # through the existing KiCad AST codec, then validate/normalize with pcbnew.
    from erc_source_contract import parse,enc,children,val
    tree=parse(P.read_text(encoding='utf-8'));setup=children(tree,'setup')[0]
    for old in children(setup,'stackup'):setup.remove(old)
    stack=['stackup']
    definition=json.loads((A/'power/CAP_TERMINAL_DEFINITION.json').read_text())
    requested=definition['native_stackup_mm']
    for layer,kind in [('F.Mask','Top Solder Mask'),('F.Cu','copper'),('dielectric 1','core'),('B.Cu','copper'),('B.Mask','Bottom Solder Mask')]:
        t=requested[layer]
        node=['layer',json.dumps(layer),['type',json.dumps(kind)],['thickness',str(t)]]
        if kind=='core':node.extend([['material','"FR4_CANDIDATE"'],['epsilon_r','4.5'],['loss_tangent','0.02']])
        stack.append(node)
    setup.append(stack);P.write_text(enc(tree)+'\n',encoding='utf-8')
    b=k.LoadBoard(str(P))
    for d in b.GetDrawings():
        if d.GetLayer()==k.B_SilkS and hasattr(d,'SetMirrored'):d.SetMirrored(True)
    assert k.SaveBoard(str(P),b)
    tree=parse(P.read_text(encoding='utf-8'));actual=children(children(tree,'setup')[0],'stackup')[0]
    layers={val(x[1]):float(children(x,'thickness')[0][1]) for x in children(actual,'layer') if children(x,'thickness')}
    assert layers==requested,layers
    assert abs(sum(layers.values())-1.6)<1e-12
    dump(A/'results/CAP_TERMINAL_STACKUP.json',dict(native_board_sha256=sha(P),layers_mm=layers,finished_thickness_mm=1.6,
        single_printed_copper_face=layers['F.Cu']==0,front_copper_scope=definition.get('front_copper_scope','No front copper'),material='FR4_CANDIDATE; laminate supplier/Tg/thermal/outgassing not qualified',
        stackup_scope='Nominal design requirement read back from native KiCad; not board-fabrication tolerance or measured thickness',manufacturing_qualified=False))
    print(json.dumps(dict(native_stackup=layers,back_silkscreen_mirrored=True)))
elif phase=='extract':
    b=k.LoadBoard(str(P));b.BuildConnectivity();mm=k.ToMM
    def xy(v):return [mm(v.x),mm(v.y)]
    pads=[]
    for f in b.GetFootprints():
        for p in f.Pads():pads.append(dict(ref=f.GetReference(),number=p.GetNumber(),uuid=p.m_Uuid.AsString(),xy_mm=xy(p.GetPosition()),size_mm=xy(p.GetSize()),drill_mm=xy(p.GetDrillSize()),circular=p.GetShape()==k.PAD_SHAPE_CIRCLE,type=int(p.GetAttribute()),net=p.GetNetname(),declared_copper_layers=[b.GetLayerName(n) for n in [k.F_Cu,k.B_Cu] if p.IsOnLayer(n)],copper_layers=[b.GetLayerName(n) for n in [k.F_Cu,k.B_Cu] if p.FlashLayer(n)],remove_unconnected=p.GetRemoveUnconnected(),keep_top_bottom=p.GetKeepTopBottom()))
    tracks=[dict(kind=t.GetClass(),start_mm=xy(t.GetStart()),end_mm=xy(t.GetEnd()),width_mm=mm(t.GetWidth()),layer=b.GetLayerName(t.GetLayer()),net=t.GetNetname()) for t in b.GetTracks()]
    rt=ET.parse(E/'wp10_system.xml').getroot();native={n.get('pin'):net.get('name') for net in rt.findall('./nets/net') for n in net.findall('node') if n.get('ref')=='C203'}
    assert len([p for p in pads if p['number']])==4 and all(p['net']==native[p['number']] for p in pads if p['number'])
    binding=json.loads((A/'results/CAP_TERMINAL_NATIVE_BINDING.json').read_text());binding.update(board_sha256=sha(P),source_xml_sha256=sha(E/'wp10_system.xml'),physical_holes_nonplated=sum(p['type']==int(k.PAD_ATTRIB_NPTH) and p['drill_mm'][0]>0 for p in pads),physical_holes_plated=sum(p['type']==int(k.PAD_ATTRIB_PTH) and p['drill_mm'][0]>0 for p in pads))
    dump(A/'results/CAP_TERMINAL_NATIVE_BINDING.json',binding)
    out=dict(board_sha256=sha(P),native_C203_binding_sha256=sha(A/'results/CAP_TERMINAL_NATIVE_BINDING.json'),pad_type_values={'PTH':int(k.PAD_ATTRIB_PTH),'NPTH':int(k.PAD_ATTRIB_NPTH),'SMD':int(k.PAD_ATTRIB_SMD)},board_thickness_mm=mm(b.GetDesignSettings().GetBoardThickness()),pads=pads,tracks=tracks,zone_count=b.GetAreaCount(),edges=[dict(start_mm=xy(d.GetStart()),end_mm=xy(d.GetEnd())) for d in b.GetDrawings() if d.GetLayer()==k.Edge_Cuts])
    out['board_copper_drawing_count']=sum(d.GetLayer() in [k.F_Cu,k.B_Cu] for d in b.GetDrawings())
    out['footprint_copper_drawing_count']=sum(d.GetLayer() in [k.F_Cu,k.B_Cu] for f in b.GetFootprints() for d in f.GraphicalItems())
    out['copper_drawing_count']=out['board_copper_drawing_count']+out['footprint_copper_drawing_count']
    out['extractor_sha256']=sha(Path(__file__))
    out['edge_count_is_four_line_segments']=len(out['edges'])==4 and all(d.GetShape()==k.SHAPE_T_SEGMENT for d in b.GetDrawings() if d.GetLayer()==k.Edge_Cuts)
    dump(A/'results/CAP_TERMINAL_NATIVE_GEOMETRY.json',out);print(json.dumps(dict(pads=len(pads),tracks=len(tracks),edges=len(out['edges']))))
else:raise ValueError(phase)
