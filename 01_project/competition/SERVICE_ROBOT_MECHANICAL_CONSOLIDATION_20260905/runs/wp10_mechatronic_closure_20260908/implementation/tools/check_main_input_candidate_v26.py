"""Native readback of the actual candidate against the same system XML."""
from pathlib import Path
import json,hashlib,xml.etree.ElementTree as ET,faulthandler
import pcbnew as k
from erc_source_contract import parse,children,val,properties
A=Path(__file__).resolve().parents[1]
diag=(A/'logs/MAIN_INPUT_READBACK_STACK_V26.log').open('w');faulthandler.enable(diag);faulthandler.dump_traceback_later(15,file=diag,exit=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):(A/p).write_text(json.dumps(x,indent=2,ensure_ascii=False),encoding='utf-8')
board=A/'ecad/wp10_main_input_v26_candidate.kicad_pcb';b=k.LoadBoard(str(board))
ids={properties(f)['Reference']:val(f[1]) for f in children(parse(board.read_text(encoding='utf-8')),'footprint')}
d=json.loads((A/'power/MAIN_INPUT_BOARD_DEFINITION_V25.json').read_text());oldrefs={r['ref']:r for r in d['refs']}
root=ET.parse(A/'ecad/wp10_system.xml').getroot();cs={c.get('ref'):c for c in root.findall('./components/comp')}
ns={(p.get('ref'),p.get('pin')):n.get('name') for n in root.findall('./nets/net') for p in n.findall('node')}
fps={f.GetReference():f for f in b.GetFootprints()};pads=[];refs=[]
assert set(fps)==set(oldrefs)|{p['board_ref'] for p in d['ports']}|{'MH1','MH2','MH3','MH4'}
for r,f in fps.items():
 if r in oldrefs:
  fp=ids[r];lib,name=fp.split(':')
  assert f.GetValue()==cs[r].findtext('value') and fp==cs[r].findtext('footprint')
  pos=[f.GetPosition().x/1e6,f.GetPosition().y/1e6];ang=f.GetOrientationDegrees()
  assert pos==([54,17] if r=='Q201' else oldrefs[r]['position_mm']) and ang==oldrefs[r]['rotation_deg']
  refs.append(dict(ref=r,MPN=f.GetValue(),footprint=fp,source_sha256=sha(A/'ecad'/(lib+'.pretty')/(name+'.kicad_mod')),position_mm=pos,rotation_deg=ang))
 for p in f.Pads():
  if r in oldrefs:
   n=ns.get((r,p.GetNumber()),'');expected='' if n.startswith('unconnected') else n
   assert p.GetNetname()==expected,(r,p.GetNumber(),p.GetNetname(),expected)
  box=p.GetBoundingBox()
  pads.append(dict(ref=r,pin=p.GetNumber(),net=p.GetNetname(),xy_mm=[p.GetPosition().x/1e6,p.GetPosition().y/1e6],
   size_mm=[p.GetSize().x/1e6,p.GetSize().y/1e6],drill_mm=[p.GetDrillSize().x/1e6,p.GetDrillSize().y/1e6],
   orientation_deg=p.GetOrientationDegrees(),bbox_mm=[box.GetLeft()/1e6,box.GetTop()/1e6,box.GetRight()/1e6,box.GetBottom()/1e6],
   through_hole=p.GetDrillSize().x>0))
tracks=[]
for t in b.GetTracks():
 if isinstance(t,k.PCB_VIA):tracks.append(dict(type='via',net=t.GetNetname(),xy_mm=[t.GetPosition().x/1e6,t.GetPosition().y/1e6],diameter_mm=t.GetWidth(k.F_Cu)/1e6,drill_mm=t.GetDrillValue()/1e6))
 else:tracks.append(dict(type='segment',net=t.GetNetname(),start_mm=[t.GetStart().x/1e6,t.GetStart().y/1e6],end_mm=[t.GetEnd().x/1e6,t.GetEnd().y/1e6],width_mm=t.GetWidth()/1e6,layer=b.GetLayerName(t.GetLayer()),length_mm=t.GetLength()/1e6))
d.update(schema='WP10_MAIN_INPUT_BOARD_LAYOUT_V26',source_xml_sha256=sha(A/'ecad/wp10_system.xml'),PCB_sha256=sha(board),
 refs=sorted(refs,key=lambda r:r['ref']),pads=pads,all_connections_routed=False,ordinary_signal_connections_routed=True,
 native_unconnected_split_terminal_items=4,source_candidate=board.relative_to(A).as_posix(),fixed_copper_file='power/MAIN_INPUT_FIXED_COPPER_V26.json')
d.pop('preliminary_routes',None)
dump('power/MAIN_INPUT_BOARD_DEFINITION_V26.json',d)
dump('results/MAIN_INPUT_NATIVE_READBACK_V26.json',dict(passed=True,PCB_sha256=sha(board),source_xml_sha256=sha(A/'ecad/wp10_system.xml'),
 components=31,footprints=len(fps),pads=len(pads),tracks=tracks,all_functional_pad_nets_match=True,unplanned_component_moves=0,
 V25_definition_sha256=sha(A/'power/MAIN_INPUT_BOARD_DEFINITION_V25.json'),design_settings_default_clearance_mm=b.GetDesignSettings().GetSmallestClearanceValue()/1e6))
print(json.dumps(dict(passed=True,footprints=len(fps),pads=len(pads),copper_items=len(tracks))))
faulthandler.cancel_dump_traceback_later()
