"""Build the exact two-station integration contract from verified WP07 geometry."""
from pathlib import Path
import json,hashlib,copy,itertools,csv,datetime,shutil,math
R=Path(__file__).resolve().parents[1];W7=R.parent/'wp07_system_20260907_0610'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def norm(p):return str(Path(p).resolve()).casefold()
def require(ok,msg):
    if not ok:raise RuntimeError(msg)
def world_box(box,T):
    points=[[sum(T[i][j]*v[j] for j in range(3))+T[i][3] for i in range(3)] for v in itertools.product(*zip(box['min_mm'],box['max_mm']))]
    mn=[min(v[i] for v in points) for i in range(3)];mx=[max(v[i] for v in points) for i in range(3)]
    return dict(min_mm=mn,max_mm=mx,size_mm=[mx[i]-mn[i] for i in range(3)])
def main():
    out=R/'results/INTEGRATION_MANIFEST.json';require(not out.exists(),'Output exists')
    baseline=read(R/'results/BASELINE_CURRENT_CHECK.json');require(baseline['status']=='PASS_CURRENT_WP07_THREE_STATE_HASH_BOUND_EVIDENCE','Baseline not current')
    mp=W7/'results/INTEGRATION_MANIFEST.json';m=read(mp)
    require(sha(mp)==baseline['manifest_sha256'],'Baseline manifest changed')
    pins={str(mp):sha(mp),str(R/'results/BASELINE_CURRENT_CHECK.json'):sha(R/'results/BASELINE_CURRENT_CHECK.json'),str(Path(__file__)):sha(__file__)};cache={}
    def pin(path,digest=None):
        path=str(Path(path).resolve());key=norm(path)
        if key not in cache:cache[key]=sha(path)
        actual=cache[key];require(digest is None or actual==digest,'Source changed '+path)
        require(path not in pins or pins[path]==actual,'Conflicting pin '+path);pins[path]=actual
    for path,digest in baseline['input_sha256_after'].items():pin(path,digest)
    contract_path=W7/'inputs/RETENTION_DESIGN_CONTRACT.json';c=read(contract_path);pin(contract_path)
    stations={};allparts={};native_lookup={};evidence=[]
    for k in (0,1):
        ep=W7/f'results/retention_detail/station_{k}/EMISSION_RECEIPT.json';e=read(ep);pin(ep)
        require(e['contract_sha256']==sha(contract_path),'Contract identity differs')
        for key,digest in e['source_inputs'].items():pin(key,digest)
        pin(e['producer_path'],e['producer_sha256'])
        np=W7/f'results/RETENTION_NATIVE_S{k}_c03_v1.json';n=read(np);pin(np)
        require(n['status']=='PASS_NATIVE_FIXED_LOCAL_ASSEMBLY_COLD_REOPEN_ONLY' and n['input_files_unchanged'],'Local native incomplete')
        require(n['input_sha256_before']==n['input_sha256_after'],'Local native input snapshot differs')
        for key,digest in n['input_sha256_after'].items():pin(key,digest)
        require(n['component_count']==18 and len(e['parts'])==17,'Local membership differs')
        nrows={x['id']:x for x in n['parts']}
        require(len(nrows)==18 and {f'CONTEXT_PARKING_hold_saddle_{k}'}==set(nrows)-set(e['parts']),'Unexpected context')
        for ident,row in e['parts'].items():
            nr=nrows[ident];pin(row['path'],row['sha256']);pin(nr['native_save']['path'],nr['native_save']['sha256'])
            require(nr['status']=='NATIVE_PART_SAVED_CLOSED_REOPENED_VERIFIED_AND_CLOSED','Local part cold inspection incomplete')
            require(nr['source_sha256']==row['sha256'] and nr['part_cold_reopen']['facts']['solid_count']==1 and nr['part_cold_reopen']['facts']['sheet_count']==0,'Local part identity/count')
            require(nr['part_cold_reopen']['facts']['document_length_unit']=='mm','Local native units')
            allparts[ident]=row;native_lookup[ident]=nr
        for mode,state in [('local',None),('neighbours','service'),('neighbours','parking'),('neighbours','released')]:
            p=W7/f'results/retention_detail_c03/station_{k}/CHECK_{mode}{"_"+state if state else ""}.json';v=read(p);pin(p)
            require(v['status']=='PASS' and v['counts']['FAIL']==v['counts']['INCOMPLETE']==0,'Local geometry evidence incomplete')
            pin(v['checker_path'],v['checker_sha256'])
            for key,digest in v['input_sha256'].items():pin(key,digest)
            evidence.append(dict(path=str(p),sha256=sha(p),station=k,mode=mode,state=state,scope=v['scope'],counts=v['counts']))
        stations[str(k)]=dict(emission_path=str(ep),emission_sha256=sha(ep),native_receipt=str(np),native_receipt_sha256=sha(np),part_ids=sorted(e['parts']),context_id=f'hold_saddle_{k}',placements=e['placements'])
    for f in ('RETENTION_BOTH_STATIONS_CROSS.json','RETENTION_WP06_CROSS_STATION0.json'):
        p=W7/'results'/f;v=read(p);pin(p)
        require(v['status'].startswith('PASS') and v['source_hashes_unchanged'] and v['needs_brep_count']==0,'Cross delta evidence incomplete')
        require(v['source_sha256_before']==v['source_sha256_after'],'Cross evidence source drift')
        for key,digest in v['source_sha256_after'].items():pin(key,digest)
        evidence.append(dict(path=str(p),sha256=sha(p),scope=v['scope'],pair_count=v['pair_count'],separated_pair_count=v['separated_pair_count']))
    states={};rows_for_bom=[]
    for state,oldinfo in m['states'].items():
        old={x['id']:x for x in oldinfo['instances']};replaced=sorted(set(old)&set(allparts));added=sorted(set(allparts)-set(old))
        wanted={f'hold_fold_mast_{k}' for k in (0,1)}|{f'hold_shoe_guide_{k}_{x}' for k in (0,1) for x in (-10,10)}
        require(set(replaced)==wanted and len(added)==28,'Unexpected exact delta membership')
        retained=[copy.deepcopy(x) for x in oldinfo['instances'] if x['id'] not in replaced]
        for x in retained:x['parent_change']=x['change'];x['change']='RETAIN_UNCHANGED'
        changes=[]
        for k in (0,1):
            st=stations[str(k)];T=st['placements'][state]
            require(T==old[f'hold_fold_mast_{k}']['T_S_local'],'Frozen mast transform differs')
            for ident in st['part_ids']:
                e=allparts[ident];nr=native_lookup[ident]
                require(e['T_S_local_by_state'][state]==T,'Per-part coordinate conflict')
                previous=old.get(ident)
                if previous:require(previous['T_S_local']==T,'Replacement used different old local frame')
                row=dict(id=ident,part_key=f'WP07_RET_S{k}_{ident}',native_path=nr['native_save']['path'],native_sha256=nr['native_save']['sha256'],step_path=e['path'],source_sha256=e['sha256'],expected_solids=1,expected_sheets=0,T_S_local=T,local_bounds_mm=e['local_bbox_mm'],world_bounds_mm=world_box(e['local_bbox_mm'],T),representation_role=e['representation_role'],product_role=e['product_role'],parent_assembly='ONBOARD_RETENTION',mount_interface=f'hold_fold_mast_{k}',arm_link=None,motion_group=f'cradle_{k}',source_revision='WP07_C02_GEOMETRY_C03_CHECKER',qualification_status='LOCAL_NOMINAL_CANDIDATE_ONLY',geometry_mode='REUSED_LOCAL_MAST_FRAME_PART',change='REPLACE_SINGLE_INSTANCE' if previous else 'ADD_RETENTION_HARDWARE',source_mass_kg=None,mass_source='UNASSIGNED_AFTER_GEOMETRY_CHANGE',station=k,source_local_native_receipt=st['native_receipt'],previous_instance=previous)
                row['bounds_mm']=row['world_bounds_mm'];changes.append(row)
        rows=retained+changes
        require(len({x['id'] for x in rows})==len(rows),'Duplicate candidate identities')
        require(all(sum(x['id']==f'hold_saddle_{k}' for x in rows)==1 for k in (0,1)),'Context duplicated')
        parent=baseline['states'][state]
        states[state]=dict(parent_assembly_path=parent['native_path'],parent_assembly_sha256=parent['final_native_sha256'],parent_receipt_path=parent['receipt_path'],parent_receipt_sha256=parent['receipt_sha256'],parent_component_count=len(old),parent_solid_count=oldinfo['expected_solid_total'],replaced_ids=replaced,added_ids=added,context_ids_retained_once=[f'hold_saddle_{k}' for k in (0,1)],component_count=len(rows),expected_solid_total=sum(x['expected_solids'] for x in rows),unique_native_dependencies=len({norm(x['native_path']) for x in rows}),role_counts={role:sum(x['representation_role']==role for x in rows) for role in {x['representation_role'] for x in rows}},instances=rows)
    after={p:sha(p) for p in pins};require(after==pins,'Input changed during preparation')
    result=dict(schema='WP08_RETENTION_INTEGRATION_MANIFEST_V1',status='PREPARED_GEOMETRY_QUALIFIED_WITH_DECLARED_SCOPE__NATIVE_NOT_EXECUTED',generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),frame='INHERITED_WP07_S_MM',base_manifest=str(mp),base_manifest_sha256=sha(mp),states=states,stations=stations,geometry_evidence=evidence,input_sha256_before=pins,input_sha256_after=after,inputs_unchanged=True,scope='Reuse C02 local geometry and C03 qualified added-material checks; change only six instances plus twenty-eight added hardware. Old baseline/global/continuous/load/actuator HOLDs remain.',whole_STEP_verified=False,continuous_motion_verified=False,strength_verified=False,manufacturing_release=False)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with (R/'results/DELTA_BOM.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        fields=['id','change','station','representation_role','native_path','step_path','source_mass_kg','mass_source'];writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for row in states['service']['instances']:
            if row['change']!='RETAIN_UNCHANGED':writer.writerow({f:row.get(f) for f in fields})
    print(json.dumps({'status':result['status'],'input_pins':len(pins),'states':{s:{k:v[k] for k in ('component_count','expected_solid_total','unique_native_dependencies')} for s,v in states.items()},'delta_replaced':len(replaced),'delta_added':len(added)},ensure_ascii=False))
if __name__=='__main__':main()
