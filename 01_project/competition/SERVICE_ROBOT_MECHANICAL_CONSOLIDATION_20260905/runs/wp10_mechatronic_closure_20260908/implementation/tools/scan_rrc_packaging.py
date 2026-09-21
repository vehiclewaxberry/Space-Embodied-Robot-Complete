"""Conservative axis-aligned packaging search; no body/kernel or CAD mutation."""
from pathlib import Path
import json,hashlib,itertools,math
import numpy as np
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
boxes=read('thermal/RADIATOR_OBSTACLE_BOUNDS.json');plan=read('mechanical/FIXED_HEAT_INSTANCE_PLAN.json')
assert boxes['source_plan_sha256']==sha(A/'mechanical/FIXED_HEAT_INSTANCE_PLAN.json')
selected=read('power/POWER_CHAIN_SELECTION.json')['battery']
assert selected['MPN']=='RRC3570-4' and read('power/BATTERY_REVISION_CONFLICT.json')['active_revision']=='D'
assert sha(A/'sources/rrc3570_4.pdf')==read('power/BATTERY_REVISION_CONFLICT.json')['D']['sha256']
dimensions=selected['dimensions_max_mm'];assert dimensions==[189.5,85.5,82.2]
# Project design search domain, NOT a new bus/interface dimension guarantee.
domain=np.array([[-177.,-98.15,-98.15],[177.,98.15,98.15]])
clearance=2.;tol=1e-7
current={r['id']:r for r in plan['states']['service']['rows']}
obstacles=[]
hashed={}
for r in boxes['states']['service']:
    if r['step_path'] not in hashed:hashed[r['step_path']]=sha(r['step_path'])
    assert hashed[r['step_path']]==r['source_sha256']
    assert r['id'] in current
    b=np.array(r['bbox_S_mm'],float).reshape(2,3)
    assert np.isfinite(b).all() and np.all(b[1]>=b[0])
    if not r['is_ground_only'] and np.all(b[1]>domain[0]) and np.all(b[0]<domain[1]):obstacles.append(r)
assert any(r['id']=='equipment_battery' for r in obstacles) # keep legacy EPS reservation
b=np.array([r['bbox_S_mm'] for r in obstacles],float)
def solve(size,removed=()):
    mask=np.array([r['id'] not in removed for r in obstacles]);bb=b[mask]
    ids=[r['id'] for r,keep in zip(obstacles,mask) if keep]
    low=domain[0]+clearance;high=domain[1]-clearance-size
    if np.any(high<low):return dict(size_mm=size.tolist(),feasible_origins=[],xy_samples=0)
    xs=sorted(set([low[0],*[max(low[0],float(v+clearance)) for v in bb[:,3] if v+clearance<=high[0]+tol]]))
    ys=sorted(set([low[1],*[max(low[1],float(v+clearance)) for v in bb[:,4] if v+clearance<=high[1]+tol]]))
    found=[];samples=0
    for x in xs:
        xmask=(bb[:,0]<x+size[0]+clearance-tol)&(bb[:,3]>x-clearance+tol)
        for y in ys:
            samples+=1
            active=bb[xmask&(bb[:,1]<y+size[1]+clearance-tol)&(bb[:,4]>y-clearance+tol)]
            intervals=sorted((float(q[2]-size[2]-clearance),float(q[5]+clearance)) for q in active)
            z=float(low[2])
            for zlo,zhi in intervals:
                if z>high[2]+tol:break
                if zlo<z-tol and zhi>z+tol:z=zhi
            if z<=high[2]+tol:
                origin=np.array([x,y,z]);overlap=np.all(bb[:,:3]<origin+size+clearance-tol,axis=1)&np.all(bb[:,3:]>origin-clearance+tol,axis=1)
                assert not overlap.any(),[i for i,q in zip(ids,overlap) if q]
                found.append(dict(origin_S_mm=origin.tolist(),max_S_mm=(origin+size).tolist()))
    return dict(size_mm=size.tolist(),feasible_origin_count=len(found),feasible_origins=found[:20],xy_samples=samples)
orientations=[np.array(x) for x in sorted(set(itertools.permutations(dimensions)))]
rows=[solve(s) for s in orientations]
# Diagnostic only: removing old reservation is forbidden as an integration action.
# It identifies whether confusion between EPS and new arm storage drives a fit claim.
old_ids=['equipment_battery','adapter_battery','thermal_interface_battery','connector_battery']
diagnostic=[solve(s,old_ids) for s in orientations]
complex_ids=['radiator_spreader','shear_web_-1','shear_web_1']
narrow_required=[solve(s,complex_ids) for s in orientations]
output=dict(schema='WP10_RRC_BATTERY_PACKAGING_SCREEN_V1',
 status='CONSERVATIVE_BOX_PLACEMENTS_FOUND' if any(r.get('feasible_origin_count',0) for r in rows) else 'NO_CLEAR_AXIS_ALIGNED_BOX_PLACEMENT_FOUND',
 source_plan_sha256=sha(A/'mechanical/FIXED_HEAT_INSTANCE_PLAN.json'),source_script_sha256=sha(__file__),
 input_sha256={p:sha(A/p) for p in ['thermal/RADIATOR_OBSTACLE_BOUNDS.json','power/POWER_CHAIN_SELECTION.json','power/BATTERY_REVISION_CONFLICT.json','sources/rrc3570_4.pdf']},
 battery_revision='D',dimensions_max_mm=dimensions,domain_S_mm=domain.tolist(),nominal_design_clearance_mm=clearance,
 state='service',actual_hardware_geometry_bound=False,all_motion_states_verified=False,
 existing_EPS_battery_reservation_retained=True,obstacle_count=len(obstacles),source_hashes_checked=len(hashed),
 orientation_results=rows,diagnostic_only_remove_legacy_battery_ids=old_ids,diagnostic_only_results=diagnostic,
 complex_nonconvex_AABBs_deferred_to_exact_check=complex_ids,not_yet_feasible_narrow_phase_candidates=narrow_required,
 actual_candidate_modified=False,full_geometry_infeasibility_proved=False,mechanical_design_closed=False,
 limitations=['Axis-aligned bounding boxes conservatively fill holes; a failed box search does not prove CAD shape infeasibility.',
 'Any found body-box location still lacks connector/support/preload/thermal/maintenance/venting and moving-state validation.',
 'Legacy battery allocation remains; diagnostic removal is not an authorized deletion or a functional replacement.',
 'Search domain and 2mm gap are project packaging choices; they are not manufacturer tolerance, swelling or connector clearances.'])
(A/'results/RRC_BATTERY_PACKAGING_SCREEN.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status=output['status'],obstacles=len(obstacles),orientation_counts=[r.get('feasible_origin_count',0) for r in rows],diagnostic_removed_counts=[r.get('feasible_origin_count',0) for r in diagnostic],narrow_phase_required_counts=[r.get('feasible_origin_count',0) for r in narrow_required])))
