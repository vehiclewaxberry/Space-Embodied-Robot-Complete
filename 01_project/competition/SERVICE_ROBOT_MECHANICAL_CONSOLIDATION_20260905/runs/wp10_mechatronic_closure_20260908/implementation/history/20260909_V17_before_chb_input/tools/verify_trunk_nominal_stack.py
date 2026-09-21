"""Check actual STEP bounds for nominal full-nut axial coverage, not thread strength."""
import json
from battery_variant_context import A,read,sha
p=read('mechanical/TRUNK_SUPPORT_INSTANCE_PLAN.json');s=read('results/TRUNK_SUPPORT_SCREEN_SERVICE.json');assert s['source_plan_sha256']==sha(A/'mechanical/TRUNK_SUPPORT_INSTANCE_PLAN.json') and s['source_script_sha256']==sha(A/'tools/check_trunk_supports.py')
assert all(sha(q)==h for q,h in s['source_hashes'].items())
bb=s['changed_bboxes'];rows=[]
for prefix in [*[f'TRUNK_{i}' for i in range(4)],'TRUNK_HIGH_FOOT']:
    for j in range(2):
        sk=f'{prefix}_SCREW_{j}';nk=f'{prefix}_NUT_{j}';b=bb[sk];n=bb[nk];dx=max(abs((b[i]+b[i+3]-n[i]-n[i+3])/2) for i in [0,1]);overlap=max(0,min(b[5]-1.5,n[5])-max(b[2],n[2]));height=n[5]-n[2];protrusion=n[2]-b[2]
        rows.append(dict(screw=sk,nut=nk,axis_center_bbox_difference_mm=dx,nominal_nut_height_mm=height,nominal_axial_coverage_mm=overlap,tip_protrusion_mm=protrusion,passed=dx<1e-6 and abs(overlap-height)<1e-6 and protrusion>=.5))
out=dict(schema='WP10_TRUNK_NOMINAL_STACK_V1',source_script_sha256=sha(__file__),inputs={q:sha(A/q) for q in ['mechanical/TRUNK_SUPPORT_INSTANCE_PLAN.json','results/TRUNK_SUPPORT_SCREEN_SERVICE.json']},rows=rows,passed=all(r['passed'] for r in rows),thread_profile_strength_torque_locking_qualified=False,scope='Exact exported bounds and reused nominal symmetric M3 nut geometry; no real thread or fastening qualification')
assert out['passed'];(A/'results/TRUNK_NOMINAL_STACK.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(dict(checks=len(rows),minimum_tip_protrusion_mm=min(r['tip_protrusion_mm'] for r in rows),passed=True)))
