import numpy as np, struct, os, json, hashlib
BASE = r"f:/China Graduate Future Flight Vehicle Innovation Competition"
MESH = os.path.join(BASE, r"20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/05_clearance/mesh/parts_STOWED")
ARM  = os.path.join(MESH, "B51_B601_ARTICULATED_ENGINEERING_ARM_STOWED_O13V.stl")

def stl_vertices(path, chunk_tris=200000):
    """Yield float64 vertex blocks from a binary STL without loading it all at once."""
    with open(path,'rb') as f:
        head=f.read(84); n=struct.unpack('<I',head[80:84])[0]
        got=0
        while got<n:
            k=min(chunk_tris, n-got)
            raw=f.read(k*50)
            a=np.frombuffer(raw,dtype=np.uint8).reshape(k,50)
            fl=a[:,:48].copy().view('<f4').reshape(k,4,3)
            yield fl[:,1:4,:].reshape(-1,3).astype(np.float64)
            got+=k
    return

with open(ARM,'rb') as f:
    n_tris = struct.unpack('<I', f.read(84)[80:84])[0]
print("arm triangles:", n_tris, "vertices:", n_tris*3)

# ---- saddle solids as explicit axis-aligned box unions (measured, not assumed) ----
SADDLES = {
 "Aft_Saddle_G07": dict(
    boxes=[(-20.0, 0.0, -26.81,  33.19, 113.15, 258.08),   # tower body
           (-20.0, 0.0, -26.81, -22.81, 258.08, 261.08),   # prong -Y
           (-20.0, 0.0,  29.19,  33.19, 258.08, 261.08)],  # prong +Y
    notch=(-20.0, 0.0, -22.81, 29.19, 258.08, 261.08)),
 "Fwd_Saddle_G08": dict(
    boxes=[(160.0,180.0, 11.55, 71.55, 113.15, 206.42),
           (160.0,180.0, 11.55, 15.55, 206.42, 209.42),
           (160.0,180.0, 67.55, 71.55, 206.42, 209.42)],
    notch=(160.0,180.0, 15.55, 67.55, 206.42, 209.42)),
 "Mid_Saddle_MID": dict(
    boxes=[(80.0,100.0, 17.80, 77.80, 113.15, 211.92),
           (80.0,100.0, 17.80, 21.80, 211.92, 214.92),
           (80.0,100.0, 73.80, 77.80, 211.92, 214.92)],
    notch=(80.0,100.0, 21.80, 73.80, 211.92, 214.92)),
}

# ---- measurement windows: WP1's three + prong-only + pad-only ----
W = {
 # name: (x0,x1,y0,y1)
 "G07_V1_FOOT":        (-20.0, 0.0, -26.809999, 33.189999),
 "G07_V2_HEAD_54x54":  (-37.0, 17.0, -23.81, 30.19),
 "G07_V2_BAND":        (-6.762, -1.888, 24.557, 30.36),
 "G07_PRONG_MINUS_Y":  (-20.0, 0.0, -26.81, -22.81),
 "G07_PRONG_PLUS_Y":   (-20.0, 0.0, 29.19, 33.19),
 "G07_NOTCH_ONLY":     (-20.0, 0.0, -22.81, 29.19),
 "G07_PAD_50x50":      (-25.0, 25.0, -21.81, 28.19),
 "G08_V1_FOOT":        (160.0, 180.0, 11.55, 71.550003),
 "G08_V2_HEAD_34x34":  (153.0, 187.0, 24.550002, 58.550002),
 "G08_V2_BAND":        (163.167, 172.33, 46.643, 60.009),
 "G08_PRONG_MINUS_Y":  (160.0, 180.0, 11.55, 15.55),
 "G08_PRONG_PLUS_Y":   (160.0, 180.0, 67.55, 71.55),
 "G08_PRONGS_UNION_MINUSY": (160.0, 180.0, 11.55, 15.55),
 "G08_NOTCH_ONLY":     (160.0, 180.0, 15.55, 67.55),
 "G08_PAD_30x30":      (155.0, 185.0, 26.55, 56.55),
 "MID_V1_FOOT":        (80.0, 100.0, 17.799999, 77.800003),
 "MID_V2_HEAD":        (73.0, 107.0, 30.595001, 65.005001),
 "MID_V2_BAND":        (87.995, 99.893, 34.574, 64.985),
 "MID_PRONG_MINUS_Y":  (80.0, 100.0, 17.80, 21.80),
 "MID_PRONG_PLUS_Y":   (80.0, 100.0, 73.80, 77.80),
 "MID_NOTCH_ONLY":     (80.0, 100.0, 21.80, 73.80),
 "MID_PAD_30x30":      (75.0, 105.0, 32.80, 62.80),
}
PADFACE = {"G07":261.5016, "G08":208.4929, "MID":212.9189}

wmin = {k: [np.inf, 0] for k in W}          # min z, count
pen  = {k: [0, np.inf] for k in SADDLES}    # points inside solid, min z of those
below= {k: 0 for k in PADFACE}              # arm vertices strictly below declared pad face inside V1 foot
armbb= [np.inf]*3 + [-np.inf]*3
nv=0
for blk in stl_vertices(ARM):
    x,y,z = blk[:,0], blk[:,1], blk[:,2]
    nv += blk.shape[0]
    armbb[0]=min(armbb[0],x.min()); armbb[1]=min(armbb[1],y.min()); armbb[2]=min(armbb[2],z.min())
    armbb[3]=max(armbb[3],x.max()); armbb[4]=max(armbb[4],y.max()); armbb[5]=max(armbb[5],z.max())
    for k,(x0,x1,y0,y1) in W.items():
        m = (x>=x0)&(x<=x1)&(y>=y0)&(y<=y1)
        c = int(m.sum())
        if c:
            zz = z[m].min()
            if zz < wmin[k][0]: wmin[k][0]=float(zz)
            wmin[k][1]+=c
    for sname,sd in SADDLES.items():
        acc = np.zeros(blk.shape[0], dtype=bool)
        for (x0,x1,y0,y1,z0,z1) in sd["boxes"]:
            acc |= (x>x0)&(x<x1)&(y>y0)&(y<y1)&(z>z0)&(z<z1)
        c=int(acc.sum())
        if c:
            pen[sname][0]+=c
            zz=float(z[acc].min())
            if zz<pen[sname][1]: pen[sname][1]=zz
res = dict(arm_vertices=nv, arm_aabb=[float(v) for v in armbb],
           window_min_z={k:[wmin[k][0], wmin[k][1]] for k in W},
           penetration_into_native_saddle_solid={k:[pen[k][0], (None if pen[k][1]==np.inf else pen[k][1])] for k in SADDLES})
print(json.dumps(res, indent=1))
open("arm_probe_result.json","w").write(json.dumps(res, indent=1))
