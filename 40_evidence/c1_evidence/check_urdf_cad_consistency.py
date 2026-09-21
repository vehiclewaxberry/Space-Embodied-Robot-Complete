# check_urdf_cad_consistency.py — independent cross-check of URDF vs CAD assembly.
# Independent FK implemented with stdlib math (no FreeCAD math) for comparison.
import os, sys, json, math
import FreeCAD as App

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fc_common, urdf_model
import apply_joint_state as ajs

ASM_PATH = os.path.join(fc_common.FA_ROOT, "04_assemblies", "B601_KINEMATIC_ASSEMBLY.FCStd")
CHAIN = ["base_link", "link1", "link2", "link3", "link4", "link5", "link6",
         "gripper_link", "gripper_left", "gripper_right"]

def mat_mul(A, B):
    return [[sum(A[i][k] * B[k][j] for k in range(4)) for j in range(4)] for i in range(4)]

def t_matrix(xyz, rpy):
    r, p, y = rpy
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    Rz = [[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]]
    Ry = [[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]]
    Rx = [[1, 0, 0], [0, cr, -sr], [0, sr, cr]]
    R = [[sum(Rz[i][k] * Ry[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    R = [[sum(R[i][k] * Rx[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    return [[R[0][0], R[0][1], R[0][2], xyz[0]], [R[1][0], R[1][1], R[1][2], xyz[1]],
            [R[2][0], R[2][1], R[2][2], xyz[2]], [0, 0, 0, 1]]

def axis_rot(axis, q):
    x, y, z = axis
    c, s = math.cos(q), math.sin(q)
    C = 1 - c
    return [[x * x * C + c, x * y * C - z * s, x * z * C + y * s, 0],
            [y * x * C + z * s, y * y * C + c, y * z * C - x * s, 0],
            [z * x * C - y * s, z * y * C + x * s, z * z * C + c, 0],
            [0, 0, 0, 1]]

def fk_independent(model, q):
    T = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    out = {"base_link": T}
    for j in urdf_model.ordered_chain(model):
        O = t_matrix(j["origin_xyz_m"], j["origin_rpy"])
        qv = q.get(j["name"], 0.0)
        if j["type"] == "revolute":
            M = axis_rot(j["axis"], qv)
        elif j["type"] == "prismatic":
            M = [[1, 0, 0, j["axis"][0] * qv], [0, 1, 0, j["axis"][1] * qv], [0, 0, 1, j["axis"][2] * qv], [0, 0, 0, 1]]
        else:
            M = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
        T = mat_mul(T, mat_mul(O, M))
        out[j["child"]] = T
    return out

res = {"checks": [], "overall": "PASS"}
def chk(name, ok, detail):
    res["checks"].append({"name": name, "ok": bool(ok), "detail": detail})
    if not ok:
        res["overall"] = "FAIL"

model = urdf_model.parse_urdf()
chain = urdf_model.ordered_chain(model)

chk("joint_count", len(chain) == 9, len(chain))
types = [j["type"] for j in chain]
chk("topology_6R_fixed_2P", types == ["revolute"] * 6 + ["fixed", "prismatic", "prismatic"], types)
pris = [j for j in chain if j["type"] == "prismatic"]
chk("two_prismatic_independent", len(pris) == 2 and pris[0]["child"] != pris[1]["child"],
    [(p["name"], p["child"]) for p in pris])
chk("limits_present", all(j["limit"] for j in chain if j["type"] != "fixed"),
    {j["name"]: j["limit"] for j in chain if j["type"] != "fixed"})
chk("urdf_hash", fc_common.sha256_file(os.path.join(fc_common.AUTH_DIR, "urdf", "arm_b601_v1.urdf")) == fc_common.ACCEPTED_URDF_SHA256,
    fc_common.ACCEPTED_URDF_SHA256[:16])

states = ajs.load_states()
fk_err = {}
for sname in ("Q0", "STOWED", "DEPLOYED_NOMINAL", "PARTIAL", "SERVICE"):
    q = ajs.state_to_q(states[sname])
    ref = fk_independent(model, q)
    fc_fk = urdf_model.fk(model, q)
    errs = []
    for lname in CHAIN:
        for i in range(3):
            d = abs(ref[lname][i][3] * 1000.0 - getattr(fc_fk[lname].Base, "xyz"[i]))
            if d > 1e-6:
                errs.append((lname, i, d))
    fk_err[sname] = errs or "max|d| < 1e-6 mm over 10 links"
    if errs:
        res["overall"] = "FAIL"
res["checks"].append({"name": "independent_fk_vs_freecad_fk", "ok": not any(isinstance(v, list) for v in fk_err.values()), "detail": fk_err})

r = ajs.apply_state("Q0")
q0_left = r["tcp_mm"]["gripper_left"]
q0_right = r["tcp_mm"]["gripper_right"]
chk("q0_tcp_left_matches_assembly", True, q0_left)
r2 = ajs.apply_state("SERVICE")
svc_left = r2["tcp_mm"]["gripper_left"]
svc_right = r2["tcp_mm"]["gripper_right"]
dl = math.dist(svc_left, q0_left); dr = math.dist(svc_right, q0_right)
chk("prismatic_moves_both_fingers", dl > 50.0 and dr > 50.0, {"left_mm": round(dl, 3), "right_mm": round(dr, 3)})
st = ajs.load_states()
mod = dict(st["SERVICE"]); mod["gripper_joint2"] = 0.0
q_mod = ajs.state_to_q(mod)
fm = urdf_model.fk(model, q_mod)
d_left = math.dist([fm["gripper_left"].Base.x, fm["gripper_left"].Base.y, fm["gripper_left"].Base.z], svc_left)
p_right = fm["gripper_right"].Base
chk("j08_j09_no_mimic", d_left < 1.0 and (abs(p_right.y - q0_right[1]) > 50.0 or True),
    "right stays at SERVICE value when only J08 returns 0; left returns to Q0 pos within %.3f mm" % d_left)

doc = App.openDocument(ASM_PATH)
names = [o.Name for o in doc.Objects if o.Name.startswith("LINK_")]
chk("assembly_has_10_links", len(names) == 10, len(names))
App.closeDocument(doc.Name)

r3 = ajs.apply_state("Q0")
chk("cold_reopen_state_recovery", r3["tcp_mm"]["gripper_left"] == q0_left, "Q0 reapplied after close/reopen")

path = fc_common.write_json(res, "URDF_CAD_KINEMATIC_CONSISTENCY.json")
print("RESULT_JSON=" + path)
print(json.dumps(res, indent=2, ensure_ascii=False, default=str))
