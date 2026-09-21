"""Independent arithmetic and protocol checks; no CAD or hardware execution."""
from pathlib import Path
import hashlib, json, math, csv, copy, importlib.util

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
WP = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def shift(m, c):
    norm = math.fsum(v*v for v in c)
    return [[m*((norm if i == j else 0)-c[i]*c[j]) for j in range(3)] for i in range(3)]


def matrix_error(a, b):
    return max(abs(a[i][j]-b[i][j]) for i in range(3) for j in range(3))


def main():
    dp = WP / 'results/DYNAMICS_HANDOFF.json'
    d = json.loads(dp.read_text(encoding='utf-8'))
    paths = [Path(p) for p in d['input_sha256']] + [dp, WP/'BOM.csv']
    before = {str(p):sha(p) for p in paths}
    input_failures = [p for p,h in d['input_sha256'].items() if before[p] != h]
    state_results=[]
    evaluated_states=d['states'] + [{'state':v['state']+'_GSE_ONLY', 'groups':{'GSE':v['GSE_ledger']}} for v in d['ground_AIT_views']]
    for s in evaluated_states:
        roles=[]
        for role,g in s['groups'].items():
            atoms=g['mass_atoms']
            if not atoms:
                continue
            owners=[a['mass_owner'] for a in atoms]
            m=math.fsum(a['mass_kg'] for a in atoms)
            c=[math.fsum(a['mass_kg']*a['center_of_mass_S_m'][i] for a in atoms)/m for i in range(3)]
            contributions=[]
            for a in atoms:
                pa=shift(a['mass_kg'],a['center_of_mass_S_m'])
                contributions.append([[a['inertia_about_COM_S_kg_m2'][i][j]+pa[i][j] for j in range(3)] for i in range(3)])
            origin=[[math.fsum(x[i][j] for x in contributions) for j in range(3)] for i in range(3)]
            pa=shift(m,c)
            about_c=[[origin[i][j]-pa[i][j] for j in range(3)] for i in range(3)]
            recorded=g['allocated_complete_property_subset']
            error={'mass_kg':abs(m-g['known_mass_kg']),
                'COM_m':max(abs(a-b) for a,b in zip(c,recorded['center_of_mass_S_m'])),
                'I_C_kg_m2':matrix_error(about_c,recorded['inertia_about_COM_S_kg_m2']),
                'I_S_kg_m2':matrix_error(origin,recorded['inertia_about_S_origin_S_kg_m2'])}
            roles.append({'role':role,'known_mass_kg':m,'positive_atoms':len(atoms),
                'unique_mass_owners':len(set(owners)), 'duplicate_mass_owners':len(owners)!=len(set(owners)),
                'unknown_mass_instance_count':len(g['unknown_mass_instances']),
                'unknowns_preserved':all(a.get('reason')=='MASS_UNKNOWN_NOT_ZERO' for a in g['unknown_mass_instances']),
                'errors':error,'arithmetic_matches':max(error.values())<1e-12})
        state_results.append({'state':s['state'],'groups':roles})
    with (WP/'BOM.csv').open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    values=[float(r['allocated_dynamics_mass_kg']) for r in rows if r['allocated_dynamics_mass_kg'] not in ('','null','None')]
    service=next(s for s in d['states'] if s['state']=='service')
    service_mass=service['groups']['ONBOARD_CANDIDATE']['known_mass_kg']
    controls=json.loads((HERE.parent/'a4/STRICT_AGGREGATOR_CONTROLS.json').read_text(encoding='utf-8'))
    proto=HERE.parent/'a4/strict_surface_aggregator.py'
    spec=importlib.util.spec_from_file_location('isolated_proto_review',proto)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    contract=controls['contract'];normal=controls['cases'][0]['input']
    scoped='DECLARED_NONADJACENT_BODY_PAIR_SURFACES_DISJOINT_ONLY'
    samples=[]
    def check(name,payload,expected):
        result=module.aggregate(contract,payload)
        samples.append({'case':name,'expected_status':expected,'observed':result,'matches':result['status']==expected})
    shuffled=copy.deepcopy(normal);shuffled['records'].reverse()
    check('independent_order_invariance',shuffled,scoped)
    reversed_ids=copy.deepcopy(normal)
    for r in reversed_ids['records']:r['links'].reverse()
    check('independent_pair_orientation_invariance',reversed_ids,scoped)
    duplicate=copy.deepcopy(normal);duplicate['records'][0]=copy.deepcopy(duplicate['records'][1])
    check('independent_duplicate_with_correct_completion',duplicate,'INCOMPLETE_OR_INVALID_EVIDENCE')
    mixed=copy.deepcopy(normal);mixed['records'][0]['snapshot_digest']='different-snapshot'
    check('independent_one_row_from_other_snapshot',mixed,'INCOMPLETE_OR_INVALID_EVIDENCE')
    masked=copy.deepcopy(normal);masked['worker_returncode']=True
    check('independent_boolean_is_not_process_exit_code',masked,'INCOMPLETE_OR_INVALID_EVIDENCE')
    missing=copy.deepcopy(normal);missing.pop('input_sha256_after')
    check('independent_missing_end_snapshot',missing,'INCOMPLETE_OR_INVALID_EVIDENCE')
    crossed=copy.deepcopy(normal);crossed['completion']['run_id']='other-run'
    check('independent_completion_from_other_run',crossed,'INCOMPLETE_OR_INVALID_EVIDENCE')
    no_unknown=copy.deepcopy(normal)
    for row in no_unknown['records']:
        if row.get('surface_intersection') is None:row['surface_intersection']=False
    check('independent_finger_unknown_cannot_be_promoted',no_unknown,'INCOMPLETE_OR_INVALID_EVIDENCE')
    view_rejected=False
    try:module.require_physical_view(json.loads((WP/'results/parking_exploded_instances.json').read_text(encoding='utf-8')))
    except ValueError:view_rejected=True
    after={str(p):sha(p) for p in paths}
    out={'scope':'Independent fsum/parallel-axis ledger arithmetic and isolated software protocol checks; no geometry re-evaluation or dynamics integration.',
        'reviewer':'/root A0/A5; prototype authored independently by /root/assembly_validation_plan',
        'input_sha256_before':before,'input_sha256_after':after,'all_inputs_unchanged':before==after,
        'recorded_input_hash_mismatches':input_failures,'states':state_results,
        'BOM':{'rows':len(rows),'allocated_sum_kg':math.fsum(values),'ledger_sum_kg':service_mass,
               'difference_kg':abs(math.fsum(values)-service_mass),'mass_columns_added_together':False},
        'protocol_prototype_sha256':sha(proto),'independent_protocol_cases':samples,
        'all_8_protocol_cases_matched':all(x['matches'] for x in samples),
        'actual_exploded_receipt_rejected_by_prototype':view_rejected,
        'prototype_deployed_to_original':False,'new_CAD_or_motion_check_performed':False,
        'momentum_or_control_simulation_performed':False,'hardware_verified':False,
        'limits':['Recalculation checks arithmetic of existing atomic properties, not their physical accuracy.',
                  'Expected topology contract is assumed frozen; current original pose_screen still needs the proposed guards.',
                  'No complete unknown-mass, flight-load, actuator, EPS or thermal model was fabricated.']}
    (HERE/'INDEPENDENT_RECHECK.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'state_groups':[(s['state'],len(s['groups'])) for s in state_results],
                      'all_ledger_arithmetic_matches':all(g['arithmetic_matches'] for s in state_results for g in s['groups']),
                      'protocol_cases':len(samples),'protocol_all_match':out['all_8_protocol_cases_matched'],
                      'exploded_rejected':view_rejected,'input_hash_mismatches':input_failures,'BOM':out['BOM']},indent=2))
    assert not input_failures and before==after
    assert all(g['arithmetic_matches'] and not g['duplicate_mass_owners'] for s in state_results for g in s['groups'])
    assert out['all_8_protocol_cases_matched'] and view_rejected and out['BOM']['difference_kg']<1e-12


if __name__=='__main__':main()
