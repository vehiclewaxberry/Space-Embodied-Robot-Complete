"""Check actual KiCad hierarchy and preservation of external wiring constraints."""
from pathlib import Path
import hashlib,json,csv,subprocess,os,xml.etree.ElementTree as ET,collections
from datetime import datetime,timezone
C=Path(__file__).resolve().parents[1];E=C/'ecad';S=C/'electrical_delta';N=C.parent/'reuse_closure'
rt=next(p/'70_tools/runtime_wp09_kicad/portable' for p in C.parents if (p/'70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe').exists())
env=os.environ.copy();env['KICAD_CONFIG_HOME']=str(E/'runtime_config');env['KICAD10_SYMBOL_DIR']=str(rt/'share/kicad/symbols');env['KICAD10_FOOTPRINT_DIR']=str(rt/'share/kicad/footprints')
(E/'exports').mkdir(exist_ok=True);runs=[]
def run(args):
    r=subprocess.run([str(rt/'bin/kicad-cli.exe'),*map(str,args)],capture_output=True,text=True,encoding='utf-8',errors='replace',env=env,timeout=60)
    runs.append({'args':list(map(str,args)),'rc':r.returncode,'stdout':r.stdout,'stderr':r.stderr});return r.returncode
assert run(['sch','export','netlist','--format','kicadxml','-o',E/'exports/wp09_system.xml',E/'wp09_system.kicad_sch'])==0,runs
erc_rc=run(['sch','erc','--format','json','--severity-all','--exit-code-violations','-o',E/'exports/wp09_system_erc.json',E/'wp09_system.kicad_sch'])
assert run(['sch','export','svg','-o',E/'exports/schematic',E/'wp09_system.kicad_sch'])==0,runs
assert run(['sch','export','pdf','-o',E/'exports/WP09_SYSTEM_AND_STOP.pdf',E/'wp09_system.kicad_sch'])==0,runs
xml=ET.parse(E/'exports/wp09_system.xml').getroot()
actual={};nets={}
for node in xml.find('nets'):
    name=node.attrib['name'];members={(x.attrib['ref'],x.attrib['pin']) for x in node.findall('node')}
    nets[name]=members
    for member in members:assert member not in actual;actual[member]=name
mp=json.loads((E/'SYSTEM_ENDPOINT_MAP.json').read_text(encoding='utf-8'))
wire=list(csv.DictReader((E/'MASTER_FROM_TO.csv').open(encoding='utf-8-sig')))
checks=[]
def check(name,ok,detail=None):checks.append({'name':name,'pass':bool(ok),'detail':detail});assert ok,(name,detail)
for r in wire:
    a,b=mp[r['from_endpoint']],mp[r['to_endpoint']];aa=(a['ref'],a['pin']);bb=(b['ref'],b['pin'])
    check(r['wire_id']+'_actual_connected',aa in actual and bb in actual and actual[aa]==actual[bb])
pinrows=list(csv.DictReader((S/'STOP_PIN_NET_MAP.csv').open(encoding='utf-8-sig')))
group=collections.defaultdict(set)
for r in pinrows:group[r['net']].add((r['reference'],r['pin']))
for net,members in group.items():
    check('stop_net_'+net,members<=actual.keys() and len({actual[p] for p in members})==1)
for ep,p in mp.items():
    if ep.startswith('STOPBOARD.'):
        ref,pin=ep[len('STOPBOARD.'):].split('.',1)
        check('hierarchy_binding_'+ep,actual[(p['ref'],p['pin'])]==actual[(ref,pin)])
check('coil_high_low_not_short',actual[('J104','1')]!=actual[('J104','2')])
check('aux_contacts_not_short',actual[('J105','1')]!=actual[('J105','2')])
check('protected_raw_and_switched_main_not_short',actual[(mp['Q1.2']['ref'],mp['Q1.2']['pin'])]!=actual[(mp['U1.IN+']['ref'],mp['U1.IN+']['pin'])])
check('MCU_VIO_not_stop_3V3_or_5V',actual[('J102','8')] not in [actual[('J101','1')],actual[('J101','2')]])
parent=list(csv.DictReader((N/'ecad/MASTER_FROM_TO.csv').open(encoding='utf-8-sig')))
for r in parent:
    new=next(x for x in wire if x['wire_id']==r['wire_id'])
    check('parent_row_'+r['wire_id'],r==new if not r['wire_id'].startswith('K1_') else new['physical_test']=='NOT_EXECUTED')
erc=json.loads((E/'exports/wp09_system_erc.json').read_text(encoding='utf-8'))
violations=[v for sheet in erc.get('sheets',[]) for v in sheet.get('violations',[])]
types=collections.Counter((v.get('severity',''),v.get('type','')) for v in violations)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
receipt={'schema':'SYSTEM_STOP_ECAD_INTEGRATION_V1','utc':datetime.now(timezone.utc).isoformat(),'status':'PASS_ACTUAL_HIERARCHY_NET_BINDINGS__ELECTRICAL_DESIGN_OPEN',
 'checks_passed':len(checks),'checks':checks,'external_master_rows':len(wire),'original_wire_ids_preserved':len(parent),
 'actual_components':len(xml.find('components')),'actual_nets':len(nets),'subpage_parts':len({x['reference'] for x in pinrows}),
 'erc_exit_code':erc_rc,'erc_violations_by_severity_and_type':{str(k):v for k,v in types.items()},'erc_all_clear':not violations,
 'source_binding':json.loads((E/'STOP_INTEGRATION_BINDING.json').read_text(encoding='utf-8')),
 'files':[{'path':str(p),'sha256':sha(p)} for p in [E/'MASTER_FROM_TO.csv',E/'wp09_system.kicad_sch',E/'wp09_stop_detail.kicad_sch',E/'exports/wp09_system.xml',E/'exports/WP09_SYSTEM_AND_STOP.pdf']],
 'runs':runs,'physical_io':0,'PCB_layout_created':False,'full_system_electrical_design_closed':False,'flight_arm_power_design_closed':False,'original_parent_unchanged':True}
(C/'results/STOP_ECAD_INTEGRATION.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in receipt.items() if k not in ['checks','runs','files','source_binding']},ensure_ascii=False))
