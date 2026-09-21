from pathlib import Path
import json,hashlib,copy,itertools,math
from chb_input_ocp import *
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
g=json.loads((A/'results/CHB_INPUT_NATIVE_V18.json').read_text());d=json.loads((A/'power/CHB_INPUT_DEFINITION.json').read_text())
assert g['board_sha256']==sha(d['board']) and g['definition_sha256']==sha('power/CHB_INPUT_DEFINITION.json') and g['extractor_sha256']==sha('tools/chb_input_native.py')
N={'1':'WP10_PRECHARGED_PLUS','2':'WP10_CHB_ENABLE','4':'WP10_INPUT_RETURN'}
def signature(data):
 def rnd(x):return round(float(x),6)
 ps=sorted((p['number'],tuple(map(rnd,p['xy_mm'])),tuple(map(rnd,p['size_mm'])),tuple(map(rnd,p['drill_mm'])),p['net'],tuple(p['layers'])) for p in data['pads'] if p['number'])
 ts=sorted((t['net'],t['layer'],tuple(map(rnd,t['start_mm'])),tuple(map(rnd,t['end_mm'])),rnd(t['width_mm'])) for t in data['tracks'])
 wantp=sorted((p['pin'],tuple(rnd(x+100) for x in p['local_xy_mm']),(p['pad_mm'],)*2,(p['drill_mm'],)*2,N[p['pin']],('F.Cu','B.Cu')) for p in d['pads'])
 wantt=sorted((N[t['pin']],layer,tuple(rnd(x+100) for x in t['start_local_xy_mm']),tuple(rnd(x+100) for x in t['end_local_xy_mm']),t['width_mm']) for t in d['routes'] for layer in t['layers'])
 return ps==wantp and ts==wantt
voids=union([disk(*p['xy_mm'],p['drill_mm'][0]/2,-1,3) for p in g['pads']])
def analyze(data):
 layers={};passed=True
 for layer in ['F.Cu','B.Cu']:
  geom={};nets={}
  for n in N.values():
   pads=[p for p in data['pads'] if p['number'] and p['net']==n]
   parts=[disk(*p['xy_mm'],p['size_mm'][0]/2) for p in pads if layer in p['layers']]+[capsule(t) for t in data['tracks'] if t['net']==n and t['layer']==layer]
   if not parts:passed=False;continue
   s=op(BRepAlgoAPI_Cut,union(parts),voids);geom[n]=s
   good=count(s)==1 and bool(BRepCheck_Analyzer(s).IsValid());passed &= good
   nets[n]=dict(solids=count(s),area_mm2=vol(s),passed=good)
  gaps=[]
  for n,m in itertools.combinations(geom,2):
   q=exact(geom[n],geom[m]);good=q['distance_mm']>1e-6 and q['common_volume_mm3']<1e-7;passed &= good;gaps.append(dict(nets=[n,m],**q,passed=good))
  layers[layer]=dict(nets=nets,gaps=gaps)
 return dict(passed=bool(passed and len(layers)==2 and all(len(v['nets'])==3 for v in layers.values())),layers=layers)
baseline=analyze(g);assert baseline['passed'] and signature(g)
faults=[]
def fault(name,x,signature_only=False):
 r=analyze(x) if not signature_only else None;rejected=(not signature(x)) if signature_only else not r['passed'];faults.append(dict(name=name,rejected=rejected,result=r));assert rejected,name
x=copy.deepcopy(g);x['tracks']=[];fault('all_tracks_removed_same_pin_numbers',x)
for pin in ['1','4']:
 x=copy.deepcopy(g)
 for t in x['tracks']:
  if t['net']==N[pin] and t['start_mm'][0]==109:t['end_mm']=[107,t['end_mm'][1]]
 fault('truncated_CAP_'+pin+'_both_layers_count_preserved',x)
x=copy.deepcopy(g)
for t in x['tracks']:
 if t['net']==N['2']:t['net']=N['1']
fault('EN_tracks_wrong_plus_net',x)
for name,end in [('bridge_to_EN',[101.87,107.62]),('zero_area_tangency',[101.87,109.37])]:
 x=copy.deepcopy(g);x['tracks'].append(dict(start_mm=[101.87,117.78],end_mm=end,width_mm=.5,net=N['1'],layer='F.Cu'));fault(name,x)
x=copy.deepcopy(g)
for p in x['pads']:
 if p['number']=='1' and abs(p['xy_mm'][0]-101.87)<1e-6:p['xy_mm'][0]+=1
fault('PIN1_shifted_1mm',x,True)
checks=[]
def ck(n,b,**kw):checks.append(dict(name=n,passed=bool(b),**kw))
ck('eight_pads_ten_tracks_match_full_definition',signature(g))
ck('no_hidden_copper',g['zone_count']==0 and g['copper_drawing_count']==0)
ck('native_finished_thickness',abs(g['board_thickness_mm']-1.6)<1e-9 and abs(sum(g['stackup_mm'].values())-1.6)<1e-9 and g['stackup_mm']['F.Cu']==g['stackup_mm']['B.Cu']==.07)
mount=sorted(tuple(p['xy_mm']) for p in g['pads'] if not p['number'])
ck('two_native_mount_holes',mount==[(101.87,74.6),(101.87,125.4)] and all(p['drill_mm']==[3.4,3.4] for p in g['pads'] if not p['number']))
edges={tuple(sorted([tuple(t['start_mm']),tuple(t['end_mm'])])) for t in g['edges']}
want={tuple(sorted([a,b])) for a,b in [((88,70),(112,70)),((112,70),(112,130)),((112,130),(88,130)),((88,130),(88,70))]}
ck('actual_24x60_outline',edges==want)
ck('all_seven_faults_rejected',len(faults)==7 and all(f['rejected'] for f in faults))
traces=[]
for t in d['routes']:
 L=math.dist(t['start_local_xy_mm'],t['end_local_xy_mm']);R=1.724e-5*L/(t['width_mm']*.07)
 traces.append(dict(pin=t['pin'],length_mm=L,width_mm=t['width_mm'],single_layer_R20_ohm=R,heat_W_at20A=R*400 if t['width_mm']==5.5 else None,heat_W_at2p4A=R*2.4**2 if t['width_mm']==3 else None))
out=dict(schema='WP10_CHB_INPUT_COPPER_V18',passed=all(c['passed'] for c in checks) and baseline['passed'],checks=checks,baseline=baseline,faults=faults,trace_screen=traces,resistance_scope='Uniform single-layer trace only; no parallel-layer sharing credit; excludes pad spreading/barrels/contacts/wires and ripple spectrum. Not ampacity or temperature qualification.',manufacturing_qualified=False,inputs={p:sha(p) for p in ['tools/check_chb_input_copper.py','tools/chb_input_ocp.py','tools/chb_input_native.py','results/CHB_INPUT_NATIVE_V18.json','power/CHB_INPUT_DEFINITION.json',d['board']]})
(A/'results/CHB_INPUT_COPPER_V18.json').write_text(json.dumps(out,indent=2));print(json.dumps(dict(passed=out['passed'],checks=len(checks),faults=len(faults))));assert out['passed']
