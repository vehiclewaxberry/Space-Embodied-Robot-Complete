"""Emit all three complete source instance tables; known failures stay present."""
from pathlib import Path
import json,numpy as np
from battery_variant_context import A,read,sha,propulsion_variant,translation
cfg=read('mechanical/BATTERY_BAY_LAYOUT.json');before=read('mechanical/BATTERY_BAY_PREVIEW_INPUTS.json')
paths=['mechanical/FIXED_HEAT_INSTANCE_PLAN.json','mechanical/BATTERY_BAY_LAYOUT.json','mechanical/BATTERY_HARNESS_PASSAGE.json','mechanical/BATTERY_PROPULSION_ROUTING.json','results/BATTERY_RELAYOUT_SEED_SCREEN.json','results/BATTERY_INTERNAL_ROUTE_SCREEN.json','results/RELEASE_PORT_CLEARANCE_COUNTEREXAMPLE.json','tools/battery_variant_context.py']
paths += [f'results/BATTERY_PROPULSION_ROUTE_SCREEN_{s}.json' for s in ['SERVICE','PARKING','RELEASED']]
out=dict(schema='WP10_BATTERY_ROUTE_FULL_SOURCE_VARIANT_V1',status='THREE_FULL_SOURCE_TABLES_EMITTED__KNOWN_HARNESS_AND_DEVICE_INSTALLATION_OPEN',source_script_sha256=sha(__file__),inputs={q:sha(A/q) for q in paths},parent_source_count=894,sealed_origin_component_count=873,sealed_origin_electrical_refs=99,states={},full_BRep_assembly_generated=False,full_native_SolidWorks_assembly_generated=False,whole_fit_verified=False,whole_required_hardware_present=False,mechanical_or_electrical_release=False)
for state in ['service','parking','released']:
    screen=read(f'results/BATTERY_PROPULSION_ROUTE_SCREEN_{state.upper()}.json');assert screen['status']=='PROP_ROUTES_AND_DUAL_SUPPORT_GEOMETRY_CLEAR__ELECTRICAL_AND_OTHER_HARNESS_OPEN' and screen['state']==state
    assert screen['source_script_sha256']==sha(A/'tools/check_propulsion_reroute.py') and all(sha(A/q)==h for q,h in screen['input_sha256'].items()) and all(sha(q)==h for q,h in screen['source_hashes'].items())
    rows,changed=propulsion_variant(state)
    for k in changed:rows[k]['bbox_S_mm']=screen['actual_changed_bboxes'][k]
    for n in range(3):del rows[f'internal_harness_proxy_{n}']
    path=A/'mechanical/battery_internal_route.step';rows['WP10_INTERNAL_BATTERY_BYPASS']=dict(id='WP10_INTERNAL_BATTERY_BYPASS',step_path=str(path),source_sha256=sha(path),T_S_step=np.eye(4).tolist(),representation_role='FUNCTIONAL_ENVELOPE_OD6_R21_NO_CUT_LENGTH',is_ground_only=False,predecessor_ids=[f'internal_harness_proxy_{n}' for n in range(3)])
    b=cfg['battery'];center=np.array(b['min_S_mm'])+np.array(b['size_S_mm'])/2;path=A/'mechanical/battery_max_envelope.step'
    rows[b['id']]=dict(id=b['id'],step_path=str(path),source_sha256=sha(path),T_S_step=translation(*center).tolist(),representation_role=b['representation_role'],is_ground_only=False,predecessor_ids=[])
    emitted=[]
    for key,r in rows.items():
        assert sha(r['step_path'])==r['source_sha256']
        T=np.array(r['T_S_step']);assert np.max(abs(T[:3,:3].T@T[:3,:3]-np.eye(3)))<1e-8 and abs(np.linalg.det(T[:3,:3])-1)<1e-8
        emitted.append(dict(id=key,step_path=r['step_path'],source_sha256=r['source_sha256'],T_S_step=r['T_S_step'],representation_role=r.get('representation_role','INHERITED_SOURCE_REPRESENTATION'),is_ground_only=r['is_ground_only'],predecessor_ids=r.get('predecessor_ids',[key]),mass_inertia_requalification='NOT_REQUALIFIED_IN_THIS_VARIANT',native_geometry_current=False,source_parent_lookup=None if key.startswith('WP10_INTERNAL') or key==b['id'] else dict(plan=cfg['source_plan'],state=state,id=key)))
    assert len(emitted)==893 and len({r['id'] for r in emitted})==893
    pending=screen['pending_trunk_support_ids']+[f'release_power_data_route_{n}_{j}' for n in range(2) for j in range(2)]
    assert all(k in rows for k in pending)
    out['states'][state]=dict(rows=emitted,source_instances=len(emitted),changed_this_round=changed,pending_harness_instances_present=pending,local_propulsion_pair_checks=screen['test_count'])
out['component_count_identity']='894 -3 old main-trunk segments +1 continuous trunk +1 RRC max envelope =893; all8 pending trunk supports and4 old release segments remain present'
(A/'mechanical/BATTERY_ROUTE_INSTANCE_PLAN.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
allrows={r['id']:r for r in out['states']['service']['rows']};screen=read('results/BATTERY_PROPULSION_ROUTE_SCREEN_SERVICE.json')
selected={r['id'] for r in before['rows']}|set(screen['changed_ids'])|{k for q in screen['tests'] for k in q['ids']}
preview=dict(schema='WP10_BATTERY_ROUTE_LOCAL_PREVIEW_V1',status='LOCAL_VIEW_FROM893_INSTANCE_SOURCE_VARIANT__FULL_HARNESS_OPEN',input_sha256={'mechanical/BATTERY_ROUTE_INSTANCE_PLAN.json':sha(A/'mechanical/BATTERY_ROUTE_INSTANCE_PLAN.json')},rows=[allrows[k] for k in sorted(selected,key=lambda k:(k!='upper_equipment_deck_B',k))],omitted_pending_design_ids=out['states']['service']['pending_harness_instances_present'],snapshot_caption='电池外包络与推进两线/支柱/夹具修订；完整893实例源表保留未解决的主干夹具及释放支路，局部图不等于整机通过。',full_native_assembly=False)
preview['component_count']=len(preview['rows']);(A/'mechanical/BATTERY_ROUTE_PREVIEW_INPUTS.json').write_text(json.dumps(preview,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(full_source_instances_by_state={s:v['source_instances'] for s,v in out['states'].items()},local_preview_instances=preview['component_count'],pending_harness_instances=len(preview['omitted_pending_design_ids']),full_native=False)))
