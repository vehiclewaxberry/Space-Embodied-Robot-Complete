"""Audit conditional ERC declarations in source, independently of hidden # netlist items.

Declarations describe the existing design topology; never infer that hardware is
energized, a battery interface is bound, or a semiconductor switches correctly.
"""
from pathlib import Path
import ast, collections, copy, hashlib, json, re, xml.etree.ElementTree as ET

A = Path(__file__).resolve().parents[1]
H = A / 'history/20260909_V15_before_erc_declarations'
PAGE = 'wp10_power_declarations.kicad_sch'
ns = {'json': json, 're': re}
tree = ast.parse((A.parent/'tools/integrate_ecad.py').read_text(encoding='utf-8'))
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ['parse','enc','val','children','walk']],type_ignores=[]),'parent_pure_parser','exec'),ns)
parse, enc, val, children, walk = [ns[k] for k in ['parse','enc','val','children','walk']]

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def dump(p, x): Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def properties(node): return {val(x[1]):val(x[2]) for x in children(node,'property')}
def node_uuid(node): return val(children(node,'uuid')[0][1])

def physical_netlist(path):
    rt=ET.parse(path).getroot()
    comps={c.get('ref'):(c.findtext('value'),c.findtext('footprint')) for c in rt.findall('./components/comp')}
    pins={(n.get('ref'),n.get('pin')):(net.get('name'),n.get('pintype')) for net in rt.findall('./nets/net') for n in net.findall('node') if not n.get('ref','').startswith('#')}
    return comps,pins

def active_sheet_paths():
    root=parse((A/'ecad/wp10_system.kicad_sch').read_text(encoding='utf-8'))
    rid='/'+node_uuid(root)
    return {rid}|{rid+'/'+node_uuid(s) for s in children(root,'sheet')}

def native_erc_summary(report, returncode=0):
    sheets=report.get('sheets',[])
    valid=isinstance(sheets,list) and bool(sheets) and all(isinstance(s,dict) and isinstance(s.get('violations'),list) for s in sheets)
    rows=[v for sheet in sheets for v in sheet['violations']] if valid else []
    counts=collections.Counter(v['severity'] for v in rows)
    paths=[s.get('uuid_path') for s in sheets] if valid else []
    valid=valid and len(paths)==len(set(paths)) and set(paths)==active_sheet_paths()
    valid=valid and report.get('source')=='wp10_system.kicad_sch' and report.get('kicad_version')=='10.0.6'
    valid=valid and set(report.get('included_severities',[]))=={'error','warning'}
    return dict(command_succeeded=returncode==0, report_valid=bool(valid), errors=counts['error'], warnings=counts['warning'],
                violations=len(rows), ERC_clean=returncode==0 and bool(valid) and not rows,
                ignored_checks=report.get('ignored_checks',[]))

def source_inventory(root_path):
    """Follow only the active hierarchy. Capture every power_out declaration."""
    flags=[]; sheets=[]; seen=set(); other_outputs=[]
    def visit(path):
        path=path.resolve()
        if path in seen: raise ValueError('repeated/cyclic sheet: '+str(path))
        seen.add(path); sheets.append(path)
        node=parse(path.read_text(encoding='utf-8-sig'))
        libs={val(s[1]):s for block in children(node,'lib_symbols') for s in children(block,'symbol')}
        labels=children(node,'global_label')
        for s in children(node,'symbol'):
            props=properties(s); ref=props.get('Reference'); lid=val(children(s,'lib_id')[0][1])
            lib=libs[lid]; power_pins=[p for sub in children(lib,'symbol') for p in children(sub,'pin') if p[1]=='power_out']
            # # symbols are normally omitted from exported component/net lists.
            declaration=ref.startswith('#') or props.get('Value')=='PWR_FLAG' or lid.endswith(':PWR_FLAG')
            if declaration:
                at=children(s,'at')[0]; xy=tuple(float(v) for v in at[1:3])
                hits=[val(l[1]) for l in labels if tuple(float(v) for v in children(l,'at')[0][1:3])==xy]
                flags.append(dict(reference=ref,uuid=node_uuid(s),library=lid,sheet=path.relative_to(A).as_posix(),
                                  nets=hits,power_output_pins=len(power_pins),position=list(xy),
                                  in_bom=children(s,'in_bom')[0][1],on_board=children(s,'on_board')[0][1],
                                  instances=children(s,'instances')))
            elif power_pins: other_outputs.extend((ref,val(children(p,'number')[0][1])) for p in power_pins)
        for s in children(node,'sheet'):
            pp=properties(s); name=pp.get('Sheetfile',pp.get('Sheet file'))
            if not name: raise ValueError('sheet file missing')
            visit(path.parent/name)
    visit(Path(root_path))
    return flags,sheets,other_outputs

def audit_contract(contract, root_path=None, xml_path=None):
    root_path=Path(root_path or A/'ecad/wp10_system.kicad_sch')
    xml_path=Path(xml_path or A/'ecad/wp10_system.xml')
    flags,sheets,outputs=source_inventory(root_path)
    oldc,oldp=physical_netlist(H/'ecad/wp10_system.xml');newc,newp=physical_netlist(xml_path)
    checks=[]
    def ck(name, passed, **kw): checks.append(dict(name=name,passed=bool(passed),**kw))
    expected_c=dict(oldc)
    expected_c['C203']=(oldc['C203'][0],read(A/'power/CAP_TERMINAL_DEFINITION.json')['footprint'])
    ck('201_entities_only_C203_terminal_footprint_changed',newc==expected_c and len(newc)==201)
    ck('exact_657_pin_network_and_type_preserved',newp==oldp and len(newp)==657)
    ck('seven_declared_instances_only',len(flags)==7 and {f['reference'] for f in flags}=={d['reference'] for d in contract['declarations']})
    for d in contract['declarations']:
        matches=[f for f in flags if f['reference']==d['reference']]
        f=matches[0] if len(matches)==1 else {}
        ck('source_'+d['reference'],all(f.get(k)==d[k] for k in ['uuid','library','sheet','position','instances']) and f.get('nets')==[d['net']] and f.get('power_output_pins')==1 and f.get('in_bom')=='no' and f.get('on_board')=='no')
        for pin,net in d['required_nodes'].items():
            r,p=pin.rsplit('.',1);ck(d['reference']+'_'+pin,newp.get((r,p),(None,None))[0]==net)
    ck('primary_secondary_returns_separate',newp[('U203','4')][0]!=newp[('U203','5')][0])
    ck('positive_converter_outputs_not_paralleled',newp[('U202','4')][0]!=newp[('U203','9')][0])
    ck('declared_hardware_and_dynamic_credit_false',all(contract[k] is False for k in ['hardware_qualified','battery_OEM_interface_bound','operating_state_simulation','whole_design_complete']))
    ck('exact_source_bindings',all(sha(A/p)==h for p,h in contract['source_bindings'].items()))
    ck('active_declaration_page_matches_frozen_MCP_source',sha(root_path.parent/PAGE)==sha(A/'power/erc_sources'/PAGE))
    old_flags,old_sheets,old_outputs=source_inventory(H/'ecad/wp10_system.kicad_sch')
    ck('existing_output_pin_roles_preserved',sorted(outputs)==sorted(old_outputs))
    return dict(schema='WP10_ERC_SOURCE_AUDIT_V16',passed=all(c['passed'] for c in checks),check_count=len(checks),checks=checks,
                native_entity_count=len(newc),pin_net_type_count=len(newp),declaration_count=len(flags),sheet_count=len(sheets),
                inputs={p.relative_to(A).as_posix():sha(p) for p in sheets+[xml_path,A/'power/ERC_SOURCE_DECLARATIONS.json',A/'tools/erc_source_contract.py',A/'power/CAP_TERMINAL_DEFINITION.json']},
                hardware_qualified=False,whole_design_complete=False)

def supply_state(source=True,f201=True,f202=True,q201=True,chb=True,q203=True,k1=True,regen=False):
    """Boolean route conditions only; NOT switching simulation or measured power."""
    main=source and f201
    pre=main and q201
    local=pre and chb
    aux=source and f202
    # Q202 body diode can supply the common drain; Q203 body diode can
    # supply it from ARM_BUS via closed K1. Neither proves valid VS voltage.
    common=local or (regen and k1)
    arm=(local and q203 and k1) or regen
    return dict(MAIN_FUSED=main,AUX_FUSED=aux,PRECHARGED_PLUS=pre,RB_COMMON_DRAIN=common,ARM_BUS_PLUS=arm)

if __name__=='__main__':
    result=audit_contract(read(A/'power/ERC_SOURCE_DECLARATIONS.json'))
    dump(A/'results/ERC_SOURCE_VALIDATION.json',result)
    print(json.dumps({k:result[k] for k in ['passed','check_count','native_entity_count','pin_net_type_count','declaration_count','sheet_count']}))
    assert result['passed'],[c for c in result['checks'] if not c['passed']]
