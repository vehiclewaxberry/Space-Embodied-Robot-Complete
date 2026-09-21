"""Independent receipt/code/source audit of the completed hierarchical native V2; no COM."""
from pathlib import Path
from collections import Counter
import hashlib,json
import numpy as np
D=Path(__file__).resolve().parents[2];O=D/'results/reviewer';checks=[];locks={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def norm(p):return str(Path(p).resolve()).replace('\\','/').casefold()
def lock(p):
 k=str(Path(p).resolve());h=sha(p);assert k not in locks or locks[k]==h;locks[k]=h;return h
def read(p):lock(p);return json.loads(Path(p).read_text(encoding='utf8'))
def ck(n,v,d=None):checks.append(dict(name=n,passed=bool(v),detail=d))
plan=read(D/'inputs/NATIVE_ASSEMBLY_PLAN.json');build=read(D/'results/NATIVE_ASSEMBLY_DELIVERY.json');resume=read(D/'results/NATIVE_SERVICE_TOP_RESUME.json');top=read(D/'results/EXISTING_TOP_INVENTORY.json');v2=read(D/'results/NATIVE_HIERARCHICAL_RECHECK_V2.json');rt=read(O/'NATIVE_ROUNDTRIP_REVIEW.json');elec=read(O/'ELECTRICAL_SOURCE_PRESERVATION.json')
codepath=D/'tools/recheck_native_groups.py';lock(codepath);code=codepath.read_text(encoding='utf8')
ck('V2_complete',v2['status']=='PASS_HIERARCHICAL_READ_ONLY_NATIVE_RECHECK')
ck('V2_source_bindings',v2['source_plan_sha256']==sha(D/'inputs/NATIVE_ASSEMBLY_PLAN.json') and v2['source_resume_sha256']==sha(D/'results/NATIVE_SERVICE_TOP_RESUME.json') and v2['source_top_inventory_sha256']==sha(D/'results/EXISTING_TOP_INVENTORY.json'))
ck('partial_build_preserved_and_resumed',build['status']=='FAILED_CLOSED' and resume['resumed_from_sha256']==sha(D/'results/NATIVE_ASSEMBLY_DELIVERY.json') and resume['status']=='PASS_R6H_SERVICE_TOP_RESUMED_AND_COLD_VERIFIED')
ck('code_global_transform_composition','T=parentT@matrix(a)' in code and 'T[:3,3]=np.array(a[9:12])*1000' in code and "assert err<1e-8" in code)
ck('code_resolve_before_body_read','assert resolution==0' in code and "part.GetBodies2(0,False)" in code and "part.GetBodies2(1,False)" in code and "assert raw is not None" in code)
ck('code_no_saving_calls',all(x not in code for x in ['SaveAs(','.Save3(','.SaveAs3(']))
ck('top_native_file_binding',top['sha256']==resume['service']['saved']['sha256']==lock(resume['service']['saved']['path']))
ck('top_cold_status',top['status']=='READ_ONLY_INVENTORY_COMPLETE' and top['errors']==top['warnings']==top['needs_rebuild2']==0 and not top['save_attempts'])
planned_top={r['id']:r for r in plan['top_rows']};actual_top={r['id']:r for r in top['top_rows']}
ck('top_15_unique_ids',len(planned_top)==len(actual_top)==len(top['top_rows'])==15 and set(planned_top)==set(actual_top))
for ident,p in planned_top.items():
 a=actual_top[ident];v=a['T'];T=np.eye(4);T[:3,:3]=np.array(v[:9]).reshape((3,3),order='F');T[:3,3]=np.array(v[9:12])*1000
 ck('actual_top_path_pose:'+ident,norm(a['path'])==norm(p['native_path']) and a['fixed'] is True and abs(v[12]-1)<1e-10 and np.max(np.abs(T-p['T_S_local']))<1e-8)
expected={r['id']:r for r in plan['expected_leaves']};leaves={r['id']:r for r in v2['leaves']}
ck('1153_leaf_set',len(leaves)==len(v2['leaves'])==len(expected)==plan['expected_leaf_count']==v2['leaf_count']==1153 and set(leaves)==set(expected))
groups={r['id']:r for r in v2['groups']};ck('15_groups_set',len(groups)==len(v2['groups'])==v2['direct_group_count']==15 and set(groups)==set(planned_top))
group_counts=Counter();group_solids=Counter();path_facts={};maxerr=0
for ident,p in expected.items():
 a=leaves[ident];ck('leaf_identity:'+ident,norm(a['path'])==norm(p['native_path']) and a['group']==p['group'] and a['fixed'] is True)
 ck('leaf_body_pose:'+ident,a['actual_solids']==p['expected_solids'] and a['actual_sheets']==p.get('expected_sheets',0) and a['global_transform_error']<1e-8)
 group_counts[a['group']]+=1;group_solids[a['group']]+=a['actual_solids'];maxerr=max(maxerr,a['global_transform_error'])
 k=norm(a['path']);f=dict(solid_count=a['actual_solids'],sheet_count=a['actual_sheets'])
 if k in path_facts:ck('same_native_body_counts:'+ident,path_facts[k]==f)
 path_facts[k]=f
ck('1602_solid_instance_sum',sum(group_solids.values())==v2['actual_solid_instances']==plan['expected_solid_instances']==1602)
actualcache={norm(k):v for k,v in v2['body_counts'].items()};ck('721_unique_native_counts',actualcache==path_facts and len(path_facts)==v2['unique_native_parts']==721)
ck('maximum_matrix_error_exact',maxerr==v2['maximum_global_transform_error'] and maxerr<1e-8,maxerr)
for ident,g in groups.items():
 ck('group_path_count_resolve:'+ident,norm(g['path'])==norm(planned_top[ident]['native_path']) and g['leaves']==group_counts[ident] and g['actual_solid_instances']==group_solids[ident] and g['cold_errors']==g['cold_warnings']==g['resolve_status']==g['needs_rebuild2']==0 and g['resolved'] is True)
 ck('group_saved_SHA:'+ident,lock(g['path'])==g['sha256'])
native_locks=plan['source_native_files']+[dict(path=r['target'],sha256=r['native_save']['sha256']) for r in build['parts']]+[r['saved'] for r in build['groups']]+[resume['service']['saved']]
canonical={}
for r in native_locks:
 k=norm(r['path'])
 if k in canonical:ck('duplicate_lock_consistent:'+k,canonical[k]['sha256']==r['sha256'])
 canonical[k]=r
ck('790_locked_native_files',len(canonical)==v2['locked_files_unchanged']==790)
for k,r in canonical.items():ck('native_SHA:'+k,lock(r['path'])==r['sha256'])
ck('all_leaf_files_in_lockset',set(path_facts).issubset(canonical))
ck('all_groups_in_lockset',all(norm(r['path']) in canonical for r in groups.values()))
ck('hierarchical_scope_honest',v2['documents_saved']==0 and not v2['save_attempts'] and v2['whole_assembly_simultaneously_resolved'] is False)
for k in ['whole_design_complete','ready_to_power','flight_ready']:ck('scope_HOLD:'+k,v2[k] is False)
ck('40_body_independent_roundtrip',rt['status']=='PASS_PARTS_GROUPS_TOP_CHAIN_WITH_SCOPE_HOLDS' and rt['checks']['passed']==rt['checks']['total'] and rt['roundtrip_body_count']==40)
ck('electrical_sources_unchanged',elec['status']=='PASS_UNCHANGED_R5E_AND_V36' and elec['schematics_preserved']==15 and elec['boards_preserved']==3)
for proofname,proof in [('roundtrip',rt),('electrical',elec)]:
 d=proof.get('source_locks',proof.get('source_review_locks',{}))
 for p,h in d.items():ck('prior_evidence_current:'+proofname+':'+p,lock(p)==h)
# Complete the electrical preservation report's data-file checks, not just receipt hashes.
for r in elec['checks_detail']:ck('electrical_file_still_current:'+r['path'],lock(r['path'])==r['actual'])
for p,h in list(locks.items()):ck('read_only_final_preservation:'+p,sha(p)==h)
out=dict(schema='R6H_INDEPENDENT_NATIVE_FINAL_REVIEW_V1',status='PASS_SOURCE_LOCKED_HIERARCHICAL_NATIVE_REVIEW' if all(c['passed'] for c in checks) else 'FAIL_NATIVE_FINAL_REVIEW',checks=dict(passed=sum(c['passed'] for c in checks),total=len(checks),failed=[c for c in checks if not c['passed']]),checks_detail=checks,source_locks=locks,counts=dict(groups=len(groups),leaves=len(leaves),solid_instances=sum(group_solids.values()),unique_native_parts=len(path_facts),native_files_locked=len(canonical)),maximum_global_transform_error=maxerr,method='Independent source-code/receipt/path/hash/count aggregation audit plus earlier independent 40-body OCP roundtrip. Builder V2 acquired the native COM facts in 15 separate cold resolved groups; this reviewer did not start a second COM session. Top transform × local leaf transform is audited in the builder code; stored leaf errors lack full matrices and are not a second native measurement.',whole_assembly_simultaneously_resolved=False,documents_saved_by_review=0,portable_package=plan['portable_package'],scope='Current local referenced native hierarchy for digital installation review, not whole-system qualification, full continuous-motion clearance or portable Pack-and-Go delivery.',manufacturing_release=False,whole_design_complete=False,ready_to_power=False,flight_ready=False)
(O/'NATIVE_FINAL_REVIEW.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:out[k] for k in ['status','checks','counts','maximum_global_transform_error']},ensure_ascii=False),flush=True)
raise SystemExit(0 if all(c['passed'] for c in checks) else 2)
