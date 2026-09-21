"""Memory-guarded native export/ERC and full pin-table comparison of V22."""
from pathlib import Path
import csv, hashlib, json, subprocess, xml.etree.ElementTree as ET
from erc_source_contract import source_inventory
A=Path(__file__).resolve().parents[1];H=A/'history/20260910_V22_before_brake_enable'
ROOT=next(p for p in A.parents if (p/'PROJECT_MAP.md').is_file())
CLI=ROOT/'70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def dump(p,v):p.write_text(json.dumps(v,indent=2),encoding='utf-8')
source=A/'ecad/wp10_system.kicad_sch';_,sheets,_=source_inventory(source)
inputs={str(p.relative_to(A)).replace('\\','/'):sha(p) for p in sheets}
inputs.update({p:sha(A/p) for p in ['ecad/wp10_system.kicad_pro','ecad/POWER_LOOP_PIN_NET.csv','power/POWER_LOOP_PARTS.json','tools/verify_brake_enable_native_v22.py']})
assert len(sheets)==13
report=A/'results/SYSTEM_ERC_NATIVE_V22.json';pdf=A/'ecad/wp10_system_v22.pdf'
assert not report.exists() and not pdf.exists(), 'Archive previous execution before retry'
commands=[]
for args in [
 ['sch','export','netlist','--format','kicadxml','-o',str(A/'ecad/wp10_system.xml')],
 ['sch','erc','--format','json','--severity-all','--exit-code-violations','-o',str(report)],
 ['sch','export','pdf','-o',str(pdf)]]:
 q=subprocess.run([str(CLI),*args,str(source)],cwd=A,capture_output=True,text=True,encoding='utf-8',errors='replace')
 commands.append(dict(command=q.args,returncode=q.returncode,stdout=q.stdout,stderr=q.stderr))
 if q.returncode not in [0,5]:break
assert inputs=={p:sha(A/p) for p in inputs}, 'Source mutated during native run'
checks=[]
def ck(n,v,**kw):checks.append(dict(name=n,passed=bool(v),**kw))
ck('all_native_commands_completed',len(commands)==3 and all(c['returncode']==0 for c in commands))
rt=ET.parse(A/'ecad/wp10_system.xml').getroot();cs={c.get('ref'):c.findtext('value') for c in rt.findall('./components/comp')}
oldrt=ET.parse(H/'ecad/wp10_system.xml').getroot();oldcs={c.get('ref'):c.findtext('value') for c in oldrt.findall('./components/comp')}
nets={(n.get('ref'),n.get('pin')):nt.get('name') for nt in rt.findall('./nets/net') for n in nt.findall('node')}
oldnets={(n.get('ref'),n.get('pin')):nt.get('name') for nt in oldrt.findall('./nets/net') for n in nt.findall('node')}
for r in csv.DictReader((A/'ecad/POWER_LOOP_PIN_NET.csv').open(encoding='utf-8-sig')):
 actual=nets.get((r['reference'],r['pin']));expect=r['net']
 ck('pin_'+r['reference']+'.'+r['pin'],(not actual or actual.startswith('unconnected')) if expect=='EXPLICIT_NC' else actual==expect,actual=actual,expected=expect)
parts=read(A/'power/POWER_LOOP_PARTS.json');oldparts=read(H/'power/POWER_LOOP_PARTS.json')
parents=set(oldcs)-set(oldparts)
ck('99_parent_references_preserved',len(parents)==99 and parents.issubset(cs))
ck('exactly_six_new_references',set(cs)-set(oldcs)=={'U304','R308','R309','R310','C307','C308'})
for ref in parts:ck('value_'+ref,cs.get(ref)==parts[ref]['mpn'])
changed_pins=[ep for ep,n in oldnets.items() if nets.get(ep)!=n and not ep[0].startswith('#')]
ck('only_original_pin_rewired_is_U303_6',set(changed_pins)=={('U303','6')},changed_pins=changed_pins)
for ref in parents:ck('parent_value_'+ref,cs.get(ref)==oldcs[ref])
erc=read(report);vs=[v for s in erc['sheets'] for v in s['violations']]
ck('13_page_ERC_clean',len(erc['sheets'])==13 and not vs,violations=vs)
ck('ERC_ignored_checks_unchanged',erc['ignored_checks']==read(H/'results/SYSTEM_ERC_NATIVE_V20.json')['ignored_checks'])
for p in ['README.md','REVIEW.html','SYSTEM_CLOSURE_MATRIX.csv','results/DELIVERY_DECISION.json']:
 ck('sealed_'+p,sha(A/p)==sha(H/p))
out=dict(schema='WP10_BRAKE_ENABLE_NATIVE_V22',passed=all(c['passed'] for c in checks),
 commands=commands,checks=checks,check_count=len(checks),inputs=inputs,
 outputs={p:sha(A/p) for p in ['ecad/wp10_system.xml','ecad/wp10_system_v22.pdf','results/SYSTEM_ERC_NATIVE_V22.json']},
 components=len(cs),pages=13,errors=sum(v['severity']=='error' for v in vs),warnings=sum(v['severity']=='warning' for v in vs),
 ignored_checks=erc['ignored_checks'],whole_design_complete=False,physical_test_executed=False)
dump(A/'results/BRAKE_ENABLE_NATIVE_V22.json',out)
print(json.dumps({k:out[k] for k in ['passed','check_count','components','pages','errors','warnings']}),flush=True)
assert out['passed'], [c for c in checks if not c['passed']]
