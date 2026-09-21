import numpy as np, struct, os
BASE=r"f:/China Graduate Future Flight Vehicle Innovation Competition"
bl=os.path.join(BASE,r"20_engineering/cad/spacecraft_layout/arm_b601_v1/meshes_b601_gripper/base_link.STL")
with open(bl,'rb') as f:
    n=struct.unpack('<I',f.read(84)[80:84])[0]; raw=f.read(n*50)
a=np.frombuffer(raw,dtype=np.uint8).reshape(n,50)
T=a[:,12:48].copy().view('<f4').reshape(n,3,3).astype(np.float64)*1000.0
zmin=T[:,:,2].min(axis=1); zmax=T[:,:,2].max(axis=1)
print("base_link.STL triangles:",n,"  z_local range [%.4f, %.4f] mm"%(T[:,:,2].min(),T[:,:,2].max()))
for gx in (208.0,210.405,212.0,215.0,218.0,220.0,230.0,250.0,290.0,290.65,291.0):
    zl=gx-208.0
    m=(zmin<=zl)&(zmax>=zl)
    k=int(m.sum())
    if k:
        P=T[m].reshape(-1,3); r=np.hypot(P[:,0],P[:,1])
        print(f"  global x={gx:8.3f} (z_local={zl:7.3f}): triangles crossing the plane = {k:6d}"
              f"   vertex radii of crossing triangles r=[{r.min():.3f},{r.max():.3f}] mm  -> SOLID MATERIAL PRESENT")
    else:
        print(f"  global x={gx:8.3f} (z_local={zl:7.3f}): triangles crossing = 0 -> outside the base_link body")
