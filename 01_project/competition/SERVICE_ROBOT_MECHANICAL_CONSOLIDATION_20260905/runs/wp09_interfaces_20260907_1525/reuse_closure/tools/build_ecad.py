"""Native KiCad candidate from explicit endpoint contracts. No physical I/O."""
from pathlib import Path
import csv,json,re,uuid,shutil,hashlib,collections
N=Path(__file__).resolve().parents[1];E=N/'ecad';F=N.parent/'functional_closure'
def uid(s):return str(uuid.uuid5(uuid.NAMESPACE_URL,'wp09-reuse:'+s))
def q(s):return json.dumps(str(s),ensure_ascii=False)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
def csvout(p,rows):
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
old=list(csv.DictReader((F/'ecad/FUNCTIONAL_FROM_TO.csv').open(encoding='utf-8-sig')))
rows=[];lineage=[]
for r in old:
 k=r['wire_id'];a=r['from_device']+'.'+r['from_pin'];b=r['to_device']+'.'+r['to_pin'];note=r['design_status']
 if k=='A05':
  lineage.append(dict(old_id=k,current_id='A04',change='RETURN_CONTACT_REMOVED; consolidated direct return'));continue
 if k=='A02':b='K1.A2(+)';note='GX11CAB polarized main contact input'
 if k=='A03':a='K1.A1(-)';note='GX11CAB main output; stopping hardware remains unbound'
 if k=='A04':b='U1.IN-';note='CONTINUOUS_RETURN; not galvanic isolation'
 if k.startswith('S0'):
  r['wire_or_mate']=f'RS422_GSE_SPLICE_BOARD A{k[-1]}.1 to TP{k[-1]}.1 to B{k[-1]}.1; original FTDI color-ended tails'
  note+='; DERIVED_GSE_SPLICE_PCB_INLINE; see RS422_PAD_MAP'
 if k in ['L01','L02']:
  r['wire_or_mate']=r['wire_or_mate'].replace('10.00-S','03.00-S');note='GROUND_P1_ONLY; hot loop<=180mOhm; source3.29..3.32V +/-20mV required'
 rows.append(dict(wire_id=k,from_endpoint=a,to_endpoint=b,signal=r['net'],wire_or_mate=r['wire_or_mate'],status=note,source=(r['source']+'; GX11 Rev6 2015-10-23 p3-4' if k in ['A02','A03'] else r['source']),build_approved=False,physical_test='NOT_EXECUTED',cut_length_mm=''))
 lineage.append(dict(old_id=k,current_id=k,change='REVISED' if k in ['A02','A03','A04','L01','L02','S01','S02','S03','S04','S05'] else 'RETAINED'))
p=json.loads((N/'power/POWER_ENDPOINT_CONTRACT.json').read_text(encoding='utf8'));excluded=[]
existing={(r['from_endpoint'],r['to_endpoint']) for r in rows}
for r in p['endpoints']:
 a=r['from_endpoint'].replace('PDU.X2.','PDU.').replace('A3200.','OBC.');b=r['to_endpoint'].replace('PDU.X2.','PDU.').replace('A3200.','OBC.')
 if (a,b) in existing:continue
 if b=='NC' or '.' not in a or '.' not in b or r['status'].startswith('REQUIREMENT'):
  excluded.append(r);continue
 rows.append(dict(wire_id=r['id'],from_endpoint=a,to_endpoint=b,signal=r['signal'],wire_or_mate='COTS external interface / pin-defined requirement; no cut length',status=r['status']+'; '+r['note'],source=r['source'],build_approved=False,physical_test='NOT_EXECUTED',cut_length_mm=''))
 existing.add((a,b))
csvout(E/'MASTER_FROM_TO.csv',rows);csvout(E/'LINEAGE_23.csv',lineage);dump(E/'EXCLUDED_REQUIREMENTS_AND_NC.json',excluded)

class DSU:
 def __init__(self):self.p={}
 def find(self,x):
  self.p.setdefault(x,x)
  if self.p[x]!=x:self.p[x]=self.find(self.p[x])
  return self.p[x]
 def union(self,a,b):self.p[self.find(a)]=self.find(b)
def graph(rows):
 d=DSU()
 for r in rows:d.union(r['from_endpoint'],r['to_endpoint'])
 groups=collections.defaultdict(list)
 for x in sorted(d.p):groups[d.find(x)].append(x)
 return {x:'W'+str(i+1).zfill(3) for i,g in enumerate(groups.values()) for x in g}
nets=graph(rows)

def pin_type(ep):
 if ep in ['PS1.TB2.4','PDU.TFM.9','BPX.PBAT2.5']:return 'power_out'
 if ep in ['PS1.TB2.1','PDU.TFM.10','BPX.PBAT2.1']:return 'power_out'
 if ep in ['OBC.P1.2','OBC.P1.1','U1.IN+','U1.IN-']:return 'power_in'
 if ep.startswith('RS_'):
  c=ep.split('.')[-1]
  return 'output' if c in ['orange','red'] else ('input' if c in ['yellow','white'] else 'passive')
 if ep.endswith(('I2C_SCL','I2C_SDA')):return 'bidirectional'
 return 'passive' # External connector/contact pin; unknown COTS internals not invented.
def symbol_def(name,pins,types,ref='U'):
 h=max(7.62,(len(pins)+1)*2.54);x=15.24
 pins_s=''.join(f'(pin {t} line (at {x+5.08} {-2.54*(i+1)} 180) (length 5.08) (name {q(p)} (effects (font (size 1.0 1.0)))) (number {q(p)} (effects (font (size 1.0 1.0)))))' for i,(p,t) in enumerate(zip(pins,types)))
 return f'(symbol {q(name)} (pin_names (offset 0.5)) (in_bom yes) (on_board no) (property "Reference" {q(ref)} (at 0 2.54 0) (effects (font (size 1.27 1.27)))) (property "Value" {q(name.split(":")[-1])} (at 0 0 0) (effects (font (size 1.0 1.0)))) (symbol {q(name.split(":")[-1]+"_0_1")} (rectangle (start -15.24 0) (end {x} {-h}) (stroke (width 0.254) (type default)) (fill (type background)))) (symbol {q(name.split(":")[-1]+"_1_1")} {pins_s}))'

def schematic(name,modules,endpoint_nets,subtitle,paper='A1'):
 root=uid(name);defs=[];placed=[];objects=[];mapping={};all_library=[]
 for j,(dev,pins) in enumerate(modules.items()):
  ref='U'+str(j+1);lib='WP09:'+dev;types=[pin_type(dev+'.'+p) for p in pins];definition=symbol_def(lib,pins,types);defs.append(definition);all_library.append(definition.replace(q(lib),q(dev),1))
  x=30.48+(j%6)*91.44;y=30.48+(j//6)*88.9;ins=uid(name+dev)
  placed.append(f'(symbol (lib_id {q(lib)}) (at {x} {y} 0) (unit 1) (in_bom yes) (on_board no) (dnp no) (uuid {q(ins)}) (property "Reference" {q(ref)} (at {x} {y-6} 0) (effects (font (size 1.27 1.27)))) (property "Value" {q(dev)} (at {x} {y-3} 0) (effects (font (size 1.27 1.27)))) '+''.join(f'(pin {q(p)} (uuid {q(uid(name+dev+p))}))' for p in pins)+f'(instances (project {q(name)} (path {q("/"+root)} (reference {q(ref)}) (unit 1)))))')
  for i,pin in enumerate(pins):
   ep=dev+'.'+pin;net=endpoint_nets[ep];px=x+20.32;py=y+2.54*(i+1);lx=px+7.62
   objects.append(f'(wire (pts (xy {px} {py}) (xy {lx} {py})) (stroke (width 0) (type default)) (uuid {q(uid(name+ep+"wire"))})) (label {q(net)} (at {lx} {py} 0) (effects (font (size 1.0 1.0)) (justify left bottom)) (uuid {q(uid(name+ep+"label"))}))')
   mapping[ep]=dict(ref=ref,pin=pin,net=net,electrical_type=types[i])
  objects.append(f'(text {q("Boundary / "+dev)} (at {x+25} {y-10} 0) (effects (font (size 1 1)) (justify left)) (uuid {q(uid(name+dev+"text"))}))')
 text=f'(kicad_sch (version 20250114) (generator "eeschema") (generator_version "10.0") (uuid {q(root)}) (paper {q(paper)}) (title_block (title {q(subtitle)}) (date "2026-09-07") (rev "R1 CONDITIONAL CANDIDATE")) (lib_symbols {"".join(defs)}) {"".join(objects)} {"".join(placed)} (sheet_instances (path "/" (page "1"))))'
 (E/(name+'.kicad_sch')).write_text(text,encoding='utf8');dump(E/(name+'_ENDPOINT_MAP.json'),mapping)
 (E/'WP09.kicad_sym').write_text('(kicad_symbol_lib (version 20250114) (generator "kicad_symbol_editor") '+''.join(all_library)+')',encoding='utf8')
 return mapping
mods=collections.OrderedDict()
for ep in sorted(nets):
 dev,pin=ep.split('.',1);mods.setdefault(dev,[]).append(pin)
mapping=schematic('wp09_system',mods,nets,'WP09 system wiring / logical OEM pins are UNBOUND / no manufacture credit','A2')
(E/'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "WP09") (type "KiCad") (uri "${KIPRJMOD}/WP09.kicad_sym") (options "") (descr "Project external boundary symbols")))',encoding='utf8')
(E/'wp09_system.kicad_pro').write_text('{}',encoding='utf8')
dump(E/'ECAD_BUILD_INPUT.json',dict(rows=len(rows),old_rows_accounted=len(lineage),modules=len(mods),endpoints=len(nets),nets=len(set(nets.values())),main_identity='SYSTEM_HARNESS_SCHEMATIC; logical DM/OEM and control endpoints NOT physical pins',all_build_approved=False,power_input_sha256=sha(N/'power/POWER_ENDPOINT_CONTRACT.json'),old_from_to_sha256=sha(F/'ecad/FUNCTIONAL_FROM_TO.csv')))

# Derived ground-only RS422 splice/test board. Electrical function follows S01..S05.
# Larger solder pads are new responsibility; probe footprints are exact OreSat geometry.
src=N/'sources/oresat-kicad/oresat-footprints/oresat-misc.pretty/TestPoint-MinTH.kicad_mod'
libdir=E/'wp09_reuse.pretty';libdir.mkdir(exist_ok=True)
shutil.copy2(src,libdir/src.name)
# Only derivative silkscreen reference readability changes; copper/drill unchanged.
pp=libdir/src.name;pp.write_text(pp.read_text(encoding='utf8').replace('(size 0.56 0.56)','(size 1 1)').replace('(at 0 1.3 0)','(at 0 2.0 0)'),encoding='utf8')
for nm,size,drill in [('WirePad_GSE',2.5,1.2)]:
 (libdir/(nm+'.kicad_mod')).write_text(f'(footprint {q(nm)} (version 20241229) (generator "pcbnew") (layer "F.Cu") (attr through_hole) (pad "1" thru_hole circle (at 0 0) (size {size} {size}) (drill {drill}) (layers "*.Cu" "*.Mask")))',encoding='utf8')
(E/'fp-lib-table').write_text('(fp_lib_table (version 7) (lib (name "wp09_reuse") (type "KiCad") (uri "${KIPRJMOD}/wp09_reuse.pretty") (options "") (descr "OreSat test point plus project solder pad")))',encoding='utf8')
name='rs422_gse_splice';root=uid(name);defs=[];placements=[];objects=[];fps=[];tracks=[];padmap=[]
sd='(symbol "WP09:Pad" (pin_names (offset 0)) (in_bom no) (on_board yes) (property "Reference" "TP" (at 0 2.54 0) (effects (font (size 1 1)))) (property "Value" "Pad" (at 0 0 0) (effects (font (size 1 1)))) (symbol "Pad_0_1" (circle (center 0 0) (radius 1) (stroke (width 0.254) (type default)) (fill (type none)))) (symbol "Pad_1_1" (pin passive line (at -2.54 0 0) (length 2.54) (name "PAD" (effects (font (size 1 1)))) (number "1" (effects (font (size 1 1)))))))'
defs.append(sd)
with (E/'WP09.kicad_sym').open('r+',encoding='utf8') as f:
 s=f.read().rstrip();f.seek(0);f.write(s[:-1]+sd.replace('"WP09:Pad"','"Pad"',1)+')');f.truncate()
paircolors=[('orange','yellow'),('red','white'),('yellow','orange'),('white','red'),('black','black')]
for i,(ca,cb) in enumerate(paircolors):
 net='RS_LOOP_'+str(i+1);y=55+i*5;sy=45.72+i*25.4
 for j,(prefix,x,sx) in enumerate([('A',55,50.8),('TP',70,101.6),('B',85,152.4)]):
  ref=prefix+str(i+1);v=ca if prefix=='A' else cb if prefix=='B' else net;kind='TestPoint-MinTH' if prefix=='TP' else 'WirePad_GSE';ins=uid(name+ref)
  placements.append(f'(symbol (lib_id "WP09:Pad") (at {sx} {sy} 0) (unit 1) (in_bom no) (on_board yes) (dnp no) (uuid {q(ins)}) (property "Reference" {q(ref)} (at {sx} {sy-4} 0) (effects (font (size 1.27 1.27)))) (property "Value" {q(v)} (at {sx} {sy+4} 0) (effects (font (size 1 1)))) (property "Footprint" {q("wp09_reuse:"+kind)} (at {sx} {sy} 0) (effects (font (size 1 1)) (hide yes))) (pin "1" (uuid {q(uid(ref+"pad"))})) (instances (project {q(name)} (path {q("/"+root)} (reference {q(ref)}) (unit 1)))))')
  objects.append(f'(wire (pts (xy {sx-2.54} {sy}) (xy {sx-10.16} {sy})) (stroke (width 0) (type default)) (uuid {q(uid(ref+"w"))})) (label {q(net)} (at {sx-10.16} {sy} 0) (effects (font (size 1 1)) (justify left bottom)) (uuid {q(uid(ref+"l"))}))')
  fp=(libdir/(kind+'.kicad_mod')).read_text(encoding='utf8')
  fp=re.sub(r'\(footprint\s+"[^"]+"',f'(footprint "wp09_reuse:{kind}" (at {x} {y}) (path "/{root}/{ins}") (uuid "{uid(ref+"fp")}")',fp,count=1)
  fp=re.sub(r'\(uuid "[^"]+"\)',lambda m:'(uuid "'+uid(ref+m.group())+'")',fp)
  fp=re.sub(r'\(property "Reference" "[^"]+"',f'(property "Reference" "{ref}"',fp)
  if '(property "Reference"' not in fp:fp=fp[:-1]+f'(property "Reference" "{ref}" (at 0 -2 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))'+')'
  fp=fp.replace('(attr through_hole)','(attr through_hole exclude_from_bom)')
  fp=re.sub(r'\(property "Value" "[^"]+"',f'(property "Value" {q(v)}',fp)
  if '(property "Value"' not in fp:fp=fp[:-1]+f'(property "Value" {q(v)} (at 0 0 0) (layer "F.Fab") (hide yes) (effects (font (size 1 1))))'+')'
  fp=re.sub(r'\(property "Description" "[^"]+"','(property "Description" ""',fp)
  fp=fp.replace('(pad "1" thru_hole circle',f'(pad "1" thru_hole circle (net {i+1} "/{net}")')
  fps.append(fp);padmap.append(dict(reference=ref,pin='1',x_mm=x,y_mm=y,net=net,from_to='S0'+str(i+1),external_wire_color=v,footprint=kind))
 for xa,xb in [(55,70),(70,85)]:tracks.append(f'(segment (start {xa} {y}) (end {xb} {y}) (width 0.5) (layer "F.Cu") (net {i+1}) (uuid {q(uid(net+str(xa)))}))')
sch=f'(kicad_sch (version 20250114) (generator "eeschema") (generator_version "10.0") (uuid {q(root)}) (paper "A4") (title_block (title "Ground RS422 wire-ended splice / S01-S05 / no VACCO ICD") (date "2026-09-07") (rev "R1 CANDIDATE")) (lib_symbols {"".join(defs)}) {"".join(placements)} {"".join(objects)} (text "Passive splice only. Black return is explicit. No shield/PE tie. Validate cable revision and wire fit before fabrication." (at 25 185 0) (effects (font (size 1 1)) (justify left)) (uuid "{uid(name+"note")}")) (sheet_instances (path "/" (page "1"))))'
(E/(name+'.kicad_sch')).write_text(sch,encoding='utf8')
board='(kicad_pcb (version 20241229) (generator "pcbnew") (generator_version "10.0") (general (thickness 1.6)) (paper "A4") (layers (0 "F.Cu" signal) (31 "B.Cu" signal) (36 "B.SilkS" user "b.silkscreen") (37 "F.SilkS" user "f.silkscreen") (38 "B.Mask" user) (39 "F.Mask" user) (44 "Edge.Cuts" user) (48 "B.Fab" user) (49 "F.Fab" user)) (setup (pad_to_mask_clearance 0)) '+''.join(f'(net {i+1} "/RS_LOOP_{i+1}")' for i in range(5))+''.join(fps)+''.join(tracks)+f'(gr_rect (start 50 50) (end 90 80) (stroke (width 0.05) (type default)) (fill none) (layer "Edge.Cuts") (uuid "{uid(name+"edge")}")) (gr_text "WP09 GSE RS422 R1" (at 70 52) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))'
(E/(name+'.kicad_pcb')).write_text(board+')',encoding='utf8');(E/(name+'.kicad_pro')).write_text('{}',encoding='utf8');csvout(E/'RS422_PAD_MAP.csv',padmap)
dump(E/'DERIVATIVE_RESPONSIBILITY.json',dict(object='40x30mm ground RS422 wire-end splice and test points',upstream_footprint_sha256=sha(src),geometry_reuse='5 OreSat TestPoint-MinTH copper/drill geometries retained; reference silkscreen enlarged0.56 to1mm',new_responsibility=['10 wire solder pads drill1.2mm: received stripped wire fit unverified','2layer FR4 candidate 1.6mm','five 30mm 0.5mm-wide copper traces','mounting: external insulated fixture, not mounted in spacecraft','no line termination fitted: depends on received FTDI revision','not qualified for radiation/vacuum/pressure'],PWR_FLAG_used=False,all_passive_reason='This board is physically passive five independent conductors; complete system schematic retains power and signal electrical types',build_approved=False,manufacturing_exports_generated=False))
print(json.dumps(dict(rows=len(rows),modules=len(mods),endpoints=len(nets),nets=len(set(nets.values())),board_pads=15),ensure_ascii=False))
