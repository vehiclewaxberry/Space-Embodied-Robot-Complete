"""Complete31-ref board binding. No full hierarchy regeneration."""
from pathlib import Path
import csv,hashlib,json,shutil
from main_board_selection_v25 import PARTS,CORE,BOARD_REFS
from erc_source_contract import parse,enc,val,children,properties,source_inventory
A=Path(__file__).resolve().parents[1]
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def dump(p,v):(A/p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
parts=read('power/POWER_LOOP_PARTS.json')
for ref in CORE:
 d=PARTS[ref];parts[ref].update(mpn=d['MPN'],footprint=d['footprint'],source=d['source_url']+'; '+d['source_revision'],status=d['status'])
 if 'pins' in d:parts[ref]['pins']=d['pins']
dump('power/POWER_LOOP_PARTS.json',parts)
selection={r:dict(PARTS[r]) if r in PARTS else dict(MPN=parts[r]['mpn'],footprint=parts[r]['footprint'],source=parts[r]['source'],status=parts[r]['status']) for r in BOARD_REFS}
dump('power/MAIN_BOARD_SELECTION_V25.json',selection)
for rel in ['power/SELECTED_BOM.csv','ecad/POWER_LOOP_PIN_NET.csv']:
 rows=list(csv.DictReader((A/rel).open(encoding='utf-8-sig')))
 for row in rows:
  ref=row['role'].split(':')[0] if 'role' in row else row['reference']
  if ref in CORE:
   row['source']=parts[ref]['source']
   if 'MPN' in row:row.update(MPN=PARTS[ref]['MPN'],manufacturer=PARTS[ref]['manufacturer'],status=PARTS[ref]['status'])
   elif ref in ['D201','D202']:row['function']=parts[ref]['pins'][row['pin']]
 with (A/rel).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
_,sheets,_=source_inventory(A/'ecad/wp10_system.kicad_sch');requests=[]
for p in sheets:
 tree=parse(p.read_text(encoding='utf-8-sig'));symbols={properties(n).get('Reference'):n for n in children(tree,'symbol')}
 edits={r:dict(value=PARTS[r]['MPN'],properties={'Footprint':PARTS[r]['footprint'],'Manufacturer':PARTS[r]['manufacturer'],'MPN':PARTS[r]['MPN'],'Selection_Revision':'V25','Datasheet':PARTS[r]['source_url']}) for r in CORE if r in symbols}
 if edits:requests.append(dict(schematicPath=str(p),components=edits))
 # Align explicit pin names with preserved electrical endpoints, only the two diodes.
 changed=False
 for ref in ['D201','D202']:
  if ref not in symbols:continue
  lid=val(children(symbols[ref],'lib_id')[0][1])
  lib=next(l for b in children(tree,'lib_symbols') for l in children(b,'symbol') if val(l[1])==lid)
  for u in children(lib,'symbol'):
   for pin in children(u,'pin'):
    no=val(children(pin,'number')[0][1]);children(pin,'name')[0][1]=json.dumps(parts[ref]['pins'][no]);changed=True
 if changed:p.write_text(enc(tree)+'\n',encoding='utf-8')
dump('results/MAIN_BOARD_CORE_MCP_REQUESTS_V25.json',requests)
copies=read('sources/MAIN_BOARD_LIBRARY_COPIES_V25.json')
for name in ['SOT-23','SOT-23-6']:
 rel='Package_TO_SOT_SMD.pretty/'+name+'.kicad_mod';src=Path('G:/Windows_program_file/Kicad/share/kicad/footprints')/rel;dst=A/'ecad'/rel
 if dst.exists():assert dst.read_bytes()==src.read_bytes(),str(dst)
 else:shutil.copy2(src,dst)
 copies.append(dict(source=str(src),destination=dst.relative_to(A).as_posix(),sha256=hashlib.sha256(dst.read_bytes()).hexdigest()))
dump('sources/MAIN_BOARD_LIBRARY_COPIES_V25.json',copies)
# Add unambiguous cathode stripe on both Fab and silk, including a K2 label.
for name in ['SMBJ30A_A1K2','STPS3H100U_A1K2']:
 p=A/'ecad/WP10_INPUT.pretty'/(name+'.kicad_mod');t=parse(p.read_text())
 for layer in ['F.Fab','F.SilkS']:
  t.append(parse(f'(fp_line (start 1.4 -1.85) (end 1.4 1.85) (stroke (width 0.15) (type default)) (layer "{layer}"))'))
 t.append(parse('(fp_text user "K2" (at 2.2 -3.1) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))'))
 p.write_text(enc(t)+'\n',encoding='utf-8')
gp=A/'tools/integrate_power_loop.py';s=gp.read_text(encoding='utf-8')
needle=" parts[ref].update(mpn=v['MPN'],footprint=v['footprint'],status=v['status'],source=v['source_url']+'; '+v['source_revision'])"
# Add optional diode pin map only in V25 loop, not V24 timing block.
marker='for ref,v in MAIN_BOARD_SELECTION_V25.items():\n'+needle
assert s.count(marker)==1;s=s.replace(marker,marker+"\n if 'pins' in v:parts[ref]['pins']=v['pins']")
gp.write_text(s,encoding='utf-8')
print(json.dumps(dict(board_refs=len(selection),core_bound=len(CORE),requests=len(requests))))
