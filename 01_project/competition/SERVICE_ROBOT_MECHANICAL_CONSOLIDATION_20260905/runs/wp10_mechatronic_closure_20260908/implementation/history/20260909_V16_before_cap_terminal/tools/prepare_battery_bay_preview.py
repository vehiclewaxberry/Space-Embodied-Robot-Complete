"""Prepare a same-source local assembly; explicitly not the whole candidate."""
from pathlib import Path
import json,hashlib
import numpy as np
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
c=read('mechanical/BATTERY_BAY_LAYOUT.json');p=read(c['source_plan']);screen=read('results/BATTERY_RELAYOUT_SEED_SCREEN.json')
passage=read('mechanical/BATTERY_HARNESS_PASSAGE.json');routing=read('results/BATTERY_INTERNAL_ROUTE_SCREEN.json')
assert routing['status']=='ROUTE_BODY_SCREEN_CLEAR__CLAMPS_AND_JUNCTIONS_PENDING'
assert all(sha(A/q)==h for q,h in routing['input_sha256'].items())
assert c['source_plan_sha256']==sha(A/c['source_plan'])
assert screen['status']=='BODY_AND_MOVED_GROUPS_SCREEN_CLEAR__MOUNT_AND_REROUTE_PENDING'
assert screen['input_sha256']['mechanical/BATTERY_BAY_LAYOUT.json']==sha(A/'mechanical/BATTERY_BAY_LAYOUT.json')
rows={r['id']:r for r in p['states']['service']['rows']};moves={}
for group in c['rigid_group_moves']:
    ids=group.get('ids') or [x for x in rows if x.startswith(group['id_prefix'])]
    R=np.array(group['rotation_S']);D=np.eye(4);D[:3,:3]=R;D[:3,3]=np.array(group['to_center_S_mm'])-R@np.array(group['from_center_S_mm'])
    for key in ids:moves[key]=D
assert set(moves)==set(screen['moved_ids'])
context={'upper_equipment_deck_B','shear_web_-1','shear_web_1','RB_upper_beam_20','RB_upper_beam_160','hold_crossbeam_0','hold_crossbeam_1'}|{f'RB_pillar_{k}' for k in range(4)}
context|={k for r in screen['moved_group_tests'] for k in r['ids']}
context|={r['id'] for r in screen['battery_tests']}
context|=set(passage['rows'])
selected=context|set(moves);assert selected.isdisjoint(screen['reroute_or_rework_required_ids'])
out=[]
for key in sorted(selected,key=lambda k:(k!='upper_equipment_deck_B',k)):
    r=rows[key];override=c['source_overrides'].get(key)
    pp=passage['rows'].get(key);path=A/pp if pp else (A/override['step_path'] if override else Path(r['step_path']));h=sha(path)
    assert h==(routing['input_sha256'][pp] if pp else (screen['source_override_sha256'][override['step_path']] if override else r['source_sha256']))
    T=np.eye(4) if override or pp else moves.get(key,np.eye(4))@np.array(r['T_S_step'])
    out.append(dict(id=key,step_path=str(path),source_sha256=h,T_S_step=T.tolist(),representation_role=r.get('representation_role'),scope='MOVED_GROUP' if key in moves else 'FIXED_CONTEXT_OR_HOST_EDIT'))
b=c['battery'];T=np.eye(4);T[:3,3]=np.array(b['min_S_mm'])+np.array(b['size_S_mm'])/2
path=A/'mechanical/battery_max_envelope.step'
out.append(dict(id=b['id'],step_path=str(path),source_sha256=sha(path),T_S_step=T.tolist(),representation_role=b['representation_role'],scope='UNBOUND_MAXIMUM_BODY_ALLOCATION'))
path=A/'mechanical/battery_internal_route.step';out.append(dict(id='WP10_INTERNAL_BATTERY_BYPASS',step_path=str(path),source_sha256=sha(path),T_S_step=np.eye(4).tolist(),representation_role='FUNCTIONAL_OD6_R21_NO_PIN_OR_CUT_LENGTH',scope='NEW_ROUTE_WITH_PASSAGE__CLAMPS_AND_JUNCTIONS_PENDING'))
r=dict(schema='WP10_BATTERY_BAY_PREVIEW_INPUTS_V1',status='LOCAL_RELAYOUT_PREVIEW__REROUTE_AND_MOUNTING_PENDING',
 input_sha256={q:sha(A/q) for q in ['mechanical/BATTERY_BAY_LAYOUT.json',c['source_plan'],'results/BATTERY_RELAYOUT_SEED_SCREEN.json','mechanical/BATTERY_HARNESS_PASSAGE.json','results/BATTERY_INTERNAL_ROUTE_SCREEN.json']},
 source_script_sha256=sha(__file__),rows=out,component_count=len(out),whole_native_assembly=False,
 omitted_from_this_local_view_but_still_required=screen['reroute_or_rework_required_ids']+routing['branch_junctions_pending'],battery_hold_down_present=False,
 snapshot_caption='电池最大外包络与上层重布置；必要改线和保持结构仍未完成，省略对象不得据图视为已解决。')
(A/'mechanical/BATTERY_BAY_PREVIEW_INPUTS.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(local_instances=len(out),moved_retained_instances=len(moves),new_actual_host='upper_equipment_deck_B',battery='D_MAX_ENVELOPE_ONLY')))
