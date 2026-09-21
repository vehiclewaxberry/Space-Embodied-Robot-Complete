import numpy as np, struct, os
BASE=r"f:/China Graduate Future Flight Vehicle Innovation Competition"
M=os.path.join(BASE,r"20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/05_clearance/mesh/parts_STOWED")
def tris(nm):
    with open(os.path.join(M,nm+".stl"),'rb') as f:
        n=struct.unpack('<I',f.read(84)[80:84])[0]; raw=f.read(n*50)
    a=np.frombuffer(raw,dtype=np.uint8).reshape(n,50)
    return a[:,12:48].copy()
G=tris("04_ARM_STOW_SUPPORT")
gset=set(bytes(r) for r in G)
print("04_ARM_STOW_SUPPORT triangles:",G.shape[0])
tot=0
for nm in ["Aft_Saddle","Fwd_Saddle","Mid_Saddle","Launch_Lock_Interface_Reference","Release_Clearance_Envelope","Harness_Passage","Hinge_Pin_Left"]:
    T=tris(nm); s=set(bytes(r) for r in T)
    inter=len(s & gset)
    print(f"  {nm:34s} tris={T.shape[0]:5d}  contained_in_group={inter:5d}  fully_contained={inter==len(s)}")
    if inter==len(s): tot+=T.shape[0]
print("  sum of fully-contained member triangles:", tot, " group total:", G.shape[0], " unaccounted:", G.shape[0]-tot)
