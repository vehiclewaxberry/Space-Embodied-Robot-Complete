"""Pure-data, same-candidate instance transforms for battery routing work."""
from pathlib import Path
import json,hashlib,copy
import numpy as np
A=Path(__file__).resolve().parents[1]
def read(q):return json.loads((A/q).read_text(encoding='utf-8-sig'))
def sha(q):return hashlib.sha256(Path(q).read_bytes()).hexdigest()
def translation(x,y,z):
    T=np.eye(4);T[:3,3]=[x,y,z];return T
def move_bbox(bb,M):
    b=np.array(bb).reshape(2,3);q=np.array([[x,y,z,1] for x in b[:,0] for y in b[:,1] for z in b[:,2]])@M.T
    return np.r_[q[:,:3].min(0),q[:,:3].max(0)].tolist()
def baseline(state='service'):
    cfg=read('mechanical/BATTERY_BAY_LAYOUT.json');plan=read(cfg['source_plan']);bounds=read('thermal/RADIATOR_OBSTACLE_BOUNDS.json');passage=read('mechanical/BATTERY_HARNESS_PASSAGE.json')
    assert sha(A/cfg['source_plan'])==cfg['source_plan_sha256']==bounds['source_plan_sha256']==passage['source_plan_sha256']
    seed=read('results/BATTERY_RELAYOUT_SEED_SCREEN.json');assert all(sha(A/q)==h for q,h in seed['input_sha256'].items())
    assert all(sha(A/q)==h for q,h in seed['source_override_sha256'].items())
    rows={r['id']:copy.deepcopy(r) for r in plan['states'][state]['rows']};bb={r['id']:r for r in bounds['states'][state]}
    moves={}
    for g in cfg['rigid_group_moves']:
        R=np.array(g['rotation_S']);T=np.eye(4);T[:3,:3]=R;T[:3,3]=np.array(g['to_center_S_mm'])-R@np.array(g['from_center_S_mm'])
        for k in g.get('ids') or [k for k in rows if k.startswith(g['id_prefix'])]:moves[k]=T
    for k,r in rows.items():
        D=moves.get(k,np.eye(4));r['bbox_S_mm']=move_bbox(bb[k]['bbox_S_mm'],D);r['is_ground_only']=bb[k]['is_ground_only'];r['T_S_step']=(D@np.array(r['T_S_step'])).tolist()
        q=cfg['source_overrides'].get(k);path=passage['rows'].get(k) or (q['step_path'] if q else None)
        if path:r.update(step_path=str(A/path),source_sha256=sha(A/path),T_S_step=np.eye(4).tolist(),native_geometry_current=False)
    return rows
def propulsion_variant(state='service'):
    rows=baseline(state);c=read('mechanical/BATTERY_PROPULSION_ROUTING.json');d=c['dual_clamp'];changed=[]
    def override(k,stem,T=np.eye(4)):
        path=A/f'mechanical/{stem}.step';rows[k].update(step_path=str(path),source_sha256=sha(path),T_S_step=T.tolist(),native_geometry_current=False,geometry_revision='WP10_BATTERY_PROPULSION_ROUTING');changed.append(k)
    for k,stem in [('PROP_PWR_ROUTE','battery_prop_power'),('PROP_DATA_ROUTE','battery_prop_data'),('CLAMP_DUAL_BASE','battery_dual_base'),('CLAMP_DUAL_LID','battery_dual_lid'),('upper_equipment_deck_B','battery_route_deck')]:override(k,stem)
    for n,(x,y) in enumerate(d['stud_xy_mm']):
        override(f'POST_DUAL_{n}','battery_dual_post',translation(x,y,d['post_z_mm'][0]));override(f'TIEROD_DUAL_{n}','battery_dual_rod',translation(x,y,d['rod_z_mm'][0]))
        ox,oy=d['old_stud_xy_mm'][n]
        for suffix in ['BN','BW','TN','TW']:
            k=f'CLAMP_DUAL_{n}_{suffix}';D=translation(x-ox,y-oy,d['top_hardware_dz_mm'] if suffix.startswith('T') else 0);rows[k]['T_S_step']=(D@np.array(rows[k]['T_S_step'])).tolist();rows[k]['bbox_S_mm']=move_bbox(rows[k]['bbox_S_mm'],D);rows[k]['native_geometry_current']=False;changed.append(k)
    assert len(changed)==17
    return rows,changed
