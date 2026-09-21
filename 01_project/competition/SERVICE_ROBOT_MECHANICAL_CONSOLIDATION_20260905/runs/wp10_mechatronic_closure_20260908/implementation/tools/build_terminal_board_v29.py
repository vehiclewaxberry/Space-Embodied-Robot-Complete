"""Native import of the OEM footprint. Every electrode pin gets real copper."""
import json,xml.etree.ElementTree as ET
import pcbnew as k
from terminals_v29 import A,ROWS,FP,dump,sha
b=k.LoadBoard(str(A/'ecad/wp10_main_input_v29_prepared.kicad_pcb'));fps={f.GetReference():f for f in b.GetFootprints()}
def xy(p):return k.VECTOR2I(round(p[0]*1e6),round(p[1]*1e6))
rows=[]
def lines(net,pts,layer,width):
 for p,q in zip(pts,pts[1:]):
  t=k.PCB_TRACK(b);t.SetStart(xy(p));t.SetEnd(xy(q));t.SetWidth(round(width*1e6));t.SetLayer(layer);t.SetNet(net);t.SetLocked(True);b.Add(t)
  rows.append(dict(net=net.GetNetname(),start_mm=p,end_mm=q,width_mm=width,layer=b.GetLayerName(layer)))
netbyname={p.GetNetname():p.GetNet() for f in fps.values() for p in f.Pads() if p.GetNetname()}
comps={c.get('ref'):c for c in ET.parse(A/'ecad/wp10_system_v29.xml').getroot().findall('./components/comp')}
for ref,_,pos,name in ROWS:
 f=k.FootprintLoad(str(A/'ecad/WP10_TERMINALS.pretty'),FP.split(':')[1]);assert f
 f.SetFPID(k.LIB_ID(*FP.split(':')));c=comps[ref];f.SetPath(k.KIID_PATH(c.find('sheetpath').get('tstamps')+c.findtext('tstamps')))
 f.SetReference(ref);f.SetValue('74651195R');f.SetPosition(xy(pos));f.SetLocked(True);b.Add(f)
 if ref=='J205':f.Reference().SetPosition(xy((7,35.5)))
 if ref=='J207':f.Reference().SetPosition(xy((84,31.5)))
 assert len(list(f.Pads()))==9
 for pad in f.Pads():assert pad.GetNumber()=='1';pad.SetNet(netbyname[name])
 for layer in [k.F_Cu,k.B_Cu]:
  for off in [-4.435,0,4.435]:
   lines(netbyname[name],[(pos[0]-4.435,pos[1]+off),(pos[0]+4.435,pos[1]+off)],layer,3.2)
   lines(netbyname[name],[(pos[0]+off,pos[1]-4.435),(pos[0]+off,pos[1]+4.435)],layer,3.2)
lines(netbyname['WP10_PRECHARGED_PLUS'],[(84.11,25),(84.11,17)],k.F_Cu,1.5)
lines(netbyname['WP10_INPUT_RETURN'],[(79.89,25),(79.89,27.5),(81.89,27.5),(81.89,29)],k.F_Cu,1.5)
dst=A/'ecad/wp10_main_input_v29_candidate.kicad_pcb';k.SaveBoard(str(dst),b)
dump(A/'results/TERMINAL_NATIVE_BUILD_V29.json',dict(parent=sha(A/'ecad/wp10_main_input_v29_prepared.kicad_pcb'),output=sha(dst),added_copper=rows))
print(json.dumps(dict(footprints=len(list(b.GetFootprints())),new_terminal_pad_count=36,added_copper=len(rows))))
