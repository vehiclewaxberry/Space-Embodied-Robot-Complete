"""Supported pcbnew fallback for unresolved project-local placement/net binding.
MCP authors footprint/outline/tracks; no edit of old V17 board or system schematic.
"""
from pathlib import Path
import json,sys,hashlib,xml.etree.ElementTree as ET
import pcbnew as k
A=Path(__file__).resolve().parents[1];P=A/'ecad/wp10_chb_input.kicad_pcb'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):(A/p).write_text(json.dumps(v,indent=2),encoding='utf-8')
b=k.LoadBoard(str(P));phase=sys.argv[1]
rt=ET.parse(A/'ecad/wp10_system.xml');nets={n.get('pin'):net.get('name') for net in rt.findall('.//nets/net') for n in net.findall('node') if n.get('ref')=='U203'}
assert {n:nets[n] for n in ['1','2','4']}=={'1':'WP10_PRECHARGED_PLUS','2':'WP10_CHB_ENABLE','4':'WP10_INPUT_RETURN'}
if phase=='bind':
 assert not list(b.GetFootprints()),'one-time binding'
 io=k.PCB_IO_KICAD_SEXPR();f=io.FootprintLoad(str(A/'ecad/WP10_PASSIVES.pretty'),'CHB_Input_124_Terminal_V18');assert f
 f.SetFPIDAsString('WP10_PASSIVES:CHB_Input_124_Terminal_V18');f.SetReference('U203');f.SetValue('INPUT_ONLY_1_2_4');f.SetAttributes(k.FP_THROUGH_HOLE)
 f.SetPosition(k.VECTOR2I(k.FromMM(100),k.FromMM(100)));b.Add(f);f.Value().SetVisible(False);f.Reference().SetVisible(False)
 ns={}
 for num in ['1','2','4']:
  n=k.NETINFO_ITEM(b,nets[num]);b.Add(n);ns[num]=n
 for p in f.Pads():
  if p.GetNumber():p.SetNet(ns[p.GetNumber()])
 assert k.SaveBoard(str(P),b)
 # Stackup setter is not exposed by installed SWIG or MCP; AST metadata only,
 # followed by native reload/save and native AST readback.
 from erc_source_contract import parse,enc,children,val
 t=parse(P.read_text());setup=children(t,'setup')[0]
 for old in children(setup,'stackup'):setup.remove(old)
 stack=['stackup']
 for layer,kind,th in [('F.Mask','Top Solder Mask',.01),('F.Cu','copper',.07),('dielectric 1','core',1.44),('B.Cu','copper',.07),('B.Mask','Bottom Solder Mask',.01)]:
  node=['layer',json.dumps(layer),['type',json.dumps(kind)],['thickness',str(th)]]
  if kind=='core':node += [['material','"FR4_CANDIDATE"'],['epsilon_r','4.5'],['loss_tangent','0.02']]
  stack.append(node)
 setup.append(stack);P.write_text(enc(t)+'\n');b=k.LoadBoard(str(P));assert k.SaveBoard(str(P),b)
 print(json.dumps(dict(bound=True,nets={n:nets[n] for n in ['1','2','4']})))
elif phase=='extract':
 mm=k.ToMM
 def xy(v):return [mm(v.x),mm(v.y)]
 pads=[dict(number=p.GetNumber(),xy_mm=xy(p.GetPosition()),size_mm=xy(p.GetSize()),drill_mm=xy(p.GetDrillSize()),net=p.GetNetname(),type=int(p.GetAttribute()),layers=[b.GetLayerName(i) for i in [k.F_Cu,k.B_Cu] if p.IsOnLayer(i)]) for f in b.GetFootprints() for p in f.Pads()]
 tracks=[dict(start_mm=xy(t.GetStart()),end_mm=xy(t.GetEnd()),width_mm=mm(t.GetWidth()),net=t.GetNetname(),layer=b.GetLayerName(t.GetLayer())) for t in b.GetTracks()]
 assert len(pads)==10 and len(tracks)==10 and all(p['net']==nets[p['number']] for p in pads if p['number'])
 from erc_source_contract import parse,children,val
 tree=parse(P.read_text());st=children(children(tree,'setup')[0],'stackup')[0]
 layers={val(x[1]):float(children(x,'thickness')[0][1]) for x in children(st,'layer') if children(x,'thickness')}
 assert layers=={'F.Mask':.01,'F.Cu':.07,'dielectric 1':1.44,'B.Cu':.07,'B.Mask':.01}
 out=dict(board_sha256=sha(P),extractor_sha256=sha(__file__),definition_sha256=sha(A/'power/CHB_INPUT_DEFINITION.json'),source_xml_sha256=sha(A/'ecad/wp10_system.xml'),pads=pads,tracks=tracks,stackup_mm=layers,board_thickness_mm=mm(b.GetDesignSettings().GetBoardThickness()),edges=[dict(start_mm=xy(x.GetStart()),end_mm=xy(x.GetEnd())) for x in b.GetDrawings() if x.GetLayer()==k.Edge_Cuts],zone_count=b.GetAreaCount(),copper_drawing_count=sum(x.GetLayer() in [k.F_Cu,k.B_Cu] for x in b.GetDrawings())+sum(x.GetLayer() in [k.F_Cu,k.B_Cu] for f in b.GetFootprints() for x in f.GraphicalItems()),system_U203_nets=nets,scope='Input-side three U203 pins only; main schematic remains ecad/wp10_system.kicad_sch; the MCP-created blank board schematic is not a system netlist',main_feed_wire_bound=False,physical_assembly_executed=False)
 dump('results/CHB_INPUT_NATIVE_V18.json',out);print(json.dumps(dict(pads=len(pads),tracks=len(tracks),layers=layers)))
else:raise ValueError(phase)
