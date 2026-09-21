from geometry import *
core=source(read(R6/'inputs/MAIN_GEOMETRY_COVERAGE.json')['board']);host=state_rows()['service'];trials=[]
for x,y,z in [(-166,84,z) for z in [10,14,18,22]]+[(-162,y,z) for y in [82,86] for z in [10,14,18]]:
    T=np.eye(4);T[:3,3]=[x,y,z];s=moved(core,T);hits=[];unknown=[]
    for r in candidates(s,host):
        try:
            v=g.volume(common(s,source(r)))
            if v>1e-5:hits.append(dict(id=r['id'],volume_mm3=v))
        except Exception as e:unknown.append(dict(id=r['id'],error=str(e)))
    trial=dict(T_S_core=T.tolist(),xyz=[x,y,z],hits=hits,unknown=unknown);trials.append(trial)
    print(x,y,z,hits,unknown,flush=True);write(D/'results/HORIZONTAL_SEARCH.json',dict(trials=trials))
    if not hits and not unknown:
        write(D/'inputs/MAIN_HORIZONTAL_POSE.json',trial);break
