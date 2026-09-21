"""KiCad native subset PCB from the authoritative full-system XML.

MCP has no subset import: this native adapter preserves31 refs and pin nets.
Board-only PORT_* are wire landings, not fictitious OEM connector pins.
Run only through run_main_board_v25.py under the existing serial resource guard.
"""
from pathlib import Path
import hashlib,json,math,xml.etree.ElementTree as ET
import pcbnew as k
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def dump(p,v):(A/p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def xy(x,y):return k.VECTOR2I(round(x*1e6),round(y*1e6))
positions={
 'F201':[18,15,0],'R201':[34,15,0],'R202':[45,15,0],'Q201':[66,17,0],
 'U201':[48,29,0],'C202':[28,24,0],'D201':[19,25,0],'D202':[84,25,0],
 'R203':[39,27,90],'R204':[39,32,90],'R205':[42,27,90],'R206':[42,32,90],
 'R207':[53,34,90],'C201':[45,43,0],
 'U205':[66,42,0],'C211':[74,39,0],'C212':[66,58,0],
 'R211':[60,41,90],'R212':[60,46,90],'R213':[60,51,90],
 'U206':[82,51,0],'C213':[82,59,0],'Q204':[91,43,0],
 'R214':[54,29,90],'R215':[74,50,90],'R216':[74,55,90],
 'R217':[85,44,90],'R218':[89,51,90],'R219':[86,39,90],
 'R220':[78,51,90],'R221':[78,46,90]}
selection=read('power/MAIN_BOARD_SELECTION_V25.json');assert set(positions)==set(selection) and len(selection)==31
rt=ET.parse(A/'ecad/wp10_system.xml').getroot();components={c.get('ref'):c for c in rt.findall('./components/comp')}
native={(p.get('ref'),p.get('pin')):n.get('name') for n in rt.findall('./nets/net') for p in n.findall('node')}
allnets={n.get('name'):['.'.join((p.get('ref'),p.get('pin'))) for p in n.findall('node')] for n in rt.findall('./nets/net')}
dest=A/'ecad/wp10_main_input.kicad_pcb';assert not dest.exists()
b=k.BOARD();b.SetCopperLayerCount(2);b.GetDesignSettings().SetBoardThickness(1600000)
nets={}
for name in sorted({native[(r,p.get('num'))] for r in positions for p in components[r].findall('./units/unit/pins/pin') if (r,p.get('num')) in native}):
 obj=k.NETINFO_ITEM(b,name);b.Add(obj);nets[name]=obj
for (x1,y1,x2,y2) in [(0,0,100,0),(100,0,100,80),(100,80,0,80),(0,80,0,0)]:
 s=k.PCB_SHAPE();s.SetShape(k.SHAPE_T_SEGMENT);s.SetStart(xy(x1,y1));s.SetEnd(xy(x2,y2));s.SetLayer(k.Edge_Cuts);s.SetWidth(50000);b.Add(s)
fps={};copied=[]
for ref,(x,y,ang) in positions.items():
 c=components[ref];fpname=c.findtext('footprint');assert fpname==selection[ref]['footprint']
 lib,name=fpname.split(':');src=A/'ecad'/(lib+'.pretty')/(name+'.kicad_mod')
 fp=k.FootprintLoad(str(src.parent),name);assert fp is not None,(ref,str(src))
 fp.SetReference(ref);fp.SetValue(c.findtext('value'));fp.SetPosition(xy(x,y));fp.SetOrientationDegrees(ang)
 fp.SetFPID(k.LIB_ID(lib,name));fp.SetPath(k.KIID_PATH(c.find('sheetpath').get('tstamps')+c.findtext('tstamps')))
 fp.Reference().SetTextSize(xy(.8,.8));fp.Reference().SetTextThickness(120000);fp.Reference().SetLayer(k.F_Fab)
 fp.Value().SetVisible(False);b.Add(fp);fps[ref]=fp
 expected={p.get('num') for p in c.findall('./units/unit/pins/pin')}
 assert {p.GetNumber() for p in fp.Pads()}==expected,(ref,expected)
 for p in fp.Pads():
  key=(ref,p.GetNumber());name_net=native.get(key)
  if name_net and not name_net.startswith('unconnected'):p.SetNet(nets[name_net])
 copied.append(dict(ref=ref,MPN=c.findtext('value'),footprint=fpname,source_sha256=sha(src),position_mm=[x,y],rotation_deg=ang))
ports=[
 ('PORT_BAT_PLUS','F201','1',7,15,True),('PORT_BAT_RETURN','U201','5',7,28,True),
 ('PORT_CHB_PLUS','Q201','3',93,15,True),('PORT_CHB_RETURN','U201','5',93,28,True),
 ('PORT_ENABLE','Q204','3',93,36,False),('PORT_RESET','U201','3',39,66,False),
 ('PORT_PGD','U201','8',51,66,False),('PORT_SIGNAL_RETURN','U201','5',63,73,False)]
boundary=[]
for ref,rr,pin,x,y,power in ports:
 fp=k.FOOTPRINT(b);fp.SetReference(ref);fp.SetValue('PROJECT_WIRE_LANDING_NOT_OEM_CONNECTOR');fp.SetPosition(xy(x,y))
 pad=k.PAD(fp);pad.SetNumber('1');pad.SetAttribute(k.PAD_ATTRIB_PTH);pad.SetShape(k.PAD_SHAPE_CIRCLE)
 pad.SetSize(xy(7 if power else 2.4,7 if power else 2.4));pad.SetDrillSize(xy(3.2 if power else 1.2,3.2 if power else 1.2));pad.SetLayerSet(k.PAD.PTHMask())
 pad.SetPosition(xy(x,y));net=native[(rr,pin)];pad.SetNet(nets[net]);fp.Add(pad);b.Add(fp);fps[ref]=fp
 fp.Reference().SetPosition(xy(x,y+5 if power else y+2));fp.Reference().SetTextSize(xy(.8,.8));fp.Reference().SetLayer(k.F_Fab);fp.Value().SetVisible(False)
 boundary.append(dict(board_ref=ref,net=net,position_mm=[x,y],function='unfitted wire landing',source_endpoint=rr+'.'+pin,
  outside_module_endpoints=[p for p in allnets[net] if p.split('.')[0] not in positions],current_qualification=False))
for i,(x,y) in enumerate([(4,4),(96,4),(4,76),(96,76)],1):
 fp=k.FOOTPRINT(b);fp.SetReference('MH'+str(i));fp.SetPosition(xy(x,y));fp.Value().SetVisible(False);fp.Reference().SetVisible(False)
 pad=k.PAD(fp);pad.SetNumber('');pad.SetAttribute(k.PAD_ATTRIB_NPTH);pad.SetShape(k.PAD_SHAPE_CIRCLE);pad.SetSize(xy(3.2,3.2));pad.SetDrillSize(xy(3.2,3.2));pad.SetLayerSet(k.PAD.PTHMask());pad.SetPosition(xy(x,y));fp.Add(pad);b.Add(fp)
 # M3 head/tool clearance is an explicit project mechanical reservation.
 circ=k.PCB_SHAPE();circ.SetShape(k.SHAPE_T_CIRCLE);circ.SetCenter(xy(x,y));circ.SetEnd(xy(x+3.5,y));circ.SetLayer(k.Dwgs_User);circ.SetWidth(100000);b.Add(circ)
def pad_at(ref,pin,kelvin=False):
 ps=[p for p in fps[ref].Pads() if p.GetNumber()==pin]
 return min(ps,key=lambda p:p.GetSize().y) if kelvin else max(ps,key=lambda p:p.GetSize().y)
routes=[]
def route(ref1,pin1,ref2,pin2,width,mid=(),kelvin=False,layer=k.F_Cu):
 p1=pad_at(ref1,pin1,kelvin);p2=pad_at(ref2,pin2)
 assert p1.GetNetname()==p2.GetNetname() and p1.GetNetCode()!=0
 points=[p1.GetPosition(),*[xy(*p) for p in mid],p2.GetPosition()]
 for start,end in zip(points,points[1:]):
  tr=k.PCB_TRACK(b);tr.SetStart(start);tr.SetEnd(end);tr.SetLayer(layer);tr.SetWidth(round(width*1e6));tr.SetNet(p1.GetNet());b.Add(tr)
 routes.append(dict(from_endpoint=ref1+'.'+pin1,to_endpoint=ref2+'.'+pin2,width_mm=width,layer=b.GetLayerName(layer),Kelvin_from_split_land=kelvin))
# Wide power skeleton is intentionally incomplete where gate/pad fan-out needs review.
route('PORT_BAT_PLUS','1','F201','1',3)
route('F201','2','R201','1',3)
route('R201','2','R202','1',3)
# Dedicated Kelvin traces leave narrow pads and never merge into the power lands.
route('R201','1','U201','2',.20,[(31.535,22),(44.5,22),(44.5,28.5)],True)
route('R202','2','U201','1',.20,[(47.465,22),(45.8,24)],True)
route('U205','13','U205','5',.25,[(65.5,42.75)])
k.SaveBoard(str(dest),b)
actual=k.LoadBoard(str(dest));assert len(actual.GetFootprints())==43
padrows=[]
for fp in actual.GetFootprints():
 for p in fp.Pads():padrows.append(dict(ref=fp.GetReference(),pin=p.GetNumber(),net=p.GetNetname(),xy_mm=[p.GetPosition().x/1e6,p.GetPosition().y/1e6],size_mm=[p.GetSize().x/1e6,p.GetSize().y/1e6],drill_mm=[p.GetDrillSize().x/1e6,p.GetDrillSize().y/1e6]))
assert all(p['net']==(native.get((p['ref'],p['pin'])) or '') for p in padrows if p['ref'] in positions and not (native.get((p['ref'],p['pin'])) or '').startswith('unconnected'))
definition=dict(schema='WP10_MAIN_INPUT_BOARD_LAYOUT_V25',source_xml_sha256=sha(A/'ecad/wp10_system.xml'),PCB_sha256=sha(dest),
 module_is_subset_of_same_system=True,duplicate_schematic_project_created=False,refs=copied,pads=padrows,ports=boundary,
 outline_mm=[0,0,100,80],thickness_mm=1.6,mounting_holes_mm=[[4,4],[96,4],[4,76],[96,76]],
 hole_diameter_mm=3.2,tool_radius_mm=3.5,preliminary_routes=routes,
 copper_current_qualification=False,stackup_copper_thickness_bound=False,all_connections_routed=False,
 installed_in_974_component_plan=False,whole_assembly_transform=None,
 Q201_tab='DRAIN_LIVE; isolated heat spreader design required; no chassis short',
 C202='near split resistor cluster; exact hot-short input L and supply-side energy buffer still open',
 thermal_path_completed=False,manufacturing_release=False)
dump('power/MAIN_INPUT_BOARD_DEFINITION_V25.json',definition)
print(json.dumps(dict(board=str(dest),functional_refs=31,wire_landings=8,mounting_holes=4,pads=len(padrows),routing_complete=False)))

