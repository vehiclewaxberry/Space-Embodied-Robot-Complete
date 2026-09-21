"""Select the same-state review subset without deleting any full-source instance."""
import json
from battery_variant_context import A,read,sha
p=read('mechanical/ROOT_BUSHING_INSTANCE_PLAN.json');s=read('results/ROOT_BUSHING_SCREEN_SERVICE.json')
assert s['status']=='ROOT_PASSAGE_STATIC_CAPTURE_CLEAR__THREAD_STRAIN_RELIEF_AND_RELEASE_OPEN' and s['source_plan_sha256']==sha(A/'mechanical/ROOT_BUSHING_INSTANCE_PLAN.json')
rows={r['id']:r for r in p['states']['service']['rows']};old=read('mechanical/TRUNK_SUPPORT_PREVIEW_INPUTS.json')
selected={r['id'] for r in old['rows']}|set(s['changed_ids']);assert len(selected)==136
out=dict(schema='WP10_ROOT_BUSHING_LOCAL_PREVIEW_V1',inputs={q:sha(A/q) for q in ['mechanical/ROOT_BUSHING_INSTANCE_PLAN.json','results/ROOT_BUSHING_SCREEN_SERVICE.json']},rows=[rows[k] for k in sorted(selected,key=lambda k:(k!='upper_equipment_deck_B',k))],component_count=len(selected),full_source_count=936,detail_ids=p['states']['service']['added_ids'],omitted_for_local_view=[k for k in rows if k not in selected],whole_fit_verified=False)
(A/'mechanical/ROOT_BUSHING_PREVIEW_INPUTS.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
src=(A/'mechanical/trunk_support_integration.step.py').read_text().replace('TRUNK_SUPPORT_PREVIEW_INPUTS','ROOT_BUSHING_PREVIEW_INPUTS').replace('WP10_TRUNK_SUPPORT_LOCAL','WP10_ROOT_BUSHING_LOCAL')
(A/'mechanical/root_bushing_integration.step.py').write_text(src,encoding='utf-8')
print(json.dumps(dict(local_instances=136,detail_instances=len(out['detail_ids']))))
