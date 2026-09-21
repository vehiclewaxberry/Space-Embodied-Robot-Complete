"""24 orthogonal orientations of the unchanged source-bound local module.

Carrier screening uses its eight additive feature boxes plus four posts rather
than treating the arch's empty interior as solid. Holes remain conservatively
filled. This only ranks poses; it cannot certify fit or mounting.
"""
from pathlib import Path
import datetime, hashlib, itertools, json, time
import numpy as np

HERE=Path(__file__).resolve().parent
A=HERE.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def run():
    outpath=HERE/'ORIENTATION_SCREEN_V28.json'
    assert not outpath.exists(),'Retain prior results'
    c=read(HERE/'CANDIDATE.json')
    assert all(sha(p)==h for p,h in c['source_lock'].items())
    g=read(HERE/'MECHANICAL_VERIFICATION.json')
    assert g['source_sha256']==sha(HERE/'mechanical_parts.py')
    bounds_file=A/'mechanical/MAIN_INPUT_PLACEMENT_BOUNDS_V27.json'
    p=read(bounds_file)
    assert sha(A/p['source_plan'])==p['source_plan_sha256']
    parts=[r for r in g['parts'] if r['group']=='main']
    assert parts[0]['bbox_mm']==[-16.,-86.,-11.6,116.,6.000000000000002,32.]
    # Exact conservative union of all additive MC01 features in current source.
    features=[[-16,-86,-11.6,116,6,-7.6],
              [39.45,1,-7.6,79.45,6,32],
              [39.45,-14.597,27,79.45,6,32],
              [39.45,-14.597,3,79.45,-9.597,32]]
    names=['carrier_plate','edge_riser','overhead_bridge','tab_contact_leg']
    owners=[0]*4
    for x,y in [(4,-4),(96,-4),(4,-76),(96,-76)]:
        features.append([x-3.5,y-3.5,-7.6,x+3.5,y+3.5,-1.6])
        names.append('carrier_post_'+str(len(names)-4));owners.append(0)
    for r in parts[1:]:
        features.append(r['bbox_mm']);names.append(r['label']);owners.append(r['index'])
    local=np.asarray(features);center=(local[:,:3]+local[:,3:])/2;half=(local[:,3:]-local[:,:3])/2
    enclosure=np.asarray([-168,-95,-100,168,95,100],dtype=float)
    rows=[r for r in p['states']['service'] if all(min(r['bbox_S_mm'][k+3],enclosure[k+3])-max(r['bbox_S_mm'][k],enclosure[k])>0 for k in range(3))]
    host=np.asarray([r['bbox_S_mm'] for r in rows])
    hc=(host[:,:3]+host[:,3:])/2;hh=(host[:,3:]-host[:,:3])/2
    rotations=[]
    for perm in itertools.permutations(range(3)):
        for signs in itertools.product([-1,1],repeat=3):
            R=np.zeros((3,3),dtype=int)
            for i in range(3):R[i,perm[i]]=signs[i]
            if round(np.linalg.det(R))==1:rotations.append(R)
    best=[];summaries=[];total=0;start=time.monotonic();gap=1.0
    for ri,R in enumerate(rotations):
        centers=center@R.T;halves=half@abs(R).T
        limits=np.array([(centers-halves).min(axis=0),(centers+halves).max(axis=0)])
        low=enclosure[:3]-limits[0]+gap;high=enclosure[3:]-limits[1]-gap
        axes=[np.arange(np.ceil(low[i]/10)*10,np.floor(high[i]/10)*10+1,10) for i in range(3)]
        shifts=np.asarray(list(itertools.product(*axes)));rank=[]
        for k in range(0,len(shifts),24):
            ts=shifts[k:k+24]
            hit=np.ones((len(ts),len(features),len(host)),dtype=bool)
            for j in range(3):
                hit &= abs(centers[None,:,None,j]+ts[:,None,None,j]-hc[None,None,:,j]) < (halves[None,:,None,j]+hh[None,None,:,j]+gap)
            counts=hit.sum(axis=(1,2))
            for n in np.argsort(counts)[:8]:rank.append((int(counts[n]),ts[n].tolist()))
        rank.sort(key=lambda x:x[0]);rank=rank[:12]
        for count,t in rank:
            hit=np.ones((len(features),len(host)),dtype=bool)
            for j in range(3):hit &= abs(centers[:,None,j]+t[j]-hc[None,:,j]) < halves[:,None,j]+hh[None,:,j]+gap
            best.append(dict(feature_pairs=count,rotation_index=ri,R=R.tolist(),translation_mm=t,
                part_host_pairs=len({(owners[i],j) for i,j in np.argwhere(hit)}),
                hosts=[dict(id=rows[j]['id'],role=rows[j]['representation_role']) for j in np.flatnonzero(hit.any(axis=0))]))
        total+=len(shifts);summaries.append(dict(rotation_index=ri,poses=len(shifts),min_pairs=rank[0][0] if rank else None))
        print(json.dumps(dict(rotation=ri,poses=len(shifts),best=rank[0] if rank else None)),flush=True)
    best.sort(key=lambda r:(r['part_host_pairs'],r['feature_pairs']))
    out=dict(schema='WP10_V28_ORTHOGONAL_LAYOUT_SEARCH',time_local=datetime.datetime.now().astimezone().isoformat(),
        script_sha256=sha(__file__),mechanical_source_sha256=sha(HERE/'mechanical_parts.py'),
        bounds_sha256=sha(bounds_file),parent_plan_sha256=p['source_plan_sha256'],
        state='service',orientations=len(rotations),poses=total,elapsed_s=time.monotonic()-start,
        enclosure_search_limit_mm=enclosure.tolist(),project_screen_clearance_mm=gap,
        carrier_feature_boxes=[dict(name=n,box=b) for n,b in zip(names,features)],
        summaries=summaries,best=best[:40],all_placements_infeasible=False,
        full_population_model=False,native_fit_verified=False,
        note='Finite grid over unchanged partial module; source feature boxes include holes as filled. '
             'Enclosure and 1mm clearance are screening allocations. Native verification and real host mounting required.')
    with outpath.open('x',encoding='utf-8') as f:json.dump(out,f,indent=2,ensure_ascii=False)
    print(json.dumps(dict(total=total,best=best[:3],elapsed_s=out['elapsed_s'])))

if __name__=='__main__':run()
