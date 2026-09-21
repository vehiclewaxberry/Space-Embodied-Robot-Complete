from geometry import *
import math
core=source(read(D/'inputs/MAIN_GEOMETRY_COVERAGE.json')['board']);rows=state_rows()['service'];trials=[]
for ang,x,y,z in [(a,x,74.5,z) for a in [20,18,22,15,25] for x in [-156,-157] for z in [9,12,15]]:
 a=math.radians(ang);T=np.array([[1,0,0,x],[0,math.cos(a),math.sin(a),y],[0,-math.sin(a),math.cos(a),z],[0,0,0,1]])
 s=moved(core,T);hits=[];unknown=[]
 for r in candidates(s,rows):
  try:
   v=g.volume(common(s,source(r)))
   if v>1e-5:hits.append({'id':r['id'],'volume_mm3':v})
  except Exception as ex:unknown.append({'id':r['id'],'error':str(ex)})
 q={'angle_deg':-ang,'xyz':[x,y,z],'T_S_core':T.tolist(),'hits':hits,'unknown':unknown,'overlap_mm3':sum(v['volume_mm3'] for v in hits)};trials.append(q)
 print(ang,x,y,z,'hits',len(hits),'volume',round(q['overlap_mm3'],3),[v['id'] for v in hits],flush=True)
 write(D/'results/CORE_TILT_SEARCH.json',{'scope':'35 refs including four assumed-height reservations; no manufacturer-complete clearance claim','trials':trials})
 if not unknown and all(h['id']=='WP10_INTERNAL_BATTERY_BYPASS' for h in hits):break
