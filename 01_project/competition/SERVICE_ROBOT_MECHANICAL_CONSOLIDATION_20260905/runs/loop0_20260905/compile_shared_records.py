"""Compile the four-entry review packet. Original WP packages remain read-only."""
from pathlib import Path
from collections import Counter
import json,csv,hashlib,datetime

RUN=Path(__file__).resolve().parent
SESSION=RUN.parent.parent
ROOT=SESSION.parents[2]
WP=ROOT/'20_engineering/service_robot_wp03_spacecraft_body_r1'


def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def rel(path):return path.relative_to(SESSION).as_posix()


def main():
    a1=read(RUN/'a1/DEPENDENCY_REVIEW.json')
    a23=read(RUN/'a2_a3/STRUCTURE_MECHANISM_REVIEW.json')
    a4=read(RUN/'a4/SOURCE_AND_RECORD_AUDIT.json')
    independent=read(RUN/'a0_a5/INDEPENDENT_RECHECK.json')
    screen=read(RUN/'screening/SCREEN_RECEIPT.json')
    seed=read(RUN/'inputs/package/issue_register_seed.json')
    original=read(WP/'results/DELIVERY_RECEIPT.json')
    source_sha=sha(WP/'spacecraft_model.py')
    intake=read(RUN/'inputs/INTAKE.json')
    uploaded=read(RUN/'inputs/package/source_manifest.json')
    uploaded_matches=[]
    for r in uploaded['uploaded_sources']:
        local=r['name'].replace('(2)','').replace('(1)','')
        path=WP/local
        uploaded_matches.append({'uploaded_name':r['name'],'local_path':str(path),
            'uploaded_sha256':r['sha256'],'current_sha256':sha(path),'same_bytes':sha(path)==r['sha256']})
    configs=[]
    params=read(WP/'design_parameters.json')
    for name in ['parking','released','service']:
        path=WP/f'results/{name}_instances.json';r=read(path)
        deps=[key for key,h in r['dependency_sha256'].items() if sha(WP/key)!=h]
        ids=[x['id'] for x in r['instances']]
        configs.append({'state':name,'receipt':str(path),'sha256':sha(path),
            'source_matches':r['source_sha256']==source_sha,'dependency_mismatches':deps,
            'q_matches_parameters':r['q_deg']==params['states'][name]['q_deg'],
            'finger_matches_parameters':r['finger_mm']==params['states'][name]['finger_mm'],
            'view':r['view'],'instance_count':len(ids),'unique_ids':len(set(ids)),
            'representation_counts':dict(Counter(x['representation_role'] for x in r['instances'])),
            'gse_instances':sum(x['product_role']=='GSE' for x in r['instances']),
            'root_transform':r['T_S_arm_base']})
    source_maps={}
    for name,field in [('INTEGRATE_CHECKS.json','source_hashes'),('DYNAMICS_HANDOFF.json','input_sha256'),('FRAME_STIFFNESS_SCREEN.json','input_source_sha256')]:
        rows=[]
        for path,h in read(WP/'results'/name)[field].items():
            p=Path(path);rows.append({'path':path,'recorded_sha256':h,'matches':p.is_file() and sha(p)==h})
        source_maps[name]=rows
    binding={'review_input_package':intake,'uploaded_source_identity':uploaded_matches,
             'configuration_bindings':configs,'recorded_source_map_bindings':source_maps,
             'all_scoped_bindings_match':all(x['same_bytes'] for x in uploaded_matches) and all(c['source_matches'] and not c['dependency_mismatches'] and c['q_matches_parameters'] and c['finger_matches_parameters'] and c['unique_ids']==c['instance_count'] and c['gse_instances']==0 and c['view']=='complete' for c in configs) and all(x['matches'] for rows in source_maps.values() for x in rows),
             'scope':'Byte/configuration identity and receipt scope only; no CAD rebuild or old geometry result replay.',
             'full_parent_child_snapshot_protocol_retroactively_proven':False}
    write(RUN/'INPUT_BINDING.json',binding)
    local_a23={x['id']:x for x in a23['findings']}
    statuses={'R01':'PATCH_PROPOSED','R02':'EVIDENCE_BOUND','R03':'EVIDENCE_BOUND','R04':'EVIDENCE_BOUND','R05':'EVIDENCE_BOUND','R06':'INPUT_BLOCKED','R07':'EVIDENCE_BOUND','R08':'EVIDENCE_BOUND','R09':'EVIDENCE_BOUND','R10':'REPRODUCED','R11':'EVIDENCE_BOUND','R12':'EVIDENCE_BOUND','R13':'EVIDENCE_BOUND','R14':'EVIDENCE_BOUND','R15':'EVIDENCE_BOUND','R16':'EVIDENCE_BOUND'}
    records=[]
    for item in seed['findings']:
        i=item['id']
        entry={'id':i,'title':item['title'],'severity':item['severity'],'status':statuses[i],
               'seed_evidence_level':item['evidence_level'],'seed_preserved_in':rel(RUN/'inputs/package/issue_register_seed.json'),
               'blocks':item['blocks'],'next_action':item['next_action'],'acceptance':item['acceptance'],
               'hardware_verified':False,'original_geometry_replayed_this_round':False,
               'production_fix_applied':False,'engineering_issue_closed':False,'evidence':[]}
        if i in local_a23:
            entry['owner']='A2/A3 /root/wp01_design_inputs'
            entry['local_review']=local_a23[i]
            entry['evidence'].append(rel(RUN/'a2_a3/STRUCTURE_MECHANISM_REVIEW.json'))
        elif i in ['R08','R09','R10','R11','R15']:
            entry['owner']='A4 /root/assembly_validation_plan'
            entry['local_review']=a4['issue_dispositions'][i]
            entry['evidence'].append(rel(RUN/'a4/SOURCE_AND_RECORD_AUDIT.json'))
        else:
            entry['owner']='A0/A5 /root'
            entry['evidence'].append(rel(RUN/'INPUT_BINDING.json'))
        if i=='R01':entry['next_ticket']=a23['first_candidate_ticket']
        if i=='R02':entry['local_review']={'scope_readback':original['non_arm_physical_checks'],'scope_not_extended':True,'source_record':str(WP/'results/GEOMETRY_CHECK.json')}
        if i=='R05':entry['local_review']={'retention_samples':71,'wing_leaf_samples':91,'continuous_proof':None,'whole_spacecraft_geometric_proof':None,'basis':'Existing JSON readback only'}
        if i=='R06':entry['missing_inputs']=['Launch/separation supplier ICD and full-system stow envelope','Provider environmental loads and boundary conditions']
        if i=='R10':
            entry['software_counterexample_replayed']=True
            entry['evidence'] += [rel(RUN/'a4/STATUS_BRANCH_PROBE_CURRENT.json'),rel(RUN/'a4/STRICT_AGGREGATOR_CONTROLS.json'),rel(RUN/'a0_a5/INDEPENDENT_RECHECK.json')]
            entry['prototype_scope']='Isolated aggregator only; original pose_screen unchanged; old five geometric records not invalidated by this defect.'
        if i=='R12':
            entry['local_review']={'independent_ledger_arithmetic':rel(RUN/'a0_a5/INDEPENDENT_RECHECK.json'),'new_dynamics_simulation':False,'unknowns_preserved':True,'old_control_gate_transfer':False}
            entry['evidence'].append(rel(RUN/'a0_a5/INDEPENDENT_RECHECK.json'))
        if i=='R13':entry['local_review']={'invalid_topology_count_documented_in_original':6,'original_record':str(WP/'results/servicer_service_validate.json'),'BRep_repairs_performed':False,'fingers_and_containment_complete':False}
        if i=='R14':entry['local_review']={'static_parameter_findings':'See CURRENT_candidate.md and dependency inventory; wing_source and several local root/structure/material fields are declarations, not drivers. State versus retention angle inputs are duplicated.','parameter_perturbation_CAD_replay_performed':False}
        if i=='R15':entry['isolated_prototype_rejects_actual_exploded_receipt']=independent['actual_exploded_receipt_rejected_by_prototype']
        records.append(entry)
    records.append({'id':'R17','title':'BOM交接来源未校验且重建顺序可能保留旧质量分配','severity':'P1','status':'PATCH_PROPOSED','owner':'A4 /root/assembly_validation_plan',
        'evidence_level':'STATIC_CODE_WORKFLOW_RISK; CURRENT_BOM_ARITHMETIC_MATCHES',
        'evidence':[rel(RUN/'a4/BOM_INPUT_BINDING_PROPOSAL.md'),rel(RUN/'a0_a5/INDEPENDENT_RECHECK.json')],
        'acceptance':'Reject stale/missing required input hashes and instance/owner mismatch before writing output; export BOM after dynamics; keep initial unallocated values null.',
        'production_fix_applied':False,'engineering_issue_closed':False,'hardware_verified':False,
        'current_BOM_is_proven_stale':False})
    issues={'schema':'WP03_LOOP0_SHARED_ISSUES_V1','mode':'REVIEW_AND_PLAN','baseline_sha256':source_sha,
            'not_a_project_release_gate':True,'issue_count':len(records),'issues':records,
            'next_minimum_ticket_id':'R01_DECK_ANGLE_FASTENER_MINIMUM_PROPOSAL_R1',
            'actual_CAD_builder_executed':False,'first_ticket':a23['first_candidate_ticket']}
    write(SESSION/'issues.json',issues)
    with (RUN/'screening/ASSET_SCREEN.csv').open(encoding='utf-8-sig',newline='') as f:asset_rows=list(csv.DictReader(f))
    mapped=Counter();flags=Counter()
    for row in asset_rows:
        cat=row['category'];path=Path(row['path']);name=path.name
        if cat in ['GENERATED_VIEWER_CACHE','GENERATED_BYTECODE']:role='REPRODUCIBLE_CACHE_CANDIDATE'
        elif cat in ['SOURCE_OR_REPRODUCTION_DEPENDENCY','RUNTIME_DEPENDENCY']:role='REQUIRED_UPSTREAM'
        elif cat=='CURRENT_PART_CANDIDATE' or cat=='CURRENT_REVIEW_EXPORT' or (cat=='CURRENT_MODEL_VARIANT' and name.endswith('.step')):role='GENERATED_DELIVERABLE'
        elif cat=='HISTORICAL_COUNTEREXAMPLE_OR_BOOTSTRAP':role='FROZEN_EVIDENCE' if name in ['setup_candidate.py','solar_kinematics_source.py'] else 'FAILED_COUNTEREXAMPLE'
        elif cat in ['HISTORICAL_COMPONENT_WORK','EXECUTION_DIAGNOSTIC','EMPTY_EXECUTION_DIAGNOSTIC','CURRENT_CHECK_OR_RECEIPT']:role='FROZEN_EVIDENCE'
        elif name.endswith('.py') or name=='design_parameters.json':role='ACTIVE_SOURCE'
        elif name.endswith(('.md','.json','.csv')):role='GENERATED_DELIVERABLE'
        else:role='UNRESOLVED'
        mapped[role]+=1
        if row['exact_duplicate_group']:flags['EXACT_DUPLICATE_CANDIDATE']+=1
        if 'ground_ait' in row['path']:flags['GSE_BRANCH']+=1
        if row['package']=='WP01' and '/inputs/' in row['path'] and name.endswith('.step'):flags['VENDOR_REFERENCE_NOMINAL_ARM_DERIVATIVE']+=1
    dep={'schema':'WP03_LOOP0_SHARED_DEPENDENCIES_V1','mode':'REVIEW_AND_PLAN','scope':screen['scope'],
        'navigation':{'current_candidate':str(WP),'upstream_WP01':str(WP.parent/'service_robot_wp01_20260905'),'upstream_WP02':str(WP.parent/'service_robot_wp02_20260905')},
        'baseline_sha256':source_sha,'primary_role_counts':dict(mapped),'nonexclusive_role_flags':dict(flags),
        'screening_statistics':screen,'detailed_asset_csv':rel(RUN/'screening/ASSET_SCREEN.csv'),'exact_duplicate_csv':rel(RUN/'screening/EXACT_DUPLICATES.csv'),
        'source_files_reviewed_count':len(a1['source_inventory']),'resolved_edges_count':len(a1['resolved_edges']),
        'active_wp01_wp02_edges':a1['active_wp01_wp02_edges_not_deletable'],
        'all_resolved_edges_and_expressions':rel(RUN/'a1/DEPENDENCY_REVIEW.json'),
        'unknowns':a1['unknowns'],'environment':a1['environment'],'git_snapshot':a1['git_snapshot'],
        'physical_cleanup_dry_run':{'source_moves':[],'source_deletions':[],'quarantine_moves':[],
            'certified_safe_delete_candidates':[],'retained_paths':'All existing source, result and cache paths preserved.',
            'migration_mapping':None,'cold_rebuild_completed':False,'backup_and_rollback_exercised':False,
            'reason':'Static consumers remain; byte duplicates alone cannot establish safe path retirement.'}}
    write(SESSION/'dependency_manifest.json',dep)
    raw=[]
    for p in sorted(RUN.rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts:
            raw.append({'path':rel(p),'bytes':p.stat().st_size,'sha256':sha(p)})
    manifest={'schema':'WP03_LOOP0_SHARED_RUNS_V1','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'requested_mode':'REVIEW_AND_PLAN','baseline_sha256':source_sha,
        'role_execution':{'A0':{'agent':'/root','executed':'Coordination, binding, consolidation and independent protocol spot checks'},
            'A1':{'agent':'/root/assembly_validation_plan','executed':'Static dependency review'},
            'A2':{'agent':'/root/wp01_design_inputs','executed':'Source/analytical structure review'},
            'A3':{'agent':'/root/wp01_design_inputs','executed':'Source/receipt mechanism review and retention subledger arithmetic'},
            'A4':{'agent':'/root/assembly_validation_plan','executed':'Original isolated expression controls and undeployed protocol prototype'},
            'A5':{'agent':'/root','executed':'Independent arithmetic on 3 onboard ledgers and separate GSE; no dynamics simulation'},
            'A6':{'agent':None,'executed':False,'reason':'First-round read-only command; no CAD production writer invoked'}},
        'independence':'Two actual subagents and root, not seven independent reviewers. Root independently tested A4 prototype. No Claude backend was invoked.',
        'source_protection':{'WP03_manifest_entries_verified':screen['WP03_manifest_entry_count'],'manifest_mismatches':screen['WP03_manifest_mismatches'],
            'directed_sources_verified':screen['pinned_source_count'],'directed_source_mismatches':screen['pinned_source_mismatches'],
            'A4_inputs_unchanged':read(RUN/'a4/READ_ONLY_RUN_RECEIPT.json').get('all_inputs_unchanged',None),
            'A2_A3_inputs_unchanged':a23['source_hashes_unchanged_during_result_preparation'],
            'independent_ledger_inputs_unchanged':independent['all_inputs_unchanged'],'scoped_input_bindings_match':binding['all_scoped_bindings_match']},
        'actual_runs':[{'name':'uploaded_expression_probe','cases':6,'scope':'synthetic expression only','raw':rel(RUN/'a4/STATUS_BRANCH_PROBE_CURRENT.json')},
            {'name':'isolated_protocol_prototype','cases':16,'view_guard_cases':5,'scope':'not deployed, not geometry','raw':rel(RUN/'a4/STRICT_AGGREGATOR_CONTROLS.json')},
            {'name':'independent_root_recheck','protocol_cases':8,'actual_exploded_receipt_guard':1,'ledger_groups':4,'scope':'arithmetic and software only','raw':rel(RUN/'a0_a5/INDEPENDENT_RECHECK.json')},
            {'name':'asset_screen','files':screen['file_count'],'scope':'Three WP packages only','raw':rel(RUN/'screening/SCREEN_RECEIPT.json')}],
        'not_executed':['CAD rebuild','OCC/VTK geometry rerun','full continuous path proof','parameter-to-CAD perturbation','cold environment rebuild','physical trial assembly','hardware/flight qualification'],
        'write_accounting':{'original_WP01_WP02_WP03_files_changed':[],'CURRENT_global_promoted':False,'original_results_overwritten':False,
            'pre_package_repair_attempts':'Two subagent apply_patch attempts failed before applying any change; no original BOM/README/exporter writes.',
            'pre_package_navigation_tool_created':str(ROOT/'70_tools/mechanical_asset_index/scan_service_robot_assets.py'),
            'session_navigation_draft_renamed':'README.md to CURRENT_candidate.md inside newly created session only'},
        'quota_or_backend_failure_this_round':None,'heavy_geometry_jobs_run':0,
        'raw_records':raw,'core_records':[{'path':name,'sha256':sha(SESSION/name)} for name in ['CURRENT_candidate.md','issues.json','dependency_manifest.json']],
        'result':'REVIEW_AND_PLAN_DELIVERED; LOCAL_REPAIR_TICKET_DEFINED; NO_PRODUCTION_REPAIR_OR_RELEASE_CREDIT'}
    # The A4 receipt uses before/after maps, so derive truth from the actual fields.
    ar=read(RUN/'a4/READ_ONLY_RUN_RECEIPT.json')
    manifest['source_protection']['A4_inputs_unchanged']=ar['input_sha256_before']==ar['input_sha256_after']
    write(SESSION/'run_manifest.json',manifest)
    assert binding['all_scoped_bindings_match']
    assert not screen['WP03_manifest_mismatches'] and not screen['pinned_source_mismatches']
    print(json.dumps({'issues':len(records),'asset_files':screen['file_count'],'duplicate_groups':screen['exact_nonempty_duplicate_groups'],
                      'source_edges':len(a1['resolved_edges']),'bindings_match':binding['all_scoped_bindings_match'],'raw_records':len(raw)},indent=2))


if __name__=='__main__':main()
