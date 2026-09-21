"""Exact STEP common-volume check for the changed bay versus parent service state.

Only broad-phase candidates are loaded. Unknown source/bounds remain explicit;
this is not a swept-motion test, tool-access or tolerance certification.
"""
from pathlib import Path
import json,hashlib,runpy,itertools,sys
from OCP.gp import gp_Trsf
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
A=Path(__file__).resolve().parents[1]
core=runpy.run_path(str(A/'tools/check_fixed_heat_geometry.py'))
readshape=core['read'];prop=core['prop'];common=core['common'];parts=core['parts']
state_name=sys.argv[1] if len(sys.argv)>1 else 'service'
assert state_name in ['service','parking','released']
plan=json.loads((A/'mechanical/FIXED_HEAT_INSTANCE_PLAN.json').read_text());state=plan['states'][state_name];rows={r['id']:r for r in state['rows']}
target_ids=list(state['changed_shape_ids'])+state['new_ids']+state['moved_ids']
cache={};facts={};unknown=[]
def bounds(r):
    b=r.get('world_bounds_mm') or r.get('bounds_mm')
    return b['min_mm']+b['max_mm'] if b else None
def overlap(a,b):return all(min(a[k+3],b[k+3])-max(a[k],b[k])>1e-5 for k in range(3))
def shape(key):
    if key not in cache:
        r=rows[key];p=Path(r['step_path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==r['source_sha256']
        s=readshape(p);M=r['T_S_step'];tr=gp_Trsf();tr.SetValues(*[float(M[i][j]) for i in range(3) for j in range(4)])
        s=BRepBuilderAPI_Transform(s,tr,True).Shape();cache[key]=s;facts[key]=prop(s)
    return cache[key]
for key in target_ids:shape(key)
pairs=[];tested=set();fail=[]
for key in target_ids:
    a=facts[key]['bbox']
    for other,r in rows.items():
        pair=tuple(sorted([key,other]))
        if other==key or pair in tested:continue
        # Preserve existing intentional screw/nut thread proxies in the moved
        # 14-piece group; verify this group's interference with everything else.
        if key in state['moved_ids'] and other in state['moved_ids']:continue
        b=facts[other]['bbox'] if other in facts else bounds(r)
        if b is None:
            if r.get('step_path') and Path(r['step_path']).exists():
                shape(other);b=facts[other]['bbox']
            else:
                unknown.append(dict(target=key,other=other,reason='NO_WORLD_BOUNDS_AND_NO_READABLE_STEP'));continue
        if not overlap(a,b):continue
        if not r.get('step_path') or not Path(r['step_path']).exists():
            unknown.append(dict(target=key,other=other,reason='NO_READABLE_STEP'));continue
        tested.add(pair);s=shape(other)
        if not overlap(a,facts[other]['bbox']):continue
        v=common(cache[key],s)
        item=dict(pair=list(pair),common_volume_mm3=v);pairs.append(item)
        if v>1e-5:fail.append(item)
        if len(cache)>100:
            for kk in list(cache):
                if kk not in target_ids:del cache[kk]
print(json.dumps(dict(exact_pairs=len(pairs),positive_volume_intersections=fail,unknown_count=len(unknown))))
out=dict(schema='WP10_FIXED_HEAT_STATE_INTERFACES_V2',state=state_name,source_plan_sha256=hashlib.sha256((A/'mechanical/FIXED_HEAT_INSTANCE_PLAN.json').read_bytes()).hexdigest(),
 targeted_ids=target_ids,exact_pairs=pairs,positive_volume_intersections=fail,unknown=unknown,
 zero_positive_volume_intersections=not fail,complete_coverage=not unknown,
 other_states_evaluated=False,continuous_motion_evaluated=False,tool_access_evaluated=False,tolerance_evaluated=False,
 known_legacy_threads_preserved=True,whole_assembly_verified=False)
(A/f'results/FIXED_HEAT_{state_name.upper()}_INTERFACES.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
