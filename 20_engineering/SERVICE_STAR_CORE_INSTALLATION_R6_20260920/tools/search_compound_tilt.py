from geometry import *
import math,itertools
core=source(read(D/'inputs/MAIN_GEOMETRY_COVERAGE.json')['board']);rows=state_rows()['service'];trials=[]
for yaw,tilt,cx,cy,cz in [(y,t,x,v,z) for y in [10,8,12,15,5,-10] for t in [20,25,15] for x,v in [(-114,42),(-113,43),(-115,42),(-115,40)] for z in [22,25,19]]:
 a,b=map(math.radians,[yaw,tilt]);rz=np.array([[math.cos(a),-math.sin(a),0],[math.sin(a),math.cos(a),0],[0,0,1]])
 rx=np.array([[1,0,0],[0,math.cos(b),math.sin(b)],[0,-math.sin(b),math.cos(b)]]);T=np.eye(4);T[:3,:3]=rz@rx;T[:3,3]=[cx,cy,cz]-T[:3,:3]@np.array([50,-40,0]);s=moved(core,T)
 # Cheap exact-board screen before all populated bodies.
 board=moved(box(0,-80,0,100,0,1.595),T);hits=[];unknown=[]
 for r in candidates(board,rows):
  try:
   v=g.volume(common(board,source(r)))
   if v>1e-5:hits.append({'id':r['id'],'volume_mm3':v,'screen':'board'})
  except Exception as e:unknown.append({'id':r['id'],'error':str(e)})
 if not hits and not unknown:
  for r in candidates(s,rows):
   try:
    v=g.volume(common(s,source(r)))
    if v>1e-5:hits.append({'id':r['id'],'volume_mm3':v,'screen':'population'})
   except Exception as e:unknown.append({'id':r['id'],'error':str(e)})
 q={'yaw_deg':yaw,'tilt_deg':-tilt,'center':[cx,cy,cz],'T_S_core':T.tolist(),'hits':hits,'unknown':unknown};trials.append(q)
 print(yaw,tilt,[cx,cy,cz],'hits',[h['id'] for h in hits],'unknown',len(unknown),flush=True)
 write(D/'results/CORE_COMPOUND_TILT_SEARCH.json',{'scope':'Candidate source-bound mixed 35-ref geometry','trials':trials})
 if not hits and not unknown:
  write(D/'inputs/MAIN_INSTALL_POSE.json',q);print('FOUND_CLEAR',flush=True);break
 if len(trials)>=90:break
