"""Read-only hierarchy plan comparison. Does not import CAD helpers."""
from pathlib import Path
import datetime,hashlib,json
C=Path(__file__).resolve().parents[1]
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
p=C/'results/NATIVE_DELTA_HIERARCHY_INPUTS.json';jpath=C/'results/NATIVE_DELTA_INPUTS.json';plan=read(p);j=read(jpath)
groups={g['id']:g for g in plan['groups']};checks=[]
snapshot=C/'results/NATIVE_DELTA_IMPORTED_PARTS.json';sealed={q['id']:q for q in read(snapshot)['parts']}
def check(n,c):checks.append({'name':n,'pass':bool(c)});assert c,n
check('inputs_SHA',sha(jpath)==plan['input_manifest_sha256'])
check('imported_parts_snapshot_SHA',sha(snapshot)==plan['imported_parts_snapshot_sha256'])
check('parent_SW_identity',plan['parent_transform_sw16']==[1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0])
for state,s in plan['states'].items():
 rows=[q for gid in s['groups'] for q in groups[gid]['rows']];want={q['id']:q for q in j['states'][state]['rows']}
 check(state+'_10_unique_containers',len(s['groups'])==len(set(s['groups']))==10)
 check(state+'_873_unique_leaves',len(rows)==len({q['id'] for q in rows})==len(want)==873)
 for q in rows:
  old=want[q['id']]
  check(state+'_'+q['id']+'_native_T_preserved',q['T_S_local']==old['T_S_local'])
  expected_sha=sealed[old['native_delta_part_id']]['native_sha256'] if old.get('native_delta_part_id') else old['native_sha256']
  check(state+'_'+q['id']+'_native_identity_preserved',Path(q['native_path']).name==Path(old['native_path']).name and q['native_sha256']==expected_sha)
code=C/'tools/native_delta_hierarchy.py'
delivery=C/'tools/native_delta_delivery.py'
view_code=C/'tools/native_delta_view.py'
service_cold=C/'results/NATIVE_DELTA_COLD_service.json'
out={'schema':'NATIVE_HIERARCHY_INDEPENDENT_CODE_PLAN_REVIEW_V1','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'status':'PASS_STATIC_PLAN_AND_CODE_REVIEW__ACTUAL_COLD_ACCEPTANCE_REMAINS_SEPARATE',
 'checks_passed':len(checks),'checks':checks,'code_sha256':sha(code),'delivery_code_sha256':sha(delivery),'optional_view_code_sha256':sha(view_code),'plan_sha256':sha(p),
 'actual_CAD_execution_by_reviewer':False,'actual_cold_results_reviewed':False,
 'service_cold_receipt_summary_read_only':{'sha256':sha(service_cold),'status':read(service_cold)['status'],'leaf_count':read(service_cold)['component_count'],'containers':read(service_cold)['top_level_container_count'],'external_dependencies':read(service_cold)['external_dependency_count'],'scope':'Read receipt summary only; reviewer did not execute or independently repeat native cold verification'},
 'accepted_contracts':['873 leaves excludes 10 containers','GetComponents(False) recursive walk','identity parent transforms; native leaf T directly compared without multiplying twice','recursive part+subassembly dependency equality and file hashes','relocation requires original directory absent before open'],
 'hardening_requests_resolved_by_author_and_read_by_reviewer':[
 {'id':'NHR01','scope':'hierarchy identity','request':'Assert each top container actual GetPathName equals group id sealed path and every leaf parent id equals its expected group, not only any member of the top group set.'},
 {'id':'NHR02','scope':'receipt lineage','request':'Bind integrate receipt hierarchy/input/import snapshots SHA to current plan before cold acceptance.'},
 {'id':'NHR03','scope':'physical relocation evidence','request':'Assert original directory still absent at cold close in addition to pre-open, and record both observations.'}],
 'delivery_code_review':['Validates frozen subassembly SHA and completed saved/cold group receipts against current hierarchy plan','Seals all state subassembly dependencies in ZIP whitelist and verifies every archive entry SHA','Accepts group memory guards and assembly guards separately','Keeps 873 leaves and 10 containers separate; does not claim rereading all 1254 solids','Hidden cold metadata verification is separate from optional Large Design Review image session; optional image is linked to native and cold receipt SHA and grants no geometry credit; ZIP count includes only accepted optional images'],
 'scope_note':'Author added actual parent path and strict expected parent id checks, three integrate-input SHA checks, and original-root absence again after relocated close. Code was read, not run by reviewer. Static plan preserves original leaf geometry. This review grants no native cold/physics/motion acceptance.'}
(C/'review/NATIVE_HIERARCHY_REVIEW.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(C/'review/NATIVE_HIERARCHY_REVIEW_ZH.md').write_text('# 原生分层装配独立静态复核\n\n三态各 873 叶部件、10 容器；5247 项计划数据检查通过。父变换为 identity，叶变换沿用原 native T，没有重复相乘。\n\n已读作者修复：实际父路径和逐叶指定父组绑定、集成回执三份输入 SHA、搬迁关闭后原目录仍缺席。交付器包含子装配文件及其真实保存/冷读回执哈希，白名单 ZIP 逐项校验。\n\n本复核没有运行 SolidWorks、COM 或 CAD，没有代替实际三态与搬迁冷读，也不授予运动、制造或飞行结论。详见同名 JSON 的源哈希。\n',encoding='utf-8')
print(json.dumps({'status':out['status'],'checks_passed':len(checks)},ensure_ascii=False))
