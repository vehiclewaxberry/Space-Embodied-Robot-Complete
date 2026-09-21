"""Native fixed power, return, Kelvin and gate routing; no hardware I/O.
Run under the serial memory guard using the KiCad Python adapter.
"""
from pathlib import Path
import hashlib,json,math,shutil
import pcbnew as k
A=Path(__file__).resolve().parents[1];H=A/'history/20260910_V26_before_routing'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def xy(x,y):return k.VECTOR2I(round(x*1e6),round(y*1e6))
source=A/'ecad/wp10_main_input.kicad_pcb'
if not H.exists():
 assert sha(source)=='a0f07733ad6455ce76246eee0c708c56945476ed0fc76024d21498bc58773ab0'
 H.mkdir();shutil.copy2(source,H/source.name)
 for rel in ['power/MAIN_INPUT_BOARD_DEFINITION_V25.json','results/MAIN_INPUT_BOARD_DRC_V25.json','ecad/wp10_system.xml']:
  shutil.copy2(A/rel,H/Path(rel).name)
b=k.LoadBoard(str(H/source.name));fps={f.GetReference():f for f in b.GetFootprints()}
# Remove old preliminary copper; the two reviewed Kelvin paths are recreated exactly.
for t in list(b.GetTracks()):b.Remove(t)
fps['Q201'].SetPosition(xy(54,17))
for fp in b.GetFootprints():fp.SetLocked(True)
# C201 silk is clipped by its widened slot: move only the silk right edge outward.
for g in fps['C201'].GraphicalItems():
 if g.GetLayer()==k.F_SilkS and isinstance(g,k.PCB_SHAPE) and g.GetShape()==k.SHAPE_T_RECT:
  end=g.GetEnd();end.x=max(end.x,round(51.8e6));g.SetEnd(end)
def pad(ref,pin,small=False):
 ps=[p for p in fps[ref].Pads() if p.GetNumber()==pin]
 return min(ps,key=lambda p:p.GetSize().y) if small else max(ps,key=lambda p:p.GetSize().y)
segments=[];vias=[]
def seg(net,start,end,width,layer=k.F_Cu,role='SIGNAL_FIXED'):
 t=k.PCB_TRACK(b);t.SetStart(xy(*start));t.SetEnd(xy(*end));t.SetWidth(round(width*1e6));t.SetLayer(layer);t.SetNet(net);t.SetLocked(True);b.Add(t)
 segments.append(dict(net=net.GetNetname(),start_mm=list(start),end_mm=list(end),width_mm=width,layer=b.GetLayerName(layer),role=role,length_mm=math.dist(start,end)))
def path(net,pts,width,layer=k.F_Cu,role='SIGNAL_FIXED'):
 for p,q in zip(pts,pts[1:]):seg(net,p,q,width,layer,role)
def at(p):return (p.GetPosition().x/1e6,p.GetPosition().y/1e6)
def route(r1,p1,r2,p2,w,mid=(),small=False,layer=k.F_Cu,role='SIGNAL_FIXED'):
 a=pad(r1,p1,small);c=pad(r2,p2);assert a.GetNetname()==c.GetNetname() and a.GetNetCode()!=0,(r1,p1,r2,p2)
 path(a.GetNet(),[at(a),*mid,at(c)],w,layer,role)
def via(net,x,y,d=.8,h=.4):
 v=k.PCB_VIA(b);v.SetPosition(xy(x,y));v.SetWidth(round(d*1e6));v.SetDrill(round(h*1e6));v.SetViaType(k.VIATYPE_THROUGH);v.SetLayerPair(k.F_Cu,k.B_Cu);v.SetNet(net);v.SetLocked(True);b.Add(v)
 vias.append(dict(net=net.GetNetname(),xy_mm=[x,y],diameter_mm=d,drill_mm=h,plating_min_requirement_um=20,plating_qualified=False))
G=pad('U201','5').GetNet()
# Power return is on B.Cu; all positive power is F.Cu. No parallel-copper credit.
path(G,[(7,28),(7,30.5),(93,30.5),(93,28)],8,k.B_Cu,'MAIN_RETURN')
route('PORT_BAT_PLUS','1','F201','1',3,role='MAIN_FORWARD')
route('F201','2','R201','1',3,role='MAIN_FORWARD')
route('R201','2','R202','1',3,role='MAIN_FORWARD')
S=pad('R202','2').GetNet();path(S,[at(pad('R202','2')),(50,14.11),(50,10)],3,role='MAIN_FORWARD')
path(S,[(50,10),(59.45,10)],5,role='MAIN_FORWARD');path(S,[(59.45,10),(59.45,17)],2.6,role='MAIN_FORWARD_NECK')
P=pad('Q201','3').GetNet();path(P,[(64.9,17),(69,17)],2.6,role='MAIN_FORWARD_NECK');path(P,[(69,17),(90,17),(93,15)],6,role='MAIN_FORWARD')
route('R201','1','U201','2',.2,[(31.535,22),(44.5,22),(44.5,28.5)],True,role='KELVIN_VIN_NO_TAPS')
route('R202','2','U201','1',.2,[(47.465,22),(45.8,24)],True,role='KELVIN_SENSE_NO_TAPS')
# Bypass and clamps take current from power copper, not from the Kelvin branch.
route('F201','2','D201','2',1.5,[(24.5,17),(24.5,25)],role='INPUT_TVS')
route('F201','2','C202','1',.8,[(27,18.5)],role='INPUT_BYPASS')
route('D202','2','PORT_CHB_PLUS','1',1.5,[(88,25),(88,17)],role='OUTPUT_NEGATIVE_CLAMP')
for r,x in [('D201',16.85),('D202',81.89)]:
 path(G,[at(pad(r,'1')),(x,29)],1.5,role='CLAMP_RETURN')
 for xx in [x-.6,x+.6]:
  for yy in [27.5,29]:via(G,xx,yy,1.2,.6);seg(G,(x,yy),(xx,yy),1.2,role='CLAMP_RETURN')
route('C202','2','PORT_BAT_RETURN','1',.8,[(33,30.5),(7,30.5)],layer=k.B_Cu,role='INPUT_BYPASS_RETURN')
# MAIN_FUSED voltage feed stays separate from the VIN Kelvin copper.
route('R201','1','R203','1',.25,[(29.5,14.11),(29.5,25.4),(38,25.4),(38,27.825)],role='UPSTREAM_DIVIDER_FEED')
route('R203','1','R205','1',.25,role='UPSTREAM_DIVIDER_FEED')
M=pad('R205','1').GetNet();path(M,[at(pad('R205','1')),(43,28.5),(43,36)],.25,role='UPSTREAM_DIVIDER_FEED');via(M,43,36)
path(M,[(43,36),(57,36),(57,54),(72,54),(72,50.9125)],.25,k.B_Cu,'UPSTREAM_DIVIDER_FEED');via(M,72,50.9125);path(M,[(72,50.9125),at(pad('R215','1'))],.25,role='UPSTREAM_DIVIDER_FEED')
# Gate and OUT return are sampled at the physical Q201 pins, away from the clamps.
route('U201','10','Q201','1',.25,[(52,28),(54,26)],role='Q201_GATE_PAIR')
route('U201','9','Q201','3',.25,[(52.4,28.5),(54.5,26.4),(54.5,22.5),(64.9,22.5)],role='Q201_SOURCE_PAIR')
# Quiet hot-swap ground: one via into the main return; no other load uses this tree.
route('R204','2','U201','5',.25,[(40,31.175),(40,37),(45.8,38)],role='HS_QUIET_GROUND')
route('R206','2','U201','5',.25,[(41,31.175),(41,37.5),(45.8,38)],role='HS_QUIET_GROUND')
route('R207','2','U201','5',.25,[(49,33.175)],role='HS_QUIET_GROUND')
route('C201','2','U201','5',.4,[(50,38),(45.8,38)],role='HS_QUIET_GROUND')
path(G,[at(pad('U201','5')),(46.5,31),(46.5,32)],.4,role='HS_SINGLE_POINT_GROUND');via(G,46.5,32)
# LDO local capacitors and supervisor grounds converge before the main-return via.
route('U205','13','U205','5',.25,[(65.5,42.75)],role='LDO_EP_GROUND')
route('U205','13','U205','7',.25,[(66.5,43.25)],role='LDO_CT_GROUND')
path(G,[at(pad('U205','5')),(63.5,43.5),(63.5,61)],.5,role='STARTUP_LOCAL_GROUND')
route('R212','2','U205','5',.25,[(63.5,46),(63.5,43.5)],role='STARTUP_LOCAL_GROUND')
route('R213','2','U205','5',.25,[(63.5,50.175),(63.5,43.5)],role='STARTUP_LOCAL_GROUND')
route('C212','2','U205','5',.5,[(71,61),(63.5,61),(63.5,43.5)],role='STARTUP_LOCAL_GROUND')
route('C211','2','U205','5',.5,[(79,43.5),(72,43.5),(72,45),(63.5,46),(63.5,43.5)],role='STARTUP_LOCAL_GROUND')
path(G,[(63.5,43.5),(63.5,33.5)],.5,role='STARTUP_SINGLE_POINT_GROUND');via(G,63.5,33.5)
route('U206','2','R216','2',.25,[(79.7,51),(79.7,52.8),(80,55),(80,56),(76,56),(76,54.175)],role='SUPERVISOR_LOCAL_GROUND')
route('C213','2','U206','2',.4,[(87,63),(80,63),(80,55),(79.7,52.8),(79.7,51)],role='SUPERVISOR_LOCAL_GROUND')
route('R218','2','C213','2',.25,[(94,49.5375),(94,63),(87,63)],role='SUPERVISOR_LOCAL_GROUND')
route('Q204','2','R218','2',.25,[(94,43.95),(94,49.5375)],role='SUPERVISOR_LOCAL_GROUND')
route('R220','2','U206','2',.25,[(77,50.175),(77,53.5),(80,55),(79.7,52.8),(79.7,51)],role='SUPERVISOR_LOCAL_GROUND')
path(G,[(76,56),(76,43.5)],.5,role='SUPERVISOR_TO_LDO_GROUND')
route('PORT_SIGNAL_RETURN','1','U205','5',.4,[(63.5,61),(63.5,43.5)],role='TEST_RETURN')
# Bias input and control pull-up feed use the power-side SOURCE, not U201 OUT trace.
path(P,[(69,17),(70,23),(70,33),(74,33),(74,39)],.8,role='BIAS_INPUT_FEED')
route('C211','1','U205','11',.4,[(68.3,39),(68.3,41.25)],role='BIAS_LOCAL_INPUT')
route('U205','11','U205','10',.25,role='BIAS_LOCAL_INPUT')
route('U205','10','U205','8',.25,[(68.3,41.75),(68.3,42.75)],role='BIAS_LOCAL_INPUT')
route('C211','1','R219','1',.25,[(74,35),(84,35),(84,39.825)],role='CONTROL_PULLUP_INPUT')
dest=A/'ecad/wp10_main_input_v26_fixed.kicad_pcb';k.SaveBoard(str(dest),b)
dsn=A/'ecad/wp10_main_input_v26_fixed.dsn';assert k.ExportSpecctraDSN(b,str(dsn))
out=dict(schema='WP10_V26_FIXED_COPPER',input_sha256=sha(H/source.name),PCB_sha256=sha(dest),DSN_sha256=sha(dsn),
 Q201_position_mm=[54,17],functional_refs_preserved=31,board_pads_refcounts_preserved=len(b.GetFootprints())==43,
 fixed_segments=segments,vias=vias,finished_copper_thickness_requirement_mm=.07,copper_thickness_guaranteed=False,
 current_temperature_qualified=False,manufacturing_release=False)
(A/'power/MAIN_INPUT_FIXED_COPPER_V26.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(dict(segments=len(segments),vias=len(vias),PCB=str(dest),exported=True)))
