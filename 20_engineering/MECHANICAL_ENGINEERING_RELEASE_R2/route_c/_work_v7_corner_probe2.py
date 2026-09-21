# Chained-fillet corner probe: models poly_edges cursor chaining exactly.
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

def chain_corners(points, radii, r_min=54.0):
    """Replicates poly_edges chaining: cursor advances past each fillet."""
    out=[]; cursor=points[0]; i=1; n=len(points); ci=0
    while i < n:
        if i < n-1:
            R = radii[i-1] if i-1 < len(radii) else r_min
            if R and R>0:
                ci+=1
                p0,p1,p2 = cursor, points[i], points[i+1]
                u=v_norm(v_sub(p1,p0)); v=v_norm(v_sub(p2,p1))
                th=math.degrees(math.acos(max(-1,min(1,v_dot(u,v)))))
                l1=v_dist(p0,p1); l2=v_dist(p1,p2)
                t=math.tan(math.radians(th/2)); T=R*t; Reff=R; clamped=False
                if T>0.98*min(l1,l2):
                    T=0.98*min(l1,l2); Reff=T/t; clamped=True
                out.append((ci,th,l1,l2,T,Reff,clamped))
                cursor = v_add(p1, v_mul(v, T))
                i+=1; continue
        cursor=points[i]; i+=1
    return out

def rep(name, pts, radii):
    cs = chain_corners(pts, radii)
    worst = min(c[5] for c in cs)
    stat = "PASS" if worst >= 54.0-1e-9 else "FAIL"
    print(f"[{stat}] {name}  worst Reff={worst:.2f}")
    for ci,th,l1,l2,T,Reff,cl in cs:
        flag = " CLAMPED" if cl else ""
        print(f"   corner{ci}: th={th:5.1f} legs={l1:6.2f}/{l2:6.2f} T={T:5.2f} Reff={Reff:5.2f}{flag}")
    return worst

YC=81.625
HN00=(-29.58,-63.44,-70.0)
HN02=(-29.58,-63.44,-18.41)
J1_C=(-0.084,0.0,126.0)
print("=== SEG-00 chained (HN00->HN02->WP_OUT->KP->T1_COIL) ===")
for r in (160.0,165.0,170.0):
    KP=(-0.084,-r,126.0); WP_OUT=(-0.084,-r,-10.0)
    t1,_=tangent_point_from_external((J1_C[0],J1_C[1]),60.0,(KP[0],KP[1]),-1)
    T1_COIL=(t1[0],t1[1],126.0)
    rep(f"SEG-00 r={r}", [HN00,HN02,WP_OUT,KP,T1_COIL], [55.0,55.0,55.0])

print()
print("=== SEG-05 chained (j5_end->W1->W2->A6->H0) ===")
J5_C=(20.0,-60.0,210.0); K2=(115.0,YC-30.0,260.0)
_,j5_start=tangent_point_from_external((J5_C[0],J5_C[1]),55.0,(K2[0],K2[1]),-1)
j5_end_ang=j5_start-185.0
j5_end=circle_point(J5_C,(1,0,0),(0,1,0),55.0,j5_end_ang)
j5_exit=tangent_dir_circle((1,0,0),(0,1,0),j5_end_ang,-1)
J6_ORIGIN=(105.0,0.0,191.7)
H0=circle_point(J6_ORIGIN,(0,1,0),(0,0,1),55.0,180.0)
j6_entry=helix_tangent((1,0,0),(0,1,0),(0,0,1),55.0,20.0,180.0,+1)
for w1l,w2l,a6s in ((70,130,110),(70,140,120),(70,145,125),(70,140,130),(75,140,125)):
    W1=v_add(j5_end,v_mul(j5_exit,float(w1l)))
    W2=v_add(W1,v_mul(v_norm(v_sub((73.11,89.04,227.3),W1)),float(w2l)))
    A6=v_sub(H0,v_mul(j6_entry,float(a6s)))
    rep(f"SEG-05 w1={w1l} w2={w2l} a6={a6s}", [j5_end,W1,W2,A6,H0], [55.0,55.0,55.0])
