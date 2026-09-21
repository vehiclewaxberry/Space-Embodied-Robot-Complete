# build_kinematic_assembly.py — B601_KINEMATIC_ASSEMBLY.FCStd: 10 linked carriers at FK(Q0).
import os, sys, json
import FreeCAD as App

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fc_common, urdf_model

DOC_NAME = "B601_KINEMATIC_ASSEMBLY"
ASM_PATH = os.path.join(fc_common.FA_ROOT, "04_assemblies", DOC_NAME + ".FCStd")
CARRIER_DIR = os.path.join(fc_common.FA_ROOT, "02_carriers")
CHAIN = ["base_link", "link1", "link2", "link3", "link4", "link5", "link6",
         "gripper_link", "gripper_left", "gripper_right"]

def build():
    model = urdf_model.parse_urdf()
    fk0 = urdf_model.fk(model, {})
    if DOC_NAME in App.listDocuments():
        App.closeDocument(DOC_NAME)
    doc = App.newDocument(DOC_NAME)
    doc.Comment = "B601 kinematic assembly. Carriers linked from 02_carriers. FK-driven placements. Joints J00-J09 per register."
    doc.saveAs(ASM_PATH)  # App::Link to external docs requires a saved owner document
    root = doc.addObject("App::Part", "B601_KINEMATIC_CHAIN")
    root.addProperty("App::PropertyString", "URDF_SHA256").URDF_SHA256 = fc_common.ACCEPTED_URDF_SHA256
    root.addProperty("App::PropertyString", "TOPOLOGY").TOPOLOGY = "6R + 1 fixed + 2P (J00 baseline fixed, J01-J06 revolute, J07 fixed, J08/J09 prismatic)"

    reg = urdf_model.joint_register(model)
    jreg = doc.addObject("App::FeaturePython", "JOINT_REGISTER")
    jreg.addProperty("App::PropertyString", "JSON").JSON = json.dumps(reg)
    jreg.addProperty("App::PropertyString", "STATE_SOURCE").STATE_SOURCE = "09_scripts/joint_states.yaml (twin joint_states.json)"
    jreg.addProperty("App::PropertyString", "GRIPPER_P_INDEPENDENT").GRIPPER_P_INDEPENDENT = "J08/J09 independent, no mimic"

    links_made = {}
    for lname in CHAIN:
        carrier_file = os.path.join(CARRIER_DIR, "B601_CARRIER_" + lname.upper() + ".FCStd")
        link = doc.addObject("App::Link", "LINK_" + lname.upper())
        cdoc = App.openDocument(carrier_file)
        link.setLink(cdoc.getObject("CARRIER_ROOT"))
        link.Placement = fk0[lname]
        root.addObject(link)
        links_made[lname] = {
            "x": round(fk0[lname].Base.x, 6), "y": round(fk0[lname].Base.y, 6), "z": round(fk0[lname].Base.z, 6),
        }

    doc.recompute()
    doc.saveAs(ASM_PATH)
    res = {"assembly": ASM_PATH, "links": len(links_made), "fk_q0_mm": links_made,
           "tcp_gripper_left_q0_mm": links_made["gripper_left"],
           "tcp_gripper_right_q0_mm": links_made["gripper_right"]}
    App.closeDocument(DOC_NAME)
    return res

if __name__ == "__main__" or True:
    res = build()
    res["sha256"] = fc_common.sha256_file(ASM_PATH)
    path = fc_common.write_json(res, "build_kinematic_assembly_result.json")
    print("RESULT_JSON=" + path)
    print(json.dumps(res, indent=2, ensure_ascii=False))
