"""Same WP10 candidate: physical-pin power pages integrated with the 99-ref parent.

No hardware I/O. All release decisions remain separate from connectivity tests.
"""
from pathlib import Path
import ast, collections, csv, hashlib, itertools, json, math, re, shutil, uuid
from input_passive_definition import PASSIVES
from timer_passive_definition_v24 import TIMING_PASSIVES
from input_passive_footprint import build_footprint
build_footprint()
A=Path(__file__).resolve().parents[1]; D=A.parent; E=A/'ecad'; P=A/'power'
def dump(p,x): p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def csvout(p,rows):
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def q(x): return json.dumps(str(x),ensure_ascii=False)
def uid(x): return str(uuid.uuid5(uuid.NAMESPACE_URL,'wp10-integrated-power-loop:'+x))
ns={'json':json,'re':re}
t=ast.parse((D/'tools/integrate_ecad.py').read_text(encoding='utf-8'))
exec(compile(ast.Module(body=[x for x in t.body if isinstance(x,ast.FunctionDef) and x.name in ['parse','enc','val','children','walk']],type_ignores=[]),'parent_pure_parser','exec'),ns)
parse,enc,val,children,walk=[ns[x] for x in ['parse','enc','val','children','walk']]

# Actual pin identities for the selected devices; project connector pins are
# distinguished from unpublished OEM battery cavities in the interface contract.
parts=collections.OrderedDict()
def part(ref,mpn,pins,source,role,status='SELECTED_CANDIDATE'):
 parts[ref]=dict(mpn=mpn,pins={str(k):v for k,v in pins.items()},source=source,role=role,status=status)
def passive(ref,value,role,source='PROJECT_VALUE_ALLOCATION_MPN_UNBOUND'):
 part(ref,value,{'1':'A','2':'B'},source,role,'VALUE_SELECTED_MPN_UNBOUND' if source.startswith('PROJECT') else 'SELECTED_CANDIDATE')
part('J200','PROJECT_BATTERY_ADAPTER_OUTPUT',{'1':'PROTECTED_PLUS','2':'PROTECTED_RETURN'},'rrc3570_4.pdf D; mc35.pdf body RevB; OEM cavity and Sys Detect UNBOUND','Project adapter pads; not OEM pin numbers','OEM_SIDE_UNBOUND')
passive('F201','30A_DC_FUSE_MPN_UNBOUND','Main branch backup fuse: clearing/I2t unbound')
passive('F202','6A_SLOW_DC_FUSE_MPN_UNBOUND','Independent AUX branch; THN recommendation is not protection coordination')
part('U201','LM5069MM-1',dict(enumerate(['SENSE','VIN','UVLO','OVLO','GND','TIMER','PWR','PGD','OUT','GATE'],1)),'lm5069_rev_g.pdf pp3,5,6,20-24','Latched hot swap, not auto-retry')
part('Q201','IXTH75N10L2',{'1':'G','2':'D','3':'S'},'https://www.littelfuse.com/assetdocs/Littelfuse-Discrete-MOSFETs-N-Channel-Linear-IXT-75N10-Datasheet.PDF?assetguid=EA051E16-AAA9-4983-A975-8D0C07325D72 pp1-2; ADVANCE TECHNICAL INFORMATION','Linear-SOA candidate replacing low-Rds-only selection','ADVANCE_DATASHEET_NOT_RELEASE_QUALIFIED')
passive('R201','WSLP27262L000FEA','2mOhm main sense, PCB Kelvin taps required','wslp2726.pdf 29-Jun-2026 pp1-2')
passive('R202','WSLP2726L2000FEA','0.2mOhm series sense, PCB Kelvin taps required','wslp2726.pdf 29-Jun-2026 pp1-2')
for ref,value,role in [('R203','47.5k_0.1pct_25ppm','UVLO upper'),('R204','5.90k_0.1pct_25ppm','UVLO lower'),('R205','120k_0.1pct_25ppm','OVLO upper'),('R206','10k_0.1pct_25ppm','OVLO lower'),('R207','30.1k_1pct','Power limit'),('C201','1uF_10pct_16V','Fault timer'),('C202','100nF_100V','Input bypass'),('C203','2200uF_20pct_100V_ESR_lt_0.12','CHB input reservoir'),('C204','10uF_50V_polymer','CHB local output'),('C205','1uF_50V_ceramic','CHB local output'),('C206','100nF_100V','Ideal diode VS decoupling'),('C207','100nF_25V','Ideal diode charge pump'),('C208','100nF_100V','Ideal diode input bypass'),('C209','6.8uF_20pct_50V','THN ripple-test external capacitor'),('C210','6.8uF_20pct_50V','THN ripple-test external capacitor')]:passive(ref,value,role)
# Bind selected inputs without renumbering the original hierarchy.
parts['F201'].update(mpn=PASSIVES['F201']['MPN'],source=PASSIVES['F201']['source_url']+' June2025 p2',role='30A backup fuse; L/R and clearing coordination OPEN',status='SELECTED_CANDIDATE_COORDINATION_OPEN',footprint=PASSIVES['F201']['footprint'])
parts['F202'].update(mpn=PASSIVES['F202']['MPN'],source=PASSIVES['F202']['source_url']+' November2025 pp1-6',role='Independent STOP supply 6A slow fuse; inrush, wire and upstream protection coordination OPEN',status='SELECTED_CANDIDATE_COORDINATION_OPEN')
parts['C203'].update(mpn=PASSIVES['C203']['MPN'],pins={'1':'PLUS','2':'MINUS'},source=PASSIVES['C203']['source_url'],role='2200uF 100V polarized; pad1+ pad2-; ripple/temp OPEN',status='SELECTED_CANDIDATE_ENVIRONMENT_OPEN',footprint=PASSIVES['C203']['footprint'])
for ref,v in TIMING_PASSIVES.items():
 parts[ref].update(mpn=v['MPN'],footprint=v['footprint'],status=v['status'],source=v['source_url']+'; '+v['source_revision'])
dump(P/'TIMER_PASSIVE_SELECTION_V24.json',TIMING_PASSIVES)
dump(P/'INPUT_PASSIVE_SELECTION.json',PASSIVES)
passive('D201','SMBJ30A-13-F','Input surge clamp: wiring L and fuse coordination not verified','lm5069_rev_g.pdf p25 reference; actual TVS datasheet pending')
passive('D202','MBR3100','Output negative clamp A=return K=precharged rail','lm5069_rev_g.pdf p25 reference; actual diode datasheet pending')
part('U202','THN 30-2415WIR',{'1':'+VIN','2':'-VIN','3':'REMOTE_OPEN_ON','4':'+VOUT','5':'TRIM_NC','6':'-VOUT'},'thn30wir_20260901.pdf pp2-4,6','Always-on independent isolated STOP supply')
part('U203','CHB500W-24S24N',{'1':'+VIN','2':'NEGATIVE_ENABLE','4':'-VIN','5':'-VOUT','6':'-SENSE','7':'TRIM_NC','8':'+SENSE','9':'+VOUT'},'cincon_chb500w.pdf V12; chb500w_application.pdf V13','360W arm only; AUX is accounted separately')
part('U204','LM74800QDRRRQ1',{'1':'DGATE','2':'A','3':'VSNS','4':'SW','5':'OV','6':'EN_UVLO','7':'GND','8':'HGATE','9':'OUT','10':'VS','11':'CAP','12':'C','EP':'FLOATING_PAD'},'lm7480_q1.pdf RevC pp3-4; EP is project pad ID, not numbered OEM pin','Common-drain reverse blocker; OV grounded, no motor clamp credit')
for r in ['Q202','Q203']:part(r,'CSD19536KTT',{'1':'G','2':'D','3':'S'},'csd19536ktt.pdf RevC May2025 pp1,3','Common-drain N-channel power MOSFET')
part('J201','PROJECT_CHB_ENABLE_DRY_CONTACT',{'1':'CHB_ENABLE','2':'INPUT_RETURN'},'PROJECT connector; external isolated enable driver unimplemented','Open circuit disables CHB; not an automatic startup proof','CONTROL_DRIVER_UNBOUND')
part('J202','PROJECT_HOTSWAP_RESET',{'1':'UVLO','2':'INPUT_RETURN'},'LM5069 RevG reset low; TIMER<0.3V required','Manual reset test pads, no automatic rearm')
part('TP201','PROJECT_PRECHARGE_PGD',{'1':'PGD'},'LM5069 RevG p12','No pullup/no enable credit; PGD can be high below VIN about5V')
part('J203','PROJECT_LOAD_SIDE_BRAKE_PORT',{'1':'ARM_BUS_PLUS','2':'ARM_RETURN'},'PROJECT connector: absolute voltage brake required','Remains with motor when K1 opens; sink not yet fitted','BRAKE_ENERGY_AND_CIRCUIT_OPEN')

groups={
 'BAT_PROTECTED_PLUS':['J200.1','F201.1','F202.1'],
 'INPUT_RETURN':['J200.2','U201.5','R204.2','R206.2','R207.2','C201.2','C202.2','C203.2','D201.1','D202.1','U202.2','U203.4','J201.2','J202.2'],
 'MAIN_FUSED':['F201.2','R201.1','U201.2','R203.1','R205.1','C202.1','D201.2'],
 'SENSE_MID':['R201.2','R202.1'],
 'MAIN_SENSE':['R202.2','U201.1','Q201.2'],
 'MAIN_GATE':['U201.10','Q201.1'],
 'PRECHARGED_PLUS':['Q201.3','U201.9','C203.1','D202.2','U203.1'],
 'HS_UVLO':['U201.3','R203.2','R204.1','J202.1'],
 'HS_OVLO':['U201.4','R205.2','R206.1'],
 'HS_POWER_LIMIT':['U201.7','R207.1'],
 'HS_TIMER':['U201.6','C201.1'],
 'HS_PGD':['U201.8','TP201.1'],
 'AUX_FUSED':['F202.2','U202.1'],
 'STOP_24V':['U202.4','C209.1','C210.1'],
 'ARM_RETURN':['U202.6','C209.2','C210.2','U203.5','U203.6','C204.2','C205.2','U204.5','U204.7','C206.2','C208.2','J203.2'],
 'CHB_ENABLE':['U203.2','J201.1'],
 'CHB_LOCAL_PLUS':['U203.9','U203.8','C204.1','C205.1','Q202.3','U204.2','C208.1'],
 'RB_COMMON_DRAIN':['Q202.2','Q203.2','U204.12','U204.10','U204.3','U204.4','U204.6','C206.1','C207.2'],
 'RB_DGATE':['U204.1','Q202.1'],
 'RB_HGATE':['U204.8','Q203.1'],
 'RB_CAP':['U204.11','C207.1'],
 'RB_OUTPUT_PLUS':['Q203.3','U204.9'],
 'ARM_BUS_PLUS':['J203.1']}
nc={'U202.3','U202.5','U203.7','U204.EP'}
import runpy
startup=runpy.run_path(str(A/'tools/startup_circuit_definition.py'))
startup_refs=startup['add_startup'](part,passive,parts,groups,nc)
# V25 exact selections, same system refs. Does not authorize full-generator execution.
from main_board_selection_v25 import PARTS as MAIN_BOARD_SELECTION_V25
for ref,v in MAIN_BOARD_SELECTION_V25.items():
 parts[ref].update(mpn=v['MPN'],footprint=v['footprint'],status=v['status'],source=v['source_url']+'; '+v['source_revision'])
 if 'pins' in v:parts[ref]['pins']=v['pins']

brake=runpy.run_path(str(A/'tools/brake_circuit_definition.py'))
brake_refs=brake['add_brake'](part,passive,parts,groups,nc)
external_brake_stop={'STOPBOARD.U120.3','STOPBOARD.U106.2'}
pin_net={ep:n for n,eps in groups.items() for ep in eps}
assert len(pin_net)==sum(map(len,groups.values()))
all_new={r+'.'+p for r,v in parts.items() for p in v['pins']}
assert (set(pin_net)-external_brake_stop)|nc==all_new and not set(pin_net)&nc

# The existing 72 wire IDs remain traceable. Retired conductors are explicitly
# inactive and are not used to derive electrical nets or physical cut lengths.
old=list(csv.DictReader((D/'ecad/MASTER_FROM_TO.csv').open(encoding='utf-8-sig')))
rows=[dict(r,active='true') for r in old]
replacements={
 'A01':('J200.1','F201.1','BAT_PROTECTED_PLUS'),
 'A02':('Q203.3','K1.A2(+)','RB_OUTPUT_PLUS'),
 'A03':('K1.A1(-)','J203.1','ARM_BUS_PLUS'),
 'A04':('U203.5','J203.2','ARM_RETURN'),
 'A06':('J200.2','U203.4','INPUT_RETURN'),
 'A07':('J203.1','SEP.PWR','ARM_BUS_PLUS'),
 'A08':('J203.2','SEP.RET','ARM_RETURN'),
 'SC_PWR24':('U202.4','STOPBOARD.J101.3','STOP_24V'),
 'SC_RET':('U202.6','STOPBOARD.J101.4','ARM_RETURN')}
lineage=[]
for r in rows:
 before=dict(r)
 if r['wire_id'] in replacements:
  r['from_endpoint'],r['to_endpoint'],r['signal']=replacements[r['wire_id']]
  r['wire_or_mate']='PROJECT_CONNECTION; contact/MPN/cut length NOT released'
  r['source']='WP10 power/POWER_LOOP_PARTS.json; ecad/POWER_LOOP_PIN_NET.csv'
  r['status']='INTEGRATED_DESIGN_CANDIDATE; dynamic/protection/thermal gates OPEN'
 if r['wire_id'] in ['A11','A12']:
  r['active']='false';r['status']='RETIRED_ODRIVE_RESISTOR_WIRE; no absolute-clamp credit'
 lineage.append(dict(wire_id=r['wire_id'],old_from=before['from_endpoint'],old_to=before['to_endpoint'],new_from=r['from_endpoint'],new_to=r['to_endpoint'],active=r['active'],change='REVISED' if r!=before else 'UNCHANGED'))
assert len(rows)==72 and {r['wire_id'] for r in rows}=={r['wire_id'] for r in old}

# Conductors only: MOSFETs, contactor, converters, fuse and resistors are NOT
# silently unioned as ideal wires. Their terminals remain distinct electrical nets.
class DSU:
 def __init__(self):self.p={}
 def find(self,x):
  self.p.setdefault(x,x)
  if self.p[x]!=x:self.p[x]=self.find(self.p[x])
  return self.p[x]
 def union(self,a,b):self.p[self.find(a)]=self.find(b)
d=DSU()
for eps in groups.values():
 for ep in eps:d.union(eps[0],ep)
for r in rows:
 if r['active']=='true':d.union(r['from_endpoint'],r['to_endpoint'])
stop_pins=list(csv.DictReader((D/'electrical/STOP_PIN_NET_MAP.csv').open(encoding='utf-8-sig')))
sn=collections.defaultdict(list)
for r in stop_pins:sn[r['net']].append('STOPBOARD.'+r['reference']+'.'+r['pin'])
for eps in sn.values():
 for ep in eps:d.union(eps[0],ep)
parent_map=json.loads((D/'ecad/SYSTEM_ENDPOINT_MAP.json').read_text())
net_names={}
for name,eps in groups.items():
 root=d.find(eps[0]);assert root not in net_names or net_names[root]==name,('Unexpected rail short',name,net_names.get(root))
 net_names[root]=name
for ep in sorted(d.p):net_names.setdefault(d.find(ep),'LEGACY_'+str(len(net_names)+1).zfill(3))
def net(ep):return 'WP10_'+net_names[d.find(ep)] if ep in d.p else None
dump(P/'POWER_LOOP_PARTS.json',parts)
csvout(E/'POWER_LOOP_PIN_NET.csv',[dict(reference=ref,pin=p,function=fn,net=net(ref+'.'+p) or 'EXPLICIT_NC',source=x['source']) for ref,x in parts.items() for p,fn in x['pins'].items()])
csvout(E/'MASTER_FROM_TO.csv',rows);csvout(E/'POWER_MASTER_LINEAGE.csv',lineage)

def textobj(s,x,y,key):return parse(f'(text {q(s)} (at {x} {y} 0) (effects (font (size 1.05 1.05)) (justify left)) (uuid {q(uid(key))}))')
def global_label(s,x,y,key):return parse(f'(global_label {q(s)} (shape bidirectional) (at {x} {y} 0) (effects (font (size 0.9 0.9)) (justify left)) (uuid {q(uid(key))}))')
def ptype(ref,p):
 if startup['pin_type'](ref,p):return startup['pin_type'](ref,p)
 if brake['pin_type'](ref,p):return brake['pin_type'](ref,p)
 # The two isolated secondary RETURNS share one intentional reference. They
 # are not independent driven voltage outputs; positive outputs are not tied.
 if (ref,p) in [('U202','6'),('U203','5')]:return 'passive'
 if (ref,p) in [('U202','4'),('U203','9')]:return 'power_out'
 if ref in ['U202','U203'] and p in ['1','2' if ref=='U202' else '4']:return 'power_in'
 if ref=='U201':return {'1':'input','2':'power_in','3':'input','4':'input','5':'power_in','6':'passive','7':'passive','8':'open_collector','9':'input','10':'output'}[p]
 if ref=='U204':return 'no_connect' if p=='EP' else ('output' if p in ['1','8','11'] else 'power_in' if p in ['7','10'] else 'input')
 return 'passive'

# Preserve the 23 parent root references and all 76 STOP symbols. Stale root
# power labels/wires are replaced at their existing pin positions, not overlaid.
root=parse((D/'ecad/wp09_system.kicad_sch').read_text())
rootid=val(children(root,'uuid')[0][1]);name='wp10_system'
for n in walk(root):
 if n and n[0]=='project':n[1]=q(name)
 if n and n[0]=='title':n[1]=q('WP10 integrated power candidate / engineering gates OPEN')
 if n and n[0]=='date':n[1]=q('2026-09-09')
 if n and n[0]=='rev':n[1]=q('POWER_LOOP_1')
for n in list(root):
 if isinstance(n,list) and n and n[0] in ['wire','label','global_label','junction']:root.remove(n)
root_map={}
for s in children(root,'symbol'):
 ref=val(next(x for x in children(s,'property') if x[1]=='"Reference"')[2])
 at=children(s,'at')[0];sx,sy=map(float,at[1:3]);libid=val(children(s,'lib_id')[0][1]);dev=libid.split(':',1)[1]
 lib=next(x for x in children(children(root,'lib_symbols')[0],'symbol') if val(x[1])==libid)
 is_retired=dev in ['PS1','Q1','U1','RB1']
 if is_retired:
  for n in children(s,'dnp'):n[1]='yes'
  next(x for x in children(s,'property') if x[1]=='"Value"')[2]=q(dev+' RETIRED_GSE_OR_OLD_CLAMP')
 for leaf in children(lib,'symbol'):
  for pn in children(leaf,'pin'):
   pin=val(children(pn,'number')[0][1]);pa=children(pn,'at')[0];px=sx+float(pa[1]);py=sy-float(pa[2]);ep=dev+'.'+pin;nn=net(ep)
   if nn is None or is_retired:
    root.append(parse(f'(no_connect (at {px} {py}) (uuid {q(uid(ep+"nc"))}))'))
   else:root.append(global_label(nn,px,py,ep+'global'))
   root_map[ep]=dict(ref=ref,pin=pin,net=nn if not is_retired else None,retired=is_retired)
assert {x['ref'] for x in root_map.values()}=={x['ref'] for x in parent_map.values()}
stop_sheet=children(root,'sheet')[0];stopid=val(children(stop_sheet,'uuid')[0][1])
next(x for x in children(stop_sheet,'property') if x[1]=='"Sheetfile"')[2]=q('wp10_stop_detail.kicad_sch')
children(stop_sheet,'at')[0][1:3]=['25.4','330']
children(stop_sheet,'size')[0][1:3]=['170','16']
for prop in children(stop_sheet,'property'):
 if prop[1] in ['"Sheetname"','"Sheetfile"']:
  children(prop,'at')[0][1:3]=['25.4','329' if prop[1]=='"Sheetname"' else '347']
# Copy original actual STOP source and replace only external net labels.
stop=parse((D/'electrical/wp09_stop_circuit.kicad_sch').read_text())
external_stop={ep.removeprefix('STOPBOARD.') for ep in parent_map if ep.startswith('STOPBOARD.')}
external_stop.update(ep.removeprefix('STOPBOARD.') for ep in external_brake_stop)
stop_globals={r['net']:net('STOPBOARD.'+r['reference']+'.'+r['pin']) for r in stop_pins if r['reference']+'.'+r['pin'] in external_stop}
for n in walk(stop):
 if n and n[0]=='project':
  n[1]=q(name)
  for path in children(n,'path'):path[1]=q('/'+rootid+'/'+stopid)
 if n and n[0]=='label' and val(n[1]) in stop_globals:
  n[0]='global_label';n[1]=q(stop_globals[val(n[1])]);n.insert(2,['shape','bidirectional'])
for s in children(stop,'sheet_instances'):stop.remove(s)
(E/'wp10_stop_detail.kicad_sch').write_text(enc(stop),encoding='utf-8')

all_lib=[];pages=[]
items=list(parts.items())
for pi in range(math.ceil(len(items)/12)):
 pname='wp10_power_'+str(pi+1);pid=uid(pname);sheetid=uid(pname+'_sheet')
 defs=[];objs=[]
 for j,(ref,v) in enumerate(items[pi*12:(pi+1)*12]):
  x=30.48+(j%4)*99.06;y=30.48+(j//4)*68.58;libid='WP10POWER:'+ref;h=(len(v['pins'])+1)*2.54
  pp=''
  for i,(pin,fn) in enumerate(v['pins'].items()):
   py=y+(i+1)*2.54;ep=ref+'.'+pin
   pp+=f'(pin {ptype(ref,pin)} line (at 20.32 {-2.54*(i+1)} 180) (length 5.08) (name {q(fn)} (effects (font (size 0.8 0.8)))) (number {q(pin)} (effects (font (size 0.8 0.8)))))'
   if ep in nc:objs.append(parse(f'(no_connect (at {x+20.32} {py}) (uuid {q(uid(ep+"nc"))}))'))
   else:objs.append(global_label(net(ep),x+20.32,py,ep+'global'))
  definition=f'(symbol {q(libid)} (pin_names (offset 0.5)) (in_bom yes) (on_board yes) (property "Reference" {q(ref[0])} (at 0 2.54 0) (effects (font (size 1 1)))) (property "Value" {q(v["mpn"])} (at 0 0 0) (effects (font (size 1 1)))) (symbol {q(ref+"_0_1")} (rectangle (start -15.24 0) (end 15.24 {-h}) (stroke (width 0.254) (type default)) (fill (type background)))) (symbol {q(ref+"_1_1")} {pp}))'
  defs.append(definition);all_lib.append(definition.replace(q(libid),q(ref),1))
  objs.append(parse(f'(symbol (lib_id {q(libid)}) (at {x} {y} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {q(uid(ref+"instance"))}) (property "Reference" {q(ref)} (at {x} {y-6} 0) (effects (font (size 1 1)))) (property "Value" {q(v["mpn"])} (at {x} {y-3} 0) (effects (font (size 0.85 0.85)))) '+''.join(f'(pin {q(p)} (uuid {q(uid(ref+"pin"+p))}))' for p in v['pins'])+f'(instances (project {q(name)} (path {q("/"+rootid+"/"+sheetid)} (reference {q(ref)}) (unit 1)))))'))
  if v.get('footprint'):
   objs[-1].append(parse(f'(property "Footprint" {q(v["footprint"])} (at {x} {y} 0) (effects (font (size 1 1)) hide))'))
  objs.append(textobj(v['role'][:94],x-15, y+min(h+5,52),ref+'role'))
 sch=parse(f'(kicad_sch (version 20250114) (generator "eeschema") (generator_version "10.0") (uuid {q(pid)}) (paper "A3") (title_block (title {q("WP10 physical power pins "+str(pi+1)+" / NO energization release")}) (date "2026-09-09") (rev "LOOP1")) (lib_symbols {"".join(defs)}))')
 sch.extend(objs);sch.append(textobj('F201/C203 selected; protection coordination, startup dynamics, ripple and thermal qualification remain OPEN.',10,270,pname+'note'))
 (E/(pname+'.kicad_sch')).write_text(enc(sch),encoding='utf-8');pages.append(pname)
 sx=25.4+189.6*((pi+1)%2);sy=330+35*((pi+1)//2)
 root.append(parse(f'(sheet (at {sx} {sy}) (size 170 16) (stroke (width 0) (type default)) (fill (color 0 0 0 0)) (uuid {q(sheetid)}) (property "Sheetname" {q("Power detail "+str(pi+1))} (at {sx} {sy-1} 0) (effects (font (size 1.27 1.27)) (justify left bottom))) (property "Sheetfile" {q(pname+".kicad_sch")} (at {sx} {sy+17} 0) (effects (font (size 1.27 1.27)) (justify left top))) (instances (project {q(name)} (path {q("/"+rootid)} (page {q(str(pi+3))})))))'))
children(root,'paper')[0][1]=q('A1')
root.append(textobj('PS1/RSP, old Q1, ODrive clamp and RB1 are retained as DNP lineage. Original 99 references are preserved.',25.4,365+35*(len(pages)//2),'retired_note'))
# Preserve the MCP-created declaration page through every source regeneration.
# It adds no physical part, wire or changed pin type to the inherited design.
erc_contract=json.loads((P/'ERC_SOURCE_DECLARATIONS.json').read_text(encoding='utf-8'))
assert all(sha(A/p)==h for p,h in erc_contract['source_bindings'].items())
root.append(json.loads((P/'erc_sources/root_sheet.json').read_text(encoding='utf-8')))
shutil.copy2(P/'erc_sources/wp10_power_declarations.kicad_sch',E/'wp10_power_declarations.kicad_sch')
(E/'wp10_system.kicad_sch').write_text(enc(root),encoding='utf-8')
(E/'wp10_system.kicad_pro').write_text('{}',encoding='utf-8')
(E/'WP10POWER.kicad_sym').write_text('(kicad_symbol_lib (version 20250114) (generator "kicad_symbol_editor") '+''.join(all_lib)+')',encoding='utf-8')
shutil.copy2(D/'ecad/WP09.kicad_sym',E/'WP09.kicad_sym');shutil.copy2(D/'electrical/WP09STOP.kicad_sym',E/'WP09STOP.kicad_sym')
(E/'sym-lib-table').write_text('(sym_lib_table (version 7) '+''.join(f'(lib (name "{l}") (type "KiCad") (uri "'+chr(36)+f'{{KIPRJMOD}}/{l}.kicad_sym") (options "") (descr "Same WP10 candidate"))' for l in ['WP09','WP09STOP','WP10POWER','power'])+')',encoding='utf-8')
dump(E/'SYSTEM_ENDPOINT_MAP.json',root_map)
dump(E/'POWER_LOOP_INTEGRATION.json',dict(parent=str(D/'ecad/wp09_system.kicad_sch'),parent_sha256=sha(D/'ecad/wp09_system.kicad_sch'),preserved_parent_refs=99,added_refs=len(parts),original_wire_ids_preserved=72,active_original_wire_rows=sum(r['active']=='true' for r in rows),power_pages=pages,stop_internal_source_unchanged_except_external_net_labels=True,stop_globals=stop_globals,input_return=net('U203.4'),output_return=net('U203.5'),independent_aux=True,whole_power_design_closed=False,charging_parallel_load_supported=None,absolute_sink_circuit_integrated=True,brake_sink_fitted=False))
dump(P/'LOAD_SIDE_BRAKE_DEFINITION.json',dict(schema='WP10_LOAD_SIDE_BRAKE_DEFINITION_V1',refs=brake_refs,parameters=brake['PARAMS'],new_stop_globals=sorted(external_brake_stop),absolute_sink_circuit_integrated=True,physical_hardware_installed=False,whole_brake_function_verified=False))
dump(P/'STARTUP_CIRCUIT_DEFINITION.json',dict(schema='WP10_PRIMARY_STARTUP_V1',refs=startup_refs,primary_reference='INPUT_RETURN',bias_source='PRECHARGED_PLUS',sense_source='MAIN_FUSED',PG_source='U201.8',K1_not_bypassed=True,STOP_domain_connection=False,manual_enable_jumper_allowed=False,physical_startup_verified=False))

# Reproducible corner screening; never mislabeled as a measured or OEM-wide guarantee.
Rs=.0022;rs_tol=(1+.01)*(1+75e-6*100)-1;kelvin_error=.00001
rsmin=Rs*(1-rs_tol)-kelvin_error;rsmax=Rs*(1+rs_tol)+kelvin_error
imin=.0485/rsmax;imax=.0615/rsmin
uv=[];uvrise=[];ov=[]
r_tol=(1+.001)*(1+25e-6*100)-1
for th,rh,rl,bias in itertools.product([2.45,2.55],[47500*(1-r_tol),47500*(1+r_tol)],[5900*(1-r_tol),5900*(1+r_tol)],[-1e-6,1e-6]):
 threshold=th*(1+rh/rl)+bias*rh
 uv.append(threshold)
 for ihys in [12e-6,30e-6]:uvrise.append(threshold+ihys*rh)
for th,rh,rl,bias in itertools.product([2.4,2.6],[120000*(1-r_tol),120000*(1+r_tol)],[10000*(1-r_tol),10000*(1+r_tol)],[-1e-6,1e-6]):ov.append(th*(1+rh/rl)+bias*rh)
scenarios=[]
for vb,eta,auxeta,rpath,rpre in itertools.product([min(uv),22.,25.2,29.4],[.85,.9],[.8,.9],[.04,.06],[.005,.02]):
 disc=vb*vb-4*rpath*360/eta
 im=(vb-math.sqrt(disc))/(2*rpath) if disc>=0 else None
 ia=16.8/(vb*auxeta)
 vfused=vb-im*rpre if im else None
 # The initial UVLO check has CHB and pass FET OFF; 3mA is a declared
 # controller/divider allowance, not the motor input current.
 vcold=vb-.003*rpre
 cold='ALL_SCREEN_CORNERS_ON' if vcold>=max(uvrise) else 'ALL_SCREEN_CORNERS_OFF' if vcold<min(uvrise) else 'CORNER_DEPENDENT'
 held='ALL_SCREEN_CORNERS_ON' if vfused is not None and vfused>=max(uv) else 'ALL_SCREEN_CORNERS_OFF' if vfused is not None and vfused<min(uv) else 'CORNER_DEPENDENT'
 resistance_feasible=rpath-rpre>=.021+.0022
 usable=bool(im is not None and held=='ALL_SCREEN_CORNERS_ON' and cold=='ALL_SCREEN_CORNERS_ON' and resistance_feasible)
 scenarios.append(dict(battery_loaded_V=vb,main_eta_assumed=eta,aux_eta_assumed=auxeta,series_R_ohm_assumed=rpath,resistance_before_MAIN_FUSED_ohm_assumed=rpre,resistance_after_MAIN_FUSED_ohm_assumed=rpath-rpre,resistance_allocation_covers_25C_max_Q201_and_nominal_shunt_only=resistance_feasible,initial_UVLO_detect_V=vcold,initial_cold_start_screen=cold,running_UVLO_detect_V=vfused,held_ON_screen=held,startup_through_inrush_verified=False,main_input_A_assuming_already_on=im,aux_input_A=ia,total_battery_A_assuming_already_on=(im+ia) if im else None,raw_current_balance_margin_A=(imin-im) if im else None,available_current_margin_after_UVLO_screen_A=(imin-im) if usable else None,series_heat_W_assuming_already_on=(im*im*rpath) if im else None,source_guaranteed=False))
pwr_nom=30100/(1.30e5*Rs)+.00118*29.4/Rs
# 19/25..31/25 is a sensitivity from the 48V test row, not a guarantee at 29.4V.
pmin=pwr_nom*.76;pmax=pwr_nom*1.24
c203_max=PASSIVES['C203']['C_nominal_F']*(1+PASSIVES['C203']['tolerance_fraction'])
ts=c203_max/2*(29.4**2/pmin+pmin/imin**2)
tmin=1e-6*.9*3.76/120e-6;tmax=1e-6*1.1*4.16/51e-6
calc=dict(schema='WP10_POWER_LOOP_CORNER_SCREEN_V1',scope='CONDITIONAL_ENGINEERING_SCREEN_NOT_HARDWARE_PASS',arm_output_W=360.,aux_output_W=16.8,coil_W=6.8,aux_remaining_allocation_W=10.,no_double_count=True,parent_376_8_W_shared_rail_retired=True,battery_revision_locked='D',new_E_is_separate_not_mixed=True,Rs_nominal_ohm=Rs,Rs_including_TCR_and_Kelvin_allocation_ohm=[rsmin,rsmax],Rs_initial_tolerance=.01,Rs_component_TCR_per_K=75e-6,Rs_deltaT_K=100,Rs_Kelvin_error_allocation_ohm=kelvin_error,LM5069_VCL_test_scope='VIN48V, TJ-40..125C; transfer to operating VIN remains verification responsibility',current_limit_screen_A=[imin,imax],UVLO_falling_screen_V=[min(uv),max(uv)],OVLO_rising_screen_V=[min(ov),max(ov)],UVLO_bias_scope='1uA table at48V used as sensitivity; resistor allocation includes0.1%+25ppm/K*100K',scenarios=scenarios,PMM_contact_counterexample=dict(total_A=376.8/(22*.9),contact_R_mOhm=[10,15],contact_A=[376.8/(22*.9)*15/25,376.8/(22*.9)*10/25],per_contact_rating_A=10),main_latched_limit_plus_aux_normal_screen_A=imax+16.8/(min(uv)*.8)+.02,normal_aux_margin_is_not_fault_current_guarantee=True,precharge=dict(Cmax_F=c203_max,energy_J=.5*c203_max*29.4**2,power_limit_nominal_W=pwr_nom,power_limit_sensitivity_W=[pmin,pmax],startup_typical_formula_with_sensitivity_s=ts,fault_timer_spec_corner_s=[tmin,tmax],one_point_IXTH_SOA_source=dict(VDS_V=80,ID_A=3,case_C=75,pulse_s=5,status='ADVANCE_TECHNICAL_INFORMATION; not a complete SOA trajectory proof'),CSD_reference_10ms_does_not_cover_max_fault_time=True,CHB_must_stay_disabled_during_precharge=True,automatic_enable_supervisor_implemented=False,SOA_full_trajectory_verified=False),independent_aux=dict(MPN='THN 30-2415WIR',static_screen_0_50C_V=[23.544,24.456],old_STOP_contract_V=[23.04,24.96],residual_dynamic_and_wiring_margin_V=.504,output_external_caps_nominal_uF=13.6,external_caps_max_uF=16.32,load_cap_limit_uF=375,unknown_internal_STOP_input_capacitance_uF=None,ripple_max_Vpp=None,transient_deviation_max_V=None,dynamic_pass=False),regen=dict(load_side_port='J203',input_loss_still_requires_absolute_clamp=True,capacitor_800uF_24_to_26V_energy_J=.5*.0008*(26**2-24**2),example_50J_0_2s_W=250,example_is_not_arm_energy_bound=True,energy_bound_J=None,absorber_fitted=False),release=False)
# Keep the old scalar for lineage, but never label it a startup upper bound.
# V23 verifies the variable-power regulation prefix and TIMER charge separately.
calc['precharge'].update(
    startup_estimate_scope='LEGACY_IDEAL_FIXED_POWER_DIAGNOSTIC_NOT_MAXIMUM_TIME',
    maximum_startup_time_verified_s=None,
    reduced_transient_definition='power/HOTSWAP_TRANSIENT_DEFINITION_V24.json',
    reduced_transient_calculations='power/HOTSWAP_TRANSIENT_CALCULATIONS_V24.json',
    timer_passive_selection='power/TIMER_PASSIVE_SELECTION_V24.json',
    timer_passive_calculations='power/TIMER_PASSIVE_CALCULATIONS_V24.json',
    fault_timer_corner_scope='0.9..1.1uF effective-C requirement; no full-temperature/life proof',
    transient_evidence_requires_source_hash_match=True,
    hot_short_fast_breaker_is_not_permanent_isolation=True,
    fault_timer_retains_charge_between_short_pulses=True)
calc['UVLO_bias_scope']='1uA48V sensitivity; selected0.1pct25ppm and100K multiplicative envelope, life/thermal unverified'
calc['Rs_tolerance_combination']='symmetric multiplicative initial1pct and75ppm/K100K envelope, plus Kelvin allocation'
dump(P/'POWER_LOOP_CALCULATIONS.json',calc)
legacy_budget=json.loads((P/'POWER_BUDGET_SCREEN.json').read_text())
legacy_budget['status']='SUPERSEDED_SHARED_RAIL_SCREEN_NOT_ACTIVE_BUDGET'
legacy_budget['active_budget']='power/POWER_LOOP_CALCULATIONS.json'
legacy_budget['reason']='360W moved to CHB;16.8W moved to independent THN. Do not add AUX twice.'
dump(P/'POWER_BUDGET_SCREEN.json',legacy_budget)
calc['UVLO_rising_screen_V']=[min(uvrise),max(uvrise)]
calc['precharge']['automatic_enable_supervisor_implemented']=True
calc['precharge']['automatic_enable_function_verified']=False
calc['precharge']['startup_source']='tools/startup_circuit_definition.py'
calc['precharge']['qualification_sense']='MAIN_FUSED plus PGD; not charged capacitor alone'
calc['UVLO_sensing_node']='MAIN_FUSED, after F201; not the battery connector'
calc['cold_start_and_hold_logic_are_separate']=True
calc['rejected_path_scenario_ohm']=dict(value=.02,reason='Less than selected Q201 25C maximum Rds_on 0.021 plus nominal shunt0.0022 even before fuse/wire')
calc['review_counterexamples_fixed']=['PLR-01: UVLO rising/holding corners and sense-node drop','PLR-02: MC35 body RevB','ROOT-03: 0.02ohm whole path inconsistent with selected linear MOSFET']
dump(P/'POWER_LOOP_CALCULATIONS.json',calc)
selection=json.loads((P/'POWER_CHAIN_SELECTION.json').read_text())
selection['status']='INTEGRATED_POWER_CANDIDATE_WITH_EXPLICIT_OPEN_ENGINEERING_GATES'
selection['manager']['active_main_power_path']=False
selection['manager']['proposed_charger_only_external_parallel_load_supported']=None
selection['manager']['proposed_charger_only_status']='UNCONFIRMED_NOT_CONNECTED_IN_NATIVE_CIRCUIT'
selection['independent_aux']=calc['independent_aux']
selection['integration']['old_D_99_ref_system_unchanged']=True
selection['integration']['derived_A_system']='ecad/wp10_system.kicad_sch'
selection['integration']['derived_system_includes_original_99_refs']=True
selection['integration']['new_source_pin_pages_integrated']=True
selection['known_blockers']=['Battery D Sys Detect and protected-terminal connector binding absent; E revision retained separately','PMM charger-only parallel-load wiring not manufacturer confirmed; charging source and mode control unimplemented','F201/C203 MPNs selected; fuse L/R and clearing, C203 ripple/temperature, startup/SOA and efficiency qualification unverified','Independent THN static screen fits STOP; dynamic amplitude and STOP internal rail stability remain UNKNOWN','LM74800 and absolute brake circuit integrated; clamp timing/mission energy/PCB switching and thermal capacity unverified','Automatic isolated CHB enable/latched reset supervisor not implemented; default open disables CHB','Local TIM designed; radiator, battery/PMM retention and full873 integration remain open']
dump(P/'POWER_CHAIN_SELECTION.json',selection)
selection['known_blockers']=[s.replace('Automatic isolated CHB enable/latched reset supervisor not implemented; default open disables CHB','Primary-side automatic CHB enable circuit implemented; brown-ramp, PGD open-wire, response and latched reset verification remain open') for s in selection['known_blockers']]
dump(P/'POWER_CHAIN_SELECTION.json',selection)
bom=list(csv.DictReader((P/'SELECTED_BOM.csv').open(encoding='utf-8-sig')))
bom=[r for r in bom if r['role'].split(':',1)[0] not in parts]
for r in bom:
 if r['MPN']=='RRC-PMM35':r['role']='proposed charger only, not connected';r['status']='PARALLEL_LOAD_INTERFACE_UNCONFIRMED'
for ref,v in parts.items():
 if ref=='U203':continue
 bom.append(dict(role=ref+': '+v['role'],manufacturer=TIMING_PASSIVES.get(ref,PASSIVES.get(ref,{})).get('manufacturer','see source'),MPN=v['mpn'],quantity=1,status=v['status'],source=v['source']))
csvout(P/'SELECTED_BOM.csv',bom)
dump(P/'BATTERY_REVISION_CONFLICT.json',dict(active_revision='D',D=dict(V=25.2,Ah=15.99,Wh=407.43,charge_field_A=8,IP='IP54',sha256=sha(A/'sources/rrc3570_4.pdf')),E=dict(V=25.48,Ah=16.,Wh=408,standard_charge_A=8,max_charge_A=16,IP='IP65',sha256=sha(A/'sources/rrc3570_4_E.pdf')),no_as_built_revision_claim=True))
print(json.dumps(dict(parent_refs=99,new_refs=len(parts),native_pages=3+len(pages),declaration_pages=1,nonphysical_declarations=7,wire_ids_preserved=len(rows),conditional_current_limit_A=[imin,imax],whole_design_closed=False)))
