"""Preserve V9 rows and replace the actual eight supports plus three plates."""
import copy,json,numpy as np
from battery_variant_context import A,read,sha,translation
c=read('mechanical/TRUNK_SUPPORT_DESIGN.json');assert c['parent_source_sha256']==sha(A/c['parent_source_plan'])
p=read(c['parent_source_plan']);states={}
for state,sp in p['states'].items():
    rows={r['id']:copy.deepcopy(r) for r in sp['rows']};changed=[];added=[]
    def setrow(k,stem,T,previous=None):
        path=A/f'mechanical/{stem}.step';r=rows.get(k,dict(id=k,is_ground_only=False,predecessor_ids=[]))
        r.update(step_path=str(path),source_sha256=sha(path),T_S_step=np.asarray(T).tolist(),representation_role='PROJECT_NOMINAL_SUPPORT_GEOMETRY_UNQUALIFIED_MATERIAL_PRELOAD',mass_inertia_requalification='NOT_REQUALIFIED_IN_THIS_VARIANT',native_geometry_current=False)
        if k not in rows:added.append(k)
        else:changed.append(k)
        rows[k]=r
    def reused(k,source,x,y,top):
        r=copy.deepcopy(rows[source]);r['id']=k;T=translation(x-72,y-41,top+11.5)@np.array(r['T_S_step']);r.update(T_S_step=T.tolist(),predecessor_ids=[],source_parent_lookup=dict(plan=c['parent_source_plan'],state=state,id=source),representation_role='REUSED_NOMINAL_M3_HARDWARE_GEOMETRY_NO_STRENGTH_RELEASE');rows[k]=r;added.append(k)
    for i,s in enumerate(c['stations']):
        T=np.array(s['T_S_local']);suffix=s['previous_suffix'];base=f'trunk_clip_standoff_{suffix}';cap=f'trunk_clip_{suffix}'
        setrow(base,'trunk_'+s['base_kind'].lower(),T);setrow(cap,'trunk_cap',T)
        for z,stem in [('LOW','trunk_liner_low'),('HIGH','trunk_liner_high')]:setrow(f'TRUNK_{i}_LINER_{z}',stem,T)
        for j,y in enumerate([-8,8]):
            xyz=(T@np.array([0,y,4,1]))[:3];setrow(f'TRUNK_{i}_SCREW_{j}','trunk_screw_'+str(s['clamp_screw_length_mm']),translation(*xyz))
            top=40 if i==0 else -11.5
            reused(f'TRUNK_{i}_WASHER_{j}','CLAMP_DUAL_0_BW',xyz[0],xyz[1],top)
            reused(f'TRUNK_{i}_NUT_{j}','CLAMP_DUAL_0_BN',xyz[0],xyz[1],top)
    for i,(x,y) in enumerate(c['deck_holes_xy_mm'][:2]):
        setrow(f'TRUNK_HIGH_FOOT_SCREW_{i}','trunk_screw_12',translation(x,y,-5.5))
        reused(f'TRUNK_HIGH_FOOT_WASHER_{i}','CLAMP_DUAL_0_BW',x,y,-11.5)
        reused(f'TRUNK_HIGH_FOOT_NUT_{i}','CLAMP_DUAL_0_BN',x,y,-11.5)
    for name,src in c['modified_sources'].items():setrow(src['id'],'trunk_'+name.lower(),np.eye(4))
    assert len(rows)==931 and len(changed)==11 and len(added)==38
    states[state]=dict(rows=list(rows.values()),changed_ids=changed,added_ids=added,known_pending_release_ids=[k for k in rows if k.startswith('release_power_data_route_')])
out=dict(schema='WP10_TRUNK_SUPPORT_SOURCE_VARIANT_V1',source_script_sha256=sha(__file__),inputs={q:sha(A/q) for q in [c['parent_source_plan'],'mechanical/TRUNK_SUPPORT_DESIGN.json','mechanical/trunk_support_common.py']},states=states,component_count=931,component_count_identity='893 +8 liner halves +10 nominal screws +10 reused washers +10 reused nuts =931; original8 support IDs replaced, all4 release segments preserved',whole_fit_verified=False,geometry_checks_complete=False,material_preload_strength_qualified=False,thermal_mass_native_requalified=False,whole_design_complete=False)
(A/'mechanical/TRUNK_SUPPORT_INSTANCE_PLAN.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(dict(instances=931,changed=11,added=38)))
