import numpy as np, struct, os, json
try:
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
except Exception as e:
    print("SCIPY_UNAVAILABLE", e); raise SystemExit(1)
BASE = r"f:/China Graduate Future Flight Vehicle Innovation Competition"
ARM  = os.path.join(BASE, r"20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/05_clearance/mesh/parts_STOWED/B51_B601_ARTICULATED_ENGINEERING_ARM_STOWED_O13V.stl")
with open(ARM,'rb') as f:
    n=struct.unpack('<I',f.read(84)[80:84])[0]
    raw=f.read(n*50)
a=np.frombuffer(raw,dtype=np.uint8).reshape(n,50)
V32=a[:,12:48].copy().view('<f4').reshape(n*3,3)      # 3 vertices per triangle, float32
del raw, a
print("triangles",n,"vertices",V32.shape[0])
# exact-bit dedup of shared vertices
key=np.ascontiguousarray(V32).view([('a','<f4'),('b','<f4'),('c','<f4')]).ravel()
uk, inv = np.unique(key, return_inverse=True)
nv=uk.shape[0]; print("unique vertices",nv)
tri=inv.reshape(n,3)
r=np.concatenate([tri[:,0],tri[:,1],tri[:,2]])
c=np.concatenate([tri[:,1],tri[:,2],tri[:,0]])
g=coo_matrix((np.ones(r.shape[0],dtype=np.int8),(r,c)),shape=(nv,nv))
ncomp, lab = connected_components(g, directed=False)
print("connected bodies:", ncomp)
Vu=np.stack([uk['a'],uk['b'],uk['c']],axis=1).astype(np.float64)
# ---- G08 footprint attribution (Fwd_Saddle real footprint) ----
def report(nm, x0,x1,y0,y1, zlo, zhi, notchfloor, prongtop):
    m=(Vu[:,0]>=x0)&(Vu[:,0]<=x1)&(Vu[:,1]>=y0)&(Vu[:,1]<=y1)&(Vu[:,2]>=zlo)&(Vu[:,2]<=zhi)
    L=lab[m]; Z=Vu[m,2]
    print(f"\n=== {nm}: footprint x[{x0},{x1}] y[{y0},{y1}] z[{zlo},{zhi}] ===")
    print("  unique vertices in footprint:", int(m.sum()), " distinct bodies:", len(np.unique(L)))
    rows=[]
    for b in np.unique(L):
        sel=L==b
        rows.append((int(b), int(sel.sum()), float(Z[sel].min())))
    rows.sort(key=lambda t:t[2])
    for b,cnt,mz in rows[:12]:
        bm=lab==b
        bb=Vu[bm]
        print(f"   body {b:6d}  pts_in_fp={cnt:7d}  min_z_in_fp={mz:12.6f}   body_verts={int(bm.sum()):7d}  body_aabb_x=[{bb[:,0].min():.2f},{bb[:,0].max():.2f}] y=[{bb[:,1].min():.2f},{bb[:,1].max():.2f}] z=[{bb[:,2].min():.2f},{bb[:,2].max():.2f}]")
    return rows
r08=report("G08 / Fwd_Saddle", 160.0,180.0, 11.55,71.550003, 195.0, 225.0, 206.42, 209.42)
r07=report("G07 / Aft_Saddle", -20.0,0.0, -26.809999,33.189999, 250.0, 275.0, 258.08, 261.08)
rmid=report("MID / Mid_Saddle", 80.0,100.0, 17.799999,77.800003, 205.0, 230.0, 211.92, 214.92)
# widened G07 window min-point location
m=(Vu[:,0]>=-37.0)&(Vu[:,0]<=17.0)&(Vu[:,1]>=-23.81)&(Vu[:,1]<=30.19)
Z=Vu[m,2]; P=Vu[m]
i=int(np.argmin(Z))
print("\nG07 widened 54x54 window minimum-z point:", [round(float(t),6) for t in P[i]],
      " inside Aft_Saddle x-footprint [-20,0]?", bool(-20.0<=P[i][0]<=0.0))
# how many of the sub-pad-face points lie outside the saddle x footprint
sub=P[Z<261.5016]
print("  points below declared pad face 261.5016:", sub.shape[0],
      " of which x outside [-20,0]:", int(((sub[:,0]<-20.0)|(sub[:,0]>0.0)).sum()))
print("  their aabb:", [round(float(t),6) for t in [sub[:,0].min(),sub[:,1].min(),sub[:,2].min(),sub[:,0].max(),sub[:,1].max(),sub[:,2].max()]] if sub.size else None)
# arm min z restricted to the true Aft_Saddle x-footprint but 54-wide y band
m2=(Vu[:,0]>=-20.0)&(Vu[:,0]<=0.0)&(Vu[:,1]>=-23.81)&(Vu[:,1]<=30.19)
print("  arm min z over x[-20,0] y[-23.81,30.19]:", float(Vu[m2,2].min()))
np.save("labels.npy", lab); np.save("uverts.npy", Vu)
