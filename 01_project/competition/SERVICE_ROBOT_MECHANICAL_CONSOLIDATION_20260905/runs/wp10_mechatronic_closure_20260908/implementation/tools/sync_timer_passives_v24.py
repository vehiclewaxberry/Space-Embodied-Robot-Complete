"""Apply six selected MPNs to current sidecars, without regenerating hierarchy."""
from pathlib import Path
import csv,hashlib,json
from timer_passive_definition_v24 import TIMING_PASSIVES as T
A=Path(__file__).resolve().parents[1]
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def dump(p,v):(A/p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def table(p):return list(csv.DictReader((A/p).open(encoding='utf-8-sig')))
def csvout(p,rows):
 with (A/p).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
for v in T.values():
 assert hashlib.sha256((A/v['source_file']).read_bytes()).hexdigest()==v['source_sha256']
parts=read('power/POWER_LOOP_PARTS.json');assert len(parts)==108
for ref,v in T.items():
 parts[ref].update(mpn=v['MPN'],footprint=v['footprint'],status=v['status'],
  source=v['source_url']+'; '+v['source_revision'])
dump('power/POWER_LOOP_PARTS.json',parts)
dump('power/TIMER_PASSIVE_SELECTION_V24.json',T)
pins=table('ecad/POWER_LOOP_PIN_NET.csv');assert len(pins)==304
for row in pins:
 if row['reference'] in T:row['source']=parts[row['reference']]['source']
csvout('ecad/POWER_LOOP_PIN_NET.csv',pins)
bom=table('power/SELECTED_BOM.csv')
for ref,v in T.items():
 rows=[r for r in bom if r['role'].startswith(ref+': ')]
 assert len(rows)==1,(ref,len(rows))
 rows[0].update(manufacturer=v['manufacturer'],MPN=v['MPN'],status=v['status'],source=parts[ref]['source'])
csvout('power/SELECTED_BOM.csv',bom)
p=read('power/POWER_LOOP_CALCULATIONS.json')
p['precharge'].update(reduced_transient_definition='power/HOTSWAP_TRANSIENT_DEFINITION_V24.json',
 reduced_transient_calculations='power/HOTSWAP_TRANSIENT_CALCULATIONS_V24.json',
 timer_passive_selection='power/TIMER_PASSIVE_SELECTION_V24.json',
 timer_passive_calculations='power/TIMER_PASSIVE_CALCULATIONS_V24.json',
 fault_timer_corner_scope='0.9..1.1uF effective-C requirement; no full-temperature/life proof')
dump('power/POWER_LOOP_CALCULATIONS.json',p)
print(json.dumps(dict(selected_refs=list(T),added_refs=0,sidecars_synchronized=True)))

