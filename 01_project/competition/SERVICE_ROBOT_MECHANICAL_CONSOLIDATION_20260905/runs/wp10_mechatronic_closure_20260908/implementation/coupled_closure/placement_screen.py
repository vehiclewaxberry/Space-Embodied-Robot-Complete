"""Bounded translation screen for one orientation; AABB hits are not collisions."""
import numpy as np
from coupled_adapter import HERE,A,read,sha,dump,load_candidate

def run():
    load_candidate()
    p=read(A/'mechanical/MAIN_INPUT_PLACEMENT_BOUNDS_V27.json')
    g=read(HERE/'MECHANICAL_VERIFICATION.json')
    assert sha(A/p['source_plan'])==p['source_plan_sha256']
    assert g['source_sha256']==sha(HERE/'mechanical_parts.py')
    rows=p['states']['service'];host=np.array([r['bbox_S_mm'] for r in rows])
    a=np.array([r['bbox_mm'] for r in g['parts'] if r['group']=='main'])
    base=np.stack((a[:,0],-a[:,5],a[:,1],a[:,3],-a[:,2],a[:,4]),axis=1)
    rank=[]
    ys=list(range(80,-61,-10));xs=list(range(-150,51,10));zs=list(range(-10,91,10))
    for y in ys:
        for x in xs:
            for z in zs:
                b=base+np.array([x,y,z,x,y,z])
                hits=np.all(np.minimum(b[:,None,3:],host[None,:,3:])-np.maximum(b[:,None,:3],host[None,:,:3])>1e-5,axis=2)
                rank.append((int(hits.sum()),x,y,z,int(np.count_nonzero(hits.any(axis=0)))))
    rank.sort();best=[]
    for count,x,y,z,hosts in rank[:20]:
        b=base+np.array([x,y,z,x,y,z])
        hits=np.all(np.minimum(b[:,None,3:],host[None,:,3:])-np.maximum(b[:,None,:3],host[None,:,:3])>1e-5,axis=2)
        best.append(dict(pair_count=count,translation_mm=[x,y,z],host_count=hosts,
            host_roles=[dict(id=rows[i]['id'],role=rows[i]['representation_role']) for i in np.flatnonzero(hits.any(axis=0))]))
    out=dict(script_sha256=sha(__file__),mechanical_source_sha256=sha(HERE/'mechanical_parts.py'),
        bounds_source_sha256=sha(A/'mechanical/MAIN_INPUT_PLACEMENT_BOUNDS_V27.json'),
        orientation=[[1,0,0],[0,0,-1],[0,1,0]],axes_mm=dict(x=xs,y=ys,z=zs),
        state='service',poses_screened=len(rank),zero_AABB_hit_poses=sum(r[0]==0 for r in rank),
        best=best,installed=False,scope='Translation grid for current partial module and saved bounds, one orientation only. '
        'Positive AABB overlap does not prove solid interference. This search neither exhausts layouts nor proves no installation exists.')
    dump('PLACEMENT_TRANSLATION_SCREEN.json',out)
    print(dict(poses_screened=len(rank),zero_AABB_hit_poses=out['zero_AABB_hit_poses'],min_pair_count=rank[0][0]))

if __name__=='__main__':run()
