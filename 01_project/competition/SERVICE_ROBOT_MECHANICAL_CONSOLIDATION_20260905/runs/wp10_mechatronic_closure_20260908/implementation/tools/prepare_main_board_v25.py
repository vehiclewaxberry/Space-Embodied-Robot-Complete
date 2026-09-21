"""Backup before edits; synchronize selected passives without full regeneration."""
from pathlib import Path
import ast,csv,hashlib,json,shutil
from erc_source_contract import source_inventory,parse,children,properties
from main_board_selection_v25 import PARTS,BOARD_REFS
A=Path(__file__).resolve().parents[1];H=A/'history/20260910_V25_before_main_board'
def dump(p,v):(A/p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
_,sheets,_=source_inventory(A/'ecad/wp10_system.kicad_sch')
paths=[p.relative_to(A).as_posix() for p in sheets]+['ecad/wp10_system.xml','ecad/wp10_system.kicad_pro','ecad/fp-lib-table',
 'ecad/POWER_LOOP_PIN_NET.csv','ecad/POWER_LOOP_INTEGRATION.json','power/POWER_LOOP_PARTS.json','power/SELECTED_BOM.csv',
 'power/STARTUP_CIRCUIT_DEFINITION.json','power/STARTUP_CIRCUIT_CALCULATIONS.json','power/STOP_FULL_FAULT_BUDGET.json',
 'power/POWER_LOOP_CALCULATIONS.json','power/BRAKE_READY_CALCULATIONS_V22.json','power/STARTUP_DESIGN.md',
 'tools/verify_startup_and_fault.py','tools/integrate_power_loop.py','tools/startup_circuit_definition.py','results/SYSTEM_ERC_NATIVE_V24.json']
assert not H.exists()
H.mkdir()
for rel in paths:
 dst=H/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(A/rel,dst)
dump('results/MAIN_BOARD_BASELINE_V25.json',{p:sha(H/p) for p in paths})
for d in PARTS.values():assert sha(A/d['source_file'])==d['source_sha256']
parts=json.loads((A/'power/POWER_LOOP_PARTS.json').read_text(encoding='utf-8-sig'))
for ref,d in PARTS.items():
 parts[ref].update(mpn=d['MPN'],footprint=d['footprint'],source=d['source_url']+'; '+d['source_revision'],status=d['status'])
dump('power/POWER_LOOP_PARTS.json',parts)
dump('power/MAIN_BOARD_PASSIVE_SELECTION_V25.json',PARTS)
for rel in ['power/SELECTED_BOM.csv','ecad/POWER_LOOP_PIN_NET.csv']:
 rows=list(csv.DictReader((A/rel).open(encoding='utf-8-sig')))
 for row in rows:
  ref=row['role'].split(':')[0] if 'role' in row else row['reference']
  if ref in PARTS:
   row['source']=parts[ref]['source']
   if 'MPN' in row:row.update(MPN=PARTS[ref]['MPN'],manufacturer=PARTS[ref]['manufacturer'],status=PARTS[ref]['status'])
 with (A/rel).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
# Generator overlays are placed after startup creation and before sheet emission.
gp=A/'tools/integrate_power_loop.py';s=gp.read_text(encoding='utf-8')
needle="startup_refs=startup['add_startup'](part,passive,parts,groups,nc)"
assert s.count(needle)==1
s=s.replace(needle,needle+'''\n# V25 exact selections, same system refs. Does not authorize full-generator execution.\nfrom main_board_selection_v25 import PARTS as MAIN_BOARD_SELECTION_V25\nfor ref,v in MAIN_BOARD_SELECTION_V25.items():\n parts[ref].update(mpn=v['MPN'],footprint=v['footprint'],status=v['status'],source=v['source_url']+'; '+v['source_revision'])\n''')
ast.parse(s);gp.write_text(s,encoding='utf-8')
requests=[]
for p in sheets:
 refs={properties(n).get('Reference') for n in children(parse(p.read_text(encoding='utf-8-sig')),'symbol')}
 edits={r:dict(value=d['MPN'],properties={'Footprint':d['footprint'],'Manufacturer':d['manufacturer'],'MPN':d['MPN'],
  'Selection_Revision':'V25','Datasheet':d['source_url']}) for r,d in PARTS.items() if r in refs}
 if edits:requests.append(dict(schematicPath=str(p),components=edits))
assert sum(len(r['components']) for r in requests)==15
dump('results/MAIN_BOARD_MCP_REQUESTS_V25.json',requests)
libbase=Path('G:/Windows_program_file/Kicad/share/kicad/footprints')
copied=[]
for size,metric in [('0805','2012'),('1210','3225')]:
 rel=f'Resistor_SMD.pretty/R_{size}_{metric}Metric.kicad_mod';src=libbase/rel;dst=A/'ecad'/rel
 assert not dst.exists();shutil.copy2(src,dst);copied.append(dict(source=str(src),destination=dst.relative_to(A).as_posix(),sha256=sha(dst)))
dump('sources/MAIN_BOARD_LIBRARY_COPIES_V25.json',copied)
print(json.dumps(dict(backed_up=len(paths),selected_passives=len(PARTS),target_board_refs=len(BOARD_REFS),mcp_requests=len(requests))))
