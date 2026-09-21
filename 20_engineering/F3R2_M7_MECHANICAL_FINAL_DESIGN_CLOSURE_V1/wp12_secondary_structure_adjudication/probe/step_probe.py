import re, io, os, json, numpy as np
BASE=r"f:/China Graduate Future Flight Vehicle Innovation Competition"
S=os.path.join(BASE,r"20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp1_structure_cad/DESIGN_FREEZE_ASSEMBLY_V1.step")
t=io.open(S,encoding='utf-8',errors='replace').read()
print("bytes(text chars):", len(t))
for tok in ("MANIFOLD_SOLID_BREP","ADVANCED_FACE","CLOSED_SHELL","SHAPE_REPRESENTATION_RELATIONSHIP","NEXT_ASSEMBLY_USAGE_OCCURRENCE","CARTESIAN_POINT","CYLINDRICAL_SURFACE","PRODUCT("):
    print(f"  {tok:36s} {t.count(tok)}")
pts=re.findall(r"CARTESIAN_POINT\('[^']*',\(([^)]*)\)\)", t)
XYZ=[]
for p in pts:
    v=[float(x) for x in p.split(',')]
    if len(v)==3: XYZ.append(v)
A=np.array(XYZ)
print("3D cartesian points:", A.shape[0])
print("point-cloud bbox:", [round(float(x),9) for x in [A[:,0].min(),A[:,1].min(),A[:,2].min(),A[:,0].max(),A[:,1].max(),A[:,2].max()]])
print("build-report shape bbox: [-230.25, -313.15, -243.075977174, 441.700116164, 313.15, 247.908130023]")
ZMAX=float(A[:,2].max())
print("global z-max of the design-freeze STEP point cloud:", ZMAX)
for nm,z in {"G07_pad_face":261.5016,"G07_pad_carrier_top":258.5016,"MID_pad_face":212.9189,"G08_pad_face":208.4929}.items():
    print(f"  {nm} z={z}  above_step_zmax_by={round(z-ZMAX,9)}")
# points inside the declared V2 support head volumes (foot-centred, 12 mm thick head under the pad face)
heads={"G07_head_54x54x12":(-37.0,17.0,-23.81,30.19,249.5016,261.5016),
       "G08_head_34x34x12":(153.0,187.0,24.550002,58.550002,196.4929,208.4929),
       "MID_head_34x34.41x12":(73.0,107.0,30.595001,65.005001,200.9189,212.9189),
       "G07_foot_20x60_full_tower":(-20.0,0.0,-26.809999,33.189999,113.15,261.5016),
       "G08_foot_20x60_full_tower":(160.0,180.0,11.55,71.550003,113.15,208.4929),
       "MID_foot_20x60_full_tower":(80.0,100.0,17.799999,77.800003,113.15,212.9189)}
for nm,(x0,x1,y0,y1,z0,z1) in heads.items():
    m=(A[:,0]>=x0)&(A[:,0]<=x1)&(A[:,1]>=y0)&(A[:,1]<=y1)&(A[:,2]>=z0)&(A[:,2]<=z1)
    print(f"  STEP points inside {nm}: {int(m.sum())}")
