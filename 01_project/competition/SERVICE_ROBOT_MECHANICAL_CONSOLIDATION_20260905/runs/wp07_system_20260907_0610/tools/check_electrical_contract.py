"""Check WP07 electrical draft consistency and fail-closed energization conditions.

Default exit 0 means a consistent BLOCKED draft, not completed electrical design.
--require-ready exits 2 while any hardware or electrical input remains unresolved.
--self-test adds in-memory negative controls; it never touches source contracts.
No CAD, COM, third-party code, ECAD application or hardware execution.
"""
from __future__ import annotations
import argparse, copy, csv, datetime, hashlib, itertools, json, math
from pathlib import Path

R=Path(__file__).resolve().parents[1]
E=R/'ecad'
NAMES=['总布置/外包络','主次结构连接','B601及夹爪','保持释放','太阳翼','EPS','电池','OBC数据/任务计算','背板卡笼载板','ADCS','通信天线','感知','线束连接器','热控EMC','平移推进','AIT夹具维护']
REQUIRED=['selected_model','operating_voltage_range_v','continuous_current_a','peak_current_a','wire_cross_section_mm2','connector_part_number','pin_map','return_bonding_definition']

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def validate(contract,sources,cards,matrix,check_files=True):
    errors=[];blockers=[];facts=[]
    def need(ok,message):
        if not ok:errors.append(message)
    source_ids={s['id'] for s in sources['sources']}
    need(len(source_ids)==len(sources['sources']),'Duplicate source evidence IDs')
    for s in sources['sources']:
        if not check_files:continue
        p=Path(s['path'])
        if not p.is_file():errors.append('Missing evidence file '+str(p));continue
        need(sha(p)==s['sha256'],'Source hash changed '+s['id'])
        lines=p.read_text(encoding='utf-8-sig').splitlines()
        for excerpt in s['excerpts']:
            need('\n'.join(lines[excerpt['line_start']-1:excerpt['line_end']])==excerpt['text'],'Source excerpt changed '+s['id'])
    expected={f'M{i:02d}':name for i,name in enumerate(NAMES,1)}
    modules={m['id']:m for m in contract['modules']}
    need(len(contract['modules'])==16 and set(modules)==set(expected),'Must cover exact 16 functional domain IDs')
    need(contract.get('required_electrical_fields')==REQUIRED,'Required electrical input schema altered')
    need(contract.get('hardware_selection_user_reply')=='PENDING','Hardware response changed: independent contract revision/review required')
    for id,m in modules.items():
        applicable=[] if id in ('M01','M02') else (['return_bonding_definition'] if id=='M14' else [f for f in REQUIRED if f!='wire_cross_section_mm2' or id=='M13'])
        need(m['name_zh']==expected.get(id),'Module name differs '+id)
        need(m['coverage_kind']=='FUNCTIONAL_DOMAIN_NOT_EXCLUSIVE_MASS_OWNER','Functional mass ownership mislabeled '+id)
        need(m.get('electrically_active')==(id not in ('M01','M02','M09','M13','M14')),'Electrical activity classification differs '+id)
        need(m.get('electrical_interface_exists')==bool(applicable),'Interface applicability classification differs '+id)
        need(m.get('required_fields')==applicable and set(m['fields'])==set(applicable),'Conditional module field schema differs '+id)
        need(set(m['source_ids']).issubset(source_ids),'Unbound module evidence '+id)
        missing=[]
        for key in applicable:
            field=m['fields'].get(key,{})
            value=field.get('value');status=field.get('status')
            if status=='UNKNOWN':
                need(value is None,'UNKNOWN illegally filled '+id+'.'+key)
                need(not field.get('source_ids'),'Unknown field falsely cites numeric evidence '+id+'.'+key)
                missing.append(key)
            else:
                # This revision has no owner's selected hardware response. A later
                # board or measured input must enter through a reviewed new revision.
                errors.append('Actual input filled while hardware reply pending '+id+'.'+key)
                need(value is not None,'Known field missing value '+id+'.'+key)
        if missing:blockers.append(dict(id=id,missing=missing))
        need(m.get('energization_allowed') is False,'Module enables energization '+id)
        need(m.get('current_hardware_confirmed') is False,'Unconfirmed hardware promoted '+id)
        need(m.get('interface_complete') is False,'Unfinished interface promoted '+id)
    need(contract.get('hardware_energization_allowed') is False,'Global energization must stay blocked')
    need(contract.get('manufacturing_release') is False and contract.get('flight_qualification') is False,'Unjustified release claim')
    domains={d['id']:d for d in contract['voltage_domains']}
    need(domains.get('D_ARM_24_REFERENCE',{}).get('nominal_v')==24.,'B601 documented 24 V altered')
    need(domains.get('D_ORESAT_2S_REFERENCE',{}).get('range_v')==[6.,8.4],'OreSat reference domain altered')
    need(domains.get('D_GSE_24_REFERENCE',{}).get('rated_supply_current_a')==14.6,'Ground supply rating altered')
    need(domains.get('D_GSE_24_REFERENCE',{}).get('gse_only') is True,'GSE supply incorrectly treated as onboard')
    nodes={n['id']:n for n in contract['nodes']}
    need(len(nodes)==len(contract['nodes']),'Duplicate endpoint IDs')
    banned={frozenset(x) for x in contract['forbidden_direct_domain_pairs']}
    required_banned={frozenset(['D_ARM_24_REFERENCE','D_ORESAT_2S_REFERENCE']),frozenset(['D_GSE_24_REFERENCE','D_ORESAT_2S_REFERENCE']),frozenset(['D_ARM_24_REFERENCE','D_PYCUBED_2S_REFERENCE'])}
    need(required_banned<=banned,'Forbidden voltage pairs removed')
    for n in nodes.values():
        need(n.get('power_domain') is None or n['power_domain'] in domains,'Unknown power-domain label '+n['id'])
        need(n.get('selected_hardware') is False,'Reference endpoint treated as selected hardware '+n['id'])
    for edge in contract['edges']:
        a=nodes.get(edge['source']);b=nodes.get(edge['target'])
        need(a is not None and b is not None,'Undefined endpoint '+edge['id'])
        need(edge.get('implemented') is False and edge.get('energization_allowed') is False,'Unimplemented edge energized '+edge['id'])
        need(edge.get('status')=='PLANNED_NOT_WIRED','Draft edge status falsely closed '+edge['id'])
        for field in ('connector_part_number','pin_map','wire_cross_section_mm2','continuous_current_a','peak_current_a'):
            need(edge.get(field) is None,'Unselected wire input filled '+edge['id']+'.'+field)
        if edge['kind']=='power' and a and b:
            pair=frozenset([a.get('power_domain'),b.get('power_domain')])
            need(pair not in banned,'Forbidden direct voltage-domain mixing '+edge['id'])
            da=domains.get(a.get('power_domain'),{});db=domains.get(b.get('power_domain'),{})
            va=da.get('nominal_v');rb=db.get('range_v');vb=db.get('nominal_v');ra=da.get('range_v')
            if va is not None and rb:need(rb[0]<=va<=rb[1],'Direct source voltage outside receiving reference range '+edge['id'])
            if vb is not None and ra:need(ra[0]<=vb<=ra[1],'Direct receiving voltage incompatible with source reference range '+edge['id'])
    for card in cards['boards']:
        need(card.get('selected_for_wp07') is False and card.get('actual_component_selection') is None,'Reference ECAD promoted to hardware selection '+card['id'])
        need(card.get('energization_allowed') is False,'Reference board energization enabled '+card['id'])
        need(card.get('erc_status')=='NOT_RUN' and card.get('drc_status')=='NOT_RUN','Unexecuted ERC/DRC credit claimed '+card['id'])
        need(card.get('spacecraft_T_S_PCB') is None and card.get('populated_height_mm') is None,'Unmeasured board assembly placement/height filled '+card['id'])
        need(card['thickness_mm']>0 and math.isfinite(card['thickness_mm']),'Invalid actual board thickness')
        need(set(card['license_source_ids']).issubset(source_ids),'License source not bound '+card['id'])
        if check_files:
            for key in ('pcb','schematic'):
                path=Path(card[key+'_path'])
                need(path.is_file() and sha(path)==card[key+'_sha256'],'Actual ECAD hash changed '+card['id']+' '+key)
        facts.append(dict(id=card['id'],actual_outline_size_mm=card['outline']['size_mm'],thickness_mm=card['thickness_mm'],
                          mounting_drill_record_count=len(card['mounting_holes']),static_outline_complete=card['outline']['static_outline_complete']))
    need(len(matrix)==16 and {r['module_id'] for r in matrix}==set(expected),'CSV functional coverage differs')
    for row in matrix:
        need(row['name_zh']==expected.get(row['module_id']),'CSV module name differs')
        for k in ('actual_model_selected','electrical_interface_complete','energization_allowed'):
            need(row[k]=='False','CSV falsely promotes completion '+row['module_id']+' '+k)
        m=modules.get(row['module_id'])
        if m:
            need(row['completion_status']==m['completion_status'],'CSV/contract status mismatch '+m['id'])
            need(row['open_inputs']==';'.join(m['open_inputs']),'CSV/contract missing-input mismatch '+m['id'])
            need(row['required_fields']==';'.join(m['required_fields']),'CSV conditional input list mismatch '+m['id'])
            need(row['electrical_interface_exists']==str(m['electrical_interface_exists']),'CSV interface applicability differs '+m['id'])
    return dict(errors=errors,blockers=blockers,board_facts=facts,ready=False)

def negative_controls(c,s,b,m):
    cases=[]
    def case(name,mutator):
        x,y,z,w=copy.deepcopy((c,s,b,m));mutator(x,y,z,w)
        q=validate(x,y,z,w,False)
        cases.append(dict(id=name,rejected=bool(q['errors']),errors=q['errors']))
    case('UNKNOWN_CURRENT_ZERO_FILL',lambda x,y,z,w:x['modules'][2]['fields']['continuous_current_a'].update(value=0))
    case('UNKNOWN_WIRE_FILL',lambda x,y,z,w:x['modules'][12]['fields']['wire_cross_section_mm2'].update(value=0.5))
    case('UNKNOWN_PIN_MAP_FILL',lambda x,y,z,w:x['modules'][2]['fields']['pin_map'].update(value={'1':'24V'}))
    case('UNCONFIRMED_MODEL_FILL',lambda x,y,z,w:x['modules'][5]['fields']['selected_model'].update(status='CONFIRMED',value='P60'))
    case('GLOBAL_ENERGIZATION_BYPASS',lambda x,y,z,w:x.update(hardware_energization_allowed=True))
    def mixed(x,y,z,w):
        next(n for n in x['nodes'] if n['id']=='M09')['power_domain']='D_ORESAT_2S_REFERENCE'
        x['edges'][0].update(source='M03',target='M09')
    case('24V_TO_6_8_4V_DIRECT_CONNECTION',mixed)
    case('ECAD_REFERENCE_PROMOTED',lambda x,y,z,w:z['boards'][0].update(selected_for_wp07=True))
    case('MATRIX_COMPLETION_PROMOTED',lambda x,y,z,w:w[0].update(electrical_interface_complete='True'))
    case('ACTIVE_MODULE_REQUIREMENTS_OMITTED',lambda x,y,z,w:x['modules'][2].update(required_fields=[],fields={},electrical_interface_exists=False))
    return cases

def check_fit_screen(screen,cards):
    errors=[];boards={c['id']:c for c in cards['boards']}
    source=Path(screen['design_parameter_path'])
    if not source.is_file() or sha(source)!=screen['design_parameter_sha256']:
        return ['Fit screen budget source changed']
    boxes={x['name']:x['size_mm'] for x in read(source)['equipment']}
    if len(screen['rows'])!=len(boards)*len(boxes):errors.append('Fit screen pair coverage differs')
    if len({(r['board_id'],r['budget_id']) for r in screen['rows']})!=len(screen['rows']):errors.append('Fit screen duplicate pair')
    for r in screen['rows']:
        c=boards[r['board_id']];size=boxes[r['budget_id']]
        dims=c['outline']['size_mm']+[c['thickness_mm']]
        expected={order:[float(size[i])-dims[j] for i,j in enumerate(order)] for order in itertools.permutations(range(3))}
        observed={tuple(q['board_dimension_order_to_budget_xyz']):q for q in r['orientations']}
        if set(observed)!=set(expected):errors.append('Fit screen does not enumerate six orientations');continue
        for order,gaps in expected.items():
            q=observed[order]
            if q['budget_minus_bare_board_mm']!=gaps or q['bare_bbox_within_budget_outer_allocation']!=all(g>=0 for g in gaps):errors.append('Independent fit arithmetic differs '+r['board_id']+'/'+r['budget_id'])
        if r['axis_aligned_within_count']!=sum(all(g>=0 for g in gaps) for gaps in expected.values()):errors.append('Fit count differs')
        if r['actual_inner_cavity_evaluated'] or r['arbitrary_tilt_fit_evaluated'] or r['selected_hardware']:errors.append('Fit claim exceeds bare-board screen')
    for flag in ('physical_assembly_fit_pass','manufacturing_release','arbitrary_tilt_fit_evaluated','actual_inner_cavity_evaluated','component_height_evaluated','standoff_height_evaluated','cable_bend_and_connector_insertion_evaluated'):
        if screen.get(flag) is not False:errors.append('Fit report unsupported credit '+flag)
    if sha(screen['ecad_cards_path'])!=screen['ecad_cards_sha256']:errors.append('Fit report ECAD card hash differs')
    if sha(screen['script_path'])!=screen['script_sha256']:errors.append('Fit report generator hash differs')
    return errors

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--self-test',action='store_true');ap.add_argument('--require-ready',action='store_true')
    ap.add_argument('--output',type=Path,default=R/'results/ELECTRICAL_CONTRACT_CHECK.json')
    args=ap.parse_args();output=args.output.resolve()
    if not output.is_relative_to((R/'results').resolve()) or not output.name.startswith('ELECTRICAL_'):raise ValueError('Output outside owned ELECTRICAL results')
    paths=[E/'ELECTRICAL_INTERFACE_CONTRACT.json',E/'ELECTRICAL_SOURCES.json',E/'ECAD_REFERENCE_CARDS.json',E/'ELECTRICAL_MODULE_MATRIX.csv',R/'results/ELECTRICAL_BUILD_RECEIPT.json',R/'results/ELECTRICAL_MECHANICAL_FIT_SCREEN.json']
    before={str(p):sha(p) for p in paths}
    c,s,b=map(read,paths[:3])
    with paths[3].open(encoding='utf-8-sig',newline='') as f:m=list(csv.DictReader(f))
    result=validate(c,s,b,m)
    receipt=read(paths[4])
    for p in paths[:4]:
        if receipt.get('artifacts',{}).get(str(p))!=sha(p):result['errors'].append('Artifact hash differs from actual build receipt '+str(p))
    generator=Path(receipt['script_path'])
    if not generator.is_file() or sha(generator)!=receipt['script_sha256']:result['errors'].append('Generator source differs from build receipt')
    fit=read(paths[5]);fit_errors=check_fit_screen(fit,b);result['errors'].extend(fit_errors)
    tests=negative_controls(c,s,b,m) if args.self_test else []
    if tests and not all(x['rejected'] for x in tests):result['errors'].append('Negative control escaped rejection')
    after={str(p):sha(p) for p in paths}
    if after!=before:result['errors'].append('Reviewed contracts changed during check')
    result.update(schema='WP07_ELECTRICAL_CONTRACT_CHECK_V1',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        status='FAIL_CONTRACT_INCONSISTENCY' if result['errors'] else 'CONSISTENT_DRAFT_ELECTRICAL_COMPLETION_BLOCKED',
        contract_consistency_pass=not result['errors'],electrical_completion_pass=False,hardware_energization_allowed=False,
        module_count=len(m),open_module_count=len(result['blockers']),negative_controls=tests,
        mechanical_allocation_domains_without_independent_electrical_load=['M01','M02'],
        unique_minimum_input_groups=c.get('minimal_dependency_inputs',[]),
        fit_screen_independent_arithmetic_pass=not fit_errors,fit_screen_pair_count=len(fit['rows']),fit_screen_orientation_count=6*len(fit['rows']),
        input_hashes_before=before,input_hashes_after=after,script_path=str(Path(__file__).resolve()),script_sha256=sha(__file__),
        require_ready=args.require_ready,notes=['Review consistency is not an electrical or manufacturing release.','No ECAD/CAD/COM application or hardware was executed.'])
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('status','contract_consistency_pass','electrical_completion_pass','module_count','open_module_count','errors')},ensure_ascii=False))
    return 1 if result['errors'] else (2 if args.require_ready else 0)

if __name__=='__main__':raise SystemExit(main())
