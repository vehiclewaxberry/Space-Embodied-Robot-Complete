"""Serial current hierarchy export, all-net invariance, and selected fields."""
from pathlib import Path
import csv,hashlib,json,subprocess,xml.etree.ElementTree as ET
from erc_source_contract import source_inventory
from timer_passive_definition_v24 import TIMING_PASSIVES as T
A=Path(__file__).resolve().parents[1];H=A/'history/20260910_V24_before_timer_passives'
ROOT=next(p for p in A.parents if (p/'PROJECT_MAP.md').exists())
CLI=ROOT/'70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
source=A/'ecad/wp10_system.kicad_sch';_,sheets,_=source_inventory(source)
extra=['ecad/wp10_system.kicad_pro','ecad/fp-lib-table','ecad/POWER_LOOP_PIN_NET.csv',
 'power/POWER_LOOP_PARTS.json','power/SELECTED_BOM.csv','power/TIMER_PASSIVE_SELECTION_V24.json',
 'tools/verify_timer_passives_native_v24.py','tools/timer_passive_definition_v24.py',
 'ecad/WP10_TIMING.pretty/C201_MKP2_1uF_P5_Slot2.kicad_mod',
 'ecad/Resistor_SMD.pretty/R_0603_1608Metric.kicad_mod']
inputs={p.relative_to(A).as_posix():sha(p) for p in sheets}
inputs.update({p:sha(A/p) for p in extra})
report=A/'results/SYSTEM_ERC_NATIVE_V24.json';pdf=A/'ecad/wp10_system_v24.pdf'
assert not report.exists() and not pdf.exists()
commands=[]
for args in [
 ['sch','export','netlist','--format','kicadxml','-o',str(A/'ecad/wp10_system.xml')],
 ['sch','erc','--format','json','--severity-all','--exit-code-violations','-o',str(report)],
 ['sch','export','pdf','-o',str(pdf)]]:
 q=subprocess.run([str(CLI),*args,str(source)],cwd=A,capture_output=True,text=True,encoding='utf-8',errors='replace')
 commands.append(dict(args=q.args,returncode=q.returncode,stdout=q.stdout,stderr=q.stderr))
 if q.returncode not in [0,5]:break
checks=[]
def ck(name,v,**kw):checks.append(dict(name=name,passed=bool(v),**kw))
ck('three_native_commands_success',len(commands)==3 and all(q['returncode']==0 for q in commands))
rt=ET.parse(A/'ecad/wp10_system.xml').getroot();old=ET.parse(H/'ecad/wp10_system.xml').getroot()
def comps(t):return {c.get('ref'):c for c in t.findall('./components/comp')}
def nets(t):return {(n.get('ref'),n.get('pin')):nt.get('name') for nt in t.findall('./nets/net') for n in nt.findall('node')}
cs=comps(rt);oc=comps(old);nt=nets(rt);on=nets(old)
ck('all207_references_unchanged',set(cs)==set(oc) and len(cs)==207)
ck('all_exported_pin_nets_identical',nt==on,changed=[list(ep) for ep in set(nt)|set(on) if nt.get(ep)!=on.get(ep)])
parts=read(A/'power/POWER_LOOP_PARTS.json')
for ref,c in cs.items():
 ck('value_'+ref,c.findtext('value')==(T[ref]['MPN'] if ref in T else oc[ref].findtext('value')))
 if ref in T:ck('footprint_'+ref,c.findtext('footprint')==T[ref]['footprint'])
for ref,v in parts.items():ck('manifest_'+ref,cs[ref].findtext('value')==v['mpn'])
for r in csv.DictReader((A/'ecad/POWER_LOOP_PIN_NET.csv').open(encoding='utf-8-sig')):
 actual=nt.get((r['reference'],r['pin']));expected=r['net']
 ck('pin_'+r['reference']+'.'+r['pin'],(not actual or actual.startswith('unconnected')) if expected=='EXPLICIT_NC' else actual==expected)
ck('99_parent_refs_preserved',len(set(cs)-set(parts))==99)
erc=read(report);vs=[v for s in erc['sheets'] for v in s['violations']]
ck('13pages_ERC_clean',len(sheets)==len(erc['sheets'])==13 and not vs)
ck('ignored_checks_not_relaxed',erc['ignored_checks']==read(H/'results/SYSTEM_ERC_NATIVE_V22.json')['ignored_checks'])
for p in ['README.md','REVIEW.html','SYSTEM_CLOSURE_MATRIX.csv','results/DELIVERY_DECISION.json']:
 ck('sealed_'+p,sha(A/p)==sha(A/'history/20260910_V22_before_brake_enable'/p))
ck('source_hashes_unchanged_during_run',inputs=={p:sha(A/p) for p in inputs})
outputs={p:sha(A/p) for p in ['ecad/wp10_system.xml','ecad/wp10_system_v24.pdf','results/SYSTEM_ERC_NATIVE_V24.json']}
out=dict(schema='WP10_TIMER_PASSIVES_NATIVE_V24',passed=all(c['passed'] for c in checks),
 checks=checks,check_count=len(checks),commands=commands,inputs=inputs,outputs=outputs,components=len(cs),pages=len(sheets),
 errors=sum(v['severity']=='error' for v in vs),warnings=sum(v['severity']=='warning' for v in vs),
 ignored_checks=erc['ignored_checks'],whole_design_complete=False,physical_test_executed=False)
(A/'results/TIMER_PASSIVES_NATIVE_V24.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps({k:out[k] for k in ['passed','check_count','components','pages','errors','warnings']}))
assert out['passed'],[c for c in checks if not c['passed']]
integration=read(A/'ecad/POWER_LOOP_INTEGRATION.json')
integration.update(active_revision='V24',native_xml_sha256=outputs['ecad/wp10_system.xml'],timer_passives_bound=list(T))
(A/'ecad/POWER_LOOP_INTEGRATION.json').write_text(json.dumps(integration,indent=2),encoding='utf-8')

