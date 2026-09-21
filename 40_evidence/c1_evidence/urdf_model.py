# urdf_model.py — parse accepted URDF into registers; FK for the 6R+1fixed+2P chain.
# Units: URDF is SI (m, rad). FreeCAD project units: mm. All conversions explicit.
import os, sys, math, json
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fc_common

def _f(s):
    return float(s)

def parse_urdf(path=None):
    path = path or os.path.join(fc_common.AUTH_DIR, "urdf", "arm_b601_v1.urdf")
    tree = ET.parse(path)
    root = tree.getroot()
    links, joints = {}, []
    for el in root.findall("link"):
        name = el.get("name")
        iner = el.find("inertial")
        rec = {"name": name}
        if iner is not None:
            o = iner.find("origin")
            rec["com_xyz_m"] = [_f(v) for v in o.get("xyz").split()] if o is not None else [0, 0, 0]
            rec["mass_kg"] = _f(iner.find("mass").get("value"))
            i = iner.find("inertia")
            rec["inertia"] = {k: _f(i.get(k)) for k in ("ixx", "ixy", "ixz", "iyy", "iyz", "izz")}
        links[name] = rec
    for el in root.findall("joint"):
        o = el.find("origin")
        ax = el.find("axis")
        lim = el.find("limit")
        joints.append({
            "name": el.get("name"),
            "type": el.get("type"),
            "parent": el.find("parent").get("link"),
            "child": el.find("child").get("link"),
            "origin_xyz_m": [_f(v) for v in o.get("xyz").split()],
            "origin_rpy": [_f(v) for v in o.get("rpy").split()],
            "axis": [_f(v) for v in ax.get("xyz").split()] if ax is not None else [0, 0, 0],
            "limit": {"lower": _f(lim.get("lower")), "upper": _f(lim.get("upper")),
                      "effort": _f(lim.get("effort")), "velocity": _f(lim.get("velocity"))} if lim is not None else None,
        })
    return {"links": links, "joints": joints}

def ordered_chain(model):
    """Return joints ordered base->tip following parent/child."""
    by_parent = {}
    for j in model["joints"]:
        by_parent.setdefault(j["parent"], []).append(j)
    chain, cursor = [], "base_link"
    while cursor in by_parent:
        nxt = by_parent[cursor]
        for j in nxt:
            chain.append(j)
        cursor = nxt[-1]["child"]
    return chain

def _rot_rpy(rpy):
    import FreeCAD as App
    r = App.Rotation()
    r.setYawPitchRoll(math.degrees(rpy[2]), math.degrees(rpy[1]), math.degrees(rpy[0]))
    return r

def joint_origin_placement(j):
    import FreeCAD as App
    p = App.Placement()
    p.Base = App.Vector(*[v * 1000.0 for v in j["origin_xyz_m"]])  # m -> mm
    p.Rotation = _rot_rpy(j["origin_rpy"])
    return p

def fk(model, q_by_joint, upto=None):
    """Forward kinematics. q in rad (revolute) or m (prismatic, keyed by joint name).
    Returns dict link_name -> App.Placement (mm, world=base_link frame)."""
    import FreeCAD as App
    T = App.Placement()
    out = {"base_link": T.copy()}
    for j in ordered_chain(model):
        if upto and j["name"] == upto:
            pass
        O = joint_origin_placement(j)
        M = App.Placement()
        q = q_by_joint.get(j["name"], 0.0)
        if j["type"] == "revolute":
            M.Rotation = App.Rotation(App.Vector(*j["axis"]), math.degrees(q))
        elif j["type"] == "prismatic":
            M.Base = App.Vector(*[a * q * 1000.0 for a in j["axis"]])
        Tj = O.multiply(M)
        T = T.multiply(Tj)
        out[j["child"]] = T.copy()
        if upto and j["name"] == upto:
            break
    return out

def total_mass(model):
    return round(sum(l.get("mass_kg", 0.0) for l in model["links"].values()), 16)

def joint_register(model):
    reg = []
    for idx, j in enumerate(ordered_chain(model)):
        reg.append({
            "index": idx, "joint_id": "J%02d" % idx, "name": j["name"], "type": j["type"],
            "parent": j["parent"], "child": j["child"],
            "origin_xyz_m": j["origin_xyz_m"], "origin_rpy": j["origin_rpy"],
            "axis": j["axis"], "limit": j["limit"],
        })
    return reg

if __name__ == "__main__":
    m = parse_urdf()
    print(json.dumps({
        "links": len(m["links"]),
        "joints": len(m["joints"]),
        "types": [j["type"] for j in ordered_chain(m)],
        "total_mass_kg": total_mass(m),
    }, indent=2))
