from pathlib import Path
import requests,json,hashlib,concurrent.futures
session=requests.Session();session.headers['User-Agent']='SEI-bounded-source-audit'
N=Path(r'F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/reuse_closure');D=N/'sources/atmos_px4'
choices={'atmos':['LICENSE','README.md','_pages/PX4.md','_posts/2024-11-23-avionics.md','assets/px4_autopilot/dds_topics.yaml'], 'px4':['LICENSE','ROMFS/px4fmu_common/init.d/airframes/70000_atmos','ROMFS/px4fmu_common/init.d-posix/airframes/70000_gz_atmos','src/modules/control_allocator/VehicleActuatorEffectiveness/ActuatorEffectivenessSpacecraft.cpp','src/modules/control_allocator/VehicleActuatorEffectiveness/ActuatorEffectivenessSpacecraft.hpp','src/modules/control_allocator/ControlAllocator.cpp','src/lib/control_allocation/actuator_effectiveness/ActuatorEffectiveness.hpp','src/modules/control_allocator/VehicleActuatorEffectiveness/ActuatorEffectivenessRotors.cpp','src/modules/control_allocator/VehicleActuatorEffectiveness/ActuatorEffectivenessRotors.hpp','src/modules/control_allocator/module.yaml','ROMFS/px4fmu_common/init.d/rc.sc_defaults','src/lib/control_allocation/control_allocation/ControlAllocationSequentialDesaturation.cpp','src/lib/control_allocation/control_allocation/ControlAllocationPseudoInverse.cpp','msg/VehicleThrustSetpoint.msg','msg/VehicleTorqueSetpoint.msg','msg/versioned/ActuatorMotors.msg','src/modules/uxrce_dds_client/dds_topics.yaml','boards/px4/fmu-v6x/spacecraft.px4board'], 'px4_msgs':['LICENSE','msg/VehicleThrustSetpoint.msg','msg/VehicleTorqueSetpoint.msg','msg/ActuatorMotors.msg']}
jobs=[]
for key,paths in choices.items():
 meta=json.loads((D/(key+'_tree.json')).read_text());tree={x['path']:x for x in meta['tree']['tree']}
 for path in paths:
  if path not in tree:print('MISSING',key,path);continue
  jobs.append((key,path,meta['repo'],meta['commit'],tree[path]['sha']))
def get(j):
 key,p,repo,c,blob=j;url='https://raw.githubusercontent.com/'+repo+'/'+c+'/'+p;out=D/key/p;out.parent.mkdir(parents=True,exist_ok=True)
 data=out.read_bytes() if out.exists() else None
 if data is None:
  import base64
  r=session.get('https://api.github.com/repos/'+repo+'/git/blobs/'+blob,timeout=45);r.raise_for_status();data=base64.b64decode(r.json()['content']);out.write_bytes(data)
 actual_blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\x00'+data).hexdigest()
 assert actual_blob==blob
 return {'repo':repo,'commit':c,'upstream_path':p,'git_blob':blob,'local_path':str(out),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'url':url,'modified':False,'git_blob_verified':True}
with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:rows=list(pool.map(get,jobs))
(D/'SOURCE_LOCK.json').write_text(json.dumps({'schema':'ATMOS_PX4_MINIMAL_SOURCE_LOCK_V1','files':rows,'execution':'SOURCE_ONLY_NO_FIRMWARE_BUILD_OR_HARDWARE'},indent=2));print('files',len(rows),'bytes',sum(x['bytes'] for x in rows))

