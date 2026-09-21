# build_carriers.py — create 10 datum-only B601 carriers from accepted URDF.
import os, sys, json
import FreeCAD as App

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fc_common, urdf_model

CARRIER_DIR = os.path.join(fc_common.FA_ROOT, "02_carriers")

def mm(v):
    return [x * 1000.0 for x in v]

def build():
    model = urdf_model.parse_urdf()
    chain = urdf_model.ordered_chain(model)
    by_child = {j["child"]: j for j in chain}
    child_joints = {}
    for j in chain:
        child_joints.setdefault(j["parent"], []).append(j)

    made = []
    for lname, link in model["links"].items():
        doc_name = "B601_CARRIER_" + lname.upper()
        if doc_name in App.listDocuments():
            App.closeDocument(doc_name)
        doc = App.newDocument(doc_name)
        doc.Comment = "Datum-only carrier for %s. No solid, no CAD mass. URDF authority %s" % (lname, fc_common.ACCEPTED_URDF_SHA256[:12])
        root = doc.addObject("App::Part", "CARRIER_ROOT")
        root.addProperty("App::PropertyString", "URDF_LINK").URDF_LINK = lname
        root.addProperty("App::PropertyString", "URDF_SHA256").URDF_SHA256 = fc_common.ACCEPTED_URDF_SHA256
        root.addProperty("App::PropertyFloat", "URDF_MASS_KG").URDF_MASS_KG = link.get("mass_kg", 0.0)
        root.addProperty("App::PropertyString", "ROLE").ROLE = "CARRIER_DATUM_ONLY_NO_SOLID_NO_CAD_MASS"

        def lcs(name, xyz=None, rpy=None):
            o = doc.addObject("App::LocalCoordinateSystem", name)
            if xyz is not None:
                o.Placement.Base = App.Vector(*mm(xyz))
            if rpy is not None:
                o.Placement.Rotation = urdf_model._rot_rpy(rpy)
            root.addObject(o)
            return o

        lcs("CS_LINK")
        j_in = by_child.get(lname)
        if j_in is not None:
            lcs("CS_JOINT_IN_" + j_in["name"].upper())
            ax = doc.addObject("App::LocalCoordinateSystem", "AXIS_" + j_in["name"].upper())
            import math
            axis = j_in["axis"]
            z = App.Vector(0, 0, 1)
            a = App.Vector(*axis)
            if a.Length > 1e-12:
                a.normalize()
                rot = App.Rotation(z, a)
                ax.Placement.Rotation = rot
            ax.addProperty("App::PropertyVector", "AXIS_VECTOR_URDF").AXIS_VECTOR_URDF = App.Vector(*axis)
            ax.addProperty("App::PropertyString", "JOINT_TYPE").JOINT_TYPE = j_in["type"]
            if j_in["limit"]:
                ax.addProperty("App::PropertyFloat", "LIMIT_LOWER").LIMIT_LOWER = j_in["limit"]["lower"]
                ax.addProperty("App::PropertyFloat", "LIMIT_UPPER").LIMIT_UPPER = j_in["limit"]["upper"]
            root.addObject(ax)
        lcs("PLANE_ZERO")
        lcs("CS_VISUAL_MOUNT")
        lcs("CS_COLLISION_MOUNT")
        if "com_xyz_m" in link:
            lcs("CS_COM", xyz=link["com_xyz_m"])
        for j_out in child_joints.get(lname, []):
            lcs("CS_JOINT_OUT_" + j_out["name"].upper(), xyz=j_out["origin_xyz_m"], rpy=j_out["origin_rpy"])

        doc.recompute()
        path = os.path.join(CARRIER_DIR, doc_name + ".FCStd")
        doc.saveAs(path)
        App.closeDocument(doc_name)
        made.append({"link": lname, "file": path, "mass_kg": link.get("mass_kg", 0.0)})

    reg = urdf_model.joint_register(model)
    res = {"carriers": made, "carrier_count": len(made),
           "joint_register": reg, "joint_count": len(reg),
           "topology": "6R + 1 fixed + 2P",
           "total_mass_kg": urdf_model.total_mass(model)}
    return res

if __name__ == "__main__" or True:
    res = build()
    for c in res["carriers"]:
        c["sha256"] = fc_common.sha256_file(c["file"])
    path = fc_common.write_json(res, "build_carriers_result.json")
    print("RESULT_JSON=" + path)
    print(json.dumps({"carrier_count": res["carrier_count"], "joint_count": res["joint_count"],
                      "total_mass_kg": res["total_mass_kg"]}, indent=2))
