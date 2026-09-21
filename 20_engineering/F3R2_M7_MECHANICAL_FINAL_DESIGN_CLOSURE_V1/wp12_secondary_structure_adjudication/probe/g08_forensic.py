import numpy as np, struct, os, json
BASE = r"f:/China Graduate Future Flight Vehicle Innovation Competition"
ARM  = os.path.join(BASE, r"20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/05_clearance/mesh/parts_STOWED/B51_B601_ARTICULATED_ENGINEERING_ARM_STOWED_O13V.stl")
def blocks(path, k=200000):
    with open(path,'rb') as f:
        n=struct.unpack('<I',f.read(84)[80:84])[0]; got=0
        while got<n:
            m=min(k,n-got); raw=f.read(m*50)
            a=np.frombuffer(raw,dtype=np.uint8).reshape(m,50)
            yield a[:,:48].copy().view('<f4').reshape(m,4,3)[:,1:4,:].reshape(-1,3).astype(np.float64)
            got+=m
keep=[]
for b in blocks(ARM):
    x,y,z=b[:,0],b[:,1],b[:,2]
    m=(x>=150)&(x<=190)&(y>=8)&(y<=75)&(z>=198)&(z<=216)
    if m.any(): keep.append(b[m])
V=np.vstack(keep); print("G08 region vertices:", V.shape[0])
z=V[:,2]
# plane clustering: count vertices per 0.001 mm z bucket, report top planes
zr=np.round(z,3); u,c=np.unique(zr,return_counts=True)
order=np.argsort(-c)[:25]
print("\ntop z-planes in the G08 region (z_mm, vertex_count):")
for i in order: print(f"  {u[i]:10.3f}  {c[i]}")
print("\nis 208.4929 a populated plane?")
for tol in (0.0005,0.005,0.05):
    m=np.abs(z-208.4929)<=tol
    print(f"  |z-208.4929|<={tol}: {int(m.sum())} vertices")
# material strictly below the notch floor 206.42 inside the Fwd_Saddle footprint
m=(V[:,0]>160)&(V[:,0]<180)&(V[:,1]>11.55)&(V[:,1]<71.55)&(z<206.42)
sub=V[m]; print("\nvertices strictly inside Fwd_Saddle tower body:", sub.shape[0])
if sub.size:
    print("  aabb:", [round(float(t),6) for t in [sub[:,0].min(),sub[:,1].min(),sub[:,2].min(),sub[:,0].max(),sub[:,1].max(),sub[:,2].max()]])
    print("  max penetration depth below notch floor 206.42 mm:", round(206.42-float(sub[:,2].min()),6))
# what is the lowest arm material over the declared 30x30 pad and over prongs
for nm,(x0,x1,y0,y1) in {"pad30_centred":(155,185,26.55,56.55),"prong_-Y":(160,180,11.55,15.55),"prong_+Y":(160,180,67.55,71.55)}.items():
    mm=(V[:,0]>=x0)&(V[:,0]<=x1)&(V[:,1]>=y0)&(V[:,1]<=y1)
    print(f"  {nm}: n={int(mm.sum())} min_z={float(V[mm,2].min()) if mm.any() else None}")
# scan: for which square sub-window does min z == 208.4929 ?
print("\nscan for a window whose min z ~= 208.4929 (tol 0.002):")
hits=0
for x0 in np.arange(150,188,2.0):
    for y0 in np.arange(8,74,2.0):
        for s in (10.,20.,30.,34.,40.):
            mm=(V[:,0]>=x0)&(V[:,0]<=x0+s)&(V[:,1]>=y0)&(V[:,1]<=y0+s)
            if mm.sum()>50:
                mz=float(V[mm,2].min())
                if abs(mz-208.4929)<=0.002:
                    hits+=1
                    if hits<=8: print(f"   x[{x0},{x0+s}] y[{y0},{y0+s}] min_z={mz:.6f} n={int(mm.sum())}")
print("   total windows matching:", hits)
