"""Small CPU triangle BVH; no CAD runtime or dense ray/triangle matrix."""
import numpy as np
from numba import njit
def build_bvh(triangles,owners):
    lo=triangles.min(axis=1);hi=triangles.max(axis=1);centres=(lo+hi)/2
    bounds=[];children=[];spans=[];order=[]
    def rec(ids):
        node=len(bounds);bounds.append(np.r_[lo[ids].min(axis=0),hi[ids].max(axis=0)]);children.append([-1,-1]);spans.append([0,0])
        if len(ids)<=8:
            spans[node]=[len(order),len(ids)];order.extend(ids);return node
        axis=np.argmax(np.ptp(centres[ids],axis=0));ids=ids[np.argsort(centres[ids,axis])];mid=len(ids)//2
        children[node]=[rec(ids[:mid]),rec(ids[mid:])];return node
    rec(np.arange(len(triangles)));order=np.array(order)
    return np.ascontiguousarray(triangles[order]),np.ascontiguousarray(owners[order]),np.array(bounds),np.array(children),np.array(spans)

@njit(cache=True)
def ray_first_hit(points,directions,triangles,owners,bounds,children,spans):
    hits=np.full(len(points),-1,np.int32);distance=np.full(len(points),np.inf)
    for ray in range(len(points)):
        o=points[ray];d=directions[ray];stack=np.empty(128,np.int64);stack[0]=0;sp=1
        while sp:
            sp-=1;node=stack[sp];near=0.;far=distance[ray];boxok=True
            for k in range(3):
                if abs(d[k])<1e-15:
                    if o[k]<bounds[node,k] or o[k]>bounds[node,k+3]:boxok=False;break
                else:
                    a=(bounds[node,k]-o[k])/d[k];b=(bounds[node,k+3]-o[k])/d[k]
                    near=max(near,min(a,b));far=min(far,max(a,b))
            if not boxok or far<near:continue
            if children[node,0]>=0:
                if sp+2>128:raise ValueError('BVH traversal stack exhausted')
                stack[sp]=children[node,0];stack[sp+1]=children[node,1];sp+=2;continue
            start,count=spans[node]
            for it in range(start,start+count):
                t=triangles[it];e1=t[1]-t[0];e2=t[2]-t[0]
                h=np.cross(d,e2);det=np.dot(e1,h)
                if abs(det)<1e-12:continue
                inv=1/det;s=o-t[0];u=inv*np.dot(s,h)
                if u<0 or u>1:continue
                q=np.cross(s,e1);v=inv*np.dot(d,q)
                if v<0 or u+v>1:continue
                dist=inv*np.dot(e2,q)
                if dist>1e-5 and dist<distance[ray]:distance[ray]=dist;hits[ray]=owners[it]
    return hits,distance
