# V8 wrist designer v2: "south bypass" route (option iii outer standoff).
# Descent: K2 -> E1 (NE diagonal) -> E2 (south along x~135) -> T1_J5 (2D tangent)
# Exit:    j5_end -> W1 -> W2 (retarget SE) -> A6 -> H0
# Evaluates raw (dist-4.5) vs link3/4/5 + palm, plus chained corner radii >= 54.
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
def chain_min_r(points, radii, r_min=54.0, detail=None):
    cursor=points[0]; i=1; n=len(points); worst=1e9
    while i < n:
        if i < n-1:
            R = radii[i-1] if i-1 < len(radii) else r_min
            if R and R>0:
                p0,p1,p2=cursor,points[i],points[i+1]
                u=v_norm(v_sub(p1,p0)); v=v_norm(v_sub(p2,p1))
                th=math.degrees(math.acos(max(-1,min(1,v_dot(u,v)))))
                l1=v_dist(p0,p1); l2=v_dist(p1,p2)
                t=math.tan(math.radians(th/2)); T=R*t; Reff=R
                if T>0.98*min(l1,l2):
                    T=0.98*min(l1,l2); Reff=T/t
                worst=min(worst,Reff)
                if detail is not None:
                    detail.append("corner@%s th %.1f legs %.1f/%.1f Reff %.1f" % (
                        str([round(x,1) for x in p1]), th, l1, l2, Reff))
                cursor=v_add(p1,v_mul(v,T)); i+=1; continue
        cursor=points[i]; i+=1
    return worst

manifest = json.load(open(SW.P_MANIFEST, encoding="utf-8"))
mount = yaml.safe_load(open(SW.P_MOUNT, encoding="utf-8"))
arm = SW.ArmModel(SW.P_URDF, mount["mount"]["transform_mm_rows"])
T0 = arm.fk([0.0]*6)
fields = {}
palm = None
rails = []
for grp in manifest["files"]:
    if grp["group"] == "arm_vendor":
        for e in grp["entries"]:
            fields[e["link"]] = SW.TriField(
                e["link"], np.load(os.path.join(SW.P_PACK, e["file"]), allow_pickle=False))
    if grp["group"] == "gripper_rails":
        for e in grp.get("entries", []):
            rails.append(SW.TriField("RAIL", np.load(
                os.path.join(SW.P_PACK, e["file"]), allow_pickle=False)))
        palm = SW.TriField("PALM", np.load(
            os.path.join(SW.P_PACK, grp["palm_slot"]["file"]), allow_pickle=False))

def eval_fld(pts_A0, link, fld):
    Pl = SW.xform_batch(np.linalg.inv(arm.mount @ T0[link]),
                        SW.xform_batch(arm.mount, pts_A0))
    c = fld.signed_clearance_batch(Pl, SW.BUNDLE_R)
    if not np.isfinite(c).any():
        return math.inf, None
    k = int(np.nanargmin(c))
    return float(c[k]), pts_A0[k]

def eval_vs(pts_A0, link):
    v, _ = eval_fld(pts_A0, link, fields[link])
    return v
def eval_grip(pts_A0):
    vals = [eval_fld(pts_A0, "gripper_link", palm)[0]] + \
           [eval_fld(pts_A0, "gripper_link", f)[0] for f in rails]
    return min(vals)
def eval_vs_pt(pts_A0, link):
    return eval_fld(pts_A0, link, fields[link])

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

def design(tag, wrap_z, k2, e1, e2, w2_target, w2_len, a6_stub, j5x=20.0, j5y=-60.0, verbose=True):
    J5_C = (j5x, j5y, wrap_z)
    t1xy, j5_start = tangent_point_from_external((j5x, j5y), 55.0, (e2[0], e2[1]), -1)
    if t1xy is None:
        print(tag, "tangent infeasible"); return None
    T1_J5 = (t1xy[0], t1xy[1], wrap_z)
    j5_end_ang = j5_start - 185.0
    j5_end = circle_point(J5_C,(1,0,0),(0,1,0),55.0,j5_end_ang)
    j5_exit = tangent_dir_circle((1,0,0),(0,1,0),j5_end_ang,-1)
    W1 = v_add(j5_end, v_mul(j5_exit, 70.0))
    W2 = v_add(W1, v_mul(v_norm(v_sub(w2_target, W1)), w2_len))
    A6 = v_sub(H0, v_mul(j6_entry, a6_stub))
    desc = [j4_end, M4, k2, e1, e2, T1_J5]
    exitp = [j5_end, W1, W2, A6, H0]
    det = []
    r_desc = chain_min_r(desc, [55.0]*4, detail=det)
    r_exit = chain_min_r(exitp, [55.0,55.0,55.0], detail=det)
    arc=[]
    n=int(185/3.0)
    for k in range(n+1):
        ang=j5_start-185.0*k/n
        arc.append(circle_point(J5_C,(1,0,0),(0,1,0),55.0,ang))
    pts = {"desc": densify(desc), "wrap": np.array(arc), "exit": densify(exitp)}
    res = {"r_desc": r_desc, "r_exit": r_exit,
           "T1_J5": T1_J5, "j5_start": j5_start, "j5_end": j5_end, "W1": W1, "W2": W2, "A6": A6,
           "corners": det}
    for nm, p in pts.items():
        for link in ("link3", "link4", "link5"):
            v, wp = eval_vs_pt(p, link)
            res["%s_%s" % (nm, link)] = v
            if v < 3.0 and wp is not None:
                res["%s_%s_worstpt" % (nm, link)] = [round(float(x), 1) for x in wp]
        res["%s_grip" % nm] = eval_grip(p)
    if verbose:
        worst = min(v for k, v in res.items()
                    if isinstance(v, float) and not k.startswith(("r_", "j5")))
        print("%-40s rd %4.0f re %4.0f | d3 %6.1f d4 %6.1f d5 %6.1f dg %6.1f | w3 %6.1f w4 %6.1f w5 %6.1f wg %6.1f | e3 %6.1f e4 %6.1f e5 %6.1f eg %6.1f | worst %6.1f" % (
            tag, r_desc, r_exit,
            res["desc_link3"], res["desc_link4"], res["desc_link5"], res["desc_grip"],
            res["wrap_link3"], res["wrap_link4"], res["wrap_link5"], res["wrap_grip"],
            res["exit_link3"], res["exit_link4"], res["exit_link5"], res["exit_grip"], worst))
        for k, v in res.items():
            if k.endswith("_worstpt"):
                print("    %-18s %s" % (k, v))
        if r_desc < 54.0 or r_exit < 54.0:
            for c in det:
                print("    corner: %s" % c)
    return res

K2 = (115.0, YC-30.0, 260.0)
print("=== east-approach candidates (preserve V7-like arc span) ===")
design("ea1: E1(150,45,252) E2(145,-30,250) wz210",
       210.0, K2, (150.0,45.0,252.0), (145.0,-30.0,250.0), (130.0,-80.0,255.0), 140.0, 120.0)
design("ea2: E1(165,48,255) E2(155,-35,250) wz210",
       210.0, K2, (165.0,48.0,255.0), (155.0,-35.0,250.0), (135.0,-85.0,258.0), 145.0, 125.0)
design("ea3: E1(172,48,255) E2(160,-35,250) wz210",
       210.0, K2, (172.0,48.0,255.0), (160.0,-35.0,250.0), (135.0,-85.0,258.0), 145.0, 125.0)
design("ea4: ea3 wz215",
       215.0, K2, (172.0,48.0,255.0), (160.0,-35.0,253.0), (135.0,-85.0,260.0), 145.0, 125.0)
design("ea5: E1(165,48,255) E2(150,-40,252) wz212",
       212.0, K2, (165.0,48.0,255.0), (150.0,-40.0,252.0), (135.0,-85.0,258.0), 145.0, 125.0)
