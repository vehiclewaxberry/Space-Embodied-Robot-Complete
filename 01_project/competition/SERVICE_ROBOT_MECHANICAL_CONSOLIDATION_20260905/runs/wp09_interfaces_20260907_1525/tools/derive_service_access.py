"""Conditional read-only interpretation of actual BRep service-prism results."""
from pathlib import Path
import json,hashlib
R=Path(__file__).resolve().parents[1]
p=R/'results/FRONT_SERVICE_PRISM_CHECK.json';d=json.loads(p.read_text())
assert d['status']=='HOLD_DECLARED_FRONT_SERVICE_PRISM'
bad=[x for x in d['checks'] if not x['ok']]
assert len(bad)==1 and bad[0]['id']=='front_service_cover'
remaining=[x for x in d['checks'] if x['id']!='front_service_cover']
assert all(x['ok'] for x in remaining)
out=dict(status='CONDITIONALLY_CLEAR_WITH_FRONT_COVER_ABSENT',source_path=str(p),source_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),original_closed_cover_status=d['status'],original_overlap_mm3=bad[0]['intersection_volume_mm3'],assumed_absent_ids=['front_service_cover'],basis='EXACT_REUSE_OF_ORIGINAL_PAIR_RESULTS_NO_NEW_CAD_RUN',remaining_checked_pairs=len(remaining),all_three_discrete_states=True,cover_removal_motion_verified=False,actual_tool_models_bound=False,plume_verified=False,condition='Ground maintenance with front cover already removed; cover removal sequence and tool access require further verification. This is not an assembled-cover PASS.')
(R/'results/FRONT_SERVICE_ACCESS_CONDITIONAL.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(out['status'])
