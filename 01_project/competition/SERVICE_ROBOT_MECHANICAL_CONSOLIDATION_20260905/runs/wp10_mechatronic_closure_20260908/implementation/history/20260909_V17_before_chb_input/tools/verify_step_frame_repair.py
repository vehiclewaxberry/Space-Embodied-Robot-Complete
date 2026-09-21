from pathlib import Path
import hashlib,json
import numpy as np
from build_radiator_obstacle_bounds import source_bounds
A=Path(__file__).resolve().parents[1]
p=json.loads((A/'mechanical/FIXED_HEAT_INSTANCE_PLAN.json').read_text())
checks=[]
for state,record in p['states'].items():
    for row in record['rows']:
        if row['id'].startswith('wing_') and '_leaf_' in row['id']:
            actual=source_bounds(row);bb=row['world_bounds_mm'];expected=bb['min_mm']+bb['max_mm']
            delta=float(np.max(np.abs(np.array(actual)-expected)))
            checks.append(dict(state=state,id=row['id'],actual_STEP_bbox_S_mm=actual,parent_current_world_bbox_mm=expected,max_delta_mm=delta,passed=delta<1e-5))
assert len(checks)==18 and all(c['passed'] for c in checks)
r=json.loads((A/'results/FIXED_HEAT_STEP_FRAME_REPAIR.json').read_text())
r.update(independent_STEP_corner_readback_verified=True,leaf_readback_checks=checks,checked_leaf_instances=18,
    changed_pose_count_by_state={s:len(items) for s,items in r['repairs_by_state'].items()})
(A/'results/FIXED_HEAT_STEP_FRAME_REPAIR.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
print(json.dumps(dict(checks=len(checks),max_delta_mm=max(c['max_delta_mm'] for c in checks),corrected_poses=r['changed_pose_count_by_state'])))
