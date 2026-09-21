# Offline corner-geometry probe for V7 fixes (SEG-00 r-reroute, SEG-05 A6 leg).
# Replicates helper math from B601_ROUTE_C_BUILD_V7.py (pure python, no FreeCAD).
import math

def v_add(a,b): return (a[0]+b[0], a[1]+b[1], a[2]+b[2])
def v_sub(a,b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def v_mul(a,s): return (a[0]*s, a[1]*s, a[2]*s)
def v_dot(a,b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def v_len(a): return math.sqrt(v_dot(a,a))
def v_norm(a):
    l=v_len(a); return (a[0]/l,a[1]/l,a[2]/l)
def v_dist(a,b): return v_len(v_sub(a,b))
def circle_point(center,e1,e2,R,ang):
    a=math.radians(ang)
    return v_add(center,v_add(v_mul(e1,R*math.cos(a)),v_mul(e2,R*math.sin(a))))
def tangent_dir_circle(e1,e2,ang,sense):
    a=math.radians(ang)
    if sense>0: return v_norm(v_add(v_mul(e1,-math.sin(a)),v_mul(e2,math.cos(a))))
    return v_norm(v_add(v_mul(e1,math.sin(a)),v_mul(e2,-math.cos(a))))
def tangent_point_from_external(c2d,R,p2d,sense):
    dx=p2d[0]-c2d[0]; dy=p2d[1]-c2d[1]; d=math.hypot(dx,dy)
    base=math.degrees(math.atan2(dy,dx)); alpha=math.degrees(math.acos(R/d))
    t_leg=math.sqrt(d*d-R*R); cands=[]
    for sign in (+1,-1):
        ang=base+sign*alpha
        tx=c2d[0]+R*math.cos(math.radians(ang)); ty=c2d[1]+R*math.sin(math.radians(ang))
        if sense>0: td=(-math.sin(math.radians(ang)),math.cos(math.radians(ang)))
        else: td=(math.sin(math.radians(ang)),-math.cos(math.radians(ang)))
        ap=((tx-p2d[0])/t_leg,(ty-p2d[1])/t_leg)
        cands.append((td[0]*ap[0]+td[1]*ap[1],(tx,ty),ang))
    cands.sort(key=lambda c:-c[0])
    return cands[0][1],cands[0][2]
def helix_tangent(axis,e1,e2,R,pitch,ang,sense):
    a=math.radians(ang); axial=pitch/(2*math.pi)*sense
    return v_norm(v_add(v_mul(axis,axial),v_mul(tangent_dir_circle(e1,e2,ang,sense),R)))

def corner(p0,p1,p2,R=55.0):
    u=v_norm(v_sub(p1,p0)); v=v_norm(v_sub(p2,p1))
    cos_t=max(-1.0,min(1.0,v_dot(u,v)))
    th=math.degrees(math.acos(cos_t))
    l1=v_dist(p0,p1); l2=v_dist(p1,p2)
    t=math.tan(math.radians(th/2)); T=R*t; Reff=R
    if T>0.98*min(l1,l2):
        T=0.98*min(l1,l2); Reff=T/t
    return th,l1,l2,T,Reff

YC=81.625
HN00=(-29.58,-63.44,-70.0)
HN02=(-29.58,-63.44,-18.41)
J1_C=(-0.084,0.0,126.0)

print("=== SEG-00 candidate r values (WP_OUT/KP y=-r) ===")
for r in (140.0,160.0,165.0,170.0,175.0):
    KP=(-0.084,-r,126.0); WP_OUT=(-0.084,-r,-10.0)
    t1_2d,_=tangent_point_from_external((J1_C[0],J1_C[1]),60.0,(KP[0],KP[1]),-1)
    T1_COIL=(t1_2d[0],t1_2d[1],126.0)
    c1=corner(HN00,HN02,WP_OUT)
    c2=corner(HN02,WP_OUT,KP)
    c3=corner(WP_OUT,KP,T1_COIL)
    # shared-leg check: T at corner1 (leg_out into HN02->WP_OUT) + T at corner2 (leg_in)
    shared = c1[3]+c2[3]
    print(f"r={r:5.1f}  HN02-WPO dist={v_dist(HN02,WP_OUT):7.2f}  "
          f"c1 th={c1[0]:5.1f} T={c1[3]:5.2f} Reff={c1[4]:5.2f} | "
          f"c2 th={c2[0]:5.1f} T={c2[3]:5.2f} Reff={c2[4]:5.2f} | shared T sum={shared:6.2f} vs 0.98*dist={0.98*v_dist(HN02,WP_OUT):6.2f} | "
          f"c3 th={c3[0]:5.1f} Reff={c3[4]:5.2f}")

print()
print("=== SEG-05 chain (J5 wrap -> W1 -> W2 -> A6 -> H0) ===")
J5_C=(20.0,-60.0,210.0)
K2=(115.0,YC-30.0,260.0)
j5_t1,j5_start=tangent_point_from_external((J5_C[0],J5_C[1]),55.0,(K2[0],K2[1]),-1)
j5_end_ang=j5_start-185.0
j5_end=circle_point(J5_C,(1,0,0),(0,1,0),55.0,j5_end_ang)
j5_exit=tangent_dir_circle((1,0,0),(0,1,0),j5_end_ang,-1)
J6_ORIGIN=(105.0,0.0,191.7)
H0=circle_point(J6_ORIGIN,(0,1,0),(0,0,1),55.0,180.0)
j6_entry_tan=helix_tangent((1,0,0),(0,1,0),(0,0,1),55.0,20.0,180.0,+1)

def seg05(w1_len, w2_len, a6_stub):
    W1=v_add(j5_end,v_mul(j5_exit,w1_len))
    W2=v_add(W1,v_mul(v_norm(v_sub((73.11,89.04,227.3),W1)),w2_len))
    A6=v_sub(H0,v_mul(j6_entry_tan,a6_stub))
    c1=corner(j5_end,W1,W2)
    c2=corner(W1,W2,A6)
    c3=corner(W2,A6,H0)
    return W1,W2,A6,c1,c2,c3

for w1l,w2l,a6s in ((70,130,110),(70,130,120),(70,140,110),(70,135,120),(75,135,115),(70,140,120),(70,145,110)):
    W1,W2,A6,c1,c2,c3=seg05(w1l,w2l,a6s)
    print(f"w1={w1l} w2={w2l} a6={a6s}: "
          f"c1@W1 th={c1[0]:5.1f} Reff={c1[4]:5.2f} (legs {c1[1]:.1f}/{c1[2]:.1f}) | "
          f"c2@W2 th={c2[0]:5.1f} Reff={c2[4]:5.2f} (legs {c2[1]:.1f}/{c2[2]:.1f}) | "
          f"c3@A6 th={c3[0]:5.1f} Reff={c3[4]:5.2f} (legs {c3[1]:.1f}/{c3[2]:.1f})")
