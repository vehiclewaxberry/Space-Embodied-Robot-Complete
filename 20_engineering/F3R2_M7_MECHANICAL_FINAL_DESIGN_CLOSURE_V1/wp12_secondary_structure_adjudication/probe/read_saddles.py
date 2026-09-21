import numpy as np, struct, io, os, json
BASE = r"f:/China Graduate Future Flight Vehicle Innovation Competition"
MESH = os.path.join(BASE, r"20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/05_clearance/mesh/parts_STOWED")

def read_stl(path):
    with open(path,'rb') as f:
        head=f.read(84)
        n=struct.unpack('<I',head[80:84])[0]
        raw=f.read(n*50)
    assert len(raw)==n*50, (len(raw), n*50)
    a=np.frombuffer(raw,dtype=np.uint8).reshape(n,50)
    fl=a[:,:48].copy().view('<f4').reshape(n,4,3)
    tris=fl[:,1:4,:].astype(np.float64)
    return tris

out={}
for name in ["Fwd_Saddle","Mid_Saddle","Aft_Saddle","04_ARM_STOW_SUPPORT","Release_Clearance_Envelope","Launch_Lock_Interface_Reference","Harness_Passage","WING_L_STOWED","WING_R_STOWED","Hinge_Pin_Left","Hinge_Pin_Right","Hard_Stop_Left","Hard_Stop_Right"]:
    p=os.path.join(MESH,name+".stl")
    t=read_stl(p)
    v=t.reshape(-1,3)
    out[name]=dict(tris=int(t.shape[0]),
                   aabb=[float(v[:,0].min()),float(v[:,1].min()),float(v[:,2].min()),
                         float(v[:,0].max()),float(v[:,1].max()),float(v[:,2].max())],
                   uniq_x=sorted(set(np.round(v[:,0],4).tolist())),
                   uniq_y=sorted(set(np.round(v[:,1],4).tolist())),
                   uniq_z=sorted(set(np.round(v[:,2],4).tolist())))
for k,vv in out.items():
    print(k, 'tris=',vv['tris'])
    print('   aabb', [round(x,4) for x in vv['aabb']])
    print('   x:', vv['uniq_x'])
    print('   y:', vv['uniq_y'])
    print('   z:', vv['uniq_z'])
