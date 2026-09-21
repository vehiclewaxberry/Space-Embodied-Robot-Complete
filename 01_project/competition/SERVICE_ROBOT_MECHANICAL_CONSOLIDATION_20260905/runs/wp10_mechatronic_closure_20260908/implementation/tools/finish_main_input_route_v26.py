"""Resolve two dense LDO escapes without modifying fixed critical nets."""
from pathlib import Path
import json,hashlib,math
import pcbnew as k
from erc_source_contract import parse,enc,children,val
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
src=A/'ecad/wp10_main_input_v26_routed.kicad_pcb';fixed=A/'ecad/wp10_main_input_v26_fixed.kicad_pcb'
allowed=set(json.loads((A/'results/MAIN_INPUT_SIGNAL_MERGE_V26.json').read_text())['allowed_nets'])
base=parse(fixed.read_text(encoding='utf-8'));old=parse(src.read_text(encoding='utf-8'))
signals=[v for v in old if isinstance(v,list) and v[0] in ['segment','via'] and val(children(v,'net')[0][-1]) in allowed]
prepared=A/'ecad/wp10_main_input_v26_escape_base.kicad_pcb';prepared.write_text(enc(base+signals)+'\n',encoding='utf-8')
b=k.LoadBoard(str(prepared));fps={f.GetReference():f for f in b.GetFootprints()}
rows=[]
def xy(p):return k.VECTOR2I(round(p[0]*1e6),round(p[1]*1e6))
def pin(r,n):return next(p for p in fps[r].Pads() if p.GetNumber()==n)
def line(net,pts,layer):
 for p,q in zip(pts,pts[1:]):
  t=k.PCB_TRACK(b);t.SetStart(xy(p));t.SetEnd(xy(q));t.SetWidth(200000);t.SetLayer(layer);t.SetNet(net);t.SetLocked(True);b.Add(t)
  rows.append(dict(type='segment',net=net.GetNetname(),start_mm=p,end_mm=q,width_mm=.2,layer=b.GetLayerName(layer)))
def via(net,p):
 v=k.PCB_VIA(b);v.SetPosition(xy(p));v.SetWidth(600000);v.SetDrill(300000);v.SetViaType(k.VIATYPE_THROUGH);v.SetLayerPair(k.F_Cu,k.B_Cu);v.SetNet(net);v.SetLocked(True);b.Add(v)
 rows.append(dict(type='via',net=net.GetNetname(),xy_mm=p,diameter_mm=.6,drill_mm=.3))
N=pin('U205','2').GetNet()
line(N,[(64.575,41.25),(63.2,41.25)],k.F_Cu);via(N,(63.2,41.25))
line(N,[(63.2,41.25),(63.2,38),(59,38),(58.8,41.825)],k.B_Cu);via(N,(58.8,41.825));line(N,[(58.8,41.825),(60,41.825)],k.F_Cu)
N=pin('U205','4').GetNet()
line(N,[(64.575,42.25),(62.775,42.25)],k.F_Cu);via(N,(62.775,42.25))
line(N,[(62.775,42.25),(62.575,41.75),(62.575,39),(60,39)],k.B_Cu);via(N,(60,39));line(N,[(60,39),(60,40.175)],k.F_Cu)
dst=A/'ecad/wp10_main_input_v26_candidate.kicad_pcb';k.SaveBoard(str(dst),b)
out=dict(schema='WP10_V26_LDO_MANUAL_ESCAPE',input_sha256=sha(src),fixed_input_sha256=sha(fixed),output_sha256=sha(dst),added=rows)
(A/'results/MAIN_INPUT_LDO_ESCAPE_V26.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps({'added_items':len(rows),'candidate_sha256':sha(dst)}))
