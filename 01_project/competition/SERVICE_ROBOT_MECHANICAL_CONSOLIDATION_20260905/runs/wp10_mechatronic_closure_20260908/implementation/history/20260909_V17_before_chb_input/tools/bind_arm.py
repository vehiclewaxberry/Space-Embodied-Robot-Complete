"""Bind existing ten DM rigid parts to public, version-matched nominal joints.
No motor commands, inertia fabrication, or mutation of the sealed parent.
"""
from pathlib import Path
import json,csv,hashlib,urllib.request,xml.etree.ElementTree as ET,copy
import numpy as np
from scipy.spatial.transform import Rotation
A=Path(__file__).resolve().parents[1];D=A.parent;ROOT=D.parents[4];M=A/'mechanical'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
urls={
 'official_matched_dm.urdf':'https://raw.githubusercontent.com/Seeed-Projects/reBotArmController_ROS2/e134941b71236523e831f15b470bc81186b0649f/src/rebotarm_bringup/description/urdf/reBot_B601_DM_with_gripper.urdf',
 'official_dm_motor.yaml':'https://raw.githubusercontent.com/Seeed-Projects/reBotArm_control_py/1bcd81b22c182ec257bf04f5746e1e3d556a5f1c/config/rebotarm_dm.yaml'}
sources=[]
for name,url in urls.items():
 p=A/'sources'/name
 if not p.exists():p.write_bytes(urllib.request.urlopen(url,timeout=25).read())
 sources.append(dict(path=str(p),url=url,sha256=sha(p)))
local=ROOT/'20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf'
urdf=ET.parse(local).getroot(); official=ET.parse(A/'sources/official_matched_dm.urdf').getroot()
assert sha(A/'sources/official_matched_dm.urdf')=='f808f6f0d33274b226c7e59db6d27d1498feb7e0955a94fe30f3f215a7425fa6'
packet_path=D/'mechanical_intake/PARAMETER_PACKET.json';packet=json.loads(packet_path.read_text(encoding='utf-8'))
instances={x['id']:x for x in packet['instances']}; checks=[];rows=[];joints=[]
def ck(name,ok,**details):checks.append(dict(check=name,pass_=bool(ok),**details))
def vec(node,key,default):return np.array([float(x) for x in node.get(key,default).split()])
states=packet['state_names'];errmax=0
for j in urdf.findall('joint'):
 o=official.find("joint[@name='%s']"%j.get('name'));ck('official_joint_xml_'+j.get('name'),o is not None and ET.tostring(j).strip()==ET.tostring(o).strip())
 origin=j.find('origin');xyz=vec(origin,'xyz','0 0 0');rpy=vec(origin,'rpy','0 0 0');O=np.eye(4);O[:3,:3]=Rotation.from_euler('xyz',rpy).as_matrix();O[:3,3]=xyz
 typ=j.get('type');axis=vec(j.find('axis'),'xyz','1 0 0') if typ!='fixed' else np.zeros(3)
 par=j.find('parent').get('link');child=j.find('child').get('link');pid='B601_'+par;cid='B601_'+child
 lim=j.find('limit'); limits={k:float(v) for k,v in lim.attrib.items()} if lim is not None else None
 entry=dict(name=j.get('name'),type=typ,parent_link=par,child_link=child,parent_instance=pid,child_instance=cid,origin_xyz_m=xyz.tolist(),origin_rpy_rad=rpy.tolist(),axis_joint_frame=axis.tolist(),source_model_limits=limits,as_built_limits=None,state_coordinates={})
 for state in states:
  Tp=np.array(instances[pid]['geometry_by_state'][state]['T_local_to_S_SI_m']);Tc=np.array(instances[cid]['geometry_by_state'][state]['T_local_to_S_SI_m']);Q=np.linalg.inv(O)@np.linalg.inv(Tp)@Tc;J=np.eye(4)
  if typ=='revolute':q=float(Rotation.from_matrix(Q[:3,:3]).as_rotvec()@axis);J[:3,:3]=Rotation.from_rotvec(axis*q).as_matrix()
  elif typ=='prismatic':q=float(Q[:3,3]@axis);J[:3,3]=axis*q
  else:q=0.
  predicted=Tp@O@J;err=float(np.max(np.abs(predicted-Tc)));errmax=max(errmax,err)
  ck(j.get('name')+'_'+state+'_FK_match',err<1e-10,error_max=err)
  if limits is not None:ck(j.get('name')+'_'+state+'_inside_source_position',limits['lower']-1e-10<=q<=limits['upper']+1e-10)
  entry['state_coordinates'][state]=q
  rows.append(dict(joint=j.get('name'),state=state,parent_instance=pid,child_instance=cid,type=typ,q_SI=q,q_unit='rad' if typ=='revolute' else 'm' if typ=='prismatic' else 'fixed',max_FK_matrix_error=err,as_built_calibrated=False))
 joints.append(entry)
for id,x in instances.items():
 if not id.startswith('B601_'):continue
 for s,g in x['geometry_by_state'].items():ck(id+'_'+s+'_STEP_source_hash',sha(Path(g['source_step']['path']))==g['source_step']['sha256'])
 x['dynamic_link_id']=id[5:];x['local_frame_definition']='Version-matched DM URDF link frame; nominal kinematics verified against all three existing static CAD poses; not COM frame.'
oldstep=ROOT/'80_third_party/vendor/reBot-DevArm/hardware/reBot_B601_DM/reBot_B601_DM_v1.1_20260425.step';raw=oldstep.read_bytes();norm=raw.replace(b'\r\n',b'\n');blob=hashlib.sha1(b'blob '+str(len(norm)).encode()+b'\0'+norm).hexdigest()
ck('old_hardware_git_blob_matches_historical_revision',blob=='363cb3b1fc97586766aa48bb6102eecaa4a402b5')
ck('same_873_instances',len(instances)==873)
ck('new_official_joint6_offset_must_not_silently_fit',abs(0.028008-next(j['origin_xyz_m'][0] for j in joints if j['name']=='joint6'))>0.004)
ck('one_gripper_motor_nominal_sync',all(abs(joints[-1]['state_coordinates'][s]-joints[-2]['state_coordinates'][s])<1e-10 for s in states))
assert all(c['pass_'] for c in checks),[c for c in checks if not c['pass_']]
binding=dict(schema='WP10_DM_NOMINAL_KINEMATIC_BINDING_V1',status='NOMINAL_STATIC_KINEMATICS_SOURCE_BOUND',parent_packet={'path':str(packet_path),'sha256':sha(packet_path)},sources=sources,local_urdf={'path':str(local),'sha256':sha(local)},historical_step={'path':str(oldstep),'raw_sha256':sha(oldstep),'normalized_git_blob_sha1':blob,'commit':'9b8fe0bfe3a13c2df1e559023f246f1fb7ad4cad'},link_instance_map={k[5:]:k for k in instances if k.startswith('B601_')},base_installation_T=instances['B601_base_link']['geometry_by_state']['service']['T_local_to_S_SI_m'],joints=joints,gripper_coupling={'equation':'q_right=q_left','identity':'NOMINAL_SYNCHRONOUS_RACK_DESIGN_CONSTRAINT','motor_count':1,'motor_angle_to_rack_calibration':None},actuators=[{'joint':'joint'+str(n) if n<7 else 'gripper','model':'DM4340P' if n<=3 else 'DM4310','command_id':n,'feedback_id':n+16,'identity':'PINNED_PUBLIC_SDK_REFERENCE_NOT_DEVICE_READBACK'} for n in range(1,8)],as_built_zero_verified=False,as_built_link_inertia_complete=False,continuous_collision_checked=False,old_urdf_velocity_not_hardware_limit=True,max_static_FK_error=errmax)
dump(M/'B601_DM_KINEMATIC_BINDING.json',binding)
with (M/'B601_DM_JOINT_INPUTS.csv').open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
packet['joint_tree_before_wp10_binding']=packet['joint_tree'];packet['joint_tree']={'status':'B601_NOMINAL_SUBTREE_BOUND__REST_UNCHANGED','binding_file':'B601_DM_KINEMATIC_BINDING.json','binding_sha256':sha(M/'B601_DM_KINEMATIC_BINDING.json'),'joints':joints,'whole_system_dynamic_tree_complete':False}
packet['wp10_implementation_overlay']={'parent_sha256':sha(packet_path),'only_changed':'B601 dynamic_link_id/local_frame_definition/joint_tree; all mass, inertia and geometry bytes inherited','power_candidate_not_inserted_in_873':True}
dump(M/'PARAMETER_PACKET.json',packet);dump(A/'results/B601_KINEMATIC_VERIFICATION.json',{'pass':True,'checks':checks,'count':len(checks),'scope':'Static source and frame binding only; no dynamics, hardware, collision or mass closure'})
print(json.dumps({'status':binding['status'],'checks':len(checks),'max_static_FK_error':errmax}))
