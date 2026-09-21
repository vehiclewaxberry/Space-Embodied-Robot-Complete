"""Reuse SHA-identical source tessellations after source instance pose repair."""
from pathlib import Path
import hashlib,json,shutil,gc
import numpy as np
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=A/'thermal/RADIATOR_MESH_MANIFEST.json';old=json.loads(p.read_text());bounds=json.loads((A/'thermal/RADIATOR_OBSTACLE_BOUNDS.json').read_text())
archive=A/'history/20260909_before_radiator_view_binding/stale_pose_mesh';archive.mkdir(exist_ok=True)
if not (archive/p.name).exists():shutil.copy2(p,archive/p.name)
probes=[(1,-1,-113.15),(1,1,113.15),(0,1,185.),(0,-1,-189.),(2,-1,-114.),(2,1,114.)]
records={};audit=[]
for state,record in old['states'].items():
    path=A/record['path'];assert sha(path)==record['sha256']
    if not (archive/path.name).exists():shutil.copy2(path,archive/path.name)
    rows=[r for r in bounds['states'][state] if not r['is_ground_only'] and any(max(s*(r['bbox_S_mm'][k]-v),s*(r['bbox_S_mm'][k+3]-v))>1e-5 for k,s,v in probes)]
    previous={r['id']:(i,r) for i,r in enumerate(record['rows'])};assert {r['id'] for r in rows}<=set(previous)
    with np.load(path) as data:triangles=data['triangles'];owners=data['owners']
    retained={previous[r['id']][0] for r in rows};mask=np.isin(owners,list(retained));out=triangles[mask].copy();old_owner=owners[mask];new_owner=np.empty(len(out),np.int32)
    for i,row in enumerate(rows):
        oi,prior=previous[row['id']];assert prior['source_sha256']==row['source_sha256']
        loc=old_owner==oi;new_owner[loc]=i
        delta=np.array(row['T_S_step'])@np.linalg.inv(np.array(prior['T_S_step']))
        if np.max(abs(delta-np.eye(4)))>1e-10:out[loc]=out[loc]@delta[:3,:3].T+delta[:3,3]
        if row['id'].startswith('wing_') and '_leaf_' in row['id']:
            b=np.r_[out[loc].reshape(-1,3).min(axis=0),out[loc].reshape(-1,3).max(axis=0)]
            err=float(np.max(abs(b-row['bbox_S_mm'])));assert err<1e-5
            audit.append(dict(state=state,id=row['id'],mesh_to_current_world_bbox_max_error_mm=err))
    np.savez_compressed(path,triangles=out,owners=new_owner)
    records[state]=dict(rows=rows,triangle_count=len(out),path=path.relative_to(A).as_posix(),sha256=sha(path))
    print(json.dumps(dict(state=state,triangles=len(out),rows=len(rows))),flush=True)
    del triangles,owners,out,new_owner,old_owner,mask;gc.collect()
old.update(schema='WP10_STEP_OBSTRUCTION_MESH_V2',bounds_input_sha256=sha(A/'thermal/RADIATOR_OBSTACLE_BOUNDS.json'),
    source_plan_sha256=bounds['source_plan_sha256'],states=records,rebind_source_sha256=sha(__file__),
    rebind_basis='world_new = T_STEP_current * inverse(T_STEP_previous) * world_previous; identical source STEP SHA required per instance',
    predecessor_manifest_path=str(archive/p.name),predecessor_manifest_sha256=sha(archive/p.name),
    leaf_corner_audit=audit,stale_pose_source_mesh_is_not_current_output=True,
    source_hash_note='Original tessellation algorithm retained; during its run only a stale-input precheck was added to the source. This rebind explicitly validates recorded per-instance source identity and pose instead of crediting that precheck retroactively.')
p.write_text(json.dumps(old,indent=2),encoding='utf-8')
