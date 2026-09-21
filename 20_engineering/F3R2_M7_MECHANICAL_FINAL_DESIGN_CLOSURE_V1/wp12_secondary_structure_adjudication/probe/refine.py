import numpy as np, struct, os, json
BASE = r"f:/China Graduate Future Flight Vehicle Innovation Competition"
ARM  = os.path.join(BASE, r"20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/05_clearance/mesh/parts_STOWED/B51_B601_ARTICULATED_ENGINEERING_ARM_STOWED_O13V.stl")
lab=np.load("labels.npy"); Vu=np.load("uverts.npy")
# 1) who owns z == 208.4929 near the G08 footprint?
m=(np.abs(Vu[:,2]-208.4929)<0.0006)&(Vu[:,0]>150)&(Vu[:,0]<190)&(Vu[:,1]>8)&(Vu[:,1]<75)
print("vertices at z=208.4929 in G08 region:", int(m.sum()))
for b in np.unique(lab[m]):
    bm=lab==b; bb=Vu[bm]
    fp=bm&(Vu[:,0]>=160)&(Vu[:,0]<=180)&(Vu[:,1]>=11.55)&(Vu[:,1]<=71.550003)
    print(f"  body {b}: verts={int(bm.sum())} aabb x=[{bb[:,0].min():.3f},{bb[:,0].max():.3f}] y=[{bb[:,1].min():.3f},{bb[:,1].max():.3f}] z=[{bb[:,2].min():.4f},{bb[:,2].max():.3f}]  min_z_over_G08_footprint={float(Vu[fp,2].min()) if fp.any() else None}")
    pts=Vu[m&bm]; print("   pts:", [[round(float(t),4) for t in p] for p in pts[:8]])
# 2) does ANY body have min z over the G08 footprint == 208.4929 ?
best=[]
fpm=(Vu[:,0]>=160)&(Vu[:,0]<=180)&(Vu[:,1]>=11.55)&(Vu[:,1]<=71.550003)
for b in np.unique(lab[fpm]):
    sel=fpm&(lab==b)
    best.append((float(Vu[sel,2].min()), int(b), int(sel.sum())))
best.sort()
print("\nper-body min z over the exact Fwd_Saddle footprint (all z):")
for mz,b,c in best[:14]: print(f"   body {b:6d} min_z={mz:12.6f} pts={c}")
print("   any body min_z within 0.002 of 208.4929 ?", any(abs(mz-208.4929)<0.002 for mz,_,_ in best))
# 3) G07 body 20 global min-z point
bm=lab==20; bb=Vu[bm]; i=int(np.argmin(bb[:,2]))
print("\nG07 body 20 global min-z point:", [round(float(t),6) for t in bb[i]])
# 4) conservative triangle-AABB overlap test vs each native saddle solid
SAD={"Aft_Saddle_G07":[(-20.,0.,-26.81,33.19,113.15,258.08),(-20.,0.,-26.81,-22.81,258.08,261.08),(-20.,0.,29.19,33.19,258.08,261.08)],
     "Fwd_Saddle_G08":[(160.,180.,11.55,71.55,113.15,206.42),(160.,180.,11.55,15.55,206.42,209.42),(160.,180.,67.55,71.55,206.42,209.42)],
     "Mid_Saddle_MID":[(80.,100.,17.80,77.80,113.15,211.92),(80.,100.,17.80,21.80,211.92,214.92),(80.,100.,73.80,77.80,211.92,214.92)]}
with open(ARM,'rb') as f:
    n=struct.unpack('<I',f.read(84)[80:84])[0]
    res={k:{'tri_aabb_overlap':0,'tri_with_vertex_inside':0,'max_depth_mm':0.0} for k in SAD}
    got=0
    while got<n:
        k=min(200000,n-got); a=np.frombuffer(f.read(k*50),dtype=np.uint8).reshape(k,50)
        T=a[:,12:48].copy().view('<f4').reshape(k,3,3).astype(np.float64)
        lo=T.min(axis=1); hi=T.max(axis=1)
        for nm,boxes in SAD.items():
            ov=np.zeros(k,dtype=bool); vin=np.zeros(k,dtype=bool)
            for (x0,x1,y0,y1,z0,z1) in boxes:
                ov |= (hi[:,0]>=x0)&(lo[:,0]<=x1)&(hi[:,1]>=y0)&(lo[:,1]<=y1)&(hi[:,2]>=z0)&(lo[:,2]<=z1)
                pv=(T[:,:,0]>x0)&(T[:,:,0]<x1)&(T[:,:,1]>y0)&(T[:,:,1]<y1)&(T[:,:,2]>z0)&(T[:,:,2]<z1)
                vin |= pv.any(axis=1)
                if pv.any():
                    d=z1-T[:,:,2][pv]
                    res[nm]['max_depth_mm']=max(res[nm]['max_depth_mm'], float(d.max()) if d.size else 0.0)
            res[nm]['tri_aabb_overlap']+=int(ov.sum()); res[nm]['tri_with_vertex_inside']+=int(vin.sum())
        got+=k
print("\nconservative triangle tests vs native saddle solids:")
print(json.dumps(res,indent=1))
