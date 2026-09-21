"""Independent source, net, geometry and counterexample acceptance for V32."""
from pathlib import Path
import copy,csv,hashlib,json,math,xml.etree.ElementTree as ET
from erc_source_contract import parse,enc,children,val,properties,source_inventory

A=Path(__file__).resolve().parents[1]; E=A/'ecad'; D=E/'revisions/v32'; R=A/'results/kelvin_v32'

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def dump(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def canonical_board(path,ignore_jumpers=True):
    t=parse(path.read_text(encoding='utf-8-sig'))
    for f in children(t,'footprint'):
        if ignore_jumpers and properties(f).get('Reference') in ['R201','R202']:
            f[:]=[x for x in f if not isinstance(x,list) or x[0]!='duplicate_pad_numbers_are_jumpers']
        for m in children(f,'model'):
            name=val(m[1])
            if name.startswith('${KIPRJMOD}/'):
                m[1]=json.dumps(str((path.parent/name.split('${KIPRJMOD}/',1)[1]).resolve()))
    return t

def xml_comp(c,ignore_jumpers=True):
    def entry(e):
        return (e.tag,tuple(sorted(e.attrib.items())),(e.text or '').strip(),
                tuple(entry(x) for x in e if not(ignore_jumpers and x.tag=='duplicate_pin_numbers_are_jumpers')))
    return entry(c)

def main():
    checks=[]
    def ck(name,passed,**detail):
        checks.append(dict(name=name,passed=bool(passed),**detail))
    lock=read(R/'PARENT_SOURCE_LOCK.json')
    ck('all_prechange_source_bytes_preserved',all(Path(p).is_file() and sha(p)==h for p,h in lock.items()),files=len(lock))
    parent=read(A/'coupled_closure/CANDIDATE_V30.json')
    ck('V30_complete_source_lock_preserved',all(Path(p).is_file() and sha(p)==h for p,h in parent['source_lock'].items()),files=len(parent['source_lock']))
    old=ET.parse(E/'wp10_system.xml').getroot(); new=ET.parse(D/'wp10_system.xml').getroot()
    oc={c.get('ref'):c for c in old.findall('./components/comp')}; nc={c.get('ref'):c for c in new.findall('./components/comp')}
    ck('all_component_metadata_preserved_except_target_internal_connections',set(oc)==set(nc) and all(xml_comp(c)==xml_comp(nc[r]) for r,c in oc.items()),components=len(nc))
    def nodes(t):return sorted((n.get('name'),tuple(sorted(p.attrib.items()))) for n in t.findall('./nets/net') for p in n.findall('node'))
    ck('all_native_net_pin_records_unchanged',nodes(old)==nodes(new),pin_records=len(nodes(new)))
    ck('native_XML_carries_exact_two_internal_connections',
       sorted(c.get('ref') for c in nc.values() if c.findtext('duplicate_pin_numbers_are_jumpers')=='1')==['R201','R202'])
    sn=parse((D/'wp10_system.net').read_text(encoding='utf-8'))
    comps=children(children(sn,'components')[0],'comp')
    marked=[]
    for c in comps:
        j=children(c,'duplicate_pin_numbers_are_jumpers')
        if j and val(j[0][1])=='1':marked.append(val(children(c,'ref')[0][1]))
    ck('forward_netlist_carries_same_two_attributes',sorted(marked)==['R201','R202'])
    ck('full_board_AST_geometry_and_nets_preserved',canonical_board(E/'wp10_main_input.kicad_pcb')==canonical_board(D/'wp10_main_input.kicad_pcb'))
    board=parse((D/'wp10_main_input.kicad_pcb').read_text(encoding='utf-8'))
    target_fps=[f for f in children(board,'footprint') if properties(f).get('Reference') in ['R201','R202']]
    ck('attributes_present_on_exact_target_board_instances',len(target_fps)==2 and all(children(f,'duplicate_pad_numbers_are_jumpers')==[['duplicate_pad_numbers_are_jumpers','yes']] for f in target_fps))
    kfp=parse((D/'WP10_INPUT.pretty/WSLP2726_KelvinSplit_TwoTerminals.kicad_mod').read_text(encoding='utf-8'))
    ck('footprint_library_persists_internal_terminal_model',children(kfp,'duplicate_pad_numbers_are_jumpers')==[['duplicate_pad_numbers_are_jumpers','yes']])
    dims=[]
    for pin in ['1','2']:
        pads=[p for p in children(kfp,'pad') if val(p[1])==pin]
        pads.sort(key=lambda p:float(children(p,'size')[0][2]),reverse=True)
        large,small=pads
        ly=float(children(large,'at')[0][2]); sy=float(children(small,'at')[0][2])
        lh=float(children(large,'size')[0][2]); sh=float(children(small,'size')[0][2])
        gap=(sy-sh/2)-(ly+lh/2)
        dims.append(dict(pin=pin,large_size_mm=[float(x) for x in children(large,'size')[0][1:3]],
                         small_size_mm=[float(x) for x in children(small,'size')[0][1:3]],gap_mm=gap))
    ck('OEM_split_land_dimensions_and_gap_preserved',all(d['large_size_mm']==[2.69,5.71] and d['small_size_mm']==[2.69,.89] and math.isclose(d['gap_mm'],.89,abs_tol=1e-9) for d in dims),dimensions=dims)
    ck('no_cross_terminal_jumper_group_added',not children(kfp,'jumper_pad_groups') and all(not children(f,'jumper_pad_groups') for f in target_fps))
    model_rows=[]
    for path in [D/'wp10_main_input.kicad_pcb',*D.glob('*.pretty/*.kicad_mod')]:
        t=parse(path.read_text(encoding='utf-8-sig'))
        fs=children(t,'footprint') if t[0]=='kicad_pcb' else [t]
        for f in fs:
            for m in children(f,'model'):
                name=val(m[1])
                if name.startswith('${KIPRJMOD}/'):
                    resolved=(D/name.split('${KIPRJMOD}/',1)[1]).resolve()
                    model_rows.append(dict(source=path.relative_to(D).as_posix(),path=name,resolved=str(resolved),exists=resolved.is_file(),sha256=sha(resolved) if resolved.is_file() else None))
    ck('all_project_relative_board_and_library_models_resolve',len(model_rows)==7 and all(x['exists'] for x in model_rows),model_references=len(model_rows))
    report=read(R/'MAIN_INPUT_DRC.json'); prior=read(A/'results/MAIN_INPUT_DRC_V29.json')
    ck('native_DRC_clear_under_unchanged_rules',not report['violations'] and not report['unconnected_items'] and report['ignored_checks']==prior['ignored_checks'],ignored_rules=report['ignored_checks'])
    erc=read(R/'SYSTEM_ERC.json'); _,pages,_=source_inventory(D/'wp10_system.kicad_sch')
    ck('entire_active_hierarchy_native_ERC_clean',len(erc['sheets'])==len(pages)==13 and all(not s['violations'] for s in erc['sheets']),sheets=len(pages))
    negatives=read(R/'COUNTEREXAMPLES.json')
    ck('native_negative_cases_detect_false_model_and_real_broken_trace',negatives['passed'] and [x['unconnected_items'] for x in negatives['cases']]==[2,1])
    case=read(R/'negative_broken_VIN_sense_DRC.json')
    ck('dangling_track_reported_as_warning_not_error',len(case['violations'])==1 and case['violations'][0]['severity']=='warning' and case['violations'][0]['type']=='track_dangling')
    copper=read(A/'power/MAIN_INPUT_COPPER_LOSS_V29.json')
    recalculated=sum(s['R20_ohm'] for s in copper['main_path_segments'])
    ck('inherited_conditional_series_copper_sum_recomputed',math.isclose(recalculated,copper['R20_ohm'],abs_tol=1e-12),R20_ohm=recalculated,model_scope=copper['method'])
    csv_rows=list(csv.DictReader((A/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig')))
    ck('original_37_closure_identities_remain',len(csv_rows)==37 and len({r['id'] for r in csv_rows})==37)
    result=dict(scope='Four Kelvin EDA connection-expression issues only',passed=all(c['passed'] for c in checks),
                checks=checks,checks_run=len(checks),active_component_count=len(nc),active_pin_record_count=len(nodes(new)),
                model_references=model_rows,full_system_PCB_schematic_parity_checked=False,whole_design_complete=False,
                hardware_tests=0,native_whole_spacecraft_rebuilds=0)
    dump(R/'VALIDATION.json',result)
    print(json.dumps({'passed':result['passed'],'checks':len(checks),'failed':[x for x in checks if not x['passed']],'refs':len(nc),'pin_records':len(nodes(new))},ensure_ascii=False))
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
