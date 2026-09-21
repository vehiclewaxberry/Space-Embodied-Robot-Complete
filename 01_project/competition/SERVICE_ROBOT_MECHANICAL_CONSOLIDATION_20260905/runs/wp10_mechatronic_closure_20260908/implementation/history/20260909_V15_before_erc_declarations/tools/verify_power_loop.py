"""Native netlist and source-preservation checks; no physical safety PASS."""
from pathlib import Path
import csv, hashlib, json, subprocess, xml.etree.ElementTree as ET
A=Path(__file__).resolve().parents[1];D=A.parent;E=A/'ecad';exe=A.parents[5]/'70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe'
checks=[]
def ck(n,b,**kw):checks.append(dict(name=n,passed=bool(b),**kw))
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for args in [['sch','export','netlist','--format','kicadxml','-o',str(E/'wp10_system.xml')],['sch','export','pdf','-o',str(E/'wp10_system.pdf')],['sch','erc','--format','json','-o',str(A/'results/POWER_LOOP_ERC.json')]]:
 p=subprocess.run([str(exe),*args,str(E/'wp10_system.kicad_sch')],capture_output=True,text=True,encoding='utf-8',errors='replace');ck('native_'+args[1]+'_'+args[2],p.returncode==0,stdout=p.stdout,stderr=p.stderr)
rt=ET.parse(E/'wp10_system.xml').getroot();comps={c.get('ref'):c for c in rt.findall('./components/comp')};actual={}
for n in rt.findall('./nets/net'):
 for p in n.findall('node'):actual[(p.get('ref'),p.get('pin'))]=n.get('name')
def n(ref,p):return actual.get((ref,p))
for r in csv.DictReader((E/'POWER_LOOP_PIN_NET.csv').open(encoding='utf-8-sig')):
 got=n(r['reference'],r['pin'])
 ck('native_new_'+r['reference']+'.'+r['pin'],(not got or got.startswith('unconnected')) if r['net']=='EXPLICIT_NC' else got==r['net'],actual=got,expected=r['net'])
root_map=json.loads((E/'SYSTEM_ENDPOINT_MAP.json').read_text())
for ep,r in root_map.items():
 got=n(r['ref'],r['pin'])
 ck('native_parent_'+ep,(not got or got.startswith('unconnected')) if not r['net'] else got==r['net'],actual=got,expected=r['net'])
parts=json.loads((A/'power/POWER_LOOP_PARTS.json').read_text())
oldref={r['ref'] for r in json.loads((D/'ecad/SYSTEM_ENDPOINT_MAP.json').read_text()).values()}
oldref.update(r['reference'] for r in csv.DictReader((D/'electrical/STOP_PIN_NET_MAP.csv').open(encoding='utf-8-sig')))
ck('99_parent_refs_preserved',len(oldref)==99 and oldref.issubset(comps))
ck('all_added_refs_exact',set(comps)-oldref==set(parts),native_count=len(comps))
ck('input_output_returns_separate',n('U203','4')!=n('U203','5'))
ck('aux_input_before_main_switch',n('F202','1')==n('J200','1') and n('F202','1')!=n('Q201','3'))
ck('aux_output_powers_stop',n('U202','4') is not None and n('U202','4')==n('U120','1')==n('U121','1')==n('J101','3'))
ck('THN_remote_is_unwired',not n('U202','3') or n('U202','3').startswith('unconnected'))
ck('CHB_default_open_no_self_output_control',n('U203','2')==n('J201','1') and n('J201','2')==n('U203','4'))
ck('CHB_local_sense',n('U203','8')==n('U203','9') and n('U203','6')==n('U203','5'))
ck('common_drain_reverse_blocker',n('Q202','2')==n('Q203','2')==n('U204','10')==n('U204','12'))
ck('reverse_blocker_orientation',n('Q202','3')==n('U203','9') and n('Q203','3')==n('U204','9') and n('Q202','3')!=n('Q203','3'))
def epnet(ep):r=root_map[ep];return n(r['ref'],r['pin'])
ck('brake_stays_with_DM_when_K1_open',n('J203','1')==epnet('K1.A1(-)')==epnet('SEP.PWR')==epnet('DM.VCC_REF') and n('J203','1')!=epnet('K1.A2(+)'))
ck('brake_return_with_DM',n('J203','2')==epnet('SEP.RET')==epnet('DM.RET_REF'))
ck('LM7480_pad_floating',not n('U204','EP') or n('U204','EP').startswith('unconnected'))
calc=json.loads((A/'power/POWER_LOOP_CALCULATIONS.json').read_text())
ck('360W_not_lowered_or_double_counted',calc['arm_output_W']==360 and calc['aux_output_W']==16.8 and calc['no_double_count'])
ck('unequal_contact_counterexample_retained',calc['PMM_contact_counterexample']['contact_A'][0]>10)
ck('OVLO_does_not_reject_normal_full_battery',calc['OVLO_rising_screen_V'][0]>29.4)
ck('conditional_normal_current_screen',calc['main_latched_limit_plus_aux_normal_screen_A']<30)
ck('no_fake_dynamic_pass',calc['independent_aux']['dynamic_pass'] is False and calc['regen']['absorber_fitted'] is False)
ck('latched_not_retry',parts['U201']['mpn']=='LM5069MM-1')
ck('22V_cold_start_counterexample_retained',all(s['initial_cold_start_screen']=='ALL_SCREEN_CORNERS_OFF' and s['available_current_margin_after_UVLO_screen_A'] is None for s in calc['scenarios'] if s['battery_loaded_V']==22))
ck('upper_UVLO_hysteresis_included',calc['UVLO_rising_screen_V'][1]>calc['UVLO_falling_screen_V'][1])
ck('sense_node_pre_fuse_drop_not_ignored',all(s['running_UVLO_detect_V']<s['battery_loaded_V'] for s in calc['scenarios']))
ck('charge_only_not_silently_connected',not any('PMM' in x['mpn'] for x in parts.values()))
oldhash=list(csv.DictReader((D/'results/OUTPUT_SHA256.csv').open(encoding='utf-8-sig')))
bad=[r['path'] for r in oldhash if not (D/r['path']).exists() or sha(D/r['path'])!=r['sha256']]
ck('sealed_parent_bytes_unchanged',not bad,count=len(oldhash),mismatches=bad)
erc=json.loads((A/'results/POWER_LOOP_ERC.json').read_text());v=[x for s in erc['sheets'] for x in s['violations']]
types={x['type']:sum(y['type']==x['type'] for y in v) for x in v}
ck('no_power_flag_fabrication',not any(c.findtext('value')=='PWR_FLAG' or (c.find('libsource') is not None and c.find('libsource').get('part')=='PWR_FLAG') for c in comps.values()))
out=dict(all_connectivity_checks_passed=all(c['passed'] for c in checks),count=len(checks),checks=checks,native_components=len(comps),ERC_count=len(v),ERC_types=types,ERC_clean=not v,whole_design_verified=False,energization_authorized=False)
dump(A/'results/POWER_LOOP_VERIFICATION.json',out)
print(json.dumps({k:out[k] for k in ['all_connectivity_checks_passed','count','native_components','ERC_count','ERC_types','whole_design_verified']}))
assert out['all_connectivity_checks_passed'],[c for c in checks if not c['passed']]
