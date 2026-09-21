"""Independent, label-free electrical topology checker for WP09F candidate rows.

validate(rows, allow_build=False, exit_conditions=None) accepts endpoint columns or
legacy from_device/from_pin/to_device/to_pin columns. net/signal labels are NEVER
read. This checks paths, not COTS internal safety, impedance, switching dynamics,
USB isolation, faults within unknown modules, or a manufacturer's release.

CLI --self-test uses frozen functional From-To plus current power endpoint contract;
CLI --input file.csv checks another row set. Both use no hardware I/O.
"""
from collections import defaultdict, deque
import argparse
import copy
import csv
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT.parent/'functional_closure'/'ecad'/'FUNCTIONAL_FROM_TO.csv'
POWER=ROOT/'power'/'POWER_ENDPOINT_CONTRACT.json'
REQUIRED_EXIT=('native_nonempty','native_netlist_match','erc_pass',
    'drc_pass_or_not_applicable','system_counterexamples_pass','object_release_authorized')
ALIASES={'K1.A2(+)':'K1.P_IN','K1.A1(-)':'K1.P_OUT'}
NC={'NC','N.C.','UNCONNECTED','NOT_CONNECTED'}
ARM_DEVICES={'PS1','Q1','K1','U1','RB1','SEP','DM','CAN','STOP_CONTROL','STOP_MONITOR'}
EPS_DEVICES={'PDU','OBC','BPX','DOCK','ACU','FPP','GSE_CHARGER'}

def normalize(value):
    if not isinstance(value,str) or not value.strip():raise ValueError('empty endpoint')
    value=value.strip()
    if value.startswith('PDU.X2.TFM.'):value='PDU.TFM.'+value[len('PDU.X2.TFM.'):]
    if value.startswith('A3200.'):value='OBC.'+value[len('A3200.'):]
    return ALIASES.get(value,value)

def endpoint(row,side):
    if side+'_endpoint' in row:return normalize(row[side+'_endpoint'])
    return normalize(str(row.get(side+'_device',''))+'.'+str(row.get(side+'_pin','')))

def bool_value(value):
    if type(value) is bool:return value
    if value in (0,1) and type(value) is int:return bool(value)
    if isinstance(value,str) and value.strip().lower() in ('false','0','no',''):return False
    if isinstance(value,str) and value.strip().lower() in ('true','1','yes'):return True
    raise ValueError('unrecognized approval boolean')

def make_graph(edges):
    graph=defaultdict(set)
    for a,b in edges:graph[a].add(b);graph[b].add(a)
    return graph

def path(graph,a,b):
    if a not in graph or b not in graph:return None
    q=deque([a]);seen={a:None}
    while q:
        current=q.popleft()
        if current==b:
            answer=[]
            while current is not None:answer.append(current);current=seen[current]
            return answer[::-1]
        for nxt in sorted(graph[current]):
            if nxt not in seen:seen[nxt]=current;q.append(nxt)
    return None

def components(graph):
    unseen=set(graph);out=[]
    while unseen:
        seed=min(unseen);q=[seed];comp=set()
        while q:
            x=q.pop()
            if x in comp:continue
            comp.add(x);q.extend(graph[x]-comp)
        unseen-=comp;out.append(comp)
    return out

def validate(rows,allow_build=False,exit_conditions=None):
    """Pure validation; external exit_conditions are NOT taken from rows.

    With no independent external exit proof, build_approved remains false even if
    topology passes. Incomplete nonempty candidates may pass ONLY this bounded
    graph test. Input is required to contain the ARM and OBC branches.
    """
    issues=[];edges=[];claimed=[];ignored=[]
    def issue(code,**detail):
        if not any(x['code']==code and x.get('path')==detail.get('path') for x in issues):
            issues.append({'code':code,**detail})
    if type(allow_build) is not bool:raise ValueError('allow_build is an external boolean')
    for i,row in enumerate(rows):
        row_id=row.get('wire_id',row.get('id',str(i)))
        try:
            a,b=endpoint(row,'from'),endpoint(row,'to')
            if a=='.' or b=='.' or a.startswith('.') or b.startswith('.') or a.endswith('.') or b.endswith('.'):
                raise ValueError('malformed endpoint')
            if bool_value(row.get('build_approved',False)):claimed.append(row_id)
            if a.upper() in NC or b.upper() in NC:ignored.append(row_id);continue
            if a==b:issue('SELF_CONNECTION',row_id=row_id,endpoint=a)
            edges.append((a,b))
        except (ValueError,TypeError) as error:issue('ROW_SCHEMA',row_id=row_id,error=str(error))

    # Explicit ideal through-paths only. Do not short all pins on any COTS object.
    fixed=[('U1.IN+','U1.OUT+'),('U1.IN-','U1.OUT-')]
    # RSP duplicate output terminals and BPX/Dock parallel power contacts.
    for group in ([f'PS1.TB2.{i}' for i in (1,2,3)], [f'PS1.TB2.{i}' for i in (4,5,6)],
                  [f'BPX.PBAT2.{i}' for i in (1,2,3,4,12)], [f'BPX.PBAT2.{i}' for i in (5,6,7,8)],
                  [f'DOCK.P4.{i}' for i in (1,2,3,4)], [f'DOCK.P4.{i}' for i in (5,6,7,8)]):
        fixed.extend((group[0],x) for x in group[1:])
    graphs={}
    for q_closed,k_closed in ((False,False),(False,True),(True,False),(True,True)):
        more=fixed+([('Q1.1','Q1.2')] if q_closed else [])+([('K1.P_IN','K1.P_OUT')] if k_closed else [])
        graphs[(q_closed,k_closed)]=make_graph(edges+more)
    full=graphs[(True,True)];open_q=graphs[(False,True)];open_k=graphs[(True,False)]
    for code,a,b in [('PDU_POS_RET_SHORT','PDU.TFM.9','PDU.TFM.10'),
                     ('ARM_POS_RET_SHORT','PS1.TB2.4','PS1.TB2.1'),
                     ('EPS_BATTERY_POS_RET_SHORT','BPX.PBAT2.5','BPX.PBAT2.1')]:
        p=path(full,a,b)
        if p:issue(code,path=p)
    for code,graph,a,b in [('Q1_BYPASS',open_q,'Q1.1','Q1.2'),('K1_BYPASS',open_k,'K1.P_IN','K1.P_OUT')]:
        p=path(graph,a,b)
        if p:issue(code,path=p)
    for code,a,b in [('ARM_SUPPLY_OPEN','PS1.TB2.4','DM.VCC_REF'),
                     ('ARM_RETURN_OPEN','PS1.TB2.1','DM.RET_REF'),
                     ('OBC_SUPPLY_OPEN','PDU.TFM.9','OBC.P1.2'),
                     ('OBC_RETURN_OPEN','PDU.TFM.10','OBC.P1.1')]:
        if path(full,a,b) is None:issue(code,required_path=[a,b])
    actual_nodes={n for pair in edges for n in pair}
    if any(n.startswith('BPX.') for n in actual_nodes):
        for code,a,b in [('BPX_DOCK_SUPPLY_OPEN','BPX.PBAT2.5','DOCK.P4.1'),
                         ('BPX_DOCK_RETURN_OPEN','BPX.PBAT2.1','DOCK.P4.5')]:
            if path(full,a,b) is None:issue(code,required_path=[a,b])
    for comp in components(full):
        arm=sorted(n for n in comp if n.split('.')[0] in ARM_DEVICES)
        eps=sorted(n for n in comp if n.split('.')[0] in EPS_DEVICES or n.startswith('PV_BRANCH_'))
        if arm and eps:issue('UNAUTHORIZED_ARM_EPS_LINK',path=path(full,arm[0],eps[0]))
    p=path(full,'PS1.TB2.4','BPX.PBAT2.5')
    if p:issue('RSP_BPX_SOURCE_PARALLEL',path=p)
    power_pins={'PS1.TB2.1','PS1.TB2.4','Q1.1','Q1.2','K1.P_IN','K1.P_OUT','U1.IN+','U1.IN-',
        'U1.OUT+','U1.OUT-','SEP.PWR','SEP.RET','DM.VCC_REF','DM.RET_REF','PDU.TFM.9','PDU.TFM.10',
        'OBC.P1.2','OBC.P1.1','BPX.PBAT2.5','BPX.PBAT2.1','DOCK.P4.1','DOCK.P4.5'}
    usb_pins={n for n in actual_nodes if n.upper().endswith('.VBUS') or n.upper().endswith('.USB_VBUS')}
    for u in sorted(usb_pins):
        for target in sorted(power_pins):
            p=path(full,u,target)
            if p:issue('USB_VBUS_BACKFEED_OR_SHORT',path=p);break
    topology_ok=not issues
    external_exit_ok=isinstance(exit_conditions,dict) and all(exit_conditions.get(k) is True for k in REQUIRED_EXIT)
    if claimed and not (allow_build and external_exit_ok and topology_ok):
        issue('BUILD_APPROVAL_WITHOUT_EXIT',row_ids=claimed,external_allow_build=allow_build,
              missing_exit=[k for k in REQUIRED_EXIT if not isinstance(exit_conditions,dict) or exit_conditions.get(k) is not True],
              topology_ok=topology_ok)
    return {'status':'PASS_SCOPED_TOPOLOGY_ONLY' if not issues else 'FAIL',
            'topology_pass':topology_ok,'issue_codes':sorted({x['code'] for x in issues}),'issues':issues,
            'wire_edges':len(edges),'nc_rows_ignored':ignored,'row_approval_claims':claimed,
            'external_exit_conditions_satisfied':bool(external_exit_ok),
            'build_approved':bool(claimed and allow_build and external_exit_ok and not issues),
            'scenarios':{f'Q_{"CLOSED" if q else "OPEN"}_K_{"CLOSED" if k else "OPEN"}':
                {'q_closed':q,'k_closed':k,
                 'source_to_load_connected':path(graph,'PS1.TB2.4','DM.VCC_REF') is not None,
                 'source_to_load_path':path(graph,'PS1.TB2.4','DM.VCC_REF')}
                for (q,k),graph in graphs.items()},
            'scope':'Undirected ideal wire connectivity, explicit power-contact bonds and U1 through paths. No label connectivity, COTS behavior, dynamic fault energy, or hardware validation credit.',
            'unresolved_internal_paths':['USB-CAN VBUS/backfeed/ground isolation inside hardware','Regen clamp loss-of-input and thermal shutdown','PDU/Dock/ACU conversion and fault-isolation behavior'],
            'physical_io_operations':0}

def reference_rows():
    old=list(csv.DictReader(OLD.open(encoding='utf-8-sig',newline='')))
    rows=[]
    # Explicit local candidate delta; parent CSV is never changed.
    for row in old:
        if row['wire_id'] in ('A02','A03','A05','L01','L02'):continue
        r=dict(row)
        if r['wire_id']=='A04':
            r.update(from_endpoint='PS1.TB2.1',to_endpoint='U1.IN-')
        rows.append(r)
    p=json.loads(POWER.read_text(encoding='utf-8-sig'))
    for row in p['endpoints']:
        r=dict(row);r['build_approved']=False;rows.append(r)
    return rows

def self_test():
    base=reference_rows();tests=[]
    def run(name,rows,expected=(),**kwargs):
        got=validate(rows,**kwargs)
        ok=(got['status']=='PASS_SCOPED_TOPOLOGY_ONLY') if not expected else set(expected)<=set(got['issue_codes'])
        tests.append({'name':name,'passed':ok,'expected_codes':list(expected),'result':got})
    def added(a,b):return base+[{'from_endpoint':a,'to_endpoint':b,'build_approved':False,'net':'INNOCENT_LABEL'}]
    run('candidate_baseline',base)
    run('pdu_9_10_short',added('PDU.TFM.9','PDU.TFM.10'),('PDU_POS_RET_SHORT',))
    run('pdu_alias_short_mislabelled',added('PDU.X2.TFM.9','PDU.X2.TFM.10'),('PDU_POS_RET_SHORT',))
    run('q1_bypass',added('Q1.1','Q1.2'),('Q1_BYPASS',))
    run('k1_bypass',added('K1.A2(+)','K1.A1(-)'),('K1_BYPASS',))
    run('arm_return_removed',[r for r in base if r.get('wire_id')!='A10'],('ARM_RETURN_OPEN',))
    run('obc_return_removed',[r for r in base if r.get('id')!='L02'],('OBC_RETURN_OPEN',))
    run('cross_domain_return',added('PS1.TB2.1','OBC.P1.1'),('UNAUTHORIZED_ARM_EPS_LINK',))
    run('cross_domain_signal',added('CAN.H','PDU.TFM.23'),('UNAUTHORIZED_ARM_EPS_LINK',))
    run('usb_vbus_backfeed',added('USB.VBUS','U1.OUT+'),('USB_VBUS_BACKFEED_OR_SHORT',))
    run('usb_vbus_to_return',added('CAN.USB_VBUS','PDU.TFM.10'),('USB_VBUS_BACKFEED_OR_SHORT',))
    run('rsp_bpx_positive_parallel',added('PS1.TB2.4','DOCK.P4.1'),('RSP_BPX_SOURCE_PARALLEL',))
    approved=copy.deepcopy(base);approved[0]['build_approved']='true'
    run('row_cannot_self_approve',approved,('BUILD_APPROVAL_WITHOUT_EXIT',))
    run('external_allow_without_exit_still_rejected',approved,('BUILD_APPROVAL_WITHOUT_EXIT',),allow_build=True)
    run('row_forged_exit_not_trusted',[dict(r,exit_conditions={k:True for k in REQUIRED_EXIT}) for r in approved],('BUILD_APPROVAL_WITHOUT_EXIT',),allow_build=True)
    fake_exit={k:True for k in REQUIRED_EXIT}
    unsafe=copy.deepcopy(added('PDU.TFM.9','PDU.TFM.10'));unsafe[0]['build_approved']=True
    run('external_exit_cannot_override_topology',unsafe,('BUILD_APPROVAL_WITHOUT_EXIT','PDU_POS_RET_SHORT'),allow_build=True,exit_conditions=fake_exit)
    relabelled=[dict(r,net='ALL_LABELS_IDENTICAL',signal='WRONG_UNRELATED_TEXT') for r in base]
    run('wrong_labels_do_not_merge_electrical_nodes',relabelled)
    run('transitive_q_bypass',base+[{'from_endpoint':a,'to_endpoint':b,'build_approved':False} for a,b in [('Q1.1','TP_X.1'),('TP_X.1','Q1.2')]],('Q1_BYPASS',))
    run('transitive_pdu_short',base+[{'from_endpoint':a,'to_endpoint':b,'build_approved':False} for a,b in [('PDU.TFM.9','TP_X.2'),('TP_X.2','OBC.P1.1')]],('PDU_POS_RET_SHORT',))
    run('nc_endpoints_not_common_net',base+[{'from_endpoint':a,'to_endpoint':'NC','build_approved':False} for a in ['PDU.TFM.9','PDU.TFM.10']])
    run('bad_approval_string_fail_closed',base+[{'from_endpoint':'NC','to_endpoint':'OBC.P1.3','build_approved':'maybe'}],('ROW_SCHEMA',))
    run('empty_candidate_not_pass',[],('ARM_SUPPLY_OPEN','ARM_RETURN_OPEN','OBC_SUPPLY_OPEN','OBC_RETURN_OPEN'))
    # Inputs are hash bound; tests alter in-memory copies only.
    files=[OLD,POWER,Path(__file__).resolve()]
    receipt={'status':'PASS_INDEPENDENT_SYSTEM_GRAPH_COUNTEREXAMPLES' if all(x['passed'] for x in tests) else 'FAIL',
        'test_count':len(tests),'passed':sum(x['passed'] for x in tests),'tests':tests,
        'input_hashes':[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files],
        'baseline_delta':['A02/A03 replaced by named GX11 positive contact contract','A04 changed to PS1.TB2.1 directly to U1.IN-','A05 removed; no negative K1 switch','L01/L02 use current power endpoint aliases'],
        'independence':'BFS path / connected components written independently; no import of previous electrical validator, no net/signal labels read',
        'actual_main_csv_check':'NOT_EXECUTED_BY_SELF_TEST; caller must pass generated current rows to validate',
        'cots_behavior':'NOT_EVALUATED; ideal U1 through-paths and known parallel supply contacts only',
        'build_approved':False,'physical_io_operations':0}
    (ROOT/'results'/'ECAD_SYSTEM_GRAPH_TESTS.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':receipt['status'],'tests':len(tests),'passed':receipt['passed']}))
    return 0 if receipt['status'].startswith('PASS') else 1

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--self-test',action='store_true');parser.add_argument('--input',type=Path)
    args=parser.parse_args()
    if args.input:
        rows=list(csv.DictReader(args.input.open(encoding='utf-8-sig',newline='')))
        result=validate(rows);print(json.dumps(result,ensure_ascii=False,indent=2))
        raise SystemExit(0 if result['status'].startswith('PASS') else 1)
    raise SystemExit(self_test())
