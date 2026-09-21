"""Same-file native pad, path, position and terminal-drill readback."""
import json,xml.etree.ElementTree as ET
import pcbnew as k
from terminals_v29 import A,H,ROWS,FP,sha,dump
from erc_source_contract import parse,children,properties,val
board=A/'ecad/wp10_main_input_v29_candidate.kicad_pcb';b=k.LoadBoard(str(board));ids={properties(f)['Reference']:val(f[1]) for f in children(parse(board.read_text()),'footprint')}
d=json.loads((A/'power/MAIN_INPUT_BOARD_DEFINITION_V26.json').read_text());oldrefs={r['ref']:r for r in d['refs']}
rt=ET.parse(A/'ecad/wp10_system_v29.xml').getroot();cs={c.get('ref'):c for c in rt.findall('./components/comp')};ns={(p.get('ref'),p.get('pin')):n.get('name') for n in rt.findall('./nets/net') for p in n.findall('node')}
fps={f.GetReference():f for f in b.GetFootprints()};functional=set(oldrefs)|{r[0] for r in ROWS};removed={r[1] for r in ROWS}
assert set(fps)==functional|{p['board_ref'] for p in d['ports'] if p['board_ref'] not in removed}|{'MH1','MH2','MH3','MH4'}
refs=[];pads=[];tracks=[];pad_uuids=[];track_uuids=[]
for r,f in fps.items():
 if r in functional:
  fp=ids[r];assert fp==cs[r].findtext('footprint') and f.GetValue()==cs[r].findtext('value'),(r,fp)
  expected=next((list(row[2]) for row in ROWS if row[0]==r),None)
  if expected is None:expected=[20,15] if r=='F201' else [82,25] if r=='D202' else oldrefs[r]['position_mm']
  pos=[f.GetPosition().x/1e6,f.GetPosition().y/1e6];assert pos==expected,(r,pos,expected)
  lib,name=fp.split(':');refs.append(dict(ref=r,MPN=f.GetValue(),footprint=fp,position_mm=pos,rotation_deg=f.GetOrientationDegrees(),source_sha256=sha(A/'ecad'/(lib+'.pretty')/(name+'.kicad_mod'))))
 for p in f.Pads():
  pad_uuids.append(p.m_Uuid.AsString())
  if r in functional:
   n=ns.get((r,p.GetNumber()),'');assert p.GetNetname()==('' if n.startswith('unconnected') else n),(r,p.GetNumber())
  box=p.GetBoundingBox();pads.append(dict(ref=r,pin=p.GetNumber(),net=p.GetNetname(),xy_mm=[p.GetPosition().x/1e6,p.GetPosition().y/1e6],size_mm=[p.GetSize().x/1e6,p.GetSize().y/1e6],drill_mm=[p.GetDrillSize().x/1e6,p.GetDrillSize().y/1e6],orientation_deg=p.GetOrientationDegrees(),bbox_mm=[box.GetLeft()/1e6,box.GetTop()/1e6,box.GetRight()/1e6,box.GetBottom()/1e6],through_hole=p.GetDrillSize().x>0))
for t in b.GetTracks():
 track_uuids.append(t.m_Uuid.AsString())
 if isinstance(t,k.PCB_VIA):tracks.append(dict(type='via',net=t.GetNetname(),xy_mm=[t.GetPosition().x/1e6,t.GetPosition().y/1e6],diameter_mm=t.GetWidth(k.F_Cu)/1e6,drill_mm=t.GetDrillValue()/1e6))
 else:tracks.append(dict(type='segment',net=t.GetNetname(),start_mm=[t.GetStart().x/1e6,t.GetStart().y/1e6],end_mm=[t.GetEnd().x/1e6,t.GetEnd().y/1e6],width_mm=t.GetWidth()/1e6,layer=b.GetLayerName(t.GetLayer()),length_mm=t.GetLength()/1e6))
for ref,_,pos,_ in ROWS:
 ps=[p for p in pads if p['ref']==ref];assert len(ps)==9 and all(p['pin']=='1' and p['size_mm']==[3.2,3.2] and p['drill_mm']==[1.85,1.85] for p in ps)
 assert sorted(tuple(round(p['xy_mm'][i]-pos[i],6) for i in range(2)) for p in ps)==sorted((x,y) for x in [-4.435,0,4.435] for y in [-4.435,0,4.435])
ports=[]
for p in d['ports']:
 q=dict(p)
 for ref,old,_,_ in ROWS:
  if q['board_ref']==old:q.update(board_ref=ref,prior_board_ref=old,function='74651195R M5 nine-leg single electrode; lug and process pending',symbol_pin='1')
 ports.append(q)
d.update(schema='WP10_MAIN_INPUT_BOARD_LAYOUT_V29',source_xml_sha256=sha(A/'ecad/wp10_system_v29.xml'),PCB_sha256=sha(board),refs=sorted(refs,key=lambda r:r['ref']),pads=pads,ports=ports,source_candidate=board.relative_to(A).as_posix(),fixed_copper_file=None)
dump(A/'power/MAIN_INPUT_BOARD_DEFINITION_V29.json',d)
dump(A/'results/MAIN_INPUT_NATIVE_READBACK_V29.json',dict(passed=True,PCB_sha256=sha(board),source_xml_sha256=sha(A/'ecad/wp10_system_v29.xml'),definition_sha256=sha(A/'power/MAIN_INPUT_BOARD_DEFINITION_V29.json'),pad_records=pads,pad_uuids=pad_uuids,track_uuids=track_uuids,components=len(refs),footprints=len(fps),pads=len(pads),tracks=tracks,all_functional_pad_nets_match=True,planned_component_moves=['F201','D202'],unplanned_component_moves=0))
print(json.dumps(dict(passed=True,functional_components=len(refs),footprints=len(fps),pads=len(pads),copper_items=len(tracks))))
