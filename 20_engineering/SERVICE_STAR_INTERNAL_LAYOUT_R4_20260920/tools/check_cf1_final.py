"""Bind the rejected CF1 search to the final R4 host; never install a rejected candidate."""
from geometry import *
search=read(D/'results/CF1_ROTATION_SEARCH.json');assert len(search['trials'])==18 and not search['feasible_pose_found']
assert sha(search['source_path'])==search['source_sha256'];module=load(search['source_path']);assert g.count(module)==60
mount=read(D/'inputs/MOUNT_LAYOUT.json');passage=read(D/'inputs/PASSAGE_LAYOUT.json');delta=mount['replacements']+mount['additions']+passage['replacements']
changes={r['id']:r for r in delta};aabbproof=[]
for t in search['trials']:
    s=moved(module,t['T_S_module']);over=[r['id'] for r in candidates(s,delta)]
    assert not over,(t['translation_mm'],over)
    assert not any(r['id'] in changes for r in t['collisions']) and not t['unknown']
    aabbproof.append({'translation_mm':t['translation_mm'],'R4_delta_AABB_candidates':over})
best=search['best'];s=moved(module,best['T_S_module']);cache={};states=[]
for st,rows in state_rows().items():
    rows=[changes.get(r['id'],r) for r in rows]+mount['additions'];hits=[];unknown=[]
    for o in candidates(s,rows):
        key=(o['id'],o['source_sha256'],str(o['T_S_local']))
        if key not in cache:
            try:cache[key]=g.volume(common(s,source(o)))
            except Exception as e:unknown.append({'id':o['id'],'error':str(e)});continue
        if cache[key]>1e-6:hits.append({'id':o['id'],'volume_mm3':cache[key],'role':o.get('representation_role'),
            'step_path':o['step_path'],'source_sha256':o['source_sha256'],'T_S_local':o['T_S_local']})
    assert hits and not unknown
    if st=='service':
        old={r['id']:r['volume_mm3'] for r in best['collisions']};assert set(old)=={r['id'] for r in hits}
        assert all(abs(old[r['id']]-r['volume_mm3'])<1e-6 for r in hits)
    states.append({'state':st,'collisions':hits,'unknown':unknown,'candidate_rejected':True})
(D/'cad/rejected').mkdir(exist_ok=True);p=D/'cad/rejected/CF1_REJECTED_RZ90.step';fact=g.dump(s,p)
report={'status':'CF1_REJECTED_IN_FINAL_R4__NOT_INSTALLED','search_sha256':sha(D/'results/CF1_ROTATION_SEARCH.json'),
    'upstream_declared_module_instances':56,'actual_STEP_solid_occurrences':60,
    'count_semantics':'Upstream component instances are not STEP solid occurrences; all 60 solid occurrences were loaded for every search',
    'final_R4_delta_is_AABB_disjoint_from_all_18_poses':aabbproof,
    'search_grid_is_bounded_not_global_impossibility':True,'best_candidate_states':states,
    'candidate_STEP':fact,'candidate_STEP_path':str(p),'pose':best['T_S_module'],
    'P60_and_RRC_battery_obstacles_retained':True,'V36_electrical_credit':False,'thermal_credit':False,
    'overlap_sum_is_pairwise_mixed_roles_not_unique_physical_volume':True,
    'source_locks':[{'path':p,'sha256':s} for p,s in SOURCE_CHECKS.items()]}
write(D/'results/CF1_FINAL_HOST_RECHECK.json',report)
print('REJECTED',[(r['state'],len(r['collisions'])) for r in states],'18 poses bound to final R4; no installation')
