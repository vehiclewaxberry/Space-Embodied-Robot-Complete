from geometry import *
v36=read(R5/'inputs/V36_SOURCE_MAP.json');v30={r['id']:r for r in read(R5/'inputs/V30_SOURCE_MAP.json')['rows']}
shapes=[source(r) for r in v36['rows']];T=np.eye(4);T[2,3]=1.595
for ident in ['V30_002','V30_006','V30_007','V30_008','V30_009','V30_014']:shapes.append(moved(source(v30[ident]),T))
shapes.append(box(41.55,-18.3,1.795,48.45,-11.7,4.945))
core=compound(shapes);rows=state_rows()['service'];trials=[]
for x,y,z in [(x,y,z) for x in [-65,-62,-59] for y in [-50,-46] for z in [-70,-62,-54]]:
 T=np.array([[0,-1,0,x],[1,0,0,y],[0,0,1,z],[0,0,0,1]],dtype=float);s=moved(core,T);hits=[];unknown=[]
 for r in candidates(s,rows):
  try:
   v=g.volume(common(s,source(r)))
   if v>1e-5:hits.append({'id':r['id'],'volume_mm3':v})
  except Exception as ex:unknown.append({'id':r['id'],'error':str(ex)})
 q={'orientation':'Rz90_lower','xyz':[x,y,z],'T_S_core':T.tolist(),'hits':hits,'unknown':unknown,'overlap_mm3':sum(v['volume_mm3'] for v in hits)};trials.append(q)
 print(x,y,z,'hits',len(hits),'volume',round(q['overlap_mm3'],3),[v['id'] for v in hits],flush=True)
 write(D/'results/CORE_LOWER_SEARCH.json',{'scope':'Partial populated model cavity screening; complete validation follows','trials':trials})
 if not hits and not unknown:break
