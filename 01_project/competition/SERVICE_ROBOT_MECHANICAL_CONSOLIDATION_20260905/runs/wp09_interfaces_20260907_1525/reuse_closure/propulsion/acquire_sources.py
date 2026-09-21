from pathlib import Path
import requests,json,hashlib
N=Path(r'F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/reuse_closure');D=N/'sources/atmos_px4'
s=requests.Session();s.headers['User-Agent']='SEI-bounded-source-audit'
for repo,key in [('DISCOWER/w3_atmos','atmos'),('PX4/PX4-Autopilot','px4'),('PX4/px4_msgs','px4_msgs')]:
 if (D/(key+'_tree.json')).exists():
  print('REUSE_LOCKED_TREE',key,json.loads((D/(key+'_tree.json')).read_text())['commit']);continue
 r=s.get('https://api.github.com/repos/'+repo+'/commits/HEAD',timeout=30);r.raise_for_status();c=r.json()['sha'];print(key,c)
 j=s.get('https://api.github.com/repos/'+repo+'/git/trees/'+c+'?recursive=1',timeout=45);j.raise_for_status();data=j.json();(D/(key+'_tree.json')).write_text(json.dumps({'repo':repo,'commit':c,'tree':data},indent=2));
 for x in data['tree']:
  p=x['path']
  if (key=='px4' and any(v in p.lower() for v in ('70000','spacecraft','vehicletorquesetpoint','vehiclethrustsetpoint','actuatormotors'))) or (key=='atmos' and any(v in p.lower() for v in ('license','px4','dds_topics','avionics'))):print(key,p)
