from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
from scipy.spatial.transform import Rotation

ROOT=Path(__file__).resolve().parents[2]
URDF=ROOT/'20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf'
TREE=ET.parse(URDF).getroot()
def tf(xyz=(0,0,0),rpy=(0,0,0)):
    t=np.eye(4);t[:3,:3]=Rotation.from_euler('xyz',rpy).as_matrix();t[:3,3]=xyz;return t
def fk(q_deg,base=None,finger_mm=0):
    frames={'base_link':np.eye(4) if base is None else np.array(base)};i=0
    for j in TREE.findall('joint'):
        o=j.find('origin');a=np.array([float(x) for x in j.find('axis').get('xyz').split()])
        t=tf(np.array([float(x) for x in o.get('xyz').split()])*1000,[float(x) for x in o.get('rpy').split()]); motion=np.eye(4)
        if j.get('type')=='revolute':motion[:3,:3]=Rotation.from_rotvec(a*np.deg2rad(q_deg[i])).as_matrix();i+=1
        elif j.get('type')=='prismatic':motion[:3,3]=a*finger_mm
        frames[j.find('child').get('link')]=frames[j.find('parent').get('link')]@t@motion
    return frames
def raw_vertices():
    meshes={}
    for link in TREE.findall('link'):
        p=URDF.parent/link.find('visual/geometry/mesh').get('filename')
        with p.open('rb') as f:
            f.read(80);n=int.from_bytes(f.read(4),'little');data=np.fromfile(f,dtype=np.dtype([('normal','<f4',3),('vertices','<f4',(3,3)),('attr','<u2')]),count=n)
        meshes[link.get('name')]=np.unique(data['vertices'].reshape(-1,3),axis=0).astype(float)*1000
    return meshes
def place(v,t):return v@t[:3,:3].T+t[:3,3]
def bounds(q,base,meshes):
    frames=fk(q,base);out={}
    for name,v in meshes.items():
        p=place(v,frames[name]);out[name]=[p.min(0).tolist(),p.max(0).tolist()]
    a=np.array(list(out.values()));return out,[a[:,0,:].min(0).tolist(),a[:,1,:].max(0).tolist()]
