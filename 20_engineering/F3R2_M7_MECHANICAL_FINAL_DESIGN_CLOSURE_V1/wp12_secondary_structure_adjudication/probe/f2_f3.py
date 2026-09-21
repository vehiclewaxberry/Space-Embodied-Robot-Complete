import numpy as np, struct, os, math, json
BASE=r"f:/China Graduate Future Flight Vehicle Innovation Competition"
# ---------- FINDING 3: is x=215.0 inside the B601 base_link body? ----------
bl=os.path.join(BASE,r"20_engineering/cad/spacecraft_layout/arm_b601_v1/meshes_b601_gripper/base_link.STL")
with open(bl,'rb') as f:
    n=struct.unpack('<I',f.read(84)[80:84])[0]; raw=f.read(n*50)
a=np.frombuffer(raw,dtype=np.uint8).reshape(n,50)
V=a[:,12:48].copy().view('<f4').reshape(n*3,3).astype(np.float64)*1000.0   # mm, link-local
print("=== FINDING 3 : accepted-URDF base_link (L0) in link-local mm ===")
print(" aabb:",[round(float(x),4) for x in [V[:,0].min(),V[:,1].min(),V[:,2].min(),V[:,0].max(),V[:,1].max(),V[:,2].max()]])
print(" T_S_B601_ARM_BASE maps global_x = 208.0 + z_local  =>  base_link occupies global x in",
      [round(208.0+float(V[:,2].min()),4), round(208.0+float(V[:,2].max()),4)])
for gx in (208.0,210.405,215.0,220.0,290.65):
    zl=gx-208.0
    m=np.abs(V[:,2]-zl)<=0.25
    if m.any():
        r=np.hypot(V[m,0],V[m,1])
        print(f"  global x={gx:8.3f} (z_local={zl:7.3f} mm): mesh vertices in +/-0.25 mm band = {int(m.sum()):6d}"
              f"  radial extent r=[{r.min():.3f},{r.max():.3f}] mm")
    else:
        print(f"  global x={gx:8.3f} (z_local={zl:7.3f} mm): NO mesh vertices in band")
# ---------- FINDING 2 : hinge / panel geometry ----------
print("\n=== FINDING 2 : solar hinge vs panel proxy ===")
axis=(143.15,0.0)
pan=dict(y0=113.15,y1=313.15,z0=-3.0,z1=3.0,x0=-170.25,x1=56.75)
print(" neutral deployed panel proxy AABB (build report):",pan, " volume_mm3 =",(pan['x1']-pan['x0'])*(pan['y1']-pan['y0'])*(pan['z1']-pan['z0']))
corners=[(y,z) for y in (pan['y0'],pan['y1']) for z in (pan['z0'],pan['z1'])]
rr=[math.hypot(y-axis[0],z-axis[1]) for y,z in corners]
print(" radial distances of the four (y,z) corners from the declared axis:",[round(r,6) for r in rr])
print(" r_max =",round(max(rr),7),"  r_min (axis inside material) = 0.0")
print(" axis inside panel material?", pan['y0']<=axis[0]<=pan['y1'] and pan['z0']<=axis[1]<=pan['z1'])
print(" inboard straddle =",round(axis[0]-pan['y0'],6),"mm ; outboard reach =",round(pan['y1']-axis[0],6),"mm")
# implied axis from the native stowed<->deployed box pair
sy0,sy1,sz0,sz1=113.150002,119.150002,-200.0,0.0
dy0,dy1,dz0,dz1=113.150002,313.149994,-3.0,3.0
y0z0=dy0            # y0+z0
z0my0=dz0-sy0       # z0-y0
z0=(y0z0+z0my0)/2.0; y0=y0z0-z0
print(" axis implied by native WING_L STOWED<->DEPLOYED rigid 90 deg rotation: (y,z) = (%.6f, %.6f)"%(y0,z0))
print("   offset from declared axis:", round(math.hypot(y0-axis[0],z0-axis[1]),6),"mm  (dy=%.6f, dz=%.6f)"%(y0-axis[0],z0-axis[1]))
# native stowed wing radius about the declared axis
sc=[(y,z) for y in (sy0,sy1) for z in (sz0,sz1)]
sr=[math.hypot(y-axis[0],z-axis[1]) for y,z in sc]
print(" native STOWED wing max radius about the declared axis =",round(max(sr),6),
      "mm vs neutral DEPLOYED panel max radius",round(max(rr),6),"mm ; delta =",round(max(sr)-max(rr),6),"mm")
# inertia sensitivity about the declared axis
m=0.3483933; L=0.200
I_root_at_axis=m*L*L/3.0
lam=m/L; a_in=0.030; a_out=0.170
I_straddle=lam*((a_out**3)+(a_in**3))/3.0
print(" I about declared axis, root-at-axis model  =",I_root_at_axis,"kg m^2  (WP5 MAV-01 value 0.004645244)")
print(" I about declared axis, proxy-as-placed     =",I_straddle,"kg m^2")
print("   relative difference =",round(100*(I_straddle-I_root_at_axis)/I_root_at_axis,4),"%")
Mnet=0.15; th=math.pi/2
print(" undamped time sqrt(2 I th / Mnet): root-at-axis =",round(math.sqrt(2*I_root_at_axis*th/Mnet),6),
      "s ; proxy-as-placed =",round(math.sqrt(2*I_straddle*th/Mnet),6),"s   (WP5 quotes 0.312 s)")
print(" stop energy Mnet*theta =",round(Mnet*th,6),"J (inertia-independent, unaffected)")
print(" M6 tip sensitivity 0.2 mm/mrad implies a moment arm of",0.2/1e-3,"mm =",200.0,"mm = panel span -> root-at-axis intent")
# analytic keep-out envelopes
print("\n analytic KO-03 envelopes about the declared axis (x-range from panel chord):")
rmax=max(rr)
print("  FAIL_CLOSED_FULL_REVOLUTION: y in [%.6f, %.6f], z in [%.6f, %.6f]"%(axis[0]-rmax,axis[0]+rmax,axis[1]-rmax,axis[1]+rmax))
print("  bus outer |y| = 113.15 -> full-revolution envelope reaches y = %.6f  => intersects the bus by %.6f mm"%(axis[0]-rmax, 113.15-(axis[0]-rmax)))
