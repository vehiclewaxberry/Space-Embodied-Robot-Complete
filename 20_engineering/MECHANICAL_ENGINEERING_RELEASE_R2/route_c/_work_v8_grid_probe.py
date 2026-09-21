# V8 J5-wrap position grid probe (corner-probe driven, no FreeCAD).
# For candidate J5_C xy positions between V3 (palm-hit) and V7 (body-hit),
# rebuild SEG-04 sec1 / SEG-05 sec0+sec1 centerlines (V7 rules incl. corner
# fillet chaining) and evaluate min signed clearance vs link3/link4/link5/
# gripper(palm)/rails fields at q=0, plus corner radii >= 54 rule.
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

def chain_corners_ok(points, radii, r_min=54.0):
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

# ---- load fields once --------------------------------------------------------
manifest = json.load(open(SW.P_MANIFEST, encoding="utf-8"))
mount = yaml.safe_load(open(SW.P_MOUNT, encoding="utf-8"))
arm = SW.ArmModel(SW.P_URDF, mount["mount"]["transform_mm_rows"])
T0 = arm.fk([0.0]*6)
inv_T0 = {k: np.linalg.inv(v) for k, v in T0.items()}
inv_TS0 = {k: np.linalg.inv(arm.mount @ v) for k, v in T0.items()}

fields = {}
for grp in manifest["files"]:
    if grp["group"] == "arm_vendor":
        for e in grp["entries"]:
            fields[e["link"]] = SW.TriField(
                e["link"], np.load(os.path.join(SW.P_PACK, e["file"]), allow_pickle=False))
palm = None; rails = []
for grp in manifest["files"]:
    if grp["group"] == "gripper_rails":
        for e in grp.get("entries", []):
            rails.append(SW.TriField("RAIL_"+e["side"], np.load(
                os.path.join(SW.P_PACK, e["file"]), allow_pickle=False)))
        palm = SW.TriField("PALM", np.load(
            os.path.join(SW.P_PACK, grp["palm_slot"]["file"]), allow_pickle=False))

YC = 81.625
K2 = (115.0, YC-30.0, 260.0)
M4 = None  # SEG-04 poly is [j4_end, M4, K2, T1_J5]; M4/j4_end unchanged by J5_C
J4_C = (5.0, YC, 135.0)
j4_start_ang = 90.0; j4_sweep = -315.0
j4_end_ang = j4_start_ang + j4_sweep
j4_end = circle_point(J4_C,(1,0,0),(0,0,1),55.0,j4_end_ang)
j4_exit = tangent_dir_circle((1,0,0),(0,0,1),j4_end_ang,-1)
s_j4 = (195.1 - j4_end[2]) / j4_exit[2]
M4 = v_add(j4_end, v_mul(j4_exit, s_j4)); M4 = (M4[0], YC, 195.1)

J6_ORIGIN = (105.0, 0.0, 191.7)
j6_pitch = 20.0
H0 = circle_point(J6_ORIGIN,(0,1,0),(0,0,1),55.0,180.0)
j6_entry = helix_tangent((1,0,0),(0,1,0),(0,0,1),55.0,j6_pitch,180.0,+1)
A6 = v_sub(H0, v_mul(j6_entry, 120.0))

def eval_pts(pts_S, host, fld):
    """pts given in A0(q=0); evaluate vs field hosted on `host` (rigid q=0)."""
    Pl = SW.xform_batch(inv_TS0[host], SW.xform_batch(arm.mount @ T0[host] @ inv_T0[host], pts_S))
    c = fld.signed_clearance_batch(Pl, SW.BUNDLE_R)
    return float(np.nanmin(c)) if np.isfinite(c).any() else math.inf

def build_and_eval(j5x, j5y, w2_len=140.0, a6_stub=120.0, verbose=False):
    J5_C = (j5x, j5y, 210.0)
    t1xy, j5_start = tangent_point_from_external((j5x, j5y), 55.0, (K2[0], K2[1]), -1)
    if t1xy is None:
        return None
    T1_J5 = (t1xy[0], t1xy[1], 210.0)
    j5_end_ang = j5_start - 185.0
    j5_end = circle_point(J5_C,(1,0,0),(0,1,0),55.0,j5_end_ang)
    j5_exit = tangent_dir_circle((1,0,0),(0,1,0),j5_end_ang,-1)
    W1 = v_add(j5_end, v_mul(j5_exit, 70.0))
    W2 = v_add(W1, v_mul(v_norm(v_sub((73.11,89.04,227.3),W1)), w2_len))
    # corner rules
    r_seg04 = chain_corners_ok([j4_end, M4, K2, T1_J5], [55.0,55.0,55.0])
    r_seg05 = chain_corners_ok([j5_end, W1, W2, A6, H0], [55.0,55.0,55.0])
    # sample the legs (straight fillet-ignored sampling is fine for clearance:
    # fillets only round corners inward, away from obstacles; legs dominate)
    def densify(points, ds=1.5):
        out=[]
        for a,b in zip(points[:-1],points[1:]):
            L=v_dist(a,b); n=max(1,int(L/ds))
            for k in range(n):
                t=k/n; out.append((a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t, a[2]+(b[2]-a[2])*t))
        out.append(points[-1]); return np.array(out)
    # wrap arc samples
    arc=[]
    n=int(185/3.0)
    for k in range(n+1):
        ang=j5_start-185.0*k/n
        arc.append(circle_point(J5_C,(1,0,0),(0,1,0),55.0,ang))
    pts_descent = densify([M4, K2, T1_J5])
    pts_arc = np.array(arc)
    pts_exit = densify([j5_end, W1, W2, A6, H0])
    res = {"j5c": (j5x, j5y), "r04": r_seg04, "r05": r_seg05}
    for name, pts, hosts in (
        ("descent", pts_descent, ("link3","link4")),
        ("wrap", pts_arc, ("link4","link5")),
        ("exit", pts_exit, ("link4","link5","link6"))):
        for h in hosts:
            res["%s_vs_%s" % (name, h)] = eval_pts(pts, h, fields[h])
    # palm/rails live on gripper_link
    for nm, fld in (("palm", palm),) + tuple(("rail%d"%i, f) for i, f in enumerate(rails)):
        res["exit_vs_%s" % nm] = eval_pts(pts_exit, "gripper_link", fld)
        res["wrap_vs_%s" % nm] = eval_pts(pts_arc, "gripper_link", fld)
        res["descent_vs_%s" % nm] = eval_pts(pts_descent, "gripper_link", fld)
    if verbose:
        for k, v in sorted(res.items()):
            print("   ", k, v if not isinstance(v, float) else round(v, 2))
    return res

grid = [(76.908, 0.0), (70.0, -10.0), (60.0, -20.0), (50.0, -30.0),
        (40.0, -45.0), (55.0, -25.0), (65.0, -15.0), (20.0, -60.0)]
print("%-16s %6s %6s | %8s %8s | %7s %7s | %7s %7s %7s | %8s" % (
    "J5_C", "r04", "r05", "desc_l3", "desc_l4", "wrp_l4", "wrp_l5",
    "ext_l4", "ext_l5", "ext_l6", "wrst_palm"))
for gx, gy in grid:
    r = build_and_eval(gx, gy)
    if r is None:
        print((gx, gy), "tangent infeasible"); continue
    worst_palm = min(r["exit_vs_palm"], r["wrap_vs_palm"], r["descent_vs_palm"])
    print("%-16s %6.1f %6.1f | %8.2f %8.2f | %7.2f %7.2f | %7.2f %7.2f %7.2f | %8.2f" % (
        str((gx, gy)), r["r04"], r["r05"],
        r["descent_vs_link3"], r["descent_vs_link4"],
        r["wrap_vs_link4"], r["wrap_vs_link5"],
        r["exit_vs_link4"], r["exit_vs_link5"], r["exit_vs_link6"],
        worst_palm))
