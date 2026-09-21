from pathlib import Path
import csv,json,hashlib,xml.etree.ElementTree as ET,importlib.util,collections
N=Path(__file__).resolve().parents[1];E=N/'ecad'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def js(p):return json.loads(Path(p).read_text(encoding='utf8'))
rows=list(csv.DictReader((E/'MASTER_FROM_TO.csv').open(encoding='utf-8-sig')));mapping=js(E/'wp09_system_ENDPOINT_MAP.json')
root=ET.parse(E/'exports/wp09_system.xml').getroot();found={};groups=[]
for net in root.findall('./nets/net'):
 members={(x.get('ref'),x.get('pin')) for x in net.findall('node')};groups.append(members)
 for x in members:assert x not in found;found[x]=net.get('code')
checks=[]
for row in rows:
 a=mapping[row['from_endpoint']];b=mapping[row['to_endpoint']];aa=(a['ref'],a['pin']);bb=(b['ref'],b['pin'])
 checks.append(dict(wire_id=row['wire_id'],pass_=aa in found and bb in found and found[aa]==found[bb],actual_net=found.get(aa)))
expected=collections.defaultdict(set)
for ep,m in mapping.items():expected[m['net']].add((m['ref'],m['pin']))
exact={frozenset(v) for v in expected.values()}=={frozenset(v) for v in groups}
assert all(x['pass_'] for x in checks) and exact
# Independent endpoint-only graph consumes physical wire rows; map actual exported nets
# back to endpoints, so a label/EDA accident cannot escape the system checker.
sp=importlib.util.spec_from_file_location('graph_check',E/'system_graph_check.py');g=importlib.util.module_from_spec(sp);sp.loader.exec_module(g)
topology=g.validate(rows);assert topology['topology_pass']
inverse={(v['ref'],v['pin']):k for k,v in mapping.items()};exported_rows=[]
for group in groups:
 xs=sorted(group)
 for x in xs[1:]:exported_rows.append(dict(from_endpoint=inverse[xs[0]],to_endpoint=inverse[x],build_approved=False))
exported_topology=g.validate(exported_rows);assert exported_topology['topology_pass']
negative=exported_rows+[dict(from_endpoint='PDU.TFM.9',to_endpoint='PDU.TFM.10',build_approved=False)]
neg=g.validate(negative);assert not neg['topology_pass']
# Board and its generated native schematic netlist: exactly five isolated groups of A/B/TP.
boardxml=ET.parse(E/'exports/rs422_gse_splice.xml').getroot()
bg=[{(x.get('ref'),x.get('pin')) for x in net.findall('node')} for net in boardxml.findall('./nets/net')]
assert {frozenset(v) for v in bg}=={frozenset({('A'+str(i),'1'),('B'+str(i),'1'),('TP'+str(i),'1')}) for i in range(1,6)}
erc=js(E/'exports/rs422_gse_splice_erc.json');drc=js(E/'exports/rs422_gse_splice_drc.json');ev=[v for z in erc['sheets'] for v in z['violations']]
assert not ev and not drc['violations'] and not drc['schematic_parity'] and not drc['unconnected_items']
sys_erc=js(E/'exports/wp09_system_erc.json');sv=[v for z in sys_erc['sheets'] for v in z['violations']]
assert len(sv)==1 and sv[0]['type']=='power_pin_not_driven'
report=dict(status='PASS_NATIVE_EDA_BINDING_AND_GROUND_SPLICE; SYSTEM_ERC_ONE_OPEN_POWER_BOUNDARY',tool='KiCad10.0.6',wire_rows=len(rows),endpoint_count=len(mapping),net_count=len(groups),row_checks=checks,exact_partition_match=exact,system_topology=topology,exported_netlist_topology=exported_topology,pdu_short_on_export_rejected=neg,splice=dict(pads=15,nets=5,erc_violations=0,drc_violations=0,parity_violations=0,unconnected=0,ignored_erc_defaults=erc['ignored_checks'],ignored_drc_defaults=drc['ignored_checks']),system_erc_open=sv,system_erc_disposition='U1.IN+ not driven across external Q/K passive contact boundaries; no PWR_FLAG and no rule exclusion. Hardware stop power/regen remains OPEN.',upstream_identity='OreSat original read-only; isolated copy ERC11warnings, DRC2courtyard errors plus other warnings; no inherited PASS',sources={str(p.relative_to(N)):sha(p) for p in [E/'MASTER_FROM_TO.csv',E/'wp09_system.kicad_sch',E/'rs422_gse_splice.kicad_sch',E/'rs422_gse_splice.kicad_pcb',E/'exports/wp09_system.xml',E/'exports/rs422_gse_splice.xml',E/'system_graph_check.py']},build_approved=False,hardware_operations=0)
(N/'results/ECAD_VERIFICATION.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf8')
print(report['status']);print('70 rows /117 endpoints /47 exact nets;15pads/5nets board ERC DRC parity PASS')
