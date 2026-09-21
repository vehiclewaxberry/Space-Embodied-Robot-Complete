# Probe SEG-01 corner at P_J1OUT vs r (KP radius) and mitigations.
import math

def v_add(a,b): return (a[0]+b[0], a[1]+b[1], a[2]+b[2])
def v_sub(a,b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def v_mul(a,s): return (a[0]*s, a[1]*s, a[2]*s)
def v_dot(a,b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def v_len(a): return math.sqrt(v_dot(a,a))
def v_norm(a):
    l=v_len(a); return (a[0]/l,a[1]/l,a[2]/l)
def v_dist(a,b): return v_len(v_sub(a,b))
def circle_point(c,e1,e2,R,ang):
    a=math.radians(ang)
    return v_add(c,v_add(v_mul(e1,R*math.cos(a)),v_mul(e2,R*math.sin(a))))
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
    th=math.degrees(math.acos(max(-1,min(1,v_dot(u,v)))))
    l1=v_dist(p0,p1); l2=v_dist(p1,p2)
    t=math.tan(math.radians(th/2)); T=R*t; Reff=R
    if T>0.98*min(l1,l2):
        T=0.98*min(l1,l2); Reff=T/t
    return th,l1,l2,T,Reff

YC=81.625
J1_C=(-0.084,0.0,126.0)
def seg01(r, sweep=-432.0, j2c=(15.0,85.0), pitch=-12.0):
    KP=(-0.084,-r,126.0)
    _,j1_start=tangent_point_from_external((J1_C[0],J1_C[1]),60.0,(KP[0],KP[1]),-1)
    j1_end_ang=j1_start+sweep
    j1_end=circle_point(J1_C,(1,0,0),(0,1,0),60.0,j1_end_ang)
    j1_end=(j1_end[0],j1_end[1],126.0+pitch*math.radians(sweep)/(2*math.pi))
    ext=helix_tangent((0,0,1),(1,0,0),(0,1,0),60.0,pitch,j1_end_ang,-1)
    s=(YC-j1_end[1])/ext[1]
    P=v_add(j1_end,v_mul(ext,s))
    _,j2_start=tangent_point_from_external((j2c[0],j2c[1]),55.0,(P[0],P[2]),-1)
    T1_J2=circle_point((j2c[0],YC,j2c[1]),(1,0,0),(0,0,1),55.0,j2_start)
    return corner(j1_end,P,T1_J2), j1_start, s

print("r sweep (baseline j2c=(15,85), sweep=-432):")
for r in (140.0,150.0,155.0,160.0,165.0,170.0):
    c,st,s=seg01(r)
    print(f"  r={r:5.1f}: th={c[0]:5.1f} legs={c[1]:6.2f}/{c[2]:6.2f} Reff={c[4]:5.2f}  (start_ang={st:.1f}, s_stub={s:.1f})")
print("mitigation: j1_sweep tweak at r=165:")
for sw in (-420.0,-426.0,-432.0,-438.0,-444.0,-450.0):
    c,st,s=seg01(165.0,sweep=sw)
    print(f"  sweep={sw}: th={c[0]:5.1f} legs={c[1]:6.2f}/{c[2]:6.2f} Reff={c[4]:5.2f}")
print("mitigation: J2_C shift at r=165, sweep=-432:")
for j2c in ((15.0,85.0),(15.0,80.0),(15.0,75.0),(10.0,85.0),(20.0,85.0),(15.0,90.0)):
    c,st,s=seg01(165.0,j2c=j2c)
    print(f"  j2c={j2c}: th={c[0]:5.1f} legs={c[1]:6.2f}/{c[2]:6.2f} Reff={c[4]:5.2f}")
