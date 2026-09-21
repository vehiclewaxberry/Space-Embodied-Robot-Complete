"""Select a review assembly from the complete current source table, never delete negatives."""
import json
from battery_variant_context import A,read,sha
p=read('mechanical/TRUNK_SUPPORT_INSTANCE_PLAN.json');s=read('results/TRUNK_SUPPORT_SCREEN_SERVICE.json');old=read('mechanical/BATTERY_ROUTE_PREVIEW_INPUTS.json')
assert s['source_plan_sha256']==sha(A/'mechanical/TRUNK_SUPPORT_INSTANCE_PLAN.json') and s['status']=='TRUNK_SUPPORT_STATIC_GEOMETRY_CLEAR__MATERIAL_PRELOAD_AND_RELEASE_BRANCHES_OPEN'
rows={r['id']:r for r in p['states']['service']['rows']};selected={r['id'] for r in old['rows']}|set(s['changed_ids'])|{k for q in s['tests'] for k in q['ids']}
out=dict(schema='WP10_TRUNK_SUPPORT_LOCAL_PREVIEW_V1',inputs={q:sha(A/q) for q in ['mechanical/TRUNK_SUPPORT_INSTANCE_PLAN.json','results/TRUNK_SUPPORT_SCREEN_SERVICE.json']},rows=[rows[k] for k in sorted(selected,key=lambda k:(k!='upper_equipment_deck_B',k))],component_count=len(selected),full_source_count=931,known_release_segments_in_full_source=p['states']['service']['known_pending_release_ids'],omitted_for_local_view=[k for k in rows if k not in selected],whole_fit_verified=False)
(A/'mechanical/TRUNK_SUPPORT_PREVIEW_INPUTS.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(dict(local_instances=len(selected),full_source_instances=931)))
