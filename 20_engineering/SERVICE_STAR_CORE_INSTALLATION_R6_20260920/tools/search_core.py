from geometry import *
import math
v36=read(R5/'inputs/V36_SOURCE_MAP.json');v30={r['id']:r for r in read(R5/'inputs/V30_SOURCE_MAP.json')['rows']}
shapes=[source(r) for r in v36['rows']]
# Additional existing catalogue/OEM references are translated to the KiCad top datum.
T=np.eye(4);T[2,3]=1.595
for ident in ['V30_002','V30_006','V30_007','V30_008','V30_009','V30_014']:
    shapes.append(moved(source(v30[ident]),T))
# Current R202 is 0.5mOhm; max-height conservative body, not the old 0.2mOhm geometry.
shapes.append(box(41.55,-18.3,1.795,48.45,-11.7,4.945))
core=compound(shapes);rows=state_rows()['service'];trials=[]
orientations={
 'flat':np.eye(3),
 'side_minusX':np.array([[0,0,1],[0,1,0],[-1,0,0]]),
 'side_minusX_flipY':np.array([[0,0,1],[0,-1,0],[1,0,0]]),
}
poses=[('flat',x,y,z) for x in [-158,-156,-154] for y in [76,77,78] for z in [21,24]]
poses += [('side_minusX',x,y,z) for x in [-170,-167,-165] for y in [38,43,48] for z in [96,99]]
poses += [('side_minusX_flipY',x,y,z) for x in [-170,-167,-165] for y in [-38,-43] for z in [-5,-2]]
for orient,x,y,z in poses:
 T=np.eye(4);T[:3,:3]=orientations[orient];T[:3,3]=[x,y,z];s=moved(core,T);hits=[];unknown=[]
 for r in candidates(s,rows):
  try:
   v=g.volume(common(s,source(r)))
   if v>1e-5:hits.append({'id':r['id'],'volume_mm3':v})
  except Exception as ex:unknown.append({'id':r['id'],'error':str(ex)})
 q={'orientation':orient,'xyz':[x,y,z],'T_S_core':T.tolist(),'hits':hits,'unknown':unknown,'overlap_mm3':sum(v['volume_mm3'] for v in hits)};trials.append(q)
 print(orient,x,y,z,'hits',len(hits),'volume',round(q['overlap_mm3'],3),[v['id'] for v in hits],flush=True)
 write(D/'results/CORE_SEARCH.json',{'scope':'Partial V36 populated model plus critical catalogue bodies; not complete PCBA clearance','trials':trials})
 if not hits and not unknown:
  emit('R6_MAIN_CORE_SEARCH',s,'PARTIAL_POPULATION_SEARCH_ONLY');break
print('best',min(trials,key=lambda r:r['overlap_mm3']),flush=True)
