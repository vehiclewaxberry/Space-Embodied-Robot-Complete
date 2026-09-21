# V8 wrist designer probe: candidate (WRAP_Z, K2_Z, descent via, exit adjust)
# evaluated directly against vendor fields (TriField distance, raw = dist - 4.5).
# Keeps J6 helix/rings/plate untouched (STOW +16.2 fix preserved).
import os
import json
import math
import importlib.util

import numpy as np
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("RC_VARIANT", "V7")
os.environ["RC_FAST"] = "1"
spec = importlib.util.spec_from_file_location(
    "rc_sweep", os.path.join(HERE, "ROUTE_C_EXACT_SWEEP_V1.py"))
SW = importlib.util.module_from_spec(spec)
spec.loader.exec_module(SW)

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
    if d<=R: return None,None
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
def chain_min_r(points, radii, r_min=54.0):
    cursor=points[0]; i=1; n=len(points); worst=1e9; ci=0
    while i < n:
        if i < n-1:
            R = radii[i-1] if i-1 < len(radii) else r_min
            if R and R>0:
                ci+=1
                p0,p1,p2=cursor,points[i],points[i+1]
                u=v_norm(v_sub(p1,p0)); v=v_norm(v_sub(p2,p1))
                th=math.degrees(math.acos(max(-1,min(1,v_dot(u,v)))))
                l1=v_dist(p0,p1); l2=v_dist(p1,p2)
                t=math.tan(math.radians(th/2)); T=R*t; Reff=R
                if T>0.98*min(l1,l2):
                    T=0.98*min(l1,l2); Reff=T/t
                worst=min(worst,Reff)
                cursor=v_add(p1,v_mul(v,T)); i+=1; continue
        cursor=points[i]; i+=1
    return worst

manifest = json.load(open(SW.P_MANIFEST, encoding="utf-8"))
mount = yaml.safe_load(open(SW.P_MOUNT, encoding="utf-8"))
arm = SW.ArmModel(SW.P_URDF, mount["mount"]["transform_mm_rows"])
T0 = arm.fk([0.0]*6)
inv_T0 = {k: np.linalg.inv(v) for k, v in T0.items()}
inv_mount = np.linalg.inv(arm.mount)

fields = {}
palm = None
for grp in manifest["files"]:
    if grp["group"] == "arm_vendor":
        for e in grp["entries"]:
            fields[e["link"]] = SW.TriField(
                e["link"], np.load(os.path.join(SW.P_PACK, e["file"]), allow_pickle=False))
    if grp["group"] == "gripper_rails":
        palm = SW.TriField("PALM", np.load(
            os.path.join(SW.P_PACK, grp["palm_slot"]["file"]), allow_pickle=False))

def eval_vs(pts_A0, link):
    """raw (dist - BUNDLE_R) of A0 points vs vendor link mesh at q=0."""
    Pl = SW.xform_batch(np.linalg.inv(arm.mount @ T0[link]),
                        SW.xform_batch(arm.mount, pts_A0))
    c = fields[link].signed_clearance_batch(Pl, SW.BUNDLE_R)
    return float(np.nanmin(c)) if np.isfinite(c).any() else math.inf

def eval_palm(pts_A0):
    Pl = SW.xform_batch(np.linalg.inv(arm.mount @ T0["gripper_link"]),
                        SW.xform_batch(arm.mount, pts_A0))
    c = palm.signed_clearance_batch(Pl, SW.BUNDLE_R)
    return float(np.nanmin(c)) if np.isfinite(c).any() else math.inf

def densify(points, ds=1.5):
    out=[]
    for a,b in zip(points[:-1],points[1:]):
        L=v_dist(a,b); n=max(1,int(L/ds))
        for k in range(n):
            t=k/n
            out.append((a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t, a[2]+(b[2]-a[2])*t))
    out.append(points[-1])
    return np.array(out)

YC = 81.625
J4_C = (5.0, YC, 135.0)
j4_end = circle_point(J4_C,(1,0,0),(0,0,1),55.0,90.0-315.0)
j4_exit = tangent_dir_circle((1,0,0),(0,0,1),90.0-315.0,-1)
s_j4 = (195.1 - j4_end[2]) / j4_exit[2]
M4 = v_add(j4_end, v_mul(j4_exit, s_j4)); M4 = (M4[0], YC, 195.1)
J6_ORIGIN = (105.0, 0.0, 191.7)
H0 = circle_point(J6_ORIGIN,(0,1,0),(0,0,1),55.0,180.0)
j6_entry = helix_tangent((1,0,0),(0,1,0),(0,0,1),55.0,20.0,180.0,+1)

def design(wrap_z, k2_z, d1, w2_len, a6_stub, j5x=20.0, j5y=-60.0):
    K2 = (115.0, YC-30.0, k2_z)
    J5_C = (j5x, j5y, wrap_z)
    t1xy, j5_start = tangent_point_from_external((j5x, j5y), 55.0, (K2[0], K2[1]), -1)
    if t1xy is None:
        return None
    T1_J5 = (t1xy[0], t1xy[1], wrap_z)
    j5_end_ang = j5_start - 185.0
    j5_end = circle_point(J5_C,(1,0,0),(0,1,0),55.0,j5_end_ang)
    j5_exit = tangent_dir_circle((1,0,0),(0,1,0),j5_end_ang,-1)
    W1 = v_add(j5_end, v_mul(j5_exit, 70.0))
    W2 = v_add(W1, v_mul(v_norm(v_sub((73.11,89.04,227.3),W1)), w2_len))
    A6 = v_sub(H0, v_mul(j6_entry, a6_stub))
    # descent poly: j4_end -> M4 -> K2 -> [D1?] -> T1_J5
    desc = [j4_end, M4, K2] + ([d1] if d1 else []) + [T1_J5]
    r_desc = chain_min_r(desc, [55.0]*(len(desc)-2))
    r_exit = chain_min_r([j5_end, W1, W2, A6, H0], [55.0,55.0,55.0])
    # wrap arc samples
    arc=[]
    n=int(185/3.0)
    for k in range(n+1):
        ang=j5_start-185.0*k/n
        arc.append(circle_point(J5_C,(1,0,0),(0,1,0),55.0,ang))
    pts_desc = densify(desc)
    pts_arc = np.array(arc)
    pts_exit = densify([j5_end, W1, W2, A6, H0])
    res = {"r_desc": r_desc, "r_exit": r_exit}
    for nm, pts in (("desc", pts_desc), ("wrap", pts_arc), ("exit", pts_exit)):
        for link in ("link3", "link4", "link5"):
            res["%s_%s" % (nm, link)] = eval_vs(pts, link)
        res["%s_palm" % nm] = eval_palm(pts)
    return res

def show(tag, r):
    if r is None:
        print(tag, "tangent infeasible"); return
    worst = min(v for k, v in r.items() if isinstance(v, float) and not k.startswith("r_"))
    print("%-46s r_d %.0f r_e %.0f | d3 %6.1f d4 %6.1f d5 %6.1f | w3 %6.1f w4 %6.1f w5 %6.1f wp %6.1f | e3 %6.1f e4 %6.1f e5 %6.1f ep %6.1f | worst %6.1f" % (
        tag, r["r_desc"], r["r_exit"],
        r["desc_link3"], r["desc_link4"], r["desc_link5"],
        r["wrap_link3"], r["wrap_link4"], r["wrap_link5"], r["wrap_palm"],
        r["exit_link3"], r["exit_link4"], r["exit_link5"], r["exit_palm"], worst))

print("baseline V7: wrap_z 210, k2_z 260, no via, w2 140, a6 120")
show("V7 baseline", design(210.0, 260.0, None, 140.0, 120.0))
print()
cands = [
    ("wrap218 k2 268",               (218.0, 268.0, None, 140.0, 120.0)),
    ("wrap220 k2 272",               (220.0, 272.0, None, 140.0, 120.0)),
    ("wrap220 k2 272 D1(100,-10,266)",(220.0, 272.0, (100.0,-10.0,266.0), 140.0, 120.0)),
    ("wrap222 k2 275 D1(100,-15,270)",(222.0, 275.0, (100.0,-15.0,270.0), 140.0, 120.0)),
    ("wrap220 k2 272 D1 a6 130",     (220.0, 272.0, (100.0,-10.0,266.0), 140.0, 130.0)),
    ("wrap222 k2 275 D1 a6 130",     (222.0, 275.0, (100.0,-15.0,270.0), 140.0, 130.0)),
    ("wrap222 k2 275 D1 w2 150 a6 135",(222.0, 275.0, (100.0,-15.0,270.0), 150.0, 135.0)),
]
for tag, args in cands:
    show(tag, design(*args))
