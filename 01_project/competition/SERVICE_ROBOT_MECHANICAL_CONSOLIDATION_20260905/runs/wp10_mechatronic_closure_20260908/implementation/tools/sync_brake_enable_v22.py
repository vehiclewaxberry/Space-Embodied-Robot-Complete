"""Synchronize V22's pure circuit definition into the existing candidate tables.

Native schematic placement/wiring is performed through KiCad MCP, independently
checked against these tables after the native export. No full regeneration.
"""
from pathlib import Path
import csv, hashlib, json, runpy
A=Path(__file__).resolve().parents[1];H=A/'history/20260910_V22_before_brake_enable'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
old=read(H/'power/POWER_LOOP_PARTS.json');parts=dict(old)
fresh={'J203':dict(old['J203'])};groups={};nc=set()
def part(ref,mpn,pins,source,role,status='SELECTED_CANDIDATE'):
 fresh[ref]=dict(mpn=mpn,pins=pins,source=source,role=role,status=status)
def passive(ref,value,role,source='PROJECT_VALUE_ALLOCATION_MPN_UNBOUND'):
 part(ref,value,{'1':'A','2':'B'},source,role,'VALUE_SELECTED_MPN_UNBOUND')
module=runpy.run_path(str(A/'tools/brake_circuit_definition.py'))
refs=module['add_brake'](part,passive,fresh,groups,nc)
new=set(fresh)-set(old)
assert new=={'U304','R308','R309','R310','C307','C308'}
for ref,p in fresh.items():parts[ref]={**old.get(ref,{}),**p}
dump(A/'power/POWER_LOOP_PARTS.json',parts)
definition=read(H/'power/LOAD_SIDE_BRAKE_DEFINITION.json')
definition.update(schema='WP10_LOAD_SIDE_BRAKE_DEFINITION_V22',refs=refs,parameters=module['PARAMS'],
 ready_source='U304 MAX16053 push-pull voltage monitor',driver='U303 MAX5048C',
 legacy_PG_diagnostic_only=True,physical_hardware_installed=False,whole_brake_function_verified=False)
dump(A/'power/LOAD_SIDE_BRAKE_DEFINITION.json',definition)
rows=list(csv.DictReader((H/'ecad/POWER_LOOP_PIN_NET.csv').open(encoding='utf-8-sig')))
for r in rows:
 ref=r['reference'];pin=r['pin']
 if ref in fresh:
  r.update(function=parts[ref]['pins'][pin],source=parts[ref]['source'])
 if (ref,pin)==('U303','6'):r['net']='WP10_BRAKE_BIAS_READY'
pin_net={ep:'WP10_'+name for name,eps in groups.items() for ep in eps}
for ref in sorted(new):
 for pin,fn in parts[ref]['pins'].items():
  rows.append(dict(reference=ref,pin=pin,function=fn,net=pin_net[ref+'.'+pin],source=parts[ref]['source']))
with (A/'ecad/POWER_LOOP_PIN_NET.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
changed=[r for r in parts if r not in old or parts[r]!=old[r]]
bom=[]
for r in changed:
 p=parts[r];bom.append(dict(reference=r,quantity=1,old_value=old.get(r,{}).get('mpn','NEW'),value=p['mpn'],manufacturer_part_number=p.get('manufacturer_part_number',p['mpn'] if p['mpn'].startswith('MAX') else 'UNBOUND'),footprint=p.get('footprint','UNBOUND'),role=p['role'],scope='SCHEMATIC_CANDIDATE_PCB_INSTALLATION_NOT_RELEASED'))
with (A/'ecad/BRAKE_ENABLE_BOM_DELTA_V22.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(bom[0]));w.writeheader();w.writerows(bom)
dump(A/'results/BRAKE_ENABLE_SOURCE_SYNC_V22.json',dict(new_refs=sorted(new),changed_refs=changed,
 previous_parts_sha256=sha(H/'power/POWER_LOOP_PARTS.json'),current_parts_sha256=sha(A/'power/POWER_LOOP_PARTS.json'),
 circuit_definition_sha256=sha(A/'tools/brake_circuit_definition.py'),pin_net_sha256=sha(A/'ecad/POWER_LOOP_PIN_NET.csv'),
 native_match_pending=True,whole_design_complete=False))
print(json.dumps(dict(new_refs=len(new),changed_refs=changed,pin_rows=len(rows))))
