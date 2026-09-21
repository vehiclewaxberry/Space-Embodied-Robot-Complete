"""Export the current system, verify selected fields and unchanged connectivity."""
from pathlib import Path
import csv,hashlib,json,subprocess,xml.etree.ElementTree as ET
from erc_source_contract import source_inventory
from main_board_selection_v25 import PARTS,BOARD_REFS
A=Path(__file__).resolve().parents[1];H=A/'history/20260910_V25_before_main_board'
ROOT=next(p for p in A.parents if (p/'PROJECT_MAP.md').exists())
CLI=ROOT/'70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
source=A/'ecad/wp10_system.kicad_sch';_,sheets,_=source_inventory(source)
inputs={p.relative_to(A).as_posix():sha(p) for p in sheets}
for rel in ['power/POWER_LOOP_PARTS.json','power/MAIN_BOARD_SELECTION_V25.json','ecad/fp-lib-table','tools/main_board_selection_v25.py','tools/verify_main_board_native_v25.py']:
 inputs[rel]=sha(A/rel)
report=A/'results/SYSTEM_ERC_NATIVE_V25.json';pdf=A/'ecad/wp10_system_v25.pdf'
assert not report.exists() and not pdf.exists()
commands=[]
for args in [
 ['sch','export','netlist','--format','kicadxml','-o',str(A/'ecad/wp10_system.xml')],
 ['sch','erc','--format','json','--severity-all','--exit-code-violations','-o',str(report)],
 ['sch','export','pdf','-o',str(pdf)]]:
 q=subprocess.run([str(CLI),*args,str(source)],cwd=A,capture_output=True,text=True,encoding='utf-8',errors='replace')
 commands.append(dict(args=q.args,returncode=q.returncode,stdout=q.stdout,stderr=q.stderr))
 if q.returncode not in [0,5]:break
def comps(t):return {c.get('ref'):c for c in t.findall('./components/comp')}
def nets(t):return {(n.get('ref'),n.get('pin')):nt.get('name') for nt in t.findall('./nets/net') for n in nt.findall('node')}
rt=ET.parse(A/'ecad/wp10_system.xml').getroot();old=ET.parse(H/'ecad/wp10_system.xml').getroot()
cs,oc,nt,on=comps(rt),comps(old),nets(rt),nets(old)
manifest=read(A/'power/POWER_LOOP_PARTS.json');selection=read(A/'power/MAIN_BOARD_SELECTION_V25.json')
checks={
 'native_three_commands_success':len(commands)==3 and all(q['returncode']==0 for q in commands),
 '207_refs_99_parent_preserved':set(cs)==set(oc) and len(cs)==207 and len(set(cs)-set(manifest))==99,
 'every_exported_pin_net_unchanged':nt==on,
 'all108_manifest_values_match':all(cs[r].findtext('value')==d['mpn'] for r,d in manifest.items()),
 'all31_board_footprints_match':all(cs[r].findtext('footprint')==selection[r]['footprint'] for r in BOARD_REFS),
 'other_values_unchanged':all(c.findtext('value')==oc[r].findtext('value') for r,c in cs.items() if r not in BOARD_REFS)}
rows=list(csv.DictReader((A/'ecad/POWER_LOOP_PIN_NET.csv').open(encoding='utf-8-sig')))
checks['all304_pin_contract_rows_match']=len(rows)==304 and all(
 (not nt.get((r['reference'],r['pin'])) or nt[(r['reference'],r['pin'])].startswith('unconnected')) if r['net']=='EXPLICIT_NC'
 else nt.get((r['reference'],r['pin']))==r['net'] for r in rows)
erc=read(report);vs=[v for s in erc['sheets'] for v in s['violations']]
checks['13pages_ERC_clean']=len(sheets)==len(erc['sheets'])==13 and not vs
checks['ignored_checks_not_relaxed']=erc['ignored_checks']==read(H/'results/SYSTEM_ERC_NATIVE_V24.json')['ignored_checks']
checks['source_unchanged_during_export']=inputs=={p:sha(A/p) for p in inputs}
out=dict(schema='WP10_MAIN_BOARD_NATIVE_V25',passed=all(checks.values()),checks=checks,commands=commands,inputs=inputs,
 outputs={p:sha(A/p) for p in ['ecad/wp10_system.xml','ecad/wp10_system_v25.pdf','results/SYSTEM_ERC_NATIVE_V25.json']},
 components=len(cs),pages=len(sheets),errors=sum(v['severity']=='error' for v in vs),warnings=sum(v['severity']=='warning' for v in vs),
 changed_values=[r for r,c in cs.items() if c.findtext('value')!=oc[r].findtext('value')],
 whole_design_complete=False,physical_test_executed=False)
(A/'results/MAIN_BOARD_NATIVE_V25.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps({k:out[k] for k in ['passed','components','pages','errors','warnings','changed_values']}))
assert out['passed'],checks
integration=read(A/'ecad/POWER_LOOP_INTEGRATION.json')
integration.update(active_revision='V25',native_xml_sha256=out['outputs']['ecad/wp10_system.xml'],main_board_selection='power/MAIN_BOARD_SELECTION_V25.json')
(A/'ecad/POWER_LOOP_INTEGRATION.json').write_text(json.dumps(integration,indent=2),encoding='utf-8')
